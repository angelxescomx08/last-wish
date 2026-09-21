"""Relic inventory: every owned relic, its effect and its activation state."""
import pygame
from src.domain.relic import Relic
from src.infrastructure import colors
from src.infrastructure.fonts import FontRegistry
from src.infrastructure.sprite_loader import SpriteLoader
from src.presentation.ui.card_widget import _wrap
from src.presentation.ui.collection_viewer import CollectionViewer
from src.presentation.ui.tooltip import relic_tooltip


class RelicViewer(CollectionViewer):
    tile_width = 530
    tile_height = 154

    def __init__(self, relics: list[Relic], fonts: FontRegistry) -> None:
        self._sprites = SpriteLoader()
        super().__init__('Tus reliquias', list(relics), fonts, 'reliquias')

    def _draw_item(self, surface, item, rect) -> None:
        box = rect.inflate(-8, -12)
        pygame.draw.rect(surface, colors.BG_DARK, box, border_radius=8)
        pygame.draw.rect(surface, colors.RELIC_BORDER, box, 1, border_radius=8)
        icon = self._sprites.get_relic_sprite(item.name, 64)
        if icon:
            surface.blit(icon, icon.get_rect(center=(box.x + 48, box.centery)))
        name = self._fonts.get(18).render(item.name, True, colors.TEXT_ACCENT)
        surface.blit(name, (box.x + 96, box.y + 12))
        for line_index, line in enumerate(_wrap(item.description, self._fonts.get(14), box.width - 115)):
            text = self._fonts.get(14).render(line, True, colors.TEXT_PRIMARY)
            surface.blit(text, (box.x + 96, box.y + 43 + line_index * 19))
        status = 'Activa' if item.is_active else 'Agotada'
        text = self._fonts.get(12).render(status, True, colors.TEXT_SECONDARY)
        surface.blit(text, (box.x + 96, box.bottom - 24))

    def _tooltip(self, item):
        return relic_tooltip(item)
