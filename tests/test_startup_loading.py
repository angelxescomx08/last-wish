"""The first frame is presented before blocking asset preparation begins."""
from types import SimpleNamespace

import pygame
import pytest

import main
from src.infrastructure.fonts import FontRegistry
from src.infrastructure.preferences import UserPreferences
from src.infrastructure.viewport import Viewport


@pytest.fixture
def startup(monkeypatch):
    calls = []
    monkeypatch.setattr(main, "load_preferences", lambda: UserPreferences())
    monkeypatch.setattr(main, "load_dev_settings", lambda: None)
    class Sound:
        def __init__(self, **kwargs):
            calls.append("sound")
        def start_music(self):
            calls.append("music")
        def stop_music(self):
            calls.append("stop")
    monkeypatch.setattr(main, "SoundPlayer", Sound)
    monkeypatch.setattr(main, "MainMenuScene", lambda *args, **kwargs: object())
    def manager(*args, **kwargs):
        return SimpleNamespace(draw=lambda surface: calls.append("menu_draw"))
    monkeypatch.setattr(main, "SceneManager", manager)
    monkeypatch.setattr(pygame.event, "get", lambda: [])
    monkeypatch.setattr(pygame.display, "flip", lambda: calls.append("flip"))
    return calls


def test_loading_frame_precedes_assets_and_completion_follows_menu(startup, monkeypatch):
    def prewarm(progress):
        assert "flip" in startup
        startup.append("assets")
        progress("Preparando cartas...", .1)
    monkeypatch.setattr(main, "_prewarm_assets", prewarm)
    result = main._load_game(pygame.Surface((1280, 720)), Viewport(1280, 720), FontRegistry())
    assert result is not None
    assert startup.index("flip") < startup.index("assets") < startup.index("menu_draw")
    assert startup[-1] == "flip"


def test_close_before_loading_does_not_decode_assets(startup, monkeypatch):
    monkeypatch.setattr(pygame.event, "get", lambda: [pygame.event.Event(pygame.QUIT)])
    monkeypatch.setattr(main, "_prewarm_assets", lambda *args: pytest.fail("Loading cancelled"))
    assert main._load_game(pygame.Surface((1280, 720)), Viewport(1280, 720), FontRegistry()) is None
    assert "sound" not in startup


def test_close_after_audio_releases_music(startup, monkeypatch):
    monkeypatch.setattr(main, "_prewarm_assets", lambda progress: None)
    def events():
        return [pygame.event.Event(pygame.QUIT)] if "sound" in startup else []
    monkeypatch.setattr(pygame.event, "get", events)
    assert main._load_game(pygame.Surface((1280, 720)), Viewport(1280, 720), FontRegistry()) is None
    assert startup[-1] == "stop"


def test_cancel_between_hero_loads_stops_remaining_assets(monkeypatch):
    from src.infrastructure import card_assets, sprite_loader
    monkeypatch.setattr(card_assets, "prewarm", lambda sizes: None)
    loaded = []
    monkeypatch.setattr(sprite_loader.SpriteLoader, "get_player_animation_frames",
                        lambda *args: loaded.append(args))
    def progress(label, fraction):
        if len(loaded) == 2:
            raise main._StartupCancelled()
    with pytest.raises(main._StartupCancelled):
        main._prewarm_assets(progress)
    assert len(loaded) == 2


def test_run_quits_cleanly_when_loading_is_cancelled(monkeypatch):
    stopped = []
    monkeypatch.setattr(main, "_load_game", lambda *args: None)
    monkeypatch.setattr(pygame.display, "set_mode", lambda *args: pygame.Surface((1280, 720)))
    monkeypatch.setattr(pygame, "quit", lambda: stopped.append(True))
    main.run(main.GameSettings(1280, 720, 60, "Last Wish"))
    assert stopped == [True]
