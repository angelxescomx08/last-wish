# Mage v2 pixel-art source

Built-in image generation (not the CLI/API fallback), 2026-10-11.
Reference: `assets/characters/rogue-rig-base.png`, style and pixel density only.
Source: `assets/characters/mage-source-v2.png`.
The earlier high-detail illustration was rejected by the user and is not used.

## Final generation prompt

Create ONE NEW MALE MAGE GAME SPRITE matching the ACTUAL LOW-RES PIXEL ART of the attached rogue sprite. Reference image is STYLE AND PIXEL DENSITY ONLY, not an edit target. Essential: match that tiny readable 16-bit game sprite with clearly countable square pixel clusters and simplified shading. This must NOT be an illustration, HD portrait, detailed painting, soft anime drawing, smooth vector art, or high-resolution art reduced later. Draw on a coarse approximately 96 by 96 logical pixel grid, displayed with a uniform large integer nearest-neighbor enlargement. Use 3-4 shades per material, approximately 32-40 colors total, hard square pixel staircases everywhere, chunky 1 logical pixel colored outlines, no antialiasing, no texture speckle. The male mage is a compact stylized adult anime adventurer, matching the rogue's roughly 4-head-tall proportions, large readable silver-haired head and cyan eyes, elegant navy-blue split coat with short flowing cape, restrained gold trim, dark trousers and brown boots. One small sapphire clasp. He faces screen-right three-quarter with feet apart. His screen-left arm is bent, hand holds a short upright staff with a small blue crystal; his screen-right free arm rests diagonally down and outward with a visible hand for casting. Keep both arms separate from torso and staff separate from body, thin straight staff kept within the figure's height. Full body and staff in a single neutral standing pose, transparent background with true alpha. No magic particles, no glow haze, no ground, no text, no grid, no extra poses. Keep all pixels within central 70 percent of square canvas with generous empty margins. The final asset must visibly belong next to the attached rogue sprite in the SAME pixel art game. Favor simple beautiful deliberate PIXEL CLUSTERS over excessive detail.

## Import and animation

`mage_rig.prepare_base()` crops using alpha >= 128, samples nearest-neighbour
at 78 px figure height inside a 96 px cell, and normalizes alpha to 0 or 255.
No filtering or image deformation is used. This import keeps the source file
unchanged. Joint layers use original pixels plus small source-derived overlap
caps. The 192 px frames are rasterized directly from those layers, preserving
hard pixel edges while giving slow movement half-native-pixel precision.

Run `scripts/generate_mage_v2_sprites.py` with the project's Python to regenerate
layers, both sheets, active metadata, individual frames, contact sheet and HTML.
The preview composer uses the project's pygame environment. Pillow is only
needed to encode the final GIF; if it lives in a separate environment, pass
that executable with `--encoder-python`:

```powershell
.venv/Scripts/python.exe scripts/generate_mage_v2_sprites.py
.venv/Scripts/python.exe scripts/export_mage_preview.py --encoder-python <python-with-Pillow>
```

Omit `--encoder-python` if the project's Python already includes Pillow.
The old mage and generator are retained in `assets/characters/mage_legacy/`.
