"""Draw and animate the enemy "Acólito de Ceniza" (Ash Acolyte). Stdlib only:

    python scripts/generate_enemy_acolyte.py

Same method as the Espectro (``docs/code-drawn-sprites.md``): one renderer, every
frame a ``Pose``. A hunched support cultist, grounded and earthy (fire and ash):

* ONE row-scanned mass from the tip of a tall pointed hood to a hem that sweeps the
  floor: charcoal robe with a draped cowl, a hunched back, a front slit showing the
  red-orange lining, a rope belt with a knot, prayer beads and a hanging book, a
  singed ragged hem. The hood opening (lined in red-orange) frames a white ceramic
  mask — cracked, with two narrow eye slits glowing ember-orange.
* Only the censer arm (bony hand, bell sleeve), its chain and the brass censer are
  drawn on top, rimmed where they cross the robe. The censer smokes and glows; its
  swing leaves a trail of pale smoke and drifting embers.

Animations (non-death actions end on idle frame 0):
  idle    12-frame loop: the censer swings like a pendulum, smoke trail, robe sway, embers
  attack  "Golpe de Incensario": winds the censer over the head, swings it in a big arc
          LEFT and hits ~55 px in front (ember spray), eased recovery
  cast    "Bendición de Ceniza": raises the censer with both hands, smoke billows into a
          ring of ash with ember runes above it, the mask eyes blaze
  hurt    white flash, staggers right, mask tilts, censer jerks, ash puff
  death   kneels, the mask cracks and falls, the robe crumbles to ash bottom-up, embers rise

Output: ``assets/enemies/acolyte_sheet.png`` + ``.json``.
"""
from __future__ import annotations

import math
import sys
from dataclasses import dataclass, field, replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from pixel_kit import (Canvas, bayer, bezier, build_sheet, dissolve, flash, hash01, lerp,  # noqa: E402
                       mix, outline, ramp, save_sheet, smooth, stroke)

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "assets" / "enemies"
SHEET_ID = "acolyte"

CELL_W, CELL_H = 144, 112
CX, GROUND = CELL_W - 48, 104         # robe centre at the hem, ground row
ANCHOR = (CX, GROUND + 2)
H = 76.0                              # hood tip above the ground
HOOD_H = 56.0                         # where the hood widens into the shoulders
BELT_H = 36.0
HUNCH = 7.0                           # the head juts forward (left) by this much

# ---------------------------------------------------------------- palette
OUTLINE = (20, 12, 16)
ROBE = [(22, 19, 28), (35, 31, 41), (50, 46, 55), (68, 63, 69), (90, 84, 86), (118, 110, 106),
        (150, 141, 132)]
LINING = [(58, 16, 16), (102, 30, 20), (148, 50, 24), (196, 84, 34), (234, 128, 58)]
ROPE = [(58, 42, 30), (98, 74, 46), (142, 112, 70), (184, 152, 102)]
MASK = [(74, 70, 82), (124, 120, 128), (176, 172, 170), (220, 214, 204), (246, 242, 230)]
BRASS = [(52, 32, 20), (96, 62, 28), (148, 102, 40), (200, 152, 62), (242, 210, 124)]
EMBER = [(112, 30, 12), (200, 70, 18), (250, 140, 40), (255, 212, 118), (255, 250, 222)]
SMOKE = [(66, 63, 70), (104, 100, 104), (146, 142, 140), (190, 186, 180)]
SKIN = [(64, 52, 52), (110, 96, 88), (158, 144, 128), (204, 192, 172)]
WOOD = [(52, 30, 24), (96, 58, 36), (140, 92, 56)]
LEATHER = [(40, 20, 20), (76, 36, 28), (116, 58, 38)]
VOID = (14, 8, 10)
SINGE = (64, 34, 24)
WHITE = (255, 255, 255)

# rune glyphs (3x3) for the blessing ring
GLYPHS = [((0, 0), (1, 0), (2, 0), (1, 1), (1, 2)), ((0, 0), (0, 1), (0, 2), (1, 1), (2, 0), (2, 2)),
          ((1, 0), (0, 1), (2, 1), (1, 2)), ((0, 0), (2, 0), (1, 1), (0, 2), (2, 2)),
          ((0, 2), (1, 2), (2, 2), (1, 1), (1, 0)), ((0, 0), (1, 1), (2, 2), (2, 0))]


@dataclass(frozen=True)
class Pose:
    dx: float = 0.0
    dy: float = 0.0
    lean: float = 0.0             # hood offset vs the hem (negative = towards the hero)
    sx: float = 1.0
    sy: float = 1.0
    kneel: float = 0.0            # death: the mass sinks and the hem pools
    phase: float = 0.0            # robe wave
    sway: float = 1.0
    hand: tuple[float, float] = (-21.0, 43.0)      # censer hand (rel. CX, height above ground)
    hand_b: tuple[float, float] = (12.0, 36.0)     # second hand (only drawn when ``both``)
    both: float = 0.0             # >0.5: both hands hold the chain (cast)
    swing: float = 0.0            # censer angle: 0 hangs down, + to the right, 3pi/2 = left
    chain: float = 13.0           # chain length
    behind: bool = False          # censer passes behind the body (wind-up)
    glow: float = 1.0             # embers inside the censer
    eye: float = 1.0              # mask eye slits
    mask_tilt: float = 0.0
    crack: float = 0.0            # extra cracks (death)
    mask_drop: float = 0.0        # 0 on the face .. 1 lying on the floor
    flash: float = 0.0
    dissolve: float = 0.0
    trail: tuple = field(default_factory=tuple)   # earlier censer centres (newest first)
    smoke: float = 1.0            # smoke density
    embers: float = 1.0           # ember motes rising from the censer
    arc: tuple = field(default_factory=tuple)     # swoosh (a0, a1, fade)
    impact: tuple = field(default_factory=tuple)  # (x, y) where the censer hits
    sparks: float = 0.0           # ember spray progress
    ring: float = 0.0             # blessing ring above (cast)
    ash: float = 0.0              # hurt ash puff progress
    motes: tuple = field(default_factory=tuple)   # baked (x, y, kind) 0-2 ash, 3-4 ember


