"""Hover = quick look, right click / long press = inspect (Slay the Spire / Hearthstone pattern).

* ``glossary.status_short`` and ``tooltip.enemy_quick_tooltip`` / ``player_quick_tooltip``:
  one short line per status, capped, element first, no glossary panels, inspect hint.
* ``tooltip`` renderer never draws off-screen (overflow → "+N más").
* ``ui/inspect_panel.InspectOverlay``: full content, scroll (wheel, drag, keys, arrows),
  clamping, closing, one tall pre-rendered surface.
* ``CombatScene``: hover shows the quick look beside the enemy; right click, long press
  and the I key open the inspect panel; a short tap does not.
"""
from __future__ import annotations

import pygame

from src.application.combat_manager import create_sample_combat
from src.domain.entities import StatusEffect
from src.infrastructure.fonts import FontRegistry
from src.presentation.scenes.combat_scene import LONG_PRESS, CombatScene
from src.presentation.ui import glossary as gl
from src.presentation.ui.inspect_panel import PANEL, InspectOverlay, render_content
from src.presentation.ui.tooltip import (QUICK_MAX_STATUSES, TooltipContent, TooltipPanel, draw_tooltip,
                                         enemy_quick_tooltip, enemy_tooltip, player_quick_tooltip)

pygame.init()
FONTS = FontRegistry()
_MANY = [("Veneno", 5, False), ("Débil", 2, False), ("Vulnerable", 2, False), ("Fuerza", 3, True),
         ("Marcado", 2, False), ("Congelado", 1, False), ("Fuego", 4, False), ("Frágil", 1, False)]


def _enemy(statuses=_MANY):
    state = create_sample_combat()
    e = state.enemies[1]
    e.status_effects = [StatusEffect(n, k, b) for n, k, b in statuses]
    return state, e


def _ev(kind, **kw):
    return pygame.event.Event(kind, **kw)


class TestShortLines:
    def test_every_known_status_has_a_short_line_with_its_stacks(self):
        for name in list(gl.STATUS_TERMS) + ["Ritual"]:
            line = gl.status_short(name, 7)
            assert line.startswith(f"{name} 7: ") and "{n}" not in line and len(line) <= 48

    def test_unknown_status_falls_back(self):
        assert gl.status_short("Raro", 1) == "Raro 1: perjuicio"

    def test_quick_tooltip_is_capped_and_has_no_panels(self):
        state, e = _enemy()
        tip = enemy_quick_tooltip(e, 5, state.player)
        status_lines = [l for l in tip.lines if l.startswith("[[") and ": " in l and "ataca" not in l]
        assert tip.panels == [] and len(status_lines) <= QUICK_MAX_STATUSES + 1
        assert any("y 3 más" in l for l in tip.lines) and "Clic derecho" in tip.lines[-1]

    def test_element_comes_first(self):
        state, e = _enemy()
        tip = enemy_quick_tooltip(e, 5, state.player)
        assert tip.lines[2].startswith("[[fire]]Fuego 4")

    def test_no_statuses(self):
        state, e = _enemy([])
        tip = enemy_quick_tooltip(e, 5, state.player)
        assert len(tip.lines) == 3

    def test_player_quick(self):
        state = create_sample_combat()
        state.player.status_effects = [StatusEffect(n, k, b) for n, k, b in _MANY]
        tip = player_quick_tooltip(state.player, 20)
        assert tip.panels == [] and any("Daño entrante" in l for l in tip.lines)

    def test_quick_is_much_shorter_than_full(self):
        state, e = _enemy()
        quick = enemy_quick_tooltip(e, 5, state.player)
        full = enemy_tooltip(e, 5, state.player)
        assert len(quick.all_text()) * 2 < len(full.all_text())


class TestRendererOverflow:
    def test_huge_tooltip_stays_on_screen(self):
        panels = [TooltipPanel(f"P{i}", ["Una regla bastante larga que ocupa varias líneas " * 3]) for i in range(40)]
        surf = pygame.Surface((1280, 720))
        rect = draw_tooltip(surf, TooltipContent("Mucho", ["x"], panels=panels), (600, 300), FONTS)
        assert rect.top >= 0 and rect.bottom <= 720 and rect.right <= 1280


