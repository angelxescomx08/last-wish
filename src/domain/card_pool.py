"""Card pool definitions organised by pack theme.

Every public function returns *new* Card instances — callers must not cache the
results across multiple uses, as cards are mutable (stacked_effects, modifiers).
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Callable

from src.domain.card import Card, CardEffect, CardType
from src.domain.numbers import BigValue


# ---------------------------------------------------------------------------
# Pack themes
# ---------------------------------------------------------------------------

class PackTheme(Enum):
    ACERO  = "acero"   # Attack-focused
    ESCUDO = "escudo"  # Defense-focused
    MAGIA  = "magia"   # Mixed/utility
    EPICO  = "epico"   # Powerful rare cards


@dataclass(frozen=True)
class PackDef:
    theme: PackTheme
    name: str
    description: str
    cost: int


ALL_PACKS: list[PackDef] = [
    PackDef(PackTheme.ACERO,  "Sobre de Acero",  "Cartas de ataque",      75),
    PackDef(PackTheme.ESCUDO, "Sobre de Escudo", "Cartas defensivas",     75),
    PackDef(PackTheme.MAGIA,  "Sobre de Magia",  "Cartas de magia mixta", 75),
    PackDef(PackTheme.EPICO,  "Sobre Épico",     "Cartas poderosas",     150),
]


# ---------------------------------------------------------------------------
# Internal card factories
# ---------------------------------------------------------------------------

def _atk(id: str, name: str, cost: int, dmg: int, draw: int = 0) -> Card:
    return Card(
        id=id, name=name, card_type=CardType.ATTACK, cost=cost,
        base_effect=CardEffect(name=name, damage=BigValue(dmg), draw=draw),
    )


def _skl(id: str, name: str, cost: int, blk: int, draw: int = 0) -> Card:
    return Card(
        id=id, name=name, card_type=CardType.SKILL, cost=cost,
        base_effect=CardEffect(name=name, block=BigValue(blk), draw=draw),
    )


def _combo(id: str, name: str, cost: int, dmg: int, blk: int, draw: int = 0) -> Card:
    """Attack that also grants block."""
    return Card(
        id=id, name=name, card_type=CardType.ATTACK, cost=cost,
        base_effect=CardEffect(name=name, damage=BigValue(dmg), block=BigValue(blk), draw=draw),
    )


def _pwr(id: str, name: str, cost: int, draw: int = 0) -> Card:
    return Card(
        id=id, name=name, card_type=CardType.POWER, cost=cost,
        base_effect=CardEffect(name=name, draw=draw),
    )


# ---------------------------------------------------------------------------
# Starter deck
# ---------------------------------------------------------------------------

def starter_deck() -> list[Card]:
    """Initial 10-card deck given to every character regardless of class."""
    return [
        _atk("golpe_base",   "Golpe",    1, 6),
        _atk("golpe_base",   "Golpe",    1, 6),
        _atk("golpe_base",   "Golpe",    1, 6),
        _atk("golpe_base",   "Golpe",    1, 6),
        _skl("defender_base","Defender", 1, 5),
        _skl("defender_base","Defender", 1, 5),
        _skl("defender_base","Defender", 1, 5),
        _skl("defender_base","Defender", 1, 5),
        _atk("embate_base",  "Embate",   2, 10),
        _skl("guardia_base", "Guardia",  2, 8),
    ]


# ---------------------------------------------------------------------------
# Acero pool (attack focus)
# ---------------------------------------------------------------------------

_ACERO: list[Callable[[], Card]] = [
    lambda: _atk("a_golpe_ferreo",   "Golpe Férreo",  1,  9),
    lambda: _atk("a_tajo",           "Tajo",          1,  6, draw=1),
    lambda: _atk("a_arremetida",     "Arremetida",    2, 14),
    lambda: _atk("a_furia",          "Furia",         3, 20),
    lambda: _atk("a_punio",          "Puñetazo",      0,  5),
    lambda: _atk("a_golpe_pesado",   "Golpe Pesado",  2, 16),
    lambda: _atk("a_patada",         "Patada",        1,  7),
    lambda: _atk("a_corte_rapido",   "Corte Rápido",  1,  5, draw=1),
    lambda: _atk("a_embestida",      "Embestida",     2, 12),
    lambda: _atk("a_gran_golpe",     "Gran Golpe",    3, 26),
]


# ---------------------------------------------------------------------------
# Escudo pool (defense focus)
# ---------------------------------------------------------------------------

_ESCUDO: list[Callable[[], Card]] = [
    lambda: _skl("e_guardia_solida",  "Guardia Sólida",  1,  8),
    lambda: _skl("e_escudo_solido",   "Escudo Sólido",   1,  5, draw=1),
    lambda: _skl("e_fortaleza",       "Fortaleza",       2, 14),
    lambda: _skl("e_baluarte",        "Baluarte",        3, 22),
    lambda: _skl("e_parada",          "Parada",          0,  4),
    lambda: _skl("e_capa_hierro",     "Capa de Hierro",  2, 11, draw=1),
    lambda: _skl("e_torre",           "Torre",           2, 16),
    lambda: _skl("e_escudo_reactivo", "Escudo Reactivo", 1,  6, draw=1),
    lambda: _skl("e_agilidad",        "Agilidad",        1,  7),
    lambda: _skl("e_gran_muralla",    "Gran Muralla",    3, 28),
]


# ---------------------------------------------------------------------------
# Magia pool (mixed/utility)
# ---------------------------------------------------------------------------

_MAGIA: list[Callable[[], Card]] = [
    lambda: _atk("m_chispa",          "Chispa",           0,  3, draw=1),
    lambda: _atk("m_rayo",            "Rayo",             2, 11),
    lambda: _skl("m_absorcion",       "Absorción",        1,  0, draw=3),
    lambda: _skl("m_impulso",         "Impulso",          1,  6, draw=1),
    lambda: _combo("m_torbellino",    "Torbellino",       2,  8, 5),
    lambda: _skl("m_barrera_magica",  "Barrera Mágica",   2, 10, draw=1),
    lambda: _skl("m_vision",          "Visión",           0,  0, draw=2),
    lambda: _atk("m_hechizo_menor",   "Hechizo Menor",    1,  6),
    lambda: _pwr("m_concentracion",   "Concentración",    1,  draw=2),
    lambda: _combo("m_conjuro",       "Conjuro de Combate", 2, 10, 6),
]


# ---------------------------------------------------------------------------
# Epico pool (rare/powerful)
# ---------------------------------------------------------------------------

_EPICO: list[Callable[[], Card]] = [
    lambda: _atk("ep_golpe_mortal",     "Golpe Mortal",        2, 22),
    lambda: _skl("ep_escudo_impenet",   "Escudo Impenetrable", 2, 22),
    lambda: _combo("ep_tormenta",       "Tormenta",            3, 16, 12),
    lambda: _pwr("ep_poder_oculto",     "Poder Oculto",        1, draw=4),
    lambda: _atk("ep_ejecucion",        "Ejecución",           3, 30),
    lambda: _skl("ep_bastion",          "Bastión",             3, 30),
    lambda: _atk("ep_descarga",         "Descarga",            2, 18, draw=2),
    lambda: _skl("ep_escudo_arcano",    "Escudo Arcano",       2, 14, draw=2),
]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

_POOL: dict[PackTheme, list[Callable[[], Card]]] = {
    PackTheme.ACERO:  _ACERO,
    PackTheme.ESCUDO: _ESCUDO,
    PackTheme.MAGIA:  _MAGIA,
    PackTheme.EPICO:  _EPICO,
}


def card_factories_for_theme(theme: PackTheme) -> list[Callable[[], Card]]:
    """Return all card factories for a given theme."""
    return list(_POOL[theme])


def pack_def_for_theme(theme: PackTheme) -> PackDef:
    for pack in ALL_PACKS:
        if pack.theme == theme:
            return pack
    raise KeyError(theme)
