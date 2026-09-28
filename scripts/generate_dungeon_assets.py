"""Pixel-art dungeon asset pack + pre-lit combat room (standard library only).

    python scripts/generate_dungeon_assets.py

Everything is authored at a native pixel size and shown at x2 in game
(the 640 x 360 room fills the 1280 x 720 virtual canvas).

Performance technique — *baked lighting*: the room's cold moonlight, torch
light and vignette are computed here, once, into ``room_combat.png``. At run
time the game only blits that picture and draws the few things that move
(flames, a flicker glow, particles), so the backdrop costs almost no CPU.

Output (``assets/dungeon/``):
    room_combat.png     640 x 360 pre-lit room (walls, floor, window, brackets, banners)
    tiles.png           reusable blocks, lit neutrally: 4 wall variants (32 x 24),
                        4 floor variants (32 x 16) and a ledge strip (32 x 6)
    props.png           window, torch bracket, banner, chain (unlit reference colours)
    flame.png           6 flame frames, 14 x 22 each, left to right
    glow.png            3 additive flicker-glow frames, 96 x 96 each
    dungeon.json        sizes, frame timings and the room's anchor points
                        (torches, window interior, sill, moonbeam, drips)
To make another room, add a layout to ROOMS and bake it the same way.
"""
from __future__ import annotations

import json
import math
import struct
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "dungeon"


def hx(h: str):
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


# ---------------------------------------------------------------------------
# Palette (strong warm / cold contrast)
# ---------------------------------------------------------------------------

COLD = [hx(c) for c in ("07060e", "0e0d1b", "161729", "20233a", "2c3250", "3d4769", "56648a", "7f8fb4")]
WARM = [hx(c) for c in ("1c1016", "33191a", "552619", "83391c", "b85a22", "e58a30", "ffc15a", "fff0b0")]
MOSS_C = [hx(c) for c in ("0a120f", "112019", "1a3024", "25432f", "335a3c")]
MOSS_W = [hx(c) for c in ("1c1a0e", "383214", "5a4c1a", "85701e", "b09428")]
MOON = [hx(c) for c in ("3a4a70", "5a6e98", "88a0c8", "c4d6f0", "eef6ff")]
OUTLINE = hx("0a0810")

BAYER = [[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]]


def band(v: float, x: int, y: int, levels: int) -> int:
    """Flat colour bands with a thin ordered-dither seam between them."""
    v = max(0.0, min(levels - 1.0, v))
    base = int(v)
    frac = v - base
    if frac < 0.4:
        return base
    if frac > 0.6:
        return min(levels - 1, base + 1)
    return min(levels - 1, base + (1 if (frac - 0.4) * 80 > BAYER[y % 4][x % 4] + 0.5 else 0))


def _hash(*v: int) -> int:
    h = 2166136261
    for k in v:
        h = ((h ^ (k & 0xFFFFFFFF)) * 16777619) & 0xFFFFFFFF
    return h


# ---------------------------------------------------------------------------
# Tiles as albedo maps: (value 0..1, material)
# ---------------------------------------------------------------------------

WALL_W, WALL_H = 32, 24
FLOOR_W, FLOOR_H = 32, 16
LEDGE_H = 6


