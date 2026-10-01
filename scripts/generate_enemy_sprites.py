"""Draw and animate the generic dungeon enemy "Espectro" (a hooded wraith).

Standard library only:

    python scripts/generate_enemy_sprites.py

Unlike the heroes (animated from approved illustrations) this enemy is drawn
entirely by code, at native pixel resolution, from shapes shaded with a fixed
palette and an ordered dither:

* a tattered hooded cloak (cold violet ramp, upper-left light, vertical folds)
  whose ragged hem fades into ghostly teal tendrils that wave;
* a void under the hood with two glowing eyes and a pulsing soul flame on the
  chest;
* bony claws out of bell sleeves and a broken rusty shackle chain.

Every frame is a *pose* (offsets, lean, squash, arm targets, glow levels) fed
to the same renderer, so animations stay consistent and fluid:

  idle   12-frame hover loop (bob, tendril wave, chain swing, pulsing core)
  attack wind-up, lunge to the left with a claw slash arc, recovery
  hurt   white flash, knock-back and shiver
  cast   arms raised, rune circle under the wraith (block / buff intents)
  death  recoil, eye flare and a bottom-up dissolve into rising motes

Every action except ``death`` ends on idle frame 0. Output
(``assets/enemies/``): ``wraith_sheet.png`` (native cells, scaled ×2 at load)
and ``wraith_sheet.json`` (cell size, anchor, animations).
"""
from __future__ import annotations

import json
import math
import struct
import zlib
from dataclasses import dataclass, field, replace
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "assets" / "enemies"
SHEET_PATH = OUT_DIR / "wraith_sheet.png"
META_PATH = OUT_DIR / "wraith_sheet.json"

CELL_W, CELL_H = 128, 104
CX, TOP, BOTTOM = 80, 18, 92          # body centre line, hood tip, lowest tendril
ANCHOR = (CX, 96)                     # ground point under the wraith (native px)

# ---------------------------------------------------------------- palette
OUTLINE = (10, 7, 18)
CLOAK = [(14, 11, 26), (26, 20, 44), (40, 31, 64), (58, 45, 90), (82, 66, 122), (116, 98, 160), (150, 134, 192)]
GHOST = [(18, 40, 52), (26, 70, 80), (44, 112, 116), (80, 170, 160)]
VOID = (5, 4, 10)
TEAL = [(30, 96, 100), (60, 170, 160), (130, 235, 215), (220, 255, 245)]
BONE = [(62, 56, 52), (112, 104, 90), (168, 160, 138), (222, 216, 192)]
IRON = [(40, 36, 42), (78, 72, 76), (126, 118, 114), (176, 166, 150)]
RUST = (122, 66, 38)
WHITE = (255, 255, 255)

BAYER = [[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]]


def bayer(x: int, y: int) -> float:
    return (BAYER[y & 3][x & 3] + 0.5) / 16.0


def hash01(x: int, y: int, s: int = 0) -> float:
    h = (x * 374761393 + y * 668265263 + s * 2147483647) & 0xFFFFFFFF
    h = ((h ^ (h >> 13)) * 1274126177) & 0xFFFFFFFF
    return ((h ^ (h >> 16)) & 0xFFFF) / 65535.0


def mix(a, b, k: float):
    k = max(0.0, min(1.0, k))
    return tuple(int(round(a[i] + (b[i] - a[i]) * k)) for i in range(3))


# ---------------------------------------------------------------- pose
@dataclass(frozen=True)
class Pose:
    dx: float = 0.0            # body offset (native px)
    dy: float = 0.0
    lean: float = 0.0          # hood offset relative to the hem (negative = towards the hero)
    sx: float = 1.0            # squash / stretch around the body centre
    sy: float = 1.0
    phase: float = 0.0         # tendril / cloak wave
    sway: float = 1.6
    hand_f: tuple[float, float] = (-30.0, 46.0)   # front (screen-left) hand, relative to (CX, TOP)
    hand_b: tuple[float, float] = (28.0, 43.0)    # back hand
    claw: float = 0.3          # 0 closed .. 1 spread
    eye: float = 1.0           # eye glow
    core: float = 0.8          # chest soul flame
    chain: float = 0.0         # chain swing (radians)
    flash: float = 0.0         # white hit flash
    dissolve: float = 0.0      # 0 intact .. 1 gone
    slash: float = 0.0         # claw slash arc progress (0 none)
    slash_fade: float = 0.0
    rune: float = 0.0          # rune circle under the body
    motes: tuple = field(default_factory=tuple)   # baked (x, y, colour index) sparks


