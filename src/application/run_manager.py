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
from dataclasses import replace

from src.application import relic_effects
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
    h = hash(room_id) & 0xFFFF_FFFF
    return (run.seed * _ENEMY_PRIME + run.floor * 997 + h) & 0xFFFF_FFFF_FFFF_FFFF


def _scale(base: int, floor: int) -> int:
    return int(base * (1 + 0.15 * (floor - 1)))


def generate_enemies(run: Run, room_id: str) -> list[Enemy]:
    """Return a list of enemies appropriate for the floor."""
    rng   = random.Random(_enemy_seed(run, room_id))
    floor = run.floor

    templates = [
        ("Cultista",  _scale(55,  floor), IntentType.ATTACK, _scale(10, floor)),
        ("Guardián",  _scale(45,  floor), IntentType.BLOCK,  _scale(8,  floor)),
        ("Brujo",     _scale(40,  floor), IntentType.BUFF,   0),
        ("Esqueleto", _scale(35,  floor), IntentType.ATTACK, _scale(8,  floor)),
        ("Golem",     _scale(70,  floor), IntentType.BLOCK,  _scale(12, floor)),
        ("Asesino",   _scale(30,  floor), IntentType.ATTACK, _scale(14, floor)),
        ("Espectro",  _scale(42,  floor), IntentType.ATTACK, _scale(11, floor)),
    ]

    # Pick 1–3 enemies; higher floors → more enemies
    max_enemies = min(1 + floor // 2, 3)
    count       = rng.randint(1, max_enemies)
    pool        = rng.sample(templates, min(count, len(templates)))

    enemies: list[Enemy] = []
    for i, (name, hp, itype, ival) in enumerate(pool):
        enemies.append(Enemy(
            id=f"{room_id}_e{i}",
            name=name,
            max_hp=hp,
            current_hp=hp,
            intent=Intent(itype, ival),
        ))
    return enemies


def generate_boss(run: Run) -> list[Enemy]:
    """Return the boss enemy for the current floor."""
    floor = run.floor
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
    base = sum(max(1, e.max_hp // 8) for e in enemies)
    base += relic_effects.bonus_gold_reward(run.relics)
    return round(base * TUNING.gold_multiplier)


def apply_combat_victory(run: Run, hp_after: int, enemies: list[Enemy]) -> int:
    """Update run state after winning a combat.  Returns gold earned."""
    heal   = relic_effects.post_combat_heal(run.relics)
    new_hp = min(hp_after + heal, run.player_max_hp)
    run.apply_combat_result(new_hp)
    gold = _combat_gold(run, enemies)
    run.gold += gold
    return gold


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
    pool = _relic_pool(run)
    rng = random.Random(_enemy_seed(run, room_id) ^ 0x1234)
    relics = _pick_relics(pool, 1, rng, run_luck(run))
    return _with_chroma(relics, rng, run_luck(run))[0]


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
