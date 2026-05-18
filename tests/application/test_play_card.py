"""Tests for play_card use case: damage, block, mana, draws, and relic bonuses."""
from __future__ import annotations

import pytest

from src.application.play_card import play_card
from src.domain.card import Card, CardEffect, CardType
from src.domain.combat import CombatState
from src.domain.entities import Enemy, Intent, IntentType, Player
from src.domain.mana import Mana
from src.domain.numbers import BigValue
from src.domain.pile import DiscardPile, DrawPile, Hand
from src.domain.relic import Relic, RelicTag


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _attack_card(damage: int, cost: int = 1) -> Card:
    return Card(
        id="atk", name="Golpe", card_type=CardType.ATTACK, cost=cost,
        base_effect=CardEffect(name="Golpe", damage=BigValue(damage)),
    )


def _skill_card(block: int, draw: int = 0, cost: int = 1) -> Card:
    return Card(
        id="skl", name="Defender", card_type=CardType.SKILL, cost=cost,
        base_effect=CardEffect(name="Defender", block=BigValue(block), draw=draw),
    )


def _power_card(cost: int = 0) -> Card:
    return Card(
        id="pow", name="Poder", card_type=CardType.POWER, cost=cost,
        base_effect=CardEffect(name="Poder"),
    )


def _draw_card() -> Card:
    return Card(
        id="fill", name="Relleno", card_type=CardType.ATTACK, cost=1,
        base_effect=CardEffect(name="Relleno", damage=BigValue(1)),
    )


def _make_state(
    hand: list[Card],
    enemy_hp: int = 50,
    enemy_block: int = 0,
    player_hp: int = 80,
    player_block: int = 0,
    mana_current: int = 3,
    mana_max: int = 3,
    relics: list[Relic] | None = None,
    draw_cards: list[Card] | None = None,
) -> CombatState:
    enemy = Enemy(
        id="e1", name="Enemigo", max_hp=enemy_hp, current_hp=enemy_hp,
        block=enemy_block, intent=Intent(IntentType.ATTACK, 5),
    )
    return CombatState(
        player=Player(name="P", max_hp=100, current_hp=player_hp, block=player_block),
        enemies=[enemy],
        hand=Hand(cards=list(hand)),
        draw_pile=DrawPile(cards=list(draw_cards or [])),
        discard_pile=DiscardPile(cards=[]),
        mana=Mana(current=mana_current, maximum=mana_max),
        relics=relics or [],
    )


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------

class TestValidation:
    def test_invalid_index_negative(self):
        state = _make_state([_attack_card(6)])
        result = play_card(state, -1, 0)
        assert not result.success

    def test_invalid_index_out_of_range(self):
        state = _make_state([_attack_card(6)])
        result = play_card(state, 5, 0)
        assert not result.success

    def test_insufficient_mana(self):
        state = _make_state([_attack_card(6, cost=3)], mana_current=1)
        result = play_card(state, 0, 0)
        assert not result.success

    def test_attack_needs_target(self):
        state = _make_state([_attack_card(6)])
        result = play_card(state, 0, None)
        assert not result.success

    def test_invalid_target_index(self):
        state = _make_state([_attack_card(6)])
        result = play_card(state, 0, 99)
        assert not result.success

    def test_zero_mana_cost_succeeds_with_no_mana(self):
        state = _make_state([_skill_card(5, cost=0)], mana_current=0)
        result = play_card(state, 0, None)
        assert result.success


# ---------------------------------------------------------------------------
# Damage application
# ---------------------------------------------------------------------------

class TestDamage:
    def test_deals_base_damage(self):
        state = _make_state([_attack_card(6)])
        play_card(state, 0, 0)
        assert state.enemies[0].current_hp == 44  # 50 - 6

    def test_damage_absorbed_by_block(self):
        state = _make_state([_attack_card(6)], enemy_block=4)
        play_card(state, 0, 0)
        assert state.enemies[0].block == 0
        assert state.enemies[0].current_hp == 48  # 50 - (6-4)=2 remaining dmg

    def test_damage_fully_blocked(self):
        state = _make_state([_attack_card(6)], enemy_block=10)
        play_card(state, 0, 0)
        assert state.enemies[0].block == 4   # 10 - 6
        assert state.enemies[0].current_hp == 50  # no HP lost

    def test_damage_kills_enemy(self):
        state = _make_state([_attack_card(100)], enemy_hp=30)
        play_card(state, 0, 0)
        assert state.enemies[0].current_hp == 0

    def test_hp_never_goes_negative(self):
        state = _make_state([_attack_card(10**9)], enemy_hp=1)
        play_card(state, 0, 0)
        assert state.enemies[0].current_hp == 0

    def test_large_damage_value(self):
        card = Card(
            id="big", name="Mega", card_type=CardType.ATTACK, cost=1,
            base_effect=CardEffect("big", damage=BigValue(10**9).add_multiplier(10**9)),
        )
        state = _make_state([card], enemy_hp=10**18)
        play_card(state, 0, 0)
        assert state.enemies[0].current_hp == 0


# ---------------------------------------------------------------------------
# Fire Orb relic bonus
# ---------------------------------------------------------------------------

