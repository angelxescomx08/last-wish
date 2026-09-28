"""Combat backdrop: draws the pre-lit room, animates torches and particles, stays cheap."""
import time

import pygame

from src.infrastructure.dungeon_assets import load_dungeon_assets
from src.presentation.ui.dungeon_backdrop import DungeonBackdrop, FALLBACK_COLOR


def _bytes(surface, rect):
    return pygame.image.tobytes(surface.subsurface(rect), "RGBA")


def _torch_rect():
    x, y = load_dungeon_assets().meta["room"]["torches"][0]
    return pygame.Rect(x * 2 - 40, y * 2 - 60, 80, 80)


class TestDrawing:
    def test_draws_the_room_not_a_flat_colour(self):
        surface = pygame.Surface((1280, 720))
        DungeonBackdrop().draw(surface)
        assert len({surface.get_at((x, 200))[:3] for x in range(0, 1280, 40)}) > 3

    def test_particles_are_alive_from_the_first_frame(self):
        assert DungeonBackdrop().particle_count > 20

    def test_torch_changes_over_time(self):
        backdrop, surface = DungeonBackdrop(), pygame.Surface((1280, 720))
        backdrop.draw(surface)
        before = _bytes(surface, _torch_rect())
        backdrop.update(0.25)
        backdrop.draw(surface)
        assert _bytes(surface, _torch_rect()) != before

    def test_budget_zero_has_no_particles(self):
        assert DungeonBackdrop(budget=0.0).particle_count == 0

    def test_missing_pack_falls_back_to_flat_colour(self, monkeypatch):
        import src.presentation.ui.dungeon_backdrop as module
        monkeypatch.setattr(module, "load_dungeon_assets", lambda: None)
        surface = pygame.Surface((64, 64))
        module.DungeonBackdrop().draw(surface)
        assert surface.get_at((5, 5))[:3] == FALLBACK_COLOR


class TestCost:
    def test_update_stays_cheap_over_many_frames(self):
        backdrop = DungeonBackdrop()
        start = time.perf_counter()
        for _ in range(600):
            backdrop.update(1 / 60)
        assert time.perf_counter() - start < 1.0       # ~0.1 ms per frame expected

    def test_particle_count_stays_bounded(self):
        backdrop = DungeonBackdrop()
        for _ in range(3000):
            backdrop.update(1 / 60)
        assert backdrop.particle_count < 400


class TestCombatScene:
    def test_combat_scene_draws_the_backdrop(self):
        from src.application.run_manager import create_run, generate_boss
        from src.application.combat_factory import create_combat_from_run
        from src.domain.character import ALL_CHARACTERS
        from src.infrastructure.fonts import FontRegistry
        from src.presentation.scenes.combat_scene import CombatScene
        run = create_run(ALL_CHARACTERS[0], 42)
        scene = CombatScene(create_combat_from_run(run, generate_boss(run)), FontRegistry())
        surface = pygame.Surface((1280, 720))
        scene.draw(surface)
        wx0, wy0, _, _ = load_dungeon_assets().meta["room"]["window_interior"]
        assert surface.get_at((wx0 * 2 + 30, wy0 * 2 + 30))[:3] != (12, 12, 20)
