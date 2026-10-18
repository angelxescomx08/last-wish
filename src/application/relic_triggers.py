"""Combat triggers of the relics added on 2026-10-17 (``docs/reliquias.xlsx``).

``relic_effects`` holds the older query functions; this module groups the new relics by
the moment they act, so the turn pipeline and ``play_card`` call one function per moment:

* ``combat_start`` / ``opening_hand_drawn`` — ``end_turn.draw_opening_hand``.
* ``turn_start`` / ``turn_end`` — ``end_turn._begin_player_turn`` / ``_discard_hand``.
* ``extra_damage`` / ``extra_block`` — added by ``play_card._resolve_cast`` (and shown by the
  combat screen through ``damage_preview`` / ``block_preview``).
* ``after_play`` — once per play, after the last cast (counters, Escalera, Ampolla…).
* ``check_deaths`` — after plays and during the enemy turn (Diente de León, Collar de
  Colmillos, Corona del Rey Ladrón).
* ``enemy_hit`` / ``after_enemy_hit`` — Bandera Blanca, Capucha de Sombras, Corona de Espinas.
* ``element_bonus`` — Yesca, Concha Marina, Piedra Pómez, Pluma de Grifo, Sombrero Puntiagudo.
* ``on_reshuffle`` — Pila Ordenada, Baraja Mágica.

Golden relics double their numbers (``relic_total``). No pygame.
"""
from __future__ import annotations

import random

from src.domain.card import Card, CardType
from src.domain.combat import CombatState
from src.domain.elements import Element, apply_element
from src.domain.entities import (FROZEN, MARKED, POISON, VULNERABLE, WEAK, Enemy, StatusEffect,
                                 add_status, enemy_hit_damage, status_stacks)
from src.domain.relic import RelicTag, relic_total

ELEMENT_RELICS: dict[Element, RelicTag] = {
    Element.FIRE: RelicTag.TINDER,
    Element.WATER: RelicTag.SEASHELL,
    Element.EARTH: RelicTag.PUMICE,
    Element.AIR: RelicTag.GRIFFIN_FEATHER,
}
MOLTEN_IRON_CAP: int = 15        # Hierro Fundido: max block added to the first attack
STAIR_LENGTH: int = 3            # Escalera: rising cards needed
MANA_VIAL_CARDS: int = 4         # Ampolla de Maná: cards played before it can refill
WATCH_CARDS: int = 6             # Reloj de Bolsillo Robado
GRIMOIRE_VOIDS: int = 3          # Grimorio en Blanco: Vacíos per card drawn
WAR_DRUM_ENDURES: int = 3        # Tambor de Guerra: Aguantes per Fuerza


SPYGLASS_CARDS: int = 3          # Catalejo: cards of the draw pile you can see


def spyglass_cards(state: CombatState) -> list[str]:
    """Catalejo: names of the next cards you will draw (top first); empty without the relic."""
    n = _n(state, RelicTag.SPYGLASS, SPYGLASS_CARDS)
    return [c.name for c in reversed(state.draw_pile.cards[-n:])] if n else []


def _n(state: CombatState, tag: RelicTag, amount: int = 1) -> int:
    return relic_total(state.relics, tag, amount)


# ---------------------------------------------------------------------------
# Combat start
# ---------------------------------------------------------------------------