class TestInspect:
    def _overlay(self):
        state, e = _enemy()
        return InspectOverlay(enemy_tooltip(e, 5, state.player), FONTS, pygame.Surface((40, 60)))

    def test_body_is_one_tall_surface_with_everything(self):
        o = self._overlay()
        assert o.body.get_height() > o.view.h and o.max_offset > 0

    def test_wheel_keys_and_clamp(self):
        o = self._overlay()
        o.handle_event(_ev(pygame.MOUSEWHEEL, x=0, y=-2, flipped=False))
        assert o.target == 96
        o.handle_event(_ev(pygame.KEYDOWN, key=pygame.K_PAGEDOWN))
        o.scroll(10 ** 9)
        assert o.target == o.max_offset
        o.scroll(-10 ** 9)
        assert o.target == 0

    def test_drag(self):
        o = self._overlay()
        y = o.view.centery
        o.handle_event(_ev(pygame.MOUSEBUTTONDOWN, button=1, pos=(o.view.centerx, y)))
        o.handle_event(_ev(pygame.MOUSEMOTION, pos=(o.view.centerx, y - 100), rel=(0, -100), buttons=(1, 0, 0)))
        o.handle_event(_ev(pygame.MOUSEBUTTONUP, button=1, pos=(o.view.centerx, y - 100)))
        assert o.offset == 100 and not o.dismissed

    def test_closing(self):
        for event in (_ev(pygame.KEYDOWN, key=pygame.K_ESCAPE), _ev(pygame.MOUSEBUTTONDOWN, button=3, pos=(5, 5)),
                      _ev(pygame.MOUSEBUTTONDOWN, button=1, pos=(5, 5))):
            o = self._overlay()
            o.handle_event(event)
            assert o.dismissed
        o = self._overlay()
        o.handle_event(_ev(pygame.MOUSEBUTTONDOWN, button=1, pos=o.close_rect.center))
        assert o.dismissed

    def test_draws_and_smooth_scroll(self):
        o = self._overlay()
        surf = pygame.Surface((1280, 720))
        o.scroll(300)
        for _ in range(60):
            o.update(10 ** 9)
            o.draw(surf)
        assert o.offset == o.target

    def test_short_content_has_no_scroll(self):
        o = InspectOverlay(TooltipContent("Poco", ["una línea"]), FONTS)
        assert o.max_offset == 0
        o.draw(pygame.Surface((1280, 720)))

    def test_render_content_handles_icons_and_notes(self):
        surf = render_content(TooltipContent("t", ["[[poison]]Veneno", "  nota", "texto"],
                                             panels=[TooltipPanel("P", ["[[fire]]a"], "fire", (255, 0, 0), "tag")]),
                              FONTS, 500)
        assert surf.get_width() == 500 and surf.get_height() > 60


class TestScene:
    def _scene(self):
        state, e = _enemy()
        scene = CombatScene(state, FONTS)
        scene.draw(pygame.Surface((1280, 720)))
        return state, scene

    def test_hover_shows_the_quick_look(self):
        state, scene = self._scene()
        r = scene._enemy_rects[1]
        scene.handle_event(_ev(pygame.MOUSEMOTION, pos=(r.centerx, r.centery - 30), rel=(0, 0), buttons=(0, 0, 0)))
        tip = scene._get_tooltip()
        assert tip.panels == [] and tip.title == state.enemies[1].name

    def test_right_click_opens_inspect(self):
        state, scene = self._scene()
        r = scene._enemy_rects[1]
        scene.handle_event(_ev(pygame.MOUSEBUTTONDOWN, button=3, pos=(r.centerx, r.centery - 30)))
        assert isinstance(scene._overlay, InspectOverlay)
        scene.handle_event(_ev(pygame.KEYDOWN, key=pygame.K_ESCAPE))
        scene.update(0.01)
        assert scene._overlay is None

    def test_long_press_opens_inspect_short_tap_does_not(self):
        state, scene = self._scene()
        r = scene._enemy_rects[1]
        pos = (r.centerx, r.centery - 30)
        scene.handle_event(_ev(pygame.MOUSEBUTTONDOWN, button=1, pos=pos))
        scene.update(LONG_PRESS * 0.4)
        scene.handle_event(_ev(pygame.MOUSEBUTTONUP, button=1, pos=pos))
        scene.update(LONG_PRESS)
        assert scene._overlay is None
        scene.handle_event(_ev(pygame.MOUSEBUTTONDOWN, button=1, pos=pos))
        for _ in range(int(LONG_PRESS / 0.05) + 2):
            scene.update(0.05)
        assert isinstance(scene._overlay, InspectOverlay)

    def test_moving_cancels_the_long_press(self):
        state, scene = self._scene()
        r = scene._enemy_rects[1]
        scene.handle_event(_ev(pygame.MOUSEBUTTONDOWN, button=1, pos=r.center))
        scene.handle_event(_ev(pygame.MOUSEMOTION, pos=(r.centerx + 40, r.centery), rel=(40, 0), buttons=(1, 0, 0)))
        scene.update(LONG_PRESS * 2)
        assert scene._overlay is None

    def test_hero_inspect_and_i_key(self):
        state, scene = self._scene()
        pr = scene._player_rect
        scene.handle_event(_ev(pygame.MOUSEBUTTONDOWN, button=3, pos=pr.center))
        assert scene._overlay.content.subtitle == "Tu héroe"
        scene._overlay = None
        r = scene._enemy_rects[0]
        scene.handle_event(_ev(pygame.MOUSEMOTION, pos=r.center, rel=(0, 0), buttons=(0, 0, 0)))
        scene.handle_event(_ev(pygame.KEYDOWN, key=pygame.K_i))
        assert isinstance(scene._overlay, InspectOverlay)

    def test_right_click_with_a_card_held_still_cancels(self):
        state, scene = self._scene()
        scene._handle_key(pygame.K_1)
        r = scene._enemy_rects[1]
        scene.handle_event(_ev(pygame.MOUSEBUTTONDOWN, button=3, pos=r.center))
        assert scene._overlay is None and not scene._play.active
