"""Draw and animate the floor-1 boss "La Tejedora" (a spider matriarch). Stdlib only:

    python scripts/generate_boss_weaver.py

Same method as the Espectro (``docs/code-drawn-sprites.md``): one renderer, every
frame a ``Pose``. She faces the hero (left):

* a huge glossy abdomen of violet-black chitin with a glowing crimson hourglass
  and rib-like markings, spinnerets at the rear;
* a smaller cephalothorax with a cluster of eight magenta eyes (two big ones),
  pedipalps and curved fangs that open and close;
* eight jointed legs: the far four drawn behind the body, darker; the near four
  in front with a dark rim; crimson bands at the joints and bristles. Leg tips
  stay planted on the floor while the body breathes and the knees rise and fall.

Animations (non-death actions end on idle frame 0):
  idle    16-frame loop: body bob, knee wave, abdomen pulse, a front-leg tap
  attack  "Colmillo": rears up on her hind legs, lunges and bites
  feast   "Banquete": three quick bites in a row (events.feast.strikes)
  web     "Hilos Pegajosos" / "Madre de la Camada": raises her abdomen and sprays silk at the hero
  cast    "Capullo de Seda": hunkers down while silk threads wrap around her
  hurt    white flash, knocked back, legs splay
  death   legs curl up under the body, she drops and burns away into crimson motes
"""
from __future__ import annotations

import math
import sys
from dataclasses import dataclass, field, replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from pixel_kit import (Canvas, bayer, bezier, build_sheet, dissolve, flash, hash01, lerp, mix,  # noqa: E402
                       outline, ramp, save_sheet, smooth, stroke)

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "assets" / "enemies"
SHEET_ID = "weaver"

CELL_W, CELL_H = 224, 124
CX, GROUND = 148, 114
ANCHOR = (CX, GROUND + 2)

# ---------------------------------------------------------------- palette
OUTLINE = (8, 5, 14)
CHITIN = [(10, 8, 18), (20, 16, 34), (34, 26, 54), (52, 40, 78), (76, 60, 106), (110, 92, 146),
          (156, 140, 196)]
LEGC = [(16, 12, 26), (34, 27, 52), (54, 44, 80), (82, 68, 114), (122, 106, 156), (164, 150, 196)]
MARK = [(70, 12, 36), (140, 26, 62), (214, 54, 96), (255, 130, 160), (255, 214, 226)]
EYE = [(90, 14, 70), (190, 40, 150), (255, 110, 220), (255, 220, 250)]
FANG = [(40, 26, 30), (110, 80, 80), (186, 160, 150), (236, 224, 212)]
SILK = [(110, 108, 130), (170, 170, 192), (220, 220, 236), (250, 250, 255)]
WHITE = (255, 255, 255)

# Leg layout: (hip lx, hip h, tip lx, knee height above the body, near side?)
# lx relative to CX, h above the ground. Near legs are drawn over the body.
LEGS = [
    (-10, 36, -72, 22, True), (-6, 35, -46, 26, True), (-1, 35, 18, 24, True), (6, 37, 54, 14, True),
    (-8, 40, -62, 20, False), (-4, 40, -34, 24, False), (1, 40, 30, 22, False), (5, 40, 62, 16, False),
]


@dataclass(frozen=True)
class Pose:
    dx: float = 0.0
    dy: float = 0.0
    rear: float = 0.0             # front of the body raised (px)
    abd: float = 0.0              # abdomen lifted (px)
    sx: float = 1.0
    sy: float = 1.0
    pulse: float = 0.0            # abdomen swelling
    phase: float = 0.0
    tips: tuple = ()              # per-leg tip offsets (dx, dh), 8 entries or empty
    knees: tuple = ()             # per-leg knee lift (px)
    curl: float = 0.0             # death: legs fold under the body 0..1
    fang: float = 0.2             # 0 closed .. 1 open
    eye: float = 1.0
    mark: float = 0.8             # hourglass glow
    flash: float = 0.0
    dissolve: float = 0.0
    spray: float = 0.0            # silk spray progress (web)
    spray_fade: float = 0.0
    cocoon: float = 0.0           # silk wrapping (cast)
    bite: float = 0.0             # crunch marks in front of the fangs (strike frames)
    motes: tuple = field(default_factory=tuple)


