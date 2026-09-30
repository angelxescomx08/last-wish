"""El Brujo scene: grid of the deck, confirmation panel, paying and leaving."""
import pygame

from src.application.run_manager import create_run
from src.application.warlock import upgrade_price
from src.domain.character import ALL_CHARACTERS
from src.infrastructure.fonts import FontRegistry
from src.presentation.scenes.warlock_scene import WarlockScene


class Sound:
    def __getattr__(self, name):
        return lambda *a: None


def _scene(gold=1000):
    run = create_run(ALL_CHARACTERS[0], 1)
    run.gold = gold
    scene = WarlockScene(run, FontRegistry(), sound=Sound())
    scene.draw(pygame.Surface((1280, 720)))
    return scene, run


def _click(scene, pos):
    scene.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=pos))


def test_click_card_then_confirm_upgrades_and_pays():
    scene, run = _scene()
    price = upgrade_price(run.deck[0])
    _click(scene, scene._grid._item_rects[0].center)
    assert scene.selected_index == 0 and scene._overlay == 0
    scene.draw(pygame.Surface((1280, 720)))
    _click(scene, scene._confirm_rect.center)
    assert run.deck[0].is_upgraded and run.gold == 1000 - price
    assert scene.selected_index is None


def test_cancel_and_escape_close_the_panel():
    scene, run = _scene()
    scene.select(0)
    scene.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE))
    assert scene.selected_index is None and not run.deck[0].is_upgraded
    scene.select(0)
    scene.draw(pygame.Surface((1280, 720)))
    _click(scene, scene._cancel_rect.center)
    assert scene.selected_index is None and not run.deck[0].is_upgraded


def test_not_enough_gold_keeps_panel_and_gold():
    scene, run = _scene(gold=0)
    scene.select(0)
    assert not scene.confirm()
    assert run.gold == 0 and not run.deck[0].is_upgraded
    assert scene.selected_index == 0


def test_upgraded_card_cannot_be_selected_again():
    scene, run = _scene()
    scene.select(0)
    scene.confirm()
    scene.select(0)
    assert scene.selected_index is None


def test_leave_button():
    scene, _ = _scene()
    _click(scene, scene._grid._close_rect.center)
    assert scene.cleared


def test_pause_button_does_not_cover_the_title():
    scene, _ = _scene()
    assert not scene.pause_button_rect.colliderect(pygame.Rect(78, 48, 600, 40))


def test_view_upgrades_toggle_by_button_and_key():
    scene, run = _scene()
    grid = scene._grid
    _click(scene, grid.toggle_rect.center)
    assert grid.show_upgraded
    scene.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_v))
    assert not grid.show_upgraded
    assert not any(c.is_upgraded for c in run.deck)       # preview never changes the deck


def test_tooltip_explains_the_upgrade():
    scene, run = _scene()
    tip = scene._grid._tooltip(run.deck[0])
    assert any("Al mejorarla" in line for line in tip.lines)
    assert any("Precio" in line for line in tip.lines)


def test_upgraded_view_draws():
    scene, _ = _scene()
    scene._grid.show_upgraded = True
    scene.draw(pygame.Surface((1280, 720)))
