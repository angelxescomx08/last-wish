"""Card deal: drawn cards fly in from the draw pile, one cast at a time.

Covers ``fx/card_deal`` (easing, flip, arc ends and height, scale overshoot, wait/flight
timing, a huge frame lands the card, drawing back and face), ``PlayResult.cast_drawn``
(per cast, golden twice, no draw = 0, a full hand), and the CombatScene: a golden "draw 2"
shows 2 cards after the first cast and 2 more after the second, a normal draw waits for the
cast, waiting cards are not in the fan nor clickable, the hand counter and the pile count
show what is on screen, the new hand is dealt after the enemy turn while the old one flies to
the discard pile, a card redrawn in the same play flies in again, and card frames are
decoded once (startup prewarm; no reload when a card changes size).
"""
from __future__ import annotations

import pygame
import pytest

from src.application.combat_factory import create_combat_from_run
from src.application.play_card import play_card
from src.application.run_manager import create_run
from src.domain.card import Card, CardEffect, CardType
from src.domain.character import ALL_CHARACTERS
from src.domain.chroma import Chroma
from src.domain.entities import Enemy, Intent, IntentType
from src.domain.numbers import BigValue
from src.infrastructure import card_assets
from src.infrastructure.fonts import FontRegistry
from src.presentation.fx import card_deal as cd
from src.presentation.scenes.combat_scene import CombatScene
from src.presentation.ui.card_widget import render_card_surface

FONTS = FontRegistry()


def _draw_card(n=2, golden=False) -> Card:
    return Card(id="draw", name="Visión", card_type=CardType.SKILL, cost=0,
                base_effect=CardEffect(name="Visión", draw=n), chroma=Chroma.GOLDEN if golden else None)


def _filler(i) -> Card:
    return Card(id=f"f{i}", name=f"F{i}", card_type=CardType.ATTACK, cost=1,
                base_effect=CardEffect(name="F", damage=BigValue(3)))


def _scene(hand=3, pile=12) -> CombatScene:
    run = create_run(ALL_CHARACTERS[0], 3)
    state = create_combat_from_run(run, [Enemy(id="e", name="Cultista", max_hp=999, current_hp=999,
                                               intent=Intent(IntentType.BLOCK, 1))])
    state.hand.cards = [_filler(i) for i in range(hand)]
    state.draw_pile.cards = [_filler(100 + i) for i in range(pile)]
    state.mana.current = 5
    scene = CombatScene(state, FONTS)
    _steps(scene, 2.0)
    scene.draw(pygame.Surface((1280, 720)))
    return scene


def _steps(scene, seconds, dt=1 / 60):
    for _ in range(int(seconds / dt) + 1):
        scene.update(dt)


def _shown(scene) -> int:
    """Cards in hand that are on screen (landed or flying)."""
    return scene.state.hand.count - len(scene._waiting_indices())


# ---------------------------------------------------------------------------
# Pure math
# ---------------------------------------------------------------------------

class TestMath:
    def test_easing_ends(self):
        assert cd.ease_out_cubic(0) == 0 and cd.ease_out_cubic(1) == 1
        assert abs(cd.ease_out_back(1) - 1) < 1e-9 and cd.ease_out_back(0) == 0

    def test_back_overshoots(self):
        assert max(cd.ease_out_back(u / 100) for u in range(101)) > 1.0

    def test_clamped(self):
        assert cd.ease_out_cubic(-5) == 0 and cd.ease_out_cubic(10 ** 9) == 1

    def test_flip(self):
        assert cd.flip_width(0) == (1.0, False)
        w, face = cd.flip_width(cd.FLIP_END / 2)
        assert w < 0.01
        assert cd.flip_width(cd.FLIP_END)[1] and abs(cd.flip_width(1)[0] - 1) < 1e-9

    def test_pose_ends(self):
        start, goal = (1150.0, 600.0), (640.0, 620.0, 1.0, -4.0)
        x, y, scale, angle = cd.deal_pose(0, start, goal)
        assert (round(x), round(y), scale, angle) == (1150, 600, cd.START_SCALE, cd.START_ANGLE)
        x, y, scale, angle = cd.deal_pose(1, start, goal)
        assert (round(x), round(y), round(scale, 6), round(angle, 6)) == (640, 620, 1.0, -4.0)

    def test_arcs_up(self):
        start, goal = (1150.0, 600.0), (640.0, 620.0, 1.0, 0.0)
        ys = [cd.deal_pose(u / 20, start, goal)[1] for u in range(21)]
        assert min(ys) < 600 - cd.ARC_HEIGHT / 3

    def test_moves_monotonically_left(self):
        start, goal = (1150.0, 600.0), (300.0, 620.0, 1.0, 0.0)
        xs = [cd.deal_pose(u / 30, start, goal)[0] for u in range(31)]
        assert xs == sorted(xs, reverse=True)


