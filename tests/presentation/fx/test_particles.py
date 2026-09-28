"""Particle pools: spawning, lifetime, capacity, landing bursts, clipping and drawing.

Stress philosophy: huge time steps and thousands of updates must never grow a
pool past its capacity or spawn a burst of catch-up particles.
"""
import pygame

from src.presentation.fx.particles import EmitterConfig, ParticleSystem


def _config(**kw):
    base = dict(rate=10, lifetime=(1.0, 1.0), area=(10, 10, 0, 0), capacity=50)
    base.update(kw)
    return EmitterConfig(**base)


def _run(system, seconds, step=0.05):
    t = 0.0
    while t < seconds - 1e-9:
        system.update(step)
        t += step


class TestSpawning:
    def test_rate_spawns_expected_count(self):
        system = ParticleSystem(_config(rate=10, lifetime=(5, 5)))
        _run(system, 1.0)
        assert system.count == 10

    def test_zero_rate_spawns_nothing(self):
        system = ParticleSystem(_config(rate=0))
        _run(system, 2.0)
        assert system.count == 0

    def test_capacity_is_never_exceeded(self):
        system = ParticleSystem(_config(rate=1000, lifetime=(10, 10), capacity=25))
        _run(system, 3.0)
        assert system.count == 25

    def test_budget_zero_disables_particles(self):
        system = ParticleSystem(_config(rate=100), budget=0.0)
        _run(system, 1.0)
        assert system.count == 0

    def test_budget_scales_capacity(self):
        system = ParticleSystem(_config(capacity=40), budget=0.5)
        assert system.capacity == 20

    def test_emit_at_reports_how_many_fit(self):
        system = ParticleSystem(_config(rate=0, capacity=3))
        assert system.emit_at(5, 5, 10) == 3


class TestLifetime:
    def test_particles_die_after_their_lifetime(self):
        system = ParticleSystem(_config(rate=0, lifetime=(0.5, 0.5)))
        system.emit_at(0, 0, 5)
        _run(system, 0.6)
        assert system.count == 0

    def test_particles_alive_before_lifetime(self):
        system = ParticleSystem(_config(rate=0, lifetime=(0.5, 0.5)))
        system.emit_at(0, 0, 5)
        _run(system, 0.4)
        assert system.count == 5

    def test_huge_dt_is_clamped(self):
        system = ParticleSystem(_config(rate=100, lifetime=(60, 60), capacity=500))
        system.update(10 ** 9)
        assert system.count == 10

    def test_negative_dt_does_nothing(self):
        system = ParticleSystem(_config(rate=100))
        system.update(-1.0)
        assert system.count == 0

    def test_stress_ten_thousand_updates_stay_bounded(self):
        system = ParticleSystem(_config(rate=300, lifetime=(0.2, 2.0), capacity=80, vy=(-50, 50), wobble=5))
        for _ in range(10_000):
            system.update(1 / 60)
        assert 0 < system.count <= 80


class TestMotion:
    def test_gravity_accelerates_downwards(self):
        system = ParticleSystem(_config(rate=0, lifetime=(5, 5), gravity=100))
        system.emit_at(0, 0, 1)
        _run(system, 1.0, step=0.01)
        assert 45 < system.positions()[0][1] < 55

    def test_landing_hands_particles_to_child(self):
        child = ParticleSystem(_config(rate=0, lifetime=(5, 5), capacity=20))
        rain = ParticleSystem(_config(rate=0, lifetime=(5, 5), vy=(100, 100), floor_y=20, burst=3), on_floor=child)
        rain.emit_at(0, 0, 2)
        _run(rain, 0.3)
        assert (rain.count, child.count) == (0, 6)

    def test_same_seed_is_deterministic(self):
        a = ParticleSystem(_config(area=(0, 0, 100, 100), vx=(-5, 5)), seed=4)
        b = ParticleSystem(_config(area=(0, 0, 100, 100), vx=(-5, 5)), seed=4)
        _run(a, 1.0)
        _run(b, 1.0)
        assert a.positions() == b.positions()

    def test_prewarm_fills_the_pool(self):
        system = ParticleSystem(_config(rate=20, lifetime=(1, 1)))
        system.prewarm(2.0)
        assert 15 <= system.count <= 21


class TestDrawing:
    def test_particle_is_drawn_scaled_on_the_pixel_grid(self):
        surface = pygame.Surface((40, 40))
        system = ParticleSystem(_config(rate=0, colors=((200, 10, 10),)), scale=2)
        system.emit_at(5, 5, 1)
        system.draw(surface)
        assert surface.get_at((11, 11))[:3] == (200, 10, 10)

    def test_clip_hides_particles_outside(self):
        surface = pygame.Surface((40, 40))
        system = ParticleSystem(_config(rate=0, colors=((200, 10, 10),)), scale=2, clip=(0, 0, 3, 3))
        system.emit_at(5, 5, 1)
        system.draw(surface)
        assert surface.get_at((10, 10))[:3] == (0, 0, 0)

    def test_clip_is_restored_after_drawing(self):
        surface = pygame.Surface((40, 40))
        system = ParticleSystem(_config(rate=0), scale=2, clip=(0, 0, 3, 3))
        system.draw(surface)
        assert surface.get_clip().size == (40, 40)

    def test_trail_draws_behind_the_head(self):
        surface = pygame.Surface((40, 40))
        system = ParticleSystem(_config(rate=0, colors=((255, 255, 255),), trail=2, trail_color=(9, 9, 99),
                                        vy=(10, 10)), scale=1)
        system.emit_at(10, 10, 1)
        system.draw(surface)
        assert surface.get_at((10, 8))[:3] == (9, 9, 99)
