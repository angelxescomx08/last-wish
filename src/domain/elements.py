"""Mage elements (Fuego, Agua, Tierra, Aire) and their reactions.

Every elemental card **applies an element to an enemy** with stacks ("aplica 3 de
Fuego"). An enemy holds **one element at a time**:

* the same element again → the stacks add up;
* a different element → a **reaction**: both elements are consumed and the
  reaction resolves with ``stacks = old stacks + new stacks``.

What an element does on its own (it never wears off by itself):

* Fuego — the enemy loses that much HP at the end of its turn (ignores block);
* Agua — each hit the enemy deals does that much less damage;
* Tierra — each hit the enemy takes deals that much more damage;
* Aire — nothing alone; its reactions spread to every enemy.

Reactions (``REACTIONS``):

* Vapor (Fuego + Agua) — 2× stacks damage to that enemy;
* Magma (Fuego + Tierra) — it loses all its block and gets Vulnerable 2;
* Incendio (Fuego + Aire) — every enemy gets that many stacks of Fuego;
* Barro (Agua + Tierra) — you gain 3× stacks block;
* Congelar (Agua + Aire) — it loses its next action (bosses and elites only deal half damage);
* Tormenta de Arena (Tierra + Aire) — Débil 1 to every enemy.

Whole-combat modifiers live on ``CombatState`` (powers / cards set them):
``reaction_block`` (Piel de Granito), ``reaction_draw`` (Ojo del Huracán),
``catalyst`` (Catalizador: the next reaction this turn resolves twice) and
``archmage`` (Archimago: single-enemy reactions hit every enemy). Every reaction
is logged in ``CombatState.reaction_log`` for the combat screen.

Pure domain code: ``state`` is a ``CombatState`` (duck-typed to avoid an import cycle).
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from src.domain.entities import (
    FROZEN, VULNERABLE, WEAK, Enemy, StatusEffect, add_status, deal_damage, status_stacks,
)


class Element(Enum):
    FIRE = "Fuego"
    WATER = "Agua"
    EARTH = "Tierra"
    AIR = "Aire"


ELEMENT_NAMES: tuple[str, ...] = tuple(e.value for e in Element)

# ``FROZEN`` ("Congelado", in ``entities``): the enemy loses its next action
# (bosses/elites: half damage). Lasts one enemy turn.


class Reaction(Enum):
    STEAM = "Vapor"
    MAGMA = "Magma"
    WILDFIRE = "Incendio"
    MUD = "Barro"
    FREEZE = "Congelar"
    SANDSTORM = "Tormenta de Arena"


REACTIONS: dict[frozenset[Element], Reaction] = {
    frozenset({Element.FIRE, Element.WATER}): Reaction.STEAM,
    frozenset({Element.FIRE, Element.EARTH}): Reaction.MAGMA,
    frozenset({Element.FIRE, Element.AIR}): Reaction.WILDFIRE,
    frozenset({Element.WATER, Element.EARTH}): Reaction.MUD,
    frozenset({Element.WATER, Element.AIR}): Reaction.FREEZE,
    frozenset({Element.EARTH, Element.AIR}): Reaction.SANDSTORM,
}

STEAM_MULT: int = 2           # Vapor: damage = 2 × stacks
MAGMA_VULNERABLE: int = 2     # Magma: Vulnerable stacks
MUD_BLOCK_MULT: int = 3       # Barro: block = 3 × stacks
SANDSTORM_WEAK: int = 1       # Tormenta de Arena: Débil stacks on every enemy

# Spanish rule text (tooltips, glossary).
ELEMENT_TEXT: dict[Element, str] = {
    Element.FIRE: "Pierde tantos PV como acumulaciones al final de su turno (ignora el escudo).",
    Element.WATER: "Cada golpe que da hace tantos puntos menos de daño como acumulaciones.",
    Element.EARTH: "Cada golpe que recibe hace tantos puntos más de daño como acumulaciones.",
    Element.AIR: "No hace nada solo, pero sus reacciones afectan a todos los enemigos.",
}
REACTION_TEXT: dict[Reaction, str] = {
    Reaction.STEAM: "Fuego + Agua: le inflige el doble de las acumulaciones como daño.",
    Reaction.MAGMA: "Fuego + Tierra: pierde todo su escudo y recibe Vulnerable 2.",
    Reaction.WILDFIRE: "Fuego + Aire: todos los enemigos reciben esas acumulaciones de Fuego.",
    Reaction.MUD: "Agua + Tierra: ganas el triple de las acumulaciones como escudo.",
    Reaction.FREEZE: "Agua + Aire: pierde su próxima acción (jefes y élites: solo hacen la mitad de daño).",
    Reaction.SANDSTORM: "Tierra + Aire: todos los enemigos reciben Débil 1.",
}
FROZEN_TEXT: str = "Pierde su próxima acción. Jefes y élites: sus golpes hacen la mitad de daño."
REACTION_RULE: str = ("Si un enemigo con un elemento recibe otro distinto, se consumen los dos "
                      "y se provoca una reacción con la suma de sus acumulaciones.")


@dataclass(frozen=True)
class ReactionEvent:
    """One reaction that happened (read by the combat screen)."""
    enemy_id: str
    reaction: Reaction
    stacks: int


def element_of(enemy: Enemy) -> Element | None:
    """The element an enemy holds now (None if none)."""
    for se in enemy.status_effects:
        if se.stacks > 0 and se.name in ELEMENT_NAMES:
            return Element(se.name)
    return None


def element_stacks(enemy: Enemy, element: Element | None = None) -> int:
    """Stacks of ``element`` (default: whichever element it holds)."""
    element = element or element_of(enemy)
    return status_stacks(enemy.status_effects, element.value) if element else 0


def would_react(enemy: Enemy, element: Element) -> bool:
    """Applying ``element`` to ``enemy`` now would cause a reaction."""
    current = element_of(enemy)
    return enemy.is_alive and current is not None and current is not element


def reaction_for(a: Element, b: Element) -> Reaction | None:
    return REACTIONS.get(frozenset({a, b}))


def _clear_elements(enemy: Enemy) -> None:
    enemy.status_effects = [se for se in enemy.status_effects if se.name not in ELEMENT_NAMES]


def apply_element(state, enemy: Enemy, element: Element, stacks: int, *,
                  spread: bool = True) -> list[Reaction]:
    """Put ``stacks`` of ``element`` on ``enemy``; returns the reactions it caused.

    ``spread=False`` is used by Incendio's own spread so a chain cannot loop.
    """
    if stacks <= 0 or not enemy.is_alive:
        return []
    current = element_of(enemy)
    if current is None or current is element:
        add_status(enemy.status_effects, element.value, stacks, is_buff=False)
        return []
    total = element_stacks(enemy, current) + stacks
    _clear_elements(enemy)
    reaction = reaction_for(current, element)
    times = 1
    if getattr(state, "catalyst", 0) > 0:          # Catalizador: this reaction resolves twice
        state.catalyst -= 1
        times = 2
    for _ in range(times):
        _resolve(state, enemy, reaction, total, spread)
    return [reaction]


def _targets(state, enemy: Enemy) -> list[Enemy]:
    """Archimago: a reaction on one enemy hits every living enemy."""
    if getattr(state, "archmage", False):
        return [e for e in state.enemies if e.is_alive]
    return [enemy]


def _resolve(state, enemy: Enemy, reaction: Reaction, stacks: int, spread: bool) -> None:
    if reaction is Reaction.STEAM:
        for e in _targets(state, enemy):
            deal_damage(e, STEAM_MULT * stacks)
    elif reaction is Reaction.MAGMA:
        for e in _targets(state, enemy):
            e.block = 0
            add_status(e.status_effects, VULNERABLE, MAGMA_VULNERABLE, is_buff=False)
    elif reaction is Reaction.WILDFIRE:
        add_status(enemy.status_effects, Element.FIRE.value, stacks, is_buff=False)
        if spread:
            for e in [x for x in state.enemies if x.is_alive and x is not enemy]:
                apply_element(state, e, Element.FIRE, stacks, spread=False)
    elif reaction is Reaction.MUD:
        state.player.block += MUD_BLOCK_MULT * stacks
    elif reaction is Reaction.FREEZE:
        for e in _targets(state, enemy):
            if status_stacks(e.status_effects, FROZEN) == 0:
                e.status_effects.append(StatusEffect(FROZEN, 1, False))
    elif reaction is Reaction.SANDSTORM:
        for e in [x for x in state.enemies if x.is_alive]:
            add_status(e.status_effects, WEAK, SANDSTORM_WEAK, is_buff=False)
    # Every reaction: Piel de Granito block, Ojo del Huracán draws, counter and log.
    state.player.block += getattr(state, "reaction_block", 0)
    state.pending_draws += getattr(state, "reaction_draw", 0)
    state.reactions_this_turn = getattr(state, "reactions_this_turn", 0) + 1
    log = getattr(state, "reaction_log", None)
    if log is not None:
        log.append(ReactionEvent(enemy.id, reaction, stacks))


def apply_to_all(state, element: Element, stacks: int) -> list[Reaction]:
    """``element`` on every living enemy (one by one, so each may react)."""
    out: list[Reaction] = []
    for e in [x for x in state.enemies if x.is_alive]:
        out += apply_element(state, e, element, stacks)
    return out


def burn(enemy: Enemy) -> int:
    """Fuego at the end of the enemy's turn: lose its stacks in HP (block does not help)."""
    stacks = element_stacks(enemy, Element.FIRE)
    if stacks <= 0 or not enemy.is_alive:
        return 0
    lost = min(enemy.current_hp, stacks)
    enemy.current_hp -= lost
    return lost