def combat_start(state: CombatState, rng: random.Random | None = None) -> None:
    """Before the opening hand is drawn (the draw pile is already shuffled)."""
    rng = rng or random
    alive = state.living_enemies()
    if alive and _n(state, RelicTag.VOTIVE_CANDLE):                     # Vela Votiva
        target = max(alive, key=lambda e: e.current_hp)
        add_status(target.status_effects, WEAK, _n(state, RelicTag.VOTIVE_CANDLE), is_buff=False)
    for _ in range(_n(state, RelicTag.SHACKLE)):                         # Grillete
        for e in alive:
            add_status(e.status_effects, VULNERABLE, 1, is_buff=False)
    normal = [e for e in alive if not (e.is_boss or e.is_elite)]
    if normal and _n(state, RelicTag.FROST_AMULET):                     # Amuleto de Escarcha
        target = rng.choice(normal)
        if status_stacks(target.status_effects, FROZEN) == 0:
            target.status_effects.append(StatusEffect(FROZEN, 1, False))
    if alive and _n(state, RelicTag.WILLOW_WAND):                       # Varita de Sauce
        apply_element(state, rng.choice(alive), Element.WATER, _n(state, RelicTag.WILLOW_WAND, 2))
    if alive and _n(state, RelicTag.FOLDING_KNIFE):                     # Navaja Plegable
        target = min(alive, key=lambda e: e.current_hp)
        add_status(target.status_effects, MARKED, _n(state, RelicTag.FOLDING_KNIFE, 2), is_buff=False)
    p = state.player
    if p.current_hp * 2 < p.max_hp:                                      # Pluma de Fénix
        state.heal_hero(_n(state, RelicTag.PHOENIX_FEATHER, 8))
    if p.current_hp >= p.max_hp and _n(state, RelicTag.BLOOD_SKIN):     # Odre de Sangre
        lost = min(5, p.current_hp - 1)
        p.current_hp -= lost
        state.gain_strength(_n(state, RelicTag.BLOOD_SKIN, 2))
    if any(e.is_boss for e in alive):                                    # Corazón Desbocado
        for _ in range(_n(state, RelicTag.RACING_HEART)):
            state.gain_strength(state.hero_strength)
    curse = _n(state, RelicTag.CURSED_CONTRACT)                         # Contrato Maldito
    if curse:
        state.mana.maximum += curse
        state.mana.refill()
        state.add_status_cards("status_herida", curse, "draw", rng)
    _put_innate_on_top(state)                                            # Cartas Marcadas


def _put_innate_on_top(state: CombatState) -> None:
    """Innate cards (Cartas Marcadas) go to the top of the draw pile, so they are drawn first."""
    innate = [c for c in state.draw_pile.cards if c.innate]
    if innate:
        rest = [c for c in state.draw_pile.cards if not c.innate]
        state.draw_pile.cards = rest + innate          # draw_one pops from the end


def opening_hand_drawn(state: CombatState, rng: random.Random | None = None) -> None:
    """Right after the opening hand is in."""
    rng = rng or random
    hand = [c for c in state.hand.cards if c.chroma is None and c.card_type is not CardType.STATUS]
    if hand and _n(state, RelicTag.D20):                                 # Dado de Veinte Caras
        from src.domain.chroma import Chroma
        rng.choice(hand).chroma = Chroma.GOLDEN
    if state.singular_deck and _n(state, RelicTag.SINGULAR_LOCKET):      # Medallón Singular
        from src.domain.card_pool import hidden_dagger
        for _ in range(_n(state, RelicTag.SINGULAR_LOCKET)):
            if not state.hand.is_full:
                dagger = hidden_dagger()
                dagger.play_on_draw = False          # in hand: you play it yourself
                state.hand.cards.append(dagger)
    marbles = _n(state, RelicTag.MARBLE_BAG)                             # Bolsa de Canicas
    if marbles and state.discard_random(rng) is not None:
        state.player.block += 3 * marbles


# ---------------------------------------------------------------------------
# Turns
# ---------------------------------------------------------------------------

def keeps_block(state: CombatState) -> bool:
    """Ancla: the block of the first turn survives into the second."""
    return state.turn == 1 and state.has_relic(RelicTag.ANCHOR)


def block_kept_at_turn_start(state: CombatState) -> int:
    """Block left when a turn starts without Capa de Sombras (Rodela Gastada: half)."""
    if state.has_relic(RelicTag.WORN_ROUNDEL):
        return state.player.block // 2
    return 0


def turn_start(state: CombatState) -> int:
    """After block reset, counters and mana refill. Returns extra cards to draw this turn."""
    state.mana.current += state.stored_mana                               # Batería Arcana
    state.stored_mana = 0
    if state.player.block == 0:                                           # Brasero
        state.turn_attack_bonus += _n(state, RelicTag.BRAZIER, 3)
    banner = _n(state, RelicTag.LEGION_BANNER)                            # Estandarte de la Legión
    if banner and state.player.block > incoming_damage(state):
        state.gain_strength(banner)
    extra = 0
    if state.turn % 4 == 0:                                               # Reloj de Arena
        extra += _n(state, RelicTag.HOURGLASS)
    return extra


