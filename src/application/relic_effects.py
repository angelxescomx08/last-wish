from __future__ import annotations

from src.domain.card import CardClass
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
    return _sum(relics, RelicTag.IRON_HEART, 15) + TUNING.extra_max_hp   # + Pruebas


def unlocked_card_classes(relics: list[Relic]) -> frozenset[CardClass]:
    """Class card pools added by relics (e.g. a relic that mixes the Mage pool into any run)."""
    out: set[CardClass] = set()
    for r in relics:
        if r.is_active:
            out |= r.card_classes
    return frozenset(out)


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
