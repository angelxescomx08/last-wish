from __future__ import annotations

import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

import pygame


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

WINDOW_TITLE: str = "Last Wish"
WINDOW_WIDTH: int = 1280
WINDOW_HEIGHT: int = 720
TARGET_FPS: int = 60

COLOR_BACKGROUND: pygame.Color = pygame.Color(20, 40, 20)
COLOR_TEXT: pygame.Color = pygame.Color(230, 220, 200)
COLOR_ACCENT: pygame.Color = pygame.Color(200, 170, 80)

FONT_SIZE_TITLE: int = 64
FONT_SIZE_BODY: int = 28


# ---------------------------------------------------------------------------
# Domain — pure value objects, no pygame
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class GameSettings:
    width: int
    height: int
    fps: int
    title: str


# ---------------------------------------------------------------------------
# Application — use-case interfaces (Protocols)
# ---------------------------------------------------------------------------

@runtime_checkable
class Scene(Protocol):
    """Contract every scene must fulfill."""

    def handle_event(self, event: pygame.event.Event) -> None: ...
    def update(self, dt: float) -> None: ...
    def draw(self, surface: pygame.Surface) -> None: ...


# ---------------------------------------------------------------------------
# Infrastructure — pygame helpers
# ---------------------------------------------------------------------------

class FontRegistry:
    """Loads and caches pygame fonts."""

    def __init__(self) -> None:
        self._cache: dict[int, pygame.font.Font] = {}

    def get(self, size: int) -> pygame.font.Font:
        if size not in self._cache:
            self._cache[size] = pygame.font.SysFont("serif", size)
        return self._cache[size]


# ---------------------------------------------------------------------------
# Presentation — scenes
# ---------------------------------------------------------------------------

class MainMenuScene(ABC):
    """Abstract base for scenes that own a font registry."""

    def __init__(self, fonts: FontRegistry) -> None:
        self._fonts = fonts


class MainMenu(MainMenuScene):
    """Entry screen shown when the game starts."""

    # Spanish UI text
    _TITLE: str = "Último Deseo"
    _SUBTITLE: str = "Un juego de cartas"
    _PROMPT: str = "Presiona cualquier tecla para comenzar"

    def __init__(self, fonts: FontRegistry) -> None:
        super().__init__(fonts)
        self._blink_timer: float = 0.0
        self._show_prompt: bool = True
        self._exit_requested: bool = False

    @property
    def exit_requested(self) -> bool:
        return self._exit_requested

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN:
            self._exit_requested = True

    def update(self, dt: float) -> None:
        self._blink_timer += dt
        if self._blink_timer >= 0.6:
            self._show_prompt = not self._show_prompt
            self._blink_timer = 0.0

    def draw(self, surface: pygame.Surface) -> None:
        surface.fill(COLOR_BACKGROUND)

        title_font = self._fonts.get(FONT_SIZE_TITLE)
        body_font = self._fonts.get(FONT_SIZE_BODY)

        cx: int = surface.get_width() // 2

        title_surf = title_font.render(self._TITLE, True, COLOR_ACCENT)
        title_rect = title_surf.get_rect(centerx=cx, centery=240)
        surface.blit(title_surf, title_rect)

        subtitle_surf = body_font.render(self._SUBTITLE, True, COLOR_TEXT)
        subtitle_rect = subtitle_surf.get_rect(centerx=cx, centery=320)
        surface.blit(subtitle_surf, subtitle_rect)

        if self._show_prompt:
            prompt_surf = body_font.render(self._PROMPT, True, COLOR_TEXT)
            prompt_rect = prompt_surf.get_rect(centerx=cx, centery=500)
            surface.blit(prompt_surf, prompt_rect)


class ComingSoonScene:
    """Placeholder scene for game content not yet implemented."""

    _MESSAGE: str = "Próximamente..."
    _BACK: str = "Presiona Escape para volver"

    def __init__(self, fonts: FontRegistry) -> None:
        self._fonts = fonts
        self._back_requested: bool = False

    @property
    def back_requested(self) -> bool:
        return self._back_requested

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self._back_requested = True

    def update(self, dt: float) -> None:
        pass

    def draw(self, surface: pygame.Surface) -> None:
        surface.fill(COLOR_BACKGROUND)
        font = self._fonts.get(FONT_SIZE_TITLE)
        body_font = self._fonts.get(FONT_SIZE_BODY)
        cx: int = surface.get_width() // 2

        msg_surf = font.render(self._MESSAGE, True, COLOR_ACCENT)
        surface.blit(msg_surf, msg_surf.get_rect(centerx=cx, centery=300))

        back_surf = body_font.render(self._BACK, True, COLOR_TEXT)
        surface.blit(back_surf, back_surf.get_rect(centerx=cx, centery=420))


# ---------------------------------------------------------------------------
# Presentation — scene manager (stack-based)
# ---------------------------------------------------------------------------

class SceneManager:
    """Owns the scene stack and routes pygame events."""

    def __init__(self, initial_scene: Scene) -> None:
        self._stack: list[Scene] = [initial_scene]

    def push(self, scene: Scene) -> None:
        self._stack.append(scene)

    def pop(self) -> None:
        if len(self._stack) > 1:
            self._stack.pop()

    def _current(self) -> Scene:
        return self._stack[-1]

    def handle_event(self, event: pygame.event.Event) -> None:
        self._current().handle_event(event)

    def update(self, dt: float) -> None:
        current = self._current()
        current.update(dt)

        if isinstance(current, MainMenu) and current.exit_requested:
            self.push(ComingSoonScene(FontRegistry()))

        if isinstance(current, ComingSoonScene) and current.back_requested:
            self.pop()

    def draw(self, surface: pygame.Surface) -> None:
        self._current().draw(surface)


# ---------------------------------------------------------------------------
# Application bootstrap
# ---------------------------------------------------------------------------

def build_window(settings: GameSettings) -> pygame.Surface:
    return pygame.display.set_mode((settings.width, settings.height))


def run(settings: GameSettings) -> None:
    pygame.init()

    screen = build_window(settings)
    pygame.display.set_caption(settings.title)

    fonts = FontRegistry()
    scene_manager = SceneManager(MainMenu(fonts))
    clock = pygame.time.Clock()

    running: bool = True
    while running:
        dt: float = clock.tick(settings.fps) / 1000.0

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            else:
                scene_manager.handle_event(event)

        scene_manager.update(dt)
        scene_manager.draw(screen)
        pygame.display.flip()

    pygame.quit()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    settings = GameSettings(
        width=WINDOW_WIDTH,
        height=WINDOW_HEIGHT,
        fps=TARGET_FPS,
        title=WINDOW_TITLE,
    )
    run(settings)


if __name__ == "__main__":
    main()