class Canvas:
    def __init__(self) -> None:
        self.px = [[None] * CELL_W for _ in range(CELL_H)]
        self.solid = [[False] * CELL_W for _ in range(CELL_H)]

    def put(self, x: int, y: int, c, *, solid: bool = True, alpha: int = 255) -> None:
        if 0 <= x < CELL_W and 0 <= y < CELL_H:
            if alpha >= 255:
                self.px[y][x] = (*c, 255)
            else:
                old = self.px[y][x]
                if old is None:
                    self.px[y][x] = (*c, alpha)
                else:
                    k = alpha / 255
                    self.px[y][x] = (*mix(old[:3], c, k), max(old[3], alpha))
            if solid:
                self.solid[y][x] = True

    def get(self, x: int, y: int):
        if 0 <= x < CELL_W and 0 <= y < CELL_H:
            return self.px[y][x]
        return None

    def glow(self, cx: float, cy: float, radius: float, color, strength: float) -> None:
        """Soft light: brightens existing pixels, adds faint colour around them."""
        r = int(radius + 1)
        for y in range(int(cy) - r, int(cy) + r + 1):
            for x in range(int(cx) - r, int(cx) + r + 1):
                d = math.hypot(x + 0.5 - cx, y + 0.5 - cy) / radius
                if d >= 1:
                    continue
                k = (1 - d) ** 2 * strength
                if k < bayer(x, y) * 0.25:
                    continue
                old = self.get(x, y)
                if old is None:
                    if k > 0.18:
                        self.put(x, y, color, solid=False, alpha=int(min(200, 255 * k)))
                else:
                    self.px[y][x] = (*mix(old[:3], color, min(0.85, k)), old[3])


# ---------------------------------------------------------------- body geometry
class Body:
    """Body frame of one pose: maps local body coords <-> cell pixels."""

    def __init__(self, p: Pose) -> None:
        self.p = p
        self.h = BOTTOM - TOP
        self.pivot_y = TOP + self.h * 0.5

    def center(self, v: float) -> float:
        p = self.p
        wave = p.sway * math.sin(p.phase + v * 4.2) * max(0.0, v - 0.35) ** 1.3 * 2.2
        return CX + p.dx + p.lean * (1 - v) ** 1.2 + wave

    def to_cell(self, lx: float, ly: float) -> tuple[float, float]:
        """Local offset from (CX, TOP) before squash -> cell coords."""
        p = self.p
        y = TOP + ly
        v = max(0.0, min(1.0, ly / self.h))
        x = self.center(v) + lx * p.sx
        y =self.pivot_y + (y - self.pivot_y) * p.sy + p.dy
        return x, y

    def local_v(self, y: float) -> float:
        p = self.p
        ly = (y - p.dy - self.pivot_y) / p.sy + self.pivot_y - TOP
        return ly / self.h


def half_width(v: float) -> float:
    if v < 0:
        return 0.0
    if v < 0.22:                          # hood: rounded dome
        k = v / 0.22
        return 3 + 10.5 * math.sqrt(k)
    if v < 0.34:                          # shoulders
        k = (v - 0.22) / 0.12
        return 13.5 + 6.5 * math.sin(k * math.pi / 2)
    if v < 0.56:                          # waist narrows under the ribs
        return 20 - 4.5 * math.sin((v - 0.34) / 0.22 * math.pi / 2)
    return 15.5 + 9.5 * ((v - 0.56) / 0.44) ** 1.2


STRANDS = 7
HEM_V = 0.64                                # where the cloak frays into strands


def strand_len(k: int) -> float:
    return 0.86 + 0.14 * hash01(k, 11) - (0.06 if k in (0, STRANDS - 1) else 0.0)


