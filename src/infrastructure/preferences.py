from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path

_PREFS_FILE = Path("preferences.json")
_DEFAULT_SFX_VOLUME = 0.7
_DEFAULT_MUSIC_VOLUME = 0.35


def _valid_volume(value: object, default: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return default
    if isinstance(value, float) and not math.isfinite(value):
        return default
    return float(max(0.0, min(1.0, value)))


@dataclass
class UserPreferences:
    show_fps: bool = False
    sfx_volume: float = _DEFAULT_SFX_VOLUME
    music_volume: float = _DEFAULT_MUSIC_VOLUME

    def __post_init__(self) -> None:
        self.sfx_volume = _valid_volume(self.sfx_volume, _DEFAULT_SFX_VOLUME)
        self.music_volume = _valid_volume(self.music_volume, _DEFAULT_MUSIC_VOLUME)


def load_preferences() -> UserPreferences:
    try:
        data = json.loads(_PREFS_FILE.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return UserPreferences()
    if not isinstance(data, dict):
        return UserPreferences()
    return UserPreferences(
        show_fps=bool(data.get("show_fps", False)),
        sfx_volume=data.get("sfx_volume", _DEFAULT_SFX_VOLUME),
        music_volume=data.get("music_volume", _DEFAULT_MUSIC_VOLUME),
    )


def save_preferences(prefs: UserPreferences) -> None:
    _PREFS_FILE.write_text(json.dumps(asdict(prefs), indent=2), encoding="utf-8")
