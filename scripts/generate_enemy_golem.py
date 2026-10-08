"""Draw and animate the enemy "Gólem de Musgo" (a moss-covered stone golem). Stdlib only:

    python scripts/generate_enemy_golem.py

Same method as the Espectro and the floor-1 bosses (``docs/code-drawn-sprites.md``): one
renderer, every frame a ``Pose``. The golem is a wall: a hulking, hunched heap of boulders.

* ONE row-scanned mass (body + head + legs + back arm) built from chiselled stone boulders
  (superellipses with faceted upper-left light, dark seams where a boulder sits in front of
  another, speckle and carved cracks), cool grey-blue stone against the warm torch room;
* thick moss on every upward-facing surface (shoulders, head, forearm), grass tufts and a
  fern on the shoulders, moss strands hanging from the front shoulder;
* a small head sunk between the shoulders with two cyan-green eyes under a heavy brow, and a
  glowing rune carved on the chest (the cold accent);
* only the huge front arm (upper arm, forearm, fist boulders) is drawn on top with a dark rim
  (the Espectro sleeve rule).

Animations (non-death actions end on idle frame 0):
  idle    12-frame heavy breathing: shoulders rise 1 px, moss sways, rune pulses, a pebble falls
  attack  "Puño de Roca": raises the fist high, leans back, smashes down-left (floor crack,
          dust and rock chips), slow recovery
  cast    "Muro de Piedra": plants both fists, rune and eyes blaze, stone plates rise in a ring
          and a cyan-green barrier shimmers, then everything settles
  hurt    white flash, chips fly off, barely knocked back (it is heavy), dust at the feet
  death   cracks spread glowing, the rune goes dark, it crumbles into a heap of rocks that sinks
          into the floor -> empty

Output: ``assets/enemies/golem_sheet.png`` + ``.json`` (``events.<anim>.strikes``, ``moves``).
"""
from __future__ import annotations

import math
import sys
from dataclasses import dataclass, field, replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from pixel_kit import (Canvas, bayer, build_sheet, dissolve, flash, hash01, mix,  # noqa: E402
                       outline, ramp, save_sheet, smooth)

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "assets" / "enemies"
SHEET_ID = "golem"

CELL_W, CELL_H = 160, 108
CX, GROUND = 112, 100            # body centre line, ground row
ANCHOR = (CX, GROUND + 2)
BODY_H = 78.0                    # local height used for the hunch

# ---------------------------------------------------------------- palette
OUTLINE = (14, 15, 24)
STONE = [(24, 26, 38), (40, 44, 60), (58, 64, 84), (80, 88, 108), (106, 116, 134), (138, 148, 162),
         (176, 184, 194)]
MOSS = [(16, 34, 28), (26, 54, 34), (40, 80, 40), (62, 108, 46), (94, 140, 56), (136, 174, 76)]
RUNE = [(18, 76, 74), (36, 146, 128), (104, 226, 188), (206, 255, 234)]
DIRT = [(46, 36, 32), (78, 64, 52), (118, 102, 84), (160, 146, 120)]
WHITE = (255, 255, 255)

LIGHT = (-0.52, 0.56, 0.64)       # upper-left, towards the viewer (x right, y up, z out)
_LN = math.sqrt(sum(c * c for c in LIGHT))
LIGHT = tuple(c / _LN for c in LIGHT)

RUNE_GLYPH = ["...#...",
              "..###..",
              ".#.#.#.",
              "#..#..#",
              ".#.#.#.",
              "..#.#..",
              "...#..."]


@dataclass(frozen=True)
class Pose:
    dx: float = 0.0
    dy: float = 0.0
    lean: float = 0.0                 # top of the body offset (negative = towards the hero)
    sx: float = 1.0                   # squash/stretch about the ground
    sy: float = 1.0
    breath: float = 0.0               # shoulders/head lift (px)
    phase: float = 0.0
    sway: float = 1.0                 # moss / grass wave
    fist: tuple[float, float] = (-36.0, 14.0)    # front fist centre (rel. CX, height above ground)
    fist_b: tuple[float, float] = (25.0, 20.0)   # back fist (part of the mass)
    elbow: float = 1.0                # +1 elbow points back (right), -1 forward
    eye: float = 1.0
    rune: float = 0.8
    flash: float = 0.0
    dissolve: float = 0.0
    crack: float = 0.0                # death: glowing cracks spread 0..1
    crumble: float = 0.0              # death: falls apart into a heap 0..1
    sink: float = 0.0                 # death: the heap sinks into the floor (px)
    smash: float = 0.0                # attack: floor crack + dust + chips progress
    smash_x: float = -70.0            # where the fist hit (rel. CX)
    smash_fade: float = 0.0
    trail: float = 0.0                # attack: motion smear of the swing
    chips: float = 0.0                # hurt: chips knocked off
    plates: float = 0.0               # cast: stone plates rising 0..1
    shimmer: float = 0.0              # cast: barrier shimmer strength
    pebble: float = -1.0              # idle: falling pebble progress (<0 none)
    dust: float = 0.0                 # dust puff at the feet
    motes: tuple = field(default_factory=tuple)


# ---------------------------------------------------------------- boulders
class Blob:
    """A stone boulder: superellipse (centre, radii, rotation, exponent) with its own facets."""
    __slots__ = ("cx", "cy", "rx", "ry", "ang", "pw", "seed", "moss", "kind", "dark", "ca", "sa", "group")

    def __init__(self, cx, cy, rx, ry, *, ang=0.0, pw=2.2, seed=0, moss=0.0, kind="", dark=0.0, group=None):
        self.cx, self.cy = round(cx), round(cy)
        self.rx, self.ry = max(1.0, rx), max(1.0, ry)
        self.ang, self.pw, self.seed, self.moss, self.kind, self.dark = ang, pw, seed, moss, kind, dark
        self.ca, self.sa = math.cos(ang), math.sin(ang)
        self.group = seed if group is None else group

    def bbox(self):
        r = max(self.rx, self.ry) + 1
        return int(self.cx - r) - 1, int(self.cy - r) - 1, int(self.cx + r) + 2, int(self.cy + r) + 2

    def local(self, x: float, y: float):
        """Normalised local coords (ex along the blob axis, ey 'up' in the blob frame)."""
        X, Y = x - self.cx, self.cy - y                      # screen y up
        lx = X * self.ca + Y * self.sa
        ly = -X * self.sa + Y * self.ca
        return lx / self.rx, ly / self.ry

    def dist(self, ex: float, ey: float) -> float:
        p = self.pw
        return (abs(ex) ** p + abs(ey) ** p) ** (1 / p)

    def to_screen_normal(self, nx: float, ny: float):
        return nx * self.ca - ny * self.sa, nx * self.sa + ny * self.ca

    def point(self, ex: float, ey: float):
        """Cell coords of a local normalised point."""
        lx, ly = ex * self.rx, ey * self.ry
        X = lx * self.ca - ly * self.sa
        Y = lx * self.sa + ly * self.ca
        return self.cx + X, self.cy - Y


