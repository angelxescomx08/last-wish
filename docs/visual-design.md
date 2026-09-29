# Visual design — Last Wish

## Required direction for Codex and Claude

**Pixel-art dungeon fantasy.** Characters follow the approved warrior design
(`warrior-source-v2.png`, detailed pixel art). Faces and bodies drawn by code
were rejected; see v7 below. Target mood for scenes: strong warm/cold contrast
(cold night and rain vs. firelight and glowing windows), crisp and looping.
Environments use dark stone, blue/purple shadows and warm torchlight. Preserve
crisp pixels, coloured outlines and consistent upper-left lighting. UI is Spanish;
code identifiers and comments are English.

## Dungeon environment pack (combat backdrop)

User liked the cold/warm dungeon test and its torch; asked for reusable assets,
rain made of particles, and low CPU use.

- `scripts/generate_dungeon_assets.py` (stdlib) writes `assets/dungeon/`:
  `tiles.png` (4 seamless 32×24 wall blocks: plain, cracked, mossy, chipped;
  4 32×16 floor flagstones; a 32×6 ledge), `props.png` (torch bracket, banner,
  chain), `flame.png` (6 frames, 14×22), `glow.png` (3 flicker levels),
  `room_combat.png` and `dungeon.json` (anchors: torches, window interior,
  sill, moonbeam, drips; particle palettes).
- **Baked lighting**: moonlight, torchlight, vignette and colour banding with
  ordered-dither seams are computed offline per room. Palette: cold blue ramp
  vs warm ember ramp; moss has its own cold/warm ramps.
- **Runtime** (`src/presentation/ui/dungeon_backdrop.py`): one full-screen blit
  of the pre-scaled room; per torch a flame `SpriteAnimation` and a 3-level
  additive glow chosen by layered sines; particles from
  `src/presentation/fx/particles.py`: embers, window rain with slanted trails
  (clipped to the window) that splash on the sill, ceiling drips that splash on
  the floor, dust in the moonbeam. Python update ≈ 0.1 ms per frame, ~100
  particles; no per-frame scaling or per-pixel work.
- GPU rendering (pygame `_sdl2` renderer) was not needed: the frame cost is
  dominated by one blit. Revisit only if profiling says so.
- New rooms: add a layout to `ROOMS`, bake, and pass its anchors via JSON.
- `scripts/generate_dungeon_background.py` and `assets/backgrounds/` were the first
  baked-GIF test (rain drawn into frames); they are superseded and unused.

## Cards and packs (cards-v2)

Assets supplied by the user in `assets/cards-v2/` (see its README): five rarity
frames (common iron/leather, uncommon silver/emerald, rare silver/sapphire, epic
amethyst/gothic, legendary gold/amber/wings) and four closed packs (acero,
escudo, magia, epico). Frames are painted at ~1064×1478 and reduced with
smoothscale to 140×194 once per size. Zones measured into `layout.json`.
Illustrations are provisional Dungeon Crawl icons by type until real art is
placed in `assets/cards-v2/art/<card id>.png` (any size, cropped to cover the
window). Effect text is generated from card data with effective values.

## Pack opening animation

`PackOpeningScene` animates the existing art only — no new images: the closed
pack painting (`pack_art`) and the crystal card back (`card_back`). Code adds
light and particles (`fx/bursts.py` for one-shot bursts, `fx/particles.py`
for background motes). Each pack theme has a colour set (`THEMES`: acero red,
escudo green, magia blue, epico purple with gold accents); each rarity has a
palette (`RARITY_PALETTE`). Beats: drop-in → float with pulsing glow and hint →
click → charge (shake grows, sparks implode, pack whitens) → tear (white flash,
screen shake, the top strip is cut along a jagged line with a light seam and
spins away, the body falls and fades, explosion + rotating light rays) → deal
(cards arc out of the pack, scaling up and straightening) → reveal (flip by
horizontal squash, rare+ wait with a growing halo and inward sparks; burst size
grows with rarity, legendary adds gold confetti, flash and shake) → pick (rare+
halos and rising sparkles) → outro (chosen card rises to the centre). Any click
or Space/Enter skips to the pick screen. Tune timings with the constants at the
top of the module.

