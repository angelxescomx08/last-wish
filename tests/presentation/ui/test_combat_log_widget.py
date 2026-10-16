"""History strip (``ui/combat_log_widget``) and its wiring in ``CombatScene``.

Layout newest-first, scroll clamp (wheel, drag, arrows), tap to pin, staying still while
reading old entries, tile cache, visible-only drawing, and the scene logging plays and
enemy turns. Includes a 1000-entry stress and a per-frame cost bound.
"""
from __future__ import annotations

import time

import pygame

from src.application.combat_log import CombatLog
from src.application.combat_manager import create_sample_combat
from src.infrastructure.fonts import FontRegistry
from src.presentation.scenes.combat_scene import CombatScene
from src.application.combat_log import HERO, LogTarget
from src.presentation.ui.combat_log_widget import (RECT, SEP, STEP, CombatLogStrip, entry_tooltip,
                                                   render_entry_detail)

pygame.init()
FONTS = FontRegistry()


def _log(n_turns=6, per_turn=3):
    log = CombatLog()
    for t in range(1, n_turns + 1):
        log.turn(t)
        for k in range(per_turn):
            log.enemy(t, "attack_1", f"Enemigo {k} ataca", "1 golpe · pierdes 3 de vida", 3)
    return log


def _strip(log):
    s = CombatLogStrip()
    s.sync(log)
    return s


def _ev(kind, **kw):
    return pygame.event.Event(kind, **kw)


class TestLayout:
    def test_newest_first(self):
        log = _log()
        s = _strip(log)
        assert s._layout[0][0] is log.entries[-1] and s._layout[-1][0] is log.entries[0]

    def test_content_height(self):
        s = _strip(_log(6, 3))
        assert s._content_h == 6 * SEP + 18 * STEP and s.max_offset == s._content_h - RECT.h

    def test_empty_log_draws_nothing(self):
        s = _strip(CombatLog())
        s.draw(pygame.Surface((300, 500)), FONTS)
        assert s.max_offset == 0 and s.visible() == []


class TestScrolling:
    def test_wheel_only_over_the_strip(self):
        s = _strip(_log())
        s.handle_event(_ev(pygame.MOUSEMOTION, pos=(500, 300), rel=(0, 0), buttons=(0, 0, 0)))
        assert not s.handle_event(_ev(pygame.MOUSEWHEEL, x=0, y=-1, flipped=False))
        s.handle_event(_ev(pygame.MOUSEMOTION, pos=RECT.center, rel=(0, 0), buttons=(0, 0, 0)))
        assert s.handle_event(_ev(pygame.MOUSEWHEEL, x=0, y=-1, flipped=False)) and s.target == STEP

    def test_clamped_both_ways(self):
        s = _strip(_log())
        s.scroll(-10 ** 9)
        assert s.target == 0
        s.scroll(10 ** 9)
        assert s.target == s.max_offset

    def test_drag_scrolls_without_tapping(self):
        s = _strip(_log())
        y = RECT.centery
        assert s.handle_event(_ev(pygame.MOUSEBUTTONDOWN, button=1, pos=(RECT.centerx, y)))
        s.handle_event(_ev(pygame.MOUSEMOTION, pos=(RECT.centerx, y - 80), rel=(0, -80), buttons=(1, 0, 0)))
        s.handle_event(_ev(pygame.MOUSEBUTTONUP, button=1, pos=(RECT.centerx, y - 80)))
        assert s.offset == 80 and s.pinned is None

    def test_tap_pins_and_untaps(self):
        s = _strip(_log())
        pos = s.tile_rect(s._layout[1][0]).center
        for _ in range(2):
            s.handle_event(_ev(pygame.MOUSEBUTTONDOWN, button=1, pos=pos))
            s.handle_event(_ev(pygame.MOUSEBUTTONUP, button=1, pos=pos))
            if s.pinned is not None:
                assert s.pinned is s._layout[1][0] and s.shown_entry() is s.pinned
        assert s.pinned is None

    def test_click_elsewhere_unpins(self):
        s = _strip(_log())
        s.pinned = s._layout[1][0]
        assert not s.handle_event(_ev(pygame.MOUSEBUTTONDOWN, button=1, pos=(600, 300)))
        assert s.pinned is None

    def test_arrows(self):
        s = _strip(_log())
        down = (RECT.centerx, RECT.bottom - 3)
        s.handle_event(_ev(pygame.MOUSEBUTTONDOWN, button=1, pos=down))
        s.handle_event(_ev(pygame.MOUSEBUTTONUP, button=1, pos=down))
        assert s.target == 2 * STEP

    def test_reading_old_entries_stays_put(self):
        log = _log()
        s = _strip(log)
        s.scroll(100)
        s.offset = s.target
        seen = s.entry_at((RECT.centerx, RECT.y + 60))
        log.enemy(9, "attack_1", "Nuevo", "x", 1)
        s.sync(log)
        assert s.entry_at((RECT.centerx, RECT.y + 60)) is seen

    def test_smooth_scroll_converges_and_clamps_dt(self):
        s = _strip(_log())
        s.scroll(200)
        for _ in range(60):
            s.update(10 ** 9)
        assert s.offset == s.target


