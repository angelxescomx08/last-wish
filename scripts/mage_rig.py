"""Rigid pixel-art mage rig, authored on a 96 px canvas.

The generated drawing supplies every visible character pixel. Joint transforms
preserve the face, hand/staff attachment and limb lengths; only FX are drawn.
"""
from pathlib import Path
import math
import pygame
from warrior_rig import Transform
from rogue_rig import bone_transform, curve

CELL = 96
ASSETS = Path(__file__).resolve().parents[1] / "assets" / "characters"
ORDER = ("cape", "far_leg", "far_shin", "far_foot", "near_leg", "near_shin", "near_foot",
         "back_robe", "torso", "far_arm", "far_forearm", "staff", "front_robe", "head", "near_arm", "near_forearm")
REGIONS = {
    # Masks follow material boundaries in the source drawing. The staff and its
    # gripping fingers share the forearm transform, including the lower shaft.
    "staff": [(71,18),(80,18),(80,32),(75,36),(75,47),(73,55),(70,64),(66,64),(67,58),(69,47),(70,34),(68,29),(68,23)],
    "head": [(33,12),(69,12),(69,38),(62,39),(58,43),(48,42),(40,39),(35,32)],
    "near_forearm": [(34,53),(37,53),(40,55),(40,57),(37,58),(38,60),(39,61),(39,63),(37,63),(36,62),(35,64),(34,67),(31,67),(31,66),(29,66),(29,63),(30,62),(32,60),(32,59),(31,59),(31,57),(33,56)],
    "near_arm": [(40,42),(47,45),(43,50),(41,56),(38,56),(36,54),(33,54),(33,51),(35,47)],
    "far_forearm": [(63,47),(66,46),(69,42),(74,42),(74,49),(70,51),(66,54),(63,53)],
    "far_arm": [(59,43),(63,43),(67,48),(66,54),(62,54),(58,49)],
    "cape": [(16,35),(43,35),(44,42),(40,45),(35,50),(34,56),(34,60),(39,60),(39,64),(36,67),(30,70),(24,71),(16,71)],
    "front_robe": [(46,57),(51,57),(49,61),(48,65),(46,68),(45,70),(46,73),(46,78),(43,78),(42,74),(41,71),(38,71),(35,73),(34,76),(30,77),(28,75),(31,71),(33,69),(35,67),(39,64),(43,60)],
    "back_robe": [
        [(60,57),(63,57),(67,64),(68,66),(69,68),(72,71),(73,76),(73,79),(69,79),(69,75),(67,74),(66,70),(64,67),(62,65)],
        [(51,65),(56,64),(57,68),(58,73),(56,76),(51,75),(49,72)],
    ],
    "near_leg": [(47,58),(55,58),(53,64),(50,70),(47,75),(43,79),(40,85),(42,92),(30,94),(29,89),(34,82),(34,74),(39,66)],
    "far_leg": [(54,57),(61,57),(66,67),(66,78),(65,83),(72,91),(59,94),(56,85),(55,76),(50,69)],
}
LEG_JOINTS = {"near": ((47,60),(40,74),(36,86)), "far": ((55,60),(59,74),(62,85))}
SHOULDERS = {"near": (43,45), "far": (60,45)}
ELBOWS = {"near": (37,54), "far": (65,50)}
PALM = (31,63)
CRYSTAL = (75,25)


def prepare_base():
    """Import the coarse pixel drawing with nearest sampling and binary alpha."""
    source = pygame.image.load(str(ASSETS / "mage-source-v2.png"))
    art = source.subsurface(source.get_bounding_rect(min_alpha=128))
    size = (round(art.get_width()*78/art.get_height()), 78)
    canvas = pygame.Surface((CELL,CELL),pygame.SRCALPHA)
    canvas.blit(pygame.transform.scale(art,size),(17,14))
    for y in range(CELL):
        for x in range(CELL):
            color = canvas.get_at((x,y))
            canvas.set_at((x,y), (*color[:3],255) if color.a >= 128 else (0,0,0,0))
    pygame.image.save(canvas,str(ASSETS / "mage-rig-base.png"))
    return canvas


