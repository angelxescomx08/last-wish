"""Tests for src/domain/card_pool.py.

Covers ALL_PACKS membership, PackDef fields, card_factories_for_theme(),
starter_deck(), pack_def_for_theme(), and factory independence.
No pygame dependency.
"""
from __future__ import annotations

from src.domain.card import Card
from src.domain.card_pool import (
    ALL_PACKS,
    PackDef,
    PackTheme,
    card_factories_for_theme,
    pack_def_for_theme,
    starter_deck,
)


# ---------------------------------------------------------------------------
# ALL_PACKS
# ---------------------------------------------------------------------------

class TestAllPacks:
    def test_has_four_entries(self):
        assert len(ALL_PACKS) == 4

    def test_acero_pack_exists(self):
        themes = [p.theme for p in ALL_PACKS]
        assert PackTheme.ACERO in themes

    def test_escudo_pack_exists(self):
        themes = [p.theme for p in ALL_PACKS]
        assert PackTheme.ESCUDO in themes

    def test_magia_pack_exists(self):
        themes = [p.theme for p in ALL_PACKS]
        assert PackTheme.MAGIA in themes

    def test_epico_pack_exists(self):
        themes = [p.theme for p in ALL_PACKS]
        assert PackTheme.EPICO in themes

    def test_all_unique_themes(self):
        themes = [p.theme for p in ALL_PACKS]
        assert len(themes) == len(set(themes))


# ---------------------------------------------------------------------------
# PackDef fields
# ---------------------------------------------------------------------------

class TestPackDefFields:
    def test_acero_has_name(self):
        pack = pack_def_for_theme(PackTheme.ACERO)
        assert isinstance(pack.name, str) and len(pack.name) > 0

    def test_acero_has_description(self):
        pack = pack_def_for_theme(PackTheme.ACERO)
        assert isinstance(pack.description, str) and len(pack.description) > 0

    def test_acero_has_positive_cost(self):
        pack = pack_def_for_theme(PackTheme.ACERO)
        assert pack.cost > 0

    def test_epico_costs_more_than_acero(self):
        acero = pack_def_for_theme(PackTheme.ACERO)
        epico = pack_def_for_theme(PackTheme.EPICO)
        assert epico.cost > acero.cost

    def test_pack_def_is_frozen(self):
        pack = pack_def_for_theme(PackTheme.ESCUDO)
        assert isinstance(pack, PackDef)

    def test_theme_field_matches(self):
        pack = pack_def_for_theme(PackTheme.MAGIA)
        assert pack.theme == PackTheme.MAGIA


# ---------------------------------------------------------------------------
# card_factories_for_theme()
# ---------------------------------------------------------------------------

class TestCardFactoriesForTheme:
    def test_returns_list_of_callables_acero(self):
        factories = card_factories_for_theme(PackTheme.ACERO)
        assert all(callable(f) for f in factories)

    def test_each_factory_returns_card_acero(self):
        for factory in card_factories_for_theme(PackTheme.ACERO):
            assert isinstance(factory(), Card)

    def test_each_factory_returns_card_escudo(self):
        for factory in card_factories_for_theme(PackTheme.ESCUDO):
            assert isinstance(factory(), Card)

    def test_each_factory_returns_card_magia(self):
        for factory in card_factories_for_theme(PackTheme.MAGIA):
            assert isinstance(factory(), Card)

    def test_each_factory_returns_card_epico(self):
        for factory in card_factories_for_theme(PackTheme.EPICO):
            assert isinstance(factory(), Card)

    def test_different_calls_different_instances(self):
        factories = card_factories_for_theme(PackTheme.ACERO)
        c1 = factories[0]()
        c2 = factories[0]()
        assert c1 is not c2

    def test_at_least_eight_factories_acero(self):
        assert len(card_factories_for_theme(PackTheme.ACERO)) >= 8

    def test_at_least_eight_factories_escudo(self):
        assert len(card_factories_for_theme(PackTheme.ESCUDO)) >= 8

    def test_at_least_eight_factories_magia(self):
        assert len(card_factories_for_theme(PackTheme.MAGIA)) >= 8

    def test_factory_independence_stacked_effects(self):
        """Mutating stacked_effects on one instance must not affect another."""
        factories = card_factories_for_theme(PackTheme.ACERO)
        c1 = factories[0]()
        c2 = factories[0]()
        from src.domain.card import CardEffect
        from src.domain.numbers import BigValue
        c1.stacked_effects.append(CardEffect(name="extra", damage=BigValue(5)))
        assert len(c2.stacked_effects) == 0


# ---------------------------------------------------------------------------
# starter_deck()
# ---------------------------------------------------------------------------

class TestStarterDeck:
    def test_returns_ten_cards(self):
        assert len(starter_deck()) == 10

    def test_all_cards_are_card_instances(self):
        for card in starter_deck():
            assert isinstance(card, Card)

    def test_all_cards_have_nonzero_effect(self):
        for card in starter_deck():
            assert card.total_damage() + card.total_block() > 0

    def test_successive_calls_return_independent_lists(self):
        deck1 = starter_deck()
        deck2 = starter_deck()
        deck1.clear()
        assert len(deck2) == 10


# ---------------------------------------------------------------------------
# pack_def_for_theme()
# ---------------------------------------------------------------------------

class TestPackDefForTheme:
    def test_acero_returns_acero_def(self):
        assert pack_def_for_theme(PackTheme.ACERO).theme == PackTheme.ACERO

    def test_escudo_returns_escudo_def(self):
        assert pack_def_for_theme(PackTheme.ESCUDO).theme == PackTheme.ESCUDO

    def test_magia_returns_magia_def(self):
        assert pack_def_for_theme(PackTheme.MAGIA).theme == PackTheme.MAGIA

    def test_epico_returns_epico_def(self):
        assert pack_def_for_theme(PackTheme.EPICO).theme == PackTheme.EPICO
