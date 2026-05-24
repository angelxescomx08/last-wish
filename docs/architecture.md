# Architecture

Last Wish follows **Clean Architecture** with SOLID principles.
Layers form a strict dependency hierarchy — outer layers depend on inner ones, never the reverse.

---

## Layer diagram

```
┌─────────────────────────────────────────────────────┐
│                   presentation/                      │
│   scenes/ main_menu · character_select             │
│           combat · death · map · combat_reward      │
│           treasure · shop · pack_opening            │
│           event · boss_reward                       │
│   ui/ card_widget · entity_widget · hud_widget      │
│       tooltip · pile_viewer                         │
└───────────────────┬─────────────────────────────────┘
                    │ calls use cases
┌───────────────────▼─────────────────────────────────┐
│                   application/                       │
│   play_card · end_turn · relic_effects              │
│   combat_manager · combat_factory                   │
│   map_generator · run_manager · card_rewards        │
└───────────────────┬─────────────────────────────────┘
                    │ reads / mutates
┌───────────────────▼─────────────────────────────────┐
│                    domain/                           │
│   combat · card · relic · character                 │
│   entities · pile · mana · numbers                  │
│   map_node · game_map · run · card_pool             │
└─────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────┐
│                 infrastructure/                      │
│   colors · fonts · viewport                         │
│   (used by presentation only)                       │
└─────────────────────────────────────────────────────┘
```

---

## Dependency rule (enforced)

| Layer | May import from | Must NOT import from |
|---|---|---|
| `domain/` | standard library only | application, infrastructure, presentation |
| `application/` | domain | infrastructure, presentation |
| `infrastructure/` | pygame, standard library | application, domain, presentation |
| `presentation/` | application, infrastructure, domain | (none) |

Violation = a higher layer leaking into a lower layer (e.g. domain importing pygame).

---

## File map

### `src/domain/`  — Pure business logic, zero pygame

| File | Key exports |
|---|---|
| `numbers.py` | `BigValue`, `Operation` |
| `card.py` | `Card`, `CardEffect`, `CardModifier`, `CardType`, `ModifierTag` |
| `relic.py` | `Relic`, `RelicTag` (8 tags total) |
| `character.py` | `Character`, `CharacterStats`, `CharacterId`, `ALL_CHARACTERS` |
| `entities.py` | `Player`, `Enemy`, `Intent`, `IntentType`, `StatusEffect` |
| `pile.py` | `DrawPile`, `DiscardPile`, `Hand` |
| `mana.py` | `Mana` |
| `combat.py` | `CombatState` |
| `map_node.py` | `MapNode`, `RoomType` |
| `game_map.py` | `GameMap` |
| `run.py` | `Run` |
| `card_pool.py` | `PackTheme`, `PackDef`, `ALL_PACKS`, `starter_deck`, `card_factories_for_theme` |

### `src/application/`  — Use cases, zero pygame

| File | Public API |
|---|---|
| `relic_effects.py` | `extra_draw_per_turn`, `extra_attack_damage`, `bonus_starting_mana`, `try_spectral_shield`, `bonus_gold_reward`, `post_combat_heal`, `max_hp_bonus` |
| `play_card.py` | `play_card(state, card_index, target_enemy_index) → PlayResult` |
| `end_turn.py` | `end_player_turn(state)`, `draw_opening_hand(state)` |
| `combat_manager.py` | `create_sample_combat() → CombatState` — dev/test fixture |
| `combat_factory.py` | `create_combat_for_character(character) → CombatState`; `create_combat_from_run(run, enemies) → CombatState` |
| `map_generator.py` | `generate_map(seed, floor) → GameMap` — seeded STS-style path-based generation |
| `run_manager.py` | `create_run(character, seed) → Run`; `generate_enemies`, `generate_boss`, `apply_combat_victory`, `generate_event_gold`, `pick_treasure_relic`, `pick_boss_relics`, `advance_floor` |
| `card_rewards.py` | `pick_reward_cards(run, room_id, count=3) → list[Card]`; `pick_pack_cards(run, theme, count=5) → list[Card]` |

### `src/infrastructure/`  — pygame utilities

| File | Key exports |
|---|---|
| `colors.py` | 49 named `pygame.Color` constants |
| `fonts.py` | `FontRegistry` — lazy SysFont cache keyed by point size |
| `viewport.py` | `Viewport`, `VIRTUAL_W = 1280`, `VIRTUAL_H = 720` |

### `src/presentation/`  — Screens and widgets

