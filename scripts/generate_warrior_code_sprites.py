"""Draw and animate "La Guerrera" by code, exactly like the Espectro: ONE mass.

Standard library only:

    python scripts/generate_warrior_code_sprites.py

Technique of ``generate_enemy_sprites.py`` (docs/code-drawn-sprites.md): the
whole figure is a single silhouette scanned row by row from the top of the
head to the soles. Each row has a centre line (hips + lean + squash) and a
front/back extent from one height profile; hair, face, neck, pauldrons,
breastplate, belt, tabard, the ponytail down her back, the cape behind and the
boots are **zones painted inside that one mass** (by height and by distance
from the centre line), all shaded with the same light, folds and Bayer dither.
There are no limbs drawn as separate pieces. Only the sword and the arm that
holds it are drawn on top (like the Espectro's front sleeve), with a dark rim
where they cross the body.

Animation deforms the mass, like the Espectro: offsets, lean, squash/stretch,
cloth and hair waves, a sink for kneeling; the boots stay on the floor.

  idle    breath (bob + lean), ponytail and cape sway, sword tip bob, one blink
  attack  lean back with the sword raised → lunge (stretch, step) with a warm
          slash arc → follow-through (blade connects on frame 3)
  guard   crouch, blade upright, blue ward crescent
  hurt    white flash, knocked back, ponytail whips forward, wince
  cast    sword raised, golden blade glow, sparkles (skills and powers)
  death   knocked back, then sinks to her knees, the tabard pooling, head bowed (held)

Look: red ponytail and bangs, green eyes, gold circlet; silver plate with gold
trim; long crimson tabard with a gold emblem; dark-teal cape; leather boots.
Output (``assets/characters/``): ``warrior_sheet_96.png`` (native),
``warrior_sheet.png`` (×2, combat) and ``warrior_sheet.json``.
"""
from __future__ import annotations

import json
import math
import struct
import zlib
from dataclasses import dataclass, field, replace
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHAR_DIR = ROOT / "assets" / "characters"
SHEET_PATH = CHAR_DIR / "warrior_sheet.png"
SHEET_96_PATH = CHAR_DIR / "warrior_sheet_96.png"
META_PATH = CHAR_DIR / "warrior_sheet.json"

CELL = 96                 # native cell; the combat sheet is ×2 (192)
GROUND = 95               # last row of the soles
HIP = (46.0, 58.0)        # resting hip point (native)
BODY_H = 36.0             # head top -> hips (rows, before squash)
HEM = 57.0                # tabard hem, in the same row units

# ---------------------------------------------------------------- palette
OUTLINE = (20, 10, 18)
SKIN = [(96, 44, 44), (160, 88, 74), (212, 136, 106), (242, 182, 146)]
HAIR = [(60, 12, 20), (110, 22, 28), (168, 36, 32), (214, 66, 42), (246, 116, 66), (255, 172, 114)]
STEEL = [(32, 36, 52), (64, 72, 96), (106, 116, 144), (156, 166, 192), (204, 212, 230), (244, 248, 255)]
GOLD = [(88, 54, 18), (154, 104, 34), (216, 164, 58), (252, 218, 124)]
CAPE = [(10, 24, 32), (16, 42, 52), (24, 66, 76), (38, 98, 104), (64, 134, 134)]
CLOTH = [(58, 14, 26), (104, 26, 38), (152, 40, 46), (198, 66, 58)]
LEATHER = [(30, 18, 18), (58, 36, 30), (92, 60, 44), (130, 94, 66)]
BLADE = [(62, 70, 92), (140, 150, 174), (212, 220, 234), (255, 255, 255)]
IRIS = (46, 120, 96)
BROW = (110, 22, 28)
WARM = [(130, 54, 20), (236, 136, 44), (255, 214, 124), (255, 255, 236)]
WARD = [(30, 64, 130), (70, 134, 224), (150, 204, 255), (236, 250, 255)]
WHITE = (255, 255, 255)

BAYER = [[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]]
LIGHT = (-0.55, -0.65, 0.52)
_LN = math.sqrt(sum(c * c for c in LIGHT))
LIGHT = tuple(c / _LN for c in LIGHT)


def bayer(x: int, y: int) -> float:
    return (BAYER[y & 3][x & 3] + 0.5) / 16.0


def hash01(x: int, y: int, s: int = 0) -> float:
    h = (x * 374761393 + y * 668265263 + s * 2147483647) & 0xFFFFFFFF
    h = ((h ^ (h >> 13)) * 1274126177) & 0xFFFFFFFF
    return ((h ^ (h >> 16)) & 0xFFFF) / 65535.0


def mix(a, b, k: float):
    k = max(0.0, min(1.0, k))
    return tuple(int(round(a[i] + (b[i] - a[i]) * k)) for i in range(3))


def add(a, b):
    return (a[0] + b[0], a[1] + b[1])


def sub(a, b):
    return (a[0] - b[0], a[1] - b[1])


def mul(a, k):
    return (a[0] * k, a[1] * k)


def norm(a):
    d = math.hypot(*a) or 1.0
    return (a[0] / d, a[1] / d)


def lerp(a, b, k: float):
    return (a[0] + (b[0] - a[0]) * k, a[1] + (b[1] - a[1]) * k)


def tone(ramp, light: float, x: int, y: int, dither: float = 0.55):
    """Quantise a light value to ``ramp`` with the ordered dither (Espectro shading)."""
    level = light * (len(ramp) - 1) + (bayer(x, y) - 0.5) * dither
    return ramp[max(0, min(len(ramp) - 1, int(round(level))))]


