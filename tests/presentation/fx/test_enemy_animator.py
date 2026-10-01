"""fx/enemy_animator.py — per-enemy animation player and its particles.

Covers action lifecycle (play, return to idle, queue with delay, unknown
names), death latching, timed particle cues, ambient wisps, dt clamping and a
10 000-step stress run that keeps the particle pool bounded.
"""
import pygame

from src.infrastructure.enemy_sprites import load_enemy_sheet
from src.presentation.fx.enemy_animator import EnemyAnimator

ANCHOR = (640, 400)


def _anim(**kw):
    a = EnemyAnimator(load_enemy_sheet("wraith"), seed=3, **kw)
    a.draw(pygame.Surface((1280, 720)), ANCHOR)       # anchor for particle cues
    return a


def _run(a, seconds, step=1 / 60):
    """Advance in frame-sized steps (update clamps dt to 0.1 s)."""
    t = 0.0
    while t < seconds - 1e-9:
        dt = min(step, seconds - t)
        a.update(dt)
        t += dt


class TestLifecycle:
    def test_starts_idle(self):
        assert _anim().action is None

    def test_play_starts_action(self):
        a = _anim()
        a.play("attack")
        assert a.action == "attack"

    def test_action_returns_to_idle(self):
        a = _anim()
        a.play("hurt")
        _run(a, a.seconds("hurt") + 0.02)
        assert (a.action, a.busy) == (None, False)

    def test_action_still_playing_just_before_end(self):
        a = _anim()
        a.play("cast")
        _run(a, a.seconds("cast") - 0.02)
        assert a.action == "cast"

    def test_idle_cannot_be_played_as_action(self):
        a = _anim()
        a.play("idle")
        assert a.action is None

    def test_unknown_action_is_ignored(self):
        a = _anim()
        a.play("dance")
        assert a.action is None

    def test_delay_queues_action(self):
        a = _anim()
        a.play("attack", delay=0.3)
        assert (a.action, a.busy) == (None, True)

    def test_delayed_action_starts_after_delay(self):
        a = _anim()
        a.play("attack", delay=0.3)
        a.update(0.05)
        for _ in range(6):
            a.update(0.05)
        assert a.action == "attack"

    def test_strike_time_inside_attack(self):
        a = _anim()
        assert 0.0 < a.strike_time() < a.seconds("attack")


class TestDeath:
    def test_death_latches(self):
        a = _anim()
        a.play("death")
        _run(a, a.seconds("death") * 3)
        assert (a.action, a.dead, a.death_done) == ("death", True, True)

    def test_not_done_mid_death(self):
        a = _anim()
        a.play("death")
        a.update(0.2)
        assert (a.death_done, a.busy) == (False, True)

    def test_actions_ignored_after_death(self):
        a = _anim()
        a.play("death")
        a.play("hurt")
        assert a.action == "death"

    def test_death_cancels_queued_actions(self):
        a = _anim()
        a.play("attack", delay=0.1)
        a.play("death")
        for _ in range(int(a.seconds("death") / 0.05) + 5):
            a.update(0.05)
        assert a.action == "death"


class TestParticles:
    def test_hurt_splashes(self):
        a = _anim()
        before = a.particles.count
        a.play("hurt")
        a.update(0.01)
        assert a.particles.count > before + 20

    def test_strike_sparks_at_strike_time(self):
        a = _anim()
        a.play("attack")
        _run(a, a.strike_time() - 0.1)
        early = a.particles.count
        _run(a, 0.08)
        assert a.particles.count > early + 15

    def test_ambient_wisps_appear(self):
        a = _anim()
        for _ in range(20):
            a.update(0.05)
        assert a.particles.count > 0

    def test_no_ambient_after_death(self):
        a = _anim()
        a.play("death")
        for _ in range(200):
            a.update(0.05)
        assert a.particles.count == 0

    def test_no_cues_before_first_draw(self):
        a = EnemyAnimator(load_enemy_sheet("wraith"), seed=1)
        a.play("hurt")
        a.update(0.01)
        assert a.particles.count == 0

    def test_huge_dt_is_clamped(self):
        a = _anim()
        a.play("attack")
        a.update(10 ** 9)
        assert a.action == "attack"

    def test_stress_10000_steps_bounded(self):
        a = _anim()
        names = ("attack", "hurt", "cast")
        for i in range(10_000):
            if i % 40 == 0:
                a.play(names[(i // 40) % 3])
            a.update(1 / 60)
        assert a.particles.count <= a.particles.capacity


class TestDrawing:
    def test_draw_changes_the_surface(self):
        a = _anim()
        surface = pygame.Surface((1280, 720))
        a.draw(surface, ANCHOR)
        assert surface.get_at((ANCHOR[0], ANCHOR[1] - 90)) != (0, 0, 0, 255)

    def test_finished_death_draws_no_sprite(self):
        a = _anim()
        a.play("death")
        for _ in range(400):
            a.update(0.05)
        surface = pygame.Surface((1280, 720))
        a.draw(surface, ANCHOR)
        assert surface.get_at((ANCHOR[0], ANCHOR[1] - 90)) == (0, 0, 0, 255)

    def test_phase_offsets_idle(self):
        a, b = _anim(phase=0.0), _anim(phase=0.5)
        sa, sb = pygame.Surface((1280, 720)), pygame.Surface((1280, 720))
        a.draw(sa, ANCHOR)
        b.draw(sb, ANCHOR)
        assert a.current_frame() is not b.current_frame()
