"""Tooltips: what a card, enemy, intent, status, relic or pile does, in plain Spanish.

Built the way card games make rules readable (Slay the Spire, Monster Train…):

* **One main panel** with an icon, a title, a short subtitle and the rule text.
  Rule text is colour-coded by ``rich_text`` (damage red, block blue, terms gold).
  A line may start with ``[[icon]]`` to show that icon in front of it, and a line
  that starts with two spaces is a dim note.
* **One small panel per keyword** the text mentions (``TooltipPanel``): Veneno,
  Vulnerable, Combo, Agotar… each with its icon and its rule, so the player never
  has to guess what a word means.
* Enemy intents are written as sentences with the real numbers — how many hits,
  how much in total, what Fuerza / Débil / Vulnerable changed, and how much of
  it your block will stop.

``draw_tooltip(surface, content, mouse_pos, fonts, beside=rect)`` lays out the
stack next to the cursor or next to ``beside`` (a hovered card) and keeps it on
screen (two columns when it is too tall).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

import pygame

from src.domain.card import Card, CardClass, CardType, ModifierTag
from src.domain.card_pool import CARD_CLASS_LABEL
from src.domain.chroma import chroma_def, chroma_title
from src.domain.entities import (
    HERO_TIMED_DEBUFFS, STRENGTH, VULNERABLE, WEAK, Enemy, Intent, IntentType, Player, StatusEffect,
    status_stacks,
)
from src.domain.keywords import Keyword, combo_text, singular_text, spoil_text, void_text
from src.domain.mana import Mana
from src.domain.numbers import BigValue
from src.domain.rarity import rarity_label
from src.domain.relic import Relic
from src.domain.status_cards import make_status_card
from src.infrastructure import colors
from src.infrastructure.fonts import FontRegistry
from src.infrastructure.ui_icons import ui_icon
from src.presentation.ui import glossary as gl
from src.presentation.ui import rich_text

# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------

@dataclass
class TooltipPanel:
    """A small glossary box under the main panel (a keyword, a status, a status card…)."""
    title: str
    lines: list[str] = field(default_factory=list)
    icon: str | None = None
    color: tuple[int, int, int] = gl.KEYWORD
    tag: str = ""                       # right-aligned note: "x2", "¡Activo!", "Perjuicio"…
    key: str = ""                       # glossary term it explains (default: the title)


@dataclass
class TooltipContent:
    title: str
    lines: list[str] = field(default_factory=list)
    icon: str | None = None
    subtitle: str = ""
    tag: str = ""
    accent: tuple[int, int, int] | None = None
    panels: list[TooltipPanel] = field(default_factory=list)

    def all_text(self) -> str:
        """Every string of the tooltip (title, subtitle, lines and panels), for searches and tests."""
        parts = [self.title, self.subtitle, self.tag, *self.lines]
        for p in self.panels:
            parts += [p.title, p.tag, *p.lines]
        return "\n".join(_strip_icon(s) for s in parts if s)


_ICON_PREFIX = re.compile(r"^\[\[(\w+)\]\]\s*")


def _strip_icon(line: str) -> str:
    return _ICON_PREFIX.sub("", line)


def _term_panel(term: gl.Term, tag: str = "") -> TooltipPanel:
    return TooltipPanel(term.name, [term.rule], term.icon, term.color, tag)


def _glossary(content: TooltipContent, *, include_shield: bool = False) -> None:
    """Add a panel for every term the content mentions that has no panel yet."""
    have = {p.key or p.title for p in content.panels}
    texts = [content.title, *content.lines] + [l for p in content.panels for l in p.lines]
    for term in gl.terms_in(texts, exclude=have, include_shield=include_shield):
        content.panels.append(_term_panel(term))
        have.add(term.name)


# ---------------------------------------------------------------------------
# Cards
# ---------------------------------------------------------------------------

_CARD_TYPE_NAME: dict[CardType, str] = {
    CardType.ATTACK: "Ataque",
    CardType.SKILL:  "Habilidad",
    CardType.POWER:  "Poder",
    CardType.STATUS: "Estado",
}

_CARD_TYPE_ICON: dict[CardType, str] = {
    CardType.ATTACK: "damage",
    CardType.SKILL: "block",
    CardType.POWER: "ritual",
    CardType.STATUS: "junk_card",
}

_MOD_DESCRIPTIONS: dict[ModifierTag, tuple[str, str]] = {
    ModifierTag.CHROMA:      ("Chroma", "Altera el tipo de daño."),
    ModifierTag.TRANSPARENT: ("Transparente", "El daño ignora el bloqueo."),
    ModifierTag.ETHEREAL:    ("Etéreo", "Se agota al jugarse, no se descarta."),
    ModifierTag.ECHO:        ("Eco", "El efecto se activa dos veces."),
}

_KEYWORD_SUMMARY = {
    Keyword.COMBO: combo_text,
    Keyword.SINGULAR: singular_text,
    Keyword.VOID: void_text,
    Keyword.SPOIL: spoil_text,
}


def _sentence(text: str) -> str:
    return text[0].upper() + text[1:] + ("" if text.endswith(".") else ".")


def card_rule_lines(card: Card) -> list[str]:
    """The card's own effect sentences (on_play texts), for status-card panels."""
    return [_sentence(fx.text) for fx in card.all_effects() if fx.text]


