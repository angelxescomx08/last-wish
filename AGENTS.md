# Codex agent instructions

Read `CLAUDE.md` for architecture, language conventions and commands.
Read `docs/visual-design.md` before changing assets, animation or UI.

Last Wish uses **pixel art, dungeon fantasy and clear anime character design**.
The warrior is red-haired with expressive emerald eyes, a long copper/crimson
ponytail, refined silver/gold armour and dark teal fabric. The user rejected the
first polygon-drawn face and stiff animation. Preserve the new source artwork in
`assets/characters/warrior-source-v2.png`; do not revert to the archived v1 script.

The current idle uses the articulated rig in `scripts/warrior_rig.py`, baked by
`scripts/generate_warrior_idle.py`: 96 frames, 256 × 256 native cells, 8 × 12 sheet,
30 FPS, 3.2 s. Keep shoulder/elbow hierarchy, a rigid forearm+weapon attachment,
unchanged facial artwork, fixed soles and delayed hair/cape rotation. The backing
image supplies only hidden patches. Never restore the previous global image warp.

Regenerate layers, PNGs and HTML after changes. The optional Pillow script
`scripts/export_warrior_preview.py` creates GIF reviews. Inspect at 96/192 px,
check joints and the loop, and run the full tests. The v2 design is approved;
perceived quality of a new animation still needs user review. Read
`docs/visual-design.md` for constraints, research, provenance and reproduction.
