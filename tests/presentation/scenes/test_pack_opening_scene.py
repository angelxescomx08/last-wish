"""Animated pack opening: phases, skipping, flips, choosing and robustness."""
import pygame
import pytest

from src.application.run_manager import create_run
from src.domain.card import CardRarity
from src.domain.character import ALL_CHARACTERS
from src.infrastructure.fonts import FontRegistry
from src.presentation.scenes import pack_opening_scene as pos
from src.presentation.scenes.pack_opening_scene import PackOpeningScene

SURF = (1280, 720)


class Sound:
    def __init__(self):
        self.calls = []

    def __getattr__(self, name):
        if name.startswith('play_'):
            return lambda: self.calls.append(name)
        raise AttributeError(name)


def _cards(n=5, rarities=None):
    cards = create_run(ALL_CHARACTERS[0], 42).deck[:n]
    for card, rarity in zip(cards, rarities or []):
        card.rarity = rarity
    return cards


def _scene(theme='acero', cards=None, sound=None):
    return PackOpeningScene(cards if cards is not None else _cards(), 'Sobre de Acero',
                            FontRegistry(), sound=sound or Sound(), theme=theme)


def _run(scene, seconds, step=1 / 60, draw=False):
    surf = pygame.Surface(SURF) if draw else None
    for _ in range(int(round(seconds / step))):
        scene.update(step)
        if surf is not None:
            scene.draw(surf)


def _click(scene, pos=(640, 360)):
    scene.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=pos))


class TestPhases:
    def test_starts_in_intro_then_waits_idle(self):
        scene = _scene()
        assert scene.phase == 'intro'
        _run(scene, pos.INTRO_T + 0.05)
        assert scene.phase == 'idle'
        _run(scene, 20.0)
        assert scene.phase == 'idle'
        assert not scene.cleared

    def test_click_charges_then_bursts(self):
        sound = Sound()
        scene = _scene(sound=sound)
        _run(scene, 1.0)
        _click(scene)
        assert scene.phase == 'charge'
        assert sound.calls == ['play_confirm']
        _run(scene, pos.CHARGE_T + 0.02)
        assert scene.phase == 'burst'
        assert sound.calls.count('play_open_pack') == 1
        assert scene.particle_count > 150

    def test_space_key_opens_too(self):
        scene = _scene()
        scene.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE))
        assert scene.phase == 'charge'

    def test_full_sequence_reaches_pick(self):
        scene = _scene()
        _click(scene)
        seen = []
        for _ in range(8 * 60):
            scene.update(1 / 60)
            if not seen or seen[-1] != scene.phase:
                seen.append(scene.phase)
        assert seen == ['charge', 'burst', 'deal', 'reveal', 'pick']
        assert scene._flipped == [True] * 5
        assert not scene.is_animating

    def test_rare_cards_wait_longer_before_flipping(self):
        rarities = [CardRarity.COMMON, CardRarity.LEGENDARY, CardRarity.COMMON,
                    CardRarity.COMMON, CardRarity.COMMON]
        scene = _scene(cards=_cards(rarities=rarities))
        gaps = [b - a for a, b in zip(scene._flip_start, scene._flip_start[1:])]
        assert gaps[0] == pytest.approx(pos.FLIP_STAGGER + pos.ANTICIPATION_T)
        assert gaps[1] == pytest.approx(pos.FLIP_STAGGER)

    def test_epic_flip_plays_reward_sound(self):
        sound = Sound()
        rarities = [CardRarity.EPIC] + [CardRarity.COMMON] * 4
        scene = _scene(cards=_cards(rarities=rarities), sound=sound)
        _click(scene)
        _run(scene, 8.0)
        assert sound.calls.count('play_reward') == 1
        assert sound.calls.count('play_card') == 5      # 1 deal + 4 common flips


class TestSkipping:
    @pytest.mark.parametrize('after', [0.1, 0.9, 1.3, 2.0, 3.0])
    def test_click_during_animation_skips_to_pick(self, after):
        scene = _scene()
        _click(scene)
        _run(scene, after)
        _click(scene)
        assert scene.phase == 'pick'
        assert scene._landed == [True] * 5 and scene._flipped == [True] * 5
        assert scene.chosen_card is None
        assert not scene.cleared

    def test_skip_from_idle_opens_directly(self):
        sound = Sound()
        scene = _scene(sound=sound)
        _run(scene, 1.0)
        scene.skip_animation()
        assert scene.phase == 'pick'
        assert sound.calls.count('play_open_pack') == 1

    def test_skip_click_does_not_choose_a_card(self):
        scene = _scene()
        _click(scene)
        _run(scene, 2.0, draw=True)
        _click(scene, (640, 217))
        assert scene.chosen_card is None


