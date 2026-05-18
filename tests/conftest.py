"""Session-scoped pygame initialisation for tests that need pygame types."""
from __future__ import annotations

import pygame
import pytest


@pytest.fixture(scope="session", autouse=True)
def _pygame_session():
    pygame.init()
    yield
    pygame.quit()
