"""Card pool definitions organised by pack theme and by class.

Two independent axes:
  * **theme** (``PackTheme``) — which pack a card comes in (acero, escudo, magia, epico);
  * **class** (``CardClass``) — who may find it: NEUTRAL cards are for every
    class, WARRIOR / MAGE / ROGUE cards only for that class. Relics can mix
    class pools (``Relic.card_classes``); see ``card_rewards.allowed_card_classes``.

A card's class is set in ``CARD_CLASS_BY_ID`` (edit that table to rebalance).
Each theme keeps at least ``PACK_SIZE`` cards available to every single class
(neutral + own), so a pack never comes up short.

Every public function returns *new* Card instances — callers must not cache the
results across multiple uses, as cards are mutable (stacked_effects, modifiers).
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Iterable

from src.domain.card import Card, CardClass, CardEffect, CardRarity, CardType
from src.domain.chroma import Chroma
from src.domain.entities import WEAK, StatusEffect, add_status
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
    chroma: Chroma | None = None   # golden pack: keep 2 cards (effect_multiplier)


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


def _add_combo(card: Card, *, dmg: int = 0, blk: int = 0, draw: int = 0, mana: int = 0,
               on_play=None, text: str = "") -> Card:
    """Give ``card`` the COMBO keyword: an extra layer if a card was played earlier this turn."""
    card.base_effect.combo = CardEffect(name="Combo", damage=BigValue(dmg), block=BigValue(blk),
                                        draw=draw, mana_gain=mana, on_play=on_play, text=text)
    return card


def _add_singular(card: Card, *, dmg: int = 0, blk: int = 0, draw: int = 0, mana: int = 0,
                  on_play=None, text: str = "") -> Card:
    """Give ``card`` the SINGULAR keyword: an extra layer if the starting deck has no repeats."""
    card.base_effect.singular = CardEffect(name="Singular", damage=BigValue(dmg), block=BigValue(blk),
                                           draw=draw, mana_gain=mana, on_play=on_play, text=text)
    return card


def _add_void(card: Card, *, dmg: int = 0, blk: int = 0, draw: int = 0, mana: int = 0,
              on_play=None, text: str = "") -> Card:
    """Give ``card`` the VOID keyword ("Vacío"): an extra layer if it spends your last mana."""
    card.base_effect.void = CardEffect(name="Vacío", damage=BigValue(dmg), block=BigValue(blk),
                                       draw=draw, mana_gain=mana, on_play=on_play, text=text)
    return card


# ---------------------------------------------------------------------------
# Starter deck
# ---------------------------------------------------------------------------

def _rogue_starter() -> list[Card]:
    """La Pícara: 4 attacks (6 dmg), 4 defenses (6 block) and 1 combo card (9 cards).

    Finta: 1 mana, 4 damage; Combo: +4 block. All class ROGUE, common rarity.
    """
    def stamp(card: Card) -> Card:
        card.card_class = CardClass.ROGUE
        card.rarity = CardRarity.COMMON
        return card
    attacks = [stamp(_atk("punalada_base", "Puñalada", 1, 6)) for _ in range(4)]
    blocks = [stamp(_skl("esquiva_base", "Esquiva", 1, 6)) for _ in range(4)]
    finta = stamp(_add_combo(_atk("finta_base", "Finta", 1, 4), blk=4))
    return attacks + blocks + [finta]


def starter_deck(character_id=None) -> list[Card]:
    """Initial deck for a character (a ``CharacterId``).

    La Pícara has her own 9-card deck (see ``_rogue_starter``); the other classes
    (and no id) get the shared neutral 10-card deck below.
    """
    if character_id is not None and getattr(character_id, "value", None) == "rogue":
        return _rogue_starter()
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
    lambda: _add_combo(_atk("a_tajo", "Tajo", 1, 6, draw=1), dmg=5),
    lambda: _atk("a_arremetida",     "Arremetida",    2, 14),
    lambda: _atk("a_furia",          "Furia",         3, 20),
    lambda: _atk("a_punio",          "Puñetazo",      0,  5),
    lambda: _atk("a_golpe_pesado",   "Golpe Pesado",  2, 16),
    lambda: _atk("a_patada",         "Patada",        1,  7),
    lambda: _add_combo(_atk("a_corte_rapido", "Corte Rápido", 1, 5, draw=1), draw=1),
    lambda: _atk("a_embestida",      "Embestida",     2, 12),
    lambda: _atk("a_gran_golpe",     "Gran Golpe",    3, 26),
    # on_play cards
    lambda: Card(
        id="a_golpe_total", name="Golpe Total", card_type=CardType.ATTACK, cost=2,
        base_effect=CardEffect(name="Golpe Total", hits_all_enemies=True, on_play=_on_golpe_total,
                               text="inflige 10 de daño a todos los enemigos"),
        rarity=CardRarity.RARE,
    ),
    lambda: _add_combo(Card(
        id="a_instinto", name="Instinto", card_type=CardType.ATTACK, cost=1,
        base_effect=CardEffect(name="Instinto", needs_target=True, on_play=_on_instinto,
                               text="inflige 2 de daño por cada carta en tu mano"),
        rarity=CardRarity.UNCOMMON,
    ), dmg=6),
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
    lambda: _add_combo(_skl("e_escudo_reactivo", "Escudo Reactivo", 1, 6, draw=1), mana=1),
    lambda: _add_combo(_skl("e_agilidad", "Agilidad", 1, 7), blk=5),
    lambda: _skl("e_gran_muralla",    "Gran Muralla",    3, 28),
    # on_play cards
    lambda: Card(
        id="e_muro_de_mana", name="Muro de Maná", card_type=CardType.SKILL, cost=1,
        base_effect=CardEffect(name="Muro de Maná", on_play=_on_muro_de_mana,
                               text="gana 5 de escudo por cada maná que te quede"),
        rarity=CardRarity.UNCOMMON,
    ),
    lambda: Card(
        id="e_retribucion", name="Retribución", card_type=CardType.SKILL, cost=1,
        base_effect=CardEffect(name="Retribución", on_play=_on_retribucion,
                               text="gana 2 de escudo por cada carta en el descarte"),
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
    lambda: _add_combo(_combo("m_torbellino", "Torbellino", 2, 8, 5), dmg=4, blk=4),
    lambda: _skl("m_barrera_magica",  "Barrera Mágica",   2, 10, draw=1),
    lambda: _skl("m_vision",          "Visión",           0,  0, draw=2),
    lambda: _atk("m_hechizo_menor",   "Hechizo Menor",    1,  6),
    lambda: _pwr("m_concentracion",   "Concentración",    1,  draw=2),
    lambda: _combo("m_conjuro",       "Conjuro de Combate", 2, 10, 6),
    # on_play cards
    lambda: _add_combo(Card(
        id="m_veneno", name="Veneno", card_type=CardType.SKILL, cost=1,
        base_effect=CardEffect(name="Veneno", needs_target=True, on_play=_on_veneno,
                               text="aplica 3 de Veneno"),
        rarity=CardRarity.UNCOMMON,
    ), on_play=_on_veneno, text="aplica 3 de Veneno más"),
    lambda: Card(
        id="m_vision_del_caos", name="Visión del Caos", card_type=CardType.SKILL, cost=0,
        base_effect=CardEffect(name="Visión del Caos", hits_all_enemies=True, on_play=_on_vision_del_caos,
                               text="inflige 1 de daño a todos por cada carta en tu pila de robo"),
        rarity=CardRarity.COMMON,
    ),
    lambda: Card(
        id="m_grito_de_guerra", name="Grito de Guerra", card_type=CardType.SKILL, cost=1,
        base_effect=CardEffect(name="Grito de Guerra", on_play=_on_grito_de_guerra,
                               text="gana 1 de maná por cada enemigo vivo"),
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
        base_effect=CardEffect(name="Lluvia de Golpes", hits_all_enemies=True, on_play=_on_lluvia_de_golpes,
                               text="inflige 5 de daño a todos por cada ataque en el descarte"),
        rarity=CardRarity.LEGENDARY,
    ),
    lambda: _add_combo(Card(
        id="ep_mazo_impecable", name="Mazo Impecable", card_type=CardType.ATTACK, cost=2,
        base_effect=CardEffect(name="Mazo Impecable", needs_target=True, on_play=_on_mazo_impecable,
                               text="inflige 40 de daño si toda tu mano cuesta 1 o menos"),
        rarity=CardRarity.LEGENDARY,
    ), dmg=12),
    lambda: Card(
        id="ep_tormenta_veneno", name="Tormenta de Veneno", card_type=CardType.SKILL, cost=3,
        base_effect=CardEffect(name="Tormenta de Veneno", hits_all_enemies=True, on_play=_on_tormenta_veneno,
                               text="aplica 5 de Veneno a todos los enemigos"),
        rarity=CardRarity.LEGENDARY,
    ),
]


# ---------------------------------------------------------------------------
# La Pícara — combo / suerte archetype (all ROGUE, see CARD_CLASS_BY_ID)
# ---------------------------------------------------------------------------

def _r(id: str, name: str, ctype: CardType, cost: int, rarity: CardRarity, *, dmg: int = 0,
       blk: int = 0, draw: int = 0, on_play=None, text: str = "", needs_target: bool = False,
       hits_all: bool = False, on_turn_start=None) -> Card:
    return Card(
        id=id, name=name, card_type=ctype, cost=cost, rarity=rarity,
        base_effect=CardEffect(name=name, damage=BigValue(dmg), block=BigValue(blk), draw=draw,
                               on_play=on_play, text=text, needs_target=needs_target,
                               hits_all_enemies=hits_all, on_turn_start=on_turn_start),
    )


_A, _S, _P = CardType.ATTACK, CardType.SKILL, CardType.POWER
_C, _U, _RA, _E, _L = (CardRarity.COMMON, CardRarity.UNCOMMON, CardRarity.RARE,
                       CardRarity.EPIC, CardRarity.LEGENDARY)


def hidden_dagger() -> Card:
    """Token "Daga Oculta": played by itself when drawn (4 damage to a random enemy), then gone."""
    card = _r("t_daga_oculta", "Daga Oculta", _A, 0, _C, on_play=_on_random_hit_4,
              text="al robarla: inflige 4 de daño a un enemigo al azar")
    card.play_on_draw = True
    return card


_ROGUE_ACERO: list[Callable[[], Card]] = [
    lambda: _add_combo(_r("r_estocada_oportuna", "Estocada Oportuna", _A, 1, _E, dmg=3), draw=1),
    lambda: _r("r_pinchazo", "Pinchazo", _A, 0, _C, dmg=3),
    lambda: _r("r_golpe_desesperado", "Golpe Desesperado", _A, 1, _U, dmg=12,
               on_play=_on_discard_random, text="descarta una carta al azar de tu mano"),
    lambda: _r("r_lluvia_de_dagas", "Lluvia de Dagas", _A, 2, _C, on_play=_on_two_random_10,
               text="inflige 10 de daño a 2 enemigos al azar", hits_all=True),
    lambda: _r("r_golpe_de_gracia", "Golpe de Gracia", _A, 1, _U, dmg=8,
               on_play=_on_refund_on_kill, text="si lo matas, recupera 1 de maná"),
    lambda: _r("r_corte_y_guardia", "Corte y Guardia", _A, 1, _C, dmg=3, blk=3),
    lambda: _add_combo(_r("r_cuchillada_errante", "Cuchillada Errante", _A, 1, _C,
                          on_play=_on_random_hit_4, text="inflige 4 de daño a un enemigo al azar",
                          hits_all=True),
                       on_play=_on_random_hit_4, text="hazlo de nuevo"),
    lambda: _add_singular(_r("r_abanico_de_cuchillas", "Abanico de Cuchillas", _A, 2, _E,
                             on_play=_on_all_hit_5, text="inflige 5 de daño a todos los enemigos",
                             hits_all=True), blk=5, draw=1),
]

_ROGUE_ESCUDO: list[Callable[[], Card]] = [
    lambda: _r("r_paso_atras", "Paso Atrás", _S, 0, _C, blk=3),
    lambda: _add_combo(_r("r_guardia_evasiva", "Guardia Evasiva", _S, 2, _U, blk=10),
                       on_play=_on_weaken_all, text="los enemigos infligen 25% menos de daño este turno"),
    lambda: _r("r_muro_de_humo", "Muro de Humo", _S, 2, _U, blk=14),
]

_ROGUE_MAGIA: list[Callable[[], Card]] = [
    lambda: _r("r_preparacion", "Preparación", _S, 0, _E, on_play=_on_next_card_cheaper,
               text="la siguiente carta que juegues este turno cuesta 1 menos"),
    lambda: _r("r_rebuscar", "Rebuscar", _S, 2, _RA, on_play=_on_draw_one_of_each_type,
               text="roba un poder, un ataque y una habilidad"),
    lambda: _r("r_astucia", "Astucia", _S, 1, _E, draw=2),
    lambda: _add_combo(_r("r_dagas_ocultas", "Dagas Ocultas", _S, 1, _RA, on_play=_on_hide_two_daggers,
                          text="mete 2 Dagas Ocultas en tu pila de robo"),
                       on_play=_on_hide_one_dagger, text="mete 3 en vez de 2"),
    lambda: _r("r_afilar", "Afilar", _S, 1, _C, on_play=_on_next_damage_plus_6,
               text="tu siguiente carta que haga daño este turno inflige 6 más"),
    lambda: _r("r_reflejos", "Reflejos", _P, 1, _U, on_play=_on_gain_dexterity,
               text="gana 1 de destreza este combate"),
    lambda: _r("r_danza_de_sombras", "Danza de Sombras", _P, 2, _E, on_play=_on_combo_always,
               text="este combate, tus Combos se activan sin jugar otra carta antes"),
]

_ROGUE_EPICO: list[Callable[[], Card]] = [
    lambda: _r("r_ritmo_letal", "Ritmo Letal", _P, 2, _L, on_play=_on_first_card_cheaper,
               text="este combate, la primera carta de cada turno cuesta 1 menos"),
    lambda: _add_singular(_r("r_tormenta_de_acero", "Tormenta de Acero", _P, 1, _L,
                             on_turn_start=_on_turn_blades,
                             text="al inicio de cada turno, inflige 3 de daño a todos los enemigos"),
                          text="5 de daño en vez de 3"),
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


# ROGUE effects

def _alive(state) -> list:
    return [e for e in state.enemies if e.is_alive]


def _on_random_hit_4(state) -> None:
    """4 damage to a random living enemy."""
    alive = _alive(state)
    if alive:
        _apply_block_absorbed_damage(random.choice(alive), 4)


def _on_two_random_10(state) -> None:
    """10 damage to 2 different random enemies (or the only one left)."""
    for e in random.sample(_alive(state), min(2, len(_alive(state)))):
        _apply_block_absorbed_damage(e, 10)


def _on_all_hit_5(state) -> None:
    for e in _alive(state):
        _apply_block_absorbed_damage(e, 5)


def _on_discard_random(state) -> None:
    """Discard a random card from the hand (this card has already left it)."""
    if state.hand.cards:
        card = state.hand.cards.pop(random.randrange(state.hand.count))
        state.discard_pile.cards.append(card)


def _on_refund_on_kill(state) -> None:
    """If this card's damage killed the target, gain 1 mana back."""
    idx = state.targeted_enemy_index
    if idx is not None and idx < len(state.enemies) and not state.enemies[idx].is_alive:
        state.mana.gain(1)


