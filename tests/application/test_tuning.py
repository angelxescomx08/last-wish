"""Pruebas tuning: defaults, chroma chance overrides, cheats and persistence. No pygame."""
from __future__ import annotations

import json
import random

from src.application import relic_effects
from src.application.card_rewards import allowed_card_classes
from src.application.end_turn import end_player_turn
from src.application.run_manager import create_run, generate_event_gold, pick_shop_stock
from src.domain.card import CardClass
from src.domain.character import ALL_CHARACTERS
from src.domain.chroma import Chroma, roll_chroma
from src.domain.entities import Intent, IntentType
from src.domain.tuning import TUNING, Tuning, chroma_chance, chroma_key, default_chroma_chance
from src.infrastructure.dev_settings import apply_dict, load_dev_settings, save_dev_settings
from tests.application.test_play_card import _make_state

G = Chroma.GOLDEN


class TestDefaults:
    def test_defaults_are_normal_play(self):
        t = Tuning()
        assert (t.all_class_cards, t.starting_gold, t.gold_multiplier, t.invincible,
                t.extra_mana, t.extra_draw, t.extra_max_hp, t.chroma_chances) == \
               (False, 2000, 1.0, False, 0, 0, 0, {})

    def test_default_chances_come_from_definitions(self):
        assert chroma_chance(G, "card") == default_chroma_chance(G, "card") == 0.05
        assert chroma_chance(G, "relic") == 0.08
        assert chroma_chance(G, "pack") == 0.06

    def test_reset(self):
        TUNING.extra_draw = 4
        TUNING.chroma_chances["golden:card"] = 1.0
        TUNING.reset()
        assert TUNING.extra_draw == 0 and TUNING.chroma_chances == {}


class TestOverrides:
    def test_chroma_override_and_clamp(self):
        TUNING.chroma_chances[chroma_key(G, "card")] = 1.0
        assert roll_chroma(random.Random(3)) is G
        TUNING.chroma_chances[chroma_key(G, "card")] = 7.0
        assert chroma_chance(G, "card") == 1.0
        TUNING.chroma_chances[chroma_key(G, "card")] = 0.0
        assert all(roll_chroma(random.Random(s)) is None for s in range(200))

    def test_pack_chance_makes_golden_packs(self):
        TUNING.chroma_chances[chroma_key(G, "pack")] = 1.0
        run = create_run(ALL_CHARACTERS[0], 5)
        run.current_room_id = "shop"
        packs, _ = pick_shop_stock(run)
        assert [p.chroma for p in packs] == [G, G, G]

    def test_all_class_cards(self):
        run = create_run(ALL_CHARACTERS[0], 1)
        TUNING.all_class_cards = True
        assert allowed_card_classes(run) == frozenset(CardClass)

    def test_starting_gold_and_hp(self):
        TUNING.starting_gold = 12345
        TUNING.extra_max_hp = 50
        run = create_run(ALL_CHARACTERS[0], 1)
        assert run.gold == 12345
        assert run.player_max_hp == ALL_CHARACTERS[0].stats.max_hp + 50 == run.player_current_hp

    def test_gold_multiplier(self):
        run = create_run(ALL_CHARACTERS[0], 1)
        base = generate_event_gold(run, "e")
        TUNING.gold_multiplier = 3.0
        assert generate_event_gold(run, "e") == base * 3

    def test_extra_mana_draw_hp_bonuses(self):
        TUNING.extra_mana, TUNING.extra_draw, TUNING.extra_max_hp = 2, 3, 40
        assert relic_effects.bonus_starting_mana([]) == 2
        assert relic_effects.extra_draw_per_turn([]) == 3
        assert relic_effects.max_hp_bonus([]) == 40

    def test_invincible(self):
        state = _make_state([], player_hp=30)
        state.enemies[0].intent = Intent(IntentType.ATTACK, 25)
        TUNING.invincible = True
        end_player_turn(state)
        assert state.player.current_hp == 30


class TestPersistence:
    def test_round_trip(self, tmp_path=None):
        import tempfile, pathlib
        path = pathlib.Path(tempfile.mkdtemp()) / "dev.json"
        TUNING.extra_draw = 2
        TUNING.invincible = True
        TUNING.chroma_chances["golden:relic"] = 0.5
        save_dev_settings(path)
        TUNING.reset()
        load_dev_settings(path)
        assert TUNING.extra_draw == 2 and TUNING.invincible
        assert TUNING.chroma_chances == {"golden:relic": 0.5}

    def test_invalid_values_fall_back(self):
        t = Tuning()
        apply_dict({"extra_draw": "x", "gold_multiplier": float("nan"), "starting_gold": -5,
                    "chroma_chances": {"golden:card": 3, "bad": True}, "invincible": 1}, t)
        assert t.extra_draw == 0 and t.gold_multiplier == 1.0 and t.starting_gold == 0
        assert t.chroma_chances == {"golden:card": 1.0} and t.invincible is True

    def test_missing_or_broken_file_gives_defaults(self):
        import tempfile, pathlib
        folder = pathlib.Path(tempfile.mkdtemp())
        TUNING.extra_mana = 3
        load_dev_settings(folder / "missing.json")
        assert TUNING.extra_mana == 0
        bad = folder / "bad.json"
        bad.write_text("{not json", encoding="utf-8")
        TUNING.extra_mana = 3
        load_dev_settings(bad)
        assert TUNING.extra_mana == 0
        weird = folder / "list.json"
        weird.write_text(json.dumps([1, 2]), encoding="utf-8")
        load_dev_settings(weird)
        assert TUNING == Tuning()

    def test_stress_many_random_dicts(self):
        rng = random.Random(0)
        values = [None, True, "s", -1, 0, 3, 10 ** 100, 1.5, float("inf"), [], {}]
        for _ in range(2000):
            t = Tuning()
            apply_dict({k: rng.choice(values) for k in ("extra_draw", "extra_mana", "starting_gold",
                                                        "gold_multiplier", "extra_max_hp", "invincible")}, t)
            assert 0 <= t.extra_draw <= 20 and 0 <= t.extra_mana <= 20
            assert 0 <= t.starting_gold <= 1_000_000 and 0 <= t.gold_multiplier <= 100


class TestHeroStatBonuses:
    def test_defaults_zero(self):
        t = Tuning()
        assert (t.extra_luck, t.extra_damage, t.extra_dexterity) == (0, 0, 0)

    def test_damage_and_dexterity_reach_the_player(self):
        from src.application.combat_factory import create_combat_for_character, create_combat_from_run
        c = ALL_CHARACTERS[0]
        TUNING.extra_damage, TUNING.extra_dexterity = 5, 3
        for state in (create_combat_for_character(c), create_combat_from_run(create_run(c, 1), [])):
            assert state.player.attack_bonus == c.stats.damage + 5
            assert state.player.dexterity == c.stats.dexterity + 3

    def test_reset_clears_stats(self):
        TUNING.extra_luck = TUNING.extra_damage = TUNING.extra_dexterity = 9
        TUNING.reset()
        assert (TUNING.extra_luck, TUNING.extra_damage, TUNING.extra_dexterity) == (0, 0, 0)

    def test_persist_and_clamp(self):
        t = Tuning()
        apply_dict({"extra_luck": 20, "extra_damage": 4, "extra_dexterity": 2}, t)
        assert (t.extra_luck, t.extra_damage, t.extra_dexterity) == (20, 4, 2)
        apply_dict({"extra_luck": -3, "extra_damage": "x", "extra_dexterity": 10**9}, t)
        assert (t.extra_luck, t.extra_damage, t.extra_dexterity) == (0, 0, 10_000)

