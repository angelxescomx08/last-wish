"""Draw and animate the elite enemy "Bruja del Pantano" (Swamp Hag). Stdlib only:

    python scripts/generate_elite_hag.py

Same method as the Espectro and the floor-1 bosses (``docs/code-drawn-sprites.md``): one
renderer, every frame a frozen ``Pose``. A hunched old swamp witch facing left (the hero),
standing behind her squat iron cauldron:

* ONE row-scanned mass from the drooping tip of her crooked, patched pointed hat to the
  ragged hem of her skirt. Zones painted inside it: hat cone (band, stitched patches) and
  drooping brim; sickly green-grey face in profile (long hooked nose, jutting chin, one
  glowing yellow-green eye, a grin); wild stringy grey-white hair falling over a hunched
  back; a layered ragged swamp-green shawl with moss on the shoulders; a murky brown skirt
  with a mossy, frayed hem. Hanging tatters and stray hair strands wave.
* A black iron cauldron in front of her (left, low) with a glowing toxic-green brew:
  bubbles that grow and pop, a swirl on the surface, green steam curls, drips on the side.
* Drawn on top (rimmed, the Espectro sleeve rule): a gnarled crooked staff topped with a
  small horned skull and a green flame; her bony front arm in a ragged bell sleeve; for
  some moves her far arm (voodoo doll, potion vial, raised hand).

Animations (non-death actions end on idle frame 0):
  idle    12-frame loop: sways and cackles, tatters and hair wave, bubbles pop, steam curls,
          the staff flame flickers
  attack  "Rayo de Ciénaga": draws the staff back, thrusts it; a green swamp bolt flies left
          and splashes at the far left (strike)
  voodoo  "Muñeco Vudú": pulls out a straw doll and stabs it three times with a pin, a purple
          hex flash per stab (three strikes), cackling
  brew    "Caldero Burbujeante" / "Brebaje Prohibido": stirs the cauldron, big bubbles, a
          burst of green steam, then sips a vial of brew (green healing sparkles)
  cast    "Maleficio": raises both arms, purple-green hex sigils swirl around her, a hex
          circle on the floor, the flame turns purple
  hurt    white flash, recoil, the hat flops
  death   shrieks, melts into a bubbling green puddle (the hat drops onto it) while the
          cauldron tips over and spills, then everything sinks away -> empty

Output: ``assets/enemies/hag_sheet.png`` + ``.json`` (``events``, ``moves``, ``boss``, ``elite``).
"""
from __future__ import annotations

import math
import sys
from dataclasses import dataclass, field, replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from pixel_kit import (Canvas, bayer, bezier, build_sheet, dissolve, flash, hash01, lerp,  # noqa: E402
                       mix, outline, ramp, save_sheet, smooth, stroke)

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "assets" / "enemies"
SHEET_ID = "hag"

CELL_W, CELL_H = 208, 120
CX, GROUND = 146, 112                 # skirt centre line, ground row
ANCHOR = (CX, GROUND + 2)
H = 84.0                              # hat height (local), used for lean falloff
CAUL_X = CX - 37                      # cauldron centre (cell x)

# ---------------------------------------------------------------- palette
OUTLINE = (12, 14, 14)
CLOTH = [(19, 26, 23), (29, 41, 32), (42, 58, 41), (58, 76, 48), (78, 98, 56), (106, 124, 70)]
MOSS = [(30, 52, 28), (50, 80, 34), (78, 112, 44), (116, 146, 60), (156, 180, 84)]
SKIRT = [(24, 18, 18), (38, 29, 25), (54, 42, 32), (74, 58, 42), (98, 78, 54)]
HAT = [(19, 15, 23), (31, 25, 35), (45, 36, 48), (62, 50, 62), (84, 70, 80)]
SKIN = [(40, 50, 42), (62, 78, 60), (88, 106, 78), (118, 134, 98), (152, 164, 120)]
HAIR = [(66, 68, 74), (102, 104, 108), (140, 142, 140), (182, 182, 174), (220, 218, 204)]
IRON = [(10, 10, 14), (20, 21, 26), (32, 33, 40), (48, 49, 58), (70, 72, 80), (104, 108, 112)]
BREW = [(22, 64, 30), (44, 122, 38), (100, 194, 54), (182, 246, 100), (236, 255, 196)]
HEX = [(46, 18, 66), (92, 36, 132), (150, 74, 204), (210, 150, 255), (246, 224, 255)]
WOOD = [(30, 21, 16), (50, 36, 25), (76, 56, 36), (104, 80, 52), (132, 106, 70)]
BONE = [(84, 78, 64), (138, 128, 104), (190, 180, 150), (232, 224, 198)]
STRAW = [(84, 60, 28), (130, 96, 44), (178, 140, 66), (222, 192, 106)]
STEAM = [(58, 86, 66), (92, 130, 96), (134, 174, 124), (184, 214, 164)]
BURST = [(60, 100, 70), (100, 150, 100), (150, 200, 140), (210, 240, 190)]
GOO = [(18, 44, 24), (34, 86, 34), (70, 150, 46), (140, 220, 84)]
MOUTH = (34, 12, 18)
THREAD = (150, 40, 40)
WHITE = (255, 255, 255)

GLYPHS = [
    ("#...#", ".#.#.", "..#..", ".#.#.", "#...#"),
    ("..#..", ".###.", "#.#.#", "..#..", "..#.."),
    (".###.", "#...#", "#.#.#", "#...#", ".###."),
    ("#.#.#", ".###.", "..#..", "#####", "..#.."),
    ("##.##", "#...#", "..#..", "#...#", "##.##"),
    ("..#..", ".#.#.", "#...#", ".#.#.", "..#.."),
]

# horned skull on the staff (origin = bottom centre, where it sits on the staff)
SKULL = ["h.........h",
         "hh.......hh",
         ".hh.....hh.",
         "..hhbbbhh..",
         "...bbbbBd..",
         "..bbbbbbBd.",
         "..beebeeBd.",
         "..bbbnbbBd.",
         "...bBnBBd..",
         "...dBdBd...",
         "....d.d...."]

DOLL = ["..sSd..",
        ".sSSSd.",
        ".SxSxd.",
        ".sSSSd.",
        "..dSd..",
        "sSSrSSd",
        "d.SrS.d",
        "..SSd..",
        "..S.d..",
        ".sd.dd."]


@dataclass(frozen=True)
class Pose:
    dx: float = 0.0
    dy: float = 0.0
    lean: float = 0.0                 # top of the body offset (negative = towards the hero)
    sx: float = 1.0
    sy: float = 1.0
    hunch: float = 0.0                # head/shoulders forward (-) or back (+)
    phase: float = 0.0                # cloth / hair wave
    sway: float = 1.0
    mouth: float = 0.0                # 0 closed grin .. 1 wide open (cackle / shriek)
    eye: float = 1.0
    hat_flop: float = 0.0             # extra droop of the hat tip
    staff_bot: tuple = (-31.0, 15.0)  # staff ends (rel. CX, height above ground)
    staff_top: tuple = (-30.0, 74.0)
    grip: float = 0.47                # front hand on the staff (fraction from bottom); <0 free
    hand_f: tuple = (-20.0, 50.0)     # free front hand (when grip < 0)
    hand_b: tuple = (4.0, 36.0)       # far hand (drawn when ``both``)
    both: float = 0.0
    doll: float = 0.0                 # voodoo doll in the far hand
    pins: int = 0                     # pins stuck in the doll
    pin: float = 0.0                  # >0: a pin in the front hand
    vial: float = 0.0                 # potion vial in the far hand
    flame: float = 1.0
    flame_hex: float = 0.0            # flame turns purple
    brew: float = 1.0                 # brew glow
    swirl: float = 0.0                # stirring
    bubbles: float = 1.0
    steam: float = 1.0
    burst: float = 0.0                # steam burst (brew) 0..1
    splash: float = 0.0               # brew droplets 0..1
    bolt: float = -1.0                # 0..1 flight of the swamp bolt (<0 none)
    bolt_from: tuple = (0.0, 0.0)     # cell coords where it was fired
    impact: float = 0.0               # splash at the far left 0..1
    hexflash: float = 0.0             # purple flash at the doll
    runes: float = 0.0                # hex sigils swirling (cast)
    rune_rot: float = 0.0
    ring: float = 0.0                 # hex circle on the floor
    fling: float = 0.0                # sigils fly towards the hero (cast release)
    heal: float = 0.0                 # green healing sparkles 0..1
    goo: float = 0.0                  # hurt: goo droplets 0..1
    melt: float = 0.0                 # death: melts into a puddle 0..1
    puddle: float = 0.0
    tilt: float = 0.0                 # death: cauldron tips over (rad)
    spill: float = 0.0
    sink: float = 0.0                 # death: cauldron sinks (px)
    flash: float = 0.0
    dissolve: float = 0.0
    motes: tuple = field(default_factory=tuple)


def _clamp(v: float, a: float = 0.0, b: float = 1.0) -> float:
    return a if v < a else b if v > b else v


def _interp(table, h: float) -> float:
    if h >= table[0][0]:
        return table[0][1]
    for (h0, x0), (h1, x1) in zip(table, table[1:]):
        if h1 <= h <= h0:
            return x0 + (x1 - x0) * (h0 - h) / (h0 - h1)
    return table[-1][1]


