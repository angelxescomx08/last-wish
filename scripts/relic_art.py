"""One drawing per relic (Spanish name → function returning a 32×32 ``Canvas``).

Add a relic with ``@art("Nombre")``; ``generate_relic_sprites.py`` writes it. Each drawing
uses ``relic_kit`` shapes and ramps and ends with ``finish`` (dark outline).
"""
from __future__ import annotations

from relic_kit import *  # noqa: F401,F403

ART: dict = {}


def art(name: str):
    def register(fn):
        ART[name] = fn
        return fn
    return register

# --- relics (in the order of docs/reliquias.xlsx) --------------------------------------


@art("Anillo de Oro")
def gold_ring():
    cv = new()
    band = ring(16, 18, 10, 6.2)
    fill(cv, band, GOLD, base=0.6)
    shine(cv, band, WHITE, 0.35)
    gem = ellipse(16, 7.5, 4.2, 3.4)
    flat(cv, rect(13, 9, 19, 11), GOLD[1])              # setting
    fill(cv, gem, RED, base=0.7)
    dots(cv, [(14, 6), (15, 6)], WHITE)
    sparkle(cv, 25, 11)
    return finish(cv)


@art("Poción de Sangre")
def blood_potion():
    cv = new()
    flask = union(circle(16, 20, 9), rect(13, 5, 19, 12))
    fill(cv, flask, GLASS, base=0.75)
    liquid = minus(circle(16, 20, 8), rect(0, 0, 32, 15))
    fill(cv, liquid, BLOOD, base=0.65)
    flat(cv, rect(9, 15, 23, 15), RED[3])                # meniscus
    fill(cv, rect(12, 2, 20, 5), WOOD, base=0.6)          # cork
    dots(cv, [(11, 17), (11, 18), (12, 16)], WHITE)
    dots(cv, [(19, 22), (14, 25)], RED[3])                # bubbles
    return finish(cv)


