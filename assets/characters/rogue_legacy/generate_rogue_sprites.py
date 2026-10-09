"""Animate the approved rogue art ("La Pícara") without deforming it.

Standard library only:

    python scripts/generate_rogue_sprites.py

Input: ``assets/characters/rogue_base.png`` (made by ``make_hero_base.py rogue``).

Same rules as the other heroes: the drawing is never cut, rotated or
resampled. Idle moves whole pixel rows (breath, head a beat later), sways the
tattered coat tails row by row and runs a glint along both daggers. Actions
move the whole figure and carry their energy in pixel effects: a shadow dash
with after-images and a crossed double slash (attack), a smoky side-step with
glinting daggers (guard), and the shared hit flash (hurt).

Output (``assets/characters/``): rogue_sheet.png (192 px), rogue_sheet_96.png,
rogue_sheet.json — same layout and animation names as the other heroes.
"""
from __future__ import annotations

import colorsys
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from generate_warrior_sprites import (  # noqa: E402  (shared pixel helpers)
    CELL, WHITE, halve, put, read_png, rows_of, sparks, tint, write_png, write_sheet,
)

ROOT = Path(__file__).resolve().parent.parent
CHAR_DIR = ROOT / "assets" / "characters"
BASE_PATH = CHAR_DIR / "rogue_base.png"
SHEET_PATH = CHAR_DIR / "rogue_sheet.png"
SHEET_96_PATH = CHAR_DIR / "rogue_sheet_96.png"
META_PATH = CHAR_DIR / "rogue_sheet.json"

BASE = read_png(BASE_PATH)
BH, BW = len(BASE), len(BASE[0])
_xs = [x for y in range(BH) for x in range(BW) if BASE[y][x][3]]
_ys = [y for y in range(BH) for x in range(BW) if BASE[y][x][3]]
OX = CELL // 2 - (min(_xs) + max(_xs) + 1) // 2
OY = 190 - max(_ys)

# Landmarks in base coordinates (checked against the art)
HEAD_BOTTOM = 30          # chin line
CHEST_BOTTOM = 55         # above the hands, so hands and daggers never shift
BLADE_BOXES = [(24, 84, 46, 126), (68, 60, 102, 80)]   # low dagger, high dagger (x0, y0, x1, y1)

SILVER = (236, 238, 246, 255)
PALE = (200, 190, 230, 255)
PURPLE = (160, 90, 210, 255)
PURPLE2 = (104, 52, 150, 255)
SHADOW = (58, 30, 84, 255)


def _hsv(p):
    return colorsys.rgb_to_hsv(p[0] / 255, p[1] / 255, p[2] / 255)


def _sway_region():
    """Tattered coat tails on both hips; weight grows downwards."""
    reg = {}
    for y in range(72, 132):
        for x in range(BW):
            p = BASE[y][x]
            if not p[3]:
                continue
            h, s, v = _hsv(p)
            purple = (h > 0.75 or h < 0.02) and s > 0.18 and v > 0.18
            if purple and (x < 50 or x > 70):
                wy = min(1.0, (y - 72) / 45)
                reg[(x, y)] = wy
    return reg


SWAY = _sway_region()


def _blades():
    out = []
    for (x0, y0, x1, y1) in BLADE_BOXES:
        pts = [(x, y) for y in range(y0, y1) for x in range(x0, x1)
               if BASE[y][x][3] and _hsv(BASE[y][x])[1] < 0.2 and _hsv(BASE[y][x])[2] > 0.6]
        pts.sort(key=lambda q: q[1] if x1 - x0 < y1 - y0 else q[0])
        out.append(pts)
    return out


BLADES = _blades()

# ---------------------------------------------------------------------------


def body_frame(*, chest=0, head=0, phase=0.0, amp=1.0, bias=0.0):
    out = {}
    for y in range(BH):
        up = head if y < HEAD_BOTTOM else chest if y < CHEST_BOTTOM else 0
        sy = min(BH - 1, y + up)
        wave = math.sin(phase - sy * 0.18)
        for x in range(BW):
            p = BASE[sy][x]
            w = SWAY.get((x, sy))
            if w is None:
                for off in (-2, -1, 1, 2):
                    ww = SWAY.get((x - off, sy))
                    if ww is not None and round(amp * ww * wave + bias * ww) == off:
                        p = BASE[sy][x - off]
                        break
            else:
                own = round(amp * w * wave + bias * w)
                if own:
                    src = x - own
                    q = BASE[sy][src] if 0 <= src < BW else (0, 0, 0, 0)
                    if (src, sy) in SWAY:
                        p = q
                    elif q[3] == 0:
                        p = (0, 0, 0, 0)
            out[(x, y)] = p
    return {k: v for k, v in out.items() if v[3]}


