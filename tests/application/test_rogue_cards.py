"""La Pícara's card set and the mechanics it needs. No pygame."""
from __future__ import annotations

import random

import pytest

from src.application.drawing import draw_cards, draw_one
from src.application.end_turn import end_player_turn
from src.application.play_card import TargetKind, play_card, target_kind
from src.domain.card import Card, CardClass, CardEffect, CardType
from src.domain.card_pool import card_factories_for_classes, hidden_dagger
from src.domain.card_upgrade import apply_upgrade, can_upgrade
from src.domain.chroma import Chroma
from src.domain.entities import WEAK, Enemy, Intent, IntentType, StatusEffect, weakened
from src.domain.keywords import Keyword
from src.domain.numbers import BigValue
from src.domain.rarity import Rarity
from tests.application.test_play_card import _make_state

ROGUE_IDS = [
    "r_estocada_oportuna", "r_pinchazo", "r_golpe_desesperado", "r_lluvia_de_dagas",
    "r_golpe_de_gracia", "r_corte_y_guardia", "r_cuchillada_errante", "r_abanico_de_cuchillas",
    "r_paso_atras", "r_guardia_evasiva", "r_muro_de_humo",
    "r_preparacion", "r_rebuscar", "r_astucia", "r_dagas_ocultas", "r_afilar", "r_reflejos",
    "r_danza_de_sombras", "r_ritmo_letal", "r_tormenta_de_acero",
]


def _get(card_id: str) -> Card:
    return next(f for f in card_factories_for_classes(set(CardClass)) if f.card_id == card_id)()


def _plain(cost=1, dmg=1, cid="p", ctype=CardType.ATTACK):
    return Card(id=cid, name=cid, card_type=ctype, cost=cost,
                base_effect=CardEffect(name=cid, damage=BigValue(dmg)))


def _enemy(hp=50, eid="e", intent=None):
    return Enemy(id=eid, name="E", max_hp=hp, current_hp=hp,
                 intent=intent or Intent(IntentType.BLOCK, 0))


class TestPool:
    def test_twenty_rogue_cards(self):
        pool = {f.card_id: f for f in card_factories_for_classes({CardClass.ROGUE})}
        for cid in ROGUE_IDS:
            assert pool[cid].card_class is CardClass.ROGUE

    def test_not_for_other_classes(self):
        ids = {f.card_id for f in card_factories_for_classes({CardClass.NEUTRAL, CardClass.MAGE,
                                                               CardClass.WARRIOR})}
        assert not ids & set(ROGUE_IDS)

    @pytest.mark.parametrize("cid, cost, rarity", [
        ("r_estocada_oportuna", 1, Rarity.EPIC), ("r_preparacion", 0, Rarity.EPIC),
        ("r_rebuscar", 2, Rarity.RARE), ("r_pinchazo", 0, Rarity.COMMON),
        ("r_paso_atras", 0, Rarity.COMMON), ("r_golpe_desesperado", 1, Rarity.UNCOMMON),
        ("r_lluvia_de_dagas", 2, Rarity.COMMON), ("r_abanico_de_cuchillas", 2, Rarity.EPIC),
        ("r_golpe_de_gracia", 1, Rarity.UNCOMMON), ("r_ritmo_letal", 2, Rarity.LEGENDARY),
        ("r_danza_de_sombras", 2, Rarity.EPIC), ("r_guardia_evasiva", 2, Rarity.UNCOMMON),
        ("r_astucia", 1, Rarity.EPIC), ("r_tormenta_de_acero", 1, Rarity.LEGENDARY),
        ("r_corte_y_guardia", 1, Rarity.COMMON), ("r_afilar", 1, Rarity.COMMON),
        ("r_cuchillada_errante", 1, Rarity.COMMON),
    ])
    def test_cost_and_rarity(self, cid, cost, rarity):
        c = _get(cid)
        assert (c.cost, c.rarity) == (cost, rarity)

    def test_powers(self):
        for cid in ("r_ritmo_letal", "r_danza_de_sombras", "r_reflejos", "r_tormenta_de_acero"):
            assert _get(cid).card_type is CardType.POWER

    @pytest.mark.parametrize("cid", ROGUE_IDS)
    def test_every_card_has_readable_effect_and_can_be_upgraded(self, cid):
        c = _get(cid)
        assert c.total_damage() or c.total_block() or c.total_draw() or any(
            fx.text for fx in c.all_effects())
        assert can_upgrade(c) and apply_upgrade(c)


