"""Draw and animate the enemy "Diablillo" (an imp). Stdlib only:

    python scripts/generate_enemy_imp.py

Same method as the Espectro (``docs/code-drawn-sprites.md``): one renderer, every
frame a ``Pose``. A small, wiry, hovering imp — a lively red creature with limbs,
the fire lives only in its hands and eyes (unlike the Cráneo Ígneo):

* head + torso are ONE row-scanned mass: a big round head with a pointed chin and
  a little nose, a skinny chest and a pot belly; crimson skin hue-shifted to
  purple in the shadows, lit from the upper left;
* long pointed ears and two curved black horns, glowing yellow eyes and a huge
  grin full of tiny teeth;
* skinny arms and dangling legs (shaded tubes, rimmed where they cross the body)
  with long black claws; small flames flicker in its palms;
* small bat wings flapping fast on the back and a long thin tail with a spade tip
  whipping in an S behind it (right side).

Animations (non-death actions end on idle frame 0):
  idle      12-frame hover: bob, fast wing flutter, S tail, claws flex, ears twitch, grin
  attack    "Zarpazos": crouch, dash left, three alternating claw slashes, zip back
  fireball  "Bola de Fuego": conjures a fireball between its hands, throws it left, burst
  cast      "Burla": laughs (bounce, belly shake), hand and horn flames flare, fiery aura
  hurt      white flash, knocked right with a twist, angry face, then grins again
  death     shriek, swell, burst into black smoke and red embers; the horns fall; empty

Output: ``assets/enemies/imp_sheet.png`` + ``.json`` (``events.<anim>.strikes``).
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
SHEET_ID = "imp"

CELL_W, CELL_H = 160, 108
CX, GROUND = CELL_W - 48, 100     # body centre line, floor row
ANCHOR = (CX, GROUND + 2)         # floor point under the imp (its shadow)
HOVER = 16                        # feet float this high above the floor
BASE_Y = GROUND - HOVER           # row of the feet (h = 0)
HC, RY, RX = 33.5, 8.0, 10.5       # head centre height, half height, half width
HEAD_DX = -1.0                    # the big head sits a little forward (towards the hero)

# ---------------------------------------------------------------- palette
OUTLINE = (30, 6, 22)
SKIN = [(44, 10, 42), (72, 14, 52), (110, 20, 56), (152, 30, 52), (194, 48, 48), (230, 88, 62),
        (252, 146, 100)]
INNER = (96, 18, 58)              # inside the ears
WING = [(30, 10, 34), (52, 16, 46), (80, 24, 56), (112, 36, 64), (148, 54, 72)]
HORN = [(12, 8, 16), (30, 22, 34), (58, 46, 62), (104, 92, 110)]
FIRE = [(118, 22, 16), (200, 60, 20), (246, 128, 32), (255, 200, 70), (255, 244, 170)]
MOUTH = (34, 4, 18)
TEETH = (246, 238, 214)
TONGUE = (178, 44, 74)
SMOKE = [(22, 16, 26), (44, 36, 50), (70, 60, 76), (106, 94, 110)]
WHITE = (255, 255, 255)


@dataclass(frozen=True)
class Pose:
    dx: float = 0.0
    dy: float = 0.0
    lean: float = 0.0             # head offset vs hips (negative = towards the hero)
    sx: float = 1.0               # squash / stretch about the feet
    sy: float = 1.0
    phase: float = 0.0            # tail / legs / flame wave
    sway: float = 1.0             # tail S amplitude
    wing: float = 0.0             # -1 down-stroke .. 1 up-stroke
    hand_f: tuple[float, float] = (-13.0, 16.0)   # front hand (rel. CX, height above the feet)
    hand_b: tuple[float, float] = (11.0, 17.0)    # back hand
    claw: float = 0.5             # 0 curled .. 1 spread
    ear: float = 0.0              # ear twitch
    mood: str = "grin"            # grin | angry | laugh | shriek
    grin: float = 0.6             # grin width / openness
    eye: float = 1.0
    fire: float = 0.6             # palm flames
    flare: float = 0.0            # horn flames (taunt)
    aura: float = 0.0             # fiery aura around the silhouette
    flash: float = 0.0
    dissolve: float = 0.0
    slash: float = 0.0            # claw-arc progress
    slash_kind: int = 1           # 1 down, 2 up (back claw), 3 wide sweep
    slash_fade: float = 0.0
    streak: float = 0.0           # dash speed lines (length, px)
    ball: float = 0.0             # fireball size 0..1
    ball_pos: tuple[float, float] = (-14.0, 24.0)  # rel. CX, height above the feet
    ball_trail: float = 0.0
    burst: float = 0.0            # fireball burst progress
    burst_fade: float = 0.0
    burst_pos: tuple[float, float] = (-94.0, 22.0)
    gone: bool = False            # death: the body has burst into smoke
    smoke: float = 0.0            # death smoke puff progress
    horns: bool = True            # death: horns still visible
    horns_drop: float = 0.0
    horns_rot: float = 0.0
    motes: tuple = field(default_factory=tuple)


class Body:
    def __init__(self, p: Pose) -> None:
        self.p = p

    def center(self, h: float) -> float:
        p = self.p
        k = max(0.0, min(1.2, (h - 10) / 30))
        return CX + p.dx + p.lean * k ** 1.2

    def y_of(self, h: float) -> float:
        return BASE_Y + self.p.dy - h * self.p.sy

    def h_of(self, y: float) -> float:
        return (BASE_Y + self.p.dy - y) / self.p.sy

    def to_cell(self, lx: float, h: float) -> tuple[float, float]:
        return self.center(h) + lx * self.p.sx, self.y_of(h)

    def head_x(self) -> float:
        return self.center(HC) + HEAD_DX * self.p.sx

    def head(self, lx: float, lh: float) -> tuple[float, float]:
        """Head-local (offset from the head centre) -> cell."""
        return self.head_x() + lx * self.p.sx, self.y_of(HC + lh)

    def hand(self, hand) -> tuple[float, float]:
        p = self.p
        return CX + p.dx + hand[0] * p.sx, BASE_Y + p.dy - hand[1] * p.sy


def _clamp(v: float) -> float:
    return max(0.0, min(1.0, v))


def _ip(v: float) -> int:
    return int(math.floor(v))


# ---------------------------------------------------------------- one mass: head + torso
def torso_ext(h: float):
    """(left, right) half extents of the torso at height ``h`` or None."""
    if h < 9.5 or h > 28.0:
        return None
    if h < 13:                                           # rounded hips
        w = 3.0 + 2.5 * smooth((h - 9.5) / 3.5)
        return w, w
    if h < 21:                                           # pot belly (front = left)
        s = math.sin(math.pi * (h - 13) / 8)
        return 5.5 + 2.2 * s, 5.5 + 0.3 * s
    if h < 25:                                           # skinny chest / shoulders
        w = 5.5 + 1.2 * math.sin((h - 21) / 4 * math.pi / 2)
        return w, w
    w = 6.7 - 4.0 * smooth((h - 25) / 3)                 # shoulders slope to the neck
    return w, w


def head_ext(lh: float):
    """(left, right, shift, half) offsets of the head row ``lh`` from the head centre, or None."""
    vy = lh / RY
    if abs(vy) > 1:
        return None
    w = RX * math.sqrt(1 - vy * vy)
    shift = 0.0
    if vy < 0:                                           # jaw narrows, chin juts forward
        w *= 1 - 0.30 * vy * vy
        shift = -1.9 * (-vy) ** 1.5
    left, right = shift - w, shift + w
    if -2.2 < lh < 0.6:                                  # little pointed nose
        left -= 1.4 * max(0.0, 1 - abs(lh + 0.8) / 1.4)
    return left, right, shift, max(1.0, w)


def draw_mass(cv: Canvas, b: Body) -> None:
    p = b.p
    hx = b.head_x()
    for y in range(CELL_H):
        h = b.h_of(y + 0.5)
        lh = h - HC
        he = head_ext(lh)
        te = torso_ext(h)
        if he is None and te is None:
            continue
        c = b.center(h)
        spans = []
        if te is not None:
            spans.append((c - te[0] * p.sx, c + te[1] * p.sx))
        if he is not None:
            spans.append((hx + he[0] * p.sx, hx + he[1] * p.sx))
        x0 = _ip(min(s[0] for s in spans)) - 1
        x1 = _ip(max(s[1] for s in spans)) + 1
        for x in range(max(0, x0), min(CELL_W, x1 + 1)):
            xc = x + 0.5
            if he is not None and hx + he[0] * p.sx <= xc <= hx + he[1] * p.sx:
                nx = (xc - hx - he[2] * p.sx) / (he[3] * p.sx)
                ny = lh / RY
                light = 0.60 - 0.30 * nx + 0.24 * ny - 0.14 * nx * nx
                if nx < -0.72 and ny > -0.45:
                    light += 0.16                         # lit rim on the forehead / cheek
                if nx > 0.82:
                    light -= 0.12
                if ny < -0.62:
                    light -= 0.12                         # under the jaw
                if -0.15 < ny < 0.35 and -0.95 < nx < 0.25:
                    light -= 0.08                         # eye sockets
                if 0.35 <= ny < 0.55 and nx < 0.3:
                    light += 0.07                         # brow ridge
                cv.put(x, y, ramp(SKIN, _clamp(light), x, y))
            elif te is not None and c - te[0] * p.sx <= xc <= c + te[1] * p.sx:
                u = (xc - c) / ((te[0] if xc < c else te[1]) * p.sx)
                v = (h - 9.5) / 18.5
                light = 0.56 - 0.34 * u + 0.10 * v
                if abs(u) > 0.82:
                    light -= 0.13
                if u < -0.74:
                    light += 0.14
                if 13 < h < 21:
                    light += 0.08 * (1 - abs(u))          # round belly
                if 13 < h < 14.2 and u < 0.5:
                    light -= 0.18                         # belly crease
                if 21 < h < 24.5 and 0.2 < u < 0.75 and int(h) % 2 == 0:
                    light -= 0.12                         # ribs
                if h > 22.5:
                    light -= 0.24 * smooth((h - 22.5) / 3)    # the head's shadow
                cv.put(x, y, ramp(SKIN, _clamp(light), x, y))
    nx_, ny_ = b.to_cell(-2.5, 16)                        # navel
    cv.put(_ip(nx_), _ip(ny_), SKIN[1])


# ---------------------------------------------------------------- face
def draw_face(cv: Canvas, b: Body) -> tuple[tuple[float, float], tuple[float, float]]:
    """Eyes, brows and mouth on the head. Returns both eye centres."""
    p = b.p

    def put(lx, lh, col):
        x, y = b.head(lx, lh)
        cv.put(_ip(x), _ip(y), col)

    fe, be = (-6.0, 1.3), (0.6, 1.3)
    e = max(0.0, p.eye)
    hot = FIRE[4] if e > 0.6 else FIRE[3]
    warm = FIRE[3] if e > 0.6 else FIRE[2]
    dark = OUTLINE
    # eyes
    if p.mood == "laugh":                                    # squeezed ^ ^
        for (ex, eh) in (fe, be):
            for ox, oh, col in ((-1, 0, warm), (0, 1, hot), (1, 0, warm)):
                put(ex + ox, eh + oh, col)
    elif p.mood == "shriek":                                 # wide round eyes
        for (ex, eh) in (fe, be):
            for ox in (-1, 0, 1):
                for oh in (-1, 0, 1):
                    edge = abs(ox) + abs(oh) == 2
                    if edge:
                        continue
                    put(ex + ox, eh + oh, hot if (ox, oh) == (0, 0) else warm)
    else:
        # front eye: outer corner (left) raised, pupil looking at the hero
        for ox, oh, col in ((-3, 1, warm), (-2, 1, hot), (-1, 1, hot), (0, 1, hot), (-2, 0, dark),
                            (-1, 0, hot), (0, 0, hot), (1, 0, warm)):
            put(fe[0] + ox, fe[1] + oh, col)
        for ox, oh, col in ((-1, 1, hot), (0, 1, warm), (1, 1, warm), (-1, 0, dark), (0, 0, hot)):
            put(be[0] + ox, be[1] + oh, col)
        if e > 1.15:
            put(fe[0] - 3, fe[1] + 2, FIRE[2])
            put(be[0] + 2, be[1] + 2, FIRE[2])
    # brows
    if p.mood == "angry":
        brows = (((-4, 3), (-3, 3), (-2, 3), (-1, 2), (0, 2), (1, 1)), ((0, 1), (1, 2), (2, 3)))
    elif p.mood == "laugh":
        brows = (((-3, 3), (-2, 4), (-1, 4), (0, 3)), ((0, 3), (1, 4), (2, 3)))
    elif p.mood == "shriek":
        brows = (((-3, 3), (-2, 3), (-1, 3)), ((0, 3), (1, 3)))
    else:                                                    # mischievous: outer ends up
        brows = (((-4, 4), (-3, 3), (-2, 3), (-1, 3), (0, 2)), ((0, 2), (1, 3), (2, 3)))
    for (ex, eh), line in zip((fe, be), brows):
        for ox, oh in line:
            put(ex + ox, eh + oh - 1, dark)
    # mouth
    mx, mh = -3.4, -3.6
    if p.mood == "shriek":
        for oh in range(-3, 2):
            half = 2.6 * math.sqrt(max(0.0, 1 - ((oh + 1) / 2.8) ** 2))
            for ox in range(-3, 4):
                if abs(ox) > half:
                    continue
                col = MOUTH
                if oh == 1 and ox % 2 == 0:
                    col = TEETH
                elif oh == -3 and ox % 2 == 1:
                    col = TEETH
                elif oh == -2 and ox == 0:
                    col = TONGUE
                put(mx + ox, mh + oh, col)
        return b.head(*fe), b.head(*be)
    hw = 5.5 + 0.8 * p.grin
    if p.mood == "laugh":
        hw = 6.4
    for ox in range(-int(hw), int(hw) + 1):
        t = ox / hw
        if p.mood == "angry":
            lift = -round(1.0 * t * t)                      # grimace: corners down
            th = 2
        elif p.mood == "laugh":
            lift = round(1.6 * t * t)
            th = 1 + round(2.6 * (1 - t * t))
        else:
            lift = round(2.2 * t * t)
            th = 1 + round(p.grin * 1.4 * (1 - t * t))
        top = mh + lift
        for k in range(th):
            if k == 0:
                col = TEETH if (ox % 2 == 0 and abs(t) < 0.9) else MOUTH
            elif k == th - 1 and th >= 2:
                col = TEETH if (ox % 2 == 1 and abs(t) < 0.8) else MOUTH
            else:
                col = TONGUE if (p.mood == "laugh" and abs(ox) < 2 and k == th - 2) else MOUTH
            put(mx + ox, top - k, col)
        if abs(t) > 0.95:
            put(mx + ox, top + 1, SKIN[2])                  # dimples at the corners
    put(mx - hw - 1, mh + round(2.2) + 1, SKIN[6])          # cheek highlight
    return b.head(*fe), b.head(*be)


# ---------------------------------------------------------------- ears and horns
def draw_ear(cv: Canvas, b: Body, front: bool) -> None:
    p = b.p
    tw = p.ear
    if front:
        pts = [b.head(-6.5, 2.0), b.head(-12.0, 4.0 + tw), b.head(-17.5 - tw, 7.5 + 2.5 * tw)]
    else:
        pts = [b.head(5.5, 2.5), b.head(10.5, 4.6 + 0.5 * tw), b.head(15.0 + 0.5 * tw, 8.0 + 1.5 * tw)]
    path = bezier(pts[0], pts[1], pts[2], 18)
    stroke(cv, path, lambda t: 2.7 * (1 - t) ** 0.9 + 0.35, SKIN[1:6] if front else SKIN[1:5],
           shade=0.0 if front else -0.12)
    for i in range(3, 12):                                   # dark inner ear
        x, y = path[i]
        cv.put(_ip(x), _ip(y + 0.8), INNER)


def horn_points(b: Body, front: bool):
    p = b.p
    if front:
        pts = [b.head(-3.6, 6.0), b.head(-6.0, 10.8), b.head(-0.8, 12.6)]
    else:
        pts = [b.head(3.2, 6.0), b.head(3.6, 10.4), b.head(8.2, 11.6)]
    path = bezier(pts[0], pts[1], pts[2], 16)
    if p.horns_rot or p.horns_drop:
        ox, oy = path[0]
        ca, sa = math.cos(p.horns_rot), math.sin(p.horns_rot)
        drift = (-1.0 if front else 1.0) * p.horns_drop * 0.25
        path = [(ox + (x - ox) * ca - (y - oy) * sa + drift, oy + (x - ox) * sa + (y - oy) * ca + p.horns_drop)
                for x, y in path]
    return path


def draw_horn(cv: Canvas, b: Body, front: bool) -> None:
    path = horn_points(b, front)
    tube = stroke(cv, path, lambda t: 2.1 * (1 - t) + 0.35, HORN, shade=0.0 if front else -0.12,
                  rim=OUTLINE if front else None)
    # ridges along the horn
    for i in (4, 8):
        x, y = path[i]
        if tube.get(_ip(x) + 1, _ip(y)) is not None:
            cv.put(_ip(x) + 1, _ip(y), HORN[0])


# ---------------------------------------------------------------- limbs
def draw_leg(cv: Canvas, b: Body, front: bool) -> None:
    p = b.p
    sw = 0.8 * math.sin(p.phase + (0.0 if front else 1.7))
    if front:
        pts = [b.to_cell(-2.4, 11), b.to_cell(-9.0 + sw, 8.0), b.to_cell(-5.0 + sw * 0.6, 2.5),
               b.to_cell(-6.5 + sw * 0.6, -0.5)]
    else:
        pts = [b.to_cell(2.4, 11), b.to_cell(-2.0 + sw, 6.5), b.to_cell(2.2 + sw * 0.6, 1.5),
               b.to_cell(1.2 + sw * 0.6, -1.5)]
    path = bezier(pts[0], pts[1], pts[2], 14) + bezier(pts[2], ((pts[2][0] + pts[3][0]) / 2,
                                                                 (pts[2][1] + pts[3][1]) / 2), pts[3], 5)
    stroke(cv, path, lambda t: 1.8 - 1.0 * t, SKIN[1:6] if front else SKIN[0:5],
           shade=0.0 if front else -0.14, rim=OUTLINE if front else None)
    x, y = pts[3]
    cv.put(_ip(x) - 1, _ip(y) + 1, HORN[1])                 # toe claw


def draw_arm(cv: Canvas, b: Body, front: bool, hand) -> tuple[float, float, float, float]:
    """Skinny arm + long black claws. Returns the palm point and the hand direction."""
    p = b.p
    side = -1 if front else 1
    sh = b.to_cell(side * 5.0, 24.0)
    hx, hy = b.hand(hand)
    el = ((sh[0] + hx) / 2 + side * 2.6, (sh[1] + hy) / 2 + 2.6)
    n = int(math.hypot(hx - sh[0], hy - sh[1]) * 1.5) + 4
    pts = bezier(sh, el, (hx, hy), n)
    stroke(cv, pts, lambda t: 1.75 - 0.7 * t + 0.9 * max(0.0, t - 0.82) / 0.18,
           SKIN[1:6] if front else SKIN[0:5], shade=0.0 if front else -0.14,
           rim=OUTLINE if front else None)
    dx, dy = hx - el[0], hy - el[1]
    L = max(0.5, math.hypot(dx, dy))
    dx, dy = dx / L, dy / L
    base = math.atan2(dy, dx)
    for a, ln in ((-0.6, 5.0), (0.0, 7.0), (0.6, 5.5)):
        ang = base + a * (0.45 + 0.9 * p.claw)
        curl = 0.55 * (1 - p.claw) * (-side)
        x, y = hx + dx, hy + dy
        for s in range(int(ln)):
            ang2 = ang + curl * s / ln
            x += math.cos(ang2)
            y += math.sin(ang2)
            col = HORN[3] if s < ln - 2 else HORN[2]
            if not front:
                col = HORN[2] if s < ln - 2 else HORN[1]
            cv.put(_ip(x), _ip(y), col, solid=s == 0)
    return hx, hy, dx, dy


# ---------------------------------------------------------------- wings and tail
def _inside(poly, x: float, y: float) -> bool:
    inside = False
    n = len(poly)
    j = n - 1
    for i in range(n):
        xi, yi = poly[i]
        xj, yj = poly[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


def draw_wing(cv: Canvas, b: Body, near: bool) -> None:
    p = b.p
    root = b.to_cell(4.0 if near else 2.0, 23.0 if near else 24.0)
    flap = max(-1.0, min(1.0, p.wing))
    base = -40.0 - 30.0 * flap + (0.0 if near else -28.0)
    sc = 1.0 if near else 0.78
    th = math.radians(base)
    wx, wy = root[0] + math.cos(th) * 11.0 * sc, root[1] + math.sin(th) * 11.0 * sc
    tips = []
    for rel, ln in ((-52.0, 13.0), (-6.0, 16.0), (40.0, 12.5)):
        a = math.radians(base + rel * (0.8 + 0.2 * flap) + 6.0 * flap)
        tips.append((wx + math.cos(a) * ln * sc, wy + math.sin(a) * ln * sc))
    attach = b.to_cell(6.0, 13.5)

    def scallop(a, c):
        ctrl = ((a[0] + c[0]) / 2 * 0.6 + wx * 0.4, (a[1] + c[1]) / 2 * 0.6 + wy * 0.4)
        return bezier(a, ctrl, c, 8)[1:-1]

    poly = [root, (wx, wy), tips[0]] + scallop(tips[0], tips[1]) + [tips[1]] + scallop(tips[1], tips[2]) \
        + [tips[2]] + scallop(tips[2], attach) + [attach]
    wcv = Canvas(cv.w, cv.h)
    xs = [q[0] for q in poly]
    ys = [q[1] for q in poly]
    span = 16.0 * sc
    for y in range(max(0, _ip(min(ys))), min(cv.h, _ip(max(ys)) + 2)):
        for x in range(max(0, _ip(min(xs))), min(cv.w, _ip(max(xs)) + 2)):
            if not _inside(poly, x + 0.5, y + 0.5):
                continue
            d = math.hypot(x + 0.5 - wx, y + 0.5 - wy) / span
            light = 0.72 - 0.42 * d - 0.12 * (x + 0.5 - wx) / span
            if not near:
                light -= 0.2
            wcv.put(x, y, ramp(WING, _clamp(light), x, y, 0.3))
    bone = SKIN[1:5] if near else SKIN[0:4]
    stroke(wcv, [root, (wx, wy)], lambda t: 1.5 - 0.4 * t, bone, shade=0.05 if near else -0.15)
    for tip in tips:
        stroke(wcv, [(wx, wy), tip], lambda t: 1.0 - 0.5 * t, bone, shade=0.0 if near else -0.2,
               min_r=0.55)
    wcv.put(_ip(wx), _ip(wy) - 1, HORN[2])                   # thumb claw
    wcv.put(_ip(wx) - 1, _ip(wy) - 2, HORN[0])
    cv.blit(wcv, rim=OUTLINE)


def tail_points(b: Body):
    p = b.p
    rx, ry = b.to_cell(4.5, 12.5)
    pts = []
    n = 30
    for i in range(n + 1):
        s = i / n
        x = rx + 24.0 * s * p.sx + 1.6 * p.sway * math.cos(math.tau * s - p.phase) * s
        y = ry + 7.0 * math.sin(math.pi * s) - 9.0 * s * s + 3.4 * p.sway * math.sin(math.tau * s - p.phase) * s
        pts.append((x, y))
    return pts


def draw_tail(cv: Canvas, b: Body) -> None:
    pts = tail_points(b)
    stroke(cv, pts, lambda t: 1.6 - 0.8 * t, SKIN[1:5], shade=-0.04, rim=OUTLINE)
    (x0, y0), (x1, y1) = pts[-3], pts[-1]
    L = max(0.5, math.hypot(x1 - x0, y1 - y0))
    dx, dy = (x1 - x0) / L, (y1 - y0) / L
    nx, ny = -dy, dx
    tip = (x1 + dx * 5.0, y1 + dy * 5.0)
    left = (x1 + nx * 3.0 - dx * 0.6, y1 + ny * 3.0 - dy * 0.6)
    notch = (x1 + dx * 0.9, y1 + dy * 0.9)
    right = (x1 - nx * 3.0 - dx * 0.6, y1 - ny * 3.0 - dy * 0.6)
    poly = [tip, left, notch, right]
    spade = Canvas(cv.w, cv.h)
    for y in range(_ip(min(q[1] for q in poly)) - 1, _ip(max(q[1] for q in poly)) + 2):
        for x in range(_ip(min(q[0] for q in poly)) - 1, _ip(max(q[0] for q in poly)) + 2):
            if not _inside(poly, x + 0.5, y + 0.5):
                continue
            side = ((x + 0.5 - x1) * nx + (y + 0.5 - y1) * ny) / 3.0
            light = 0.55 + 0.35 * side * (1 if nx < 0 else -1) - 0.1 * ((x + 0.5 - x1) * dx + (y + 0.5 - y1) * dy) / 5
            spade.put(x, y, ramp(SKIN[1:6], _clamp(light), x, y))
    cv.blit(spade, rim=OUTLINE)


# ---------------------------------------------------------------- fire effects
def draw_flame(cv: Canvas, x: float, y: float, size: float, phase: float, seed: int) -> None:
    """A small flickering flame rising from (x, y)."""
    if size <= 0.05:
        return
    fh = 2.0 + 5.0 * size
    hw = 1.3 + 1.3 * size
    for yy in range(_ip(y - fh) - 1, _ip(y) + 2):
        k = (y + 0.5 - yy) / fh                                # 0 base .. 1 tip
        if k < -0.25 or k > 1:
            continue
        wob = 0.9 * math.sin(2 * phase + seed + yy * 0.9) * max(0.0, k)
        w = hw * (1 - max(0.0, k) ** 1.3) * (1.0 if k >= 0 else 0.8)
        for xx in range(_ip(x - hw - 2), _ip(x + hw + 3)):
            d = abs(xx + 0.5 - x - wob) / max(0.3, w)
            if d > 1:
                continue
            if k > 0.75 and hash01(xx, yy, seed + int(4 + 3.9 * math.sin(phase))) < 0.3:
                continue
            lvl = 4 if d < 0.35 and k < 0.45 else 3 if d < 0.6 and k < 0.75 else 2 if d < 0.85 else 1
            cv.put(xx, yy, FIRE[lvl], solid=False)


def draw_fireball(cv: Canvas, x: float, y: float, r: float, phase: float, trail: float) -> None:
    if r <= 0.3:
        return
    if trail > 0:
        for k in range(10, 0, -1):
            tx = x + k * 2.6
            tr = r * (1 - k / 11) * 0.9
            ty = y + 0.6 * math.sin(phase + k)
            a = int(255 * trail * (1 - k / 11))
            for yy in range(_ip(ty - tr) - 1, _ip(ty + tr) + 2):
                for xx in range(_ip(tx - tr) - 1, _ip(tx + tr) + 2):
                    d = math.hypot(xx + 0.5 - tx, yy + 0.5 - ty) / max(0.4, tr)
                    if d > 1 or bayer(xx, yy) > 1.2 - d * 0.6 - k * 0.05:
                        continue
                    cv.put(xx, yy, FIRE[2] if k < 4 and d < 0.5 else FIRE[1] if k < 8 else FIRE[0],
                           solid=False, alpha=a)
    for yy in range(_ip(y - r) - 2, _ip(y + r) + 3):
        for xx in range(_ip(x - r) - 2, _ip(x + r) + 3):
            ddx, ddy = xx + 0.5 - x, yy + 0.5 - y
            ang = math.atan2(ddy, ddx)
            rr = r * (1 + 0.22 * math.sin(5 * ang + 2 * phase) * (0.5 + 0.5 * (ddx > 0)))
            d = math.hypot(ddx, ddy) / max(0.5, rr)
            if d > 1:
                continue
            lit = d - 0.25 * (-ddx - ddy) / max(1.0, r)          # hot core towards the upper left
            lvl = 4 if lit < 0.3 else 3 if lit < 0.58 else 2 if lit < 0.82 else 1 if d < 0.95 else 0
            cv.put(xx, yy, FIRE[lvl], solid=False)
    cv.glow(x, y, r * 2.4 + 2, FIRE[2], 0.35)


def draw_burst(cv: Canvas, x: float, y: float, prog: float, fade: float, phase: float) -> None:
    if prog <= 0:
        return
    R = 4 + 11 * smooth(min(1.0, prog))
    thick = 3.0 * (1 - fade) + 1
    for yy in range(_ip(y - R - 6), _ip(y + R + 6)):
        for xx in range(_ip(x - R - 6), _ip(x + R + 6)):
            ddx, ddy = xx + 0.5 - x, yy + 0.5 - y
            ang = math.atan2(ddy, ddx)
            spike = 3.5 * max(0.0, math.sin(8 * ang + 1.3)) * (1 - fade)
            d = math.hypot(ddx, ddy)
            if d > R + spike:
                continue
            inner = R - thick - (1 - fade) * R * 0.8
            if d < inner:
                core = 1 - fade * 1.3
                if bayer(xx, yy) < core:
                    cv.put(xx, yy, FIRE[4] if fade < 0.2 else FIRE[3] if fade < 0.5 else FIRE[2],
                           solid=False)
                continue
            k = (d - inner) / max(1.0, R + spike - inner)       # 0 inner .. 1 outer
            if fade > 0 and bayer(xx, yy) < fade * 0.9:
                if fade > 0.4 and hash01(xx, yy, 21) < 0.45:
                    cv.put(xx, yy, SMOKE[1 + (ddy < 0)], solid=False, alpha=int(200 * (1 - fade)))
                continue
            lvl = 4 if k < 0.25 else 3 if k < 0.5 else 2 if k < 0.75 else 1
            lvl = max(0, lvl - int(fade * 2.5))
            cv.put(xx, yy, FIRE[lvl], solid=False)
    for j in range(16):                                         # flying sparks
        a = hash01(j, 3, 11) * math.tau
        s = (0.6 + 0.6 * hash01(j, 4, 11)) * (R + 6 + 10 * fade)
        sx_, sy_ = x + math.cos(a) * s, y + math.sin(a) * s * 0.8 + 6 * fade * fade
        if fade < 0.9:
            cv.put(_ip(sx_), _ip(sy_), FIRE[3 if j % 3 else 4] if fade < 0.5 else FIRE[1], solid=False)
    if fade < 0.6:
        cv.glow(x, y, R + 8, FIRE[2], 0.45 * (1 - fade))


def draw_slash(cv: Canvas, cx: float, cy: float, kind: int, prog: float, fade: float) -> None:
    """Three parallel fiery claw trails."""
    if prog <= 0:
        return
    if kind == 1:
        a0, a1, base_r, sq = -1.6, -4.2, 13.0, 1.2              # downward, through the left
    elif kind == 2:
        a0, a1, base_r, sq = -4.5, -2.0, 12.0, 1.15             # upward backhand
    else:
        a0, a1, base_r, sq = -2.1, -4.1, 17.0, 1.5              # wide sweep
    a_end = a0 + (a1 - a0) * min(1.0, prog)
    steps = 110
    for line, (dr, thick) in enumerate(((0.0, 1), (3.5, 2), (7.0, 1))):
        for i in range(steps):
            t = i / (steps - 1)                                  # 1 = leading edge
            w = t - fade * 1.15
            if w <= 0:
                continue
            a = a0 + (a_end - a0) * t
            r = base_r + dr + 1.5 * math.sin(t * math.pi)
            x = cx + math.cos(a) * r * sq
            y = cy + math.sin(a) * r
            lv = 4 if w > 0.8 else 3 if w > 0.5 else 2 if w > 0.25 else 1
            alpha = int(255 * min(1.0, 0.3 + w * 1.1))
            for k in range(thick if w > 0.3 else 1):
                cv.put(_ip(x), _ip(y) + k, FIRE[lv], solid=False, alpha=alpha)
            if w > 0.92 and line == 1:
                cv.put(_ip(x) - 1, _ip(y), WHITE, solid=False)


def draw_streaks(cv: Canvas, b: Body, length: float) -> None:
    if length <= 0:
        return
    for k, h in enumerate((8, 15, 21, 27, 34, 40)):
        x0, y = b.to_cell(8 + 2 * (k % 2), h)
        ln = length * (0.6 + 0.4 * hash01(k, 1, 31))
        for i in range(int(ln)):
            a = int(200 * (1 - i / ln))
            cv.put(_ip(x0 + i), _ip(y), FIRE[1] if i < ln * 0.3 else SKIN[2], solid=False, alpha=a)


def draw_aura(cv: Canvas, strength: float, phase: float) -> None:
    """Flickering fire around the silhouette (taunt)."""
    if strength <= 0:
        return
    ring = {(x, y) for y in range(cv.h) for x in range(cv.w) if cv.px[y][x] is not None}
    seen = set(ring)
    for r in range(1, 5):
        nxt = set()
        for (x, y) in ring:
            for ox, oy in ((1, 0), (-1, 0), (0, 1), (0, -1), (0, -1)):
                q = (x + ox, y + oy - (1 if r > 2 else 0))
                if q in seen or not (0 <= q[0] < cv.w and 0 <= q[1] < cv.h):
                    continue
                seen.add(q)
                nxt.add(q)
        for (x, y) in nxt:
            f = 0.5 + 0.5 * math.sin(phase * 3 + x * 0.7 + y * 0.45)
            k = strength * (1.15 - r / 4.5) * (0.6 + 0.4 * f)
            if k < bayer(x, y) * 0.9:
                continue
            col = FIRE[3] if r == 1 else FIRE[2] if r == 2 else FIRE[1]
            cv.put(x, y, col, solid=False, alpha=int(255 * min(1.0, k + 0.2)))
        ring = nxt


def draw_smoke(cv: Canvas, cx: float, cy: float, s: float) -> None:
    """Death puff: black smoke billows out and fades, red embers fly."""
    if s <= 0:
        return
    dens = 1 - smooth(max(0.0, (s - 0.25) / 0.75))
    for k in range(10):
        a = hash01(k, 1, 41) * math.tau
        dist = (3 + 10 * hash01(k, 2, 41)) * (0.5 + 1.2 * s ** 0.6)
        px_ = cx + math.cos(a) * dist * 1.2
        py_ = cy + math.sin(a) * dist * 0.9 - 12 * s * s
        r = (5 + 4 * hash01(k, 3, 41)) * (0.7 + 0.9 * s ** 0.5)
        for yy in range(_ip(py_ - r) - 1, _ip(py_ + r) + 2):
            for xx in range(_ip(px_ - r) - 1, _ip(px_ + r) + 2):
                d = math.hypot(xx + 0.5 - px_, yy + 0.5 - py_) / r
                if d > 1:
                    continue
                if bayer(xx, yy) > dens * (1.5 - d) * 1.2:
                    continue
                lit = (-(xx + 0.5 - px_) - (yy + 0.5 - py_)) / r
                lvl = 3 if lit > 0.7 and d < 0.8 else 2 if lit > 0.1 else 1 if d < 0.85 else 0
                if s < 0.2 and d < 0.6:
                    col = FIRE[3] if d < 0.3 else FIRE[2]         # hot core of the pop
                elif s < 0.32 and d < 0.4:
                    col = FIRE[1]
                else:
                    col = SMOKE[lvl]
                cv.put(xx, yy, col, solid=False, alpha=int(255 * min(1.0, dens + 0.15)))
    for j in range(30):                                          # embers
        a = hash01(j, 5, 43) * math.tau
        sp = 10 + 26 * hash01(j, 6, 43)
        ex = cx + math.cos(a) * sp * s ** 0.7 * 1.2
        ey = cy + math.sin(a) * sp * s ** 0.7 - 14 * s * hash01(j, 7, 43)
        life = 0.55 + 0.45 * hash01(j, 8, 43)
        if s > life:
            continue
        col = FIRE[3] if s < 0.25 and j % 3 == 0 else FIRE[2] if j % 2 else FIRE[1]
        cv.put(_ip(ex), _ip(ey), col, solid=False)
        if j % 4 == 0 and s < 0.5:
            cv.put(_ip(ex) + 1, _ip(ey), FIRE[1], solid=False, alpha=150)


# ---------------------------------------------------------------- render
def render(p: Pose, t: float = 0.0) -> Canvas:
    cv = Canvas(CELL_W, CELL_H)
    if p.dissolve >= 1:
        return cv
    b = Body(p)
    eyes = None
    hands = []
    if not p.gone:
        draw_wing(cv, b, near=False)
        draw_wing(cv, b, near=True)
        draw_tail(cv, b)
        draw_leg(cv, b, front=False)
        hands.append(draw_arm(cv, b, False, p.hand_b))
        draw_ear(cv, b, front=False)
        draw_horn(cv, b, front=False)
        draw_ear(cv, b, front=True)
        draw_mass(cv, b)
        eyes = draw_face(cv, b)
        draw_leg(cv, b, front=True)
        draw_horn(cv, b, front=True)
        hands.append(draw_arm(cv, b, True, p.hand_f))
    elif p.horns:
        draw_horn(cv, b, front=False)
        draw_horn(cv, b, front=True)
    outline(cv, OUTLINE)
    flash(cv, p.flash)
    if not p.gone:
        draw_aura(cv, p.aura, p.phase)
        for k, (hx, hy, dx, dy) in enumerate(hands):
            draw_flame(cv, hx + dx * 1.5, hy - 0.5, p.fire * (0.8 if k == 0 else 1.0), p.phase, 3 + k * 5)
            if p.fire > 0.1:
                cv.glow(hx + dx, hy - 1, 3 + 3 * p.fire, FIRE[2], 0.3 * min(1.2, p.fire))
        if p.flare > 0:
            for front in (False, True):
                tx, ty = horn_points(b, front)[-1]
                draw_flame(cv, tx, ty + 1, p.flare, p.phase + 1.3, 9 + front)
                cv.glow(tx, ty, 4 + 3 * p.flare, FIRE[2], 0.3 * p.flare)
        e = p.eye
        if eyes and e > 0.05:
            for ex, ey in eyes:
                cv.glow(ex, ey, 3.5 + 1.5 * e, FIRE[3], 0.28 * e)
    draw_streaks(cv, b, p.streak)
    if p.slash > 0:
        sx_, sy_ = b.to_cell(-9, 22)
        draw_slash(cv, sx_, sy_, p.slash_kind, p.slash, p.slash_fade)
    if p.ball > 0:
        bx, by = CX + p.ball_pos[0], BASE_Y - p.ball_pos[1]
        draw_fireball(cv, bx, by, 1.2 + 3.8 * p.ball, p.phase, p.ball_trail)
    if p.burst > 0:
        draw_burst(cv, CX + p.burst_pos[0], BASE_Y - p.burst_pos[1], p.burst, p.burst_fade, p.phase)
    if p.smoke > 0:
        cx_, cy_ = b.to_cell(0, 24)
        draw_smoke(cv, cx_, cy_, p.smoke)
    for (mx, my, lv) in p.motes:
        cv.put(_ip(mx), _ip(my), FIRE[max(0, min(4, int(lv)))], solid=False)
    if p.dissolve > 0:
        dissolve(cv, p.dissolve, BASE_Y - 50, BASE_Y + 4, FIRE[3], FIRE[1], upward=True)
    return cv


# ---------------------------------------------------------------- animations
IDLE_FRAMES = 12


def idle_pose(i: int, n: int = IDLE_FRAMES) -> Pose:
    j = i % n
    a = math.tau * j / n
    return Pose(
        dy=-round(1.6 * math.sin(a)), phase=a, sway=1.0,
        wing=math.sin(3 * a + 0.4),
        hand_f=(-13.0 + 0.8 * math.sin(a + 0.5), 16.0 + 1.2 * math.sin(a + 1.2)),
        hand_b=(11.0 + 0.6 * math.sin(a + 2.0), 17.0 + 1.0 * math.sin(a + 1.8)),
        claw=0.5 + 0.35 * math.sin(a + 1.0),
        ear=1.0 if j in (4, 5) else 0.0,
        grin=0.5 + 0.5 * max(0.0, math.sin(a - 1.2)),
        fire=0.6 + 0.25 * math.sin(2 * a),
    )


def idle_frames():
    return [(idle_pose(i), 105) for i in range(IDLE_FRAMES)]


def attack_frames():
    """Zarpazos: crouch back, dash left, three alternating claw slashes, zip back."""
    b = idle_pose(0)
    return [
        (replace(b, dx=3, dy=1, sy=0.94, sx=1.04, lean=3, hand_f=(-9, 24), hand_b=(14, 25), claw=0.9,
                 eye=1.2, wing=1.0, phase=0.4, grin=1.0), 80),
        (replace(b, dx=6, dy=2, sy=0.88, sx=1.08, lean=5, hand_f=(-4, 30), hand_b=(16, 30), claw=1.0,
                 eye=1.4, wing=1.0, phase=0.8, grin=1.0, fire=1.0), 105),
        (replace(b, dx=-28, sy=1.04, sx=1.12, lean=-5, hand_f=(-10, 30), hand_b=(10, 28), claw=1.0,
                 eye=1.4, wing=-1.0, phase=1.2, streak=26, fire=1.0, grin=1.0), 45),
        (replace(b, dx=-50, lean=-4, hand_f=(-17, 8), hand_b=(10, 30), claw=1.0, eye=1.5, wing=-0.6,
                 phase=1.6, slash=1.0, slash_kind=1, streak=10, fire=1.1, mood="angry"), 60),
        (replace(b, dx=-51, lean=-2, hand_f=(-11, 14), hand_b=(4, 6), claw=1.0, eye=1.4, wing=0.6,
                 phase=2.0, slash=1.0, slash_kind=1, slash_fade=0.6, grin=1.0), 45),
        (replace(b, dx=-52, lean=-5, hand_f=(-12, 12), hand_b=(-16, 30), claw=1.0, eye=1.5, wing=-0.8,
                 phase=2.4, slash=1.0, slash_kind=2, fire=1.1, mood="angry"), 60),
        (replace(b, dx=-51, lean=-2, hand_f=(-8, 26), hand_b=(-8, 22), claw=1.0, eye=1.4, wing=0.8,
                 phase=2.8, slash=1.0, slash_kind=2, slash_fade=0.6, grin=1.0), 45),
        (replace(b, dx=-53, lean=-6, sx=1.06, hand_f=(-22, 18), hand_b=(-12, 16), claw=1.0, eye=1.6,
                 wing=-1.0, phase=3.2, slash=1.0, slash_kind=3, fire=1.2, mood="angry"), 65),
        (replace(b, dx=-52, lean=-4, hand_f=(-20, 16), hand_b=(-6, 18), claw=0.8, eye=1.3, wing=0.4,
                 phase=3.6, slash=1.0, slash_kind=3, slash_fade=0.55, grin=1.0), 70),
        (replace(b, dx=-30, lean=3, sx=1.1, sy=0.96, hand_f=(-8, 20), hand_b=(12, 22), wing=1.0,
                 phase=4.2, streak=-0.0, grin=1.0), 55),
        (replace(b, dx=-9, lean=2, hand_f=(-11, 18), wing=-0.6, phase=4.9, grin=0.9), 65),
        (replace(b, dx=-2, lean=0.5, hand_f=(-12, 17), wing=0.3, phase=5.6, grin=0.7), 75),
        (b, 100),
    ]


def fireball_frames():
    """Bola de Fuego: conjure a ball between the hands, throw it left, it bursts on the hero."""
    b = idle_pose(0)
    hold = dict(hand_f=(-18, 22), hand_b=(-8, 26), claw=1.0)
    return [
        (replace(b, lean=1, ball=0.25, ball_pos=(-14, 24), fire=0.3, phase=0.5, wing=0.5, **hold), 90),
        (replace(b, lean=2, ball=0.5, ball_pos=(-14, 25), fire=0.2, eye=1.2, phase=1.0, wing=-0.5,
                 grin=1.0, **hold), 90),
        (replace(b, lean=3, dx=2, ball=0.8, ball_pos=(-13, 26), fire=0.1, eye=1.35, phase=1.5, wing=0.5,
                 grin=1.0, **hold), 100),
        (replace(b, lean=5, dx=4, sy=0.96, ball=1.0, ball_pos=(-9, 30), fire=0.0, eye=1.5, phase=2.0,
                 wing=1.0, grin=1.0, hand_f=(-12, 28), hand_b=(-4, 31), claw=1.0), 110),
        (replace(b, lean=-5, dx=-3, sx=1.06, ball=1.0, ball_pos=(-34, 25), ball_trail=1.0, eye=1.5,
                 phase=2.5, wing=-1.0, mood="angry", hand_f=(-22, 24), hand_b=(4, 20), claw=1.0,
                 fire=0.2), 55),
        (replace(b, lean=-4, dx=-2, ball=1.0, ball_pos=(-61, 23), ball_trail=1.0, eye=1.4, phase=3.0,
                 wing=0.4, grin=1.0, hand_f=(-21, 22), claw=0.9, fire=0.3), 55),
        (replace(b, lean=-3, dx=-1, ball=1.0, ball_pos=(-86, 22), ball_trail=1.0, eye=1.3, phase=3.5,
                 wing=-0.4, grin=1.0, hand_f=(-18, 20), fire=0.4), 55),
        (replace(b, lean=-2, burst=0.55, phase=4.0, wing=0.6, grin=1.0, eye=1.3, hand_f=(-16, 19)), 65),
        (replace(b, lean=-1, burst=1.0, burst_fade=0.35, phase=4.4, wing=-0.6, grin=1.0, mood="laugh"), 80),
        (replace(b, burst=1.0, burst_fade=0.75, phase=4.9, wing=0.4, grin=1.0, mood="laugh"), 80),
        (replace(b, phase=5.6, wing=-0.2, grin=0.9, hand_f=(-13, 17)), 90),
        (b, 100),
    ]


def cast_frames():
    """Burla: it laughs (bounce, belly shake), flames flare from its hands and horns, aura."""
    b = idle_pose(0)
    bounce = [-1, -3, -1, -3, -2, -3, -1, -2, -1, 0]
    up = [0.2, 0.45, 0.7, 0.9, 1.0, 1.0, 0.9, 0.7, 0.4, 0.15]
    out = []
    for k, (dy, u) in enumerate(zip(bounce, up)):
        shake = 1 if k % 2 else -1
        out.append((replace(
            b, dy=dy, sx=1.0 + 0.04 * shake * u, sy=1.0 - 0.03 * shake * u, lean=1.5 * u,
            mood="laugh" if 0 < k < 9 else "grin", grin=1.0,
            hand_f=(-13 - 2 * u, 18 + 9 * u), hand_b=(12 + 2 * u, 19 + 9 * u), claw=0.5 + 0.5 * u,
            fire=0.6 + 1.0 * u, flare=u, aura=u, eye=1.0 + 0.5 * u, wing=1.0 if k % 2 else -1.0,
            phase=0.7 * k, sway=1.3), 80))
    out.append((b, 105))
    return out


def hurt_frames():
    b = idle_pose(0)
    return [
        (replace(b, dx=4, lean=5, sx=0.92, sy=1.05, flash=0.82, mood="angry", eye=0.5, wing=-1.0,
                 claw=1.0, hand_f=(-9, 23), hand_b=(15, 25), phase=1.4, sway=1.8, fire=0.2), 55),
        (replace(b, dx=7, lean=6, sx=0.95, flash=0.55, mood="angry", eye=0.8, wing=1.0, claw=1.0,
                 hand_f=(-8, 21), hand_b=(16, 23), phase=2.1, sway=1.8, fire=0.3), 60),
        (replace(b, dx=6, lean=3, dy=1, flash=0.2, mood="angry", eye=1.1, wing=-0.5,
                 hand_f=(-10, 19), phase=2.8, sway=1.5, fire=0.5), 70),
        (replace(b, dx=4, lean=1.5, mood="angry", eye=1.2, wing=0.6, hand_f=(-11, 18), phase=3.5,
                 fire=0.8), 75),
        (replace(b, dx=2, lean=0.5, grin=1.0, wing=-0.4, hand_f=(-12, 17), phase=4.3, fire=0.8), 80),
        (replace(b, dx=1, grin=0.9, wing=0.4, phase=5.1), 85),
        (b, 100),
    ]


def death_frames():
    b = idle_pose(0)
    shriek = dict(mood="shriek", claw=1.0, hand_f=(-17, 28), hand_b=(15, 30))
    out = [
        (replace(b, dx=3, lean=3, flash=0.85, eye=1.4, wing=1.0, phase=0.6, sway=1.8, **shriek), 70),
        (replace(b, dx=4, sy=1.1, sx=0.93, flash=0.3, eye=1.9, fire=1.4, flare=0.6, wing=-1.0,
                 phase=1.2, sway=1.8, **shriek), 95),
        (replace(b, dx=5, sy=0.92, sx=1.14, flash=0.6, eye=2.0, fire=1.6, flare=1.0, wing=1.0,
                 phase=1.8, sway=2.0, **shriek), 75),
    ]
    falls = [(0.12, 0.0, 0.0), (0.24, 2.0, 0.25), (0.36, 6.0, 0.55), (0.48, 12.0, 0.9),
             (0.6, 20.0, 1.3), (0.72, 30.0, 1.7), (0.84, 0.0, 0.0), (0.94, 0.0, 0.0)]
    for k, (s, drop, rot) in enumerate(falls):
        out.append((replace(b, dx=5, gone=True, smoke=s, horns=k < 6, horns_drop=drop, horns_rot=rot,
                            flare=0.0), 75 + 4 * k))
    out.append((replace(b, dissolve=1.0), 120))
    return out


ANIMATIONS = {
    "idle": (idle_frames, True),
    "attack": (attack_frames, False),
    "fireball": (fireball_frames, False),
    "cast": (cast_frames, False),
    "hurt": (hurt_frames, False),
    "death": (death_frames, False),
}

# Frames where a hit lands: three claw slashes; the fireball bursts on the hero.
EVENTS = {"attack": {"strikes": [3, 5, 7]}, "fireball": {"strikes": [7]}}
MOVES = {"claws": "attack", "fireball": "fireball", "taunt": "cast", "vengeance": "cast"}


def build():
    return build_sheet(ANIMATIONS, render, (CELL_W, CELL_H), ANCHOR, f"{SHEET_ID}_sheet.png",
                       {"events": EVENTS, "moves": MOVES})


def main() -> None:
    sheet, meta = build()
    save_sheet(OUT_DIR, SHEET_ID, sheet, meta)
    print(f"wrote assets/enemies/{SHEET_ID}_sheet.png ({len(sheet[0])}x{len(sheet)}) and .json")


if __name__ == "__main__":
    main()
