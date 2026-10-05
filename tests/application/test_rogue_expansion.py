"""La Pícara expansion: keyword Despojo, her new cards, her new relics and the new neutral relics.

No pygame. Each card/relic is exercised through the real use cases (play_card, end_turn,
run_manager) with plain domain objects; random effects are pinned with ``random.seed`` or
by leaving a single living enemy.
"""
from __future__ import annotations

import random

import pytest

from src.application import relic_effects
from src.application.end_turn import draw_opening_hand, end_player_turn
from src.application.play_card import play_card
from src.application.run_manager import (
    _all_relic_defs, _combat_gold, apply_combat_victory, create_run, pick_treasure_relics, shop_price,
)
from src.domain.card import Card, CardClass, CardEffect, CardType
from src.domain.card_pool import (
    CARD_CLASS_BY_ID, PACK_SIZE, PackTheme, card_factories_for_theme, hidden_dagger,
    lucky_crit_chance, lucky_roll_count,
)
from src.domain.character import ALL_CHARACTERS, CharacterId
from src.domain.chroma import Chroma
from src.domain.combat import CombatState
from src.domain.entities import (
    MARKED, POISON, Enemy, Intent, IntentType, Player, deal_damage, status_stacks,
)
from src.domain.keywords import KEYWORD_DEFS, Keyword, spoil_text
from src.domain.mana import Mana
from src.domain.numbers import BigValue
from src.domain.pile import DiscardPile, DrawPile, Hand
from src.domain.relic import Relic, RelicTag, relic_total

G = Chroma.GOLDEN


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _card(card_id: str) -> Card:
    """A fresh pool card by id (any theme)."""
    for theme in PackTheme:
        for f in card_factories_for_theme(theme):
            if f.card_id == card_id:
                return f()
    raise KeyError(card_id)


def _filler(n: int = 1, block: int = 1) -> list[Card]:
    return [Card(id=f"f{i}", name="Relleno", card_type=CardType.SKILL, cost=0,
                 base_effect=CardEffect("Relleno", block=BigValue(block))) for i in range(n)]


def _attack(dmg: int = 5, cost: int = 0, cid: str = "atk") -> Card:
    return Card(id=cid, name="Ataque", card_type=CardType.ATTACK, cost=cost,
                base_effect=CardEffect("Ataque", damage=BigValue(dmg)))


def _enemy(hp: int = 100, block: int = 0, eid: str = "e", intent: int = 5) -> Enemy:
    return Enemy(id=eid, name="E", max_hp=hp, current_hp=hp, block=block,
                 intent=Intent(IntentType.ATTACK, intent))


def _relic(tag: RelicTag, chroma=None) -> Relic:
    return Relic("r", "Reliquia", "d", tag=tag, chroma=chroma)


def _state(hand=(), *, enemies=None, relics=(), draw=(), discard=(), mana=3, luck=0) -> CombatState:
    enemies = enemies if enemies is not None else [_enemy()]
    state = CombatState(
        player=Player(name="P", max_hp=100, current_hp=100, luck=luck),
        enemies=enemies,
        hand=Hand(cards=list(hand)),
        draw_pile=DrawPile(cards=list(draw)),
        discard_pile=DiscardPile(cards=list(discard)),
        mana=Mana(current=mana, maximum=mana),
        relics=list(relics),
    )
    state.turn_start_alive = len(state.living_enemies())
    return state


def _spoil_card(dmg: int = 0, blk: int = 0, extra_dmg: int = 0, extra_blk: int = 0, cid="sp") -> Card:
    return Card(id=cid, name="Despojada", card_type=CardType.ATTACK if dmg or extra_dmg else CardType.SKILL,
                cost=0, base_effect=CardEffect("Despojada", damage=BigValue(dmg), block=BigValue(blk),
                                               spoil=CardEffect("Despojo", damage=BigValue(extra_dmg),
                                                                block=BigValue(extra_blk))))


# ---------------------------------------------------------------------------
# Keyword Despojo
# ---------------------------------------------------------------------------