class TestSimpleCards:
    def test_pinchazo_and_paso_atras_are_free(self):
        state = _make_state([_get("r_pinchazo"), _get("r_paso_atras")], mana_current=0)
        assert play_card(state, 0, 0).success and state.enemies[0].current_hp == 47
        assert play_card(state, 0).success and state.player.block == 3

    def test_corte_y_guardia(self):
        state = _make_state([_get("r_corte_y_guardia")])
        play_card(state, 0, 0)
        assert state.enemies[0].current_hp == 47 and state.player.block == 3

    def test_muro_de_humo(self):
        state = _make_state([_get("r_muro_de_humo")])
        play_card(state, 0)
        assert state.player.block == 14

    def test_astucia_draws_two(self):
        state = _make_state([_get("r_astucia")], draw_cards=[_plain(cid=f"d{i}") for i in range(4)])
        play_card(state, 0)
        assert state.hand.count == 2

    def test_estocada_combo_draws(self):
        state = _make_state([_plain(cost=0), _get("r_estocada_oportuna")], draw_cards=[_plain(cid="d")])
        play_card(state, 0, 0)
        assert play_card(state, 0, 0).combo and state.hand.count == 1


class TestRandomDamage:
    def test_cuchillada_once_then_twice_with_combo(self):
        state = _make_state([_get("r_cuchillada_errante")])
        play_card(state, 0)
        assert state.enemies[0].current_hp == 46
        state = _make_state([_plain(cost=0), _get("r_cuchillada_errante")])
        play_card(state, 0, 0)
        play_card(state, 0)
        assert state.enemies[0].current_hp == 50 - 1 - 8

    def test_lluvia_de_dagas_two_different_enemies(self):
        state = _make_state([_get("r_lluvia_de_dagas")])
        state.enemies = [_enemy(eid="a"), _enemy(eid="b"), _enemy(eid="c")]
        play_card(state, 0)
        assert sorted(e.current_hp for e in state.enemies) == [40, 40, 50]

    def test_lluvia_de_dagas_single_enemy(self):
        state = _make_state([_get("r_lluvia_de_dagas")])
        play_card(state, 0)
        assert state.enemies[0].current_hp == 40

    def test_random_cards_show_all_enemies_as_target(self):
        assert target_kind(_get("r_cuchillada_errante")) is TargetKind.ALL_ENEMIES
        assert target_kind(_get("r_lluvia_de_dagas")) is TargetKind.ALL_ENEMIES

    def test_abanico_hits_all_and_singular(self):
        state = _make_state([_get("r_abanico_de_cuchillas")], draw_cards=[_plain(cid="d")])
        state.enemies = [_enemy(eid="a"), _enemy(eid="b")]
        state.singular_deck = True
        play_card(state, 0)
        assert [e.current_hp for e in state.enemies] == [45, 45]
        assert state.player.block == 5 and state.hand.count == 1


