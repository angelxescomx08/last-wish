"""infrastructure/enemy_sprites.py — animated enemy sheets ("Espectro").

Checks the name registry, slicing and ×2 scaling, timing (looping idle, held
death even after 10^9 s), caching and graceful failure for missing sheets.
"""
import pygame

from src.infrastructure.enemy_sprites import (
    ENEMY_ANIMATIONS, ENEMY_DIR, ENEMY_SHEET_IDS, enemy_sheet_id, load_enemy_sheet, sheet_for_enemy,
)


def _sheet():
    return load_enemy_sheet("wraith")


class TestRegistry:
    def test_espectro_uses_the_wraith_sheet(self):
        assert enemy_sheet_id("Espectro") == "wraith"

    def test_unknown_enemy_has_no_sheet(self):
        assert sheet_for_enemy("Cultista") is None

    def test_every_registered_sheet_exists_on_disk(self):
        assert all((ENEMY_DIR / f"{sid}_sheet.png").exists() and (ENEMY_DIR / f"{sid}_sheet.json").exists()
                   for sid in ENEMY_SHEET_IDS.values())

    def test_missing_sheet_is_none(self):
        assert load_enemy_sheet("no_such_enemy") is None


class TestSheet:
    def test_has_every_animation(self):
        assert set(_sheet().animations) == set(ENEMY_ANIMATIONS)

    def test_cells_are_scaled_by_two(self):
        assert _sheet().size == (256, 208)

    def test_anchor_is_scaled_by_two(self):
        assert _sheet().anchor == (160, 192)

    def test_frames_have_cell_size(self):
        sheet = _sheet()
        assert {f.get_size() for frames in sheet.frames.values() for f in frames} == {sheet.size}

    def test_frame_count_matches_durations(self):
        sheet = _sheet()
        assert all(len(sheet.frames[n]) == len(a.durations) for n, a in sheet.animations.items())

    def test_load_is_cached(self):
        assert load_enemy_sheet("wraith") is load_enemy_sheet("wraith")

    def test_idle_wraps(self):
        sheet = _sheet()
        period = sheet.seconds("idle")
        assert sheet.frame("idle", period + 0.001) is sheet.frame("idle", 0.001)

    def test_death_holds_last_frame_for_huge_time(self):
        sheet = _sheet()
        assert sheet.frame("death", 10 ** 9) is sheet.frames["death"][-1]

    def test_unknown_animation_falls_back_to_idle(self):
        sheet = _sheet()
        assert sheet.frame("dance", 0.0) is sheet.frames["idle"][0]

    def test_unknown_animation_lasts_zero(self):
        assert _sheet().seconds("dance") == 0.0

    def test_actions_end_on_idle_frame_zero(self):
        sheet = _sheet()
        idle0 = pygame.image.tobytes(sheet.frames["idle"][0], "RGBA")
        assert all(pygame.image.tobytes(sheet.frames[a][-1], "RGBA") == idle0
                   for a in ("attack", "hurt", "cast"))

    def test_death_ends_transparent(self):
        last = pygame.image.tobytes(_sheet().frames["death"][-1], "RGBA")
        assert max(last[3::4]) == 0
