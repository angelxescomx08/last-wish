"""Animate the approved mage art ("El Mago") without deforming it.

Standard library only:

    python scripts/generate_mage_sprites.py

Input: ``assets/characters/mage_base.png`` — the approved illustration reduced
to native pixel art by ``scripts/make_mage_base.py``.

Same rules as the warrior (see generate_warrior_sprites.py): the drawing is
never cut, rotated or resampled. Idle moves whole pixel rows (breath, head a
beat later), sways the robe hem row by row, pulses the staff crystal with
orbiting motes and blinks once. Actions move the whole figure and carry
their energy in pixel effects: an arcane bolt (attack), a rune circle (guard)
and the shared hit flash (hurt).

Output (``assets/characters/``): mage_sheet.png (192 px), mage_sheet_96.png,
mage_sheet.json — same layout and animation names as the warrior sheets.
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
BASE_PATH = CHAR_DIR / "mage_base.png"
SHEET_PATH = CHAR_DIR / "mage_sheet.png"
SHEET_96_PATH = CHAR_DIR / "mage_sheet_96.png"
META_PATH = CHAR_DIR / "mage_sheet.json"

BASE = read_png(BASE_PATH)
BH, BW = len(BASE), len(BASE[0])
_xs = [x for y in range(BH) for x in range(BW) if BASE[y][x][3]]
_ys = [y for y in range(BH) for x in range(BW) if BASE[y][x][3]]
OX = CELL // 2 - (min(_xs) + max(_xs) + 1) // 2
OY = 190 - max(_ys)

# Landmarks in base coordinates (checked against the art)
HEAD_BOTTOM = 27          # chin line: rows above follow the head
CHEST_BOTTOM = 62         # just above the belt: rows above rise with the breath
CRYSTAL = (108, 17)       # centre of the staff crystal
EYES = [(68, 15), (73, 19)]

ARC = (120, 196, 255, 255)
ARC2 = (70, 124, 232, 255)
DEEP = (40, 64, 150, 255)
VIOLET = (178, 150, 255, 255)
PALE = (214, 236, 255, 255)


def _hsv(p):
    return colorsys.rgb_to_hsv(p[0] / 255, p[1] / 255, p[2] / 255)


def _sway_region() -> dict[tuple[int, int], float]:
    """Robe hem flaring out on the left: weight grows downwards and outwards."""
    reg = {}
    for y in range(84, BH - 24):
        for x in range(0, 52):
            p = BASE[y][x]
            if not p[3]:
                continue
            h, s, v = _hsv(p)
            if 0.45 < h < 0.75 and s > 0.25 or v < 0.25:
                wy = min(1.0, (y - 84) / 60)
                wx = min(1.0, max(0.0, (52 - x) / 26))
                reg[(x, y)] = wy * (0.3 + 0.7 * wx)
    return reg


SWAY = _sway_region()


def _crystal_pixels():
    pts = []
    for y in range(4, 34):
        for x in range(98, 118):
            p = BASE[y][x]
            h, s, v = _hsv(p)
            if p[3] and 0.5 < h < 0.72 and s > 0.35 and v > 0.4:
                pts.append((x, y))
    return pts


CRYSTAL_PX = _crystal_pixels()


def _blink():
    edits = {}
    for (x, y) in EYES:
        below = BASE[y + 1][x]
        edits[(x, y)] = below if below[3] else BASE[y][x - 1]
    return edits


BLINK = _blink()

# ---------------------------------------------------------------------------


def body_frame(*, chest=0, head=0, phase=0.0, amp=1.0, bias=0.0, blink=False, glow=0.0):
    out = {}
    for y in range(BH):
        up = head if y < HEAD_BOTTOM else chest if y < CHEST_BOTTOM else 0
        sy = min(BH - 1, y + up)
        wave = math.sin(phase - sy * 0.14)
        for x in range(BW):
            p = BASE[sy][x]
            w = SWAY.get((x, sy))
            if w is None:
                # a swaying neighbour may move into this pixel
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
    if blink:
        for (x, y), p in BLINK.items():
            out[(x, y - head)] = p
    if glow:
        for (x, y) in CRYSTAL_PX:
            q = (x, y - (head if y < HEAD_BOTTOM else chest if y < CHEST_BOTTOM else 0))
            p = out.get(q)
            if p and p[3]:
                out[q] = tuple(min(255, round(c + (255 - c) * glow * 0.6)) for c in p[:3]) + (255,)
    return {k: v for k, v in out.items() if v[3]}


def place(body, dx=0, dy=0):
    return {(x + OX + dx, y + OY + dy): p for (x, y), p in body.items()
            if 0 <= x + OX + dx < CELL and 0 <= y + OY + dy < CELL}


def crystal_at(dx=0, dy=0, chest=0):
    return CRYSTAL[0] + OX + dx, CRYSTAL[1] + OY + dy - chest


def motes(f, cx, cy, phase, n=3, r=9):
    """Small sparks orbiting the crystal on a tilted ellipse."""
    for i in range(n):
        a = phase + i * 2 * math.pi / n
        x, y = cx + math.cos(a) * r, cy + math.sin(a) * r * 0.45
        col = WHITE if math.sin(a) > 0 else ARC
        put(f, x, y, col)
        if math.sin(a) > 0.3:
            put(f, x + 1, y, ARC)


def flare(f, cx, cy, r):
    for k in range(16):
        a = k * math.pi / 8
        rr = r if k % 2 == 0 else r * 0.55
        for t in range(int(rr)):
            put(f, cx + math.cos(a) * t, cy + math.sin(a) * t, WHITE if t < rr * 0.4 else ARC)


def bolt(f, x, y, trail):
    """Arcane bolt: bright core, blue halo, sparkling tail."""
    for i in range(trail):
        tx = x - 5 - i * 2
        put(f, tx, y + round(math.sin(i * 1.3) * 2), ARC if i < trail // 2 else DEEP)
        if i % 3 == 0:
            put(f, tx, y - 3 + (i % 2), VIOLET)
    for dx in range(-6, 7):
        for dy in range(-4, 5):
            d = abs(dx) * 0.8 + abs(dy) * 1.3
            if d <= 6:
                put(f, x + dx, y + dy, WHITE if d <= 1.6 else PALE if d <= 3 else ARC if d <= 4.6 else ARC2)


def burst(f, x, y, r, seed):
    for k in range(12):
        a = k * math.pi / 6 + seed
        for t in (r * 0.5, r * 0.75, r):
            put(f, x + math.cos(a) * t, y + math.sin(a) * t, WHITE if t < r * 0.6 else ARC if t < r else DEEP)
    sparks(f, x, y, 8, r + 4, seed=seed, colors=(WHITE, ARC, VIOLET))


def rune_circle(f, cx, cy, r, level, spin):
    """Arcane guard: an upright ellipse of runes with bright nodes."""
    n = 90
    for i in range(n):
        a = i / n * 2 * math.pi
        if level < 1 and i % 3 == 0:
            continue
        x, y = cx + math.cos(a) * r * 0.45, cy + math.sin(a) * r
        put(f, x, y, ARC if level >= 0.5 else DEEP)
        put(f, x + (1 if math.cos(a) > 0 else -1), y, ARC2 if level >= 0.5 else DEEP)
    for k in range(6):
        a = spin + k * math.pi / 3
        x, y = cx + math.cos(a) * r * 0.45, cy + math.sin(a) * r
        put(f, x, y, WHITE)
        put(f, x, y - 1, VIOLET)
        put(f, x + math.cos(a) * -3, y + math.sin(a) * -3 * 2, ARC2)


# ---------------------------------------------------------------------------

TAU = 2 * math.pi
IDLE_N = 16
CHEST = [0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0]
HEAD = [0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 0, 0, 0]


def idle():
    frames = []
    for i in range(IDLE_N):
        ph = TAU * i / IDLE_N
        glow = 0.25 + 0.25 * math.sin(ph)
        f = place(body_frame(chest=CHEST[i], head=HEAD[i], phase=ph, amp=1.4, blink=(i == 10), glow=glow))
        cx, cy = crystal_at(chest=CHEST[i])
        motes(f, cx, cy, ph * 2)
        frames.append(f)
    return frames, [100] * IDLE_N, True


def idle0():
    f = place(body_frame(phase=0.0, amp=1.4, glow=0.25))
    cx, cy = crystal_at()
    motes(f, cx, cy, 0.0)
    return f


def attack():
    frames = []
    steps = [(-2, 0.7), (-3, 1.0), (2, 0.6), (3, 0.3), (2, 0.2), (1, 0.1), (0, 0.2)]
    for i, (dx, glow) in enumerate(steps):
        f = place(body_frame(phase=0.5 * i, amp=1.2, bias=1.0 if i < 2 else -1.0, glow=glow, chest=1 if i < 2 else 0),
                  dx)
        cx, cy = crystal_at(dx, chest=1 if i < 2 else 0)
        if i == 0:
            for k in range(8):                       # energy gathering into the crystal
                a = k * math.pi / 4
                put(f, cx + math.cos(a) * 10, cy + math.sin(a) * 10, ARC)
                put(f, cx + math.cos(a) * 7, cy + math.sin(a) * 7, WHITE)
        elif i == 1:
            flare(f, cx, cy, 11)
        elif i == 2:
            bolt(f, cx + 16, cy + 2, 5)
            flare(f, cx, cy, 6)
        elif i == 3:
            bolt(f, cx + 38, cy + 6, 9)
        elif i == 4:
            bolt(f, CELL - 14, cy + 10, 12)
            burst(f, CELL - 10, cy + 10, 8, seed=3)
        elif i == 5:
            sparks(f, CELL - 12, cy + 12, 8, 14, seed=7, colors=(ARC, VIOLET, DEEP))
        frames.append(f)
    frames.append(idle0())
    return frames, [70, 90, 45, 45, 70, 80, 70, 80], False


def guard():
    frames = []
    steps = [(-1, 0.4, 0.5), (-2, 1.0, 0.8), (-2, 1.0, 1.0), (-2, 1.0, 0.8), (-2, 0.5, 0.5), (-1, 0.0, 0.3)]
    for i, (dx, level, glow) in enumerate(steps):
        f = place(body_frame(phase=0.6 * i, amp=1.2, bias=0.8 if i < 4 else 0.2, glow=glow,
                             chest=1 if 0 < i < 4 else 0), dx)
        if level > 0:
            rune_circle(f, 150 + dx, 96, 44 if level >= 1 else 34, level, spin=i * 0.5)
        if 0 < i < 4:
            sparks(f, 150 + dx, 96, 5, 30, seed=13 + i, colors=(ARC, WHITE, VIOLET))
        cx, cy = crystal_at(dx)
        motes(f, cx, cy, i * 0.9, n=4, r=10)
        frames.append(f)
    frames.append(idle0())
    return frames, [60, 80, 80, 80, 90, 80, 80], False


def hurt():
    frames = []
    steps = [(-4, 1.0, (255, 255, 255)), (-8, 0.35, (255, 60, 60)), (-6, 0.15, (255, 60, 60)), (-2, 0.0, None)]
    for i, (dx, amount, col) in enumerate(steps):
        f = place(body_frame(phase=1.0 + i, amp=1.4, bias=2.0 - i * 0.6), dx)
        if col is not None and amount:
            f = tint(f, col, amount)
        if i in (0, 1):
            sparks(f, 96 + dx, 70, 9 if i == 0 else 6, 10 + i * 8, seed=21 + i, colors=(WHITE, ARC, VIOLET))
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
                write_png(CHAR_DIR / "mage_frames" / f"{name}_{i:02d}.png", rows_of(f, CELL), CELL, CELL)
    META_PATH.write_text(json.dumps({
        "cell": CELL, "columns": cols,
        "sheets": {str(CELL): SHEET_PATH.name, str(CELL // 2): SHEET_96_PATH.name},
        "animations": meta}, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {SHEET_PATH.name}, {SHEET_96_PATH.name} and {META_PATH.name}")


if __name__ == "__main__":
    main()
