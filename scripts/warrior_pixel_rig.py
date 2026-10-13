"""Full-body warrior v3 animation from the shared coarse pixel-art style.

The earlier warrior source/rig remain archived and untouched. Visible art comes
from one generated drawing; rigid joints and two-bone legs animate its pixels.
"""
from pathlib import Path
import math
import pygame
from warrior_rig import Transform
from rogue_rig import bone_transform, curve
from warrior_pixel_layers import ORDER, split_layers

CELL = 96
ASSETS = Path(__file__).resolve().parents[1] / "assets" / "characters"
LEG_JOINTS = {"near": ((50,58),(55,73),(56,86)), "far": ((42,58),(36,73),(30,86))}
SHOULDERS = {"sword": (52,42), "free": (37,41)}
ELBOWS = {"sword": (55,52), "free": (32,52)}
SWORD_TIP = (80,78)


def prepare_base():
    """Import actual pixel clusters with nearest sampling and binary alpha."""
    source = pygame.image.load(str(ASSETS / "warrior-source-v3.png"))
    art = source.subsurface(source.get_bounding_rect(min_alpha=128))
    size = (round(art.get_width()*78/art.get_height()),78)
    base = pygame.Surface((CELL,CELL),pygame.SRCALPHA)
    base.blit(pygame.transform.scale(art,size),(8,14))
    for y in range(CELL):
        for x in range(CELL):
            color = base.get_at((x,y))
            base.set_at((x,y), (*color[:3],255) if color.a >= 128 else (0,0,0,0))
    pygame.image.save(base,str(ASSETS / "warrior-v3-base.png"))
    return base


def load_base():
    return pygame.image.load(str(ASSETS / "warrior-v3-base.png"))


def leg_pose(side, target_hip, foot_shift):
    hip,knee,ankle = LEG_JOINTS[side]
    if target_hip == hip and foot_shift == (0,0):
        return Transform(),Transform(),Transform()
    target_ankle = (ankle[0]+foot_shift[0],ankle[1]+foot_shift[1])
    l1,l2 = math.dist(hip,knee),math.dist(knee,ankle)
    vx,vy = target_ankle[0]-target_hip[0],target_ankle[1]-target_hip[1]
    distance = math.hypot(vx,vy)
    if not abs(l1-l2) < distance <= l1+l2+1e-7:
        raise ValueError(f"Unreachable warrior {side} leg: {distance:.3f}")
    along = (l1*l1-l2*l2+distance*distance)/(2*distance)
    height = math.sqrt(max(0,l1*l1-along*along))
    cross = (ankle[0]-hip[0])*(knee[1]-hip[1])-(ankle[1]-hip[1])*(knee[0]-hip[0])
    sign = 1 if cross >= 0 else -1
    target_knee = (target_hip[0]+vx/distance*along-vy/distance*height*sign,
                   target_hip[1]+vy/distance*along+vx/distance*height*sign)
    return (bone_transform(hip,knee,target_hip,target_knee),
            bone_transform(knee,ankle,target_knee,target_ankle),
            Transform(tx=foot_shift[0],ty=foot_shift[1]))


def envelope(p, peak=.4):
    return curve(p,((0,0),(peak,1),(1,0)))


