# Diseño del juego — Last Wish

Lista viva de ideas y contenido del juego. Apunta aquí cartas, reliquias y palabras clave
nuevas; cuando algo ya esté en el juego, márcalo con ✅ y su nombre final.

Leyenda: ✅ implementado · ⏳ pendiente · 🟡 dorada = efectos x2

---

## Rarezas

Cartas y reliquias usan los mismos 5 tiers. La **suerte** hace más probables los tiers
altos y las versiones doradas (ver `src/domain/rarity.py`).

1. Común
2. Poco común
3. Rara
4. Épica
5. Legendaria

---

## Tipos de carta

| Tipo | Qué pasa al jugarla | Cartas en el pool | Estado |
|---|---|---|---|
| **Ataque** | Hace su efecto y va al descarte. | 31 | ✅ |
| **Habilidad** | Hace su efecto y va al descarte. | 31 | ✅ |
| **Poder** | Hace su efecto y se queda en juego el resto del combate; puede tener un efecto al inicio de cada turno. | 6 | ✅ |
| **Hechizo** | Por definir: ¿en qué se distingue de una Habilidad? | 0 | ⏳ idea |

Los mazos iniciales solo tienen Ataques y Habilidades.

**Poderes con efecto continuo ✅:** un Poder puede cambiar reglas para todo el combate
(Ritmo Letal, Danza de Sombras, Reflejos) o actuar al inicio de cada turno (Tormenta de
Acero). Concentración y Poder Oculto siguen siendo solo "roba X" al jugarse.

**Cartas que se juegan al robarlas ✅:** p. ej. la Daga Oculta (la crea Dagas Ocultas):
al robarla se juega sola gratis y desaparece del combate.

---

## Palabras clave

| Palabra | Regla | Clases | Estado |
|---|---|---|---|
| **Combo** | Efecto extra si ya jugaste otra carta este turno. | Solo Pícara | ✅ |
| **Singular** | Efecto extra si tu mazo inicial no contiene cartas repetidas. | Pícara por ahora (Abanico de Cuchillas, Tormenta de Acero) | ✅ |
| **Vacío** | Efecto extra si al jugar la carta te quedas con 0 de maná (ej.: te queda 1 de maná y juegas una carta de 1). Las cartas de coste 0 no lo activan. | Solo Mago (aún no hay cartas con Vacío) | ✅ |

La columna **Clases** indica qué clases tienen cartas con esa palabra: *Todas*, *Solo X*
o una lista (*Guerrera y Mago*). La regla en sí funciona igual para cualquier carta.

---

## Estados

| Estado | Efecto | Quién lo aplica | Estado |
|---|---|---|---|
| **Veneno** | Pierde X de vida al inicio de su turno; baja 1 por turno. | Cartas (enemigos) | ✅ |
| **Débil** | Inflige 25% menos de daño. | Guardia Evasiva (a enemigos, 1 turno); intención DEBUFF de enemigos (al héroe, 2 turnos) | ✅ |

---

## Cartas

### Neutrales
- ⏳ *

### Mago
- ⏳ *

### Guerrera
- ⏳ *

### Pícara

| Carta | Tipo | Coste | Efecto | Rareza | Estado |
|---|---|---|---|---|---|
| Estocada Oportuna | Ataque | 1 | Inflige 3 de daño. **Combo:** roba 1 carta. | Épica | ✅ |
| Preparación | Habilidad | 0 | La siguiente carta que juegues este turno cuesta 1 menos. | Épica | ✅ |
| Rebuscar | Habilidad | 2 | Roba un Poder, un Ataque y una Habilidad (de tu pila de robo). | Rara | ✅ |
| Pinchazo | Ataque | 0 | Inflige 3 de daño. | Común | ✅ |
| Paso Atrás | Habilidad | 0 | Gana 3 de escudo. | Común | ✅ |
| Golpe Desesperado | Ataque | 1 | Inflige 12 de daño; descarta una carta al azar de tu mano. | Poco común | ✅ |
| Lluvia de Dagas | Ataque | 2 | Inflige 10 de daño a 2 enemigos al azar. | Común | ✅ |
| Abanico de Cuchillas | Ataque | 2 | Inflige 5 de daño a todos. **Singular:** gana 5 de escudo y roba 1. | Épica | ✅ |
| Golpe de Gracia | Ataque | 1 | Inflige 8 de daño; si lo matas, recupera 1 de maná. | Poco común | ✅ |
| Ritmo Letal | Poder | 2 | Este combate, la primera carta de cada turno cuesta 1 menos. | Legendaria | ✅ |
| Danza de Sombras | Poder | 2 | Este combate, tus Combos se activan sin jugar otra carta antes. | Épica | ✅ |
| Guardia Evasiva | Habilidad | 2 | Gana 10 de escudo. **Combo:** los enemigos quedan Débiles este turno (−25% daño). | Poco común | ✅ |
| Reflejos | Poder | 1 | Gana 1 de destreza este combate. | Poco común* | ✅ |
| Astucia | Habilidad | 1 | Roba 2 cartas. | Épica | ✅ |
| Dagas Ocultas | Habilidad | 1 | Mete 2 Dagas Ocultas en tu pila de robo (al robarlas se juegan solas: 4 de daño a un enemigo al azar). **Combo:** mete 3. | Rara* | ✅ |
| Tormenta de Acero | Poder | 1 | Al inicio de cada turno inflige 3 de daño a todos. **Singular:** 5. | Legendaria | ✅ |
| Corte y Guardia | Ataque | 1 | Inflige 3 de daño y gana 3 de escudo. | Común | ✅ |
| Afilar | Habilidad | 1 | Tu siguiente carta que haga daño este turno inflige 6 más. | Común | ✅ |
| Muro de Humo | Habilidad | 2 | Gana 14 de escudo. | Poco común* | ✅ |
| Cuchillada Errante | Ataque | 1 | Inflige 4 de daño a un enemigo al azar. **Combo:** hazlo de nuevo. | Común | ✅ |

