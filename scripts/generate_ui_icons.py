"""Pixel-art UI icons for intents, statuses and keywords (``assets/ui/icons.png`` + ``icons.json``).

Card-game convention (Slay the Spire, Monster Train…): every rule has one
small picture that is used everywhere it appears — above the enemy (intent),
under a character (status badge) and in the tooltip that explains it — so the
player learns the picture once and then reads the board at a glance.

* Intent icons are 18×18 (shown ×2): ``attack_1``…``attack_4`` (the blade grows
  with the damage), ``defend``, ``buff``, ``debuff``, ``cards``, ``unknown``,
  ``lethal``.
* Status / keyword icons are 14×14 (shown ×2): poison, vulnerable, weak, frail,
  entangled, strength, blades, marked, ritual, status_buff, status_debuff,
  block, junk_card, combo, singular, void, spoil, exhaust, ethereal, unplayable, damage,
  draw, mana, heal.

Each icon is a small shape drawn with ramps, upper-left light and the usual dark
outline (``pixel_kit``). The JSON maps every name to its ``[x, y, w, h]`` in the
strip. Standard library only; run ``python scripts/generate_ui_icons.py``.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from pixel_kit import Canvas, outline, ramp, write_png  # noqa: E402

OUT = Path(__file__).parent.parent / "assets" / "ui"
INK = (22, 14, 26)

# Ramps, dark → light.
STEEL = [(52, 58, 78), (92, 102, 128), (150, 162, 186), (210, 220, 236), (250, 252, 255)]
GOLD = [(96, 58, 20), (168, 112, 34), (226, 172, 58), (255, 226, 120)]
WOOD = [(58, 34, 22), (102, 62, 36), (146, 96, 54)]
RED = [(92, 18, 26), (160, 34, 40), (220, 66, 58), (255, 132, 104), (255, 204, 170)]
BLUE = [(26, 44, 96), (44, 86, 168), (80, 140, 224), (150, 200, 255), (224, 244, 255)]
GREEN = [(22, 70, 30), (44, 128, 46), (98, 194, 70), (176, 240, 120), (232, 255, 200)]
VIOLET = [(54, 26, 84), (98, 48, 150), (150, 86, 210), (204, 150, 250), (240, 214, 255)]
ORANGE = [(110, 40, 16), (186, 78, 24), (240, 132, 40), (255, 196, 96), (255, 238, 190)]
GREY = [(50, 48, 58), (88, 86, 98), (134, 132, 146), (188, 186, 198), (236, 234, 242)]
BONE = [(92, 82, 70), (150, 138, 118), (206, 196, 176), (246, 240, 226)]
CYAN = [(24, 70, 86), (40, 120, 140), (86, 186, 200), (170, 236, 240), (236, 255, 255)]
BROWN = [(60, 38, 22), (104, 70, 40), (150, 110, 62), (196, 160, 104)]
PURPLE_DARK = [(18, 10, 30), (44, 22, 70), (86, 44, 136), (150, 92, 220), (226, 190, 255)]


def _lit(x: float, y: float, cx: float, cy: float, r: float, base: float = 0.55) -> float:
    """Upper-left light for a roughly round shape centred at (cx, cy)."""
    dx, dy = (x - cx) / max(1.0, r), (y - cy) / max(1.0, r)
    return max(0.0, min(1.0, base - 0.45 * (dx + dy) * 0.7))


def fill(cv: Canvas, inside, colors, cx: float, cy: float, r: float, *, base: float = 0.55,
         rim: bool = True) -> None:
    """Fill every pixel whose centre is ``inside`` with a shaded ramp (+ darker rim)."""
    for y in range(cv.h):
        for x in range(cv.w):
            if not inside(x + 0.5, y + 0.5):
                continue
            light = _lit(x + 0.5, y + 0.5, cx, cy, r, base)
            if rim and not all(inside(x + 0.5 + dx, y + 0.5 + dy) for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))):
                light = max(0.0, light - 0.35) if (x + y) > cx + cy else min(1.0, light + 0.1)
            cv.put(x, y, ramp(colors, light, x, y, 0.5))


def paint(cv: Canvas, rows: list[str], palette: dict[str, tuple], ox: int = 0, oy: int = 0) -> None:
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            if ch in palette:
                cv.put(ox + x, oy + y, palette[ch])


def finish(cv: Canvas) -> Canvas:
    """Pad by 1 px and add the dark outline."""
    out = Canvas(cv.w + 2, cv.h + 2)
    for y in range(cv.h):
        for x in range(cv.w):
            c = cv.px[y][x]
            if c is not None:
                out.put(x + 1, y + 1, c[:3], solid=cv.solid[y][x], alpha=c[3])
    outline(out, INK)
    return out


# ---------------------------------------------------------------- intents (16 → 18)

def sword(length: int, width: int, *, ember: bool = False, size: int = 16) -> Canvas:
    """A diagonal blade, tip up-right, hilt down-left. ``width`` 2 or 3."""
    cv = Canvas(size, size)
    # The hilt sits near the lower-left corner; the blade runs up-right.
    gx, gy = 4, size - 5                          # guard centre
    for k in range(1, length + 1):                # blade
        x, y = gx + k, gy - k
        tip = k == length
        cv.put(x, y, STEEL[4] if tip else STEEL[3])
        if not tip:
            cv.put(x + 1, y, STEEL[2])
            cv.put(x, y + 1, STEEL[3] if k > 1 else STEEL[2])
            if width >= 3:
                cv.put(x + 1, y + 1, STEEL[1])
        if k < length - 1:                        # fuller / edge glint
            cv.put(x, y, STEEL[4] if k % 3 else STEEL[3])
    guard = 3 if width >= 3 else 2
    for j in range(-guard, guard + 1):            # cross-guard (perpendicular)
        cv.put(gx + j, gy + j, GOLD[2] if j < 0 else GOLD[1])
        cv.put(gx + j + 1, gy + j, GOLD[3] if j < 0 else GOLD[2])
    for k in range(1, 4):                         # grip
        cv.put(gx - k + 1, gy + k, WOOD[1 + (k % 2)])
    cv.put(gx - 3, gy + 3, GOLD[2])               # pommel
    cv.put(gx - 3, gy + 4, GOLD[1])
    cv.put(gx - 4, gy + 3, GOLD[1])
    if ember:                                     # a hot red edge on the big blades
        for k in range(2, length - 1):
            cv.tint(gx + k + 1, gy - k + (1 if width >= 3 else 0), RED[2], 0.75)
        cv.glow(gx + length * 0.55, gy - length * 0.55, length * 0.6, RED[3], 0.6, halo=False)
    return cv


def defend() -> Canvas:
    cv = Canvas(16, 16)
    cx = 7.5

    def inside(x, y):
        if y < 1.5 or y > 15:
            return False
        half = 6.5 if y < 8 else 6.5 * (1 - ((y - 8) / 7.2) ** 1.6)
        return abs(x - cx) <= half
    fill(cv, inside, BLUE, cx, 7, 7, base=0.6)
    for y in range(2, 14):                        # central steel band
        cv.put(7, y, STEEL[3] if y < 8 else STEEL[2])
        cv.put(8, y, STEEL[2] if y < 8 else STEEL[1])
    for x in range(2, 14):
        if inside(x + 0.5, 6.5):
            cv.put(x, 6, STEEL[3] if x < 8 else STEEL[2])
    cv.put(7, 6, STEEL[4]); cv.put(8, 6, STEEL[3])
    return cv


def arrow(up: bool, colors) -> Canvas:
    cv = Canvas(16, 16)
    head_top, head_bot = (1, 8) if up else (14, 7)

    def inside(x, y):
        if up:
            if 1 <= y <= 8:
                return abs(x - 8) <= (y - 1) * 0.95 + 0.5
            return 8 < y <= 15 and abs(x - 8) <= 2.6
        if 7 <= y <= 15:
            return abs(x - 8) <= (15 - y) * 0.95 + 0.5
        return 0 <= y < 7 and abs(x - 8) <= 2.6
    fill(cv, inside, colors, 8, 8, 8, base=0.6)
    del head_top, head_bot
    return cv


def cards() -> Canvas:
    """Two grey status cards fanned, with a sickly green border on the front one."""
    cv = Canvas(16, 16)
    back = [(x, y) for y in range(1, 13) for x in range(1, 10)]
    for x, y in back:
        edge = x in (1, 9) or y in (1, 12)
        cv.put(x, y, GREY[1] if edge else GREY[2])
    for y in range(3, 16):
        for x in range(6, 15):
            edge = x in (6, 14) or y in (3, 15)
            inner = x in (7, 13) or y in (4, 14)
            cv.put(x, y, GREEN[2] if edge else GREEN[1] if inner else GREY[3] if (x + y) < 21 else GREY[2])
    paint(cv, ["..g..",
               ".ggg.",
               "ggGgg",
               ".ggg.",
               "..g.."], {"g": GREEN[2], "G": GREEN[4]}, 8, 7)
    return cv


def unknown() -> Canvas:
    cv = Canvas(16, 16)
    paint(cv, ["....aaaaa.....",
               "...aBBBBBa....",
               "..aBBaaaBBa...",
               "..aBa...aBBa..",
               "...a....aBBa..",
               ".......aBBa...",
               "......aBBa....",
               ".....aBBa.....",
               ".....aBBa.....",
               "......aa......",
               "..............",
               ".....aBBa.....",
               ".....aBBa.....",
               "......aa......"], {"a": VIOLET[1], "B": VIOLET[3]}, 1, 1)
    return cv


def lethal() -> Canvas:
    """A small skull for "this kills you"."""
    cv = Canvas(16, 16)
    paint(cv, ["....bbbbbb....",
               "..bBBBBBBBBb..",
               ".bBWWBBBBBBBb.",
               ".bBWBBBBBBBBb.",
               "bBBBBBBBBBBBBb",
               "bBkkkBBBBkkkBb",
               "bBkRkBBBBkRkBb",
               "bBkkkBBbBkkkBb",
               ".bBBBBbkbBBBb.",
               "..bBBBBBBBBb..",
               "...bBkBkBkb...",
               "...bBBBBBBb...",
               "....bbbbbb...."], {"b": BONE[0], "B": BONE[2], "W": BONE[3], "k": (24, 12, 16), "R": RED[3]}, 1, 1)
    return cv


# ---------------------------------------------------------------- statuses / keywords (12 → 14)

def droplet(colors) -> Canvas:
    cv = Canvas(12, 12)

    def inside(x, y):
        if y >= 6:
            return math.hypot(x - 6, y - 7.2) <= 4.3
        return y > 0.6 and abs(x - 6) <= (y - 0.6) * 0.72
    fill(cv, inside, colors, 6, 7, 5, base=0.55)
    cv.put(4, 6, colors[-1]); cv.put(4, 7, colors[-2]); cv.put(5, 5, colors[-2])
    return cv


def shield_small(colors, cracked: bool = False, crumbled: bool = False) -> Canvas:
    cv = Canvas(12, 12)

    def inside(x, y):
        if y < 0.5 or y > 11.6:
            return False
        half = 5.2 if y < 5.5 else 5.2 * (1 - ((y - 5.5) / 6.3) ** 1.5)
        if crumbled and x > 7 and y > 6:
            return False
        return abs(x - 6) <= half
    fill(cv, inside, colors, 6, 5, 6, base=0.6)
    if cracked:
        for x, y in ((6, 1), (6, 2), (5, 3), (6, 4), (7, 5), (6, 6), (5, 7), (6, 8), (6, 9)):
            cv.put(x, y, INK)
    if crumbled:
        for x, y in ((9, 8), (10, 10), (8, 11)):
            cv.put(x, y, colors[2])
    return cv


def broken_sword() -> Canvas:
    cv = Canvas(12, 12)
    for k in range(0, 4):                     # lower half of the blade
        cv.put(4 + k, 7 - k, STEEL[2]); cv.put(5 + k, 7 - k, STEEL[1])
    for k in range(0, 3):                     # snapped tip, drooping
        cv.put(9 + (k // 2), 3 + k, STEEL[2])
        cv.put(10 + (k // 2), 3 + k, STEEL[1])
    for j in range(-2, 3):
        cv.put(3 + j, 7 + j, GOLD[1])
    cv.put(2, 9, WOOD[1]); cv.put(1, 10, WOOD[2]); cv.put(0, 11, GOLD[1])
    for x, y in ((2, 2), (3, 1), (1, 3)):     # sad violet sparks
        cv.put(x, y, VIOLET[3])
    return cv


def net() -> Canvas:
    cv = Canvas(12, 12)
    vine, light = GREEN[1], GREEN[3]
    for i in range(12):
        for line in (i, 11 - i):
            cv.put(i, line, vine)
        cv.put(i, (i + 4) % 12, BROWN[1])
        cv.put((i + 4) % 12, i, BROWN[2])
    for x, y in ((2, 2), (9, 2), (2, 9), (9, 9), (5, 5), (6, 6)):
        cv.put(x, y, light)
    for x, y in ((3, 6), (8, 5)):
        cv.put(x, y, GREEN[4])
    return cv


def arm() -> Canvas:
    """Fuerza: a flexed arm (fist up-left, bicep bulging on the right)."""
    cv = Canvas(12, 12)
    paint(cv, [".rrr........",
               "rRWRr.......",
               "rRRRr.......",
               ".rRRr.......",
               ".rRr...rrr..",
               ".rRr..rRWRr.",
               ".rRRrrRRRRRr",
               ".rRRRRRRRRRr",
               ".rRRRRRRRRdr",
               "..rRRRRRRdr.",
               "...rrrrrrr.."], {"r": RED[1], "R": RED[2], "W": RED[4], "d": RED[1]}, 0, 1)
    return cv


def blades() -> Canvas:
    cv = Canvas(12, 12)
    for bx in (1, 5, 9):
        tip = 1 if bx == 5 else 2
        for y in range(tip, tip + 6):
            cv.put(bx, y, STEEL[3]); cv.put(bx + 1, y, STEEL[1])
        cv.put(bx, tip - 1, STEEL[4])
        cv.put(bx - 1, tip + 6, GOLD[1]); cv.put(bx, tip + 6, GOLD[2]); cv.put(bx + 1, tip + 6, GOLD[2]); cv.put(bx + 2, tip + 6, GOLD[1])
        cv.put(bx, tip + 7, WOOD[2]); cv.put(bx, tip + 8, WOOD[1])
    return cv


def crosshair() -> Canvas:
    cv = Canvas(12, 12)
    for y in range(12):
        for x in range(12):
            d = math.hypot(x + 0.5 - 6, y + 0.5 - 6)
            if 3.6 <= d <= 5.4:
                cv.put(x, y, RED[3] if x + y < 11 else RED[2])
    for i in range(12):
        if i < 4 or i > 7:
            cv.put(i, 5, RED[1]); cv.put(5, i, RED[1])
    cv.put(5, 5, RED[4]); cv.put(6, 6, RED[3]); cv.put(5, 6, RED[3]); cv.put(6, 5, RED[3])
    return cv


def eye() -> Canvas:
    cv = Canvas(12, 12)
    paint(cv, ["............",
               "...vvvvvv...",
               "..vVVVVVVv..",
               ".vVWkkkWVVv.",
               "vVWkkRkkWVVv",
               "vVWkRRRkWVVv",
               ".vVWkkkWVVv.",
               "..vVVVVVVv..",
               "...vvvvvv...",
               "............",
               "....v..v....",
               "...v....v..."], {"v": VIOLET[1], "V": VIOLET[2], "W": VIOLET[4], "k": (20, 8, 30), "R": RED[3]})
    return cv


def mini_arrow(up: bool, colors) -> Canvas:
    cv = Canvas(12, 12)

    def inside(x, y):
        if up:
            if y <= 6:
                return abs(x - 6) <= (y - 0.5) * 0.95 + 0.4 and y > 0.5
            return y <= 11.5 and abs(x - 6) <= 1.9
        if y >= 5.5:
            return abs(x - 6) <= (11.5 - y) * 0.95 + 0.4
        return y >= 0.5 and abs(x - 6) <= 1.9
    fill(cv, inside, colors, 6, 6, 6, base=0.62)
    return cv


def chevrons() -> Canvas:
    """Combo: two gold chevrons in a row (one card after another)."""
    cv = Canvas(12, 12)
    for ox in (0, 5):
        for k in range(5):
            for t in range(2):
                cv.put(ox + k + t, 1 + k, GOLD[3 - t])
                cv.put(ox + k + t, 10 - k, GOLD[2 - t])
    return cv


def star() -> Canvas:
    cv = Canvas(12, 12)

    def inside(x, y):
        dx, dy = x - 6, y - 6.2
        ang = math.atan2(dy, dx)
        r = math.hypot(dx, dy)
        lim = 2.4 + 3.4 * (0.5 + 0.5 * math.cos(5 * (ang + math.pi / 2)))
        return r <= lim
    fill(cv, inside, CYAN, 6, 6, 6, base=0.62)
    return cv


def vortex() -> Canvas:
    cv = Canvas(12, 12)
    for y in range(12):
        for x in range(12):
            dx, dy = x + 0.5 - 6, y + 0.5 - 6
            r = math.hypot(dx, dy)
            if r > 5.8:
                continue
            ang = math.atan2(dy, dx) + r * 0.9
            band = 0.5 + 0.5 * math.cos(ang * 2)
            cv.put(x, y, ramp(PURPLE_DARK, band * (r / 5.8) * 1.1, x, y, 0.4))
    cv.put(5, 5, (8, 4, 12)); cv.put(6, 6, (8, 4, 12)); cv.put(6, 5, (8, 4, 12)); cv.put(5, 6, (8, 4, 12))
    return cv


def torn_card() -> Canvas:
    cv = Canvas(12, 12)
    for y in range(12):
        for x in range(1, 10):
            if y > 7 + (x % 3) and x > 4:
                continue
            edge = x in (1, 9) or y in (0,)
            cv.put(x, y, BONE[1] if edge else BONE[2] if x + y < 12 else BONE[1])
    for x, y in ((7, 9), (9, 10), (8, 11)):
        cv.put(x, y, BONE[2])
    for y in (3, 5):
        for x in range(3, 8):
            cv.put(x, y, BROWN[1])
    return cv


def flame(colors=ORANGE) -> Canvas:
    cv = Canvas(12, 12)

    def inside(x, y):
        if y >= 6.5:
            return math.hypot(x - 6, y - 7.6) <= 4.2
        w = (y - 0.2) * 0.62
        return abs(x - 6 - (6.5 - y) * 0.35) <= w
    fill(cv, inside, colors, 6, 8, 5, base=0.5)
    for y in range(6, 11):                    # bright core
        for x in range(5, 8):
            if math.hypot(x - 6, y - 8.6) <= 1.9:
                cv.put(x, y, colors[-1] if y > 7 else colors[-2])
    return cv


def ghost() -> Canvas:
    cv = Canvas(12, 12)

    def inside(x, y):
        if y < 6:
            return math.hypot(x - 6, y - 5.8) <= 5
        if y > 11.6:
            return False
        wave = 10.6 + 0.9 * math.sin(x * 1.6)
        return 1 <= x <= 11 and y <= wave
    fill(cv, inside, CYAN, 6, 5, 6, base=0.62)
    for x, y in ((4, 5), (4, 6), (8, 5), (8, 6)):
        cv.put(x, y, (18, 30, 50))
    return cv


def no_entry() -> Canvas:
    cv = Canvas(12, 12)
    for y in range(12):
        for x in range(12):
            d = math.hypot(x + 0.5 - 6, y + 0.5 - 6)
            if 3.9 <= d <= 5.9:
                cv.put(x, y, RED[3] if x + y < 11 else RED[2])
    for k in range(2, 10):
        cv.put(k, k, RED[2]); cv.put(k + 1, k, RED[1])
    return cv


def small_sword() -> Canvas:
    cv = Canvas(12, 12)
    for k in range(1, 8):
        cv.put(3 + k, 8 - k, STEEL[4] if k == 7 else STEEL[3])
        if k < 7:
            cv.put(4 + k, 8 - k, STEEL[1])
    for j in range(-2, 3):
        cv.put(3 + j, 8 + j, GOLD[2])
    cv.put(2, 10, WOOD[1]); cv.put(1, 11, GOLD[1])
    cv.tint(9, 3, RED[2], 0.6); cv.tint(8, 4, RED[2], 0.6)
    return cv


def card_draw() -> Canvas:
    cv = Canvas(12, 12)
    for y in range(1, 11):
        for x in range(0, 8):
            edge = x in (0, 7) or y in (1, 10)
            cv.put(x, y, BLUE[1] if edge else BLUE[2] if x + y < 9 else BLUE[1])
    paint(cv, ["..w..",
               ".www.",
               "wwwww",
               "..w..",
               "..w.."], {"w": GOLD[3]}, 7, 4)
    return cv


def crystal() -> Canvas:
    cv = Canvas(12, 12)

    def inside(x, y):
        return abs(x - 6) / 4.2 + abs(y - 6) / 5.8 <= 1
    fill(cv, inside, BLUE, 6, 6, 5, base=0.62)
    for y in range(2, 10):
        cv.put(6, y, BLUE[4] if y < 6 else BLUE[3])
    return cv


def heart() -> Canvas:
    cv = Canvas(12, 12)
    paint(cv, [".rrr...rrr.",
               "rRWRr.rRRRr",
               "rWRRRrRRRRr",
               "rRRRRRRRRdr",
               "rRRRRRRRRdr",
               ".rRRRRRRdr.",
               "..rRRRRdr..",
               "...rRRdr...",
               "....rdr....",
               ".....r....."], {"r": RED[1], "R": RED[2], "W": RED[4], "d": RED[1]}, 0, 1)
    return cv


def junk_card() -> Canvas:
    """A small grey status card with a sickly green border (enemy puts cards in your deck)."""
    cv = Canvas(12, 12)
    for y in range(0, 12):
        for x in range(2, 10):
            edge = x in (2, 9) or y in (0, 11)
            cv.put(x, y, GREEN[2] if edge else GREY[3] if x + y < 10 else GREY[2])
    paint(cv, [".g.",
               "gGg",
               ".g."], {"g": GREEN[2], "G": GREEN[4]}, 5, 4)
    return cv


def block_small() -> Canvas:
    return shield_small(BLUE)


ICONS_16 = {
    "attack_1": lambda: sword(6, 2),
    "attack_2": lambda: sword(9, 2),
    "attack_3": lambda: sword(10, 3),
    "attack_4": lambda: sword(11, 3, ember=True),
    "defend": defend,
    "buff": lambda: arrow(True, BLUE),
    "debuff": lambda: arrow(False, VIOLET),
    "cards": cards,
    "unknown": unknown,
    "lethal": lethal,
}

ICONS_12 = {
    "poison": lambda: droplet(GREEN),
    "vulnerable": lambda: shield_small(ORANGE, cracked=True),
    "weak": broken_sword,
    "frail": lambda: shield_small(CYAN, crumbled=True),
    "entangled": net,
    "strength": arm,
    "blades": blades,
    "marked": crosshair,
    "ritual": eye,
    "status_buff": lambda: mini_arrow(True, BLUE),
    "status_debuff": lambda: mini_arrow(False, VIOLET),
    "block": block_small,
    "junk_card": junk_card,
    "combo": chevrons,
    "singular": star,
    "void": vortex,
    "spoil": torn_card,
    "exhaust": flame,
    "ethereal": ghost,
    "unplayable": no_entry,
    "damage": small_sword,
    "draw": card_draw,
    "mana": crystal,
    "heal": heart,
}


def build() -> tuple[list, dict]:
    tiles: list[tuple[str, Canvas]] = []
    for name, fn in ICONS_16.items():
        tiles.append((name, finish(fn())))
    for name, fn in ICONS_12.items():
        tiles.append((name, finish(fn())))
    width = sum(cv.w for _, cv in tiles)
    height = max(cv.h for _, cv in tiles)
    rows = [[None] * width for _ in range(height)]
    meta: dict = {"scale": 2, "icons": {}}
    x0 = 0
    for name, cv in tiles:
        for y in range(cv.h):
            for x in range(cv.w):
                rows[y][x0 + x] = cv.px[y][x]
        meta["icons"][name] = [x0, 0, cv.w, cv.h]
        x0 += cv.w
    return rows, meta


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rows, meta = build()
    write_png(OUT / "icons.png", rows)
    (OUT / "icons.json").write_text(json.dumps(meta, indent=1) + "\n", encoding="utf-8")
    print(f"{len(meta['icons'])} icons -> {OUT / 'icons.png'}")


if __name__ == "__main__":
    main()