def draw_cloak(cv: Canvas, b: Body) -> None:
    p = b.p
    for y in range(CELL_H):
        v = b.local_v(y + 0.5)
        if v < 0 or v > 1.05:
            continue
        c = b.center(min(1.0, v))
        hw = half_width(min(v, 1.0)) * p.sx
        if v < 0.06:                              # hood peak leaning back
            c += (0.06 - v) * 40
        fray = max(0.0, (v - HEM_V) / (1.0 - HEM_V))
        for x in range(CELL_W):
            dxp = x + 0.5 - c
            u = dxp / max(1.0, hw)
            k = -1
            f = 0.0
            if fray > 0:
                # the hem splits into tapering strands that wave on their own
                k0 = int(math.floor((u + 1) / 2 * STRANDS))
                wob = 1.6 * fray * math.sin(p.phase + k0 * 1.7 + v * 7)
                pos = ((dxp - wob) / max(1.0, hw) + 1) / 2 * STRANDS
                k = int(math.floor(pos))
                if k < 0 or k >= STRANDS:
                    continue
                ln = strand_len(k)
                if v > ln:
                    continue
                f = (v - HEM_V) / (ln - HEM_V)      # 0 at the fray line, 1 at the tip
                half = 0.5 * (1 - f) ** 0.8 + 0.06
                if abs(pos - k - 0.5) > half:
                    continue
            elif abs(dxp) > hw:
                continue
            # shading: upper-left light, folds, darker low
            light = 0.66 - 0.36 * u - 0.44 * v
            if v > 0.3:
                light += 0.13 * math.cos(u * 8.5 + v * 2.5 + 0.3 * math.sin(p.phase))
            if abs(u) > 0.86:
                light -= 0.14
            if u < -0.78 and v < 0.62:
                light += 0.18
            level = light * (len(CLOAK) - 1) + (bayer(x, y) - 0.5) * 0.55
            col = CLOAK[max(0, min(len(CLOAK) - 1, int(round(level))))]
            solid = True
            if k >= 0:
                g = f * 3.4 + (bayer(x, y) - 0.5) * 0.8 - 0.5
                if g > 0:
                    col = mix(col, GHOST[max(0, min(3, int(g)))], min(0.92, 0.3 + f))
                if f > 0.72:
                    solid = False
                    if bayer(x, y) < (f - 0.72) * 2.4:
                        continue
            cv.put(x, y, col, solid=solid)


def draw_capelet(cv: Canvas, b: Body) -> None:
    """Short shoulder mantle over the cloak with a torn edge and a shadow under it."""
    p = b.p
    for y in range(CELL_H):
        v = b.local_v(y + 0.5)
        if v < 0.2 or v > 0.5:
            continue
        c = b.center(v)
        hw = (half_width(v) + 1.5) * p.sx
        for x in range(CELL_W):
            dxp = x + 0.5 - c
            if abs(dxp) > hw:
                continue
            u = dxp / hw
            edge = 0.40 + 0.035 * math.sin(u * 11 + 0.7) + 0.03 * hash01(int(u * 6 + 9), 5) + 0.05 * u * u
            if v > edge + 0.018:
                continue
            if v > edge - 0.004:
                cv.put(x, y, CLOAK[0])              # shadow cast on the cloak below
                continue
            light = 0.8 - 0.4 * u - 0.5 * (v - 0.2) / 0.2
            if abs(u) > 0.9:
                light -= 0.2
            level = light * (len(CLOAK) - 1) + (bayer(x, y) - 0.5) * 0.55
            cv.put(x, y, CLOAK[max(0, min(len(CLOAK) - 1, int(round(level))))])