class TestSpoilKeyword:
    def test_keyword_definition(self):
        assert KEYWORD_DEFS[Keyword.SPOIL].name == "Despojo"

    def test_rule_has_no_extra_condition(self):
        assert KEYWORD_DEFS[Keyword.SPOIL].rule == "Despojo: efecto extra si ya descartaste una carta este turno."

    def test_card_reports_keyword(self):
        assert Keyword.SPOIL in _spoil_card(extra_dmg=3).keywords()

    def test_plain_card_has_no_spoil(self):
        assert Keyword.SPOIL not in _attack().keywords()

    def test_totals_include_layer_only_when_on(self):
        card = _spoil_card(dmg=6, extra_dmg=6)
        assert (card.total_damage(), card.total_damage(spoil=True)) == (6, 12)

    def test_spoil_text(self):
        assert spoil_text(_spoil_card(extra_blk=7)) == "+7 de escudo"

    def test_not_ready_without_discard(self):
        state = _state([_spoil_card(extra_dmg=3)])
        assert state.spoil_ready(state.hand.cards[0]) is False

    def test_discard_from_hand_counts(self):
        state = _state(_filler(2))
        state.discard_from_hand(0)
        assert (state.discards_this_turn, state.discard_pile.count, state.hand.count) == (1, 1, 1)

    def test_discard_out_of_range_is_ignored(self):
        state = _state(_filler(1))
        assert state.discard_from_hand(5) is None and state.discards_this_turn == 0

    def test_discard_random_empty_hand(self):
        assert _state().discard_random() is None

    def test_layer_resolves_after_discard(self):
        card = _spoil_card(dmg=6, extra_dmg=6)
        state = _state([card, *_filler()])
        state.discard_from_hand(1)
        result = play_card(state, 0, 0)
        assert (result.spoil, state.enemies[0].current_hp) == (True, 88)

    def test_layer_off_without_discard(self):
        state = _state([_spoil_card(dmg=6, extra_dmg=6)])
        result = play_card(state, 0, 0)
        assert (result.spoil, state.enemies[0].current_hp) == (False, 94)

    def test_playing_cards_is_not_discarding(self):
        state = _state([*_filler(1), _spoil_card(extra_blk=5)])
        play_card(state, 0)
        assert play_card(state, 0).spoil is False

    def test_message_mentions_spoil(self):
        state = _state([_spoil_card(extra_blk=1), *_filler()])
        state.discard_from_hand(1)
        assert "¡Despojo!" in play_card(state, 0).message

    def test_end_of_turn_discard_does_not_count(self):
        state = _state(_filler(3), draw=_filler(10))
        end_player_turn(state)
        assert state.discards_this_turn == 0

    def test_discards_reset_each_turn(self):
        state = _state(_filler(3), draw=_filler(10))
        state.discard_random()
        end_player_turn(state)
        assert state.spoil_active is False

    def test_golden_card_resolves_layer_each_cast(self):
        card = _spoil_card(extra_blk=5)
        card.chroma = G
        state = _state([card, *_filler()])
        state.discard_from_hand(1)
        play_card(state, 0)
        assert state.player.block == 10

    def test_existing_golpe_desesperado_turns_spoil_on(self):
        state = _state([_card("r_golpe_desesperado"), *_filler(2)])
        play_card(state, 0, 0)
        assert state.spoil_active


# ---------------------------------------------------------------------------
# Damage helper and Marcado
# ---------------------------------------------------------------------------

class TestDealDamage:
    def test_block_absorbs(self):
        e = _enemy(hp=20, block=5)
        assert (deal_damage(e, 8), e.current_hp, e.block) == (3, 17, 0)

    def test_zero_damage(self):
        e = _enemy(hp=20, block=5)
        assert deal_damage(e, 0) == 0 and e.block == 5

    def test_never_below_zero(self):
        e = _enemy(hp=5)
        assert (deal_damage(e, 10 ** 9), e.current_hp) == (5, 0)

    def test_dead_enemy_takes_nothing(self):
        e = _enemy(hp=5)
        e.current_hp = 0
        assert deal_damage(e, 3) == 0

    def test_marked_adds_per_hit(self):
        e = _enemy(hp=50)
        e.status_effects.append(__import__("src.domain.entities", fromlist=["StatusEffect"]).StatusEffect(MARKED, 3, False))
        deal_damage(e, 1)
        deal_damage(e, 1)
        assert e.current_hp == 42


# ---------------------------------------------------------------------------
# New cards
# ---------------------------------------------------------------------------

