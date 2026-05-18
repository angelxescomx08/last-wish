"""Tests for BigValue: arithmetic correctness, extreme values, chains, and formatting.

Stress philosophy:
- Values up to 10^1000 — Python int has no overflow.
- Chains of 100+ operations to verify accumulation is exact.
- Multiplier chains that produce 2^100 ≈ 10^30.
- Mixed flat+mult sequences to verify resolution order.
- Edge cases: zero base, zero multiplier, multiplier=1, negative numbers.
"""
from __future__ import annotations

import pytest

from src.domain.numbers import BigValue, Operation


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _chain_flat(base: int, flat: int, n: int) -> BigValue:
    """Apply add_flat(flat) n times starting from base."""
    v = BigValue(base)
    for _ in range(n):
        v = v.add_flat(flat)
    return v


def _chain_mult(base: int, mult: int, n: int) -> BigValue:
    """Apply add_multiplier(mult) n times starting from base."""
    v = BigValue(base)
    for _ in range(n):
        v = v.add_multiplier(mult)
    return v


# ---------------------------------------------------------------------------
# resolve() — basic
# ---------------------------------------------------------------------------

class TestResolveBasic:
    def test_zero_base(self):
        assert BigValue(0).resolve() == 0

    def test_one_base(self):
        assert BigValue(1).resolve() == 1

    def test_positive_base(self):
        assert BigValue(6).resolve() == 6

    def test_large_base(self):
        assert BigValue(10**18).resolve() == 10**18

    def test_very_large_base(self):
        assert BigValue(10**100).resolve() == 10**100

    def test_astronomically_large_base(self):
        assert BigValue(10**1000).resolve() == 10**1000

    def test_no_ops_returns_base(self):
        assert BigValue(42, []).resolve() == 42


# ---------------------------------------------------------------------------
# resolve() — flat additions
# ---------------------------------------------------------------------------

class TestResolveFlat:
    def test_single_flat(self):
        assert BigValue(6).add_flat(4).resolve() == 10

    def test_flat_zero(self):
        assert BigValue(6).add_flat(0).resolve() == 6

    def test_flat_chain_two(self):
        assert BigValue(6).add_flat(3).add_flat(2).resolve() == 11

    def test_flat_chain_ten(self):
        # base=0, +1 ten times → 10
        assert _chain_flat(0, 1, 10).resolve() == 10

    def test_flat_chain_hundred(self):
        # base=0, +1 hundred times → 100
        assert _chain_flat(0, 1, 100).resolve() == 100

    def test_flat_chain_large_increment(self):
        # base=0, +10^9 fifty times → 50 * 10^9
        assert _chain_flat(0, 10**9, 50).resolve() == 50 * 10**9

    def test_flat_on_huge_base(self):
        v = BigValue(10**1000).add_flat(10**1000)
        assert v.resolve() == 2 * 10**1000

    def test_flat_chain_hundred_on_huge_base(self):
        # 10^100 + 100 flats of 10^100 = 101 * 10^100
        v = _chain_flat(10**100, 10**100, 100)
        assert v.resolve() == 101 * 10**100


# ---------------------------------------------------------------------------
# resolve() — multipliers
# ---------------------------------------------------------------------------

class TestResolveMultiplier:
    def test_single_multiplier(self):
        assert BigValue(6).add_multiplier(2).resolve() == 12

    def test_multiplier_zero(self):
        assert BigValue(100).add_multiplier(0).resolve() == 0

    def test_multiplier_one(self):
        assert BigValue(7).add_multiplier(1).resolve() == 7

    def test_two_multipliers(self):
        # chips=2, mult=3*4=12 → 24
        assert BigValue(2).add_multiplier(3).add_multiplier(4).resolve() == 24

    def test_multiplier_chain_ten(self):
        # base=2, mult=2^10=1024 → 2048
        assert _chain_mult(2, 2, 10).resolve() == 2 * (2**10)

    def test_multiplier_chain_fifty(self):
        # base=1, mult=2^50 → 2^50
        result = _chain_mult(1, 2, 50).resolve()
        assert result == 2**50

    def test_multiplier_chain_hundred(self):
        # base=1, x2 one hundred times → 2^100
        result = _chain_mult(1, 2, 100).resolve()
        assert result == 2**100

    def test_large_base_large_multiplier(self):
        assert BigValue(10**9).add_multiplier(10**9).resolve() == 10**18

    def test_huge_multiplier_chain(self):
        # base=1, x10 repeated 1000 times → 10^1000
        result = _chain_mult(1, 10, 1000).resolve()
        assert result == 10**1000

    def test_astronomical_mult(self):
        v = BigValue(10**500).add_multiplier(10**500)
        assert v.resolve() == 10**1000

    def test_zero_base_any_multiplier(self):
        assert _chain_mult(0, 10**100, 50).resolve() == 0


