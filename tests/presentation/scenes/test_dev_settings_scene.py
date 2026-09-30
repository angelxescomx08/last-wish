"""Pruebas screen: rows, adjusting values, toggles, reset and leaving."""
import pygame

from src.domain.chroma import Chroma
from src.domain.tuning import TUNING, chroma_chance
from src.infrastructure.fonts import FontRegistry
from src.presentation.scenes.dev_settings_scene import DevSettingsScene, _Kind


class Sound:
    def __getattr__(self, name):
        return lambda *a: None


def _scene():
    scene = DevSettingsScene(FontRegistry(), sound=Sound())
    scene.draw(pygame.Surface((1280, 720)))
    return scene


def _index(scene, label_part):
    return next(i for i, r in enumerate(scene._rows) if label_part in r.label)


def _key(scene, key):
    scene.handle_event(pygame.event.Event(pygame.KEYDOWN, key=key))


def test_has_a_row_per_chroma_and_kind_and_fits_the_screen():
    scene = _scene()
    percent = [r for r in scene._rows if r.kind is _Kind.PERCENT]
    assert len(percent) == 3 * len(Chroma)
    assert scene._row_rects[-1].bottom <= 680


def test_arrows_change_golden_card_chance_in_steps_of_5():
    scene = _scene()
    i = _index(scene, "cartas doradas")
    scene._selected = i
    for _ in range(3):
        _key(scene, pygame.K_RIGHT)
    assert chroma_chance(Chroma.GOLDEN, "card") == 0.20
    for _ in range(30):
        _key(scene, pygame.K_RIGHT)
    assert chroma_chance(Chroma.GOLDEN, "card") == 1.0
    for _ in range(30):
        _key(scene, pygame.K_LEFT)
    assert chroma_chance(Chroma.GOLDEN, "card") == 0.0


def test_plus_button_click_and_toggle_click():
    scene = _scene()
    i = _index(scene, "Cartas extra")
    minus, plus = scene._buttons[i]
    scene.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=plus.center))
    assert TUNING.extra_draw == 1
    j = _index(scene, "Invencible")
    scene.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=scene._row_rects[j].center))
    assert TUNING.invincible is True


def test_numbers_are_clamped():
    scene = _scene()
    i = _index(scene, "Maná extra")
    for _ in range(50):
        scene.adjust(i, 1)
    assert TUNING.extra_mana == 10
    for _ in range(50):
        scene.adjust(i, -1)
    assert TUNING.extra_mana == 0


def test_reset_and_back():
    scene = _scene()
    TUNING.extra_draw = 5
    scene.activate(_index(scene, "Restablecer"))
    assert TUNING.extra_draw == 0
    _key(scene, pygame.K_ESCAPE)
    assert scene.cleared


def test_values_render():
    scene = _scene()
    texts = [scene.value_text(r) for r in scene._rows]
    assert "5 %" in texts and "x1" in texts and "No" in texts


def test_hero_stats_section_in_right_column():
    scene = _scene()
    for label in ("Suerte extra", "Daño extra", "Destreza extra"):
        i = _index(scene, label)
        assert scene._rows[i].column == 1
        assert scene._row_rects[i].left > 640
    assert all(r.bottom <= 680 for r in scene._row_rects)


def test_luck_row_changes_tuning_and_shift_steps_ten():
    scene = _scene()
    scene._selected = _index(scene, "Suerte extra")
    _key(scene, pygame.K_RIGHT)
    assert TUNING.extra_luck == 1
    scene.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RIGHT, mod=pygame.KMOD_SHIFT))
    assert TUNING.extra_luck == 11
    for _ in range(30):
        scene.adjust(scene._selected, 10)
    assert TUNING.extra_luck == 200


def test_luck_preview_reflects_extra_luck():
    from src.presentation.scenes.dev_settings_scene import luck_preview_lines
    before = luck_preview_lines()
    TUNING.extra_luck = 50
    after = luck_preview_lines()
    assert len(after) == 6 and before != after
    assert any("suerte 58" in line for line in after)   # La Pícara: 8 + 50