def _on_weaken_all(state) -> None:
    """Every living enemy is Débil for its next action (25 % less damage)."""
    for e in _alive(state):
        add_status(e.status_effects, WEAK, 1, is_buff=False)


def _on_next_card_cheaper(state) -> None:
    state.next_card_discount += 1


def _on_first_card_cheaper(state) -> None:
    state.first_card_discount += 1


def _on_next_damage_plus_6(state) -> None:
    state.next_damage_bonus += 6


def _on_combo_always(state) -> None:
    state.combo_always = True


def _on_gain_dexterity(state) -> None:
    state.player.dexterity += 1


def _on_draw_one_of_each_type(state) -> None:
    """Take the top Power, Attack and Skill of the draw pile into the hand (if any)."""
    for ctype in (CardType.POWER, CardType.ATTACK, CardType.SKILL):
        if state.hand.is_full:
            return
        for i in range(state.draw_pile.count - 1, -1, -1):     # top of the pile = end of the list
            if state.draw_pile.cards[i].card_type is ctype:
                state.hand.cards.append(state.draw_pile.cards.pop(i))
                break


def _hide_daggers(state, n: int) -> None:
    for _ in range(n):
        state.draw_pile.cards.insert(random.randint(0, state.draw_pile.count), hidden_dagger())


