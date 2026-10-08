"""Draw and animate the enemy "Babosa Ácida" (an acid slime). Stdlib only:

    python scripts/generate_enemy_slime.py

Same method as the Espectro (``docs/code-drawn-sprites.md``): one renderer, every
frame a ``Pose``. The slime is ONE mass scanned row by row (a width profile by
height and a wobbling centre line) with everything painted inside it:

* acid-green translucent gel: lit rim on the upper left, a darker core, a glossy
  specular highlight and a sagging base that spreads on the floor;
* things it has dissolved, seen through the jelly: a small skull, a bone and a
  rusty coin (darker, desaturated by the gel);
* bubbles rising inside, two beady eyes with a bright pinpoint, a wide drooling
  mouth and acid drips on the floor around it.

Its identity is corrosion (Frágil / Vulnerable), so the accent is a sickly
yellow-green acid glow.

Animations (non-death actions end on idle frame 0):
  idle    12-frame breathing wobble: squash/stretch, ripples, rising bubbles, one blink
  attack  "Aplastar": squashes, leaps left in an arc, lands with a big splat, slides home
  spit    "Escupitajo Ácido": inflates, spits an acid glob that arcs left and splashes
  cast    "Corroer": the gel boils and glows, acid fumes rise, a puddle ring spreads
  hurt    white flash, strong jiggle, knocked right, droplets fly off
  death   collapses into a puddle that evaporates into green fumes -> empty

Output: ``assets/enemies/slime_sheet.png`` + ``.json`` (``events.<anim>.strikes``).
"""
from __future__ import annotations

import math
import sys
from dataclasses import dataclass, replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from pixel_kit import (Canvas, bayer, build_sheet, flash, hash01, mix, outline,  # noqa: E402
                       ramp, save_sheet, smooth)

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "assets" / "enemies"
SHEET_ID = "slime"

CELL_W, CELL_H = 160, 108
CX, GROUND = 112, 100            # body centre line, last floor row of the body
ANCHOR = (CX, GROUND + 2)
BODY_H = 48.0                    # dome height (native px)
BODY_W = 26.0                    # half-width at the widest point (before the foot flare)
FOOT_V = 0.24                    # where the dome meets the sagging base
TAU = math.tau

# ---------------------------------------------------------------- palette
OUTLINE = (8, 24, 20)
GEL = [(12, 34, 34), (16, 56, 44), (26, 86, 50), (44, 120, 52), (82, 160, 56), (138, 198, 72),
       (196, 232, 112)]
SHINE = [(220, 246, 160), (248, 255, 222)]
ACID = [(118, 150, 26), (186, 214, 44), (232, 248, 110), (250, 255, 206)]
EYE_DARK = (10, 22, 16)
MOUTH = [(10, 20, 16), (22, 44, 28)]
BONE = [(58, 74, 58), (96, 112, 84), (138, 150, 112), (172, 184, 140)]
RUST = [(78, 58, 26), (124, 92, 36), (164, 132, 52)]
FUME = [(70, 120, 50), (120, 170, 60), (186, 222, 96)]
WHITE = (255, 255, 255)

# skull (7x7): L light, M mid, D dark (holes/shadow)
SKULL = ("..LLLL...",
         ".LLLLLLM.",
         "LLLLLLLMM",
         "LDDDLDDDM",
         "LDDDLDDDM",
         "MLLLDLLMM",
         ".MMLLLMM.",
         "..LDLDLD.",
         "..M.M.M..")
COIN = (".LLM.",
        "LLMMD",
        "LMDMD",
        "MMMDD",
        ".DDD.")
# floor drips around the base: (x offset from CX, width)
DRIPS = [(-38, 3), (-43, 1), (36, 2), (41, 1), (-31, 1)]


@dataclass(frozen=True)
class Pose:
    dx: float = 0.0
    dy: float = 0.0               # vertical lift (negative = up, airborne)
    lean: float = 0.0             # top offset (negative = towards the hero)
    sx: float = 1.0               # squash/stretch about the floor
    sy: float = 1.0
    foot: float = 1.0             # 1 = base spread on the floor, 0 = rounded (airborne)
    phase: float = 0.0
    wobble: float = 1.0           # centre-line wobble amplitude
    ripple: float = 1.0           # surface ripple amplitude
    eye: float = 1.0              # eye pinpoint glow
    blink: float = 0.0
    mouth: float = 0.15           # 0 closed .. 1 wide open
    boil: float = 0.0             # bubbles (cast)
    glow: float = 0.45            # inner acid glow
    flash: float = 0.0
    dissolve: float = 0.0         # death: evaporation 0..1
    drips: float = 1.0            # floor drips visible
    splat: float = 0.0            # slam splash progress
    splat_x: float = 0.0
    shadow: float = 0.0           # baked shadow while airborne
    glob: float = 0.0             # spit projectile progress (0 = none)
    gsplash: float = 0.0          # spit splash progress
    fumes: float = 0.0            # rising acid fumes
    ring: float = 0.0             # puddle ring (cast)
    shed: float = 0.0             # hurt droplets