def wall_tile(variant: int):
    """Seamless 32 x 24 brick block: two courses of 11 px bricks, 1 px mortar.
    variant 0 plain, 1 cracked, 2 mossy, 3 worn/chipped."""
    g = [[(0.3, "mortar")] * WALL_W for _ in range(WALL_H)]
    for course in (0, 1):
        y0 = course * 12
        joints = (31,) if course == 0 else (15,)
        for y in range(y0, y0 + 11):
            for x in range(WALL_W):
                if x in joints:
                    continue
                # brick index for per-brick tone
                bi = 0 if course == 0 else (0 if x < 15 else 1)
                bx0 = 0 if course == 0 else (0 if x < 15 else 16)
                bx1 = 30 if course == 0 else (14 if x < 15 else 31)
                tone = 0.62 + (_hash(variant, course, bi) % 5) * 0.03
                v = tone
                if y == y0 or x == bx0:
                    v += 0.14                      # upper-left bevel catches light
                if y == y0 + 10 or x == bx1:
                    v -= 0.14                      # lower-right bevel in shadow
                if _hash(x, y, variant, 7) % 23 == 0:
                    v -= 0.1                       # pitting
                g[y][x] = (v, "stone")
    if variant == 1:        # crack running across the upper brick
        pts = [(6, 2), (8, 4), (9, 6), (12, 7), (13, 9), (16, 10)]
        for x, y in pts:
            g[y][x] = (0.22, "mortar")
            g[y][x + 1] = (0.45, "stone")
    if variant == 2:        # moss creeping along the mortar lines
        for x in range(WALL_W):
            for y in (10, 11, 12, 22, 23):
                if _hash(x, y, 3) % 3 == 0:
                    g[y][x] = (0.55 + (_hash(x, y) % 3) * 0.1, "moss")
    if variant == 3:        # chipped corner and worn face
        for y in range(12, 16):
            for x in range(16, 21 - (y - 12)):
                g[y][x] = (0.28, "mortar")
        for x in range(2, 12):
            g[5][x] = (g[5][x][0] - 0.08, "stone")
    return g


def floor_tile(variant: int):
    """Seamless 32 x 16 flagstone course."""
    g = [[(0.28, "mortar")] * FLOOR_W for _ in range(FLOOR_H)]
    split = (14, 20, 9, 24)[variant % 4]
    for y in range(0, 15):
        for x in range(FLOOR_W):
            if x in (split, 31):
                continue
            left = x < split
            tone = 0.6 + (_hash(variant, 1 if left else 2) % 4) * 0.035
            v = tone
            if y == 0:
                v += 0.16
            if y == 14:
                v -= 0.12
            if x == (0 if left else split + 1):
                v += 0.06
            if _hash(x, y, variant, 11) % 19 == 0:
                v -= 0.09
            g[y][x] = (v, "stone")
    return g


def ledge_strip():
    g = []
    for y in range(LEDGE_H):
        row = []
        for x in range(WALL_W):
            v = (0.9, 0.78, 0.66, 0.55, 0.42, 0.3)[y]
            if x % 16 == 15 and y > 0:
                v = 0.25
            row.append((v, "stone"))
        g.append(row)
    return g


# ---------------------------------------------------------------------------
# Props in reference colours (lit by the baker)
# ---------------------------------------------------------------------------

def P(s):
    return hx(s)


PROP_PAL = {
    "X": OUTLINE, "J": P("474a5e"), "j": P("7c8098"), "i": P("a8adc2"),
    "l": P("7a4a2a"), "L": P("4c2c18"),
    "t": P("1f6571"), "T": P("144650"), "s": P("2c8488"),
    "Y": P("e8c060"), "O": P("a8701e"),
    "S": P("6a7090"), "s2": P("8a90b0"),
}

TORCH_BRACKET = [
    "XXjjjjXX",
    "XJjiijJX",
    ".XJJJJX.",
    "..XllX..",
    "..XlLX..",
    "..XlLX..",
    ".XJjJJX.",
    "..XlLX..",
    "..XlLX..",
    "..XlLX..",
    "XXXlLXXX",
    "XJJjJJJX",
    "XJjJJJJX",
    "XXXXXXXX",
]

FLAMES = [
    ["...d...", "...r...", "..rod..", "..oor..", ".royor.", ".oyyyo.", "royywyr", "oyywwyo", ".oywwo.", "..oyo..", "...o..."],
    ["..d....", "..r....", ".ror...", ".ooy...", ".oyyo..", "royyyo.", "oyywyor", "oyywwyo", ".oywwo.", "..oyo..", "...o..."],
    ["....d..", "...r...", "...or..", "..ooy..", "..oyyr.", ".oyyyo.", "royywyo", "oyywwyo", ".oywwo.", "..oyo..", "...o..."],
    ["....d..", "....r..", "...rod.", "...yoo.", "..oyyo.", ".oyyyor", "royywyo", "oyywwyo", ".oywwo.", "..oyo..", "...o..."],
    [".......", "..d.d..", "..r.r..", ".rorord", ".oyyyo.", "royyyor", "oyywwyo", "oyywwyo", ".oywwo.", "..oyo..", "...o..."],
    ["..d....", ".......", "...r...", "..ror..", ".royo..", ".oyyyo.", "royywyr", "oyywwyo", ".oywwo.", "..oyo..", "...o..."],
]
FLAME_PAL = {"w": WARM[7], "y": WARM[6], "o": WARM[5], "r": WARM[4], "d": WARM[3]}
FLAME_W, FLAME_H = 14, 22            # native pixels (art drawn in 2 x 2 blocks)
FLAME_MS = [90, 80, 100, 80, 90, 100]


