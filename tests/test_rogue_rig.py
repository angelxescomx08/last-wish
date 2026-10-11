"""Continuity contracts for the rogue's articulated motion."""
import math
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from rogue_rig import LEG_JOINTS, pose_at


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


def test_attack_uses_a_full_dagger_swing_and_body_turn():
    poses = [pose_at("attack", step / 100) for step in range(101)]
    tips = [pose["near_forearm"].point((28, 78)) for pose in poses]
    largest_tip_span = max(math.dist(a, b) for a in tips for b in tips)
    torso_angles = [math.degrees(pose["torso"].angle) for pose in poses]

    assert largest_tip_span > 40
    assert max(torso_angles) - min(torso_angles) > 12


def test_attack_steps_the_front_foot_towards_the_target():
    ankle = (66, 89)
    foot_positions = [
        pose_at("attack", step / 100)["far_foot"].point(ankle)
        for step in range(101)
    ]

    assert max(x for x, _ in foot_positions) - ankle[0] >= 5


def test_idle_feet_stay_fixed_through_breathing():
    for step in range(101):
        pose = pose_at("idle", step / 100)
        for name in ("near_foot", "far_foot"):
            foot = pose[name]
            assert foot.angle == pytest.approx(0, abs=1e-10)
            assert foot.tx == pytest.approx(0, abs=1e-10)
            assert foot.ty == pytest.approx(0, abs=1e-10)


def test_full_arm_motion_keeps_the_elbow_connected_and_upper_arm_rigid():
    shoulder, elbow = (47, 45), (41, 56)
    upper_arm_length = math.dist(shoulder, elbow)
    for action in ("attack", "guard", "hurt", "cast"):
        for step in range(101):
            pose = pose_at(action, step / 100)
            shoulder_position = pose["near_arm"].point(shoulder)
            elbow_position = pose["near_arm"].point(elbow)

            assert shoulder_position == pytest.approx(pose["torso"].point(shoulder))
            assert elbow_position == pytest.approx(pose["near_forearm"].point(elbow))
            assert math.dist(shoulder_position, elbow_position) == pytest.approx(
                upper_arm_length
            )


@pytest.mark.parametrize("action", ("idle", "attack", "guard", "hurt", "cast", "death"))
@pytest.mark.parametrize("side", ("near", "far"))
def test_leg_joints_remain_connected_without_stretching(action, side):
    hip, knee, ankle = LEG_JOINTS[side]
    thigh_length, shin_length = math.dist(hip, knee), math.dist(knee, ankle)
    for step in range(101):
        pose = pose_at(action, step / 100)
        thigh, shin, foot = (pose[f"{side}_{part}"] for part in ("leg", "shin", "foot"))
        hip_position = thigh.point(hip)
        knee_position = thigh.point(knee)
        ankle_position = shin.point(ankle)

        assert knee_position == pytest.approx(shin.point(knee), abs=1e-9)
        assert ankle_position == pytest.approx(foot.point(ankle), abs=1e-9)
        assert math.dist(hip_position, knee_position) == pytest.approx(thigh_length)
        assert math.dist(shin.point(knee), ankle_position) == pytest.approx(shin_length)
