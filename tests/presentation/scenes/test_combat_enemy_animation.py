"""CombatScene + animated enemies (the code-drawn "Espectro").

The scene owns one EnemyAnimator per enemy with a sheet. These tests pin the
hand-off: hits play ``hurt``, a kill plays ``death`` (and victory waits for
it), ending the turn plays ``attack`` for attack intents and ``cast`` for the
rest, and the hero flinches when the claws land, not before.
"""
import pygame

from src.application.combat_factory import create_combat_from_run
from src.application.run_manager import create_run
from src.domain.card_pool import starter_deck
from src.domain.character import ALL_CHARACTERS
from src.domain.entities import Enemy, Intent, IntentType
from src.infrastructure.fonts import FontRegistry
from src.presentation.scenes.combat_scene import CombatScene


def _scene(*intents, hp=40):
    run = create_run(ALL_CHARACTERS[0], 42)
    enemies = [Enemy(id=f"e{i}", name="Espectro", max_hp=hp, current_hp=hp, intent=Intent(t, 6))
               for i, t in enumerate(intents or (IntentType.ATTACK,))]
    return CombatScene(create_combat_from_run(run, enemies), FontRegistry())


def _steps(scene, seconds, dt=1 / 60):
    for _ in range(int(seconds / dt) + 1):
        scene.update(dt)


def _attack_first(scene):
    card = next(c for c in starter_deck() if c.total_damage() > 0)
    scene.state.hand.cards.insert(0, card)
    scene.state.mana.current = max(scene.state.mana.current, card.cost)
    return card


def _drawn(scene):
    surface = pygame.Surface((1280, 720))
    scene.draw(surface)
    return surface


class TestSetup:
    def test_espectro_gets_an_animator(self):
        assert set(_scene().enemy_animators) == {0}

    def test_static_enemies_get_none(self):
        run = create_run(ALL_CHARACTERS[0], 42)
        state = create_combat_from_run(run, [Enemy(id="c", name="Cultista", max_hp=30, current_hp=30)])
        assert CombatScene(state, FontRegistry()).enemy_animators == {}

    def test_three_espectros_three_animators(self):
        scene = _scene(IntentType.ATTACK, IntentType.BLOCK, IntentType.BUFF)
        assert len(scene.enemy_animators) == 3

    def test_draws_without_error(self):
        scene = _scene()
        _drawn(scene)
        _steps(scene, 0.5)
        assert _drawn(scene).get_size() == (1280, 720)


class TestHits:
    def test_damage_plays_hurt(self):
        scene = _scene()
        _drawn(scene)
        _attack_first(scene)
        scene._do_play_card(0, 0)
        assert scene.enemy_animators[0].action == "hurt"

    def test_kill_plays_death(self):
        scene = _scene(hp=1)
        _drawn(scene)
        _attack_first(scene)
        scene._do_play_card(0, 0)
        assert scene.enemy_animators[0].dead is True

    def test_victory_waits_for_the_death_animation(self):
        scene = _scene(hp=1)
        _drawn(scene)
        _attack_first(scene)
        scene._do_play_card(0, 0)
        _steps(scene, 0.8)
        assert scene.combat_won is False

    def test_victory_after_the_death_animation(self):
        scene = _scene(hp=1)
        _drawn(scene)
        _attack_first(scene)
        scene._do_play_card(0, 0)
        _steps(scene, scene.enemy_animators[0].seconds("death") + 0.2)
        assert scene.combat_won is True

    def test_dead_espectro_still_draws(self):
        scene = _scene(hp=1)
        _drawn(scene)
        _attack_first(scene)
        scene._do_play_card(0, 0)
        for _ in range(30):
            scene.update(1 / 30)
            _drawn(scene)
        assert scene.enemy_animators[0].dead is True


class TestEnemyTurn:
    def test_attack_intent_plays_attack(self):
        scene = _scene(IntentType.ATTACK)
        _drawn(scene)
        scene._do_end_turn()
        assert scene.enemy_animators[0].action == "attack"

    def test_block_intent_plays_cast(self):
        scene = _scene(IntentType.BLOCK)
        _drawn(scene)
        scene._do_end_turn()
        assert scene.enemy_animators[0].action == "cast"

    def test_second_enemy_is_staggered(self):
        scene = _scene(IntentType.ATTACK, IntentType.ATTACK)
        _drawn(scene)
        scene._do_end_turn()
        assert (scene.enemy_animators[0].action, scene.enemy_animators[1].action) == ("attack", None)

    def test_hero_waits_for_the_claws(self):
        scene = _scene(IntentType.ATTACK)
        scene.state.player.block = 0
        _drawn(scene)
        scene._do_end_turn()
        assert scene.hero_action is None

    def test_hero_flinches_when_the_claws_land(self):
        scene = _scene(IntentType.ATTACK)
        scene.state.player.block = 0
        _drawn(scene)
        scene._do_end_turn()
        _steps(scene, scene.enemy_animators[0].strike_time() + 0.05)
        assert scene.hero_action == "hurt"

    def test_stress_many_turns(self):
        scene = _scene(IntentType.ATTACK, IntentType.BLOCK, IntentType.BUFF, hp=10 ** 6)
        scene.state.player.current_hp = scene.state.player.max_hp = 10 ** 9
        for _ in range(100):
            scene._do_end_turn()
            _steps(scene, 0.2, dt=0.05)
            _drawn(scene)
        assert all(a.particles.count <= a.particles.capacity for a in scene.enemy_animators.values())
