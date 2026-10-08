"""Class card pools: own-class cards, neutral cards and relics that mix pools.

No pygame dependency.
"""
from __future__ import annotations

import pytest

from src.application import relic_effects
from src.application.card_rewards import allowed_card_classes, pick_pack_cards, pick_reward_cards
from src.application.run_manager import create_run
from src.domain.card import Card, CardClass, CardEffect, CardType
from src.domain.card_pool import (
    CARD_CLASS_BY_ID,
    CARD_CLASS_LABEL,
    PACK_SIZE,
    PackTheme,
    card_factories_for_classes,
    card_factories_for_theme,
    class_for_character,
    starter_deck,
)
from src.domain.character import ALL_CHARACTERS, CharacterId
from src.domain.relic import Relic

CLASSES = [CardClass.WARRIOR, CardClass.MAGE, CardClass.ROGUE]


def _run(character_id: CharacterId, seed: int = 1):
    return create_run(next(c for c in ALL_CHARACTERS if c.id == character_id), seed)


def _mix(*classes: CardClass, active: bool = True) -> Relic:
    return Relic("mix", "Reliquia de mezcla", "", card_classes=frozenset(classes), is_active=active)


# ---------------------------------------------------------------------------
# Domain
# ---------------------------------------------------------------------------

class TestCardClassDomain:
    def test_card_defaults_to_neutral(self):
        card = Card(id="x", name="X", card_type=CardType.ATTACK, cost=1, base_effect=CardEffect(name="X"))
        assert card.card_class is CardClass.NEUTRAL

    def test_starter_deck_is_neutral(self):
        assert {c.card_class for c in starter_deck()} == {CardClass.NEUTRAL}

    def test_every_class_matches_a_character(self):
        assert [class_for_character(c.id) for c in ALL_CHARACTERS] == CLASSES

    def test_every_class_has_a_label(self):
        assert set(CARD_CLASS_LABEL) == set(CardClass)

    def test_every_pool_card_is_mapped_and_no_stale_ids(self):
        ids = {f.card_id for t in PackTheme for f in card_factories_for_theme(t)}
        assert ids == set(CARD_CLASS_BY_ID)

    def test_factory_stamps_class_and_theme(self):
        for theme in PackTheme:
            for factory in card_factories_for_theme(theme):
                card = factory()
                assert card.card_class is factory.card_class is CARD_CLASS_BY_ID[card.id]
                assert factory.theme is theme

    @pytest.mark.parametrize("cls", CLASSES)
    def test_each_class_has_own_cards_in_every_theme(self, cls):
        for theme in PackTheme:
            assert len(card_factories_for_theme(theme, {cls})) >= 2

    @pytest.mark.parametrize("cls", CLASSES)
    def test_each_theme_fills_a_pack_for_every_class(self, cls):
        for theme in PackTheme:
            assert len(card_factories_for_theme(theme, {CardClass.NEUTRAL, cls})) >= PACK_SIZE

    def test_every_theme_has_neutral_cards(self):
        for theme in PackTheme:
            assert len(card_factories_for_theme(theme, {CardClass.NEUTRAL})) >= 2

    def test_filter_without_classes_returns_whole_theme(self):
        # 3 neutral + 3 Guerrera + 3 Mago + 19 Pícara (her 2026-10-04 expansion)
        theme = card_factories_for_theme(PackTheme.ACERO)
        assert len(theme) == 3 + 3 + 3 + 19
        per_class = {c: sum(f.card_class == c for f in theme) for c in CardClass}
        assert per_class == {CardClass.NEUTRAL: 3, CardClass.WARRIOR: 3, CardClass.MAGE: 3, CardClass.ROGUE: 19}

    def test_class_filter_across_themes(self):
        mage = card_factories_for_classes({CardClass.MAGE})
        assert len(mage) == 3 + 2 + 6 + 3
        assert {f.card_class for f in mage} == {CardClass.MAGE}

    def test_class_cards_are_exclusive(self):
        per_class = [{f.card_id for f in card_factories_for_classes({c})} for c in CLASSES]
        assert not (per_class[0] & per_class[1] or per_class[0] & per_class[2] or per_class[1] & per_class[2])


