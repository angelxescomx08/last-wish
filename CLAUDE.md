# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Last Wish** is a roguelike card game built with pygame, managed with uv. Python 3.13+ required.

The combat system uses a **BigValue** arithmetic engine (inspired by Balatro's Chips × Mult model) that
supports arbitrary-precision integers with no overflow risk — values up to 10^1000 and beyond are exact.

---

## Commands

```bash
# Run the game
uv run main.py

# Run the full test suite (mandatory before any merge)
uv run pytest tests/ -v

# Run a single test file
uv run pytest tests/test_numbers.py -v

# Add a runtime dependency
uv add <package> --system-certs

# Add a dev-only dependency
uv add <package> --dev --system-certs
```

---

## Change Workflow — mandatory for every change

**Before finishing any change:**

1. **Run the full test suite**: `uv run pytest tests/ -v` — 0 failures required.
2. **Add or update tests** in the corresponding `tests/test_<module>.py` file.
   - Cover the new behaviour, boundary values (0, 1, max, max+1), and large numbers.
3. **Update this file** if the change affects architecture, a module's responsibility, a relic mechanic, a public API, or the BigValue resolution formula.

No exceptions. A change without passing tests is not done.

---

## Language Convention

- **Code**: all identifiers, comments, variable names, class names, and file names must be in **English**.
- **UI / dialog text**: every string rendered on screen (menus, dialogs, card names, player messages) must be in **Spanish**.

---

## Architecture

The project follows Clean Architecture with SOLID principles. Layers must not be crossed — outer layers depend on inner ones, never the reverse.

```
src/
  domain/        # Pure business logic — no pygame, no I/O
  application/   # Use cases — orchestrate domain objects, no pygame
  infrastructure/# pygame utilities: colors, fonts, viewport scaling
  presentation/  # Screens, UI widgets, scene manager
main.py          # Entry point — wires layers and owns the game loop
tests/           # pytest unit tests — one file per module
```

### Dependency rule (enforced)

```
presentation  →  application  →  domain
infrastructure  →  (used by presentation only)
```

- **Domain** has zero pygame imports.
- **Use cases** never call pygame; they receive and return domain objects.
- **Screens** call use cases; they never touch domain logic directly.

### pygame loop (in main.py)

```python
clock = pygame.time.Clock()
scene_manager = SceneManager(...)
while running:
    dt = clock.tick(60) / 1000.0
    for event in pygame.event.get():
        scene_manager.handle_event(event)
    scene_manager.update(dt)
    scene_manager.draw(screen)
    pygame.display.flip()
```

Scenes are pushed/popped on a stack managed by `SceneManager`; each scene implements `handle_event`, `update(dt)`, and `draw(surface)`.

---

## File Map

### Domain layer — `src/domain/`

Every file in this layer is pygame-free and has a corresponding test file.

| File | Class / data | Responsibility |
|---|---|---|
| `numbers.py` | `BigValue`, `Operation` | Arbitrary-precision arithmetic: base + flat additions + multipliers |
| `card.py` | `Card`, `CardEffect`, `CardModifier`, `CardType`, `ModifierTag` | A card with stacked effect chain and modifier list |
| `relic.py` | `Relic`, `RelicTag` | Passive items with a tag identifying their mechanic (8 tags total) |
| `character.py` | `Character`, `CharacterStats`, `CharacterId`, `ALL_CHARACTERS` | Three playable characters with stat profiles (damage, max_hp, luck, max_mana, dexterity) |
| `entities.py` | `Player`, `Enemy`, `Intent`, `IntentType`, `StatusEffect` | Combat participants and their intents. `Player` carries `dexterity`, `attack_bonus`, `luck` |
| `pile.py` | `DrawPile`, `DiscardPile`, `Hand` | Card containers with `count` and `is_full` |
| `mana.py` | `Mana` | Mana resource with `spend`, `gain`, `refill`, `can_afford` |
| `combat.py` | `CombatState` | Single source of truth for the entire battle state |
| `map_node.py` | `MapNode`, `RoomType` | Single node on the run map: id, room_type, row, col, connections, visited, available |
| `game_map.py` | `GameMap` | Floor map: nodes dict, boss_id, rows, cols; `available_nodes()`, `mark_visited()` |
| `run.py` | `Run` | Persistent state across rooms: character, seed, floor, gold, hp, deck, relics, map; `add_card`, `add_relic`, `apply_combat_result` |
| `card_pool.py` | `PackTheme`, `PackDef`, `ALL_PACKS`, `starter_deck`, `card_factories_for_theme` | 4 card packs (ACERO/ESCUDO/MAGIA/EPICO), pack definitions with gold costs, starter 10-card deck |

### Application layer — `src/application/`

| File | Public API | Responsibility |
|---|---|---|
| `relic_effects.py` | `extra_draw_per_turn`, `extra_attack_damage`, `bonus_starting_mana`, `try_spectral_shield`, `bonus_gold_reward`, `post_combat_heal`, `max_hp_bonus` | Pure query functions — read relics, return bonuses or mutate state |
| `play_card.py` | `play_card(state, card_index, target_enemy_index)` → `PlayResult` | Validate and execute playing a card from hand. Applies `player.attack_bonus` to attack damage and `player.dexterity` to block |
| `end_turn.py` | `end_player_turn(state)`, `draw_opening_hand(state)` | Full turn pipeline. Draw count = 5 + relic bonus + `player.luck // 5` |
| `combat_manager.py` | `create_sample_combat()` → `CombatState` | Builds the sample battle (used for dev/testing), calls `draw_opening_hand` |
| `combat_factory.py` | `create_combat_for_character(character)` → `CombatState`; `create_combat_from_run(run, enemies)` → `CombatState` | Builds battles from a selected character or a live run; `create_combat_from_run` starts with no relics |
| `map_generator.py` | `generate_map(seed, floor)` → `GameMap` | Seeded STS-style path-based map generation. Rows = min(7 + (floor-1)//2, 12), cols = min(5 + (floor-1)//3, 8), paths = min(3 + (floor-1)//3, 6) |
| `run_manager.py` | `create_run(character, seed)` → `Run`; `generate_enemies`, `generate_boss`, `apply_combat_victory`, `generate_event_gold`, `pick_treasure_relic`, `pick_boss_relics`, `advance_floor` | Full roguelike run lifecycle: create, populate rooms, advance floors |
| `card_rewards.py` | `pick_reward_cards(run, room_id, count=3)` → `list[Card]`; `pick_pack_cards(run, theme, count=5)` → `list[Card]` | Seeded card reward selection after combat and pack opening |

### Infrastructure layer — `src/infrastructure/`

| File | Responsibility |
|---|---|
| `colors.py` | Named `pygame.Color` constants for the entire project |
| `fonts.py` | `FontRegistry` — lazy font cache, keyed by point size |
| `viewport.py` | Screen scaling for the virtual 1280×720 canvas |

### Presentation layer — `src/presentation/`

| File | Responsibility |
|---|---|
| `scenes/main_menu_scene.py` | Main menu: Jugar/Continuar, Ajustes (stub), Salir. Sets `requested_action: MenuAction` |
| `scenes/character_select_scene.py` | Character panel grid with stat bars; seed text input (click to focus, type digits). Sets `confirmed` / `back_to_menu`; exposes `seed: int` property |
| `scenes/combat_scene.py` | Main battle screen: input, layout, hover, tooltip dispatch. `is_boss` constructor param; `combat_won` property; `state` property |
| `scenes/death_scene.py` | Death screen: Nueva Partida / Menú Principal. Sets `requested_action: DeathAction` |
| `scenes/map_scene.py` | STS-style node map. Signals `selected_node: MapNode \| None` |
| `scenes/combat_reward_scene.py` | Gold display + 3 card choices after a non-boss combat. Signals `cleared: bool`, `chosen_card: Card \| None` |
| `scenes/treasure_scene.py` | Show a relic, take or skip. Signals `cleared: bool`, `took_relic: bool` |
| `scenes/shop_scene.py` | 4 pack tiles with gold cost. Signals `selected_pack: PackTheme \| None`, `cleared: bool` |
| `scenes/pack_opening_scene.py` | 5-card pick-1 overlay. Signals `cleared: bool`, `chosen_card: Card \| None` |
| `scenes/event_scene.py` | Spanish narrative + gold pickup "Recoger" button. Signals `cleared: bool` |
| `scenes/boss_reward_scene.py` | 3-phase boss reward: gold → epic pack → relic choice. Signals `cleared: bool`, `open_pack_requested: bool`, `chosen_relic: Relic \| None` |
| `ui/card_widget.py` | `draw_card(…, bonus_damage=0, bonus_block=0)` — renders card with effective final values |
| `ui/entity_widget.py` | `draw_player()`, `draw_enemy()` |
| `ui/hud_widget.py` | Relic bar, mana orb, pile buttons, turn counter, End Turn button |
| `ui/tooltip.py` | `card_tooltip(card, *, bonus_damage=0, bonus_block=0)`, `relic_tooltip`, `enemy_tooltip`, etc. |
| `ui/pile_viewer.py` | Modal overlay for browsing a pile's cards |

---

## BigValue Arithmetic

`BigValue` stores a `base: int` and an ordered list of `Operation` steps.

**Resolution formula (exact integer arithmetic, no floats):**
```
chips  = base + Σ(all "+" ops)
result = chips × Π(all "×" ops)
```

This mirrors Balatro's Chips × Mult model. Python `int` is arbitrary-precision — values like 10^1000 are computed exactly.

### Builder API (each call returns a new BigValue)

```python
BigValue(6)                                   # resolve → 6
BigValue(6).add_flat(4)                       # chips=10 → 10
BigValue(6).add_multiplier(2)                 # chips=6, mult=2 → 12
BigValue(6).add_flat(4).add_multiplier(2)     # chips=10, mult=2 → 20
BigValue(4).add_multiplier(2)                 # → 8  (Chroma Fuego pattern)
BigValue(10).merge(BigValue(5).add_mult(3))   # resolved(10)+5=15, ×3 → 45
```

### Key invariants

| Expression | Result | Why |
|---|---|---|
| `BigValue(n).add_flat(0).resolve()` | `n` | Adding 0 is identity |
| `BigValue(n).add_multiplier(1).resolve()` | `n` | Multiplying by 1 is identity |
| `BigValue(n).add_multiplier(0).resolve()` | `0` | Zero multiplier collapses everything |
| `BigValue(0).add_multiplier(10**100).resolve()` | `0` | Zero base × anything = 0 |

### format_int suffixes

| Range | Suffix | Example |
|---|---|---|
| < 10³ | (none) | `999` |
| ≥ 10³ | K | `1.5K` |
| ≥ 10⁶ | M | `2.0M` |
| ≥ 10⁹ | B | `1.0B` |
| ≥ 10¹² | T | `1.0T` |
| ≥ 10¹⁵ | Q | `1.0Q` |
| ≥ 10¹⁸ | E | `100.0E` |

Values above 10¹⁸ still display correctly (e.g. 10^1000 → `"...E"`).

---

## Relic System

Relics are stored in `CombatState.relics: list[Relic]`. Each `Relic` carries a `tag: RelicTag | None` that identifies its mechanic. Effects are computed on-demand by pure functions in `src/application/relic_effects.py` — there are no callbacks, observers, or hidden side-effects.

### Four relics in the sample combat

| Name | Tag | Effect | When applied |
|---|---|---|---|
| Amuleto de Combate | `COMBAT_AMULET` | +1 mana maximum permanently | `draw_opening_hand()` at combat start |
| Tótem Roto | `BROKEN_TOTEM` | +1 card drawn per turn | `draw_opening_hand()` and `_begin_player_turn()` |
| Orbe de Fuego | `FIRE_ORB` | +2 flat damage on every attack played | `play_card()` when `card.total_damage() > 0` |
| Escudo Espectral | `SPECTRAL_SHIELD` | Survive a fatal hit at 1 HP (one-time use) | `_execute_intent()` after ATTACK damage |

### Four relics from the roguelike run

| Name | Tag | Effect | When applied |
|---|---|---|---|
| Piedra de Energía | `ENERGY_STONE` | +1 card drawn per turn (stacks with BROKEN_TOTEM) | `draw_opening_hand()` and `_begin_player_turn()` |
| Anillo de Oro | `GOLD_RING` | +15 gold after each combat | `apply_combat_victory()` in run_manager |
| Corazón de Hierro | `IRON_HEART` | +15 max HP (applied when relic is acquired) | `pick_treasure_relic()` / `pick_boss_relics()` |
| Poción de Sangre | `BLOOD_POTION` | Heal 8 HP after each combat | `post_combat_heal()` in run_manager |

### How to add a new relic

1. Add a new variant to `RelicTag` in `src/domain/relic.py`.
2. Add a query function in `src/application/relic_effects.py`.
3. Call it at the right point in `end_turn.py` or `play_card.py`.
4. Pass any UI hint (`bonus_damage`, etc.) from the scene to the widget/tooltip.
5. Add the relic to `create_sample_combat()` in `combat_manager.py`.
6. Write tests in `tests/test_relic.py`, `tests/test_relic_effects.py`, and the relevant use-case test file.

---

## Turn Pipeline

```
draw_opening_hand(state)         ← called once at combat start
  ├── random.shuffle(draw_pile)
  ├── COMBAT_AMULET: mana.maximum += 1; mana.refill()
  └── _draw_cards(5 + extra_draw_per_turn(relics) + player.luck // 5)

end_player_turn(state)           ← called each time player ends their turn
  ├── _discard_hand()            discard all hand cards
  ├── state.player.block = 0    STS rule: block resets BEFORE enemies act
  ├── _run_enemy_turn()
  │     ├── _execute_intent() for each living enemy
  │     │     └── ATTACK: apply damage → try_spectral_shield()
  │     └── _roll_intent()       random new intent for next turn
  └── _begin_player_turn()
        ├── state.turn += 1
        ├── state.mana.refill()
        └── _draw_cards(5 + extra_draw_per_turn(relics) + player.luck // 5)
```

**Important STS rule:** The player's block resets to 0 at end of their turn, _before_ enemies execute their intents. Block gained during the player's turn does **not** absorb enemy attacks that same turn.

---

## Character System

Three playable characters are defined in `src/domain/character.py`. Each has five stats that map to
Player fields and affect combat calculations:

| Stat | Player field | Effect |
|---|---|---|
| `damage` | `attack_bonus` | Flat bonus added to every attack card's effective damage |
| `max_hp` | `max_hp` / `current_hp` | Starting and maximum HP |
| `luck` | `luck` | Extra cards drawn per turn: `luck // 5` |
| `max_mana` | `mana.maximum` | Starting mana pool (before COMBAT_AMULET adds 1) |
| `dexterity` | `dexterity` | Flat bonus added to every block card's effective block |

The three characters (Guerrero / Mago / Pícaro) differ in these values so each offers a different playstyle.

### Scene flow

```
MainMenuScene
  → [Jugar]      → CharacterSelectScene
                      → [confirm]  → create_run() → MapScene
                                       → [COMBAT]    → CombatScene
                                                          → [combat_won] → CombatRewardScene → MapScene
                                                          → [death]      → DeathScene
                                                                               → [Nueva Partida] → CharacterSelectScene
                                                                               → [Menú]          → MainMenuScene
                                       → [TREASURE]  → TreasureScene → MapScene
                                       → [SHOP]      → ShopScene
                                                          → [pack]       → PackOpeningScene → ShopScene → MapScene
                                       → [EVENT]     → EventScene → MapScene
                                       → [BOSS]      → CombatScene(is_boss=True)
                                                          → [combat_won] → BossRewardScene
                                                                               → [open_pack]  → PackOpeningScene → BossRewardScene
                                                                               → [cleared]    → advance_floor() → MapScene
                      → [ESC]      → MainMenuScene
  → [Salir]      → quit
```

`SceneManager` in `main.py` stores `_run: Run | None` and drives all transitions. After each
`update()` call it inspects the top scene's flags and pushes/pops scenes accordingly. Flags are
reset immediately after being consumed.

---

## Roguelike Run System

A full roguelike run persists state across rooms via the `Run` domain object and the `run_manager` / `map_generator` use cases.

### Run object (`src/domain/run.py`)

`Run` is the single source of truth for everything that survives between rooms:

| Field | Type | Description |
|---|---|---|
| `character` | `Character` | Selected character (immutable after run start) |
| `seed` | `int` | RNG seed for deterministic map and reward generation |
| `floor` | `int` | Current floor (starts at 1, increments after boss) |
| `gold` | `int` | Current gold amount |
| `player_max_hp` | `int` | Maximum HP (can increase from relics) |
| `player_current_hp` | `int` | Current HP (persists across rooms) |
| `deck` | `list[Card]` | Full card collection (draw pile is rebuilt from this each combat) |
| `relics` | `list[Relic]` | Acquired relics (active from the moment they are added) |
| `current_map` | `GameMap` | The current floor's node map |
| `current_room_id` | `str \| None` | ID of the room the player is currently in |

Mutation methods: `add_card(card)`, `add_relic(relic)`, `apply_combat_result(hp_after)`.

### Seeded map generation (`src/application/map_generator.py`)

`generate_map(seed, floor) → GameMap` produces a deterministic STS-style map:

- **Seed formula**: `6364136223846793005 × seed + 1442695040888963407 × floor`
- **Dimensions**: rows = `min(7 + (floor-1)//2, 12)`, cols = `min(5 + (floor-1)//3, 8)`
- **Paths**: `min(3 + (floor-1)//3, 6)` independent paths from row 0 to boss row
- Mid-rows receive TREASURE, SHOP, and EVENT nodes; all other non-boss rooms are COMBAT

### Room types (`src/domain/map_node.py`)

| `RoomType` | Scene | Outcome |
|---|---|---|
| `COMBAT` | `CombatScene` | Fight enemies → `CombatRewardScene` (pick 1 of 3 cards, earn gold) |
| `TREASURE` | `TreasureScene` | Take or skip a free relic |
| `SHOP` | `ShopScene` → `PackOpeningScene` | Spend gold to buy a card pack (pick 1 of 5 cards) |
| `EVENT` | `EventScene` | Narrative event with gold reward |
| `BOSS` | `CombatScene(is_boss=True)` | Fight boss → `BossRewardScene` (gold + epic pack + relic choice) |

### Card packs (`src/domain/card_pool.py`)

Four pack themes are available in the shop. Each pack shows 5 cards; the player picks 1.

| `PackTheme` | Cost | Focus |
|---|---|---|
| `ACERO` | 75 gold | Attack cards |
| `ESCUDO` | 75 gold | Block / defense cards |
| `MAGIA` | 75 gold | Special / utility cards |
| `EPICO` | 150 gold | High-power mixed cards |

`starter_deck()` returns the initial 10-card deck used when creating a new run.
`card_factories_for_theme(theme)` returns a list of zero-argument callables that produce the cards belonging to that theme — used by `pick_pack_cards()`.

---

## Card Rendering

`draw_card()` in `card_widget.py` accepts `bonus_damage: int = 0`. The number shown in the card centre is always the **effective** value: `card.total_damage() + bonus_damage`.

The combat scene computes `bonus_damage` via `relic_effects.extra_attack_damage(state.relics)` for any card with `total_damage() > 0`, then passes it to both `draw_card()` and `card_tooltip()`.

`card_tooltip()` shows a breakdown when the bonus is non-zero:
```
Inflige 16 de daño a un enemigo.
  (14 + 2 del Orbe de Fuego)
```

`relic_tooltip()` appends `Estado: Activo` or `Estado: Agotado` so the player can see whether a one-time relic has already triggered.

---

## Test Suite

Run with: `uv run pytest tests/ -v`

One test file per source module. All test files follow the same structure:
1. Module-level docstring explaining scope and stress philosophy.
2. Imports.
3. Helper functions / fixtures (no pytest fixtures — plain functions).
4. `class Test<Topic>:` groups, one per concept.
5. `def test_<specific_case>(self):` methods with a single `assert`.

### Test files

| Test file | Module under test | Key areas covered |
|---|---|---|
| `test_numbers.py` | `domain/numbers.py` | resolve, flat/mult chains, 10^1000, 2^200, 1000-op chains, merge, format, display |
| `test_card.py` | `domain/card.py` | total_damage, total_block, stacking, modifiers, draw field, is_broken |
| `test_relic.py` | `domain/relic.py` | RelicTag enum (all 8 values), Relic creation, defaults, is_active mutation |
| `test_character.py` | `domain/character.py` | CharacterStats, Character frozen fields, ALL_CHARACTERS count and invariants |
| `test_entities.py` | `domain/entities.py` | is_alive (Player+Enemy), hp_ratio, dexterity/attack_bonus/luck defaults |
| `test_pile.py` | `domain/pile.py` | DrawPile/DiscardPile count, Hand count, is_full, max_size, mutations |
| `test_mana.py` | `domain/mana.py` | can_afford, spend, gain (capped), refill, boundary values, large amounts |
| `test_combat.py` | `domain/combat.py` | CombatState defaults, field storage, mutations, no-pygame-dependency |
| `test_map_node.py` | `domain/map_node.py` | RoomType enum, MapNode fields, connections, visited/available flags |
| `test_game_map.py` | `domain/game_map.py` | GameMap fields, available_nodes, mark_visited, boss_id |
| `test_run.py` | `domain/run.py` | Run creation, add_card, add_relic, apply_combat_result, field storage |
| `test_card_pool.py` | `domain/card_pool.py` | PackTheme enum, ALL_PACKS count/costs, starter_deck size, card_factories_for_theme |
| `test_relic_effects.py` | `application/relic_effects.py` | All 8 relic functions: active, inactive, two of same, relic without tag |
| `test_play_card.py` | `application/play_card.py` | Validation, damage, Fire Orb, attack_bonus, block, dexterity bonus, mana, draw |
| `test_end_turn.py` | `application/end_turn.py` | draw_opening_hand, end_player_turn, relic integration, STS block rule, luck draw |
| `test_combat_manager.py` | `application/combat_manager.py` | Structural integrity, relic tags, mana=4/4, hand=6, card pool total |
| `test_combat_factory.py` | `application/combat_factory.py` | Player stats from character, full HP enemies, mana setup, luck-based draw |
| `test_map_generator.py` | `application/map_generator.py` | Determinism, row/col/path counts per floor, room type distribution, boss placement |
| `test_run_manager.py` | `application/run_manager.py` | create_run, generate_enemies, generate_boss, apply_combat_victory, advance_floor |
| `test_card_rewards.py` | `application/card_rewards.py` | pick_reward_cards count, pick_pack_cards theme filtering, seeded determinism |

### Testing rules

- **Boundary values**: always test 0, 1, exact limit, limit+1, and huge numbers (10^9, 10^18, 10^1000).
- **Inactive relics**: test separately from active ones.
- **Combinations**: two of the same relic, mixed active/inactive.
- **No mocks**: instantiate domain objects directly — they have no side effects.
- **No pygame**: domain and application layers are pygame-free; tests must import without errors.
- **Concrete assertions**: assert exact values, not just `assert result.success`.
- **Stress tests**: include at least one test per file that operates at large scale (100+ iterations, 10^100+ values).
