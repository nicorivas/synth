# kichoro · synth

Un sintetizador sustractivo que vive entero en el terminal. Suena de verdad
(por los parlantes), se maneja con el mouse y con el teclado.

```
./synth        # o:  uv run synth.py
```

La primera vez `uv` arma el entorno solo (numpy, scipy, sounddevice, textual).

## Qué tiene

- **Polifónico** (8 voces), síntesis sustractiva clásica:
  - 2 osciladores con *detune*; ondas: seno, triángulo, sierra, cuadrada
    (sierra/cuadrada con anti-aliasing polyBLEP).
  - Filtro pasa-bajos resonante; la envolvente lo abre (`E→F`).
  - Envolvente ADSR.
- **Capa B en el lead**: un segundo patch completo (osciladores, filtro,
  envolventes y LFO propios) que al activarse suena apilado con el primero en
  cada nota —el *layer* de los sintes de los 80. En el panel "capa B" se
  enciende y se elige si el rack de controles edita la capa A o la B; los
  presets y las canciones guardan las dos capas. Cada capa tiene su propia
  **afinación** (`Semi` en semitonos, `Fine` en cents): la B puede ir una
  octava o una quinta arriba, o apenas corrida para engordar el unísono.
- **Ecualizador por capa**, en la pantalla principal (junto al osciloscopio):
  8 bandas de octava (63 Hz–8 kHz) de ±12 dB después del filtro, como barras
  clickeables/arrastrables (o ←→ y ↑↓ con el foco) sobre la curva de respuesta
  total. El cutoff sigue barriendo esa curva —con su envolvente y LFO— y tú
  decides qué frecuencias suben, se quedan o bajan.
- **Osciloscopio** en vivo (braille).
- **Piano** de dos octavas, clickeable.
- **Presets**: guardar y recuperar la foto completa (el sonido de todos los
  instrumentos *y* el patrón del secuenciador). Tercer tab, "presets".
- **Tonalidad** (componer dentro de una escala): eliges tónica + escala
  (mayor/menor) en el tab "tonalidad"; el piano resalta las notas de la escala y
  la **fila 1–7 toca el acorde de cada grado** (con su mayor/menor automático;
  tríada o séptima). El panel muestra los 7 acordes con su nombre.

## Cómo se toca

| acción | mouse | teclado |
|---|---|---|
| tocar notas | clic/arrastre en el piano | fila `z…` (octava base), fila `q…` (una arriba); negras en `s d g h j` (y `2 3 5 6 7` si la fila numérica está en "cromático") |
| tocar acordes | — | `1`–`7` tocan el acorde de cada grado de la tonalidad |
| elegir tonalidad | clic en los selectores del tab "tonalidad" | — |
| cambiar octava | — | `−` baja, `=` sube |
| mover un control | clic+arrastra el fader (o rueda) | `Tab` mueve el foco, flechas suben/bajan, `PgUp/PgDn` salta |
| elegir onda | clic en la opción | flechas con el selector enfocado |
| pánico (apagar todo) | — | `espacio` |
| guardar/cargar preset | clic en la lista del tab "presets" | escribe el nombre + `Enter` guarda; `↑↓` + `Enter` carga; `d` borra |
| salir | — | `ctrl+c` |

## Nota sobre sostener notas con el teclado

El terminal no avisa cuándo *sueltas* una tecla, así que la nota se mantiene
mientras el sistema repite la tecla y se suelta ~0.4 s después (constante
`GATE_TIMEOUT` en `ui.py`). Si el *retardo inicial* de repetición de tu teclado
es más largo que ese gate, la nota alcanza a soltarse antes de la primera
repetición; en ese caso la repetición la **retoma donde iba** (legato) en vez de
atacarla de nuevo —antes sonaba dos veces. El piano con **mouse** sí sostiene
exacto (mantén apretado). Para tocar fluido con el teclado, conviene una
repetición de tecla rápida en macOS (Ajustes → Teclado → *Velocidad de
repetición* alta y *Retardo* corto).

## Componer en vivo (sin tocar el piano)

El piano y el secuenciador son para tocar a mano. Pero también se puede componer
**escribiendo un archivo** y oyéndolo recargarse en caliente, sin reiniciar:

```
./play canciones/primera.json     # lo suena por los parlantes
```

