"""Looping pixel-art dungeon background for combat (test piece).

Standard library only:

    python scripts/generate_dungeon_background.py

Native 640 x 360, shown x2 (1280 x 720, the game's virtual canvas), so its pixel
size sits close to the hero's.
Mood: cold moonlit stone and rain behind a barred window against warm
flickering torches, rising embers and dust drifting in the moonbeam.
Every effect is periodic over the loop, so it repeats seamlessly forever.

Output (``assets/backgrounds/``):
    dungeon_sheet.png   frames in a grid (8 columns), 640 x 360 each
    dungeon_sheet.json  frame count, columns, frame duration
"""
from __future__ import annotations

import json
import math
import struct
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "backgrounds"
W, H = 640, 360
N = 32                 # frames per loop
FRAME_MS = 90
COLS = 8


def hx(h: str):
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


COLD = [hx(c) for c in ("07060e", "0e0d1b", "161729", "20233a", "2c3250", "3d4769", "56648a", "7f8fb4")]
WARM = [hx(c) for c in ("1c1016", "33191a", "552619", "83391c", "b85a22", "e58a30", "ffc15a", "fff0b0")]
MOON = [hx(c) for c in ("3a4a70", "5a6e98", "88a0c8", "c4d6f0", "eef6ff")]

BAYER = [[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]]


def dither_level(v: float, x: int, y: int, levels: int) -> int:
    """Flat colour bands with a thin ordered-dither seam between them."""
    v = max(0.0, min(levels - 1.0, v))
    base = int(v)
    frac = v - base
    if frac < 0.4:
        return base
    if frac > 0.6:
        return min(levels - 1, base + 1)
    return min(levels - 1, base + (1 if (frac - 0.4) * 5 * 16 > BAYER[y % 4][x % 4] + 0.5 else 0))


# ---------------------------------------------------------------------------
# Static layout
# ---------------------------------------------------------------------------

FLOOR_Y = 146         # where the fighters stand (y ~292 on screen)
WIN = (282, 26, 358, 114)            # window x0, y0, x1, y1 (arched top)
TORCHES = [(52, 82), (560, 82)]     # flame base positions


def in_window(x, y):
    x0, y0, x1, y1 = WIN
    cx, r = (x0 + x1) / 2, (x1 - x0) / 2
    if x0 <= x < x1 and y0 + r <= y < y1:
        return True
    return y < y0 + r and (x + 0.5 - cx) ** 2 + (y + 0.5 - (y0 + r)) ** 2 <= r * r and y >= y0