def bbox(points, pad: float):
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    return (max(0, int(min(xs) - pad) - 1), max(0, int(min(ys) - pad) - 1),
            min(CELL - 1, int(max(xs) + pad) + 1), min(CELL - 1, int(max(ys) + pad) + 1))


def bezier(a, c, b, n: int):
    return [((1 - t) ** 2 * a[0] + 2 * (1 - t) * t * c[0] + t * t * b[0],
             (1 - t) ** 2 * a[1] + 2 * (1 - t) * t * c[1] + t * t * b[1])
            for t in (i / n for i in range(n + 1))]


def through(a, mid, b):
    """Control point so the quadratic curve a -> b passes through ``mid`` at t = 0.5."""
    return (2 * mid[0] - (a[0] + b[0]) / 2, 2 * mid[1] - (a[1] + b[1]) / 2)


# ---------------------------------------------------------------- canvas
class Canvas:
    def __init__(self, size: int = CELL) -> None:
        self.size = size
        self.px = [[None] * size for _ in range(size)]
        self.solid = [[False] * size for _ in range(size)]

    def get(self, x: int, y: int):
        if 0 <= x < self.size and 0 <= y < self.size:
            return self.px[y][x]
        return None

    def put(self, x: int, y: int, c, *, solid: bool = True, alpha: int = 255) -> None:
        if not (0 <= x < self.size and 0 <= y < self.size):
            return
        if alpha >= 255:
            self.px[y][x] = (*c[:3], 255)
        else:
            old = self.px[y][x]
            if old is None:
                self.px[y][x] = (*c[:3], alpha)
            else:
                self.px[y][x] = (*mix(old[:3], c, alpha / 255), max(old[3], alpha))
        if solid:
            self.solid[y][x] = True

    def stamp(self, part: dict, *, rim: bool = False) -> None:
        """Copy a part over the canvas; ``rim`` darkens what it overlaps along its edge."""
        if rim:
            for (x, y) in part:
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    qx, qy = x + dx, y + dy
                    if (qx, qy) in part or not (0 <= qx < self.size and 0 <= qy < self.size):
                        continue
                    if self.px[qy][qx] is not None and self.solid[qy][qx]:
                        self.px[qy][qx] = (*OUTLINE, 255)
        for (x, y), c in part.items():
            self.put(x, y, c)

    def glow(self, cx: float, cy: float, radius: float, color, strength: float) -> None:
        r = int(radius + 1)
        for y in range(int(cy) - r, int(cy) + r + 1):
            for x in range(int(cx) - r, int(cx) + r + 1):
                d = math.hypot(x + 0.5 - cx, y + 0.5 - cy) / radius
                if d >= 1:
                    continue
                k = (1 - d) ** 2 * strength
                if k < bayer(x, y) * 0.25:
                    continue
                old = self.get(x, y)
                if old is None:
                    if k > 0.16:
                        self.put(x, y, color, solid=False, alpha=int(min(210, 255 * k)))
                else:
                    self.px[y][x] = (*mix(old[:3], color, min(0.8, k)), old[3])


def sweep(part: dict, pts, width, paint, *, caps: bool = True) -> None:
    """Sweep a shape along the polyline ``pts`` (the Espectro technique for limbs).

    ``width(t) -> (back, front)`` gives the half-width on each side of the curve
    (front = left of the direction of travel turned to the figure's front);
    ``paint(t, u, x, y, nx, ny) -> colour`` colours a pixel, where ``u`` in -1..1
    runs across the shape and ``(nx, ny)`` is the across direction on screen.
    The shape is one continuous surface: no joints, no seams.
    """
    n = len(pts) - 1
    lens = [math.hypot(pts[i + 1][0] - pts[i][0], pts[i + 1][1] - pts[i][1]) for i in range(n)]
    total = sum(lens) or 1e-6
    cum = [0.0]
    for L in lens:
        cum.append(cum[-1] + L)
    wmax = max(max(width(i / 20)) for i in range(21))
    x0, y0, x1, y1 = bbox(pts, wmax + 1)
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            px, py = x + 0.5, y + 0.5
            best = None
            for i in range(n):
                ax, ay = pts[i]
                dx, dy = pts[i + 1][0] - ax, pts[i + 1][1] - ay
                L2 = dx * dx + dy * dy or 1e-9
                s = ((px - ax) * dx + (py - ay) * dy) / L2
                sc = max(0.0, min(1.0, s))
                qx, qy = ax + dx * sc, ay + dy * sc
                d2 = (px - qx) ** 2 + (py - qy) ** 2
                if best is None or d2 < best[0]:
                    best = (d2, i, sc, s, dx, dy, qx, qy)
            d2, i, sc, s, dx, dy, qx, qy = best
            if not caps and ((i == 0 and s < 0) or (i == n - 1 and s > 1)):
                continue
            t = max(0.0, min(1.0, (cum[i] + lens[i] * sc) / total))
            L = math.sqrt(dx * dx + dy * dy) or 1e-9
            tx, ty = dx / L, dy / L
            side = (px - qx) * (-ty) + (py - qy) * tx          # >0: left of travel
            wb, wf = width(t)
            w = wf if side > 0 else wb
            if w <= 0 or d2 > w * w:
                continue
            u = math.sqrt(d2) / w * (1 if side > 0 else -1)
            part[(x, y)] = paint(t, u, x, y, -ty, tx)


