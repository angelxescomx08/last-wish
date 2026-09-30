from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from src.domain.card import CardClass
from src.domain.chroma import Chroma, effect_multiplier
from src.domain.rarity import Rarity


class RelicTag(Enum):
    COMBAT_AMULET   = "combat_amulet"    # +1 maná máximo al inicio del combate
    BROKEN_TOTEM    = "broken_totem"     # +1 carta al robar cada turno
    FIRE_ORB        = "fire_orb"         # +2 daño en todos los ataques
    SPECTRAL_SHIELD = "spectral_shield"  # Sobrevive con 1 HP al recibir golpe fatal
    ENERGY_STONE    = "energy_stone"     # +1 carta al robar cada turno (se apila con Tótem)
    GOLD_RING       = "gold_ring"        # +15 de oro extra por victoria de combate
    IRON_HEART      = "iron_heart"       # +15 de HP máximo permanente
    BLOOD_POTION    = "blood_potion"     # Recupera 8 HP después de cada combate


# Tier of each relic (same five tiers as cards). Luck makes higher tiers likelier.
RELIC_RARITY: dict[RelicTag, Rarity] = {
    RelicTag.BLOOD_POTION:    Rarity.COMMON,
    RelicTag.GOLD_RING:       Rarity.COMMON,
    RelicTag.IRON_HEART:      Rarity.UNCOMMON,
    RelicTag.FIRE_ORB:        Rarity.UNCOMMON,
    RelicTag.BROKEN_TOTEM:    Rarity.RARE,
    RelicTag.ENERGY_STONE:    Rarity.RARE,
    RelicTag.COMBAT_AMULET:   Rarity.EPIC,
    RelicTag.SPECTRAL_SHIELD: Rarity.LEGENDARY,
}


@dataclass
class Relic:
    id: str
    name: str
    description: str
    tag: RelicTag | None = None
    is_active: bool = True
    # Class card pools this relic adds to rewards and packs (mixes pools).
    card_classes: frozenset[CardClass] = field(default_factory=frozenset)
    chroma: Chroma | None = None   # special finish (golden = effects x2)
    times_triggered: int = 0       # uses spent by one-shot relics (charges = multiplier)
    rarity: Rarity | None = None   # None → taken from RELIC_RARITY by tag (Common if untagged)

    def __post_init__(self) -> None:
        if self.rarity is None:
            self.rarity = RELIC_RARITY.get(self.tag, Rarity.COMMON) if self.tag else Rarity.COMMON

    def effect_multiplier(self) -> int:
        return effect_multiplier(self.chroma)
