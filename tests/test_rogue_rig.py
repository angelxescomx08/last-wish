"""Continuity contracts for the rogue's articulated motion."""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from rogue_rig import pose_at


def test_actions_start_and_finish_at_the_same_rest_pose():
    rest = pose_at("idle", 0)
    for action in ("attack", "guard", "hurt", "cast"):
        assert pose_at(action, 0) == rest
        assert pose_at(action, 1) == rest


def test_motion_has_no_discontinuous_joint_jumps():
    points = [(46, 44), (41, 56), (37, 64), (62, 45), (68, 62), (55, 34)]
    for action in ("idle", "attack", "guard", "hurt", "cast", "death"):
        previous = pose_at(action, 0)
        for step in range(1, 501):
            current = pose_at(action, step / 500)
            for name in current:
                for point in points:
                    a, b = previous[name].point(point), current[name].point(point)
                    assert math.dist(a, b) < 2.0, (action, name, step)
            previous = current


def test_daggers_share_the_forearm_transform():
    for action in ("idle", "attack", "guard", "hurt", "cast", "death"):
        for phase in (0, .2, .5, .8, 1):
            pose = pose_at(action, phase)
            assert pose["near_weapon"] == pose["near_forearm"]
            assert pose["far_weapon"] == pose["far_forearm"]


def test_idle_loop_is_periodic():
    assert pose_at("idle", 0) == pose_at("idle", 1)
