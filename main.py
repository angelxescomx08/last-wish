from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

import pygame

from src.application.combat_manager import create_sample_combat
from src.infrastructure.colors import BG_DARK, TEXT_ACCENT, TEXT_PRIMARY
from src.infrastructure.fonts import FontRegistry
from src.infrastructure.viewport import Viewport
from src.presentation.scenes.combat_scene import CombatScene


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

WINDOW_TITLE: str  = "Last Wish"
WINDOW_WIDTH: int  = 1280
WINDOW_HEIGHT: int = 720
TARGET_FPS: int    = 60

# Minimum window size — keeps the UI usable when resizing manually
MIN_W: int = 480
MIN_H: int = 270


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
        self._fonts          = fonts
        self._blink_timer    = 0.0
        self._show_prompt    = True
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
            self.push(CombatScene(create_sample_combat(), fonts))

    def draw(self, surface: pygame.Surface) -> None:
        self._top().draw(surface)


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

    # Resizable window — adapts to phone landscape, tablet, or desktop
    screen = pygame.display.set_mode(
        (settings.width, settings.height),
        pygame.RESIZABLE,
    )
    pygame.display.set_caption(settings.title)

    viewport      = Viewport(settings.width, settings.height)
    fonts         = FontRegistry()
    scene_manager = SceneManager(MainMenu(fonts))
    clock         = pygame.time.Clock()

    running = True
    while running:
        dt: float = clock.tick(settings.fps) / 1000.0

        # Sync viewport if window was resized (pygame 2 updates surface size automatically)
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
