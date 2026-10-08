"""Draw and animate the enemy "Murciélago Vampiro" (a vampire bat). Stdlib only:

    python scripts/generate_enemy_bat.py

Same method as the Espectro (``docs/code-drawn-sprites.md``): one renderer, every
frame a ``Pose``. The bat hovers above its shadow point, facing left (the hero):

* a hunched, fuzzy body scanned as ONE mass (head, snout, pointed ears, torso)
  in a cold purple-brown fur ramp with dithered strands and a paler chest ruff;
* two membranous wings swept from the shoulders: arm and finger bones fan out
  from the wrist and the membrane between them has a scalloped trailing edge,
  thinner (lighter, translucent) towards the edge. One renderer with a ``flap``
  parameter (-1 down .. +1 raised), ``fold`` (crumple) and ``spread`` (fan);
* glowing blood-red eyes, a leaf nose, fangs with a drop of blood, tiny claws.

Animations (non-death actions end on idle frame 0):
  idle    12-frame wing-flap cycle (slow up stroke, fast down stroke), body bobs
          against the flap, an ear twitches, the blood drop swells
  attack  "Mordisco Vampírico": wings rise, swoop down-left, two bites (red bite
          arcs + blood sparks), flaps back home
  cast    "Chillido": wings spread wide, mouth open, sound-wave arcs pulse left
  hurt    white flash, knocked right and tumbling with crumpled wings, recovers
  death   wings fold, it drops to the floor and dissolves into red mist and
          little shadow bats -> empty

Output: ``assets/enemies/bat_sheet.png`` + ``.json`` (``events.attack.strikes``
lists the two bite frames).
"""
from __future__ import annotations

import math
import sys
from dataclasses import dataclass, field, replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from pixel_kit import (Canvas, bayer, build_sheet, dissolve, flash, hash01, mix,  # noqa: E402
                       outline, ramp, save_sheet, stroke)

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "assets" / "enemies"
SHEET_ID = "bat"

CELL_W, CELL_H = 144, 106
CX, GROUND = 96, 100            # body centre column, ground row
ANCHOR = (CX, GROUND + 2)       # floor point under the bat (shadow)
BODY_Y = 62                     # body centre row while hovering (feet ~23 px above the floor)

# ---------------------------------------------------------------- palette
OUTLINE = (14, 6, 18)
FUR = [(22, 13, 28), (38, 23, 44), (56, 36, 60), (78, 52, 76), (104, 72, 92), (134, 98, 114),
       (168, 134, 146)]
MEMB = [(24, 6, 22), (44, 10, 34), (68, 16, 46), (96, 26, 58), (128, 40, 70), (164, 64, 88),
        (200, 98, 112)]
BONE = [(58, 34, 50), (100, 70, 86), (148, 116, 126), (196, 170, 170)]
SKIN = [(66, 28, 44), (112, 54, 70), (164, 94, 106), (204, 140, 146)]
BLOOD = [(70, 6, 18), (140, 14, 32), (212, 40, 58), (255, 116, 128), (255, 214, 218)]
FANG = [(176, 166, 160), (240, 234, 222)]
WHITE = (255, 255, 255)

# wing geometry (native px, before the per-wing scale)
ARM_LEN = 13.0
FINGER_LEN = (12.0, 22.0, 21.0, 15.5)
FINGER_OFF = (0.45, -0.15, -0.75, -1.35)     # radians from the arm direction (fan)


@dataclass(frozen=True)
class Pose:
    dx: float = 0.0
    dy: float = 0.0
    rot: float = 0.0              # whole-body rotation (radians, + = clockwise)
    sx: float = 1.0
    sy: float = 1.0
    phase: float = 0.0
    flap: float = 0.0             # -1 wings down .. +1 raised
    fold: float = 0.0             # 0 open .. 1 folded / crumpled
    fold_far: float = 0.0         # extra fold of the far (screen-left) wing
    spread: float = 1.0           # finger fan
    reach: float = 1.0            # wing length factor
    mouth: float = 0.0            # 0 closed .. 1 wide open
    eye: float = 1.0
    ear: float = 0.0              # ear twitch
    drip: float = 1.0             # blood drop size 0..2
    drain: float = 0.0            # red life-drain glow on the chest
    flash: float = 0.0
    dissolve: float = 0.0
    bite: int = 0                 # 0 none, 1 / 2 = which bite arc
    bite_fade: float = 0.0
    waves: float = 0.0            # screech sound-wave progress
    waves_fade: float = 0.0
    motes: tuple = field(default_factory=tuple)   # (x, y, kind): 0..3 blood, 4 shadow bat
    mist: tuple = field(default_factory=tuple)    # (x, y, r, strength)


