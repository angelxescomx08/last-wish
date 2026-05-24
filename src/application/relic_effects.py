from __future__ import annotations

from src.domain.combat import CombatState
from src.domain.relic import Relic, RelicTag


def extra_draw_per_turn(relics: list[Relic]) -> int:
    """Extra cards drawn at the start of each player turn (Tótem Roto / Piedra de Energía: +1 each)."""
    totem  = sum(1 for r in relics if r.is_active and r.tag == RelicTag.BROKEN_TOTEM)
    energy = sum(1 for r in relics if r.is_active and r.tag == RelicTag.ENERGY_STONE)
    return totem + energy


def extra_attack_damage(relics: list[Relic]) -> int:
    """Flat bonus damage added to every attack card played (Orbe de Fuego: +2)."""
    return sum(2 for r in relics if r.is_active and r.tag == RelicTag.FIRE_ORB)


def bonus_starting_mana(relics: list[Relic]) -> int:
    """Extra mana maximum granted once at combat start (Amuleto de Combate: +1)."""
    return sum(1 for r in relics if r.is_active and r.tag == RelicTag.COMBAT_AMULET)


def bonus_gold_reward(relics: list[Relic]) -> int:
    """Extra gold earned per combat victory (Anillo de Oro: +15 each)."""
    return sum(15 for r in relics if r.is_active and r.tag == RelicTag.GOLD_RING)


def post_combat_heal(relics: list[Relic]) -> int:
    """HP restored after each combat victory (Poción de Sangre: +8 each)."""
    return sum(8 for r in relics if r.is_active and r.tag == RelicTag.BLOOD_POTION)


def max_hp_bonus(relics: list[Relic]) -> int:
    """Permanent max-HP increase from relics (Corazón de Hierro: +15 each)."""
    return sum(15 for r in relics if r.is_active and r.tag == RelicTag.IRON_HEART)


def try_spectral_shield(state: CombatState) -> bool:
    """If player HP dropped to 0, save them at 1 HP and consume the shield.

    Returns True if the shield triggered.
    """
    if state.player.current_hp > 0:
        return False
    for relic in state.relics:
        if relic.is_active and relic.tag == RelicTag.SPECTRAL_SHIELD:
            relic.is_active = False
            state.player.current_hp = 1
            return True
    return False