class TestDealState:
    def test_wait_then_fly(self):
        d = cd.Deal(0.3, (0, 0))
        d.advance(0.2)
        assert d.waiting and d.progress == 0
        d.advance(0.2)
        assert not d.waiting and abs(d.t - 0.1) < 1e-9

    def test_done(self):
        d = cd.Deal(0.0, (0, 0))
        d.advance(cd.DEAL_SECONDS)
        assert d.done and d.progress == 1.0

    def test_huge_frame(self):
        d = cd.Deal(5.0, (0, 0))
        d.advance(10 ** 9)
        assert d.done

    def test_negative_dt(self):
        d = cd.Deal(0.2, (0, 0))
        d.advance(-1)
        assert d.wait == 0.2


class TestDrawing:
    @pytest.mark.parametrize("u", [0.0, 0.1, 0.29, 0.31, 0.5, 0.59, 0.6, 1.0])
    def test_draws(self, u):
        face = render_card_surface(_filler(0), FONTS)
        rect = cd.draw_dealt_card(pygame.Surface((1280, 720)), face, (600, 500, 0.8, -12.0), u)
        assert rect.width >= 1 and rect.height > 50

    def test_edge_on_is_thin(self):
        face = render_card_surface(_filler(0), FONTS)
        thin = cd.draw_dealt_card(pygame.Surface((1280, 720)), face, (600, 500, 1.0, 0.0), cd.FLIP_END / 2)
        assert thin.width <= 3


# ---------------------------------------------------------------------------
# Rules: cards drawn per cast
# ---------------------------------------------------------------------------

class TestCastDrawn:
    def _state(self, hand, pile=10):
        scene = _scene(hand=0, pile=pile)
        scene.state.hand.cards = list(hand)
        scene.state.discard_pile.cards = []
        return scene.state

    def test_normal(self):
        st = self._state([_draw_card(2)])
        assert play_card(st, 0, None).cast_drawn == [2]

    def test_golden(self):
        st = self._state([_draw_card(2, golden=True)])
        assert play_card(st, 0, None).cast_drawn == [2, 2]

    def test_no_draw(self):
        st = self._state([_draw_card(0)])
        assert play_card(st, 0, None).cast_drawn == [0]

    def test_empty_pile(self):
        # 1 card in the pile; the played card is already in the discard, so the first cast
        # reshuffles and draws it back; the second cast finds nothing left.
        st = self._state([_draw_card(2, golden=True)], pile=1)
        assert play_card(st, 0, None).cast_drawn == [2, 0]


# ---------------------------------------------------------------------------
# Combat screen
# ---------------------------------------------------------------------------

