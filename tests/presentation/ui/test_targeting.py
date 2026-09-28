"""Tests for presentation/ui/targeting.py — curve geometry, cached sprites, drawing cost."""
from __future__ import annotations

import math

import pygame

from src.presentation.ui import targeting
from src.presentation.ui.targeting import (
    FLOW_SPEED, HEAD_GAP, SPACING, bezier, control_point, draw_arrow, draw_reticle,
    head_placement, sample_curve, segment_placements,
)

START = (640.0, 400.0)
END = (1000.0, 150.0)


class TestCurve:
    def test_curve_starts_at_card(self):
        assert sample_curve(START, END)[0] == START

    def test_curve_ends_at_pointer(self):
        x, y = sample_curve(START, END)[-1]
        assert (round(x, 6), round(y, 6)) == END

    def test_bezier_midpoint_between_ends(self):
        ctrl = control_point(START, END)
        x, y = bezier(START, ctrl, END, 0.5)
        assert min(START[0], END[0]) <= x <= max(START[0], END[0])

    def test_arrow_leaves_the_card_upward(self):
        first = segment_placements(START, END, 0.0)[0]
        assert first[2] < 0          # screen angles: negative = pointing up

    def test_arrow_bends_toward_the_target(self):
        segs = segment_placements(START, END, 0.0)
        assert segs[-1][2] > segs[0][2]

    def test_straight_up_has_no_bend(self):
        segs = segment_placements(START, (640.0, 100.0), 0.0)
        assert all(abs(a + 90) < 1e-6 for _x, _y, a, _t in segs)


class TestSegments:
    def test_spacing_along_the_curve(self):
        segs = segment_placements(START, (640.0, 100.0), 0.0)
        gaps = [abs(b[1] - a[1]) for a, b in zip(segs, segs[1:])]
        assert all(abs(g - SPACING) < 0.5 for g in gaps)

    def test_segments_grow_toward_head(self):
        sizes = [t for *_rest, t in segment_placements(START, END, 0.0)]
        assert sizes == sorted(sizes)

    def test_head_area_is_left_free(self):
        pts = sample_curve(START, END)
        total = sum(math.dist(a, b) for a, b in zip(pts, pts[1:]))
        last_t = segment_placements(START, END, 0.0)[-1][3]
        assert last_t * total < total - HEAD_GAP + 1e-6

    def test_flow_moves_segments(self):
        a = segment_placements(START, END, 0.0)[0]
        b = segment_placements(START, END, 0.1)[0]
        assert a[:2] != b[:2]

    def test_flow_is_periodic(self):
        period = SPACING / FLOW_SPEED
        a = segment_placements(START, END, 0.0)
        b = segment_placements(START, END, period * 3)
        assert len(a) == len(b) and all(math.isclose(p[0], q[0], abs_tol=1e-6) for p, q in zip(a, b))

    def test_zero_length_has_no_segments(self):
        assert segment_placements(START, START, 0.0) == []

    def test_very_short_arrow_has_no_segments(self):
        assert segment_placements(START, (START[0], START[1] - HEAD_GAP), 0.0) == []

    def test_huge_distance_is_finite(self):
        segs = segment_placements(START, (1e6, -1e6), 12.5)
        assert len(segs) > 1000 and all(math.isfinite(x) for x, *_ in segs)


class TestHead:
    def test_head_sits_on_pointer(self):
        x, y, _a = head_placement(START, END)
        assert (x, y) == END

    def test_head_points_along_the_end_tangent(self):
        _x, _y, a = head_placement(START, (640.0, 100.0))
        assert abs(a + 90) < 1e-6


class TestDrawing:
    def test_draws_pixels_on_the_curve(self):
        surface = pygame.Surface((1280, 720))
        draw_arrow(surface, START, END, hot=True, phase=0.0)
        x, y, *_ = segment_placements(START, END, 0.0)[3]
        assert tuple(surface.get_at((round(x), round(y))))[:3] != (0, 0, 0)

    def test_hot_arrow_is_red(self):
        surface = pygame.Surface((1280, 720))
        draw_arrow(surface, START, (640.0, 100.0), hot=True, phase=0.0)
        colours = {tuple(surface.get_at((640, y)))[:3] for y in range(110, 390)}
        assert targeting.HOT[0] in colours

    def test_cold_arrow_is_pale(self):
        surface = pygame.Surface((1280, 720))
        draw_arrow(surface, START, (640.0, 100.0), hot=False, phase=0.0)
        colours = {tuple(surface.get_at((640, y)))[:3] for y in range(110, 390)}
        assert targeting.COLD[0] in colours and targeting.HOT[0] not in colours

    def test_blit_count_is_segments_plus_head(self):
        surface = pygame.Surface((1280, 720))
        n = draw_arrow(surface, START, END, hot=False, phase=0.3)
        assert n == len(segment_placements(START, END, 0.3)) + 1

    def test_sprites_are_cached_across_frames(self):
        surface = pygame.Surface((1280, 720))
        for frame in range(120):
            draw_arrow(surface, START, (500 + frame * 5, 150.0), hot=frame % 2 == 0, phase=frame / 60)
        # 2 colours × (4 chevrons + head) × 72 angle buckets, plus unrotated bases
        assert len(targeting._sprite_cache) <= 2 * 5 * 73

    def test_reticle_draws_corners_only(self):
        surface = pygame.Surface((400, 400))
        rect = pygame.Rect(100, 100, 150, 150)
        draw_reticle(surface, rect, targeting.RETICLE_ENEMY, 0.0)
        centre = tuple(surface.get_at(rect.center))[:3]
        corner = {tuple(surface.get_at((x, y)))[:3] for x in range(80, 110) for y in range(80, 110)}
        assert centre == (0, 0, 0) and targeting.RETICLE_ENEMY in corner
