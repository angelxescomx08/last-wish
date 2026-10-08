"""Draw and animate the enemy "Cráneo Ígneo" (a flaming horned skull). Stdlib only:

    python scripts/generate_enemy_skull.py

Same method as the Espectro (``docs/code-drawn-sprites.md``): one renderer, every
frame a ``Pose``, shared helpers from ``pixel_kit``. The creature:

* a large floating horned skull of cracked, warm ivory bone (upper-left light,
  hue-shifted maroon shadows), slanted eye sockets, a heart-shaped nasal cavity,
  jagged upper teeth and a hinged jaw that opens on a mouth full of fire;
* a crown of waving flame tongues licking up and trailing to the right/back
  (deep red edge -> orange -> yellow -> near-white core near the bone);
* two burning ember eyes with a cold blue-white core (the accent), cinders.

Identity: aggressive, it stokes its own fire to hit harder each time.

Animations (non-death actions end on idle frame 0):
  idle    12-frame hover loop: bob, flames wave, the jaw chatters once, embers pulse
  attack  "Llamarada": rears back, flames flare, then lunges left spewing a fire jet
  cast    "Avivar": flames swell white-hot, jaw roaring, ring of sparks
  hurt    white flash, knocked right, flames gutter and recover
  death   cracks spread, the fire sputters to smoke, the skull drops and crumbles to ash

Output: ``assets/enemies/skull_sheet.png`` + ``.json`` (``events.attack.strikes``).
"""
from __future__ import annotations

import math
import sys
from dataclasses import dataclass, field, replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from pixel_kit import (Canvas, bayer, bezier, build_sheet, dissolve, flash, hash01, mix,  # noqa: E402
                       outline, ramp, save_sheet, smooth, stroke)

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "assets" / "enemies"
SHEET_ID = "skull"

CELL_W, CELL_H = 144, 108
CX = CELL_W - 48                # skull centre line (room on the left for the fire jet)
GROUND = 100                    # floor row under the floating skull
ANCHOR = (CX, GROUND + 2)
SKY = 59                        # cranium centre row (jaw bottom ~20 px above the ground)

# ---------------------------------------------------------------- palette
OUTLINE = (30, 8, 14)
BONE = [(58, 30, 36), (100, 58, 54), (148, 102, 80), (192, 152, 114), (226, 196, 152),
        (248, 230, 196)]
HORN = [(34, 18, 24), (64, 34, 36), (102, 64, 54), (150, 112, 84), (200, 172, 132)]
SOCKET = [(14, 4, 10), (34, 10, 16), (70, 20, 20)]
FIRE = [(64, 10, 22), (128, 20, 22), (188, 52, 22), (232, 104, 28), (252, 166, 48),
        (255, 222, 116), (255, 250, 222)]
EYE = [(255, 150, 40), (255, 210, 110), (150, 210, 255), (236, 248, 255)]
SMOKE = [(36, 30, 40), (58, 50, 60), (86, 78, 86), (118, 110, 112)]
ASH = [(70, 62, 66), (112, 104, 102), (160, 150, 140)]
WHITE = (255, 255, 255)

# flame tongues: (base angle on the cranium in degrees, length, width)
TONGUES = [(196, 8, 4.4), (172, 12, 5.2), (150, 16, 6.0), (127, 20, 6.6), (104, 23, 7.0),
           (82, 22, 7.0), (60, 20, 6.8), (38, 18, 6.4), (16, 16, 6.0), (-6, 14, 5.4),
           (-28, 12, 4.8), (-48, 9, 4.0)]
CINDERS = [(-18, 0.0, 24), (-6, 0.37, 26), (6, 0.71, 24), (16, 0.18, 22), (24, 0.55, 18),
           (30, 0.86, 14)]
# fixed cracks on the cranium (head-local points)
CRACKS = [[(5, -12.5), (6, -9), (4, -7), (6, -4)], [(-11, -5), (-8.5, -3.5), (-9, -1)]]
# death cracks, appearing in order
DEATH_CRACKS = [[(-1, -13), (-3, -9), (-1, -6), (-3, -2), (-2, 1)],
                [(8, -9), (11, -6), (10, -2), (13, 1)],
                [(-12, -2), (-9, 0), (-12, 5), (-10, 8)],
                [(2, 6), (4, 9), (2, 12)]]


