"""Code-drawn elites: scripts/generate_elite_<id>.py (Verdugo, Bruja, Gárgola, Minotauro, Escorpión).

Same Espectro art contract as the bosses and regular enemies: every action ends on idle
frame 0, the idle loop closes and moves, the idle figure fits inside the 208×120 cell, death
ends empty, the hit flash brightens, strike events point at real frames (multi-hit clips
have one per hit), every move maps to an animation, random poses render, the sheets on disk
match and are flagged ``boss``/``elite`` (big slot), every move id of the elite's pattern
(``application/elites``) has a clip, and attack clips reach out towards the hero (left).
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


IDS = ("executioner", "hag", "gargoyle", "minotaur", "scorpion")
GENS = {sid: _load(f"generate_elite_{sid}") for sid in IDS}
EXTRA = {"executioner": ("behead", "sharpen"), "hag": ("voodoo", "brew"),
         "gargoyle": ("dive", "petrify"), "minotaur": ("charge", "paw"),
         "scorpion": ("sting", "spray")}
MULTI = {("hag", "voodoo"): 3, ("gargoyle", "dive"): 3, ("scorpion", "attack"): 2}


def _px(gen, pose, t=0.0):
    return tuple(tuple(row) for row in gen.render(pose, t).px)


def _opaque(gen, pose):
    return [(x, y) for y, row in enumerate(gen.render(pose).px) for x, c in enumerate(row)
            if c is not None and c[3] > 0]


@pytest.mark.parametrize("sid", IDS)
class TestContract:
    def test_animations_present(self, sid):
        assert {"idle", "attack", "hurt", "cast", "death", *EXTRA[sid]} <= set(GENS[sid].ANIMATIONS)

    def test_only_idle_loops(self, sid):
        assert [n for n, (_, loop) in GENS[sid].ANIMATIONS.items() if loop] == ["idle"]

    def test_actions_end_on_idle_frame_zero(self, sid):
        g = GENS[sid]
        idle0 = _px(g, g.idle_frames()[0][0])
        assert all(_px(g, fn()[-1][0]) == idle0 for n, (fn, _) in g.ANIMATIONS.items()
                   if n not in ("idle", "death"))

    def test_idle_loop_closes(self, sid):
        g = GENS[sid]
        assert _px(g, g.idle_pose(g.IDLE_FRAMES)) == _px(g, g.idle_pose(0))

    def test_idle_moves(self, sid):
        g = GENS[sid]
        assert len({_px(g, p) for p, _ in g.idle_frames()[::3]}) > 1

    def test_cell_and_anchor(self, sid):
        g = GENS[sid]
        assert (g.CELL_W, g.CELL_H) == (208, 120) and g.ANCHOR == (g.CX, g.GROUND + 2)

    def test_idle_fits_inside_the_cell(self, sid):
        g = GENS[sid]
        pts = _opaque(g, g.idle_frames()[0][0])
        assert min(x for x, _ in pts) > 0 and max(x for x, _ in pts) < g.CELL_W - 1 \
            and min(y for _, y in pts) > 0 and max(y for _, y in pts) < g.CELL_H - 1

    def test_mini_boss_size(self, sid):
        """Taller than a regular enemy's ~75 px or (scorpion) much wider."""
        g = GENS[sid]
        pts = _opaque(g, g.idle_frames()[0][0])
        h = max(y for _, y in pts) - min(y for _, y in pts)
        w = max(x for x, _ in pts) - min(x for x, _ in pts)
        assert h >= 78 or w >= 120

    def test_death_ends_empty(self, sid):
        g = GENS[sid]
        assert _opaque(g, g.death_frames()[-1][0]) == []

    def test_flash_brightens(self, sid):
        g = GENS[sid]
        base = g.idle_frames()[0][0]

        def lum(pose):
            return sum(sum(c[:3]) for row in g.render(pose).px for c in row if c)
        assert lum(replace(base, flash=0.8)) > lum(base)

    def test_strike_events_inside_their_animation(self, sid):
        g = GENS[sid]
        assert "attack" in g.EVENTS
        assert all(0 <= f < len(g.ANIMATIONS[a][0]()) for a, ev in g.EVENTS.items()
                   for f in ev.get("strikes", ()))

    def test_moves_map_to_animations(self, sid):
        g = GENS[sid]
        assert set(g.MOVES.values()) <= set(g.ANIMATIONS) and "vengeance" in g.MOVES

    def test_attack_reaches_left(self, sid):
        g = GENS[sid]
        frames = g.attack_frames()
        strike = g.EVENTS["attack"]["strikes"][0]
        idle_left = min(x for x, _ in _opaque(g, g.idle_frames()[0][0]))
        assert min(x for x, _ in _opaque(g, frames[strike][0])) < idle_left

    def test_random_poses_render(self, sid):
        g = GENS[sid]
        rng = random.Random(4)
        frames = [p for fn, _ in g.ANIMATIONS.values() for p, _ in fn()]
        for _ in range(10):
            pose = rng.choice(frames)
            pose = replace(pose, phase=rng.uniform(-50, 50), dx=pose.dx + rng.uniform(-6, 6))
            g.render(pose, rng.uniform(0, 100))

    def test_sheet_files_match(self, sid):
        g = GENS[sid]
        meta = json.loads((g.OUT_DIR / f"{g.SHEET_ID}_sheet.json").read_text(encoding="utf-8"))
        counts = {n: len(fn()) for n, (fn, _) in g.ANIMATIONS.items()}
        assert {n: a["frames"] for n, a in meta["animations"].items()} == counts
        assert meta.get("boss") is True and meta.get("elite") is True
        assert (meta["cell_w"], meta["cell_h"]) == (g.CELL_W, g.CELL_H)
        assert meta["moves"] == g.MOVES
        assert {k: v["strikes"] for k, v in meta["events"].items()} == \
               {k: v["strikes"] for k, v in g.EVENTS.items()}


@pytest.mark.parametrize("key,hits", list(MULTI.items()))
def test_multi_hit_clips_have_one_strike_per_hit(key, hits):
    sid, anim = key
    assert len(GENS[sid].EVENTS[anim]["strikes"]) == hits


class TestPatterns:
    def test_every_pattern_move_has_a_clip(self):
        from src.application import elites as E
        from src.infrastructure.enemy_sprites import ENEMY_SHEET_IDS
        for ai, d in E.ELITES.items():
            g = GENS[ENEMY_SHEET_IDS[d.name]]
            enemy = E.create_elite(ai)
            ids = {enemy.intent.move_id}
            for _ in range(10):
                ids.add(E.next_intent(enemy, None).move_id)
            enemy.current_hp = 1
            ids.add(E.next_intent(enemy, None).move_id)          # the half-HP move
            assert ids <= set(g.MOVES), (ai, ids - set(g.MOVES))

    def test_multi_hit_moves_use_multi_strike_clips(self):
        from src.application import elites as E
        from src.infrastructure.enemy_sprites import ENEMY_SHEET_IDS
        for ai, d in E.ELITES.items():
            sid = ENEMY_SHEET_IDS[d.name]
            enemy = E.create_elite(ai)
            for _ in range(8):
                it = E.next_intent(enemy, None)
                if it.hits > 1:
                    anim = GENS[sid].MOVES[it.move_id]
                    assert len(GENS[sid].EVENTS[anim]["strikes"]) == it.hits, (ai, it.move_id)
