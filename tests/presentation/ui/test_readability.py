"""Readability UI: icons, colour-coded text, keyword glossary, intents, badges and banners.

Covers the icon strip (every name the code asks for exists), rich text colours
(damage red, block blue, keywords gold, poison green), glossary detection, the
multi-panel tooltips (intent sentences with totals / modifiers / block / lethal,
one panel per status and keyword with no repeats, two columns when too tall),
the intent widget (number, extras, lethal, hitboxes), status badges, the HP
preview of incoming damage, enemy action banners, and the combat scene's hover
of intents and status badges.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pygame
import pytest

from src.application.combat_factory import create_combat_from_run
from src.application import enemy_ai
from src.application.run_manager import create_run
from src.domain.character import ALL_CHARACTERS
from src.domain.combat import EnemyAction
from src.domain.entities import (
    BLADES, ENTANGLED, FRAIL, MARKED, POISON, STRENGTH, VULNERABLE, WEAK, Enemy, Intent, IntentType,
    Player, StatusEffect,
)
from src.domain.status_cards import MOLD_ID, SPORE_ID, mold, spore
from src.infrastructure.fonts import FontRegistry
from src.infrastructure.ui_icons import UI_DIR, has_ui_icon, ui_icon
from src.presentation.scenes.combat_scene import CombatScene
from src.presentation.ui import glossary as gl
from src.presentation.ui import rich_text
from src.presentation.ui.action_banner import FADE_IN, FADE_OUT, HOLD, ActionBanners, describe_action
from src.presentation.ui.entity_widget import (
    draw_enemy, draw_intent, draw_player, intent_extras, intent_number, status_rects,
)
from src.presentation.ui.tooltip import (
    TooltipContent, TooltipPanel, attack_icon, card_tooltip, draw_tooltip, enemy_tooltip,
    intent_icon, intent_lines, intent_tooltip, player_tooltip, status_tooltip, tooltip_size,
)

FONTS = FontRegistry()


def _enemy(intent: Intent, statuses=(), name="Cultista", block=0) -> Enemy:
    return Enemy("e", name, 40, 40, block=block, intent=intent, status_effects=list(statuses))


def _player(hp=50, block=0, statuses=()) -> Player:
    return Player("Viajera", 50, hp, block=block, status_effects=list(statuses))


# ---------------------------------------------------------------- icons

class TestIcons:
    NAMES = ["attack_1", "attack_2", "attack_3", "attack_4", "defend", "buff", "debuff", "cards",
             "unknown", "lethal", "block", "junk_card", "status_buff", "status_debuff", "combo",
             "singular", "void", "spoil", "exhaust", "ethereal", "unplayable", "damage", "draw",
             "mana", "heal"]

    @pytest.mark.parametrize("name", NAMES)
    def test_icon_exists(self, name):
        assert has_ui_icon(name) and ui_icon(name, 2) is not None

    @pytest.mark.parametrize("status", [POISON, VULNERABLE, WEAK, FRAIL, ENTANGLED, STRENGTH, BLADES, MARKED, "Ritual"])
    def test_every_status_has_its_own_icon(self, status):
        icon = gl.status_icon(status)
        assert icon not in ("status_buff", "status_debuff") and has_ui_icon(icon)

    def test_unknown_status_falls_back(self):
        assert gl.status_icon("Raro", True) == "status_buff"
        assert gl.status_icon("Raro", False) == "status_debuff"

    def test_scale(self):
        assert ui_icon("poison", 2).get_size() == (28, 28)
        assert ui_icon("attack_1", 2).get_size() == (36, 36)

    def test_missing_name(self):
        assert ui_icon("nope") is None and not has_ui_icon("nope")

    def test_glossary_icons_exist(self):
        for term in gl.ALL_TERMS + (gl.SHIELD,):
            assert has_ui_icon(term.icon), term.name

    def test_generator_matches_assets(self):
        sys.path.insert(0, str(Path(__file__).parents[3] / "scripts"))
        import generate_ui_icons as gen
        rows, meta = gen.build()
        on_disk = json.loads((UI_DIR / "icons.json").read_text(encoding="utf-8"))
        assert meta == on_disk
        assert len(rows[0]) == sum(w for _, _, w, _ in meta["icons"].values())

    def test_icons_have_outline_and_content(self):
        for name in self.NAMES:
            surf = ui_icon(name, 1)
            opaque = sum(1 for x in range(surf.get_width()) for y in range(surf.get_height())
                         if surf.get_at((x, y)).a > 0)
            assert opaque > surf.get_width() * surf.get_height() * 0.15, name


# ---------------------------------------------------------------- rich text

def _color_of(text: str, word: str, base=(1, 2, 3)):
    for piece, col in rich_text.spans(text, base):
        if word in piece:
            return col
    raise AssertionError(word)


class TestRichText:
    def test_damage_red(self):
        assert _color_of("Inflige 12 de daño.", "12 de daño") == gl.DAMAGE

    def test_block_blue(self):
        assert _color_of("Gana 8 de escudo.", "8 de escudo") == gl.BLOCK

    def test_keyword_gold(self):
        assert _color_of("Agotar. Algo", "Agotar") == gl.KEYWORD

    def test_poison_green(self):
        assert _color_of("aplica 3 de Veneno", "3 de Veneno") == gl.POISON_INK

    def test_mana(self):
        assert _color_of("pierdes 1 de maná", "1 de maná") == gl.MANA

    def test_hp_loss_red(self):
        assert _color_of("pierdes 6 de vida", "6 de vida") == gl.DAMAGE

    def test_plain_text_keeps_base(self):
        assert rich_text.spans("Hola mundo", (9, 9, 9)) == [("Hola mundo", (9, 9, 9))]

    def test_spans_rebuild_text(self):
        text = "Combo: inflige 4 de daño y gana 3 de escudo; aplica Débil."
        assert "".join(p for p, _ in rich_text.spans(text, (0, 0, 0))) == text

    def test_big_numbers(self):
        assert _color_of("Inflige 1.2K de daño", "1.2K de daño") == gl.DAMAGE

    def test_word_inside_word_not_highlighted(self):
        assert _color_of("Combos", "Combos") != gl.KEYWORD

    def test_wrap_respects_width(self):
        lines = rich_text.render_lines("Inflige 12 de daño a un enemigo y luego " * 4, FONTS.get(12), 150)
        assert len(lines) > 2 and all(s.get_width() <= 150 for s in lines)

    def test_single_line(self):
        assert rich_text.render_line("Gana 5 de escudo", FONTS.get(12)).get_height() > 0


# ---------------------------------------------------------------- glossary

class TestGlossary:
    def test_finds_terms_in_order(self):
        names = [t.name for t in gl.terms_in("Agotar. Aplica 2 de Veneno y Débil.")]
        assert names == ["Agotar", "Veneno", "Débil"]

    def test_no_duplicates(self):
        assert len(gl.terms_in(["Veneno", "Veneno otra vez"])) == 1

    def test_exclude(self):
        assert gl.terms_in("Veneno", exclude={"Veneno"}) == []

    def test_shield_only_on_request(self):
        assert gl.terms_in("gana escudo") == []
        assert gl.terms_in("gana escudo", include_shield=True)[0] is gl.SHIELD

    def test_keyword_rule_drops_prefix(self):
        assert not gl.KEYWORD_TERMS[next(iter(gl.KEYWORD_TERMS))].rule.lower().startswith("combo:")

    def test_unknown_status_term(self):
        assert gl.status_term("Raro", True).rule


# ---------------------------------------------------------------- intents in words

class TestIntentText:
    def test_attack_icon_grows(self):
        assert [attack_icon(d) for d in (5, 10, 20, 40)] == ["attack_1", "attack_2", "attack_3", "attack_4"]

    def test_multi_hit_total(self):
        text = "\n".join(intent_lines(_enemy(Intent(IntentType.ATTACK, 4, hits=3)), 4))
        assert "3 veces" in text and "12 de daño en total" in text

    def test_single_hit(self):
        assert "por 7 de daño" in intent_lines(_enemy(Intent(IntentType.ATTACK, 7)), 7)[0]

    def test_modifiers_explained(self):
        e = _enemy(Intent(IntentType.ATTACK, 6), [StatusEffect(STRENGTH, 2, True), StatusEffect(WEAK, 1, False)])
        p = _player(statuses=[StatusEffect(VULNERABLE, 1, False)])
        text = "\n".join(intent_lines(e, 9, p))
        assert "Base 6" in text and "+2 Fuerza" in text and "Débil" in text and "Vulnerable" in text

    def test_no_modifier_line_when_plain(self):
        assert not any("Base" in l for l in intent_lines(_enemy(Intent(IntentType.ATTACK, 6)), 6, _player()))

    def test_block_absorbs(self):
        text = "\n".join(intent_lines(_enemy(Intent(IntentType.ATTACK, 5, hits=2)), 5, _player(block=4)))
        assert "para 4" in text and "perderías 6" in text

    def test_lethal_warning(self):
        text = "\n".join(intent_lines(_enemy(Intent(IntentType.ATTACK, 30)), 30, _player(hp=20)))
        assert "matará" in text

    def test_no_lethal_when_blocked(self):
        text = "\n".join(intent_lines(_enemy(Intent(IntentType.ATTACK, 30)), 30, _player(hp=20, block=30)))
        assert "matará" not in text

    def test_extras(self):
        it = Intent(IntentType.ATTACK, 5, block=6, buffs=((STRENGTH, 2),), debuffs=((FRAIL, 1),),
                    cards=((SPORE_ID, 2, "draw"),))
        text = "\n".join(intent_lines(_enemy(it), 5))
        assert "6 de escudo" in text and "2 de Fuerza" in text and "1 de Frágil" in text
        assert "2 Esporas" in text and "pila de robo" in text

    def test_generic_intents(self):
        for kind, word in ((IntentType.BLOCK, "escudo"), (IntentType.BUFF, "fortalecerse"),
                           (IntentType.DEBUFF, "debilitarte"), (IntentType.UNKNOWN, "No se sabe")):
            assert word in "\n".join(intent_lines(_enemy(Intent(kind, 5))))

    def test_lines_carry_icons(self):
        assert intent_lines(_enemy(Intent(IntentType.ATTACK, 5)), 5)[0].startswith("[[attack_1]]")

    def test_intent_icon(self):
        assert intent_icon(Intent(IntentType.ATTACK, 5, hits=4)) == "attack_3"
        assert intent_icon(Intent(IntentType.BLOCK, 5)) == "defend"
        assert intent_icon(Intent(IntentType.UNKNOWN)) == "unknown"


# ---------------------------------------------------------------- tooltips

class TestTooltips:
    def test_intent_tooltip_has_move_and_card_panel(self):
        it = Intent(IntentType.ATTACK, 6, move="Lluvia de Esporas", cards=((SPORE_ID, 2, "draw"),),
                    description="Ataca y baraja Esporas.")
        tip = intent_tooltip(_enemy(it), 6, _player())
        assert tip.title == "Lluvia de Esporas"
        assert any(p.title == "Espora" for p in tip.panels)
        assert any(p.title == "Agotar" for p in tip.panels)        # the Espora text mentions it

    def test_enemy_tooltip_status_panels_not_repeated(self):
        e = _enemy(Intent(IntentType.ATTACK, 4, move="Danza de Espadas"),
                   [StatusEffect(BLADES, 2, True), StatusEffect(WEAK, 1, False)])
        tip = enemy_tooltip(e, 3, _player(statuses=[StatusEffect(VULNERABLE, 1, False)]))
        keys = [p.key or p.title for p in tip.panels]
        assert len(keys) == len(set(keys))
        assert "Espadas" in keys and "Débil" in keys

    def test_boss_tag(self):
        e = _enemy(Intent(IntentType.ATTACK, 4))
        e.is_boss = True
        assert enemy_tooltip(e).tag == "JEFE"

    def test_status_tooltip(self):
        tip = status_tooltip(StatusEffect(POISON, 3, False))
        assert tip.title == "Veneno 3" and "Pierde" in tip.all_text() and tip.icon == "poison"

    def test_timed_debuff_duration_on_player(self):
        tip = status_tooltip(StatusEffect(VULNERABLE, 2, False), on_player=True)
        assert "Dura 2 turnos" in tip.all_text()

    def test_player_incoming(self):
        text = player_tooltip(_player(hp=10), incoming=12).all_text()
        assert "Daño entrante" in text and "Letal" in text

    def test_player_no_incoming_line(self):
        assert "entrante" not in player_tooltip(_player()).all_text()

    def test_card_keyword_panels(self):
        tip = card_tooltip(spore())
        titles = [p.title for p in tip.panels]
        assert "Agotar" in titles and "Veneno" in titles and titles.count("Agotar") == 1

    def test_unplayable_card(self):
        tip = card_tooltip(mold())
        assert "Injugable" in tip.subtitle and any(p.title == "Injugable" for p in tip.panels)
        assert any(p.title == "Etérea" for p in tip.panels)

    def test_combo_panel_active_tag(self):
        from src.domain.card_pool import PackTheme, card_factories_for_theme
        tajo = next(f for f in card_factories_for_theme(PackTheme.ACERO) if f.card_id == "a_tajo")()
        panel = next(p for p in card_tooltip(tajo, combo_active=True).panels if p.title == "Combo")
        assert panel.tag == "¡Activo!"

    def test_all_text_strips_icon_markup(self):
        tip = TooltipContent("T", ["[[poison]]Hola"], panels=[TooltipPanel("P", ["[[block]]x"])])
        assert "[[" not in tip.all_text()


class TestRenderer:
    def _tall(self) -> TooltipContent:
        return TooltipContent("Muchos", ["línea"] * 4,
                              panels=[TooltipPanel(f"P{i}", ["texto largo de regla " * 4]) for i in range(12)])

    def test_draws_inside_screen(self):
        surf = pygame.Surface((1280, 720))
        rect = draw_tooltip(surf, self._tall(), (1270, 700), FONTS)
        assert surf.get_rect().contains(rect)

    def test_two_columns_when_tall(self):
        surf = pygame.Surface((1280, 720))
        w, h = tooltip_size(self._tall(), FONTS)
        rect = draw_tooltip(surf, self._tall(), (100, 100), FONTS)
        assert h > 712 and rect.width > w

    def test_beside_rect(self):
        surf = pygame.Surface((1280, 720))
        card = pygame.Rect(200, 500, 150, 210)
        rect = draw_tooltip(surf, card_tooltip(spore()), (0, 0), FONTS, beside=card)
        assert rect.left >= card.right and rect.bottom <= 716

    def test_beside_flips_left(self):
        surf = pygame.Surface((1280, 720))
        card = pygame.Rect(1100, 500, 150, 210)
        rect = draw_tooltip(surf, card_tooltip(spore()), (0, 0), FONTS, beside=card)
        assert rect.right <= card.left

    def test_icon_lines_render(self):
        surf = pygame.Surface((1280, 720))
        draw_tooltip(surf, intent_tooltip(_enemy(Intent(IntentType.ATTACK, 30)), 30, _player(hp=5)), (640, 300), FONTS)


# ---------------------------------------------------------------- widgets

class TestWidgets:
    def test_intent_number(self):
        assert intent_number(Intent(IntentType.ATTACK, 4, hits=3), 5) == "5×3"
        assert intent_number(Intent(IntentType.ATTACK, 4)) == "4"
        assert intent_number(Intent(IntentType.BLOCK, 9)) == "9"
        assert intent_number(Intent(IntentType.BUFF)) == ""

    def test_intent_extras(self):
        it = Intent(IntentType.ATTACK, 4, block=3, buffs=((STRENGTH, 1),), debuffs=((WEAK, 1),),
                    cards=((MOLD_ID, 1, "discard"),))
        assert intent_extras(it) == ["block", "status_buff", "status_debuff", "junk_card"]
        assert intent_extras(Intent(IntentType.DEBUFF, debuffs=((WEAK, 1),))) == []

    def test_draw_intent_rect_and_lethal(self):
        surf = pygame.Surface((400, 200), pygame.SRCALPHA)
        plain = draw_intent(surf, Intent(IntentType.ATTACK, 4, hits=2), 200, 100, FONTS, 4)
        assert plain.bottom == 100 and plain.width > 36
        draw_intent(surf, Intent(IntentType.ATTACK, 40), 200, 100, FONTS, 40, lethal=True, t=0.3)

    def test_enemy_hitboxes(self):
        surf = pygame.Surface((600, 500))
        boxes: dict = {}
        e = _enemy(Intent(IntentType.ATTACK, 5), [StatusEffect(WEAK, 1, False), StatusEffect(POISON, 2, False)],
                   block=4)
        rect = draw_enemy(surf, e, 200, 150, FONTS, hitboxes=boxes)
        assert boxes["intent"].bottom < rect.top
        assert [fx.name for fx, _ in boxes["statuses"]] == [WEAK, POISON]
        assert all(r.top > rect.bottom for _, r in boxes["statuses"])

    def test_player_preview(self):
        surf = pygame.Surface((600, 500))
        boxes: dict = {}
        draw_player(surf, _player(statuses=[StatusEffect(VULNERABLE, 1, False)]), 50, 50, FONTS,
                    incoming_loss=12, t=1.0, hitboxes=boxes)
        assert len(boxes["statuses"]) == 1

    def test_status_rects_wrap(self):
        effects = [StatusEffect(str(i), 1, False) for i in range(6)]
        rects = status_rects(effects, 0, 0, max_w=95)
        assert rects[3].top > rects[0].top and rects[3].left == 0


# ---------------------------------------------------------------- banners

class TestBanners:
    def test_describe_attack(self):
        icon, title, detail = describe_action("Caballero", Intent(IntentType.ATTACK, 4, hits=2, move="Danza"),
                                              EnemyAction(0, move="Danza", hits=[3, 0]))
        assert icon.startswith("attack") and title == "Caballero usa Danza"
        assert "2 golpes" in detail and "pierdes 3 de vida" in detail

    def test_describe_fully_blocked(self):
        _, _, detail = describe_action("X", Intent(IntentType.ATTACK, 4), EnemyAction(0, hits=[0]))
        assert "todo bloqueado" in detail

    def test_describe_generic_block(self):
        icon, title, detail = describe_action("Babosa", Intent(IntentType.BLOCK, 7), EnemyAction(0))
        assert (icon, title, detail) == ("defend", "Babosa se defiende", "gana 7 de escudo")

    def test_describe_cards_and_debuffs(self):
        _, _, detail = describe_action("Reina", Intent(IntentType.DEBUFF, move="Moho"),
                                       EnemyAction(0, cards=[(MOLD_ID, 2, "discard")], debuffs=[(WEAK, 1)]))
        assert "te aplica 1 de Débil" in detail and "2 Mohos en tu descarte" in detail

    def test_lifecycle(self):
        b = ActionBanners()
        b.add("defend", "A", "x", delay=0.5)
        surf = pygame.Surface((1280, 720))
        b.update(0.2)
        assert b.active[0].alpha == 0
        b.update(0.5)
        b.draw(surf, FONTS)
        assert b.active[0].alpha > 0
        b.update(FADE_IN + HOLD + FADE_OUT)
        assert b.active == []


# ---------------------------------------------------------------- combat scene

def _knight_scene():
    run = create_run(ALL_CHARACTERS[0], 3)
    state = create_combat_from_run(run, [enemy_ai.create_boss(enemy_ai.HOLLOW_KNIGHT)])
    state.player.status_effects.append(StatusEffect(VULNERABLE, 2, False))
    scene = CombatScene(state, FONTS)
    surf = pygame.Surface((1280, 720))
    scene.update(1 / 60)
    scene.draw(surf)
    return scene, surf


def _hover(scene, surf, pos):
    scene.handle_event(pygame.event.Event(pygame.MOUSEMOTION, pos=pos, rel=(0, 0), buttons=(0, 0, 0)))
    scene.update(1 / 60)
    scene.draw(surf)
    return scene._get_tooltip()


class TestCombatScene:
    def test_hover_intent(self):
        scene, surf = _knight_scene()
        tip = _hover(scene, surf, scene._enemy_hitboxes[0]["intent"].center)
        assert tip is not None and "Intención de" in tip.subtitle

    def test_hover_player_status(self):
        scene, surf = _knight_scene()
        badge = scene._player_hitboxes["statuses"][0][1]
        tip = _hover(scene, surf, badge.center)
        assert tip.title == "Vulnerable 2"

    def test_hover_enemy_status(self):
        scene, surf = _knight_scene()
        scene.state.enemies[0].status_effects.append(StatusEffect(WEAK, 1, False))
        scene.draw(surf)
        badges = scene._enemy_hitboxes[0]["statuses"]
        tip = _hover(scene, surf, badges[-1][1].center)
        assert tip.title == "Débil 1"

    def test_incoming_damage(self):
        scene, _ = _knight_scene()
        enemy = scene.state.enemies[0]
        expected = enemy_ai.intent_hit_damage(enemy, scene.state.player) * max(1, enemy.intent.hits) \
            if enemy.intent.intent_type == IntentType.ATTACK else 0
        assert scene._incoming_damage() == expected

    def test_end_turn_shows_banner(self):
        scene, surf = _knight_scene()
        scene._do_end_turn()
        assert scene._banners.active and "Caballero" in scene._banners.active[0].title
        for _ in range(30):
            scene.update(1 / 30)
        scene.draw(surf)
