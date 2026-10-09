"""Draw and animate the elite enemy "Gárgola" (a living cathedral gargoyle). Stdlib only:

    python scripts/generate_elite_gargoyle.py

Same method as the Espectro, the golem and the floor-1 bosses (``docs/code-drawn-sprites.md``):
one renderer, every frame a frozen ``Pose``. Identity "Piel de Piedra": it turns to stone
for a huge block, then dives at the hero with its claws.

* The creature is ONE z-buffered mass of shaded stone ellipsoids and tapered tubes (haunches,
  pelvis, belly, chest, hunched back, neck, demonic head with snout, cheek, brow ridge, open
  jaw, pointed ear, curved horns, long arms, tail with a spade tip). Every pixel takes the
  front-most surface; parts of the same group (the torso) merge smoothly, and a dark crease /
  cast shadow appears only where one part really sits in front of another (an arm over the
  chest), so it reads as one carved body, not a pile of pieces.
* Light from the upper left with slightly chiselled facets, speckle, pits, carved cracks and
  yellow-green / orange lichen on the upward faces; cool blue-violet weathered stone.
* Two bat wings of stone (far one darker, behind; near one on top with a dark rim): arm and
  finger bones fan from the wrist, scalloped membrane with darker veins.
* Glowing amber eyes under a heavy brow and a faint amber glow in the throat are the accent.
* It crouches on a warm-grey cracked plinth (stays on the ground) with its claws over the edge.

Animations (non-death actions end exactly on idle frame 0):
  idle     12-frame breathing loop: shoulders rise 1 px, wings twitch, tail tip sways, eyes
           flicker, a pebble trickles off the plinth
  attack   "Zarpazo de Piedra": rears back with the claw raised, lunges off the plinth edge with
           a bright claw arc, eased return (strike frame 3)
  dive     "Picado": crouches, leaps with wings spread, dives at the hero and rakes three times,
           flaps back and lands on the plinth with dust (strikes 6, 9, 12)
  petrify  "Petrificar": wraps its wing around itself, the colour drains into pale flat stone
           with cracks and dust puffs, holds, then the stone skin flakes off
  cast     "Despertar": spreads its wings wide and roars, eyes and throat blaze, chips fly
  hurt     white flash, chips knocked off, small recoil
  death    amber cracks spread, it crumbles together with the plinth into rubble that sinks
           and dissolves -> empty

Output: ``assets/enemies/gargoyle_sheet.png`` + ``.json`` (``events``, ``moves``, ``boss``,
``elite``).
"""
from __future__ import annotations

import math
import sys
from dataclasses import dataclass, field, replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from pixel_kit import (Canvas, bayer, build_sheet, dissolve, flash, hash01, mix,  # noqa: E402
                       outline, polyline, ramp, save_sheet, smooth)

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "assets" / "enemies"
SHEET_ID = "gargoyle"

CELL_W, CELL_H = 208, 120
CX, GROUND = 140, 112            # body centre column, ground row
ANCHOR = (CX, GROUND + 2)
PT = GROUND - 15                 # top row of the plinth's top face
FOOT_Y = PT + 1                  # the creature's feet stand on this row

# ---------------------------------------------------------------- palette
OUTLINE = (16, 12, 26)
STONE = [(21, 18, 33), (33, 30, 50), (48, 45, 68), (65, 62, 87), (86, 83, 109), (110, 107, 133),
         (138, 135, 157), (170, 167, 186), (206, 204, 218)]
WING = [(20, 16, 32), (31, 27, 47), (44, 40, 64), (60, 56, 84), (78, 74, 104), (99, 96, 126),
        (124, 122, 150)]
PLINTH = [(27, 24, 30), (41, 38, 44), (57, 53, 58), (75, 70, 73), (96, 90, 91), (120, 113, 111),
          (148, 140, 135), (178, 171, 163)]
LICHEN = [(58, 72, 40), (88, 106, 52), (126, 142, 70), (168, 178, 98)]
RUST = [(118, 70, 34), (168, 108, 50), (206, 150, 76)]
AMBER = [(72, 28, 8), (150, 66, 14), (226, 132, 28), (255, 192, 74), (255, 234, 164), (255, 252, 228)]
FANG = [(132, 128, 146), (196, 192, 204), (236, 234, 242)]
MOUTH = (22, 9, 18)
CLAW = [(48, 47, 69), (84, 85, 111), (150, 148, 166), (214, 212, 222)]
PETRI = [(70, 69, 68), (98, 96, 94), (124, 122, 119), (150, 148, 144), (176, 174, 169),
         (200, 198, 192), (222, 220, 214)]
DUST = [(60, 56, 62), (92, 88, 92), (128, 124, 124), (164, 160, 156)]
WHITE = (255, 255, 255)

_L = (-0.5, -0.62, 0.6)
_LN = math.sqrt(sum(c * c for c in _L))
LIGHT = tuple(c / _LN for c in _L)


@dataclass(frozen=True)
class Pose:
    dx: float = 0.0
    dy: float = 0.0
    rot: float = 0.0                  # whole-creature rotation (radians, + = clockwise)
    lean: float = 0.0                 # upper body shift (negative = towards the hero)
    crouch: float = 1.0               # vertical scale of the upper body
    breath: int = 0                   # shoulders / head lift (px)
    phase: float = 0.0
    head: tuple = (0.0, 0.0)          # extra head offset
    jaw: float = 0.25                 # 0 closed .. 1 roaring
    hand: tuple = (-27.0, -2.0)       # near hand (rel. body origin)
    hand_b: tuple = (-17.0, -1.0)     # far hand
    elbow: float = 0.35               # elbow bend side (+1 forward/out, -1 back)
    legs: float = 0.0                 # 0 crouched .. 1 tucked for flight
    wing: float = 48.0                # near wing arm angle (degrees, 0 = back/right, 90 = up)
    fan: float = 1.0
    wing_b: float = 64.0              # far wing
    fan_b: float = 0.9
    wlen: float = 1.0
    wlen_b: float = 0.86
    wrap: float = 0.0                 # near wing wraps around the body 0..1
    tail: float = 1.0                 # tail tip sway amplitude
    ear: float = 0.0
    eye: float = 1.0
    throat: float = 0.35
    stone: float = 0.0                # petrified 0..1
    crack: float = 0.0                # death: glowing cracks 0..1
    crumble: float = 0.0
    sink: float = 0.0
    flash: float = 0.0
    dissolve: float = 0.0
    smears: tuple = ()                # ((r, a0, a1, k), ...) claw arcs whose head ends at the claw
    chips: float = 0.0
    chip_kind: int = 0                # 0 hurt, 1 awaken (up), 2 stone flakes (fall)
    dust: float = 0.0
    puff: float = 0.0
    roar: float = 0.0
    pebble: float = -1.0
    motes: tuple = field(default_factory=tuple)


# ---------------------------------------------------------------- primitives
class Ell:
    """Ellipsoid seen from the front: centre, radii, depth of its centre (z towards viewer)."""
    __slots__ = ("cx", "cy", "rx", "ry", "cz", "group", "shade", "kind", "rz")

    def __init__(self, c, rx, ry, cz, group, shade=0.0, kind="stone"):
        self.cx, self.cy = c
        self.rx, self.ry = max(0.8, rx), max(0.8, ry)
        self.cz, self.group, self.shade, self.kind = cz, group, shade, kind
        self.rz = min(self.rx, self.ry)

    def bbox(self):
        return (int(self.cx - self.rx) - 1, int(self.cy - self.ry) - 1,
                int(self.cx + self.rx) + 2, int(self.cy + self.ry) + 2)

    def at(self, x, y):
        ex = (x + 0.5 - self.cx) / self.rx
        ey = (y + 0.5 - self.cy) / self.ry
        d2 = ex * ex + ey * ey
        if d2 > 1:
            return None
        h = math.sqrt(1 - d2)
        return self.cz + self.rz * h, ex, ey, h


