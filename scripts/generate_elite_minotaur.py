"""Draw and animate the elite "Minotauro" (a bull-headed brute). Stdlib only:

    python scripts/generate_elite_minotaur.py

Same method as the Espectro, the golem and the floor-1 bosses (``docs/code-drawn-sprites.md``):
one renderer, every frame a frozen ``Pose``. The minotaur stands upright on cloven hooves,
faces LEFT (the hero) and leans forward.

* ONE mass scanned row by row (section 10): the head, muzzle, ears, neck, mane hump, chest,
  belly, hips and near leg are muscle volumes joined by a smooth union of signed distances,
  so the figure is one silhouette with no seams; shading comes from that one field (normal =
  its gradient, depth = distance to the edge) with upper-left light, Bayer dither and creases
  where two muscles meet. Zones are painted inside it: dark long fur (head, mane, legs) vs a
  warmer short-furred chest and arms, grey-tan muzzle, black hooves, the belt band with
  bronze studs and buckle; the shaggy mane hangs in pointed tufts over the shoulders.
* Behind it (darker): tail with a tuft, far leg, far arm, far horn (chipped), back flap.
  On top with a dark rim (the Espectro sleeve rule): the tattered dark-red loincloth, the
  near arm (deltoid, bronze armlet and bracer, big fist) and the near ivory horn.
* Face: red slanted eyes under a heavy brow, nostrils, gold nose ring, a mouth that opens;
  white steam puffs from the nostrils (the cold accent against the warm room).

Animations (non-death actions end exactly on idle frame 0):
  idle    12-frame heavy breathing: chest and shoulders rise, head bobs, tail swishes, a
          steam puff on the exhale, an eye glint
  attack  "Pisotón": rears up on the back leg, front hoof high, slams it down; a crack and a
          shockwave of dust and rock run along the floor to the left (strike when it arrives)
  charge  "Embestida": lowers the horns, scrapes once, rushes left (stretch, speed lines, dust
          trail), horns hit at the far left (impact burst), skids, backs up to its spot
  paw     "Escarbar": scrapes the floor twice with a front hoof, dirt kicked back, big snorts
  cast    "Furia Taurina": throws the head back and roars, chest up, red rage aura pulses,
          heat shimmer, eyes blaze
  hurt    white flash, recoil, head jerks back
  death   staggers, drops to its knees, topples forward, dissolves into dust -> empty

Output: ``assets/enemies/minotaur_sheet.png`` + ``.json`` (``events``, ``moves``, ``boss``,
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
SHEET_ID = "minotaur"

CELL_W, CELL_H = 208, 120
CX, GROUND = 146, 113
ANCHOR = (CX, GROUND + 2)
HIP_H = 40.0                     # hip height above the ground (native px)
TOP_H = 78.0                     # top of the hump

# ---------------------------------------------------------------- palette
OUTLINE = (16, 8, 10)
FUR = [(15, 9, 10), (28, 16, 15), (43, 25, 20), (61, 37, 27), (84, 53, 36), (114, 78, 52)]
HIDE = [(38, 19, 16), (64, 34, 25), (96, 54, 36), (130, 78, 50), (166, 108, 70), (200, 146, 100)]
MUZZLE = [(44, 28, 26), (78, 52, 44), (114, 82, 66), (150, 116, 92), (184, 152, 122)]
HOOF = [(14, 11, 15), (30, 25, 30), (52, 45, 50), (86, 78, 80)]
HORN = [(86, 70, 52), (142, 124, 92), (196, 182, 144), (236, 228, 198), (255, 252, 236)]
HORN_TIP = [(26, 20, 20), (46, 36, 32), (74, 60, 50)]
GOLD = [(98, 60, 18), (168, 118, 38), (228, 182, 78), (255, 236, 160)]
BRONZE = [(58, 32, 20), (106, 64, 32), (164, 106, 52), (212, 158, 90), (246, 210, 150)]
LEATHER = [(26, 15, 13), (46, 28, 21), (72, 46, 32), (104, 72, 50)]
CLOTH = [(36, 9, 13), (62, 16, 21), (94, 26, 30), (130, 40, 40), (164, 62, 52)]
EYE = [(110, 10, 10), (214, 36, 26), (255, 110, 70), (255, 226, 196)]
MOUTH = [(30, 6, 8), (70, 16, 20), (118, 34, 38)]
STEAM = [(132, 150, 172), (186, 204, 222), (232, 242, 252), (255, 255, 255)]
RAGE = [(90, 10, 10), (176, 30, 20), (240, 80, 40), (255, 170, 90)]
DUST = [(52, 40, 36), (88, 72, 60), (130, 112, 92), (172, 156, 132)]
ROCK = [(40, 38, 48), (72, 70, 84), (112, 110, 124), (158, 156, 166)]
WHITE = (255, 255, 255)

_L = (-0.52, 0.6, 0.6)            # light: upper-left, towards the viewer (x right, y up, z out)
_LN = math.sqrt(sum(c * c for c in _L))
LIGHT = tuple(c / _LN for c in _L)


@dataclass(frozen=True)
class Pose:
    dx: float = 0.0
    dy: float = 0.0
    lean: float = 0.0                 # top of the torso offset (negative = towards the hero)
    tilt: float = 0.0                 # torso rotation about the hips (+ = rears back, - = forward)
    sx: float = 1.0
    sy: float = 1.0
    breath: float = 0.0               # chest/shoulders/head lift (px)
    crouch: float = 0.0               # hips sink (px), knees bend
    hx: float = 0.0                   # head offset (px)
    hy: float = 0.0
    ha: float = 0.0                   # head angle (+ = muzzle up / head back, - = horns forward)
    jaw: float = 0.0                  # mouth open 0..1
    fist_f: tuple = (-17.0, 38.0)     # near fist (rel. CX+dx, height above ground)
    fist_b: tuple = (17.0, 38.0)      # far fist
    foot_f: float = -15.0             # near hoof x (rel. CX+dx)
    foot_b: float = 12.0              # far hoof x
    lift_f: float = 0.0               # near hoof height above the floor
    lift_b: float = 0.0
    tail: float = 0.0                 # tail swing -1..1
    wind: float = 0.0                 # loincloth blown back (+) / forward (-)
    phase: float = 0.0
    eye: float = 1.0                  # eye glow (0 dark .. 2 blazing)
    steam: float = -1.0               # nostril puff progress 0..1 (<0: none)
    steam_big: float = -1.0           # big snort clouds progress 0..1
    flash: float = 0.0
    dissolve: float = 0.0
    shock: float = 0.0                # stomp shockwave progress 0..1 (front runs left)
    shock_fade: float = 0.0
    shock_x: float = -18.0            # where the hoof slammed (rel. CX)
    speed: float = 0.0                # charge: speed lines
    trail: float = 0.0                # charge: dust trail behind the hooves
    impact: float = 0.0               # charge: horn impact burst 0..1 (0 = none)
    skid: float = 0.0                 # skid dust in front of the hooves
    dust: float = 0.0                 # dust at the feet
    kick: float = -1.0                # paw: dirt clods kicked back, progress 0..1
    scrape: float = 0.0               # scrape marks on the floor (alpha)
    scrape_x: float = -20.0
    rage: float = 0.0                 # cast: red aura
    motes: tuple = field(default_factory=tuple)


# ---------------------------------------------------------------- primitives
class Prim:
    """A muscle volume: round cone (``cap``) or rotated superellipse (``ell``)."""
    __slots__ = ("kind", "ax", "ay", "bx", "by", "ra", "rb", "rx", "ry", "ca", "sa", "pw",
                 "zone", "dark", "shag", "mane", "k", "seed", "name", "ox")

    def __init__(self, kind, *, a=(0, 0), b=(0, 0), ra=1.0, rb=1.0, c=(0, 0), rx=1.0, ry=1.0,
                 ang=0.0, pw=2.0, zone="fur", dark=0.0, shag=0.0, mane=False, k=4.0, seed=0,
                 name="", ox=0.0):
        self.kind = kind
        if kind == "cap":
            self.ax, self.ay = a
            self.bx, self.by = b
            self.ra, self.rb = ra, rb
        else:
            self.ax, self.ay = c
            self.rx, self.ry = max(1.0, rx), max(1.0, ry)
            self.ca, self.sa = math.cos(ang), math.sin(ang)
            self.pw = pw
        self.zone, self.dark, self.shag, self.mane, self.k = zone, dark, shag, mane, k
        self.seed, self.name, self.ox = seed, name, ox

    def bbox(self, m: float):
        if self.kind == "cap":
            r = max(self.ra, self.rb) + self.shag + m
            return (min(self.ax, self.bx) - r, min(self.ay, self.by) - r,
                    max(self.ax, self.bx) + r, max(self.ay, self.by) + r)
        r = max(self.rx, self.ry) + self.shag + m
        return self.ax - r, self.ay - r, self.ax + r, self.ay + r

    def radius(self, t: float) -> float:
        if self.kind == "cap":
            return self.ra + (self.rb - self.ra) * t
        return min(self.rx, self.ry)

    def eval(self, px: float, py: float):
        """(signed distance, t along the axis / 0, outward dir x, outward dir y)."""
        if self.kind == "cap":
            abx, aby = self.bx - self.ax, self.by - self.ay
            l2 = abx * abx + aby * aby or 1e-6
            t = ((px - self.ax) * abx + (py - self.ay) * aby) / l2
            t = 0.0 if t < 0 else 1.0 if t > 1 else t
            qx, qy = self.ax + abx * t, self.ay + aby * t
            vx, vy = px - qx, py - qy
            dl = math.hypot(vx, vy) or 1e-6
            d = dl - (self.ra + (self.rb - self.ra) * t)
            ox, oy = vx / dl, vy / dl
        else:
            vx, vy = px - self.ax, py - self.ay
            lx = vx * self.ca + vy * self.sa
            ly = -vx * self.sa + vy * self.ca
            dl = math.hypot(vx, vy) or 1e-6
            p = self.pw
            kk = (abs(lx / self.rx) ** p + abs(ly / self.ry) ** p) ** (1 / p)
            d = dl * (1 - 1 / kk) if kk > 1e-6 else -min(self.rx, self.ry)
            t = 0.0
            ox, oy = vx / dl, vy / dl
        if self.shag > 0:
            d -= self.shag * tuft(px - self.ox, self.seed) * max(0.5, min(1.0, 0.45 + 0.75 * oy + 0.35 * ox))
        return d, t, ox, oy


def tuft(xr: float, seed: int, period: float = 3.0) -> float:
    """Pointed tufts along x: 0..1 triangle wave with a random length per tuft."""
    u = (xr + seed * 1.7) / period
    i = math.floor(u)
    f = abs((u - i) * 2 - 1)
    return (1 - f) * (0.45 + 0.55 * hash01(i, seed, 17))


def smin(a: float, b: float, k: float) -> float:
    if k <= 0:
        return min(a, b)
    h = max(k - abs(a - b), 0.0) / k
    return min(a, b) - h * h * k * 0.25


class Field:
    """The smooth union of a list of prims sampled on the cell grid."""

    def __init__(self, prims, w: int = CELL_W, h: int = CELL_H) -> None:
        self.prims = prims
        bx0, by0, bx1, by1 = 1e9, 1e9, -1e9, -1e9
        for pr in prims:
            x0, y0, x1, y1 = pr.bbox(pr.k + 3)
            bx0, by0, bx1, by1 = min(bx0, x0), min(by0, y0), max(bx1, x1), max(by1, y1)
        self.x0 = max(0, int(bx0) - 1)
        self.y0 = max(0, int(by0) - 1)
        self.x1 = min(w, int(bx1) + 2)
        self.y1 = min(h, int(by1) + 2)
        W, H = max(0, self.x1 - self.x0), max(0, self.y1 - self.y0)
        self.W, self.H = W, H
        INF = 99.0
        D = [[INF] * W for _ in range(H)]
        RD = [[INF] * W for _ in range(H)]
        OW = [[-1] * W for _ in range(H)]
        T = [[0.0] * W for _ in range(H)]
        MD = [[INF] * W for _ in range(H)]
        for i, pr in enumerate(prims):
            x0, y0, x1, y1 = pr.bbox(pr.k + 3)
            for y in range(max(self.y0, int(y0)), min(self.y1, int(y1) + 2)):
                Dy, RDy, OWy, Ty, MDy = D[y - self.y0], RD[y - self.y0], OW[y - self.y0], T[y - self.y0], MD[y - self.y0]
                for x in range(max(self.x0, int(x0)), min(self.x1, int(x1) + 2)):
                    d, t, _, _ = pr.eval(x + 0.5, y + 0.5)
                    j = x - self.x0
                    if d < RDy[j]:
                        RDy[j], OWy[j], Ty[j] = d, i, t
                    Dy[j] = smin(Dy[j], d, pr.k) if Dy[j] < INF else d
                    if pr.mane and d < MDy[j]:
                        MDy[j] = d
        self.D, self.RD, self.OW, self.T, self.MD = D, RD, OW, T, MD

    def d(self, x: int, y: int) -> float:
        if self.x0 <= x < self.x1 and self.y0 <= y < self.y1:
            return self.D[y - self.y0][x - self.x0]
        return 99.0

    def owner(self, x: int, y: int) -> int:
        if self.x0 <= x < self.x1 and self.y0 <= y < self.y1 and self.D[y - self.y0][x - self.x0] < 0:
            return self.OW[y - self.y0][x - self.x0]
        return -1

    def light(self, x: int, y: int) -> float:
        """Lambert light of the field's surface at a pixel (normal from the gradient)."""
        d = self.d(x, y)
        gx = min(2.0, self.d(x + 1, y)) - min(2.0, self.d(x - 1, y))
        gy = min(2.0, self.d(x, y + 1)) - min(2.0, self.d(x, y - 1))
        gl = math.hypot(gx, gy) or 1e-6
        i = self.OW[y - self.y0][x - self.x0]
        pr = self.prims[i]
        r = max(2.0, pr.radius(self.T[y - self.y0][x - self.x0]) * 1.15)
        e = 1 - min(1.0, max(0.0, -d / r))
        e = e ** 0.8
        nz = math.sqrt(max(0.0, 1 - e * e))
        nx, ny = gx / gl * e, -gy / gl * e
        lam = max(0.0, nx * LIGHT[0] + ny * LIGHT[1] + nz * LIGHT[2])
        if e > 0.9 and nx < -0.45 and d > -1.6:
            lam += 0.14                                      # torchlit rim on the hero's side
        return lam


