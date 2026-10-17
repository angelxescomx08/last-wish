"""La Guerrera: Fuerza on the hero, losing HP, healing, keywords Furia / Aguante, her cards,
her relics and the class starter decks (Guerrera, Mago).

No pygame. Cards and relics are exercised through the real use cases (play_card, end_turn)
with plain domain objects and a single living enemy unless a test needs more.
"""
from __future__ import annotations

import pytest

from src.application import relic_effects
from src.application.end_turn import draw_opening_hand, end_player_turn
from src.application.play_card import play_card
from src.application.run_manager import _all_relic_defs
from src.domain.card import Card, CardClass, CardEffect, CardRarity, CardType
from src.domain.card_pool import (
    CARD_CLASS_BY_ID, PACK_SIZE, PackTheme, card_factories_for_classes, card_factories_for_theme,
    starter_deck,
)
from src.domain.character import CharacterId
from src.domain.chroma import Chroma
from src.domain.combat import CombatState
from src.domain.entities import (
    STRENGTH, VULNERABLE, WEAK, Enemy, Intent, IntentType, Player, StatusEffect, status_stacks,
)
from src.domain.keywords import KEYWORD_DEFS, Keyword, endure_text, fury_text
from src.domain.mana import Mana
from src.domain.numbers import BigValue
from src.domain.pile import DiscardPile, DrawPile, Hand
from src.domain.relic import RELIC_RARITY, Relic, RelicTag
from src.domain.rarity import Rarity

G = Chroma.GOLDEN


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _card(card_id: str) -> Card:
    for theme in PackTheme:
        for f in card_factories_for_theme(theme):
            if f.card_id == card_id:
                return f()
    raise KeyError(card_id)


def _enemy(hp: int = 100, block: int = 0, eid: str = "e", intent: int = 5) -> Enemy:
    return Enemy(id=eid, name="E", max_hp=hp, current_hp=hp, block=block,
                 intent=Intent(IntentType.ATTACK, intent))


def _filler(n: int = 1) -> list[Card]:
    return [Card(id=f"f{i}", name="Relleno", card_type=CardType.SKILL, cost=0,
                 base_effect=CardEffect("Relleno")) for i in range(n)]


def _state(hand=(), *, enemies=None, relics=(), hp=100, max_hp=100, mana=5, draw=()) -> CombatState:
    state = CombatState(
        player=Player(name="P", max_hp=max_hp, current_hp=hp),
        enemies=enemies if enemies is not None else [_enemy()],
        hand=Hand(cards=list(hand)),
        draw_pile=DrawPile(cards=list(draw)),
        discard_pile=DiscardPile(cards=[]),
        mana=Mana(current=mana, maximum=mana),
        relics=list(relics),
    )
    state.turn_start_alive = len(state.living_enemies())
    return state


def _relic(tag: RelicTag, chroma=None) -> Relic:
    return Relic("r", "Reliquia", "d", tag=tag, chroma=chroma)


def _play(state: CombatState, card_id: str, target: int | None = 0):
    state.hand.cards.append(_card(card_id))
    return play_card(state, state.hand.count - 1, target)


WARRIOR_IDS = [cid for cid, cls in CARD_CLASS_BY_ID.items() if cid.startswith("wr_")]


# ---------------------------------------------------------------------------
# Fuerza, losing HP, healing
# ---------------------------------------------------------------------------

class TestStrength:
    def test_strength_adds_to_card_damage(self):
        state = _state()
        state.gain_strength(3)
        _play(state, "wr_tajo_brutal")
        assert state.enemies[0].current_hp == 100 - 8 - 3

    def test_strength_counts_on_every_extra_hit(self):
        state = _state()
        state.gain_strength(2)
        _play(state, "wr_golpe_doble")
        assert state.enemies[0].current_hp == 100 - 2 * (5 + 2)

    def test_strength_is_a_buff_status(self):
        state = _state()
        state.gain_strength(1)
        assert state.player.status_effects == [StatusEffect(STRENGTH, 1, True)]

    def test_zero_strength_adds_nothing(self):
        state = _state()
        state.gain_strength(0)
        assert state.hero_strength == 0 and state.player.status_effects == []

    def test_hero_hit_applies_weak_and_vulnerable(self):
        state = _state()
        state.player.status_effects.append(StatusEffect(WEAK, 1, False))
        state.enemies[0].status_effects.append(StatusEffect(VULNERABLE, 1, False))
        state.gain_strength(4)
        state.hero_hit(state.enemies[0], 8)     # (8+4) x0.75 = 9, x1.5 = 13
        assert state.enemies[0].current_hp == 100 - 13

    def test_strength_survives_end_of_turn(self):
        state = _state(draw=_filler(10))
        state.gain_strength(2)
        end_player_turn(state)
        assert state.hero_strength == 2


