"""Tests for src/infrastructure/preferences.py.

Covers: default values, round-trip save/load, graceful handling of missing
or corrupted files, and unknown keys in the JSON being ignored safely.
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

import src.infrastructure.preferences as prefs_mod
from src.infrastructure.preferences import UserPreferences, load_preferences, save_preferences


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _with_prefs_file(tmp_path: Path):
    """Context manager: redirect _PREFS_FILE to a temp file, restore after."""
    import contextlib

    @contextlib.contextmanager
    def ctx(content: str | None = None):
        fake = tmp_path / "preferences.json"
        if content is not None:
            fake.write_text(content, encoding="utf-8")
        original = prefs_mod._PREFS_FILE
        prefs_mod._PREFS_FILE = fake
        try:
            yield fake
        finally:
            prefs_mod._PREFS_FILE = original

    return ctx


# ---------------------------------------------------------------------------
# UserPreferences defaults
# ---------------------------------------------------------------------------

class TestUserPreferencesDefaults:
    def test_show_fps_default_is_false(self):
        p = UserPreferences()
        assert p.show_fps is False

    def test_explicit_true(self):
        p = UserPreferences(show_fps=True)
        assert p.show_fps is True


# ---------------------------------------------------------------------------
# load_preferences
# ---------------------------------------------------------------------------

class TestLoadPreferences:
    def test_missing_file_returns_defaults(self, tmp_path):
        ctx = _with_prefs_file(tmp_path)
        with ctx():  # no file written
            result = load_preferences()
        assert result.show_fps is False

    def test_show_fps_true_loaded(self, tmp_path):
        ctx = _with_prefs_file(tmp_path)
        with ctx(json.dumps({"show_fps": True})):
            result = load_preferences()
        assert result.show_fps is True

    def test_show_fps_false_loaded(self, tmp_path):
        ctx = _with_prefs_file(tmp_path)
        with ctx(json.dumps({"show_fps": False})):
            result = load_preferences()
        assert result.show_fps is False

    def test_invalid_json_returns_defaults(self, tmp_path):
        ctx = _with_prefs_file(tmp_path)
        with ctx("not valid json {{{"):
            result = load_preferences()
        assert result.show_fps is False

    def test_empty_json_object_returns_defaults(self, tmp_path):
        ctx = _with_prefs_file(tmp_path)
        with ctx("{}"):
            result = load_preferences()
        assert result.show_fps is False

    def test_unknown_keys_are_ignored(self, tmp_path):
        ctx = _with_prefs_file(tmp_path)
        with ctx(json.dumps({"show_fps": True, "unknown_key": 42})):
            result = load_preferences()
        assert result.show_fps is True

    def test_integer_1_is_truthy(self, tmp_path):
        ctx = _with_prefs_file(tmp_path)
        with ctx(json.dumps({"show_fps": 1})):
            result = load_preferences()
        assert result.show_fps is True

    def test_integer_0_is_falsy(self, tmp_path):
        ctx = _with_prefs_file(tmp_path)
        with ctx(json.dumps({"show_fps": 0})):
            result = load_preferences()
        assert result.show_fps is False


# ---------------------------------------------------------------------------
# save_preferences
# ---------------------------------------------------------------------------

class TestSavePreferences:
    def test_save_creates_file(self, tmp_path):
        ctx = _with_prefs_file(tmp_path)
        fake_path = tmp_path / "preferences.json"
        with ctx():
            save_preferences(UserPreferences(show_fps=True))
        assert fake_path.exists()

    def test_save_show_fps_true(self, tmp_path):
        ctx = _with_prefs_file(tmp_path)
        fake_path = tmp_path / "preferences.json"
        with ctx():
            save_preferences(UserPreferences(show_fps=True))
        data = json.loads(fake_path.read_text(encoding="utf-8"))
        assert data["show_fps"] is True

    def test_save_show_fps_false(self, tmp_path):
        ctx = _with_prefs_file(tmp_path)
        fake_path = tmp_path / "preferences.json"
        with ctx():
            save_preferences(UserPreferences(show_fps=False))
        data = json.loads(fake_path.read_text(encoding="utf-8"))
        assert data["show_fps"] is False


# ---------------------------------------------------------------------------
# Round-trip
# ---------------------------------------------------------------------------

class TestRoundTrip:
    def test_save_then_load_true(self, tmp_path):
        ctx = _with_prefs_file(tmp_path)
        with ctx():
            save_preferences(UserPreferences(show_fps=True))
            result = load_preferences()
        assert result.show_fps is True

    def test_save_then_load_false(self, tmp_path):
        ctx = _with_prefs_file(tmp_path)
        with ctx():
            save_preferences(UserPreferences(show_fps=False))
            result = load_preferences()
        assert result.show_fps is False

    def test_overwrite_preserves_last_value(self, tmp_path):
        ctx = _with_prefs_file(tmp_path)
        with ctx():
            save_preferences(UserPreferences(show_fps=True))
            save_preferences(UserPreferences(show_fps=False))
            result = load_preferences()
        assert result.show_fps is False
