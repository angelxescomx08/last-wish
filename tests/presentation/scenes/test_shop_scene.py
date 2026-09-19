import pygame
from src.application.run_manager import create_run
from src.domain.character import ALL_CHARACTERS
from src.infrastructure.fonts import FontRegistry
from src.presentation.scenes.shop_scene import ShopScene


def make_shop():
    run = create_run(ALL_CHARACTERS[0], 42)
    scene = ShopScene(run, FontRegistry())
    scene.draw(pygame.Surface((1280, 720)))
    return run, scene


def test_shop_has_three_packs_and_three_relics():
    _, scene = make_shop()
    assert len(scene._packs) == len(scene._relics) == 3


def test_pack_stays_sold_out_after_returning_from_opening():
    run, scene = make_shop()
    pos = scene._pack_rects[0].center
    scene._handle_click(pos)
    gold_after = run.gold
    assert scene.selected_pack is not None
    scene.selected_pack = None
    scene.draw(pygame.Surface((1280, 720)))
    scene._handle_click(pos)
    assert run.gold == gold_after
    assert scene.selected_pack is None


def test_relic_can_only_be_bought_once():
    run, scene = make_shop()
    pos = scene._relic_rects[0].center
    scene._handle_click(pos)
    gold_after = run.gold
    scene._handle_click(pos)
    assert run.relics == [scene._relics[0]]
    assert run.gold == gold_after < 2000


def test_insufficient_gold_does_not_consume_stock():
    run, scene = make_shop()
    run.gold = 0
    scene._handle_click(scene._pack_rects[0].center)
    scene._handle_click(scene._relic_rects[0].center)
    assert not scene._sold_packs and not scene._sold_relics
    assert not run.relics
    assert scene.selected_pack is None
