"""Active warrior v3 sheets: crisp pixels, timing, complete poses and combat.

The articulated pixel rig bakes 96/192 px sheets. These tests protect the active
metadata contract while older generator tests continue checking archived art.
"""
import pygame
import pytest

from src.infrastructure.sprite_loader import (
    HERO_ANIMATIONS, IDLE_CYCLE_SECONDS, SpriteLoader, hero_animation_seconds,
)


def _bytes(surface):
    return pygame.image.tobytes(surface, "RGBA")


def _combat_scene():
    from src.application.run_manager import create_run, generate_boss
    from src.application.combat_factory import create_combat_from_run
    from src.domain.character import ALL_CHARACTERS
    from src.infrastructure.fonts import FontRegistry
    from src.presentation.scenes.combat_scene import CombatScene
    run = create_run(ALL_CHARACTERS[0], 42)
    return CombatScene(create_combat_from_run(run, generate_boss(run)), FontRegistry())


class TestSheet:
    def test_sheet_has_the_six_hero_animations(self):
        assert set(HERO_ANIMATIONS) == {"idle", "attack", "guard", "hurt", "cast", "death"}

    def test_only_idle_loops(self):
        assert [n for n, a in HERO_ANIMATIONS.items() if a.loop] == ["idle"]

    @pytest.mark.parametrize("name, count, seconds", [
        ("idle", 48, 1.6), ("attack", 48, 0.8), ("guard", 40, 0.72),
        ("hurt", 36, 0.6), ("cast", 56, 1.0), ("death", 72, 1.4),
    ])
    def test_every_animation_has_its_complete_motion_at_both_sizes(self, name, count, seconds):
        loader = SpriteLoader()
        assert hero_animation_seconds(name) == pytest.approx(seconds)
        for size in (96, 192):
            assert len(loader.get_player_animation_frames(name, size)) == count

    def test_runtime_uses_the_versioned_warrior_files(self):
        from src.infrastructure.sprite_loader import HERO_SHEETS
        assert HERO_SHEETS == {96: "warrior_v3_sheet_96.png", 192: "warrior_v3_sheet.png"}

    @pytest.mark.parametrize("size", [96, 192])
    def test_frames_are_scaled_by_whole_numbers(self, size):
        frames = SpriteLoader().get_player_animation_frames("idle", size)
        assert {f.get_size() for f in frames} == {(size, size)}

    def test_unknown_animation_gives_no_frames(self):
        assert SpriteLoader().get_player_animation_frames("dance", 96) == ()

    def test_frames_are_cached_per_animation_and_size(self):
        loader = SpriteLoader()
        assert loader.get_player_animation_frames("attack", 192) is loader.get_player_animation_frames("attack", 192)


