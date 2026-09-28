"""Measure the real per-frame cost of the combat backdrop with pygame.

    uv run python scripts/bench_backdrop.py

Runs headless (SDL dummy video driver), converts surfaces like the game does,
and reports the average update + draw time over 600 frames.
"""
import os
import sys
import time
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pygame  # noqa: E402

pygame.init()
screen = pygame.display.set_mode((1280, 720))

from src.presentation.ui.dungeon_backdrop import DungeonBackdrop  # noqa: E402

backdrop = DungeonBackdrop()
frames = 600
start = time.perf_counter()
for _ in range(frames):
    backdrop.update(1 / 60)
    backdrop.draw(screen)
elapsed = (time.perf_counter() - start) / frames * 1000
print(f"backdrop: {elapsed:.3f} ms per frame ({backdrop.particle_count} particles); "
      f"a 60 FPS frame has 16.7 ms")
pygame.quit()
