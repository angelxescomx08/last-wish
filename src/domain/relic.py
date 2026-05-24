from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class RelicTag(Enum):
    COMBAT_AMULET   = "combat_amulet"    # +1 maná máximo al inicio del combate
    BROKEN_TOTEM    = "broken_totem"     # +1 carta al robar cada turno
    FIRE_ORB        = "fire_orb"         # +2 daño en todos los ataques
    SPECTRAL_SHIELD = "spectral_shield"  # Sobrevive con 1 HP al recibir golpe fatal
    ENERGY_STONE    = "energy_stone"     # +1 carta al robar cada turno (se apila con Tótem)
    GOLD_RING       = "gold_ring"        # +15 de oro extra por victoria de combate
    IRON_HEART      = "iron_heart"       # +15 de HP máximo permanente
    BLOOD_POTION    = "blood_potion"     # Recupera 8 HP después de cada combate


@dataclass
class Relic:
    id: str
    name: str
    description: str
    tag: RelicTag | None = None
    is_active: bool = True
