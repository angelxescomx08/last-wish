"""Card collection with an accessible, clipped grid and real scrolling."""
from src.domain.card import Card
from src.infrastructure.fonts import FontRegistry
from src.presentation.ui.card_widget import draw_card
from src.presentation.ui.collection_viewer import CollectionViewer
from src.presentation.ui.tooltip import card_tooltip


class PileViewer(CollectionViewer):
    def __init__(self, title: str, cards: list[Card], fonts: FontRegistry) -> None:
        self._cards = list(cards)
        super().__init__(title, self._cards, fonts, 'cartas')

    def _draw_item(self, surface, item, rect) -> None:
        draw_card(surface, item, rect.x + 20, rect.y + 44, self._fonts)

    def _tooltip(self, item):
        return card_tooltip(item)