# ---------------------------------------------------------------- geometry
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


class Body:
    def __init__(self, p: Pose) -> None:
        self.p = p
        self.bx = CX + p.dx
        self.pivot = (self.bx + 2, GROUND - HIP_H * p.sy + p.dy + p.crouch)
        self.ct, self.st = math.cos(p.tilt), math.sin(p.tilt)
        # head frame
        hx, hy = self.place(-25 + p.hx, 69 - p.hy, 1.0)
        self.head = (hx, hy)
        self.ha = p.ha + p.tilt
        self.hc, self.hs = math.cos(self.ha), math.sin(self.ha)

    def place(self, x: float, h: float, lift: float = 0.0):
        p = self.p
        X = self.bx + x * p.sx + p.lean * (max(0.0, h - HIP_H) / (TOP_H - HIP_H)) ** 1.2
        Y = GROUND - h * p.sy + p.dy + p.crouch - lift * p.breath
        if p.tilt:
            px, py = self.pivot
            vx, vy = X - px, Y - py
            X = px + vx * self.ct - vy * self.st
            Y = py + vx * self.st + vy * self.ct
        return X, Y

    def hp(self, lx: float, ly: float):
        """Head-local point (x forward = negative, y up) -> cell coords."""
        X = lx * self.hc + ly * self.hs
        Y = -lx * self.hs + ly * self.hc
        return self.head[0] + X, self.head[1] - Y

    def hang(self, a: float) -> float:
        """Head-local angle (y up, radians) -> screen ellipse angle."""
        return -(a - self.ha)

    def inv_head(self, x: float, y: float):
        X, Y = x - self.head[0], self.head[1] - y
        return X * self.hc - Y * self.hs, X * self.hs + Y * self.hc

    def fist(self, rel):
        p = self.p
        return self.bx + rel[0], GROUND - rel[1] + p.dy + p.crouch

    def foot(self, near: bool):
        p = self.p
        if near:
            return self.bx + p.foot_f, GROUND - p.lift_f
        return self.bx + p.foot_b, GROUND - p.lift_b


def leg_points(b: Body, near: bool):
    p = b.p
    hip = b.place(-3 if near else 9, 38)
    fx, fy = b.foot(near)
    hoof = (fx - 1, fy - 2.6)
    fet = (fx + 1.5, fy - 6.5)
    vx, vy = fet[0] - hip[0], fet[1] - hip[1]
    L = math.hypot(vx, vy) or 1e-3
    nx, ny = vx / L, vy / L
    fwx, fwy = ny, -nx                       # perpendicular pointing forward (left) for a leg going down
    if fwx > 0:
        fwx, fwy = -fwx, -fwy
    c = max(0.0, (31.0 - L) / 31.0)
    kb = 4.5 + 26 * c
    hb = 4.5 + 9 * c
    knee = (hip[0] + vx * 0.4 + fwx * kb, hip[1] + vy * 0.4 + fwy * kb)
    hock = (hip[0] + vx * 0.74 - fwx * hb, hip[1] + vy * 0.74 - fwy * hb)
    knee = (knee[0], min(GROUND - 3.5, knee[1]))
    hock = (hock[0], min(GROUND - 4.5, hock[1]))
    return hip, knee, hock, fet, hoof


def leg_prims(b: Body, near: bool, dark: float, seed: int):
    hip, knee, hock, fet, hoof = leg_points(b, near)
    ox = b.bx
    return [
        Prim("cap", a=hip, b=knee, ra=10.0, rb=7.0, zone="fur", dark=dark, k=3.0, seed=seed, name="thigh"),
        Prim("cap", a=knee, b=hock, ra=6.6, rb=4.2, zone="fur", dark=dark, k=2.5, seed=seed + 1, name="shin"),
        Prim("cap", a=hock, b=fet, ra=3.9, rb=3.4, zone="fur", dark=dark, k=2.0, seed=seed + 2,
             shag=1.6, name="cannon", ox=ox),
        Prim("ell", c=hoof, rx=5.0, ry=3.2, pw=2.8, zone="hoof", dark=dark, k=1.2, seed=seed + 3,
             name="hoof"),
    ]


