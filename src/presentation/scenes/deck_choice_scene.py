"""Deck choice asked by a relic when you get it (``Run.pending_choices``).

* ``("remove", n)`` — Tijeras del Sastre: pick up to ``n`` cards to remove from the deck
  (the deck never drops below ``purge.MIN_DECK``).
* ``("innate", n)`` — Cartas Marcadas: pick ``n`` cards that start every combat in your hand.

The deck is shown in the usual grid (``CollectionViewer``). A click toggles a card (gold rim
and a check mark); "Confirmar" applies the choice. Escape closes nothing here: the choice was
part of the relic, so the scene stays until it is confirmed (a deck too small to choose from
confirms empty). Pure rules: ``application.deck_choice``.

Public flag consumed by SceneManager: ``cleared`` — the choice was applied.
"""
from __future__ import annotations

import pygame

from src.application.card_preview import run_card_bonus
from src.application.deck_choice import apply_choice, choice_limit
from src.domain.card import Card
from src.domain.run import Run
from src.infrastructure import colors
from src.infrastructure.audio import SoundPlayer
from src.infrastructure.fonts import FontRegistry
from src.presentation.ui.card_widget import CARD_H, CARD_W, draw_card
from src.presentation.ui.collection_viewer import CollectionViewer
from src.presentation.ui.tooltip import card_tooltip

_GOLD = pygame.Color(235, 195, 70)
_TITLES = {"remove": "Tijeras del Sastre", "innate": "Cartas Marcadas"}
_VERBS = {"remove": "eliminar", "innate": "marcar"}


class _ChoiceGrid(CollectionViewer):
    close_label = 'Confirmar'
    close_on_outside_click = False

    def __init__(self, scene: "DeckChoiceScene") -> None:
        self._scene = scene
        super().__init__(_TITLES.get(scene.kind, "Elige cartas"), scene.run.deck, scene.fonts, 'cartas')
        self.clicked: int | None = None

    @property
    def hint_text(self) -> str:  # type: ignore[override]
        sc = self._scene
        return (f'Elige hasta {sc.limit} carta{"s" if sc.limit != 1 else ""} para {_VERBS.get(sc.kind, "elegir")}'
                '  ·  Clic para marcar o desmarcar  ·  Rueda / ↑ ↓')

    @property
    def footer_text(self) -> str:  # type: ignore[override]
        sc = self._scene
        if sc.kind == "remove":
            return (f'Elegidas: {len(sc.selected)}/{sc.limit}  ·  Salen de tu mazo para siempre'
                    '  ·  Pulsa Confirmar')
        return f'Elegidas: {len(sc.selected)}/{sc.limit}  ·  Empezarás cada combate con ellas en la mano'

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            return                                  # the choice cannot be skipped by Escape
        if (event.type == pygame.MOUSEBUTTONDOWN and event.button == 1
                and self._viewport.collidepoint(event.pos)):
            for i, rect in self._item_rects.items():
                if rect.collidepoint(event.pos):
                    self.clicked = i
                    return
        super().handle_event(event)

    def _draw_item(self, surface, item: Card, rect) -> None:
        index = next((i for i, c in enumerate(self._items) if c is item), -1)
        chosen = index in self._scene.selected
        label = self._fonts.get(15).render('✓ Elegida' if chosen else ' ', True, _GOLD)
        surface.blit(label, label.get_rect(centerx=rect.centerx, centery=rect.y + 24))
        dmg, blk = run_card_bonus(self._scene.run).for_card(item)
        draw_card(surface, item, rect.x + 20, rect.y + 44, self._fonts, bonus_damage=dmg,
                  bonus_block=blk)
        if chosen:
            pygame.draw.rect(surface, _GOLD, pygame.Rect(rect.x + 16, rect.y + 40, CARD_W + 8, CARD_H + 8),
                             3, border_radius=10)

    def _tooltip(self, item):
        dmg, blk = run_card_bonus(self._scene.run).for_card(item)
        return card_tooltip(item, bonus_damage=dmg, bonus_block=blk)


class DeckChoiceScene:
    """Choose cards of the deck for a relic (remove or mark)."""

    pause_button_rect = pygame.Rect(78, 652, 64, 36)
    gold_hud_pos = ("bottomright", (1268, 708))

    def __init__(self, run: Run, kind: str, count: int, fonts: FontRegistry, *,
                 sound: SoundPlayer | None = None) -> None:
        self.run = run
        self.kind = kind
        self.fonts = fonts
        self._sound = sound if sound is not None else SoundPlayer()
        self.limit = choice_limit(run, kind, count)
        self.selected: list[int] = []
        self._grid = _ChoiceGrid(self)
        self.cleared = False

    def toggle(self, index: int) -> None:
        if not 0 <= index < len(self.run.deck):
            return
        if index in self.selected:
            self.selected.remove(index)
            self._sound.play_cancel()
        elif len(self.selected) < self.limit:
            self.selected.append(index)
            self._sound.play_confirm()
        else:
            self._sound.play_error()

    def confirm(self) -> None:
        apply_choice(self.run, self.kind, self.selected)
        self.cleared = True
        self._sound.play_purchase()

    def handle_event(self, event: pygame.event.Event) -> None:
        if self.cleared:
            return
        if event.type == pygame.KEYDOWN and event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            self.confirm()
            return
        self._grid.handle_event(event)
        if self._grid.clicked is not None:
            index, self._grid.clicked = self._grid.clicked, None
            self.toggle(index)
        if self._grid.dismissed:                    # the "Confirmar" button
            self._grid.dismissed = False
            self.confirm()

    def update(self, dt: float) -> None:
        pass

    def draw(self, surface: pygame.Surface) -> None:
        surface.fill(colors.BG_DARK)
        self._grid.draw(surface)