def lit(u: float, nx: float, ny: float, ramp, x: int, y: int, bias: float = 0.0, dither: float = 0.5):
    """Cylinder shading across a swept shape (same light as everything else)."""
    sx, sy = nx * u, ny * u
    nz = math.sqrt(max(0.0, 1.0 - u * u))
    lam = max(0.0, sx * LIGHT[0] + sy * LIGHT[1] + nz * LIGHT[2])
    level = (0.06 + 0.82 * lam + bias) * (len(ramp) - 1) + (bayer(x, y) - 0.5) * dither
    return ramp[max(0, min(len(ramp) - 1, int(round(level))))]


# ---------------------------------------------------------------- pose
@dataclass(frozen=True)
class Pose:
    dx: float = 0.0                 # mass offset (native px)
    dy: float = 0.0
    lean: float = 0.0               # head offset vs hips (+ = forward/right)
    sx: float = 1.0                 # squash / stretch around the hips
    sy: float = 1.0
    nod: float = 0.0                # head bow (rows the face drops forward)
    kneel: float = 0.0              # 0 standing .. 1 on her knees (mass sinks, tabard pools)
    ff: float = 57.0                # front boot x (on the floor)
    bf: float = 37.0                # back boot x
    fh: tuple = (60.0, 57.0)        # sword hand (cell coords)
    sword: float = -0.9             # blade direction (radians; 0 = right, -pi/2 = up)
    phase: float = 0.0              # cloth / hair wave
    hair_amp: float = 1.0
    hair_wind: float = 0.0          # + blown back (left), - whipped forward
    cape_wind: float = 0.0
    eye: str = "open"               # open | closed | wince | fierce
    flash: float = 0.0
    slash: float = 0.0
    slash_fade: float = 0.0
    ward: float = 0.0
    glow: float = 0.0
    sparkle: int = -1
    sparks: tuple = field(default_factory=tuple)


class Body:
    """Row geometry of one pose: centre line, extents and zones of the single mass."""

    def __init__(self, p: Pose) -> None:
        self.p = p
        self.hx = HIP[0] + p.dx
        self.hy = HIP[1] + p.dy + p.kneel * 12.0
        self.top = self.hy - BODY_H * p.sy
        # front shoulder (where the sword arm starts) and pieces the effects need
        self.fs = (self.center(18.5) + 2.6, self.y_of(18.5))

    def ly(self, y: float) -> float:
        """Cell row -> body row units (0 = top of the head, 36 = hips)."""
        return (y - self.top) / self.p.sy

    def y_of(self, ly: float) -> float:
        return self.top + ly * self.p.sy

    def center(self, ly: float) -> float:
        p = self.p
        if ly <= BODY_H:
            k = (BODY_H - ly) / BODY_H
            c = self.hx + p.lean * k ** 1.1
            if ly < 14:
                c += p.nod * 0.5
            return c
        t = (ly - BODY_H) / (HEM - BODY_H)
        return self.hx + 1.0 * t + 0.9 * math.sin(p.phase + t * 3) * t

    def extents(self, ly: float) -> tuple[float, float]:
        """(back, front) half-widths of the body proper at row ``ly``."""
        sx = self.p.sx
        if ly < 0:
            return (0.0, 0.0)
        if ly < 13.6:                                          # head
            k = (ly - 6.7) / 6.9
            half = 6.4 * math.sqrt(max(0.0, 1 - k * k))
            face = 0.0
            if 4.5 < ly < 12.8:
                face = 1.0 + 0.7 * math.exp(-((ly - 8.3) / 0.9) ** 2) - max(0.0, ly - 11.0) * 0.6
            return (half + 0.6, half + face)
        if ly < 16.0:                                          # neck
            return (2.5, 2.1)
        if ly < 21.0:                                          # shoulders
            k = (ly - 16.0) / 5.0
            return ((2.6 + 3.6 * math.sin(k * math.pi / 2)) * sx, (2.3 + 4.1 * math.sin(k * math.pi / 2)) * sx)
        if ly < 34.0:                                          # breastplate
            k = (ly - 21.0) / 13.0
            return ((6.2 - 1.6 * k) * sx, (6.4 + 0.5 * math.exp(-((k - 0.15) / 0.2) ** 2) - 1.6 * k) * sx)
        if ly < BODY_H:                                        # belt
            return (4.6 * sx, 4.9 * sx)
        t = (ly - BODY_H) / (HEM - BODY_H)                     # tabard
        pool = self.p.kneel * 3.0 * t
        return ((5.0 + 4.0 * t + pool) * sx, (5.4 + 5.0 * t ** 1.1 + pool) * sx)

    def hem_cut(self, u: float) -> float:
        """Ragged tabard hem (row units) for a position ``u`` across it."""
        p = self.p
        cut = HEM + 0.5 * math.sin(u * 7 + 0.5 + p.phase)
        if abs(math.sin(u * 5.2)) < 0.15:
            cut -= 1.2                                        # slits between panels
        return cut

    def ponytail(self, ly: float):
        """(centre, half-width) of the ponytail hanging down the back, or None."""
        p = self.p
        if not 4.0 <= ly <= 33.0:
            return None
        k = (ly - 4.0) / 29.0
        c = self.center(ly) - self.extents(ly)[0] - 0.4 - 1.6 * k
        c -= p.hair_wind * 7.0 * k ** 1.2
        c += p.hair_amp * 1.3 * math.sin(p.phase - ly * 0.2) * k
        w = 3.0 * (1 - k) ** 0.7 + 0.6
        return c, w

    def cape_back(self, ly: float):
        """Back edge of the cape at row ``ly``, or None above the shoulders / below the hem."""
        p = self.p
        if ly < 16.5:
            return None
        k = (ly - 16.5) / 42.0
        y = self.y_of(ly)
        if y > GROUND - 13 - 1.5 * math.sin(ly * 0.7 + p.phase) or k > 1.12:   # hem above the boots
            return None
        back = self.center(min(ly, BODY_H)) - self.extents(min(ly, 33.0))[0] - 1.0
        return back - 10.5 * k ** 0.8 - p.cape_wind * 6.0 * k - 1.3 * math.sin(p.phase + ly * 0.13) * k


