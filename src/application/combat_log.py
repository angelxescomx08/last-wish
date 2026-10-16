"""Combat history (Hearthstone style): every card you played and every enemy action.

``CombatLog`` keeps the entries of one fight (oldest first, capped at
``MAX_ENTRIES`` so a long fight never grows without bound) and a ``version``
that changes on every add, so the screen re-renders only when needed.

* ``LogEntry.kind``: ``"turn"`` (separator "Turno N"), ``"hero"`` (a card you played),
  ``"enemy"`` (what an enemy did), ``"effect"`` (things that happen on their own:
  an enemy frozen, Fuego burning…).
* ``value`` + ``value_kind`` is the number on the tile: damage you dealt (``"damage"``),
  block you gained (``"block"``) or HP you lost (``"loss"``).
* **Who acted on whom** (Hearthstone's history: source → arrow → targets, each target with
  its damage splash and a skull when it died): ``source`` is the actor's portrait key
  (``HERO`` or an enemy name), ``verb`` the arrow icon, ``targets`` one ``LogTarget`` per
  character the action touched, with what happened to it.

``hero_entry`` builds the entry of a played card from the ``PlayResult`` (pure, no pygame).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from src.domain.card import Card, CardType

MAX_ENTRIES: int = 150
HERO: str = "hero"                  # portrait key of the hero

_TYPE_ICON = {CardType.ATTACK: "damage", CardType.SKILL: "block", CardType.POWER: "ritual",
              CardType.STATUS: "junk_card"}
_ELEMENT_ICON = {"Fuego": "fire", "Agua": "water", "Tierra": "earth", "Aire": "air"}


@dataclass(frozen=True)
class LogTarget:
    """One character an action touched, and what happened to it."""
    name: str
    portrait: str                   # HERO or the enemy's name (the screen draws it)
    hp: int = 0                     # HP lost
    block: int = 0                  # block gained
    healed: int = 0
    died: bool = False
    statuses: tuple[tuple[str, int], ...] = ()     # statuses / elements put on it (+stacks)
    reactions: tuple[str, ...] = ()                # reactions it suffered (Spanish names)
    enemy_id: str = ""              # to point at it on the battlefield ("" = the hero)
    aimed: bool = False             # the card was aimed at it
    blocked: bool = False           # it was hit but its block stopped everything


@dataclass(frozen=True)
class LogEntry:
    kind: str                       # "turn" | "hero" | "enemy" | "effect"
    turn: int
    icon: str                       # ui icon name
    title: str
    lines: tuple[str, ...] = ()
    value: int = 0
    value_kind: str = ""            # "damage" | "block" | "loss" | ""
    card: Card | None = field(default=None, compare=False)
    source: str = ""                # portrait key of who acted (HERO / enemy name)
    source_name: str = ""
    verb: str = ""                  # arrow icon between source and targets
    targets: tuple[LogTarget, ...] = ()


class CombatLog:
    def __init__(self, max_entries: int = MAX_ENTRIES) -> None:
        self.max_entries = max(1, max_entries)
        self._entries: list[LogEntry] = []
        self.version = 0

    @property
    def entries(self) -> list[LogEntry]:
        return self._entries

    def __len__(self) -> int:
        return len(self._entries)

    def add(self, entry: LogEntry) -> None:
        self._entries.append(entry)
        if len(self._entries) > self.max_entries:
            del self._entries[: len(self._entries) - self.max_entries]
        self.version += 1

    def turn(self, n: int) -> None:
        self.add(LogEntry("turn", n, "hourglass", f"Turno {n}"))

    def enemy(self, turn: int, icon: str, title: str, detail: str, hp_lost: int = 0, *,
              source: str = "", targets: tuple[LogTarget, ...] = ()) -> None:
        lines = tuple(_sentence(p) for p in detail.split(" · ") if p)
        self.add(LogEntry("enemy", turn, icon, title, lines, hp_lost, "loss" if hp_lost else "",
                          source=source, source_name=source, verb=icon, targets=targets))

    def effect(self, turn: int, icon: str, title: str, *lines: str,
               targets: tuple[LogTarget, ...] = ()) -> None:
        self.add(LogEntry("effect", turn, icon, title, tuple(lines), verb=icon, targets=targets))


def _sentence(text: str) -> str:
    """"pierdes 3 de vida" → "Pierdes 3 de vida." (no extra dot after "!" or ".")."""
    i = 1 if text[:1] in "¡¿" else 0                                # "¡todo…" → "¡Todo…"
    text = text[:i] + text[i:i + 1].upper() + text[i + 1:]
    return text if text[-1] in ".!?" else text + "."


def _plural(n: int, one: str, many: str) -> str:
    return f"{n} {one if n == 1 else many}"


def _status_gain(before: dict[str, int], after_effects) -> tuple[tuple[str, int], ...]:
    out = []
    for se in after_effects:
        gain = se.stacks - before.get(se.name, 0)
        if gain > 0:
            out.append((se.name, gain))
    return tuple(out)


def hero_entry(turn: int, card: Card, result, enemy_names: list[str], enemies_after,
               block_gain: int, reactions=(), *, statuses_before: list[dict[str, int]] | None = None,
               target: int | None = None, hero_name: str = "Héroe") -> LogEntry:
    """Entry for a card you just played. ``enemy_names`` / ``enemies_after`` are the enemies
    in the order of ``result.cast_hits``; ``reactions`` the ``ReactionEvent``s it caused;
    ``statuses_before`` each enemy's {status: stacks} before the play; ``target`` the aimed enemy."""
    lost = [0] * len(enemy_names)
    for hits in result.cast_hits:
        for i, n in enumerate(hits[: len(lost)]):
            lost[i] += max(0, n)
    lines: list[str] = []
    for i, n in enumerate(lost):
        if n > 0:
            dead = i < len(enemies_after) and not enemies_after[i].is_alive
            lines.append(f"{enemy_names[i]}: −{n} de vida" + (" (muere)" if dead else ""))
    if block_gain > 0:
        lines.append(f"Ganaste {block_gain} de escudo")
    drawn = sum(result.cast_drawn)
    if drawn > 0:
        lines.append("Robaste " + _plural(drawn, "carta", "cartas"))
    for fx in card.all_effects():
        if fx.element is not None and fx.element_stacks > 0:
            who = "todos" if fx.element_all else "al enemigo"
            lines.append(f"Aplicaste {fx.element_stacks} de {fx.element.value} " + ("a todos" if fx.element_all else who))
    names_by_id = {e.id: e.name for e in enemies_after}
    for ev in reactions:
        from src.domain.elements import reaction_summary   # local: keeps this module light
        target = names_by_id.get(ev.enemy_id, "")
        lines.append(f"¡{ev.reaction.value}! en {target}: {reaction_summary(ev.reaction, ev.stacks)}")
    for flag, label in ((result.combo, "¡Combo!"), (result.singular, "¡Singular!"), (result.void, "¡Vacío!"),
                        (result.spoil, "¡Despojo!"), (result.reaction, "¡Reacción!")):
        if flag:
            lines.append(label)
    title = f"Jugaste {card.name}" + (f" x{result.casts}" if result.casts > 1 else "")
    badges = card.element_badges() if hasattr(card, "element_badges") else []
    icon = _ELEMENT_ICON[badges[0].value] if badges else _TYPE_ICON.get(card.card_type, "cards")
    dealt = sum(lost)
    value, kind = (dealt, "damage") if dealt else (block_gain, "block") if block_gain else (0, "")
    # who it touched: every enemy that lost HP / got a status / reacted, the aimed one, the hero
    before = statuses_before or [{} for _ in enemy_names]
    by_enemy: dict[str, list[str]] = {}
    for ev in reactions:
        by_enemy.setdefault(ev.enemy_id, []).append(ev.reaction.value)
    targets: list[LogTarget] = []
    for i, name in enumerate(enemy_names):
        enemy = enemies_after[i] if i < len(enemies_after) else None
        if enemy is None:
            continue
        gained = _status_gain(before[i] if i < len(before) else {}, enemy.status_effects)
        reacted = tuple(by_enemy.get(enemy.id, ()))
        if lost[i] or gained or reacted or i == target:
            targets.append(LogTarget(name, name, hp=lost[i], died=not enemy.is_alive, statuses=gained,
                                     reactions=reacted, enemy_id=enemy.id, aimed=i == target))
    if block_gain > 0 or not targets:
        targets.append(LogTarget(hero_name, HERO, block=max(0, block_gain)))
    verb = {CardType.ATTACK: "attack_2", CardType.SKILL: "block" if block_gain else "buff",
            CardType.POWER: "buff"}.get(card.card_type, "buff")
    if any(t.statuses or t.reactions for t in targets if t.portrait != HERO) and card.card_type != CardType.ATTACK:
        verb = "debuff"
    return LogEntry("hero", turn, icon, title, tuple(lines) or ("Sin efecto visible",), value, kind, card,
                    source=HERO, source_name=hero_name, verb=verb, targets=tuple(targets))