@dataclass(frozen=True)
class Pose:
    dx: float = 0.0
    dy: float = 0.0
    tilt: float = 0.0             # radians, positive = face (left side) up (rear back)
    sx: float = 1.0
    sy: float = 1.0
    jaw: float = 0.0              # 0 closed .. 1 gaping
    phase: float = 0.0
    flame: float = 1.0            # flame size
    heat: float = 1.0             # flame brightness
    trail: float = 0.6            # flames trailing right/back
    gutter: float = 0.0           # flames shrink and darken
    smoke: float = 0.0
    eye: float = 1.0
    crack: float = 0.0            # death cracks 0..1
    flash: float = 0.0
    dissolve: float = 0.0
    jet: float = 0.0              # fire jet length 0..1 (attack)
    jet_fade: float = 0.0
    ring: float = 0.0             # spark ring (cast)
    ring_fade: float = 0.0
    shards: float = 0.0           # bone fragments scattered on impact (death)
    cinders: float = 1.0
    motes: tuple = field(default_factory=tuple)


class Body:
    """Head-local coordinates (origin = cranium centre) <-> cell pixels."""

    def __init__(self, p: Pose) -> None:
        self.p = p
        self.cx = CX + p.dx
        self.cy = SKY + p.dy
        self.c, self.s = math.cos(p.tilt), math.sin(p.tilt)

    def to_cell(self, lx: float, ly: float) -> tuple[float, float]:
        p = self.p
        x, y = lx * p.sx, ly * p.sy
        # positive tilt rotates the face (left) upwards: counter-clockwise on screen
        return self.cx + x * self.c + y * self.s, self.cy - x * self.s + y * self.c

    def to_local(self, x: float, y: float) -> tuple[float, float]:
        p = self.p
        ox, oy = x - self.cx, y - self.cy
        lx = ox * self.c - oy * self.s
        ly = ox * self.s + oy * self.c
        return lx / p.sx, ly / p.sy


FC = -1.5                       # face centre (slight 3/4 view towards the hero)
HINGE = (11.5, 9.0)


def head_hw(ly: float) -> float:
    """Half width of the skull (without the jaw) at head-local row ``ly``."""
    if ly < -13 or ly > 16.2:
        return 0.0
    if ly < 3:
        return 15.0 * math.sqrt(max(0.0, 1 - (ly / 13.0) ** 2)) if ly < 0 else 15.0 - 0.15 * ly
    if ly < 9:                                   # cheekbones
        return 14.5 - 0.25 * (ly - 3)
    return 13.0 - 5.0 * smooth((ly - 9) / 6.5)  # maxilla narrows to the teeth


def in_jaw(jx: float, jy: float) -> str | None:
    """Part of the mandible at jaw-local coordinates (same frame as the head when closed)."""
    c = FC - 0.5
    if 14.0 <= jy <= 21.5:
        hw = 9.6 - 2.6 * (jy - 14) / 7.5
        u = (jx - c) / hw
        if abs(u) <= 1 and jy <= 21.5 - 2.2 * u ** 4:
            if jy < 16.2 and abs(jx - c) < 8.2:
                return "teeth"
            return "bone"
    if 6.5 <= jx <= 11.8 and 9.0 <= jy <= 16:   # ramus up to the hinge
        return "bone"
    return None


def jaw_local(lx: float, ly: float, ang: float) -> tuple[float, float]:
    """Head-local -> jaw-local (the jaw opens by turning ``ang`` about the hinge, chin down)."""
    hx, hy = HINGE
    drop = 7.0 * ang                              # the jaw also slides down as it opens
    ox, oy = lx - hx, ly - drop - hy
    c, s = math.cos(ang), math.sin(-ang)
    return hx + ox * c + oy * s, hy - ox * s + oy * c


def tooth(x: float, y: float, top: float, down: bool) -> bool:
    """Jagged teeth: columns 2 px wide with dark gaps, pointed tips."""
    k = math.floor((x + 20) / 2.5)
    fx = (x + 20) / 2.5 - k
    if fx < 0.22:
        return False
    tip = 0.9 * abs(fx - 0.6) * 2 + 0.3 * hash01(k, 3, 11)
    return (y - top) < 3.2 - tip if down else (top - y) < 2.8 - tip