def load_base():
    return pygame.image.load(str(ASSETS / "mage-rig-base.png"))


def split_layers(base):
    layers = {name:pygame.Surface((CELL,CELL),pygame.SRCALPHA) for name in ORDER}
    masks = {}
    for name,points in REGIONS.items():
        mask = pygame.Surface((CELL,CELL),pygame.SRCALPHA)
        polygons = points if isinstance(points[0][0], tuple) else [points]
        for polygon in polygons:
            pygame.draw.polygon(mask,"white",polygon)
        masks[name] = mask
    for y in range(CELL):
        for x in range(CELL):
            color = base.get_at((x,y))
            if not color.a:
                continue
            fallback = ("near_leg" if x < 49 else "far_leg") if y >= 64 else "torso"
            if 64 <= y < 80 and x >= 67:
                fallback = "back_robe"
            name = next((name for name,mask in masks.items() if mask.get_at((x,y)).a),fallback)
            # The fingers overlap the blue cape in the source. Keep those
            # visible cloth pixels on the cape, rather than carrying blue
            # triangles along with the casting hand.
            if name == "near_forearm" and color.b > color.r*1.65 and color.b > color.g*1.5:
                name = "cape"
            # Trouser shadows are neutral violet, unlike the saturated blue
            # robe panels. The broad cloth mask must not steal the thighs.
            if name in {"front_robe", "back_robe"} and 60 <= y <= 79 and color.r < 95 and color.g < 95 and color.b-color.r < 34:
                side = "near" if x < 53 else "far"
                if masks[f"{side}_leg"].get_at((x,y)).a:
                    name = f"{side}_leg"
            layers[name].set_at((x,y),color)
    # Move isolated mask leftovers to the adjacent physical piece. At rest
    # these are outline pixels, not independent floating costume fragments.
    for name in ("torso", "near_leg", "far_leg", "near_arm", "near_forearm", "front_robe", "back_robe"):
        surface = layers[name]
        mask = pygame.mask.from_surface(surface)
        components = mask.connected_components()
        for component in components:
            if component.count() >= 8:
                continue
            points = [(x,y) for y in range(CELL) for x in range(CELL) if component.get_at((x,y))]
            for x,y in points:
                candidates = []
                for other,other_surface in layers.items():
                    if other == name:
                        continue
                    for oy in range(max(0,y-2),min(CELL,y+3)):
                        for ox in range(max(0,x-2),min(CELL,x+3)):
                            if other_surface.get_at((ox,oy)).a:
                                candidates.append(((ox-x)**2+(oy-y)**2,other))
                if candidates:
                    destination = min(candidates)[1]
                    layers[destination].set_at((x,y),surface.get_at((x,y)))
                    surface.set_at((x,y),(0,0,0,0))
    # The source hand occludes the cape. Restore only that hidden cloth,
    # sampling the existing cape; the hand covers every added pixel at rest.
    cape_samples = [(x,y,layers["cape"].get_at((x,y))) for y in range(43,68) for x in range(22,40)
                    if layers["cape"].get_at((x,y)).a]
    for y in range(48,66):
        for x in range(29,41):
            if layers["cape"].get_at((x,y)).a:
                continue
            if not any(layers[cover].get_at((x,y)).a for cover in ("near_arm","near_forearm")):
                continue
            sample = min(cape_samples,key=lambda sample:(sample[0]-x)**2+(sample[1]-y)**2)
            if (sample[0]-x)**2+(sample[1]-y)**2 <= 16:
                layers["cape"].set_at((x,y),sample[2])
    # Underlapping trouser patches use the nearest existing trouser pixel.
    # Every added pixel is hidden by the untouched robe/torso at rest.
    for side in ("near", "far"):
        leg = layers[f"{side}_leg"]
        samples = [(x,y,leg.get_at((x,y))) for y in range(60,78) for x in range(28,68)
                   if leg.get_at((x,y)).a and leg.get_at((x,y)).b-leg.get_at((x,y)).r < 34]
        for y in range(60,77):
            for x in range(32,66):
                if leg.get_at((x,y)).a or not masks[f"{side}_leg"].get_at((x,y)).a:
                    continue
                if not any(layers[cover].get_at((x,y)).a for cover in ("torso","front_robe","back_robe")):
                    continue
                if (side == "near" and x >= 53) or (side == "far" and x < 53):
                    continue
                source = min(samples,key=lambda sample:(sample[0]-x)**2+(sample[1]-y)**2)
                leg.set_at((x,y),source[2])
    # Source-derived caps overlap underneath each articulated sleeve.
    for name,center,radius in (("torso",(43,45),3),("torso",(60,45),3),
                               ("near_arm",(37,54),3),("far_arm",(65,50),2),
                               ("torso",(49,59),4)):
        for y in range(center[1]-radius,center[1]+radius+1):
            for x in range(center[0]-radius,center[0]+radius+1):
                if math.dist((x,y),center) <= radius:
                    layers[name].set_at((x,y),base.get_at((x,y)))
    for side,knee_y,ankle_y in (("near",74,84),("far",74,83)):
        leg = layers[f"{side}_leg"].copy()
        layers[f"{side}_leg"].fill((0,0,0,0))
        for y in range(CELL):
            for x in range(CELL):
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