def arm_prims(b: Body, near: bool, dark: float):
    p = b.p
    sh = b.place(-3, 65, 1.0) if near else b.place(14, 66, 1.0)
    fx, fy = b.fist(p.fist_f if near else p.fist_b)
    dx, dy = fx - sh[0], fy - sh[1]
    d = max(1e-3, math.hypot(dx, dy))
    wrist_t = (fx - dx / d * 4.5, fy - dy / d * 4.5)
    elb, wr = ik(sh, wrist_t, 17.0, 16.0, -1.0 if dx < 0 else 1.0)
    fdx, fdy = wr[0] - elb[0], wr[1] - elb[1]
    fl = math.hypot(fdx, fdy) or 1e-3
    fist_c = (wr[0] + fdx / fl * 4.8, wr[1] + fdy / fl * 4.8)
    fang = math.atan2(fdy, fdx)
    prims = [
        Prim("ell", c=(sh[0] + 0.5, sh[1] + 1), rx=8.5, ry=8.0, zone="hide", dark=dark, k=3.0, name="delt"),
        Prim("cap", a=sh, b=elb, ra=7.0, rb=5.4, zone="hide", dark=dark, k=3.0, name="upper"),
        Prim("cap", a=elb, b=wr, ra=5.8, rb=4.6, zone="hide", dark=dark, k=2.5, name="fore"),
        Prim("ell", c=(elb[0] + fdx / fl * 4, elb[1] + fdy / fl * 4), rx=6.6, ry=5.4, ang=fang,
             zone="hide", dark=dark, k=2.5, name="forebulge"),
        Prim("ell", c=fist_c, rx=6.6, ry=6.0, ang=fang, pw=2.5, zone="hide", dark=dark + 0.04, k=1.5,
             name="fist"),
    ]
    return prims, fist_c, (sh, elb, wr)


def body_prims(b: Body):
    """The main mass: torso, mane, head and near leg (one smooth union)."""
    p = b.p
    ox = b.bx
    out = []
    hp = b.place
    c = hp(3, 41)
    out.append(Prim("ell", c=c, rx=12.5 * p.sx, ry=8.5, zone="hide", dark=-0.05, name="hips"))
    c = hp(-3, 50, 0.3)
    out.append(Prim("ell", c=c, rx=11.0 * p.sx, ry=8.5, ang=-0.15 - p.tilt, zone="hide", name="belly"))
    c = hp(-12, 59, 0.8)
    out.append(Prim("ell", c=c, rx=16.0 * p.sx, ry=12.5, ang=0.35 - p.tilt, zone="hide", name="chest"))
    c = hp(4, 69, 1.0)
    out.append(Prim("ell", c=c, rx=15.0 * p.sx, ry=11.0, ang=-0.2 - p.tilt, zone="fur", shag=4.5,
                    mane=True, seed=3, name="hump", ox=ox, dark=-0.06))
    nb = hp(2, 68, 1.0)
    nh = b.hp(6, 0)
    out.append(Prim("cap", a=nb, b=nh, ra=10.0, rb=7.0, zone="fur", shag=4.0, mane=True, seed=5,
                    name="neck", ox=ox, dark=-0.06))
    # head (hard-ish union so it reads in front of the chest)
    out.append(Prim("ell", c=b.hp(0, 0), rx=9.5, ry=9.0, ang=b.hang(0.1), zone="fur", k=2.0,
                    shag=1.0, seed=7, name="skull", ox=ox))
    out.append(Prim("ell", c=b.hp(-10.5, -5.5), rx=8.5, ry=6.5, ang=b.hang(0.4), pw=2.5, zone="muzzle",
                    k=2.5, name="muzzle"))
    jaw = p.jaw
    jc = b.hp(-8.0 + 1.5 * jaw, -10.5 - 3.0 * jaw)
    out.append(Prim("ell", c=jc, rx=6.5, ry=3.0, ang=b.hang(0.2 + 0.55 * jaw), zone="muzzle", k=1.5,
                    name="jaw"))
    out.append(Prim("ell", c=b.hp(9.5, 3.0), rx=5.5, ry=2.3, ang=b.hang(-0.35), zone="ear", k=1.0,
                    name="ear"))
    out += leg_prims(b, True, 0.0, 30)
    return out


# ---------------------------------------------------------------- painting
CREASES = {("chest", "belly"), ("belly", "chest"), ("belly", "hips"), ("hips", "belly"),
           ("delt", "upper"), ("upper", "fore"), ("forebulge", "fist"), ("fore", "fist"),
           ("thigh", "shin"), ("shin", "cannon"), ("hips", "thigh"), ("thigh", "hips"),
           ("skull", "chest"), ("muzzle", "chest"), ("jaw", "chest"), ("neck", "chest"),
           ("chest", "skull"), ("chest", "neck"), ("muzzle", "skull"), ("skull", "muzzle"),
           ("jaw", "muzzle"), ("ear", "skull"), ("skull", "ear"), ("cannon", "hoof"),
           ("upper", "delt"), ("chest", "muzzle"), ("chest", "jaw")}


def paint_field(cv: Canvas, f: Field, b: Body, colour) -> None:
    for y in range(f.y0, f.y1):
        for x in range(f.x0, f.x1):
            i = f.owner(x, y)
            if i < 0:
                continue
            pr = f.prims[i]
            light = f.light(x, y)
            up = f.owner(x, y - 1)
            lf = f.owner(x - 1, y)
            crease = False
            for o in (up, lf):
                if o >= 0 and o != i and (f.prims[o].name, pr.name) in CREASES:
                    crease = True
            cv.put(x, y, colour(pr, x, y, light, crease, f))


