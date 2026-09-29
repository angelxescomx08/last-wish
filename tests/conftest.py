"""Session-scoped pygame initialisation for tests that need pygame types."""
from __future__ import annotations

import pygame
import pytest


@pytest.fixture(scope="session", autouse=True)
def _pygame_session():
    pygame.init()
    yield
    pygame.quit()


@pytest.fixture(autouse=True)
def _default_tuning():
    """Every test starts from normal-play tuning (the Pruebas screen is global state)."""
    from src.domain.tuning import TUNING
    TUNING.reset()
    yield
    TUNING.reset()
