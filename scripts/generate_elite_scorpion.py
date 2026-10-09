"""Draw and animate the elite "Escorpión Rey" (a giant scorpion king). Stdlib only:

    python scripts/generate_elite_scorpion.py

Same method as the Espectro and the floor-1 bosses (``docs/code-drawn-sprites.md``): one
renderer, every frame a ``Pose``. Identity "Veneno letal": it poisons you relentlessly
behind a hard shell. Seen from the side (slight 3/4), facing the hero (left):

* ONE column-scanned body mass: a flat prosoma (head shield) with a crown of gold-tipped
  spikes, a cluster of glowing amber eyes and small chelicerae, then seven overlapping
  mesosoma plates (tergites with gold rims, specular glints and a dorsal keel, a dark
  pleural band, sternites underneath) in glossy obsidian / black-crimson chitin;
* the tail (metasoma): five bead-like glossy segments with gold joint bands arching up and
  over the back, a bulbous telson with a toxic-green glowing aculeus that drips venom;
* two big pincers held forward: the far one darker, behind the body; the near one bigger,
  drawn on top with a dark rim (the Espectro sleeve rule), its movable finger opens/closes;
* eight legs (four near, four far and darker) whose tips stay planted on the floor.

Animations (non-death actions end on idle frame 0):
  idle    12-frame loop: body breathes on its legs, tail sways, stinger drips, pincers flex
  attack  "Pinzas": rears, lunges and snaps the near then the far pincer (two strikes)
  sting   "Aguijonazo": the tail coils back, whips over the head and stabs far left (splash)
  spray   "Toxina": the tail aims forward and sprays a cone of green venom mist to the left
  cast    "Caparazón" / "Frenesí" / "Venganza": hunkers, pincers raised to guard, an amber
          glint sweeps across the carapace
  hurt    white flash, recoil, legs scramble
  death   rears, then collapses belly-up with the legs curling, the venom glow fades, it
          burns away -> empty

Output: ``assets/enemies/scorpion_sheet.png`` + ``.json`` (``events``, ``moves``,
``boss``/``elite`` flags).
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
SHEET_ID = "scorpion"

CELL_W, CELL_H = 208, 120
CX, GROUND = 140, 112
ANCHOR = (CX, GROUND + 2)

# ---------------------------------------------------------------- palette
OUTLINE = (12, 5, 9)
SHELL = [(9, 5, 10), (19, 8, 15), (33, 11, 21), (52, 15, 27), (78, 23, 34), (114, 38, 44),
         (160, 70, 64)]
SPEC = [(214, 150, 120), (250, 222, 196)]
MEMB = [(22, 9, 14), (44, 16, 22), (70, 28, 30), (98, 44, 40)]           # pleural membrane
LEGC = [(12, 6, 11), (26, 10, 17), (44, 14, 23), (68, 21, 30), (100, 34, 40), (146, 64, 60)]
GOLD = [(78, 40, 14), (146, 86, 22), (212, 146, 42), (255, 208, 104), (255, 244, 198)]
EYE = [(120, 46, 8), (226, 122, 20), (255, 196, 66), (255, 248, 200)]
VENOM = [(18, 64, 34), (44, 140, 52), (122, 226, 72), (214, 255, 160), (246, 255, 226)]
WHITE = (255, 255, 255)

# body profile (local x: 0 = CX, negative = towards the hero)
HEAD_X, REAR_X = -48.0, 38.0
PRO_END = -19.0                    # prosoma | mesosoma
SEG_W = 7.6                        # mesosoma plate width
BODY_H = 18.0                      # centre line height above the ground

# legs: (hip lx, tip lx, knee lift, near?)  near legs drawn over the body
LEGS = [
    (-26, -52, 4, True), (-18, -33, 5, True), (-9, -6, 5, True), (0, 22, 4, True),
    (-23, -44, 5, False), (-15, -22, 6, False), (-6, 7, 6, False), (3, 32, 5, False),
]


@dataclass(frozen=True)
class Pose:
    dx: float = 0.0
    dy: float = 0.0
    lift: float = 0.0              # body raised above its legs (px, negative = hunker)
    pitch: float = 0.0             # front of the body raised (px at the head)
    sx: float = 1.0
    breath: float = 0.0            # mesosoma swelling
    phase: float = 0.0
    tail_a: float = -1.12          # tail base angle (rad, screen coords; -pi/2 = up)
    tail_c: float = -0.43          # curl per joint
    tail_len: float = 1.0
    tail_sway: float = 0.0
    claw_n: tuple = (0.0, 0.0)     # near wrist offset
    claw_f: tuple = (0.0, 0.0)     # far wrist offset
    rot_n: float = 0.0             # chela rotation (negative = tip raised)
    rot_f: float = 0.0
    open_n: float = 0.2            # movable finger 0 shut .. 1 wide
    open_f: float = 0.2
    tips: tuple = ()               # per-leg tip offsets (dx, dh)
    knees: tuple = ()              # per-leg knee lift
    curl: float = 0.0              # death: belly-up, legs curl 0..1
    eye: float = 1.0
    venom: float = 1.0             # aculeus glow
    drip: float = -1.0             # droplet fall 0..1 (-1: from phase)
    glint: float = -1.0            # amber glint sweep 0..1 (cast); <0 none
    guard: float = 0.0             # amber guard aura (cast)
    flash: float = 0.0
    dissolve: float = 0.0
    smear: float = 0.0             # pincer snap arc (strike frames)
    smear_far: bool = False
    splash: float = 0.0            # venom splash at the sting tip
    spray: float = 0.0             # venom mist progress
    spray_fade: float = 0.0
    motes: tuple = field(default_factory=tuple)


def _get(seq, i, default):
    return seq[i] if i < len(seq) else default


def _rot(x, y, a):
    ca, sa = math.cos(a), math.sin(a)
    return x * ca - y * sa, x * sa + y * ca


# ---------------------------------------------------------------- rig
class Rig:
    def __init__(self, p: Pose) -> None:
        self.p = p
        self.ox = CX + p.dx
        self.base = GROUND + p.dy - p.lift

    def yc(self, lx: float) -> float:
        """Centre line row of the body at local x."""
        p = self.p
        k = (REAR_X - lx) / (REAR_X - HEAD_X)          # 1 at the head, 0 at the rear
        return self.base - BODY_H - p.pitch * k + 1.5 * ((lx + 5) / 43) ** 2

    def at(self, lx: float, h: float) -> tuple[float, float]:
        """A point h px above the centre line at local x."""
        return self.ox + lx * self.p.sx, self.yc(lx) - h

    def extents(self, lx: float) -> tuple[float, float]:
        """(top, bottom) half-thickness at local x."""
        p = self.p
        if lx < PRO_END:                                # flat head shield, rounded snout
            t = (lx - HEAD_X) / (PRO_END - HEAD_X)
            nose = math.sqrt(max(0.0, min(1.0, t / 0.2)))
            top = (5.5 + 5.0 * smooth(t / 0.75)) * nose + 1.0
            bot = 7.5 * nose + 0.5
        else:
            t = (lx - PRO_END) / (REAR_X - PRO_END)
            s = ((lx - PRO_END) / SEG_W) % 1.0
            bump = 1.0 * math.sin(math.pi * min(1.0, s / 0.85))
            arch = 12.5 + 1.8 * math.sin(math.pi * min(1.0, t * 1.15)) - 6.0 * smooth((t - 0.72) / 0.28)
            top = arch + bump + 0.6 * p.breath
            bot = 9.0 - 3.5 * smooth((t - 0.6) / 0.4) + 0.3 * p.breath
        return top, bot


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


def _glint_k(p: Pose, x: float, y: float) -> float:
    if p.glint < 0:
        return 0.0
    gx = lerp(CX - 100, CX + 80, p.glint) + (y - GROUND) * 0.6     # slanted band
    d = abs(x - gx)
    return max(0.0, 1 - d / 5.0)


def draw_body(cv: Canvas, rig: Rig) -> None:
    p = rig.p
    x0 = int(rig.ox + HEAD_X * p.sx) - 1
    x1 = int(rig.ox + REAR_X * p.sx) + 2
    for x in range(x0, x1):
        lx = (x + 0.5 - rig.ox) / p.sx
        if lx < HEAD_X or lx > REAR_X:
            continue
        top, bot = rig.extents(lx)
        yc = rig.yc(lx)
        head = lx < PRO_END
        for y in range(int(yc - top), int(yc + bot) + 1):
            fy = y + 0.5 - yc
            if fy < -top or fy > bot:
                continue
            v = fy / top if fy < 0 else fy / bot                     # -1 top .. 1 belly
            front = (lx - HEAD_X) / (REAR_X - HEAD_X)
            light = 0.62 - 0.5 * v - 0.16 * front
            if abs(v) > 0.86:
                light -= 0.12
            if head:
                t = (lx - HEAD_X) / (PRO_END - HEAD_X)
                light += 0.1 * (1 - t)
                if v < -0.2:                                          # carapace: granules
                    light += 0.12 * (hash01(x // 2, y // 2, 3) - 0.5)
                # eye tubercle groove + rear rim of the shield
                if t > 0.9 and v < 0.3:
                    light -= 0.35
                col = ramp(SHELL, max(0.0, min(1.0, light)), x, y)
                if v > 0.35:                                          # underside
                    col = ramp(SHELL[:4], max(0.0, light + 0.2), x, y)
                if -0.62 < v < -0.38 and 0.18 < t < 0.6 and bayer(x, y) < 0.55:
                    col = SPEC[0]                                    # glossy streak
                if -0.62 < v < -0.48 and 0.28 < t < 0.42:
                    col = SPEC[1]
            else:
                s = ((lx - PRO_END) / SEG_W) % 1.0
                seg = int((lx - PRO_END) / SEG_W)
                # plates overlap front over back: a lit rear rim, a shadow just behind it
                if s < 0.16:
                    light -= 0.3
                elif s > 0.8:
                    light += 0.14
                if v < 0.18:                                          # tergite (dorsal plate)
                    col = ramp(SHELL, max(0.0, min(1.0, light)), x, y)
                    if s > 0.88 and v < 0.05:
                        col = GOLD[2] if v < -0.55 else GOLD[1]       # gold plate rim
                    elif abs(v + 0.86) < 0.11 and 0.3 < s < 0.7:
                        col = GOLD[1]                                 # dorsal keel spot
                    elif -0.68 < v < -0.4 and 0.4 < s < 0.72 and seg < 6:
                        col = SPEC[1] if (s < 0.56 and v < -0.52) else SPEC[0]
                    elif 0.0 < v < 0.18:
                        col = ramp(SHELL, max(0.0, light - 0.2), x, y)
                elif v < 0.5:                                         # pleural membrane
                    wrinkle = 0.25 * math.sin(lx * 1.7 + v * 4)
                    col = ramp(MEMB, max(0.0, min(1.0, 0.45 + wrinkle - 0.3 * v)), x, y)
                else:                                                 # sternites
                    col = ramp(SHELL[:5], max(0.0, min(1.0, light + 0.25)), x, y)
                    if s < 0.14:
                        col = SHELL[0]
            g = _glint_k(p, x, y)
            if g > 0:
                col = mix(col, GOLD[4] if g > 0.7 else GOLD[3], 0.85 * g)
            cv.put(x, y, col)
    # crown of spikes on the head shield
    for k, (lx, h, lean) in enumerate(((-42, 3, 0.3), (-37, 5, 0.4), (-32, 7, 0.5),
                                       (-27, 6, 0.6), (-23, 4, 0.7))):
        top, _ = rig.extents(lx)
        bx, by = rig.at(lx, top - 1)
        for j in range(h):
            w = max(0, int((h - j) * 0.5))
            cx_ = bx + lean * j
            for q in range(-w, w + 1):
                c = GOLD[3] if j >= h - 1 else GOLD[2] if j >= h - 2 else \
                    (SHELL[4] if q < 0 else SHELL[2])
                cv.put(cx_ + q, by - j, c)
    # chelicerae under the snout
    hx, hy = rig.at(HEAD_X + 2, -2)
    for q in range(4):
        cv.put(hx - 2 + q * 0.3, hy + q, SHELL[3] if q < 2 else SHELL[2])
        cv.put(hx - 1 + q * 0.3, hy + q, SHELL[1])
        cv.put(hx - 3 + q * 0.3, hy + q, GOLD[1] if q == 3 else SHELL[2])


def eye_points(rig: Rig):
    p = rig.p
    pts = []
    top, _ = rig.extents(-33)
    mx, my = rig.at(-33, top - 1.5)
    pts += [(mx, my, 3), (mx + 3, my, 3)]                         # median pair
    for k, (lx, h) in enumerate(((-46, 0.5), (-45, 2.5), (-43, 4.0))):
        ex, ey = rig.at(lx, h)
        pts.append((ex, ey, 2))
    return pts


def draw_eyes(cv: Canvas, rig: Rig) -> tuple[float, float]:
    p = rig.p
    e = p.eye
    pts = eye_points(rig)
    if e <= 0.05:
        return pts[0][0], pts[0][1]
    for (x, y, size) in pts:
        hot = EYE[3] if e > 0.85 else EYE[2] if e > 0.5 else EYE[1]
        if size == 3:
            cv.put(x, y, hot)
            cv.put(x + 1, y, EYE[2] if e > 0.5 else EYE[1])
            cv.put(x, y + 1, EYE[1])
            cv.put(x + 1, y + 1, EYE[0])
        else:
            cv.put(x, y, hot if e > 0.7 else EYE[1])
    return pts[0][0] + 1, pts[0][1]


# ---------------------------------------------------------------- tail
def tail_chain(rig: Rig):
    """Joint points of the tail + telson centre, aculeus control points and angles."""
    p = rig.p
    bx, by = rig.at(REAR_X - 6, 4)
    lens = [12.5, 12.5, 13.0, 13.5, 13.0]
    a = p.tail_a
    pts = [(bx, by)]
    angs = []
    x, y = bx, by
    for i, L in enumerate(lens):
        sway = p.tail_sway * math.sin(p.phase + i * 0.55) * (0.3 + 0.18 * i)
        a_i = a + p.tail_c * i + sway * 0.12
        L *= p.tail_len
        x += math.cos(a_i) * L
        y += math.sin(a_i) * L
        pts.append((x, y))
        angs.append(a_i)
    a_t = angs[-1] + p.tail_c * 0.9
    return pts, angs, a_t


def draw_tail(cv: Canvas, rig: Rig) -> tuple[float, float, float]:
    """Metasoma segments, telson and aculeus. Returns the stinger tip (x, y) and angle."""
    p = rig.p
    pts, angs, a_t = tail_chain(rig)
    radii = [6.8, 6.3, 5.9, 5.6, 5.4]
    tail = Canvas(cv.w, cv.h)
    for i in range(5):
        (x0, y0), (x1, y1) = pts[i], pts[i + 1]
        a = angs[i]
        L = math.hypot(x1 - x0, y1 - y0)
        mx, my = (x0 + x1) / 2, (y0 + y1) / 2
        rx, ry = L / 2 + 2.2, radii[i]
        ca, sa = math.cos(a), math.sin(a)
        # which side of the segment faces the light (upper-left)
        nlx, nly = -sa, ca                       # one perpendicular
        if nlx * -0.7 + nly * -0.7 < 0:
            sgn = -1.0
        else:
            sgn = 1.0

        def shade(x, y, u, v, d, i=i, sgn=sgn, ca=ca, sa=sa):
            side = v * sgn                       # +1 = lit side
            light = 0.52 + 0.4 * side - 0.28 * d
            along = (u + 1) / 2                  # 0 base .. 1 tip of the segment
            if along > 0.86:
                light -= 0.28                    # joint shadow
            if 0.68 < along < 0.84 and side > -0.4:
                col = GOLD[2] if side > 0.35 else GOLD[1]
                return col
            col = ramp(SHELL, max(0.0, min(1.0, light)), x, y)
            if 0.45 < side < 0.78 and 0.18 < along < 0.55:
                col = SPEC[1] if 0.26 < along < 0.4 else SPEC[0]
            # carinae (keels) along the segment
            if abs(side + 0.1) < 0.09 and 0.1 < along < 0.66 and bayer(x, y) < 0.6:
                col = SHELL[1]
            g = _glint_k(p, x, y)
            if g > 0:
                col = mix(col, GOLD[4], 0.85 * g)
            return col

        seg = Canvas(cv.w, cv.h)
        ellipse_fill(seg, mx, my, rx, ry, shade, tilt=a)
        tail.blit(seg, rim=OUTLINE)
    # telson bulb
    ex, ey = pts[-1]
    ca, sa = math.cos(a_t), math.sin(a_t)
    tx, ty = ex + ca * 7.5, ey + sa * 7.5
    inward = (sa, -ca)
    if p.tail_c > 0:
        inward = (-sa, ca)
    sw = 1.0 + 0.08 * max(0.0, p.venom - 1.0)

    def bulb(x, y, u, v, d):
        lx_, ly_ = (x + 0.5 - tx), (y + 0.5 - ty)
        nd = (lx_ * -0.7 + ly_ * -0.7) / 7.0
        light = 0.48 + 0.5 * nd - 0.25 * d
        col = ramp(SHELL, max(0.0, min(1.0, light)), x, y)
        if (lx_ + 2.8) ** 2 + (ly_ + 2.6) ** 2 < 2.2:
            col = SPEC[1]
        elif (lx_ + 2.5) ** 2 + (ly_ + 2.1) ** 2 < 5.5:
            col = SPEC[0]
        # venom sac glowing through the shell on the ventral side
        dv = (lx_ * inward[0] + ly_ * inward[1]) / 7.0
        if p.venom > 0.2 and dv > 0.15 and d < 0.82:
            k = min(1.0, (dv - 0.15) * 2.2) * min(1.0, p.venom) * (1 - 0.5 * d)
            vc = VENOM[2] if k > 0.55 else VENOM[1] if k > 0.25 else VENOM[0]
            if bayer(x, y) < 0.25 + 0.75 * k:
                col = mix(col, vc, 0.3 + 0.6 * k)
        g = _glint_k(p, x, y)
        if g > 0:
            col = mix(col, GOLD[4], 0.85 * g)
        return col

    seg = Canvas(cv.w, cv.h)
    ellipse_fill(seg, tx, ty, 9.0 * sw, 7.2 * sw, bulb, tilt=a_t)
    tail.blit(seg, rim=OUTLINE)
    # aculeus: curved tapered barb towards the inward side
    p0 = (tx + ca * 7.5, ty + sa * 7.5)
    p1 = (p0[0] + ca * 6.0 + inward[0] * 0.5, p0[1] + sa * 6.0 + inward[1] * 0.5)
    p2 = (p0[0] + ca * 6.5 + inward[0] * 8.0, p0[1] + sa * 6.5 + inward[1] * 8.0)
    barb = bezier(p0, p1, p2, 14)
    stroke(tail, barb, lambda t: 3.0 - 2.4 * t, SHELL[1:6], rim=OUTLINE, min_r=0.6)
    # venom glow on the last third of the barb
    if p.venom > 0.05:
        for i, (x, y) in enumerate(barb[7:]):
            tail.tint(x, y, VENOM[2] if i < 3 else VENOM[3], min(1.0, 0.75 * p.venom))
        tail.put(p2[0], p2[1], VENOM[3] if p.venom > 0.5 else VENOM[1])
    cv.blit(tail, rim=OUTLINE)
    return p2[0], p2[1], math.atan2(p2[1] - p1[1], p2[0] - p1[0])


def draw_drip(cv: Canvas, p: Pose, tip) -> None:
    if p.venom <= 0.2:
        return
    x, y, _ = tip
    f = p.drip if p.drip >= 0 else (p.phase / math.tau) % 1.0
    if f > 0.9999:
        f = 0.0
    # the bead swells on the tip, stretches, then falls
    if f < 0.6:
        n = 1 + int(f / 0.6 * 3)
        for j in range(n):
            cv.put(x, y + 1 + j, VENOM[3] if j == n - 1 else VENOM[2], solid=False)
        if n >= 3:
            cv.put(x + 1, y + n, VENOM[2], solid=False, alpha=180)
    else:
        k = (f - 0.6) / 0.4
        dy = y + 3 + 46 * k * k
        if dy < GROUND - 1:
            cv.put(x, dy, VENOM[3], solid=False)
            cv.put(x, dy - 1, VENOM[2], solid=False, alpha=170)
            cv.put(x, dy - 2, VENOM[1], solid=False, alpha=90)
        cv.put(x, y + 1, VENOM[2], solid=False)


# ---------------------------------------------------------------- legs
def leg_points(rig: Rig, i: int):
    p = rig.p
    hip_lx, tip_lx, knee_h, near = LEGS[i]
    _, bot = rig.extents(hip_lx)
    hx, hy = rig.at(hip_lx, -bot + 3 + (0 if near else 3))
    tdx, tdh = _get(p.tips, i, (0.0, 0.0))
    tx = CX + tip_lx + tdx
    ty = GROUND - tdh - (0 if near else 2) + 0.5
    side = -1 if tip_lx < hip_lx else 1
    kh = knee_h + _get(p.knees, i, 0.0)
    if p.curl > 0:                                   # belly-up: legs fold into the air
        c = p.curl
        ux = hx + side * (5 + 2 * (i % 4)) * (1 - 0.3 * c)
        uy = hy - 10 - 5 * (i % 2)
        tx, ty = lerp(tx, ux, c), lerp(ty, uy, c)
        kh = kh * (1 - c) + 4 * c
    kx = lerp(hx, tx, 0.45) + side * 2
    ky = min(hy, ty) - kh
    mx, my = lerp(kx, tx, 0.5) + side * 2.0, lerp(ky, ty, 0.35)
    return (hx, hy), (kx, ky), (mx, my), (tx, ty), near


def draw_leg(cv: Canvas, rig: Rig, i: int) -> None:
    (hx, hy), (kx, ky), (mx, my), (tx, ty), near = leg_points(rig, i)
    cols = LEGC if near else LEGC[:-2]
    shade = 0.0 if near else -0.12
    femur = bezier((hx, hy), ((hx + kx) / 2 - 0.5, (hy + ky) / 2 - 1.5), (kx, ky), 12)
    stroke(cv, femur, lambda t: 2.8 - 0.5 * t, cols, shade=shade, rim=OUTLINE)
    tib = bezier((kx, ky), (mx, my), (tx, ty), 16)
    stroke(cv, tib, lambda t: 2.3 - 1.3 * t, cols, shade=shade - 0.05, rim=OUTLINE)
    band = GOLD[2] if near else GOLD[1]
    cv.put(kx, ky, GOLD[3] if near else GOLD[2])
    cv.put(kx + 1, ky, band)
    cv.put(kx, ky + 1, GOLD[0])
    bx, by = lerp(kx, tx, 0.6), lerp(ky, ty, 0.6)
    cv.put(bx, by, band)
    cv.put(tx, ty - 0.5, GOLD[1] if near else LEGC[2])       # claw tip of the tarsus


# ---------------------------------------------------------------- pincers
def draw_pincer(cv: Canvas, rig: Rig, near: bool) -> tuple[float, float]:
    """Arm + chela; drawn on its own canvas and rimmed. Returns the fingertip point."""
    p = rig.p
    s = 1.0 if near else 0.84
    off = p.claw_n if near else p.claw_f
    rot = (p.rot_n if near else p.rot_f - 0.12)
    opn = p.open_n if near else p.open_f
    shade = 0.0 if near else -0.2
    ramp_c = SHELL if near else SHELL[:-1]
    sh = rig.at(HEAD_X + 6 if near else HEAD_X + 9, -3 if near else 0)
    wx = CX + p.dx + (-58 if near else -50) + off[0]
    wy = rig.base - (22 if near else 32) + off[1] + p.pitch * 0.6
    if p.curl > 0:
        wy = lerp(wy, GROUND - 8, p.curl)
        wx = lerp(wx, wx + 8, p.curl)
    ex_, ey_ = (sh[0] + wx) / 2 + 2, max(sh[1], wy) + 2 * s
    arm = Canvas(cv.w, cv.h)
    stroke(arm, bezier(sh, ((sh[0] + ex_) / 2, ey_ + 1), (ex_, ey_), 10),
           lambda t: (3.0 + 0.5 * t) * s, LEGC if near else LEGC[:-2], shade=shade, rim=OUTLINE)
    stroke(arm, bezier((ex_, ey_), ((ex_ + wx) / 2 + 1, (ey_ + wy) / 2 + 1), (wx, wy), 10),
           lambda t: (3.4 + 1.4 * t) * s, LEGC if near else LEGC[:-2], shade=shade, rim=OUTLINE)
    arm.put(ex_, ey_, GOLD[2] if near else GOLD[1])
    arm.put(ex_ + 1, ey_, GOLD[1])

    def P(lx, ly):                                       # chela local -> cell
        x, y = _rot(lx * s, ly * s, rot)
        return wx + x, wy + y

    # palm (manus): glossy swollen hand
    pcx, pcy = P(-9.5, 0.0)

    def palm(x, y, u, v, d):
        light = 0.58 - 0.36 * u * 0.4 - 0.5 * v - 0.25 * d + shade
        col = ramp(ramp_c, max(0.0, min(1.0, light)), x, y)
        if (u + 0.2) ** 2 + (v + 0.52) ** 2 < 0.018:
            col = SPEC[1] if near else SPEC[0]
        elif (u + 0.1) ** 2 * 0.35 + (v + 0.5) ** 2 < 0.035:
            col = SPEC[0] if near else ramp_c[-1]
        if -0.86 < v < -0.7 and -0.5 < u < 0.7 and d > 0.6 and bayer(x, y) < 0.5:
            col = GOLD[2] if near else GOLD[1]                    # gold granules on the ridge
        if 0.45 < v and abs(math.sin(u * 7)) < 0.2 and d < 0.9:
            col = ramp_c[1]                                      # ribbing on the underside
        if d > 0.75 and v > 0.2 and hash01(x, y, 8) > 0.7:
            col = ramp_c[1]
        return col

    hand = Canvas(cv.w, cv.h)
    ellipse_fill(hand, pcx, pcy, 11.5 * s, 7.8 * s, palm, tilt=rot)
    # fixed finger (upper) and movable finger (lower, opens downward)
    f0 = [P(-18, -3.6), P(-28, -6.0), P(-36, -1.0)]
    hinge = (-17.5, 3.2)
    m_ang = -(0.12 + opn * 0.7)
    def M(lx, ly):
        x, y = _rot(lx - hinge[0], ly - hinge[1], -m_ang)
        return P(hinge[0] + x, hinge[1] + y)
    f1 = [M(-17.5, 3.2), M(-27, 4.2), M(-35, 0.6)]
    fingers = Canvas(cv.w, cv.h)
    stroke(fingers, bezier(*f1, 12), lambda t: (2.6 - 1.9 * t) * s, ramp_c[:-1],
           shade=shade - 0.05, rim=OUTLINE, min_r=0.6)
    stroke(fingers, bezier(*f0, 12), lambda t: (3.0 - 2.2 * t) * s, ramp_c,
           shade=shade, rim=OUTLINE, min_r=0.6)
    # teeth on the inner edges
    for k in range(3):
        tx_, ty_ = P(-22 - 3 * k, -1.2)
        fingers.put(tx_, ty_, GOLD[3] if near else GOLD[1])
    fingers.put(f0[2][0], f0[2][1], GOLD[3] if near else GOLD[2])
    fingers.put(f1[2][0], f1[2][1], GOLD[2] if near else GOLD[1])
    hand.blit(fingers, rim=OUTLINE)
    arm.blit(hand, rim=OUTLINE)
    cv.blit(arm, rim=OUTLINE)
    return (f0[2][0] + f1[2][0]) / 2, (f0[2][1] + f1[2][1]) / 2


# ---------------------------------------------------------------- effects
def draw_smear(cv: Canvas, tip, k: float) -> None:
    """Snap arc: two crescent jaws closing in front of the pincer + sparks."""
    if k <= 0:
        return
    bx, by = tip[0] - 6, tip[1]
    for r, c in ((5.0, GOLD[4]), (6.5, GOLD[3]), (8.0, GOLD[2])):
        for i in range(26):
            t_ = i / 25
            for lo, hi in ((math.pi * 1.1, math.pi * 1.7), (math.pi * 0.3, math.pi * 0.9)):
                ang = lo + (hi - lo) * t_
                x = bx + math.cos(ang) * r
                y = by + math.sin(ang) * r * 0.8
                col = WHITE if (r < 6 and 0.3 < t_ < 0.7) else c
                cv.put(x, y, col, solid=False, alpha=int(255 * min(1.0, k)))
    for j in range(6):
        ang = math.tau * j / 6 + 0.4
        for q in range(2 + int(2 * k)):
            cv.put(bx + math.cos(ang) * (10 + q), by + math.sin(ang) * (8 + q), GOLD[3],
                   solid=False, alpha=int(230 * k))


def draw_splash(cv: Canvas, tip, k: float) -> None:
    if k <= 0:
        return
    x, y, _ = tip
    a = min(1.0, k)
    for j in range(14):
        ang = math.pi * (0.55 + 0.9 * j / 13) + 0.2 * (hash01(j, 1, 5) - 0.5)
        ln = 6 + 9 * hash01(j, 2, 5)
        for q in range(int(ln * (0.4 + 0.6 * k))):
            px = x + math.cos(ang) * (2 + q)
            py = y + math.sin(ang) * (2 + q) * 0.8 + 0.04 * q * q
            c = VENOM[4] if q < 2 else VENOM[3] if q < 5 else VENOM[2]
            cv.put(px, py, c, solid=False, alpha=int(255 * a))
    for r in range(3, 7):
        for i in range(int(r * 5)):
            ang = math.tau * i / (r * 5)
            if hash01(i, r, 9) < 0.45:
                cv.put(x + math.cos(ang) * r * 1.2, y + math.sin(ang) * r * 0.7, VENOM[2],
                       solid=False, alpha=int(200 * a))
    cv.glow(x, y, 10, VENOM[2], 0.55 * a)


def draw_spray(cv: Canvas, tip, prog: float, fade: float) -> None:
    """A cone of toxic mist from the stinger towards the hero (left)."""
    if prog <= 0:
        return
    sx, sy, _ = tip
    end_x = 6.0
    head = lerp(sx, end_x, min(1.0, prog))
    n = 320
    for j in range(n):
        t = hash01(j, 3, 21)                                   # position along the jet
        x = lerp(sx, sx + (end_x - sx) * 1.0, t)
        if x < head:
            continue
        spread = 2 + 20 * t ** 0.9
        y = sy + 14 * t + 14 * t * t + (hash01(j, 7, 21) - 0.5) * 2 * spread
        w = t - fade * 1.15
        if w <= -0.15:
            continue
        a = max(0.0, min(1.0, 0.35 + w)) * (1 - 0.6 * fade)
        size = 1 + int(2.2 * t * hash01(j, 9, 21))
        c = VENOM[4] if t < 0.12 else VENOM[3] if t < 0.4 else VENOM[2] if hash01(j, 4, 2) > 0.4 \
            else VENOM[1]
        for q in range(size):
            for r_ in range(size):
                if (q + r_) <= size:
                    cv.put(x + q, y + r_, c, solid=False, alpha=int(230 * a))
    # streaks in the jet core
    for k in range(4):
        off = (k - 1.5) * 2.0
        for i in range(90):
            t = i / 89
            x = lerp(sx, head, t)
            y = sy + 14 * t + 14 * t * t + off * t * 2.5
            if hash01(i, k, 13) < 0.25 + 0.5 * fade:
                continue
            cv.put(x, y, VENOM[3] if t < 0.5 else VENOM[2], solid=False,
                   alpha=int(220 * (1 - fade)))
    if prog >= 0.95 and fade < 0.95:                           # cloud at the far end
        cxl, cyl = end_x + 16, sy + 28
        for j in range(60):
            ang = hash01(j, 1, 31) * math.tau
            r = 3 + 10 * hash01(j, 2, 31) * (0.6 + 0.6 * fade)
            cv.put(cxl + math.cos(ang) * r * 1.4, cyl + math.sin(ang) * r * 0.8,
                   VENOM[2] if j % 3 else VENOM[3], solid=False, alpha=int(200 * (1 - fade)))


def draw_guard(cv: Canvas, rig: Rig, k: float) -> None:
    """Amber shell aura: a thin arc of light over the hunkered body (cast)."""
    if k <= 0:
        return
    cx_ = rig.ox - 4
    cy_ = rig.base - 8
    for i in range(160):
        a = math.pi + math.pi * i / 159
        x = cx_ + math.cos(a) * 66
        y = cy_ + math.sin(a) * 52
        if hash01(i, 2, 17) < 0.3:
            continue
        c = GOLD[3] if (i // 6) % 3 == 0 else GOLD[2]
        cv.put(x, y, c, solid=False, alpha=int(200 * min(1.0, k)))
        if k > 0.6 and i % 4 == 0:
            cv.put(x, y + 1, GOLD[1], solid=False, alpha=int(150 * k))


# ---------------------------------------------------------------- render
def render(p: Pose, t: float = 0.0) -> Canvas:
    cv = Canvas(CELL_W, CELL_H)
    rig = Rig(p)
    for i in range(4, 8):
        draw_leg(cv, rig, i)
    far_tip = draw_pincer(cv, rig, near=False)
    body = Canvas(CELL_W, CELL_H)
    draw_body(body, rig)
    cv.blit(body, rim=OUTLINE)
    tip = draw_tail(cv, rig)
    for i in range(4):
        draw_leg(cv, rig, i)
    near_tip = draw_pincer(cv, rig, near=True)
    eye = draw_eyes(cv, rig)
    outline(cv, OUTLINE)
    if p.eye > 0.05:
        cv.glow(eye[0], eye[1], 4 + 3 * p.eye, EYE[1], 0.35 * p.eye)
        ex2, ey2 = rig.at(-45, 2)
        cv.glow(ex2, ey2, 3 + 2 * p.eye, EYE[1], 0.3 * p.eye)
    if p.venom > 0.05:
        cv.glow(tip[0], tip[1], 4 + 4 * p.venom, VENOM[2], 0.4 * p.venom)
        tel = tail_chain(rig)
        (ex, ey), a_t = tel[0][-1], tel[2]
        cv.glow(ex + math.cos(a_t) * 9 + 2, ey + math.sin(a_t) * 9 + 2, 6 + 3 * p.venom, VENOM[1],
                0.25 * p.venom, halo=False)
    draw_drip(cv, p, tip)
    draw_guard(cv, rig, p.guard)
    if p.smear > 0:
        draw_smear(cv, far_tip if p.smear_far else near_tip, p.smear)
    draw_splash(cv, tip, p.splash)
    draw_spray(cv, tip, p.spray, p.spray_fade)
    for (mx, my, lv) in p.motes:
        cv.put(mx, my, VENOM[lv] if lv < 4 else GOLD[3], solid=False)
    flash(cv, p.flash)
    if p.dissolve > 0:
        dissolve(cv, p.dissolve, GROUND - 100, GROUND + 2, VENOM[3], VENOM[1], upward=True)
    return cv


# ---------------------------------------------------------------- animations
IDLE_FRAMES = 12


def idle_pose(i: int, n: int = IDLE_FRAMES) -> Pose:
    a = math.tau * i / n
    knees = tuple(1.2 * math.sin(a + k * 0.9) for k in range(8))
    flex = max(0.0, math.sin(a * 2 + 0.6))
    return Pose(lift=round(1.0 * math.sin(a)), breath=math.sin(a - 0.6), phase=a, knees=knees,
                tail_sway=1.0,
                claw_n=(0.0, round(-1.0 * math.sin(a + 0.5))), claw_f=(0.0, round(-1.0 * math.sin(a + 1.4))),
                open_n=0.3 + 0.35 * flex, open_f=0.3 + 0.3 * max(0.0, math.sin(a * 2 + 2.2)),
                eye=0.75 if i == 8 else 1.0, venom=0.85 + 0.2 * math.sin(a))


def idle_frames():
    return [(idle_pose(i), 110) for i in range(IDLE_FRAMES)]


def _front_step(reach: float) -> tuple:
    """Front leg tips stepping towards the hero during a lunge."""
    return ((-reach, 0.0), (-reach * 0.6, 0.0), (0.0, 0.0), (0.0, 0.0),
            (-reach * 0.8, 0.0), (-reach * 0.4, 0.0), (0.0, 0.0), (0.0, 0.0))


def attack_frames():
    """Pinzas: rears with both pincers open, lunges and snaps near then far (2 strikes)."""
    b = idle_pose(0)
    return [
        (replace(b, dx=3, pitch=3, lift=1, claw_n=(4, -6), claw_f=(4, -6), rot_n=0.25, rot_f=0.25,
                 open_n=0.9, open_f=0.9, eye=1.2, tail_a=-1.0), 110),
        (replace(b, dx=6, pitch=6, lift=2, claw_n=(7, -12), claw_f=(6, -12), rot_n=0.45, rot_f=0.4,
                 open_n=1.0, open_f=1.0, eye=1.4, tail_a=-0.9, knees=(3,) * 8), 130),
        (replace(b, dx=-12, sx=1.04, pitch=-1, claw_n=(-18, 4), claw_f=(-2, -8), rot_n=-0.1,
                 rot_f=0.3, open_n=0.0, open_f=1.0, eye=1.4, tips=_front_step(6), smear=1.0,
                 tail_a=-1.25), 60),
        (replace(b, dx=-12, pitch=0, claw_n=(-12, 2), claw_f=(-6, -6), rot_n=0.0, rot_f=0.2,
                 open_n=0.6, open_f=1.0, eye=1.3, tips=_front_step(6), smear=0.4, tail_a=-1.2), 70),
        (replace(b, dx=-14, sx=1.04, pitch=-1, claw_n=(-6, -4), claw_f=(-20, 6), rot_n=0.2,
                 rot_f=-0.1, open_n=0.8, open_f=0.0, eye=1.4, tips=_front_step(7), smear=1.0,
                 smear_far=True, tail_a=-1.25), 60),
        (replace(b, dx=-13, claw_n=(-4, -2), claw_f=(-14, 4), open_n=0.5, open_f=0.3, eye=1.25,
                 tips=_front_step(7), smear=0.4, smear_far=True, tail_a=-1.2), 80),
        (replace(b, dx=-8, claw_n=(-2, 0), claw_f=(-6, 2), open_n=0.3, open_f=0.3,
                 tips=_front_step(4), eye=1.1), 90),
        (replace(b, dx=-3, tips=_front_step(1)), 90),
        (b, 110),
    ]


def sting_frames():
    """Aguijonazo: the tail coils back, whips over the head and stabs far left."""
    b = idle_pose(0)
    return [
        (replace(b, dx=3, pitch=-1, tail_a=-0.8, tail_c=-0.5, claw_n=(4, -2), claw_f=(4, -2),
                 open_n=0.5, venom=1.3, eye=1.2), 120),
        (replace(b, dx=6, pitch=-2, lift=1, tail_a=-0.55, tail_c=-0.58, claw_n=(6, -3), claw_f=(6, -3),
                 open_n=0.7, open_f=0.7, venom=1.6, eye=1.4, knees=(3,) * 8), 140),
        (replace(b, dx=-4, pitch=1, tail_a=-1.75, tail_c=-0.38, tail_len=1.2, claw_n=(10, 5),
                 claw_f=(10, 3), rot_n=0.3, rot_f=0.3, venom=1.6, eye=1.4), 55),
        (replace(b, dx=-18, sx=1.03, pitch=-4, lift=-1, tail_a=-2.2, tail_c=-0.3, tail_len=1.6,
                 claw_n=(18, 9), claw_f=(16, 7), rot_n=0.6, rot_f=0.55, open_n=0.6, venom=1.8,
                 eye=1.5, tips=_front_step(7), splash=1.0, drip=0.0), 60),
        (replace(b, dx=-17, pitch=-3, lift=-1, tail_a=-2.15, tail_c=-0.31, tail_len=1.55,
                 claw_n=(16, 8), claw_f=(14, 6), rot_n=0.5, rot_f=0.5, venom=1.5, eye=1.3,
                 tips=_front_step(7), splash=0.55, drip=0.0), 90),
        (replace(b, dx=-10, pitch=-1, tail_a=-1.5, tail_c=-0.42, tail_len=1.2, claw_n=(5, 3),
                 venom=1.2, tips=_front_step(4), splash=0.2, drip=0.0), 90),
        (replace(b, dx=-3, tail_a=-1.2, tail_c=-0.42, venom=1.0, drip=0.0), 90),
        (b, 110),
    ]


def spray_frames():
    """Toxina: the tail aims forward and sprays a cone of venom mist to the left."""
    b = idle_pose(0)
    aim = dict(tail_a=-1.6, tail_c=-0.3, tail_len=1.15)
    out = [
        (replace(b, dx=2, pitch=2, venom=1.3, eye=1.2, tail_a=-1.35, tail_c=-0.38,
                 claw_n=(3, -3), claw_f=(3, -3), open_n=0.5), 110),
        (replace(b, dx=3, pitch=3, lift=1, venom=1.9, eye=1.35, **aim, claw_n=(5, -5),
                 claw_f=(5, -5), open_n=0.8, open_f=0.8, knees=(2,) * 8, drip=0.3), 130),
    ]
    for k, s in enumerate((0.3, 0.6, 0.9, 1.0, 1.0, 1.0)):
        out.append((replace(b, dx=3 - 0.5 * k, pitch=2, lift=1, venom=1.8 - 0.1 * k, eye=1.35,
                            **aim, claw_n=(5, -5), claw_f=(5, -5), open_n=0.8, open_f=0.8,
                            spray=s, spray_fade=max(0.0, (k - 3) / 3.0), drip=0.0,
                            phase=0.4 * k), 70 if k < 4 else 85))
    out += [(replace(b, dx=1, tail_a=-1.25, tail_c=-0.45, venom=1.1, drip=0.0), 90), (b, 110)]
    return out


def cast_frames():
    """Caparazón: hunkers, pincers raised to guard, an amber glint sweeps across the shell."""
    b = idle_pose(0)
    out = []
    ks = [0.25, 0.6, 1.0, 1.0, 1.0, 1.0, 1.0, 0.7, 0.35]
    gl = [-1, -1, 0.0, 0.2, 0.42, 0.64, 0.86, 1.05, -1]
    for k, (c, g) in enumerate(zip(ks, gl)):
        out.append((replace(b, lift=-round(4 * c), pitch=-round(2 * c), claw_n=(8 * c, -10 * c),
                            claw_f=(7 * c, -9 * c), rot_n=-0.9 * c, rot_f=-0.8 * c,
                            open_n=0.1, open_f=0.1, tail_a=-1.12 - 0.15 * c, tail_c=-0.43 - 0.08 * c,
                            knees=tuple(-3 * c for _ in range(8)), eye=1.0 + 0.4 * c,
                            venom=1.0 + 0.4 * c, glint=g, guard=c if 2 <= k <= 7 else 0.0,
                            drip=0.0), 85))
    out.append((b, 110))
    return out


def hurt_frames():
    b = idle_pose(0)
    scr = ((-3, 3), (3, 2), (-2, 3), (3, 2), (2, 3), (-3, 2), (3, 3), (-2, 2))
    scr2 = tuple((-a, h - 1) for a, h in scr)
    return [
        (replace(b, dx=6, pitch=4, flash=0.85, eye=0.4, tips=scr, claw_n=(6, -5), claw_f=(6, -5),
                 open_n=1.0, open_f=1.0, tail_a=-0.95, venom=0.6), 55),
        (replace(b, dx=8, pitch=3, flash=0.55, eye=0.6, tips=scr2, claw_n=(6, -3), claw_f=(6, -3),
                 open_n=0.8, open_f=0.8, tail_a=-1.0), 65),
        (replace(b, dx=6, pitch=1, flash=0.2, eye=0.8, tips=scr, open_n=0.5), 70),
        (replace(b, dx=4, tips=_front_step(-1)), 70),
        (replace(b, dx=2), 80),
        (b, 100),
    ]


def death_frames():
    b = idle_pose(0)
    out = [
        (replace(b, dx=6, pitch=5, flash=0.85, eye=0.5, claw_n=(6, -8), claw_f=(6, -8),
                 open_n=1.0, open_f=1.0, tail_a=-0.9), 70),
        (replace(b, dx=6, pitch=8, lift=2, flash=0.3, eye=1.8, venom=1.6, claw_n=(5, -12),
                 claw_f=(5, -12), rot_n=-0.4, rot_f=-0.4, open_n=1.0, open_f=1.0, tail_a=-0.8,
                 tail_c=-0.5), 110),
    ]
    steps = 12
    for k in range(steps):
        u = (k + 1) / steps
        c = smooth(min(1.0, u * 1.8))
        drop = smooth(min(1.0, u * 2.2))
        motes = tuple(
            (CX - 50 + hash01(k, j, 9) * 100, GROUND - 4 - u * 60 * hash01(j, k, 4),
             1 + int(hash01(j, k, 2) * 3)) for j in range(6 + k)) if u > 0.35 else ()
        out.append((replace(b, dx=6, lift=-14 * drop + 2 * (1 - drop), pitch=8 * (1 - c) - 3 * c,
                            curl=c, eye=1.6 * (1 - c), venom=1.4 * (1 - u),
                            tail_a=lerp(-0.8, -1.45, c), tail_c=lerp(-0.5, -0.64, c), tail_len=1 - 0.12 * c,
                            claw_n=(5 - 2 * c, -12 * (1 - c)), claw_f=(5, -12 * (1 - c)),
                            rot_n=-0.4 * (1 - c) + 0.3 * c, rot_f=-0.4 * (1 - c) + 0.3 * c,
                            open_n=1.0, open_f=1.0, drip=0.0,
                            dissolve=0.0 if u < 0.45 else min(1.0, (u - 0.45) / 0.55),
                            motes=motes), 85))
    out.append((replace(b, dissolve=1.0), 120))
    return out


ANIMATIONS = {
    "idle": (idle_frames, True),
    "attack": (attack_frames, False),
    "sting": (sting_frames, False),
    "spray": (spray_frames, False),
    "cast": (cast_frames, False),
    "hurt": (hurt_frames, False),
    "death": (death_frames, False),
}
EVENTS = {"attack": {"strikes": [2, 4]}, "sting": {"strikes": [3]}, "spray": {"strikes": [5]}}
MOVES = {"pinch": "attack", "sting": "sting", "toxin": "spray", "shell": "cast", "frenzy": "cast",
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