def _tip(p: Pose, i: int):
    return p.tips[i] if i < len(p.tips) else (0.0, 0.0)


def _knee(p: Pose, i: int) -> float:
    return p.knees[i] if i < len(p.knees) else 0.0


class Rig:
    """Body anchor points of one pose (cell coords)."""

    def __init__(self, p: Pose) -> None:
        self.p = p
        base_y = GROUND + p.dy
        self.ceph = (CX - 22 + p.dx, base_y - 38 - p.rear)          # cephalothorax centre
        self.abd = (CX + 16 + p.dx * 0.8, base_y - 46 - p.abd - p.rear * 0.25)

    def hip(self, lx: float, h: float) -> tuple[float, float]:
        cx, cy = self.ceph
        return cx + 14 + lx * 0.9, cy + (38 - h) + (-0.2 * self.p.rear * (lx + 12) / 12)


# ---------------------------------------------------------------- shapes
def ellipse_fill(cv: Canvas, cx, cy, rx, ry, shade_fn, tilt: float = 0.0):
    ca, sa = math.cos(tilt), math.sin(tilt)
    r = int(max(rx, ry)) + 2
    for y in range(int(cy) - r, int(cy) + r + 1):
        for x in range(int(cx) - r, int(cx) + r + 1):
            dx, dy = x + 0.5 - cx, y + 0.5 - cy
            u = (dx * ca + dy * sa) / rx
            v = (-dx * sa + dy * ca) / ry
            d = u * u + v * v
            if d <= 1:
                c = shade_fn(x, y, u, v, d)
                if c is not None:
                    cv.put(x, y, c)


def draw_abdomen(cv: Canvas, rig: Rig) -> None:
    p = rig.p
    ax, ay = rig.abd
    rx, ry = 31 * p.sx * (1 + 0.03 * p.pulse), 24 * p.sy * (1 + 0.04 * p.pulse)

    def shade(x, y, u, v, d):
        light = 0.62 - 0.32 * u - 0.38 * v - 0.25 * d
        spec = (u + 0.42) ** 2 + (v + 0.5) ** 2                 # glossy highlight
        if spec < 0.03:
            light += 0.55
        elif spec < 0.09:
            light += 0.25
        if d > 0.86:
            light -= 0.12
        col = ramp(CHITIN, max(0.0, min(1.0, light)), x, y)
        # crimson hourglass on the back + ribs
        hu, hv = (u + 0.08) * 1.25, (v + 0.22) * 1.25
        hour = abs(hu) < 0.04 + 0.30 * abs(hv) ** 1.25 and abs(hv) < 0.55
        waist = abs(hv) < 0.07 and abs(hu) < 0.08
        ribs = (abs(math.sin(hv * 9.5)) > 0.9 and 0.25 < abs(hu) < 0.62 and abs(hv) < 0.7
                and d < 0.75)
        if hour or waist:
            g = p.mark
            edge = abs(hu) > 0.02 + 0.30 * abs(hv) ** 1.25 - 0.06
            lvl = (1 if edge else 2) + (1 if g > 0.9 and abs(hu) < 0.03 + 0.12 * abs(hv) else 0) \
                + (1 if g > 1.3 else 0) - (1 if hv > 0.25 else 0)
            if g < 0.5:
                lvl = 1
            col = MARK[min(4, lvl)]
        elif ribs:
            col = mix(col, MARK[1], 0.55 * min(1.0, p.mark))
        # fine bristles at the rim
        if d > 0.8 and hash01(x, y, 4) > 0.82:
            col = CHITIN[4]
        return col

    ellipse_fill(cv, ax, ay, rx, ry, shade, tilt=-0.18 - 0.012 * p.abd)
    # spinnerets at the rear
    sx, sy_ = ax + rx * 0.92, ay + ry * 0.35
    for k in range(3):
        cv.put(sx + k, sy_ + k * 0.6, CHITIN[3])
        cv.put(sx + k, sy_ + 1 + k * 0.6, CHITIN[1])


