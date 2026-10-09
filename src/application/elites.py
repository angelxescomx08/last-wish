"""Elite enemies: one mini-boss room per floor, between the regular enemies and the boss.

Five code-drawn elites, each with an identity and a readable, fixed cycle of named moves
(like the bosses in ``enemy_ai``) plus a one-shot move the first time it drops to half HP:

* **El Verdugo** — *ejecución*: marks you Vulnerable, sharpens his axe (Fuerza) and swings
  a huge Decapitar.
* **Bruja del Pantano** — *maleficios*: Débil and Frágil, Moho into your deck, a voodoo doll
  that stabs three times, and a forbidden brew that heals her.
* **Gárgola** — *piel de piedra*: turns to stone for a lot of block, then dives three times.
* **Minotauro** — *embestida*: scrapes the floor, then charges; every Embestida hits
  ``MINOTAUR_CHARGE_STEP`` more than the one before.
* **Escorpión Rey** — *veneno letal*: Veneno with every sting, Débil pincers, a hard shell.

Elites are stronger than regular enemies (≈ 80–100 HP on floor 1, bigger hits) and weaker
than the bosses (126–150 HP). Winning gives a relic and a card reward with slightly better
odds (``ELITE_CARD_LUCK``). Pure application code (no pygame); numbers are floor-1 values
scaled +15 % per floor.
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Callable

from src.domain.entities import (ENTANGLED, FRAIL, POISON, STRENGTH, VULNERABLE, WEAK, Enemy,
                                 Intent, IntentType, Player)
from src.domain.status_cards import MOLD_ID

ENRAGE_RATIO = 0.5             # one-shot move the first time HP <= 50 %
MINOTAUR_CHARGE_BASE = 15      # first Embestida
MINOTAUR_CHARGE_STEP = 5       # every later Embestida hits this much more
# Card reward after an elite: this much extra luck on the rarity roll only (not on golden
# cards nor on the luck's extra cards). With 0 luck: Rara or better 22 % -> 35 %.
ELITE_CARD_LUCK = 5


@dataclass(frozen=True)
class EliteDef:
    ai: str
    name: str             # Spanish display name (sprite sheet key)
    hp: int               # floor-1 HP
    identity: str         # short tag shown in the tooltip ("Ejecución")
    title: str            # Spanish one-line identity


EXECUTIONER, HAG, GARGOYLE, MINOTAUR, SCORPION = (
    "verdugo", "bruja", "gargola", "minotauro", "escorpion")

ELITES: dict[str, EliteDef] = {d.ai: d for d in (
    EliteDef(EXECUTIONER, "El Verdugo", 92, "Ejecución",
             "Te marca como Vulnerable, afila su hacha y descarga golpes enormes."),
    EliteDef(HAG, "Bruja del Pantano", 80, "Maleficios",
             "Te maldice, llena tu mazo de Moho y se cura con sus brebajes."),
    EliteDef(GARGOYLE, "Gárgola", 84, "Piel de piedra",
             "Se convierte en piedra con muchísimo escudo y luego cae en picado sobre ti."),
    EliteDef(MINOTAUR, "Minotauro", 100, "Embestida",
             "Escarba el suelo y embiste: cada Embestida golpea más fuerte que la anterior."),
    EliteDef(SCORPION, "Escorpión Rey", 88, "Veneno letal",
             "Te envenena sin parar y se protege con un caparazón muy duro."),
)}
ELITE_ORDER: tuple[str, ...] = (EXECUTIONER, HAG, GARGOYLE, MINOTAUR, SCORPION)


def _scale(base: int, floor: int) -> int:
    return int(base * (1 + 0.15 * (max(1, floor) - 1)))


# ---------------------------------------------------------------------------
# Creation
# ---------------------------------------------------------------------------

def create_elite(ai: str, floor: int = 1, enemy_id: str | None = None) -> Enemy:
    """A fresh elite with its first intent planned."""
    d = ELITES[ai]
    hp = _scale(d.hp, floor)
    elite = Enemy(id=enemy_id or f"elite_{ai}_f{floor}", name=d.name, max_hp=hp, current_hp=hp,
                  ai=ai, is_elite=True, floor=max(1, floor))
    elite.intent = next_intent(elite, None)
    return elite


def elite_label(index: int) -> str:
    """Pruebas label of ``ELITE_ORDER[index - 1]`` (0 = "Al azar")."""
    if not 1 <= index <= len(ELITE_ORDER):
        return "Al azar"
    return ELITES[ELITE_ORDER[index - 1]].name


def roll_elite(rng: random.Random, floor: int, room_id: str, forced: int = 0) -> list[Enemy]:
    """The elite of an elite room (``forced`` 1.. picks ``ELITE_ORDER[forced - 1]``)."""
    if 1 <= forced <= len(ELITE_ORDER):
        ai = ELITE_ORDER[forced - 1]
    else:
        ai = rng.choice(ELITE_ORDER)
    return [create_elite(ai, floor, f"{room_id}_elite")]


# ---------------------------------------------------------------------------
# Patterns
# ---------------------------------------------------------------------------

def _f(enemy: Enemy) -> int:
    return max(1, enemy.floor)


def _step(enemy: Enemy, n: int) -> int:
    s = enemy.ai_step % n
    enemy.ai_step += 1
    return s


def _enraged(enemy: Enemy, key: str) -> bool:
    """True once, the first time the elite is at half HP or below (marks it used)."""
    if key in enemy.ai_used or enemy.max_hp <= 0:
        return False
    if enemy.current_hp > enemy.max_hp * ENRAGE_RATIO:
        return False
    enemy.ai_used.add(key)
    return True


def _executioner(enemy: Enemy, player: Player | None) -> Intent:
    f = _f(enemy)
    if _enraged(enemy, "bloodlust"):
        return Intent(IntentType.BUFF, move="Sed de Sangre", move_id="bloodlust",
                      buffs=((STRENGTH, 3),),
                      description="Huele la sangre: gana 3 de Fuerza para siempre.")
    s = _step(enemy, 4)
    if s == 0:
        return Intent(IntentType.DEBUFF, move="Sentencia", move_id="sentence",
                      debuffs=((VULNERABLE, 2),), block=_scale(8, f),
                      description="Te señala con el hacha: Vulnerable 2 turnos. Se cubre.")
    if s == 1:
        return Intent(IntentType.ATTACK, _scale(14, f), move="Hachazo", move_id="chop",
                      description="Un hachazo pesado.")
    if s == 2:
        return Intent(IntentType.BUFF, move="Afilar", move_id="sharpen",
                      buffs=((STRENGTH, 2),), block=_scale(10, f),
                      description="Afila el hacha: gana 2 de Fuerza y escudo.")
    return Intent(IntentType.ATTACK, _scale(21, f), move="Decapitar", move_id="behead",
                  description="Levanta el hacha y descarga un golpe enorme.")


def _hag(enemy: Enemy, player: Player | None) -> Intent:
    f = _f(enemy)
    if _enraged(enemy, "potion"):
        return Intent(IntentType.BUFF, move="Brebaje Prohibido", move_id="potion",
                      heal_allies=_scale(15, f), buffs=((STRENGTH, 2),),
                      description="Bebe un brebaje prohibido: se cura 15 y gana 2 de Fuerza.")
    s = _step(enemy, 4)
    if s == 0:
        return Intent(IntentType.DEBUFF, move="Maleficio", move_id="hex",
                      debuffs=((WEAK, 2), (FRAIL, 2)),
                      description="Te maldice: Débil 2 turnos y Frágil 2 turnos.")
    if s == 1:
        return Intent(IntentType.ATTACK, _scale(9, f), move="Rayo de Ciénaga", move_id="bolt",
                      debuffs=((POISON, 3),),
                      description="Un rayo de fango verde: te da 3 de Veneno.")
    if s == 2:
        return Intent(IntentType.BLOCK, _scale(10, f), move="Caldero Burbujeante",
                      move_id="cauldron", cards=((MOLD_ID, 2, "draw"),),
                      description="Remueve el caldero: se cubre y baraja 2 Moho en tu pila de robo.")
    return Intent(IntentType.ATTACK, _scale(4, f), hits=3, move="Muñeco Vudú", move_id="voodoo",
                  description="Clava tres alfileres en un muñeco con tu cara.")


def _gargoyle(enemy: Enemy, player: Player | None) -> Intent:
    f = _f(enemy)
    if _enraged(enemy, "awaken"):
        return Intent(IntentType.BUFF, move="Despertar", move_id="awaken",
                      buffs=((STRENGTH, 3),), block=_scale(10, f),
                      description="Despierta del todo: gana 3 de Fuerza y escudo.")
    s = _step(enemy, 3)
    if s == 0:
        return Intent(IntentType.BLOCK, _scale(18, f), move="Petrificar", move_id="petrify",
                      description="Se convierte en piedra: gana muchísimo escudo.")
    if s == 1:
        return Intent(IntentType.ATTACK, _scale(5, f), hits=3, move="Picado", move_id="dive",
                      description="Cae en picado: tres zarpazos seguidos.")
    return Intent(IntentType.ATTACK, _scale(11, f), move="Zarpazo de Piedra", move_id="rend",
                  debuffs=((FRAIL, 2),),
                  description="Un zarpazo de piedra: te deja Frágil 2 turnos.")


def minotaur_charge_damage(enemy: Enemy) -> int:
    """Printed damage of the Minotauro's next Embestida (grows after every charge)."""
    done = sum(1 for k in enemy.ai_used if k.startswith("charge#"))
    return _scale(MINOTAUR_CHARGE_BASE + MINOTAUR_CHARGE_STEP * done, _f(enemy))