class Body:
    def __init__(self, p: Pose) -> None:
        self.p = p
        self.bx = CX + p.dx
        self.by = BODY_Y + p.dy

    def to_cell(self, lx: float, ly: float) -> tuple[float, float]:
        return self.bx + lx * self.p.sx, self.by + ly * self.p.sy


# ---------------------------------------------------------------- helpers
def _clamp(v: float) -> float:
    return 0.0 if v < 0 else 1.0 if v > 1 else v


def _wrap(a: float) -> float:
    return (a + math.pi) % math.tau - math.pi


def fill_polygon(poly):
    """Scanline fill: yields (x, y) of the pixels whose centres are inside ``poly``."""
    ys = [p[1] for p in poly]
    y0, y1 = int(math.floor(min(ys))), int(math.ceil(max(ys)))
    n = len(poly)
    for y in range(y0, y1 + 1):
        yc = y + 0.5
        xs = []
        for i in range(n):
            ax, ay = poly[i]
            bx, by = poly[(i + 1) % n]
            if (ay <= yc < by) or (by <= yc < ay):
                xs.append(ax + (yc - ay) * (bx - ax) / (by - ay))
        xs.sort()
        for k in range(0, len(xs) - 1, 2):
            for x in range(int(math.ceil(xs[k] - 0.5)), int(math.floor(xs[k + 1] - 0.5)) + 1):
                yield x, y


def in_tri(px, py, a, b, c) -> bool:
    d1 = (px - b[0]) * (a[1] - b[1]) - (a[0] - b[0]) * (py - b[1])
    d2 = (px - c[0]) * (b[1] - c[1]) - (b[0] - c[0]) * (py - c[1])
    d3 = (px - a[0]) * (c[1] - a[1]) - (c[0] - a[0]) * (py - a[1])
    neg = d1 < 0 or d2 < 0 or d3 < 0
    pos = d1 > 0 or d2 > 0 or d3 > 0
    return not (neg and pos)


def rotate(cv: Canvas, ang: float, cx: float, cy: float) -> Canvas:
    """Nearest-neighbour rotation about (cx, cy) (inverse mapping: no holes)."""
    if abs(ang) < 1e-3:
        return cv
    out = Canvas(cv.w, cv.h)
    ca, sa = math.cos(ang), math.sin(ang)
    for y in range(cv.h):
        for x in range(cv.w):
            rx, ry = x + 0.5 - cx, y + 0.5 - cy
            sx = int(math.floor(cx + ca * rx + sa * ry))
            sy = int(math.floor(cy - sa * rx + ca * ry))
            if 0 <= sx < cv.w and 0 <= sy < cv.h and cv.px[sy][sx] is not None:
                out.px[y][x] = cv.px[sy][sx]
                out.solid[y][x] = cv.solid[sy][sx]
    return out


# ---------------------------------------------------------------- wings
def wing_geometry(b: Body, side: int, scale: float):
    """Shoulder, wrist, finger tips and hip of one wing (side -1 = screen left)."""
    p = b.p
    k = scale * p.reach
    fold = _clamp(p.fold + (p.fold_far if side < 0 else 0.0))
    sx_, sy_ = b.to_cell(side * (7 if side > 0 else 8), -5)
    hip = b.to_cell(side * 6.5, 8)
    theta = 0.35 + 0.95 * p.flap - 0.9 * fold          # arm angle above the outward horizontal
    arm = ARM_LEN * k * (1 - 0.35 * fold)
    wx = sx_ + side * arm * math.cos(theta)
    wy = sy_ - arm * math.sin(theta)
    fan = p.spread * (1 - 0.7 * fold)
    tips = []
    for off, ln in zip(FINGER_OFF, FINGER_LEN):
        a = theta + off * fan - 0.6 * fold
        L = ln * k * (1 - 0.62 * fold)
        tips.append((wx + side * L * math.cos(a), wy - L * math.sin(a)))
    return (sx_, sy_), (wx, wy), tips, hip


def _scallop(a, c, toward, depth_k: float, n: int = 7):
    """Points from a to c bowing in towards ``toward`` (the membrane's scalloped edge)."""
    mx, my = (a[0] + c[0]) / 2, (a[1] + c[1]) / 2
    vx, vy = toward[0] - mx, toward[1] - my
    d = math.hypot(vx, vy) or 1.0
    depth = depth_k * math.hypot(c[0] - a[0], c[1] - a[1])
    out = []
    for i in range(1, n):
        s = i / n
        bow = depth * math.sin(math.pi * s)
        out.append((a[0] + (c[0] - a[0]) * s + vx / d * bow, a[1] + (c[1] - a[1]) * s + vy / d * bow))
    return out