class TestLoseHp:
    def test_ignores_block(self):
        state = _state()
        state.player.block = 20
        assert state.lose_hp(5) == 5
        assert state.player.current_hp == 95 and state.player.block == 20

    def test_never_kills_you(self):
        state = _state(hp=4)
        assert state.lose_hp(10) == 3
        assert state.player.current_hp == 1

    def test_at_one_hp_loses_nothing(self):
        state = _state(hp=1)
        assert state.lose_hp(5) == 0 and state.hp_lost_this_turn == 0

    def test_counts_for_the_turn(self):
        state = _state()
        state.lose_hp(3)
        state.lose_hp(2)
        assert state.hp_lost_this_turn == 5

    def test_turn_counter_resets(self):
        state = _state(draw=_filler(10))
        state.lose_hp(3)
        end_player_turn(state)
        assert state.hp_lost_this_turn == 0

    def test_enemy_hits_do_not_count_for_your_turn(self):
        state = _state(draw=_filler(10), enemies=[_enemy(intent=7)])
        end_player_turn(state)
        assert state.player.current_hp == 93 and state.hp_lost_this_turn == 0


class TestHeal:
    def test_heals_up_to_max(self):
        state = _state(hp=90)
        assert state.heal_hero(5) == 5 and state.player.current_hp == 95

    def test_overflow_becomes_block(self):
        state = _state(hp=97)
        assert state.heal_hero(10) == 3
        assert state.player.current_hp == 100 and state.player.block == 7

    def test_full_hp_all_block(self):
        state = _state()
        state.heal_hero(6)
        assert state.player.block == 6

    def test_zero_heal_does_nothing(self):
        state = _state(hp=50)
        assert state.heal_hero(0) == 0 and state.player.block == 0


# ---------------------------------------------------------------------------
# Keywords Furia and Aguante
# ---------------------------------------------------------------------------

class TestKeywords:
    def test_definitions(self):
        assert KEYWORD_DEFS[Keyword.FURY].rule == "Furia: efecto extra si ya perdiste vida este turno."
        assert KEYWORD_DEFS[Keyword.ENDURE].rule == "Aguante: efecto extra si tienes escudo al jugarla."

    def test_cards_report_keywords(self):
        assert Keyword.FURY in _card("wr_tajo_brutal").keywords()
        assert Keyword.ENDURE in _card("wr_embate_firme").keywords()

    def test_layer_texts(self):
        assert fury_text(_card("wr_tajo_brutal")) == "+5 de daño"
        assert endure_text(_card("wr_muro_acero")) == "+1 de Fuerza"

    def test_fury_off_without_hp_lost(self):
        state = _state()
        result = _play(state, "wr_tajo_brutal")
        assert not result.fury and state.enemies[0].current_hp == 92

    def test_fury_on_after_losing_hp(self):
        state = _state()
        state.lose_hp(1)
        result = _play(state, "wr_tajo_brutal")
        assert result.fury and state.enemies[0].current_hp == 100 - 13

    def test_card_own_hp_cost_does_not_trigger_its_fury(self):
        state = _state()
        result = _play(state, "wr_sacrificio")
        assert not result.fury and state.hand.count == 0

    def test_fury_ready_matches_play(self):
        state = _state()
        card = _card("wr_rugido")
        assert not state.fury_ready(card)
        state.lose_hp(2)
        assert state.fury_ready(card)

    def test_endure_off_without_block(self):
        state = _state()
        result = _play(state, "wr_embate_firme")
        assert not result.endure and state.enemies[0].current_hp == 88

    def test_endure_on_with_block(self):
        state = _state()
        state.player.block = 1
        result = _play(state, "wr_embate_firme")
        assert result.endure and state.enemies[0].current_hp == 100 - 18

    def test_endure_checked_before_own_block(self):
        state = _state()
        result = _play(state, "wr_muro_acero")
        assert not result.endure and state.hero_strength == 0 and state.player.block == 14

    def test_endure_after_another_block(self):
        state = _state()
        _play(state, "wr_postura_firme")
        _play(state, "wr_muro_acero")
        assert state.hero_strength == 1 and state.player.block == 8 + 14


# ---------------------------------------------------------------------------
# Cards
# ---------------------------------------------------------------------------

