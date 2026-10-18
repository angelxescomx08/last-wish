"""Repeatable CPU render benchmark; SDL dummy excludes real display/vsync cost.

Run: uv run python scripts/benchmark_performance.py --output tmp/performance.json
Use separate processes for before/after runs. Timings are not FPS guarantees.
"""
from __future__ import annotations

import argparse
import ast
import json
import hashlib
import random
import os
from pathlib import Path
import platform
import statistics
import sys
import subprocess
import types
from time import perf_counter

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pygame

from main import _prewarm_assets
from src.application.combat_manager import create_sample_combat
from src.infrastructure.fonts import FontRegistry
from src.infrastructure.sprite_loader import SpriteLoader
from src.infrastructure.viewport import Viewport
from src.presentation.scenes.combat_scene import CombatScene
from src.presentation.scenes.character_select_scene import CharacterSelectScene
from src.presentation.scenes.main_menu_scene import MainMenuScene


def use_baseline(ref: str) -> None:
    """Load the two infrastructure modules from Git without changing the checkout."""
    global SpriteLoader, Viewport, _prewarm_assets
    root = Path(__file__).resolve().parents[1]
    def source(path):
        return subprocess.run(
            ["git", "-c", f"safe.directory={root.as_posix()}", "show", f"{ref}:{path}"],
            cwd=root, check=True, capture_output=True, encoding="utf-8").stdout
    def module(path, name):
        loaded = types.ModuleType(name)
        loaded.__file__ = str(root / path)
        sys.modules[name] = loaded
        exec(compile(source(path), loaded.__file__, "exec"), loaded.__dict__)
        return loaded
    SpriteLoader = module("src/infrastructure/sprite_loader.py", "benchmark_baseline_sprites").SpriteLoader
    Viewport = module("src/infrastructure/viewport.py", "benchmark_baseline_viewport").Viewport
    import src.presentation.scenes.main_menu_scene as menu_module
    import src.presentation.scenes.combat_scene as combat_module
    menu_module.SpriteLoader = SpriteLoader
    combat_module.SpriteLoader = SpriteLoader
    import src.presentation.scenes.character_select_scene as select_module
    select_module.SpriteLoader = SpriteLoader
    main_source = source("main.py")
    node = next(n for n in ast.parse(main_source).body
                if isinstance(n, ast.FunctionDef) and n.name == "_prewarm_assets")
    namespace = {}
    exec(ast.get_source_segment(main_source, node), namespace)
    _prewarm_assets = namespace["_prewarm_assets"]


def timed(action) -> float:
    start = perf_counter()
    action()
    return (perf_counter() - start) * 1000


def summarize(samples: list[float]) -> dict:
    ordered = sorted(samples)
    return {
        "median_ms": statistics.median(samples),
        "p95_ms": ordered[int((len(ordered) - 1) * .95)],
        "p99_ms": ordered[int((len(ordered) - 1) * .99)],
        "max_ms": max(samples),
        "over_16_67_ms": sum(t > 1000 / 60 for t in samples),
        "samples": len(samples),
    }


def benchmark(frames: int) -> dict:
    random.seed(42)
    pygame.init()
    pygame.display.set_mode((1280, 720))
    fonts = FontRegistry()
    canvas = pygame.Surface((1280, 720))
    result = {"seed": 42, "combat_player": "La Guerrera",
              "python": platform.python_version(), "pygame": pygame.version.ver,
              "video_driver": pygame.display.get_driver(),
              "smoothscale_backend": pygame.transform.get_smoothscale_backend()}
    result["startup_prewarm_ms"] = timed(_prewarm_assets)
    menu = MainMenuScene(fonts)
    result["menu_first_draw_ms"] = timed(lambda: menu.draw(canvas))
    result["hero_new_loader_ms"] = [
        timed(lambda: SpriteLoader().get_player_animation_frames("idle", 192, "warrior"))
        for _ in range(5)
    ]
    start = perf_counter()
    state = create_sample_combat()
    state.player.name = "La Guerrera"
    combat = CombatScene(state, fonts)
    result["combat_constructor_ms"] = (perf_counter() - start) * 1000
    selection = CharacterSelectScene(fonts)
    result["selection_first_draw_ms"] = timed(lambda: selection.draw(canvas))
    result["selection_sha256"] = hashlib.sha256(pygame.image.tobytes(canvas, "RGB")).hexdigest()
    result["combat_first_draw_ms"] = timed(lambda: combat.draw(canvas))
    for label, scene in (("menu", menu), ("combat", combat)):
        def frame():
            scene.update(1 / 60)
            scene.draw(canvas)
        for _ in range(120):
            frame()
        result[label] = summarize([timed(frame) for _ in range(frames)])
        result[f"{label}_sha256"] = hashlib.sha256(pygame.image.tobytes(canvas, "RGB")).hexdigest()
    rect = combat._card_rects[2]
    combat.handle_event(pygame.event.Event(pygame.MOUSEMOTION, pos=rect.center,
                                         rel=(0, 0), buttons=(0, 0, 0)))
    def hover_frame():
        combat.update(1 / 60)
        combat.draw(canvas)
    result["hover_first_ms"] = timed(hover_frame)
    result["hover"] = summarize([timed(hover_frame) for _ in range(frames)])
    for size in ((1280, 720), (1920, 1080), (2560, 1440)):
        viewport = Viewport(*size)
        viewport.surface.blit(canvas, (0, 0))
        screen = pygame.Surface(size)
        for _ in range(30):
            viewport.present(screen)
        result[f"present_{size[0]}x{size[1]}"] = summarize(
            [timed(lambda: viewport.present(screen)) for _ in range(frames)])
        def combat_frame():
            combat.update(1 / 60)
            combat.draw(viewport.surface)
            viewport.present(screen)
        result[f"combat_total_{size[0]}x{size[1]}"] = summarize(
            [timed(combat_frame) for _ in range(frames)])
    pygame.quit()
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frames", type=int, default=300)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--baseline-ref", help="Compare a Git revision without checking it out")
    args = parser.parse_args()
    if args.frames < 1:
        parser.error("--frames must be positive")
    if args.baseline_ref:
        use_baseline(args.baseline_ref)
    result = benchmark(args.frames)
    result["baseline_ref"] = args.baseline_ref
    report = json.dumps(result, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(report + "\n", encoding="utf-8")
    print(report)