def _on_hide_two_daggers(state) -> None:
    _hide_daggers(state, 2)


def _on_hide_one_dagger(state) -> None:
    _hide_daggers(state, 1)


def _on_turn_blades(state) -> None:
    """Tormenta de Acero: at turn start, 3 damage to all enemies (Singular deck: 5)."""
    dmg = 5 if state.singular_deck else 3
    for e in _alive(state):
        _apply_block_absorbed_damage(e, dmg)


# ---------------------------------------------------------------------------
# Classes
# ---------------------------------------------------------------------------

PACK_SIZE: int = 5

CARD_CLASS_LABEL: dict[CardClass, str] = {
    CardClass.NEUTRAL: "Neutral",
    CardClass.WARRIOR: "La Guerrera",
    CardClass.MAGE:    "El Mago",
    CardClass.ROGUE:   "La Pícara",
}

_N, _W, _M, _R = CardClass.NEUTRAL, CardClass.WARRIOR, CardClass.MAGE, CardClass.ROGUE

# Class of every pool card, by card id. Cards missing here are NEUTRAL
# (the starter deck is neutral too). Per theme: neutral + each class >= PACK_SIZE.
CARD_CLASS_BY_ID: dict[str, CardClass] = {
    # Acero — neutral: basic blows
    "a_punio": _N, "a_patada": _N, "a_golpe_ferreo": _N,
    "a_golpe_pesado": _W, "a_gran_golpe": _W, "a_golpe_total": _W,
    "a_furia": _M, "a_arremetida": _M, "a_embestida": _M,
    "a_tajo": _R, "a_corte_rapido": _R, "a_instinto": _R,
    # Escudo
    "e_parada": _N, "e_guardia_solida": _N, "e_escudo_solido": _N, "e_fortaleza": _N,
    "e_baluarte": _W, "e_gran_muralla": _W, "e_torre": _W, "e_retribucion": _W,
    "e_muro_de_mana": _M, "e_capa_hierro": _M,
    "e_agilidad": _R, "e_escudo_reactivo": _R,
    # Magia
    "m_vision": _N, "m_impulso": _N, "m_absorcion": _N,
    "m_grito_de_guerra": _W, "m_conjuro": _W,
    "m_chispa": _M, "m_rayo": _M, "m_hechizo_menor": _M, "m_concentracion": _M,
    "m_barrera_magica": _M, "m_vision_del_caos": _M,
    "m_veneno": _R, "m_torbellino": _R,
    # Épico
    "ep_poder_oculto": _N, "ep_golpe_mortal": _N,
    "ep_escudo_impenet": _W, "ep_bastion": _W, "ep_ejecucion": _W,
    "ep_tormenta": _M, "ep_descarga": _M, "ep_escudo_arcano": _M,
    "ep_lluvia_de_golpes": _R, "ep_tormenta_veneno": _R, "ep_mazo_impecable": _R,
    # La Pícara (combo / suerte)
    "r_estocada_oportuna": _R, "r_pinchazo": _R, "r_golpe_desesperado": _R, "r_lluvia_de_dagas": _R,
    "r_golpe_de_gracia": _R, "r_corte_y_guardia": _R, "r_cuchillada_errante": _R,
    "r_paso_atras": _R, "r_guardia_evasiva": _R, "r_muro_de_humo": _R,
    "r_preparacion": _R, "r_rebuscar": _R, "r_astucia": _R, "r_dagas_ocultas": _R, "r_afilar": _R,
    "r_reflejos": _R, "r_danza_de_sombras": _R,
    "r_abanico_de_cuchillas": _R, "r_ritmo_letal": _R, "r_tormenta_de_acero": _R,
}