def incoming_damage(state: CombatState) -> int:
    """Total damage the living enemies announce for their next turn."""
    total = 0
    for e in state.living_enemies():
        if e.intent.intent_type.name == "ATTACK":
            total += enemy_hit_damage(e, state.player) * max(1, e.intent.hits)
    return total


def turn_end(state: CombatState) -> None:
    """End of the hero's turn, before the hand is discarded."""
    p = state.player
    played = state.cards_played_this_turn
    if played >= 3:                                                        # Saco de Arena
        p.block += _n(state, RelicTag.SANDBAG, 4)
    if played == 2:                                                        # Ficha de Ajedrez
        p.block += _n(state, RelicTag.CHESS_PIECE, 5)
    if state.attacks_this_turn and state.attacks_this_turn == state.skills_this_turn:
        p.block += _n(state, RelicTag.BALANCE_BRACELET, 5)                 # Brazalete del Equilibrio
    p.block += state.mana.current * _n(state, RelicTag.EMPTY_BOWL, 3)     # Cuenco Vacío
    if state.mana.current > 0:                                             # Batería Arcana
        state.stored_mana = min(state.mana.current, _n(state, RelicTag.ARCANE_BATTERY))
    if state.hp_lost_this_turn > 0:                                        # Venda de Campaña
        state.heal_hero(_n(state, RelicTag.FIELD_BANDAGE, 2))
    if p.block == 0:                                                       # Capa Raída
        p.block += _n(state, RelicTag.RAGGED_CAPE, 3)


def marked_wears_off(state: CombatState, enemy: Enemy) -> bool:
    """Marcado is cleared at the end of your turn; Hilo de Seda Negra lets it last one more."""
    if status_stacks(enemy.status_effects, MARKED) <= 0:
        state.marked_seen.discard(id(enemy))
        return False
    if not state.has_relic(RelicTag.BLACK_SILK):
        return True
    if id(enemy) in state.marked_seen:
        state.marked_seen.discard(id(enemy))
        return True
    state.marked_seen.add(id(enemy))
    return False


def reset_turn(state: CombatState) -> None:
    """Per-turn counters of these relics (with ``end_turn._reset_turn_counters``)."""
    state.skills_this_turn = 0
    state.combos_this_turn = 0
    state.voids_this_turn = 0
    state.fury_attack_done = False
    state.turn_attack_bonus = 0
    state.stair_last_cost = -1
    state.stair_len = 0
    state.stair_done = False
    state.mana_vial_used = False
    state.watch_used = False
    state.heal_draw_used = False
    state.elements_this_turn = set()
    state.ring_used = False
    state.spoil_mist_used = False


# ---------------------------------------------------------------------------
# Card damage / block
# ---------------------------------------------------------------------------

def extra_damage(state: CombatState, card: Card, enemy: Enemy | None, *,
                 fury: bool = False, combo: bool = False) -> int:
    """Damage the relics add to a card's main hit right now."""
    bonus = state.turn_attack_bonus
    if card.card_type is CardType.ATTACK:
        if not state.attack_played_combat:                                 # Piedra de Afilar
            bonus += _n(state, RelicTag.WHETSTONE, 6)
        if state.turn == 3:                                                 # Cuerno de Guerra
            bonus += _n(state, RelicTag.WAR_HORN, 4)
        if state.turn % 2 == 0:                                             # Péndulo
            bonus += _n(state, RelicTag.PENDULUM, 2)
        if state.player.current_hp * 2 < state.player.max_hp:              # Yelmo del Berserker
            bonus += _n(state, RelicTag.BERSERKER_HELM, 3)
        if state.attacks_this_turn == 0 and _n(state, RelicTag.MOLTEN_IRON):   # Hierro Fundido
            bonus += min(state.player.block, MOLTEN_IRON_CAP * _n(state, RelicTag.MOLTEN_IRON))
        if fury and not state.fury_attack_done:                             # Hacha Mellada
            bonus += _n(state, RelicTag.NOTCHED_AXE, 4)
    if enemy is not None and enemy.block > 0:                                # Lanza de Ruptura
        bonus += _n(state, RelicTag.BREACH_SPEAR, 3)
    if card.is_upgraded:                                                     # Piedra de Toque
        bonus += _n(state, RelicTag.TOUCHSTONE, 2)
    if combo and state.combos_this_turn == 2:                               # Máscara de Arlequín
        bonus += _n(state, RelicTag.HARLEQUIN_MASK, 5)
    return bonus