| File | Responsibility |
|---|---|
| `scenes/main_menu_scene.py` | Main menu with Jugar/Continuar, Ajustes (stub), Salir |
| `scenes/character_select_scene.py` | Three-panel character selector with stat bars; seed text input field; `seed: int` property |
| `scenes/combat_scene.py` | Full battle screen: input, layout, hover, tooltip dispatch. `is_boss` param, `combat_won` property |
| `scenes/death_scene.py` | Death screen with Nueva Partida / Menú Principal options |
| `scenes/map_scene.py` | STS-style node map display; signals `selected_node: MapNode \| None` |
| `scenes/combat_reward_scene.py` | Gold display + 3 card choices after a non-boss combat |
| `scenes/treasure_scene.py` | Show a relic and let the player take or skip it |
| `scenes/shop_scene.py` | 4 pack tiles with gold cost; signals `selected_pack: PackTheme \| None` |
| `scenes/pack_opening_scene.py` | 5-card pick-1 overlay; signals `chosen_card: Card \| None` |
| `scenes/event_scene.py` | Spanish narrative text + gold pickup ("Recoger" button) |
| `scenes/boss_reward_scene.py` | 3-phase reward (gold → epic pack → relic choice); signals `chosen_relic: Relic \| None` |
| `ui/card_widget.py` | `draw_card(…, bonus_damage=0, bonus_block=0)` → `pygame.Rect` |
| `ui/entity_widget.py` | `draw_player()`, `draw_enemy()` → `pygame.Rect` |
| `ui/hud_widget.py` | Relic bar, mana, pile buttons, turn counter, End Turn button |
| `ui/tooltip.py` | Content generators + `draw_tooltip()` renderer |
| `ui/pile_viewer.py` | `PileViewer` — modal card list overlay |

---

## Scene flow

```
MainMenuScene
  → [Jugar / Continuar]  → CharacterSelectScene
                               → [confirm]  → create_run() → MapScene
                                                → [COMBAT node]   → CombatScene
                                                                       → [combat_won]  → CombatRewardScene → MapScene
                                                                       → [death]       → DeathScene
                                                                                             → [Nueva Partida] → CharacterSelectScene
                                                                                             → [Menú]          → MainMenuScene
                                                → [TREASURE node] → TreasureScene → MapScene
                                                → [SHOP node]     → ShopScene
                                                                       → [pack picked] → PackOpeningScene → ShopScene → MapScene
                                                → [EVENT node]    → EventScene → MapScene
                                                → [BOSS node]     → CombatScene(is_boss=True)
                                                                       → [combat_won]  → BossRewardScene
                                                                                             → [open_pack]    → PackOpeningScene → BossRewardScene
                                                                                             → [cleared]      → advance_floor() → MapScene (next floor)
                               → [ESC]      → MainMenuScene (pop)
  → [Salir]              → quit
```

`SceneManager` in `main.py` stores `_run: Run | None` and drives all transitions. After each
`update()` tick it reads the top scene's flags and pushes/pops accordingly. Each flag is reset
immediately after being consumed to prevent re-triggering on the following frame.

| Scene | Signal fields |
|---|---|
| `MainMenuScene` | `requested_action: MenuAction \| None` |
| `CharacterSelectScene` | `confirmed: bool`, `back_to_menu: bool`, `seed: int` |
| `MapScene` | `selected_node: MapNode \| None` |
| `CombatScene` | `death_occurred: bool`, `combat_won: bool`, `is_boss: bool`, `state` property |
| `DeathScene` | `requested_action: DeathAction \| None` |
| `CombatRewardScene` | `cleared: bool`, `chosen_card: Card \| None` |
| `TreasureScene` | `cleared: bool`, `took_relic: bool` |
| `ShopScene` | `selected_pack: PackTheme \| None`, `cleared: bool` |
| `PackOpeningScene` | `cleared: bool`, `chosen_card: Card \| None` |
| `EventScene` | `cleared: bool` |
| `BossRewardScene` | `cleared: bool`, `open_pack_requested: bool`, `chosen_relic: Relic \| None` |

---

## Entry point

`main.py` owns the pygame loop and wires all layers:

```python
clock         = pygame.time.Clock()
scene_manager = SceneManager(MainMenuScene(fonts))

while running:
    dt = clock.tick(60) / 1000.0
    for event in pygame.event.get():
        scene_manager.handle_event(_transform_mouse(event, viewport))
    scene_manager.update(dt, fonts)
    if scene_manager.quit_requested:
        running = False
    scene_manager.draw(viewport.surface)
    viewport.present(screen)
    pygame.display.flip()
```

Scenes implement `handle_event(event)`, `update(dt)`, and `draw(surface)`.
`SceneManager` maintains a stack — push to enter a new screen, pop to return.
`SceneManager.quit_requested` is set to `True` when the player chooses Salir.
