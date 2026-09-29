"""One-shot burst particles: spawning shapes, lifetime, physics, capacity and drawing.

Stress philosophy (as in test_particles): huge time steps and thousands of
updates never grow the pool past capacity nor teleport particles.
"""
import math

import pygame

from src.presentation.fx.bursts import GLOW, SPARK, SQUARE, BurstParticles, scaled, soft_glow

PAL = ((255, 255, 255), (200, 100, 50))


class TestSpawning:
    def test_emit_adds_one_particle(self):
        fx = BurstParticles(10)
        assert fx.emit(5, 6, 0, 0, life=1.0, palette=PAL) is True
        assert fx.count == 1
        assert fx.positions() == [(5.0, 6.0)]

    def test_emit_refuses_when_full(self):
        fx = BurstParticles(2)
        assert fx.emit(0, 0, 0, 0, life=1, palette=PAL)
        assert fx.emit(0, 0, 0, 0, life=1, palette=PAL)
        assert fx.emit(0, 0, 0, 0, life=1, palette=PAL) is False
        assert fx.count == 2

    def test_emit_refuses_empty_palette(self):
        fx = BurstParticles(5)
        assert fx.emit(0, 0, 0, 0, life=1, palette=()) is False
        assert fx.count == 0

    def test_burst_returns_spawned_count_capped_by_capacity(self):
        fx = BurstParticles(30)
        assert fx.burst(0, 0, 50, palette=PAL) == 30
        assert fx.count == 30

    def test_burst_speeds_stay_in_range(self):
        fx = BurstParticles(200, seed=3)
        fx.burst(0, 0, 200, palette=PAL, speed=(100, 100), drag=0.0)
        fx.update(0.1)
        for x, y in fx.positions():
            assert math.isclose(math.hypot(x, y), 10.0, abs_tol=1e-6)

    def test_burst_angle_range_upwards_only(self):
        fx = BurstParticles(100, seed=1)
        fx.burst(0, 0, 100, palette=PAL, speed=(50, 50), angle=(-math.pi * 0.9, -math.pi * 0.1), drag=0.0)
        fx.update(0.1)
        assert all(y < 0 for _, y in fx.positions())

    def test_implode_arrives_at_centre_as_it_dies(self):
        fx = BurstParticles(50, seed=2)
        fx.implode(100, 100, 50, palette=PAL, radius=(80, 80), life=(0.5, 0.5))
        fx.update(0.25)
        for x, y in fx.positions():
            assert math.isclose(math.hypot(x - 100, y - 100), 40.0, abs_tol=1e-6)
        fx.update(0.26)
        assert fx.count == 0

    def test_same_seed_is_deterministic(self):
        a, b = BurstParticles(40, seed=9), BurstParticles(40, seed=9)
        a.burst(0, 0, 40, palette=PAL)
        b.burst(0, 0, 40, palette=PAL)
        a.update(0.05)
        b.update(0.05)
        assert a.positions() == b.positions()


class TestSimulation:
    def test_particles_die_after_life(self):
        fx = BurstParticles(10)
        fx.emit(0, 0, 0, 0, life=0.3, palette=PAL)
        fx.update(0.1)
        fx.update(0.1)
        assert fx.count == 1
        fx.update(0.1)
        assert fx.count == 0

    def test_gravity_accelerates_down(self):
        fx = BurstParticles(1)
        fx.emit(0, 0, 0, 0, life=5, palette=PAL, gravity=100)
        fx.update(0.1)
        assert math.isclose(fx.positions()[0][1], 1.0, abs_tol=1e-9)

    def test_drag_slows_motion(self):
        free, dragged = BurstParticles(1), BurstParticles(1)
        free.emit(0, 0, 100, 0, life=5, palette=PAL)
        dragged.emit(0, 0, 100, 0, life=5, palette=PAL, drag=5.0)
        for _ in range(5):
            free.update(0.1)
            dragged.update(0.1)
        assert free.positions()[0][0] == 50.0
        assert dragged.positions()[0][0] < 25.0

    def test_dt_is_clamped(self):
        fx = BurstParticles(1)
        fx.emit(0, 0, 10, 0, life=100, palette=PAL)
        fx.update(10 ** 9)
        assert math.isclose(fx.positions()[0][0], 1.0, abs_tol=1e-9)

    def test_negative_dt_is_ignored(self):
        fx = BurstParticles(1)
        fx.emit(0, 0, 10, 0, life=1, palette=PAL)
        fx.update(-5)
        assert fx.positions() == [(0.0, 0.0)]

    def test_clear_empties_the_pool(self):
        fx = BurstParticles(20)
        fx.burst(0, 0, 20, palette=PAL)
        fx.clear()
        assert fx.count == 0

    def test_swap_remove_keeps_survivors(self):
        fx = BurstParticles(3)
        fx.emit(1, 0, 0, 0, life=0.05, palette=PAL)
        fx.emit(2, 0, 0, 0, life=5, palette=PAL)
        fx.emit(3, 0, 0, 0, life=0.05, palette=PAL)
        fx.update(0.1)
        assert fx.positions() == [(2.0, 0.0)]


