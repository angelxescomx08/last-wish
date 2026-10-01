"""Preview an animated enemy sheet the way the method in docs/code-drawn-sprites.md asks.

    uv run scripts/preview_enemy_sheet.py [sheet_id]      # default: wraith

Writes to ``output/``:
  <id>-sheet-preview.png  every animation row, each frame zoomed ×3 (native px)
                          on a dark background, with a 1-px cell grid
  <id>-in-room.png        idle frame 0 in the combat room at game scale, next to
                          the hero, with the enemy rect's HP-bar line, to check
                          scale and label overlap
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pygame  # noqa: E402

from src.infrastructure.enemy_sprites import load_enemy_sheet  # noqa: E402

OUT = ROOT / "output"
BG = (34, 30, 44)
GRID = (52, 46, 66)
ZOOM = 3                       # native pixels -> 3 screen px (sheet frames are already ×2)
ENEMY_SLOT = (762, 125, 128, 150)     # CombatScene first enemy rect (x, y, w, h)
HERO_CENTER = (272, 187)


def _label(surface, text, pos):
    try:
        font = pygame.font.SysFont(None, 22)
    except Exception:          # fonts unavailable: preview still useful without labels
        return
    surface.blit(font.render(text, True, (230, 210, 150)), pos)


def contact_sheet(sheet) -> pygame.Surface:
    names = list(sheet.animations)
    cw, ch = sheet.size
    fw, fh = cw * ZOOM // 2, ch * ZOOM // 2
    cols = max(len(sheet.frames[n]) for n in names)
    pad = 24
    out = pygame.Surface((cols * fw, len(names) * (fh + pad)))
    out.fill(BG)
    for row, name in enumerate(names):
        y = row * (fh + pad) + pad
        ms = [round(d * 1000) for d in sheet.animations[name].durations]
        _label(out, f"{name}  ({len(ms)} frames, {sum(ms)} ms)", (6, y - pad + 4))
        for col, frame in enumerate(sheet.frames[name]):
            x = col * fw
            out.fill(GRID, (x, y, 1, fh))
            out.blit(pygame.transform.scale(frame, (fw, fh)), (x, y))
    return out


def in_room(sheet) -> pygame.Surface:
    out = pygame.Surface((1280, 720))
    out.fill((12, 12, 20))
    room = ROOT / "assets" / "dungeon" / "room_combat.png"
    if room.exists():
        out.blit(pygame.transform.scale(pygame.image.load(str(room)), (1280, 720)), (0, 0))
    hero = ROOT / "assets" / "characters" / "warrior_sheet.png"
    if hero.exists():
        cell = pygame.image.load(str(hero)).subsurface((0, 0, 192, 192))
        out.blit(cell, (HERO_CENTER[0] - 96, HERO_CENTER[1] - 96))
    x, y, w, h = ENEMY_SLOT
    ax, ay = x + w // 2, y + h + 6                       # same anchor as CombatScene
    frame = sheet.frames["idle"][0]
    out.blit(frame, (ax - sheet.anchor[0], ay - sheet.anchor[1]))
    out.fill((40, 160, 60), (x, y + h + 4, w, 13))       # HP bar
    out.fill((230, 200, 120), (x + 30, y - 16, w - 60, 10))   # name label
    return out


def main() -> None:
    sheet_id = sys.argv[1] if len(sys.argv) > 1 else "wraith"
    pygame.init()
    sheet = load_enemy_sheet(sheet_id)
    if sheet is None:
        sys.exit(f"no sheet assets/enemies/{sheet_id}_sheet.png/json")
    OUT.mkdir(exist_ok=True)
    pygame.image.save(contact_sheet(sheet), str(OUT / f"{sheet_id}-sheet-preview.png"))
    pygame.image.save(in_room(sheet), str(OUT / f"{sheet_id}-in-room.png"))
    print(f"wrote output/{sheet_id}-sheet-preview.png and output/{sheet_id}-in-room.png")


if __name__ == "__main__":
    main()
