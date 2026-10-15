"""Mage elements (Fuego, Agua, Tierra, Aire), reactions, keyword Reacción and the Mage cards.

Covers the element rules on their own (stacking, one element at a time, what each
does), the six reactions with their numbers, the reaction powers (Piel de Granito,
Ojo del Huracán, Catalizador, Archimago), Reacción / Vacío on the new cards, golden
casts, the enemy turn (Fuego burn, Congelado, Agua, Vulnerable) and stress runs
(10^9 stacks, 300 random plays). No pygame.
"""
from __future__ import annotations

import random

from src.application.end_turn import end_player_turn
from src.application.play_card import TargetKind, play_card, requires_target, target_kind
from src.domain.card import CardClass
from src.domain.card_pool import CARD_CLASS_BY_ID, card_factories_for_classes
from src.domain.chroma import Chroma
from src.domain.combat import CombatState
from src.domain.elements import (
    ELEMENT_NAMES, MUD_BLOCK_MULT, REACTIONS, STEAM_MULT, Element, Reaction, apply_element,
    card_reacts, element_of, element_stacks, would_react,
)
from src.domain.entities import (
    FROZEN, VULNERABLE, WEAK, Enemy, Intent, IntentType, Player, enemy_hit_damage, status_stacks,
)
from src.domain.keywords import KEYWORD_DEFS, Keyword
from src.domain.mana import Mana
from src.domain.pile import DiscardPile, DrawPile, Hand
from src.domain.card_pool import _atk


def _card(card_id: str):
    for f in card_factories_for_classes({CardClass.MAGE}):
        if f.card_id == card_id:
            return f()
    raise KeyError(card_id)


def _enemy(i: int = 1, hp: int = 100, attack: int = 10, **kw) -> Enemy:
    return Enemy(id=f"e{i}", name=f"Enemigo {i}", max_hp=hp, current_hp=hp,
                 intent=Intent(IntentType.ATTACK, attack), **kw)


def _state(hand=(), enemies=None, mana: int = 4, draw=None, attack_bonus: int = 0) -> CombatState:
    return CombatState(
        player=Player(name="Mago", max_hp=60, current_hp=60, attack_bonus=attack_bonus),
        enemies=enemies if enemies is not None else [_enemy()],
        hand=Hand(cards=list(hand)),
        draw_pile=DrawPile(cards=list(draw or [_atk("x", "Relleno", 1, 1) for _ in range(20)])),
        discard_pile=DiscardPile(cards=[]),
        mana=Mana(current=mana, maximum=4),
    )


def _with(enemy: Enemy, element: Element, stacks: int) -> Enemy:
    apply_element(_state(enemies=[enemy]), enemy, element, stacks)
    return enemy


# ---------------------------------------------------------------- element rules

class TestApplyElement:
    def test_first_element_is_put(self):
        e = _with(_enemy(), Element.FIRE, 3)
        assert (element_of(e), element_stacks(e)) == (Element.FIRE, 3)

    def test_same_element_stacks(self):
        e = _with(_with(_enemy(), Element.WATER, 2), Element.WATER, 5)
        assert element_stacks(e, Element.WATER) == 7

    def test_zero_or_negative_stacks_do_nothing(self):
        e = _enemy()
        assert apply_element(_state(enemies=[e]), e, Element.FIRE, 0) == []
        assert apply_element(_state(enemies=[e]), e, Element.FIRE, -3) == []
        assert e.status_effects == []

    def test_dead_enemy_gets_nothing(self):
        e = _enemy(hp=0)
        e.current_hp = 0
        assert apply_element(_state(enemies=[e]), e, Element.FIRE, 2) == [] and e.status_effects == []

    def test_different_element_reacts_and_clears_both(self):
        e = _with(_enemy(), Element.FIRE, 3)
        s = _state(enemies=[e])
        assert apply_element(s, e, Element.EARTH, 1) == [Reaction.MAGMA]
        assert element_of(e) is None

    def test_every_pair_has_a_reaction(self):
        names = [Element.FIRE, Element.WATER, Element.EARTH, Element.AIR]
        pairs = {frozenset({a, b}) for a in names for b in names if a is not b}
        assert set(REACTIONS) == pairs and len(REACTIONS) == 6

    def test_would_react(self):
        e = _with(_enemy(), Element.AIR, 1)
        assert would_react(e, Element.FIRE) and not would_react(e, Element.AIR)
        assert not would_react(_enemy(), Element.FIRE)

    def test_huge_stacks(self):
        e = _with(_with(_enemy(hp=10 ** 12), Element.FIRE, 10 ** 9), Element.FIRE, 10 ** 9)
        assert element_stacks(e) == 2 * 10 ** 9


