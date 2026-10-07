"""Draw and animate the floor-1 boss "Reina Micélida" (a fungal queen). Stdlib only:

    python scripts/generate_boss_mycelid.py

Same method as the Espectro (``docs/code-drawn-sprites.md``): one renderer, every
frame a ``Pose``. The queen is a giant toadstool-woman:

* a wide crimson cap with a scalloped, drooping rim and glowing toxic spots;
* the shadow under the cap (gills lit green from below) hides her face: two
  slanted yellow-green eyes;
* a lace veil (like a veiled-lady mushroom) hangs from her neck over an ivory
  stem with green veins, swelling into a cup-shaped volva and floor roots;
* thin hyphae arms with root fingers, and baby mushrooms sprouting at her feet.

Animations (non-death actions end on idle frame 0):
  idle    14-frame breathing loop: cap swells, stalk sways, veil lags, spots pulse
  attack  "Raíces Estranguladoras": rears up, slams forward, a root wave erupts towards the hero
  spores  "Lluvia de Esporas" / "Floración": the cap inflates and blasts a spore cloud forward
  cast    "Brote de Moho": gills blaze, a ring of mould and spores grows around her
  hurt    white flash, squash, cap wobble
  death   the cap wilts, the stalk folds and she rots away top-down into spores

Output: ``assets/enemies/mycelid_sheet.png`` + ``.json`` (``events.<anim>.strikes``
lists the frames where a hit lands).
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
SHEET_ID = "mycelid"

CELL_W, CELL_H = 224, 124
CX, GROUND = 150, 114           # stalk centre line, ground row
ANCHOR = (CX, GROUND + 2)
RIM_H = 64                      # height of the cap rim above the ground
CAP_A, CAP_B = 40.0, 26.0       # cap half-width and dome height
NECK_H = 54                     # where the veil hangs from

# ---------------------------------------------------------------- palette
OUTLINE = (16, 6, 14)
CAP = [(30, 8, 24), (58, 14, 40), (96, 22, 58), (138, 32, 72), (178, 52, 84), (212, 92, 104),
       (238, 148, 132)]
GILL = [(14, 6, 12), (30, 12, 22), (46, 30, 30), (62, 70, 34)]
STEM = [(36, 34, 36), (66, 64, 58), (100, 100, 82), (138, 140, 108), (176, 178, 140),
        (206, 206, 172)]
VEIN = (82, 120, 54)
LACE = [(120, 112, 84), (186, 180, 140), (232, 228, 196), (255, 252, 232)]
TOX = [(40, 76, 22), (90, 160, 40), (170, 230, 70), (236, 255, 160)]
SPORE = [(120, 130, 60), (180, 196, 96), (226, 236, 150), (250, 255, 214)]
MOULD = [(36, 46, 26), (62, 84, 36), (100, 134, 50)]
ROT = (58, 40, 30)
WHITE = (255, 255, 255)

SPOTS = [(-0.62, 0.30, 3.2), (-0.30, 0.62, 2.6), (0.05, 0.84, 2.4), (0.36, 0.55, 3.4),
         (0.70, 0.26, 2.6), (-0.04, 0.38, 2.0), (-0.78, 0.08, 1.8), (0.55, 0.80, 1.6),
         (-0.48, 0.80, 1.5)]
BABIES = [(-34, 7, 4.0, 0.0), (-25, 5, 3.0, 1.7), (27, 8, 4.5, 3.1), (36, 5, 3.0, 4.4)]
ROOTS = [(-1, 0.0, 30), (-1, 2.2, 22), (1, 1.1, 26), (1, 3.3, 18)]


@dataclass(frozen=True)
class Pose:
    dx: float = 0.0
    dy: float = 0.0
    lean: float = 0.0             # top of the stalk offset (negative = towards the hero)
    sx: float = 1.0               # squash/stretch about the ground
    sy: float = 1.0
    cap_s: float = 1.0            # cap inflation
    droop: float = 0.0            # rim droop (wilting)
    phase: float = 0.0
    sway: float = 1.0
    hand_f: tuple[float, float] = (-30.0, 34.0)   # front hand (rel. CX, height above ground)
    hand_b: tuple[float, float] = (27.0, 36.0)
    finger: float = 0.4           # 0 curled .. 1 spread
    eye: float = 1.0
    glow: float = 0.8             # spots + gills
    flash: float = 0.0
    rot: float = 0.0              # death: colours rot to brown
    dissolve: float = 0.0
    roots: float = 0.0            # root wave progress (attack)
    roots_fade: float = 0.0
    spores: float = 0.0           # spore blast progress
    spores_fade: float = 0.0
    ring: float = 0.0             # mould ring (cast)
    motes: tuple = field(default_factory=tuple)


class Body:
    def __init__(self, p: Pose) -> None:
        self.p = p
        self.H = RIM_H + CAP_B

    def center(self, h: float) -> float:
        p = self.p
        k = max(0.0, h) / self.H
        wave = p.sway * 1.6 * math.sin(p.phase + h * 0.05) * k ** 1.5
        return CX + p.dx + p.lean * k ** 1.3 + wave

    def y_of(self, h: float) -> float:
        return GROUND - h * self.p.sy + self.p.dy

    def h_of(self, y: float) -> float:
        return (GROUND + self.p.dy - y) / self.p.sy

    def to_cell(self, lx: float, h: float) -> tuple[float, float]:
        return self.center(h) + lx * self.p.sx, self.y_of(h)


def _rotc(c, k: float):
    return mix(c, ROT, k * 0.75) if k > 0 else c


# ---------------------------------------------------------------- stalk
def stem_hw(h: float) -> float:
    if h < 0:
        return 0.0
    if h < 9:                                   # volva cup, wide at the ground
        return 21 - 6 * (h / 9) ** 0.8
    if h < 30:                                  # bulb
        return 15 + 3.0 * math.sin((h - 9) / 21 * math.pi)
    if h < 50:
        return 15 - 5 * smooth((h - 30) / 20)
    return 10.0 if h <= RIM_H + 2 else 0.0


def draw_stem(cv: Canvas, b: Body) -> None:
    p = b.p
    for y in range(CELL_H):
        h = b.h_of(y + 0.5)
        if h < -0.5 or h > RIM_H + 2:
            continue
        c = b.center(h)
        hw = stem_hw(max(0.0, h)) * p.sx
        for x in range(CELL_W):
            dxp = x + 0.5 - c
            if abs(dxp) > hw:
                continue
            u = dxp / max(1.0, hw)
            light = 0.78 - 0.36 * u - 0.25 * (1 - h / RIM_H)
            if h > 36:                           # under the cap: deep shadow
                light -= 0.75 * smooth((h - 36) / 20)
            if abs(u) > 0.85:
                light -= 0.15
            if h < 9:                            # volva: rougher, darker, a lip at its top
                light -= 0.12 + 0.1 * hash01(x, int(h), 2)
                if 7.5 < h < 9:
                    light += 0.25
            col = ramp(STEM, max(0.0, min(1.0, light)), x, y)
            # green veins climbing the stalk
            vein = math.sin(u * 7.5 + h * 0.11 + 0.6 * math.sin(h * 0.2)) > 0.93 and 9 < h < 48
            if vein:
                col = mix(col, VEIN, 0.65)
            cv.put(x, y, _rotc(col, p.rot))


def draw_roots(cv: Canvas, b: Body) -> None:
    """Thin roots that crawl along the floor from the volva."""
    p = b.p
    for side, ph, length in ROOTS:
        x0 = CX + p.dx + side * 17
        pts = []
        for i in range(int(length)):
            t = i / length
            x = x0 + side * i
            y = GROUND - 0.6 + 1.3 * math.sin(i * 0.45 + ph + 0.6 * math.sin(p.phase)) * t
            pts.append((x, y))
        for i, (x, y) in enumerate(pts):
            t = i / len(pts)
            col = STEM[2] if t < 0.4 else STEM[1]
            cv.put(x, y, _rotc(col, p.rot))
            if t < 0.35:
                cv.put(x, y - 1, _rotc(STEM[3], p.rot))


def draw_babies(cv: Canvas, b: Body) -> None:
    p = b.p
    for lx, height, cap_r, ph in BABIES:
        bob = 0.6 * math.sin(p.phase + ph)
        bx = CX + p.dx * 0.3 + lx
        top = GROUND - height - bob * 0.5
        for yy in range(int(top), GROUND + 1):        # little stalk
            for xx in (int(bx), int(bx) + 1):
                cv.put(xx, yy, _rotc(STEM[3] if xx == int(bx) else STEM[2], p.rot))
        cy = top - 1
        for yy in range(int(cy - cap_r * 0.8) - 1, int(cy) + 2):
            for xx in range(int(bx - cap_r) - 1, int(bx + cap_r) + 2):
                dx, dy = (xx + 0.5 - bx - 0.5) / cap_r, (yy + 0.5 - cy) / (cap_r * 0.8)
                if dy > 0.25 or dx * dx + dy * dy > 1:
                    continue
                light = 0.75 - 0.4 * dx - 0.3 * (dy + 1)
                cv.put(xx, yy, _rotc(ramp(CAP, light, xx, yy), p.rot))
        cv.put(int(bx) - 1, int(cy - cap_r * 0.4), _rotc(TOX[2] if p.glow > 0.6 else TOX[1], p.rot))


# ---------------------------------------------------------------- veil
def draw_veil(cv: Canvas, b: Body) -> None:
    """Lace net hanging from the neck and flaring over the stalk (holes show the stem)."""
    p = b.p
    bottom = 22
    for y in range(CELL_H):
        h = b.h_of(y + 0.5)
        if h > NECK_H or h < bottom - 4:
            continue
        k = (NECK_H - h) / (NECK_H - bottom)            # 0 at the neck, 1 at the hem
        lag = 2.4 * math.sin(p.phase - 0.9) * k ** 1.2 * p.sway
        c = b.center(h) + lag
        hw = (11 + 16 * k ** 1.15) * p.sx
        for x in range(CELL_W):
            dxp = x + 0.5 - c
            if abs(dxp) > hw:
                continue
            u = dxp / hw
            hem = bottom + 2.5 * math.sin(u * 9 + 0.5) + 1.5 * hash01(int(u * 8 + 20), 3)
            if h < hem:
                continue
            a = (dxp * 0.9 + h * 0.75) % 5.0
            bb = (dxp * 0.9 - h * 0.75) % 5.0
            on = a < 1.05 or bb < 1.05
            edge = h < hem + 1.3 or abs(u) > 0.94 or h > NECK_H - 1.5
            if not (on or edge):
                continue
            light = 0.8 - 0.4 * u - 0.35 * k
            col = ramp(LACE, max(0.0, min(1.0, light)), x, y, 0.4)
            cv.put(x, y, _rotc(col, p.rot))


# ---------------------------------------------------------------- cap
def rim_drop(u: float, p: Pose) -> float:
    """How far below the rim line the cap edge hangs at ``u`` (-1..1)."""
    scallop = 1.4 * abs(math.sin(u * 5.2 * math.pi / 2 + 0.4))
    return (4.5 + 10 * p.droop) * u * u + scallop * (0.6 + 0.4 * u * u)


def draw_cap(cv: Canvas, b: Body) -> tuple[float, float]:
    """Cap dome, gills shadow and eyes. Returns the eye centre."""
    p = b.p
    ccx = b.center(RIM_H + CAP_B * 0.4) + p.lean * 0.15
    A = CAP_A * p.sx * (0.96 + 0.04 * p.cap_s) * (1 + 0.04 * p.droop)
    B = CAP_B * p.cap_s * (1 - 0.25 * p.droop)
    rim_y = b.y_of(RIM_H)
    tilt = p.lean * 0.035                              # the cap tips with the stalk
    gill_band = 11.0
    for y in range(CELL_H):
        for x in range(CELL_W):
            u = (x + 0.5 - ccx) / A
            if abs(u) > 1:
                continue
            ry = rim_y + u * tilt * A * 0.4
            dy_up = (ry - (y + 0.5)) / (B * p.sy)        # >0 above the rim line
            edge = ry + rim_drop(u, p)
            if dy_up >= 0:
                if u * u + dy_up * dy_up > 1:
                    continue
                v = dy_up                                   # 0 rim .. 1 top
                light = 0.62 - 0.38 * u + 0.30 * v - 0.12 * (1 - v)
                light += 0.07 * math.cos(u * 6 + v * 3)
                if u < -0.7 and v < 0.6:
                    light += 0.12
                col = ramp(CAP, max(0.0, min(1.0, light)), x, y)
                cv.put(x, y, _rotc(col, p.rot))
            elif y + 0.5 <= edge:                          # drooping rim part
                light = 0.42 - 0.35 * u - 0.15 * ((y + 0.5 - ry) / 8)
                col = ramp(CAP, max(0.0, min(1.0, light)), x, y)
                if y + 0.5 > edge - 1.2:
                    col = CAP[5] if u < 0.2 else CAP[3]       # lit lip of the rim
                cv.put(x, y, _rotc(col, p.rot))
            elif abs(u) < 0.92 and y + 0.5 <= ry + rim_drop(u, p) + gill_band * math.sqrt(max(0.0, 1 - u * u / 0.85)):
                # underside: dark gills, glowing green near the edge
                depth = (y + 0.5 - edge) / gill_band
                radial = math.sin(math.atan2(y + 0.5 - ry + 10, x + 0.5 - ccx) * 30)
                g = 0 if depth > 0.5 else 1
                col = GILL[g]
                if radial > 0.45 and depth < 0.8:
                    gl = p.glow * (1 - depth) * (0.4 + 0.6 * abs(u))
                    col = mix(GILL[2], TOX[1] if gl < 0.7 else TOX[2], min(1.0, gl))
                cv.put(x, y, _rotc(col, p.rot))
    # spots
    for su, sv, r in SPOTS:
        sx = ccx + su * A * 0.92
        sy_ = rim_y - sv * B * p.sy * math.sqrt(max(0.0, 1 - su * su)) * 0.95 + su * tilt * A * 0.4
        rr = r * (0.9 + 0.1 * p.cap_s)
        for yy in range(int(sy_ - rr) - 1, int(sy_ + rr) + 2):
            for xx in range(int(sx - rr * 1.2) - 1, int(sx + rr * 1.2) + 2):
                d = math.hypot((xx + 0.5 - sx) / 1.2, yy + 0.5 - sy_) / rr
                if d > 1 or cv.get(xx, yy) is None:
                    continue
                lvl = 3 if d < 0.4 else 2 if d < 0.75 else 1
                if p.glow < 0.6:
                    lvl -= 1
                col = SPORE[max(0, lvl)] if p.glow < 1.15 else TOX[min(3, lvl + 1)]
                cv.put(xx, yy, _rotc(col, p.rot))
    # eyes in the gill shadow, slanted and menacing
    ex = b.center(RIM_H - 4) + p.lean * 0.1
    ey = rim_y + 6.0
    e = p.eye * (1 - p.rot)
    # a pale, mask-like face in the gill shadow (only its lit lower half shows)
    for yy in range(int(ey - 3), int(ey + 9)):
        for xx in range(int(ex - 9), int(ex + 10)):
            dx, dy = (xx + 0.5 - ex) / 8.5, (yy + 0.5 - ey - 2) / 7.0
            d = dx * dx + dy * dy
            if d > 1 or cv.get(xx, yy) is None:
                continue
            light = 0.15 + 0.5 * max(0.0, dy) - 0.25 * dx
            col = mix(GILL[1], STEM[2], max(0.0, min(1.0, light)))
            if d > 0.82:
                col = GILL[0]
            cv.put(xx, yy, _rotc(col, p.rot))
    if e > 0.05:
        hot = TOX[3] if e > 0.6 else TOX[1]
        warm = TOX[2] if e < 1.2 else TOX[3]
        for ox, oy, c in ((-7, -2, warm), (-6, -1, hot), (-5, -1, hot), (-4, 0, hot), (-3, 0, warm),
                          (-6, 0, GILL[0]), (-5, 0, warm),
                          (3, 0, warm), (4, 0, hot), (5, -1, hot), (6, -1, hot), (7, -2, warm),
                          (6, 0, GILL[0]), (5, 0, warm)):
            cv.put(int(ex + ox), int(ey + oy), c)
        if e > 1.15:
            for ox, oy in ((-8, -3), (8, -3), (-2, 1), (2, 1)):
                cv.put(int(ex + ox), int(ey + oy), TOX[1])
    # jagged mouth
    mouth = 1 if e > 1.2 else 0
    for k, ox in enumerate(range(-3, 4)):
        my = ey + 5 + (k % 2) + (mouth if abs(ox) < 2 else 0)
        cv.put(int(ex + ox), int(my), GILL[0])
        if mouth:
            cv.put(int(ex + ox), int(my) - 1, TOX[0])
    return ex, ey


# ---------------------------------------------------------------- arms
def draw_arm(cv: Canvas, b: Body, side: int, hand, finger: float, back: bool) -> None:
    p = b.p
    sh_x, sh_y = b.to_cell(side * 9, NECK_H - 3)
    hx = CX + p.dx + hand[0] * p.sx
    hy = b.y_of(hand[1])
    ex, ey = (sh_x + hx) / 2 + side * 7, (sh_y + hy) / 2 - 4
    pts = bezier((sh_x, sh_y), (ex, ey), (hx, hy), int(math.hypot(hx - sh_x, hy - sh_y) * 1.5) + 3)
    cols = STEM[:-1] if not back else STEM[:-2]
    stroke(cv, pts, lambda t: 2.3 - 1.0 * t + 0.6 * max(0.0, t - 0.8) / 0.2, cols,
           shade=-0.15 if back else 0.0, rim=OUTLINE)
    # root fingers
    ang0 = math.atan2(hy - ey, hx - ex)
    for k, (a, ln) in enumerate(((-0.7, 6), (-0.2, 8), (0.3, 7), (0.8, 5))):
        ang = ang0 + a * (0.5 + 0.9 * finger)
        curl = 0.18 * (1 - finger) * (1 if side < 0 else -1)
        x, y = hx, hy
        for s in range(ln):
            ang += curl
            x += math.cos(ang)
            y += math.sin(ang)
            col = STEM[3] if s < ln - 2 else TOX[1] if p.glow > 0.9 else STEM[1]
            cv.put(x, y, _rotc(col, p.rot))


# ---------------------------------------------------------------- effects
def draw_root_wave(cv: Canvas, b: Body, prog: float, fade: float) -> None:
    """Roots erupt from the floor in a wave travelling left, towards the hero."""
    if prog <= 0:
        return
    start, end = CX - 22, 2
    front = start + (end - start) * min(1.0, prog)
    for i in range(16):
        x0 = start - i * (start - end) / 15.5
        if x0 < front:
            continue
        age = (x0 - front) / max(1.0, start - end)        # 0 newest .. older behind
        height = (20 - 9 * (i % 3 == 1) - 4 * (i % 2)) * max(0.0, 1 - age * 1.6) * (1 - fade)
        if height < 1:
            continue
        lean = -0.35 - 0.1 * (i % 2)
        for s in range(int(height)):
            t = s / height
            w = 2.6 * (1 - t) + 0.6
            cx = x0 + lean * s
            y = GROUND + 1 - s
            for xx in range(int(cx - w), int(cx + w) + 1):
                light = 0.75 - 0.4 * (xx + 0.5 - cx) / max(1.0, w) - 0.3 * t
                col = ramp(STEM, max(0.0, min(1.0, light)), xx, y)
                if t > 0.82:
                    col = TOX[2]
                cv.put(xx, y, col)
        for k in range(3):                                 # dirt kicked up
            cv.put(x0 + (hash01(i, k, 7) - 0.5) * 8, GROUND - hash01(k, i, 8) * 6, MOULD[1], solid=False)


def draw_spore_blast(cv: Canvas, b: Body, prog: float, fade: float, t: float) -> None:
    """Puffy spore clouds blown forward (left) and up from under the cap."""
    if prog <= 0:
        return
    ox, oy = b.to_cell(-20, RIM_H - 2)
    for k in range(9):
        lead = prog * 1.4 - k * 0.11
        if lead <= 0:
            continue
        lead = min(1.0, lead)
        x = ox - lead * (118 + 12 * hash01(k, 1, 4)) - k * 2
        y = oy + 6 - lead * 26 * math.sin(lead * math.pi * 0.8) + (hash01(k, 3, 4) - 0.5) * 18
        r = 4 + 8 * lead * (0.7 + 0.3 * hash01(k, 2, 4))
        alpha_k = (1 - fade) * (1 - max(0.0, lead - 0.8) * 2.5)
        if alpha_k <= 0:
            continue
        for yy in range(int(y - r) - 1, int(y + r) + 2):
            for xx in range(int(x - r) - 1, int(x + r) + 2):
                d = math.hypot(xx + 0.5 - x, yy + 0.5 - y) / r
                if d > 1:
                    continue
                if bayer(xx, yy) > (1.5 - d) * alpha_k * 1.4:
                    continue
                ly = (yy + 0.5 - y) / r - (xx + 0.5 - x) / r * 0.4      # lit from the upper left
                lvl = 3 if d < 0.3 and ly < 0 else 2 if d < 0.65 else 1 if d < 0.88 else 0
                cv.put(xx, yy, SPORE[lvl], solid=False, alpha=int(255 * min(1.0, alpha_k + 0.25)))
    for j in range(22):                                     # specks
        s = prog * 1.2 - hash01(j, 9, 1) * 0.5
        if s <= 0 or fade > 0.85:
            continue
        x = ox - s * 120 * (0.6 + 0.6 * hash01(j, 4, 1))
        y = oy - s * 40 * hash01(j, 5, 1) + (hash01(j, 6, 1) - 0.4) * 30
        cv.put(x, y, TOX[2 + (j % 2)], solid=False)


def draw_ring(cv: Canvas, strength: float, t: float) -> None:
    """Mould ring on the floor with spore buds (cast)."""
    if strength <= 0:
        return
    gx, gy = CX, GROUND + 1
    k = min(1.0, strength + 0.15)
    rx, ry = 44 * k, 8 * k
    for i in range(200):
        a = i / 200 * math.tau
        x, y = gx + math.cos(a) * rx, gy + math.sin(a) * ry
        on = (i + int(t * 30)) % 9 < 6
        cv.put(x, y, MOULD[2] if on else MOULD[1], solid=False, alpha=int(240 * strength))
        if math.sin(a) > 0:                                  # nearer half: thicker
            cv.put(x, y + 1, MOULD[1] if on else MOULD[0], solid=False, alpha=int(220 * strength))
        if i % 25 == 0 and strength > 0.4:                 # buds
            hh = 1 + int(3 * strength * hash01(i, 2, 9))
            for s in range(hh):
                cv.put(x, y - s - 1, STEM[3], solid=False)
            cv.put(x, y - hh - 1, TOX[2], solid=False)


# ---------------------------------------------------------------- render
def render(p: Pose, t: float = 0.0) -> Canvas:
    cv = Canvas(CELL_W, CELL_H)
    b = Body(p)
    draw_ring(cv, p.ring, t)
    draw_roots(cv, b)
    draw_arm(cv, b, 1, p.hand_b, p.finger, back=True)
    draw_stem(cv, b)
    draw_veil(cv, b)
    eye = draw_cap(cv, b)
    draw_arm(cv, b, -1, p.hand_f, p.finger, back=False)
    draw_babies(cv, b)
    draw_root_wave(cv, b, p.roots, p.roots_fade)
    outline(cv, OUTLINE)
    # lights
    e = p.eye * (1 - p.rot)
    if e > 0.05:
        cv.glow(eye[0], eye[1], 7 + 3 * e, TOX[1], 0.4 * e)
    if p.glow > 0.05 and p.rot < 0.6:
        gx, gy = b.to_cell(0, RIM_H - 6)
        cv.glow(gx, gy, 16 + 6 * p.glow, TOX[0], 0.35 * p.glow * (1 - p.rot), halo=False)
    draw_spore_blast(cv, b, p.spores, p.spores_fade, t)
    for (mx, my, lv) in p.motes:
        cv.put(mx, my, SPORE[lv] if lv < 4 else TOX[2], solid=False)
    flash(cv, p.flash)
    if p.dissolve > 0:
        dissolve(cv, p.dissolve, GROUND - RIM_H - CAP_B - 6, GROUND + 2, TOX[3], TOX[1], upward=False)
    return cv


# ---------------------------------------------------------------- animations
IDLE_FRAMES = 14


def idle_pose(i: int, n: int = IDLE_FRAMES) -> Pose:
    a = math.tau * i / n
    breath = math.sin(a)
    return Pose(
        dy=0, lean=round(1.5 * math.sin(a + 0.6)), sy=1.0 + 0.012 * breath, sx=1.0 - 0.008 * breath,
        cap_s=1.0 + 0.035 * math.sin(a - 0.5), phase=a, sway=1.0,
        hand_f=(-30 + 1.5 * math.sin(a + 1.0), 33 + 2 * math.sin(a + 0.3)),
        hand_b=(27 + 1.2 * math.sin(a + 2.0), 35 + 1.6 * math.sin(a + 1.1)),
        finger=0.4 + 0.15 * math.sin(a + 2.4), eye=0.85 if i == 9 else 1.0,
        glow=0.75 + 0.25 * math.sin(2 * a),
    )


def idle_frames():
    return [(idle_pose(i), 115) for i in range(IDLE_FRAMES)]


def attack_frames():
    """Raíces Estranguladoras: rear up, slam, a root wave runs to the hero."""
    b = idle_pose(0)
    return [
        (replace(b, lean=5, sy=1.04, sx=0.97, cap_s=1.04, hand_f=(-22, 50), hand_b=(30, 50),
                 finger=0.8, eye=1.2, phase=0.4), 100),
        (replace(b, lean=9, sy=1.08, sx=0.94, cap_s=1.06, hand_f=(-14, 66), hand_b=(26, 64),
                 finger=1.0, eye=1.45, glow=1.2, phase=0.8), 130),
        (replace(b, lean=-12, sy=0.9, sx=1.07, cap_s=0.96, hand_f=(-44, 8), hand_b=(16, 14),
                 finger=1.0, eye=1.5, glow=1.3, phase=1.4, roots=0.35), 60),
        (replace(b, lean=-14, sy=0.9, sx=1.08, cap_s=0.97, hand_f=(-46, 4), hand_b=(14, 12),
                 finger=0.9, eye=1.4, glow=1.2, phase=1.9, roots=0.75), 65),
        (replace(b, lean=-12, sy=0.93, sx=1.05, hand_f=(-44, 8), hand_b=(16, 16), eye=1.3,
                 phase=2.4, roots=1.0), 90),
        (replace(b, lean=-8, sy=0.97, hand_f=(-40, 18), eye=1.15, phase=3.0, roots=1.0,
                 roots_fade=0.5), 90),
        (replace(b, lean=-4, sy=0.99, hand_f=(-35, 26), phase=3.7, roots=1.0, roots_fade=0.9), 90),
        (replace(b, lean=-1, hand_f=(-31, 31), phase=4.6), 95),
        (b, 110),
    ]


def spores_frames():
    """Lluvia de Esporas: the cap inflates, then blasts a spore cloud forward."""
    b = idle_pose(0)
    out = [
        (replace(b, lean=3, cap_s=1.08, sy=1.02, hand_f=(-26, 40), hand_b=(30, 44), eye=1.15,
                 glow=1.1, phase=0.3), 100),
        (replace(b, lean=5, cap_s=1.16, sy=1.04, hand_f=(-24, 46), hand_b=(31, 48), eye=1.3,
                 glow=1.3, phase=0.6), 110),
        (replace(b, lean=6, cap_s=1.2, sy=1.05, hand_f=(-22, 50), hand_b=(31, 50), eye=1.4,
                 glow=1.45, phase=0.9), 90),
    ]
    blast = [0.2, 0.42, 0.62, 0.8, 0.95, 1.0, 1.0]
    for k, s in enumerate(blast):
        cap = 0.86 + 0.14 * smooth(k / (len(blast) - 1))
        out.append((replace(b, lean=-6 + k, cap_s=cap, sy=0.97 + 0.004 * k,
                            hand_f=(-38 + k, 30), hand_b=(28, 36), eye=1.4 - 0.06 * k,
                            glow=1.3 - 0.07 * k, phase=1.2 + 0.45 * k, spores=s,
                            spores_fade=max(0.0, (k - 3) / 3.5)), 70 if k < 2 else 85))
    out += [(replace(b, lean=-1, phase=5.0, hand_f=(-31, 32)), 90), (b, 110)]
    return out


def cast_frames():
    """Brote de Moho: gills blaze, a mould ring grows on the floor."""
    b = idle_pose(0)
    out = []
    ups = [0.0, 0.35, 0.7, 1.0, 1.0, 1.0, 0.8, 0.5, 0.2]
    for k, u in enumerate(ups):
        out.append((replace(
            b, dy=-round(2 * u), cap_s=1.0 + 0.08 * u, hand_f=(-30 - 6 * u, 34 + 18 * u),
            hand_b=(27 + 6 * u, 36 + 18 * u), finger=0.4 + 0.6 * u, eye=1.0 + 0.45 * u,
            glow=0.8 + 0.6 * u, ring=min(1.0, k / 3) if k < 7 else u, phase=0.5 * k), 85))
    out.append((b, 110))
    return out


def hurt_frames():
    b = idle_pose(0)
    return [
        (replace(b, lean=6, sx=1.07, sy=0.92, cap_s=0.94, flash=0.85, eye=0.4, finger=1.0,
                 hand_f=(-24, 40), phase=1.4), 55),
        (replace(b, lean=8, sx=1.04, sy=0.95, cap_s=1.04, flash=0.6, eye=0.6, finger=0.9,
                 hand_f=(-22, 38), phase=2.1), 60),
        (replace(b, lean=5, sx=1.0, sy=1.02, cap_s=0.98, flash=0.25, eye=0.8, phase=2.8), 70),
        (replace(b, lean=3, sy=0.99, cap_s=1.02, phase=3.5), 70),
        (replace(b, lean=1, phase=4.3), 85),
        (b, 100),
    ]


def death_frames():
    b = idle_pose(0)
    out = [
        (replace(b, lean=6, sx=1.06, sy=0.93, flash=0.85, eye=0.5, finger=1.0, hand_f=(-24, 46),
                 hand_b=(30, 48)), 70),
        (replace(b, lean=4, sy=1.05, flash=0.35, eye=1.8, glow=1.5, cap_s=1.08, finger=1.0,
                 hand_f=(-28, 60), hand_b=(31, 62), phase=0.8), 100),
        (replace(b, lean=2, sy=1.04, eye=1.6, glow=1.4, cap_s=1.04, finger=0.8,
                 hand_f=(-30, 56), hand_b=(31, 58), phase=1.4), 90),
    ]
    steps = 11
    for k in range(steps):
        u = (k + 1) / steps
        wilt = smooth(min(1.0, u * 1.6))
        motes = tuple(
            (CX - 40 + hash01(k, j, 9) * 80, GROUND - 90 * (1 - u * 0.7) - hash01(j, k, 4) * 30 + u * 20,
             1 + int(hash01(j, k, 2) * 3) + (1 if j % 4 == 0 else 0))
            for j in range(8 + k))
        out.append((replace(b, lean=10 * wilt, sy=1.0 - 0.32 * wilt, sx=1.0 + 0.1 * wilt,
                            droop=wilt, cap_s=1.0 - 0.1 * wilt, eye=1.4 * (1 - wilt),
                            glow=0.9 * (1 - wilt), rot=wilt, finger=0.1,
                            hand_f=(-30, 30 - 18 * wilt), hand_b=(28, 30 - 18 * wilt),
                            phase=1.6 + 0.3 * k,
                            dissolve=0.0 if u < 0.35 else min(1.0, (u - 0.35) / 0.65),
                            motes=motes), 85))
    out.append((replace(b, dissolve=1.0), 120))
    return out


ANIMATIONS = {
    "idle": (idle_frames, True),
    "attack": (attack_frames, False),
    "spores": (spores_frames, False),
    "cast": (cast_frames, False),
    "hurt": (hurt_frames, False),
    "death": (death_frames, False),
}

# Frames where a hit lands (attack: the root wave reaches the edge; spores: the cloud arrives).
EVENTS = {"attack": {"strikes": [3]}, "spores": {"strikes": [6]}}
# Boss move id -> animation (the combat screen falls back to attack / cast).
MOVES = {"roots": "attack", "spores": "spores", "bloom": "spores", "mold": "cast"}


def build():
    return build_sheet(ANIMATIONS, render, (CELL_W, CELL_H), ANCHOR, f"{SHEET_ID}_sheet.png",
                       {"events": EVENTS, "moves": MOVES, "boss": True})


def main() -> None:
    sheet, meta = build()
    save_sheet(OUT_DIR, SHEET_ID, sheet, meta)
    print(f"wrote assets/enemies/{SHEET_ID}_sheet.png ({len(sheet[0])}x{len(sheet)}) and .json")


if __name__ == "__main__":
    main()
