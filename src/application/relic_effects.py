from __future__ import annotations

import random

from src.application.drawing import draw_cards
from src.domain.card import Card, CardClass
from src.domain.keywords import Keyword
from src.domain.combat import CombatState
from src.domain.entities import POISON, add_status, deal_damage, status_stacks
from src.domain.relic import Relic, RelicTag, relic_total
from src.domain.tuning import TUNING


def _sum(relics: list[Relic], tag: RelicTag, amount: int) -> int:
    """``amount`` per active relic with ``tag``, scaled by its chroma (golden x2)."""
    return relic_total(relics, tag, amount)


def extra_draw_per_turn(relics: list[Relic]) -> int:
    """Extra cards drawn at the start of each player turn (Tótem Roto / Piedra de Energía: +1 each)."""
    return (_sum(relics, RelicTag.BROKEN_TOTEM, 1)
            + _sum(relics, RelicTag.ENERGY_STONE, 1)
            + TUNING.extra_draw)                      # Pruebas screen (0 in normal play)


def extra_attack_damage(relics: list[Relic]) -> int:
    """Flat bonus damage added to every attack card played (Orbe de Fuego: +2)."""
    return _sum(relics, RelicTag.FIRE_ORB, 2)


def bonus_starting_mana(relics: list[Relic]) -> int:
    """Extra mana maximum granted once at combat start (Amuleto de Combate: +1)."""
    return _sum(relics, RelicTag.COMBAT_AMULET, 1) + TUNING.extra_mana   # + Pruebas


def bonus_gold_reward(relics: list[Relic]) -> int:
    """Extra gold earned per combat victory (Anillo de Oro: +15 each)."""
    return _sum(relics, RelicTag.GOLD_RING, 15)


def post_combat_heal(relics: list[Relic]) -> int:
    """HP restored after each combat victory (Poción de Sangre: +8 each)."""
    return _sum(relics, RelicTag.BLOOD_POTION, 8)


def max_hp_bonus(relics: list[Relic]) -> int:
    """Permanent max-HP increase from relics (Corazón de Hierro: +15 each)."""
    return (_sum(relics, RelicTag.IRON_HEART, 15)
            + _sum(relics, RelicTag.VITALITY_AMULET, 10)
            + TUNING.extra_max_hp)                    # + Pruebas


def remove_duplicate_cards(deck: list[Card]) -> list[Card]:
    """One copy of each card id, in first-seen order. A golden copy is kept over a plain one."""
    kept: dict[str, Card] = {}
    for card in deck:
        best = kept.get(card.id)
        if best is None or (best.chroma is None and card.chroma is not None):
            kept[card.id] = card
    return list(kept.values())


def immune_to_debuffs(relics: list[Relic]) -> bool:
    """Panacea: enemy debuffs never land on the hero."""
    return any(r.is_active and r.tag == RelicTag.PANACEA for r in relics)


def max_mana_per_turn(relics: list[Relic]) -> int:
    """Fuente Eterna: +1 max mana at the start of each of your turns (golden: +2)."""
    return _sum(relics, RelicTag.ETERNAL_FOUNT, 1)


def compound_interest_percent(relics: list[Relic]) -> int:
    """Interés Compuesto: % of your total gold added every time you gain gold (golden: x2)."""
    return _sum(relics, RelicTag.COMPOUND_INTEREST, 10)


def luck_bonus(relics: list[Relic]) -> int:
    """Extra luck from relics (Trébol de Siete Hojas: +100, Herradura de Plata: +30)."""
    return (_sum(relics, RelicTag.SEVEN_LEAF_CLOVER, 100)
            + _sum(relics, RelicTag.SILVER_HORSESHOE, 30))


