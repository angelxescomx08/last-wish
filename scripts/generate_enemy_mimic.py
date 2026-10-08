"""Draw and animate the enemy "Mímico" (a treasure-chest mimic). Stdlib only:

    python scripts/generate_enemy_mimic.py

Same method as the Espectro (``docs/code-drawn-sprites.md``): one renderer, every
frame a ``Pose``. The mimic is a small wooden chest seen in 3/4 view, its lock
facing the hero (left):

* the chest is built from planar parts (planks, end panel, barrel lid strips,
  teeth) in a tiny oblique 3D space and rasterised with a depth buffer, so ONE
  number -- the lid angle -- drives the whole render: the lid rotates about its
  back hinge, the jaws part, the mouth, tongue and eyes appear by themselves;
* dark warm wood planks (grain streaks, upper-left light), iron bands with
  rivets, a gold lock plate and hasp, stubby clawed feet;
* inside: a dark-crimson mouth, a ribbed palate, jagged teeth on both jaws, a
  long purple-red tongue, gold coins, and two hungry yellow-green eyes that peek
  from the gap.

Animations (non-death actions end on idle frame 0):
  idle    12-frame loop: the lid breathes ajar, eyes glint, the tongue peeks once, a coin glints
  attack  "Mordisco Voraz": the lid creaks wide (drool), lunge left, SLAM shut (splinters, spit), hop back
  lick    "Lengüetazo": three whip lashes of the tongue towards the hero
  cast    "Fingir": slams shut tight, plays an innocent chest, a glint runs over the lock
  hurt    white flash, the lid bangs, coins fly, knocked right
  death   the lid flops open, the tongue lolls, the chest falls apart, coins scatter, dissolve

Output: ``assets/enemies/mimic_sheet.png`` + ``.json`` (``events.<anim>.strikes``).
"""
from __future__ import annotations

import math
import sys
from dataclasses import dataclass, replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from pixel_kit import (Canvas, bayer, build_sheet, dissolve, flash, hash01, mix,  # noqa: E402
                       outline, ramp, save_sheet, smooth)

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "assets" / "enemies"
SHEET_ID = "mimic"

CELL_W, CELL_H = 152, 108
GROUND = 100
CX = CELL_W - 48                    # 104: footprint centre
ANCHOR = (CX, GROUND + 2)

# chest geometry (world units = native px): x to the right, d into the screen, h up
W, D = 48, 28                       # width (lock face) and depth
LEG, HB = 4, 32                     # feet height, box rim height
FLOOR = LEG + 3                     # inner floor of the mouth
LW, LR = 4.0, 11.0                  # lid front wall height, barrel dome rise
KX, KY = 0.5, 0.35                  # oblique projection of the depth axis
OX = CX - (W / 2 + D / 2 * KX)      # screen x of the front-left-bottom corner
OY = GROUND + 1
LIGHT = (-0.5, -0.45, 0.75)         # upper-left, towards the viewer
_ln = math.sqrt(sum(c * c for c in LIGHT))
LIGHT = tuple(c / _ln for c in LIGHT)

# ---------------------------------------------------------------- palette
OUTLINE = (22, 9, 14)
WOOD = [(30, 14, 20), (54, 26, 26), (82, 42, 32), (112, 62, 40), (144, 88, 52), (178, 120, 70),
        (210, 158, 100)]
IRON = [(22, 20, 32), (44, 42, 58), (74, 72, 90), (114, 112, 126), (164, 162, 170)]
GOLD = [(78, 42, 16), (130, 82, 22), (188, 132, 36), (234, 188, 72), (255, 238, 156)]
FLESH = [(26, 6, 16), (52, 10, 26), (86, 18, 36), (124, 30, 48), (164, 52, 62)]
TONGUE = [(58, 14, 42), (100, 26, 62), (146, 42, 82), (192, 72, 104), (232, 124, 142)]
TEETH = [(96, 82, 70), (160, 148, 122), (214, 204, 172), (248, 242, 220)]
EYE = [(56, 84, 18), (130, 196, 40), (206, 250, 92), (250, 255, 206)]
DROOL = [(150, 120, 150), (206, 186, 206), (244, 236, 246)]
SPIT = [(196, 160, 180), (240, 222, 232)]
WHITE = (255, 255, 255)

GROUND_COINS = [(-38, 0, 0), (-33, 1, 1), (35, 0, 2)]           # (dx from CX, dy, seed)
INNER_COINS = [(6, 15, 0.5), (10, 20, 0.6), (7, 23, 1.6), (39, 13, 0.5), (42, 19, 1.0),
               (36, 22, 0.5), (15, 9, 0.5), (31, 8, 0.6)]
BANDS = (5.0, W - 8.0)              # x of the two iron bands (3 wide)


@dataclass(frozen=True)
class Pose:
    dx: float = 0.0
    dy: float = 0.0
    sx: float = 1.0                 # squash/stretch about the footprint centre
    sy: float = 1.0
    lean: float = 0.0               # shift of the top (px at h=50), negative = towards the hero
    lid: float = 6.0                # lid angle in degrees (0 shut .. 120 flopped open)
    phase: float = 0.0
    eye: float = 1.0                # eye glow (0 hidden)
    tongue: float = 0.0             # tongue extension 0..1 (1 = ~62 px out)
    t_arc: float = 0.0              # bulge of the tongue curve (world h)
    t_dh: float = 0.0               # tip height offset
    swipe: float = 0.0              # whip trail strength
    t_arc0: float = 0.0             # where the lash came from (trail)
    t_dh0: float = 0.0
    crack: float = 0.0              # whip-crack spark at the tip
    drool: float = 0.0
    flash: float = 0.0
    dissolve: float = 0.0
    burst: float = 0.0              # chomp splinters + spit (0 none .. 1 gone)
    coins: float = 0.0              # hurt: coins flying out
    scatter: float = 0.0            # death: coins bursting and rolling away
    broken: float = 0.0             # death: the chest falls apart
    sparkle: float = 0.0            # cast: glint on the lock + sheen over the chest
    glint: float = 0.0              # a coin twinkles
    dust: float = 0.0               # landing dust puffs


def _clamp(v: float) -> float:
    return 0.0 if v < 0 else 1.0 if v > 1 else v


def tone(colors, light, x, y, dither=0.55):
    return ramp(colors, _clamp(light), x, y, dither)


def lam(n) -> float:
    return max(0.0, n[0] * LIGHT[0] + n[1] * LIGHT[1] + n[2] * LIGHT[2])