def leg_pose(side, target_hip, foot_shift):
    hip,knee,ankle = LEG_JOINTS[side]
    if target_hip == hip and foot_shift == (0,0):
        return Transform(),Transform(),Transform()
    target_ankle = (ankle[0]+foot_shift[0],ankle[1]+foot_shift[1])
    l1,l2 = math.dist(hip,knee),math.dist(knee,ankle)
    vx,vy = target_ankle[0]-target_hip[0],target_ankle[1]-target_hip[1]
    distance = math.hypot(vx,vy)
    if not abs(l1-l2) < distance <= l1+l2+1e-7:
        raise ValueError(f"Unreachable mage {side} leg: {distance:.3f}")
    along = (l1*l1-l2*l2+distance*distance)/(2*distance)
    height = math.sqrt(max(0,l1*l1-along*along))
    cross = (ankle[0]-hip[0])*(knee[1]-hip[1])-(ankle[1]-hip[1])*(knee[0]-hip[0])
    sign = 1 if cross >= 0 else -1
    target_knee = (target_hip[0]+vx/distance*along-vy/distance*height*sign,
                   target_hip[1]+vy/distance*along+vx/distance*height*sign)
    return (bone_transform(hip,knee,target_hip,target_knee),
            bone_transform(knee,ankle,target_knee,target_ankle),
            Transform(tx=foot_shift[0],ty=foot_shift[1]))


def envelope(p,peak=.4):
    return curve(p,((0,0),(peak,1),(1,0)))


