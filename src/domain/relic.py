from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class RelicTag(Enum):
    COMBAT_AMULET   = "combat_amulet"    # +1 maná máximo al inicio del combate
    BROKEN_TOTEM    = "broken_totem"     # +1 carta al robar cada turno
    FIRE_ORB        = "fire_orb"         # +2 daño en todos los ataques
    SPECTRAL_SHIELD = "spectral_shield"  # Sobrevive con 1 HP al recibir golpe fatal


@dataclass
class Relic:
    id: str
    name: str
    description: str
    tag: RelicTag | None = None
    is_active: bool = True
