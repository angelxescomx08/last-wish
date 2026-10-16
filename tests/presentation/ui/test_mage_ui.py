"""Mage elements on screen: icons, glossary terms, colour-coded text, card faces,
tooltips, the "¡REACCIÓN!" ready effect and the reaction labels in combat.

Every element / reaction has its own picture (``assets/ui/icons``) used on the
enemy badge, the card art corner, the tooltips and the floating "¡VAPOR!".
"""
from __future__ import annotations

import pygame

from src.application.combat_manager import create_sample_combat
from src.domain.card import CardClass
from src.domain.card_pool import card_factories_for_classes
from src.domain.elements import Element, Reaction, apply_element
from src.domain.entities import FROZEN, StatusEffect
from src.domain.keywords import Keyword
from src.infrastructure.fonts import FontRegistry
from src.infrastructure.ui_icons import has_ui_icon, ui_icon
from src.presentation.fx import card_fx
from src.presentation.scenes.combat_scene import CombatScene
from src.presentation.ui import glossary as gl
from src.presentation.ui import rich_text
from src.presentation.ui.card_widget import _ability_lines, draw_card, draw_card_at
from src.presentation.ui.fx import FxLayer
from src.presentation.ui.tooltip import card_tooltip, draw_tooltip, enemy_tooltip, status_tooltip

pygame.init()


def _card(card_id: str):
    return next(f for f in card_factories_for_classes({CardClass.MAGE}) if f.card_id == card_id)()


def _mage_cards():
    return [f() for f in card_factories_for_classes({CardClass.MAGE}) if f.card_id.startswith("mg_")]


class TestIcons:
    def test_every_element_reaction_and_keyword_has_an_icon(self):
        names = ["fire", "water", "earth", "air", "frozen", "reaction",
                 *gl.REACTION_ICON.values()]
        assert all(has_ui_icon(n) for n in names)

    def test_icons_are_14px_shown_x2(self):
        assert ui_icon("steam").get_size() == (28, 28) and ui_icon("fire", 1).get_size() == (14, 14)

    def test_statuses_use_their_icons(self):
        assert [gl.status_icon(e.value) for e in Element] == ["fire", "water", "earth", "air"]
        assert gl.status_icon(FROZEN) == "frozen"

    def test_reactions_have_distinct_icons(self):
        assert len(set(gl.REACTION_ICON.values())) == len(Reaction)


class TestGlossary:
    def test_element_terms_found_with_their_number(self):
        found = gl.terms_in("Aplica 2 de Fuego. +1 de Agua a todos.")
        assert [t.name for t in found][:2] == ["Fuego", "Agua"]

    def test_names_that_contain_an_element_are_not_the_element(self):
        for text in ("Bola de Fuego", "Orbe de Fuego", "Lengua de Fuego", "Muro de Roca",
                     "Piel de Granito"):
            assert all(t.name not in {"Fuego", "Tierra"} for t in gl.terms_in(text)), text

    def test_element_panel_lists_its_three_reactions(self):
        term = gl.STATUS_TERMS["Fuego"]
        assert len(term.lines) == 3 and all(line.startswith("[[") for line in term.lines)
        assert {"Vapor", "Magma", "Incendio"} == {line.rsplit(": ", 1)[1] for line in term.lines}

    def test_reaction_keyword_and_rule_terms(self):
        names = [t.name for t in gl.terms_in("Reacción: roba 2. Cada reacción que provoques")]
        assert "Reacción" in names and "Reacción elemental" in names
        assert gl.KEYWORD_TERMS[Keyword.REACTION].icon == "reaction"

    def test_rule_term_lists_all_six_reactions(self):
        assert len(gl.ELEMENTS_RULE.lines) == 6

    def test_rich_text_colours_elements(self):
        colors = {c for t, c in rich_text.spans("Aplica 3 de Fuego y 2 de Agua.", (255, 255, 255))}
        assert gl.FIRE_INK in colors and gl.WATER_INK in colors