# ---------------------------------------------------------------------------
# resolve() — mixed flat + multiplier chains
# ---------------------------------------------------------------------------

class TestResolveMixed:
    def test_flat_then_mult(self):
        # chips = 6+4 = 10; mult=2 → 20
        assert BigValue(6).add_flat(4).add_multiplier(2).resolve() == 20

    def test_mult_then_flat(self):
        # chips = 6 + 0_flats + 4 = 10; but wait — resolution is:
        # chips = base + all_flats; mult = product_of_all_mults
        # Order of ops DOES NOT reorder resolution: flats sum first, mults product
        # add_multiplier THEN add_flat: chips=6+4=10, mult=2 → 20
        assert BigValue(6).add_multiplier(2).add_flat(4).resolve() == 20

    def test_alternating_flat_mult(self):
        # base=10, +5, x3, +5, x2
        # chips = 10 + 5 + 5 = 20; mult = 3*2 = 6 → 120
        v = BigValue(10).add_flat(5).add_multiplier(3).add_flat(5).add_multiplier(2)
        assert v.resolve() == 120

    def test_long_mixed_chain(self):
        # Start at 0, add 1 fifty times (chips=50), multiply by 2 ten times (mult=2^10=1024)
        # → 50 * 1024 = 51200
        v = _chain_flat(0, 1, 50)
        for _ in range(10):
            v = v.add_multiplier(2)
        assert v.resolve() == 50 * (2**10)

    def test_flat_between_mults(self):
        # base=1, x10, +99, x10
        # chips = 1 + 99 = 100; mult = 10*10 = 100 → 10000
        v = BigValue(1).add_multiplier(10).add_flat(99).add_multiplier(10)
        assert v.resolve() == 10000

    def test_game_pattern_chroma_fuego(self):
        # Replicates: BigValue(4).add_multiplier(2) — Chroma Fuego stacked effect
        # chips=4, mult=2 → 8
        assert BigValue(4).add_multiplier(2).resolve() == 8

    def test_game_pattern_stacked_on_base(self):
        # Base card: BigValue(6) → 6
        # Stacked: BigValue(4).add_multiplier(2) → 8
        # Total: add_flat the resolved stacked onto base: 6 + 8 = 14
        base = BigValue(6)
        stacked_resolved = BigValue(4).add_multiplier(2).resolve()
        total = base.add_flat(stacked_resolved)
        assert total.resolve() == 14

    def test_hundred_flats_then_hundred_mults(self):
        # chips = 0 + 100*1 = 100; mult = 3^100
        v = _chain_flat(0, 1, 100)
        for _ in range(100):
            v = v.add_multiplier(3)
        assert v.resolve() == 100 * (3**100)


# ---------------------------------------------------------------------------
# resolve() — identity and invariant checks
# ---------------------------------------------------------------------------

class TestResolveInvariants:
    def test_add_flat_zero_is_identity(self):
        v = BigValue(999).add_flat(0)
        assert v.resolve() == 999

    def test_add_multiplier_one_is_identity(self):
        v = BigValue(999).add_multiplier(1)
        assert v.resolve() == 999

    def test_hundred_flat_zeros_unchanged(self):
        v = _chain_flat(42, 0, 100)
        assert v.resolve() == 42

    def test_hundred_mult_ones_unchanged(self):
        v = _chain_mult(42, 1, 100)
        assert v.resolve() == 42

    def test_mult_zero_anywhere_in_chain_gives_zero(self):
        # Even after many flats and mults, one x0 collapses everything
        v = BigValue(10**9).add_flat(10**9).add_multiplier(10**9)
        v = v.add_multiplier(0)
        assert v.resolve() == 0

    def test_two_equivalent_chains_equal(self):
        # 10 + 40 + 50 = 100; * 5 = 500  (all flat first, then mult)
        a = BigValue(10).add_flat(40).add_flat(50).add_multiplier(5)
        # 50 + 50 = 100; * 5 = 500
        b = BigValue(50).add_flat(50).add_multiplier(5)
        assert a.resolve() == b.resolve() == 500


# ---------------------------------------------------------------------------
# merge()
# ---------------------------------------------------------------------------

