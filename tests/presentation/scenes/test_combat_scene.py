"""Tests for presentation/scenes/combat_scene.py.

CombatScene renders the full battle screen. Tests here cover construction,
initial state, and event handling without visual assertions — all rendering
is smoke-tested (draw() must not raise). The session fixture in conftest.py
initialises pygame so Surface creation works.
"""
from __future__ import annotations

import pygame
import pytest

from src.application.combat_manager import create_sample_combat
from src.infrastructure.fonts import FontRegistry
from src.presentation.scenes.combat_scene import CombatScene


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _surface() -> pygame.Surface:
    return pygame.Surface((1280, 720))


def _fonts() -> FontRegistry:
    return FontRegistry()


def _scene() -> CombatScene:
    return CombatScene(create_sample_combat(), _fonts())


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------

class TestCombatSceneConstruction:
    def test_creates_without_error(self):
        assert _scene() is not None

    def test_no_overlay_initially(self):
        assert _scene()._overlay is None

    def test_no_hovered_card_initially(self):
        assert _scene()._hovered_card is None

    def test_no_hovered_enemy_initially(self):
        assert _scene()._hovered_enemy is None

    def test_in_targeting_mode_false_initially(self):
        assert not _scene()._in_targeting_mode


# ---------------------------------------------------------------------------
# draw() — smoke test (must not raise)
# ---------------------------------------------------------------------------

class TestCombatSceneDraw:
    def test_draw_initial_state(self):
        scene = _scene()
        scene.draw(_surface())

    def test_draw_multiple_times(self):
        scene = _scene()
        surf = _surface()
        for _ in range(3):
            scene.draw(surf)

    def test_draw_with_selected_card(self):
        scene = _scene()
        scene._state.selected_card_index = 0
        scene.draw(_surface())


# ---------------------------------------------------------------------------
# handle_event() — keyboard
# ---------------------------------------------------------------------------

class TestCombatSceneKeyboard:
    def test_escape_clears_selection(self):
        scene = _scene()
        scene._state.selected_card_index = 0
        escape = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE, mod=0, unicode="")
        scene.handle_event(escape)
        assert scene._state.selected_card_index is None

    def test_escape_with_no_selection_does_not_crash(self):
        scene = _scene()
        escape = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE, mod=0, unicode="")
        scene.handle_event(escape)

    def test_other_key_ignored(self):
        scene = _scene()
        scene._state.selected_card_index = 0
        space = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE, mod=0, unicode=" ")
        scene.handle_event(space)
        assert scene._state.selected_card_index == 0


# ---------------------------------------------------------------------------
# handle_event() — mouse motion
# ---------------------------------------------------------------------------

class TestCombatSceneMouseMotion:
    def test_mouse_motion_does_not_crash(self):
        scene = _scene()
        motion = pygame.event.Event(pygame.MOUSEMOTION, pos=(0, 0), rel=(0, 0), buttons=(0, 0, 0))
        scene.handle_event(motion)

    def test_mouse_over_empty_clears_hover(self):
        scene = _scene()
        motion = pygame.event.Event(pygame.MOUSEMOTION, pos=(640, 400), rel=(0, 0), buttons=(0, 0, 0))
        scene.handle_event(motion)
        assert scene._hovered_card is None


# ---------------------------------------------------------------------------
# update()
# ---------------------------------------------------------------------------

class TestCombatSceneUpdate:
    def test_update_without_overlay(self):
        scene = _scene()
        scene.update(1 / 60)

    def test_update_clears_dismissed_overlay(self):
        from src.presentation.ui.pile_viewer import PileViewer
        scene = _scene()
        scene._overlay = PileViewer("Test", [], _fonts())
        scene._overlay.dismissed = True
        scene.update(1 / 60)
        assert scene._overlay is None


def test_rejected_card_does_not_play_success_sound():
    from unittest.mock import Mock
    scene = _scene()
    scene._sound = Mock()
    scene._do_play_card(-1, None)
    scene._sound.play_card.assert_not_called()


# ---------------------------------------------------------------------------
# Card play — Slay the Spire style drag, aim and click
# ---------------------------------------------------------------------------

def _drawn():
    scene = _scene()
    scene._state.mana.current = 99
    scene.draw(_surface())
    return scene


def _drawn_with(kind):
    """A drawn scene whose first hand card is of the given target kind."""
    from src.application.play_card import target_kind
    from src.domain.card_pool import PackTheme, card_factories_for_theme, starter_deck
    pool = starter_deck() + [f() for t in PackTheme for f in card_factories_for_theme(t)]
    scene = _scene()
    scene._state.hand.cards.insert(0, next(c for c in pool if target_kind(c) is kind))
    scene._state.mana.current = 99
    scene.draw(_surface())
    return scene