class TestFireOrbBonus:
    def _orb(self) -> Relic:
        return Relic("r", "Orbe de Fuego", "", tag=RelicTag.FIRE_ORB)

    def test_orb_adds_two_damage(self):
        state = _make_state([_attack_card(6)], relics=[self._orb()])
        play_card(state, 0, 0)
        # 50 - (6+2) = 42
        assert state.enemies[0].current_hp == 42

    def test_orb_inactive_no_bonus(self):
        orb = Relic("r", "Orbe", "", tag=RelicTag.FIRE_ORB, is_active=False)
        state = _make_state([_attack_card(6)], relics=[orb])
        play_card(state, 0, 0)
        assert state.enemies[0].current_hp == 44  # base only

    def test_orb_does_not_affect_block_cards(self):
        state = _make_state([_skill_card(5)], relics=[self._orb()])
        play_card(state, 0, None)
        # block should be exactly 5, not 7
        assert state.player.block == 5

    def test_orb_with_large_base_damage(self):
        card = Card(
            id="big", name="Big", card_type=CardType.ATTACK, cost=1,
            base_effect=CardEffect("big", damage=BigValue(10**9)),
        )
        state = _make_state([card], relics=[self._orb()], enemy_hp=10**9 + 3)
        play_card(state, 0, 0)
        # (10^9 + 2) damage → 10^9+3 - (10^9+2) = 1 HP left
        assert state.enemies[0].current_hp == 1


# ---------------------------------------------------------------------------
# Block application
# ---------------------------------------------------------------------------

class TestBlock:
    def test_skill_gives_block(self):
        state = _make_state([_skill_card(5)])
        play_card(state, 0, None)
        assert state.player.block == 5

    def test_block_stacks(self):
        state = _make_state([_skill_card(5), _skill_card(3)], mana_current=3)
        play_card(state, 0, None)
        play_card(state, 0, None)
        assert state.player.block == 8


# ---------------------------------------------------------------------------
# Mana spending
# ---------------------------------------------------------------------------

class TestMana:
    def test_mana_spent(self):
        state = _make_state([_attack_card(6, cost=2)])
        play_card(state, 0, 0)
        assert state.mana.current == 1  # 3 - 2

    def test_zero_cost_no_mana_spent(self):
        state = _make_state([_skill_card(5, cost=0)])
        play_card(state, 0, None)
        assert state.mana.current == 3

    def test_exact_mana_succeeds(self):
        state = _make_state([_attack_card(6, cost=3)], mana_current=3)
        result = play_card(state, 0, 0)
        assert result.success
        assert state.mana.current == 0


# ---------------------------------------------------------------------------
# Card movement after play
# ---------------------------------------------------------------------------

class TestCardMovement:
    def test_attack_goes_to_discard(self):
        state = _make_state([_attack_card(6)])
        play_card(state, 0, 0)
        assert state.hand.count == 0
        assert state.discard_pile.count == 1

    def test_skill_goes_to_discard(self):
        state = _make_state([_skill_card(5)])
        play_card(state, 0, None)
        assert state.hand.count == 0
        assert state.discard_pile.count == 1

    def test_power_goes_to_active_powers(self):
        state = _make_state([_power_card()])
        play_card(state, 0, None)
        assert state.hand.count == 0
        assert len(state.active_powers) == 1
        assert state.discard_pile.count == 0


# ---------------------------------------------------------------------------
# Draw effect
# ---------------------------------------------------------------------------

class TestDrawEffect:
    def test_skill_with_draw_draws_card(self):
        extra = _draw_card()
        state = _make_state([_skill_card(5, draw=1)], draw_cards=[extra])
        play_card(state, 0, None)
        assert state.hand.count == 1  # drew 1 card
        assert state.draw_pile.count == 0

    def test_draw_from_truly_empty_piles_does_nothing(self):
        # When both draw AND discard are empty, draw effect yields nothing.
        # Note: the played card itself goes to discard first, so we use a card
        # with draw=2 but pre-clear the discard after play by using a POWER card
        # (which goes to active_powers, not discard) to avoid the reshuffle edge case.
        power_draw = Card(
            id="pd", name="PD", card_type=CardType.POWER, cost=0,
            base_effect=CardEffect("pd", draw=2),
        )
        state = _make_state([power_draw], draw_cards=[])
        # Discard is also empty; power goes to active_powers (not discard)
        play_card(state, 0, None)
        assert state.hand.count == 0  # nothing to draw from either pile

    def test_draw_reshuffles_discard(self):
        filler = _draw_card()
        state = _make_state([_skill_card(5, draw=1)], draw_cards=[])
        state.discard_pile.cards.append(filler)
        play_card(state, 0, None)
        assert state.hand.count == 1  # drew from reshuffled discard

    def test_draw_stops_at_hand_limit(self):
        # hand max_size = 10; start with 9 cards + draw 2 more → only 1 drawn
        hand = [_skill_card(1, cost=0)] + [_draw_card() for _ in range(8)]
        draw_pile = [_draw_card(), _draw_card()]
        state = _make_state(hand, draw_cards=draw_pile, mana_current=0)
        # play the skill card (index 0) which draws 2
        skill = Card(
            id="sk", name="Sk", card_type=CardType.SKILL, cost=0,
            base_effect=CardEffect("sk", block=BigValue(0), draw=2),
        )
        state.hand.cards[0] = skill
        play_card(state, 0, None)
        assert state.hand.count == 10  # capped at max
