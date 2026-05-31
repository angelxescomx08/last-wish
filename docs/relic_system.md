# Relic System

Relics are passive items that permanently alter combat rules. They are stored as a list in `CombatState.relics` and never removed (except that `is_active` can be set to `False` when a one-time relic is consumed).

---

## Data model

```python
class RelicTag(Enum):
    # Combat relics (sample set)
    COMBAT_AMULET   = "combat_amulet"
    BROKEN_TOTEM    = "broken_totem"
    FIRE_ORB        = "fire_orb"
    SPECTRAL_SHIELD = "spectral_shield"
    # Roguelike run relics
    ENERGY_STONE    = "energy_stone"
    GOLD_RING       = "gold_ring"
    IRON_HEART      = "iron_heart"
    BLOOD_POTION    = "blood_potion"

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
| `bonus_gold_reward(relics)` | `int` extra gold per combat | `apply_combat_victory` in run_manager |
| `post_combat_heal(relics)` | `int` HP healed after combat | `apply_combat_victory` in run_manager |
| `max_hp_bonus(relics)` | `int` extra max HP | `pick_treasure_relic` / `pick_boss_relics` when relic acquired |

---

## Combat relics (sample set)

These four relics are present in every combat built by `create_sample_combat()` and `create_combat_for_character()`.

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
  effective_dmg = (
      dmg
      + relic_effects.extra_attack_damage(state.relics)
      + state.player.attack_bonus          # from character stats
  )
  ```
- **UI:** card widget and tooltip both show the combined effective value. The tooltip breakdown
  shows `base + total_bonus` when any bonus is non-zero.

### Escudo Espectral  (`SPECTRAL_SHIELD`)
- **Effect:** when player HP drops to 0 from an enemy attack, survive at 1 HP. One-time use.
- **Applied:** in `_execute_intent()` immediately after damage is applied.
  ```python
  relic_effects.try_spectral_shield(state)  # sets is_active=False if triggered
  ```
- **Tooltip:** shows `Estado: Agotado` once consumed.

---

## Roguelike run relics

These four relics can be acquired during a run (treasure rooms, boss rewards). They are added to `run.relics` via `run.add_relic()` and carried into every subsequent combat via `create_combat_from_run()`.

### Piedra de Energía  (`ENERGY_STONE`)
- **Effect:** +1 card drawn per turn (stacks additively with BROKEN_TOTEM).
- **Applied:** `extra_draw_per_turn(relics)` sums all active `BROKEN_TOTEM` and `ENERGY_STONE` relics.

### Anillo de Oro  (`GOLD_RING`)
- **Effect:** +15 gold after each combat victory.
- **Applied:** `bonus_gold_reward(relics)` called in `apply_combat_victory()` in run_manager.

### Corazón de Hierro  (`IRON_HEART`)
- **Effect:** +15 maximum HP, applied at the moment the relic is acquired.
- **Applied:** `max_hp_bonus(relics)` called in `pick_treasure_relic()` and `pick_boss_relics()`.
  `run.player_max_hp` is recalculated as `character.stats.max_hp + max_hp_bonus(run.relics)`.

### Poción de Sangre  (`BLOOD_POTION`)
- **Effect:** heal 8 HP after each combat victory.
- **Applied:** `post_combat_heal(relics)` called in `apply_combat_victory()` in run_manager.
  Healed HP is capped at `run.player_max_hp`.

---

## Multiple relics of the same type

All query functions use `sum(... for r in relics if r.is_active and r.tag == tag)`, so owning two `FIRE_ORB` relics gives +4 damage, two `BROKEN_TOTEM` relics give +2 draw, etc.

---

## Relic icons

Every relic has a 32×32 sprite icon from the DCSS asset pack, displayed in the HUD relic bar.
Loaded and cached by `SpriteLoader.get_relic_sprite(relic.name, size=36)`.
When a one-time relic is exhausted (`is_active = False`) a semi-transparent dark overlay is drawn on top of the icon.

| Relic | Icon file |
|---|---|
| Amuleto de Combate | `item/amulet/celtic_red.png` |
| Tótem Roto | `item/misc/misc_stone_old.png` |
| Orbe de Fuego | `item/misc/misc_orb.png` |
| Escudo Espectral | `item/armor/shields/shield_of_reflection.png` |
| Piedra de Energía | `item/misc/misc_stone_new.png` |
| Anillo de Oro | `item/ring/gold.png` |
| Corazón de Hierro | `item/amulet/crystal_red.png` |
| Poción de Sangre | `item/potion/ruby_new.png` |

---

## How to add a new relic

1. Add a new variant to `RelicTag` in `src/domain/relic.py`.
1b. Add an entry to `RELIC_SPRITE_PATHS` in `src/infrastructure/sprite_loader.py` mapping `relic.name` → PNG path relative to `assets/dungeon-crawl-stone-soup-full/`.
2. Add a query function in `src/application/relic_effects.py`.
3. Call it at the right hook in `end_turn.py`, `play_card.py`, or `run_manager.py`.
4. Propagate any UI hint (`bonus_damage`, `bonus_block`, etc.) from `CombatScene` to the widget/tooltip.
5. Add the relic to `create_sample_combat()` in `combat_manager.py` **and** to `create_combat_for_character()` in `combat_factory.py` if it belongs to the base combat set.
6. Write tests:
   - `tests/domain/test_relic.py` — tag exists, fields correct.
   - `tests/application/test_relic_effects.py` — active, inactive, stacked, boundary.
   - Relevant use-case test — integration coverage.
