"""Gachapón room: pay gold, turn the crank, open a capsule, get a random relic.

Two pulls (``domain/gacha.py``): **Tirada normal** (usual relic odds) and
**Tirada estelar** (dearer, never Común, double golden chance). Every pull makes
the next one more expensive for the whole run. The pull resolves the moment it
is paid (``application.gacha.pull``: gold, relic, chroma); the screen then acts
it out, so leaving mid-animation never loses the relic.

Phases (``phase``)::

  idle     the machine hums: chasing bulbs, glass glints, capsules bob
  coin     a gold coin flies from the purse into the slot (clink, sparks)
  crank    the brass knob turns twice; capsules jostle; the bulbs race — in the
           prize's tier colour for Épica / Legendaria (a tease)
  drop     the capsule falls out of the chute, bounces twice and hops to the stage
  present  the big capsule floats in a halo of its tier colour and shakes once
           per tier step; click (or wait) to open
  open     flash, the halves fly apart, a particle burst sized by tier, light
           rays for Rara+, screen shake for Épica+, gold confetti for Legendaria;
           the relic pops out
  reveal   name, tier, description (golden note); click to keep it
  collect  the relic flies to the relic counter → idle

Clicks / Space skip ahead (coin, crank and drop jump to present; open jumps to
reveal). Keys: 1 = normal pull, 2 = stellar pull. ``Salir`` sets ``cleared``.
"""
from __future__ import annotations

import math
import random

import pygame

from src.application.gacha import (PullResult, accept, can_pull, decline, gacha_odds, gacha_price,
                                  pull)
from src.domain.chroma import chroma_def, chroma_title
from src.domain.gacha import PRICE_GROWTH, PULLS, PullKind
from src.domain.rarity import Rarity, rarity_label
from src.domain.run import Run
from src.infrastructure import colors
from src.infrastructure.audio import SoundPlayer
from src.infrastructure.fonts import FontRegistry
from src.infrastructure.gacha_assets import GachaAssets, load_gacha_assets
from src.infrastructure.sprite_loader import SpriteLoader
from src.presentation.fx import chroma_fx
from src.presentation.fx.bursts import GLOW, SPARK, SQUARE, BurstParticles, scaled, soft_glow
from src.presentation.ui.card_widget import RARITY_COLOR, _wrap
from src.presentation.ui.dungeon_backdrop import DungeonBackdrop

Color = tuple[int, int, int]

# ---------------------------------------------------------------- layout (1280×720)
_MACHINE_TOPLEFT = (272, 132)
_FLOOR_Y = 548                         # where the capsule bounces
_STAGE = (742.0, 292.0)                # where the prize capsule / relic is presented
_PANEL_X = 960
_BTN_W, _BTN_H = 292, 92
_BTN_NORMAL = pygame.Rect(_PANEL_X, 150, _BTN_W, _BTN_H)
_BTN_STELLAR = pygame.Rect(_PANEL_X, 256, _BTN_W, _BTN_H)
_EXIT = pygame.Rect(1100, 654, 150, 44)
_BTN_KEEP = pygame.Rect(0, 0, 160, 44)       # placed under the relic panel at draw time
_BTN_DECLINE = pygame.Rect(0, 0, 160, 44)
_PURSE = (1200, 35)                    # the shared gold counter (the coin flies from it)
_RELIC_COUNTER = (110, 96)             # where a kept relic flies to

# ---------------------------------------------------------------- timing (s)
COIN_T = 0.75
CRANK_T = 1.9
THUNK_AT = 0.86                         # fraction of the crank when the capsule drops inside
FALL_T = 0.78                          # fall + two bounces
HOP_T = 0.55                           # hop from the floor to the stage
DROP_T = FALL_T + HOP_T
SHAKE_T = 0.34                         # one anticipation shake while presenting
PRESENT_AUTO = 6.0                     # opens by itself after this long
OPEN_T = 1.05
COLLECT_T = 0.55
DISCARD_T = 0.6

_TIERS = list(Rarity)
_GOLD = ((255, 250, 210), (255, 214, 90), (230, 150, 30), (140, 80, 10))
_DUST = ((150, 140, 140), (110, 100, 104), (80, 72, 78))
_WHITE = (255, 255, 255)


def _clamp01(t: float) -> float:
    return 0.0 if t < 0 else 1.0 if t > 1 else t


def ease_out_cubic(t: float) -> float:
    t = _clamp01(t)
    return 1 - (1 - t) ** 3


def smoothstep(t: float) -> float:
    t = _clamp01(t)
    return t * t * (3 - 2 * t)


def ease_out_back(t: float, s: float = 1.9) -> float:
    t = _clamp01(t) - 1
    return 1 + (s + 1) * t ** 3 + s * t ** 2


def desc_text(relic) -> str:
    """Relic description plus its chroma note (golden: effects x2)."""
    if relic.chroma is None:
        return relic.description
    return relic.description + " " + chroma_def(relic.chroma).short_note + "."


def tier_color(rarity: Rarity) -> Color:
    c = RARITY_COLOR[rarity]
    return (c.r, c.g, c.b)


def tier_palette(rarity: Rarity) -> tuple[Color, ...]:
    base = tier_color(rarity)
    return (_WHITE, scaled(base, 1.25), base, scaled(base, 0.6))


def _make_rays(color: Color, size: int = 640) -> list[pygame.Surface]:
    """Additive light-ray fan at 4 brightness levels (rotated when drawn)."""
    r = size // 2
    base = pygame.Surface((size, size))
    base.fill((0, 0, 0))
    n = 12
    for i in range(n):
        a0 = i * math.tau / n
        a1 = a0 + math.tau / n * 0.45
        pygame.draw.polygon(base, scaled(color, 0.85), [
            (r, r), (r + math.cos(a0) * r, r + math.sin(a0) * r), (r + math.cos(a1) * r, r + math.sin(a1) * r)])
    base.blit(soft_glow((255, 255, 255), r), (0, 0), special_flags=pygame.BLEND_RGB_MULT)
    out = []
    for k in (0.25, 0.5, 0.75, 1.0):
        s = base.copy()
        s.fill(scaled((255, 255, 255), k), special_flags=pygame.BLEND_RGB_MULT)
        out.append(s)
    return out