def body_colour(b: Body):
    p = b.p
    # belt axis
    A = b.place(-16, 40)
    B = b.place(18, 40)
    ax, ay = B[0] - A[0], B[1] - A[1]
    al = math.hypot(ax, ay) or 1e-3
    ux, uy = ax / al, ay / al

    def colour(pr: Prim, x: int, y: int, lam: float, crease: bool, f: Field):
        h = GROUND - y
        light = 0.1 + 0.9 * lam + pr.dark
        light -= 0.16 * max(0.0, 1 - h / 22)              # ground occlusion
        if crease:
            light -= 0.24
        zone = pr.zone
        xr = x - b.bx
        # belt band (over hips / belly)
        if pr.name in ("hips", "belly", "thigh", "chest"):
            vx, vy = x + 0.5 - A[0], y + 0.5 - A[1]
            s = vx * (-uy) + vy * ux                        # perpendicular (down +)
            s = -s if ux < 0 else s
            u = vx * ux + vy * uy
            if -3.2 <= s <= 2.6:
                if abs(s) > 2.4 or s > 2.0:
                    return LEATHER[0]
                if 1.5 <= u <= 8.5 and -2.4 <= s <= 2.2:   # bronze buckle
                    cu, cs = u - 5, s + 0.1
                    if abs(cu) + abs(cs) * 1.2 < 3.6:
                        k = 0.75 - 0.18 * cu / 3 - 0.2 * cs / 2
                        return ramp(BRONZE, max(0.0, min(1.0, k)), x, y, 0.4)
                if (int(u) % 6 == 0) and abs(s + 0.2) < 0.9 and u > 9:
                    return BRONZE[4] if lam > 0.5 else BRONZE[3]
                if (int(u) % 6 == 1) and abs(s + 0.2) < 0.9 and u > 9:
                    return BRONZE[1]
                return ramp(LEATHER, 0.25 + 0.75 * lam - (0.25 if s < -1.6 else 0), x, y)
        # mane hanging over chest / shoulders: pointed tufts below the mane prims
        if zone == "hide" and pr.name == "chest":
            md = f.MD[y - f.y0][x - f.x0]
            if md < 3.6 * tuft(xr, 11, 2.6) + 0.3:
                zone = "fur"
                light += 0.05
        if zone == "fur":
            # long-fur strands: short vertical dashes
            off = int(hash01(int(xr) + 40, 3, 21) * 3)
            s = hash01(int(xr) + 40, (y + off) // 3, 22)
            light += (s - 0.5) * 0.13
            if pr.mane and lam > 0.55 and s > 0.8:
                light += 0.12
            if pr.name == "skull":
                # curly forelock between the horns: lighter bumps
                lx, ly = b.inv_head(x + 0.5, y + 0.5)
                if ly > 3 and -6 < lx < 3 and hash01(x, y, 23) > 0.6:
                    light += 0.12
            return ramp(FUR, max(0.0, min(1.0, light)), x, y)
        if zone == "hide":
            light = 0.06 + 0.84 * lam + pr.dark - (0.24 if crease else 0) - 0.16 * max(0.0, 1 - h / 22)
            if pr.name in ("chest", "belly"):
                # pec and ab definition
                lx = x + 0.5 - b.place(-7, 62, 0.8)[0]
                if pr.name == "belly" and abs((y - b.place(-2, 51, 0.3)[1]) % 5 - 2.5) < 0.6 and lx < 0 \
                        and -8 < xr - b.p.lean * 0.4 < 0:
                    light -= 0.12
            return ramp(HIDE, max(0.0, min(1.0, light)), x, y)
        if zone == "muzzle":
            return ramp(MUZZLE, max(0.0, min(1.0, light + 0.04)), x, y, 0.45)
        if zone == "ear":
            lx, ly = b.inv_head(x + 0.5, y + 0.5)
            if ly < 2.2 and lx < 11:
                return ramp(MOUTH, 0.5 + 0.4 * lam, x, y)    # inner ear
            return ramp(FUR, max(0.0, min(1.0, light)), x, y)
        if zone == "hoof":
            hx, hy = b.foot(pr.seed == 33)
            cl = abs(x + 0.5 - (hx - 3.2)) < 0.6 and y > GROUND - 4 - (p.lift_f if pr.seed == 33 else p.lift_b)
            if cl:
                return HOOF[0]                               # cloven split
            return ramp(HOOF, max(0.0, min(1.0, light * 1.1)), x, y, 0.4)
        return ramp(FUR, max(0.0, min(1.0, light)), x, y)
    return colour


def arm_colour(b: Body, prims_by_name, near: bool):
    def colour(pr: Prim, x: int, y: int, lam: float, crease: bool, f: Field):
        light = 0.06 + 0.86 * lam + pr.dark
        if crease:
            light -= 0.22
        t = f.T[y - f.y0][x - f.x0]
        if pr.name == "fore" and 0.6 <= t <= 0.9:          # bronze bracer
            edge = t < 0.65 or t > 0.85
            k = light + (0.1 if not edge else -0.15)
            if not edge and hash01(int(t * 20), 1, 3) > 0.5 and abs(f.RD[y - f.y0][x - f.x0] + 2.5) < 0.5:
                k += 0.2
            return ramp(BRONZE, max(0.0, min(1.0, k)), x, y, 0.4)
        if pr.name == "upper" and 0.2 <= t <= 0.36:         # armlet
            edge = t < 0.24 or t > 0.32
            return ramp(BRONZE, max(0.0, min(1.0, light + (-0.15 if edge else 0.08))), x, y, 0.4)
        if pr.name == "fist":
            # knuckle seams across the leading face
            lx, ly = x + 0.5 - pr.ax, y + 0.5 - pr.ay
            fl = lx * pr.ca + ly * pr.sa
            fs = -lx * pr.sa + ly * pr.ca
            if fl > 1.5 and abs(abs(fs) - 1.8) < 0.45:
                return HIDE[0]
            light += 0.03
        return ramp(HIDE, max(0.0, min(1.0, light)), x, y)
    return colour


# ---------------------------------------------------------------- tubes (horns, tail)
def tube(w: int, h: int, pts, rfun, paint) -> Canvas:
    out = Canvas(w, h)
    pts = polyline(list(pts), 0.4)
    n = len(pts)
    best: dict = {}
    for i, (x, y) in enumerate(pts):
        t = i / max(1, n - 1)
        r = max(0.6, rfun(t))
        for yy in range(int(y - r) - 1, int(y + r) + 2):
            for xx in range(int(x - r) - 1, int(x + r) + 2):
                ddx, ddy = xx + 0.5 - x, yy + 0.5 - y
                d = math.hypot(ddx, ddy) / r
                if d > 1:
                    continue
                key = (xx, yy)
                if key not in best or d < best[key][0]:
                    best[key] = (d, t, (ddx * -0.6 + ddy * -0.8) / r)
    for (xx, yy), (d, t, side) in best.items():
        c = paint(t, d, side, xx, yy)
        if c is not None:
            out.put(xx, yy, c)
    return out


def bez3(p0, p1, p2, p3, n=40):
    out = []
    for i in range(n):
        t = i / (n - 1)
        a, bb, c, d = (1 - t) ** 3, 3 * (1 - t) ** 2 * t, 3 * (1 - t) * t * t, t ** 3
        out.append((a * p0[0] + bb * p1[0] + c * p2[0] + d * p3[0],
                    a * p0[1] + bb * p1[1] + c * p2[1] + d * p3[1]))
    return out


def horn(b: Body, near: bool) -> tuple[Canvas, tuple]:
    if near:
        pts = [b.hp(*q) for q in ((1.0, 6.0), (-1.0, 14.5), (-9.5, 19.5), (-18.5, 16.0))]
        r0, chip = 3.6, 1.0
        dark = 0.0
    else:
        pts = [b.hp(*q) for q in ((6.0, 6.0), (10.5, 12.5), (8.5, 18.5), (2.5, 20.0))]
        r0, chip = 3.1, 0.8                                  # chipped: ends early, broken face
        dark = -0.2
    path = bez3(*pts, n=36)
    path = path[:max(2, int(len(path) * chip))]

    def rfun(t):
        return r0 * (1 - t) ** 0.75 + (0.7 if near else 1.3)

    def paint(t, d, side, x, y):
        light = 0.55 + 0.4 * side - 0.25 * d * d + dark
        if near:
            tip = t > 0.82 or (t > 0.74 and bayer(x, y) < (t - 0.74) / 0.08)
        else:
            tip = t > 0.82 or (t > 0.72 and bayer(x, y) < (t - 0.72) / 0.1)
        if tip:
            return ramp(HORN_TIP, max(0.0, min(1.0, light + 0.1)), x, y, 0.4)
        ring = (t * 11) % 1.0
        if t < 0.62 and ring < 0.14:
            light -= 0.22
        return ramp(HORN, max(0.0, min(1.0, light)), x, y, 0.5)
    cv = tube(CELL_W, CELL_H, path, rfun, paint)
    if not near:                                             # broken face at the chipped end
        ex, ey = path[-1]
        for ox in (-1, 0, 1):
            for oy in (-1, 0, 1):
                if cv.get(round(ex) + ox, round(ey) + oy) is not None and hash01(ox, oy, 31) > 0.35:
                    cv.put(round(ex) + ox, round(ey) + oy, HORN[2] if oy < 0 else HORN[1])
    return cv, path[-1]


def tail(b: Body) -> Canvas:
    p = b.p
    base = b.place(15, 44)
    sw = p.tail
    pts = bez3(base, (base[0] + 9, base[1] + 3), (base[0] + 12 + 5 * sw, base[1] + 18),
               (base[0] + 9 + 8 * sw, base[1] + 30), n=30)

    def rfun(t):
        if t > 0.78:
            return 1.6 + 2.2 * math.sin((t - 0.78) / 0.22 * math.pi) ** 0.7
        return 1.9 - 0.6 * t

    def paint(t, d, side, x, y):
        light = 0.38 + 0.3 * side - 0.2 * d - 0.12
        if t > 0.8:
            light += (hash01(x, y, 41) - 0.5) * 0.3
            if d > 0.75 and hash01(x, y // 2, 42) > 0.55:
                return None
        return ramp(FUR, max(0.0, min(1.0, light)), x, y)
    return tube(CELL_W, CELL_H, pts, rfun, paint)


def loincloth(b: Body, front: bool, t: float) -> Canvas:
    p = b.p
    cv = Canvas(CELL_W, CELL_H)
    if front:
        L, R, ln, dark = b.place(-12, 37.5), b.place(0, 37.5), 18.0, 0.0
    else:
        L, R, ln, dark = b.place(7, 38), b.place(16, 38), 15.0, -0.22
    top = min(L[1], R[1])
    wspan = R[0] - L[0]
    bottom_y = int(top + ln + 3)
    for y in range(int(top), min(GROUND + 1, bottom_y + 1)):
        k = (y - top) / ln
        if k < 0:
            continue
        sway = (1.4 * math.sin(p.phase + 0.6) + 7.0 * p.wind) * k ** 1.3
        xl = L[0] + (R[1] - L[1]) * 0 + sway - 0.6 * k
        xr = L[0] + wspan + sway - 1.6 * k
        for x in range(int(xl), int(xr) + 1):
            u = (x + 0.5 - xl) / max(1.0, xr - xl)
            hem = ln + 1.8 * math.sin(u * 9 + 1.3 + p.phase * 0.5) - 3.5 * (hash01(int(u * 6), 2, 51) > 0.6) \
                - 2.0 * (u < 0.15 or u > 0.88)
            if y - top > hem:
                continue
            fold = math.cos(u * 10 + 0.6 * math.sin(p.phase))
            light = 0.62 - 0.35 * u - 0.25 * k + 0.16 * fold + dark
            if y - top < 1.5:
                light -= 0.3                                  # shadow under the belt
            if y - top > hem - 1.5:
                light -= 0.18                                 # frayed hem
            c = ramp(CLOTH, max(0.0, min(1.0, light)), x, y)
            if front and abs(u - 0.5) < 0.09 and 4 < y - top < 9:
                c = BRONZE[3] if y - top < 6 else BRONZE[1]   # bronze ring on the flap
            cv.put(x, y, c)
    return cv


# ---------------------------------------------------------------- face
def draw_face(cv: Canvas, b: Body, p: Pose):
    hp = b.hp
    # heavy brow ridge
    for lx in range(-7, 3):
        x, y = hp(lx + 0.5, 3.2 + 0.18 * (lx + 7))
        if cv.get(int(x), int(y)) is not None:
            cv.put(int(x), int(y), OUTLINE)
        x2, y2 = hp(lx + 0.5, 4.6 + 0.18 * (lx + 7))
        if cv.get(int(x2), int(y2)) is not None and lx < 0:
            cv.put(int(x2), int(y2), FUR[4])
    # eye: slanted, glowing red
    ex, ey = hp(-3.5, 1.5)
    ex, ey = int(ex), int(ey)
    e = p.eye
    if e > 0.05:
        hot = EYE[3] if e > 1.2 else EYE[2]
        cv.put(ex - 1, ey + 1, EYE[1])
        cv.put(ex, ey, hot)
        cv.put(ex + 1, ey, EYE[2] if e > 0.7 else EYE[1])
        cv.put(ex + 2, ey - 1, EYE[1])
        if e > 1.3:
            cv.put(ex - 1, ey, EYE[2])
            cv.put(ex + 1, ey - 1, EYE[2])
    else:
        for ox, oy in ((-1, 1), (0, 0), (1, 0), (2, -1)):
            cv.put(ex + ox, ey + oy, OUTLINE)
    # nostrils
    nx, ny = hp(-17.2, -6.4)
    cv.put(int(nx), int(ny), OUTLINE)
    cv.put(int(nx) + 1, int(ny), MUZZLE[0])
    nx2, ny2 = hp(-14.6, -4.6)
    cv.put(int(nx2), int(ny2), MUZZLE[0])
    # mouth line / open mouth
    jaw = p.jaw
    if jaw < 0.15:
        for lx in range(-17, -6):
            x, y = hp(lx + 0.5, -10.6 + 0.1 * (lx + 17))
            if cv.get(int(x), int(y)) is not None:
                cv.put(int(x), int(y), MUZZLE[0])
    else:
        hinge = (-4.0, -10.0)
        for yy in range(int(b.head[1] - 20), int(b.head[1] + 22)):
            for xx in range(int(b.head[0] - 24), int(b.head[0] + 6)):
                lx, ly = b.inv_head(xx + 0.5, yy + 0.5)
                if not (-19.5 < lx < hinge[0]):
                    continue
                up = -10.4 + 0.08 * (lx + 19)
                lo = up - jaw * 0.55 * (hinge[0] - lx)
                if lo < ly < up:
                    k = (up - ly) / max(0.5, up - lo)
                    c = MOUTH[2] if k > 0.6 and lx < -12 else MOUTH[1] if k > 0.3 else MOUTH[0]
                    if lx < -16 and (up - ly) < 1.2:
                        c = (236, 226, 204)                  # teeth
                    cv.put(xx, yy, c)
    # gold nose ring
    rcx, rcy = hp(-18.2, -10.4)
    for k in range(10):
        a = k / 10 * math.tau
        x, y = rcx + math.cos(a) * 2.1, rcy + math.sin(a) * 2.1
        col = GOLD[3] if (math.cos(a) < -0.2 and math.sin(a) < 0.3) else GOLD[2] if math.sin(a) < 0.5 else GOLD[1]
        cv.put(int(x), int(y), col)
    return (ex + 0.5, ey + 0.5), (nx + 0.5, ny + 0.5)


# ---------------------------------------------------------------- effects
def puff(cv: Canvas, cx: float, cy: float, r: float, a: float, cols, seed: int = 0) -> None:
    if a <= 0.02 or r <= 0.3:
        return
    for yy in range(int(cy - r) - 1, int(cy + r) + 2):
        for xx in range(int(cx - r) - 1, int(cx + r) + 2):
            d = math.hypot(xx + 0.5 - cx, (yy + 0.5 - cy) * 1.15) / r
            if d > 1:
                continue
            if d > 0.55 and bayer(xx, yy) > (1.2 - d) * 1.6:
                continue
            lvl = len(cols) - 1 if d < 0.3 and yy < cy else len(cols) - 2 if d < 0.65 else max(0, len(cols) - 3)
            cv.put(xx, yy, cols[lvl], solid=False, alpha=int(255 * min(1.0, a * (1.15 - 0.45 * d))))


def draw_steam(cv: Canvas, nostril, s: float, big: bool, facing: float = -1.0) -> None:
    if s < 0:
        return
    nx, ny = nostril
    n = 4 if big else 2
    for j in range(n):
        delay = j * 0.14
        u = (s - delay) / (1 - delay) if s > delay else -1
        if u < 0:
            continue
        dist = (12 + 16 * big) * smooth(u) + 2
        ang = 0.55 + 0.35 * hash01(j, 1, 61) + (0.25 if big else 0)
        x = nx + facing * dist * math.cos(ang) + (j - 1) * 1.5 * big
        y = ny + dist * math.sin(ang) * 0.55 - (5 + 6 * big) * u * u
        r = (1.8 + (4.2 + 2.6 * big) * u) * (1 - 0.25 * hash01(j, 2, 61))
        a = (1 - u) ** 1.1 * 0.95
        puff(cv, x, y, r, a, STEAM)


def shard(cv: Canvas, x: float, base: int, hgt: float, w: float, lean: float) -> None:
    """A jagged rock spike jutting from the floor, lit from the upper left."""
    n = int(hgt)
    for j in range(n):
        k = j / max(1, n)
        half = w * (1 - k) ** 0.9
        cx = x + lean * k * hgt
        for i in range(int(cx - half - 0.5), int(cx + half + 1.5)):
            u = (i + 0.5 - cx) / max(0.6, half)
            if abs(u) > 1.05:
                continue
            light = 0.75 - 0.5 * u - 0.15 * (1 - k)
            cv.put(i, base - j, ramp(ROCK, max(0.0, min(1.0, light)), i, base - j, 0.4))


def draw_shock(cv: Canvas, p: Pose) -> None:
    s, fade = p.shock, p.shock_fade
    if s <= 0:
        return
    vis = 1 - fade
    x0 = CX + p.shock_x
    gy = GROUND
    front = x0 - (x0 - 10) * min(1.0, s)
    # jagged crack from the hoof to the front: dark, 2 px, hot core near the hoof
    y = gy + 1.0
    x = x0
    i = 0
    while x > front + 2:
        x -= 1
        i += 1
        if hash01(i, 3, 71) > 0.6:
            y += 1 if hash01(i, 4, 71) > 0.5 else -1
        y = max(gy, min(gy + 3, y))
        if vis > 0.1:
            a = int(255 * min(1.0, vis * 1.6))
            cv.put(round(x), round(y), OUTLINE, solid=False, alpha=a)
            cv.put(round(x), round(y) + 1, OUTLINE, solid=False, alpha=int(a * 0.7))
            heat = (1 - fade) * (1 - (x0 - x) / max(1.0, x0 - front) * 0.6) * (1.0 if s < 1.02 else 0.6)
            if heat > 0.35 and hash01(i, 6, 71) > 0.35:
                cv.put(round(x), round(y), RAGE[3] if heat > 0.75 and i % 3 else RAGE[2], solid=False,
                       alpha=int(255 * min(1.0, heat)))
            if hash01(i, 5, 71) > 0.82:                        # side branches
                cv.put(round(x) - 1, round(y) + 1, OUTLINE, solid=False, alpha=int(200 * vis))
                cv.put(round(x) - 2, round(y) + 2, OUTLINE, solid=False, alpha=int(150 * vis))
    # settling dust along the crack
    for k in range(9):
        u = (k + hash01(k, 8, 74)) / 9
        cx = x0 + (front - x0) * u
        a = vis * 0.55 * (0.4 + 0.6 * u)
        r = 2.2 + 4.5 * hash01(k, 7, 72) * (0.5 + 0.5 * u)
        puff(cv, cx, gy - 1 - r * 0.6 - 2 * hash01(k, 6, 72), r, a, DUST)
    # the travelling front: rock spikes erupting and a rolling dust wall
    if s <= 1.02 and vis > 0.1:
        for k in range(4):
            sx = front + 1 + k * 4.5 + hash01(k, 4, 72) * 2
            if sx > x0 - 8:
                continue
            grow = 1 - k * 0.22
            shard(cv, sx, gy, (6 + 7 * hash01(k, 5, 72)) * grow, 2.2 + 1.2 * hash01(k, 6, 73),
                  -0.25 + 0.5 * hash01(k, 7, 73))
        for k in range(6):
            cx = front + 2 + 14 * hash01(k, 1, 72)
            cy = gy - 4 - 10 * hash01(k, 2, 72)
            puff(cv, cx, cy, 4 + 4 * hash01(k, 3, 72), 0.85, DUST)
        # chips thrown up from the front
        for k in range(8):
            ph = (s * 3 + hash01(k, 8, 72)) % 1.0
            x = front + 3 + (hash01(k, 9, 72) - 0.6) * 16 * ph
            y = gy - 4 - 22 * ph + 26 * ph * ph
            cv.put(round(x), round(y), ROCK[3] if k % 2 else DUST[3])
            cv.put(round(x) + 1, round(y), ROCK[1])
            cv.put(round(x), round(y) + 1, ROCK[0])
    elif vis > 0.1:                                         # spikes crumble back as it fades
        for k in range(3):
            sx = front + 1 + k * 4.5 + hash01(k, 4, 72) * 2
            shard(cv, sx, gy, (6 + 7 * hash01(k, 5, 72)) * (1 - k * 0.22) * max(0.0, vis - 0.2),
                  2.2 + 1.2 * hash01(k, 6, 73), -0.25 + 0.5 * hash01(k, 7, 73))
            puff(cv, sx, gy - 4, 4 + 3 * fade, 0.6 * vis, DUST)
    # impact at the hoof: white starburst + dust ring
    if s < 0.6:
        kk = 1 - s / 0.6
        for r in range(11):
            ang = math.pi + r / 10 * math.pi
            ln = (6 + 9 * hash01(r, 2, 73)) * (0.5 + kk)
            for j in range(int(ln)):
                x = x0 + math.cos(ang) * (3 + j)
                y = gy - 2 + math.sin(ang) * (3 + j) * 0.75
                cv.put(round(x), round(y), WHITE if j < ln * 0.45 else DUST[3], solid=False,
                       alpha=int(255 * min(1.0, kk + 0.2)))
        for side in (-1, 1):
            for k in range(3):
                puff(cv, x0 + side * (5 + 9 * (1 - kk) + 4 * k), gy - 3 - k, 3.5 + 2 * (1 - kk), 0.9 * kk + 0.1,
                     DUST)


def draw_speed(cv: Canvas, b: Body, k: float) -> None:
    if k <= 0:
        return
    for j in range(11):
        h = 8 + 70 * hash01(j, 1, 81)
        x0 = b.bx + 18 + 10 * hash01(j, 2, 81)
        ln = (16 + 34 * hash01(j, 3, 81)) * k
        y = GROUND - h
        for i in range(int(ln)):
            if bayer(int(x0 + i), int(y)) > (1 - i / max(1.0, ln)) * 1.2:
                continue
            c = STEAM[2] if i < ln * 0.3 else DUST[3]
            cv.put(round(x0 + i), round(y), c, solid=False, alpha=int(200 * (1 - i / ln)))


def draw_trail(cv: Canvas, b: Body, k: float) -> None:
    if k <= 0:
        return
    for j in range(10):
        u = (j + hash01(j, 2, 82) * 0.6) / 10
        cx = b.bx + 12 + 75 * u
        if cx > CELL_W + 6:
            continue
        r = (2.5 + 5 * u * k) * (0.6 + 0.7 * hash01(j, 3, 82))
        a = k * (1 - u) * 0.9
        puff(cv, cx, GROUND - 2 - r * 0.5 - 4 * u * hash01(j, 1, 82), r, a, DUST)


def draw_impact(cv: Canvas, at, k: float) -> None:
    if k <= 0:
        return
    x0, y0 = at
    big = math.sin(min(1.0, k) * math.pi * 0.5 + 0.4)
    for r in range(14):
        ang = r / 14 * math.tau + 0.2 * hash01(r, 1, 83)
        ln = (7 + 14 * hash01(r, 2, 83)) * big
        for j in range(int(ln)):
            x = x0 + math.cos(ang) * (3 + j)
            y = y0 + math.sin(ang) * (3 + j)
            c = WHITE if j < ln * 0.45 else RAGE[3] if j < ln * 0.75 else RAGE[2]
            cv.put(round(x), round(y), c, solid=False, alpha=int(255 * min(1.0, k + 0.2)))
    puff(cv, x0, y0, 4 * big, 0.95, [RAGE[3], STEAM[2], WHITE])
    for k2 in range(8):
        tt = (1.2 - k) * 0.8
        x = x0 + (hash01(k2, 3, 83) * 22) * tt * 1.5
        y = y0 + (-14 + 28 * hash01(k2, 4, 83)) * tt
        cv.put(round(x), round(y), ROCK[3])


def draw_dust(cv: Canvas, b: Body, k: float) -> None:
    if k <= 0:
        return
    for side, base in ((-1, b.bx + b.p.foot_f), (1, b.bx + b.p.foot_b)):
        for j in range(4):
            cx = base + side * (2 + 10 * k * hash01(j, side + 2, 84))
            cy = GROUND - 1 - 4 * k * hash01(j, 4, 84)
            puff(cv, cx, cy, 2 + 3 * k, 0.7 * (1 - 0.5 * k), DUST)


def draw_skid(cv: Canvas, b: Body, k: float) -> None:
    if k <= 0:
        return
    for j in range(6):
        cx = b.bx - 22 - 9 * j * hash01(j, 1, 85) + 6
        puff(cv, cx, GROUND - 2 - 3 * hash01(j, 2, 85), 2 + 4 * k * hash01(j, 3, 85) + 1, 0.8 * k, DUST)
    for i in range(int(30 * k)):                              # furrows
        cv.put(round(b.bx - 18 + i), GROUND + 1, OUTLINE, solid=False, alpha=160)


def draw_kick(cv: Canvas, b: Body, s: float) -> None:
    """Dirt clods and a dust spray kicked back (right) by the scraping hoof."""
    if s < 0:
        return
    hx, _ = b.foot(True)
    puff(cv, hx + 6 + 12 * s, GROUND - 3 - 5 * s, 3 + 4 * s, 0.9 * (1 - s * 0.7), DUST)
    for k in range(13):
        tt = s * (0.7 + 0.5 * hash01(k, 1, 86))
        vx = 26 + 40 * hash01(k, 2, 86)
        vy = 34 + 36 * hash01(k, 3, 86)
        x = hx + 4 + vx * tt
        y = GROUND - 2 - vy * tt + 64 * tt * tt
        if y > GROUND:
            continue
        x, y = round(x), round(y)
        big = k % 3 == 0
        cv.put(x, y, DUST[3] if k % 2 else DUST[2])
        cv.put(x + 1, y, DUST[2])
        cv.put(x, y + 1, DUST[1])
        cv.put(x + 1, y + 1, DUST[0])
        if big:
            cv.put(x + 2, y, DUST[1])
            cv.put(x + 2, y + 1, DUST[0])
            cv.put(x + 1, y - 1, DUST[3])


def draw_scrape(cv: Canvas, p: Pose) -> None:
    if p.scrape <= 0:
        return
    for j, (ln, dy) in enumerate(((14, 1), (10, 2))):
        for i in range(ln):
            x = CX + p.dx + p.scrape_x + 4 + i
            if hash01(i, j, 87) > 0.8:
                continue
            cv.put(round(x), GROUND + dy, OUTLINE, solid=False, alpha=int(200 * p.scrape))
            if i % 3 == 0:
                cv.put(round(x), GROUND + dy - 1, DUST[2], solid=False, alpha=int(180 * p.scrape))


def draw_rage(cv: Canvas, k: float, t: float, phase: float) -> None:
    """Red aura hugging the silhouette + heat shimmer wisps rising."""
    if k <= 0:
        return
    solid = cv.solid
    w, h = cv.w, cv.h
    dist = {}
    for y in range(h):
        for x in range(w):
            c = cv.px[y][x]
            if c is not None and c[3] > 120:
                dist[(x, y)] = 0
    frontier = list(dist)
    R = 4
    for step in range(1, R + 1):
        nxt = []
        for (x, y) in frontier:
            for ox, oy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                q = (x + ox, y + oy)
                if q in dist or not (0 <= q[0] < w and 0 <= q[1] < h):
                    continue
                if cv.px[q[1]][q[0]] is not None:
                    continue
                dist[q] = step
                nxt.append(q)
        frontier = nxt
    flick = 0.5 + 0.5 * math.sin(phase * 3)
    step = int(phase * 4)
    for (x, y), dd in dist.items():
        if dd == 0 or y > GROUND + 1:
            continue
        n = hash01(x // 2, (y + step * 2) // 3, 95)
        a = k * (1 - (dd - 1) / R) * (0.6 + 0.4 * flick) * (0.55 + 0.7 * n)
        if bayer(x, y + step) > a * 1.3:
            continue
        c = RAGE[3] if dd == 1 else RAGE[2] if dd == 2 else RAGE[1]
        cv.put(x, y, c, solid=False, alpha=int(255 * min(0.9, a + 0.2)))
    # flame tongues licking up from the top edges
    for x in range(w):
        top = next((y for y in range(h) if dist.get((x, y)) == 0), None)
        if top is None or top > GROUND - 20:
            continue
        hk = hash01(x // 2, step, 96)
        if hk < 0.45:
            continue
        ln = int(k * (3 + 9 * (hk - 0.45) / 0.55))
        for j in range(ln):
            yy = top - R + 1 - j
            if yy < 0:
                break
            u = j / max(1, ln)
            xx = x + round(1.2 * math.sin(j * 0.7 + x + phase * 3) * u)
            c = RAGE[3] if u < 0.3 else RAGE[2] if u < 0.7 else RAGE[1]
            cv.put(xx, yy, c, solid=False, alpha=int(230 * (1 - u * 0.6) * k))
    # tint the body edge red
    for y in range(h):
        for x in range(w):
            if solid[y][x] and any(dist.get(q) == 1 for q in ((x - 2, y), (x + 2, y), (x, y - 2), (x, y + 2))):
                cv.tint(x, y, RAGE[2], 0.4 * k)


def draw_shimmer(cv: Canvas, b: Body, k: float, phase: float) -> None:
    if k <= 0:
        return
    for j in range(7):
        x0 = b.bx - 30 + j * 9 + 3 * hash01(j, 1, 88)
        base = GROUND - 70 - 10 * hash01(j, 2, 88)
        ln = 10 + 12 * hash01(j, 3, 88)
        rise = (phase * 0.7 + hash01(j, 4, 88)) % 1.0
        for i in range(int(ln)):
            y = base - i - rise * 8
            x = x0 + 1.3 * math.sin(i * 0.6 + phase * 2 + j)
            if bayer(int(x), int(y)) > k * (1 - i / ln):
                continue
            cv.put(round(x), round(y), RAGE[3] if i < ln * 0.3 else RAGE[2], solid=False,
                   alpha=int(170 * k * (1 - i / ln)))


# ---------------------------------------------------------------- render
def render(p: Pose, t: float = 0.0) -> Canvas:
    cv = Canvas(CELL_W, CELL_H)
    if p.dissolve >= 1.0:
        return cv
    b = Body(p)
    # ---- back layer (darker): tail, far horn, far leg, far arm, back flap
    back = Canvas(CELL_W, CELL_H)
    back.blit(tail(b))
    far_horn, _ = horn(b, False)
    back.blit(far_horn)
    fl = Field(leg_prims(b, False, -0.2, 40))
    paint_field(back, fl, b, body_colour(b))
    back.blit(loincloth(b, False, t), rim=OUTLINE)
    farm, _, _ = arm_prims(b, False, -0.3)
    fa = Field(farm)
    arm_b = Canvas(CELL_W, CELL_H)
    paint_field(arm_b, fa, b, arm_colour(b, None, False))
    back.blit(arm_b, rim=OUTLINE)
    cv.blit(back)
    # ---- main mass
    main = Canvas(CELL_W, CELL_H)
    fm = Field(body_prims(b))
    paint_field(main, fm, b, body_colour(b))
    eye_c, nostril = draw_face(main, b, p)
    cv.blit(main, rim=OUTLINE)
    # ---- on top: loincloth, near arm, near horn
    cv.blit(loincloth(b, True, t), rim=OUTLINE)
    narm, fist_c, _ = arm_prims(b, True, 0.0)
    na = Field(narm)
    arm_f = Canvas(CELL_W, CELL_H)
    paint_field(arm_f, na, b, arm_colour(b, None, True))
    cv.blit(arm_f, rim=OUTLINE)
    nh, tip = horn(b, True)
    cv.blit(nh, rim=OUTLINE)
    outline(cv, OUTLINE)
    # ---- lights
    if p.eye > 0.05:
        cv.glow(eye_c[0], eye_c[1], 3 + 3 * p.eye, EYE[1], 0.3 * p.eye)
    draw_rage(cv, p.rage, t, p.phase)
    draw_shimmer(cv, b, p.rage, p.phase)
    # ---- effects
    draw_steam(cv, nostril, p.steam, False)
    draw_steam(cv, nostril, p.steam_big, True)
    draw_speed(cv, b, p.speed)
    draw_trail(cv, b, p.trail)
    draw_scrape(cv, p)
    draw_kick(cv, b, p.kick)
    draw_shock(cv, p)
    draw_impact(cv, tip, p.impact)
    draw_skid(cv, b, p.skid)
    draw_dust(cv, b, p.dust)
    for (mx, my, lv) in p.motes:
        cv.put(mx, my, DUST[lv], solid=False)
    flash(cv, p.flash)
    if p.dissolve > 0:
        dissolve(cv, p.dissolve, GROUND - 40, GROUND + 3, DUST[3], DUST[2], upward=False)
    return cv


# ---------------------------------------------------------------- animations
IDLE_FRAMES = 12


def idle_pose(i: int, n: int = IDLE_FRAMES) -> Pose:
    i %= n
    a = math.tau * i / n
    breath = round(math.sin(a))
    return Pose(
        breath=breath, phase=a,
        hy=round(0.7 * math.sin(a - 0.7)),
        fist_f=(-17 + round(0.6 * math.sin(a + 0.4)), 38 + round(math.sin(a - 0.4))),
        fist_b=(17, 38 + round(math.sin(a - 0.6))),
        tail=math.sin(a + 0.5),
        eye=1.5 if i == 9 else 1.0,
        steam=(i - 3) / 6 if 3 <= i <= 8 else -1.0,
    )


def idle_frames():
    return [(idle_pose(i), 120) for i in range(IDLE_FRAMES)]


def attack_frames():
    """Pisotón: rear up on the back leg, front hoof high, slam; the shockwave runs left."""
    b = idle_pose(0)
    return [
        (replace(b, tilt=0.07, crouch=1, lift_f=5, foot_f=-14, ha=0.1, eye=1.1, fist_f=(-24, 40),
                 phase=0.3), 100),
        (replace(b, tilt=0.15, dy=-2, lift_f=15, foot_f=-19, ha=0.25, eye=1.3, fist_f=(-16, 62),
                 fist_b=(20, 62), tail=0.6, phase=0.6), 120),
        (replace(b, tilt=0.2, dy=-3, lift_f=22, foot_f=-22, ha=0.3, eye=1.5, jaw=0.3,
                 fist_f=(-12, 76), fist_b=(18, 78), tail=0.9, phase=0.9, steam=0.2), 140),
        (replace(b, tilt=-0.1, crouch=4, sy=0.95, sx=1.04, lift_f=0, foot_f=-20, ha=-0.15, eye=1.6,
                 fist_f=(-32, 26), fist_b=(20, 30), shock=0.12, dust=0.7, tail=-0.4, phase=1.3), 55),
        (replace(b, tilt=-0.1, crouch=4, sy=0.95, sx=1.04, foot_f=-20, ha=-0.15, eye=1.5,
                 fist_f=(-32, 26), fist_b=(20, 30), shock=0.5, dust=0.9, tail=-0.7, phase=1.6), 55),
        (replace(b, tilt=-0.08, crouch=3, sy=0.96, sx=1.03, foot_f=-20, ha=-0.1, eye=1.4,
                 fist_f=(-31, 28), shock=1.0, dust=0.6, tail=-0.5, phase=1.9), 70),
        (replace(b, tilt=-0.05, crouch=2, sy=0.98, foot_f=-19, eye=1.2, fist_f=(-29, 30), shock=1.05,
                 shock_fade=0.35, tail=-0.2, phase=2.4), 90),
        (replace(b, tilt=-0.03, crouch=1, foot_f=-17, fist_f=(-27, 32), shock=1.1, shock_fade=0.65,
                 phase=3.0), 90),
        (replace(b, tilt=-0.01, foot_f=-16, fist_f=(-26, 33), shock=1.1, shock_fade=0.9, phase=3.6), 90),
        (b, 100),
    ]


def charge_frames():
    """Embestida: horns down, one scrape, rush left, horns hit far left, skid, back up."""
    b = idle_pose(0)
    low = dict(ha=-0.5, lean=-7, crouch=4, hy=-2, hx=-2, tilt=-0.05)
    rush = dict(ha=-0.75, lean=-12, crouch=5, hy=-3, hx=-4, tilt=-0.15)
    return [
        (replace(b, ha=-0.25, lean=-3, crouch=2, eye=1.2, fist_f=(-18, 38), phase=0.3), 100),
        (replace(b, **low, lift_f=6, foot_f=-21, eye=1.3, fist_f=(-17, 37), steam_big=0.15, phase=0.6), 100),
        (replace(b, **low, foot_f=-6, kick=0.35, scrape=1.0, scrape_x=-20, eye=1.3, fist_f=(-17, 37),
                 steam_big=0.45, phase=0.9), 80),
        (replace(b, ha=-0.66, lean=-10, crouch=6, hy=-3, hx=-3, tilt=-0.1, foot_f=-12, foot_b=16, eye=1.7,
                 fist_f=(-13, 34), fist_b=(22, 34), kick=0.75, scrape=0.8, scrape_x=-20,
                 steam_big=0.75, tail=0.8, phase=1.2), 160),
        # rush
        (replace(b, **rush, dx=-18, sx=1.08, foot_f=-26, foot_b=22, lift_b=5, fist_f=(-10, 34),
                 fist_b=(26, 36), speed=0.7, trail=0.5, wind=1.0, eye=1.8, tail=1.0, scrape=0.6,
                 scrape_x=-2, phase=1.6), 50),
        (replace(b, **rush, dx=-42, sx=1.1, foot_f=-6, foot_b=4, lift_f=6, fist_f=(-9, 34),
                 fist_b=(24, 36), speed=1.0, trail=0.9, wind=1.0, eye=1.8, tail=1.0, scrape=0.4,
                 scrape_x=22, phase=2.0), 45),
        # impact (strike): horn tips at the far left
        (replace(b, **{**rush, "ha": -0.8}, dx=-62, sx=0.95, sy=0.98, foot_f=-24, foot_b=20,
                 fist_f=(-11, 33), fist_b=(24, 35), impact=1.0, speed=0.5, trail=0.8, wind=0.6, eye=2.0,
                 tail=0.6, dust=0.8, phase=2.3), 65),
        (replace(b, **{**rush, "ha": -0.65, "tilt": -0.1}, dx=-59, sx=0.97, foot_f=-24, foot_b=20,
                 fist_f=(-12, 34), fist_b=(23, 35), impact=0.55, trail=0.5, wind=0.2, eye=1.6, tail=0.2,
                 dust=1.0, phase=2.6), 85),
        # skid and back up to the spot
        (replace(b, ha=-0.35, lean=-6, crouch=4, hx=-1, tilt=-0.04, dx=-54, foot_f=-26, foot_b=18,
                 skid=0.9, fist_f=(-17, 36), eye=1.3, tail=-0.3, wind=-0.4, phase=3.0), 100),
        (replace(b, ha=-0.15, lean=-3, crouch=2, dx=-42, foot_f=-12, foot_b=8, lift_b=4, skid=0.5,
                 fist_f=(-17, 37), eye=1.1, tail=-0.5, phase=3.6), 110),
        (replace(b, ha=-0.05, lean=-1, crouch=1, dx=-28, foot_f=-17, foot_b=16, lift_f=3, dust=0.4,
                 fist_f=(-17, 38), tail=-0.2, phase=4.2), 110),
        (replace(b, dx=-15, crouch=1, foot_f=-12, foot_b=10, lift_b=3, dust=0.3, fist_f=(-17, 38),
                 tail=0.2, phase=4.8), 110),
        (replace(b, dx=-5, foot_f=-16, foot_b=14, lift_f=2, fist_f=(-17, 38), tail=0.4, phase=5.4), 100),
        (b, 100),
    ]


def paw_frames():
    """Escarbar: two scrapes of the front hoof, dirt kicked back, big snorts."""
    b = idle_pose(0)
    low = dict(ha=-0.45, lean=-7, crouch=4, hy=-2, hx=-2, tilt=-0.06, fist_f=(-15, 34), fist_b=(19, 35))
    return [
        (replace(b, **{**low, "ha": -0.3, "crouch": 2, "lean": -4}, eye=1.1, phase=0.3), 100),
        (replace(b, **low, lift_f=9, foot_f=-26, eye=1.3, tail=0.5, phase=0.6), 100),
        (replace(b, **low, foot_f=-8, kick=0.25, scrape=1.0, scrape_x=-24, steam=0.3, tail=0.8, phase=0.9), 60),
        (replace(b, **low, lift_f=4, foot_f=0, kick=0.6, scrape=0.9, scrape_x=-24, steam=0.75, tail=1.0,
                 phase=1.2), 80),
        (replace(b, **low, lift_f=9, foot_f=-26, eye=1.5, kick=0.95, scrape=0.8, scrape_x=-24,
                 steam_big=0.12, tail=0.4, phase=1.5), 100),
        (replace(b, **low, foot_f=-8, kick=0.25, scrape=1.0, scrape_x=-24, steam_big=0.35, eye=1.6,
                 tail=0.9, phase=1.8), 60),
        (replace(b, **low, lift_f=4, foot_f=0, kick=0.6, scrape=0.9, scrape_x=-24, steam_big=0.6, eye=1.6,
                 tail=1.0, phase=2.1), 80),
        (replace(b, **{**low, "ha": -0.3, "crouch": 2}, foot_f=-12, kick=0.95, scrape=0.6, scrape_x=-24,
                 steam_big=0.85, eye=1.4, phase=2.4), 110),
        (replace(b, ha=-0.1, crouch=1, foot_f=-14, scrape=0.3, scrape_x=-24, fist_f=(-17, 37), phase=2.9), 100),
        (b, 100),
    ]


def cast_frames():
    """Furia Taurina: head thrown back, roar, chest up, red aura pulses, eyes blaze."""
    b = idle_pose(0)
    return [
        (replace(b, crouch=2, ha=-0.2, eye=1.3, rage=0.15, fist_f=(-24, 32), phase=0.3), 100),
        (replace(b, tilt=0.08, ha=0.3, jaw=0.4, eye=1.6, rage=0.45, fist_f=(-24, 46), fist_b=(25, 46),
                 breath=1, phase=0.8), 110),
        (replace(b, tilt=0.14, sy=1.03, ha=0.62, jaw=1.0, eye=2.0, rage=1.0, fist_f=(-27, 54),
                 fist_b=(28, 54), breath=1, tail=0.8, steam_big=0.2, phase=1.3), 130),
        (replace(b, tilt=0.15, sy=1.03, ha=0.66, jaw=1.0, eye=2.0, rage=0.75, fist_f=(-27, 55),
                 fist_b=(28, 55), breath=1, tail=1.0, steam_big=0.5, phase=1.8), 110),
        (replace(b, tilt=0.14, sy=1.03, ha=0.62, jaw=0.9, eye=2.0, rage=1.0, fist_f=(-27, 54),
                 fist_b=(28, 54), breath=1, tail=0.6, steam_big=0.8, phase=2.3), 110),
        (replace(b, tilt=0.08, ha=0.3, jaw=0.4, eye=1.6, rage=0.6, fist_f=(-25, 44), fist_b=(24, 44),
                 phase=2.9), 100),
        (replace(b, tilt=0.03, ha=0.08, jaw=0.1, eye=1.3, rage=0.3, fist_f=(-25, 38), phase=3.5), 100),
        (replace(b, eye=1.1, rage=0.1, fist_f=(-25, 35), phase=4.1), 90),
        (b, 100),
    ]


def hurt_frames():
    b = idle_pose(0)
    return [
        (replace(b, dx=3, tilt=0.08, ha=0.32, jaw=0.3, flash=0.82, eye=0.5, fist_f=(-20, 36),
                 tail=-0.8, phase=0.8), 60),
        (replace(b, dx=4, tilt=0.1, ha=0.25, jaw=0.2, flash=0.45, eye=0.7, fist_f=(-20, 36),
                 tail=-1.0, dust=0.4, phase=1.3), 70),
        (replace(b, dx=3, tilt=0.06, ha=0.1, flash=0.15, eye=0.9, fist_f=(-22, 35), dust=0.6,
                 phase=1.9), 80),
        (replace(b, dx=1, tilt=0.02, fist_f=(-24, 34), phase=2.6), 90),
        (replace(b, phase=3.3), 90),
        (b, 100),
    ]


def death_frames():
    b = idle_pose(0)
    out = [
        (replace(b, dx=2, tilt=0.08, ha=0.3, jaw=0.4, flash=0.85, eye=0.6, fist_f=(-20, 36)), 70),
        (replace(b, dx=4, tilt=0.12, ha=0.5, jaw=0.9, eye=1.6, fist_f=(-18, 42), fist_b=(26, 40),
                 foot_b=15, phase=0.5), 110),
        (replace(b, dx=3, tilt=0.02, ha=0.1, jaw=0.4, eye=1.2, foot_f=-12, foot_b=14,
                 fist_f=(-22, 30), phase=1.0), 100),
        (replace(b, dx=2, tilt=-0.08, crouch=9, ha=-0.2, jaw=0.2, eye=0.9, foot_f=-12, foot_b=16,
                 fist_f=(-24, 20), fist_b=(18, 24), phase=1.4), 110),
        (replace(b, dx=2, tilt=-0.14, crouch=16, ha=-0.3, eye=0.7, foot_f=-6, foot_b=18,
                 fist_f=(-28, 8), fist_b=(16, 12), dust=0.5, phase=1.8), 120),
        (replace(b, dx=2, tilt=-0.22, crouch=18, ha=-0.3, eye=0.6, foot_f=-4, foot_b=18,
                 fist_f=(-32, 4), fist_b=(14, 6), dust=0.3, phase=2.1), 130),
        (replace(b, dx=2, tilt=-0.55, crouch=19, ha=-0.1, eye=0.4, foot_f=-2, foot_b=18,
                 fist_f=(-40, 3), fist_b=(6, 4), phase=2.4), 80),
        (replace(b, dx=2, tilt=-0.85, crouch=19, ha=0.15, eye=0.2, foot_f=0, foot_b=18,
                 fist_f=(-46, 3), fist_b=(-2, 3), dust=0.7, phase=2.6), 70),
        (replace(b, dx=2, tilt=-0.92, crouch=19, ha=0.2, eye=0.0, foot_f=0, foot_b=18,
                 fist_f=(-47, 3), fist_b=(-4, 3), dust=1.0, phase=2.7), 150),
    ]
    lying = out[-1][0]
    steps = [0.15, 0.32, 0.5, 0.68, 0.85]
    for k, d in enumerate(steps):
        motes = tuple((round(CX - 70 + hash01(k, j, 91) * 90), round(GROUND - 6 - hash01(j, k, 92) * 30 * (0.3 + d)),
                       1 + int(hash01(j, k, 93) * 3)) for j in range(6 + 2 * k))
        out.append((replace(lying, dissolve=d, dust=max(0.0, 0.8 - 0.15 * k), motes=motes), 90))
    out.append((replace(lying, dissolve=1.0), 120))
    return out


ANIMATIONS = {
    "idle": (idle_frames, True),
    "attack": (attack_frames, False),
    "charge": (charge_frames, False),
    "paw": (paw_frames, False),
    "cast": (cast_frames, False),
    "hurt": (hurt_frames, False),
    "death": (death_frames, False),
}

# Frames where a hit lands: the shockwave reaches the left; the horns hit.
EVENTS = {"attack": {"strikes": [5]}, "charge": {"strikes": [6]}}
MOVES = {"stomp": "attack", "charge": "charge", "paw": "paw", "rage": "cast", "vengeance": "cast"}


def build():
    return build_sheet(ANIMATIONS, render, (CELL_W, CELL_H), ANCHOR, f"{SHEET_ID}_sheet.png",
                       {"events": EVENTS, "moves": MOVES, "boss": True, "elite": True})


def main() -> None:
    sheet, meta = build()
    save_sheet(OUT_DIR, SHEET_ID, sheet, meta)
    print(f"wrote assets/enemies/{SHEET_ID}_sheet.png ({len(sheet[0])}x{len(sheet)}) and .json")


if __name__ == "__main__":
    main()
