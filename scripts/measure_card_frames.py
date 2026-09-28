"""Measure the content zones of the card frames in assets/cards-v2 (dev tool).

    uv run --with pillow --with numpy python scripts/measure_card_frames.py

Writes ``assets/cards-v2/layout.json`` with every zone as fractions of the
frame size, so the runtime renderer can place text and art at any card size.

* ``art``: bounding box of the transparent illustration window, found per frame
  by flood-filling the transparent pixels from the window centre (the margins
  differ slightly between frames, as the asset README warns).
* The other zones (mana circle, name plate, effect panel, stat circles) share
  one layout: they were read off a 5 % grid overlay of the frames and agree
  within ~1 % across rarities, i.e. about 1 px at the in-game card size.
"""
import json
from collections import deque
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
CARDS = ROOT / "assets" / "cards-v2"
RARITIES = ["common", "uncommon", "rare", "epic", "legendary"]

SHARED = {
    "mana":  {"cx": 0.137, "cy": 0.097, "r": 0.058},
    "name":  {"x0": 0.285, "y0": 0.080, "x1": 0.850, "y1": 0.146},
    "text":  {"x0": 0.150, "y0": 0.590, "x1": 0.850, "y1": 0.835},
    "attack": {"cx": 0.131, "cy": 0.889, "r": 0.056},
    "block": {"cx": 0.870, "cy": 0.889, "r": 0.056},
}


def art_window(path: Path) -> dict:
    a = np.asarray(Image.open(path).convert("RGBA"))[..., 3]
    h, w = a.shape
    seen = np.zeros_like(a, dtype=bool)
    start = (int(h * 0.33), w // 2)
    q = deque([start])
    seen[start] = True
    ys, xs = [], []
    while q:
        y, x = q.popleft()
        ys.append(y)
        xs.append(x)
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            ny, nx = y + dy, x + dx
            if 0 <= ny < h and 0 <= nx < w and not seen[ny, nx] and a[ny, nx] < 40:
                seen[ny, nx] = True
                q.append((ny, nx))
    return {"x0": round(min(xs) / w, 4), "y0": round(min(ys) / h, 4),
            "x1": round((max(xs) + 1) / w, 4), "y1": round((max(ys) + 1) / h, 4)}


def main() -> None:
    frames = {}
    for r in RARITIES:
        path = CARDS / "frames" / f"card_{r}.png"
        w, h = Image.open(path).size
        frames[r.upper()] = {"file": f"frames/card_{r}.png", "size": [w, h], "art": art_window(path)}
    layout = {"frames": frames, "zones": SHARED,
              "packs": {t: f"packs/pack_{t}.png" for t in ("acero", "escudo", "magia", "epico")}}
    (CARDS / "layout.json").write_text(json.dumps(layout, indent=2) + "\n", encoding="utf-8")
    print("wrote layout.json")


if __name__ == "__main__":
    main()
