"""Tests for src/infrastructure/sprite_loader.py.

Covers: mapping completeness, file existence, unknown-name fallback, and
cache deduplication.  No pygame initialisation required — file-existence
checks use pathlib only; cache checks inspect internal state.
"""
from __future__ import annotations

from pathlib import Path

from src.infrastructure.sprite_loader import (
    CARD_ART_PATHS,
    ENEMY_SPRITE_PATHS,
    PACK_SPRITE_PATHS,
    PLAYER_SPRITE_PATHS,
    RARITY_BADGE_PATHS,
    RELIC_SPRITE_PATHS,
    SpriteLoader,
    _ASSETS,
    _CARD_ASSETS,
)

# ---------------------------------------------------------------------------
# Mapping completeness
# ---------------------------------------------------------------------------

_EXPECTED_PLAYERS = {"El Guerrero", "El Mago", "El Pícaro"}
_EXPECTED_ENEMIES = {
    "Cultista", "Guardián", "Brujo", "Esqueleto",
    "Golem", "Asesino", "Señor de la Cripta",
}
_EXPECTED_RELICS = {
    "Amuleto de Combate", "Tótem Roto", "Orbe de Fuego", "Escudo Espectral",
    "Piedra de Energía", "Anillo de Oro", "Corazón de Hierro", "Poción de Sangre",
}


class TestMappingCompleteness:
    def test_all_player_names_mapped(self):
        assert _EXPECTED_PLAYERS == set(PLAYER_SPRITE_PATHS.keys())

    def test_all_enemy_names_mapped(self):
        assert _EXPECTED_ENEMIES == set(ENEMY_SPRITE_PATHS.keys())

    def test_all_relic_names_mapped(self):
        assert _EXPECTED_RELICS == set(RELIC_SPRITE_PATHS.keys())

    def test_no_empty_player_paths(self):
        assert all(v for v in PLAYER_SPRITE_PATHS.values())

    def test_no_empty_enemy_paths(self):
        assert all(v for v in ENEMY_SPRITE_PATHS.values())

    def test_no_empty_relic_paths(self):
        assert all(v for v in RELIC_SPRITE_PATHS.values())


# ---------------------------------------------------------------------------
# Asset files exist on disk
# ---------------------------------------------------------------------------

class TestCardAssets:
    def test_card_assets_dir_exists(self):
        assert _CARD_ASSETS.is_dir()

    def test_card_art_paths_all_exist(self):
        for card_id, rel in CARD_ART_PATHS.items():
            assert (_CARD_ASSETS / rel).is_file(), f"Missing art for {card_id!r}: {rel}"

    def test_rarity_badge_paths_all_exist(self):
        for rarity, rel in RARITY_BADGE_PATHS.items():
            assert (_CARD_ASSETS / rel).is_file(), f"Missing badge for {rarity!r}: {rel}"

    def test_pack_sprite_paths_all_exist(self):
        for theme, rel in PACK_SPRITE_PATHS.items():
            assert (_CARD_ASSETS / rel).is_file(), f"Missing pack sprite for {theme!r}: {rel}"

    def test_rarity_badges_cover_all_five_tiers(self):
        assert set(RARITY_BADGE_PATHS.keys()) == {
            "COMMON", "UNCOMMON", "RARE", "EPIC", "LEGENDARY"
        }

    def test_pack_sprites_cover_all_themes(self):
        assert set(PACK_SPRITE_PATHS.keys()) == {"acero", "escudo", "magia", "epico"}

    def test_unknown_card_art_returns_none(self):
        loader = SpriteLoader()
        assert loader.get_card_art("carta_inexistente", size=32) is None

    def test_unknown_rarity_badge_returns_none(self):
        loader = SpriteLoader()
        assert loader.get_rarity_badge("MYTHIC", size=16) is None

    def test_unknown_pack_returns_none(self):
        loader = SpriteLoader()
        assert loader.get_pack_sprite("oscuro", size=80) is None


class TestAssetFilesExist:
    def test_player_sprites_exist(self):
        for name, rel in PLAYER_SPRITE_PATHS.items():
            assert (_ASSETS / rel).is_file(), f"Missing sprite for {name!r}: {rel}"

    def test_enemy_sprites_exist(self):
        for name, rel in ENEMY_SPRITE_PATHS.items():
            assert (_ASSETS / rel).is_file(), f"Missing sprite for {name!r}: {rel}"

    def test_relic_sprites_exist(self):
        for name, rel in RELIC_SPRITE_PATHS.items():
            assert (_ASSETS / rel).is_file(), f"Missing relic icon for {name!r}: {rel}"

    def test_assets_dir_exists(self):
        assert _ASSETS.is_dir()


# ---------------------------------------------------------------------------
# Unknown-name fallback (no pygame needed — dict.get returns None early)
# ---------------------------------------------------------------------------

class TestUnknownNameFallback:
    def test_unknown_player_returns_none(self):
        loader = SpriteLoader()
        assert loader.get_player_sprite("Desconocido", size=32) is None

    def test_unknown_enemy_returns_none(self):
        loader = SpriteLoader()
        assert loader.get_enemy_sprite("Monstruo", size=32) is None

    def test_unknown_relic_returns_none(self):
        loader = SpriteLoader()
        assert loader.get_relic_sprite("Reliquia Falsa", size=32) is None

    def test_empty_string_player_returns_none(self):
        loader = SpriteLoader()
        assert loader.get_player_sprite("", size=32) is None

    def test_empty_string_enemy_returns_none(self):
        loader = SpriteLoader()
        assert loader.get_enemy_sprite("", size=32) is None

    def test_empty_string_relic_returns_none(self):
        loader = SpriteLoader()
        assert loader.get_relic_sprite("", size=32) is None


# ---------------------------------------------------------------------------
# Cache behaviour (internal state inspection, no pygame)
# ---------------------------------------------------------------------------

class TestCacheBehaviour:
    def test_cache_starts_empty(self):
        loader = SpriteLoader()
        assert len(loader._cache) == 0

    def test_unknown_name_does_not_populate_cache(self):
        loader = SpriteLoader()
        loader.get_player_sprite("Ghost", size=32)
        assert len(loader._cache) == 0

    def test_all_player_paths_are_strings(self):
        for path in PLAYER_SPRITE_PATHS.values():
            assert isinstance(path, str)

    def test_all_enemy_paths_are_strings(self):
        for path in ENEMY_SPRITE_PATHS.values():
            assert isinstance(path, str)

    def test_all_player_paths_end_with_png(self):
        for path in PLAYER_SPRITE_PATHS.values():
            assert path.endswith(".png")

    def test_all_enemy_paths_end_with_png(self):
        for path in ENEMY_SPRITE_PATHS.values():
            assert path.endswith(".png")

    def test_all_relic_paths_are_strings(self):
        for path in RELIC_SPRITE_PATHS.values():
            assert isinstance(path, str)

    def test_all_relic_paths_end_with_png(self):
        for path in RELIC_SPRITE_PATHS.values():
            assert path.endswith(".png")
