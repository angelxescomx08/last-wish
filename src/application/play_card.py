from __future__ import annotations

import random
from dataclasses import dataclass

from src.application import relic_effects
from src.domain.card import CardType
from src.domain.combat import CombatState


@dataclass
class PlayResult:
    success: bool
    message: str = ""


def play_card(
    state: CombatState,
    card_index: int,
    target_enemy_index: int | None = None,
) -> PlayResult:
    """Execute playing a card from the hand onto the battlefield."""
    if card_index < 0 or card_index >= state.hand.count:
        return PlayResult(False, "Índice de carta inválido")

    card = state.hand.cards[card_index]

    if not state.mana.can_afford(card.cost):
        return PlayResult(False, "¡Sin maná suficiente!")

    dmg = card.total_damage()
    blk = card.total_block()

    # A card needs a target if it deals base damage OR any effect declares it.
    needs_target = dmg > 0 or any(fx.needs_target for fx in card.all_effects())

    if needs_target and target_enemy_index is None:
        return PlayResult(False, "Esta carta necesita un objetivo")

    if needs_target and target_enemy_index is not None:
        if target_enemy_index >= len(state.enemies):
            return PlayResult(False, "Objetivo inválido")
        if not state.enemies[target_enemy_index].is_alive:
            return PlayResult(False, "Ese enemigo ya está derrotado")

    # Apply damage to target enemy (relic bonus + character attack_bonus)
    if dmg > 0 and target_enemy_index is not None:
        enemy = state.enemies[target_enemy_index]
        effective_dmg = (
            dmg
            + relic_effects.extra_attack_damage(state.relics)
            + state.player.attack_bonus
        )
        absorbed = min(enemy.block, effective_dmg)
        enemy.block = max(0, enemy.block - absorbed)
        enemy.current_hp = max(0, enemy.current_hp - (effective_dmg - absorbed))

    # Apply block to player (character dexterity adds a flat bonus)
    if blk > 0:
        state.player.block += blk + state.player.dexterity

    # Compute extra draws before mutating the hand
    draw_count = sum(fx.draw for fx in card.all_effects())

    # Spend mana, then apply any mana refund from the card
    state.mana.spend(card.cost)
    mana_gain = sum(fx.mana_gain for fx in card.all_effects())
    if mana_gain > 0:
        state.mana.gain(mana_gain)

    # Move card out of hand (powers stay on field; everything else goes to discard)
    played = state.hand.cards.pop(card_index)
    if played.card_type == CardType.POWER:
        state.active_powers.append(played)
    else:
        state.discard_pile.cards.append(played)

    # Run custom on_play logic — state is fully updated at this point:
    # card is out of hand, mana spent, base damage/block applied.
    # targeted_enemy_index is set so callbacks can read it.
    state.targeted_enemy_index = target_enemy_index
    for fx in card.all_effects():
        if fx.on_play is not None:
            fx.on_play(state)

    # Draw bonus cards
    for _ in range(draw_count):
        _draw_one(state)

    state.selected_card_index = None
    state.targeted_enemy_index = None
    return PlayResult(True, f"Jugaste {played.name}")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _draw_one(state: CombatState) -> None:
    if state.draw_pile.count == 0:
        if state.discard_pile.count == 0:
            return
        state.draw_pile.cards = list(state.discard_pile.cards)
        random.shuffle(state.draw_pile.cards)
        state.discard_pile.cards.clear()

    if state.draw_pile.count > 0 and not state.hand.is_full:
        state.hand.cards.append(state.draw_pile.cards.pop())