def draw_hood(cv: Canvas, b: Body) -> tuple[float, float]:
    """Void under the hood, rim highlight and the two eyes. Returns the eye centre."""
    p = b.p
    hx, hy = b.to_cell(-3.0, 15.5)
    rx, ry = 7.6 * p.sx, 8.2 * p.sy
    for y in range(int(hy - ry) - 3, int(hy + ry) + 3):
        for x in range(int(hx - rx) - 3, int(hx + rx) + 3):
            dx, dy = (x + 0.5 - hx) / rx, (y + 0.5 - hy) / ry
            d = dx * dx + dy * dy
            if d < 1.0:
                if dy < -0.45 + 0.25 * dx * dx:      # brow of the hood overhangs
                    col = CLOAK[1] if dy > -0.8 else CLOAK[2]
                else:
                    col = VOID if dy < 0.35 else mix(VOID, GHOST[1], (dy - 0.35) * 0.9)
                cv.put(x, y, col)
            elif d < 1.6 and cv.get(x, y) is not None:
                lit = dx < -0.1 or dy < -0.6
                cv.put(x, y, CLOAK[6] if (lit and d < 1.3) else CLOAK[5] if lit else CLOAK[4])
    ex, ey = hx, hy + 1.0
    e = p.eye
    if e > 0.05:
        hot = TEAL[3] if e > 0.6 else TEAL[1]
        warm = TEAL[2] if e < 1.2 else TEAL[3]
        for (ox, oy, c) in ((-5, -1, warm), (-4, 0, hot), (-3, 0, warm),
                            (2, 0, warm), (3, 0, hot), (4, -1, warm)):
            cv.put(int(ex + ox), int(ey + oy), c)
        if e > 1.1:
            for (ox, oy) in ((-6, -2), (5, -2), (-4, 1), (3, 1)):
                cv.put(int(ex + ox), int(ey + oy), TEAL[1])
    return ex - 0.5, ey


def draw_chest_chain(cv: Canvas, b: Body) -> None:
    """Rusty chain slung across the chest, from the left shoulder to the right hip."""
    x0, y0 = b.to_cell(-14, 26)
    x1, y1 = b.to_cell(15, 44)
    n = 9
    for i in range(n + 1):
        t = i / n
        sag = 2.2 * math.sin(t * math.pi)
        x, y = x0 + (x1 - x0) * t, y0 + (y1 - y0) * t + sag
        xi, yi = int(x), int(y)
        if i % 2 == 0:
            for ox, oy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                cv.put(xi + ox, yi + oy, IRON[3] if (ox < 0 or oy < 0) else IRON[1])
            cv.put(xi, yi, CLOAK[0])
            if i in (4, 8):
                cv.put(xi + 1, yi + 1, RUST)
        else:
            cv.put(xi, yi, IRON[2])
            cv.put(xi + 1, yi, IRON[1])


def draw_core(cv: Canvas, b: Body) -> tuple[float, float]:
    p = b.p
    cx, cy = b.to_cell(-1.5, 31)
    k = p.core
    if k <= 0.05:
        return cx, cy
    shape = [(0, -3, 1), (0, -2, 2), (-1, -1, 1), (0, -1, 3), (1, -1, 1), (-1, 0, 2), (0, 0, 3), (1, 0, 2),
             (0, 1, 2), (-1, 1, 1), (1, 1, 1), (0, 2, 1)]
    for ox, oy, lvl in shape:
        lv = max(0, min(3, lvl - (1 if k < 0.6 else 0) + (1 if k > 1.1 else 0)))
        cv.put(int(cx) + ox, int(cy) + oy, TEAL[lv])
    return cx, cy


def line_points(x0, y0, x1, y1):
    n = int(max(abs(x1 - x0), abs(y1 - y0))) + 1
    return [(x0 + (x1 - x0) * i / max(1, n - 1), y0 + (y1 - y0) * i / max(1, n - 1)) for i in range(n)]