class TestDrawing:
    def test_only_visible_tiles_are_rendered(self):
        log = CombatLog(1000)
        for i in range(1000):
            log.enemy(1, "attack_1", f"E{i}", "1 golpe", 1)
        s = _strip(log)
        surf = pygame.Surface((1280, 720))
        s.draw(surf, FONTS)
        assert len(s._tiles) <= RECT.h // STEP + 2

    def test_frame_cost_is_small(self):
        s = _strip(_log(40, 3))
        surf = pygame.Surface((1280, 720))
        s.draw(surf, FONTS)
        t = time.perf_counter()
        for _ in range(100):
            s.update(1 / 60)
            s.draw(surf, FONTS)
        assert (time.perf_counter() - t) / 100 < 0.004

    def test_tooltip(self):
        log = _log(1, 1)
        content = entry_tooltip(log.entries[-1])
        assert content.subtitle == "Turno 1  ·  Enemigo" and "Pierdes 3 de vida." in content.lines


class TestSceneWiring:
    def test_plays_and_enemy_turns_are_logged(self):
        state = create_sample_combat()
        scene = CombatScene(state, FONTS)
        surf = pygame.Surface((1280, 720))
        scene.draw(surf)
        assert scene.combat_log.entries[0].title == "Turno 1"
        playable = next(i for i, c in enumerate(state.hand.cards) if state.mana.can_afford(c.cost))
        scene._do_play_card(playable, 0)
        assert scene.combat_log.entries[-1].kind == "hero"
        scene._do_end_turn()
        kinds = [e.kind for e in scene.combat_log.entries]
        assert "enemy" in kinds and scene.combat_log.entries[-1].title == f"Turno {state.turn}"
        for _ in range(30):
            scene.update(1 / 60)
            scene.draw(surf)

    def test_hovering_a_tile_shows_its_detail(self):
        state = create_sample_combat()
        scene = CombatScene(state, FONTS)
        surf = pygame.Surface((1280, 720))
        scene.draw(surf)
        playable = next(i for i, c in enumerate(state.hand.cards) if state.mana.can_afford(c.cost))
        scene._do_play_card(playable, 0)
        scene.update(0.01)
        entry = scene.combat_log.entries[-1]
        pos = scene._log_strip.tile_rect(entry).center
        scene.handle_event(_ev(pygame.MOUSEMOTION, pos=pos, rel=(0, 0), buttons=(0, 0, 0)))
        assert scene._log_strip.shown_entry() is entry
        assert scene._draw_log_detail(surf)


class TestDetail:
    def _entry(self, **kw):
        log = CombatLog()
        targets = kw.pop("targets", (LogTarget("El Mago", HERO, hp=7), LogTarget("Gólem", "Gólem de Musgo", block=8)))
        log.enemy(2, "attack_2", "Espectro ataca", "2 golpes · pierdes 7 de vida", 7,
                  source="Espectro", targets=targets)
        return log.entries[0]

    def test_panel_lists_source_arrow_and_targets(self):
        asked = []
        panel = render_entry_detail(self._entry(), FONTS, lambda k: asked.append(k) or None)
        assert asked == ["Espectro", HERO, "Gólem de Musgo"] and panel.get_width() >= 300

    def test_panel_is_cached(self):
        e = self._entry()
        a = render_entry_detail(e, FONTS, lambda k: None)
        assert render_entry_detail(e, FONTS, lambda k: None) is a

    def test_many_targets_are_capped(self):
        targets = tuple(LogTarget(f"E{i}", f"E{i}", hp=1, died=i % 2 == 0, statuses=(("Fuego", 2),),
                                  reactions=("Vapor",)) for i in range(12))
        panel = render_entry_detail(self._entry(targets=targets), FONTS, lambda k: pygame.Surface((300, 200)))
        assert panel.get_width() < 640

    def test_blocked_hit_and_no_targets_render(self):
        render_entry_detail(self._entry(targets=(LogTarget("El Mago", HERO, blocked=True),)), FONTS, lambda k: None)
        render_entry_detail(self._entry(targets=()), FONTS, lambda k: None)

    def test_scene_detail_names_the_target(self):
        state = create_sample_combat()
        scene = CombatScene(state, FONTS)
        surf = pygame.Surface((1280, 720))
        scene.draw(surf)
        i = next(i for i, c in enumerate(state.hand.cards)
                 if state.mana.can_afford(c.cost) and c.total_damage() > 0)
        scene._do_play_card(i, 1)
        entry = scene.combat_log.entries[-1]
        assert entry.targets[0].name == state.enemies[1].name and entry.targets[0].aimed
        scene._do_end_turn()
        enemy_entries = [e for e in scene.combat_log.entries if e.kind == "enemy"]
        assert enemy_entries and all(e.source for e in enemy_entries)
        assert any(t.portrait == HERO for e in enemy_entries for t in e.targets)
        scene.update(0.01)
        pos = scene._log_strip.tile_rect(enemy_entries[-1]).center
        scene.handle_event(_ev(pygame.MOUSEMOTION, pos=pos, rel=(0, 0), buttons=(0, 0, 0)))
        assert scene._draw_log_detail(surf)
