"""scenes/gacha_scene.py — the Gachapón room and its show; plus its pixel-art assets.

Covers the asset loader (scale, strips, anchors), the generator contract
(capsule halves add up to the closed one, crank frames differ), phase order of a
pull, skipping, auto-open, buttons and keys, refusing a pull without gold or
while busy, exit, drawing every phase for every tier (shake / rays / confetti),
the drop path ending on the stage, pull counter and a 10 000-step stress run.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pygame
import pytest

from src.application.run_manager import _all_relic_defs, create_run
from src.domain.character import ALL_CHARACTERS
from src.domain.gacha import PullKind
from src.domain.rarity import Rarity
from src.infrastructure.fonts import FontRegistry
from src.infrastructure.gacha_assets import load_gacha_assets
from src.presentation.scenes import gacha_scene as gs
from src.presentation.scenes.gacha_scene import GachaScene

ROOT = Path(__file__).resolve().parents[3]


def _scene(gold: int = 5000) -> GachaScene:
    run = create_run(ALL_CHARACTERS[0], 4)
    run.gold = gold
    return GachaScene(run, FontRegistry())


def _run(scene, seconds, step=1 / 60):
    t = 0.0
    while t < seconds - 1e-9:
        dt = min(step, seconds - t)
        scene.update(dt)
        t += dt


def _with_tier(scene, rarity):
    scene._result.relic = next(r for r in _all_relic_defs() if r.rarity is rarity)


class TestAssets:
    def test_loads(self):
        assert load_gacha_assets() is not None

    def test_machine_scaled_x2(self):
        a = load_gacha_assets()
        assert a.machine.get_size() == (a.meta["size"][0] * 2, a.meta["size"][1] * 2)

    def test_five_tiers_three_parts(self):
        a = load_gacha_assets()
        assert len(a.big) == 5 and all(set(t) == {"closed", "top", "bottom"} for t in a.big)

    def test_crank_frames(self):
        assert len(load_gacha_assets().crank) == 8

    def test_points_inside_machine(self):
        a = load_gacha_assets()
        w, h = a.machine.get_size()
        assert all(0 < a.point(n)[0] < w and 0 < a.point(n)[1] < h for n in ("slot", "crank"))


class TestGenerator:
    @pytest.fixture(scope="class")
    def gen(self):
        spec = importlib.util.spec_from_file_location("generate_gacha_sprites",
                                                      ROOT / "scripts" / "generate_gacha_sprites.py")
        mod = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = mod
        spec.loader.exec_module(mod)
        return mod

    @staticmethod
    def _count(cv):
        return sum(1 for row in cv.px for c in row if c is not None)

    def test_halves_cover_the_capsule(self, gen):
        t = gen.TIER[2]
        closed = self._count(gen.capsule(52, t))
        halves = self._count(gen.capsule(52, t, "top")) + self._count(gen.capsule(52, t, "bottom"))
        assert abs(halves - closed) < closed * 0.25

    def test_crank_rotates(self, gen):
        frames = gen.crank_frames()
        assert frames[0].px != frames[2].px

    def test_tier_capsules_differ(self, gen):
        assert gen.capsule(22, gen.TIER[0]).px != gen.capsule(22, gen.TIER[4]).px

    def test_machine_has_pixels(self, gen):
        assert self._count(gen.machine()) > 10_000


class TestFlow:
    def test_starts_idle(self):
        assert _scene().phase == "idle"

    def test_pull_starts_coin(self):
        s = _scene()
        assert s.start_pull(PullKind.NORMAL) and s.phase == "coin"

    def test_phase_order(self):
        s = _scene()
        s.start_pull(PullKind.NORMAL)
        seen = []
        for _ in range(600):
            s.update(1 / 60)
            if not seen or seen[-1] != s.phase:
                seen.append(s.phase)
        assert seen[:4] == ["coin", "crank", "drop", "present"]

    def test_auto_open(self):
        s = _scene()
        s.start_pull(PullKind.NORMAL)
        _run(s, gs.COIN_T + gs.CRANK_T + gs.DROP_T + gs.PRESENT_AUTO + 0.2)
        assert s.phase in ("open", "reveal")

    def test_click_skips_to_present(self):
        s = _scene()
        s.start_pull(PullKind.NORMAL)
        s.advance()
        assert s.phase == "present"

    def test_full_cycle_back_to_idle(self):
        s = _scene()
        s.start_pull(PullKind.STELLAR)
        s.skip_to_reveal()
        s.advance()
        _run(s, gs.COLLECT_T + 0.1)
        assert s.phase == "idle"

    def test_relic_not_given_before_deciding(self):
        s = _scene()
        n = len(s._run.relics)
        s.start_pull(PullKind.NORMAL)
        s.skip_to_reveal()
        assert len(s._run.relics) == n

    def test_keep_gives_the_relic(self):
        s = _scene()
        s.start_pull(PullKind.NORMAL)
        s.skip_to_reveal()
        s.keep()
        assert s._run.relics[-1] is s.result.relic and s.phase == "collect"

    def test_decline_gives_nothing(self):
        s = _scene()
        gold = s._run.gold
        s.start_pull(PullKind.NORMAL)
        s.skip_to_reveal()
        s.decline()
        assert s._run.relics == [] and s.phase == "discard" and s._run.gold < gold

    def test_decline_returns_to_idle(self):
        s = _scene()
        s.start_pull(PullKind.NORMAL)
        s.skip_to_reveal()
        s.decline()
        _run(s, gs.DISCARD_T + 0.1)
        assert s.phase == "idle"

    def test_decline_only_in_reveal(self):
        s = _scene()
        s.start_pull(PullKind.NORMAL)
        assert not s.decline() and s.phase == "coin"

    def test_reveal_click_outside_buttons_does_nothing(self):
        s = _scene()
        s.start_pull(PullKind.NORMAL)
        s.skip_to_reveal()
        s.draw(pygame.Surface((1280, 720)))
        s.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=(20, 700)))
        assert s.phase == "reveal"

    def test_reveal_buttons_by_mouse(self):
        s = _scene()
        s.start_pull(PullKind.NORMAL)
        s.skip_to_reveal()
        s.draw(pygame.Surface((1280, 720)))
        s.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=gs._BTN_DECLINE.center))
        assert s.phase == "discard"

    def test_key_r_declines(self):
        s = _scene()
        s.start_pull(PullKind.NORMAL)
        s.skip_to_reveal()
        s.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_r, mod=0, unicode="r"))
        assert s.phase == "discard"

    def test_busy_refuses_second_pull(self):
        s = _scene()
        s.start_pull(PullKind.NORMAL)
        assert not s.start_pull(PullKind.NORMAL) and s._run.gacha_pulls == 1

    def test_poor_refused_with_message(self):
        s = _scene(gold=10)
        assert not s.start_pull(PullKind.STELLAR) and s._feedback_t > 0 and s.phase == "idle"

    def test_key_1_and_2(self):
        s = _scene()
        s.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_2, mod=0, unicode="2"))
        assert s.result.kind is PullKind.STELLAR

    def test_click_buttons(self):
        s = _scene()
        s.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=gs._BTN_NORMAL.center))
        assert s.phase == "coin" and s.result.kind is PullKind.NORMAL

    def test_exit(self):
        s = _scene()
        s.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=gs._EXIT.center))
        assert s.cleared

    def test_exit_ignored_while_animating(self):
        s = _scene()
        s.start_pull(PullKind.NORMAL)
        s.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=gs._EXIT.center))
        assert not s.cleared

    def test_drop_ends_on_stage(self):
        s = _scene()
        x, y, grow = s._drop_pos(gs.DROP_T)
        assert (round(x), round(y), grow) == (round(gs._STAGE[0]), round(gs._STAGE[1]), 1.0)

    def test_drop_never_below_floor(self):
        s = _scene()
        assert all(s._drop_pos(k / 100 * gs.FALL_T)[1] <= gs._FLOOR_Y + 1e-6 for k in range(101))

    def test_shakes_per_tier(self):
        s = _scene()
        s.start_pull(PullKind.NORMAL)
        _with_tier(s, Rarity.LEGENDARY)
        assert s._shakes() == 5

    def test_epic_open_shakes_screen(self):
        s = _scene()
        s.start_pull(PullKind.NORMAL)
        _with_tier(s, Rarity.EPIC)
        s.skip_to_reveal()
        s2 = _scene()
        s2.start_pull(PullKind.NORMAL)
        _with_tier(s2, Rarity.EPIC)
        s2.advance()
        s2.advance()
        assert s2._shake > 0

    def test_legendary_confetti(self):
        s = _scene()
        s.start_pull(PullKind.NORMAL)
        _with_tier(s, Rarity.LEGENDARY)
        s.advance()
        before = s.particle_count
        s.advance()
        assert s.particle_count - before > 150


class TestSpectacle:
    def test_vortex_during_crank(self):
        s = _scene()
        s.start_pull(PullKind.NORMAL)
        _run(s, gs.COIN_T + gs.CRANK_T * 0.5)
        assert s.phase == "crank" and s._swirl() == pytest.approx(1.0)

    def test_no_vortex_in_idle(self):
        assert _scene()._swirl() == 0.0

    def test_thunk_hops_and_shakes(self):
        s = _scene()
        s.start_pull(PullKind.NORMAL)
        _run(s, gs.COIN_T + gs.CRANK_T * gs.THUNK_AT + 0.02)
        assert s._jump > 0 and s._shake > 0

    def test_lightning_for_epic(self):
        s = _scene()
        s.start_pull(PullKind.NORMAL)
        _with_tier(s, Rarity.EPIC)
        seen = 0
        for _ in range(int((gs.COIN_T + gs.CRANK_T * 0.8) * 60)):
            s.update(1 / 60)
            seen = max(seen, len(s._bolts))
        assert seen > 0

    def test_focus_darkens_while_working(self):
        s = _scene()
        s.start_pull(PullKind.NORMAL)
        _run(s, gs.COIN_T + 0.6)
        assert s._focus > 0.5

    def test_focus_fades_back(self):
        s = _scene()
        s.start_pull(PullKind.NORMAL)
        s.skip_to_reveal()
        s.keep()
        _run(s, gs.COLLECT_T + 2.0)
        assert s._focus < 0.05

    def test_shockwave_on_pop(self):
        s = _scene()
        s.start_pull(PullKind.NORMAL)
        _run(s, gs.COIN_T + gs.CRANK_T + 0.05)
        assert s.phase == "drop" and s._rings


class TestDraw:
    @pytest.mark.parametrize("rarity", list(Rarity))
    def test_every_phase_draws(self, rarity):
        s = _scene()
        surf = pygame.Surface((1280, 720))
        s.draw(surf)
        s.start_pull(PullKind.NORMAL)
        _with_tier(s, rarity)
        for k in range(400):
            s.update(1 / 20)
            if k % 3 == 0:
                s.draw(surf)
            if s.phase == "present" and s._t > 1.5:
                s.advance()
            if s.phase == "reveal":
                if rarity is Rarity.RARE:
                    s.decline()
                else:
                    s.advance()
        assert s.phase == "idle"

    def test_hover_buttons(self):
        s = _scene()
        s.handle_event(pygame.event.Event(pygame.MOUSEMOTION, pos=gs._BTN_STELLAR.center, rel=(0, 0), buttons=(0, 0, 0)))
        s.draw(pygame.Surface((1280, 720)))
        assert s._hovered == "stellar"


class TestStress:
    def test_10000_steps_bounded(self):
        s = _scene(gold=10 ** 12)
        surf = pygame.Surface((1280, 720))
        for k in range(10_000):
            if s.phase == "idle":
                s.start_pull(PullKind.STELLAR if k % 2 else PullKind.NORMAL)
            elif s.phase == "reveal" and k % 3 == 0:
                s.decline()
            elif k % 37 == 0:
                s.advance()
            s.update(1 / 60 if k % 50 else 10 ** 9)
            if k % 500 == 0:
                s.draw(surf)
        assert s.particle_count <= s._fx.capacity and s._run.gacha_pulls > 20