def _lambert(nx: float, ny: float, nz: float) -> float:
    return max(0.0, nx * LIGHT[0] + ny * LIGHT[1] + nz * LIGHT[2])


def shade_stone(b: Blob, ex: float, ey: float, d: float, x: int, y: int, p: Pose):
    """Colour of one boulder pixel: faceted + smooth light, speckle, moss on top faces."""
    dd = min(1.0, d)
    nz = math.sqrt(max(0.0, 1 - dd * dd))
    snx, sny = b.to_screen_normal(ex, ey)
    smooth_l = _lambert(snx, sny, nz)
    # chiselled facets: quantise the normal's direction and tilt
    th = math.atan2(ey, ex) + b.seed * 0.7
    step = math.tau / 7
    thq = round(th / step) * step - b.seed * 0.7
    rq = 0.0 if dd < 0.42 else 0.64 if dd < 0.8 else 0.92
    fnx, fny = b.to_screen_normal(rq * math.cos(thq), rq * math.sin(thq))
    facet_l = _lambert(fnx, fny, math.sqrt(1 - rq * rq))
    light = 0.08 + 0.58 * facet_l + 0.42 * smooth_l
    # facet edges catch a hairline (chisel marks) on the lit side
    edge = abs((th / step) - round(th / step))
    if 0.42 < dd < 0.9 and edge > 0.44:
        light += 0.07 if snx < 0 else -0.08
    h = GROUND - y
    light -= 0.20 * max(0.0, 1 - h / 40)                     # ground occlusion
    light += b.dark
    lx, ly = int(round(ex * b.rx)), int(round(ey * b.ry))
    sp = hash01(lx, ly, b.seed + 11)
    light += (sp - 0.5) * 0.10
    if dd > 0.9:
        light -= 0.10
    col = ramp(STONE, max(0.0, min(1.0, light)), x, y)
    if sp > 0.94 and dd < 0.85:
        col = STONE[max(0, STONE.index(col) - 2)] if col in STONE else col  # pits
    # moss on the upward faces
    if b.moss > 0 and p.crumble < 0.6:
        noise = hash01(int((th + 7) * 4.2), b.seed, 5)
        top = sny * (0.9 + 0.1 * nz)
        thr = 0.88 - 0.7 * b.moss + 0.22 * noise + 0.12 * math.sin(lx * 0.9 + b.seed)
        if top > thr:
            ml = 0.15 + 0.95 * smooth_l + (hash01(lx, ly, b.seed + 3) - 0.5) * 0.25
            ml -= 0.25 * max(0.0, min(1.0, (thr + 0.12 - top) / 0.12))   # darker at its lip
            col = ramp(MOSS, max(0.0, min(1.0, ml)), x, y, 0.7)
    if b.kind == "fist":                                       # finger seams on the leading face
        if ex < -0.3 and abs(abs(ey) - 0.34) < 0.09 and d < 0.97:
            col = STONE[0]
        elif ex < -0.3 and abs(ey) < 0.06 and d < 0.97:
            col = STONE[1]
    if b.kind == "head" and ey < 0.15:                         # face under the brow in shadow
        col = mix(col, STONE[0], 0.45 if ey > -0.5 else 0.25)
    return col


def paint_blobs(cv: Canvas, blobs, p: Pose, owner=None) -> None:
    """Row-scan every boulder (back to front) into ONE mass; seams where a boulder overlaps."""
    w, h = cv.w, cv.h
    for i, b in enumerate(blobs):
        x0, y0, x1, y1 = b.bbox()
        for y in range(max(0, y0), min(h, y1)):
            for x in range(max(0, x0), min(w, x1)):
                ex, ey = b.local(x + 0.5, y + 0.5)
                d = b.dist(ex, ey)
                if d > 1:
                    continue
                prev = cv.px[y][x]
                po = owner.get((x, y)) if owner is not None else None
                same = po is not None and blobs[po].group == b.group
                if prev is not None and d > 0.86 and not same:
                    col = STONE[0] if d > 0.93 else STONE[1]          # seam: boulder in front
                else:
                    col = shade_stone(b, ex, ey, d, x, y, p)
                cv.put(x, y, col)
                if owner is not None:
                    owner[(x, y)] = i


# ---------------------------------------------------------------- geometry
class Body:
    def __init__(self, p: Pose) -> None:
        self.p = p

    def place(self, lx: float, lh: float, lift: float = 0.0):
        p = self.p
        x = CX + p.dx + lx * p.sx + p.lean * (max(0.0, lh) / BODY_H) ** 1.2
        y = GROUND - lh * p.sy - lift * p.breath + p.dy
        return x, y

    def shoulder_f(self):
        return self.place(-22, 60, 1.0)

    def shoulder_b(self):
        return self.place(21, 60, 1.0)


def segment_blob(a, b, r, **kw) -> Blob:
    (x0, y0), (x1, y1) = a, b
    ln = math.hypot(x1 - x0, y1 - y0)
    ang = math.atan2(-(y1 - y0), x1 - x0)                  # screen y up
    return Blob((x0 + x1) / 2, (y0 + y1) / 2, ln / 2 + r * 0.55, r, ang=ang, **kw)