class Tube:
    """Tapered tube along a polyline (radius r0 -> r1)."""
    __slots__ = ("pts", "r0", "r1", "cz", "group", "shade", "kind", "segs", "total")

    def __init__(self, pts, r0, r1, cz, group, shade=0.0, kind="stone"):
        self.pts = [tuple(q) for q in pts]
        self.r0, self.r1, self.cz, self.group, self.shade, self.kind = r0, r1, cz, group, shade, kind
        self.segs = []
        acc = 0.0
        for a, b in zip(self.pts, self.pts[1:]):
            ln = math.hypot(b[0] - a[0], b[1] - a[1])
            self.segs.append((a, b, ln, acc))
            acc += ln
        self.total = max(1e-6, acc)

    def bbox(self):
        r = max(self.r0, self.r1)
        xs = [q[0] for q in self.pts]
        ys = [q[1] for q in self.pts]
        return int(min(xs) - r) - 1, int(min(ys) - r) - 1, int(max(xs) + r) + 2, int(max(ys) + r) + 2

    def at(self, x, y):
        px, py = x + 0.5, y + 0.5
        best = None
        for (ax, ay), (bx, by), ln, acc in self.segs:
            vx, vy = bx - ax, by - ay
            s = 0.0 if ln < 1e-6 else max(0.0, min(1.0, ((px - ax) * vx + (py - ay) * vy) / (ln * ln)))
            qx, qy = ax + vx * s, ay + vy * s
            t = (acc + ln * s) / self.total
            r = self.r0 + (self.r1 - self.r0) * t
            dx, dy = px - qx, py - qy
            d = math.hypot(dx, dy) / r
            if d <= 1 and (best is None or d < best[0]):
                best = (d, dx / r, dy / r, r)
        if best is None:
            return None
        d, nx, ny, r = best
        h = math.sqrt(max(0.0, 1 - d * d))
        return self.cz + r * h, nx, ny, h


def _clamp(v, a=0.0, b=1.0):
    return a if v < a else b if v > b else v


def lerp(a, b, t):
    return a + (b - a) * t


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


def fill_polygon(poly):
    ys = [q[1] for q in poly]
    y0, y1 = int(math.floor(min(ys))), int(math.ceil(max(ys)))
    n = len(poly)
    out = []
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
                out.append((x, y))
    return out


def tube(cv: Canvas, pts, rad, colors, shade=0.0, dither=0.6, min_r=0.6, solid=True):
    """Shaded tube written straight into ``cv`` (the kit's ``stroke`` without the full blit)."""
    pts = polyline(list(pts), 0.5) if len(pts) > 1 else list(pts)
    n = len(pts)
    best = {}
    for i, (x, y) in enumerate(pts):
        t = i / max(1, n - 1)
        r = max(min_r, rad(t))
        for yy in range(int(y - r) - 1, int(y + r) + 2):
            for xx in range(int(x - r) - 1, int(x + r) + 2):
                dx, dy = xx + 0.5 - x, yy + 0.5 - y
                d = math.hypot(dx, dy) / r
                if d > 1:
                    continue
                if (xx, yy) not in best or d < best[(xx, yy)][0]:
                    best[(xx, yy)] = (d, (-dx * 0.7 - dy * 0.7) / r, t)
    for (xx, yy), (d, side, t) in best.items():
        light = 0.55 + 0.42 * side - 0.22 * d * d + shade
        cv.put(xx, yy, ramp(colors, _clamp(light), xx, yy, dither), solid=solid)


def rotate(cv: Canvas, ang: float, cx: float, cy: float) -> Canvas:
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


# ---------------------------------------------------------------- body geometry
class Body:
    def __init__(self, p: Pose) -> None:
        self.p = p
        self.ox = CX + round(p.dx)
        self.oy = FOOT_Y + round(p.dy)

    def P(self, lx: float, ly: float):
        """Body-local point -> cell; the upper body leans, squashes and breathes."""
        p = self.p
        k = _clamp(-ly / 60.0, 0.0, 1.4)
        x = self.ox + lx + round(p.lean * k)
        yy = ly * p.crouch if ly < 0 else ly
        lift = p.breath if ly < -33 else 0
        return x, self.oy + round(yy) - lift + (ly * p.crouch - round(ly * p.crouch) if ly < 0 else 0)

    def A(self, lx: float, ly: float):
        """Absolute body-local point (no lean / crouch): planted hands and feet."""
        return self.ox + lx, self.oy + ly

    def head_c(self):
        p = self.p
        x, y = self.P(-22, -50)
        return x + p.head[0], y + p.head[1]

    def centre(self):
        return self.ox + 2, self.oy - 34


OPEN = (8.0, -30.0, -68.0, -104.0)       # finger directions from the arm (degrees)
CLOAK_W = (1, -60)                      # near wing wrapped round the body (body-local)
CLOAK_TIPS = ((-30, -47), (-37, -31), (-31, -13), (-18, -1))
CLOAK_H = (12, -3)
ARM_LEN = 17.0
FINGERS = (17.0, 24.0, 22.0, 17.0)


def wing_geom(S, H, A, fan, ln, wrap=0.0, cloak=None):
    """Shoulder, wrist, finger tips and hip of a wing; ``wrap`` blends towards ``cloak``
    (wrist, tips, hip of the wing wrapped round the body like a cloak)."""
    s = _clamp((100.0 - A) / 14.0, -1.0, 1.0)
    ar = math.radians(A)
    W = (S[0] + ARM_LEN * ln * math.cos(ar), S[1] - ARM_LEN * ln * math.sin(ar))
    tips = []
    for o, L in zip(OPEN, FINGERS):
        a = math.radians(A + o * s * fan)
        tips.append((W[0] + L * ln * math.cos(a), W[1] - L * ln * math.sin(a)))
    Hh = H
    if wrap > 0 and cloak is not None:
        cw, ct, ch = cloak
        k = smooth(wrap)
        W = (lerp(W[0], cw[0], k), lerp(W[1], cw[1], k))
        tips = [(lerp(a[0], c[0], k), lerp(a[1], c[1], k)) for a, c in zip(tips, ct)]
        Hh = (lerp(H[0], ch[0], k), lerp(H[1], ch[1], k))
    rnd = lambda q: (round(q[0]), round(q[1]))  # noqa: E731  whole-pixel vertices
    return rnd(S), rnd(W), [rnd(t) for t in tips], rnd(Hh)


def _scallop(a, c, toward, depth_k, n=6):
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


def _wrapd(a):
    return (a + math.pi) % math.tau - math.pi


def draw_wing(cv: Canvas, geom, shade: float, stone: float) -> None:
    S, W, tips, H = geom
    poly = [S, W, tips[0]]
    for a, c in zip(tips, tips[1:]):
        poly += _scallop(a, c, W, 0.24)
        poly.append(c)
    poly += _scallop(tips[-1], H, W, 0.12)
    poly.append(H)
    poly += _scallop(H, S, W, -0.05, 3)
    pix = fill_polygon(poly)
    pset = set(pix)
    angs = [math.atan2(t[1] - W[1], t[0] - W[0]) for t in tips]
    lens = [math.hypot(t[0] - W[0], t[1] - W[1]) for t in tips]
    lmax = max(lens) or 1.0
    veins = [(_wrapd(angs[i] + _wrapd(angs[i + 1] - angs[i]) / 2)) for i in range(len(angs) - 1)]
    top = min(q[1] for q in poly)
    height = max(1.0, max(q[1] for q in poly) - top)
    for x, y in pix:
        rx, ry = x + 0.5 - W[0], y + 0.5 - W[1]
        r = math.hypot(rx, ry)
        a = math.atan2(ry, rx)
        dmin = min(abs(_wrapd(a - g)) for g in angs)
        between = _clamp(dmin / 0.35) if r > 3 else 0.4
        light = 0.22 + 0.34 * _clamp(r / lmax) ** 1.2 + 0.1 * between
        light += 0.2 * (1 - (y + 0.5 - top) / height) + shade
        hd = math.hypot(x + 0.5 - S[0], y + 0.5 - S[1])
        light -= 0.16 * _clamp(1 - hd / 10)
        light += (hash01(x, y, 17) - 0.5) * 0.08
        edge = ((x - 1, y) not in pset or (x, y + 1) not in pset or (x + 1, y) not in pset)
        if edge and r > 0.4 * lmax:
            light += 0.16
        col = ramp(WING, _clamp(light), x, y)
        # darker veins half-way between the bones, fading out before the edge
        for va in veins:
            if 3.5 < r < 0.78 * lmax and abs(_wrapd(a - va)) * r < 0.55:
                col = WING[max(0, WING.index(col) - 2)] if col in WING else WING[1]
                break
        cv.put(x, y, col)
    # petrified: stone cracks across the membrane
    if stone > 0.45:
        for k in range(3):
            a0 = veins[k % len(veins)] + 0.25
            x, y = W[0] + math.cos(a0) * 6, W[1] + math.sin(a0) * 6
            for s in range(int(6 + 8 * stone)):
                x += math.cos(a0) + (hash01(k, s, 23) - 0.5) * 1.4
                y += math.sin(a0) + (hash01(s, k, 24) - 0.5) * 1.4
                if (round(x), round(y)) in pset:
                    cv.put(round(x), round(y), WING[0])
    # bones: forearm bowed at the elbow, fingers fanning from the wrist
    ex, ey = (S[0] + W[0]) / 2 + 1.0, (S[1] + W[1]) / 2 + 1.5
    tube(cv, [S, (ex, ey), W], lambda t: 2.3 - 0.7 * t, STONE, shade=shade - 0.02)
    for tip, ln in zip(tips, lens):
        tube(cv, [W, tip], lambda t: 1.25 - 0.55 * t, STONE, shade=shade - 0.06)
    # thumb claw on the wrist
    cv.put(W[0] - 1, W[1] - 2, STONE[6])
    cv.put(W[0] - 2, W[1] - 3, FANG[1])
    cv.put(W[0] - 2, W[1] - 2, STONE[3])


