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

from src.domain.entities import (
    BLADES, ENTANGLED, FRAIL, MARKED, POISON, STATUS_TEXT, STRENGTH, VULNERABLE, WEAK,
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
}

_KEYWORD_ICON: dict[Keyword, str] = {
    Keyword.COMBO: "combo",
    Keyword.SINGULAR: "singular",
    Keyword.VOID: "void",
    Keyword.SPOIL: "spoil",
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

    @cached_property
    def pattern(self) -> re.Pattern:
        words = self.words or (self.name,)
        return re.compile(r"(?<![\wÁÉÍÓÚáéíóúñÑ])(" + "|".join(re.escape(w) for w in words) + r")(?![\wáéíóúñ])")


def _keyword_rule(kw: Keyword) -> str:
    rule = KEYWORD_DEFS[kw].rule
    prefix = KEYWORD_DEFS[kw].name + ":"
    rule = rule[len(prefix):].strip() if rule.startswith(prefix) else rule
    return rule[0].upper() + rule[1:]


_STATUS_KIND: dict[str, bool] = {      # True = buff
    POISON: False, VULNERABLE: False, WEAK: False, FRAIL: False, ENTANGLED: False,
    MARKED: False, STRENGTH: True, BLADES: True, RITUAL: True,
}

STATUS_TERMS: dict[str, Term] = {
    name: Term(name, STATUS_TEXT.get(name, ""), status_icon(name, is_buff),
               POISON_INK if name == POISON else KEYWORD)
    for name, is_buff in _STATUS_KIND.items() if STATUS_TEXT.get(name)
}

KEYWORD_TERMS: dict[Keyword, Term] = {
    kw: Term(KEYWORD_DEFS[kw].name, _keyword_rule(kw), _KEYWORD_ICON[kw]) for kw in Keyword
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
ALL_TERMS: tuple[Term, ...] = (*STATUS_TERMS.values(), *KEYWORD_TERMS.values(), EXHAUST, ETHEREAL, UNPLAYABLE)


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