def draw_ceph(cv: Canvas, rig: Rig) -> tuple[float, float]:
    """Cephalothorax with the eye cluster. Returns the eye cluster centre."""
    p = rig.p
    cx, cy = rig.ceph
    rx, ry = 19 * p.sx, 15 * p.sy

    def shade(x, y, u, v, d):
        light = 0.6 - 0.35 * u - 0.4 * v - 0.2 * d
        if (u + 0.35) ** 2 + (v + 0.55) ** 2 < 0.05:
            light += 0.4
        # carapace groove
        if abs(u - 0.15) < 0.05 and v < 0.3:
            light -= 0.25
        return ramp(CHITIN, max(0.0, min(1.0, light)), x, y)

    ellipse_fill(cv, cx, cy, rx, ry, shade, tilt=0.12 - 0.02 * p.rear)
    # eyes: two big front eyes and a crown of small ones
    ex, ey = cx - rx * 0.62, cy - ry * 0.3
    e = p.eye
    if e > 0.05:
        big = EYE[3] if e > 0.8 else EYE[2]
        for (ox, oy) in ((0, 0), (6, -1)):
            for qy in range(-1, 3):
                for qx in range(-1, 3):
                    if abs(qx - 0.5) + abs(qy - 0.5) > 2:
                        continue
                    c = big if (qx, qy) in ((0, 0), (0, -1)) else EYE[2] if qy < 1 else EYE[1]
                    cv.put(ex + ox + qx, ey + oy + qy, c)
        small = EYE[2] if e > 0.7 else EYE[1]
        for (ox, oy) in ((-3, -4), (2, -5), (7, -6), (11, -4), (-4, 3), (10, 2)):
            cv.put(ex + ox, ey + oy, small)
            cv.put(ex + ox + 1, ey + oy, EYE[1])
        if e > 1.2:
            for (ox, oy) in ((-1, -1), (6, -2), (3, -6)):
                cv.put(ex + ox, ey + oy, EYE[3])
    return ex + 2, ey


def draw_fangs(cv: Canvas, rig: Rig) -> tuple[float, float]:
    """Chelicerae and curved fangs under the face; returns the fang tip point."""
    p = rig.p
    cx, cy = rig.ceph
    tips = []
    for k, side in enumerate((-1, 1)):
        bx = cx - 14 * p.sx + side * 2.5
        by = cy + 5
        # chelicera (stubby, hairy)
        for yy in range(int(by), int(by) + 6):
            for xx in range(int(bx) - 2, int(bx) + 3):
                light = 0.5 - 0.3 * (xx - bx) / 2 - 0.1 * (yy - by)
                cv.put(xx, yy, ramp(CHITIN, light, xx, yy))
        # fang: curls inward; opens with p.fang
        ang = math.pi / 2 + side * (0.15 + 0.9 * p.fang) - 0.35
        x, y = bx, by + 5
        for s in range(10):
            ang += -side * 0.15
            x += math.cos(ang) * 1.0
            y += math.sin(ang) * 1.0
            c = FANG[3] if s < 3 else FANG[2] if s < 7 else FANG[1]
            cv.put(x, y, c)
            if s < 5:
                cv.put(x + 1, y, FANG[1] if s > 1 else FANG[2])
                cv.put(x - 1, y, FANG[0])
        tips.append((x, y))
    # pedipalps (short feelers in front)
    for k, ph in enumerate((0.0, 1.3)):
        px0, py0 = cx - 15 * p.sx, cy + 1 + k
        wob = math.sin(p.phase * 2 + ph)
        pts = [(px0, py0), (px0 - 5 - wob, py0 + 3), (px0 - 7 - wob, py0 + 8)]
        stroke(cv, bezier(*pts, 10), lambda t: 1.4 - 0.5 * t, LEGC[1:], rim=OUTLINE)
    return (tips[0][0] + tips[1][0]) / 2, (tips[0][1] + tips[1][1]) / 2


