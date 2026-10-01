# Code-drawn pixel-art enemies — the "Espectro" method

Approved by the user (2026-09-30) after the first enemy, **Espectro** (a hooded
wraith), was drawn and animated entirely by code. Use this method for new
enemies. **La Guerrera** was then redrawn the same way (section 10), because the
illustrated heroine did not match the pixel art; the other heroes still use the
illustration pipeline (`visual-design.md`) until the user asks otherwise.

Reference implementation:

| Piece | File |
|---|---|
| Drawing + animation (stdlib only) | `scripts/generate_enemy_sprites.py` |
| Contact-sheet preview (pygame) | `scripts/preview_enemy_sheet.py` |
| Output | `assets/enemies/<id>_sheet.png` + `<id>_sheet.json` |
| Loader (×2 nearest, cached) | `src/infrastructure/enemy_sprites.py` |
| Player + particles | `src/presentation/fx/enemy_animator.py` |
| Combat hookup | `CombatScene` (`_enemy_anims`, `_enemy_hit`, `_do_end_turn`) |
| Preview | `output/espectro-preview.gif` |

---

## 1. Core idea: one renderer, many poses

Never draw frames by hand and never paste or rotate pieces of an image. Write
**one** function `render(pose) -> pixels` that builds the whole creature from
shapes, and describe each frame as a `Pose`: a small frozen dataclass of
numbers.

```
Pose(dx, dy, lean, sx, sy,            # body offset, hood-vs-hem lean, squash/stretch
     phase, sway,                     # cloth / tendril wave
     hand_f, hand_b, claw,            # arm targets (relative to CX, TOP), finger spread
     eye, core,                       # glow levels
     chain, flash, dissolve,          # chain swing, white hit flash, death burn 0..1
     slash, slash_fade, rune, motes)  # baked effects
```

An animation is a list of `(pose, milliseconds)`. Because every frame comes
from the same renderer, proportions, palette and lighting can never drift
between frames, and in-betweens are just interpolated numbers. That is why the
motion looks fluid.

## 2. Canvas, scale and anchor

* Draw at **native pixel size** and show it at **×2** with nearest-neighbour. The
  baked room is 640×360 shown ×2, so one art pixel = 2 screen px, the same
  grain as the walls.
* Cell **128×104** native (256×208 on screen). Leave room on the side the
  creature attacks towards (the hero is on the left): body centre `CX = 80`.
* Body from `TOP = 18` (hood tip) to `BOTTOM = 92` (lowest tendril), ~75 px tall
  → ~150 screen px, about hero height.
* **Anchor** = ground point under the creature (`(80, 96)`), stored in the JSON.
  The scene places the anchor at `(enemy_rect.centerx, enemy_rect.bottom + 6)`,
  so the name label and HP bar never overlap the sprite.

## 3. Palette

Fixed ramps from dark to light, 4–7 steps each. Shadows are hue-shifted (cold
violet), never plain black. One **cold accent** (teal) contrasts the warm
torchlight of the room and is reserved for magic: eyes, soul flame, slash,
runes and particles.

```
OUTLINE (10,7,18)    coloured outline, not black
CLOAK   7 violet steps (14,11,26) … (150,134,192)
GHOST   4 dark teals for the fading hem
TEAL    4 glow steps (30,96,100) … (220,255,245)
BONE    4 steps for claws;  IRON 4 steps + RUST for chains
VOID    (5,4,10) inside the hood
```

## 4. Building a shape: axis, width profile, shading

Big masses (cloak, hood) are **swept along a body axis**:

1. `v` = 0 at the top to 1 at the bottom, from the pixel row (with squash and
   offset undone: `Body.local_v`).
2. **Centre line** `center(v)` = `CX + dx + lean·(1−v)^1.2 + wave`, where
   `wave = sway·sin(phase + 4.2v)·max(0, v−0.35)^1.3·2.2`. The top stays put and
   the bottom flows.
3. **Width profile** `half_width(v)`, piecewise: round dome (hood, `√k`),
   shoulders (`sin` ease), **narrow waist** (it separates torso from skirt; a
   straight bell looked like a sack), flaring skirt.
4. A pixel is inside if `|x − center(v)| ≤ half_width(v)·sx`.

**Shading** per pixel, with `u = (x − centre)/half_width` in −1..1:

```
light = 0.66 − 0.36·u − 0.44·v              # light from upper-left, darker low
      + 0.13·cos(8.5u + 2.5v + 0.3·sin(phase))   # vertical cloth folds
      − 0.14 if |u| > 0.86                   # turning edge
      + 0.18 if u < −0.78 and v < 0.62       # left rim light
index = round(light·(len(ramp)−1) + (bayer(x,y) − 0.5)·0.55)
```