def card_tooltip(
    card: Card,
    *,
    bonus_damage: int = 0,
    bonus_block: int = 0,
    combo_active: bool = False,
    singular_active: bool = False,
    void_active: bool = False,
    spoil_active: bool = False,
) -> TooltipContent:
    active = {
        Keyword.COMBO: combo_active and bool(card.combo_effects()),
        Keyword.SINGULAR: singular_active and bool(card.singular_effects()),
        Keyword.VOID: void_active and bool(card.void_effects()),
        Keyword.SPOIL: spoil_active and bool(card.spoil_effects()),
    }
    combo, singular, void, spoil = (active[k] for k in (Keyword.COMBO, Keyword.SINGULAR, Keyword.VOID, Keyword.SPOIL))
    title = chroma_title(card.name, card.chroma) + (" (Rota)" if card.is_broken else "")
    cost = "Injugable" if card.unplayable else f"Coste: {card.cost} maná"
    content = TooltipContent(
        title=title,
        icon=_CARD_TYPE_ICON.get(card.card_type),
        subtitle=f"{_CARD_TYPE_NAME[card.card_type]}  ·  {cost}  ·  {CARD_CLASS_LABEL[card.card_class]}",
    )
    lines = content.lines

    dmg = card.total_damage(combo, singular, void, spoil)
    blk = card.total_block(combo, singular, void, spoil)
    if dmg > 0:
        lines.append(f"Inflige {BigValue.format_int(dmg + bonus_damage)} de daño a un enemigo.")
        if bonus_damage > 0:
            lines.append(f"  ({BigValue.format_int(dmg)} base + {bonus_damage} bonus)")
    if blk > 0:
        lines.append(f"Gana {BigValue.format_int(blk + bonus_block)} de escudo.")
        if bonus_block > 0:
            lines.append(f"  ({BigValue.format_int(blk)} base + {bonus_block} destreza)")

    base_draw = card.total_draw(combo, singular, void, spoil)
    if base_draw > 0:
        lines.append(f"Roba {base_draw} carta{'s' if base_draw > 1 else ''}.")

    for fx in card.all_effects():
        if fx.text:
            lines.append(_sentence(fx.text))
    if card.play_on_draw:
        lines.append("Se juega sola al robarla y desaparece.")
    if not (dmg or blk or base_draw or any(fx.text for fx in card.all_effects())):
        lines.append("Poder permanente: efecto especial." if card.card_type == CardType.POWER
                     else "Efecto especial.")

    if card.stacked_effects:
        lines += ["", f"Efectos apilados ({card.effect_count()}):"]
        for fx in card.stacked_effects:
            parts: list[str] = []
            d = fx.damage.resolve()
            b = fx.block.resolve()
            if d > 0:
                parts.append(f"+{BigValue.format_int(d)} de daño")
            if b > 0:
                parts.append(f"+{BigValue.format_int(b)} de escudo")
            lines.append(f"  · {fx.name}: {', '.join(parts) if parts else 'efecto pasivo'}")

    # Keyword layers: one panel each, with the extra effect and whether it is on now.
    for kw in sorted(card.keywords(), key=lambda k: k.value):
        term = gl.KEYWORD_TERMS[kw]
        on = active[kw]
        content.panels.append(TooltipPanel(
            term.name, [term.rule, f"Efecto extra: {_KEYWORD_SUMMARY[kw](card)}."],
            term.icon, (150, 240, 140) if on else term.color, "¡Activo!" if on else "",
        ))

    if card.exhaust:
        content.panels.append(_term_panel(gl.EXHAUST))
    if card.unplayable:
        content.panels.append(_term_panel(gl.UNPLAYABLE))
    if card.ethereal:
        content.panels.append(_term_panel(gl.ETHEREAL))

    for mod in card.modifiers:
        name, rule = _MOD_DESCRIPTIONS.get(mod.tag, (mod.tag.name.title(), ""))
        content.panels.append(TooltipPanel(name, [rule] if rule else [], "singular", (200, 210, 255)))

    if card.is_broken:
        content.panels.append(TooltipPanel("ROTA", ["Puede fusionarse con otra carta rota."],
                                           "unplayable", (255, 140, 120)))
    if card.chroma is not None:
        cdef = chroma_def(card.chroma)
        content.panels.append(TooltipPanel(cdef.name, [cdef.card_note], "singular", (255, 222, 120)))

    _glossary(content)
    return content


