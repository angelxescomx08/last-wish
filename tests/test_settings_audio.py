"""Audio preference persistence and validation."""
import json
from unittest.mock import Mock

import pygame
import pytest

import src.infrastructure.preferences as prefs_mod
from src.infrastructure.fonts import FontRegistry
from src.infrastructure.preferences import UserPreferences, load_preferences, save_preferences
from src.presentation.scenes.settings_scene import SettingsScene


def test_audio_defaults_are_quiet():
    prefs = UserPreferences()
    assert prefs.sfx_volume == 0.7
    assert prefs.music_volume == 0.35


@pytest.mark.parametrize("value", [None, "loud", True, [], {}, float("nan"), float("inf")])
def test_invalid_audio_values_use_defaults(value):
    prefs = UserPreferences(sfx_volume=value, music_volume=value)
    assert prefs.sfx_volume == 0.7
    assert prefs.music_volume == 0.35


def test_audio_values_are_clamped():
    prefs = UserPreferences(sfx_volume=-2, music_volume=4)
    assert prefs.sfx_volume == 0.0
    assert prefs.music_volume == 1.0


@pytest.fixture
def prefs_path(tmp_path, monkeypatch):
    path = tmp_path / "preferences.json"
    monkeypatch.setattr(prefs_mod, "_PREFS_FILE", path)
    return path


def test_legacy_preferences_keep_default_audio(prefs_path):
    prefs_path.write_text('{"show_fps": true}', encoding="utf-8")
    result = load_preferences()
    assert result.show_fps is True
    assert result.sfx_volume == 0.7
    assert result.music_volume == 0.35


@pytest.mark.parametrize("content", ["null", "[]", "42", '"text"'])
def test_non_object_json_returns_defaults(prefs_path, content):
    prefs_path.write_text(content, encoding="utf-8")
    assert load_preferences() == UserPreferences()


def test_invalid_loaded_audio_values_are_sanitized(prefs_path):
    prefs_path.write_text('{"sfx_volume": 20, "music_volume": "loud"}', encoding="utf-8")
    result = load_preferences()
    assert result.sfx_volume == 1.0
    assert result.music_volume == 0.35


def test_independent_audio_volumes_survive_save_and_load(prefs_path):
    prefs = UserPreferences(show_fps=True, sfx_volume=0, music_volume=0.55)
    save_preferences(prefs)
    assert load_preferences() == prefs
    assert json.loads(prefs_path.read_text(encoding="utf-8"))["music_volume"] == 0.55


def key(scene, code):
    scene.handle_event(pygame.event.Event(pygame.KEYDOWN, key=code))


@pytest.fixture
def settings():
    prefs = UserPreferences()
    sound = Mock()
    scene = SettingsScene(FontRegistry(), prefs, sound=sound)
    scene.draw(pygame.Surface((1280, 720)))
    return scene, prefs, sound


def test_keyboard_changes_each_volume_independently_and_applies_immediately(settings):
    scene, prefs, sound = settings
    key(scene, pygame.K_DOWN)
    key(scene, pygame.K_LEFT)
    assert prefs.sfx_volume == 0.6
    assert prefs.music_volume == 0.35
    sound.set_volumes.assert_called_with(0.6, 0.35)
    key(scene, pygame.K_DOWN)
    key(scene, pygame.K_RIGHT)
    assert prefs.sfx_volume == 0.6
    assert prefs.music_volume == 0.45
    sound.set_volumes.assert_called_with(0.6, 0.45)


def test_zero_mutes_and_volume_never_exceeds_bounds(settings):
    scene, prefs, sound = settings
    key(scene, pygame.K_DOWN)
    for _ in range(15):
        key(scene, pygame.K_LEFT)
    assert prefs.sfx_volume == 0
    sound.set_volumes.assert_called_with(0, 0.35)
    sound.reset_mock()
    key(scene, pygame.K_LEFT)
    sound.play_confirm.assert_not_called()
    sound.set_volumes.assert_not_called()
    for _ in range(15):
        key(scene, pygame.K_RIGHT)
    assert prefs.sfx_volume == 1


def test_volume_buttons_work_with_mouse(settings):
    scene, prefs, sound = settings
    minus, plus = scene._volume_buttons[2]
    scene.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=minus.center))
    assert prefs.music_volume == 0.25
    sound.set_volumes.assert_called_with(0.7, 0.25)
    scene.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=plus.center))
    assert prefs.music_volume == 0.35


def test_hover_only_sounds_when_the_selected_row_changes(settings):
    scene, _, sound = settings
    for _ in range(5):
        scene.handle_event(pygame.event.Event(pygame.MOUSEMOTION, pos=scene._item_rects[1].center))
    sound.play_nav.assert_called_once_with()


def test_fps_toggle_and_escape_still_work(settings):
    scene, prefs, sound = settings
    key(scene, pygame.K_RETURN)
    assert prefs.show_fps is True
    assert scene.cleared is False
    sound.play_confirm.assert_called_once_with()
    key(scene, pygame.K_ESCAPE)
    assert scene.cleared is True
    sound.play_cancel.assert_called_once_with()


def test_back_button_exits(settings):
    scene, _, sound = settings
    scene.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=scene._item_rects[3].center))
    assert scene.cleared is True
    sound.play_cancel.assert_called_once_with()