class GachaScene:
    def __init__(self, run: Run, fonts: FontRegistry, *, sound: SoundPlayer | None = None,
                 seed: int = 3) -> None:
        self._run = run
        self._fonts = fonts
        self._sound = sound if sound is not None else SoundPlayer()
        self._sprites = SpriteLoader()
        self._assets: GachaAssets | None = load_gacha_assets()
        self._backdrop = DungeonBackdrop(seed=seed + 11, budget=0.6)
        self._rng = random.Random(seed)
        self._fx = BurstParticles(900, seed=seed)
        self._time = 0.0
        self._phase = "idle"
        self._t = 0.0                           # time in the current phase
        self._result: PullResult | None = None
        self._shake = 0.0                       # screen shake amplitude (px)
        self._flash = 0.0                       # white flash 0..1
        self._fired: set[str] = set()
        self._hovered: str | None = None
        self._feedback = ""
        self._feedback_t = 0.0
        self._rays: dict[Rarity, list[pygame.Surface]] = {}
        self._icon_cache: dict[str, pygame.Surface | None] = {}
        self._pile = self._make_pile()
        self._sparkle_clock = 0.0
        self.cleared = False
        self.pulls_made = 0
        self.gold_hud_pos = ("topright", (1268, 12))      # the shared gold counter (SceneManager)
        self._focus = 0.0                       # spotlight: darkens the room around the machine
        self._pulse = 0.0                       # squash pulse on each quarter turn of the crank
        self._jump = 0.0                        # the machine hops when the capsule drops inside
        self._bulb_flash = 0.0                  # every bulb lit (coin in, thunk)
        self._bolts: list[list] = []            # [points, colour, age, life]
        self._rings: list[list] = []            # [x, y, age, life, colour, max radius]
        self._vignette: pygame.Surface | None = None
        self._beam: pygame.Surface | None = None
        self._layer: pygame.Surface | None = None
        self._shade: pygame.Surface | None = None      # built once at the first draw
        self._band: pygame.Surface | None = None

    # ------------------------------------------------------------------ state
    @property
    def phase(self) -> str:
        return self._phase

    @property
    def result(self) -> PullResult | None:
        return self._result

    @property
    def is_animating(self) -> bool:
        return self._phase not in ("idle", "reveal")

    @property
    def particle_count(self) -> int:
        return self._fx.count

    def _tier(self) -> Rarity:
        if self._result is not None and self._result.relic is not None:
            return self._result.relic.rarity
        return Rarity.COMMON

    def _tier_index(self) -> int:
        return _TIERS.index(self._tier())

    def _set_phase(self, name: str) -> None:
        self._phase = name
        self._t = 0.0
        self._fired = set()

    def _once(self, key: str, at: float = 0.0) -> bool:
        if key in self._fired or self._t < at:
            return False
        self._fired.add(key)
        return True

    # ------------------------------------------------------------------ geometry
    def _machine_point(self, name: str) -> tuple[float, float]:
        mx, my = _MACHINE_TOPLEFT
        if self._assets is not None:
            px, py = self._assets.point(name)
        else:
            px, py = {"slot": (128, 264), "crank": (128, 300)}.get(name, (128, 300))
        return mx + px, my + py

    def _chute_mouth(self) -> tuple[float, float]:
        mx, my = _MACHINE_TOPLEFT
        if self._assets is not None:
            r = self._assets.rect("chute")
            return mx + r.centerx, my + r.centery
        return mx + 128, my + 340

    def _box(self) -> pygame.Rect:
        mx, my = _MACHINE_TOPLEFT
        if self._assets is not None:
            return self._assets.rect("box").move(mx, my)
        return pygame.Rect(mx + 24, my + 60, 208, 168)

    def _make_pile(self) -> list[list[float]]:
        """Capsules resting in the glass box: [x, y, colour index, phase]."""
        box = self._box()
        r = random.Random(17)
        out = []
        size = 32
        rows = 4
        for row in range(rows):
            n = 7 - (row // 2)
            y = box.bottom - size * 0.5 - 2 - row * (size * 0.72)
            for k in range(n):
                x = box.x + size * 0.6 + k * (box.width - size * 1.2) / max(1, n - 1)
                x += (size * 0.36 if row % 2 else 0) + r.uniform(-4, 4)
                if row == rows - 1 and r.random() < 0.4:
                    continue
                if x > box.right - size * 0.5:
                    continue
                out.append([x, y + r.uniform(-3, 3), r.randrange(6), r.uniform(0, math.tau)])
        return out

    # ------------------------------------------------------------------ input
    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.MOUSEMOTION:
            self._hovered = self._hit(event.pos)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self._click(event.pos)
        elif event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_SPACE, pygame.K_RETURN, pygame.K_KP_ENTER):
                self.advance()
            elif event.key in (pygame.K_r, pygame.K_BACKSPACE, pygame.K_DELETE):
                self.decline()
            elif event.key in (pygame.K_1, pygame.K_KP1):
                self.start_pull(PullKind.NORMAL)
            elif event.key in (pygame.K_2, pygame.K_KP2):
                self.start_pull(PullKind.STELLAR)

    def _hit(self, pos) -> str | None:
        if self._phase == "reveal":
            if _BTN_KEEP.collidepoint(pos):
                return "keep"
            if _BTN_DECLINE.collidepoint(pos):
                return "decline"
            return None
        if _BTN_NORMAL.collidepoint(pos):
            return "normal"
        if _BTN_STELLAR.collidepoint(pos):
            return "stellar"
        if _EXIT.collidepoint(pos):
            return "exit"
        return None

    def _click(self, pos) -> None:
        hit = self._hit(pos)
        if self._phase == "idle":
            if hit == "normal":
                self.start_pull(PullKind.NORMAL)
            elif hit == "stellar":
                self.start_pull(PullKind.STELLAR)
            elif hit == "exit":
                self._sound.play_cancel()
                self.cleared = True
            return
        if self._phase == "reveal":                 # only the two buttons decide
            if hit == "keep":
                self.keep()
            elif hit == "decline":
                self.decline()
            return
        self.advance()

    def start_pull(self, kind: PullKind) -> bool:
        """Pay and start the show. False (with a message) when busy or too poor."""
        if self._phase != "idle":
            return False
        result = pull(self._run, kind)
        if not result.success:
            self._feedback, self._feedback_t = result.message, 2.0
            self._sound.play_error()
            return False
        self._result = result
        self.pulls_made += 1
        self._sound.play_purchase()
        self._set_phase("coin")
        return True

    def advance(self) -> None:
        """Click / Space: skip ahead or move on (in the reveal, Space keeps the relic)."""
        if self._phase in ("coin", "crank", "drop"):
            self._set_phase("present")
            self._t = 0.25
            self._focus = max(self._focus, 0.6)
        elif self._phase == "present":
            self._open()
        elif self._phase == "open":
            self._set_phase("reveal")
        elif self._phase == "reveal":
            self.keep()

    def keep(self) -> bool:
        """Keep the revealed relic: it is added to the run and flies to the relic counter."""
        if self._phase != "reveal" or self._result is None:
            return False
        accept(self._run, self._result)
        self._set_phase("collect")
        self._sound.play_confirm()
        return True

    def decline(self) -> bool:
        """Throw the revealed relic away (the gold is spent anyway)."""
        if self._phase != "reveal" or self._result is None:
            return False
        decline(self._result)
        self._set_phase("discard")
        x, y = _STAGE
        self._fx.burst(x, y, 40, palette=_DUST, speed=(60, 240), life=(0.4, 0.9), size=(3, 6),
                       drag=2.5, gravity=-60)
        self._fx.burst(x, y, 2, palette=((90, 80, 90),), speed=(0, 10), life=(0.3, 0.5), size=(50, 70),
                       style=GLOW, drag=4.0)
        self._sound.play_cancel()
        return True

    def skip_to_reveal(self) -> None:
        while self._phase not in ("reveal", "idle"):
            self.advance()

    # ------------------------------------------------------------------ simulation
    def update(self, dt: float) -> None:
        dt = min(0.1, max(0.0, dt))
        self._time += dt
        self._t += dt
        self._backdrop.update(dt)
        self._feedback_t = max(0.0, self._feedback_t - dt)
        self._shake = max(0.0, self._shake - dt * 30)
        self._flash = max(0.0, self._flash - dt * 3.2)
        self._pulse = max(0.0, self._pulse - dt * 5.0)
        self._jump = max(0.0, self._jump - dt * 3.5)
        self._bulb_flash = max(0.0, self._bulb_flash - dt * 2.0)
        focus_target = {"coin": 0.55, "crank": 1.0, "drop": 0.9, "present": 0.75, "open": 0.7,
                        "reveal": 0.6}.get(self._phase, 0.0)
        self._focus += (focus_target - self._focus) * min(1.0, dt * 4.0)
        for b in self._bolts:
            b[2] += dt
        self._bolts = [b for b in self._bolts if b[2] < b[3]]
        for r in self._rings:
            r[2] += dt
        self._rings = [r for r in self._rings if r[2] < r[3]]
        getattr(self, f"_update_{self._phase}")(dt)
        self._ambient(dt)
        self._fx.update(dt)

    def _update_idle(self, dt: float) -> None:
        pass

    def _update_coin(self, dt: float) -> None:
        if self._once("clink", COIN_T * 0.72):
            x, y = self._machine_point("slot")
            self._fx.burst(x, y, 26, palette=_GOLD, speed=(80, 300), life=(0.2, 0.5), size=(1.5, 2.5),
                           style=SPARK, drag=4.0)
            self._fx.burst(x, y, 2, palette=_GOLD, speed=(0, 10), life=(0.25, 0.35), size=(34, 44),
                           style=GLOW, drag=4.0)
            self._rings.append([x, y, 0.0, 0.4, (255, 214, 90), 46])
            self._bulb_flash = 1.0                       # the machine wakes up
            self._pulse = 1.0
            self._sound.play_nav()
        if self._t >= COIN_T:
            self._set_phase("crank")

    def _crank_u(self) -> float:
        return _clamp01(self._t / CRANK_T)

    def _update_crank(self, dt: float) -> None:
        turns = 12                                            # quarter turns, getting faster
        for k in range(turns):
            at = CRANK_T * THUNK_AT * (1 - (1 - k / turns) ** 1.35)
            if self._once(f"tick{k}", at):
                x, y = self._machine_point("crank")
                self._fx.burst(x, y, 6 + k, palette=_GOLD, speed=(60, 180 + 10 * k), life=(0.15, 0.35),
                               size=(1, 2.5), style=SPARK, drag=5.0)
                self._pulse = 0.6 + 0.4 * k / turns
                self._sound.play_nav()
        tier = self._tier_index()
        box = self._box()
        # energy arcs on the glass: little sparks for everyone, real lightning for Épica+
        u = self._crank_u()
        chance = (0.25 + 0.6 * u) * (1.0 if tier >= 3 else 0.45)
        if 0.15 < u < THUNK_AT and self._rng.random() < chance:
            color = tier_color(self._tier()) if tier >= 3 else (200, 220, 255)
            self._spawn_bolt(box, color, big=tier >= 3)
        if tier >= 3 and self._once("tease", CRANK_T * 0.55):
            self._fx.implode(box.centerx, box.centery, 40, palette=tier_palette(self._tier()),
                             radius=(120, 200), life=(0.35, 0.55))
            self._flash = 0.25
        if self._once("thunk", CRANK_T * THUNK_AT):         # the capsule drops inside: KA-CHUNK
            self._jump = 1.0
            self._shake = 6 + 2 * tier
            self._bulb_flash = 1.0
            cx, cy = self._chute_mouth()
            self._fx.burst(cx, cy - 10, 30 + 10 * tier, palette=tier_palette(self._tier()),
                           speed=(120, 380), angle=(math.pi * 1.05, math.pi * 1.95), life=(0.3, 0.7),
                           size=(2, 4), drag=2.5, gravity=300)
            self._rings.append([cx, cy, 0.0, 0.45, tier_color(self._tier()), 120])
            self._sound.play_card()
        if self._t >= CRANK_T:
            self._set_phase("drop")

    def _spawn_bolt(self, box: pygame.Rect, color: Color, *, big: bool) -> None:
        """A jagged lightning arc between two points on the glass edge (or a short spark)."""
        r = self._rng

        def edge_point():
            side = r.randrange(4)
            if side == 0:
                return r.uniform(box.left, box.right), box.top + 4
            if side == 1:
                return r.uniform(box.left, box.right), box.bottom - 4
            if side == 2:
                return box.left + 4, r.uniform(box.top, box.bottom)
            return box.right - 4, r.uniform(box.top, box.bottom)

        p0 = edge_point()
        if big:
            p1 = (box.centerx + r.uniform(-30, 30), box.centery + r.uniform(-30, 30))
            n, jitter, life = 9, 14, 0.18
        else:
            ang = r.uniform(0, math.tau)
            p1 = (p0[0] + math.cos(ang) * 26, p0[1] + math.sin(ang) * 26)
            n, jitter, life = 4, 6, 0.12
        pts = [p0]
        for k in range(1, n):
            t = k / n
            pts.append((p0[0] + (p1[0] - p0[0]) * t + r.uniform(-jitter, jitter),
                        p0[1] + (p1[1] - p0[1]) * t + r.uniform(-jitter, jitter)))
        pts.append(p1)
        self._bolts.append([pts, color, 0.0, life])
        self._fx.burst(p1[0], p1[1], 5 if big else 2, palette=(_WHITE, color), speed=(40, 160),
                       life=(0.1, 0.25), size=(1, 2), style=SPARK, drag=5.0)

    def _drop_pos(self, t: float) -> tuple[float, float, float]:
        """Capsule centre and scale (0..1 from drop size to stage size) at ``t`` into the drop."""
        x0, y0 = self._chute_mouth()
        floor = _FLOOR_Y
        if t < FALL_T:
            # fall with two decaying bounces, rolling a little to the right
            x = x0 + 70 * ease_out_cubic(t / FALL_T)
            g = 2600.0
            t1 = math.sqrt(2 * (floor - y0) / g)             # first impact
            if t < t1:
                return x, y0 + 0.5 * g * t * t, 0.0
            v = g * t1 * 0.42
            tb = t - t1
            for _ in range(3):
                flight = 2 * v / g
                if tb < flight:
                    return x, floor - (v * tb - 0.5 * g * tb * tb), 0.0
                tb -= flight
                v *= 0.42
            return x, floor, 0.0
        u = _clamp01((t - FALL_T) / HOP_T)
        sx, sy = x0 + 70, floor
        ex, ey = _STAGE
        e = ease_out_cubic(u)
        x = sx + (ex - sx) * e
        y = sy + (ey - sy) * e - 150 * math.sin(math.pi * u)
        return x, y, e

    def _update_drop(self, dt: float) -> None:
        x0, y0 = self._chute_mouth()
        tier = self._tier_index()
        if self._once("out"):                              # POP out of the chute
            pal = tier_palette(self._tier())
            self._fx.burst(x0, y0, 16, palette=_DUST, speed=(30, 140), life=(0.3, 0.6), size=(2, 4),
                           drag=3.0, gravity=-40)
            self._fx.burst(x0, y0, 24 + 8 * tier, palette=pal, speed=(160, 420),
                           angle=(math.pi * 0.15, math.pi * 0.85), life=(0.2, 0.45), size=(1.5, 2.5),
                           style=SPARK, drag=3.0)
            self._rings.append([x0, y0, 0.0, 0.5, tier_color(self._tier()), 90])
            self._flash = max(self._flash, 0.15 + 0.05 * tier)
        g = 2600.0
        t1 = math.sqrt(2 * (_FLOOR_Y - y0) / g)
        v = g * t1 * 0.42
        hits = [t1, t1 + 2 * v / g, t1 + 2 * v / g + 2 * v * 0.42 / g]
        for k, at in enumerate(hits[:2]):
            if self._once(f"bounce{k}", at):
                x, _, _ = self._drop_pos(at)
                self._fx.burst(x, _FLOOR_Y + 10, 14 - 4 * k, palette=_DUST, speed=(40, 180),
                               angle=(math.pi, math.tau), life=(0.3, 0.6), size=(2, 4), drag=3.0, gravity=200)
                self._rings.append([x, _FLOOR_Y + 14, 0.0, 0.3, (200, 190, 180), 50 - 15 * k])
                self._sound.play_card()
        if self._t > FALL_T and tier >= 1:                  # sparkle trail on the hop
            x, y, _ = self._drop_pos(self._t)
            for _ in range(1 + tier):
                self._fx.emit(x + self._rng.uniform(-12, 12), y + self._rng.uniform(-12, 12),
                              self._rng.uniform(-30, 30), self._rng.uniform(-60, 0), life=0.5,
                              palette=tier_palette(self._tier()), size=2.5)
        if self._t >= DROP_T:
            self._set_phase("present")

    def _shakes(self) -> int:
        return self._tier_index() + 1

    def _update_present(self, dt: float) -> None:
        x, y = _STAGE
        for k in range(self._shakes()):
            at = 0.35 + k * (SHAKE_T + 0.12)
            if self._once(f"shake{k}", at):
                self._fx.implode(x, y, 14 + 6 * k, palette=tier_palette(self._tier()),
                                 radius=(70, 130), life=(0.28, 0.4))
                self._sound.play_nav()
        if self._t >= PRESENT_AUTO:
            self._open()

    def _open(self) -> None:
        self._set_phase("open")
        tier = self._tier_index()
        x, y = _STAGE
        pal = tier_palette(self._tier())
        self._flash = 0.75 + 0.08 * tier
        self._shake = (0, 0, 2, 7, 11)[tier]
        self._fx.burst(x, y, 30 + 22 * tier, palette=pal, speed=(140, 460 + 60 * tier), life=(0.4, 1.0),
                       size=(2, 4), drag=2.2, gravity=160)
        self._fx.burst(x, y, 16 + 8 * tier, palette=pal, speed=(200, 520), life=(0.2, 0.5),
                       size=(1.5, 2.5), style=SPARK, drag=3.5)
        self._fx.burst(x, y, 3, palette=pal, speed=(0, 20), life=(0.35, 0.6), size=(60, 90 + 15 * tier),
                       style=GLOW, drag=4.0)
        if self._tier() is Rarity.LEGENDARY:                  # gold confetti rain
            for _ in range(90):
                self._fx.emit(x + self._rng.uniform(-260, 260), y - self._rng.uniform(140, 300),
                              self._rng.uniform(-40, 40), self._rng.uniform(40, 160),
                              life=self._rng.uniform(1.2, 2.2), palette=_GOLD,
                              size=self._rng.uniform(2.5, 4.5), gravity=120, drag=0.6)
        self._sound.play_open_pack()
        if tier >= 3:
            self._sound.play_reward()

    def _update_open(self, dt: float) -> None:
        if self._t >= OPEN_T:
            self._set_phase("reveal")

    def _update_reveal(self, dt: float) -> None:
        pass

    def _update_collect(self, dt: float) -> None:
        if self._t >= COLLECT_T:
            x, y = _RELIC_COUNTER
            self._fx.burst(x, y, 16, palette=tier_palette(self._tier()), speed=(60, 200),
                           life=(0.3, 0.6), size=(1.5, 3), style=SPARK, drag=3.0)
            self._set_phase("idle")

    def _update_discard(self, dt: float) -> None:
        if self._t >= DISCARD_T:
            self._set_phase("idle")

    def _ambient(self, dt: float) -> None:
        """Glints on the glass in idle, rising motes around a presented / revealed prize."""
        self._sparkle_clock -= dt
        if self._sparkle_clock > 0:
            return
        self._sparkle_clock = self._rng.uniform(0.08, 0.2)
        r = self._rng
        if self._phase in ("idle", "coin", "crank"):
            box = self._box()
            self._fx.emit(r.uniform(box.left + 6, box.right - 6), r.uniform(box.top + 6, box.bottom - 6),
                          0, r.uniform(-12, -4), life=r.uniform(0.4, 0.8),
                          palette=((255, 255, 255), (220, 210, 255)), size=r.uniform(1.0, 2.0))
        elif self._phase in ("present", "reveal", "open") and self._tier_index() >= 1:
            x, y = _STAGE
            a = r.uniform(0, math.tau)
            d = r.uniform(50, 110)
            self._fx.emit(x + math.cos(a) * d, y + math.sin(a) * d * 0.6 + 30, r.uniform(-8, 8),
                          r.uniform(-60, -25), life=r.uniform(0.8, 1.4), palette=tier_palette(self._tier()),
                          size=r.uniform(1.5, 3.0), drag=0.4)

    # ------------------------------------------------------------------ drawing
    def draw(self, surface: pygame.Surface) -> None:
        self._backdrop.draw(surface)
        if self._shade is None or self._shade.get_size() != surface.get_size():
            self._build_overlays(surface.get_size())
        surface.blit(self._shade, (0, 0))
        if self._focus > 0.02:                              # spotlight on the machine and the stage
            self._vignette.set_alpha(int(235 * min(1.0, self._focus)))
            surface.blit(self._vignette, (0, 0))
        ox = oy = 0
        if self._shake > 0:
            ox = int(self._rng.uniform(-self._shake, self._shake))
            oy = int(self._rng.uniform(-self._shake, self._shake))
        self._draw_beams(surface, ox, oy)
        self._draw_machine(surface, ox, oy)
        self._draw_bolts(surface, ox, oy)
        self._draw_rings(surface, ox, oy)
        self._draw_prize(surface, ox, oy)
        self._fx.draw(surface)
        self._draw_panel(surface)
        self._draw_reveal_text(surface)
        if self._flash > 0:
            surface.fill(scaled((255, 255, 255), 0.8 * min(1.0, self._flash)),
                         special_flags=pygame.BLEND_RGB_ADD)

    def _build_overlays(self, size: tuple[int, int]) -> None:
        w, h = size
        self._shade = pygame.Surface(size, pygame.SRCALPHA)
        self._shade.fill((8, 4, 14, 120))
        self._band = pygame.Surface((w, 92), pygame.SRCALPHA)
        for y in range(92):
            pygame.draw.line(self._band, (6, 4, 12, int(210 * (1 - y / 92) ** 1.4)), (0, y), (w, y))
        # vignette: dark everywhere except an ellipse around the machine and the stage
        small = pygame.Surface((w // 8, h // 8), pygame.SRCALPHA)
        cx, cy = 560 / 8, 330 / 8
        for y in range(small.get_height()):
            for x in range(small.get_width()):
                d = math.hypot((x - cx) / (420 / 8), (y - cy) / (300 / 8))
                small.set_at((x, y), (4, 2, 8, int(255 * _clamp01((d - 0.55) / 0.7) ** 1.3)))
        self._vignette = pygame.transform.smoothscale(small, size)
        # a searchlight cone (additive), rotated at draw time
        L = 360
        cone = pygame.Surface((L * 2, L * 2))
        cone.fill((0, 0, 0))
        for i in range(24):
            k = i / 24
            spread = 0.26 * (1 - k * 0.4)
            col = scaled((150, 130, 95), (1 - k) ** 0.8)
            pygame.draw.polygon(cone, col, [(L, L), (L + math.cos(-spread) * L * (1 - k * 0.5),
                                                     L + math.sin(-spread) * L * (1 - k * 0.5)),
                                            (L + math.cos(spread) * L * (1 - k * 0.5),
                                             L + math.sin(spread) * L * (1 - k * 0.5))])
        self._beam = cone

    def _draw_beams(self, surface: pygame.Surface, ox: int, oy: int) -> None:
        """Two searchlights sweep from the crown while the machine works."""
        if self._phase not in ("crank", "drop") or self._beam is None:
            return
        k = _clamp01(self._t / 0.4) if self._phase == "crank" else max(0.0, 1 - self._t / 0.5)
        if k <= 0.02:
            return
        cx = _MACHINE_TOPLEFT[0] + 128 + ox
        cy = _MACHINE_TOPLEFT[1] + 8 + oy
        tint = tier_color(self._tier()) if self._tier_index() >= 3 and self._crank_u() > 0.5 else (255, 230, 170)
        for side in (-1, 1):
            ang = -90 + side * (35 + 28 * math.sin(self._time * 3.2 + side))
            beam = pygame.transform.rotate(self._beam, -ang)
            beam.fill(scaled(tint, 0.9 * k), special_flags=pygame.BLEND_RGB_MULT)
            surface.blit(beam, beam.get_rect(center=(cx, cy)), special_flags=pygame.BLEND_RGB_ADD)

    def _draw_bolts(self, surface: pygame.Surface, ox: int, oy: int) -> None:
        for pts, color, age, life in self._bolts:
            k = 1 - age / life
            shifted = [(x + ox, y + oy) for x, y in pts]
            pygame.draw.lines(surface, scaled(color, 0.55 * k + 0.2), False, shifted, 4)
            pygame.draw.lines(surface, scaled((255, 255, 255), 0.6 + 0.4 * k), False, shifted, 1)
            g = soft_glow(scaled(color, 0.5 * k), 20)
            surface.blit(g, g.get_rect(center=(int(shifted[-1][0]), int(shifted[-1][1]))),
                         special_flags=pygame.BLEND_RGB_ADD)

    def _draw_rings(self, surface: pygame.Surface, ox: int, oy: int) -> None:
        """Shockwave rings (coin in, thunk, pop out of the chute, bounces)."""
        for x, y, age, life, color, rmax in self._rings:
            u = age / life
            r = int(6 + (rmax - 6) * ease_out_cubic(u))
            w = max(1, int(5 * (1 - u)))
            pygame.draw.ellipse(surface, scaled(color, 1 - u * 0.7),
                                (int(x - r + ox), int(y - r * 0.45 + oy), 2 * r, int(r * 0.9)), w)

    def _machine_jitter(self) -> tuple[int, int]:
        if self._phase == "crank":
            u = self._crank_u()
            amp = 1.0 + 2.0 * u
            return (int(round(math.sin(self._t * (30 + 30 * u)) * amp)),
                    int(round(-abs(math.sin(self._t * (15 + 15 * u))) * amp)))
        if self._phase == "coin" and COIN_T * 0.72 < self._t < COIN_T * 0.9:
            return 0, 1
        return 0, 0

    def _swirl(self) -> float:
        """0 resting .. 1 capsules whirling in a vortex (crank only)."""
        if self._phase != "crank":
            return 0.0
        u = self._crank_u()
        if u < 0.18:
            return smoothstep(u / 0.18)
        if u < THUNK_AT - 0.1:
            return 1.0
        return 1.0 - smoothstep((u - (THUNK_AT - 0.1)) / (1.0 - THUNK_AT + 0.1))

    def _draw_machine(self, surface: pygame.Surface, ox: int, oy: int) -> None:
        jx, jy = self._machine_jitter()
        a = self._assets
        bx, by = _MACHINE_TOPLEFT[0] + ox + jx, _MACHINE_TOPLEFT[1] + oy + jy
        # warm glow behind the machine, stronger while it works
        power = 0.35 + 0.65 * self._focus
        glow = soft_glow(scaled((90, 26, 64), power), 240)
        surface.blit(glow, glow.get_rect(center=(bx + 128, by + 200)), special_flags=pygame.BLEND_RGB_ADD)
        if a is None:
            pygame.draw.rect(surface, (120, 30, 50), (bx + 20, by, 216, 360), border_radius=10)
            return
        pad = 24
        mw, mh = a.machine.get_size()
        if self._layer is None:
            self._layer = pygame.Surface((mw + 2 * pad, mh + 2 * pad), pygame.SRCALPHA)
        layer = self._layer
        layer.fill((0, 0, 0, 0))
        mx, my = pad, pad
        layer.blit(a.machine, (mx, my))
        # capsules in the box: resting pile, jostle, or a whirling vortex while the crank turns
        box = a.rect("box").move(mx, my)
        layer.set_clip(box)
        swirl = self._swirl()
        spin = self._time * (2.0 + 9.0 * swirl)
        cxv, cyv = box.centerx, box.centery + 6
        n = len(self._pile)
        base = self._box()
        order = []
        for i, (x, y, ci, ph) in enumerate(self._pile):
            rx_ = x - base.x + box.x
            ry_ = y - base.y + box.y
            bob = math.sin(self._time * 1.6 + ph) * 0.8
            if swirl > 0:
                ang = spin * (1.0 + 0.25 * (i % 3)) + ph * 2 + i * 0.7
                rad = 26 + (i * 37 % 64)
                h = -46 + (i / max(1, n - 1)) * 88
                tx = cxv + math.cos(ang) * rad
                ty = cyv + h + math.sin(ang) * rad * 0.28
                depth = math.sin(ang)
                px = rx_ + (tx - rx_) * swirl
                py = ry_ + (ty - ry_) * swirl
            else:
                depth = 0.0
                px, py = rx_, ry_ - bob
            order.append((depth, px, py, int(ci)))
        order.sort(key=lambda o: o[0])
        for depth, px, py, ci in order:
            img = a.small[ci % len(a.small)]
            layer.blit(img, img.get_rect(center=(int(px), int(py))))
        # the prize capsule, glowing in the middle of the vortex, sinks into the funnel
        u = self._crank_u() if self._phase == "crank" else 0.0
        if self._phase == "crank" and u > 0.5:
            k = _clamp01((u - 0.5) / (THUNK_AT - 0.5))
            px = cxv
            py = box.top + 30 + (box.height - 20) * smoothstep(k)
            halo = soft_glow(scaled(tier_color(self._tier()), 0.5 + 0.3 * math.sin(self._time * 20)), 40)
            layer.blit(halo, halo.get_rect(center=(int(px), int(py))), special_flags=pygame.BLEND_RGB_ADD)
            if k < 1.0:
                img = a.drop[self._tier_index()]
                layer.blit(img, img.get_rect(center=(int(px), int(py))))
        layer.set_clip(None)
        layer.blit(a.glass, (mx, my))
        self._draw_bulbs(layer, mx, my)
        frames = a.crank
        k = 0
        if self._phase == "crank":
            turns = 3.0 * smoothstep(min(1.0, u / THUNK_AT))         # three turns, easing in and out
            k = int(turns * len(frames)) % len(frames)
        cx, cy = a.point("crank")
        img = frames[k]
        layer.blit(img, img.get_rect(center=(mx + cx, my + cy)))
        if (self._phase == "coin" and self._t > COIN_T * 0.65) or self._bulb_flash > 0.3:
            sx, sy = a.point("slot")
            g = soft_glow((255, 200, 80), 26)
            layer.blit(g, g.get_rect(center=(mx + sx, my + sy)), special_flags=pygame.BLEND_RGB_ADD)
        flap = 0
        if self._phase == "drop" and self._t < 0.35:
            flap = 2 if self._t < 0.2 else 1
        ch = a.rect("chute")
        layer.blit(a.flap[flap], (mx + ch.x, my + ch.y))
        # squash on each quarter turn, a hop at the thunk
        zoom = 1.0 + 0.06 * swirl                                 # leans in while it whirls
        sx_ = zoom + 0.035 * self._pulse - 0.04 * self._jump
        sy_ = zoom - 0.03 * self._pulse + 0.06 * self._jump
        hop = int(-18 * math.sin(math.pi * min(1.0, self._jump)) * (1 if self._jump > 0.5 else 0.3))
        lw, lh = layer.get_size()
        if abs(sx_ - 1) > 0.002 or abs(sy_ - 1) > 0.002:
            img = pygame.transform.scale(layer, (int(lw * sx_), int(lh * sy_)))
        else:
            img = layer
        rect = img.get_rect(midbottom=(bx + mw // 2, by + mh + pad + hop))
        surface.blit(img, rect)
        if self._phase == "coin":
            sxp, syp = a.point("slot")
            self._draw_coin(surface, bx + sxp, by + syp)

    def _draw_bulbs(self, surface: pygame.Surface, mx: int, my: int) -> None:
        a = self._assets
        bulbs = a.meta.get("bulbs", [])
        n = len(bulbs)
        t = self._time
        speed = 4.0
        color: Color = (255, 214, 120)
        if self._phase == "crank":
            speed = 16.0
            if self._tier_index() >= 3 and self._t > CRANK_T * 0.45:
                color = tier_color(self._tier())
        elif self._phase in ("present", "open", "reveal") and self._result is not None:
            color = tier_color(self._tier())
            speed = 9.0
        if self._phase == "crank":
            speed = 10.0 + 30.0 * self._crank_u()
        lit = int(t * speed)
        for i, (bx, by) in enumerate(bulbs):
            on = (i + lit) % 3 == 0 or self._phase in ("open",) or self._bulb_flash > 0.35
            x, y = mx + bx * a.scale, my + by * a.scale
            if on:
                pygame.draw.rect(surface, color, (x - 3, y - 3, 6, 6))
                pygame.draw.rect(surface, scaled(color, 1.3), (x - 3, y - 3, 2, 2))
                g = soft_glow(scaled(color, 0.6), 14)
                surface.blit(g, g.get_rect(center=(x, y)), special_flags=pygame.BLEND_RGB_ADD)
            else:
                pygame.draw.rect(surface, (64, 30, 26), (x - 3, y - 3, 6, 6))
                pygame.draw.rect(surface, (110, 70, 50), (x - 3, y - 3, 2, 2))

    def _draw_coin(self, surface: pygame.Surface, sx: float, sy: float) -> None:
        a = self._assets
        u = _clamp01(self._t / (COIN_T * 0.78))
        if u >= 1:
            return
        x0, y0 = _PURSE
        x = x0 + (sx - x0) * u
        y = y0 + (sy - y0) * u - 160 * math.sin(math.pi * u)
        img = a.coin[int(self._t * 30) % len(a.coin)]
        img = pygame.transform.scale(img, (img.get_width() * 2, img.get_height() * 2))
        g = soft_glow((120, 90, 20), 30)
        surface.blit(g, g.get_rect(center=(int(x), int(y))), special_flags=pygame.BLEND_RGB_ADD)
        surface.blit(img, img.get_rect(center=(int(x), int(y))))
        for _ in range(2):
            self._fx.emit(x, y, self._rng.uniform(-30, 30), self._rng.uniform(-30, 30), life=0.4,
                          palette=_GOLD, size=self._rng.uniform(1.5, 3))

    # prize -------------------------------------------------------------
    def _rays_for(self, rarity: Rarity) -> list[pygame.Surface]:
        if rarity not in self._rays:
            self._rays[rarity] = _make_rays(tier_color(rarity))
        return self._rays[rarity]

    def _relic_icon(self) -> pygame.Surface | None:
        relic = self._result.relic if self._result else None
        if relic is None:
            return None
        if relic.name not in self._icon_cache:
            self._icon_cache[relic.name] = self._sprites.get_relic_sprite(relic.name, 96)
        return self._icon_cache[relic.name]

    def _draw_prize(self, surface: pygame.Surface, ox: int, oy: int) -> None:
        if self._result is None or self._phase in ("idle", "coin", "crank"):
            return
        a = self._assets
        tier = self._tier_index()
        rarity = self._tier()
        if self._phase == "drop":
            x, y, grow = self._drop_pos(self._t)
            if a is not None:
                img = a.drop[tier] if grow < 0.5 else a.big[tier]["closed"]
                if grow >= 0.5:
                    k = 0.55 + 0.45 * (grow - 0.5) / 0.5
                    img = pygame.transform.scale(img, (int(img.get_width() * k), int(img.get_height() * k)))
                spin = 0 if self._t < FALL_T else int(-360 * ease_out_cubic((self._t - FALL_T) / HOP_T))
                if spin:
                    img = pygame.transform.rotate(img, spin)
                surface.blit(img, img.get_rect(center=(int(x + ox), int(y + oy))))
            return
        x, y = _STAGE
        x += ox
        y += oy
        if self._phase == "present":
            float_y = math.sin(self._t * 2.6) * 6
            pulse = 0.5 + 0.5 * math.sin(self._t * 5)
            halo = soft_glow(scaled(tier_color(rarity), 0.35 + 0.25 * pulse + 0.08 * tier), 90 + 12 * tier)
            surface.blit(halo, halo.get_rect(center=(int(x), int(y))), special_flags=pygame.BLEND_RGB_ADD)
            angle = 0.0
            for k in range(self._shakes()):
                at = 0.35 + k * (SHAKE_T + 0.12)
                if at <= self._t < at + SHAKE_T:
                    u = (self._t - at) / SHAKE_T
                    angle = math.sin(u * math.tau * 2) * (10 + 4 * k) * (1 - u)
            if a is not None:
                img = a.big[tier]["closed"]
                if angle:
                    img = pygame.transform.rotate(img, angle)
                surface.blit(img, img.get_rect(center=(int(x), int(y + float_y))))
            if self._t > 0.6:
                hint = self._fonts.get(16).render("Haz clic para abrir", True, (235, 225, 200))
                hint.set_alpha(int(175 + 80 * math.sin(self._time * 4)))
                surface.blit(hint, hint.get_rect(center=(int(x), int(y) + 92)))
            return
        # open / reveal / collect
        t_open = self._t if self._phase == "open" else OPEN_T + 1
        if self._phase in ("open", "reveal") and tier >= 2:
            k = min(1.0, t_open / 0.25) * (1.0 if self._phase == "reveal" else 1.0)
            level = min(3, int(k * (2 + tier * 0.5)))
            rays = pygame.transform.rotate(self._rays_for(rarity)[level], (self._time * 20) % 360)
            surface.blit(rays, rays.get_rect(center=(int(x), int(y))), special_flags=pygame.BLEND_RGB_ADD)
        if self._phase == "open" and a is not None:                  # the halves fly apart
            u = _clamp01(t_open / 0.6)
            top = a.big[tier]["top"]
            bot = a.big[tier]["bottom"]
            alpha = int(255 * (1 - u))
            tt = pygame.transform.rotate(top, -40 * u)
            tt.set_alpha(alpha)
            surface.blit(tt, tt.get_rect(center=(int(x - 60 * u), int(y - 20 - 140 * u + 120 * u * u))))
            bb = pygame.transform.rotate(bot, 30 * u)
            bb.set_alpha(alpha)
            surface.blit(bb, bb.get_rect(center=(int(x + 50 * u), int(y + 20 + 60 * u + 200 * u * u))))
        # the relic
        pop = ease_out_back((t_open - 0.1) / 0.5)
        if self._phase == "discard":
            u = _clamp01(self._t / DISCARD_T)
            pop = 1.0 - smoothstep(u)
            y += 40 * u * u
            icon = self._relic_icon()
            if icon is not None and pop > 0.02:
                size = max(4, int(96 * pop))
                img = pygame.transform.scale(icon, (size, size))
                img.fill((90, 90, 90), special_flags=pygame.BLEND_RGB_MULT)
                img.set_alpha(int(255 * (1 - u)))
                surface.blit(img, img.get_rect(center=(int(x), int(y))))
            return
        if self._phase == "collect":
            u = ease_out_cubic(self._t / COLLECT_T)
            tx, ty = _RELIC_COUNTER
            x, y = x + (tx - x) * u, y + (ty - y) * u - 80 * math.sin(math.pi * u)
            pop = 1.0 - 0.75 * u
        if pop <= 0.02:
            return
        halo = soft_glow(scaled(tier_color(rarity), 0.55), 70 + 10 * tier)
        surface.blit(halo, halo.get_rect(center=(int(x), int(y))), special_flags=pygame.BLEND_RGB_ADD)
        icon = self._relic_icon()
        bob = math.sin(self._time * 2.2) * 4 if self._phase == "reveal" else 0
        size = int(96 * pop)
        if size < 4:
            return
        if icon is None:
            pygame.draw.circle(surface, tier_color(rarity), (int(x), int(y + bob)), size // 3)
            pygame.draw.circle(surface, _WHITE, (int(x - size // 9), int(y + bob - size // 9)), max(1, size // 12))
            return
        img = pygame.transform.scale(icon, (size, size))
        surface.blit(img, img.get_rect(center=(int(x), int(y + bob))))

    # text --------------------------------------------------------------
    def _label(self, surface, text, center, size, color, alpha: int = 255):
        img = self._fonts.get(size).render(text, True, color)
        if alpha < 255:
            img.set_alpha(alpha)
        surface.blit(img, img.get_rect(center=center))

    def _draw_reveal_text(self, surface: pygame.Surface) -> None:
        if self._phase not in ("open", "reveal") or self._result is None or self._result.relic is None:
            return
        relic = self._result.relic
        k = 1.0 if self._phase == "reveal" else _clamp01((self._t - 0.45) / 0.4)
        if k <= 0:
            return
        a = int(255 * k)
        x, y = int(_STAGE[0]), int(_STAGE[1]) + 92
        lines = _wrap(desc_text(relic), self._fonts.get(13), 300)[:4]
        panel = pygame.Rect(0, 0, 330, 72 + 18 * len(lines))
        panel.midtop = (x, y - 10)
        bg = pygame.Surface(panel.size, pygame.SRCALPHA)
        bg.fill((14, 10, 22, int(215 * k)))
        surface.blit(bg, panel.topleft)
        col = tier_color(relic.rarity)
        pygame.draw.rect(surface, col, panel, 2, border_radius=8)
        if relic.chroma is not None:
            chroma_fx.draw_chroma_box(surface, panel, relic.chroma, chroma_fx.now(), radius=8)
        self._label(surface, chroma_title(relic.name, relic.chroma), (x, y + 10), 20, colors.TEXT_ACCENT, a)
        tag = rarity_label(relic.rarity) + ("  ·  ¡Repetida!" if self._result.duplicate else "")
        self._label(surface, tag, (x, y + 34), 14, col, a)
        for i, line in enumerate(lines):
            self._label(surface, line, (x, y + 58 + i * 18), 13, colors.TEXT_PRIMARY, a)
        _BTN_KEEP.midtop = (x - 88, panel.bottom + 12)
        _BTN_DECLINE.midtop = (x + 88, panel.bottom + 12)
        if self._phase == "reveal":
            for rect, label, key, edge, fill in (
                    (_BTN_KEEP, "Quedármela", "keep", col, (26, 40, 26)),
                    (_BTN_DECLINE, "Rechazar", "decline", (150, 90, 90), (40, 20, 22))):
                hov = self._hovered == key
                pygame.draw.rect(surface, scaled(fill, 1.6) if hov else fill, rect, border_radius=8)
                pygame.draw.rect(surface, scaled(edge, 1.25) if hov else edge, rect, 2, border_radius=8)
                self._label(surface, label, (rect.centerx, rect.centery - 6), 16,
                            (240, 240, 230) if key == "keep" else (235, 200, 200))
                hint = "Enter" if key == "keep" else "R  ·  no se devuelve el oro"
                self._label(surface, hint, (rect.centerx, rect.centery + 12), 10, colors.TEXT_SECONDARY)

    def _draw_panel(self, surface: pygame.Surface) -> None:
        if self._band is not None:
            surface.blit(self._band, (0, 0))
        self._label(surface, "Gachapón", (640, 40), 30, (255, 190, 225))
        self._label(surface, "Cada tirada sube el precio de las siguientes", (640, 72), 13,
                    colors.TEXT_SECONDARY)
        self._label(surface, f"Reliquias: {len(self._run.relics)}", (_RELIC_COUNTER[0], _RELIC_COUNTER[1]),
                    15, colors.TEXT_ACCENT)
        busy = self._phase != "idle"
        for kind, rect, key in ((PullKind.NORMAL, _BTN_NORMAL, "normal"), (PullKind.STELLAR, _BTN_STELLAR, "stellar")):
            self._draw_button(surface, kind, rect, hovered=self._hovered == key and not busy, busy=busy)
        self._draw_odds(surface)
        self._label(surface, f"Tiradas hechas: {self._run.gacha_pulls}  ·  precio ×{PRICE_GROWTH:g} por tirada",
                    (_PANEL_X + _BTN_W // 2, 628), 12, colors.TEXT_SECONDARY)
        hov = self._hovered == "exit" and not busy
        pygame.draw.rect(surface, colors.BG_PANEL, _EXIT, border_radius=6)
        pygame.draw.rect(surface, colors.TEXT_ACCENT if hov else colors.PANEL_BORDER, _EXIT, 2, border_radius=6)
        self._label(surface, "Salir", _EXIT.center, 16, colors.TEXT_PRIMARY if not busy else colors.TEXT_SECONDARY)
        if self._feedback_t > 0:
            self._label(surface, self._feedback, (640, 690), 16, (245, 140, 120))

    def _draw_button(self, surface, kind: PullKind, rect: pygame.Rect, *, hovered: bool, busy: bool) -> None:
        d = PULLS[kind]
        price = gacha_price(self._run, kind)
        ok = can_pull(self._run, kind) and not busy
        stellar = kind is PullKind.STELLAR
        base = (46, 20, 54) if stellar else (24, 26, 40)
        if hovered and ok:
            base = scaled(base, 1.5)
        pygame.draw.rect(surface, base, rect, border_radius=10)
        edge = (255, 205, 90) if stellar else (170, 180, 210)
        if not ok:
            edge = (80, 76, 90)
        pygame.draw.rect(surface, edge, rect, 2, border_radius=10)
        if stellar and ok:                                         # sweeping sparkle on the border
            t = (self._time * 0.6) % 1.0
            per = 2 * (rect.width + rect.height)
            pos = t * per
            if pos < rect.width:
                px, py = rect.x + pos, rect.y
            elif pos < rect.width + rect.height:
                px, py = rect.right, rect.y + pos - rect.width
            elif pos < 2 * rect.width + rect.height:
                px, py = rect.right - (pos - rect.width - rect.height), rect.bottom
            else:
                px, py = rect.x, rect.bottom - (pos - 2 * rect.width - rect.height)
            g = soft_glow((255, 200, 90), 16)
            surface.blit(g, g.get_rect(center=(int(px), int(py))), special_flags=pygame.BLEND_RGB_ADD)
        title_col = (255, 220, 140) if stellar else colors.TEXT_PRIMARY
        if not ok:
            title_col = colors.TEXT_SECONDARY
        key = "2" if stellar else "1"
        self._label(surface, f"{d.name}  [{key}]", (rect.centerx, rect.y + 22), 17, title_col)
        price_col = colors.TEXT_ACCENT if self._run.gold >= price else (220, 100, 90)
        self._label(surface, f"{price} oro", (rect.centerx, rect.y + 50), 20, price_col)
        self._label(surface, d.note, (rect.centerx, rect.y + 75), 12, colors.TEXT_SECONDARY)

    def _draw_odds(self, surface: pygame.Surface) -> None:
        top = 372
        x0 = _PANEL_X
        box = pygame.Rect(x0, top, _BTN_W, 236)
        bg = pygame.Surface(box.size, pygame.SRCALPHA)
        bg.fill((12, 10, 20, 200))
        surface.blit(bg, box.topleft)
        pygame.draw.rect(surface, colors.PANEL_BORDER, box, 1, border_radius=8)
        self._label(surface, "Probabilidades", (box.centerx, top + 16), 15, colors.TEXT_ACCENT)
        self._label(surface, "Normal", (x0 + 178, top + 40), 12, colors.TEXT_SECONDARY)
        self._label(surface, "Estelar", (x0 + 246, top + 40), 12, (255, 220, 140))
        normal = gacha_odds(self._run, PullKind.NORMAL)
        stellar = gacha_odds(self._run, PullKind.STELLAR)
        for i, rarity in enumerate(_TIERS):
            y = top + 66 + i * 32
            col = tier_color(rarity)
            pygame.draw.rect(surface, col, (x0 + 14, y - 6, 12, 12), border_radius=3)
            self._label_left(surface, rarity_label(rarity), (x0 + 34, y), 14, col)
            for cx, odds in ((x0 + 178, normal), (x0 + 246, stellar)):
                p = odds[rarity]
                bar = int(52 * p)
                pygame.draw.rect(surface, scaled(col, 0.35), (cx - 26, y + 8, 52, 3))
                if bar:
                    pygame.draw.rect(surface, col, (cx - 26, y + 8, bar, 3))
                self._label(surface, f"{p * 100:.1f}%" if p < 0.1 else f"{p * 100:.0f}%", (cx, y - 2), 13,
                            colors.TEXT_PRIMARY if p > 0 else colors.TEXT_SECONDARY)

    def _label_left(self, surface, text, midleft, size, color):
        img = self._fonts.get(size).render(text, True, color)
        surface.blit(img, img.get_rect(midleft=midleft))
