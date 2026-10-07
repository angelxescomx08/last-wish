"""Pixel art for the Gachapón room (stdlib only):

    python scripts/generate_gacha_sprites.py

Everything is drawn by code at native size (shown ×2 in game, like the room)
with the shared kit (``pixel_kit.py``): fixed ramps, upper-left light, ordered
dither and a coloured outline. Output in ``assets/gacha/``:

  machine.png        the machine without its moving parts: crimson lacquered lid
                     with a brass crown and a moon emblem, a glass box (dark
                     interior), brass posts, collar, lacquered base with a brass
                     coin plate, a lock, the chute and little feet
  glass.png          front glass overlay drawn over the capsules (reflection
                     streaks, edge light, posts in front)
  crank.png          8 rotations of the brass crank knob (strip)
  capsule_small.png  decorative capsules for the pile inside the box: 6 colours
  capsule.png        the prize capsule per tier (Común … Legendaria) at drop
                     size: closed (strip of 5)
  capsule_big.png    the prize capsule at stage size per tier: closed, top half,
                     bottom half (5 rows × 3 columns)
  coin.png           6-frame spinning gold coin
  flap.png           3 frames of the chute flap (closed, half, open)
  gacha.json         sizes and the anchor points the scene needs (glass box,
                     coin slot, crank pivot, chute mouth, bulbs)
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from pixel_kit import Canvas, bayer, hash01, mix, outline, ramp, write_png  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "gacha"

W, H = 128, 186
OUTLINE = (14, 6, 12)
LACQ = [(30, 6, 16), (58, 12, 28), (92, 20, 40), (132, 30, 52), (172, 48, 64), (208, 86, 90),
        (236, 140, 128)]
BRASS = [(54, 32, 14), (98, 62, 24), (150, 104, 40), (204, 156, 66), (240, 206, 120), (255, 244, 196)]
STEEL = [(28, 30, 40), (56, 60, 74), (96, 102, 118), (148, 154, 168), (204, 208, 218), (240, 242, 248)]
GLASS_IN = [(10, 8, 22), (18, 14, 36), (28, 22, 52), (40, 32, 70)]
VOID = (6, 4, 10)
WHITE = (255, 255, 255)

# layout (native px)
LID = (8, 6, 120, 30)            # x0, y0, x1, y1
BOX = (12, 30, 116, 114)         # glass box interior
COLLAR = (8, 114, 120, 122)
BASE = (10, 122, 118, 176)
PLATE = (42, 126, 86, 164)       # brass coin plate
SLOT = (64, 132)                 # coin slot centre
CRANK = (64, 150)                # crank pivot
CHUTE = (48, 166, 80, 176)       # chute mouth (x0, y0, x1, y1)
LOCK = (24, 140)
BULBS = [(14 + 10 * k, 27) for k in range(11)]

# capsules
SMALL = 16
DROP = 22
BIG = 52
DECOR = [((236, 120, 170), (255, 190, 220)), ((110, 220, 180), (190, 255, 230)),
         ((110, 170, 250), (190, 220, 255)), ((240, 220, 90), (255, 248, 190)),
         ((180, 130, 240), (226, 200, 255)), ((250, 160, 110), (255, 214, 180))]
TIER = [  # (dark, mid, light) shell colours: Común, Poco común, Rara, Épica, Legendaria
    ((96, 92, 100), (170, 166, 176), (226, 224, 232)),
    ((30, 120, 60), (80, 200, 110), (180, 255, 190)),
    ((30, 80, 170), (80, 150, 240), (190, 220, 255)),
    ((90, 40, 150), (180, 90, 240), (230, 196, 255)),
    ((160, 100, 10), (245, 175, 40), (255, 236, 150)),
]
SHELL_WHITE = [(120, 116, 128), (190, 188, 200), (236, 236, 244), (255, 255, 255)]


def _box(cv: Canvas, x0, y0, x1, y1, colors, *, light_bias=0.0, dither=0.5, bevel=True):
    for y in range(y0, y1):
        for x in range(x0, x1):
            u = (x - x0) / max(1, x1 - x0 - 1)
            v = (y - y0) / max(1, y1 - y0 - 1)
            light = 0.62 - 0.32 * u - 0.28 * v + light_bias
            if bevel:
                if x == x0 or y == y0:
                    light += 0.25
                elif x == x1 - 1 or y == y1 - 1:
                    light -= 0.25
            cv.put(x, y, ramp(colors, max(0.0, min(1.0, light)), x, y, dither))


def _disc(cv: Canvas, cx, cy, r, colors, *, light=0.7, solid=True, ry=None):
    ry = ry or r
    for y in range(int(cy - ry) - 1, int(cy + ry) + 2):
        for x in range(int(cx - r) - 1, int(cx + r) + 2):
            dx, dy = (x + 0.5 - cx) / r, (y + 0.5 - cy) / ry
            d = dx * dx + dy * dy
            if d > 1:
                continue
            lv = light - 0.35 * dx - 0.4 * dy - 0.2 * d
            cv.put(x, y, ramp(colors, max(0.0, min(1.0, lv)), x, y), solid=solid)


# ---------------------------------------------------------------- machine
def machine() -> Canvas:
    cv = Canvas(W, H)
    # glass box interior: dark violet, a little lighter at the top (lamp light)
    x0, y0, x1, y1 = BOX
    for y in range(y0, y1):
        for x in range(x0, x1):
            v = (y - y0) / (y1 - y0)
            u = (x - x0) / (x1 - x0)
            light = 0.65 - 0.55 * v - 0.2 * abs(u - 0.5)
            cv.put(x, y, ramp(GLASS_IN, max(0.0, light), x, y, 0.7))
    # back posts seen through the glass
    for px in (x0 + 8, x1 - 9):
        for y in range(y0, y1):
            cv.put(px, y, GLASS_IN[3])
    # lid: lacquered roof with brass trim and a crown
    lx0, ly0, lx1, ly1 = LID
    for y in range(ly0, ly1):
        inset = max(0, 4 - (y - ly0)) if y < ly0 + 4 else 0
        for x in range(lx0 + inset, lx1 - inset):
            u = (x - lx0) / (lx1 - lx0)
            v = (y - ly0) / (ly1 - ly0)
            light = 0.7 - 0.35 * u - 0.35 * v + 0.08 * math.cos(u * 18)
            col = ramp(LACQ, max(0.0, min(1.0, light)), x, y)
            if y in (ly0 + 4, ly1 - 4) or y == ly1 - 1:
                col = ramp(BRASS, 0.75 - 0.4 * u, x, y, 0.3)
            if y == ly1 - 3:
                col = BRASS[1]
            cv.put(x, y, col)
    # crown on the lid with a moon emblem
    cx = W // 2
    for y in range(0, ly0 + 5):
        w = 15 - y if y < 4 else 11
        for x in range(cx - w, cx + w + 1):
            if y < 4 and (x - cx) % 6 not in (0, 1, 5):
                continue
            cv.put(x, y, ramp(BRASS, 0.85 - 0.3 * (x - cx + w) / (2 * w) - 0.2 * y / 8, x, y, 0.3))
    for y in range(ly0 + 7, ly0 + 20):                        # emblem disc
        for x in range(cx - 7, cx + 8):
            d = math.hypot(x + 0.5 - cx, y + 0.5 - (ly0 + 13.5))
            if d < 6.5:
                moon = math.hypot(x + 0.5 - cx - 2.5, y + 0.5 - (ly0 + 12)) < 4.8
                cv.put(x, y, BRASS[1] if d > 5.6 else (LACQ[1] if moon else BRASS[4] if x < cx else BRASS[3]))
    # collar
    _box(cv, *COLLAR, BRASS)
    # base: lacquer with brass edge
    bx0, by0, bx1, by1 = BASE
    _box(cv, bx0, by0, bx1, by1, LACQ, light_bias=0.05)
    for x in range(bx0, bx1):                                   # lower brass skirting
        cv.put(x, by1 - 3, BRASS[2])
        cv.put(x, by1 - 2, BRASS[1])
    for y in range(by0 + 4, by1 - 6, 5):                        # lacquer grain
        for x in range(bx0 + 3, bx1 - 3):
            if hash01(x, y, 3) > 0.93:
                cv.tint(x, y, LACQ[5], 0.4)
    # coin plate (brass) with a steel inset
    px0, py0, px1, py1 = PLATE
    _box(cv, px0, py0, px1, py1, BRASS)
    _box(cv, px0 + 3, py0 + 3, px1 - 3, py1 - 3, STEEL, light_bias=0.05)
    for (sx, sy) in ((px0 + 1, py0 + 1), (px1 - 2, py0 + 1), (px0 + 1, py1 - 2), (px1 - 2, py1 - 2)):
        cv.put(sx, sy, BRASS[5])                                # rivets
    # coin slot: dark slit with a bevel
    sx, sy = SLOT
    for x in range(sx - 4, sx + 5):
        cv.put(x, sy - 1, STEEL[1])
        cv.put(x, sy, VOID)
        cv.put(x, sy + 1, STEEL[4])
    # crank socket ring
    _disc(cv, CRANK[0], CRANK[1], 10.5, STEEL, light=0.55)
    _disc(cv, CRANK[0], CRANK[1], 8.5, STEEL[:3], light=0.4)
    # lock on the left
    lx, ly = LOCK
    _disc(cv, lx, ly, 3.5, STEEL)
    cv.put(lx, ly, VOID)
    cv.put(lx, ly + 1, VOID)
    # chute: dark mouth with a brass frame
    cx0, cy0, cx1, cy1 = CHUTE
    for y in range(cy0 - 2, cy1 + 1):
        for x in range(cx0 - 2, cx1 + 2):
            edge = x in (cx0 - 2, cx0 - 1, cx1, cx1 + 1) or y in (cy0 - 2, cy0 - 1)
            if edge:
                cv.put(x, y, BRASS[3] if (x < cx0 or y < cy0 - 1) else BRASS[1])
            else:
                cv.put(x, y, mix(VOID, LACQ[0], (y - cy0) / (cy1 - cy0) * 0.5))
    # feet
    for fx in (bx0 + 4, bx1 - 14):
        _box(cv, fx, by1, fx + 10, by1 + 6, BRASS)
    # front posts and frame are in glass.png (over the capsules); the side frame is here
    for x in (BOX[0] - 4, BOX[2]):
        _box(cv, x, BOX[1], x + 4, BOX[3], BRASS)
    outline(cv, OUTLINE)
    return cv


def glass() -> Canvas:
    """Front glass: faint tint, diagonal reflections, a lit top edge."""
    cv = Canvas(W, H)
    x0, y0, x1, y1 = BOX
    for y in range(y0, y1):
        for x in range(x0, x1):
            u = (x - x0) / (x1 - x0)
            streak = (x - x0) + (y - y0) * 0.6
            a = 0
            if 6 < streak % 70 < 13:
                a = 70
            elif 16 < streak % 70 < 18:
                a = 45
            if y - y0 < 2:
                a = max(a, 90)
            if u < 0.04 or u > 0.96:
                a = max(a, 60)
            if a and bayer(x, y) < 0.85:
                cv.put(x, y, (220, 230, 255), solid=False, alpha=a)
    # a few bright glints
    for (gx, gy) in ((x0 + 10, y0 + 8), (x0 + 11, y0 + 9), (x1 - 20, y0 + 30), (x0 + 30, y1 - 12)):
        cv.put(gx, gy, WHITE, solid=False, alpha=230)
    return cv


def crank_frames(n: int = 8) -> list[Canvas]:
    out = []
    size = 24
    c = size / 2
    for k in range(n):
        cv = Canvas(size, size)
        a = k / n * math.tau
        _disc(cv, c, c, 6.5, BRASS, light=0.75)
        # T-handle: a bar across the knob, rotated
        for s in range(-10, 11):
            t = s / 2
            x, y = c + math.cos(a) * t, c + math.sin(a) * t
            for w in (-1, 0, 1):
                xx, yy = x - math.sin(a) * w * 0.9, y + math.cos(a) * w * 0.9
                lv = 0.8 - 0.3 * w - 0.25 * abs(t) / 5
                cv.put(xx, yy, ramp(BRASS, max(0.0, min(1.0, lv)), int(xx), int(yy), 0.2))
        # handle ends: rounded grips
        for sgn in (-1, 1):
            ex, ey = c + math.cos(a) * 5.2 * sgn, c + math.sin(a) * 5.2 * sgn
            _disc(cv, ex, ey, 2.0, LACQ, light=0.85)
        cv.put(c - 0.5, c - 0.5, BRASS[5])
        outline(cv, OUTLINE)
        out.append(cv)
    return out


# ---------------------------------------------------------------- capsules
def capsule(size: int, shell, part: str = "closed", angle: float = 0.0) -> Canvas:
    """Two-tone capsule: coloured translucent top, white bottom, a seam band, glossy.

    ``part``: "closed", "top" or "bottom" (the halves separate along the seam).
    """
    cv = Canvas(size, size)
    c = size / 2
    r = size / 2 - 1.5
    dark, midc, light = shell
    top_ramp = [mix(dark, (0, 0, 0), 0.35), dark, mix(dark, midc, 0.5), midc, mix(midc, light, 0.5), light]
    seam_y = c + r * 0.08
    for y in range(size):
        for x in range(size):
            dx, dy = (x + 0.5 - c) / r, (y + 0.5 - c) / r
            d = dx * dx + dy * dy
            if d > 1:
                continue
            is_top = y + 0.5 < seam_y
            if part == "top" and not is_top:
                continue
            if part == "bottom" and is_top:
                continue
            lv = 0.72 - 0.35 * dx - 0.45 * dy - 0.25 * d
            if is_top:
                col = ramp(top_ramp, max(0.0, min(1.0, lv - 0.05)), x, y, 0.5)
                # translucent: a darker inner core shows through
                if d < 0.35 and dy > -0.5 and part != "top":
                    col = mix(col, dark, 0.35)
            else:
                col = ramp(SHELL_WHITE, max(0.0, min(1.0, lv + 0.05)), x, y, 0.5)
            if abs(y + 0.5 - seam_y) < max(1.0, size / 26):       # seam band
                col = mix(midc, WHITE, 0.25) if dx < 0.2 else dark
            if (dx + 0.42) ** 2 + (dy + 0.48) ** 2 < 0.035:       # gloss
                col = WHITE
            cv.put(x, y, col)
    # a little star printed on the shell
    if size >= 40 and part in ("closed", "top"):
        sx, sy = c + r * 0.25, c - r * 0.45
        for ox, oy in ((0, -2), (0, -1), (0, 0), (0, 1), (0, 2), (-2, 0), (-1, 0), (1, 0), (2, 0),
                       (-1, -1), (1, 1), (-1, 1), (1, -1)):
            if abs(ox) + abs(oy) <= 2:
                cv.put(sx + ox, sy + oy, mix(light, WHITE, 0.7))
    outline(cv, OUTLINE)
    return cv


def coin_frames(n: int = 6) -> list[Canvas]:
    out = []
    size = 12
    for k in range(n):
        cv = Canvas(size, size)
        w = abs(math.cos(k / n * math.pi)) * 4.8 + 0.8
        _disc(cv, size / 2, size / 2, w, BRASS, light=0.85, ry=4.8)
        if w > 2.5:
            cv.put(size / 2 - 0.5, size / 2 - 1.5, BRASS[5])
            cv.put(size / 2 - 0.5, size / 2 + 0.5, BRASS[1])
        outline(cv, OUTLINE)
        out.append(cv)
    return out


def flap_frames() -> list[Canvas]:
    out = []
    cx0, cy0, cx1, cy1 = CHUTE
    w, h = cx1 - cx0, cy1 - cy0
    for k, lift in enumerate((0.0, 0.5, 1.0)):
        cv = Canvas(w, h)
        hh = max(1, int(round(h * (1 - lift * 0.8))))
        for y in range(hh):
            for x in range(w):
                lv = 0.75 - 0.4 * x / w - 0.3 * y / max(1, hh)
                cv.put(x, y, ramp(STEEL, max(0.0, lv), x, y, 0.4))
        for x in range(w):
            cv.put(x, hh - 1, STEEL[1])
        out.append(cv)
    return out


# ---------------------------------------------------------------- output
def strip(canvases: list[Canvas]) -> list[list]:
    h = canvases[0].h
    rows = [[] for _ in range(h)]
    for cv in canvases:
        for y in range(h):
            rows[y].extend(cv.px[y])
    return rows


def grid(rows_of: list[list[Canvas]]) -> list[list]:
    out = []
    for row in rows_of:
        out.extend(strip(row))
    return out


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    write_png(OUT / "machine.png", machine().px)
    write_png(OUT / "glass.png", glass().px)
    write_png(OUT / "crank.png", strip(crank_frames()))
    write_png(OUT / "capsule_small.png", strip([capsule(SMALL, (mix(a, (0, 0, 0), 0.35), a, b))
                                                for a, b in DECOR]))
    write_png(OUT / "capsule.png", strip([capsule(DROP, t) for t in TIER]))
    write_png(OUT / "capsule_big.png", grid([[capsule(BIG, t, p) for p in ("closed", "top", "bottom")]
                                             for t in TIER]))
    write_png(OUT / "coin.png", strip(coin_frames()))
    write_png(OUT / "flap.png", strip(flap_frames()))
    meta = {
        "scale": 2, "size": [W, H], "box": list(BOX), "slot": list(SLOT), "crank": list(CRANK),
        "chute": list(CHUTE), "bulbs": [list(b) for b in BULBS],
        "crank_size": 24, "crank_frames": 8, "small": SMALL, "small_colors": len(DECOR),
        "drop": DROP, "big": BIG, "tiers": len(TIER), "coin": 12, "coin_frames": 6,
        "tier_colors": [list(t[1]) for t in TIER], "tier_light": [list(t[2]) for t in TIER],
    }
    (OUT / "gacha.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print("wrote assets/gacha/ (machine, glass, crank, capsules, coin, flap, gacha.json)")


if __name__ == "__main__":
    main()