* **Ordered (Bayer 4×4) dither, amplitude ≈ 0.55.** At 0.9 the whole cloak
  looked like a checkerboard.
* **Everything that depends on `phase` must be periodic** (`sin(phase)`,
  never `phase·k`), or the idle loop pops on the wrap. A test caught this:
  `test_idle_loop_closes`.

## 5. Making it read as a creature, not a blob (lessons)

| Problem seen | Fix that worked |
|---|---|
| Dithered hem fade looked like a net / mesh | Hem frays into **7 tapering strands** (`STRANDS`), each with its own length (`hash01`) and wobble; colour shifts cloak → ghost teal; only the last 30 % of each tip is dithered away |
| Arms were straight tubes (T-pose) | Arm = **quadratic Bézier** shoulder → elbow (bowed outward and down) → hand, radius tapering then widening into a **bell sleeve**; claws come out of the sleeve |
| Arm melted into the body | Draw the arm on its own canvas, paint a **dark rim** (`OUTLINE`) where it crosses the cloak, then copy it over |
| Lump at the shoulder joint | Draw the front arm **before** the shoulder capelet, so the capelet covers the joint |
| Body was one flat mass | Layers: shoulder **capelet** with a torn edge and a 1 px cast shadow; diagonal **chain** across the chest; **soul flame** on the chest |
| Face unreadable | Large round hood opening with an overhanging brow, a void that warms to teal at the bottom, **slanted** 3-px eyes (menacing), bright rim on the lit side |

**Draw order** (later wins):
`rune → back arm → cloak → front arm → capelet → hood/eyes → chest chain → soul
flame → outline (solid pixels only) → glows → slash/motes → hit flash → dissolve`.

* Only "solid" pixels create the outline; glow and faded pixels do not, or the
  hem gets speckled.
* Glows tint existing pixels and add faint alpha around them (cheap, baked).

## 6. Animation design

Every non-death action **ends on exactly idle frame 0** (same pixels), so
returning to idle never pops. `death` ends on an empty frame and holds it.

| Animation | Frames / time | Beats |
|---|---|---|
| `idle` (loop) | 12 × 110 ms | bob ±2 px (rounded to whole pixels), tendril wave, chain swing, soul flame pulsing at 2× speed, one dimmer eye frame |
| `attack` | 9, ≈0.77 s | anticipation (lean back, raise claw, eyes flare, 90 + 110 ms) → **fast** lunge left with stretch and slash arc (55 + 60 ms) → hold (80) → eased recovery (90, 90, 90) → idle 0 |
| `hurt` | 7, ≈0.52 s | white flash 0.82 (baked) + knock-back and squash → flash fading, drifting back → idle 0 |
| `cast` | 9, ≈0.79 s | arms rise, eyes and flame brighten, rune ellipse grows under the body, then everything settles → idle 0 |
| `death` | 14, ≈1.17 s | recoil + flash → stretch with arms up, eyes flare → **bottom-up dissolve**: pixels past a noisy front vanish, the front glows teal, baked motes rise → empty |

Timing rules: long anticipation, very short contact frames, eased recovery.
Use whole-pixel offsets (`round`) for small motion so pixels never shimmer.

Baked pixel effects (inside the sheet): slash arc (three parallel claw trails
sweeping through the left, bright head, fading tail via `slash_fade`), rune
ellipse with marching dashes, hit flash, dissolve, rising motes.

## 7. Runtime: sheet, animator, particles

* `load_enemy_sheet(id)` slices rows by the JSON, scales ×2 once, caches.
  Frame choice is by **elapsed time** (`HeroAnimation.frame_at`), never frame count.
* `EnemyAnimator` per enemy: `play(name, delay=)`, `update(dt)` (dt clamped to
  0.1 s), `draw(surface, anchor)`. It draws, in order: a soft floor shadow, a
  flattened **additive** teal floor glow that pulses (brighter while casting or
  attacking), the frame, then its own pooled `BurstParticles`.
* **Particles are timed cues**, not baked: ambient wisps and glows rising from
  the hem; claw sparks at `strike_time()` (when the claws land); ectoplasm and
  violet shreds on `hurt`; ring implosion to the chest and rune motes on
  `cast`; a burst, motes torn off the dissolving front and a rising soul on
  `death`.
* Scene hookup: HP loss → `hurt` (only the damage number, no red rectangle,
  because the flash is baked); kill → `death` (victory waits on
  `enemies_dying`); end of turn → `attack` for ATTACK intents and `cast`
  otherwise, staggered 0.14 s per enemy. The hero's `hurt` and hit number are
  **delayed to the first `strike_time()`**, so cause and effect line up.