def _index(scene, kind):
    from src.application.play_card import target_kind
    return next((i for i, c in enumerate(scene._state.hand.cards) if target_kind(c) is kind), None)


def _press(scene, pos, button=1):
    scene.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=button, pos=pos))


def _release(scene, pos, button=1):
    scene.handle_event(pygame.event.Event(pygame.MOUSEBUTTONUP, button=button, pos=pos))


def _move(scene, pos):
    scene.handle_event(pygame.event.Event(pygame.MOUSEMOTION, pos=pos, rel=(0, 0), buttons=(1, 0, 0)))


def _key(scene, key):
    scene.handle_event(pygame.event.Event(pygame.KEYDOWN, key=key, mod=0, unicode=""))


def _alive_enemy(scene):
    return next(i for i, e in enumerate(scene._state.enemies) if e.is_alive)


class TestHandLayout:
    def test_fan_is_symmetric(self):
        from src.presentation.scenes.combat_scene import _hand_layout
        poses = _hand_layout(5)
        assert poses[0].angle == -poses[4].angle and poses[2].angle == 0

    def test_single_card_is_straight(self):
        from src.presentation.scenes.combat_scene import _hand_layout
        assert _hand_layout(1)[0].angle == 0

    def test_empty_hand(self):
        from src.presentation.scenes.combat_scene import _hand_layout
        assert _hand_layout(0) == {}

    def test_tilt_is_capped_for_a_full_hand(self):
        from src.presentation.scenes.combat_scene import _MAX_TILT, _hand_layout
        assert max(abs(p.angle) for p in _hand_layout(10).values()) <= _MAX_TILT

    def test_hovered_card_grows_and_stays_on_screen(self):
        from src.presentation.scenes.combat_scene import _HOVER_SCALE, _hand_layout, _pose_rect
        pose = _hand_layout(5, hovered=2)[2]
        assert pose.scale == _HOVER_SCALE and pose.angle == 0 and _pose_rect(pose).bottom <= 720

    def test_neighbours_make_room(self):
        from src.presentation.scenes.combat_scene import _hand_layout
        rest, hover = _hand_layout(5), _hand_layout(5, hovered=2)
        assert hover[1].x < rest[1].x and hover[3].x > rest[3].x

    def test_held_card_leaves_the_fan(self):
        from src.presentation.scenes.combat_scene import _hand_layout
        assert 2 not in _hand_layout(5, held=2) and len(_hand_layout(5, held=2)) == 4