def leg_points(rig: Rig, i: int):
    p = rig.p
    hip_lx, hip_h, tip_lx, knee_h, near = LEGS[i]
    hx, hy = rig.hip(hip_lx, hip_h)
    tdx, tdh = _tip(p, i)
    tx = CX + tip_lx + tdx + (0 if near else 2)
    ty = GROUND - tdh - (0 if near else 2) + 0.5
    # death curl: the tips fold under the body
    if p.curl > 0:
        ux, uy = rig.ceph[0] + 14 + (tip_lx * 0.18), rig.ceph[1] + 10
        tx, ty = lerp(tx, ux, p.curl), lerp(ty, uy, p.curl)
    side = -1 if tip_lx + tdx < hip_lx else 1
    kh = (knee_h + _knee(p, i)) * (1 - 0.65 * p.curl)
    kx = lerp(hx, tx, 0.42) + side * 2
    ky = min(hy, ty) - kh
    # tibia bows outward
    mx, my = lerp(kx, tx, 0.5) + side * (3 + 4 * p.curl), lerp(ky, ty, 0.45)
    return (hx, hy), (kx, ky), (mx, my), (tx, ty), near


def draw_leg(cv: Canvas, rig: Rig, i: int) -> None:
    (hx, hy), (kx, ky), (mx, my), (tx, ty), near = leg_points(rig, i)
    cols = LEGC if near else LEGC[:-1]
    shade = 0.0 if near else -0.18
    femur = bezier((hx, hy), ((hx + kx) / 2 - 1, (hy + ky) / 2 - 2), (kx, ky), 14)
    stroke(cv, femur, lambda t: 2.7 - 0.6 * t, cols, shade=shade, rim=OUTLINE)
    tib = bezier((kx, ky), (mx, my), (tx, ty), 18)
    stroke(cv, tib, lambda t: 2.1 - 1.2 * t, cols, shade=shade - 0.05, rim=OUTLINE)
    # crimson joint band and knee knob
    band = MARK[2] if near else MARK[1]
    for ox, oy in ((0, 0), (1, 0), (0, 1), (-1, 0)):
        cv.put(kx + ox, ky + oy, band if (ox, oy) != (0, 0) else MARK[3] if near else MARK[2])
    bx, by = lerp(kx, tx, 0.62), lerp(ky, ty, 0.62)
    cv.put(bx, by, band)
    cv.put(bx + 1, by, MARK[1])
    # bristles
    for s in range(4):
        t = 0.2 + s * 0.17
        qx, qy = lerp(kx, mx, t), lerp(ky, my, t)
        cv.put(qx + 2, qy - 1, LEGC[3] if near else LEGC[2])


# ---------------------------------------------------------------- effects
def draw_spray(cv: Canvas, rig: Rig, prog: float, fade: float) -> None:
    """Silk threads shot from the spinnerets over her back towards the hero, ending in a web."""
    if prog <= 0:
        return
    ax, ay = rig.abd
    sx, sy = ax + 6, ay - 22
    end_x = 6
    head = sx + (end_x - sx) * min(1.0, prog)
    for k in range(5):
        off = (k - 2) * 2.2 + (hash01(k, 1, 3) - 0.5)
        for i in range(160):
            t = i / 159
            x = lerp(sx, head, t)
            arc = -26 * math.sin(math.pi * t) * min(1.0, prog * 1.3)
            y = sy + arc + off * t * 2.2 + 6 * t + 1.2 * math.sin(t * 9 + k)
            if hash01(i, k, 2) < 0.1 * t:
                continue
            w = t - fade * 1.1
            if w <= 0:
                continue
            c = SILK[3] if w > 0.8 else SILK[2] if w > 0.4 else SILK[1]
            cv.put(x, y, c, solid=False, alpha=int(255 * min(1.0, 0.3 + w)))
    if prog >= 0.95 and fade < 0.95:                       # web net where the threads land
        wx, wy = end_x + 12, sy + 8
        a = 1 - fade
        for r in (4, 8, 12):
            for i in range(int(r * 6)):
                ang = i / (r * 6) * math.tau
                cv.put(wx + math.cos(ang) * r, wy + math.sin(ang) * r * 0.8, SILK[2], solid=False,
                       alpha=int(220 * a))
        for k in range(8):
            ang = k / 8 * math.tau
            for s in range(13):
                cv.put(wx + math.cos(ang) * s, wy + math.sin(ang) * s * 0.8, SILK[1], solid=False,
                       alpha=int(200 * a))