def grain(a: float, b: float, seed: float) -> float:
    g = math.sin(a * 0.5 + 2.2 * math.sin(a * 0.08 + seed) + b * 1.6 + seed * 3)
    if g > 0.74:
        return -0.13
    if g < -0.88:
        return 0.07
    return 0.0


# ---------------------------------------------------------------- rig: world -> screen
class Rig:
    def __init__(self, p: Pose) -> None:
        self.p = p
        th = math.radians(max(-5.0, min(130.0, p.lid)))
        self.c, self.s = math.cos(th), math.sin(th)
        self.lift = D * self.s                     # height of the lid's front edge above the rim
        self.k = _clamp(p.broken)
        self.shadow = 0.45 * (1 - smooth(self.lift / 12.0))     # teeth in the dark of a narrow gap

    def lid_pt(self, x, dl, hl):
        """Lid-local (x, d' from the front, h' above the rim) -> box world (hinge at the back)."""
        a, b = dl - D, hl
        return x, D + a * self.c + b * self.s, HB - a * self.s + b * self.c

    def lid_n(self, n):
        return n[0], n[1] * self.c + n[2] * self.s, -n[1] * self.s + n[2] * self.c

    def broken_pt(self, piece, x, d, h):
        k = self.k
        if piece.startswith("plank"):
            i = int(piece[5:])
            ki = _clamp(k * 1.35 - 0.12 * (3 - i))          # the top plank goes first
            h0 = LEG + 7 * i
            phi = ki * (1.2 + 0.1 * i)
            hr = h - h0
            spread = (i - 1.5) * 4 + (3 if i % 2 else -3)
            return (x + (spread - 7) * ki + hr * 0.15 * ki * (1 if i % 2 else -1),
                    d - hr * math.sin(phi) - 3 * ki * (3 - i), h0 * (1 - ki) + hr * math.cos(phi))
        if piece == "end":
            phi = 1.45 * k
            hr = h - LEG
            return x + hr * math.sin(phi) + 7 * k, d + 2 * k, LEG * (1 - k) + hr * math.cos(phi)
        if piece == "lid":
            return x + 12 * k, d + 8 * k, HB * (1 - 0.85 * k) + (h - HB) * (1 - 0.6 * k)
        if piece == "inner":
            return x - 3 * k, d, h * (1 - 0.8 * k)
        return x, d, h

    def world(self, piece, x, d, h):
        if piece == "lid":
            x, d, h = self.lid_pt(x, d, h)
        if self.k > 0:
            x, d, h = self.broken_pt(piece, x, d, h)
        p = self.p
        x += p.lean * h / 50.0
        x = W / 2 + (x - W / 2) * p.sx
        d = D / 2 + (d - D / 2) * p.sx
        return x, d, h * p.sy

    def scr(self, x, d, h):
        return OX + self.p.dx + x + d * KX, OY + self.p.dy - h - d * KY

    def at(self, piece, x, d, h):
        """Screen x, y and depth of a point."""
        wx, wd, wh = self.world(piece, x, d, h)
        sx, sy = self.scr(wx, wd, wh)
        return sx, sy, wd


class Scene:
    def __init__(self) -> None:
        self.cv = Canvas(CELL_W, CELL_H)
        self.z = [[1e9] * CELL_W for _ in range(CELL_H)]

    def put(self, ix, iy, z, c, solid=True):
        ix, iy = int(ix), int(iy)
        if 0 <= ix < CELL_W and 0 <= iy < CELL_H and z < self.z[iy][ix]:
            self.z[iy][ix] = z
            self.cv.px[iy][ix] = (*c[:3], 255)
            self.cv.solid[iy][ix] = solid


VIEW = (0.5, -1.0, 0.35)            # towards the viewer: faces with n.VIEW > 0 are seen


def facing(n) -> bool:
    return n[0] * VIEW[0] + n[1] * VIEW[1] + n[2] * VIEW[2] > 0.02


def quad(sc: Scene, rig: Rig, piece, o, eu, ev, shade) -> None:
    """Rasterise the parallelogram o + u*eu + v*ev (u, v in 0..1) with a depth test."""
    p0 = rig.at(piece, *o)
    pu = rig.at(piece, o[0] + eu[0], o[1] + eu[1], o[2] + eu[2])
    pv = rig.at(piece, o[0] + ev[0], o[1] + ev[1], o[2] + ev[2])
    ax, ay = pu[0] - p0[0], pu[1] - p0[1]
    bx, by = pv[0] - p0[0], pv[1] - p0[1]
    det = ax * by - ay * bx
    if abs(det) < 0.05:
        return
    xs = (p0[0], pu[0], pv[0], pu[0] + bx)
    ys = (p0[1], pu[1], pv[1], pu[1] + by)
    zu, zv = pu[2] - p0[2], pv[2] - p0[2]
    zb, px = sc.z, sc.cv.px
    for iy in range(max(0, int(min(ys)) - 1), min(CELL_H, int(max(ys)) + 2)):
        qy = iy + 0.5 - p0[1]
        zrow = zb[iy]
        for ix in range(max(0, int(min(xs)) - 1), min(CELL_W, int(max(xs)) + 2)):
            qx = ix + 0.5 - p0[0]
            u = (qx * by - qy * bx) / det
            if u < -0.001 or u > 1.001:
                continue
            v = (ax * qy - ay * qx) / det
            if v < -0.001 or v > 1.001:
                continue
            z = p0[2] + u * zu + v * zv
            if z >= zrow[ix]:
                continue
            c = shade(ix, iy, u, v)
            if c is None:
                continue
            zrow[ix] = z
            px[iy][ix] = (*c[:3], 255)
            sc.cv.solid[iy][ix] = True


# ---------------------------------------------------------------- materials
def iron_band(ix, iy, bx, light, rivet):
    """bx 0..1 across a band (left edge lit)."""
    if rivet:
        return IRON[4]
    lv = light + 0.2 * (1 - bx) - 0.05
    if bx > 0.8:
        lv -= 0.3
    return tone(IRON, lv, ix, iy, 0.4)


def wood_px(ix, iy, light, a, b, seed, plank_h=7.0):
    """Plank wood: ``a`` along the plank, ``b`` 0..plank_h across (0 = lower edge)."""
    lv = light + grain(a, b, seed)
    if b > plank_h - 0.9:
        lv += 0.12
    elif b < 0.9:
        lv -= 0.24
    # a knot here and there
    kx = 9 + 29 * hash01(int(seed * 7), 1, 11)
    if abs(a - kx) < 2.2 and abs(b - plank_h / 2) < 1.6 and hash01(int(seed * 7), 2, 11) > 0.45:
        lv -= 0.18 if abs(a - kx) < 1.0 else 0.08
    return tone(WOOD, lv, ix, iy)


