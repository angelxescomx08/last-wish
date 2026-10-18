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
    SCAR            = "scar"             # empiezas cada combate con +1 de Fuerza
    WAR_BRACER      = "war_bracer"       # al empezar cada combate, 8 de escudo
    # La Guerrera — vida, curación, escudo y Fuerza
    IRON_FANG       = "iron_fang"        # Guerrera: tu primer ataque de cada turno te cura 2
    SOAKED_BANDAGE  = "soaked_bandage"   # Guerrera: la primera vez que pierdes vida en tu turno, roba 1
    BLOOD_CUP       = "blood_cup"        # Guerrera: tus curaciones en combate curan +2
    TORN_BANNER     = "torn_banner"      # Guerrera: cada 3 Furias activadas, +1 de Fuerza
    TITAN_HEART     = "titan_heart"      # Guerrera: la curación sobrante da el doble de escudo
    # Neutrales (2026-10-17)
    DIAMOND_CARDS = "diamond_cards"
    COLLECTOR_SEAL = "collector_seal"
    ANTIQUARY_SEAL = "antiquary_seal"
    STAIRWAY = "stairway"
    UNIQUE_PIECE = "unique_piece"
    TAILOR_SCISSORS = "tailor_scissors"
    WHETSTONE = "whetstone"
    RAGGED_CAPE = "ragged_cape"
    VOTIVE_CANDLE = "votive_candle"
    WHITE_FLAG = "white_flag"
    DANDELION = "dandelion"
    OIL_LAMP = "oil_lamp"
    WILD_FRUIT = "wild_fruit"
    ANTIDOTE = "antidote"
    WAR_HORN = "war_horn"
    SANDBAG = "sandbag"
    CHESS_PIECE = "chess_piece"
    OLD_SCROLL = "old_scroll"
    TIDY_PILE = "tidy_pile"
    MONK_WRAPS = "monk_wraps"
    SPYGLASS = "spyglass"
    RABBIT_FOOT = "rabbit_foot"
    THORN_CROWN = "thorn_crown"
    FROST_AMULET = "frost_amulet"
    BREACH_SPEAR = "breach_spear"
    PENDULUM = "pendulum"
    BALANCE_BRACELET = "balance_bracelet"
    EMPTY_BOWL = "empty_bowl"
    HOURGLASS = "hourglass"
    ANCHOR = "anchor"
    MARKED_CARDS = "marked_cards"
    VETERAN_MEDAL = "veteran_medal"
    LAUREL_LEAF = "laurel_leaf"
    PHOENIX_FEATHER = "phoenix_feather"
    LAST_BREATH = "last_breath"
    SHACKLE = "shackle"
    MAGIC_DECK = "magic_deck"
    ARCANE_BATTERY = "arcane_battery"
    STONE_HEART = "stone_heart"
    PRISM = "prism"
    TOUCHSTONE = "touchstone"
    BOTTOMLESS_BAG = "bottomless_bag"
    CURSED_CONTRACT = "cursed_contract"
    D20 = "d20"
    MANA_VIAL = "mana_vial"
    LEAKY_PURSE = "leaky_purse"
    CANTEEN = "canteen"
    VOUCHER = "voucher"
    MINER_PICK = "miner_pick"
    PIGGY_BANK = "piggy_bank"
    GRINNING_SKULL = "grinning_skull"
    PORTABLE_ANVIL = "portable_anvil"
    LOADED_DIE = "loaded_die"
    MEMBER_CARD = "member_card"
    HUNTING_TROPHY = "hunting_trophy"
    SMITH_HAMMER = "smith_hammer"
    IRON_FILE = "iron_file"
    APPRAISER_LENS = "appraiser_lens"
    TWO_FACED_COIN = "two_faced_coin"
    BROKEN_CHAIN = "broken_chain"
    # La Guerrera (2026-10-17)
    SPIKED_GAUNTLET = "spiked_gauntlet"
    WRISTGUARD = "wristguard"
    FIELD_BANDAGE = "field_bandage"
    DENTED_PLATE = "dented_plate"
    FANG_NECKLACE = "fang_necklace"
    NOTCHED_AXE = "notched_axe"
    BLOOD_SKIN = "blood_skin"
    BLOOD_GEM = "blood_gem"
    MARTYR_SHIELD = "martyr_shield"
    CRIMSON_CHALICE = "crimson_chalice"
    WAR_DRUM = "war_drum"
    BRAZIER = "brazier"
    WORN_ROUNDEL = "worn_roundel"
    BERSERKER_HELM = "berserker_helm"
    BLOOD_RUNE = "blood_rune"
    LEGION_BANNER = "legion_banner"
    RACING_HEART = "racing_heart"
    MOLTEN_IRON = "molten_iron"
    # El Mago (2026-10-17)
    TINDER = "tinder"
    SEASHELL = "seashell"
    PUMICE = "pumice"
    GRIFFIN_FEATHER = "griffin_feather"
    WILLOW_WAND = "willow_wand"
    WATER_CLOCK = "water_clock"
    POINTY_HAT = "pointy_hat"
    LAVA_STONE = "lava_stone"
    WITCH_BROOM = "witch_broom"
    CAULDRON = "cauldron"
    VOLCANO_EMBER = "volcano_ember"
    STORM_ORB = "storm_orb"
    BLANK_GRIMOIRE = "blank_grimoire"
    LESSER_FOUNT = "lesser_fount"
    FROST_CRYSTAL = "frost_crystal"
    PRISMATIC_LENS = "prismatic_lens"
    ARCHMAGE_CLOAK = "archmage_cloak"
    RING_OF_FOUR = "ring_of_four"
    # La Pícara (2026-10-17)
    POCKET_SHARPENER = "pocket_sharpener"
    FOLDING_KNIFE = "folding_knife"
    MARBLE_BAG = "marble_bag"
    RASCAL_BOOTS = "rascal_boots"
    THIEF_GLOVE = "thief_glove"
    SCORPION_VENOM = "scorpion_venom"
    BLACK_SILK = "black_silk"
    BONE_DIE = "bone_die"
    MIST_FLASK = "mist_flask"
    LOCKPICK = "lockpick"
    HARLEQUIN_MASK = "harlequin_mask"
    CAPUCHE = "capuche"
    POISONED_SCARF = "poisoned_scarf"
    TWIN_DAGGERS = "twin_daggers"
    FOX_TAIL = "fox_tail"
    STOLEN_WATCH = "stolen_watch"
    SINGULAR_LOCKET = "singular_locket"
    THIEF_KING_CROWN = "thief_king_crown"


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
    RelicTag.SCAR:            Rarity.COMMON,
    RelicTag.WAR_BRACER:      Rarity.COMMON,
    RelicTag.IRON_FANG:       Rarity.UNCOMMON,
    RelicTag.SOAKED_BANDAGE:  Rarity.UNCOMMON,
    RelicTag.BLOOD_CUP:       Rarity.RARE,
    RelicTag.TORN_BANNER:     Rarity.EPIC,
    RelicTag.TITAN_HEART:     Rarity.LEGENDARY,
    RelicTag.DIAMOND_CARDS: Rarity.LEGENDARY,
    RelicTag.COLLECTOR_SEAL: Rarity.LEGENDARY,
    RelicTag.ANTIQUARY_SEAL: Rarity.LEGENDARY,
    RelicTag.STAIRWAY: Rarity.EPIC,
    RelicTag.UNIQUE_PIECE: Rarity.LEGENDARY,
    RelicTag.TAILOR_SCISSORS: Rarity.LEGENDARY,
    RelicTag.WHETSTONE: Rarity.COMMON,
    RelicTag.RAGGED_CAPE: Rarity.COMMON,
    RelicTag.VOTIVE_CANDLE: Rarity.COMMON,
    RelicTag.WHITE_FLAG: Rarity.COMMON,
    RelicTag.DANDELION: Rarity.COMMON,
    RelicTag.OIL_LAMP: Rarity.COMMON,
    RelicTag.WILD_FRUIT: Rarity.COMMON,
    RelicTag.ANTIDOTE: Rarity.COMMON,
    RelicTag.WAR_HORN: Rarity.UNCOMMON,
    RelicTag.SANDBAG: Rarity.UNCOMMON,
    RelicTag.CHESS_PIECE: Rarity.UNCOMMON,
    RelicTag.OLD_SCROLL: Rarity.UNCOMMON,
    RelicTag.TIDY_PILE: Rarity.UNCOMMON,
    RelicTag.MONK_WRAPS: Rarity.UNCOMMON,
    RelicTag.SPYGLASS: Rarity.UNCOMMON,
    RelicTag.RABBIT_FOOT: Rarity.UNCOMMON,
    RelicTag.THORN_CROWN: Rarity.RARE,
    RelicTag.FROST_AMULET: Rarity.RARE,
    RelicTag.BREACH_SPEAR: Rarity.RARE,
    RelicTag.PENDULUM: Rarity.RARE,
    RelicTag.BALANCE_BRACELET: Rarity.RARE,
    RelicTag.EMPTY_BOWL: Rarity.RARE,
    RelicTag.HOURGLASS: Rarity.RARE,
    RelicTag.ANCHOR: Rarity.RARE,
    RelicTag.MARKED_CARDS: Rarity.RARE,
    RelicTag.VETERAN_MEDAL: Rarity.RARE,
    RelicTag.LAUREL_LEAF: Rarity.RARE,
    RelicTag.PHOENIX_FEATHER: Rarity.EPIC,
    RelicTag.LAST_BREATH: Rarity.EPIC,
    RelicTag.SHACKLE: Rarity.EPIC,
    RelicTag.MAGIC_DECK: Rarity.EPIC,
    RelicTag.ARCANE_BATTERY: Rarity.EPIC,
    RelicTag.STONE_HEART: Rarity.EPIC,
    RelicTag.PRISM: Rarity.EPIC,
    RelicTag.TOUCHSTONE: Rarity.EPIC,
    RelicTag.BOTTOMLESS_BAG: Rarity.EPIC,
    RelicTag.CURSED_CONTRACT: Rarity.LEGENDARY,
    RelicTag.D20: Rarity.LEGENDARY,
    RelicTag.MANA_VIAL: Rarity.LEGENDARY,
    RelicTag.LEAKY_PURSE: Rarity.COMMON,
    RelicTag.CANTEEN: Rarity.COMMON,
    RelicTag.VOUCHER: Rarity.COMMON,
    RelicTag.MINER_PICK: Rarity.UNCOMMON,
    RelicTag.PIGGY_BANK: Rarity.UNCOMMON,
    RelicTag.GRINNING_SKULL: Rarity.UNCOMMON,
    RelicTag.PORTABLE_ANVIL: Rarity.UNCOMMON,
    RelicTag.LOADED_DIE: Rarity.UNCOMMON,
    RelicTag.MEMBER_CARD: Rarity.RARE,
    RelicTag.HUNTING_TROPHY: Rarity.RARE,
    RelicTag.SMITH_HAMMER: Rarity.RARE,
    RelicTag.IRON_FILE: Rarity.RARE,
    RelicTag.APPRAISER_LENS: Rarity.RARE,
    RelicTag.TWO_FACED_COIN: Rarity.RARE,
    RelicTag.BROKEN_CHAIN: Rarity.RARE,
    RelicTag.SPIKED_GAUNTLET: Rarity.COMMON,
    RelicTag.WRISTGUARD: Rarity.COMMON,
    RelicTag.FIELD_BANDAGE: Rarity.COMMON,
    RelicTag.DENTED_PLATE: Rarity.UNCOMMON,
    RelicTag.FANG_NECKLACE: Rarity.UNCOMMON,
    RelicTag.NOTCHED_AXE: Rarity.UNCOMMON,
    RelicTag.BLOOD_SKIN: Rarity.UNCOMMON,
    RelicTag.BLOOD_GEM: Rarity.UNCOMMON,
    RelicTag.MARTYR_SHIELD: Rarity.RARE,
    RelicTag.CRIMSON_CHALICE: Rarity.RARE,
    RelicTag.WAR_DRUM: Rarity.RARE,
    RelicTag.BRAZIER: Rarity.RARE,
    RelicTag.WORN_ROUNDEL: Rarity.EPIC,
    RelicTag.BERSERKER_HELM: Rarity.EPIC,
    RelicTag.BLOOD_RUNE: Rarity.EPIC,
    RelicTag.LEGION_BANNER: Rarity.EPIC,
    RelicTag.RACING_HEART: Rarity.LEGENDARY,
    RelicTag.MOLTEN_IRON: Rarity.LEGENDARY,
    RelicTag.TINDER: Rarity.COMMON,
    RelicTag.SEASHELL: Rarity.COMMON,
    RelicTag.PUMICE: Rarity.COMMON,
    RelicTag.GRIFFIN_FEATHER: Rarity.COMMON,
    RelicTag.WILLOW_WAND: Rarity.COMMON,
    RelicTag.WATER_CLOCK: Rarity.UNCOMMON,
    RelicTag.POINTY_HAT: Rarity.UNCOMMON,
    RelicTag.LAVA_STONE: Rarity.UNCOMMON,
    RelicTag.WITCH_BROOM: Rarity.UNCOMMON,
    RelicTag.CAULDRON: Rarity.RARE,
    RelicTag.VOLCANO_EMBER: Rarity.RARE,
    RelicTag.STORM_ORB: Rarity.RARE,
    RelicTag.BLANK_GRIMOIRE: Rarity.RARE,
    RelicTag.LESSER_FOUNT: Rarity.RARE,
    RelicTag.FROST_CRYSTAL: Rarity.EPIC,
    RelicTag.PRISMATIC_LENS: Rarity.EPIC,
    RelicTag.ARCHMAGE_CLOAK: Rarity.EPIC,
    RelicTag.RING_OF_FOUR: Rarity.LEGENDARY,
    RelicTag.POCKET_SHARPENER: Rarity.COMMON,
    RelicTag.FOLDING_KNIFE: Rarity.COMMON,
    RelicTag.MARBLE_BAG: Rarity.COMMON,
    RelicTag.RASCAL_BOOTS: Rarity.COMMON,
    RelicTag.THIEF_GLOVE: Rarity.UNCOMMON,
    RelicTag.SCORPION_VENOM: Rarity.UNCOMMON,
    RelicTag.BLACK_SILK: Rarity.UNCOMMON,
    RelicTag.BONE_DIE: Rarity.UNCOMMON,
    RelicTag.MIST_FLASK: Rarity.UNCOMMON,
    RelicTag.LOCKPICK: Rarity.UNCOMMON,
    RelicTag.HARLEQUIN_MASK: Rarity.RARE,
    RelicTag.CAPUCHE: Rarity.RARE,
    RelicTag.POISONED_SCARF: Rarity.RARE,
    RelicTag.TWIN_DAGGERS: Rarity.RARE,
    RelicTag.FOX_TAIL: Rarity.RARE,
    RelicTag.STOLEN_WATCH: Rarity.EPIC,
    RelicTag.SINGULAR_LOCKET: Rarity.EPIC,
    RelicTag.THIEF_KING_CROWN: Rarity.LEGENDARY,
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
