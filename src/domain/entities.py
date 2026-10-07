from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto


class IntentType(Enum):
    ATTACK = auto()
    BLOCK = auto()
    BUFF = auto()
    DEBUFF = auto()
    UNKNOWN = auto()


@dataclass
class Intent:
    """What an enemy will do on its next turn.

    Simple enemies only use ``intent_type`` + ``value`` (damage for ATTACK, block
    for BLOCK). Bosses describe a named move with extras that resolve after the
    main action, in this order: ``block`` → ``buffs`` → ``debuffs`` → ``cards``.

    * ``hits``: an ATTACK hits ``hits`` times for ``value`` each (block absorbs
      every hit separately).
    * ``move`` / ``move_id``: Spanish name shown in the tooltip, and a stable id
      the presentation layer uses to pick a matching animation.
    * ``debuffs`` / ``buffs``: ``(status name, stacks)`` given to the hero / to
      the enemy itself.
    * ``cards``: ``(status card id, count, pile)`` added to the hero's
      ``"draw"`` pile (shuffled in), ``"discard"`` pile or ``"hand"``.
    """
    intent_type: IntentType
    value: int = 0
    hits: int = 1
    move: str = ""
    move_id: str = ""
    block: int = 0
    debuffs: tuple[tuple[str, int], ...] = ()
    buffs: tuple[tuple[str, int], ...] = ()
    cards: tuple[tuple[str, int, str], ...] = ()
    description: str = ""

    @property
    def is_multi_hit(self) -> bool:
        return self.intent_type == IntentType.ATTACK and self.hits > 1


@dataclass
class StatusEffect:
    name: str
    stacks: int
    is_buff: bool


# Status "Veneno": loses its stacks in HP at the start of its turn, then 1 stack wears off.
POISON: str = "Veneno"
# Status "Marcado": every hit it takes deals its stacks as extra damage (cleared when your turn ends).
MARKED: str = "Marcado"

# Status "Débil": the one who has it deals 25 % less attack damage (rounded down).
WEAK: str = "Débil"
WEAK_FACTOR_NUM, WEAK_FACTOR_DEN = 3, 4

# Boss statuses (floor 1 bosses, see ``application/enemy_ai.py``).
# "Vulnerable": takes 50 % more damage from attacks (rounded down).
VULNERABLE: str = "Vulnerable"
VULNERABLE_NUM, VULNERABLE_DEN = 3, 2
# "Frágil": block gained from cards is 25 % lower (rounded down).
FRAIL: str = "Frágil"
FRAIL_NUM, FRAIL_DEN = 3, 4
# "Enredado": draws 1 card less per stack at the start of the next turn (then it is gone).
ENTANGLED: str = "Enredado"
# "Fuerza" (enemies): every hit deals +stacks damage. Permanent.
STRENGTH: str = "Fuerza"
# "Espadas" (El Caballero Hueco): how many floating swords he has; some moves hit once per sword.
BLADES: str = "Espadas"

# Spanish rule text of every status, for tooltips.
STATUS_TEXT: dict[str, str] = {
    POISON: "Pierde tantos PV como acumulaciones al inicio de su turno; luego baja 1.",
    MARKED: "Cada golpe que recibe inflige tantos puntos extra como acumulaciones.",
    WEAK: "Inflige un 25 % menos de daño con ataques.",
    VULNERABLE: "Recibe un 50 % más de daño de ataques.",
    FRAIL: "Gana un 25 % menos de escudo con cartas.",
    ENTANGLED: "Roba 1 carta menos por acumulación al inicio de su próximo turno.",
    STRENGTH: "Cada golpe inflige tantos puntos extra como acumulaciones.",
    BLADES: "Espadas flotantes: algunos ataques golpean una vez por espada.",
}
# Statuses that wear off by 1 at the end of the hero's turn.
HERO_TIMED_DEBUFFS: tuple[str, ...] = (WEAK, VULNERABLE, FRAIL)