@dataclass(frozen=True)
class CardFactory:
    """Callable that builds a fresh card and stamps its class and theme."""
    card_id: str
    card_class: CardClass
    theme: PackTheme
    build: Callable[[], Card]

    def __call__(self) -> Card:
        card = self.build()
        card.card_class = self.card_class
        return card

    @property
    def rarity(self) -> CardRarity:
        """Tier of the card this factory builds (used for luck-weighted picks)."""
        return _factory_rarity(self.build)


_RARITY_CACHE: dict[Callable[[], Card], CardRarity] = {}


def _factory_rarity(build: Callable[[], Card]) -> CardRarity:
    if build not in _RARITY_CACHE:
        _RARITY_CACHE[build] = build().rarity or CardRarity.COMMON
    return _RARITY_CACHE[build]


def class_for_character(character_id) -> CardClass:
    """CardClass owned by a ``CharacterId`` (their values match)."""
    return CardClass(character_id.value)


def _factories(theme: PackTheme, raw: list[Callable[[], Card]]) -> list[CardFactory]:
    out = []
    for build in raw:
        card_id = build().id
        out.append(CardFactory(card_id, CARD_CLASS_BY_ID.get(card_id, CardClass.NEUTRAL), theme, build))
    return out


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

_POOL: dict[PackTheme, list[CardFactory]] = {
    PackTheme.ACERO:  _factories(PackTheme.ACERO, _ACERO + _ROGUE_ACERO),
    PackTheme.ESCUDO: _factories(PackTheme.ESCUDO, _ESCUDO + _ROGUE_ESCUDO),
    PackTheme.MAGIA:  _factories(PackTheme.MAGIA, _MAGIA + _ROGUE_MAGIA),
    PackTheme.EPICO:  _factories(PackTheme.EPICO, _EPICO + _ROGUE_EPICO),
}


def card_factories_for_theme(theme: PackTheme,
                             classes: Iterable[CardClass] | None = None) -> list[CardFactory]:
    """Card factories of a theme; with ``classes``, only cards of those classes."""
    pool = _POOL[theme]
    if classes is None:
        return list(pool)
    allowed = frozenset(classes)
    return [f for f in pool if f.card_class in allowed]


def card_factories_for_classes(classes: Iterable[CardClass]) -> list[CardFactory]:
    """Every card factory (all themes) whose class is in ``classes``."""
    allowed = frozenset(classes)
    return [f for theme in PackTheme for f in _POOL[theme] if f.card_class in allowed]


def pack_def_for_theme(theme: PackTheme) -> PackDef:
    for pack in ALL_PACKS:
        if pack.theme == theme:
            return pack
    raise KeyError(theme)
