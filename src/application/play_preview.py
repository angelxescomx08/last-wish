"""What playing a card would do, without doing it (for the aiming preview).

``preview_play(state, card_index, target)`` plays the card on a deep copy of the
combat (the real state and the global random generator are left untouched) and
reports, per enemy, the element it holds before and after, the reactions it
suffers and the HP it would lose. The combat screen shows it while you aim a
Mage card ("[fuego]3 + [agua]2 = ¡VAPOR! · 10 de daño"), so you see a reaction coming
before you commit.

``reacting_enemies(state, card)`` is the cheap version used while a card is only
hovered: the indices of living enemies an element of the card would react with.
"""
from __future__ import annotations

import copy
import random
from dataclasses import dataclass, field

from src.application.play_card import play_card
from src.domain.combat import CombatState
from src.domain.elements import (
    Element, Reaction, ReactionEvent, card_elements, element_of, element_stacks, reaction_for,
    would_react,
)


@dataclass
class EnemyPreview:
    index: int
    before: tuple[Element, int] | None          # element held now (and stacks)
    after: tuple[Element, int] | None           # element held after the play
    reactions: list[ReactionEvent] = field(default_factory=list)
    hp_loss: int = 0
    killed: bool = False

    @property
    def changed(self) -> bool:
        return bool(self.reactions) or self.before != self.after or self.hp_loss > 0


@dataclass
class PlayPreview:
    enemies: list[EnemyPreview]
    block_gain: int = 0
    reaction_keyword: bool = False               # a Reacción layer would resolve


def _held(enemy) -> tuple[Element, int] | None:
    el = element_of(enemy)
    return (el, element_stacks(enemy, el)) if el is not None else None


def preview_play(state: CombatState, card_index: int, target: int | None) -> PlayPreview | None:
    """Simulated result of ``play_card(state, card_index, target)``; None if it cannot be played."""
    if not (0 <= card_index < state.hand.count):
        return None
    rng = random.getstate()
    try:
        sim = copy.deepcopy(state)
        before = [(e.current_hp, _held(e)) for e in sim.enemies]
        block = sim.player.block
        result = play_card(sim, card_index, target)
    finally:
        random.setstate(rng)
    if not result.success:
        return None
    by_id: dict[str, list[ReactionEvent]] = {}
    for ev in sim.reaction_log:
        by_id.setdefault(ev.enemy_id, []).append(ev)
    out = []
    for i, (enemy, (hp, held)) in enumerate(zip(sim.enemies, before)):
        out.append(EnemyPreview(i, held, _held(enemy), by_id.get(enemy.id, []),
                                max(0, hp - enemy.current_hp), hp > 0 and not enemy.is_alive))
    return PlayPreview(out, max(0, sim.player.block - block), result.reaction)


def reacting_enemies(state: CombatState, card) -> dict[int, Reaction]:
    """Living enemies an element of ``card`` would react with now → the reaction (first element wins)."""
    out: dict[int, Reaction] = {}
    for element, _everyone in card_elements(card):
        for i, enemy in enumerate(state.enemies):
            if i not in out and would_react(enemy, element):
                out[i] = reaction_for(element_of(enemy), element)
    return out
