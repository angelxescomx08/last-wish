"""The ten new animated enemies and pairs on the combat screen.

Covers the sheet registry and particle styles of every regular enemy, the Seta's
terminal ``explode`` clip (latches like death), the CombatScene with pairs (opening
banner, each enemy keeps its slot when its partner leaves, an exploding/dying enemy
keeps drawing until its clip ends, "¡VENGANZA!" once, heal numbers), tooltips and
intent extras (identity, pair, lifesteal, ally block/buffs, prayer, explosion, Mecha
icon), action banners, the Pruebas encounter row, and a 60-turn stress per encounter.
"""
from __future__ import annotations

import pygame
import pytest

from src.application import enemy_roster as R
from src.application.combat_factory import create_combat_from_run
from src.application.run_manager import create_run
from src.domain.card import Card, CardEffect, CardType
from src.domain.character import ALL_CHARACTERS
from src.domain.combat import EnemyAction
from src.domain.entities import FUSE, Intent, IntentType
from src.domain.numbers import BigValue
from src.domain.tuning import TUNING
from src.infrastructure.enemy_sprites import (ENEMY_SHEET_IDS, REGULAR_SHEET_IDS, load_enemy_sheet,
                                              sheet_for_enemy)
from src.infrastructure.fonts import FontRegistry
from src.infrastructure.ui_icons import has_ui_icon
from src.presentation.fx.enemy_animator import STYLES, EnemyAnimator
from src.presentation.scenes.combat_scene import CombatScene
from src.presentation.ui import glossary
from src.presentation.ui.action_banner import describe_action
from src.presentation.ui.entity_widget import intent_extras
from src.presentation.ui.tooltip import enemy_tooltip

FONTS = FontRegistry()


def _scene(enemies, hero=0) -> CombatScene:
    run = create_run(ALL_CHARACTERS[hero], 3)
    return CombatScene(create_combat_from_run(run, enemies), FONTS)


def _steps(scene, seconds, dt=1 / 60):
    for _ in range(int(seconds / dt) + 1):
        scene.update(dt)


def _draw(scene):
    surface = pygame.Surface((1280, 720))
    scene.draw(surface)
    return surface


def _killer(dmg=999) -> Card:
    return Card(id="k", name="Matar", card_type=CardType.ATTACK, cost=0,
                base_effect=CardEffect(name="Matar", damage=BigValue(dmg)))


class TestSheets:
    @pytest.mark.parametrize("sheet_id", REGULAR_SHEET_IDS)
    def test_loads_with_style(self, sheet_id):
        assert load_enemy_sheet(sheet_id) is not None and sheet_id in STYLES

    def test_every_enemy_mapped(self):
        assert all(ENEMY_SHEET_IDS.get(d.name) in REGULAR_SHEET_IDS for d in R.ENEMIES.values())

    def test_bomb_terminal_explode(self):
        assert load_enemy_sheet("bomb").terminal == ("explode",)
        assert load_enemy_sheet("slime").terminal == ()

    def test_explode_latches(self):
        anim = EnemyAnimator(load_enemy_sheet("bomb"))
        anim.play("explode")
        assert anim.dead and not anim.death_done
        anim.update(0.1)
        anim.play("hurt")                         # nothing interrupts it
        assert anim.action == "explode"
        for _ in range(200):
            anim.update(0.05)
        assert anim.death_done

    def test_explode_draws_particles(self):
        anim = EnemyAnimator(load_enemy_sheet("bomb"))
        surface = pygame.Surface((1280, 720))
        anim.draw(surface, (900, 300))
        anim.play("explode")
        for _ in range(40):
            anim.update(1 / 30)
            anim.draw(surface, (900, 300))
        assert anim.particles.count > 0