def draw_cocoon(cv: Canvas, rig: Rig, k: float, t: float) -> None:
    """Silk threads winding around her body (cast)."""
    if k <= 0:
        return
    cx = (rig.ceph[0] + rig.abd[0]) / 2
    cy = (rig.ceph[1] + rig.abd[1]) / 2 + 2
    for j in range(7):
        tilt = -0.5 + j * 0.17
        r = 26 + 7 * math.sin(j * 1.7)
        span = min(1.0, k * 1.4 - j * 0.08)
        if span <= 0:
            continue
        for i in range(int(140 * span)):
            a = i / 140 * math.tau + t * 3 + j
            x = cx + math.cos(a) * r * 1.35
            y = cy + math.sin(a) * r * 0.42 + math.cos(a) * r * tilt * 0.5
            front = math.sin(a) > 0
            if not front and cv.get(int(x), int(y)) is not None:
                continue                                        # behind the body
            cv.put(x, y, SILK[3] if front else SILK[1], solid=False, alpha=int(230 * min(1.0, k + 0.2)))


def draw_drapes(cv: Canvas, rig: Rig) -> None:
    """A few silk threads trailing from the spinnerets to the floor, with dew beads."""
    p = rig.p
    ax, ay = rig.abd
    sx, sy = ax + 27, ay + 9
    for k, (gx, sag) in enumerate(((28, 3.0), (40, 5.0), (52, 4.0))):
        ex, ey = CX + gx, GROUND
        wob = 1.2 * math.sin(p.phase + k * 1.3)
        mx, my = (sx + ex) / 2 + sag + wob, (sy + ey) / 2 + sag
        for i, (x, y) in enumerate(bezier((sx, sy), (mx, my), (ex, ey), 70)):
            if hash01(i, k, 6) < 0.12:
                continue
            cv.put(x, y, SILK[1] if i % 9 else SILK[3], solid=False, alpha=150)


# ---------------------------------------------------------------- render
def render(p: Pose, t: float = 0.0) -> Canvas:
    cv = Canvas(CELL_W, CELL_H)
    rig = Rig(p)
    if p.curl < 0.3:
        draw_drapes(cv, rig)
    for i in range(4, 8):
        draw_leg(cv, rig, i)
    draw_abdomen(cv, rig)
    for i in range(4):
        draw_leg(cv, rig, i)
    head = Canvas(CELL_W, CELL_H)                  # head over the legs' roots, rimmed
    eye = draw_ceph(head, rig)
    fang_tip = draw_fangs(head, rig)
    cv.blit(head, rim=OUTLINE)
    outline(cv, OUTLINE)
    if p.eye > 0.05:
        cv.glow(eye[0], eye[1], 6 + 3 * p.eye, EYE[1], 0.4 * p.eye)
    if p.mark > 0.05:
        cv.glow(rig.abd[0] - 1, rig.abd[1] - 1, 14 + 6 * p.mark, MARK[1], 0.28 * p.mark, halo=False)
    draw_cocoon(cv, rig, p.cocoon, t)
    if p.bite > 0:                                  # two jaw crescents snapping shut
        bx, by = fang_tip[0] - 13, fang_tip[1] - 2
        for r, c in ((6.0, MARK[3]), (7.5, MARK[2]), (9.0, MARK[1])):
            for i in range(30):
                t_ = i / 29
                for lo, hi in ((math.pi * 1.15, math.pi * 1.85), (math.pi * 0.15, math.pi * 0.85)):
                    ang = lo + (hi - lo) * t_
                    x = bx + math.cos(ang) * r
                    y = by + math.sin(ang) * r * 0.75
                    col = WHITE if (r < 7 and 0.35 < t_ < 0.65) else c
                    cv.put(x, y, col, solid=False, alpha=int(255 * p.bite))
    draw_spray(cv, rig, p.spray, p.spray_fade)
    for (mx, my, lv) in p.motes:
        cv.put(mx, my, MARK[lv], solid=False)
    flash(cv, p.flash)
    if p.dissolve > 0:
        dissolve(cv, p.dissolve, GROUND - 90, GROUND + 2, MARK[4], MARK[2], upward=True)
    return cv


