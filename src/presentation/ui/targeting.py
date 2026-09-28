"""Targeting arrow and reticle (Slay the Spire style) in chunky pixel art.

The arrow is a curve of chevron segments from the held card to the pointer,
ending in a big arrowhead. Segments grow toward the head and flow along the
curve. It is pale while it points at nothing and turns red over a valid target.

Performance: every sprite (chevron in 4 sizes, head, 2 colours) is drawn once
at half resolution, doubled with nearest-neighbour (crisp 2 px pixels) and
rotated into 72 cached angle buckets (5° each, nearest-neighbour, so no blur).
Drawing the arrow is ~20 small blits per frame and no per-frame rasterising.
The curve maths are pure functions so they can be tested without a display.
"""
from __future__ import annotations

import math

import pygame

COLD = ((240, 232, 214), (44, 30, 30))    # fill, outline — no target
HOT = ((232, 56, 42), (48, 8, 10))        # over a valid target
RETICLE_ENEMY = (255, 212, 60)
RETICLE_SELF = (120, 210, 255)

SPACING = 26.0         # px between chevrons along the curve
FLOW_SPEED = 70.0      # px per second the chevrons travel toward the head
HEAD_GAP = 44.0        # px kept free behind the head
_ANGLE_STEP = 5
_SIZES = (0.6, 0.78, 0.95, 1.1)
_PIXEL = 2             # sprites are drawn at 1/2 resolution then doubled


# ---------------------------------------------------------------------------
# Geometry (pure)
# ---------------------------------------------------------------------------

def control_point(start: tuple[float, float], end: tuple[float, float]) -> tuple[float, float]:
    """Bend of the arrow: it leaves the card going up and curves toward the target."""
    sx, sy = start
    ex, ey = end
    dx, dy = ex - sx, ey - sy
    return sx + dx * 0.12, sy + dy * 0.95 - abs(dx) * 0.18


def bezier(start, ctrl, end, t: float) -> tuple[float, float]:
    u = 1.0 - t
    return (u * u * start[0] + 2 * u * t * ctrl[0] + t * t * end[0],
            u * u * start[1] + 2 * u * t * ctrl[1] + t * t * end[1])


def sample_curve(start, end, steps: int = 48) -> list[tuple[float, float]]:
    ctrl = control_point(start, end)
    return [bezier(start, ctrl, end, i / steps) for i in range(steps + 1)]


def segment_placements(start, end, phase: float) -> list[tuple[float, float, float, float]]:
    """(x, y, angle_deg, size 0..1) for every chevron, tail first.

    ``phase`` in seconds animates the flow; the angle follows the curve's
    tangent (0° = pointing right, 90° = pointing down, screen coordinates).
    """
    pts = sample_curve(start, end)
    lengths = [0.0]
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        lengths.append(lengths[-1] + math.hypot(x1 - x0, y1 - y0))
    total = lengths[-1]
    usable = total - HEAD_GAP
    if usable <= SPACING * 0.5:
        return []
    out = []
    s = (phase * FLOW_SPEED) % SPACING
    j = 0
    while s < usable:
        while j < len(lengths) - 2 and lengths[j + 1] < s:
            j += 1
        seg = max(1e-6, lengths[j + 1] - lengths[j])
        f = (s - lengths[j]) / seg
        (x0, y0), (x1, y1) = pts[j], pts[j + 1]
        angle = math.degrees(math.atan2(y1 - y0, x1 - x0))
        out.append((x0 + (x1 - x0) * f, y0 + (y1 - y0) * f, angle, s / total))
        s += SPACING
    return out


def head_placement(start, end) -> tuple[float, float, float]:
    """Arrowhead position (the pointer) and angle along the end tangent."""
    ctrl = control_point(start, end)
    px, py = bezier(start, ctrl, end, 0.94)
    return end[0], end[1], math.degrees(math.atan2(end[1] - py, end[0] - px))


# ---------------------------------------------------------------------------
# Sprites (cached)
# ---------------------------------------------------------------------------

_sprite_cache: dict[tuple, pygame.Surface] = {}


