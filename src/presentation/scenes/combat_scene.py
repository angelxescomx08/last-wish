from __future__ import annotations

import pygame

from src.domain.combat import CombatState
from src.domain.entities import Enemy
from src.infrastructure import colors
from src.infrastructure.fonts import FontRegistry
from src.presentation.ui.card_widget import (
    CARD_H,
    CARD_W,
    draw_card,
)
from src.presentation.ui.entity_widget import (
    ENEMY_H,
    ENEMY_W,
    PLAYER_H,
    PLAYER_W,
    draw_enemy,
    draw_player,
)
from src.presentation.ui.hud_widget import (
    RELIC_SZ,
    draw_end_turn_button,
    draw_mana,
    draw_pile_widget,
    draw_relics,
    draw_turn_counter,
)

# ---------------------------------------------------------------------------
# Layout constants
# ---------------------------------------------------------------------------

_TOP_BAR_H: int     = 68
_HAND_AREA_Y: int   = 500
_CARD_Y: int        = 608

_ENEMY_Y: int       = 125
_PLAYER_X: int      = 930
_PLAYER_Y: int      = 90

_CARD_GAP: int      = 8
_CARD_AREA_START: int = 130
_CARD_AREA_END: int   = 1130

_MANA_CX: int = 68
_MANA_CY: int = 595

_DRAW_X: int    = 1145
_DRAW_Y: int    = 565
_DISCARD_X: int = 1210
_DISCARD_Y: int = 565

_END_TURN_X: int = 1085
_END_TURN_Y: int = 15
_END_TURN_W: int = 183
_END_TURN_H: int = 38

_ENEMY_POSITIONS: list[tuple[int, int]] = [
    (30,  _ENEMY_Y),
    (210, _ENEMY_Y),
    (390, _ENEMY_Y),
]


def _card_positions(card_count: int) -> list[tuple[int, int]]:
    total_w = card_count * CARD_W + max(0, card_count - 1) * _CARD_GAP
    area_w  = _CARD_AREA_END - _CARD_AREA_START
    start_x = _CARD_AREA_START + (area_w - total_w) // 2
    return [(start_x + i * (CARD_W + _CARD_GAP), _CARD_Y) for i in range(card_count)]


# ---------------------------------------------------------------------------
# Combat scene
# ---------------------------------------------------------------------------