# ---------------------------------------------------------------- animations
IDLE_FRAMES = 16


def idle_pose(i: int, n: int = IDLE_FRAMES) -> Pose:
    a = math.tau * i / n
    knees = tuple(1.6 * math.sin(a + k * 0.8) for k in range(8))
    tap = 0.0
    if 7 <= i <= 10:                                   # the front leg taps the floor
        tap = (0.0, 3.0, 4.0, 1.5)[i - 7]
    tips = ((0.0, tap),) + ((0.0, 0.0),) * 7
    return Pose(dy=round(-1.0 * math.sin(a)), pulse=math.sin(a - 0.7), phase=a, knees=knees,
                tips=tips, fang=0.2 + 0.15 * max(0.0, math.sin(a * 2)),
                eye=0.8 if i == 12 else 1.0, mark=0.8 + 0.25 * math.sin(a))


def idle_frames():
    return [(idle_pose(i), 100) for i in range(IDLE_FRAMES)]


def _front_raise(lift: float, reach: float = 0.0) -> tuple:
    """Tip offsets with the two near front legs lifted (pounce / threat)."""
    return ((-reach, lift), (-reach * 0.6, lift * 0.7)) + ((0.0, 0.0),) * 2 + \
           ((-reach * 0.8, lift * 0.8), (-reach * 0.5, lift * 0.55)) + ((0.0, 0.0),) * 2


def attack_frames():
    b = idle_pose(0)
    return [
        (replace(b, rear=4, dx=3, tips=_front_raise(8), fang=0.6, eye=1.2, mark=1.0), 100),
        (replace(b, rear=10, dx=6, abd=-2, tips=_front_raise(18, -4), knees=(6,) * 8, fang=1.0,
                 eye=1.5, mark=1.2), 130),
        (replace(b, rear=-2, dx=-16, sx=1.05, tips=_front_raise(4, 14), fang=0.0, eye=1.5,
                 mark=1.3, bite=1.0), 60),
        (replace(b, rear=-3, dx=-18, sx=1.04, tips=_front_raise(0, 16), fang=0.0, eye=1.4,
                 mark=1.2, bite=0.5), 80),
        (replace(b, rear=0, dx=-12, tips=_front_raise(2, 10), fang=0.3, eye=1.2), 90),
        (replace(b, dx=-6, tips=_front_raise(1, 5), fang=0.3), 90),
        (replace(b, dx=-2, fang=0.25), 90),
        (b, 110),
    ]


def feast_frames():
    """Three quick bites; ends on idle 0."""
    b = idle_pose(0)
    out = [(replace(b, rear=8, dx=5, tips=_front_raise(14, -3), fang=1.0, eye=1.5, mark=1.3,
                    knees=(4,) * 8), 120)]
    for k in range(3):
        lunge = -14 - 2 * k
        out += [
            (replace(b, rear=-2, dx=lunge, sx=1.04, tips=_front_raise(2, 12), fang=0.0, eye=1.5,
                     mark=1.3 + 0.1 * k, phase=0.6 * k, bite=1.0), 60),
            (replace(b, rear=6, dx=lunge + 10, tips=_front_raise(10, 2), fang=1.0, eye=1.4,
                     mark=1.2, phase=0.6 * k + 0.3), 75),
        ]
    out += [(replace(b, dx=-3, fang=0.4, mark=1.0), 90), (replace(b, dx=-1), 90), (b, 110)]
    return out


def web_frames():
    """Raises her abdomen and shoots silk at the hero."""
    b = idle_pose(0)
    out = [
        (replace(b, abd=4, rear=-1, dx=2, mark=1.1, eye=1.15, pulse=1.0), 100),
        (replace(b, abd=10, rear=-2, dx=3, mark=1.4, eye=1.3, pulse=1.4, knees=(3,) * 8), 120),
    ]
    for k, s in enumerate((0.3, 0.6, 0.9, 1.0, 1.0, 1.0)):
        out.append((replace(b, abd=10 - k, rear=-2, dx=3 - k * 0.4, mark=1.4 - 0.08 * k, eye=1.3,
                            pulse=1.2 - 0.2 * k, spray=s, spray_fade=max(0.0, (k - 2) / 3.5)), 75))
    out += [(replace(b, abd=2, dx=1), 90), (b, 110)]
    return out


