"""Startup loading feedback renders without loading game artwork."""
import pygame
import pytest

from src.infrastructure.fonts import FontRegistry
from src.infrastructure.viewport import Viewport
from src.presentation.ui.loading_screen import LoadingScreen


@pytest.mark.parametrize("progress", [-1, 0, .5, 1, 2])
def test_loading_draws_without_asset_loads(monkeypatch, progress):
    def unexpected_load(*args):
        pytest.fail("Loading feedback must not depend on game artwork")
    monkeypatch.setattr(pygame.image, "load", unexpected_load)
    screen = LoadingScreen(FontRegistry())
    surface = pygame.Surface((1280, 720))
    screen.draw(surface, "Preparando la aventura...", progress)
    assert surface.get_at((0, 0)) != (0, 0, 0, 255)
    assert pygame.mask.from_threshold(surface, (215, 180, 75), (1, 1, 1, 255)).count() > 100


def test_quit_during_loading_skips_presentation(monkeypatch):
    monkeypatch.setattr(pygame.event, "get", lambda: [pygame.event.Event(pygame.QUIT)])
    monkeypatch.setattr(pygame.display, "flip", lambda: pytest.fail("Must close immediately"))
    assert not LoadingScreen(FontRegistry()).present(
        pygame.Surface((1280, 720)), Viewport(1280, 720), "Cargando...", .2)


def test_resize_during_loading_preserves_letterbox(monkeypatch):
    monkeypatch.setattr(pygame.event, "get", lambda: [
        pygame.event.Event(pygame.WINDOWRESIZED, x=640, y=480)])
    flips = []
    monkeypatch.setattr(pygame.display, "flip", lambda: flips.append(True))
    viewport = Viewport(1280, 720)
    assert LoadingScreen(FontRegistry()).present(
        pygame.Surface((640, 480)), viewport, "Cargando...", .5)
    assert viewport._dest_w == 640 and viewport._dest_h == 360
    assert viewport._off_y == 60
    assert len(flips) == 1


def test_progress_changes_the_bar():
    loading = LoadingScreen(FontRegistry())
    empty = pygame.Surface((1280, 720))
    full = pygame.Surface((1280, 720))
    loading.draw(empty, "Cargando...", 0)
    loading.draw(full, "Cargando...", 1)
    assert empty.get_at((600, 412)) != full.get_at((600, 412))


def test_menu_after_loading_is_visible_on_its_first_draw():
    from src.presentation.scenes.main_menu_scene import MainMenuScene
    menu = MainMenuScene(FontRegistry(), fade_in=False)
    surface = pygame.Surface((1280, 720))
    menu.draw(surface)
    black = pygame.mask.from_threshold(surface, (0, 0, 0), (1, 1, 1, 255)).count()
    assert black < 1280 * 720 * .9
