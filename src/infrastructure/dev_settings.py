"""Load/save the Pruebas (tuning) settings to ``dev_settings.json``.

Invalid or missing values fall back to the defaults, so a broken file never
stops the game.
"""
from __future__ import annotations

import json
import math
from dataclasses import asdict
from pathlib import Path

from src.domain.tuning import TUNING, Tuning

_FILE = Path("dev_settings.json")


def _num(value, default, lo, hi, *, integer: bool):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        return default
    value = max(lo, min(hi, value))
    return int(value) if integer else float(value)


def apply_dict(data: object, target: Tuning = TUNING) -> None:
    """Copy valid values from ``data`` into ``target`` (defaults for anything invalid)."""
    target.reset()
    if not isinstance(data, dict):
        return
    chances = data.get("chroma_chances", {})
    if isinstance(chances, dict):
        target.chroma_chances = {str(k): _num(v, 0.0, 0.0, 1.0, integer=False)
                                 for k, v in chances.items()
                                 if not isinstance(v, bool) and isinstance(v, (int, float))}
    target.all_class_cards = bool(data.get("all_class_cards", False))
    target.invincible = bool(data.get("invincible", False))
    target.starting_gold = _num(data.get("starting_gold"), target.starting_gold, 0, 1_000_000, integer=True)
    target.gold_multiplier = _num(data.get("gold_multiplier"), 1.0, 0.0, 100.0, integer=False)
    target.extra_mana = _num(data.get("extra_mana"), 0, 0, 20, integer=True)
    target.extra_draw = _num(data.get("extra_draw"), 0, 0, 20, integer=True)
    target.extra_max_hp = _num(data.get("extra_max_hp"), 0, 0, 10_000, integer=True)
    target.extra_luck = _num(data.get("extra_luck"), 0, 0, 1_000, integer=True)
    target.extra_damage = _num(data.get("extra_damage"), 0, 0, 10_000, integer=True)
    target.extra_dexterity = _num(data.get("extra_dexterity"), 0, 0, 10_000, integer=True)
    target.forced_boss = _num(data.get("forced_boss"), 0, 0, 3, integer=True)
    target.forced_encounter = _num(data.get("forced_encounter"), 0, 0, 99, integer=True)
    target.boss_rooms = bool(data.get("boss_rooms", False))
    target.gacha_rooms = bool(data.get("gacha_rooms", False))


def load_dev_settings(path: Path = _FILE) -> None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        TUNING.reset()
        return
    apply_dict(data)


def save_dev_settings(path: Path = _FILE) -> None:
    path.write_text(json.dumps(asdict(TUNING), indent=2), encoding="utf-8")
