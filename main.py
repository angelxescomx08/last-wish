from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

import pygame

from src.application.combat_factory import create_combat_for_character
from src.infrastructure.colors import TEXT_ACCENT, TEXT_PRIMARY
from src.infrastructure.fonts import FontRegistry
from src.infrastructure.viewport import Viewport
from src.presentation.scenes.character_select_scene import CharacterSelectScene
from src.presentation.scenes.combat_scene import CombatScene
from src.presentation.scenes.death_scene import DeathAction, DeathScene
from src.presentation.scenes.main_menu_scene import MainMenuScene, MenuAction


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

WINDOW_TITLE: str  = "Last Wish"
WINDOW_WIDTH: int  = 1280
WINDOW_HEIGHT: int = 720
TARGET_FPS: int    = 60

MIN_W: int = 480
MIN_H: int = 270


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class GameSettings:
    width: int
    height: int
    fps: int
    title: str


# ---------------------------------------------------------------------------
# Scene protocol
# ---------------------------------------------------------------------------

@runtime_checkable
class Scene(Protocol):
    def handle_event(self, event: pygame.event.Event) -> None: ...
    def update(self, dt: float) -> None: ...
    def draw(self, surface: pygame.Surface) -> None: ...


# ---------------------------------------------------------------------------
# Scene manager
# ---------------------------------------------------------------------------

class SceneManager:
    """Stack-based scene manager that drives all scene transitions.

    Transition rules (checked once per update tick, top of stack):
      MainMenuScene   → PLAY action   → push CharacterSelectScene
      MainMenuScene   → EXIT action   → set quit_requested
      CharacterSelectScene → confirmed→ push CombatScene (via combat_factory)
      CharacterSelectScene → back     → pop (return to MainMenuScene)
      CombatScene     → death         → push DeathScene
      DeathScene      → NEW_GAME      → pop all, push CharacterSelectScene
      DeathScene      → MAIN_MENU     → pop all (reveal MainMenuScene)
    """

    def __init__(self, initial: Scene) -> None:
        self._stack:         list[Scene] = [initial]
        self.quit_requested: bool        = False

    def push(self, scene: Scene) -> None:
        self._stack.append(scene)

    def pop(self) -> None:
        if len(self._stack) > 1:
            self._stack.pop()

    def _pop_all_except_first(self) -> None:
        while len(self._stack) > 1:
            self._stack.pop()

    def _top(self) -> Scene:
        return self._stack[-1]

    def handle_event(self, event: pygame.event.Event) -> None:
        self._top().handle_event(event)

    def update(self, dt: float, fonts: FontRegistry) -> None:
        top = self._top()
        top.update(dt)
        self._handle_transitions(top, fonts)

    def draw(self, surface: pygame.Surface) -> None:
        self._top().draw(surface)

    # ------------------------------------------------------------------
    # Transition logic
    # ------------------------------------------------------------------

    def _handle_transitions(self, top: Scene, fonts: FontRegistry) -> None:
        if isinstance(top, MainMenuScene):
            self._transition_main_menu(top, fonts)

        elif isinstance(top, CharacterSelectScene):
            self._transition_character_select(top, fonts)

        elif isinstance(top, CombatScene):
            self._transition_combat(top, fonts)

        elif isinstance(top, DeathScene):
            self._transition_death(top, fonts)

    def _transition_main_menu(self, scene: MainMenuScene, fonts: FontRegistry) -> None:
        action = scene.requested_action
        if action is None:
            return
        scene.requested_action = None          # consume

        if action == MenuAction.PLAY:
            self.push(CharacterSelectScene(fonts))
        elif action == MenuAction.EXIT:
            self.quit_requested = True

    def _transition_character_select(
        self, scene: CharacterSelectScene, fonts: FontRegistry
    ) -> None:
        if scene.confirmed:
            scene.confirmed = False            # consume
            state = create_combat_for_character(scene.selected_character)
            self.push(CombatScene(state, fonts))

        elif scene.back_to_menu:
            scene.back_to_menu = False         # consume
            self.pop()

    def _transition_combat(self, scene: CombatScene, fonts: FontRegistry) -> None:
        if scene.death_occurred and not scene._death_acknowledged:
            scene._death_acknowledged = True
            self.push(DeathScene(fonts, scene.turn_reached))

    def _transition_death(self, scene: DeathScene, fonts: FontRegistry) -> None:
        action = scene.requested_action
        if action is None:
            return
        scene.requested_action = None          # consume

        if action == DeathAction.NEW_GAME:
            self._pop_all_except_first()
            self.push(CharacterSelectScene(fonts))
        elif action == DeathAction.MAIN_MENU:
            self._pop_all_except_first()


# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------

def _transform_mouse(event: pygame.event.Event, viewport: Viewport) -> pygame.event.Event:
    """Re-map a mouse event's .pos from actual screen to virtual canvas coords."""
    _MOUSE = (pygame.MOUSEMOTION, pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP)
    if event.type not in _MOUSE:
        return event
    attrs = dict(event.__dict__)
    attrs["pos"] = viewport.to_virtual(event.pos)
    if "rel" in attrs and viewport._scale > 0:
        rx, ry = event.rel
        attrs["rel"] = (rx / viewport._scale, ry / viewport._scale)
    return pygame.event.Event(event.type, attrs)


def run(settings: GameSettings) -> None:
    pygame.init()

    screen = pygame.display.set_mode(
        (settings.width, settings.height),
        pygame.RESIZABLE,
    )
    pygame.display.set_caption(settings.title)

    viewport      = Viewport(settings.width, settings.height)
    fonts         = FontRegistry()
    scene_manager = SceneManager(MainMenuScene(fonts))
    clock         = pygame.time.Clock()

    running = True
    while running:
        dt: float = clock.tick(settings.fps) / 1000.0

        actual_w, actual_h = screen.get_size()
        if (actual_w, actual_h) != (viewport._dest_w + viewport._off_x * 2,
                                    viewport._dest_h + viewport._off_y * 2):
            viewport.resize(
                max(actual_w, MIN_W),
                max(actual_h, MIN_H),
            )

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.WINDOWRESIZED:
                viewport.resize(
                    max(event.x, MIN_W),
                    max(event.y, MIN_H),
                )
            else:
                scene_manager.handle_event(_transform_mouse(event, viewport))

        scene_manager.update(dt, fonts)

        if scene_manager.quit_requested:
            running = False

        scene_manager.draw(viewport.surface)
        viewport.present(screen)
        pygame.display.flip()

    pygame.quit()


def main() -> None:
    run(GameSettings(
        width=WINDOW_WIDTH,
        height=WINDOW_HEIGHT,
        fps=TARGET_FPS,
        title=WINDOW_TITLE,
    ))


if __name__ == "__main__":
    main()
