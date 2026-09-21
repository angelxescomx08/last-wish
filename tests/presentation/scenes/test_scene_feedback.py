"""Interaction feedback is actionable, single-shot, and quiet on idle motion."""
import pygame
import pytest

from src.application.combat_manager import create_sample_combat
from src.application.run_manager import create_run, pick_boss_relics
from src.domain.character import ALL_CHARACTERS
from src.infrastructure.fonts import FontRegistry
from src.presentation.scenes.boss_reward_scene import BossRewardScene
from src.presentation.scenes.character_select_scene import CharacterSelectScene
from src.presentation.scenes.combat_reward_scene import CombatRewardScene
from src.presentation.scenes.combat_scene import CombatScene
from src.presentation.scenes.death_scene import DeathScene
from src.presentation.scenes.event_scene import EventScene
from src.presentation.scenes.main_menu_scene import MainMenuScene
from src.presentation.scenes.map_scene import MapScene
from src.presentation.scenes.pack_opening_scene import PackOpeningScene
from src.presentation.scenes.shop_scene import ShopScene
from src.presentation.scenes.treasure_scene import TreasureScene


class RecordingSound:
    def __init__(self):
        self.calls = []

    def __getattr__(self, name):
        if name.startswith('play_'):
            return lambda: self.calls.append(name)
        raise AttributeError(name)


def _draw(scene):
    scene.draw(pygame.Surface((1280, 720)))
    return scene


def _click(scene, pos):
    scene.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=pos))


def _motion(scene, pos):
    scene.handle_event(pygame.event.Event(pygame.MOUSEMOTION, pos=pos))


def _run():
    return create_run(ALL_CHARACTERS[0], 42)


@pytest.mark.parametrize('factory,rects', [
    (lambda sound: MainMenuScene(FontRegistry(), sound=sound), '_option_rects'),
    (lambda sound: DeathScene(FontRegistry(), 3, sound=sound), '_option_rects'),
    (lambda sound: CharacterSelectScene(FontRegistry(), sound=sound), '_panel_rects'),
])
def test_navigation_only_sounds_when_selection_changes(factory, rects):
    sound = RecordingSound()
    scene = _draw(factory(sound))
    pos = getattr(scene, rects)[1].center
    for _ in range(100):
        _motion(scene, pos)
    assert sound.calls == ['play_nav']


def test_confirming_menu_twice_before_transition_plays_once():
    sound = RecordingSound()
    scene = _draw(MainMenuScene(FontRegistry(), sound=sound))
    for _ in range(2):
        _click(scene, scene._option_rects[0].center)
    assert sound.calls == ['play_confirm']


def test_shop_purchase_sold_and_unaffordable_have_distinct_feedback():
    sound = RecordingSound()
    run = _run()
    scene = _draw(ShopScene(run, FontRegistry(), sound=sound))
    _click(scene, scene._relic_rects[0].center)
    _click(scene, scene._relic_rects[0].center)
    run.gold = 0
    _click(scene, scene._pack_rects[0].center)
    assert sound.calls == ['play_purchase', 'play_error', 'play_error']


def test_shop_error_message_expires_and_cannot_consume_stock():
    run = _run()
    run.gold = 0
    scene = _draw(ShopScene(run, FontRegistry(), sound=RecordingSound()))
    _click(scene, scene._pack_rects[0].center)
    assert 'oro' in scene._feedback_text.lower()
    scene.update(5)
    assert scene._feedback_time == 0 and not scene._sold_packs


def test_map_travel_only_fires_for_available_node_once():
    sound = RecordingSound()
    run = _run()
    scene = _draw(MapScene(run, FontRegistry(), sound=sound))
    locked = next(node for node in run.current_map.nodes.values() if not node.available)
    available = next(node for node in run.current_map.nodes.values() if node.available)
    _click(scene, scene._node_rects[locked.id].center)
    for _ in range(2):
        _click(scene, scene._node_rects[available.id].center)
    assert sound.calls == ['play_travel']


def test_pack_reveal_is_once_and_card_choice_is_once():
    sound = RecordingSound()
    scene = _draw(PackOpeningScene(_run().deck[:5], 'Sobre', FontRegistry(), sound=sound))
    for _ in range(100):
        scene.update(1 / 60)
    for _ in range(2):
        _click(scene, scene._card_rects[0].center)
    assert sound.calls == ['play_open_pack', 'play_reward']


