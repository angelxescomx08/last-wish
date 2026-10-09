"""Rogue hero sheets ("La Pícara"): same contract as the other heroes.

The rogue pose atlas (assets/characters/rogue-source-v2.png) is baked by
scripts/generate_rogue_v2_sprites.py; runtime uses cached frames.
"""
import pygame

from src.infrastructure.sprite_loader import (
    HEROES, SpriteLoader, has_hero_sprites, hero_animation_seconds, hero_id_for,
)


def _bytes(surface):
    return pygame.image.tobytes(surface, "RGBA")


class TestRegistry:
    def test_rogue_names_map_to_rogue_sheets(self):
        assert (hero_id_for("La Pícara"), hero_id_for("El Pícaro")) == ("rogue", "rogue")

    def test_unknown_name_has_no_hero_sheets(self):
        assert has_hero_sprites("Nadie") is False

    def test_rogue_has_complete_combat_animations(self):
        assert set(HEROES["rogue"].animations) == {"idle", "attack", "guard", "hurt", "cast", "death"}

    def test_daggers_connect_during_attack(self):
        from src.infrastructure.sprite_loader import hero_strike_seconds
        assert 0.1 < hero_strike_seconds("rogue") < hero_animation_seconds("attack", "rogue")

    def test_rogue_has_combat_and_selection_sheets(self):
        assert set(HEROES["rogue"].sheets) == {96, 192}

    def test_unknown_hero_animation_is_zero(self):
        assert hero_animation_seconds("idle", "nobody") == 0.0


class TestFrames:
    def test_combat_sprite_comes_from_the_rogue_sheet(self):
        assert SpriteLoader().get_player_sprite("La Pícara", 192).get_size() == (192, 192)

    def test_selection_sprite_is_96(self):
        assert SpriteLoader().get_player_sprite("La Pícara", 96).get_size() == (96, 96)

    def test_rogue_and_warrior_differ(self):
        loader = SpriteLoader()
        assert _bytes(loader.get_player_sprite("La Pícara", 192)) != _bytes(loader.get_player_sprite("La Guerrera", 192))

    def test_idle_has_motion(self):
        frames = SpriteLoader().get_player_idle_frames(192, "rogue")
        assert len({_bytes(f) for f in frames}) >= len(frames) // 2

    def test_idle_boots_stay_planted(self):
        frames = SpriteLoader().get_player_idle_frames(192, "rogue")
        assert len({_bytes(f.subsurface((50, 176, 90, 15))) for f in frames}) == 1

    def test_actions_end_on_idle_frame_zero(self):
        loader = SpriteLoader()
        idle0 = _bytes(loader.get_player_idle_frames(192, "rogue")[0])
        assert all(_bytes(loader.get_player_animation_frames(a, 192, "rogue")[-1]) == idle0
                   for a in ("attack", "guard", "hurt"))

    def test_actions_are_short(self):
        assert all(0.3 <= hero_animation_seconds(a, "rogue") <= 0.8 for a in ("attack", "guard", "hurt"))

    def test_death_holds_collapsed_pose(self):
        loader = SpriteLoader()
        frames = loader.get_player_animation_frames("death", 192, "rogue")
        assert frames
        assert _bytes(frames[-1]) != _bytes(loader.get_player_idle_frames(192, "rogue")[0])
        assert _bytes(loader.get_player_sprite("La Pícara", 192, elapsed=100, animation="death")) == _bytes(frames[-1])

    def test_idle_cycle_matches_the_shared_scene_clock(self):
        from src.infrastructure.sprite_loader import IDLE_CYCLE_SECONDS
        assert hero_animation_seconds("idle", "rogue") == IDLE_CYCLE_SECONDS


class TestCombat:
    def test_rogue_combat_plays_attack_on_attack_card(self):
        from src.application.run_manager import create_run, generate_boss
        from src.application.combat_factory import create_combat_from_run
        from src.domain.card_pool import starter_deck
        from src.domain.character import ALL_CHARACTERS, CharacterId
        from src.infrastructure.fonts import FontRegistry
        from src.presentation.scenes.combat_scene import CombatScene
        rogue = next(c for c in ALL_CHARACTERS if c.id is CharacterId.ROGUE)
        run = create_run(rogue, 42)
        scene = CombatScene(create_combat_from_run(run, generate_boss(run)), FontRegistry())
        attack = next(c for c in starter_deck() if c.total_damage() > 0)
        scene.state.hand.cards.insert(0, attack)
        scene.state.mana.current = max(scene.state.mana.current, attack.cost)
        scene._do_play_card(0, 0)
        assert (scene._hero_id, scene.hero_action) == ("rogue", "attack")



class TestRogueBackup:
    def test_legacy_metadata_still_resolves_original_sheets(self):
        import json
        from pathlib import Path
        assets = Path(__file__).resolve().parents[1] / "assets" / "characters"
        meta = json.loads((assets / "rogue_legacy" / "rogue_sheet.json").read_text())
        assert set(meta["animations"]) == {"idle", "attack", "guard", "hurt"}
        for filename in meta["sheets"].values():
            assert (assets / filename).read_bytes() == (assets / "rogue_legacy" / filename).read_bytes()

class TestRoguePixelIntegrity:
    def test_all_frames_keep_transparent_safe_margins(self):
        loader = SpriteLoader()
        for name in HEROES["rogue"].animations:
            for frame in loader.get_player_animation_frames(name, 96, "rogue"):
                bounds = frame.get_bounding_rect()
                assert bounds.left >= 2 and bounds.right <= 94
                assert bounds.top >= 2 and bounds.bottom <= 94

    def test_combat_art_is_exact_double_native_pixels(self):
        loader = SpriteLoader()
        for name in HEROES["rogue"].animations:
            native = loader.get_player_animation_frames(name, 96, "rogue")
            combat = loader.get_player_animation_frames(name, 192, "rogue")
            assert all(_bytes(pygame.transform.scale(a, (192, 192))) == _bytes(b)
                       for a, b in zip(native, combat, strict=True))