# ---------------------------------------------------------------- fire
def fire_field(b: Body) -> dict:
    """Heat (0..~1.3) per pixel for the flame crown and the aura around the bone."""
    p = b.p
    heat: dict[tuple[int, int], float] = {}
    size = p.flame * (1 - 0.55 * p.gutter)
    if size <= 0.02:
        return heat

    def splat(x, y, r, h):
        for yy in range(int(y - r) - 1, int(y + r) + 2):
            for xx in range(int(x - r) - 1, int(x + r) + 2):
                d = math.hypot(xx + 0.5 - x, yy + 0.5 - y) / r
                if d > 1:
                    continue
                v = h * (1 - d) ** 0.6
                key = (xx, yy)
                if v > heat.get(key, 0.0):
                    heat[key] = v

    for k, (deg, length, width) in enumerate(TONGUES):
        th = math.radians(deg)
        m = 1 + k % 2
        bx, by = b.to_cell(12.0 * math.cos(th), -10.5 * math.sin(th) - 1)
        L = length * 0.86 * size * (0.88 + 0.14 * math.sin(m * p.phase + k * 2.3))
        if L < 1:
            continue
        W = width * (0.6 + 0.4 * min(1.6, size)) * (0.88 + 0.12 * math.sin((3 - m) * p.phase + k))
        out = 0.35 * math.cos(th)
        n = int(L * 2.2) + 3
        for i in range(n):
            s = i / (n - 1)
            wave = 1.6 * math.sin(m * p.phase + k * 1.7 - s * 3.6) * s * (0.6 + L / 18)
            x = bx + L * s * (out + p.trail * s ** 0.7) + wave
            y = by - L * s * (0.95 if deg > 0 else 0.7)
            r = max(0.6, W * (1 - s) ** 0.75)
            splat(x, y, r, (1.0 - 0.7 * s) * (1.05 if 40 < deg < 140 else 0.95))
        # a lick breaking off the tip
        if math.sin(2 * p.phase + k * 2.1) > 0.35 and k % 3 != 1:
            s = 1.18
            x = bx + L * s * (out + p.trail) + 1.6 * math.sin(m * p.phase + k * 1.7 - 4.2)
            splat(x, by - L * s * 0.95, 1.4 * min(1.5, size), 0.4)
    # aura hugging the bone (and filling between the tongues)
    for yy in range(int(b.cy - 24), int(b.cy + 20)):
        for xx in range(int(b.cx - 26), int(b.cx + 27)):
            lx, ly = b.to_local(xx + 0.5, yy + 0.5)
            if ly > 12:
                continue
            e = math.hypot(lx / 15.0, (ly + 0.5) / 13.5)
            reach = (0.55 + 0.08 * math.sin(p.phase + lx * 0.4)) * min(1.5, size)
            if e < 1 or e > 1 + reach:
                continue
            v = (1 - (e - 1) / reach) * 0.85
            key = (xx, yy)
            if v > heat.get(key, 0.0):
                heat[key] = v
    return heat


def draw_fire(cv: Canvas, b: Body) -> None:
    p = b.p
    boost = p.heat * (1 - 0.5 * p.gutter)
    for (x, y), h in fire_field(b).items():
        v = h * boost
        if v < 0.12:
            continue
        if v < 0.2 and bayer(x, y) > (v - 0.12) * 12:     # ragged outer edge
            continue
        col = ramp(FIRE, max(0.0, min(1.0, v * 1.02 - 0.02)), x, y, 0.6)
        if p.gutter > 0:
            col = mix(col, SMOKE[1], 0.35 * p.gutter)
        cv.put(x, y, col, solid=False)


def draw_smoke(cv: Canvas, b: Body, amount: float, seed: int = 0) -> None:
    if amount <= 0:
        return
    p = b.p
    for k in range(7):
        rise = (k / 7 + 0.15 * math.sin(p.phase + k)) % 1.0
        x = b.cx - 14 + k * 5 + 6 * rise + 2 * math.sin(p.phase * 2 + k)
        y = b.cy - 12 - rise * 30
        r = 2.5 + 4 * rise
        a = amount * (1 - rise * 0.7)
        for yy in range(int(y - r), int(y + r) + 1):
            for xx in range(int(x - r), int(x + r) + 1):
                d = math.hypot(xx + 0.5 - x, yy + 0.5 - y) / r
                if d > 1 or bayer(xx, yy) > (1.5 - d) * a * 1.2:
                    continue
                lvl = 2 if (xx - x) + (yy - y) < -r * 0.3 else 1 if d < 0.7 else 0
                cv.put(xx, yy, SMOKE[lvl], solid=False, alpha=int(150 + 90 * a))


# ---------------------------------------------------------------- skull
def draw_horns(cv: Canvas, b: Body) -> None:
    for side in (-1, 1):
        base = (side * 9.5 - 1, -9.5)
        mid = (side * 17 - 1, -13)
        tip = (side * 15.5 - 1, -21)
        pts = [b.to_cell(*q) for q in bezier(base, mid, tip, 18)]
        curl = b.to_cell(side * 12.5 - 1, -22.5)
        pts.append(curl)
        stroke(cv, pts, lambda t: 3.0 - 2.3 * t, HORN if side < 0 else HORN[:-1],
               shade=0.05 if side < 0 else -0.1, rim=OUTLINE)