def body_mass(cv, b: Body) -> tuple:
    """Scan the whole figure row by row and paint every zone. Returns the eye position."""
    p = b.p
    eye_ly, eye_dx = 8.0, 3.4
    for y in range(CELL):
        ly = b.ly(y + 0.5)
        if ly < -0.5:
            continue
        upper = ly <= HEM + 1.5 and y <= GROUND
        c = b.center(ly) if upper else 0.0
        wb, wf = b.extents(ly) if upper else (0.0, 0.0)
        pony = b.ponytail(ly) if upper else None
        cape = b.cape_back(ly)
        legs = _leg_spans(b, y)
        x0 = int(min([c - wb - 1] + ([pony[0] - pony[1] - 1] if pony else []) + ([cape - 1] if cape else [])
                     + [s[0] - 1 for s in legs] or [0]))
        x1 = int(max([c + wf + 2] + [s[1] + 2 for s in legs]))
        for x in range(max(0, x0), min(CELL, x1 + 1)):
            px = x + 0.5
            col = None
            d = px - c
            if upper and -wb <= d <= wf and (ly <= BODY_H or ly <= b.hem_cut(d / max(1.0, wf if d > 0 else wb))):
                col = _body_colour(b, x, y, ly, d, wb, wf)
            if col is None:
                for (s0, s1, back, top_y) in legs:
                    if s0 <= px <= s1:
                        col = _leg_colour(b, x, y, (px - s0) / max(1.0, s1 - s0), back, top_y)
                        break
            if col is None and pony and abs(px - pony[0]) <= pony[1]:
                u = (px - pony[0]) / pony[1]
                light = 0.62 - 0.32 * u - 0.15 * (ly - 4) / 29
                col = tone(HAIR, light, x, y)
                if abs(u + 0.35) < 0.2 and int(ly * 0.8) % 3:
                    col = HAIR[5] if ly < 18 else HAIR[4]           # glossy strands
            cape_front = (c - wb + 3) if upper else (b.hx - 2)
            if col is None and cape is not None and cape <= px <= cape_front:
                s = (px - cape) / max(1.0, cape_front - cape)
                k = (ly - 16.5) / 42.0
                fold = math.cos(s * 9 + k * 2.5 + 0.5 * math.sin(p.phase))
                light = 0.6 - 0.3 * k + 0.16 * fold - 0.22 * s + (0.15 if s < 0.12 else 0)
                col = tone(CAPE, light, x, y)
            if col is not None:
                cv.put(x, y, col)
    return (b.center(eye_ly) + eye_dx + p.nod * 0.4, b.y_of(eye_ly) + p.nod * 0.5)


def _body_colour(b: Body, x: int, y: int, ly: float, d: float, wb: float, wf: float):
    p = b.p
    u = d / max(1.0, wf if d > 0 else wb)
    if ly < 13.6:                                              # head: hair with the face in front
        bang = 4.6 + 0.8 * math.sin(d * 1.7 + 0.4) - (0.7 if d > 4.0 else 0.0)
        face = d > -0.2 and ly > bang + p.nod * 0.3 and ly < 13.0
        if face:
            light = 0.78 - 0.25 * (d - 2) / 4 - 0.25 * max(0.0, ly - 9) / 4
            return tone(SKIN, light, x, y, 0.45)
        light = 0.72 - 0.32 * u - 0.35 * ly / 13 + (0.15 if ly < 3 and u < 0 else 0)
        col = tone(HAIR, light, x, y)
        if hash01(int(d * 2 + 20), int(ly * 0.8), 2) > 0.82 and ly < 9:
            col = HAIR[min(5, HAIR.index(col) + 1)]
        if abs(ly - (3.9 + 0.1 * d)) < 0.55 and -5 < d < 4:
            col = GOLD[3] if abs(d - 1.5) < 0.6 else GOLD[2]          # circlet
            if abs(d - 1.6) < 0.5:
                col = (90, 210, 170)                                   # gem
        return col
    if ly < 16.0:                                              # neck + gorget
        if ly > 15.0:
            return LEATHER[1] if u > 0 else LEATHER[2]
        return tone(SKIN, 0.55 - 0.3 * u, x, y, 0.4)
    if ly < BODY_H:                                            # armour
        k = (ly - 16.0) / (BODY_H - 16.0)
        light = 0.6 - 0.34 * u - 0.28 * k + (0.18 if u < -0.8 else 0)
        if 0.18 < u < 0.42 and 0.15 < k < 0.85:
            light += 0.22                                      # specular streak on the plate
        if ly < 21.0 and abs(ly - 20.4) < 0.5:
            return GOLD[2] if u < 0.3 else GOLD[1]             # pauldron rim
        if abs(ly - 21.6) < 0.5 and abs(u) < 0.6:
            return GOLD[3] if u < 0 else GOLD[2]               # neckline
        if ly >= 34.0:
            if 0.45 < u < 0.85 and 34.3 < ly < 35.7:
                return GOLD[3]                                 # buckle
            return tone(LEATHER, 0.62 - 0.3 * u, x, y)
        if abs(u - 0.55) < 0.07 and 22 < ly < 33:
            return STEEL[2]                                    # centre ridge
        return tone(STEEL, light, x, y)
    t = (ly - BODY_H) / (HEM - BODY_H)                         # tabard
    if ly > b.hem_cut(u) - 1.0:
        return GOLD[2] if (x % 3) else GOLD[3]
    if abs(ly - (BODY_H + 5.5)) < 1.6 and abs(d - 2.6) < 1.6 and abs(ly - (BODY_H + 5.5)) + abs(d - 2.6) < 1.7:
        return GOLD[3] if abs(d - 2.6) < 0.5 else GOLD[2]     # emblem
    fold = math.cos(u * 7.5 + t * 2 + 0.4 * math.sin(p.phase))
    light = 0.62 - 0.3 * u - 0.28 * t + 0.14 * fold
    if abs(math.sin(u * 5.2)) < 0.12 and t > 0.3:
        light -= 0.3
    return tone(CLOTH, light, x, y)


