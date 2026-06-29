"""Card pool definitions organised by pack theme.

Every public function returns *new* Card instances — callers must not cache the
results across multiple uses, as cards are mutable (stacked_effects, modifiers).
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Callable

from src.domain.card import Card, CardEffect, CardRarity, CardType
from src.domain.entities import StatusEffect
from src.domain.numbers import BigValue


def _rar(cost: int, *, epic: bool = False, legendary: bool = False) -> CardRarity:
    if legendary:
        return CardRarity.LEGENDARY
    if epic:
        return CardRarity.EPIC
    if cost == 0:
        return CardRarity.COMMON
    if cost == 1:
        return CardRarity.UNCOMMON
    if cost == 2:
        return CardRarity.RARE
    return CardRarity.EPIC


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

def _atk(id: str, name: str, cost: int, dmg: int, draw: int = 0, *,
         legendary: bool = False) -> Card:
    return Card(
        id=id, name=name, card_type=CardType.ATTACK, cost=cost,
        base_effect=CardEffect(name=name, damage=BigValue(dmg), draw=draw),
        rarity=_rar(cost, legendary=legendary),
    )


def _skl(id: str, name: str, cost: int, blk: int, draw: int = 0, *,
         legendary: bool = False) -> Card:
    return Card(
        id=id, name=name, card_type=CardType.SKILL, cost=cost,
        base_effect=CardEffect(name=name, block=BigValue(blk), draw=draw),
        rarity=_rar(cost, legendary=legendary),
    )


def _combo(id: str, name: str, cost: int, dmg: int, blk: int, draw: int = 0, *,
           legendary: bool = False) -> Card:
    return Card(
        id=id, name=name, card_type=CardType.ATTACK, cost=cost,
        base_effect=CardEffect(name=name, damage=BigValue(dmg), block=BigValue(blk), draw=draw),
        rarity=_rar(cost, legendary=legendary),
    )


def _pwr(id: str, name: str, cost: int, draw: int = 0, *,
         legendary: bool = False) -> Card:
    return Card(
        id=id, name=name, card_type=CardType.POWER, cost=cost,
        base_effect=CardEffect(name=name, draw=draw),
        rarity=_rar(cost, legendary=legendary),
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
    # on_play cards
    lambda: Card(
        id="a_golpe_total", name="Golpe Total", card_type=CardType.ATTACK, cost=2,
        base_effect=CardEffect(name="Golpe Total", on_play=_on_golpe_total),
        rarity=CardRarity.RARE,
    ),
    lambda: Card(
        id="a_instinto", name="Instinto", card_type=CardType.ATTACK, cost=1,
        base_effect=CardEffect(name="Instinto", needs_target=True, on_play=_on_instinto),
        rarity=CardRarity.UNCOMMON,
    ),
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
    # on_play cards
    lambda: Card(
        id="e_muro_de_mana", name="Muro de Maná", card_type=CardType.SKILL, cost=1,
        base_effect=CardEffect(name="Muro de Maná", on_play=_on_muro_de_mana),
        rarity=CardRarity.UNCOMMON,
    ),
    lambda: Card(
        id="e_retribucion", name="Retribución", card_type=CardType.SKILL, cost=1,
        base_effect=CardEffect(name="Retribución", on_play=_on_retribucion),
        rarity=CardRarity.UNCOMMON,
    ),
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
    # on_play cards
    lambda: Card(
        id="m_veneno", name="Veneno", card_type=CardType.SKILL, cost=1,
        base_effect=CardEffect(name="Veneno", needs_target=True, on_play=_on_veneno),
        rarity=CardRarity.UNCOMMON,
    ),
    lambda: Card(
        id="m_vision_del_caos", name="Visión del Caos", card_type=CardType.SKILL, cost=0,
        base_effect=CardEffect(name="Visión del Caos", on_play=_on_vision_del_caos),
        rarity=CardRarity.COMMON,
    ),
    lambda: Card(
        id="m_grito_de_guerra", name="Grito de Guerra", card_type=CardType.SKILL, cost=1,
        base_effect=CardEffect(name="Grito de Guerra", on_play=_on_grito_de_guerra),
        rarity=CardRarity.UNCOMMON,
    ),
]


# ---------------------------------------------------------------------------
# Epico pool (rare/powerful)
# ---------------------------------------------------------------------------

_EPICO: list[Callable[[], Card]] = [
    lambda: _atk("ep_golpe_mortal",     "Golpe Mortal",        2, 22,       legendary=True),
    lambda: _skl("ep_escudo_impenet",   "Escudo Impenetrable", 2, 22,       legendary=True),
    lambda: _combo("ep_tormenta",       "Tormenta",            3, 16, 12,   legendary=True),
    lambda: _pwr("ep_poder_oculto",     "Poder Oculto",        1, draw=4,   legendary=True),
    lambda: _atk("ep_ejecucion",        "Ejecución",           3, 30,       legendary=True),
    lambda: _skl("ep_bastion",          "Bastión",             3, 30,       legendary=True),
    lambda: _atk("ep_descarga",         "Descarga",            2, 18, draw=2, legendary=True),
    lambda: _skl("ep_escudo_arcano",    "Escudo Arcano",       2, 14, draw=2, legendary=True),
    # on_play cards
    lambda: Card(
        id="ep_lluvia_de_golpes", name="Lluvia de Golpes", card_type=CardType.ATTACK, cost=3,
        base_effect=CardEffect(name="Lluvia de Golpes", on_play=_on_lluvia_de_golpes),
        rarity=CardRarity.LEGENDARY,
    ),
    lambda: Card(
        id="ep_mazo_impecable", name="Mazo Impecable", card_type=CardType.ATTACK, cost=2,
        base_effect=CardEffect(name="Mazo Impecable", needs_target=True, on_play=_on_mazo_impecable),
        rarity=CardRarity.LEGENDARY,
    ),
    lambda: Card(
        id="ep_tormenta_veneno", name="Tormenta de Veneno", card_type=CardType.SKILL, cost=3,
        base_effect=CardEffect(name="Tormenta de Veneno", on_play=_on_tormenta_veneno),
        rarity=CardRarity.LEGENDARY,
    ),
]


# ---------------------------------------------------------------------------
# on_play effect functions (receive full CombatState, called after base
# damage/block/mana have been applied)
# ---------------------------------------------------------------------------

def _apply_block_absorbed_damage(enemy, dmg: int) -> None:
    absorbed = min(enemy.block, dmg)
    enemy.block = max(0, enemy.block - absorbed)
    enemy.current_hp = max(0, enemy.current_hp - (dmg - absorbed))


# ACERO effects

def _on_golpe_total(state) -> None:
    """10 damage to ALL enemies."""
    for e in state.enemies:
        if e.is_alive:
            _apply_block_absorbed_damage(e, 10)


def _on_instinto(state) -> None:
    """2 damage per card remaining in hand to the targeted enemy."""
    idx = state.targeted_enemy_index
    if idx is not None and idx < len(state.enemies) and state.enemies[idx].is_alive:
        dmg = state.hand.count * 2
        _apply_block_absorbed_damage(state.enemies[idx], dmg)


# ESCUDO effects

def _on_muro_de_mana(state) -> None:
    """Block = current mana × 5 (after paying this card's cost)."""
    state.player.block += state.mana.current * 5


def _on_retribucion(state) -> None:
    """Gain 2 block for each card in the discard pile."""
    state.player.block += state.discard_pile.count * 2


# MAGIA effects

def _on_veneno(state) -> None:
    """Apply 3 stacks of POISON to the targeted enemy."""
    idx = state.targeted_enemy_index
    if idx is not None and idx < len(state.enemies) and state.enemies[idx].is_alive:
        state.enemies[idx].status_effects.append(StatusEffect("Veneno", 3, is_buff=False))


def _on_vision_del_caos(state) -> None:
    """Deal 1 damage per card in the draw pile to ALL enemies."""
    dmg = state.draw_pile.count
    if dmg == 0:
        return
    for e in state.enemies:
        if e.is_alive:
            _apply_block_absorbed_damage(e, dmg)


def _on_grito_de_guerra(state) -> None:
    """Gain 1 mana for each enemy alive."""
    count = sum(1 for e in state.enemies if e.is_alive)
    state.mana.gain(count)


# EPICO effects

def _on_lluvia_de_golpes(state) -> None:
    """5 damage to ALL enemies per attack card in the discard pile."""
    atk_in_discard = sum(1 for c in state.discard_pile.cards if c.card_type == CardType.ATTACK)
    dmg = atk_in_discard * 5
    if dmg == 0:
        return
    for e in state.enemies:
        if e.is_alive:
            _apply_block_absorbed_damage(e, dmg)


def _on_mazo_impecable(state) -> None:
    """Deal 40 damage to target if every card in hand costs ≤ 1 mana."""
    if not all(c.cost <= 1 for c in state.hand.cards):
        return
    idx = state.targeted_enemy_index
    if idx is not None and idx < len(state.enemies) and state.enemies[idx].is_alive:
        _apply_block_absorbed_damage(state.enemies[idx], 40)


def _on_tormenta_veneno(state) -> None:
    """Apply POISON 5 to ALL enemies."""
    for e in state.enemies:
        if e.is_alive:
            e.status_effects.append(StatusEffect("Veneno", 5, is_buff=False))


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
