"""La Guerrera in the UI: keywords Furia / Aguante on the card face, the ready effects,
tooltips, glossary icons, and Fuerza in the shown damage.
"""
from __future__ import annotations

import pygame
import pytest

from src.application.card_preview import combat_card_bonus
from src.domain import card_pool as cp
from src.domain.card import CardClass
from src.domain.keywords import Keyword
from src.infrastructure.fonts import FontRegistry
from src.infrastructure.ui_icons import has_ui_icon
from src.presentation.fx import card_fx
from src.presentation.ui import glossary as gl
from src.presentation.ui.card_widget import _ability_lines, draw_card, draw_card_at
from src.presentation.ui.tooltip import card_tooltip
from tests.application.test_warrior import _card, _state

FONTS = FontRegistry()


@pytest.fixture(autouse=True)
def _display():
    pygame.init()
    pygame.display.set_mode((1, 1))


class TestCardFace:
    def test_fury_line_when_off(self):
        card = _card("wr_tajo_brutal")
        assert "Furia: +5 de daño." in _ability_lines(card, 8)

    def test_fury_line_when_on(self):
        card = _card("wr_tajo_brutal")
        assert "¡Furia activa!" in _ability_lines(card, 13, fury=True)

    def test_endure_line(self):
        card = _card("wr_muro_acero")
        assert "Aguante: +1 de Fuerza." in _ability_lines(card, 0, 14)
        assert "¡Aguante activo!" in _ability_lines(card, 0, 14, endure=True)

    def test_every_warrior_card_draws(self):
        surf = pygame.Surface((400, 300))
        for f in cp.card_factories_for_classes({CardClass.WARRIOR}):
            draw_card(surf, f(), 10, 10, FONTS, fury=True, endure=True)
            draw_card_at(surf, f(), (200, 150), FONTS, scale=0.8, fury=True)


class TestReady:
    def test_ready_keywords(self):
        card = _card("wr_tajo_brutal")
        assert card_fx.ready_keywords(card, fury=True) == [Keyword.FURY]
        assert card_fx.ready_keywords(card, endure=True) == []      # no Aguante layer

    def test_styles_exist(self):
        assert card_fx.READY_STYLES[Keyword.FURY].label == "¡FURIA!"
        assert card_fx.READY_STYLES[Keyword.ENDURE].label == "¡AGUANTE!"


class TestTooltipAndGlossary:
    def test_tooltip_panel_active(self):
        content = card_tooltip(_card("wr_tajo_brutal"), fury_active=True)
        panel = next(p for p in content.panels if p.title == "Furia")
        assert panel.tag == "¡Activo!"
        assert any("13 de daño" in line for line in content.lines)

    def test_keyword_icons(self):
        assert gl.KEYWORD_TERMS[Keyword.FURY].icon == "fury" and has_ui_icon("fury")
        assert gl.KEYWORD_TERMS[Keyword.ENDURE].icon == "endure" and has_ui_icon("endure")


class TestShownDamage:
    def test_strength_in_combat_bonus(self):
        state = _state()
        state.gain_strength(3)
        assert combat_card_bonus(state).attack == 3


class TestFlagsReachTheFace:
    @pytest.mark.parametrize("draw", ["draw_card", "draw_card_at"])
    def test_fury_and_endure_reach_render(self, draw, monkeypatch):
        from src.presentation.ui import card_widget as cw
        seen = {}
        real = cw.render_card_surface

        def spy(card, fonts, **kw):
            seen.update(kw)
            return real(card, fonts, **kw)
        monkeypatch.setattr(cw, "render_card_surface", spy)
        surf = pygame.Surface((400, 300))
        card = _card("wr_tajo_brutal")
        if draw == "draw_card":
            cw.draw_card(surf, card, 10, 10, FONTS, fury=True, endure=True)
        else:
            cw.draw_card_at(surf, card, (200, 150), FONTS, fury=True, endure=True)
        assert seen["fury"] is True and seen["endure"] is True
