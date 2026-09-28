"""Tests for presentation/ui/card_play.py — the Slay the Spire style input state machine.

Pure logic (no pygame): pick, drag, aim, release, sticky click, keyboard, cancel.
Stress: thousands of pointer moves and target cycles keep the machine consistent.
"""
from __future__ import annotations

from src.application.play_card import TargetKind
from src.presentation.ui.card_play import DRAG_THRESHOLD, CardPlayInput, Mode, PlayRequest

LINE = 465
HAND = (640, 600)      # a point inside the hand area
ABOVE = (640, 300)     # a point above the play line


def _picked(kind: TargetKind, index: int = 2) -> CardPlayInput:
    play = CardPlayInput(LINE)
    play.pick(index, kind, HAND)
    return play


class TestPick:
    def test_idle_initially(self):
        assert CardPlayInput(LINE).mode is Mode.IDLE

    def test_pick_holds_the_card(self):
        play = _picked(TargetKind.ENEMY)
        assert (play.mode, play.card, play.active) == (Mode.HOLDING, 2, True)

    def test_pick_card_zero(self):
        assert _picked(TargetKind.SELF, 0).card == 0

    def test_pick_does_not_aim_before_dragging(self):
        assert not _picked(TargetKind.ENEMY).aiming


class TestDragEnemyCard:
    def test_small_motion_is_not_a_drag(self):
        play = _picked(TargetKind.ENEMY)
        play.move((HAND[0] + int(DRAG_THRESHOLD), HAND[1]), None)
        assert play.mode is Mode.HOLDING

    def test_dragging_above_the_line_aims(self):
        play = _picked(TargetKind.ENEMY)
        play.move(ABOVE, None)
        assert play.aiming

    def test_exactly_on_the_line_is_still_the_hand(self):
        play = _picked(TargetKind.ENEMY)
        play.move((640, LINE), None)
        assert not play.aiming

    def test_one_pixel_above_the_line_aims(self):
        play = _picked(TargetKind.ENEMY)
        play.move((640, LINE - 1), None)
        assert play.aiming

    def test_enemy_under_pointer_becomes_target(self):
        play = _picked(TargetKind.ENEMY)
        play.move(ABOVE, 1)
        assert play.target == 1

    def test_dragging_back_to_hand_drops_aim(self):
        play = _picked(TargetKind.ENEMY)
        play.move(ABOVE, 1)
        play.move(HAND, None)
        assert (play.mode, play.target) == (Mode.HOLDING, None)

    def test_release_over_enemy_plays(self):
        play = _picked(TargetKind.ENEMY)
        play.move(ABOVE, 0)
        assert play.release(ABOVE, 0) == PlayRequest(2, 0)

    def test_release_resets_to_idle(self):
        play = _picked(TargetKind.ENEMY)
        play.move(ABOVE, 0)
        play.release(ABOVE, 0)
        assert play.mode is Mode.IDLE

    def test_release_on_nothing_puts_card_back(self):
        play = _picked(TargetKind.ENEMY)
        play.move(ABOVE, None)
        assert play.release(ABOVE, None) is None and not play.active

    def test_release_in_hand_puts_card_back(self):
        play = _picked(TargetKind.ENEMY)
        play.move(ABOVE, 0)
        assert play.release(HAND, None) is None and not play.active


class TestDragSelfCard:
    def test_not_armed_inside_hand(self):
        play = _picked(TargetKind.SELF)
        play.move((HAND[0], HAND[1] - 20), None)
        assert not play.armed

    def test_armed_above_line(self):
        play = _picked(TargetKind.SELF)
        play.move(ABOVE, None)
        assert play.armed

    def test_never_aims(self):
        play = _picked(TargetKind.ALL_ENEMIES)
        play.move(ABOVE, 1)
        assert not play.aiming and play.target is None

    def test_release_above_plays_without_target(self):
        play = _picked(TargetKind.SELF)
        play.move(ABOVE, None)
        assert play.release(ABOVE, None) == PlayRequest(2, None)

    def test_release_over_enemy_still_has_no_target(self):
        play = _picked(TargetKind.ALL_ENEMIES)
        play.move(ABOVE, 0)
        assert play.release(ABOVE, 0) == PlayRequest(2, None)

    def test_release_in_hand_cancels(self):
        play = _picked(TargetKind.SELF)
        play.move(ABOVE, None)
        assert play.release(HAND, None) is None and not play.active


