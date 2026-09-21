import pygame
import pytest
from src.infrastructure.sprite_loader import SpriteLoader


def test_idle_frames_are_transparent_and_feet_stay_aligned():
    frames = SpriteLoader().get_player_idle_frames(192)
    assert len(frames) == 8
    assert len({pygame.image.tobytes(frame, 'RGBA') for frame in frames}) > 1
    bottoms = []
    for frame in frames:
        assert frame.get_size() == (192, 192)
        assert frame.get_at((0, 0)).a == 0
        bounds = frame.get_bounding_rect(min_alpha=32)
        assert bounds.height > 140
        assert 0 < bounds.left < bounds.right < 192
        bottoms.append(bounds.bottom)
    assert max(bottoms) - min(bottoms) <= 2


def test_idle_timing_is_a_gentle_seamless_ping_pong():
    from src.infrastructure.sprite_loader import IDLE_FRAME_SECONDS, IDLE_SEQUENCE, IDLE_CYCLE_SECONDS
    loader = SpriteLoader()
    frames = loader.get_player_idle_frames(192)
    assert 2.3 <= IDLE_CYCLE_SECONDS <= 3.0
    for i, frame_index in enumerate(IDLE_SEQUENCE):
        assert loader.get_player_sprite('La Guerrera', 192, elapsed=(i + 0.5) * IDLE_FRAME_SECONDS) is frames[frame_index]
    assert loader.get_player_sprite('La Guerrera', 192, elapsed=0) is loader.get_player_sprite('La Guerrera', 192, elapsed=IDLE_CYCLE_SECONDS)


def test_missing_idle_asset_uses_existing_character_fallback(monkeypatch):
    import src.infrastructure.sprite_loader as module
    monkeypatch.setattr(module, '_HERO_IDLE_PATH', module._ASSETS / 'missing-idle.png')
    loader = SpriteLoader()
    monkeypatch.setattr(loader, '_load', lambda path, size: 'fallback')
    assert loader.get_player_sprite('La Guerrera') == 'fallback'


def test_idle_clock_depends_on_elapsed_time_not_frame_rate():
    from src.application.run_manager import create_run, generate_boss
    from src.application.combat_factory import create_combat_from_run
    from src.domain.character import ALL_CHARACTERS
    from src.infrastructure.fonts import FontRegistry
    from src.presentation.scenes.combat_scene import CombatScene
    scenes = []
    for fps in (30, 144):
        run = create_run(ALL_CHARACTERS[0], 42)
        scene = CombatScene(create_combat_from_run(run, generate_boss(run)), FontRegistry())
        for _ in range(fps):
            scene.update(1 / fps)
        scenes.append(scene)
    assert scenes[0]._idle_time == pytest.approx(scenes[1]._idle_time)

@pytest.mark.parametrize('screen_name', ['combat', 'selection'])
def test_scene_renders_a_different_idle_pose_after_time_passes(screen_name):
    from src.application.run_manager import create_run, generate_boss
    from src.application.combat_factory import create_combat_from_run
    from src.domain.character import ALL_CHARACTERS
    from src.infrastructure.fonts import FontRegistry
    from src.presentation.scenes.combat_scene import CombatScene
    from src.presentation.scenes.character_select_scene import CharacterSelectScene
    if screen_name == 'combat':
        run = create_run(ALL_CHARACTERS[0], 42)
        scene = CombatScene(create_combat_from_run(run, generate_boss(run)), FontRegistry())
        area = pygame.Rect(195, 90, 155, 195)
    else:
        scene = CharacterSelectScene(FontRegistry())
        area = pygame.Rect(290, 195, 96, 100)
    surface = pygame.Surface((1280, 720))
    scene.draw(surface)
    before = pygame.image.tobytes(surface.subsurface(area), 'RGBA')
    scene.update(1.26)
    scene.draw(surface)
    assert pygame.image.tobytes(surface.subsurface(area), 'RGBA') != before
