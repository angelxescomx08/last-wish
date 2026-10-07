"""Card art for the status cards the Reina Micélida adds to your deck. Stdlib only:

    python scripts/generate_status_card_art.py

Writes ``assets/cards-v2/art/status_espora.png`` and ``status_moho.png``: small
pixel-art scenes (44×36 native, saved ×4 nearest) in the boss's toxic palette.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from pixel_kit import Canvas, bayer, hash01, outline, ramp, write_png  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
ART_DIR = ROOT / "assets" / "cards-v2" / "art"
W, H, SCALE = 44, 36, 4

BG = [(10, 16, 8), (18, 28, 12), (28, 42, 16), (40, 58, 22)]
TOX = [(40, 76, 22), (90, 160, 40), (170, 230, 70), (236, 255, 160)]
SPORE = [(120, 130, 60), (180, 196, 96), (226, 236, 150), (250, 255, 214)]
CAP = [(58, 14, 40), (96, 22, 58), (138, 32, 72), (178, 52, 84), (212, 92, 104)]
MOULD = [(30, 42, 22), (56, 78, 32), (92, 126, 46), (140, 176, 70), (196, 220, 120)]
OUTLINE = (8, 12, 6)


def _background(cv: Canvas) -> None:
    for y in range(H):
        for x in range(W):
            d = math.hypot((x - W / 2) / W, (y - H * 0.6) / H)
            cv.put(x, y, ramp(BG, max(0.0, 0.85 - d * 1.6), x, y, 0.8), solid=False)


def _blob(cv: Canvas, cx, cy, r, colors, solid=True) -> None:
    for y in range(int(cy - r) - 1, int(cy + r) + 2):
        for x in range(int(cx - r) - 1, int(cx + r) + 2):
            dx, dy = (x + 0.5 - cx) / r, (y + 0.5 - cy) / r
            d = dx * dx + dy * dy
            if d > 1:
                continue
            light = 0.75 - 0.35 * dx - 0.45 * dy - 0.2 * d
            cv.put(x, y, ramp(colors, max(0.0, min(1.0, light)), x, y), solid=solid)


def espora() -> Canvas:
    """A swollen spore pod bursting, with glowing spores drifting out."""
    cv = Canvas(W, H)
    _background(cv)
    pod = Canvas(W, H)
    _blob(pod, 22, 21, 9, CAP)
    for (sx, sy, r) in ((19, 17, 1.6), (25, 19, 1.2), (21, 24, 1.3), (27, 24, 1.0)):
        _blob(pod, sx, sy, r, SPORE)
    for x in range(17, 28):                              # the split where it bursts
        pod.put(x, 13 + int(1.5 * math.sin(x * 1.3)), TOX[2])
    outline(pod, OUTLINE)
    cv.blit(pod)
    for k in range(14):
        a = -math.pi * (0.15 + 0.7 * hash01(k, 1))
        d = 6 + 13 * hash01(k, 2)
        x, y = 22 + math.cos(a) * d * 1.3, 12 + math.sin(a) * d * 0.6
        lvl = 3 if hash01(k, 3) > 0.6 else 2
        cv.put(x, y, SPORE[lvl])
        if lvl == 3:
            for ox, oy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                cv.put(x + ox, y + oy, TOX[1], solid=False, alpha=150)
    return cv


def moho() -> Canvas:
    """A patch of fuzzy mould creeping over a stone, sucking the light (mana) out."""
    cv = Canvas(W, H)
    _background(cv)
    for y in range(24, H):                               # stone floor
        for x in range(W):
            if (x + (y // 5) * 3) % 11 == 0 or y % 6 == 0:
                cv.put(x, y, BG[0], solid=False)
    m = Canvas(W, H)
    for k, (cx, cy, r) in enumerate(((22, 25, 8), (14, 27, 5), (30, 27, 6), (19, 20, 5), (27, 21, 4))):
        _blob(m, cx, cy, r, MOULD)
    for y in range(H):                                   # fuzz on the edge
        for x in range(W):
            if m.get(x, y) is None and any(m.get(x + ox, y + oy) for ox, oy in ((1, 0), (-1, 0), (0, 1), (0, -1))):
                if bayer(x, y) > 0.5:
                    m.put(x, y, MOULD[3], solid=False)
    outline(m, OUTLINE)
    cv.blit(m)
    for k in range(6):                                   # a drained blue mana mote sinking in
        t = k / 5
        x, y = 22 + 6 * math.sin(t * 5), 6 + t * 14
        cv.put(x, y, (90 + int(60 * (1 - t)), 150 + int(60 * (1 - t)), 255), solid=False,
               alpha=int(255 * (1 - t * 0.7)))
    return cv


def save(cv: Canvas, path: Path) -> None:
    rows = []
    for y in range(H):
        row = []
        for x in range(W):
            c = cv.px[y][x]
            row += [c if c is not None else (0, 0, 0, 255)] * SCALE
        rows += [row] * SCALE
    write_png(path, rows)


def main() -> None:
    ART_DIR.mkdir(parents=True, exist_ok=True)
    save(espora(), ART_DIR / "status_espora.png")
    save(moho(), ART_DIR / "status_moho.png")
    print("wrote assets/cards-v2/art/status_espora.png and status_moho.png")


if __name__ == "__main__":
    main()