def bone_light(lx: float, ly: float, hw: float) -> float:
    u = (lx - FC * 0.5) / max(1.0, hw)
    v = (ly + 13) / 34
    light = 0.86 - 0.34 * u - 0.42 * v
    if u < -0.8 and ly < 6:
        light += 0.14                            # lit rim on the hero side
    if u > 0.82:
        light -= 0.14
    return light


def draw_skull(cv: Canvas, b: Body) -> None:
    p = b.p
    ang = 0.5 * p.jaw
    sk = Canvas(cv.w, cv.h)
    x0, x1 = int(b.cx - 26), int(b.cx + 27)
    y0, y1 = int(b.cy - 20), int(b.cy + 32)
    for y in range(y0, y1):
        for x in range(x0, x1):
            lx, ly = b.to_local(x + 0.5, y + 0.5)
            hw = head_hw(ly)
            col = None
            if hw > 0 and abs(lx - (FC * 0.3 if ly > 9 else 0)) <= hw:
                col = head_pixel(x, y, lx, ly, hw, p)
            if col is None:
                jx, jy = jaw_local(lx, ly, ang)
                part = in_jaw(jx, jy)
                if part == "teeth":
                    if tooth(jx, jy, 16.2, down=False):
                        col = ramp(BONE, 0.88 - 0.04 * (jx - FC), x, y, 0.4)
                    elif jy < 16.2 and p.jaw > 0.05:
                        col = None                   # gap between teeth shows the mouth
                    else:
                        col = SOCKET[1]
                elif part == "bone":
                    light = bone_light(jx, jy, 9.0) - 0.08
                    if jy > 20.3 - 1.4 * ((jx - FC) / 9.0) ** 4:
                        light -= 0.18                # underside of the chin
                    if jx > 6.5 and jy < 15:
                        light -= 0.25                # ramus in the cheek's shadow
                    col = ramp(BONE, max(0.0, min(1.0, light)), x, y)
            if col is None and p.jaw > 0.05 and ly >= 13.0 and -9 <= lx <= 9.5:
                jx, jy = jaw_local(lx, ly, ang)
                if jy < 16.5 and jx > FC - 9.5:     # open mouth: fire inside
                    depth = (ly - 13.5) / max(1.0, 12 * p.jaw)
                    live = p.flame * (1 - p.gutter)
                    col = SOCKET[0 if depth > 0.4 else 1] if live < 0.25 else ramp(FIRE, max(0.0, min(1.0, 0.95 - 0.5 * depth + 0.1 * (p.heat - 1))),
                               x, y, 0.5)
            if col is not None:
                sk.put(x, y, col)
    # cracks
    lines = [c for c in CRACKS]
    n_death = p.crack * len(DEATH_CRACKS)
    for i, line in enumerate(DEATH_CRACKS):
        if n_death > i:
            frac = min(1.0, n_death - i)
            cut = max(2, int(round(len(line) * frac + 0.49)))
            lines.append(line[:cut])
    for line in lines:
        for (ax, ay), (bx_, by_) in zip(line, line[1:]):
            steps = int(math.hypot(bx_ - ax, by_ - ay) * 2) + 1
            for i in range(steps + 1):
                t = i / steps
                lx, ly = ax + (bx_ - ax) * t, ay + (by_ - ay) * t
                x, y = b.to_cell(lx, ly)
                if sk.get(int(x), int(y)) is None:
                    continue
                hot = p.crack > 0 and line not in CRACKS and p.flame > 0.2
                sk.put(x, y, FIRE[3] if hot and (i % 3 == 0) else SOCKET[1])
                if sk.get(int(x) + 1, int(y) + 1) is not None and not hot:
                    sk.tint(int(x) + 1, int(y) + 1, BONE[5], 0.35)
    cv.blit(sk, rim=OUTLINE)


