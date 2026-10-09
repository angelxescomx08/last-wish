"""Draw and animate the elite enemy "El Verdugo" (the Executioner). Stdlib only:

    python scripts/generate_elite_executioner.py

Same method as the Espectro and the floor-1 bosses (``docs/code-drawn-sprites.md``): one
renderer, every frame a ``Pose``. Identity "Ejecución": he telegraphs huge blows and marks
the hero to receive them.

* ONE row-scanned mass (``paint_mass``) from the tip of the hood to the soles: a hulking,
  slightly hunched executioner facing left. Zones painted inside it: a dark-crimson leather
  hood with a short ragged cape over the shoulders and two eye holes where ember eyes burn
  (the accent colour), bare massive ash-olive shoulders, a black leather jerkin with a
  diagonal strap, iron buckle and lacing, a rope belt with a knot, a bloodstained leather
  apron that sways, dark trousers and heavy boots. The hood's pointed tail flops back.
* Drawn on top with a dark rim (the Espectro sleeve rule): the far arm, the enormous
  crescent-bladed headsman's axe (long wooden haft with a leather grip, dark iron head with a
  bevel and a bright honed edge that glints) and the near arm with its leather bracer; the
  near deltoid is painted over the arm root so the joint never shows.

Animations (non-death actions end on idle frame 0):
  idle     12-frame heavy breathing, axe head resting low in front; hood tail and apron
           sway, a glint runs along the edge, the eyes flicker
  attack   "Hachazo": axe hauled over the right shoulder, heavy diagonal swing down-left
           with a bright arc smear, sparks where it lands, eased recovery
  behead   "Decapitar": axe raised high overhead (long anticipation, eyes blaze), a
           vertical chop down-left into the floor (cracks, sparks, dust), slow recovery
  sharpen  "Afilar": whetstone dragged along the edge (sparks), the edge brightens
  cast     "Sentencia" / "Sed de Sangre": points the axe at the hero, eyes and a blood-red
           sigil flare, a red aura pulses
  hurt     white flash, knocked back a little (he is heavy)
  death    drops to his knees, the axe falls, then he burns away into embers and ash -> empty

Output: ``assets/enemies/executioner_sheet.png`` + ``.json`` (``events``, ``moves``,
``boss``/``elite``).
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
SHEET_ID = "executioner"

CELL_W, CELL_H = 208, 120
CX, GROUND = 142, 113
ANCHOR = (CX, GROUND + 2)
TOP_H = 84.0                       # hood tip height (before the tail)
HUNCH = 5.0                        # the head sits forward (left)
KNEEL_DROP = 17.0                  # how far the upper body sinks when kneeling

# ---------------------------------------------------------------- palette
OUTLINE = (14, 8, 10)
HOOD = [(18, 8, 11), (34, 12, 16), (54, 17, 22), (78, 25, 29), (106, 36, 38), (138, 54, 50)]
SKIN = [(34, 36, 33), (52, 56, 49), (74, 80, 67), (98, 105, 86), (126, 133, 108), (156, 161, 133),
        (188, 190, 160)]
JERKIN = [(15, 12, 13), (26, 21, 21), (38, 31, 30), (54, 44, 40), (72, 60, 53), (96, 80, 68)]
APRON = [(22, 14, 12), (36, 23, 19), (53, 35, 27), (72, 49, 36), (96, 67, 48), (124, 90, 64)]
CLOTH = [(19, 17, 20), (30, 27, 30), (43, 39, 41), (58, 53, 54), (76, 70, 68)]
BOOT = [(16, 12, 12), (28, 21, 19), (42, 31, 26), (60, 45, 36), (82, 63, 49)]
ROPE = [(58, 42, 30), (98, 74, 46), (142, 112, 70), (184, 152, 102)]
IRON = [(14, 15, 20), (26, 28, 36), (40, 44, 54), (58, 63, 76), (82, 88, 102), (112, 118, 132),
        (150, 156, 168)]
EDGE = [(150, 158, 170), (196, 204, 214), (232, 238, 244), (255, 255, 255)]
WOOD = [(30, 18, 13), (52, 32, 20), (78, 50, 30), (106, 72, 42), (138, 98, 60)]
GRIP = [(26, 14, 12), (46, 24, 18), (70, 38, 26)]
EMBER = [(112, 30, 12), (200, 70, 18), (250, 140, 40), (255, 212, 118), (255, 250, 222)]
BLOOD = [(56, 6, 10), (110, 12, 18), (176, 26, 30), (232, 70, 62), (255, 160, 140)]
STAIN = (46, 14, 12)
ASH = [(48, 44, 46), (78, 72, 72), (112, 104, 100)]
DUST = [(52, 44, 40), (84, 72, 62), (118, 104, 88), (156, 142, 120)]
STONE = [(52, 54, 62), (88, 92, 100), (130, 134, 140)]
VOID = (8, 4, 6)
WHITE = (255, 255, 255)

# axe geometry (local: s along the haft from the near grip towards the head, n towards the edge)
BUTT_S, HEAD_S, TIP_S = -14.0, 44.0, 51.0
BL = 1.3                           # blade scale (the drawing below is in unscaled units)


def blade_local(s: float, n: float) -> tuple[float, float]:
    return 36.0 + (s - HEAD_S) / BL, n / BL


def edge_n(s: float) -> float:
    """Outer edge of the crescent blade at ``s`` (scaled units)."""
    s0 = 36.0 + (s - HEAD_S) / BL
    return (16.0 - 6.2 * ((s0 - 35.0) / 12.0) ** 2) * BL


EDGE_S0, EDGE_S1 = HEAD_S + (24.5 - 36.0) * BL, HEAD_S + (46.5 - 36.0) * BL


@dataclass(frozen=True)
class Pose:
    dx: float = 0.0
    dy: float = 0.0
    lean: float = 0.0                  # head/shoulders offset (negative = towards the hero)
    sx: float = 1.0
    sy: float = 1.0
    breath: float = 0.0                # chest and head lift (px)
    kneel: float = 0.0                 # death: drops to his knees
    bow: float = 0.0                   # head bowed forward (px)
    phase: float = 0.0
    sway: float = 1.0
    grip: tuple[float, float] = (-17.0, 40.0)     # near hand on the haft (rel. CX, height)
    ang: float = 2.18                  # haft direction (screen radians, 0 = right, pi/2 = down)
    edge: int = -1                     # which side of the haft the blade is on
    far_s: float = -7.0                # far hand along the haft
    hand_f: tuple | None = None        # free near hand (rel. CX, height) instead of the haft
    hand_b: tuple | None = None        # free far hand
    pole_f: tuple = (-10.0, 18.0)      # where the elbows point (screen offset from the shoulder)
    pole_b: tuple = (12.0, 16.0)
    axe_front: bool = False            # the axe is drawn over the near arm (sharpen)
    far_behind: bool = False           # the far arm passes behind the head (raised overhead)
    eye: float = 1.0
    glint: float = -1.0                # glint position along the edge 0..1 (<0 none)
    hone: float = 0.0                  # edge brightness (sharpen)
    stone: float = -1.0                # whetstone in the near hand at this edge position (<0 none)
    flash: float = 0.0
    dissolve: float = 0.0
    smear: tuple = field(default_factory=tuple)   # earlier (grip_x, grip_h, ang) of the swing
    smear_fade: float = 0.0
    impact: tuple = field(default_factory=tuple)  # (x rel CX, progress, fade) floor hit
    spark: tuple = field(default_factory=tuple)   # (x rel CX, h, progress, dir) spark spray
    hone_sparks: float = -1.0          # whetstone sparks progress
    sigil: float = 0.0                 # blood sigil (cast)
    aura: float = 0.0                  # red aura (cast)
    dust: float = 0.0                  # dust at the feet
    motes: tuple = field(default_factory=tuple)   # (x, y, kind) 0-2 ash, 3-5 ember


# ---------------------------------------------------------------- body frame
class Body:
    def __init__(self, p: Pose) -> None:
        self.p = p

    def lift(self, h: float) -> float:
        p = self.p
        return p.breath * smooth((h - 42) / 18)

    def base_y(self, h: float) -> float:
        """Screen height (above ground) of body height ``h`` before breath."""
        k = self.p.kneel * KNEEL_DROP
        knee = 28.0
        if h >= knee:
            return h - k
        return h * (1 - k / knee)

    def y_of(self, h: float) -> float:
        p = self.p
        return GROUND + p.dy - (self.base_y(h) + self.lift(h)) * p.sy

    def h_of(self, y: float) -> float:
        p = self.p
        k = p.kneel * KNEEL_DROP
        Y = (GROUND + p.dy - y) / p.sy
        h = 0.0
        for _ in range(3):                    # breath depends on h: refine
            Yb = Y - self.lift(h)
            h = Yb + k if Yb >= 28 - k else Yb / max(0.2, 1 - k / 28)
        return h

    def center(self, h: float) -> float:
        p = self.p
        k = max(0.0, min(1.0, h / TOP_H))
        hunch = -(HUNCH + p.bow) * smooth((h - 56) / 18) - 3.5 * smooth((h - 34) / 30)
        return CX + p.dx + p.lean * k ** 1.2 + hunch

    def to_cell(self, lx: float, h: float) -> tuple[float, float]:
        return self.center(h) + lx * self.p.sx, self.y_of(h)


def _c(light: float) -> float:
    return max(0.0, min(1.0, light))


# ---------------------------------------------------------------- the mass
def torso_extent(h: float) -> tuple[float, float]:
    """(front, back) half extents of hips / torso / chest."""
    if h < 36:
        return 15.0, 14.0
    if h < 46:
        s = (h - 36) / 10
        return 15.0 + 4.0 * math.sin(s * math.pi / 2), 14.0 + 1.0 * s     # belly
    if h < 58:
        s = (h - 46) / 12
        return 19.0 + 0.4 * math.sin(s * math.pi), 15.0 + 1.6 * s           # chest
    s = min(1.0, (h - 58) / 9)
    return 19.0 - 7.0 * s * s, 16.6 - 6.0 * s * s                          # traps to the neck


def leg_spans(h: float, kneel: float):
    """Spans (x0, x1, kind) of the two legs/boots at body height ``h`` (rel. centre)."""
    out = []
    fk = -8.0 - 3.0 * kneel
    for side, cx_ in ((-1, fk), (1, 8.0)):
        if h >= 10.5:
            k = (h - 10.5) / 15.5
            hw = 5.3 + 1.7 * k * k + (0.6 if 11 < h < 17 else 0.0)
            out.append((cx_ - hw, cx_ + hw, "leg", side))
        else:
            toe = 9.5 if side < 0 else 7.0
            heel = 5.6
            cuff = 1.0 if h > 7.5 else 0.0
            front = (toe if h < 5.5 else 6.2 + (toe - 6.2) * (1 - (h - 5.5) / 2.5) if h < 8 else 5.6) + cuff
            out.append((cx_ - front, cx_ + heel + cuff, "boot", side))
    return out


def paint_mass(cv: Canvas, b: Body) -> dict:
    """Row-scan the whole figure. Returns reference points (face, belt knot...)."""
    p = b.p
    sx = p.sx
    ph = p.phase
    nd = b.to_cell(-19.0, 59.5)                       # near deltoid centre
    fd = b.to_cell(17.0, 60.0)                        # far deltoid
    for y in range(CELL_H):
        h = b.h_of(y + 0.5)
        if h < -0.5 or h > TOP_H + 1:
            continue
        c = b.center(h)
        v = 1 - max(0.0, min(1.0, h / TOP_H))
        for x in range(max(0, int(c - 34)), min(CELL_W, int(c + 34))):
            X = x + 0.5
            lx = (X - c) / sx
            col = None
            # --- hood dome
            if 67.5 <= h <= TOP_H:
                top = (TOP_H - h) / 5.0
                hw = 8.8 * math.sqrt(min(1.0, top)) + 1.0 * (TOP_H - h) / 16
                fr = hw * 1.06
                if -fr <= lx <= hw:
                    u = lx / (fr if lx < 0 else hw)
                    light = 0.64 - 0.42 * u - 0.32 * (TOP_H - h) / 16
                    light += 0.08 * math.cos(u * 4.0 + 0.4)
                    if abs(u) > 0.84:
                        light -= 0.14
                    if u < -0.6 and h > 76:
                        light += 0.12
                    col = ramp(HOOD, _c(light), x, y)
                    if abs(lx + 2.6) < 0.5 and h > 78.5:   # stitched centre seam
                        col = HOOD[1] if (y % 2) else HOOD[3]
            # --- hood cape (short, ragged, over the shoulders)
            if col is None and 50.0 <= h < 70.5:
                sw = 0.8 * p.sway * math.sin(ph + 0.6) * (70 - h) / 14
                lxs = lx - sw
                k = smooth((70.5 - h) / 12)
                hw = 9.0 + 6.4 * k
                if -hw * 1.06 <= lxs <= hw:
                    bot = 57.0 + 2.4 * abs(math.sin(lxs * 0.45 + 0.9))
                    bot -= 5.5 * max(0.0, 1 - abs(lxs + 2.5) / 6.5)       # bib point in front
                    if h >= bot:
                        u = lxs / (hw * 1.04 if lxs < 0 else hw)
                        light = 0.58 - 0.4 * u - 0.22 * (70 - h) / 14
                        light += 0.12 * math.cos(u * 6.5 + h * 0.15)
                        if h < bot + 1.1:
                            light -= 0.22                  # cape hem turning under
                        if abs(u) > 0.88:
                            light -= 0.12
                        col = ramp(HOOD, _c(light), x, y)
            # --- deltoids (bare shoulders)
            if col is None:
                for (dcx, dcy), dark in ((nd, 0.0), (fd, -0.16)):
                    ex = (X - dcx) / (8.4 * sx)
                    ey = (y + 0.5 - dcy) / 8.0
                    d = ex * ex + ey * ey
                    if d <= 1:
                        nz = math.sqrt(max(0.0, 1 - d))
                        light = 0.24 + 0.5 * (-0.6 * ex - 0.6 * ey + 0.55 * nz) + dark
                        if ex < -0.7 and ey < 0.2:
                            light += 0.14
                        col = ramp(SKIN, _c(light), x, y)
                        break
            # --- torso: jerkin, bare upper chest
            if col is None and 25.0 <= h < 66.0:
                fr, bk = torso_extent(h)
                if -fr <= lx <= bk:
                    u = lx / (fr if lx < 0 else bk)
                    jtop = 60.5 - 5.0 * u * u
                    if h > jtop:
                        light = 0.5 - 0.35 * u
                        col = ramp(SKIN, _c(light), x, y)
                    elif h >= 38.6:
                        light = 0.56 - 0.38 * u - 0.15 * (58 - h) / 20
                        light += 0.1 * math.cos(u * 6.0 + 0.2 * math.sin(ph))
                        if abs(u) > 0.86:
                            light -= 0.15
                        if u < -0.75 and h > 44:
                            light += 0.14
                        if h > jtop - 1.0:
                            light += 0.2                   # stitched neckline
                        col = ramp(JERKIN, _c(light), x, y)
                    elif h >= 35.6:
                        twist = (x + int(h * 2)) % 3
                        light = 0.78 - 0.42 * u - 0.15 * twist + (0.15 if h > 37.5 else -0.1)
                        col = ramp(ROPE, _c(light), x, y, 0.3)
                    else:
                        light = 0.5 - 0.38 * u - 0.2 * (36 - h) / 11
                        col = ramp(CLOTH, _c(light), x, y)
            # --- apron (in front of the legs)
            if True:                                       # the apron covers what is behind it
                if 9.0 <= h < 35.6:
                    k = (35.6 - h) / 24.6
                    swing = p.sway * 1.3 * math.sin(ph + 0.4 + h * 0.08) * k ** 1.4
                    ax0 = -15.8 - 2.6 * k + swing
                    ax1 = 4.0 + 0.8 * k + swing
                    hem = 11.0 + 1.0 * math.sin(lx * 0.7 + ph) + 0.8 * hash01(int(lx + 40), 3, 21)
                    if ax0 <= lx <= ax1 and h >= hem - p.kneel * 3:
                        u = (lx - (ax0 + ax1) / 2) / ((ax1 - ax0) / 2)
                        light = 0.52 - 0.34 * u - 0.24 * k
                        light += 0.13 * math.cos(u * 5.2 + h * 0.05 + 0.4 * math.sin(ph + h * 0.1))
                        if abs(u) > 0.88:
                            light -= 0.14
                        if h < hem + 1.2 - p.kneel * 3:
                            light -= 0.18
                        col = ramp(APRON, _c(light), x, y)
                        # dried blood splashes
                        st = hash01(int((lx + 30) / 3), int(h / 3), 31)
                        if st > 0.86 and hash01(x, y, 32) > 0.35:
                            col = mix(col, STAIN, 0.75)
            # --- legs and boots
            if col is None and h < 26.0:
                for x0, x1, kind, side in leg_spans(h, p.kneel):
                    if x0 <= lx <= x1:
                        u = (lx - (x0 + x1) / 2) / ((x1 - x0) / 2)
                        dark = -0.12 if side > 0 else 0.0
                        if kind == "leg":
                            light = 0.48 - 0.36 * u - 0.15 * (26 - h) / 16 + dark
                            light += 0.1 * math.cos(u * 5 + h * 0.4)
                            col = ramp(CLOTH, _c(light), x, y)
                        else:
                            light = 0.55 - 0.32 * u + dark + (0.22 if 7.5 < h < 9.5 else 0.0)
                            if h < 1.5:
                                light = 0.08
                            if 4.5 < h < 5.6:
                                light -= 0.25                 # strap across the boot
                            col = ramp(BOOT, _c(light), x, y)
                        break
            if col is not None:
                cv.put(x, y, col)
    # --- details painted onto the mass
    refs = {}
    _draw_strap(cv, b)
    _draw_knot(cv, b)
    refs["eyes"] = _draw_eyes(cv, b)
    _draw_tail(cv, b)
    refs["chest"] = b.to_cell(-3.0, 50.0)
    return refs


def _draw_strap(cv: Canvas, b: Body) -> None:
    """Diagonal leather strap from the far shoulder to the front hip, iron buckle, lacing."""
    x0, y0 = b.to_cell(12.0, 60.0)
    x1, y1 = b.to_cell(-14.0, 39.5)
    n = int(math.hypot(x1 - x0, y1 - y0) * 2) + 1
    for i in range(n + 1):
        t = i / n
        x, y = x0 + (x1 - x0) * t, y0 + (y1 - y0) * t
        for k, lv in ((-1, 4), (0, 2), (1, 2), (2, 0)):
            xx, yy = int(x + k * 0.6), int(y + k * 0.8)
            if cv.get(xx, yy) is not None:
                cv.put(xx, yy, APRON[lv])
    bx, by = x0 + (x1 - x0) * 0.42, y0 + (y1 - y0) * 0.42
    for ox, oy, c in ((-1, -1, IRON[5]), (0, -1, IRON[6]), (1, -1, IRON[4]), (-1, 0, IRON[4]),
                      (1, 0, IRON[2]), (-1, 1, IRON[3]), (0, 1, IRON[2]), (1, 1, IRON[1]),
                      (0, 0, APRON[1])):
        cv.put(int(bx) + ox, int(by) + oy, c)
    # lacing down the jerkin front
    for h in range(42, 56, 3):
        lx, ly = b.to_cell(-6.0, h)
        cv.put(int(lx) - 1, int(ly), ROPE[2])
        cv.put(int(lx), int(ly) + 1, ROPE[1])
        cv.put(int(lx) + 1, int(ly), ROPE[2])


def _draw_knot(cv: Canvas, b: Body) -> None:
    p = b.p
    kx, ky = b.to_cell(-9.0, 37.0)
    for ox, oy, lv in ((-1, -1, 3), (0, -1, 2), (1, -1, 2), (-1, 0, 2), (0, 0, 3), (1, 0, 1),
                       (-1, 1, 1), (0, 1, 2), (1, 1, 1)):
        cv.put(int(kx) + ox, int(ky) + oy, ROPE[lv])
    for k, (ln, ox) in enumerate(((8, -1), (11, 1))):
        for s in range(ln):
            t = s / ln
            sw = 1.1 * math.sin(p.phase - 0.6 - k) * t * t * p.sway
            x, y = kx + ox + sw - 0.2 * s * (k == 0), ky + 2 + s
            col = ROPE[2] if s % 3 else ROPE[1]
            cv.put(int(x), int(y), col if s < ln - 1 else ROPE[3])


def face_center(b: Body) -> tuple[float, float]:
    return b.to_cell(-2.4, 76.5)


EYE_L = [(-2, -1), (-1, -1), (0, -1), (-1, 0), (0, 0), (1, 0)]
EYE_R = [(0, -1), (1, -1), (-1, 0), (0, 0)]


def _draw_eyes(cv: Canvas, b: Body) -> list[tuple[float, float]]:
    p = b.p
    fx, fy = face_center(b)
    fx, fy = round(fx), round(fy)
    eyes = []
    for (ex, holes, hot) in ((fx - 3, EYE_L, ((-1, 0), (0, 0))), (fx + 3, EYE_R, ((0, 0),))):
        for ox, oy in holes:                                   # brow shadow + rim
            cv.put(ex + ox, fy + oy - 1, HOOD[4] if ox < 0 else HOOD[3])
        for ox, oy in holes:
            cv.put(ex + ox, fy + oy, VOID)
        for ox, oy in holes:
            if (ox, oy + 1) not in holes:
                cv.put(ex + ox, fy + oy + 1, HOOD[1])          # lower lid in shadow
        if p.eye > 0.05:
            for ox, oy in hot:
                lv = 4 if p.eye > 1.3 else 3 if p.eye > 0.7 else 2
                cv.put(ex + ox, fy + oy, EMBER[lv])
            for ox, oy in holes:
                if (ox, oy) not in hot and p.eye > 1.0:
                    cv.put(ex + ox, fy + oy, EMBER[1] if p.eye < 1.4 else EMBER[2])
            eyes.append((ex + 0.5, fy + 0.5))
    return eyes


def _draw_tail(cv: Canvas, b: Body) -> None:
    """The hood's pointed tail flopping back over the crown."""
    p = b.p
    x0, y0 = b.to_cell(2.0, TOP_H - 1.5)
    w = p.sway * math.sin(p.phase - 0.9)
    pts = bezier((x0 - 1, y0 + 1), (x0 + 7, y0 - 6 + 0.5 * w), (x0 + 13 + w, y0 - 1 + 1.6 * w), 18)
    stroke(cv, pts, lambda t: 3.6 * (1 - t) + 0.7, HOOD, shade=-0.05)