def _outlined_polygon(points: list[tuple[float, float]], fill, outline) -> pygame.Surface:
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    w = int(math.ceil(max(xs))) + 3
    h = int(math.ceil(max(ys))) + 3
    small = pygame.Surface((w, h), pygame.SRCALPHA)
    shifted = [(x + 1, y + 1) for x, y in points]
    for ox, oy in ((-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (1, -1), (-1, 1), (1, 1)):
        pygame.draw.polygon(small, outline, [(x + ox, y + oy) for x, y in shifted])
    pygame.draw.polygon(small, fill, shifted)
    return pygame.transform.scale(small, (w * _PIXEL, h * _PIXEL))


def _chevron_points(k: float) -> list[tuple[float, float]]:
    """A thick '>' pointing right, native half-resolution units."""
    L, H, T = 9 * k, 7 * k, 4 * k
    return [(0, 0), (T, 0), (L, H), (T, 2 * H), (0, 2 * H), (L - T, H)]


def _head_points() -> list[tuple[float, float]]:
    return [(0, 0), (22, 13), (0, 26), (6, 13)]


def _sprite(kind: str, size_idx: int, hot: bool, angle_deg: float) -> pygame.Surface:
    bucket = int(round(angle_deg / _ANGLE_STEP)) % (360 // _ANGLE_STEP)
    key = (kind, size_idx, hot, bucket)
    cached = _sprite_cache.get(key)
    if cached is not None:
        return cached
    base_key = (kind, size_idx, hot, None)
    base = _sprite_cache.get(base_key)
    if base is None:
        fill, outline = HOT if hot else COLD
        pts = _head_points() if kind == "head" else _chevron_points(_SIZES[size_idx])
        base = _outlined_polygon(pts, fill, outline)
        _sprite_cache[base_key] = base
    # pygame rotates counter-clockwise; screen angles grow clockwise
    rotated = pygame.transform.rotate(base, -bucket * _ANGLE_STEP)
    _sprite_cache[key] = rotated
    return rotated


# ---------------------------------------------------------------------------
# Drawing
# ---------------------------------------------------------------------------

def draw_arrow(surface: pygame.Surface, start: tuple[float, float], end: tuple[float, float],
               *, hot: bool, phase: float) -> int:
    """Draw the arrow; returns the number of blits (for budgets/tests)."""
    blits = 0
    for x, y, angle, t in segment_placements(start, end, phase):
        idx = min(len(_SIZES) - 1, int(t * len(_SIZES)))
        spr = _sprite("chevron", idx, hot, angle)
        surface.blit(spr, spr.get_rect(center=(round(x), round(y))))
        blits += 1
    hx, hy, angle = head_placement(start, end)
    head = _sprite("head", 0, hot, angle)
    # the tip sits on the pointer: move the sprite centre back along the tangent
    back = 22 * _PIXEL * 0.45
    cx = hx - math.cos(math.radians(angle)) * back
    cy = hy - math.sin(math.radians(angle)) * back
    surface.blit(head, head.get_rect(center=(round(cx), round(cy))))
    return blits + 1


def draw_reticle(surface: pygame.Surface, rect: pygame.Rect, color, t: float) -> None:
    """Four pixel-art corner brackets that breathe in and out around ``rect``."""
    pulse = 5 + round(3 * math.sin(t * 6.0))
    r = rect.inflate(pulse * 2, pulse * 2)
    arm = max(10, min(r.w, r.h) // 5)
    thick = 4
    dark = (20, 12, 8)
    for cx, cy, sx, sy in ((r.left, r.top, 1, 1), (r.right, r.top, -1, 1),
                           (r.left, r.bottom, 1, -1), (r.right, r.bottom, -1, -1)):
        x0 = cx if sx > 0 else cx - thick
        y0 = cy if sy > 0 else cy - thick
        hx = cx if sx > 0 else cx - arm
        vy = cy if sy > 0 else cy - arm
        for col, grow in ((dark, 2), (color, 0)):
            surface.fill(col, pygame.Rect(hx - grow // 2, y0 - grow // 2, arm + grow, thick + grow))
            surface.fill(col, pygame.Rect(x0 - grow // 2, vy - grow // 2, thick + grow, arm + grow))
