"""Rigid cutout rig of the approved rogue, with continuous authored joint curves.

No generated pose switching, global image warp, optical flow or frame blending.
Coordinates are on the approved 96 px rest drawing.
"""
import math
import pygame
from warrior_rig import Transform

ORDER = ("hair", "cape", "far_leg", "near_leg", "torso", "far_arm", "far_forearm", "head", "near_arm", "near_forearm", "near_weapon", "far_weapon")
REGIONS = {
    "head": [(43,18),(69,18),(70,44),(62,45),(55,42),(47,41),(42,34)],
    "near_forearm": [(36,54),(45,54),(46,62),(41,67),(34,75),(26,82),(27,72),(32,64)],
    "near_arm": [(43,42),(50,44),(48,51),(45,58),(36,57),(40,48)],
    "far_forearm": [(65,55),(71,55),(75,63),(88,73),(84,79),(70,68),(65,64)],
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


def pose_at(action, phase):
    p = max(0,min(1,phase))
    # Exact endpoints avoid numerical seam differences.
    breath = (1-math.cos(math.tau*p))/2 if 0 < p < 1 else 0
    torso_angle = head_angle = near_arm = near_elbow = far_arm = far_elbow = 0.
    dx = dy = fall = 0.
    hair_angle = 3.0*math.sin(math.tau*p) if action == "idle" and 0<p<1 else 0.
    cape_angle = -2.4*math.sin(math.tau*p) if action == "idle" and 0<p<1 else 0.
    if action == "idle":
        torso_angle = -.9*breath
        head_angle = .7*breath
        near_arm, near_elbow = -1.8*breath, 2.8*breath
        far_arm = 1.6*breath
    elif action == "attack":
        wind = curve(p, ((0,0),(.22,-1),(.43,1),(.58,.8),(1,0)))
        torso_angle = 5*wind
        dx = 1.5*wind
        near_arm = -43*wind
        near_elbow = -20*wind
        far_arm, far_elbow = -7*wind, -12*wind
        hair_angle, cape_angle = -10*wind, -8*wind
    elif action == "guard":
        e = envelope(p,.35)
        dx = -6*e
        torso_angle = -12*e
        near_arm, near_elbow = -22*e,-38*e
        far_arm, far_elbow = -32*e,-25*e
        head_angle, hair_angle, cape_angle = 6*e,10*e,7*e
    elif action == "hurt":
        e = envelope(p,.2)
        dx = -4*e
        torso_angle, head_angle = -11*e,-5*e
        near_arm, near_elbow = 12*e,12*e
        far_arm = 15*e
        hair_angle, cape_angle = 9*e,7*e
    elif action == "cast":
        e = envelope(p,.48)
        near_arm, near_elbow = -25*e,-45*e
        far_arm, far_elbow = -8*e,-18*e
        torso_angle, head_angle = -2*e,2*e
        hair_angle, cape_angle = -4*e,4*e
    elif action == "death":
        fall = curve(p,((0,0),(.2,.08),(.42,.3),(.8,1),(1,1)))
        near_arm, near_elbow = 15*fall,20*fall
        far_arm = -12*fall
        head_angle = -8*fall
        hair_angle, cape_angle = 8*fall,5*fall
    root = Transform(tx=dx,ty=dy)
    if action == "death":
        root = root.joint((53,63),-78*fall, (0*fall,-18*fall))
    torso = root.joint((53,64),torso_angle)
    head = torso.joint((55,42),head_angle)
    near = torso.joint((47,45),near_arm)
    far = torso.joint((63,46),far_arm)
    near_forearm = near.joint((41,56),near_elbow)
    far_forearm = far.joint((67,57),far_elbow)
    pose = {"torso":torso,"head":head,
            "near_arm":near,"near_forearm":near_forearm,"near_weapon":near_forearm,
            "far_arm":far,"far_forearm":far_forearm,"far_weapon":far_forearm,
            "hair":head.joint((45,21),hair_angle),"cape":torso.joint((44,43),cape_angle),
            "near_leg":root,"far_leg":root}
    if action == "death" and p > 0:
        supports = {"near_leg": ((31,93),(47,93)), "far_leg": ((60,93),(76,93)),
                    "hair": ((18,44),(18,30),(40,14)), "cape": ((18,58),(22,68)),
                    "near_forearm": ((27,80),(40,65)), "far_forearm": ((85,77),)}
        bottom = max(pose[name].point(point)[1] for name,points in supports.items() for point in points)
        settle = min(1, p/.06)
        offset = (92-bottom)*settle*settle*(3-2*settle)
        pose = {name: Transform(t.angle,t.tx,t.ty+offset) for name,t in pose.items()}
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