# ---------------------------------------------------------------- arms
def ik_pole(sh, target, l1, l2, pole):
    """Two-bone IK choosing the elbow side closest to ``pole`` (a point)."""
    e1, w = ik(sh, target, l1, l2, 1.0)
    e2, _ = ik(sh, target, l1, l2, -1.0)
    d1 = math.hypot(e1[0] - pole[0], e1[1] - pole[1])
    d2 = math.hypot(e2[0] - pole[0], e2[1] - pole[1])
    return (e1 if d1 <= d2 else e2), w


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


def limb(cv: Canvas, pts, radius, colors_at, *, shade=0.0, rim=OUTLINE) -> None:
    """Shaded tube like ``pixel_kit.stroke`` but with a ramp chosen by ``t`` (skin / bracer)."""
    from pixel_kit import polyline
    tube = Canvas(cv.w, cv.h)
    pts = polyline(list(pts), 0.5)
    n = len(pts)
    best: dict = {}
    for i, (x, y) in enumerate(pts):
        t = i / max(1, n - 1)
        r = max(0.7, radius(t))
        for yy in range(int(y - r) - 1, int(y + r) + 2):
            for xx in range(int(x - r) - 1, int(x + r) + 2):
                ddx, ddy = xx + 0.5 - x, yy + 0.5 - y
                d = math.hypot(ddx, ddy) / r
                if d > 1:
                    continue
                key = (xx, yy)
                if key not in best or d < best[key][0]:
                    best[key] = (d, (-0.7 * ddx - 0.7 * ddy) / r, t)
    for (xx, yy), (d, side, t) in best.items():
        cols, extra = colors_at(t)
        light = 0.5 + 0.42 * side - 0.2 * d * d + shade + extra
        tube.put(xx, yy, ramp(cols, _c(light), xx, yy, 0.6))
    cv.blit(tube, rim=rim)