class TestMerge:
    def test_merge_two_plain_values(self):
        # resolved(6) + base(4) with no ops → 10
        assert BigValue(6).merge(BigValue(4)).resolve() == 10

    def test_merge_with_other_multiplier(self):
        # (6) merged with (4 x3) → base=10, x3 → 30
        assert BigValue(6).merge(BigValue(4).add_multiplier(3)).resolve() == 30

    def test_merge_chain_on_left(self):
        # left: 6+2=8; right: 4 x2 → base=8+4=12, x2 → 24
        a = BigValue(6).add_flat(2)
        b = BigValue(4).add_multiplier(2)
        assert a.merge(b).resolve() == 24

    def test_merge_zero_left(self):
        b = BigValue(10**9).add_multiplier(10**9)
        assert BigValue(0).merge(b).resolve() == 10**18

    def test_merge_astronomical(self):
        a = BigValue(10**500)
        b = BigValue(10**500).add_multiplier(2)
        # resolved(a)=10^500 → new base=10^500+10^500=2*10^500, x2 → 4*10^500
        assert a.merge(b).resolve() == 4 * 10**500

    def test_merge_chain_on_right_preserves_ops(self):
        a = BigValue(5)
        b = BigValue(5).add_flat(5).add_multiplier(4)
        # resolved(a)=5; combined base=5+5=10; then +5 (flat in b) and x4
        # chips = 10+5=15; mult=4 → 60
        assert a.merge(b).resolve() == 60

    def test_merge_self_with_zero(self):
        v = BigValue(42)
        assert v.merge(BigValue(0)).resolve() == 42

    def test_merge_does_not_mutate_originals(self):
        a = BigValue(10)
        b = BigValue(20)
        a.merge(b)
        assert a.resolve() == 10
        assert b.resolve() == 20


# ---------------------------------------------------------------------------
# add_flat / add_multiplier immutability
# ---------------------------------------------------------------------------

class TestImmutability:
    def test_add_flat_does_not_mutate(self):
        original = BigValue(10)
        original.add_flat(5)
        assert original.resolve() == 10

    def test_add_multiplier_does_not_mutate(self):
        original = BigValue(10)
        original.add_multiplier(5)
        assert original.resolve() == 10

    def test_chain_shares_no_state(self):
        base = BigValue(5)
        a = base.add_flat(10)
        b = base.add_multiplier(3)
        assert a.resolve() == 15
        assert b.resolve() == 15
        assert base.resolve() == 5


# ---------------------------------------------------------------------------
# format_int()
# ---------------------------------------------------------------------------

class TestFormatIntBasic:
    def test_zero(self):
        assert BigValue.format_int(0) == "0"

    def test_one(self):
        assert BigValue.format_int(1) == "1"

    def test_just_below_thousand(self):
        assert BigValue.format_int(999) == "999"

    def test_exact_thousand(self):
        assert BigValue.format_int(1_000) == "1.0K"

    def test_mid_thousands(self):
        assert BigValue.format_int(1_500) == "1.5K"

    def test_nine_nine_nine_thousands(self):
        assert BigValue.format_int(9_999) == "9.9K"

    def test_ten_k(self):
        assert BigValue.format_int(10_000) == "10.0K"

    def test_exact_million(self):
        assert BigValue.format_int(1_000_000) == "1.0M"

    def test_mid_million(self):
        assert BigValue.format_int(1_500_000) == "1.5M"

    def test_exact_billion(self):
        assert BigValue.format_int(1_000_000_000) == "1.0B"

    def test_mid_billion(self):
        assert BigValue.format_int(2_500_000_000) == "2.5B"

    def test_exact_trillion(self):
        assert BigValue.format_int(10**12) == "1.0T"

    def test_exact_quadrillion(self):
        assert BigValue.format_int(10**15) == "1.0Q"

    def test_exact_exa(self):
        assert BigValue.format_int(10**18) == "1.0E"