def body_prims(b: Body):
    p = b.p
    P = b.P
    out = []
    dk = -0.2
    # far side (behind, darker)
    out.append(Ell(P(15, -13), 9.5, 9.0, -7, "farleg", dk))
    fh = b.A(lerp(10, 16, p.legs), lerp(-2, -9, p.legs))
    out.append(Tube([P(14, -10), (fh[0] + 1, fh[1] - 2)], 4.0, 3.0, -7, "farleg", dk))
    out.append(Tube([(fh[0] + 1, fh[1]), (fh[0] - 8, fh[1] + 0.5)], 2.6, 2.2, -6, "farleg", dk))
    sb = P(3, -43)
    hb = b.A(*p.hand_b)
    elb, wr = ik(sb, hb, 23, 23, p.elbow)
    out.append(Tube([sb, elb], 4.6, 3.8, -6, "fararm", dk))
    out.append(Tube([elb, wr], 3.8, 3.2, -5, "fararm", dk))
    out.append(Ell(wr, 3.6, 3.0, -4, "fararm", dk))
    # torso (one smooth group)
    out.append(Ell(P(11, -18), 10.5, 10.0, 0, "torso"))
    out.append(Ell(P(1, -27), 8.0, 8.5, 1, "torso"))
    out.append(Ell(P(4, -44), 13.5, 11.0, 0, "torso", 0.02))
    out.append(Ell(P(-6, -37), 9.5, 8.0, 4, "chest", -0.04))
    for k, (sx_, sy_) in enumerate(((-1, -51), (5, -52), (11, -50), (16, -46), (19, -40), (21, -33),
                                    (21, -26))):
        out.append(Ell(P(sx_ - 0.5, sy_ + 0.5), 1.7, 1.7, -1, "torso", -0.02))
    out.append(Tube([P(-5, -44), P(-15, -49)], 6.2, 5.0, 2, "torso"))
    # tail: from the hips, down the plinth's right side, curling in front of it
    sw = p.tail * math.sin(p.phase)
    tp = [P(19, -15), b.A(29, -9), b.A(34, -1), b.A(32, 6), b.A(24 + 0.5 * sw, 10),
          b.A(15 + 1.5 * sw, 10 - round(0.8 * sw))]
    if p.legs > 0:
        k = p.legs
        tp = [tp[0]] + [(q[0] + 6 * k * i, q[1] - 5 * k * i) for i, q in enumerate(tp[1:], 1)]
    out.append(Tube(tp, 3.3, 1.5, -2, "tail", -0.04))
    # near leg: haunch, shin, foot
    out.append(Ell(P(12, -14), 9.5, 9.0, 4, "leg"))
    out.append(Tube([P(10, -16), P(-4, -18)], 8.5, 5.5, 6, "leg"))
    nf = b.A(lerp(-2, 8, p.legs), lerp(-2, -7, p.legs))
    out.append(Tube([P(-5, -17), (nf[0] + 2, nf[1] - 3)], 4.6, 3.2, 7, "shin"))
    out.append(Tube([(nf[0] + 4, nf[1]), (nf[0] - 7, nf[1] + 0.5)], 3.0, 2.4, 8, "foot"))
    # near arm
    sh = P(-6, -40)
    hn = b.A(*p.hand)
    elb, wr = ik(sh, hn, 24, 24, p.elbow)
    out.append(Ell(P(-5, -41), 6.5, 6.5, 8, "arm"))
    out.append(Tube([sh, elb], 5.2, 4.2, 9, "arm"))
    out.append(Tube([elb, wr], 4.4, 3.6, 10, "fore"))
    out.append(Ell(wr, 4.2, 3.4, 11, "hand"))
    # head
    hx, hy = b.head_c()
    jaw = p.jaw
    out.append(Ell((hx, hy), 7.5, 7.0, 6, "head"))
    out.append(Ell((hx - 2, hy + 2.5), 5.5, 4.5, 8, "head"))
    out.append(Ell((hx - 8, hy + 1.5), 5.5, 3.2, 8, "head"))
    out.append(Ell((hx - 13, hy + 0.5), 2.2, 2.2, 9, "head"))
    out.append(Tube([(hx - 1, hy + 5), (hx - 11, hy + 5.5 + 4.5 * jaw)], 2.8, 1.8, 7, "jaw"))
    out.append(Tube([(hx - 10, hy - 3), (hx - 4, hy - 5), (hx + 1, hy - 5.5)], 1.9, 2.2, 10, "brow"))
    tw = p.ear
    out.append(Tube([(hx + 3, hy - 1), (hx + 11, hy - 5 + tw), (hx + 13, hy - 7 + 2 * tw)],
                    2.6, 0.5, 9, "ear"))
    horn = [(0, -6), (3, -12), (9, -15.5), (14, -14), (16, -10)]
    out.append(Tube([(hx + a - 3, hy + c - 1) for a, c in horn[:-1]], 2.4, 0.6, 1, "hornb", -0.16))
    out.append(Tube([(hx + a, hy + c) for a, c in horn], 2.8, 0.6, 11, "horn", -0.04))
    return out, (sh, elb, wr), (hx, hy)


CRACKS = [  # body-local polylines (level at which they appear: 0 always, >0 death/petrify)
    ([(4, -50), (7, -45), (5, -41), (8, -37)], 0.0),
    ([(14, -20), (11, -16), (13, -12)], 0.0),
    ([(-8, -32), (-6, -28), (-8, -24)], 0.0),
    ([(-2, -38), (1, -34), (0, -30), (3, -26), (1, -21)], 0.3),
    ([(10, -46), (14, -42), (17, -38)], 0.25),
    ([(6, -16), (2, -10), (4, -6)], 0.45),
    ([(-12, -40), (-10, -36)], 0.55),
    ([(17, -26), (13, -22), (16, -18)], 0.6),
    ([(-20, -55), (-17, -50)], 0.7),
]