# ---------------------------------------------------------------------------
# Enemies and intents
# ---------------------------------------------------------------------------

_CARD_PILE = {"draw": "tu pila de robo", "discard": "tu pila de descarte", "hand": "tu mano"}

_INTENT_TITLE: dict[IntentType, str] = {
    IntentType.ATTACK:  "Va a atacar",
    IntentType.BLOCK:   "Va a defenderse",
    IntentType.BUFF:    "Va a fortalecerse",
    IntentType.DEBUFF:  "Va a debilitarte",
    IntentType.UNKNOWN: "Intención desconocida",
}


def attack_icon(total_damage: int) -> str:
    """Intent sword size grows with the damage of the whole attack (Slay the Spire style)."""
    if total_damage < 8:
        return "attack_1"
    if total_damage < 16:
        return "attack_2"
    if total_damage < 26:
        return "attack_3"
    return "attack_4"


def intent_icon(intent: Intent, hit_damage: int | None = None) -> str:
    if intent.intent_type == IntentType.ATTACK:
        dmg = hit_damage if hit_damage is not None else intent.value
        return attack_icon(dmg * max(1, intent.hits))
    return {IntentType.BLOCK: "defend", IntentType.BUFF: "buff",
            IntentType.DEBUFF: "debuff"}.get(intent.intent_type, "unknown")


def _damage_breakdown(enemy: Enemy, player: Player | None) -> str:
    """"  Base 4 · +2 Fuerza · Débil −25 % · Vulnerable +50 %" (empty when nothing changes it)."""
    parts: list[str] = []
    strength = status_stacks(enemy.status_effects, STRENGTH)
    if strength:
        parts.append(f"+{strength} Fuerza")
    if status_stacks(enemy.status_effects, WEAK) > 0:
        parts.append("Débil −25 %")
    if player is not None and status_stacks(player.status_effects, VULNERABLE) > 0:
        parts.append("tu Vulnerable +50 %")
    return f"  Base {enemy.intent.value} por golpe · " + " · ".join(parts) if parts else ""


