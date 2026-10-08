"""Card numbers outside combat, "ready" keyword effects and the restyled main menu.

Covers ``application/card_preview`` (bonuses from the character, Pruebas and relics;
the same numbers as the combat hand; cards without damage/block get no bonus), every
screen that offers cards using them (reward, pack, deck/pile viewers, Brujo),
``fx/card_fx`` (which keywords are ready, colour cycling, comets on the edge, badge,
tilt, golden + ready together) and ``MainMenuScene`` (buttons, fade-in, hover, 1000-frame
stress).
"""
from __future__ import annotations

from unittest.mock import Mock

import pygame
import pytest

from src.application.card_preview import NO_BONUS, CardBonus, combat_card_bonus, run_card_bonus
from src.application.card_rewards import pick_reward_cards
from src.application.combat_factory import create_combat_from_run
from src.application.run_manager import create_run, generate_enemies
from src.domain import card_pool as cp
from src.domain.card import Card, CardEffect, CardType
from src.domain.character import ALL_CHARACTERS
from src.domain.chroma import Chroma
from src.domain.keywords import Keyword
from src.domain.numbers import BigValue
from src.domain.relic import Relic, RelicTag
from src.domain.tuning import TUNING
from src.infrastructure.fonts import FontRegistry
from src.presentation.fx import card_fx
from src.presentation.scenes.combat_reward_scene import CombatRewardScene
from src.presentation.scenes.main_menu_scene import MainMenuScene, MenuAction
from src.presentation.scenes.pack_opening_scene import PackOpeningScene
from src.presentation.ui.card_widget import draw_card, draw_card_at
from src.presentation.ui.pile_viewer import PileViewer

FONTS = FontRegistry()


def _run(hero: int = 0):
    return create_run(ALL_CHARACTERS[hero], 3)


def _atk(dmg: int = 6) -> Card:
    return Card(id="t_atk", name="Golpe", card_type=CardType.ATTACK, cost=1,
                base_effect=CardEffect("Golpe", damage=BigValue(dmg)))


def _skl(blk: int = 5) -> Card:
    return Card(id="t_skl", name="Defender", card_type=CardType.SKILL, cost=1,
                base_effect=CardEffect("Defender", block=BigValue(blk)))


def _power() -> Card:
    return Card(id="t_pow", name="Poder", card_type=CardType.POWER, cost=1, base_effect=CardEffect("Poder"))


def _rogue_cards() -> list[Card]:
    return [f() for f in cp._ROGUE_ACERO + cp._ROGUE_MAGIA + cp._ROGUE_EPICO + cp._ROGUE_ESCUDO]


# ---------------------------------------------------------------- numbers outside combat

class TestCardPreview:
    @pytest.mark.parametrize("hero", range(3))
    def test_run_bonus_is_the_hero_stats(self, hero):
        run = _run(hero)
        st = run.character.stats
        assert run_card_bonus(run) == CardBonus(st.damage, st.dexterity)

    def test_relic_and_pruebas(self):
        run = _run()
        run.relics.append(Relic("o", "Orbe de Fuego", "", tag=RelicTag.FIRE_ORB))
        TUNING.extra_damage, TUNING.extra_dexterity = 3, 2
        st = run.character.stats
        assert run_card_bonus(run) == CardBonus(st.damage + 3 + 2, st.dexterity + 2)

    @pytest.mark.parametrize("hero", range(3))
    def test_same_as_combat_hand(self, hero):
        run = _run(hero)
        run.relics.append(Relic("o", "Orbe de Fuego", "", tag=RelicTag.FIRE_ORB))
        state = create_combat_from_run(run, generate_enemies(run, "r1"))
        assert run_card_bonus(run) == combat_card_bonus(state)

    def test_for_card(self):
        bonus = CardBonus(4, 3)
        assert (bonus.for_card(_atk()), bonus.for_card(_skl()), bonus.for_card(_power())) == \
            ((4, 0), (0, 3), (0, 0))

    def test_no_run(self):
        assert run_card_bonus(None) is NO_BONUS and NO_BONUS.for_card(_atk()) == (0, 0)

    def test_huge_bonus(self):
        assert CardBonus(10 ** 100, 0).for_card(_atk())[0] == 10 ** 100

    def test_reward_scene_uses_run_bonus(self):
        run = _run()
        scene = CombatRewardScene(run, 10, pick_reward_cards(run, "r1"), FONTS, sound=Mock())
        assert scene._bonus == run_card_bonus(run)
        scene.draw(pygame.Surface((1280, 720)))

    def test_pack_scene_takes_bonus(self):
        bonus = CardBonus(4, 4)
        scene = PackOpeningScene([_atk(), _skl()], "Sobre", FONTS, sound=Mock(), bonus=bonus)
        assert scene._bonus == bonus
        scene.skip_animation()
        scene.draw(pygame.Surface((1280, 720)))

    def test_pile_viewer_shows_bonus(self):
        viewer = PileViewer("Mazo", [_atk()], FONTS, CardBonus(4, 0))
        assert "10 de daño" in viewer._tooltip(_atk()).all_text()

    def test_manager_wires_bonus_into_packs(self):
        import main
        src = open(main.__file__, encoding="utf-8").read()
        assert src.count("bonus=run_card_bonus(run)") >= 2


# ---------------------------------------------------------------- ready effects

