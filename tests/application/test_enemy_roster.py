"""Regular enemies: identities, patterns, pairs, Venganza and the new enemy-turn extras.

Scope: ``application/enemy_roster.py``, its hooks in ``enemy_ai``/``end_turn``/``play_card``,
``run_manager.generate_enemies`` and the Pruebas encounter knob. Covers every enemy's
moves (and that each has a matching animation), floor scaling, pairs (partners, names,
80 % HP, floor gating), encounter odds over many seeds, vampire bite, golem wall kept by
its partner, acolyte blessing and prayer, the Seta's Mecha countdown and explosion,
Venganza (after a kill, after an explosion, once), and a 300-turn stress per encounter.
"""
from __future__ import annotations

import random

import pytest

from src.application import enemy_ai
from src.application import enemy_roster as R
from src.application.end_turn import _execute_intent, end_player_turn
from src.application.play_card import play_card
from src.application.run_manager import create_run, generate_enemies
from src.domain.card import Card, CardEffect, CardType
from src.domain.character import ALL_CHARACTERS
from src.domain.combat import CombatState
from src.domain.entities import (FUSE, POISON, STRENGTH, Enemy, Intent, IntentType, Player,
                                 status_stacks)
from src.domain.mana import Mana
from src.domain.numbers import BigValue
from src.domain.pile import DiscardPile, DrawPile, Hand
from src.domain.tuning import TUNING
from src.infrastructure.enemy_sprites import ENEMY_SHEET_IDS, load_enemy_sheet


def _plain(cid="c", damage=0) -> Card:
    return Card(id=cid, name=cid, card_type=CardType.ATTACK, cost=0,
                base_effect=CardEffect(name=cid, damage=BigValue(damage)))


def _state(enemies, *, hp=100, hand=None) -> CombatState:
    return CombatState(
        player=Player(name="Héroe", max_hp=hp, current_hp=hp), enemies=list(enemies),
        hand=Hand(cards=list(hand or [])),
        draw_pile=DrawPile(cards=[_plain(f"d{i}") for i in range(40)]),
        discard_pile=DiscardPile(cards=[]), mana=Mana(current=3, maximum=3))


def _moves(ai: str, turns: int = 12) -> list[Intent]:
    enemy = R.create_enemy(ai)
    out = [enemy.intent]
    for _ in range(turns):
        out.append(R.next_intent(enemy, None, [enemy]))
    return out


# ---------------------------------------------------------------------------
# Catalogue
# ---------------------------------------------------------------------------

class TestCatalogue:
    def test_eleven_enemies(self):
        assert len(R.ENEMIES) == 11

    def test_names_unique(self):
        assert len({d.name for d in R.ENEMIES.values()}) == 11

    @pytest.mark.parametrize("ai", list(R.ENEMIES))
    def test_each_has_a_sheet(self, ai):
        sheet = load_enemy_sheet(ENEMY_SHEET_IDS[R.ENEMIES[ai].name])
        assert sheet is not None and "death" in sheet.animations

    @pytest.mark.parametrize("ai", list(R.ENEMIES))
    def test_identity_texts(self, ai):
        d = R.ENEMIES[ai]
        assert d.identity and d.title.endswith(".")

    @pytest.mark.parametrize("ai", [a for a in R.ENEMIES if a != R.WRAITH])
    def test_every_move_has_its_animation(self, ai):
        sheet = load_enemy_sheet(ENEMY_SHEET_IDS[R.ENEMIES[ai].name])
        ids = {i.move_id for i in _moves(ai)} | {R.VENGEANCE_ID}
        if ai == R.ACOLYTE:
            ids.add("mend")
        assert ids <= set(sheet.moves)

    @pytest.mark.parametrize("ai", list(R.ENEMIES))
    def test_every_move_named_and_described(self, ai):
        assert all(i.move and i.move_id and i.description for i in _moves(ai))

    @pytest.mark.parametrize("ai", list(R.ENEMIES))
    def test_pattern_enemy(self, ai):
        e = R.create_enemy(ai)
        assert enemy_ai.has_pattern(e) and not e.is_boss and e.current_hp == e.max_hp == R.ENEMIES[ai].hp

    def test_floor_scaling(self):
        assert R.create_enemy(R.GOLEM, 3).max_hp == int(72 * 1.3)
        assert R.create_enemy(R.SKULL, 3).intent.value == int(7 * 1.3)

    def test_huge_floor(self):
        e = R.create_enemy(R.IMP, 10 ** 6)
        assert e.max_hp > 10 ** 6 and e.intent.value > 0


