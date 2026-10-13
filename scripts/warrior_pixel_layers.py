"""Source-pixel segmentation for the 96 px warrior drawing.

Masks follow armour, cloth and hair boundaries. Hidden underlaps copy source
pixels and remain covered at rest, so composing the layers reproduces the base.
"""
import math

import pygame

CELL = 96
ORDER = (
    "hair", "cape", "far_leg", "far_shin", "far_foot",
    "near_leg", "near_shin", "near_foot", "back_cloth", "torso",
    "head", "sword_upper", "sword_forearm", "weapon",
    "front_cloth", "free_upper", "free_forearm",
)

# Dictionary order is the ownership priority where source silhouettes overlap.
REGIONS = {
    "weapon": [(63,56),(66,56),(66,59),(65,61),(68,63),(83,78),
               (83,81),(80,80),(63,65),(61,65),(58,66),(59,62),(61,60)],
    "head": [(40,19),(49,20),(54,24),(55,29),(55,34),(53,39),
             (49,39),(46,38),(43,38),(40,36),(37,31),(37,24)],
    "sword_forearm": [(53,51),(56,50),(58,54),(60,56),(63,57),
                      (63,61),(60,63),(57,61),(55,57),(53,56)],
    "sword_upper": [(50,39),(53,39),(55,43),(54,47),(57,51),
                    (56,55),(53,55),(51,51),(51,47)],
    "free_forearm": [(30,49),(34,49),(36,52),(35,55),(33,59),
                     (33,64),(29,65),(27,62),(28,57),(29,54)],
    "free_upper": [(35,36),(39,37),(43,40),(43,43),(40,46),
                   (38,48),(36,50),(35,53),(30,51),(33,46),(33,41)],
    "hair": [(10,14),(43,14),(44,19),(39,23),(37,28),(37,36),
             (35,40),(30,42),(28,48),(16,48),(10,43)],
    "front_cloth": [(43,52),(50,53),(53,57),(53,63),(52,69),
                    (49,73),(46,71),(44,69),(43,64)],
    "back_cloth": [
        [(39,53),(44,53),(43,58),(42,62),(40,65),(36,68),
         (32,69),(30,71),(27,70),(27,66),(32,64),(35,61),(36,57)],
        [(56,60),(58,61),(59,65),(60,70),(60,72),(57,70),(55,66)],
    ],
    "near_leg": [(49,56),(54,56),(57,60),(58,68),(59,73),
                 (59,81),(58,86),(65,91),(65,93),(52,93),
                 (51,85),(51,77),(50,71),(48,65)],
    "far_leg": [(39,56),(46,56),(46,63),(44,68),(41,72),
                (39,77),(35,82),(33,90),(33,93),(23,93),
                (25,86),(27,78),(30,73),(33,68),(36,63)],
    "cape": [(8,40),(34,39),(41,42),(43,49),(40,56),(37,63),
             (34,69),(30,71),(24,69),(23,64),(18,65),(14,60),(8,59)],
}


def _region_masks():
    masks = {}
    for name, points in REGIONS.items():
        mask = pygame.Surface((CELL, CELL), pygame.SRCALPHA)
        polygons = points if isinstance(points[0][0], tuple) else [points]
        for polygon in polygons:
            pygame.draw.polygon(mask, "white", polygon)
        masks[name] = mask
    return masks


def _is_teal(color):
    return color.g > color.r * 1.2 and color.b > color.r * 1.2


def _is_trouser(color):
    return color.r < 120 and color.g < 120 and abs(color.r-color.g) < 20 and color.b >= color.r * .85


def _is_cloth_trim(color):
    red = color.r > color.g * 1.4 and color.r > color.b * 1.3
    gold = color.r > 90 and color.r > color.g * 1.05 and color.g > color.b * 1.5
    return red or gold


def _owner(x, y, color, masks):
    fallback = ("far_leg" if x < 46 else "near_leg") if y >= 64 else "torso"
    name = next((name for name, mask in masks.items() if mask.get_at((x, y)).a), fallback)
    # The free hand crosses the cloak. Preserve the cloak's teal pixels on it.
    if name in {"hair", "free_upper", "free_forearm", "back_cloth"} and y >= 38 and _is_teal(color):
        return "cape"
    if name == "cape" and x >= 36 and y < 58 and not _is_teal(color):
        return "torso"
    if name == "free_forearm" and y >= 63 and _is_cloth_trim(color):
        return "back_cloth"
    # The tabard has red cloth and gold piping; neutral trousers visible at
    # its side remain attached to the legs when the cloth swings away.
    if name in {"front_cloth", "back_cloth"} and 58 <= y <= 73 and _is_trouser(color):
        side = "far_leg" if x < 46 else "near_leg"
        if masks[side].get_at((x, y)).a:
            return side
    return name


