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
    VITALITY_AMULET = "vitality_amulet"  # +10 de HP máximo permanente
    SEVEN_LEAF_CLOVER = "seven_leaf_clover"  # +100 de suerte
    EVASION_BROOCH  = "evasion_brooch"   # Pícara: al activar un Combo → +1 de bloqueo
    SINGULAR_MIRROR = "singular_mirror"  # Al obtenerla: elimina las cartas repetidas del mazo
    PANACEA         = "panacea"          # Inmune a los debuffs de los enemigos
    ETERNAL_FOUNT   = "eternal_fount"    # +1 de maná máximo al inicio de cada turno
    ANKH            = "ankh"             # Al recibir un golpe fatal, revive con toda la vida
    THROWING_KNIFE  = "throwing_knife"   # Pícara: al activar un Combo → 1 de daño a un enemigo al azar
    # La Pícara — Combo, Despojo, dagas y veneno
    RAG_SACK        = "rag_sack"         # Pícara: al activar un Despojo → +2 de escudo
    DUELIST_SCARF   = "duelist_scarf"    # Pícara: al activar un Combo, la carta hace +2 de daño / +2 de escudo
    GRAPPLING_HOOK  = "grappling_hook"   # Pícara: el primer Despojo de cada turno roba 1
    CRIMSON_RIBBON  = "crimson_ribbon"   # Pícara: en el primer turno los Combos están siempre activos
    TORN_POCKET     = "torn_pocket"      # Pícara: tras robar tu mano, descarta 1 al azar y roba 1
    SPLIT_DAGGER    = "split_dagger"     # Pícara: los efectos de Despojo se activan dos veces
    DAGGER_POUCH    = "dagger_pouch"     # Pícara: al empezar el combate, 2 Dagas Ocultas en el mazo
    SHARP_SHEATH    = "sharp_sheath"     # Pícara: las Dagas Ocultas hacen +2 de daño
    POISON_VIAL     = "poison_vial"      # Pícara: el primer ataque de cada turno aplica 1 de Veneno
    VIPER_FANG      = "viper_fang"       # Pícara: el Veneno de un enemigo muerto pasa a otro
    # Neutrales
    THIEF_MASK      = "thief_mask"       # +25 % de oro por combate, tienda 10 % más barata
    LUCKY_COIN      = "lucky_coin"       # efecto al azar repite enemigo → +1 de maná (1 vez por turno)
    SILVER_HORSESHOE = "silver_horseshoe"  # +30 de suerte
    SILK_GLOVE      = "silk_glove"       # la tercera carta de cada turno cuesta 0
    SILENT_BOOTS    = "silent_boots"     # el primer turno de cada combate robas 2 más
    SPIDER_THREAD   = "spider_thread"    # acabar el turno sin cartas en la mano → +6 de escudo
    MASTER_KEY      = "master_key"       # los tesoros ofrecen 2 reliquias a elegir
    BROKEN_CLOCK    = "broken_clock"     # 1 vez por combate: a 0 de maná con cartas en mano, recupéralo
    COMPOUND_INTEREST = "compound_interest"  # cada vez que ganas oro, +10 % de tu oro total


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
    RelicTag.VITALITY_AMULET: Rarity.COMMON,
    RelicTag.EVASION_BROOCH:  Rarity.UNCOMMON,
    RelicTag.THROWING_KNIFE:  Rarity.UNCOMMON,
    RelicTag.SEVEN_LEAF_CLOVER: Rarity.LEGENDARY,
    RelicTag.ANKH:            Rarity.LEGENDARY,
    RelicTag.SINGULAR_MIRROR: Rarity.LEGENDARY,
    RelicTag.PANACEA:         Rarity.LEGENDARY,
    RelicTag.ETERNAL_FOUNT:   Rarity.LEGENDARY,
    RelicTag.RAG_SACK:        Rarity.COMMON,
    RelicTag.DUELIST_SCARF:   Rarity.UNCOMMON,
    RelicTag.GRAPPLING_HOOK:  Rarity.UNCOMMON,
    RelicTag.CRIMSON_RIBBON:  Rarity.RARE,
    RelicTag.TORN_POCKET:     Rarity.RARE,
    RelicTag.SPLIT_DAGGER:    Rarity.LEGENDARY,
    RelicTag.DAGGER_POUCH:    Rarity.COMMON,
    RelicTag.SHARP_SHEATH:    Rarity.UNCOMMON,
    RelicTag.POISON_VIAL:     Rarity.UNCOMMON,
    RelicTag.VIPER_FANG:      Rarity.RARE,
    RelicTag.THIEF_MASK:      Rarity.COMMON,
    RelicTag.LUCKY_COIN:      Rarity.UNCOMMON,
    RelicTag.SILVER_HORSESHOE: Rarity.UNCOMMON,
    RelicTag.SILK_GLOVE:      Rarity.RARE,
    RelicTag.SILENT_BOOTS:    Rarity.RARE,
    RelicTag.SPIDER_THREAD:   Rarity.EPIC,
    RelicTag.MASTER_KEY:      Rarity.EPIC,
    RelicTag.BROKEN_CLOCK:    Rarity.LEGENDARY,
    RelicTag.COMPOUND_INTEREST: Rarity.EPIC,
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
    # Who can find it: NEUTRAL = every hero, otherwise only that class's hero.
    relic_class: CardClass = CardClass.NEUTRAL
    chroma: Chroma | None = None   # special finish (golden = effects x2)
    times_triggered: int = 0       # uses spent by one-shot relics (charges = multiplier)
    rarity: Rarity | None = None   # None → taken from RELIC_RARITY by tag (Common if untagged)

    def __post_init__(self) -> None:
        if self.rarity is None:
            self.rarity = RELIC_RARITY.get(self.tag, Rarity.COMMON) if self.tag else Rarity.COMMON

    def effect_multiplier(self) -> int:
        return effect_multiplier(self.chroma)


def relic_total(relics: list[Relic], tag: RelicTag, amount: int = 1) -> int:
    """``amount`` per active relic with ``tag``, scaled by its chroma (golden x2). 0 if none."""
    return sum(amount * r.effect_multiplier() for r in relics if r.is_active and r.tag == tag)