class TestWarriorCards:
    def test_corte_sangriento(self):
        state = _state()
        _play(state, "wr_corte_sangriento")
        assert state.enemies[0].current_hp == 87 and state.player.current_hp == 97

    def test_self_damage_cards_beat_plain_ones(self):
        assert _card("wr_corte_sangriento").total_damage() > _card("a_golpe_ferreo").total_damage()
        assert _card("wr_escudo_sangre").total_block() > _card("e_guardia_solida").total_block()
        assert _card("wr_hachazo_temerario").total_damage() > _card("a_golpe_pesado").total_damage()

    def test_golpe_de_escudo_uses_block(self):
        state = _state()
        state.player.block = 17
        _play(state, "wr_golpe_escudo")
        assert state.enemies[0].current_hp == 83

    def test_golpe_de_escudo_without_block(self):
        state = _state()
        _play(state, "wr_golpe_escudo")
        assert state.enemies[0].current_hp == 100

    def test_sed_de_batalla_heals_hp_damage_only(self):
        state = _state(hp=50, enemies=[_enemy(block=4)])
        _play(state, "wr_sed_batalla")
        assert state.enemies[0].current_hp == 94 and state.player.current_hp == 56

    def test_torbellino_furia_heals_per_enemy(self):
        state = _state(hp=50, enemies=[_enemy(eid="a"), _enemy(eid="b")])
        state.lose_hp(1)
        _play(state, "wr_torbellino_acero", None)
        assert [e.current_hp for e in state.enemies] == [93, 93]
        assert state.player.current_hp == 49 + 6

    def test_represalia_doubles_hp_lost(self):
        state = _state()
        state.lose_hp(6)
        _play(state, "wr_represalia")
        assert state.enemies[0].current_hp == 88

    def test_represalia_without_hp_lost(self):
        state = _state()
        _play(state, "wr_represalia")
        assert state.enemies[0].current_hp == 100

    def test_martillo_endure_strength(self):
        state = _state(enemies=[_enemy(eid="a"), _enemy(eid="b")])
        state.player.block = 5
        _play(state, "wr_martillo_sismico", None)
        assert [e.current_hp for e in state.enemies] == [82, 82] and state.hero_strength == 2

    def test_furia_desatada_hits(self):
        state = _state()
        state.lose_hp(1)
        _play(state, "wr_furia_desatada")
        assert state.enemies[0].current_hp == 100 - 6 * 4

    def test_ira_carmesi(self):
        state = _state(hp=60, enemies=[_enemy(hp=100)])
        _play(state, "wr_ira_carmesi")
        assert state.enemies[0].current_hp == 60
        assert state.player.current_hp == 60 - 8 + 20

    def test_golpe_vampirico_overflow_becomes_block(self):
        state = _state(hp=90)
        _play(state, "wr_golpe_vampirico")
        assert state.player.current_hp == 100 and state.player.block == 14

    def test_herida_abierta_draws(self):
        state = _state(draw=_filler(3))
        _play(state, "wr_herida_abierta", None)
        assert state.hand.count == 2 and state.player.current_hp == 97

    def test_vendaje_endure(self):
        state = _state(hp=50)
        state.player.block = 1
        _play(state, "wr_vendaje", None)
        assert state.player.current_hp == 59

    def test_rugido_with_fury(self):
        state = _state()
        state.lose_hp(1)
        _play(state, "wr_rugido", None)
        assert state.hero_strength == 3

    def test_sangria(self):
        state = _state()
        _play(state, "wr_sangria", None)
        assert state.hero_strength == 3 and state.player.current_hp == 96

    def test_pacto_de_hierro(self):
        state = _state(mana=3)
        state.mana.current = 1
        _play(state, "wr_pacto_hierro", None)
        assert state.mana.current == 2 and state.player.current_hp == 96

    def test_coraza_viva_scales_and_caps(self):
        state = _state(hp=70)
        _play(state, "wr_coraza_viva", None)
        assert state.player.block == 15
        state = _state(hp=10)
        _play(state, "wr_coraza_viva", None)
        assert state.player.block == 30

    def test_transfusion(self):
        state = _state(hp=80)
        state.player.block = 12
        _play(state, "wr_transfusion", None)
        assert state.player.current_hp == 92 and state.player.block == 0

    def test_doblar_escudo(self):
        state = _state()
        state.player.block = 9
        _play(state, "wr_doblar_escudo", None)
        assert state.player.block == 18

    def test_muralla_keeps_block(self):
        state = _state(draw=_filler(10), enemies=[_enemy(intent=0)])
        _play(state, "wr_muralla_infranqueable", None)
        end_player_turn(state)
        assert state.player.block == 30

    def test_ejecucion_heals_on_kill(self):
        state = _state(hp=50, enemies=[_enemy(hp=20)])
        _play(state, "ep_ejecucion")
        assert state.player.current_hp == 60

    def test_ejecucion_no_heal_without_kill(self):
        state = _state(hp=50, enemies=[_enemy(hp=200)])
        _play(state, "ep_ejecucion")
        assert state.player.current_hp == 50


