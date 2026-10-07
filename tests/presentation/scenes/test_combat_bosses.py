"""Floor-1 bosses in the combat screen: sheets, animator styles, floating swords and the scene.

Covers the loader's boss data (strike events, move → animation, blade frames,
sprite top), per-enemy particle styles, the Caballero Hueco's swords (count
follows his Espadas, thrown one per hit and re-formed), the big boss slot, move
clips chosen at end of turn, one hit number per blow, and a 60-turn stress run.
"""
import pygame
import pytest

from src.application import enemy_ai
from src.application.combat_factory import create_combat_from_run
from src.application.run_manager import create_run
from src.domain.character import ALL_CHARACTERS
from src.domain.entities import BLADES, Intent, IntentType, status_stacks
from src.domain.tuning import TUNING
from src.infrastructure.enemy_sprites import (BOSS_SHEET_IDS, ENEMY_SHEET_IDS, load_enemy_sheet,
                                              sheet_for_enemy)
from src.infrastructure.fonts import FontRegistry
from src.presentation.fx.enemy_animator import (BLADE_FIRST, BLADE_FLIGHT, BLADE_GAP, EnemyAnimator,
                                                STYLES, style_for)
from src.presentation.scenes.combat_scene import CombatScene

ANCHOR = (900, 314)
AIS = {"mycelid": enemy_ai.MYCELID, "weaver": enemy_ai.WEAVER, "knight": enemy_ai.HOLLOW_KNIGHT}


def _run(obj, seconds, step=1 / 60):
    t = 0.0
    while t < seconds - 1e-9:
        dt = min(step, seconds - t)
        obj.update(dt)
        t += dt


def _anim(sheet_id):
    a = EnemyAnimator(load_enemy_sheet(sheet_id), seed=2)
    a.draw(pygame.Surface((1280, 720)), ANCHOR)
    return a


def _scene(ai):
    run = create_run(ALL_CHARACTERS[0], 3)
    return CombatScene(create_combat_from_run(run, [enemy_ai.create_boss(ai)]), FontRegistry())


class TestSheets:
    @pytest.mark.parametrize("sid", BOSS_SHEET_IDS)
    def test_loads_as_boss(self, sid):
        assert load_enemy_sheet(sid).is_boss

    def test_names_registered(self):
        assert {ENEMY_SHEET_IDS[enemy_ai.BOSSES[ai].name] for ai in AIS.values()} == set(BOSS_SHEET_IDS)

    def test_wraith_is_not_a_boss(self):
        assert not load_enemy_sheet("wraith").is_boss

    def test_wraith_strike_unchanged(self):
        s = load_enemy_sheet("wraith")
        assert s.strike_seconds("attack") == (sum(s.animations["attack"].durations[:3]),)

    def test_feast_three_strikes(self):
        assert len(load_enemy_sheet("weaver").strike_seconds("feast")) == 3

    def test_move_mapping(self):
        assert load_enemy_sheet("mycelid").animation_for_move("spores", "attack") == "spores"

    def test_unknown_move_falls_back(self):
        assert load_enemy_sheet("knight").animation_for_move("nope", "cast") == "cast"

    def test_knight_blades_loaded(self):
        assert len(load_enemy_sheet("knight").blade_frames) == 16

    def test_others_have_no_blades(self):
        assert load_enemy_sheet("weaver").blade_frames == ()

    def test_top_is_inside_cell(self):
        s = load_enemy_sheet("knight")
        assert 0 < s.top < s.anchor[1]

    def test_sheet_for_boss_name(self):
        assert sheet_for_enemy("Caballero Hueco").sheet_id == "knight"


class TestStyles:
    def test_each_boss_has_a_style(self):
        assert set(BOSS_SHEET_IDS) <= set(STYLES)

    def test_unknown_sheet_uses_wraith_style(self):
        assert style_for("nope") is STYLES["wraith"]

    def test_only_the_knight_has_blades(self):
        assert [k for k, v in STYLES.items() if v.blades] == ["knight"]


class TestStrikeTimes:
    def test_extra_hits_follow_the_last_strike(self):
        a = _anim("weaver")
        t = a.strike_times("feast", 5)
        assert len(t) == 5 and t[4] == pytest.approx(t[2] + 0.24)

    def test_no_strike_for_cast(self):
        assert _anim("mycelid").strike_times("cast") == ()

    def test_command_one_sword_per_hit(self):
        a = _anim("knight")
        assert a.strike_times("command", 3) == pytest.approx(
            tuple(BLADE_FIRST + k * BLADE_GAP + BLADE_FLIGHT for k in range(3)))

    def test_zero_hits_counts_as_one(self):
        assert len(_anim("knight").strike_times("command", 0)) == 1


