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

from src.application import relic_effects
from src.application.map_generator import generate_map
from src.domain.card_pool import starter_deck
from src.domain.character import Character
from src.domain.entities import Enemy, Intent, IntentType
from src.domain.relic import Relic, RelicTag
from src.domain.run import Run

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
        gold=0,
        player_max_hp=character.stats.max_hp,
        player_current_hp=character.stats.max_hp,
        deck=starter_deck(),
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
    return base


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
    return rng.randint(10 + run.floor * 2, 25 + run.floor * 3)


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
    ]


def pick_treasure_relic(run: Run, room_id: str) -> Relic:
    """Choose a relic not already owned by the player."""
    owned_tags = {r.tag for r in run.relics}
    pool       = [r for r in _all_relic_defs() if r.tag not in owned_tags]
    if not pool:
        pool = _all_relic_defs()   # fallback: duplicates allowed
    rng = random.Random(_enemy_seed(run, room_id) ^ 0x1234)
    return rng.choice(pool)


def pick_boss_relics(run: Run, count: int = 3) -> list[Relic]:
    """Choose `count` distinct relics for the boss reward screen."""
    owned_tags = {r.tag for r in run.relics}
    pool       = [r for r in _all_relic_defs() if r.tag not in owned_tags]
    if len(pool) < count:
        pool = _all_relic_defs()
    rng = random.Random(run.seed * 37 + run.floor * 13)
    return rng.sample(pool, min(count, len(pool)))


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
