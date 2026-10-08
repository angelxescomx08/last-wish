"""Card collection with an accessible, clipped grid and real scrolling."""
from src.application.card_preview import NO_BONUS, CardBonus
from src.domain.card import Card
from src.infrastructure.fonts import FontRegistry
from src.presentation.ui.card_widget import draw_card
from src.presentation.ui.collection_viewer import CollectionViewer
from src.presentation.ui.tooltip import card_tooltip


class PileViewer(CollectionViewer):
    def __init__(self, title: str, cards: list[Card], fonts: FontRegistry,
                 bonus: CardBonus = NO_BONUS) -> None:
        self._cards = list(cards)
        self._bonus = bonus          # the hero's stats, so numbers match the hand
        super().__init__(title, self._cards, fonts, 'cartas')

    def _draw_item(self, surface, item, rect) -> None:
        dmg, blk = self._bonus.for_card(item)
        draw_card(surface, item, rect.x + 20, rect.y + 44, self._fonts, bonus_damage=dmg, bonus_block=blk)

    def _tooltip(self, item):
        dmg, blk = self._bonus.for_card(item)
        return card_tooltip(item, bonus_damage=dmg, bonus_block=blk)