def intent_lines(enemy: Enemy, hit_damage: int | None = None,
                 player: Player | None = None) -> list[str]:
    """What the enemy will do on its turn, one plain sentence per effect, with icons."""
    it = enemy.intent
    lines: list[str] = []
    if it.intent_type == IntentType.ATTACK:
        dmg = hit_damage if hit_damage is not None else it.value
        hits = max(1, it.hits)
        total = dmg * hits
        icon = attack_icon(total)
        if hits > 1:
            lines.append(f"[[{icon}]]Te atacará {hits} veces de {dmg} de daño ({total} de daño en total).")
        else:
            lines.append(f"[[{icon}]]Te atacará por {dmg} de daño.")
        note = _damage_breakdown(enemy, player)
        if note:
            lines.append(note)
        if player is not None:
            stopped = min(player.block, total)
            lost = total - stopped
            if stopped > 0:
                lines.append(f"  Tu escudo para {stopped}: perderías {lost} de vida.")
            if lost >= player.current_hp > 0:
                lines.append("[[lethal]]¡Este ataque te matará si no te proteges!")
    elif it.intent_type == IntentType.BLOCK:
        lines.append(f"[[defend]]Ganará {it.value} de escudo.")
    elif it.intent_type == IntentType.BUFF and not it.buffs:
        lines.append("[[buff]]Va a fortalecerse.")
    elif it.intent_type == IntentType.DEBUFF and not it.debuffs:
        lines.append("[[debuff]]Va a debilitarte.")
    elif it.intent_type == IntentType.UNKNOWN:
        lines.append("[[unknown]]No se sabe qué hará.")

    if it.block > 0:
        lines.append(f"[[defend]]Ganará {it.block} de escudo.")
    for name, n in it.buffs:
        lines.append(f"[[buff]]Ganará {n} de {name}.")
    for name, n in it.debuffs:
        lines.append(f"[[debuff]]Te aplicará {n} de {name}.")
    for card_id, n, pile in it.cards:
        card = make_status_card(card_id)
        label = card.name if card else card_id
        if n > 1 and not label.endswith("s"):
            label += "s"
        lines.append(f"[[cards]]Meterá {n} {label} en {_CARD_PILE.get(pile, pile)}.")
    if it.lifesteal:
        lines.append("[[heal]]Se curará tanta vida como te quite.")
    if it.ally_block > 0:
        lines.append(f"[[defend]]Dará {it.ally_block} de escudo a su compañero.")
    for name, n in it.ally_buffs:
        lines.append(f"[[buff]]Dará {n} de {name} a sus aliados.")
    if it.heal_allies > 0:
        lines.append(f"[[heal]]Curará {it.heal_allies} de vida a cada aliado (y a sí mismo).")
    if it.self_destruct:
        lines.append("[[fuse]]Después de atacar, explota y muere.")
    return lines


def _intent_panels(enemy: Enemy) -> list[TooltipPanel]:
    """A panel per status card the intent shuffles in (what that junk card does)."""
    out: list[TooltipPanel] = []
    for card_id, _, _ in enemy.intent.cards:
        card = make_status_card(card_id)
        if card is not None:
            out.append(TooltipPanel(card.name, card_rule_lines(card), "cards", (170, 230, 110), "Carta de estado"))
    return out


def intent_tooltip(enemy: Enemy, hit_damage: int | None = None,
                   player: Player | None = None) -> TooltipContent:
    """Hovering the intent icon: the move, what it will do and the words it uses."""
    it = enemy.intent
    title = it.move or _INTENT_TITLE.get(it.intent_type, "Intención")
    content = TooltipContent(
        title=title, icon=intent_icon(it, hit_damage),
        subtitle=f"Intención de {enemy.name}  ·  ocurre al terminar tu turno",
        lines=intent_lines(enemy, hit_damage, player),
        accent=_intent_accent(it),
    )
    if it.description:
        content.lines.append("  " + it.description)
    content.panels += _intent_panels(enemy)
    _glossary(content)
    return content


def _intent_accent(intent: Intent) -> tuple[int, int, int]:
    return {
        IntentType.ATTACK: (255, 120, 100), IntentType.BLOCK: (120, 180, 255),
        IntentType.BUFF: (130, 200, 255), IntentType.DEBUFF: (220, 150, 255),
    }.get(intent.intent_type, (190, 190, 200))


