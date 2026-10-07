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
| **Ataque** | Hace su efecto y va al descarte. | 40 | ✅ |
| **Habilidad** | Hace su efecto y va al descarte. | 48 | ✅ |
| **Poder** | Hace su efecto y se queda en juego el resto del combate; puede tener un efecto al inicio de cada turno. | 13 | ✅ |
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
| **Despojo** | Efecto extra si ya descartaste una carta este turno. Solo cuentan los descartes de cartas o reliquias, no el descarte del final del turno. | Solo Pícara | ✅ |

**Regla de diseño:** la palabra clave *es* la condición. Un efecto de palabra clave nunca
añade otra condición propia ("Combo: si además…" no vale). Lo comprueba un test.

La columna **Clases** indica qué clases tienen cartas con esa palabra: *Todas*, *Solo X*
o una lista (*Guerrera y Mago*). La regla en sí funciona igual para cualquier carta.

---

## Estados

| Estado | Efecto | Quién lo aplica | Estado |
|---|---|---|---|
| **Veneno** | Pierde X de vida al inicio de su turno; baja 1 por turno. | Cartas (enemigos) | ✅ |
| **Débil** | Inflige 25% menos de daño. | Guardia Evasiva (a enemigos, 1 turno); intención DEBUFF de enemigos (al héroe, 2 turnos) | ✅ |
| **Marcado** | Cada golpe que recibe hace X de daño más. Se quita al terminar tu turno. | Marcar Objetivo (Pícara) | ✅ |
| **Veneno (héroe)** | El héroe pierde X de vida al inicio de su turno (ignora el bloqueo); baja 1. | Reina Micélida, Espora | ✅ |
| **Vulnerable** | Recibe 50% más de daño de ataques. Baja 1 al terminar tu turno. | La Tejedora | ✅ |
| **Frágil** | Gana 25% menos de escudo con cartas. Baja 1 al terminar tu turno. | La Tejedora | ✅ |
| **Enredado** | Roba 1 carta menos por acumulación en su próximo turno; luego desaparece. | La Tejedora | ✅ |
| **Fuerza** (enemigos) | Cada golpe hace X de daño más. Permanente. | Caballero Hueco (Furia Hueca) | ✅ |
| **Espadas** (enemigo) | Espadas flotantes: la Danza de Espadas golpea una vez por espada (máx. 6). | Caballero Hueco | ✅ |

Cada estado tiene su **icono** (`assets/ui/icons.png`): aparece en la insignia bajo el
personaje (con las acumulaciones en la esquina), en la intención del enemigo y en el
tooltip que lo explica. Pasar el ratón por una insignia muestra su regla.

---

## Interfaz de lectura ✅

- **Intenciones**: icono grande + número ("6", "4×3"); la espada crece con el daño total;
  iconos pequeños para escudo / mejora / perjuicio / cartas de estado. Brillo rojo y
  calavera si los ataques de este turno te matan. Ratón encima → qué hará, en frases.
- **Tooltips**: panel principal + un panel por palabra clave o estado mencionado (Veneno,
  Combo, Agotar…). Colores: daño rojo, escudo azul, palabras clave doradas, Veneno verde.
- **Barra de vida del héroe**: parpadea la vida que te quitarán los ataques ("−N").
- **Turno enemigo**: un cartel por enemigo con su movimiento y lo que te hizo.

---

## Cartas de estado

Cartas basura que los enemigos meten en tu mazo **solo durante el combate** (nunca entran al
mazo de la partida). Tipo *Estado*, marco verde enfermizo, arte en `assets/cards-v2/art/`.

| Carta | Coste | Efecto | Quién la añade | Estado |
|---|---|---|---|---|
| **Espora** | 1 | Agotar. Si sigue en tu mano al final del turno, recibes 3 de Veneno. | Reina Micélida | ✅ |
| **Moho** | — | Injugable. Al robarla pierdes 1 de maná. Se desvanece al final del turno (etérea). | Reina Micélida | ✅ |