def draw_wing(cv: Canvas, b: Body, side: int, scale: float, shade: float) -> None:
    p = b.p
    sh, wr, tips, hip = wing_geometry(b, side, scale)
    # membrane outline: shoulder -> wrist -> tips (scalloped between) -> hip
    poly = [sh, wr, tips[0]]
    for a, c in zip(tips, tips[1:]):
        poly += _scallop(a, c, wr, 0.27)
        poly.append(c)
    poly += _scallop(tips[-1], hip, wr, 0.16)
    poly.append(hip)
    angs = [math.atan2(t[1] - wr[1], t[0] - wr[0]) for t in tips]
    lmax = max(math.hypot(t[0] - wr[0], t[1] - wr[1]) for t in tips) or 1.0
    top = min(q[1] for q in poly)
    height = max(1.0, max(q[1] for q in poly) - top)
    pix = set(fill_polygon(poly))
    for x, y in pix:
        rx, ry = x + 0.5 - wr[0], y + 0.5 - wr[1]
        r = math.hypot(rx, ry)
        a = math.atan2(ry, rx)
        dmin = min(abs(_wrap(a - g)) for g in angs)
        between = _clamp(dmin / 0.32) if r > 3 else 0.4
        # membrane gets thinner (lit, translucent) away from the wrist and between bones
        light = 0.18 + 0.48 * _clamp(r / lmax) ** 1.3 + 0.16 * between
        light += 0.18 * (1 - (y + 0.5 - top) / height) - 0.08 * side + shade
        # darker near the body (thick skin), fine wrinkles along the bones
        hd = math.hypot(x + 0.5 - sh[0], y + 0.5 - sh[1])
        light -= 0.16 * _clamp(1 - hd / 9)
        if between > 0.55 and math.sin(r * 1.3 + a * 3) > 0.9:
            light -= 0.1
        # thin, light-catching trailing edge (reads as a translucent membrane)
        if r > 0.45 * lmax and ((x - 1, y) not in pix or (x, y + 1) not in pix or (x + 1, y) not in pix):
            light += 0.22
        cv.put(x, y, ramp(MEMB, _clamp(light), x, y))
    # bones: forearm (bowed at the elbow), then the fingers fanning from the wrist
    ex = (sh[0] + wr[0]) / 2 + side * 0.5
    ey = (sh[1] + wr[1]) / 2 + 2.0
    bones = BONE if shade > -0.05 else BONE[:-1]
    stroke(cv, [sh, (ex, ey), wr], lambda t: 1.7 - 0.6 * t, bones, shade=shade)
    for tip in tips:
        stroke(cv, [wr, tip], lambda t: 0.95 - 0.35 * t, bones, shade=shade - 0.05, min_r=0.6)
    # thumb claw on the wrist, pointing up/out
    tx, ty = wr[0] + side * 1.0, wr[1] - 1.5
    cv.put(tx, ty, BONE[3])
    cv.put(tx + side, ty - 1, FANG[0])


# ---------------------------------------------------------------- body mass
def _fringe(lx: float, ly: float, cx: float, cy: float, amp: float, seed: int) -> float:
    ang = math.atan2(ly - cy, lx - cx)
    return 1.0 + amp * hash01(int((ang + math.pi) * 7), seed, 11)


EAR_L = ((-9.5, -15.5), (-4.0, -18.5), (-12.5, -25.5))
EAR_R = ((-1.5, -18.5), (4.5, -15.5), (3.0, -26.0))


def _ears(p: Pose):
    tw = p.ear
    l = (EAR_L[0], EAR_L[1], (EAR_L[2][0] - 2.0 * tw, EAR_L[2][1] + 1.5 * tw))
    return l, EAR_R


def body_part(lx: float, ly: float, p: Pose):
    """Which part of the single mass (lx, ly) belongs to, or None."""
    # snout
    if ((lx + 9.5) / 3.6) ** 2 + ((ly + 10.5) / 3.1) ** 2 <= 1.0:
        return "snout"
    dh = ((lx + 3) ** 2 + (ly + 12) ** 2) / 49.0
    if dh <= _fringe(lx, ly, -3, -12, 0.12, 2) ** 2:
        return "head"
    el, er = _ears(p)
    if in_tri(lx, ly, *el):
        return "ear_l"
    if in_tri(lx, ly, *er):
        return "ear_r"
    t = (ly - 1) / 11.0
    a = 8.8 - 1.6 * t
    dt = (lx / a) ** 2 + t * t
    amp = 0.3 if ly > -2 else 0.14
    if dt <= _fringe(lx, ly, 0, 1, amp, 5) ** 2:
        return "torso"
    return None