class TestFormatIntEdge:
    def test_negative_small(self):
        assert BigValue.format_int(-1) == "-1"

    def test_negative_999(self):
        assert BigValue.format_int(-999) == "-999"

    def test_negative_thousand(self):
        assert BigValue.format_int(-1_000) == "-1.0K"

    def test_negative_billion(self):
        assert BigValue.format_int(-10**9) == "-1.0B"

    def test_above_exa_has_suffix(self):
        # 10^20 > 10^18 threshold → ends with "E"
        assert BigValue.format_int(10**20).endswith("E")

    def test_above_exa_correct_whole(self):
        # 100 * 10^18 = 10^20 → "100.0E"
        assert BigValue.format_int(100 * 10**18) == "100.0E"

    def test_fractional_K(self):
        assert BigValue.format_int(1_100) == "1.1K"

    def test_fractional_M(self):
        assert BigValue.format_int(1_200_000) == "1.2M"

    def test_boundary_999_999(self):
        # 999 999 < 10^6 → shows as K
        assert BigValue.format_int(999_999).endswith("K")

    def test_boundary_1_000_000(self):
        # Exact million
        assert BigValue.format_int(1_000_000) == "1.0M"

    def test_giant_formatted_value(self):
        # 10^1000 resolves to a huge int; format_int just needs to not crash
        result = BigValue.format_int(10**1000)
        assert isinstance(result, str)
        assert len(result) > 0
        assert result.endswith("E")  # 10^1000 >> 10^18


# ---------------------------------------------------------------------------
# display()
# ---------------------------------------------------------------------------

class TestDisplay:
    def test_display_small(self):
        assert BigValue(42).display() == "42"

    def test_display_thousand(self):
        assert BigValue(1000).display() == "1.0K"

    def test_display_chained(self):
        # 10 + 90 = 100; x10 → 1000 → "1.0K"
        assert BigValue(10).add_flat(90).add_multiplier(10).display() == "1.0K"

    def test_display_huge_chain(self):
        # 1 * 2^50 = 2^50 ≈ 10^15 → Q range
        v = _chain_mult(1, 2, 50)
        result = v.display()
        assert isinstance(result, str)
        assert result.endswith(("K", "M", "B", "T", "Q", "E"))

    def test_display_astronomical(self):
        # 10^1000 → ends with "E"
        v = BigValue(10**1000)
        assert v.display().endswith("E")


# ---------------------------------------------------------------------------
# Stress / property tests
# ---------------------------------------------------------------------------

class TestStress:
    def test_one_thousand_flat_adds(self):
        # base=0, +1 one thousand times → 1000
        v = _chain_flat(0, 1, 1000)
        assert v.resolve() == 1000

    def test_one_thousand_mult_by_one(self):
        # base=42, x1 one thousand times → still 42
        v = _chain_mult(42, 1, 1000)
        assert v.resolve() == 42

    def test_fifty_mults_of_ten(self):
        # base=1, x10 fifty times → 10^50
        v = _chain_mult(1, 10, 50)
        assert v.resolve() == 10**50

    def test_two_to_the_200(self):
        # base=1, x2 two-hundred times → 2^200
        v = _chain_mult(1, 2, 200)
        assert v.resolve() == 2**200

    def test_alternating_flat_mult_fifty_each(self):
        # 50 flats of 2 on base=0 → chips=100; 50 mults of 2 → mult=2^50
        # result = 100 * 2^50
        v = BigValue(0)
        for _ in range(50):
            v = v.add_flat(2)
        for _ in range(50):
            v = v.add_multiplier(2)
        assert v.resolve() == 100 * (2**50)

    def test_nested_merge_large(self):
        # Merge 100 BigValue(10^9) objects one after another
        # Each merge: resolved(accumulator) + base(10^9), no extra ops
        # After 100 merges: (n+1) * 10^9 for n merges from BigValue(10^9)
        acc = BigValue(10**9)
        for _ in range(99):
            acc = acc.merge(BigValue(10**9))
        assert acc.resolve() == 100 * 10**9

    def test_huge_flat_then_huge_mult(self):
        # chips = 10^500 + 10^500 = 2*10^500; mult = 10^500 → 2*10^1000
        v = BigValue(10**500).add_flat(10**500).add_multiplier(10**500)
        assert v.resolve() == 2 * 10**1000

    def test_precision_no_float_drift(self):
        # If Python used floats this would lose precision; int arithmetic is exact
        # 2^53 + 1 — this is where float64 starts losing integers
        precise = (2**53) + 1
        assert BigValue(precise).resolve() == precise

    def test_very_precise_large_number(self):
        # A prime-flavored large number to confirm no rounding
        n = 10**100 + 7
        assert BigValue(n).resolve() == n

    def test_chained_operations_associativity(self):
        # Verify: flat additions commute (chips = sum of all flats)
        a = BigValue(0).add_flat(3).add_flat(7).add_flat(5)  # chips=15
        b = BigValue(0).add_flat(5).add_flat(7).add_flat(3)  # chips=15
        assert a.resolve() == b.resolve() == 15
