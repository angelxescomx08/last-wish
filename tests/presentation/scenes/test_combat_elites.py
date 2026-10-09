"""Elites on screen: sheets, styles, the combat scene, the reward and the map.

Covers the loader (every elite sheet loads in the big slot with its strikes and move
clips), per-elite particle styles, the combat scene (big slot, ``is_elite``, opening
"¡Élite!" banner, move clip at end of turn, one hit number per blow, a 40-turn stress run
per elite), the tooltip ("ÉLITE" tag + identity), the reward screen with the relic panel
(draws with every relic, normal and golden, without spilling; hovering shows the relic),
the map's ÉLITE room, and the SceneManager flow (elite room → fight → reward with relic +
cards → the relic is obtained → back to the map).
"""
from dataclasses import replace
from unittest.mock import Mock

import pygame
import pytest

from src.application import elites as E
from src.application.combat_factory import create_combat_from_run
from src.application.run_manager import _all_relic_defs, create_run
from src.domain.character import ALL_CHARACTERS
from src.domain.chroma import Chroma
from src.domain.map_node import RoomType
from src.domain.tuning import TUNING
from src.infrastructure.enemy_sprites import ELITE_SHEET_IDS, ENEMY_SHEET_IDS, load_enemy_sheet
from src.infrastructure.fonts import FontRegistry
from src.presentation.fx.enemy_animator import STYLES
from src.presentation.scenes.combat_reward_scene import CombatRewardScene
from src.presentation.scenes.combat_scene import CombatScene

SHEET_OF = {ai: ENEMY_SHEET_IDS[d.name] for ai, d in E.ELITES.items()}


def _fonts():
    return FontRegistry()


def _run(obj, seconds, step=1 / 30):
    t = 0.0
    while t < seconds - 1e-9:
        obj.update(min(step, seconds - t))
        t += step


def _scene(ai, run=None):
    run = run or create_run(ALL_CHARACTERS[0], 3)
    return CombatScene(create_combat_from_run(run, [E.create_elite(ai, 1, "e")]), _fonts(),
                       sound=Mock())


class TestSheets:
    def test_registered(self):
        assert set(SHEET_OF.values()) == set(ELITE_SHEET_IDS)

    @pytest.mark.parametrize("sid", ELITE_SHEET_IDS)
    def test_loads_in_the_big_slot(self, sid):
        s = load_enemy_sheet(sid)
        assert s is not None and s.is_boss and 0 < s.top < s.anchor[1]
        assert s.strike_seconds("attack")

    @pytest.mark.parametrize("ai", E.ELITE_ORDER)
    def test_every_move_has_a_clip(self, ai):
        s = load_enemy_sheet(SHEET_OF[ai])
        e = E.create_elite(ai)
        ids = {e.intent.move_id} | {E.next_intent(e, None).move_id for _ in range(8)}
        assert all(s.animation_for_move(m, "") for m in ids)

    @pytest.mark.parametrize("sid", ELITE_SHEET_IDS)
    def test_style(self, sid):
        st = STYLES[sid]
        assert st.claw[0] < 0 and st.eyes[1] < 0 and not st.blades


class TestScene:
    @pytest.mark.parametrize("ai", E.ELITE_ORDER)
    def test_draws_in_the_big_slot(self, ai):
        scene = _scene(ai)
        scene.update(0.1)
        scene.draw(pygame.Surface((1280, 720)))
        assert scene.is_elite and not scene.is_boss
        assert scene.enemy_animators[0].sheet.is_boss and scene._enemy_rects[0].width == 230

    def test_regular_fight_is_not_elite(self):
        from src.application.enemy_roster import create_enemy
        run = create_run(ALL_CHARACTERS[0], 3)
        scene = CombatScene(create_combat_from_run(run, [create_enemy("golem")]), _fonts(), sound=Mock())
        assert not scene.is_elite

    def test_opening_banner(self):
        scene = _scene(E.MINOTAUR)
        titles = [b.title for b in scene._banners._items]
        assert any("¡Élite! Minotauro" in t for t in titles)

    @pytest.mark.parametrize("ai,clip", [(E.EXECUTIONER, "cast"), (E.HAG, "cast"),
                                         (E.GARGOYLE, "petrify"), (E.MINOTAUR, "paw"),
                                         (E.SCORPION, "sting")])
    def test_first_move_clip(self, ai, clip):
        scene = _scene(ai)
        scene.draw(pygame.Surface((1280, 720)))
        scene._do_end_turn()
        assert scene.enemy_animators[0].action == clip

    def test_dive_three_numbers(self):
        scene = _scene(E.GARGOYLE)
        scene.draw(pygame.Surface((1280, 720)))
        scene._do_end_turn()                           # Petrificar
        _run(scene, 3.0)
        scene.state.player.block = 0
        n = len(scene._fx._effects)
        scene._do_end_turn()                           # Picado ×3
        assert scene.enemy_animators[0].action == "dive"
        assert len(scene._fx._effects) - n >= 3

    @pytest.mark.parametrize("ai", E.ELITE_ORDER)
    def test_40_turn_stress(self, ai):
        TUNING.invincible = True
        scene = _scene(ai)
        surf = pygame.Surface((1280, 720))
        for _ in range(40):
            scene.draw(surf)
            scene._do_end_turn()
            _run(scene, 0.4, 1 / 20)
        scene.draw(surf)
        assert scene.state.enemies[0].is_alive and scene.state.player.is_alive

    def test_tooltip(self):
        from src.presentation.ui.tooltip import enemy_tooltip
        tip = enemy_tooltip(E.create_elite(E.SCORPION))
        assert tip.tag == "ÉLITE" and "reliquia" in tip.subtitle
        assert any(line.startswith("Veneno letal:") for line in tip.lines)