class TestScene:
    def test_golden_draws_cast_by_cast(self):
        scene = _scene()
        scene.state.hand.cards.insert(0, _draw_card(2, golden=True))
        scene.draw(pygame.Surface((1280, 720)))
        scene._do_play_card(0, None)
        assert scene.state.hand.count == 7
        scene.update(0.0)
        assert _shown(scene) == 3                        # nothing yet: the card goes on stage
        _steps(scene, scene._cast_time(0) + 0.45)
        assert _shown(scene) == 5                        # first cast: 2 cards
        _steps(scene, scene._cast_time(1) - scene._cast_time(0))
        assert _shown(scene) == 7                        # second cast: 2 more

    def test_normal_draw_waits_for_the_cast(self):
        scene = _scene()
        scene.state.hand.cards.insert(0, _draw_card(2))
        scene._do_play_card(0, None)
        scene.update(1 / 60)
        assert _shown(scene) == 3
        _steps(scene, 1.0)
        assert _shown(scene) == 5 and not scene._deals

    def test_waiting_cards_not_in_fan_nor_clickable(self):
        scene = _scene()
        scene.state.hand.cards.insert(0, _draw_card(2))
        scene._do_play_card(0, None)
        scene.update(1 / 60)
        scene.draw(pygame.Surface((1280, 720)))
        waiting = scene._waiting_indices()
        assert len(waiting) == 2 and not waiting & set(scene._card_hit_order())

    def test_counts_follow_the_screen(self):
        scene = _scene(pile=12)
        scene.state.hand.cards.insert(0, _draw_card(2, golden=True))
        scene._do_play_card(0, None)
        scene.update(1 / 60)
        assert scene.state.draw_pile.count + len(scene._waiting_indices()) == 12

    def test_cards_land_in_their_slots(self):
        scene = _scene()
        scene.state.hand.cards.insert(0, _draw_card(2, golden=True))
        scene._do_play_card(0, None)
        _steps(scene, 5.0)
        goal = scene._target_poses()
        for i, key in enumerate(scene._card_keys()):
            assert abs(scene._motion[key].x - goal[i].x) < 0.5

    def test_drawing_while_dealing(self):
        scene = _scene()
        scene.state.hand.cards.insert(0, _draw_card(3, golden=True))
        scene._do_play_card(0, None)
        surface = pygame.Surface((1280, 720))
        for _ in range(150):
            scene.update(1 / 60)
            scene.draw(surface)

    def test_end_turn_old_hand_leaves_new_hand_waits(self):
        scene = _scene(hand=4)
        scene._do_end_turn()
        assert len(scene._leaving) == 4
        scene.update(1 / 60)
        assert len(scene._waiting_indices()) == scene.state.hand.count > 0
        _steps(scene, 3.0)
        assert not scene._deals

    def test_opening_hand_dealt_one_by_one(self):
        run = create_run(ALL_CHARACTERS[0], 3)
        state = create_combat_from_run(run, [Enemy(id="e", name="Cultista", max_hp=50, current_hp=50)])
        scene = CombatScene(state, FONTS)
        scene.update(1 / 60)
        waits = sorted(d.wait for d in scene._deals.values())
        assert len(waits) == state.hand.count and waits[-1] > waits[0]

    def test_redrawn_card_flies_again(self):
        scene = _scene(hand=0, pile=0)
        card = _draw_card(1)
        scene.state.hand.cards = [card]
        scene.update(1 / 60)
        _steps(scene, 1.0)
        scene._do_play_card(0, None)                    # its own draw reshuffles and draws it back
        assert scene.state.hand.cards == [card]
        scene.update(1 / 60)
        assert scene._card_keys()[0] in scene._deals

    def test_stress_many_draws(self):
        scene = _scene(hand=0, pile=200)
        for _ in range(20):
            scene.state.hand.cards.insert(0, _draw_card(3, golden=True))
            scene._do_play_card(0, None)
            _steps(scene, 0.4, dt=0.05)
            scene.state.hand.cards = scene.state.hand.cards[:2]
        _steps(scene, 5.0, dt=0.05)
        assert not scene._deals


class TestAssetCache:
    def test_prewarm(self):
        assert card_assets.prewarm(((150, 210),)) > 5

    def test_sources_decoded_once(self, monkeypatch):
        card_assets.prewarm()
        calls = []
        real = card_assets._load_uncached
        monkeypatch.setattr(card_assets, "_load_uncached", lambda p: calls.append(p) or real(p))
        for w in range(100, 140):
            card_assets.card_frame("common", w, int(w * 1.4))
        assert calls == []
