# La Guerrera: reposo

Asset: `redhead_idle.png`, generado con la herramienta integrada ImageGen (modo built-in).
PNG con alfa, 1774 × 887 píxeles; ocho celdas en cuatro columnas y dos filas.

El cargador corta la cuadrícula, alinea las botas y conserva una escala común.
Se reproduce 0–7–1 en ida y vuelta, con 180 ms por paso: ciclo de 2,52 s.
El render añade hasta dos píxeles de respiración en el torso a resolución lógica
96 × 96, dejando las botas apoyadas. Se escala sin suavizado y se almacena en caché.
El tiempo procede de `update(dt)`, tanto en combate como en selección.

## Prompt utilizado

Create a production-ready 2D pixel art idle animation SPRITE SHEET for a dungeon fantasy game. TRUE TRANSPARENT PNG background, alpha zero outside the sprites, NOT checkerboard painted into image. A simple original adult female redheaded dungeon adventurer: vivid copper-red ponytail, a few swept bangs, emerald short cape, modest dark leather adventuring tunic with a small bronze shoulder guard, belt pouch, dark boots, short sword held casually downward in right hand. Friendly determined face, 3/4 side view facing RIGHT (she stands on left of battle facing enemies to right). Strong readable silhouette, restrained 16-24 color palette, crisp pixel clusters, classic 2D fantasy game sprite style, no text, no UI, no ground, no cast shadow, no background, no detached particles. EXACT layout: eight equal square cells in a 4-column x 2-row regular grid; all frames identical scale and character alignment, generous transparent margins in each cell, boots fixed at same baseline. Frame reading order left to right then next row. Subtle seamless idle breathing sequence 8 frames: neutral, inhale a little, inhale more, gentle peak, gentle peak, exhale a little, exhale more, neutral nearly identical to frame1. Motion only 1-2 logical pixel shifts in shoulders/hair/cape; stationary feet, no walking, no bouncing, no big sword movement, no pose or costume changes. Each cell contains exactly ONE complete full-body same woman. Final canvas 1024x512 pixels, each cell256x256, character occupying about 160x205 pixels within each cell. This is one sprite sheet asset to slice for animation, not a poster.
