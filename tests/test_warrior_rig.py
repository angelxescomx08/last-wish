"""Rigid attachments and stationary ground anchors in the offline warrior rig."""
import math
import pytest
from scripts.warrior_rig import build_pose


def test_forearm_elbow_stays_attached_to_upper_arm():
    for index in range(97):
        pose = build_pose(index / 96)
        assert pose['forearm'].point((109,96)) == pytest.approx(pose['upper_arm'].point((109,96)))


def test_weapon_is_rigid_and_attached_to_hand():
    for index in range(97):
        pose = build_pose(index / 96)
        assert pose['weapon'] == pose['forearm']
        grip, tip = (pose['weapon'].point(p) for p in ((112,132),(176,186)))
        assert math.dist(grip,tip) == pytest.approx(math.dist((112,132),(176,186)))


def test_all_bones_close_the_loop_with_continuous_velocity():
    epsilon = 0.00001
    for name, start in build_pose(0).items():
        assert start.point((128,80)) == pytest.approx(build_pose(1)[name].point((128,80)))
        before = build_pose(1-epsilon)[name].point((128,80))
        after = build_pose(epsilon)[name].point((128,80))
        center = start.point((128,80))
        assert [(c-b)/epsilon for c,b in zip(center,before)] == pytest.approx(
            [(a-c)/epsilon for a,c in zip(after,center)], abs=0.02)