NEW_IDS = [
    "r_punalada_trapera", "r_tajo_veloz", "r_tirar_y_cortar", "r_rafaga_de_cortes", "r_lanzar_la_daga",
    "r_corte_afortunado", "r_abrir_la_guardia", "r_hoja_unica", "r_quiebro", "r_finta_doble",
    "r_sombra_esquiva", "r_manto_raido", "r_rodar", "r_deshacerse", "r_senuelo", "r_capa_de_sombras",
    "r_contraataque", "r_estilo_propio", "r_chatarra", "r_vaciar_bolsillos", "r_juego_de_manos",
    "r_carterista", "r_hoja_envenenada", "r_tirar_los_dados", "r_marcar_objetivo", "r_rapina",
    "r_maestra_de_dagas", "r_sombra_gemela", "r_fortuna_audaz", "r_nada_que_perder",
    "r_cadena_perfecta", "r_asesina", "r_mil_cortes",
]


class TestCardPool:
    @pytest.mark.parametrize("cid", NEW_IDS)
    def test_card_is_rogue(self, cid):
        assert CARD_CLASS_BY_ID[cid] is CardClass.ROGUE

    @pytest.mark.parametrize("cid", NEW_IDS)
    def test_card_has_text_or_numbers(self, cid):
        c = _card(cid)
        assert any(fx.text for fx in c.all_effects()) or c.keywords() or c.total_damage() or c.total_block()

    def test_ids_unique(self):
        ids = [f.card_id for t in PackTheme for f in card_factories_for_theme(t)]
        assert len(ids) == len(set(ids))

    def test_names_unique(self):
        names = [f().name for t in PackTheme for f in card_factories_for_theme(t)]
        assert len(names) == len(set(names))

    @pytest.mark.parametrize("theme", list(PackTheme))
    def test_each_class_still_fills_a_pack(self, theme):
        for cls in (CardClass.WARRIOR, CardClass.MAGE, CardClass.ROGUE):
            assert len(card_factories_for_theme(theme, {CardClass.NEUTRAL, cls})) >= PACK_SIZE

    def test_poison_cards_are_rogue(self):
        assert CARD_CLASS_BY_ID["m_veneno"] is CARD_CLASS_BY_ID["ep_tormenta_veneno"] is CardClass.ROGUE

    def test_no_keyword_layer_has_conditions_in_text(self):
        """Design rule: the keyword is the only condition ("si" never appears in a layer)."""
        for t in PackTheme:
            for f in card_factories_for_theme(t):
                c = f()
                for fx in c.combo_effects() + c.singular_effects() + c.void_effects() + c.spoil_effects():
                    assert " si " not in f" {fx.text} "


class TestAttackCards:
    def test_punalada_trapera_combo(self):
        state = _state([*_filler(), _card("r_punalada_trapera")])
        play_card(state, 0)
        play_card(state, 0, 0)
        assert state.enemies[0].current_hp == 90

    def test_tajo_veloz_combo_gives_mana(self):
        state = _state([*_filler(), _card("r_tajo_veloz")], mana=3)
        play_card(state, 0)
        play_card(state, 0, 0)
        assert state.mana.current == 3

    def test_tirar_y_cortar_spoil(self):
        state = _state([_card("r_tirar_y_cortar"), *_filler()])
        state.discard_from_hand(1)
        play_card(state, 0, 0)
        assert state.enemies[0].current_hp == 88

    def test_rafaga_counts_cards(self):
        state = _state([*_filler(2), _card("r_rafaga_de_cortes")])
        play_card(state, 0)
        play_card(state, 0)
        play_card(state, 0, 0)
        assert state.enemies[0].current_hp == 94

    def test_rafaga_alone_hits_two(self):
        state = _state([_card("r_rafaga_de_cortes")])
        play_card(state, 0, 0)
        assert state.enemies[0].current_hp == 98

    def test_lanzar_la_daga_hides_one(self):
        state = _state([_card("r_lanzar_la_daga")])
        play_card(state, 0, 0)
        assert [c.id for c in state.draw_pile.cards] == ["t_daga_oculta"]

    def test_corte_afortunado_crit_with_luck(self):
        random.seed(1)
        state = _state([_card("r_corte_afortunado")], luck=10 ** 6)
        play_card(state, 0, 0)
        assert state.enemies[0].current_hp in (88, 94)   # 75 % cap: crit or not

    def test_crit_chance_bounds(self):
        assert (lucky_crit_chance(0), lucky_crit_chance(8), lucky_crit_chance(10 ** 9)) == pytest.approx(
            (0.10, 0.30, 0.75))

    def test_abrir_la_guardia_strips_block(self):
        state = _state([_card("r_abrir_la_guardia")], enemies=[_enemy(block=10)])
        play_card(state, 0, 0)
        assert (state.enemies[0].block, state.enemies[0].current_hp) == (0, 100)

    def test_hoja_unica_singular(self):
        state = _state([_card("r_hoja_unica")])
        state.singular_deck = True
        play_card(state, 0, 0)
        assert state.enemies[0].current_hp == 84

    def test_mil_cortes_per_discard(self):
        state = _state([_card("r_mil_cortes")], discard=_filler(4))
        play_card(state, 0)
        assert state.enemies[0].current_hp == 100 - 3 * 5   # 4 + itself


