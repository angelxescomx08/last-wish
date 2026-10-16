"""Reading the Mage's elements: aiming preview, card art, enemy badge, reaction show, wheel.

* ``application.play_preview`` — simulates a play on a copy (state and global RNG untouched).
* ``ui.element_preview`` — bubble rows (full / compact), hints, floor glow.
* ``fx.reaction_fx`` — clash → impact (burst + shake) → result, then gone.
* ``ui.element_wheel`` — the cheat sheet (R / button), closing, layout.
* card faces (element backdrop + chip), enemy element badge, combat wiring.
"""
from __future__ import annotations

import random

import pygame

from src.application.combat_manager import create_sample_combat
from src.application.play_preview import preview_play, reacting_enemies
from src.domain.card import CardClass
from src.domain.card_pool import card_factories_for_classes
from src.domain.elements import REACTIONS, Element, Reaction, apply_element, element_stacks
from src.domain.entities import StatusEffect
from src.infrastructure.card_assets import has_card_art
from src.infrastructure.fonts import FontRegistry
from src.presentation.fx.bursts import BurstParticles
from src.presentation.fx.reaction_fx import CLASH, LIFE, ReactionShow
from src.presentation.scenes.combat_scene import CombatScene
from src.presentation.ui.card_widget import CARD_H, CARD_W, _element_chip, render_card_surface
from src.presentation.ui.element_preview import (draw_element_floor, draw_preview_bubble, draw_react_hint,
                                                 preview_rows)
from src.presentation.ui.element_wheel import CORNERS, PANEL, ElementWheelOverlay, reaction_spot
from src.presentation.ui.entity_widget import draw_enemy

pygame.init()
FONTS = FontRegistry()


def _card(card_id: str):
    return next(f for f in card_factories_for_classes({CardClass.MAGE}) if f.card_id == card_id)()


def _state(hand_ids=("mg_gota",)):
    state = create_sample_combat()
    for e in state.enemies:
        e.status_effects = []
    state.hand.cards = [_card(c) for c in hand_ids]
    state.mana.current = 4
    return state


def _key(key):
    return pygame.event.Event(pygame.KEYDOWN, key=key)


# ---------------------------------------------------------------- simulation

class TestPreviewPlay:
    def test_predicts_steam_without_touching_the_state(self):
        s = _state()
        apply_element(s, s.enemies[0], Element.FIRE, 3)
        hp, hand, mana = s.enemies[0].current_hp, s.hand.count, s.mana.current
        p = preview_play(s, 0, 0)
        ep = p.enemies[0]
        assert [ev.reaction for ev in ep.reactions] == [Reaction.STEAM]
        assert ep.before == (Element.FIRE, 3) and ep.after is None and ep.hp_loss > 10
        assert (s.enemies[0].current_hp, s.hand.count, s.mana.current) == (hp, hand, mana)
        assert element_stacks(s.enemies[0], Element.FIRE) == 3 and s.reaction_log == []

    def test_global_random_is_restored(self):
        s = _state(("mg_brisa",))
        random.seed(5)
        expected = random.random()
        random.seed(5)
        preview_play(s, 0, None)
        assert random.random() == expected

    def test_unplayable_returns_none(self):
        s = _state(("mg_convergencia",))
        s.mana.current = 0
        assert preview_play(s, 0, 0) is None
        assert preview_play(s, 5, 0) is None

    def test_reaction_keyword_flag(self):
        s = _state(("mg_vapor_hirviente",))
        apply_element(s, s.enemies[0], Element.FIRE, 1)
        assert preview_play(s, 0, 0).reaction_keyword
        assert not preview_play(s, 0, 1).reaction_keyword

    def test_reacting_enemies(self):
        s = _state(("mg_piedra",))
        apply_element(s, s.enemies[1], Element.WATER, 2)
        assert reacting_enemies(s, s.hand.cards[0]) == {1: Reaction.MUD}
        assert reacting_enemies(s, _card("mg_archimago")) == {}

    def test_200_random_previews_never_change_the_state(self):
        rng = random.Random(3)
        ids = [f.card_id for f in card_factories_for_classes({CardClass.MAGE}) if f.card_id.startswith("mg_")]
        for _ in range(200):
            s = _state((rng.choice(ids),))
            for e in s.enemies:
                if rng.random() < 0.7:
                    apply_element(s, e, rng.choice(list(Element)), rng.randint(1, 10 ** 6))
            snap = [(e.current_hp, e.block, [(x.name, x.stacks) for x in e.status_effects]) for e in s.enemies]
            preview_play(s, 0, rng.randrange(len(s.enemies)))
            assert snap == [(e.current_hp, e.block, [(x.name, x.stacks) for x in e.status_effects])
                            for e in s.enemies]


