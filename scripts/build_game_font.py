"""Build the game fonts: Pixel Operator + the symbols Last Wish uses, drawn as pixel glyphs.

    uv run scripts/build_game_font.py        (fonttools is a dev dependency)

Pixel Operator (Jayvee Enaguas, CC0 1.0 — public domain, no credit required) covers every
Spanish letter (á é í ó ú ñ ü ¿ ¡) but not a few symbols the UI prints (→ ← ↑ ↓ ↔ − ▲ ✓ ≤ ≥
≈ ⚙ ⛑). This script adds them, drawn on the font's own pixel grid (one pixel = 100 font
units in both versions), so the text never falls back to another font:

* ``assets/fonts/source/PixelOperator.ttf``  (16 px grid, cap 9 px)  → ``LastWish.ttf``
* ``assets/fonts/source/PixelOperator8.ttf`` (8 px grid, cap 7 px)   → ``LastWish8.ttf``
* the ``-Bold`` versions (same licence) → ``LastWish-Bold.ttf`` / ``LastWish8-Bold.ttf``; their
  symbols are thickened like the bold letters (every pixel also fills the one on its right).

Only needed when a new symbol is added; the game itself just loads the built TTFs.
"""
from __future__ import annotations

from pathlib import Path

from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont

FONTS = Path(__file__).resolve().parent.parent / "assets" / "fonts"
PIXEL = 100                       # font units per pixel (both versions)

# Each symbol: rows top → bottom ('#' = pixel) and the row of its bottom line on the
# 16 px font (0 = baseline). The 8 px font uses ``bottom8`` (its x-height is 2 px lower).
GLYPHS: dict[str, tuple[int, int, tuple[str, ...]]] = {
    "→": (2, 1, ("....#..",
                 ".....#.",
                 "#######",
                 ".....#.",
                 "....#..")),
    "←": (2, 1, ("..#....",
                 ".#.....",
                 "#######",
                 ".#.....",
                 "..#....")),
    "↑": (1, 0, ("..#..",
                 ".###.",
                 "#.#.#",
                 "..#..",
                 "..#..",
                 "..#..",
                 "..#..")),
    "↓": (1, 0, ("..#..",
                 "..#..",
                 "..#..",
                 "..#..",
                 "#.#.#",
                 ".###.",
                 "..#..")),
    "↔": (3, 2, (".#...#.",
                 "#######",
                 ".#...#.")),
    "−": (4, 3, ("#####",)),
    "▲": (2, 1, ("...#...",
                 "..###..",
                 ".#####.",
                 "#######")),
    "✓": (2, 1, ("......#",
                 ".....#.",
                 "#...#..",
                 ".#.#...",
                 "..#....")),
    "≤": (1, 0, ("...##",
                 ".##..",
                 "#....",
                 ".##..",
                 "...##",
                 ".....",
                 "#####")),
    "≥": (1, 0, ("##...",
                 "..##.",
                 "....#",
                 "..##.",
                 "##...",
                 ".....",
                 "#####")),
    "≈": (2, 1, (".##.#",
                 "#.##.",
                 ".....",
                 ".##.#",
                 "#.##.")),
    "⚙": (1, 0, (".#.#.#.",
                 "#######",
                 ".##.##.",
                 "###.###",
                 ".##.##.",
                 "#######",
                 ".#.#.#.")),
    "⛑": (1, 0, ("..###..",
                 ".#####.",
                 "###.###",
                 "#.....#",
                 "#.....#")),
}


def glyph_name(ch: str) -> str:
    return f"uni{ord(ch):04X}"


def draw(rows: tuple[str, ...], bottom: int):
    """A TrueType glyph made of one rectangle per horizontal run of pixels (+ its width)."""
    pen = TTGlyphPen(None)
    height = len(rows)
    for r, row in enumerate(rows):
        y = (bottom + height - 1 - r) * PIXEL
        c = 0
        while c < len(row):
            if row[c] != "#":
                c += 1
                continue
            start = c
            while c < len(row) and row[c] == "#":
                c += 1
            x0, x1 = (start + 1) * PIXEL, (c + 1) * PIXEL       # 1 px left bearing
            pen.moveTo((x0, y))
            pen.lineTo((x0, y + PIXEL))
            pen.lineTo((x1, y + PIXEL))
            pen.lineTo((x1, y))
            pen.closePath()
    width = max(len(row) for row in rows)
    return pen.glyph(), (width + 2) * PIXEL


def embolden(rows: tuple[str, ...]) -> tuple[str, ...]:
    """Bold like Pixel Operator Bold: each pixel also fills the one to its right (1 px wider)."""
    out = []
    for row in rows:
        row = row + "."
        out.append("".join("#" if row[i] == "#" or (i > 0 and row[i - 1] == "#") else "."
                           for i in range(len(row))))
    return tuple(out)


def build(source: Path, target: Path, *, small: bool, bold: bool = False) -> list[str]:
    font = TTFont(str(source))
    order = font.getGlyphOrder()
    added = []
    for ch, (bottom16, bottom8, rows) in GLYPHS.items():
        name = glyph_name(ch)
        glyph, advance = draw(embolden(rows) if bold else rows, bottom8 if small else bottom16)
        if name not in order:
            order.append(name)
        font["glyf"][name] = glyph
        font["hmtx"][name] = (advance, PIXEL)
        for table in font["cmap"].tables:
            if table.isUnicode():
                table.cmap[ord(ch)] = name
        added.append(ch)
    font.setGlyphOrder(order)
    font["maxp"].numGlyphs = len(order)
    font.save(str(target))
    return added


def main() -> None:
    for src, dst, small, bold in (("PixelOperator.ttf", "LastWish.ttf", False, False),
                                  ("PixelOperator8.ttf", "LastWish8.ttf", True, False),
                                  ("PixelOperator-Bold.ttf", "LastWish-Bold.ttf", False, True),
                                  ("PixelOperator8-Bold.ttf", "LastWish8-Bold.ttf", True, True)):
        added = build(FONTS / "source" / src, FONTS / dst, small=small, bold=bold)
        print(f"{dst}: +{len(added)} glyphs ({''.join(added)})")


if __name__ == "__main__":
    main()
