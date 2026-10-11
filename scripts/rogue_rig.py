"""Rigid cutout rig of the approved rogue, with continuous authored joint curves.

No generated pose switching, global image warp, optical flow or frame blending.
Coordinates are on the approved 96 px rest drawing.
"""
import math
import pygame
from warrior_rig import Transform

ORDER = ("hair", "cape", "far_leg", "far_shin", "far_foot", "near_leg", "near_shin", "near_foot", "torso", "far_arm", "far_forearm", "head", "near_arm", "near_forearm", "near_weapon", "far_weapon")
REGIONS = {
    "head": [(43,14),(71,14),(70,44),(62,45),(55,42),(47,41),(42,34)],
    "near_forearm": [(36,54),(46,54),(47,63),(42,68),(37,76),(31,83),(25,83),(26,73),(31,66)],
    "near_arm": [(43,42),(50,44),(48,51),(45,58),(36,57),(40,48)],
    "far_forearm": [(65,55),(71,55),(75,62),(88,73),(87,82),(72,75),(65,65)],
    "far_arm": [(61,44),(66,45),(68,52),(71,57),(65,61),(61,54)],
    "hair": [(15,12),(49,12),(48,19),(44,25),(43,34),(38,41),(30,47),(16,46)],
    "cape": [(17,40),(42,36),(49,41),(45,48),(42,59),(33,70),(21,69),(16,58)],
    "near_leg": [(47,62),(56,64),(56,70),(48,82),(45,89),(47,94),(31,94),(34,85),(36,78),(41,69)],
    "far_leg": [(55,62),(65,62),(68,75),(68,84),(77,91),(77,94),(60,94),(59,80),(55,71)],
}


def separate_layers(base):
    layers = {name: pygame.Surface((96,96), pygame.SRCALPHA) for name in ORDER}
    masks = {}
    for name, points in REGIONS.items():
        mask = pygame.Surface((96,96), pygame.SRCALPHA)
        pygame.draw.polygon(mask, "white", points)
        masks[name] = mask
    for y in range(96):
        for x in range(96):
            color = base.get_at((x,y))
            if not color.a:
                continue
            name = next((name for name,mask in masks.items() if mask.get_at((x,y)).a), ("near_leg" if x < 55 else "far_leg") if y >= 64 else "torso")
            # Keep cape fringes and blade tips out of the leg masks.
            if name in ("near_leg","far_leg") and y < 84:
                if x >= 70 and y < 80:
                    name = "far_forearm"
                elif x <= 35:
                    name = "cape" if y < 73 else "near_forearm"
            layers[name].set_at((x,y), color)
    # Small duplicated joint caps stay under the moving pieces. All pixels come
    # from the approved source; face and costume are never repainted.
    for name, center, radius in (("torso", (47,45),3), ("torso", (63,46),3),
                                  ("near_arm", (41,56),3), ("far_arm", (67,57),3),
                                  ("torso", (53,63),4)):
        for y in range(center[1]-radius,center[1]+radius+1):
            for x in range(center[0]-radius,center[0]+radius+1):
                if math.dist((x,y),center) <= radius:
                    layers[name].set_at((x,y),base.get_at((x,y)))
    # Separate thighs, shins and boots; the boots keep their own planted transform.
    for side, knee_y, ankle_y in (("near",78,85),("far",79,85)):
        leg = layers[f"{side}_leg"].copy()
        layers[f"{side}_leg"].fill((0,0,0,0))
        for y in range(96):
            for x in range(96):
                color = leg.get_at((x,y))
                if not color.a:
                    continue
                if y <= knee_y+1:
                    layers[f"{side}_leg"].set_at((x,y),color)
                if knee_y-1 <= y <= ankle_y+1:
                    layers[f"{side}_shin"].set_at((x,y),color)
                if y >= ankle_y-1:
                    layers[f"{side}_foot"].set_at((x,y),color)
    return layers


