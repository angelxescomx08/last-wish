"""Enemy action banners: "Caballero Hueco usa Danza de Espadas — 2 golpes · pierdes 3 de vida".

During the enemy turn a lot happens at once (several enemies, multi-hits,
debuffs, junk cards). Card games name every enemy action on screen so the
player can follow it (Slay the Spire shows the move name, Hearthstone the
played card). One banner per acting enemy, stacked under the top bar; each one
fades in, stays ~2 s and fades out.

``describe_action(name, intent, action)`` builds the texts (pure, testable);
``ActionBanners`` keeps and draws them.
"""
from __future__ import annotations

from dataclasses import dataclass

import pygame

from src.domain.combat import EnemyAction
from src.domain.entities import Intent, IntentType
from src.domain.status_cards import make_status_card
from src.infrastructure.fonts import FontRegistry
from src.infrastructure.ui_icons import ui_icon
from src.presentation.ui import rich_text
from src.presentation.ui.tooltip import intent_icon

_PILE = {"draw": "tu pila de robo", "discard": "tu descarte", "hand": "tu mano"}
_GENERIC = {
    IntentType.ATTACK: "ataca",
    IntentType.BLOCK: "se defiende",
    IntentType.BUFF: "se fortalece",
    IntentType.DEBUFF: "te debilita",
    IntentType.UNKNOWN: "actúa",
}

FADE_IN = 0.15
HOLD = 2.1
FADE_OUT = 0.35


def _plural(word: str, n: int) -> str:
    return word if n == 1 or word.endswith("s") else word + "s"


def describe_action(enemy_name: str, intent: Intent, action: EnemyAction) -> tuple[str, str, str]:
    """(icon name, title, detail) for what one enemy just did."""
    title = f"{enemy_name} usa {action.move or intent.move}" if (action.move or intent.move) \
        else f"{enemy_name} {_GENERIC.get(intent.intent_type, 'actúa')}"
    parts: list[str] = []
    if intent.intent_type == IntentType.ATTACK and action.hits:
        n, lost = len(action.hits), sum(action.hits)
        hits = f"{n} {'golpe' if n == 1 else 'golpes'}"
        parts.append(f"{hits} · ¡todo bloqueado!" if lost == 0 else f"{hits} · pierdes {lost} de vida")
    elif intent.intent_type == IntentType.BLOCK and intent.value > 0:
        parts.append(f"gana {intent.value} de escudo")
    if intent.block > 0:
        parts.append(f"gana {intent.block} de escudo")
    for name, n in intent.buffs:
        parts.append(f"gana {n} de {name}")
    for name, n in action.debuffs:
        parts.append(f"te aplica {n} de {name}")
    for card_id, n, pile in action.cards:
        card = make_status_card(card_id)
        label = _plural(card.name if card else card_id, n)
        parts.append(f"mete {n} {label} en {_PILE.get(pile, pile)}")
    if intent.ally_block > 0:
        parts.append(f"da {intent.ally_block} de escudo a su compañero")
    for name, n in intent.ally_buffs:
        parts.append(f"da {n} de {name} a sus aliados")
    if action.healed > 0:
        parts.append(f"recupera {action.healed} de vida")
    if action.exploded:
        parts.append("¡explota y muere!")
    return intent_icon(intent), title, " · ".join(parts)


@dataclass
class _Banner:
    icon: str
    title: str
    detail: str
    delay: float
    age: float = 0.0

    @property
    def alpha(self) -> float:
        t = self.age - self.delay
        if t < 0:
            return 0.0
        if t < FADE_IN:
            return t / FADE_IN
        if t < FADE_IN + HOLD:
            return 1.0
        return max(0.0, 1.0 - (t - FADE_IN - HOLD) / FADE_OUT)

    @property
    def done(self) -> bool:
        return self.age - self.delay >= FADE_IN + HOLD + FADE_OUT


class ActionBanners:
    WIDTH = 560

    def __init__(self, top: int = 372) -> None:
        self.top = top
        self._items: list[_Banner] = []

    @property
    def active(self) -> list[_Banner]:
        return list(self._items)

    def clear(self) -> None:
        self._items.clear()

    def add(self, icon: str, title: str, detail: str = "", delay: float = 0.0) -> None:
        self._items.append(_Banner(icon, title, detail, delay))

    def update(self, dt: float) -> None:
        for b in self._items:
            b.age += dt
        self._items = [b for b in self._items if not b.done]

    def draw(self, surface: pygame.Surface, fonts: FontRegistry) -> None:
        y = self.top
        cx = surface.get_width() // 2
        title_font, detail_font = fonts.get(16), fonts.get(13)
        for b in self._items:
            a = b.alpha
            if a <= 0:
                continue
            icon = ui_icon(b.icon, 2)
            title = title_font.render(b.title, True, (246, 220, 150))
            detail = rich_text.render_line(b.detail, detail_font, (230, 224, 212), shadow=True) if b.detail else None
            text_w = max(title.get_width(), detail.get_width() if detail else 0)
            w = min(self.WIDTH, max(260, text_w + (icon.get_width() if icon else 0) + 40))
            h = 50 if detail else 36
            panel = pygame.Surface((w, h), pygame.SRCALPHA)
            pygame.draw.rect(panel, (12, 8, 20, 215), panel.get_rect(), border_radius=6)
            pygame.draw.rect(panel, (150, 110, 70, 255), panel.get_rect(), 1, border_radius=6)
            x = 12
            if icon is not None:
                panel.blit(icon, icon.get_rect(midleft=(x - 2, h // 2)))
                x += icon.get_width() + 6
            panel.blit(title, (x, 5 if detail else (h - title.get_height()) // 2))
            if detail is not None:
                panel.blit(detail, (x, h - detail.get_height() - 5))
            slide = int((1 - min(1.0, a * 1.2)) * -10)
            panel.set_alpha(int(255 * a))
            surface.blit(panel, panel.get_rect(midtop=(cx, y + slide)))
            y += h + 6
