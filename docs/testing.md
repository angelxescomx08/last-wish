# Testing Guide

## Running tests

```bash
# Full suite
uv run pytest tests/ -v

# Single layer
uv run pytest tests/domain/ -v
uv run pytest tests/application/ -v
uv run pytest tests/infrastructure/ -v
uv run pytest tests/presentation/ -v

# Single file
uv run pytest tests/domain/test_numbers.py -v

# Concise summary
uv run pytest tests/ -q
```

---

## Test structure mirrors `src/`

```
tests/
  conftest.py                       ← session-scoped pygame.init()
  test_preferences.py               ← src/infrastructure/preferences.py
  test_sprite_loader.py             ← src/infrastructure/sprite_loader.py
  domain/
    test_numbers.py                 ← src/domain/numbers.py
    test_card.py                    ← src/domain/card.py
    test_relic.py                   ← src/domain/relic.py
    test_character.py               ← src/domain/character.py
    test_entities.py                ← src/domain/entities.py
    test_pile.py                    ← src/domain/pile.py
    test_mana.py                    ← src/domain/mana.py
    test_combat.py                  ← src/domain/combat.py
    test_map_node.py                ← src/domain/map_node.py
    test_game_map.py                ← src/domain/game_map.py
    test_run.py                     ← src/domain/run.py
    test_card_pool.py               ← src/domain/card_pool.py
  application/
    test_relic_effects.py           ← src/application/relic_effects.py
    test_play_card.py               ← src/application/play_card.py
    test_end_turn.py                ← src/application/end_turn.py
    test_combat_manager.py          ← src/application/combat_manager.py
    test_combat_factory.py          ← src/application/combat_factory.py
    test_map_generator.py           ← src/application/map_generator.py
    test_run_manager.py             ← src/application/run_manager.py
    test_card_rewards.py            ← src/application/card_rewards.py
  infrastructure/
    test_colors.py                  ← src/infrastructure/colors.py
    test_fonts.py                   ← src/infrastructure/fonts.py
    test_viewport.py                ← src/infrastructure/viewport.py
  presentation/
    ui/
      test_tooltip.py               ← src/presentation/ui/tooltip.py
      test_card_widget.py           ← src/presentation/ui/card_widget.py
      test_entity_widget.py         ← src/presentation/ui/entity_widget.py
      test_hud_widget.py            ← src/presentation/ui/hud_widget.py
      test_pile_viewer.py           ← src/presentation/ui/pile_viewer.py
    scenes/
      test_combat_scene.py          ← src/presentation/scenes/combat_scene.py
```

---

## File structure — every test file follows this pattern

```python
"""Module docstring: what is being tested and the stress philosophy."""
from __future__ import annotations

import pytest

# imports of the module under test
# imports of domain helpers (no mocks)

# ---------------------------------------------------------------------------
# Helpers / fixtures (plain functions, no pytest fixtures)
# ---------------------------------------------------------------------------

def _some_helper(...) -> ...:
    ...

# ---------------------------------------------------------------------------
# class TestTopic:          ← one class per concept or method
# ---------------------------------------------------------------------------

class TestSomeConcept:
    def test_specific_case(self):
        # arrange
        # act
        # assert (single assert per test preferred)
        assert ...
```

**Rules:**
- Class name: `Test<MethodName>` or `Test<ConceptName>`.
- Method name: `test_<specific_readable_case>`.
- One logical assertion per test.
- No `pytest.fixture` — use plain helper functions instead.

---

## What to test

### Boundary values (required for every numeric parameter)

| Value | Why |
|---|---|
| `0` | Identity, empty, zero-cost edge |
| `1` | Minimal non-trivial input |
| `max` | Exact capacity limit |
| `max + 1` | Over-limit — ensure clamp / no crash |
| `10^9, 10^18, 10^100, 10^1000` | Stress BigValue precision |

### State combinations

