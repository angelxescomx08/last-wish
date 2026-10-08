"""Draw and animate the enemy "Ojo Vigilante" (a floating watcher eye). Stdlib only:

    python scripts/generate_enemy_eye.py

Same method as the Espectro (``docs/code-drawn-sprites.md``): one renderer, every
frame a ``Pose``. A debuffer: its gaze leaves the hero Vulnerable, Débil, Enredado.

* a big glossy eyeball (ivory-pink sclera with red veins, upper-left light) held in
  heavy fleshy lids that narrow, widen and blink;
* a huge violet iris with a slit pupil that looks LEFT at the hero, a wet cornea
  highlight and a faint glow;
* five dangling tentacles / optic nerves beneath (tapered tubes, darker flesh, the far
  ones darker still), waving out of phase with curling tips.

Animations (non-death actions end on idle frame 0):
  idle    12-frame hover loop: bob, tentacles wave, the iris darts, one blink
  attack  "Rayo Ocular": the lids narrow, the iris goes white-hot, a beam fires left
  cast    "Mirada Paralizante" / "Pesadilla": eye wide, pupil dilates, hypnotic rings
          pulse towards the hero, tentacles stiffen and spread
  hurt    white flash, the eye squeezes shut, knocked right, tentacles flail
  death   the eye rolls up bloodshot, deflates, tentacles go limp, it falls and
          dissolves into violet motes

Output: ``assets/enemies/eye_sheet.png`` + ``.json`` (``events.attack.strikes``).
"""
from __future__ import annotations

import math
import sys
from dataclasses import dataclass, field, replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from pixel_kit import (Canvas, bayer, build_sheet, dissolve, flash, hash01, mix,  # noqa: E402
                       outline, ramp, save_sheet, smooth, stroke)

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "assets" / "enemies"
SHEET_ID = "eye"

CELL_W, CELL_H = 160, 108
CX, GROUND = CELL_W - 48, 100     # eyeball centre line, floor row
ANCHOR = (CX, GROUND + 2)         # floor point under the eye (shadow)
EY = 51                           # eyeball centre row (body top ≈ 66 px above the floor)
R = 18.0                          # eyeball radius (≈ 36 px sphere)
IR = 8.6                          # iris radius

# ---------------------------------------------------------------- palette
OUTLINE = (26, 8, 24)
FLESH = [(40, 12, 34), (70, 22, 50), (106, 36, 66), (144, 58, 84), (180, 90, 104), (212, 130, 126),
         (236, 172, 156)]
TENT = [(34, 10, 30), (60, 20, 44), (94, 34, 60), (132, 56, 78), (170, 88, 100), (206, 130, 128)]
SCLERA = [(118, 76, 92), (164, 118, 128), (204, 164, 160), (230, 200, 186), (246, 228, 212),
          (255, 246, 234)]
VEIN = [(110, 12, 36), (160, 28, 48), (200, 64, 76)]
IRIS = [(34, 8, 58), (70, 20, 112), (112, 40, 170), (156, 78, 220), (204, 150, 255), (244, 226, 255)]
PINK = (246, 128, 228)
VOID = (12, 4, 18)
HOT = (255, 244, 255)
WHITE = (255, 255, 255)

# Tentacles: (root along the eyeball bottom -1..1, base angle deg (90 = down), length, phase,
# curl direction, back?)
TENTACLES = [
    (-0.62, 114, 16, 0.0, 1, True),
    (0.66, 64, 17, 2.2, -1, True),
    (-0.34, 101, 21, 1.1, -1, False),
    (0.02, 89, 23, 3.3, 1, False),
    (0.36, 76, 20, 4.6, -1, False),
]


