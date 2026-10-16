"""Combat history strip (Hearthstone style) on the left edge of the battlefield.

One tile per entry of ``application.combat_log.CombatLog``, newest on top, with a thin
"T3" separator between turns. Tile colour says who acted (gold = you, red = an enemy,
blue = an effect), the icon says what (card type / element, intent, frozen…), the
number in the corner what it cost (damage dealt, block gained, HP lost).

Scrolling: mouse wheel over the strip, dragging it (touch), or the arrows at its ends.
Hover a tile (or tap it on a phone: it stays pinned until tapped again) for the detail;
a card you played is shown next to the detail.

Performance (phones): each tile is rendered once and cached; a frame costs one blit of
the strip background plus one blit per *visible* tile (≈ 9), clipped to the strip. The
smooth scroll only moves the blits. Fresh tiles glow for ``FRESH`` s.
"""
from __future__ import annotations

import pygame

from src.application.combat_log import CombatLog, LogEntry
from src.infrastructure.fonts import FontRegistry
from src.infrastructure.ui_icons import ui_icon
from src.presentation.ui.pixel_ui import outlined
from src.presentation.ui.tooltip import TooltipContent

RECT = pygame.Rect(6, 74, 48, 384)
TILE = 40
STEP = 44
SEP = 18                 # turn separator height
ARROW = 14               # arrow band at each end when there is more to see
FRESH = 1.2
DRAG_START = 6           # px before a press becomes a drag (otherwise it is a tap)

_STYLE = {   # kind → (fill, rim)
    "hero": ((36, 46, 74), (226, 172, 58)),
    "enemy": ((70, 24, 30), (220, 66, 58)),
    "effect": ((26, 40, 56), (130, 190, 240)),
}
_VALUE_INK = {"damage": (255, 150, 110), "block": (120, 190, 255), "loss": (255, 96, 86)}


