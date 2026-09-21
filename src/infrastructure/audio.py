"""Shared sound effects and continuous original music for the whole game."""
from __future__ import annotations

import math
from pathlib import Path

import pygame

_ASSETS = Path(__file__).resolve().parents[2] / 'assets' / 'audio'
_EFFECTS = (
    'card', 'attack', 'block', 'death', 'end_turn', 'hit', 'win',
    'nav', 'confirm', 'cancel', 'purchase', 'open_pack', 'reward', 'error', 'travel',
)
_MAX_VOICES = 3
_REPEAT_GAP_MS = 80
_REPEAT_GAPS = {'nav': 120, 'error': 300}
_IMPORTANT_CUES = {'win', 'purchase', 'open_pack', 'reward', 'travel'}


def _volume(value: float) -> float:
    return max(0.0, min(1.0, value)) if math.isfinite(value) else 0.0


class SoundPlayer:
    """Share one instance across scenes so music, mixing and variations persist."""

    def __init__(self, *, sfx_volume: float = 0.7, music_volume: float = 0.35) -> None:
        self._ok = False
        self._sounds: dict[str, list[pygame.mixer.Sound]] = {}
        self._next_variant: dict[str, int] = {}
        self._last_played: dict[str, int] = {}
        self._sfx_volume = _volume(sfx_volume)
        self._music_volume = _volume(music_volume)
        self._music_started = False
        self._pending: tuple[str, int] | None = None
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
            self._ok = bool(pygame.mixer.get_init())
        except pygame.error:
            return
        if self._ok:
            self._load_sounds()

    def _load_sounds(self) -> None:
        for name in _EFFECTS:
            variants = []
            for variant in range(3):
                try:
                    sound = pygame.mixer.Sound(str(_ASSETS / f'{name}_{variant}.wav'))
                    sound.set_volume(self._sfx_volume)
                    variants.append(sound)
                except (pygame.error, OSError):
                    continue
            self._sounds[name] = variants

    def set_volumes(self, sfx_volume: float, music_volume: float) -> None:
        self._sfx_volume = _volume(sfx_volume)
        self._music_volume = _volume(music_volume)
        if self._sfx_volume == 0:
            self._pending = None
        if not self._ok or not pygame.mixer.get_init():
            return
        for variants in self._sounds.values():
            for sound in variants:
                sound.set_volume(self._sfx_volume)
        pygame.mixer.music.set_volume(self._music_volume)

    def start_music(self) -> None:
        """Start once; scene transitions never rewind the loop."""
        if self._music_started or not self._ok or not pygame.mixer.get_init():
            return
        try:
            pygame.mixer.music.load(str(_ASSETS / 'last_wish_theme.wav'))
            # Loading music resets its volume, so apply preferences after load.
            pygame.mixer.music.set_volume(self._music_volume)
            pygame.mixer.music.play(loops=-1, fade_ms=1200)
            self._music_started = True
        except (pygame.error, OSError):
            return

    def stop_music(self) -> None:
        if self._music_started and pygame.mixer.get_init():
            pygame.mixer.music.stop()
            pygame.mixer.music.unload()
        self._music_started = False
        self._pending = None

    def update(self) -> None:
        """Let a reward cue finish waiting for a combat burst without cutting audio."""
        if self._pending is None:
            return
        name, requested_at = self._pending
        now = pygame.time.get_ticks()
        if now - requested_at > 1000 or self._try_play(name, now):
            self._pending = None

    def play_card(self) -> None: self._play('card')
    def play_attack(self) -> None: self._play('attack')
    def play_block(self) -> None: self._play('block')
    def play_death(self) -> None: self._play('death')
    def play_end_turn(self) -> None: self._play('end_turn')
    def play_hit(self) -> None: self._play('hit')
    def play_win(self) -> None: self._play('win')
    def play_nav(self) -> None: self._play('nav')
    def play_confirm(self) -> None: self._play('confirm')
    def play_cancel(self) -> None: self._play('cancel')
    def play_purchase(self) -> None: self._play('purchase')
    def play_open_pack(self) -> None: self._play('open_pack')
    def play_reward(self) -> None: self._play('reward')
    def play_error(self) -> None: self._play('error')
    def play_travel(self) -> None: self._play('travel')

    def _play(self, name: str) -> None:
        now = pygame.time.get_ticks()
        if not self._try_play(name, now) and name in _IMPORTANT_CUES:
            if self._pending is None or name == 'win':
                self._pending = (name, now)

    def _try_play(self, name: str, now: int) -> bool:
        """True means handled (including mute/cooldown); False means mixer busy."""
        variants = self._sounds.get(name, [])
        if not self._ok or not variants or not pygame.mixer.get_init() or self._sfx_volume == 0:
            return True
        gap = _REPEAT_GAPS.get(name, _REPEAT_GAP_MS)
        if now - self._last_played.get(name, -gap) < gap:
            return True
        voices = sum(sound.get_num_channels()
                     for group in self._sounds.values() for sound in group)
        if voices >= _MAX_VOICES:
            return False
        channel = pygame.mixer.find_channel()
        if channel is None:
            return False
        index = self._next_variant.get(name, 0)
        channel.set_volume(1.0)
        channel.play(variants[index])
        self._last_played[name] = now
        self._next_variant[name] = (index + 1) % len(variants)
        return True
