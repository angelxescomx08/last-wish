from __future__ import annotations

from src.domain.combat import CombatState
from src.domain.relic import Relic, RelicTag


def extra_draw_per_turn(relics: list[Relic]) -> int:
    """Extra cards drawn at the start of each player turn (Tótem Roto: +1)."""
    return sum(1 for r in relics if r.is_active and r.tag == RelicTag.BROKEN_TOTEM)


def extra_attack_damage(relics: list[Relic]) -> int:
    """Flat bonus damage added to every attack card played (Orbe de Fuego: +2)."""
    return sum(2 for r in relics if r.is_active and r.tag == RelicTag.FIRE_ORB)


def bonus_starting_mana(relics: list[Relic]) -> int:
    """Extra mana maximum granted once at combat start (Amuleto de Combate: +1)."""
    return sum(1 for r in relics if r.is_active and r.tag == RelicTag.COMBAT_AMULET)


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