@art("Amuleto de Vitalidad")
def vitality_amulet():
    cv = new()
    for i in range(9):                                   # chain
        x = 8 + i * 2
        cv.put(x, 3 + abs(4 - i) // 2, SILVER[2])
    line(cv, 8, 5, 12, 12, SILVER[1])
    line(cv, 24, 5, 20, 12, SILVER[1])
    heart = union(circle(12.5, 17, 5), circle(19.5, 17, 5), poly([(7.6, 18.5), (24.4, 18.5), (16, 28)]))
    fill(cv, heart, GOLD, base=0.6)
    inner = union(circle(13, 17.5, 3), circle(19, 17.5, 3), poly([(10, 18.5), (22, 18.5), (16, 25)]))
    fill(cv, inner, GREEN, base=0.7)
    dots(cv, [(12, 16), (13, 15)], GREEN[4])
    sparkle(cv, 24, 13)
    return finish(cv)


@art("Máscara del Ladrón")
def thief_mask():
    cv = new()
    mask = union(ellipse(10, 16, 8, 6), ellipse(22, 16, 8, 6), rect(10, 13, 22, 19))
    eyes = union(ellipse(10, 16, 3.2, 2.2), ellipse(22, 16, 3.2, 2.2))
    fill(cv, minus(mask, eyes), BLACK, base=0.6, slope=0.8)
    shine(cv, minus(mask, eyes), VIOLET[2], 0.4)
    flat(cv, rect(1, 14, 2, 15), BLACK[2])               # strap ends
    flat(cv, rect(29, 14, 30, 15), BLACK[2])
    line(cv, 4, 22, 2, 27, CLOTH_RED[2])                 # ribbon
    line(cv, 5, 22, 4, 28, CLOTH_RED[1])
    return finish(cv)


@art("Cicatriz")
def scar():
    cv = new()
    skin = [(120, 60, 50), (170, 98, 80), (210, 140, 112), (236, 180, 150), (252, 216, 190)]
    patch = ellipse(16, 16, 12, 10)
    fill(cv, patch, skin, base=0.6, slope=0.5)
    line(cv, 7, 23, 24, 8, BLOOD[2])                     # the scar
    line(cv, 8, 23, 25, 8, BLOOD[1])
    for t in range(4):                                   # stitches
        x, y = 10 + t * 4, 20 - t * 3.6
        line(cv, x - 1, y - 2, x + 1, y + 2, BONE[3])
    return finish(cv)


@art("Brazal de Guerra")
def war_bracer():
    cv = new()
    cuff = poly([(7, 8), (25, 6), (27, 24), (5, 26)])
    fill(cv, cuff, STEEL, base=0.6)
    for y0 in (11, 16, 21):                              # plates
        line(cv, 6, y0 + 1, 26, y0 - 1, STEEL[0])
    fill(cv, rect(5, 4, 27, 6), LEATHER, base=0.6)       # leather rims
    fill(cv, rect(4, 26, 28, 28), LEATHER, base=0.6)
    for x in (10, 22):
        fill(cv, circle(x, 13.5, 1.6), GOLD, base=0.8)   # rivets
        fill(cv, circle(x, 19, 1.6), GOLD, base=0.8)
    shine(cv, cuff, WHITE, 0.3)
    return finish(cv)


@art("Orbe de Fuego")
def fire_orb():
    cv = new()
    orb = circle(16, 14, 10)
    fill(cv, orb, [(70, 10, 10), (130, 24, 12), (190, 50, 16), (236, 100, 30), (255, 170, 70)],
         base=0.45, slope=0.9)
    flame = union(poly([(11, 20), (13, 10), (15, 15), (17, 6), (19, 13), (21, 9), (21, 20)]),
                  ellipse(16, 19, 5, 3))
    fill(cv, flame, FIRE, base=0.75, rim=False)
    fill(cv, ellipse(16, 18, 2.5, 2), [(255, 230, 150), (255, 250, 220), WHITE], base=0.8, rim=False)
    dots(cv, [(10, 8), (11, 7), (9, 9)], WHITE)
    stand = poly([(9, 28), (23, 28), (20, 23), (12, 23)])
    fill(cv, stand, BRONZE, base=0.6)
    cv.glow(16, 14, 15, FIRE[3], 0.3)
    return finish(cv)


@art("Corazón de Hierro")
def iron_heart():
    cv = new()
    heart = union(circle(11, 12, 7), circle(21, 12, 7), poly([(4.2, 14), (27.8, 14), (16, 28)]))
    fill(cv, heart, IRON, base=0.6, slope=0.8)
    for x, y in ((9, 10), (23, 10), (16, 22), (12, 18), (20, 18)):   # rivets
        cv.put(x, y, IRON[4])
        cv.put(x + 1, y + 1, IRON[0])
    line(cv, 16, 9, 16, 26, IRON[0])                     # welded seam
    shine(cv, heart, WHITE, 0.3)
    return finish(cv)


@art("Moneda de la Suerte")
def lucky_coin():
    cv = new()
    coin = circle(16, 16, 11)
    fill(cv, coin, GOLD, base=0.6)
    fill(cv, ring(16, 16, 11, 9), GOLD, base=0.4, rim=False)
    clover = union(circle(13.5, 13.5, 2.6), circle(18.5, 13.5, 2.6), circle(13.5, 18.5, 2.6),
                   circle(18.5, 18.5, 2.6))
    fill(cv, clover, GREEN, base=0.6, rim=False)
    line(cv, 17, 19, 20, 23, GREEN[1])
    sparkle(cv, 24, 8)
    return finish(cv)


@art("Herradura de Plata")
def silver_horseshoe():
    cv = new()
    top = minus(ring(16, 15, 11, 6.5), rect(0, 15.01, 32, 32))
    shoe = union(top, rect(5, 15, 9.5, 26), rect(22.5, 15, 27, 26))
    fill(cv, shoe, SILVER, base=0.6)
    for x, y in ((7, 18), (7, 22), (24, 18), (24, 22), (9, 9), (22, 9), (16, 6)):   # nail holes
        cv.put(x, y, SILVER[0])
    fill(cv, rect(4, 26, 10, 28), SILVER, base=0.4)      # heels
    fill(cv, rect(22, 26, 28, 28), SILVER, base=0.4)
    sparkle(cv, 26, 5)
    return finish(cv)


@art("Tótem Roto")
def broken_totem():
    cv = new()
    pole = minus(rect(10, 6, 22, 28), poly([(10, 6), (17, 6), (13, 11), (10, 9)]))
    fill(cv, pole, WOOD, base=0.55)
    face = rect(12, 13, 20, 22)
    fill(cv, face, [(90, 40, 30), (150, 60, 40), (200, 90, 50), (230, 140, 80), (250, 190, 130)], base=0.6)
    flat(cv, rect(13, 15, 14, 16), INK)                  # eyes
    flat(cv, rect(18, 15, 19, 16), INK)
    flat(cv, rect(14, 19, 18, 20), INK)                  # mouth
    line(cv, 17, 6, 21, 12, WOOD[0])                     # crack
    line(cv, 21, 12, 19, 16, WOOD[0])
    fill(cv, rect(8, 27, 24, 29), STONE, base=0.5)       # base
    for x, y in ((6, 6), (8, 4), (25, 8)):               # splinters
        cv.put(x, y, WOOD[2])
    return finish(cv)


@art("Piedra de Energía")
def energy_stone():
    cv = new()
    stone = poly([(16, 3), (25, 10), (24, 23), (16, 29), (8, 23), (7, 10)])
    fill(cv, stone, CYAN, base=0.6, slope=0.9)
    line(cv, 16, 3, 16, 29, CYAN[1])                     # facets
    line(cv, 7, 10, 16, 16, CYAN[2])
    line(cv, 25, 10, 16, 16, CYAN[1])
    bolt = poly([(17, 8), (12, 17), (16, 17), (14, 25), (21, 14), (17, 14), (19, 8)])
    fill(cv, bolt, [(255, 220, 90), (255, 240, 150), WHITE], base=0.7, rim=False)
    cv.glow(16, 16, 14, CYAN[3], 0.3)
    return finish(cv)


@art("Guante de Seda")
def silk_glove():
    cv = new()
    silk = [(120, 110, 150), (170, 160, 200), (210, 204, 236), (238, 234, 252), (255, 255, 255)]
    palm = union(ellipse(15, 19, 8, 8), rect(10, 22, 20, 29))
    fingers = union(capsule(9, 16, 9, 7, 2), capsule(13, 13, 13, 4, 2), capsule(17, 13, 17, 4, 2),
                    capsule(21, 15, 21, 7, 2), capsule(22, 20, 27, 15, 2))
    glove = union(palm, fingers)
    fill(cv, glove, silk, base=0.6)
    fill(cv, rect(9, 26, 21, 29), VIOLET, base=0.6)      # cuff
    line(cv, 11, 27, 19, 27, GOLD[3])
    return finish(cv)


@art("Botas Silenciosas")
def silent_boots():
    cv = new()
    boot = union(rect(7, 5, 16, 22), poly([(7, 18), (16, 17), (24, 20), (28, 23), (28, 27), (7, 27)]))
    fill(cv, boot, LEATHER, base=0.55)
    fill(cv, rect(6, 3, 17, 6), LEATHER, base=0.8)       # folded top
    fill(cv, rect(7, 26, 28, 28), [(40, 40, 50), (70, 70, 84), (100, 100, 116)], base=0.5)  # soft sole
    for y in (10, 14, 18):
        line(cv, 9, y, 14, y, LEATHER[1])                # laces
    dots(cv, [(30, 17), (29, 14), (31, 20)], (200, 200, 230))   # hush
    return finish(cv)


@art("Amuleto de Combate")
def combat_amulet():
    cv = new()
    line(cv, 9, 2, 13, 9, GOLD[2])
    line(cv, 23, 2, 19, 9, GOLD[2])
    disc = circle(16, 18, 10)
    fill(cv, disc, GOLD, base=0.6)
    fill(cv, circle(16, 18, 7), CLOTH_RED, base=0.6)
    blade = union(poly([(16, 11), (18, 22), (16, 25), (14, 22)]), rect(12, 21, 20, 22))
    fill(cv, blade, STEEL, base=0.75, rim=False)
    rot = rotate(poly([(16, 11), (18, 22), (16, 25), (14, 22)]), 16, 18, 90)
    fill(cv, rot, STEEL, base=0.55, rim=False)
    sparkle(cv, 25, 11)
    return finish(cv)


@art("Hilo de Araña")
def spider_thread():
    cv = new()
    import math as _m
    for k in range(8):                                   # web spokes (no outline: fine threads)
        a = _m.radians(k * 45 + 10)
        line(cv, 16, 16, 16 + 14 * _m.cos(a), 16 + 14 * _m.sin(a), SILVER[3], solid=False)
    for r in (5, 9.5, 13.5):                             # web rings
        for k in range(60):
            a = _m.radians(k * 6)
            cv.put(round(16 + r * _m.cos(a)), round(16 + r * _m.sin(a)), SILVER[2], solid=False)
    for dx in (-1, 1):                                   # legs
        for i, dy in enumerate((-2, 0, 2, 4)):
            line(cv, 16 + dx * 3, 16 + dy, 16 + dx * (9 - abs(i - 1)), 13 + dy * 2, BLACK[2])
    body = union(circle(16, 19, 4.2), circle(16, 13, 2.8))
    fill(cv, body, VIOLET[:1] + BLACK[1:], base=0.7)
    cv.put(15, 12, RED[3])
    cv.put(17, 12, RED[3])
    flat(cv, rect(15, 18, 16, 20), RED[2])               # mark on the back
    return finish(cv)


@art("Llave Maestra")
def master_key():
    cv = new()
    bow = minus(circle(10, 10, 7), circle(10, 10, 3.2))
    fill(cv, bow, GOLD, base=0.6)
    shaft = capsule(14, 14, 26, 26, 1.8)
    fill(cv, shaft, GOLD, base=0.55)
    teeth = union(rect(20, 24, 22, 29), rect(24, 20, 29, 22), rect(23, 26, 25, 28))
    fill(cv, teeth, GOLD, base=0.45)
    fill(cv, circle(10, 10, 1.5), CLOTH_RED, base=0.7)
    sparkle(cv, 4, 4)
    return finish(cv)


@art("Interés Compuesto")
def compound_interest():
    cv = new()
    for i, (x, h) in enumerate(((5, 6), (12, 12), (19, 18))):   # growing coin stacks
        for k in range(h // 3):
            y = 28 - k * 3
            fill(cv, ellipse(x + 3, y, 4, 1.8), GOLD, base=0.55 + 0.05 * (k % 2))
    shaft = capsule(4, 15, 22, 5, 1.3)
    head = poly([(19, 2), (29, 2), (26, 11)])
    fill(cv, union(shaft, head), GREEN, base=0.7)
    return finish(cv)


@art("Escudo Espectral")
def spectral_shield():
    cv = new()
    ghost = [(60, 90, 140), (90, 140, 200), (140, 200, 240), (200, 240, 255), (240, 255, 255)]
    shield = union(rect(6, 4, 26, 16), poly([(6, 16), (26, 16), (16, 29)]))
    fill(cv, shield, ghost, base=0.65)
    fill(cv, minus(shield, union(rect(9, 7, 23, 16), poly([(9, 16), (23, 16), (16, 25)]))), SILVER,
         base=0.5, rim=False)
    eye = ellipse(16, 14, 4, 2.5)
    fill(cv, eye, [(20, 40, 80), (60, 120, 200), WHITE], base=0.7, rim=False)
    cv.put(16, 14, INK)
    cv.glow(16, 15, 14, ghost[3], 0.35)
    return finish(cv)


@art("Trébol de Siete Hojas")
def seven_leaf_clover():
    cv = new()
    import math as _m
    leaves = []
    for k in range(7):
        a = _m.radians(-90 + k * 360 / 7)
        leaves.append(circle(16 + 6.5 * _m.cos(a), 13 + 6.5 * _m.sin(a), 3.6))
    clover = union(*leaves, circle(16, 13, 3))
    fill(cv, clover, GREEN, base=0.6)
    for k in range(7):
        a = _m.radians(-90 + k * 360 / 7)
        line(cv, 16, 13, 16 + 5 * _m.cos(a), 13 + 5 * _m.sin(a), GREEN[1])
    stem = capsule(16, 18, 20, 29, 1.1)
    fill(cv, stem, GREEN, base=0.4)
    sparkle(cv, 27, 4)
    sparkle(cv, 4, 20)
    return finish(cv)


@art("Panacea")
def panacea():
    cv = new()
    bottle = union(ellipse(16, 20, 8, 8), rect(13, 6, 19, 13))
    fill(cv, bottle, GLASS, base=0.75)
    liquid = minus(ellipse(16, 20, 7, 7), rect(0, 0, 32, 16))
    fill(cv, liquid, GOLD, base=0.7)
    fill(cv, rect(12, 3, 20, 6), GOLD, base=0.5)          # golden stopper
    cross = union(rect(14.5, 17, 17.5, 26), rect(11.5, 20, 20.5, 23))
    flat(cv, cross, WHITE)
    dots(cv, [(10, 16), (10, 17)], WHITE)
    sparkle(cv, 26, 9)
    sparkle(cv, 5, 24)
    return finish(cv)


@art("Fuente Eterna")
def eternal_fount():
    cv = new()
    basin = union(ellipse(16, 23, 12, 4), rect(5, 19, 27, 23))
    fill(cv, basin, STONE, base=0.6)
    fill(cv, ellipse(16, 20, 10, 2.5), BLUE, base=0.7, rim=False)
    fill(cv, rect(14, 9, 18, 19), STONE, base=0.6)          # pillar
    fill(cv, ellipse(16, 9, 5, 2), STONE, base=0.7)
    for i, (x0, x1) in enumerate(((15, 8), (17, 24))):     # arcs of water
        for t in range(10):
            u = t / 9
            x = x0 + (x1 - x0) * u
            y = 7 - 5 * (1 - (2 * u - 1) ** 2) + 12 * u * u
            cv.put(round(x), round(y), BLUE[3], solid=False)
    flat(cv, rect(15, 2, 17, 7), BLUE[3], solid=False)
    cv.glow(16, 12, 12, BLUE[3], 0.25)
    return finish(cv)


@art("Ankh")
def ankh():
    cv = new()
    loop = minus(ellipse(16, 9, 6, 7), ellipse(16, 9.5, 2.6, 3.8))
    body = union(loop, rect(14, 15, 18, 29), rect(6, 15, 26, 18))
    fill(cv, body, GOLD, base=0.6)
    shine(cv, body, WHITE, 0.35)
    fill(cv, circle(16, 16.5, 1.4), BLUE, base=0.8, rim=False)
    sparkle(cv, 26, 6)
    return finish(cv)


@art("Espejo Singular")
def singular_mirror():
    cv = new()
    frame = ellipse(16, 13, 10, 11)
    fill(cv, frame, VIOLET, base=0.55)
    glass = ellipse(16, 13, 7, 8)
    fill(cv, glass, GLASS, base=0.7)
    line(cv, 12, 9, 19, 17, WHITE, solid=False)
    line(cv, 13, 8, 15, 10, WHITE, solid=False)
    fill(cv, rect(14, 23, 18, 29), VIOLET, base=0.5)       # handle
    fill(cv, circle(16, 3, 1.6), GOLD, base=0.8)
    sparkle(cv, 25, 6)
    return finish(cv)


@art("Reloj Roto")
def broken_clock():
    cv = new()
    case = circle(16, 17, 11)
    fill(cv, case, BRONZE, base=0.55)
    face = circle(16, 17, 8.5)
    fill(cv, face, PAPER, base=0.75, rim=False)
    for x, y in ((16, 10), (23, 17), (16, 24), (9, 17)):
        cv.put(x, y, INK)
    line(cv, 16, 17, 16, 12, INK)                          # hands
    line(cv, 16, 17, 20, 19, INK)
    line(cv, 10, 11, 14, 16, (90, 90, 100))                # crack in the glass
    line(cv, 14, 16, 13, 21, (90, 90, 100))
    fill(cv, rect(14, 3, 18, 6), BRONZE, base=0.6)         # crown
    line(cv, 26, 8, 29, 5, BRONZE[2])                      # sprung spring
    line(cv, 28, 9, 30, 11, BRONZE[2])
    return finish(cv)


@art("Colmillo de Hierro")
def iron_fang():
    cv = new()
    fang = poly([(10, 4), (22, 4), (21, 12), (17, 28), (14, 27), (12, 13)])
    fill(cv, fang, IRON, base=0.6, slope=0.9)
    fill(cv, rect(9, 3, 23, 7), BRONZE, base=0.6)          # iron cap band
    line(cv, 15, 9, 15, 24, IRON[4], solid=False)
    flat(cv, rect(16, 25, 17, 27), BLOOD[3])               # blood at the tip
    cv.put(17, 29, BLOOD[2])
    return finish(cv)


@art("Venda Empapada")
def soaked_bandage():
    cv = new()
    roll = ellipse(13, 15, 8, 9)
    fill(cv, roll, PAPER, base=0.7)
    fill(cv, ellipse(13, 15, 3, 3.5), PAPER, base=0.3, rim=False)
    tail = poly([(19, 18), (29, 22), (27, 28), (16, 23)])
    fill(cv, tail, PAPER, base=0.6)
    for x, y, r in ((10, 9, 2.4), (22, 23, 2.2), (16, 20, 1.6)):   # blood stains
        fill(cv, circle(x, y, r), BLOOD, base=0.6, rim=False)
    cv.put(27, 30, BLOOD[2])
    return finish(cv)


@art("Copa de Sangre")
def blood_cup():
    cv = new()
    bowl = minus(ellipse(16, 10, 10, 8), rect(0, 0, 32, 7))
    fill(cv, bowl, GOLD, base=0.6)
    fill(cv, ellipse(16, 8, 9, 2.4), BLOOD, base=0.6, rim=False)   # blood surface
    fill(cv, rect(14, 17, 18, 23), GOLD, base=0.55)
    fill(cv, ellipse(16, 26, 7, 2.5), GOLD, base=0.55)
    fill(cv, circle(16, 13, 1.6), RED, base=0.8, rim=False)
    cv.put(22, 11, BLOOD[2])                               # a drip
    cv.put(22, 12, BLOOD[2])
    return finish(cv)


@art("Estandarte Desgarrado")
def torn_banner():
    cv = new()
    fill(cv, rect(5, 2, 7, 30), WOOD, base=0.6)            # pole
    fill(cv, circle(6, 2, 1.8), GOLD, base=0.8)
    flag = poly([(8, 4), (27, 6), (25, 12), (28, 17), (22, 18), (24, 24), (17, 21), (14, 26), (8, 22)])
    fill(cv, flag, CLOTH_RED, base=0.55)
    emblem = poly([(16, 8), (20, 13), (16, 18), (12, 13)])
    fill(cv, emblem, GOLD, base=0.7, rim=False)
    cv.put(16, 13, CLOTH_RED[1])
    return finish(cv)


@art("Corazón de Titán")
def titan_heart():
    cv = new()
    heart = union(circle(11, 12, 7.5), circle(21, 12, 7.5), poly([(3.6, 14), (28.4, 14), (16, 29)]))
    fill(cv, heart, BLOOD, base=0.6, slope=0.8)
    plate = minus(heart, union(circle(11, 12, 5), circle(21, 12, 5), poly([(6, 14), (26, 14), (16, 26)])))
    fill(cv, plate, STEEL, base=0.55, rim=False)
    line(cv, 16, 8, 16, 24, BLOOD[0])
    dots(cv, [(9, 9), (10, 8)], WHITE)
    cv.glow(16, 15, 14, RED[2], 0.2)
    return finish(cv)


@art("Saco de Trapos")
def rag_sack():
    cv = new()
    sack = union(ellipse(16, 20, 11, 9), poly([(11, 12), (21, 12), (19, 6), (13, 6)]))
    fill(cv, sack, EARTH, base=0.6)
    for x, y in ((9, 18), (20, 23), (14, 25)):                 # patches
        fill(cv, rect(x, y, x + 4, y + 3), CLOTH_RED if x == 9 else BLUE, base=0.5, rim=False)
        cv.put(x + 1, y, PAPER[3])
    fill(cv, rect(11, 10, 21, 12), LEATHER, base=0.4)          # tied neck
    line(cv, 13, 6, 9, 3, EARTH[2])
    line(cv, 19, 6, 23, 3, EARTH[2])
    return finish(cv)


@art("Bolsa de Dagas")
def dagger_pouch():
    cv = new()
    for i, x in enumerate((10, 15, 20)):                       # daggers sticking out
        fill(cv, poly([(x, 3 + i % 2 * 2), (x + 2, 6), (x + 2, 14), (x - 2, 14), (x - 2, 6)]), STEEL,
             base=0.7)
        fill(cv, rect(x - 3, 13, x + 3, 14), GOLD, base=0.6, rim=False)
    pouch = union(rect(6, 15, 26, 27), ellipse(16, 27, 10, 3))
    fill(cv, pouch, LEATHER, base=0.55)
    fill(cv, rect(6, 15, 26, 17), LEATHER, base=0.3)
    fill(cv, circle(16, 21, 1.6), BRONZE, base=0.8)
    return finish(cv)


@art("Broche de Evasión")
def evasion_brooch():
    cv = new()
    brooch = ellipse(16, 16, 11, 9)
    fill(cv, brooch, SILVER, base=0.6)
    fill(cv, ellipse(16, 16, 6.5, 5), CYAN, base=0.7)
    for k, (x, y) in enumerate(((7, 16), (25, 16), (16, 8), (16, 24))):
        fill(cv, circle(x, y, 1.3), GOLD, base=0.8)
    line(cv, 3, 26, 10, 22, SILVER[2])                         # pin
    cv.put(14, 13, WHITE)
    cv.put(15, 13, WHITE)
    for x in (27, 29):                                         # dodge streaks
        line(cv, x, 12, x, 20, CYAN[3], solid=False)
    return finish(cv)


@art("Cuchillo Arrojadizo")
def throwing_knife():
    cv = new()
    blade = poly([(26, 4), (28, 6), (15, 19), (12, 17)])
    fill(cv, blade, STEEL, base=0.7)
    fill(cv, poly([(13, 16), (16, 19), (9, 26), (6, 23)]), LEATHER, base=0.55)   # wrapped grip
    for k in range(3):
        cv.put(9 + k * 2, 23 - k * 2, LEATHER[0])
    fill(cv, circle(6, 26, 2), BRONZE, base=0.7)               # ring
    for k in range(3):                                         # motion lines
        line(cv, 3 + k * 3, 10 + k * 2, 7 + k * 3, 6 + k * 2, SILVER[1], solid=False)
    return finish(cv)


@art("Pañuelo del Duelista")
def duelist_scarf():
    cv = new()
    cloth = poly([(5, 7), (27, 7), (16, 26)])
    fill(cv, cloth, CLOTH_RED, base=0.55)
    tails = union(poly([(5, 7), (2, 15), (4, 16), (8, 9)]), poly([(27, 7), (30, 14), (28, 15), (24, 9)]))
    fill(cv, tails, CLOTH_RED, base=0.4)
    fill(cv, circle(16, 6, 2.6), CLOTH_RED, base=0.75)         # knot
    for t in range(9):                                         # gold hem
        u = t / 8
        cv.put(round(7 + 9 * u), round(9 + 15 * u), GOLD[3])
        cv.put(round(25 - 9 * u), round(9 + 15 * u), GOLD[3])
    fill(cv, poly([(16, 12), (18, 15), (16, 18), (14, 15)]), GOLD, base=0.8, rim=False)
    return finish(cv)


@art("Garfio")
def grappling_hook():
    cv = new()
    import math as _m
    for k in range(18):                                        # rope
        cv.put(round(5 + k * 0.6 + _m.sin(k * 0.9)), 2 + k, EARTH[2] if k % 2 else EARTH[3])
    shank = rect(14, 12, 18, 22)
    fill(cv, shank, IRON, base=0.6)
    fill(cv, circle(16, 11, 2.6), IRON, base=0.7)
    for side in (-1, 1):                                       # curved prongs
        fill(cv, minus(ring(16 + side * 6, 22, 6, 3.2), rect(0, 0, 32, 22),
                       rect(0, 0, 16, 32) if side > 0 else rect(16, 0, 32, 32)), IRON, base=0.55)
        fill(cv, poly([(16 + side * 12, 22), (16 + side * 13.5, 16), (16 + side * 9, 21)]), IRON, base=0.7)
    fill(cv, poly([(14, 22), (18, 22), (16, 28)]), IRON, base=0.5)
    return finish(cv)


@art("Vaina Afilada")
def sharp_sheath():
    cv = new()
    sheath = rotate(union(rect(14, 9, 18, 26), poly([(14, 26), (18, 26), (16, 29)])), 16, 16, 35)
    fill(cv, sheath, LEATHER, base=0.55)
    hilt = rotate(union(rect(15, 3, 17, 8), rect(12, 8, 20, 9.5)), 16, 16, 35)
    fill(cv, hilt, GOLD, base=0.7)
    band = rotate(rect(14, 16, 18, 17.5), 16, 16, 35)
    fill(cv, band, BRONZE, base=0.8, rim=False)
    for x, y in ((24, 22), (26, 19), (22, 25)):
        sparkle(cv, x, y)
    return finish(cv)


@art("Frasco de Veneno")
def poison_vial():
    cv = new()
    vial = union(rect(11, 9, 21, 27), ellipse(16, 27, 5, 2))
    fill(cv, vial, GLASS, base=0.75)
    liquid = union(rect(12, 15, 20, 27), ellipse(16, 27, 4, 1.5))
    fill(cv, liquid, POISON, base=0.7, rim=False)
    fill(cv, rect(12, 5, 20, 9), WOOD, base=0.6)
    skull = union(circle(16, 19, 2.6), rect(15, 21, 17, 23))
    flat(cv, skull, BONE[3])
    cv.put(15, 19, INK)
    cv.put(17, 19, INK)
    for x, y in ((22, 3), (24, 6), (20, 1)):                   # fumes
        cv.put(x, y, POISON[3], solid=False)
    return finish(cv)


@art("Cinta Roja")
def crimson_ribbon():
    cv = new()
    loops = union(ellipse(9, 11, 7, 5), ellipse(23, 11, 7, 5))
    fill(cv, minus(loops, union(ellipse(9, 11, 3, 2), ellipse(23, 11, 3, 2))), CLOTH_RED, base=0.6)
    tails = union(poly([(14, 13), (17, 13), (11, 28), (7, 26)]), poly([(15, 13), (18, 13), (25, 26), (21, 28)]))
    fill(cv, tails, CLOTH_RED, base=0.45)
    fill(cv, ellipse(16, 12, 3, 3), CLOTH_RED, base=0.75)
    return finish(cv)


@art("Bolsillo Roto")
def torn_pocket():
    cv = new()
    pocket = poly([(5, 6), (27, 6), (27, 20), (16, 28), (5, 20)])
    fill(cv, pocket, [(40, 50, 70), (60, 74, 100), (86, 102, 134), (120, 136, 166), (160, 172, 200)], base=0.55)
    hole = poly([(14, 18), (19, 17), (21, 22), (16, 25), (12, 22)])
    flat(cv, hole, INK)
    for x, y in ((13, 17), (20, 21), (17, 25)):                # frayed threads
        cv.put(x, y, PAPER[2])
    line(cv, 5, 9, 27, 9, (160, 172, 200))                     # seam
    fill(cv, ellipse(16, 29.5, 2.5, 1.5), GOLD, base=0.7)      # a coin falling out
    return finish(cv)


@art("Colmillo de Víbora")
def viper_fang():
    cv = new()
    for ox, scale in ((0, 1.0), (11, 0.7)):                      # two curved fangs
        f = poly([(6 + ox, 4), (6 + ox + 10 * scale, 4), (6 + ox + 8 * scale, 4 + 10 * scale),
                  (6 + ox + 3 * scale, 4 + 22 * scale), (6 + ox + 1 * scale, 4 + 20 * scale),
                  (6 + ox + 1 * scale, 4 + 10 * scale)])
        fill(cv, f, BONE, base=0.65)
    fill(cv, rect(4, 2, 27, 5), [(40, 70, 30), (60, 110, 40), (90, 150, 60)], base=0.5)   # jaw
    for x, y in ((9, 27), (9, 30), (18, 22)):
        fill(cv, circle(x + 0.5, y, 1.3), POISON, base=0.8, rim=False)
    return finish(cv)


@art("Daga Partida")
def split_dagger():
    cv = new()
    hilt = union(rect(14, 22, 18, 29), rect(10, 20, 22, 22))
    fill(cv, hilt, GOLD, base=0.6)
    fill(cv, rect(14, 23, 18, 28), LEATHER, base=0.6, rim=False)
    left = poly([(11, 19), (15, 19), (12, 3)])
    right = poly([(17, 19), (21, 19), (20, 3)])
    fill(cv, left, STEEL, base=0.75)
    fill(cv, right, STEEL, base=0.6)
    cv.glow(16, 10, 6, VIOLET[3], 0.4)
    return finish(cv)


@art("Escalera")
def stairway():
    cv = new()
    for k in range(4):                                         # rising stone steps
        x0, y0 = 4 + k * 6, 24 - k * 6
        fill(cv, rect(x0, y0, x0 + 6 + (3 - k) * 0, 28), STONE, base=0.55 + 0.05 * k)
        line(cv, x0, y0, x0 + 6, y0, STONE[4], solid=False)
    for k, x in enumerate((6, 12, 18)):                        # rising mana gems
        fill(cv, poly([(x + 1, 19 - k * 6), (x + 3, 21 - k * 6), (x + 1, 23 - k * 6), (x - 1, 21 - k * 6)]),
             BLUE, base=0.8, rim=False)
    sparkle(cv, 27, 3)
    return finish(cv)


@art("Cartas de Diamante")
def diamond_cards():
    cv = new()
    back = rotate(rect(6, 6, 18, 24), 12, 15, -12)
    fill(cv, back, GOLD, base=0.5)
    front = rotate(rect(13, 5, 25, 23), 19, 14, 10)
    fill(cv, front, ICE, base=0.65)
    gem = poly([(19, 7), (24, 12), (19, 20), (14, 12)])
    fill(cv, gem, BLUE, base=0.3, slope=0.8, rim=False)
    line(cv, 14, 12, 24, 12, WHITE, solid=False)
    line(cv, 19, 7, 17, 12, ICE[3], solid=False)
    sparkle(cv, 26, 4, size=2)
    sparkle(cv, 5, 26)
    return finish(cv)


@art("Sello del Coleccionista")
def collector_seal():
    cv = new()
    card = rect(9, 3, 23, 22)
    fill(cv, card, PAPER, base=0.65)
    fill(cv, rect(11, 5, 21, 12), VIOLET, base=0.6, rim=False)
    line(cv, 11, 15, 21, 15, PAPER[1], solid=False)
    line(cv, 11, 18, 19, 18, PAPER[1], solid=False)
    seal = circle(20, 23, 6.5)                                 # wax seal
    fill(cv, seal, CLOTH_RED, base=0.55)
    fill(cv, poly([(20, 19), (22, 23), (20, 27), (18, 23)]), GOLD, base=0.8, rim=False)
    fill(cv, poly([(15, 27), (18, 29), (16, 31), (13, 30)]), CLOTH_RED, base=0.4)   # wax drip
    return finish(cv)


@art("Pieza Única")
def unique_piece():
    cv = new()
    piece = union(rect(8, 9, 24, 25), circle(16, 7, 3.5), circle(26, 17, 3.5))
    hole = circle(6, 17, 3.2)
    fill(cv, minus(piece, hole), VIOLET, base=0.6)
    fill(cv, poly([(16, 12), (20, 17), (16, 22), (12, 17)]), GOLD, base=0.8, rim=False)
    sparkle(cv, 27, 5, size=2)
    return finish(cv)


@art("Tijeras del Sastre")
def tailor_scissors():
    cv = new()
    blade_a = poly([(14, 15), (27, 3), (28, 5), (17, 17)])
    blade_b = poly([(14, 17), (25, 27), (23, 28), (12, 19)])
    fill(cv, blade_a, STEEL, base=0.75)
    fill(cv, blade_b, STEEL, base=0.6)
    for cy in (9, 23):                                          # handles
        fill(cv, minus(circle(7, cy, 4.6), circle(7, cy, 2.4)), CLOTH_RED, base=0.6)
    line(cv, 10, 11, 14, 15, CLOTH_RED[2])
    line(cv, 10, 21, 13, 18, CLOTH_RED[2])
    fill(cv, circle(15, 16, 1.6), GOLD, base=0.8)               # pivot
    for k in range(3):                                          # cut thread
        cv.put(28 - k, 16 + k, PAPER[3], solid=False)
    return finish(cv)


@art("Piedra de Afilar")
def whetstone():
    cv = new()
    stone = poly([(4, 18), (24, 12), (28, 16), (8, 23)])
    fill(cv, stone, STONE, base=0.6)
    fill(cv, poly([(4, 18), (24, 12), (25, 13), (5, 19)]), STONE, base=0.85, rim=False)
    blade = poly([(10, 4), (12, 3), (20, 13), (18, 14)])
    fill(cv, blade, STEEL, base=0.75)
    for x, y in ((21, 12), (23, 10), (19, 9)):                 # sparks
        cv.put(x, y, ORANGE[3], solid=False)
    sparkle(cv, 24, 8)
    return finish(cv)


@art("Capa Raída")
def ragged_cape():
    cv = new()
    cape = poly([(9, 4), (23, 4), (26, 22), (23, 27), (20, 23), (17, 28), (14, 23), (10, 27), (6, 22)])
    fill(cv, cape, [(50, 40, 60), (80, 64, 92), (112, 92, 124), (146, 124, 156), (180, 160, 190)], base=0.55)
    fill(cv, rect(8, 3, 24, 6), LEATHER, base=0.6)              # collar
    fill(cv, circle(16, 5, 1.8), BRONZE, base=0.8)
    for x, y in ((12, 14), (20, 18)):                           # holes
        flat(cv, rect(x, y, x + 1, y + 1), INK)
    return finish(cv)


@art("Vela Votiva")
def votive_candle():
    cv = new()
    wax = rect(11, 13, 21, 27)
    fill(cv, wax, BONE, base=0.65)
    fill(cv, ellipse(16, 27, 9, 2.5), BRONZE, base=0.5)          # dish
    for x, y in ((12, 15), (12, 16), (20, 17)):                 # drips
        cv.put(x, y, BONE[4])
    line(cv, 16, 10, 16, 13, INK)
    flame = union(ellipse(16, 7.5, 2.6, 3.8), poly([(14, 7), (18, 7), (16, 1)]))
    fill(cv, flame, FIRE, base=0.75, rim=False)
    cv.glow(16, 7, 9, FIRE[3], 0.35)
    return finish(cv)


@art("Bandera Blanca")
def white_flag():
    cv = new()
    fill(cv, rect(6, 3, 8, 30), WOOD, base=0.6)
    flag = poly([(9, 4), (26, 6), (23, 11), (27, 16), (9, 17)])
    fill(cv, flag, [(150, 150, 160), (200, 200, 210), (236, 236, 242), (250, 250, 252), WHITE], base=0.55)
    fill(cv, circle(7, 3, 1.6), GOLD, base=0.8)
    return finish(cv)


@art("Diente de León")
def dandelion():
    cv = new()
    import math as _m
    stem = capsule(16, 16, 15, 30, 0.9)
    fill(cv, stem, GREEN, base=0.5)
    fill(cv, poly([(15, 24), (9, 21), (15, 27)]), GREEN, base=0.6)
    for k in range(16):                                         # seed head
        a = _m.radians(k * 22.5)
        x, y = 16 + 8 * _m.cos(a), 11 + 8 * _m.sin(a)
        line(cv, 16, 11, x, y, BONE[2], solid=False)
        cv.put(round(x), round(y), WHITE)
    fill(cv, circle(16, 11, 2), EARTH, base=0.6)
    for x, y in ((27, 4), (29, 7)):                             # seeds flying away
        cv.put(x, y, WHITE, solid=False)
    return finish(cv)


@art("Lámpara de Aceite")
def oil_lamp():
    cv = new()
    body = union(ellipse(15, 21, 10, 5), poly([(22, 19), (29, 16), (29, 18), (23, 23)]))
    fill(cv, body, BRONZE, base=0.6)
    handle = minus(ellipse(5, 19, 4, 4), ellipse(5, 19, 2, 2))
    fill(cv, handle, BRONZE, base=0.5)
    fill(cv, ellipse(15, 26, 6, 1.6), BRONZE, base=0.4)
    fill(cv, ellipse(15, 17, 4, 1.6), BRONZE, base=0.8)
    flame = union(ellipse(28, 12, 2, 3), poly([(26, 12), (30, 12), (28, 6)]))
    fill(cv, flame, FIRE, base=0.75, rim=False)
    cv.glow(28, 11, 7, FIRE[3], 0.35)
    return finish(cv)


@art("Fruta Silvestre")
def wild_fruit():
    cv = new()
    for x, y, r in ((11, 18, 5.5), (20, 17, 5), (16, 24, 5.5)):  # berries
        fill(cv, circle(x, y, r), [(70, 16, 60), (120, 30, 90), (176, 54, 120), (220, 100, 160), (250, 170, 210)],
             base=0.6)
        cv.put(int(x - r / 2), int(y - r / 2), WHITE)
    leaf = poly([(16, 11), (24, 4), (26, 7), (19, 12)])
    fill(cv, leaf, GREEN, base=0.65)
    line(cv, 16, 12, 15, 7, EARTH[1])
    return finish(cv)


@art("Antídoto")
def antidote():
    cv = new()
    vial = union(ellipse(16, 21, 7, 7), rect(13, 7, 19, 15))
    fill(cv, vial, GLASS, base=0.75)
    fill(cv, minus(ellipse(16, 21, 6, 6), rect(0, 0, 32, 18)), CYAN, base=0.7, rim=False)
    fill(cv, rect(12, 4, 20, 7), CLOTH_RED, base=0.6)
    leaf = poly([(20, 14), (28, 7), (28, 12), (23, 16)])       # herb tied to the neck
    fill(cv, leaf, GREEN, base=0.65)
    line(cv, 12, 9, 20, 11, PAPER[2])
    dots(cv, [(11, 18), (11, 19)], WHITE)
    return finish(cv)


@art("Bolsa Agujereada")
def leaky_bag():
    cv = new()
    bag = union(ellipse(15, 19, 9, 9), poly([(10, 11), (20, 11), (18, 7), (12, 7)]))
    fill(cv, bag, LEATHER, base=0.55)
    fill(cv, rect(10, 9, 20, 11), CLOTH_RED, base=0.5)
    fill(cv, ellipse(18, 24, 2.5, 2), BLACK, base=0.2, rim=False)   # the hole
    for x, y in ((22, 27), (25, 29), (27, 26)):                     # coins falling out
        fill(cv, circle(x, y, 1.8), GOLD, base=0.8)
    return finish(cv)


@art("Cantimplora")
def canteen():
    cv = new()
    fill(cv, circle(16, 18, 10), [(40, 60, 50), (70, 98, 76), (100, 132, 98), (140, 168, 126), (190, 210, 170)],
         base=0.5)
    fill(cv, ring(16, 18, 10, 8.4), LEATHER, base=0.5)
    fill(cv, rect(14, 4, 18, 9), STEEL, base=0.6)
    fill(cv, rect(13, 2, 19, 4), CLOTH_RED, base=0.6)
    line(cv, 6, 12, 2, 3, LEATHER[2])
    line(cv, 26, 12, 30, 3, LEATHER[2])
    shine(cv, circle(16, 18, 8))
    return finish(cv)


@art("Vale de Descuento")
def voucher():
    cv = new()
    ticket = rotate(minus(rect(4, 10, 28, 22), union(circle(4, 16, 2.5), circle(28, 16, 2.5))), 16, 16, -12)
    fill(cv, ticket, PAPER, base=0.65)
    for i in range(-5, 6, 2):
        cv.put(16 + i // 3, 16 + i, PAPER[1])                # perforation
    fill(cv, rotate(circle(10, 15, 2.5), 16, 16, -12), RED, base=0.6)
    for x, y in ((19, 14), (23, 13), (20, 18), (24, 17)):
        cv.put(x, y, INK)
    return finish(cv)


@art("Cuerno de Guerra")
def war_horn():
    cv = new()
    horn = minus(minus(circle(16, 24, 15), circle(16, 27, 12.5)), rect(0, 22, 32, 32))
    bell = poly([(24, 10), (30, 14), (29, 22), (25, 21)])
    fill(cv, union(horn, bell), BONE, base=0.6)
    fill(cv, ellipse(28, 18, 1.6, 3.6), BLACK, base=0.2, rim=False)
    for x in (10, 16, 22):
        line(cv, x, 9, x, 13, BRONZE[2])
    fill(cv, circle(3, 21, 1.8), BRONZE, base=0.7)
    return finish(cv)


@art("Saco de Arena")
def sandbag():
    cv = new()
    fill(cv, ellipse(16, 20, 11, 8), [(90, 70, 40), (130, 104, 64), (170, 140, 92), (204, 176, 124), (232, 210, 160)],
         base=0.5)
    fill(cv, poly([(12, 12), (20, 12), (22, 7), (10, 7)]), [(90, 70, 40), (130, 104, 64), (170, 140, 92),
                                                          (204, 176, 124), (232, 210, 160)], base=0.6)
    fill(cv, rect(11, 11, 21, 13), LEATHER, base=0.4)
    for x, y in ((8, 28), (11, 29), (24, 28)):
        cv.put(x, y, (220, 196, 140))
    return finish(cv)


@art("Ficha de Ajedrez")
def chess_piece():
    cv = new()
    piece = union(circle(16, 7, 3.5), poly([(13, 10), (19, 10), (21, 22), (11, 22)]), rect(8, 22, 24, 27))
    fill(cv, piece, [(30, 26, 34), (56, 50, 64), (90, 82, 100), (130, 122, 140), (180, 172, 190)], base=0.5)
    fill(cv, rect(10, 13, 22, 15), GOLD, base=0.7)
    fill(cv, rect(7, 26, 25, 28), GOLD, base=0.55)
    return finish(cv)


@art("Pergamino Viejo")
def old_scroll():
    cv = new()
    fill(cv, rect(8, 7, 24, 25), PAPER, base=0.55)
    fill(cv, capsule(5, 6, 27, 6, 2.5), [(110, 80, 50), (150, 116, 76), (190, 154, 104), (220, 190, 140),
                                          (240, 220, 180)], base=0.6)
    fill(cv, capsule(5, 26, 27, 26, 2.5), [(110, 80, 50), (150, 116, 76), (190, 154, 104), (220, 190, 140),
                                            (240, 220, 180)], base=0.5)
    for y in (11, 14, 17, 20):
        line(cv, 11, y, 21 - (y % 3), y, EARTH[1], solid=False)
    fill(cv, circle(20, 22, 2), RED, base=0.6)
    return finish(cv)


@art("Pila Ordenada")
def tidy_pile():
    cv = new()
    for i, c in enumerate((BLUE, GREEN, RED, GOLD)):
        y = 24 - i * 4
        fill(cv, rect(7 + i % 2, y - 3, 25 + i % 2, y + 1), PAPER, base=0.55 + i * 0.05)
        line(cv, 9 + i % 2, y - 1, 23 + i % 2, y - 1, c[2])
    fill(cv, rect(9, 5, 23, 9), PAPER, base=0.8)
    fill(cv, circle(16, 7, 1.6), RED, base=0.6)
    return finish(cv)


@art("Vendas del Monje")
def monk_wraps():
    cv = new()
    roll = circle(13, 18, 8)
    fill(cv, roll, PAPER, base=0.65)
    fill(cv, ring(13, 18, 4.5, 2.5), PAPER, base=0.35)
    fill(cv, circle(13, 18, 2.4), BLACK, base=0.2, rim=False)
    tail = poly([(19, 23), (29, 21), (30, 26), (20, 27)])
    fill(cv, tail, PAPER, base=0.75)
    for x in (23, 26):
        line(cv, x, 22, x, 26, PAPER[1], solid=False)
    fill(cv, circle(25, 9, 2.5), GOLD, base=0.7)              # prayer bead
    return finish(cv)


@art("Catalejo")
def spyglass():
    cv = new()
    tube = rotate(union(rect(4, 13, 12, 19), rect(11, 12, 20, 20), rect(19, 11, 28, 21)), 16, 16, -30)
    fill(cv, tube, BRONZE, base=0.6)
    for x in (12, 20):
        fill(cv, rotate(rect(x - 1, 11, x + 1, 21), 16, 16, -30), GOLD, base=0.75)
    fill(cv, rotate(ellipse(28, 16, 1.4, 4.5), 16, 16, -30), GLASS, base=0.8, rim=False)
    return finish(cv)


@art("Pata de Conejo")
def rabbit_foot():
    cv = new()
    foot = union(ellipse(16, 19, 6, 9), ellipse(13, 26, 5, 3.5))
    fill(cv, foot, [(130, 120, 110), (170, 160, 148), (206, 198, 188), (232, 226, 218), (250, 248, 244)], base=0.55)
    fill(cv, rect(13, 6, 19, 10), GOLD, base=0.7)
    line(cv, 16, 5, 16, 1, GOLD[2])
    for x, y in ((10, 25), (12, 28), (15, 28)):
        cv.put(x, y, (140, 120, 120))
    return finish(cv)


@art("Pico de Minero")
def pickaxe():
    cv = new()
    fill(cv, rotate(rect(15, 6, 17, 30), 16, 16, 35), WOOD, base=0.55)
    head = poly([(2, 12), (9, 7), (16, 5), (23, 7), (30, 12), (23, 10), (16, 9), (9, 10)])
    fill(cv, rotate(head, 16, 16, 35), IRON, base=0.6)
    return finish(cv)


@art("Hucha")
def piggy_bank():
    cv = new()
    body = union(ellipse(15, 19, 11, 8), circle(25, 17, 4))
    fill(cv, body, PINK, base=0.6)
    fill(cv, ellipse(28, 18, 2, 2.4), PINK, base=0.35)
    for x in (8, 20):
        fill(cv, rect(x, 25, x + 3, 29), PINK, base=0.45)
    fill(cv, poly([(20, 11), (23, 7), (24, 13)]), PINK, base=0.55)
    fill(cv, rect(12, 10, 18, 12), BLACK, base=0.2, rim=False)  # coin slot
    fill(cv, circle(15, 6, 2.6), GOLD, base=0.8)
    cv.put(24, 15, INK)
    return finish(cv)


@art("Calavera Sonriente")
def grinning_skull():
    cv = new()
    skull = union(circle(16, 13, 10), rect(10, 18, 22, 26))
    fill(cv, skull, BONE, base=0.6)
    for x in (12, 20):
        fill(cv, circle(x, 14, 2.8), BLACK, base=0.2, rim=False)
    fill(cv, poly([(16, 17), (14, 20), (18, 20)]), BLACK, base=0.2, rim=False)
    for x in range(11, 22, 2):                              # wide grin
        line(cv, x, 23, x, 25, INK)
    line(cv, 10, 22, 22, 22, INK)
    fill(cv, circle(20, 14, 0.9), RED, base=0.8, rim=False)
    return finish(cv)


@art("Yunque Portátil")
def anvil():
    cv = new()
    top = union(rect(8, 10, 26, 15), poly([(8, 10), (2, 11), (8, 14)]))
    fill(cv, top, IRON, base=0.65)
    fill(cv, rect(12, 15, 22, 21), IRON, base=0.45)
    fill(cv, poly([(8, 25), (26, 25), (23, 21), (11, 21)]), IRON, base=0.4)
    fill(cv, rect(13, 6, 21, 8), LEATHER, base=0.5)            # carrying strap
    line(cv, 13, 8, 13, 10, LEATHER[1])
    line(cv, 21, 8, 21, 10, LEATHER[1])
    return finish(cv)


@art("Dado Cargado")
def loaded_die():
    cv = new()
    face = poly([(6, 12), (18, 8), (18, 26), (6, 28)])
    side = poly([(18, 8), (27, 12), (27, 26), (18, 26)])
    topf = poly([(6, 12), (15, 6), (27, 12), (18, 8)])
    fill(cv, face, WHITE if False else BONE, base=0.75)
    fill(cv, side, BONE, base=0.45)
    fill(cv, topf, BONE, base=0.9)
    for x, y in ((9, 15), (15, 21), (12, 18)):
        fill(cv, circle(x, y, 1.2), RED, base=0.5, rim=False)
    fill(cv, circle(22, 19, 2.2), [(60, 50, 40), (100, 90, 80), (150, 140, 130), (190, 180, 170), WHITE],
         base=0.4)                                          # the lead weight
    return finish(cv)


@art("Corona de Espinas")
def crown_of_thorns():
    cv = new()
    band = minus(ellipse(16, 18, 13, 7), ellipse(16, 18, 9.5, 4.2))
    fill(cv, band, [(50, 34, 20), (84, 60, 34), (120, 88, 52), (156, 120, 74), (190, 160, 110)], base=0.5)
    import math as _m
    for k in range(10):
        a = _m.radians(k * 36 + 10)
        x, y = 16 + 11.5 * _m.cos(a), 18 + 6 * _m.sin(a)
        dx, dy = _m.cos(a) * 4, _m.sin(a) * 3 - 2
        line(cv, x, y, x + dx, y + dy, BONE[3])
    for x, y in ((9, 22), (21, 23)):
        fill(cv, circle(x, y + 2, 1.3), BLOOD, base=0.6, rim=False)
    return finish(cv)


@art("Amuleto de Escarcha")
def frost_amulet():
    cv = new()
    line(cv, 8, 2, 16, 10, SILVER[2])
    line(cv, 24, 2, 16, 10, SILVER[2])
    gem = poly([(16, 9), (24, 18), (16, 29), (8, 18)])
    fill(cv, gem, ICE, base=0.6)
    fill(cv, poly([(16, 12), (20, 18), (16, 24), (12, 18)]), ICE, base=0.9, rim=False)
    for dx, dy in ((0, -1), (1, 0), (0, 1), (-1, 0)):
        cv.put(16 + dx * 2, 18 + dy * 2, WHITE)
    sparkle(cv, 25, 9, WHITE, 1)
    return finish(cv)


@art("Lanza de Ruptura")
def breaking_lance():
    cv = new()
    fill(cv, rotate(rect(15, 8, 17, 31), 16, 16, 40), WOOD, base=0.55)
    tip = rotate(poly([(16, 0), (20, 9), (16, 12), (12, 9)]), 16, 16, 40)
    fill(cv, tip, STEEL, base=0.7)
    for x, y in ((9, 6), (6, 10), (11, 3)):                     # shards of a broken shield
        fill(cv, poly([(x, y), (x + 3, y + 1), (x + 1, y + 3)]), CYAN, base=0.6, rim=False)
    return finish(cv)


@art("Péndulo")
def pendulum():
    cv = new()
    fill(cv, rect(6, 3, 26, 5), BRONZE, base=0.6)
    line(cv, 16, 5, 22, 22, SILVER[2])
    fill(cv, circle(22, 24, 5), GOLD, base=0.65)
    for x, y in ((8, 24), (11, 26), (14, 27)):                  # motion trail
        cv.put(x, y, GOLD[1], solid=False)
    return finish(cv)


@art("Brazalete del Equilibrio")
def balance_bracelet():
    cv = new()
    fill(cv, minus(ellipse(16, 17, 12, 9), ellipse(16, 17, 8, 5.5)), SILVER, base=0.6)
    fill(cv, circle(8, 12, 3), RED, base=0.6)
    fill(cv, circle(24, 12, 3), BLUE, base=0.6)
    fill(cv, circle(16, 26, 2.5), GOLD, base=0.7)
    return finish(cv)


@art("Cuenco Vacío")
def empty_bowl():
    cv = new()
    bowl = minus(ellipse(16, 17, 12, 10), rect(0, 0, 32, 15))
    fill(cv, bowl, WOOD, base=0.6)
    fill(cv, ellipse(16, 15, 12, 3), WOOD, base=0.25, rim=False)
    fill(cv, rect(13, 26, 19, 28), WOOD, base=0.4)
    return finish(cv)


@art("Reloj de Arena")
def hourglass():
    cv = new()
    glass = union(poly([(9, 6), (23, 6), (16, 16)]), poly([(16, 16), (23, 26), (9, 26)]))
    fill(cv, glass, GLASS, base=0.75)
    fill(cv, poly([(12, 10), (20, 10), (16, 15)]), [(150, 110, 50), (190, 150, 80), (220, 186, 110),
                                                  (240, 214, 150), (250, 236, 190)], base=0.6, rim=False)
    fill(cv, poly([(16, 20), (21, 25), (11, 25)]), [(150, 110, 50), (190, 150, 80), (220, 186, 110),
                                                  (240, 214, 150), (250, 236, 190)], base=0.6, rim=False)
    line(cv, 16, 16, 16, 20, (230, 200, 130))
    fill(cv, rect(7, 3, 25, 6), WOOD, base=0.6)
    fill(cv, rect(7, 26, 25, 29), WOOD, base=0.5)
    return finish(cv)


@art("Ancla")
def anchor():
    cv = new()
    fill(cv, rect(15, 7, 17, 26), IRON, base=0.6)
    fill(cv, ring(16, 5, 3.2, 1.5), IRON, base=0.6)
    fill(cv, rect(10, 10, 22, 12), IRON, base=0.6)
    arc = minus(minus(circle(16, 17, 11), circle(16, 17, 8.5)), rect(0, 0, 32, 19))
    fill(cv, arc, IRON, base=0.55)
    for x in (5, 27):
        fill(cv, poly([(x - 2, 19), (x + 2, 19), (x, 15)]), IRON, base=0.6)
    return finish(cv)


@art("Cartas Marcadas")
def marked_cards():
    cv = new()
    fill(cv, rotate(rect(6, 7, 20, 27), 13, 17, -14), PAPER, base=0.5)
    fill(cv, rotate(rect(12, 6, 26, 26), 19, 16, 10), PAPER, base=0.75)
    mark = rotate(poly([(17, 11), (22, 11), (19, 15)]), 19, 16, 10)
    fill(cv, mark, RED, base=0.6, rim=False)
    fill(cv, rotate(circle(19, 20, 2.5), 19, 16, 10), BLACK, base=0.3, rim=False)
    line(cv, 25, 3, 29, 7, INK)                          # nail scratch
    return finish(cv)


@art("Medalla del Veterano")
def veteran_medal():
    cv = new()
    fill(cv, poly([(10, 2), (16, 2), (18, 14), (14, 14)]), CLOTH_RED, base=0.6)
    fill(cv, poly([(16, 2), (22, 2), (18, 14), (14, 14)]), BLUE, base=0.55)
    fill(cv, circle(16, 21, 8), BRONZE, base=0.6)
    import math as _m
    star = poly([(16 + (4.5 if k % 2 == 0 else 2) * _m.cos(_m.radians(-90 + k * 36)),
                  21 + (4.5 if k % 2 == 0 else 2) * _m.sin(_m.radians(-90 + k * 36))) for k in range(10)])
    fill(cv, star, GOLD, base=0.85, rim=False)
    return finish(cv)


@art("Hoja de Laurel")
def laurel():
    cv = new()
    import math as _m
    for side in (-1, 1):
        for k in range(5):
            a = _m.radians(110 + k * 30) if side < 0 else _m.radians(70 - k * 30)
            x, y = 16 + 10 * _m.cos(a), 16 + 10 * _m.sin(a)
            fill(cv, rotate(ellipse(x, y, 2, 3.6), x, y, _m.degrees(a) + 90), GREEN, base=0.6)
    fill(cv, circle(16, 27, 2), GOLD, base=0.7)
    return finish(cv)


@art("Tarjeta de Socio")
def member_card():
    cv = new()
    fill(cv, rect(3, 9, 29, 25), [(30, 30, 50), (50, 50, 84), (80, 80, 130), (120, 120, 180), (180, 180, 230)],
         base=0.5)
    fill(cv, rect(6, 13, 12, 18), GOLD, base=0.7)
    for y in (14, 17):
        line(cv, 15, y, 26, y, SILVER[3], solid=False)
    line(cv, 6, 22, 20, 22, SILVER[2], solid=False)
    sparkle(cv, 26, 21, GOLD[4], 1)
    return finish(cv)


@art("Trofeo de Caza")
def hunting_trophy():
    cv = new()
    fill(cv, poly([(9, 18), (23, 18), (21, 29), (11, 29)]), WOOD, base=0.55)    # plaque
    head = union(ellipse(16, 18, 5, 6), ellipse(16, 24, 3, 3))
    fill(cv, head, LEATHER, base=0.65)
    for side in (-1, 1):
        x0 = 16 + side * 3
        line(cv, x0, 13, x0 + side * 6, 4, BONE[3])
        line(cv, x0 + side * 3, 9, x0 + side * 9, 8, BONE[3])
        line(cv, x0 + side * 5, 6, x0 + side * 4, 2, BONE[3])
    cv.put(14, 18, INK)
    cv.put(18, 18, INK)
    return finish(cv)


@art("Martillo del Herrero")
def smith_hammer():
    cv = new()
    fill(cv, rotate(rect(15, 10, 18, 31), 16, 16, -35), WOOD, base=0.55)
    fill(cv, rotate(rect(8, 4, 24, 11), 16, 16, -35), IRON, base=0.6)
    for x, y in ((25, 22), (28, 19), (27, 25)):
        cv.put(x, y, FIRE[3])
    return finish(cv)


@art("Lima de Hierro")
def iron_file():
    cv = new()
    blade = rotate(rect(14, 2, 18, 22), 16, 16, 40)
    fill(cv, blade, IRON, base=0.6)
    for k in range(4, 21, 2):
        a, b = rotate(rect(14, k, 18, k + 1), 16, 16, 40), None
        fill(cv, a, IRON, base=0.35, rim=False)
    fill(cv, rotate(rect(14, 22, 18, 30), 16, 16, 40), WOOD, base=0.55)
    return finish(cv)


@art("Lupa del Tasador")
def magnifier():
    cv = new()
    fill(cv, rotate(rect(18, 18, 21, 30), 19, 19, -45), WOOD, base=0.55)
    fill(cv, ring(13, 13, 9, 7), GOLD, base=0.65)
    fill(cv, circle(13, 13, 7), GLASS, base=0.7, rim=False)
    fill(cv, poly([(13, 9), (16, 13), (13, 17), (10, 13)]), GREEN, base=0.7, rim=False)  # gem under the lens
    cv.put(10, 9, WHITE)
    return finish(cv)


@art("Moneda de Dos Caras")
def two_faced_coin():
    cv = new()
    fill(cv, circle(12, 16, 9), GOLD, base=0.65)
    fill(cv, circle(21, 16, 9), SILVER, base=0.55)
    fill(cv, minus(circle(12, 16, 9), circle(21, 16, 9.5)), GOLD, base=0.7)
    for x, y in ((9, 13), (11, 13)):
        cv.put(x, y, GOLD[0])
    line(cv, 8, 19, 12, 19, GOLD[0])
    for x, y in ((21, 13), (24, 13)):
        cv.put(x, y, SILVER[0])
    line(cv, 21, 20, 24, 19, SILVER[0])
    return finish(cv)


@art("Cadena Rota")
def broken_chain():
    cv = new()
    for cx, cy, deg in ((7, 24, 45), (13, 18, -45), (19, 12, 45)):
        link = rotate(minus(ellipse(cx, cy, 5, 3), ellipse(cx, cy, 3, 1.4)), cx, cy, deg)
        fill(cv, link, IRON, base=0.6)
    open_link = minus(rotate(minus(ellipse(25, 6, 5, 3), ellipse(25, 6, 3, 1.4)), 25, 6, -45),
                      rect(23, 7, 30, 12))
    fill(cv, open_link, IRON, base=0.6)
    sparkle(cv, 26, 12, WHITE, 1)
    return finish(cv)


@art("Pluma de Fénix")
def phoenix_feather():
    cv = new()
    vane = rotate(union(ellipse(16, 13, 6, 11), poly([(16, 0), (19, 4), (13, 4)])), 16, 16, 30)
    fill(cv, vane, FIRE, base=0.65)
    fill(cv, rotate(ellipse(16, 12, 3, 7), 16, 16, 30), [(200, 60, 20), (240, 120, 30), (250, 180, 60),
                                                         (255, 220, 120), WHITE], base=0.7, rim=False)
    flat(cv, rotate(rect(15.4, 3, 16.6, 31), 16, 16, 30), GOLD[3])
    cv.glow(16, 13, 10, FIRE[3], 0.25)
    return finish(cv)


@art("Talismán del Último Aliento")
def last_breath_talisman():
    cv = new()
    line(cv, 16, 2, 16, 7, LEATHER[2])
    fill(cv, poly([(16, 6), (25, 12), (22, 26), (10, 26), (7, 12)]), STONE, base=0.55)
    heart = union(circle(13, 15, 3), circle(19, 15, 3), poly([(10, 16), (22, 16), (16, 23)]))
    fill(cv, heart, BLOOD, base=0.55)
    line(cv, 16, 13, 15, 18, INK)                               # cracked heart
    line(cv, 15, 18, 17, 21, INK)
    return finish(cv)


@art("Grillete")
def shackle():
    cv = new()
    cuff = minus(circle(12, 19, 8), circle(12, 19, 5))
    fill(cv, cuff, IRON, base=0.6)
    fill(cv, rect(10, 9, 14, 12), IRON, base=0.7)
    for i, (cx, cy) in enumerate(((19, 13), (23, 9), (27, 5))):
        fill(cv, rotate(minus(ellipse(cx, cy, 3.4, 2), ellipse(cx, cy, 1.8, 0.6)), cx, cy, -45 + 90 * (i % 2)),
             IRON, base=0.55)
    fill(cv, circle(12, 26, 1.5), IRON, base=0.3)
    return finish(cv)


@art("Baraja Mágica")
def magic_deck():
    cv = new()
    for i in range(3):
        fill(cv, rect(8 + i * 2, 10 - i * 2, 22 + i * 2, 28 - i * 2), VIOLET, base=0.4 + i * 0.15)
    fill(cv, ring(19, 16, 4, 2.6), GOLD, base=0.7)
    for x, y in ((6, 6), (27, 4), (28, 20)):
        sparkle(cv, x, y, (230, 200, 255), 1)
    return finish(cv)


@art("Batería Arcana")
def arcane_battery():
    cv = new()
    fill(cv, rect(9, 7, 23, 28), GLASS, base=0.6)
    fill(cv, rect(10, 15, 22, 27), CYAN, base=0.65, rim=False)
    fill(cv, rect(13, 4, 19, 7), BRONZE, base=0.7)
    fill(cv, rect(8, 27, 24, 30), BRONZE, base=0.5)
    bolt = poly([(17, 9), (13, 17), (16, 17), (14, 24), (20, 14), (17, 14), (19, 9)])
    fill(cv, bolt, GOLD, base=0.9, rim=False)
    return finish(cv)


@art("Corazón de Piedra")
def stone_heart():
    cv = new()
    heart = union(circle(11, 13, 6), circle(21, 13, 6), poly([(5, 15), (27, 15), (16, 28)]))
    fill(cv, heart, STONE, base=0.55)
    for x0, y0, x1, y1 in ((12, 9, 15, 15), (15, 15, 13, 20), (20, 16, 23, 19)):
        line(cv, x0, y0, x1, y1, STONE[0])
    fill(cv, circle(19, 22, 1.4), GREEN, base=0.8, rim=False)  # moss
    return finish(cv)


@art("Prisma")
def prism():
    cv = new()
    tri = poly([(16, 4), (27, 25), (5, 25)])
    fill(cv, tri, GLASS, base=0.75)
    fill(cv, poly([(16, 9), (21, 21), (16, 21)]), GLASS, base=0.95, rim=False)
    line(cv, 0, 17, 11, 15, WHITE, solid=False)
    for i, c in enumerate((RED[3], ORANGE[3], GOLD[3], GREEN[3], BLUE[3], VIOLET[3])):
        line(cv, 21, 15 + i, 31, 14 + i * 2, c, solid=False)
    return finish(cv)


@art("Piedra de Toque")
def touchstone():
    cv = new()
    fill(cv, ellipse(16, 19, 12, 8), [(14, 14, 18), (30, 30, 38), (50, 50, 62), (76, 76, 92), (120, 120, 140)],
         base=0.5)
    for y, x0, x1 in ((16, 9, 20), (19, 11, 24), (22, 10, 18)):     # gold streaks rubbed on it
        line(cv, x0, y, x1, y - 1, GOLD[3])
    sparkle(cv, 24, 13, GOLD[4], 1)
    return finish(cv)


@art("Bolsa sin Fondo")
def bottomless_bag():
    cv = new()
    bag = union(ellipse(16, 19, 10, 9), poly([(11, 11), (21, 11), (19, 6), (13, 6)]))
    fill(cv, bag, VIOLET, base=0.5)
    fill(cv, ellipse(16, 10, 5, 2), BLACK, base=0.15, rim=False)
    fill(cv, rect(11, 12, 21, 13), GOLD, base=0.7)
    import math as _m
    for k in range(8):                                        # swirl of the void
        a = _m.radians(k * 50)
        cv.put(round(16 + (1 + k * 0.7) * _m.cos(a)), round(20 + (1 + k * 0.7) * _m.sin(a)), (210, 170, 255))
    return finish(cv)


@art("Contrato Maldito")
def cursed_contract():
    cv = new()
    fill(cv, rect(7, 4, 25, 28), PAPER, base=0.5)
    for y in (8, 11, 14, 17):
        line(cv, 10, y, 22, y, EARTH[1], solid=False)
    line(cv, 11, 23, 20, 22, BLOOD[2])                          # blood signature
    fill(cv, circle(22, 25, 3), BLOOD, base=0.55)
    fill(cv, poly([(3, 2), (7, 4), (5, 7)]), VIOLET, base=0.6, rim=False)
    cv.glow(16, 16, 14, VIOLET[2], 0.15)
    return finish(cv)


@art("Dado de Veinte Caras")
def d20():
    cv = new()
    hexa = poly([(16, 3), (27, 9), (27, 23), (16, 29), (5, 23), (5, 9)])
    fill(cv, hexa, BLUE, base=0.5)
    fill(cv, poly([(16, 8), (24, 21), (8, 21)]), BLUE, base=0.8)
    for a, b in (((16, 3), (16, 8)), ((5, 9), (8, 21)), ((27, 9), (24, 21)), ((8, 21), (16, 29)),
                 ((24, 21), (16, 29)), ((5, 23), (8, 21)), ((27, 23), (24, 21))):
        line(cv, *a, *b, BLUE[1], solid=False)
    for x, y in ((14, 15), (15, 15), (17, 15), (18, 15), (14, 17), (17, 17), (18, 17), (15, 18), (14, 18)):
        cv.put(x, y, WHITE)
    return finish(cv)


@art("Ampolla de Maná")
def mana_ampoule():
    cv = new()
    vial = union(capsule(16, 12, 16, 25, 5), rect(14, 4, 18, 9))
    fill(cv, vial, GLASS, base=0.75)
    fill(cv, capsule(16, 17, 16, 25, 3.8), BLUE, base=0.35, slope=0.8, rim=False)
    fill(cv, rect(13, 3, 19, 5), SILVER, base=0.7)
    for x, y in ((15, 19), (17, 22)):
        cv.put(x, y, CYAN[4])
    sparkle(cv, 24, 8, CYAN[4], 1)
    return finish(cv)


@art("Guantelete de Púas")
def spiked_gauntlet():
    cv = new()
    fist = union(rect(8, 12, 24, 22), rect(10, 22, 22, 29))
    fill(cv, fist, IRON, base=0.6)
    for x in (9, 13, 17, 21):
        fill(cv, poly([(x, 12), (x + 3, 12), (x + 1.5, 5)]), STEEL, base=0.8)
    for x in (12, 16, 20):
        line(cv, x, 13, x, 20, IRON[1])
    fill(cv, rect(9, 22, 23, 24), LEATHER, base=0.5)
    return finish(cv)


@art("Muñequera")
def wristband():
    cv = new()
    band = minus(ellipse(16, 17, 12, 8), ellipse(16, 17, 8.5, 4.5))
    fill(cv, band, LEATHER, base=0.55)
    for x in (8, 16, 24):
        fill(cv, circle(x, 17 + (3 if x == 16 else 0) - (0 if x == 16 else 0), 1.6), STEEL, base=0.8)
    line(cv, 6, 12, 26, 12, LEATHER[3], solid=False)
    return finish(cv)


@art("Venda de Campaña")
def field_bandage():
    cv = new()
    fill(cv, rotate(rect(5, 11, 27, 21), 16, 16, -30), PAPER, base=0.7)
    fill(cv, rotate(rect(12, 13, 20, 19), 16, 16, -30), PAPER, base=0.5)
    cross = union(rect(14, 12, 18, 20), rect(12, 14, 20, 18))
    fill(cv, rotate(cross, 16, 16, -30), RED, base=0.6, rim=False)
    return finish(cv)


@art("Peto Abollado")
def dented_breastplate():
    cv = new()
    plate = poly([(6, 6), (12, 4), (16, 7), (20, 4), (26, 6), (27, 18), (22, 27), (10, 27), (5, 18)])
    fill(cv, plate, STEEL, base=0.6)
    line(cv, 16, 8, 16, 25, STEEL[1], solid=False)
    fill(cv, circle(21, 15, 2.5), STEEL, base=0.25, rim=False)       # dent
    line(cv, 9, 19, 13, 22, STEEL[1])
    return finish(cv)


@art("Collar de Colmillos")
def fang_necklace():
    cv = new()
    import math as _m
    pts = [(16 + 12 * _m.cos(_m.radians(a)), 6 + 12 * _m.sin(_m.radians(a))) for a in range(10, 171, 10)]
    for a, b in zip(pts, pts[1:]):
        line(cv, *a, *b, LEATHER[2])
    for a in (40, 65, 90, 115, 140):
        x, y = 16 + 12 * _m.cos(_m.radians(a)), 6 + 12 * _m.sin(_m.radians(a))
        fang = rotate(poly([(x - 1.6, y), (x + 1.6, y), (x, y + 7)]), x, y, a - 90)
        fill(cv, fang, BONE, base=0.7)
    return finish(cv)


@art("Hacha Mellada")
def notched_axe():
    cv = new()
    fill(cv, rotate(rect(15, 4, 17, 31), 16, 16, 30), WOOD, base=0.55)
    blade = minus(poly([(16, 4), (27, 2), (29, 12), (27, 18), (16, 13)]), union(circle(29, 8, 1.5), circle(28, 14, 1.2)))
    fill(cv, rotate(blade, 16, 16, 30), IRON, base=0.6)
    return finish(cv)


@art("Odre de Sangre")
def blood_skin():
    cv = new()
    skin = union(ellipse(16, 20, 10, 8), poly([(12, 13), (20, 13), (18, 6), (14, 6)]))
    fill(cv, skin, [(70, 20, 22), (110, 34, 34), (150, 52, 48), (186, 80, 70), (220, 130, 120)], base=0.55)
    fill(cv, rect(13, 3, 19, 6), LEATHER, base=0.6)
    line(cv, 11, 12, 21, 12, LEATHER[1])
    fill(cv, ellipse(20, 30, 2, 1), BLOOD, base=0.5, rim=False)
    return finish(cv)


@art("Gema de Sangre")
def blood_gem():
    cv = new()
    gem = poly([(10, 8), (22, 8), (28, 14), (16, 29), (4, 14)])
    fill(cv, gem, BLOOD, base=0.45, slope=0.8)
    fill(cv, poly([(10, 8), (22, 8), (19, 14), (13, 14)]), BLOOD, base=0.8, rim=False)
    line(cv, 4, 14, 28, 14, BLOOD[1], solid=False)
    sparkle(cv, 12, 10, WHITE, 1)
    cv.glow(16, 17, 12, RED[3], 0.2)
    return finish(cv)


@art("Escudo del Mártir")
def martyr_shield():
    cv = new()
    sh = poly([(5, 5), (27, 5), (26, 17), (16, 29), (6, 17)])
    fill(cv, sh, SILVER, base=0.6)
    fill(cv, union(rect(14, 8, 18, 24), rect(9, 12, 23, 16)), BLOOD, base=0.55, rim=False)
    for x, y in ((22, 21), (10, 23)):
        fill(cv, circle(x, y, 1.2), BLOOD, base=0.5, rim=False)
    return finish(cv)


@art("Cáliz Carmesí")
def crimson_chalice():
    cv = new()
    cup = minus(ellipse(16, 10, 10, 9), rect(0, 0, 32, 8))
    fill(cv, cup, GOLD, base=0.6)
    fill(cv, ellipse(16, 8, 10, 2.5), BLOOD, base=0.5, rim=False)
    fill(cv, rect(15, 18, 17, 25), GOLD, base=0.5)
    fill(cv, ellipse(16, 26, 7, 2.5), GOLD, base=0.45)
    fill(cv, circle(16, 13, 1.6), RED, base=0.7, rim=False)
    line(cv, 9, 9, 8, 14, BLOOD[2])
    return finish(cv)


@art("Tambor de Guerra")
def war_drum():
    cv = new()
    fill(cv, rect(6, 12, 26, 26), CLOTH_RED, base=0.55)
    fill(cv, ellipse(16, 26, 10, 3), CLOTH_RED, base=0.35)
    fill(cv, ellipse(16, 12, 10, 3.5), PAPER, base=0.75)
    for x0, x1 in ((7, 13), (13, 19), (19, 25)):
        line(cv, x0, 14, x1, 25, GOLD[3])
        line(cv, x1, 14, x0, 25, GOLD[3])
    line(cv, 20, 2, 14, 10, WOOD[2])
    fill(cv, circle(20, 3, 1.6), BONE, base=0.7)
    return finish(cv)


@art("Brasero")
def brazier():
    cv = new()
    bowl = minus(ellipse(16, 16, 11, 7), rect(0, 0, 32, 15))
    fill(cv, bowl, IRON, base=0.55)
    for x0, x1 in ((10, 6), (22, 26), (16, 16)):
        line(cv, x0, 21, x1, 29, IRON[2])
    flame = union(ellipse(16, 12, 7, 4), poly([(10, 12), (13, 3), (16, 9), (19, 1), (22, 12)]))
    fill(cv, flame, FIRE, base=0.7, rim=False)
    fill(cv, ellipse(16, 13, 3, 2), FIRE, base=0.95, rim=False)
    cv.glow(16, 9, 12, FIRE[3], 0.25)
    return finish(cv)


@art("Rodela Gastada")
def worn_buckler():
    cv = new()
    fill(cv, circle(16, 16, 12), WOOD, base=0.55)
    fill(cv, ring(16, 16, 12, 10.5), IRON, base=0.55)
    fill(cv, circle(16, 16, 3.5), IRON, base=0.7)
    for x0, y0, x1, y1 in ((7, 9, 11, 13), (21, 21, 25, 23), (9, 22, 12, 20)):
        line(cv, x0, y0, x1, y1, WOOD[0])
    return finish(cv)


@art("Yelmo del Berserker")
def berserker_helm():
    cv = new()
    helm = union(circle(16, 15, 9), rect(7, 15, 25, 25))
    fill(cv, helm, IRON, base=0.6)
    fill(cv, rect(10, 16, 22, 18), BLACK, base=0.2, rim=False)      # eye slit
    fill(cv, rect(15, 18, 17, 25), IRON, base=0.4)
    for side in (-1, 1):
        horn = poly([(16 + side * 7, 11), (16 + side * 13, 8), (16 + side * 14, 1), (16 + side * 10, 7),
                     (16 + side * 7, 7)])
        fill(cv, horn, BONE, base=0.65)
    for x in (12, 20):
        cv.put(x, 17, RED[3])
    return finish(cv)


@art("Runa de Sangre")
def blood_rune():
    cv = new()
    fill(cv, poly([(9, 4), (24, 6), (27, 24), (16, 29), (6, 22)]), STONE, base=0.55)
    for a, b in (((13, 9), (13, 24)), ((13, 13), (21, 9)), ((13, 17), (21, 13)), ((21, 13), (21, 24))):
        line(cv, *a, *b, BLOOD[3])
    cv.glow(17, 16, 10, RED[3], 0.2)
    return finish(cv)


@art("Estandarte de la Legión")
def legion_banner():
    cv = new()
    fill(cv, rect(15, 2, 17, 31), WOOD, base=0.55)
    fill(cv, rect(8, 5, 24, 7), GOLD, base=0.65)
    cloth = poly([(9, 7), (23, 7), (23, 23), (16, 19), (9, 23)])
    fill(cv, cloth, CLOTH_RED, base=0.6)
    fill(cv, rect(12, 11, 20, 15), GOLD, base=0.75, rim=False)       # laurel plate
    fill(cv, poly([(16, 0), (18, 3), (14, 3)]), GOLD, base=0.8)
    return finish(cv)


@art("Corazón Desbocado")
def racing_heart():
    cv = new()
    heart = union(circle(12, 13, 6), circle(20, 13, 6), poly([(6, 15), (26, 15), (16, 27)]))
    fill(cv, heart, RED, base=0.6)
    pulse = [(1, 17), (6, 17), (9, 11), (12, 22), (15, 14), (17, 17), (31, 17)]
    for a, b in zip(pulse, pulse[1:]):
        line(cv, *a, *b, WHITE)
    for x, y in ((3, 8), (29, 9)):
        line(cv, x, y, x + (1 if x < 16 else -1) * 2, y - 2, RED[3])
    return finish(cv)


@art("Hierro Fundido")
def molten_iron():
    cv = new()
    fill(cv, poly([(4, 18), (28, 18), (24, 28), (8, 28)]), IRON, base=0.45)   # crucible
    fill(cv, ellipse(16, 18, 12, 3), ORANGE, base=0.55, rim=False)
    fill(cv, ellipse(15, 18, 6, 1.5), FIRE, base=0.9, rim=False)
    fill(cv, capsule(16, 2, 16, 16, 1.6), ORANGE, base=0.7, rim=False)      # stream pouring in
    for x, y in ((12, 13), (19, 11), (16, 8)):
        cv.put(x, y, FIRE[4])
    cv.glow(16, 17, 12, FIRE[3], 0.3)
    return finish(cv)


@art("Yesca")
def tinder():
    cv = new()
    for deg, y in ((-20, 22), (15, 24), (0, 19)):
        fill(cv, rotate(rect(6, y - 1.5, 26, y + 1.5), 16, y, deg), WOOD, base=0.55)
    fill(cv, circle(16, 18, 3), BONE, base=0.6)
    for x, y in ((14, 13), (18, 11), (16, 9)):
        cv.put(x, y, FIRE[4])
    fill(cv, poly([(14, 17), (16, 10), (18, 17)]), FIRE, base=0.8, rim=False)
    cv.glow(16, 14, 8, FIRE[3], 0.25)
    return finish(cv)


@art("Concha Marina")
def seashell():
    cv = new()
    import math as _m
    shell = union(poly([(16, 27)] + [(16 + 13 * _m.cos(_m.radians(a)), 22 - 15 * _m.sin(_m.radians(a)))
                                     for a in range(20, 161, 10)]), rect(13, 24, 19, 29))
    fill(cv, shell, PINK, base=0.65)
    for a in range(35, 150, 22):
        line(cv, 16, 26, 16 + 11 * _m.cos(_m.radians(a)), 22 - 13 * _m.sin(_m.radians(a)), PINK[1])
    return finish(cv)


@art("Piedra Pómez")
def pumice():
    cv = new()
    fill(cv, ellipse(16, 18, 12, 9), [(110, 104, 96), (150, 144, 134), (186, 180, 170), (214, 208, 198),
                                       (236, 232, 224)], base=0.6)
    for x, y in ((10, 15), (14, 20), (19, 14), (22, 20), (17, 24), (12, 11), (24, 16)):
        cv.put(x, y, (110, 104, 96))
        cv.put(x + 1, y, (150, 144, 134))
    return finish(cv)


@art("Pluma de Grifo")
def griffin_feather():
    cv = new()
    vane = rotate(union(ellipse(16, 12, 5.5, 10), poly([(16, 0), (19, 5), (13, 5)])), 16, 16, 28)
    fill(cv, vane, [(90, 60, 30), (140, 100, 50), (190, 150, 80), (226, 196, 130), (250, 236, 200)], base=0.6)
    fill(cv, rotate(ellipse(16, 4, 3.5, 3), 16, 16, 28), BONE, base=0.85, rim=False)   # white tip
    flat(cv, rotate(rect(15.4, 3, 16.6, 31), 16, 16, 28), GOLD[2])
    return finish(cv)


@art("Varita de Sauce")
def willow_wand():
    cv = new()
    line(cv, 6, 28, 23, 9, WOOD[2])
    line(cv, 7, 28, 24, 9, WOOD[3])
    for x, y in ((12, 21), (17, 16)):
        fill(cv, rotate(ellipse(x + 2, y + 2, 1.4, 3), x + 2, y + 2, 40), GREEN, base=0.6)
    fill(cv, circle(25, 7, 2.5), GREEN, base=0.8, rim=False)
    for x, y in ((28, 3), (29, 9), (22, 3)):
        sparkle(cv, x, y, GREEN[4], 1)
    return finish(cv)


@art("Reloj de Agua")
def water_clock():
    cv = new()
    fill(cv, poly([(6, 4), (26, 4), (21, 14), (11, 14)]), BRONZE, base=0.6)
    fill(cv, ellipse(16, 5, 10, 2), BLUE, base=0.6, rim=False)
    line(cv, 16, 15, 16, 19, CYAN[3])
    fill(cv, rect(8, 19, 24, 29), GLASS, base=0.7)
    fill(cv, rect(9, 24, 23, 28), BLUE, base=0.45, rim=False)
    for y in (21, 24, 27):
        line(cv, 24, y, 25, y, BRONZE[2])
    return finish(cv)


@art("Sombrero Puntiagudo")
def pointy_hat():
    cv = new()
    fill(cv, ellipse(16, 25, 14, 4), VIOLET, base=0.45)
    cone = poly([(8, 25), (24, 25), (20, 12), (24, 3), (15, 9)])
    fill(cv, cone, VIOLET, base=0.6)
    fill(cv, poly([(9, 23), (23, 23), (22, 20), (10, 20)]), GOLD, base=0.65, rim=False)
    sparkle(cv, 15, 15, GOLD[4], 1)
    return finish(cv)


@art("Piedra de Lava")
def lava_stone():
    cv = new()
    rock = poly([(8, 8), (20, 5), (28, 13), (25, 26), (12, 28), (4, 19)])
    fill(cv, rock, [(20, 16, 16), (40, 30, 30), (60, 46, 44), (84, 64, 60), (120, 96, 90)], base=0.5)
    for a, b in (((9, 12), (16, 17)), ((16, 17), (22, 11)), ((16, 17), (14, 25)), ((16, 17), (24, 21))):
        line(cv, *a, *b, ORANGE[3])
    cv.glow(16, 17, 10, ORANGE[3], 0.2)
    return finish(cv)


@art("Escoba de Brujo")
def witch_broom():
    cv = new()
    flat(cv, rotate(rect(15, 1, 17, 22), 16, 16, -40), WOOD[2])
    flat(cv, rotate(rect(16, 1, 17, 22), 16, 16, -40), WOOD[3])
    bristles = rotate(poly([(12, 22), (20, 22), (24, 31), (8, 31)]), 16, 16, -40)
    fill(cv, bristles, [(110, 80, 30), (160, 120, 50), (200, 160, 80), (226, 196, 120), (244, 226, 170)],
         base=0.6)
    fill(cv, rotate(rect(12, 21, 20, 23), 16, 16, -40), CLOTH_RED, base=0.6)
    sparkle(cv, 7, 6, VIOLET[4], 1)
    return finish(cv)


@art("Caldero")
def cauldron():
    cv = new()
    pot = minus(circle(16, 18, 11), rect(0, 0, 32, 11))
    fill(cv, pot, BLACK, base=0.5)
    fill(cv, ellipse(16, 11, 11, 2.5), IRON, base=0.55)
    fill(cv, ellipse(16, 11, 9, 1.6), GREEN, base=0.7, rim=False)
    for x in (9, 23):
        fill(cv, rect(x - 1, 27, x + 2, 30), BLACK, base=0.5)
    for x, y, r in ((13, 6, 1.6), (19, 4, 1.2), (16, 1, 0.9)):
        fill(cv, circle(x, y, r), GREEN, base=0.8, rim=False)
    return finish(cv)


@art("Ascua de Volcán")
def volcano_ember():
    cv = new()
    ember = poly([(16, 6), (25, 13), (23, 25), (10, 26), (7, 14)])
    fill(cv, ember, [(60, 14, 8), (130, 30, 14), (200, 70, 20), (245, 140, 40), (255, 220, 120)], base=0.6)
    fill(cv, circle(16, 17, 4), FIRE, base=0.85, rim=False)
    cv.glow(16, 17, 13, ORANGE[3], 0.3)
    for x, y in ((10, 4), (22, 3), (26, 8)):
        cv.put(x, y, FIRE[4])
    return finish(cv)


@art("Orbe de Tormenta")
def storm_orb():
    cv = new()
    fill(cv, circle(16, 15, 11), [(30, 30, 60), (50, 54, 100), (80, 90, 150), (130, 140, 200), (200, 210, 250)],
         base=0.45)
    bolt = poly([(17, 6), (12, 16), (16, 16), (13, 24), (21, 13), (17, 13), (20, 6)])
    fill(cv, bolt, GOLD, base=0.9, rim=False)
    fill(cv, poly([(9, 26), (23, 26), (25, 30), (7, 30)]), BRONZE, base=0.55)
    cv.put(11, 9, WHITE)
    return finish(cv)


@art("Grimorio en Blanco")
def blank_grimoire():
    cv = new()
    fill(cv, rect(6, 6, 26, 27), [(40, 30, 60), (64, 48, 90), (94, 72, 128), (130, 104, 168), (180, 156, 210)],
         base=0.55)
    fill(cv, rect(8, 26, 26, 28), PAPER, base=0.8)
    fill(cv, rect(6, 6, 8, 27), GOLD, base=0.6)
    fill(cv, ring(17, 16, 5, 3.6), GOLD, base=0.7)
    fill(cv, rect(22, 4, 24, 9), RED, base=0.6)                 # ribbon bookmark
    return finish(cv)


@art("Fuente Menor")
def lesser_fountain():
    cv = new()
    fill(cv, ellipse(16, 25, 12, 4), STONE, base=0.5)
    fill(cv, ellipse(16, 24, 10, 2.5), BLUE, base=0.6, rim=False)
    fill(cv, rect(14, 12, 18, 23), STONE, base=0.6)
    fill(cv, ellipse(16, 12, 6, 2), STONE, base=0.7)
    for side in (-1, 1):
        for k in range(5):
            cv.put(16 + side * (2 + k), 9 + (k * k) // 3, CYAN[3])
    fill(cv, circle(16, 7, 1.6), CYAN, base=0.8, rim=False)
    return finish(cv)


@art("Cristal de Escarcha")
def frost_crystal():
    cv = new()
    for cx, h, w in ((16, 4, 4), (10, 11, 3), (22, 9, 3)):
        fill(cv, poly([(cx, h), (cx + w, h + 5), (cx + w, 26), (cx - w, 26), (cx - w, h + 5)]), ICE,
             base=0.65 if cx == 16 else 0.5)
    fill(cv, ellipse(16, 27, 10, 2.5), STONE, base=0.5)
    sparkle(cv, 15, 10, WHITE, 1)
    return finish(cv)


@art("Lente Prismática")
def prismatic_lens():
    cv = new()
    fill(cv, ring(16, 16, 11, 9), SILVER, base=0.65)
    for i, c in enumerate((RED, ORANGE, GOLD, GREEN, BLUE, VIOLET)):
        r = 8.6 - i * 1.3
        fill(cv, circle(16, 16, r), c, base=0.65, rim=False)
    cv.put(12, 11, WHITE)
    cv.put(13, 11, WHITE)
    return finish(cv)


@art("Capa del Archimago")
def archmage_cloak():
    cv = new()
    cloak = poly([(12, 5), (20, 5), (27, 28), (16, 25), (5, 28)])
    fill(cv, cloak, BLUE, base=0.5)
    fill(cv, poly([(12, 5), (20, 5), (18, 11), (14, 11)]), BLUE, base=0.75)
    fill(cv, circle(16, 8, 2), GOLD, base=0.8)
    for x, y in ((11, 18), (20, 15), (15, 21), (22, 23), (9, 25)):
        cv.put(x, y, GOLD[4])
    return finish(cv)


@art("Anillo de los Cuatro")
def ring_of_four():
    cv = new()
    fill(cv, minus(ellipse(16, 19, 10, 9), ellipse(16, 19, 7, 6)), GOLD, base=0.6)
    for (x, y), c in zip(((12, 8), (20, 8), (12, 13), (20, 13)), (RED, BLUE, GREEN, VIOLET)):
        fill(cv, circle(x, y, 2.6), c, base=0.6)
    return finish(cv)


@art("Afiladora de Bolsillo")
def pocket_sharpener():
    cv = new()
    fill(cv, rect(6, 14, 26, 22), STONE, base=0.6)
    fill(cv, rect(6, 21, 26, 24), WOOD, base=0.5)
    blade = rotate(poly([(4, 10), (22, 10), (26, 12), (22, 13), (4, 13)]), 16, 12, -20)
    fill(cv, blade, STEEL, base=0.75)
    for x, y in ((24, 8), (27, 10), (25, 5)):
        cv.put(x, y, GOLD[4])
    return finish(cv)


@art("Navaja Plegable")
def folding_knife():
    cv = new()
    fill(cv, rotate(capsule(8, 22, 20, 22, 3), 14, 22, -30), WOOD, base=0.55)
    blade = poly([(18, 17), (27, 6), (28, 9), (21, 19)])
    fill(cv, blade, STEEL, base=0.75)
    fill(cv, circle(18, 18, 1.6), BRASS if False else GOLD, base=0.7)
    return finish(cv)


@art("Bolsa de Canicas")
def marble_bag():
    cv = new()
    bag = union(ellipse(13, 19, 8, 8), poly([(9, 12), (17, 12), (16, 8), (10, 8)]))
    fill(cv, bag, CLOTH_RED, base=0.55)
    fill(cv, rect(9, 11, 17, 12), GOLD, base=0.7)
    for x, y, c in ((22, 24, BLUE), (26, 20, GREEN), (25, 28, GOLD)):
        fill(cv, circle(x, y, 2.6), c, base=0.6)
        cv.put(x - 1, y - 1, WHITE)
    return finish(cv)


@art("Botas de Ratero")
def thief_boots():
    cv = new()
    for ox, oy, base in ((-4, -3, 0.35), (4, 2, 0.65)):
        boot = union(rect(8 + ox, 6 + oy, 15 + ox, 22 + oy),
                     poly([(8 + ox, 20 + oy), (20 + ox, 22 + oy), (20 + ox, 26 + oy), (8 + ox, 26 + oy)]))
        fill(cv, boot, [(24, 24, 30), (44, 42, 52), (66, 62, 76), (94, 90, 106), (140, 136, 150)], base=base)
        fill(cv, rect(8 + ox, 9 + oy, 15 + ox, 11 + oy), LEATHER, base=0.5)
    return finish(cv)


@art("Guante de Ladrón")
def thief_glove():
    cv = new()
    hand = union(rect(10, 13, 22, 24), rect(11, 24, 21, 29))
    fill(cv, hand, [(24, 24, 30), (44, 42, 52), (66, 62, 76), (94, 90, 106), (140, 136, 150)], base=0.55)
    for i, x in enumerate((10, 13, 16, 19)):
        fill(cv, rect(x, 6 - (i in (1, 2)) * 2, x + 3, 14), [(24, 24, 30), (44, 42, 52), (66, 62, 76),
                                                             (94, 90, 106), (140, 136, 150)], base=0.6)
    fill(cv, rotate(rect(22, 14, 25, 20), 22, 18, 30), [(24, 24, 30), (44, 42, 52), (66, 62, 76),
                                                         (94, 90, 106), (140, 136, 150)], base=0.5)
    fill(cv, circle(6, 8, 2.5), GOLD, base=0.8)                  # snatched coin
    return finish(cv)


@art("Veneno de Escorpión")
def scorpion_venom():
    cv = new()
    tail = [(6, 27), (7, 19), (12, 12), (19, 8), (25, 10)]
    for (a, b), r in zip(zip(tail, tail[1:]), (3.4, 3.1, 2.8, 2.5)):
        fill(cv, capsule(*a, *b, r), EARTH, base=0.55)
    for x, y in tail[1:4]:
        cv.put(x, y, EARTH[0])
    stinger = poly([(23, 7), (28, 7), (30, 11), (29, 16), (27, 12), (24, 12)])
    fill(cv, stinger, [(30, 20, 20), (60, 40, 36), (96, 66, 56), (140, 100, 84), (190, 150, 130)], base=0.55)
    fill(cv, circle(27, 20, 1.8), POISON, base=0.7, rim=False)
    fill(cv, circle(26, 25, 1.2), POISON, base=0.7, rim=False)
    return finish(cv)


_DARK_CLOTH = [(24, 24, 30), (44, 42, 52), (66, 62, 76), (94, 90, 106), (140, 136, 150)]


@art("Hilo de Seda Negra")
def black_silk():
    cv = new()
    fill(cv, rect(9, 8, 23, 24), WOOD, base=0.5)                # spool
    fill(cv, rect(11, 10, 21, 22), _DARK_CLOTH, base=0.55)
    for y in range(11, 22, 2):
        line(cv, 11, y, 21, y, _DARK_CLOTH[3], solid=False)
    fill(cv, rect(7, 6, 25, 9), WOOD, base=0.65)
    fill(cv, rect(7, 23, 25, 26), WOOD, base=0.45)
    line(cv, 21, 16, 29, 28, _DARK_CLOTH[3])
    cv.put(28, 4, WHITE)
    return finish(cv)


@art("Dado de Hueso")
def bone_die():
    cv = new()
    fill(cv, rotate(rect(8, 8, 24, 24), 16, 16, 15), BONE, base=0.6)
    for x, y in ((12, 12), (20, 20), (16, 16), (20, 12), (12, 20)):
        p = rotate(circle(x, y, 1.4), 16, 16, 15)
        fill(cv, p, BLACK, base=0.2, rim=False)
    line(cv, 9, 25, 13, 23, BONE[1])
    return finish(cv)


@art("Frasco de Neblina")
def mist_flask():
    cv = new()
    flask = union(circle(16, 20, 8), rect(13, 6, 19, 13))
    fill(cv, flask, GLASS, base=0.7)
    fill(cv, circle(16, 21, 6), [(110, 110, 130), (150, 150, 170), (190, 190, 205), (220, 220, 232), WHITE],
         base=0.6, rim=False)
    fill(cv, rect(12, 3, 20, 6), WOOD, base=0.6)
    for x, y, r in ((22, 6, 2.4), (26, 3, 1.8), (9, 4, 1.6)):
        fill(cv, circle(x, y, r), [(150, 150, 170), (190, 190, 205), (220, 220, 232), (240, 240, 248), WHITE],
             base=0.5, rim=False, solid=False)
    return finish(cv)


@art("Ganzúa")
def lockpick():
    cv = new()
    fill(cv, ring(9, 22, 5, 3), IRON, base=0.6)
    line(cv, 12, 19, 27, 4, STEEL[3])
    line(cv, 13, 19, 28, 4, STEEL[2])
    line(cv, 27, 4, 29, 7, STEEL[3])
    line(cv, 13, 25, 26, 13, STEEL[3])
    line(cv, 26, 13, 27, 10, STEEL[3])
    return finish(cv)


@art("Máscara de Arlequín")
def harlequin_mask():
    cv = new()
    mask = union(ellipse(16, 15, 13, 8), poly([(3, 12), (0, 6), (7, 9)]), poly([(29, 12), (32, 6), (25, 9)]))
    fill(cv, mask, RED, base=0.6)
    fill(cv, intersect(mask, rect(16, 0, 32, 32)) if 'intersect' in globals() else minus(mask, rect(0, 0, 16, 32)),
         _DARK_CLOTH, base=0.55)
    for x in (10, 22):
        fill(cv, ellipse(x, 14, 3.4, 2.2), BLACK, base=0.15, rim=False)
    fill(cv, poly([(16, 22), (18, 27), (14, 27)]), GOLD, base=0.7)
    sparkle(cv, 26, 22, GOLD[4], 1)
    return finish(cv)


@art("Capucha de Sombras")
def shadow_hood():
    cv = new()
    hood = poly([(16, 2), (27, 12), (28, 28), (4, 28), (5, 12)])
    fill(cv, hood, _DARK_CLOTH, base=0.5)
    fill(cv, ellipse(16, 18, 7, 8), BLACK, base=0.1, rim=False)
    for x in (13, 19):
        cv.put(x, 17, VIOLET[4])
    return finish(cv)


@art("Pañuelo Envenenado")
def poisoned_kerchief():
    cv = new()
    cloth = poly([(5, 8), (27, 6), (24, 18), (16, 27), (8, 18)])
    fill(cv, cloth, [(60, 70, 50), (90, 110, 70), (130, 150, 90), (170, 190, 120), (210, 226, 170)], base=0.6)
    for x, y in ((13, 13), (19, 16), (16, 20)):
        fill(cv, circle(x, y, 1.6), POISON, base=0.7, rim=False)
    fill(cv, circle(16, 29, 1.4), POISON, base=0.7, rim=False)
    return finish(cv)


@art("Dagas Gemelas")
def twin_daggers():
    cv = new()
    for deg in (-35, 35):
        blade = rotate(poly([(15, 2), (17, 2), (18, 18), (14, 18)]), 16, 16, deg)
        fill(cv, blade, STEEL, base=0.75)
        fill(cv, rotate(rect(11, 18, 21, 20), 16, 16, deg), GOLD, base=0.65)
        fill(cv, rotate(rect(15, 20, 17, 27), 16, 16, deg), LEATHER, base=0.5)
    return finish(cv)


@art("Cola de Zorro")
def fox_tail():
    cv = new()
    tail = rotate(union(ellipse(16, 15, 7, 12), circle(16, 5, 4)), 16, 16, 25)
    fill(cv, tail, ORANGE, base=0.6)
    fill(cv, rotate(ellipse(16, 4, 4, 4), 16, 16, 25), [(170, 170, 180), (210, 210, 218), (236, 236, 240),
                                                       (248, 248, 250), WHITE], base=0.7, rim=False)
    fill(cv, rotate(rect(14, 25, 18, 29), 16, 16, 25), GOLD, base=0.6)
    return finish(cv)


@art("Reloj de Bolsillo Robado")
def stolen_pocket_watch():
    cv = new()
    fill(cv, circle(16, 18, 10), GOLD, base=0.6)
    fill(cv, circle(16, 18, 7.5), PAPER, base=0.85, rim=False)
    fill(cv, ring(16, 5, 2.6, 1.2), GOLD, base=0.7)
    line(cv, 16, 18, 16, 13, INK)
    line(cv, 16, 18, 20, 19, INK)
    line(cv, 18, 6, 29, 2, GOLD[2], solid=False)                 # snapped chain
    line(cv, 9, 12, 13, 22, PAPER[1], solid=False)               # cracked glass
    return finish(cv)


@art("Medallón Singular")
def singular_medallion():
    cv = new()
    line(cv, 9, 2, 16, 8, GOLD[2])
    line(cv, 23, 2, 16, 8, GOLD[2])
    fill(cv, circle(16, 18, 10), SILVER, base=0.6)
    fill(cv, ring(16, 18, 10, 8.4), GOLD, base=0.6)
    fill(cv, poly([(16, 12), (19, 18), (16, 24), (13, 18)]), [(10, 60, 80), (20, 110, 140), (60, 170, 200),
                                                             (140, 220, 240), WHITE], base=0.6)
    return finish(cv)


@art("Corona del Rey Ladrón")
def thief_king_crown():
    cv = new()
    crown = poly([(4, 24), (4, 10), (10, 16), (16, 6), (22, 16), (28, 10), (28, 24)])
    fill(cv, crown, GOLD, base=0.6)
    fill(cv, rect(4, 22, 28, 26), GOLD, base=0.4)
    for x, c in ((10, RED), (16, GREEN), (22, BLUE)):
        fill(cv, circle(x, 20, 1.8), c, base=0.7)
    fill(cv, rotate(poly([(18, 2), (30, 13), (28, 15), (16, 4)]), 23, 8, 0), _DARK_CLOTH, base=0.5)  # thief's dagger
    fill(cv, poly([(19, 1), (21, 3), (17, 5)]) if False else rect(15, 1, 18, 4), GOLD, base=0.5)
    return finish(cv)


@art("Sello del Anticuario")
def antiquarian_seal():
    cv = new()
    fill(cv, rect(13, 4, 19, 16), WOOD, base=0.6)
    fill(cv, circle(16, 4, 3.2), WOOD, base=0.7)
    fill(cv, rect(10, 16, 22, 19), BRONZE, base=0.6)
    wax = union(circle(16, 25, 6), circle(10, 26, 2.5), circle(22, 24, 2.5))
    fill(cv, wax, [(60, 40, 20), (110, 80, 40), (170, 130, 60), (210, 176, 100), (240, 220, 160)], base=0.55)
    fill(cv, ring(16, 25, 3.6, 2.4), [(60, 40, 20), (90, 66, 32), (120, 92, 48), (150, 120, 70), (190, 160, 110)],
         base=0.35, rim=False)
    return finish(cv)
