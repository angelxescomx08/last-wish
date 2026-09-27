# La Guerrera — sprites

Diseño aprobado: `warrior-source-v2.png`. Convertido a pixel art nativo en
`warrior_base.png` (135 × 181) con `scripts/make_warrior_base.py` (una sola vez).

Animación: `python scripts/generate_warrior_sprites.py` genera
- `warrior_sheet.png`: celdas de 192 px (combate, 1:1),
- `warrior_sheet_96.png`: celdas de 96 px (selección),
- `warrior_sheet.json`: tiempos por cuadro.

El dibujo nunca se corta, gira ni reescala: en reposo se mueven filas enteras de
píxeles (respiración, coleta y capa, parpadeo); en ataque, guardia y golpe se
mueve la figura completa y se añaden efectos (tajo, chispas, escudo, destello).

`warrior_pixel_art.py` y el resto de archivos antiguos ya no se usan.