def head_pixel(x: int, y: int, lx: float, ly: float, hw: float, p: Pose):
    # upper teeth row
    if ly > 13.0:
        if abs(lx - FC) <= 8.0:
            if tooth(lx, ly, 13.0, down=True):
                return ramp(BONE, 0.9 - 0.04 * (lx - FC), x, y, 0.4)
            return None if p.jaw > 0.05 else SOCKET[1]
        return None
    # eye sockets (slanted: inner top corners lower = scowl)
    for ex, rx, ry in ((-6.8, 4.8, 4.2), (5.0, 4.4, 3.9)):
        ey = 1.5
        dxe, dye = (lx - ex) / rx, (ly - ey) / ry
        d = dxe * dxe + dye * dye
        brow = ey - ry + 2.4 * max(0.0, 1 - abs(lx - FC) / 7.5)
        if d <= 1 and ly >= brow:
            return SOCKET[0] if d < 0.55 else SOCKET[1]
        if d <= 1.55 and ly < brow + 1 and ly > ey - ry - 2.2:
            return ramp(BONE, bone_light(lx, ly, hw) + 0.16, x, y)   # brow ridge
        if 1 < d <= 1.6 and ly > ey:
            return ramp(BONE, bone_light(lx, ly, hw) - 0.2, x, y)    # under-socket shadow
    # nasal cavity: inverted heart
    nx = lx - FC
    if 6.2 <= ly <= 11.0:
        half = (ly - 6.2) * 0.55 + 0.4 - (0.6 if ly > 10 and abs(nx) < 0.6 else 0.0)
        if abs(nx) <= half:
            return SOCKET[0] if abs(nx) < half - 0.8 else SOCKET[1]
        if abs(nx) <= half + 1.1 and nx < 0:
            return ramp(BONE, bone_light(lx, ly, hw) - 0.18, x, y)
    light = bone_light(lx, ly, hw)
    if 3 < ly < 9 and lx > 9.5:
        light -= 0.28                                # temple hollow
    if 7 < ly < 9.5 and lx < -6:
        light += 0.12                                # cheekbone highlight
    if 9 < ly < 13 and abs(lx - FC) > 6.5:
        light -= 0.2                                 # cheek recess above the teeth
    if ly > 11.8:
        light -= 0.1
    light += 0.05 * math.cos(lx * 0.9 + ly * 0.4)    # bone texture
    return ramp(BONE, max(0.0, min(1.0, light)), x, y)


def draw_eyes(cv: Canvas, b: Body) -> list[tuple[float, float]]:
    p = b.p
    e = p.eye
    out = []
    for ex in (-6.8, 5.0):
        x, y = b.to_cell(ex + 0.3, 2.2)
        out.append((x, y))
        if e <= 0.05:
            continue
        ix, iy = int(x), int(y)
        ringc = EYE[0] if e < 1.3 else EYE[1]
        hot = e > 0.4
        for ox, oy in ((-2, 0), (1, 0), (-1, -1), (0, -1), (-1, 1), (0, 1)):
            cv.put(ix + ox, iy + oy, ringc if hot else FIRE[2])
        if hot:
            core = EYE[3] if e > 0.75 else EYE[2]
            cv.put(ix, iy, core)
            cv.put(ix - 1, iy, EYE[2] if e > 0.75 else EYE[0])
            cv.put(ix - 1, iy - 1, EYE[1])
        if e > 1.15:                                  # blazing: bigger ember, a flame wisp
            for ox, oy in ((-3, 0), (2, 0), (-2, 1), (1, 1), (-2, -1), (1, -1)):
                cv.put(ix + ox, iy + oy, EYE[0])
            cv.put(ix, iy - 1, EYE[2])
            for s in range(int(2 + 2 * (e - 1.15) * 4)):
                cv.put(ix + (s + 1) // 2, iy - 2 - s, EYE[1] if s < 2 else FIRE[4] if s < 4 else FIRE[3],
                       solid=False)
    return out


