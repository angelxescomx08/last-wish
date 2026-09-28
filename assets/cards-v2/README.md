# Last Wish — cartas y sobres, propuesta v2

Nueve PNG RGBA independientes, generados con la herramienta de imágenes integrada.
Los prompts están en `prompts.json`; dimensiones y transparencia, en `manifest.json`.

## Marcos de cartas

- `frames/card_common.png`: común; hierro, cuero y remaches.
- `frames/card_uncommon.png`: poco común; plata, verde y esmeraldas.
- `frames/card_rare.png`: rara; plata, azul y zafiros angulares.
- `frames/card_epic.png`: épica; amatistas, plata oscura y remates góticos.
- `frames/card_legendary.png`: legendaria; oro, ámbar, coronas y alas.

Cada marco incluye placa vacía para nombre, hueco superior izquierdo para coste,
ventana transparente para ilustración, panel oscuro para efectos y dos espacios
inferiores para estadísticas. No llevan texto ni ilustración de una carta concreta.
La rareza cambia color, materiales y ornamentación, no solamente una gema.

## Sobres

- `packs/pack_acero.png`: acero y rojo, espadas cruzadas.
- `packs/pack_escudo.png`: plata y verde, escudo.
- `packs/pack_magia.png`: plata y azul, cristal arcano.
- `packs/pack_epico.png`: oro y violeta, corona y alas.

Todos tienen fondo exterior transparente. Los sobres son los cuatro temas que
existen en el proyecto, no una nueva clasificación de rareza de paquetes.

## Uso

Son assets de diseño separados para revisión. La integración requiere adaptar las
zonas de texto e ilustración de `card_widget.py`, que actualmente compone varias
piezas distintas. Los marcos no sustituyen automáticamente esas piezas. Guardar
siempre el canal alfa; el RGB de píxeles transparentes puede contener colores que
solo se verán si se elimina la transparencia. Usar escalado nearest-neighbour para
mantener bordes definidos. Los archivos originales tienen ligeras diferencias de
márgenes y requieren anclajes de diseño al incorporarlos al renderer.