class TestBubble:
    def _ep(self):
        s = _state()
        apply_element(s, s.enemies[0], Element.FIRE, 3)
        return preview_play(s, 0, 0).enemies[0]

    def test_full_rows_show_the_formula(self):
        rows = preview_rows(self._ep(), "+1 de maná")
        assert rows[0][:2] == ["@fire", ("3", rows[0][1][1])] and "@water" in rows[0]
        assert rows[0][-1][0] == "¡VAPOR!" and rows[1][0][0] == "10 de daño"
        assert rows[2][1][0] == "Reacción: +1 de maná" and rows[-1][0][0].startswith("−")

    def test_compact_rows(self):
        rows = preview_rows(self._ep(), compact=True)
        assert rows[0] == ["@steam", ("¡VAPOR!", rows[0][1][1])] and len(rows) == 2

    def test_new_element_and_stacking_rows(self):
        s = _state(("mg_gota",))
        assert preview_rows(preview_play(s, 0, 0).enemies[0])[0][1][0] == "+2 de Agua"
        apply_element(s, s.enemies[0], Element.WATER, 3)
        assert preview_rows(preview_play(s, 0, 0).enemies[0])[0][1][0] == "Agua 3 → 5"

    def test_nothing_changes_nothing_shown(self):
        s = _state(("mg_gota",))
        assert preview_rows(preview_play(s, 0, 0).enemies[1]) == []

    def test_bubble_stays_on_screen_and_above_the_hand(self):
        surf = pygame.Surface((1280, 720))
        rows = preview_rows(self._ep(), "+1 de maná")
        for x in (0, 640, 1280):
            rect = draw_preview_bubble(surf, (x, 440), rows, FONTS, (255, 0, 0), bottom_limit=461)
            assert rect.left >= 0 and rect.right <= 1280 and rect.bottom <= 461
        assert draw_preview_bubble(surf, (10, 10), [], FONTS, (1, 2, 3)) is None

    def test_hint_and_floor_draw(self):
        surf = pygame.Surface((400, 300))
        for r in Reaction:
            draw_react_hint(surf, pygame.Rect(100, 100, 34, 34), r, 1.3)
        for t in (0.0, 0.5, 10 ** 6):
            draw_element_floor(surf, (200, 200), (255, 120, 40), t, 150, strong=True)


# ---------------------------------------------------------------- reaction show

class TestReactionShow:
    def test_phases_burst_shake_and_end(self):
        bursts = BurstParticles(400, seed=1)
        show = ReactionShow(bursts, seed=2)
        show.add((300, 200), Reaction.STEAM, Element.FIRE, Element.WATER, "10 de daño")
        for _ in range(3):                       # 0.15 s: still flying
            show.update(0.05)
        assert bursts.count == 0 and show.shake_offset() == (0, 0)
        for _ in range(6):                       # past CLASH: impact
            show.update(0.05)
        assert bursts.count > 0 and show.busy and show.shake_offset() != (0, 0) or bursts.count > 0
        for _ in range(int(LIFE / 0.05)):
            show.update(0.05)
        assert not show.busy

    def test_delay_waits(self):
        bursts = BurstParticles(100)
        show = ReactionShow(bursts)
        show.add((0, 0), Reaction.MUD, Element.WATER, Element.EARTH, "", delay=1.0)
        show.update(0.9)
        assert bursts.count == 0 and show.busy

    def test_every_reaction_draws_in_every_phase(self):
        surf = pygame.Surface((640, 360))
        for r in Reaction:
            show = ReactionShow(BurstParticles(200))
            show.add((320, 180), r, None, Element.AIR, "algo")
            for _ in range(int(LIFE / 0.05) + 2):
                show.update(0.05)
                show.draw(surf, FONTS)
            assert not show.busy

    def test_huge_dt_is_clamped(self):
        show = ReactionShow(BurstParticles(50))
        show.add((0, 0), Reaction.FREEZE, Element.WATER, Element.AIR, "")
        for _ in range(100):
            show.update(10 ** 9)
        assert not show.busy


# ---------------------------------------------------------------- wheel

