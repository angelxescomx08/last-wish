"""Own pixel-art sprites for the relics (``assets/relics/<slug>.png`` + ``relics.json``).

Every relic drawn in ``scripts/relic_art.py`` (one function per relic, keyed by its Spanish
name) becomes a 32×32 PNG; ``relics.json`` maps the relic name to its file and
``SpriteLoader.get_relic_sprite`` prefers it over the borrowed Dungeon Crawl item sprite.
Standard library only:

    python scripts/generate_relic_sprites.py               # every relic drawn so far
    python scripts/generate_relic_sprites.py "Ankh" ...    # only these
"""
from __future__ import annotations

import json
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from pixel_kit import write_png  # noqa: E402
import relic_art  # noqa: E402

OUT = Path(__file__).parent.parent / "assets" / "relics"


def slug(name: str) -> str:
    text = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    return "".join(c if c.isalnum() else "_" for c in text).strip("_")


def build(names: list[str] | None = None) -> dict[str, str]:
    OUT.mkdir(parents=True, exist_ok=True)
    index_path = OUT / "relics.json"
    index = json.loads(index_path.read_text(encoding="utf-8")) if index_path.is_file() else {}
    for name in names or list(relic_art.ART):
        cv = relic_art.ART[name]()
        file = f"{slug(name)}.png"
        write_png(OUT / file, cv.px)
        index[name] = file
    index = {k: index[k] for k in sorted(index)}
    index_path.write_text(json.dumps(index, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return index


if __name__ == "__main__":
    done = build(sys.argv[1:] or None)
    print(f"{len(done)} relic sprites -> {OUT}")