class TestScenePairs:
    def test_animators_for_both(self):
        scene = _scene(R.create_pair("culto", 1, "r"))
        assert len(scene.enemy_animators) == 2

    def test_pair_banner(self):
        scene = _scene(R.create_pair("muro", 1, "r"))
        assert any("Muro Corrosivo" in b.title for b in scene._banners.active)

    def test_no_banner_solo(self):
        scene = _scene([R.create_enemy(R.IMP)])
        assert not any("Pareja" in b.title for b in scene._banners.active)

    def test_survivor_keeps_its_slot(self):
        scene = _scene(R.create_pair("caceria", 1, "r"))
        _draw(scene)
        x_before = scene._enemy_rects[1].centerx
        scene.state.hand.cards.insert(0, _killer())
        scene.state.mana.current = 3
        scene._do_play_card(0, 0)
        _steps(scene, 1.0)
        scene._do_end_turn()
        _steps(scene, 3.0)
        _draw(scene)
        assert len(scene.state.enemies) == 1 and scene._enemy_rects[0].centerx == x_before

    def test_survivor_animator_follows_it(self):
        eye, bat = R.create_pair("caceria", 1, "r")
        scene = _scene([eye, bat])
        bat_anim = scene.enemy_animators[1]
        eye.current_hp = 0
        scene._do_end_turn()
        assert scene.enemy_animators == {0: bat_anim}

    def test_vengeance_text_once(self):
        scene = _scene(R.create_pair("culto", 1, "r"))
        _draw(scene)
        scene.state.hand.cards.insert(0, _killer())
        scene._do_play_card(0, 0)
        _steps(scene, 0.2)
        _steps(scene, 0.2)
        assert scene._avenging == {scene.state.enemies[1].id}

    def test_explosion_keeps_drawing(self):
        TUNING.invincible = True
        worm, bomb = R.create_pair("cementerio", 1, "r")
        scene = _scene([worm, bomb])
        _draw(scene)
        for _ in range(2):
            scene._do_end_turn()
            _steps(scene, 3.0)
        scene._do_end_turn()
        assert [e.name for e in scene.state.enemies] == ["Gusano de Tumba"]
        assert len(scene._gone) == 1
        _steps(scene, 0.6)
        _draw(scene)
        assert scene._gone[0][0].action == "explode"
        _steps(scene, 4.0)
        assert scene._gone == []

    def test_solo_bomb_victory_waits_for_blast(self):
        TUNING.invincible = True
        scene = _scene([R.create_enemy(R.BOMB, 1, "b")])
        _draw(scene)
        for _ in range(3):
            scene._do_end_turn()
            if scene.state.enemies:
                _steps(scene, 3.0)
        assert scene.enemies_dying
        _steps(scene, 4.0)
        assert not scene.enemies_dying

    def test_heal_number(self):
        bat = R.create_enemy(R.BAT, 1, "b")
        bat.current_hp = 5
        scene = _scene([bat])
        _draw(scene)
        scene._do_end_turn()
        assert bat.current_hp > 5

    def test_trio_draws(self):
        enemies = R.create_pair("culto", 3, "r") + [R.create_enemy(R.GOLEM, 3, "g")]
        scene = _scene(enemies, hero=1)
        _steps(scene, 0.3)
        _draw(scene)
        assert len(scene._enemy_rects) == 3

    @pytest.mark.parametrize("idx", range(1, len(R.ENCOUNTERS) + 1))
    def test_60_turns(self, idx):
        TUNING.invincible = True
        scene = _scene(R.create_encounter(idx, 1, "s"))
        for _ in range(60):
            if not scene.state.enemies:
                break
            _draw(scene)
            scene._do_end_turn()
            _steps(scene, 0.5, dt=0.1)
        _draw(scene)


class TestTexts:
    def test_tooltip_identity_and_pair(self):
        skull = R.create_pair("culto")[1]
        text = " ".join(enemy_tooltip(skull).lines)
        assert "Agresivo" in text and "El Culto del Fuego" in text and "Venganza" in text

    def test_tooltip_lifesteal(self):
        bat = R.create_enemy(R.BAT)
        assert any("Se curará" in line for p in enemy_tooltip(bat).panels for line in p.lines)

    def test_tooltip_explosion(self):
        bomb = R.create_enemy(R.BOMB)
        bomb.intent = Intent(IntentType.ATTACK, 24, move="¡Explosión!", self_destruct=True)
        lines = [line for p in enemy_tooltip(bomb).panels for line in p.lines]
        assert any("explota y muere" in line for line in lines)

    def test_extras(self):
        assert intent_extras(Intent(IntentType.ATTACK, 5, lifesteal=True)) == ["heal"]
        assert intent_extras(Intent(IntentType.BLOCK, 5, ally_block=3)) == ["block"]
        assert intent_extras(Intent(IntentType.ATTACK, 5, self_destruct=True)) == ["fuse"]
        assert intent_extras(Intent(IntentType.BUFF, heal_allies=8)) == ["heal"]

    def test_fuse_icon(self):
        assert glossary.status_icon(FUSE) == "fuse" and has_ui_icon("fuse")

    def test_banner_texts(self):
        intent = Intent(IntentType.BLOCK, 10, move="Muralla", ally_block=8)
        _, title, detail = describe_action("Gólem de Musgo", intent, EnemyAction(0, move="Muralla"))
        assert title == "Gólem de Musgo usa Muralla" and "da 8 de escudo a su compañero" in detail
        _, _, detail = describe_action("Seta", Intent(IntentType.ATTACK, 24),
                                       EnemyAction(0, hits=[24], exploded=True))
        assert "¡explota y muere!" in detail
        _, _, detail = describe_action("Murciélago", Intent(IntentType.ATTACK, 7, lifesteal=True),
                                       EnemyAction(0, hits=[7], healed=7))
        assert "recupera 7 de vida" in detail

    def test_pruebas_row(self):
        from src.presentation.scenes.dev_settings_scene import _ENCOUNTER_LABELS
        assert _ENCOUNTER_LABELS[0] == "Al azar" and len(_ENCOUNTER_LABELS) == len(R.ENCOUNTERS) + 1

    def test_sprite_lookup_by_name(self):
        assert sheet_for_enemy("Mímico") is not None and sheet_for_enemy("Cultista") is None
