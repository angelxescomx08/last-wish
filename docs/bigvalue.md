# BigValue — Arbitrary-Precision Combat Arithmetic

`BigValue` is the numeric backbone of Last Wish's combat system, inspired by Balatro's **Chips × Mult** model. All damage and block values are `BigValue` instances. Python `int` has no upper bound, so values like 10^1000 are computed exactly — zero overflow risk.

---

## Data model

```python
@dataclass
class Operation:
    kind: Literal["+", "x"]
    value: int

@dataclass
class BigValue:
    base: int
    ops: list[Operation]   # ordered log of additions and multiplications
```

---

## Resolution formula

```
chips  = base  +  Σ(all "+" ops in order)
result = chips ×  Π(all "×" ops in order)
```

Flat additions always accumulate into `chips` regardless of their position in `ops`.  
Multipliers always contribute to the product regardless of order.

---

## Builder API  (each call returns a **new** BigValue — originals are never mutated)

| Method | Effect | Example |
|---|---|---|
| `BigValue(n)` | base = n, no ops | `BigValue(6).resolve()` → `6` |
| `.add_flat(n)` | appends `Operation("+", n)` | `BigValue(6).add_flat(4).resolve()` → `10` |
| `.add_multiplier(n)` | appends `Operation("×", n)` | `BigValue(6).add_multiplier(2).resolve()` → `12` |
| `.merge(other)` | `resolved(self) + other.base`, then carries `other.ops` | see below |

### Chain examples

```python
BigValue(6).add_flat(4).add_multiplier(2)
# chips = 6+4 = 10 · mult = 2 → 20

BigValue(4).add_multiplier(2)
# Chroma Fuego pattern: chips=4 · mult=2 → 8

BigValue(1).add_multiplier(2)  # repeated 100 times
# → 2^100  (exact)

BigValue(10**500).add_multiplier(10**500)
# → 10^1000  (exact)
```

### merge()

```python
a.merge(b)
# new_base = a.resolve() + b.base
# new_ops  = list(b.ops)
```

```python
BigValue(6).merge(BigValue(4).add_multiplier(3))
# new_base = 6+4 = 10 · then ×3 → 30
```

Used when two `BigValue` chains are combined (e.g. card stacking across effects).

---

## Key invariants

| Expression | Result | Reason |
|---|---|---|
| `BigValue(n).add_flat(0).resolve()` | `n` | Adding 0 is identity |
| `BigValue(n).add_multiplier(1).resolve()` | `n` | Multiplying by 1 is identity |
| `BigValue(n).add_multiplier(0).resolve()` | `0` | Zero multiplier collapses everything |
| `BigValue(0).add_multiplier(10**100).resolve()` | `0` | Zero base × anything = 0 |
| Any chain with a `×0` op | `0` | Regardless of position |

---

## format_int(value) — display suffixes

All UI rendering goes through `BigValue.format_int(int) → str`.  
Uses pure integer arithmetic — no floats, no rounding drift.

| Threshold | Suffix | Example |
|---|---|---|
| < 1 000 | (none) | `"999"` |
| ≥ 10³ | `K` | `"1.5K"` |
| ≥ 10⁶ | `M` | `"2.0M"` |
| ≥ 10⁹ | `B` | `"1.0B"` |
| ≥ 10¹² | `T` | `"1.0T"` |
| ≥ 10¹⁵ | `Q` | `"1.0Q"` |
| ≥ 10¹⁸ | `E` | `"100.0E"` |

Values above 10¹⁸ display correctly — e.g. `10^1000` shows as `"...E"`.

Negative values: `format_int(-n)` = `"-" + format_int(n)`.

---

## How cards use BigValue

```python
# base_effect damage
CardEffect(name="Golpe", damage=BigValue(6))

# stacked effect (Chroma Fuego)
CardEffect("Chroma Fuego", damage=BigValue(4).add_multiplier(2))   # → 8

# total damage from a card:
card.total_damage()   # sums resolved() of all effects
```

`Card.total_damage()` iterates over `all_effects()` (base + stacked) and calls `add_flat` on a running `BigValue(0)` for each resolved value.
