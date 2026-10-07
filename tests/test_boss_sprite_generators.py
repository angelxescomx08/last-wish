"""Code-drawn floor-1 bosses: scripts/generate_boss_{mycelid,weaver,knight}.py + pixel_kit.

Stdlib renderers checked against the Espectro art contract: actions end on idle
frame 0, idle loops and moves, the idle figure fits inside the cell, death ends
empty, the hit flash brightens, strike events point at real frames, every boss
move maps to an animation, random poses render, and the sheets on disk match.
Plus the shared kit (smooth tubes without gaps, dissolve, PNG round trip).
"""
import importlib.util
import json
import random
import sys
from dataclasses import replace
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))


def _load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


GENS = {name: _load(f"generate_boss_{name}") for name in ("mycelid", "weaver", "knight")}
kit = _load("pixel_kit")
IDS = list(GENS)


def _px(gen, pose, t=0.0):
    return tuple(tuple(row) for row in gen.render(pose, t).px)


def _opaque(gen, pose):
    return [(x, y) for y, row in enumerate(gen.render(pose).px) for x, c in enumerate(row)
            if c is not None and c[3] > 0]


@pytest.mark.parametrize("bid", IDS)
class TestContract:
    def test_core_animations_present(self, bid):
        assert {"idle", "attack", "hurt", "cast", "death"} <= set(GENS[bid].ANIMATIONS)

    def test_only_idle_loops(self, bid):
        assert [n for n, (_, loop) in GENS[bid].ANIMATIONS.items() if loop] == ["idle"]

    def test_actions_end_on_idle_frame_zero(self, bid):
        g = GENS[bid]
        idle0 = _px(g, g.idle_frames()[0][0])
        ends = [_px(g, fn()[-1][0]) for n, (fn, _) in g.ANIMATIONS.items() if n not in ("idle", "death")]
        assert all(e == idle0 for e in ends)

    def test_idle_loop_closes(self, bid):
        g = GENS[bid]
        assert _px(g, g.idle_pose(g.IDLE_FRAMES)) == _px(g, g.idle_pose(0))

    def test_idle_moves(self, bid):
        g = GENS[bid]
        frames = {_px(g, p) for p, _ in g.idle_frames()[::3]}
        assert len(frames) > 1

    def test_idle_fits_inside_the_cell(self, bid):
        g = GENS[bid]
        pts = _opaque(g, g.idle_frames()[0][0])
        assert min(x for x, _ in pts) > 0 and max(x for x, _ in pts) < g.CELL_W - 1 \
            and min(y for _, y in pts) > 0 and max(y for _, y in pts) < g.CELL_H - 1

    def test_death_ends_empty(self, bid):
        g = GENS[bid]
        assert _opaque(g, g.death_frames()[-1][0]) == []

    def test_flash_brightens(self, bid):
        g = GENS[bid]
        base = g.idle_frames()[0][0]

        def lum(pose):
            return sum(sum(c[:3]) for row in g.render(pose).px for c in row if c)
        assert lum(replace(base, flash=0.8)) > lum(base)

    def test_strike_events_inside_their_animation(self, bid):
        g = GENS[bid]
        assert all(0 <= f < len(g.ANIMATIONS[a][0]()) for a, ev in g.EVENTS.items()
                   for f in ev.get("strikes", ()))

    def test_moves_map_to_animations(self, bid):
        g = GENS[bid]
        assert set(g.MOVES.values()) <= set(g.ANIMATIONS)

    def test_random_poses_render(self, bid):
        g = GENS[bid]
        rng = random.Random(4)
        frames = [p for fn, _ in g.ANIMATIONS.values() for p, _ in fn()]
        for _ in range(12):
            pose = rng.choice(frames)
            pose = replace(pose, phase=rng.uniform(-50, 50), dx=pose.dx + rng.uniform(-6, 6))
            g.render(pose, rng.uniform(0, 100))

    def test_sheet_files_match(self, bid):
        g = GENS[bid]
        meta = json.loads((g.OUT_DIR / f"{g.SHEET_ID}_sheet.json").read_text(encoding="utf-8"))
        counts = {n: len(fn()) for n, (fn, _) in g.ANIMATIONS.items()}
        assert ({n: a["frames"] for n, a in meta["animations"].items()} == counts
                and meta["boss"] and (meta["cell_w"], meta["cell_h"]) == (g.CELL_W, g.CELL_H))


class TestBossMoves:
    def test_every_boss_move_has_an_animation(self):
        from src.application import enemy_ai
        mapping = {enemy_ai.MYCELID: "mycelid", enemy_ai.WEAVER: "weaver",
                   enemy_ai.HOLLOW_KNIGHT: "knight"}
        for ai, bid in mapping.items():
            boss = enemy_ai.create_boss(ai)
            seen = {boss.intent.move_id} | {enemy_ai.next_intent(boss, None).move_id for _ in range(12)}
            boss.current_hp = 1
            seen.add(enemy_ai.next_intent(boss, None).move_id)
            assert seen <= set(GENS[bid].MOVES), (ai, seen - set(GENS[bid].MOVES))


class TestKnightBlade:
    def test_blade_strip_size(self):
        g = GENS["knight"]
        rows = g.build_blade_strip()
        assert (len(rows[0]), len(rows)) == (g.BLADE_W * g.BLADE_ROTATIONS, g.BLADE_W)

    def test_every_rotation_drawn(self):
        g = GENS["knight"]
        assert all(kit.opaque_count(g.render_blade(k / 16 * 6.283)) > 20 for k in range(16))


class TestKit:
    def test_stroke_has_no_gaps(self):
        cv = kit.Canvas(60, 20)
        kit.stroke(cv, [(5, 10), (55, 10)], lambda t: 1.0, [(10, 10, 10), (200, 200, 200)])
        assert all(cv.get(x, 10) is not None for x in range(6, 55))

    def test_stroke_zero_radius_still_one_pixel(self):
        cv = kit.Canvas(20, 20)
        kit.stroke(cv, [(5, 5), (15, 5)], lambda t: 0.0, [(10, 10, 10)])
        assert kit.opaque_count(cv) > 0

    def test_dissolve_full_clears(self):
        cv = kit.Canvas(10, 10)
        for y in range(10):
            for x in range(10):
                cv.put(x, y, (100, 100, 100))
        kit.dissolve(cv, 1.0, 0, 10, (255, 255, 255), (200, 200, 200))
        assert kit.opaque_count(cv) == 0

    def test_dissolve_zero_keeps(self):
        cv = kit.Canvas(5, 5)
        cv.put(2, 2, (1, 2, 3))
        kit.dissolve(cv, 0.0, 0, 5, (255, 255, 255), (200, 200, 200))
        assert kit.opaque_count(cv) == 1

    def test_put_outside_is_ignored(self):
        cv = kit.Canvas(4, 4)
        cv.put(10 ** 9, -10 ** 9, (1, 1, 1))
        assert kit.opaque_count(cv) == 0

    def test_png_round_trip(self, tmp_path):
        import pygame
        kit.write_png(tmp_path / "a.png", [[(1, 2, 3, 255), None], [None, (9, 8, 7, 128)]])
        img = pygame.image.load(str(tmp_path / "a.png"))
        assert (img.get_size(), tuple(img.get_at((0, 0)))) == ((2, 2), (1, 2, 3, 255))