def curve(phase, keys):
    """Monotone cubic (Fritsch-Carlson) through authored keys.

    Velocity is continuous across every key: the motion only comes to rest at
    true extremes (wind-up, peak, endpoints), never at intermediate keys. The
    previous per-segment smoothstep stopped at every key, which read as
    stop-and-go jerks. Endpoints stay exact so actions return to rest.
    """
    xs = [k[0] for k in keys]
    ys = [k[1] for k in keys]
    if phase <= xs[0]:
        return ys[0]
    if phase >= xs[-1]:
        return ys[-1]
    n = len(keys)
    d = [(ys[i+1]-ys[i])/(xs[i+1]-xs[i]) for i in range(n-1)]
    m = [0.0]*n
    for i in range(1, n-1):
        if d[i-1]*d[i] > 0:
            h0, h1 = xs[i]-xs[i-1], xs[i+1]-xs[i]
            w0, w1 = 2*h1+h0, h1+2*h0
            m[i] = (w0+w1)/(w0/d[i-1]+w1/d[i])
    for i in range(n-1):
        if xs[i] <= phase <= xs[i+1]:
            h = xs[i+1]-xs[i]
            t = (phase-xs[i])/h
            t2, t3 = t*t, t*t*t
            return ((2*t3-3*t2+1)*ys[i] + (t3-2*t2+t)*h*m[i]
                    + (-2*t3+3*t2)*ys[i+1] + (t3-t2)*h*m[i+1])
    return ys[-1]


def envelope(phase, peak=.4):
    return curve(phase, ((0,0),(peak,1),(1,0)))


# Source landmarks stay in the same coordinate space as the approved drawing.
LEG_JOINTS = {
    "near": ((51,64),(42,78),(38,89)),
    "far": ((58,64),(64,79),(65,88)),
}


def bone_transform(start, end, target_start, target_end):
    angle = math.atan2(target_end[1]-target_start[1],target_end[0]-target_start[0]) - math.atan2(end[1]-start[1],end[0]-start[0])
    c,s = math.cos(angle),math.sin(angle)
    return Transform(angle, target_start[0]-c*start[0]+s*start[1],
                     target_start[1]-s*start[0]-c*start[1])


def leg_pose(side, hip_shift, foot_shift):
    hip,knee,ankle = LEG_JOINTS[side]
    if hip_shift == (0,0) and foot_shift == (0,0):
        return Transform(),Transform(),Transform()
    target_hip = (hip[0]+hip_shift[0],hip[1]+hip_shift[1])
    target_ankle = (ankle[0]+foot_shift[0],ankle[1]+foot_shift[1])
    l1,l2 = math.dist(hip,knee),math.dist(knee,ankle)
    vx,vy = target_ankle[0]-target_hip[0],target_ankle[1]-target_hip[1]
    distance = math.hypot(vx,vy)
    if distance > l1+l2+1e-7:
        raise ValueError(f"Unreachable {side} leg: {distance:.3f} > {l1+l2:.3f}")
    along = (l1*l1-l2*l2+distance*distance)/(2*distance)
    height = math.sqrt(max(0,l1*l1-along*along))
    cross = (ankle[0]-hip[0])*(knee[1]-hip[1])-(ankle[1]-hip[1])*(knee[0]-hip[0])
    sign = 1 if cross >= 0 else -1
    target_knee = (target_hip[0]+vx/distance*along-vy/distance*height*sign,
                   target_hip[1]+vy/distance*along+vx/distance*height*sign)
    return (bone_transform(hip,knee,target_hip,target_knee),
            bone_transform(knee,ankle,target_knee,target_ankle),
            Transform(tx=foot_shift[0],ty=foot_shift[1]))


def compose(parent, child):
    tx,ty = parent.point((child.tx,child.ty))
    return Transform(parent.angle+child.angle,tx,ty)