## Playing cards — Slay the Spire style hand and targeting arrow

User found card play "raro" and asked for the Slay the Spire arrow. Behaviour
(`src/presentation/ui/card_play.py`, pure state machine; `CombatScene` feeds it):

- **Hand**: gentle fan (±2.5°/card, max 10°, slight arc). Hovering a card
  straightens it, grows it ×1.3 until fully visible and pushes neighbours aside;
  its tooltip sits beside it. Cards tween (exponential ease, frame-rate
  independent), fly in from the draw pile and fly to the discard pile when played.
- **Drag**: press a card to pick it up. Cards for the hero or for all enemies
  are played by releasing them above the hand line (hero or all enemies get a
  reticle while it would play). Cards for one enemy park at the aiming spot once
  dragged out of the hand and a **chevron arrow** runs to the cursor; release on
  an enemy to play it, anywhere else (or back into the hand) to put it back.
- **Click**: a quick click keeps the card held (aimed cards show the arrow at
  once); the next click on an enemy / above the hand plays it; empty space
  drops it. Right click or ESC always cancels. Unaffordable cards cannot be
  picked ("Maná insuficiente").
- **Keyboard**: 1–9 pick a card (aimed at the first living enemy), ←/→/Tab change
  target, Enter/Space play, E ends the turn.
- **Target kind** comes from card data (`application.play_card.target_kind`):
  damage or `needs_target` → one enemy; `CardEffect.hits_all_enemies` → all
  enemies; otherwise the hero.
- **Arrow** (`src/presentation/ui/targeting.py`): quadratic curve that leaves
  the card upward and bends to the target; chevrons every 26 px growing toward
  a big arrowhead, flowing at 70 px/s. Pale when pointing at nothing, red over a
  valid target; yellow pulsing corner reticle on the target (blue on the hero).
  Pixel-art sprites drawn at half resolution, doubled nearest-neighbour and
  pre-rotated in 5° buckets (cached) — ~20 blits per frame.
- Preview: `output/card-targeting.gif`, `output/card-targeting-preview.png`.

## Rogue ("La Pícara") — approved art, same pipeline

- Source `assets/characters/rogue-source.png`; converted by
  `scripts/make_hero_base.py rogue` (3 halo-peel passes up to brightness 0.74
  because the daggers carry a bright glow; polished steel counted as an accent so
  blades stay crisp). The domain name changed from "El Pícaro" to "La Pícara";
  both names map to the rogue sheets.
- `scripts/generate_rogue_sprites.py`: idle 16 × 100 ms (breath, head lag,
  coat-tail sway, a glint down each dagger); attack = anticipation, shadow dash
  with dithered purple after-images, crossed double slash, sparks; guard = smoky
  side-step with after-image and glinting daggers; hurt = shared flash/recoil.

## Mage — approved art, same pipeline as the warrior

- Source: `assets/characters/mage-source.png` (user-supplied, dark vignette with
  a soft glow instead of transparency).
- `scripts/make_hero_base.py mage` (one-time, Pillow + numpy; `make_mage_base.py` is a wrapper): estimates the smooth
  backdrop, keeps pixels that differ from it or are clearly coloured, protects
  the thin dark staff shaft, closes 15 px gaps so boots stay solid, floods the
  outside; then reduces ×8 to `mage_base.png` (128×192) with a light unsharp
  mask, block averages snapped to a 64-colour palette (12 colours reserved for
  glowing accents: eyes, crystal, gems) and peels grey halo pixels.
  The mage source has a finer pixel grid than the warrior's, so the reduced art
  is a little softer; a cleaner source at ~4 px per art pixel would help.
