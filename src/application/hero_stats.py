"""Hero sheet: every stat of the hero, where each point comes from and what it does.

``hero_sheet(run, state=None)`` builds a ``HeroSheet`` for the character screen
(no pygame). Each ``HeroStat`` carries its value, the character's base value and
the ``sources`` that add to it (one per relic, "Pruebas", "Este combate"), plus a
plain Spanish sentence of what the number does right now, so the screen can draw
"base + bonus" bars and explain them. Inside a combat the live values (current HP,
mana maximum, dexterity gained from cards…) come from the ``CombatState``.

Per-relic contributions are measured by calling each ``relic_effects`` query with
that relic alone, so a new relic that changes a stat shows up without extra code.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from src.application import relic_effects
from src.domain.card import CardType
from src.domain.chroma import CHROMA_DEFS
from src.domain.combat import CombatState
from src.domain.pile import Hand
from src.domain.rarity import Rarity, luck_chroma_multiplier, rarity_odds
from src.domain.relic import Relic
from src.domain.run import Run
from src.domain.tuning import TUNING, chroma_chance, hero_luck

BASE_DRAW = 5


@dataclass(frozen=True)
class StatSource:
    label: str           # "Orbe de Fuego", "Pruebas", "Este combate"
    amount: int


@dataclass(frozen=True)
class HeroStat:
    key: str              # "hp", "mana", "attack", "dexterity", "luck", "draw", "hand"
    name: str             # Spanish label
    icon: str             # ui icon name
    value: int            # total now
    base: int             # the character's own value
    sources: tuple[StatSource, ...] = ()
    effect: str = ""      # what the value does, in a sentence
    current: int | None = None   # HP: current value (value = maximum)
    reference: int = 10   # bar scale (the bar grows past it when needed)

    @property
    def bonus(self) -> int:
        return self.value - self.base

    def breakdown(self) -> str:
        """"Base 4 · Orbe de Fuego +2 · Pruebas +1"."""
        parts = [f"Base {self.base}"]
        for s in self.sources:
            if s.amount:
                parts.append(f"{s.label} {'+' if s.amount > 0 else '−'}{abs(s.amount)}")
        return " · ".join(parts)


@dataclass
class HeroSheet:
    name: str
    title: str                      # "Luchadora resistente…" (character description)
    stats: list[HeroStat]
    gold: int
    floor: int
    deck_size: int
    deck_by_type: dict[str, int]
    relic_count: int
    golden_card_chance: float       # 0..1
    golden_relic_chance: float
    epic_relic_chance: float        # Épica or Legendaria
    statuses: list[tuple[str, int, bool]] = field(default_factory=list)   # (name, stacks, is_buff)
    turn: int | None = None

    def stat(self, key: str) -> HeroStat:
        return next(s for s in self.stats if s.key == key)


def _per_relic(relics: list[Relic], query: Callable[[list[Relic]], int]) -> list[StatSource]:
    empty = query([])
    out = []
    for r in relics:
        amount = query([r]) - empty
        if amount:
            out.append(StatSource(r.name, amount))
    return out


def _pruebas(amount: int) -> list[StatSource]:
    return [StatSource("Pruebas", amount)] if amount else []


def _golden_chance(kind: str, luck: int) -> float:
    boost = luck_chroma_multiplier(luck)
    return min(1.0, sum(min(1.0, chroma_chance(c, kind) * boost) for c in CHROMA_DEFS))


_TYPE_LABEL = {CardType.ATTACK: "Ataques", CardType.SKILL: "Habilidades",
               CardType.POWER: "Poderes", CardType.STATUS: "Estados"}


def hero_sheet(run: Run, state: CombatState | None = None) -> HeroSheet:
    stats = run.character.stats
    relics = list(state.relics) if state is not None else list(run.relics)

    # Vida
    hp_sources = _per_relic(relics, lambda rs: relic_effects.max_hp_bonus(rs) - TUNING.extra_max_hp)
    hp_sources += _pruebas(TUNING.extra_max_hp)
    max_hp = stats.max_hp + sum(s.amount for s in hp_sources)
    current = run.player_current_hp
    if state is not None:
        if state.player.max_hp != max_hp:
            hp_sources.append(StatSource("Este combate", state.player.max_hp - max_hp))
            max_hp = state.player.max_hp
        current = state.player.current_hp
    hp = HeroStat("hp", "Vida", "heal", max_hp, stats.max_hp, tuple(hp_sources),
                  "Si llega a 0, la partida termina. Se conserva entre salas.",
                  current=min(current, max_hp), reference=max_hp)

    # Maná
    mana_sources = _per_relic(relics, lambda rs: relic_effects.bonus_starting_mana(rs) - TUNING.extra_mana)
    mana_sources += _pruebas(TUNING.extra_mana)
    mana_total = stats.max_mana + sum(s.amount for s in mana_sources)
    if state is not None and state.mana.maximum != mana_total:
        mana_sources.append(StatSource("Este combate", state.mana.maximum - mana_total))
        mana_total = state.mana.maximum
    growth = relic_effects.max_mana_per_turn(relics)
    mana = HeroStat("mana", "Maná", "mana", mana_total, stats.max_mana, tuple(mana_sources),
                    f"Cada turno empiezas con {mana_total} de maná para jugar cartas."
                    + (f" Sube {growth} por turno." if growth else ""), reference=6)

    # Daño extra
    atk_sources = _per_relic(relics, relic_effects.extra_attack_damage) + _pruebas(TUNING.extra_damage)
    atk_total = stats.damage + sum(s.amount for s in atk_sources)
    if state is not None:
        live = state.player.attack_bonus + relic_effects.extra_attack_damage(relics)
        if live != atk_total:
            atk_sources.append(StatSource("Este combate", live - atk_total))
            atk_total = live
    attack = HeroStat("attack", "Ataque", "damage", atk_total, stats.damage, tuple(atk_sources),
                      f"Cada carta de ataque inflige +{atk_total} de daño.", reference=10)

    # Destreza
    dex_sources = _pruebas(TUNING.extra_dexterity)
    dex_total = stats.dexterity + TUNING.extra_dexterity
    if state is not None and state.player.dexterity != dex_total:
        dex_sources.append(StatSource("Este combate", state.player.dexterity - dex_total))
        dex_total = state.player.dexterity
    dexterity = HeroStat("dexterity", "Destreza", "block", dex_total, stats.dexterity, tuple(dex_sources),
                         f"Cada carta de escudo da +{dex_total} de escudo.", reference=10)

    # Suerte
    luck_sources = _pruebas(hero_luck(stats.luck) - stats.luck)
    luck_sources += _per_relic(relics, relic_effects.luck_bonus)
    luck_total = hero_luck(stats.luck) + relic_effects.luck_bonus(relics)
    gold_card, gold_relic = _golden_chance("card", luck_total), _golden_chance("relic", luck_total)
    odds = rarity_odds(luck_total)
    epic = odds[Rarity.EPIC] + odds[Rarity.LEGENDARY]
    luck = HeroStat("luck", "Suerte", "clover", luck_total, stats.luck, tuple(luck_sources),
                    f"En sobres, premios y gachapón: Rara o mejor {odds[Rarity.RARE] + epic:.0%} · "
                    f"carta dorada {gold_card:.0%}.", reference=20)

    # Robo y mano
    draw_sources = _per_relic(relics, lambda rs: relic_effects.extra_draw_per_turn(rs) - TUNING.extra_draw)
    draw_sources += _pruebas(TUNING.extra_draw)
    draw_total = BASE_DRAW + sum(s.amount for s in draw_sources)
    hand_max = state.hand.max_size if state is not None else Hand(cards=[]).max_size
    draw = HeroStat("draw", "Robo", "draw", draw_total, BASE_DRAW, tuple(draw_sources),
                    f"Robas {draw_total} cartas al empezar cada turno.", reference=10)
    hand = HeroStat("hand", "Mano máxima", "hand_cards", hand_max, Hand(cards=[]).max_size, (),
                    f"Puedes tener hasta {hand_max} cartas; las que no caben se quedan en el mazo.",
                    reference=10)

    deck_by_type: dict[str, int] = {}
    for card in run.deck:
        label = _TYPE_LABEL.get(card.card_type, "Otras")
        deck_by_type[label] = deck_by_type.get(label, 0) + 1

    statuses = [(fx.name, fx.stacks, fx.is_buff) for fx in state.player.status_effects] if state else []
    return HeroSheet(
        name=run.character.name, title=run.character.description,
        stats=[hp, mana, attack, dexterity, luck, draw, hand],
        gold=run.gold, floor=run.floor, deck_size=len(run.deck), deck_by_type=deck_by_type,
        relic_count=len(relics), golden_card_chance=gold_card, golden_relic_chance=gold_relic,
        epic_relic_chance=epic, statuses=statuses, turn=state.turn if state is not None else None,
    )
