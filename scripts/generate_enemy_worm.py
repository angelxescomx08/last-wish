"""Draw and animate the enemy "Gusano de Tumba" (a grave worm). Stdlib only:

    python scripts/generate_enemy_worm.py

Same method as the Espectro (``docs/code-drawn-sprites.md``): one renderer, every
frame a ``Pose``. The worm is ONE mass swept along a cubic Bézier spine (width
profile along the spine, segment rings and belly plates painted as shading):

* a thick, pale, sickly body (bluish-grey shadows to pale-yellow lights, wet
  highlights) with darker segment grooves and bristles, rearing out of a mound
  of dark grave earth with broken tombstones (the mound is part of the sprite);
* a round lamprey mouth at the head with rings of small teeth around a dark
  throat glowing toxic green, two tiny milky blind eyes, green poison drool.

Animations (non-death actions end on idle frame 0):
  idle    12-frame cobra sway, peristaltic ripple, mouth flexing, a drool drop falling
  attack  "Mordida Pútrida": coils back (S-curve), mouth wide, strikes left ~50 px, snaps shut
          with a green poison spray, recoils
  burrow  "Enterrarse": dives into the mound (dirt spray), only a hump of back shows, rises again
  cast    "Escupir Bilis": rears high, the throat bulges, spits a bile glob that splashes into a
          toxic puddle near the hero
  hurt    white flash, recoil to the right, writhing
  death   thrashes, collapses onto the mound, rots into green-black ooze and dissolves (empty)

Output: ``assets/enemies/worm_sheet.png`` + ``.json`` (``events.attack.strikes``).
"""
from __future__ import annotations

import math
import sys
from dataclasses import dataclass, field, replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from pixel_kit import (Canvas, bayer, build_sheet, dissolve, flash, hash01, mix,  # noqa: E402
                       outline, ramp, save_sheet, smooth)

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "assets" / "enemies"
SHEET_ID = "worm"

CELL_W, CELL_H = 144, 108
CX, GROUND = 96, 100            # body centre (mound centre), ground row
ANCHOR = (CX, GROUND + 2)
MOUND_W, MOUND_H = 30.0, 13.0   # mound half-width and height
SEG = 6.2                       # segment length along the spine (px)

# ---------------------------------------------------------------- palette
OUTLINE = (20, 12, 26)
FLESH = [(34, 30, 52), (56, 56, 80), (84, 92, 108), (118, 128, 128), (156, 160, 140),
         (196, 194, 158), (230, 224, 186)]
BELLY = [(60, 54, 58), (104, 98, 84), (150, 140, 104), (196, 184, 128), (232, 220, 160)]
LIP = [(70, 36, 52), (124, 66, 80), (176, 108, 108), (214, 160, 146)]
TEETH = [(150, 140, 112), (214, 206, 174), (248, 244, 222)]
THROAT = (14, 8, 16)
TOX = [(36, 72, 24), (82, 152, 40), (160, 226, 70), (232, 255, 160)]
EARTH = [(24, 16, 22), (42, 28, 32), (62, 42, 40), (86, 60, 50), (114, 84, 64)]
STONE = [(36, 36, 50), (60, 60, 76), (90, 90, 104), (126, 124, 132), (164, 160, 160)]
MOSS = (58, 88, 44)
OOZE = [(10, 14, 12), (18, 30, 20), (30, 52, 28), (54, 88, 34), (96, 140, 50)]
BRISTLE = [(66, 60, 74), (112, 106, 112)]
EYE = [(150, 168, 172), (214, 226, 220)]
LIGHT = (-0.62, -0.78)          # upper-left light


@dataclass(frozen=True)
class Pose:
    dx: float = 0.0
    dy: float = 0.0
    # spine: base, two controls and head, relative to (CX, GROUND)
    base: tuple[float, float] = (3.0, -4.0)
    c1: tuple[float, float] = (17.0, -30.0)
    c2: tuple[float, float] = (10.0, -66.0)
    head: tuple[float, float] = (-13.0, -58.0)
    girth: float = 1.0
    phase: float = 0.0
    ripple: float = 1.0           # peristaltic wave strength
    writhe: float = 0.0           # lateral wave (hurt / death thrash)
    open: float = 0.3             # mouth 0 shut .. 1 wide
    eye: float = 1.0
    drool: float = 1.0
    bulge: float = 0.0            # throat bulge size
    bulge_t: float = 0.6          # where along the spine
    flash: float = 0.0
    rot: float = 0.0              # death: flesh rots into ooze
    ooze: float = 0.0             # ooze puddle spreading over the mound
    dissolve: float = 0.0
    spray: float = 0.0            # poison spray (attack)
    spray_fade: float = 0.0
    dirt: float = 0.0             # dirt clods thrown up (burrow); 0 = none
    dirt_seed: int = 0
    glob: float = 0.0             # bile glob flight (cast) 0..1
    puddle: float = 0.0           # toxic puddle size
    puddle_fade: float = 0.0
    motes: tuple = field(default_factory=tuple)


