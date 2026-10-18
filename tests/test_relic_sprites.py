"""Own relic sprites (``scripts/generate_relic_sprites.py`` → ``assets/relics``).

Every drawn relic is a real relic, its PNG exists, is 32×32 with transparency, the generator
reproduces the shipped files, and ``SpriteLoader.get_relic_sprite`` prefers it.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pygame
import pytest

from src.application.run_manager import _all_relic_defs
from src.infrastructure.sprite_loader import RELIC_OWN_DIR, SpriteLoader, own_relic_sprites

SCRIPTS = Path(__file__).parent.parent / "scripts"
INDEX = json.loads((RELIC_OWN_DIR / "relics.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module", autouse=True)
def _display():
    pygame.init()
    pygame.display.set_mode((1, 1))


def test_every_entry_is_a_relic():
    names = {r.name for r in _all_relic_defs()}
    assert set(INDEX) <= names


@pytest.mark.parametrize("name", sorted(INDEX))
def test_file_is_32_with_transparency(name):
    img = pygame.image.load(str(RELIC_OWN_DIR / INDEX[name]))
    assert img.get_size() == (32, 32)
    assert img.get_at((0, 0)).a == 0


def test_generator_matches_files():
    sys.path.insert(0, str(SCRIPTS))
    import relic_art                                   # noqa: E402
    from pixel_kit import write_png                    # noqa: E402,F401
    assert set(relic_art.ART) == set(INDEX)
    for name, fn in relic_art.ART.items():
        cv = fn()
        img = pygame.image.load(str(RELIC_OWN_DIR / INDEX[name]))
        for y in range(0, 32, 3):
            for x in range(0, 32, 3):
                c = cv.px[y][x]
                assert tuple(img.get_at((x, y))) == ((0, 0, 0, 0) if c is None else tuple(c))


def test_loader_prefers_own_sprite():
    name = next(iter(INDEX))
    loader = SpriteLoader()
    surf = loader.get_relic_sprite(name, 64)
    assert surf is not None and surf.get_size() == (64, 64)
    assert name in own_relic_sprites()
