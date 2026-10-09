"""Pattern AI for bosses: each boss plays a fixed, readable cycle of named moves.

Floor 1 has three bosses, each with its own identity:

* **La Reina Micélida** — *cartas tóxicas*. Fills your deck with Esporas (pay 1 mana
  or take Veneno) and Moho (drains mana when drawn) and poisons you.
* **La Tejedora** — *debuffs*. Débil, Frágil, Vulnerable and Enredado; her Banquete
  bites once more for every different debuff you carry.
* **El Caballero Hueco** — *ataques múltiples*. Floating swords ("Espadas"): his
  Danza de Espadas hits once per sword, and he keeps summoning more.

Each boss also has a one-shot move the first time it drops to half HP or below.

``next_intent(enemy, player)`` decides the intent shown for the next enemy turn
(called right after the boss acts, and when the boss is created). It advances
``enemy.ai_step``. Damage values are the printed per-hit numbers; Fuerza, Débil
and Vulnerable are applied when the hit lands (``entities.enemy_hit_damage``).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from src.domain.entities import (BLADES, ENTANGLED, FRAIL, POISON, STRENGTH, VULNERABLE, WEAK,
                                 Enemy, Intent, IntentType, Player, add_status, status_stacks)
from src.application import elites, enemy_roster
from src.domain.status_cards import MOLD_ID, SPORE_ID

MYCELID = "micelida"
WEAVER = "tejedora"
HOLLOW_KNIGHT = "caballero"

ENRAGE_RATIO = 0.5          # one-shot move the first time HP <= 50 %
KNIGHT_START_BLADES = 2
KNIGHT_MAX_BLADES = 6


@dataclass(frozen=True)
class BossDef:
    ai: str
    name: str             # Spanish display name (also the sprite sheet key)
    hp: int               # floor-1 HP (scaled by floor)
    title: str            # Spanish one-line identity, for tooltips / docs


BOSSES: dict[str, BossDef] = {
    MYCELID: BossDef(MYCELID, "Reina Micélida", 138,
                     "Llena tu mazo de Esporas y Moho, y te envenena."),
    WEAVER: BossDef(WEAVER, "La Tejedora", 126,
                    "Te enreda en debuffs; su Banquete muerde más cuantos más tengas."),
    HOLLOW_KNIGHT: BossDef(HOLLOW_KNIGHT, "Caballero Hueco", 150,
                           "Espadas flotantes: golpea una vez por espada y cada vez invoca más."),
}
FLOOR1_BOSSES: tuple[str, ...] = (MYCELID, WEAVER, HOLLOW_KNIGHT)


def _scale(base: int, floor: int) -> int:
    return int(base * (1 + 0.15 * (max(1, floor) - 1)))


# ---------------------------------------------------------------------------
# Creation
# ---------------------------------------------------------------------------

def create_boss(ai: str, floor: int = 1, enemy_id: str | None = None) -> Enemy:
    """A fresh boss with its first intent planned (and its starting buffs)."""
    d = BOSSES[ai]
    hp = _scale(d.hp, floor)
    boss = Enemy(id=enemy_id or f"boss_{ai}_f{floor}", name=d.name, max_hp=hp, current_hp=hp,
                 ai=ai, is_boss=True, floor=max(1, floor))
    if ai == HOLLOW_KNIGHT:
        add_status(boss.status_effects, BLADES, KNIGHT_START_BLADES, is_buff=True)
    boss.intent = next_intent(boss, None)
    return boss


def _floor(enemy: Enemy) -> int:
    return max(1, enemy.floor)


# ---------------------------------------------------------------------------
# Move tables
# ---------------------------------------------------------------------------

def _debuff_kinds(player: Player | None) -> int:
    """How many different debuffs the hero has right now."""
    if player is None:
        return 0
    return len({se.name for se in player.status_effects if not se.is_buff and se.stacks > 0})


def _mycelid(enemy: Enemy, player: Player | None) -> Intent:
    f = _floor(enemy)
    if _enraged(enemy, "bloom"):
        return Intent(IntentType.DEBUFF, move="Floración Pútrida", move_id="bloom",
                      debuffs=((POISON, _scale(4, f)),), cards=((SPORE_ID, 2, "hand"),),
                      description="Te da 4 de Veneno y pone 2 Esporas en tu mano.")
    step = enemy.ai_step % 3
    enemy.ai_step += 1
    if step == 0:
        return Intent(IntentType.ATTACK, _scale(6, f), move="Lluvia de Esporas", move_id="spores",
                      cards=((SPORE_ID, 2, "draw"),),
                      description="Ataca y baraja 2 Esporas en tu pila de robo.")
    if step == 1:
        return Intent(IntentType.ATTACK, _scale(10, f), move="Raíces Estranguladoras",
                      move_id="roots", debuffs=((POISON, 3),),
                      description="Ataca y te da 3 de Veneno.")
    return Intent(IntentType.BLOCK, _scale(12, f), move="Brote de Moho", move_id="mold",
                  cards=((MOLD_ID, 2, "draw"),),
                  description="Se cubre y baraja 2 Moho en tu pila de robo.")


def _weaver(enemy: Enemy, player: Player | None) -> Intent:
    f = _floor(enemy)
    if _enraged(enemy, "brood"):
        return Intent(IntentType.DEBUFF, move="Madre de la Camada", move_id="brood",
                      debuffs=((WEAK, 1), (FRAIL, 1), (VULNERABLE, 1), (ENTANGLED, 1)),
                      description="Te aplica Débil, Frágil, Vulnerable y Enredado a la vez.")
    step = enemy.ai_step % 4
    enemy.ai_step += 1
    if step == 0:
        return Intent(IntentType.DEBUFF, move="Hilos Pegajosos", move_id="web",
                      debuffs=((WEAK, 2), (ENTANGLED, 1)),
                      description="Te deja Débil 2 turnos y Enredado (robas 1 carta menos).")
    if step == 1:
        return Intent(IntentType.ATTACK, _scale(9, f), move="Colmillo", move_id="fang",
                      debuffs=((VULNERABLE, 2),),
                      description="Muerde y te deja Vulnerable 2 turnos.")
    if step == 2:
        return Intent(IntentType.BLOCK, _scale(10, f), move="Capullo de Seda", move_id="cocoon",
                      debuffs=((FRAIL, 2),),
                      description="Se envuelve en seda y te deja Frágil 2 turnos.")
    hits = 1 + _debuff_kinds(player)
    return Intent(IntentType.ATTACK, _scale(5, f), hits=hits, move="Banquete", move_id="feast",
                  description="Muerde una vez más por cada debuff distinto que tengas.")


def _hollow_knight(enemy: Enemy, player: Player | None) -> Intent:
    f = _floor(enemy)
    blades = max(1, status_stacks(enemy.status_effects, BLADES))
    if _enraged(enemy, "fury"):
        return Intent(IntentType.BUFF, move="Furia Hueca", move_id="fury",
                      buffs=((STRENGTH, 2),), block=_scale(6, f),
                      description="Gana 2 de Fuerza: cada golpe hace +2.")
    step = enemy.ai_step % 6
    enemy.ai_step += 1
    if step in (0, 3):
        return Intent(IntentType.ATTACK, _scale(4, f), hits=blades, move="Danza de Espadas",
                      move_id="blade_dance",
                      description="Golpea una vez por cada espada flotante.")
    if step in (1, 4):
        more = 1 if blades < KNIGHT_MAX_BLADES else 0
        return Intent(IntentType.BUFF, move="Llamar al Acero", move_id="summon",
                      buffs=((BLADES, more),) if more else (), block=_scale(8, f),
                      description="Invoca otra espada y se cubre.")
    if step == 2:
        return Intent(IntentType.ATTACK, _scale(8, f), hits=2, move="Estocada Doble",
                      move_id="double", description="Dos estocadas rápidas.")
    return Intent(IntentType.ATTACK, _scale(17, f), move="Tajo del Verdugo", move_id="execute",
                  description="Un único tajo devastador.")


_PATTERNS: dict[str, Callable[[Enemy, Player | None], Intent]] = {
    MYCELID: _mycelid,
    WEAVER: _weaver,
    HOLLOW_KNIGHT: _hollow_knight,
}


def _enraged(enemy: Enemy, key: str) -> bool:
    """True once, the first time the boss is at half HP or below (marks it used)."""
    if key in enemy.ai_used or enemy.max_hp <= 0:
        return False
    if enemy.current_hp > enemy.max_hp * ENRAGE_RATIO:
        return False
    enemy.ai_used.add(key)
    return True


def has_pattern(enemy: Enemy) -> bool:
    return enemy.ai in _PATTERNS or enemy.ai in enemy_roster.PATTERNS or enemy.ai in elites.PATTERNS


def next_intent(enemy: Enemy, player: Player | None, allies: list[Enemy] | None = None) -> Intent:
    """The next move (advances the pattern): bosses here, regular enemies in
    ``enemy_roster`` (which also see their ``allies``), elites in ``elites``.
    Unknown AI → an UNKNOWN intent."""
    pattern = _PATTERNS.get(enemy.ai)
    if pattern is not None:
        return pattern(enemy, player)
    if enemy.ai in enemy_roster.PATTERNS:
        return enemy_roster.next_intent(enemy, player, allies)
    if enemy.ai in elites.PATTERNS:
        return elites.next_intent(enemy, player, allies)
    return Intent(IntentType.UNKNOWN)


def intent_hit_damage(enemy: Enemy, player: Player) -> int:
    """Per-hit damage the enemy's ATTACK intent will deal right now (for the intent bubble)."""
    from src.domain.entities import enemy_hit_damage
    return enemy_hit_damage(enemy, player)