- Active relic + inactive relic — never conflate them.
- Two of the same relic — effects must stack.
- Relic with `tag=None` — must be silently ignored.
- `player.dexterity = 0` vs. non-zero — block bonus must only apply when non-zero.
- `player.attack_bonus = 0` vs. non-zero — damage bonus must only apply when non-zero.
- `player.luck < 5` vs. `>= 5` — extra draw only kicks in at thresholds.

### Smoke tests (presentation layer)

For every `draw_*()` function: call it, verify no exception and the return type is correct (`pygame.Rect` or `list[pygame.Rect]`). Do not assert pixel values.

### Immutability (BigValue)

Always verify that calling `.add_flat()` or `.add_multiplier()` on a `BigValue` does not mutate the original.

---

## Layer-specific notes

### `domain/` tests
- No pygame — domain is pygame-free. If a test imports pygame, it's in the wrong layer.
- Instantiate domain objects directly. No mocks.

### `application/` tests
- Build minimal `CombatState` objects using the inline helpers in each test file.
- Never import from `presentation/` or `infrastructure/`.
- The `_make_state()` helpers in play_card and end_turn tests accept `player_dexterity`,
  `player_attack_bonus`, and `player_luck` to exercise character-stat paths cleanly.
- Map generator tests include `TestOrthogonalConnections`: all edges must be purely horizontal
  (same row, col diff = 1) or purely vertical (same col, row diff = 1). No diagonals allowed.

### `infrastructure/` tests

#### `preferences.py`
- `pygame.Color` objects work without `pygame.init()`.
- Tests redirect `_PREFS_FILE` via a context manager to avoid touching the real `preferences.json`.
- Covers: defaults, load (present / missing / invalid JSON / empty object / unknown keys),
  save (creates file, correct values), round-trip.

#### `sprite_loader.py`
- Tests do **not** require `pygame.init()` — they only call `Path.is_file()` and inspect the
  mapping tables (`PLAYER_SPRITE_PATHS`, `ENEMY_SPRITE_PATHS`).
- `SpriteLoader._load()` is never called in tests; only the public API with unknown names
  (returns `None` early, before any pygame call) and the cache state are tested.
- Key checks: all expected Spanish names are in the tables, all mapped `.png` files exist on
  disk under `assets/dungeon-crawl-stone-soup-full/`, unknown name returns `None` without
  populating the cache.

#### Other infrastructure
- `FontRegistry.get()`, `Viewport`, and any `pygame.Surface` creation require the session
  fixture (`conftest.py` handles this automatically).

### `presentation/` tests
- Content generators in `tooltip.py` (`card_tooltip`, `relic_tooltip`, etc.) are pure Python — no pygame needed.
- `card_tooltip` now accepts keyword-only `bonus_damage` and `bonus_block`; both default to 0.
- Widget rendering functions (`draw_card`, `draw_enemy`, `draw_player`, etc.) need a `pygame.Surface`.
  Create it with `pygame.Surface((w, h))` — no display required.
- `draw_player` and `draw_enemy` now accept an optional `sprite: pygame.Surface | None = None`
  parameter. Smoke tests should exercise both the `sprite=None` path and a `sprite=pygame.Surface`
  path to ensure neither crashes.
- Smoke-test rendering by calling the function and checking the return type; don't assert colors
  or pixel values.

---

## When to add tests

Every code change must be accompanied by tests. Specifically:

| Change type | Required tests |
|---|---|
| New domain class / field | At least: default values, storage, boundary inputs |
| New use case / function | At least: success path, failure path, boundary inputs |
| New relic | Tag enum, relic_effects query, integration in end_turn or play_card |
| New character | Entry in `ALL_CHARACTERS`, stat values, invariants (hp > 0, mana > 0) |
| New widget function | Smoke test + return type |
| New sprite mapping | Entry in `PLAYER_SPRITE_PATHS` or `ENEMY_SPRITE_PATHS`, file exists on disk |
| Bug fix | Regression test that reproduces the bug before the fix |
| BigValue formula change | Stress tests at 10^100 and chain of 100+ ops |
| Map generation change | Orthogonal invariant still holds across multiple seeds and floors |
