"""Draw and animate the floor-1 boss "Caballero Hueco" (a haunted, empty suit of armour).

    python scripts/generate_boss_knight.py

Same method as the Espectro (``docs/code-drawn-sprites.md``): one renderer, every
frame a ``Pose``. The knight floats above the floor:

* a crowned great helm with a T-shaped visor burning with embers; a gap of
  darkness and ember light between helm and gorget shows he is hollow;
* cold steel plate (pauldrons with bronze trim, a breastplate with a ridge and a
  crack glowing from inside), faulds, and a crimson tabard torn into strands that
  fade into ash instead of legs;
* two floating gauntlets (no arms): the back one wields an executioner's
  greatsword, the front one commands his floating swords.

The floating swords ("Espadas") are NOT in this sheet: their number changes
during the fight, so ``knight_blade.png`` (16 rotations of one sword, also drawn
here) is drawn by the game around him, one per stack, and they fly at the hero
one by one during "Danza de Espadas".

Animations (non-death actions end on idle frame 0):
  idle    16-frame float: bob, tabard and plume wave, gauntlets lag, visor flicker
  attack  "Tajo del Verdugo": greatsword raised overhead, lunge, huge ember slash
  double  "Estocada Doble": two fast thrusts
  command "Danza de Espadas": the front gauntlet points at the hero, visor blazes
  cast    "Llamar al Acero" / "Furia Hueca": gauntlets rise, ember sigil on the floor
  hurt    white flash, knock-back, the helm jolts
  death   the helm drops, the armour collapses and crumbles into ash and embers
"""
from __future__ import annotations

import math
import sys
from dataclasses import dataclass, field, replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from pixel_kit import (Canvas, bayer, build_sheet, dissolve, flash, hash01, lerp, mix,  # noqa: E402
                       outline, ramp, save_sheet, smooth, write_png)

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "assets" / "enemies"
SHEET_ID = "knight"

CELL_W, CELL_H = 224, 124
CX, GROUND = 150, 114
ANCHOR = (CX, GROUND + 2)
FLOAT = 3                       # hover height of the lowest strands

# ---------------------------------------------------------------- palette
OUTLINE = (10, 8, 14)
STEEL = [(12, 13, 20), (24, 27, 38), (40, 45, 60), (62, 69, 88), (92, 100, 120), (134, 142, 160),
         (196, 202, 214)]
TRIM = [(70, 42, 22), (130, 86, 40), (196, 146, 72), (240, 204, 128)]
EMBER = [(80, 20, 8), (176, 58, 16), (255, 132, 40), (255, 214, 130), (255, 250, 220)]
CLOTH = [(20, 8, 12), (42, 12, 18), (72, 20, 28), (110, 32, 38), (150, 50, 50)]
ASH = [(36, 32, 36), (62, 56, 58), (92, 86, 84)]
VOID = (6, 4, 8)
WHITE = (255, 255, 255)

# heights above the ground (before squash)
H_CLOTH_TOP, H_FAULD, H_WAIST, H_CHEST, H_GORGET, H_HELM0, H_HELM1 = 36, 42, 49, 66, 71, 75, 93
STRANDS = 6


@dataclass(frozen=True)
class Pose:
    dx: float = 0.0
    dy: float = 0.0
    lean: float = 0.0               # helm/torso offset relative to the strands (neg = towards hero)
    sx: float = 1.0
    sy: float = 1.0
    phase: float = 0.0
    sway: float = 1.0
    helm_dy: float = 0.0            # helm lifted (+) / dropped (-) relative to the gorget
    helm_dx: float = 0.0
    hand_f: tuple[float, float] = (-26.0, 50.0)   # front gauntlet (rel. CX, height)
    hand_b: tuple[float, float] = (24.0, 46.0)    # sword gauntlet
    open_f: float = 0.0             # front gauntlet open (pointing)
    sword: float = 1.75             # greatsword angle (radians, 0 = pointing right, pi/2 = down)
    visor: float = 1.0
    core: float = 0.7               # chest crack glow
    flash: float = 0.0
    collapse: float = 0.0           # death: the armour sinks and spreads
    dissolve: float = 0.0
    slash: float = 0.0              # greatsword arc (attack)
    slash_fade: float = 0.0
    thrust: float = 0.0             # thrust streak (double)
    sigil: float = 0.0              # ember ring on the floor (cast)
    motes: tuple = field(default_factory=tuple)