class TestSkillCards:
    def test_quiebro_combo_draws(self):
        state = _state([*_filler(), _card("r_quiebro")], draw=_filler(3))
        play_card(state, 0)
        play_card(state, 0)
        assert state.hand.count == 1

    def test_finta_doble_combo_hits(self):
        state = _state([*_filler(), _card("r_finta_doble")])
        play_card(state, 0)
        play_card(state, 0)
        assert state.enemies[0].current_hp == 97

    def test_sombra_esquiva_combo_hides_dagger(self):
        state = _state([*_filler(), _card("r_sombra_esquiva")])
        play_card(state, 0)
        play_card(state, 0)
        assert state.draw_pile.count == 1

    def test_manto_raido_spoil(self):
        state = _state([_card("r_manto_raido"), *_filler()])
        state.discard_from_hand(1)
        play_card(state, 0)
        assert state.player.block == 14

    def test_rodar_discards_and_draws(self):
        state = _state([_card("r_rodar"), *_filler(2)], draw=_filler(1, block=9))
        play_card(state, 0)
        assert (state.hand.count, state.discards_this_turn) == (2, 1)

    def test_deshacerse_turns_spoil_on(self):
        state = _state([_card("r_deshacerse"), *_filler()])
        play_card(state, 0)
        assert (state.player.block, state.spoil_active) == (4, True)

    def test_senuelo_redirects_attack(self):
        a, b = _enemy(eid="a", intent=10), _enemy(eid="b", intent=0)
        b.intent = Intent(IntentType.BLOCK, 0)
        state = _state([_card("r_senuelo")], enemies=[a, b], draw=_filler(10))
        play_card(state, 0)
        end_player_turn(state)
        assert (state.player.current_hp, b.current_hp) == (100, 90)

    def test_senuelo_alone_does_nothing(self):
        state = _state([_card("r_senuelo")], enemies=[_enemy(intent=10)], draw=_filler(10))
        play_card(state, 0)
        end_player_turn(state)
        assert state.player.current_hp == 95   # 5 block absorbed 5

    def test_capa_keeps_block(self):
        state = _state([_card("r_capa_de_sombras")], enemies=[_enemy(intent=0)], draw=_filler(10))
        state.enemies[0].intent = Intent(IntentType.BLOCK, 0)
        play_card(state, 0)
        end_player_turn(state)
        assert state.player.block == 8

    def test_capa_only_one_turn(self):
        state = _state([_card("r_capa_de_sombras")], enemies=[_enemy()], draw=_filler(20))
        state.enemies[0].intent = Intent(IntentType.BLOCK, 0)
        play_card(state, 0)
        end_player_turn(state)
        state.enemies[0].intent = Intent(IntentType.BLOCK, 0)
        end_player_turn(state)
        assert state.player.block == 0

    def test_contraataque_hits_back(self):
        e = _enemy(intent=3)
        state = _state([_card("r_contraataque")], enemies=[e], draw=_filler(10))
        play_card(state, 0)
        end_player_turn(state)
        assert e.current_hp == 97

    def test_contraataque_not_when_hit_through(self):
        e = _enemy(intent=10)
        state = _state([_card("r_contraataque")], enemies=[e], draw=_filler(10))
        play_card(state, 0)
        end_player_turn(state)
        assert e.current_hp == 100

    def test_estilo_propio_singular_draws(self):
        state = _state([_card("r_estilo_propio")], draw=_filler(3))
        state.singular_deck = True
        play_card(state, 0)
        assert (state.player.block, state.hand.count) == (12, 2)