# ---------------------------------------------------------------------------
# Allowed classes and relics
# ---------------------------------------------------------------------------

class TestAllowedClasses:
    @pytest.mark.parametrize("cid,cls", [(CharacterId.WARRIOR, CardClass.WARRIOR),
                                          (CharacterId.MAGE, CardClass.MAGE),
                                          (CharacterId.ROGUE, CardClass.ROGUE)])
    def test_run_allows_neutral_and_own_class(self, cid, cls):
        assert allowed_card_classes(_run(cid)) == frozenset({CardClass.NEUTRAL, cls})

    def test_relic_mixes_in_another_class(self):
        run = _run(CharacterId.WARRIOR)
        run.add_relic(_mix(CardClass.MAGE))
        assert allowed_card_classes(run) == frozenset({CardClass.NEUTRAL, CardClass.WARRIOR, CardClass.MAGE})

    def test_relic_can_mix_every_class(self):
        run = _run(CharacterId.ROGUE)
        run.add_relic(_mix(*CLASSES))
        assert allowed_card_classes(run) == frozenset(CardClass)

    def test_inactive_relic_does_not_mix(self):
        run = _run(CharacterId.MAGE)
        run.add_relic(_mix(CardClass.ROGUE, active=False))
        assert CardClass.ROGUE not in allowed_card_classes(run)

    def test_relics_without_classes_unlock_nothing(self):
        assert relic_effects.unlocked_card_classes([Relic("r", "R", "")]) == frozenset()

    def test_several_relics_combine(self):
        relics = [_mix(CardClass.MAGE), _mix(CardClass.ROGUE)]
        assert relic_effects.unlocked_card_classes(relics) == frozenset({CardClass.MAGE, CardClass.ROGUE})


# ---------------------------------------------------------------------------
# Rewards and packs respect classes
# ---------------------------------------------------------------------------

class TestRewardsRespectClasses:
    @pytest.mark.parametrize("cid", list(CharacterId))
    def test_packs_only_contain_allowed_classes(self, cid):
        for seed in range(30):
            run = _run(cid, seed)
            allowed = allowed_card_classes(run)
            for theme in PackTheme:
                cards = pick_pack_cards(run, theme)
                assert len([c for c in cards if not c.lucky_drop]) == PACK_SIZE   # + luck's extra cards
                assert len({c.id for c in cards}) == len(cards)
                assert all(c.card_class in allowed for c in cards)

    @pytest.mark.parametrize("cid", list(CharacterId))
    def test_rewards_only_contain_allowed_classes(self, cid):
        for seed in range(30):
            run = _run(cid, seed)
            allowed = allowed_card_classes(run)
            for room in ("a", "b", "c"):
                assert all(c.card_class in allowed for c in pick_reward_cards(run, room))

    def test_mixed_relic_makes_other_class_cards_appear(self):
        seen = set()
        for seed in range(60):
            run = _run(CharacterId.WARRIOR, seed)
            run.add_relic(_mix(CardClass.MAGE))
            seen |= {c.card_class for c in pick_pack_cards(run, PackTheme.MAGIA)}
            seen |= {c.card_class for c in pick_reward_cards(run, "room")}
        assert CardClass.MAGE in seen and CardClass.ROGUE not in seen

    def test_short_theme_is_topped_up_from_other_themes(self):
        run = _run(CharacterId.MAGE)
        cards = pick_pack_cards(run, PackTheme.EPICO, count=12)
        assert len(cards) == 12
        assert len({c.id for c in cards}) == 12
        assert all(c.card_class in {CardClass.NEUTRAL, CardClass.MAGE} for c in cards)

    def test_stress_many_runs_never_leak_other_classes(self):
        for seed in range(1_000):
            cid = list(CharacterId)[seed % 3]
            run = _run(cid, seed * 10 ** 12)
            own = class_for_character(cid)
            cards = pick_reward_cards(run, f"room_{seed}") + pick_pack_cards(run, list(PackTheme)[seed % 4])
            assert {c.card_class for c in cards} <= {CardClass.NEUTRAL, own}