def _minotaur(enemy: Enemy, player: Player | None) -> Intent:
    f = _f(enemy)
    if _enraged(enemy, "rage"):
        return Intent(IntentType.BUFF, move="Furia Taurina", move_id="rage",
                      buffs=((STRENGTH, 3),),
                      description="Brama de furia: gana 3 de Fuerza para siempre.")
    s = _step(enemy, 3)
    if s == 0:
        return Intent(IntentType.BLOCK, _scale(12, f), move="Escarbar", move_id="paw",
                      description="Escarba el suelo y resopla: se cubre. Lo próximo es una Embestida.")
    if s == 1:
        dmg = minotaur_charge_damage(enemy)
        enemy.ai_used.add(f"charge#{enemy.ai_step}")
        return Intent(IntentType.ATTACK, dmg, move="Embestida", move_id="charge",
                      description=f"Embiste con los cuernos. Cada Embestida hace "
                                  f"{MINOTAUR_CHARGE_STEP} más que la anterior.")
    return Intent(IntentType.ATTACK, _scale(9, f), move="Pisotón", move_id="stomp",
                  debuffs=((ENTANGLED, 1),),
                  description="Un pisotón que hace temblar el suelo: Enredado (robas 1 carta menos).")


def _scorpion(enemy: Enemy, player: Player | None) -> Intent:
    f = _f(enemy)
    if _enraged(enemy, "frenzy"):
        return Intent(IntentType.BUFF, move="Frenesí", move_id="frenzy",
                      buffs=((STRENGTH, 2),), block=_scale(8, f),
                      description="Entra en frenesí: gana 2 de Fuerza y escudo.")
    s = _step(enemy, 4)
    if s == 0:
        return Intent(IntentType.ATTACK, _scale(7, f), move="Aguijonazo", move_id="sting",
                      debuffs=((POISON, 4),),
                      description="Te clava el aguijón: 4 de Veneno.")
    if s == 1:
        return Intent(IntentType.ATTACK, _scale(5, f), hits=2, move="Pinzas", move_id="pinch",
                      debuffs=((WEAK, 1),),
                      description="Dos pinzazos: te deja Débil 1 turno.")
    if s == 2:
        return Intent(IntentType.BLOCK, _scale(14, f), move="Caparazón", move_id="shell",
                      description="Se encoge bajo su caparazón: gana mucho escudo.")
    return Intent(IntentType.DEBUFF, move="Toxina", move_id="toxin", debuffs=((POISON, 6),),
                  description="Rocía veneno: 6 de Veneno.")


PATTERNS: dict[str, Callable[[Enemy, Player | None], Intent]] = {
    EXECUTIONER: _executioner, HAG: _hag, GARGOYLE: _gargoyle, MINOTAUR: _minotaur,
    SCORPION: _scorpion,
}


def next_intent(enemy: Enemy, player: Player | None, allies: list[Enemy] | None = None) -> Intent:
    """The elite's next move (advances its pattern)."""
    pattern = PATTERNS.get(enemy.ai)
    return pattern(enemy, player) if pattern else Intent(IntentType.UNKNOWN)
