"""scripts/generate_warrior_code_sprites.py — the code-drawn red-haired warrior.

Pure standard library: poses are rendered straight from the generator. Pins
the art contract (idle loop closes and moves, boots planted, actions end on
idle frame 0, death holds a kneel, the figure is ONE connected mass like the
Espectro — no jointed pieces) and the sheet files the game loads.
"""
import importlib.util
import json
import math
import random
import sys
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("generate_warrior_code_sprites",
                                               ROOT / "scripts" / "generate_warrior_code_sprites.py")
gen = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = gen
_spec.loader.exec_module(gen)


def _px(pose):
    return tuple(tuple(row) for row in gen.render(pose).px)


def _bounds(pose):
    px = gen.render(pose).px
    pts = [(x, y) for y, row in enumerate(px) for x, c in enumerate(row) if c is not None and c[3] >= 32]
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    return min(xs), max(xs), min(ys), max(ys)


class TestAnimations:
    def test_six_animations(self):
        assert list(gen.ANIMATIONS) == ["idle", "attack", "guard", "hurt", "cast", "death"]

    def test_idle_is_the_shared_1_6_second_cycle(self):
        assert sum(ms for _, ms in gen.idle_frames()) == 1600

    def test_actions_end_on_idle_frame_zero(self):
        idle0 = _px(gen.idle_pose(0))
        assert all(_px(gen.ANIMATIONS[a][0]()[-1][0]) == idle0 for a in ("attack", "guard", "hurt", "cast"))

    def test_actions_are_short(self):
        assert all(0.3 <= sum(ms for _, ms in gen.ANIMATIONS[a][0]()) / 1000 <= 0.8
                   for a in ("attack", "guard", "hurt", "cast"))

    def test_death_is_longer_and_held(self):
        frames = gen.death_frames()
        assert (sum(ms for _, ms in frames) > 1000, frames[-1][0].eye) == (True, "closed")

    def test_strike_frame_is_the_contact(self):
        pose = gen.attack_frames()[gen.STRIKE_FRAME][0]
        assert (pose.slash, pose.sword > 0) == (1.0, True)


class TestIdle:
    def test_idle_has_motion(self):
        assert len({_px(p) for p, _ in gen.idle_frames()}) == gen.IDLE_FRAMES

    def test_idle_loop_closes(self):
        assert _px(gen.idle_pose(gen.IDLE_FRAMES)) == _px(gen.idle_pose(0))

    def test_boots_stay_planted(self):
        rows = {tuple(tuple(r) for r in gen.render(p).px[84:]) for p, _ in gen.idle_frames()}
        assert len(rows) == 1

    def test_soles_on_the_ground_row(self):
        assert {_bounds(p)[3] for p, _ in gen.idle_frames()} == {gen.GROUND}

    def test_tall_enough_for_the_combat_sheet(self):
        x0, x1, y0, y1 = _bounds(gen.idle_pose(0))
        assert (y1 - y0 + 1) * 2 > 140

    def test_one_blink(self):
        assert [p.eye for p, _ in gen.idle_frames()].count("closed") == 1


class TestPoses:
    def test_attack_reaches_past_idle(self):
        idle_right = _bounds(gen.idle_pose(0))[1]
        assert max(_bounds(p)[1] for p, _ in gen.attack_frames()) >= idle_right + 8

    def test_hurt_flashes(self):
        assert gen.hurt_frames()[0][0].flash > 0.5

    def test_limbs_are_one_continuous_sweep(self):
        part = {}
        pts = gen.bezier((10.0, 10.0), (40.0, 5.0), (60.0, 50.0), 14)
        gen.sweep(part, pts, lambda t: (2.5, 2.5), lambda t, u, x, y, nx, ny: (1, 2, 3))
        seen, todo = set(), [next(iter(part))]
        while todo:
            q = todo.pop()
            if q in seen or q not in part:
                continue
            seen.add(q)
            todo += [(q[0] + dx, q[1] + dy) for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))]
        assert len(seen) == len(part)

    def test_sweep_of_zero_width_draws_nothing(self):
        part = {}
        gen.sweep(part, [(10.0, 10.0), (30.0, 30.0)], lambda t: (0.0, 0.0), lambda *a: (1, 2, 3))
        assert part == {}

    def test_sweep_far_outside_the_cell_is_safe(self):
        part = {}
        gen.sweep(part, [(10.0 ** 9, 10.0 ** 9), (10.0 ** 9 + 5, 10.0 ** 9)], lambda t: (2.0, 2.0),
                  lambda *a: (1, 2, 3))
        assert part == {}

    def test_one_mass_without_seams(self):
        """The body is one silhouette: its opaque pixels form a single connected region."""
        px = gen.render(gen.idle_pose(0)).px
        part = {(x, y) for y, row in enumerate(px) for x, c in enumerate(row) if c is not None and c[3] == 255}
        seen, todo = set(), [next(iter(part))]
        while todo:
            q = todo.pop()
            if q in seen or q not in part:
                continue
            seen.add(q)
            todo += [(q[0] + dx, q[1] + dy) for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))]
        assert len(seen) == len(part)

    def test_kneeling_hides_the_boots(self):
        px = gen.render(gen.death_frames()[-1][0]).px
        leather = sum(1 for row in px[86:] for c in row if c is not None and c[:3] in gen.LEATHER)
        assert leather == 0

    def test_through_passes_the_midpoint(self):
        a, mid, b = (0.0, 0.0), (5.0, 9.0), (10.0, 0.0)
        pts = gen.bezier(a, gen.through(a, mid, b), b, 2)
        assert pts[1] == mid

    def test_red_hair_dominates_the_head(self):
        px = gen.render(gen.idle_pose(0)).px
        reds = sum(1 for row in px[18:36] for c in row if c and c[0] > c[1] + 60 and c[0] > c[2] + 60)
        assert reds > 60

    def test_stress_random_poses(self):
        rng = random.Random(7)
        base = gen.idle_pose(0)
        for _ in range(100):
            pose = replace(base, dx=rng.uniform(-6, 9), dy=rng.uniform(-3, 4), lean=rng.uniform(-6, 8),
                           sx=rng.uniform(0.9, 1.08), sy=rng.uniform(0.92, 1.05), nod=rng.uniform(0, 3),
                           kneel=rng.random(), ff=rng.uniform(52, 68), bf=rng.uniform(32, 42),
                           fh=(rng.uniform(30, 75), rng.uniform(25, 75)), sword=rng.uniform(-math.pi, math.pi),
                           phase=rng.uniform(0, 7), hair_wind=rng.uniform(-1, 1), cape_wind=rng.uniform(-1, 1),
                           flash=rng.random(), slash=rng.random(), ward=rng.random(), glow=rng.random())
            cv = gen.render(pose)
            assert (len(cv.px), len(cv.px[0])) == (gen.CELL, gen.CELL)


class TestSheetFiles:
    def test_meta_matches_generator(self):
        meta = json.loads((ROOT / "assets" / "characters" / "warrior_sheet.json").read_text(encoding="utf-8"))
        assert (meta["cell"], meta["sheets"], meta["events"]["attack"]["strike_frame"], list(meta["animations"])) == (
            192, {"192": "warrior_sheet.png", "96": "warrior_sheet_96.png"}, gen.STRIKE_FRAME, list(gen.ANIMATIONS))

    def test_legacy_illustrated_sheet_is_kept(self):
        assert (ROOT / "assets" / "characters" / "warrior_illustrated" / "warrior_sheet.png").exists()