`player.py` vigila ese archivo (una "foto" en JSON, el mismo formato que los
presets: basta el bloque `sequencer` con el `bpm` y la grilla de 6 pistas × 16
pasos, cada celda `null` o una nota midi) y cada vez que lo guardas vuelve a
sonar con el cambio. Para revisar una pieza **sin** tarjeta de audio —que suene
algo, que no sature, qué alturas tiene— está el render fuera de línea:

```
uv run render.py canciones/primera.json 4 render.wav   # -> WAV + análisis
```

Así nació este flujo: Kichoro escribe el archivo y revisa por números (FFT,
nivel); una persona con oídos lo escucha en vivo y le va diciendo cómo suena.

### Canciones largas: patrones + arreglo

Una grilla sola es un compás que se repite. Para piezas largas hay dos niveles
(como un *tracker*): **patrones** con nombre y un **arreglo** (`order`) que los
encadena. La canción suena los patrones en ese orden y vuelve a empezar; con
pocos patrones reusados se arman minutos de música, y reordenar la pieza es solo
cambiar la lista `order` —sin tocar los patrones.

```jsonc
{
  "bpm": 100,
  "patterns": {            // cada patrón: 6 pistas (lead,bajo,pad,kick,snare,hat);
    "A": [ ... ],          // pueden tener distinto largo (8, 16, 32…)
    "B": [ ... ],
    "fill": [ ... ]
  },
  "order": ["A", "A", "B", "B", "fill"]   // el arreglo = la canción
}
```

`canciones/cancion.json` es un ejemplo completo en La menor (intro, groove, un
*lift* y un relleno). El formato viejo de un solo patrón (`sequencer.grid`) sigue
cargando igual.

### Dinámica y groove de la percusión

Para que la batería no suene tiesa, una celda puede llevar **velocity** además de
la nota — `[nota, vel]` con `vel` en 0..1 — y así se escriben acentos y *ghost
notes*. Un `"swing"` (0..0.7) atrasa el contratiempo y le da balanceo. El kit son
7 voces: kick, redoble, **hat cerrado y abierto** (el cerrado *ahoga* al abierto,
como un charles real). `canciones/percusion.json` lo muestra todo.

```jsonc
{
  "bpm": 96,
  "swing": 0.5,                       // groove: atrasa los 16avos pares
  "patterns": {
    "groove": [
      // … kick con acento y ghost: golpe fuerte, luego flojito
      [[36, 1.0], null, null, null, null, null, [36, 0.45], null, … ]
    ]
  },
  "order": ["groove"]
}
```

### Notas largas (aliento)

Por defecto cada nota dura un paso y se suelta en el siguiente —de ahí que todo
suene picado. Para que una nota *respire* —el arco largo de una cuerda— se le da
una **duración** en pasos: `[nota, vel, pasos]`. Una nota de duración 16 se
sostiene el compás entero. Si varias pistas sostienen a la vez (bajo + pad +
lead), forman una cama de acorde continua bajo el groove. `canciones/aliento.json`
lo muestra: bajo, pad y lead mantienen el acorde mientras la batería marca.

```jsonc
// pad sosteniendo Do todo el compás, en vez de un pinchazo:
[[60, 0.55, 16], null, null, null, null, null, null, null, … ]
```

### Jazz: componer con teoría

`theory.py` sabe de armonía de jazz: acordes por cualidad (`maj7`, `m7`, `7♭9`…),
**voces guía** (la 3ª y la 7ª, las notas que definen un acorde) y el **ii–V–I**.
`compose_jazz.py` lo usa para escribir una pieza entera: un ii–V–I–VI (Dm7 · G7 ·
Cmaj7 · A7♭9) con bajo caminante, comping de voces guía con conducción de voces
suave (cada acorde se mueve por medios tonos y notas comunes) y batería con swing
de corcheas. El resultado vive en `canciones/jazz.json`.

```
uv run compose_jazz.py        # regenera canciones/jazz.json
./play canciones/jazz.json    # a escucharlo
```

## Estructura

- `engine.py` — motor de audio (numpy/scipy/sounddevice). No sabe de la UI.
  Incluye el kit de percusión de 9 voces (kick, redoble, hats cerrado/abierto con
  choke, 2 toms) con ruido filtrado por modo, click de ataque y velocity.
- `sequencer.py` — secuenciador por pasos en dos niveles: patrones (grilla
  nota-por-paso) y arreglo (`order` que los encadena en una canción).