class CombatLogStrip:
    def __init__(self, rect: pygame.Rect = RECT) -> None:
        self.rect = pygame.Rect(rect)
        self.offset = 0.0           # px scrolled down from the newest entry (drawn offset)
        self.target = 0.0
        self.pinned: LogEntry | None = None
        self._layout: list[tuple[LogEntry, int, int]] = []    # (entry, y from top, height)
        self._content_h = 0
        self._version = -1
        self._tiles: dict[int, pygame.Surface] = {}
        self._fresh: dict[int, float] = {}
        self._press: tuple[int, float] | None = None          # (y, offset) at press
        self._dragging = False
        self._bg: pygame.Surface | None = None
        self.mouse = (0, 0)

    # ---------------------------------------------------------------- data

    def sync(self, log: CombatLog) -> None:
        """Re-lay out when the log changed (keeps the view still if you scrolled down)."""
        if log.version == self._version:
            return
        old_h = self._content_h
        first = self._version < 0
        self._version = log.version
        y, layout = 0, []
        for entry in reversed(log.entries):                   # newest first
            h = SEP if entry.kind == "turn" else STEP
            layout.append((entry, y, h))
            y += h
        self._layout, self._content_h = layout, y
        alive = {id(e) for e, _, _ in layout}
        self._tiles = {k: v for k, v in self._tiles.items() if k in alive}
        for e, _, _ in layout:
            if id(e) not in self._fresh and not first:
                self._fresh[id(e)] = 0.0
        self._fresh = {k: v for k, v in self._fresh.items() if k in alive}
        if self.target > 0 and not first:                    # reading older entries: stay there
            grow = self._content_h - old_h
            self.target += grow
            self.offset += grow
        self.target = self._clamp(self.target)
        self.offset = self._clamp(self.offset)
        if self.pinned is not None and id(self.pinned) not in alive:
            self.pinned = None

    @property
    def max_offset(self) -> int:
        return max(0, self._content_h - self.rect.h)

    def _clamp(self, v: float) -> float:
        return max(0.0, min(float(self.max_offset), v))

    def scroll(self, px: float) -> None:
        self.target = self._clamp(self.target + px)

    def update(self, dt: float) -> None:
        dt = max(0.0, min(dt, 0.1))
        self.offset += (self.target - self.offset) * min(1.0, dt * 14)
        if abs(self.target - self.offset) < 0.5:
            self.offset = self.target
        for k in list(self._fresh):
            self._fresh[k] += dt
            if self._fresh[k] > FRESH:
                del self._fresh[k]

    # ---------------------------------------------------------------- input

    def _up_arrow(self) -> pygame.Rect:
        return pygame.Rect(self.rect.x, self.rect.y, self.rect.w, ARROW)

    def _down_arrow(self) -> pygame.Rect:
        return pygame.Rect(self.rect.x, self.rect.bottom - ARROW, self.rect.w, ARROW)

    def handle_event(self, event: pygame.event.Event) -> bool:
        """True when the strip used the event (the scene then ignores it)."""
        if event.type == pygame.MOUSEMOTION:
            self.mouse = event.pos
            if self._press is not None:
                y0, off0 = self._press
                if self._dragging or abs(event.pos[1] - y0) >= DRAG_START:
                    self._dragging = True
                    self.target = self.offset = self._clamp(off0 - (event.pos[1] - y0))
                return True
            return False
        if event.type == pygame.MOUSEWHEEL:
            if self.rect.collidepoint(self.mouse):
                self.scroll(-event.y * STEP)
                return True
            return False
        if event.type == pygame.MOUSEBUTTONDOWN and event.button in (4, 5):   # old wheel events
            if self.rect.collidepoint(event.pos):
                self.scroll(STEP if event.button == 5 else -STEP)
                return True
            return False
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self.mouse = event.pos
            if self.rect.collidepoint(event.pos):
                self._press, self._dragging = (event.pos[1], self.offset), False
                return True
            self.pinned = None
            return False
        if event.type == pygame.MOUSEBUTTONUP and event.button == 1 and self._press is not None:
            dragged, self._press, self._dragging = self._dragging, None, False
            if not dragged:
                self._tap(event.pos)
            return True
        return False

    def _tap(self, pos: tuple[int, int]) -> None:
        if self.offset > 0 and self._up_arrow().collidepoint(pos):
            self.scroll(-2 * STEP)
            return
        if self.offset < self.max_offset and self._down_arrow().collidepoint(pos):
            self.scroll(2 * STEP)
            return
        entry = self.entry_at(pos)
        self.pinned = None if entry is None or entry is self.pinned else entry

    # ---------------------------------------------------------------- queries

    def tile_rect(self, entry: LogEntry) -> pygame.Rect | None:
        for e, y, h in self._layout:
            if e is entry:
                return pygame.Rect(self.rect.x + (self.rect.w - TILE) // 2,
                                   self.rect.y + y - round(self.offset), TILE, min(TILE, h))
        return None

    def entry_at(self, pos: tuple[int, int]) -> LogEntry | None:
        if not self.rect.collidepoint(pos):
            return None
        y = pos[1] - self.rect.y + self.offset
        for e, ey, h in self._layout:
            if ey <= y < ey + h and e.kind != "turn":
                return e
        return None

    def shown_entry(self) -> LogEntry | None:
        """The entry whose detail is shown: pinned (tap) or under the pointer."""
        if self._dragging:
            return None
        return self.pinned or self.entry_at(self.mouse)

    def visible(self) -> list[tuple[LogEntry, int, int]]:
        top = self.offset
        return [(e, y, h) for e, y, h in self._layout if y + h > top and y < top + self.rect.h]

    # ---------------------------------------------------------------- drawing

    def _background(self) -> pygame.Surface:
        if self._bg is None or self._bg.get_size() != self.rect.size:
            bg = pygame.Surface(self.rect.size, pygame.SRCALPHA)
            pygame.draw.rect(bg, (10, 8, 14, 150), bg.get_rect(), border_radius=8)
            pygame.draw.rect(bg, (90, 80, 110, 160), bg.get_rect(), 1, border_radius=8)
            self._bg = bg
        return self._bg

    def _tile(self, entry: LogEntry, fonts: FontRegistry) -> pygame.Surface:
        surf = self._tiles.get(id(entry))
        if surf is not None:
            return surf
        if entry.kind == "turn":
            surf = pygame.Surface((self.rect.w, SEP), pygame.SRCALPHA)
            label = outlined(fonts.get(8), f"T{entry.turn}", (246, 204, 92))
            y = SEP // 2
            pygame.draw.line(surf, (120, 100, 70), (2, y), (self.rect.w - 3, y), 1)
            surf.blit(label, label.get_rect(center=(self.rect.w // 2, y)))
        else:
            fill, rim = _STYLE.get(entry.kind, _STYLE["effect"])
            surf = pygame.Surface((TILE, TILE), pygame.SRCALPHA)
            pygame.draw.rect(surf, fill, surf.get_rect(), border_radius=6)
            pygame.draw.rect(surf, rim, surf.get_rect(), 2, border_radius=6)
            icon = ui_icon(entry.icon, 2)
            if icon is not None:
                surf.blit(icon, icon.get_rect(center=(TILE // 2, TILE // 2 - 2)))
            if entry.value > 0:
                text = ("−" if entry.value_kind == "loss" else "") + str(entry.value)
                num = outlined(fonts.get(8), text, _VALUE_INK.get(entry.value_kind, (236, 228, 214)))
                surf.blit(num, num.get_rect(bottomright=(TILE - 1, TILE)))
        self._tiles[id(entry)] = surf
        return surf

    def draw(self, surface: pygame.Surface, fonts: FontRegistry, t: float = 0.0) -> None:
        if not self._layout:
            return
        surface.blit(self._background(), self.rect.topleft)
        clip = surface.get_clip()
        surface.set_clip(self.rect.inflate(-2, -2).clip(clip) if clip else self.rect.inflate(-2, -2))
        shown = self.shown_entry()
        for entry, y, h in self.visible():
            tile = self._tile(entry, fonts)
            x = self.rect.x if entry.kind == "turn" else self.rect.x + (self.rect.w - TILE) // 2
            ty = self.rect.y + y - round(self.offset)
            surface.blit(tile, (x, ty))
            age = self._fresh.get(id(entry))
            if (age is not None or entry is shown) and entry.kind != "turn":
                k = 1.0 if entry is shown else max(0.0, 1 - age / FRESH)
                if k > 0:
                    col = (255, 236, 160) if entry is shown else (255, 214, 90)
                    pygame.draw.rect(surface, col, (x - 1, ty - 1, TILE + 2, TILE + 2), 2 if k > 0.4 else 1,
                                     border_radius=7)
        surface.set_clip(clip)
        for arrow, show, up in ((self._up_arrow(), self.offset > 0.5, True),
                                (self._down_arrow(), self.offset < self.max_offset - 0.5, False)):
            if show:
                cx, cy = arrow.centerx, arrow.centery
                pts = [(cx - 7, cy + 3), (cx + 7, cy + 3), (cx, cy - 4)] if up else \
                      [(cx - 7, cy - 3), (cx + 7, cy - 3), (cx, cy + 4)]
                pygame.draw.rect(surface, (14, 10, 18), arrow, border_radius=5)
                pygame.draw.polygon(surface, (246, 204, 92), pts)


def entry_tooltip(entry: LogEntry) -> TooltipContent:
    who = {"hero": "Tú", "enemy": "Enemigo", "effect": "Efecto"}.get(entry.kind, "")
    accent = _STYLE.get(entry.kind, _STYLE["effect"])[1]
    return TooltipContent(title=entry.title, lines=list(entry.lines), icon=entry.icon,
                          subtitle=f"Turno {entry.turn}  ·  {who}", accent=accent)


# ---------------------------------------------------------------------------
# Detail panel: who acted → on whom (Hearthstone history style)
# ---------------------------------------------------------------------------

PORTRAIT = 64            # portrait box (px)
_TARGET_W = 84
_MAX_TARGETS = 4
_PANEL_PAD = 10
_TEXT_W = 300
_detail_cache: dict = {}


def _portrait_box(name: str, image, rim, fonts: FontRegistry, *, hp=0, block=0, healed=0, died=False,
                  statuses=(), reactions=(), aimed=False, blocked=False) -> pygame.Surface:
    """A character in the detail: portrait in a frame, name, what happened to it."""
    from src.presentation.ui.glossary import REACTION_ICON, status_icon
    from src.domain.elements import Reaction
    from src.presentation.ui.text_fit import fit
    box = pygame.Surface((_TARGET_W, PORTRAIT + 40), pygame.SRCALPHA)
    frame = pygame.Rect((_TARGET_W - PORTRAIT) // 2, 4, PORTRAIT, PORTRAIT)
    pygame.draw.rect(box, (20, 16, 26), frame, border_radius=8)
    if image is None:                                   # no sprite: a generic picture
        image = ui_icon("helmet" if rim == (226, 172, 58) else "unknown", 3)
    if image is not None:
        iw, ih = image.get_size()
        k = min((PORTRAIT - 6) / max(1, iw), (PORTRAIT - 6) / max(1, ih))
        pic = pygame.transform.scale(image, (max(1, int(iw * k)), max(1, int(ih * k))))
        if died:
            pic = pic.copy()
            pic.fill((90, 90, 90, 255), special_flags=pygame.BLEND_RGBA_MULT)
        box.blit(pic, pic.get_rect(center=frame.center))
    pygame.draw.rect(box, (255, 236, 160) if aimed else rim, frame, 3 if aimed else 2, border_radius=8)
    if died:
        skull = ui_icon("lethal", 2)
        if skull is not None:
            box.blit(skull, skull.get_rect(center=frame.center))
    # result splash in the top-right corner: damage (red), block (blue), heal (green)
    for value, ink, prefix, icon in ((hp, (255, 90, 70), "−", "damage"), (block, (110, 180, 255), "+", "block"),
                                     (healed, (120, 236, 120), "+", "heal")):
        if value > 0:
            num = outlined(fonts.get(16), f"{prefix}{value}", ink)
            r = max(num.get_width(), num.get_height()) // 2 + 5
            c = (frame.right - 4, frame.top + 10)
            pygame.draw.circle(box, (24, 12, 16), c, r)
            pygame.draw.circle(box, ink, c, r, 2)
            box.blit(num, num.get_rect(center=c))
            break
    else:
        if blocked:                                     # hit, but the block stopped it all
            shield = ui_icon("block", 2)
            if shield is not None:
                box.blit(shield, shield.get_rect(center=(frame.right - 4, frame.top + 10)))
    for k, name_r in enumerate(reactions[:2]):              # reactions it suffered (top-left)
        try:
            icon = ui_icon(REACTION_ICON[Reaction(name_r)], 2)
        except ValueError:
            icon = None
        if icon is not None:
            box.blit(icon, (frame.x - 4, frame.y - 2 + k * 24))
    label = outlined(fonts.get(8), fit(fonts.get(8), name, _TARGET_W - 4), (236, 228, 214))
    box.blit(label, label.get_rect(center=(_TARGET_W // 2, frame.bottom + 9)))
    x = 4
    for sname, n in statuses[:4]:                         # statuses put on it
        icon = ui_icon(status_icon(sname), 1)
        if icon is not None:
            box.blit(icon, (x, frame.bottom + 18))
            stack = outlined(fonts.get(8), f"+{n}", (236, 228, 214))
            box.blit(stack, (x + 15, frame.bottom + 19))
            x += 15 + stack.get_width() + 3
    return box


def render_entry_detail(entry: LogEntry, fonts: FontRegistry, portrait, card_face=None) -> pygame.Surface:
    """The detail panel of one entry (cached): source → arrow → targets, then its sentences.

    ``portrait(key)`` returns a Surface for ``HERO`` or an enemy name (or None);
    ``card_face(card)`` the face of the card you played.
    """
    key = id(entry)
    cached = _detail_cache.get(key)
    if cached is not None and cached[0] is entry:
        return cached[1]
    from src.application.combat_log import HERO
    from src.presentation.ui import rich_text
    blocks: list[pygame.Surface] = []
    hero_rim, enemy_rim = (226, 172, 58), (220, 66, 58)
    if entry.card is not None and card_face is not None:
        blocks.append(card_face(entry.card))
    elif entry.source:
        rim = hero_rim if entry.source == HERO else enemy_rim
        blocks.append(_portrait_box(entry.source_name or entry.source, portrait(entry.source), rim, fonts))
    arrow = None
    if entry.targets and blocks:
        arrow = ui_icon(entry.verb or "attack_2", 2)
    targets = [
        _portrait_box(t.name, portrait(t.portrait), hero_rim if t.portrait == HERO else enemy_rim, fonts,
                      hp=t.hp, block=t.block, healed=t.healed, died=t.died, statuses=t.statuses,
                      reactions=t.reactions, aimed=t.aimed, blocked=t.blocked)
        for t in entry.targets[:_MAX_TARGETS]
    ]
    more = len(entry.targets) - len(targets)
    row_w = sum(b.get_width() for b in blocks) + (52 if arrow else 0) + sum(t.get_width() for t in targets) \
        + (30 if more > 0 else 0)
    row_h = max([b.get_height() for b in blocks + targets] or [0])
    width = max(_TEXT_W, row_w) + 2 * _PANEL_PAD
    font = fonts.get(14)
    text: list[pygame.Surface] = [outlined(fonts.get(16), entry.title, (246, 204, 92))]
    sub = {"hero": "Tú", "enemy": "Enemigo", "effect": "Efecto"}.get(entry.kind, "")
    text.append(outlined(fonts.get(8), f"Turno {entry.turn}  ·  {sub}", (176, 170, 160)))
    for line in entry.lines:
        text += rich_text.render_lines(line, font, width - 2 * _PANEL_PAD)
    text_h = sum(s.get_height() + 2 for s in text)
    height = _PANEL_PAD * 2 + row_h + (10 if row_h else 0) + text_h
    panel = pygame.Surface((width, height), pygame.SRCALPHA)
    accent = _STYLE.get(entry.kind, _STYLE["effect"])[1]
    pygame.draw.rect(panel, (16, 12, 22, 240), panel.get_rect(), border_radius=10)
    pygame.draw.rect(panel, accent, panel.get_rect(), 2, border_radius=10)
    x, y = _PANEL_PAD, _PANEL_PAD
    for b in blocks:
        panel.blit(b, (x, y + (row_h - b.get_height()) // 2))
        x += b.get_width()
    if arrow is not None:
        cy = y + row_h // 2 - 8
        pygame.draw.line(panel, (236, 228, 214), (x + 4, cy), (x + 46, cy), 3)
        pygame.draw.polygon(panel, (236, 228, 214), [(x + 46, cy - 7), (x + 46, cy + 7), (x + 52, cy)])
        panel.blit(arrow, arrow.get_rect(center=(x + 25, cy - 16)))
        x += 52
    for t in targets:
        panel.blit(t, (x, y + (row_h - t.get_height()) // 2))
        x += t.get_width()
    if more > 0:
        extra = outlined(fonts.get(16), f"+{more}", (236, 228, 214))
        panel.blit(extra, (x + 4, y + row_h // 2 - 8))
    y += row_h + (10 if row_h else 0)
    for s in text:
        panel.blit(s, (_PANEL_PAD, y))
        y += s.get_height() + 2
    if len(_detail_cache) > 64:
        _detail_cache.clear()
    _detail_cache[key] = (entry, panel)
    return panel