def gold_plate(ix, iy, gx, gy, glow):
    """Lock plate: gx 0..1 left->right, gy 0..1 bottom->top."""
    if gx < 0.13 or gy > 0.87:
        c = GOLD[3]
    elif gx > 0.87 or gy < 0.13:
        c = GOLD[1]
    else:
        c = tone(GOLD, 0.55 - 0.25 * (gx - 0.5) + 0.2 * (gy - 0.5) + 0.3 * glow, ix, iy, 0.45)
    if (gx < 0.2 or gx > 0.8) and (gy < 0.2 or gy > 0.8):
        c = GOLD[4] if gx < 0.5 and gy > 0.5 else GOLD[2]
    return c


# ---------------------------------------------------------------- the box
def draw_feet(sc, rig):
    for x0, d0 in ((2, D - 8), (W - 9, D - 8), (2, 1), (W - 9, 1)):
        def front(ix, iy, u, v):
            if v < 0.4 and (u * 3) % 1.0 < 0.55:
                return TEETH[2] if (u * 3) % 1.0 < 0.25 else TEETH[1]
            return tone(WOOD, 0.35 + 0.25 * v - 0.2 * u, ix, iy)

        def side(ix, iy, u, v):
            if v < 0.4 and (u * 2) % 1.0 < 0.5:
                return TEETH[0]
            return tone(WOOD, 0.15 + 0.15 * v, ix, iy)
        quad(sc, rig, "feet", (x0, d0, 0), (7, 0, 0), (0, 0, LEG + 0.5), front)
        quad(sc, rig, "feet", (x0 + 7, d0, 0), (0, 7, 0), (0, 0, LEG + 0.5), side)


def draw_front(sc, rig, p):
    base = 0.22 + 0.62 * lam((0, -1, 0))
    for i in range(4):
        def shade(ix, iy, u, v, i=i):
            x, hh = u * W, v * 7
            h = LEG + 7 * i + hh
            if abs(x - W / 2) <= 4.6 and HB - 10.5 <= h <= HB - 1.5:          # lock plate
                if math.hypot(x - W / 2, h - (HB - 5.2)) < 1.3 or (abs(x - W / 2) < 0.6 and HB - 8.4 < h < HB - 5.2):
                    return (26, 10, 8)
                return gold_plate(ix, iy, (x - W / 2 + 4.6) / 9.2, (h - HB + 10.5) / 9.0, p.sparkle)
            if x < 2.2 or x > W - 2.2:                                     # corner irons
                rv = (abs(hh - 3.5) < 0.7) and abs(x - (1.1 if x < 2.2 else W - 1.1)) < 0.6
                return iron_band(ix, iy, (x if x < 2.2 else x - (W - 2.2)) / 2.2, base, rv)
            if i == 3 and hh > 5.0:                                        # rim band
                return iron_band(ix, iy, 0.3, base + 0.1 * (hh - 5), False)
            for b0 in BANDS:
                if b0 <= x <= b0 + 3:
                    rv = abs(x - b0 - 1.4) < 0.7 and abs(hh - 3.3) < 0.7
                    return iron_band(ix, iy, (x - b0) / 3, base, rv)
            return wood_px(ix, iy, base - 0.22 * (1 - h / HB), x, hh, 1.3 + i)
        quad(sc, rig, f"plank{i}", (0, 0, LEG + 7 * i), (W, 0, 0), (0, 0, 7), shade)


def draw_end(sc, rig):
    base = 0.32

    def shade(ix, iy, u, v):
        d, h = u * D, LEG + v * (HB - LEG)
        hh = (h - LEG) % 7
        if d < 1.6:
            return IRON[2] if d < 0.8 else IRON[1]
        if h > HB - 2:
            return iron_band(ix, iy, 0.5, base, False)
        if abs(d - D / 2) < 1.5:
            rv = abs(d - D / 2) < 0.6 and abs(hh - 3.5) < 0.6
            return iron_band(ix, iy, (d - D / 2 + 1.5) / 3, base - 0.05, rv)
        return wood_px(ix, iy, base - 0.15 * (1 - v) - 0.08 * u, d, hh, 5.7 + int((h - LEG) / 7))
    quad(sc, rig, "end", (W, 0, LEG), (0, D, 0), (0, 0, HB - LEG), shade)


def draw_rims(sc, rig):
    def top(ix, iy, u, v):
        return tone(WOOD, 0.62 - 0.2 * u, ix, iy)

    def front_rim(ix, iy, u, v):
        return tone(IRON, 0.7 - 0.25 * u, ix, iy, 0.4)
    quad(sc, rig, "plank3", (0, 0, HB), (W, 0, 0), (0, 2, 0), front_rim)
    quad(sc, rig, "inner", (0, 0, HB), (2, 0, 0), (0, D, 0), top)
    quad(sc, rig, "end", (W - 2, 0, HB), (2, 0, 0), (0, D, 0), top)
    quad(sc, rig, "inner", (0, D - 2, HB), (W, 0, 0), (0, 2, 0), top)


def draw_mouth(sc, rig, p):
    """Inside of the box: floor, back and left walls in dark flesh, a throat."""
    def floor(ix, iy, u, v):
        lv = 0.42 - 0.3 * v + 0.08 * math.sin(u * 17 + v * 5)
        return tone(FLESH, lv, ix, iy)

    def back(ix, iy, u, v):
        lv = 0.12 + 0.42 * v
        tx, ty = (u - 0.5) / 0.2, (v - 0.32) / 0.42
        if tx * tx + ty * ty < 1:
            return FLESH[0] if tx * tx + ty * ty < 0.55 else FLESH[1]
        if math.sin(u * 26) > 0.75:
            lv -= 0.12
        return tone(FLESH, lv, ix, iy)

    def left(ix, iy, u, v):
        return tone(FLESH, 0.2 + 0.4 * v + 0.15 * u, ix, iy)
    quad(sc, rig, "inner", (2, 2, FLOOR), (W - 4, 0, 0), (0, D - 4, 0), floor)
    quad(sc, rig, "inner", (2, D - 2, FLOOR), (W - 4, 0, 0), (0, 0, HB - FLOOR), back)
    quad(sc, rig, "inner", (2, 2, FLOOR), (0, D - 4, 0), (0, 0, HB - FLOOR), left)


