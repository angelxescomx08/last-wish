"""Animated GIF of the Gachapón room (needs Pillow).

    uv run --with pillow scripts/export_gacha_preview.py

Records a normal pull (forced to Poco común, then declined) and a stellar pull
(forced to Legendaria, kept) through the real ``GachaScene`` with the shared gold
counter, and writes ``output/gacha-preview.gif`` (640×360 to keep it small).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pygame  # noqa: E402
from PIL import Image  # noqa: E402

from src.application.run_manager import _all_relic_defs, create_run  # noqa: E402
from src.domain.character import ALL_CHARACTERS  # noqa: E402
from src.domain.gacha import PullKind  # noqa: E402
from src.domain.rarity import Rarity  # noqa: E402
from src.infrastructure.fonts import FontRegistry  # noqa: E402
from src.presentation.scenes.gacha_scene import GachaScene  # noqa: E402
from src.presentation.ui.gold_hud import GoldHud  # noqa: E402

FPS = 15


def main() -> None:
    pygame.init()
    pygame.display.set_mode((1280, 720))
    run = create_run(ALL_CHARACTERS[0], 7)
    run.gold = 900
    scene = GachaScene(run, FontRegistry())
    hud = GoldHud(FontRegistry())
    hud.sync(run.gold)
    surf = pygame.display.get_surface()
    frames: list[Image.Image] = []

    def record(seconds: float, click_at: float | None = None) -> None:
        for k in range(int(seconds * FPS)):
            if click_at is not None and abs(k / FPS - click_at) < 0.5 / FPS:
                scene.advance()
            scene.update(1 / FPS)
            hud.update(1 / FPS, run.gold)
            scene.draw(surf)
            hud.draw(surf, *scene.gold_hud_pos)
            small = pygame.transform.smoothscale(surf, (640, 360))
            frames.append(Image.frombytes("RGB", (640, 360), pygame.image.tobytes(small, "RGB"))
                          .quantize(colors=224, method=Image.Quantize.FASTOCTREE, dither=Image.Dither.NONE))

    record(1.0)
    for kind, tier in ((PullKind.NORMAL, Rarity.UNCOMMON), (PullKind.STELLAR, Rarity.LEGENDARY)):
        scene.start_pull(kind)
        scene.result.relic = next(r for r in _all_relic_defs() if r.rarity is tier)
        record(4.0 + 0.5 * tier.value)                    # coin, crank, drop, shakes
        scene.advance() if scene.phase == "present" else None
        record(2.6)                                       # open + reveal
        if tier is Rarity.UNCOMMON:
            scene.decline()
        else:
            scene.keep()
        record(0.9)                                       # collect / discard
    OUT = ROOT / "output"
    OUT.mkdir(exist_ok=True)
    path = OUT / "gacha-preview.gif"
    frames[0].save(path, save_all=True, append_images=frames[1:], duration=1000 // FPS, loop=0, optimize=True)
    print(f"wrote {path.relative_to(ROOT)} ({len(frames)} frames)")


if __name__ == "__main__":
    main()