\* Rareza elegida por mí (no venía en la lista); cámbiala si quieres.

La Pícara ya tenía antes: Tajo, Corte Rápido, Instinto, Escudo Reactivo, Agilidad,
Torbellino, Veneno, Lluvia de Golpes, Tormenta de Veneno, Mazo Impecable y Finta (inicial).

---

## Reliquias

### Neutrales

| Reliquia | Efecto | Rareza | Estado |
|---|---|---|---|
| Amuleto de Vitalidad | +10 de vida máxima. | Común | ✅ |
| Trébol de Siete Hojas | +100 de suerte (muchísima suerte). Referencia a Futurama. | Legendaria | ✅ |
| Ankh | Al recibir un golpe fatal, revives con toda tu vida (una vez). | Legendaria | ✅ |
| Espejo Singular | Al obtenerla, elimina todas tus cartas repetidas: te quedas con una copia de cada carta. | Legendaria | ✅ |
| Panacea | Eres inmune a cualquier debuff de los enemigos (p. ej. Débil). | Legendaria | ✅ |
| Fuente Eterna | Al inicio de cada turno ganas 1 de maná máximo. | Legendaria | ✅ |

### Pícara

| Reliquia | Efecto | Rareza | Estado |
|---|---|---|---|
| Broche de Evasión | Cada vez que activas un Combo, ganas 1 de bloqueo. | Poco común | ✅ |
| Cuchillo Arrojadizo | Cada vez que activas un Combo, inflige 1 de daño a un enemigo al azar. | Poco común | ✅ |

### Ya existentes (antes de esta lista)

| Reliquia | Efecto | Rareza |
|---|---|---|
| Poción de Sangre | Recupera 8 HP después de cada combate. | Común |
| Anillo de Oro | +15 de oro por victoria de combate. | Común |
| Corazón de Hierro | +15 de vida máxima. | Poco común |
| Orbe de Fuego | +2 de daño en todos los ataques. | Poco común |
| Tótem Roto | +1 carta robada cada turno. | Rara |
| Piedra de Energía | +1 carta robada cada turno. | Rara |
| Amuleto de Combate | +1 de maná máximo al inicio del combate. | Épica |
| Escudo Espectral | Sobrevives una vez con 1 HP a un golpe fatal. | Legendaria |

---

## Mejoras de cartas — El Brujo ✅

- Aparece **una vez por piso** en el mapa (sala "Brujo").
- Mejoras tus cartas pagando oro; puedes mejorar varias si te alcanza.
- Toda carta se puede mejorar. Las normales **una vez** (quedan como "Golpe+"); una carta
  puede declararse mejorable varias veces o **sin límite** ("Golpe+2", "Golpe+3"…).
- Qué mejora (si la carta no define la suya):
  - Si hace daño o da escudo: +3 (o +1/3 del valor si es mayor).
  - Si no, y cuesta maná: cuesta 1 menos.
  - Si es gratis: roba 1 carta más.
- Una carta puede definir su propia mejora: maná, daño, escudo, robo, maná ganado o un texto/efecto nuevo.
- Para ver qué gana cada carta: **"Ver mejoras (V)"** muestra todo el mazo ya mejorado, el
  tooltip de cada carta dice "Al mejorarla: …" y al hacer clic sale la carta actual → mejorada.

| Rareza | Precio de la mejora |
|---|---|
| Común | 50 |
| Poco común | 75 |
| Rara | 100 |
| Épica | 150 |
| Legendaria | 200 |

Las cartas mejorables varias veces cuestan más en cada nivel: precio × (nivel + 1).

---

## Personajes

| Personaje | Vida | Daño | Destreza | Suerte | Maná |
|---|---|---|---|---|---|
| La Guerrera | 100 | 4 | 4 | 2 | 2 |
| El Mago | 60 | 8 | 1 | 5 | 4 |
| La Pícara | 70 | 6 | 2 | 8 | 3 |

---

## Arquetipos

| Clase | Arquetipos |
|---|---|
| Pícara | Combo · Suerte |
| Mago | Vacío · Cartas de elementos |
| Guerrera | Bloqueo · Fuerza · Curación |

---

## Ideas sueltas

- *