class TestIdentities:
    def test_skull_escalates(self):
        kinds = [(i.move_id, i.buffs) for i in _moves(R.SKULL, 5)]
        assert kinds[2] == ("stoke", ((STRENGTH, 3),))

    def test_eye_mostly_debuffs(self):
        moves = _moves(R.EYE, 5)
        assert sum(i.intent_type == IntentType.DEBUFF for i in moves) == 4

    def test_imp_aggressive(self):
        moves = _moves(R.IMP, 7)
        assert sum(i.intent_type == IntentType.ATTACK for i in moves) == 6

    def test_mimic_feigns_then_bites(self):
        m = _moves(R.MIMIC, 3)
        assert m[0].move_id == "feign" and m[1].move_id == "chomp" and m[1].value == 18

    def test_bat_lifesteal_and_dive(self):
        m = _moves(R.BAT, 2)
        assert m[0].lifesteal and m[1].hits == 3

    def test_golem_alone_no_ally_block(self):
        assert R.create_enemy(R.GOLEM).intent.ally_block == 0

    def test_acolyte_alone_blesses_itself(self):
        i = R.create_enemy(R.ACOLYTE).intent
        assert i.buffs == ((STRENGTH, 2),) and i.ally_buffs == ()

    def test_acolyte_penance_when_nobody_hurt(self):
        e = R.create_enemy(R.ACOLYTE)
        R.next_intent(e, None, [e])
        assert R.next_intent(e, None, [e]).move_id == "penance"

    def test_acolyte_prays_when_hurt(self):
        e = R.create_enemy(R.ACOLYTE)
        e.current_hp -= 5
        R.next_intent(e, None, [e])
        assert R.next_intent(e, None, [e]).heal_allies == 8


# ---------------------------------------------------------------------------
# Pairs and encounters
# ---------------------------------------------------------------------------

class TestPairs:
    def test_six_pairs(self):
        assert len(R.PAIRS) == 6

    @pytest.mark.parametrize("key", list(R.PAIRS))
    def test_partners_linked(self, key):
        a, b = R.create_pair(key, 1, "x")
        assert a.partner_id == b.id and b.partner_id == a.id and a.pair == b.pair == R.PAIRS[key].name

    @pytest.mark.parametrize("key", list(R.PAIRS))
    def test_pair_hp_80_percent(self, key):
        for e in R.create_pair(key, 1, "x"):
            assert e.max_hp == int(R.ENEMIES[e.ai].hp * R.PAIR_HP_FACTOR)

    def test_golem_shields_partner(self):
        golem, slime = R.create_pair("muro")
        assert golem.intent.ally_block == 8

    def test_acolyte_blesses_partner(self):
        acolyte, skull = R.create_pair("culto")
        assert acolyte.intent.ally_buffs == ((STRENGTH, 2),)

    def test_ids_unique(self):
        ids = [e.id for e in R.create_pair("caceria", 1, "room")]
        assert len(set(ids)) == 2