def ik(sh, target, l1, l2, bend):
    sx, sy = sh
    tx, ty = target
    dx, dy = tx - sx, ty - sy
    d = max(1e-3, math.hypot(dx, dy))
    d2 = min(d, l1 + l2 - 0.01)
    tx, ty = sx + dx / d * d2, sy + dy / d * d2
    a = (l1 * l1 - l2 * l2 + d2 * d2) / (2 * d2)
    hh = math.sqrt(max(0.0, l1 * l1 - a * a))
    mx, my = sx + dx / d * a, sy + dy / d * a
    px, py = -dy / d, dx / d
    return (mx + px * hh * bend, my + py * hh * bend), (tx, ty)


def body_blobs(b: Body):
    p = b.p
    out = []
    # back arm (behind everything, darker)
    bsx, bsy = b.shoulder_b()
    bfx, bfy = CX + p.dx + p.fist_b[0] * p.sx, GROUND - p.fist_b[1] + p.dy
    elb, wr = ik((bsx, bsy), (bfx, bfy - 3), 19, 20, -1.0)
    out.append(Blob(bfx, bfy, 8, 7.5, pw=2.5, seed=21, moss=0.25, kind="fist", dark=-0.16,
                    ang=math.atan2(-(bfy - elb[1]), bfx - elb[0]) + math.pi))
    out.append(segment_blob(elb, wr, 6.0, pw=2.3, seed=22, moss=0.3, dark=-0.14))
    out.append(segment_blob((bsx, bsy), elb, 7.0, pw=2.3, seed=23, moss=0.3, dark=-0.12))
    # legs and feet (planted)
    x, y = b.place(13, 11)
    out.append(Blob(x, y, 9 * p.sx, 11 * p.sy, pw=2.7, seed=3, dark=-0.08))
    x, y = b.place(15, 3)
    out.append(Blob(x, y, 11 * p.sx, 3.6, pw=3.2, seed=4, dark=-0.06))
    x, y = b.place(18, 63, 1.0)
    out.append(Blob(x, y, 14 * p.sx, 12 * p.sy, pw=2.2, seed=5, moss=0.85))
    x, y = b.place(2, 21)
    out.append(Blob(x, y, 18 * p.sx, 8 * p.sy, pw=2.4, seed=7, group=1, dark=-0.05))
    x, y = b.place(-2, 41, 0.45)
    out.append(Blob(x, y, 25 * p.sx, 23 * p.sy, pw=2.35, seed=8, moss=0.3, group=1))
    x, y = b.place(-12, 11)
    out.append(Blob(x, y, 10 * p.sx, 11 * p.sy, pw=2.7, seed=9))
    x, y = b.place(-14, 3)
    out.append(Blob(x, y, 12 * p.sx, 3.6, pw=3.2, seed=10))
    x, y = b.place(-7, 63, 1.0)
    out.append(Blob(x, y, 10 * p.sx, 8.5 * p.sy, pw=2.1, seed=12, moss=0.95, kind="head"))
    x, y = b.place(-22, 62, 1.0)
    out.append(Blob(x, y, 14 * p.sx, 12 * p.sy, pw=2.2, seed=13, moss=0.9))
    return out


def arm_blobs(b: Body):
    p = b.p
    sh = b.shoulder_f()
    fx, fy = CX + p.dx + p.fist[0] * p.sx, GROUND - p.fist[1] + p.dy
    dx, dy = fx - sh[0], fy - sh[1]
    d = max(1e-3, math.hypot(dx, dy))
    wrist_t = (fx - dx / d * 7, fy - dy / d * 7)
    elb, wr = ik(sh, wrist_t, 21, 22, p.elbow)
    fang = math.atan2(-(wr[1] - elb[1]), wr[0] - elb[0])
    fist_c = (wr[0] + math.cos(fang) * 7.5, wr[1] - math.sin(fang) * 7.5)
    return [
        segment_blob(sh, elb, 7.0, pw=2.3, seed=31, moss=0.55),
        segment_blob(elb, wr, 9.5, pw=2.5, seed=32, moss=0.75, dark=0.05),
        # fist: its leading face points along the forearm (local -x = front)
        Blob(fist_c[0], fist_c[1], 12, 10.5, pw=2.6, seed=33, moss=0.35, kind="fist", dark=0.12,
             ang=math.atan2(math.sin(fang) * 0.5, math.cos(fang) * 0.5 - 0.5) + math.pi),
    ], fist_c


# ---------------------------------------------------------------- details
def draw_cracks(cv: Canvas, blobs, owner, p: Pose) -> None:
    """Carved cracks on the big boulders; in death they spread and glow."""
    sets = {  # blob seed -> polylines in local normalised coords, (level at which it appears)
        8: [([(-0.5, 0.62), (-0.36, 0.3), (-0.44, 0.05), (-0.28, -0.3)], 0.0),
            ([(0.62, 0.1), (0.45, -0.2), (0.58, -0.55)], 0.0),
            ([(0.5, 0.75), (0.62, 0.45), (0.48, 0.25)], 0.35),
            ([(-0.1, -0.2), (0.15, -0.5), (0.0, -0.8)], 0.2)],
        7: [([(-0.5, 0.5), (-0.25, 0.05), (-0.42, -0.5)], 0.25)],
        5: [([(0.1, 0.1), (0.35, -0.2), (0.3, -0.55)], 0.0)],
        13: [([(-0.2, -0.1), (-0.45, -0.35), (-0.4, -0.7)], 0.1)],
        6: [([(-0.6, 0.3), (-0.2, -0.1), (0.1, 0.25), (0.5, -0.2)], 0.5)],
        9: [([(0.0, 0.6), (-0.25, 0.1), (0.1, -0.4)], 0.55)],
        3: [([(0.2, 0.7), (-0.1, 0.0), (0.15, -0.5)], 0.6)],
        12: [([(0.5, 0.5), (0.2, 0.2)], 0.7)],
        32: [([(-0.5, 0.3), (0.0, -0.2), (0.45, 0.25)], 0.45)],
        31: [([(-0.4, -0.2), (0.3, 0.3)], 0.65)],
    }
    by_seed = {b.seed: (i, b) for i, b in enumerate(blobs)}
    glow = p.crack
    for seed, lines in sets.items():
        if seed not in by_seed:
            continue
        idx, b = by_seed[seed]
        for pts, level in lines:
            if level > 0 and glow < level:
                continue
            grow = 1.0 if level == 0 else min(1.0, (glow - level) / 0.3)
            if level == 0 and glow > 0:
                grow = 1.0
            cells = [b.point(ex, ey) for ex, ey in pts]
            seg_pts = []
            for (x0, y0), (x1, y1) in zip(cells, cells[1:]):
                n = int(max(abs(x1 - x0), abs(y1 - y0))) + 1
                for k in range(n):
                    seg_pts.append((x0 + (x1 - x0) * k / n, y0 + (y1 - y0) * k / n))
            seg_pts = seg_pts[:max(1, int(len(seg_pts) * grow))]
            for k, (x, y) in enumerate(seg_pts):
                xi, yi = int(x), int(y)
                if owner.get((xi, yi)) != idx:
                    continue
                if glow > 0.05:
                    hot = glow > 0.5 and (k + int(glow * 10)) % 3 != 0
                    cv.put(xi, yi, RUNE[3] if hot else RUNE[2])
                    if owner.get((xi + 1, yi)) == idx:
                        cv.put(xi + 1, yi, RUNE[1])
                else:
                    cv.put(xi, yi, STONE[0])
                    if owner.get((xi - 1, yi - 1)) == idx and cv.get(xi - 1, yi - 1) is not None:
                        c = cv.get(xi - 1, yi - 1)
                        cv.put(xi - 1, yi - 1, mix(c[:3], STONE[6], 0.35))


