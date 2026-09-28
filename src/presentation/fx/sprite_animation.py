"""Time-based frame animation, independent of the render frame rate."""
from __future__ import annotations

from typing import Generic, Sequence, TypeVar

T = TypeVar("T")


class SpriteAnimation(Generic[T]):
    """Cycles through ``frames`` using per-frame durations in seconds.

    Works with any frame type (usually ``pygame.Surface``). ``start`` offsets
    the clock so several copies of the same animation (e.g. torches) do not
    move in lock-step.
    """

    def __init__(self, frames: Sequence[T], durations: Sequence[float], *, loop: bool = True,
                 start: float = 0.0) -> None:
        if not frames or len(frames) != len(durations):
            raise ValueError("frames and durations must be non-empty and the same length")
        self.frames = list(frames)
        self.durations = [max(1e-6, float(d)) for d in durations]
        self.loop = loop
        self.total = sum(self.durations)
        self.time = max(0.0, start) % self.total if loop else max(0.0, start)

    def update(self, dt: float) -> None:
        self.time += max(0.0, dt)
        if self.loop:
            self.time %= self.total

    @property
    def index(self) -> int:
        t = self.time
        if not self.loop and t >= self.total:
            return len(self.frames) - 1
        for i, d in enumerate(self.durations):
            if t < d:
                return i
            t -= d
        return len(self.frames) - 1

    @property
    def frame(self) -> T:
        return self.frames[self.index]

    @property
    def finished(self) -> bool:
        return not self.loop and self.time >= self.total