def status_panel(fx: StatusEffect, *, on_player: bool = False) -> TooltipPanel:
    term = gl.status_term(fx.name, fx.is_buff)
    lines = [term.rule] if term.rule else []
    if on_player and fx.name in HERO_TIMED_DEBUFFS:
        lines.append(f"  Dura {fx.stacks} turno{'s' if fx.stacks != 1 else ''} (baja 1 al final de tu turno).")
    return TooltipPanel(
        f"{fx.name} {fx.stacks}", lines, term.icon,
        gl.BUFF_TITLE if fx.is_buff else gl.DEBUFF_TITLE,
        "Mejora" if fx.is_buff else "Perjuicio", key=fx.name,
    )


def status_tooltip(fx: StatusEffect, *, on_player: bool = False) -> TooltipContent:
    """Hovering a status badge: just that status."""
    panel = status_panel(fx, on_player=on_player)
    return TooltipContent(title=panel.title, lines=panel.lines, icon=panel.icon,
                          subtitle="Mejora" if fx.is_buff else "Perjuicio", accent=panel.color)


def _identity(enemy: Enemy) -> str:
    """"Agresivo: …" — the identity of a regular enemy (``enemy_roster.ENEMIES``) or an elite."""
    from src.application.elites import ELITES
    from src.application.enemy_roster import ENEMIES, NAME_TO_AI
    d = (ELITES.get(enemy.ai) if enemy.is_elite else None) or ENEMIES.get(enemy.ai) \
        or ENEMIES.get(NAME_TO_AI.get(enemy.name, ""))
    return f"{d.identity}: {d.title}" if d is not None and not enemy.is_boss else ""


def enemy_tooltip(enemy: Enemy, hit_damage: int | None = None,
                  player: Player | None = None) -> TooltipContent:
    lines: list[str] = [f"Vida: {enemy.current_hp} / {enemy.max_hp}"]
    identity = _identity(enemy)
    if identity:
        lines.append(identity)
    if enemy.pair:
        lines.append(f"  Pareja: {enemy.pair}. Si cae su pareja, buscará Venganza.")
    if enemy.block > 0:
        lines.append(f"Bloqueo: {enemy.block} (absorbe el próximo daño)")
    it = enemy.intent
    head = f"Intención: {it.move}" if it.move else "Intención"
    panels = [TooltipPanel(head, intent_lines(enemy, hit_damage, player) +
                           (["  " + it.description] if it.description else []),
                           intent_icon(it, hit_damage), _intent_accent(it))]
    panels += [status_panel(fx) for fx in enemy.status_effects]
    panels += _intent_panels(enemy)
    content = TooltipContent(
        title=enemy.name, lines=lines,
        tag="JEFE" if enemy.is_boss else "ÉLITE" if enemy.is_elite else "",
        subtitle=("Jefe del piso" if enemy.is_boss else
                  "Élite del piso: suelta una reliquia" if enemy.is_elite else "Enemigo"),
        panels=panels,
    )
    _glossary(content)
    return content


# ---------------------------------------------------------------------------
# Relics, piles, mana, player
# ---------------------------------------------------------------------------

def relic_tooltip(relic: Relic) -> TooltipContent:
    status = "Estado: Activo" if relic.is_active else "Estado: Agotado"
    lines = [relic.description, f"Rareza: {rarity_label(relic.rarity)}"]
    if relic.relic_class is not CardClass.NEUTRAL:
        lines.append(f"Solo para {CARD_CLASS_LABEL[relic.relic_class]}")
    if relic.chroma is not None:
        lines.append(chroma_def(relic.chroma).relic_note)
    content = TooltipContent(title=chroma_title(relic.name, relic.chroma), lines=[*lines, "", status],
                             subtitle="Reliquia")
    _glossary(content)
    return content