# ---------------------------------------------------------------- effects
def draw_jet(cv: Canvas, b: Body, prog: float, fade: float) -> None:
    """A cone of fire spewed from the mouth towards the hero (left)."""
    if prog <= 0:
        return
    p = b.p
    mx, my = b.to_cell(-9.5, 17.5)
    ax, ay = -1.0, -0.12
    n = math.hypot(ax, ay)
    ax, ay = ax / n, ay / n
    L = 74 * prog
    s0 = L * fade * 0.9
    for y in range(int(my - 26), int(my + 20)):
        for x in range(0, int(mx) + 4):
            ox, oy = x + 0.5 - mx, y + 0.5 - my
            s = ox * ax + oy * ay
            d = -ox * ay + oy * ax
            if s < -1 or s < s0:
                continue
            w = (2.4 + 0.2 * s + 1.3 * math.sin(s * 0.33 - p.phase * 2) * min(1.0, s / 12)) \
                * (1 - 0.55 * fade) * (1 + 0.4 * fade * min(1.0, (s - s0) / 20))
            q = abs(d) / max(0.5, w)
            if q > 1:
                continue
            end = L - 5 * q * q + 2.5 * math.sin(d * 0.8 + p.phase * 3)
            if s > end:
                continue
            along = s / max(1.0, L)
            v = (1 - q) ** 0.7 * (1.05 - 0.45 * along) + 0.12
            v *= 1 - 0.6 * fade
            if s > end - 3 or q > 0.82:
                v = min(v, 0.35)
            cv.put(x, y, ramp(FIRE, max(0.0, min(1.0, v)), x, y, 0.6), solid=False)
    # billows at the head of the jet
    if fade < 0.95:
        for k in range(4):
            s = L - 3 - k * 6
            if s < s0:
                continue
            bx = mx + ax * s + (hash01(k, 1, 3) - 0.5) * 4
            by = my + ay * s + (hash01(k, 2, 3) - 0.5) * 10
            r = 3 + 3 * hash01(k, 4, 3) * prog
            for yy in range(int(by - r), int(by + r) + 1):
                for xx in range(int(bx - r), int(bx + r) + 1):
                    dd = math.hypot(xx + 0.5 - bx, yy + 0.5 - by) / r
                    if dd > 1 - 0.6 * fade:
                        continue
                    lvl = 0.55 - 0.45 * dd + 0.15 * ((bx - xx) - (yy - by)) / r
                    lvl *= 1 - 0.5 * fade
                    if cv.get(xx, yy) is None or lvl > 0.3:
                        cv.put(xx, yy, ramp(FIRE, max(0.05, lvl), xx, yy), solid=False)
    # sparks along the jet
    for j in range(14):
        s = s0 + (L - s0) * hash01(j, 7, 2)
        x = mx + ax * s + (hash01(j, 8, 2) - 0.5) * 6
        y = my + ay * s + (hash01(j, 9, 2) - 0.5) * (6 + 0.35 * s)
        cv.put(x, y, FIRE[5 + j % 2] if fade < 0.6 else FIRE[3], solid=False)


def draw_ring(cv: Canvas, b: Body, prog: float, fade: float) -> None:
    """Ring of sparks bursting out from the stoked fire (cast)."""
    if prog <= 0 or fade >= 1:
        return
    cx, cy = b.to_cell(0, 2)
    r = 16 + 26 * prog
    for k in range(16):
        a = k / 16 * math.tau + 0.2
        rk = r * (0.85 + 0.25 * hash01(k, 1, 5))
        for s in range(4):
            rr = rk - s * (1.5 + 1.5 * prog)
            if rr < 10:
                continue
            x, y = cx + math.cos(a) * rr, cy + math.sin(a) * rr * 0.8
            if fade > 0 and bayer(int(x), int(y)) < fade:
                continue
            c = FIRE[6] if s == 0 else FIRE[5] if s == 1 else FIRE[4] if s == 2 else FIRE[2]
            cv.put(x, y, c, solid=False)


def draw_cinders(cv: Canvas, b: Body) -> None:
    p = b.p
    if p.cinders <= 0:
        return
    cyc = (p.phase / math.tau) % 1.0
    for k, (ox, off, rise) in enumerate(CINDERS):
        f = round(((cyc + off) % 1.0) * 48) / 48 % 1.0
        x = b.cx + ox + f * 8 * p.trail * 2 + 1.2 * math.sin(p.phase + k)
        y = b.cy - 14 - f * rise * p.flame
        c = FIRE[6] if f < 0.3 else FIRE[5] if f < 0.6 else FIRE[3] if f < 0.85 else FIRE[1]
        cv.put(round(x), round(y), c, solid=False)
        if f < 0.4 and k % 2 == 0:
            cv.put(round(x), round(y) + 1, FIRE[3], solid=False)


def draw_shards(cv: Canvas, b: Body, prog: float) -> None:
    if prog <= 0:
        return
    for k in range(10):
        dirx = (hash01(k, 1, 13) - 0.5) * 2
        x = CX + b.p.dx + dirx * (6 + 26 * prog)
        y = GROUND - 2 - math.sin(min(1.0, prog) * math.pi) * (6 + 8 * hash01(k, 2, 13)) - 2 * (1 - prog)
        y = min(y, GROUND)
        cv.put(x, y, BONE[4] if k % 3 else BONE[3])
        if k % 2:
            cv.put(x + 1, y, BONE[2])


