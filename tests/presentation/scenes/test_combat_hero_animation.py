"""Combat hero clips: authored contact events, complete casts and held defeats.

Warrior, rogue and mage share playback; the mage adds timed arcane effects.
"""
import pygame
import pytest

from src.application.combat_factory import create_combat_from_run
from src.application.run_manager import create_run
from src.domain.card import Card, CardEffect, CardType
from src.domain.character import ALL_CHARACTERS
from src.domain.entities import Enemy, Intent, IntentType
from src.infrastructure.fonts import FontRegistry
from src.infrastructure.sprite_loader import hero_animation_seconds, hero_strike_seconds
from src.presentation.scenes.combat_scene import CombatScene


def _character(name):
    return next(c for c in ALL_CHARACTERS if c.name == name)


def _scene(hero="La Guerrera", *, enemy="Espectro", hp=40, intent=IntentType.ATTACK):
    run = create_run(_character(hero), 42)
    enemies = [Enemy(id="e0", name=enemy, max_hp=hp, current_hp=hp, intent=Intent(intent, 8))]
    scene = CombatScene(create_combat_from_run(run, enemies), FontRegistry())
    scene.draw(pygame.Surface((1280, 720)))
    return scene


def _steps(scene, seconds, dt=1 / 60):
    for _ in range(int(seconds / dt) + 1):
        scene.update(dt)


def _play_first(scene, card):
    scene.state.hand.cards.insert(0, card)
    scene.state.mana.current = max(scene.state.mana.current, card.cost)
    scene._do_play_card(0, 0)


def _strike_card():
    from src.domain.card_pool import starter_deck
    return next(c for c in starter_deck() if c.total_damage() > 0)


def _skill():
    return Card(id="test_skill", name="Concentración", card_type=CardType.SKILL, cost=0,
                base_effect=CardEffect(name="Concentración", draw=1))


class TestSetup:
    def test_warrior_has_strike_event(self):
        assert 0.15 < hero_strike_seconds("warrior") < 0.4

    def test_warrior_gets_warm_effects_at_its_metadata_origins(self):
        from src.infrastructure.sprite_loader import hero_strike_point, hero_cast_point, hero_cast_seconds
        from src.presentation.fx.hero_fx import WARM, GOLD
        effects = _scene()._hero_fx
        assert effects is not None
        assert effects.attack_palette == WARM and effects.cast_palette == GOLD
        assert effects.strike_point == hero_strike_point("warrior")
        assert effects.cast_point == hero_cast_point("warrior")
        assert effects.cast_seconds == pytest.approx(hero_cast_seconds("warrior"))
        assert effects._guard_time == pytest.approx(hero_animation_seconds("guard") * 0.4)
        assert effects._death_kneel == pytest.approx(hero_animation_seconds("death") * 0.6)

    def test_legacy_warrior_keeps_original_cue_timing(self, monkeypatch):
        from dataclasses import replace
        from src.infrastructure.sprite_loader import HEROES
        monkeypatch.setitem(HEROES, "warrior", replace(HEROES["warrior"], cast_frame=None, cast_point=None))
        effects = _scene()._hero_fx
        assert effects._guard_time == pytest.approx(0.06)
        assert effects._death_kneel == pytest.approx(0.18)

    def test_mage_gets_timed_arcane_effects(self):
        from src.presentation.fx.hero_fx import ARCANE
        effects = _scene("El Mago")._hero_fx
        assert effects is not None
        assert effects.attack_palette == ARCANE

    def test_mage_has_a_spell_contact_event(self):
        assert hero_strike_seconds("mage") == pytest.approx(0.345)


class TestCast:
    def test_skill_plays_cast(self):
        scene = _scene()
        _play_first(scene, _skill())
        assert scene.hero_action == "cast"

    def test_cast_returns_to_idle(self):
        scene = _scene()
        _play_first(scene, _skill())
        _steps(scene, hero_animation_seconds("cast") + 0.05)
        assert scene.hero_action is None