def _move_small_components(layers):
    """Attach isolated outline pixels to their adjacent physical piece."""
    for name in ("hair", "torso", "near_leg", "far_leg", "sword_upper", "sword_forearm",
                 "free_upper", "free_forearm", "front_cloth", "back_cloth"):
        surface = layers[name]
        for component in pygame.mask.from_surface(surface).connected_components():
            if component.count() >= 6:
                continue
            bounds = component.get_bounding_rects()[0]
            for y in range(bounds.top, bounds.bottom):
                for x in range(bounds.left, bounds.right):
                    if not component.get_at((x, y)):
                        continue
                    candidates = []
                    for other, other_surface in layers.items():
                        if other == name:
                            continue
                        for oy in range(max(0, y-2), min(CELL, y+3)):
                            for ox in range(max(0, x-2), min(CELL, x+3)):
                                if other_surface.get_at((ox, oy)).a:
                                    candidates.append(((ox-x)**2+(oy-y)**2, other))
                    if candidates:
                        target = min(candidates)[1]
                        layers[target].set_at((x, y), surface.get_at((x, y)))
                        surface.set_at((x, y), (0, 0, 0, 0))


def _restore_cloth_edges(layers):
    # Adjacency cleanup can place one-pixel tabard piping on the nearby cloak.
    # Keep these source material edges with the red panel as it swings.
    for y in range(55, 72):
        for x in range(26, 44):
            color = layers["cape"].get_at((x, y))
            if color.a and _is_cloth_trim(color):
                layers["back_cloth"].set_at((x, y), color)
                layers["cape"].set_at((x, y), (0, 0, 0, 0))


def _hidden_patch(layers, target, covers, bounds, accepts, max_distance=None):
    """Fill only occluded pixels with the nearest suitable source material."""
    layer = layers[target]
    samples = [(x, y, layer.get_at((x, y))) for y in range(CELL) for x in range(CELL)
               if layer.get_at((x, y)).a and accepts(x, y, layer.get_at((x, y)))]
    if not samples:
        return
    for y in range(bounds.top, bounds.bottom):
        for x in range(bounds.left, bounds.right):
            if layer.get_at((x, y)).a or not any(layers[name].get_at((x, y)).a for name in covers):
                continue
            sample = min(samples, key=lambda p: (p[0]-x)**2+(p[1]-y)**2)
            if max_distance is None or math.dist((x, y), sample[:2]) <= max_distance:
                layer.set_at((x, y), sample[2])


def _joint_caps(layers, base):
    # Each cap sits underneath its corresponding limb in ORDER. Copying the
    # exact original pixel also preserves reconstruction at every overlap.
    for name, center, radius in (
        ("torso", (37,41), 3), ("torso", (52,42), 3),
        ("free_upper", (32,52), 2), ("sword_upper", (55,52), 2),
        ("torso", (46,56), 3),
    ):
        for y in range(center[1]-radius, center[1]+radius+1):
            for x in range(center[0]-radius, center[0]+radius+1):
                if math.dist((x, y), center) <= radius and base.get_at((x, y)).a:
                    layers[name].set_at((x, y), base.get_at((x, y)))


def _split_legs(layers):
    for side, knee_y, ankle_y in (("near", 73, 86), ("far", 73, 86)):
        original = layers[f"{side}_leg"].copy()
        layers[f"{side}_leg"].fill((0, 0, 0, 0))
        for y in range(CELL):
            for x in range(CELL):
                color = original.get_at((x, y))
                if not color.a:
                    continue
                if y <= knee_y+1:
                    layers[f"{side}_leg"].set_at((x, y), color)
                if knee_y-1 <= y <= ankle_y+1:
                    layers[f"{side}_shin"].set_at((x, y), color)
                if y >= ankle_y-1:
                    layers[f"{side}_foot"].set_at((x, y), color)


def split_layers(base):
    """Return independent full-canvas pieces, preserving all source RGBA pixels."""
    if base.get_size() != (CELL, CELL):
        raise ValueError("Warrior layer source must be a 96 by 96 pixel surface")
    layers = {name: pygame.Surface((CELL, CELL), pygame.SRCALPHA) for name in ORDER}
    masks = _region_masks()
    for y in range(CELL):
        for x in range(CELL):
            color = base.get_at((x, y))
            if color.a:
                layers[_owner(x, y, color, masks)].set_at((x, y), color)
    _move_small_components(layers)
    _restore_cloth_edges(layers)
    _hidden_patch(layers, "cape", ("free_upper", "free_forearm"),
                  pygame.Rect(27, 44, 12, 22),
                  lambda x, y, color: _is_teal(color) and color.g > 35 and color.b > 40, 6)
    for side, bounds in (("far", pygame.Rect(36, 56, 9, 15)),
                         ("near", pygame.Rect(49, 56, 7, 15))):
        _hidden_patch(layers, f"{side}_leg", ("torso", "front_cloth", "back_cloth"),
                      bounds, lambda x, y, color: 58 <= y <= 71 and _is_trouser(color))
    _joint_caps(layers, base)
    _hidden_patch(layers, "torso", ("free_upper",), pygame.Rect(36, 38, 9, 8),
                  lambda x, y, color: 41 <= x <= 49 and 39 <= y <= 48 and not _is_teal(color))
    _hidden_patch(layers, "free_upper", ("free_forearm",), pygame.Rect(31, 47, 6, 8),
                  lambda x, y, color: 44 <= y <= 50 and not _is_teal(color))
    _split_legs(layers)
    return layers
