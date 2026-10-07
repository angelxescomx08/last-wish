"""Shared pixel-art helpers for code-drawn sprites (standard library only).

The same toolbox as ``generate_enemy_sprites.py`` (the approved "Espectro"
method, see ``docs/code-drawn-sprites.md``) with the canvas size as a
parameter, so bigger creatures (the floor-1 bosses) can reuse it:

* ``Canvas(w, h)``: RGBA pixels + a "solid" mask (only solid pixels get the
  outline), ``put`` with alpha, ``glow`` (soft baked light), ``blit``.
* ``bayer`` (4×4 ordered dither), ``hash01`` (stable noise), ``mix``, ``ramp``
  (pick a colour from a ramp with dither), ``outline``, ``flash``, ``dissolve``.
* ``bezier``, ``stroke`` (tapered shaded tube along a polyline, drawn on its own
  canvas and rimmed where it crosses the body — the Espectro sleeve rule).
* ``write_png`` and ``build_sheet`` (rows = animations, JSON meta with cell
  size, anchor, scale, durations, loop flags and optional events).
"""
from __future__ import annotations

import json
import math
import struct
import zlib
from pathlib import Path
from typing import Callable, Iterable

BAYER = [[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]]
WHITE = (255, 255, 255)


def bayer(x: int, y: int) -> float:
    return (BAYER[y & 3][x & 3] + 0.5) / 16.0


def hash01(x: int, y: int, s: int = 0) -> float:
    h = (x * 374761393 + y * 668265263 + s * 2147483647) & 0xFFFFFFFF
    h = ((h ^ (h >> 13)) * 1274126177) & 0xFFFFFFFF
    return ((h ^ (h >> 16)) & 0xFFFF) / 65535.0


def mix(a, b, k: float):
    k = max(0.0, min(1.0, k))
    return tuple(int(round(a[i] + (b[i] - a[i]) * k)) for i in range(3))


def ramp(colors, light: float, x: int, y: int, dither: float = 0.55):
    """Colour of a ramp for ``light`` 0..1 with ordered dither (amplitude ``dither`` steps)."""
    level = light * (len(colors) - 1) + (bayer(x, y) - 0.5) * dither
    return colors[max(0, min(len(colors) - 1, int(round(level))))]