class TestWarriorPowers:
    def test_sangre_hirviente(self):
        state = _state(draw=_filler(10), enemies=[_enemy(intent=0)])
        _play(state, "wr_sangre_hirviente", None)
        end_player_turn(state)
        assert state.player.current_hp == 98 and state.hero_strength == 1
        assert state.hp_lost_this_turn == 2           # turns Furia on for the new turn

    def test_regeneracion(self):
        state = _state(hp=50, draw=_filler(10), enemies=[_enemy(intent=0)])
        _play(state, "wr_regeneracion", None)
        end_player_turn(state)
        assert state.player.current_hp == 53

    def test_segunda_piel(self):
        state = _state()
        _play(state, "wr_segunda_piel", None)
        state.lose_hp(2)
        assert state.player.block == 3

    def test_segunda_piel_on_enemy_hit(self):
        state = _state(draw=_filler(10), enemies=[_enemy(intent=5, eid="a"), _enemy(intent=5, eid="b")])
        _play(state, "wr_segunda_piel", None)
        state.retain_block = True
        end_player_turn(state)
        # hit 1: -5 HP, +3 block; hit 2: block absorbs 3, -2 HP, +3 block again
        assert state.player.current_hp == 93 and state.player.block == 3

    def test_fortaleza_interior(self):
        state = _state(hp=50)
        _play(state, "wr_fortaleza_interior", None)
        state.heal_hero(4)
        assert state.player.block == 2

    def test_piel_de_acero(self):
        state = _state(draw=_filler(10), enemies=[_enemy(intent=4)])
        _play(state, "wr_piel_acero", None)
        end_player_turn(state)
        assert state.player.current_hp == 100

    def test_berserker(self):
        state = _state()
        _play(state, "wr_berserker", None)
        state.lose_hp(1)
        state.lose_hp(1)
        assert state.hero_strength == 2

    def test_voluntad_caps_self_damage(self):
        state = _state()
        _play(state, "wr_voluntad_hierro", None)
        _play(state, "wr_hachazo_temerario")
        assert state.player.current_hp == 99 and state.enemies[0].current_hp == 76

    def test_golden_power_stacks_twice(self):
        state = _state()
        card = _card("wr_berserker")
        card.chroma = G
        state.hand.cards.append(card)
        play_card(state, 0, None)
        assert state.strength_on_hp_loss == 2


class TestWarriorPool:
    def test_thirty_six_new_cards(self):
        assert len(WARRIOR_IDS) == 36

    def test_new_cards_are_warrior(self):
        assert all(CARD_CLASS_BY_ID[cid] is CardClass.WARRIOR for cid in WARRIOR_IDS)

    def test_review_changes(self):
        assert _card("wr_golpe_escudo").rarity is CardRarity.RARE
        assert _card("wr_torbellino_acero").rarity is CardRarity.RARE
        assert _card("wr_doblar_escudo").rarity is CardRarity.LEGENDARY
        assert _card("wr_transfusion").cost == 2
        assert _card("wr_berserker").cost == 2
        assert _card("wr_pacto_hierro").total_mana_gain() == 1

    def test_retribucion_is_neutral(self):
        assert CARD_CLASS_BY_ID["e_retribucion"] is CardClass.NEUTRAL

    def test_kept_cards_stay_warrior(self):
        for cid in ("m_grito_de_guerra", "m_conjuro", "ep_bastion"):
            assert CARD_CLASS_BY_ID[cid] is CardClass.WARRIOR

    def test_baluarte_and_escudo_impenetrable_have_endure(self):
        assert Keyword.ENDURE in _card("e_baluarte").keywords()
        assert Keyword.ENDURE in _card("ep_escudo_impenet").keywords()

    def test_every_theme_fills_a_pack(self):
        for theme in PackTheme:
            assert len(card_factories_for_theme(theme, {CardClass.NEUTRAL, CardClass.WARRIOR})) >= PACK_SIZE

    def test_every_card_plays_without_error(self):
        for factory in card_factories_for_classes({CardClass.WARRIOR}):
            state = _state(enemies=[_enemy(eid="a"), _enemy(eid="b")], draw=_filler(5), mana=10)
            state.player.block = 3
            state.lose_hp(1)
            state.hand.cards.append(factory())
            result = play_card(state, 0, 0)
            assert result.success, factory.card_id