# ---------------------------------------------------------------- body frame
class Body:
    def __init__(self, p: Pose) -> None:
        self.p = p
        self.sy = p.sy * (1 - 0.3 * p.kneel)

    def center(self, h: float) -> float:
        p = self.p
        k = max(0.0, min(1.0, h / H))
        hunch = -HUNCH * (1 + 0.6 * p.kneel) * smooth((h - 38) / 36)
        wave = p.sway * 1.2 * math.sin(p.phase + h * 0.09) * max(0.0, 1 - h / 36) ** 1.5
        return CX + p.dx + p.lean * k ** 1.3 + hunch + wave

    def y_of(self, h: float) -> float:
        return GROUND + self.p.dy - h * self.sy

    def h_of(self, y: float) -> float:
        return (GROUND + self.p.dy - y) / self.sy

    def to_cell(self, u_px: float, h: float) -> tuple[float, float]:
        return self.center(h) + u_px * self.p.sx, self.y_of(h)


def extents(h: float, kneel: float) -> tuple[float, float, float] | None:
    """(front, back, offset) of the mass at height ``h``: front = towards the hero (left)."""
    if h > H or h < -0.6:
        return None
    if h >= HOOD_H:                                  # tall pointed hood, tip droops back
        k = (H - h) / (H - HOOD_H)
        return 0.6 + 11.6 * k ** 0.68, 0.6 + 12.0 * k ** 0.6, 5.0 * (1 - k) ** 2
    if h >= 46:                                      # shoulders, hunched back
        s = smooth((HOOD_H - h) / 10)
        hump = 1.6 * math.sin(min(1.0, (HOOD_H - h) / 8) * math.pi)
        return 12.2 + 1.8 * s, 12.6 + 5.4 * s + hump, 0.0
    if h >= 32:                                      # torso, drawn in at the belt
        s = (46 - h) / 14
        return 14.0 - 1.3 * math.sin(s * math.pi), 17.2 - 2.6 * s, 0.0
    s = (32 - h) / 32                                # flaring skirt that pools on the floor
    widen = 1 + 0.38 * kneel * s
    pool = 1.5 if h < 1.5 else 0.0
    return (13.2 + 7.0 * s ** 1.2) * widen + pool, (14.6 + 6.6 * s ** 1.2) * widen + pool, 0.0


def cowl_edge(u: float) -> float:
    return 47.5 + 1.8 * math.sin(u * 4.6 + 0.8) - 1.6 * u * u + 0.8 * hash01(int(u * 7 + 20), 3)


# ---------------------------------------------------------------- the mass
def draw_mass(cv: Canvas, b: Body) -> None:
    p = b.p
    for y in range(CELL_H):
        h = b.h_of(y + 0.5)
        ext = extents(h, p.kneel)
        if ext is None:
            continue
        front, back, off = ext
        c = b.center(h) + off
        f, bk = front * p.sx, back * p.sx
        v = 1 - max(0.0, h) / H
        for x in range(int(c - f) - 1, int(c + bk) + 2):
            dxp = x + 0.5 - c
            if dxp < -f or dxp > bk:
                continue
            u = dxp / max(1.0, f if dxp < 0 else bk)
            # ragged hem: groups of columns lifted off the floor, a singed band
            if h < 4:
                key = int(math.floor((x + 0.5 - b.center(0)) / 2.2))
                lift = 2.6 * hash01(key, 7) ** 2
                if h < lift - 0.6:
                    continue
            if h >= HOOD_H - 2 or h >= cowl_edge(u):
                # hood and the cowl draped over the shoulders
                light = 0.74 - 0.42 * u - 0.12 * (1 - min(1.0, (h - 46) / 30))
                if abs(u) > 0.84:
                    light -= 0.14
                if u < -0.7 and h > 50:
                    light += 0.16
                light += 0.06 * math.cos(u * 5 + h * 0.35)
                col = ramp(ROBE, max(0.0, min(1.0, light)), x, y)
            elif h >= cowl_edge(u) - 1.3:
                col = ROBE[0]                            # cowl casts a shadow
            else:
                light = 0.6 - 0.36 * u - 0.36 * v
                light += 0.12 * math.cos(u * 8.0 + h * 0.06 + 0.3 * math.sin(p.phase))
                if abs(u) > 0.86:
                    light -= 0.14
                if u < -0.78 and h > 26:
                    light += 0.16
                col = ramp(ROBE, max(0.0, min(1.0, light)), x, y)
                # front slit of the robe showing the red-orange lining
                if h < BELT_H - 1:
                    k = 1 - h / (BELT_H - 1)
                    us = -0.36 + 0.05 * math.sin(p.phase + h * 0.1) * k
                    hw = 0.03 + 0.13 * k ** 0.9
                    du = u - us
                    if abs(du) < hw:
                        depth = abs(du) / hw
                        col = ramp(LINING, max(0.0, min(1.0, 0.62 - 0.4 * depth - 0.3 * v
                                                        - 0.2 * (du > 0))), x, y, 0.45)
                    elif 0 < du < hw + 0.07:
                        col = ROBE[0]
                # singed hem
                if h < 3.5:
                    col = mix(col, SINGE, 0.45)
                    if h < 1.6 and hash01(x, 3, 11) > 0.93:
                        col = EMBER[1] if math.sin(p.phase + x) > 0 else EMBER[0]
            cv.put(x, y, col)


