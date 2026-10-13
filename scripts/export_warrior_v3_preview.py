"""Compose a warrior review with pygame and encode its GIF with optional Pillow.

When Pillow belongs to another Python environment, pass --encoder-python PATH.
The encoder only packages already rendered review frames; it does not edit art.
"""
from pathlib import Path
import argparse
import importlib.util
import json
import os
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets" / "characters"
LABELS = {"idle": "Reposo", "attack": "Ataque con espada", "guard": "Defensa", "hurt": "Recibir daño", "cast": "Habilidad", "death": "Derrota"}


def export(encoder_python=None):
    os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
    import pygame
    if encoder_python is None and importlib.util.find_spec("PIL") is None:
        raise RuntimeError("Pillow is required only for GIF encoding; use --encoder-python with a Python environment that provides it")
    meta = json.loads((ASSETS / "warrior_v3_sheet.json").read_text(encoding="utf-8"))
    sheets = {cell: pygame.image.load(str(ASSETS / filename)) for cell, filename in meta["sheets"].items()}
    pygame.font.init()
    font, small_font = pygame.font.Font(None, 22), pygame.font.Font(None, 17)
    staging = ROOT / "tmp" / "warrior-v3-preview-frames"
    staging.mkdir(parents=True, exist_ok=True)
    records, samples = [], []
    for name, animation in meta["animations"].items():
        for index, duration in enumerate(animation["durations_ms"]):
            canvas = pygame.Surface((408, 264))
            canvas.fill((16, 23, 36))
            canvas.blit(font.render("La Guerrera · " + LABELS[name], True, (225, 236, 251)), (16, 14))
            pygame.draw.line(canvas, (79, 107, 139), (12, 234), (396, 234))
            for cell, position in ((96, (16, 138)), (192, (172, 42))):
                frame = sheets[str(cell)].subsurface((index * cell, animation["row"] * cell, cell, cell))
                canvas.blit(frame, position)
            canvas.blit(small_font.render("96 px", True, (154, 179, 206)), (42, 243))
            canvas.blit(small_font.render("192 px · combate", True, (154, 179, 206)), (220, 243))
            if len(records) % 12 == 0:
                samples.append(canvas.copy())
            filename = f"{name}_{index:02}.png"
            pygame.image.save(canvas, str(staging / filename))
            records.append({"file": filename, "duration": duration})
        records[-1]["duration"] += 700 if name == "death" else 350
    palette = pygame.Surface((408, 264 * len(samples)))
    for row, canvas in enumerate(samples):
        palette.blit(canvas, (0, 264 * row))
    pygame.image.save(palette, str(staging / "palette.png"))
    output = ROOT / "output" / "warrior-v3-preview.gif"
    output.parent.mkdir(exist_ok=True)
    manifest = staging / "manifest.json"
    manifest.write_text(json.dumps({"output": str(output), "frames": records}), encoding="utf-8")
    if encoder_python:
        subprocess.run([str(encoder_python), str(Path(__file__).resolve()), "--encode-manifest", str(manifest)], check=True)
    else:
        encode(manifest)


def encode(manifest):
    from PIL import Image
    manifest = Path(manifest)
    data = json.loads(manifest.read_text(encoding="utf-8"))
    with Image.open(manifest.parent / "palette.png") as source:
        palette = source.convert("RGB").quantize(colors=256)
    frames, durations, elapsed = [], [], 0
    for record in data["frames"]:
        with Image.open(manifest.parent / record["file"]) as source:
            frames.append(source.convert("RGB").quantize(palette=palette, dither=Image.Dither.NONE))
        duration = record["duration"]
        # GIF stores centiseconds; accumulated rounding preserves clip timing.
        durations.append(round((elapsed + duration) / 10) * 10 - round(elapsed / 10) * 10)
        elapsed += duration
    frames[0].save(data["output"], save_all=True, append_images=frames[1:], duration=durations, loop=0, disposal=2)
    print(f"Exported warrior-v3-preview.gif: {len(frames)} frames, {sum(durations)} ms")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--encoder-python", type=Path, help="Python executable with optional Pillow installed")
    parser.add_argument("--encode-manifest", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.encode_manifest:
        encode(args.encode_manifest)
    else:
        export(args.encoder_python)
