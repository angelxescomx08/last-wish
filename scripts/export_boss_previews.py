"""Animated GIF previews of the floor-1 bosses and the elites in the combat room (needs Pillow).

    uv run --with pillow scripts/export_boss_previews.py

For each boss (mycelid, weaver, knight) and elite (executioner, hag, gargoyle, minotaur,
scorpion) plays idle → every action → death through the real ``EnemyAnimator``
(particles and floating swords included) over the baked room, next to the hero, and
writes ``output/boss-<id>-preview.gif`` / ``output/elite-<id>-preview.gif``.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pygame  # noqa: E402
from PIL import Image  # noqa: E402

from src.infrastructure.enemy_sprites import BOSS_SHEET_IDS, ELITE_SHEET_IDS, load_enemy_sheet  # noqa: E402
from src.presentation.fx.enemy_animator import EnemyAnimator  # noqa: E402

OUT = ROOT / "output"
FPS = 20
CROP = pygame.Rect(150, 40, 1000, 320)
BOSS = (905, 314)
HERO_CENTER = (272, 187)
ORDER = {"mycelid": ["attack", "spores", "cast", "hurt", "death"],
         "weaver": ["attack", "feast", "web", "cast", "hurt", "death"],
         "knight": ["command", "attack", "double", "cast", "hurt", "death"],
         "executioner": ["cast", "attack", "sharpen", "behead", "hurt", "death"],
         "hag": ["cast", "attack", "brew", "voodoo", "hurt", "death"],
         "gargoyle": ["petrify", "dive", "attack", "cast", "hurt", "death"],
         "minotaur": ["paw", "charge", "attack", "cast", "hurt", "death"],
         "scorpion": ["sting", "attack", "cast", "spray", "hurt", "death"]}
HITS = {"command": 4, "feast": 4, "voodoo": 3, "dive": 3}


def main() -> None:
    pygame.init()
    pygame.display.set_mode((1, 1))
    room = pygame.transform.scale(pygame.image.load(str(ROOT / "assets/dungeon/room_combat.png")),
                                  (1280, 720))
    hero = pygame.image.load(str(ROOT / "assets/characters/warrior_sheet.png")).subsurface((0, 0, 192, 192))
    OUT.mkdir(exist_ok=True)
    only = set(sys.argv[1:])
    for sid in (*BOSS_SHEET_IDS, *ELITE_SHEET_IDS):
        if only and sid not in only:
            continue
        sheet = load_enemy_sheet(sid)
        anim = EnemyAnimator(sheet, seed=4)
        anim.blades = 4
        anim.target = (HERO_CENTER[0] + 10, HERO_CENTER[1] - 8)
        surf = pygame.Surface((1280, 720))
        frames: list[Image.Image] = []

        def record(seconds: float) -> None:
            for _ in range(int(seconds * FPS)):
                anim.update(1 / FPS)
                surf.blit(room, (0, 0))
                surf.blit(hero, (HERO_CENTER[0] - 96, HERO_CENTER[1] - 96))
                anim.draw(surf, BOSS)
                shot = surf.subsurface(CROP)
                frames.append(Image.frombytes("RGB", shot.get_size(), pygame.image.tobytes(shot, "RGB")))

        anim.draw(surf, BOSS)
        record(1.6)
        for name in ORDER[sid]:
            anim.play(name, hits=HITS.get(name, 1))
            record(anim.seconds(name) + (0.5 if name != "death" else 1.2))
        path = OUT / f"{'elite' if sid in ELITE_SHEET_IDS else 'boss'}-{sid}-preview.gif"
        frames[0].save(path, save_all=True, append_images=frames[1:], duration=1000 // FPS, loop=0,
                       optimize=True)
        print(f"wrote {path.relative_to(ROOT)} ({len(frames)} frames)")


if __name__ == "__main__":
    main()