def place(body, dx=0, dy=0):
    return {(x + OX + dx, y + OY + dy): p for (x, y), p in body.items()
            if 0 <= x + OX + dx < CELL and 0 <= y + OY + dy < CELL}


def ghost(f, body, dx, color, parity):
    """After-image: a dithered, tinted silhouette left behind by fast motion."""
    for (x, y), p in body.items():
        X, Y = x + OX + dx, y + OY
        if (X + Y + parity) % 2 == 0 and 0 <= X < CELL and 0 <= Y < CELL and (X, Y) not in f:
            f[(X, Y)] = color


def glint(f, blade, t, dx=0):
    if not blade:
        return
    x, y = blade[min(len(blade) - 1, int(t * (len(blade) - 1)))]
    x, y = x + OX + dx, y + OY
    for ddx, ddy, c in ((0, 0, WHITE), (1, 0, WHITE), (-1, 0, SILVER), (0, -1, WHITE), (0, 1, SILVER),
                        (0, -2, PALE), (0, 2, PALE), (2, 0, PALE), (-2, 0, PALE)):
        put(f, x + ddx, y + ddy, c)


def crescent(f, cx, cy, r, a0, a1, width, colors=(WHITE, PALE, PURPLE)):
    steps = 80
    for i in range(steps + 1):
        t = i / steps
        a = a0 + (a1 - a0) * t
        w = width * math.sin(math.pi * t) ** 0.8
        k = 0.0
        while k <= w:
            col = colors[0] if k < w * 0.4 else colors[1] if k < w * 0.75 else colors[2]
            put(f, cx + math.cos(a) * (r - k), cy + math.sin(a) * (r - k), col)
            k += 0.5


def smoke(f, cx, cy, r, seed, fade=0):
    for i in range(14):
        a = (seed * 1.3 + i * 2.4) % (2 * math.pi)
        d = r * (0.3 + 0.7 * ((i * 37 + seed * 11) % 10) / 10)
        x, y = cx + math.cos(a) * d, cy + math.sin(a) * d * 0.6
        col = (SHADOW, PURPLE2, (90, 80, 100, 255))[(i + fade) % 3]
        for ddx, ddy in ((0, 0), (1, 0), (0, 1), (1, 1)):
            if fade and (i + ddx) % (fade + 1):
                continue
            put(f, x + ddx, y + ddy, col)


# ---------------------------------------------------------------------------

TAU = 2 * math.pi
IDLE_N = 16
CHEST = [0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0]
HEAD = [0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 0, 0, 0]


def idle():
    frames = []
    for i in range(IDLE_N):
        ph = TAU * i / IDLE_N
        f = place(body_frame(chest=CHEST[i], head=HEAD[i], phase=ph, amp=1.4))
        if 6 <= i <= 9:                            # a glint runs down each blade once per loop
            glint(f, BLADES[0], (i - 6) / 3)
        if 10 <= i <= 13:
            glint(f, BLADES[1], (i - 10) / 3)
        frames.append(f)
    return frames, [100] * IDLE_N, True


def idle0():
    return place(body_frame(phase=0.0, amp=1.4))