class TestMagicCards:
    def test_chatarra_spoil_mana(self):
        state = _state([_card("r_chatarra"), *_filler()], draw=_filler(2), mana=3)
        state.mana.current = 1
        state.discard_from_hand(1)
        play_card(state, 0)
        assert state.mana.current == 2

    def test_vaciar_bolsillos(self):
        state = _state([_card("r_vaciar_bolsillos"), *_filler(3)], draw=_filler(5, block=9))
        play_card(state, 0)
        assert (state.hand.count, state.discards_this_turn, state.discard_pile.count) == (3, 3, 4)

    def test_juego_de_manos_returns_last(self):
        last = _attack(cid="last")
        state = _state([_card("r_juego_de_manos")], discard=[*_filler(), last])
        play_card(state, 0)
        assert [c.id for c in state.hand.cards] == ["last"]

    def test_juego_de_manos_skips_itself(self):
        state = _state([_card("r_juego_de_manos")])
        play_card(state, 0)
        assert state.hand.count == 0

    def test_carterista_pays_on_kill(self):
        state = _state([_card("r_carterista"), _attack(10)], enemies=[_enemy(hp=5)], draw=_filler(2))
        play_card(state, 0)
        play_card(state, 0, 0)
        assert state.gold_earned == 10

    def test_carterista_no_kill_no_gold(self):
        state = _state([_card("r_carterista")], draw=_filler(5))
        play_card(state, 0)
        end_player_turn(state)
        assert state.gold_earned == 0

    def test_hoja_envenenada_three_attacks(self):
        state = _state([_card("r_hoja_envenenada"), *[_attack(1) for _ in range(4)]])
        play_card(state, 0)
        for _ in range(4):
            play_card(state, 0, 0)
        assert status_stacks(state.enemies[0].status_effects, POISON) == 6

    def test_tirar_los_dados_range(self):
        for seed in range(50):
            random.seed(seed)
            state = _state([_card("r_tirar_los_dados")], mana=3)
            state.mana.current = 0
            play_card(state, 0)
            assert 0 <= state.mana.current <= 3

    def test_roll_count_bounds(self):
        assert (lucky_roll_count(0), lucky_roll_count(20), lucky_roll_count(10 ** 9)) == (1, 2, 4)

    def test_marcar_objetivo(self):
        state = _state([_card("r_marcar_objetivo"), _attack(5), _attack(5)])
        play_card(state, 0, 0)
        play_card(state, 0, 0)
        play_card(state, 0, 0)
        assert state.enemies[0].current_hp == 84

    def test_mark_cleared_at_end_of_turn(self):
        state = _state([_card("r_marcar_objetivo")], draw=_filler(10))
        play_card(state, 0, 0)
        end_player_turn(state)
        assert status_stacks(state.enemies[0].status_effects, MARKED) == 0


class TestPowers:
    def test_rapina_hits_on_discard(self):
        state = _state([_card("r_rapina"), *_filler(2)])
        play_card(state, 0)
        state.discard_random()
        assert state.enemies[0].current_hp == 97

    def test_maestra_de_dagas_chains(self):
        state = _state([_card("r_maestra_de_dagas")])
        play_card(state, 0)
        state.draw_pile.cards.append(hidden_dagger())
        from src.application.drawing import draw_cards
        draw_cards(state, 1)
        assert (state.enemies[0].current_hp, state.draw_pile.count) == (96, 1)

    def test_sombra_gemela_doubles_first_combo(self):
        state = _state([_card("r_sombra_gemela"), _card("r_punalada_trapera"), _card("r_punalada_trapera")],
                       mana=10)
        play_card(state, 0)
        play_card(state, 0, 0)     # 5 + 5 combo + 5 again
        play_card(state, 0, 0)     # 5 + 5 combo
        assert state.enemies[0].current_hp == 100 - 15 - 10

    def test_fortuna_audaz_each_turn(self):
        state = _state([_card("r_fortuna_audaz")], enemies=[_enemy(intent=0)], draw=_filler(20))
        play_card(state, 0)
        end_player_turn(state)
        assert state.player.block == 4 or state.hand.count == 6

    def test_nada_que_perder_rummages(self):
        state = _state([_card("r_nada_que_perder")], draw=_filler(20))
        play_card(state, 0)
        end_player_turn(state)
        assert (state.hand.count, state.spoil_active) == (6, True)

    def test_cadena_perfecta_fifth_card(self):
        state = _state([_card("r_cadena_perfecta"), *_filler(3), _attack(5)], mana=10)
        for _ in range(4):
            play_card(state, 0)
        result = play_card(state, 0, 0)
        assert (result.casts, state.enemies[0].current_hp) == (2, 90)

    def test_cadena_perfecta_fourth_card_normal(self):
        state = _state([_card("r_cadena_perfecta"), *_filler(2), _attack(5)], mana=10)
        for _ in range(3):
            play_card(state, 0)
        assert play_card(state, 0, 0).casts == 1

    def test_asesina_executes(self):
        state = _state([_card("r_asesina"), _attack(80)], mana=10)   # 20 HP left < 25 %
        play_card(state, 0)
        play_card(state, 0, 0)
        assert state.enemies[0].current_hp == 0

    def test_asesina_not_above_quarter(self):
        state = _state([_card("r_asesina"), _attack(70)], enemies=[_enemy(hp=1000)], mana=10)
        play_card(state, 0)
        play_card(state, 0, 0)
        assert state.enemies[0].current_hp == 930


