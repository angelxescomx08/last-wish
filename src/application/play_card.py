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

    if dmg > 0 and target_enemy_index is None:
        return PlayResult(False, "Esta carta necesita un objetivo")

    # Apply damage to target enemy (bonus from Orbe de Fuego added to attack cards)
    if dmg > 0 and target_enemy_index is not None:
        if target_enemy_index >= len(state.enemies):
            return PlayResult(False, "Objetivo inválido")
        enemy = state.enemies[target_enemy_index]
        if not enemy.is_alive:
            return PlayResult(False, "Ese enemigo ya está derrotado")
        effective_dmg = dmg + relic_effects.extra_attack_damage(state.relics)
        absorbed = min(enemy.block, effective_dmg)
        enemy.block = max(0, enemy.block - absorbed)
        enemy.current_hp = max(0, enemy.current_hp - (effective_dmg - absorbed))

    # Apply block to player
    if blk > 0:
        state.player.block += blk

    # Compute extra draws before mutating the hand
    draw_count = sum(fx.draw for fx in card.all_effects())

    # Spend mana and move card out of hand
    state.mana.spend(card.cost)
    played = state.hand.cards.pop(card_index)

    # Powers stay on the field; everything else goes to discard
    if played.card_type == CardType.POWER:
        state.active_powers.append(played)
    else:
        state.discard_pile.cards.append(played)

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
