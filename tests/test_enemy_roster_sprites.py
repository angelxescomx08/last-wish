"""Code-drawn regular enemies: scripts/generate_enemy_<id>.py for the ten new monsters.

Same Espectro art contract as the bosses: actions end on idle frame 0 (the Seta's
terminal ``explode`` ends empty like death), idle loops and moves, the idle figure fits
inside the cell, death ends empty, the hit flash brightens, strike events point at real
frames, every move maps to an animation, random poses render, the sheets on disk match,
and every move id of the enemy's pattern (``enemy_roster``) has a clip.
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


GENS = {name: _load(f"generate_enemy_{name}") for name in
        ("slime", "worm", "eye", "skull", "bat", "bomb", "golem", "acolyte", "imp", "mimic")}
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
        terminal = set(getattr(g, "TERMINAL", ()))
        ends = [_px(g, fn()[-1][0]) for n, (fn, _) in g.ANIMATIONS.items()
                if n not in ("idle", "death") and n not in terminal]
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
                and not meta.get("boss") and (meta["cell_w"], meta["cell_h"]) == (g.CELL_W, g.CELL_H))




class TestRoster:
    def test_every_pattern_move_has_a_clip(self):
        from src.application import enemy_roster as R
        from src.infrastructure.enemy_sprites import ENEMY_SHEET_IDS
        for ai, d in R.ENEMIES.items():
            sid = ENEMY_SHEET_IDS[d.name]
            if sid not in GENS:
                continue
            enemy = R.create_enemy(ai)
            ids = {enemy.intent.move_id}
            for _ in range(8):
                ids.add(R.next_intent(enemy, None, [enemy]).move_id)
            assert ids <= set(GENS[sid].MOVES), (ai, ids - set(GENS[sid].MOVES))

    def test_bomb_explode_ends_empty(self):
        g = GENS["bomb"]
        assert _opaque(g, g.ANIMATIONS["explode"][0]()[-1][0]) == []