def arm_radius(te: float):
    def r(t: float) -> float:
        if t < te:
            k = t / te
            return 6.0 + 1.0 * math.sin(k * math.pi * 0.8) - 1.2 * k * k + 1.2 * max(0.0, 1 - k / 0.2)  # bicep
        k = (t - te) / (1 - te)
        if 0.35 < k < 0.85:
            return 5.8                                                      # bracer
        return 5.4 - 1.2 * max(0.0, k - 0.85) / 0.15 + 0.3 * math.sin(k * math.pi)
    return r


def arm_colors(te: float, dark: float):
    def f(t: float):
        k = (t - te) / (1 - te) if t > te else -1
        if 0.35 < k < 0.85:
            edge = k < 0.42 or k > 0.78
            return APRON, dark + (0.15 if edge else 0.0)
        return SKIN, dark
    return f


def draw_arm(cv: Canvas, sh, hand, pole, *, far: bool) -> None:
    l1, l2 = 17.0, 16.0
    elb, wr = ik_pole(sh, hand, l1, l2, (sh[0] + pole[0], sh[1] + pole[1]))
    te = l1 / (l1 + l2)
    dark = -0.18 if far else 0.0
    limb(cv, [sh, elb, wr], arm_radius(te), arm_colors(te, dark), shade=0.0)
    draw_fist(cv, wr, dark)