def draw_belt(cv: Canvas, b: Body) -> tuple[float, float]:
    """Rope belt with a knot at the front and two hanging ends. Returns the knot point."""
    p = b.p
    for y in range(CELL_H):
        h = b.h_of(y + 0.5)
        if not (BELT_H - 1.4 <= h <= BELT_H + 1.2):
            continue
        for x in range(CELL_W):
            if cv.get(x, y) is None:
                continue
            c = b.center(h)
            ext = extents(h, p.kneel)
            if ext is None:
                continue
            dxp = x + 0.5 - c
            u = dxp / max(1.0, (ext[0] if dxp < 0 else ext[1]) * p.sx)
            if abs(u) > 1.05:
                continue
            twist = (x + int(h * 2)) % 3
            light = 0.75 - 0.4 * u - 0.15 * twist + (0.2 if h > BELT_H else 0)
            cv.put(x, y, ramp(ROPE, max(0.0, min(1.0, light)), x, y, 0.3))
    kx, ky = b.to_cell(-0.62 * 13.0, BELT_H)
    for ox, oy, lv in ((-1, -1, 3), (0, -1, 2), (1, -1, 2), (-1, 0, 2), (0, 0, 3), (1, 0, 1),
                       (-1, 1, 1), (0, 1, 2), (1, 1, 1)):
        cv.put(int(kx) + ox, int(ky) + oy, ROPE[lv])
    for k, (ln, ox) in enumerate(((11, -1), (14, 1))):        # hanging rope ends
        for s in range(ln):
            t = s / ln
            sway = 1.2 * math.sin(p.phase - 0.8 - k) * t * t * p.sway
            x, y = kx + ox + sway - 0.25 * s * (k == 0), ky + 2 + s
            col = ROPE[2] if s % 3 else ROPE[1]
            if s >= ln - 2:
                col = ROPE[3] if s == ln - 1 else ROPE[2]
            cv.put(int(x), int(y), col)
            cv.put(int(x) + 1, int(y), ROPE[1] if s < ln - 2 else ROPE[2])
    return kx, ky


def draw_beads(cv: Canvas, b: Body) -> None:
    """Prayer beads looped from the belt across the front, with a brass charm."""
    p = b.p
    ax, ay = b.to_cell(-0.18 * 14, BELT_H - 1)
    bx, by = b.to_cell(0.32 * 15, BELT_H - 1)
    sag = 7.0 + 0.6 * math.sin(p.phase)
    n = 9
    low = (0.0, 0.0)
    for i in range(n + 1):
        t = i / n
        x = ax + (bx - ax) * t + 0.8 * math.sin(p.phase - 0.5) * math.sin(t * math.pi)
        y = ay + (by - ay) * t + sag * math.sin(t * math.pi)
        if i == n // 2:
            low = (x, y)
        if i % 2 == 0:
            cv.put(int(x), int(y), WOOD[2])
            cv.put(int(x) + 1, int(y), WOOD[1])
            cv.put(int(x), int(y) + 1, WOOD[0])
        else:
            cv.put(int(x), int(y), WOOD[1])
    cx, cy = low[0], low[1] + 2                               # brass charm
    for ox, oy, c in ((0, 0, BRASS[2]), (0, 1, BRASS[4]), (-1, 1, BRASS[3]), (1, 1, BRASS[1]),
                      (0, 2, BRASS[1])):
        cv.put(int(cx) + ox, int(cy) + oy, c)


def draw_book(cv: Canvas, b: Body) -> None:
    """A small prayer book hanging from the belt on the back hip."""
    p = b.p
    sw = round(0.6 * math.sin(p.phase - 1.2) * p.sway)
    x0, y0 = b.to_cell(0.6 * 15, BELT_H - 2)
    x0, y0 = int(x0) + sw, int(y0)
    cv.put(x0 + 1, y0 - 1, LEATHER[0])
    cv.put(x0 + 1, y0, LEATHER[0])
    for yy in range(y0 + 1, y0 + 8):
        for xx in range(x0 - 1, x0 + 4):
            edge = xx in (x0 - 1, x0 + 3) or yy in (y0 + 1, y0 + 7)
            lv = 2 if (xx == x0 - 1 or yy == y0 + 1) else 0 if edge else 1
            cv.put(xx, yy, LEATHER[lv])
        cv.put(x0 + 3, yy, MASK[2] if yy % 2 else MASK[1])   # page edges
    cv.put(x0 + 1, y0 + 4, BRASS[3])
    cv.put(x0 + 2, y0 + 4, BRASS[1])


# ---------------------------------------------------------------- hood + mask
def face_point(b: Body) -> tuple[float, float]:
    h = 62.5
    return b.center(h) - 4.8 * b.p.sx, b.y_of(h)


def draw_hood_opening(cv: Canvas, b: Body) -> tuple[float, float]:
    """Dark opening lined in red-orange; returns the opening centre."""
    p = b.p
    ox, oy = face_point(b)
    rx, ry = 5.7 * p.sx, 6.9 * b.sy
    for y in range(int(oy - ry) - 3, int(oy + ry) + 3):
        for x in range(int(ox - rx) - 3, int(ox + rx) + 3):
            dx, dy = (x + 0.5 - ox) / rx, (y + 0.5 - oy) / ry
            d = dx * dx + dy * dy
            if d < 1.0:
                if dy < -0.55 + 0.3 * dx * dx:               # hood brow overhangs
                    col = ROBE[2] if dy > -0.8 else ROBE[3]
                else:
                    col = VOID if dy < 0.45 else mix(VOID, LINING[0], (dy - 0.45) * 1.2)
                cv.put(x, y, col)
            elif d < 1.55 and cv.get(x, y) is not None:
                lit = dx < 0.0 or dy < -0.55
                cv.put(x, y, LINING[3] if (lit and d < 1.28) else LINING[2] if lit else LINING[1])
    return ox, oy


