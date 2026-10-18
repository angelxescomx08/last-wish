"""Hero assets survive scene changes without decoding or copying them again."""
from dataclasses import replace

import pygame
import pytest

from src.infrastructure import sprite_loader


@pytest.fixture
def hero_sheet(tmp_path, monkeypatch):
    source = pygame.Surface((16, 8), pygame.SRCALPHA)
    source.fill((30, 120, 210, 170))
    source.fill((240, 80, 20, 255), (8, 0, 8, 8))
    path = tmp_path / "hero.png"
    pygame.image.save(source, str(path))
    monkeypatch.setattr(sprite_loader, "_HERO_DIR", tmp_path)
    hero = replace(sprite_loader.HEROES["warrior"], cell=8, sheets={8: path.name},
                   animations={"idle": sprite_loader.HeroAnimation(0, (.1, .1), True)})
    monkeypatch.setitem(sprite_loader.HEROES, "cache_test", hero)
    return path, source


def test_frames_are_shared_between_scene_loaders(hero_sheet, monkeypatch):
    original = pygame.image.load
    opened = []
    def record(path):
        opened.append(path)
        return original(path)
    monkeypatch.setattr(pygame.image, "load", record)
    first = sprite_loader.SpriteLoader().get_player_animation_frames("idle", 16, "cache_test")
    second = sprite_loader.SpriteLoader().get_player_animation_frames("idle", 16, "cache_test")
    assert len(first) == 2
    assert first is second
    assert len(opened) == 1
    expected = pygame.transform.scale(hero_sheet[1].subsurface((0, 0, 8, 8)), (16, 16))
    assert pygame.image.tobytes(first[0], "RGBA") == pygame.image.tobytes(expected, "RGBA")


def test_different_sizes_reuse_decoded_sheet(hero_sheet, monkeypatch):
    original = pygame.image.load
    opened = []
    def record(path):
        opened.append(path)
        return original(path)
    monkeypatch.setattr(pygame.image, "load", record)
    small = sprite_loader.SpriteLoader().get_player_animation_frames("idle", 8, "cache_test")
    large = sprite_loader.SpriteLoader().get_player_animation_frames("idle", 16, "cache_test")
    assert small[0].get_size() == (8, 8)
    assert large[0].get_size() == (16, 16)
    assert len(opened) == 1


def test_changed_metadata_selects_new_file(hero_sheet, monkeypatch):
    first = sprite_loader.SpriteLoader().get_player_animation_frames("idle", 8, "cache_test")
    path = hero_sheet[0].with_name("replacement.png")
    replacement = pygame.Surface((16, 8), pygame.SRCALPHA)
    replacement.fill((1, 2, 3, 255))
    pygame.image.save(replacement, str(path))
    monkeypatch.setitem(sprite_loader.HEROES, "cache_test",
                        replace(sprite_loader.HEROES["cache_test"], sheets={8: path.name}))
    second = sprite_loader.SpriteLoader().get_player_animation_frames("idle", 8, "cache_test")
    assert second[0].get_at((0, 0)) == (1, 2, 3, 255)
    assert second is not first


def test_missing_sheet_returns_empty_frames(hero_sheet):
    hero_sheet[0].unlink()
    assert sprite_loader.SpriteLoader().get_player_animation_frames("idle", 8, "cache_test") == ()


def test_active_scene_keeps_frames_when_shared_cache_evicts_them(hero_sheet, monkeypatch):
    loader = sprite_loader.SpriteLoader()
    frames = loader.get_player_animation_frames("idle", 8, "cache_test")
    sprite_loader._shared_hero_frames.cache_clear()
    sprite_loader._shared_hero_sheet.cache_clear()
    def unexpected_load(path):
        pytest.fail("An active scene must keep its prepared animation frames")
    monkeypatch.setattr(pygame.image, "load", unexpected_load)
    assert loader.get_player_animation_frames("idle", 8, "cache_test") is frames
