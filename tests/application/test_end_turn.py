"""Tests for end_turn pipeline: draw mechanics, enemy actions, relic integration."""
from __future__ import annotations

import pytest

from src.application.end_turn import draw_opening_hand, end_player_turn
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

def _card(name: str = "Golpe") -> Card:
    return Card(
        id=name, name=name, card_type=CardType.ATTACK, cost=1,
        base_effect=CardEffect(name, damage=BigValue(1)),
    )


def _relic(tag: RelicTag, *, active: bool = True) -> Relic:
    return Relic(id="r", name="R", description="", tag=tag, is_active=active)


def _make_state(
    draw_count: int = 20,
    hand_cards: list[Card] | None = None,
    relics: list[Relic] | None = None,
    player_hp: int = 80,
    player_block: int = 0,
    player_luck: int = 0,
    mana_current: int = 3,
    mana_max: int = 3,
    enemy_attack: int = 5,
) -> CombatState:
    draw_pile = [_card(f"d{i}") for i in range(draw_count)]
    enemy = Enemy(
        id="e1", name="E", max_hp=50, current_hp=50, block=0,
        intent=Intent(IntentType.ATTACK, enemy_attack),
    )
    return CombatState(
        player=Player(name="P", max_hp=100, current_hp=player_hp,
                      block=player_block, luck=player_luck),
        enemies=[enemy],
        hand=Hand(cards=list(hand_cards or [])),
        draw_pile=DrawPile(cards=draw_pile),
        discard_pile=DiscardPile(cards=[]),
        mana=Mana(current=mana_current, maximum=mana_max),
        relics=relics or [],
    )


# ---------------------------------------------------------------------------
# draw_opening_hand
# ---------------------------------------------------------------------------

class TestDrawOpeningHand:
    def test_draws_five_cards_no_relics(self):
        state = _make_state(draw_count=20)
        draw_opening_hand(state)
        assert state.hand.count == 5

    def test_draws_six_with_broken_totem(self):
        state = _make_state(draw_count=20, relics=[_relic(RelicTag.BROKEN_TOTEM)])
        draw_opening_hand(state)
        assert state.hand.count == 6

    def test_draws_seven_with_two_totems(self):
        relics = [_relic(RelicTag.BROKEN_TOTEM), _relic(RelicTag.BROKEN_TOTEM)]
        state = _make_state(draw_count=20, relics=relics)
        draw_opening_hand(state)
        assert state.hand.count == 7

    def test_inactive_totem_no_extra(self):
        state = _make_state(draw_count=20, relics=[_relic(RelicTag.BROKEN_TOTEM, active=False)])
        draw_opening_hand(state)
        assert state.hand.count == 5

    def test_combat_amulet_increases_max_mana(self):
        state = _make_state(relics=[_relic(RelicTag.COMBAT_AMULET)])
        draw_opening_hand(state)
        assert state.mana.maximum == 4
        assert state.mana.current == 4

    def test_two_amulets_double_bonus(self):
        relics = [_relic(RelicTag.COMBAT_AMULET), _relic(RelicTag.COMBAT_AMULET)]
        state = _make_state(relics=relics)
        draw_opening_hand(state)
        assert state.mana.maximum == 5

    def test_inactive_amulet_no_mana_bonus(self):
        state = _make_state(relics=[_relic(RelicTag.COMBAT_AMULET, active=False)])
        draw_opening_hand(state)
        assert state.mana.maximum == 3

    def test_stops_when_draw_pile_empty(self):
        state = _make_state(draw_count=3)
        draw_opening_hand(state)
        assert state.hand.count == 3  # only 3 available

    def test_uses_discard_when_draw_empty(self):
        state = _make_state(draw_count=2)
        state.discard_pile.cards = [_card("dc1"), _card("dc2"), _card("dc3")]
        draw_opening_hand(state)
        assert state.hand.count == 5

    def test_stops_when_both_piles_empty(self):
        state = _make_state(draw_count=0)
        draw_opening_hand(state)
        assert state.hand.count == 0

    def test_does_not_exceed_hand_limit(self):
        # Hand max is 10; draw 6 with totem, but deck has 20 → capped at 6
        state = _make_state(draw_count=20, relics=[_relic(RelicTag.BROKEN_TOTEM)])
        draw_opening_hand(state)
        assert state.hand.count == 6
        assert state.hand.count <= state.hand.max_size


# ---------------------------------------------------------------------------
# end_player_turn
# ---------------------------------------------------------------------------