def _leg_spans(b: Body, y: int):
    """Spans of the boots/greaves on row ``y`` (anchored to the floor, below the tabard)."""
    p = b.p
    if p.kneel > 0.5 or y > GROUND:
        return []
    hem_y = b.y_of(HEM) - 2
    if y < hem_y:
        return []
    spans = []
    for foot, back, ref in ((p.bf, True, HIP[0] - 2.5), (p.ff, False, HIP[0] + 2.5)):
        k = (GROUND - 2 - y) / (GROUND - 2 - HIP[1])
        c = foot + (ref - foot) * max(0.0, k)
        boot = y >= GROUND - 9
        w = 3.0 if boot else 2.6 + 0.3 * math.sin(max(0.0, min(1.0, (GROUND - 9 - y) / 8)) * math.pi)
        x0, x1 = c - w, c + w
        if y >= GROUND - 3:
            x1 += 3.2 * (y - (GROUND - 4)) / 4 + 1.0                # toe
        spans.append((x0, x1, back, hem_y))
    spans.reverse()                                                 # front leg wins
    return spans


def _leg_colour(b: Body, x: int, y: int, s: float, back: bool, top_y: float):
    u = s * 2 - 1
    bias = -0.18 if back else 0.0
    if y >= GROUND:
        return LEATHER[0]                                           # sole
    if y >= GROUND - 9:
        if y == GROUND - 9:
            return GOLD[2] if u < 0.3 else GOLD[1]                  # boot cuff
        return tone(LEATHER, 0.62 - 0.3 * u + bias, x, y)
    return tone(STEEL, 0.56 - 0.34 * u + bias, x, y)


def arm_part(b: Body) -> dict:
    """The sword arm: one sweep shoulder -> hand (like the Espectro's front sleeve)."""
    part: dict = {}
    shoulder, hand = b.fs, b.p.fh
    mid = lerp(shoulder, hand, 0.5)
    d = norm(sub(hand, shoulder))
    elbow = add(mid, add(mul((-d[1], d[0]), 2.0), (0.0, 1.5)))
    pts = bezier(shoulder, through(shoulder, elbow, hand), hand, 14)

    def width(t):
        w = 2.6 - 0.4 * t + 1.8 * math.exp(-(t / 0.16) ** 2) + 0.25 * math.exp(-((t - 0.72) / 0.1) ** 2)
        return (w, w)

    def paint(t, u, x, y, nx, ny):
        if 0.86 < t < 0.9:
            return GOLD[2]
        sx, sy = nx * u, ny * u
        nz = math.sqrt(max(0.0, 1 - u * u))
        lam = max(0.0, sx * LIGHT[0] + sy * LIGHT[1] + nz * LIGHT[2])
        return tone(STEEL, 0.06 + 0.82 * lam + (0.08 if t < 0.2 else 0.0) - (0.12 if t > 0.9 else 0.0), x, y, 0.5)

    sweep(part, pts, width, paint)
    return part


def sword_part(r: Body) -> tuple[dict, tuple]:
    p = r.p
    part: dict = {}
    g = p.fh
    d = (math.cos(p.sword), math.sin(p.sword))
    n = (-d[1], d[0])
    # blade
    a, b = add(g, mul(d, 3.0)), add(g, mul(d, 26.0))
    x0, y0, x1, y1 = bbox((a, b), 2)
    L = 23.0
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            q = sub((x + 0.5, y + 0.5), a)
            t = (q[0] * d[0] + q[1] * d[1]) / L
            if t < 0 or t > 1:
                continue
            s = q[0] * n[0] + q[1] * n[1]
            w = 1.45 * (1.0 if t < 0.82 else max(0.0, 1 - (t - 0.82) / 0.18))
            if abs(s) > w + 0.05:
                continue
            up = s * (n[0] * LIGHT[0] + n[1] * LIGHT[1])     # side facing the light
            idx = 3 if up > 0.5 else 2 if up > -0.2 else 1
            if abs(s) < 0.35 and 0.08 < t < 0.7:
                idx = 1                                      # fuller
            col = BLADE[idx]
            if p.glow > 0:
                col = mix(col, GOLD[3], 0.35 + 0.4 * p.glow)
            part[(x, y)] = col
    # crossguard, grip, pommel
    cg = add(g, mul(d, 2.2))
    for k in range(-4, 5):
        q = add(cg, mul(n, k * 0.9))
        part[(int(round(q[0])), int(round(q[1])))] = GOLD[3] if k < 0 else GOLD[2]
    for k in range(0, 4):
        q = add(g, mul(d, -k * 0.9 + 1.0))
        part[(int(round(q[0])), int(round(q[1])))] = LEATHER[2 if k % 2 else 1]
    pm = add(g, mul(d, -3.4))
    for dx, dy in ((0, 0), (1, 0), (0, 1), (1, 1)):
        part[(int(pm[0]) + dx, int(pm[1]) + dy)] = GOLD[3] if (dx, dy) == (0, 0) else GOLD[1]
    return part, b