def attack():
    frames = []
    base = body_frame(phase=0.0, amp=1.0)
    steps = [(-3, 1.2, None), (14, -2.4, "dash"), (14, -2.2, "x1"), (13, -1.6, "x2"), (12, -1.0, "fade"),
             (6, -0.5, "back"), (2, 0.0, None)]
    for i, (dx, bias, fx) in enumerate(steps):
        body = body_frame(phase=0.6 * i, amp=1.2, bias=bias)
        f = place(body, dx)
        cx, cy = 150 + dx // 2, 92
        if fx == "dash":
            ghost(f, base, dx - 6, PURPLE2, 0)
            ghost(f, base, dx - 12, SHADOW, 1)
        elif fx == "x1":
            ghost(f, base, dx - 8, SHADOW, 0)
            crescent(f, cx, cy, 26, -2.2, -0.5, 5)
        elif fx == "x2":
            crescent(f, cx, cy, 26, -2.2, -0.5, 4, (PALE, PURPLE, PURPLE2))
            crescent(f, cx, cy + 4, 26, 2.3, 0.5, 6)
            sparks(f, cx + 20, cy, 10, 12, seed=4, colors=(WHITE, SILVER, PURPLE))
        elif fx == "fade":
            crescent(f, cx, cy + 4, 26, 2.3, 0.5, 3, (PURPLE, PURPLE2, SHADOW))
            sparks(f, cx + 22, cy + 2, 7, 18, seed=9, colors=(PURPLE, SHADOW))
        elif fx == "back":
            ghost(f, base, dx + 6, SHADOW, 1)
        frames.append(f)
    frames.append(idle0())
    return frames, [70, 45, 50, 60, 90, 70, 70, 80], False


def guard():
    frames = []
    base = body_frame(phase=0.0, amp=1.0)
    steps = [(-2, 1.0), (-8, 2.0), (-8, 1.6), (-7, 1.2), (-4, 0.6), (-1, 0.2)]
    for i, (dx, bias) in enumerate(steps):
        f = place(body_frame(phase=0.7 * i, amp=1.2, bias=bias, chest=1 if 0 < i < 4 else 0), dx)
        if i == 1:
            ghost(f, base, dx + 6, PURPLE2, 0)
            smoke(f, 96 + 4, 150, 16, seed=1)
        elif i == 2:
            smoke(f, 96 + 6, 146, 20, seed=2, fade=1)
        elif i == 3:
            smoke(f, 96 + 8, 142, 24, seed=3, fade=2)
        if 1 <= i <= 3:
            glint(f, BLADES[0], (i - 1) / 2, dx)
            glint(f, BLADES[1], (i - 1) / 2, dx)
        frames.append(f)
    frames.append(idle0())
    return frames, [60, 70, 90, 90, 90, 80, 80], False


def hurt():
    frames = []
    steps = [(-4, 1.0, (255, 255, 255)), (-8, 0.35, (255, 60, 60)), (-6, 0.15, (255, 60, 60)), (-2, 0.0, None)]
    for i, (dx, amount, col) in enumerate(steps):
        f = place(body_frame(phase=1.0 + i, amp=1.4, bias=2.0 - i * 0.6), dx)
        if col is not None and amount:
            f = tint(f, col, amount)
        if i in (0, 1):
            sparks(f, 96 + dx, 64, 9 if i == 0 else 6, 10 + i * 8, seed=21 + i, colors=(WHITE, PURPLE, SILVER))
        frames.append(f)
    frames.append(idle0())
    return frames, [70, 110, 110, 100, 90], False


ANIMATIONS = {"idle": idle, "attack": attack, "guard": guard, "hurt": hurt}


def main() -> None:
    frames, meta = {}, {}
    for row, (name, fn) in enumerate(ANIMATIONS.items()):
        cells, ms, loop = fn()
        frames[name] = cells
        meta[name] = {"row": row, "frames": len(cells), "durations_ms": ms, "loop": loop}
    cols = max(len(v) for v in frames.values())
    write_sheet(SHEET_PATH, frames, CELL, cols)
    write_sheet(SHEET_96_PATH, {k: [halve(f) for f in v] for k, v in frames.items()}, CELL // 2, cols)
    if "--frames" in sys.argv:
        for name, cells in frames.items():
            for i, f in enumerate(cells):
                write_png(CHAR_DIR / "rogue_frames" / f"{name}_{i:02d}.png", rows_of(f, CELL), CELL, CELL)
    META_PATH.write_text(json.dumps({
        "cell": CELL, "columns": cols,
        "sheets": {str(CELL): SHEET_PATH.name, str(CELL // 2): SHEET_96_PATH.name},
        "animations": meta}, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {SHEET_PATH.name}, {SHEET_96_PATH.name} and {META_PATH.name}")


if __name__ == "__main__":
    main()
