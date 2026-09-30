from __future__ import annotations

import random

from src.application import relic_effects
from src.application.drawing import draw_cards
from src.domain.combat import CombatState
from src.domain.entities import WEAK, Enemy, Intent, IntentType, StatusEffect, add_status, tick_status, weakened
from src.domain.tuning import TUNING

_HAND_DRAW_SIZE: int = 5
ENEMY_DEBUFF_TURNS: int = 2    # an enemy DEBUFF makes the hero Débil for this many turns


def cards_per_turn(state: CombatState) -> int:
    """Nominal turn draw; actual draws are limited by deck and hand capacity."""
    return _HAND_DRAW_SIZE + relic_effects.extra_draw_per_turn(state.relics)


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
    draw_cards(state, cards_per_turn(state))


# ---------------------------------------------------------------------------
# Pipeline steps
# ---------------------------------------------------------------------------

def _discard_hand(state: CombatState) -> None:
    state.discard_pile.cards.extend(state.hand.cards)
    state.hand.cards.clear()
    # End of the hero's turn: one turn of Débil wears off; "this turn" bonuses expire.
    state.player.status_effects = tick_status(state.player.status_effects, WEAK)
    state.next_card_discount = 0
    state.next_damage_bonus = 0


def _run_enemy_turn(state: CombatState) -> None:
    for enemy in state.enemies:
        if enemy.is_alive:
            _tick_status_effects(enemy)   # poison/burn deal damage before acting
            if not enemy.is_alive:        # killed by status? skip action
                continue
            enemy.block = 0              # reset block at the START of each enemy's action
            _execute_intent(state, enemy)
            enemy.status_effects = tick_status(enemy.status_effects, WEAK)   # lasts its turn

    # Remove defeated enemies before rolling new intents
    state.enemies = [e for e in state.enemies if e.is_alive]

    for enemy in state.enemies:
        enemy.intent = _roll_intent(enemy)


def _execute_intent(state: CombatState, enemy: Enemy) -> None:
    match enemy.intent.intent_type:
        case IntentType.ATTACK:
            dmg = weakened(enemy.intent.value, enemy.status_effects)
            absorbed = min(state.player.block, dmg)
            state.player.block = max(0, state.player.block - absorbed)
            if not TUNING.invincible:          # Pruebas: invincible hero
                state.player.current_hp = max(0, state.player.current_hp - (dmg - absorbed))
            relic_effects.try_revive(state)

        case IntentType.BLOCK:
            enemy.block += enemy.intent.value

        case IntentType.BUFF:
            # Buff: ramp up damage for the following attack
            enemy.intent = Intent(IntentType.ATTACK, random.randint(10, 20))

        case IntentType.DEBUFF:
            # The hero is weakened for their next 2 turns (Panacea: immune).
            if not relic_effects.immune_to_debuffs(state.relics):
                add_status(state.player.status_effects, WEAK, ENEMY_DEBUFF_TURNS, is_buff=False)

        case IntentType.UNKNOWN:
            pass


def _tick_status_effects(enemy: Enemy) -> None:
    """Apply per-turn status effects and reduce their stacks by 1."""
    for se in enemy.status_effects:
        if se.name == "Veneno":
            enemy.current_hp = max(0, enemy.current_hp - se.stacks)
            se.stacks -= 1
    enemy.status_effects = [se for se in enemy.status_effects if se.stacks > 0]


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
    state.cards_played_this_turn = 0  # Combo needs a card played earlier this turn
    state.mana.maximum += relic_effects.max_mana_per_turn(state.relics)   # Fuente Eterna
    state.mana.refill()
    state.selected_card_index = None
    state.targeted_enemy_index = None
    _trigger_powers(state)
    draw_cards(state, cards_per_turn(state))


def _trigger_powers(state: CombatState) -> None:
    """Powers in play with an ``on_turn_start`` effect act (golden powers: twice)."""
    for power in list(state.active_powers):
        for fx in power.all_effects():
            if fx.on_turn_start is not None:
                for _ in range(power.casts()):
                    fx.on_turn_start(state)