def tooth_shade(hk, down, shadow=0.0):
    """A pointed tooth on a quad: u across, v along (0 = base for up teeth)."""
    def shade(ix, iy, u, v):
        t = v if not down else 1 - v                       # 0 at the gum .. 1 at the tip
        if t * (hk + 1) < 1:                               # gum strip
            return FLESH[3] if u < 0.5 else FLESH[2]
        tip = (t * (hk + 1) - 1) / hk
        if abs(u - 0.5) * 2 > 1 - tip:
            return None
        lv = 0.78 - 0.5 * (u - 0.5) * 2 - 0.25 * (1 - tip) + 0.1 * tip - shadow
        if (u - 0.5) * 2 > 0.55 * (1 - tip):
            lv -= 0.3
        if lv < 0.12:
            return FLESH[1] if lv < 0 else TEETH[0]
        return tone(TEETH, lv, ix, iy, 0.4)
    return shade


def draw_box_teeth(sc, rig):
    for k in range(9):
        xk = 3.2 + k * 5.2
        hk = 3.2 + 2.6 * hash01(k, 3, 21)
        quad(sc, rig, "plank3", (xk - 2.0, 1.0, HB - 1), (4.0, 0, 0), (0, 0, hk + 1), tooth_shade(hk, False, rig.shadow))
    for k in range(4):
        dk = 5 + k * 5.0
        hk = 2.6 + 2.0 * hash01(k, 5, 21)
        quad(sc, rig, "inner", (1.2, dk - 2.2, HB - 1), (0, 4.4, 0), (0, 0, hk + 1), tooth_shade(hk, False))


# ---------------------------------------------------------------- the lid
NS = 10


def dome(s: float):
    return D / 2 * (1 - math.cos(math.pi * s)), LW + LR * math.sin(math.pi * s)


def dome_n(s: float):
    nd, nh = -math.cos(math.pi * s) / (D / 2), math.sin(math.pi * s) / LR
    m = math.hypot(nd, nh)
    return 0.0, nd / m, nh / m


def draw_lid(sc, rig, p):
    # outer dome in strips
    for j in range(NS):
        s0, s1 = j / NS, (j + 1) / NS
        d0, h0 = dome(s0)
        d1, h1 = dome(s1)
        if not facing(rig.lid_n(dome_n(s0))) and not facing(rig.lid_n(dome_n(s1))):
            continue

        def shade(ix, iy, u, v, s0=s0, s1=s1):
            s = s0 + v * (s1 - s0)
            x = u * W
            n = rig.lid_n(dome_n(s))
            light = 0.2 + 0.68 * lam(n)
            bk = (s * 5) % 1.0                    # five boards along the barrel
            if x < 2.0 or x > W - 2.0:
                return iron_band(ix, iy, x / 2 if x < 2 else (x - W + 2) / 2, light, False)
            for b0 in BANDS:
                if b0 <= x <= b0 + 3:
                    rv = abs(x - b0 - 1.4) < 0.7 and abs(bk - 0.5) < 0.09
                    return iron_band(ix, iy, (x - b0) / 3, light, rv)
            lv = light + grain(x, bk * 7, 3.1 + int(s * 5))
            if bk < 0.1:
                lv -= 0.22
            elif bk > 0.88:
                lv += 0.1
            return tone(WOOD, lv, ix, iy)
        quad(sc, rig, "lid", (0, d0, h0), (W, 0, 0), (0, d1 - d0, h1 - h0), shade)

    # front wall of the lid (with an iron lip at the bottom)
    nf = rig.lid_n((0, -1, 0))
    if facing(nf):
        base = 0.22 + 0.62 * lam(nf)

        def front(ix, iy, u, v):
            x, hl = u * W, v * LW
            if x < 2.0 or x > W - 2.0:
                return iron_band(ix, iy, x / 2 if x < 2 else (x - W + 2) / 2, base, False)
            if hl < 1.5:
                return iron_band(ix, iy, 0.2 + 0.4 * (1 - hl / 1.5), base, abs((x % 6) - 3) < 0.5)
            for b0 in BANDS:
                if b0 <= x <= b0 + 3:
                    return iron_band(ix, iy, (x - b0) / 3, base, False)
            return wood_px(ix, iy, base, x, hl, 2.4, LW)
        quad(sc, rig, "lid", (0, 0, 0), (W, 0, 0), (0, 0, LW), front)
        # gold hasp hanging over the lock
        def hasp(ix, iy, u, v):
            if v < 0.25 and abs(u - 0.5) > 0.3:
                return None
            return gold_plate(ix, iy, u, v, p.sparkle)
        quad(sc, rig, "lid", (W / 2 - 2.6, -0.4, -3.2), (5.2, 0, 0), (0, 0, 6.2), hasp)

    # right end cap
    def cap(ix, iy, u, v):
        dl, hl = u * D, v * (LW + LR)
        top = LW + LR * math.sin(math.pi * u)
        if hl > top:
            return None
        if hl > top - 1.4 or hl < 1.3 or dl < 1.3:
            return IRON[2] if hl > top - 0.7 else IRON[1]
        return wood_px(ix, iy, 0.3 - 0.1 * u, dl, hl % 5, 7.3, 5)
    quad(sc, rig, "lid", (W, 0, 0), (0, D, 0), (0, 0, LW + LR), cap)

    # underside (the upper jaw), only when the lid is open enough to face us
    if facing(rig.lid_n((0, 0, -1))):
        def under(ix, iy, u, v):
            x, dl = u * W, v * D
            if x < 2 or x > W - 2 or dl < 1.5 or dl > D - 2:
                return tone(WOOD, 0.3, ix, iy)
            lv = 0.48 - 0.32 * v
            if math.sin(dl * 1.35) > 0.55:
                lv += 0.12
            if abs(x - W / 2) < 0.7:
                lv -= 0.15
            return tone(FLESH, lv, ix, iy)
        quad(sc, rig, "lid", (0, 0, -0.01), (W, 0, 0), (0, D, 0), under)
    # upper teeth (hang from the lid's front and left edges)
    for k in range(9):
        xk = 5.8 + k * 5.2
        hk = 3.6 + 2.8 * hash01(k, 7, 21)
        if xk + 2.3 > W - 1:
            continue
        quad(sc, rig, "lid", (xk - 2.0, 1.2 + 0.55 * hk, -hk), (4.0, 0, 0), (0, -0.55 * (hk + 1), hk + 1),
             tooth_shade(hk, True, rig.shadow))
    for k in range(4):
        dk = 6.5 + k * 5.0
        hk = 2.8 + 2.0 * hash01(k, 9, 21)
        quad(sc, rig, "lid", (1.2, dk - 2.2, -hk), (0, 4.4, 0), (0, 0, hk + 1), tooth_shade(hk, True))