# ---------------------------------------------------------------- body frame
class Body:
    def __init__(self, p: Pose, *, hat_pass: bool = False) -> None:
        self.p = p
        m = 0.0 if hat_pass else p.melt
        self.sx = p.sx * (1 + 0.6 * m)
        self.sy = p.sy * (1 - 0.86 * m)
        self.dy = p.dy + (58 * smooth(p.melt) if hat_pass else 0.0)

    def shift(self, h: float) -> float:
        p = self.p
        k = _clamp(h / 70)
        wave = p.sway * 1.0 * math.sin(p.phase + h * 0.13) * max(0.0, 1 - h / 30) ** 1.5
        return p.lean * k ** 1.3 + p.hunch * smooth((h - 34) / 20) + wave

    def y_of(self, h: float) -> float:
        return GROUND + self.dy - h * self.sy

    def h_of(self, y: float) -> float:
        return (GROUND + self.dy - y) / self.sy

    def to_cell(self, lx: float, h: float) -> tuple[float, float]:
        return CX + self.p.dx + (lx + self.shift(h)) * self.sx, self.y_of(h)


def body_span(h: float):
    """(left, right) of skirt + torso + hunched back at local height ``h``."""
    if h < -0.5 or h > 56:
        return None
    if h < 34:
        s = (34 - h) / 34
        return -13 - 7 * s ** 1.3, 13 + 7.5 * s ** 1.3
    if h < 44:
        k = smooth((h - 34) / 10)
        return -13 - 2 * k, 13 + 4.5 * k
    t = (h - 44) / 12
    return -15 + 6 * t * t, -4 + 21.5 * math.sqrt(max(0.0, 1 - t ** 1.5))


FACE = [(62.0, -18.0), (59.6, -19.0), (58.2, -20.6), (54.6, -25.0), (53.4, -25.6), (52.6, -24.4),
        (52.1, -20.6), (51.3, -18.4), (50.4, -19.6), (49.2, -22.6), (48.3, -23.4), (47.4, -21.6),
        (46.7, -17.6), (46.2, -14.0)]
HEAD_C, HEAD_H, HEAD_R = -13.0, 55.0, 7.6


def head_back(h: float) -> float:
    d = (h - HEAD_H) / HEAD_R
    if abs(d) >= 1:
        return -99.0
    return HEAD_C + 6.4 * math.sqrt(1 - d * d)


def cone(h: float, p: Pose):
    """Centre and half width of the hat cone at height ``h`` (crooked, bends back)."""
    k = (h - 63.0) / 19.5
    c = -11.5 + 3.2 * k ** 1.6 + 1.0 * math.sin(k * 5.0) + p.hat_flop * 2 * k * k
    w = 7.4 * max(0.0, 1 - k) ** 0.85 + 0.6
    return c, w


def brim_mid(lx: float) -> float:
    d = lx + 12.0
    return 62.8 - 0.009 * d * d - 0.3 * max(0.0, -(lx + 23.0))


def hem_lift(x: int, cx: float) -> float:
    key = int(math.floor((x + 0.5 - cx) / 2.3))
    return 3.2 * hash01(key, 7, 3) ** 2