class CombatScene:
    """Renders the full battle screen from a CombatState.

    Follows the Scene protocol: handle_event / update / draw.
    All selection and hover state lives here, not in the domain.
    """

    def __init__(self, state: CombatState, fonts: FontRegistry) -> None:
        self._state  = state
        self._fonts  = fonts

        self._hovered_card: int | None   = None
        self._hovered_enemy: int | None  = None
        self._end_turn_hovered: bool     = False

        self._card_rects:  list[pygame.Rect] = []
        self._enemy_rects: list[pygame.Rect] = []
        self._end_turn_rect: pygame.Rect | None = None

    # ------------------------------------------------------------------
    # Protocol
    # ------------------------------------------------------------------

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.MOUSEMOTION:
            self._update_hover(event.pos)

        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self._handle_click(event.pos)

    def update(self, dt: float) -> None:
        pass  # future: animations, enemy timers

    def draw(self, surface: pygame.Surface) -> None:
        surface.fill(colors.BG_DARK)
        self._draw_top_bar(surface)
        self._draw_battlefield(surface)
        self._draw_hand_area(surface)

    # ------------------------------------------------------------------
    # Drawing sections
    # ------------------------------------------------------------------

    def _draw_top_bar(self, surface: pygame.Surface) -> None:
        bar = pygame.Rect(0, 0, surface.get_width(), _TOP_BAR_H)
        pygame.draw.rect(surface, colors.BG_PANEL, bar)
        pygame.draw.line(surface, colors.PANEL_BORDER,
                         (0, _TOP_BAR_H - 1), (surface.get_width(), _TOP_BAR_H - 1))

        draw_relics(surface, self._state.relics, 10, 10, self._fonts)
        draw_turn_counter(surface, self._state.turn, surface.get_width() // 2, 34, self._fonts)

        self._end_turn_rect = draw_end_turn_button(
            surface, _END_TURN_X, _END_TURN_Y, _END_TURN_W, _END_TURN_H,
            self._fonts, hovered=self._end_turn_hovered,
        )

    def _draw_battlefield(self, surface: pygame.Surface) -> None:
        # Separator
        pygame.draw.line(surface, colors.PANEL_BORDER,
                         (0, _HAND_AREA_Y), (surface.get_width(), _HAND_AREA_Y))

        self._enemy_rects = []
        for i, enemy in enumerate(self._state.enemies):
            if i >= len(_ENEMY_POSITIONS):
                break
            ex, ey = _ENEMY_POSITIONS[i]
            targeted = self._state.targeted_enemy_index == i
            rect = draw_enemy(surface, enemy, ex, ey, self._fonts, targeted=targeted)
            self._enemy_rects.append(rect)

        draw_player(surface, self._state.player, _PLAYER_X, _PLAYER_Y, self._fonts)

    def _draw_hand_area(self, surface: pygame.Surface) -> None:
        hand_area = pygame.Rect(0, _HAND_AREA_Y, 1280, 720 - _HAND_AREA_Y)
        pygame.draw.rect(surface, colors.BG_CARD_AREA, hand_area)

        # Mana
        draw_mana(surface, self._state.mana, _MANA_CX, _MANA_CY, self._fonts)

        # Cards in hand
        cards = self._state.hand.cards
        positions = _card_positions(len(cards))
        self._card_rects = []
        for i, (card, (cx, cy)) in enumerate(zip(cards, positions)):
            selected = self._state.selected_card_index == i
            hovered  = self._hovered_card == i
            rect = draw_card(surface, card, cx, cy, self._fonts,
                             selected=selected, hovered=hovered)
            self._card_rects.append(rect)

        # Piles
        draw_pile_widget(surface, "ROBO", self._state.draw_pile.count,
                         _DRAW_X, _DRAW_Y, self._fonts)
        draw_pile_widget(surface, "DESCARTE", self._state.discard_pile.count,
                         _DISCARD_X, _DISCARD_Y, self._fonts)

        # Hand count indicator
        hc_font = self._fonts.get(11)
        hc_surf = hc_font.render(
            f"MANO  {self._state.hand.count}/{self._state.hand.max_size}",
            True, colors.TEXT_SECONDARY,
        )
        surface.blit(hc_surf, (self._fonts.get(11).size("")[0] + _MANA_CX + 48, _MANA_CY + 26))

    # ------------------------------------------------------------------
    # Interaction helpers
    # ------------------------------------------------------------------

    def _update_hover(self, pos: tuple[int, int]) -> None:
        self._hovered_card  = None
        self._hovered_enemy = None
        self._end_turn_hovered = False

        for i, rect in enumerate(self._card_rects):
            # Expand hover rect upward to catch lifted cards
            hover_rect = pygame.Rect(rect.x, rect.y - 20, rect.width, rect.height + 20)
            if hover_rect.collidepoint(pos):
                self._hovered_card = i
                break

        for i, rect in enumerate(self._enemy_rects):
            if rect.collidepoint(pos):
                self._hovered_enemy = i
                break

        if self._end_turn_rect and self._end_turn_rect.collidepoint(pos):
            self._end_turn_hovered = True

    def _handle_click(self, pos: tuple[int, int]) -> None:
        # Click on a card → select / deselect
        for i, rect in enumerate(self._card_rects):
            hover_rect = pygame.Rect(rect.x, rect.y - 20, rect.width, rect.height + 20)
            if hover_rect.collidepoint(pos):
                if self._state.selected_card_index == i:
                    self._state.selected_card_index = None
                else:
                    self._state.selected_card_index = i
                return

        # Click on an enemy with a card selected → target (placeholder)
        for i, rect in enumerate(self._enemy_rects):
            if rect.collidepoint(pos) and self._state.selected_card_index is not None:
                self._state.targeted_enemy_index = i
                # TODO: play card use-case
                self._state.selected_card_index = None
                return

        # Click on end turn (placeholder)
        if self._end_turn_rect and self._end_turn_rect.collidepoint(pos):
            self._state.mana.refill()
            self._state.selected_card_index    = None
            self._state.targeted_enemy_index   = None
            self._state.turn += 1