def draw_arm(cv: Canvas, b: Body, shoulder_lx: float, hand, *, back: bool) -> tuple[float, float]:
    p = b.p
    ex = ey = 0.0
    sx, sy = b.to_cell(shoulder_lx, 26)
    hx, hy = CX + p.dx + hand[0] * p.sx, TOP + hand[1] * p.sy + p.dy
    # curved sleeve: the elbow bows outwards and down (quadratic Bezier)
    side = -1 if shoulder_lx < 0 else 1
    ex, ey = (sx + hx) / 2 + side * 4, (sy + hy) / 2 + 3
    steps = int(math.hypot(hx - sx, hy - sy) * 1.6) + 2
    pts = []
    for i in range(steps):
        t = i / (steps - 1)
        pts.append(((1 - t) ** 2 * sx + 2 * (1 - t) * t * ex + t * t * hx,
                    (1 - t) ** 2 * sy + 2 * (1 - t) * t * ey + t * t * hy))
    n = len(pts)
    dirx, diry = hx - ex, hy - ey
    L = max(1.0, math.hypot(dirx, diry))
    nx, ny = -diry / L, dirx / L
    ramp = CLOAK[:-2] if back else CLOAK[1:]
    arm = Canvas()
    for i, (x, y) in enumerate(pts):
        t = i / max(1, n - 1)
        r = 4.4 - 1.4 * t + (2.6 * max(0.0, t - 0.68) / 0.32)       # bell sleeve at the wrist
        for yy in range(int(y - r) - 1, int(y + r) + 2):
            for xx in range(int(x - r) - 1, int(x + r) + 2):
                d = math.hypot(xx + 0.5 - x, yy + 0.5 - y)
                if d > r:
                    continue
                side = ((xx + 0.5 - x) * nx + (yy + 0.5 - y) * ny) / max(0.5, r)
                light = 0.55 - 0.35 * side * (1 if nx < 0 else -1) - 0.25 * (yy + 0.5 - y) / r
                light -= 0.15 * t
                if back:
                    light -= 0.12
                idx = max(0, min(len(ramp) - 1, int(round(light * (len(ramp) - 1) + (bayer(xx, yy) - 0.5) * 0.6))))
                arm.put(xx, yy, ramp[idx])
    for yy in range(CELL_H):                 # dark rim where the sleeve crosses the cloak
        for xx in range(CELL_W):
            if arm.px[yy][xx] is None and cv.px[yy][xx] is not None:
                if any(arm.get(xx + ox, yy + oy) is not None for ox, oy in ((1, 0), (-1, 0), (0, 1), (0, -1))):
                    cv.put(xx, yy, OUTLINE)
    for yy in range(CELL_H):
        for xx in range(CELL_W):
            if arm.px[yy][xx] is not None:
                cv.put(xx, yy, arm.px[yy][xx][:3])
    # sleeve opening (dark) and claws
    ox, oy = hx + dirx / L * 1.5, hy + diry / L * 1.5
    cv.put(int(ox), int(oy), CLOAK[0])
    cv.put(int(ox + nx), int(oy + ny), CLOAK[0])
    draw_claws(cv, ox, oy, dirx / L, diry / L, p.claw, back)
    return ox, oy


def draw_claws(cv: Canvas, x: float, y: float, dx: float, dy: float, spread: float, back: bool) -> None:
    base_ang = math.atan2(dy, dx)
    fingers = [(-0.6, 7.5), (-0.15, 9.5), (0.3, 8.5), (0.8, 5.5)]
    for k, (a, length) in enumerate(fingers):
        ang = base_ang + a * (0.45 + 0.9 * spread)
        curl = 0.5 * (1 - spread)
        px, py = x, y
        for s in range(int(length)):
            ang2 = ang + curl * s / length
            px += math.cos(ang2)
            py += math.sin(ang2)
            tip = s >= length - 2
            col = BONE[0] if tip else BONE[3 if (s % 3 == 1 and not back) else 2 if not back else 1]
            cv.put(int(px), int(py), col)
    # knuckles
    cv.put(int(x), int(y), BONE[2])
    cv.put(int(x + dx), int(y + dy), BONE[3] if not back else BONE[2])


def draw_chain(cv: Canvas, wrist, swing: float, broken_len: int = 5) -> None:
    x, y = wrist
    # shackle
    for ox, oy in [(-2, -1), (-2, 0), (-2, 1), (2, -1), (2, 0), (2, 1), (-1, 2), (0, 2), (1, 2)]:
        cv.put(int(x) + ox, int(y) + oy, IRON[2] if ox < 0 else IRON[1])
    cv.put(int(x) - 1, int(y) + 2, RUST)
    ang = math.pi / 2 + swing
    cx, cy = x, y + 3
    for i in range(broken_len):
        a = ang + swing * 0.35 * i
        cx += math.cos(a) * 3
        cy += math.sin(a) * 3
        if i % 2 == 0:
            for ox, oy in [(-1, -1), (0, -1), (-1, 0), (1, 0), (-1, 1), (0, 1)]:
                cv.put(int(cx) + ox, int(cy) + oy, IRON[3] if ox < 0 else IRON[1])
            if i == 2:
                cv.put(int(cx), int(cy) + 1, RUST)
        else:
            cv.put(int(cx), int(cy), IRON[2])
            cv.put(int(cx), int(cy) - 1, IRON[1])