def draw_mask(cv: Canvas, mx: float, my: float, tilt: float, eye: float, crack: float,
              sxs: float = 1.0) -> list[tuple[float, float]]:
    """Cracked white ceramic mask with two ember eye slits. Returns the eye points."""
    rx, ry = 4.3 * sxs, 5.7
    ca, sa = math.cos(tilt), math.sin(tilt)
    eyes = []
    r = int(max(rx, ry)) + 2
    for y in range(int(my) - r, int(my) + r + 1):
        for x in range(int(mx) - r, int(mx) + r + 1):
            X, Y = x + 0.5 - mx, y + 0.5 - my
            lx, ly = X * ca + Y * sa, -X * sa + Y * ca
            nx, ny = lx / rx, ly / ry
            if ny > 0.2:                                  # narrower chin
                nx /= (1 - 0.25 * (ny - 0.2))
            d = nx * nx + ny * ny
            if d > 1:
                continue
            light = 0.86 - 0.42 * nx - 0.3 * ny - 0.25 * max(0.0, d - 0.6)
            if abs(nx + 0.05) < 0.14 and -0.2 < ny < 0.35:  # nose ridge
                light += 0.12
            col = ramp(MASK, max(0.0, min(1.0, light)), x, y, 0.25)
            # crack: zigzag from the brow down between the eyes to the cheek
            zz = 0.22 - 0.22 * (ny + 1) + 0.12 * math.sin(ny * 9)
            if -1 < ny < -0.3 and abs(nx - zz) < 0.12:
                col = MASK[1]
            if crack > 0.3:
                zz2 = -0.5 + 0.3 * (ny - 0.1) + 0.08 * math.sin(ny * 13 + 1)
                if 0.1 < ny < 1 and abs(nx - zz2) < 0.11:
                    col = MASK[0]
            if crack > 0.7 and nx > 0.45 and ny > 0.35:   # a chipped corner
                col = VOID
            # narrow eye slits, slanted down towards the middle (menacing)
            for side in (-1, 1):
                ex0 = side * 0.52 - 0.04
                slit_y = -0.08 - 0.3 * side * (nx - ex0)      # inner ends lower
                if abs(nx - ex0) < 0.36 and abs(ny - slit_y - 0.2) < 0.1 and col != VOID:
                    col = MASK[1]                             # socket shadow under the slit
                if abs(nx - ex0) < 0.36 and abs(ny - slit_y) < 0.1:
                    hot = abs(nx - ex0) < 0.14
                    if eye > 0.05:
                        lv = 4 if (hot and eye > 1.25) else 3 if hot else 2
                        col = EMBER[max(0, lv - (1 if eye < 0.6 else 0))]
                    else:
                        col = VOID
                    if hot:
                        eyes.append((x + 0.5, y + 0.5))
            cv.put(x, y, col)
    return eyes


# ---------------------------------------------------------------- censer arm
def hand_point(b: Body, hand) -> tuple[float, float]:
    return CX + b.p.dx + hand[0] * b.p.sx, b.y_of(hand[1])


def censer_center(p: Pose) -> tuple[float, float]:
    b = Body(p)
    hx, hy = hand_point(b, p.hand)
    L = p.chain + 4.5
    x, y = hx + L * math.sin(p.swing), hy + L * math.cos(p.swing)
    return x, min(y, GROUND - 4.0)


def draw_arm(cv: Canvas, b: Body, hand, back: bool) -> tuple[float, float, float, float]:
    """Bell sleeve from the shoulder to ``hand`` with a bony hand. Returns hand + direction."""
    p = b.p
    if back:
        sx_, sy_ = b.to_cell(0.35 * 15, 50)
    else:
        sx_, sy_ = b.to_cell(-0.45 * 14, 50)
    hx, hy = hand_point(b, hand)
    side = 1 if back else -1
    ex, ey = (sx_ + hx) / 2 + side * 3, (sy_ + hy) / 2 + 4
    n = int(math.hypot(hx - sx_, hy - sy_) * 1.5) + 3
    pts = bezier((sx_, sy_), (ex, ey), (hx, hy), n)
    cols = ROBE[1:] if not back else ROBE[:-1]
    stroke(cv, pts, lambda t: 3.6 - 1.2 * t + 2.2 * max(0.0, t - 0.7) / 0.3, cols,
           shade=-0.12 if back else 0.0, rim=OUTLINE)
    dxh, dyh = hx - ex, hy - ey
    L = max(1.0, math.hypot(dxh, dyh))
    dxh, dyh = dxh / L, dyh / L
    nx, ny = -dyh, dxh
    for k in range(-3, 4):                       # red lining inside the sleeve mouth
        cv.put(int(hx + nx * k * 0.9), int(hy + ny * k * 0.9), LINING[2] if k < 0 else LINING[1])
    # bony hand gripping the chain
    gx, gy = hx + dxh * 2.0, hy + dyh * 2.0
    for ox, oy, lv in ((0, 0, 2), (-1, 0, 3), (1, 0, 1), (0, 1, 2), (-1, 1, 2), (0, -1, 3), (1, 1, 1)):
        cv.put(int(gx) + ox, int(gy) + oy, SKIN[lv])
    cv.put(int(gx + dxh * 1.6) - 1, int(gy + dyh * 1.6), SKIN[3])   # knuckles / thumb
    return gx, gy, dxh, dyh


def draw_chain(cv: Canvas, x0: float, y0: float, x1: float, y1: float) -> None:
    n = int(math.hypot(x1 - x0, y1 - y0)) + 1
    for i in range(n):
        t = i / max(1, n - 1)
        x, y = x0 + (x1 - x0) * t, y0 + (y1 - y0) * t
        k = i % 3
        if k == 2:
            continue
        cv.put(int(x), int(y), BRASS[3] if k == 0 else BRASS[1])