class TestBladeTiming:
    @pytest.mark.parametrize("hero", ["La Guerrera", "La Pícara", "El Mago"])
    def test_golden_cast_waits_for_blade_contact(self, hero):
        from src.domain.chroma import Chroma
        scene = _scene(hero, hp=100)
        card = _strike_card()
        card.chroma = Chroma.GOLDEN
        _play_first(scene, card)
        scene._advance_sequence(scene._cast_time(0))
        assert scene.hero_action == "attack"
        assert scene.enemy_animators[0].action is None
        _steps(scene, hero_strike_seconds(scene._hero_id) + 0.03)
        assert scene.enemy_animators[0].action == "hurt"

    def test_golden_cast_gap_allows_the_attack_to_finish(self, monkeypatch):
        from dataclasses import replace
        from src.domain.chroma import Chroma
        from src.infrastructure.sprite_loader import HEROES
        sheets = HEROES["rogue"]
        animations = dict(sheets.animations)
        animations["attack"] = replace(animations["attack"], durations=(0.72,))
        monkeypatch.setitem(HEROES, "rogue", replace(sheets, animations=animations))
        scene = _scene("La Pícara", hp=100)
        card = _strike_card()
        card.chroma = Chroma.GOLDEN
        _play_first(scene, card)
        assert scene._cast_time(1) - scene._cast_time(0) == pytest.approx(0.76)
        # Draw plans are built before the replay exists and must use the same gap.
        from types import SimpleNamespace
        scene._sequence = None
        scene._plan_draws(SimpleNamespace(cast_drawn=[1, 1], casts=2), action="attack")
        assert scene._deal_plan[1] - scene._deal_plan[0] == pytest.approx(0.76)
        assert scene._cast_time(1) - scene._cast_time(0) == pytest.approx(0.65)

    def test_enemy_waits_for_the_blade(self):
        scene = _scene()
        _play_first(scene, _strike_card())
        assert scene.enemy_animators[0].action is None

    def test_enemy_reacts_when_the_blade_connects(self):
        scene = _scene()
        _play_first(scene, _strike_card())
        _steps(scene, hero_strike_seconds() + 0.03)
        assert scene.enemy_animators[0].action == "hurt"

    def test_damage_is_applied_at_once(self):
        scene = _scene()
        _play_first(scene, _strike_card())
        assert scene.state.enemies[0].current_hp < 40


class TestDeath:
    def _dying(self):
        scene = _scene(enemy="Cultista")
        scene.state.player.current_hp = 1
        scene.state.player.block = 0
        scene.state.enemies[0].intent = Intent(IntentType.ATTACK, 50)
        scene._do_end_turn()
        return scene

    def test_lethal_hit_plays_death(self):
        assert self._dying().hero_action == "death"

    def test_defeat_waits_for_the_fall(self):
        scene = self._dying()
        _steps(scene, 0.5)
        assert scene.death_occurred is False

    def test_defeat_after_the_fall(self):
        scene = self._dying()
        _steps(scene, hero_animation_seconds("death") + 0.5)
        assert scene.death_occurred is True

    def test_death_is_held(self):
        scene = self._dying()
        _steps(scene, 5.0)
        assert scene.hero_action == "death"

    def test_nothing_interrupts_death(self):
        scene = self._dying()
        scene._play_hero_action("hurt")
        assert scene.hero_action == "death"