class TestEndPlayerTurn:
    def test_hand_discarded(self):
        hand = [_card("h1"), _card("h2"), _card("h3")]
        state = _make_state(hand_cards=hand)
        end_player_turn(state)
        # All hand cards should be in discard (or reshuffled into draw for new draw)
        # After end_turn, new hand is drawn — original 3 cards discarded, 5 new drawn
        # We just verify the final hand has 5 new cards
        assert state.hand.count == 5

    def test_player_block_resets_at_start_of_next_turn(self):
        # Block resets at the START of the new player turn (after enemies act)
        state = _make_state(player_block=10)
        state.player.block = 10
        end_player_turn(state)
        # After enemies act and new turn begins, block is 0
        assert state.player.block == 0

    def test_turn_incremented(self):
        state = _make_state()
        assert state.turn == 1
        end_player_turn(state)
        assert state.turn == 2

    def test_mana_refilled(self):
        state = _make_state(mana_current=0, mana_max=3)
        end_player_turn(state)
        assert state.mana.current == 3

    def test_enemy_deals_damage(self):
        state = _make_state(player_hp=80, enemy_attack=10)
        end_player_turn(state)
        # player block was 0, enemy attacks for 10
        assert state.player.current_hp == 70

    def test_player_block_absorbs_enemy_attack(self):
        # Block earned during the player's turn protects against enemy attacks
        state = _make_state(player_hp=80, player_block=5, enemy_attack=10)
        state.player.block = 5
        end_player_turn(state)
        # 5 block absorbs 5 of the 10 damage → takes 5 damage
        assert state.player.current_hp == 75

    def test_player_block_fully_absorbs_weak_attack(self):
        state = _make_state(player_hp=80, player_block=15, enemy_attack=10)
        state.player.block = 15
        end_player_turn(state)
        # 15 block fully absorbs 10 damage → no HP loss
        assert state.player.current_hp == 80

    def test_draw_respects_broken_totem_each_turn(self):
        state = _make_state(draw_count=20, relics=[_relic(RelicTag.BROKEN_TOTEM)])
        end_player_turn(state)
        assert state.hand.count == 6  # 5 + 1 from totem

    def test_spectral_shield_triggers_on_fatal_hit(self):
        state = _make_state(player_hp=1, enemy_attack=999,
                            relics=[_relic(RelicTag.SPECTRAL_SHIELD)])
        end_player_turn(state)
        assert state.player.current_hp == 1
        assert not state.relics[0].is_active  # consumed

    def test_spectral_shield_not_triggered_if_survived(self):
        state = _make_state(player_hp=80, enemy_attack=10,
                            relics=[_relic(RelicTag.SPECTRAL_SHIELD)])
        end_player_turn(state)
        assert state.player.current_hp == 70
        assert state.relics[0].is_active  # not triggered

    def test_dead_enemies_removed_after_turn(self):
        state = _make_state()
        state.enemies[0].current_hp = 0
        end_player_turn(state)
        assert len(state.enemies) == 0

    def test_draw_reshuffles_discard_when_pile_empty(self):
        # Draw pile starts at 3 cards; 5 needed → uses discard (3 more)
        state = _make_state(draw_count=3)
        state.discard_pile.cards = [_card("dc1"), _card("dc2"), _card("dc3")]
        end_player_turn(state)
        assert state.hand.count == 5

    def test_multiple_turns_consistent_draw(self):
        state = _make_state(draw_count=20)
        for _ in range(3):
            end_player_turn(state)
            assert state.hand.count == 5


# ---------------------------------------------------------------------------
# Luck bonus draw
# ---------------------------------------------------------------------------

class TestLuckBonus:
    def test_zero_luck_no_extra_draw(self):
        state = _make_state(draw_count=20, player_luck=0)
        draw_opening_hand(state)
        assert state.hand.count == 5

    def test_luck_4_no_extra_draw(self):
        state = _make_state(draw_count=20, player_luck=4)
        draw_opening_hand(state)
        assert state.hand.count == 5  # 4 // 5 == 0

    def test_luck_5_draws_one_extra(self):
        state = _make_state(draw_count=20, player_luck=5)
        draw_opening_hand(state)
        assert state.hand.count == 6  # 5 // 5 == 1

    def test_luck_10_draws_two_extra(self):
        state = _make_state(draw_count=20, player_luck=10)
        draw_opening_hand(state)
        assert state.hand.count == 7  # 10 // 5 == 2

    def test_luck_bonus_also_applies_each_turn(self):
        state = _make_state(draw_count=20, player_luck=5)
        end_player_turn(state)
        assert state.hand.count == 6

    def test_luck_100_capped_by_hand_max(self):
        state = _make_state(draw_count=50, player_luck=100)
        draw_opening_hand(state)
        assert state.hand.count == state.hand.max_size  # 5+20=25 > max → capped
        assert state.hand.count <= state.hand.max_size