class TestElementsAlone:
    def test_earth_adds_damage_per_hit(self):
        e = _with(_enemy(), Element.EARTH, 3)
        s = _state([_atk("a", "Golpe", 1, 6)], enemies=[e])
        play_card(s, 0, 0)
        assert e.current_hp == 100 - 9

    def test_water_lowers_enemy_hits(self):
        e = _with(_enemy(attack=10), Element.WATER, 4)
        assert enemy_hit_damage(e, Player("P", 50, 50)) == 6

    def test_water_never_below_zero(self):
        e = _with(_enemy(attack=3), Element.WATER, 10 ** 9)
        assert enemy_hit_damage(e, Player("P", 50, 50)) == 0

    def test_fire_burns_at_end_of_enemy_turn_and_stays(self):
        e = _with(_enemy(attack=0), Element.FIRE, 5)
        s = _state(enemies=[e])
        end_player_turn(s)
        assert e.current_hp == 95 and element_stacks(e, Element.FIRE) == 5

    def test_fire_burn_ignores_block(self):
        e = _with(_enemy(attack=0), Element.FIRE, 4)
        e.intent = Intent(IntentType.BLOCK, 50)
        s = _state(enemies=[e])
        end_player_turn(s)
        assert e.current_hp == 96

    def test_fire_burn_can_kill(self):
        e = _with(_enemy(hp=3, attack=0), Element.FIRE, 9)
        s = _state(enemies=[e])
        end_player_turn(s)
        assert s.enemies == []


# ---------------------------------------------------------------- reactions

class TestReactions:
    def test_steam_deals_double_total(self):
        e = _with(_enemy(), Element.FIRE, 3)
        apply_element(_state(enemies=[e]), e, Element.WATER, 2)
        assert e.current_hp == 100 - STEAM_MULT * 5

    def test_steam_goes_through_block(self):
        e = _with(_enemy(), Element.FIRE, 3)
        e.block = 4
        apply_element(_state(enemies=[e]), e, Element.WATER, 2)
        assert (e.block, e.current_hp) == (0, 94)

    def test_magma_breaks_block_and_vulnerable(self):
        e = _with(_enemy(), Element.EARTH, 1)
        e.block = 30
        apply_element(_state(enemies=[e]), e, Element.FIRE, 1)
        assert e.block == 0 and status_stacks(e.status_effects, VULNERABLE) == 2

    def test_vulnerable_enemy_takes_more_from_cards(self):
        e = _with(_enemy(), Element.EARTH, 1)
        apply_element(_state(enemies=[e]), e, Element.FIRE, 1)
        s = _state([_atk("a", "Golpe", 1, 10)], enemies=[e])
        play_card(s, 0, 0)
        assert e.current_hp == 85

    def test_wildfire_spreads_total_fire(self):
        a, b, c = _enemy(1), _enemy(2), _enemy(3)
        s = _state(enemies=[a, b, c])
        apply_element(s, a, Element.AIR, 1)
        apply_element(s, a, Element.FIRE, 3)
        assert [element_stacks(x, Element.FIRE) for x in (a, b, c)] == [4, 4, 4]

    def test_wildfire_chains_into_other_reactions_once(self):
        a, b = _enemy(1), _enemy(2)
        s = _state(enemies=[a, b])
        apply_element(s, b, Element.WATER, 1)
        apply_element(s, a, Element.AIR, 1)
        reacted = apply_element(s, a, Element.FIRE, 1)
        assert reacted == [Reaction.WILDFIRE]
        assert b.current_hp == 100 - STEAM_MULT * 3 and element_of(b) is None
        assert [ev.reaction for ev in s.reaction_log] == [Reaction.STEAM, Reaction.WILDFIRE]

    def test_mud_gives_triple_block(self):
        e = _with(_enemy(), Element.WATER, 2)
        s = _state(enemies=[e])
        apply_element(s, e, Element.EARTH, 2)
        assert s.player.block == MUD_BLOCK_MULT * 4

    def test_freeze_skips_regular_enemy_action(self):
        e = _with(_enemy(attack=20), Element.WATER, 1)
        s = _state(enemies=[e])
        apply_element(s, e, Element.AIR, 1)
        assert enemy_hit_damage(e, s.player) == 0
        end_player_turn(s)
        assert s.player.current_hp == 60 and status_stacks(e.status_effects, FROZEN) == 0

    def test_freeze_halves_boss_damage(self):
        e = _with(_enemy(attack=20, is_boss=True), Element.WATER, 1)
        s = _state(enemies=[e])
        apply_element(s, e, Element.AIR, 1)
        end_player_turn(s)
        assert s.player.current_hp == 50 and status_stacks(e.status_effects, FROZEN) == 0

    def test_freeze_does_not_stack(self):
        e = _enemy()
        s = _state(enemies=[e])
        for _ in range(3):
            apply_element(s, e, Element.WATER, 1)
            apply_element(s, e, Element.AIR, 1)
        assert status_stacks(e.status_effects, FROZEN) == 1

    def test_sandstorm_weakens_everyone(self):
        a, b = _enemy(1), _enemy(2)
        s = _state(enemies=[a, b])
        apply_element(s, a, Element.EARTH, 1)
        apply_element(s, a, Element.AIR, 1)
        assert all(status_stacks(x.status_effects, WEAK) == 1 for x in (a, b))

    def test_reaction_counter_and_log(self):
        e = _enemy()
        s = _state(enemies=[e])
        apply_element(s, e, Element.FIRE, 1)
        apply_element(s, e, Element.WATER, 1)
        assert s.reactions_this_turn == 1 and s.reaction_log[0].stacks == 2

    def test_huge_steam(self):
        e = _with(_enemy(hp=10 ** 30), Element.FIRE, 10 ** 18)
        apply_element(_state(enemies=[e]), e, Element.WATER, 10 ** 18)
        assert e.current_hp == 10 ** 30 - 4 * 10 ** 18