def outline(cv: Canvas) -> None:
    add = []
    for y in range(CELL_H):
        for x in range(CELL_W):
            if cv.px[y][x] is not None:
                continue
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nx, ny = x + dx, y + dy
                if 0 <= nx < CELL_W and 0 <= ny < CELL_H and cv.solid[ny][nx]:
                    add.append((x, y))
                    break
    for x, y in add:
        cv.px[y][x] = (*OUTLINE, 255)


def draw_slash(cv: Canvas, cx: float, cy: float, prog: float, fade: float) -> None:
    """Three parallel claw trails sweeping down through the left of (cx, cy)."""
    if prog <= 0:
        return
    a0, a1 = -1.75, -4.55                     # from above, through the left, to below
    a_end = a0 + (a1 - a0) * min(1.0, prog)
    steps = 120
    for line, (rad, thick) in enumerate(((17.0, 1), (21.0, 2), (25.0, 1))):
        for i in range(steps):
            t = i / (steps - 1)                  # 1 = leading edge
            w = t - fade * 1.15
            if w <= 0:
                continue
            a = a0 + (a_end - a0) * t
            r = rad + 1.5 * math.sin(t * math.pi)
            x = cx + math.cos(a) * r * 1.15
            y = cy + math.sin(a) * r
            lv = 3 if w > 0.75 else 2 if w > 0.4 else 1 if w > 0.15 else 0
            alpha = int(255 * min(1.0, 0.25 + w * 1.1))
            for k in range(thick if w > 0.3 else 1):
                cv.put(int(x), int(y) + k, TEAL[lv], solid=False, alpha=alpha)
            if w > 0.9 and line == 1:            # bright head
                cv.put(int(x) - 1, int(y), WHITE, solid=False)


def draw_rune(cv: Canvas, strength: float, t: float) -> None:
    if strength <= 0:
        return
    gx, gy = ANCHOR[0], ANCHOR[1] - 1
    rx, ry = 26 * min(1.0, strength + 0.2), 6 * min(1.0, strength + 0.2)
    for i in range(160):
        a = i / 160 * math.tau
        x, y = gx + math.cos(a) * rx, gy + math.sin(a) * ry
        on = (i + int(t * 40)) % 10 < 7
        lv = 2 if on else 1
        cv.put(int(x), int(y), TEAL[lv], solid=False, alpha=int(230 * strength))
    for i in range(6):                               # glyph ticks on an inner ring
        a = i / 6 * math.tau + t * 2
        x, y = gx + math.cos(a) * rx * 0.7, gy + math.sin(a) * ry * 0.7
        cv.put(int(x), int(y), TEAL[3], solid=False, alpha=int(255 * strength))
        cv.put(int(x) + 1, int(y), TEAL[2], solid=False, alpha=int(200 * strength))


def render(p: Pose, t: float = 0.0) -> Canvas:
    cv = Canvas()
    b = Body(p)
    draw_rune(cv, p.rune, t)
    draw_arm(cv, b, 14, p.hand_b, back=True)
    draw_cloak(cv, b)
    wrist = draw_arm(cv, b, -14, p.hand_f, back=False)
    draw_capelet(cv, b)
    eye = draw_hood(cv, b)
    draw_chest_chain(cv, b)
    core = draw_core(cv, b)
    draw_chain(cv, (wrist[0] + 1, wrist[1] - 3), p.chain)
    outline(cv)
    # lights
    if p.eye > 0.05:
        cv.glow(eye[0] - 1.5, eye[1] + 0.5, 6 + 3 * p.eye, TEAL[1], 0.45 * p.eye)
    if p.core > 0.05:
        cv.glow(core[0] + 0.5, core[1], 7 + 3 * p.core, TEAL[1], 0.4 * p.core)
    if p.slash > 0:
        draw_slash(cv, CX + p.dx - 18, TOP + 36 + p.dy, p.slash, p.slash_fade)
    for (mx, my, lv) in p.motes:
        cv.put(int(mx), int(my), TEAL[lv], solid=False)
    if p.flash > 0:
        for y in range(CELL_H):
            for x in range(CELL_W):
                c = cv.px[y][x]
                if c is not None and cv.solid[y][x]:
                    cv.px[y][x] = (*mix(c[:3], WHITE, p.flash), c[3])
    if p.dissolve > 0:
        dissolve(cv, b, p.dissolve)
    return cv


