"""Rogue hero sheets ("La Pícara"): same contract as the other heroes.

The rogue art (assets/characters/rogue_base.png) is animated by
scripts/generate_rogue_sprites.py; runtime never resamples it.
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

    def test_rogue_has_the_four_animations(self):
        assert set(HEROES["rogue"].animations) == {"idle", "attack", "guard", "hurt"}

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