class TestReactionPowers:
    def test_granite_skin_block_per_reaction(self):
        e = _enemy()
        s = _state([_card("mg_piel_granito")], enemies=[e])
        play_card(s, 0)
        apply_element(s, e, Element.FIRE, 1)
        apply_element(s, e, Element.AIR, 1)
        assert s.player.block == 4

    def test_hurricane_eye_draws_per_reaction(self):
        e = _with(_enemy(), Element.FIRE, 1)
        s = _state([_card("mg_ojo_huracan"), _card("mg_gota")], enemies=[e])
        play_card(s, 0)
        play_card(s, 0, 0)            # Gota: Agua → Vapor → draw 1
        assert s.hand.count == 1

    def test_catalyst_doubles_next_reaction_only(self):
        e = _with(_enemy(), Element.FIRE, 1)
        s = _state([_card("mg_catalizador"), _card("mg_gota")], enemies=[e])
        play_card(s, 0)
        play_card(s, 0, 0)            # 2 dmg + Vapor (3 stacks → 6) twice
        assert e.current_hp == 100 - 2 - 12 and s.catalyst == 0

    def test_catalyst_expires_at_end_of_turn(self):
        s = _state([_card("mg_catalizador")], enemies=[_enemy(attack=0)])
        play_card(s, 0)
        end_player_turn(s)
        assert s.catalyst == 0

    def test_archmage_steam_hits_everyone(self):
        a, b = _enemy(1), _enemy(2)
        s = _state([_card("mg_archimago")], enemies=[a, b])
        play_card(s, 0)
        apply_element(s, a, Element.FIRE, 2)
        apply_element(s, a, Element.WATER, 3)
        assert (a.current_hp, b.current_hp) == (90, 90)

    def test_fire_heart_at_turn_start(self):
        a, b = _enemy(1, attack=0), _enemy(2, attack=0)
        s = _state([_card("mg_corazon_igneo")], enemies=[a, b])
        play_card(s, 0)
        end_player_turn(s)
        assert element_stacks(a, Element.FIRE) == 1 and element_stacks(b, Element.FIRE) == 1


# ---------------------------------------------------------------- keyword Reacción