def pose_at(action, phase):
    p = max(0,min(1,phase))
    if action == "idle":
        p %= 1
    if p == 0 or (p == 1 and action != "death"):
        return {name:Transform() for name in ORDER}
    torso_angle = head_angle = near_arm = near_elbow = far_arm = far_elbow = 0.
    dx = dy = front_step = front_lift = rear_step = roll = 0.
    hair_angle = cape_angle = 0.
    if action == "idle":
        breath = (1-math.cos(math.tau*p))/2
        torso_angle,head_angle = -.9*breath,.7*breath
        near_arm,near_elbow,far_arm = -1.8*breath,2.8*breath,1.6*breath
        hair_angle,cape_angle = 3*math.sin(math.tau*p),-2.4*math.sin(math.tau*p)
    elif action == "attack":
        # Compress -> push off -> extend -> cut through -> fold elbow -> recover.
        dx = curve(p,((0,0),(.2,-6),(.42,0),(.57,0),(.78,-1),(1,0)))
        dy = curve(p,((0,0),(.2,4),(.42,7),(.57,6),(.78,3),(1,0)))
        torso_angle = curve(p,((0,0),(.2,-10),(.42,15),(.57,18),(.78,7),(1,0)))
        head_angle = -torso_angle*.55
        near_arm = curve(p,((0,0),(.2,30),(.42,-125),(.57,-165),(.78,-65),(1,0)))
        near_elbow = curve(p,((0,0),(.2,-65),(.42,0),(.57,30),(.78,-65),(1,0)))
        far_arm = curve(p,((0,0),(.2,12),(.42,4),(.57,-5),(.78,8),(1,0)))
        far_elbow = curve(p,((0,0),(.2,-20),(.42,-40),(.57,-20),(.78,-10),(1,0)))
        front_step = curve(p,((0,0),(.2,0),(.38,6),(.65,6),(1,0)))
        front_lift = curve(p,((0,0),(.2,0),(.29,-2),(.38,0),(.65,0),(.8,-2),(1,0)))
        hair_angle = curve(p,((0,0),(.24,6),(.48,-12),(.64,-6),(.84,4),(1,0)))
        cape_angle = curve(p,((0,0),(.24,5),(.5,-16),(.68,-6),(.85,3),(1,0)))
    elif action == "guard":
        e = envelope(p,.38)
        dx,dy = -5*e,9*e
        torso_angle,head_angle = -15*e,10*e
        near_arm,near_elbow = -105*e,-10*e
        far_arm,far_elbow = -10*e,-90*e
        hair_angle,cape_angle = 10*envelope(p,.48),8*envelope(p,.5)
    elif action == "hurt":
        e = envelope(p,.2)
        dx,dy = -3*e,4*e
        torso_angle,head_angle = -19*e,-6*e
        near_arm,near_elbow = 22*e,-20*e
        far_arm,far_elbow = 15*e,-25*e
        hair_angle,cape_angle = 12*envelope(p,.31),10*envelope(p,.34)
    elif action == "cast":
        e = envelope(p,.48)
        dy = 2*e
        near_arm,near_elbow = 15*e,95*e
        far_arm,far_elbow = 5*e,-80*e
        torso_angle,head_angle = -3*e,3*e
        hair_angle,cape_angle = -6*envelope(p,.6),6*envelope(p,.62)
    elif action == "death":
        collapse = curve(p,((0,0),(.2,.2),(.48,1),(1,1)))
        dy = 12*collapse
        torso_angle,head_angle = 16*collapse,14*collapse
        near_arm,near_elbow = -25*collapse,-25*collapse
        far_arm,far_elbow = 10*collapse,-15*collapse
        roll = curve(p,((0,0),(.4,0),(.82,1),(1,1)))
        hair_angle,cape_angle = 8*roll,6*roll
    root = Transform(tx=dx,ty=dy)
    torso = root.joint((53,64),torso_angle)
    head = torso.joint((55,42),head_angle)
    near = torso.joint((47,45),near_arm)
    far = torso.joint((63,46),far_arm)
    near_forearm = near.joint((41,56),near_elbow)
    far_forearm = far.joint((67,57),far_elbow)
    near_leg,near_shin,near_foot = leg_pose("near",(dx,dy),(rear_step,0))
    far_leg,far_shin,far_foot = leg_pose("far",(dx,dy),(front_step,front_lift))
    pose = {"torso":torso,"head":head,
            "near_arm":near,"near_forearm":near_forearm,"near_weapon":near_forearm,
            "far_arm":far,"far_forearm":far_forearm,"far_weapon":far_forearm,
            "hair":head.joint((45,21),hair_angle),"cape":torso.joint((44,43),cape_angle),
            "near_leg":near_leg,"far_leg":far_leg,"near_shin":near_shin,"far_shin":far_shin,
            "near_foot":near_foot,"far_foot":far_foot}
    if roll:
        fall = Transform().joint((53,76),-88*roll,(-3*roll,3*roll))
        pose = {name:compose(fall,t) for name,t in pose.items()}
    if action == "death":
        # Feet, dagger tips and the ends of the hair/cape keep the fall in-frame.
        supports = {"near_foot":((31,84),(31,93),(47,93)),"far_foot":((60,84),(76,93)),
                    "near_shin":((29,80),(34,77),(34,86),(49,86)),"far_shin":((59,78),(70,86)),
                    "hair":((18,30),(18,44),(40,14)),"cape":((18,58),(22,68)),
                    "near_forearm":((27,80),(41,56)),"far_forearm":((85,77),(67,57)),
                    "head":((43,20),(68,42)),"near_leg":((41,64),(54,80)),
                    "far_leg":((55,64),(69,80))}
        points = [pose[name].point(point) for name,anchors in supports.items() for point in anchors]
        shift_x = max(0,3-min(point[0] for point in points))
        shift_y = min(0,92-max(point[1] for point in points))
        pose = {name:Transform(t.angle,t.tx+shift_x,t.ty+shift_y) for name,t in pose.items()}
    return pose