class Body:
    def __init__(self, p: Pose) -> None:
        self.p = p
        self.base = GROUND + 1 + p.dy
        self.H = BODY_H * p.sy

    def h_of(self, y: float) -> float:
        return (self.base - y) / self.p.sy

    def y_of(self, h: float) -> float:
        return self.base - h * self.p.sy

    def center(self, v: float) -> float:
        p = self.p
        v = max(0.0, v)
        wave = p.wobble * 1.3 * math.sin(p.phase + 2.6 * v) * v ** 1.4
        return CX + p.dx + p.lean * v ** 1.3 + wave

    def half_width(self, v: float) -> float:
        p = self.p
        if v < 0 or v > 1:
            return 0.0
        if v >= FOOT_V:
            k = (v - FOOT_V) / (1 - FOOT_V)
            f = max(0.0, 1 - k ** 1.85) ** 0.5
        else:
            k = (FOOT_V - v) / FOOT_V
            flare = 1 + 0.24 * k ** 1.6
            rounded = max(0.0, 1 - ((FOOT_V - v) / (FOOT_V + 0.07)) ** 2) ** 0.5
            f = rounded + (flare - rounded) * p.foot
        hw = BODY_W * f
        if v > 0.08:
            hw += p.ripple * 0.75 * math.sin(2 * p.phase + 11 * v)
        return max(0.0, hw * p.sx)

    def to_cell(self, lx: float, v: float) -> tuple[float, float]:
        return self.center(v) + lx * self.p.sx, self.y_of(v * BODY_H)


# ---------------------------------------------------------------- body
def draw_body(cv: Canvas, b: Body) -> list[list[bool]]:
    """The gel mass. Returns the mask of body pixels (bubbles and debris stay inside it)."""
    p = b.p
    mask = [[False] * CELL_W for _ in range(CELL_H)]
    for y in range(CELL_H):
        h = b.h_of(y + 0.5)
        if h < 0 or h > BODY_H:
            continue
        v = h / BODY_H
        hw = b.half_width(v)
        if hw < 0.5:
            continue
        c = b.center(v)
        for x in range(max(0, int(c - hw) - 1), min(CELL_W, int(c + hw) + 2)):
            dxp = x + 0.5 - c
            if abs(dxp) > hw:
                continue
            u = dxp / hw
            light = 0.50 - 0.30 * u + 0.24 * (v - 0.4)
            dc = math.hypot((u + 0.05) / 0.72, (v - 0.36) / 0.42)
            light -= 0.34 * max(0.0, 1 - dc)                       # darker core
            light += 0.05 * math.sin(14 * v - 3 * u + p.phase)      # inner ripple bands
            if u < -0.78 and v > 0.18:
                light += 0.22                                       # lit rim, upper left
            elif u > 0.84 and v > 0.12:
                light += 0.10                                       # light through the gel
            if v > 0.86 and u < 0.2:
                light += 0.10
            if v < 0.07 * p.foot + 0.01:
                light -= 0.16                                       # contact shadow
            light += 0.25 * p.glow * max(0.0, 1 - dc) * 0.8         # acid glow from inside
            col = ramp(GEL, max(0.0, min(1.0, light)), x, y)
            if p.glow > 0.7 and dc < 0.6:
                col = mix(col, ACID[1], (p.glow - 0.7) * 0.6 * (1 - dc / 0.6))
            cv.put(x, y, col)
            mask[y][x] = True
    # glossy lip where the sagging base meets the floor
    if p.foot > 0.5 and p.dy > -0.5:
        y = int(b.base) - 1
        hw = b.half_width(0.5 / BODY_H)
        c = b.center(0.0)
        for x in (int(c - hw), int(c - hw) + 1, int(c + hw) - 1):
            if 0 <= y < CELL_H and 0 <= x < CELL_W and mask[y][x]:
                cv.put(x, y, GEL[4] if x < c else GEL[3])
    return mask


def _template(cv: Canvas, mask, x0: int, y0: int, rows, colors, tint: float) -> None:
    keys = {"D": 0, "M": 1, "L": 2}
    drawn = set()
    for j, row in enumerate(rows):
        for i, ch in enumerate(row):
            if ch == ".":
                continue
            x, y = x0 + i, y0 + j
            if not (0 <= x < CELL_W and 0 <= y < CELL_H):
                continue
            col = colors[keys[ch]]
            under = cv.get(x, y)
            if under is not None and mask[y][x]:
                col = mix(col, under[:3], tint)
            cv.put(x, y, col)
            drawn.add((x, y))
    _shade_around(cv, mask, drawn)


