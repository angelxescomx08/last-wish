from __future__ import annotations

import random
from dataclasses import dataclass, field
from enum import Enum

from src.application import relic_effects
from src.application.drawing import draw_cards
from src.domain.card import Card, CardEffect, CardType
from src.domain.chroma import chroma_def
from src.domain.combat import CombatState
from src.domain.entities import deal_damage, frail, weakened


@dataclass
class PlayResult:
    success: bool
    message: str = ""
    combo: bool = False     # a Combo layer resolved
    singular: bool = False  # a Singular layer resolved
    void: bool = False      # a Vacío layer resolved
    spoil: bool = False     # a Despojo layer resolved
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
    return (card.total_damage(combo=True, singular=True, void=True, spoil=True) > 0
            or any(fx.needs_target for fx in card.active_effects(True, True, True, True)))


def target_kind(card: Card) -> TargetKind:
    if requires_target(card):
        return TargetKind.ENEMY
    if any(fx.hits_all_enemies for fx in card.active_effects(True, True, True, True)):
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
    if card.unplayable:
        return PlayResult(False, "Esta carta no se puede jugar")

    cost = state.card_cost(card)          # after discounts (next card / first card of the turn)
    if not state.mana.can_afford(cost):
        return PlayResult(False, "¡Sin maná suficiente!")

    # Keyword COMBO: combo layers resolve if another card was played earlier this turn.
    combo = state.combo_active and bool(card.combo_effects())
    # Keyword SINGULAR: its layers resolve if the starting deck had no repeated cards.
    singular = state.singular_ready(card)
    # Keyword VOID: checked before paying — its layers resolve if the card spends the last mana.
    void = state.void_ready(card)
    # Keyword SPOIL ("Despojo"): its layers resolve if a card was discarded earlier this turn.
    spoil = state.spoil_ready(card)

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
    if card.total_damage(combo, singular, void, spoil) > 0:
        damage_bonus, state.next_damage_bonus = state.next_damage_bonus, 0
    played = state.hand.cards.pop(card_index)
    if played.card_type == CardType.POWER:
        state.active_powers.append(played)
    elif played.exhaust:                  # "Agotar": gone for the rest of the combat
        state.exhausted.append(played)
    else:
        state.discard_pile.cards.append(played)

    # Sombra Gemela: the first Combo of the turn resolves its layer once more per copy.
    extra_combo = 0
    if combo and state.double_combo and not state.double_combo_used:
        extra_combo, state.double_combo_used = state.double_combo, True
    # Daga Partida: Despojo layers resolve once more (golden: twice more).
    extra_spoil = relic_effects.split_dagger_repeats(state.relics) if spoil else 0
    is_attack = card.card_type == CardType.ATTACK

    # A chroma casts the whole card several times (golden: twice), each cast complete.
    # Cadena Perfecta: every 5th card of the turn is cast once more per copy of the power.
    casts = card.casts()
    if state.echo_every_fifth and (state.cards_played_this_turn + 1) % 5 == 0:
        casts += state.echo_every_fifth
    cast_hits: list[list[int]] = []
    snap_hp: list[list[int]] = []
    snap_blk: list[list[int]] = []
    snap_player: list[int] = []
    for k in range(casts):
        before = [e.current_hp for e in state.enemies]
        target = _cast_target(state, card, target_enemy_index, needs_target)
        _resolve_cast(state, card, combo, target, singular, void, damage_bonus, spoil,
                      extra_combo, extra_spoil)
        if is_attack:
            relic_effects.poison_on_attack(state, target, first_attack=state.attacks_this_turn == 0)
            if state.execute_threshold:
                relic_effects.execute_wounded(state, before)
        if k == casts - 1:          # relic triggers once per play, shown with the last cast
            relic_effects.on_card_played(state, card, combo, spoil=spoil)
            relic_effects.spread_poison(state)
        cast_hits.append([b - e.current_hp for b, e in zip(before, state.enemies)])
        snap_hp.append([e.current_hp for e in state.enemies])
        snap_blk.append([e.block for e in state.enemies])
        snap_player.append(state.player.block)
    if card.chroma is not None and chroma_def(card.chroma).on_card_played is not None:
        chroma_def(card.chroma).on_card_played(state, played)

    state.selected_card_index = None
    state.targeted_enemy_index = None
    state.cards_played_this_turn += 1
    if is_attack:
        state.attacks_this_turn += 1
    if spoil:
        state.spoils_this_turn += 1
    relic_effects.settle_pickpocket(state)
    relic_effects.try_broken_clock(state)
    message = (f"Jugaste {played.name}" + (f" x{casts}" if casts > 1 else "")
               + (" — ¡Combo!" if combo else "") + (" — ¡Singular!" if singular else "")
               + (" — ¡Vacío!" if void else "") + (" — ¡Despojo!" if spoil else ""))
    return PlayResult(True, message, combo=combo, singular=singular, void=void, spoil=spoil,
                      casts=casts, cast_hits=cast_hits,
                      cast_enemy_hp=snap_hp, cast_enemy_block=snap_blk, cast_player_block=snap_player)