def on_card_played(state: CombatState, card: Card, combo: bool,
                   rng: random.Random | None = None, *, spoil: bool = False) -> None:
    """Relic triggers after a card fully resolves (once per play, not per golden cast).

    ``combo`` / ``spoil``: the card's Combo / Despojo layer resolved this play.
    Broche de Evasión: Combo → +1 block. Cuchillo Arrojadizo: Combo → 1 damage to a
    random living enemy (block absorbs it). Saco de Trapos: Despojo → +2 block.
    Garfio: the first Despojo of the turn draws 1. Golden relics: x2.
    """
    if combo and Keyword.COMBO in card.keywords():
        block = _sum(state.relics, RelicTag.EVASION_BROOCH, 1)
        if block:
            state.player.block += block
        damage = _sum(state.relics, RelicTag.THROWING_KNIFE, 1)
        if damage:
            state.hit_random_enemy(damage, rng)
    if spoil and Keyword.SPOIL in card.keywords():
        state.player.block += _sum(state.relics, RelicTag.RAG_SACK, 2)
        if state.spoils_this_turn == 0:
            draw_cards(state, _sum(state.relics, RelicTag.GRAPPLING_HOOK, 1))


# ---------------------------------------------------------------------------
# La Pícara: Combo, Despojo, daggers and poison
# ---------------------------------------------------------------------------

def combo_scarf_bonus(relics: list[Relic]) -> int:
    """Pañuelo del Duelista: a card whose Combo resolves gets +2 damage and +2 block
    (only on what it already does: damage if it deals damage, block if it gives block)."""
    return _sum(relics, RelicTag.DUELIST_SCARF, 2)


def split_dagger_repeats(relics: list[Relic]) -> int:
    """Daga Partida: extra times the Despojo layers resolve (golden: 2)."""
    return _sum(relics, RelicTag.SPLIT_DAGGER, 1)


def dagger_pouch_count(relics: list[Relic]) -> int:
    """Bolsa de Dagas: Dagas Ocultas shuffled into the draw pile at combat start."""
    return _sum(relics, RelicTag.DAGGER_POUCH, 2)


def torn_pocket_rummages(relics: list[Relic]) -> int:
    """Bolsillo Roto: after drawing your hand, discard 1 at random and draw 1 (golden: twice)."""
    return _sum(relics, RelicTag.TORN_POCKET, 1)


def poison_on_attack(state: CombatState, target: int | None, *, first_attack: bool,
                     rng: random.Random | None = None) -> int:
    """Poison put by an attack card: Frasco de Veneno (first attack of the turn: 1) and
    Hoja Envenenada (a charge: 2). Goes on the target, or a random living enemy for area
    attacks. Returns the stacks applied."""
    from src.domain.card_pool import POISON_BLADE_STACKS   # local: card_pool is a big leaf
    stacks = _sum(state.relics, RelicTag.POISON_VIAL, 1) if first_attack else 0
    if state.poison_attacks > 0:
        state.poison_attacks -= 1
        stacks += POISON_BLADE_STACKS
    if stacks <= 0:
        return 0
    enemy = None
    if target is not None and target < len(state.enemies) and state.enemies[target].is_alive:
        enemy = state.enemies[target]
    else:
        alive = state.living_enemies()
        enemy = (rng or random).choice(alive) if alive else None
    if enemy is None:
        return 0
    add_status(enemy.status_effects, POISON, stacks, is_buff=False)
    return stacks


def spread_poison(state: CombatState, rng: random.Random | None = None) -> None:
    """Colmillo de Víbora: a dead enemy's Veneno moves to a random living enemy (golden: x2)."""
    mult = _sum(state.relics, RelicTag.VIPER_FANG, 1)
    if not mult:
        return
    for dead in [e for e in state.enemies if not e.is_alive]:
        stacks = status_stacks(dead.status_effects, POISON)
        if stacks <= 0:
            continue
        dead.status_effects = [se for se in dead.status_effects if se.name != POISON]
        alive = state.living_enemies()
        if alive:
            add_status((rng or random).choice(alive).status_effects, POISON, stacks * mult,
                       is_buff=False)