def draw_fist(cv: Canvas, c, dark: float) -> None:
    fx, fy = c
    g = Canvas(cv.w, cv.h)
    for yy in range(int(fy) - 5, int(fy) + 6):
        for xx in range(int(fx) - 5, int(fx) + 6):
            ex, ey = (xx + 0.5 - fx) / 4.3, (yy + 0.5 - fy) / 3.9
            d = ex * ex + ey * ey
            if d > 1:
                continue
            light = 0.62 - 0.4 * ex - 0.4 * ey - 0.2 * d + dark
            col = ramp(SKIN, _c(light), xx, yy)
            if abs(ey + 0.15) < 0.16 and ex < 0.4:
                col = SKIN[1]                                          # finger crease
            g.put(xx, yy, col)
    cv.blit(g, rim=OUTLINE)


def hand_points(b: Body, p: Pose):
    gx, gy = CX + p.dx + p.grip[0] * p.sx, GROUND + p.dy - p.grip[1]
    ca, sa = math.cos(p.ang), math.sin(p.ang)
    near = (gx, gy) if p.hand_f is None else (CX + p.dx + p.hand_f[0], GROUND + p.dy - p.hand_f[1])
    far = (gx + ca * p.far_s, gy + sa * p.far_s) if p.hand_b is None else \
        (CX + p.dx + p.hand_b[0], GROUND + p.dy - p.hand_b[1])
    return (gx, gy), near, far


def draw_deltoid_cap(cv: Canvas, b: Body) -> None:
    """Repaint the near shoulder over the arm root so the joint never shows."""
    dcx, dcy = b.to_cell(-19.0, 59.5)
    g = Canvas(cv.w, cv.h)
    for yy in range(int(dcy) - 7, int(dcy) + 7):
        for xx in range(int(dcx) - 8, int(dcx) + 8):
            ex = (xx + 0.5 - dcx) / (7.4 * b.p.sx)
            ey = (yy + 0.5 - dcy) / 7.0
            d = ex * ex + ey * ey
            if d > 1 or ey > 0.55:
                continue
            nz = math.sqrt(max(0.0, 1 - d))
            light = 0.24 + 0.5 * (-0.6 * ex - 0.6 * ey + 0.55 * nz)
            if ex < -0.7 and ey < 0.2:
                light += 0.14
            g.put(xx, yy, ramp(SKIN, _c(light), xx, yy))
    # keep the hood cape in front of it
    for yy in range(g.h):
        for xx in range(g.w):
            if g.px[yy][xx] is not None and cv.get(xx, yy) is not None:
                c = cv.get(xx, yy)[:3]
                if c in HOOD:
                    g.px[yy][xx] = None
    cv.blit(g, rim=OUTLINE)


# ---------------------------------------------------------------- the axe
def axe_frame(p: Pose, grip):
    gx, gy = grip
    ca, sa = math.cos(p.ang), math.sin(p.ang)
    nx, ny = p.edge * sa, -p.edge * ca
    return gx, gy, ca, sa, nx, ny


def axe_point(p: Pose, grip, s: float, n: float):
    gx, gy, ca, sa, nx, ny = axe_frame(p, grip)
    return gx + ca * s + nx * n, gy + sa * s + ny * n


def draw_axe(cv: Canvas, p: Pose, grip) -> list[tuple[float, float]]:
    """Headsman's axe. Returns points along the honed edge (for glints and sparks)."""
    gx, gy, ca, sa, nx, ny = axe_frame(p, grip)
    lit = -0.7 * nx - 0.7 * ny                      # how much the edge side faces the light
    lit_h = (-0.7 * (-sa) - 0.7 * ca)               # haft cross-normal facing the light
    corners = [axe_point(p, grip, s, n) for s in (BUTT_S - 2, TIP_S + 1) for n in (-9, 23)]
    x0 = int(min(c[0] for c in corners)) - 1
    x1 = int(max(c[0] for c in corners)) + 2
    y0 = int(min(c[1] for c in corners)) - 1
    y1 = int(max(c[1] for c in corners)) + 2
    g = Canvas(cv.w, cv.h)
    for y in range(max(0, y0), min(cv.h, y1)):
        for x in range(max(0, x0), min(cv.w, x1)):
            rx, ry = x + 0.5 - gx, y + 0.5 - gy
            s_real = rx * ca + ry * sa
            n_real = rx * nx + ry * ny
            s, n = blade_local(s_real, n_real)
            col = None
            # blade
            if 3.0 <= n <= edge_n(s_real) / BL and s <= 41.5 + 0.45 * (n - 3) and \
                    s >= 31.0 - 9.5 * max(0.0, (n - 3) / 13) ** 0.8:
                e = (edge_n(s_real) - n_real) / BL * 1.15
                if e < 1.25:
                    k = 0.55 + 0.35 * lit + 0.6 * p.hone
                    col = EDGE[max(0, min(3, int(round(k * 3 + (bayer(x, y) - 0.5) * 0.5))))]
                elif e < 4.6:
                    light = 0.55 + 0.25 * lit + 0.1 * (e < 2.3) + 0.35 * p.hone
                    col = ramp(IRON, _c(light), x, y, 0.5)
                else:
                    light = 0.3 + 0.2 * lit - 0.1 * (n - 3) / 8 + 0.05 * math.sin(s * 0.4)
                    col = ramp(IRON, _c(light), x, y, 0.5)
                    if e < 5.4:
                        col = IRON[1]                       # bevel line
                    if hash01(int(s), int(n), 41) > 0.9 and e > 6:
                        col = mix(col, STAIN, 0.6)          # old blood
            # cheek / socket over the haft
            elif 31.0 <= s <= 42.0 and -2.4 <= n < 3.0:
                light = 0.42 + 0.3 * lit * (n / 3) - 0.1 * abs(s - 36.5) / 6
                col = ramp(IRON, _c(light), x, y, 0.5)
                if abs(s - 32) < 0.6 or abs(s - 41) < 0.6:
                    col = IRON[1]
                if (abs(s - 34) < 0.7 or abs(s - 39) < 0.7) and abs(n - 0.6) < 0.7:
                    col = IRON[6]                           # rivets
            # back spike
            elif -4.6 <= n < -2.4 and abs(s - 36.5) <= 2.2:
                light = 0.5 - 0.3 * lit
                col = ramp(IRON, _c(light), x, y, 0.5)
            # top spike
            elif 42.0 < s and s_real <= TIP_S and abs(n_real) <= 2.1 * (1 - (s_real - HEAD_S - 7.8) / (TIP_S - HEAD_S - 7.8)) + 0.2:
                col = ramp(IRON, _c(0.55 + 0.3 * lit_h * n_real), x, y, 0.4)
            # haft
            elif BUTT_S <= s_real <= HEAD_S - 6 and abs(n_real) <= 1.35:
                s, n = s_real, n_real
                if s < BUTT_S + 2.6:
                    col = ramp(IRON, _c(0.5 + 0.3 * lit_h * n), x, y, 0.4)
                elif -10.5 <= s <= 2.5:
                    wrap = (int(s * 1.0 + n * 0.8) % 3 == 0)
                    col = GRIP[0] if wrap else ramp(GRIP, _c(0.6 + 0.35 * lit_h * n), x, y, 0.4)
                else:
                    light = 0.55 + 0.4 * lit_h * n / 1.35
                    if hash01(int(s / 2), 0, 43) > 0.75:
                        light -= 0.12                       # grain
                    col = ramp(WOOD, _c(light), x, y, 0.4)
            if col is not None:
                g.put(x, y, col)
    cv.blit(g, rim=OUTLINE)
    return edge_points(p, grip)