# ---------------------------------------------------------------------------
# Rogue relics
# ---------------------------------------------------------------------------

class TestRogueRelics:
    @pytest.mark.parametrize("tag", [RelicTag.RAG_SACK, RelicTag.DUELIST_SCARF, RelicTag.GRAPPLING_HOOK,
                                     RelicTag.CRIMSON_RIBBON, RelicTag.TORN_POCKET, RelicTag.SPLIT_DAGGER,
                                     RelicTag.DAGGER_POUCH, RelicTag.SHARP_SHEATH, RelicTag.POISON_VIAL,
                                     RelicTag.VIPER_FANG])
    def test_is_rogue_only(self, tag):
        relic = next(r for r in _all_relic_defs() if r.tag is tag)
        assert relic.relic_class is CardClass.ROGUE

    def test_rag_sack(self):
        state = _state([_spoil_card(extra_dmg=1), *_filler()], relics=[_relic(RelicTag.RAG_SACK)])
        state.discard_from_hand(1)
        play_card(state, 0, 0)
        assert state.player.block == 2

    def test_rag_sack_needs_spoil(self):
        state = _state([_spoil_card(extra_dmg=1)], relics=[_relic(RelicTag.RAG_SACK)])
        play_card(state, 0, 0)
        assert state.player.block == 0

    def test_scarf_on_combo(self):
        card = Card(id="c", name="C", card_type=CardType.ATTACK, cost=0,
                    base_effect=CardEffect("C", damage=BigValue(5), block=BigValue(5),
                                           combo=CardEffect("x", draw=0)))
        state = _state([*_filler(), card], relics=[_relic(RelicTag.DUELIST_SCARF)])
        play_card(state, 0)
        state.player.block = 0
        play_card(state, 0, 0)
        assert (state.enemies[0].current_hp, state.player.block) == (93, 7)

    def test_scarf_not_without_combo(self):
        card = Card(id="c", name="C", card_type=CardType.ATTACK, cost=0,
                    base_effect=CardEffect("C", damage=BigValue(5), combo=CardEffect("x")))
        state = _state([card], relics=[_relic(RelicTag.DUELIST_SCARF)])
        play_card(state, 0, 0)
        assert state.enemies[0].current_hp == 95

    def test_hook_draws_once_per_turn(self):
        state = _state([_spoil_card(extra_blk=1, cid="a"), _spoil_card(extra_blk=1, cid="b"), *_filler()],
                       relics=[_relic(RelicTag.GRAPPLING_HOOK)], draw=_filler(5))
        state.discard_from_hand(2)
        play_card(state, 0)
        play_card(state, 0)
        assert state.hand.count == 1

    def test_ribbon_first_turn_combo(self):
        state = _state([_card("r_punalada_trapera")], relics=[_relic(RelicTag.CRIMSON_RIBBON)])
        assert play_card(state, 0, 0).combo is True

    def test_ribbon_not_second_turn(self):
        state = _state([_card("r_punalada_trapera")], relics=[_relic(RelicTag.CRIMSON_RIBBON)])
        state.turn = 2
        assert play_card(state, 0, 0).combo is False

    def test_torn_pocket_turn_start(self):
        state = _state(enemies=[_enemy()], relics=[_relic(RelicTag.TORN_POCKET)], draw=_filler(20))
        end_player_turn(state)
        assert (state.hand.count, state.spoil_active) == (5, True)

    def test_torn_pocket_opening_hand(self):
        state = _state(relics=[_relic(RelicTag.TORN_POCKET)], draw=_filler(20))
        draw_opening_hand(state)
        assert (state.hand.count, state.discard_pile.count) == (5, 1)

    def test_split_dagger_doubles_layer(self):
        state = _state([_spoil_card(extra_blk=5), *_filler()], relics=[_relic(RelicTag.SPLIT_DAGGER)])
        state.discard_from_hand(1)
        play_card(state, 0)
        assert state.player.block == 10

    def test_golden_split_dagger(self):
        state = _state([_spoil_card(extra_blk=5), *_filler()], relics=[_relic(RelicTag.SPLIT_DAGGER, G)])
        state.discard_from_hand(1)
        play_card(state, 0)
        assert state.player.block == 15

    def test_dagger_pouch(self):
        state = _state(relics=[_relic(RelicTag.DAGGER_POUCH)], draw=_filler(20))
        draw_opening_hand(state)
        daggers_left = sum(c.id == "t_daga_oculta" for c in state.draw_pile.cards)
        assert daggers_left + (100 - state.enemies[0].current_hp) // 4 == 2

    def test_sharp_sheath(self):
        state = _state(relics=[_relic(RelicTag.SHARP_SHEATH)], draw=[hidden_dagger()])
        from src.application.drawing import draw_cards
        draw_cards(state, 1)
        assert state.enemies[0].current_hp == 94

    def test_poison_vial_first_attack_only(self):
        state = _state([_attack(1), _attack(1)], relics=[_relic(RelicTag.POISON_VIAL)])
        play_card(state, 0, 0)
        play_card(state, 0, 0)
        assert status_stacks(state.enemies[0].status_effects, POISON) == 1

    def test_poison_vial_resets_each_turn(self):
        state = _state([_attack(1)], relics=[_relic(RelicTag.POISON_VIAL)], draw=[_attack(1) for _ in range(10)])
        state.enemies[0].intent = Intent(IntentType.BLOCK, 0)
        play_card(state, 0, 0)
        end_player_turn(state)
        play_card(state, 0, 0)
        assert status_stacks(state.enemies[0].status_effects, POISON) == 1   # 1 ticked, +1

    def test_viper_fang_spreads(self):
        a, b = _enemy(hp=5, eid="a"), _enemy(eid="b")
        from src.domain.entities import add_status
        add_status(a.status_effects, POISON, 4, is_buff=False)
        state = _state([_attack(10)], enemies=[a, b], relics=[_relic(RelicTag.VIPER_FANG)])
        play_card(state, 0, 0)
        assert (status_stacks(b.status_effects, POISON), status_stacks(a.status_effects, POISON)) == (4, 0)

    def test_viper_fang_on_poison_death(self):
        a, b = _enemy(hp=2, eid="a", intent=0), _enemy(eid="b", intent=0)
        from src.domain.entities import add_status
        add_status(a.status_effects, POISON, 5, is_buff=False)
        state = _state(enemies=[a, b], relics=[_relic(RelicTag.VIPER_FANG)], draw=_filler(10))
        end_player_turn(state)
        # a: 5 dmg, 4 stacks left, dies → b gets 4, then ticks them (4 dmg, 3 left)
        assert (status_stacks(b.status_effects, POISON), b.current_hp) == (3, 96)