def is_frozen(enemy: Enemy) -> bool:
    return status_stacks(enemy.status_effects, FROZEN) > 0


def thaw(enemy: Enemy) -> None:
    enemy.status_effects = [se for se in enemy.status_effects if se.name != FROZEN]


def card_elements(card) -> list[tuple[Element, bool]]:
    """(element, applies to every enemy) of a card's printed chain (keyword layers excluded)."""
    return [(fx.element, fx.element_all) for fx in card.all_effects()
            if fx.element is not None and fx.element_stacks > 0]


def element_line(fx, verb: str = "") -> str:
    """"+2 de Fuego" / "Aplica 2 de Fuego a todos" for a layer that applies an element."""
    if fx.element is None or fx.element_stacks <= 0:
        return ""
    head = f"{verb} {fx.element_stacks}" if verb else f"+{fx.element_stacks}"
    return f"{head} de {fx.element.value}" + (" a todos" if fx.element_all else "")


def card_reacts(state, card, target: int | None = None) -> bool:
    """Playing ``card`` now would cause a reaction (keyword REACCIÓN).

    Targeted elements check ``target`` when it is a living enemy, else any living
    enemy (so a card in hand shows as ready when some target would react).
    """
    living = [e for e in state.enemies if e.is_alive]
    for element, everyone in card_elements(card):
        if everyone or target is None or not (0 <= target < len(state.enemies)) \
                or not state.enemies[target].is_alive:
            pool = living
        else:
            pool = [state.enemies[target]]
        if any(would_react(e, element) for e in pool):
            return True
    return False