def _shade_around(cv: Canvas, mask, drawn) -> None:
    """Darker gel right around a submerged object, so it reads through the jelly."""
    for (x, y) in drawn:
        for ox, oy in ((1, 0), (0, 1), (1, 1), (-1, 0), (0, -1)):
            nx, ny = x + ox, y + oy
            if (nx, ny) in drawn or not (0 <= nx < CELL_W and 0 <= ny < CELL_H) or not mask[ny][nx]:
                continue
            c = cv.get(nx, ny)
            if c is not None:
                cv.px[ny][nx] = (*mix(c[:3], GEL[1], 0.45 if oy >= 0 else 0.2), c[3])


def draw_debris(cv: Canvas, b: Body, mask) -> None:
    """A skull, a bone and a rusty coin floating inside the jelly."""
    p = b.p
    tint = 0.36
    # bone (diagonal, knobbed ends)
    bob = round(0.8 * math.sin(p.phase + 1.3))
    bx, by = b.to_cell(-12, 0.15)
    by += bob
    pts = [(bx - 6 + i, by + 3 - i * 0.5) for i in range(12)]
    drawn = set()
    for i, (x, y) in enumerate(pts):
        for yy in (0, 1):
            xi, yi = int(x), int(y) + yy
            if 0 <= xi < CELL_W and 0 <= yi < CELL_H:
                col = BONE[3] if yy == 0 else BONE[1]
                under = cv.get(xi, yi)
                cv.put(xi, yi, mix(col, under[:3], tint) if under and mask[yi][xi] else col)
                drawn.add((xi, yi))
    for (kx, ky) in (pts[0], pts[-1]):
        for ox, oy, k in ((-1, -1, 3), (0, -1, 3), (-1, 0, 2), (-1, 1, 1), (1, 2, 1), (0, 2, 0)):
            xi, yi = int(kx) + ox, int(ky) + oy
            if 0 <= xi < CELL_W and 0 <= yi < CELL_H:
                under = cv.get(xi, yi)
                cv.put(xi, yi, mix(BONE[k], under[:3], tint) if under and mask[yi][xi] else BONE[k])
                drawn.add((xi, yi))
    _shade_around(cv, mask, drawn)
    # skull, lower right, slightly tilted by the wobble
    sx_, sy_ = b.to_cell(8, 0.21)
    sy_ += round(0.8 * math.sin(p.phase + 0.2))
    _template(cv, mask, int(sx_) - 4, int(sy_) - 6, SKULL, (BONE[0], BONE[1], BONE[3]), tint)
    # rusty coin, higher up on the right
    cx_, cy_ = b.to_cell(15, 0.50)
    cy_ += round(0.9 * math.sin(p.phase + 2.6))
    _template(cv, mask, int(cx_) - 2, int(cy_) - 2, COIN, RUST, tint)


def draw_bubbles(cv: Canvas, b: Body, mask) -> None:
    p = b.p
    n = 6 + int(round(10 * p.boil))
    for k in range(n):
        speed = 1 + (k % 2)                               # integer multiples: loop closes
        frac = ((p.phase / TAU) * speed + hash01(k, 3, 11)) % 1.0
        v = 0.08 + 0.80 * frac
        lx = (hash01(k, 1, 11) - 0.5) * 1.5 * BODY_W * (1 - 0.6 * v)
        lx += 1.2 * math.sin(p.phase * speed + k)
        x, y = b.to_cell(lx, v)
        big = (k % 3 == 0) or p.boil > 0.6 and k % 2 == 0
        xi, yi = int(x), int(y)
        if not (0 <= xi < CELL_W - 1 and 0 <= yi < CELL_H - 1) or not mask[yi][xi]:
            continue
        if big:
            for ox, oy, col in ((0, 0, SHINE[0]), (1, 0, GEL[5]), (0, 1, GEL[5]), (1, 1, GEL[3])):
                if mask[yi + oy][xi + ox]:
                    cv.put(xi + ox, yi + oy, col)
            if p.boil > 0.5 and mask[yi - 1][xi]:
                cv.put(xi, yi - 1, GEL[4])
        else:
            cv.put(xi, yi, GEL[6] if frac > 0.3 else GEL[5])


