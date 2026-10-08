"""Pack opening scene — animated booster opening, then pick 1 of 5 cards.

Sequence (all time-based; any click or Space/Enter skips the animation):

  intro   the closed pack drops in and settles (ease-out-back);
  idle    it floats with a pulsing theme-coloured glow — click it to open;
  charge  it shakes harder and harder, energy sparks rush into it, it whitens;
  burst   flash + screen shake: the top strip tears off along a jagged line and
          spins away, the body falls and fades, a particle explosion and
          rotating light rays in the pack's colours;
  deal    five face-down cards fly out of the pack to their slots;
  reveal  cards flip one by one; rare and better get an anticipation glow first,
          and every flip bursts in its rarity colour (legendary: gold confetti
          and a shake);
  pick    the classic pick-1 screen; rare+ cards keep a halo and sparkles;
  outro   the chosen card rises to the centre in a burst, the others fall away.

Art comes from existing assets only (pack paintings in ``assets/cards-v2/packs``
and the crystal card back); everything else is code-drawn light and particles
(:mod:`src.presentation.fx.bursts`, :mod:`src.presentation.fx.particles`).

A pack with a chroma multiplies how many cards you keep (golden: pick 2);
the pack art is gilded and sparkles.

Public flag consumed by SceneManager:
  cleared:      bool        — True when player picks (after the outro) or skips.
  chosen_cards: list[Card]  — every card kept (1, or more for chroma packs).
  chosen_card:  Card | None — the first chosen card (compatibility).
"""
from __future__ import annotations

import math
import random

import pygame

from src.application.card_preview import NO_BONUS, CardBonus
from src.application.luck import LuckReport
from src.presentation.ui.luck_badge import draw_luck_badge
from src.domain.card import Card, CardRarity
from src.domain.chroma import Chroma, effect_multiplier
from src.infrastructure import colors
from src.infrastructure.audio import SoundPlayer
from src.infrastructure.card_assets import card_back, pack_art
from src.infrastructure.fonts import FontRegistry
from src.presentation.fx.bursts import GLOW, SPARK, SQUARE, BurstParticles, scaled, soft_glow
from src.presentation.fx import card_fx, chroma_fx
from src.presentation.fx.particles import EmitterConfig, ParticleSystem
from src.presentation.ui.card_widget import CARD_H, CARD_W, draw_card, render_card_surface
from src.presentation.ui.tooltip import card_tooltip, draw_tooltip

Color = tuple[int, int, int]

_BG = pygame.Color(8, 12, 20)
_GAP = 20
_CARD_Y = 120
_SCREEN_W, _SCREEN_H = 1280, 720
_PACK_H = 380
_PACK_CENTER = (640, 360)

# Timings (seconds)
INTRO_T = 0.55
CHARGE_T = 0.8
BURST_T = 0.35          # from the tear until the first card leaves the pack
DEAL_EACH = 0.45
DEAL_STAGGER = 0.09
FLIP_T = 0.32
FLIP_STAGGER = 0.28
ANTICIPATION_T = 0.3    # extra wait (with a growing glow) before flipping rare+
OUTRO_T = 0.55
TEAR_FRACTION = 0.13    # where the top strip tears off, as a fraction of pack height

# Theme colours: (glow, burst palette bright -> dark, accent palette)
_SILVER: tuple[Color, ...] = ((255, 255, 255), (220, 225, 235), (150, 155, 170))
_GOLD: tuple[Color, ...] = ((255, 245, 190), (255, 210, 80), (215, 140, 25), (140, 70, 10))
THEMES: dict[str, tuple[Color, tuple[Color, ...], tuple[Color, ...]]] = {
    "acero":  ((200, 50, 40), ((255, 245, 230), (255, 130, 95), (205, 45, 40), (95, 20, 20)), _SILVER),
    "escudo": ((40, 170, 85), ((240, 255, 240), (125, 240, 155), (40, 165, 80), (15, 65, 30)), _SILVER),
    "magia":  ((50, 120, 240), ((235, 250, 255), (125, 205, 255), (50, 115, 235), (20, 40, 115)), _SILVER),
    "epico":  ((155, 60, 225), ((255, 245, 255), (220, 150, 255), (150, 60, 220), (60, 20, 100)), _GOLD),
}
_DEFAULT_THEME = "acero"

RARITY_PALETTE: dict[CardRarity, tuple[Color, ...]] = {
    CardRarity.COMMON:    ((255, 255, 255), (205, 195, 180), (120, 110, 100)),
    CardRarity.UNCOMMON:  ((230, 255, 235), (110, 220, 130), (40, 120, 60)),
    CardRarity.RARE:      ((230, 245, 255), (110, 170, 255), (40, 80, 180)),
    CardRarity.EPIC:      ((250, 235, 255), (200, 120, 255), (110, 40, 170)),
    CardRarity.LEGENDARY: ((255, 255, 230), (255, 215, 90), (240, 150, 30), (150, 70, 10)),
}
_SPARKLE_RATE = {CardRarity.RARE: 3.0, CardRarity.EPIC: 6.0, CardRarity.LEGENDARY: 11.0}


# ---------------------------------------------------------------------------
# Easing
# ---------------------------------------------------------------------------