def draw_rune(cv: Canvas, b: Body, p: Pose):
    cx, cy = b.place(5, 47, 0.6)
    cx, cy = round(cx), round(cy)
    k = p.rune
    for j, row in enumerate(RUNE_GLYPH):
        for i, ch in enumerate(row):
            if ch != "#":
                continue
            x, y = cx - 3 + i, cy - 3 + j
            if cv.get(x, y) is None:
                continue
            if k <= 0.05:
                col = STONE[0]
            else:
                lvl = 1 + (1 if k > 0.55 else 0) + (1 if k > 1.05 else 0)
                if (i, j) == (3, 3):
                    lvl = min(3, lvl + 1)
                col = RUNE[lvl]
            cv.put(x, y, col)
            # carved: the groove's lower-right lip is in shadow
            if RUNE_GLYPH[min(6, j + 1)][min(6, i + 1)] != "#" and cv.get(x + 1, y + 1) is not None:
                cv.put(x + 1, y + 1, STONE[1] if k < 1.1 else RUNE[0])
    return cx + 0.5, cy + 0.5


def draw_face(cv: Canvas, b: Body, p: Pose):
    hx, hy = b.place(-7, 63, 1.0)
    hx, hy = round(hx), round(hy)
    # heavy brow ridge
    for ox in range(-8, 6):
        y = hy - 2 + (1 if ox < -6 else 0)
        if cv.get(hx + ox, y) is not None:
            cv.put(hx + ox, y, STONE[4] if ox < -3 else STONE[3])
        if cv.get(hx + ox, y + 1) is not None:
            cv.put(hx + ox, y + 1, STONE[0])
    ex, ey = hx - 4, hy
    e = p.eye
    if e > 0.05:
        hot = RUNE[3] if e > 0.6 else RUNE[1]
        warm = RUNE[2] if e < 1.2 else RUNE[3]
        for ox, oy, c in ((-3, -1, warm), (-2, -1, hot), (-1, 0, hot), (0, 0, warm),
                          (4, 0, warm), (5, 0, hot), (6, -1, warm)):
            cv.put(ex + ox, ey + oy, c)
        if e > 1.15:
            for ox, oy in ((-3, -1), (6, -1), (-1, 1), (5, 1)):
                cv.put(ex + ox, ey + oy, RUNE[1])
    else:
        for ox, oy in ((-3, -1), (-2, -1), (-1, 0), (0, 0), (4, 0), (5, 0), (6, -1)):
            cv.put(ex + ox, ey + oy, STONE[0])
    # jaw slit
    for ox in range(-4, 1):
        if cv.get(ex + ox, ey + 4) is not None:
            cv.put(ex + ox, ey + 4, STONE[0])
    return ex + 1.5, ey + 0.5


def blade(cv: Canvas, x0: float, y0: float, height: float, bend: float, cols) -> None:
    n = max(1, int(height))
    for s in range(n + 1):
        t = s / n
        x = x0 + bend * t * t
        y = y0 - s
        c = cols[min(len(cols) - 1, int(t * len(cols)))]
        cv.put(round(x), round(y), c)