---

## Gachapón ✅

Sala del mapa ("Gacha", una por piso). Una máquina de cápsulas que vende reliquias al azar.

| Tirada | Precio base | Probabilidades (sin suerte) | Extra |
|---|---|---|---|
| Normal | 80 oro | Común 50% · Poco común 28% · Rara 14% · Épica 6% · Legendaria 2% | — |
| Estelar | 190 oro | Común 0% · Poco común 40% · Rara 34% · Épica 18% · Legendaria 8% | Doble probabilidad de dorada |

- **Cada tirada (de cualquier tipo) multiplica por 1,5 el precio de las siguientes** durante
  toda la partida: 80 → 120 → 180 → 270… / 190 → 285 → 430…; la Máscara del Ladrón lo rebaja.
- La suerte mejora los tiers altos igual que en el resto de reliquias.
- No salen reliquias repetidas hasta que no queden nuevas.
- Al abrir la cápsula eliges **Quedármela** o **Rechazar**. Si la rechazas no se devuelve el oro
  (y el precio de la siguiente tirada ya subió), pero la reliquia puede volver a salir.
- El color de la cápsula indica la rareza (gris, verde, azul, morado, dorado); cuanto más rara,
  más se agita antes de abrirse y más grande es la explosión.

---

## Jefes

Piso 1: uno de tres, elegido por la semilla (Pruebas → "Jefe del piso 1" lo fija;
"Todas las salas: el jefe" convierte cada combate en el jefe para probarlos). Pisos 2+:
Señor de la Cripta. Cada jefe sigue un **patrón fijo y legible** y tiene un movimiento
único la primera vez que baja a la mitad de vida.

### Reina Micélida — cartas tóxicas (138 PV)
Hongo reina: sombrero carmesí con manchas tóxicas, rostro en la sombra de las láminas, velo de encaje.

| Turno | Movimiento | Efecto |
|---|---|---|
| 1 | Lluvia de Esporas | 6 de daño y baraja 2 Esporas en tu pila de robo |
| 2 | Raíces Estranguladoras | 10 de daño y 3 de Veneno |
| 3 | Brote de Moho | 12 de bloqueo y baraja 2 Moho en tu pila de robo |
| ≤50% (una vez) | Floración Pútrida | 4 de Veneno y 2 Esporas en tu mano |

### La Tejedora — debuffs (126 PV)
Araña matriarca: quitina violeta, reloj de arena carmesí, ocho ojos magenta, hilos de seda.

| Turno | Movimiento | Efecto |
|---|---|---|
| 1 | Hilos Pegajosos | Débil 2 y Enredado 1 |
| 2 | Colmillo | 9 de daño y Vulnerable 2 |
| 3 | Capullo de Seda | 10 de bloqueo y Frágil 2 |
| 4 | Banquete | 5 de daño × (1 + debuffs distintos que tengas) |
| ≤50% (una vez) | Madre de la Camada | Débil, Frágil, Vulnerable y Enredado 1 a la vez |

### Caballero Hueco — ataques múltiples (150 PV, empieza con 2 Espadas)
Armadura vacía flotante: yelmo coronado con visera de brasas, guanteletes sin brazos, espadón.

| Turno | Movimiento | Efecto |
|---|---|---|
| 1, 4 | Danza de Espadas | 4 de daño × Espadas (cada espada vuela por separado) |
| 2, 5 | Llamar al Acero | +1 Espada (máx. 6) y 8 de bloqueo |
| 3 | Estocada Doble | 8 de daño × 2 |
| 6 | Tajo del Verdugo | 17 de daño |
| ≤50% (una vez) | Furia Hueca | +2 Fuerza (cada golpe +2) y 6 de bloqueo |

