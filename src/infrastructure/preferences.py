from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

_PREFS_FILE = Path("preferences.json")


@dataclass
class UserPreferences:
    show_fps: bool = False


def load_preferences() -> UserPreferences:
    try:
        data = json.loads(_PREFS_FILE.read_text(encoding="utf-8"))
        return UserPreferences(show_fps=bool(data.get("show_fps", False)))
    except (FileNotFoundError, json.JSONDecodeError):
        return UserPreferences()


def save_preferences(prefs: UserPreferences) -> None:
    _PREFS_FILE.write_text(json.dumps(asdict(prefs), indent=2), encoding="utf-8")
