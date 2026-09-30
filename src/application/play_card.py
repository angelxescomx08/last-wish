from __future__ import annotations

import random
from dataclasses import dataclass, field
from enum import Enum

from src.application import relic_effects
from src.application.drawing import draw_cards
from src.domain.card import Card, CardType
from src.domain.chroma import chroma_def
from src.domain.combat import CombatState
from src.domain.entities import weakened


@dataclass
class PlayResult:
    success: bool
    message: str = ""
    combo: bool = False     # a Combo layer resolved
    singular: bool = False  # a Singular layer resolved
    void: bool = False      # a Vacío layer resolved
    casts: int = 1          # times the card resolved (golden: 2)
    cast_hits: list[list[int]] = field(default_factory=list)   # per cast, HP lost by each enemy
    # Snapshots after each cast, so the UI can replay the casts one by one:
    cast_enemy_hp: list[list[int]] = field(default_factory=list)
    cast_enemy_block: list[list[int]] = field(default_factory=list)
    cast_player_block: list[int] = field(default_factory=list)


class TargetKind(Enum):
    """What a card acts on, so the UI can show it before the card is played."""
    ENEMY = "enemy"              # one enemy chosen by the player
    ALL_ENEMIES = "all_enemies"  # every living enemy, no choice
    SELF = "self"                # the hero (block, draw, mana, powers)


def requires_target(card: Card) -> bool:
    """True when the card must be played on one chosen enemy (combo layers included)."""
    return (card.total_damage(combo=True, singular=True, void=True) > 0
            or any(fx.needs_target for fx in card.active_effects(True, True, True)))


def target_kind(card: Card) -> TargetKind:
    if requires_target(card):
        return TargetKind.ENEMY
    if any(fx.hits_all_enemies for fx in card.active_effects(True, True, True)):
        return TargetKind.ALL_ENEMIES
    return TargetKind.SELF


def play_card(
    state: CombatState,
    card_index: int,
    target_enemy_index: int | None = None,
) -> PlayResult:
    """Execute playing a card from the hand onto the battlefield."""
    if card_index < 0 or card_index >= state.hand.count:
        return PlayResult(False, "Índice de carta inválido")

    card = state.hand.cards[card_index]

    cost = state.card_cost(card)          # after discounts (next card / first card of the turn)
    if not state.mana.can_afford(cost):
        return PlayResult(False, "¡Sin maná suficiente!")

    # Keyword COMBO: combo layers resolve if another card was played earlier this turn.
    combo = state.combo_active and bool(card.combo_effects())
    # Keyword SINGULAR: its layers resolve if the starting deck had no repeated cards.
    singular = state.singular_ready(card)
    # Keyword VOID: checked before paying — its layers resolve if the card spends the last mana.
    void = state.void_ready(card)

    # A card needs a target if it deals base damage OR any effect declares it.
    needs_target = requires_target(card)

    if needs_target and target_enemy_index is None:
        return PlayResult(False, "Esta carta necesita un objetivo")

    if needs_target and target_enemy_index is not None:
        if target_enemy_index >= len(state.enemies):
            return PlayResult(False, "Objetivo inválido")
        if not state.enemies[target_enemy_index].is_alive:
            return PlayResult(False, "Ese enemigo ya está derrotado")

    # Pay once, then move the card out of hand (powers stay on field; the rest is discarded).
    state.mana.spend(cost)
    state.next_card_discount = 0          # "the next card costs less" is used up by this card
    damage_bonus = 0
    if card.total_damage(combo, singular, void) > 0:
        damage_bonus, state.next_damage_bonus = state.next_damage_bonus, 0
    played = state.hand.cards.pop(card_index)
    if played.card_type == CardType.POWER:
        state.active_powers.append(played)
    else:
        state.discard_pile.cards.append(played)

    # A chroma casts the whole card several times (golden: twice), each cast complete.
    casts = card.casts()
    cast_hits: list[list[int]] = []
    snap_hp: list[list[int]] = []
    snap_blk: list[list[int]] = []
    snap_player: list[int] = []
    for k in range(casts):
        before = [e.current_hp for e in state.enemies]
        _resolve_cast(state, card, combo, target_enemy_index, singular, void, damage_bonus)
        if k == casts - 1:          # relic triggers once per play, shown with the last cast
            relic_effects.on_card_played(state, card, combo)
        cast_hits.append([b - e.current_hp for b, e in zip(before, state.enemies)])
        snap_hp.append([e.current_hp for e in state.enemies])
        snap_blk.append([e.block for e in state.enemies])
        snap_player.append(state.player.block)
    if card.chroma is not None and chroma_def(card.chroma).on_card_played is not None:
        chroma_def(card.chroma).on_card_played(state, played)

    state.selected_card_index = None
    state.targeted_enemy_index = None
    state.cards_played_this_turn += 1
    message = (f"Jugaste {played.name}" + (f" x{casts}" if casts > 1 else "")
               + (" — ¡Combo!" if combo else "") + (" — ¡Singular!" if singular else "")
               + (" — ¡Vacío!" if void else ""))
    return PlayResult(True, message, combo=combo, singular=singular, void=void, casts=casts, cast_hits=cast_hits,
                      cast_enemy_hp=snap_hp, cast_enemy_block=snap_blk, cast_player_block=snap_player)


def _resolve_cast(state: CombatState, card: Card, combo: bool, target: int | None,
                  singular: bool = False, void: bool = False, damage_bonus: int = 0) -> None:
    """One full cast: damage (+ bonuses), block (+ dexterity), mana, on_play effects, draws.

    Damage = printed + relics + hero's attack bonus + ``damage_bonus`` (e.g. Afilar),
    reduced by Débil if the hero has it.
    """
    dmg = card.total_damage(combo, singular, void)
    blk = card.total_block(combo, singular, void)
    if dmg > 0 and target is not None and target < len(state.enemies) and state.enemies[target].is_alive:
        enemy = state.enemies[target]
        effective_dmg = weakened(dmg + relic_effects.extra_attack_damage(state.relics)
                                 + state.player.attack_bonus + damage_bonus,
                                 state.player.status_effects)
        absorbed = min(enemy.block, effective_dmg)
        enemy.block = max(0, enemy.block - absorbed)
        enemy.current_hp = max(0, enemy.current_hp - (effective_dmg - absorbed))
    if blk > 0:
        state.player.block += blk + state.player.dexterity
    mana_gain = card.total_mana_gain(combo, singular, void)
    if mana_gain > 0:
        state.mana.gain(mana_gain)
    # on_play runs with the card out of hand and this cast's damage/block applied;
    # targeted_enemy_index is set so callbacks can read it.
    state.targeted_enemy_index = target
    for fx in card.active_effects(combo, singular, void):
        if fx.on_play is not None:
            fx.on_play(state)
    draw_cards(state, card.total_draw(combo, singular, void))