# ---------------------------------------------------------------- effects
def draw_slash(cv: Canvas, r: Body, prog: float, fade: float) -> None:
    """Warm crescent of the overhead swing, from behind the head over to the front-low side."""
    if prog <= 0:
        return
    c = add(r.fs, (2.0, 4.0))
    a0, a1 = -2.5, 0.75
    a_end = a0 + (a1 - a0) * min(1.0, prog)
    steps = 140
    for line, (rad, thick) in enumerate(((22.0, 1), (25.0, 2), (28.0, 1))):
        for i in range(steps):
            t = i / (steps - 1)
            w = t - fade * 1.15
            if w <= 0:
                continue
            a = a0 + (a_end - a0) * t
            rr = rad + 1.2 * math.sin(t * math.pi)
            x = c[0] + math.cos(a) * rr * 1.08
            y = c[1] + math.sin(a) * rr
            lv = 3 if w > 0.75 else 2 if w > 0.42 else 1 if w > 0.15 else 0
            alpha = int(255 * min(1.0, 0.25 + w * 1.1))
            for k in range(thick if w > 0.3 else 1):
                cv.put(int(x), int(y) + k, WARM[lv], solid=False, alpha=alpha)


def draw_ward(cv: Canvas, r: Body, k: float) -> None:
    """Blue protective crescent in front of the raised blade."""
    if k <= 0:
        return
    cx, cy = r.p.fh[0] + 7, r.p.fh[1] - 2
    rx, ry = 6.0, 19.0 * min(1.0, 0.5 + k)
    for y in range(int(cy - ry) - 1, int(cy + ry) + 2):
        for x in range(int(cx - 2), int(cx + rx) + 2):
            dx, dy = (x + 0.5 - cx) / rx, (y + 0.5 - cy) / ry
            d = dx * dx + dy * dy
            if dx < 0 or d > 1.0 or d < 0.55:
                continue
            edge = d > 0.85
            hexed = (x + y * 2) % 5 == 0 or (x * 2 - y) % 7 == 0
            lv = 3 if edge else 2 if hexed else 1
            cv.put(x, y, WARD[lv], solid=False, alpha=int(255 * min(1.0, k) * (0.95 if edge else 0.6)))


def draw_sparkles(cv: Canvas, seed: int, center, radius: float, count: int, ramp) -> None:
    for j in range(count):
        a = hash01(j, seed, 1) * math.tau
        d = radius * (0.3 + 0.7 * hash01(seed, j, 2))
        x, y = int(center[0] + math.cos(a) * d), int(center[1] + math.sin(a) * d)
        lv = 3 if hash01(j, seed, 3) > 0.6 else 2
        cv.put(x, y, ramp[lv], solid=False)
        if lv == 3:
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                cv.put(x + dx, y + dy, ramp[1], solid=False, alpha=170)


def outline(cv: Canvas) -> None:
    add_ = []
    for y in range(cv.size):
        for x in range(cv.size):
            if cv.px[y][x] is not None:
                continue
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nx, ny = x + dx, y + dy
                if 0 <= nx < cv.size and 0 <= ny < cv.size and cv.solid[ny][nx]:
                    add_.append((x, y))
                    break
    for x, y in add_:
        cv.px[y][x] = (*OUTLINE, 255)


def render(p: Pose) -> Canvas:
    cv = Canvas()
    b = Body(p)
    eye = body_mass(cv, b)
    _face_details(cv, b, eye)
    sword, tip = sword_part(b)
    cv.stamp(sword, rim=True)
    cv.stamp(arm_part(b), rim=True)            # like the Espectro's front sleeve
    outline(cv)
    if p.glow > 0:
        mid = add(p.fh, mul((math.cos(p.sword), math.sin(p.sword)), 15))
        cv.glow(mid[0], mid[1], 9 + 6 * p.glow, GOLD[2], 0.5 * p.glow)
        cv.glow(tip[0], tip[1], 5 + 3 * p.glow, GOLD[3], 0.7 * p.glow)
    if p.sparkle >= 0:
        draw_sparkles(cv, p.sparkle, tip, 11, 10, WARM)
        draw_sparkles(cv, p.sparkle + 50, (b.hx, b.hy - 14), 18, 8, WARM)
    draw_ward(cv, b, p.ward)
    draw_slash(cv, b, p.slash, p.slash_fade)
    for (x, y, lv) in p.sparks:
        cv.put(int(x), int(y), WARM[lv], solid=False)
    if p.flash > 0:
        for y in range(CELL):
            for x in range(CELL):
                c = cv.px[y][x]
                if c is not None and cv.solid[y][x]:
                    cv.px[y][x] = (*mix(c[:3], WHITE, p.flash), c[3])
    return cv


