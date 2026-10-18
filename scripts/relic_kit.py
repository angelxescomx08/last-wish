"""Drawing helpers for the code-drawn relic sprites (``scripts/relic_art.py``). Stdlib only.

Same rules as every sprite of the game (``docs/code-drawn-sprites.md``): native pixels on a
32×32 canvas (shown ×2 or more, nearest), shaded ramps with the light from the upper left,
ordered dither, and the dark outline added last. Shapes are "inside" functions
``f(x, y) -> bool`` evaluated at pixel centres, so they combine with ``union`` / ``minus``.
"""
from __future__ import annotations

import math

from pixel_kit import Canvas, outline, ramp

SIZE = 32
INK = (22, 14, 26)

# Ramps, dark → light (same family as the UI icons).
STEEL = [(52, 58, 78), (92, 102, 128), (150, 162, 186), (210, 220, 236), (250, 252, 255)]
IRON = [(40, 40, 48), (70, 72, 84), (110, 112, 126), (160, 162, 176), (205, 208, 220)]
GOLD = [(96, 58, 20), (168, 112, 34), (226, 172, 58), (255, 226, 120), (255, 248, 200)]
SILVER = [(70, 76, 96), (124, 132, 154), (184, 192, 210), (228, 234, 244), (255, 255, 255)]
BRONZE = [(70, 40, 20), (124, 74, 36), (178, 116, 58), (222, 162, 96), (250, 210, 150)]
WOOD = [(46, 26, 16), (82, 50, 28), (122, 80, 44), (162, 112, 64), (196, 148, 94)]
LEATHER = [(50, 28, 20), (90, 52, 32), (134, 84, 50), (176, 120, 76), (210, 160, 112)]
CLOTH_RED = [(70, 12, 20), (128, 24, 34), (186, 44, 50), (226, 90, 80), (250, 150, 130)]
RED = [(92, 18, 26), (160, 34, 40), (220, 66, 58), (255, 132, 104), (255, 204, 170)]
BLOOD = [(60, 6, 14), (110, 14, 26), (168, 24, 36), (214, 52, 56), (246, 112, 104)]
BLUE = [(26, 44, 96), (44, 86, 168), (80, 140, 224), (150, 200, 255), (224, 244, 255)]
CYAN = [(24, 70, 86), (40, 120, 140), (86, 186, 200), (170, 236, 240), (236, 255, 255)]
ICE = [(40, 90, 130), (90, 160, 210), (160, 215, 245), (215, 245, 255), (255, 255, 255)]
GREEN = [(22, 70, 30), (44, 128, 46), (98, 194, 70), (176, 240, 120), (232, 255, 200)]
POISON = [(20, 56, 24), (40, 104, 34), (84, 168, 48), (150, 222, 80), (214, 252, 150)]
VIOLET = [(54, 26, 84), (98, 48, 150), (150, 86, 210), (204, 150, 250), (240, 214, 255)]
ORANGE = [(110, 40, 16), (186, 78, 24), (240, 132, 40), (255, 196, 96), (255, 238, 190)]
FIRE = [(120, 24, 10), (200, 60, 16), (248, 128, 32), (255, 200, 80), (255, 248, 200)]
BONE = [(92, 82, 70), (150, 138, 118), (206, 196, 176), (246, 240, 226), (255, 255, 250)]
STONE = [(48, 46, 52), (82, 80, 88), (124, 120, 128), (168, 164, 170), (210, 206, 210)]
EARTH = [(56, 36, 20), (98, 66, 36), (144, 102, 58), (188, 146, 92), (222, 190, 138)]
PAPER = [(120, 100, 70), (176, 154, 112), (222, 204, 160), (244, 232, 196), (255, 250, 230)]
PINK = [(110, 30, 70), (170, 60, 110), (226, 110, 160), (250, 170, 200), (255, 220, 236)]
BLACK = [(14, 12, 20), (30, 26, 40), (50, 44, 64), (78, 70, 96), (110, 100, 130)]
GLASS = [(40, 70, 90), (80, 130, 160), (150, 200, 220), (210, 240, 250), (255, 255, 255)]
WHITE = (255, 255, 255)


# --- shapes ----------------------------------------------------------------------------

def circle(cx, cy, r):
    return lambda x, y: (x - cx) ** 2 + (y - cy) ** 2 <= r * r


def ellipse(cx, cy, rx, ry):
    return lambda x, y: ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2 <= 1.0


def rect(x0, y0, x1, y1):
    return lambda x, y: x0 <= x <= x1 and y0 <= y <= y1


def ring(cx, cy, r_out, r_in):
    return lambda x, y: r_in * r_in < (x - cx) ** 2 + (y - cy) ** 2 <= r_out * r_out