def dissolve(cv: Canvas, b: Body, d: float) -> None:
    """Bottom-up burn: pixels vanish past a noisy front; the front glows teal."""
    top, bottom = TOP - 4, BOTTOM + 4
    front = bottom - (bottom - top + 12) * d            # pixels below the front are gone
    for y in range(CELL_H):
        for x in range(CELL_W):
            c = cv.px[y][x]
            if c is None:
                continue
            f = front + (hash01(x, y, 3) - 0.5) * 12
            if y > f:
                cv.px[y][x] = None
            elif y > f - 2.5:
                cv.px[y][x] = (*TEAL[3 if hash01(x, y, 5) > 0.5 else 2], 255)
            elif y > f - 5:
                cv.px[y][x] = (*mix(c[:3], TEAL[1], 0.6), c[3])


# ---------------------------------------------------------------- animations
IDLE_FRAMES = 12


def idle_pose(i: int, n: int = IDLE_FRAMES) -> Pose:
    t = i / n
    a = math.tau * t
    bob = round(2.0 * math.sin(a))
    arm = 1.5 * math.sin(a + 0.9)
    return Pose(
        dy=-bob, phase=a, sway=1.6,
        hand_f=(-27.0, 52.0 + arm), hand_b=(26.0, 49.0 + arm * 0.8),
        claw=0.3 + 0.1 * math.sin(a + 2), eye=0.85 if i == 7 else 1.0,
        core=0.75 + 0.3 * math.sin(a * 2), chain=0.28 * math.sin(a + 1.3),
    )


def idle_frames():
    return [(idle_pose(i), 110) for i in range(IDLE_FRAMES)]


def attack_frames():
    b = idle_pose(0)
    return [
        (replace(b, dx=2, lean=3, hand_f=(-20, 38), hand_b=(26, 40), eye=1.2, claw=0.6, phase=0.4), 90),
        (replace(b, dx=5, lean=6, sy=0.96, hand_f=(-8, 12), hand_b=(26, 26), eye=1.45, claw=1.0,
                 core=1.2, phase=0.8, chain=0.6), 110),
        (replace(b, dx=-9, lean=-8, sx=1.06, hand_f=(-40, 30), hand_b=(20, 36), eye=1.5, claw=1.0,
                 core=1.2, phase=1.6, chain=-0.5, slash=0.55), 55),
        (replace(b, dx=-15, lean=-10, sx=1.04, hand_f=(-44, 52), hand_b=(18, 40), eye=1.4, claw=0.9,
                 phase=2.2, chain=-0.8, slash=1.0), 60),
        (replace(b, dx=-16, lean=-9, hand_f=(-40, 56), hand_b=(18, 42), eye=1.25, claw=0.7,
                 phase=2.8, chain=-0.6, slash=1.0, slash_fade=0.45), 80),
        (replace(b, dx=-12, lean=-6, hand_f=(-35, 54), eye=1.15, phase=3.4, chain=-0.2, slash=1.0,
                 slash_fade=0.9), 90),
        (replace(b, dx=-7, lean=-3, hand_f=(-31, 52), phase=4.0, chain=0.2), 90),
        (replace(b, dx=-3, lean=-1, hand_f=(-28, 52), phase=4.8, chain=0.3), 90),
        (b, 110),
    ]


def hurt_frames():
    b = idle_pose(0)
    return [
        (replace(b, dx=5, lean=5, sx=0.93, sy=1.04, hand_f=(-20, 42), hand_b=(29, 40), eye=0.4,
                 flash=0.82, claw=1.0, phase=1.5, chain=0.9), 55),
        (replace(b, dx=8, lean=6, sx=0.95, hand_f=(-18, 44), hand_b=(31, 42), eye=0.6, flash=0.6,
                 claw=0.9, phase=2.2, chain=1.0), 60),
        (replace(b, dx=6, lean=4, dy=1, hand_f=(-21, 46), hand_b=(28, 44), eye=0.8, flash=0.25,
                 phase=2.9, chain=0.6), 70),
        (replace(b, dx=5, lean=3, hand_f=(-23, 49), eye=1.0, phase=3.6, chain=0.2), 70),
        (replace(b, dx=3, lean=1, hand_f=(-25, 51), phase=4.3, chain=-0.1), 80),
        (replace(b, dx=1, phase=5.0, chain=-0.1), 90),
        (b, 100),
    ]