def weakened(amount: int, status_effects: list[StatusEffect]) -> int:
    """``amount`` reduced by Débil (x0.75, rounded down) when present."""
    if any(se.name == WEAK and se.stacks > 0 for se in status_effects):
        return amount * WEAK_FACTOR_NUM // WEAK_FACTOR_DEN
    return amount


def vulnerable(amount: int, status_effects: list[StatusEffect]) -> int:
    """``amount`` raised by Vulnerable (x1.5, rounded down) when present."""
    if status_stacks(status_effects, VULNERABLE) > 0:
        return amount * VULNERABLE_NUM // VULNERABLE_DEN
    return amount


def frail(amount: int, status_effects: list[StatusEffect]) -> int:
    """Block ``amount`` reduced by Frágil (x0.75, rounded down) when present."""
    if status_stacks(status_effects, FRAIL) > 0:
        return amount * FRAIL_NUM // FRAIL_DEN
    return amount


def add_status(status_effects: list[StatusEffect], name: str, stacks: int, *, is_buff: bool) -> None:
    """Add ``stacks`` to an existing status of that name, or append a new one."""
    for se in status_effects:
        if se.name == name:
            se.stacks += stacks
            return
    status_effects.append(StatusEffect(name, stacks, is_buff))


def tick_status(status_effects: list[StatusEffect], name: str) -> list[StatusEffect]:
    """One stack of ``name`` wears off; returns the list without exhausted statuses."""
    for se in status_effects:
        if se.name == name:
            se.stacks -= 1
    return [se for se in status_effects if se.stacks > 0]


@dataclass
class Enemy:
    id: str
    name: str
    max_hp: int
    current_hp: int
    block: int = 0
    intent: Intent = field(default_factory=lambda: Intent(IntentType.UNKNOWN))
    status_effects: list[StatusEffect] = field(default_factory=list)
    # Bosses: pattern AI id (``application/enemy_ai.py``), position in the pattern and
    # one-shot moves already used. Empty ``ai`` = the generic random intents.
    ai: str = ""
    ai_step: int = 0
    ai_used: set[str] = field(default_factory=set)
    is_boss: bool = False
    floor: int = 1                    # scales the numbers of pattern moves

    @property
    def is_alive(self) -> bool:
        return self.current_hp > 0

    @property
    def hp_ratio(self) -> float:
        return self.current_hp / self.max_hp if self.max_hp > 0 else 0.0


def deal_damage(enemy: "Enemy", amount: int) -> int:
    """One hit on ``enemy``: Marcado adds its stacks, block absorbs first. Returns HP lost."""
    if amount <= 0 or not enemy.is_alive:
        return 0
    amount += sum(se.stacks for se in enemy.status_effects if se.name == MARKED)
    absorbed = min(enemy.block, amount)
    enemy.block -= absorbed
    lost = min(enemy.current_hp, amount - absorbed)
    enemy.current_hp -= lost
    return lost


def status_stacks(status_effects: list[StatusEffect], name: str) -> int:
    return sum(se.stacks for se in status_effects if se.name == name)


@dataclass
class Player:
    name: str
    max_hp: int
    current_hp: int
    block: int = 0
    dexterity: int = 0    # bonus block added to every block card played
    attack_bonus: int = 0  # bonus damage added to every attack card played
    luck: int = 0          # better odds of golden cards/relics and higher relic tiers
    status_effects: list[StatusEffect] = field(default_factory=list)

    @property
    def is_alive(self) -> bool:
        return self.current_hp > 0

    @property
    def hp_ratio(self) -> float:
        return self.current_hp / self.max_hp if self.max_hp > 0 else 0.0


def enemy_hit_damage(enemy: Enemy, player: Player) -> int:
    """Damage of ONE hit of ``enemy``'s ATTACK intent on ``player``, before block.

    Printed value + Fuerza, then Débil on the enemy (x0.75), then Vulnerable on
    the hero (x1.5). Used by the turn pipeline and by the intent shown on screen.
    """
    base = enemy.intent.value + status_stacks(enemy.status_effects, STRENGTH)
    return vulnerable(weakened(max(0, base), enemy.status_effects), player.status_effects)