- `theory.py` — teoría musical pura: escalas y modos, acordes diatónicos por
  grado, y armonía de jazz (acordes por cualidad, voces guía, ii–V–I).
- `presets.py` — guardar/cargar la foto completa a `presets/*.json`. No sabe de la UI.
- `ui.py` — interfaz Textual (faders, selector, osciloscopio, piano, grilla, presets).
- `synth.py` / `synth` — punto de entrada (la TUI interactiva).
- `player.py` / `play` — reproductor en vivo: vigila un archivo de música y lo
  re-suena al cambiarlo, sin reiniciar. Para componer escribiendo.
- `render.py` — render fuera de línea: toca una partitura sin audio, escribe un
  WAV y un análisis (nivel, pico, afinación). El "ojo" para revisar sin oír.
- `compose_jazz.py` — genera un tema de jazz (ii–V–I–VI) desde `theory.py`:
  voces guía, bajo caminante y swing → `canciones/jazz.json`.
- `compose_jazz_solo.py` — un tema largo sobre la misma progresión, como un solo
  de batería: la base sigue corriendo y la batería construye → `canciones/jazz-solo.json`.
- `compose_samsara.py` — una pieza de mantra budista: drone modal (frigio), canto
  de Oṃ Maṇi Padme Hūm, campana y latido, en un ciclo sin fin → `canciones/samsara.json`.
- `canciones/` — las piezas, en JSON. `primera.json` es un loop de un compás;
  `cancion.json` encadena varios patrones; `percusion.json` muestra velocity,
  swing y los hats con choke; `aliento.json` muestra notas largas sostenidas;
  `jazz.json` es un ii–V–I–VI con voces guía y bajo caminante; `jazz-solo.json`
  es un tema largo (~1:40) como solo de batería sobre esa misma base;
  `samsara.json` es un mantra budista (drone + canto en frigio, en bucle).
- `test_engine.py` — prueba headless del motor (verifica afinación, escribe `demo.wav`).
- `test_ui.py` — monta la UI sin audio y exporta una captura `ui.svg`.
- `test_presets.py` — ida y vuelta de presets por disco, headless.
- `test_theory.py` — escalas, acordes diatónicos y sus nombres (Do mayor, La menor).
- `test_render.py` — toca la canción de ejemplo headless; verifica que suena y no satura.
- `test_song.py` — el arreglo: que `order` encadene patrones y la canción de ejemplo cargue.
- `test_drums.py` — la percusión: velocity, choke (cerrado ahoga al abierto) y swing.

Si el osciloscopio o algún símbolo se ven como cuadritos, es la fuente del
terminal sin glifos braille; usa una con buen soporte (p. ej. una Nerd Font).

## Para desarrollar

Requisitos:

- [**uv**](https://docs.astral.sh/uv/) (resuelve el entorno y las dependencias).
- **Python ≥ 3.12** (uv lo instala solo si no lo tienes).
- Una **salida de audio** para escucharlo (los tests no la necesitan).
- Un terminal con buen soporte braille para el osciloscopio (ver nota de arriba).

Arranque desde cero:

```
git clone <url-del-repo> synth
cd synth
uv sync          # arma .venv con numpy, scipy, sounddevice, textual
./synth          # corre la app
```

### Pruebas

Todo es *headless*: no abren la tarjeta de audio ni necesitan un terminal real,
así que corren en cualquier máquina o en CI. Cada una imprime `OK` al final.

```
uv run test_engine.py    # afinación del motor por FFT; escribe demo.wav
uv run test_theory.py    # escalas y acordes diatónicos (Do mayor, La menor)
uv run test_presets.py   # guardar/cargar presets, ida y vuelta por disco
uv run test_ui.py        # monta la UI sin audio; exporta una captura ui.svg
```

`demo.wav`, `ui.svg` y `ui.png` son artefactos regenerables (están en
`.gitignore`). Antes de mandar un cambio, corre las cuatro pruebas.

## Contribuir

Las pautas (arquitectura, estilo, cómo proponer un cambio) están en
[`CONTRIBUTING.md`](CONTRIBUTING.md). En corto: el motor de audio no sabe de la
UI, la teoría musical es pura, y cada cambio pasa los `test_*.py`.

## Licencia

[MIT](LICENSE).
