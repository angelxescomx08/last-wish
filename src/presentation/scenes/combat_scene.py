from __future__ import annotations

import pygame

from src.application import relic_effects
from src.application.end_turn import end_player_turn
from src.application.play_card import play_card
from src.domain.combat import CombatState
from src.infrastructure import colors
from src.infrastructure.fonts import FontRegistry
from src.presentation.ui.card_widget import CARD_H, CARD_W, draw_card
from src.presentation.ui.entity_widget import (
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
from src.presentation.ui.tooltip import (
    TooltipContent,
    card_tooltip,
    draw_tooltip,
    enemy_tooltip,
    mana_tooltip,
    pile_tooltip,
    player_tooltip,
    relic_tooltip,
)

# ---------------------------------------------------------------------------
# Layout constants (virtual canvas 1280×720)
# ---------------------------------------------------------------------------

_TOP_BAR_H: int    = 68
_HAND_AREA_Y: int  = 500
_CARD_Y: int       = 608
_CARD_GAP: int     = 8
_CARD_AREA_X0: int = 130
_CARD_AREA_X1: int = 1130

_ENEMY_Y: int  = 125
_PLAYER_X: int = 930
_PLAYER_Y: int = 90

_MANA_CX: int   = 68
_MANA_CY: int   = 595
_MANA_R: int    = 42          # orb radius (for hover detection)

_DRAW_X: int    = 1145
_DRAW_Y: int    = 565
_DISCARD_X: int = 1210
_DISCARD_Y: int = 565

_END_TURN_X: int = 1085
_END_TURN_Y: int = 15
_END_TURN_W: int = 183
_END_TURN_H: int = 38

_ENEMY_SLOTS: list[tuple[int, int]] = [
    (30,  _ENEMY_Y),
    (210, _ENEMY_Y),
    (390, _ENEMY_Y),
]

_TARGETING_COLOR: pygame.Color = pygame.Color(255, 190, 50)


def _card_positions(count: int) -> list[tuple[int, int]]:
    total_w = count * CARD_W + max(0, count - 1) * _CARD_GAP
    area_w  = _CARD_AREA_X1 - _CARD_AREA_X0
    start_x = _CARD_AREA_X0 + (area_w - total_w) // 2
    return [(start_x + i * (CARD_W + _CARD_GAP), _CARD_Y) for i in range(count)]


# ---------------------------------------------------------------------------
# Combat scene
# ---------------------------------------------------------------------------

class CombatScene:
    """Renders the full battle screen and drives all player interactions.

    Follows the Scene protocol: handle_event / update / draw.
    Game-rule mutations are delegated to use-case functions in application/.
    """

    def __init__(self, state: CombatState, fonts: FontRegistry) -> None:
        self._state              = state
        self._fonts              = fonts
        self._death_acknowledged = False  # prevents pushing DeathScene more than once

        # Mouse
        self._mouse: tuple[int, int] = (0, 0)

        # Hit-test rects (rebuilt each draw call)
        self._card_rects:     list[pygame.Rect]  = []
        self._enemy_rects:    list[pygame.Rect]  = []
        self._relic_rects:    list[pygame.Rect]  = []
        self._player_rect:    pygame.Rect | None = None
        self._end_turn_rect:  pygame.Rect | None = None
        self._draw_pile_rect: pygame.Rect | None = None
        self._disc_pile_rect: pygame.Rect | None = None

        # Hover state (which element index / flag is under cursor)
        self._hovered_card:      int | None = None
        self._hovered_enemy:     int | None = None
        self._hovered_relic:     int | None = None
        self._end_turn_hovered:  bool = False
        self._hovered_player:    bool = False
        self._hovered_mana:      bool = False
        self._hovered_draw_pile: bool = False
        self._hovered_disc_pile: bool = False

        # Overlay
        self._overlay: PileViewer | None = None

    # ------------------------------------------------------------------
    # Protocol
    # ------------------------------------------------------------------

    def handle_event(self, event: pygame.event.Event) -> None:
        if self._overlay is not None:
            self._overlay.handle_event(event)
            return

        if event.type == pygame.MOUSEMOTION:
            self._mouse = event.pos
            self._update_hover(event.pos)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self._handle_click(event.pos)
        elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self._state.selected_card_index = None

    def update(self, dt: float) -> None:
        if self._overlay is not None and self._overlay.dismissed:
            self._overlay = None

    def draw(self, surface: pygame.Surface) -> None:
        surface.fill(colors.BG_DARK)
        self._draw_top_bar(surface)
        self._draw_battlefield(surface)
        self._draw_hand_area(surface)

        if self._in_targeting_mode:
            self._draw_targeting_hint(surface)

        if self._overlay is not None:
            self._overlay.draw(surface)
        else:
            tooltip = self._get_tooltip()
            if tooltip is not None:
                draw_tooltip(surface, tooltip, self._mouse, self._fonts)

    # ------------------------------------------------------------------
    # Derived state
    # ------------------------------------------------------------------

    @property
    def death_occurred(self) -> bool:
        """True once the player's HP reaches 0 (latches until acknowledged)."""
        return not self._state.player.is_alive

    @property
    def turn_reached(self) -> int:
        return self._state.turn

    @property
    def _in_targeting_mode(self) -> bool:
        idx = self._state.selected_card_index
        if idx is None or idx >= self._state.hand.count:
            return False
        return self._state.hand.cards[idx].total_damage() > 0

    # ------------------------------------------------------------------
    # Drawing sections
    # ------------------------------------------------------------------

    def _draw_top_bar(self, surface: pygame.Surface) -> None:
        bar = pygame.Rect(0, 0, surface.get_width(), _TOP_BAR_H)
        pygame.draw.rect(surface, colors.BG_PANEL, bar)
        pygame.draw.line(surface, colors.PANEL_BORDER,
                         (0, _TOP_BAR_H - 1), (surface.get_width(), _TOP_BAR_H - 1))

        self._relic_rects = draw_relics(
            surface, self._state.relics, 10, 10, self._fonts,
            hovered_index=self._hovered_relic,
        )
        draw_turn_counter(surface, self._state.turn, surface.get_width() // 2, 34, self._fonts)

        self._end_turn_rect = draw_end_turn_button(
            surface, _END_TURN_X, _END_TURN_Y, _END_TURN_W, _END_TURN_H,
            self._fonts, hovered=self._end_turn_hovered,
        )

    def _draw_battlefield(self, surface: pygame.Surface) -> None:
        pygame.draw.line(surface, colors.PANEL_BORDER,
                         (0, _HAND_AREA_Y), (surface.get_width(), _HAND_AREA_Y))

        targeting = self._in_targeting_mode
        self._enemy_rects = []

        for i, enemy in enumerate(self._state.enemies):
            if i >= len(_ENEMY_SLOTS):
                break
            ex, ey = _ENEMY_SLOTS[i]
            rect = draw_enemy(
                surface, enemy, ex, ey, self._fonts,
                targeted    = self._state.targeted_enemy_index == i,
                highlighted = targeting and enemy.is_alive,
            )
            self._enemy_rects.append(rect)

        self._player_rect = draw_player(
            surface, self._state.player, _PLAYER_X, _PLAYER_Y, self._fonts
        )

        if self._state.active_powers:
            self._draw_active_powers(surface)

    def _draw_active_powers(self, surface: pygame.Surface) -> None:
        label_surf = self._fonts.get(10).render("PODERES ACTIVOS", True, colors.TEXT_SECONDARY)
        surface.blit(label_surf, (560, _HAND_AREA_Y - 80))
        for i, card in enumerate(self._state.active_powers):
            draw_card(surface, card, 560 + i * (CARD_W + 6), _HAND_AREA_Y - 78, self._fonts)

    def _draw_hand_area(self, surface: pygame.Surface) -> None:
        hand_bg = pygame.Rect(0, _HAND_AREA_Y, 1280, 720 - _HAND_AREA_Y)
        pygame.draw.rect(surface, colors.BG_CARD_AREA, hand_bg)

        draw_mana(surface, self._state.mana, _MANA_CX, _MANA_CY, self._fonts)

        relic_atk_bonus = relic_effects.extra_attack_damage(self._state.relics)
        char_atk_bonus  = self._state.player.attack_bonus
        char_blk_bonus  = self._state.player.dexterity

        cards     = self._state.hand.cards
        positions = _card_positions(len(cards))
        self._card_rects = []
        for i, (card, (cx, cy)) in enumerate(zip(cards, positions)):
            bonus_dmg = (relic_atk_bonus + char_atk_bonus) if card.total_damage() > 0 else 0
            bonus_blk = char_blk_bonus if card.total_block() > 0 else 0
            rect = draw_card(
                surface, card, cx, cy, self._fonts,
                selected     = self._state.selected_card_index == i,
                hovered      = self._hovered_card == i,
                affordable   = self._state.mana.can_afford(card.cost),
                bonus_damage = bonus_dmg,
                bonus_block  = bonus_blk,
            )
            self._card_rects.append(rect)

        self._draw_pile_rect = draw_pile_widget(
            surface, "ROBO", self._state.draw_pile.count,
            _DRAW_X, _DRAW_Y, self._fonts,
        )
        self._disc_pile_rect = draw_pile_widget(
            surface, "DESCARTE", self._state.discard_pile.count,
            _DISCARD_X, _DISCARD_Y, self._fonts,
        )

        hc_surf = self._fonts.get(11).render(
            f"MANO  {self._state.hand.count}/{self._state.hand.max_size}",
            True, colors.TEXT_SECONDARY,
        )
        surface.blit(hc_surf, (_MANA_CX + 52, _MANA_CY + 26))

    def _draw_targeting_hint(self, surface: pygame.Surface) -> None:
        msg_surf = self._fonts.get(15).render(
            "Selecciona un enemigo objetivo  ·  ESC para cancelar",
            True, _TARGETING_COLOR,
        )
        surface.blit(msg_surf, msg_surf.get_rect(centerx=640, centery=_HAND_AREA_Y - 16))

    # ------------------------------------------------------------------
    # Tooltip
    # ------------------------------------------------------------------

    def _get_tooltip(self) -> TooltipContent | None:
        if self._hovered_card is not None and self._hovered_card < self._state.hand.count:
            card      = self._state.hand.cards[self._hovered_card]
            bonus_dmg = (
                relic_effects.extra_attack_damage(self._state.relics)
                + self._state.player.attack_bonus
            ) if card.total_damage() > 0 else 0
            bonus_blk = self._state.player.dexterity if card.total_block() > 0 else 0
            return card_tooltip(card, bonus_damage=bonus_dmg, bonus_block=bonus_blk)

        if self._hovered_enemy is not None and self._hovered_enemy < len(self._state.enemies):
            return enemy_tooltip(self._state.enemies[self._hovered_enemy])

        if self._hovered_relic is not None and self._hovered_relic < len(self._state.relics):
            return relic_tooltip(self._state.relics[self._hovered_relic])

        if self._hovered_player:
            return player_tooltip(self._state.player)

        if self._hovered_mana:
            return mana_tooltip(self._state.mana)

        if self._hovered_draw_pile:
            return pile_tooltip("ROBO", self._state.draw_pile.count, is_draw=True)

        if self._hovered_disc_pile:
            return pile_tooltip("DESCARTE", self._state.discard_pile.count, is_draw=False)

        return None

    # ------------------------------------------------------------------
    # Hover detection
    # ------------------------------------------------------------------

    def _update_hover(self, pos: tuple[int, int]) -> None:
        self._hovered_card     = None
        self._hovered_enemy    = None
        self._hovered_relic    = None
        self._hovered_player   = False
        self._hovered_mana     = False
        self._hovered_draw_pile = False
        self._hovered_disc_pile = False
        self._end_turn_hovered = False

        for i, rect in enumerate(self._card_rects):
            if _card_hover_rect(rect).collidepoint(pos):
                self._hovered_card = i
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
        # Pile viewers
        if self._draw_pile_rect and self._draw_pile_rect.collidepoint(pos):
            self._overlay = PileViewer(
                "Pila de Robo", list(self._state.draw_pile.cards), self._fonts
            )
            return

        if self._disc_pile_rect and self._disc_pile_rect.collidepoint(pos):
            self._overlay = PileViewer(
                "Pila de Descarte", list(self._state.discard_pile.cards), self._fonts
            )
            return

        # End turn
        if self._end_turn_rect and self._end_turn_rect.collidepoint(pos):
            end_player_turn(self._state)
            return

        # Targeting mode: click enemy → play card; click card → switch; click blank → cancel
        if self._in_targeting_mode:
            for i, rect in enumerate(self._enemy_rects):
                if rect.collidepoint(pos):
                    if i < len(self._state.enemies) and self._state.enemies[i].is_alive:
                        play_card(self._state, self._state.selected_card_index, i)  # type: ignore[arg-type]
                    return
            for i, rect in enumerate(self._card_rects):
                if _card_hover_rect(rect).collidepoint(pos):
                    card = self._state.hand.cards[i]
                    if card.total_damage() > 0:
                        self._state.selected_card_index = i
                    elif self._state.mana.can_afford(card.cost):
                        play_card(self._state, i, None)
                    return
            self._state.selected_card_index = None
            return

        # Normal card click
        for i, rect in enumerate(self._card_rects):
            if _card_hover_rect(rect).collidepoint(pos):
                card       = self._state.hand.cards[i]
                needs_target = card.total_damage() > 0
                can_afford   = self._state.mana.can_afford(card.cost)

                if needs_target:
                    self._state.selected_card_index = (
                        None if self._state.selected_card_index == i else i
                    )
                elif can_afford:
                    play_card(self._state, i, None)
                return

        # Click on empty space clears selection
        self._state.selected_card_index = None


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _card_hover_rect(rect: pygame.Rect) -> pygame.Rect:
    return pygame.Rect(rect.x, rect.y - 22, rect.width, rect.height + 22)