def material(x, y):
    """Albedo 0..1 and a surface id for the wall / floor."""
    if y >= FLOOR_Y:
        row = (y - FLOOR_Y)
        depth = row / (H - FLOOR_Y)  # noqa: F841
        ty = 0
        acc = 0
        while acc + (6 + int(acc / (H - FLOOR_Y) * 16)) <= row:
            acc += 6 + int(acc / (H - FLOOR_Y) * 16)
            ty += 1
        tile_w = 30 + int(depth * 40)
        off = (ty * 11) % tile_w
        seam = (row - acc) == 0 or ((x + off) % tile_w) == 0
        grain = ((x // 4 * 7 + ty * 13) % 4) * 0.025
        return (0.4 if seam else 0.7 + grain), "floor"
    bh, bw = 12, 28
    r = y // bh
    off = (r % 2) * (bw // 2)
    mortar = (y % bh == 0) or ((x + off) % bw == 0)
    chip = ((x // 3 * 31 + r * 17) % 23 == 0)
    grain = (((x + off) // bw * 37 + r * 11) % 7) * 0.035
    return (0.3 if mortar else 0.62 + grain - (0.12 if chip else 0)), "wall"


# ---------------------------------------------------------------------------
# Animated pieces
# ---------------------------------------------------------------------------

FLAMES = [
    ["..y..", ".yOy.", ".OrO.", "yOrOy", ".OrO.", "..O.."],
    [".y...", "..y..", ".yOy.", "yOrOy", ".OrO.", "..O.."],
    ["...y.", "..y..", ".yOy.", "yOrOy", ".OrrO", "..O.."],
    ["..y..", "..Oy.", ".yOy.", ".OrOy", "yOrO.", "..O.."],
]
FLAME_PAL = {"y": WARM[7], "O": WARM[6], "r": WARM[5]}


def flicker(i: int, k: int) -> float:
    t = 2 * math.pi * i / N
    return 1.0 + 0.10 * math.sin(3 * t + k) + 0.06 * math.sin(5 * t + 2 * k) + 0.04 * math.sin(11 * t + k)


def render(i: int) -> list[bytes]:
    t = i / N
    img = [[COLD[0]] * W for _ in range(H)]
    fl = [flicker(i, k) for k in range(len(TORCHES))]
    x0, y0, x1, y1 = WIN
    wcx = (x0 + x1) / 2
    for y in range(H):
        for x in range(W):
            if in_window(x, y):
                continue
            alb, kind = material(x, y)
            # cold ambient falls off toward the edges (vignette)
            vx = abs(x - W / 2) / (W / 2)
            amb = 2.6 - 1.4 * vx ** 2 - (0.8 if y < 20 else 0)
            # moonbeam: a slanted shaft from the window onto the floor
            beam = 0.0
            if y > y1 - 4:
                sx = wcx + (y - y1) * 0.55
                d = abs(x - sx)
                width = 38 + (y - y1) * 0.35
                if d < width:
                    beam = 1.6 * (1 - d / width) * (1.0 if kind == "floor" else 0.6)
            # warm torchlight
            warm = 0.0
            for (tx, ty), f in zip(TORCHES, fl):
                dd = math.hypot((x - tx) * 0.9, (y - ty) * 1.15)
                warm += f * 4.6 * max(0.0, 1 - dd / 170) ** 1.7
            lvl_cold = (amb + beam) * alb * 2.0
            lvl_warm = warm * alb * 1.3
            total = lvl_cold + lvl_warm
            ratio = lvl_warm / total if total > 0 else 0.0
            # hue follows the dominant light; the seam between them is dithered
            use_warm = ratio > 0.46 or (ratio > 0.38 and (ratio - 0.38) * 12.5 * 16 > BAYER[y % 4][x % 4])
            if use_warm:
                img[y][x] = WARM[dither_level(total * 0.78, x, y, len(WARM) - 1)]
            else:
                img[y][x] = COLD[dither_level(total + (0.5 if beam > 0.3 else 0), x, y, len(COLD) - 1)]
    # window: night sky, moon, rain, bars and stone frame
    for y in range(y0, y1):
        for x in range(x0, x1):
            if not in_window(x, y):
                continue
            g = (y - y0) / (y1 - y0)
            c = COLD[3] if g < 0.5 else COLD[2]
            if (x - 338) ** 2 + (y - 50) ** 2 <= 110:
                c = MOON[4] if (x - 336) ** 2 + (y - 48) ** 2 <= 60 else MOON[3]
            img[y][x] = c
    for k in range(46):
        rx = x0 + (k * 13 + 5) % (x1 - x0)
        ry = y0 + ((k * 29 + int(t * (y1 - y0) * 3)) % (y1 - y0))
        for j in range(7):
            px, py = rx - j // 3, ry + j
            if in_window(px, py) and in_window(px, py + 1):
                img[py][px] = MOON[1] if j < 3 else MOON[0]
    for bx in range(x0 + 12, x1, 17):
        for y in range(y0, y1):
            if in_window(bx, y):
                img[y][bx] = COLD[1]
                if in_window(bx + 1, y):
                    img[y][bx + 1] = COLD[4]
    for y in range(y0 - 6, y1 + 3):
        for x in range(x0 - 6, x1 + 6):
            if 0 <= x < W and 0 <= y < H and not in_window(x, y):
                near = any(in_window(x + dx, y + dy) for dx in (-5, 0, 5) for dy in (-5, 0, 5))
                if near:
                    img[y][x] = COLD[5] if (x + y) % 5 else COLD[4]
    for x in range(x0 - 8, x1 + 8):          # sill catching moonlight
        img[y1 + 1][x] = MOON[1]
        img[y1 + 2][x] = MOON[0]
        img[y1 + 3][x] = COLD[4]
        img[y1 + 4][x] = COLD[2]
    # torches: iron bracket, flame, glow core
    for k, (tx, ty) in enumerate(TORCHES):
        for y in range(ty, ty + 24):
            img[y][tx - 1] = COLD[1]
            img[y][tx] = WARM[2]
            img[y][tx + 1] = WARM[3]
            img[y][tx + 2] = COLD[1]
        for x in range(tx - 5, tx + 8):
            img[ty + 2][x] = WARM[2]
            img[ty + 1][x] = WARM[3]
            img[ty][x] = WARM[4]
        fr = FLAMES[(i + k * 2) % len(FLAMES)]
        for fy, row in enumerate(fr):
            for fx, ch in enumerate(row):
                if ch in FLAME_PAL:
                    for sy in (0, 1):
                        for sx in (0, 1):
                            img[ty - 2 * len(fr) + 2 * fy + sy][tx - 4 + 2 * fx + sx] = FLAME_PAL[ch]
    # embers rising from the torches (periodic over the loop)
    for k, (tx, ty) in enumerate(TORCHES):
        for e in range(10):
            ph = (t + e / 10 + k * 0.13) % 1.0
            ex = tx + math.sin(2 * math.pi * (ph * 2 + e * 0.37)) * (5 + e % 4) + (e % 3 - 1) * 2
            ey = ty - 12 - ph * 90
            c = WARM[7] if ph < 0.3 else WARM[6] if ph < 0.65 else WARM[4]
            xi, yi = round(ex), round(ey)
            if 0 <= xi < W and 0 <= yi < H:
                img[yi][xi] = c
    # dust drifting in the moonbeam
    for d in range(28):
        ph = (t + d / 28) % 1.0
        dx = wcx - 20 + (d * 23) % 80 + ph * 60 + math.sin(2 * math.pi * (t + d * 0.21)) * 2
        dy = y1 + 12 + (d * 17) % 110 + math.sin(2 * math.pi * (ph + d * 0.11)) * 5
        xi, yi = round(dx), round(dy)
        if 0 <= xi < W and 0 <= yi < H and (d + i) % 5:
            img[yi][xi] = MOON[3] if d % 3 else MOON[2]
    return [bytes(v for p in row for v in (*p, 255)) for row in img]


def write_png(path: Path, rows: list[bytes], w: int, h: int) -> None:
    raw = b"".join(b"\0" + r for r in rows)

    def chunk(tag: bytes, body: bytes) -> bytes:
        return struct.pack(">I", len(body)) + tag + body + struct.pack(">I", zlib.crc32(tag + body))

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
                     + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


def main() -> None:
    rows_n = (N + COLS - 1) // COLS
    sheet = [bytearray(COLS * W * 4) for _ in range(rows_n * H)]
    for i in range(N):
        fr = render(i)
        r, c = divmod(i, COLS)
        for y in range(H):
            sheet[r * H + y][c * W * 4:(c + 1) * W * 4] = fr[y]
    write_png(OUT / "dungeon_sheet.png", [bytes(r) for r in sheet], COLS * W, rows_n * H)
    (OUT / "dungeon_sheet.json").write_text(json.dumps(
        {"width": W, "height": H, "frames": N, "columns": COLS, "frame_ms": FRAME_MS, "scale": 2}, indent=2) + "\n",
        encoding="utf-8")
    print(f"wrote {N} frames of {W}x{H}")


if __name__ == "__main__":
    main()