def smooth(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


class Canvas:
    def __init__(self, w: int, h: int) -> None:
        self.w, self.h = w, h
        self.px = [[None] * w for _ in range(h)]
        self.solid = [[False] * w for _ in range(h)]

    def inside(self, x: int, y: int) -> bool:
        return 0 <= x < self.w and 0 <= y < self.h

    def put(self, x: int, y: int, c, *, solid: bool = True, alpha: int = 255) -> None:
        x, y = int(x), int(y)
        if not (0 <= x < self.w and 0 <= y < self.h):
            return
        if alpha >= 255:
            self.px[y][x] = (*c[:3], 255)
        else:
            old = self.px[y][x]
            if old is None:
                self.px[y][x] = (*c[:3], max(0, alpha))
            else:
                self.px[y][x] = (*mix(old[:3], c, alpha / 255), max(old[3], alpha))
        if solid:
            self.solid[y][x] = True

    def get(self, x: int, y: int):
        if 0 <= x < self.w and 0 <= y < self.h:
            return self.px[y][x]
        return None

    def tint(self, x: int, y: int, c, k: float) -> None:
        """Shift an existing pixel towards ``c`` (no-op on empty pixels)."""
        old = self.get(int(x), int(y))
        if old is not None:
            self.px[int(y)][int(x)] = (*mix(old[:3], c, k), old[3])

    def glow(self, cx: float, cy: float, radius: float, color, strength: float,
             halo: bool = True) -> None:
        """Soft light: brightens existing pixels, adds faint colour around them."""
        if strength <= 0 or radius <= 0:
            return
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
                    if halo and k > 0.18:
                        self.put(x, y, color, solid=False, alpha=int(min(200, 255 * k)))
                else:
                    self.px[y][x] = (*mix(old[:3], color, min(0.85, k)), old[3])

    def blit(self, other: "Canvas", rim=None) -> None:
        """Copy ``other`` on top; ``rim`` paints a dark edge where it crosses existing pixels."""
        if rim is not None:
            for y in range(self.h):
                row, orow = self.px[y], other.px[y]
                for x in range(self.w):
                    if orow[x] is None and row[x] is not None:
                        for ox, oy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                            if other.get(x + ox, y + oy) is not None and other.solid[y + oy][x + ox]:
                                self.put(x, y, rim)
                                break
        for y in range(self.h):
            for x in range(self.w):
                c = other.px[y][x]
                if c is not None:
                    self.put(x, y, c[:3], solid=other.solid[y][x], alpha=c[3])


def outline(cv: Canvas, color) -> None:
    add = []
    for y in range(cv.h):
        for x in range(cv.w):
            if cv.px[y][x] is not None:
                continue
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nx, ny = x + dx, y + dy
                if 0 <= nx < cv.w and 0 <= ny < cv.h and cv.solid[ny][nx]:
                    add.append((x, y))
                    break
    for x, y in add:
        cv.px[y][x] = (*color, 255)


def flash(cv: Canvas, k: float) -> None:
    if k <= 0:
        return
    for y in range(cv.h):
        for x in range(cv.w):
            c = cv.px[y][x]
            if c is not None and cv.solid[y][x]:
                cv.px[y][x] = (*mix(c[:3], WHITE, k), c[3])


def dissolve(cv: Canvas, d: float, top: float, bottom: float, edge_hot, edge_warm,
             *, upward: bool = True, seed: int = 3) -> None:
    """Burn the sprite away past a noisy front; the front glows ``edge_hot``/``edge_warm``.

    ``upward=True``: the front climbs from ``bottom`` to ``top`` (pixels below it vanish).
    ``upward=False``: it falls from ``top`` to ``bottom`` (pixels above it vanish).
    """
    if d <= 0:
        return
    span = bottom - top + 12
    for y in range(cv.h):
        for x in range(cv.w):
            c = cv.px[y][x]
            if c is None:
                continue
            n = (hash01(x, y, seed) - 0.5) * 12
            if upward:
                front = bottom + 6 - span * d + n
                gone, dist = y > front, front - y
            else:
                front = top - 6 + span * d + n
                gone, dist = y < front, y - front
            if gone:
                cv.px[y][x] = None
            elif dist < 2.5:
                cv.px[y][x] = (*(edge_hot if hash01(x, y, 5) > 0.5 else edge_warm), 255)
            elif dist < 5:
                cv.px[y][x] = (*mix(c[:3], edge_warm, 0.55), c[3])


def bezier(p0, p1, p2, steps: int):
    out = []
    for i in range(steps):
        t = i / max(1, steps - 1)
        out.append(((1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * p1[0] + t * t * p2[0],
                    (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * p1[1] + t * t * p2[1]))
    return out


def polyline(points, step: float = 0.6):
    """Evenly resampled points along a polyline."""
    out = [points[0]]
    for (x0, y0), (x1, y1) in zip(points, points[1:]):
        n = max(1, int(math.hypot(x1 - x0, y1 - y0) / step))
        for i in range(1, n + 1):
            out.append((x0 + (x1 - x0) * i / n, y0 + (y1 - y0) * i / n))
    return out


def stroke(cv: Canvas, pts, radius: Callable[[float], float], colors,
           *, light_dir=(-0.7, -0.7), shade: float = 0.0, solid: bool = True,
           rim=None, dither: float = 0.6, min_r: float = 0.7) -> Canvas:
    """A shaded tube along ``pts`` (radius by t 0..1), drawn on its own canvas then copied.

    Every pixel takes the sample of the axis it is closest to (relative to the local
    radius), so the tube is smooth (no "beads"). Lit from ``light_dir`` (upper left by
    default). With ``rim`` a dark edge is painted where it crosses existing pixels.
    Returns the tube's own canvas.
    """
    tube = Canvas(cv.w, cv.h)
    pts = polyline(list(pts), 0.5) if len(pts) > 1 else list(pts)    # dense: no gaps
    n = len(pts)
    lx, ly = light_dir
    best: dict[tuple[int, int], tuple[float, float, float]] = {}
    for i, (x, y) in enumerate(pts):
        t = i / max(1, n - 1)
        r = max(min_r, radius(t))
        for yy in range(int(y - r) - 1, int(y + r) + 2):
            for xx in range(int(x - r) - 1, int(x + r) + 2):
                dx, dy = xx + 0.5 - x, yy + 0.5 - y
                d = math.hypot(dx, dy) / r
                if d > 1:
                    continue
                key = (xx, yy)
                if key not in best or d < best[key][0]:
                    best[key] = (d, (dx * lx + dy * ly) / r, t)
    for (xx, yy), (d, side, t) in best.items():
        light = 0.55 + 0.42 * side - 0.22 * d * d + shade
        tube.put(xx, yy, ramp(colors, max(0.0, min(1.0, light)), xx, yy, dither), solid=solid)
    cv.blit(tube, rim=rim)
    return tube


# ---------------------------------------------------------------- PNG + sheet
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


def build_sheet(animations: dict, render: Callable, cell: tuple[int, int], anchor: tuple[int, int],
                sheet_name: str, extra_meta: dict | None = None):
    """Render every animation (``{name: (frames_fn, loop)}``) into one sheet + meta dict."""
    cw, ch = cell
    names = list(animations)
    frames = {n: animations[n][0]() for n in names}
    cols = max(len(f) for f in frames.values())
    sheet = [[None] * (cw * cols) for _ in range(ch * len(names))]
    meta = {"cell_w": cw, "cell_h": ch, "columns": cols, "anchor": list(anchor), "scale": 2,
            "sheet": sheet_name, "animations": {}}
    for row, name in enumerate(names):
        t = 0.0
        for col, (pose, ms) in enumerate(frames[name]):
            cv = render(pose, t)
            t += ms / 1000
            for y in range(ch):
                sheet[row * ch + y][col * cw:(col + 1) * cw] = cv.px[y]
        meta["animations"][name] = {"row": row, "frames": len(frames[name]),
                                    "durations_ms": [ms for _, ms in frames[name]],
                                    "loop": animations[name][1]}
    if extra_meta:
        meta.update(extra_meta)
    return sheet, meta


def save_sheet(out_dir: Path, sheet_id: str, sheet, meta) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    write_png(out_dir / f"{sheet_id}_sheet.png", sheet)
    (out_dir / f"{sheet_id}_sheet.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")


def bbox(cv: Canvas):
    """(x0, y0, x1, y1) of the non-empty pixels, or None."""
    xs, ys = [], []
    for y in range(cv.h):
        for x in range(cv.w):
            if cv.px[y][x] is not None and cv.px[y][x][3] > 0:
                xs.append(x)
                ys.append(y)
    if not xs:
        return None
    return min(xs), min(ys), max(xs), max(ys)


def opaque_count(cv: Canvas) -> int:
    return sum(1 for row in cv.px for c in row if c is not None and c[3] > 0)


def frames_of(fn: Callable[[], Iterable]):
    return list(fn())