class TestEncounters:
    def test_deterministic(self):
        a = [e.name for e in R.roll_encounter(random.Random(5), 2, "r")]
        b = [e.name for e in R.roll_encounter(random.Random(5), 2, "r")]
        assert a == b

    def test_floor1_pair_rate(self):
        pairs = sum(len(R.roll_encounter(random.Random(s), 1, "r")) == 2 for s in range(2000))
        assert 0.28 < pairs / 2000 < 0.42

    def test_floor1_no_treasure_trap_and_no_trio(self):
        for s in range(800):
            enemies = R.roll_encounter(random.Random(s), 1, "r")
            assert len(enemies) <= 2
            assert not any(e.pair == "Trampa del Tesoro" for e in enemies)

    def test_trios_from_floor3(self):
        sizes = {len(R.roll_encounter(random.Random(s), 3, "r")) for s in range(600)}
        assert sizes == {1, 2, 3}

    def test_every_enemy_appears(self):
        seen = {e.ai for s in range(1500) for e in R.roll_encounter(random.Random(s), 2, "r")}
        assert seen == set(R.ENEMIES)

    def test_forced(self):
        for idx in range(1, len(R.ENCOUNTERS) + 1):
            kind, key = R.ENCOUNTERS[idx - 1]
            enemies = R.roll_encounter(random.Random(1), 1, "r", idx)
            assert len(enemies) == (2 if kind == "pair" else 1)

    def test_forced_out_of_range_is_random(self):
        assert R.roll_encounter(random.Random(1), 1, "r", 999)

    def test_labels(self):
        assert R.encounter_label(0) == "Al azar"
        assert R.encounter_label(1) == "Espectro"
        assert R.encounter_label(len(R.ENCOUNTERS)).startswith("Pareja: ")
        assert R.encounter_label(10 ** 9) == "Al azar"

    def test_generate_enemies_uses_roster(self):
        run = create_run(ALL_CHARACTERS[0], 7)
        enemies = generate_enemies(run, "r3_c1")
        assert enemies and all(e.ai in R.ENEMIES for e in enemies)

    def test_generate_enemies_stable_seed(self):
        run = create_run(ALL_CHARACTERS[0], 7)
        assert [e.name for e in generate_enemies(run, "x")] == [e.name for e in generate_enemies(run, "x")]

    def test_pruebas_knob(self):
        TUNING.forced_encounter = len(R.ENEMIES) + 1      # first pair
        enemies = generate_enemies(create_run(ALL_CHARACTERS[0], 7), "r")
        assert len(enemies) == 2 and enemies[0].pair


# ---------------------------------------------------------------------------
# New enemy-turn extras
# ---------------------------------------------------------------------------

def _with(enemy: Enemy, intent: Intent) -> Enemy:
    enemy.intent = intent
    return enemy


class TestExtras:
    def test_lifesteal_heals_hp_lost(self):
        bat = R.create_enemy(R.BAT)
        bat.current_hp = 10
        st = _state([bat])
        action = _execute_intent(st, bat)
        assert action.healed == sum(action.hits) == 7 and bat.current_hp == 17

    def test_lifesteal_nothing_when_blocked(self):
        bat = R.create_enemy(R.BAT)
        bat.current_hp = 10
        st = _state([bat])
        st.player.block = 50
        assert _execute_intent(st, bat).healed == 0 and bat.current_hp == 10

    def test_lifesteal_capped_at_max(self):
        bat = R.create_enemy(R.BAT)
        bat.current_hp = bat.max_hp - 2
        _execute_intent(_state([bat]), bat)
        assert bat.current_hp == bat.max_hp

    def test_wall_block_survives_partner_turn(self):
        golem, slime = R.create_pair("muro")
        st = _state([golem, slime])
        end_player_turn(st)
        assert slime.block == 8 and golem.block == 10

    def test_ally_buffs(self):
        acolyte, skull = R.create_pair("culto")
        end_player_turn(_state([acolyte, skull]))
        assert status_stacks(skull.status_effects, STRENGTH) == 2
        assert status_stacks(acolyte.status_effects, STRENGTH) == 2

    def test_heal_allies(self):
        a = Enemy(id="a", name="A", max_hp=40, current_hp=20)
        b = Enemy(id="b", name="B", max_hp=40, current_hp=39)
        a.intent = Intent(IntentType.BUFF, move="Plegaria", move_id="mend", heal_allies=8)
        action = _execute_intent(_state([a, b]), a)
        assert (a.current_hp, b.current_hp, action.healed) == (28, 40, 9)

    def test_self_destruct(self):
        bomb = _with(R.create_enemy(R.BOMB), Intent(IntentType.ATTACK, 24, move="¡Explosión!",
                                                     move_id="explode", self_destruct=True))
        st = _state([bomb])
        action = _execute_intent(st, bomb)
        assert action.exploded and not bomb.is_alive and st.player.current_hp == 76