def draw_censer(cv: Canvas, cx: float, cy: float, ang: float, glow: float) -> None:
    """Brass thurible: domed lid with ember holes, rim band, round bowl, little foot.

    ``ang`` points from the hand to the censer (0 = hanging straight down).
    """
    dxv, dyv = math.sin(ang), math.cos(ang)                # along the chain, away from the hand
    nxv, nyv = dyv, -dxv
    g = max(0.0, glow)
    for y in range(int(cy) - 9, int(cy) + 10):
        for x in range(int(cx) - 9, int(cx) + 10):
            X, Y = x + 0.5 - cx, y + 0.5 - cy
            lx, ly = X * nxv + Y * nyv, X * dxv + Y * dyv
            # profile (half width) along ly: ring, lid dome, rim, bowl, foot
            if -7.6 <= ly < -6.2:
                hw = 1.0
                if abs(lx) < 0.4:
                    continue                                # the ring's hole
            elif -6.2 <= ly < -2.2:
                hw = 1.2 + 3.0 * math.sqrt(max(0.0, (ly + 6.2) / 4))
            elif -2.2 <= ly < -0.8:
                hw = 5.0
            elif -0.8 <= ly < 3.2:
                hw = 4.7 * math.sqrt(max(0.0, 1 - ((ly + 0.8) / 4.3) ** 2)) + 0.5
            elif 3.2 <= ly < 4.8:
                hw = 2.0 + (ly - 3.2) * 0.5
            else:
                continue
            if abs(lx) > hw:
                continue
            u = lx / max(0.8, hw)
            if ly < -6.2:
                col = BRASS[3] if lx < 0 else BRASS[1]
            elif ly < -2.2:                                   # lid dome
                light = 0.72 - 0.45 * u - 0.06 * (ly + 6.2)
                col = ramp(BRASS, max(0.0, min(1.0, light)), x, y, 0.3)
                if abs(ly + 3.6) < 0.7 and abs(abs(lx) - 2.0) < 0.6 or (abs(ly + 3.6) < 0.7 and abs(lx) < 0.5):
                    col = (EMBER[3] if g > 1.2 else EMBER[2]) if g > 0.5 else EMBER[1] if g > 0.05 else BRASS[0]
            elif ly < -0.8:                                   # bright rim band
                col = BRASS[4] if u < -0.35 else BRASS[3] if u < 0.55 else BRASS[1]
            elif ly < 3.2:                                    # bowl
                light = 0.55 - 0.45 * u - 0.1 * (ly + 0.8)
                col = ramp(BRASS, max(0.0, min(1.0, light)), x, y, 0.3)
                if ly < 0.2 and abs(u) < 0.85 and g > 0.05:   # ember seam under the rim
                    col = EMBER[4 if (g > 1.2 and abs(u) < 0.35) else 3 if g > 0.8 else 2 if g > 0.4 else 1]
            else:                                             # foot
                col = BRASS[2] if u < 0 else BRASS[0]
            cv.put(x, y, col)


# ---------------------------------------------------------------- effects
def smoke_puff(cv: Canvas, x: float, y: float, r: float, dens: float) -> None:
    if dens <= 0 or r <= 0:
        return
    y = max(y, r + 2.0)                                   # smoke spreads under the cell top
    for yy in range(int(y - r) - 1, int(y + r) + 2):
        for xx in range(int(x - r) - 1, int(x + r) + 2):
            d = math.hypot(xx + 0.5 - x, yy + 0.5 - y) / r
            if d > 1:
                continue
            if d > 0.55 and bayer(xx, yy) > (1.3 - d) * dens * 1.6:
                continue
            lit = (yy + 0.5 - y) + (xx + 0.5 - x) * 0.6
            lv = 3 if (lit < -r * 0.3 and d < 0.7) else 2 if d < 0.6 else 1 if d < 0.85 else 0
            cv.put(xx, yy, SMOKE[lv], solid=False, alpha=int(255 * min(0.85, 0.25 + 0.6 * dens)))


def draw_trail(cv: Canvas, p: Pose, here) -> None:
    pts = [here] + list(p.trail)
    for k, (x, y) in enumerate(pts):
        if k == 0:
            continue
        dens = p.smoke * (1 - k / (len(pts) + 1.0))
        smoke_puff(cv, x - 0.9 * k, y - 3 - 2.6 * k, 1.5 + 0.6 * k, dens)
    # a thin wisp straight off the lid
    x0, y0 = here
    for s in range(6):
        smoke_puff(cv, x0 + 0.6 * math.sin(p.phase * 2 + s), y0 - 6 - s * 1.4, 0.9, 0.7 * p.smoke)


def draw_embers(cv: Canvas, p: Pose, here) -> None:
    if p.embers <= 0:
        return
    x0, y0 = here
    for j in range(5):
        f = (p.phase / math.tau * 2 + j / 5 + 0.13 * j) % 1.0
        x = x0 + 3.5 * math.sin(j * 2.3 + f * 4) + 6 * f * (1 if j % 2 else -0.4)
        y = y0 - 3 - f * 26
        lv = 4 if f < 0.15 else 3 if f < 0.4 else 2 if f < 0.7 else 1
        if f > 0.9 or hash01(j, 4, 2) > p.embers:
            continue
        cv.put(int(x), int(y), EMBER[lv], solid=False)


def draw_arc(cv: Canvas, p: Pose, b: Body) -> None:
    """Swoosh of the swing: smoke on the outside, a band of embers, bright head."""
    if not p.arc:
        return
    a0, a1, fade = p.arc
    hx, hy = hand_point(b, p.hand)
    L = p.chain + 4.5
    steps = 90
    for i in range(steps):
        t = i / (steps - 1)                    # 1 = head
        w = t - fade * 1.1
        if w <= 0:
            continue
        a = a0 + (a1 - a0) * t
        for k, (dr, kind) in enumerate(((-3.0, 0), (-1.5, 1), (0.0, 2), (1.5, 1), (3.2, 0))):
            r = L + dr
            x, y = hx + r * math.sin(a), hy + r * math.cos(a)
            if kind == 0:
                if bayer(int(x), int(y)) < w * 0.9:
                    cv.put(int(x), int(y), SMOKE[1 + (w > 0.5)], solid=False, alpha=200)
            else:
                lv = 4 if (w > 0.85 and kind == 2) else 3 if w > 0.6 else 2 if w > 0.3 else 1
                if kind == 1:
                    lv = max(0, lv - 1)
                cv.put(int(x), int(y), EMBER[lv], solid=False, alpha=int(255 * min(1.0, 0.3 + w)))