- `scripts/generate_mage_sprites.py`: idle 16 × 100 ms (breath, head lag, robe
  hem sway, crystal pulse, orbiting motes, blink); attack = crystal flare +
  arcane bolt + burst; guard = rune circle; hurt = shared flash/recoil.
  Landmarks (`HEAD_BOTTOM`, `CHEST_BOTTOM`, `CRYSTAL`, `EYES`) at the top.

## Warrior v7 — approved art, animated without deformation (current runtime asset)

History: v2 rotated layers of the approved illustration (looked good, not
fluid); v3–v6 were characters drawn by code or by hand in text grids (fluid,
but faces and bodies looked wrong). Conclusion: **do not let code draw new
characters.** Character art must come from a real drawing (the approved
illustration, an artist, a CC0 pack or a pixel-art tool); code animates it and
adds effects, which it does well.

- `scripts/make_warrior_base.py` (one-time, Pillow + numpy) reduces
  `warrior-source-v2.png` — generated as pixel art on a ~4 px grid — by 8 into
  `assets/characters/warrior_base.png` (135 × 181): 64-colour palette, each 8×8
  block takes its dominant colour, dark outlines win at 30 %.
- `scripts/generate_warrior_sprites.py` (stdlib) animates that drawing without
  cutting it into limbs or rotating/resampling anything:
  - idle: rows above the chest line rise one pixel on the in-breath and the
    head follows a beat later; ponytail and cape sway with per-row offsets that
    grow away from where they attach; one blink per loop;
  - attack / guard / hurt: the whole figure moves as one piece (anticipation,
    lunge, recoil) and pixel effects carry the energy: slash crescent and
    sparks, hexagonal guard ward with a gleam on the blade, white hit flash with
    red tint and sparks.
- Output: `warrior_sheet.png` (192 px cells, shown 1:1 in combat),
  `warrior_sheet_96.png` (96 px cells for selection; each frame reduced by 2
  with dominant-pixel blocks) and `warrior_sheet.json`.

| Animation | Frames | Duration | Loop | Trigger in combat |
|---|---|---|---|---|
| `idle` | 16 | 1.6 s | yes | default |
| `attack` | 8 | 0.59 s | no | playing a card with damage |
| `guard` | 7 | 0.55 s | no | gaining block |
| `hurt` | 5 | 0.48 s | no | taking damage |

Every action ends on idle frame 0. Region landmarks (`HEAD_BOTTOM`,
`CHEST_BOTTOM`, sway colour rules, eye and blade coordinates) live at the top of
the generator; re-check them if `warrior_base.png` changes.
`scripts/warrior_pixel_art.py` belongs to the abandoned v5/v6 attempt and is unused.

**Future characters/poses:** obtain a drawing first (same pixel-art style as
`warrior_base.png`), then reuse this generator's techniques. Environments and
effects (rain, fire, smoke, flickering light, warm/cold contrast) can be made
in code.

## Warrior v2 — previous direction (superseded at runtime)

Adult red-haired anime swordswoman, facing right in three-quarter view. Long
crimson/copper ponytail and face-framing bangs, large emerald eyes, small nose and
mouth, refined silver armour with gold trim, charcoal fitted clothing, dark teal
cape and skirt panels, brown leather belt and tall boots. Her sword points down
across the front, in the near hand. Both feet stay planted in a relaxed guard.
The face is delicate and recognizably anime, with stable features throughout idle.

`assets/characters/warrior-source-v2.png` is the immutable source artwork generated
with the built-in image-generation tool. `warrior-concept-v2.png` is its earlier
concept, not a runtime asset. Do not replace the source with the old procedural
polygon drawing. `scripts/warrior_idle_v1_archive.py` preserves the rejected old
implementation for reference only; do not run it against current assets.

## Animation implementation — articulated revision

The approved face and costume remain in `warrior-source-v2.png`. A built-in AI
image edit created `warrior-rig-backing.png`, used only to fill small regions behind
removed arms, hair and sword. Its head and boots never replace the approved art.
The edit requested identical placement and design, removing the ponytail and both
arms/sword and reconstructing hidden cape, tunic, armour and leg material.