class Body:
    def __init__(self, p: Pose) -> None:
        self.p = p

    def center(self, h: float) -> float:
        p = self.p
        k = max(0.0, min(1.0, h / H_HELM1))
        wave = p.sway * 1.8 * math.sin(p.phase + h * 0.12) * max(0.0, (H_FAULD - h) / H_FAULD) ** 1.2
        return CX + p.dx + p.lean * k ** 1.1 + wave

    def y_of(self, h: float) -> float:
        p = self.p
        hh = h * (1 - 0.55 * p.collapse)
        return GROUND - hh * p.sy + p.dy

    def h_of(self, y: float) -> float:
        p = self.p
        return (GROUND + p.dy - y) / p.sy / max(0.2, 1 - 0.55 * p.collapse)

    def to_cell(self, lx: float, h: float):
        return self.center(h) + lx * self.p.sx * (1 + 0.35 * self.p.collapse), self.y_of(h)


def _steel(light: float, x: int, y: int):
    # darker overall, dents break up big flat areas
    light = light - 0.1 + 0.07 * (hash01(x // 3, y // 3, 11) - 0.5)
    return ramp(STEEL, max(0.0, min(1.0, light)), x, y, 0.55)


# ---------------------------------------------------------------- torso and tabard
def torso_hw(h: float) -> float:
    if h < H_FAULD:
        return 0.0
    if h < H_WAIST:                                    # faulds flare outwards downwards
        return 9.5 + 3.5 * (H_WAIST - h) / (H_WAIST - H_FAULD)
    if h < H_CHEST:
        return 9.5 + 5.0 * smooth((h - H_WAIST) / (H_CHEST - H_WAIST))
    if h < H_GORGET:
        return 14.5 - 4.0 * smooth((h - H_CHEST) / (H_GORGET - H_CHEST))
    return 0.0


def draw_tabard(cv: Canvas, b: Body) -> None:
    """Crimson tabard torn into waving strands that fade into ash (no legs)."""
    p = b.p
    for y in range(CELL_H):
        h = b.h_of(y + 0.5)
        if h < FLOAT - 6 or h > H_WAIST:
            continue
        c = b.center(h)
        k = (H_WAIST - h) / (H_WAIST - FLOAT)              # 0 at the waist .. 1 at the tips
        hw = (10 + 6 * k ** 0.9) * p.sx * (1 + 0.35 * p.collapse)
        for x in range(CELL_W):
            dxp = x + 0.5 - c
            if abs(dxp) > hw + 1:
                continue
            u = dxp / hw
            fray = max(0.0, (H_CLOTH_TOP - h) / (H_CLOTH_TOP - FLOAT))
            if fray > 0:
                k0 = int(math.floor((u + 1) / 2 * STRANDS))
                wob = 1.4 * fray * math.sin(p.phase + k0 * 1.9 + h * 0.3)
                pos = ((dxp - wob) / hw + 1) / 2 * STRANDS
                s = int(math.floor(pos))
                if s < 0 or s >= STRANDS:
                    continue
                ln = 0.82 + 0.18 * hash01(s, 4)
                if fray > ln:
                    continue
                f = fray / ln
                half = 0.48 * (1 - f) ** 0.7 + 0.06
                if abs(pos - s - 0.5) > half:
                    continue
            elif abs(dxp) > hw:
                continue
            else:
                f = 0.0
            light = 0.62 - 0.35 * u - 0.3 * k + 0.12 * math.cos(u * 7 + h * 0.2)
            col = ramp(CLOTH, max(0.0, min(1.0, light)), x, y)
            solid = True
            if fray > 0 and f > 0.45:                     # tips burn into ash
                g = (f - 0.45) / 0.55
                col = mix(col, ASH[1] if g < 0.6 else ASH[0], min(0.9, g * 1.3))
                if g > 0.6:
                    solid = False
                    if bayer(x, y) < (g - 0.6) * 2.2:
                        continue
                if 0.25 < g < 0.45 and hash01(x, y, 8) > 0.86:
                    col = EMBER[2]                        # smouldering edge
            # gold hem line just under the faulds
            if 0 < H_FAULD - h < 1.4 and fray == 0:
                col = TRIM[2] if u < 0.3 else TRIM[1]
            cv.put(x, y, col, solid=solid)


def draw_torso(cv: Canvas, b: Body) -> tuple[float, float]:
    """Faulds, breastplate (ridge, specular, glowing crack) and gorget. Returns the crack centre."""
    p = b.p
    crack = b.to_cell(-3, H_CHEST - 6)
    for y in range(CELL_H):
        h = b.h_of(y + 0.5)
        if h < H_FAULD or h > H_GORGET + 2:
            continue
        c = b.center(h)
        hw = torso_hw(h) * p.sx * (1 + 0.35 * p.collapse)
        if h >= H_GORGET:                                  # gorget: narrow collar
            hw = 7 * p.sx
        for x in range(CELL_W):
            dxp = x + 0.5 - c
            if abs(dxp) > hw:
                continue
            u = dxp / max(1.0, hw)
            if h < H_WAIST:                                # faulds: overlapping bands
                band = (H_WAIST - h) % 2.6
                light = 0.62 - 0.35 * u - (0.25 if band < 0.8 else 0.0)
                col = _steel(light, x, y)
                if band < 0.8 and abs(u) < 0.95:
                    col = STEEL[1]
            elif h < H_GORGET:                             # breastplate
                curve = 1 - u * u
                light = 0.3 + 0.36 * curve ** 0.5 - 0.32 * u + 0.15 * (h - H_WAIST) / 17
                if -0.55 < u < -0.38 and h > H_WAIST + 4:  # specular streak
                    light += 0.35
                col = _steel(light, x, y)
                if abs(u - 0.02) < 0.05 and h > H_WAIST + 2:
                    col = STEEL[5] if h > H_CHEST - 6 else STEEL[4]   # central ridge
                if abs(u) > 0.88:
                    col = TRIM[1] if u < 0 else TRIM[0]          # bronze edging
            else:                                          # gorget
                light = 0.5 - 0.3 * u
                col = _steel(light, x, y)
                if h > H_GORGET + 1:
                    col = TRIM[2] if u < 0 else TRIM[1]
            cv.put(x, y, col)
    # the crack: jagged, glowing from inside (he is hollow)
    cx, cy = crack
    k = p.core
    pts = [(-1, -6), (0, -5), (0, -4), (1, -3), (0, -2), (-1, -1), (0, 0), (1, 1), (2, 2), (1, 3), (0, 4),
           (0, 5), (-1, 0), (-2, 1), (-3, 1), (2, 1), (3, 0), (4, 0)]
    for ox, oy in pts:
        lvl = 2 if k < 0.8 else 3
        if (ox, oy) in ((0, 0), (0, -2), (1, 1)):
            lvl += 1
        cv.put(cx + ox, cy + oy, EMBER[max(0, min(4, lvl - (1 if k < 0.4 else 0)))])
    return crack


def draw_pauldron(cv: Canvas, b: Body, side: int) -> None:
    p = b.p
    cx, cy = b.to_cell(side * 13.5, H_CHEST + 2)
    for layer, (rx, ry, oy) in enumerate(((9.5, 7.0, 0.0), (8.0, 5.0, 4.0))):
        lcy = cy + oy
        for yy in range(int(lcy - ry) - 1, int(lcy + ry) + 2):
            for xx in range(int(cx - rx) - 1, int(cx + rx) + 2):
                du, dv = (xx + 0.5 - cx) / rx, (yy + 0.5 - lcy) / ry
                d = du * du + dv * dv
                if d > 1 or (layer == 1 and dv < -0.2):
                    continue
                light = 0.75 - 0.35 * du - 0.45 * dv - 0.25 * d - (0.12 if side > 0 else 0)
                col = _steel(light, xx, yy)
                if d > 0.78 and dv > -0.3:
                    col = TRIM[2] if du < 0 else TRIM[1]
                if (du + 0.35) ** 2 + (dv + 0.45) ** 2 < 0.04:
                    col = STEEL[6]
                cv.put(xx, yy, col)
        cv.put(cx - side * 2, lcy - 1, TRIM[3])                 # rivet


def draw_helm(cv: Canvas, b: Body) -> tuple[float, float]:
    """Crowned great helm with a burning T-visor. Returns the visor centre."""
    p = b.p
    lift = 2.5 * (1 - p.collapse)                       # the helm floats over an empty collar
    hx, hy0 = b.to_cell(p.helm_dx, H_HELM0 + p.helm_dy + lift)
    _, hy1 = b.to_cell(p.helm_dx, H_HELM1 + p.helm_dy + lift)
    hx += p.lean * 0.15
    hw = 9.5 * p.sx
    top, bot = hy1, hy0
    # hollow gap between gorget and helm: darkness lit by embers
    gx, gy = b.to_cell(0, H_GORGET + 1.5)
    for yy in range(int(min(gy, bot)) - 1, int(max(gy, bot)) + 2):
        for xx in range(int(gx - 6), int(gx + 7)):
            if cv.get(xx, yy) is None or yy >= int(gy) - 1:
                k = 0.45 + 0.4 * p.core * (1 - abs(xx + 0.5 - gx) / 6)
                lvl = EMBER[1] if k > 0.75 and bayer(xx, yy) < 0.6 else mix(VOID, EMBER[0], k)
                if cv.get(xx, yy) is None:
                    cv.put(xx, yy, lvl)
    for yy in range(int(top) - 1, int(bot) + 1):
        v = (yy + 0.5 - top) / max(1.0, bot - top)            # 0 top .. 1 bottom
        if v < 0:
            continue
        w = hw * (math.sqrt(max(0.0, v / 0.28)) if v < 0.28 else 1.0) * (1 - 0.06 * max(0.0, v - 0.7))
        for xx in range(int(hx - w) - 1, int(hx + w) + 2):
            u = (xx + 0.5 - hx) / max(1.0, w)
            if abs(u) > 1:
                continue
            light = 0.68 - 0.38 * u - 0.25 * v + (0.2 if v < 0.3 and u < -0.2 else 0.0)
            col = _steel(light, xx, yy)
            if 0.27 < v < 0.33:
                col = TRIM[2] if u < 0.2 else TRIM[1]           # brow band
            if abs(u) > 0.9:
                col = STEEL[1]
            cv.put(xx, yy, col)
    # crown spikes
    for k, ox in enumerate((-6, -2, 2, 6)):
        ln = 4 if ox in (-2, 2) else 3
        for s in range(ln):
            x = hx + ox * p.sx + (0.5 if s == ln - 1 else 0)
            col = TRIM[3] if s == ln - 1 else TRIM[2] if ox < 0 else TRIM[1]
            cv.put(x, top - 1 - s, col)
    # T visor: slit across the eyes + a vertical slit down the face
    vy = top + (bot - top) * 0.47
    e = p.visor
    for xx in range(int(hx - 7 * p.sx), int(hx + 7 * p.sx) + 1):
        u = (xx + 0.5 - hx) / (7 * p.sx)
        hot = e * (1 - 0.5 * abs(u))
        lvl = 1 + int(hot * 2.2 + (bayer(xx, int(vy)) - 0.5) * 0.6)
        cv.put(xx, vy, EMBER[max(0, min(4, lvl))] if e > 0.05 else VOID)
        cv.put(xx, vy + 1, VOID if abs(u) > 0.25 else EMBER[max(0, min(3, lvl - 1))] if e > 0.05 else VOID)
    for yy in range(int(vy) + 1, int(bot) - 1):
        cv.put(hx - 0.5, yy, EMBER[1] if e > 0.5 else VOID)
        cv.put(hx + 0.5, yy, VOID)
    # breathing holes
    for k in range(3):
        cv.put(hx + 3 + k * 1.5, vy + 4 + (k % 2), VOID)
    return hx, vy


def draw_plume(cv: Canvas, b: Body) -> None:
    """Tattered crimson plume streaming back from the crown."""
    p = b.p
    hx, top = b.to_cell(p.helm_dx + 2, H_HELM1 + p.helm_dy + 2)
    hx += p.lean * 0.15
    for i in range(34):
        t = i / 33
        x = hx + 3 + t * 28
        y = top + 1 + t * 12 + 2.6 * math.sin(p.phase * 1 + t * 5) * t
        w = 3.0 * (1 - t) + 0.7
        for yy in range(int(y - w), int(y + w) + 1):
            if hash01(i, yy, 3) < t * 0.5:
                continue
            light = 0.7 - 0.5 * (yy + 0.5 - (y - w)) / (2 * w) - 0.3 * t
            cv.put(x, yy, ramp(CLOTH, max(0.0, min(1.0, light)), int(x), yy), solid=t < 0.85)


# ---------------------------------------------------------------- gauntlets and sword
def draw_gauntlet(cv: Canvas, b: Body, hand, *, back: bool, open_k: float = 0.0) -> tuple[float, float]:
    """Floating plate gauntlet: flared cuff trailing ember smoke behind, a fist (or pointing hand)."""
    p = b.p
    x, y = CX + p.dx + hand[0] * p.sx, b.y_of(hand[1])
    g = Canvas(CELL_W, CELL_H)
    side = 1 if back else -1                       # the cuff trails away from the hero
    cx, cy = x + side * 4.5, y + 1.5
    for yy in range(int(cy - 5), int(cy + 6)):     # cuff: a short flared cylinder
        for xx in range(int(cx - 4), int(cx + 5)):
            du, dv = (xx + 0.5 - cx) / 3.6, (yy + 0.5 - cy) / (3.0 + 1.6 * max(0.0, (xx + 0.5 - cx) * side) / 3.6)
            if du * du + dv * dv > 1:
                continue
            light = 0.62 - 0.35 * du - 0.45 * dv - (0.12 if back else 0)
            col = _steel(light, xx, yy)
            if abs(du * side - 0.8) < 0.22:
                col = TRIM[1]
            g.put(xx, yy, col)
    for yy in range(int(cy - 3), int(cy + 4)):     # the open, hollow end of the cuff glows
        xx = int(cx + side * 3.5)
        if g.get(xx, yy) is not None:
            g.put(xx, yy, EMBER[1] if abs(yy - cy) < 2 else VOID)
    for yy in range(int(y - 3), int(y + 4)):       # fist
        for xx in range(int(x - 4), int(x + 4)):
            du, dv = (xx + 0.5 - x) / 3.6, (yy + 0.5 - y) / 3.3
            if du * du + dv * dv > 1:
                continue
            light = 0.7 - 0.4 * du - 0.45 * dv - (0.12 if back else 0)
            g.put(xx, yy, _steel(light, xx, yy))
    if open_k > 0.2:                               # pointing: plated fingers stretch to the hero
        for k in range(3):
            for s_ in range(int(2 + 4 * open_k) - k):
                g.put(x - 4 - s_, y - 2 + k * 1.3, STEEL[5] if k == 0 else STEEL[3] if k == 1 else STEEL[2])
        g.put(x - 1, y - 4, STEEL[4])              # thumb
    else:
        for k in range(4):                         # knuckle plates
            g.put(x - 3 + k * 1.6, y - 2.5, STEEL[6] if not back else STEEL[4])
            g.put(x - 3 + k * 1.6, y - 1.5, STEEL[2])
    cv.blit(g, rim=OUTLINE)
    return x, y


def draw_greatsword(cv: Canvas, b: Body, grip, angle: float, glow: float) -> tuple[float, float]:
    """Executioner's greatsword held at ``grip``. Returns the blade tip."""
    gx, gy = grip
    ca, sa = math.cos(angle), math.sin(angle)
    nx, ny = -sa, ca
    sw = Canvas(CELL_W, CELL_H)

    def seg(s0, s1, half, colors, shade=0.0, rune=False):
        steps = int(abs(s1 - s0) * 2) + 1
        for i in range(steps):
            s = s0 + (s1 - s0) * i / max(1, steps - 1)
            hw = half(s)
            for j in range(-int(hw) - 1, int(hw) + 2):
                if abs(j) > hw:
                    continue
                px = gx + ca * s + nx * j
                py = gy + sa * s + ny * j
                side = j / max(0.5, hw)
                light = 0.62 + 0.38 * side * (1 if ny > 0 else -1) * -1 + shade
                if abs(j) <= 0.5 and rune and int(s) % 4 == 0 and glow > 0.3:
                    sw.put(px, py, EMBER[2 if glow < 1 else 3])
                    continue
                sw.put(px, py, ramp(colors, max(0.0, min(1.0, light)), int(px), int(py), 0.4))

    seg(-4, 0, lambda s: 1.0, TRIM[:3], -0.1)                       # grip + pommel
    seg(-5.5, -4.5, lambda s: 1.8, TRIM)
    seg(0, 1.6, lambda s: 7.0, TRIM, 0.05)                          # crossguard
    blade_len = 42
    seg(1.2, blade_len, lambda s: 3.0 * (1 - max(0.0, s - blade_len + 7) / 8) + 0.4, STEEL, 0.1, True)
    cv.blit(sw, rim=OUTLINE)
    return gx + ca * blade_len, gy + sa * blade_len


# ---------------------------------------------------------------- effects
def draw_slash(cv: Canvas, center, prog: float, fade: float) -> None:
    """Huge ember arc from overhead down through the left."""
    if prog <= 0:
        return
    cx, cy = center
    a0, a1 = -1.4, -4.3
    a_end = a0 + (a1 - a0) * min(1.0, prog)
    for line, (rad, thick) in enumerate(((30.0, 2), (35.0, 3), (40.0, 1))):
        for i in range(160):
            t = i / 159
            w = t - fade * 1.15
            if w <= 0:
                continue
            a = a0 + (a_end - a0) * t
            x = cx + math.cos(a) * rad * 1.25
            y = cy + math.sin(a) * rad * 0.9
            lv = 4 if w > 0.85 else 3 if w > 0.55 else 2 if w > 0.25 else 1
            for k in range(thick if w > 0.3 else 1):
                cv.put(x, y + k, EMBER[lv], solid=False, alpha=int(255 * min(1.0, 0.3 + w)))


def draw_thrust(cv: Canvas, tip, k: float) -> None:
    if k <= 0:
        return
    tx, ty = tip
    for i in range(40):
        t = i / 39
        x = tx - t * 46 * k
        w = 1 - t
        cv.put(x, ty, EMBER[3 if w > 0.6 else 2], solid=False, alpha=int(255 * w * k))
        if t < 0.6:
            cv.put(x, ty - 1, EMBER[2], solid=False, alpha=int(180 * w * k))
            cv.put(x, ty + 1, EMBER[1], solid=False, alpha=int(160 * w * k))


def draw_sigil(cv: Canvas, s: float, t: float) -> None:
    if s <= 0:
        return
    gx, gy = CX, GROUND
    k = min(1.0, s + 0.2)
    rx, ry = 36 * k, 7 * k
    for i in range(180):
        a = i / 180 * math.tau
        x, y = gx + math.cos(a) * rx, gy + math.sin(a) * ry
        on = (i + int(t * 40)) % 12 < 8
        cv.put(x, y, EMBER[2] if on else EMBER[1], solid=False, alpha=int(235 * s))
    for i in range(5):                                    # sword-shaped glyphs
        a = i / 5 * math.tau + t * 1.5
        x, y = gx + math.cos(a) * rx * 0.62, gy + math.sin(a) * ry * 0.62
        for d in range(-2, 3):
            cv.put(x + d, y, EMBER[3], solid=False, alpha=int(255 * s))
        cv.put(x, y - 1, EMBER[3], solid=False, alpha=int(255 * s))


# ---------------------------------------------------------------- render
def render(p: Pose, t: float = 0.0) -> Canvas:
    cv = Canvas(CELL_W, CELL_H)
    b = Body(p)
    draw_sigil(cv, p.sigil, t)
    grip = (CX + p.dx + p.hand_b[0] * p.sx, b.y_of(p.hand_b[1]))
    sword_behind = math.sin(p.sword) < -0.2 and p.slash <= 0     # raised: behind the helm
    tip = None
    if sword_behind:
        tip = draw_greatsword(cv, b, grip, p.sword, p.core)
    draw_plume(cv, b)
    draw_tabard(cv, b)
    crack = draw_torso(cv, b)
    draw_pauldron(cv, b, 1)
    visor = draw_helm(cv, b)
    draw_pauldron(cv, b, -1)
    if not sword_behind:
        tip = draw_greatsword(cv, b, grip, p.sword, p.core)
    draw_gauntlet(cv, b, p.hand_b, back=True)
    draw_gauntlet(cv, b, p.hand_f, back=False, open_k=p.open_f)
    outline(cv, OUTLINE)
    if p.visor > 0.05:
        cv.glow(visor[0], visor[1], 7 + 4 * p.visor, EMBER[1], 0.45 * p.visor)
    if p.core > 0.05:
        cv.glow(crack[0], crack[1], 8 + 4 * p.core, EMBER[1], 0.4 * p.core)
    if p.slash > 0:
        draw_slash(cv, b.to_cell(-10, 52), p.slash, p.slash_fade)
    if p.thrust > 0 and tip is not None:
        draw_thrust(cv, tip, p.thrust)
    for (mx, my, lv) in p.motes:
        cv.put(mx, my, EMBER[lv] if lv < 5 else ASH[2], solid=False)
    flash(cv, p.flash)
    if p.dissolve > 0:
        dissolve(cv, p.dissolve, GROUND - H_HELM1 - 10, GROUND + 2, EMBER[3], EMBER[1], upward=True)
    return cv


# ---------------------------------------------------------------- animations
IDLE_FRAMES = 16


def idle_pose(i: int, n: int = IDLE_FRAMES) -> Pose:
    a = math.tau * i / n
    bob = round(2.0 * math.sin(a))
    return Pose(
        dy=-bob, phase=a, sway=1.0,
        helm_dy=0.6 * math.sin(a - 0.8),
        hand_f=(-26 + 1.2 * math.sin(a + 0.7), 50 + 2.0 * math.sin(a - 0.9)),
        hand_b=(24 + 0.8 * math.sin(a + 1.6), 46 + 1.6 * math.sin(a - 1.4)),
        sword=1.75 + 0.03 * math.sin(a - 1.4),
        visor=0.8 if i == 11 else 1.0, core=0.65 + 0.25 * math.sin(a * 2),
    )


def idle_frames():
    return [(idle_pose(i), 100) for i in range(IDLE_FRAMES)]


def attack_frames():
    """Tajo del Verdugo: overhead wind-up, lunge, ember arc."""
    b = idle_pose(0)
    return [
        (replace(b, dx=3, lean=3, hand_b=(18, 66), sword=-1.0, visor=1.2, core=0.9), 100),
        (replace(b, dx=6, lean=6, sy=1.04, hand_b=(12, 80), hand_f=(-20, 60), sword=-1.9, visor=1.5,
                 core=1.2), 150),
        (replace(b, dx=-12, lean=-9, sx=1.05, hand_b=(-26, 60), hand_f=(-34, 48), sword=3.4, visor=1.6,
                 core=1.3, slash=0.55), 55),
        (replace(b, dx=-18, lean=-11, sx=1.04, hand_b=(-34, 40), hand_f=(-36, 44), sword=2.4,
                 visor=1.5, core=1.2, slash=1.0), 65),
        (replace(b, dx=-18, lean=-10, hand_b=(-30, 34), sword=2.1, visor=1.3, slash=1.0,
                 slash_fade=0.45), 90),
        (replace(b, dx=-13, lean=-6, hand_b=(-14, 38), sword=1.95, visor=1.15, slash=1.0,
                 slash_fade=0.9), 95),
        (replace(b, dx=-7, lean=-3, hand_b=(6, 42), sword=1.85), 95),
        (replace(b, dx=-3, lean=-1, hand_b=(18, 45), sword=1.78), 95),
        (b, 110),
    ]


def double_frames():
    """Estocada Doble: two quick thrusts (sword levelled at the hero)."""
    b = idle_pose(0)
    level = math.pi                                    # pointing left
    return [
        (replace(b, dx=4, lean=3, hand_b=(14, 52), sword=level - 0.15, visor=1.25, core=0.9), 110),
        (replace(b, dx=-14, lean=-7, sx=1.04, hand_b=(-24, 52), sword=level, visor=1.5, thrust=1.0), 60),
        (replace(b, dx=-4, lean=-2, hand_b=(4, 52), sword=level - 0.1, visor=1.3, thrust=0.3), 80),
        (replace(b, dx=-16, lean=-8, sx=1.05, hand_b=(-28, 50), sword=level + 0.05, visor=1.5,
                 thrust=1.0), 60),
        (replace(b, dx=-10, lean=-5, hand_b=(-12, 50), sword=level - 0.2, visor=1.25, thrust=0.3), 90),
        (replace(b, dx=-5, lean=-2, hand_b=(10, 48), sword=2.4), 95),
        (replace(b, dx=-1, hand_b=(20, 46), sword=1.9), 95),
        (b, 110),
    ]


def command_frames():
    """Danza de Espadas: the front gauntlet points at the hero while the swords fly (drawn by the game)."""
    b = idle_pose(0)
    out = [
        (replace(b, lean=2, hand_f=(-30, 60), open_f=0.6, visor=1.3, core=1.0), 100),
        (replace(b, lean=-3, hand_f=(-40, 58), open_f=1.0, visor=1.6, core=1.3), 110),
    ]
    for k in range(8):                                    # hold while blades are thrown
        out.append((replace(b, lean=-4, dy=b.dy - (k % 2), hand_f=(-42 + (k % 2), 58), open_f=1.0,
                            visor=1.5 + 0.1 * (k % 2), core=1.2, phase=0.4 * k), 90))
    out += [(replace(b, lean=-1, hand_f=(-30, 54), open_f=0.4, visor=1.2), 100), (b, 110)]
    return out


def cast_frames():
    """Llamar al Acero / Furia Hueca: gauntlets rise, sigil on the floor, visor and crack blaze."""
    b = idle_pose(0)
    out = []
    ups = [0.0, 0.35, 0.7, 1.0, 1.0, 1.0, 0.8, 0.5, 0.2]
    for k, u in enumerate(ups):
        out.append((replace(b, dy=-round(3 * u), helm_dy=1.2 * u,
                            hand_f=(-26 - 6 * u, 50 + 22 * u), hand_b=(24 + 4 * u, 46 + 12 * u),
                            open_f=u, sword=1.75 - 0.25 * u, visor=1.0 + 0.7 * u, core=0.7 + 0.8 * u,
                            sigil=min(1.0, k / 3) if k < 7 else u, phase=0.5 * k), 85))
    out.append((b, 110))
    return out


def hurt_frames():
    b = idle_pose(0)
    return [
        (replace(b, dx=6, lean=6, sx=0.95, helm_dy=2.5, helm_dx=2, flash=0.85, visor=0.3,
                 hand_f=(-20, 56), hand_b=(28, 50), phase=1.4), 55),
        (replace(b, dx=8, lean=6, helm_dy=1.5, helm_dx=2, flash=0.55, visor=0.6, hand_f=(-19, 54),
                 hand_b=(29, 49), phase=2.1), 65),
        (replace(b, dx=6, lean=4, helm_dy=0.5, helm_dx=1, flash=0.2, visor=0.85, phase=2.8), 70),
        (replace(b, dx=4, lean=2, phase=3.5), 70),
        (replace(b, dx=2, lean=1, phase=4.2), 80),
        (b, 100),
    ]


def death_frames():
    b = idle_pose(0)
    out = [
        (replace(b, dx=5, lean=5, flash=0.85, visor=0.4, helm_dy=3, hand_f=(-20, 60), hand_b=(28, 58)), 70),
        (replace(b, dx=6, lean=3, flash=0.3, visor=1.9, core=1.6, helm_dy=4, hand_f=(-24, 66),
                 hand_b=(30, 64), sword=1.4), 110),
    ]
    steps = 12
    for k in range(steps):
        u = (k + 1) / steps
        c = smooth(min(1.0, u * 1.7))
        motes = tuple(
            (CX - 30 + hash01(k, j, 9) * 70, GROUND - 6 - u * 80 * hash01(j, k, 4),
             (1 + int(hash01(j, k, 2) * 3)) if j % 3 else 5) for j in range(6 + k))
        out.append((replace(b, dx=6, dy=FLOAT * c, lean=3 + 4 * c, collapse=c, helm_dy=4 - 10 * c,
                            helm_dx=5 * c, visor=1.6 * (1 - c), core=1.3 * (1 - c),
                            hand_f=(-24 - 8 * c, 30 - 22 * c), hand_b=(30 + 6 * c, 30 - 22 * c),
                            sword=1.4 - 1.3 * c, sway=1 - c,
                            dissolve=0.0 if u < 0.45 else min(1.0, (u - 0.45) / 0.55),
                            motes=motes if u > 0.25 else ()), 85))
    out.append((replace(b, dissolve=1.0), 120))
    return out


ANIMATIONS = {
    "idle": (idle_frames, True),
    "attack": (attack_frames, False),
    "double": (double_frames, False),
    "command": (command_frames, False),
    "cast": (cast_frames, False),
    "hurt": (hurt_frames, False),
    "death": (death_frames, False),
}
EVENTS = {"attack": {"strikes": [2]}, "double": {"strikes": [1, 3]},
          "command": {"strikes": [2], "blades": True}}
MOVES = {"execute": "attack", "double": "double", "blade_dance": "command", "summon": "cast",
         "fury": "cast"}


# ---------------------------------------------------------------- floating sword sprite
BLADE_W = 52
BLADE_ROTATIONS = 16


def render_blade(angle: float) -> Canvas:
    """One floating sword (pointing at ``angle``), centred in a BLADE_W square, ember-runed."""
    cv = Canvas(BLADE_W, BLADE_W)
    c = BLADE_W / 2
    ca, sa = math.cos(angle), math.sin(angle)
    nx, ny = -sa, ca
    length, back = 20.0, 7.0
    for i in range(int((length + back) * 3)):
        s = -back + i / 3
        if s < -5.5:
            hw, cols = 1.4, TRIM                          # pommel
        elif s < -0.7:
            hw, cols = 0.8, TRIM[:3]                      # grip
        elif s < 0.7:
            hw, cols = 4.6, TRIM                          # guard
        else:
            hw, cols = 2.2 * (1 - max(0.0, s - length + 5) / 6) + 0.3, STEEL
        for jj in range(-5, 6):
            j = jj * 0.5
            if abs(j) > hw:
                continue
            x, y = c + ca * s + nx * j, c + sa * s + ny * j
            light = 0.6 - 0.35 * j / max(0.5, hw) * (1 if ny >= 0 else -1)
            col = ramp(cols, max(0.0, min(1.0, light)), int(x), int(y), 0.3)
            if cols is STEEL and abs(j) < 0.3 and int(s) % 3 == 0:
                col = EMBER[2]
            cv.put(x, y, col)
    outline(cv, OUTLINE)
    cv.glow(c + ca * 7, c + sa * 7, 11, EMBER[1], 0.3)
    return cv


def build_blade_strip():
    rows = [[None] * (BLADE_W * BLADE_ROTATIONS) for _ in range(BLADE_W)]
    for k in range(BLADE_ROTATIONS):
        cv = render_blade(k / BLADE_ROTATIONS * math.tau)
        for y in range(BLADE_W):
            rows[y][k * BLADE_W:(k + 1) * BLADE_W] = cv.px[y]
    return rows


def build():
    return build_sheet(ANIMATIONS, render, (CELL_W, CELL_H), ANCHOR, f"{SHEET_ID}_sheet.png",
                       {"events": EVENTS, "moves": MOVES, "boss": True,
                        "blade": {"sheet": "knight_blade.png", "size": BLADE_W,
                                  "rotations": BLADE_ROTATIONS}})


def main() -> None:
    sheet, meta = build()
    save_sheet(OUT_DIR, SHEET_ID, sheet, meta)
    write_png(OUT_DIR / "knight_blade.png", build_blade_strip())
    print(f"wrote assets/enemies/{SHEET_ID}_sheet.png ({len(sheet[0])}x{len(sheet)}), .json and knight_blade.png")


if __name__ == "__main__":
    main()