def draw_sparks(cv: Canvas, p: Pose) -> None:
    if p.sparks <= 0 or not p.impact:
        return
    ix, iy = p.impact
    s = p.sparks
    for j in range(18):
        ang = math.pi + (hash01(j, 1, 6) - 0.5) * 2.8
        sp = 10 + 20 * hash01(j, 2, 6)
        d = sp * (1 - (1 - min(1.0, s)) ** 2)
        x = ix + math.cos(ang) * d
        y = iy + math.sin(ang) * d + 10 * s * s * hash01(j, 3, 6)
        if s > 0.95 and hash01(j, 5, 6) > 0.5:
            continue
        lv = 4 if s < 0.35 else 3 if s < 0.65 else 2 if s < 0.85 else 1
        cv.put(int(x), int(y), EMBER[lv], solid=False)
        if s < 0.7:                                       # streak behind each spark
            cv.put(int(x - math.cos(ang) * 1.5), int(y - math.sin(ang) * 1.5), EMBER[max(0, lv - 1)],
                   solid=False)
    if s < 0.5:                                           # impact flare
        k = 1 - s * 2
        for ox, oy in ((0, 0), (-1, 0), (1, 0), (0, -1), (0, 1), (-2, 0), (2, 0), (0, -2), (0, 2)):
            cv.put(int(ix) + ox, int(iy) + oy, EMBER[4] if abs(ox) + abs(oy) < 2 else EMBER[3],
                   solid=False, alpha=int(255 * k))
        cv.glow(ix, iy, 9 * k + 3, EMBER[2], 0.6 * k)
    for j in range(6):                                    # ash smoke ball
        ang = math.pi + (hash01(j, 8, 6) - 0.5) * 2.2
        d = 6 * s + 2
        smoke_puff(cv, ix + math.cos(ang) * d, iy + math.sin(ang) * d - 3 * s, 1.5 + 2 * s,
                   0.8 * (1 - s))


def draw_ring(cv: Canvas, p: Pose, b: Body, t: float, censer) -> None:
    """Blessing: a smoke column rises from the censer into a ring of ash with ember runes."""
    if p.ring <= 0:
        return
    st = p.ring
    gx = CX - 6 + p.dx
    gy = b.y_of(H) - 13
    grow = min(1.0, st * 1.3)
    rx, ry = 6 + 26 * grow, 1.5 + 5.5 * grow
    # smoke column from the censer up into the ring
    cx, cy = censer
    n = 8
    for k in range(n):
        f = k / (n - 1)
        if f > grow + 0.15:
            break
        x = cx + (gx - cx) * f + 2 * math.sin(f * 6 + t * 6)
        y = cy - 6 + (gy - cy + 6) * f
        smoke_puff(cv, x, y, 1.6 + 2.0 * f * grow, 0.75 * min(1.0, st * 2))
    for i in range(220):
        a = i / 220 * math.tau
        x, y = gx + math.cos(a) * rx, gy + math.sin(a) * ry
        front = math.sin(a) > 0
        if bayer(int(x), int(y)) > 0.85 * st + 0.1:
            continue
        cv.put(int(x), int(y), SMOKE[3 if front else 1], solid=False, alpha=int(230 * st))
        if front:
            cv.put(int(x), int(y) + 1, SMOKE[1], solid=False, alpha=int(180 * st))
    if st > 0.35:                                       # ember runes marching round the ring
        for j in range(6):
            a = j / 6 * math.tau + t * 1.8
            x, y = gx + math.cos(a) * rx, gy + math.sin(a) * ry - 3
            lv = 4 if math.sin(a) > 0 else 2
            for ox, oy in GLYPHS[j]:
                cv.put(int(x) + ox - 1, int(y) + oy - 1, EMBER[lv if (ox + oy) % 2 == 0 else lv - 1],
                       solid=False, alpha=int(255 * min(1.0, st * 1.4)))
            cv.glow(x, y, 4, EMBER[2], 0.4 * st, halo=False)
    # sparks drifting outwards to both sides (the blessing spreading to allies)
    for j in range(10):
        f = (st * 1.4 + hash01(j, 3, 9) * 0.6) % 1.0
        side = -1 if j % 2 == 0 else 1
        x = gx + side * (rx * 0.6 + f * 26)
        y = gy - 2 + f * 10 * hash01(j, 4, 9) - 4 * math.sin(f * math.pi)
        cv.put(int(x), int(y), EMBER[3 if f < 0.5 else 2], solid=False, alpha=int(255 * st))


def draw_ash(cv: Canvas, p: Pose, b: Body) -> None:
    if p.ash <= 0:
        return
    s = p.ash
    cx, cy = b.to_cell(2, 48)
    for j in range(12):
        ang = -math.pi / 2 + (hash01(j, 1, 13) - 0.3) * 3.0
        d = 4 + 16 * s * (0.5 + 0.5 * hash01(j, 2, 13))
        x, y = cx + math.cos(ang) * d + 4 * s, cy + math.sin(ang) * d + 6 * s * s
        if j < 5:
            smoke_puff(cv, x, y, 1.5 + 2.5 * s, 0.9 * (1 - s))
        elif s < 0.9:
            cv.put(int(x), int(y), SMOKE[3] if j % 3 else EMBER[2], solid=False)