# ---------------------------------------------------------------- spine
def _cubic(p0, p1, p2, p3, t):
    u = 1 - t
    return (u ** 3 * p0[0] + 3 * u * u * t * p1[0] + 3 * u * t * t * p2[0] + t ** 3 * p3[0],
            u ** 3 * p0[1] + 3 * u * u * t * p1[1] + 3 * u * t * t * p2[1] + t ** 3 * p3[1])


class Spine:
    """Evenly spaced samples along the body axis with tangent, normal and arc length."""

    def __init__(self, p: Pose) -> None:
        ox, oy = CX + p.dx, GROUND + p.dy
        pts = [(ox + a, oy + b) for a, b in (p.base, p.c1, p.c2, p.head)]
        raw = [_cubic(*pts, i / 80) for i in range(81)]
        dense = [raw[0]]
        for (x0, y0), (x1, y1) in zip(raw, raw[1:]):
            n = max(1, int(math.hypot(x1 - x0, y1 - y0) / 0.6))
            for i in range(1, n + 1):
                dense.append((x0 + (x1 - x0) * i / n, y0 + (y1 - y0) * i / n))
        s, arc = 0.0, [0.0]
        for (x0, y0), (x1, y1) in zip(dense, dense[1:]):
            s += math.hypot(x1 - x0, y1 - y0)
            arc.append(s)
        self.length = max(1.0, s)
        self.samples = []                     # (x, y, tx, ty, t, s)
        n = len(dense)
        for i, (x, y) in enumerate(dense):
            a, b = dense[max(0, i - 3)], dense[min(n - 1, i + 3)]
            tx, ty = b[0] - a[0], b[1] - a[1]
            d = math.hypot(tx, ty) or 1.0
            tx, ty = tx / d, ty / d
            t = arc[i] / self.length
            # lateral writhe (base planted, grows towards the head)
            w = p.writhe * math.sin(t * 9.0 - 2 * p.phase) * t ** 1.2
            self.samples.append((x - ty * w, y + tx * w, tx, ty, t, arc[i]))
        self.p = p

    def radius(self, t: float) -> float:
        p = self.p
        if t < 0.3:
            r = 10.5 + 1.0 * math.sin(t / 0.3 * math.pi / 2)
        elif t < 0.72:
            r = 11.5 - 3.0 * smooth((t - 0.3) / 0.42)
        elif t < 0.9:
            r = 8.5 + 2.0 * smooth((t - 0.72) / 0.18)          # the head swells
        else:
            r = 10.5 - 1.0 * (t - 0.9) / 0.1
        r *= 1 + 0.055 * p.ripple * math.sin(t * 15.0 - 2 * p.phase)
        if p.bulge > 0:
            r += p.bulge * 5.5 * math.exp(-((t - p.bulge_t) / 0.075) ** 2)
        return r * p.girth

    def end(self):
        x, y, tx, ty, t, s = self.samples[-1]
        return x, y, tx, ty


# ---------------------------------------------------------------- body
def _rot(c, k: float, light: float):
    if k <= 0:
        return c
    o = OOZE[max(0, min(len(OOZE) - 1, int(round(light * 0.8 * (len(OOZE) - 1)))))]
    return mix(c, o, min(1.0, k))


def draw_body(cv: Canvas, sp: Spine) -> None:
    p = sp.p
    best: dict[tuple[int, int], tuple] = {}
    for (x, y, tx, ty, t, s) in sp.samples:
        r = sp.radius(t)
        for yy in range(int(y - r) - 1, int(y + r) + 2):
            if yy > GROUND or yy < 0 or yy >= CELL_H:
                continue
            for xx in range(int(x - r) - 1, int(x + r) + 2):
                ddx, ddy = xx + 0.5 - x, yy + 0.5 - y
                d = math.hypot(ddx, ddy) / r
                if d > 1:
                    continue
                key = (xx, yy)
                if key not in best or d < best[key][0]:
                    best[key] = (d, ddx / r, ddy / r, tx, ty, t, s)
    shift = 1.4 * math.sin(p.phase)
    for (xx, yy), (d, nx, ny, tx, ty, t, s) in best.items():
        ndl = nx * LIGHT[0] + ny * LIGHT[1]
        light = 0.5 + 0.5 * ndl - 0.2 * d * d - 0.22 * (1 - t) ** 2
        seg = ((s + shift) % SEG) / SEG
        if t < 0.88:                                       # segment rings (not on the head)
            if seg < 0.16:
                light -= 0.3
            elif seg < 0.26:
                light -= 0.1
            else:
                light += 0.07 * math.sin((seg - 0.26) / 0.74 * math.pi)
        side = (tx * ny - ty * nx)                         # signed: <0 = front / belly side
        belly = side < -0.42 and t < 0.86
        if belly:
            col = ramp(BELLY, max(0.0, min(1.0, light + 0.06)), xx, yy, 0.35)
        else:
            col = ramp(FLESH, max(0.0, min(1.0, light)), xx, yy)
        # wet highlight: little specular glints on the lit side of each segment
        if ndl > 0.55 and 0.4 < d < 0.82 and 0.38 < seg < 0.62 and t < 0.88 and bayer(xx, yy) < 0.6:
            col = FLESH[6] if not belly else BELLY[4]
        if p.rot > 0:
            col = _rot(col, p.rot, light)
        cv.put(xx, yy, col)


