"""Layered skeletal animation authoring. Coordinates use the 256 px art canvas."""
from dataclasses import dataclass
import math
import pygame


@dataclass(frozen=True)
class Transform:
    angle: float = 0.0
    tx: float = 0.0
    ty: float = 0.0

    def point(self, point):
        x,y = point
        c,s = math.cos(self.angle),math.sin(self.angle)
        return c*x-s*y+self.tx, s*x+c*y+self.ty

    def joint(self, pivot, degrees, shift=(0,0)):
        angle = self.angle + math.radians(degrees)
        px,py = self.point(pivot)
        c,s = math.cos(angle),math.sin(angle)
        return Transform(angle,px+shift[0]-c*pivot[0]+s*pivot[1],
                         py+shift[1]-s*pivot[0]-c*pivot[1])


# Periodic Catmull-Rom keys describe acting, not a global image displacement.
# Inhalation is shorter than exhalation; the elbows follow the shoulders.
KEYS = {
    'breath': (0,0.25,0.8,1,0.85,0.5,0.15,0),
    'torso': (0,-0.35,-0.75,-0.8,-0.45,0.05,0.25,0.15),
    'arm': (0,-0.5,-1.6,-2.0,-0.7,0.9,1.3,0.7),
    'elbow': (0,0.8,2.5,3.2,1.6,-0.7,-1.6,-0.8),
    'head': (0,0.1,0.35,0.7,0.65,0.3,-0.15,-0.1),
    'hair': (0,-1.0,-3.0,-4.0,-1.5,2.0,3.5,2.0),
    'cape': (0,-0.3,-1.2,-2.0,-1.0,1.1,1.6,0.8),
}


def curve(name, phase):
    values=KEYS[name]
    position=(phase%1)*len(values)
    i=int(position)
    t=position-i
    p0,p1,p2,p3=(values[j%len(values)] for j in (i-1,i,i+1,i+2))
    return 0.5*((2*p1)+(-p0+p2)*t+(2*p0-5*p1+4*p2-p3)*t*t+(-p0+3*p1-3*p2+p3)*t*t*t)


def lagged(name, phase, lag):
    return curve(name,phase-lag)-curve(name,-lag)


def build_pose(phase):
    torso=Transform().joint((143,109),1.3*curve('torso',phase),(0,-2.0*curve('breath',phase)))
    head=torso.joint((144,61),curve('head',phase))
    arm=torso.joint((120,69),1.7*curve('arm',phase))
    forearm=arm.joint((109,96),1.5*curve('elbow',phase))
    return {
        'legs':Transform(), 'torso':torso, 'head':head,
        'upper_arm':arm, 'forearm':forearm, 'weapon':forearm,
        'far_arm':torso.joint((160,78),-0.6*1.7*curve('arm',phase)),
        'hair':head.joint((129,19),1.3*lagged('hair',phase,0.06)),
        'cape':torso.joint((131,67),1.5*lagged('cape',phase,0.1)),
    }


# Frontmost silhouettes are selected first. The pristine face is never painted
# over or resampled by an AI editor. Backing art is used only inside removed masks.
REGIONS = {
    'weapon': [(96,113),(101,114),(108,124),(114,128),(128,121),(132,124),
               (122,133),(179,186),(179,191),(118,141),(109,146),(107,140),
               (110,133),(105,130),(100,124),(96,120)],
    'forearm': [(104,93),(114,95),(113,102),(110,114),(112,124),(114,129),
                (110,133),(104,132),(101,127),(101,119),(102,106)],
    'upper_arm': [(116,57),(125,59),(130,65),(128,73),(120,84),(114,97),
                  (103,95),(104,87),(108,76),(108,68)],
    'far_arm': [(160,78),(166,87),(169,103),(173,123),(181,135),(181,141),
                (176,146),(172,143),(168,138),(165,127),(162,115),(159,109),(158,93)],
    'head': [(128,18),(163,18),(168,32),(168,58),(160,69),(153,66),
             (148,63),(144,62),(138,65),(130,61),(128,52),(122,47),(123,30)],
    'hair': [(126,7),(136,12),(134,19),(127,25),(124,42),(119,54),(111,64),
             (104,84),(99,100),(80,100),(67,88),(67,68),(75,51),(92,38),(108,21)],
    'cape': [(116,64),(130,66),(133,85),(127,102),(117,115),(102,130),
             (92,140),(82,147),(70,142),(66,126),(69,115),(94,99),(105,77)],
}
DRAW_ORDER=('cape','hair','legs','far_arm','torso','head','upper_arm','forearm','weapon')


def mask_polygon(points, size):
    mask=pygame.Surface((size,size),pygame.SRCALPHA)
    pygame.draw.polygon(mask,'white',points)
    return mask


def separate_layers(base, backing):
    size=base.get_width()
    layers={name:pygame.Surface((size,size),pygame.SRCALPHA) for name in DRAW_ORDER}
    masks={name:mask_polygon(points,size) for name,points in REGIONS.items()}
    for y in range(size):
        for x in range(size):
            name=next((n for n,m in masks.items() if m.get_at((x,y)).a),None)
            color=base.get_at((x,y))
            if name:
                layers[name].set_at((x,y),color)
                # AI reconstruction only replaces the material hidden behind
                # moved arms, hair and blade. Exclude its head and all foot art.
                if name != 'head' and 54 <= y < 194:
                    support='cape' if masks['cape'].get_at((x,y)).a else ('torso' if y<109 else 'legs')
                    layers[support].set_at((x,y),backing.get_at((x,y)))
            else:
                layers['torso' if y<111 else 'legs'].set_at((x,y),color)
    # A small overlap across the waist prevents a gap under torso rotation.
    for y in range(107,114):
        for x in range(123,166):
            layers['torso'].set_at((x,y),backing.get_at((x,y)))
    return layers


def render_pose(layers, pose, size=256):
    output=pygame.Surface((size,size),pygame.SRCALPHA)
    for name in DRAW_ORDER:
        layer=layers[name]
        transform=pose[name]
        c,s=math.cos(transform.angle),math.sin(transform.angle)
        bounds=layer.get_bounding_rect()
        corners=[transform.point(p) for p in (bounds.topleft,bounds.topright,bounds.bottomleft,bounds.bottomright)]
        left=max(0,math.floor(min(p[0] for p in corners))-1)
        right=min(size,math.ceil(max(p[0] for p in corners))+1)
        top=max(0,math.floor(min(p[1] for p in corners))-1)
        bottom=min(size,math.ceil(max(p[1] for p in corners))+1)
        for y in range(top,bottom):
            for x in range(left,right):
                px,py=x-transform.tx,y-transform.ty
                sx,sy=round(c*px+s*py),round(-s*px+c*py)
                if 0<=sx<size and 0<=sy<size:
                    color=layer.get_at((sx,sy))
                    if color.a:
                        output.set_at((x,y),color)
    return output