# ---------------------------------------------------------------- render
def render(p: Pose, t: float = 0.0) -> Canvas:
    cv = Canvas(CELL_W, CELL_H)
    if p.dissolve >= 1.0:
        return cv
    b = Body(p)
    hx, hy = hand_point(b, p.hand)
    ccx, ccy = censer_center(p)
    ang = 0.6 * math.atan2(ccx - hx, ccy - hy)            # hang (kept fairly upright to read)
    lid = (ccx - 6.5 * math.sin(ang), ccy - 6.5 * math.cos(ang))
    if p.behind:
        draw_chain(cv, hx, hy, *lid)
        draw_censer(cv, ccx, ccy, ang, p.glow)
    draw_mass(cv, b)
    draw_belt(cv, b)
    draw_beads(cv, b)
    draw_book(cv, b)
    face = draw_hood_opening(cv, b)
    eyes: list = []
    tilt = p.mask_tilt - 0.06 * p.lean / 5
    if p.mask_drop <= 0:
        eyes = draw_mask(cv, face[0] + 0.4, face[1] + 0.4, tilt, p.eye, p.crack)
    elif p.mask_drop < 0.5 and p.eye > 0.05:            # embers left in the empty hood
        for ox in (-2, 2):
            cv.put(int(face[0]) + ox, int(face[1]), EMBER[1])
    if p.both > 0.5:
        draw_arm(cv, b, p.hand_b, back=True)
    gx, gy, _, _ = draw_arm(cv, b, p.hand, back=False)
    if not p.behind:
        draw_chain(cv, gx, gy, *lid)
        draw_censer(cv, ccx, ccy, ang, p.glow)
    if p.mask_drop > 0:
        d = min(1.0, p.mask_drop)
        tx, ty = face[0] - 9, GROUND - 2.5
        mx = lerp(face[0] + 0.4, tx, d)
        my = lerp(face[1] + 0.4, ty, d * d) - 3 * math.sin(d * math.pi)
        draw_mask(cv, mx, my, p.mask_tilt + 1.45 * d, 0.0, max(1.0, p.crack), 1.0)
    outline(cv, OUTLINE)
    # lights
    if eyes and p.eye > 0.05:
        ex = sum(e[0] for e in eyes) / len(eyes)
        ey = sum(e[1] for e in eyes) / len(eyes)
        cv.glow(ex, ey, 5 + 3 * p.eye, EMBER[2], 0.32 * p.eye, halo=p.eye > 1.2)
    if p.glow > 0.05:
        cv.glow(ccx, ccy - 1, 6 + 3 * p.glow, EMBER[1], 0.3 * p.glow)
    if p.smoke > 0:
        draw_trail(cv, p, lid)
    draw_embers(cv, p, lid)
    draw_arc(cv, p, b)
    draw_sparks(cv, p)
    draw_ring(cv, p, b, t, lid)
    draw_ash(cv, p, b)
    for (mx, my, kind) in p.motes:
        col = SMOKE[min(3, int(kind) + 1)] if kind < 3 else EMBER[min(4, int(kind) - 1)]
        cv.put(int(mx), int(my), col, solid=False)
    flash(cv, p.flash)
    if p.dissolve > 0:
        top = b.y_of(H) - 4
        dissolve(cv, p.dissolve, top, GROUND + 2, EMBER[3], EMBER[1], upward=True, seed=7)
    return cv


# ---------------------------------------------------------------- animations
IDLE_FRAMES = 12


def _idle_core(a: float) -> Pose:
    return Pose(
        lean=round(0.9 * math.sin(a + 0.5)), phase=a, sway=1.0,
        hand=(-21.0 - 1.2 * math.sin(a), 43.0 + 0.8 * math.cos(2 * a)),
        swing=0.5 * math.sin(a), chain=13.0,
        glow=0.85 + 0.25 * math.sin(2 * a), eye=1.0,
    )


def idle_pose(i: int, n: int = IDLE_FRAMES) -> Pose:
    i %= n
    a = math.tau * i / n
    trail = tuple(_lid(_idle_core(a - 0.42 * k)) for k in range(1, 7))
    return replace(_idle_core(a), trail=trail, eye=0.8 if i == 8 else 1.0)


def idle_frames():
    return [(idle_pose(i), 110) for i in range(IDLE_FRAMES)]


def _lid(p: Pose) -> tuple[float, float]:
    b = Body(p)
    hx, hy = hand_point(b, p.hand)
    x, y = censer_center(p)
    a = 0.6 * math.atan2(x - hx, y - hy)
    return x - 6.5 * math.sin(a), y - 6.5 * math.cos(a)


def _with_trails(poses: list[Pose], keep_last: bool = True) -> list[Pose]:
    """Each pose gets the lid positions of the previous ones as its smoke trail."""
    out = []
    lids = [_lid(p) for p in poses]
    for j, p in enumerate(poses):
        if keep_last and j == len(poses) - 1:
            out.append(p)
            continue
        prev = []
        for k in range(1, 4):
            if j - k < 0:
                break
            x0, y0 = lids[j - k + 1]
            x1, y1 = lids[j - k]
            prev.append(((x0 + x1) / 2, (y0 + y1) / 2))
            prev.append((x1, y1))
        out.append(replace(p, trail=tuple(prev[:6])))
    return out


def attack_frames():
    """Golpe de Incensario: censer back over the head, big arc LEFT, embers on contact."""
    b = idle_pose(0)
    base = replace(b, trail=())
    tau = math.tau
    contact = replace(base, dx=-6, lean=-9, sx=1.04, hand=(-26, 50), swing=4.95, chain=22, glow=1.5,
                      eye=1.4, phase=1.6)
    cx, cy = censer_center(contact)
    impact = (cx - 4, cy)
    poses = [
        replace(base, dx=1, lean=3, hand=(-12, 56), swing=1.2, chain=13, eye=1.15, glow=1.1, phase=0.3),
        replace(base, dx=3, lean=6, sy=1.03, hand=(2, 70), swing=2.4, chain=13, eye=1.3, glow=1.3,
                phase=0.6, behind=True),
        replace(base, dx=4, lean=7, sy=1.04, hand=(6, 72), swing=2.95, chain=14, eye=1.4, glow=1.4,
                phase=0.9, behind=True),
        replace(base, dx=-2, lean=-4, hand=(-14, 68), swing=3.95, chain=19, eye=1.5, glow=1.5, phase=1.2,
                arc=(2.95, 3.95, 0.0)),
        replace(contact, arc=(3.3, 4.95, 0.0), impact=impact, sparks=0.18),
        replace(base, dx=-6, lean=-8, sx=1.02, hand=(-25, 44), swing=5.5, chain=20, glow=1.3, eye=1.3,
                phase=2.0, arc=(3.6, 5.5, 0.55), impact=impact, sparks=0.5),
        replace(base, dx=-4, lean=-5, hand=(-24, 42), swing=tau - 0.35, chain=17, glow=1.15, eye=1.15,
                phase=2.6, impact=impact, sparks=0.8),
        replace(base, dx=-2, lean=-3, hand=(-22, 43), swing=tau + 0.4, chain=14.5, glow=1.0, phase=3.4,
                impact=impact, sparks=1.0),
        replace(base, dx=-1, lean=-1, hand=(-21, 43), swing=tau + 0.25, chain=13, phase=4.6),
        b,
    ]
    durs = [100, 130, 80, 55, 60, 80, 90, 90, 90, 110]
    return list(zip(_with_trails(poses), durs))