def draw_body(cv: Canvas, b: Body):
    p = b.p
    prims, arm, hc = body_prims(b)
    W, H = cv.w, cv.h
    zb = {}
    for i, pr in enumerate(prims):
        x0, y0, x1, y1 = pr.bbox()
        for y in range(max(0, y0), min(H, y1)):
            for x in range(max(0, x0), min(W, x1)):
                r = pr.at(x, y)
                if r is None:
                    continue
                z = r[0]
                cur = zb.get((x, y))
                if cur is None or z > cur[0]:
                    zb[(x, y)] = (z, i, r[1], r[2], r[3])
    ox, oy = b.ox, b.oy
    lx0, ly0, lz0 = LIGHT
    for (x, y), (z, i, nx, ny, nz) in zb.items():
        pr = prims[i]
        lam = max(0.0, nx * lx0 + ny * ly0 + nz * lz0)
        qx, qy = round(nx * 3) / 3, round(ny * 3) / 3              # chiselled facets
        qz = math.sqrt(max(0.0, 1 - min(1.0, qx * qx + qy * qy)))
        fl = max(0.0, qx * lx0 + qy * ly0 + qz * lz0)
        light = -0.04 + 0.6 * lam + 0.42 * fl + pr.shade
        if nx < -0.78 and ny < 0.3:
            light += 0.1                                           # rim on the lit edge
        lx, ly = x - ox, y - oy
        light -= 0.14 * _clamp(1 + ly / 12.0)                      # occlusion near the plinth
        sp = hash01(lx, ly, 31)
        light += (sp - 0.5) * 0.1
        # creases: a part sitting in front of this pixel darkens its edge / casts shadow
        g = pr.group
        for ddx, ddy, amt in ((-1, 0, 0.32), (0, -1, 0.32), (1, 0, 0.26), (0, 1, 0.22),
                              (-1, -1, 0.16), (-2, -2, 0.1)):
            o = zb.get((x + ddx, y + ddy))
            if o is not None and prims[o[1]].group != g and o[0] > z + 1.6:
                light -= amt
                break
        col = ramp(STONE, _clamp(light), x, y)
        if sp > 0.95 and nz > 0.3:
            col = STONE[max(0, STONE.index(col) - 2)]              # pits
        # lichen on upward faces
        if ny < -0.42 and pr.group not in ("horn", "hornb", "jaw", "brow"):
            n1 = hash01(lx // 3, ly // 2, 7)
            if n1 > 0.8 and hash01(lx, ly, 8) > 0.3:
                rust = hash01(lx // 3, ly // 2, 9) > 0.86
                lc = RUST if rust else LICHEN
                col = ramp(lc, _clamp(0.25 + 0.7 * lam + (sp - 0.5) * 0.3), x, y, 0.7)
        if pr.group == "horn" or pr.group == "hornb":
            # ridged rings along the horn
            if (int((x - hc[0]) * 0.6 + (y - hc[1]) * 0.4)) % 3 == 0 and nz > 0.4:
                col = STONE[max(0, STONE.index(col) - 1)] if col in STONE else col
        cv.put(x, y, col)
    owner = {k: prims[v[1]].group for k, v in zb.items()}
    draw_cracks(cv, b, owner)
    draw_face(cv, b, hc)
    draw_claws(cv, b, arm)
    draw_spade(cv, b, prims)
    return arm, hc


def draw_cracks(cv: Canvas, b: Body, owner) -> None:
    p = b.p
    lvl = max(p.crack, p.stone * 0.75)
    for pts, level in CRACKS:
        if level > 0 and lvl < level:
            continue
        grow = 1.0 if level == 0 else min(1.0, (lvl - level) / 0.25)
        cells = [b.P(x, y) for x, y in pts]
        seg = []
        for (x0, y0), (x1, y1) in zip(cells, cells[1:]):
            n = int(max(abs(x1 - x0), abs(y1 - y0))) + 1
            for k in range(n):
                seg.append((x0 + (x1 - x0) * k / n, y0 + (y1 - y0) * k / n))
        seg = seg[:max(1, int(len(seg) * grow))]
        for k, (x, y) in enumerate(seg):
            xi, yi = int(x), int(y)
            if owner.get((xi, yi)) not in ("torso", "leg", "head", "arm"):
                continue
            if p.crack > 0.05:
                hot = p.crack > 0.5 and (k + int(p.crack * 10)) % 3 != 0
                cv.put(xi, yi, AMBER[4] if hot else AMBER[3])
                if (xi + 1, yi) in owner:
                    cv.put(xi + 1, yi, AMBER[1])
            else:
                cv.put(xi, yi, STONE[0])
                if (xi - 1, yi) in owner and cv.get(xi - 1, yi) is not None:
                    cv.put(xi - 1, yi, mix(cv.get(xi - 1, yi)[:3], STONE[7], 0.4))


def draw_face(cv: Canvas, b: Body, hc) -> None:
    p = b.p
    hx, hy = round(hc[0]), round(hc[1])
    jaw = p.jaw
    # mouth: dark wedge between the snout and the lower jaw, amber deep in the throat
    a = (hx - 1, hy + 3.6)
    s = (hx - 13, hy + 3.4)
    j = (hx - 11, hy + 4.6 + 4.5 * jaw)
    if jaw > 0.12:
        for x, y in fill_polygon([a, s, j]):
            d = _clamp((x - s[0]) / max(1.0, a[0] - s[0]))
            col = MOUTH
            if d > 0.55 and p.throat > 0.1:
                col = mix(MOUTH, AMBER[2] if p.throat < 1 else AMBER[3], _clamp(p.throat * (d - 0.45) * 1.4))
            cv.put(x, y, col)
        # fangs: upper ones point down, lower ones up
        for fx in (-12, -9, -5):
            top = hy + 4
            cv.put(hx + fx, top, FANG[2])
            if fx != -5:
                cv.put(hx + fx, top + 1, FANG[1])
        jy = lambda fx: round(hy + 4.6 + 4.5 * jaw * (-(fx + 1) / 10.0))  # noqa: E731
        for fx in (-10, -7):
            cv.put(hx + fx, jy(fx) - 1, FANG[2])
            if jaw > 0.5:
                cv.put(hx + fx, jy(fx) - 2, FANG[1])
    else:
        for x in range(hx - 12, hx):
            cv.put(x, hy + 4, MOUTH)
        cv.put(hx - 11, hy + 3, FANG[2])
        cv.put(hx - 7, hy + 5, FANG[1])
    # nostril and eye socket under the brow
    cv.put(hx - 14, hy, STONE[0])
    ex, ey = hx - 6, hy - 1
    for ox_, oy_ in ((-1, -1), (0, -1), (1, -1), (2, -1), (-1, 0), (2, 0)):
        cv.put(ex + ox_, ey + oy_, STONE[0])
    e = p.eye * (1 - p.stone)
    if e > 0.05:
        hot = AMBER[4] if e > 0.6 else AMBER[2]
        cv.put(ex - 1, ey - 1, AMBER[2] if e < 1.2 else AMBER[3])
        cv.put(ex, ey, hot)
        cv.put(ex + 1, ey, AMBER[5] if e > 1.1 else hot)
        cv.put(ex + 2, ey - 1 + (0 if e > 1.3 else 1), AMBER[2])
        if e > 1.3:
            cv.put(ex, ey - 1, AMBER[3])
            cv.put(ex + 1, ey - 1, AMBER[4])
    else:
        cv.put(ex, ey, STONE[1])
        cv.put(ex + 1, ey, STONE[2])


def draw_claws(cv: Canvas, b: Body, arm) -> None:
    sh, elb, wr = arm
    ang = math.atan2(wr[1] - elb[1], wr[0] - elb[0])
    for k, off in enumerate((-0.55, 0.0, 0.55)):
        a = ang + off * 0.8
        x0, y0 = wr[0] + math.cos(a) * 3.2, wr[1] + math.sin(a) * 3.2
        curl = 0.9                                                  # claws hook downwards
        pts = [(x0, y0), (x0 + math.cos(a) * 3.5, y0 + math.sin(a) * 3.5),
               (x0 + math.cos(a + curl) * 6, y0 + math.sin(a + curl) * 6 + 0.5)]
        tube(cv, pts, lambda t: 1.25 - 0.7 * t, CLAW, shade=-0.05 - 0.05 * k, min_r=0.55)
    # toe claws on both feet, hooking over the plinth edge
    p = b.p
    for fx, fy, sh_ in ((lerp(-2, 8, p.legs) - 7, lerp(-2, -7, p.legs), 0.0),
                        (lerp(10, 16, p.legs) - 8, lerp(-2, -9, p.legs), -0.2)):
        x, y = b.A(fx, fy)
        for k in range(3):
            cx_, cy_ = round(x - 1 + k * 2.5), round(y + 1)
            cv.put(cx_ - 1, cy_, CLAW[2] if sh_ == 0 else CLAW[1])
            cv.put(cx_ - 2, cy_ + 1, CLAW[1] if sh_ == 0 else CLAW[0])


def draw_spade(cv: Canvas, b: Body, prims) -> None:
    tail = next(pr for pr in prims if pr.group == "tail")
    (ax, ay), (bx, by) = tail.pts[-2], tail.pts[-1]
    d = math.hypot(bx - ax, by - ay) or 1.0
    ux, uy = (bx - ax) / d, (by - ay) / d
    px_, py_ = -uy, ux
    poly = [(bx + ux * 6, by + uy * 6), (bx + px_ * 3.4 - ux * 0.5, by + py_ * 3.4 - uy * 0.5),
            (bx + ux * 1.0, by + uy * 1.0), (bx - px_ * 3.4 - ux * 0.5, by - py_ * 3.4 - uy * 0.5)]
    for x, y in fill_polygon(poly):
        side = (x + 0.5 - bx) * px_ + (y + 0.5 - by) * py_
        up = side * (py_ if py_ != 0 else 1)
        light = 0.62 - 0.3 * (1 if up > 0 else 0) + (hash01(x, y, 3) - 0.5) * 0.1
        cv.put(x, y, ramp(STONE, light, x, y))


# ---------------------------------------------------------------- plinth
PL_X0, PL_X1 = CX - 32, CX + 30


def draw_plinth(cv: Canvas, p: Pose) -> None:
    w = PL_X1 - PL_X0
    for y in range(PT - 1, GROUND + 1):
        if y <= PT + 1:                       # top face (seen slightly from above)
            x0, x1 = PL_X0 + 1, PL_X1 - 1
        elif y <= PT + 4:                     # cornice
            x0, x1 = PL_X0, PL_X1
        elif y == PT + 5:                     # undercut
            x0, x1 = PL_X0 + 2, PL_X1 - 2
        elif y < GROUND - 3:                  # die
            x0, x1 = PL_X0 + 3, PL_X1 - 3
        else:                                 # base moulding
            x0, x1 = PL_X0 + 1 - (y - (GROUND - 3)), PL_X1 - 1 + (y - (GROUND - 3))
        if y == PT - 1:
            x0, x1 = PL_X0 + 3, PL_X1 - 3
        for x in range(x0, x1 + 1):
            # chipped corner, top right
            if x > PL_X1 - 6 and y < PT + 3 + (x - (PL_X1 - 6)) * 0 and (x - (PL_X1 - 6)) > (y - PT + 1) * 1.5:
                continue
            u = (x - x0) / max(1, x1 - x0)
            if y <= PT + 1:
                light = 0.72 - 0.2 * u
            elif y <= PT + 4:
                light = 0.6 - 0.25 * u - 0.06 * (y - PT - 2)
                if y == PT + 2:
                    light += 0.12
            elif y == PT + 5:
                light = 0.12
            elif y < GROUND - 3:
                light = 0.48 - 0.28 * u - 0.1 * (y - PT) / 12
                if y == PT + 6:
                    light -= 0.18                      # shadow under the cornice
            else:
                light = 0.55 - 0.25 * u if y == GROUND - 3 else 0.38 - 0.22 * u
            if x == x0:
                light += 0.16
            elif x == x1:
                light -= 0.16
            light += (hash01(x // 3, y // 2, 61) - 0.5) * 0.12
            col = ramp(PLINTH, _clamp(light), x, y)
            if hash01(x, y, 62) > 0.965:
                col = PLINTH[max(0, PLINTH.index(col) - 2)]
            if y <= PT + 4 and hash01(x // 2, y, 63) > 0.86 and x < CX + 6:
                col = ramp(LICHEN, 0.45 + 0.3 * (1 - u), x, y)
            cv.put(x, y, col)
    # cracks across the plinth face
    for pts in (((CX - 8, PT + 2), (CX - 6, PT + 6), (CX - 9, PT + 9), (CX - 7, GROUND - 3)),
                ((CX + 18, PT + 6), (CX + 15, PT + 9), (CX + 17, PT + 11)),
                ((PL_X0 + 1, PT + 3), (PL_X0 + 6, PT + 4))):
        for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
            n = max(abs(x1 - x0), abs(y1 - y0))
            for k in range(n + 1):
                x, y = round(x0 + (x1 - x0) * k / n), round(y0 + (y1 - y0) * k / n)
                if cv.get(x, y) is not None:
                    cv.put(x, y, PLINTH[0])
                    if cv.get(x + 1, y) is not None:
                        cv.put(x + 1, y, PLINTH[5])
    # a fallen chunk at the base
    for ox_, oy_, c in ((0, 0, 5), (1, 0, 4), (2, 0, 3), (0, 1, 3), (1, 1, 2), (2, 1, 1), (-1, 1, 4)):
        cv.put(PL_X1 + 3 + ox_, GROUND - 1 + oy_, PLINTH[c])


# ---------------------------------------------------------------- effects
def petrify(cv: Canvas, k: float) -> None:
    if k <= 0:
        return
    for y in range(cv.h):
        row = cv.px[y]
        for x in range(cv.w):
            c = row[x]
            if c is None:
                continue
            lum = (0.3 * c[0] + 0.59 * c[1] + 0.11 * c[2]) / 255
            lv = 0.18 + 0.75 * lum ** 0.8                         # flatter, paler
            tgt = ramp(PETRI, _clamp(lv), x, y, 0.12)
            row[x] = (*mix(c[:3], tgt, k), c[3])


def draw_smear(cv: Canvas, cx, cy, r, a0, a1, k) -> None:
    """Three parallel claw trails along an arc from a0 (tail) to a1 (head)."""
    if k <= 0:
        return
    n = int(abs(a1 - a0) * (r + 6)) + 2
    for lane, dr in enumerate((-4, 0, 4)):
        for i in range(n):
            t = i / (n - 1)                  # 0 tail .. 1 head
            a = a0 + (a1 - a0) * t
            rr = r + dr * (0.6 + 0.4 * t)
            w = 1 + (t > 0.55) + (t > 0.85 and lane == 1)
            for j in range(w):
                x = cx + math.cos(a) * (rr + j)
                y = cy + math.sin(a) * (rr + j)
                vis = t * k
                if bayer(int(x), int(y)) > vis * 1.6 + 0.05:
                    continue
                if t > 0.8:
                    c = WHITE if j == 0 else AMBER[4]
                elif t > 0.45:
                    c = AMBER[4] if j == 0 else AMBER[3]
                else:
                    c = AMBER[3] if t > 0.25 else AMBER[2]
                cv.put(round(x), round(y), c, solid=False, alpha=int(150 + 105 * t))
    # sparks at the head
    hx, hy = cx + math.cos(a1) * r, cy + math.sin(a1) * r
    if k > 0.6:
        for s in range(6):
            ang = a1 + (hash01(s, 1, 77) - 0.3) * 2.4
            ln = 2 + 4 * hash01(s, 2, 77)
            for j in range(int(ln)):
                cv.put(round(hx + math.cos(ang) * (2 + j)), round(hy + math.sin(ang) * (2 + j)),
                       AMBER[5] if j < 2 else AMBER[3], solid=False)


def draw_roar(cv: Canvas, mx, my, k) -> None:
    if k <= 0:
        return
    for ring in range(3):
        rr = 6 + 30 * ((k + ring * 0.33) % 1.0)
        fade = 1 - ((k + ring * 0.33) % 1.0)
        for i in range(60):
            a = math.pi + (i / 59 - 0.5) * 1.3
            x, y = mx + math.cos(a) * rr, my + math.sin(a) * rr * 0.9
            if bayer(int(x), int(y)) > fade * 1.2:
                continue
            cv.put(round(x), round(y), AMBER[4] if fade > 0.6 else AMBER[2], solid=False,
                   alpha=int(110 + 140 * fade))


def draw_chips(cv: Canvas, ox, oy, s, kind, fl=0.0) -> None:
    if s <= 0:
        return
    n = (9, 14, 22)[kind]
    for k in range(n):
        if kind == 0:                         # knocked off to the right/up
            x0 = ox + (hash01(k, 3, 9) - 0.5) * 16
            y0 = oy + (hash01(k, 4, 9) - 0.5) * 14
            vx, vy = 8 + 30 * hash01(k, 1, 9), 10 + 22 * hash01(k, 2, 9)
            x, y = x0 + vx * s, y0 - vy * s + 40 * s * s
        elif kind == 1:                       # awakening: thrown up and out
            ang = -math.pi * (0.1 + 0.8 * hash01(k, 1, 19))
            sp = 26 + 30 * hash01(k, 2, 19)
            x0 = ox + (hash01(k, 3, 19) - 0.5) * 30
            y0 = oy + (hash01(k, 4, 19) - 0.3) * 30
            x, y = x0 + math.cos(ang) * sp * s, y0 + math.sin(ang) * sp * s + 46 * s * s
        else:                                 # stone flakes peel off and fall
            x0 = ox + (hash01(k, 3, 29) - 0.5) * 44
            y0 = oy + (hash01(k, 4, 29) - 0.6) * 56
            dl = hash01(k, 5, 29) * 0.4
            ss = max(0.0, s - dl) / (1 - dl)
            if ss <= 0:
                continue
            x = x0 + (x0 - ox) * 0.3 * ss + 3 * math.sin(k + ss * 6)
            y = y0 + 30 * ss * ss
        if y > GROUND or not (0 <= x < cv.w):
            continue
        sz = 1 + (k % 3 == 0) + (kind == 1 and k % 4 == 1)
        pal = PETRI if kind == 2 else STONE
        for i in range(sz + 1):
            for j in range(sz):
                c = mix(pal[7 if kind < 2 else 5] if (i, j) == (0, 0) else pal[4], WHITE, fl * 0.8)
                cv.put(round(x) + i, round(y) + j, c, solid=False)
        for i in range(sz + 1):
            if cv.get(round(x) + i, round(y) + sz) is None and fl < 0.3:
                cv.put(round(x) + i, round(y) + sz, OUTLINE if kind < 2 else pal[2], solid=False)


def _cloud(cv: Canvas, cx, cy, r, a, pal) -> None:
    for yy in range(int(cy - r) - 1, int(cy + r) + 2):
        for xx in range(int(cx - r) - 1, int(cx + r) + 2):
            d = math.hypot(xx + 0.5 - cx, (yy + 0.5 - cy) * 1.2) / r
            if d > 1 or yy > GROUND + 1:
                continue
            if bayer(xx, yy) > (1.25 - d) * a * 1.3:
                continue
            lvl = 3 if d < 0.4 and yy < cy else 2 if d < 0.75 else 1
            cv.put(xx, yy, pal[lvl], solid=False, alpha=int(255 * min(1.0, a + 0.4)))


def draw_dust(cv: Canvas, k: float) -> None:
    if k <= 0:
        return
    for j in range(8):
        side = -1 if j % 2 == 0 else 1
        base = PL_X0 if side < 0 else PL_X1
        cx = base + side * (2 + 14 * k * hash01(j, 1, 7))
        cy = GROUND - 2 - 5 * k * hash01(j, 4, 7)
        _cloud(cv, cx, cy, 2 + 4 * k, 1 - 0.6 * k, DUST)


def draw_puff(cv: Canvas, b: Body, k: float) -> None:
    """Stone dust puffs around the body while it petrifies."""
    if k <= 0:
        return
    for j in range(9):
        ang = math.pi * (0.15 + 1.7 * hash01(j, 1, 37))
        rad = 24 + 10 * k * hash01(j, 2, 37)
        cx = b.ox + 2 + math.cos(ang) * rad * 0.9
        cy = b.oy - 30 + math.sin(ang) * rad * 0.8 - 6 * k
        _cloud(cv, cx, cy, 2.5 + 4 * k * hash01(j, 3, 37) + 1.5, 1 - 0.7 * k, PETRI[1:5])


def draw_pebble(cv: Canvas, prog: float) -> None:
    if prog < 0:
        return
    x0, y0 = PL_X0 + 1, PT + 4
    if prog < 0.7:
        t = prog / 0.7
        x, y = x0 - 2 * t, y0 + (GROUND - 1 - y0) * t * t
    else:
        t = (prog - 0.7) / 0.3
        x, y = x0 - 2 - 4 * t, GROUND - 1 - 3 * math.sin(t * math.pi)
    for ox_, oy_, c in ((0, 0, PLINTH[6]), (1, 0, PLINTH[4]), (0, 1, PLINTH[3])):
        cv.put(round(x) + ox_, round(y) + oy_, c)
    if prog < 0.6:                            # dust trail
        for s in range(1, 4):
            if hash01(s, int(prog * 10), 5) > 0.4:
                cv.put(round(x0 - 2 * prog), round(y0 + (y - y0) * (1 - s * 0.25)) - 1, DUST[2],
                       solid=False, alpha=120)


def crumble(cv: Canvas, c: float, sink: float) -> Canvas:
    """Break everything (creature and plinth) into rocks that tumble into a heap, then sink."""
    cell = 8
    sites = {}

    def site(gx, gy):
        key = (gx, gy)
        if key not in sites:
            sites[key] = (gx * cell + 1 + hash01(gx, gy, 41) * (cell - 2),
                          gy * cell + 1 + hash01(gx, gy, 42) * (cell - 2))
        return sites[key]

    chunk = {}
    for y in range(cv.h):
        for x in range(cv.w):
            if cv.px[y][x] is None:
                continue
            gx, gy = x // cell, y // cell
            best, bk = 1e9, None
            for ox_ in (-1, 0, 1):
                for oy_ in (-1, 0, 1):
                    sx, sy = site(gx + ox_, gy + oy_)
                    d = (x + 0.5 - sx) ** 2 + (y + 0.5 - sy) ** 2
                    if d < best:
                        best, bk = d, (gx + ox_, gy + oy_)
            chunk[(x, y)] = bk
    groups: dict = {}
    for xy, k in chunk.items():
        groups.setdefault(k, []).append(xy)
    out = Canvas(cv.w, cv.h)
    for k in sorted(groups, key=lambda k: site(*k)[1]):
        sx, sy = site(*k)
        delay = 0.3 * hash01(*k, 45) + 0.2 * _clamp((sy - 30) / 80)
        e = smooth((c - delay) / (1 - delay)) if c < 1 else 1.0
        hgt = max(0.0, GROUND - sy)
        mound = max(0.0, 1 - abs(sx - CX) / 50)
        target = min(hgt, 3 + 14 * mound * (0.7 + 0.3 * hash01(*k, 43)) + hgt * 0.05)
        fall = round(e * (hgt - target) + sink)
        shift = round(e * ((sx - CX) * 0.25 + (hash01(*k, 44) - 0.5) * 8))
        for (x, y) in groups[k]:
            col = cv.px[y][x]
            ny = y + fall
            if ny > GROUND + 2:
                continue
            rgb = col[:3]
            if c > 0.02:
                below = chunk.get((x, y + 1)) not in (k, None) or chunk.get((x + 1, y)) not in (k, None)
                above = chunk.get((x, y - 1)) not in (k, None) or chunk.get((x - 1, y)) not in (k, None)
                if below:
                    rgb = OUTLINE if e > 0.05 else mix(rgb, OUTLINE, 0.6)
                elif above and e > 0.05:
                    rgb = mix(rgb, STONE[6], 0.35)
            out.put(x + shift, ny, rgb, solid=cv.solid[y][x], alpha=col[3])
    return out


# ---------------------------------------------------------------- render
def render(p: Pose, t: float = 0.0) -> Canvas:
    b = Body(p)
    fig = Canvas(CELL_W, CELL_H)
    S_far, H_far = b.P(1, -49), b.P(10, -30)
    draw_wing(fig, wing_geom(S_far, H_far, p.wing_b, p.fan_b, p.wlen_b), -0.16, p.stone)
    body = Canvas(CELL_W, CELL_H)
    arm, hc = draw_body(body, b)
    fig.blit(body, rim=OUTLINE)
    near = Canvas(CELL_W, CELL_H)
    S, Hh = b.P(5, -45), b.P(18, -24)
    cloak = (b.P(*CLOAK_W), [b.P(*q) for q in CLOAK_TIPS], b.P(*CLOAK_H))
    draw_wing(near, wing_geom(S, Hh, p.wing, p.fan, p.wlen, p.wrap, cloak), 0.0, p.stone)
    fig.blit(near, rim=OUTLINE)
    eye = (hc[0] - 5, hc[1] - 1)
    mouth = (hc[0] - 9, hc[1] + 5 + 2 * p.jaw)
    chest = b.P(-6, -34)
    _, elb, wr = arm
    da = math.atan2(wr[1] - elb[1], wr[0] - elb[0])
    claw = (wr[0] + math.cos(da) * 5, wr[1] + math.sin(da) * 5)
    rc = b.centre()
    if abs(p.rot) > 1e-3:
        fig = rotate(fig, p.rot, rc[0], rc[1])
        ca, sa = math.cos(p.rot), math.sin(p.rot)

        def rot(q):
            rx, ry = q[0] - rc[0], q[1] - rc[1]
            return rc[0] + ca * rx - sa * ry, rc[1] + sa * rx + ca * ry
        eye, mouth, chest, claw = rot(eye), rot(mouth), rot(chest), rot(claw)
    petrify(fig, p.stone)
    flash(fig, p.flash)
    cv = Canvas(CELL_W, CELL_H)
    draw_plinth(cv, p)
    cv.blit(fig, rim=OUTLINE)
    draw_pebble(cv, p.pebble)
    if p.crumble > 0 or p.sink > 0:
        cv = crumble(cv, p.crumble, p.sink)
    outline(cv, OUTLINE)
    if p.crumble < 0.25:
        live = (1 - p.stone) * (1 - p.crumble * 4)
        if p.eye > 0.05 and live > 0:
            cv.glow(eye[0] + 0.5, eye[1] + 0.5, 3 + 2.5 * p.eye, AMBER[3], 0.3 * p.eye * live)
        if p.throat > 0.05 and p.jaw > 0.12 and live > 0:
            cv.glow(mouth[0], mouth[1], 3 + 4 * p.throat, AMBER[2], 0.22 * p.throat * live)
        if p.crack > 0.1:
            cx, cy = b.P(0, -30)
            cv.glow(cx, cy, 34, AMBER[1], 0.22 * p.crack * (1 - p.crumble * 4), halo=False)
    for r_, a0, a1, k in p.smears:
        draw_smear(cv, claw[0] - r_ * math.cos(a1), claw[1] - r_ * math.sin(a1), r_, a0, a1, k)
    draw_roar(cv, mouth[0] - 3, mouth[1], p.roar)
    draw_chips(cv, chest[0], chest[1], p.chips, p.chip_kind, p.flash)
    draw_puff(cv, b, p.puff)
    draw_dust(cv, p.dust)
    for (mx, my, lv) in p.motes:
        cv.put(mx, my, DUST[lv] if lv < 4 else AMBER[3], solid=False)
    if p.dissolve > 0:
        dissolve(cv, p.dissolve, GROUND - 24, GROUND + 3, DUST[3], DUST[2], upward=False)
    return cv


# ---------------------------------------------------------------- animations
IDLE_FRAMES = 12


def idle_pose(i: int, n: int = IDLE_FRAMES) -> Pose:
    i %= n
    a = math.tau * i / n
    return Pose(
        breath=round(math.sin(a)), phase=a,
        wing=48 + round(2 * math.sin(a + 0.8)), fan=1.0 + 0.04 * math.sin(a + 0.8),
        wing_b=64 + round(2 * math.sin(a + 1.6)),
        jaw=0.25 + (0.1 if round(math.sin(a)) > 0 else 0.0),
        ear=1.0 if i in (8, 9) else 0.0,
        eye=0.55 if i == 6 else 1.0,
        throat=0.35 + 0.2 * math.sin(a),
        pebble=(i - 3) / 6 if 3 <= i <= 9 else -1.0,
    )


def idle_frames():
    return [(idle_pose(i), 120) for i in range(IDLE_FRAMES)]


def attack_frames():
    """Zarpazo de Piedra: rear back with the claw raised, lunge off the plinth edge, swipe."""
    b = idle_pose(0)
    sm = lambda k: ((26, 4.5, 2.35, k),)  # noqa: E731
    return [
        (replace(b, lean=3, crouch=0.96, hand=(-14, -40), elbow=1.0, wing=56, eye=1.2, jaw=0.4,
                 phase=0.3), 110),
        (replace(b, lean=5, crouch=0.93, dy=1, hand=(-4, -62), elbow=1.0, wing=62, wing_b=72,
                 eye=1.4, jaw=0.6, phase=0.6), 130),
        (replace(b, lean=6, crouch=0.92, dy=1, hand=(-2, -64), elbow=1.0, wing=64, wing_b=74,
                 eye=1.5, jaw=0.7, phase=0.8), 80),
        (replace(b, dx=-26, dy=2, lean=-9, crouch=1.04, hand=(-38, -12), elbow=-1.0, wing=30,
                 wing_b=46, eye=1.6, jaw=1.0, throat=1.0, phase=1.1, smears=sm(1.0),
                 hand_b=(-20, 0)), 60),
        (replace(b, dx=-28, dy=2, lean=-9, crouch=1.03, hand=(-37, -8), wing=32, wing_b=48,
                 eye=1.4, jaw=0.8, throat=0.8, phase=1.4, smears=sm(0.5), hand_b=(-20, 0)), 70),
        (replace(b, dx=-22, dy=1, lean=-7, hand=(-34, -6), wing=36, wing_b=52, eye=1.2,
                 jaw=0.6, phase=1.8, smears=sm(0.2), hand_b=(-19, 0)), 90),
        (replace(b, dx=-12, dy=1, lean=-4, hand=(-30, -4), wing=42, wing_b=58, eye=1.1,
                 jaw=0.4, phase=2.4, dust=0.4), 100),
        (replace(b, dx=-4, lean=-1, hand=(-28, -3), wing=46, phase=3.2, dust=0.8), 100),
        (b, 110),
    ]


def dive_frames():
    """Picado: leap with wings spread, dive and rake three times at the far left, fly back."""
    b = idle_pose(0)
    fly = dict(legs=1.0, hand=(-30, -24), hand_b=(-20, -20), elbow=-1.0, tail=0.4)

    return [
        (replace(b, crouch=0.92, dy=1, lean=2, wing=60, wing_b=72, eye=1.3, jaw=0.4), 120),
        (replace(b, crouch=0.86, dy=2, lean=3, wing=72, wing_b=82, fan=0.8, eye=1.5, jaw=0.6), 110),
        (replace(b, dy=-8, dx=-4, crouch=1.06, wing=22, wing_b=84, fan=1.2, fan_b=1.25, wlen_b=1.0,
                 legs=0.6, hand=(-22, -12), hand_b=(-14, -8), eye=1.5, dust=0.5), 70),
        (replace(b, dy=-14, dx=-10, wing=-12, wing_b=196, fan=1.1, eye=1.5, dust=0.9, **fly), 80),
        (replace(b, dy=-8, dx=-20, rot=-0.15, wing=54, wing_b=78, fan=1.2, fan_b=1.1, wlen_b=0.92, eye=1.6, jaw=0.8,
                 throat=1.0, **fly), 90),
        (replace(b, dy=-8, dx=-52, rot=-0.5, wing=4, wing_b=26, fan=0.6, fan_b=0.6, eye=1.6,
                 jaw=1.0, **fly), 60),
        (replace(b, dy=-2, dx=-80, rot=-0.38, wing=-8, wing_b=18, fan=0.7, eye=1.7, jaw=1.0,
                 throat=1.2, smears=((20, 4.4, 2.5, 1.0),),
                 **{**fly, "hand": (-38, -10)}), 55),
        (replace(b, dy=-11, dx=-66, rot=0.12, wing=64, wing_b=84, eye=1.4, jaw=0.6,
                 smears=((20, 4.4, 2.5, 0.4),), **fly), 70),
        (replace(b, dy=-6, dx=-86, rot=-0.4, wing=0, wing_b=22, fan=0.6, eye=1.6, jaw=1.0,
                 **fly), 55),
        (replace(b, dy=0, dx=-92, rot=-0.3, wing=-10, wing_b=16, fan=0.7, eye=1.7, jaw=1.0,
                 throat=1.2, smears=((18, 1.9, 3.9, 1.0),),
                 **{**fly, "hand": (-36, -6)}), 55),
        (replace(b, dy=-11, dx=-76, rot=0.15, wing=66, wing_b=84, eye=1.4, jaw=0.6,
                 smears=((18, 1.9, 3.9, 0.4),), **fly), 70),
        (replace(b, dy=-4, dx=-88, rot=-0.45, wing=2, wing_b=24, fan=0.6, eye=1.7, jaw=1.0,
                 **fly), 50),
        (replace(b, dy=2, dx=-94, rot=-0.32, wing=-14, wing_b=12, fan=0.7, eye=1.8, jaw=1.0,
                 throat=1.4, smears=((24, 4.3, 2.6, 1.0), (16, 4.2, 2.7, 0.8)),
                 **{**fly, "hand": (-38, -8)}), 60),
        (replace(b, dy=0, dx=-90, rot=-0.25, wing=-8, wing_b=20, eye=1.5, jaw=0.8,
                 smears=((24, 4.3, 2.6, 0.4),), **fly), 80),
        (replace(b, dy=-12, dx=-62, rot=0.18, wing=-14, wing_b=196, fan=1.1, eye=1.3, jaw=0.4,
                 **fly), 90),
        (replace(b, dy=-9, dx=-36, rot=0.12, wing=64, wing_b=84, fan=1.2, eye=1.2, **fly), 90),
        (replace(b, dy=-8, dx=-12, rot=0.05, wing=0, wing_b=80, fan=1.1, eye=1.1,
                 **{**fly, "legs": 0.5}), 90),
        (replace(b, crouch=0.88, dy=1, lean=2, wing=70, wing_b=86, fan=0.9, dust=0.5), 80),
        (replace(b, crouch=0.96, wing=54, wing_b=70, dust=1.0), 100),
        (b, 120),
    ]


def petrify_frames():
    """Petrificar: wrap the wing round, drain into pale stone, hold, flake back to life."""
    b = idle_pose(0)
    w = dict(wing_b=72, fan_b=0.7, wlen_b=0.76, crouch=0.95, hand=(-26, -2), lean=-1, jaw=0.1)
    return [
        (replace(b, wrap=0.3, eye=1.3, crouch=0.97, wing_b=74), 100),
        (replace(b, wrap=0.65, eye=1.3, **w), 90),
        (replace(b, wrap=0.92, eye=1.2, **w), 90),
        (replace(b, wrap=1.0, stone=0.35, eye=1.0, puff=0.25, **w), 90),
        (replace(b, wrap=1.0, stone=0.7, eye=0.6, puff=0.55, **w), 90),
        (replace(b, wrap=1.0, stone=1.0, eye=0.0, puff=0.85, dust=0.5, **w), 110),
        (replace(b, wrap=1.0, stone=1.0, eye=0.0, dust=0.9, **w), 230),
        (replace(b, wrap=1.0, stone=1.0, eye=0.0, **w), 230),
        (replace(b, wrap=1.0, stone=0.75, eye=0.4, chips=0.2, chip_kind=2, **w), 90),
        (replace(b, wrap=0.7, stone=0.45, eye=0.9, chips=0.5, chip_kind=2, **w), 90),
        (replace(b, wrap=0.35, stone=0.2, eye=1.3, chips=0.8, chip_kind=2, wing_b=72, crouch=0.97), 90),
        (replace(b, wrap=0.1, stone=0.0, eye=1.1, chips=1.0, chip_kind=2, wing_b=66), 100),
        (b, 110),
    ]


def cast_frames():
    """Despertar: wings spread wide, roar, eyes and throat blaze, chips fly."""
    b = idle_pose(0)
    big = dict(wing=22, wing_b=80, fan=1.2, fan_b=1.15, wlen_b=1.02, wlen=1.05, jaw=1.0, eye=1.8, throat=1.5,
               crouch=1.04, head=(0, -2), lean=1)
    return [
        (replace(b, crouch=0.94, head=(1, 2), wing=60, wing_b=76, fan=0.85, jaw=0.1, eye=1.2), 120),
        (replace(b, crouch=1.0, head=(0, -1), wing=34, wing_b=76, fan=1.1, fan_b=1.2, wlen_b=0.96, jaw=0.5, eye=1.4,
                 throat=0.8, chips=0.1, chip_kind=1), 90),
        (replace(b, roar=0.15, chips=0.25, chip_kind=1, **big), 80),
        (replace(b, roar=0.45, chips=0.45, chip_kind=1, dx=-1, **big), 80),
        (replace(b, roar=0.75, chips=0.65, chip_kind=1, dx=1, **big), 80),
        (replace(b, roar=0.98, chips=0.85, chip_kind=1, **big), 80),
        (replace(b, wing=36, wing_b=72, fan=1.1, jaw=0.5, eye=1.4, throat=0.8, chips=1.05,
                 chip_kind=1), 90),
        (replace(b, wing=42, wing_b=82, jaw=0.3, eye=1.2), 100),
        (replace(b, wing=46, wing_b=68), 100),
        (b, 110),
    ]


def hurt_frames():
    b = idle_pose(0)
    return [
        (replace(b, dx=3, lean=3, flash=0.85, eye=0.4, jaw=0.6, chips=0.2, wing=56, wing_b=72,
                 hand=(-25, -3), phase=0.8), 60),
        (replace(b, dx=3, lean=2, flash=0.5, eye=0.6, jaw=0.5, chips=0.5, wing=54, wing_b=70,
                 phase=1.4), 70),
        (replace(b, dx=2, lean=1, flash=0.15, eye=0.9, chips=0.8, wing=51, phase=2.0), 80),
        (replace(b, dx=1, chips=1.05, phase=2.8), 90),
        (replace(b, phase=3.6), 90),
        (b, 100),
    ]


def death_frames():
    b = idle_pose(0)
    out = [
        (replace(b, dx=2, lean=3, flash=0.85, eye=0.4, chips=0.25), 70),
        (replace(b, lean=1, crack=0.3, eye=1.8, throat=1.5, jaw=1.0, head=(0, -2), wing=60,
                 wing_b=80, flash=0.2, chips=0.6), 100),
        (replace(b, crack=0.6, eye=1.4, jaw=0.9, throat=1.2, wing=52, wing_b=72), 90),
        (replace(b, crack=0.9, eye=0.8, jaw=0.6, throat=0.6, crouch=0.97, wing=40, wing_b=62), 90),
        (replace(b, crack=1.0, eye=0.0, jaw=0.4, throat=0.0, crouch=0.95, wing=34, wing_b=58), 90),
    ]
    steps = 6
    for k in range(steps):
        u = (k + 1) / steps
        motes = tuple((CX - 44 + hash01(k, j, 51) * 88, GROUND - 8 - hash01(j, k, 52) * 44 * u,
                       1 + int(hash01(j, k, 53) * 4)) for j in range(6 + 2 * k))
        out.append((replace(b, crack=1.0 - 0.6 * u, eye=0.0, throat=0.0, crumble=u, crouch=0.95,
                            wing=34, wing_b=58, dust=0.5 + 0.5 * u, motes=motes), 80))
    for k, (d, s) in enumerate(((0.3, 2), (0.6, 4), (0.85, 6))):
        motes = tuple((CX - 36 + hash01(k, j, 54) * 72, GROUND - 4 - hash01(j, k, 55) * 26,
                       1 + int(hash01(j, k, 56) * 3)) for j in range(10 - 3 * k))
        out.append((replace(b, eye=0.0, throat=0.0, crumble=1.0, sink=s, crouch=0.95, wing=34,
                            wing_b=58, dissolve=d, dust=1.0 - 0.3 * k, motes=motes), 85))
    out.append((replace(b, crumble=1.0, eye=0.0, throat=0.0, dissolve=1.0), 120))
    return out


ANIMATIONS = {
    "idle": (idle_frames, True),
    "attack": (attack_frames, False),
    "dive": (dive_frames, False),
    "petrify": (petrify_frames, False),
    "cast": (cast_frames, False),
    "hurt": (hurt_frames, False),
    "death": (death_frames, False),
}

EVENTS = {"attack": {"strikes": [3]}, "dive": {"strikes": [6, 9, 12]}}
MOVES = {"rend": "attack", "dive": "dive", "petrify": "petrify", "awaken": "cast",
         "vengeance": "cast"}


def build():
    return build_sheet(ANIMATIONS, render, (CELL_W, CELL_H), ANCHOR, f"{SHEET_ID}_sheet.png",
                       {"events": EVENTS, "moves": MOVES, "boss": True, "elite": True})


def main() -> None:
    sheet, meta = build()
    save_sheet(OUT_DIR, SHEET_ID, sheet, meta)
    print(f"wrote assets/enemies/{SHEET_ID}_sheet.png ({len(sheet[0])}x{len(sheet)}) and .json")


if __name__ == "__main__":
    main()