class TestClickToHold:
    def test_quick_click_keeps_holding(self):
        play = _picked(TargetKind.SELF)
        assert play.release(HAND, None) is None and play.sticky and play.active

    def test_quick_click_on_attack_aims_immediately(self):
        play = _picked(TargetKind.ENEMY)
        play.release(HAND, None)
        assert play.aiming

    def test_sticky_release_is_ignored(self):
        play = _picked(TargetKind.ENEMY)
        play.release(HAND, None)
        assert play.release(ABOVE, 0) is None and play.active

    def test_second_click_on_enemy_plays(self):
        play = _picked(TargetKind.ENEMY)
        play.release(HAND, None)
        assert play.click(ABOVE, 1) == PlayRequest(2, 1)

    def test_second_click_on_nothing_cancels(self):
        play = _picked(TargetKind.ENEMY)
        play.release(HAND, None)
        assert play.click(ABOVE, None) is None and not play.active

    def test_sticky_self_card_click_above_plays(self):
        play = _picked(TargetKind.SELF)
        play.release(HAND, None)
        assert play.click(ABOVE, None) == PlayRequest(2, None)

    def test_sticky_self_card_click_in_hand_cancels(self):
        play = _picked(TargetKind.SELF)
        play.release(HAND, None)
        assert play.click(HAND, None) is None and not play.active

    def test_sticky_aim_follows_pointer_target(self):
        play = _picked(TargetKind.ENEMY)
        play.release(HAND, None)
        play.move(ABOVE, 2)
        assert play.target == 2


class TestKeyboard:
    def test_key_pick_aims_at_first_target(self):
        play = CardPlayInput(LINE)
        play.pick_with_key(0, TargetKind.ENEMY, 1)
        assert (play.aiming, play.target, play.keyboard_aim) == (True, 1, True)

    def test_key_pick_without_enemies_has_no_target(self):
        play = CardPlayInput(LINE)
        play.pick_with_key(0, TargetKind.ENEMY, None)
        assert play.target is None and play.confirm() is None

    def test_cycle_right_wraps(self):
        play = CardPlayInput(LINE)
        play.pick_with_key(0, TargetKind.ENEMY, 2)
        play.cycle_target([0, 2], 1)
        assert play.target == 0

    def test_cycle_left_wraps(self):
        play = CardPlayInput(LINE)
        play.pick_with_key(0, TargetKind.ENEMY, 0)
        play.cycle_target([0, 1, 2], -1)
        assert play.target == 2

    def test_cycle_skips_dead_target(self):
        play = CardPlayInput(LINE)
        play.pick_with_key(0, TargetKind.ENEMY, 1)
        play.cycle_target([0, 2], 1)
        assert play.target == 0

    def test_cycle_does_nothing_when_idle(self):
        play = CardPlayInput(LINE)
        play.cycle_target([0, 1], 1)
        assert play.target is None

    def test_confirm_plays_on_target(self):
        play = CardPlayInput(LINE)
        play.pick_with_key(3, TargetKind.ENEMY, 1)
        assert play.confirm() == PlayRequest(3, 1)

    def test_confirm_self_card(self):
        play = CardPlayInput(LINE)
        play.pick_with_key(1, TargetKind.SELF, None)
        assert play.armed and play.confirm() == PlayRequest(1, None)

    def test_confirm_when_idle(self):
        assert CardPlayInput(LINE).confirm() is None

    def test_mouse_motion_hands_aim_back_to_pointer(self):
        play = CardPlayInput(LINE)
        play.pick_with_key(0, TargetKind.ENEMY, 1)
        play.move((10, 10), None)
        assert (play.keyboard_aim, play.target) == (False, None)


class TestCancel:
    def test_cancel_reports_holding(self):
        assert _picked(TargetKind.SELF).cancel()

    def test_cancel_when_idle(self):
        assert not CardPlayInput(LINE).cancel()

    def test_cancel_clears_everything(self):
        play = _picked(TargetKind.ENEMY)
        play.move(ABOVE, 1)
        play.cancel()
        assert (play.mode, play.card, play.target, play.sticky) == (Mode.IDLE, None, None, False)


class TestStress:
    def test_ten_thousand_moves_keep_state_consistent(self):
        play = _picked(TargetKind.ENEMY)
        for step in range(10_000):
            y = 100 + (step * 37) % 700
            enemy = step % 3 if y < LINE else None
            play.move((step % 1280, y), enemy)
            assert play.aiming == (y < LINE)
            if play.aiming:
                assert play.target == enemy

    def test_thousand_cycles_visit_every_target(self):
        play = CardPlayInput(LINE)
        play.pick_with_key(0, TargetKind.ENEMY, 0)
        seen = set()
        for _ in range(1000):
            play.cycle_target([0, 1, 2], 1)
            seen.add(play.target)
        assert seen == {0, 1, 2}

    def test_huge_coordinates(self):
        play = _picked(TargetKind.ENEMY)
        play.move((10 ** 9, -10 ** 9), 0)
        assert play.release((10 ** 9, -10 ** 9), 0) == PlayRequest(2, 0)