def _face_details(cv: Canvas, b: Body, eye) -> None:
    """Eye (white, pupil, green iris), brow, mouth and blush painted onto the mass."""
    p = b.p
    ex, ey = int(eye[0]), int(eye[1])
    if p.eye in ("open", "fierce"):
        cv.put(ex, ey, (36, 22, 34))
        cv.put(ex, ey + 1, IRIS)
        cv.put(ex - 1, ey, (238, 230, 226))
        by = ey - 2 if p.eye == "open" else ey - 1
        cv.put(ex - 1, by, BROW)
        cv.put(ex, by, BROW)
    else:
        cv.put(ex - 1, ey + 1, SKIN[0])
        cv.put(ex, ey + 1, SKIN[0])
        if p.eye == "wince":
            cv.put(ex - 1, ey - 1, BROW)
            cv.put(ex, ey, BROW)
    cv.put(ex, ey + 4, SKIN[0] if p.eye != "wince" else (90, 30, 40))     # mouth
    cv.put(ex - 2, ey + 2, (226, 124, 106))                                # blush


# ---------------------------------------------------------------- animations
IDLE_FRAMES = 16


def idle_pose(i: int, n: int = IDLE_FRAMES) -> Pose:
    a = math.tau * (i % n) / n
    bob = round(0.62 * (1 - math.cos(a)))                    # hips: 0 or 1 px
    lean = round(0.62 * (1 - math.cos(a - 0.7))) * -0.6      # chest settles a beat later
    return Pose(dy=bob, lean=lean, fh=(60.0, 57.0 + bob), sword=-0.9 + 0.03 * math.sin(a),
                phase=a, eye="closed" if i % n == 10 else "open")


def idle_frames():
    return [(idle_pose(i), 100) for i in range(IDLE_FRAMES)]


def _spark_ring(cx, cy, seed, n=12, r=7.0):
    return tuple((cx + math.cos(hash01(j, seed) * math.tau) * r * (0.4 + 0.6 * hash01(seed, j)),
                  cy + math.sin(hash01(j, seed) * math.tau) * r * (0.4 + 0.6 * hash01(seed, j)),
                  1 + int(hash01(j, j, seed) * 3)) for j in range(n))


def attack_frames():
    b = idle_pose(0)
    return [
        (replace(b, dx=-2, lean=-3, sy=0.98, fh=(46, 33), sword=-2.4, hair_wind=0.3, cape_wind=0.2,
                 eye="fierce", phase=0.4), 90),
        (replace(b, dx=-3, lean=-5, sy=0.96, fh=(42, 29), sword=-2.85, hair_wind=0.45, cape_wind=0.3,
                 eye="fierce", phase=0.8), 100),
        (replace(b, dx=5, lean=5, sx=1.04, sy=1.02, ff=65, fh=(66, 36), sword=-0.7, hair_wind=0.9,
                 cape_wind=0.9, eye="fierce", slash=0.55, phase=1.4), 50),
        (replace(b, dx=8, lean=7, sx=1.05, ff=66, fh=(70, 53), sword=0.45, hair_wind=1.0, cape_wind=1.0,
                 eye="fierce", slash=1.0, phase=2.0, sparks=_spark_ring(89, 64, 4)), 55),
        (replace(b, dx=8, lean=6, ff=66, fh=(70, 55), sword=0.5, hair_wind=0.7, cape_wind=0.8, eye="fierce",
                 slash=1.0, slash_fade=0.5, phase=2.6, sparks=_spark_ring(89, 65, 9, 7, 10)), 70),
        (replace(b, dx=5, lean=4, ff=64, fh=(67, 56), sword=0.2, hair_wind=0.4, cape_wind=0.5, slash=1.0,
                 slash_fade=1.0, phase=3.3), 80),
        (replace(b, dx=2, lean=2, ff=60, fh=(63, 57), sword=-0.45, hair_wind=0.15, cape_wind=0.2,
                 phase=4.2), 90),
        (replace(b, dx=0.5, lean=0.5, ff=58, fh=(61, 57), sword=-0.8, phase=5.2), 90),
        (b, 100),
    ]


def guard_frames():
    b = idle_pose(0)
    return [
        (replace(b, dx=-1, lean=-2, sy=0.98, fh=(58, 44), sword=-1.45, ward=0.4, hair_wind=0.2,
                 eye="fierce", phase=0.5), 60),
        (replace(b, dx=-2, lean=-3, sy=0.95, dy=1, fh=(59, 44), sword=-1.52, ward=1.0, hair_wind=0.3,
                 cape_wind=0.2, eye="fierce", phase=1.1), 80),
        (replace(b, dx=-2, lean=-3, sy=0.95, dy=1, fh=(59, 44), sword=-1.52, ward=0.9, hair_wind=0.2,
                 eye="fierce", phase=1.8), 90),
        (replace(b, dx=-2, lean=-2, sy=0.96, dy=1, fh=(59, 45), sword=-1.5, ward=0.6, phase=2.6), 90),
        (replace(b, dx=-1, lean=-1, sy=0.98, fh=(60, 50), sword=-1.25, ward=0.25, phase=3.6), 80),
        (replace(b, fh=(60, 55), sword=-1.0, phase=4.8), 80),
        (b, 70),
    ]


