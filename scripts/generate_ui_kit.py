"""Pixel-art HUD kit: frames, buttons, mana orb, card piles, top bar (``assets/ui/kit.png`` + ``kit.json``).

The same language as the dungeon and the gachapón (native pixels shown ×2,
ramps with upper-left light, ordered dither, dark ``INK`` outline):

* ``panel`` — 9-slice frame of dark iron with gold rivets and a slate inside.
* ``btn_<style>_<state>`` — 3-slice buttons (fixed native height, the middle
  column tiles): styles ``bronze`` (18 px) and ``gold`` (24 px, End Turn),
  states ``idle`` / ``hover`` / ``press`` / ``off``.
* ``orb_back`` / ``orb_frame`` / ``orb_glass`` / ``orb_liquid_0..7`` — the mana orb
  (48×48): dark glass, metal ring with four crystal studs, glass highlight and
  8 frames of swirling liquid (the runtime cuts it at the mana level).
* ``pile_draw`` / ``pile_discard`` / ``pile_empty`` — card stacks for the piles.
* ``topbar`` — tile for the top bar (34 px: iron plate + gold trim);
  ``trim`` — the gold edge alone (for the hand area); ``ribbon`` — 3-slice red
  ribbon for the turn counter.

The JSON maps each name to ``{"rect": [x, y, w, h], "slice": [left, top, right, bottom]}``
(``slice`` only on stretchable pieces). Standard library only:
``python scripts/generate_ui_kit.py``.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from pixel_kit import Canvas, bayer, hash01, mix, ramp, write_png  # noqa: E402

OUT = Path(__file__).parent.parent / "assets" / "ui"
INK = (14, 10, 18)

IRON = [(30, 30, 42), (52, 52, 70), (82, 84, 104), (124, 128, 150), (176, 182, 204)]
GOLD = [(84, 50, 18), (150, 100, 32), (212, 160, 56), (250, 214, 112), (255, 246, 196)]
BRONZE = [(70, 40, 22), (120, 74, 36), (172, 116, 56), (220, 168, 96), (250, 222, 160)]
SLATE = [(16, 14, 24), (22, 20, 32), (30, 27, 42), (40, 36, 54)]
WINE = [(40, 14, 22), (66, 24, 32), (96, 36, 44), (132, 54, 58), (176, 84, 80)]
AMBER = [(92, 44, 10), (150, 78, 18), (206, 124, 34), (246, 178, 64), (255, 226, 140)]
GREY = [(34, 34, 40), (56, 56, 64), (84, 84, 94), (120, 120, 130), (160, 160, 170)]
MANA = [(10, 20, 64), (18, 46, 128), (34, 92, 200), (78, 156, 246), (160, 214, 255), (232, 248, 255)]
CRIMSON = [(70, 12, 20), (118, 22, 32), (168, 38, 44), (210, 70, 66)]
CARD_BLUE = [(18, 24, 60), (30, 44, 104), (48, 70, 150), (80, 108, 196)]
CARD_RED = [(48, 16, 20), (84, 28, 30), (120, 44, 40), (160, 70, 58)]


# ---------------------------------------------------------------- frames and buttons

def bevel_frame(cv: Canvas, x0: int, y0: int, x1: int, y1: int, colors, width: int,
                *, inverted: bool = False) -> None:
    """A ``width``-px bevelled frame on [x0, x1) × [y0, y1): light top-left, dark bottom-right."""
    for y in range(y0, y1):
        for x in range(x0, x1):
            d = min(x - x0, y - y0, x1 - 1 - x, y1 - 1 - y)
            if d >= width:
                continue
            if d == 0:
                cv.put(x, y, INK)
                continue
            top_left = (x - x0) + (y - y0) < (x1 - 1 - x) + (y1 - 1 - y)
            if inverted:
                top_left = not top_left
            light = 0.78 if top_left else 0.3
            if d == width - 1:
                light -= 0.25                       # inner shadow line
            cv.put(x, y, ramp(colors, light, x, y, 0.35))


def rivet(cv: Canvas, x: int, y: int) -> None:
    cv.put(x, y, GOLD[3])
    cv.put(x + 1, y, GOLD[2])
    cv.put(x, y + 1, GOLD[2])
    cv.put(x + 1, y + 1, GOLD[0])


def panel() -> Canvas:
    cv = Canvas(24, 24)
    for y in range(24):
        for x in range(24):
            n = hash01(x, y, 5)
            cv.put(x, y, SLATE[2] if n > 0.86 else SLATE[1] if n > 0.25 else SLATE[0] if n < 0.06 else SLATE[1])
    bevel_frame(cv, 0, 0, 24, 24, IRON, 4)
    for x, y in ((1, 1), (21, 1), (1, 21), (21, 21)):
        rivet(cv, x, y)
    for x in range(4, 20):                          # thin gold line inside the top edge
        cv.put(x, 4, mix(SLATE[1], GOLD[1], 0.55))
    return cv


BUTTON_STYLES = {
    "bronze": (BRONZE, WINE, 18),
    "gold": (GOLD, AMBER, 24),
}


def button(style: str, state: str) -> Canvas:
    frame_col, inner, height = BUTTON_STYLES[style]
    if state == "off":
        frame_col, inner = GREY, [GREY[0], GREY[1], GREY[1], GREY[2], GREY[3]]
    w = 24
    cv = Canvas(w, height)
    lift = {"idle": 0.0, "hover": 0.16, "press": -0.18, "off": -0.1}[state]
    for y in range(height):
        t = y / (height - 1)
        for x in range(w):
            light = 0.78 - 0.55 * t + lift            # vertical gradient, light from above
            if state == "press":
                light = 0.25 + 0.3 * t + lift          # pressed: lit from below
            cv.put(x, y, ramp(inner, max(0.0, min(1.0, light)), x, y, 0.5))
    if state != "press":                              # a soft glassy highlight band
        for x in range(3, w - 3):
            cv.put(x, 3, mix(cv.get(x, 3)[:3], (255, 255, 255), 0.25 + (0.1 if state == "hover" else 0)))
    bevel_frame(cv, 0, 0, w, height, frame_col, 3, inverted=state == "press")
    for x, y in ((1, 1), (w - 3, 1), (1, height - 3), (w - 3, height - 3)):
        if state != "off":
            rivet(cv, x, y)
    return cv


# ---------------------------------------------------------------- mana orb

ORB = 48
ORB_C = 23.5
ORB_R_IN = 18.5
ORB_R_OUT = 23.0


def orb_back() -> Canvas:
    cv = Canvas(ORB, ORB)
    for y in range(ORB):
        for x in range(ORB):
            d = math.hypot(x + 0.5 - ORB_C, y + 0.5 - ORB_C)
            if d <= ORB_R_IN:
                k = 0.15 + 0.25 * (1 - d / ORB_R_IN)
                cv.put(x, y, ramp([(6, 8, 18), (12, 16, 34), (20, 26, 52)], k * 2, x, y, 0.6))
    return cv


def orb_frame() -> Canvas:
    cv = Canvas(ORB, ORB)
    for y in range(ORB):
        for x in range(ORB):
            dx, dy = x + 0.5 - ORB_C, y + 0.5 - ORB_C
            d = math.hypot(dx, dy)
            if ORB_R_IN < d <= ORB_R_OUT:
                if d > ORB_R_OUT - 0.9 or d < ORB_R_IN + 0.7:
                    cv.put(x, y, INK)
                    continue
                light = 0.55 - 0.4 * (dx + dy) / (d * 1.4142)
                rune = (math.degrees(math.atan2(dy, dx)) % 30) < 4
                cv.put(x, y, ramp(GOLD if rune else IRON, max(0.0, min(1.0, light)), x, y, 0.4))
    for ang in (90, 210, 330):                         # three crystal studs
        a = math.radians(ang)
        sx, sy = ORB_C + math.cos(a) * 21, ORB_C - math.sin(a) * 21
        for y in range(int(sy) - 3, int(sy) + 4):
            for x in range(int(sx) - 3, int(sx) + 4):
                d = abs(x + 0.5 - sx) + abs(y + 0.5 - sy)
                if d <= 3.2:
                    cv.put(x, y, INK if d > 2.4 else ramp(MANA, 0.9 - 0.25 * (x - sx + y - sy), x, y, 0.3))
    return cv


def orb_glass() -> Canvas:
    cv = Canvas(ORB, ORB)
    for y in range(ORB):
        for x in range(ORB):
            dx, dy = x + 0.5 - ORB_C, y + 0.5 - ORB_C
            d = math.hypot(dx, dy)
            if d > ORB_R_IN - 1:
                continue
            ang = math.degrees(math.atan2(dy, dx))
            if 13.5 < d < 16.5 and -165 < ang < -105:      # curved reflection, upper-left
                cv.put(x, y, (255, 255, 255), solid=False, alpha=120 if bayer(x, y) > 0.3 else 60)
            elif math.hypot(dx + 7, dy + 8) < 2.2:
                cv.put(x, y, (255, 255, 255), solid=False, alpha=190)
            elif d > ORB_R_IN - 2.2 and dx + dy > 8:
                cv.put(x, y, (0, 0, 0), solid=False, alpha=90)  # inner shade, lower-right
    return cv


def orb_liquid(frame: int, frames: int = 8) -> Canvas:
    cv = Canvas(ORB, ORB)
    phase = frame / frames * math.tau
    for y in range(ORB):
        for x in range(ORB):
            dx, dy = x + 0.5 - ORB_C, y + 0.5 - ORB_C
            d = math.hypot(dx, dy)
            if d > ORB_R_IN:
                continue
            swirl = math.sin(math.atan2(dy, dx) * 2 + d * 0.35 - phase) * 0.5 + 0.5
            light = 0.35 + 0.35 * swirl - 0.25 * (dx + dy) / ORB_R_IN * 0.7 - 0.15 * (d / ORB_R_IN) ** 3
            cv.put(x, y, ramp(MANA, max(0.0, min(1.0, light)), x, y, 0.6))
    for k in range(5):                                  # drifting motes inside the liquid
        a = phase + k * 1.3
        r = 4 + 3 * k % 12
        px, py = ORB_C + math.cos(a) * r, ORB_C + math.sin(a * 0.7) * r * 0.8
        cv.put(int(px), int(py), MANA[5])
    return cv


# ---------------------------------------------------------------- piles, bars, ribbon

def _card_back(cv: Canvas, ox: int, oy: int, w: int, h: int, colors, tilt: int = 0) -> None:
    for y in range(h):
        shift = (tilt * y) // h
        for x in range(w):
            px, py = ox + x + shift, oy + y
            edge = x in (0, w - 1) or y in (0, h - 1)
            if edge:
                cv.put(px, py, INK)
            elif x in (1, w - 2) or y in (1, h - 2):
                cv.put(px, py, GOLD[1] if (x + y) % 2 else GOLD[2])
            else:
                diamond = abs(x - w / 2 + 0.5) / (w / 2 - 2) + abs(y - h / 2 + 0.5) / (h / 2 - 2)
                if 0.55 < diamond < 0.72:
                    cv.put(px, py, GOLD[2])
                else:
                    cv.put(px, py, ramp(colors, 0.75 - 0.5 * (x + y) / (w + h), px, py, 0.5))


def pile(kind: str) -> Canvas:
    cv = Canvas(34, 40)
    if kind == "empty":
        for y in range(4, 38):
            for x in range(4, 30):
                if (x in (4, 29) or y in (4, 37)) and (x + y) % 3:
                    cv.put(x, y, GREY[2])
        return cv
    colors = CARD_BLUE if kind == "draw" else CARD_RED
    offsets = ((6, 2, 0), (4, 4, 0), (2, 6, 0)) if kind == "draw" else ((7, 3, 3), (1, 5, -2), (4, 6, 0))
    for ox, oy, tilt in offsets:
        _card_back(cv, ox, oy, 24, 32, colors, tilt)
    return cv


def topbar() -> Canvas:
    w, h = 32, 34
    cv = Canvas(w, h)
    for y in range(h):
        for x in range(w):
            if y < 29:
                n = hash01(x, y, 11)
                base = 0.25 + 0.35 * (y / 29) + (0.12 if n > 0.9 else 0)
                c = ramp(SLATE, base, x, y, 0.6)
                if x == 0:
                    c = SLATE[0]                        # plate seam every tile
                elif x == 1:
                    c = SLATE[3]
                cv.put(x, y, c)
            elif y == 29:
                cv.put(x, y, GOLD[3] if x % 8 else GOLD[4])
            elif y == 30:
                cv.put(x, y, GOLD[2])
            elif y == 31:
                cv.put(x, y, GOLD[0])
            else:
                cv.put(x, y, INK, alpha=200 if y == 32 else 110)
    for x in (4, 20):
        rivet(cv, x, 24)
    return cv


def trim() -> Canvas:
    cv = Canvas(32, 4)
    for x in range(32):
        cv.put(x, 0, INK, alpha=120)
        cv.put(x, 1, GOLD[0])
        cv.put(x, 2, GOLD[2])
        cv.put(x, 3, GOLD[3] if x % 8 else GOLD[4])
    return cv


def ribbon() -> Canvas:
    w, h = 24, 16
    cv = Canvas(w, h)
    for y in range(2, h - 2):
        for x in range(w):
            if x < 6 and abs(y - h / 2 + 0.5) > (x + 1.5) * 0.9 + 1:   # swallow-tail notch, left
                continue
            if x >= w - 6 and abs(y - h / 2 + 0.5) > (w - x + 0.5) * 0.9 + 1:
                continue
            light = 0.8 - 0.6 * (y - 2) / (h - 5)
            cv.put(x, y, ramp(CRIMSON, light, x, y, 0.5))
    for x in range(6, w - 6):
        cv.put(x, 2, GOLD[2])
        cv.put(x, h - 3, GOLD[1])
    for y in range(h):                                  # dark outline around the shape
        for x in range(w):
            if cv.get(x, y) is None and any(cv.get(x + dx, y + dy) is not None and cv.solid[y + dy][x + dx]
                                            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
                                            if 0 <= x + dx < w and 0 <= y + dy < h):
                cv.put(x, y, INK, solid=False)
    return cv


# ---------------------------------------------------------------- sheet

def pieces() -> list[tuple[str, Canvas, list[int] | None]]:
    out: list[tuple[str, Canvas, list[int] | None]] = [("panel", panel(), [8, 8, 8, 8])]
    for style in BUTTON_STYLES:
        for state in ("idle", "hover", "press", "off"):
            out.append((f"btn_{style}_{state}", button(style, state), [7, 0, 7, 0]))
    out += [("orb_back", orb_back(), None), ("orb_frame", orb_frame(), None), ("orb_glass", orb_glass(), None)]
    out += [(f"orb_liquid_{i}", orb_liquid(i), None) for i in range(8)]
    out += [("pile_draw", pile("draw"), None), ("pile_discard", pile("discard"), None),
            ("pile_empty", pile("empty"), None)]
    out += [("topbar", topbar(), None), ("trim", trim(), None), ("ribbon", ribbon(), [7, 0, 7, 0])]
    return out


def build() -> tuple[list, dict]:
    items = pieces()
    width = 512
    x = y = row_h = 0
    placed = []
    for name, cv, sl in items:                       # simple shelf packing
        if x + cv.w > width:
            x, y, row_h = 0, y + row_h + 1, 0
        placed.append((name, cv, sl, x, y))
        x += cv.w + 1
        row_h = max(row_h, cv.h)
    height = y + row_h
    rows = [[None] * width for _ in range(height)]
    meta: dict = {"scale": 2, "pieces": {}}
    for name, cv, sl, px, py in placed:
        for yy in range(cv.h):
            for xx in range(cv.w):
                rows[py + yy][px + xx] = cv.px[yy][xx]
        entry: dict = {"rect": [px, py, cv.w, cv.h]}
        if sl is not None:
            entry["slice"] = sl
        meta["pieces"][name] = entry
    return rows, meta


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rows, meta = build()
    write_png(OUT / "kit.png", rows)
    (OUT / "kit.json").write_text(json.dumps(meta, indent=1) + "\n", encoding="utf-8")
    print(f"{len(meta['pieces'])} pieces -> {OUT / 'kit.png'}")


if __name__ == "__main__":
    main()
