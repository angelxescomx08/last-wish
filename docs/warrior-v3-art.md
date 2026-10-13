# Warrior v3 pixel art

Built-in image generation (not the CLI/API fallback), 2026-10-12.
Style references: `rogue-rig-base.png` and `mage-rig-base.png`.
Final source: `assets/characters/warrior-source-v3.png`.
The original `warrior-source-v2.png` and `scripts/warrior_rig.py` remain unchanged.

## Final generation prompt

Create ONE NEW FEMALE WARRIOR GAME SPRITE for Last Wish, matching the ACTUAL LOW-RES PIXEL ART of the two attached rogue and mage sprites. Input images are STYLE, PROPORTION AND PIXEL DENSITY references only. Essential: this is a tiny readable 16-bit game sprite with deliberately countable square pixel clusters, NOT an HD illustration, NOT painted art reduced later, NO soft antialiasing. Draw on an approximately 96 by 96 logical pixel grid and enlarge uniformly with nearest neighbor. Roughly 4-head-tall stylized adult anime woman, large readable emerald-green eyes, vivid copper/crimson RED hair with bangs and long high ponytail flowing screen-left, attractive confident face, small gold circlet. Elegant silver plate armor with simple gold edging, fitted dark charcoal underarmor, a short split crimson tabard, dark teal cape swept behind to screen-left, brown armored boots. Gold details kept simple and readable, not filigree. She faces SCREEN RIGHT three-quarter, balanced ready stance with both boots apart and clearly visible knees. Her front sword arm hangs slightly away from torso with a naturally bent elbow, hand gripping a straight silver single-handed sword with gold guard, blade extending DIAGONALLY DOWN toward screen-right, tip clear of legs and fully visible. Sword approximately one third of character height, simple thin blade with a clean two-tone edge. Other arm rests by her far side; NO shield. Both arms need clear separation from torso for animation. Hands and weapon anatomically connected. Single neutral standing pose, full body and sword entirely visible, true transparent background, generous margins for animation. 3-4 shades per material, restrained palette, hard dark-colored 1-pixel outlines, clean square-pixel staircases, upper-left lighting, NO gradients, NO glow, NO particles, NO floor, NO shadows, NO typography, NO extra poses, NO grid. Keep the entire character inside central 75% of canvas. The final sprite must belong in the SAME pixel art game as the attached rogue and mage; readable simplified pixel clusters take priority over ornamental detail.

## Reproduction

The baker imports the source with nearest sampling at 78 px figure height inside
96 px cells and normalizes alpha to 0/255. `warrior_pixel_layers.py` separates
material boundaries and uses original-source pixels for hidden joint caps.
`warrior_pixel_rig.py` animates rigid shoulder/elbow/weapon chains and two-bone
legs. It reuses the monotone cubic curve helper without changing older rigs.

```powershell
.venv/Scripts/python.exe scripts/generate_warrior_v3_sprites.py
.venv/Scripts/python.exe scripts/export_warrior_v3_preview.py --encoder-python <python-with-Pillow>
```

Pygame composes the review; Pillow only encodes the GIF. Omit the encoder flag
when the project environment already includes Pillow. Baking regenerates the
base, layers, native 96/192 sheets, frame PNGs, metadata, contact sheet and HTML.
All 300 frames use hard nearest-neighbour pixels; the 192 px combat sheet is
rasterized directly so joints move at half-native-pixel precision without blur.

Review at `output/warrior-v3-preview.html` or `output/warrior-v3-preview.gif`.
The first version is kept in `assets/characters/warrior_before_v3/` with its
metadata, PNGs and generator. Restore only its metadata to `warrior_sheet.json`
to select the preserved original root PNGs again. Do not overwrite v2 artwork.

The design follows the game's red-haired warrior identity and the rogue/mage
pixel density. Technical checks verify connected joints, complete sword range,
planted soles, exact rest/recovery, safe margins and hit timing. Perceived
animation quality remains subject to user review.