def edge_points(p: Pose, grip) -> list[tuple[float, float]]:
    out = []
    for k in range(16):
        s = EDGE_S0 + (EDGE_S1 - EDGE_S0) * k / 15
        out.append(axe_point(p, grip, s, edge_n(s) - 0.6))
    return out


def draw_glint(cv: Canvas, pts, pos: float, k: float = 1.0) -> None:
    if pos < 0 or not pts:
        return
    x, y = pts[max(0, min(len(pts) - 1, int(round(pos * (len(pts) - 1)))))]
    x, y = int(x), int(y)
    cv.put(x, y, WHITE, solid=False)
    ln = 3 if k > 0.6 else 2
    for d in range(1, ln + 1):
        a = int(255 * (1 - d / (ln + 1)) * k) + 40
        for ox, oy in ((d, 0), (-d, 0), (0, d), (0, -d)):
            cv.put(x + ox, y + oy, EDGE[3] if d == 1 else EDGE[2], solid=False, alpha=min(255, a))


def draw_stone(cv: Canvas, c) -> None:
    """Whetstone held against the edge."""
    x, y = int(c[0]), int(c[1])
    for oy in range(-2, 2):
        for ox in range(-3, 3):
            light = 0.8 - 0.25 * (ox + 3) / 6 - 0.35 * (oy + 2) / 4
            cv.put(x + ox, y + oy, STONE[max(0, min(2, int(light * 3)))])


# ---------------------------------------------------------------- effects
def _unwrap(a0: float, a1: float) -> float:
    """``a1`` shifted by whole turns to the shortest way from ``a0``."""
    while a1 - a0 > math.pi:
        a1 -= math.tau
    while a1 - a0 < -math.pi:
        a1 += math.tau
    return a1


def draw_smear(cv: Canvas, p: Pose) -> None:
    """Bright crescent swept by the outer half of the blade between the swing keys and now."""
    if not p.smear or p.smear_fade >= 1:
        return
    keys = list(p.smear) + [(p.grip[0], p.grip[1], p.ang)]
    total = len(keys) - 1
    best: dict = {}
    for j in range(total):
        (ax, ah, aa), (bx, bh, ba) = keys[j], keys[j + 1]
        ba = _unwrap(aa, ba)
        steps = int(abs(ba - aa) * 70) + 12
        for i in range(steps):
            t = i / steps
            age = 1 - (j + t) / total                       # 1 oldest .. 0 newest
            w = (1 - age) ** 0.8 - p.smear_fade * 1.1
            if w <= 0:
                continue
            gx = CX + p.dx + lerp(ax, bx, t)
            gy = GROUND + p.dy - lerp(ah, bh, t)
            q = replace(p, ang=lerp(aa, ba, t))
            for k in range(14):
                sv = HEAD_S - 2 + (EDGE_S1 - HEAD_S + 2) * k / 13
                en = edge_n(sv)
                for dn in (0.3, -1.0, -2.3, -3.6):
                    x, y = axe_point(q, (gx, gy), sv, en + dn)
                    key = (int(x), int(y))
                    rk = (k / 13) * (1 - (-dn + 0.3) / 6)
                    if key not in best or best[key][0] < w:
                        best[key] = (w, rk)
    for (xi, yi), (w, rk) in best.items():
        if not cv.inside(xi, yi) or cv.solid[yi][xi]:
            continue
        v = w * (0.45 + 0.55 * rk)
        if w < 0.3 and bayer(xi, yi) > w * 3:
            continue
        col = EDGE[3] if v > 0.75 else EDGE[2] if v > 0.5 else EDGE[1] if v > 0.3 else EDGE[0]
        cv.put(xi, yi, col, solid=False, alpha=int(70 + 185 * min(1.0, w)))


def draw_sparks(cv: Canvas, ox: float, oy: float, prog: float, direction: float, n: int = 12,
                spread: float = 1.4, seed: int = 0, speed: float = 30.0) -> None:
    """Streaked sparks flying from ``(ox, oy)`` around ``direction`` (screen radians)."""
    if prog < 0 or prog > 1.2:
        return
    for k in range(n):
        a = direction + (hash01(k, 1, 60 + seed) - 0.5) * spread
        sp = speed * (0.5 + 0.7 * hash01(k, 2, 60 + seed))
        t = prog
        x = ox + math.cos(a) * sp * t
        y = oy + math.sin(a) * sp * t + 26 * t * t
        ln = 3 if t < 0.5 else 2
        hot = 1 - t
        for j in range(ln):
            xx = x - math.cos(a) * j * 1.1
            yy = y - (math.sin(a) * sp + 52 * t) / sp * j * 1.1
            lv = 4 if (j == 0 and hot > 0.6) else 3 if hot > 0.45 else 2 if hot > 0.2 else 1
            cv.put(int(xx), int(yy), EMBER[lv], solid=False, alpha=int(255 * min(1.0, hot + 0.35)))