class TestStress:
    def test_ten_thousand_updates_with_bursts_never_exceed_capacity(self):
        fx = BurstParticles(300, seed=5)
        for step in range(10_000):
            fx.burst(640, 360, 25, palette=PAL, style=(SQUARE, SPARK, GLOW)[step % 3])
            fx.implode(640, 360, 5, palette=PAL)
            fx.update((step % 7) / 30)
            assert fx.count <= 300
        assert 0 < fx.count <= 300

    def test_huge_values_do_not_crash(self):
        fx = BurstParticles(10)
        fx.emit(0, 0, 10 ** 100, -10 ** 100, life=10 ** 100, palette=PAL, size=10 ** 3)
        fx.update(0.1)
        assert fx.count == 1


class TestDrawing:
    def test_square_draws_its_colour(self):
        fx = BurstParticles(1)
        fx.emit(10, 10, 0, 0, life=1, palette=((255, 0, 0),), size=4)
        surf = pygame.Surface((20, 20))
        fx.draw(surf)
        assert surf.get_at((10, 10))[:3] == (255, 0, 0)

    def test_offset_moves_drawing(self):
        fx = BurstParticles(1)
        fx.emit(10, 10, 0, 0, life=1, palette=((0, 255, 0),), size=2)
        surf = pygame.Surface((40, 40))
        fx.draw(surf, (15, 5))
        assert surf.get_at((25, 15))[:3] == (0, 255, 0)
        assert surf.get_at((10, 10))[:3] == (0, 0, 0)

    def test_glow_adds_light(self):
        fx = BurstParticles(1)
        fx.emit(20, 20, 0, 0, life=1, palette=((200, 100, 0),), size=10, style=GLOW)
        surf = pygame.Surface((40, 40))
        fx.draw(surf)
        r, g, b = surf.get_at((20, 20))[:3]
        assert r > 100 and g > 40 and b == 0
        assert surf.get_at((0, 0))[:3] == (0, 0, 0)

    def test_spark_draws_a_streak(self):
        fx = BurstParticles(1)
        fx.emit(30, 10, 0, 400, life=1, palette=((0, 0, 255),), size=2, style=SPARK)
        surf = pygame.Surface((60, 40))
        fx.draw(surf)
        lit = sum(1 for y in range(40) if any(surf.get_at((x, y))[2] == 255 for x in range(28, 33)))
        assert lit >= 10


class TestHelpers:
    def test_soft_glow_is_bright_centre_dark_edge(self):
        g = soft_glow((255, 128, 0), 40)
        assert g.get_size() == (80, 80)
        assert g.get_at((40, 40))[0] > 200
        assert g.get_at((0, 0))[:3] == (0, 0, 0)

    def test_soft_glow_is_cached(self):
        assert soft_glow((10, 20, 30), 12) is soft_glow((10, 20, 30), 12)

    def test_scaled_clamps(self):
        assert scaled((200, 100, 10), 2.0) == (255, 200, 20)
        assert scaled((200, 100, 10), -1) == (0, 0, 0)
