"""Pruebas — tuning screen for testing: chroma chances, class pools, economy, cheats.

Rows are generated from ``_rows()``: one percentage row per chroma and kind
(card / relic / pack) plus the fixed knobs of ``Tuning``. Adding a knob means
adding one ``_Row``. Two columns: column 0 "Probabilidades y partida" (plus the
actions), column 1 "Stats del héroe" (extra luck, damage, dexterity, HP, mana,
draw) with a live preview of the drop odds each hero gets with that luck.
Shift + ←/→ or Shift + click adjusts 10 steps at once. Values apply live; the
SceneManager saves them to ``dev_settings.json`` when leaving (``cleared``).
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto

import pygame

from src.domain.character import ALL_CHARACTERS
from src.domain.chroma import CHROMA_DEFS, Chroma
from src.domain.rarity import Rarity, luck_chroma_multiplier, rarity_odds
from src.domain.tuning import CHROMA_KINDS, TUNING, chroma_chance, chroma_key, hero_luck
from src.infrastructure import colors
from src.infrastructure.audio import SoundPlayer
from src.infrastructure.fonts import FontRegistry

_BG = pygame.Color(12, 16, 22)
_ROW_W, _ROW_H, _ROW_GAP = 600, 38, 44
_COL_GAP = 20
_TOP = 150                      # first row; section titles sit above it
_SECTION_TITLES = ("Probabilidades y partida", "Stats del héroe")
_BIG_STEP = 10                  # Shift multiplies a step by this
_ON = pygame.Color(80, 200, 80)
_OFF = pygame.Color(160, 100, 100)
_KIND_LABEL = {"card": "cartas", "relic": "reliquias", "pack": "sobres"}


class _Kind(Enum):
    PERCENT = auto()   # chroma chance 0..100 %
    NUMBER = auto()    # int / float with step
    TOGGLE = auto()
    ACTION = auto()


@dataclass
class _Row:
    label: str
    kind: _Kind
    attr: str = ""                 # Tuning attribute (NUMBER / TOGGLE)
    step: float = 1
    lo: float = 0
    hi: float = 0
    fmt: str = "{}"
    chroma: Chroma | None = None   # PERCENT rows
    chroma_kind: str = ""
    column: int = 0                # 0 = left, 1 = right ("Stats del héroe")


def _rows() -> list[_Row]:
    rows: list[_Row] = []
    for chroma, d in CHROMA_DEFS.items():
        for kind in CHROMA_KINDS:
            adj = d.name_masc if kind == "pack" and d.name_masc else d.name
            rows.append(_Row(f"Probabilidad {_KIND_LABEL[kind]} {adj.lower()}s", _Kind.PERCENT,
                             chroma=chroma, chroma_kind=kind))
    rows += [
        _Row("Cartas de todas las clases", _Kind.TOGGLE, "all_class_cards"),
        _Row("Oro inicial (nueva partida)", _Kind.NUMBER, "starting_gold", 250, 0, 99_750),
        _Row("Multiplicador de oro", _Kind.NUMBER, "gold_multiplier", 0.5, 0, 20, "x{:g}"),
        _Row("Invencible", _Kind.TOGGLE, "invincible"),
        # --- Stats del héroe (right column) ---
        _Row("Suerte extra", _Kind.NUMBER, "extra_luck", 1, 0, 200, "+{}", column=1),
        _Row("Daño extra", _Kind.NUMBER, "extra_damage", 1, 0, 999, "+{}", column=1),
        _Row("Destreza extra", _Kind.NUMBER, "extra_dexterity", 1, 0, 999, "+{}", column=1),
        _Row("HP máximo extra", _Kind.NUMBER, "extra_max_hp", 25, 0, 1000, "+{}", column=1),
        _Row("Maná extra por combate", _Kind.NUMBER, "extra_mana", 1, 0, 10, "+{}", column=1),
        _Row("Cartas extra por turno", _Kind.NUMBER, "extra_draw", 1, 0, 10, "+{}", column=1),
        # --- actions (left column, bottom) ---
        _Row("Restablecer valores", _Kind.ACTION, "reset"),
        _Row("Volver", _Kind.ACTION, "back"),
    ]
    return rows


def luck_preview_lines() -> list[str]:
    """Two Spanish lines per hero: total luck, then the odds it gives (Pruebas overrides included)."""
    lines = []
    for c in ALL_CHARACTERS:
        luck = hero_luck(c.stats.luck)
        odds = rarity_odds(luck)
        boost = luck_chroma_multiplier(luck)
        card_g = min(1.0, chroma_chance(Chroma.GOLDEN, "card") * boost)
        relic_g = min(1.0, chroma_chance(Chroma.GOLDEN, "relic") * boost)
        lines.append(f"{c.name} · suerte {luck}")
        lines.append(
            f"    Legendaria {odds[Rarity.LEGENDARY] * 100:.1f} %  ·  Épica {odds[Rarity.EPIC] * 100:.1f} %"
            f"  ·  Rara {odds[Rarity.RARE] * 100:.1f} %  ·  Dorada: carta {card_g * 100:.0f} %,"
            f" reliquia {relic_g * 100:.0f} %"
        )
    return lines


class DevSettingsScene:
    """Keyboard (↑↓ ←→ Enter Esc) and mouse (−/+ buttons, click rows) tuning screen."""

    _TITLE = "Pruebas"
    _HINT = ("↑ ↓ navegar  |  ← → ajustar (Shift: x10)  |  ENTER activar  |  ESC volver"
             "  ·  se guarda al salir")

    def __init__(self, fonts: FontRegistry, *, sound: SoundPlayer | None = None) -> None:
        self._fonts = fonts
        self._sound = sound if sound is not None else SoundPlayer()
        self._rows = _rows()
        self._selected = 0
        self._row_rects: list[pygame.Rect] = []
        self._buttons: list[tuple[pygame.Rect, pygame.Rect] | None] = []
        self.cleared = False

    # ------------------------------------------------------------------ values

    def value_text(self, row: _Row) -> str:
        if row.kind is _Kind.PERCENT:
            return f"{chroma_chance(row.chroma, row.chroma_kind) * 100:.0f} %"
        if row.kind is _Kind.TOGGLE:
            return "Sí" if getattr(TUNING, row.attr) else "No"
        if row.kind is _Kind.NUMBER:
            return row.fmt.format(getattr(TUNING, row.attr))
        return ""

    def adjust(self, index: int, direction: int) -> None:
        """Move a value ``direction`` steps (±1, or ±10 with Shift), clamped to its range."""
        row = self._rows[index]
        if row.kind is _Kind.PERCENT:
            current = round(chroma_chance(row.chroma, row.chroma_kind) * 100)
            new = max(0, min(100, round((current + 5 * direction) / 5) * 5))
            TUNING.chroma_chances[chroma_key(row.chroma, row.chroma_kind)] = new / 100
        elif row.kind is _Kind.NUMBER:
            value = getattr(TUNING, row.attr) + row.step * direction
            value = max(row.lo, min(row.hi, value))
            setattr(TUNING, row.attr, type(getattr(TUNING, row.attr))(value))
        elif row.kind is _Kind.TOGGLE:
            setattr(TUNING, row.attr, not getattr(TUNING, row.attr))
        else:
            return
        self._sound.play_nav()

    def activate(self, index: int) -> None:
        row = self._rows[index]
        if row.kind is _Kind.TOGGLE:
            self.adjust(index, 1)
        elif row.kind is _Kind.ACTION and row.attr == "reset":
            TUNING.reset()
            self._sound.play_confirm()
        elif row.kind is _Kind.ACTION and row.attr == "back":
            self._leave()

    def _leave(self) -> None:
        if not self.cleared:
            self.cleared = True
            self._sound.play_cancel()

    # ------------------------------------------------------------------ protocol

    def handle_event(self, event: pygame.event.Event) -> None:
        if self.cleared:
            return
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_UP:
                self._select(self._selected - 1)
            elif event.key == pygame.K_DOWN:
                self._select(self._selected + 1)
            elif event.key == pygame.K_LEFT:
                self.adjust(self._selected, -self._step(getattr(event, "mod", 0)))
            elif event.key == pygame.K_RIGHT:
                self.adjust(self._selected, self._step(getattr(event, "mod", 0)))
            elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                self.activate(self._selected)
            elif event.key == pygame.K_ESCAPE:
                self._leave()
        elif event.type == pygame.MOUSEMOTION:
            for i, rect in enumerate(self._row_rects):
                if rect.collidepoint(event.pos) and i != self._selected:
                    self._select(i)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self._click(event.pos)

    def update(self, dt: float) -> None:
        pass

    def draw(self, surface: pygame.Surface) -> None:
        surface.fill(_BG)
        cx = surface.get_width() // 2
        title = self._fonts.get(34).render(self._TITLE, True, colors.TEXT_ACCENT)
        surface.blit(title, title.get_rect(centerx=cx, centery=48))
        sub = self._fonts.get(13).render(
            "Ajustes para probar el juego. El oro inicial y el HP aplican al empezar partida;"
            " los stats, en el próximo combate.",
            True, colors.TEXT_SECONDARY)
        surface.blit(sub, sub.get_rect(centerx=cx, centery=84))
        left_x = cx - _ROW_W - _COL_GAP // 2
        col_x = (left_x, left_x + _ROW_W + _COL_GAP)
        for col, text in enumerate(_SECTION_TITLES):
            t = self._fonts.get(18).render(text, True, colors.TEXT_ACCENT)
            surface.blit(t, t.get_rect(midleft=(col_x[col] + 4, _TOP - 22)))
        self._row_rects, self._buttons = [], []
        slots = [0, 0]
        for i, row in enumerate(self._rows):
            rect = pygame.Rect(col_x[row.column], _TOP + slots[row.column] * _ROW_GAP, _ROW_W, _ROW_H)
            slots[row.column] += 1
            self._row_rects.append(rect)
            selected = i == self._selected
            pygame.draw.rect(surface, (34, 30, 22) if selected else colors.BG_PANEL, rect, border_radius=6)
            pygame.draw.rect(surface, colors.TEXT_ACCENT if selected else colors.PANEL_BORDER, rect, 1,
                             border_radius=6)
            label = self._fonts.get(16).render(row.label, True,
                                               colors.TEXT_ACCENT if selected else colors.TEXT_PRIMARY)
            if row.kind is _Kind.ACTION:
                surface.blit(label, label.get_rect(center=rect.center))
                self._buttons.append(None)
                continue
            surface.blit(label, label.get_rect(midleft=(rect.left + 16, rect.centery)))
            value = self.value_text(row)
            if row.kind is _Kind.TOGGLE:
                color = _ON if getattr(TUNING, row.attr) else _OFF
            else:
                color = colors.TEXT_PRIMARY
            minus = pygame.Rect(rect.right - 212, rect.top + 5, 28, 28)
            plus = pygame.Rect(rect.right - 44, rect.top + 5, 28, 28)
            self._buttons.append((minus, plus))
            for button, sign in ((minus, "-"), (plus, "+")):
                pygame.draw.rect(surface, colors.BG_DARK, button, border_radius=5)
                s = self._fonts.get(18).render(sign, True, colors.TEXT_PRIMARY)
                surface.blit(s, s.get_rect(center=button.center))
            v = self._fonts.get(16).render(value, True, color)
            surface.blit(v, v.get_rect(center=((minus.right + plus.left) // 2, rect.centery)))
        y = _TOP + slots[1] * _ROW_GAP + 8
        head = self._fonts.get(13).render("Con esta suerte (personaje + extra):", True, colors.TEXT_SECONDARY)
        surface.blit(head, (col_x[1] + 4, y))
        for k, line in enumerate(luck_preview_lines()):
            color = colors.TEXT_PRIMARY if k % 2 == 0 else colors.TEXT_SECONDARY
            t = self._fonts.get(11).render(line, True, color)
            surface.blit(t, (col_x[1] + 4, y + 22 + k * 17))
        hint = self._fonts.get(12).render(self._HINT, True, colors.TEXT_SECONDARY)
        surface.blit(hint, hint.get_rect(centerx=cx, centery=696))

    # ------------------------------------------------------------------ input helpers

    @staticmethod
    def _step(mods: int) -> int:
        return _BIG_STEP if mods & pygame.KMOD_SHIFT else 1

    def _select(self, index: int) -> None:
        index %= len(self._rows)
        if index != self._selected:
            self._selected = index
            self._sound.play_nav()

    def _click(self, pos: tuple[int, int]) -> None:
        for i, rect in enumerate(self._row_rects):
            if not rect.collidepoint(pos):
                continue
            self._selected = i
            buttons = self._buttons[i] if i < len(self._buttons) else None
            if buttons is not None:
                minus, plus = buttons
                try:
                    step = self._step(pygame.key.get_mods())
                except pygame.error:
                    step = 1
                if minus.collidepoint(pos):
                    self.adjust(i, -step)
                    return
                if plus.collidepoint(pos):
                    self.adjust(i, step)
                    return
            self.activate(i)
            return