class TestReactionKeyword:
    def test_keyword_defined(self):
        assert KEYWORD_DEFS[Keyword.REACTION].name == "Reacción"
        assert " si " not in KEYWORD_DEFS[Keyword.REACTION].rule.split(":", 1)[0]

    def test_ready_only_when_an_enemy_would_react(self):
        card = _card("mg_vapor_hirviente")         # applies Agua
        e = _enemy()
        s = _state([card], enemies=[e])
        assert not s.reaction_ready(card)
        apply_element(s, e, Element.WATER, 1)
        assert not s.reaction_ready(card)
        e.status_effects.clear()
        apply_element(s, e, Element.FIRE, 1)
        assert s.reaction_ready(card)

    def test_ready_checks_the_chosen_target(self):
        card = _card("mg_grieta")                  # applies Tierra
        a, b = _enemy(1), _with(_enemy(2), Element.FIRE, 1)
        s = _state([card], enemies=[a, b])
        assert s.reaction_ready(card) and not s.reaction_ready(card, 0) and s.reaction_ready(card, 1)

    def test_layer_resolves_on_reaction(self):
        e = _with(_enemy(), Element.FIRE, 1)
        s = _state([_card("mg_vapor_hirviente")], enemies=[e], mana=1)
        result = play_card(s, 0, 0)
        assert result.reaction and result.reactions == ["Vapor"]
        assert s.mana.current == 1 and s.hand.count == 0

    def test_layer_does_not_resolve_without_reaction(self):
        s = _state([_card("mg_vapor_hirviente")], mana=1)
        result = play_card(s, 0, 0)
        assert not result.reaction and s.mana.current == 0 and s.hand.count == 0

    def test_llamarada_extra_damage(self):
        e = _with(_enemy(), Element.WATER, 1)
        s = _state([_card("mg_llamarada")], enemies=[e])
        play_card(s, 0, 0)          # 12 dmg, then Vapor (3 stacks → 6)
        assert e.current_hp == 100 - 12 - 6

    def test_grieta_block(self):
        e = _with(_enemy(), Element.AIR, 1)
        s = _state([_card("mg_grieta")], enemies=[e])
        play_card(s, 0, 0)
        assert s.player.block == 6

    def test_keyword_layers_never_add_a_condition(self):
        for f in card_factories_for_classes({CardClass.MAGE}):
            c = f()
            for fx in c.reaction_effects() + c.void_effects():
                assert " si " not in f" {fx.text} "


# ---------------------------------------------------------------- the cards