class TestReadyKeywords:
    def _combo(self) -> Card:
        return next(c for c in _rogue_cards() if c.combo_effects())

    def _singular(self) -> Card:
        return next(c for c in _rogue_cards() if c.singular_effects())

    def test_only_layers_the_card_has(self):
        assert card_fx.ready_keywords(_atk(), combo=True, singular=True, void=True, spoil=True) == []

    def test_combo(self):
        assert card_fx.ready_keywords(self._combo(), combo=True) == [Keyword.COMBO]

    def test_not_ready(self):
        assert card_fx.ready_keywords(self._combo(), combo=False) == []

    def test_every_keyword_has_a_style(self):
        assert set(card_fx.READY_STYLES) == set(Keyword)

    def test_single_colour(self):
        assert card_fx.current_color([Keyword.COMBO], 3.3) == card_fx.READY_STYLES[Keyword.COMBO].color

    def test_colour_cycles_with_two(self):
        ks = [Keyword.COMBO, Keyword.SINGULAR]
        assert card_fx.current_color(ks, 0.1) != card_fx.current_color(ks, 1.3)

    def test_no_colour(self):
        assert card_fx.current_color([], 1.0) is None

    @pytest.mark.parametrize("u", [0.0, 0.1, 0.37, 0.5, 0.99, 7.25])
    def test_perimeter_on_edge(self, u):
        x, y = card_fx.perimeter_point(u, 100, 140)
        assert abs(abs(x) - 50) < 1e-6 or abs(abs(y) - 70) < 1e-6

    def test_comets_per_keyword(self):
        ks = [Keyword.COMBO, Keyword.SPOIL]
        assert len(card_fx.comet_positions(ks, 150, 210, 1.0)) == 2 * card_fx.COMETS_PER_KEYWORD

    def test_comets_move(self):
        a = card_fx.comet_positions([Keyword.COMBO], 150, 210, 0.0)
        b = card_fx.comet_positions([Keyword.COMBO], 150, 210, 0.5)
        assert a != b

    def test_tilt_rotates(self):
        flat = card_fx.comet_positions([Keyword.COMBO], 150, 210, 0.2)
        tilted = card_fx.comet_positions([Keyword.COMBO], 150, 210, 0.2, angle=10)
        assert flat != tilted

    def test_front_returns_badge(self):
        surf = pygame.Surface((800, 600))
        badge = card_fx.draw_ready_front(surf, (400, 300), (150, 210), [Keyword.COMBO], 0.4, FONTS)
        assert badge is not None and badge.bottom <= 300 - 105 + 4

    def test_front_nothing_ready(self):
        assert card_fx.draw_ready_front(pygame.Surface((10, 10)), (5, 5), (4, 4), [], 0.0, FONTS) is None

    def test_card_widgets_with_ready_and_golden(self):
        surf = pygame.Surface((1280, 720))
        card = self._combo()
        card.chroma = Chroma.GOLDEN
        for angle in (0.0, 7.0):
            draw_card_at(surf, card, (640, 400), FONTS, scale=1.2, angle=angle, combo=True)
        draw_card(surf, self._singular(), 100, 100, FONTS, singular=True, combo=True)

    def test_combat_hand_draws_ready_cards(self):
        from src.presentation.scenes.combat_scene import CombatScene
        run = _run(2)
        state = create_combat_from_run(run, generate_enemies(run, "r1"))
        state.hand.cards[:] = [self._combo(), self._singular()]
        state.cards_played_this_turn = 1
        state.singular_deck = True
        scene = CombatScene(state, FONTS, sound=Mock())
        surf = pygame.Surface((1280, 720))
        for _ in range(3):
            scene.update(1 / 60)
            scene.draw(surf)


# ---------------------------------------------------------------- main menu

class TestMainMenu:
    def _menu(self):
        return MainMenuScene(FONTS, sound=Mock())

    def test_buttons_are_rects_of_the_kit_size(self):
        m = self._menu()
        m.draw(pygame.Surface((1280, 720)))
        assert len(m._option_rects) == 4 and all(r.size == (330, 48) for r in m._option_rects)

    def test_buttons_do_not_overlap(self):
        m = self._menu()
        m.draw(pygame.Surface((1280, 720)))
        rs = m._option_rects
        assert not any(a.colliderect(b) for i, a in enumerate(rs) for b in rs[i + 1:])

    def test_click_confirms(self):
        m = self._menu()
        m.draw(pygame.Surface((1280, 720)))
        m.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=m._option_rects[3].center))
        assert m.requested_action == MenuAction.EXIT

    def test_keys(self):
        m = self._menu()
        m.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_DOWN))
        m.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN))
        assert m.requested_action == MenuAction.SETTINGS

    def test_fade_in_then_clear(self):
        m = self._menu()
        surf = pygame.Surface((1280, 720))
        m.draw(surf)
        dark = surf.get_at((640, 150))
        for _ in range(60):
            m.update(1 / 60)
        m.draw(surf)
        assert sum(surf.get_at((640, 150))[:3]) > sum(dark[:3])

    def test_stress(self):
        m = self._menu()
        surf = pygame.Surface((1280, 720))
        for k in range(1000):
            m.update(10 ** 9 if k == 5 else 1 / 60)
        m.handle_event(pygame.event.Event(pygame.MOUSEMOTION, pos=(640, 400), rel=(0, 0), buttons=(0, 0, 0)))
        m.draw(surf)