def extra_block(state: CombatState, card: Card) -> int:
    """Block the relics add to a card that gives block."""
    p = state.player
    bonus = 0
    if state.turn == 1:                                                      # Lámpara de Aceite
        bonus += _n(state, RelicTag.OIL_LAMP, 3)
    if state.turn % 2 == 1:                                                  # Péndulo
        bonus += _n(state, RelicTag.PENDULUM, 2)
    bonus += (max(0, p.max_hp - p.current_hp) // 10) * _n(state, RelicTag.DENTED_PLATE)   # Peto Abollado
    if card.endure_effects():                                                # Muñequera
        bonus += _n(state, RelicTag.WRISTGUARD, 2)
    if card.is_upgraded:                                                     # Piedra de Toque
        bonus += _n(state, RelicTag.TOUCHSTONE, 2)
    return bonus


# ---------------------------------------------------------------------------
# After a play
# ---------------------------------------------------------------------------

def after_play(state: CombatState, card: Card, cost: int, *, combo: bool, void: bool,
               fury: bool, endure: bool, spoil: bool, target: int | None) -> None:
    """Once per play, after the last cast; counters are this play's (before the increment)."""
    is_attack = card.card_type is CardType.ATTACK
    if is_attack:
        state.attack_played_combat = True
        if fury:
            state.fury_attack_done = True
    if card.card_type is CardType.SKILL:
        state.skill_played_combat = True
        state.skills_this_turn += 1
    if combo:
        if state.combos_this_turn == 0 and target is not None and target < len(state.enemies):
            state.poison_enemy(state.enemies[target], _n(state, RelicTag.POISONED_SCARF, 2))
        state.combos_this_turn += 1
    if endure:
        state.endures += 1
        if state.endures % WAR_DRUM_ENDURES == 0:                           # Tambor de Guerra
            state.gain_strength(_n(state, RelicTag.WAR_DRUM))
    if void:
        if state.voids_this_turn == 0:                                       # Reloj de Agua
            state.player.block += _n(state, RelicTag.WATER_CLOCK, 4)
        state.voids_this_turn += 1
        state.voids_combat += 1
        if state.voids_combat % GRIMOIRE_VOIDS == 0:                         # Grimorio en Blanco
            state.pending_draws += _n(state, RelicTag.BLANK_GRIMOIRE)
        if card.cost >= 3:                                                   # Fuente Menor
            state.mana.gain(_n(state, RelicTag.LESSER_FOUNT))
    if spoil and not state.spoil_mist_used and _n(state, RelicTag.MIST_FLASK):   # Frasco de Neblina
        alive = state.living_enemies()
        if alive:
            state.spoil_mist_used = True
            add_status(max(alive, key=lambda e: e.current_hp).status_effects, WEAK,
                       _n(state, RelicTag.MIST_FLASK), is_buff=False)
    _stairway(state, cost)
    played = state.cards_played_this_turn + 1
    if (played >= MANA_VIAL_CARDS and state.mana.current == 0 and not state.mana_vial_used
            and _n(state, RelicTag.MANA_VIAL)):                              # Ampolla de Maná
        state.mana_vial_used = True
        state.mana.gain(_n(state, RelicTag.MANA_VIAL))
    if played >= WATCH_CARDS and not state.watch_used and _n(state, RelicTag.STOLEN_WATCH):
        state.watch_used = True                                              # Reloj de Bolsillo Robado
        state.next_card_discount = 99
    _ring_of_four(state)


def _stairway(state: CombatState, cost: int) -> None:
    """Escalera: three cards in a row, each costing 1 more than the one before."""
    if state.stair_len > 0 and cost == state.stair_last_cost + 1:
        state.stair_len += 1
    else:
        state.stair_len = 1
    state.stair_last_cost = cost
    stairs = _n(state, RelicTag.STAIRWAY)
    if stairs and state.stair_len >= STAIR_LENGTH and not state.stair_done:
        state.stair_done = True
        state.player.attack_bonus += stairs
        state.player.dexterity += stairs


def note_element(state: CombatState, element: Element) -> None:
    """An element the hero applied this turn (Anillo de los Cuatro)."""
    state.elements_this_turn.add(element)


def _ring_of_four(state: CombatState) -> None:
    ring = _n(state, RelicTag.RING_OF_FOUR)
    if ring and not state.ring_used and len(state.elements_this_turn) >= len(Element):
        state.ring_used = True
        state.mana.maximum += ring


def element_bonus(state: CombatState, card: Card | None, element: Element) -> int:
    """Extra stacks a card applies of ``element`` (one per relic of that element; Sombrero
    Puntiagudo: +1 on 0-cost cards)."""
    bonus = _n(state, ELEMENT_RELICS[element])
    if card is not None and card.cost == 0:
        bonus += _n(state, RelicTag.POINTY_HAT)
    return bonus


# ---------------------------------------------------------------------------
# Deaths, enemy hits, reshuffles
# ---------------------------------------------------------------------------

def check_deaths(state: CombatState) -> None:
    """Relics that act once per enemy death (call before dead enemies leave the list)."""
    for e in state.enemies:
        if e.is_alive or id(e) in state.dead_ids:
            continue
        state.dead_ids.add(id(e))
        state.heal_hero(_n(state, RelicTag.DANDELION, 3))                   # Diente de León
        state.gain_strength(_n(state, RelicTag.FANG_NECKLACE))             # Collar de Colmillos
        if status_stacks(e.status_effects, POISON) > 0:                     # Corona del Rey Ladrón
            state.next_card_discount += _n(state, RelicTag.THIEF_KING_CROWN)


def enemy_hit(state: CombatState, dmg: int) -> int:
    """Damage of an enemy hit after Bandera Blanca (first hit of the combat −4) and Capucha
    de Sombras (first hit of the first turn: half)."""
    if dmg <= 0:
        return dmg
    if not state.first_hit_taken:
        state.first_hit_taken = True
        dmg = max(0, dmg - _n(state, RelicTag.WHITE_FLAG, 4))
    if state.turn == 1 and not state.hidden_first_attack and state.has_relic(RelicTag.CAPUCHE):
        state.hidden_first_attack = True
        dmg //= 2
    return dmg


def after_enemy_hit(state: CombatState, enemy: Enemy) -> None:
    """Corona de Espinas: the attacker takes 2 damage per hit."""
    thorns = _n(state, RelicTag.THORN_CROWN, 2)
    if thorns and enemy.is_alive:
        from src.domain.entities import deal_damage
        deal_damage(enemy, thorns)


def blocks_debuff(state: CombatState, name: str) -> bool:
    """An enemy debuff does not land: Antídoto (Veneno) or Vendas del Monje (the first one)."""
    if name == POISON and state.has_relic(RelicTag.ANTIDOTE):
        return True
    if not state.debuff_ignored and state.has_relic(RelicTag.MONK_WRAPS):
        state.debuff_ignored = True
        return True
    return False


def on_reshuffle(state: CombatState) -> int:
    """The discard pile was shuffled into the draw pile. Returns extra cards to draw."""
    state.player.block += _n(state, RelicTag.TIDY_PILE, 4)                  # Pila Ordenada
    if not state.reshuffled:                                                # Baraja Mágica
        state.reshuffled = True
        return _n(state, RelicTag.MAGIC_DECK)
    return 0
