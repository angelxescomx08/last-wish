from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Relic:
    id: str
    name: str
    description: str
    is_active: bool = True
