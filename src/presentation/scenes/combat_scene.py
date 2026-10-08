from __future__ import annotations

import math
from dataclasses import dataclass

import pygame

from src.application.enemy_roster import PAIRS, VENGEANCE_ID
from src.application import relic_effects
from src.application.end_turn import cards_per_turn, end_player_turn
from src.application.play_card import TargetKind, play_card, target_kind
from src.domain.combat import CombatState
from src.application.card_preview import combat_card_bonus
from src.application.enemy_ai import intent_hit_damage
from src.domain.entities import BLADES, IntentType, status_stacks
from src.infrastructure.enemy_sprites import sheet_for_enemy
from src.infrastructure import colors
from src.infrastructure.audio import SoundPlayer
from src.infrastructure.fonts import FontRegistry
from src.infrastructure.sprite_loader import (
    IDLE_CYCLE_SECONDS, SpriteLoader, has_hero_sprites, hero_animation_seconds, hero_id_for,
    hero_strike_seconds,
)
from src.presentation.ui.dungeon_backdrop import DungeonBackdrop
from src.presentation.fx.bursts import GLOW, SPARK, BurstParticles
from src.presentation.fx.enemy_animator import EnemyAnimator
from src.presentation.fx.hero_fx import HeroFx
from src.presentation.ui.fx import FxLayer
from src.presentation.ui.action_banner import ActionBanners, describe_action
from src.presentation.ui.card_play import CardPlayInput, PlayRequest
from src.presentation.ui.pixel_ui import (
    ManaOrb, button_state, draw_button, draw_panel, draw_topbar, draw_trim, outlined,
)
from src.infrastructure.ui_icons import ui_icon
from src.presentation.ui.card_widget import CARD_H, CARD_W, _RARITY_COLOR, card_size, draw_card, draw_card_at
from src.presentation.ui.targeting import RETICLE_ENEMY, RETICLE_SELF, draw_arrow, draw_reticle
from src.presentation.ui.entity_widget import (
    ENEMY_H,
    PLAYER_H,
    ENEMY_W,
    PLAYER_W,
    draw_enemy,
    draw_player,
)
from src.presentation.ui.hud_widget import (
    RELIC_SZ,
    _RELIC_GAP,
    draw_end_turn_button,
    draw_mana,
    draw_pile_widget,
    draw_relics,
    draw_turn_counter,
)
from src.presentation.ui.pile_viewer import PileViewer
from src.presentation.ui.relic_viewer import RelicViewer
from src.presentation.ui.collection_viewer import CollectionViewer
from src.presentation.ui.tooltip import (
    TooltipContent,
    card_tooltip,
    draw_tooltip,
    enemy_tooltip,
    intent_tooltip,
    mana_tooltip,
    pile_tooltip,
    status_tooltip,
    player_tooltip,
    relic_tooltip,
)

# ---------------------------------------------------------------------------
# Layout constants (virtual canvas 1280×720)
# ---------------------------------------------------------------------------

_TOP_BAR_H: int    = 68
_HAND_AREA_Y: int  = 465
_CARD_Y: int       = 524   # bottom = 524+194 = 718, within 720
_CARD_GAP: int     = 28
_CARD_AREA_X0: int = 180   # reserve left mana and right pile controls
_CARD_AREA_X1: int = 1100

_ENEMY_Y: int  = 125
_PLAYER_X: int = 195
_PLAYER_Y: int = 90

_MANA_CX: int   = 68
_MANA_CY: int   = 595
_MANA_R: int    = 42          # orb radius (for hover detection)

_DRAW_X: int    = 1160
_DRAW_Y: int    = 484
_DISCARD_X: int = 1160
_DISCARD_Y: int = 596

_END_TURN_X: int = 1074
_END_TURN_Y: int = 9
_END_TURN_W: int = 196
_END_TURN_H: int = 48
_ENEMY_PHASE: float = 1.3      # seconds the End Turn button shows "Turno enemigo"

_ENEMY_SLOTS: list[tuple[int, int]] = [
    (762, _ENEMY_Y),
    (942, _ENEMY_Y),
    (1122, _ENEMY_Y),
]

# Bosses with a big animated sheet stand alone in a wider slot, a bit lower (closer to the
# camera); their name and intent float above the top of the sprite.
_BOSS_CX: int = 905
_BOSS_GROUND: int = 314
_BOSS_W: int = 230
_CARD_NAMES_ES: dict[str, str] = {"status_espora": "Espora", "status_moho": "Moho"}
_TOXIC = (170, 230, 70)
_HEAL_TEXT = (120, 236, 120)
_VENGEANCE_TEXT = (255, 90, 70)
_VENGEANCE_DELAY = 1.0          # after the blow (or blast) that killed the partner
_DEBUFF_TEXT = (220, 120, 240)

_TARGETING_COLOR: pygame.Color = pygame.Color(255, 190, 50)

# Hand fan and card play (Slay the Spire style)
_PLAY_LINE_Y: int = _HAND_AREA_Y          # release above this line to play
_HAND_BASE_Y: float = _CARD_Y + CARD_H / 2 - 12  # centre line of the resting hand
_HOVER_SCALE: float = 1.3
_AIM_SCALE: float = 1.1
_AIM_CENTER: tuple[float, float] = (640.0, 500.0)
_MAX_TILT: float = 10.0
_TILT_STEP: float = 2.5                   # degrees per card away from the middle
_NEIGHBOUR_PUSH: float = 46.0             # px the neighbours of a hovered card move away
_EASE: float = 16.0                       # hand tween speed (1/s)
_EASE_HELD: float = 32.0                  # held card follows the pointer faster
_LEAVE_SECONDS: float = 0.3               # played card flies to the discard pile
# Multi-cast replay (golden cards): the rules resolve instantly, the screen replays each cast.
_CAST_INTRO: float = 0.35                  # card flies to the stage before the first cast
_CAST_GAP: float = 0.65                    # time between casts
_CAST_OUTRO: float = 0.8                   # linger after the last cast (see the kill)
_KILL_HOLD: float = 0.7                    # any killing blow: wait before declaring victory
_DEATH_HOLD: float = 0.35                  # after the hero's death animation, before the defeat screen
_CAST_STAGE: tuple[float, float] = (560.0, 250.0)
_GOLD = ((255, 250, 210), (255, 214, 90), (230, 150, 30), (140, 80, 10))
_ENEMY_HIT_PAD: tuple[int, int] = (40, 70)
_PLAYABLE = (255, 212, 60)
_HELD = (240, 232, 214)


@dataclass
class CardPose:
    x: float
    y: float
    scale: float = 1.0
    angle: float = 0.0


def _card_positions(count: int) -> list[tuple[int, int]]:
    if count == 0:
        return []
    area_w = _CARD_AREA_X1 - _CARD_AREA_X0
    step = min(CARD_W + _CARD_GAP, (area_w - CARD_W) / max(1, count - 1))
    total_w = CARD_W + step * (count - 1)
    start_x = _CARD_AREA_X0 + (area_w - total_w) / 2
    return [(round(start_x + i * step), _CARD_Y) for i in range(count)]


def _hand_layout(count: int, hovered: int | None = None, held: int | None = None) -> dict[int, CardPose]:
    """Resting pose of every card in hand: a gentle fan (tilt + arc).

    The hovered card grows, stands straight and rises until it is fully
    visible; its neighbours slide away. The held card leaves the fan and the
    others close the gap.
    """
    indices = [i for i in range(count) if i != held]
    slots = _card_positions(len(indices))
    mid = (len(indices) - 1) / 2
    hovered_k = indices.index(hovered) if hovered in indices else None
    poses: dict[int, CardPose] = {}
    for k, (i, (x, _y)) in enumerate(zip(indices, slots)):
        off = k - mid
        cx = x + CARD_W / 2
        if hovered_k is not None:
            d = k - hovered_k
            if d == 0:
                poses[i] = CardPose(cx, 718 - CARD_H * _HOVER_SCALE / 2, _HOVER_SCALE, 0.0)
                continue
            if abs(d) <= 2:
                cx += math.copysign(_NEIGHBOUR_PUSH / abs(d), d)
        angle = max(-_MAX_TILT, min(_MAX_TILT, -off * _TILT_STEP))
        poses[i] = CardPose(cx, _HAND_BASE_Y + min(14.0, off * off * 1.2), 1.0, angle)
    return poses


