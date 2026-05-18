# Architecture

Last Wish follows **Clean Architecture** with SOLID principles.
Layers form a strict dependency hierarchy — outer layers depend on inner ones, never the reverse.

---

## Layer diagram

```
┌─────────────────────────────────────────────────────┐
│                   presentation/                      │
│   scenes/combat_scene.py                            │
│   ui/ card_widget · entity_widget · hud_widget      │
│       tooltip · pile_viewer                         │
└───────────────────┬─────────────────────────────────┘
                    │ calls use cases
┌───────────────────▼─────────────────────────────────┐
│                   application/                       │
│   play_card · end_turn · relic_effects              │
│   combat_manager                                    │
└───────────────────┬─────────────────────────────────┘
                    │ reads / mutates
┌───────────────────▼─────────────────────────────────┐
│                    domain/                           │
│   combat · card · relic · entities                  │
│   pile · mana · numbers                             │
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
| `relic.py` | `Relic`, `RelicTag` |
| `entities.py` | `Player`, `Enemy`, `Intent`, `IntentType`, `StatusEffect` |
| `pile.py` | `DrawPile`, `DiscardPile`, `Hand` |
| `mana.py` | `Mana` |
| `combat.py` | `CombatState` |

### `src/application/`  — Use cases, zero pygame

| File | Public API |
|---|---|
| `relic_effects.py` | `extra_draw_per_turn`, `extra_attack_damage`, `bonus_starting_mana`, `try_spectral_shield` |
| `play_card.py` | `play_card(state, card_index, target_enemy_index) → PlayResult` |
| `end_turn.py` | `end_player_turn(state)`, `draw_opening_hand(state)` |
| `combat_manager.py` | `create_sample_combat() → CombatState` |

### `src/infrastructure/`  — pygame utilities

| File | Key exports |
|---|---|
| `colors.py` | 49 named `pygame.Color` constants |
| `fonts.py` | `FontRegistry` — lazy SysFont cache keyed by point size |
| `viewport.py` | `Viewport`, `VIRTUAL_W = 1280`, `VIRTUAL_H = 720` |

### `src/presentation/`  — Screens and widgets

| File | Responsibility |
|---|---|
| `scenes/combat_scene.py` | Full battle screen: input, layout, hover, tooltip dispatch |
| `ui/card_widget.py` | `draw_card(…, bonus_damage=0)` → `pygame.Rect` |
| `ui/entity_widget.py` | `draw_player()`, `draw_enemy()` → `pygame.Rect` |
| `ui/hud_widget.py` | Relic bar, mana, pile buttons, turn counter, End Turn button |
| `ui/tooltip.py` | Content generators + `draw_tooltip()` renderer |
| `ui/pile_viewer.py` | `PileViewer` — modal card list overlay |

---

## Entry point

`main.py` owns the pygame loop and wires all layers:

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

Scenes implement `handle_event(event)`, `update(dt)`, and `draw(surface)`.
`SceneManager` maintains a stack — push to enter a new screen, pop to return.
