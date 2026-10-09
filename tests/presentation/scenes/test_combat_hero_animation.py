"""CombatScene + the code-drawn warrior: cast for skills, enemies react when the
blade connects, she falls before the defeat screen, particles only for her.
"""
import pygame

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

    def test_warrior_gets_hero_fx(self):
        assert _scene()._hero_fx is not None

    def test_other_heroes_have_no_hero_fx(self):
        assert _scene("El Mago")._hero_fx is None

    def test_other_heroes_strike_is_zero(self):
        assert hero_strike_seconds("mage") == 0.0


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
