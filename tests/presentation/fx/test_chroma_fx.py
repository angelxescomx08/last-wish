"""Chroma visuals: gilded frames, sheen timing, halos, relic boxes and golden cards on screen."""
import pygame
import pytest

from src.domain.card import Card, CardEffect, CardType
from src.domain.chroma import Chroma
from src.domain.numbers import BigValue
from src.domain.relic import Relic, RelicTag
from src.infrastructure.fonts import FontRegistry
from src.presentation.fx import chroma_fx
from src.presentation.ui.card_widget import CARD_H, CARD_W, draw_card, draw_card_at, render_card_surface
from src.presentation.ui.hud_widget import draw_relics
from src.presentation.ui.tooltip import card_tooltip, relic_tooltip

G = Chroma.GOLDEN


def _card(chroma=None):
    return Card(id="golpe_base", name="Golpe", card_type=CardType.ATTACK, cost=1, chroma=chroma,
                base_effect=CardEffect(name="Golpe", damage=BigValue(6)))


class TestStyles:
    def test_every_chroma_has_a_style(self):
        assert set(chroma_fx.STYLES) == set(Chroma)

    def test_gild_frame_turns_grey_gold_and_keeps_alpha(self):
        frame = pygame.Surface((4, 4), pygame.SRCALPHA)
        frame.fill((180, 180, 180, 200))
        r, g, b, a = chroma_fx.gild_frame(frame, G).get_at((1, 1))
        assert a == 200 and r > g > b


class TestSheen:
    def test_visible_only_during_the_sweep(self):
        assert chroma_fx.sheen_frame(40, 60, G, 0.2) is not None
        assert chroma_fx.sheen_frame(40, 60, G, chroma_fx.SHEEN_SWEEP + 0.1) is None
        assert chroma_fx.sheen_frame(40, 60, G, chroma_fx.SHEEN_CYCLE + 0.2) is not None

    def test_frames_are_cached(self):
        a = chroma_fx.sheen_frame(40, 60, G, 0.3)
        assert a is chroma_fx.sheen_frame(40, 60, G, 0.3)
        assert a.get_size() == (40, 60)

    def test_zero_size_is_safe(self):
        assert chroma_fx.sheen_frame(0, 10, G, 0.2) is None


class TestComposites:
    def test_animated_face_keeps_card_shape(self):
        body = pygame.Surface((20, 30), pygame.SRCALPHA)
        body.fill((50, 50, 50, 255), (5, 5, 10, 20))
        out = chroma_fx.animate_card_face(body, G, 0.4, base_w=20)
        assert out is not body and out.get_size() == (20, 30)
        assert out.get_at((0, 0))[3] == 0          # transparent corners stay transparent
        assert body.get_at((10, 10)) == (50, 50, 50, 255)  # original untouched

    def test_halo_adds_warm_light(self):
        surf = pygame.Surface((200, 200))
        chroma_fx.draw_halo(surf, (100, 100), (80, 100), G, 0.0)
        r, g, b = surf.get_at((100, 100))[:3]
        assert r > 0 and r >= g > b

    @pytest.mark.parametrize("size", [(48, 48), (400, 220), (8, 8), (1, 1)])
    def test_box_draws_gold_border(self, size):
        surf = pygame.Surface((500, 300))
        rect = pygame.Rect(10, 10, *size)
        chroma_fx.draw_chroma_box(surf, rect, G, 0.3)
        if size[0] >= 48:
            r, g, b = surf.get_at((rect.centerx, rect.top))[:3]
            assert r > 200 and g > 150 and b < 200


