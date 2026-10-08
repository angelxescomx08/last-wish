"""Draw and animate the enemy "Seta Explosiva" (a bomb mushroom). Stdlib only:

    python scripts/generate_enemy_bomb.py

Same method as the Espectro (``docs/code-drawn-sprites.md``): one renderer, every
frame a ``Pose``. The creature is a squat walking toadstool that is also a bomb:

* a round, glossy slate-teal cap shaped like a cannonball bomb, with pale warning
  spots and pressure cracks that glow orange (white-hot before it blows);
* an iron collar on top holding a twisted FUSE whose tip sputters and throws sparks;
* a fat pale stalk-body on two stubby feet; under the cap rim, in its shadow, two
  nervous beady eyes with worried brows and a clenched, grimacing mouth.

Animations (only ``idle`` loops; non-terminal actions end on idle frame 0):
  idle     12-frame nervous loop: breathing squash, jitter, darting eyes, fuse sparks, cracks pulse
  attack   crouch, hop LEFT and headbutt with a puff (rarely used)
  cast     "Soltar Esporas" / "Hincharse": the cap inflates, puffs an orange spore cloud, deflates
  explode  "Detonación" (TERMINAL): swells, shakes, cracks blaze, the fuse burns down, BOOM:
           white flash, fireball and debris thrown left, smoke ring, smoke clears -> empty
  hurt     white flash, squash, the spark flares, knocked right
  death    killed without a boom: the fuse fizzles, the cap deflates and droops, it wilts
           and crumbles into dull spores -> empty

Output: ``assets/enemies/bomb_sheet.png`` + ``.json`` (``events.<anim>.strikes``,
``moves`` and ``terminal: ["explode"]``).
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
SHEET_ID = "bomb"

CELL_W, CELL_H = 160, 108
CX, GROUND = CELL_W - 48, 100     # body centre line, ground row
ANCHOR = (CX, GROUND + 2)
RIM_H = 20                        # height of the cap's bottom rim above the ground
CAP_A, CAP_B = 21.0, 17.0         # cap half-width and half-height (a round bomb)
CAP_CUT = 0.72                    # the cap is cut flat this far below its centre (in B units)
TERMINAL = ("explode",)

# ---------------------------------------------------------------- palette
OUTLINE = (12, 13, 22)
CAP = [(16, 20, 32), (26, 36, 50), (38, 54, 66), (54, 76, 84), (78, 104, 108), (112, 138, 136),
       (168, 190, 182)]
STALK = [(54, 38, 52), (92, 72, 76), (138, 116, 104), (184, 164, 136), (220, 206, 174),
         (244, 236, 210)]
SPOT = [(120, 112, 100), (190, 180, 150), (234, 226, 196), (252, 248, 228)]
EMBER = [(92, 24, 16), (178, 64, 18), (246, 140, 36), (255, 214, 110), (255, 250, 214)]
FUSE = [(36, 22, 18), (76, 50, 32), (124, 90, 54), (172, 136, 86)]
IRON = [(28, 28, 36), (62, 60, 68), (108, 104, 108), (160, 154, 150)]
SPORE = [(120, 62, 26), (196, 116, 38), (240, 178, 64), (255, 232, 150)]
DULL = [(70, 62, 56), (104, 96, 84), (140, 132, 112), (176, 168, 146)]
SMOKE = [(44, 38, 46), (72, 64, 70), (104, 96, 96), (140, 132, 126), (180, 172, 160)]
EYE = [(176, 160, 140), (236, 226, 200)]
PUPIL = (18, 12, 22)
MOUTH = (46, 14, 20)
WILT = (86, 78, 70)
WHITE = (255, 255, 255)

# warning spots on the cap (sphere coords nx, ny, radius)
SPOTS = [(-0.46, -0.42, 0.21), (0.30, -0.62, 0.15), (0.60, -0.10, 0.19), (-0.12, -0.02, 0.15),
         (-0.76, 0.12, 0.12), (0.30, 0.30, 0.13), (-0.40, 0.36, 0.10)]
# pressure cracks (sphere coords); the last ones only show when it is about to blow
CRACKS = [
    [(0.06, -0.94), (-0.06, -0.78), (0.05, -0.64), (-0.08, -0.48), (-0.02, -0.34)],
    [(-0.70, -0.40), (-0.58, -0.24), (-0.66, -0.08), (-0.54, 0.06)],
    [(0.48, -0.66), (0.62, -0.46), (0.52, -0.30), (0.70, -0.16)],
    [(-0.26, 0.10), (-0.12, 0.22), (-0.22, 0.40)],
    [(0.20, -0.20), (0.34, 0.02), (0.20, 0.14), (0.38, 0.40)],
]


@dataclass(frozen=True)
class Pose:
    dx: float = 0.0
    dy: float = 0.0
    lean: float = 0.0             # cap offset (negative = towards the hero)
    sx: float = 1.0               # squash / stretch about the ground
    sy: float = 1.0
    cap_s: float = 1.0            # cap inflation
    droop: float = 0.0            # deflated, drooping cap (death)
    wilt: float = 0.0             # colours fade to grey-brown (death)
    phase: float = 0.0
    eye: float = 1.0              # 0 squeezed shut, 1 normal, 2 wide open
    look: int = 0                 # pupils: -1 left (hero), 0, 1 right
    mouth: float = 0.0            # 0 clenched grimace .. 2 screaming
    cracks: float = 0.8           # crack glow level 0..3+ (3 = white-hot)
    heat: float = 0.0             # whole cap heats towards orange (before the boom)
    fuse: float = 1.0             # fuse length left 0..1
    spark: float = 1.0            # fuse spark size 0 (out) .. 2.5 (flare)
    smoke: float = 0.0            # smoke puff from a fizzled fuse
    flash: float = 0.0
    dissolve: float = 0.0
    gone: bool = False            # body not drawn (after the boom)
    boom: float = 0.0             # explosion progress 0..1
    spores: float = 0.0           # spore cloud progress (cast)
    spores_fade: float = 0.0
    puff: float = 0.0             # headbutt puff (attack)
    motes: tuple = field(default_factory=tuple)


class Body:
    def __init__(self, p: Pose) -> None:
        self.p = p

    def center(self, h: float) -> float:
        k = max(0.0, min(1.0, h / (RIM_H + 2 * CAP_B)))
        return CX + self.p.dx + self.p.lean * k ** 1.2

    def y_of(self, h: float) -> float:
        return GROUND + self.p.dy - h * self.p.sy

    def h_of(self, y: float) -> float:
        return (GROUND + self.p.dy - y) / self.p.sy

    def rim_h(self) -> float:
        return RIM_H * (1 - 0.22 * self.p.droop)


def _w(c, p: Pose):
    """Wilt a colour (death)."""
    return mix(c, WILT, p.wilt * 0.7) if p.wilt > 0 else c


def _clamp(v: float) -> float:
    return max(0.0, min(1.0, v))


# ---------------------------------------------------------------- body
def stalk_hw(h: float) -> float:
    if h < 0:
        return 0.0
    t = min(1.0, h / RIM_H)
    hw = 11.0 + 3.4 * math.sin(t * math.pi * 0.8)
    if h < 4:                                    # rounded bottom
        hw *= 0.8 + 0.2 * h / 4
    return hw


def draw_feet(cv: Canvas, b: Body) -> None:
    p = b.p
    for lx, rx, shade in ((8.5, 6.5, -0.2), (-9.5, 7.2, 0.0)):    # back foot first
        fx = CX + p.dx + lx * p.sx - 1.5
        fy = b.y_of(2.6)
        ry = 3.3
        for y in range(int(fy - ry) - 1, int(fy + ry) + 2):
            for x in range(int(fx - rx) - 1, int(fx + rx) + 2):
                u, v = (x + 0.5 - fx) / rx, (y + 0.5 - fy) / ry
                if u * u + v * v > 1 or y > GROUND:
                    continue
                light = 0.62 - 0.35 * u - 0.35 * v + shade
                cv.put(x, y, _w(ramp(STALK[:-1], _clamp(light), x, y), p))
        # a toe crease
        cv.put(int(fx - rx * 0.45), int(fy + 1), _w(STALK[1], p))


def draw_stalk(cv: Canvas, b: Body) -> None:
    p = b.p
    top = b.rim_h() + 5
    for y in range(CELL_H):
        h = b.h_of(y + 0.5)
        if h < 0 or h > top:
            continue
        c = b.center(h)
        hw = stalk_hw(h) * p.sx
        for x in range(int(c - hw) - 1, int(c + hw) + 2):
            dxp = x + 0.5 - c
            if abs(dxp) > hw:
                continue
            u = dxp / hw
            light = 0.86 - 0.42 * u - 0.30 * (1 - h / RIM_H) ** 2
            if abs(u) > 0.84:
                light -= 0.16
            if u < -0.74 and 6 < h < b.rim_h() - 6:
                light += 0.12                                   # rim light on the lit side
            shadow = b.rim_h() - 7
            if h > shadow:                                      # the cap's shadow
                light -= 0.95 * smooth((h - shadow) / 4.5)
            col = ramp(STALK, _clamp(light), x, y)
            if hash01(x, int(h / 2.5), 11) > 0.94 and 4 < h < shadow:    # fibres
                col = mix(col, STALK[1], 0.4)
            cv.put(x, y, _w(col, p))


def draw_face(cv: Canvas, b: Body) -> None:
    p = b.p
    eh = b.rim_h() - 5
    ey = int(round(b.y_of(eh)))
    cxf = b.center(eh) - 1.5
    w = 1.0 + 0.06 * (p.sx - 1)
    eyes = (int(round(cxf - 5.5 * w)), int(round(cxf + 4.0 * w)))
    e = p.eye * (1 - p.wilt * 0.6)
    for k, ex in enumerate(eyes):
        inner = 1 if k == 0 else -1                     # direction towards the nose
        if e < 0.2:                                     # squeezed shut: > <
            for ox, oy in ((-1, -1), (0, 0), (1, 1)) if p.eye < 0.1 else ((-1, 0), (0, 0), (1, 0)):
                cv.put(ex + ox * inner, ey + oy, OUTLINE)
            continue
        if e > 1.45:                                    # terror: white eyes, pinprick pupils
            for oy in range(-2, 2):
                for ox in (-1, 0, 1):
                    if abs(ox) == 1 and oy in (-2, 1):
                        continue
                    cv.put(ex + ox, ey + oy, _w(EYE[1] if oy < 1 else EYE[0], p))
            for ox, oy in ((-2, -1), (-2, 0), (2, -1), (2, 0), (-1, -3), (0, -3), (1, -3),
                           (-1, 2), (0, 2), (1, 2), (-2, -2), (2, -2), (-2, 1), (2, 1)):
                cv.put(ex + ox, ey + oy, OUTLINE)
            cv.put(ex + p.look, ey, PUPIL)
        else:                                           # beady: dark bead with a glint
            for oy in (-1, 0, 1):
                for ox in (0, 1):
                    cv.put(ex + ox + min(0, p.look), ey + oy, PUPIL)
            bx = ex + min(0, p.look)
            cv.put(bx, ey - 1, WHITE if p.wilt < 0.4 else EYE[0])
            cv.put(bx + 1, ey + 1, (70, 40, 50))
        # worried brows (inner end up)
        lift = 2 if e > 1.45 else 0
        cv.put(ex - inner * 2, ey - 2 - lift, OUTLINE)
        cv.put(ex - inner, ey - 3 - lift, OUTLINE)
        cv.put(ex, ey - 3 - lift, OUTLINE)
        cv.put(ex + inner, ey - 4 - lift, OUTLINE)
    # grimacing mouth with clenched teeth
    mh = b.rim_h() - 11
    my = int(round(b.y_of(mh)))
    mx0 = int(round(cxf - 6))
    gap = 0 if p.mouth < 0.5 else 1 if p.mouth < 1.4 else 3
    width = 11
    for i in range(width):
        x = mx0 + i
        corner = 1 if i in (0, width - 1) else 0
        y0 = my + corner
        cv.put(x, y0 - 1, OUTLINE)
        if corner:
            continue
        tooth = EYE[1] if i % 2 else EYE[0]
        if p.mouth < 0.5:
            cv.put(x, y0, _w(tooth if i % 3 else OUTLINE, p))
        else:
            cv.put(x, y0, _w(tooth, p))
            for g in range(gap):
                cv.put(x, y0 + 1 + g, MOUTH if g < gap - 1 or i % 4 else (120, 40, 40))
            cv.put(x, y0 + 1 + gap, _w(EYE[0] if i % 2 else STALK[3], p))
        cv.put(x, y0 + (2 + gap if p.mouth >= 0.5 else 1), OUTLINE)
    cv.put(mx0 - 1, my + 1, OUTLINE)
    cv.put(mx0 + width, my + 1, OUTLINE)


# ---------------------------------------------------------------- cap
class CapGeo:
    def __init__(self, b: Body) -> None:
        p = b.p
        self.A = CAP_A * p.sx * p.cap_s * (1 + 0.12 * p.droop)
        self.B = CAP_B * p.sy * p.cap_s * (1 - 0.45 * p.droop)
        rim_y = b.y_of(b.rim_h())
        self.cut = CAP_CUT + 0.15 * p.droop
        self.ccy = rim_y - self.cut * self.B
        self.ccx = b.center(b.rim_h() + self.B) + p.lean * 0.25

    def cell(self, nx: float, ny: float) -> tuple[float, float]:
        return self.ccx + nx * self.A, self.ccy + ny * self.B

    def cut_line(self, nx: float, droop: float) -> float:
        return self.cut + droop * 0.55 * nx * nx


def draw_cap(cv: Canvas, b: Body) -> CapGeo:
    p = b.p
    g = CapGeo(b)
    A, B = g.A, g.B
    L = (-0.55, -0.62, 0.56)
    for y in range(int(g.ccy - B) - 1, int(g.ccy + B * 1.4) + 2):
        for x in range(int(g.ccx - A) - 1, int(g.ccx + A) + 2):
            nx, ny = (x + 0.5 - g.ccx) / A, (y + 0.5 - g.ccy) / B
            r2 = nx * nx + ny * ny
            if r2 > 1:
                continue
            cut = g.cut_line(nx, p.droop)
            if ny > cut:
                continue
            nz = math.sqrt(1 - r2)
            dot = L[0] * nx + L[1] * ny + L[2] * nz
            light = 0.10 + 0.82 * max(0.0, dot)
            light += 0.06 * math.cos(nx * 7 + ny * 4 + 0.4 * math.sin(p.phase))
            if nx > 0.55 and ny > -0.2:
                light += 0.06                                    # warm bounce from the room
            if (cut - ny) * B < 1.3:
                col = CAP[1]                                     # rolled under-lip
            elif (cut - ny) * B < 2.5:
                col = CAP[3] if nx < 0.3 else CAP[2]             # lit lip of the rim
            else:
                col = ramp(CAP[:-1], _clamp(light), x, y)
                if dot > 0.93 and p.droop < 0.5:
                    col = CAP[6]                                 # glossy highlight
            if p.heat > 0:
                hot = EMBER[0] if p.heat < 0.5 else EMBER[1]
                col = mix(col, hot, p.heat * (0.3 + 0.35 * nz))
            cv.put(x, y, _w(col, p))
    # warning spots (foreshortened on the sphere)
    for sx_, sy_, r in SPOTS:
        nz0 = math.sqrt(max(0.0, 1 - sx_ * sx_ - sy_ * sy_))
        sy2 = sy_ + p.droop * 0.3 * sx_ * sx_
        cx_, cy_ = g.cell(sx_, sy2)
        rx, ry = r * A * (0.55 + 0.45 * nz0), r * B
        for y in range(int(cy_ - ry) - 1, int(cy_ + ry) + 2):
            for x in range(int(cx_ - rx) - 1, int(cx_ + rx) + 2):
                d = math.hypot((x + 0.5 - cx_) / max(0.8, rx), (y + 0.5 - cy_) / max(0.8, ry))
                if d > 1 or cv.get(x, y) is None:
                    continue
                ny = (y + 0.5 - g.ccy) / B
                if ny > g.cut_line((x + 0.5 - g.ccx) / A, p.droop) - 2.5 / B:
                    continue
                lvl = 0.75 - 0.35 * (x + 0.5 - cx_) / max(1.0, rx) - 0.25 * (y + 0.5 - cy_) / max(1.0, ry)
                lvl -= 0.25 * max(0.0, sx_) + 0.2 * max(0.0, sy_)
                col = ramp(SPOT, _clamp(lvl), x, y, 0.4) if d < 0.8 else SPOT[0]
                if p.heat > 0:
                    col = mix(col, EMBER[3], p.heat * 0.5)
                cv.put(x, y, _w(col, p))
    return g


def crack_pixels(g: CapGeo, p: Pose):
    """Jagged crack pixels on the cap (cell coords), longer as the pressure grows."""
    out, seen = [], set()
    n = 3 if p.cracks < 1.5 else 4 if p.cracks < 2.3 else 5
    reach = _clamp(0.55 + 0.25 * p.cracks)
    for ci, path in enumerate(CRACKS[:n]):
        pts = [g.cell(nx, ny + p.droop * 0.3 * nx * nx) for nx, ny in path]
        total = len(pts) - 1
        seg_len = total * (reach if ci < 3 else _clamp(p.cracks - 1.5 - 0.5 * (ci - 3)))
        for s in range(total):
            if s >= seg_len:
                break
            (x0, y0), (x1, y1) = pts[s], pts[s + 1]
            frac = min(1.0, seg_len - s)
            n = max(1, int(math.hypot(x1 - x0, y1 - y0) * 2.5))
            for i in range(int(n * frac) + 1):
                q = (int(x0 + (x1 - x0) * i / n), int(y0 + (y1 - y0) * i / n))
                if q not in seen:
                    seen.add(q)
                    out.append(q)
    return out


def draw_cracks(cv: Canvas, g: CapGeo, p: Pose) -> list:
    pix = [(x, y) for x, y in crack_pixels(g, p) if cv.get(x, y) is not None]
    c = p.cracks * (1 - p.wilt)
    if c <= 0.05:
        for x, y in pix:
            cv.put(x, y, _w(CAP[0], p))
        return pix
    core = EMBER[0] if c < 0.45 else EMBER[1] if c < 1.0 else EMBER[2] if c < 1.8 else EMBER[3] if c < 2.6 else EMBER[4]
    edge = EMBER[0] if c < 1.0 else EMBER[1] if c < 2.0 else EMBER[2]
    pset = set(pix)
    for x, y in pix:
        if (x + 1, y + 1) not in pset and cv.get(x + 1, y + 1) is not None:
            cv.put(x + 1, y + 1, _w(CAP[0], p))
    for x, y in pix:
        cv.put(x, y, core)
        if c > 1.2:
            for ox, oy in ((1, 0), (0, 1)):
                if cv.get(x + ox, y + oy) is not None and (x + ox, y + oy) not in pset:
                    cv.tint(x + ox, y + oy, edge, 0.55)
    return pix


# ---------------------------------------------------------------- fuse + spark
def draw_fuse(cv: Canvas, b: Body, g: CapGeo) -> tuple[float, float]:
    p = b.p
    bx, by = g.cell(0.10, -0.97 + p.droop * 0.1)
    bx, by = round(bx), round(by)
    # iron collar
    for y in range(by - 2, by + 1):
        for x in range(bx - 2, bx + 3):
            u = (x - bx) / 2.5
            light = 0.7 - 0.45 * u - (0.25 if y == by else 0)
            cv.put(x, y, _w(ramp(IRON, _clamp(light), x, y, 0.3), p))
    cv.put(bx - 2, by - 2, _w(IRON[3], p))
    if p.fuse <= 0.02:
        return bx, by - 3
    L = 8.0 * p.fuse
    sway = 1.3 * math.sin(p.phase) * p.fuse + p.dx * 0 - p.lean * 0.15
    droop = p.droop * 5
    p0 = (bx + 0.5, by - 2.5)
    p1 = (bx + 4.0 * p.fuse + droop * 0.6, by - 2.5 - 0.55 * L + droop * 0.5)
    p2 = (bx + 1.5 * p.fuse + sway + droop * 1.4, by - 2.5 - L + droop * 1.6)
    pts = bezier(p0, p1, p2, max(3, int(L * 2)))
    tube = stroke(cv, pts, lambda t: 1.05, FUSE, rim=OUTLINE, dither=0.3)
    for y in range(max(0, int(p2[1]) - 3), min(CELL_H, by)):
        for x in range(max(0, bx - 4), min(CELL_W, bx + 10)):
            if tube.px[y][x] is not None and (x - y) % 3 == 0:
                cv.put(x, y, _w(FUSE[0], p))                         # twisted cord
    tx, ty = pts[-1]
    if p.spark > 0.05 and p.wilt < 0.3:
        cv.put(tx, ty, FUSE[0])
        cv.put(tx, ty + 1, EMBER[1])                                 # burning end
    return tx, ty - 1


def draw_spark(cv: Canvas, tip, p: Pose) -> None:
    s = p.spark
    if s <= 0.05:
        return
    tx, ty = int(round(tip[0])), int(round(tip[1]))
    f = 0.8 + 0.2 * math.sin(3 * p.phase) + 0.12 * math.sin(7 * p.phase + 1.0)
    k = s * f
    cv.glow(tx + 0.5, ty + 0.5, 4 + 3.5 * k, EMBER[2], 0.45 + 0.2 * k)
    arm = int(round(0.6 + 1.3 * k))
    for i in range(1, arm + 1):
        col = EMBER[3] if i == 1 else EMBER[2] if i < arm else EMBER[1]
        for ox, oy in ((i, 0), (-i, 0), (0, -i), (0, i)):
            cv.put(tx + ox, ty + oy, col, solid=False)
    if k > 0.75:
        diag = 1 if k < 1.6 else 2
        for i in range(1, diag + 1):
            for ox, oy in ((i, i), (-i, i), (i, -i), (-i, -i)):
                cv.put(tx + ox, ty + oy, EMBER[2] if i == 1 else EMBER[1], solid=False)
    cv.put(tx, ty, WHITE, solid=False)
    if k > 0.5:
        cv.put(tx + 1, ty, EMBER[4], solid=False)
    # thrown sparks (periodic in phase: an integer number of bursts per loop)
    n = 4 if s < 1.8 else 7
    for j in range(n):
        age = (p.phase / math.tau * 2 + j / n) % 1.0
        if age > 0.85:
            continue
        ang = -math.pi / 2 + (hash01(j, 3, 21) - 0.55) * 2.6
        dist = (2 + 9 * age) * (0.7 + 0.3 * s)
        x = tx + math.cos(ang) * dist
        y = ty + math.sin(ang) * dist + 7 * age * age
        col = WHITE if age < 0.15 else EMBER[3] if age < 0.4 else EMBER[2] if age < 0.65 else EMBER[1]
        cv.put(x, y, col, solid=False)
        if age < 0.45:                                              # short trail
            cv.put(x - math.cos(ang), y - math.sin(ang) + 0.5, EMBER[1], solid=False, alpha=170)


def draw_smoke(cv: Canvas, tip, p: Pose) -> None:
    """A grey puff from a fizzled fuse, rising and spreading."""
    s = p.smoke
    if s <= 0:
        return
    for k in range(4):
        lead = s * 1.2 - k * 0.18
        if lead <= 0:
            continue
        lead = min(1.0, lead)
        x = tip[0] + (k - 1.5) * 2 - lead * 4 * math.sin(k + 1)
        y = tip[1] - 2 - lead * (10 + 4 * k)
        r = 1.5 + 3.5 * lead
        a = 1 - lead ** 2 * 0.8
        for yy in range(int(y - r) - 1, int(y + r) + 2):
            for xx in range(int(x - r) - 1, int(x + r) + 2):
                d = math.hypot(xx + 0.5 - x, yy + 0.5 - y) / r
                if d > 1 or bayer(xx, yy) > (1.3 - d) * a:
                    continue
                cv.put(xx, yy, SMOKE[3] if d < 0.5 and yy < y else SMOKE[2], solid=False, alpha=210)


# ---------------------------------------------------------------- effects
def _cloud(cv: Canvas, x: float, y: float, r: float, a: float, pal) -> None:
    for yy in range(int(y - r) - 1, int(y + r) + 2):
        for xx in range(int(x - r) - 1, int(x + r) + 2):
            d = math.hypot(xx + 0.5 - x, yy + 0.5 - y) / max(0.5, r)
            if d > 1 or bayer(xx, yy) > (1.5 - d) * a * 1.4:
                continue
            ly = (yy + 0.5 - y) / r + (xx + 0.5 - x) / r * 0.5
            lvl = 3 if d < 0.35 and ly < 0 else 2 if d < 0.68 else 1 if d < 0.9 else 0
            cv.put(xx, yy, pal[lvl], solid=False, alpha=int(255 * min(1.0, a + 0.25)))


def draw_spores(cv: Canvas, b: Body, prog: float, fade: float) -> None:
    """Orange-yellow spore cloud puffed out of the cap, drifting up and left."""
    if prog <= 0:
        return
    ox, oy = CX + b.p.dx - 4, b.y_of(RIM_H + 2 * CAP_B) + 4
    for k in range(12):
        lead = prog * 1.6 - (k % 6) * 0.1 - (k // 6) * 0.15
        if lead <= 0:
            continue
        lead = min(1.0, lead)
        h1, h2 = hash01(k, 1, 5), hash01(k, 3, 5)
        ang = -math.pi / 2 - 0.15 - 1.35 * h1
        dist = lead * (10 + 26 * hash01(k, 2, 5))
        x = ox + math.cos(ang) * dist - lead * 12
        y = oy + math.sin(ang) * dist * 0.7 + 6 * lead * lead
        r = 3 + 7 * lead * (0.6 + 0.4 * h2)
        a = (1 - fade) * (1 - max(0.0, lead - 0.85) * 3)
        if a > 0:
            _cloud(cv, x, y, r, a, SPORE)
    for j in range(20):                                         # specks
        s = prog * 1.3 - hash01(j, 9, 5) * 0.4
        if s <= 0 or fade > 0.9:
            continue
        x = ox - s * 50 * (hash01(j, 4, 5) - 0.25)
        y = oy - s * 30 * hash01(j, 5, 5) + s * s * 10
        cv.put(x, y, SPORE[2 + (j % 2)], solid=False)


def draw_puff(cv: Canvas, b: Body, prog: float) -> None:
    """Headbutt impact: a small dusty spore puff and impact ticks to the left."""
    if prog <= 0:
        return
    hx, hy = CX + b.p.dx - CAP_A - 4, b.y_of(RIM_H + CAP_B * 0.7)
    a = 1 - smooth((prog - 0.4) / 0.6)
    for k in range(5):
        ang = math.pi + (k - 2) * 0.55
        d = 3 + 10 * prog
        _cloud(cv, hx + math.cos(ang) * d, hy + math.sin(ang) * d * 0.8, 2 + 3 * prog, a, SPORE)
    if prog < 0.6:
        for k in range(3):                                      # impact ticks
            y = hy - 6 + 6 * k
            for i in range(3):
                cv.put(hx - 12 - 6 * prog - i - abs(k - 1), y, EMBER[3] if i == 0 else EMBER[2], solid=False)


PUFFS = [(hash01(k, 1, 41), hash01(k, 2, 41), hash01(k, 3, 41)) for k in range(11)]
DEBRIS = [(hash01(k, 1, 31), hash01(k, 2, 31), hash01(k, 3, 31)) for k in range(16)]


def draw_explosion(cv: Canvas, e: float) -> None:
    """The detonation: white flash, a left-biased fireball, debris, smoke ring, smoke clearing."""
    if e <= 0:
        return
    bx, by = CX - 4, GROUND - 32
    # fireball / smoke cloud: a cluster of billowing puffs, left-biased
    grow = smooth(min(1.0, (e + 0.12) / 0.42))
    R = 12 + 28 * grow
    cx = bx - 14 * smooth(min(1.0, e / 0.6))
    cy = by - 1 - 12 * e
    heat = max(0.0, 1.1 - e * 1.6)
    fade = smooth((e - 0.45) / 0.55)
    puffs = [(cx, cy, R * 0.62)]
    for k, (h1, h2, h3) in enumerate(PUFFS):
        ox = (-1.05 + 1.55 * h1) * R
        oy = (-0.75 + 1.0 * h2) * R * 0.7 - 4 * e * h3
        puffs.append((cx + ox, min(GROUND - 4, cy + oy), R * (0.34 + 0.24 * h3)))
    shrink = 1 - 0.45 * fade
    alpha = int(255 * (1 - fade) ** 0.6) if fade > 0 else 255
    x_lo = max(0, int(min(px - r for px, _, r in puffs)) - 1)
    x_hi = min(CELL_W, int(max(px + r for px, _, r in puffs)) + 2)
    y_lo = max(0, int(min(py - r for _, py, r in puffs)) - 1)
    for y in range(y_lo, min(CELL_H, GROUND + 2)):
        for x in range(x_lo, x_hi):
            best = None
            for px, py, r in puffs:
                r *= shrink
                d = math.hypot(x + 0.5 - px, (y + 0.5 - py) / 0.85) / max(1.0, r)
                if d <= 1 and (best is None or d < best[0]):
                    best = (d, px, py, r)
            if best is None:
                continue
            d, px, py, r = best
            if d > 0.78 and fade > 0 and bayer(x, y) < fade * (d - 0.6) * 2.5:
                continue                                       # only the edges thin out
            dc = math.hypot(x + 0.5 - cx, (y + 0.5 - cy) / 0.8) / (R * 1.3)
            puff_l = -(x + 0.5 - px) / r - (y + 0.5 - py) / r            # lit upper-left
            tmp = heat * (1.3 - dc) + 0.12 * puff_l * heat - 0.15 * d
            if e < 0.12:
                tmp += 0.7
            if tmp > 1.0:
                col = EMBER[4]
            elif tmp > 0.82:
                col = EMBER[3]
            elif tmp > 0.62:
                col = EMBER[2]
            elif tmp > 0.45:
                col = EMBER[1]
            elif tmp > 0.33:
                col = EMBER[0]
            else:
                light = 0.55 + 0.3 * puff_l - 0.2 * d - 0.2 * e
                col = ramp(SMOKE, _clamp(light), x, y, 0.5)
                if heat > 0.05:                               # fire glow under the smoke
                    col = mix(col, EMBER[1], heat * 0.55 * _clamp((y + 0.5 - py) / r + 0.3))
            cv.put(x, y, col, solid=False, alpha=alpha)
    if e < 0.12:                                          # the white flash itself
        k = 1 - e / 0.12
        for y in range(int(by - 26), int(by + 26)):
            for x in range(int(bx - 30), int(bx + 26)):
                d = math.hypot(x + 0.5 - bx, (y + 0.5 - by) / 0.85) / 24
                if d < 1 and y <= GROUND and bayer(x, y) < (1.25 - d) * k * 1.3:
                    cv.put(x, y, WHITE if d < 0.7 else EMBER[3], solid=False)
    # white flash: rays and a hot core at the very start
    if e < 0.2:
        k = 1 - e / 0.2
        cv.glow(bx, by, 26 + 20 * (1 - k), EMBER[4], 0.9 * k)
        for i in range(10):
            ang = i / 10 * math.tau + 0.3
            ln = (16 + 18 * hash01(i, 4, 33)) * (1 + 0.6 * max(0.0, -math.cos(ang)))
            for s in range(int(ln * (0.4 + e * 3))):
                x, y = bx + math.cos(ang) * (8 + s), by + math.sin(ang) * (8 + s) * 0.8
                if y < GROUND + 1:
                    cv.put(x, y, WHITE if s < ln * 0.5 else EMBER[3], solid=False, alpha=int(255 * k))
    # smoke ring rolling along the floor, left-biased (a row of small puffs)
    if 0.08 < e < 0.9:
        ring = smooth((e - 0.08) / 0.6)
        rx = 12 + 56 * ring
        rcx = CX - 6 - 24 * ring
        a = 1 - smooth((e - 0.45) / 0.45)
        for i in range(21):
            ang = math.pi * (0.03 + 0.94 * i / 20)
            sx_ = rcx - math.cos(ang) * rx * (1 + 0.25 * max(0.0, math.cos(ang)))
            sy_ = GROUND - 2 + math.sin(ang) * 2.5 * ring
            pr = (3.0 + 4.5 * ring) * (0.75 + 0.5 * hash01(i, 5, 41))
            _cloud(cv, sx_, sy_ - pr * (0.3 + 0.5 * hash01(i, 6, 41)), pr, a * 0.85, SMOKE[:4])
            if e < 0.3:
                cv.put(sx_, sy_, EMBER[1], solid=False)
    # debris: bits of cap and stalk thrown mostly to the left
    if e < 0.95:
        tau = e * 1.15
        for k, (h1, h2, h3) in enumerate(DEBRIS):
            vx = -(28 + 62 * h1) if k % 5 else (14 + 20 * h1)
            vy = -(30 + 40 * h2)
            x = bx + (h3 - 0.5) * 14 + vx * tau
            y = by + (h2 - 0.5) * 10 + vy * tau + 85 * tau * tau
            landed = y >= GROUND
            y = min(y, GROUND)
            col = CAP[2 + (k % 3)] if k % 3 else STALK[3]
            size = 2 if k % 4 else 3
            alpha = 255 if e < 0.75 else int(255 * (1 - (e - 0.75) / 0.2))
            for oy in range(2):
                for ox in range(size):
                    cv.put(x + ox, y - oy, col if oy else mix(col, OUTLINE, 0.5), solid=False, alpha=alpha)
            if not landed and e < 0.45:                       # burning trail
                cv.put(x - vx * 0.04 + 1, y - vy * 0.04, EMBER[2], solid=False)
                cv.put(x - vx * 0.08 + 1, y - vy * 0.08, EMBER[1], solid=False, alpha=160)
    # embers drifting up
    if 0.1 < e < 0.9:
        for j in range(14):
            age = _clamp((e - 0.1) * 1.4 - hash01(j, 7, 33) * 0.3)
            x = bx - 50 * hash01(j, 8, 33) + 15 + 6 * math.sin(j + e * 6)
            y = by - 10 - 40 * age * (0.5 + hash01(j, 9, 33))
            if age <= 0 or age >= 1:
                continue
            cv.put(x, y, EMBER[3] if age < 0.4 else EMBER[2] if age < 0.7 else EMBER[1], solid=False)


# ---------------------------------------------------------------- render
def render(p: Pose, t: float = 0.0) -> Canvas:
    cv = Canvas(CELL_W, CELL_H)
    b = Body(p)
    tip = None
    pix = []
    g = None
    if not p.gone:
        draw_feet(cv, b)
        draw_stalk(cv, b)
        draw_face(cv, b)
        g = draw_cap(cv, b)
        pix = draw_cracks(cv, g, p)
        tip = draw_fuse(cv, b, g)
        outline(cv, OUTLINE)
        c = p.cracks * (1 - p.wilt)
        if c > 0.4:                                           # glowing cracks
            step = max(1, len(pix) // 10)
            for x, y in pix[::step]:
                cv.glow(x + 0.5, y + 0.5, 2.5 + 1.5 * min(c, 3.0), EMBER[2], 0.12 * min(c, 3.0), halo=False)
        if p.heat > 0.3:
            cv.glow(g.ccx, g.ccy, g.A, EMBER[3], 0.25 * p.heat, halo=False)
        draw_spark(cv, tip, p)
        draw_smoke(cv, tip, p)
    flash(cv, p.flash)
    if p.dissolve > 0:
        dissolve(cv, p.dissolve, GROUND - 64, GROUND + 2, DULL[3], DULL[1], upward=False, seed=7)
    draw_spores(cv, b, p.spores, p.spores_fade)
    draw_puff(cv, b, p.puff)
    draw_explosion(cv, p.boom)
    for mx, my, lv in p.motes:
        cv.put(mx, my, DULL[max(0, min(3, int(lv)))], solid=False)
    return cv


# ---------------------------------------------------------------- animations
IDLE_FRAMES = 12
_JITTER = (0, 0, 1, 0, 0, -1, 0, 0, 1, 0, 0, -1)
_LOOK = (0, 0, -1, -1, -1, 0, 1, 1, 0, -1, -1, 0)


def idle_pose(i: int, n: int = IDLE_FRAMES) -> Pose:
    i %= n
    a = math.tau * i / n
    breath = math.sin(a)
    return Pose(
        dx=_JITTER[i % len(_JITTER)] if n == IDLE_FRAMES else 0,
        sy=1.0 + 0.035 * breath, sx=1.0 - 0.022 * breath,
        cap_s=1.0 + 0.03 * math.sin(a - 0.7), lean=round(0.9 * math.sin(a + 1.2)),
        phase=a, eye=1.6 if i == 6 else 1.0, look=_LOOK[i % len(_LOOK)] if n == IDLE_FRAMES else 0,
        cracks=1.0 + 0.45 * math.sin(2 * a), spark=1.0,
    )


def idle_frames():
    return [(idle_pose(i), 110) for i in range(IDLE_FRAMES)]


def attack_frames():
    """A hop to the left and a headbutt with a puff."""
    b = idle_pose(0)
    return [
        (replace(b, sy=0.88, sx=1.08, cap_s=0.98, lean=2, eye=1.3, look=-1, mouth=0, spark=1.4,
                 phase=0.3), 100),
        (replace(b, sy=0.82, sx=1.12, cap_s=0.97, lean=3, eye=1.5, look=-1, spark=1.6, cracks=1.2,
                 phase=0.6), 110),
        (replace(b, dx=-9, dy=-9, sy=1.1, sx=0.93, lean=-3, eye=1.5, look=-1, mouth=1, phase=0.9), 60),
        (replace(b, dx=-20, sy=0.86, sx=1.14, lean=-6, eye=0.0, mouth=1, cracks=1.5, spark=1.8,
                 puff=0.35, phase=1.2), 55),
        (replace(b, dx=-19, sy=0.92, sx=1.08, lean=-4, eye=0.1, mouth=0, puff=0.7, phase=1.6), 65),
        (replace(b, dx=-16, sy=0.98, sx=1.02, lean=-2, eye=1.0, look=-1, puff=1.0, phase=2.0), 80),
        (replace(b, dx=-9, dy=-6, sy=1.06, sx=0.96, lean=1, phase=2.6), 90),
        (replace(b, dx=-2, sy=0.92, sx=1.06, lean=1, phase=3.4), 90),
        (replace(b, dx=0, sy=1.02, sx=0.99, phase=4.4), 90),
        (b, 100),
    ]


def cast_frames():
    """Soltar Esporas / Hincharse: inflate, puff a spore cloud, deflate."""
    b = idle_pose(0)
    return [
        (replace(b, cap_s=1.08, sy=1.04, sx=1.02, cracks=1.1, eye=1.3, spark=1.3, phase=0.3), 90),
        (replace(b, cap_s=1.17, sy=1.08, sx=1.04, cracks=1.5, eye=1.4, spark=1.5, phase=0.6), 100),
        (replace(b, cap_s=1.24, sy=1.1, sx=1.06, cracks=1.8, eye=1.6, spark=1.7, look=0, phase=0.9), 90),
        (replace(b, cap_s=1.0, sy=0.93, sx=1.07, cracks=1.4, eye=0.1, mouth=1, spores=0.22, phase=1.2), 60),
        (replace(b, cap_s=0.94, sy=0.95, sx=1.05, cracks=1.1, eye=0.8, mouth=1, spores=0.48, phase=1.6), 70),
        (replace(b, cap_s=0.97, sy=0.99, sx=1.02, cracks=0.9, spores=0.74, spores_fade=0.2, phase=2.2), 80),
        (replace(b, cap_s=1.0, sy=1.01, spores=0.92, spores_fade=0.5, phase=3.0), 90),
        (replace(b, spores=1.0, spores_fade=0.85, phase=4.0), 90),
        (b, 110),
    ]


def explode_frames():
    """Detonación (terminal): swell, shake, fuse burns down, BOOM, smoke clears -> empty."""
    b = idle_pose(0)
    out = []
    build = [(1.12, 1.6, 0.8, 1, 0.15, 110), (1.22, 2.0, 0.62, -1, 0.3, 100),
             (1.30, 2.4, 0.45, 2, 0.45, 90), (1.38, 2.8, 0.28, -2, 0.62, 80),
             (1.46, 3.2, 0.1, 1, 0.82, 70)]
    for k, (cs, cr, fu, sh, ht, ms) in enumerate(build):
        out.append((replace(b, cap_s=cs, sx=1.0 + 0.04 * (k + 1), sy=1.03 + 0.017 * (k + 1), dx=sh,
                            cracks=cr, fuse=fu, heat=ht, spark=1.5 + 0.2 * k, eye=2.0,
                            look=0, mouth=1 if k < 2 else 2,
                            phase=0.9 * (k + 1)), ms))
    for e, ms in ((0.04, 60), (0.14, 60), (0.26, 70), (0.4, 80), (0.55, 90), (0.7, 100),
                  (0.85, 110), (0.95, 110)):
        out.append((replace(b, gone=True, boom=e), ms))
    out.append((replace(b, gone=True, boom=0.0), 120))
    return out


def hurt_frames():
    b = idle_pose(0)
    return [
        (replace(b, dx=4, sx=1.1, sy=0.86, lean=2, flash=0.85, spark=2.4, eye=0.0, mouth=1,
                 cracks=1.4, phase=1.0), 55),
        (replace(b, dx=5, sx=1.06, sy=0.9, lean=3, flash=0.6, spark=2.1, eye=0.0, mouth=1,
                 cracks=1.3, phase=1.6), 60),
        (replace(b, dx=4, sx=0.97, sy=1.05, lean=1, flash=0.3, spark=1.7, eye=1.6, phase=2.2), 70),
        (replace(b, dx=3, sx=1.0, sy=0.98, spark=1.35, eye=1.3, phase=2.9), 75),
        (replace(b, dx=1, sy=1.01, phase=3.7), 80),
        (replace(b, dx=0, sy=1.01, phase=4.6), 80),
        (b, 90),
    ]


def death_frames():
    """Killed without a boom: the fuse fizzles, the cap deflates, it wilts into dull spores."""
    b = idle_pose(0)
    out = [
        (replace(b, dx=3, sx=1.08, sy=0.9, flash=0.8, spark=0.6, eye=0.0, mouth=1, phase=0.8), 70),
        (replace(b, dx=2, sy=1.02, flash=0.3, spark=0.3, smoke=0.15, eye=1.6, mouth=1, phase=1.2), 90),
        (replace(b, dx=1, spark=0.0, smoke=0.35, eye=1.0, cracks=0.4, phase=1.5), 90),
        (replace(b, dx=1, droop=0.3, wilt=0.2, spark=0.0, smoke=0.55, eye=0.8, cracks=0.25,
                 sy=0.97, phase=1.7), 90),
        (replace(b, droop=0.6, wilt=0.45, spark=0.0, smoke=0.75, eye=0.5, cracks=0.1, sy=0.93,
                 sx=1.03, phase=1.8), 90),
        (replace(b, droop=0.85, wilt=0.7, spark=0.0, smoke=0.9, eye=0.25, cracks=0.0, sy=0.88,
                 sx=1.05, phase=1.9), 90),
    ]
    steps = 6
    for k in range(steps):
        u = (k + 1) / steps
        motes = tuple(
            (CX - 30 + hash01(k, j, 9) * 56 + u * 6 * (hash01(j, k, 3) - 0.5),
             GROUND - 60 + 50 * hash01(j, k, 4) + u * 16, 1 + int(hash01(j, k, 2) * 3))
            for j in range(10 + 2 * k))
        out.append((replace(b, droop=1.0, wilt=1.0, spark=0.0, eye=0.0, cracks=0.0, sy=0.86, sx=1.06,
                            phase=2.0, smoke=0.0, dissolve=min(1.0, 0.16 * (k + 1) + 0.04),
                            motes=motes if k < steps - 1 else motes[::2]), 85))
    out.append((replace(b, gone=True, dissolve=1.0), 120))
    return out


ANIMATIONS = {
    "idle": (idle_frames, True),
    "attack": (attack_frames, False),
    "cast": (cast_frames, False),
    "explode": (explode_frames, False),
    "hurt": (hurt_frames, False),
    "death": (death_frames, False),
}

# Frames where a hit lands (attack: the headbutt; explode: the boom).
EVENTS = {"attack": {"strikes": [3]}, "explode": {"strikes": [5]}}
# Move id -> animation (the combat screen falls back to attack / cast).
MOVES = {"puff": "cast", "swell": "cast", "explode": "explode", "vengeance": "cast"}


def build():
    return build_sheet(ANIMATIONS, render, (CELL_W, CELL_H), ANCHOR, f"{SHEET_ID}_sheet.png",
                       {"events": EVENTS, "moves": MOVES, "terminal": list(TERMINAL)})


def main() -> None:
    sheet, meta = build()
    save_sheet(OUT_DIR, SHEET_ID, sheet, meta)
    print(f"wrote assets/enemies/{SHEET_ID}_sheet.png ({len(sheet[0])}x{len(sheet)}) and .json")


if __name__ == "__main__":
    main()