def _cast_target(state: CombatState, card: Card, target: int | None, needs_target: bool) -> int | None:
    """The chosen enemy; if it died during an earlier cast, another living enemy (or None)."""
    if not needs_target or target is None:
        return target
    if target < len(state.enemies) and state.enemies[target].is_alive:
        return target
    for i, e in enumerate(state.enemies):
        if e.is_alive:
            return i
    return None


def _resolve_cast(state: CombatState, card: Card, combo: bool, target: int | None,
                  singular: bool = False, void: bool = False, damage_bonus: int = 0,
                  spoil: bool = False, extra_combo: int = 0, extra_spoil: int = 0) -> None:
    """One full cast: damage (+ bonuses), block (+ dexterity), mana, on_play effects, draws.

    Damage = printed + relics + hero's attack bonus + ``damage_bonus`` (e.g. Afilar)
    (+ Pañuelo del Duelista when a Combo resolves), reduced by Débil if the hero has it.
    ``extra_combo`` / ``extra_spoil``: the Combo / Despojo layers resolve that many more
    times (Sombra Gemela / Daga Partida), with their raw printed values.
    """
    dmg = card.total_damage(combo, singular, void, spoil)
    blk = card.total_block(combo, singular, void, spoil)
    scarf = relic_effects.combo_scarf_bonus(state.relics) if combo else 0
    if dmg > 0 and target is not None and target < len(state.enemies) and state.enemies[target].is_alive:
        enemy = state.enemies[target]
        effective_dmg = weakened(dmg + relic_effects.extra_attack_damage(state.relics)
                                 + state.player.attack_bonus + damage_bonus + scarf,
                                 state.player.status_effects)
        deal_damage(enemy, effective_dmg)
    if blk > 0:                           # Frágil: 25 % less block from cards
        state.player.block += frail(blk + state.player.dexterity + scarf, state.player.status_effects)
    mana_gain = card.total_mana_gain(combo, singular, void, spoil)
    if mana_gain > 0:
        state.mana.gain(mana_gain)
    # on_play runs with the card out of hand and this cast's damage/block applied;
    # targeted_enemy_index is set so callbacks can read it.
    state.targeted_enemy_index = target
    for fx in card.active_effects(combo, singular, void, spoil):
        if fx.on_play is not None:
            fx.on_play(state)
    draws = card.total_draw(combo, singular, void, spoil) + state.pending_draws
    state.pending_draws = 0
    draw_cards(state, draws)
    for _ in range(extra_combo):
        _resolve_layers(state, card.combo_effects(), target)
    for _ in range(extra_spoil):
        _resolve_layers(state, card.spoil_effects(), target)


def _resolve_layers(state: CombatState, layers: list[CardEffect], target: int | None) -> None:
    """Resolve keyword layers once more on their own (printed values, no hero bonuses)."""
    if not layers:
        return
    dmg = sum(fx.damage.resolve() for fx in layers)
    if dmg > 0 and target is not None and target < len(state.enemies):
        deal_damage(state.enemies[target], dmg)
    blk = sum(fx.block.resolve() for fx in layers)
    if blk > 0:
        state.player.block += frail(blk, state.player.status_effects)
    mana = sum(fx.mana_gain for fx in layers)
    if mana > 0:
        state.mana.gain(mana)
    state.targeted_enemy_index = target
    for fx in layers:
        if fx.on_play is not None:
            fx.on_play(state)
    draws = sum(fx.draw for fx in layers) + state.pending_draws
    state.pending_draws = 0
    draw_cards(state, draws)