class TestBlades:
    def test_count_follows_espadas(self):
        a = _anim("knight")
        a.blades = 4
        _run(a, 0.5)
        assert len(a._blade_state) == 4

    def test_losing_blades_trims(self):
        a = _anim("knight")
        a.blades = 5
        _run(a, 0.2)
        a.blades = 2
        _run(a, 0.1)
        assert len(a._blade_state) == 2

    def test_command_throws_them(self):
        a = _anim("knight")
        a.blades = 3
        _run(a, 0.5)
        a.play("command", hits=3)
        _run(a, BLADE_FIRST + 2 * BLADE_GAP + 0.05)
        assert sum(b[0] == "fly" for b in a._blade_state) >= 1

    def test_thrown_blades_reform(self):
        a = _anim("knight")
        a.blades = 2
        _run(a, 0.5)
        a.play("command", hits=2)
        _run(a, a.seconds("command") + 1.0)
        assert all(b[0] == "orbit" for b in a._blade_state)

    def test_death_drops_blades(self):
        a = _anim("knight")
        a.blades = 3
        _run(a, 0.5)
        a.play("death")
        _run(a, 0.1)
        assert a._blade_state == []

    def test_huge_count_stress(self):
        a = _anim("knight")
        a.blades = 40
        surf = pygame.Surface((1280, 720))
        for _ in range(300):
            a.update(1 / 30)
            a.draw(surf, ANCHOR)
        assert len(a._blade_state) == 40 and a.particles.count <= a.particles.capacity


class TestScene:
    @pytest.mark.parametrize("ai", list(AIS.values()))
    def test_boss_gets_an_animator(self, ai):
        assert _scene(ai).enemy_animators[0].sheet.is_boss

    @pytest.mark.parametrize("ai", list(AIS.values()))
    def test_draws(self, ai):
        scene = _scene(ai)
        scene.update(0.1)
        scene.draw(pygame.Surface((1280, 720)))
        assert scene._enemy_rects[0].width == 230

    def test_boss_rect_below_the_top_bar(self):
        scene = _scene(enemy_ai.HOLLOW_KNIGHT)
        scene.draw(pygame.Surface((1280, 720)))
        assert scene._enemy_rects[0].top >= 68 + 30

    def test_scene_sets_blade_count(self):
        scene = _scene(enemy_ai.HOLLOW_KNIGHT)
        scene.update(0.05)
        assert scene.enemy_animators[0].blades == status_stacks(scene.state.enemies[0].status_effects, BLADES)

    def test_move_clip_played(self):
        scene = _scene(enemy_ai.MYCELID)
        scene.draw(pygame.Surface((1280, 720)))
        scene._do_end_turn()                     # first move: Lluvia de Esporas
        assert scene.enemy_animators[0].action == "spores"

    def test_spores_reach_the_draw_pile(self):
        scene = _scene(enemy_ai.MYCELID)
        scene.draw(pygame.Surface((1280, 720)))
        before = scene.state.draw_pile.count + scene.state.hand.count + scene.state.discard_pile.count
        scene._do_end_turn()
        after = scene.state.draw_pile.count + scene.state.hand.count + scene.state.discard_pile.count
        assert after == before + 2

    def test_multi_hit_numbers(self):
        scene = _scene(enemy_ai.HOLLOW_KNIGHT)
        scene.draw(pygame.Surface((1280, 720)))
        scene.state.player.block = 0
        n = len(scene._fx._effects)
        scene._do_end_turn()                     # Danza de Espadas: 2 swords
        assert len(scene._fx._effects) - n >= 2

    def test_hero_waits_for_the_first_sword(self):
        scene = _scene(enemy_ai.HOLLOW_KNIGHT)
        scene.draw(pygame.Surface((1280, 720)))
        scene.state.player.block = 0
        scene._do_end_turn()
        assert scene.hero_action is None and scene._pending_hero_hurt == pytest.approx(
            BLADE_FIRST + BLADE_FLIGHT)

    def test_unplayable_card_rejected(self):
        from src.domain.status_cards import mold
        scene = _scene(enemy_ai.MYCELID)
        scene.state.hand.cards.insert(0, mold())
        scene._pick_card(0, (100, 600))
        assert scene.state.selected_card_index is None and scene._feedback_time > 0

    @pytest.mark.parametrize("ai", list(AIS.values()))
    def test_60_turn_stress(self, ai):
        TUNING.invincible = True
        scene = _scene(ai)
        surf = pygame.Surface((1280, 720))
        for _ in range(60):
            scene.draw(surf)
            scene._do_end_turn()
            _run(scene, 0.4, 1 / 20)
        scene.draw(surf)
        assert scene.state.enemies[0].is_alive and scene.state.player.is_alive
