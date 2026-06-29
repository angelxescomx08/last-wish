"""Procedural sound player — generates tones via pygame.mixer, no external files needed."""
from __future__ import annotations

import array
import math

import pygame


class SoundPlayer:
    """Generates and plays simple procedural sound effects.

    All sounds are synthesized at runtime using sine waves and frequency
    sweeps. Falls back to a no-op silently if mixer initialisation fails.
    """

    def __init__(self) -> None:
        self._ok       = False
        self._freq     = 22050
        self._channels = 1

        try:
            result = pygame.mixer.get_init()
            if not result:
                pygame.mixer.init(frequency=22050, size=-16, channels=1, buffer=512)
                result = pygame.mixer.get_init()
            if not result:
                return
            self._freq, _, self._channels = result
            self._ok = True
        except pygame.error:
            return

        self._card      = self._tone(660,  120, 0.28)
        self._attack    = self._sweep(320, 110, 180, 0.50)
        self._block     = self._tone(880,  200, 0.32)
        self._death     = self._sweep(220,  55, 420, 0.50)
        self._end_turn  = self._tone(520,   80, 0.22, "square")
        self._hit       = self._sweep(160,  75, 220, 0.45)
        self._win       = self._tone(1046, 320, 0.38)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def play_card(self)     -> None: self._play(self._card)
    def play_attack(self)   -> None: self._play(self._attack)
    def play_block(self)    -> None: self._play(self._block)
    def play_death(self)    -> None: self._play(self._death)
    def play_end_turn(self) -> None: self._play(self._end_turn)
    def play_hit(self)      -> None: self._play(self._hit)
    def play_win(self)      -> None: self._play(self._win)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _play(self, sound: pygame.mixer.Sound | None) -> None:
        if self._ok and sound is not None:
            sound.play()

    def _buf(self, mono: list[float]) -> array.array:
        """Convert mono float samples [-1, 1] into a mixer-compatible buffer."""
        out = array.array("h", [0] * (len(mono) * self._channels))
        for i, s in enumerate(mono):
            val = int(max(-1.0, min(1.0, s)) * 32767)
            for ch in range(self._channels):
                out[i * self._channels + ch] = val
        return out

    def _fade(self, i: int, n: int) -> float:
        """10 ms linear fade-in/out to eliminate clicks."""
        ramp = int(self._freq * 0.01)
        return min(1.0, min(i, n - i) / max(ramp, 1))

    def _tone(
        self, freq: float, duration_ms: int,
        volume: float = 0.4, waveform: str = "sine",
    ) -> pygame.mixer.Sound | None:
        try:
            n = int(self._freq * duration_ms / 1000)
            mono: list[float] = []
            for i in range(n):
                t = i / self._freq
                if waveform == "square":
                    s = 1.0 if math.sin(2 * math.pi * freq * t) >= 0 else -1.0
                else:
                    s = math.sin(2 * math.pi * freq * t)
                mono.append(volume * self._fade(i, n) * s)
            return pygame.mixer.Sound(buffer=self._buf(mono))
        except Exception:
            return None

    def _sweep(
        self, f_start: float, f_end: float,
        duration_ms: int, volume: float = 0.4,
    ) -> pygame.mixer.Sound | None:
        """Frequency sweep from f_start to f_end with integrated phase."""
        try:
            n     = int(self._freq * duration_ms / 1000)
            phase = 0.0
            mono: list[float] = []
            for i in range(n):
                progress = i / max(n - 1, 1)
                freq     = f_start + (f_end - f_start) * progress
                phase   += 2 * math.pi * freq / self._freq
                fade     = self._fade(i, n) * (1 - progress * 0.75)
                mono.append(volume * fade * math.sin(phase))
            return pygame.mixer.Sound(buffer=self._buf(mono))
        except Exception:
            return None
