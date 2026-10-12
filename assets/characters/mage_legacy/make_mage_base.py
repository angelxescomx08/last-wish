"""Kept for reference: the mage conversion now lives in make_hero_base.py.

    uv run --with pillow --with numpy python scripts/make_hero_base.py mage
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from make_hero_base import HEROES, PEEL, convert  # noqa: E402

if __name__ == "__main__":
    convert("mage", HEROES["mage"], PEEL["mage"])