def _veins():
    """Vein polylines in eyeball-local units (radius 1), each with the blood level that shows it."""
    out = []
    starts = [(0.2, 0.0), (0.75, 0.0), (1.25, 0.0), (-0.35, 0.0), (2.2, 0.0), (-0.9, 0.0),
              (0.45, 0.5), (1.0, 0.45), (-0.1, 0.55), (1.6, 0.6), (2.55, 0.7), (-0.6, 0.75),
              (0.05, 0.85), (1.45, 0.9)]
    for k, (a, level) in enumerate(starts):
        x, y = math.cos(a) * 1.02, math.sin(a) * 1.02
        ang = math.atan2(-y, -x - 0.2)
        pts = [(x, y)]
        n = 9 + int(hash01(k, 1, 3) * 6)
        for s in range(n):
            ang += (hash01(k, s, 7) - 0.5) * 0.9
            x += math.cos(ang) * 0.055
            y += math.sin(ang) * 0.055
            pts.append((x, y))
            if s == n // 2 and hash01(k, 2, 5) > 0.35:            # a short branch
                bx, by, ba = x, y, ang + (0.8 if hash01(k, 3, 5) > 0.5 else -0.8)
                br = [(bx, by)]
                for q in range(4):
                    ba += (hash01(k, q, 11) - 0.5) * 0.7
                    bx += math.cos(ba) * 0.05
                    by += math.sin(ba) * 0.05
                    br.append((bx, by))
                out.append((br, level + 0.2, True))
        out.append((pts, level, False))
    return out


VEINS = _veins()


@dataclass(frozen=True)
class Pose:
    dx: float = 0.0
    dy: float = 0.0
    sx: float = 1.0
    sy: float = 1.0
    phase: float = 0.0            # tentacle wave
    gaze: tuple[float, float] = (-0.55, 0.05)    # iris direction (-1..1, left/up negative)
    lid: float = 1.0              # 0 shut .. 1 open .. 1.35 wide
    scowl: float = 0.6            # upper lid lowered towards the hero (menace)
    pupil: float = 0.0            # 0 slit .. 1 dilated round
    heat: float = 0.0             # iris goes white-hot (beam charge)
    hyp: float = 0.0              # hypnotic swirl in the iris
    eye: float = 1.0              # iris glow
    spread: float = 0.0           # tentacles stiffen and spread
    flail: float = 0.0            # tentacles thrash (hurt)
    limp: float = 0.0             # tentacles hang dead (death)
    blood: float = 0.0            # bloodshot sclera
    deflate: float = 0.0          # death: the ball sags
    flash: float = 0.0
    dissolve: float = 0.0
    beam: float = 0.0             # beam length progress 0..1
    beam_fade: float = 0.0
    burst: float = 0.0            # impact burst at the beam's end
    ring: float = 0.0             # hypnotic rings progress
    ring_fade: float = 0.0
    motes: tuple = field(default_factory=tuple)


class Eye:
    """Geometry of the eyeball for one pose."""

    def __init__(self, p: Pose) -> None:
        self.p = p
        self.x = CX + p.dx
        self.y = EY + p.dy
        d = max(0.0, min(1.0, p.deflate))
        self.rx = R * p.sx * (1 + 0.1 * d)
        self.rt = R * p.sy * (1 - 0.4 * d)       # top half sags when it deflates
        self.rb = R * p.sy * (1 - 0.08 * d)
        gx = max(-1.2, min(1.2, p.gaze[0]))
        gy = max(-1.4, min(1.2, p.gaze[1]))
        self.ix = self.x + gx * self.rx * 0.56
        self.iy = self.y + gy * (self.rt if gy < 0 else self.rb) * 0.5
        self.irx = IR * p.sx * (1 - 0.3 * min(1.0, abs(gx)))
        self.iry = IR * p.sy * (1 - 0.25 * max(0.0, -gy - 0.6)) * (1 - 0.25 * d)

    def ry(self, dy: float) -> float:
        return self.rt if dy < 0 else self.rb

    def lid_edges(self, x: float):
        """(upper, lower) edge rows of the lid opening at column ``x``; None when shut there."""
        p = self.p
        lid = max(0.0, p.lid)
        if lid <= 0.02:
            return None
        ox = self.x - 1
        w = self.rx * 0.97
        u = (x - ox) / w
        if abs(u) >= 1:
            return None
        k = (1 - u * u) ** 0.62
        y0 = self.y + 1.0
        up = y0 - self.rt * 0.66 * lid * k + p.scowl * 3.2 * max(0.0, -u) * min(1.0, lid)
        dn = y0 + self.rb * 0.5 * min(1.25, lid) * k
        if up >= dn - 0.4:
            return None
        return up, dn