# ---------------------------------------------------------------- tongue
def tongue_points(rig, p, ext=None, arc=None, dh=None):
    ext = p.tongue if ext is None else ext
    arc = p.t_arc if arc is None else arc
    dh = p.t_dh if dh is None else dh
    b = (W * 0.56, D * 0.62, FLOOR + 1.5)
    if ext < 0.02:
        ctrl = [(b, 3.0), ((W * 0.4, D * 0.36, FLOOR + 2.2), 2.8), ((W * 0.28, D * 0.24, FLOOR + 1.8), 2.2)]
        pts = []
        for (a, ra), (c, rc) in zip(ctrl, ctrl[1:]):
            for i in range(8):
                t = i / 8
                pts.append((tuple(a[j] + (c[j] - a[j]) * t for j in range(3)), ra + (rc - ra) * t))
        pts.append(ctrl[-1])
        return pts
    eh = HB + min(2.6, 0.5 * rig.lift) + 0.6
    m = (W * 0.42, 3.0, HB - 2.0)
    e = (W * 0.36, -1.2, eh)
    tip = (e[0] - 62 * ext, e[1] - 2.0, eh + dh)
    c = ((e[0] + tip[0]) / 2, e[1] - 1.0, (e[2] + tip[2]) / 2 + arc)
    pts = []
    for (a, ra), (q, rq) in (((b, 3.4), (m, 3.2)), ((m, 3.2), (e, 3.1))):
        for i in range(8):
            t = i / 8
            pts.append((tuple(a[j] + (q[j] - a[j]) * t for j in range(3)), ra + (rq - ra) * t))
    n = max(4, int(abs(tip[0] - e[0]) * 1.2 + abs(dh) + abs(arc)))
    for i in range(n + 1):
        t = i / n
        pt = tuple((1 - t) ** 2 * e[j] + 2 * (1 - t) * t * c[j] + t * t * tip[j] for j in range(3))
        r = 3.1 - 1.6 * t + 0.5 * max(0.0, t - 0.85) / 0.15
        pts.append((pt, r))
    return pts


def draw_tongue(sc, rig, p):
    pts = []
    for (x, d, h), r in tongue_points(rig, p):
        sx, sy, z = rig.at("inner", x, d, h)
        pts.append((sx, sy, z, r))
    dense = [pts[0]]
    for a, b in zip(pts, pts[1:]):
        n = max(1, int(math.hypot(b[0] - a[0], b[1] - a[1]) / 0.5))
        for i in range(1, n + 1):
            t = i / n
            dense.append(tuple(a[j] + (b[j] - a[j]) * t for j in range(4)))
    best = {}
    total = len(dense)
    for k, (x, y, z, r) in enumerate(dense):
        nxt = dense[min(total - 1, k + 1)]
        prv = dense[max(0, k - 1)]
        tx, ty = nxt[0] - prv[0], nxt[1] - prv[1]
        tl = math.hypot(tx, ty) or 1.0
        tx, ty = tx / tl, ty / tl
        for yy in range(int(y - r) - 1, int(y + r) + 2):
            for xx in range(int(x - r) - 1, int(x + r) + 2):
                ddx, ddy = xx + 0.5 - x, yy + 0.5 - y
                dist = math.hypot(ddx, ddy) / r
                if dist > 1:
                    continue
                key = (xx, yy)
                if key not in best or dist < best[key][0]:
                    perp = (ddx * -ty + ddy * tx) / r
                    side = (ddx * -0.7 + ddy * -0.7) / r
                    best[key] = (dist, side, perp, k / total, z - 0.6 * r * (1 - dist))
    for (xx, yy), (dist, side, perp, t, z) in best.items():
        lv = 0.55 + 0.45 * side - 0.25 * dist * dist
        if 0.1 < t < 0.93 and -0.12 < perp < 0.22 and dist < 0.4:
            lv -= 0.28                                     # the groove down the middle
        if t > 0.94:
            lv += 0.12
        sc.put(xx, yy, z, tone(TONGUE, lv, xx, yy, 0.5))