# ---------------------------------------------------------------------------
# Relics
# ---------------------------------------------------------------------------

class TestWarriorRelics:
    def test_defs(self):
        defs = {r.tag: r for r in _all_relic_defs()}
        for tag in (RelicTag.IRON_FANG, RelicTag.SOAKED_BANDAGE, RelicTag.BLOOD_CUP,
                    RelicTag.TORN_BANNER, RelicTag.TITAN_HEART):
            assert defs[tag].relic_class is CardClass.WARRIOR
        assert defs[RelicTag.SCAR].relic_class is CardClass.NEUTRAL
        assert defs[RelicTag.WAR_BRACER].relic_class is CardClass.NEUTRAL

    def test_rarities(self):
        assert RELIC_RARITY[RelicTag.SCAR] is Rarity.COMMON
        assert RELIC_RARITY[RelicTag.TITAN_HEART] is Rarity.LEGENDARY

    def test_scar_and_bracer_at_combat_start(self):
        state = _state(relics=[_relic(RelicTag.SCAR), _relic(RelicTag.WAR_BRACER)], draw=_filler(10))
        draw_opening_hand(state)
        assert state.hero_strength == 1 and state.player.block == 8

    def test_golden_scar(self):
        state = _state(relics=[_relic(RelicTag.SCAR, G)], draw=_filler(10))
        draw_opening_hand(state)
        assert state.hero_strength == 2

    def test_iron_fang_first_attack_only(self):
        state = _state(hp=50, relics=[_relic(RelicTag.IRON_FANG)])
        _play(state, "wr_tajo_brutal")
        _play(state, "wr_tajo_brutal")
        assert state.player.current_hp == 52

    def test_soaked_bandage_draws_once_per_turn(self):
        state = _state(relics=[_relic(RelicTag.SOAKED_BANDAGE)], draw=_filler(5))
        _play(state, "wr_corte_sangriento")
        _play(state, "wr_corte_sangriento")
        assert state.hand.count == 1

    def test_blood_cup(self):
        state = _state(hp=50, relics=[_relic(RelicTag.BLOOD_CUP)])
        state.heal_hero(5)
        assert state.player.current_hp == 57

    def test_torn_banner_every_third_fury(self):
        state = _state(relics=[_relic(RelicTag.TORN_BANNER)])
        state.lose_hp(1)
        for _ in range(3):
            _play(state, "wr_tajo_brutal")
        assert state.hero_strength == 1 and state.furies == 3

    def test_titan_heart_doubles_overflow(self):
        state = _state(hp=98, relics=[_relic(RelicTag.TITAN_HEART)])
        state.heal_hero(5)
        assert state.player.block == 6

    def test_count_fury_without_banner(self):
        state = _state()
        for _ in range(3):
            relic_effects.count_fury(state)
        assert state.hero_strength == 0


# ---------------------------------------------------------------------------
# Starter decks
# ---------------------------------------------------------------------------

class TestStarterDecks:
    @pytest.mark.parametrize("cid, cls", [(CharacterId.WARRIOR, CardClass.WARRIOR),
                                          (CharacterId.MAGE, CardClass.MAGE)])
    def test_ten_cards_of_the_class(self, cid, cls):
        deck = starter_deck(cid)
        assert len(deck) == 10
        assert all(c.card_class is cls and c.rarity is CardRarity.COMMON for c in deck)

    @pytest.mark.parametrize("cid", [CharacterId.WARRIOR, CharacterId.MAGE])
    def test_five_attacks_five_blocks(self, cid):
        deck = starter_deck(cid)
        assert sum(c.card_type is CardType.ATTACK for c in deck) == 5
        assert sum(c.card_type is CardType.SKILL for c in deck) == 5

    def test_warrior_class_card_has_endure(self):
        guard = [c for c in starter_deck(CharacterId.WARRIOR) if c.keywords()]
        assert [c.name for c in guard] == ["Guardia Férrea"]
        assert Keyword.ENDURE in guard[0].keywords()

    def test_mage_class_card_applies_fire(self):
        spark = [c for c in starter_deck(CharacterId.MAGE) if c.element_badges()]
        assert [c.name for c in spark] == ["Chispa Ígnea"]

    def test_rogue_deck_unchanged(self):
        assert len(starter_deck(CharacterId.ROGUE)) == 9

    def test_fresh_cards_each_call(self):
        assert starter_deck(CharacterId.WARRIOR)[0] is not starter_deck(CharacterId.WARRIOR)[0]
