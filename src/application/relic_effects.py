from __future__ import annotations

import random

from src.domain.card import Card, CardClass
from src.domain.keywords import Keyword
from src.domain.combat import CombatState
from src.domain.relic import Relic, RelicTag
from src.domain.tuning import TUNING


def _sum(relics: list[Relic], tag: RelicTag, amount: int) -> int:
    """``amount`` per active relic with ``tag``, scaled by its chroma (golden x2)."""
    return sum(amount * r.effect_multiplier() for r in relics if r.is_active and r.tag == tag)


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


def luck_bonus(relics: list[Relic]) -> int:
    """Extra luck from relics (Trébol de Siete Hojas: +100)."""
    return _sum(relics, RelicTag.SEVEN_LEAF_CLOVER, 100)


def on_card_played(state: CombatState, card: Card, combo: bool,
                   rng: random.Random | None = None) -> None:
    """Relic triggers after a card fully resolves (once per play, not per golden cast).

    ``combo``: the card's Combo layer resolved this play (``PlayResult.combo``).
    Broche de Evasión: a card whose Combo resolved gives +1 block.
    Cuchillo Arrojadizo: a card whose Combo resolved deals 1 damage to a random
    living enemy (block absorbs it). Golden relics: x2.
    """
    if not combo or Keyword.COMBO not in card.keywords():
        return
    block = _sum(state.relics, RelicTag.EVASION_BROOCH, 1)
    if block:
        state.player.block += block
    damage = _sum(state.relics, RelicTag.THROWING_KNIFE, 1)
    alive = [e for e in state.enemies if e.is_alive]
    if damage and alive:
        enemy = (rng or random).choice(alive)
        absorbed = min(enemy.block, damage)
        enemy.block -= absorbed
        enemy.current_hp = max(0, enemy.current_hp - (damage - absorbed))


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