def pose_at(action, phase):
    p = max(0,min(1,phase))
    if action == "idle":
        p %= 1
    if p == 0 or (p == 1 and action != "death"):
        return {name:Transform() for name in ORDER}
    dx=dy=body=head=upper=elbow=staff_arm=staff_elbow=cape=robe=step=lift=0.
    if action == "idle":
        breath = (1-math.cos(math.tau*p))/2
        body,head,dy = -.7*breath,.7*breath,.35*breath
        upper,elbow = -2*breath,3*breath
        staff_arm,staff_elbow = -.8*breath,1.3*breath
        cape,robe = 2.5*math.sin(math.tau*p),1.2*math.sin(math.tau*p)
    elif action == "attack":
        dx = curve(p,((0,0),(.22,-3),(.45,3),(.58,3),(.78,1),(1,0)))
        dy = curve(p,((0,0),(.22,3),(.45,5),(.6,4),(1,0)))
        body = curve(p,((0,0),(.22,-9),(.45,12),(.58,14),(.78,5),(1,0)))
        upper = curve(p,((0,0),(.22,24),(.45,-108),(.58,-117),(.8,-40),(1,0)))
        elbow = curve(p,((0,0),(.22,38),(.45,-25),(.58,-10),(.8,28),(1,0)))
        staff_arm = curve(p,((0,0),(.22,-10),(.45,10),(.62,7),(1,0)))
        staff_elbow = -staff_arm-body*.7
        step = curve(p,((0,0),(.22,0),(.4,4),(.65,4),(1,0)))
        lift = curve(p,((0,0),(.22,0),(.3,-2),(.4,0),(.65,0),(.82,-1.5),(1,0)))
        cape = curve(p,((0,0),(.28,5),(.52,-10),(.68,-5),(.85,2),(1,0)))
        robe = -cape*.5
        head = -body*.6
    elif action == "guard":
        e = envelope(p,.4)
        dx,dy,body,head = -2*e,6*e,-9*e,8*e
        upper,elbow = -95*e,-55*e
        staff_arm,staff_elbow = -6*e,10*e
        cape,robe = 7*envelope(p,.51),-3*e
    elif action == "hurt":
        e = envelope(p,.22)
        dx,dy,body,head = -3*e,4*e,-13*e,-5*e
        upper,elbow = 22*e,-16*e
        staff_arm,staff_elbow = -10*e,19*e
        cape,robe = 10*envelope(p,.33),3*envelope(p,.35)
    elif action == "cast":
        e = envelope(p,.5)
        dy,body,head = 3*e,-5*e,6*e
        upper = curve(p,((0,0),(.23,-35),(.5,-145),(.65,-140),(.84,-50),(1,0)))
        elbow = curve(p,((0,0),(.23,-30),(.5,-10),(.65,0),(.84,35),(1,0)))
        staff_arm,staff_elbow = -14*e,7*e
        cape,robe = -7*envelope(p,.6),3*envelope(p,.58)
    elif action == "death":
        e = curve(p,((0,0),(.25,.35),(.6,1),(1,1)))
        dx,dy,body,head = -2*e,10*e,23*e,16*e
        upper,elbow = -10*e,-12*e
        staff_arm,staff_elbow = 12*e,-22*e
        cape,robe = -8*e,5*e
    else:
        raise ValueError(f"Unknown mage animation: {action}")
    torso = Transform(tx=dx,ty=dy).joint((51,60),body)
    near = torso.joint(SHOULDERS["near"],upper)
    far = torso.joint(SHOULDERS["far"],staff_arm)
    forearm = near.joint(ELBOWS["near"],elbow)
    staff_forearm = far.joint(ELBOWS["far"],staff_elbow)
    pose = {"torso":torso,"head":torso.joint((51,40),head),
            "near_arm":near,"near_forearm":forearm,"far_arm":far,
            "far_forearm":staff_forearm,"staff":staff_forearm,
            "cape":torso.joint((41,39),cape),
            "front_robe":torso.joint((48,58),robe),
            "back_robe":torso.joint((55,58),-robe*.7)}
    for side,foot_shift in (("near",(0,0)),("far",(step,lift))):
        transforms = leg_pose(side,torso.point(LEG_JOINTS[side][0]),foot_shift)
        for name,t in zip(("leg","shin","foot"),transforms):
            pose[f"{side}_{name}"] = t
    return pose


def magic_origin(pose, action):
    return pose["near_forearm"].point(PALM)


_PIXEL_CACHE = {}


def render_pose(layers, pose, scale=1):
    """Inverse-map original pixels at native 96 or 192 px, without smoothing."""
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


