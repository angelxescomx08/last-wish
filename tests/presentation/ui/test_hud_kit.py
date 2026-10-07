"""Pixel-art HUD kit and hero sheet.

Covers ``scripts/generate_ui_kit.py`` (assets match, every piece present),
``infrastructure/ui_kit`` (exact sizes, tiling, cache, missing names),
``ui/pixel_ui`` (buttons in every style/state, key caps, ribbon, mana orb effects:
spend splash, refill flash, can't-pay shake, eased level, empty max), the HUD widgets
(End Turn ready/disabled, piles), ``application/hero_stats`` (base, per-relic sources,
Pruebas, live combat values, odds, deck by type), ``ui/hero_sheet`` (bars fill in
order, closing rules, every phase drawn, stress) and the SceneManager / CombatScene
wiring (C key, hero button, Escape order, End Turn locked while enemies act).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import Mock

import pygame
import pytest

from main import SceneManager
from src.application import enemy_ai
from src.application.combat_factory import create_combat_from_run
from src.application.hero_stats import BASE_DRAW, hero_sheet
from src.application.run_manager import create_run, generate_enemies
from src.domain.card import CardType
from src.domain.character import ALL_CHARACTERS
from src.domain.entities import POISON, StatusEffect
from src.domain.mana import Mana
from src.domain.relic import Relic, RelicTag
from src.domain.tuning import TUNING
from src.infrastructure.fonts import FontRegistry
from src.infrastructure.preferences import UserPreferences
from src.infrastructure.ui_icons import has_ui_icon
from src.infrastructure.ui_kit import UI_DIR, has_kit, kit_names, kit_piece, kit_slice
from src.presentation.scenes.combat_scene import CombatScene
from src.presentation.scenes.main_menu_scene import MainMenuScene
from src.presentation.ui.hero_sheet import CLOSE, PANEL, HeroSheetOverlay
from src.presentation.ui.hud_widget import draw_end_turn_button, draw_pile_widget, draw_turn_counter
from src.presentation.ui.pause_menu import stats_button_rect
from src.presentation.ui.pixel_ui import (
    ManaOrb, button_state, draw_button, draw_keycap, draw_panel, draw_ribbon, draw_topbar, draw_trim,
)

FONTS = FontRegistry()


def _surf() -> pygame.Surface:
    return pygame.Surface((1280, 720), pygame.SRCALPHA)


def _run(hero: int = 0, seed: int = 3):
    return create_run(ALL_CHARACTERS[hero], seed)


def _relic(tag: RelicTag, name: str = "R") -> Relic:
    return Relic(name.lower(), name, "", tag=tag)


# ---------------------------------------------------------------- kit assets

class TestKitAssets:
    PIECES = ["panel", "orb_back", "orb_frame", "orb_glass", "pile_draw", "pile_discard", "pile_empty",
              "topbar", "trim", "ribbon"] + [f"orb_liquid_{i}" for i in range(8)] + [
        f"btn_{style}_{state}" for style in ("bronze", "gold") for state in ("idle", "hover", "press", "off")]

    def test_kit_loads(self):
        assert has_kit()

    @pytest.mark.parametrize("name", PIECES)
    def test_piece_exists(self, name):
        assert name in kit_names() and kit_piece(name) is not None

    def test_generator_matches_assets(self):
        sys.path.insert(0, str(Path(__file__).parents[3] / "scripts"))
        import generate_ui_kit as gen
        _, meta = gen.build()
        assert meta == json.loads((UI_DIR / "kit.json").read_text(encoding="utf-8"))

    @pytest.mark.parametrize("name", ["gear", "helmet", "bag", "hand_cards", "clover", "tower",
                                      "hourglass", "deck", "coin"])
    def test_hud_icons(self, name):
        assert has_ui_icon(name)

    def test_scale(self):
        assert kit_piece("orb_frame", 2).get_size() == (96, 96)

    @pytest.mark.parametrize("size", [(48, 48), (290, 42), (1000, 600), (17, 17), (601, 33)])
    def test_nine_slice_exact_size(self, size):
        assert kit_slice("panel", *size).get_size() == size

    @pytest.mark.parametrize("size", [(64, 36), (196, 48), (430, 52), (10, 36)])
    def test_three_slice_exact_size(self, size):
        assert kit_slice("btn_bronze_idle", *size).get_size() == size

    def test_slice_cached(self):
        assert kit_slice("panel", 200, 100) is kit_slice("panel", 200, 100)

    def test_corners_kept_when_tiled(self):
        small, big = kit_slice("panel", 48, 48), kit_slice("panel", 480, 48)
        assert small.get_at((3, 3)) == big.get_at((3, 3))

    def test_missing(self):
        assert kit_piece("nope") is None and kit_slice("nope", 10, 10) is None


# ---------------------------------------------------------------- widgets

class TestPixelWidgets:
    @pytest.mark.parametrize("style", ["bronze", "gold"])
    @pytest.mark.parametrize("state", ["idle", "hover", "press", "off"])
    def test_button_states(self, style, state):
        rect = pygame.Rect(100, 100, 200, 40)
        assert draw_button(_surf(), rect, "Hola", FONTS, style=style, state=state, icon="gear", key="E",
                           t=1.3, glow=0.5) == rect

    def test_button_without_label(self):
        draw_button(_surf(), pygame.Rect(0, 0, 64, 36), "", FONTS, icon="helmet", key="C")

    def test_button_state(self):
        rect = pygame.Rect(0, 0, 10, 10)
        assert [button_state(rect, (5, 5), False), button_state(rect, (5, 5), True),
                button_state(rect, (50, 5), True), button_state(rect, (5, 5), False, enabled=False)] == \
            ["hover", "press", "idle", "off"]

    def test_frames(self):
        surf = _surf()
        draw_panel(surf, pygame.Rect(10, 10, 300, 200))
        draw_topbar(surf)
        draw_trim(surf, 465)
        assert draw_ribbon(surf, (640, 30), "TURNO 3", FONTS).centerx == 640
        assert draw_keycap(surf, (50, 50), "Esc", FONTS).center == (50, 50)

    def test_turn_counter_ribbon(self):
        assert draw_turn_counter(_surf(), 12, 660, 34, FONTS).width > 60

    def test_end_turn_variants(self):
        for kwargs in ({}, {"hovered": True}, {"hovered": True, "pressed": True}, {"enabled": False},
                       {"ready": True, "t": 0.3}):
            assert draw_end_turn_button(_surf(), 1074, 9, 196, 48, FONTS, **kwargs).size == (196, 48)

    @pytest.mark.parametrize("count", [0, 1, 99, 10 ** 6])
    def test_piles(self, count):
        for kind in ("ROBO", "DESCARTE"):
            assert draw_pile_widget(_surf(), kind, count, 1160, 484, FONTS, hovered=count == 1).x == 1160


class TestManaOrb:
    def test_first_update_syncs(self):
        orb = ManaOrb()
        orb.update(0.0, Mana(2, 4))
        assert orb.level == pytest.approx(0.5) and orb.shown == 2

    def test_spend_splashes(self):
        orb = ManaOrb()
        orb.update(0.0, Mana(3, 3))
        orb.update(1 / 60, Mana(1, 3))
        assert orb.splash > 0 and orb._particles.count > 0 and orb.level > 1 / 3

    def test_level_eases_to_target(self):
        orb = ManaOrb()
        orb.update(0.0, Mana(3, 3))
        for _ in range(120):
            orb.update(1 / 60, Mana(0, 3))
        assert orb.level == pytest.approx(0.0, abs=1e-3)

    def test_refill_flashes(self):
        orb = ManaOrb()
        orb.update(0.0, Mana(0, 3))
        orb.update(1 / 60, Mana(3, 3))
        assert orb.flash > 0

    def test_error_shakes(self):
        orb = ManaOrb()
        orb.error()
        orb.update(0.1, Mana(0, 3))
        assert 0 < orb.shake < 0.45

    def test_zero_maximum(self):
        orb = ManaOrb()
        orb.update(0.0, Mana(0, 0))
        assert orb.level == 0.0
        orb.draw(_surf(), (68, 595), FONTS, Mana(0, 0))

    def test_draw_rect(self):
        orb = ManaOrb()
        orb.update(0.0, Mana(2, 3))
        assert orb.draw(_surf(), (100, 100), FONTS, Mana(2, 3)).center == (100, 100)

    def test_huge_dt_and_stress(self):
        orb = ManaOrb()
        for k in range(3000):
            orb.update(10 ** 9 if k == 7 else 1 / 60, Mana(k % 4, 3))
        assert orb._particles.count <= 160
        orb.draw(_surf(), (68, 595), FONTS, Mana(1, 3))


# ---------------------------------------------------------------- hero stats

class TestHeroStats:
    @pytest.mark.parametrize("hero", range(3))
    def test_base_values(self, hero):
        run = _run(hero)
        sheet = hero_sheet(run)
        st = run.character.stats
        assert [sheet.stat(k).value for k in ("hp", "mana", "attack", "dexterity", "luck", "draw")] == \
            [st.max_hp, st.max_mana, st.damage, st.dexterity, st.luck, BASE_DRAW]

    def test_no_bonus_without_relics(self):
        assert all(s.bonus == 0 and not s.sources for s in hero_sheet(_run()).stats)

    def test_relic_sources(self):
        run = _run()
        run.relics += [_relic(RelicTag.FIRE_ORB, "Orbe de Fuego"), _relic(RelicTag.IRON_HEART, "Corazón"),
                       _relic(RelicTag.SILVER_HORSESHOE, "Herradura"), _relic(RelicTag.BROKEN_TOTEM, "Tótem"),
                       _relic(RelicTag.COMBAT_AMULET, "Amuleto")]
        sheet = hero_sheet(run)
        assert sheet.stat("attack").bonus == 2 and "Orbe de Fuego +2" in sheet.stat("attack").breakdown()
        assert sheet.stat("hp").bonus == 15 and sheet.stat("luck").bonus == 30
        assert sheet.stat("draw").value == BASE_DRAW + 1 and sheet.stat("mana").bonus == 1

    def test_golden_relic_doubles(self):
        run = _run()
        orb = _relic(RelicTag.FIRE_ORB, "Orbe")
        from src.domain.chroma import Chroma
        orb.chroma = Chroma.GOLDEN
        run.relics.append(orb)
        assert hero_sheet(run).stat("attack").bonus == 4

    def test_inactive_relic_ignored(self):
        run = _run()
        run.relics.append(Relic("o", "Orbe", "", tag=RelicTag.FIRE_ORB, is_active=False))
        assert hero_sheet(run).stat("attack").bonus == 0

    def test_pruebas_source(self):
        TUNING.extra_damage = 5
        sheet = hero_sheet(_run())
        assert sheet.stat("attack").bonus == 5 and "Pruebas +5" in sheet.stat("attack").breakdown()

    def test_combat_live_values(self):
        run = _run()
        state = create_combat_from_run(run, generate_enemies(run, "r1"))
        state.player.current_hp = 7
        state.player.dexterity += 3
        state.mana.maximum += 2
        state.player.status_effects.append(StatusEffect(POISON, 2, False))
        sheet = hero_sheet(run, state)
        assert sheet.stat("hp").current == 7 and sheet.stat("dexterity").bonus == 3
        assert any(s.label == "Este combate" for s in sheet.stat("mana").sources)
        assert sheet.statuses == [(POISON, 2, False)] and sheet.turn == 1

    def test_hp_current_out_of_combat(self):
        run = _run()
        run.player_current_hp = 12
        assert hero_sheet(run).stat("hp").current == 12

    def test_luck_raises_odds(self):
        low = hero_sheet(_run(0))
        run = _run(0)
        run.relics.append(_relic(RelicTag.SEVEN_LEAF_CLOVER, "Trébol"))
        high = hero_sheet(run)
        assert high.golden_card_chance > low.golden_card_chance
        assert high.epic_relic_chance > low.epic_relic_chance
        assert 0 <= high.golden_relic_chance <= 1

    def test_huge_luck_capped(self):
        TUNING.extra_luck = 10 ** 6
        sheet = hero_sheet(_run())
        assert sheet.golden_card_chance == 1.0 and "100%" in sheet.stat("luck").effect

    def test_deck_by_type(self):
        run = _run()
        sheet = hero_sheet(run)
        assert sum(sheet.deck_by_type.values()) == sheet.deck_size == len(run.deck)
        attacks = sum(1 for c in run.deck if c.card_type == CardType.ATTACK)
        assert sheet.deck_by_type.get("Ataques", 0) == attacks

    def test_every_stat_explained(self):
        assert all(s.effect and s.name and s.icon for s in hero_sheet(_run(2)).stats)


# ---------------------------------------------------------------- overlay

class TestHeroSheetOverlay:
    def _overlay(self, hero=1, combat=True):
        run = _run(hero)
        state = create_combat_from_run(run, generate_enemies(run, "r1")) if combat else None
        if state:
            state.player.status_effects.append(StatusEffect(POISON, 3, False))
        return HeroSheetOverlay(hero_sheet(run, state), FONTS)

    def test_bars_fill_in_order(self):
        o = self._overlay()
        for _ in range(30):
            o.update(1 / 60)
        assert o.fill(0) >= o.fill(3) >= o.fill(6)
        for _ in range(120):
            o.update(1 / 60)
        assert o.fill(6) == 1.0 and len(o._sparked) == len(o.sheet.stats)

    @pytest.mark.parametrize("key", [pygame.K_ESCAPE, pygame.K_c])
    def test_keys_close(self, key):
        o = self._overlay()
        o.handle_event(pygame.event.Event(pygame.KEYDOWN, key=key))
        assert o.closed

    def test_click_close_button_and_outside(self):
        for pos in (CLOSE.center, (5, 5)):
            o = self._overlay()
            o.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=pos))
            assert o.closed

    def test_click_inside_stays(self):
        o = self._overlay()
        o.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=PANEL.center))
        assert not o.closed

    @pytest.mark.parametrize("hero", range(3))
    def test_draws_every_phase(self, hero):
        o = self._overlay(hero, combat=hero != 2)
        surf = _surf()
        for t in (0.0, 0.1, 0.4, 2.0):
            while o.t < t:
                o.update(1 / 30)
            o.draw(surf)

    def test_stress(self):
        o = self._overlay()
        for k in range(2000):
            o.update(10 ** 9 if k == 3 else 1 / 60)
        o.draw(_surf())


# ---------------------------------------------------------------- wiring

def _manager(room=None):
    fonts = FontRegistry()
    manager = SceneManager(MainMenuScene(fonts), fonts, UserPreferences(), sound=Mock())
    manager._run = _run()
    if room is None:
        room = Mock()
        room._overlay = None
        room.gold_hud_pos = ("topright", (1268, 12))
    manager.push(room)
    return manager, room


def _key(manager, key):
    manager.handle_event(pygame.event.Event(pygame.KEYDOWN, key=key))


class TestWiring:
    def test_c_opens_and_freezes_room(self):
        manager, room = _manager()
        _key(manager, pygame.K_c)
        manager.update(0.5)
        assert manager.hero_sheet is not None
        room.update.assert_not_called()

    def test_c_again_closes(self):
        manager, _ = _manager()
        _key(manager, pygame.K_c)
        _key(manager, pygame.K_c)
        assert manager.hero_sheet is None

    def test_escape_closes_sheet_not_pause(self):
        manager, _ = _manager()
        _key(manager, pygame.K_c)
        _key(manager, pygame.K_ESCAPE)
        assert manager.hero_sheet is None and manager._pause is None

    def test_button_opens(self):
        manager, room = _manager()
        rect = stats_button_rect(room)
        manager.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=rect.center))
        assert manager.hero_sheet is not None

    def test_not_without_run(self):
        fonts = FontRegistry()
        manager = SceneManager(MainMenuScene(fonts), fonts, UserPreferences(), sound=Mock())
        _key(manager, pygame.K_c)
        assert manager.hero_sheet is None

    def test_not_while_room_overlay_open(self):
        manager, room = _manager()
        room._overlay = object()
        _key(manager, pygame.K_c)
        assert manager.hero_sheet is None

    def test_combat_sheet_uses_live_state(self):
        run = _run()
        scene = CombatScene(create_combat_from_run(run, [enemy_ai.create_boss(enemy_ai.HOLLOW_KNIGHT)]),
                            FONTS, sound=Mock())
        manager, _ = _manager(scene)
        manager._run = run
        _key(manager, pygame.K_c)
        assert manager.hero_sheet.sheet.turn == 1
        surf = _surf()
        manager.update(0.5)
        manager.draw(surf)

    def test_manager_draws_buttons_with_hover(self):
        manager, room = _manager()
        manager.handle_event(pygame.event.Event(pygame.MOUSEMOTION, pos=stats_button_rect(room).center,
                                                rel=(0, 0), buttons=(0, 0, 0)))
        manager.draw(_surf())


class TestCombatHud:
    def _scene(self):
        run = _run()
        return CombatScene(create_combat_from_run(run, generate_enemies(run, "r1")), FONTS, sound=Mock())

    def test_nothing_to_play(self):
        scene = self._scene()
        assert not scene.nothing_to_play
        scene.state.mana.current = 0
        assert scene.nothing_to_play

    def test_end_turn_locked_during_enemy_phase(self):
        scene = self._scene()
        scene.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_e))
        assert scene.state.turn == 2
        scene.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_e))
        assert scene.state.turn == 2
        for _ in range(100):
            scene.update(1 / 60)
        scene.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_e))
        assert scene.state.turn == 3 or not scene.state.player.is_alive

    def test_unaffordable_card_shakes_orb(self):
        scene = self._scene()
        scene.state.mana.current = 0
        scene.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_1))
        assert scene._orb.shake > 0

    def test_draws(self):
        scene = self._scene()
        surf = _surf()
        scene.handle_event(pygame.event.Event(pygame.MOUSEMOTION, pos=(1170, 33), rel=(0, 0), buttons=(0, 0, 0)))
        for _ in range(5):
            scene.update(1 / 60)
            scene.draw(surf)
