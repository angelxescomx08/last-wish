# Audio original de Last Wish

Los efectos y la música se sintetizan con código del proyecto; no usan grabaciones ni samples de terceros.

Para reconstruir todos los WAV, desde la raíz del proyecto:

```sh
python scripts/generate_audio.py
```

- `last_wish_theme.wav`: «Embers of the Last Wish», instrumental estéreo de 16 compases, re menor, 84 BPM y 45,714 segundos. Las notas y reverberaciones se prolongan al inicio del siguiente ciclo; se reproduce continuamente con `loops=-1`.
- `music_preview.wav`: muestra de 16 segundos con entrada y salida suaves; no se utiliza para el bucle del juego.
- Cada efecto tiene tres variantes (`_0`, `_1`, `_2`) que se alternan al reproducirse.
- `preview.wav`: muestra de carta, ataque, bloqueo, derrota, fin de turno, daño, victoria, navegación, confirmación, cancelar, compra, abrir sobre, recompensa, error y recorrido, en ese orden.

La música y los efectos tienen controles independientes en Ajustes. Sus valores se guardan en `preferences.json`. La mezcla comparte un reproductor entre escenas, limita las voces simultáneas y evita repetir el mismo aviso demasiado rápido.
