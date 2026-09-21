import pygame
from src.application.combat_manager import create_sample_combat
from src.application.run_manager import _all_relic_defs
from src.infrastructure.fonts import FontRegistry
from src.presentation.ui.pile_viewer import PileViewer
from src.presentation.scenes.combat_scene import CombatScene, _card_positions
from src.presentation.ui.card_widget import CARD_W


def test_pile_scroll_reaches_last_card_and_clamps():
    cards = create_sample_combat().hand.cards * 12
    viewer = PileViewer('Robo', cards, FontRegistry())
    surface = pygame.Surface((1280, 720))
    viewer.draw(surface)
    assert viewer._max_scroll > 0
    viewer.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_END))
    viewer.draw(surface)
    assert len(cards) - 1 in viewer._visible_indices
    assert viewer._scroll_y == viewer._max_scroll
    viewer.handle_event(pygame.event.Event(pygame.MOUSEWHEEL, y=-10000))
    assert viewer._scroll_y == viewer._max_scroll
    viewer.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_HOME))
    assert viewer._scroll_y == 0


def test_viewer_preserves_callers_clip_and_close_button_works():
    viewer = PileViewer('Robo', create_sample_combat().hand.cards, FontRegistry())
    surface = pygame.Surface((1280, 720))
    original = pygame.Rect(0, 0, 1270, 710)
    surface.set_clip(original)
    viewer.draw(surface)
    assert surface.get_clip() == original
    viewer.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=viewer._close_rect.center))
    assert viewer.dismissed


def test_large_hand_stays_between_mana_and_piles():
    for count in (1, 5, 10, 20):
        positions = _card_positions(count)
        assert min(x for x, y in positions) >= 175
        assert max(x + CARD_W for x, y in positions) <= 1110


def test_relic_collection_opens_and_scrolls_without_covering_turn_controls():
    from src.presentation.ui.relic_viewer import RelicViewer
    state = create_sample_combat()
    state.relics = _all_relic_defs() * 5
    scene = CombatScene(state, FontRegistry())
    surface = pygame.Surface((1280, 720))
    scene.draw(surface)
    assert len(scene._relic_rects) <= 5
    scene._handle_click(scene._relic_collection_rect.center)
    assert isinstance(scene._overlay, RelicViewer)
    scene.draw(surface)
    scene.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_END))
    scene.draw(surface)
    assert len(state.relics) - 1 in scene._overlay._visible_indices


def test_turn_draw_count_uses_same_bonuses_as_gameplay():
    from src.application.end_turn import cards_per_turn
    from src.application import relic_effects
    state = create_sample_combat()
    assert cards_per_turn(state) == 5 + relic_effects.extra_draw_per_turn(state.relics) + state.player.luck // 5


def test_scrollbar_drag_and_short_collection():
    cards = create_sample_combat().hand.cards * 12
    viewer = PileViewer('Descarte', cards, FontRegistry())
    viewer.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=viewer._thumb.center))
    viewer.handle_event(pygame.event.Event(pygame.MOUSEMOTION, pos=viewer._track.bottomleft))
    viewer.handle_event(pygame.event.Event(pygame.MOUSEBUTTONUP, button=1, pos=viewer._track.bottomleft))
    assert viewer._scroll_y == viewer._max_scroll
    assert viewer._drag_offset is None
    small = PileViewer('Robo', cards[:1], FontRegistry())
    small.handle_event(pygame.event.Event(pygame.MOUSEWHEEL, y=-20))
    assert small._scroll_y == small._max_scroll == 0


def test_hovered_hand_card_draws_last_and_receives_click():
    state = create_sample_combat()
    state.hand.cards = (state.hand.cards * 2)[:10]
    scene = CombatScene(state, FontRegistry())
    surface = pygame.Surface((1280, 720))
    scene.draw(surface)
    scene._hovered_card = 4
    scene.draw(surface)
    assert scene._card_draw_order[-1] == 4
    assert scene._card_hit_order()[0] == 4
    assert scene._card_rects[4].y < scene._card_rects[3].y


def test_map_collections_block_underlying_map_clicks():
    from src.application.run_manager import create_run
    from src.domain.character import ALL_CHARACTERS
    from src.presentation.scenes.map_scene import MapScene
    scene = MapScene(create_run(ALL_CHARACTERS[0], 42), FontRegistry())
    scene.draw(pygame.Surface((1280, 720)))
    scene.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=scene._deck_collection_rect.center))
    assert isinstance(scene._overlay, PileViewer)
    scene.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_END))
    assert scene.selected_node is None
    scene.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE))
    scene.update(0.1)
    assert scene._overlay is None


def test_mana_does_not_paint_flattened_segments_outside_its_orb():
    from src.presentation.ui.hud_widget import draw_mana
    from src.domain.mana import Mana
    surface = pygame.Surface((160, 160))
    surface.fill((1, 2, 3))
    draw_mana(surface, Mana(current=4, maximum=4), 80, 80, FontRegistry())
    assert surface.get_at((46, 44))[:3] == (1, 2, 3)