# ---------------------------------------------------------------- tentacles
def tentacle_points(e: Eye, spec) -> list[tuple[float, float]]:
    p = e.p
    ru, ang_deg, length, ph, curl_dir, _ = spec
    rx = e.x + ru * e.rx * 0.72
    ry = e.y + e.rb * (0.62 + 0.18 * (1 - abs(ru)))
    base = math.radians(ang_deg)
    base += (base - math.pi / 2) * 0.9 * p.spread
    base = base + (math.pi / 2 - base) * 0.6 * p.limp
    amp = (0.32 + 0.75 * p.flail) * (1 - 0.7 * p.spread) * (1 - 0.8 * p.limp)
    curl = curl_dir * 1.5 * (1 - 0.65 * p.spread) * (1 - 0.7 * p.limp)
    length = length * (1 + 0.12 * p.spread + 0.15 * p.limp)
    n = 14
    seg = length / n
    x, y = rx, ry
    pts = [(x, y)]
    for s in range(1, n + 1):
        f = s / n
        wave = amp * math.sin(p.phase + ph - f * 3.4) * f
        if p.flail > 0:
            wave += p.flail * 0.5 * math.sin(p.phase * 2 + ph * 3 + f * 5)
        a = base + wave + curl * f ** 2.6
        x += math.cos(a) * seg
        y += math.sin(a) * seg
        pts.append((x, y))
    return pts


def draw_tentacles(cv: Canvas, e: Eye, back: bool) -> None:
    for spec in TENTACLES:
        if spec[5] != back:
            continue
        pts = tentacle_points(e, spec)
        thick = 2.7 if not back else 2.3
        tube = stroke(cv, pts, lambda t, th=thick: th * (1 - t) ** 0.8 + 0.55, TENT,
                      shade=-0.22 if back else -0.02, rim=OUTLINE)
        # pale rings along the nerve (every few px) for a fleshy, segmented read
        for i in range(3, len(pts) - 3, 3):
            x, y = pts[i]
            if tube.get(int(x), int(y)) is not None:
                cv.put(int(x), int(y), TENT[4] if not back else TENT[3])
        tip = pts[-1]
        cv.put(int(tip[0]), int(tip[1]), TENT[5] if not back else TENT[4])