def draw_face(cv: Canvas, b: Body) -> list[tuple[float, float]]:
    """Two beady eyes and a wide drooling mouth, turned a little towards the hero."""
    p = b.p
    eyes = []
    for lx in (-14.0, -1.0):
        ex, ey = b.to_cell(lx, 0.64)
        ex, ey = int(round(ex)), int(round(ey))
        if p.blink > 0.5:
            for ox in (-1, 0, 1):
                cv.put(ex + ox, ey, EYE_DARK)
            cv.put(ex - 1, ey - 1, GEL[2])
            cv.put(ex + 1, ey - 1, GEL[2])
        else:
            for oy in (-2, -1, 0, 1, 2):
                for ox in (-1, 0, 1, 2):
                    if oy in (-2, 2) and ox in (-1, 2):
                        continue
                    cv.put(ex + ox, ey + oy, EYE_DARK)
            cv.put(ex - 2, ey, GEL[1])
            cv.put(ex + 3, ey, GEL[2])
            cv.put(ex, ey + 3, GEL[5])                    # wet lower lid
            cv.put(ex + 1, ey + 3, GEL[5])
            hot = ACID[3] if p.eye > 0.9 else ACID[2] if p.eye > 0.5 else ACID[0]
            cv.put(ex - 1, ey - 1, hot)
            cv.put(ex, ey - 1, ACID[2] if p.eye > 0.5 else ACID[0])
            cv.put(ex + 1, ey + 1, MOUTH[1])
            if p.eye > 1.2:
                cv.put(ex - 1, ey, ACID[2])
        eyes.append((ex - 0.5, ey - 0.5))
    # mouth: a wide sagging slit that opens into a dark maw
    mx0, my = b.to_cell(-19, 0.42)
    mx1, _ = b.to_cell(5, 0.42)
    x0, x1 = int(round(mx0)), int(round(mx1))
    span = max(1, x1 - x0)
    drool_x = []
    for x in range(x0, x1 + 1):
        t = (x - x0) / span
        sag = 1.6 * math.sin(math.pi * t)                 # grin sags in the middle
        top = int(round(my + sag - 0.3))
        depth = p.mouth * 6.5 * math.sin(math.pi * t) ** 0.8
        bottom = int(round(my + sag + depth))
        cv.put(x, top - 1, GEL[2])                        # upper lip shadow
        for y in range(top, bottom + 1):
            cv.put(x, y, MOUTH[0] if y < bottom or depth < 1 else MOUTH[1])
        if depth > 2.5 and 0.2 < t < 0.8:
            cv.put(x, top + 1, ACID[0] if (x % 3) else MOUTH[1])   # acid glinting in the maw
        cv.put(x, bottom + 1, GEL[5] if t < 0.6 else GEL[4])       # wet lower lip
        if t in (0,) or x in (x0 + 3, x0 + span // 2 + 2):
            drool_x.append((x, bottom + 1))
    # drool strands hanging from the lower lip (length breathes with the phase)
    for k, (x, y) in enumerate(drool_x):
        ln = 3 + k + round(1.4 * math.sin(p.phase + k * 1.7)) + int(3 * p.mouth)
        for s in range(1, ln + 1):
            cv.put(x, y + s, ACID[1] if s < ln else ACID[2])
        cv.put(x, y + ln + 1, ACID[1])
        cv.put(x + 1, y + ln, ACID[0])
    return eyes


def draw_shine(cv: Canvas, b: Body, mask) -> None:
    """Glossy specular highlight, upper left, plus a thin rim streak."""
    hx, hy = b.to_cell(-12, 0.84)
    for yy in range(int(hy) - 3, int(hy) + 3):
        for xx in range(int(hx) - 5, int(hx) + 5):
            if not (0 <= xx < CELL_W and 0 <= yy < CELL_H) or not mask[yy][xx]:
                continue
            dx, dy = (xx + 0.5 - hx) / 4.2, (yy + 0.5 - hy) / 2.0
            d = dx * dx + dy * dy - 0.4 * dx * dy
            if d < 0.35:
                cv.put(xx, yy, SHINE[1])
            elif d < 1.0:
                cv.put(xx, yy, SHINE[0] if bayer(xx, yy) < 0.75 else GEL[6])
    for x, y in ((hx + 6, hy + 2), (hx - 7, hy + 6), (hx - 8, hy + 8)):
        xi, yi = int(x), int(y)
        if 0 <= xi < CELL_W and 0 <= yi < CELL_H and mask[yi][xi]:
            cv.put(xi, yi, SHINE[0])


def draw_drips(cv: Canvas, p: Pose) -> None:
    if p.drips <= 0.05:
        return
    for k, (ox, w) in enumerate(DRIPS):
        if hash01(k, 7, 2) > p.drips + 0.1:
            continue
        x0 = CX + ox
        for i in range(w):
            cv.put(x0 + i, GROUND, GEL[3] if i else GEL[4])
        if w >= 2:
            cv.put(x0 + 1, GROUND - 1, GEL[5])
        cv.put(x0, GROUND, SHINE[0] if w > 2 else GEL[4])


# ---------------------------------------------------------------- effects
def _droplet(cv: Canvas, x: float, y: float, big: bool, hot: bool = False) -> None:
    c1 = ACID[2] if hot else GEL[5]
    c0 = ACID[1] if hot else GEL[3]
    cv.put(x, y, c1)
    if big:
        cv.put(x + 1, y, c0)
        cv.put(x, y + 1, c0)
        cv.put(x + 1, y + 1, GEL[2])


def draw_splat(cv: Canvas, prog: float, x0: float) -> None:
    """Big splash droplets flying out from the landing point, and floor splash sheets."""
    if prog <= 0:
        return
    for k in range(20):
        side = -1 if k % 2 == 0 else 1
        ang = (0.25 + 0.7 * hash01(k, 1, 5)) * math.pi / 2
        speed = 26 + 26 * hash01(k, 2, 5)
        dist = speed * prog
        x = x0 + side * (32 + math.cos(ang) * dist * 1.1)
        y = GROUND - 3 - math.sin(ang) * dist * 1.3 + 40 * prog * prog
        if y > GROUND or (prog > 0.75 and hash01(k, 3, 5) < (prog - 0.75) * 3):
            continue
        _droplet(cv, x, y, k % 3 != 2, hot=k % 4 == 0)
    if prog < 0.8:                                          # sheets of gel thrown sideways
        for side in (-1, 1):
            base = x0 + side * (40 + 10 * prog)
            hgt = 7 * math.sin(math.pi * min(1.0, prog * 1.3))
            for i in range(9):
                x = base + side * i
                top = GROUND - hgt * (1 - i / 9) * (0.6 + 0.4 * math.sin(i * 1.7))
                for y in range(int(top), GROUND + 1):
                    cv.put(x, y, GEL[5] if y == int(top) else GEL[3] if i % 3 else GEL[4])
    reach = 36 + 14 * prog
    for side in (-1, 1):                                    # puddle splashes on the floor
        for i in range(int(7 * (1 - prog * 0.4))):
            cv.put(x0 + side * (reach + i * 2.2), GROUND, GEL[4] if i % 2 else GEL[3])


def draw_air_shadow(cv: Canvas, p: Pose) -> None:
    if p.shadow <= 0:
        return
    cx = CX + p.dx
    rx = 26 * (1 - 0.3 * p.shadow)
    for x in range(int(cx - rx), int(cx + rx) + 1):
        k = 1 - abs(x + 0.5 - cx) / rx
        if k <= 0:
            continue
        cv.put(x, GROUND, OUTLINE, solid=False, alpha=int(150 * p.shadow * min(1.0, k * 2)))
        if k > 0.4:
            cv.put(x, GROUND - 1, OUTLINE, solid=False, alpha=int(90 * p.shadow))


def glob_point(b: Body, prog: float) -> tuple[float, float]:
    sx, sy = b.to_cell(-16, 0.40)
    ex, ey = CX - 94, GROUND - 34
    x = sx + (ex - sx) * prog
    y = sy + (ey - sy) * prog - 20 * math.sin(math.pi * prog)
    return x, y


def draw_glob(cv: Canvas, b: Body, prog: float) -> None:
    if prog <= 0 or prog >= 1:
        return
    gx, gy = glob_point(b, prog)
    for k in range(1, 6):                                    # trailing drops
        tx, ty = glob_point(b, max(0.0, prog - 0.05 * k))
        _droplet(cv, tx, ty + k * 0.4, k < 3, hot=True)
    r = 4.6
    for yy in range(int(gy - r) - 1, int(gy + r) + 2):
        for xx in range(int(gx - r) - 2, int(gx + r) + 2):
            dx, dy = (xx + 0.5 - gx) / (r * 1.2), (yy + 0.5 - gy) / r
            d = dx * dx + dy * dy
            if d > 1.5:
                continue
            if d > 1:
                cv.put(xx, yy, OUTLINE, solid=False)
                continue
            light = 0.7 - 0.45 * dx - 0.4 * dy - 0.3 * d
            cv.put(xx, yy, ramp(ACID, max(0.0, min(1.0, light)), xx, yy))
    cv.put(gx - 1, gy - 2, ACID[3])


def _splatter(cv: Canvas, cx: float, cy: float, r: float, seed: int, solid: bool = False) -> None:
    """An irregular acid splash blob with spikes, lit from the upper left."""
    for yy in range(int(cy - r * 1.6) - 1, int(cy + r * 1.6) + 2):
        for xx in range(int(cx - r * 1.6) - 1, int(cx + r * 1.6) + 2):
            dx, dy = xx + 0.5 - cx, yy + 0.5 - cy
            a = math.atan2(dy, dx)
            rr = r * (0.75 + 0.3 * math.sin(a * 3 + seed) + 0.55 * max(0.0, math.sin(a * 7 + seed * 2)) ** 6)
            d = math.hypot(dx, dy) / max(0.5, rr)
            if d > 1:
                continue
            light = 0.75 - 0.35 * dx / r - 0.35 * dy / r - 0.25 * d
            cv.put(xx, yy, ramp(ACID, max(0.0, min(1.0, light)), xx, yy), solid=solid)


def draw_glob_splash(cv: Canvas, b: Body, prog: float) -> None:
    if prog <= 0:
        return
    hx, hy = glob_point(b, 1.0)
    if prog < 0.75:                                           # the hit: a splatter that spreads
        _splatter(cv, hx, hy, 3.5 + 6 * min(1.0, prog * 1.6) * (1 - max(0.0, prog - 0.5)), 3)
    for k in range(14):
        a = math.pi * (0.5 + 1.0 * hash01(k, 3, 6))           # backwards / up / down
        sp = 12 + 16 * hash01(k, 4, 6)
        x = hx + math.cos(a) * sp * prog * 1.2
        y = hy + math.sin(a) * sp * prog - 8 * prog + 30 * prog * prog
        if prog > 0.6 and hash01(k, 5, 6) < (prog - 0.6) * 2.2:
            continue
        _droplet(cv, x, y, k % 3 == 0, hot=True)
    if prog > 0.45:                                            # acid dripping off the target
        for k in range(3):
            x = hx - 3 + k * 3
            y = hy + 3 + (prog - 0.45) * (18 + 14 * hash01(k, 7, 6))
            cv.put(x, y, ACID[2], solid=False)
            cv.put(x, y - 1, ACID[1], solid=False)


def draw_ring(cv: Canvas, p: Pose, t: float) -> None:
    """Acid puddle ring spreading on the floor (cast)."""
    if p.ring <= 0:
        return
    k = min(1.0, p.ring)
    rx, ry = 22 + 26 * k, 3 + 4 * k
    cx, cy = CX + p.dx, GROUND + 1
    alpha = int(255 * min(1.0, 1.4 - k * 0.5))
    for i in range(220):
        a = i / 220 * TAU
        x, y = cx + math.cos(a) * rx, cy + math.sin(a) * ry
        on = (i + int(t * 40)) % 11 < 7
        cv.put(x, y, ACID[2] if on else ACID[0], solid=False, alpha=alpha)
        if math.sin(a) > 0.2:
            cv.put(x, y - 1, GEL[3], solid=False, alpha=alpha // 2)
        if i % 37 == 0 and k > 0.3:                           # fizz
            cv.put(x, y - 2 - int(3 * hash01(i, 2, 4) * k), ACID[3], solid=False)


def draw_fumes(cv: Canvas, b: Body, strength: float, t: float, spread: float = 1.0) -> None:
    """Acid fumes curling up from the body."""
    if strength <= 0:
        return
    top = b.y_of(BODY_H)
    for k in range(20):
        life = (t * 0.9 + hash01(k, 1, 8)) % 1.0
        x = CX + b.p.dx + (hash01(k, 2, 8) - 0.5) * 50 * spread + 3 * math.sin(life * 6 + k)
        y = top + 10 - life * 44 + 6 * hash01(k, 3, 8)
        if y < 2:
            continue
        r = 1 + int(2.5 * life)
        a = strength * (1 - life * 0.8) * 1.6
        for yy in range(int(y) - r, int(y) + r + 1):
            for xx in range(int(x) - r, int(x) + r + 1):
                if math.hypot(xx - x, yy - y) > r + 0.3 or bayer(xx, yy) > a:
                    continue
                col = FUME[2] if life < 0.3 else FUME[1] if life < 0.6 else FUME[0]
                cv.put(xx, yy, col, solid=False, alpha=int(255 * min(1.0, 0.4 + a)))


def draw_shed(cv: Canvas, b: Body, prog: float) -> None:
    """Droplets knocked off the body (hurt), flying right and up."""
    if prog <= 0:
        return
    for k in range(7):
        v = 0.3 + 0.6 * hash01(k, 1, 9)
        x0, y0 = b.to_cell(BODY_W * (0.6 + 0.4 * hash01(k, 2, 9)) * (1 if k % 3 else -0.6), v)
        sp = 12 + 12 * hash01(k, 3, 9)
        x = x0 + sp * prog * (1 if k % 3 else -0.4)
        y = y0 - sp * prog * 0.8 + 22 * prog * prog
        if x >= CELL_W - 1 or y > GROUND:
            continue
        _droplet(cv, x, y, k % 2 == 0, hot=k == 3)


def evaporate(cv: Canvas, d: float, cx: float) -> None:
    """Death: solid pixels boil away in a scattered pattern, the edges fizz acid-yellow."""
    if d <= 0:
        return
    for y in range(CELL_H):
        for x in range(CELL_W):
            c = cv.px[y][x]
            if c is None:
                continue
            edge = 1 - min(1.0, abs(x + 0.5 - cx) / 56)                # rims dry first
            n = 0.62 * edge + 0.38 * hash01(x, y, 17)
            if n < d * 1.05:
                cv.px[y][x] = None
            elif n < d * 1.05 + 0.08:
                cv.px[y][x] = (*(ACID[2] if hash01(x, y, 4) > 0.5 else ACID[1]), 255)


# ---------------------------------------------------------------- render
def render(p: Pose, t: float = 0.0) -> Canvas:
    cv = Canvas(CELL_W, CELL_H)
    if p.dissolve >= 1:
        return cv
    b = Body(p)
    draw_ring(cv, p, t)
    draw_air_shadow(cv, p)
    draw_drips(cv, p)
    mask = draw_body(cv, b)
    draw_debris(cv, b, mask)
    draw_bubbles(cv, b, mask)
    eyes = draw_face(cv, b)
    draw_shine(cv, b, mask)
    draw_shed(cv, b, p.shed)
    draw_splat(cv, p.splat, p.splat_x)
    outline(cv, OUTLINE)
    if p.eye > 0.05 and p.blink < 0.5:
        for ex, ey in eyes:
            cv.glow(ex - 0.5, ey - 0.5, 2.5 + 1.5 * p.eye, ACID[2], 0.22 * p.eye)
    if p.glow > 0.6:
        gx, gy = b.to_cell(0, 0.36)
        cv.glow(gx, gy, 18 + 8 * p.glow, ACID[1], 0.25 * (p.glow - 0.5), halo=False)
    draw_glob(cv, b, p.glob)
    draw_glob_splash(cv, b, p.gsplash)
    flash(cv, p.flash)
    evaporate(cv, p.dissolve, CX + p.dx)
    draw_fumes(cv, b, p.fumes, t, spread=1.0 + 0.6 * (1 - p.sy) if p.sy < 1 else 1.0)
    return cv


# ---------------------------------------------------------------- animations
IDLE_FRAMES = 12


def idle_pose(i: int, n: int = IDLE_FRAMES) -> Pose:
    i %= n
    a = TAU * i / n
    breath = math.sin(a)
    return Pose(
        sy=1.0 + 0.055 * breath, sx=1.0 - 0.04 * breath, lean=1.2 * math.sin(a + 0.9),
        phase=a, wobble=1.0, ripple=1.0, eye=1.0, blink=1.0 if i == 7 else 0.0,
        mouth=0.3 + 0.12 * math.sin(a - 1.0), glow=0.42 + 0.1 * math.sin(2 * a),
    )


def idle_frames():
    return [(idle_pose(i), 110) for i in range(IDLE_FRAMES)]


def attack_frames():
    """Aplastar: squash, leap left in an arc, splat on the hero, slide home."""
    b = idle_pose(0)
    land = CX - 40
    return [
        (replace(b, sy=0.84, sx=1.12, lean=2, mouth=0.05, eye=1.2, phase=0.3, wobble=0.6), 100),
        (replace(b, sy=0.70, sx=1.22, lean=4, mouth=0.0, eye=1.4, phase=0.5, wobble=0.4,
                 glow=0.6), 110),
        (replace(b, dx=-10, dy=-12, sy=1.32, sx=0.80, foot=0.2, lean=-5, mouth=0.4, eye=1.4,
                 phase=0.9, drips=1.0, shadow=0.5), 55),
        (replace(b, dx=-24, dy=-24, sy=1.14, sx=0.90, foot=0.0, lean=-3, mouth=0.6, eye=1.5,
                 phase=1.3, shadow=0.35), 55),
        (replace(b, dx=-35, dy=-10, sy=1.24, sx=0.84, foot=0.1, lean=1, mouth=0.7, eye=1.5,
                 phase=1.7, shadow=0.6), 55),
        (replace(b, dx=-40, sy=0.52, sx=1.40, lean=0, mouth=0.3, eye=1.2, blink=1.0, phase=2.1,
                 wobble=0.3, ripple=2.0, splat=0.3, splat_x=land, glow=0.7), 60),
        (replace(b, dx=-40, sy=0.70, sx=1.26, mouth=0.5, eye=1.3, phase=2.6, wobble=1.5,
                 ripple=2.0, splat=0.65, splat_x=land, glow=0.6), 75),
        (replace(b, dx=-38, sy=1.10, sx=0.93, mouth=0.4, phase=3.1, wobble=2.0, splat=0.95,
                 splat_x=land), 65),
        (replace(b, dx=-24, sy=0.95, sx=1.05, lean=4, phase=3.8, wobble=1.6), 80),
        (replace(b, dx=-10, sy=1.02, lean=3, phase=4.6, wobble=1.3), 80),
        (replace(b, dx=-3, lean=1.5, phase=5.4), 75),
        (b, 95),
    ]


def spit_frames():
    """Escupitajo Ácido: inflate, spit a glob that arcs left and splashes on the hero."""
    b = idle_pose(0)
    return [
        (replace(b, sy=1.10, sx=1.06, lean=2, mouth=0.35, glow=0.8, eye=1.2, phase=0.3), 100),
        (replace(b, sy=1.17, sx=1.10, lean=4, mouth=0.75, glow=1.05, eye=1.4, boil=0.4,
                 phase=0.6), 110),
        (replace(b, sy=0.88, sx=1.08, lean=-5, mouth=1.0, glow=0.9, eye=1.4, phase=1.0,
                 glob=0.22), 55),
        (replace(b, sy=0.95, sx=1.03, lean=-3, mouth=0.8, glow=0.7, phase=1.4, glob=0.58), 55),
        (replace(b, sy=1.0, lean=-2, mouth=0.6, glow=0.6, phase=1.8, glob=0.9), 55),
        (replace(b, sy=1.02, lean=-1, mouth=0.5, phase=2.2, gsplash=0.3), 60),
        (replace(b, lean=0, mouth=0.4, phase=2.8, gsplash=0.65), 80),
        (replace(b, mouth=0.3, phase=3.6, gsplash=0.92), 85),
        (replace(b, phase=4.8), 90),
        (b, 100),
    ]


def cast_frames():
    """Corroer: the gel boils and glows, fumes rise, a puddle ring spreads."""
    b = idle_pose(0)
    out = []
    ups = [0.3, 0.65, 1.0, 1.0, 1.0, 1.0, 0.75, 0.45, 0.15]
    for k, u in enumerate(ups):
        out.append((replace(
            b, sy=1.0 + 0.07 * u * (1 if k % 2 else 0.6), sx=1.0 + 0.04 * u, phase=0.7 * k,
            wobble=1.0 + 1.2 * u, ripple=1.0 + 1.6 * u, boil=u, glow=0.45 + 0.85 * u,
            eye=1.0 + 0.5 * u, mouth=0.18 + 0.4 * u, fumes=u,
            ring=min(1.0, (k + 1) / 5) if k < 7 else u), 85))
    out.append((b, 110))
    return out


def hurt_frames():
    b = idle_pose(0)
    return [
        (replace(b, dx=4, sx=1.14, sy=0.82, flash=0.82, wobble=3.5, ripple=2.5, blink=1.0,
                 mouth=0.5, phase=1.0, shed=0.25), 55),
        (replace(b, dx=6, sx=0.92, sy=1.10, flash=0.55, wobble=4.0, ripple=2.5, blink=1.0,
                 mouth=0.6, phase=2.4, shed=0.55), 60),
        (replace(b, dx=6, sx=1.07, sy=0.93, flash=0.22, wobble=3.0, ripple=2.0, eye=0.6,
                 mouth=0.4, phase=3.8, shed=0.85), 70),
        (replace(b, dx=4, sx=0.97, sy=1.04, wobble=2.2, ripple=1.5, eye=0.8, phase=5.0), 80),
        (replace(b, dx=2, sx=1.02, sy=0.98, wobble=1.5, phase=5.9), 85),
        (b, 105),
    ]


def death_frames():
    b = idle_pose(0)
    out = [
        (replace(b, dx=4, sx=1.14, sy=0.84, flash=0.85, wobble=3.5, ripple=2.5, blink=1.0,
                 mouth=0.6, phase=1.0, shed=0.3), 70),
        (replace(b, dx=3, sx=0.94, sy=1.14, flash=0.3, wobble=2.5, eye=1.8, mouth=0.9,
                 glow=1.1, boil=0.8, phase=2.0), 100),
    ]
    collapse = 6
    for k in range(collapse):
        u = smooth((k + 1) / collapse)
        out.append((replace(b, dx=round(-4 * u), sy=1.0 - 0.80 * u, sx=1.0 + 0.38 * u,
                            wobble=2.0 * (1 - u), ripple=1.5 * (1 - u) + 0.3, eye=1.2 * (1 - u),
                            blink=1.0 if u > 0.6 else 0.0, mouth=0.6 * (1 - u), glow=0.9 - 0.4 * u,
                            boil=0.6 * (1 - u), phase=2.6 + 0.5 * k, fumes=0.3 * u), 80))
    evap = 6
    for k in range(evap):
        u = (k + 1) / (evap + 1)
        out.append((replace(b, dx=-4, sy=0.2 - 0.08 * u, sx=1.38 - 0.4 * u, wobble=0.0, ripple=0.3, eye=0.0, blink=1.0,
                            mouth=0.0, glow=0.5, phase=5.6 + 0.4 * k, drips=1.0 - u,
                            dissolve=0.05 + 0.9 * u, fumes=1.0 - 0.3 * u), 85))
    out.append((replace(b, dissolve=1.0), 120))
    return out


ANIMATIONS = {
    "idle": (idle_frames, True),
    "attack": (attack_frames, False),
    "spit": (spit_frames, False),
    "cast": (cast_frames, False),
    "hurt": (hurt_frames, False),
    "death": (death_frames, False),
}

# Frames where the hit lands (attack: the splat landing; spit: the glob splashes).
EVENTS = {"attack": {"strikes": [5]}, "spit": {"strikes": [5]}}
MOVES = {"slam": "attack", "spit": "spit", "corrode": "cast", "vengeance": "cast"}


def build():
    return build_sheet(ANIMATIONS, render, (CELL_W, CELL_H), ANCHOR, f"{SHEET_ID}_sheet.png",
                       {"events": EVENTS, "moves": MOVES})


def main() -> None:
    sheet, meta = build()
    save_sheet(OUT_DIR, SHEET_ID, sheet, meta)
    print(f"wrote assets/enemies/{SHEET_ID}_sheet.png ({len(sheet[0])}x{len(sheet)}) and .json")


if __name__ == "__main__":
    main()