def draw_greenery(cv: Canvas, blobs, p: Pose) -> None:
    """Grass tufts and a fern growing on the shoulders and head, moss strands hanging."""
    if p.crumble > 0.3:
        return
    by_seed = {b.seed: b for b in blobs}
    wave = p.sway * math.sin(p.phase)
    tufts = [(13, 0.25, 4, 0.0), (13, 0.55, 3, 1.3), (5, 0.35, 4, 2.1), (12, 0.1, 3, 3.0),
             (5, -0.2, 4, 0.7)]
    for seed, ex, height, off in tufts:
        b = by_seed.get(seed)
        if b is None:
            continue
        x, y = b.point(ex, math.sqrt(max(0.0, 1 - abs(ex) ** 2.2)) * 0.97)
        for k, (ox, hk) in enumerate(((-1, 0.7), (0, 1.0), (1, 0.8), (2, 0.55))):
            bend = (1.2 * math.sin(p.phase + off + k * 0.8) * p.sway) + (ox - 0.5) * 1.2
            blade(cv, x + ox, y, height * hk, bend, (MOSS[2], MOSS[3], MOSS[4], MOSS[5]))
    # fern frond arching off the back shoulder
    b = by_seed.get(5)
    if b is not None:
        x0, y0 = b.point(-0.15, 0.98)
        sw = 0.8 * wave
        pts = []
        for s in range(14):
            t = s / 13
            pts.append((x0 + 9 * t + sw * t * t, y0 - 6 * math.sin(t * 2.4) + 2 * t))
        for k, (x, y) in enumerate(pts):
            cv.put(round(x), round(y), MOSS[3] if k < 9 else MOSS[2])
            if 1 < k < 12 and k % 2 == 0:
                ln = 2 if 3 < k < 10 else 1
                for s in range(1, ln + 1):
                    cv.put(round(x) - s // 2, round(y) - s, MOSS[4])
                    cv.put(round(x) + s // 2 + 1, round(y) + s - 1 + (1 if k > 7 else 0), MOSS[2])
    # moss strands hanging from the front shoulder's underside
    b = by_seed.get(13)
    if b is not None:
        for ex, ln, off in ((-0.75, 5, 0.0), (-0.45, 7, 1.4), (0.55, 4, 2.6)):
            x, y = b.point(ex, -math.sqrt(max(0.0, 1 - ex * ex)) * 0.9)
            for s in range(ln):
                t = s / ln
                xx = x + 0.9 * math.sin(p.phase + off) * p.sway * t * t
                cv.put(round(xx), round(y + s), MOSS[2] if s < ln - 2 else MOSS[1])


# ---------------------------------------------------------------- effects
def draw_pebble(cv: Canvas, b: Body, prog: float) -> None:
    if prog < 0:
        return
    x0, y0 = b.place(-34, 56, 1.0)
    if prog < 0.7:
        t = prog / 0.7
        x, y = x0 - 4 * t, y0 + (GROUND - 1 - y0) * t * t
    else:
        t = (prog - 0.7) / 0.3
        x, y = x0 - 4 - 6 * t, GROUND - 1 - 4 * math.sin(t * math.pi)
    for ox, oy, c in ((0, 0, STONE[5]), (1, 0, STONE[3]), (0, 1, STONE[3]), (1, 1, STONE[1])):
        cv.put(round(x) + ox, round(y) + oy, c)


def draw_smash(cv: Canvas, s: float, fade: float, ix: float) -> None:
    """Floor crack, dust and rock chips where the fist lands (left, towards the hero)."""
    if s <= 0:
        return
    x0 = CX + ix
    gy = GROUND + 1
    vis = 1 - fade
    # jagged cracks running along the floor (perspective: thin, shallow)
    for k, (dirx, ln, dy0) in enumerate(((-1, 30, 1), (1, 22, 2), (-1, 18, 3), (1, 14, 0))):
        n = int(ln * min(1.0, s * 1.5))
        x, y = x0, gy + dy0 * 0.5
        for i in range(n):
            x += dirx
            if hash01(i, k, 3) > 0.6:
                y += 1 if hash01(i, k, 4) > 0.5 else -1
            y = max(gy - 1, min(gy + 4, y))
            if vis > 0.2:
                cv.put(round(x), round(y), OUTLINE, solid=False, alpha=int(255 * min(1.0, vis * 1.5)))
                if i < n * 0.35:
                    cv.put(round(x), round(y) + 1, STONE[0], solid=False, alpha=int(230 * vis))
                if i < n * 0.4 and s < 0.9:
                    cv.put(round(x), round(y) - 1, RUNE[1] if i % 3 else DIRT[3], solid=False,
                           alpha=int(200 * vis))
    # impact burst: short bright rays at the contact point
    if s < 0.45:
        kk = 1 - s / 0.45
        for r in range(8):
            ang = math.pi + r / 7 * math.pi + 0.2 * hash01(r, 1, 8)
            ln = (5 + 7 * hash01(r, 2, 8)) * (0.5 + kk)
            for j in range(int(ln)):
                x = x0 + math.cos(ang) * (3 + j)
                y = gy - 3 + math.sin(ang) * (3 + j) * 0.8
                c = WHITE if j < ln * 0.5 else RUNE[2]
                cv.put(round(x), round(y), c, solid=False, alpha=int(255 * kk))
    # dust clouds rolling out sideways
    for k in range(7):
        side = -1 if k % 2 == 0 else 1
        dist = (6 + 26 * hash01(k, 1, 6)) * smooth(min(1.0, s * 1.2)) * (1.3 if side < 0 else 0.8)
        cx = x0 + side * dist
        cy = gy - 3 - 7 * s * hash01(k, 2, 6)
        r = 3 + 6 * s * (0.6 + 0.4 * hash01(k, 3, 6))
        a = vis * (1 - 0.4 * s)
        if a <= 0.02:
            continue
        for yy in range(int(cy - r) - 1, int(cy + r) + 2):
            for xx in range(int(cx - r) - 1, int(cx + r) + 2):
                d = math.hypot(xx + 0.5 - cx, (yy + 0.5 - cy) * 1.3) / r
                if d > 1 or yy > gy + 2:
                    continue
                if bayer(xx, yy) > (1.3 - d) * a * 1.3:
                    continue
                lvl = 3 if d < 0.35 and yy < cy else 2 if d < 0.7 else 1
                cv.put(xx, yy, DIRT[lvl], solid=False, alpha=int(255 * min(1.0, a + 0.45)))
    # rock chips flying in arcs
    for k in range(9):
        vx = (-1.4 + 2.2 * hash01(k, 5, 6)) * 26
        vy = 18 + 16 * hash01(k, 6, 6)
        t = s * 1.1
        x = x0 + vx * t
        y = gy - 2 - vy * t + 30 * t * t
        if y > gy or vis < 0.3:
            continue
        sz = 1 + (k % 3 == 0)
        for ox in range(sz + 1):
            for oy in range(sz):
                cv.put(round(x) + ox, round(y) + oy, STONE[5] if (ox, oy) == (0, 0) else STONE[2])


def draw_trail(cv: Canvas, b: Body, k: float, p: Pose) -> None:
    """Motion smear of the fist swinging down from overhead (an arc around the shoulder)."""
    if k <= 0:
        return
    sh = b.shoulder_f()
    fx, fy = CX + p.dx + p.fist[0] * p.sx, GROUND - p.fist[1] + p.dy
    rx_, ry_ = CX - 14, GROUND - 86                      # where the fist was raised
    a0 = math.atan2(ry_ - sh[1], rx_ - sh[0])
    a1 = math.atan2(fy - sh[1], fx - sh[0])
    while a1 > a0:                                      # sweep: up -> over the front -> down-left
        a1 -= math.tau
    r0, r1 = math.hypot(rx_ - sh[0], ry_ - sh[1]), math.hypot(fx - sh[0], fy - sh[1])
    n = 90
    for i in range(n):
        t = i / (n - 1)
        a = a1 + (a0 - a1) * t * 0.85                   # t = 0 at the fist, 1 back towards the top
        r = r1 + (r0 - r1) * t
        w = 11 * (1 - t) + 2
        tt = 1 - t                                      # 1 near the fist
        for j in range(int(w) + 1):
            rr = r - w / 2 + j
            x, y = sh[0] + math.cos(a) * rr, sh[1] + math.sin(a) * rr
            if bayer(int(x), int(y)) > (0.25 + 0.75 * tt) * tt * k * 1.5:
                continue
            outer = j >= int(w) - 1
            c = WHITE if outer and tt > 0.75 else STONE[6] if outer or tt > 0.8 else STONE[4]
            cv.put(round(x), round(y), c, solid=False, alpha=int(110 + 140 * tt))


def draw_chips(cv: Canvas, b: Body, s: float) -> None:
    """Hurt: chips knocked off the chest and shoulder, flying right/up."""
    if s <= 0:
        return
    ox, oy = b.place(-10, 52, 1.0)
    for k in range(8):
        vx = 8 + 30 * hash01(k, 1, 9)
        vy = 10 + 22 * hash01(k, 2, 9)
        x = ox + (hash01(k, 3, 9) - 0.5) * 18 + vx * s
        y = oy + (hash01(k, 4, 9) - 0.5) * 14 - vy * s + 40 * s * s
        sz = 1 + (k % 3 == 0)
        for i in range(sz + 1):
            for j in range(sz):
                cv.put(round(x) + i, round(y) + j, STONE[5] if (i, j) == (0, 0) else STONE[3])


def draw_dust(cv: Canvas, k: float) -> None:
    if k <= 0:
        return
    for side, base in ((-1, CX - 22), (1, CX + 26)):
        for j in range(5):
            cx = base + side * (2 + 10 * k * hash01(j, side + 2, 7))
            cy = GROUND - 1 - 4 * k * hash01(j, 4, 7)
            r = 2 + 3 * k
            for yy in range(int(cy - r), int(cy + r) + 1):
                for xx in range(int(cx - r), int(cx + r) + 1):
                    d = math.hypot(xx + 0.5 - cx, yy + 0.5 - cy) / r
                    if d > 1 or yy > GROUND + 1 or bayer(xx, yy) > (1.2 - d) * (1 - k * 0.6):
                        continue
                    cv.put(xx, yy, DIRT[2 if d < 0.5 else 1], solid=False, alpha=170)


PLATES = [(k / 9 * math.tau + 0.35, 0.75 + 0.25 * hash01(k, 1, 12)) for k in range(9)]


def draw_plates(cv: Canvas, rise: float, front: bool, t: float) -> None:
    """Stone slabs rising from the floor in a ring around the golem (cast)."""
    if rise <= 0:
        return
    gx = CX - 4
    for k, (a, hk) in enumerate(PLATES):
        sa = math.sin(a)
        if (sa > 0) != front:
            continue
        x = gx + math.cos(a) * 48
        y = GROUND + sa * 7
        delay = hash01(k, 3, 12) * 0.35
        r = smooth(max(0.0, min(1.0, (rise - delay) / (1 - delay + 1e-6)))) if rise < 1.5 else 1.0
        hgt = (11 + 9 * hk) * r
        if hgt < 1:
            continue
        w = 7 + int(3 * hk)
        tilt = math.cos(a) * 0.18
        for j in range(int(hgt)):
            for i in range(w):
                xx = round(x - w / 2 + i + tilt * j)
                yy = round(y - j)
                top = j >= int(hgt) - 2
                lit = i < 2
                light = 0.72 if lit else 0.46 if i < w - 1 else 0.24
                if top:
                    light = 0.85 if lit else 0.68
                light -= 0.18 * (1 - j / max(1, hgt))
                col = ramp(STONE, light, xx, yy)
                if i == w // 2 and 3 < j < hgt - 3 and (j + k) % 4 != 0:
                    col = RUNE[2] if rise > 0.5 else RUNE[1]
                cv.put(xx, yy, col)
        for i in range(-1, w + 1):                       # dirt lip at the base
            cv.put(round(x - w / 2 + i), round(y) + 1, DIRT[1])


def draw_shimmer(cv: Canvas, k: float, t: float) -> None:
    """Translucent cyan-green barrier dome over the golem (cast)."""
    if k <= 0:
        return
    gx, gy = CX - 4, GROUND - 2
    rx, ry = 51.0, 80.0
    band = (t * 40) % 12
    for y in range(max(0, int(gy - ry) - 1), int(gy) + 1):
        for x in range(max(0, int(gx - rx) - 1), min(CELL_W, int(gx + rx) + 2)):
            dx, dy = (x + 0.5 - gx) / rx, (gy - y - 0.5) / ry
            d = math.hypot(dx, dy)
            if d > 1:
                continue
            rim = d > 0.93
            hexl = ((x + (y // 4) * 2) % 8 == 0) or (y % 4 == 0 and (x // 2 + y // 4) % 4 == 0)
            scan = abs(((gy - y) % 12) - band) < 1
            if rim:
                a = 0.75 * k
                c = RUNE[3] if d > 0.97 or dx < -0.5 else RUNE[2]
            elif hexl or scan:
                a = (0.16 + 0.2 * d) * k
                c = RUNE[2]
            else:
                a = 0.12 * k * d
                c = RUNE[1]
            if a < 0.04 or bayer(x, y) > a * 2.2:
                continue
            cv.put(x, y, c, solid=False, alpha=int(255 * min(0.9, a + 0.25)))


def crumble(cv: Canvas, c: float, sink: float) -> Canvas:
    """Break the figure into rocks that fall into a heap (Voronoi chunks), then sink."""
    cell = 9
    pts = {}

    def site(gx, gy):
        key = (gx, gy)
        if key not in pts:
            pts[key] = (gx * cell + 1 + hash01(gx, gy, 41) * (cell - 2),
                        gy * cell + 1 + hash01(gx, gy, 42) * (cell - 2))
        return pts[key]

    chunk = {}
    for y in range(cv.h):
        for x in range(cv.w):
            if cv.px[y][x] is None:
                continue
            gx, gy = x // cell, y // cell
            best, bk = 1e9, None
            for ox in (-1, 0, 1):
                for oy in (-1, 0, 1):
                    sx, sy = site(gx + ox, gy + oy)
                    d = (x + 0.5 - sx) ** 2 + (y + 0.5 - sy) ** 2
                    if d < best:
                        best, bk = d, (gx + ox, gy + oy)
            chunk[(x, y)] = bk
    out = Canvas(cv.w, cv.h)
    groups: dict = {}
    for (x, y), k in chunk.items():
        groups.setdefault(k, []).append((x, y))
    order = sorted(groups, key=lambda k: site(*k)[1])
    for k in order:
        sx, sy = site(*k)
        delay = 0.35 * hash01(*k, 45) + 0.15 * max(0.0, min(1.0, (sy - 30) / 70))
        e = smooth((c - delay) / (1 - delay)) if c < 1 else 1.0
        hgt = max(0.0, GROUND - sy)
        mound = max(0.0, 1 - abs(sx - CX + 4) / 46)          # the heap is highest in the middle
        target_h = min(hgt, 3 + 15 * mound * (0.7 + 0.3 * hash01(*k, 43)) + hgt * 0.04)
        fall = round(e * (hgt - target_h) + sink)
        shift = round(e * ((sx - CX) * 0.2 + (hash01(*k, 44) - 0.5) * 6))
        crack_on = c > 0.02
        for (x, y) in groups[k]:
            col = cv.px[y][x]
            ny = y + fall
            if ny > GROUND + 2:
                continue
            rgb = col[:3]
            if crack_on:
                below = chunk.get((x, y + 1)) not in (k, None) or chunk.get((x + 1, y)) not in (k, None)
                above = chunk.get((x, y - 1)) not in (k, None) or chunk.get((x - 1, y)) not in (k, None)
                if below:
                    rgb = OUTLINE if e > 0.05 else mix(rgb, OUTLINE, 0.6)
                elif above and e > 0.05:
                    rgb = mix(rgb, STONE[5], 0.35)
                else:
                    rgb = mix(rgb, STONE[2], 0.2 * e)
            out.put(x + shift, ny, rgb, solid=cv.solid[y][x], alpha=col[3])
    return out


# ---------------------------------------------------------------- render
def render(p: Pose, t: float = 0.0) -> Canvas:
    cv = Canvas(CELL_W, CELL_H)
    b = Body(p)
    draw_plates(cv, p.plates, False, t)
    owner: dict = {}
    blobs = body_blobs(b)
    body = Canvas(CELL_W, CELL_H)
    paint_blobs(body, blobs, p, owner)
    rune_c = draw_rune(body, b, p)
    eye_c = draw_face(body, b, p)
    draw_cracks(body, blobs, owner, p)
    cv.blit(body)
    arm, fist_c = arm_blobs(b)
    arm_cv = Canvas(CELL_W, CELL_H)
    arm_owner: dict = {}
    paint_blobs(arm_cv, arm, p, arm_owner)
    draw_cracks(arm_cv, arm, arm_owner, p)
    cv.blit(arm_cv, rim=OUTLINE)
    draw_greenery(cv, blobs + arm, p)
    draw_plates(cv, p.plates, True, t)
    draw_pebble(cv, b, p.pebble)
    draw_chips(cv, b, p.chips)
    if p.crumble > 0 or p.sink > 0:
        cv = crumble(cv, p.crumble, p.sink)
    outline(cv, OUTLINE)
    # lights
    if p.crumble < 0.2:
        if p.eye > 0.05:
            cv.glow(eye_c[0], eye_c[1], 5 + 3 * p.eye, RUNE[1], 0.35 * p.eye)
        if p.rune > 0.05:
            cv.glow(rune_c[0], rune_c[1], 7 + 5 * p.rune, RUNE[1], 0.32 * p.rune)
    if p.crack > 0.1 and p.crumble < 0.5:
        cx, cy = b.place(0, 42)
        cv.glow(cx, cy, 30, RUNE[0], 0.25 * p.crack * (1 - p.crumble), halo=False)
    draw_trail(cv, b, p.trail, p)
    draw_smash(cv, p.smash, p.smash_fade, p.smash_x)
    draw_dust(cv, p.dust)
    draw_shimmer(cv, p.shimmer, t)
    for (mx, my, lv) in p.motes:
        cv.put(mx, my, DIRT[lv] if lv < 4 else RUNE[2], solid=False)
    flash(cv, p.flash)
    if p.dissolve > 0:
        dissolve(cv, p.dissolve, GROUND - 22, GROUND + 3, DIRT[3], DIRT[2], upward=False)
    return cv


# ---------------------------------------------------------------- animations
IDLE_FRAMES = 12


def idle_pose(i: int, n: int = IDLE_FRAMES) -> Pose:
    i %= n
    a = math.tau * i / n
    breath = round(math.sin(a))                          # shoulders rise/fall 1 px
    pebble = (i - 4) / 5 if 4 <= i <= 9 else -1.0
    return Pose(
        breath=breath, phase=a, sway=1.0, lean=0,
        fist=(-36 + round(0.6 * math.sin(a + 0.5)), 14 + round(math.sin(a - 0.3))),
        fist_b=(25, 20 + round(math.sin(a - 0.5))),
        eye=0.8 if i == 7 else 1.0,
        rune=0.75 + 0.3 * math.sin(2 * a),
        pebble=pebble,
    )


def idle_frames():
    return [(idle_pose(i), 115) for i in range(IDLE_FRAMES)]


def attack_frames():
    """Puño de Roca: raise the fist high, lean back, smash down-left, slow recovery."""
    b = idle_pose(0)
    return [
        (replace(b, lean=3, sy=1.01, breath=1, fist=(-34, 38), elbow=-1.0, eye=1.1, phase=0.3), 95),
        (replace(b, lean=6, sy=1.03, breath=1, fist=(-26, 72), elbow=-1.0, eye=1.3, rune=1.1,
                 phase=0.6), 125),
        (replace(b, lean=8, sy=1.04, breath=1, fist=(-20, 88), elbow=-1.0, eye=1.45, rune=1.3,
                 phase=0.9), 110),
        (replace(b, lean=-9, sy=0.94, sx=1.04, fist=(-70, 10), elbow=1.0, eye=1.5, rune=1.2,
                 phase=1.3, trail=1.0, smash=0.25, dust=0.4), 55),
        (replace(b, lean=-10, sy=0.93, sx=1.05, fist=(-70, 9), elbow=1.0, eye=1.4, rune=1.1,
                 phase=1.6, trail=0.4, smash=0.55, dust=0.8), 60),
        (replace(b, lean=-9, sy=0.95, sx=1.03, fist=(-68, 10), eye=1.25, phase=2.0, smash=0.8,
                 smash_fade=0.3), 90),
        (replace(b, lean=-6, sy=0.97, fist=(-56, 12), eye=1.1, phase=2.6, smash=1.0,
                 smash_fade=0.65), 90),
        (replace(b, lean=-3, sy=0.99, fist=(-42, 13), phase=3.4, smash=1.0, smash_fade=0.9), 90),
        (replace(b, lean=-1, fist=(-33, 13), phase=4.4), 85),
        (b, 100),
    ]


def cast_frames():
    """Muro de Piedra: plant the fists, rune and eyes blaze, plates rise, the barrier flashes."""
    b = idle_pose(0)
    out = []
    plan = [  # (plant, plates, shimmer, blaze)
        (0.5, 0.0, 0.0, 0.3), (1.0, 0.15, 0.0, 0.7), (1.0, 0.45, 0.2, 1.0), (1.0, 0.8, 0.9, 1.0),
        (1.0, 1.0, 0.6, 0.9), (1.0, 1.0, 0.35, 0.7), (0.8, 0.75, 0.15, 0.45), (0.5, 0.4, 0.0, 0.25),
        (0.2, 0.1, 0.0, 0.1),
    ]
    for k, (pl, pt, sh, bz) in enumerate(plan):
        out.append((replace(
            b, sy=1.0 - 0.05 * pl, sx=1.0 + 0.03 * pl, lean=-round(3 * pl), breath=0,
            fist=(-30 - 4 * pl, 13 - 7 * pl), fist_b=(25 + 3 * pl, 20 - 12 * pl),
            eye=1.0 + 0.55 * bz, rune=0.8 + 0.8 * bz, plates=pt, shimmer=sh,
            dust=0.6 if k in (1, 2) else 0.0, phase=0.45 * k), 85))
    out.append((b, 110))
    return out


def hurt_frames():
    b = idle_pose(0)
    return [
        (replace(b, dx=1, lean=3, sx=1.03, sy=0.97, flash=0.82, eye=0.4, chips=0.2, dust=0.3,
                 fist=(-28, 14), phase=0.8), 60),
        (replace(b, dx=2, lean=3, sx=1.02, sy=0.98, flash=0.5, eye=0.6, chips=0.5, dust=0.6,
                 fist=(-28, 14), phase=1.4), 70),
        (replace(b, dx=1, lean=2, flash=0.18, eye=0.8, chips=0.8, dust=0.85, phase=2.0), 80),
        (replace(b, dx=1, lean=1, chips=1.05, phase=2.8), 90),
        (replace(b, lean=0, phase=3.6), 95),
        (b, 105),
    ]


def death_frames():
    b = idle_pose(0)
    out = [
        (replace(b, dx=1, lean=3, sy=0.97, flash=0.85, eye=0.5, chips=0.25), 70),
        (replace(b, lean=2, crack=0.3, eye=1.6, rune=1.6, flash=0.25, chips=0.55, phase=0.5), 90),
        (replace(b, lean=1, crack=0.6, eye=1.3, rune=1.2, phase=1.0), 90),
        (replace(b, lean=0, sy=0.99, crack=0.9, eye=0.7, rune=0.5, phase=1.5), 90),
        (replace(b, lean=-1, sy=0.98, crack=1.0, eye=0.0, rune=0.0, phase=2.0), 90),
    ]
    steps = 6
    for k in range(steps):
        u = (k + 1) / steps
        motes = tuple((CX - 40 + hash01(k, j, 51) * 80, GROUND - 8 - hash01(j, k, 52) * 40 * u,
                       1 + int(hash01(j, k, 53) * 3)) for j in range(6 + 2 * k))
        out.append((replace(b, crack=1.0 - 0.6 * u, eye=0.0, rune=0.0, crumble=u, lean=-1,
                            dust=0.5 + 0.5 * u, motes=motes, phase=2.0 + 0.3 * k), 80))
    for k, (d, s) in enumerate(((0.3, 2), (0.6, 4), (0.85, 6))):
        motes = tuple((CX - 34 + hash01(k, j, 54) * 68, GROUND - 4 - hash01(j, k, 55) * 26,
                       1 + int(hash01(j, k, 56) * 3)) for j in range(10 - 3 * k))
        out.append((replace(b, crack=0.0, eye=0.0, rune=0.0, crumble=1.0, sink=s, lean=-1,
                            dissolve=d, dust=1.0 - 0.3 * k, motes=motes), 85))
    out.append((replace(b, crumble=1.0, eye=0.0, rune=0.0, dissolve=1.0), 120))
    return out


ANIMATIONS = {
    "idle": (idle_frames, True),
    "attack": (attack_frames, False),
    "cast": (cast_frames, False),
    "hurt": (hurt_frames, False),
    "death": (death_frames, False),
}

# Frame where the fist lands (attack).
EVENTS = {"attack": {"strikes": [3]}}
MOVES = {"punch": "attack", "wall": "cast", "harden": "cast", "vengeance": "cast"}


def build():
    return build_sheet(ANIMATIONS, render, (CELL_W, CELL_H), ANCHOR, f"{SHEET_ID}_sheet.png",
                       {"events": EVENTS, "moves": MOVES})


def main() -> None:
    sheet, meta = build()
    save_sheet(OUT_DIR, SHEET_ID, sheet, meta)
    print(f"wrote assets/enemies/{SHEET_ID}_sheet.png ({len(sheet[0])}x{len(sheet)}) and .json")


if __name__ == "__main__":
    main()