def pile_tooltip(pile_label: str, count: int, *, is_draw: bool) -> TooltipContent:
    if is_draw:
        return TooltipContent(
            title="Pila de Robo", icon="draw",
            lines=[
                f"{count} carta(s) restantes.",
                "Haz clic para ver las cartas.",
                "",
                "Cuando se agota se baraja la pila de descarte y se convierte en la nueva pila.",
            ],
        )
    return TooltipContent(
        title="Pila de Descarte", icon="spoil",
        lines=[
            f"{count} carta(s) descartadas.",
            "Haz clic para ver las cartas.",
            "",
            "Se baraja en la pila de robo cuando ésta se queda sin cartas.",
        ],
    )


def mana_tooltip(mana: Mana) -> TooltipContent:
    return TooltipContent(
        title="Maná", icon="mana",
        lines=[
            f"Disponible: {mana.current} / {mana.maximum}",
            "",
            "Recurso para jugar cartas. Se recarga completamente al inicio de cada turno.",
        ],
    )


def player_tooltip(player: Player, incoming: int | None = None) -> TooltipContent:
    """The hero: HP, block, luck, the damage coming this enemy turn and every status."""
    lines = [f"Vida: {player.current_hp} / {player.max_hp}"]
    if player.block > 0:
        lines.append(f"[[block]]Bloqueo: {player.block} (absorbe el próximo daño recibido).")
    else:
        lines.append("Sin bloqueo activo.")
    if incoming:
        lost = max(0, incoming - player.block)
        lines.append(f"[[{attack_icon(incoming)}]]Daño entrante: {incoming} de daño; perderías {lost} de vida.")
        if lost >= player.current_hp > 0:
            lines.append("[[lethal]]¡Letal! Consigue escudo o mata a quien ataca.")
    if player.luck > 0:
        lines.append(f"Suerte: {player.luck} -- más cartas y reliquias doradas, y reliquias de mayor rareza.")
    content = TooltipContent(title=player.name, lines=lines, subtitle="Tu héroe",
                             panels=[status_panel(fx, on_player=True) for fx in player.status_effects])
    _glossary(content)
    return content


# ---------------------------------------------------------------------------
# Renderer
# ---------------------------------------------------------------------------

_MAIN_W: int = 318
_PANEL_W: int = 318
_PAD: int = 9
_GAP: int = 3
_STACK_GAP: int = 5
_CORNER: int = 5
_OFF_X: int = 18
_OFF_Y: int = -6
_BG = (16, 13, 26, 238)
_PANEL_BG = (22, 18, 34, 236)
_ICON_W = 28


def _fonts(fonts: FontRegistry):
    return fonts.get(16), fonts.get(11), fonts.get(13), fonts.get(11)


def _body(lines: list[str], font: pygame.font.Font, width: int, base) -> list[tuple[pygame.Surface | None, pygame.Surface | None, int]]:
    """Lay out body lines: (icon or None, text surface or None for a gap, indent)."""
    out: list[tuple[pygame.Surface | None, pygame.Surface | None, int]] = []
    for raw in lines:
        if raw == "":
            out.append((None, None, 0))
            continue
        icon = None
        m = _ICON_PREFIX.match(raw)
        if m:
            icon = ui_icon(m.group(1), 1)
            raw = raw[m.end():]
        dim = raw.startswith("  ")
        indent = (icon.get_width() + 5) if icon is not None else (8 if dim else 0)
        surfs = rich_text.render_lines(raw.strip(), font, width - indent, gl.DIM if dim else base)
        for k, s in enumerate(surfs):
            out.append((icon if k == 0 else None, s, indent))
    return out


def _row_h(icon, s) -> int:
    return max(s.get_height(), icon.get_height() - 2 if icon is not None else 0)


def _body_height(rows, font) -> int:
    h = 0
    for icon, s, _ in rows:
        h += (_GAP * 2) if s is None else (_row_h(icon, s) + _GAP)
    return h


def _header(title: str, icon: str | None, tag: str, color, title_font, tag_font, width: int):
    icon_surf = ui_icon(icon, 2) if icon else None
    title_x = (_ICON_W + 6) if icon_surf is not None else 0
    tag_s = tag_font.render(tag, True, (210, 200, 180)) if tag else None
    room = width - title_x - ((tag_s.get_width() + 8) if tag_s else 0)
    lines = [title_font.render(t, True, color) for t in _word_wrap(title, title_font, room)] if title else []
    h = max(_ICON_W if icon_surf is not None else 0, sum(s.get_height() for s in lines))
    return icon_surf, title_x, tag_s, lines, h


