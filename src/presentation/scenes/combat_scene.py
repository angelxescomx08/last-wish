from __future__ import annotations

import pygame

from src.application.end_turn import end_player_turn
from src.application.play_card import play_card
from src.domain.combat import CombatState
from src.infrastructure import colors
from src.infrastructure.fonts import FontRegistry
from src.presentation.ui.card_widget import CARD_H, CARD_W, draw_card
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
from src.presentation.ui.pile_viewer import PileViewer

# ---------------------------------------------------------------------------
# Layout
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
    Delegates game-rule mutations to use-case functions in src/application/.
    """

    def __init__(self, state: CombatState, fonts: FontRegistry) -> None:
        self._state  = state
        self._fonts  = fonts

        # Hit-test rectangles (rebuilt every draw call)
        self._card_rects:     list[pygame.Rect]  = []
        self._enemy_rects:    list[pygame.Rect]  = []
        self._end_turn_rect:  pygame.Rect | None = None
        self._draw_pile_rect: pygame.Rect | None = None
        self._disc_pile_rect: pygame.Rect | None = None

        # Hover state
        self._hovered_card:      int | None = None
        self._hovered_enemy:     int | None = None
        self._end_turn_hovered:  bool = False

        # Overlay (pile viewer)
        self._overlay: PileViewer | None = None

    # ------------------------------------------------------------------
    # Protocol
    # ------------------------------------------------------------------

    def handle_event(self, event: pygame.event.Event) -> None:
        # Overlay consumes all events while open
        if self._overlay is not None:
            self._overlay.handle_event(event)
            return

        if event.type == pygame.MOUSEMOTION:
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

    # ------------------------------------------------------------------
    # Derived state
    # ------------------------------------------------------------------

    @property
    def _in_targeting_mode(self) -> bool:
        idx = self._state.selected_card_index
        if idx is None or idx >= self._state.hand.count:
            return False
        return self._state.hand.cards[idx].total_damage() > 0

    # ------------------------------------------------------------------
    # Draw sections
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

        draw_player(surface, self._state.player, _PLAYER_X, _PLAYER_Y, self._fonts)

        # Active powers strip (bottom of battlefield, above hand area)
        if self._state.active_powers:
            self._draw_active_powers(surface)

    def _draw_active_powers(self, surface: pygame.Surface) -> None:
        label_font = self._fonts.get(10)
        label_surf = label_font.render("PODERES ACTIVOS", True, colors.TEXT_SECONDARY)
        surface.blit(label_surf, (560, _HAND_AREA_Y - 80))
        for i, card in enumerate(self._state.active_powers):
            cx = 560 + i * (CARD_W + 6)
            draw_card(surface, card, cx, _HAND_AREA_Y - 78, self._fonts)

    def _draw_hand_area(self, surface: pygame.Surface) -> None:
        hand_bg = pygame.Rect(0, _HAND_AREA_Y, 1280, 720 - _HAND_AREA_Y)
        pygame.draw.rect(surface, colors.BG_CARD_AREA, hand_bg)

        draw_mana(surface, self._state.mana, _MANA_CX, _MANA_CY, self._fonts)

        # Hand cards
        cards     = self._state.hand.cards
        positions = _card_positions(len(cards))
        self._card_rects = []
        for i, (card, (cx, cy)) in enumerate(zip(cards, positions)):
            affordable = self._state.mana.can_afford(card.cost)
            rect = draw_card(
                surface, card, cx, cy, self._fonts,
                selected   = self._state.selected_card_index == i,
                hovered    = self._hovered_card == i,
                affordable = affordable,
            )
            self._card_rects.append(rect)

        # Piles
        self._draw_pile_rect = draw_pile_widget(
            surface, "ROBO", self._state.draw_pile.count,
            _DRAW_X, _DRAW_Y, self._fonts,
        )
        self._disc_pile_rect = draw_pile_widget(
            surface, "DESCARTE", self._state.discard_pile.count,
            _DISCARD_X, _DISCARD_Y, self._fonts,
        )

        # Hand count
        hc_surf = self._fonts.get(11).render(
            f"MANO  {self._state.hand.count}/{self._state.hand.max_size}",
            True, colors.TEXT_SECONDARY,
        )
        surface.blit(hc_surf, (_MANA_CX + 52, _MANA_CY + 26))

    def _draw_targeting_hint(self, surface: pygame.Surface) -> None:
        msg = self._fonts.get(15).render(
            "Selecciona un enemigo objetivo  ·  ESC para cancelar",
            True, _TARGETING_COLOR,
        )
        surface.blit(msg, msg.get_rect(centerx=640, centery=_HAND_AREA_Y - 16))

    # ------------------------------------------------------------------
    # Interaction
    # ------------------------------------------------------------------

    def _update_hover(self, pos: tuple[int, int]) -> None:
        self._hovered_card     = None
        self._hovered_enemy    = None
        self._end_turn_hovered = False

        for i, rect in enumerate(self._card_rects):
            if _card_hover_rect(rect).collidepoint(pos):
                self._hovered_card = i
                break

        if self._in_targeting_mode:
            for i, rect in enumerate(self._enemy_rects):
                if rect.collidepoint(pos):
                    self._hovered_enemy = i
                    break

        if self._end_turn_rect and self._end_turn_rect.collidepoint(pos):
            self._end_turn_hovered = True

    def _handle_click(self, pos: tuple[int, int]) -> None:
        # Priority 1: pile viewers
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

        # Priority 2: end turn
        if self._end_turn_rect and self._end_turn_rect.collidepoint(pos):
            end_player_turn(self._state)
            return

        # Priority 3: targeting mode — click on enemy plays the selected card
        if self._in_targeting_mode:
            for i, rect in enumerate(self._enemy_rects):
                if rect.collidepoint(pos):
                    if i < len(self._state.enemies) and self._state.enemies[i].is_alive:
                        play_card(self._state, self._state.selected_card_index, i)  # type: ignore[arg-type]
                    return
            # Click on a different card switches selection
            for i, rect in enumerate(self._card_rects):
                if _card_hover_rect(rect).collidepoint(pos):
                    card = self._state.hand.cards[i]
                    self._state.selected_card_index = i if card.total_damage() > 0 else None
                    if card.total_damage() == 0 and self._state.mana.can_afford(card.cost):
                        play_card(self._state, i, None)
                    return
            # Click on empty space cancels targeting
            self._state.selected_card_index = None
            return

        # Priority 4: normal card click
        for i, rect in enumerate(self._card_rects):
            if _card_hover_rect(rect).collidepoint(pos):
                card = self._state.hand.cards[i]
                needs_target = card.total_damage() > 0
                can_afford   = self._state.mana.can_afford(card.cost)

                if needs_target:
                    # Enter targeting mode (even if no mana — visual feedback)
                    self._state.selected_card_index = (
                        None if self._state.selected_card_index == i else i
                    )
                elif can_afford:
                    # Self-targeted cards play immediately
                    play_card(self._state, i, None)
                return

        # Click on empty space clears selection
        self._state.selected_card_index = None


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _card_hover_rect(rect: pygame.Rect) -> pygame.Rect:
    """Expand card rect upward to catch the lifted hover/selected state."""
    return pygame.Rect(rect.x, rect.y - 22, rect.width, rect.height + 22)