def execute_wounded(state: CombatState, hp_before: list[int]) -> None:
    """Asesina: every enemy this attack hurt that is left under 25 % HP dies."""
    for enemy, before in zip(state.enemies, hp_before):
        if enemy.is_alive and enemy.current_hp < before and enemy.current_hp * 4 < enemy.max_hp:
            enemy.current_hp = 0


def settle_pickpocket(state: CombatState) -> int:
    """Carterista: once an enemy has died this turn, its pending gold is earned."""
    if state.pickpocket_gold and state.kills_this_turn() > 0:
        gold, state.pickpocket_gold = state.pickpocket_gold, 0
        state.gold_earned += gold
        return gold
    return 0


# ---------------------------------------------------------------------------
# Neutral relics
# ---------------------------------------------------------------------------

def try_broken_clock(state: CombatState) -> bool:
    """Reloj Roto: at 0 mana with cards in hand, refill the mana — once per combat (golden: 2)."""
    charges = _sum(state.relics, RelicTag.BROKEN_CLOCK, 1)
    if (charges and state.clock_uses < charges and state.mana.current == 0
            and state.hand.count > 0):
        state.clock_uses += 1
        state.mana.refill()
        return True
    return False


def spider_thread_block(relics: list[Relic]) -> int:
    """Hilo de Araña: block for ending the turn with an empty hand."""
    return _sum(relics, RelicTag.SPIDER_THREAD, 6)


def opening_extra_draw(relics: list[Relic]) -> int:
    """Botas Silenciosas: extra cards in the opening hand."""
    return _sum(relics, RelicTag.SILENT_BOOTS, 2)


def combat_gold_multiplier(relics: list[Relic]) -> float:
    """Máscara del Ladrón: +25 % combat gold (golden: +50 %)."""
    return 1.0 + 0.25 * _sum(relics, RelicTag.THIEF_MASK, 1)


def shop_price(relics: list[Relic], base: int) -> int:
    """Máscara del Ladrón: shop prices 10 % lower (golden: 20 %), never below 1."""
    discount = min(0.5, 0.10 * _sum(relics, RelicTag.THIEF_MASK, 1))
    return max(1, round(base * (1.0 - discount)))


def treasure_choices(relics: list[Relic]) -> int:
    """Llave Maestra: relics offered in a treasure room (1 + 1 per key; golden +2)."""
    return 1 + _sum(relics, RelicTag.MASTER_KEY, 1)


def unlocked_card_classes(relics: list[Relic]) -> frozenset[CardClass]:
    """Class card pools added by relics (e.g. a relic that mixes the Mage pool into any run)."""
    out: set[CardClass] = set()
    for r in relics:
        if r.is_active:
            out |= r.card_classes
    return frozenset(out)


def try_revive(state: CombatState) -> bool:
    """Called after the hero takes damage: Escudo Espectral first (1 HP), then Ankh (full HP).

    The weaker save is spent first so the Ankh is kept for later. Returns True if one triggered.
    """
    return try_spectral_shield(state) or try_ankh(state)


def try_ankh(state: CombatState) -> bool:
    """If player HP dropped to 0, revive at full HP and consume the Ankh (golden: 2 uses)."""
    if state.player.current_hp > 0:
        return False
    for relic in state.relics:
        if relic.is_active and relic.tag == RelicTag.ANKH:
            relic.times_triggered += 1
            if relic.times_triggered >= relic.effect_multiplier():
                relic.is_active = False
            state.player.current_hp = state.player.max_hp
            return True
    return False


def try_spectral_shield(state: CombatState) -> bool:
    """If player HP dropped to 0, save them at 1 HP and consume the shield.

    Returns True if the shield triggered.
    """
    if state.player.current_hp > 0:
        return False
    for relic in state.relics:
        if relic.is_active and relic.tag == RelicTag.SPECTRAL_SHIELD:
            # Charges = chroma multiplier: a golden shield saves you twice.
            relic.times_triggered += 1
            if relic.times_triggered >= relic.effect_multiplier():
                relic.is_active = False
            state.player.current_hp = 1
            return True
    return False
