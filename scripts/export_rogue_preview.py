"""Export the baked rogue frames as a compact animated review (Pillow optional)."""
from pathlib import Path
import json
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets" / "characters"
LABELS = {"idle": "Reposo", "attack": "Ataque", "guard": "Esquiva", "hurt": "Recibir dano", "cast": "Habilidad", "death": "Derrota"}


def export():
    meta = json.loads((ASSETS / "rogue_v2_sheet.json").read_text())
    sheet = Image.open(ASSETS / "rogue_v2_sheet_96.png").convert("RGBA")
    frames, durations = [], []
    for name, animation in meta["animations"].items():
        for index, duration in enumerate(animation["durations_ms"]):
            canvas = Image.new("RGB", (384, 248), (18, 20, 34))
            ImageDraw.Draw(canvas).text((16, 12), "La Picara - " + LABELS[name], fill=(229, 216, 246))
            x, y = index * 96, animation["row"] * 96
            frame = sheet.crop((x, y, x + 96, y + 96))
            canvas.paste(frame, (12, 134), frame)
            large = frame.resize((192, 192), Image.Resampling.NEAREST)
            canvas.paste(large, (160, 38), large)
            frames.append(canvas)
            durations.append(duration)
        durations[-1] += 350
    # GIF stores centiseconds; distribute rounding instead of shortening every frame.
    elapsed = 0
    rounded = []
    for duration in durations:
        rounded.append(round((elapsed + duration) / 10) * 10 - round(elapsed / 10) * 10)
        elapsed += duration
    durations = rounded
    palette = frames[0].quantize(colors=128)
    quantized = [frame.quantize(palette=palette, dither=Image.Dither.NONE) for frame in frames]
    quantized[0].save(ROOT / "output" / "rogue-v2-preview.gif", save_all=True,
                      append_images=quantized[1:], duration=durations, loop=0, disposal=2)


if __name__ == "__main__":
    export()