def _measure_main(content: TooltipContent, fonts: FontRegistry):
    title_font, sub_font, body_font, tag_font = _fonts(fonts)
    inner = _MAIN_W - _PAD * 2
    accent = content.accent or colors.TEXT_ACCENT
    head = _header(content.title, content.icon, content.tag, tuple(accent[:3]), title_font, tag_font, inner)
    sub = rich_text.render_lines(content.subtitle, sub_font, inner, (160, 152, 138)) if content.subtitle else []
    rows = _body(content.lines, body_font, inner, gl.BODY)
    h = _PAD * 2 + head[4] + sum(s.get_height() for s in sub) + (2 if sub else 0)
    if rows:
        h += 10 + _body_height(rows, body_font)
    return head, sub, rows, h, accent


def _measure_panel(panel: TooltipPanel, fonts: FontRegistry):
    _, _, _, tag_font = _fonts(fonts)
    title_font = fonts.get(14)
    body_font = fonts.get(12)
    inner = _PANEL_W - _PAD * 2
    head = _header(panel.title, panel.icon, panel.tag, panel.color, title_font, tag_font, inner)
    rows = _body(panel.lines, body_font, inner, (214, 208, 196))
    h = _PAD * 2 - 2 + head[4] + ((4 + _body_height(rows, body_font)) if rows else 0)
    return head, rows, h


def _draw_box(surface: pygame.Surface, rect: pygame.Rect, bg, border) -> None:
    box = pygame.Surface(rect.size, pygame.SRCALPHA)
    pygame.draw.rect(box, bg, box.get_rect(), border_radius=_CORNER)
    surface.blit(box, rect.topleft)
    pygame.draw.rect(surface, border, rect, 1, border_radius=_CORNER)
    hl = tuple(min(255, c + 40) for c in border[:3])
    pygame.draw.line(surface, hl, (rect.x + _CORNER, rect.y + 1), (rect.right - _CORNER - 1, rect.y + 1))


