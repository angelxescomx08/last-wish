"""scripts/generate_enemy_sprites.py — the code-drawn wraith ("Espectro").

Pure standard library: poses are rendered straight from the generator, so these
tests check the art contract (actions end on idle frame 0, idle moves, death
vanishes, everything fits in the cell) without pygame.
"""
import importlib.util
import json
import math
import random
import sys
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("generate_enemy_sprites",
                                               ROOT / "scripts" / "generate_enemy_sprites.py")
gen = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = gen
_spec.loader.exec_module(gen)


def _pixels(pose, t=0.0):
    return tuple(tuple(row) for row in gen.render(pose, t).px)


def _opaque(pose):
    return [(x, y) for y, row in enumerate(gen.render(pose).px) for x, c in enumerate(row)
            if c is not None and c[3] > 0]


class TestAnimations:
    def test_five_animations(self):
        assert set(gen.ANIMATIONS) == {"idle", "attack", "hurt", "cast", "death"}

    def test_only_idle_loops(self):
        assert [n for n, (_, loop) in gen.ANIMATIONS.items() if loop] == ["idle"]

    def test_actions_end_on_idle_frame_zero(self):
        idle0 = _pixels(gen.idle_frames()[0][0])
        assert all(_pixels(gen.ANIMATIONS[a][0]()[-1][0]) == idle0 for a in ("attack", "hurt", "cast"))

    def test_idle_has_motion(self):
        frames = {_pixels(p) for p, _ in gen.idle_frames()}
        assert len(frames) >= gen.IDLE_FRAMES // 2

    def test_idle_loop_closes(self):
        assert _pixels(gen.idle_pose(gen.IDLE_FRAMES)) == _pixels(gen.idle_pose(0))

    def test_actions_are_short(self):
        assert all(0.4 <= sum(ms for _, ms in gen.ANIMATIONS[a][0]()) / 1000 <= 1.6
                   for a in ("attack", "hurt", "cast", "death"))

    def test_every_duration_positive(self):
        assert all(ms > 0 for a in gen.ANIMATIONS for _, ms in gen.ANIMATIONS[a][0]())


class TestPoses:
    def test_render_is_deterministic(self):
        assert _pixels(gen.idle_pose(3)) == _pixels(gen.idle_pose(3))

    def test_idle_figure_fits_inside_the_cell(self):
        pts = _opaque(gen.idle_pose(0))
        xs, ys = [x for x, _ in pts], [y for _, y in pts]
        assert (min(xs) > 0, min(ys) > 0, max(xs) < gen.CELL_W - 1, max(ys) < gen.CELL_H - 1) == (True,) * 4

    def test_idle_figure_is_substantial(self):
        assert len(_opaque(gen.idle_pose(0))) > 2000

    def test_dissolve_zero_is_intact(self):
        base = gen.idle_pose(0)
        assert _pixels(replace(base, dissolve=0.0)) == _pixels(base)

    def test_dissolve_one_is_empty(self):
        assert _opaque(replace(gen.idle_pose(0), dissolve=1.0)) == []

    def test_death_ends_empty(self):
        assert _opaque(gen.death_frames()[-1][0]) == []

    def test_hit_flash_brightens(self):
        def lum(pose):
            px = [c for row in gen.render(pose).px for c in row if c is not None]
            return sum(c[0] + c[1] + c[2] for c in px) / len(px)
        base = gen.idle_pose(0)
        assert lum(replace(base, flash=1.0)) > lum(base) + 100

    def test_attack_lunges_towards_the_hero(self):
        lunge = min(p.dx for p, _ in gen.attack_frames())
        assert lunge <= -10

    def test_stress_random_poses_stay_in_bounds(self):
        rng = random.Random(5)
        for _ in range(100):
            pose = gen.Pose(dx=rng.uniform(-16, 8), dy=rng.uniform(-4, 4), lean=rng.uniform(-10, 6),
                            sx=rng.uniform(0.9, 1.08), sy=rng.uniform(0.94, 1.08),
                            phase=rng.uniform(0, math.tau), claw=rng.random(),
                            eye=rng.uniform(0, 1.8), core=rng.uniform(0, 1.5),
                            flash=rng.random(), dissolve=rng.random(), slash=rng.random(),
                            rune=rng.random())
            cv = gen.render(pose, rng.random())
            assert (len(cv.px), len(cv.px[0])) == (gen.CELL_H, gen.CELL_W)


class TestSheetFiles:
    def test_meta_matches_generator(self):
        meta = json.loads((ROOT / "assets" / "enemies" / "wraith_sheet.json").read_text(encoding="utf-8"))
        assert (meta["cell_w"], meta["cell_h"], meta["anchor"], set(meta["animations"])) == (
            gen.CELL_W, gen.CELL_H, list(gen.ANCHOR), set(gen.ANIMATIONS))

    def test_sheet_png_exists(self):
        assert (ROOT / "assets" / "enemies" / "wraith_sheet.png").stat().st_size > 1000
