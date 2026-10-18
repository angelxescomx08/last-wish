"""Run lifecycle management.

Responsibilities:
  - Creating a new Run from a chosen character + seed.
  - Generating enemies appropriate for the current floor.
  - Post-combat state updates (HP, gold, relic heal).
  - Generating events (gold rewards).
  - Generating treasure (relic selection pool).
  - Generating boss enemy.
  - Generating the elite of an elite room and its relic.
"""
from __future__ import annotations

import random
import zlib
from dataclasses import replace

from src.application import elites, enemy_roster, enemy_ai, relic_effects
from src.application.map_generator import generate_map
from src.domain.card import CardClass
from src.domain.card_pool import ALL_PACKS, PackDef, class_for_character, starter_deck
from src.domain.character import Character
from src.domain.chroma import roll_chroma
from src.domain.rarity import weighted_sample
from src.domain.entities import Enemy, Intent, IntentType
from src.domain.relic import Relic, RelicTag, relic_total
from src.domain.run import Run
from src.domain.tuning import TUNING, hero_luck

# Large prime for enemy RNG seeding
_ENEMY_PRIME: int = 2_654_435_761


# ---------------------------------------------------------------------------
# Run creation
# ---------------------------------------------------------------------------

def create_run(character: Character, seed: int) -> Run:
    """Initialise a brand-new Run with the starter deck and no relics."""
    run = Run(
        character=character,
        seed=seed,
        floor=1,
        gold=TUNING.starting_gold,
        player_max_hp=character.stats.max_hp + TUNING.extra_max_hp,
        player_current_hp=character.stats.max_hp + TUNING.extra_max_hp,
        deck=starter_deck(character.id),
        relics=[],
    )
    run.current_map = generate_map(seed, 1)
    return run


# ---------------------------------------------------------------------------
# Enemy generation
# ---------------------------------------------------------------------------

def _enemy_seed(run: Run, room_id: str) -> int:
    h = zlib.crc32(room_id.encode("utf-8")) & 0xFFFF_FFFF    # stable across runs (hash() is salted)
    return (run.seed * _ENEMY_PRIME + run.floor * 997 + h) & 0xFFFF_FFFF_FFFF_FFFF


def _scale(base: int, floor: int) -> int:
    return int(base * (1 + 0.15 * (floor - 1)))


def generate_enemies(run: Run, room_id: str) -> list[Enemy]:
    """The enemies of a combat room (Pruebas: the floor boss, or a fixed encounter).

    Regular enemies come from ``enemy_roster``: one enemy alone or a fixed pair
    (and from floor 3, sometimes a pair plus one more), each with its own pattern.
    """
    if TUNING.boss_rooms:
        return generate_boss(run)
    if TUNING.elite_rooms:
        return generate_elite(run, room_id)
    rng = random.Random(_enemy_seed(run, room_id))
    return enemy_roster.roll_encounter(rng, run.floor, room_id, TUNING.forced_encounter)


def generate_elite(run: Run, room_id: str) -> list[Enemy]:
    """The elite of an elite room: one of the five ``elites`` (seeded per room; Pruebas can fix it)."""
    rng = random.Random(_enemy_seed(run, room_id) ^ 0xE117E)
    return elites.roll_elite(rng, run.floor, room_id, TUNING.forced_elite)


def floor_boss_ai(run: Run) -> str | None:
    """Pattern-AI boss of this floor (floor 1: one of three, by seed or Pruebas), or None."""
    if run.floor != 1:
        return None
    forced = TUNING.forced_boss
    if 1 <= forced <= len(enemy_ai.FLOOR1_BOSSES):
        return enemy_ai.FLOOR1_BOSSES[forced - 1]
    rng = random.Random((run.seed * _ENEMY_PRIME) ^ 0xB055)
    return rng.choice(enemy_ai.FLOOR1_BOSSES)


def generate_boss(run: Run) -> list[Enemy]:
    """Return the boss enemy for the current floor.

    Floor 1: La Reina Micélida, La Tejedora or El Caballero Hueco (seeded, see
    ``application/enemy_ai.py``). Later floors: the Señor de la Cripta.
    """
    floor = run.floor
    ai = floor_boss_ai(run)
    if ai is not None:
        return [enemy_ai.create_boss(ai, floor, enemy_id=f"boss_f{floor}")]
    hp    = _scale(120, floor)
    dmg   = _scale(18,  floor)
    return [
        Enemy(
            id=f"boss_f{floor}",
            name=f"Señor de la Cripta (Piso {floor})",
            max_hp=hp,
            current_hp=hp,
            intent=Intent(IntentType.ATTACK, dmg),
        )
    ]


# ---------------------------------------------------------------------------
# Post-combat updates
# ---------------------------------------------------------------------------