def _clamp01(t: float) -> float:
    return 0.0 if t < 0.0 else 1.0 if t > 1.0 else t


def ease_out_cubic(t: float) -> float:
    t = _clamp01(t)
    return 1.0 - (1.0 - t) ** 3


def ease_out_back(t: float, s: float = 1.7) -> float:
    t = _clamp01(t) - 1.0
    return t * t * ((s + 1.0) * t + s) + 1.0


def _rarity(card: Card) -> CardRarity:
    return card.rarity or CardRarity.COMMON


def _is_special(card: Card) -> bool:
    """Rare or better, or any chroma (golden…): gets anticipation and a halo."""
    return _rarity(card).value >= CardRarity.RARE.value or card.chroma is not None or card.lucky_drop


def _reveal_palette(card: Card) -> tuple[Color, ...]:
    if card.chroma is not None:
        st = chroma_fx.style(card.chroma)
        return (st.bright, st.main, st.glow, st.dark)
    return RARITY_PALETTE[_rarity(card)]


class PackOpeningScene:
    """Animated pack opening; player then selects one of the cards to keep."""

    def __init__(
        self,
        cards: list[Card],
        pack_name: str,
        fonts: FontRegistry,
        *,
        sound: SoundPlayer | None = None,
        theme: str | None = None,
        seed: int = 0,
        chroma: Chroma | None = None,
        bonus: CardBonus = NO_BONUS,
        luck: LuckReport | None = None,
    ) -> None:
        self._sound = sound if sound is not None else SoundPlayer()
        self._bonus = bonus          # the hero's stats, so numbers match the hand
        self._luck = luck            # shown bottom-left: what luck did to this pack's odds
        self._cards      = cards
        self._pack_name  = pack_name
        self._fonts      = fonts
        self._card_rects: list[pygame.Rect] = []
        self._hovered:    int | None = None
        self._skip_rect:  pygame.Rect | None = None
        self._mouse:      tuple[int, int] = (0, 0)
        self._rng = random.Random(seed)

        self.cleared:     bool = False
        self.chosen_card: Card | None = None
        self.chosen_cards: list[Card] = []
        self._pack_chroma = chroma
        self._picks = max(1, min(effect_multiplier(chroma), len(cards))) if cards else 1
        self._chosen: list[int] = []

        # --- theme and art -------------------------------------------------
        self._theme = theme if theme in THEMES else _DEFAULT_THEME
        self._glow_color, self._palette, self._accent = THEMES[self._theme]
        self._pack = self._load_pack()
        if chroma is not None:
            self._pack = chroma_fx.gild_frame(self._pack, chroma)
        self._pack_white = self._pack.copy()
        self._pack_white.fill((255, 255, 255, 0), special_flags=pygame.BLEND_RGBA_MAX)
        self._strip, self._body, self._tear_y = self._split_pack(self._pack)
        self._back = card_back(CARD_W, CARD_H) or self._fallback_back()
        self._rays = self._make_rays(self._glow_color)

        # --- effects ------------------------------------------------------
        self._fx = BurstParticles(900, seed=seed)
        dark = scaled(self._glow_color, 0.35)
        self._motes = ParticleSystem(EmitterConfig(
            rate=14, lifetime=(3.0, 6.0), area=(0, 330, 640, 30), vy=(-18.0, -8.0), wobble=6.0,
            colors=(dark, scaled(self._glow_color, 0.8), self._palette[1], dark), size=1, capacity=90,
        ), scale=2, seed=seed)
        self._motes.prewarm(4.0)
        self._shake = 0.0
        self._shake_off = (0, 0)
        self._flash = 0.0            # white overlay alpha 0..1
        self._veil: pygame.Surface | None = None
        self._time = 0.0

        # --- timeline -----------------------------------------------------
        self._phase = "intro"
        self._t = 0.0                # time in the current pre-open phase
        self._t_open = 0.0           # time since the tear (burst/deal/reveal/pick)
        self._t_out = 0.0
        self._pack_hover = False
        self._landed = [False] * len(cards)
        self._flipped = [False] * len(cards)
        self._deal_angle = [self._rng.uniform(-22.0, 22.0) for _ in cards]
        self._flip_start = self._schedule_flips()
        self._pick_at = (self._flip_start[-1] + FLIP_T + 0.15) if cards else BURST_T
        self._strip_state = [0.0, 0.0, 0.0, 0.0, 0.0]   # dx, dy, vx, vy, angle
        self._body_state = [0.0, 0.0]                   # dy, vy
        self._sparkle_acc = [0.0] * len(cards)

    # ------------------------------------------------------------------
    # Setup helpers
    # ------------------------------------------------------------------

    def _load_pack(self) -> pygame.Surface:
        art = pack_art(self._theme, _PACK_H)
        if art is not None:
            return art.copy()
        # Missing asset: a plain themed booster so the animation still works.
        w = int(_PACK_H * 0.68)
        surf = pygame.Surface((w, _PACK_H), pygame.SRCALPHA)
        surf.fill((*scaled(self._glow_color, 0.45), 255))
        pygame.draw.rect(surf, self._accent[1], surf.get_rect(), 6, border_radius=10)
        pygame.draw.rect(surf, self._accent[2], (0, 0, w, int(_PACK_H * 0.08)))
        pygame.draw.rect(surf, self._accent[2], (0, int(_PACK_H * 0.92), w, int(_PACK_H * 0.08)))
        return surf

    def _fallback_back(self) -> pygame.Surface:
        surf = pygame.Surface((CARD_W, CARD_H), pygame.SRCALPHA)
        pygame.draw.rect(surf, (24, 36, 58), surf.get_rect(), border_radius=10)
        pygame.draw.rect(surf, (170, 180, 200), surf.get_rect(), 3, border_radius=10)
        pygame.draw.polygon(surf, (90, 180, 255), [(CARD_W // 2, 70), (CARD_W // 2 + 20, 97),
                                                    (CARD_W // 2, 124), (CARD_W // 2 - 20, 97)])
        return surf

    @staticmethod
    def _tear_edge(w: int, tear_y: int, seed: int = 7) -> list[int]:
        """Jagged tear line: y for every column (zig-zag with random teeth)."""
        rng = random.Random(seed)
        pts: list[tuple[int, int]] = []
        x = 0
        up = True
        while x < w + 14:
            pts.append((x, tear_y + (-5 if up else 5) + rng.randint(-2, 2)))
            x += rng.randint(8, 14)
            up = not up
        ys = []
        j = 0
        for cx in range(w):
            while j + 1 < len(pts) - 1 and pts[j + 1][0] <= cx:
                j += 1
            (x0, y0), (x1, y1) = pts[j], pts[j + 1]
            u = (cx - x0) / (x1 - x0) if x1 != x0 else 0.0
            ys.append(int(y0 + (y1 - y0) * u))
        return ys

    def _split_pack(self, pack: pygame.Surface) -> tuple[pygame.Surface, pygame.Surface, int]:
        """Cut the pack into a top strip and the body along a jagged line."""
        w, h = pack.get_size()
        tear_y = max(10, int(h * TEAR_FRACTION))
        edge = self._tear_edge(w, tear_y)
        margin = 10
        strip = pygame.Surface((w, tear_y + margin), pygame.SRCALPHA)
        strip.blit(pack, (0, 0))
        top = tear_y - margin
        body = pygame.Surface((w, h - top), pygame.SRCALPHA)
        body.blit(pack, (0, -top))
        clear = (0, 0, 0, 0)
        for x, y in enumerate(edge):
            strip.fill(clear, (x, y, 1, strip.get_height() - y))
            body.fill(clear, (x, 0, 1, y - top))
            # a thin light seam on both torn edges
            if 0 <= y - 1 < strip.get_height():
                strip.fill((*self._palette[0], 255), (x, y - 1, 1, 1))
            if 0 <= y - top < body.get_height():
                body.fill((*self._palette[0], 255), (x, y - top, 1, 1))
        return strip, body, tear_y

    @staticmethod
    def _make_rays(color: Color) -> list[pygame.Surface]:
        """Light-ray fan (additive) at 4 brightness levels; rotated at draw time."""
        size = 760
        r = size // 2
        base = pygame.Surface((size, size))
        base.fill((0, 0, 0))
        n = 14
        for i in range(n):
            a0 = i * math.tau / n
            a1 = a0 + math.tau / n * 0.42
            pygame.draw.polygon(base, scaled(color, 0.9), [
                (r, r), (r + math.cos(a0) * r, r + math.sin(a0) * r),
                (r + math.cos(a1) * r, r + math.sin(a1) * r)])
        base.blit(soft_glow((255, 255, 255), r), (0, 0), special_flags=pygame.BLEND_RGB_MULT)
        levels = []
        for k in (0.25, 0.5, 0.75, 1.0):
            s = base.copy()
            s.fill(scaled((255, 255, 255), k), special_flags=pygame.BLEND_RGB_MULT)
            levels.append(s)
        return levels

    def _schedule_flips(self) -> list[float]:
        deal_end = BURST_T + max(0, len(self._cards) - 1) * DEAL_STAGGER + DEAL_EACH
        t = deal_end + 0.15
        starts = []
        for card in self._cards:
            if _is_special(card):
                t += ANTICIPATION_T
            starts.append(t)
            t += FLIP_STAGGER
        return starts

    # ------------------------------------------------------------------
    # Geometry
    # ------------------------------------------------------------------

    def _slot_center(self, i: int) -> tuple[float, float]:
        n = len(self._cards)
        total_w = n * CARD_W + max(0, n - 1) * _GAP
        start_x = _SCREEN_W // 2 - total_w // 2
        return start_x + i * (CARD_W + _GAP) + CARD_W / 2, _CARD_Y + CARD_H / 2

    def _pack_rect(self) -> pygame.Rect:
        return self._pack.get_rect(center=_PACK_CENTER)

    # ------------------------------------------------------------------
    # State queries (used by tests and the manager)
    # ------------------------------------------------------------------

    @property
    def phase(self) -> str:
        """intro | idle | charge | burst | deal | reveal | pick | outro."""
        if self._phase != "open":
            return self._phase
        if self._t_open < BURST_T:
            return "burst"
        if not all(self._landed):
            return "deal"
        if self._t_open < self._pick_at:
            return "reveal"
        return "pick"

    @property
    def is_animating(self) -> bool:
        return self.phase not in ("idle", "pick")

    @property
    def particle_count(self) -> int:
        return self._fx.count

    # ------------------------------------------------------------------
    # Protocol
    # ------------------------------------------------------------------

    def handle_event(self, event: pygame.event.Event) -> None:
        if self.cleared:
            return
        if event.type == pygame.MOUSEMOTION:
            self._mouse = event.pos
            self._pack_hover = self.phase in ("intro", "idle") and self._pack_rect().collidepoint(event.pos)
            if self.phase == "pick":
                self._update_hover(event.pos)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self._mouse = event.pos
            self._advance_or_click(event.pos)
        elif event.type == pygame.KEYDOWN and event.key in (pygame.K_SPACE, pygame.K_RETURN, pygame.K_KP_ENTER):
            if self.phase != "pick":
                self._advance_or_click(None)

    def _advance_or_click(self, pos: tuple[int, int] | None) -> None:
        phase = self.phase
        if phase in ("intro", "idle"):
            self.start_charge()
        elif phase == "pick":
            if pos is not None:
                self._handle_click(pos)
        elif phase != "outro":
            self.skip_animation()

    def start_charge(self) -> None:
        """Begin opening (the click on the pack)."""
        if self._phase in ("intro", "idle"):
            self._phase = "charge"
            self._t = 0.0
            self._sound.play_confirm()

    def skip_animation(self) -> None:
        """Jump straight to the pick screen (every card dealt and face-up)."""
        if self._phase in ("intro", "idle", "charge"):
            self._open()
        if self._phase != "open":
            return
        self._t_open = max(self._t_open, self._pick_at)
        self._landed = [True] * len(self._cards)
        self._flipped = [True] * len(self._cards)
        self._fx.clear()
        self._flash = 0.0
        self._shake = 0.0

    def update(self, dt: float) -> None:
        dt = min(0.1, max(0.0, dt))
        self._time += dt
        self._motes.update(dt)
        self._fx.update(dt)
        self._flash = max(0.0, self._flash - dt * 2.8)
        self._shake *= math.exp(-7.0 * dt)
        if self._shake > 0.3:
            a = self._shake
            self._shake_off = (int(self._rng.uniform(-a, a)), int(self._rng.uniform(-a, a)))
        else:
            self._shake_off = (0, 0)

        if self._phase == "intro":
            self._t += dt
            if self._t >= INTRO_T:
                self._phase, self._t = "idle", 0.0
        elif self._phase == "idle":
            self._t += dt
            if self._rng.random() < dt * 5:
                r = self._pack_rect()
                self._fx.emit(self._rng.uniform(r.left, r.right), self._rng.uniform(r.top, r.bottom),
                              0.0, self._rng.uniform(-40, -20), life=self._rng.uniform(0.6, 1.1),
                              palette=self._palette[:3], size=self._rng.uniform(4, 8), style=GLOW)
        elif self._phase == "charge":
            self._t += dt
            u = self._t / CHARGE_T
            self._shake = max(self._shake, 1.0 + 6.0 * u * u)
            n = int(dt * (40 + 160 * u)) + (1 if self._rng.random() < 0.5 else 0)
            self._fx.implode(*_PACK_CENTER, n, palette=self._palette[:3],
                             radius=(150.0, 280.0), life=(0.25, 0.45), size=(1.5, 3.0))
            if self._t >= CHARGE_T:
                self._open()
        elif self._phase == "open":
            self._update_open(dt)
        elif self._phase == "outro":
            self._t_out += dt
            if self._t_out >= OUTRO_T:
                self.cleared = True

    def _open(self) -> None:
        """The tear: flash, shake, explosion, pieces fly."""
        self._phase = "open"
        self._t_open = 0.0
        self._flash = 1.0
        self._shake = 14.0
        self._sound.play_open_pack()
        cx, cy = _PACK_CENTER
        tear_screen_y = self._pack_rect().top + self._tear_y
        pal = self._palette
        fx = self._fx
        fx.burst(cx, cy, 110, palette=pal, speed=(120, 620), life=(0.5, 1.2), size=(3, 7),
                 drag=2.2, gravity=260, spread=40)
        fx.burst(cx, tear_screen_y, 70, palette=pal[:3], speed=(250, 800), life=(0.25, 0.6),
                 size=(1.5, 3.0), style=SPARK, drag=3.0, spread=60)
        fx.burst(cx, cy, 26, palette=pal[:3], speed=(40, 260), life=(0.5, 1.0), size=(14, 34),
                 style=GLOW, drag=2.5, spread=50)
        fx.burst(cx, tear_screen_y, 45, palette=self._accent, speed=(200, 520),
                 angle=(-math.pi * 0.95, -math.pi * 0.05), life=(0.9, 1.6), size=(3, 5),
                 drag=1.2, gravity=520)
        # strip flies up and away spinning; body drops
        self._strip_state = [0.0, 0.0, self._rng.uniform(140, 220), -560.0, 0.0]
        self._body_state = [0.0, -60.0]

    def _update_open(self, dt: float) -> None:
        self._t_open += dt
        s = self._strip_state
        s[2] *= 1.0 - 0.4 * dt
        s[3] += 1500.0 * dt
        s[0] += s[2] * dt
        s[1] += s[3] * dt
        s[4] -= 300.0 * dt
        b = self._body_state
        b[1] += 900.0 * dt
        b[0] += b[1] * dt

        for i, card in enumerate(self._cards):
            start = BURST_T + i * DEAL_STAGGER
            if i == 0 and not self._landed[0] and self._t_open - dt < start <= self._t_open:
                self._sound.play_card()
            if not self._landed[i] and self._t_open >= start + DEAL_EACH:
                self._landed[i] = True
                x, y = self._slot_center(i)
                self._fx.burst(x, y + CARD_H / 2, 8, palette=_SILVER, speed=(40, 140),
                               angle=(math.pi, math.tau), life=(0.25, 0.5), size=(2, 3), drag=4.0)
            fs = self._flip_start[i]
            r = _rarity(card)
            if (_is_special(card) and not self._flipped[i]
                    and fs - ANTICIPATION_T <= self._t_open < fs and self._rng.random() < dt * 30):
                x, y = self._slot_center(i)
                self._fx.implode(x, y, 2, palette=_reveal_palette(card)[:3], radius=(90, 150),
                                 life=(0.2, 0.35))
            if not self._flipped[i] and self._t_open >= fs + FLIP_T * 0.5:
                self._flipped[i] = True
                self._flip_burst(i)

        if self.phase == "pick":
            self._update_sparkles(dt)

    def _flip_burst(self, i: int) -> None:
        r = _rarity(self._cards[i])
        v = r.value
        pal = RARITY_PALETTE[r]
        x, y = self._slot_center(i)
        fx = self._fx
        fx.burst(x, y, 8 + 6 * v, palette=pal, speed=(80, 200 + 50 * v), life=(0.35, 0.8),
                 size=(2, 4), drag=2.5, spread=30)
        fx.burst(x, y, 4 * v, palette=pal[:2], speed=(200, 380 + 40 * v), life=(0.2, 0.45),
                 size=(1.5, 2.5), style=SPARK, drag=3.0, spread=20)
        if v >= CardRarity.RARE.value:
            fx.burst(x, y, 2 * v, palette=pal[:3], speed=(20, 120), life=(0.4, 0.8),
                     size=(16, 30), style=GLOW, drag=3.0, spread=25)
        if r is CardRarity.LEGENDARY:
            fx.burst(x, y - CARD_H / 2, 55, palette=_GOLD, speed=(220, 460),
                     angle=(-math.pi * 0.9, -math.pi * 0.1), life=(1.0, 1.7), size=(3, 5),
                     drag=1.0, gravity=560)
            self._shake = max(self._shake, 7.0)
            self._flash = max(self._flash, 0.35)
        if self._cards[i].chroma is not None:
            gold = _reveal_palette(self._cards[i])
            fx.burst(x, y - CARD_H / 2, 60, palette=gold, speed=(220, 480),
                     angle=(-math.pi * 0.95, -math.pi * 0.05), life=(1.0, 1.8), size=(3, 5),
                     drag=1.0, gravity=560)
            fx.burst(x, y, 12, palette=gold[:3], speed=(20, 140), life=(0.5, 0.9),
                     size=(18, 34), style=GLOW, drag=3.0, spread=30)
            self._shake = max(self._shake, 6.0)
            self._flash = max(self._flash, 0.3)
        if v >= CardRarity.EPIC.value or self._cards[i].chroma is not None:
            self._sound.play_reward()
        else:
            self._sound.play_card()

    def _update_sparkles(self, dt: float) -> None:
        for i, card in enumerate(self._cards):
            if self._phase == "outro":
                break
            rate = (_SPARKLE_RATE.get(_rarity(card), 0.0) + (4.0 if self._hovered == i else 0.0)
                    + (8.0 if card.chroma is not None else 0.0))
            if not rate:
                continue
            self._sparkle_acc[i] += rate * dt
            x, y = self._slot_center(i)
            lift = -20 if self._hovered == i else 0
            pal = _reveal_palette(card)
            while self._sparkle_acc[i] >= 1.0:
                self._sparkle_acc[i] -= 1.0
                rng = self._rng
                self._fx.emit(x + rng.uniform(-CARD_W / 2, CARD_W / 2),
                              y + lift + rng.uniform(-CARD_H / 2, CARD_H / 2),
                              rng.uniform(-8, 8), rng.uniform(-60, -25), life=rng.uniform(0.7, 1.3),
                              palette=pal[:3], size=rng.uniform(2, 3), style=SQUARE)

    # ------------------------------------------------------------------
    # Drawing
    # ------------------------------------------------------------------

    def draw(self, surface: pygame.Surface) -> None:
        surface.fill(_BG)
        ox, oy = self._shake_off
        phase = self.phase
        self._motes.draw(surface)
        self._draw_background_glow(surface, phase, ox, oy)

        if phase in ("intro", "idle", "charge"):
            self._draw_closed_pack(surface, phase, ox, oy)
        else:
            self._draw_rays(surface, ox, oy)
            self._draw_pack_pieces(surface, ox, oy)
            self._draw_cards(surface, phase, ox, oy)

        self._fx.draw(surface, (ox, oy))
        if self._flash > 0.0:
            if self._veil is None or self._veil.get_size() != surface.get_size():
                self._veil = pygame.Surface(surface.get_size())
                self._veil.fill((255, 255, 255))
            self._veil.set_alpha(int(255 * min(1.0, self._flash)))
            surface.blit(self._veil, (0, 0))
        self._draw_ui(surface, phase)
        if self._luck is not None:
            draw_luck_badge(surface, "bottomleft", (16, 704), self._luck, self._fonts)

    def _draw_background_glow(self, surface: pygame.Surface, phase: str, ox: int, oy: int) -> None:
        if phase in ("intro", "idle", "charge"):
            k = 0.45 + 0.12 * math.sin(self._time * 2.4)
            if phase == "idle" and self._pack_hover:
                k += 0.15
            if phase == "charge":
                k += 0.55 * (self._t / CHARGE_T)
            if phase == "intro":
                k *= ease_out_cubic(self._t / INTRO_T)
            center, radius = _PACK_CENTER, 300
        else:
            k = 0.4 if phase != "outro" else 0.4 * (1.0 - self._t_out / OUTRO_T)
            center, radius = (_SCREEN_W // 2, _CARD_Y + CARD_H // 2), 420
        k = round(k * 10) / 10
        if k <= 0:
            return
        g = soft_glow(scaled(self._glow_color, k), radius)
        surface.blit(g, (center[0] - radius + ox, center[1] - radius + oy),
                     special_flags=pygame.BLEND_RGB_ADD)

    def _draw_closed_pack(self, surface: pygame.Surface, phase: str, ox: int, oy: int) -> None:
        cx, cy = _PACK_CENTER
        angle = 0.0
        scale = 1.0
        if phase == "intro":
            e = ease_out_back(self._t / INTRO_T)
            cy = int(-_PACK_H + (cy + _PACK_H) * e)
        elif phase == "idle":
            cy += int(math.sin(self._time * 2.0) * 6)
            angle = math.sin(self._time * 1.3) * 2.0
            scale = 1.04 if self._pack_hover else 1.0
        else:
            u = self._t / CHARGE_T
            angle = math.sin(self._time * 55.0) * (1.5 + 4.0 * u)
            scale = 1.0 + 0.08 * u
        img = self._pack
        if self._pack_chroma is not None:
            img = chroma_fx.animate_card_face(img, self._pack_chroma, self._time, base_w=90)
        if angle or scale != 1.0:
            img = pygame.transform.rotozoom(img, angle, scale)
        surface.blit(img, img.get_rect(center=(cx + ox, cy + oy)))
        if self._pack_chroma is not None:
            chroma_fx.draw_motes(surface, img.get_rect(center=(cx + ox, cy + oy)), self._pack_chroma,
                                 self._time, count=18, scale=1.8)
        if phase == "charge":
            u = self._t / CHARGE_T
            white = self._pack_white
            if angle or scale != 1.0:
                white = pygame.transform.rotozoom(white, angle, scale)
            white.set_alpha(int(230 * u * u))
            surface.blit(white, white.get_rect(center=(cx + ox, cy + oy)))

    def _draw_rays(self, surface: pygame.Surface, ox: int, oy: int) -> None:
        t = self._t_open
        if self.phase == "outro":
            k = 0.5 * (1.0 - self._t_out / OUTRO_T)
        elif t < 0.25:
            k = t / 0.25
        else:
            k = max(0.0, 1.0 - (t - 0.25) / max(0.1, self._pick_at - 0.25)) * 0.8
        level = min(3, int(k * 4))
        if k <= 0.05:
            return
        rays = pygame.transform.rotate(self._rays[level], (self._time * 18.0) % 360)
        center = _PACK_CENTER if t < BURST_T + 0.4 else (_SCREEN_W // 2, _CARD_Y + CARD_H // 2)
        surface.blit(rays, rays.get_rect(center=(center[0] + ox, center[1] + oy)),
                     special_flags=pygame.BLEND_RGB_ADD)

    def _draw_pack_pieces(self, surface: pygame.Surface, ox: int, oy: int) -> None:
        t = self._t_open
        if t > 1.2:
            return
        rect = self._pack_rect()
        # body: holds for a moment (cards come out of it), then drops and fades
        fade = _clamp01((t - 0.35) / 0.6)
        if fade < 1.0:
            dy = self._body_state[0] if t > 0.1 else 0.0
            body = self._body.copy()
            body.set_alpha(int(255 * (1.0 - fade)))
            top = rect.top + self._tear_y - 10
            surface.blit(body, (rect.left + ox, top + int(max(0.0, dy)) + oy))
        s = self._strip_state
        if t < 1.1:
            strip = pygame.transform.rotozoom(self._strip, s[4], 1.0)
            strip.set_alpha(int(255 * (1.0 - _clamp01((t - 0.5) / 0.6))))
            c = (rect.centerx + s[0] + ox, rect.top + self._strip.get_height() / 2 + s[1] + oy)
            surface.blit(strip, strip.get_rect(center=(int(c[0]), int(c[1]))))

    def _blit_card(self, surface: pygame.Surface, img: pygame.Surface, cx: float, cy: float,
                   sx: float = 1.0, sy: float = 1.0, angle: float = 0.0, alpha: int = 255) -> None:
        w = max(1, int(CARD_W * abs(sx)))
        h = max(1, int(CARD_H * sy))
        s = img if (w, h) == img.get_size() else pygame.transform.smoothscale(img, (w, h))
        if angle:
            s = pygame.transform.rotozoom(s, angle, 1.0)
        if alpha < 255:
            if s is img:
                s = img.copy()
            s.set_alpha(max(0, alpha))
        surface.blit(s, s.get_rect(center=(int(cx), int(cy))))

    def _halo(self, surface: pygame.Surface, card: Card, cx: float, cy: float, k: float) -> None:
        r = _rarity(card)
        if not _is_special(card) or k <= 0:
            return
        k = round(min(1.0, k) * 8) / 8
        if card.chroma is not None:
            col = scaled(chroma_fx.style(card.chroma).glow, k * 0.6)
        else:
            col = scaled(RARITY_PALETTE[r][1], k * (0.35 + 0.12 * (r.value - 3)))
        radius = 125
        surface.blit(soft_glow(col, radius), (int(cx) - radius, int(cy) - radius),
                     special_flags=pygame.BLEND_RGB_ADD)

    def _draw_cards(self, surface: pygame.Surface, phase: str, ox: int, oy: int) -> None:
        if phase == "pick":
            self._draw_pick(surface, ox, oy)
            return
        if phase == "outro":
            self._draw_outro(surface, ox, oy)
            return
        t = self._t_open
        px, py = _PACK_CENTER[0], _PACK_CENTER[1] - 30
        for i, card in enumerate(self._cards):
            start = BURST_T + i * DEAL_STAGGER
            if t < start:
                continue
            tx, ty = self._slot_center(i)
            u = ease_out_cubic((t - start) / DEAL_EACH)
            x = px + (tx - px) * u
            y = py + (ty - py) * u - 70 * math.sin(math.pi * u)
            scale = 0.35 + 0.65 * u
            angle = self._deal_angle[i] * (1.0 - u)
            fs = self._flip_start[i]
            f = _clamp01((t - fs) / FLIP_T)
            pulse = 1.0 + 0.12 * math.sin(math.pi * f)
            sx = abs(math.cos(math.pi * f)) * scale * pulse
            img = self._back if f < 0.5 else self._face(card)
            if f >= 0.5 and card.chroma is not None:
                img = chroma_fx.animate_card_face(img, card.chroma, self._time)
            if _is_special(card):
                pre = _clamp01((t - (fs - ANTICIPATION_T)) / ANTICIPATION_T)
                self._halo(surface, card, x + ox, y + oy, pre * 1.4 if f < 1.0 else 1.0)
                if f == 0.0 and pre > 0:
                    x += math.sin(self._time * 60.0) * 2.5 * pre
            self._blit_card(surface, img, x + ox, y + oy, sx, scale * pulse, angle)

    def _face(self, card: Card) -> pygame.Surface:
        dmg, blk = self._bonus.for_card(card)
        return render_card_surface(card, self._fonts, bonus_damage=dmg, bonus_block=blk)

    def _draw_pick(self, surface: pygame.Surface, ox: int, oy: int) -> None:
        n = len(self._cards)
        total_w = n * CARD_W + max(0, n - 1) * _GAP
        start_x = _SCREEN_W // 2 - total_w // 2
        self._card_rects = []
        for i, card in enumerate(self._cards):
            cx, cy = self._slot_center(i)
            pulse = 0.85 + 0.15 * math.sin(self._time * 3.0 + i)
            self._halo(surface, card, cx + ox, cy + oy - (20 if self._hovered == i else 0),
                       pulse * (1.25 if self._hovered == i else 1.0))
            dmg, blk = self._bonus.for_card(card)
            if card.lucky_drop:                         # luck added this card: mark it
                lift = -20 if (self._hovered == i or i in self._chosen) else 0
                card_fx.draw_lucky_back(surface, pygame.Rect(start_x + i * (CARD_W + _GAP) + ox,
                                                             _CARD_Y + oy + lift, CARD_W, CARD_H), self._time)
            rect = draw_card(surface, card, start_x + i * (CARD_W + _GAP) + ox, _CARD_Y + oy,
                             self._fonts, hovered=(self._hovered == i), selected=(i in self._chosen),
                             bonus_damage=dmg, bonus_block=blk)
            if card.lucky_drop:
                card_fx.draw_lucky_front(surface, rect, self._time, self._fonts)
            self._card_rects.append(rect.move(-ox, -oy))

    def _draw_outro(self, surface: pygame.Surface, ox: int, oy: int) -> None:
        u = ease_out_cubic(self._t_out / OUTRO_T)
        for i, card in enumerate(self._cards):
            if i in self._chosen:
                continue
            cx, cy = self._slot_center(i)
            self._blit_card(surface, self._face(card), cx + ox,
                            cy + 60 * u + oy, alpha=int(255 * (1.0 - u)))
        n = len(self._chosen)
        for k, idx in enumerate(self._chosen):
            card = self._cards[idx]
            sx, sy = self._slot_center(idx)
            tx = _SCREEN_W / 2 + (k - (n - 1) / 2) * (CARD_W * 1.35 + 30)
            ty = _SCREEN_H / 2 - 20
            x, y = sx + (tx - sx) * u, (sy - 20) + (ty - sy + 20) * u
            scale = 1.0 + 0.35 * u
            col = _reveal_palette(card)[1]
            radius = int(150 * scale)
            surface.blit(soft_glow(scaled(col, 0.55), radius),
                         (int(x) - radius + ox, int(y) - radius + oy), special_flags=pygame.BLEND_RGB_ADD)
            face = self._face(card)
            if card.chroma is not None:
                face = chroma_fx.animate_card_face(face, card.chroma, self._time)
            self._blit_card(surface, face, x + ox, y + oy, scale, scale)

    def _draw_ui(self, surface: pygame.Surface, phase: str) -> None:
        cx = surface.get_width() // 2
        self._skip_rect = None
        if phase in ("intro", "idle", "charge"):
            t = self._fonts.get(24).render(self._pack_name, True, colors.TEXT_ACCENT)
            surface.blit(t, t.get_rect(centerx=cx, centery=50))
            if phase == "idle":
                hint = self._fonts.get(15).render("Haz clic en el sobre para abrirlo", True,
                                                  colors.TEXT_PRIMARY)
                hint.set_alpha(int(150 + 105 * (0.5 + 0.5 * math.sin(self._time * 3.2))))
                surface.blit(hint, hint.get_rect(centerx=cx, centery=_PACK_CENTER[1] + _PACK_H // 2 + 40))
            return
        if phase == "pick":
            t = self._fonts.get(24).render(f"Abriendo: {self._pack_name}", True, colors.TEXT_ACCENT)
            surface.blit(t, t.get_rect(centerx=cx, centery=50))
            left = self._picks - len(self._chosen)
            text = ("Elige una carta para añadir a tu mazo:" if self._picks == 1 else
                    f"Sobre {'dorado' if self._pack_chroma is Chroma.GOLDEN else 'especial'}: "
                    f"elige {self._picks} cartas (te quedan {left})")
            sub = self._fonts.get(13).render(text, True, colors.TEXT_PRIMARY)
            surface.blit(sub, sub.get_rect(centerx=cx, centery=90))

            ss = self._fonts.get(14).render("Terminar" if self._chosen else "Omitir", True,
                                            colors.TEXT_SECONDARY)
            sr = ss.get_rect(centerx=cx, centery=_CARD_Y + CARD_H + 40)
            self._skip_rect = pygame.Rect(sr.x - 10, sr.y - 6, sr.width + 20, sr.height + 12)
            pygame.draw.rect(surface, colors.BG_PANEL,     self._skip_rect, border_radius=5)
            pygame.draw.rect(surface, colors.PANEL_BORDER, self._skip_rect, 1, border_radius=5)
            surface.blit(ss, sr)

            if self._hovered is not None and self._hovered < len(self._cards):
                dmg, blk = self._bonus.for_card(self._cards[self._hovered])
                tip = card_tooltip(self._cards[self._hovered], bonus_damage=dmg, bonus_block=blk)
                draw_tooltip(surface, tip, self._mouse, self._fonts)
        elif phase != "outro":
            skip = self._fonts.get(12).render("Clic para saltar", True, colors.TEXT_SECONDARY)
            surface.blit(skip, skip.get_rect(centerx=cx, centery=_SCREEN_H - 28))

    # ------------------------------------------------------------------
    # Input
    # ------------------------------------------------------------------

    def _update_hover(self, pos: tuple[int, int]) -> None:
        previous = self._hovered
        self._hovered = None
        for i, rect in enumerate(self._card_rects):
            if rect.collidepoint(pos):
                self._hovered = i
                if i != previous:
                    self._sound.play_nav()
                return

    def _handle_click(self, pos: tuple[int, int]) -> None:
        if self.cleared or self.phase != "pick":
            return
        for i, rect in enumerate(self._card_rects):
            if rect.collidepoint(pos):
                self.choose(i)
                return
        if self._skip_rect and self._skip_rect.collidepoint(pos):
            self._sound.play_cancel()
            self.chosen_card = self.chosen_cards[0] if self.chosen_cards else None
            self.cleared     = True

    def choose(self, i: int) -> None:
        """Keep card ``i``; after the last allowed pick plays the outro, then sets ``cleared``."""
        if self.phase != "pick" or not 0 <= i < len(self._cards) or i in self._chosen:
            return
        self._sound.play_reward()
        self._chosen.append(i)
        self.chosen_cards.append(self._cards[i])
        self.chosen_card = self.chosen_cards[0]
        if len(self._chosen) >= self._picks:
            self._hovered = None
            self._phase = "outro"
            self._t_out = 0.0
        x, y = self._slot_center(i)
        pal = _reveal_palette(self._cards[i])
        self._fx.burst(x, y - 20, 50, palette=pal, speed=(120, 420), life=(0.4, 0.9), size=(2, 5),
                       drag=2.5, spread=40)
        self._fx.burst(x, y - 20, 10, palette=pal[:3], speed=(20, 120), life=(0.4, 0.7),
                       size=(18, 30), style=GLOW, drag=3.0, spread=30)