def draw_body(cv: Canvas, b: Body) -> None:
    p = b.p
    el, er = _ears(p)
    for y in range(int(b.by - 30 * p.sy), int(b.by + 16 * p.sy) + 1):
        for x in range(int(b.bx - 18 * p.sx), int(b.bx + 15 * p.sx) + 1):
            lx = (x + 0.5 - b.bx) / p.sx
            ly = (y + 0.5 - b.by) / p.sy
            part = body_part(lx, ly, p)
            if part is None:
                continue
            fur = True
            if part == "torso":
                t = (ly - 1) / 11.0
                nx, ny = lx / (8.8 - 1.6 * t), t
                light = 0.6 - 0.38 * nx - 0.34 * ny - 0.14 * (nx * nx + ny * ny)
                if nx < -0.72 and ny < 0.35:
                    light += 0.12
                # pale chest ruff under the chin, ragged lower edge
                ruff = -9.5 < ly < -1.5 + 1.6 * math.sin(lx * 1.7) and abs(lx + 2.5) < 7.5
                if ruff:
                    light += 0.26 + 0.08 * math.sin(lx * 2.3 + ly)
            elif part == "head":
                nx, ny = (lx + 3) / 7, (ly + 12) / 7
                light = 0.72 - 0.38 * nx - 0.32 * ny - 0.12 * (nx * nx + ny * ny)
            elif part == "snout":
                nx, ny = (lx + 9.5) / 3.6, (ly + 10.5) / 3.1
                light = 0.62 - 0.25 * nx - 0.3 * ny
                fur = False
            else:                                   # ears: dark outer rim, pink inner
                tri = el if part == "ear_l" else er
                cxm = sum(q[0] for q in tri) / 3
                cym = sum(q[1] for q in tri) / 3
                inner = [(q[0] + (cxm - q[0]) * 0.42, q[1] + (cym - q[1]) * 0.42 + 0.6) for q in tri]
                if in_tri(lx, ly, *inner):
                    shade = 0.55 - 0.25 * (lx - cxm) / 4 - 0.15 * (ly - cym) / 4
                    cv.put(x, y, ramp(SKIN, _clamp(shade - (0.2 if part == "ear_r" else 0)), x, y))
                    continue
                light = 0.5 - 0.06 * (lx - cxm) - (0.12 if part == "ear_r" else 0)
                fur = False
            if fur:                                  # short dithered fur strands
                n = int(3 * hash01(x // 2, y // 3, 4))
                if (2 * x + y + n) % 6 == 0:
                    light -= 0.14
                elif (x + 2 * y + n) % 7 == 3:
                    light += 0.07
            cv.put(x, y, ramp(FUR, _clamp(light), x, y))


def draw_feet(cv: Canvas, b: Body) -> None:
    p = b.p
    sw = 0.6 * math.sin(p.phase + 1.0)
    for lx0 in (-4.0, 3.0):
        x0, y0 = b.to_cell(lx0, 10.5)
        for s in range(4):
            cv.put(x0 + sw * s / 4 - (0.3 * s if lx0 < 0 else 0), y0 + s, FUR[2] if s < 2 else FUR[1])
        fx, fy = int(x0 + sw - (0.9 if lx0 < 0 else 0)), int(y0 + 4)
        cv.put(fx - 1, fy, BONE[3])
        cv.put(fx, fy, BONE[2])
        cv.put(fx + 1, fy, BONE[3])
        cv.put(fx - 1, fy + 1, BONE[1])
        cv.put(fx + 1, fy + 1, BONE[1])


def draw_face(cv: Canvas, b: Body) -> tuple[float, float, float, float]:
    """Eyes, leaf nose, mouth, fangs, blood drop. Returns eye centre and mouth point."""
    p = b.p

    def put(lx, ly, c, solid=True):
        x, y = b.to_cell(lx, ly)
        cv.put(int(math.floor(x)), int(math.floor(y)), c, solid=solid)

    e = p.eye
    # sockets + slanted eyes (inner corners low: menacing)
    for lx, ly in ((-10, -14), (-9, -14), (-8, -13), (-7, -13), (-3, -13), (-2, -13), (-1, -14), (0, -14)):
        put(lx, ly + 1, FUR[0])
    if e > 0.05:
        hot = BLOOD[4] if e > 0.7 else BLOOD[3]
        mid = BLOOD[3] if e > 0.7 else BLOOD[2]
        for lx, ly, c in ((-10, -15, BLOOD[1]), (-9, -14, mid), (-8, -14, hot), (-7, -13, mid),
                          (-3, -13, mid), (-2, -14, hot), (-1, -14, mid), (0, -15, BLOOD[1])):
            put(lx, ly, c)
    # brows
    for lx, ly in ((-10, -16), (-9, -16), (-8, -15), (-2, -15), (-1, -16), (0, -16)):
        put(lx, ly, FUR[1])
    # leaf nose and nostrils
    put(-13, -12, SKIN[2])
    put(-12, -13, SKIN[3])
    put(-12, -12, SKIN[1])
    put(-12, -11, OUTLINE)
    put(-11, -11, SKIN[1])
    # mouth
    m = p.mouth
    if m > 0.25:
        rows = 1 + int(round(2.2 * m))
        for r in range(rows + 1):
            for lx in range(-13, -7):
                c = BLOOD[0] if r < rows else FUR[1]
                if r == rows - 1 and -11 <= lx <= -9:
                    c = BLOOD[1]                       # tongue
                put(lx, -8 + r, c)
        put(-13, -8, FANG[1])
        put(-13, -7, FANG[0])
        put(-10, -8, FANG[1])
        put(-10, -7, FANG[0])
        put(-13, -8 + rows, FANG[0])                   # lower fangs
        put(-9, -8 + rows, FANG[0])
    else:
        for lx in range(-13, -8):
            put(lx, -8, OUTLINE)
        put(-12, -7, FANG[1])
        put(-10, -7, FANG[1])
        put(-12, -6, FANG[0])
        # drop of blood hanging off the fang
        if p.drip > 0.3:
            put(-12, -5, BLOOD[2])
            if p.drip > 1.2:
                put(-12, -4, BLOOD[1])
                put(-13, -5, BLOOD[1])
    ex, ey = b.to_cell(-5, -14)
    mx, my = b.to_cell(-12, -7)
    return ex, ey, mx, my


# ---------------------------------------------------------------- effects
def draw_bite(cv: Canvas, mx: float, my: float, which: int, fade: float) -> None:
    """Two red jaw crescents snapping shut in front of the mouth, teeth marks and a blood spark."""
    if which <= 0:
        return
    size = 1.0 + 0.25 * (which - 1)
    tip = (mx - 15 * size, my + (0 if which == 1 else 2))         # where the jaws meet
    for sgn in (-1, 1):                                          # upper jaw, lower jaw
        start = (mx - 2, my + sgn * 8 * size)
        ctrl = (mx - 13 * size, my + sgn * 9 * size)
        n = 26
        for i in range(n):
            s = i / (n - 1)
            if hash01(i, which * 3 + sgn, 3) < fade * 1.1:
                continue
            x = (1 - s) ** 2 * start[0] + 2 * (1 - s) * s * ctrl[0] + s * s * tip[0]
            y = (1 - s) ** 2 * start[1] + 2 * (1 - s) * s * ctrl[1] + s * s * tip[1]
            thick = math.sin(math.pi * min(1.0, 0.15 + s * 0.85))
            for w in range(1 + int(thick * 2.2)):
                yy = y + sgn * w                                 # thickness grows outward
                c = BLOOD[4] if w == 0 and thick > 0.7 else BLOOD[3] if w == 0 else BLOOD[2] if w == 1 else BLOOD[1]
                cv.put(x, yy, c, solid=False)
            if 0.2 < s < 0.8 and i % 5 == 2 and fade < 0.5:      # teeth pointing in
                cv.put(x, y - sgn, FANG[1], solid=False)
                cv.put(x, y - 2 * sgn, FANG[0], solid=False)
    # blood spark at the bite point, thrown out to the left
    for j in range(9 + 3 * which):
        h1, h2 = hash01(j, which, 21), hash01(which, j, 22)
        spread = 0.5 + fade * 1.3
        ang = math.pi + (h2 - 0.5) * 2.2
        dist = (2 + h1 * 9) * spread
        x = tip[0] + math.cos(ang) * dist
        y = tip[1] + math.sin(ang) * dist + fade * 5 * h1
        if hash01(j, 7, which) < fade * 0.8:
            continue
        cv.put(x, y, BLOOD[3] if h2 > 0.6 else BLOOD[2], solid=False)
        if h1 > 0.6:
            cv.put(x + 1, y, BLOOD[1], solid=False)
    if fade < 0.3:
        cv.put(tip[0], tip[1], WHITE, solid=False)
        for ox, oy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            cv.put(tip[0] + ox, tip[1] + oy, BLOOD[4], solid=False)


def draw_waves(cv: Canvas, mx: float, my: float, prog: float, fade: float) -> None:
    """Concentric screech arcs pulsing out to the left of the open mouth."""
    if prog <= 0:
        return
    for k in range(4):
        r = 5 + 78 * (prog - 0.2 * k)
        if r < 4:
            continue
        life = 1 - r / 92
        strength = life * (1 - fade)
        if strength <= 0.05:
            continue
        span = 0.55 + 0.25 * (r / 80)
        n = int(r * 2 * span * 1.6) + 6
        for i in range(n):
            a = math.pi - span + 2 * span * i / (n - 1)
            for w in range(2):
                rr = r - w * 1.4
                x = mx + math.cos(a) * rr
                y = my + math.sin(a) * rr * 0.9
                if bayer(int(x), int(y)) > strength * 2.2 + 0.15:
                    continue
                edge = abs(i / (n - 1) - 0.5) * 2
                c = BLOOD[4] if w == 0 and edge < 0.5 else BLOOD[3] if w == 0 else BLOOD[1]
                cv.put(x, y, c, solid=False, alpha=int(255 * min(1.0, 0.35 + strength)))


def draw_mist(cv: Canvas, mist) -> None:
    for (x0, y0, r, s) in mist:
        for y in range(int(y0 - r) - 1, int(y0 + r) + 2):
            for x in range(int(x0 - r) - 1, int(x0 + r) + 2):
                d = math.hypot(x + 0.5 - x0, y + 0.5 - y0) / max(0.5, r)
                if d > 1 or bayer(x, y) > (1.2 - d) * s:
                    continue
                c = BLOOD[2] if d < 0.35 else BLOOD[1] if d < 0.75 else MEMB[2]
                cv.put(x, y, c, solid=False, alpha=int(255 * min(1.0, 0.4 + s * 0.6)))


def draw_motes(cv: Canvas, motes) -> None:
    for (x, y, kind) in motes:
        if kind < 4:
            cv.put(x, y, BLOOD[min(4, 1 + kind)], solid=False)
        else:                                          # a tiny shadow bat: ^v^
            x, y = int(x), int(y)
            flap = (x + y) % 2
            for ox, oy in ((-2, -flap), (-1, 0), (0, 1), (1, 0), (2, -flap)):
                cv.put(x + ox, y + oy, MEMB[3], solid=False)
            cv.put(x, y, FUR[4], solid=False)
            cv.put(x - 1 if flap else x, y - 1 if flap else y, BLOOD[3], solid=False)


# ---------------------------------------------------------------- render
def render(p: Pose, t: float = 0.0) -> Canvas:
    b = Body(p)
    fig = Canvas(CELL_W, CELL_H)
    draw_wing(fig, b, -1, 0.86, -0.12)              # far wing (screen left), smaller and darker
    draw_wing(fig, b, 1, 1.0, 0.0)                  # near wing
    body = Canvas(CELL_W, CELL_H)
    draw_body(body, b)
    draw_feet(body, b)
    eye_mouth = draw_face(body, b)
    fig.blit(body, rim=OUTLINE)                     # dark rim where the body crosses the wings
    if abs(p.rot) > 1e-3:
        fig = rotate(fig, p.rot, b.bx, b.by)
        ca, sa = math.cos(p.rot), math.sin(p.rot)

        def rot(x, y):
            rx, ry = x - b.bx, y - b.by
            return b.bx + ca * rx - sa * ry, b.by + sa * rx + ca * ry
        ex, ey = rot(eye_mouth[0], eye_mouth[1])
        mx, my = rot(eye_mouth[2], eye_mouth[3])
    else:
        ex, ey, mx, my = eye_mouth
    outline(fig, OUTLINE)
    cv = fig
    if p.eye > 0.05:
        cv.glow(ex, ey, 4 + 1.5 * p.eye, BLOOD[2], 0.28 * p.eye)
    if p.drain > 0:
        cx_, cy_ = b.to_cell(-1, 0)
        cv.glow(cx_, cy_, 13, BLOOD[2], 0.45 * p.drain, halo=False)
    draw_bite(cv, mx, my, p.bite, p.bite_fade)
    draw_waves(cv, mx, my, p.waves, p.waves_fade)
    flash(cv, p.flash)
    if p.dissolve > 0:
        dissolve(cv, p.dissolve, b.by - 34, CELL_H + 2, BLOOD[3], BLOOD[1], upward=False, seed=7)
    draw_mist(cv, p.mist)
    draw_motes(cv, p.motes)
    return cv


# ---------------------------------------------------------------- animations
IDLE_FRAMES = 12


def _wing_cycle(a: float) -> float:
    """-1 down .. +1 up; warped so the up stroke is slow and the down stroke fast."""
    w = a + 0.55 * math.cos(a)
    return -math.cos(w)


def idle_pose(i: int, n: int = IDLE_FRAMES) -> Pose:
    i %= n
    a = math.tau * i / n
    f = _wing_cycle(a)
    lift = _wing_cycle(a - 0.9)                      # body lags the wings
    return Pose(
        dy=round(2.0 * lift), phase=a, flap=0.12 + 0.62 * f,
        spread=1.0 + 0.06 * math.sin(a), sy=1.0 + 0.03 * f, sx=1.0 - 0.02 * f,
        ear=1.0 if i in (5, 6) else 0.0, eye=0.8 if i == 9 else 1.0,
        drip=1.0 + 0.8 * math.sin(a - 1.0),
    )


def idle_frames():
    return [(idle_pose(i), 105) for i in range(IDLE_FRAMES)]


def attack_frames():
    """Mordisco Vampírico: wings rise, swoop down-left, bite twice, flap home."""
    b = idle_pose(0)
    return [
        (replace(b, dx=4, dy=1, flap=0.95, spread=1.1, eye=1.3, mouth=0.4, sy=1.04, phase=0.4), 110),
        (replace(b, dx=7, dy=-3, flap=1.15, spread=1.15, eye=1.5, mouth=0.6, sy=1.06, sx=0.96,
                 rot=0.12, phase=0.8), 120),
        (replace(b, dx=-30, dy=8, flap=-0.7, fold=0.25, eye=1.5, mouth=0.8, rot=-0.3, sx=1.05,
                 sy=0.95, phase=1.3), 60),
        (replace(b, dx=-50, dy=12, flap=-0.1, fold_far=0.25, eye=1.5, mouth=1.0, rot=-0.18, phase=1.8), 55),
        (replace(b, dx=-57, dy=13, flap=0.35, fold_far=0.4, eye=1.6, mouth=0.1, drip=2.0, rot=-0.1, bite=1,
                 drain=0.5, phase=2.2), 60),
        (replace(b, dx=-51, dy=11, flap=0.75, fold_far=0.3, eye=1.4, mouth=1.0, rot=-0.05, bite=1, bite_fade=0.7,
                 drain=0.3, phase=2.6), 70),
        (replace(b, dx=-58, dy=14, flap=-0.2, fold_far=0.4, eye=1.6, mouth=0.1, drip=2.0, rot=-0.12, bite=2,
                 drain=0.9, phase=3.0), 60),
        (replace(b, dx=-42, dy=5, flap=0.95, eye=1.3, mouth=0.3, drip=2.0, bite=2, bite_fade=0.75,
                 drain=0.5, rot=0.06, phase=3.6), 80),
        (replace(b, dx=-20, dy=-3, flap=-0.6, eye=1.15, drain=0.2, rot=0.04, phase=4.3), 80),
        (replace(b, dx=-6, dy=-1, flap=0.4, phase=5.2), 90),
        (b, 100),
    ]


def cast_frames():
    """Chillido: wings spread wide, mouth open, sound-wave arcs pulse to the left."""
    b = idle_pose(0)
    out = [
        (replace(b, dy=1, flap=0.85, mouth=0.3, eye=1.15, phase=0.3), 90),
        (replace(b, dy=-1, flap=1.05, spread=1.1, mouth=0.5, eye=1.3, sy=1.04, phase=0.6), 90),
        (replace(b, dy=-2, flap=0.3, spread=1.35, reach=1.18, mouth=1.0, eye=1.6, sx=1.04, sy=0.97,
                 waves=0.12, phase=0.9), 70),
    ]
    for k, w in enumerate((0.32, 0.52, 0.72, 0.92)):
        out.append((replace(b, dx=(-1 if k % 2 == 0 else 1), dy=-2, flap=0.3 + 0.06 * (k % 2),
                            spread=1.35, reach=1.18, mouth=1.0, eye=1.6, sx=1.04, sy=0.97,
                            waves=w, phase=1.2 + 0.3 * k), 75))
    out += [
        (replace(b, dy=-1, flap=0.55, spread=1.15, reach=1.08, mouth=0.5, eye=1.25, waves=1.05,
                 waves_fade=0.6, phase=2.6), 80),
        (replace(b, flap=0.2, mouth=0.1, phase=3.4), 90),
        (b, 100),
    ]
    return out


def hurt_frames():
    b = idle_pose(0)
    return [
        (replace(b, dx=7, dy=-1, rot=0.35, fold=0.6, flap=-0.3, eye=0.4, mouth=0.6, flash=0.85,
                 sx=0.95, sy=1.05, phase=1.0), 55),
        (replace(b, dx=10, dy=0, rot=0.6, fold=0.7, flap=-0.2, eye=0.5, mouth=0.6, flash=0.55,
                 phase=1.5), 60),
        (replace(b, dx=9, dy=1, rot=0.42, fold=0.45, flap=0.2, eye=0.7, mouth=0.4, flash=0.25,
                 phase=2.0), 70),
        (replace(b, dx=6, dy=1, rot=0.2, fold=0.2, flap=0.7, eye=0.9, phase=2.6), 75),
        (replace(b, dx=3, rot=0.06, flap=0.15, phase=3.3), 80),
        (replace(b, dx=1, flap=-0.35, phase=4.2), 85),
        (b, 100),
    ]


def death_frames():
    b = idle_pose(0)
    out = [
        (replace(b, dx=4, rot=0.2, fold=0.4, flap=0.2, eye=0.5, mouth=0.7, flash=0.85), 70),
        (replace(b, dx=5, dy=-2, rot=0.1, flap=1.1, spread=1.2, eye=1.7, mouth=1.0, flash=0.35), 90),
    ]
    for k, (dy, fold, rot) in enumerate(((6, 0.5, 0.25), (13, 0.75, 0.4), (20, 0.95, 0.55), (23, 1.0, 0.62))):
        out.append((replace(b, dx=6 + k, dy=dy, fold=fold, flap=-0.6 - 0.1 * k, rot=rot, eye=1.2 - 0.25 * k,
                            mouth=0.6, sy=0.86 if k == 3 else 1.0, sx=1.1 if k == 3 else 1.0,
                            phase=1.0 + 0.4 * k), (70, 70, 60, 90)[k]))
    steps = 7
    base = replace(b, dx=9, dy=23, fold=1.0, flap=-0.9, rot=0.62, eye=0.3, mouth=0.4, sy=0.9, sx=1.06)
    for k in range(steps):
        u = (k + 1) / steps
        mist = tuple((CX + 9 - 14 + hash01(k, j, 31) * 30 - u * 10 * hash01(j, 2, 3),
                      GROUND - 14 - u * 26 * (0.5 + hash01(j, k, 32)) - j * 2,
                      3.0 + 6.0 * u * (0.5 + hash01(j, 3, 33)), max(0.0, 1.1 - u * 0.8))
                     for j in range(4 + k // 2))
        motes = tuple((CX + 9 - 20 + hash01(j, k, 41) * 36 - u * 22 * hash01(j, 1, 42),
                       GROUND - 12 - u * 50 * (0.4 + hash01(j, 0, 43)),
                       4 if (j % 4 == 0 and u > 0.2) else int(hash01(k, j, 44) * 4))
                      for j in range(6 + k))
        out.append((replace(base, eye=0.3 * (1 - u), dissolve=min(1.0, 0.15 + u * 0.9), mist=mist,
                            motes=motes, phase=2.6 + 0.3 * k), 85))
    out.append((replace(base, dissolve=1.0, eye=0.0), 120))
    return out


ANIMATIONS = {
    "idle": (idle_frames, True),
    "attack": (attack_frames, False),
    "hurt": (hurt_frames, False),
    "cast": (cast_frames, False),
    "death": (death_frames, False),
}

# Frames where each bite lands.
EVENTS = {"attack": {"strikes": [4, 6]}}
MOVES = {"bite": "attack", "dive": "attack", "screech": "cast", "vengeance": "cast"}


def build():
    return build_sheet(ANIMATIONS, render, (CELL_W, CELL_H), ANCHOR, f"{SHEET_ID}_sheet.png",
                       {"events": EVENTS, "moves": MOVES})


def main() -> None:
    sheet, meta = build()
    save_sheet(OUT_DIR, SHEET_ID, sheet, meta)
    print(f"wrote assets/enemies/{SHEET_ID}_sheet.png ({len(sheet[0])}x{len(sheet)}) and .json")


if __name__ == "__main__":
    main()
