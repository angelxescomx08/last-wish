"""Animate the approved warrior art without ever deforming it.

Standard library only:

    python scripts/generate_warrior_sprites.py [--frames]

Input: ``assets/characters/warrior_base.png`` — the approved design
(warrior-source-v2.png) reduced to native pixel art by make_warrior_base.py.

Technique (the drawing is never cut into limbs, rotated or resampled):

* idle: the upper body rises one pixel on the in-breath and the head follows a
  beat later (whole pixel rows move, the classic pixel-art breath); ponytail
  and cape sway with per-row horizontal offsets that grow away from where they
  attach; one blink per loop.
* actions (attack, guard, hurt): the whole figure moves as one piece —
  anticipation, lunge, recoil — and the energy comes from pixel effects drawn
  on top: a slash crescent and sparks, a guard ward with a gleam on the blade,
  a white hit flash with red tint and sparks.

Output (``assets/characters/``):
    warrior_sheet.png     192 px cells (combat, shown at x1)
    warrior_sheet_96.png  96 px cells (selection), each frame reduced by 2
    warrior_sheet.json    sheets, rows, per-frame ms, loop flags
"""
from __future__ import annotations

import colorsys
import json
import math
import struct
import sys
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHAR_DIR = ROOT / "assets" / "characters"
BASE_PATH = CHAR_DIR / "warrior_base.png"
# Superseded at runtime by the code-drawn warrior (scripts/generate_warrior_code_sprites.py),
# so this illustrated version now writes to its own folder and never overwrites the game sheet.
LEGACY_DIR = CHAR_DIR / "warrior_illustrated"
SHEET_PATH = LEGACY_DIR / "warrior_sheet.png"
SHEET_96_PATH = LEGACY_DIR / "warrior_sheet_96.png"
META_PATH = LEGACY_DIR / "warrior_sheet.json"
FRAMES_DIR = CHAR_DIR / "warrior_frames"

CELL = 192
Px = tuple[int, int, int, int]

# ---------------------------------------------------------------------------
# PNG I/O (stdlib)
# ---------------------------------------------------------------------------