@pytest.mark.parametrize('factory,rect', [
    (lambda run, sound: CombatRewardScene(run, 20, run.deck[:3], FontRegistry(), sound=sound), '_card_rects'),
    (lambda run, sound: TreasureScene(run, pick_boss_relics(run)[0], FontRegistry(), sound=sound), '_take_rect'),
    (lambda run, sound: EventScene(run, 20, 'event', FontRegistry(), sound=sound), '_btn_rect'),
])
def test_reward_collection_only_plays_once(factory, rect):
    sound = RecordingSound()
    scene = _draw(factory(_run(), sound))
    target = getattr(scene, rect)
    pos = (target[0] if isinstance(target, list) else target).center
    for _ in range(2):
        _click(scene, pos)
    assert sound.calls == ['play_reward']


def test_boss_reward_confirmation_and_relic_collection():
    sound = RecordingSound()
    run = _run()
    scene = _draw(BossRewardScene(run, 100, pick_boss_relics(run), FontRegistry(), sound=sound))
    _click(scene, scene._btn_rect.center)
    scene.pack_done()
    _draw(scene)
    for _ in range(2):
        _click(scene, scene._relic_rects[0].center)
    assert sound.calls == ['play_confirm', 'play_reward']


def test_pile_open_and_close_each_have_one_cue():
    sound = RecordingSound()
    scene = _draw(CombatScene(create_sample_combat(), FontRegistry(), sound=sound))
    _click(scene, scene._draw_pile_rect.center)
    scene.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE))
    scene.update(0.1)
    scene.update(0.1)
    assert sound.calls == ['play_card', 'play_cancel']


def test_rejected_card_has_only_error_feedback():
    sound = RecordingSound()
    scene = CombatScene(create_sample_combat(), FontRegistry(), sound=sound)
    scene._do_play_card(-1, None)
    assert sound.calls == ['play_error']


def test_unaffordable_card_click_explains_failure_without_selecting():
    sound = RecordingSound()
    state = create_sample_combat()
    state.mana.current = 0
    scene = _draw(CombatScene(state, FontRegistry(), sound=sound))
    index = next(i for i, card in enumerate(state.hand.cards) if card.cost > 0)
    _click(scene, scene._card_rects[index].center)
    assert sound.calls == ['play_error'] and state.selected_card_index is None


def test_empty_click_and_idle_updates_remain_silent():
    sound = RecordingSound()
    scene = _draw(ShopScene(_run(), FontRegistry(), sound=sound))
    _click(scene, (0, 0))
    for _ in range(100):
        scene.update(1 / 60)
        _motion(scene, (0, 0))
    assert sound.calls == []


def test_shop_pack_purchase_is_charged_and_announced_once_before_transition():
    sound = RecordingSound()
    run = _run()
    scene = _draw(ShopScene(run, FontRegistry(), sound=sound))
    initial_gold = run.gold
    for _ in range(2):
        _click(scene, scene._pack_rects[0].center)
    assert sound.calls == ['play_purchase']
    assert run.gold == initial_gold - scene._packs[0].cost
    assert scene._sold_packs == {0}


def test_combat_target_selection_and_escape_only_sound_once():
    sound = RecordingSound()
    state = create_sample_combat()
    scene = _draw(CombatScene(state, FontRegistry(), sound=sound))
    index = next(i for i, card in enumerate(state.hand.cards) if card.total_damage() > 0)
    _click(scene, scene._card_rects[index].center)
    for _ in range(2):
        scene.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE))
    assert sound.calls == ['play_confirm', 'play_cancel']
    assert state.selected_card_index is None


def test_switching_to_unaffordable_card_preserves_target_selection_and_shows_error():
    sound = RecordingSound()
    state = create_sample_combat()
    scene = _draw(CombatScene(state, FontRegistry(), sound=sound))
    attack = next(i for i, card in enumerate(state.hand.cards) if card.total_damage() > 0)
    _click(scene, scene._card_rects[attack].center)
    state.mana.current = 0
    index = next(i for i, card in enumerate(state.hand.cards) if i != attack and card.cost > 0)
    _click(scene, scene._card_rects[index].center)
    assert sound.calls == ['play_confirm', 'play_error']
    assert state.selected_card_index == attack
    assert 'insuficiente' in scene._feedback_text
    assert scene._feedback_time > 0
    _draw(scene)
    scene.update(5)
    assert scene._feedback_time == 0


def test_shop_and_combat_card_hover_stay_silent_while_pointer_remains():
    for factory, rects in (
        (lambda sound: ShopScene(_run(), FontRegistry(), sound=sound), '_pack_rects'),
        (lambda sound: CombatScene(create_sample_combat(), FontRegistry(), sound=sound), '_card_rects'),
    ):
        sound = RecordingSound()
        scene = _draw(factory(sound))
        for _ in range(100):
            _motion(scene, getattr(scene, rects)[0].center)
        assert sound.calls == ['play_nav']
