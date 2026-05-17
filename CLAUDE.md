# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Last Wish** is a card game built with pygame, managed with uv. Python 3.13+ required.

## Commands

```bash
# Run the game
uv run main.py

# Add a dependency
uv add <package> --system-certs

# Run with a specific Python script
uv run <script>.py
```

## Language Convention

- **Code**: all identifiers, comments, docstrings, variable names, class names, and file names must be in **English**.
- **UI / dialog text**: all strings rendered on screen (menus, dialogs, card descriptions, player messages) must be in **Spanish**.

## Architecture

The project follows Clean Architecture with SOLID principles. Layers must not be crossed — outer layers depend on inner ones, never the reverse.

```
src/
  domain/        # Pure business logic: Card, Deck, Hand, Player, GameState — no pygame
  application/   # Use cases: deal, draw, play, score — orchestrate domain objects
  infrastructure/# pygame rendering, input handling, asset loading
  presentation/  # Screens, UI components, scene manager
main.py          # Entry point — wires layers together and starts the game loop
```

### Key design rules

- **Domain layer** has zero pygame imports. All game rules live here.
- **Use cases** in `application/` receive domain objects and return domain objects; they never call pygame.
- **Screens** in `presentation/` call use cases, never domain logic directly.
- Every public function, method, and class must have full type annotations (no `Any` unless unavoidable).
- Use `dataclass` or `NamedTuple` for value objects (Card, Score, etc.).
- Depend on abstractions: define `Protocol` interfaces in `domain/` or `application/` for things like renderers or repositories.

### pygame loop pattern

```python
# main.py wires everything and owns the clock
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
