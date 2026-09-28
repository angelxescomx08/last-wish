"""Animated pixel-art dungeon backdrop for combat.

Per frame this costs one full-screen blit of a pre-lit, pre-scaled picture,
two small additive glow blits, two flame sprites and ~150 particle rects.
Lighting is baked offline (see scripts/generate_dungeon_assets.py), so no
per-pixel work happens at run time.

Reuse: build any room with the generator, then feed its anchor points
(torches, window, drips, moonbeam) through ``dungeon.json``; the effects here
read them from there. ``budget`` scales particle counts (0 = no particles).
"""
from __future__ import annotations

import math

import pygame

from src.infrastructure.dungeon_assets import DungeonAssets, load_dungeon_assets
from src.presentation.fx.particles import EmitterConfig, ParticleSystem
from src.presentation.fx.sprite_animation import SpriteAnimation

FALLBACK_COLOR = (12, 12, 20)


def _rgb(values) -> tuple[tuple[int, int, int], ...]:
    return tuple(tuple(int(c) for c in v) for v in values)


class _Torch:
    def __init__(self, x: int, y: int, assets: DungeonAssets, phase: float) -> None:
        self.x, self.y = x, y
        self.phase = phase
        self.flame = SpriteAnimation(assets.flame_frames, assets.flame_durations, start=phase)
        self.glow_level = 1
        self._t = phase

    def update(self, dt: float) -> None:
        self.flame.update(dt)
        self._t += dt
        t, p = self._t, self.phase
        # layered sines -> irregular but smooth flicker, quantised to 3 glow levels
        v = math.sin(t * 7.3 + p) * 0.5 + math.sin(t * 13.1 + p * 2) * 0.3 + math.sin(t * 2.1) * 0.2
        self.glow_level = 0 if v < -0.35 else 2 if v > 0.35 else 1


class DungeonBackdrop:
    """Draws the combat room and its living details onto a 1280 x 720 surface."""

    def __init__(self, *, seed: int = 7, budget: float = 1.0, assets: DungeonAssets | None = None) -> None:
        self.assets = assets if assets is not None else load_dungeon_assets()
        self.torches: list[_Torch] = []
        self.systems: list[ParticleSystem] = []
        if self.assets is None:
            return
        a = self.assets
        room, pal, s = a.meta["room"], a.meta["palette"], a.scale
        self.torches = [_Torch(x, y, a, phase=i * 0.37) for i, (x, y) in enumerate(room["torches"])]

        # embers rising from each flame
        for i, (x, y) in enumerate(room["torches"]):
            self.systems.append(ParticleSystem(EmitterConfig(
                rate=7, lifetime=(0.9, 1.9), area=(x - 3, y - 20, 6, 4), vx=(-6, 6), vy=(-40, -22),
                gravity=-6, wobble=9, colors=_rgb(pal["ember"]), capacity=24), scale=s, seed=11 + i, budget=budget))

        # rain seen through the window, splashing on the sill
        x0, y0, x1, y1 = room["window_interior"]
        sill = room["sill_y"]
        splash = ParticleSystem(EmitterConfig(
            rate=0, lifetime=(0.12, 0.26), area=(0, 0, 0, 0), vx=(-28, 22), vy=(-55, -25), gravity=420,
            colors=_rgb(pal["splash"]), capacity=60), scale=s, seed=21, budget=budget)
        self.systems.append(ParticleSystem(EmitterConfig(
            rate=95, lifetime=(1.5, 1.5), area=(x0 - 6, y0 - 12, x1 - x0 + 14, 4), vx=(-60, -48), vy=(260, 320),
            colors=_rgb(pal["rain"][:1]), length=2, trail=4, trail_color=_rgb(pal["rain"])[2],
            floor_y=sill - 1, burst=2, capacity=110),
            scale=s, seed=22, clip=(x0, y0, x1 - x0, y1 - y0), on_floor=splash, budget=budget))

        # water dripping from ceiling cracks onto the floor
        floor = room["floor_y"] + 30
        for i, (dx, dy) in enumerate(room["drips"]):
            drop_splash = ParticleSystem(EmitterConfig(
                rate=0, lifetime=(0.15, 0.3), area=(0, 0, 0, 0), vx=(-24, 24), vy=(-45, -20), gravity=380,
                colors=_rgb(pal["splash"]), capacity=12), scale=s, seed=31 + i, budget=budget)
            self.systems.append(ParticleSystem(EmitterConfig(
                rate=0.45, lifetime=(3.0, 3.0), area=(dx, dy, 1, 1), vy=(0, 0), gravity=380,
                colors=_rgb(pal["drip"]), length=2, floor_y=floor, burst=3, capacity=4),
                scale=s, seed=41 + i, on_floor=drop_splash, budget=budget))

        # dust drifting in the moonbeam
        beam = room["moonbeam"]
        bx, by = beam["top"]
        self.systems.append(ParticleSystem(EmitterConfig(
            rate=5, lifetime=(3.0, 6.0), area=(bx - 30, by + 6, 80, 90), vx=(2, 7), vy=(-3, 3), wobble=4,
            colors=_rgb([pal["dust"][1], pal["dust"][0], pal["dust"][0], pal["dust"][1]]), capacity=30),
            scale=s, seed=51, budget=budget))

        for system in self.systems:
            system.prewarm(3.0)

    # ------------------------------------------------------------------

    @property
    def particle_count(self) -> int:
        total = 0
        for system in self.systems:
            total += system.count + (system.on_floor.count if system.on_floor else 0)
        return total

    def update(self, dt: float) -> None:
        for torch in self.torches:
            torch.update(dt)
        for system in self.systems:
            system.update(dt)

    def draw(self, surface: pygame.Surface) -> None:
        if self.assets is None:
            surface.fill(FALLBACK_COLOR)
            return
        a, s = self.assets, self.assets.scale
        surface.blit(a.room, (0, 0))
        half_glow = a.glow_frames[0].get_width() // 2
        fw, fh = a.flame_frames[0].get_size()
        for t in self.torches:
            surface.blit(a.glow_frames[t.glow_level], (t.x * s - half_glow, (t.y - 8) * s - half_glow),
                         special_flags=pygame.BLEND_RGB_ADD)
            surface.blit(t.flame.frame, (t.x * s - fw // 2, t.y * s - fh + s))
        for system in self.systems:
            system.draw(surface)