class TestIdle:
    def test_idle_frames_are_transparent_and_tall(self):
        for frame in SpriteLoader().get_player_idle_frames(192):
            bounds = frame.get_bounding_rect(min_alpha=32)
            assert frame.get_at((0, 0)).a == 0 and bounds.height > 140 and 0 < bounds.left < bounds.right < 192

    def test_idle_soles_share_one_baseline(self):
        bottoms = {f.get_bounding_rect(min_alpha=32).bottom for f in SpriteLoader().get_player_idle_frames(192)}
        assert len(bottoms) == 1
        assert 160 <= next(iter(bottoms)) <= 188

    def test_selection_size_uses_its_own_sheet(self):
        from src.infrastructure.sprite_loader import HERO_SHEETS
        assert set(HERO_SHEETS) == {96, 192}

    @pytest.mark.parametrize("size", [96, 192])
    def test_idle_soles_are_identical_throughout_cycle(self, size):
        # The v3 cape and shins move above the planted soles.
        frames = SpriteLoader().get_player_idle_frames(size)
        bottom = frames[0].get_bounding_rect(min_alpha=32).bottom
        sole_height = 4 * (size // 96)
        soles = (f.subsurface((0, bottom - sole_height, size, sole_height)) for f in frames)
        assert len({_bytes(sole) for sole in soles}) == 1

    def test_idle_has_motion(self):
        frames = SpriteLoader().get_player_idle_frames(96)
        assert len({_bytes(f) for f in frames}) >= len(frames) // 2

    @pytest.mark.parametrize("size", [96, 192])
    def test_idle_has_no_long_frozen_segment(self, size):
        # Native pixel quantization can hold a pose across the loop seam.
        # Check elapsed time (including that seam), rather than three frames.
        pixels = [_bytes(f) for f in SpriteLoader().get_player_idle_frames(size)]
        durations = HERO_ANIMATIONS["idle"].durations
        for start in range(len(pixels)):
            held = 0.0
            for step in range(len(pixels)):
                index = (start + step) % len(pixels)
                if pixels[index] != pixels[start]:
                    break
                held += durations[index]
            assert held <= 0.2, (size, start, held)

    def test_idle_cycle_is_a_calm_breath(self):
        assert 1.0 <= IDLE_CYCLE_SECONDS <= 2.0


class TestActions:
    @pytest.mark.parametrize("name", ["attack", "guard", "hurt", "cast"])
    @pytest.mark.parametrize("size", [96, 192])
    def test_action_starts_and_ends_exactly_on_idle_frame_zero(self, name, size):
        loader = SpriteLoader()
        frames = loader.get_player_animation_frames(name, size)
        rest = _bytes(loader.get_player_idle_frames(size)[0])
        assert _bytes(frames[0]) == rest
        assert _bytes(frames[-1]) == rest

    @pytest.mark.parametrize("name", ["attack", "guard", "hurt"])
    def test_action_is_short(self, name):
        assert 0.3 <= hero_animation_seconds(name) <= 0.8 + 1e-9

    def test_attack_reaches_beyond_the_idle_silhouette(self):
        loader = SpriteLoader()
        idle_right = loader.get_player_idle_frames(96)[0].get_bounding_rect(min_alpha=32).right
        attack_right = max(f.get_bounding_rect(min_alpha=32).right for f in loader.get_player_animation_frames("attack", 96))
        assert attack_right >= idle_right + 8

    def test_unknown_animation_length_is_zero(self):
        assert hero_animation_seconds("dance") == 0.0


class TestTiming:
    def test_each_idle_frame_is_selected_inside_its_slot(self):
        loader = SpriteLoader()
        frames = loader.get_player_idle_frames(192)
        start = 0.0
        for index, duration in enumerate(HERO_ANIMATIONS["idle"].durations):
            assert loader.get_player_sprite("La Guerrera", 192, elapsed=start + duration / 2) is frames[index]
            start += duration

    def test_idle_wraps_after_a_full_cycle(self):
        loader = SpriteLoader()
        assert loader.get_player_sprite("La Guerrera", 192, elapsed=0) is \
            loader.get_player_sprite("La Guerrera", 192, elapsed=IDLE_CYCLE_SECONDS)

    def test_idle_wraps_after_huge_elapsed_time(self):
        anim = HERO_ANIMATIONS["idle"]
        assert anim.frame_at(anim.total * 10**9 + anim.durations[0] / 2) == 0

    def test_negative_elapsed_is_frame_zero(self):
        assert HERO_ANIMATIONS["attack"].frame_at(-5.0) == 0

    def test_action_holds_its_last_frame(self):
        anim = HERO_ANIMATIONS["attack"]
        assert anim.frame_at(anim.total + 100.0) == len(anim.durations) - 1

    def test_action_first_frame_boundary(self):
        anim = HERO_ANIMATIONS["attack"]
        assert (anim.frame_at(anim.durations[0] - 0.001), anim.frame_at(anim.durations[0] + 0.001)) == (0, 1)

    def test_missing_sheet_uses_existing_character_fallback(self, monkeypatch):
        import src.infrastructure.sprite_loader as module
        from dataclasses import replace
        monkeypatch.setitem(module.HEROES, "warrior",
                            replace(module.HEROES["warrior"], sheets={192: "missing-sheet.png"}))
        loader = SpriteLoader()
        monkeypatch.setattr(loader, "_load", lambda path, size: "fallback")
        assert loader.get_player_sprite("La Guerrera") == "fallback"


class TestScenes:
    def test_idle_clock_depends_on_elapsed_time_not_frame_rate(self):
        scenes = []
        for fps in (30, 144):
            scene = _combat_scene()
            for _ in range(fps):
                scene.update(1 / fps)
            scenes.append(scene)
        assert scenes[0]._idle_time == pytest.approx(scenes[1]._idle_time)

    @pytest.mark.parametrize("screen_name", ["combat", "selection"])
    def test_scene_renders_a_different_idle_pose_after_time_passes(self, screen_name):
        from src.infrastructure.fonts import FontRegistry
        from src.presentation.scenes.character_select_scene import CharacterSelectScene
        if screen_name == "combat":
            scene = _combat_scene()
            area = pygame.Rect(195, 90, 155, 195)
        else:
            scene = CharacterSelectScene(FontRegistry())
            area = pygame.Rect(290, 185, 96, 110)
        surface = pygame.Surface((1280, 720))
        scene.draw(surface)
        before = _bytes(surface.subsurface(area))
        scene.update(IDLE_CYCLE_SECONDS / 2)
        scene.draw(surface)
        assert _bytes(surface.subsurface(area)) != before

    def test_playing_an_attack_card_starts_the_attack_animation(self):
        scene = _combat_scene()
        from src.domain.card_pool import starter_deck
        attack = next(c for c in starter_deck() if c.total_damage() > 0)
        scene.state.hand.cards.insert(0, attack)
        scene.state.mana.current = max(scene.state.mana.current, attack.cost)
        scene._do_play_card(0, 0)
        assert scene.hero_action == "attack"

    def test_hero_returns_to_idle_after_the_action(self):
        scene = _combat_scene()
        scene._play_hero_action("guard")
        scene.update(hero_animation_seconds("guard") + 0.01)
        assert (scene.hero_action, scene._idle_time) == (None, 0.0)

    def test_taking_damage_plays_hurt(self):
        scene = _combat_scene()
        scene.state.player.block = 0
        for enemy in scene.state.enemies:
            from src.domain.entities import Intent, IntentType
            enemy.intent = Intent(IntentType.ATTACK, 5)
        scene._do_end_turn()
        seen = scene.hero_action == "hurt"
        for _ in range(40):                 # animated bosses: she flinches when the blow lands
            if seen:
                break
            scene.update(0.05)
            seen = scene.hero_action == "hurt"
        assert seen

    def test_unknown_action_is_ignored(self):
        scene = _combat_scene()
        scene._play_hero_action("dance")
        assert scene.hero_action is None


class TestWarriorPixelIntegrity:
    @pytest.mark.parametrize("size", [96, 192])
    def test_all_frames_have_crisp_pixels_and_safe_margins(self, size):
        loader = SpriteLoader()
        margin = size // 48
        for name in HERO_ANIMATIONS:
            for index, frame in enumerate(loader.get_player_animation_frames(name, size)):
                bounds = frame.get_bounding_rect()
                assert bounds.left >= margin and bounds.right <= size - margin, (name, index, bounds)
                assert bounds.top >= margin and bounds.bottom <= size - margin, (name, index, bounds)
                assert set(memoryview(_bytes(frame))[3::4]) <= {0, 255}, (name, index)

    def test_contact_event_has_a_point_and_matches_the_selected_attack_frame(self):
        from src.infrastructure.sprite_loader import HEROES, hero_strike_point, hero_strike_seconds
        assert HEROES["warrior"].strike_frame == 20
        assert hero_strike_seconds("warrior") == pytest.approx(0.333)
        assert hero_strike_point("warrior") is not None
        assert HERO_ANIMATIONS["attack"].frame_at(hero_strike_seconds("warrior")) == 20

    @pytest.mark.parametrize("action, frame, point_name", [
        ("attack", 20, "strike_point"), ("cast", 28, "cast_point"),
    ])
    def test_effect_origin_stays_on_the_sword_at_the_authored_event(self, monkeypatch, action, frame, point_name):
        from pathlib import Path
        from src.infrastructure.sprite_loader import HEROES
        monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "scripts"))
        from warrior_pixel_rig import pose_at, weapon_tip
        phase = frame / (len(HERO_ANIMATIONS[action].durations) - 1)
        assert getattr(HEROES["warrior"], point_name) == pytest.approx(
            weapon_tip(pose_at(action, phase)), abs=0.001)

    def test_death_keeps_the_collapsed_endpoint(self):
        loader = SpriteLoader()
        frames = loader.get_player_animation_frames("death", 192)
        assert _bytes(frames[-1]) != _bytes(loader.get_player_idle_frames(192)[0])
        assert loader.get_player_sprite("La Guerrera", 192, animation="death", elapsed=100) is frames[-1]


class TestWarriorBackup:
    def test_previous_warrior_is_preserved_with_its_original_metadata(self):
        import json
        from pathlib import Path
        assets = Path(__file__).resolve().parents[1] / "assets" / "characters"
        backup = assets / "warrior_before_v3"
        meta = json.loads((backup / "warrior_sheet.json").read_text(encoding="utf-8"))
        assert meta["animations"]["idle"]["frames"] == 16
        assert meta["events"]["attack"]["strike_frame"] == 3
        for filename in meta["sheets"].values():
            assert (backup / filename).read_bytes() == (assets / filename).read_bytes()