class TestCardFaces:
    def test_elements_are_on_the_chip_not_in_the_text(self):
        assert _ability_lines(_card("mg_bola_fuego"), damage=16) == ["Inflige 16 de daño."]
        assert not any("Tierra" in line for line in _ability_lines(_card("mg_terremoto")))

    def test_keyword_lines(self):
        assert _ability_lines(_card("mg_vapor_hirviente"), damage=4)[-1] == "Reacción: +1 de maná."
        assert _ability_lines(_card("mg_vapor_hirviente"), damage=4, reaction=True)[-1] == "¡Reacción!"
        assert _ability_lines(_card("mg_chispa_arcana"), damage=4)[-1] == "Vacío: +2 de Agua."

    def test_badges_follow_the_card(self):
        assert _card("mg_chispa_arcana").element_badges() == [Element.FIRE, Element.WATER]
        assert _card("mg_convergencia").element_badges() == list(Element)
        assert _card("mg_archimago").element_badges() == []

    def test_every_mage_card_draws_at_every_size(self):
        fonts = FontRegistry()
        surf = pygame.Surface((1280, 720))
        for c in _mage_cards():
            draw_card(surf, c, 10, 10, fonts, reaction=True, void=True)
            for scale in (0.6, 1.0, 1.3):
                draw_card_at(surf, c, (640, 360), fonts, scale=scale, angle=7, reaction=True)

    def test_every_mage_card_text_fits_the_face(self):
        """Same wrap as ``render_card_surface`` at the base size (damage shown with the Mago's +8)."""
        from src.infrastructure.card_assets import card_layout
        from src.presentation.ui.card_widget import CARD_H, CARD_W, _card_font, _rect, _zones
        fonts = FontRegistry()
        font = _card_font(fonts, max(8, round(CARD_H * 0.052)))
        for c in _mage_cards():
            box = _rect(_zones((c.rarity).name)["text"], CARD_W, CARD_H)
            dmg = c.total_damage() + 10 if c.total_damage() else 0
            for flags in ({}, {"void": True}, {"reaction": True}):
                rows = sum(len(rich_text.render_lines(line, font, box.w, (255, 255, 255)))
                           for line in _ability_lines(c, dmg, c.total_block() + 1 if c.total_block() else 0, **flags))
                assert rows <= box.h // font.get_linesize(), (c.name, flags, rows)


class TestReadyEffect:
    def test_reaction_style(self):
        style = card_fx.READY_STYLES[Keyword.REACTION]
        assert style.label == "¡REACCIÓN!" and style.icon == "reaction"

    def test_ready_only_with_a_reaction_layer(self):
        assert card_fx.ready_keywords(_card("mg_grieta"), reaction=True) == [Keyword.REACTION]
        assert card_fx.ready_keywords(_card("mg_piedra"), reaction=True) == []


class TestTooltips:
    def test_card_tooltip_says_what_it_applies_with_icon(self):
        content = card_tooltip(_card("mg_ola"))
        assert "[[water]]Aplica 1 de Agua a todos los enemigos." in content.lines
        assert any(p.title == "Agua" for p in content.panels)

    def test_reaction_panel_active(self):
        content = card_tooltip(_card("mg_grieta"), reaction_active=True)
        panel = next(p for p in content.panels if p.title == "Reacción")
        assert panel.tag == "¡Activo!" and "Efecto extra: +6 de escudo." in panel.lines

    def test_status_tooltip_lists_reactions(self):
        content = status_tooltip(StatusEffect("Agua", 3, False))
        assert content.title == "Agua 3" and any("Congelar" in line for line in content.lines)

    def test_intent_mentions_water_and_frozen(self):
        state = create_sample_combat()
        enemy = state.enemies[0]
        apply_element(state, enemy, Element.WATER, 2)
        lines = enemy_tooltip(enemy, 3, state.player).panels[0].lines
        assert any("−2 Agua" in line for line in lines)
        enemy.status_effects.append(StatusEffect(FROZEN, 1, False))
        lines = enemy_tooltip(enemy, 0, state.player).panels[0].lines
        assert any("Congelado: no actúa" in line for line in lines)

    def test_tooltips_render(self):
        fonts = FontRegistry()
        surf = pygame.Surface((1280, 720))
        for c in _mage_cards():
            draw_tooltip(surf, card_tooltip(c, reaction_active=True, void_active=True), (600, 300), fonts)


class TestCombat:
    def _scene(self):
        state = create_sample_combat()
        for e in state.enemies:
            e.status_effects = []
        state.hand.cards = [_card("mg_gota"), _card("mg_brisa")]
        state.mana.current = 4
        return state, CombatScene(state, FontRegistry())

    def test_floating_text_with_icon_draws(self):
        fx = FxLayer(FontRegistry().get(16))
        fx.add_text(100, 100, "¡VAPOR!", (255, 255, 255), icon=ui_icon("steam"))
        fx.update(0.1)
        fx.draw(pygame.Surface((300, 300)))

    def test_reaction_show_over_the_enemy(self):
        state, scene = self._scene()
        scene.draw(pygame.Surface((1280, 720)))
        apply_element(state, state.enemies[0], Element.FIRE, 3)
        scene._do_play_card(0, 0)                       # Gota: Agua → Vapor
        assert scene._reaction_show.count == 1

    def test_frozen_label_at_end_of_turn(self):
        state, scene = self._scene()
        scene.draw(pygame.Surface((1280, 720)))
        state.enemies[0].status_effects.append(StatusEffect(FROZEN, 1, False))
        scene._do_end_turn()
        assert any(getattr(e, "_text", "") == "¡Congelado!" for e in scene._fx._effects)

    def test_100_frames_with_elements(self):
        state, scene = self._scene()
        for i, e in enumerate(state.enemies):
            apply_element(state, e, list(Element)[i % 4], 3)
        surf = pygame.Surface((1280, 720))
        for _ in range(100):
            scene.update(1 / 60)
            scene.draw(surf)