El bloqueo absorbe cada golpe por separado, así que los ataques múltiples castigan el
bloqueo justo y premian Contraataque (daño por cada golpe bloqueado del todo).

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
| Puñalada Trapera | Ataque | 1 | Inflige 5 de daño. **Combo:** +5 de daño. | Poco común | ✅ |
| Tajo Veloz | Ataque | 1 | Inflige 6 de daño. **Combo:** +1 de maná. | Común | ✅ |
| Tirar y Cortar | Ataque | 1 | Inflige 6 de daño. **Despojo:** +6 de daño. | Común | ✅ |
| Ráfaga de Cortes | Ataque | 1 | 2 de daño por cada carta jugada este turno (esta incluida). | Rara | ✅ |
| Lanzar la Daga | Ataque | 0 | Inflige 4 de daño; mete 1 Daga Oculta en tu pila de robo. | Común | ✅ |
| Corte Afortunado | Ataque | 1 | Inflige 6 de daño; crítico de +6 con probabilidad 10% + 2,5% por punto de Suerte (máx. 75%). | Rara | ✅ |
| Abrir la Guardia | Ataque | 1 | Inflige 4 de daño y luego le quita todo el escudo. | Común | ✅ |
| Hoja Única | Ataque | 1 | Inflige 8 de daño. **Singular:** +8 de daño. | Rara | ✅ |
| Mil Cortes | Ataque | 3 | Por cada carta en tu descarte, 3 de daño a un enemigo al azar. | Legendaria | ✅ |
| Quiebro | Habilidad | 1 | Gana 6 de escudo. **Combo:** roba 1. (Iba a llamarse "Esquiva", pero ya es la carta inicial.) | Común | ✅ |
| Finta Doble | Habilidad | 0 | Gana 3 de escudo. **Combo:** 3 de daño a un enemigo al azar. | Común | ✅ |
| Sombra Esquiva | Habilidad | 1 | Gana 7 de escudo. **Combo:** mete 1 Daga Oculta en tu pila de robo. | Poco común | ✅ |
| Manto Raído | Habilidad | 1 | Gana 7 de escudo. **Despojo:** +7 de escudo. | Poco común | ✅ |
| Rodar | Habilidad | 0 | Gana 2 de escudo; descarta una carta al azar y roba 1. | Común | ✅ |
| Deshacerse | Habilidad | 0 | Descarta una carta al azar y gana 4 de escudo. | Común | ✅ |
| Señuelo | Habilidad | 1 | Gana 5 de escudo; el siguiente ataque enemigo de este turno golpea a otro enemigo. | Poco común | ✅ |
| Capa de Sombras | Habilidad | 2 | Gana 8 de escudo; tu escudo no se pierde al empezar tu siguiente turno. | Rara | ✅ |
| Contraataque | Habilidad | 1 | Gana 4 de escudo; cada golpe que bloquees por completo este turno hace 3 de daño al atacante. | Poco común | ✅ |
| Estilo Propio | Habilidad | 2 | Gana 12 de escudo. **Singular:** roba 2. | Épica | ✅ |
| Chatarra | Habilidad | 0 | Roba 1. **Despojo:** +1 de maná. | Común | ✅ |
| Vaciar Bolsillos | Habilidad | 1 | Descarta tu mano y roba esa misma cantidad. | Rara | ✅ |
| Juego de Manos | Habilidad | 0 | Devuelve a tu mano la última carta de tu descarte. | Poco común | ✅ |
| Carterista | Habilidad | 1 | Roba 1; si un enemigo muere este turno, ganas 10 de oro. | Común | ✅ |
| Hoja Envenenada | Habilidad | 1 | Tus próximos 3 ataques aplican 2 de Veneno. | Poco común | ✅ |
| Tirar los Dados | Habilidad | 0 | Gana de 0 a 3 de maná al azar; la Suerte da tiradas extra (te quedas con la mejor). | Rara | ✅ |
| Marcar Objetivo | Habilidad | 1 | Este turno, cada golpe a ese enemigo hace 3 de daño más (Marcado). | Común | ✅ |
| Rapiña | Poder | 1 | Cada carta que descartes inflige 3 de daño a un enemigo al azar. | Épica | ✅ |
| Maestra de Dagas | Poder | 1 | Cada Daga Oculta que robes mete otra en tu pila de robo. | Épica | ✅ |
| Sombra Gemela | Poder | 2 | La primera carta de cada turno que active su Combo lo activa dos veces. | Épica | ✅ |
| Fortuna Audaz | Poder | 1 | Al inicio de cada turno: 50% roba 1, 50% gana 4 de escudo. | Épica | ✅ |
| Nada que Perder | Poder | 2 | Al inicio de cada turno, tras robar, descarta una carta al azar y roba 2. | Legendaria | ✅ |
| Cadena Perfecta | Poder | 2 | Cada quinta carta que juegues en un turno se lanza una vez más. | Legendaria | ✅ |
| Asesina | Poder | 3 | Tus ataques rematan a los enemigos que queden por debajo del 25% de vida. | Legendaria | ✅ |

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
| Máscara del Ladrón | +25% de oro en combates; la tienda es un 10% más barata. | Común | ✅ |
| Moneda de la Suerte | Si un efecto al azar golpea dos veces seguidas al mismo enemigo, +1 de maná. Una vez por turno y solo con 2+ enemigos vivos. | Poco común | ✅ |
| Herradura de Plata | +30 de suerte. | Poco común | ✅ |
| Guante de Seda | La tercera carta que juegas cada turno cuesta 0. | Rara | ✅ |
| Botas Silenciosas | En el primer turno de cada combate robas 2 cartas extra. | Rara | ✅ |
| Hilo de Araña | Si terminas el turno sin cartas en la mano, ganas 6 de escudo. | Épica | ✅ |
| Llave Maestra | Las salas del tesoro te dejan elegir entre 2 reliquias. | Épica | ✅ |
| Reloj Roto | Una vez por combate, al quedarte en 0 de maná con cartas en la mano, recuperas todo el maná. | Legendaria | ✅ |