class TestWheel:
    def test_every_reaction_has_its_own_spot_inside_the_panel(self):
        spots = [reaction_spot(p) for p in REACTIONS]
        assert len(set(spots)) == 6 and all(PANEL.collidepoint(s) for s in spots)
        assert all(PANEL.collidepoint(c) for c in CORNERS.values())

    def test_close_by_key_click_outside_and_button(self):
        for event in (_key(pygame.K_ESCAPE), _key(pygame.K_r),
                      pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=(5, 5))):
            w = ElementWheelOverlay(FONTS)
            w.handle_event(event)
            assert w.dismissed
        w = ElementWheelOverlay(FONTS)
        w.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=w.close_rect.center))
        assert w.dismissed
        w = ElementWheelOverlay(FONTS)
        w.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=PANEL.center))
        assert not w.dismissed

    def test_draws(self):
        w = ElementWheelOverlay(FONTS)
        surf = pygame.Surface((1280, 720))
        for _ in range(30):
            w.update(1 / 30)
            w.draw(surf)


# ---------------------------------------------------------------- cards and badges

class TestCardArt:
    def test_mage_cards_have_no_illustration_yet(self):
        assert not has_card_art("mg_bola_fuego")

    def test_element_art_changes_the_face(self):
        fire = render_card_surface(_card("mg_bola_fuego"), FONTS)
        water = render_card_surface(_card("mg_gota"), FONTS)
        mid = (CARD_W // 2, 50)
        assert fire.get_at(mid) != water.get_at(mid)

    def test_chips_fit_the_art_window(self):
        for f in card_factories_for_classes({CardClass.MAGE}):
            for fx in f().all_effects():
                if fx.element is not None and fx.element_stacks > 0:
                    assert _element_chip(fx, 2, FONTS).get_width() < 100
                    assert _element_chip(fx, 1, FONTS).get_width() < 64

    def test_every_size_renders(self):
        for f in card_factories_for_classes({CardClass.MAGE}):
            for w, h in ((84, 116), (CARD_W, CARD_H), (182, 252)):
                render_card_surface(f(), FONTS, w=w, h=h)


class TestEnemyBadge:
    def test_element_badge_is_separate_and_first_in_the_hitboxes(self):
        s = _state()
        enemy = s.enemies[0]
        enemy.status_effects = [StatusEffect("Veneno", 2, False)]
        apply_element(s, enemy, Element.EARTH, 4)
        boxes: dict = {}
        draw_enemy(pygame.Surface((1280, 720)), enemy, 700, 120, FONTS, hitboxes=boxes)
        assert boxes["element"].w == 34
        assert [fx.name for fx, _ in boxes["statuses"]] == ["Tierra", "Veneno"]


class TestCombatWiring:
    def _scene(self, hand=("mg_gota", "mg_brisa")):
        s = _state(hand)
        scene = CombatScene(s, FONTS)
        scene.draw(pygame.Surface((1280, 720)))
        return s, scene

    def test_wheel_button_and_key(self):
        s, scene = self._scene()
        scene.handle_event(_key(pygame.K_r))
        assert isinstance(scene._overlay, ElementWheelOverlay)
        scene.handle_event(_key(pygame.K_ESCAPE))
        scene.update(0.01)
        assert scene._overlay is None
        scene._handle_click(scene.elements_button_rect.center)
        assert isinstance(scene._overlay, ElementWheelOverlay)

    def test_no_wheel_without_elements(self):
        s = create_sample_combat()
        for e in s.enemies:
            e.status_effects = []
        scene = CombatScene(s, FONTS)
        scene.draw(pygame.Surface((1280, 720)))
        scene.handle_event(_key(pygame.K_r))
        assert scene._overlay is None

    def test_aiming_builds_the_preview(self):
        s, scene = self._scene()
        apply_element(s, s.enemies[0], Element.FIRE, 3)
        scene._handle_key(pygame.K_1)
        scene.draw(pygame.Surface((1280, 720)))
        assert scene._preview_cache is not None
        assert scene._preview_cache[1].enemies[0].reactions[0].reaction is Reaction.STEAM

    def test_hover_hints_who_would_react(self):
        s, scene = self._scene()
        apply_element(s, s.enemies[2], Element.FIRE, 1)
        scene._hovered_card = 0
        assert scene._reaction_targets() == {2: Reaction.STEAM}

    def test_killing_reaction_holds_victory_for_the_show(self):
        s, scene = self._scene()
        s.enemies = s.enemies[:1]
        enemy = s.enemies[0]
        enemy.status_effects = []
        enemy.current_hp = 5
        scene.draw(pygame.Surface((1280, 720)))
        apply_element(s, enemy, Element.FIRE, 3)
        scene._do_play_card(0, 0)
        assert not enemy.is_alive and scene._hold_time > CLASH
        assert not scene.combat_won

    def test_shake_draws_at_an_offset(self):
        s, scene = self._scene()
        apply_element(s, s.enemies[0], Element.FIRE, 3)
        scene._do_play_card(0, 0)
        surf = pygame.Surface((1280, 720))
        for _ in range(60):
            scene.update(1 / 60)
            scene.draw(surf)