class TestSpecialCards:
    def test_golpe_desesperado_discards_one_random_card(self):
        state = _make_state([_get("r_golpe_desesperado"), _plain(cid="x"), _plain(cid="y")])
        play_card(state, 0, 0)
        assert state.enemies[0].current_hp == 38
        assert state.hand.count == 1 and state.discard_pile.count == 2

    def test_golpe_desesperado_empty_hand_is_safe(self):
        state = _make_state([_get("r_golpe_desesperado")])
        assert play_card(state, 0, 0).success

    def test_golpe_de_gracia_refunds_on_kill(self):
        state = _make_state([_get("r_golpe_de_gracia")], enemy_hp=8, mana_current=1)
        play_card(state, 0, 0)
        assert not state.enemies[0].is_alive and state.mana.current == 1

    def test_golpe_de_gracia_no_kill_no_refund(self):
        state = _make_state([_get("r_golpe_de_gracia")], enemy_hp=30, mana_current=1)
        play_card(state, 0, 0)
        assert state.mana.current == 0

    def test_rebuscar_takes_one_of_each_type(self):
        power = _plain(cid="pw", ctype=CardType.POWER)
        skill = _plain(cid="sk", ctype=CardType.SKILL)
        attacks = [_plain(cid=f"a{i}") for i in range(3)]
        state = _make_state([_get("r_rebuscar")], draw_cards=[power, *attacks, skill])
        play_card(state, 0)
        assert {c.id for c in state.hand.cards} == {"pw", "sk", "a2"}
        assert state.draw_pile.count == 2

    def test_rebuscar_missing_types(self):
        state = _make_state([_get("r_rebuscar")], draw_cards=[_plain(cid="a")])
        play_card(state, 0)
        assert [c.id for c in state.hand.cards] == ["a"]


class TestNextCardModifiers:
    def test_preparacion_next_card_costs_one_less(self):
        state = _make_state([_get("r_preparacion"), _plain(cost=2), _plain(cost=2, cid="q")], mana_current=2)
        play_card(state, 0)
        assert state.card_cost(state.hand.cards[0]) == 1
        play_card(state, 0, 0)
        assert state.mana.current == 1
        assert state.card_cost(state.hand.cards[0]) == 2     # only the next card

    def test_discount_expires_at_end_of_turn(self):
        state = _make_state([_get("r_preparacion")], draw_cards=[_plain(cid=f"d{i}") for i in range(10)])
        play_card(state, 0)
        end_player_turn(state)
        assert state.next_card_discount == 0

    def test_cost_never_below_zero(self):
        state = _make_state([])
        state.next_card_discount = 5
        assert state.card_cost(_plain(cost=1)) == 0

    def test_afilar_next_damaging_card(self):
        state = _make_state([_get("r_afilar"), _get("r_paso_atras"), _plain(cost=0, dmg=2)])
        play_card(state, 0)
        play_card(state, 0)                     # block card: bonus kept
        assert state.next_damage_bonus == 6
        play_card(state, 0, 0)
        assert state.enemies[0].current_hp == 50 - 8 and state.next_damage_bonus == 0


class TestWeak:
    def test_weakened_math(self):
        fx = [StatusEffect(WEAK, 1, False)]
        assert weakened(20, fx) == 15 and weakened(10, fx) == 7 and weakened(10, []) == 10

    def test_guardia_evasiva_combo_weakens_enemies_for_their_turn(self):
        state = _make_state([_plain(cost=0), _get("r_guardia_evasiva")], mana_current=2,
                            draw_cards=[_plain(cid=f"d{i}") for i in range(10)])
        state.enemies[0].intent = Intent(IntentType.ATTACK, 40)
        play_card(state, 0, 0)
        play_card(state, 0)
        assert any(se.name == WEAK for se in state.enemies[0].status_effects)
        state.player.current_hp = 100
        end_player_turn(state)
        assert state.player.current_hp == 100 - (30 - 10)       # 40*0.75=30, 10 block
        assert not any(se.name == WEAK for se in state.enemies[0].status_effects)

    def test_without_combo_no_weak(self):
        state = _make_state([_get("r_guardia_evasiva")], mana_current=2)
        play_card(state, 0)
        assert state.player.block == 10 and not state.enemies[0].status_effects


@pytest.fixture
def passive_enemies(monkeypatch):
    """Enemies never attack or block, so damage numbers stay exact across turns."""
    from src.application import end_turn
    monkeypatch.setattr(end_turn, "_roll_intent", lambda enemy: Intent(IntentType.BLOCK, 0))