# ---------------------------------------------------------------- eyeball
def draw_eye(cv: Canvas, e: Eye) -> set:
    """Lids + eyeball + iris. Returns the set of visible eyeball pixels."""
    p = e.p
    seen: set = set()
    shell = 1.6                                    # lid thickness beyond the ball
    lx, ly, lz = -0.52, -0.62, 0.59                # light from the upper left, in front
    d_def = max(0.0, min(1.0, p.deflate))
    x0, x1 = int(e.x - e.rx - shell - 1), int(e.x + e.rx + shell + 2)
    y0, y1 = int(e.y - e.rt - shell - 3), int(e.y + e.rb + shell + 2)
    sclera_px = []
    seam_y0 = e.y + 1.0
    for y in range(y0, y1):
        for x in range(x0, x1):
            px, py = x + 0.5, y + 0.5
            ddx, ddy = px - e.x, py - e.y
            ry = e.ry(ddy)
            # wrinkles on the deflating ball
            wob = 1 + 0.06 * d_def * math.sin(ddx * 0.9 + ddy * 0.3)
            sh_y = shell + (1.4 if ddy < 0 else 0.0)            # heavy brow-like upper lid
            su, sv = ddx / (e.rx + shell), ddy / (ry + sh_y) * wob
            if su * su + sv * sv > 1:
                continue
            u, v = ddx / e.rx, ddy / ry * wob
            inside_ball = u * u + v * v <= 1
            edges = e.lid_edges(px)
            in_open = inside_ball and edges is not None and edges[0] < py < edges[1]
            if in_open:
                nz = math.sqrt(max(0.0, 1 - u * u - v * v))
                light = 0.42 + 0.62 * (u * lx + v * ly + nz * lz)
                # shadow cast by the heavy upper lid
                dist_up = py - edges[0]
                if dist_up < 3.2:
                    light -= 0.42 * (1 - dist_up / 3.2)
                dist_dn = edges[1] - py
                if dist_dn < 1.6:
                    light -= 0.18
                corner = abs((px - e.x + 1) / (e.rx * 0.97))
                light -= 0.35 * max(0.0, corner - 0.6) ** 1.5 * 2
                light -= 0.12 * p.blood
                col = ramp(SCLERA, max(0.0, min(1.0, light)), x, y)
                if p.blood > 0:
                    col = mix(col, VEIN[1], 0.28 * p.blood * (0.4 + 0.6 * (u * u + v * v)))
                cv.put(x, y, col)
                seen.add((x, y))
                sclera_px.append((x, y))
            else:
                # fleshy lid (or the shell around the ball)
                nu, nv = su, sv
                nz = math.sqrt(max(0.0, 1 - nu * nu - nv * nv))
                light = 0.34 + 0.6 * (nu * lx + nv * ly + nz * lz)
                light += 0.05 * math.sin(nu * 7 + nv * 5) - 0.06 * hash01(x // 2, y // 2, 9)
                if nu > 0.5 and nv > 0.3:                       # cold bounce light low right
                    light += 0.06
                col = None
                uo = (px - e.x + 1) / (e.rx * 0.97)
                seam = seam_y0 + 2.2 * max(0.0, 1 - uo * uo) + p.scowl * 1.5 * max(0.0, -uo)
                if edges is not None:
                    up, dn = edges
                    if py <= up:
                        g = up - py                              # distance above the lid edge
                        if g < 1.4:
                            col = OUTLINE if g < 1.0 else FLESH[1]      # lash line
                        elif 3.4 < g < 4.6 and abs(ddx) < e.rx * 0.82:
                            light -= 0.3                          # lid crease
                        elif g < 3.4:
                            light += 0.2                          # the lid's lit roll
                    else:
                        g = py - dn
                        if g < 1.1:
                            col = FLESH[5] if ddx < 2 else FLESH[4]   # wet lower rim
                        elif 2.6 < g < 3.6 and abs(ddx) < e.rx * 0.7:
                            light -= 0.2                          # lower lid bag
                elif inside_ball and abs(uo) < 0.92 and p.lid <= 0.02:
                    g = seam - py
                    if -0.5 < g < 0.9:
                        col = OUTLINE                             # shut: the seam
                    elif 0.9 <= g < 3.4:
                        light += 0.2                              # squeezed lid roll
                    elif 3.4 <= g < 4.6 or -2.6 < g < -1.6:
                        light -= 0.28                             # creases
                if col is None:
                    col = ramp(FLESH, max(0.0, min(1.0, light)), x, y)
                cv.put(x, y, col)
    if not seen:
        return seen
    # veins on the sclera
    for pts, level, thin in VEINS:
        if level > 0.25 + p.blood:
            continue
        n = len(pts)
        for i, (vu, vv) in enumerate(pts):
            x = int(e.x + vu * e.rx)
            y = int(e.y + vv * e.ry(vv))
            if (x, y) not in seen:
                continue
            f = i / max(1, n - 1)
            c = VEIN[0] if f < 0.3 and not thin else VEIN[1] if f < 0.75 else VEIN[2]
            old = cv.get(x, y)
            cv.put(x, y, mix(old[:3], c, 0.92 - 0.4 * f))
    draw_iris(cv, e, seen)
    return seen


def draw_iris(cv: Canvas, e: Eye, seen: set) -> None:
    p = e.p
    ix, iy, irx, iry = e.ix, e.iy, e.irx, e.iry
    pw = 0.16 + 0.4 * p.pupil                      # pupil half-width (iris units)
    ph = 0.78 - 0.16 * p.pupil
    for y in range(int(iy - iry) - 1, int(iy + iry) + 2):
        for x in range(int(ix - irx) - 1, int(ix + irx) + 2):
            if (x, y) not in seen:
                continue
            du, dv = (x + 0.5 - ix) / irx, (y + 0.5 - iy) / iry
            d = math.hypot(du, dv)
            if d > 1:
                continue
            theta = math.atan2(dv, du)
            if (du / pw) ** 2 + (dv / ph) ** 2 < 1:
                q = (du / pw) ** 2 + (dv / ph) ** 2
                col = VOID if q < 0.55 else IRIS[0]
                if p.hyp > 0.3 and q < 0.8 and math.sin(math.sqrt(q) * 12 - p.hyp * 5) > 0.55:
                    col = IRIS[2] if p.hyp < 0.8 else PINK               # hypnotic rings
                if p.heat > 0.2:                                  # the slit burns white
                    col = mix(col, HOT if q < 0.55 else IRIS[4], min(1.0, (p.heat - 0.2) * 1.6))
            elif d > 0.86:
                col = IRIS[0] if d > 0.93 else IRIS[1]          # dark limbal ring
            else:
                swirl = p.hyp * (d * 7.0 - 2.0)
                streak = math.sin(theta * 9 + swirl + 1.3 * hash01(int(theta * 9 + 40), 2, 6))
                lvl = 0.42 + 0.34 * dv + 0.16 * streak
                if 0.33 < d - pw * 0.4 < 0.5:
                    lvl += 0.16                                  # collarette ring
                if p.hyp > 0 and math.sin(theta * 3 - d * 9 + p.hyp * 4) > 0.55:
                    lvl += 0.35 * p.hyp                          # spiral arms
                lvl -= 0.3 * max(0.0, -dv - 0.25)               # lid shadow on top
                col = ramp(IRIS, max(0.0, min(1.0, lvl)), x, y, 0.5)
                if p.hyp > 0.5 and math.sin(theta * 3 - d * 9 + p.hyp * 4) > 0.8:
                    col = mix(col, PINK, 0.5 * p.hyp)
                if p.heat > 0:
                    col = mix(col, IRIS[3] if d > 0.45 else PINK, p.heat * 0.7)
            cv.put(x, y, col)
    # wet cornea highlight (upper left) and a soft second one
    hx, hy = ix - 0.38 * irx, iy - 0.42 * iry
    for ox, oy, c in ((0, 0, WHITE), (1, 0, WHITE), (0, 1, WHITE), (1, 1, SCLERA[5]),
                      (2, -1, SCLERA[4])):
        q = (int(hx) + ox, int(hy) + oy)
        if q in seen:
            cv.put(*q, c)
    q = (int(ix + 0.42 * irx), int(iy + 0.4 * iry))
    if q in seen:
        cv.tint(q[0], q[1], IRIS[5], 0.6)
    # broad sclera sheen on the upper-left of the ball
    sx, sy = int(e.x - e.rx * 0.6), int(e.y - e.rt * 0.18)
    for ox, oy in ((0, 0), (1, 0), (0, 1)):
        q = (sx + ox, sy + oy)
        if q in seen and abs(q[0] - ix) > irx + 1:
            cv.tint(q[0], q[1], WHITE, 0.55)


# ---------------------------------------------------------------- effects
def draw_beam(cv: Canvas, e: Eye, prog: float, fade: float, t: float) -> tuple[float, float]:
    """A thin beam fired left from the iris. Returns its end point."""
    ox, oy = e.ix - e.irx * 0.7, e.iy
    if prog <= 0:
        return ox, oy
    length = 92 * min(1.0, prog)
    ex = ox - length
    width = (1 - fade)
    for i in range(int(length) + 1):
        x = ox - i
        f = i / max(1.0, length)
        wob = 0.5 * math.sin(i * 0.7 - t * 40)
        tip = min(1.0, (length - i) / 6 + 0.3)           # the leading end tapers
        halo = (3.2 - 0.8 * f) * width * tip + wob * 0.5
        core = 1 if width > 0.55 and f < 0.85 else 0
        for dy in range(-5, 6):
            ad = abs(dy)
            if ad > halo + 1:
                continue
            if ad <= core - 0 or (ad == 0 and width > 0.25):
                c, a = (WHITE if width > 0.6 else IRIS[5]), 255
            elif ad <= core + 1 and width > 0.15:
                c, a = (IRIS[5] if width > 0.6 else IRIS[4]), 240
            elif ad <= halo:
                c, a = IRIS[3], int(220 * width)
            else:
                c, a = IRIS[2], int(140 * width)
            if hash01(int(x), dy, int(t * 30) % 7) < 0.12 and ad > 1:
                continue
            if a > 10 and width > 0.12:
                cv.put(int(x), int(oy) + dy, c, solid=False, alpha=a)
    # sparks flicking off the beam
    for j in range(10):
        s = hash01(j, 4, int(t * 20) % 5)
        x = ox - s * length
        y = oy + (hash01(j, 6, 2) - 0.5) * 10 * (0.5 + s)
        if fade < 0.9:
            cv.put(int(x), int(y), IRIS[4] if j % 2 else PINK, solid=False, alpha=int(230 * (1 - fade)))
    # muzzle flare at the eye
    cv.glow(ox, oy, 6 * width + 2, HOT, 0.8 * width)
    return ex, oy


def draw_burst(cv: Canvas, x: float, y: float, k: float) -> None:
    """Small star burst where the beam lands."""
    if k <= 0:
        return
    grow = min(1.0, k * 1.4)
    fade = max(0.0, (k - 0.55) / 0.45)
    a = int(255 * (1 - fade))
    for r in range(8):
        ang = r / 8 * math.tau + 0.2
        ln = (5 + 9 * grow) * (1.0 if r % 2 == 0 else 0.55)
        for s in range(int(ln)):
            f = s / max(1.0, ln)
            c = WHITE if f < 0.3 else IRIS[4] if f < 0.7 else IRIS[3]
            cv.put(int(x + math.cos(ang) * s), int(y + math.sin(ang) * s), c, solid=False, alpha=a)
    rr = 3 + 8 * grow
    for yy in range(-2, 3):
        for xx in range(-2, 3):
            if xx * xx + yy * yy <= 5 * (1 - fade) + 0.5:
                cv.put(int(x) + xx, int(y) + yy, WHITE if xx * xx + yy * yy < 3 else IRIS[5], solid=False, alpha=a)
    for i in range(36):
        ang = i / 36 * math.tau
        if (i % 3) == 0:
            continue
        cv.put(int(x + math.cos(ang) * rr), int(y + math.sin(ang) * rr * 0.9), PINK, solid=False,
               alpha=int(a * 0.7))
    cv.glow(x, y, 7 + 6 * grow, IRIS[3], 0.9 * (1 - fade))


def draw_rings(cv: Canvas, e: Eye, prog: float, fade: float, t: float) -> None:
    """Hypnotic concentric arcs pulsing out of the iris towards the hero (left)."""
    if prog <= 0:
        return
    cx, cy = e.ix, e.iy
    for j in range(5):
        pj = prog * 1.6 - j * 0.24
        if pj <= 0 or pj >= 1:
            continue
        r = 9 + pj * 60
        alpha = (1 - pj) ** 0.6 * (1 - fade)
        if alpha <= 0.05:
            continue
        span = 0.62 + 0.25 * (1 - pj)
        steps = int(r * span * 2.2) + 6
        c = IRIS[4] if j % 2 == 0 else PINK
        c2 = IRIS[3] if j % 2 == 0 else IRIS[2]
        for i in range(steps):
            a = math.pi - span + 2 * span * i / (steps - 1)
            if (i + int(t * 40)) % 9 >= 7:
                continue
            x = cx + math.cos(a) * r
            y = cy + math.sin(a) * r * 0.8
            cv.put(int(x), int(y), c, solid=False, alpha=int(255 * min(1.0, alpha * 1.3)))
            cv.put(int(x) + 1, int(y), c2, solid=False, alpha=int(220 * alpha))
            if pj < 0.5:
                cv.put(int(x) - 1, int(y), IRIS[5], solid=False, alpha=int(200 * alpha))


# ---------------------------------------------------------------- render
def render(p: Pose, t: float = 0.0) -> Canvas:
    cv = Canvas(CELL_W, CELL_H)
    e = Eye(p)
    draw_tentacles(cv, e, back=True)
    draw_tentacles(cv, e, back=False)
    draw_eye(cv, e)
    outline(cv, OUTLINE)
    # lights
    g = p.eye * (1 - p.blood * 0.6)
    if g > 0.05 and p.lid > 0.1:
        cv.glow(e.ix, e.iy, IR + 2 + 3 * p.heat, IRIS[3], 0.22 * g + 0.4 * p.heat, halo=p.heat > 0.3)
    if p.heat > 0.3 and p.beam <= 0:                 # charge: sparks drawn into the iris
        for j in range(10):
            a = j / 10 * math.tau + 0.5 * hash01(j, 1, 3)
            r = 6 + (16 - 9 * p.heat) * (0.6 + 0.6 * hash01(j, 2, 3))
            cv.put(int(e.ix + math.cos(a) * r), int(e.iy + math.sin(a) * r * 0.85),
                   IRIS[5] if j % 3 else PINK, solid=False)
            cv.put(int(e.ix + math.cos(a) * (r + 1.5)), int(e.iy + math.sin(a) * (r + 1.5) * 0.85),
                   IRIS[3], solid=False, alpha=150)
    draw_rings(cv, e, p.ring, p.ring_fade, t)
    if p.beam > 0:
        end = draw_beam(cv, e, p.beam, p.beam_fade, t)
        draw_burst(cv, end[0], end[1], p.burst)
    for (mx, my, lv) in p.motes:
        cv.put(int(mx), int(my), IRIS[lv] if lv < 6 else PINK, solid=False)
    flash(cv, p.flash)
    if p.dissolve > 0:
        top = e.y - e.rt - 4
        dissolve(cv, p.dissolve, top, e.y + e.rb + 30, IRIS[5], IRIS[3], upward=False)
    return cv


# ---------------------------------------------------------------- animations
IDLE_FRAMES = 12
_DART = [(-0.55, 0.05), (-0.55, 0.05), (-0.55, 0.05), (-0.62, 0.0), (-0.62, 0.0), (-0.5, 0.14),
         (-0.5, 0.14), (-0.5, 0.14), (-0.55, 0.05), (-0.6, -0.08), (-0.6, -0.08), (-0.55, 0.05)]
_BLINK = {6: 0.45, 7: 0.0, 8: 0.55}


def idle_pose(i: int, n: int = IDLE_FRAMES) -> Pose:
    k = i % n
    a = math.tau * k / n
    return Pose(
        dy=-round(2.0 * math.sin(a)), phase=a, gaze=_DART[k % len(_DART)] if n == IDLE_FRAMES else (-0.55, 0.05),
        lid=_BLINK.get(k, 1.0) if n == IDLE_FRAMES else 1.0,
        eye=0.85 + 0.15 * math.sin(2 * a),
    )


def idle_frames():
    return [(idle_pose(i), 110) for i in range(IDLE_FRAMES)]


def attack_frames():
    """Rayo Ocular: lids narrow, the iris goes white-hot, a beam fires left."""
    b = idle_pose(0)
    return [
        (replace(b, dx=1, lid=0.75, scowl=0.7, heat=0.15, gaze=(-0.6, 0.04), phase=0.4, eye=1.2), 90),
        (replace(b, dx=2, dy=-1, lid=0.5, scowl=1.0, heat=0.5, gaze=(-0.66, 0.03), spread=0.3,
                 phase=0.8, eye=1.4), 110),
        (replace(b, dx=3, dy=-1, lid=0.42, scowl=1.1, heat=0.9, gaze=(-0.68, 0.02), spread=0.5,
                 phase=1.1, eye=1.6), 100),
        (replace(b, dx=4, lid=0.48, scowl=1.1, heat=1.0, gaze=(-0.7, 0.02), spread=0.6, phase=1.5,
                 beam=0.55), 55),
        (replace(b, dx=5, lid=0.5, scowl=1.0, heat=1.0, gaze=(-0.7, 0.02), spread=0.6, phase=1.9,
                 beam=1.0, burst=0.35), 60),
        (replace(b, dx=4, lid=0.55, scowl=0.9, heat=0.75, gaze=(-0.66, 0.03), spread=0.45,
                 phase=2.4, beam=1.0, beam_fade=0.5, burst=0.75), 70),
        (replace(b, dx=3, lid=0.7, scowl=0.7, heat=0.35, gaze=(-0.6, 0.04), spread=0.2, phase=3.1,
                 beam=1.0, beam_fade=0.9, burst=1.0), 90),
        (replace(b, dx=1, lid=0.9, scowl=0.45, heat=0.1, phase=4.4), 90),
        (b, 110),
    ]


def cast_frames():
    """Mirada Paralizante / Pesadilla: eye wide, pupil dilates, hypnotic rings pulse left."""
    b = idle_pose(0)
    keys = [  # lid, pupil, spread, ring, ring_fade, hyp
        (1.12, 0.3, 0.3, 0.0, 0.0, 0.3),
        (1.3, 0.7, 0.7, 0.12, 0.0, 0.6),
        (1.36, 1.0, 1.0, 0.3, 0.0, 0.9),
        (1.36, 1.0, 1.0, 0.48, 0.0, 1.0),
        (1.36, 1.0, 1.0, 0.66, 0.0, 1.0),
        (1.3, 0.9, 0.9, 0.84, 0.25, 0.9),
        (1.18, 0.6, 0.6, 1.0, 0.6, 0.6),
        (1.06, 0.25, 0.25, 1.0, 1.0, 0.25),
    ]
    out = []
    for k, (lid, pu, sp, rg, rf, hy) in enumerate(keys):
        out.append((replace(b, lid=lid, scowl=0.3 * (1 - sp), pupil=pu, spread=sp, ring=rg, ring_fade=rf,
                            hyp=hy, dy=-round(2 * sp), gaze=(-0.5, 0.02), eye=1.0 + 0.6 * sp,
                            phase=0.35 * k), 85 if k < 6 else 90))
    out.append((b, 110))
    return out


def hurt_frames():
    b = idle_pose(0)
    return [
        (replace(b, dx=5, sx=0.92, sy=1.06, lid=0.0, flash=0.82, flail=1.0, phase=1.2, eye=0.3), 55),
        (replace(b, dx=7, sx=0.95, sy=1.03, lid=0.0, flash=0.55, flail=0.9, phase=2.0, eye=0.4), 60),
        (replace(b, dx=6, sx=1.02, lid=0.15, flash=0.25, flail=0.6, phase=2.8, eye=0.6), 70),
        (replace(b, dx=4, lid=0.6, flail=0.35, phase=3.6, gaze=(-0.45, 0.1)), 70),
        (replace(b, dx=2, lid=0.85, flail=0.15, phase=4.4), 80),
        (replace(b, dx=1, phase=5.4), 90),
        (b, 100),
    ]


def death_frames():
    b = idle_pose(0)
    out = [
        (replace(b, dx=5, sx=0.93, sy=1.05, lid=0.0, flash=0.85, flail=1.0, phase=1.0), 70),
        (replace(b, dx=6, lid=1.3, flash=0.3, gaze=(-0.4, -0.5), blood=0.35, pupil=0.4, flail=0.6,
                 phase=1.8, eye=1.4), 90),
        (replace(b, dx=6, lid=1.2, gaze=(-0.2, -1.0), blood=0.7, pupil=0.7, flail=0.3, phase=2.4,
                 eye=0.9), 90),
        (replace(b, dx=6, lid=1.0, gaze=(-0.05, -1.3), blood=1.0, pupil=0.8, limp=0.3, phase=2.9,
                 eye=0.5), 90),
    ]
    steps = 8
    for k in range(steps):
        u = (k + 1) / steps
        d = smooth(min(1.0, u * 1.3))
        fall = round(16 * u * u)
        motes = tuple(
            (CX + 6 + (hash01(k, j, 9) - 0.5) * 46, EY + fall - 10 + 20 * hash01(j, k, 4) - 30 * u,
             2 + int(hash01(j, k, 2) * 3) + (4 if j % 5 == 0 else 0))
            for j in range(6 + 2 * k))
        out.append((replace(b, dx=6, dy=fall, sx=1.0 + 0.06 * d, lid=1.0 - 0.5 * d,
                            gaze=(-0.05, -1.3), blood=1.0, pupil=0.8, limp=0.3 + 0.7 * d, deflate=d,
                            eye=0.3 * (1 - d), phase=3.2 + 0.25 * k,
                            dissolve=0.0 if u < 0.3 else min(1.0, (u - 0.3) / 0.7), motes=motes), 85))
    out.append((replace(b, dissolve=1.0), 120))
    return out


ANIMATIONS = {
    "idle": (idle_frames, True),
    "attack": (attack_frames, False),
    "cast": (cast_frames, False),
    "hurt": (hurt_frames, False),
    "death": (death_frames, False),
}

# The beam reaches the hero on attack frame 4.
EVENTS = {"attack": {"strikes": [4]}}
MOVES = {"beam": "attack", "stare": "cast", "dread": "cast", "vengeance": "cast"}


def build():
    return build_sheet(ANIMATIONS, render, (CELL_W, CELL_H), ANCHOR, f"{SHEET_ID}_sheet.png",
                       {"events": EVENTS, "moves": MOVES})


def main() -> None:
    sheet, meta = build()
    save_sheet(OUT_DIR, SHEET_ID, sheet, meta)
    print(f"wrote assets/enemies/{SHEET_ID}_sheet.png ({len(sheet[0])}x{len(sheet)}) and .json")


if __name__ == "__main__":
    main()