class TestMageCards:
    def test_all_new_cards_are_mage(self):
        ids = [k for k in CARD_CLASS_BY_ID if k.startswith("mg_")]
        assert len(ids) == 28 and {CARD_CLASS_BY_ID[k] for k in ids} == {CardClass.MAGE}

    def test_arcane_spark_without_void(self):
        e = _enemy()
        s = _state([_card("mg_chispa_arcana")], enemies=[e], mana=4)
        play_card(s, 0, 0)
        assert e.current_hp == 96 and element_stacks(e, Element.FIRE) == 2

    def test_arcane_spark_void_causes_steam(self):
        e = _enemy()
        s = _state([_card("mg_chispa_arcana")], enemies=[e], mana=1)
        result = play_card(s, 0, 0)
        assert result.void and e.current_hp == 100 - 4 - STEAM_MULT * 4 and element_of(e) is None

    def test_targeting(self):
        assert target_kind(_card("mg_brisa")) is TargetKind.ALL_ENEMIES
        assert target_kind(_card("mg_ola")) is TargetKind.ALL_ENEMIES
        assert target_kind(_card("mg_muro_roca")) is TargetKind.ENEMY
        assert target_kind(_card("mg_avivar")) is TargetKind.ENEMY
        assert target_kind(_card("mg_piel_granito")) is TargetKind.SELF
        assert requires_target(_card("mg_remolino"))

    def test_avivar_doubles_fire(self):
        e = _with(_enemy(), Element.FIRE, 3)
        s = _state([_card("mg_avivar")], enemies=[e])
        play_card(s, 0, 0)
        assert element_stacks(e, Element.FIRE) == 6

    def test_combustion_consumes_fire(self):
        e = _with(_enemy(), Element.FIRE, 4)
        s = _state([_card("mg_combustion")], enemies=[e], mana=4)
        play_card(s, 0, 0)
        assert e.current_hp == 88 and element_of(e) is None

    def test_combustion_void_hits_all(self):
        a, b = _with(_enemy(1), Element.FIRE, 2), _with(_enemy(2), Element.FIRE, 5)
        s = _state([_card("mg_combustion")], enemies=[a, b], mana=2)
        play_card(s, 0, 0)
        assert (a.current_hp, b.current_hp) == (94, 85)

    def test_avalanche_scales_with_earth(self):
        e = _with(_enemy(), Element.EARTH, 2)
        s = _state([_card("mg_avalancha")], enemies=[e])
        play_card(s, 0, 0)          # 6 + 2 (Tierra) then 8 + 2 (Tierra)
        assert e.current_hp == 100 - 8 - 10

    def test_convergence_chain(self):
        a, b = _enemy(1), _enemy(2)
        s = _state([_card("mg_convergencia")], enemies=[a, b])
        result = play_card(s, 0, 0)
        assert result.reactions == ["Vapor", "Tormenta de Arena"]
        assert a.current_hp == 92 and status_stacks(b.status_effects, WEAK) == 1

    def test_ola_and_ciclon_hit_all(self):
        a, b = _enemy(1), _enemy(2)
        s = _state([_card("mg_ola"), _card("mg_ciclon")], enemies=[a, b])
        play_card(s, 0)
        assert [x.current_hp for x in (a, b)] == [94, 94]
        play_card(s, 0)             # Aire meets Agua → Congelar on both
        assert all(status_stacks(x.status_effects, FROZEN) == 1 for x in (a, b))

    def test_rafaga_hits_twice(self):
        e = _enemy()
        s = _state([_card("mg_rafaga")], enemies=[e], attack_bonus=8)
        play_card(s, 0, 0)
        assert e.current_hp == 100 - 11 - 3

    def test_burbuja_void_keeps_block(self):
        s = _state([_card("mg_burbuja")], enemies=[_enemy(attack=0)], mana=1)
        play_card(s, 0)
        end_player_turn(s)
        assert s.player.block == 8

    def test_marea_void_extra_block(self):
        e = _enemy()
        s = _state([_card("mg_marea")], enemies=[e], mana=1)
        play_card(s, 0, 0)
        assert s.player.block == 10 and element_stacks(e, Element.WATER) == 2

    def test_corriente_void(self):
        s = _state([_card("mg_corriente")], mana=1)
        play_card(s, 0)
        assert s.mana.current == 1 and s.hand.count == 3

    def test_golden_card_applies_twice(self):
        card = _card("mg_bola_fuego")
        card.chroma = Chroma.GOLDEN
        e = _enemy()
        s = _state([card], enemies=[e])
        play_card(s, 0, 0)
        assert element_stacks(e, Element.FIRE) == 6 and e.current_hp == 84

    def test_card_reacts_helper(self):
        s = _state(enemies=[_with(_enemy(), Element.WATER, 1)])
        assert card_reacts(s, _card("mg_brisa")) and not card_reacts(s, _card("mg_gota"))


class TestStress:
    def test_300_random_plays_keep_invariants(self):
        rng = random.Random(7)
        factories = [f for f in card_factories_for_classes({CardClass.MAGE}) if f.card_id.startswith("mg_")]
        for _ in range(300):
            enemies = [_enemy(i, hp=rng.randint(1, 200), attack=rng.randint(0, 20)) for i in range(1, 4)]
            for e in enemies:
                if rng.random() < 0.6:
                    _with(e, rng.choice(list(Element)), rng.randint(1, 10))
            s = _state([rng.choice(factories)() for _ in range(5)], enemies=enemies, mana=rng.randint(0, 4))
            for _ in range(5):
                if not s.hand.count or not s.living_enemies():
                    break
                alive = [i for i, e in enumerate(s.enemies) if e.is_alive]
                play_card(s, rng.randrange(s.hand.count), rng.choice(alive))
            for e in s.enemies:
                held = [se.name for se in e.status_effects if se.name in ELEMENT_NAMES]
                assert len(held) <= 1 and e.current_hp >= 0
            if s.living_enemies():
                end_player_turn(s)
            assert s.player.current_hp >= 0