def draw_bristles(cv: Canvas, sp: Spine) -> None:
    """Short dark bristles poking out of the silhouette at each segment groove."""
    p = sp.p
    shift = 1.4 * math.sin(p.phase)
    k_seen = set()
    for (x, y, tx, ty, t, s) in sp.samples:
        k = int((s + shift) // SEG)
        if k in k_seen or t < 0.12 or t > 0.84:
            continue
        k_seen.add(k)
        r = sp.radius(t)
        for sgn in (-1, 1):
            nx, ny = -ty * sgn, tx * sgn
            # tilt the bristle backwards (towards the base)
            bx, by = nx * 0.85 - tx * 0.5, ny * 0.85 - ty * 0.5
            ln = 2 + (1 if hash01(k, sgn, 3) > 0.5 else 0)
            for j in range(ln):
                px = x + nx * (r + 1.3) + bx * j
                py = y + ny * (r + 1.3) + by * j
                if py >= GROUND - 1 or cv.get(int(px), int(py)) is not None:
                    continue
                c = BRISTLE[1] if j == ln - 1 else BRISTLE[0]
                cv.put(px, py, _rot(c, p.rot, 0.2), solid=False)


def draw_head(cv: Canvas, sp: Spine) -> tuple[float, float, float, float]:
    """Lamprey mouth on the end of the body, blind eyes, returns mouth (x, y, low-lip x, y)."""
    p = sp.p
    ex, ey, tx, ty = sp.end()
    r = sp.radius(1.0)
    nx, ny = -ty, tx
    if ny > 0:                                             # (nx, ny) = the "up" side of the head
        nx, ny = -nx, -ny
    o = max(0.0, min(1.2, p.open))
    mx, my = ex + tx * r * 0.3, ey + ty * r * 0.3
    a = r * (0.62 + 0.36 * o)                              # across the mouth
    b = a * (0.58 + 0.12 * o)                              # foreshortened depth
    for yy in range(int(my - a) - 2, int(my + a) + 3):
        for xx in range(int(mx - a) - 2, int(mx + a) + 3):
            px, py = xx + 0.5 - mx, yy + 0.5 - my
            pn, pt = px * nx + py * ny, px * tx + py * ty
            e = (pn / a) ** 2 + (pt / b) ** 2
            if e > 1 or cv.get(xx, yy) is None:
                continue
            ang = math.atan2(pt / b, pn / a)
            lip_in = 0.62 - 0.22 * (1 - min(1.0, o))       # shut: thick puckered lips
            if e > lip_in:                                  # fleshy lip ring, lit from the top
                light = 0.4 + 0.45 * (pn / a) + 0.25 * (1 - abs(e - (1 + lip_in) / 2) / 0.3)
                col = ramp(LIP, max(0.0, min(1.0, light)), xx, yy, 0.35)
                if e > 0.93:
                    col = LIP[0]
            elif e > lip_in - 0.26 and math.cos(ang * 12) > -0.05:   # outer ring of teeth
                tip = e < lip_in - 0.16
                col = TEETH[2] if (pn > 0 and not tip) else TEETH[1] if not tip else TEETH[0]
            elif e > lip_in - 0.26:
                col = LIP[0]                                # gums between the teeth
            else:                                           # throat glowing toxic green
                g = (1 - e / max(0.05, lip_in - 0.26)) * min(1.0, o * 1.3)
                col = mix(THROAT, TOX[1] if g < 0.6 else TOX[2], g * 0.95)
                if o > 0.5 and 0.1 < e < 0.2 and math.cos(ang * 8 + 0.5) > 0.5:
                    col = TEETH[0]                          # inner ring of teeth
            if p.rot > 0:
                col = _rot(col, p.rot, 0.3)
            cv.put(xx, yy, col)
    # tiny milky blind eyes behind the mouth, on the upper side
    if p.eye > 0.05 and p.rot < 0.7:
        for k, back in enumerate((0.6, 0.98)):
            qx = ex - tx * r * back + nx * r * (0.58 - 0.06 * k)
            qy = ey - ty * r * back + ny * r * (0.58 - 0.06 * k)
            cv.put(qx, qy, EYE[1] if p.eye > 0.6 else EYE[0])
            cv.put(qx + 1, qy, EYE[0])
    lx, ly = mx - nx * b * 0.4, my - ny * a * 0.95          # lower lip
    return mx, my, lx, ly


def draw_drool(cv: Canvas, p: Pose, lip: tuple[float, float], t: float) -> None:
    if p.drool <= 0.05 or p.rot > 0.5:
        return
    lx, ly = lip
    f = (p.phase / math.tau) % 1.0
    length = 2 + p.drool * (3 + 4 * f)                    # strand stretches, then lets go
    for j in range(int(length)):
        c = TOX[2] if j < length - 1 else TOX[3]
        cv.put(lx + 0.4 * math.sin(j * 0.7), ly + 1 + j, c, solid=False)
    if f > 0.55:                                           # the drop falls
        k = (f - 0.55) / 0.45
        dyy = ly + length + 2 + 30 * k * k
        if dyy < GROUND:
            cv.put(lx, dyy, TOX[3], solid=False)
            cv.put(lx, dyy - 1, TOX[2], solid=False, alpha=170)


# ---------------------------------------------------------------- mound + stones
def mound_h(x: float) -> float:
    u = (x - CX) / MOUND_W
    if abs(u) >= 1:
        return 0.0
    lump = 1.3 * (hash01(int(x) // 3, 1, 7) - 0.5) + 0.8 * math.sin(x * 0.7)
    return max(0.0, MOUND_H * (1 - u * u) ** 0.65 + lump * (1 - u * u))


def draw_mound(cv: Canvas, p: Pose, body: Canvas) -> None:
    for x in range(int(CX - MOUND_W) - 1, int(CX + MOUND_W) + 2):
        h = mound_h(x + 0.5)
        if h <= 0.4:
            continue
        top = GROUND + 1 - h
        slope = (mound_h(x + 1.5) - mound_h(x - 0.5)) / 2
        for y in range(int(top), GROUND + 2):
            depth = (y - top) / max(1.0, h)
            light = 0.48 + 0.22 * max(-1.0, min(1.0, slope)) + 0.18 * (1 - depth) - 0.25 * depth
            light += (hash01(x, y, 11) - 0.5) * 0.3
            col = ramp(EARTH, max(0.0, min(1.0, light)), x, y, 0.5)
            if hash01(x // 2, y // 2, 13) > 0.94:          # pebbles / bone chips
                col = STONE[3] if hash01(x, y, 2) > 0.5 else STONE[2]
            if y < top + 2.2 and body.get(x, y - 1) is not None:
                col = EARTH[0]                             # dark hole where the body enters
            if y < top + 1.2:
                col = EARTH[4] if slope > -0.2 and hash01(x, y, 4) > 0.3 else EARTH[3]
                if body.get(x, y - 1) is not None:
                    col = EARTH[1]
            if p.ooze > 0:
                ou = abs(x + 0.5 - CX + 6) / (MOUND_W * 1.1)
                if ou < p.ooze and depth < 0.55 + 0.3 * p.ooze:
                    col = mix(col, OOZE[1 if depth > 0.25 else 2], 0.85)
            cv.put(x, y, col)
    # loose clods on the mound
    for k, (lx, ly) in enumerate(((-17, -7), (-6, -12), (13, -10), (22, -5), (-24, -3))):
        cx, cy = CX + lx, GROUND + 1 - mound_h(CX + lx) + 0.5
        for yy in range(int(cy) - 2, int(cy) + 1):
            for xx in range(int(cx) - 1, int(cx) + 2 + (k % 2)):
                dd = math.hypot(xx + 0.5 - cx - 0.5, (yy + 0.5 - cy + 1) * 1.3)
                if dd > 1.8:
                    continue
                cv.put(xx, yy, EARTH[4] if yy < cy - 1 and xx <= cx else EARTH[2])


def draw_stone(cv: Canvas, bx: float, by: float, w: float, h: float, ang: float, seed: int,
               broken: bool = True) -> None:
    """A tilted, broken gravestone (arched top, crack, inscription lines, moss)."""
    ux, uy = math.sin(ang), -math.cos(ang)
    rx, ry = math.cos(ang), math.sin(ang)
    half = w / 2
    reach = int(h + w) + 2
    for y in range(int(by) - reach, int(by) + 3):
        for x in range(int(bx) - reach, int(bx) + reach):
            px, py = x + 0.5 - bx, y + 0.5 - by
            along, across = px * ux + py * uy, px * rx + py * ry
            if along < -1 or abs(across) > half or y > GROUND + 1:
                continue
            q = across / half
            top = h + 0.45 * w * math.sqrt(max(0.0, 1 - q * q))
            if broken:                                      # jagged break across the top
                top -= 4.5 * (0.5 + 0.5 * q) + 2.5 * hash01(int(across + 20), seed, 9)
            if along > top:
                continue
            light = 0.55 - 0.32 * q + 0.1 * (along / h)
            if across < -half + 1.4:
                light += 0.3                                # lit left edge
            if along > top - 1.3:
                light += 0.2                                # lit top / break
            light += (hash01(x, y, seed) - 0.5) * 0.22
            col = ramp(STONE, max(0.0, min(1.0, light)), x, y, 0.45)
            crack = abs(across - (0.35 * along - 2 + 1.2 * math.sin(along * 0.9 + seed))) < 0.55
            if crack and along > h * 0.25:
                col = STONE[0]
            for ly in (0.42, 0.6):                          # worn inscription
                if abs(along - h * ly) < 0.5 and abs(q) < 0.55 and hash01(int(across), seed, 3) > 0.25:
                    col = STONE[1]
            if along < 3.5 and hash01(x, y, seed + 4) > 0.45:
                col = mix(col, MOSS, 0.6)
            cv.put(x, y, col)


# ---------------------------------------------------------------- effects
def draw_spray(cv: Canvas, mouth, prog: float, fade: float) -> None:
    """Poison spray fanning out of the snapping mouth, towards the hero (left)."""
    if prog <= 0 or fade >= 1:
        return
    mx, my = mouth
    for j in range(26):
        sp = 0.5 + 0.8 * hash01(j, 1, 21)
        ang = math.pi + (hash01(j, 2, 21) - 0.5) * 1.3
        dist = prog * 30 * sp + 3
        x = mx + math.cos(ang) * dist
        y = my + math.sin(ang) * dist + prog * prog * 10 * hash01(j, 3, 21)
        if hash01(j, 4, 21) < fade:
            continue
        c = TOX[3] if j % 4 == 0 else TOX[2] if j % 3 else TOX[1]
        cv.put(x, y, c, solid=False)
        if j % 3 == 0:
            cv.put(x + 1, y, TOX[1], solid=False, alpha=200)
    # streaks along the bite
    for j in range(5):
        y = my - 4 + j * 2
        for i in range(int(14 * prog * (1 - fade))):
            cv.put(mx - 4 - i - j % 2 * 3, y + i * 0.15, TOX[2] if i < 4 else TOX[1], solid=False,
                   alpha=int(230 * (1 - i / 20)))


def draw_dirt(cv: Canvas, prog: float, seed: int) -> None:
    """Clods of grave earth thrown up from the mound (parabolas), falling back."""
    if prog <= 0:
        return
    for j in range(16):
        vx = (hash01(j, seed, 31) - 0.55) * 46
        vy = 30 + 34 * hash01(j, seed, 32)
        tt = prog * (0.75 + 0.45 * hash01(j, seed, 33))
        x = CX - 4 + vx * tt
        y = GROUND - 12 - vy * tt + 62 * tt * tt
        if y > GROUND or tt > 1.2:
            continue
        big = j % 3 == 0
        cv.put(x, y, EARTH[4])
        cv.put(x + 1, y, EARTH[2])
        if big:
            cv.put(x, y + 1, EARTH[2])
            cv.put(x + 1, y + 1, EARTH[1])
    for j in range(12):                                       # dust specks
        tt = prog * 1.1
        x = CX - 14 + 28 * hash01(j, seed, 34) + (hash01(j, seed, 35) - 0.5) * 20 * tt
        y = GROUND - 12 - 18 * tt * hash01(j, seed, 36)
        if tt < 1:
            cv.put(x, y, EARTH[3], solid=False, alpha=int(200 * (1 - tt)))


GLOB_FROM = (CX - 30, GROUND - 62)
GLOB_TO = (18, GROUND - 1)


def draw_glob(cv: Canvas, k: float) -> None:
    if k <= 0 or k >= 1:
        return
    (x0, y0), (x1, y1) = GLOB_FROM, GLOB_TO
    x = x0 + (x1 - x0) * k
    y = y0 + (y1 - y0) * k - 34 * math.sin(k * math.pi)
    for j in range(1, 5):                                      # trail
        kk = max(0.0, k - j * 0.045)
        tx_ = x0 + (x1 - x0) * kk
        ty_ = y0 + (y1 - y0) * kk - 34 * math.sin(kk * math.pi)
        cv.put(tx_, ty_, TOX[2 if j < 3 else 1], solid=False, alpha=230 - 40 * j)
    r = 4.4
    for yy in range(int(y - r) - 1, int(y + r) + 2):
        for xx in range(int(x - r) - 1, int(x + r) + 2):
            d = math.hypot(xx + 0.5 - x, yy + 0.5 - y) / r
            if d > 1:
                continue
            ly = ((xx + 0.5 - x) * LIGHT[0] + (yy + 0.5 - y) * LIGHT[1]) / r
            col = ramp(TOX, 0.5 + 0.45 * ly - 0.2 * d * d, xx, yy, 0.4)
            cv.put(xx, yy, col)
    cv.put(x - 1, y - 2, TOX[3])


def draw_puddle(cv: Canvas, size: float, fade: float, t: float) -> None:
    if size <= 0 or fade >= 1:
        return
    px, py = GLOB_TO[0], GROUND
    rx, ry = 18 * size, 3.8 * size
    vis = 1 - fade
    for yy in range(int(py - ry) - 1, int(py + ry) + 2):
        for xx in range(int(px - rx) - 2, int(px + rx) + 3):
            wob = 1 + 0.12 * math.sin(xx * 0.9 + yy)
            d = math.hypot((xx + 0.5 - px) / max(0.5, rx * wob), (yy + 0.5 - py) / max(0.5, ry))
            if d > 1 or bayer(xx, yy) > vis * 1.6 - 0.2:
                continue
            col = TOX[0] if d > 0.8 else TOX[1] if d > 0.35 or yy > py else TOX[2]
            cv.put(xx, yy, col, solid=False, alpha=int(255 * min(1.0, vis + 0.3)))
    if vis > 0.3:
        for j in range(3):                                        # bubbles
            bx = px - rx * 0.5 + j * rx * 0.45
            if (int(t * 12) + j) % 3 == 0:
                cv.put(bx, py - 1, TOX[3], solid=False)
    if size < 0.95 and fade <= 0:                                 # splash droplets
        for j in range(10):
            a = math.pi * (0.1 + 0.8 * hash01(j, 1, 41))
            dist = size * 16 * (0.5 + hash01(j, 2, 41))
            x = px + math.cos(a) * dist
            y = py - math.sin(a) * dist * 0.9 + size * size * 8
            if y < GROUND:
                cv.put(x, y, TOX[2 + j % 2], solid=False)


# ---------------------------------------------------------------- render
def render(p: Pose, t: float = 0.0) -> Canvas:
    cv = Canvas(CELL_W, CELL_H)
    sp = Spine(p)
    draw_puddle(cv, p.puddle, p.puddle_fade, t)
    draw_stone(cv, CX + 22, GROUND - 3, 13, 20, 0.24, 5)              # behind the worm
    body = Canvas(CELL_W, CELL_H)
    draw_body(body, sp)
    mouth = draw_head(body, sp)
    flash(body, p.flash)                                   # only the worm flashes, not the mound
    cv.blit(body, rim=OUTLINE)
    mound = Canvas(CELL_W, CELL_H)
    draw_mound(mound, p, body)
    draw_stone(mound, CX - 23, GROUND + 1, 8, 7, -0.42, 9)             # broken chunk in front
    cv.blit(mound, rim=OUTLINE)
    draw_glob(cv, p.glob)
    outline(cv, OUTLINE)
    draw_bristles(cv, sp)
    o = max(0.0, p.open) * (1 - p.rot)
    if o > 0.05:
        cv.glow(mouth[0], mouth[1], 5 + 6 * o, TOX[1], 0.25 + 0.3 * o)
    draw_drool(cv, p, (mouth[2], mouth[3]), t)
    draw_spray(cv, (mouth[0], mouth[1]), p.spray, p.spray_fade)
    draw_dirt(cv, p.dirt, p.dirt_seed)
    if p.glob > 0 and p.glob < 1:
        cv.glow(*_glob_pos(p.glob), 6, TOX[2], 0.35)
    for (mx, my, lv) in p.motes:
        cv.put(mx, my, TOX[lv] if lv < 4 else OOZE[3], solid=False)
    if p.dissolve > 0:
        dissolve(cv, p.dissolve, GROUND - 30, CELL_H + 2, TOX[3], TOX[1], upward=False, seed=7)
    return cv


def _glob_pos(k: float):
    (x0, y0), (x1, y1) = GLOB_FROM, GLOB_TO
    return x0 + (x1 - x0) * k, y0 + (y1 - y0) * k - 34 * math.sin(k * math.pi)


# ---------------------------------------------------------------- animations
IDLE_FRAMES = 12


def idle_pose(i: int, n: int = IDLE_FRAMES) -> Pose:
    a = math.tau * (i % n) / n
    s = math.sin(a)
    return Pose(
        head=(round(-13 + 4 * s), round(-58 + 1.5 * math.sin(2 * a))),
        c2=(10 - 3 * math.sin(a - 0.7), -66 + 1.0 * math.sin(2 * a + 0.5)),
        c1=(17 + 2.5 * math.sin(a - 1.5), -30),
        phase=a, open=0.3 + 0.16 * math.sin(a + 1.0), eye=0.6 if i % n == 7 else 1.0,
    )


def idle_frames():
    return [(idle_pose(i), 110) for i in range(IDLE_FRAMES)]


def _toward(a: Pose, b: Pose, k: float) -> Pose:
    """Interpolated spine between two poses (other fields from ``b``)."""
    def lp(u, v):
        return (u[0] + (v[0] - u[0]) * k, u[1] + (v[1] - u[1]) * k)
    return replace(b, base=lp(a.base, b.base), c1=lp(a.c1, b.c1), c2=lp(a.c2, b.c2),
                   head=lp(a.head, b.head), open=a.open + (b.open - a.open) * k)


def attack_frames():
    """Mordida Pútrida: coil back into an S, mouth wide, strike left, snap shut, recoil."""
    b = idle_pose(0)
    coil = replace(b, c1=(-10, -24), c2=(34, -56), head=(12, -66), open=0.8, phase=0.6, girth=1.03)
    coil2 = replace(b, c1=(-14, -22), c2=(40, -58), head=(16, -68), open=1.1, phase=1.1, girth=1.05)
    strike = replace(b, c1=(6, -40), c2=(-24, -48), head=(-62, -38), open=0.15, phase=1.6,
                     girth=0.94, spray=0.45, ripple=0.4)
    hold = replace(strike, head=(-60, -37), open=0.05, phase=2.0, spray=0.9, spray_fade=0.3)
    return [
        (replace(_toward(b, coil, 0.55), phase=0.3), 100),
        (coil, 120),
        (coil2, 100),
        (strike, 55),
        (hold, 65),
        (replace(_toward(hold, b, 0.4), phase=2.6, spray=1.0, spray_fade=0.7, open=0.2), 90),
        (replace(_toward(hold, b, 0.72), phase=3.4, open=0.25), 90),
        (replace(_toward(hold, b, 0.92), phase=4.4), 95),
        (b, 100),
    ]


def burrow_frames():
    """Enterrarse: dive into the mound (dirt spray), a hump of back, rise again."""
    b = idle_pose(0)
    dive1 = replace(b, c1=(14, -34), c2=(-4, -54), head=(-18, -30), open=0.05, phase=0.5, dirt=0.0)
    dive2 = replace(b, c1=(10, -30), c2=(-6, -26), head=(-10, -4), open=0.0, phase=1.0, dirt=0.25,
                    drool=0)
    hidden = replace(b, base=(10, -2), c1=(8, -20), c2=(-2, -20), head=(-4, 8), open=0.0, phase=1.6,
                     dirt=0.55, drool=0)
    hidden2 = replace(hidden, c1=(9, -17), c2=(-3, -17), phase=2.2, dirt=0.85)
    hidden3 = replace(hidden, c1=(8, -15), c2=(-2, -15), phase=2.8, dirt=0.0)
    rise1 = replace(b, c1=(6, -30), c2=(2, -40), head=(-2, -40), open=0.1, phase=3.4, dirt=0.3,
                    dirt_seed=1, drool=0)
    rise2 = replace(b, c1=(16, -32), c2=(12, -70), head=(-8, -66), open=0.5, phase=4.2, dirt=0.65,
                    dirt_seed=1)
    return [
        (dive1, 80), (dive2, 70), (hidden, 90), (hidden2, 120), (hidden3, 120),
        (rise1, 80), (rise2, 90), (replace(_toward(rise2, b, 0.6), phase=5.0), 90), (b, 100),
    ]


def cast_frames():
    """Escupir Bilis: rear up high, the throat bulges, spit a bile glob that splashes."""
    b = idle_pose(0)
    rear = replace(b, c1=(14, -36), c2=(12, -76), head=(-6, -72), open=0.2, phase=0.5)
    out = [
        (replace(_toward(b, rear, 0.6), bulge=0.5, bulge_t=0.25, phase=0.3), 100),
        (replace(rear, bulge=0.8, bulge_t=0.45, phase=0.8), 100),
        (replace(rear, bulge=1.0, bulge_t=0.68, phase=1.2, open=0.5), 90),
        (replace(rear, head=(-8, -73), bulge=1.0, bulge_t=0.88, phase=1.6, open=0.9), 80),
        (replace(b, c1=(10, -32), c2=(4, -66), head=(-20, -62), open=1.1, phase=2.0, glob=0.12,
                 girth=0.97), 60),
        (replace(b, c1=(12, -32), c2=(6, -66), head=(-18, -60), open=0.8, phase=2.4, glob=0.52), 60),
        (replace(b, head=(-16, -59), open=0.6, phase=2.8, glob=0.96, puddle=0.25), 60),
        (replace(b, head=(-15, -59), open=0.45, phase=3.2, puddle=0.6), 65),
        (replace(b, head=(-14, -58), phase=3.8, puddle=1.0), 75),
        (replace(b, phase=4.8, puddle=1.0, puddle_fade=0.6), 80),
        (b, 100),
    ]
    return out


def hurt_frames():
    b = idle_pose(0)
    return [
        (replace(b, c1=(20, -30), c2=(22, -58), head=(4, -54), girth=1.06, open=0.9, flash=0.82,
                 writhe=2.0, phase=1.0, eye=0.3), 60),
        (replace(b, c1=(21, -30), c2=(24, -58), head=(6, -55), girth=1.04, open=0.8, flash=0.5, writhe=2.5,
                 phase=1.8), 70),
        (replace(b, c2=(16, -62), head=(-4, -56), open=0.6, flash=0.18, writhe=1.8, phase=2.6), 80),
        (replace(b, c2=(13, -64), head=(-8, -57), open=0.45, writhe=1.0, phase=3.4), 90),
        (replace(b, c2=(11, -65), head=(-11, -58), writhe=0.4, phase=4.3), 95),
        (b, 100),
    ]


def death_frames():
    b = idle_pose(0)
    out = [
        (replace(b, c2=(18, -60), head=(0, -55), open=1.0, flash=0.85, writhe=2.5, phase=1.0), 70),
        (replace(b, c1=(4, -34), c2=(30, -66), head=(14, -74), open=1.2, flash=0.3, writhe=3.5,
                 phase=1.9), 80),
        (replace(b, c1=(24, -30), c2=(-10, -64), head=(-30, -60), open=1.0, writhe=4.0, phase=2.8), 80),
        (replace(b, c1=(6, -30), c2=(24, -54), head=(6, -50), open=0.8, writhe=3.5, phase=3.7), 80),
    ]
    steps = 10
    last = out[-1][0]
    for k in range(steps):
        u = (k + 1) / steps
        fall = smooth(min(1.0, u * 2.2))
        lying = replace(b, c1=(6, -18), c2=(-14, -14), head=(-30, -6), girth=0.9)
        pose = _toward(last, lying, fall)
        motes = tuple((CX - 34 + hash01(k, j, 9) * 60, GROUND - 6 - u * 30 - hash01(j, k, 4) * 22,
                       2 + (j % 3 == 0) if j % 2 else 4) for j in range(4 + k))
        out.append((replace(pose, open=0.8 * (1 - fall), writhe=3.0 * (1 - fall), phase=4.4 + 0.5 * k,
                            rot=smooth(min(1.0, u * 1.6)), ooze=smooth(min(1.0, u * 1.4)),
                            girth=0.9 - 0.12 * max(0.0, u - 0.5), eye=1 - u, drool=0,
                            dissolve=0.0 if u < 0.3 else min(1.0, (u - 0.3) / 0.7) * 0.97,
                            motes=motes), 85))
    out.append((replace(b, dissolve=1.0), 120))
    return out


ANIMATIONS = {
    "idle": (idle_frames, True),
    "attack": (attack_frames, False),
    "burrow": (burrow_frames, False),
    "cast": (cast_frames, False),
    "hurt": (hurt_frames, False),
    "death": (death_frames, False),
}

# Frames where a hit lands (the bite snaps shut on frame 3).
EVENTS = {"attack": {"strikes": [3]}}
# Move id -> animation.
MOVES = {"bite": "attack", "burrow": "burrow", "bile": "cast", "vengeance": "cast"}


def build():
    return build_sheet(ANIMATIONS, render, (CELL_W, CELL_H), ANCHOR, f"{SHEET_ID}_sheet.png",
                       {"events": EVENTS, "moves": MOVES})


def main() -> None:
    sheet, meta = build()
    save_sheet(OUT_DIR, SHEET_ID, sheet, meta)
    print(f"wrote assets/enemies/{SHEET_ID}_sheet.png ({len(sheet[0])}x{len(sheet)}) and .json")


if __name__ == "__main__":
    main()
