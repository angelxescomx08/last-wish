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
  conftest.py                  ← session-scoped pygame.init()
  domain/
    test_numbers.py            ← src/domain/numbers.py
    test_card.py               ← src/domain/card.py
    test_relic.py              ← src/domain/relic.py
    test_entities.py           ← src/domain/entities.py
    test_pile.py               ← src/domain/pile.py
    test_mana.py               ← src/domain/mana.py
    test_combat.py             ← src/domain/combat.py
  application/
    test_relic_effects.py      ← src/application/relic_effects.py
    test_play_card.py          ← src/application/play_card.py
    test_end_turn.py           ← src/application/end_turn.py
    test_combat_manager.py     ← src/application/combat_manager.py
  infrastructure/
    test_colors.py             ← src/infrastructure/colors.py
    test_fonts.py              ← src/infrastructure/fonts.py
    test_viewport.py           ← src/infrastructure/viewport.py
  presentation/
    ui/
      test_tooltip.py          ← src/presentation/ui/tooltip.py
      test_card_widget.py      ← src/presentation/ui/card_widget.py
      test_entity_widget.py    ← src/presentation/ui/entity_widget.py
      test_hud_widget.py       ← src/presentation/ui/hud_widget.py
      test_pile_viewer.py      ← src/presentation/ui/pile_viewer.py
    scenes/
      test_combat_scene.py     ← src/presentation/scenes/combat_scene.py
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

### `infrastructure/` tests
- `pygame.Color` objects work without `pygame.init()`.
- `FontRegistry.get()`, `Viewport`, and any `pygame.Surface` creation require the session fixture (`conftest.py` handles this automatically).

### `presentation/` tests
- Content generators in `tooltip.py` (`card_tooltip`, `relic_tooltip`, etc.) are pure Python — no pygame needed.
- Widget rendering functions (`draw_card`, `draw_enemy`, etc.) need a `pygame.Surface`. Create it with `pygame.Surface((w, h))` — no display required.
- Smoke-test rendering by calling the function and checking the return type; don't assert colors or pixel values.

---

## When to add tests

Every code change must be accompanied by tests. Specifically:

| Change type | Required tests |
|---|---|
| New domain class / field | At least: default values, storage, boundary inputs |
| New use case / function | At least: success path, failure path, boundary inputs |
| New relic | Tag enum, relic_effects query, integration in end_turn or play_card |
| New widget function | Smoke test + return type |
| Bug fix | Regression test that reproduces the bug before the fix |
| BigValue formula change | Stress tests at 10^100 and chain of 100+ ops |