def shawl_edge(lx: float, p: Pose, layer: int) -> float:
    if layer == 0:                                   # long lower shawl
        base = 27.5 + 2.5 * math.cos(lx * 0.22 + 0.8)
        tooth = abs(((lx + 40) / 4.2) % 1.0 - 0.5) * 2
        drop = 5.5 * (1 - tooth) ** 2 * (0.5 + 0.8 * hash01(int((lx + 40) // 4.2), 2, 9))
    else:                                            # short capelet over the shoulders
        base = 38.5 + 2.0 * math.cos(lx * 0.3 + 2.0)
        tooth = abs(((lx + 41) / 3.4) % 1.0 - 0.5) * 2
        drop = 3.5 * (1 - tooth) ** 2 * (0.4 + 0.8 * hash01(int((lx + 41) // 3.4), 5, 9))
    return base - drop + 0.7 * math.sin(p.phase + lx * 0.31 + layer)


# ---------------------------------------------------------------- the mass
def zone_color(lx: float, h: float, x: int, y: int, p: Pose, b: Body, part: str):
    """Colour of the mass at local (lx, h), or None. ``part``: all / body / hat."""
    want_hat = part in ("all", "hat")
    want_body = part in ("all", "body")
    # --- hat: brim then cone
    if want_hat and h > 58:
        bm = brim_mid(lx)
        d = lx + 12.0
        if abs(d) <= 17.4:
            th = 1.6 - 0.75 * (abs(d) / 17.4) ** 2
            if abs(h - bm) <= th:
                u = d / 17.4
                light = 0.5 - 0.3 * u + (0.25 if h > bm + 0.3 else -0.12)
                if abs(d) > 15.8:
                    light -= 0.1
                return ramp(HAT, _clamp(light), x, y, 0.4)
        if 62.5 <= h <= 82.5:
            c, w = cone(h, p)
            if abs(lx - c) <= w:
                u = (lx - c) / w
                k = (h - 63) / 19.5
                if h < 64.6:                               # band
                    if abs(u + 0.25) < 0.2 and 63.3 < h < 64.3:
                        return BREW[2]                     # a little green charm
                    return ramp(HEX, _clamp(0.35 - 0.3 * u), x, y, 0.4)
                light = 0.66 - 0.44 * u - 0.18 * k + 0.08 * math.cos(u * 4 + h * 0.6)
                if u < -0.7:
                    light += 0.12
                if u > 0.82:
                    light -= 0.12
                # stitched patches
                if 68.5 <= h <= 72.5 and -0.7 <= u <= 0.05:
                    edge = h < 69.2 or h > 71.8 or u < -0.55 or u > -0.08
                    if edge and (x + y) % 2 == 0:
                        return BONE[1]
                    return ramp(SKIRT, _clamp(light + 0.05), x, y, 0.4)
                if 74.5 <= h <= 77.5 and 0.0 <= u <= 0.9:
                    edge = h < 75.1 or h > 76.9 or u < 0.12 or u > 0.78
                    if edge and (x + y) % 2 == 1:
                        return BONE[0]
                    return ramp(CLOTH, _clamp(light), x, y, 0.4)
                return ramp(HAT, _clamp(light), x, y)
        if part == "hat":
            return None
    if not want_body:
        return None
    # --- face (profile) and hair
    if 35.0 <= h <= 62.2:
        front = _interp(FACE, h) if h >= 46.2 else 99.0
        back = head_back(h)
        jag = 1.2 * (hash01(int(h * 1.3), 6, 11) - 0.5)
        hair_r = -3.0 + (62.5 - h) * 1.08 + 1.4 * math.sin(h * 0.7 + p.phase + 1) * p.sway + jag
        strand = int(math.floor((lx + 10.6 - (61 - h) * 0.45) / 1.5))
        hair_end = 36.0 + 9.0 * hash01(strand, 4, 11) + 3.0 * max(0.0, -lx - 4) / 6
        bs = body_span(h)
        if bs is not None and h < 54:
            hair_r = min(hair_r, bs[1] + 2.2 + 1.5 * hash01(strand, 3, 5))
        if front <= lx <= max(back, -10.6) and lx < -10.2:
            u = (lx - (front + -10.2) / 2) / max(1.0, (-10.2 - front) / 2)
            light = 0.66 - 0.32 * u - 0.12 * (h < 52)
            if h > 59.4:
                light -= 0.42                                # brim shadow
            elif h > 58.4:
                light -= 0.18
            if 53.0 <= h <= 58.0 and lx < -20.5:              # nose ridge catches light
                light += 0.12 if h > 54.6 else -0.05
            if lx < front + 0.9 and h < 59:
                light += 0.1
            if 46.5 < h < 50.2 and lx > front + 2.2 and lx < -15:  # under the jaw
                light -= 0.2
            return ramp(SKIN, _clamp(light), x, y, 0.45)
        if lx >= -10.6 and lx <= hair_r and h >= hair_end:
            u = (lx + 10.6) / max(1.0, hair_r + 10.6)
            sv = hash01(strand, 9, 4)
            ph = (lx + 10.6 - (61 - h) * 0.45) / 1.5 - strand      # across one strand 0..1
            light = 0.5 - 0.32 * u - 0.2 * (62 - h) / 26 + 0.45 * (sv - 0.5)
            if ph < 0.3:
                light += 0.18                                      # lit edge of each strand
            if ph > 0.7:
                light -= 0.4                                       # gap between strands
            if h < hair_end + 1.6:
                light -= 0.18                                      # thin dark tips
            if h > 60.4:
                light -= 0.35                                      # under the brim
            return ramp(HAIR, _clamp(light), x, y, 0.22)
    # --- skirt, shawl, capelet
    sp = body_span(h)
    if sp is None:
        return None
    L, R = sp
    if not (L <= lx <= R):
        return None
    if h < 3.6 and h < hem_lift(x, b.to_cell(0, 0)[0]) - 0.5:
        return None
    mid, half = (L + R) / 2, max(1.0, (R - L) / 2)
    u = (lx - mid) / half
    v = 1 - h / 56
    rim = 0.0
    if abs(u) > 0.86:
        rim -= 0.14
    if u < -0.8 and h > 18:
        rim += 0.15
    cape = shawl_edge(lx, p, 1)
    shawl = shawl_edge(lx, p, 0)
    if h >= cape:
        light = 0.64 - 0.4 * u - 0.25 * v + 0.1 * math.cos(u * 6.5 - h * 0.35) + rim
        # moss on the shoulders / top of the hump
        top = 52.5 - 2.2 * abs(lx - 2) / 6 if h > 44 else 99
        if h > top or (h > 47 and u > -0.2 and hash01(x, y, 8) > 0.55):
            ml = 0.45 - 0.3 * u + (hash01(x, y, 3) - 0.5) * 0.4
            return ramp(MOSS, _clamp(ml), x, y, 0.7)
        return ramp(CLOTH, _clamp(light + 0.16), x, y)
    if h >= cape - 1.2:
        return CLOTH[0]                                      # capelet casts a shadow
    if h >= shawl:
        light = 0.5 - 0.4 * u - 0.3 * v + 0.14 * math.cos(u * 8 + h * 0.25 + 0.3 * math.sin(p.phase)) + rim
        if h < shawl + 1.0:
            light += 0.12                                    # lit fringe of the shawl
        return ramp(CLOTH, _clamp(light), x, y)
    if h >= shawl - 1.2:
        return SKIRT[0]
    # skirt
    fold = math.cos(u * 10.5 + 0.4 * math.sin(p.phase) + h * 0.05)
    light = 0.6 - 0.36 * u - 0.36 * v + 0.16 * fold + rim
    if fold < -0.82:
        light -= 0.14                                        # deep fold lines
    col = ramp(SKIRT, _clamp(light), x, y)
    if 9 <= h <= 14.5 and 0.15 <= u <= 0.45:                 # a patch with stitches
        edge = h < 9.7 or h > 13.8 or u < 0.2 or u > 0.4
        col = (BONE[0] if (x + y) % 2 == 0 else CLOTH[1]) if edge else ramp(CLOTH, _clamp(light + 0.1), x, y)
    if h < 7:                                               # mossy, muddy hem
        if hash01(x, y, 12) > 0.35 + h / 9:
            col = ramp(MOSS, _clamp(0.3 - 0.25 * u + (hash01(x, y, 13) - 0.5) * 0.4), x, y, 0.6)
        elif h < 2.2:
            col = mix(col, SKIRT[0], 0.5)
    return col


def draw_mass(cv: Canvas, b: Body, part: str = "all") -> None:
    p = b.p
    goo_k = p.melt
    for y in range(CELL_H):
        h = b.h_of(y + 0.5)
        if h < -0.6 or h > 89:
            continue
        sh = b.shift(h)
        x0 = int(CX + p.dx + (sh - 30) * b.sx) - 1
        x1 = int(CX + p.dx + (sh + 24) * b.sx) + 2
        for x in range(max(0, x0), min(CELL_W, x1)):
            lx = (x + 0.5 - CX - p.dx) / b.sx - sh
            col = zone_color(lx, h, x, y, p, b, part)
            if col is None:
                continue
            if goo_k > 0 and part != "hat":
                k = _clamp(goo_k * 1.8 - h / 70 * 1.1)
                lum = sum(col) / 3 / 120
                col = mix(col, ramp(GOO, _clamp(0.15 + lum * 0.8), x, y, 0.5), k * 0.9)
                drip = hash01(int(x // 3), 5, 31)
                if drip > 0.8 and (x % 3 == 1) and h < 70 * goo_k * (0.4 + 0.6 * drip):
                    col = GOO[3] if hash01(x, y, 2) > 0.7 else GOO[2]     # running drips
            cv.put(x, y, col)


def draw_hat_tip(cv: Canvas, b: Body) -> None:
    """The crooked tip flops over backwards (a tube in the hat colours, no rim)."""
    p = b.p
    c, _ = cone(81.0, p)
    x0, y0 = b.to_cell(c, 81.0)
    sw = 1.2 * math.sin(p.phase + 0.6) * p.sway
    fl = p.hat_flop
    p1 = (x0 + 3 * b.sx, y0 - 6 * b.sy + 2 * fl)
    p2 = (x0 + (9 + sw + 2 * fl) * b.sx, y0 + (1 + 4 * fl - 0.5 * sw) * b.sy)
    pts = bezier((x0, y0 + 1), p1, p2, 14)
    stroke(cv, pts, lambda t: 1.9 - 1.2 * t, HAT[1:], dither=0.4)
    cv.put(round(p2[0]) + 1, round(p2[1]), HAT[1])


def draw_face(cv: Canvas, b: Body, p: Pose):
    """Eye, brow, mouth, wart, wrinkles. Returns the eye point."""
    ex, ey = b.to_cell(-17.4, 57.3)
    ex, ey = int(ex), int(ey)
    for ox, oy in ((-1, 0), (2, 0), (0, 1), (1, 1), (-1, 1)):
        if cv.get(ex + ox, ey + oy) is not None:
            cv.put(ex + ox, ey + oy, SKIN[0])
    for ox, oy in ((-2, -1), (-1, -1), (0, -1), (1, -2), (2, -2)):
        if cv.get(ex + ox, ey + oy) is not None:
            cv.put(ex + ox, ey + oy, OUTLINE)
    if p.eye > 0.05:
        cv.put(ex, ey, BREW[4] if p.eye > 0.6 else BREW[2])
        cv.put(ex + 1, ey, BREW[3] if p.eye > 0.6 else BREW[1])
    else:
        cv.put(ex, ey, SKIN[0])
        cv.put(ex + 1, ey, SKIN[0])
    # wart on the nose
    wx, wy = b.to_cell(-22.2, 55.8)
    cv.put(int(wx), int(wy), GOO[1])
    cv.put(int(wx), int(wy) - 1, SKIN[4])
    # wrinkles on the cheek
    for lx, h in ((-15.0, 54.0), (-14.0, 53.0), (-13.4, 52.0)):
        x, y = b.to_cell(lx, h)
        if cv.get(int(x), int(y)) is not None:
            cv.put(int(x), int(y), SKIN[1])
    # mouth: a grin, or wide open
    mx, my = b.to_cell(-18.4, 51.4)
    mx, my = int(mx), int(my)
    if p.mouth > 0.25:
        rows = 1 + int(round(p.mouth * 2))
        for j in range(rows):
            for i in range(0, 5 - (j == rows - 1)):
                cv.put(mx + i, my + j, MOUTH)
        cv.put(mx + 1, my, BONE[2])                              # a single tooth
        cv.put(mx, my - 1 if p.mouth > 0.7 else my, SKIN[1])
    else:
        for i in range(0, 4):
            cv.put(mx + i, my, OUTLINE if i < 3 else SKIN[0])
        cv.put(mx + 4, my - 1, SKIN[0])                          # upturned corner
        cv.put(mx + 1, my - 1, BONE[1])
    return ex + 0.5, ey + 0.5


def draw_hair_strands(cv: Canvas, b: Body, p: Pose) -> None:
    """Stray stringy strands: two over the cheek, wild ones sticking out behind."""
    strands = [((-10.6, 61.0), (-10.8, 52), (-12.2, 44.5), 0.0, HAIR[3]),
               ((-8.6, 61.0), (-8.0, 50), (-9.2, 41.5), 1.1, HAIR[2]),
               ((4.0, 58.0), (12.0, 54), (15.5, 45.0), 2.0, HAIR[2]),
               ((8.0, 53.0), (15.0, 49), (18.5, 40.0), 2.9, HAIR[1]),
               ((1.0, 60.0), (7.0, 59.0), (11.0, 53.0), 3.7, HAIR[3])]
    for (a, c, e, off, col) in strands:
        pts = []
        for i in range(16):
            t = i / 15
            lx = (1 - t) ** 2 * a[0] + 2 * (1 - t) * t * c[0] + t * t * e[0]
            h = (1 - t) ** 2 * a[1] + 2 * (1 - t) * t * c[1] + t * t * e[1]
            lx += 1.3 * math.sin(p.phase + off + t * 2.5) * p.sway * t * t
            pts.append(b.to_cell(lx, h))
        for i, (x, y) in enumerate(pts):
            cv.put(int(x), int(y), col if i < 12 else HAIR[1])


def draw_tatters(cv: Canvas, b: Body, p: Pose) -> None:
    """Rag strips hanging below the shawl edge."""
    for k, (lx, ln, off) in enumerate(((-15.5, 9, 0.0), (-9.0, 6, 1.3), (-2.5, 8, 2.1), (5.0, 5, 3.0),
                                       (11.5, 9, 4.1), (17.0, 7, 5.0))):
        h0 = shawl_edge(lx, p, 0) + 1.0
        for s in range(ln):
            t = s / ln
            xx = lx + 1.4 * math.sin(p.phase + off) * p.sway * t * t + (0.6 * t if lx > 0 else -0.6 * t)
            x, y = b.to_cell(xx, h0 - s)
            col = CLOTH[2] if s < ln * 0.4 else CLOTH[1]
            if k % 2 == 0 and s == 1:
                col = CLOTH[3]
            cv.put(int(x), int(y), col)
            if s < ln * 0.6:
                cv.put(int(x) + 1, int(y), CLOTH[1] if s else CLOTH[2])


def draw_pouch(cv: Canvas, b: Body, p: Pose) -> None:
    """A little hanging pouch and a bone charm on a cord at the back hip."""
    sw = round(0.7 * math.sin(p.phase - 1.0) * p.sway)
    x0, y0 = b.to_cell(12.5, 28)
    x0, y0 = int(x0) + sw, int(y0)
    cv.put(x0, y0, SKIRT[0])
    for j in range(1, 6):
        w = 2 if j in (1, 5) else 3
        for i in range(-w + 1, w):
            lvl = 3 if i < 0 and j < 4 else 2 if i <= 0 else 1
            cv.put(x0 + i, y0 + j, SKIRT[lvl] if j > 1 else SKIRT[1])
    cv.put(x0 - 1, y0 + 2, SKIRT[4])
    # charm: a tooth on a cord
    cx = x0 - 4 + sw
    for j in range(1, 4):
        cv.put(cx, y0 + j, SKIRT[1])
    cv.put(cx, y0 + 4, BONE[3])
    cv.put(cx, y0 + 5, BONE[1])


# ---------------------------------------------------------------- cauldron
def cauldron_zone(q: float, hh: float, p: Pose, x: int, y: int):
    """(zone, colour) of the cauldron at local (q, hh) (q right, hh up from its base)."""
    # rim (a ring) and the brew inside
    rc, rrx, rry = 18.2, 15.6, 3.5
    d_out = (q / rrx) ** 2 + ((hh - rc) / rry) ** 2
    if d_out <= 1.0:
        d_in = (q / 12.4) ** 2 + ((hh - rc - 0.4) / 2.3) ** 2
        if d_in < 1.0:
            # brew surface: swirl + glow
            ang = math.atan2((hh - rc - 0.4) / 2.3, q / 12.4)
            r = math.sqrt(d_in)
            sw = math.cos(ang * 2 + r * (5 + 6 * p.swirl) - p.phase * (1 + p.swirl) * 2)
            light = 0.55 + 0.22 * sw * (0.5 + p.swirl) - 0.35 * max(0.0, r - 0.7) + 0.15 * (p.brew - 1)
            if hh > rc + 0.4 + 1.2 * math.sqrt(max(0.0, 1 - (q / 12.4) ** 2)):
                light -= 0.3                                    # far inner wall in shadow
            return "brew", ramp(BREW, _clamp(light), x, y, 0.5)
        front = hh < rc
        u = q / rrx
        light = 0.45 - 0.4 * u + (0.25 if not front else 0.0)
        if front and hh > rc - 1.2:
            light += 0.25                                       # top of the lip
        col = ramp(IRON, _clamp(light), x, y, 0.4)
        if not front and d_out > 0.55:
            col = mix(col, BREW[1], 0.35 * p.brew)              # inner lip lit by the brew
        return ("rimfront" if front else "rimback"), col
    # handles (ears)
    for side in (-1, 1):
        ex, ey = side * 16.2, 13.4
        d = math.hypot(q - ex, (hh - ey) * 1.1)
        if 1.0 <= d <= 2.3 and side * (q - ex) > -0.6:
            return "body", IRON[3] if hh > ey else IRON[1]
    # pot body
    bc, brx, bry = 10.5, 14.8, 9.8
    if hh <= rc - 1.0:
        dx, dy = q / brx, (hh - bc) / bry
        d = dx * dx + dy * dy
        if d <= 1.0:
            nz = math.sqrt(max(0.0, 1 - d))
            lam = max(0.0, -0.55 * dx + 0.5 * dy + 0.68 * nz)
            light = 0.08 + 0.75 * lam - 0.15 * max(0.0, 0.35 - hh / 10)
            spec = -0.55 * dx + 0.5 * dy + 0.68 * nz
            col = ramp(IRON, _clamp(light), x, y, 0.5)
            if spec > 0.93:
                col = IRON[5]
            elif dx > 0.7:
                col = mix(col, BREW[0], 0.25 * p.brew)          # green bounce on the far side
            # drips of brew running down the front
            for dq, ln in ((-6.5, 5.5), (3.5, 3.5), (8.5, 7.0)):
                if abs(q - dq) < 0.6 and hh > rc - 1.0 - ln:
                    col = BREW[2] if hh > rc - 2.5 - ln * 0.5 else BREW[1]
            # riveted band
            if abs(hh - 12.0) < 0.5 and abs(dx) < 0.95:
                col = IRON[0] if lam < 0.5 else IRON[2]
                if int(q + 30) % 6 == 0:
                    col = IRON[4]
            return "body", col
    # stubby feet
    for fq in (-9.0, 9.0):
        if abs(q - fq) <= 2.2 - 0.25 * (2 - hh) and -0.4 <= hh <= 2.5:
            return "body", IRON[2] if q < fq else IRON[1]
    return None


def draw_cauldron(cv: Canvas, p: Pose, zones: dict) -> None:
    piv_x, piv_y = CAUL_X - 14.5, GROUND + 1
    ca, sa = math.cos(p.tilt), math.sin(p.tilt)
    for y in range(int(GROUND - 34), GROUND + 2):
        for x in range(CAUL_X - 30, CAUL_X + 20):
            # undo the tip-over (rotation about the left foot) and the sinking
            X, Y = x + 0.5 - piv_x, piv_y - (y + 0.5)
            qx = X * ca - Y * sa
            qy = X * sa + Y * ca
            q = qx - 14.5
            hh = qy - 1 + p.sink
            if y > GROUND + 1:
                continue
            z = cauldron_zone(q, hh, p, x, y)
            if z is None:
                continue
            if p.sink > 0 and y >= GROUND - 1 - 0.0 and hh < p.sink - 0.5:
                continue
            zones[(x, y)] = z[0]
            zones[("c", x, y)] = z[1]
            cv.put(x, y, z[1])


def brew_surface(p: Pose):
    return CAUL_X, GROUND - 18.6


def draw_bubbles(cv: Canvas, p: Pose) -> None:
    if p.bubbles <= 0 or p.tilt > 0.3:
        return
    bx, by = brew_surface(p)
    big = p.bubbles
    for j in range(5):
        f = (p.phase / math.tau * (1 + (j % 2)) + j * 0.23 + 0.11 * j * j) % 1.0
        q = -9 + 18 * hash01(j, 1, 21) + 1.5 * math.sin(p.phase + j)
        x, y = bx + q, by + 0.6 * math.sin(j * 1.7)
        r = (0.8 + 1.4 * hash01(j, 2, 21)) * big * min(1.0, f / 0.65)
        if f < 0.72:
            for yy in range(int(y - r) - 1, int(y) + 1):
                for xx in range(int(x - r) - 1, int(x + r) + 2):
                    d = math.hypot(xx + 0.5 - x, (yy + 0.5 - y) * 1.15) / max(0.6, r)
                    if d > 1:
                        continue
                    col = BREW[4] if (d < 0.5 and xx < x and yy < y - r * 0.3) else BREW[3] if d > 0.7 else BREW[2]
                    cv.put(xx, yy, col)
        elif f < 0.86:                                          # pop: a ring and droplets
            k = (f - 0.72) / 0.14
            rr = r + 1 + 2 * k
            for a in range(8):
                ang = a / 8 * math.tau
                cv.put(int(x + math.cos(ang) * rr), int(y + math.sin(ang) * rr * 0.4), BREW[3],
                       solid=False, alpha=int(255 * (1 - k)))
            cv.put(int(x - 1), int(y - 2 - 3 * k), BREW[3], solid=False)
            cv.put(int(x + 1), int(y - 3 - 2 * k), BREW[2], solid=False)


def smoke_puff(cv: Canvas, x: float, y: float, r: float, dens: float, cols=STEAM) -> None:
    if dens <= 0 or r <= 0:
        return
    for yy in range(int(y - r) - 1, int(y + r) + 2):
        for xx in range(int(x - r) - 1, int(x + r) + 2):
            d = math.hypot(xx + 0.5 - x, yy + 0.5 - y) / r
            if d > 1:
                continue
            if d > 0.62 and bayer(xx, yy) > (1.4 - d) * dens * 1.6:
                continue
            lit = (yy + 0.5 - y) + (xx + 0.5 - x) * 0.6
            lv = 3 if (lit < -r * 0.3 and d < 0.7) else 2 if d < 0.6 else 1 if d < 0.85 else 0
            cv.put(xx, yy, cols[lv], solid=False, alpha=int(255 * min(0.75, 0.15 + 0.5 * dens)))


def draw_steam(cv: Canvas, p: Pose) -> None:
    bx, by = brew_surface(p)
    if p.steam > 0 and p.tilt < 0.3:
        for j in range(4):
            f = (p.phase / math.tau + j / 4) % 1.0
            x = bx - 6 + 4 * j + 3 * math.sin(f * 5 + j * 1.3) - 5 * f
            y = by - 2 - f * 30
            r = 1.6 + 2.8 * f
            smoke_puff(cv, x, y, r, p.steam * (1 - 0.85 * f))
    if p.burst > 0:
        s = p.burst
        for j in range(7):
            a = -math.pi / 2 + (hash01(j, 1, 17) - 0.5) * 1.8
            d = 4 + 26 * s * (0.5 + 0.5 * hash01(j, 2, 17))
            x, y = bx + math.cos(a) * d * 0.9, by - 3 + math.sin(a) * d
            smoke_puff(cv, x, y, 2 + 5 * s * (0.6 + 0.4 * hash01(j, 3, 17)), 1.1 * (1 - s * 0.7), BURST)
    if p.splash > 0:
        s = p.splash
        for j in range(12):
            vx = (hash01(j, 1, 19) - 0.5) * 30
            vy = 18 + 18 * hash01(j, 2, 19)
            x = bx + vx * s
            y = by - 2 - vy * s + 34 * s * s
            if y > GROUND or s > 0.98:
                continue
            cv.put(int(x), int(y), BREW[3 if j % 3 else 4], solid=False)
            cv.put(int(x), int(y) + 1, BREW[1], solid=False)


# ---------------------------------------------------------------- staff, arms, props
def staff_points(p: Pose):
    (bx, bh), (tx, th) = p.staff_bot, p.staff_top
    x0, y0 = CX + p.dx + bx, GROUND + p.dy - bh
    x1, y1 = CX + p.dx + tx, GROUND + p.dy - th
    L = max(1.0, math.hypot(x1 - x0, y1 - y0))
    nx, ny = -(y1 - y0) / L, (x1 - x0) / L
    pts = []
    n = 24
    for i in range(n + 1):
        t = i / n
        off = 0.9 * math.sin(t * 13 + 1.3) + 0.5 * math.sin(t * 29 + 0.4)
        pts.append((x0 + (x1 - x0) * t + nx * off, y0 + (y1 - y0) * t + ny * off))
    return pts, ((x1 - x0) / L, (y1 - y0) / L)


def draw_staff(cv: Canvas, p: Pose, czones: dict):
    pts, up = staff_points(p)

    def rad(t):
        knot = 0.55 * math.exp(-((t - 0.32) / 0.04) ** 2) + 0.5 * math.exp(-((t - 0.63) / 0.04) ** 2)
        return 1.25 + knot + 0.5 * max(0.0, t - 0.9) / 0.1

    tube = Canvas(CELL_W, CELL_H)
    stroke(tube, pts, rad, WOOD, dither=0.5)
    # hide what is inside / behind the cauldron's front
    for y in range(CELL_H):
        for x in range(CELL_W):
            if tube.px[y][x] is None:
                continue
            z = czones.get((x, y))
            if z in ("body", "rimfront") or (z == "brew" and y >= GROUND - 18.6):
                tube.px[y][x] = None
                tube.solid[y][x] = False
    cv.blit(tube, rim=OUTLINE)
    top = pts[-1]
    draw_skull(cv, top, up, p)
    return top, up


def draw_skull(cv: Canvas, top, up, p: Pose) -> None:
    ux, uy = up
    px_, py_ = -uy, ux                                   # perpendicular (screen right when upright)
    if px_ < 0:                                          # keep the skull's face looking left
        px_, py_ = -px_, -py_
    pal = {"h": HAIR[0], "b": BONE[2], "B": BONE[1], "d": BONE[0], "n": OUTLINE}
    ox0, oy0 = 5, 10
    for y in range(int(top[1]) - 12, int(top[1]) + 12):
        for x in range(int(top[0]) - 12, int(top[0]) + 12):
            X, Y = x + 0.5 - top[0], y + 0.5 - top[1]
            a = X * px_ + Y * py_                         # along the skull's width
            u = -(X * ux + Y * uy)                        # along "down" in the pattern
            c = int(math.floor(a + 0.5)) + ox0
            r = int(math.floor(u + 0.5)) + oy0
            if not (0 <= r < len(SKULL) and 0 <= c < 11):
                continue
            ch = SKULL[r][c]
            if ch == ".":
                continue
            if ch == "e":
                col = (HEX[3] if p.flame_hex > 0.5 else BREW[3]) if p.flame > 0.3 else OUTLINE
            elif ch == "h":
                col = HAIR[2] if (r < 2 and c < 5) else HAIR[1] if c < 5 else HAIR[0]
            else:
                col = pal[ch]
            cv.put(x, y, col)


def flame_point(p: Pose):
    pts, (ux, uy) = staff_points(p)
    x, y = pts[-1]
    return x + ux * 9.5, y + uy * 9.5, ux, uy


def draw_flame(cv: Canvas, p: Pose) -> None:
    if p.flame <= 0.05:
        return
    x0, y0, ux, uy = flame_point(p)
    nx, ny = -uy, ux
    hgt = 4.5 + 2.2 * p.flame + 1.2 * math.sin(p.phase * 3)
    cols = [mix(BREW[i], HEX[i], p.flame_hex) for i in range(5)]
    for i in range(int(hgt * 2) + 1):
        t = i / (hgt * 2)
        w = 2.2 * math.sin(min(1.0, t * 1.6 + 0.15) * math.pi) * (1 - t * 0.5) * min(1.6, 0.8 + 0.4 * p.flame)
        wob = 0.8 * math.sin(p.phase * 3 + t * 6) * t
        cx, cy = x0 + ux * t * hgt + nx * wob, y0 + uy * t * hgt + ny * wob
        for k in range(-int(w) - 1, int(w) + 2):
            if abs(k) > w + 0.3:
                continue
            lv = 4 if (abs(k) < w * 0.35 and t < 0.5) else 3 if abs(k) < w * 0.7 else 2
            if t > 0.75:
                lv = max(1, lv - 1)
            cv.put(int(cx + nx * k), int(cy + ny * k), cols[lv], solid=False)


def shoulder(b: Body, back: bool):
    return b.to_cell(1.5, 46.0) if back else b.to_cell(-9.5, 45.0)


def draw_arm(cv: Canvas, b: Body, hand, back: bool, drop: float = 9.0, grip: bool = False):
    """Ragged bell sleeve from the shoulder towards ``hand`` (cell coords) and a bony hand.

    ``grip``: the fingers wrap round a vertical-ish staff at ``hand``. Returns the hand point.
    """
    sx_, sy_ = shoulder(b, back)
    hx, hy = hand
    dxh, dyh = hx - sx_, hy - sy_
    L = max(1.0, math.hypot(dxh, dyh))
    dxh, dyh = dxh / L, dyh / L
    cx_, cy_ = hx - dxh * 3.2, hy - dyh * 3.2                    # cuff
    ex, ey = (sx_ + cx_) / 2 + (2 if back else 1), max(sy_, cy_) + drop
    n = int(math.hypot(cx_ - sx_, cy_ - sy_) * 1.5) + 4
    pts = bezier((sx_, sy_), (ex, ey), (cx_, cy_), n)
    cols = CLOTH[:-1] if not back else CLOTH[:-2]
    stroke(cv, pts, lambda t: 2.9 - 0.9 * t + 1.9 * max(0.0, t - 0.68) / 0.32, cols,
           shade=-0.16 if back else -0.04, rim=OUTLINE)
    # frayed cuff: rags hanging from the underside
    ph = b.p.phase
    for k, (off, ln) in enumerate(((-2.4, 3), (-0.6, 4), (1.6, 2), (3.0, 3))):
        x0 = cx_ + off * 0.8
        y0 = cy_ + 2.6
        for s_ in range(ln):
            xx = x0 + 0.6 * math.sin(ph + k) * s_ / ln
            cv.put(int(xx), int(y0 + s_), CLOTH[1] if s_ < ln - 1 else CLOTH[0])
    sk = SKIN if not back else SKIN[:-1]
    gx, gy = int(round(hx)), int(round(hy))
    if grip:
        # thumb over the top, three knuckly fingers wrapping the staff, dark nails on the far side
        cv.put(gx + 1, gy - 3, sk[3])
        cv.put(gx, gy - 3, sk[4 if len(sk) > 4 else 3])
        cv.put(gx + 2, gy - 2, sk[2])
        for j in range(4):
            for i in range(-2, 3):
                lvl = 4 if i <= -1 else 3 if i <= 1 else 2
                if j % 2 == 1:
                    lvl -= 2                                   # creases between the fingers
                if j == 3:
                    lvl -= 1
                cv.put(gx + i, gy - 2 + j, sk[max(0, min(len(sk) - 1, lvl))])
            cv.put(gx - 3, gy - 2 + j, (52, 40, 34) if j % 2 == 0 else OUTLINE)   # nails
        cv.put(gx + 3, gy - 1, sk[1])
        return gx, gy
    # free hand: bony palm and three long clawed fingers along the arm direction
    for ox, oy, lv in ((0, 0, 2), (-1, 0, 3), (1, 0, 1), (0, 1, 1), (-1, 1, 2), (0, -1, 3), (1, -1, 2)):
        cv.put(gx + ox, gy + oy, sk[min(len(sk) - 1, lv)])
    nx, ny = -dyh, dxh
    for f, spread in ((-1, -1.1), (0, 0.0), (1, 1.1)):
        for s_ in range(1, 4):
            x = gx + dxh * (1 + s_) + nx * spread * (0.6 + 0.25 * s_)
            y = gy + dyh * (1 + s_) + ny * spread * (0.6 + 0.25 * s_)
            cv.put(int(round(x)), int(round(y)), sk[2] if s_ < 3 else (60, 48, 40))
    return gx, gy


def draw_doll(cv: Canvas, x0: float, y0: float, pins: int, k: float, fl: float) -> tuple[float, float]:
    """Straw voodoo doll held at (x0, y0) (its feet). Returns its chest point."""
    pal = {"s": STRAW[3], "S": STRAW[2], "d": STRAW[1], "x": OUTLINE, "r": THREAD}
    ox, oy = int(x0) - 3, int(y0) - 10
    for j, row in enumerate(DOLL):
        for i, ch in enumerate(row):
            if ch == ".":
                continue
            col = pal[ch]
            if fl > 0:
                col = mix(col, HEX[4], fl * 0.7)
            cv.put(ox + i, oy + j, col)
    # pins already stuck (head + shaft pointing in from the upper right)
    for n, (i, j) in enumerate(((4, 5), (2, 3), (5, 2))[:pins]):
        cv.put(ox + i + 1, oy + j - 1, BONE[3])
        cv.put(ox + i + 2, oy + j - 2, HEX[2] if n % 2 == 0 else THREAD)
    return ox + 3.5, oy + 5.5


def draw_pin(cv: Canvas, hx: float, hy: float, tx: float, ty: float) -> None:
    dx, dy = tx - hx, ty - hy
    L = max(1.0, math.hypot(dx, dy))
    dx, dy = dx / L, dy / L
    for s in range(6):
        cv.put(int(hx + dx * (s + 1)), int(hy + dy * (s + 1)), BONE[3] if s > 1 else BONE[2])
    cv.put(int(hx - dx), int(hy - dy), HEX[3])


def draw_vial(cv: Canvas, x: float, y: float) -> None:
    """A little round-bellied flask of glowing brew held up (neck up)."""
    x, y = int(x), int(y)
    for j in range(5):
        for i in range(-2, 3):
            if abs(i) == 2 and j in (0, 4):
                continue
            col = BREW[2] if j < 3 else BREW[3]
            if i == -1 and j in (2, 3):
                col = BREW[4]
            if i == 2 or j == 0:
                col = BREW[1]
            cv.put(x + i, y - j, col)
    for j in range(5, 7):
        cv.put(x, y - j, (170, 196, 186))
        cv.put(x + 1, y - j, (110, 132, 128))
    cv.put(x, y - 7, WOOD[3])
    cv.put(x + 1, y - 7, WOOD[1])


# ---------------------------------------------------------------- effects
BOLT_END = (12.0, 64.0)


def draw_bolt(cv: Canvas, p: Pose) -> None:
    if p.bolt < 0:
        return
    sx, sy = p.bolt_from
    ex, ey = BOLT_END
    t = _clamp(p.bolt)
    hx, hy = lerp(sx, ex, t), lerp(sy, ey, t) - 6 * math.sin(t * math.pi)
    if t < 1.0:
        tail = 26 * min(1.0, 0.3 + t * 2)
        dx, dy = sx - hx, sy - hy
        L = max(1.0, math.hypot(dx, dy))
        dx, dy = dx / L, dy / L
        nx, ny = -dy, dx
        n = int(tail)
        for i in range(n):
            f = i / max(1, n)
            w = 2.6 * (1 - f)
            wig = 1.6 * math.sin(i * 0.9 + t * 17) * f
            cx, cy = hx + dx * i + nx * wig, hy + dy * i + ny * wig
            for k in range(-int(w), int(w) + 1):
                if bayer(int(cx), int(cy + k)) > (1 - f) * 1.4:
                    continue
                lv = 3 if (abs(k) < w * 0.4 and f < 0.4) else 2 if f < 0.6 else 1
                cv.put(int(cx + nx * k * 0.6), int(cy + ny * k * 0.6), BREW[lv], solid=False)
            if i % 5 == 2:
                cv.put(int(cx + nx * 3.5 * math.sin(i)), int(cy + ny * 3.5 * math.sin(i)) - 1,
                       HEX[3] if i % 2 else HEX[2], solid=False)
        # the orb
        for yy in range(int(hy) - 4, int(hy) + 5):
            for xx in range(int(hx) - 4, int(hx) + 5):
                d = math.hypot(xx + 0.5 - hx, yy + 0.5 - hy)
                if d > 3.6:
                    continue
                col = WHITE if d < 1.2 else BREW[4] if d < 2.2 else BREW[3] if d < 3.0 else BREW[2]
                cv.put(xx, yy, col, solid=False)
        cv.glow(hx, hy, 10, BREW[2], 0.55)
    if p.impact > 0:
        s = p.impact
        ix, iy = ex, ey
        if s < 0.6:
            k = 1 - s / 0.6
            for yy in range(int(iy) - 5, int(iy) + 6):
                for xx in range(int(ix) - 5, int(ix) + 6):
                    d = math.hypot(xx + 0.5 - ix, yy + 0.5 - iy)
                    if d < 4.5 * k + 1:
                        cv.put(xx, yy, WHITE if d < 2 * k else BREW[3], solid=False)
            cv.glow(ix, iy, 14 * k + 4, BREW[2], 0.7 * k)
        rr = 3 + 12 * s
        for a in range(28):
            ang = a / 28 * math.tau
            if bayer(a, 3) > (1 - s) * 1.3:
                continue
            cv.put(int(ix + math.cos(ang) * rr), int(iy + math.sin(ang) * rr * 0.8), BREW[2 if s > 0.5 else 3],
                   solid=False)
        for j in range(14):
            ang = (hash01(j, 1, 23) - 0.5) * 2 * math.pi
            sp = 8 + 16 * hash01(j, 2, 23)
            x = ix + math.cos(ang) * sp * s + 4 * s
            y = iy + math.sin(ang) * sp * s * 0.8 + 16 * s * s
            if s > 0.95:
                continue
            cv.put(int(x), int(y), BREW[3] if j % 3 else HEX[3], solid=False)
            if s < 0.6:
                cv.put(int(x - math.cos(ang)), int(y - math.sin(ang)), BREW[1], solid=False)


def draw_hexflash(cv: Canvas, x: float, y: float, k: float) -> None:
    if k <= 0:
        return
    for dxs, dys in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (-1, -1), (1, -1), (-1, 1)):
        diag = dxs != 0 and dys != 0
        ln = int((3 if diag else 6) * k + 1)
        for s in range(1, ln + 1):
            col = HEX[4] if s <= ln * 0.4 else HEX[3] if s <= ln * 0.75 else HEX[2]
            cv.put(int(x + dxs * s), int(y + dys * s), col, solid=False)
    cv.glow(x, y, 6 + 8 * k, HEX[2], 0.6 * k)


def draw_glyph(cv: Canvas, x: float, y: float, g: int, col, col2, alpha: int) -> None:
    for j, row in enumerate(GLYPHS[g % len(GLYPHS)]):
        for i, ch in enumerate(row):
            if ch == "#":
                cv.put(int(x) + i - 2, int(y) + j - 2, col if (i + j) % 2 == 0 else col2,
                       solid=False, alpha=alpha)


def rune_positions(p: Pose):
    gx, gy = CX - 8 + p.dx, GROUND - 46
    out = []
    for j in range(8):
        a = j / 8 * math.tau + p.rune_rot
        rx, ry = 38 + 6 * p.fling, 11
        x = gx + math.cos(a) * rx - 70 * p.fling * smooth(p.fling) * (0.6 + 0.4 * hash01(j, 1, 29))
        y = gy + math.sin(a) * ry - 6 * math.sin(a * 2 + p.rune_rot) - 8 * p.fling * hash01(j, 2, 29)
        out.append((x, y, math.sin(a), j))
    return out


def draw_runes(cv: Canvas, p: Pose, front: bool) -> None:
    if p.runes <= 0:
        return
    alpha = int(255 * _clamp(p.runes * 1.3) * (1 - 0.8 * p.fling))
    for x, y, depth, j in rune_positions(p):
        if (depth > 0) != front:
            continue
        purple = j % 2 == 0
        hi = (HEX if purple else BREW)[4 if front else 3]
        lo = (HEX if purple else BREW)[3 if front else 2]
        draw_glyph(cv, x, y, j, hi, lo, alpha if front else int(alpha * 0.6))
        cv.glow(x, y, 7, (HEX if purple else BREW)[2], (0.5 if front else 0.25) * p.runes)


def draw_ring(cv: Canvas, p: Pose, t: float) -> None:
    if p.ring <= 0:
        return
    gx, gy = CX - 6 + p.dx, GROUND + 1
    rx, ry = 12 + 26 * smooth(min(1.0, p.ring * 1.4)), 4.2
    n = 160
    for i in range(n):
        a = i / n * math.tau
        x, y = gx + math.cos(a) * rx, gy + math.sin(a) * ry
        dash = ((i + int(t * 40)) // 5) % 2 == 0
        col = HEX[3] if dash else HEX[1]
        if bayer(int(x), int(y)) > p.ring + 0.1:
            continue
        cv.put(int(x), int(y), col, solid=False, alpha=int(230 * min(1.0, p.ring)))
    if p.ring > 0.4:
        for j in range(5):
            a = j / 5 * math.tau + t * 2
            x, y = gx + math.cos(a) * rx * 0.62, gy + math.sin(a) * ry * 0.62
            cv.put(int(x), int(y), HEX[4], solid=False)
            cv.put(int(x) + 1, int(y), HEX[2], solid=False)


def draw_heal(cv: Canvas, p: Pose) -> None:
    if p.heal <= 0:
        return
    for j in range(10):
        f = (p.heal * 1.2 + hash01(j, 1, 33) * 0.5) % 1.0
        x = CX - 22 + 40 * hash01(j, 2, 33) + p.dx
        y = GROUND - 14 - 50 * hash01(j, 3, 33) - 18 * f
        if f > 0.9:
            continue
        col = BREW[4] if f < 0.4 else BREW[3]
        cv.put(int(x), int(y), col, solid=False)
        if j % 2 == 0 and f < 0.6:
            for ox, oy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                cv.put(int(x) + ox, int(y) + oy, BREW[2], solid=False)


def draw_goo(cv: Canvas, p: Pose, b: Body) -> None:
    if p.goo <= 0:
        return
    s = p.goo
    cx, cy = b.to_cell(-4, 46)
    for j in range(12):
        ang = -math.pi / 2 + (hash01(j, 1, 37) - 0.25) * 2.6
        sp = 8 + 18 * hash01(j, 2, 37)
        x = cx + math.cos(ang) * sp * s + 6 * s
        y = cy + math.sin(ang) * sp * s + 24 * s * s
        if s > 0.95:
            continue
        cv.put(int(x), int(y), GOO[3] if j % 3 else HEX[3], solid=False)
        if j % 2 == 0:
            cv.put(int(x) + 1, int(y), GOO[2], solid=False)


def draw_puddle(cv: Canvas, p: Pose) -> None:
    if p.puddle <= 0:
        return
    gx = CX - 12 + p.dx
    rx, ry = 6 + 38 * smooth(p.puddle), 1.5 + 3.5 * smooth(p.puddle)
    cy = GROUND - ry * 0.4
    for y in range(int(cy - ry) - 1, GROUND + 2):
        for x in range(int(gx - rx) - 1, int(gx + rx) + 2):
            wob = 0.8 * math.sin(x * 0.7 + p.phase * 2)
            d = ((x + 0.5 - gx) / rx) ** 2 + ((y + 0.5 - cy) / (ry + 0.3 * wob)) ** 2
            if d > 1:
                continue
            top = y + 0.5 < cy - ry * 0.3
            light = 0.45 - 0.35 * (x + 0.5 - gx) / rx + (0.3 if top else 0.0) - 0.25 * max(0.0, d - 0.7)
            col = ramp(GOO, _clamp(light), x, y, 0.6)
            if top and d < 0.6 and hash01(x, y, 41) > 0.85:
                col = BREW[3]
            cv.put(x, y, col)
    # bubbles on the puddle
    for j in range(5):
        f = (p.phase / math.tau * 2 + j * 0.31) % 1.0
        x = gx + (hash01(j, 1, 43) - 0.5) * rx * 1.4
        y = cy - ry * 0.5
        r = 0.6 + 1.6 * hash01(j, 2, 43) * min(1.0, f / 0.6) * min(1.0, p.puddle * 1.5)
        if f < 0.75:
            for yy in range(int(y - r) - 1, int(y) + 1):
                for xx in range(int(x - r) - 1, int(x + r) + 2):
                    if math.hypot(xx + 0.5 - x, yy + 0.5 - y) <= r:
                        cv.put(xx, yy, BREW[3] if xx < x else BREW[2])
        elif f < 0.9:
            cv.put(int(x), int(y) - 2, BREW[3], solid=False)


def draw_spill(cv: Canvas, p: Pose) -> None:
    """Brew pouring out of the tipped cauldron's mouth onto the floor."""
    if p.spill <= 0:
        return
    piv_x, piv_y = CAUL_X - 14.5, GROUND + 1
    ca, sa = math.cos(p.tilt), math.sin(p.tilt)
    # the rim's left end (local q = -15.6, hh = 18.2 + 1) rotated forward
    X, Y = -15.6 + 14.5, 18.2 + 1 - p.sink
    mx = piv_x + X * ca + Y * sa
    my = piv_y - (-X * sa + Y * ca)
    n = int(max(1, GROUND - my))
    for i in range(n):
        t = i / max(1, n)
        x = mx - 3 * t - 1.5 * math.sin(t * 3 + p.phase * 3)
        y = my + i
        w = 1 + int(2 * t * p.spill)
        for k in range(-w, w + 1):
            cv.put(int(x) + k, int(y), BREW[3] if k == -w + 1 else BREW[2] if abs(k) < w else BREW[1])
    for j in range(8):
        a = math.pi + (hash01(j, 1, 47) - 0.5) * 1.6
        d = 4 + 10 * hash01(j, 2, 47) * p.spill
        cv.put(int(mx - 3 + math.cos(a) * d), int(GROUND - 2 - abs(math.sin(a)) * d * 0.5), BREW[3], solid=False)


# ---------------------------------------------------------------- render
def render(p: Pose, t: float = 0.0) -> Canvas:
    cv = Canvas(CELL_W, CELL_H)
    if p.dissolve >= 1.0:
        return cv
    b = Body(p)
    draw_ring(cv, p, t)
    draw_runes(cv, p, front=False)
    melting = p.melt > 0
    draw_mass(cv, b, "body" if melting else "all")
    if not melting:
        draw_hat_tip(cv, b)
    draw_pouch(cv, b, p)
    draw_tatters(cv, b, p)
    eye_c = draw_face(cv, b, p) if p.melt < 0.35 else None
    if p.melt < 0.5:
        draw_hair_strands(cv, b, p)
    if melting:
        draw_puddle(cv, p)
        hb = Body(p, hat_pass=True)
        draw_mass(cv, hb, "hat")
        draw_hat_tip(cv, hb)
    # far arm (doll / vial / raised hand), in front of the body, darker
    doll_c = None
    if p.both > 0.5:
        hb_ = (CX + p.dx + p.hand_b[0], GROUND + p.dy - p.hand_b[1])
        gx, gy = draw_arm(cv, b, hb_, back=True)
        if p.doll > 0.5:
            doll_c = draw_doll(cv, gx, gy - 1, p.pins, 1.0, p.hexflash)
        if p.vial > 0.5:
            draw_vial(cv, gx - 1, gy)
    # cauldron, staff, front arm
    czones: dict = {}
    if p.dissolve < 1:
        draw_cauldron(cv, p, czones)
    top, up = draw_staff(cv, p, czones)
    if p.melt < 0.3:
        if p.grip >= 0:
            pts, _ = staff_points(p)
            i = int(round(p.grip * (len(pts) - 1)))
            hand = pts[i]
            hand = (hand[0], hand[1])
        else:
            hand = (CX + p.dx + p.hand_f[0], GROUND + p.dy - p.hand_f[1])
        hx, hy = draw_arm(cv, b, hand, back=False, grip=p.grip >= 0)
        if p.pin > 0 and doll_c is not None:
            draw_pin(cv, hx - 1, hy - 1, doll_c[0], doll_c[1])
    draw_spill(cv, p)
    # the cauldron is a prop: it does not flash white with her
    keep = {(k[1], k[2]) for k, c in czones.items() if k[0] == "c"
            and cv.px[k[2]][k[1]] is not None and cv.px[k[2]][k[1]][:3] == c}
    outline(cv, OUTLINE)
    # lights
    bx, by = brew_surface(p)
    if p.tilt < 0.4:
        cv.glow(bx, by - 2, 22 + 6 * p.brew, BREW[1], 0.22 * p.brew, halo=False)
        cv.glow(bx, by, 9, BREW[2], 0.25 * p.brew)
    if eye_c is not None and p.eye > 0.05:
        cv.glow(eye_c[0], eye_c[1], 4 + 3 * p.eye, BREW[2], 0.3 * p.eye, halo=p.eye > 1.2)
    if p.flame > 0.05:
        fx, fy, _, _ = flame_point(p)
        cv.glow(fx, fy, 6 + 3 * p.flame, mix(BREW[2], HEX[2], p.flame_hex), 0.3 * p.flame)
        draw_flame(cv, p)
    draw_bubbles(cv, p)
    draw_steam(cv, p)
    if doll_c is not None:
        draw_hexflash(cv, doll_c[0], doll_c[1], p.hexflash)
    draw_runes(cv, p, front=True)
    draw_bolt(cv, p)
    draw_heal(cv, p)
    draw_goo(cv, p, b)
    for (mx, my, kind) in p.motes:
        col = GOO[min(3, int(kind))] if kind < 4 else BREW[4]
        cv.put(int(mx), int(my), col, solid=False)
    if p.flash > 0:
        saved = {(x, y): cv.px[y][x] for (x, y) in keep}
        flash(cv, p.flash)
        for (x, y), c in saved.items():
            cv.px[y][x] = c
    if p.dissolve > 0:
        dissolve(cv, p.dissolve, GROUND - 26, GROUND + 3, BREW[3], BREW[1], upward=False, seed=9)
    return cv


# ---------------------------------------------------------------- animations
IDLE_FRAMES = 12


def idle_pose(i: int, n: int = IDLE_FRAMES) -> Pose:
    i %= n
    a = math.tau * i / n
    cackle = {3: 0.5, 4: 1.0, 5: 0.6}.get(i, 0.0)
    return Pose(
        lean=round(math.sin(a)), dy=-1 if i == 4 else 0, phase=a, sway=1.0, mouth=cackle,
        hunch=-1 if i in (3, 4, 5) else 0,
        eye=0.75 if i == 9 else 1.0, flame=1.0 + 0.25 * math.sin(3 * a),
        brew=1.0 + 0.15 * math.sin(2 * a),
    )


def idle_frames():
    return [(idle_pose(i), 110) for i in range(IDLE_FRAMES)]


def _skull_tip(p: Pose):
    x, y, _, _ = flame_point(p)
    return x, y


def attack_frames():
    """Rayo de Ciénaga: draw the staff back, thrust it, a swamp bolt flies left and splashes."""
    b = idle_pose(0)
    thrust = replace(b, dx=-3, lean=-5, hunch=-2, staff_bot=(-12.0, 46.0), staff_top=(-64.0, 62.0),
                     grip=0.45, flame=2.0, eye=1.5, mouth=0.8, phase=1.3)
    src = _skull_tip(thrust)
    poses = [
        (replace(b, dx=1, lean=3, hunch=1, staff_bot=(-28.0, 18.0), staff_top=(-20.0, 78.0), grip=0.45,
                 flame=1.5, eye=1.25, mouth=0.3, phase=0.3), 100),
        (replace(b, dx=2, lean=5, hunch=2, staff_bot=(-26.0, 30.0), staff_top=(-6.0, 86.0), grip=0.4,
                 flame=2.0, flame_hex=0.3, eye=1.5, mouth=0.5, phase=0.6, steam=0.6), 130),
        (replace(thrust, bolt=0.0, bolt_from=src), 55),
        (replace(thrust, bolt=0.5, bolt_from=src, flame=1.4, phase=1.6), 50),
        (replace(thrust, bolt=1.0, bolt_from=src, impact=0.15, flame=1.2, mouth=1.0, phase=1.9), 60),
        (replace(thrust, dx=-2, lean=-4, bolt=1.0, bolt_from=src, impact=0.55, flame=1.1, mouth=1.0,
                 phase=2.3, staff_bot=(-14.0, 40.0), staff_top=(-60.0, 66.0)), 80),
        (replace(b, dx=-1, lean=-3, hunch=-1, staff_bot=(-22.0, 28.0), staff_top=(-46.0, 74.0), grip=0.42,
                 bolt=1.0, bolt_from=src, impact=0.9, mouth=0.6, phase=2.9), 90),
        (replace(b, lean=-2, staff_bot=(-28.0, 19.0), staff_top=(-34.0, 75.0), grip=0.45, mouth=0.3,
                 phase=3.7), 90),
        (replace(b, lean=-1, phase=4.6), 90),
        (b, 100),
    ]
    return poses


ATTACK_STRIKE = 4


def voodoo_frames():
    """Muñeco Vudú: the doll comes out, three pin stabs (purple flash each), cackling."""
    b = idle_pose(0)
    doll_at = (-27.0, 33.0)
    base = replace(b, both=1.0, doll=1.0, grip=-1.0, staff_bot=(-40.0, 15.0), staff_top=(-47.0, 72.0))
    up = (-13.0, 52.0)
    hit = (-19.0, 41.0)
    out = [
        (replace(b, both=1.0, doll=1.0, hand_b=(-17.0, 32.0), mouth=0.4, eye=1.1, phase=0.3), 100),
        (replace(base, hand_b=doll_at, hand_f=up, pin=1.0, eye=1.3, mouth=0.6, lean=1, phase=0.6), 130),
    ]
    stabs = [(2, 0.9), (4, 1.0), (6, 1.3)]
    for n, (_, k) in enumerate(stabs):
        out.append((replace(base, hand_b=doll_at, hand_f=hit, pin=1.0, pins=n, hexflash=k, eye=1.6,
                            mouth=0.4, lean=-1, hunch=-1, phase=1.0 + n), 55 if n < 2 else 60))
        if n < 2:
            out.append((replace(base, hand_b=doll_at, hand_f=up, pin=1.0, pins=n + 1, hexflash=0.3,
                                eye=1.2, mouth=1.0, dy=-1, lean=1, phase=1.5 + n), 90))
    out += [
        (replace(base, hand_b=(-28.0, 35.0), hand_f=(-14.0, 48.0), pins=3, hexflash=0.45, eye=1.4,
                 mouth=1.0, dy=-1, phase=4.0), 110),
        (replace(base, hand_b=(-20.0, 32.0), hand_f=(-15.0, 44.0), pins=3, mouth=0.6, phase=4.6,
                 staff_bot=(-35.0, 15.0), staff_top=(-38.0, 74.0)), 90),
        (replace(b, both=1.0, hand_b=(-8.0, 33.0), mouth=0.3, phase=5.3), 90),
        (b, 100),
    ]
    return out


VOODOO_STRIKES = [2, 4, 6]


def brew_frames():
    """Caldero Burbujeante: stir the cauldron, big bubbles, a steam burst, then sip a vial."""
    b = idle_pose(0)
    out = [(replace(b, lean=-2, hunch=-1, staff_bot=(-36.0, 17.0), staff_top=(-26.0, 74.0), grip=0.42,
                    swirl=0.4, bubbles=1.3, phase=0.4, mouth=0.3), 100)]
    for k in range(4):
        a = k / 4 * math.tau
        out.append((replace(b, lean=-2 + round(math.sin(a)), hunch=-1, dy=0,
                             staff_bot=(-37.0 + 6 * math.cos(a), 17.0 + 0.8 * math.sin(a)),
                             staff_top=(-25.0 + 5 * math.cos(a), 73.0), grip=0.42, swirl=1.0 + 0.3 * k,
                             bubbles=1.5 + 0.2 * k, brew=1.3 + 0.1 * k, steam=1.4, mouth=0.6 * (k % 2),
                             phase=0.8 + 0.6 * k), 85))
    out += [
        (replace(b, lean=1, hunch=1, staff_bot=(-30.0, 26.0), staff_top=(-28.0, 82.0), grip=0.4,
                 swirl=1.6, bubbles=2.0, brew=1.8, burst=0.35, splash=0.3, steam=0.0, mouth=1.0,
                 eye=1.4, phase=3.4), 90),
        (replace(b, lean=2, hunch=2, both=1.0, vial=1.0, hand_b=(-20.0, 52.0), swirl=0.8, bubbles=1.4,
                 brew=1.4, burst=0.7, splash=0.7, steam=0.0, mouth=0.4, eye=1.3, phase=4.0, heal=0.2), 120),
        (replace(b, lean=2, hunch=3, both=1.0, vial=1.0, hand_b=(-19.0, 54.0), swirl=0.4, brew=1.3,
                 burst=0.95, steam=0.3, mouth=0.4, eye=1.6, phase=4.5, heal=0.55), 120),
        (replace(b, lean=1, hunch=1, both=1.0, vial=1.0, hand_b=(-12.0, 44.0), brew=1.15, mouth=0.8,
                 eye=1.3, phase=5.0, heal=0.85, steam=0.6), 90),
        (replace(b, both=1.0, hand_b=(-4.0, 37.0), phase=5.6, mouth=0.3), 90),
        (b, 100),
    ]
    return out


def cast_frames():
    """Maleficio: both arms up, hex sigils swirl, a hex circle, then they fly at the hero."""
    b = idle_pose(0)
    out = []
    plan = [  # (up, runes, ring, fling)
        (0.4, 0.0, 0.0, 0.0), (0.85, 0.3, 0.3, 0.0), (1.0, 0.7, 0.7, 0.0), (1.0, 1.0, 1.0, 0.0),
        (1.0, 1.0, 1.0, 0.0), (0.9, 1.0, 0.8, 0.45), (0.6, 0.7, 0.45, 0.9), (0.3, 0.0, 0.15, 0.0),
    ]
    durs = [90, 100, 90, 90, 90, 70, 80, 90]
    for k, (u, r, g, f) in enumerate(plan):
        out.append((replace(
            b, lean=round(2 * u) if f == 0 else -2, hunch=round(2 * u) if f == 0 else -1, dy=-round(u),
            staff_bot=(lerp(-31, -24, u), lerp(15, 40, u)), staff_top=(lerp(-30, -36, u), lerp(74, 96, u)),
            grip=0.45, both=1.0 if u > 0.3 else 0.0, hand_b=(lerp(-2, 12, u), lerp(37, 74, u)),
            flame=1.0 + u, flame_hex=u, eye=1.0 + 0.8 * u, mouth=0.5 + 0.5 * u if k % 2 else 0.4,
            runes=r, rune_rot=0.55 * k, ring=g, fling=f, phase=0.5 * k, steam=1.0 - 0.6 * u), durs[k]))
    out.append((b, 100))
    return out


def hurt_frames():
    b = idle_pose(0)
    return [
        (replace(b, dx=3, lean=4, hunch=2, sx=0.96, sy=1.02, flash=0.82, eye=0.4, mouth=1.0, hat_flop=1.0,
                 goo=0.2, staff_top=(-28.0, 75.0), phase=1.0), 60),
        (replace(b, dx=4, lean=5, hunch=2, flash=0.5, eye=0.6, mouth=1.0, hat_flop=1.2, goo=0.5,
                 staff_top=(-27.0, 75.0), phase=1.6), 70),
        (replace(b, dx=3, lean=3, hunch=1, flash=0.18, eye=0.8, mouth=0.6, hat_flop=0.7, goo=0.8,
                 phase=2.2), 80),
        (replace(b, dx=2, lean=2, mouth=0.3, hat_flop=0.3, goo=1.0, phase=3.0), 85),
        (replace(b, dx=1, lean=1, hat_flop=0.1, phase=3.9), 90),
        (replace(b, lean=0, phase=5.0), 95),
        (b, 105),
    ]


def death_frames():
    b = idle_pose(0)
    out = [
        (replace(b, dx=3, lean=4, hunch=2, flash=0.85, eye=0.5, mouth=1.0, hat_flop=1.0, goo=0.3), 70),
        (replace(b, dx=1, lean=2, sy=1.05, hunch=3, eye=2.0, mouth=1.0, both=1.0, hand_b=(11.0, 72.0),
                 staff_top=(-30.0, 78.0), flame=1.6, flash=0.2, phase=0.6), 110),
        (replace(b, dx=1, lean=1, sy=1.04, hunch=3, eye=1.8, mouth=1.0, both=1.0, hand_b=(12.0, 74.0),
                 flame=1.2, tilt=0.12, brew=1.4, phase=1.2), 110),
    ]
    steps = 8
    for k in range(steps):
        u = (k + 1) / steps
        motes = tuple((CX - 30 + hash01(k, j, 51) * 50, GROUND - 6 - hash01(j, k, 52) * 30 * u - 6 * u,
                       1 + int(hash01(j, k, 53) * 3) + (j % 4 == 0)) for j in range(4 + k))
        sf = smooth(min(1.0, u * 1.7))
        out.append((replace(b, melt=u, puddle=0.15 + 0.85 * u, mouth=1.0, eye=1.5 * (1 - u), flame=1 - sf,
                            staff_bot=(lerp(-31, -22, sf), lerp(15, 2, sf)),
                            staff_top=(lerp(-30, -84, sf), lerp(74, 3, sf)),
                            tilt=0.12 + 0.95 * smooth(min(1.0, u * 1.4)), spill=min(1.0, u * 2.0) * (1 - u * 0.6),
                            sink=10 * max(0.0, u - 0.55), brew=1.0 - 0.6 * u, steam=0.0, bubbles=0.0,
                            phase=1.6 + 0.6 * k, motes=motes), 80))
    for k, (d, s) in enumerate(((0.3, 13), (0.55, 16), (0.8, 18))):
        motes = tuple((CX - 40 + hash01(k, j, 54) * 56, GROUND - 4 - hash01(j, k, 55) * 26,
                       1 + int(hash01(j, k, 56) * 3)) for j in range(8 - 2 * k))
        out.append((replace(b, melt=1.0, puddle=1.0, tilt=1.07, sink=s, eye=0.0, flame=0.0, brew=0.3, steam=0.0,
                            staff_bot=(-22.0, 2.0), staff_top=(-84.0, 3.0),
                            bubbles=0.0, phase=7.0 + 0.7 * k, dissolve=d, motes=motes), 90))
    out.append((replace(b, melt=1.0, puddle=1.0, dissolve=1.0, staff_bot=(-22.0, 2.0), staff_top=(-84.0, 3.0)),
                120))
    return out


ANIMATIONS = {
    "idle": (idle_frames, True),
    "attack": (attack_frames, False),
    "voodoo": (voodoo_frames, False),
    "brew": (brew_frames, False),
    "cast": (cast_frames, False),
    "hurt": (hurt_frames, False),
    "death": (death_frames, False),
}

EVENTS = {"attack": {"strikes": [ATTACK_STRIKE]}, "voodoo": {"strikes": VOODOO_STRIKES}}
MOVES = {"bolt": "attack", "voodoo": "voodoo", "cauldron": "brew", "potion": "brew", "hex": "cast",
         "vengeance": "cast"}


def build():
    return build_sheet(ANIMATIONS, render, (CELL_W, CELL_H), ANCHOR, f"{SHEET_ID}_sheet.png",
                       {"events": EVENTS, "moves": MOVES, "boss": True, "elite": True})


def main() -> None:
    sheet, meta = build()
    save_sheet(OUT_DIR, SHEET_ID, sheet, meta)
    print(f"wrote assets/enemies/{SHEET_ID}_sheet.png ({len(sheet[0])}x{len(sheet)}) and .json")


if __name__ == "__main__":
    main()
