"""Run lifecycle management.

Responsibilities:
  - Creating a new Run from a chosen character + seed.
  - Generating enemies appropriate for the current floor.
  - Post-combat state updates (HP, gold, relic heal).
  - Generating events (gold rewards).
  - Generating treasure (relic selection pool).
  - Generating boss enemy.
"""
from __future__ import annotations

import random
import zlib
from dataclasses import replace

from src.application import enemy_roster, enemy_ai, relic_effects
from src.application.map_generator import generate_map
from src.domain.card import CardClass
from src.domain.card_pool import ALL_PACKS, PackDef, class_for_character, starter_deck
from src.domain.character import Character
from src.domain.chroma import roll_chroma
from src.domain.rarity import weighted_sample
from src.domain.entities import Enemy, Intent, IntentType
from src.domain.relic import Relic, RelicTag
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
    rng = random.Random(_enemy_seed(run, room_id))
    return enemy_roster.roll_encounter(rng, run.floor, room_id, TUNING.forced_encounter)


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


def apply_combat_victory(run: Run, hp_after: int, enemies: list[Enemy], bonus_gold: int = 0) -> int:
    """Update run state after winning a combat.  Returns gold earned.

    ``bonus_gold``: gold won during the fight (``CombatState.gold_earned``, e.g. Carterista).
    """
    heal   = relic_effects.post_combat_heal(run.relics)
    new_hp = min(hp_after + heal, run.player_max_hp)
    run.apply_combat_result(new_hp)
    gold = _combat_gold(run, enemies) + max(0, bonus_gold)
    gain_gold(run, gold)
    return gold


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
    ]


def acquire_relic(run: Run, relic: Relic) -> None:
    """Add ``relic`` to the run and apply its on-pickup effects (treasure, boss and shop).

    * Every relic: max HP is recomputed (Corazón de Hierro, Amuleto de Vitalidad).
    * Espejo Singular: removes every repeated card, keeping one copy of each.
    """
    run.add_relic(relic)
    run.player_max_hp = run.character.stats.max_hp + relic_effects.max_hp_bonus(run.relics)
    if relic.tag is RelicTag.SINGULAR_MIRROR:
        run.deck = relic_effects.remove_duplicate_cards(run.deck)


def _relic_pool(run: Run, minimum: int = 1) -> list[Relic]:
    """Relics this hero can find (neutral + own class), not owned yet.

    If fewer than ``minimum`` remain, owned ones come back (duplicates allowed).
    """
    own = class_for_character(run.character.id)
    allowed = [r for r in _all_relic_defs() if r.relic_class in (CardClass.NEUTRAL, own)]
    owned_tags = {r.tag for r in run.relics}
    pool = [r for r in allowed if r.tag not in owned_tags]
    return pool if len(pool) >= minimum else allowed


def run_luck(run: Run) -> int:
    """Luck used for drop odds: character luck + Pruebas bonus + relics (Trébol: +100)."""
    return hero_luck(run.character.stats.luck) + relic_effects.luck_bonus(run.relics)


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
    bonus           = relic_effects.max_hp_bonus(run.relics)
    run.player_max_hp = run.character.stats.max_hp + bonus


def pick_shop_stock(run: Run) -> tuple[list[PackDef], list[Relic]]:
    """Choose three distinct offers of each kind, stable for this room."""
    rng = random.Random(f"shop:{run.seed}:{run.floor}:{run.current_room_id}")
    pool = _relic_pool(run, 3)
    packs, relics = rng.sample(ALL_PACKS, 3), _pick_relics(pool, 3, rng, run_luck(run))
    relics = _with_chroma(relics, rng, run_luck(run))
    packs = [replace(p, chroma=roll_chroma(rng, kind="pack", luck=run_luck(run))) for p in packs]
    return packs, relics