def _combat_gold(run: Run, enemies: list[Enemy]) -> int:
    """Gold for a victory: enemies' worth + Anillo de Oro, x Máscara del Ladrón, x Pruebas."""
    base = sum(max(1, e.max_hp // 8) for e in enemies)
    base += relic_effects.bonus_gold_reward(run.relics)
    return round(base * relic_effects.combat_gold_multiplier(run.relics) * TUNING.gold_multiplier)


def apply_combat_victory(run: Run, hp_after: int, enemies: list[Enemy], bonus_gold: int = 0, *,
                         hp_lost: int | None = None, turns: int | None = None,
                         elite: bool = False, boss: bool = False) -> int:
    """Update run state after winning a combat.  Returns gold earned.

    ``bonus_gold``: gold won during the fight (``CombatState.gold_earned``, e.g. Carterista).
    ``hp_lost`` / ``turns`` (``CombatState.hp_lost_combat`` / ``turn``) and ``elite`` / ``boss``
    feed the victory relics: Cantimplora, Trofeo de Caza, Botas de Ratero, Calavera Sonriente,
    Medalla del Veterano and Hoja de Laurel.
    """
    n = lambda tag, amount=1: relic_total(run.relics, tag, amount)     # noqa: E731
    if elite and n(RelicTag.VETERAN_MEDAL):                           # Medalla del Veterano
        run.bonus_max_hp += n(RelicTag.VETERAN_MEDAL, 3)
        run.player_max_hp = max_hp(run)
        hp_after += n(RelicTag.VETERAN_MEDAL, 3)
    heal   = relic_effects.post_combat_heal(run.relics)
    new_hp = min(hp_after + heal, run.player_max_hp)
    if boss and n(RelicTag.LAUREL_LEAF):                              # Hoja de Laurel
        new_hp = run.player_max_hp
    run.apply_combat_result(new_hp)
    gold = _combat_gold(run, enemies) + max(0, bonus_gold)
    flawless = hp_lost is not None and hp_lost <= 0
    if flawless:
        gold += n(RelicTag.CANTEEN, 15)                               # Cantimplora
        run.bonus_luck += n(RelicTag.RASCAL_BOOTS, 2)                 # Botas de Ratero
    if turns is not None and turns <= 3:
        gold += n(RelicTag.HUNTING_TROPHY, 20)                        # Trofeo de Caza
    if elite:
        gold += n(RelicTag.GRINNING_SKULL, 30)                        # Calavera Sonriente
    gain_gold(run, gold)
    return gold


def enter_room(run: Run, room_type) -> int:
    """A room is entered. Bolsa Agujereada +5 gold every room; Hucha in shops (1 per 10 gold,
    max 15); Pico de Minero (+25) and Ganzúa (+20) in treasure rooms. Returns the gold won."""
    from src.domain.map_node import RoomType
    n = lambda tag, amount=1: relic_total(run.relics, tag, amount)     # noqa: E731
    gold = n(RelicTag.LEAKY_PURSE, 5)
    if room_type is RoomType.SHOP:
        gold += min(n(RelicTag.PIGGY_BANK, 15), (run.gold // 10) * n(RelicTag.PIGGY_BANK))
    if room_type is RoomType.TREASURE:
        gold += n(RelicTag.MINER_PICK, 25) + n(RelicTag.LOCKPICK, 20)
    if gold > 0:
        gain_gold(run, gold)
    return gold


def shop_offer_price(run: Run, base: int, *, relic: bool, purchases: int) -> int:
    """Price of a shop offer now: Máscara del Ladrón, then Tarjeta de Socio (the first purchase
    of the shop costs half) and Vale de Descuento (one relic free while the voucher is active)."""
    if relic and relic_effects.has_tag(run.relics, RelicTag.VOUCHER):
        return 0
    price = shop_price(run, base)
    if purchases == 0 and relic_effects.has_tag(run.relics, RelicTag.MEMBER_CARD):
        price = max(1, price // 2)
    return price


def use_voucher(run: Run) -> bool:
    """The free relic of the Vale de Descuento was taken: the voucher is spent."""
    for relic in run.relics:
        if relic.is_active and relic.tag is RelicTag.VOUCHER:
            relic.is_active = False
            return True
    return False


def pack_picks(run: Run, chroma) -> int:
    """Cards you keep from a pack: its chroma multiplier (golden 2); Bolsa sin Fondo: golden 3."""
    from src.domain.chroma import Chroma, effect_multiplier
    picks = effect_multiplier(chroma)
    if chroma is Chroma.GOLDEN and relic_effects.has_tag(run.relics, RelicTag.BOTTOMLESS_BAG):
        picks += 1
    return picks


def gain_gold(run: Run, amount: int) -> int:
    """Add ``amount`` gold (every gold *gain* of the run goes through here). Returns the interest.

    Interés Compuesto: after the gain, add ``compound_interest_percent`` % of the new
    total (rounded down). The interest itself does not earn more interest. Recorded in
    ``Run.last_interest`` (0 when none) and ``Run.interest_earned``.
    """
    run.last_interest = 0
    if amount <= 0:
        return 0
    run.gold += amount
    interest = run.gold * relic_effects.compound_interest_percent(run.relics) // 100
    run.gold += interest
    run.last_interest = interest
    run.interest_earned += interest
    return interest


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------

def generate_event_gold(run: Run, room_id: str) -> int:
    rng = random.Random(_enemy_seed(run, room_id) ^ 0xABCD)
    return round(rng.randint(10 + run.floor * 2, 25 + run.floor * 3) * TUNING.gold_multiplier)


# ---------------------------------------------------------------------------
# Treasure relics
# ---------------------------------------------------------------------------

def _all_relic_defs() -> list[Relic]:
    return [
        Relic("r_amulet",   "Amuleto de Combate",
              "+1 maná máximo al inicio del combate.",      tag=RelicTag.COMBAT_AMULET),
        Relic("r_totem",    "Tótem Roto",
              "+1 carta robada al inicio de cada turno.",   tag=RelicTag.BROKEN_TOTEM),
        Relic("r_fire",     "Orbe de Fuego",
              "+2 de daño en todos los ataques.",           tag=RelicTag.FIRE_ORB),
        Relic("r_shield",   "Escudo Espectral",
              "Sobrevive una vez con 1 HP a un golpe fatal.", tag=RelicTag.SPECTRAL_SHIELD),
        Relic("r_energy",   "Piedra de Energía",
              "+1 carta robada al inicio de cada turno.",   tag=RelicTag.ENERGY_STONE),
        Relic("r_gold",     "Anillo de Oro",
              "+15 de oro extra por victoria de combate.",  tag=RelicTag.GOLD_RING),
        Relic("r_iron",     "Corazón de Hierro",
              "+15 de HP máximo permanente.",               tag=RelicTag.IRON_HEART),
        Relic("r_blood",    "Poción de Sangre",
              "Recupera 8 HP después de cada combate.",    tag=RelicTag.BLOOD_POTION),
        Relic("r_vitality", "Amuleto de Vitalidad",
              "+10 de HP máximo permanente.",               tag=RelicTag.VITALITY_AMULET),
        Relic("r_clover",   "Trébol de Siete Hojas",
              "+100 de suerte: muchas más cartas y reliquias doradas y de mayor rareza.",
              tag=RelicTag.SEVEN_LEAF_CLOVER),
        Relic("r_panacea",  "Panacea",
              "Eres inmune a cualquier debuff de los enemigos.", tag=RelicTag.PANACEA),
        Relic("r_fount",    "Fuente Eterna",
              "Al inicio de cada turno ganas 1 de maná máximo.", tag=RelicTag.ETERNAL_FOUNT),
        Relic("r_ankh",     "Ankh",
              "Al recibir un golpe fatal, revives con toda tu vida (una vez).",
              tag=RelicTag.ANKH),
        Relic("r_mirror",   "Espejo Singular",
              "Al obtenerla, elimina todas tus cartas repetidas: te quedas con una copia de cada carta.",
              tag=RelicTag.SINGULAR_MIRROR),
        Relic("r_brooch",   "Broche de Evasión",
              "Cada vez que activas un Combo, ganas 1 de bloqueo.",
              tag=RelicTag.EVASION_BROOCH, relic_class=CardClass.ROGUE),
        Relic("r_knife",    "Cuchillo Arrojadizo",
              "Cada vez que activas un Combo, inflige 1 de daño a un enemigo al azar.",
              tag=RelicTag.THROWING_KNIFE, relic_class=CardClass.ROGUE),
        # La Pícara — Combo, Despojo, dagas y veneno
        Relic("r_rag_sack", "Saco de Trapos",
              "Cada vez que activas un Despojo, ganas 2 de escudo.",
              tag=RelicTag.RAG_SACK, relic_class=CardClass.ROGUE),
        Relic("r_scarf",    "Pañuelo del Duelista",
              "Cuando una carta activa su Combo, hace +2 de daño y da +2 de escudo.",
              tag=RelicTag.DUELIST_SCARF, relic_class=CardClass.ROGUE),
        Relic("r_hook",     "Garfio",
              "La primera vez que activas un Despojo cada turno, robas 1 carta.",
              tag=RelicTag.GRAPPLING_HOOK, relic_class=CardClass.ROGUE),
        Relic("r_ribbon",   "Cinta Roja",
              "En el primer turno de cada combate, tus Combos se activan sin jugar otra carta antes.",
              tag=RelicTag.CRIMSON_RIBBON, relic_class=CardClass.ROGUE),
        Relic("r_pocket",   "Bolsillo Roto",
              "Al inicio de cada turno, tras robar, descarta una carta al azar y roba 1.",
              tag=RelicTag.TORN_POCKET, relic_class=CardClass.ROGUE),
        Relic("r_split",    "Daga Partida",
              "Tus efectos de Despojo se activan dos veces.",
              tag=RelicTag.SPLIT_DAGGER, relic_class=CardClass.ROGUE),
        Relic("r_pouch",    "Bolsa de Dagas",
              "Al inicio de cada combate, mete 2 Dagas Ocultas en tu pila de robo.",
              tag=RelicTag.DAGGER_POUCH, relic_class=CardClass.ROGUE),
        Relic("r_sheath",   "Vaina Afilada",
              "Tus Dagas Ocultas hacen +2 de daño.",
              tag=RelicTag.SHARP_SHEATH, relic_class=CardClass.ROGUE),
        Relic("r_vial",     "Frasco de Veneno",
              "Tu primer ataque de cada turno aplica 1 de Veneno.",
              tag=RelicTag.POISON_VIAL, relic_class=CardClass.ROGUE),
        Relic("r_fang",     "Colmillo de Víbora",
              "Cuando un enemigo muere envenenado, su Veneno pasa a otro enemigo al azar.",
              tag=RelicTag.VIPER_FANG, relic_class=CardClass.ROGUE),
        # Neutrales
        Relic("r_mask",     "Máscara del Ladrón",
              "+25% de oro en los combates y la tienda es un 10% más barata.",
              tag=RelicTag.THIEF_MASK),
        Relic("r_coin",     "Moneda de la Suerte",
              "Si un efecto al azar golpea dos veces seguidas al mismo enemigo, ganas 1 de maná "
              "(una vez por turno).", tag=RelicTag.LUCKY_COIN),
        Relic("r_horseshoe", "Herradura de Plata",
              "+30 de suerte.", tag=RelicTag.SILVER_HORSESHOE),
        Relic("r_glove",    "Guante de Seda",
              "La tercera carta que juegas cada turno cuesta 0.", tag=RelicTag.SILK_GLOVE),
        Relic("r_boots",    "Botas Silenciosas",
              "En el primer turno de cada combate robas 2 cartas extra.", tag=RelicTag.SILENT_BOOTS),
        Relic("r_thread",   "Hilo de Araña",
              "Si terminas el turno sin cartas en la mano, ganas 6 de escudo.",
              tag=RelicTag.SPIDER_THREAD),
        Relic("r_key",      "Llave Maestra",
              "Las salas del tesoro te dejan elegir entre 2 reliquias.", tag=RelicTag.MASTER_KEY),
        Relic("r_interest", "Interés Compuesto",
              "Cada vez que ganas oro, ganas además un 10% de tu oro total.",
              tag=RelicTag.COMPOUND_INTEREST),
        Relic("r_clock",    "Reloj Roto",
              "Una vez por combate, al quedarte en 0 de maná con cartas en la mano, recuperas todo el maná.",
              tag=RelicTag.BROKEN_CLOCK),
        Relic("r_scar",     "Cicatriz",
              "Empiezas cada combate con 1 de Fuerza.", tag=RelicTag.SCAR),
        Relic("r_bracer",   "Brazal de Guerra",
              "Al empezar cada combate ganas 8 de escudo.", tag=RelicTag.WAR_BRACER),
        # La Guerrera — vida, curación, escudo y Fuerza
        Relic("r_iron_fang", "Colmillo de Hierro",
              "Tu primer ataque de cada turno te cura 2.",
              tag=RelicTag.IRON_FANG, relic_class=CardClass.WARRIOR),
        Relic("r_bandage",  "Venda Empapada",
              "La primera vez que pierdes vida en tu turno, robas 1 carta.",
              tag=RelicTag.SOAKED_BANDAGE, relic_class=CardClass.WARRIOR),
        Relic("r_blood_cup", "Copa de Sangre",
              "Todas tus curaciones en combate curan 2 más.",
              tag=RelicTag.BLOOD_CUP, relic_class=CardClass.WARRIOR),
        Relic("r_banner",   "Estandarte Desgarrado",
              "Cada 3 veces que activas Furia, ganas 1 de Fuerza.",
              tag=RelicTag.TORN_BANNER, relic_class=CardClass.WARRIOR),
        Relic("r_titan",    "Corazón de Titán",
              "La curación que sobrepasa tu vida máxima te da el doble de escudo.",
              tag=RelicTag.TITAN_HEART, relic_class=CardClass.WARRIOR),
        # Neutrales (2026-10-17)
        Relic("r_diamond_cards", "Cartas de Diamante",
              "Tus cartas doradas pasan a ser de Diamante: se lanzan 3 veces en lugar de 2.",
              tag=RelicTag.DIAMOND_CARDS),
        Relic("r_collector_seal", "Sello del Coleccionista",
              "Ya no te salen cartas Comunes ni Poco comunes en sobres ni recompensas.",
              tag=RelicTag.COLLECTOR_SEAL),
        Relic("r_antiquary_seal", "Sello del Anticuario",
              "Ya no te salen reliquias Comunes ni Poco comunes.",
              tag=RelicTag.ANTIQUARY_SEAL),
        Relic("r_stairway", "Escalera",
              "Si este turno juegas 3 cartas seguidas que cuesten 1 de maná más que la anterior (p. ej. 0-1-2), ganas +1 de Daño y +1 de Destreza para el resto del combate.",
              tag=RelicTag.STAIRWAY),
        Relic("r_unique_piece", "Pieza Única",
              "Si tu mazo no tiene cartas repetidas, la primera carta que juegas cada turno cuesta 1 menos.",
              tag=RelicTag.UNIQUE_PIECE),
        Relic("r_tailor_scissors", "Tijeras del Sastre",
              "Al obtenerla, elimina 3 cartas de tu mazo a tu elección.",
              tag=RelicTag.TAILOR_SCISSORS),
        Relic("r_whetstone", "Piedra de Afilar",
              "Tu primer ataque de cada combate hace +6 de daño.",
              tag=RelicTag.WHETSTONE),
        Relic("r_ragged_cape", "Capa Raída",
              "Al final de tu turno, si no tienes escudo, ganas 3.",
              tag=RelicTag.RAGGED_CAPE),
        Relic("r_votive_candle", "Vela Votiva",
              "Al empezar cada combate, el enemigo con más vida recibe 1 de Débil.",
              tag=RelicTag.VOTIVE_CANDLE),
        Relic("r_white_flag", "Bandera Blanca",
              "El primer golpe que recibes en cada combate hace 4 menos de daño.",
              tag=RelicTag.WHITE_FLAG),
        Relic("r_dandelion", "Diente de León",
              "Cada vez que derrotas a un enemigo, te curas 3.",
              tag=RelicTag.DANDELION),
        Relic("r_oil_lamp", "Lámpara de Aceite",
              "En tu primer turno de cada combate, tus cartas de escudo dan +3.",
              tag=RelicTag.OIL_LAMP),
        Relic("r_wild_fruit", "Fruta Silvestre",
              "Al obtenerla, +7 de vida máxima.",
              tag=RelicTag.WILD_FRUIT),
        Relic("r_antidote", "Antídoto",
              "Eres inmune al Veneno.",
              tag=RelicTag.ANTIDOTE),
        Relic("r_war_horn", "Cuerno de Guerra",
              "En el turno 3 de cada combate, tus ataques hacen +4 de daño.",
              tag=RelicTag.WAR_HORN),
        Relic("r_sandbag", "Saco de Arena",
              "Si terminas el turno habiendo jugado 3 cartas o más, ganas 4 de escudo.",
              tag=RelicTag.SANDBAG),
        Relic("r_chess_piece", "Ficha de Ajedrez",
              "Si en un turno juegas exactamente 2 cartas, ganas 5 de escudo.",
              tag=RelicTag.CHESS_PIECE),
        Relic("r_old_scroll", "Pergamino Viejo",
              "La primera Habilidad de cada combate cuesta 0.",
              tag=RelicTag.OLD_SCROLL),
        Relic("r_tidy_pile", "Pila Ordenada",
              "Cada vez que barajas tu descarte en la pila de robo, ganas 4 de escudo.",
              tag=RelicTag.TIDY_PILE),
        Relic("r_monk_wraps", "Vendas del Monje",
              "El primer debuff que recibes en cada combate no te afecta.",
              tag=RelicTag.MONK_WRAPS),
        Relic("r_spyglass", "Catalejo",
              "Puedes ver las 3 primeras cartas de tu pila de robo.",
              tag=RelicTag.SPYGLASS),
        Relic("r_rabbit_foot", "Pata de Conejo",
              "+15 de suerte.",
              tag=RelicTag.RABBIT_FOOT),
        Relic("r_thorn_crown", "Corona de Espinas",
              "Cada vez que un enemigo te golpea, recibe 2 de daño.",
              tag=RelicTag.THORN_CROWN),
        Relic("r_frost_amulet", "Amuleto de Escarcha",
              "Al empezar cada combate, un enemigo normal al azar queda Congelado (pierde su primera acción). No afecta a jefes ni élites.",
              tag=RelicTag.FROST_AMULET),
        Relic("r_breach_spear", "Lanza de Ruptura",
              "Tus ataques contra enemigos con escudo hacen +3 de daño.",
              tag=RelicTag.BREACH_SPEAR),
        Relic("r_pendulum", "Péndulo",
              "En turnos pares tus ataques hacen +2 de daño; en turnos impares tus cartas de escudo dan +2.",
              tag=RelicTag.PENDULUM),
        Relic("r_balance_bracelet", "Brazalete del Equilibrio",
              "Si en un turno juegas tantos Ataques como Habilidades (al menos 1 de cada), ganas 5 de escudo.",
              tag=RelicTag.BALANCE_BRACELET),
        Relic("r_empty_bowl", "Cuenco Vacío",
              "Al final de tu turno, ganas 3 de escudo por cada maná que no gastaste.",
              tag=RelicTag.EMPTY_BOWL),
        Relic("r_hourglass", "Reloj de Arena",
              "Cada 4 turnos de combate, robas 1 carta extra.",
              tag=RelicTag.HOURGLASS),
        Relic("r_anchor", "Ancla",
              "Tu escudo del primer turno de cada combate no se pierde al empezar el segundo.",
              tag=RelicTag.ANCHOR),
        Relic("r_marked_cards", "Cartas Marcadas",
              "Al obtenerla, eliges 1 carta de tu mazo: empezarás cada combate con ella en la mano.",
              tag=RelicTag.MARKED_CARDS),
        Relic("r_veteran_medal", "Medalla del Veterano",
              "Cada vez que vences a una élite, +3 de vida máxima.",
              tag=RelicTag.VETERAN_MEDAL),
        Relic("r_laurel_leaf", "Hoja de Laurel",
              "Al vencer a un jefe, te curas toda la vida.",
              tag=RelicTag.LAUREL_LEAF),
        Relic("r_phoenix_feather", "Pluma de Fénix",
              "Si empiezas un combate con menos de la mitad de vida, te curas 8.",
              tag=RelicTag.PHOENIX_FEATHER),
        Relic("r_last_breath", "Talismán del Último Aliento",
              "La primera vez en cada combate que bajas del 25 % de vida, ganas 15 de escudo.",
              tag=RelicTag.LAST_BREATH),
        Relic("r_shackle", "Grillete",
              "Todos los enemigos empiezan el combate con 1 de Vulnerable.",
              tag=RelicTag.SHACKLE),
        Relic("r_magic_deck", "Baraja Mágica",
              "La primera vez en cada combate que tu pila de robo se queda vacía, robas 1 carta.",
              tag=RelicTag.MAGIC_DECK),
        Relic("r_arcane_battery", "Batería Arcana",
              "Si terminas el turno con maná sin gastar, guardas 1 para el siguiente turno.",
              tag=RelicTag.ARCANE_BATTERY),
        Relic("r_stone_heart", "Corazón de Piedra",
              "+30 de vida máxima, pero no puedes curarte durante los combates.",
              tag=RelicTag.STONE_HEART),
        Relic("r_prism", "Prisma",
              "Tus cartas doradas cuestan 1 menos (mínimo 1).",
              tag=RelicTag.PRISM),
        Relic("r_touchstone", "Piedra de Toque",
              "Tus cartas mejoradas hacen +2 de daño y dan +2 de escudo.",
              tag=RelicTag.TOUCHSTONE),
        Relic("r_bottomless_bag", "Bolsa sin Fondo",
              "Los sobres dorados te dejan quedarte con 3 cartas en lugar de 2.",
              tag=RelicTag.BOTTOMLESS_BAG),
        Relic("r_cursed_contract", "Contrato Maldito",
              "+1 de maná por turno, pero cada combate empieza con una carta Herida (Injugable) en tu pila de robo.",
              tag=RelicTag.CURSED_CONTRACT),
        Relic("r_d20", "Dado de Veinte Caras",
              "Al empezar cada combate, una carta al azar de tu mano inicial se vuelve dorada durante ese combate.",
              tag=RelicTag.D20),
        Relic("r_mana_vial", "Ampolla de Maná",
              "Una vez por turno, si juegas 4 cartas y te quedas sin maná, recuperas 1.",
              tag=RelicTag.MANA_VIAL),
        Relic("r_leaky_purse", "Bolsa Agujereada",
              "Ganas 5 de oro al terminar cada sala.",
              tag=RelicTag.LEAKY_PURSE),
        Relic("r_canteen", "Cantimplora",
              "Si ganas un combate sin perder vida, +15 de oro.",
              tag=RelicTag.CANTEEN),
        Relic("r_voucher", "Vale de Descuento",
              "En la próxima tienda que visites, una reliquia es gratis (se gasta al usarlo).",
              tag=RelicTag.VOUCHER),
        Relic("r_miner_pick", "Pico de Minero",
              "Las salas del tesoro dan además 25 de oro.",
              tag=RelicTag.MINER_PICK),
        Relic("r_piggy_bank", "Hucha",
              "Al entrar en una tienda, ganas 1 de oro por cada 10 que tengas (máx. 15).",
              tag=RelicTag.PIGGY_BANK),
        Relic("r_grinning_skull", "Calavera Sonriente",
              "Las élites dan +30 de oro.",
              tag=RelicTag.GRINNING_SKULL),
        Relic("r_portable_anvil", "Yunque Portátil",
              "Al obtenerla, mejora 1 carta al azar de tu mazo.",
              tag=RelicTag.PORTABLE_ANVIL),
        Relic("r_loaded_die", "Dado Cargado",
              "Una vez por sobre, puedes volver a tirar las cartas que ofrece.",
              tag=RelicTag.LOADED_DIE),
        Relic("r_member_card", "Tarjeta de Socio",
              "La primera compra en cada tienda cuesta la mitad.",
              tag=RelicTag.MEMBER_CARD),
        Relic("r_hunting_trophy", "Trofeo de Caza",
              "Si ganas un combate en 3 turnos o menos, +20 de oro.",
              tag=RelicTag.HUNTING_TROPHY),
        Relic("r_smith_hammer", "Martillo del Herrero",
              "El Brujo te cobra la mitad por mejorar cartas.",
              tag=RelicTag.SMITH_HAMMER),
        Relic("r_iron_file", "Lima de Hierro",
              "Al obtenerla, elimina 1 carta básica de tu mazo inicial.",
              tag=RelicTag.IRON_FILE),
        Relic("r_appraiser_lens", "Lupa del Tasador",
              "Las recompensas de combate ofrecen 1 carta más para elegir.",
              tag=RelicTag.APPRAISER_LENS),
        Relic("r_two_faced_coin", "Moneda de Dos Caras",
              "Una tirada gratis de gachapón por piso.",
              tag=RelicTag.TWO_FACED_COIN),
        Relic("r_broken_chain", "Cadena Rota",
              "Las cartas de estado que te meten los enemigos se vuelven Etéreas.",
              tag=RelicTag.BROKEN_CHAIN),
        # La Guerrera (2026-10-17)
        Relic("r_spiked_gauntlet", "Guantelete de Púas",
              "Cada vez que pierdes vida por tus cartas, inflige 2 de daño a un enemigo al azar.",
              tag=RelicTag.SPIKED_GAUNTLET, relic_class=CardClass.WARRIOR),
        Relic("r_wristguard", "Muñequera",
              "Tus cartas con Aguante dan +2 de escudo.",
              tag=RelicTag.WRISTGUARD, relic_class=CardClass.WARRIOR),
        Relic("r_field_bandage", "Venda de Campaña",
              "Al final de tu turno, si perdiste vida este turno, te curas 2.",
              tag=RelicTag.FIELD_BANDAGE, relic_class=CardClass.WARRIOR),
        Relic("r_dented_plate", "Peto Abollado",
              "Tus cartas de escudo dan +1 por cada 10 de vida que te faltan.",
              tag=RelicTag.DENTED_PLATE, relic_class=CardClass.WARRIOR),
        Relic("r_fang_necklace", "Collar de Colmillos",
              "Cada vez que matas a un enemigo, +1 de Fuerza para ese combate.",
              tag=RelicTag.FANG_NECKLACE, relic_class=CardClass.WARRIOR),
        Relic("r_notched_axe", "Hacha Mellada",
              "Tu primer ataque con Furia de cada turno hace +4 de daño.",
              tag=RelicTag.NOTCHED_AXE, relic_class=CardClass.WARRIOR),
        Relic("r_blood_skin", "Odre de Sangre",
              "Si empiezas un combate con la vida llena, pierdes 5 y ganas 2 de Fuerza.",
              tag=RelicTag.BLOOD_SKIN, relic_class=CardClass.WARRIOR),
        Relic("r_blood_gem", "Gema de Sangre",
              "La primera vez que te curas 10 o más en un turno, robas 1 carta.",
              tag=RelicTag.BLOOD_GEM, relic_class=CardClass.WARRIOR),
        Relic("r_martyr_shield", "Escudo del Mártir",
              "Cada vez que pierdes vida por tus cartas, ganas el doble de esa cantidad en escudo.",
              tag=RelicTag.MARTYR_SHIELD, relic_class=CardClass.WARRIOR),
        Relic("r_crimson_chalice", "Cáliz Carmesí",
              "Tu curación sobrante también hace ese daño a un enemigo al azar.",
              tag=RelicTag.CRIMSON_CHALICE, relic_class=CardClass.WARRIOR),
        Relic("r_war_drum", "Tambor de Guerra",
              "Cada 3 veces que activas Aguante, +1 de Fuerza.",
              tag=RelicTag.WAR_DRUM, relic_class=CardClass.WARRIOR),
        Relic("r_brazier", "Brasero",
              "Si empiezas tu turno sin escudo, tus ataques hacen +3 de daño ese turno.",
              tag=RelicTag.BRAZIER, relic_class=CardClass.WARRIOR),
        Relic("r_worn_roundel", "Rodela Gastada",
              "Al empezar tu turno, en lugar de perder todo tu escudo, conservas la mitad.",
              tag=RelicTag.WORN_ROUNDEL, relic_class=CardClass.WARRIOR),
        Relic("r_berserker_helm", "Yelmo del Berserker",
              "Mientras estés por debajo de la mitad de vida, tus ataques hacen +3 de daño.",
              tag=RelicTag.BERSERKER_HELM, relic_class=CardClass.WARRIOR),
        Relic("r_blood_rune", "Runa de Sangre",
              "Furia también se activa si un enemigo te hizo daño en su último turno.",
              tag=RelicTag.BLOOD_RUNE, relic_class=CardClass.WARRIOR),
        Relic("r_legion_banner", "Estandarte de la Legión",
              "Si empiezas tu turno con más escudo que todo el daño que anuncian los enemigos, +1 de Fuerza.",
              tag=RelicTag.LEGION_BANNER, relic_class=CardClass.WARRIOR),
        Relic("r_racing_heart", "Corazón Desbocado",
              "Tu Fuerza se duplica al empezar un combate contra un jefe.",
              tag=RelicTag.RACING_HEART, relic_class=CardClass.WARRIOR),
        Relic("r_molten_iron", "Hierro Fundido",
              "Tu primer ataque de cada turno suma tu escudo a su daño (máx. +15).",
              tag=RelicTag.MOLTEN_IRON, relic_class=CardClass.WARRIOR),
        # El Mago (2026-10-17)
        Relic("r_tinder", "Yesca",
              "Tus cartas que aplican Fuego aplican +1.",
              tag=RelicTag.TINDER, relic_class=CardClass.MAGE),
        Relic("r_seashell", "Concha Marina",
              "Tus cartas que aplican Agua aplican +1.",
              tag=RelicTag.SEASHELL, relic_class=CardClass.MAGE),
        Relic("r_pumice", "Piedra Pómez",
              "Tus cartas que aplican Tierra aplican +1.",
              tag=RelicTag.PUMICE, relic_class=CardClass.MAGE),
        Relic("r_griffin_feather", "Pluma de Grifo",
              "Tus cartas que aplican Aire aplican +1.",
              tag=RelicTag.GRIFFIN_FEATHER, relic_class=CardClass.MAGE),
        Relic("r_willow_wand", "Varita de Sauce",
              "Al empezar cada combate, un enemigo al azar recibe 2 de Agua.",
              tag=RelicTag.WILLOW_WAND, relic_class=CardClass.MAGE),
        Relic("r_water_clock", "Reloj de Agua",
              "La primera vez que activas Vacío cada turno, ganas 4 de escudo.",
              tag=RelicTag.WATER_CLOCK, relic_class=CardClass.MAGE),
        Relic("r_pointy_hat", "Sombrero Puntiagudo",
              "Tus cartas de 0 de maná aplican +1 del elemento que tengan.",
              tag=RelicTag.POINTY_HAT, relic_class=CardClass.MAGE),
        Relic("r_lava_stone", "Piedra de Lava",
              "Incendio extiende 1 de Fuego más a cada enemigo.",
              tag=RelicTag.LAVA_STONE, relic_class=CardClass.MAGE),
        Relic("r_witch_broom", "Escoba de Brujo",
              "Tormenta de Arena aplica Débil 2 en lugar de 1.",
              tag=RelicTag.WITCH_BROOM, relic_class=CardClass.MAGE),
        Relic("r_cauldron", "Caldero",
              "Vapor también aplica 1 de Débil.",
              tag=RelicTag.CAULDRON, relic_class=CardClass.MAGE),
        Relic("r_volcano_ember", "Ascua de Volcán",
              "Magma hace además 5 de daño.",
              tag=RelicTag.VOLCANO_EMBER, relic_class=CardClass.MAGE),
        Relic("r_storm_orb", "Orbe de Tormenta",
              "Cada reacción que provocas hace 3 de daño a un enemigo al azar.",
              tag=RelicTag.STORM_ORB, relic_class=CardClass.MAGE),
        Relic("r_blank_grimoire", "Grimorio en Blanco",
              "Cada 3 veces que activas Vacío, robas 1 carta.",
              tag=RelicTag.BLANK_GRIMOIRE, relic_class=CardClass.MAGE),
        Relic("r_lesser_fount", "Fuente Menor",
              "Cuando activas Vacío con una carta de 3 de maná o más, recuperas 1 de maná.",
              tag=RelicTag.LESSER_FOUNT, relic_class=CardClass.MAGE),
        Relic("r_frost_crystal", "Cristal de Escarcha",
              "Congelar dura 1 turno más en enemigos normales.",
              tag=RelicTag.FROST_CRYSTAL, relic_class=CardClass.MAGE),
        Relic("r_prismatic_lens", "Lente Prismática",
              "La primera reacción de cada combate ocurre 2 veces.",
              tag=RelicTag.PRISMATIC_LENS, relic_class=CardClass.MAGE),
        Relic("r_archmage_cloak", "Capa del Archimago",
              "El Daño del héroe también se suma al daño en área de tus cartas.",
              tag=RelicTag.ARCHMAGE_CLOAK, relic_class=CardClass.MAGE),
        Relic("r_ring_of_four", "Anillo de los Cuatro",
              "Si en un mismo turno aplicas los 4 elementos, +1 de maná máximo para el resto del combate.",
              tag=RelicTag.RING_OF_FOUR, relic_class=CardClass.MAGE),
        # La Pícara (2026-10-17)
        Relic("r_pocket_sharpener", "Afiladora de Bolsillo",
              "La primera Daga Oculta de cada combate hace +4 de daño.",
              tag=RelicTag.POCKET_SHARPENER, relic_class=CardClass.ROGUE),
        Relic("r_folding_knife", "Navaja Plegable",
              "Al empezar cada combate, el enemigo con menos vida queda con 2 de Marcado.",
              tag=RelicTag.FOLDING_KNIFE, relic_class=CardClass.ROGUE),
        Relic("r_marble_bag", "Bolsa de Canicas",
              "Al empezar cada combate, descarta 1 carta al azar de tu mano y ganas 3 de escudo (activa Despojo).",
              tag=RelicTag.MARBLE_BAG, relic_class=CardClass.ROGUE),
        Relic("r_rascal_boots", "Botas de Ratero",
              "Si ganas un combate sin perder vida, +2 de suerte permanente.",
              tag=RelicTag.RASCAL_BOOTS, relic_class=CardClass.ROGUE),
        Relic("r_thief_glove", "Guante de Ladrón",
              "Cada vez que descartas por un efecto, ganas 1 de oro (máx. 10 por combate).",
              tag=RelicTag.THIEF_GLOVE, relic_class=CardClass.ROGUE),
        Relic("r_scorpion_venom", "Veneno de Escorpión",
              "El Veneno que aplicas a un enemigo Marcado se duplica.",
              tag=RelicTag.SCORPION_VENOM, relic_class=CardClass.ROGUE),
        Relic("r_black_silk", "Hilo de Seda Negra",
              "El Marcado de los enemigos dura hasta el final de tu siguiente turno.",
              tag=RelicTag.BLACK_SILK, relic_class=CardClass.ROGUE),
        Relic("r_bone_die", "Dado de Hueso",
              "Tus cartas de suerte tiran una vez más y se quedan con el mejor resultado.",
              tag=RelicTag.BONE_DIE, relic_class=CardClass.ROGUE),
        Relic("r_mist_flask", "Frasco de Neblina",
              "La primera vez que activas Despojo cada turno, el enemigo con más vida recibe 1 de Débil.",
              tag=RelicTag.MIST_FLASK, relic_class=CardClass.ROGUE),
        Relic("r_lockpick", "Ganzúa",
              "Las salas del tesoro dan además 20 de oro.",
              tag=RelicTag.LOCKPICK, relic_class=CardClass.ROGUE),
        Relic("r_harlequin_mask", "Máscara de Arlequín",
              "Tu tercer Combo de cada turno hace +5 de daño.",
              tag=RelicTag.HARLEQUIN_MASK, relic_class=CardClass.ROGUE),
        Relic("r_capuche", "Capucha de Sombras",
              "En el primer turno de cada combate, el primer ataque enemigo hace la mitad de daño.",
              tag=RelicTag.CAPUCHE, relic_class=CardClass.ROGUE),
        Relic("r_poisoned_scarf", "Pañuelo Envenenado",
              "Tu primer Combo de cada turno aplica 2 de Veneno al objetivo.",
              tag=RelicTag.POISONED_SCARF, relic_class=CardClass.ROGUE),
        Relic("r_twin_daggers", "Dagas Gemelas",
              "Tus Dagas Ocultas golpean también a otro enemigo por la mitad de daño.",
              tag=RelicTag.TWIN_DAGGERS, relic_class=CardClass.ROGUE),
        Relic("r_fox_tail", "Cola de Zorro",
              "Tus Dagas Ocultas hacen +1 de daño por cada 3 de Veneno del objetivo.",
              tag=RelicTag.FOX_TAIL, relic_class=CardClass.ROGUE),
        Relic("r_stolen_watch", "Reloj de Bolsillo Robado",
              "Si juegas 6 cartas en un turno, la siguiente cuesta 0.",
              tag=RelicTag.STOLEN_WATCH, relic_class=CardClass.ROGUE),
        Relic("r_singular_locket", "Medallón Singular",
              "Si tu mazo no tiene cartas repetidas, empiezas cada combate con 1 Daga Oculta en la mano.",
              tag=RelicTag.SINGULAR_LOCKET, relic_class=CardClass.ROGUE),
        Relic("r_thief_king_crown", "Corona del Rey Ladrón",
              "Cuando un enemigo muere envenenado, tu siguiente carta cuesta 1 menos.",
              tag=RelicTag.THIEF_KING_CROWN, relic_class=CardClass.ROGUE),
    ]


def max_hp(run: Run) -> int:
    """The hero's max HP: character + relics + what the run won (Medalla del Veterano)."""
    return run.character.stats.max_hp + relic_effects.max_hp_bonus(run.relics) + run.bonus_max_hp


def acquire_relic(run: Run, relic: Relic) -> None:
    """Add ``relic`` to the run and apply its on-pickup effects (treasure, boss and shop).

    * Every relic: max HP is recomputed (Corazón de Hierro, Amuleto de Vitalidad, Fruta Silvestre…).
    * Espejo Singular: removes every repeated card, keeping one copy of each.
    * Cartas de Diamante: golden cards of the deck become diamond.
    * Yunque Portátil: upgrades one random card. Lima de Hierro: removes one basic card.
    * Tijeras del Sastre / Cartas Marcadas: ask the deck screen (``Run.pending_choices``).
    """
    run.add_relic(relic)
    run.player_max_hp = max_hp(run)
    run.player_current_hp = min(run.player_current_hp, run.player_max_hp)
    times = relic.effect_multiplier()
    if relic.tag is RelicTag.SINGULAR_MIRROR:
        run.deck = relic_effects.remove_duplicate_cards(run.deck)
    elif relic.tag is RelicTag.DIAMOND_CARDS:
        from src.domain.chroma import Chroma
        for card in run.deck:
            if card.chroma is Chroma.GOLDEN:
                card.chroma = Chroma.DIAMOND
    elif relic.tag is RelicTag.PORTABLE_ANVIL:
        from src.domain.card_upgrade import apply_upgrade, can_upgrade
        rng = random.Random(run.seed * 31 + len(run.relics))
        for _ in range(times):
            options = [c for c in run.deck if can_upgrade(c)]
            if options:
                apply_upgrade(rng.choice(options))
    elif relic.tag is RelicTag.IRON_FILE:
        for _ in range(times):
            basic = [i for i, c in enumerate(run.deck) if c.id.endswith("_base")]
            if basic and len(run.deck) > 1:
                run.deck.pop(basic[0])
    elif relic.tag is RelicTag.TAILOR_SCISSORS:
        run.pending_choices.append(("remove", 3 * times))
    elif relic.tag is RelicTag.MARKED_CARDS:
        run.pending_choices.append(("innate", times))


def _relic_pool(run: Run, minimum: int = 1) -> list[Relic]:
    """Relics this hero can find (neutral + own class), not owned yet.

    If fewer than ``minimum`` remain, owned ones come back (duplicates allowed).
    """
    own = class_for_character(run.character.id)
    allowed = [r for r in _all_relic_defs() if r.relic_class in (CardClass.NEUTRAL, own)]
    if relic_effects.has_tag(run.relics, RelicTag.ANTIQUARY_SEAL):     # Sello del Anticuario
        high = [r for r in allowed if r.rarity.value >= 3]
        allowed = high or allowed
    owned_tags = {r.tag for r in run.relics}
    pool = [r for r in allowed if r.tag not in owned_tags]
    return pool if len(pool) >= minimum else allowed


def run_luck(run: Run) -> int:
    """Luck used for drop odds: character luck + Pruebas bonus + relics (Trébol: +100)."""
    return hero_luck(run.character.stats.luck) + relic_effects.luck_bonus(run.relics) + run.bonus_luck


def _pick_relics(pool: list[Relic], count: int, rng: random.Random, luck: int) -> list[Relic]:
    """``count`` distinct relics, higher tiers likelier with more luck (``rarity.weighted_sample``)."""
    return weighted_sample(pool, count, rng, rarity_of=lambda r: r.rarity, luck=luck)


def _with_chroma(relics: list[Relic], rng: random.Random, luck: int = 0) -> list[Relic]:
    """Each offered relic may get a chroma (8 % golden, boosted by luck)."""
    for relic in relics:
        relic.chroma = roll_chroma(rng, for_relic=True, luck=luck)
    return relics


def pick_treasure_relic(run: Run, room_id: str) -> Relic:
    """Choose a relic not already owned by the player."""
    return pick_treasure_relics(run, room_id)[0]


def pick_treasure_relics(run: Run, room_id: str) -> list[Relic]:
    """Relics offered by a treasure room: 1, or more with Llave Maestra (pick one)."""
    count = relic_effects.treasure_choices(run.relics)
    pool = _relic_pool(run, count)
    rng = random.Random(_enemy_seed(run, room_id) ^ 0x1234)
    relics = _pick_relics(pool, min(count, len(pool)), rng, run_luck(run))
    return _with_chroma(relics, rng, run_luck(run))


def pick_elite_relic(run: Run, room_id: str) -> Relic:
    """The relic an elite drops (luck-weighted like a treasure, may be golden)."""
    pool = _relic_pool(run, 1)
    rng = random.Random(_enemy_seed(run, room_id) ^ 0xE1173)
    return _with_chroma(_pick_relics(pool, 1, rng, run_luck(run)), rng, run_luck(run))[0]


def shop_price(run: Run, base: int) -> int:
    """What a shop item costs this run (Máscara del Ladrón discounts it)."""
    return relic_effects.shop_price(run.relics, base)


def pick_boss_relics(run: Run, count: int = 3) -> list[Relic]:
    """Choose `count` distinct relics for the boss reward screen."""
    pool = _relic_pool(run, count)
    rng = random.Random(run.seed * 37 + run.floor * 13)
    return _with_chroma(_pick_relics(pool, count, rng, run_luck(run)), rng, run_luck(run))


# ---------------------------------------------------------------------------
# Floor advance
# ---------------------------------------------------------------------------

def advance_floor(run: Run) -> None:
    """Move the run to the next floor and generate a fresh map."""
    run.floor      += 1
    run.current_map = generate_map(run.seed, run.floor)
    # Update max HP in case IRON_HEART was picked up this floor
    run.player_max_hp = max_hp(run)


def pick_shop_stock(run: Run) -> tuple[list[PackDef], list[Relic]]:
    """Choose three distinct offers of each kind, stable for this room."""
    rng = random.Random(f"shop:{run.seed}:{run.floor}:{run.current_room_id}")
    pool = _relic_pool(run, 3)
    packs, relics = rng.sample(ALL_PACKS, 3), _pick_relics(pool, 3, rng, run_luck(run))
    relics = _with_chroma(relics, rng, run_luck(run))
    packs = [replace(p, chroma=roll_chroma(rng, kind="pack", luck=run_luck(run))) for p in packs]
    return packs, relics
