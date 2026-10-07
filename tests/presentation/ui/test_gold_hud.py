"""ui/gold_hud.py — the shared gold counter, and how the SceneManager shows it.

Covers formatting (groups, millions, 10^30, negatives), sync without animation,
counting towards the target within COUNT_TIME, +N / −N labels and their expiry,
spin and flash on change, drawing at each anchor, dt clamp, a 10 000-step stress,
and the SceneManager: drawn on run screens with each scene's position, synced on
a new run, hidden on the main menu.
"""
from __future__ import annotations

import pygame
import pytest

from src.infrastructure.fonts import FontRegistry
from src.presentation.ui.gold_hud import COUNT_TIME, GAIN, LOSS, GoldHud, format_gold


def _hud(amount: int = 100) -> GoldHud:
    h = GoldHud(FontRegistry())
    h.sync(amount)
    return h


def _run(h, seconds, amount, step=1 / 60):
    t = 0.0
    while t < seconds - 1e-9:
        h.update(min(step, seconds - t), amount)
        t += step


class TestFormat:
    def test_small(self):
        assert format_gold(0) == "0"

    def test_groups(self):
        assert format_gold(12345) == "12 345"

    def test_millions_use_suffix(self):
        assert format_gold(1_500_000) == "1.5M"

    def test_huge(self):
        assert format_gold(10 ** 30)

    def test_negative(self):
        assert format_gold(-1200) == "-1 200"


class TestCounting:
    def test_sync_is_instant(self):
        h = _hud(500)
        assert (h.shown, h.target, h.counting) == (500, 500, False)

    def test_first_update_syncs(self):
        h = GoldHud(FontRegistry())
        h.update(0.016, 777)
        assert h.shown == 777 and h.deltas == []

    def test_counts_up_gradually(self):
        h = _hud(100)
        h.update(0.05, 400)
        assert 100 < h.shown < 400

    def test_reaches_target_in_time(self):
        h = _hud(100)
        _run(h, COUNT_TIME + 0.05, 400)
        assert h.shown == 400 and not h.counting

    def test_counts_down(self):
        h = _hud(400)
        _run(h, COUNT_TIME + 0.05, 120)
        assert h.shown == 120

    def test_huge_change_still_in_time(self):
        h = _hud(0)
        _run(h, COUNT_TIME + 0.05, 10 ** 12)
        assert h.shown == 10 ** 12

    def test_gain_label(self):
        h = _hud(100)
        h.update(0.01, 150)
        assert h.deltas == [("+50", GAIN)]

    def test_loss_label(self):
        h = _hud(100)
        h.update(0.01, 20)
        assert h.deltas == [("−80", LOSS)]

    def test_labels_expire(self):
        h = _hud(100)
        h.update(0.01, 150)
        _run(h, 2.0, 150)
        assert h.deltas == []

    def test_labels_capped(self):
        h = _hud(0)
        for k in range(1, 30):
            h.update(0.01, k)
        assert len(h.deltas) <= 6

    def test_flash_and_spin_on_change(self):
        h = _hud(0)
        h.update(0.01, 5)
        assert h._flash > 0 and h._spin > 0

    def test_dt_clamped(self):
        h = _hud(0)
        h.update(10 ** 9, 50)
        assert h.shown <= 50


class TestDraw:
    @pytest.mark.parametrize("anchor,pos", [("topright", (1268, 12)), ("topleft", (12, 476)),
                                            ("midtop", (640, 10))])
    def test_anchor(self, anchor, pos):
        h = _hud(250)
        rect = h.draw(pygame.Surface((1280, 720)), anchor, pos)
        assert getattr(rect, anchor) == pos

    def test_wide_numbers_grow_the_plate(self):
        h1, h2 = _hud(5), _hud(999_999)
        s = pygame.Surface((1280, 720))
        assert h2.draw(s).width > h1.draw(s).width

    def test_stress_10000(self):
        h = _hud(0)
        s = pygame.Surface((1280, 720))
        for k in range(10_000):
            h.update(1 / 60, (k * 37) % 5000)
            if k % 500 == 0:
                h.draw(s)
        assert h._fx.count <= h._fx.capacity


class TestSceneManager:
    def _manager(self):
        import main
        from src.application.run_manager import create_run
        from src.domain.character import ALL_CHARACTERS
        from src.infrastructure.preferences import UserPreferences
        from src.presentation.scenes.map_scene import MapScene
        fonts = FontRegistry()
        m = main.SceneManager(main.MainMenuScene(fonts), fonts, UserPreferences())
        m._run = create_run(ALL_CHARACTERS[0], 3)
        m._run.gold = 321
        m.push(MapScene(m._run, fonts))
        return m

    def test_synced_on_new_run(self):
        m = self._manager()
        m.update(0.016)
        assert m.gold_hud.shown == 321 and m.gold_hud.deltas == []

    def test_drawn_on_map_at_its_spot(self):
        m = self._manager()
        m.update(0.016)
        m.draw(pygame.Surface((1280, 720)))
        assert m.gold_hud.rect.topright == (1048, 11)

    def test_change_animates(self):
        m = self._manager()
        m.update(0.016)
        m._run.gold += 60
        m.update(0.016)
        assert m.gold_hud.deltas[0][0] == "+60"

    def test_hidden_without_run(self):
        import main
        from src.infrastructure.preferences import UserPreferences
        fonts = FontRegistry()
        m = main.SceneManager(main.MainMenuScene(fonts), fonts, UserPreferences())
        m.update(0.016)
        m.draw(pygame.Surface((1280, 720)))
        assert m.gold_hud.rect.width == 0