class TestChoosing:
    def _pick_ready(self, sound=None):
        scene = _scene(sound=sound)
        scene.skip_animation()
        scene.draw(pygame.Surface(SURF))
        return scene

    def test_choosing_plays_outro_then_clears(self):
        scene = self._pick_ready()
        card = scene._cards[2]
        _click(scene, scene._card_rects[2].center)
        assert scene.phase == 'outro'
        assert scene.chosen_card is card
        assert not scene.cleared
        _run(scene, pos.OUTRO_T + 0.05, draw=True)
        assert scene.cleared
        assert scene.chosen_card is card

    def test_choice_happens_once(self):
        sound = Sound()
        scene = self._pick_ready(sound)
        sound.calls.clear()
        rect = scene._card_rects[0]
        _click(scene, rect.center)
        _click(scene, scene._card_rects[1].center)
        assert sound.calls == ['play_reward']
        assert scene.chosen_card is scene._cards[0]

    def test_skip_button_clears_without_card(self):
        scene = self._pick_ready()
        _click(scene, scene._skip_rect.center)
        assert scene.cleared and scene.chosen_card is None

    def test_cannot_choose_before_pick(self):
        scene = _scene()
        scene.choose(0)
        assert scene.chosen_card is None and scene.phase == 'intro'

    def test_hover_in_pick_sets_hovered(self):
        scene = self._pick_ready()
        scene.handle_event(pygame.event.Event(pygame.MOUSEMOTION, pos=scene._card_rects[3].center,
                                              rel=(0, 0), buttons=(0, 0, 0)))
        assert scene._hovered == 3


class TestRobustness:
    @pytest.mark.parametrize('theme', ['acero', 'escudo', 'magia', 'epico', None, 'desconocido'])
    def test_every_theme_draws_every_phase(self, theme):
        scene = _scene(theme=theme)
        surf = pygame.Surface(SURF)
        _run(scene, 1.0, step=1 / 30, draw=True)
        _click(scene)
        _run(scene, 6.0, step=1 / 30, draw=True)
        assert scene.phase == 'pick'
        scene.draw(surf)
        assert scene._card_rects and len(scene._card_rects) == 5

    def test_split_pack_pieces_cover_the_pack_height(self):
        scene = _scene()
        h = scene._pack.get_height()
        assert scene._strip.get_height() == scene._tear_y + 10
        assert scene._body.get_height() == h - (scene._tear_y - 10)
        assert scene._strip.get_width() == scene._body.get_width() == scene._pack.get_width()

    def test_all_rarities_legendary_draws(self):
        scene = _scene(theme='epico', cards=_cards(rarities=[CardRarity.LEGENDARY] * 5))
        _click(scene)
        _run(scene, 8.0, step=1 / 30, draw=True)
        assert scene.phase == 'pick'
        assert scene.particle_count <= scene._fx.capacity

    def test_empty_pack_does_not_crash(self):
        scene = _scene(cards=[])
        _click(scene)
        _run(scene, 3.0, draw=True)
        assert scene.phase == 'pick'

    def test_stress_ten_thousand_random_updates(self):
        import random
        rng = random.Random(4)
        scene = _scene(theme='magia', cards=_cards(rarities=list(CardRarity)))
        _click(scene)
        for _ in range(10_000):
            scene.update(rng.choice([0.0, 1 / 240, 1 / 60, 0.5, 10 ** 9]))
            assert scene.particle_count <= scene._fx.capacity
        assert scene.phase == 'pick'
        scene.draw(pygame.Surface(SURF))

    def test_easings_hit_endpoints(self):
        assert pos.ease_out_cubic(0) == 0.0 and pos.ease_out_cubic(1) == 1.0
        assert pos.ease_out_back(0) == pytest.approx(0.0) and pos.ease_out_back(1) == pytest.approx(1.0)
        assert pos.ease_out_back(0.7) > 1.0