def draw_tongue_trail(cv, rig, p):
    """Ghost arcs between the previous and current lash (motion smear)."""
    if p.swipe <= 0 or p.tongue < 0.3:
        return
    for j in range(1, 5):
        f = j / 5
        pts = tongue_points(rig, p, p.tongue, p.t_arc0 + (p.t_arc - p.t_arc0) * f,
                            p.t_dh0 + (p.t_dh - p.t_dh0) * f)
        tail = pts[len(pts) // 2 + 6:]
        for (x, d, h), _ in tail[::1]:
            sx, sy, _ = rig.at("inner", x, d, h)
            if bayer(int(sx), int(sy)) < 0.35 + 0.5 * f:
                cv.put(sx, sy, TONGUE[4] if j > 2 else TONGUE[3], solid=False,
                       alpha=int((60 + 35 * j) * p.swipe))


# ---------------------------------------------------------------- details
def draw_eyes(sc, rig, p):
    if p.eye <= 0.05:
        return []
    out = []
    hot = EYE[3] if p.eye > 0.7 else EYE[2]
    warm = EYE[2] if p.eye > 0.5 else EYE[1]
    deep = 1.7 + 7.0 * smooth(rig.lift / 22.0)
    for xe, side in ((W * 0.34, -1), (W * 0.6, 1)):
        sx, sy, z = rig.at("lid", xe, deep, -1.9)
        ex, ey = int(sx), int(sy)
        # slanted, the inner end lower (hungry/angry); a dark slit pupil
        cells = [(-3, -1, warm), (-2, -1, hot), (-1, -1, hot), (0, -1, hot),
                 (-2, 0, warm), (-1, 0, hot), (0, 0, (20, 30, 6)), (1, 0, hot), (2, 0, warm),
                 (0, 1, warm), (1, 1, warm), (-1, 1, EYE[1])]
        if p.eye > 1.2:
            cells += [(-4, -2, EYE[1]), (3, 0, EYE[1])]
        for ox, oy, c in cells:
            sc.put(ex + ox * -side, ey + oy, z - 0.7, c)
        out.append((ex + 0.5, ey))
    return out


def coin_px(put, x, y, seed, z=None, spin=0, glint=0.0, rim=False):
    """A small gold coin: 4x2 face-on or edge-on 2x2 while spinning (``rim``: dark edge)."""
    x, y = int(x), int(y)
    if spin % 3 == 1:
        cells = [(0, 0, GOLD[3]), (1, 0, GOLD[2]), (0, 1, GOLD[2]), (1, 1, GOLD[1])]
    elif spin % 3 == 2:
        cells = [(0, 0, GOLD[4]), (0, 1, GOLD[2]), (0, 2, GOLD[1])]
    else:
        cells = [(0, 0, GOLD[3]), (1, 0, GOLD[4]), (2, 0, GOLD[3]), (3, 0, GOLD[2]),
                 (0, 1, GOLD[2]), (1, 1, GOLD[2]), (2, 1, GOLD[1]), (3, 1, GOLD[1])]
    if rim:
        own = {(ox, oy) for ox, oy, _ in cells}
        for ox, oy, _ in cells:
            for ax, ay in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                if (ox + ax, oy + ay) not in own:
                    put(x + ox + ax, y + oy + ay, OUTLINE)
    for ox, oy, c in cells:
        put(x + ox, y + oy, c)


def draw_inner_coins(sc, rig):
    for i, (x, d, h) in enumerate(INNER_COINS):
        sx, sy, z = rig.at("inner", x, d, h)
        coin_px(lambda a, b, c: sc.put(a, b, z - 0.3, c), sx, sy, i)


def draw_ground_coins(cv, p):
    for gx, gy, s in GROUND_COINS:
        x, y = CX + gx, GROUND - 1 + gy
        if p.scatter > 0:
            ang = (hash01(s, 1, 4) - 0.5) * 2
            x += ang * 14 * smooth(p.scatter)
        coin_px(lambda a, b, c: cv.put(a, b, c), x, y, s)
    if p.glint > 0.05:
        gx, gy, _ = GROUND_COINS[1]
        star(cv, CX + gx + 1, GROUND + gy - 1, p.glint)


def star(cv, x, y, k, color=WHITE):
    x, y = int(x), int(y)
    arm = 1 + int(round(3 * k))
    cv.put(x, y, color, solid=False)
    for a in range(1, arm + 1):
        col = color if a < arm else GOLD[3]
        for ox, oy in ((a, 0), (-a, 0), (0, a), (0, -a)):
            cv.put(x + ox, y + oy, col, solid=False, alpha=int(255 * min(1.0, k + 0.2)))
    if k > 0.5:
        for ox, oy in ((1, 1), (-1, -1), (1, -1), (-1, 1)):
            cv.put(x + ox, y + oy, GOLD[4], solid=False, alpha=150)


def draw_inside_glint(sc, rig, p):
    """A coin stuck between the front teeth -- the bait."""
    sx, sy, z = rig.at("plank3", W * 0.8, 0.6, HB + 1.2)
    coin_px(lambda a, b, c: sc.put(a, b, z - 0.4, c), sx, sy, 7, spin=1)


def draw_drool(cv, rig, p):
    if p.drool <= 0 or rig.lift < 6:
        return
    for k, (xf, ln) in enumerate(((0.24, 0.45), (0.55, 1.0), (0.8, 0.3))):
        x = W * xf
        tx, ty, _ = rig.at("lid", x, 1.2, -3.0)
        bx, by, _ = rig.at("plank3", x + 1, 0.5, HB + 1.5)
        frac = min(1.0, p.drool * ln)
        span = abs(by - ty)
        n = max(2, int(span * frac))
        sag = 2.5 if ln == 1.0 else 0.6
        for i in range(n):
            t = i / max(1.0, span)
            px = tx + (bx - tx) * t + sag * math.sin(t * math.pi) * (1 if k % 2 else -1)
            py = ty + (by - ty) * t
            cv.put(px, py, DROOL[1] if i % 4 else DROOL[2], solid=False, alpha=170)
        if frac < 1:                                       # a drop forming at the end
            cv.put(px, py + 1, DROOL[2], solid=False, alpha=220)
            cv.put(px, py + 2, DROOL[1], solid=False, alpha=150)
    # drips running down the front planks
    for k, xf in enumerate((0.3, 0.64)):
        x0, y0, _ = rig.at("plank3", W * xf, -0.2, HB - 0.5)
        ln = int(5 * p.drool * (0.6 + 0.6 * hash01(k, 2, 31)))
        for i in range(ln):
            cv.put(x0, y0 + i, DROOL[0] if i < ln - 1 else DROOL[2], solid=False, alpha=200)


def draw_burst(cv, rig, p):
    """Chomp: wood splinters and spit spraying out of the slammed mouth."""
    k = p.burst
    if k <= 0 or k >= 1:
        return
    cx, cy, _ = rig.at("plank3", W * 0.15, -1, HB + 1)
    fade = 1 - max(0.0, k - 0.55) / 0.45
    for i in range(16):
        ang = math.pi * (0.55 + 0.9 * hash01(i, 1, 41)) + (0.5 if i % 3 == 0 else 0)
        dist = 4 + (18 + 18 * hash01(i, 2, 41)) * smooth(k * 1.3)
        x = cx + math.cos(ang) * dist
        y = cy - math.sin(ang) * dist * 0.8 + 18 * k * k
        dx, dy = math.cos(ang), -math.sin(ang)
        for s in range(2 + (i % 2)):
            col = WOOD[5] if s == 0 else WOOD[3]
            cv.put(x - dx * s, y - dy * s, col, solid=False, alpha=int(255 * fade))
    for i in range(16):
        ang = math.pi * (0.4 + 1.2 * hash01(i, 3, 41))
        dist = 4 + (10 + 22 * hash01(i, 4, 41)) * smooth(k * 1.2)
        x = cx - 4 + math.cos(ang) * dist * 1.2
        y = cy - math.sin(ang) * dist * 0.7 + 14 * k * k
        cv.put(x, y, SPIT[i % 2], solid=False, alpha=int(230 * fade))
    if k < 0.45:                                           # impact lines
        for i in range(6):
            ang = math.pi * (0.6 + 0.8 * i / 5)
            for s in range(3):
                r = 9 + 6 * k * 2 + s
                cv.put(cx - 6 + math.cos(ang) * r, cy - math.sin(ang) * r * 0.8, WHITE, solid=False,
                       alpha=int(255 * (1 - k * 2)))


def draw_flying_coins(cv, rig, p):
    k = p.coins
    if k <= 0 or k >= 1:
        return
    cx, cy, _ = rig.at("plank3", W * 0.45, 0, HB + 3)
    for i in range(8):
        vx = (-1 if i % 2 else 1) * (14 + 34 * hash01(i, 1, 51)) + 8
        vy = 62 + 26 * hash01(i, 2, 51)
        x = cx + vx * k
        y = cy - vy * k + 78 * k * k
        if y > GROUND - 2:
            continue
        coin_px(lambda a, b, c: cv.put(a, b, c, solid=False), x, y, i, spin=int(k * 9 + i), rim=True)


def draw_scatter(cv, rig, p):
    k = p.scatter
    if k <= 0:
        return
    cx, cy = CX - 8, GROUND - 30
    for i in range(12):
        vx = (hash01(i, 1, 61) - 0.45) * 70
        up = 20 + 22 * hash01(i, 2, 61)
        land = GROUND - 1 + int(2 * hash01(i, 3, 61))
        t = min(1.0, k * (1.4 + 0.4 * hash01(i, 4, 61)))
        x = cx + vx * t
        y = cy - up * t + (up + land - cy) * t * t
        y = min(y, land)
        coin_px(lambda a, b, c: cv.put(a, b, c), x, y, i, spin=0 if t >= 1 else int(t * 9 + i), rim=t < 1)


def draw_dust(cv, p):
    k = p.dust
    if k <= 0 or k >= 1:
        return
    fx = CX + p.dx
    for side in (-1, 1):
        for i in range(4):
            r = 2 + 9 * k + i * 2
            x = fx + side * (26 + r)
            y = GROUND - 1 - (i % 2) - 2 * k
            cv.put(x, y, WOOD[4] if i % 2 else WOOD[5], solid=False, alpha=int(200 * (1 - k)))


def draw_crack(cv, rig, p):
    if p.crack <= 0:
        return
    (x, d, h), _ = tongue_points(rig, p)[-1]
    sx, sy, _ = rig.at("inner", x, d, h)
    star(cv, sx - 2, sy, p.crack, SPIT[1])
    for i in range(5):
        ang = math.tau * i / 5 + 0.3
        r = 4 + 3 * p.crack
        cv.put(sx - 2 + math.cos(ang) * r, sy + math.sin(ang) * r, TONGUE[4], solid=False, alpha=200)


def depth_edges(sc):
    """Dark line where a part passes in front of something much deeper."""
    cv, zb = sc.cv, sc.z
    dark = []
    for y in range(CELL_H):
        for x in range(CELL_W):
            if cv.px[y][x] is None:
                continue
            z = zb[y][x]
            for ox, oy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nx, ny = x + ox, y + oy
                if 0 <= nx < CELL_W and 0 <= ny < CELL_H and cv.px[ny][nx] is not None \
                        and zb[ny][nx] < z - 3.5:
                    dark.append((x, y))
                    break
    for x, y in dark:
        c = cv.px[y][x]
        cv.px[y][x] = (*mix(c[:3], OUTLINE, 0.7), c[3])


def sheen(cv, k):
    """Cast: a diagonal glint sweeping over the chest (innocent shine)."""
    if k <= 0 or k >= 1:
        return
    pos = 50 + k * 130
    for y in range(CELL_H):
        for x in range(CELL_W):
            c = cv.px[y][x]
            if c is None or not cv.solid[y][x]:
                continue
            dd = abs(x + y * 0.7 - pos)
            if dd < 2.5:
                cv.px[y][x] = (*mix(c[:3], GOLD[4], 0.45 if dd < 1.2 else 0.22), c[3])


# ---------------------------------------------------------------- render
def render(p: Pose, t: float = 0.0) -> Canvas:
    sc = Scene()
    rig = Rig(p)
    draw_feet(sc, rig)
    draw_front(sc, rig, p)
    draw_end(sc, rig)
    if p.lid > 0.5 or p.broken > 0:
        draw_rims(sc, rig)
        draw_mouth(sc, rig, p)
        draw_inner_coins(sc, rig)
        draw_tongue(sc, rig, p)
    elif p.tongue > 0.02:
        draw_tongue(sc, rig, p)
    draw_box_teeth(sc, rig)
    draw_inside_glint(sc, rig, p)
    draw_lid(sc, rig, p)
    eyes = draw_eyes(sc, rig, p) if p.broken < 0.5 else []
    depth_edges(sc)
    cv = sc.cv
    draw_ground_coins(cv, p)
    outline(cv, OUTLINE)
    for ex, ey in eyes:
        cv.glow(ex, ey, 4 + 2.5 * p.eye, EYE[1], 0.22 * min(1.5, p.eye) ** 1.5, halo=p.eye > 1.2)
    if p.sparkle > 0:
        lx, ly, _ = rig.at("plank3", W / 2 - 2.5, -0.5, HB - 2.5)
        cv.glow(lx, ly, 6 + 4 * p.sparkle, GOLD[3], 0.5 * p.sparkle)
        star(cv, lx, ly, min(1.0, p.sparkle * 1.2))
        sheen(cv, p.sparkle)
    draw_drool(cv, rig, p)
    draw_tongue_trail(cv, rig, p)
    draw_crack(cv, rig, p)
    draw_burst(cv, rig, p)
    draw_flying_coins(cv, rig, p)
    draw_scatter(cv, rig, p)
    draw_dust(cv, p)
    flash(cv, p.flash)
    if p.dissolve > 0:
        dissolve(cv, p.dissolve, GROUND - 64, GROUND + 3, GOLD[4], (196, 96, 54), upward=False)
    return cv


# ---------------------------------------------------------------- animations
IDLE_FRAMES = 12


def idle_pose(i: int, n: int = IDLE_FRAMES) -> Pose:
    a = math.tau * (i % n) / n
    breath = math.sin(a)
    return Pose(
        lid=8.0 + 3.0 * breath, sy=1.0 + 0.015 * breath, sx=1.0 - 0.01 * breath, phase=a,
        eye=0.85 + 0.3 * max(0.0, math.sin(a + 0.8)) ** 3,
        tongue=0.16 * max(0.0, math.sin(a - 1.4)) ** 6, t_dh=-3.5, t_arc=1.0,
        glint=max(0.0, math.sin(a + 2.2)) ** 10,
    )


def idle_frames():
    return [(idle_pose(i), 110) for i in range(IDLE_FRAMES)]


def attack_frames():
    """Mordisco Voraz: creak wide open, lunge left, SLAM shut on the hero, hop back."""
    b = idle_pose(0)
    return [
        (replace(b, lid=22, dx=2, lean=1, eye=1.15, sy=1.02), 100),
        (replace(b, lid=48, dx=3, lean=3, sy=1.05, sx=0.97, eye=1.3, drool=0.5), 110),
        (replace(b, lid=78, dx=3, lean=4, sy=1.06, sx=0.96, eye=1.5, drool=1.0, tongue=0.1,
                 t_dh=-6, t_arc=2), 130),
        (replace(b, lid=84, dx=-20, dy=-9, lean=-6, sy=1.08, sx=0.95, eye=1.5, drool=0.8,
                 tongue=0.06, t_dh=-3), 60),
        (replace(b, lid=0, dx=-40, dy=0, lean=-3, sx=1.12, sy=0.88, eye=0, burst=0.2), 60),
        (replace(b, lid=0, dx=-40, lean=-1, sx=1.05, sy=0.95, eye=0, burst=0.55, dust=0.3), 75),
        (replace(b, lid=10, dx=-25, dy=-7, sy=1.04, sx=0.97, burst=0.85), 80),
        (replace(b, lid=6, dx=-9, dy=-3, sy=1.02), 85),
        (replace(b, lid=5, dx=-2, sx=1.04, sy=0.96, dust=0.4), 90),
        (b, 110),
    ]


def lick_frames():
    """Lengüetazo: the lid opens and the tongue whips out three times."""
    b = idle_pose(0)
    o = dict(lid=58, eye=1.35, sy=1.03)
    return [
        (replace(b, lid=24, eye=1.1), 90),
        (replace(b, **o, tongue=0.12, t_dh=6, t_arc=4, drool=0.6, lean=1), 100),
        (replace(b, **o, tongue=0.35, t_dh=20, t_arc=10, drool=0.8, dx=2, lean=2), 90),
        (replace(b, **o, tongue=1.0, t_dh=-4, t_arc=12, swipe=1.0, t_arc0=26, t_dh0=24,
                 crack=1.0, dx=-3, lean=-3), 60),
        (replace(b, **o, tongue=0.55, t_dh=18, t_arc=-2, drool=0.6), 70),
        (replace(b, **o, tongue=1.0, t_dh=6, t_arc=-10, swipe=1.0, t_arc0=8, t_dh0=24,
                 crack=1.0, dx=-3, lean=-3), 60),
        (replace(b, **o, tongue=0.5, t_dh=24, t_arc=6, drool=0.5), 70),
        (replace(b, **o, tongue=1.0, t_dh=-2, t_arc=16, swipe=1.0, t_arc0=30, t_dh0=30,
                 crack=1.0, dx=-4, lean=-4), 60),
        (replace(b, **o, tongue=0.4, t_dh=-6, t_arc=2), 80),
        (replace(b, lid=26, tongue=0.1, t_dh=-3, eye=1.1), 90),
        (replace(b, lid=8, eye=1.0), 90),
        (b, 110),
    ]


def cast_frames():
    """Fingir: slams shut, plays a harmless chest, a glint runs over the lock."""
    b = idle_pose(0)
    return [
        (replace(b, lid=0, eye=0, sx=1.08, sy=0.9, dust=0.25), 70),
        (replace(b, lid=0, eye=0, sx=0.96, sy=1.05, dy=-2), 80),
        (replace(b, lid=0, eye=0, sparkle=0.25), 90),
        (replace(b, lid=0, eye=0, sparkle=0.5), 90),
        (replace(b, lid=0, eye=0, sparkle=0.75), 100),
        (replace(b, lid=0, eye=0, sparkle=0.95), 90),
        (replace(b, lid=2, eye=0.4), 90),
        (replace(b, lid=4.5, eye=0.8), 90),
        (b, 110),
    ]


def hurt_frames():
    b = idle_pose(0)
    return [
        (replace(b, lid=32, dx=4, sx=1.06, sy=0.92, flash=0.85, eye=0.3, coins=0.12), 55),
        (replace(b, lid=0, dx=6, sx=1.04, sy=0.95, flash=0.55, eye=0, coins=0.35), 60),
        (replace(b, lid=14, dx=5, sy=1.02, flash=0.25, eye=0.6, coins=0.6), 70),
        (replace(b, lid=4, dx=3, coins=0.85), 80),
        (replace(b, lid=7, dx=1), 90),
        (b, 100),
    ]


def death_frames():
    b = idle_pose(0)
    out = [
        (replace(b, lid=28, dx=3, sx=1.06, sy=0.92, flash=0.85, eye=0.4), 70),
        (replace(b, lid=72, dx=3, flash=0.35, eye=1.6, tongue=0.18, t_dh=-6, sy=1.04), 90),
        (replace(b, lid=112, dx=2, eye=0.8, tongue=0.3, t_dh=-20, t_arc=4), 100),
        (replace(b, lid=120, dx=2, eye=0.3, tongue=0.32, t_dh=-24, t_arc=3, sy=0.97), 100),
    ]
    steps = 7
    for k in range(steps):
        u = (k + 1) / steps
        out.append((replace(b, lid=120, dx=2, eye=0, tongue=0.32, t_dh=-24, t_arc=3,
                            broken=smooth(min(1.0, u * 1.3)), scatter=min(1.0, u * 1.2), burst=min(0.95, 0.15 + u * 0.8),
                            dissolve=0.0 if u < 0.3 else (u - 0.3) / 0.7 * 0.92), 90))
    out.append((replace(b, dissolve=1.0), 120))
    return out


ANIMATIONS = {
    "idle": (idle_frames, True),
    "attack": (attack_frames, False),
    "lick": (lick_frames, False),
    "cast": (cast_frames, False),
    "hurt": (hurt_frames, False),
    "death": (death_frames, False),
}

# Frames where a hit lands (attack: the jaws slam; lick: each lash).
EVENTS = {"attack": {"strikes": [4]}, "lick": {"strikes": [3, 5, 7]}}
MOVES = {"chomp": "attack", "lick": "lick", "feign": "cast", "vengeance": "cast"}


def build():
    return build_sheet(ANIMATIONS, render, (CELL_W, CELL_H), ANCHOR, f"{SHEET_ID}_sheet.png",
                       {"events": EVENTS, "moves": MOVES})


def main() -> None:
    sheet, meta = build()
    save_sheet(OUT_DIR, SHEET_ID, sheet, meta)
    print(f"wrote assets/enemies/{SHEET_ID}_sheet.png ({len(sheet[0])}x{len(sheet)}) and .json")


if __name__ == "__main__":
    main()
