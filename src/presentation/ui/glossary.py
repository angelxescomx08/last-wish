"""Keyword glossary: one icon, one colour and one rule per term (Slay the Spire style).

Every status, card keyword and card flag the player may not know has a
``Term`` here. Tooltips show a small panel for each term a text mentions
(``terms_in``), status badges use ``status_icon`` and the rich-text renderer
(``rich_text``) paints the term names in ``KEYWORD`` gold.

Rule texts come from the domain (``STATUS_TEXT``, ``KEYWORD_DEFS``); this module
only adds the presentation (icon names from ``assets/ui/icons.json``, colours).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from functools import cached_property

from src.domain.elements import REACTION_RULE, REACTION_TEXT, REACTIONS, Element, Reaction
from src.domain.entities import (
    AIR, BLADES, EARTH, ENTANGLED, FIRE, FRAIL, FROZEN, FUSE, MARKED, POISON, STATUS_TEXT,
    STRENGTH, VULNERABLE, WATER, WEAK,
)
from src.domain.keywords import KEYWORD_DEFS, Keyword

# Text colours shared by tooltips, card faces and status panels.
KEYWORD = (246, 204, 92)       # term names (gold)
DAMAGE = (255, 116, 92)        # "N de daño"
BLOCK = (112, 182, 255)        # "N de escudo / bloqueo"
POISON_INK = (138, 226, 96)    # Veneno
MANA = (150, 226, 255)         # "N de maná"
BUFF_TITLE = (130, 220, 150)   # status panel title: a buff
DEBUFF_TITLE = (226, 140, 238)  # status panel title: a debuff
# Mage elements (also the colour of "N de Fuego" etc. in rule text).
FIRE_INK = (255, 128, 72)
WATER_INK = (110, 176, 255)
EARTH_INK = (214, 168, 100)
AIR_INK = (170, 236, 240)
ICE_INK = (170, 226, 255)
REACTION_INK = (255, 150, 220)
DIM = (176, 170, 160)          # secondary text (flavour, notes)
BODY = (228, 223, 210)         # main text

RITUAL = "Ritual"

_STATUS_ICON: dict[str, str] = {
    POISON: "poison",
    VULNERABLE: "vulnerable",
    WEAK: "weak",
    FRAIL: "frail",
    ENTANGLED: "entangled",
    STRENGTH: "strength",
    BLADES: "blades",
    MARKED: "marked",
    RITUAL: "ritual",
    FUSE: "fuse",
    FIRE: "fire",
    WATER: "water",
    EARTH: "earth",
    AIR: "air",
    FROZEN: "frozen",
}

_KEYWORD_ICON: dict[Keyword, str] = {
    Keyword.COMBO: "combo",
    Keyword.SINGULAR: "singular",
    Keyword.VOID: "void",
    Keyword.SPOIL: "spoil",
    Keyword.REACTION: "reaction",
}

REACTION_ICON: dict[Reaction, str] = {
    Reaction.STEAM: "steam",
    Reaction.MAGMA: "magma",
    Reaction.WILDFIRE: "wildfire",
    Reaction.MUD: "mud",
    Reaction.FREEZE: "frozen",
    Reaction.SANDSTORM: "sandstorm",
}
REACTION_COLOR: dict[Reaction, tuple[int, int, int]] = {
    Reaction.STEAM: (236, 236, 246),
    Reaction.MAGMA: (255, 150, 60),
    Reaction.WILDFIRE: (255, 110, 70),
    Reaction.MUD: (200, 150, 96),
    Reaction.FREEZE: ICE_INK,
    Reaction.SANDSTORM: (236, 206, 140),
}
ELEMENT_COLOR: dict[str, tuple[int, int, int]] = {
    FIRE: FIRE_INK, WATER: WATER_INK, EARTH: EARTH_INK, AIR: AIR_INK,
}


def status_icon(name: str, is_buff: bool = False) -> str:
    """Icon name of a status (a generic arrow for statuses without their own picture)."""
    return _STATUS_ICON.get(name, "status_buff" if is_buff else "status_debuff")


@dataclass(frozen=True)
class Term:
    name: str                  # shown as the panel title
    rule: str                  # one or two plain sentences
    icon: str
    color: tuple[int, int, int] = KEYWORD
    words: tuple[str, ...] = ()  # spellings that mention it in a text (default: the name)
    regex: str = ""            # raw pattern instead of ``words`` (elements: "3 de Fuego")
    lines: tuple[str, ...] = ()  # extra panel lines (may start with "[[icon]]")

    @cached_property
    def pattern(self) -> re.Pattern:
        if self.regex:
            return re.compile(self.regex)
        words = self.words or (self.name,)
        return re.compile(r"(?<![\wÁÉÍÓÚáéíóúñÑ])(" + "|".join(re.escape(w) for w in words) + r")(?![\wáéíóúñ])")


def _keyword_rule(kw: Keyword) -> str:
    rule = KEYWORD_DEFS[kw].rule
    prefix = KEYWORD_DEFS[kw].name + ":"
    rule = rule[len(prefix):].strip() if rule.startswith(prefix) else rule
    return rule[0].upper() + rule[1:]


_STATUS_KIND: dict[str, bool] = {      # True = buff
    POISON: False, VULNERABLE: False, WEAK: False, FRAIL: False, ENTANGLED: False,
    MARKED: False, STRENGTH: True, BLADES: True, RITUAL: True, FUSE: True,
    FIRE: False, WATER: False, EARTH: False, AIR: False, FROZEN: False,
}

# Names that contain an element word but are not the element (cards, relics, enemy moves).
_NOT_ELEMENT = ("Orbe de ", "Bola de ", "Lengua de ", "Chroma ", "Muro de ", "Piel de ")


def _element_regex(name: str) -> str:
    """"3 de Fuego", "Fuego" — but not "Bola de Fuego" or "Orbe de Fuego"."""
    behind = "".join(f"(?<!{re.escape(p)})" for p in _NOT_ELEMENT)
    return behind + r"(?<![\wÁÉÍÓÚáéíóúñÑ])(?:\d+ de )?" + name + r"(?![\wáéíóúñ])"


def _element_lines(name: str) -> tuple[str, ...]:
    """What the element does with each other element: "[[steam]] + Agua: Vapor"."""
    me = Element(name)
    out = []
    for pair, reaction in REACTIONS.items():
        if me in pair:
            other = next(e for e in pair if e is not me)
            out.append(f"[[{REACTION_ICON[reaction]}]]+ {other.value}: {reaction.value}")
    return tuple(out)


def _status_term(name: str, is_buff: bool) -> Term:
    if name in ELEMENT_COLOR:
        return Term(name, STATUS_TEXT[name], status_icon(name), ELEMENT_COLOR[name],
                    regex=_element_regex(name), lines=_element_lines(name))
    color = POISON_INK if name == POISON else ICE_INK if name == FROZEN else KEYWORD
    return Term(name, STATUS_TEXT.get(name, ""), status_icon(name, is_buff), color)


STATUS_TERMS: dict[str, Term] = {
    name: _status_term(name, is_buff)
    for name, is_buff in _STATUS_KIND.items() if STATUS_TEXT.get(name)
}

# The six reactions (Vapor, Magma…): a panel each when a text names one.
REACTION_TERMS: dict[Reaction, Term] = {
    r: Term(r.value, REACTION_TEXT[r], REACTION_ICON[r], REACTION_COLOR[r]) for r in Reaction
}
# "reacción elemental": the general rule, with the six reactions as icon lines.
ELEMENTS_RULE = Term("Reacción elemental", REACTION_RULE, "reaction", REACTION_INK,
                     words=("reacción elemental", "reacciones", "reacción"),
                     lines=tuple(f"[[{REACTION_ICON[r]}]]{r.value}: {REACTION_TEXT[r]}" for r in Reaction))

KEYWORD_TERMS: dict[Keyword, Term] = {
    kw: Term(KEYWORD_DEFS[kw].name, _keyword_rule(kw), _KEYWORD_ICON[kw],
             REACTION_INK if kw is Keyword.REACTION else KEYWORD)
    for kw in Keyword
}

EXHAUST = Term("Agotar", "Al jugarla se retira del combate (no vuelve al descarte).", "exhaust",
               words=("Agotar", "Agota", "agotar", "se agota"))
ETHEREAL = Term("Etérea", "Si sigue en tu mano al final del turno, se desvanece: sale del combate.",
                "ethereal", words=("Etérea", "Etéreo", "Se desvanece", "se desvanece"))
UNPLAYABLE = Term("Injugable", "No se puede jugar. Solo ocupa sitio en tu mano.", "unplayable")
SHIELD = Term("Escudo", "Absorbe el daño de los golpes antes que tu vida. "
              "Se pierde al empezar tu siguiente turno.", "block", BLOCK,
              words=("escudo", "Escudo", "bloqueo", "Bloqueo"))

# Order = priority when several terms are found (statuses first, then keywords, then flags).
ALL_TERMS: tuple[Term, ...] = (*STATUS_TERMS.values(), *KEYWORD_TERMS.values(),
                               *REACTION_TERMS.values(), ELEMENTS_RULE, EXHAUST, ETHEREAL, UNPLAYABLE)


def status_term(name: str, is_buff: bool | None = None) -> Term:
    """Glossary entry of a status (a generic one for unknown names)."""
    term = STATUS_TERMS.get(name)
    if term is not None:
        return term
    buff = _STATUS_KIND.get(name, bool(is_buff))
    return Term(name, "Mejora temporal." if buff else "Perjuicio temporal.", status_icon(name, buff))


def is_buff_status(name: str, default: bool = False) -> bool:
    return _STATUS_KIND.get(name, default)


def terms_in(texts, *, exclude: set[str] | None = None, include_shield: bool = False) -> list[Term]:
    """Glossary terms mentioned in ``texts`` (a string or several), first mention first, no repeats."""
    if isinstance(texts, str):
        texts = [texts]
    joined = "\n".join(texts)
    pool = ALL_TERMS + ((SHIELD,) if include_shield else ())
    found: list[tuple[int, Term]] = []
    skip = exclude or set()
    for term in pool:
        if term.name in skip:
            continue
        m = term.pattern.search(joined)
        if m:
            found.append((m.start(), term))
    found.sort(key=lambda pair: pair[0])
    return [t for _, t in found]


def highlight_words() -> list[tuple[re.Pattern, tuple[int, int, int]]]:
    """(pattern, colour) of every term name, for the rich-text renderer."""
    return _HIGHLIGHTS


_HIGHLIGHTS = [(t.pattern, t.color) for t in ALL_TERMS]


# One short line per status for the quick view (hover an enemy / the hero), Slay the Spire style.
# ``{n}`` = stacks. The full rule stays in ``STATUS_TEXT`` (status badge hover, inspect panel).
_STATUS_SHORT: dict[str, str] = {
    POISON: "−{n} de vida por turno",
    WEAK: "−25 % de daño",
    VULNERABLE: "recibe +50 % de daño",
    FRAIL: "−25 % de escudo",
    ENTANGLED: "roba {n} menos",
    STRENGTH: "+{n} de daño por golpe",
    BLADES: "{n} espadas flotantes",
    MARKED: "+{n} por golpe recibido",
    FUSE: "explota en {n} turnos",
    RITUAL: "se fortalece cada turno",
    FIRE: "arde: −{n} de vida por turno",
    WATER: "sus golpes hacen {n} menos",
    EARTH: "recibe +{n} por golpe",
    AIR: "listo para reaccionar",
    FROZEN: "pierde su próxima acción",
}


def status_short(name: str, stacks: int) -> str:
    """"Veneno 5: pierde 5 de vida al inicio de su turno" (first sentence of the rule if unknown)."""
    text = _STATUS_SHORT.get(name)
    if text is None:
        rule = STATUS_TEXT.get(name, "")
        text = rule.split(". ")[0].rstrip(".") if rule else ("mejora" if is_buff_status(name) else "perjuicio")
        text = text[0].lower() + text[1:] if text else text
    return f"{name} {stacks}: " + text.replace("{n}", str(stacks))