# ---------------------------------------------------------------------------
# Neutral relics
# ---------------------------------------------------------------------------

def _rogue_run():
    char = next(c for c in ALL_CHARACTERS if c.id is CharacterId.ROGUE)
    return create_run(char, 7)


class TestNeutralRelics:
    @pytest.mark.parametrize("tag", [RelicTag.THIEF_MASK, RelicTag.LUCKY_COIN, RelicTag.SILVER_HORSESHOE,
                                     RelicTag.SILK_GLOVE, RelicTag.SILENT_BOOTS, RelicTag.SPIDER_THREAD,
                                     RelicTag.MASTER_KEY, RelicTag.BROKEN_CLOCK])
    def test_is_neutral(self, tag):
        relic = next(r for r in _all_relic_defs() if r.tag is tag)
        assert relic.relic_class is CardClass.NEUTRAL

    def test_mask_gold(self):
        run = _rogue_run()
        enemies = [_enemy(hp=80)]
        plain = _combat_gold(run, enemies)
        run.relics.append(_relic(RelicTag.THIEF_MASK))
        assert _combat_gold(run, enemies) == round(plain * 1.25)

    def test_mask_shop_price(self):
        run = _rogue_run()
        run.relics.append(_relic(RelicTag.THIEF_MASK))
        assert (shop_price(run, 150), shop_price(run, 75)) == (135, 68)

    def test_shop_price_never_below_one(self):
        assert relic_effects.shop_price([_relic(RelicTag.THIEF_MASK)] * 20, 1) == 1

    def test_lucky_coin_once_per_turn(self):
        state = _state(enemies=[_enemy(eid="a"), _enemy(eid="b")], relics=[_relic(RelicTag.LUCKY_COIN)])
        state.mana.current = 0
        rng = random.Random(0)
        for _ in range(40):
            state.pick_random_enemy(rng)
        assert state.mana.current == 1

    def test_lucky_coin_needs_two_enemies(self):
        state = _state(relics=[_relic(RelicTag.LUCKY_COIN)])
        state.mana.current = 0
        for _ in range(5):
            state.pick_random_enemy()
        assert state.mana.current == 0

    def test_horseshoe_luck(self):
        assert relic_effects.luck_bonus([_relic(RelicTag.SILVER_HORSESHOE)]) == 30

    def test_silk_glove_third_card_free(self):
        state = _state([*_filler(2), _attack(5, cost=3)], relics=[_relic(RelicTag.SILK_GLOVE)], mana=3)
        play_card(state, 0)
        play_card(state, 0)
        state.mana.current = 0
        assert play_card(state, 0, 0).success

    def test_silk_glove_only_third(self):
        state = _state([_attack(5, cost=3)], relics=[_relic(RelicTag.SILK_GLOVE)])
        assert state.card_cost(state.hand.cards[0]) == 3

    def test_silent_boots(self):
        state = _state(relics=[_relic(RelicTag.SILENT_BOOTS)], draw=_filler(20))
        draw_opening_hand(state)
        assert state.hand.count == 7

    def test_spider_thread(self):
        state = _state(enemies=[_enemy(intent=6)], relics=[_relic(RelicTag.SPIDER_THREAD)], draw=_filler(10))
        end_player_turn(state)
        assert state.player.current_hp == 100

    def test_spider_thread_needs_empty_hand(self):
        state = _state(_filler(1), enemies=[_enemy(intent=6)], relics=[_relic(RelicTag.SPIDER_THREAD)],
                       draw=_filler(10))
        end_player_turn(state)
        assert state.player.current_hp == 94

    def test_master_key_two_choices(self):
        run = _rogue_run()
        run.relics.append(_relic(RelicTag.MASTER_KEY))
        relics = pick_treasure_relics(run, "room")
        assert len(relics) == 2 and relics[0].tag is not relics[1].tag

    def test_treasure_default_one(self):
        assert len(pick_treasure_relics(_rogue_run(), "room")) == 1

    def test_broken_clock_once(self):
        state = _state([_attack(1, cost=3), *_filler(2)], relics=[_relic(RelicTag.BROKEN_CLOCK)])
        play_card(state, 0, 0)
        first = state.mana.current
        state.mana.current = 3
        state.hand.cards.insert(0, _attack(1, cost=3))
        play_card(state, 0, 0)
        assert (first, state.mana.current) == (3, 0)

    def test_broken_clock_needs_cards_in_hand(self):
        state = _state([_attack(1, cost=3)], relics=[_relic(RelicTag.BROKEN_CLOCK)])
        play_card(state, 0, 0)
        assert state.mana.current == 0


