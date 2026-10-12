"""The mage preserves pixel geometry throughout full-body animation."""
import math
from pathlib import Path
import sys

import pygame
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1] / "scripts"))
from mage_rig import ELBOWS, LEG_JOINTS, PALM, SHOULDERS, load_base, magic_origin, pose_at, render_pose, split_layers

ACTIONS = ("idle","attack","guard","hurt","cast","death")


def test_rest_reconstructs_source_pixels_exactly():
    base = load_base()
    frame = render_pose(split_layers(base),pose_at("idle",0))
    assert pygame.image.tobytes(base,"RGBA") == pygame.image.tobytes(frame,"RGBA")
    assert {base.get_at((x,y)).a for y in range(96) for x in range(96)} == {0,255}


def test_actions_have_continuous_recovery_and_idle_loops():
    rest = pose_at("idle",0)
    assert pose_at("idle",1) == rest
    for action in ACTIONS[1:-1]:
        assert pose_at(action,0) == pose_at(action,1) == rest
    assert pose_at("death",1) != rest
    assert pose_at("death",1) == pose_at("death",2)


@pytest.mark.parametrize("action", ACTIONS)
def test_motion_curves_have_no_position_jumps(action):
    previous = pose_at(action,0)
    for i in range(1,501):
        current = pose_at(action,i/500)
        for layer in current:
            for point in ((31,63),(65,50),(51,30),(40,74),(75,25)):
                assert math.dist(previous[layer].point(point),current[layer].point(point)) < 1.7
        previous = current


@pytest.mark.parametrize("action", ACTIONS)
def test_elbows_and_staff_remain_attached(action):
    for i in range(101):
        pose = pose_at(action,i/100)
        assert pose["staff"] == pose["far_forearm"]
        for side in ("near","far"):
            shoulder,elbow = SHOULDERS[side],ELBOWS[side]
            assert pose[f"{side}_arm"].point(shoulder) == pytest.approx(pose["torso"].point(shoulder))
            assert pose[f"{side}_arm"].point(elbow) == pytest.approx(pose[f"{side}_forearm"].point(elbow))


@pytest.mark.parametrize("action", ACTIONS)
@pytest.mark.parametrize("side", ("near","far"))
def test_leg_ik_preserves_lengths_and_attachments(action,side):
    hip,knee,ankle = LEG_JOINTS[side]
    for i in range(101):
        pose = pose_at(action,i/100)
        thigh,shin,foot = (pose[f"{side}_{part}"] for part in ("leg","shin","foot"))
        assert thigh.point(hip) == pytest.approx(pose["torso"].point(hip))
        assert thigh.point(knee) == pytest.approx(shin.point(knee))
        assert shin.point(ankle) == pytest.approx(foot.point(ankle))
        assert math.dist(thigh.point(hip),thigh.point(knee)) == pytest.approx(math.dist(hip,knee))
        assert math.dist(shin.point(knee),shin.point(ankle)) == pytest.approx(math.dist(knee,ankle))


def test_attack_extends_hand_and_steps_towards_enemy():
    poses = [pose_at("attack",i/100) for i in range(101)]
    hands = [magic_origin(p,"attack") for p in poses]
    assert max(x for x,y in hands)-min(x for x,y in hands) > 35
    assert max(math.degrees(p["torso"].angle) for p in poses) > 10
    assert max(p["far_foot"].tx for p in poses) >= 4
    for i in range(101):
        pose = pose_at("idle",i/100)
        for side in ("near","far"):
            assert pose[f"{side}_foot"].point(LEG_JOINTS[side][2]) == LEG_JOINTS[side][2]


def test_cast_hand_traces_a_full_arc_without_moving_the_face_pixels():
    rest,peak = pose_at("cast",0),pose_at("cast",.5)
    assert math.dist(rest["near_forearm"].point(PALM),peak["near_forearm"].point(PALM)) > 35
    layers = split_layers(load_base())
    colors = {tuple(layers["head"].get_at((x,y))) for y in range(96) for x in range(96)}
    head = render_pose({k:v if k == "head" else pygame.Surface((96,96),pygame.SRCALPHA) for k,v in layers.items()},peak,2)
    assert all(tuple(head.get_at((x,y))) in colors for y in range(192) for x in range(192) if head.get_at((x,y)).a)
