"""Regular enemies: eleven code-drawn monsters, each with an identity and a readable pattern.

Every enemy plays a fixed cycle of named moves (like the bosses in ``enemy_ai``), so the
player can read what is coming and plan around it. Identities:

* **Espectro** — *lamento*: claws, and a wail that leaves you Débil and Frágil.
* **Babosa Ácida** — *corrosión*: its acid leaves you Frágil and Vulnerable.
* **Gusano de Tumba** — *veneno*: poisons you and burrows for block.
* **Ojo Vigilante** — *debuffs puros*: Vulnerable, Débil, Enredado; hits little.
* **Cráneo Ígneo** — *agresivo que escala*: stokes its fire for +3 Fuerza every 3 turns.
* **Murciélago Vampiro** — *robo de vida*: heals what it bites, dives three times.
* **Seta Explosiva** — *cuenta atrás*: "Mecha" counts down; at 0 it explodes for a lot and dies.
* **Gólem de Musgo** — *muro*: huge block, shields its partner, hits slow and hard.
* **Acólito de Ceniza** — *apoyo*: gives Fuerza to everyone and heals its allies.
* **Diablillo** — *muy agresivo*: three claws, fireball (Vulnerable), taunts for Fuerza.
* **Mímico** — *emboscada*: pretends to be a chest (big block), then a devastating bite.

**Parejas** (``PAIRS``): fixed duos built around a synergy (the acolyte powers up the
skull, the eye makes you Vulnerable for the bat's dive…). Partners know each other
(``Enemy.partner_id``): when one dies, the other's intent turns at once into
**Venganza** (+3 Fuerza, block) — ``react_to_deaths``.

Pure application code (no pygame). Numbers are floor-1 values scaled +15 % per floor.
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Callable

from src.domain.entities import (ENTANGLED, FRAIL, FUSE, POISON, STRENGTH, VULNERABLE, WEAK, Enemy,
                                 Intent, IntentType, Player, add_status, status_stacks)

VENGEANCE_ID = "vengeance"
VENGEANCE_STRENGTH = 3
VENGEANCE_BLOCK = 6
BOMB_FUSE = 3                 # turns until the Seta Explosiva blows up
PAIR_HP_FACTOR = 0.8          # each member of a pair has 80 % of its solo HP


@dataclass(frozen=True)
class EnemyDef:
    ai: str               # pattern id (also stored in ``Enemy.ai``)
    name: str             # Spanish display name (sprite sheet key)
    hp: int               # floor-1 HP when alone
    identity: str         # one word/phrase shown in the tooltip ("Corrosión")
    title: str            # Spanish one-line identity, for tooltips / docs


@dataclass(frozen=True)
class PairDef:
    key: str
    name: str             # Spanish name of the duo ("El Culto del Fuego")
    members: tuple[str, str]   # ai ids
    synergy: str          # Spanish: why they work together
    min_floor: int = 1    # first floor where the pair can appear


WRAITH, SLIME, WORM, EYE, SKULL, BAT, BOMB, GOLEM, ACOLYTE, IMP, MIMIC = (
    "espectro", "babosa", "gusano", "ojo", "craneo", "murcielago", "seta", "golem", "acolito",
    "diablillo", "mimico")

ENEMIES: dict[str, EnemyDef] = {d.ai: d for d in (
    EnemyDef(WRAITH, "Espectro", 42, "Lamento",
             "Zarpazos espectrales y un lamento que te deja Débil y Frágil."),
    EnemyDef(SLIME, "Babosa Ácida", 46, "Corrosión",
             "Su ácido te deja Frágil y Vulnerable: tu escudo rinde menos y recibes más daño."),
    EnemyDef(WORM, "Gusano de Tumba", 52, "Veneno",
             "Te envenena con cada mordida y se entierra para protegerse."),
    EnemyDef(EYE, "Ojo Vigilante", 34, "Debuffs",
             "Pega poco, pero su mirada te deja Vulnerable, Débil y Enredado."),
    EnemyDef(SKULL, "Cráneo Ígneo", 38, "Agresivo",
             "Aviva su fuego: gana Fuerza cada tres turnos y golpea cada vez más fuerte."),
    EnemyDef(BAT, "Murciélago Vampiro", 30, "Robo de vida",
             "Se cura con la vida que te quita y cae en picado con tres mordiscos."),
    EnemyDef(BOMB, "Seta Explosiva", 28, "Cuenta atrás",
             "Su Mecha se consume: si no la matas a tiempo, explota con un golpe enorme."),
    EnemyDef(GOLEM, "Gólem de Musgo", 72, "Muro",
             "Mucho escudo, protege a su compañero y golpea lento pero muy fuerte."),
    EnemyDef(ACOLYTE, "Acólito de Ceniza", 40, "Apoyo",
             "Bendice a sus aliados con Fuerza y los cura. Mátalo primero."),
    EnemyDef(IMP, "Diablillo", 32, "Muy agresivo",
             "Tres zarpazos, bolas de fuego que te dejan Vulnerable y burlas que lo fortalecen."),
    EnemyDef(MIMIC, "Mímico", 60, "Emboscada",
             "Se hace pasar por un cofre (mucho escudo) y luego muerde con todo."),
)}

PAIRS: dict[str, PairDef] = {p.key: p for p in (
    PairDef("culto", "El Culto del Fuego", (ACOLYTE, SKULL),
            "El Acólito bendice al Cráneo con Fuerza mientras este no para de atacar."),
    PairDef("muro", "Muro Corrosivo", (GOLEM, SLIME),
            "El Gólem cubre a la Babosa con escudo mientras su ácido te corroe."),
    PairDef("caceria", "Vigía y Cazador", (EYE, BAT),
            "El Ojo te deja Vulnerable y el Murciélago cae en picado sobre ti."),
    PairDef("cementerio", "Cementerio Podrido", (WORM, BOMB),
            "El Gusano te envenena y te entretiene mientras la Seta se consume."),
    PairDef("tesoro", "Trampa del Tesoro", (MIMIC, IMP),
            "El Mímico se cubre como un cofre y el Diablillo ataca sin parar.", min_floor=2),
    PairDef("procesion", "Procesión de Ceniza", (WRAITH, ACOLYTE),
            "El Espectro te debilita mientras el Acólito lo fortalece y lo cura."),
)}

NAME_TO_AI: dict[str, str] = {d.name: d.ai for d in ENEMIES.values()}


def _scale(base: int, floor: int) -> int:
    return int(base * (1 + 0.15 * (max(1, floor) - 1)))


# ---------------------------------------------------------------------------
# Creation and encounters
# ---------------------------------------------------------------------------

def create_enemy(ai: str, floor: int = 1, enemy_id: str | None = None, *,
                 hp_factor: float = 1.0) -> Enemy:
    """A fresh regular enemy with its first intent planned (and starting statuses)."""
    d = ENEMIES[ai]
    hp = max(1, int(_scale(d.hp, floor) * hp_factor))
    enemy = Enemy(id=enemy_id or f"{ai}_f{floor}", name=d.name, max_hp=hp, current_hp=hp,
                  ai=ai, floor=max(1, floor))
    if ai == BOMB:
        add_status(enemy.status_effects, FUSE, BOMB_FUSE, is_buff=True)
    enemy.intent = next_intent(enemy, None, [enemy])
    return enemy


def create_pair(key: str, floor: int = 1, id_prefix: str = "pair") -> list[Enemy]:
    """Both members of a pair, linked as partners."""
    pair = PAIRS[key]
    a, b = (create_enemy(ai, floor, f"{id_prefix}_e{i}", hp_factor=PAIR_HP_FACTOR)
            for i, ai in enumerate(pair.members))
    a.partner_id, b.partner_id = b.id, a.id
    a.pair, b.pair = pair.name, pair.name
    # Plan again now that each knows its ally (support moves look at allies).
    for e in (a, b):
        e.ai_step = 0
        e.intent = next_intent(e, None, [a, b])
    return [a, b]


def pair_chance(floor: int) -> float:
    """Chance that a combat room is a pair (floor 1: 35 %, floor 2: 50 %, then 60 %)."""
    return 0.35 if floor <= 1 else 0.5 if floor == 2 else 0.6


def trio_chance(floor: int) -> float:
    """From floor 3 a pair may come with a third, solo enemy."""
    return 0.0 if floor < 3 else 0.25


# Every fixed encounter, in Pruebas order: each enemy alone, then each pair.
ENCOUNTERS: tuple[tuple[str, str], ...] = (
    *(("solo", ai) for ai in ENEMIES), *(("pair", key) for key in PAIRS))


def encounter_label(index: int) -> str:
    """Spanish label of ``ENCOUNTERS[index - 1]`` (0 = "Al azar"), for the Pruebas screen."""
    if not 1 <= index <= len(ENCOUNTERS):
        return "Al azar"
    kind, key = ENCOUNTERS[index - 1]
    return ENEMIES[key].name if kind == "solo" else f"Pareja: {PAIRS[key].name}"


def create_encounter(index: int, floor: int, room_id: str) -> list[Enemy]:
    """Encounter number ``index`` (1-based, see ``ENCOUNTERS``)."""
    kind, key = ENCOUNTERS[index - 1]
    if kind == "pair":
        return create_pair(key, floor, room_id)
    return [create_enemy(key, floor, f"{room_id}_e0")]


def roll_encounter(rng: random.Random, floor: int, room_id: str, forced: int = 0) -> list[Enemy]:
    """The enemies of one combat room: a solo enemy, a pair, or (floor 3+) a pair + one.

    ``forced`` (Pruebas): 1.. picks ``ENCOUNTERS[forced - 1]`` every time.
    """
    if 1 <= forced <= len(ENCOUNTERS):
        return create_encounter(forced, floor, room_id)
    if rng.random() < pair_chance(floor):
        key = rng.choice(sorted(k for k, p in PAIRS.items() if p.min_floor <= floor))
        enemies = create_pair(key, floor, room_id)
        if rng.random() < trio_chance(floor):
            taken = set(PAIRS[key].members)
            extra = rng.choice(sorted(a for a in ENEMIES if a not in taken))
            enemies.append(create_enemy(extra, floor, f"{room_id}_e2", hp_factor=PAIR_HP_FACTOR))
        return enemies
    ai = rng.choice(sorted(ENEMIES))
    return [create_enemy(ai, floor, f"{room_id}_e0")]


# ---------------------------------------------------------------------------
# Patterns
# ---------------------------------------------------------------------------

def _f(enemy: Enemy) -> int:
    return max(1, enemy.floor)


def _step(enemy: Enemy, n: int) -> int:
    s = enemy.ai_step % n
    enemy.ai_step += 1
    return s


def _allies(enemy: Enemy, allies: list[Enemy] | None) -> list[Enemy]:
    return [e for e in (allies or []) if e is not enemy and e.is_alive]


def _wraith(enemy, player, allies) -> Intent:
    f = _f(enemy)
    if _step(enemy, 3) < 2:
        return Intent(IntentType.ATTACK, _scale(11, f), move="Zarpazo Espectral", move_id="claw",
                      description="Te desgarra con sus garras.")
    return Intent(IntentType.DEBUFF, move="Lamento", move_id="wail",
                  debuffs=((WEAK, 2), (FRAIL, 1)),
                  description="Su lamento te deja Débil 2 turnos y Frágil 1 turno.")


def _slime(enemy, player, allies) -> Intent:
    f = _f(enemy)
    s = _step(enemy, 3)
    if s == 0:
        return Intent(IntentType.ATTACK, _scale(5, f), move="Escupitajo Ácido", move_id="spit",
                      debuffs=((FRAIL, 2),),
                      description="Te escupe ácido: Frágil 2 turnos (tu escudo rinde menos).")
    if s == 1:
        return Intent(IntentType.ATTACK, _scale(10, f), move="Golpe Viscoso", move_id="slam",
                      description="Se deja caer sobre ti.")
    return Intent(IntentType.DEBUFF, move="Corroer", move_id="corrode",
                  debuffs=((VULNERABLE, 2),), block=_scale(5, f),
                  description="Corroe tu armadura: Vulnerable 2 turnos. Se cubre un poco.")


def _worm(enemy, player, allies) -> Intent:
    f = _f(enemy)
    s = _step(enemy, 3)
    if s == 0:
        return Intent(IntentType.ATTACK, _scale(6, f), move="Mordida Pútrida", move_id="bite",
                      debuffs=((POISON, 3),), description="Muerde y te da 3 de Veneno.")
    if s == 1:
        return Intent(IntentType.BLOCK, _scale(12, f), move="Enterrarse", move_id="burrow",
                      description="Se mete bajo tierra y gana mucho escudo.")
    return Intent(IntentType.DEBUFF, move="Bilis", move_id="bile", debuffs=((POISON, 5),),
                  description="Te vomita bilis: 5 de Veneno.")


def _eye(enemy, player, allies) -> Intent:
    f = _f(enemy)
    s = _step(enemy, 3)
    if s == 0:
        return Intent(IntentType.DEBUFF, move="Mirada Fija", move_id="stare",
                      debuffs=((VULNERABLE, 2), (WEAK, 1)),
                      description="Te clava la mirada: Vulnerable 2 turnos y Débil 1 turno.")
    if s == 1:
        return Intent(IntentType.ATTACK, _scale(8, f), move="Rayo Ocular", move_id="beam",
                      description="Dispara un rayo por la pupila.")
    return Intent(IntentType.DEBUFF, move="Pavor", move_id="dread",
                  debuffs=((ENTANGLED, 1), (FRAIL, 1)),
                  description="Te paraliza de miedo: Enredado (robas 1 carta menos) y Frágil.")


def _skull(enemy, player, allies) -> Intent:
    f = _f(enemy)
    if _step(enemy, 3) < 2:
        return Intent(IntentType.ATTACK, _scale(7, f), move="Llamarada", move_id="flame",
                      description="Escupe fuego. Cada Fuerza que gana suma a este golpe.")
    return Intent(IntentType.BUFF, move="Avivar", move_id="stoke", buffs=((STRENGTH, 3),),
                  description="Aviva su fuego: gana 3 de Fuerza para siempre.")


def _bat(enemy, player, allies) -> Intent:
    f = _f(enemy)
    s = _step(enemy, 3)
    if s == 0:
        return Intent(IntentType.ATTACK, _scale(7, f), move="Mordisco Vampírico", move_id="bite",
                      lifesteal=True,
                      description="Muerde y se cura tanta vida como te quite.")
    if s == 1:
        return Intent(IntentType.ATTACK, _scale(3, f), hits=3, move="Picado", move_id="dive",
                      description="Cae en picado: tres mordiscos rápidos.")
    return Intent(IntentType.DEBUFF, move="Chillido", move_id="screech", debuffs=((WEAK, 2),),
                  description="Un chillido ensordecedor: Débil 2 turnos.")


def _bomb(enemy, player, allies) -> Intent:
    f = _f(enemy)
    fuse = status_stacks(enemy.status_effects, FUSE)
    if fuse <= 1:
        return Intent(IntentType.ATTACK, _scale(24, f), move="¡Explosión!", move_id="explode",
                      self_destruct=True,
                      description="Explota con un golpe enorme y muere. ¡Mátala antes!")
    if fuse == 2:
        return Intent(IntentType.BLOCK, _scale(8, f), move="Hincharse", move_id="swell",
                      description="Se hincha y se cubre. La próxima vez, explota.")
    return Intent(IntentType.DEBUFF, move="Nube de Esporas", move_id="puff",
                  debuffs=((POISON, 2),), description="Suelta esporas: 2 de Veneno.")


def _golem(enemy, player, allies) -> Intent:
    f = _f(enemy)
    s = _step(enemy, 3)
    if s == 0:
        mates = _allies(enemy, allies)
        return Intent(IntentType.BLOCK, _scale(10, f), move="Muralla", move_id="wall",
                      ally_block=_scale(8, f) if mates else 0,
                      description=("Levanta un muro: escudo para él y para su compañero."
                                   if mates else "Levanta un muro de piedra."))
    if s == 1:
        return Intent(IntentType.ATTACK, _scale(13, f), move="Puñetazo de Roca", move_id="punch",
                      description="Un puñetazo lento y demoledor.")
    return Intent(IntentType.BUFF, move="Endurecer", move_id="harden", block=_scale(12, f),
                  buffs=((STRENGTH, 2),), description="Endurece la piedra: escudo y 2 de Fuerza.")


def _acolyte(enemy, player, allies) -> Intent:
    f = _f(enemy)
    mates = _allies(enemy, allies)
    s = _step(enemy, 4)
    if s == 0:
        return Intent(IntentType.BUFF, move="Bendición de Ceniza", move_id="bless",
                      buffs=((STRENGTH, 2),), ally_buffs=((STRENGTH, 2),) if mates else (),
                      description=("Da 2 de Fuerza a todos sus aliados y a sí mismo."
                                   if mates else "Se bendice: gana 2 de Fuerza."))
    if s == 2:
        hurt = [e for e in mates + [enemy] if e.current_hp < e.max_hp]
        if hurt:
            return Intent(IntentType.BUFF, move="Plegaria", move_id="mend", heal_allies=_scale(8, f),
                          description="Reza: cura 8 de vida a cada aliado (y a sí mismo).")
        return Intent(IntentType.DEBUFF, move="Penitencia", move_id="penance",
                      debuffs=((WEAK, 1), (FRAIL, 1)),
                      description="Te impone penitencia: Débil y Frágil 1 turno.")
    return Intent(IntentType.ATTACK, _scale(6, f), move="Incensario", move_id="censer",
                  description="Te golpea con el incensario ardiente.")


def _imp(enemy, player, allies) -> Intent:
    f = _f(enemy)
    s = _step(enemy, 4)
    if s in (0, 2):
        return Intent(IntentType.ATTACK, _scale(3, f), hits=3, move="Zarpazos", move_id="claws",
                      description="Tres zarpazos seguidos.")
    if s == 1:
        return Intent(IntentType.ATTACK, _scale(11, f), move="Bola de Fuego", move_id="fireball",
                      debuffs=((VULNERABLE, 1),),
                      description="Te lanza una bola de fuego: Vulnerable 1 turno.")
    return Intent(IntentType.BUFF, move="Burla", move_id="taunt", buffs=((STRENGTH, 2),),
                  description="Se ríe de ti y gana 2 de Fuerza.")


def _mimic(enemy, player, allies) -> Intent:
    f = _f(enemy)
    s = _step(enemy, 4)
    if s == 0:
        return Intent(IntentType.BLOCK, _scale(15, f), move="Fingir", move_id="feign",
                      description="Se hace pasar por un cofre: gana mucho escudo. Lo próximo es una dentellada.")
    if s == 1:
        return Intent(IntentType.ATTACK, _scale(18, f), move="Dentellada", move_id="chomp",
                      description="Abre la tapa y muerde con todo.")
    if s == 2:
        return Intent(IntentType.ATTACK, _scale(4, f), hits=3, move="Lengüetazo", move_id="lick",
                      debuffs=((WEAK, 1),), description="Tres latigazos con la lengua: Débil 1 turno.")
    return Intent(IntentType.ATTACK, _scale(12, f), move="Dentellada", move_id="chomp",
                  description="Otra dentellada.")


PATTERNS: dict[str, Callable[[Enemy, Player | None, list[Enemy] | None], Intent]] = {
    WRAITH: _wraith, SLIME: _slime, WORM: _worm, EYE: _eye, SKULL: _skull, BAT: _bat,
    BOMB: _bomb, GOLEM: _golem, ACOLYTE: _acolyte, IMP: _imp, MIMIC: _mimic,
}


def vengeance_intent(enemy: Enemy) -> Intent:
    f = _f(enemy)
    return Intent(IntentType.BUFF, move="Venganza", move_id=VENGEANCE_ID,
                  buffs=((STRENGTH, VENGEANCE_STRENGTH),), block=_scale(VENGEANCE_BLOCK, f),
                  description=f"Su pareja ha caído: gana {VENGEANCE_STRENGTH} de Fuerza y escudo.")


def _partner_fell(enemy: Enemy, allies: list[Enemy] | None) -> bool:
    if not enemy.partner_id or allies is None:
        return False
    partner = next((e for e in allies if e.id == enemy.partner_id), None)
    return partner is None or not partner.is_alive


def next_intent(enemy: Enemy, player: Player | None, allies: list[Enemy] | None = None) -> Intent:
    """The enemy's next move. A partner that just fell → Venganza (once)."""
    if VENGEANCE_ID not in enemy.ai_used and _partner_fell(enemy, allies):
        enemy.ai_used.add(VENGEANCE_ID)
        return vengeance_intent(enemy)
    pattern = PATTERNS.get(enemy.ai)
    return pattern(enemy, player, allies) if pattern else Intent(IntentType.UNKNOWN)


def react_to_deaths(enemies: list[Enemy], player: Player | None = None) -> list[int]:
    """A partner died: the survivor's intent turns into Venganza right away.

    Returns the indices of the enemies whose intent changed (for the screen).
    """
    changed: list[int] = []
    for i, enemy in enumerate(enemies):
        if (enemy.is_alive and enemy.ai in PATTERNS and VENGEANCE_ID not in enemy.ai_used
                and _partner_fell(enemy, enemies)):
            enemy.ai_used.add(VENGEANCE_ID)
            enemy.intent = vengeance_intent(enemy)
            changed.append(i)
    return changed


def after_action(enemy: Enemy) -> None:
    """Bookkeeping after the enemy acted (the Seta's Mecha burns down)."""
    if enemy.ai == BOMB and enemy.is_alive:
        for se in enemy.status_effects:
            if se.name == FUSE and se.stacks > 1:
                se.stacks -= 1