def banner_sprite():
    """Teal war banner with gold trim and a sword crest (20 x 46)."""
    w, h = 20, 46
    g = [[None] * w for _ in range(h)]
    for x in range(w):                      # gold rod
        g[0][x] = "O" if x in (0, w - 1) else "Y"
        g[1][x] = "O"
    for y in range(2, h):
        for x in range(1, w - 1):
            tail = y - (h - 8)
            if tail > 0 and abs(x - (w - 1) / 2) < tail * 1.2:
                continue                    # swallow-tail cut
            edge = x in (1, w - 2) or y == h - 1
            g[y][x] = "X" if edge else ("Y" if x in (2, w - 3) else "t")
    for y in range(4, h - 8):               # folds
        for x in (6, 13):
            if g[y][x] == "t":
                g[y][x] = "T"
        if g[y][9] == "t":
            g[y][9] = "s"
    for y in range(12, 30):                 # sword crest
        g[y][9] = "Y"
        g[y][10] = "O" if y > 14 else "Y"
    for x in range(6, 14):
        g[15][x] = "Y"
    g[11][9] = g[11][10] = "Y"
    for y in range(h - 8, h):               # re-outline the cut
        for x in range(1, w - 1):
            if g[y][x] and g[y][x] != "X":
                nb = [g[y + dy][x + dx] if 0 <= y + dy < h and 0 <= x + dx < w else None
                      for dx, dy in ((1, 0), (-1, 0), (0, 1))]
                if None in nb:
                    g[y][x] = "X"
    return g


def chain_sprite(length: int = 30):
    g = []
    for y in range(length):
        k = y % 4
        g.append([None, "X", None] if k == 3 else (["X", "j", "X"] if k in (0, 2) else ["X", None, "X"]))
    return g


# window: stone arch frame with night sky, moon and iron bars
WIN_W, WIN_H = 56, 88
WIN_FRAME = 6