def draw_impact(cv: Canvas, p: Pose) -> None:
    """Floor cracks, dust and sparks where the axe bites the floor."""
    if not p.impact:
        return
    ix, s, fade = p.impact
    x0 = CX + p.dx + ix
    gy = GROUND + 1
    vis = 1 - fade
    if vis <= 0:
        return
    for k, (dirx, ln, dy0) in enumerate(((-1, 26, 1), (1, 20, 2), (-1, 16, 3), (1, 12, 0), (-1, 10, 4))):
        n = int(ln * min(1.0, 0.4 + s * 1.4))
        x, y = x0, gy + dy0 * 0.5
        for i in range(n):
            x += dirx
            if hash01(i, k, 3) > 0.6:
                y += 1 if hash01(i, k, 4) > 0.5 else -1
            y = max(gy - 1, min(gy + 5, y))
            cv.put(round(x), round(y), OUTLINE, solid=False, alpha=int(255 * min(1.0, vis * 1.4)))
            if i < n * 0.45 and s < 0.8:
                cv.put(round(x), round(y) - 1, EMBER[2] if i % 3 else EMBER[3], solid=False,
                       alpha=int(220 * vis))
    if s < 0.4:                                                  # bright burst
        kk = 1 - s / 0.4
        for r in range(10):
            ang = math.pi + r / 9 * math.pi + 0.2 * hash01(r, 1, 8)
            ln = (6 + 9 * hash01(r, 2, 8)) * (0.6 + kk)
            for j in range(int(ln)):
                x = x0 + math.cos(ang) * (3 + j)
                y = gy - 2 + math.sin(ang) * (3 + j) * 0.75
                cv.put(round(x), round(y), WHITE if j < ln * 0.45 else EMBER[3], solid=False,
                       alpha=int(255 * kk))
    for k in range(8):                                           # dust rolling out
        side = -1 if k % 2 == 0 else 1
        dist = (5 + 26 * hash01(k, 1, 6)) * smooth(min(1.0, s * 1.2)) * (1.25 if side < 0 else 0.8)
        cx = x0 + side * dist
        cy = gy - 3 - 8 * s * hash01(k, 2, 6)
        r = 3 + 6 * s * (0.6 + 0.4 * hash01(k, 3, 6))
        a = vis * (1 - 0.45 * s)
        for yy in range(int(cy - r) - 1, int(cy + r) + 2):
            for xx in range(int(cx - r) - 1, int(cx + r) + 2):
                d = math.hypot(xx + 0.5 - cx, (yy + 0.5 - cy) * 1.3) / r
                if d > 1 or yy > gy + 2 or bayer(xx, yy) > (1.3 - d) * a * 1.3:
                    continue
                lvl = 3 if d < 0.35 and yy < cy else 2 if d < 0.7 else 1
                cv.put(xx, yy, DUST[lvl], solid=False, alpha=int(255 * min(1.0, a + 0.4)))
    draw_sparks(cv, x0, gy - 2, s * 1.1, -math.pi / 2 - 0.35, n=14, spread=2.4, seed=3, speed=36)
    for k in range(7):                                           # stone chips
        vx = (-1.4 + 2.2 * hash01(k, 5, 6)) * 24
        vy = 16 + 14 * hash01(k, 6, 6)
        t = s * 1.1
        x = x0 + vx * t
        y = gy - 2 - vy * t + 30 * t * t
        if y > gy or vis < 0.3:
            continue
        cv.put(round(x), round(y), DUST[3])
        cv.put(round(x) + 1, round(y), DUST[1])


def draw_dust(cv: Canvas, k: float, p: Pose) -> None:
    if k <= 0:
        return
    for side, base in ((-1, CX + p.dx - 20), (1, CX + p.dx + 16)):
        for j in range(5):
            cx = base + side * (2 + 10 * k * hash01(j, side + 2, 7))
            cy = GROUND - 1 - 4 * k * hash01(j, 4, 7)
            r = 2 + 3 * k
            for yy in range(int(cy - r), int(cy + r) + 1):
                for xx in range(int(cx - r), int(cx + r) + 1):
                    d = math.hypot(xx + 0.5 - cx, yy + 0.5 - cy) / r
                    if d > 1 or yy > GROUND + 1 or bayer(xx, yy) > (1.2 - d) * (1 - k * 0.6):
                        continue
                    cv.put(xx, yy, DUST[2 if d < 0.5 else 1], solid=False, alpha=170)


SIGIL_GLYPH = ["..#.#..",
               ".#####.",
               "#.###.#",
               "..###..",
               "...#...",
               ".#.#.#.",
               "#..#..#"]