class TestReward:
    def _scene(self, relic):
        run = create_run(ALL_CHARACTERS[0], 3)
        from src.application.card_rewards import pick_reward_cards
        return CombatRewardScene(run, 12, pick_reward_cards(run, "x", luck_bonus=E.ELITE_CARD_LUCK),
                                 _fonts(), sound=Mock(), relic=relic)

    @pytest.mark.parametrize("golden", [False, True])
    def test_every_relic_fits(self, golden):
        surf = pygame.Surface((1280, 720))
        for relic in _all_relic_defs():
            relic = replace(relic, chroma=Chroma.GOLDEN) if golden else relic
            scene = self._scene(relic)
            scene.draw(surf)
            box = scene._relic_rect
            assert box.width == 600 and box.bottom < scene._card_rects[0].top

    def test_without_relic_unchanged_layout(self):
        scene = self._scene(None)
        scene.draw(pygame.Surface((1280, 720)))
        assert scene._relic_rect is None and scene._card_rects[0].top == 190

    def test_hover_shows_the_relic(self, monkeypatch):
        from src.presentation.scenes import combat_reward_scene as mod
        relic = _all_relic_defs()[0]
        scene = self._scene(relic)
        surf = pygame.Surface((1280, 720))
        scene.draw(surf)
        shown = []
        monkeypatch.setattr(mod, "draw_tooltip", lambda s, tip, *a, **k: shown.append(tip.title))
        scene.handle_event(pygame.event.Event(pygame.MOUSEMOTION, pos=scene._relic_rect.center))
        scene.draw(surf)
        assert shown and relic.name in shown[0]

    def test_skipping_cards_keeps_the_relic(self):
        relic = _all_relic_defs()[0]
        scene = self._scene(relic)
        scene.draw(pygame.Surface((1280, 720)))
        scene.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1,
                                              pos=scene._skip_rect.center))
        assert scene.cleared and scene.chosen_card is None and scene.relic is relic


class TestMap:
    def test_label_and_colour(self):
        from src.presentation.scenes import map_scene as ms
        assert ms._LABELS[RoomType.ELITE] == "ÉLITE" and RoomType.ELITE in ms._FILL_AVAIL

    def test_map_draws(self):
        from src.presentation.scenes.map_scene import MapScene
        MapScene(create_run(ALL_CHARACTERS[0], 3), _fonts(), sound=Mock()).draw(pygame.Surface((1280, 720)))


class TestManager:
    def test_elite_room_to_reward_to_map(self):
        import main
        from src.infrastructure.preferences import UserPreferences
        from src.presentation.scenes.map_scene import MapScene
        fonts = _fonts()
        m = main.SceneManager(main.MainMenuScene(fonts), fonts, UserPreferences())
        run = create_run(ALL_CHARACTERS[0], 3)
        m._run = run
        node = next(n for n in run.current_map.nodes.values() if n.room_type is RoomType.ELITE)
        mscene = MapScene(run, fonts)
        m.push(mscene)
        mscene.selected_node = node
        m._t_map(mscene)
        combat = m._stack[-1]
        assert isinstance(combat, CombatScene) and combat.is_elite
        for e in combat.state.enemies:
            e.current_hp = 0
        m._t_combat(combat)
        reward = m._stack[-1]
        assert isinstance(reward, CombatRewardScene) and reward.relic is not None
        relics_before, deck_before = len(run.relics), len(run.deck)
        reward.chosen_card, reward.cleared = reward._cards[0], True
        m._t_combat_reward(reward)
        assert len(run.relics) == relics_before + 1 and len(run.deck) == deck_before + 1
        assert isinstance(m._stack[-1], MapScene)