def poly(points):
    """Point-in-polygon (even-odd) for a list of (x, y)."""
    pts = list(points)

    def inside(x, y):
        hit = False
        j = len(pts) - 1
        for i in range(len(pts)):
            xi, yi = pts[i]
            xj, yj = pts[j]
            if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi + 1e-9) + xi:
                hit = not hit
            j = i
        return hit
    return inside


def capsule(x0, y0, x1, y1, r):
    """A thick segment with round ends."""
    def inside(x, y):
        dx, dy = x1 - x0, y1 - y0
        t = max(0.0, min(1.0, ((x - x0) * dx + (y - y0) * dy) / (dx * dx + dy * dy + 1e-9)))
        px, py = x0 + t * dx, y0 + t * dy
        return (x - px) ** 2 + (y - py) ** 2 <= r * r
    return inside


def union(*shapes):
    return lambda x, y: any(s(x, y) for s in shapes)


def minus(a, *b):
    return lambda x, y: a(x, y) and not any(s(x, y) for s in b)


def rotate(shape, cx, cy, deg):
    """The shape turned ``deg`` degrees (clockwise on screen) around (cx, cy)."""
    c, s = math.cos(math.radians(-deg)), math.sin(math.radians(-deg))

    def inside(x, y):
        dx, dy = x - cx, y - cy
        return shape(cx + dx * c - dy * s, cy + dx * s + dy * c)
    return inside


# --- painting ----------------------------------------------------------------------------

def bounds(shape, w=SIZE, h=SIZE):
    xs, ys = [], []
    for y in range(h):
        for x in range(w):
            if shape(x + 0.5, y + 0.5):
                xs.append(x)
                ys.append(y)
    if not xs:
        return 0, 0, 1, 1
    return min(xs), min(ys), max(xs) + 1, max(ys) + 1


def fill(cv: Canvas, shape, colors, *, base: float = 0.55, slope: float = 0.6, rim: bool = True,
         dither: float = 0.5, solid: bool = True) -> None:
    """Fill ``shape`` with ``colors``: light from the upper left across the shape's box,
    darker rim on the lower-right edge and lighter on the upper-left one."""
    x0, y0, x1, y1 = bounds(shape, cv.w, cv.h)
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    r = max(1.0, max(x1 - x0, y1 - y0) / 2)
    for y in range(cv.h):
        for x in range(cv.w):
            px, py = x + 0.5, y + 0.5
            if not shape(px, py):
                continue
            light = base - slope * 0.5 * ((px - cx) / r + (py - cy) / r)
            if rim:
                edge = [shape(px + dx, py + dy) for dx, dy in ((1, 0), (0, 1), (-1, 0), (0, -1))]
                if not (edge[0] and edge[1]):
                    light -= 0.3
                elif not (edge[2] and edge[3]):
                    light += 0.15
            cv.put(x, y, ramp(colors, max(0.0, min(1.0, light)), x, y, dither), solid=solid)


def flat(cv: Canvas, shape, color, *, solid: bool = True) -> None:
    for y in range(cv.h):
        for x in range(cv.w):
            if shape(x + 0.5, y + 0.5):
                cv.put(x, y, color, solid=solid)


def line(cv: Canvas, x0, y0, x1, y1, color, *, solid: bool = True) -> None:
    n = int(max(abs(x1 - x0), abs(y1 - y0))) + 1
    for i in range(n + 1):
        t = i / max(1, n)
        cv.put(round(x0 + (x1 - x0) * t), round(y0 + (y1 - y0) * t), color, solid=solid)


def dots(cv: Canvas, points, color) -> None:
    for x, y in points:
        cv.put(x, y, color)


def sparkle(cv: Canvas, x: int, y: int, color=WHITE, size: int = 1) -> None:
    """A tiny four-point glint (drawn without outline)."""
    cv.put(x, y, color, solid=False)
    for k in range(1, size + 1):
        for dx, dy in ((k, 0), (-k, 0), (0, k), (0, -k)):
            cv.put(x + dx, y + dy, color, solid=False, alpha=200 - 60 * k)


def shine(cv: Canvas, shape, color=WHITE, k: float = 0.5) -> None:
    """Tint the upper-left inner edge of a shape (a specular streak)."""
    for y in range(cv.h):
        for x in range(cv.w):
            px, py = x + 0.5, y + 0.5
            if shape(px, py) and not shape(px - 1.5, py - 1.5):
                cv.tint(x, y, color, k)


def new() -> Canvas:
    return Canvas(SIZE, SIZE)


def finish(cv: Canvas) -> Canvas:
    """The dark outline around every solid pixel."""
    outline(cv, INK)
    return cv