def cast_frames():
    b = idle_pose(0)
    out = []
    ups = [(0.0, 0.25), (0.35, 0.55), (0.7, 0.85), (1.0, 1.0), (1.0, 1.0), (1.0, 0.9), (0.6, 0.6),
           (0.25, 0.3)]
    for k, (u, r) in enumerate(ups):
        out.append((replace(
            b, dy=-round(3 * u), hand_f=(-27 + 4 * u, 52 - 34 * u), hand_b=(26 - 2 * u, 49 - 34 * u),
            claw=0.3 + 0.7 * u, eye=1.0 + 0.5 * u, core=0.8 + 0.6 * u, rune=r, phase=0.5 * k,
            chain=0.3 * math.sin(k)), 85))
    out.append((b, 110))
    return out


def death_frames():
    b = idle_pose(0)
    out = [
        (replace(b, dx=5, lean=5, flash=0.85, eye=0.5, hand_f=(-22, 34), hand_b=(28, 30), claw=1.0), 70),
        (replace(b, dx=7, lean=3, sy=1.06, flash=0.4, eye=1.8, core=1.4, hand_f=(-26, 18),
                 hand_b=(30, 16), claw=1.0, phase=1.0), 90),
        (replace(b, dx=7, sy=1.08, eye=1.8, core=1.5, hand_f=(-28, 14), hand_b=(31, 12), claw=1.0,
                 phase=1.6), 90),
    ]
    steps = 10
    for k in range(steps):
        d = (k + 1) / steps
        motes = tuple(
            (CX + 7 + (hash01(k, j, 9) - 0.5) * 44, BOTTOM - (BOTTOM - TOP + 10) * d - hash01(j, k, 4) * 18,
             1 + int(hash01(j, k, 2) * 3))
            for j in range(10 + k))
        out.append((replace(b, dx=7, dy=-k * 0.6, sy=1.08, eye=1.6 - 0.1 * k, core=1.4,
                            hand_f=(-28, 14 - k * 0.5), hand_b=(31, 12 - k * 0.5), claw=1.0,
                            phase=1.6 + 0.5 * k, dissolve=d * 0.999 if k < steps - 1 else 1.0,
                            motes=motes), 80))
    out.append((replace(b, dissolve=1.0), 120))
    return out


ANIMATIONS = {
    "idle": (idle_frames, True),
    "attack": (attack_frames, False),
    "hurt": (hurt_frames, False),
    "cast": (cast_frames, False),
    "death": (death_frames, False),
}


# ---------------------------------------------------------------- PNG
def write_png(path: Path, rows) -> None:
    h, w = len(rows), len(rows[0])
    raw = bytearray()
    for row in rows:
        raw.append(0)
        for c in row:
            raw.extend(c if c is not None else (0, 0, 0, 0))

    def chunk(tag, data):
        c = struct.pack(">I", len(data)) + tag + data
        return c + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(bytes(raw), 9)) + chunk(b"IEND", b"")
    path.write_bytes(png)


def build():
    names = list(ANIMATIONS)
    frames = {n: ANIMATIONS[n][0]() for n in names}
    cols = max(len(f) for f in frames.values())
    sheet = [[None] * (CELL_W * cols) for _ in range(CELL_H * len(names))]
    meta = {"cell_w": CELL_W, "cell_h": CELL_H, "columns": cols, "anchor": list(ANCHOR),
            "scale": 2, "sheet": SHEET_PATH.name, "animations": {}}
    for row, name in enumerate(names):
        t = 0.0
        for col, (pose, ms) in enumerate(frames[name]):
            cv = render(pose, t)
            t += ms / 1000
            for y in range(CELL_H):
                sheet[row * CELL_H + y][col * CELL_W:(col + 1) * CELL_W] = cv.px[y]
        meta["animations"][name] = {"row": row, "frames": len(frames[name]),
                                    "durations_ms": [ms for _, ms in frames[name]],
                                    "loop": ANIMATIONS[name][1]}
    return sheet, meta


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    sheet, meta = build()
    write_png(SHEET_PATH, sheet)
    META_PATH.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(f"wrote {SHEET_PATH.relative_to(ROOT)} ({len(sheet[0])}x{len(sheet)}) and {META_PATH.name}")


if __name__ == "__main__":
    main()