class TestGoldenCardsAndRelicsOnScreen:
    def test_face_has_gilded_frame_and_distinct_cache(self):
        fonts = FontRegistry()
        normal = render_card_surface(_card(), fonts)
        golden = render_card_surface(_card(G), fonts)
        assert normal is not golden
        assert golden.get_size() == (CARD_W, CARD_H)

    def test_golden_card_keeps_stats_and_explains_double_cast(self):
        tip = card_tooltip(_card(G))
        text = "\n".join(tip.lines)
        assert tip.title == "Golpe · Dorada"
        assert "Inflige 6" in text and "2 veces" in text

    def test_draw_card_and_draw_card_at_with_tilt(self):
        fonts = FontRegistry()
        surf = pygame.Surface((1280, 720))
        rect = draw_card(surf, _card(G), 100, 100, fonts)
        assert rect.size == (CARD_W, CARD_H)
        for angle in (0, 7.0):
            r = draw_card_at(surf, _card(G), (640, 360), fonts, scale=1.3, angle=angle)
            assert r.center == (640, 360)

    def test_relic_bar_and_tooltip(self):
        relic = Relic("r_fire", "Orbe de Fuego", "+2 de daño.", tag=RelicTag.FIRE_ORB, chroma=G)
        surf = pygame.Surface((400, 100))
        rects = draw_relics(surf, [relic], 10, 10, FontRegistry())
        assert len(rects) == 1
        tip = relic_tooltip(relic)
        assert tip.title == "Orbe de Fuego · Dorada"
        assert any("x2" in line for line in tip.lines)

    def test_stress_many_frames(self):
        fonts = FontRegistry()
        surf = pygame.Surface((1280, 720))
        for i in range(600):
            t = i / 60
            face = chroma_fx.animate_card_face(render_card_surface(_card(G), fonts), G, t)
            surf.blit(face, (0, 0))
            chroma_fx.draw_chroma_box(surf, pygame.Rect(300, 20, 48, 48), G, t)
        assert chroma_fx._sheen_frames.cache_info().currsize <= 48


class TestAuraAndMotes:
    def test_aura_hugs_silhouette_and_leaves_inside_dark(self):
        body = pygame.Surface((60, 80), pygame.SRCALPHA)
        body.fill((200, 200, 200, 255), (10, 5, 40, 60))     # frame smaller than its rect
        aura, pad = chroma_fx.card_aura(body, G, 3, key=("test", 60, 80))
        assert aura.get_size() == (60 + 2 * pad, 80 + 2 * pad)
        inside = aura.get_at((pad + 30, pad + 35))[:3]
        edge = aura.get_at((pad + 8, pad + 35))[:3]            # just outside the opaque part
        far = aura.get_at((0, 0))[:3]
        assert inside == (0, 0, 0)
        assert edge[0] > 20 and edge[0] >= edge[2]
        assert far[0] < edge[0]

    def test_aura_cache(self):
        body = pygame.Surface((30, 40), pygame.SRCALPHA)
        body.fill((255, 255, 255, 255))
        a, _ = chroma_fx.card_aura(body, G, 2, key=("k",))
        b, _ = chroma_fx.card_aura(body, G, 2, key=("k",))
        assert a is b

    def test_motes_draw_near_rect(self):
        surf = pygame.Surface((300, 300))
        chroma_fx.draw_motes(surf, pygame.Rect(100, 100, 100, 120), G, 1.0)
        lit = [(x, y) for x in range(0, 300, 2) for y in range(0, 300, 2) if surf.get_at((x, y))[0] > 0]
        assert lit and all(60 <= x <= 240 for x, _ in lit)


class TestComboCardUi:
    def test_combo_face_and_tooltip(self):
        from src.domain.card_pool import card_factories_for_theme, PackTheme
        tajo = next(f for f in card_factories_for_theme(PackTheme.ACERO) if f.card_id == "a_tajo")()
        fonts = FontRegistry()
        assert render_card_surface(tajo, fonts) is not render_card_surface(tajo, fonts, combo=True)
        tip = card_tooltip(tajo)
        text = "\n".join(tip.lines)
        assert "Combo" in text and "+5 de daño" in text
        active = "\n".join(card_tooltip(tajo, combo_active=True).lines)
        assert "11" in active and "¡Activo!" in active
        surf = pygame.Surface((1280, 720))
        draw_card_at(surf, tajo, (640, 360), fonts, angle=4.0, combo=True)