def window_sprite():
    w, h = WIN_W, WIN_H
    cx, r = w / 2, w / 2
    g = [[None] * w for _ in range(h)]

    def inside(x, y, shrink):
        rr = r - shrink
        if y >= r and shrink <= x < w - shrink and y < h - shrink // 2:
            return True
        return (x + 0.5 - cx) ** 2 + (y + 0.5 - r) ** 2 <= rr * rr and y < r + 1

    for y in range(h):
        for x in range(w):
            if inside(x, y, WIN_FRAME):
                g[y][x] = ("sky", y / h)
            elif inside(x, y, 0):
                stone = ((x // 7) + (y // 6)) % 2
                edge = not inside(x, y, 1) or inside(x, y, WIN_FRAME - 1)
                g[y][x] = ("frame", 0.35 if edge else (0.7 if stone else 0.58))
    return g


WINDOW_INTERIOR = (WIN_FRAME, WIN_FRAME, WIN_W - WIN_FRAME, WIN_H - WIN_FRAME // 2)  # x0, y0, x1, y1 (local)
MOON_AT = (38, 20)

# ---------------------------------------------------------------------------
# Room layouts
# ---------------------------------------------------------------------------

ROOMS = {
    "combat": {
        "size": (640, 360),
        "floor_y": 146,
        "window": (292, 18),
        "torches": [(56, 76), (576, 76)],       # bracket top-left; flame sits on its cup
        "banners": [(214, 14), (406, 14)],
        "chains": [(150, 0, 34), (156, 0, 22), (486, 0, 28)],
        "drips": [(176, 2), (468, 2)],
        "moon_strength": 1.6,
        "torch_radius": 170,
    }
}


# ---------------------------------------------------------------------------
# Lighting
# ---------------------------------------------------------------------------

class Lighting:
    def __init__(self, room):
        self.room = room
        self.w, self.h = room["size"]
        wx, wy = room["window"]
        self.beam_top = wy + WIN_H - 2
        self.beam_cx = wx + WIN_W / 2
        self.torches = [(x + 4, y) for x, y in room["torches"]]

    def at(self, x, y, kind="wall"):
        vx = abs(x - self.w / 2) / (self.w / 2)
        amb = 2.6 - 1.4 * vx ** 2 - (0.8 if y < 20 else 0) - (0.6 if y > self.h - 40 else 0)
        beam = 0.0
        if y > self.beam_top - 4:
            sx = self.beam_cx + (y - self.beam_top) * 0.55
            d = abs(x - sx)
            width = 38 + (y - self.beam_top) * 0.35
            if d < width:
                beam = self.room["moon_strength"] * (1 - d / width) * (1.0 if kind == "floor" else 0.6)
        warm = 0.0
        for tx, ty in self.torches:
            dd = math.hypot((x - tx) * 0.9, (y - ty) * 1.15)
            warm += 4.6 * max(0.0, 1 - dd / self.room["torch_radius"]) ** 1.7
        return amb, beam, warm

    def color(self, x, y, value, material, kind="wall"):
        amb, beam, warm = self.at(x, y, kind)
        lvl_cold = (amb + beam) * value * 2.0
        lvl_warm = warm * value * 1.3
        total = lvl_cold + lvl_warm
        ratio = lvl_warm / total if total > 0 else 0.0
        use_warm = ratio > 0.46 or (ratio > 0.38 and (ratio - 0.38) * 200 > BAYER[y % 4][x % 4])
        if material == "moss":
            ramp = MOSS_W if use_warm else MOSS_C
            return ramp[band(total * 0.55, x, y, len(ramp))]
        if use_warm:
            return WARM[band(total * 0.78, x, y, len(WARM) - 1)]
        return COLD[band(total + (0.5 if beam > 0.3 else 0), x, y, len(COLD) - 1)]

    def tint(self, x, y, rgb, base=0.55):
        """Light a reference colour: darken with distance from light, warm near torches."""
        amb, beam, warm = self.at(x, y)
        f = max(0.35, min(1.15, base + 0.12 * (amb + beam) + 0.18 * warm))
        r, g, b = (c * f for c in rgb)
        k = min(0.45, warm * 0.12)
        r, g, b = r + (255 - r) * k * 0.6, g + (150 - g) * k * 0.4, b * (1 - k * 0.6)
        return tuple(max(0, min(255, round(v))) for v in (r, g, b))


# ---------------------------------------------------------------------------
# Baking
# ---------------------------------------------------------------------------

def bake_room(name: str):
    room = ROOMS[name]
    w, h = room["size"]
    L = Lighting(room)
    img = [[COLD[0]] * w for _ in range(h)]
    walls = [wall_tile(v) for v in range(4)]
    floors = [floor_tile(v) for v in range(4)]
    ledge = ledge_strip()
    fy = room["floor_y"]
    for y in range(fy):
        for x in range(w):
            tx, ty = x // WALL_W, y // WALL_H
            v = _hash(tx, ty, 99) % 10
            variant = 0 if v < 5 else 1 if v < 7 else 2 if (ty >= 3 and v < 9) else 3
            val, mat = walls[variant][y % WALL_H][x % WALL_W]
            img[y][x] = L.color(x, y, val, mat)
    for y in range(fy, min(h, fy + LEDGE_H)):
        for x in range(w):
            val, mat = ledge[y - fy][x % WALL_W]
            img[y][x] = L.color(x, y, val, mat, "floor")
    for y in range(fy + LEDGE_H, h):
        row = (y - fy - LEDGE_H) // FLOOR_H
        for x in range(w):
            off = (row * 13) % FLOOR_W
            variant = _hash((x + off) // FLOOR_W, row, 5) % 4
            val, mat = floors[variant][(y - fy - LEDGE_H) % FLOOR_H][(x + off) % FLOOR_W]
            img[y][x] = L.color(x, y, val, mat, "floor")
    # window (sky is not relit: it is outside)
    wx, wy = room["window"]
    win = window_sprite()
    for y, row in enumerate(win):
        for x, cell in enumerate(row):
            if cell is None:
                continue
            X, Y = wx + x, wy + y
            if cell[0] == "sky":
                img[Y][X] = COLD[3] if cell[1] < 0.45 else COLD[2]
                mx, my = MOON_AT
                d2 = (x - mx) ** 2 + (y - my) ** 2
                if d2 <= 36:
                    img[Y][X] = MOON[4] if (x - mx + 1) ** 2 + (y - my + 1) ** 2 <= 14 else MOON[3]
                elif d2 <= 64 and (x + y) % 2 == 0:
                    img[Y][X] = COLD[4]
            else:
                img[Y][X] = L.color(X, Y, cell[1], "stone")
    x0, y0, x1, y1 = WINDOW_INTERIOR
    for bx in range(x0 + 9, x1 - 2, 11):                       # iron bars
        for y in range(y0, y1):
            if win[y][bx] and win[y][bx][0] == "sky":
                img[wy + y][wx + bx] = COLD[1]
                img[wy + y][wx + bx + 1] = COLD[4]
    for x in range(x0, x1):                                   # cross bar
        if win[y0 + 34][x] and win[y0 + 34][x][0] == "sky":
            img[wy + y0 + 34][wx + x] = COLD[1]
            img[wy + y0 + 35][wx + x] = COLD[4]
    sill_y = wy + WIN_H
    for x in range(wx - 6, wx + WIN_W + 6):                   # sill catching moonlight
        img[sill_y][x] = MOON[1]
        img[sill_y + 1][x] = MOON[0]
        img[sill_y + 2][x] = COLD[4]
        img[sill_y + 3][x] = COLD[2]
    # props lit in place
    def put_sprite(grid, ox, oy, base=0.55):
        for y, row in enumerate(grid):
            for x, ch in enumerate(row):
                if ch and ch != ".":
                    col = PROP_PAL[ch] if isinstance(ch, str) else ch
                    img[oy + y][ox + x] = L.tint(ox + x, oy + y, col, base)

    for (bx, by) in room["banners"]:
        put_sprite(banner_sprite(), bx, by)
    for (cx, cy, n) in room["chains"]:
        put_sprite(chain_sprite(n), cx, cy, 0.5)
    for (tx, ty) in room["torches"]:
        put_sprite([list(r) for r in TORCH_BRACKET], tx, ty, 0.7)
    return img, room


# ---------------------------------------------------------------------------
# Exports
# ---------------------------------------------------------------------------

def neutral_tile_rgba(grid):
    rows = []
    for y, row in enumerate(grid):
        out = bytearray()
        for x, (v, mat) in enumerate(row):
            ramp = MOSS_C if mat == "moss" else COLD
            c = ramp[band(v * (len(ramp) - 1) * 1.05, x, y, len(ramp))]
            out += bytes((*c, 255))
        rows.append(bytes(out))
    return rows


def flame_frames():
    frames = []
    for art in FLAMES:
        rows = []
        for y in range(FLAME_H):
            out = bytearray()
            for x in range(FLAME_W):
                ch = art[y // 2][x // 2]
                out += bytes((*FLAME_PAL[ch], 255)) if ch in FLAME_PAL else b"\0\0\0\0"
            rows.append(bytes(out))
        frames.append(rows)
    return frames


GLOW = 96


def glow_frames():
    """Additive warm glow at three flicker intensities (black = no light)."""
    frames = []
    for level in (0.55, 0.8, 1.0):
        rows = []
        for y in range(GLOW):
            out = bytearray()
            for x in range(GLOW):
                d = math.hypot(x + 0.5 - GLOW / 2, y + 0.5 - GLOW / 2) / (GLOW / 2)
                v = level * max(0.0, 1 - d) ** 1.6 * 4
                k = band(v, x, y, 5)
                col = ((0, 0, 0), (22, 10, 2), (42, 20, 4), (66, 32, 8), (96, 48, 12))[k]
                out += bytes((*col, 255))
            rows.append(bytes(out))
        frames.append(rows)
    return frames


def hstack(frames):
    return [b"".join(f[y] for f in frames) for y in range(len(frames[0]))]


def sprite_rows(grid, w, h):
    rows = []
    for y in range(h):
        out = bytearray()
        for x in range(w):
            ch = grid[y][x] if y < len(grid) and x < len(grid[y]) else None
            if ch and ch != "." and (ch in PROP_PAL):
                out += bytes((*PROP_PAL[ch], 255))
            else:
                out += b"\0\0\0\0"
        rows.append(bytes(out))
    return rows


def write_png(path: Path, rows: list[bytes], w: int, h: int) -> None:
    raw = b"".join(b"\0" + r for r in rows)

    def chunk(tag: bytes, body: bytes) -> bytes:
        return struct.pack(">I", len(body)) + tag + body + struct.pack(">I", zlib.crc32(tag + body))

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
                     + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


def main() -> None:
    img, room = bake_room("combat")
    w, h = room["size"]
    write_png(OUT / "room_combat.png", [bytes(v for p in row for v in (*p, 255)) for row in img], w, h)

    tiles = [neutral_tile_rgba(wall_tile(v)) for v in range(4)]
    floors = [neutral_tile_rgba(floor_tile(v)) for v in range(4)]
    blank = bytes(4 * WALL_W)
    sheet = hstack(tiles) + [b"".join(r) + bytes(0) for r in zip(*[f for f in floors])] \
        + [b"".join([r] + [blank] * 3) for r in neutral_tile_rgba(ledge_strip())]
    write_png(OUT / "tiles.png", sheet, WALL_W * 4, WALL_H + FLOOR_H + LEDGE_H)

    props = [sprite_rows([list(r) for r in TORCH_BRACKET], 8, 46), sprite_rows(banner_sprite(), 20, 46),
             sprite_rows(chain_sprite(46), 3, 46)]
    write_png(OUT / "props.png", hstack(props), 8 + 20 + 3, 46)

    write_png(OUT / "flame.png", hstack(flame_frames()), FLAME_W * len(FLAMES), FLAME_H)
    write_png(OUT / "glow.png", hstack(glow_frames()), GLOW * 3, GLOW)

    wx, wy = room["window"]
    x0, y0, x1, y1 = WINDOW_INTERIOR
    meta = {
        "scale": 2,
        "room": {
            "image": "room_combat.png", "size": [w, h], "floor_y": room["floor_y"],
            "torches": [[tx + 4, ty] for tx, ty in room["torches"]],      # flame base (centre of the cup)
            "window_interior": [wx + x0, wy + y0, wx + x1, wy + y1],
            "sill_y": wy + WIN_H,
            "moonbeam": {"top": [wx + WIN_W // 2, wy + WIN_H], "slope": 0.55, "width": 38},
            "drips": [list(d) for d in room["drips"]],
        },
        "flame": {"image": "flame.png", "size": [FLAME_W, FLAME_H], "frames": len(FLAMES), "durations_ms": FLAME_MS},
        "glow": {"image": "glow.png", "size": GLOW, "frames": 3},
        "tiles": {"image": "tiles.png", "wall": [WALL_W, WALL_H, 4], "floor": [FLOOR_W, FLOOR_H, 4],
                  "ledge": [WALL_W, LEDGE_H]},
        "props": {"image": "props.png", "torch_bracket": [0, 0, 8, 14], "banner": [8, 0, 20, 46],
                  "chain": [28, 0, 3, 46]},
        "palette": {
            "rain": [list(MOON[3]), list(MOON[2]), list(MOON[1])],
            "splash": [list(MOON[4]), list(MOON[2])],
            "ember": [list(WARM[7]), list(WARM[6]), list(WARM[5]), list(WARM[3])],
            "dust": [list(MOON[3]), list(MOON[1])],
            "drip": [list(MOON[2]), list(MOON[1])],
        },
    }
    (OUT / "dungeon.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    print("wrote", ", ".join(p.name for p in sorted(OUT.iterdir())))


if __name__ == "__main__":
    main()