def _draw_head(surface, head, x, y, width) -> int:
    icon_surf, title_x, tag_s, lines, h = head
    if icon_surf is not None:
        surface.blit(icon_surf, icon_surf.get_rect(midleft=(x - 2, y + h // 2)))
    ty = y + (h - sum(s.get_height() for s in lines)) // 2
    for s in lines:
        surface.blit(s, (x + title_x, ty))
        ty += s.get_height()
    if tag_s is not None:
        surface.blit(tag_s, tag_s.get_rect(midright=(x + width, y + h // 2)))
    return y + h


def _draw_rows(surface, rows, x, y) -> int:
    for icon, s, indent in rows:
        if s is None:
            y += _GAP * 2
            continue
        rh = _row_h(icon, s)
        if icon is not None:
            surface.blit(icon, icon.get_rect(midleft=(x - 1, y + rh // 2)))
        surface.blit(s, (x + indent, y + (rh - s.get_height()) // 2))
        y += rh + _GAP
    return y


def tooltip_size(content: TooltipContent, fonts: FontRegistry) -> tuple[int, int]:
    """(width, height) of the whole stack in one column (layout helper and tests)."""
    h = _measure_main(content, fonts)[3]
    for p in content.panels:
        h += _STACK_GAP + _measure_panel(p, fonts)[2]
    return _MAIN_W, h


_STACK_CACHE: dict = {}
_STACK_CACHE_MAX = 48


def _render_stack(content: TooltipContent, fonts: FontRegistry, screen_h: int) -> pygame.Surface:
    """The whole tooltip stack (main panel + glossary panels, 1–2 columns) on one surface, cached."""
    key = (repr(content), id(fonts), screen_h)
    cached = _STACK_CACHE.get(key)
    if cached is not None:
        return cached
    head, sub, rows, main_h, accent = _measure_main(content, fonts)
    panels = [(p, *_measure_panel(p, fonts)) for p in content.panels]
    limit = screen_h - 8

    # Columns: the main panel then as many glossary panels as fit; the rest go in a 2nd column.
    columns: list[list[tuple]] = [[("main", main_h)]]
    col_h = main_h
    for item in panels:
        h = item[3]
        if col_h + _STACK_GAP + h > limit and len(columns) < 2:
            columns.append([])
            col_h = -_STACK_GAP
        columns[-1].append(("panel", item))
        col_h += _STACK_GAP + h
    heights = [sum(_entry_h(e) for e in col) + _STACK_GAP * (len(col) - 1) for col in columns]
    total_w = _MAIN_W * len(columns) + 6 * (len(columns) - 1)
    stack = pygame.Surface((total_w, max(heights)), pygame.SRCALPHA)

    for c, col in enumerate(columns):
        x = c * (_MAIN_W + 6)
        y = 0
        for kind, data in col:
            if kind == "main":
                rect = pygame.Rect(x, y, _MAIN_W, main_h)
                _draw_box(stack, rect, _BG, _dim(accent, 0.85))
                cy = _draw_head(stack, head, x + _PAD, y + _PAD, _MAIN_W - _PAD * 2)
                for s in sub:
                    stack.blit(s, (x + _PAD, cy + 1))
                    cy += s.get_height()
                if rows:
                    cy += 5
                    pygame.draw.line(stack, _dim(accent, 0.45), (x + _PAD, cy), (x + _MAIN_W - _PAD, cy))
                    cy += 5
                    _draw_rows(stack, rows, x + _PAD, cy)
                y += main_h + _STACK_GAP
            else:
                panel, phead, prows, ph = data
                rect = pygame.Rect(x, y, _PANEL_W, ph)
                _draw_box(stack, rect, _PANEL_BG, _dim(panel.color, 0.55))
                cy = _draw_head(stack, phead, x + _PAD, y + _PAD - 2, _PANEL_W - _PAD * 2)
                if prows:
                    _draw_rows(stack, prows, x + _PAD, cy + 4)
                y += ph + _STACK_GAP
    _STACK_CACHE[key] = stack
    if len(_STACK_CACHE) > _STACK_CACHE_MAX:
        _STACK_CACHE.pop(next(iter(_STACK_CACHE)))
    return stack


def draw_tooltip(
    surface: pygame.Surface,
    content: TooltipContent,
    mouse_pos: tuple[int, int],
    fonts: FontRegistry,
    *,
    beside: pygame.Rect | None = None,
) -> pygame.Rect:
    """Draw the tooltip stack near the cursor, or next to ``beside`` (e.g. a hovered card).

    Returns the bounding rect of everything drawn.
    """
    sw, sh = surface.get_size()
    stack = _render_stack(content, fonts, sh)
    total_w, total_h = stack.get_size()
    if beside is not None:
        tx = beside.right + 8 if beside.right + 8 + total_w <= sw - 4 else beside.left - total_w - 8
        ty = min(beside.top, sh - 4 - total_h)
    else:
        tx = mouse_pos[0] + _OFF_X
        ty = mouse_pos[1] + _OFF_Y
        if tx + total_w > sw - 4:
            tx = mouse_pos[0] - total_w - _OFF_X
        if ty + total_h > sh - 4:
            ty = sh - 4 - total_h
    tx = max(4, min(tx, sw - 4 - total_w))
    ty = max(4, ty)
    surface.blit(stack, (tx, ty))
    return pygame.Rect(tx, ty, total_w, total_h)


def _entry_h(entry) -> int:
    kind, data = entry
    return data if kind == "main" else data[3]


def _dim(color, k: float) -> tuple[int, int, int]:
    return tuple(int(c * k) for c in color[:3])


def _word_wrap(text: str, font: pygame.font.Font, max_w: int) -> list[str]:
    """Plain word wrap (kept for callers that render their own text)."""
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        test = (current + " " + word).strip()
        if font.size(test)[0] <= max_w:
            current = test
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines or [text]