class TestRunIntegration:
    def test_every_new_relic_defined_once(self):
        tags = [r.tag for r in _all_relic_defs()]
        assert len(tags) == len(set(tags)) == len(list(RelicTag))

    def test_victory_adds_combat_gold(self):
        run = _rogue_run()
        before = run.gold
        gold = apply_combat_victory(run, run.player_current_hp, [_enemy(hp=8)], bonus_gold=10)
        assert run.gold - before == gold == 11

    def test_relic_total_golden(self):
        assert relic_total([_relic(RelicTag.SILENT_BOOTS, G)], RelicTag.SILENT_BOOTS, 2) == 4

    def test_stress_many_turns(self):
        """A rogue loaded with every new power and relic survives 200 turns without errors."""
        random.seed(3)
        relics = [Relic("r", "R", "d", tag=t) for t in RelicTag]
        deck = [_card(cid) for cid in NEW_IDS] * 2
        state = _state(enemies=[_enemy(hp=10 ** 9, eid=str(i)) for i in range(3)], relics=relics,
                       draw=deck, mana=10)
        draw_opening_hand(state)
        for _ in range(200):
            for _ in range(8):
                if not state.hand.cards:
                    break
                idx = random.randrange(state.hand.count)
                target = next(i for i, e in enumerate(state.enemies) if e.is_alive)
                play_card(state, idx, target)
            end_player_turn(state)
        assert state.turn == 201