def read_png(path: Path) -> list[list[Px]]:
    data = path.read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n", "not a PNG"
    pos, idat, w = 8, b"", 0
    while pos < len(data):
        n = struct.unpack(">I", data[pos:pos + 4])[0]
        tag, body = data[pos + 4:pos + 8], data[pos + 8:pos + 8 + n]
        if tag == b"IHDR":
            w, h, depth, ctype, _, _, inter = struct.unpack(">IIBBBBB", body)
            assert depth == 8 and ctype in (2, 6) and inter == 0, "need 8-bit RGB/RGBA, not interlaced"
            bpp = 4 if ctype == 6 else 3
        elif tag == b"IDAT":
            idat += body
        pos += 12 + n
    raw = zlib.decompress(idat)
    stride = w * bpp
    rows, prev = [], bytearray(stride)
    i = 0
    for _ in range(h):
        ft = raw[i]
        cur = bytearray(raw[i + 1:i + 1 + stride])
        i += 1 + stride
        for x in range(stride):
            a = cur[x - bpp] if x >= bpp else 0
            b = prev[x]
            c = prev[x - bpp] if x >= bpp else 0
            if ft == 1:
                cur[x] = (cur[x] + a) & 255
            elif ft == 2:
                cur[x] = (cur[x] + b) & 255
            elif ft == 3:
                cur[x] = (cur[x] + (a + b) // 2) & 255
            elif ft == 4:
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                cur[x] = (cur[x] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 255
        rows.append([tuple(cur[x:x + bpp]) + ((255,) if bpp == 3 else ()) for x in range(0, stride, bpp)])
        prev = cur
    return rows


def write_png(path: Path, rows: list[bytes], w: int, h: int) -> None:
    raw = b"".join(b"\0" + r for r in rows)

    def chunk(tag: bytes, body: bytes) -> bytes:
        return struct.pack(">I", len(body)) + tag + body + struct.pack(">I", zlib.crc32(tag + body))

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
                     + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


# ---------------------------------------------------------------------------
# Base art and its regions
# ---------------------------------------------------------------------------

BASE = read_png(BASE_PATH)
BH, BW = len(BASE), len(BASE[0])


def _bbox():
    xs = [x for y in range(BH) for x in range(BW) if BASE[y][x][3]]
    ys = [y for y in range(BH) for x in range(BW) if BASE[y][x][3]]
    return min(xs), min(ys), max(xs), max(ys)


BX0, BY0, BX1, BY1 = _bbox()
# centre the figure horizontally and stand it on row 190 of the 192 cell
OX = CELL // 2 - (BX0 + BX1 + 1) // 2
OY = 190 - BY1

# Row landmarks in base coordinates (checked against the art)
HEAD_BOTTOM = 31      # rows above this move with the head
CHEST_BOTTOM = 62     # rows above this rise with the breath (below the breastplate)


def _hsv(p):
    return colorsys.rgb_to_hsv(p[0] / 255, p[1] / 255, p[2] / 255)


def _is_hair(p):
    h, s, v = _hsv(p)
    return (h < 0.045 or h > 0.93) and s > 0.55


def _is_cape(p):
    h, s, v = _hsv(p)
    return 0.47 < h < 0.66 and s > 0.35


def _region() -> dict[tuple[int, int], float]:
    """Pixels that sway, with a 0..1 weight growing away from the attachment."""
    reg: dict[tuple[int, int], float] = {}
    for y in range(BH):
        for x in range(BW):
            p = BASE[y][x]
            if not p[3]:
                continue
            if _is_hair(p) and x < 60 and 16 <= y < 80:
                wy = min(1.0, max(0.0, (y - 20) / 40))
                wx = min(1.0, max(0.0, (60 - x) / 28))
                reg[(x, y)] = wy * (0.4 + 0.6 * wx)
            elif _is_cape(p) and x < 46 and 40 <= y < 110:
                wy = min(1.0, max(0.0, (y - 44) / 50))
                wx = min(1.0, max(0.0, (46 - x) / 24))
                reg[(x, y)] = wy * (0.3 + 0.7 * wx)
    # dark outline pixels bordering the swaying area travel with it
    for (x, y), w in list(reg.items()):
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            q = (x + dx, y + dy)
            if 0 <= q[0] < BW and 0 <= q[1] < BH and q not in reg:
                p = BASE[q[1]][q[0]]
                if p[3] and _hsv(p)[2] < 0.3 and q[0] < 60:
                    reg[q] = w
    return reg


SWAY = _region()


def _blade() -> list[tuple[int, int]]:
    """Bright, unsaturated pixels of the sword blade ordered from hilt to tip."""
    pts = []
    for y in range(80, 150):
        for x in range(45, 110):
            p = BASE[y][x]
            h, s, v = _hsv(p)
            if p[3] and s < 0.18 and v > 0.62 and (x - 50) * 0.6 - (y - 88) * 0.9 > -12:
                pts.append((x, y))
    pts.sort(key=lambda q: q[0] + q[1])
    return pts


BLADE = _blade()

# Blink: near eye (x 69..74, y 22..24) and far eye (x 78..80, y 23..24)
SKIN = (255, 196, 165, 255)
LASH = (0, 0, 0, 255)


def _blink_edits():
    e = {}
    for y in (22, 23, 24):
        for x in range(69, 75):
            if BASE[y][x][3]:
                e[(x, y)] = SKIN
    for x in range(69, 75):
        e[(x, 23)] = LASH
    for (x, y) in ((78, 24), (79, 24)):
        e[(x, y)] = SKIN
    return e


BLINK = _blink_edits()

# ---------------------------------------------------------------------------
# Frame rendering
# ---------------------------------------------------------------------------

Frame = dict  # (x, y) -> Px in cell coordinates


def body_frame(*, chest: int = 0, head: int = 0, phase: float = 0.0, amp: float = 1.0,
               bias: float = 0.0, blink: bool = False) -> Frame:
    """The figure in base coordinates, breathing and swaying; never deformed."""
    out: Frame = {}
    for y in range(BH):
        # rows above the chest line move up by `chest`; rows above the neck by `head`
        up = head if y < HEAD_BOTTOM else chest if y < CHEST_BOTTOM else 0
        sy = min(BH - 1, y + up)
        for x in range(BW):
            out[(x, y)] = BASE[sy][x]
    # sway pass: pull each pixel from its offset source when that source sways
    swayed: Frame = {}
    for y in range(BH):
        up = head if y < HEAD_BOTTOM else chest if y < CHEST_BOTTOM else 0
        sy = min(BH - 1, y + up)
        wave = math.sin(phase - sy * 0.16)
        for x in range(BW):
            best = None
            for off in (-2, -1, 0, 1, 2):
                q = (x - off, sy)
                w = SWAY.get(q)
                if w is None:
                    continue
                want = round(amp * w * wave + bias * w)
                if want == off:
                    best = BASE[sy][x - off]
                    break
            if best is not None:
                swayed[(x, y)] = best
            elif (x, sy) in SWAY:
                # this pixel's own content moved away: reveal transparency on the
                # open side, keep the pixel where the body is behind it
                w = SWAY[(x, sy)]
                own = round(amp * w * wave + bias * w)
                src_x = x - own
                behind = BASE[sy][src_x] if 0 <= src_x < BW else (0, 0, 0, 0)
                swayed[(x, y)] = (0, 0, 0, 0) if behind[3] == 0 else BASE[sy][x]
    out.update(swayed)
    if blink:
        for (x, y), p in BLINK.items():
            yy = y - head
            out[(x, yy)] = p
    return {k: v for k, v in out.items() if v[3]}


def place(body: Frame, dx: int = 0, dy: int = 0) -> Frame:
    return {(x + OX + dx, y + OY + dy): p for (x, y), p in body.items()
            if 0 <= x + OX + dx < CELL and 0 <= y + OY + dy < CELL}


def tint(f: Frame, color, amount: float) -> Frame:
    return {k: tuple(round(v + (c - v) * amount) for v, c in zip(p[:3], color)) + (255,) for k, p in f.items()}


# ---- effects ---------------------------------------------------------------

WHITE = (255, 255, 255, 255)
PALE = (214, 236, 255, 255)
ICE = (140, 190, 235, 255)
DEEP = (70, 110, 170, 255)
EMBER = (255, 190, 90, 255)
EMBER2 = (255, 120, 60, 255)
WARD = (120, 230, 220, 255)
WARD2 = (60, 160, 170, 255)


def put(f: Frame, x, y, c) -> None:
    x, y = round(x), round(y)
    if 0 <= x < CELL and 0 <= y < CELL:
        f[(x, y)] = c


def slash(f: Frame, cx, cy, r: float, a0: float, a1: float, width: float, fade: int = 0) -> None:
    """Pixel crescent: widest in the middle, white core, blue edge."""
    steps = 90
    for i in range(steps + 1):
        t = i / steps
        a = a0 + (a1 - a0) * t
        wdt = width * math.sin(math.pi * t) ** 0.8
        k = 0.0
        while k <= wdt:
            rr = r - k
            col = WHITE if k < wdt * 0.45 else PALE if k < wdt * 0.75 else ICE
            if fade and (i // 3) % (fade + 1):
                col = ICE if col is WHITE else DEEP
            put(f, cx + math.cos(a) * rr, cy + math.sin(a) * rr, col)
            k += 0.5
        put(f, cx + math.cos(a) * (r + 1), cy + math.sin(a) * (r + 1), DEEP if fade else ICE)


def sparks(f: Frame, cx, cy, n: int, spread: float, seed: int, colors=(WHITE, EMBER, EMBER2)) -> None:
    for i in range(n):
        a = (seed * 1.7 + i * 2.39996) % (2 * math.pi)
        d = spread * (0.45 + 0.55 * ((i * 7919 + seed * 104729) % 97) / 97)
        x, y = cx + math.cos(a) * d, cy + math.sin(a) * d
        c = colors[i % len(colors)]
        put(f, x, y, c)
        put(f, x - math.cos(a), y - math.sin(a), c if i % 2 else colors[-1])


def ward(f: Frame, cx, cy, r: float, level: float) -> None:
    """Guard ward: a pixel hexagon outline with bright vertices."""
    pts = [(cx + math.cos(math.pi / 6 + k * math.pi / 3) * r * 0.62, cy + math.sin(math.pi / 6 + k * math.pi / 3) * r)
           for k in range(6)]
    for k in range(6):
        (x0, y0), (x1, y1) = pts[k], pts[(k + 1) % 6]
        n = int(max(abs(x1 - x0), abs(y1 - y0))) + 1
        for i in range(n + 1):
            t = i / n
            if level < 1 and (i % 3 == 0):
                continue
            put(f, x0 + (x1 - x0) * t, y0 + (y1 - y0) * t, WARD if level >= 0.5 else WARD2)
    for (x, y) in pts:
        put(f, x, y, WHITE)
        put(f, x + 1, y, WARD)


def gleam(f: Frame, t: float, dx: int, dy: int, head: int = 0) -> None:
    if not BLADE:
        return
    x, y = BLADE[min(len(BLADE) - 1, int(t * (len(BLADE) - 1)))]
    x, y = x + OX + dx, y + OY + dy
    for ddx, ddy, c in ((0, 0, WHITE), (1, 0, WHITE), (-1, 0, PALE), (0, -1, WHITE), (0, 1, PALE),
                        (0, -2, PALE), (0, 2, ICE), (2, 0, PALE), (-2, 0, ICE), (0, -3, ICE), (0, 3, ICE)):
        put(f, x + ddx, y + ddy, c)


# ---------------------------------------------------------------------------
# Animations
# ---------------------------------------------------------------------------

TAU = 2 * math.pi
IDLE_N = 16
CHEST = [0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0]
HEAD = [0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 0, 0, 0]   # head settles a beat later


def idle():
    frames = []
    for i in range(IDLE_N):
        body = body_frame(chest=CHEST[i], head=HEAD[i], phase=TAU * i / IDLE_N, amp=1.6, blink=(i == 14))
        frames.append(place(body))
    return frames, [100] * IDLE_N, True


def idle0():
    return place(body_frame(phase=0.0, amp=1.6))


def attack():
    ph = [0.0, 0.5, 1.2, 1.9, 2.6, 3.3, 4.0]
    moves = [(-3, 0, 1.5), (-6, 1, 2.0), (6, 0, -2.2), (12, 0, -2.4), (12, 0, -1.8), (8, 0, -1.0), (4, 0, -0.4)]
    frames = []
    for i, (dx, dy, bias) in enumerate(moves):
        f = place(body_frame(phase=ph[i], amp=1.2, bias=bias, chest=1 if i in (0, 1) else 0), dx, dy)
        cx, cy = 118 + dx, 96
        if i == 2:
            slash(f, cx, cy, 38, -1.25, -0.2, 4)
        elif i == 3:
            slash(f, cx, cy, 40, -1.35, 1.05, 7)
            sparks(f, cx + 40, cy + 6, 10, 12, seed=3)
        elif i == 4:
            slash(f, cx, cy, 41, -1.2, 1.0, 5, fade=1)
            sparks(f, cx + 42, cy + 8, 8, 18, seed=5)
        elif i == 5:
            sparks(f, cx + 40, cy + 12, 5, 24, seed=9, colors=(EMBER2, DEEP))
        frames.append(f)
    frames.append(idle0())
    return frames, [70, 90, 45, 70, 90, 70, 70, 80], False


def guard():
    frames = []
    steps = [(-2, 0.4, None), (-3, 1.0, 0.1), (-3, 1.0, 0.45), (-3, 1.0, 0.8), (-3, 0.5, None), (-1, 0.0, None)]
    for i, (dx, level, g) in enumerate(steps):
        f = place(body_frame(phase=0.6 * i, amp=1.2, bias=0.8 if i < 4 else 0.3, chest=1 if 0 < i < 4 else 0), dx)
        if level > 0:
            ward(f, 150 + dx, 92, 40 if level >= 1 else 30, level)
        if g is not None:
            gleam(f, g, dx, 0)
        if 0 < i < 4:
            sparks(f, 150 + dx, 92, 4, 30, seed=11 + i, colors=(WARD, WHITE))
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
            sparks(f, 104 + dx, 70, 9 if i == 0 else 6, 10 + i * 8, seed=21 + i, colors=(WHITE, EMBER2, EMBER))
        frames.append(f)
    frames.append(idle0())
    return frames, [70, 110, 110, 100, 90], False


ANIMATIONS = {"idle": idle, "attack": attack, "guard": guard, "hurt": hurt}


# ---------------------------------------------------------------------------
# Sheets
# ---------------------------------------------------------------------------


def halve(f: Frame) -> Frame:
    """2x reduction for the 96 px sheet: each 2x2 block keeps its dominant pixel,
    dark outline pixels win ties so silhouettes stay closed."""
    blocks: dict[tuple[int, int], list[Px]] = {}
    for (x, y), p in f.items():
        blocks.setdefault((x // 2, y // 2), []).append(p)
    out: Frame = {}
    for k, ps in blocks.items():
        if len(ps) < 2:
            continue
        counts: dict[Px, int] = {}
        for p in ps:
            counts[p] = counts.get(p, 0) + 1
        dark = [p for p in ps if sum(p[:3]) < 110]
        if len(dark) >= 3:
            out[k] = max(dark, key=lambda p: counts[p])
        else:
            out[k] = max(counts, key=lambda p: (counts[p], sum(p[:3])))
    return out


def rows_of(f: Frame, size: int) -> list[bytes]:
    rows = []
    for y in range(size):
        r = bytearray()
        for x in range(size):
            p = f.get((x, y))
            r += bytes(p) if p else b"\0\0\0\0"
        rows.append(bytes(r))
    return rows


def write_sheet(path: Path, frames: dict[str, list[Frame]], size: int, cols: int) -> None:
    sheet = [bytearray(cols * size * 4) for _ in range(len(frames) * size)]
    for r, cells in enumerate(frames.values()):
        for c, f in enumerate(cells):
            for y, row in enumerate(rows_of(f, size)):
                sheet[r * size + y][c * size * 4:(c + 1) * size * 4] = row
    write_png(path, [bytes(r) for r in sheet], cols * size, len(frames) * size)


def main() -> None:
    frames: dict[str, list[Frame]] = {}
    meta: dict[str, dict] = {}
    for row, (name, fn) in enumerate(ANIMATIONS.items()):
        cells, ms, loop = fn()
        frames[name] = cells
        meta[name] = {"row": row, "frames": len(cells), "durations_ms": ms, "loop": loop}
    cols = max(len(v) for v in frames.values())
    write_sheet(SHEET_PATH, frames, CELL, cols)
    small = {k: [halve(f) for f in v] for k, v in frames.items()}
    write_sheet(SHEET_96_PATH, small, CELL // 2, cols)
    if "--frames" in sys.argv:
        for name, cells in frames.items():
            for i, f in enumerate(cells):
                write_png(FRAMES_DIR / f"{name}_{i:02d}.png", rows_of(f, CELL), CELL, CELL)
    META_PATH.write_text(json.dumps({
        "cell": CELL, "columns": cols,
        "sheets": {str(CELL): SHEET_PATH.name, str(CELL // 2): SHEET_96_PATH.name},
        "animations": meta}, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {SHEET_PATH.name} ({cols}x{len(frames)} x {CELL}px), {SHEET_96_PATH.name} and {META_PATH.name}")


if __name__ == "__main__":
    main()