# ---------------------------------------------------------------- render
def render(p: Pose, t: float = 0.0) -> Canvas:
    cv = Canvas(CELL_W, CELL_H)
    if p.dissolve >= 1:
        return cv
    b = Body(p)
    draw_fire(cv, b)
    draw_smoke(cv, b, p.smoke)
    draw_horns(cv, b)
    draw_skull(cv, b)
    draw_shards(cv, b, p.shards)
    outline(cv, OUTLINE)
    # lights (before the eyes, so their cold core stays crisp)
    if p.flame > 0.1:
        gx, gy = b.to_cell(0, -6)
        cv.glow(gx, gy, 18 + 6 * p.flame, FIRE[4], 0.12 * p.heat * p.flame * (1 - p.gutter), halo=False)
    if p.eye > 0.05:
        for ex in (-6.8, 5.0):
            x, y = b.to_cell(ex + 0.3, 2.2)
            cv.glow(x, y, 3.5 + 2 * p.eye, EYE[0], 0.35 * p.eye, halo=False)
    draw_eyes(cv, b)
    draw_jet(cv, b, p.jet, p.jet_fade)
    draw_ring(cv, b, p.ring, p.ring_fade)
    draw_cinders(cv, b)
    for (mx, my, lv) in p.motes:
        cv.put(mx, my, ASH[lv] if lv < 3 else FIRE[lv], solid=False)
    flash(cv, p.flash)
    if p.dissolve > 0:
        dissolve(cv, p.dissolve, b.cy - 26, GROUND + 2, FIRE[5], FIRE[2], upward=False)
    return cv


# ---------------------------------------------------------------- animations
IDLE_FRAMES = 12


def idle_pose(i: int, n: int = IDLE_FRAMES) -> Pose:
    a = math.tau * i / n
    return Pose(
        dy=round(2 * math.sin(a)), phase=a,
        flame=1.0 + 0.06 * math.sin(2 * a), heat=1.0 + 0.05 * math.sin(2 * a + 1),
        jaw=0.22 if i in (7, 9) else 0.0,
        eye=1.0 + 0.12 * math.sin(2 * a) - (0.25 if i == 4 else 0.0),
    )


def idle_frames():
    return [(idle_pose(i), 110) for i in range(IDLE_FRAMES)]


def attack_frames():
    """Llamarada: rear back (flames flare), gape, lunge left spewing a fire jet."""
    b = idle_pose(0)
    return [
        (replace(b, dx=3, dy=-2, tilt=0.08, flame=1.2, heat=1.15, eye=1.3, jaw=0.25, phase=0.5,
                 trail=0.6), 100),
        (replace(b, dx=5, dy=-4, tilt=0.15, flame=1.45, heat=1.3, eye=1.6, jaw=0.7, phase=1.0,
                 trail=0.75, sy=1.04, sx=0.97), 130),
        (replace(b, dx=-8, dy=0, tilt=-0.05, flame=1.15, heat=1.3, eye=1.5, jaw=1.0, phase=1.6,
                 trail=1.3, jet=0.5, sx=1.05, sy=0.96), 55),
        (replace(b, dx=-10, dy=1, tilt=-0.07, flame=1.1, heat=1.3, eye=1.5, jaw=1.0, phase=2.1,
                 trail=1.4, jet=1.0, sx=1.06, sy=0.95), 60),
        (replace(b, dx=-9, dy=1, tilt=-0.05, flame=1.05, heat=1.2, eye=1.35, jaw=0.95, phase=2.7,
                 trail=1.2, jet=1.0, jet_fade=0.3), 80),
        (replace(b, dx=-6, dy=1, tilt=-0.03, eye=1.2, jaw=0.6, phase=3.4, trail=0.9, jet=1.0,
                 jet_fade=0.6, smoke=0.2), 85),
        (replace(b, dx=-3, dy=0, eye=1.1, jaw=0.3, phase=4.2, trail=0.65, jet=1.0, jet_fade=0.88,
                 smoke=0.1), 90),
        (replace(b, dx=-1, jaw=0.08, phase=5.2, trail=0.5), 90),
        (b, 110),
    ]


def cast_frames():
    """Avivar: the skull rises roaring, its fire swells white-hot, a ring of sparks bursts."""
    b = idle_pose(0)
    steps = [  # dy, flame, heat, jaw, eye, ring, ring_fade
        (-1, 1.2, 1.1, 0.3, 1.2, 0.0, 0.0),
        (-3, 1.5, 1.35, 0.7, 1.5, 0.2, 0.0),
        (-4, 1.75, 1.6, 1.0, 1.8, 0.5, 0.0),
        (-4, 1.85, 1.7, 1.0, 1.8, 0.8, 0.1),
        (-4, 1.7, 1.5, 0.85, 1.6, 1.0, 0.45),
        (-3, 1.4, 1.3, 0.5, 1.35, 1.0, 0.8),
        (-2, 1.15, 1.1, 0.2, 1.15, 0.0, 0.0),
        (-1, 1.03, 1.02, 0.05, 1.05, 0.0, 0.0),
    ]
    out = []
    for k, (dy, fl, ht, jaw, eye, ring, rf) in enumerate(steps):
        out.append((replace(b, dy=dy, flame=fl, heat=ht, jaw=jaw, eye=eye, ring=ring, ring_fade=rf,
                            phase=0.55 * (k + 1), trail=0.3, sy=1.0 + 0.02 * jaw), 90 if k < 5 else 85))
    out.append((b, 110))
    return out