def _pose_rect(pose: CardPose) -> pygame.Rect:
    w, h = card_size(pose.scale)
    return pygame.Rect(round(pose.x) - w // 2, round(pose.y) - h // 2, w, h)


# ---------------------------------------------------------------------------
# Combat scene
# ---------------------------------------------------------------------------

class CombatScene:
    """Renders the full battle screen and drives all player interactions.

    Follows the Scene protocol: handle_event / update / draw.
    Game-rule mutations are delegated to use-case functions in application/.
    """

    def __init__(
        self,
        state: CombatState,
        fonts: FontRegistry,
        *,
        is_boss: bool = False,
        sound: SoundPlayer | None = None,
    ) -> None:
        self._state               = state
        self._fonts               = fonts
        self._sprites             = SpriteLoader()
        self._backdrop            = DungeonBackdrop()
        self._idle_time = 0.0
        self._hero_action: str | None = None   # attack | guard | hurt | cast | death
        self._hero_id = hero_id_for(state.player.name) or "warrior"
        self._hero_action_time = 0.0
        self._is_boss             = is_boss
        self._death_acknowledged  = False
        self._victory_acknowledged = False
        self._initial_enemy_count = len(state.enemies)

        self._sound = sound if sound is not None else SoundPlayer()
        self._fx    = FxLayer(fonts.get(16))

        # Mouse and card play
        self._mouse: tuple[int, int] = (0, 0)
        self._play = CardPlayInput(_PLAY_LINE_Y)
        self._motion: dict[tuple[int, int], CardPose] = {}
        self._leaving: list[list] = []         # [card, pose, age, bonus_dmg, bonus_blk]
        self._sequence: dict | None = None     # multi-cast replay in progress (golden cards)
        self._hold_time = 0.0                  # delay before victory after a killing blow
        self._shown_enemies: list[tuple[int, int]] | None = None   # (hp, block) drawn during a replay
        self._shown_player_block: int | None = None
        self._bursts = BurstParticles(400, seed=11)
        self._fx_time = 0.0
        # Animated enemies (sprite sheets in assets/enemies/), keyed by enemy index
        # Keyed by enemy id (indices shift when the dead are removed); ``_enemy_anims`` is the
        # same set keyed by the current index. Each enemy keeps the screen slot it started in,
        # and an animator whose enemy left the list keeps drawing until its death/explosion ends.
        self._anim_by_id: dict[str, EnemyAnimator] = {}
        self._slot_of: dict[str, int] = {e.id: i for i, e in enumerate(state.enemies)}
        self._gone: list[tuple[EnemyAnimator, int]] = []
        self._avenging: set[str] = set()
        for i, enemy in enumerate(state.enemies):
            sheet = sheet_for_enemy(enemy.name)
            if sheet is not None:
                self._anim_by_id[enemy.id] = EnemyAnimator(sheet, seed=31 + 17 * i, phase=0.47 * i)
        self._enemy_anims: dict[int, EnemyAnimator] = {}
        self._sync_enemy_anims()
        self._pending_hero_hurt: float | None = None     # hero flinches when the enemy claws land
        self._pending_hero_name = "hurt"                # ... or falls ("death")
        # Code-drawn heroes (sheet with a strike event) get timed particles and a floor shadow.
        strike = hero_strike_seconds(self._hero_id) if has_hero_sprites(state.player.name) else 0.0
        self._hero_fx: HeroFx | None = HeroFx(strike=strike, seed=5) if strike > 0 else None

        # Hit-test rects (rebuilt each draw call)
        self._card_rects:     list[pygame.Rect]  = []
        self._enemy_rects:    list[pygame.Rect]  = []
        self._relic_rects:    list[pygame.Rect]  = []
        self._player_rect:    pygame.Rect | None = None
        self._end_turn_rect:  pygame.Rect | None = None
        self._draw_pile_rect: pygame.Rect | None = None
        self._disc_pile_rect: pygame.Rect | None = None
        self._relic_collection_rect = pygame.Rect(10, 16, 164, 36)
        self._hand_collection_rect = pygame.Rect(12, 668, 150, 36)
        self._draw_info_rect = pygame.Rect(770, 12, 290, 42)
        # Pause + hero buttons in the free gap between the relic bar (184–449) and the turn ribbon.
        self.pause_button_rect = pygame.Rect(460, 16, 64, 36)
        self._orb = ManaOrb()
        self._enemy_phase = 0.0
        self._mouse_down = False
        self.gold_hud_pos = ("topleft", (12, 476))     # the top bar is full: above the mana orb
        self._card_draw_order: list[int] = []

        # Hover state (which element index / flag is under cursor)
        self._hovered_card:      int | None = None
        self._hovered_enemy:     int | None = None
        self._hovered_relic:     int | None = None
        self._end_turn_hovered:  bool = False
        self._hovered_player:    bool = False
        self._hovered_mana:      bool = False
        self._hovered_draw_pile: bool = False
        self._hovered_disc_pile: bool = False
        self._hovered_detail: tuple | None = None    # ("intent", i) / ("status", i or "player", j)
        self._enemy_hitboxes: list[dict] = []
        self._player_hitboxes: dict = {}

        # Overlay
        self._overlay: CollectionViewer | None = None
        self._feedback_text = ""
        self._feedback_time = 0.0
        self._banners = ActionBanners()
        self._announce_pair()

    # ------------------------------------------------------------------
    # Protocol
    # ------------------------------------------------------------------

    def handle_event(self, event: pygame.event.Event) -> None:
        if self._overlay is not None:
            self._overlay.handle_event(event)
            return
        if self.presentation_busy and event.type in (pygame.MOUSEBUTTONDOWN, pygame.KEYDOWN):
            return      # a multi-cast replay is playing: wait for it

        if event.type == pygame.MOUSEMOTION:
            self._mouse = event.pos
            self._play.move(event.pos, self._enemy_at(event.pos))
            if self._play.active:
                self._clear_hover()
            else:
                self._update_hover(event.pos)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self._mouse_down = True
            self._handle_click(event.pos)
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self._mouse_down = False
            self._handle_release(event.pos)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 3:
            self._cancel_selection()
        elif event.type == pygame.KEYDOWN:
            self._handle_key(event.key)

    def update(self, dt: float) -> None:
        self._advance_hero_animation(max(0.0, dt))
        hero = (_PLAYER_X + PLAYER_W / 2, _PLAYER_Y + PLAYER_H / 2 - 8)
        for i, anim in self._enemy_anims.items():
            if anim.style.blades and i < len(self._state.enemies):
                anim.blades = status_stacks(self._state.enemies[i].status_effects, BLADES)
                anim.target = hero
        for anim in self._anim_by_id.values():
            anim.update(dt)
        self._gone = [(a, slot) for a, slot in self._gone if a.busy]
        self._announce_vengeance()
        if self._hero_fx is not None:
            self._hero_fx.update(dt)
        if self._pending_hero_hurt is not None:
            self._pending_hero_hurt -= max(0.0, dt)
            if self._pending_hero_hurt <= 0:
                self._pending_hero_hurt = None
                self._play_hero_action(self._pending_hero_name)
        self._backdrop.update(max(0.0, dt))
        if self._overlay is not None and self._play.cancel():
            self._state.selected_card_index = None
        if self._overlay is not None and self._overlay.dismissed:
            self._overlay = None
            self._sound.play_cancel()
        self._feedback_time = max(0.0, self._feedback_time - dt)
        self._banners.update(dt)
        self._orb.update(dt, self._state.mana)
        self._enemy_phase = max(0.0, self._enemy_phase - max(0.0, dt))
        self._fx.update(dt)
        self._fx_time += max(0.0, dt)
        self._advance_cards(max(0.0, dt))
        self._bursts.update(dt)
        self._hold_time = max(0.0, self._hold_time - max(0.0, dt))
        self._advance_sequence(max(0.0, dt))

    def draw(self, surface: pygame.Surface) -> None:
        self._backdrop.draw(surface)
        self._draw_top_bar(surface)
        self._draw_battlefield(surface)
        self._draw_hand_area(surface)

        self._draw_leaving(surface)
        self._draw_cast_stage(surface)
        self._bursts.draw(surface)
        self._banners.draw(surface, self._fonts)
        self._fx.draw(surface)
        if self._feedback_time > 0:
            message = self._fonts.get(16).render(self._feedback_text, True, (245, 165, 125))
            surface.blit(message, message.get_rect(center=(640, _HAND_AREA_Y - 48)))

        self._draw_targets(surface)
        self._draw_held_card(surface)
        if self._play.active:
            self._draw_targeting_hint(surface)

        if self._overlay is not None:
            self._overlay.draw(surface)
        elif not self._play.active:
            tooltip = self._get_tooltip()
            if tooltip is not None:
                hovered = self._hovered_card
                beside = (self._card_rects[hovered]
                          if hovered is not None and hovered < len(self._card_rects) else None)
                draw_tooltip(surface, tooltip, self._mouse, self._fonts, beside=beside)

    # ------------------------------------------------------------------
    # Derived state
    # ------------------------------------------------------------------

    @property
    def presentation_busy(self) -> bool:
        """A multi-cast replay or a killing blow is still on screen (victory waits for it)."""
        return self._sequence is not None or self._hold_time > 0

    @property
    def death_occurred(self) -> bool:
        """True once the player's HP reaches 0 (latches until acknowledged)."""
        if self.presentation_busy or self._pending_hero_hurt is not None:
            return False
        if self._hero_action == "death" and \
                self._hero_action_time < hero_animation_seconds("death", self._hero_id) + _DEATH_HOLD:
            return False                       # let her fall before the defeat screen
        return not self._state.player.is_alive

    @property
    def combat_won(self) -> bool:
        """True when all enemies are dead and victory hasn't been acknowledged."""
        if self._victory_acknowledged or self.presentation_busy or self.enemies_dying:
            return False
        if self._initial_enemy_count == 0:
            return False
        return len(self._state.enemies) == 0 or all(
            not e.is_alive for e in self._state.enemies
        )

    @property
    def enemies_dying(self) -> bool:
        """An animated enemy is still playing its death (victory waits for it)."""
        return any(a.dead and not a.death_done for a in self._anim_by_id.values())

    @property
    def enemy_animators(self) -> dict[int, EnemyAnimator]:
        return self._enemy_anims

    @property
    def is_boss(self) -> bool:
        return self._is_boss

    @property
    def turn_reached(self) -> int:
        return self._state.turn

    @property
    def state(self) -> CombatState:
        return self._state

    @property
    def _in_targeting_mode(self) -> bool:
        """True while an enemy card is aimed (arrow on screen)."""
        return self._play.aiming

    # ------------------------------------------------------------------
    # Drawing sections
    # ------------------------------------------------------------------

    def _draw_top_bar(self, surface: pygame.Surface) -> None:
        draw_topbar(surface, _TOP_BAR_H)
        t = self._idle_time

        self._relic_rects = draw_relics(
            surface, self._state.relics[:5], 184, 10, self._fonts,
            hovered_index=self._hovered_relic,
            sprites=self._sprites,
        )
        rc = self._relic_collection_rect
        draw_button(surface, rc, f"Reliquias ({len(self._state.relics)})", self._fonts, icon="bag",
                    state=button_state(rc, self._mouse, self._mouse_down), t=t, size=14)

        info = self._draw_info_rect
        draw_panel(surface, info)
        nominal_draw = cards_per_turn(self._state)
        count = min(nominal_draw, self._state.hand.max_size)
        x = info.x + 12
        for icon_name, text in (("draw", f"Robo: {count}/turno"), ("hand_cards", f"Mano máx.: {self._state.hand.max_size}")):
            icon = ui_icon(icon_name, 2)
            if icon is not None:
                surface.blit(icon, icon.get_rect(midleft=(x, info.centery)))
                x += icon.get_width() + 3
            label = outlined(self._fonts.get(14), text)
            surface.blit(label, label.get_rect(midleft=(x, info.centery)))
            x += label.get_width() + 16
        draw_turn_counter(surface, self._state.turn, surface.get_width() // 2 + 22, 34, self._fonts)

        rect = pygame.Rect(_END_TURN_X, _END_TURN_Y, _END_TURN_W, _END_TURN_H)
        self._end_turn_rect = draw_end_turn_button(
            surface, _END_TURN_X, _END_TURN_Y, _END_TURN_W, _END_TURN_H,
            self._fonts, hovered=rect.collidepoint(self._mouse), pressed=self._mouse_down,
            enabled=self._enemy_phase <= 0, ready=self.nothing_to_play, t=t,
        )

    @property
    def nothing_to_play(self) -> bool:
        """No card in hand can be played now (unplayable or too expensive): End Turn pulses."""
        mana = self._state.mana
        return not any(not c.unplayable and mana.can_afford(self._state.card_cost(c))
                       for c in self._state.hand.cards)

    def _draw_battlefield(self, surface: pygame.Surface) -> None:
        pygame.draw.line(surface, colors.PANEL_BORDER,
                         (0, _HAND_AREA_Y), (surface.get_width(), _HAND_AREA_Y))

        self._enemy_rects = []
        self._enemy_hitboxes = []
        incoming = self._incoming_damage()
        lethal = incoming - self._state.player.block >= self._state.player.current_hp > 0
        t = self._idle_time

        for anim, slot in self._gone:                     # left the fight, still exploding/dying
            gx, gy = _ENEMY_SLOTS[min(slot, len(_ENEMY_SLOTS) - 1)]
            anim.draw(surface, (gx + ENEMY_W // 2, gy + ENEMY_H + 6))
        for i, enemy in enumerate(self._state.enemies):
            slot = self._slot_of.get(enemy.id, i)
            if slot >= len(_ENEMY_SLOTS):
                break
            ex, ey = _ENEMY_SLOTS[slot]
            shown = self._shown_enemies
            saved = None
            if shown is not None and i < len(shown):      # replay: show HP/block cast by cast
                saved = (enemy.current_hp, enemy.block)
                enemy.current_hp, enemy.block = shown[i]
            anim = self._enemy_anims.get(i)
            hit = intent_hit_damage(enemy, self._state.player)
            boxes: dict = {}
            attacking = lethal and enemy.intent.intent_type == IntentType.ATTACK
            extra = dict(intent_damage=hit, lethal=attacking, t=t, hitboxes=boxes)
            try:
                if anim is not None and anim.sheet.is_boss:
                    rect = self._boss_rect(anim)
                    anim.draw(surface, (_BOSS_CX, _BOSS_GROUND))
                    if enemy.is_alive:
                        rect = draw_enemy(surface, enemy, rect.x, rect.y, self._fonts,
                                          targeted=self._state.targeted_enemy_index == i,
                                          framed=False, size=rect.size, **extra)
                elif anim is not None:
                    rect = pygame.Rect(ex, ey, ENEMY_W, ENEMY_H)
                    anim.draw(surface, (rect.centerx, rect.bottom + 6))
                    if enemy.is_alive:
                        rect = draw_enemy(surface, enemy, ex, ey, self._fonts,
                                          targeted=self._state.targeted_enemy_index == i,
                                          framed=False, **extra)
                else:
                    rect = draw_enemy(
                        surface, enemy, ex, ey, self._fonts,
                        targeted    = self._state.targeted_enemy_index == i,
                        sprite      = self._sprites.get_enemy_sprite(enemy.name),
                        **extra,
                    )
            finally:
                if saved is not None:
                    enemy.current_hp, enemy.block = saved
            self._enemy_rects.append(rect)
            self._enemy_hitboxes.append(boxes)

        real_block = self._state.player.block
        if self._shown_player_block is not None:
            self._state.player.block = self._shown_player_block
        try:
            self._draw_player(surface)
        finally:
            self._state.player.block = real_block

        if self._state.active_powers:
            self._draw_active_powers(surface)

    @staticmethod
    def _boss_rect(anim: EnemyAnimator) -> pygame.Rect:
        """Hit / label rect of a boss: from the top of its sprite down to just above its feet."""
        height = max(120, anim.sheet.anchor[1] - anim.sheet.top - 4)
        top = max(_TOP_BAR_H + 60, _BOSS_GROUND - height)   # room for the intent above the name
        return pygame.Rect(_BOSS_CX - _BOSS_W // 2, top, _BOSS_W, _BOSS_GROUND - 6 - top)

    def _draw_player(self, surface: pygame.Surface) -> None:
        center = (_PLAYER_X + PLAYER_W / 2, _PLAYER_Y + PLAYER_H / 2)
        if self._hero_fx is not None:
            self._hero_fx.draw_shadow(surface, center)
        self._draw_player_sprite(surface)
        if self._hero_fx is not None:
            self._hero_fx.draw(surface, center)

    def _incoming_damage(self) -> int:
        """Damage every living enemy's ATTACK intent will deal this enemy turn (before block)."""
        player = self._state.player
        return sum(intent_hit_damage(e, player) * max(1, e.intent.hits)
                   for e in self._state.enemies
                   if e.is_alive and e.intent.intent_type == IntentType.ATTACK)

    def _draw_player_sprite(self, surface: pygame.Surface) -> None:
        player = self._state.player
        loss = max(0, self._incoming_damage() - player.block) if self._shown_enemies is None else 0
        self._player_hitboxes = {}
        self._player_rect = draw_player(
            surface, self._state.player, _PLAYER_X, _PLAYER_Y, self._fonts,
            sprite=self._sprites.get_player_sprite(self._state.player.name,
                size=192 if has_hero_sprites(self._state.player.name) else 128,
                elapsed=self._hero_action_time if self._hero_action else self._idle_time,
                animation=self._hero_action or "idle"),
            framed=not has_hero_sprites(self._state.player.name),
            incoming_loss=loss, t=self._idle_time, hitboxes=self._player_hitboxes,
        )

    def _draw_active_powers(self, surface: pygame.Surface) -> None:
        label_surf = self._fonts.get(10).render("PODERES ACTIVOS", True, colors.TEXT_SECONDARY)
        surface.blit(label_surf, (560, _HAND_AREA_Y - 80))
        for i, card in enumerate(self._state.active_powers):
            draw_card(surface, card, 560 + i * (CARD_W + 6), _HAND_AREA_Y - 78, self._fonts)

    def _draw_hand_area(self, surface: pygame.Surface) -> None:
        hand_bg = pygame.Rect(0, _HAND_AREA_Y, 1280, 720 - _HAND_AREA_Y)
        pygame.draw.rect(surface, colors.BG_CARD_AREA, hand_bg)
        shade = _hand_shade(hand_bg.size)
        surface.blit(shade, hand_bg.topleft)
        draw_trim(surface, _HAND_AREA_Y)

        draw_mana(surface, self._state.mana, _MANA_CX, _MANA_CY, self._fonts, orb=self._orb)

        relic_atk_bonus = relic_effects.extra_attack_damage(self._state.relics)
        char_atk_bonus  = self._state.player.attack_bonus
        char_blk_bonus  = self._state.player.dexterity

        cards = self._state.hand.cards
        poses = self._target_poses()
        held = self._held_index()
        self._card_rects = [_pose_rect(poses[i]) for i in range(len(cards))]
        self._card_draw_order = [i for i in range(len(cards)) if i != held]
        hovered = self._hovered_card if held is None else None
        if hovered in self._card_draw_order:
            self._card_draw_order.remove(hovered)
            self._card_draw_order.append(hovered)
        keys = self._card_keys()
        for i in self._card_draw_order:
            card = cards[i]
            pose = self._motion.get(keys[i]) or self._spawn_pose()
            bonus_dmg, bonus_blk = self._bonuses(card)
            draw_card_at(
                surface, card, (pose.x, pose.y), self._fonts,
                scale        = pose.scale,
                angle        = pose.angle,
                affordable   = self._state.mana.can_afford(self._state.card_cost(card)),
                cost         = self._state.card_cost(card),
                bonus_damage = bonus_dmg,
                bonus_block  = bonus_blk,
                outline      = _RARITY_COLOR.get(card.rarity) if i == hovered else None,
                combo        = self._combo_ready(card),
                singular     = self._state.singular_ready(card),
                void         = self._state.void_ready(card),
                spoil        = self._state.spoil_ready(card),
            )

        self._draw_pile_rect = draw_pile_widget(
            surface, "ROBO", self._state.draw_pile.count,
            _DRAW_X, _DRAW_Y, self._fonts, hovered=self._hovered_draw_pile,
        )
        self._disc_pile_rect = draw_pile_widget(
            surface, "DESCARTE", self._state.discard_pile.count,
            _DISCARD_X, _DISCARD_Y, self._fonts, hovered=self._hovered_disc_pile,
        )

        hc = self._hand_collection_rect
        draw_button(surface, hc, f"Mano {self._state.hand.count}/{self._state.hand.max_size}", self._fonts,
                    icon="hand_cards", state=button_state(hc, self._mouse, self._mouse_down),
                    t=self._idle_time, size=14)

    def _card_hit_order(self) -> list[int]:
        # Match actual stacking so the visible, raised card receives the click.
        return [i for i in reversed(self._card_draw_order) if i < self._state.hand.count]

    def _draw_targeting_hint(self, surface: pygame.Surface) -> None:
        play = self._play
        if play.kind is TargetKind.ENEMY:
            if play.keyboard_aim:
                text = "←/→ cambia de objetivo  ·  Enter para jugar  ·  ESC para cancelar"
            elif play.sticky:
                text = "Haz clic en un enemigo  ·  Clic derecho para cancelar"
            else:
                text = "Suelta sobre un enemigo  ·  Vuelve a la mano para cancelar"
        elif play.by_key:
            text = "Enter para jugar  ·  ESC para cancelar"
        elif play.armed:
            text = "Suelta para jugar la carta" if not play.sticky else "Haz clic para jugar la carta"
        else:
            text = "Arrástrala fuera de la mano para jugarla  ·  Clic derecho para cancelar"
        msg_surf = self._fonts.get(15).render(text, True, _TARGETING_COLOR)
        surface.blit(msg_surf, msg_surf.get_rect(centerx=640, centery=_TOP_BAR_H + 16))

    # ------------------------------------------------------------------
    # Hand motion, held card, arrow
    # ------------------------------------------------------------------

    def _combo_ready(self, card) -> bool:
        """Keyword COMBO would trigger if ``card`` were played now."""
        return self._state.combo_active and bool(card.combo_effects())

    def _ready_damage(self, card) -> int:
        """Printed damage of ``card`` with every keyword layer that would resolve now."""
        return card.total_damage(self._combo_ready(card), self._state.singular_ready(card),
                                 self._state.void_ready(card), self._state.spoil_ready(card))

    def _bonuses(self, card) -> tuple[int, int]:
        combo, singular = self._combo_ready(card), self._state.singular_ready(card)
        void, spoil = self._state.void_ready(card), self._state.spoil_ready(card)
        scarf = relic_effects.combo_scarf_bonus(self._state.relics) if combo else 0
        dmg = (relic_effects.extra_attack_damage(self._state.relics) + self._state.player.attack_bonus
               + self._state.next_damage_bonus + scarf) if card.total_damage(combo, singular, void, spoil) > 0 else 0
        blk = (self._state.player.dexterity + scarf) if card.total_block(combo, singular, void, spoil) > 0 else 0
        return dmg, blk

    def _held_index(self) -> int | None:
        card = self._play.card if self._play.active else None
        return card if card is not None and card < self._state.hand.count else None

    def _card_keys(self) -> list[tuple[int, int]]:
        """Stable identity per card in hand (the same Card object may repeat)."""
        seen: dict[int, int] = {}
        keys = []
        for card in self._state.hand.cards:
            n = seen.get(id(card), 0)
            seen[id(card)] = n + 1
            keys.append((id(card), n))
        return keys

    def _spawn_pose(self) -> CardPose:
        """New cards fly in from the draw pile."""
        if self._draw_pile_rect is not None:
            x, y = self._draw_pile_rect.center
        else:
            x, y = _DRAW_X + 40, _DRAW_Y + 40
        return CardPose(float(x), float(y), 0.3, 0.0)

    def _target_poses(self) -> dict[int, CardPose]:
        held = self._held_index()
        hovered = self._hovered_card if held is None else None
        poses = _hand_layout(self._state.hand.count, hovered=hovered, held=held)
        if held is not None:
            if self._play.aiming or self._play.by_key:
                poses[held] = CardPose(*_AIM_CENTER, _AIM_SCALE, 0.0)
            else:
                px, py = self._play.pointer
                poses[held] = CardPose(float(px), float(py), 1.0, 0.0)
        return poses

    def _advance_cards(self, dt: float) -> None:
        poses = self._target_poses()
        held = self._held_index()
        keys = self._card_keys()
        k = 1.0 - math.exp(-_EASE * dt)
        k_held = 1.0 - math.exp(-_EASE_HELD * dt)
        for i, key in enumerate(keys):
            pose = self._motion.get(key)
            if pose is None:
                pose = self._motion[key] = self._spawn_pose()
            goal = poses[i]
            f = k_held if i == held else k
            pose.x += (goal.x - pose.x) * f
            pose.y += (goal.y - pose.y) * f
            pose.scale += (goal.scale - pose.scale) * f
            pose.angle += (goal.angle - pose.angle) * f
        live = set(keys)
        for key in [key for key in self._motion if key not in live]:
            del self._motion[key]
        if self._disc_pile_rect is not None:
            dx, dy = self._disc_pile_rect.center
        else:
            dx, dy = _DISCARD_X + 40, _DISCARD_Y + 40
        for ghost in self._leaving:
            pose = ghost[1]
            ghost[2] += dt
            pose.x += (dx - pose.x) * k
            pose.y += (dy - pose.y) * k
            pose.scale += (0.25 - pose.scale) * k
            pose.angle += (0.0 - pose.angle) * k
        self._leaving = [g for g in self._leaving if g[2] < _LEAVE_SECONDS]

    def _draw_leaving(self, surface: pygame.Surface) -> None:
        for card, pose, _age, dmg, blk in self._leaving:
            draw_card_at(surface, card, (pose.x, pose.y), self._fonts, scale=pose.scale,
                         angle=pose.angle, bonus_damage=dmg, bonus_block=blk)

    def _held_pose(self) -> CardPose | None:
        held = self._held_index()
        if held is None:
            return None
        return self._motion.get(self._card_keys()[held]) or self._target_poses()[held]

    def _draw_held_card(self, surface: pygame.Surface) -> None:
        held = self._held_index()
        pose = self._held_pose()
        if held is None or pose is None:
            return
        card = self._state.hand.cards[held]
        ready = self._play.armed or (self._play.aiming and self._play.target is not None)
        dmg, blk = self._bonuses(card)
        rect = draw_card_at(surface, card, (pose.x, pose.y), self._fonts, scale=pose.scale,
                            bonus_damage=dmg, bonus_block=blk,
                            outline=_PLAYABLE if ready else _HELD, combo=self._combo_ready(card),
                            singular=self._state.singular_ready(card),
                            void=self._state.void_ready(card), spoil=self._state.spoil_ready(card),
                            cost=self._state.card_cost(card))
        if self._play.aiming:
            draw_arrow(surface, (rect.centerx, rect.top + 6), self._arrow_end(),
                       hot=self._play.target is not None, phase=self._fx_time)

    def _arrow_end(self) -> tuple[float, float]:
        target = self._play.target
        if self._play.keyboard_aim and target is not None and target < len(self._enemy_rects):
            return self._enemy_rects[target].center
        return self._play.pointer

    def _draw_targets(self, surface: pygame.Surface) -> None:
        play = self._play
        if not play.active:
            return
        t = self._fx_time
        if play.kind is TargetKind.ENEMY:
            target = play.target
            if play.aiming and target is not None and target < len(self._enemy_rects):
                draw_reticle(surface, self._enemy_rects[target], RETICLE_ENEMY, t)
        elif play.armed:
            if play.kind is TargetKind.ALL_ENEMIES:
                for enemy, rect in zip(self._state.enemies, self._enemy_rects):
                    if enemy.is_alive:
                        draw_reticle(surface, rect, RETICLE_ENEMY, t)
            elif self._player_rect is not None:
                draw_reticle(surface, self._player_rect, RETICLE_SELF, t)

    def _enemy_at(self, pos: tuple[int, int]) -> int | None:
        for i, rect in enumerate(self._enemy_rects):
            if (i < len(self._state.enemies) and self._state.enemies[i].is_alive
                    and rect.inflate(*_ENEMY_HIT_PAD).collidepoint(pos)):
                return i
        return None

    def _card_at(self, pos: tuple[int, int]) -> int | None:
        for i in self._card_hit_order():
            if self._card_rects[i].collidepoint(pos):
                return i
        return None

    # ------------------------------------------------------------------
    # Tooltip
    # ------------------------------------------------------------------

    def _get_tooltip(self) -> TooltipContent | None:
        detail = self._detail_tooltip()
        if detail is not None:
            return detail
        if self._hovered_card is not None and self._hovered_card < self._state.hand.count:
            card      = self._state.hand.cards[self._hovered_card]
            bonus_dmg, bonus_blk = self._bonuses(card)
            return card_tooltip(card, bonus_damage=bonus_dmg, bonus_block=bonus_blk,
                                combo_active=self._combo_ready(card),
                                singular_active=self._state.singular_ready(card),
                                void_active=self._state.void_ready(card),
                                spoil_active=self._state.spoil_ready(card))

        if self._hovered_enemy is not None and self._hovered_enemy < len(self._state.enemies):
            enemy = self._state.enemies[self._hovered_enemy]
            return enemy_tooltip(enemy, intent_hit_damage(enemy, self._state.player), self._state.player)

        if self._hovered_relic is not None and self._hovered_relic < len(self._state.relics):
            return relic_tooltip(self._state.relics[self._hovered_relic])

        if self._draw_info_rect.collidepoint(self._mouse):
            return TooltipContent('Cartas por turno', [
                '5 cartas base',
                f'+{relic_effects.extra_draw_per_turn(self._state.relics)} por reliquias',
                'El robo se limita al espacio libre en la mano',
                'y a las cartas disponibles en robo y descarte.',
            ])
        if self._hovered_player:
            return player_tooltip(self._state.player, self._incoming_damage())

        if self._hovered_mana:
            return mana_tooltip(self._state.mana)

        if self._hovered_draw_pile:
            return pile_tooltip("ROBO", self._state.draw_pile.count, is_draw=True)

        if self._hovered_disc_pile:
            return pile_tooltip("DESCARTE", self._state.discard_pile.count, is_draw=False)

        return None

    def _detail_tooltip(self) -> TooltipContent | None:
        """Tooltip of a hovered intent or status badge (more precise than the whole enemy)."""
        d = self._hovered_detail
        if d is None:
            return None
        player = self._state.player
        if d[0] == "intent" and d[1] < len(self._state.enemies):
            enemy = self._state.enemies[d[1]]
            if enemy.is_alive:
                return intent_tooltip(enemy, intent_hit_damage(enemy, player), player)
        if d[0] == "status":
            owner, j = d[1], d[2]
            effects = (player.status_effects if owner == "player"
                       else self._state.enemies[owner].status_effects if owner < len(self._state.enemies) else [])
            if j < len(effects):
                return status_tooltip(effects[j], on_player=owner == "player")
        return None

    def _detail_at(self, pos: tuple[int, int]) -> tuple | None:
        for i, boxes in enumerate(self._enemy_hitboxes):
            if i < len(self._state.enemies) and not self._state.enemies[i].is_alive:
                continue
            rect = boxes.get("intent")
            if rect is not None and rect.inflate(6, 6).collidepoint(pos):
                return ("intent", i)
            for j, (_, badge) in enumerate(boxes.get("statuses", [])):
                if badge.collidepoint(pos):
                    return ("status", i, j)
        for j, (_, badge) in enumerate(self._player_hitboxes.get("statuses", [])):
            if badge.collidepoint(pos):
                return ("status", "player", j)
        return None

    # ------------------------------------------------------------------
    # Hover detection
    # ------------------------------------------------------------------

    def _clear_hover(self) -> None:
        self._hovered_card = self._hovered_enemy = self._hovered_relic = None
        self._hovered_player = self._hovered_mana = False
        self._hovered_draw_pile = self._hovered_disc_pile = self._end_turn_hovered = False
        self._hovered_detail = None

    def _update_hover(self, pos: tuple[int, int]) -> None:
        previous_card = self._hovered_card
        self._hovered_card     = None
        self._hovered_enemy    = None
        self._hovered_relic    = None
        self._hovered_player   = False
        self._hovered_mana     = False
        self._hovered_draw_pile = False
        self._hovered_disc_pile = False
        self._end_turn_hovered = False
        self._hovered_detail = None

        card = self._card_at(pos)
        if card is not None:
            self._hovered_card = card
            if card != previous_card:
                self._sound.play_nav()
            return

        self._hovered_detail = self._detail_at(pos)
        if self._hovered_detail is not None:
            return

        for i, rect in enumerate(self._enemy_rects):
            if rect.collidepoint(pos):
                self._hovered_enemy = i
                return

        for i, rect in enumerate(self._relic_rects):
            if rect.collidepoint(pos):
                self._hovered_relic = i
                return

        if self._player_rect and self._player_rect.collidepoint(pos):
            self._hovered_player = True
            return

        mx, my = pos
        if (mx - _MANA_CX) ** 2 + (my - _MANA_CY) ** 2 <= _MANA_R ** 2:
            self._hovered_mana = True
            return

        if self._draw_pile_rect and self._draw_pile_rect.collidepoint(pos):
            self._hovered_draw_pile = True
            return

        if self._disc_pile_rect and self._disc_pile_rect.collidepoint(pos):
            self._hovered_disc_pile = True
            return

        if self._end_turn_rect and self._end_turn_rect.collidepoint(pos):
            self._end_turn_hovered = True

    # ------------------------------------------------------------------
    # Click handling
    # ------------------------------------------------------------------

    def _handle_click(self, pos: tuple[int, int]) -> None:
        if self._relic_collection_rect.collidepoint(pos) or any(r.collidepoint(pos) for r in self._relic_rects):
            self._overlay = RelicViewer(self._state.relics, self._fonts)
            self._sound.play_confirm()
            return
        if self._hand_collection_rect.collidepoint(pos):
            self._overlay = PileViewer('Tu mano', list(self._state.hand.cards), self._fonts,
                                       combat_card_bonus(self._state))
            self._sound.play_card()
            return
        # Pile viewers
        if self._draw_pile_rect and self._draw_pile_rect.collidepoint(pos):
            self._overlay = PileViewer(
                "Pila de Robo", list(self._state.draw_pile.cards), self._fonts,
                combat_card_bonus(self._state),
            )
            self._sound.play_card()
            return

        if self._disc_pile_rect and self._disc_pile_rect.collidepoint(pos):
            self._overlay = PileViewer(
                "Pila de Descarte", list(self._state.discard_pile.cards), self._fonts,
                combat_card_bonus(self._state),
            )
            self._sound.play_card()
            return

        # End turn
        if self._end_turn_rect and self._end_turn_rect.collidepoint(pos):
            if self._enemy_phase <= 0:
                self._do_end_turn()
            return

        # A card under the pointer: pick it up (or switch to it)
        card_index = self._card_at(pos)
        if card_index is not None:
            self._pick_card(card_index, pos)
            return

        # A card held after a click: this click plays or drops it
        if self._play.active:
            self._finish(self._play.click(pos, self._enemy_at(pos)))
            return

        self._cancel_selection()

    def _handle_release(self, pos: tuple[int, int]) -> None:
        if self._play.active and not self._play.sticky:
            self._finish(self._play.release(pos, self._enemy_at(pos)))

    def _handle_key(self, key: int) -> None:
        if key == pygame.K_ESCAPE:
            self._cancel_selection()
        elif pygame.K_1 <= key <= pygame.K_9:
            index = key - pygame.K_1
            if index < self._state.hand.count:
                self._pick_card(index, None)
        elif key in (pygame.K_LEFT, pygame.K_RIGHT, pygame.K_TAB):
            alive = [i for i, e in enumerate(self._state.enemies) if e.is_alive]
            self._play.cycle_target(alive, -1 if key == pygame.K_LEFT else 1)
        elif key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
            if self._play.active:
                self._finish(self._play.confirm())
        elif key == pygame.K_e and self._enemy_phase <= 0:
            self._do_end_turn()

    def _pick_card(self, index: int, pos: tuple[int, int] | None) -> None:
        """Pick up a card with the mouse (``pos``) or with its number key."""
        card = self._state.hand.cards[index]
        if card.unplayable:
            self._show_error("Esta carta no se puede jugar")
            return
        if not self._state.mana.can_afford(self._state.card_cost(card)):
            self._orb.error()
            self._show_error("Maná insuficiente")
            return
        kind = target_kind(card)
        if pos is None:
            alive = [i for i, e in enumerate(self._state.enemies) if e.is_alive]
            self._play.pick_with_key(index, kind, alive[0] if alive else None)
        else:
            self._play.pick(index, kind, pos)
        self._state.selected_card_index = index
        self._hovered_card = None
        self._sound.play_confirm()

    def _finish(self, request: PlayRequest | None) -> None:
        """Play the returned card, or put the card back when nothing was played."""
        if request is not None:
            self._do_play_card(request.card_index, request.target_index)
        elif not self._play.active:
            self._state.selected_card_index = None

    # ------------------------------------------------------------------
    # Feedback helpers
    # ------------------------------------------------------------------

    def _cancel_selection(self) -> None:
        was_holding = self._play.cancel()
        if was_holding or self._state.selected_card_index is not None:
            self._state.selected_card_index = None
            self._sound.play_cancel()

    def _show_error(self, message: str) -> None:
        self._feedback_text = message
        self._feedback_time = 1.8
        self._sound.play_error()

    def _do_play_card(self, card_idx: int, target_idx: int | None) -> None:
        state         = self._state
        old_enemy_hps = [e.current_hp for e in state.enemies]
        old_enemy_blk = [e.block for e in state.enemies]
        old_block     = state.player.block
        is_attack     = (0 <= card_idx < state.hand.count
                         and self._ready_damage(state.hand.cards[card_idx]) > 0)

        self._play.cancel()
        played = state.hand.cards[card_idx] if 0 <= card_idx < state.hand.count else None
        played_pose = self._motion.get(self._card_keys()[card_idx]) if played is not None else None
        bonuses = self._bonuses(played) if played is not None else (0, 0)

        result = play_card(state, card_idx, target_idx)
        if not result.success:
            state.selected_card_index = None
            self._show_error(result.message)
            return
        self._feedback_time = 0.0
        self._hovered_card = None
        self._sound.play_card()
        if result.combo and self._player_rect:
            self._fx.add_text(self._player_rect.centerx, self._player_rect.top - 10, "¡COMBO!",
                              (90, 235, 180), lifetime=1.1)
        shown = 1 if result.combo else 0
        for flag, label, color in ((result.singular, "¡SINGULAR!", (185, 140, 255)),
                                   (result.void, "¡VACÍO!", (90, 170, 255)),
                                   (result.spoil, "¡DESPOJO!", (240, 150, 60))):
            if flag and self._player_rect:
                self._fx.add_text(self._player_rect.centerx, self._player_rect.top - 10 - 24 * shown,
                                  label, color, lifetime=1.1)
                shown += 1

        if result.casts > 1 and played is not None:
            # Golden: replay every cast on screen, one after another.
            start = (CardPose(played_pose.x, played_pose.y, played_pose.scale, played_pose.angle)
                     if played_pose is not None else CardPose(640.0, 600.0, 1.0, 0.0))
            self._sequence = {
                "card": played, "bonuses": bonuses, "result": result, "attack": is_attack,
                "start": start, "t": 0.0, "fired": 0, "pulse": 0.0,
                "prev_block": old_block, "prev_hp": list(old_enemy_hps),
            }
            self._shown_enemies = list(zip(old_enemy_hps, old_enemy_blk))
            self._shown_player_block = old_block
            return

        if played is not None and played_pose is not None:
            self._leaving.append([played, CardPose(played_pose.x, played_pose.y, played_pose.scale,
                                                   played_pose.angle), 0.0, *bonuses])
        block_gained = state.player.block - old_block
        if is_attack:
            self._play_hero_action("attack")
        elif block_gained > 0:
            self._play_hero_action("guard")
        else:
            self._play_hero_action("cast")        # skills and powers (heroes whose sheet has it)
        if block_gained > 0 and self._player_rect:
            self._fx.add_block_flash(self._player_rect, block_gained, flash=self._hero_fx is None)
            self._sound.play_block()

        # Enemies react when the blade connects (code-drawn hero), not when the card is played.
        delay = hero_strike_seconds(self._hero_id) if self._hero_action == "attack" and self._hero_fx else 0.0
        for i, (old_hp, enemy) in enumerate(zip(old_enemy_hps, state.enemies)):
            dmg = old_hp - enemy.current_hp
            if dmg > 0 and i < len(self._enemy_rects):
                self._enemy_hit(i, dmg, killed=not enemy.is_alive, delay=delay)

    # ------------------------------------------------------------------
    # Multi-cast replay (golden cards cast twice)
    # ------------------------------------------------------------------

    def _cast_time(self, k: int) -> float:
        return _CAST_INTRO + k * _CAST_GAP

    def _advance_sequence(self, dt: float) -> None:
        seq = self._sequence
        if seq is None:
            return
        seq["t"] += dt
        seq["pulse"] = max(0.0, seq["pulse"] - dt * 3.0)
        result = seq["result"]
        while seq["fired"] < result.casts and seq["t"] >= self._cast_time(seq["fired"]):
            self._fire_cast(seq["fired"])
            seq["fired"] += 1
        if seq["t"] >= self._cast_time(result.casts - 1) + _CAST_OUTRO:
            card, (dmg, blk) = seq["card"], seq["bonuses"]
            x, y = _CAST_STAGE
            self._leaving.append([card, CardPose(x, y, 0.95, 0.0), 0.0, dmg, blk])
            self._sequence = None
            self._shown_enemies = None
            self._shown_player_block = None

    def _fire_cast(self, k: int) -> None:
        """Show cast ``k``: hero action, hits, HP/block step, gold burst and label."""
        seq = self._sequence
        result = seq["result"]
        n = result.casts
        x, y = _CAST_STAGE
        seq["pulse"] = 1.0
        # gold flare on the staged card (bigger for the repeat casts)
        self._bursts.burst(x, y, 26 + 14 * k, palette=_GOLD, speed=(120, 420), life=(0.4, 0.9),
                           size=(2, 5), drag=2.5, spread=40)
        self._bursts.burst(x, y, 16, palette=_GOLD[:2], speed=(250, 520), life=(0.2, 0.4),
                           size=(1.5, 2.5), style=SPARK, drag=3.0, spread=30)
        self._bursts.burst(x, y, 6, palette=_GOLD[:3], speed=(10, 80), life=(0.4, 0.7),
                           size=(20, 34), style=GLOW, drag=3.0, spread=20)
        self._fx.add_text(x, y - 120, f"Lanzamiento {k + 1}/{n}", (255, 214, 90), lifetime=0.9)
        if k > 0:
            self._sound.play_card()
            if self._player_rect:
                self._fx.add_text(self._player_rect.centerx, self._player_rect.top - 34,
                                  f"¡x{k + 1}!", (255, 210, 80), lifetime=1.0)

        block = result.cast_player_block[k] if k < len(result.cast_player_block) else seq["prev_block"]
        gained = block - seq["prev_block"]
        seq["prev_block"] = block
        self._shown_player_block = block
        if seq["attack"]:
            self._play_hero_action("attack")
        elif gained > 0:
            self._play_hero_action("guard")
        if gained > 0 and self._player_rect:
            self._fx.add_block_flash(self._player_rect, gained)
            self._sound.play_block()

        hp_after = result.cast_enemy_hp[k] if k < len(result.cast_enemy_hp) else []
        blk_after = result.cast_enemy_block[k] if k < len(result.cast_enemy_block) else []
        self._shown_enemies = list(zip(hp_after, blk_after)) or self._shown_enemies
        for i, hit in enumerate(result.cast_hits[k] if k < len(result.cast_hits) else []):
            if hit > 0 and i < len(self._enemy_rects):
                killed = i < len(hp_after) and hp_after[i] <= 0 < seq["prev_hp"][i]
                self._enemy_hit(i, hit, killed=killed, hold=False)
        seq["prev_hp"] = list(hp_after) or seq["prev_hp"]

    def _draw_cast_stage(self, surface: pygame.Surface) -> None:
        """The golden card hovering on stage while its casts replay."""
        seq = self._sequence
        if seq is None:
            return
        u = min(1.0, seq["t"] / _CAST_INTRO)
        u = 1.0 - (1.0 - u) ** 3
        start = seq["start"]
        x = start.x + (_CAST_STAGE[0] - start.x) * u
        y = start.y + (_CAST_STAGE[1] - start.y) * u
        scale = start.scale + (0.95 - start.scale) * u + 0.14 * seq["pulse"]
        dmg, blk = seq["bonuses"]
        draw_card_at(surface, seq["card"], (x, y), self._fonts, scale=scale,
                     angle=start.angle * (1.0 - u), bonus_damage=dmg, bonus_block=blk)

    @property
    def hero_action(self) -> str | None:
        """Hero action animation currently playing (attack/guard/hurt), else None."""
        return self._hero_action

    def _play_hero_action(self, name: str) -> None:
        if self._hero_action == "death":
            return                                   # she stays down
        if hero_animation_seconds(name, self._hero_id) > 0:
            self._hero_action = name
            self._hero_action_time = 0.0
            if self._hero_fx is not None:
                self._hero_fx.play(name)

    def _advance_hero_animation(self, dt: float) -> None:
        if self._hero_action is None:
            self._idle_time = (self._idle_time + dt) % IDLE_CYCLE_SECONDS
            return
        self._hero_action_time += dt
        if self._hero_action == "death":
            return                                   # held on the last frame
        if self._hero_action_time >= hero_animation_seconds(self._hero_action, self._hero_id):
            # every action ends on idle frame 0, so idle restarts without a pop
            self._hero_action = None
            self._hero_action_time = 0.0
            self._idle_time = 0.0

    def _announce_actions(self, log, intents: dict, names: dict) -> None:
        """One banner per enemy that acted: its move and what it did to the hero."""
        self._banners.clear()
        for k, action in enumerate(a for a in log if a.index in intents):
            icon, title, detail = describe_action(names.get(action.index, ""), intents[action.index], action)
            self._banners.add(icon, title, detail, delay=0.12 * k)

    def _announce_extras(self, action, enemy_name: str, at: float) -> None:
        """Floating text for a boss move's debuffs and the status cards it adds."""
        if not self._player_rect:
            return
        x, y = self._player_rect.centerx + 60, self._player_rect.top + 70
        for j, (name, stacks) in enumerate(action.debuffs):
            self._fx.add_text(x, y - 18 * j, f"{name} {stacks}", _DEBUFF_TEXT, 1.3, delay=at + 0.1 * j)
        if action.cards:
            for j, (cid, n, pile) in enumerate(action.cards):
                self._fx.add_text(x, y - 18 * (len(action.debuffs) + j),
                                  f"+{n} {_CARD_NAMES_ES.get(cid, cid)}", _TOXIC, 1.4, delay=at + 0.15)

    def _enemy_hit(self, i: int, dmg: int, *, killed: bool, hold: bool = True,
                   delay: float = 0.0) -> None:
        """Damage number, sound and the enemy's reaction (hurt / death animation or flashes).

        ``delay`` (s) postpones the visuals until the hero's blade connects.
        """
        rect = self._enemy_rects[i]
        anim = self._enemy_anims.get(i)
        self._fx.add_hit_flash(rect, dmg, flash=anim is None, delay=delay)
        self._sound.play_attack()
        if killed:
            if anim is not None:
                anim.play("death", delay=delay)
            else:
                self._fx.add_death_flash(rect, delay=delay)
            self._sound.play_death()
            if hold:
                self._hold_time = _KILL_HOLD + delay      # let the kill be seen before victory
        elif anim is not None:
            anim.play("hurt", delay=delay)

    def _sync_enemy_anims(self, before: list | None = None) -> None:
        """Rebuild ``_enemy_anims`` (index → animator) for the current enemy list.

        Animators of enemies that left the list (dead, exploded) move to ``_gone`` so their
        last animation finishes in their old slot.
        """
        current = {e.id for e in self._state.enemies}
        for enemy in before or ():
            anim = self._anim_by_id.get(enemy.id)
            if enemy.id not in current and anim is not None:
                if anim.busy:                    # death / explosion playing or still queued
                    self._gone.append((anim, self._slot_of.get(enemy.id, 0)))
                else:
                    del self._anim_by_id[enemy.id]
        self._enemy_anims = {i: self._anim_by_id[e.id] for i, e in enumerate(self._state.enemies)
                             if e.id in self._anim_by_id}

    def _announce_vengeance(self) -> None:
        """A partner fell: "¡VENGANZA!" over the survivor once its intent turns into it."""
        for i, enemy in enumerate(self._state.enemies):
            if (enemy.is_alive and enemy.intent.move_id == VENGEANCE_ID
                    and enemy.id not in self._avenging and i < len(self._enemy_rects)):
                self._avenging.add(enemy.id)
                rect = self._enemy_rects[i]
                self._fx.add_text(rect.centerx, rect.top - 46, "¡VENGANZA!", _VENGEANCE_TEXT, 1.6,
                                  delay=_VENGEANCE_DELAY)
                anim = self._enemy_anims.get(i)
                if anim is not None:
                    anim.play("cast", delay=_VENGEANCE_DELAY)

    def _announce_pair(self) -> None:
        """Opening banner when the fight is a pair: its name and how the two work together."""
        names = {e.pair for e in self._state.enemies if e.pair}
        for pair in PAIRS.values():
            if pair.name in names:
                self._banners.add("buff", f"¡Pareja! {pair.name}", pair.synergy, delay=0.4)

    def _do_end_turn(self) -> None:
        state  = self._state
        old_hp = state.player.current_hp
        before = list(state.enemies)                      # indices of the log refer to this list
        old_enemy_hps = [e.current_hp for e in before]
        intents = {i: e.intent for i, e in enumerate(before) if e.is_alive}
        names = {i: e.name for i, e in enumerate(before)}

        self._play.cancel()
        self._sound.play_end_turn()
        self._enemy_phase = _ENEMY_PHASE
        end_player_turn(state)
        self._announce_actions(state.enemy_log, intents, names)

        # Animated enemies act out their move: the sheet may have a clip for it (bosses),
        # otherwise claws for attacks and a spell for the rest. Each hit lands on its strike.
        strike: float | None = None
        hit_times: list[tuple[float, int]] = []          # (seconds, HP lost) per hit on the hero
        k = 0
        for action in state.enemy_log:
            i = action.index
            anim = self._enemy_anims.get(i)
            if anim is None or i not in intents:
                continue
            delay = 0.14 * k
            k += 1
            fallback = "attack" if intents[i].intent_type == IntentType.ATTACK else "cast"
            name = anim.sheet.animation_for_move(action.move_id, fallback)
            if action.exploded and name not in anim.sheet.terminal:
                name = "death"                             # no explosion clip: just die
            hits = max(1, len(action.hits))
            anim.play(name, delay=delay, hits=hits)
            times = [delay + t for t in anim.strike_times(name, hits)]
            if action.hits and times:
                strike = times[0] if strike is None else min(strike, times[0])
                hit_times += [(times[min(j, len(times) - 1)], lost) for j, lost in enumerate(action.hits)]
            self._announce_extras(action, names.get(i, ""), (times[-1] if times else delay + 0.5))
        for action in state.enemy_log:                    # static enemies: extras too
            if action.index not in self._enemy_anims:
                self._announce_extras(action, names.get(action.index, ""), 0.2)
        exploded = {a.index for a in state.enemy_log if a.exploded}
        for i, (old, enemy) in enumerate(zip(old_enemy_hps, before)):
            if i >= len(self._enemy_rects):
                continue
            if old - enemy.current_hp > 0 and i not in exploded:          # e.g. poison
                self._enemy_hit(i, old - enemy.current_hp, killed=not enemy.is_alive)
            elif enemy.current_hp > old:                                   # vampire bite, prayer
                rect = self._enemy_rects[i]
                self._fx.add_text(rect.centerx, rect.top + 20, f"+{enemy.current_hp - old}",
                                  _HEAL_TEXT, 1.2, delay=0.55)
        for i in exploded:                                # the blast: screen shake + number
            if i < len(self._enemy_rects):
                self._sound.play_death()
                self._hold_time = max(self._hold_time, 1.2)
        self._sync_enemy_anims(before)

        dmg = old_hp - state.player.current_hp
        wait = strike or 0.0
        reaction = "hurt" if state.player.is_alive else "death"
        if dmg > 0:
            if wait > 0:
                self._pending_hero_hurt = wait
                self._pending_hero_name = reaction
            else:
                self._play_hero_action(reaction)
        if dmg > 0 and self._player_rect:
            shown = [(t, lost) for t, lost in hit_times if lost > 0]
            if len(shown) > 1 or (shown and sum(l for _, l in shown) < dmg):
                # one number per hit, each when its blow lands; leftovers (Veneno) at the end
                spread = len(shown)
                for j, (t, lost) in enumerate(shown):
                    self._fx.add_hit_flash(self._player_rect, lost, delay=t, flash=False,
                                           dx=(j - (spread - 1) / 2) * 18)
                rest = dmg - sum(l for _, l in shown)
                if rest > 0:
                    last = max([t for t, _ in shown], default=0.0)
                    self._fx.add_hit_flash(self._player_rect, rest, delay=last + 0.25, flash=False)
                    self._fx.add_text(self._player_rect.centerx + 60, self._player_rect.top + 50,
                                      "Veneno", _TOXIC, delay=last + 0.25)
            else:
                self._fx.add_hit_flash(self._player_rect, dmg, delay=wait, flash=self._hero_fx is None)
            self._sound.play_hit()


_SHADE_CACHE: dict = {}


def _hand_shade(size: tuple[int, int]) -> pygame.Surface:
    """Soft vertical darkening of the hand area (cached)."""
    shade = _SHADE_CACHE.get(size)
    if shade is None:
        w, h = size
        shade = pygame.Surface(size, pygame.SRCALPHA)
        for y in range(h):
            a = int(10 + 70 * (y / max(1, h - 1)) ** 1.5)
            pygame.draw.line(shade, (0, 0, 0, a), (0, y), (w, y))
        for y in range(0, 26):
            pygame.draw.line(shade, (255, 190, 110, int(22 * (1 - y / 26))), (0, y), (w, y))
        _SHADE_CACHE[size] = shade
    return shade