class TestPowers:
    def test_reflejos_dexterity(self):
        state = _make_state([_get("r_reflejos"), _get("r_paso_atras")])
        play_card(state, 0)
        play_card(state, 0)
        assert state.player.dexterity == 1 and state.player.block == 4
        assert state.active_powers[0].id == "r_reflejos"

    def test_danza_de_sombras_combo_always(self):
        state = _make_state([_get("r_danza_de_sombras")], mana_current=2,
                            draw_cards=[_plain(cid=f"d{i}") for i in range(10)])
        play_card(state, 0)
        end_player_turn(state)
        assert state.cards_played_this_turn == 0 and state.combo_active
        state.hand.cards = [_get("r_estocada_oportuna")]
        assert play_card(state, 0, 0).combo

    def test_ritmo_letal_first_card_each_turn(self):
        state = _make_state([_get("r_ritmo_letal")], mana_current=2,
                            draw_cards=[_plain(cost=1, cid=f"d{i}") for i in range(10)])
        play_card(state, 0)
        end_player_turn(state)
        first = state.hand.cards[0]
        assert state.card_cost(first) == 0
        play_card(state, 0, 0)
        assert state.card_cost(state.hand.cards[0]) == 1

    @pytest.mark.parametrize("singular, dmg", [(False, 3), (True, 5)])
    def test_tormenta_de_acero_each_turn(self, singular, dmg, passive_enemies):
        state = _make_state([_get("r_tormenta_de_acero")], draw_cards=[_plain(cid=f"d{i}") for i in range(20)])
        state.singular_deck = singular
        state.enemies = [_enemy(eid="a"), _enemy(eid="b")]
        play_card(state, 0)
        assert [e.current_hp for e in state.enemies] == [50, 50]
        end_player_turn(state)
        end_player_turn(state)
        assert [e.current_hp for e in state.enemies] == [50 - 2 * dmg] * 2

    def test_golden_power_triggers_twice(self, passive_enemies):
        c = _get("r_tormenta_de_acero")
        c.chroma = Chroma.GOLDEN
        state = _make_state([c], draw_cards=[_plain(cid=f"d{i}") for i in range(10)])
        play_card(state, 0)
        end_player_turn(state)
        assert state.enemies[0].current_hp == 50 - 6

    def test_tormenta_has_singular_keyword(self):
        assert Keyword.SINGULAR in _get("r_tormenta_de_acero").keywords()


class TestHiddenDaggers:
    def test_token(self):
        d = hidden_dagger()
        assert d.play_on_draw and d.cost == 0

    def test_play_on_draw_hits_and_disappears(self):
        state = _make_state([], draw_cards=[hidden_dagger()])
        drawn = draw_one(state)
        assert drawn is not None and state.hand.count == 0
        assert state.enemies[0].current_hp == 46
        assert state.discard_pile.count == 0 and state.draw_pile.count == 0

    def test_dagas_ocultas_two_and_three_with_combo(self):
        state = _make_state([_get("r_dagas_ocultas")])
        play_card(state, 0)
        assert sum(c.id == "t_daga_oculta" for c in state.draw_pile.cards) == 2
        state = _make_state([_plain(cost=0), _get("r_dagas_ocultas")])
        play_card(state, 0, 0)
        play_card(state, 0)
        assert sum(c.id == "t_daga_oculta" for c in state.draw_pile.cards) == 3

    def test_drawing_them_at_turn_start(self, passive_enemies):
        state = _make_state([_get("r_dagas_ocultas")])
        play_card(state, 0)
        state.enemies[0].intent = Intent(IntentType.BLOCK, 0)
        end_player_turn(state)
        assert state.enemies[0].current_hp == 50 - 8
        assert not any(c.id == "t_daga_oculta" for c in [*state.hand.cards, *state.discard_pile.cards])

    def test_draw_cards_zero_and_negative(self):
        state = _make_state([], draw_cards=[_plain()])
        draw_cards(state, 0)
        draw_cards(state, -3)
        assert state.hand.count == 0
