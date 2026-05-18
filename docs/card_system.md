# Card System

Cards are the primary gameplay objects. Each card has a type, a cost, a base effect, and optional stacked effects and modifiers.

---

## Card types

| `CardType` | UI label | Behaviour after play |
|---|---|---|
| `ATTACK` | `ATK` | Goes to discard pile |
| `SKILL` | `HAB` | Goes to discard pile |
| `POWER` | `POD` | Stays on the field (`active_powers`) |

---

## Card structure

```python
@dataclass
class Card:
    id: str
    name: str
    card_type: CardType
    cost: int                          # mana required to play
    base_effect: CardEffect            # always present
    stacked_effects: list[CardEffect]  # grows when cards stack / merge
    modifiers: list[CardModifier]      # CHROMA, TRANSPARENT, ETHEREAL, ECHO
    is_broken: bool = False            # eligible for merge mechanic
    is_upgraded: bool = False
```

---

## CardEffect

```python
@dataclass
class CardEffect:
    name: str
    damage: BigValue    # default BigValue(0)
    block: BigValue     # default BigValue(0)
    draw: int = 0       # bonus cards drawn when this effect resolves
    mana_gain: int = 0
```

Each card can have multiple `CardEffect` layers. `Card.all_effects()` returns `[base_effect, *stacked_effects]`.

**Resolution:**
- `total_damage()` → sums `fx.damage.resolve()` across all effects
- `total_block()`  → sums `fx.block.resolve()` across all effects
- `draw_count`     → sums `fx.draw` across all effects (used in `play_card`)

---

## Modifiers

```python
class ModifierTag(Enum):
    CHROMA      # alters damage element
    TRANSPARENT # bypasses enemy block
    ETHEREAL    # exhausted instead of discarded
    ECHO        # effect triggers twice
```

Modifiers are stored as `CardModifier(tag, stacks)` but their mechanical effects are interpreted at resolution time. Query methods:
- `card.has_modifier(tag) → bool`
- `card.modifier_stacks(tag) → int`

---

## Stacking mechanic

Additional `CardEffect` objects can be appended to `stacked_effects`. The UI shows a badge `+Nfx` for stacked cards. All effects contribute to the card's totals.

```python
card.stacked_effects.append(
    CardEffect("Chroma Fuego", damage=BigValue(4).add_multiplier(2))
)
# Adds 8 to the card's total damage
```

---

## Broken cards & merge

`is_broken = True` marks a card as a merge candidate. Two broken cards can fuse — their effect chains concatenate into a single card that inherits both parents' history. The UI draws a diagonal stripe on broken cards.

---

## Relic bonus damage (Orbe de Fuego)

`relic_effects.extra_attack_damage(relics)` returns a flat int bonus applied to all attack cards at play time (in `play_card.py`). This bonus is NOT stored on the card — it is computed from the current relic list every time a card is played.

The card widget and card tooltip both accept `bonus_damage: int = 0` to display the effective final value.

---

## Card factories (in combat_manager.py)

```python
_attack("id", "Golpe",    cost=1, damage=6)
_skill( "id", "Defender", cost=1, block=5, draw=0)
_power( "id", "Poder",    cost=0)
```
