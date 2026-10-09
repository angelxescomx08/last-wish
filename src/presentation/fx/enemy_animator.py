"""Per-enemy animation player with its own particles (idle, attack, hurt, cast, death).

Plays an :class:`~src.infrastructure.enemy_sprites.EnemySheet` by elapsed time
(never by frame count) and adds what a baked sheet cannot: a floor shadow, a
pulsing spectral floor glow, rising ghost wisps, and one-shot bursts timed to
the action (claw sparks on the strike, ectoplasm on a hit, soul motes while
dying, sparks spiralling into the chest while casting).

* Actions return to idle at their end (every non-death action ends on idle
  frame 0, so there is no pop). ``death`` latches and holds its last (empty)
  frame; particles still finish.
* ``play(name, delay=…)`` queues an action, so several enemies can be staggered.
* Particles live in a small pooled :class:`BurstParticles` in screen px; cues
  use the anchor of the previous draw.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass
from functools import lru_cache

import pygame

from src.infrastructure.enemy_sprites import EnemySheet
from src.presentation.fx.bursts import GLOW, SPARK, BurstParticles, soft_glow

MAX_DT = 0.1

_WISP = ((150, 255, 230), (90, 210, 190), (50, 140, 140), (26, 70, 80))
_ECTO = ((230, 255, 245), (130, 235, 215), (60, 170, 160), (40, 31, 64))
_SPARK = ((255, 255, 255), (200, 255, 240), (110, 220, 200))
_VIOLET = ((180, 160, 230), (116, 98, 160), (58, 45, 90))
_GLOW_COL = (40, 150, 140)

# Screen offsets from the anchor (ground point), for a ×2 sheet (the Espectro's).
CHEST = (-4, -96)
EYES = (-6, -124)
BODY = (0, -84)
CLAW = (-118, -80)          # where the lunge's claws land (towards the hero)


@dataclass(frozen=True)
class EnemyFxStyle:
    """Particle colours and cue points of one animated enemy (screen px from the anchor)."""
    wisp: tuple = _WISP          # ambient motes / cast motes
    ecto: tuple = _ECTO          # hurt splash
    spark: tuple = _SPARK        # strike sparks
    shreds: tuple = _VIOLET      # bits torn off on hurt
    glow: tuple = _GLOW_COL      # floor glow colour
    chest: tuple = CHEST
    eyes: tuple = EYES
    body: tuple = BODY
    claw: tuple = CLAW
    shadow_w: int = 150
    ambient_rise: float = 1.0    # ambient motes speed factor (spores drift slowly)
    ambient_heavy: bool = False  # ambient motes fall a little (ash, embers rise: False)
    blades: bool = False         # floating swords drawn around the enemy (El Caballero Hueco)


_TOX = ((236, 255, 160), (170, 230, 70), (110, 170, 50), (60, 100, 30))
_SPORE = ((250, 255, 214), (226, 236, 150), (180, 196, 96), (120, 130, 60))
_CAPBITS = ((238, 148, 132), (178, 52, 84), (96, 22, 58))
_ICHOR = ((255, 214, 226), (255, 110, 170), (214, 54, 96), (110, 20, 50))
_CHITIN = ((156, 140, 196), (76, 60, 106), (34, 26, 54))
_SILK = ((250, 250, 255), (220, 220, 236), (170, 170, 192))
_EMBER = ((255, 250, 220), (255, 214, 130), (255, 132, 40), (176, 58, 16))
_STEEL = ((235, 240, 250), (196, 202, 214), (134, 142, 160))
_ASH = ((140, 130, 128), (92, 86, 84), (62, 56, 58))

STYLES: dict[str, EnemyFxStyle] = {
    "wraith": EnemyFxStyle(),
    "mycelid": EnemyFxStyle(wisp=_SPORE, ecto=_TOX, spark=_TOX, shreds=_CAPBITS, glow=(60, 120, 30),
                            chest=(0, -126), eyes=(0, -116), body=(0, -96), claw=(-292, -14),
                            shadow_w=210, ambient_rise=0.55),
    "weaver": EnemyFxStyle(wisp=_SILK, ecto=_ICHOR, spark=_ICHOR, shreds=_CHITIN, glow=(120, 24, 70),
                           chest=(30, -96), eyes=(-70, -92), body=(10, -84), claw=(-120, -64),
                           shadow_w=230, ambient_rise=0.4, ambient_heavy=True),
    "knight": EnemyFxStyle(wisp=_EMBER, ecto=_EMBER, spark=_STEEL, shreds=_ASH, glow=(150, 60, 16),
                           chest=(-6, -124), eyes=(0, -178), body=(0, -110), claw=(-120, -100),
                           shadow_w=170, blades=True),
}

# Regular enemies (application/enemy_roster.py). Cue points measured on each sheet's idle
# frame (×2 px from the ground anchor); ``claw`` = where its hit lands (lunge, beam, flame).
_ACID = ((236, 255, 170), (170, 240, 80), (96, 190, 50), (40, 110, 30))
_FLESH = ((250, 236, 214), (214, 196, 170), (150, 140, 128), (86, 80, 90))
_EARTH = ((122, 96, 70), (84, 62, 46), (46, 34, 28))
_VIOLET_GLOW = ((240, 220, 255), (196, 150, 255), (140, 86, 220), (70, 40, 120))
_BLOOD = ((255, 200, 200), (230, 70, 80), (160, 24, 44), (80, 10, 26))
_FUR = ((150, 112, 120), (96, 66, 86), (54, 36, 52))
_BONE = ((246, 236, 214), (210, 190, 160), (140, 118, 100))
_TEAL_CAP = ((150, 200, 196), (70, 120, 124), (34, 62, 70))
_MOSS = ((200, 250, 220), (120, 220, 170), (60, 160, 120), (30, 90, 80))
_STONE = ((220, 226, 232), (150, 160, 172), (96, 104, 120), (56, 62, 76))
_MOSS_BITS = ((150, 210, 90), (90, 150, 60), (50, 90, 40))
_COINS = ((255, 250, 210), (255, 214, 90), (220, 150, 40), (130, 80, 20))
_WOOD = ((176, 120, 74), (118, 76, 46), (66, 40, 26))

STYLES.update({
    "slime": EnemyFxStyle(wisp=_ACID, ecto=_ACID, spark=_ACID, shreds=_ACID[1:], glow=(50, 130, 30),
                          chest=(0, -60), eyes=(-10, -72), body=(0, -50), claw=(-118, -40),
                          shadow_w=180, ambient_rise=0.5, ambient_heavy=True),
    "worm": EnemyFxStyle(wisp=_TOX, ecto=_FLESH, spark=_TOX, shreds=_EARTH, glow=(60, 100, 40),
                         chest=(-10, -110), eyes=(-30, -128), body=(0, -70), claw=(-118, -96),
                         shadow_w=150, ambient_rise=0.6),
    "eye": EnemyFxStyle(wisp=_VIOLET_GLOW, ecto=_ICHOR, spark=_VIOLET_GLOW, shreds=_ICHOR[1:],
                        glow=(100, 40, 150), chest=(0, -96), eyes=(-12, -108), body=(0, -92),
                        claw=(-170, -108), shadow_w=90),
    "skull": EnemyFxStyle(wisp=_EMBER, ecto=_EMBER, spark=_EMBER, shreds=_BONE, glow=(170, 70, 20),
                          chest=(10, -92), eyes=(0, -100), body=(10, -92), claw=(-150, -82),
                          shadow_w=110),
    "bat": EnemyFxStyle(wisp=_BLOOD, ecto=_BLOOD, spark=_BLOOD, shreds=_FUR, glow=(110, 20, 40),
                        chest=(0, -94), eyes=(-10, -108), body=(0, -92), claw=(-110, -90),
                        shadow_w=130, ambient_rise=0.7),
    "bomb": EnemyFxStyle(wisp=_EMBER, ecto=_FLESH, spark=_EMBER, shreds=_TEAL_CAP, glow=(160, 90, 20),
                         chest=(0, -84), eyes=(0, -60), body=(0, -70), claw=(-100, -62),
                         shadow_w=100),
    "golem": EnemyFxStyle(wisp=_MOSS, ecto=_STONE, spark=_STONE, shreds=_MOSS_BITS, glow=(40, 120, 110),
                          chest=(-10, -110), eyes=(-24, -140), body=(-10, -90), claw=(-150, -24),
                          shadow_w=190, ambient_rise=0.5, ambient_heavy=True),
    "acolyte": EnemyFxStyle(wisp=_EMBER, ecto=_EMBER, spark=_EMBER, shreds=_ASH, glow=(150, 70, 20),
                            chest=(-10, -110), eyes=(-20, -134), body=(-10, -90), claw=(-104, -70),
                            shadow_w=130, ambient_heavy=True),
    "imp": EnemyFxStyle(wisp=_EMBER, ecto=_BLOOD, spark=_EMBER, shreds=_BLOOD[1:], glow=(160, 50, 20),
                        chest=(10, -84), eyes=(0, -108), body=(10, -80), claw=(-112, -80),
                        shadow_w=100),
    "mimic": EnemyFxStyle(wisp=_COINS, ecto=_BLOOD, spark=_COINS, shreds=_WOOD, glow=(150, 110, 30),
                          chest=(0, -60), eyes=(0, -72), body=(0, -56), claw=(-124, -40),
                          shadow_w=170, ambient_rise=0.4, ambient_heavy=True),
})

# Elites (application/elites.py): cue points measured by each generator on idle frame 0.
_ASH_FALL = ((255, 212, 118), (250, 140, 40), (200, 70, 18), (78, 72, 72))
_RED_BLOOD = ((232, 70, 62), (176, 26, 30), (110, 12, 18), (56, 6, 10))
_HOOD = ((138, 54, 50), (106, 36, 38), (78, 25, 29), (34, 12, 16))
_SWAMP_MIST = ((184, 214, 164), (134, 174, 124), (92, 130, 96), (58, 86, 66))
_SWAMP_GOO = ((182, 246, 100), (100, 194, 54), (44, 122, 38), (22, 64, 30))
_HEX = ((236, 255, 196), (182, 246, 100), (210, 150, 255), (150, 74, 204))
_RAGS = ((106, 124, 70), (78, 98, 56), (58, 76, 48), (29, 41, 32))
_GRIT = ((176, 174, 169), (128, 124, 124), (92, 88, 92), (60, 56, 62))
_CHIPS = ((206, 204, 218), (138, 135, 157), (86, 83, 109), (48, 45, 68))
_AMBER = ((255, 252, 228), (255, 234, 164), (255, 192, 74), (226, 132, 28))
_FLAKES = ((222, 220, 214), (176, 174, 169), (124, 122, 119), (98, 96, 94))
_STEAM = ((255, 255, 255), (232, 242, 252), (186, 204, 222), (132, 150, 172))
_FUR_BLOOD = ((200, 146, 100), (166, 62, 52), (94, 26, 30), (36, 9, 13))
_RAGE = ((255, 255, 255), (255, 170, 90), (240, 80, 40), (176, 30, 20))
_DIRT = ((172, 156, 132), (130, 112, 92), (84, 53, 36), (43, 25, 20))
_VENOM = ((214, 255, 160), (122, 226, 72), (44, 140, 52), (18, 64, 34))
_ICHOR_RED = ((250, 222, 196), (184, 92, 78), (114, 38, 44), (52, 15, 27))
_GOLD = ((255, 244, 198), (255, 208, 104), (212, 146, 42), (146, 86, 22))
_SHELL = ((160, 70, 64), (78, 23, 34), (33, 11, 21), (9, 5, 10))

STYLES.update({
    "executioner": EnemyFxStyle(wisp=_ASH_FALL, ecto=_RED_BLOOD, spark=_EMBER, shreds=_HOOD,
                                glow=(150, 40, 20), chest=(-10, -104), eyes=(-21, -157),
                                body=(-14, -84), claw=(-148, -36), shadow_w=120,
                                ambient_rise=0.5, ambient_heavy=True),
    "hag": EnemyFxStyle(wisp=_SWAMP_MIST, ecto=_SWAMP_GOO, spark=_HEX, shreds=_RAGS,
                        glow=(60, 130, 40), chest=(-10, -88), eyes=(-35, -119), body=(-22, -68),
                        claw=(-268, -100), shadow_w=150, ambient_rise=0.5),
    "gargoyle": EnemyFxStyle(wisp=_GRIT, ecto=_CHIPS, spark=_AMBER, shreds=_FLAKES,
                             glow=(150, 100, 30), chest=(-12, -100), eyes=(-54, -134),
                             body=(8, -96), claw=(-138, -50), shadow_w=150, ambient_rise=0.5,
                             ambient_heavy=True),
    "minotaur": EnemyFxStyle(wisp=_STEAM, ecto=_FUR_BLOOD, spark=_RAGE, shreds=_DIRT,
                             glow=(150, 40, 20), chest=(-24, -122), eyes=(-57, -145),
                             body=(-10, -99), claw=(-255, -111), shadow_w=130,
                             ambient_rise=0.5, ambient_heavy=True),
    "scorpion": EnemyFxStyle(wisp=_VENOM, ecto=_ICHOR_RED, spark=_GOLD, shreds=_SHELL,
                             glow=(50, 130, 40), chest=(-64, -39), eyes=(-66, -56),
                             body=(-4, -48), claw=(-246, -37), shadow_w=260, ambient_rise=0.5,
                             ambient_heavy=True),
})

# Floating swords (El Caballero Hueco): orbit, launch timing and flight.
BLADE_ORBIT = (78.0, 20.0)        # ellipse radii around the body (px)
BLADE_CENTER = (0.0, -118.0)      # orbit centre from the anchor
BLADE_FIRST = 0.30                # s into "command" when the first sword flies
BLADE_GAP = 0.13                  # s between swords
BLADE_FLIGHT = 0.22               # s from the orbit to the hero
BLADE_REFORM = 0.45               # s before a thrown sword re-forms in the orbit
DEFAULT_TARGET = (-560.0, -96.0)  # hero chest from the anchor when the scene gives none


def style_for(sheet_id: str) -> EnemyFxStyle:
    return STYLES.get(sheet_id, STYLES["wraith"])


@lru_cache(maxsize=8)
def _shadow(w: int, h: int) -> pygame.Surface:
    s = pygame.Surface((w, h), pygame.SRCALPHA)
    for i in range(6, 0, -1):
        k = i / 6
        pygame.draw.ellipse(s, (0, 0, 0, int(26 * (1.2 - k) + 10)),
                            (w * (1 - k) / 2, h * (1 - k) / 2, w * k, h * k))
    return s


@lru_cache(maxsize=48)
def _floor_glow(level: int, color: tuple = _GLOW_COL, width: int = 190) -> pygame.Surface:
    """Flattened additive glow, ``level`` 1..6 in brightness."""
    k = level / 6
    base = soft_glow((int(color[0] * k), int(color[1] * k), int(color[2] * k)), 40)
    return pygame.transform.smoothscale(base, (width, 44))


class EnemyAnimator:
    """Animation state + particles of one animated enemy on screen."""

    def __init__(self, sheet: EnemySheet, *, seed: int = 0, phase: float = 0.0,
                 particles: int = 220) -> None:
        self.sheet = sheet
        self._rng = random.Random(seed)
        self._idle_time = phase % max(1e-6, sheet.seconds("idle"))
        self._action: str | None = None
        self._action_time = 0.0
        self._queue: list[list] = []                  # [name, delay]
        self._dead = False
        self._final = "death"                         # the action that ended it (death / explode)
        self._wisp_clock = self._rng.uniform(0.0, 0.2)
        self._fx_time = self._rng.uniform(0.0, 10.0)
        self._anchor: tuple[float, float] | None = None
        self._fired: set[str] = set()
        self.particles = BurstParticles(particles, seed=seed + 7)
        self.style = style_for(sheet.sheet_id)
        self._hits = 1                                # hits of the action playing (multi-hit)
        # Floating swords (style.blades): the scene sets ``blades`` (count) and ``target``.
        self.blades = 0
        self.target: tuple[float, float] | None = None
        self._blade_angle = self._rng.uniform(0.0, math.tau)
        self._blade_state: list[list] = []            # per sword: [mode, t, x0, y0, tx, ty]
        self._shown_blades = 0

    # ------------------------------------------------------------------ state
    @property
    def action(self) -> str | None:
        """Action currently playing (attack/hurt/cast/death), None while idle."""
        return self._action

    @property
    def dead(self) -> bool:
        return self._dead

    @property
    def death_done(self) -> bool:
        """The death animation has fully played (the sprite is gone)."""
        return self._dead and self._action_time >= self.sheet.seconds(self._final)

    @property
    def busy(self) -> bool:
        """An action is playing or queued."""
        if self._dead:
            return not self.death_done
        return self._action is not None or bool(self._queue)

    def seconds(self, name: str) -> float:
        return self.sheet.seconds(name)

    def strike_time(self) -> float:
        """Seconds from the start of ``attack`` to the frame where the claws land."""
        times = self.strike_times("attack")
        return times[0] if times else 0.0

    def strike_times(self, name: str, hits: int = 1) -> tuple[float, ...]:
        """When each of ``hits`` hits of action ``name`` lands (s from its start).

        Floating swords ("command" with ``style.blades``): one sword per hit, thrown
        ``BLADE_GAP`` apart. Otherwise the sheet's strike frames; extra hits follow the
        last strike 0.12 s apart. Empty when the action has no strike.
        """
        hits = max(1, hits)
        if name == "command" and self.style.blades:
            return tuple(BLADE_FIRST + k * BLADE_GAP + BLADE_FLIGHT for k in range(hits))
        base = list(self.sheet.strike_seconds(name))
        if not base:
            return ()
        while len(base) < hits:
            base.append(base[-1] + 0.12)
        return tuple(base[:max(hits, 1)])

    def play(self, name: str, *, delay: float = 0.0, hits: int = 1) -> None:
        """Start (or queue after ``delay`` s) an action. Unknown names are ignored."""
        if self._dead or name not in self.sheet.animations or name == "idle":
            return
        if delay > 0:
            self._queue.append([name, delay, hits])
            return
        self._start(name, hits)

    def _start(self, name: str, hits: int = 1) -> None:
        if self._dead:
            return
        if name == "death" or name in self.sheet.terminal:   # explode: dies acting
            self._dead = True
            self._final = name
            self._queue.clear()
            self._drop_blades()
        self._action = name
        self._action_time = 0.0
        self._fired = set()
        self._hits = max(1, hits)

    # ------------------------------------------------------------------ simulation
    def update(self, dt: float) -> None:
        dt = min(MAX_DT, max(0.0, dt))
        self._fx_time += dt
        for item in list(self._queue):
            item[1] -= dt
            if item[1] <= 0:
                self._queue.remove(item)
                self._start(item[0], item[2] if len(item) > 2 else 1)
        if self._action is not None:
            self._action_time += dt
            self._cues()
            if not self._dead and self._action_time >= self.sheet.seconds(self._action):
                self._action = None
                self._action_time = 0.0
                self._idle_time = 0.0
        else:
            self._idle_time = (self._idle_time + dt) % max(1e-6, self.sheet.seconds("idle"))
        self._ambient(dt)
        if self.style.blades:
            self._update_blades(dt)
        self.particles.update(dt)

    def _once(self, key: str, at: float) -> bool:
        if key in self._fired or self._action_time < at:
            return False
        self._fired.add(key)
        return True

    def _cues(self) -> None:
        if self._anchor is None:
            return
        ax, ay = self._anchor
        p, r, st = self.particles, self._rng, self.style
        name = self._action
        strikes = self.strike_times(name, self._hits) if name not in ("hurt", "death", "cast") else ()
        if not (name == "command" and st.blades):            # flying swords spark on their own
            for k, at in enumerate(strikes):
                if self._once(f"strike{k}", at - 0.05):
                    x, y = ax + st.claw[0], ay + st.claw[1]
                    p.burst(x, y, 22, palette=st.spark, speed=(160, 420),
                            angle=(math.pi * 0.55, math.pi * 1.25), life=(0.18, 0.4), size=(1.5, 2.5),
                            style=SPARK, drag=4.0)
                    p.burst(x, y, 14, palette=st.wisp, speed=(40, 160), life=(0.4, 0.8), size=(2, 4),
                            drag=3.0, gravity=-60, spread=18)
                    p.burst(x, y, 3, palette=st.wisp, speed=(0, 30), life=(0.25, 0.4), size=(26, 36),
                            style=GLOW, drag=4.0)
        if name in self.sheet.terminal and strikes and self._once("boom", strikes[0]):
            x, y = ax + st.body[0], ay + st.body[1]
            p.burst(x, y, 60, palette=st.spark, speed=(200, 560), life=(0.3, 0.8), size=(1.5, 3),
                    style=SPARK, drag=2.5)
            p.burst(x, y, 40, palette=st.wisp, speed=(80, 300), life=(0.5, 1.2), size=(3, 6),
                    drag=2.0, gravity=-40, spread=20)
            p.burst(x, y, 24, palette=_ASH, speed=(30, 140), life=(0.8, 1.6), size=(5, 9),
                    drag=1.5, gravity=-70, spread=24)
            p.burst(x, y, 4, palette=st.spark, speed=(0, 20), life=(0.3, 0.5), size=(90, 120),
                    style=GLOW, drag=4.0)
        if name == "hurt" and self._once("splash", 0.0):
            x, y = ax + st.body[0], ay + st.body[1]
            p.burst(x, y, 26, palette=st.ecto, speed=(90, 280), angle=(-math.pi * 0.45, math.pi * 0.45),
                    life=(0.35, 0.8), size=(2, 4), drag=2.2, gravity=380, spread=10)
            p.burst(x, y, 10, palette=st.shreds, speed=(60, 200), life=(0.3, 0.6), size=(2, 3),
                    drag=2.5, gravity=200, spread=14)
            p.burst(x, y, 2, palette=st.ecto, speed=(0, 10), life=(0.15, 0.25), size=(36, 46),
                    style=GLOW, drag=4.0)
        elif name in ("cast", "spores", "web", "command"):
            if self._once("charge", 0.0):
                p.implode(ax + st.chest[0], ay + st.chest[1], 24, palette=st.wisp, radius=(70, 130),
                          life=(0.35, 0.55))
            if name == "cast" and self._once("rune", 0.3):
                for _ in range(16):
                    a = r.uniform(0, math.tau)
                    p.emit(ax + math.cos(a) * 52, ay - 2 + math.sin(a) * 12, 0, r.uniform(-90, -40),
                           life=r.uniform(0.6, 1.1), palette=st.wisp, size=r.uniform(2, 3), drag=1.0)
                p.burst(ax + st.chest[0], ay + st.chest[1], 2, palette=st.wisp, speed=(0, 10),
                        life=(0.3, 0.45), size=(40, 52), style=GLOW, drag=4.0)
        elif name == "death":
            if self._once("pop", 0.0):
                x, y = ax + st.body[0], ay + st.body[1]
                p.burst(x, y, 30, palette=st.ecto, speed=(120, 320), life=(0.4, 0.9), size=(2, 4),
                        drag=2.0, gravity=300, spread=12)
                p.burst(ax + st.eyes[0], ay + st.eyes[1], 3, palette=st.ecto, speed=(0, 10),
                        life=(0.3, 0.5), size=(40, 56), style=GLOW, drag=4.0)
            total = self.sheet.seconds("death")
            u = self._action_time / max(1e-6, total)
            if 0.2 < u < 0.95:                        # motes torn off the dissolving front
                front = ay - 8 - (u - 0.2) / 0.75 * 170
                for _ in range(3):
                    p.emit(ax + r.uniform(-44, 48), front + r.uniform(-8, 8), r.uniform(-25, 25),
                           r.uniform(-140, -60), life=r.uniform(0.5, 1.1), palette=st.wisp,
                           size=r.uniform(2, 4), drag=1.2)
            if self._once("soul", total * 0.8):
                x, y = ax + st.eyes[0], ay + st.eyes[1]
                p.burst(x, y, 24, palette=st.spark, speed=(100, 300), life=(0.3, 0.7), size=(1.5, 2.5),
                        style=SPARK, drag=3.0)
                p.burst(x, y, 6, palette=st.wisp, speed=(10, 60), angle=(-math.pi * 0.7, -math.pi * 0.3),
                        life=(0.8, 1.4), size=(14, 24), style=GLOW, drag=0.5, gravity=-90)

    # ------------------------------------------------------------------ floating swords
    def _blade_home(self, k: int, n: int) -> tuple[float, float, float]:
        """Orbit position (x, y) of sword ``k`` of ``n`` and its depth (-1 back .. 1 front)."""
        ax, ay = self._anchor or (0.0, 0.0)
        a = self._blade_angle + k * math.tau / max(1, n)
        bob = 4 * math.sin(self._fx_time * 2.2 + k * 1.7)
        return (ax + BLADE_CENTER[0] + math.cos(a) * BLADE_ORBIT[0],
                ay + BLADE_CENTER[1] + math.sin(a) * BLADE_ORBIT[1] + bob, math.sin(a))

    def _update_blades(self, dt: float) -> None:
        n = max(0, int(self.blades)) if not self._dead else 0
        self._blade_angle = (self._blade_angle + dt * 0.9) % math.tau
        while len(self._blade_state) < n:                 # a new sword forms out of embers
            self._blade_state.append(["form", 0.0, 0.0, 0.0, 0.0, 0.0])
            if self._anchor is not None:
                x, y, _ = self._blade_home(len(self._blade_state) - 1, n)
                self.particles.implode(x, y, 16, palette=_EMBER, radius=(40, 80), life=(0.3, 0.45))
        if not self._dead:
            del self._blade_state[n:]
        for k, b in enumerate(self._blade_state):
            b[1] += dt
            if b[0] == "form" and b[1] > 0.35:
                b[0], b[1] = "orbit", 0.0
            elif b[0] == "fly" and b[1] >= BLADE_FLIGHT:
                b[0], b[1] = "gone", 0.0
                self.particles.burst(b[4], b[5], 18, palette=_STEEL, speed=(160, 380),
                                     angle=(math.pi * 0.6, math.pi * 1.4), life=(0.15, 0.35),
                                     size=(1.5, 2.5), style=SPARK, drag=4.0)
                self.particles.burst(b[4], b[5], 2, palette=_EMBER, speed=(0, 20), life=(0.2, 0.3),
                                     size=(22, 30), style=GLOW, drag=4.0)
            elif b[0] == "gone" and b[1] >= BLADE_REFORM:
                b[0], b[1] = "form", 0.0
        # launches during "command": sword k flies at BLADE_FIRST + k * BLADE_GAP
        if self._action == "command" and n > 0 and self._anchor is not None:
            ax, ay = self._anchor
            tx, ty = self.target or (ax + DEFAULT_TARGET[0], ay + DEFAULT_TARGET[1])
            for h in range(self._hits):
                if self._once(f"blade{h}", BLADE_FIRST + h * BLADE_GAP):
                    k = h % n
                    x, y, _ = self._blade_home(k, n)
                    jitter = (self._rng.uniform(-14, 14), self._rng.uniform(-22, 22))
                    self._blade_state[k][:] = ["fly", 0.0, x, y, tx + jitter[0], ty + jitter[1]]

    def _drop_blades(self) -> None:
        if self._anchor is None:
            self._blade_state.clear()
            return
        n = len(self._blade_state)
        for k in range(n):
            x, y, _ = self._blade_home(k, n)
            self.particles.burst(x, y, 10, palette=_EMBER, speed=(40, 160), life=(0.3, 0.7),
                                 size=(2, 3), drag=2.0, gravity=200)
        self._blade_state.clear()

    def _blade_frame(self, angle: float) -> pygame.Surface:
        frames = self.sheet.blade_frames
        k = int(round((angle % math.tau) / math.tau * len(frames))) % len(frames)
        return frames[k]

    def _draw_blades(self, surface: pygame.Surface, front: bool) -> None:
        if not self.sheet.blade_frames or not self._blade_state:
            return
        n = len(self._blade_state)
        for k, b in enumerate(self._blade_state):
            mode, t = b[0], b[1]
            if mode == "gone":
                continue
            x, y, depth = self._blade_home(k, n)
            if mode == "fly":
                if not front:
                    continue
                img = self._blade_frame(math.atan2(b[5] - b[3], b[4] - b[2]))
                for lag, alpha in ((0.09, 70), (0.045, 130)):      # motion trail
                    u0 = max(0.0, min(1.0, (t - lag) / BLADE_FLIGHT)) ** 1.6
                    ghost = img.copy()
                    ghost.set_alpha(alpha)
                    surface.blit(ghost, ghost.get_rect(center=(int(b[2] + (b[4] - b[2]) * u0),
                                                               int(b[3] + (b[5] - b[3]) * u0))))
                u = min(1.0, t / BLADE_FLIGHT) ** 1.6              # accelerates into the hero
                x, y = b[2] + (b[4] - b[2]) * u, b[3] + (b[5] - b[3]) * u
            else:
                if (depth >= 0) != front:
                    continue
                img = self._blade_frame(math.pi / 2 + 0.25 * math.cos(self._blade_angle + k))
                if mode == "form":
                    img = img.copy()
                    img.set_alpha(int(255 * min(1.0, t / 0.35)))
            surface.blit(img, img.get_rect(center=(int(x), int(y))))

    def _ambient(self, dt: float) -> None:
        if self._anchor is None or self._dead:
            return
        self._wisp_clock -= dt
        if self._wisp_clock > 0:
            return
        self._wisp_clock += self._rng.uniform(0.12, 0.26)
        ax, ay = self._anchor
        r = self._rng
        st = self.style
        k = st.ambient_rise
        x = ax + r.uniform(-st.shadow_w * 0.3, st.shadow_w * 0.32)
        if st.ambient_heavy:                             # silk motes drift down from above
            self.particles.emit(x, ay - r.uniform(60, 130), r.uniform(-6, 6), r.uniform(4, 14),
                                life=r.uniform(1.2, 2.0), palette=st.wisp, size=r.uniform(1.0, 2.0),
                                drag=0.3)
        elif r.random() < 0.55:
            self.particles.emit(x, ay - r.uniform(8, 30), r.uniform(-8, 8), r.uniform(-50, -22) * k,
                                life=r.uniform(1.0, 1.8) / max(0.5, k), palette=st.wisp,
                                size=r.uniform(1.5, 3.0), drag=0.3)
        else:
            self.particles.emit(x, ay - r.uniform(10, 40), r.uniform(-6, 6), r.uniform(-30, -14) * k,
                                life=r.uniform(1.2, 2.0), palette=st.wisp, size=r.uniform(6, 11),
                                style=GLOW, drag=0.2)

    # ------------------------------------------------------------------ drawing
    def current_frame(self) -> pygame.Surface:
        if self._action is not None:
            return self.sheet.frame(self._action, self._action_time)
        return self.sheet.frame("idle", self._idle_time)

    def draw(self, surface: pygame.Surface, anchor: tuple[float, float]) -> None:
        """Shadow, floor glow, sprite and particles; ``anchor`` = ground point under the enemy."""
        self._anchor = (float(anchor[0]), float(anchor[1]))
        ax, ay = int(anchor[0]), int(anchor[1])
        fade = 1.0
        if self._dead:
            fade = max(0.0, 1.0 - self._action_time / max(1e-6, self.sheet.seconds(self._final)))
        st = self.style
        if fade > 0:
            sw = st.shadow_w
            sh = _shadow(sw, 26)
            if fade < 1.0:
                sh = sh.copy()
                sh.set_alpha(int(255 * fade))
            surface.blit(sh, (ax - sw // 2, ay - 13))
            pulse = 0.5 + 0.5 * math.sin(self._fx_time * 2.4)
            boost = 2 if self._action not in (None, "hurt", "death") else 0
            level = max(1, min(6, int((2 + 2 * pulse + boost) * fade + 0.5)))
            gw = sw + 40
            glow = _floor_glow(level, st.glow, gw)
            surface.blit(glow, (ax - gw // 2, ay - 22), special_flags=pygame.BLEND_RGB_ADD)
        if st.blades:
            self._draw_blades(surface, front=False)
        if not self.death_done:
            frame = self.current_frame()
            w, h = self.sheet.anchor
            surface.blit(frame, (ax - w, ay - h))
        if st.blades:
            self._draw_blades(surface, front=True)
        self.particles.draw(surface)
