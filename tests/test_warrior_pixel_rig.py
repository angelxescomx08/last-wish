"""Geometry contracts for the warrior's complete sword stroke and recovery."""
import math
from pathlib import Path
import sys

import pygame
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1] / "scripts"))
from warrior_pixel_rig import ELBOWS, LEG_JOINTS, SHOULDERS, load_base, pose_at, render_pose, split_layers, weapon_tip

ACTIONS = ("idle","attack","guard","hurt","cast","death")


def test_rest_reconstructs_the_unmodified_pixel_drawing():
    base = load_base()
    assert pygame.image.tobytes(render_pose(split_layers(base),pose_at("idle",0)),"RGBA") == pygame.image.tobytes(base,"RGBA")
    assert {base.get_at((x,y)).a for y in range(96) for x in range(96)} == {0,255}


def test_loop_recovery_and_held_defeat():
    rest = pose_at("idle",0)
    assert pose_at("idle",1) == rest
    for action in ("attack","guard","hurt","cast"):
        assert pose_at(action,0) == pose_at(action,1) == rest
    assert pose_at("death",1) == pose_at("death",10) != rest


@pytest.mark.parametrize("action",ACTIONS)
def test_motion_has_no_discontinuous_joint_jumps(action):
    previous = pose_at(action,0)
    for i in range(1,501):
        current = pose_at(action,i/500)
        for name in current:
            for point in ((80,78),(55,52),(52,42),(45,27),(38,20)):
                assert math.dist(previous[name].point(point),current[name].point(point)) < 1.6, (action,name,i)
        previous = current


@pytest.mark.parametrize("action",ACTIONS)
def test_arms_and_sword_remain_attached_without_stretching(action):
    for i in range(101):
        pose = pose_at(action,i/100)
        assert pose["weapon"] == pose["sword_forearm"]
        for side in ("sword","free"):
            shoulder,elbow = SHOULDERS[side],ELBOWS[side]
            arm,forearm = pose[f"{side}_upper"],pose[f"{side}_forearm"]
            assert arm.point(shoulder) == pytest.approx(pose["torso"].point(shoulder))
            assert arm.point(elbow) == pytest.approx(forearm.point(elbow))
            assert math.dist(arm.point(shoulder),arm.point(elbow)) == pytest.approx(math.dist(shoulder,elbow))


@pytest.mark.parametrize("action",ACTIONS)
@pytest.mark.parametrize("side",("near","far"))
def test_leg_ik_keeps_hips_knees_and_ankles_connected(action,side):
    hip,knee,ankle = LEG_JOINTS[side]
    for i in range(101):
        pose = pose_at(action,i/100)
        thigh,shin,foot = (pose[f"{side}_{part}"] for part in ("leg","shin","foot"))
        assert thigh.point(hip) == pytest.approx(pose["torso"].point(hip))
        assert thigh.point(knee) == pytest.approx(shin.point(knee))
        assert shin.point(ankle) == pytest.approx(foot.point(ankle))
        assert math.dist(thigh.point(hip),thigh.point(knee)) == pytest.approx(math.dist(hip,knee))
        assert math.dist(shin.point(knee),shin.point(ankle)) == pytest.approx(math.dist(knee,ankle))


def test_attack_has_windup_forward_reach_and_low_follow_through():
    poses = [pose_at("attack",i/200) for i in range(201)]
    tips = [weapon_tip(p) for p in poses]
    assert min(y for x,y in tips) < 20
    assert max(y for x,y in tips) > 85
    assert max(x for x,y in tips) > 89
    assert max(x for x,y in tips)-min(x for x,y in tips) > 35
    assert max(p["near_foot"].tx for p in poses) >= 5


def test_idle_soles_are_fixed_at_both_feet():
    for i in range(101):
        pose = pose_at("idle",i/100)
        for side in ("near","far"):
            ankle = LEG_JOINTS[side][2]
            assert pose[f"{side}_foot"].point(ankle) == ankle