def _layer_pixels(layer):
    w, h = layer.get_size()
    return [[tuple(layer.get_at((x, y))) for x in range(w)] for y in range(h)]


_PIXEL_CACHE = {}


def render_pose(layers, pose, scale=1):
    """Draw the pose at ``scale`` x the 96 px art.

    Rendering the 192 px sheet directly (instead of enlarging the 96 px frame)
    lets each joint move in half-pixel steps of the art, so slow motions such
    as breathing glide instead of popping by whole 2 px blocks. Sampling is
    still nearest-neighbour from the original pixels: no blur, no repaint.
    """
    size = 96*scale
    canvas = pygame.Surface((size, size), pygame.SRCALPHA)
    for name in ORDER:
        layer, transform = layers[name], pose[name]
        bounds = layer.get_bounding_rect()
        if not bounds.width:
            continue
        key = id(layer)
        if key not in _PIXEL_CACHE:
            _PIXEL_CACHE[key] = (layer, _layer_pixels(layer))
        pixels = _PIXEL_CACHE[key][1]
        c, s = math.cos(transform.angle), math.sin(transform.angle)
        corners = [transform.point(point) for point in (bounds.topleft, bounds.topright,
                                                        bounds.bottomleft, bounds.bottomright)]
        left = max(0, math.floor(min(p[0] for p in corners)*scale)-scale)
        right = min(size, math.ceil(max(p[0] for p in corners)*scale)+scale)
        top = max(0, math.floor(min(p[1] for p in corners)*scale)-scale)
        bottom = min(size, math.ceil(max(p[1] for p in corners)*scale)+scale)
        # Sample at destination pixel centres (identical to the old 1x result
        # when scale == 1 because round(i) == floor(i + .5)).
        offset = .5 - .5/scale
        for y in range(top, bottom):
            py = y/scale - offset - transform.ty
            for x in range(left, right):
                px = x/scale - offset - transform.tx
                sx, sy = round(c*px+s*py), round(-s*px+c*py)
                if 0 <= sx < 96 and 0 <= sy < 96:
                    color = pixels[sy][sx]
                    if color[3]:
                        canvas.set_at((x, y), color)
    return canvas