## 8. Workflow and checks

1. Edit the generator → `python scripts/generate_enemy_sprites.py` (≈1 s).
2. Look at it **zoomed ×3–4 on a dark background**, row by row:
   `uv run scripts/preview_enemy_sheet.py wraith` → `output/<id>-sheet-preview.png`
   (every animation over the combat room at game scale and ×3 zoom).
3. Iterate on silhouette first, then shading, then details. Most of the quality
   came from 4–5 quick look-and-fix passes (section 5).
4. Check it in place in the combat room next to the hero (scale, label overlap).
5. Tests (contract): actions end on idle 0, idle loop closes and moves, figure
   fits the cell, dissolve 0 = intact and 1 = empty, death ends empty, flash
   brightens, attack lunges towards the hero, 100 random poses, sheet files
   match. Plus loader, animator and scene tests (see `CLAUDE.md`).

## 9. Adding a new enemy with this method

1. Copy the structure of `generate_enemy_sprites.py` (palette ramps, `Pose`,
   `Body`, shape functions, `render`, animation lists, `build`). Keep the
   animation names `idle / attack / hurt / cast / death` and the JSON layout
   (`cell_w`, `cell_h`, `anchor`, `scale`, `sheet`, `animations`).
2. Design the silhouette with a width profile and a centre line. Pick a body
   type that moves well from parameters (floating, slithering, hopping, cloth,
   tentacles). Give it 2–3 readable details (an accent colour, a prop, glowing
   eyes).
3. Write the poses following the timing table above.
4. Register the name: `ENEMY_SHEET_IDS["Nombre"] = "<id>"`. If the particle
   colours or cue offsets (`CHEST`, `EYES`, `BODY`, `CLAW`) differ, give the
   animator per-enemy values.
5. Add the enemy to `run_manager.generate_enemies` templates.
6. Generate, preview, test, then add a row to `CLAUDE.md` and to
   `docs/game_design.md`.

## 10. Humanoids (La Guerrera): one mass, exactly like the Espectro

Reference: `scripts/generate_warrior_code_sprites.py`, runtime `fx/hero_fx.py`,
preview `output/guerrera-preview.gif`.

**Two rejected attempts — do not repeat them:**

1. A joint rig with IK, capsule limbs, joint ellipses and outlines between
   parts: read as a doll made of pieces.
2. The same figure with each limb, the torso and the ponytail as separate
   smooth sweeps stacked on top of each other: no visible joints, but still
   assembled from pieces ("la estás haciendo por piezas").

**What the user approved is the Espectro technique applied literally:**

* The whole figure is **one silhouette scanned row by row** from the top of the
  head to the soles (`body_mass`). Each row has a centre line (hips + `lean`,
  squash `sx`/`sy`, `nod` for the head) and back/front extents from ONE height
  profile (`Body.extents`): head dome with the face profile (nose, chin),
  neck, shoulders, breastplate, belt, flaring tabard with a ragged hem.
* Everything is a **zone painted inside that mass**, decided by row (`ly`) and
  by the signed distance from the centre line (`u`): hair vs face (bangs line,
  circlet and gem), gorget, pauldron rim, plate with a specular streak and a
  centre ridge, belt and buckle, tabard with folds, panel slits, gold hem and
  emblem. Behind the body, in the same row scan, the **ponytail** hangs down
  the back and the **cape** fills out to its waving back edge (priority: body >
  boots > ponytail > cape).
* Below the tabard the same scan paints the **boots**: two spans per row,
  anchored to the floor (`ff`, `bf`), so idle boots never move.
* All zones use the same light (upper-left, `u`-based), folds and Bayer dither
  (`tone`). One coloured outline goes around the whole mass.
* **Only the sword and the sword arm are drawn on top**, with a dark rim where
  they cross the body — the Espectro's front sleeve rule. Face details (eye,
  brow, mouth, blush) are single pixels painted onto the mass.
* **Animation deforms the mass**, never limbs: offsets, lean, squash/stretch,
  head nod, hair/cape wind and phase, a stepped front boot for the lunge, and
  `kneel` (the mass sinks, the tabard pools on the floor and hides the boots)
  for death.

Test that pins it: `test_one_mass_without_seams` (the opaque pixels of a frame
form one connected region). Timing follows section 6; hero extras are `cast`
and `death` (held). The sheet JSON records `events.attack.strike_frame`; the
scene delays the enemy's reaction until `hero_strike_seconds()`, and `HeroFx`
fires its sparks at the same moment.
