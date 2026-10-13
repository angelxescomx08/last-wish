"""fx/hero_fx.py — timed particles and floor shadows of animated heroes.

Cues fire at their time (blade sparks at ``strike``), never before the first
draw gives them a position; dt is clamped; a 10 000-step stress keeps the
pool bounded.
"""
import pygame
import pytest

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
    @pytest.mark.parametrize("point", [(32, -18), None])
    def test_attack_sparks_originate_at_the_hero_strike_point(self, point):
        from src.presentation.fx.hero_fx import BLADE_HIT
        fx = HeroFx(strike=0, strike_point=point, seed=1)
        fx.draw_shadow(pygame.Surface((1280, 720)), CENTER)
        fx.play("attack")
        fx.update(0)
        offset = point if point is not None else BLADE_HIT
        expected = (CENTER[0] + offset[0], CENTER[1] + offset[1])
        assert fx.particles.positions()[:26] == [expected] * 26

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


class TestArcaneStyle:
    @pytest.mark.parametrize("arcane", [False, True])
    def test_attack_and_cast_use_their_style_palette(self, arcane):
        from src.presentation.fx.hero_fx import ARCANE, VIOLET, WARM, GOLD
        fx = HeroFx(strike=0, arcane=arcane, seed=1)
        fx.draw_shadow(pygame.Surface((1280, 720)), CENTER)
        fx.play("attack")
        fx.update(0)
        assert fx.particles.count > 0
        assert all(palette == (ARCANE if arcane else WARM)
                   for palette in fx.particles._pal[:fx.particles.count])
        fx.particles.clear()
        fx.play("cast")
        _run(fx, 0.31 if arcane else 0.06)
        assert fx.particles.count > 0
        assert all(palette == (VIOLET if arcane else GOLD)
                   for palette in fx.particles._pal[:fx.particles.count])


    @pytest.mark.parametrize("action, cue, before, after", [
        ("cast", "flare", 0.49, 0.02), ("guard", "ward", 0.27, 0.02),
        ("death", "kneel", 0.83, 0.02),
    ])
    def test_arcane_cues_wait_for_the_matching_body_pose(self, action, cue, before, after):
        fx = HeroFx(strike=0.345, arcane=True, seed=1)
        fx.draw_shadow(pygame.Surface((1280, 720)), CENTER)
        fx.play(action)
        _run(fx, before)
        assert cue not in fx._fired
        _run(fx, after)
        assert cue in fx._fired

    def test_cast_flare_uses_its_hand_point_and_metadata_time(self, monkeypatch):
        fx = HeroFx(strike=0.345, arcane=True, cast_point=(24, -20), cast_seconds=0.52)
        fx.draw_shadow(pygame.Surface((1280, 720)), CENTER)
        bursts = []
        monkeypatch.setattr(fx.particles, "burst", lambda x, y, count, **kwargs: bursts.append((x, y)))
        fx.play("cast")
        _run(fx, 0.51)
        assert not bursts
        _run(fx, 0.02)
        assert bursts == [(CENTER[0] + 24, CENTER[1] - 20)]


class TestAuthoredWarriorCues:
    @pytest.mark.parametrize("action, cue, before, after", [
        ("guard", "ward", 0.287, 0.002), ("death", "kneel", 0.839, 0.002),
    ])
    def test_guard_and_kneeling_cues_wait_for_the_authored_pose(self, action, cue, before, after):
        fx = HeroFx(strike=0.333, guard_seconds=0.288, kneel_seconds=0.84)
        fx.draw_shadow(pygame.Surface((1280, 720)), CENTER)
        fx.play(action)
        _run(fx, before)
        assert cue not in fx._fired
        _run(fx, after)
        assert cue in fx._fired
