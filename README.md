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
`GATE_TIMEOUT` en `ui.py`). El piano con **mouse** sí sostiene exacto
(mantén apretado). Para tocar fluido con el teclado, conviene una repetición de
tecla rápida en macOS (Ajustes → Teclado → *Velocidad de repetición* alta y
*Retardo* corto).

## Estructura

- `engine.py` — motor de audio (numpy/scipy/sounddevice). No sabe de la UI.
- `sequencer.py` — secuenciador por pasos (grilla nota-por-paso, reloj por BPM).
- `theory.py` — teoría musical pura (escalas, acordes diatónicos por grado).
- `presets.py` — guardar/cargar la foto completa a `presets/*.json`. No sabe de la UI.
- `ui.py` — interfaz Textual (faders, selector, osciloscopio, piano, grilla, presets).
- `synth.py` / `synth` — punto de entrada.
- `test_engine.py` — prueba headless del motor (verifica afinación, escribe `demo.wav`).
- `test_ui.py` — monta la UI sin audio y exporta una captura `ui.svg`.
- `test_presets.py` — ida y vuelta de presets por disco, headless.
- `test_theory.py` — escalas, acordes diatónicos y sus nombres (Do mayor, La menor).

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
