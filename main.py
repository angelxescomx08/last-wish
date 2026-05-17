from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

import pygame

from src.application.combat_manager import create_sample_combat
from src.infrastructure.colors import BG_DARK, TEXT_ACCENT, TEXT_PRIMARY
from src.infrastructure.fonts import FontRegistry
from src.presentation.scenes.combat_scene import CombatScene


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

WINDOW_TITLE: str  = "Last Wish"
WINDOW_WIDTH: int  = 1280
WINDOW_HEIGHT: int = 720
TARGET_FPS: int    = 60


# ---------------------------------------------------------------------------
# Domain
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
# Main menu
# ---------------------------------------------------------------------------

class MainMenu:
    _TITLE:    str = "Último Deseo"
    _SUBTITLE: str = "Un juego de cartas"
    _PROMPT:   str = "Presiona cualquier tecla para comenzar"

    def __init__(self, fonts: FontRegistry) -> None:
        self._fonts         = fonts
        self._blink_timer   = 0.0
        self._show_prompt   = True
        self.start_requested = False

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN:
            self.start_requested = True

    def update(self, dt: float) -> None:
        self._blink_timer += dt
        if self._blink_timer >= 0.55:
            self._show_prompt = not self._show_prompt
            self._blink_timer = 0.0

    def draw(self, surface: pygame.Surface) -> None:
        surface.fill(pygame.Color(14, 20, 14))
        cx = surface.get_width() // 2

        title_surf = self._fonts.get(68).render(self._TITLE, True, TEXT_ACCENT)
        surface.blit(title_surf, title_surf.get_rect(centerx=cx, centery=240))

        sub_surf = self._fonts.get(28).render(self._SUBTITLE, True, TEXT_PRIMARY)
        surface.blit(sub_surf, sub_surf.get_rect(centerx=cx, centery=325))

        if self._show_prompt:
            prompt_surf = self._fonts.get(22).render(self._PROMPT, True, TEXT_PRIMARY)
            surface.blit(prompt_surf, prompt_surf.get_rect(centerx=cx, centery=500))


# ---------------------------------------------------------------------------
# Scene manager
# ---------------------------------------------------------------------------

class SceneManager:
    def __init__(self, initial: Scene) -> None:
        self._stack: list[Scene] = [initial]

    def push(self, scene: Scene) -> None:
        self._stack.append(scene)

    def pop(self) -> None:
        if len(self._stack) > 1:
            self._stack.pop()

    def _top(self) -> Scene:
        return self._stack[-1]

    def handle_event(self, event: pygame.event.Event) -> None:
        self._top().handle_event(event)

    def update(self, dt: float, fonts: FontRegistry) -> None:
        top = self._top()
        top.update(dt)
        if isinstance(top, MainMenu) and top.start_requested:
            combat_state = create_sample_combat()
            self.push(CombatScene(combat_state, fonts))

    def draw(self, surface: pygame.Surface) -> None:
        self._top().draw(surface)


# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------

def run(settings: GameSettings) -> None:
    pygame.init()
    screen = pygame.display.set_mode((settings.width, settings.height))
    pygame.display.set_caption(settings.title)

    fonts        = FontRegistry()
    scene_manager = SceneManager(MainMenu(fonts))
    clock        = pygame.time.Clock()

    running = True
    while running:
        dt: float = clock.tick(settings.fps) / 1000.0

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            else:
                scene_manager.handle_event(event)

        scene_manager.update(dt, fonts)
        scene_manager.draw(screen)
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
