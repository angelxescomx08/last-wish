from __future__ import annotations

import random

from src.application import relic_effects
from src.domain.combat import CombatState
from src.domain.entities import Enemy, Intent, IntentType

_HAND_DRAW_SIZE: int = 5


def end_player_turn(state: CombatState) -> None:
    """Full end-of-turn pipeline: discard → enemies act → new player turn.

    Block resets at the START of the player's next turn (inside
    _begin_player_turn), so block accumulated this turn absorbs enemy attacks.
    """
    _discard_hand(state)
    _run_enemy_turn(state)
    _begin_player_turn(state)


def draw_opening_hand(state: CombatState) -> None:
    """Apply combat-start relic effects and draw the opening hand."""
    random.shuffle(state.draw_pile.cards)
    bonus_mana = relic_effects.bonus_starting_mana(state.relics)
    if bonus_mana > 0:
        state.mana.maximum += bonus_mana
        state.mana.refill()
    count = (
        _HAND_DRAW_SIZE
        + relic_effects.extra_draw_per_turn(state.relics)
        + state.player.luck // 5
    )
    _draw_cards(state, count)


# ---------------------------------------------------------------------------
# Pipeline steps
# ---------------------------------------------------------------------------

def _discard_hand(state: CombatState) -> None:
    state.discard_pile.cards.extend(state.hand.cards)
    state.hand.cards.clear()


def _run_enemy_turn(state: CombatState) -> None:
    for enemy in state.enemies:
        if enemy.is_alive:
            enemy.block = 0         # reset block at the START of each enemy's action
            _execute_intent(state, enemy)

    # Remove defeated enemies before rolling new intents
    state.enemies = [e for e in state.enemies if e.is_alive]

    for enemy in state.enemies:
        enemy.intent = _roll_intent(enemy)


def _execute_intent(state: CombatState, enemy: Enemy) -> None:
    match enemy.intent.intent_type:
        case IntentType.ATTACK:
            dmg = enemy.intent.value
            absorbed = min(state.player.block, dmg)
            state.player.block = max(0, state.player.block - absorbed)
            state.player.current_hp = max(0, state.player.current_hp - (dmg - absorbed))
            relic_effects.try_spectral_shield(state)

        case IntentType.BLOCK:
            enemy.block += enemy.intent.value

        case IntentType.BUFF:
            # Buff: ramp up damage for the following attack
            enemy.intent = Intent(IntentType.ATTACK, random.randint(10, 20))

        case IntentType.DEBUFF:
            pass

        case IntentType.UNKNOWN:
            pass


def _roll_intent(enemy: Enemy) -> Intent:
    """Simple weighted random intent for the next turn."""
    roll = random.random()
    if roll < 0.55:
        return Intent(IntentType.ATTACK, random.randint(5, 15))
    elif roll < 0.80:
        return Intent(IntentType.BLOCK, random.randint(4, 10))
    elif roll < 0.92:
        return Intent(IntentType.BUFF, 0)
    else:
        return Intent(IntentType.DEBUFF, 0)


def _begin_player_turn(state: CombatState) -> None:
    state.player.block = 0           # block resets at the START of the new turn
    state.turn += 1
    state.mana.refill()
    state.selected_card_index = None
    state.targeted_enemy_index = None
    count = (
        _HAND_DRAW_SIZE
        + relic_effects.extra_draw_per_turn(state.relics)
        + state.player.luck // 5
    )
    _draw_cards(state, count)


def _draw_cards(state: CombatState, count: int) -> None:
    for _ in range(count):
        if state.draw_pile.count == 0:
            if state.discard_pile.count == 0:
                break
            state.draw_pile.cards = list(state.discard_pile.cards)
            random.shuffle(state.draw_pile.cards)
            state.discard_pile.cards.clear()

        if state.draw_pile.count > 0 and not state.hand.is_full:
            state.hand.cards.append(state.draw_pile.cards.pop())