class TestBomb:
    def test_fuse_starts_at_3(self):
        assert status_stacks(R.create_enemy(R.BOMB).status_effects, FUSE) == R.BOMB_FUSE

    def test_countdown_and_blast(self):
        bomb = R.create_enemy(R.BOMB)
        st = _state([bomb], hp=200)
        seen = [bomb.intent.move_id]
        for _ in range(3):
            end_player_turn(st)
            if st.enemies:
                seen.append(st.enemies[0].intent.move_id)
        assert seen[:3] == ["puff", "swell", "explode"] and st.enemies == []
        assert st.player.current_hp < 200 - 20

    def test_killed_in_time_no_blast(self):
        bomb = R.create_enemy(R.BOMB)
        st = _state([bomb], hand=[_plain("k", 999)])
        play_card(st, 0, 0)
        end_player_turn(st)
        assert st.player.current_hp == 100 and not st.enemy_log


# ---------------------------------------------------------------------------
# Venganza
# ---------------------------------------------------------------------------

class TestVengeance:
    def test_partner_killed_by_card(self):
        acolyte, skull = R.create_pair("culto")
        st = _state([acolyte, skull], hand=[_plain("k", 999)])
        play_card(st, 0, 0)
        assert skull.intent.move_id == R.VENGEANCE_ID

    def test_resolves_strength_and_block(self):
        acolyte, skull = R.create_pair("culto")
        st = _state([acolyte, skull], hand=[_plain("k", 999)])
        play_card(st, 0, 0)
        end_player_turn(st)
        assert status_stacks(skull.status_effects, STRENGTH) == R.VENGEANCE_STRENGTH
        assert skull.intent.move_id != R.VENGEANCE_ID

    def test_only_once(self):
        a, b = R.create_pair("caceria")
        a.current_hp = 0
        assert R.react_to_deaths([a, b]) == [1]
        assert R.react_to_deaths([a, b]) == []

    def test_solo_never(self):
        e = R.create_enemy(R.IMP)
        assert R.react_to_deaths([e]) == [] and e.intent.move_id != R.VENGEANCE_ID

    def test_after_explosion(self):
        worm, bomb = R.create_pair("cementerio")
        st = _state([worm, bomb], hp=500)
        for _ in range(3):
            end_player_turn(st)
        assert [e.name for e in st.enemies] == ["Gusano de Tumba"]
        assert worm.intent.move_id == R.VENGEANCE_ID

    def test_unrelated_enemy_not_avenging(self):
        a, b = R.create_pair("caceria")
        c = R.create_enemy(R.GOLEM, 1, "c")
        a.current_hp = 0
        R.react_to_deaths([a, b, c])
        assert c.intent.move_id != R.VENGEANCE_ID


class TestStress:
    @pytest.mark.parametrize("idx", range(1, len(R.ENCOUNTERS) + 1))
    def test_300_turns(self, idx):
        TUNING.invincible = True
        st = _state(R.create_encounter(idx, 2, "s"), hp=10 ** 9)
        for _ in range(300):
            if not st.enemies:
                break
            end_player_turn(st)
            st.hand.cards.clear()
            for e in st.enemies:
                assert e.intent.intent_type is not IntentType.UNKNOWN and e.current_hp <= e.max_hp

    def test_poison_never_negative(self):
        worm = R.create_enemy(R.WORM)
        st = _state([worm], hp=10 ** 6)
        for _ in range(60):
            end_player_turn(st)
        assert status_stacks(st.player.status_effects, POISON) >= 0