def draw_sigil(cv: Canvas, c, k: float, t: float) -> None:
    """Blood-red sentence sigil: a ring with a crowned blade glyph, in front of the axe."""
    if k <= 0:
        return
    cx, cy = c
    r = 8 + 5 * min(1.0, k)
    a = int(255 * min(1.0, k))
    for i in range(72):
        ang = i / 72 * math.tau + t * 2.0
        x, y = cx + math.cos(ang) * r, cy + math.sin(ang) * r * 1.15
        on = (i // 3) % 4 != 3
        cv.put(int(x), int(y), BLOOD[3] if on else BLOOD[1], solid=False, alpha=a)
        if k > 0.6:
            x2, y2 = cx + math.cos(ang) * (r + 2), cy + math.sin(ang) * (r + 2) * 1.15
            if i % 6 == 0:
                cv.put(int(x2), int(y2), BLOOD[2], solid=False, alpha=a)
    if k > 0.35:
        for j, row in enumerate(SIGIL_GLYPH):
            for i, ch in enumerate(row):
                if ch == "#":
                    cv.put(int(cx) - 3 + i, int(cy) - 3 + j, BLOOD[4] if k > 0.9 else BLOOD[3],
                           solid=False, alpha=a)
    cv.glow(cx, cy, r + 5, BLOOD[2], 0.3 * min(1.0, k))


def draw_floor_ring(cv: Canvas, k: float, t: float, p: Pose) -> None:
    if k <= 0:
        return
    gx, gy = CX + p.dx - 4, GROUND
    rx, ry = 34 * min(1.0, k + 0.2), 6 * min(1.0, k + 0.2)
    for i in range(160):
        a = i / 160 * math.tau
        x, y = gx + math.cos(a) * rx, gy + math.sin(a) * ry
        on = (i + int(t * 50)) % 10 < 7
        cv.put(int(x), int(y), BLOOD[2] if on else BLOOD[1], solid=False, alpha=int(230 * min(1.0, k)))


def draw_aura(cv: Canvas, k: float) -> None:
    """Pulsing red rim of light around the solid figure (cast)."""
    if k <= 0:
        return
    add = []
    for y in range(cv.h):
        for x in range(cv.w):
            if cv.px[y][x] is not None:
                continue
            best = 9
            for ox, oy, d in ((1, 0, 1), (-1, 0, 1), (0, 1, 1), (0, -1, 1), (2, 0, 2), (-2, 0, 2),
                              (0, -2, 2), (0, 2, 2), (0, -3, 3)):
                nx_, ny_ = x + ox, y + oy
                if 0 <= nx_ < cv.w and 0 <= ny_ < cv.h and cv.solid[ny_][nx_]:
                    best = min(best, d)
            if best < 9:
                add.append((x, y, best))
    for x, y, d in add:
        a = k * (1.0 if d == 1 else 0.55 if d == 2 else 0.3)
        if bayer(x, y) > a * 1.4:
            continue
        cv.put(x, y, BLOOD[3] if d == 1 else BLOOD[2], solid=False, alpha=int(255 * min(1.0, a + 0.2)))


# ---------------------------------------------------------------- render
def render(p: Pose, t: float = 0.0) -> Canvas:
    cv = Canvas(CELL_W, CELL_H)
    if p.dissolve >= 1.0:
        return cv
    b = Body(p)
    draw_floor_ring(cv, p.sigil * 0.9, t, p)
    mass = Canvas(CELL_W, CELL_H)
    refs = paint_mass(mass, b)
    grip, near, far = hand_points(b, p)
    sh_n = b.to_cell(-20.0, 59.0)
    sh_f = b.to_cell(16.5, 59.5)
    if p.far_behind:
        draw_arm(cv, sh_f, far, p.pole_b, far=True)
        cv.blit(mass, rim=OUTLINE)
    else:
        cv.blit(mass)
        draw_arm(cv, sh_f, far, p.pole_b, far=True)
    if p.axe_front:
        draw_arm(cv, sh_n, near, p.pole_f, far=False)
        edge_pts = draw_axe(cv, p, grip)
    else:
        edge_pts = draw_axe(cv, p, grip)
        draw_arm(cv, sh_n, near, p.pole_f, far=False)
    if p.stone >= 0:
        k = max(0, min(len(edge_pts) - 1, int(round(p.stone * (len(edge_pts) - 1)))))
        draw_stone(cv, (edge_pts[k][0] + 1, edge_pts[k][1]))
    draw_deltoid_cap(cv, b)
    outline(cv, OUTLINE)
    # lights
    if p.eye > 0.05:
        for ex, ey in refs["eyes"]:
            cv.glow(ex, ey, 3.5 + 2.5 * p.eye, EMBER[2], 0.3 * p.eye, halo=p.eye > 1.2)
    if p.hone > 0.05:
        for x, y in edge_pts[::3]:
            cv.glow(x, y, 4 + 3 * p.hone, EDGE[1], 0.25 * p.hone, halo=False)
    draw_glint(cv, edge_pts, p.glint)
    if p.aura > 0:
        draw_aura(cv, p.aura)
    draw_smear(cv, p)
    draw_impact(cv, p)
    if p.spark:
        sx_, sh_, sp_, sd_ = p.spark
        draw_sparks(cv, CX + p.dx + sx_, GROUND + p.dy - sh_, sp_, sd_, n=10, spread=1.6, seed=5)
    if p.hone_sparks >= 0 and p.stone >= 0:
        k = max(0, min(len(edge_pts) - 1, int(round(p.stone * (len(edge_pts) - 1)))))
        ex, ey = edge_pts[k]
        draw_sparks(cv, ex - 1, ey, p.hone_sparks, math.pi + 0.5, n=12, spread=1.3, seed=9, speed=26)
        draw_sparks(cv, ex - 1, ey, 0.12 + 0.5 * p.hone_sparks, math.pi - 0.3, n=8, spread=1.0,
                    seed=11, speed=20)
    if p.sigil > 0:
        tip = axe_point(p, grip, TIP_S + 12, 4)
        draw_sigil(cv, tip, p.sigil, t)
    draw_dust(cv, p.dust, p)
    for (mx, my, kind) in p.motes:
        col = ASH[int(kind)] if kind < 3 else EMBER[min(4, int(kind) - 1)]
        cv.put(int(mx), int(my), col, solid=False)
    flash(cv, p.flash)
    if p.dissolve > 0:
        top = b.y_of(TOP_H) - 6
        dissolve(cv, p.dissolve, top, GROUND + 2, EMBER[3], EMBER[1], upward=True, seed=7)
    return cv


# ---------------------------------------------------------------- animations
IDLE_FRAMES = 12
REST_GRIP = (-15.0, 40.0)
REST_ANG = 2.33


def idle_pose(i: int, n: int = IDLE_FRAMES) -> Pose:
    i %= n
    a = math.tau * i / n
    breath = round(1.0 * math.sin(a))
    lift = round(0.9 * math.sin(a - 0.4))
    glint = (i - 3) / 4 if 3 <= i <= 7 else -1.0
    return Pose(
        breath=breath, phase=a, sway=1.0,
        grip=(REST_GRIP[0], REST_GRIP[1] + lift), ang=REST_ANG + 0.012 * lift, edge=-1,
        eye=0.75 if i in (8, 9) else 1.0, glint=glint,
    )


def idle_frames():
    return [(idle_pose(i), 120) for i in range(IDLE_FRAMES)]


def attack_frames():
    """Hachazo: haul the axe over the right shoulder, heavy diagonal swing down-left."""
    b = idle_pose(0)
    up1 = (6.0, 60.0, -0.85)
    up2 = (10.0, 64.0, -0.45)
    mid = (-26.0, 58.0, -2.75)
    hit = (-36.0, 38.0, 2.62)
    return [
        (replace(b, lean=2, grip=(0.0, 50.0), ang=-1.3, edge=1, far_s=-9, eye=1.15,
                 phase=0.3, glint=-1), 110),
        (replace(b, lean=4, breath=1, sy=1.02, grip=up1[:2], ang=up1[2], edge=1, far_s=-9,
                 eye=1.35, phase=0.6, glint=-1), 130),
        (replace(b, lean=5, breath=1, sy=1.03, grip=up2[:2], ang=up2[2], edge=1, far_s=-9,
                 eye=1.5, phase=0.8, glint=0.5), 150),
        (replace(b, dx=-4, lean=-6, sx=1.03, grip=mid[:2], ang=mid[2], edge=1, far_s=-9,
                 eye=1.5, phase=1.2, smear=(up2,), glint=-1), 55),
        (replace(b, dx=-6, lean=-9, sy=0.96, sx=1.04, grip=hit[:2], ang=hit[2], edge=1, far_s=-9,
                 eye=1.4, phase=1.5, smear=(up2, mid), spark=(-72.0, 20.0, 0.15, math.pi + 0.3),
                 glint=-1), 65),
        (replace(b, dx=-6, lean=-9, sy=0.96, sx=1.03, grip=(-37.0, 36.0), ang=2.58, edge=1,
                 far_s=-9, eye=1.25, phase=1.9, smear=(up2, mid), smear_fade=0.55,
                 spark=(-72.0, 20.0, 0.5, math.pi + 0.3)), 90),
        (replace(b, dx=-4, lean=-6, grip=(-30.0, 37.0), ang=2.45, edge=1, far_s=-9, eye=1.1,
                 phase=2.5, spark=(-72.0, 20.0, 0.85, math.pi + 0.3)), 100),
        (replace(b, dx=-2, lean=-3, grip=(-23.0, 39.0), ang=2.3, edge=-1, phase=3.3), 100),
        (replace(b, dx=-1, lean=-1, grip=(-19.0, 40.0), ang=2.22, edge=-1, phase=4.4), 95),
        (b, 110),
    ]


def behead_frames():
    """Decapitar: raise the axe high overhead, then a vertical chop into the floor."""
    b = idle_pose(0)
    over = (-14.0, 92.0, 0.25)
    mid = (-22.0, 74.0, -2.35)
    hit = (-40.0, 20.0, 2.98)
    imp = (-82.0,)
    return [
        (replace(b, lean=1, grip=(-12.0, 62.0), ang=-2.0, edge=1, far_s=-9, eye=1.1,
                 phase=0.3, glint=-1), 120),
        (replace(b, lean=3, breath=1, sy=1.02, grip=(-13.0, 86.0), ang=-0.35, edge=1, far_s=9,
                 pole_f=(-12.0, -4.0), pole_b=(14.0, -2.0), far_behind=True, eye=1.35, phase=0.6), 130),
        (replace(b, lean=5, breath=1, sy=1.04, grip=over[:2], ang=over[2], edge=1, far_s=9,
                 pole_f=(-12.0, -4.0), pole_b=(14.0, -2.0), far_behind=True, eye=1.6, phase=0.9, glint=0.4), 170),
        (replace(b, lean=6, breath=1, sy=1.05, grip=(-13.0, 93.0), ang=0.31, edge=1, far_s=9,
                 pole_f=(-12.0, -4.0), pole_b=(14.0, -2.0), far_behind=True, eye=1.8, phase=1.1, glint=0.8), 200),
        (replace(b, dx=-4, lean=-8, sy=1.0, grip=mid[:2], ang=mid[2], edge=1, far_s=-9,
                 eye=1.8, phase=1.4, smear=(over,)), 50),
        (replace(b, dx=-8, lean=-14, sy=0.9, sx=1.06, grip=hit[:2], ang=hit[2], edge=1, far_s=-9,
                 eye=1.7, phase=1.7, smear=(over, mid), impact=(imp[0], 0.12, 0.0), dust=0.5), 70),
        (replace(b, dx=-8, lean=-14, sy=0.91, sx=1.05, grip=hit[:2], ang=hit[2], edge=1, far_s=-9,
                 eye=1.5, phase=2.0, smear=(over, mid), smear_fade=0.6,
                 impact=(imp[0], 0.45, 0.0), dust=0.85), 110),
        (replace(b, dx=-7, lean=-12, sy=0.93, sx=1.04, grip=(-39.0, 21.0), ang=2.95, edge=1,
                 far_s=-9, eye=1.3, phase=2.5, impact=(imp[0], 0.8, 0.35), dust=1.0), 130),
        (replace(b, dx=-5, lean=-8, sy=0.96, sx=1.02, grip=(-32.0, 28.0), ang=2.7, edge=1, far_s=-9,
                 eye=1.15, phase=3.1, impact=(imp[0], 1.0, 0.7)), 130),
        (replace(b, dx=-3, lean=-4, sy=0.98, grip=(-24.0, 35.0), ang=2.4, edge=-1, phase=3.8,
                 impact=(imp[0], 1.0, 0.9)), 120),
        (replace(b, dx=-1, lean=-1, grip=(-19.0, 39.0), ang=2.24, edge=-1, phase=4.7), 110),
        (b, 120),
    ]


def sharpen_frames():
    """Afilar: the axe stands up in front, the near hand drags a whetstone along the edge."""
    b = idle_pose(0)
    hold = dict(grip=(-4.0, 35.0), ang=-2.22)

    def stone_pose(k, s, sp, hone, phase, eye=1.1):
        q = replace(b, lean=-2, grip=hold["grip"], ang=hold["ang"], edge=1, far_s=0.0,
                    stone=s, hone_sparks=sp, hone=hone, phase=phase, eye=eye, glint=-1,
                    pole_b=(14.0, 8.0), axe_front=True)
        pts = _edge_points(q)
        i = max(0, min(len(pts) - 1, int(round(s * (len(pts) - 1)))))
        ex, ey = pts[i]
        return replace(q, hand_f=(ex + 3 - CX, GROUND - ey), )

    out = [
        (replace(b, lean=-1, grip=(-10.0, 38.0), ang=-2.5, edge=1, far_s=-6, eye=1.0, phase=0.3,
                 glint=-1), 110),
        (stone_pose(0, 0.02, -1.0, 0.0, 0.6), 120),
    ]
    strokes = [(0.25, 0.1, 0.2), (0.55, 0.45, 0.4), (0.9, 0.8, 0.6), (0.3, 0.25, 0.65),
               (0.65, 0.6, 0.85), (1.0, 0.95, 1.0)]
    for k, (s, sp, hone) in enumerate(strokes):
        out.append((stone_pose(k, s, sp, hone, 0.9 + 0.35 * k, eye=1.1 + 0.1 * (k % 2)), 85))
    out += [
        (replace(b, lean=-1, grip=hold["grip"], ang=hold["ang"], edge=1, far_s=-1.5, 
                 hand_f=(-14.0, 52.0), hone=1.1, glint=0.5, eye=1.3, phase=3.2), 150),
        (replace(b, lean=-1, grip=(-10.0, 38.0), ang=-2.5, edge=1, far_s=-6, hone=0.6, eye=1.1,
                 phase=3.8), 100),
        (replace(b, grip=(-18.0, 40.0), ang=2.3, edge=-1, hone=0.25, phase=4.6), 100),
        (b, 110),
    ]
    return out


def _edge_points(p: Pose):
    gx, gy = CX + p.dx + p.grip[0] * p.sx, GROUND + p.dy - p.grip[1]
    return edge_points(p, (gx, gy))


def cast_frames():
    """Sentencia / Sed de Sangre: point the axe at the hero; eyes, sigil and aura flare."""
    b = idle_pose(0)
    plan = [  # (point, sigil, aura, eye)
        (0.4, 0.0, 0.0, 1.2), (1.0, 0.3, 0.3, 1.5), (1.0, 0.8, 0.8, 1.8), (1.0, 1.1, 1.0, 1.9),
        (1.0, 1.0, 0.6, 1.7), (1.0, 0.9, 0.9, 1.7), (0.9, 0.6, 0.4, 1.4), (0.5, 0.2, 0.1, 1.15),
    ]
    out = []
    for k, (pt, sg, au, ey) in enumerate(plan):
        g = (lerp(REST_GRIP[0], -33.0, pt), lerp(REST_GRIP[1], 50.0, pt))
        out.append((replace(
            b, lean=-round(3 * pt), grip=g, ang=lerp(REST_ANG, math.pi + 0.06, pt), edge=1 if pt > 0.6 else -1,
            hand_b=(lerp(-11.0, 2.0, pt), lerp(46.0, 48.0, pt)) if pt > 0.3 else None, 
            eye=ey, sigil=sg, aura=au, phase=0.45 * k, glint=0.9 if k == 3 else -1), 95 if k else 110))
    out.append((b, 110))
    return out


def hurt_frames():
    b = idle_pose(0)
    return [
        (replace(b, dx=3, lean=4, sx=0.98, flash=0.82, eye=0.4, bow=-1, grip=(-13.0, 42.0),
                 ang=2.1, phase=0.8, dust=0.3), 60),
        (replace(b, dx=4, lean=4, flash=0.5, eye=0.6, bow=-1, grip=(-12.0, 42.0), ang=2.1,
                 phase=1.4, dust=0.6), 70),
        (replace(b, dx=3, lean=2, flash=0.18, eye=0.85, grip=(-14.0, 41.0), ang=2.14, phase=2.0,
                 dust=0.85), 80),
        (replace(b, dx=1, lean=1, grip=(-16.0, 40.0), ang=2.16, phase=2.8), 90),
        (replace(b, lean=0, phase=3.6), 95),
        (b, 105),
    ]


def death_frames():
    b = idle_pose(0)
    out = [
        (replace(b, dx=3, lean=4, flash=0.85, eye=0.5, grip=(-13.0, 42.0), ang=2.1), 70),
        (replace(b, dx=3, lean=2, flash=0.3, eye=1.7, sy=1.02, grip=(-15.0, 44.0), ang=2.1,
                 phase=0.5), 110),
    ]
    steps = 5
    for k in range(steps):                                  # drops to his knees, axe falls
        u = smooth((k + 1) / steps)
        ang = lerp(2.15, math.pi - 0.02, u)
        head_x, head_h = -42.0, 6.0
        g = (head_x - math.cos(ang) * HEAD_S, head_h + math.sin(ang) * HEAD_S * (1 - u) - 4 * u)
        g = (g[0], max(3.0, g[1]))
        out.append((replace(
            b, kneel=u, lean=-3 * u, bow=3 * u, eye=1.4 - 0.9 * u, grip=g, ang=ang, edge=-1,
            hand_f=(lerp(-17, -22, u), lerp(40, 22, u)), hand_b=(lerp(-11, 13, u), lerp(46, 24, u)),
            dust=0.5 * u if k > 2 else 0.0, phase=0.5 + 0.3 * k), 90 + 15 * k))
    kneeling = out[-1][0]
    for k, d in enumerate((0.15, 0.32, 0.5, 0.68, 0.84, 0.95)):
        motes = tuple((CX - 34 + hash01(k, j, 51) * 64, GROUND - 10 - hash01(j, k, 52) * (30 + 50 * d),
                       (hash01(j, k, 53) * 6)) for j in range(8 + 3 * k))
        out.append((replace(kneeling, dissolve=d, eye=0.3 * (1 - d), motes=motes, dust=0.0,
                            phase=2.0 + 0.3 * k), 90))
    out.append((replace(kneeling, dissolve=1.0), 140))
    return out


ANIMATIONS = {
    "idle": (idle_frames, True),
    "attack": (attack_frames, False),
    "behead": (behead_frames, False),
    "sharpen": (sharpen_frames, False),
    "cast": (cast_frames, False),
    "hurt": (hurt_frames, False),
    "death": (death_frames, False),
}

# Frames where a blow lands.
EVENTS = {"attack": {"strikes": [4]}, "behead": {"strikes": [5]}}
MOVES = {"chop": "attack", "behead": "behead", "sharpen": "sharpen", "sentence": "cast",
         "bloodlust": "cast", "vengeance": "cast"}


def build():
    return build_sheet(ANIMATIONS, render, (CELL_W, CELL_H), ANCHOR, f"{SHEET_ID}_sheet.png",
                       {"events": EVENTS, "moves": MOVES, "boss": True, "elite": True})


def main() -> None:
    sheet, meta = build()
    save_sheet(OUT_DIR, SHEET_ID, sheet, meta)
    print(f"wrote assets/enemies/{SHEET_ID}_sheet.png ({len(sheet[0])}x{len(sheet)}) and .json")


if __name__ == "__main__":
    main()