class TestRogueAnimationIntegration:
    def test_rogue_effects_use_the_metadata_strike_point(self, monkeypatch):
        from dataclasses import replace
        from src.infrastructure.sprite_loader import HEROES
        monkeypatch.setitem(HEROES, "rogue", replace(HEROES["rogue"], strike_point=(84, 34)))
        assert _scene("La Pícara")._hero_fx.strike_point == (72, -28)

    def test_skill_uses_cast_and_returns_to_idle(self):
        scene = _scene("La Pícara")
        _play_first(scene, _skill())
        assert scene.hero_action == "cast"
        _steps(scene, hero_animation_seconds("cast", "rogue") + 0.05)
        assert scene.hero_action is None

    def test_rogue_enemy_reacts_at_dagger_contact(self):
        scene = _scene("La Pícara")
        _play_first(scene, _strike_card())
        assert scene.enemy_animators[0].action is None
        _steps(scene, hero_strike_seconds("rogue") + 0.03)
        assert scene.enemy_animators[0].action == "hurt"

    def test_lethal_damage_waits_for_rogue_collapse(self):
        scene = _scene("La Pícara", enemy="Cultista")
        scene.state.player.current_hp = 1
        scene.state.player.block = 0
        scene.state.enemies[0].intent = Intent(IntentType.ATTACK, 50)
        scene._do_end_turn()
        assert scene.hero_action == "death"
        _steps(scene, 0.4)
        assert scene.death_occurred is False
        _steps(scene, hero_animation_seconds("death", "rogue") + 0.5)
        assert scene.death_occurred is True
        assert scene.hero_action == "death"


class TestMageAnimationIntegration:
    def test_damage_rules_resolve_at_once_but_enemy_waits_for_spell_contact(self):
        scene = _scene("El Mago")
        _play_first(scene, _strike_card())
        assert scene.state.enemies[0].current_hp < 40
        assert scene.enemy_animators[0].action is None
        _steps(scene, hero_strike_seconds("mage") - 0.05)
        assert scene.enemy_animators[0].action is None
        _steps(scene, 0.08)
        assert scene.enemy_animators[0].action == "hurt"

    def test_skill_uses_cast_and_recovers_to_idle(self):
        scene = _scene("El Mago")
        _play_first(scene, _skill())
        assert scene.hero_action == "cast"
        _steps(scene, hero_animation_seconds("cast", "mage") + 0.05)
        assert scene.hero_action is None

    def test_golden_skill_plays_cast(self):
        from src.domain.chroma import Chroma
        scene = _scene("El Mago")
        card = _skill()
        card.chroma = Chroma.GOLDEN
        _play_first(scene, card)
        scene._advance_sequence(scene._cast_time(0))
        assert scene.hero_action == "cast"
        assert scene._cast_time(1) - scene._cast_time(0) == pytest.approx(1.04)
        _steps(scene, 0.72)
        assert scene._sequence["fired"] == 1
        _steps(scene, 0.36)
        assert scene._sequence["fired"] == 2
        _steps(scene, 0.85)
        assert scene.presentation_busy
        _steps(scene, 0.3)
        assert not scene.presentation_busy

    def test_mage_effects_use_the_cast_metadata(self):
        from src.infrastructure.sprite_loader import hero_cast_point, hero_cast_seconds
        scene = _scene("El Mago")
        assert scene._hero_fx.cast_point == hero_cast_point("mage")
        assert scene._hero_fx.cast_seconds == pytest.approx(hero_cast_seconds("mage"))

    def test_block_plays_guard(self):
        from src.domain.numbers import BigValue
        scene = _scene("El Mago")
        card = Card(id="test_ward", name="Barrera", card_type=CardType.SKILL, cost=0,
                    base_effect=CardEffect(name="Barrera", block=BigValue(6)))
        _play_first(scene, card)
        assert scene.hero_action == "guard"

    def test_hurt_recovers_and_death_stays_down(self):
        scene = _scene("El Mago", enemy="Cultista")
        scene._play_hero_action("hurt")
        _steps(scene, hero_animation_seconds("hurt", "mage") + 0.05)
        assert scene.hero_action is None
        scene.state.player.current_hp = 1
        scene.state.player.block = 0
        scene.state.enemies[0].intent = Intent(IntentType.ATTACK, 50)
        scene._do_end_turn()
        assert scene.hero_action == "death"
        _steps(scene, 0.5)
        assert scene.death_occurred is False
        _steps(scene, hero_animation_seconds("death", "mage") + 0.5)
        assert scene.death_occurred is True
        assert scene.hero_action == "death"