`scripts/warrior_rig.py` owns the joint hierarchy, silhouette masks, layer order
and periodic Catmull-Rom pose curves. Nine exported layers live in
`assets/characters/warrior_rig/`: legs, torso, head, upper_arm, forearm, weapon,
far_arm, hair and cape. Torso rotates around the waist; head and shoulders inherit
its transform; forearm rotates around the transformed elbow. The weapon uses
exactly the forearm transform, so it cannot slide or bend independently.
Hair and cape inherit their attachment transforms plus delayed angular motion.
Feet are a stationary layer. Rotation sampling uses nearest pixels, never blur.

`scripts/generate_warrior_idle.py` assembles **96 frames**, **30 FPS**, **3.2 s**.
Cells are **256 × 256**, anchor **(128,246)**; sheet is **8 × 12**, **2048 × 3072**.
Runtime only slices and scales; it does not deform artwork. The cycle is forward,
without ping-pong or duplicated endpoint. Short pixel-grid holds at a turnaround
are acceptable: forcing every frame to differ can introduce artificial shimmer.
The tests check attachment, blade rigidity, periodic joint position/velocity,
stationary boots, timing, no long frozen segment and scene rendering.

This replaces the old global sinusoidal displacement. It is a local articulated
animation of AI-assisted artwork, not an AI-generated video or a Spine/Live2D file.
Only idle is implemented; no blink has been added to the approved face.

## Files and reproduction

- `assets/characters/redhead_idle.png`: runtime sheet.
- `assets/characters/warrior_idle/idle_00.png` … `idle_95.png`: individual frames.
- `assets/characters/warrior_idle/poses.json`: generated metadata, not editable input.
- `output/hero-idle-preview.html`: play/pause, frame stepping, speed and size controls.
- `output/hero-frames.png`: full contact sheet.
- `output/warrior-v2-preview.png`: enlarged still of the new design.

```powershell
.venv/Scripts/python.exe scripts/generate_warrior_idle.py
.venv/Scripts/python.exe -m pytest tests/ -q -p no:cacheprovider
```

Review the face at 96 px selection and 192 px combat, all transitions and the loop
seam. Check stable soles, connected shoulders/waist, straight blade, fixed grip,
no flickering features or aura, and restrained breathing. The automated tests
check timing, stable lower legs, transparent margins, the seam and scene playback;
they cannot establish that the user likes the design or perceived fluidity.
Only idle is in scope. Walking, attacking and hit reactions need their own art.

## Artwork provenance and final edit prompt

Built-in image generation was used, not the API/CLI fallback. The initial concept
requested an adult copper/red-haired anime dungeon swordswoman with emerald eyes,
silver/gold armour, teal cape, planted stance and a downward sword. The final edit
prompt applied to that concept was:

> Edit target: the provided red-haired anime swordswoman. Preserve her attractive anime face, red ponytail, green eyes, costume and pose. Convert into clean production PIXEL ART GAME SPRITE, as if drawn on a 192 by 256 pixel grid enlarged with nearest-neighbor. Simplify fine detail into deliberate sharp solid pixel clusters, limited ~40 colour palette. CRITICAL remove ALL glow, aura, haze, shadows and semi-transparent fringe outside the actual body, hair, cape and sword: entire background must be perfectly transparent, crisp solid silhouette with zero atmosphere. Keep full body centered including both boots and entire sword. Shorten sword moderately so tip ends at knee height, not ankle, preserve rigid straight blade and hand grip. Make face slightly larger and anime eyes clear, gentle determined expression with small natural mouth. No text, grid, additional characters or poses.

## Animation research — historical diagnosis before articulated revision

The user approved the v2 design and rejected the previous displacement animation.
The findings below motivated the articulated revision described above. They describe
the previous generator; art approval does not imply approval of the new motion.

### Diagnosis from source inspection