class TestCardPlay:
    def test_drag_attack_onto_enemy_plays_it(self):
        from src.application.play_card import TargetKind
        scene = _drawn()
        i, e = _index(scene, TargetKind.ENEMY), _alive_enemy(scene)
        hp, count = scene._state.enemies[e].current_hp, scene._state.hand.count
        target = scene._enemy_rects[e].center
        _press(scene, scene._card_rects[i].center)
        _move(scene, (640, 300))
        _move(scene, target)
        assert scene._in_targeting_mode and scene._play.target == e
        _release(scene, target)
        assert scene._state.hand.count == count - 1 and scene._state.enemies[e].current_hp < hp

    def test_drag_attack_released_on_nothing_returns(self):
        from src.application.play_card import TargetKind
        scene = _drawn()
        i, count = _index(scene, TargetKind.ENEMY), scene._state.hand.count
        _press(scene, scene._card_rects[i].center)
        _move(scene, (400, 300))
        _release(scene, (400, 300))
        assert scene._state.hand.count == count and scene._state.selected_card_index is None

    def test_self_card_plays_when_dropped_above_the_hand(self):
        from src.application.play_card import TargetKind
        scene = _drawn_with(TargetKind.SELF)
        i = _index(scene, TargetKind.SELF)
        count = scene._state.hand.count
        _press(scene, scene._card_rects[i].center)
        _move(scene, (640, 300))
        assert scene._play.armed
        _release(scene, (640, 300))
        assert scene._state.hand.count == count - 1

    def test_self_card_dropped_in_hand_is_not_played(self):
        from src.application.play_card import TargetKind
        scene = _drawn_with(TargetKind.SELF)
        i = _index(scene, TargetKind.SELF)
        count = scene._state.hand.count
        start = scene._card_rects[i].center
        _press(scene, start)
        _move(scene, (start[0] + 40, start[1] - 20))
        _release(scene, (start[0] + 40, start[1] - 20))
        assert scene._state.hand.count == count

    def test_click_attack_then_click_enemy(self):
        from src.application.play_card import TargetKind
        scene = _drawn()
        i, e = _index(scene, TargetKind.ENEMY), _alive_enemy(scene)
        count = scene._state.hand.count
        pos = scene._card_rects[i].center
        _press(scene, pos)
        _release(scene, pos)
        assert scene._in_targeting_mode
        _move(scene, scene._enemy_rects[e].center)
        _press(scene, scene._enemy_rects[e].center)
        assert scene._state.hand.count == count - 1

    def test_right_click_cancels_aim(self):
        from src.application.play_card import TargetKind
        scene = _drawn()
        pos = scene._card_rects[_index(scene, TargetKind.ENEMY)].center
        _press(scene, pos)
        _release(scene, pos)
        _press(scene, (640, 300), button=3)
        assert not scene._play.active and scene._state.selected_card_index is None

    def test_number_key_and_enter_play_on_first_enemy(self):
        from src.application.play_card import TargetKind
        scene = _drawn()
        i, e = _index(scene, TargetKind.ENEMY), _alive_enemy(scene)
        hp = scene._state.enemies[e].current_hp
        _key(scene, pygame.K_1 + i)
        assert scene._play.target == e
        _key(scene, pygame.K_RETURN)
        assert scene._state.enemies[e].current_hp < hp

    def test_number_key_beyond_hand_is_ignored(self):
        scene = _drawn()
        scene._state.hand.cards = scene._state.hand.cards[:2]
        _key(scene, pygame.K_9)
        assert not scene._play.active

    def test_aiming_draws_arrow_and_reticle(self):
        from src.application.play_card import TargetKind
        scene = _drawn()
        i, e = _index(scene, TargetKind.ENEMY), _alive_enemy(scene)
        _press(scene, scene._card_rects[i].center)
        _move(scene, (640, 300))
        _move(scene, scene._enemy_rects[e].center)
        surface = _surface()
        scene.update(1 / 60)
        scene.draw(surface)
        rect = scene._enemy_rects[e]
        corner = {tuple(surface.get_at((x, y)))[:3] for x in range(rect.x - 12, rect.x + 6)
                  for y in range(rect.y - 12, rect.y + 6)}
        from src.presentation.ui.targeting import RETICLE_ENEMY
        assert RETICLE_ENEMY in corner

    def test_played_card_flies_away_then_vanishes(self):
        from src.application.play_card import TargetKind
        scene = _drawn()
        scene.update(1 / 60)
        _key(scene, pygame.K_1 + _index(scene, TargetKind.ENEMY))
        _key(scene, pygame.K_RETURN)
        assert len(scene._leaving) == 1
        for _ in range(30):
            scene.update(1 / 60)
        assert scene._leaving == []

    def test_cards_tween_to_their_slots(self):
        scene = _drawn()
        for _ in range(120):
            scene.update(1 / 60)
        key = scene._card_keys()[0]
        pose, goal = scene._motion[key], scene._target_poses()[0]
        assert abs(pose.x - goal.x) < 0.5 and abs(pose.y - goal.y) < 0.5

    def test_huge_frame_time_does_not_overshoot(self):
        scene = _drawn()
        scene.update(10 ** 9)
        key = scene._card_keys()[0]
        assert abs(scene._motion[key].x - scene._target_poses()[0].x) < 1e-6

    def test_end_turn_drops_the_held_card(self):
        from src.application.play_card import TargetKind
        scene = _drawn()
        _key(scene, pygame.K_1 + _index(scene, TargetKind.ENEMY))
        scene._do_end_turn()
        assert not scene._play.active

    def test_area_card_marks_every_enemy(self):
        from src.application.play_card import TargetKind
        from src.presentation.ui.targeting import RETICLE_ENEMY
        scene = _drawn_with(TargetKind.ALL_ENEMIES)
        _press(scene, scene._card_rects[0].center)
        _move(scene, (640, 300))
        surface = _surface()
        scene.draw(surface)
        for rect in scene._enemy_rects:
            corner = {tuple(surface.get_at((x, y)))[:3] for x in range(rect.x - 12, rect.x + 6)
                      for y in range(rect.y - 12, rect.y + 6)}
            assert RETICLE_ENEMY in corner

    def test_self_card_marks_the_hero(self):
        from src.application.play_card import TargetKind
        from src.presentation.ui.targeting import RETICLE_SELF
        scene = _drawn_with(TargetKind.SELF)
        _press(scene, scene._card_rects[0].center)
        _move(scene, (640, 300))
        surface = _surface()
        scene.draw(surface)
        rect = scene._player_rect
        corner = {tuple(surface.get_at((x, y)))[:3] for x in range(rect.x - 12, rect.x + 6)
                  for y in range(rect.y - 12, rect.y + 6)}
        assert RETICLE_SELF in corner
