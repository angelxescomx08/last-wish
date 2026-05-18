# Relic System

Relics are passive items that permanently alter combat rules. They are stored as a list in `CombatState.relics` and never removed (except that `is_active` can be set to `False` when a one-time relic is consumed).

---

## Data model

```python
class RelicTag(Enum):
    COMBAT_AMULET   = "combat_amulet"
    BROKEN_TOTEM    = "broken_totem"
    FIRE_ORB        = "fire_orb"
    SPECTRAL_SHIELD = "spectral_shield"

@dataclass
class Relic:
    id: str
    name: str
    description: str
    tag: RelicTag | None = None
    is_active: bool = True
```

---

## Effect model

Effects are **pure query functions** in `src/application/relic_effects.py`. They are called on demand — no callbacks, no observers.

| Function | Returns | Used in |
|---|---|---|
| `extra_draw_per_turn(relics)` | `int` extra cards to draw | `draw_opening_hand`, `_begin_player_turn` |
| `extra_attack_damage(relics)` | `int` bonus flat damage | `play_card` when `total_damage() > 0` |
| `bonus_starting_mana(relics)` | `int` extra mana maximum | `draw_opening_hand` |
| `try_spectral_shield(state)` | `bool` — True if triggered | `_execute_intent` after ATTACK damage |

---

## The four sample relics

### Amuleto de Combate  (`COMBAT_AMULET`)
- **Effect:** +1 mana maximum for the entire combat.
- **Applied:** once in `draw_opening_hand()`. `mana.maximum += 1; mana.refill()`.
- **Stays:** `is_active = True` permanently (the mana increase is already baked in).

### Tótem Roto  (`BROKEN_TOTEM`)
- **Effect:** +1 card drawn at the start of every player turn.
- **Applied:** in `draw_opening_hand()` and in `_begin_player_turn()` each turn.
- **Draw count:** `5 + extra_draw_per_turn(relics)` cards per turn.

### Orbe de Fuego  (`FIRE_ORB`)
- **Effect:** +2 flat damage on every attack card played.
- **Applied:** in `play_card()` when `card.total_damage() > 0`.
  ```python
  effective_dmg = dmg + relic_effects.extra_attack_damage(state.relics)
  ```
- **UI:** card widget and tooltip both show the effective final value.

### Escudo Espectral  (`SPECTRAL_SHIELD`)
- **Effect:** when player HP drops to 0 from an enemy attack, survive at 1 HP. One-time use.
- **Applied:** in `_execute_intent()` immediately after damage is applied.
  ```python
  relic_effects.try_spectral_shield(state)  # sets is_active=False if triggered
  ```
- **Tooltip:** shows `Estado: Agotado` once consumed.

---

## How to add a new relic

1. Add a new variant to `RelicTag` in `src/domain/relic.py`.
2. Add a query function in `src/application/relic_effects.py`.
3. Call it at the right hook in `end_turn.py` or `play_card.py`.
4. Propagate any UI hint (`bonus_damage`, etc.) from `CombatScene` to the widget/tooltip.
5. Add the relic to `create_sample_combat()` in `combat_manager.py`.
6. Write tests:
   - `tests/domain/test_relic.py` — tag exists, fields correct.
   - `tests/application/test_relic_effects.py` — active, inactive, stacked, boundary.
   - Relevant use-case test — integration coverage.

---

## Multiple relics of the same type

All query functions use `sum(... for r in relics if r.is_active and r.tag == tag)`, so owning two `FIRE_ORB` relics gives +4 damage, two `BROKEN_TOTEM` relics give +2 draw, etc.
