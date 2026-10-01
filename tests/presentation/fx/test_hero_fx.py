"""fx/hero_fx.py — timed particles and floor shadow of the code-drawn hero.

Cues fire at their time (blade sparks at ``strike``), never before the first
draw gives them a position; dt is clamped; a 10 000-step stress keeps the
pool bounded.
"""
import pygame

from src.presentation.fx.hero_fx import DEATH_KNEEL, HeroFx

CENTER = (272, 187)


def _fx(strike=0.24):
    fx = HeroFx(strike=strike, seed=1)
    fx.draw_shadow(pygame.Surface((1280, 720)), CENTER)
    return fx


def _run(fx, seconds, step=1 / 60):
    t = 0.0
    while t < seconds - 1e-9:
        dt = min(step, seconds - t)
        fx.update(dt)
        t += dt


class TestCues:
    def test_attack_sparks_wait_for_the_strike(self):
        fx = _fx()
        fx.play("attack")
        _run(fx, 0.2)
        before = fx.particles.count
        _run(fx, 0.06)
        assert fx.particles.count > before + 20

    def test_guard_bursts(self):
        fx = _fx()
        fx.play("guard")
        _run(fx, 0.1)
        assert fx.particles.count >= 15

    def test_hurt_bursts_at_once(self):
        fx = _fx()
        fx.play("hurt")
        fx.update(0.01)
        assert fx.particles.count >= 20

    def test_cast_rises(self):
        fx = _fx()
        fx.play("cast")
        _run(fx, 0.4)
        assert fx.particles.count > 20

    def test_death_dust_when_kneeling(self):
        fx = _fx()
        fx.play("death")
        _run(fx, DEATH_KNEEL - 0.02)
        before = fx.particles.count
        _run(fx, 0.05)
        assert fx.particles.count > before + 15

    def test_unknown_action_ignored(self):
        fx = _fx()
        fx.play("dance")
        assert fx.action is None

    def test_delay_queues(self):
        fx = _fx()
        fx.play("hurt", delay=0.2)
        fx.update(0.05)
        assert (fx.action, fx.particles.count) == (None, 0)

    def test_no_cues_before_first_draw(self):
        fx = HeroFx(strike=0.24, seed=2)
        fx.play("hurt")
        fx.update(0.01)
        assert fx.particles.count == 0

    def test_huge_dt_clamped(self):
        fx = _fx()
        fx.play("attack")
        fx.update(10 ** 9)
        assert fx.action == "attack"

    def test_zero_strike_fires_immediately(self):
        fx = _fx(strike=0.0)
        fx.play("attack")
        fx.update(0.001)
        assert fx.particles.count > 20

    def test_stress_10000_steps_bounded(self):
        fx = _fx()
        names = ("attack", "guard", "hurt", "cast")
        for i in range(10_000):
            if i % 30 == 0:
                fx.play(names[(i // 30) % 4])
            fx.update(1 / 60)
        assert fx.particles.count <= fx.particles.capacity


class TestDrawing:
    def test_shadow_darkens_under_the_feet(self):
        surface = pygame.Surface((1280, 720))
        surface.fill((100, 100, 100))
        HeroFx(strike=0.24).draw_shadow(surface, CENTER)
        assert surface.get_at((CENTER[0], CENTER[1] + 94))[0] < 100

    def test_draw_particles_does_not_fail(self):
        fx = _fx()
        fx.play("hurt")
        fx.update(0.02)
        surface = pygame.Surface((1280, 720))
        fx.draw(surface, CENTER)
        assert surface.get_size() == (1280, 720)
