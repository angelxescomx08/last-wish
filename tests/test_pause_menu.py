"""Pause freezes the run and consumes events; abandonment clears all rooms."""
from unittest.mock import Mock
import pygame
from main import SceneManager
from src.application.run_manager import create_run
from src.domain.character import ALL_CHARACTERS
from src.infrastructure.fonts import FontRegistry
from src.infrastructure.preferences import UserPreferences
from src.presentation.scenes.main_menu_scene import MainMenuScene
from src.presentation.ui.pause_menu import PAUSE_BUTTON


def setup_run():
    fonts = FontRegistry()
    manager = SceneManager(MainMenuScene(fonts), fonts, UserPreferences(), sound=Mock())
    manager._run = create_run(ALL_CHARACTERS[0], 42)
    room = Mock()
    room._overlay = None
    manager.push(room)
    return manager, room


def key(manager, value):
    manager.handle_event(pygame.event.Event(pygame.KEYDOWN, key=value))


def test_pause_freezes_room_updates_and_input_and_escape_resumes():
    manager, room = setup_run()
    key(manager, pygame.K_ESCAPE)
    manager.update(10)
    key(manager, pygame.K_a)
    room.update.assert_not_called()
    room.handle_event.assert_not_called()
    key(manager, pygame.K_ESCAPE)
    manager.update(0.1)
    room.update.assert_called_once_with(0.1)


def test_abandon_requires_confirmation_and_discards_whole_run_stack():
    manager, room = setup_run()
    manager.push(room)
    key(manager, pygame.K_ESCAPE)
    key(manager, pygame.K_DOWN)
    key(manager, pygame.K_RETURN)
    assert manager._run is not None
    assert manager._pause.confirming
    key(manager, pygame.K_DOWN)
    key(manager, pygame.K_RETURN)
    assert manager._run is None
    assert len(manager._stack) == 1
    assert isinstance(manager._top(), MainMenuScene)
    assert not manager.quit_requested


def test_mouse_button_can_pause_and_cancel_abandonment_without_losing_run():
    manager, room = setup_run()
    run = manager._run
    manager.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=PAUSE_BUTTON.center))
    room.handle_event.assert_not_called()
    for index in (1, 0, 0):
        manager.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=manager._pause.buttons[index].center))
    assert manager._pause is None
    assert manager._run is run
    assert manager._top() is room


def test_escape_on_main_menu_does_not_open_run_pause():
    fonts = FontRegistry()
    manager = SceneManager(MainMenuScene(fonts), fonts, UserPreferences(), sound=Mock())
    key(manager, pygame.K_ESCAPE)
    assert manager._pause is None


def test_escape_cancels_card_before_pausing_and_pause_button_releases_drag():
    from src.application.combat_factory import create_combat_from_run
    from src.application.run_manager import generate_boss
    from src.presentation.scenes.combat_scene import CombatScene
    manager, _ = setup_run()
    scene = CombatScene(create_combat_from_run(manager._run, generate_boss(manager._run)), manager._fonts)
    manager.push(scene)
    scene._play = Mock(active=True)
    scene._play.cancel.return_value = True
    key(manager, pygame.K_ESCAPE)
    scene._play.cancel.assert_called_once()
    assert manager._pause is None
    manager.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=PAUSE_BUTTON.center))
    assert manager._pause is not None
    assert scene._play.cancel.call_count == 2


def test_escape_backs_out_of_confirmation_then_resumes_same_room():
    manager, room = setup_run()
    key(manager, pygame.K_ESCAPE)
    key(manager, pygame.K_DOWN)
    key(manager, pygame.K_RETURN)
    key(manager, pygame.K_ESCAPE)
    assert not manager._pause.confirming
    key(manager, pygame.K_ESCAPE)
    assert manager._pause is None
    assert manager._top() is room


def test_escape_dismisses_collection_before_opening_pause():
    manager, room = setup_run()
    room._overlay = Mock()
    key(manager, pygame.K_ESCAPE)
    room.handle_event.assert_called_once()
    assert manager._pause is None