def hurt_frames():
    b = idle_pose(0)
    return [
        (replace(b, dx=-3, lean=-5, sx=0.95, fh=(55, 55), sword=-0.55, hair_wind=-0.7, cape_wind=-0.5,
                 eye="wince", flash=0.82, phase=1.0), 55),
        (replace(b, dx=-4, lean=-4, fh=(54, 56), sword=-0.6, hair_wind=-0.8, cape_wind=-0.6, eye="wince",
                 flash=0.4, phase=1.6), 65),
        (replace(b, dx=-3, lean=-2, fh=(56, 57), sword=-0.7, hair_wind=-0.3, cape_wind=-0.3, eye="wince",
                 flash=0.12, phase=2.4), 75),
        (replace(b, dx=-1, lean=-1, fh=(59, 57), sword=-0.8, hair_wind=0.1, phase=3.4), 85),
        (replace(b, dx=-0.5, fh=(60, 57), sword=-0.85, phase=4.6), 90),
        (b, 100),
    ]


def cast_frames():
    b = idle_pose(0)
    return [
        (replace(b, fh=(57, 43), sword=-1.3, glow=0.3, eye="fierce", phase=0.5), 80),
        (replace(b, sy=1.02, lean=-1, fh=(54, 28), sword=-1.57, glow=0.7, sparkle=1, hair_wind=0.2,
                 cape_wind=0.2, eye="fierce", phase=1.2), 90),
        (replace(b, sy=1.03, lean=-1, fh=(54, 27), sword=-1.57, glow=1.0, sparkle=2, hair_wind=0.3,
                 cape_wind=0.3, eye="fierce", phase=2.0), 100),
        (replace(b, sy=1.02, lean=-1, fh=(54, 27), sword=-1.57, glow=1.0, sparkle=3, hair_wind=0.25,
                 cape_wind=0.25, eye="fierce", phase=2.8), 100),
        (replace(b, fh=(56, 37), sword=-1.35, glow=0.6, sparkle=4, phase=3.7), 90),
        (replace(b, fh=(59, 50), sword=-1.05, glow=0.25, phase=4.7), 90),
        (b, 100),
    ]


def death_frames():
    b = idle_pose(0)
    return [
        (replace(b, dx=-3, lean=-5, sx=0.95, fh=(55, 55), sword=-0.5, hair_wind=-0.7, cape_wind=-0.5,
                 eye="wince", flash=0.8, phase=1.0), 70),
        (replace(b, dx=-1, lean=1, kneel=0.35, fh=(58, 68), sword=1.42, hair_wind=-0.3, eye="wince",
                 phase=1.8), 110),
        (replace(b, lean=3, nod=1.0, kneel=0.8, fh=(58, 70), sword=1.45, eye="closed", phase=2.6), 130),
        (replace(b, lean=5, nod=2.0, kneel=1.0, fh=(58, 71), sword=1.47, hair_wind=-0.2, eye="closed",
                 phase=3.4), 160),
        (replace(b, lean=6, nod=2.6, kneel=1.0, sy=0.98, fh=(58, 71), sword=1.48, hair_wind=-0.3,
                 hair_amp=0.4, eye="closed", phase=4.0), 220),
        (replace(b, lean=6, nod=2.6, kneel=1.0, sy=0.98, fh=(58, 71), sword=1.48, hair_wind=-0.3,
                 hair_amp=0.0, eye="closed", phase=4.4), 600),
    ]


ANIMATIONS = {
    "idle": (idle_frames, True),
    "attack": (attack_frames, False),
    "guard": (guard_frames, False),
    "hurt": (hurt_frames, False),
    "cast": (cast_frames, False),
    "death": (death_frames, False),
}
STRIKE_FRAME = 3          # attack frame where the blade connects (HeroFx cues)


# ---------------------------------------------------------------- output
def write_png(path: Path, rows) -> None:
    h, w = len(rows), len(rows[0])
    raw = bytearray()
    for row in rows:
        raw.append(0)
        for c in row:
            raw.extend(c if c is not None else (0, 0, 0, 0))

    def chunk(tag, data):
        c = struct.pack(">I", len(data)) + tag + data
        return c + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(bytes(raw), 9)) + chunk(b"IEND", b"")
    path.write_bytes(png)


def double(rows):
    out = []
    for row in rows:
        wide = [c for c in row for _ in (0, 1)]
        out.append(wide)
        out.append(list(wide))
    return out


def build():
    names = list(ANIMATIONS)
    frames = {n: ANIMATIONS[n][0]() for n in names}
    cols = max(len(f) for f in frames.values())
    sheet = [[None] * (CELL * cols) for _ in range(CELL * len(names))]
    meta = {"cell": CELL * 2, "columns": cols,
            "sheets": {str(CELL * 2): SHEET_PATH.name, str(CELL): SHEET_96_PATH.name},
            "source": "scripts/generate_warrior_code_sprites.py",
            "events": {"attack": {"strike_frame": STRIKE_FRAME}},
            "animations": {}}
    for row, name in enumerate(names):
        for col, (pose, _) in enumerate(frames[name]):
            cv = render(pose)
            for y in range(CELL):
                sheet[row * CELL + y][col * CELL:(col + 1) * CELL] = cv.px[y]
        meta["animations"][name] = {"row": row, "frames": len(frames[name]),
                                    "durations_ms": [ms for _, ms in frames[name]],
                                    "loop": ANIMATIONS[name][1]}
    return sheet, meta


def main() -> None:
    sheet, meta = build()
    write_png(SHEET_96_PATH, sheet)
    write_png(SHEET_PATH, double(sheet))
    META_PATH.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(f"wrote {SHEET_PATH.name} ({len(sheet[0]) * 2}x{len(sheet) * 2}), "
          f"{SHEET_96_PATH.name} and {META_PATH.name}")


if __name__ == "__main__":
    main()