ATTACK_STRIKE = 4


def cast_frames():
    """Bendición de Ceniza: both hands raise the censer, a ring of ash and ember runes above."""
    b = idle_pose(0)
    base = replace(b, trail=())
    ups = [0.35, 0.75, 1.0, 1.0, 1.0, 1.0, 0.55]
    rings = [0.0, 0.25, 0.55, 0.85, 1.0, 0.75, 0.3]
    out = []
    for k, (u, r) in enumerate(zip(ups, rings)):
        out.append(replace(
            base, dy=-round(1.5 * u), lean=round(2 * u), hand=(lerp(-21, -31, u), lerp(43, 80, u)),
            hand_b=(lerp(-4, -29, u), lerp(38, 57, u)), both=1.0 if u > 0.5 else 0.0,
            swing=0.25 * math.sin(k * 1.3) * (1 - u), chain=lerp(13, 8, u), glow=1.0 + 0.7 * u,
            eye=1.0 + 0.75 * u, smoke=1.0 + 0.3 * u, ring=r, phase=0.45 * k))
    out = _with_trails(out, keep_last=False)
    durs = [85, 90, 90, 100, 110, 90, 90]
    return list(zip(out, durs)) + [(b, 110)]


def hurt_frames():
    b = idle_pose(0)
    base = replace(b, trail=())
    poses = [
        replace(base, dx=4, lean=4, sx=0.95, sy=1.03, hand=(-17, 47), swing=1.1, mask_tilt=0.35,
                eye=0.4, flash=0.82, ash=0.2, phase=1.2),
        replace(base, dx=6, lean=6, sx=0.97, hand=(-16, 46), swing=0.75, mask_tilt=0.42, eye=0.6,
                flash=0.6, ash=0.45, phase=1.8),
        replace(base, dx=5, lean=4, dy=1, hand=(-18, 45), swing=0.2, mask_tilt=0.28, eye=0.8,
                flash=0.25, ash=0.7, phase=2.4),
        replace(base, dx=3, lean=2, hand=(-19, 44), swing=-0.25, mask_tilt=0.12, ash=0.92, phase=3.1),
        replace(base, dx=2, lean=1, hand=(-20, 43), swing=-0.18, mask_tilt=0.04, phase=3.9),
        replace(base, dx=1, hand=(-21, 43), swing=-0.06, phase=5.0),
        b,
    ]
    durs = [55, 60, 70, 70, 80, 90, 100]
    return list(zip(_with_trails(poses), durs))


def death_frames():
    b = idle_pose(0)
    base = replace(b, trail=())
    out = [
        (replace(base, dx=4, lean=4, flash=0.85, eye=0.5, mask_tilt=0.3, swing=0.9, hand=(-17, 46),
                 phase=0.8), 70),
        (replace(base, dx=3, lean=-2, kneel=0.35, eye=1.8, crack=0.5, mask_tilt=0.15, hand=(-20, 30),
                 swing=0.3, glow=1.4, flash=0.2, phase=1.4), 100),
        (replace(base, dx=2, lean=-4, kneel=0.62, eye=1.0, crack=1.0, mask_drop=0.35, hand=(-21, 20),
                 swing=0.1, glow=1.0, phase=1.9), 90),
        (replace(base, dx=2, lean=-5, kneel=0.72, eye=0.5, crack=1.0, mask_drop=0.75, hand=(-21, 16),
                 swing=0.0, glow=0.8, smoke=0.6, phase=2.3), 80),
    ]
    steps = 9
    for k in range(steps):
        u = (k + 1) / steps
        d = 0.04 + 0.92 * u
        motes = tuple(
            (CX - 26 + hash01(k, j, 9) * 52,
             GROUND - 8 - u * 60 - hash01(j, k, 4) * 26,
             (3 + int(hash01(j, k, 2) * 2)) if j % 3 == 0 else int(hash01(j, k, 5) * 3))
            for j in range(10 + 2 * k))
        out.append((replace(base, dx=2, lean=-5, kneel=0.75, eye=0.0, crack=1.0, mask_drop=1.0,
                            hand=(-21, 15), swing=0.0, glow=0.7 * (1 - u), smoke=0.5 * (1 - u),
                            embers=1 - u, phase=2.6 + 0.4 * k, dissolve=d, motes=motes), 80))
    out.append((replace(b, dissolve=1.0), 120))
    return out


ANIMATIONS = {
    "idle": (idle_frames, True),
    "attack": (attack_frames, False),
    "cast": (cast_frames, False),
    "hurt": (hurt_frames, False),
    "death": (death_frames, False),
}

EVENTS = {"attack": {"strikes": [ATTACK_STRIKE]}}
MOVES = {"censer": "attack", "ember": "attack", "bless": "cast", "mend": "cast", "penance": "cast",
         "vengeance": "cast"}


def build():
    return build_sheet(ANIMATIONS, render, (CELL_W, CELL_H), ANCHOR, f"{SHEET_ID}_sheet.png",
                       {"events": EVENTS, "moves": MOVES})


def main() -> None:
    sheet, meta = build()
    save_sheet(OUT_DIR, SHEET_ID, sheet, meta)
    print(f"wrote assets/enemies/{SHEET_ID}_sheet.png ({len(sheet[0])}x{len(sheet)}) and .json")


if __name__ == "__main__":
    main()
