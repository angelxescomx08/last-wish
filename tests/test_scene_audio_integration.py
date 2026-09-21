"""Keep one audio mix throughout navigation, room changes and combat results."""
from unittest.mock import Mock

import pygame
import pytest

from main import SceneManager
from src.application.combat_factory import create_combat_from_run
from src.application.run_manager import create_run, generate_boss
from src.domain.character import ALL_CHARACTERS
from src.domain.map_node import MapNode, RoomType
from src.infrastructure.fonts import FontRegistry
from src.infrastructure.preferences import UserPreferences
from src.presentation.scenes.combat_scene import CombatScene
from src.presentation.scenes.main_menu_scene import MainMenuScene, MenuAction
from src.presentation.scenes.map_scene import MapScene
from src.presentation.scenes.pack_opening_scene import PackOpeningScene
from src.presentation.scenes.shop_scene import ShopScene


def manager_with_run():
    fonts = FontRegistry()
    sound = Mock()
    menu = MainMenuScene(fonts, sound=sound)
    manager = SceneManager(menu, fonts, UserPreferences(), sound=sound)
    manager._run = create_run(ALL_CHARACTERS[0], 42)
    return manager, sound, fonts


@pytest.mark.parametrize('room_type', list(RoomType))
def test_all_rooms_share_the_same_audio_without_restarting_music(room_type):
    manager, sound, fonts = manager_with_run()
    scene = MapScene(manager._run, fonts, sound=sound)
    manager.push(scene)
    scene.selected_node = MapNode('audio-test', room_type, 0, 0)
    manager.update(0.016)
    assert manager._top()._sound is sound
    sound.start_music.assert_not_called()


def test_menu_to_settings_shares_audio():
    manager, sound, _ = manager_with_run()
    manager._top().requested_action = MenuAction.SETTINGS
    manager.update(0.016)
    assert manager._top()._sound is sound
    sound.update.assert_called_once()


def test_shop_to_pack_and_back_preserves_mix_and_stock():
    manager, sound, fonts = manager_with_run()
    shop = ShopScene(manager._run, fonts, sound=sound)
    manager.push(shop)
    shop.draw(pygame.Surface((1280, 720)))
    shop._handle_click(shop._pack_rects[0].center)
    manager.update(0.016)
    pack = manager._top()
    assert isinstance(pack, PackOpeningScene)
    assert pack._sound is sound
    pack.cleared = True
    manager.update(0.016)
    assert manager._top() is shop
    assert 0 in shop._sold_packs
    sound.start_music.assert_not_called()


def test_victory_sound_occurs_once_even_across_updates():
    manager, sound, fonts = manager_with_run()
    state = create_combat_from_run(manager._run, generate_boss(manager._run))
    combat = CombatScene(state, fonts, sound=sound)
    manager.push(combat)
    for enemy in state.enemies:
        enemy.current_hp = 0
    manager.update(0.016)
    manager.update(0.016)
    sound.play_win.assert_called_once()
    assert manager._top()._sound is sound


def test_player_death_sound_occurs_once_even_across_updates():
    manager, sound, fonts = manager_with_run()
    state = create_combat_from_run(manager._run, generate_boss(manager._run))
    combat = CombatScene(state, fonts, sound=sound)
    manager.push(combat)
    state.player.current_hp = 0
    manager.update(0.016)
    manager.update(0.016)
    sound.play_death.assert_called_once()
    assert manager._top()._sound is sound
