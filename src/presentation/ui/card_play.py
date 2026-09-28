"""Card play input — Slay the Spire style, as a small pygame-free state machine.

How a card is played (mouse):
  * Press on a card to pick it up. Dragging it keeps it under the cursor.
  * Cards that act on the hero or on every enemy are played by releasing them
    above the play line (out of the hand area). Released inside the hand, they
    go back.
  * Cards that need one enemy: once dragged above the play line the card
    stops at the aiming spot and an arrow runs from it to the cursor. Release
    over an enemy to play it there; release anywhere else to put it back.
    Dragging back into the hand also puts the aim away.
  * A quick click (press and release without dragging) keeps the card held:
    an aimed card shows its arrow straight away; the next click on an enemy
    plays it, a click above the play line plays a non-targeted card, and a
    click on empty space puts it back.
  * Right click or ESC cancels at any moment.

Keyboard: 1-9 pick a card, ←/→ (or Tab) change the target, Enter/Space play.

The scene feeds pointer events plus what is under the pointer, and executes
the ``PlayRequest`` returned when a card is played.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from src.application.play_card import TargetKind

DRAG_THRESHOLD = 8.0   # px the pointer must travel before a press becomes a drag


class Mode(Enum):
    IDLE = "idle"
    HOLDING = "holding"   # card follows the pointer (or waits for a click)
    AIMING = "aiming"     # enemy card parked at the aim spot, arrow to the pointer


@dataclass(frozen=True)
class PlayRequest:
    card_index: int
    target_index: int | None


class CardPlayInput:
    def __init__(self, play_line_y: int) -> None:
        self.play_line_y = play_line_y
        self.mode = Mode.IDLE
        self.card: int | None = None
        self.kind: TargetKind | None = None
        self.target: int | None = None       # enemy under the arrow (or chosen by keys)
        self.pointer: tuple[int, int] = (0, 0)
        self.sticky = False                  # picked with a click: waits for a second click
        self.keyboard_aim = False            # target chosen with keys: arrow ends on it
        self.by_key = False                  # picked with a number key: shown at the aim spot
        self._press: tuple[int, int] = (0, 0)
        self._dragged = False

    # ------------------------------------------------------------------ queries
    @property
    def active(self) -> bool:
        return self.mode is not Mode.IDLE

    @property
    def aiming(self) -> bool:
        return self.mode is Mode.AIMING

    @property
    def above_play_line(self) -> bool:
        return self.pointer[1] < self.play_line_y

    @property
    def armed(self) -> bool:
        """A non-targeted card that would be played if released now."""
        if self.mode is not Mode.HOLDING or self.kind is TargetKind.ENEMY:
            return False
        return self.by_key or ((self._dragged or self.sticky) and self.above_play_line)

    # ------------------------------------------------------------------ actions
    def pick(self, index: int, kind: TargetKind, pos: tuple[int, int]) -> None:
        """Pick up card ``index`` with the mouse (button pressed on it)."""
        self.mode = Mode.HOLDING
        self.card, self.kind, self.target = index, kind, None
        self.pointer = self._press = pos
        self.sticky = self.keyboard_aim = self.by_key = self._dragged = False

    def pick_with_key(self, index: int, kind: TargetKind, first_target: int | None) -> None:
        self.pick(index, kind, self.pointer)
        self.sticky = self.by_key = True
        if kind is TargetKind.ENEMY:
            self.mode = Mode.AIMING
            self.target = first_target
            self.keyboard_aim = first_target is not None

    def move(self, pos: tuple[int, int], enemy_under: int | None) -> None:
        if self.mode is Mode.IDLE:
            self.pointer = pos
            return
        if pos != self.pointer:
            self.keyboard_aim = self.by_key = False
        self.pointer = pos
        px, py = self._press
        if not self._dragged and (pos[0] - px) ** 2 + (pos[1] - py) ** 2 > DRAG_THRESHOLD ** 2:
            self._dragged = True
        if self.kind is TargetKind.ENEMY:
            if self.sticky:
                self.mode = Mode.AIMING
            elif self._dragged:
                self.mode = Mode.AIMING if self.above_play_line else Mode.HOLDING
            if self.mode is Mode.HOLDING:
                self.target = None
            elif not self.keyboard_aim:
                self.target = enemy_under

    def release(self, pos: tuple[int, int], enemy_under: int | None) -> PlayRequest | None:
        """Left button released. Returns the card to play, if any."""
        if self.mode is Mode.IDLE or self.sticky:
            return None
        self.move(pos, enemy_under)
        if not self._dragged:                 # plain click: keep holding it
            self.sticky = True
            if self.kind is TargetKind.ENEMY:
                self.mode = Mode.AIMING
                self.target = enemy_under
            return None
        return self._resolve()

    def click(self, pos: tuple[int, int], enemy_under: int | None) -> PlayRequest | None:
        """Left press while a card is held after a click (sticky mode)."""
        if self.mode is Mode.IDLE:
            return None
        self.move(pos, enemy_under)
        return self._resolve()

    def cycle_target(self, alive: list[int], step: int) -> None:
        if self.mode is not Mode.AIMING or not alive:
            return
        if self.target in alive:
            self.target = alive[(alive.index(self.target) + step) % len(alive)]
        else:
            self.target = alive[0] if step >= 0 else alive[-1]
        self.keyboard_aim = True

    def confirm(self) -> PlayRequest | None:
        """Enter/Space: play the held card on the current target."""
        if self.mode is Mode.IDLE or self.card is None:
            return None
        if self.kind is TargetKind.ENEMY and self.target is None:
            return None
        request = PlayRequest(self.card, self.target if self.kind is TargetKind.ENEMY else None)
        self.cancel()
        return request

    def cancel(self) -> bool:
        """Put the card back. True if something was held."""
        was_active = self.mode is not Mode.IDLE
        self.mode = Mode.IDLE
        self.card = self.kind = self.target = None
        self.sticky = self.keyboard_aim = self.by_key = self._dragged = False
        return was_active

    # ------------------------------------------------------------------ helpers
    def _resolve(self) -> PlayRequest | None:
        card = self.card
        if self.kind is TargetKind.ENEMY:
            request = PlayRequest(card, self.target) if (self.aiming and self.target is not None) else None
        else:
            request = PlayRequest(card, None) if self.above_play_line else None
        self.cancel()
        return request