### Pícara

| Reliquia | Efecto | Rareza | Estado |
|---|---|---|---|
| Broche de Evasión | Cada vez que activas un Combo, ganas 1 de bloqueo. | Poco común | ✅ |
| Cuchillo Arrojadizo | Cada vez que activas un Combo, inflige 1 de daño a un enemigo al azar. | Poco común | ✅ |
| Pañuelo del Duelista | Cuando una carta activa su Combo, hace +2 de daño y da +2 de escudo (solo sobre lo que ya hace). | Poco común | ✅ |
| Cinta Roja | En el primer turno de cada combate, tus Combos se activan sin jugar otra carta antes. | Rara | ✅ |
| Saco de Trapos | Cada vez que activas un Despojo, ganas 2 de escudo. | Común | ✅ |
| Garfio | La primera vez que activas un Despojo cada turno, robas 1. | Poco común | ✅ |
| Bolsillo Roto | Al inicio de cada turno, tras robar, descarta una carta al azar y roba 1. | Rara | ✅ |
| Daga Partida | Tus efectos de Despojo se activan dos veces. | Legendaria | ✅ |
| Bolsa de Dagas | Al inicio de cada combate, mete 2 Dagas Ocultas en tu pila de robo. | Común | ✅ |
| Vaina Afilada | Tus Dagas Ocultas hacen +2 de daño. | Poco común | ✅ |
| Frasco de Veneno | Tu primer ataque de cada turno aplica 1 de Veneno. | Poco común | ✅ |
| Colmillo de Víbora | Cuando un enemigo muere envenenado, su Veneno pasa a otro enemigo al azar. | Rara | ✅ |

Regla: las reliquias de la Pícara solo tocan sus temas (Combo, Despojo, dagas y veneno);
lo demás es neutral.

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
| Pícara | Combo · Despojo · Dagas · Veneno · Suerte |
| Mago | Vacío · Cartas de elementos |
| Guerrera | Bloqueo · Fuerza · Curación |

---

## Ideas sueltas

- *
