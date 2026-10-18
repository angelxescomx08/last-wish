"""Alternate original/current frames in one process to reduce timing noise.

Run: uv run python scripts/benchmark_paired_render.py --baseline-ref HEAD
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import random

import benchmark_performance as benchmark
import pygame


def compare(ref: str, frames: int) -> dict:
    pygame.init()
    pygame.display.set_mode((1280, 720))
    fonts = benchmark.FontRegistry()
    benchmark._prewarm_assets()

    def scenes():
        random.seed(42)
        state = benchmark.create_sample_combat()
        state.player.name = "La Guerrera"
        return (benchmark.MainMenuScene(fonts), benchmark.CombatScene(state, fonts))

    current = scenes()
    canvases = {key: pygame.Surface((1280, 720)) for key in ("before", "after")}
    for scene in current:
        scene.draw(canvases["after"])
    benchmark.use_baseline(ref)
    original = scenes()
    for scene in original:
        scene.draw(canvases["before"])
    result = {"baseline_ref": ref, "video_driver": pygame.display.get_driver(), "seed": 42}
    for label, old, new in (("menu", original[0], current[0]),
                            ("combat", original[1], current[1]),
                            ("hover", original[1], current[1])):
        if label == "hover":
            for scene in (old, new):
                scene.handle_event(pygame.event.Event(
                    pygame.MOUSEMOTION, pos=scene._card_rects[2].center,
                    rel=(0, 0), buttons=(0, 0, 0)))
        def frame(scene, variant):
            scene.update(1 / 60)
            scene.draw(canvases[variant])
        for _ in range(120):
            frame(old, "before")
            frame(new, "after")
        samples = {"before": [], "after": []}
        for index in range(frames):
            order = ((old, "before"), (new, "after"))
            if index % 2:
                order = order[::-1]
            for scene, variant in order:
                samples[variant].append(benchmark.timed(lambda: frame(scene, variant)))
        result[label] = {variant: benchmark.summarize(values) for variant, values in samples.items()}
        result[label]["pixels_equal"] = (
            hashlib.sha256(pygame.image.tobytes(canvases["before"], "RGB")).digest()
            == hashlib.sha256(pygame.image.tobytes(canvases["after"], "RGB")).digest())
    pygame.quit()
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-ref", default="HEAD")
    parser.add_argument("--frames", type=int, default=600)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.frames < 1:
        parser.error("--frames must be positive")
    report = json.dumps(compare(args.baseline_ref, args.frames), indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(report + "\n", encoding="utf-8")
    print(report)