def hurt_frames():
    b = idle_pose(0)
    return [
        (replace(b, dx=4, sx=1.07, sy=0.93, tilt=-0.08, flash=0.82, jaw=0.4, flame=0.6, gutter=0.55,
                 eye=0.5, phase=0.9, trail=0.9), 55),
        (replace(b, dx=5, sx=1.03, sy=0.97, tilt=-0.05, flash=0.55, jaw=0.3, flame=0.5, gutter=0.7,
                 smoke=0.35, eye=0.6, phase=1.6, trail=0.8), 60),
        (replace(b, dx=4, flash=0.25, jaw=0.15, flame=0.7, gutter=0.4, smoke=0.2, eye=0.8,
                 phase=2.4, trail=0.6), 70),
        (replace(b, dx=2, flame=0.9, gutter=0.15, eye=0.95, phase=3.3), 80),
        (replace(b, dx=1, phase=4.6), 100),
        (b, 110),
    ]


def death_frames():
    b = idle_pose(0)
    out = [
        (replace(b, dx=4, sx=1.06, sy=0.94, flash=0.85, crack=0.3, eye=1.6, jaw=0.5, flame=0.8,
                 phase=0.6), 70),
        (replace(b, dx=3, flash=0.3, crack=0.6, eye=1.8, jaw=1.0, flame=1.25, heat=1.3, phase=1.2), 100),
        (replace(b, dx=2, crack=1.0, eye=0.9, jaw=0.7, flame=0.75, gutter=0.4, smoke=0.3,
                 phase=1.8), 90),
        (replace(b, dx=1, dy=4, crack=1.0, eye=0.45, jaw=0.5, flame=0.45, gutter=0.8, smoke=0.6,
                 phase=2.4, cinders=0.0), 85),
        (replace(b, dy=10, tilt=-0.06, crack=1.0, eye=0.15, jaw=0.6, flame=0.2, gutter=1.0,
                 smoke=0.8, phase=3.0, cinders=0.0), 85),
        (replace(b, dy=16, tilt=-0.1, crack=1.0, eye=0.0, jaw=0.8, flame=0.0, smoke=0.9,
                 phase=3.6, cinders=0.0), 75),
    ]
    # impact on the floor, then the skull crumbles top-down into ash and cinders
    for k in range(6):
        u = k / 5
        motes = tuple(
            (CX - 22 + hash01(k, j, 9) * 44,
             GROUND - 4 - (8 + 26 * u) * hash01(j, k, 4) - 4 * u,
             (j % 3) if j % 4 else 4 + (j % 3 == 0))
            for j in range(6 + 3 * k))
        out.append((replace(b, dy=19, tilt=-0.12, sx=1.08 if k == 0 else 1.0,
                            sy=0.92 if k == 0 else 1.0, crack=1.0, eye=0.0, jaw=0.85, flame=0.0,
                            smoke=max(0.0, 0.7 - 0.15 * k), phase=4.0 + 0.4 * k, cinders=0.0,
                            shards=0.25 + 0.15 * k, dissolve=0.12 + 0.17 * k if k else 0.0,
                            motes=motes), 80 if k == 0 else 85))
    out.append((replace(b, dissolve=1.0), 120))
    return out


ANIMATIONS = {
    "idle": (idle_frames, True),
    "attack": (attack_frames, False),
    "cast": (cast_frames, False),
    "hurt": (hurt_frames, False),
    "death": (death_frames, False),
}

# Frame where the fire jet is longest and reaches the hero.
EVENTS = {"attack": {"strikes": [3]}}
MOVES = {"flame": "attack", "stoke": "cast", "vengeance": "cast"}


def build():
    return build_sheet(ANIMATIONS, render, (CELL_W, CELL_H), ANCHOR, f"{SHEET_ID}_sheet.png",
                       {"events": EVENTS, "moves": MOVES})


def main() -> None:
    sheet, meta = build()
    save_sheet(OUT_DIR, SHEET_ID, sheet, meta)
    print(f"wrote assets/enemies/{SHEET_ID}_sheet.png ({len(sheet[0])}x{len(sheet)}) and .json")


if __name__ == "__main__":
    main()