The generator samples a single image through sine/cosine displacement fields and
rounds source coordinates to integers. It has no joint hierarchy, new anatomical
poses, independent hand/weapon attachment or reconstructed surfaces behind moving
parts. Its 64 distinct frames prove changing pixels, not convincing acting or
smooth motion. At 256-to-192 nearest-neighbour scaling, quantized movement may
also become uneven. These are implementation findings and likely contributors;
they are not a substitute for watching the actual animation.

### Recommended next experiment

Use the existing source as identity reference and author an actual relaxed-guard
motion. Compare two routes without replacing the current asset until reviewed:

1. AI motion generation: use a specialist sprite animator with first/middle/final
   pose control or motion transfer from a short, stationary-camera reference.
   Use the approved pose at the start and end, with a restrained inhalation pose
   in the middle. Preserve face, armour, sword length, direction and planted feet.
   Generate the motion first; choose export FPS/frame count afterwards. Inspect
   identity drift, sliding grip, bent blade, limb proportions and loop velocity.
2. Local controlled rig: separate ponytail, cape, head, torso, upper arms,
   forearms, hand+sword, pelvis and legs. Use AI editing only to reconstruct hidden
   artwork or make compatible pose corrections. Animate a bone hierarchy with
   deliberate keys and easing; use delayed spring motion for hair/cape. Preserve
   rigid face/metal shapes and fixed soles. Sample the rig into PNGs for pygame.

The second route offers more direct control over the approved design; the first
is the more direct way to use AI to generate actual motion. Neither was implemented
by the previous sinusoidal image warp. Do not claim otherwise. Do not solve this
by merely raising the frame count or globally blending/blur-filtering frames.

Candidate motion brief (proposal, not a tested generation):
"Seamless relaxed guard idle of the exact reference swordswoman. Locked camera,
full body, fixed scale. Gentle ribcage breathing and small shoulder/elbow motion;
head settles slightly after the torso. Both soles planted, no stepping. Sword
rigidly attached to the same hand. Ponytail and cape follow with restrained inertia.
Preserve face, red hair, costume, anatomy and pixel-art style. No attack, camera
motion, effects, morphing or costume changes. Return smoothly to the starting pose."

### Primary sources consulted

- [Live2D: material separation](https://docs.live2d.com/en/cubism-editor-manual/divide-the-material/): prepare separate artwork parts for modelling.
- [Spine: graph editor](https://en.esotericsoftware.com/spine-graph): author timing/value curves rather than uniform pose changes.
- [Spine: physics constraints](https://en.esotericsoftware.com/spine-physics-constraints): secondary motion, inertia and damping for hair/clothing; warm up simulations before loop export.
- [Spine: weights](https://en.esotericsoftware.com/spine-weights): mesh topology and smoothing weights for controlled deformation.
- [Ludo: sprite generator](https://ludo.ai/docs/sprite-generator): first/middle/final keyframes and motion transfer. Its documentation explicitly says a seamless loop is not guaranteed.
- [Ludo: pixel-art workflow](https://ludo.ai/docs/sprite-generator/pixel-art-sprites): native-grid input, suitable animation model, nearest-neighbour export. Detailed art that lacks a strict grid may require a different model from Forge Pixel.

Ludo features are vendor-documented, not tested on this character. No Ludo account,
paid generation or video service was used. No callable specialist animation tool
was found in this session. The built-in image tool was used previously for still
artwork, not for AI video motion. The subsequent articulated revision implements the second route locally.


## Animated review

`output/warrior-idle.gif` plays the new animation directly. The optional
`output/warrior-idle-comparison.gif` shows the saved previous displacement cycle
beside the new rig at the same wall-clock phase. Both use one fixed GIF palette
and exactly 3200 ms per loop. Re-export with `scripts/export_warrior_preview.py`
using a Python environment with Pillow; Pillow is needed only for review GIFs,
not for sprite generation or the game. `output/warrior-idle-before.png` is the
comparison baseline, not a runtime asset. Inspect the animation at its real
96/192 px display sizes as well as enlarged. Automated checks cannot judge taste.