def cast_frames():
    """Capullo de Seda: crouches while silk wraps around her."""
    b = idle_pose(0)
    out = []
    ks = [0.15, 0.4, 0.65, 0.9, 1.0, 1.0, 0.8, 0.45, 0.15]
    for k, c in enumerate(ks):
        crouch = min(1.0, c * 1.3)
        out.append((replace(b, dy=round(3 * crouch), knees=tuple(-4 * crouch for _ in range(8)),
                            cocoon=c, eye=1.0 + 0.3 * crouch, mark=0.8 + 0.4 * crouch,
                            phase=0.5 * k), 85))
    out.append((b, 110))
    return out


def hurt_frames():
    b = idle_pose(0)
    splay = ((-4, 2), (-3, 3), (2, 2), (4, 1), (-4, 2), (-2, 3), (3, 2), (4, 1))
    return [
        (replace(b, dx=6, rear=4, sx=0.95, flash=0.85, eye=0.4, tips=splay, fang=1.0), 55),
        (replace(b, dx=8, rear=3, flash=0.55, eye=0.6, tips=splay, fang=0.8), 65),
        (replace(b, dx=6, rear=1, flash=0.2, eye=0.8, fang=0.5), 70),
        (replace(b, dx=4, fang=0.3), 70),
        (replace(b, dx=2), 80),
        (b, 100),
    ]


def death_frames():
    b = idle_pose(0)
    out = [
        (replace(b, dx=6, rear=6, flash=0.85, eye=0.5, fang=1.0, tips=_front_raise(10, -2)), 70),
        (replace(b, dx=6, rear=8, flash=0.3, eye=1.8, mark=1.6, fang=1.0, tips=_front_raise(14, -4)), 100),
    ]
    steps = 12
    for k in range(steps):
        u = (k + 1) / steps
        c = smooth(min(1.0, u * 1.8))
        drop = 18 * smooth(min(1.0, u * 2.2))
        motes = tuple(
            (CX - 40 + hash01(k, j, 9) * 90, GROUND - 4 - u * 70 * hash01(j, k, 4),
             1 + int(hash01(j, k, 2) * 3)) for j in range(6 + k)) if u > 0.3 else ()
        out.append((replace(b, dx=6, dy=drop, rear=4 * (1 - c), curl=c, eye=1.6 * (1 - c),
                            mark=1.4 * (1 - u), fang=1.0 - 0.6 * c,
                            dissolve=0.0 if u < 0.45 else min(1.0, (u - 0.45) / 0.55),
                            motes=motes), 85))
    out.append((replace(b, dissolve=1.0), 120))
    return out


ANIMATIONS = {
    "idle": (idle_frames, True),
    "attack": (attack_frames, False),
    "feast": (feast_frames, False),
    "web": (web_frames, False),
    "cast": (cast_frames, False),
    "hurt": (hurt_frames, False),
    "death": (death_frames, False),
}
EVENTS = {"attack": {"strikes": [2]}, "feast": {"strikes": [1, 3, 5]}, "web": {"strikes": [4]}}
MOVES = {"fang": "attack", "feast": "feast", "web": "web", "brood": "web", "cocoon": "cast"}


def build():
    return build_sheet(ANIMATIONS, render, (CELL_W, CELL_H), ANCHOR, f"{SHEET_ID}_sheet.png",
                       {"events": EVENTS, "moves": MOVES, "boss": True})


def main() -> None:
    sheet, meta = build()
    save_sheet(OUT_DIR, SHEET_ID, sheet, meta)
    print(f"wrote assets/enemies/{SHEET_ID}_sheet.png ({len(sheet[0])}x{len(sheet)}) and .json")


if __name__ == "__main__":
    main()