def pose_at(action, phase):
    p = max(0,min(1,phase))
    if action == "idle":
        p %= 1
    if p == 0 or (p == 1 and action != "death"):
        return {name:Transform() for name in ORDER}
    dx=dy=body=head=sword_upper=sword_elbow=free_upper=free_elbow=hair=cape=cloth=step=lift=0.
    if action == "idle":
        breath = (1-math.cos(math.tau*p))/2
        body,head,dy = -.75*breath,.9*breath,.35*breath
        sword_upper,sword_elbow = -1.8*breath,2.8*breath
        free_upper,free_elbow = -2*breath,2.5*breath
        hair = 2.8*math.sin(math.tau*p)
        cape = -2.5*math.sin(math.tau*p)
        cloth = 1.2*math.sin(math.tau*p)
    elif action == "attack":
        # Fold the elbow to bring the blade overhead, cut forward, then follow
        # through below the hand. The hand and blade never separate or stretch.
        dx = curve(p,((0,0),(.22,-4),(.43,-3.5),(.59,-2),(.8,-1),(1,0)))
        dy = curve(p,((0,0),(.22,2),(.43,3),(.59,2),(.8,1),(1,0)))
        body = curve(p,((0,0),(.22,-8),(.43,10),(.59,14),(.8,4),(1,0)))
        sword_upper = curve(p,((0,0),(.22,-20),(.43,-20),(.59,10),(.8,0),(1,0)))
        sword_elbow = curve(p,((0,0),(.22,-120),(.43,-45),(.59,0),(.8,-25),(1,0)))
        free_upper = curve(p,((0,0),(.22,-20),(.43,15),(.59,20),(1,0)))
        free_elbow = -18*envelope(p,.43)
        step = curve(p,((0,0),(.22,0),(.4,5),(.65,5),(1,0)))
        lift = curve(p,((0,0),(.22,0),(.3,-2),(.4,0),(.65,0),(.8,-2),(1,0)))
        hair = curve(p,((0,0),(.27,5),(.49,-8),(.67,-4),(.86,2),(1,0)))
        cape = curve(p,((0,0),(.27,3),(.5,-7),(.68,-3),(.86,2),(1,0)))
        cloth = -cape*.5
        head = -body*.65
    elif action == "guard":
        e = envelope(p,.4)
        dx,dy,body,head = -1.5*e,6*e,-7*e,6*e
        sword_upper,sword_elbow = -12*e,-100*e
        free_upper,free_elbow = -65*e,-15*e
        hair,cape,cloth = 5*envelope(p,.5),4*envelope(p,.53),-2*e
    elif action == "hurt":
        e = envelope(p,.22)
        dx,dy,body,head = -2*e,4*e,-13*e,-5*e
        sword_upper,sword_elbow = 10*e,-30*e
        free_upper,free_elbow = 15*e,-15*e
        hair,cape,cloth = 8*envelope(p,.32),5*envelope(p,.35),3*e
    elif action == "cast":
        e = envelope(p,.5)
        dy,body,head = 2*e,-4*e,6*e
        sword_upper = -22*e
        sword_elbow = -117*e
        free_upper,free_elbow = -65*e,-35*e
        hair,cape,cloth = -5*envelope(p,.6),-4*envelope(p,.62),2*e
    elif action == "death":
        e = curve(p,((0,0),(.22,.25),(.6,1),(1,1)))
        dx,dy,body,head = -2*e,9*e,18*e,15*e
        sword_upper,sword_elbow = 0,-15*e
        free_upper,free_elbow = -12*e,-15*e
        hair,cape,cloth = -6*e,-4*e,3*e
    else:
        raise ValueError(f"Unknown warrior animation: {action}")
    torso = Transform(tx=dx,ty=dy).joint((46,58),body)
    face = torso.joint((45,38),head)
    sword_arm = torso.joint(SHOULDERS["sword"],sword_upper)
    sword_forearm = sword_arm.joint(ELBOWS["sword"],sword_elbow)
    free_arm = torso.joint(SHOULDERS["free"],free_upper)
    pose = {
        "torso":torso,"head":face,"hair":face.joint((38,20),hair),
        "cape":torso.joint((35,41),cape),
        "sword_upper":sword_arm,"sword_forearm":sword_forearm,"weapon":sword_forearm,
        "free_upper":free_arm,"free_forearm":free_arm.joint(ELBOWS["free"],free_elbow),
        "front_cloth":torso.joint((46,57),cloth),
        "back_cloth":torso.joint((42,57),-cloth*.7),
    }
    for side,foot_shift in (("far",(0,0)),("near",(step,lift))):
        transforms = leg_pose(side,torso.point(LEG_JOINTS[side][0]),foot_shift)
        for name,t in zip(("leg","shin","foot"),transforms):
            pose[f"{side}_{name}"] = t
    return pose


def weapon_tip(pose):
    return pose["weapon"].point(SWORD_TIP)


_PIXEL_CACHE = {}


def render_pose(layers, pose, scale=1):
    """Rasterize rigid source pixels directly at 96/192 px without blur."""
    size = CELL*scale
    canvas = pygame.Surface((size,size),pygame.SRCALPHA)
    for name in ORDER:
        layer,t = layers[name],pose[name]
        bounds = layer.get_bounding_rect()
        if not bounds.width:
            continue
        key = id(layer)
        if key not in _PIXEL_CACHE:
            _PIXEL_CACHE[key] = (layer,[[tuple(layer.get_at((x,y))) for x in range(CELL)] for y in range(CELL)])
        pixels = _PIXEL_CACHE[key][1]
        c,s = math.cos(t.angle),math.sin(t.angle)
        corners = [t.point(point) for point in (bounds.topleft,bounds.topright,bounds.bottomleft,bounds.bottomright)]
        left = max(0,math.floor(min(p[0] for p in corners)*scale)-scale)
        right = min(size,math.ceil(max(p[0] for p in corners)*scale)+scale)
        top = max(0,math.floor(min(p[1] for p in corners)*scale)-scale)
        bottom = min(size,math.ceil(max(p[1] for p in corners)*scale)+scale)
        offset = .5-.5/scale
        for y in range(top,bottom):
            py = y/scale-offset-t.ty
            for x in range(left,right):
                px = x/scale-offset-t.tx
                sx,sy = round(c*px+s*py),round(-s*px+c*py)
                if 0 <= sx < CELL and 0 <= sy < CELL and pixels[sy][sx][3]:
                    canvas.set_at((x,y),pixels[sy][sx])
    return canvas

