# Contribuir a synth

Gracias por mirar este sintetizador. Es un proyecto chico y deliberado: un
sintetizador sustractivo que vive entero en el terminal, suena de verdad y se
puede leer de cabo a rabo en una tarde. Esa legibilidad es la feature principal;
cuídala.

## Empezar

```
git clone <url-del-repo> synth
cd synth
uv sync          # arma .venv con las dependencias del pyproject.toml
./synth          # corre la app  (o: uv run synth.py)
```

Necesitas [uv](https://docs.astral.sh/uv/) y una salida de audio para
escucharlo. Python lo instala uv solo (pedimos ≥ 3.12).

## Cómo está armado

Cada módulo tiene una responsabilidad y los límites entre ellos son la regla más
importante del proyecto:

- **`engine.py`** — el motor de audio (numpy/scipy/sounddevice): osciladores,
  filtro, envolvente ADSR, mezcla de voces. **No sabe que existe una UI.** Si tu
  cambio hace que el motor importe algo de `ui.py`, vas en contra del diseño.
- **`sequencer.py`** — secuenciador por pasos (la grilla nota-por-paso y el reloj
  por BPM). Tampoco sabe de la UI.
- **`theory.py`** — teoría musical **pura** (escalas, acordes diatónicos por
  grado). Sin estado, sin efectos: entra un número, sale un número. Es lo más
  fácil de testear; aprovéchalo.
- **`presets.py`** — serializa la foto completa (sonido + patrón del
  secuenciador) a `presets/*.json` y la lee de vuelta. No sabe de la UI.
- **`ui.py`** — la única capa que conoce a las demás. Interfaz Textual: faders,
  selector de onda, osciloscopio, piano, grilla, presets. Aquí vive el manejo de
  teclado/mouse.
- **`synth.py` / `synth`** — el punto de entrada.

Regla de oro: **el flujo de dependencias va hacia `ui.py`, nunca al revés.**
Eso es lo que deja probar el motor sin audio y la teoría sin nada.

## Pruebas

Hay una prueba *headless* por pieza. No abren la tarjeta de audio ni necesitan un
terminal real, así que corren en cualquier parte. Cada una imprime `OK`.

```
uv run test_engine.py    # verifica la afinación por FFT; escribe demo.wav
uv run test_theory.py    # escalas y acordes (casos comprobables a mano)
uv run test_presets.py   # guardar/cargar presets por disco
uv run test_ui.py        # monta la UI sin audio; exporta ui.svg
```

Antes de proponer un cambio, **corre las cuatro y deja que pasen.** Si tocas el
motor, escucha el `demo.wav` que genera `test_engine.py`. Si agregas
comportamiento, agrega (o extiende) la prueba que lo cubra: las pruebas de este
repo verifican cosas que un humano puede comprobar a oído o a mano (un La a 440
Hz, las teclas blancas de Do mayor), no solo que el código no explote.

`demo.wav`, `ui.svg` y `ui.png` son artefactos regenerables y están en
`.gitignore`; no los subas.

## Estilo

- **Español**, en el código, los comentarios y los mensajes de commit. Es la
  lengua del proyecto.
- Los comentarios explican el **porqué**, no el qué. El código dice qué hace.
- Cómodo con numpy vectorizado; evita el loop por muestra salvo en el polyBLEP y
  donde de verdad haga falta.
- Sin dependencias nuevas a la ligera. Cuatro paquetes (numpy, scipy,
  sounddevice, textual) son suficientes para mucho; justifica cualquier quinto.

## Proponer un cambio

1. Una rama por cambio (`git switch -c lo-que-hace`).
2. Mantén el PR enfocado en una cosa.
3. En el mensaje de commit: una línea corta en imperativo, con prefijo de área
   cuando ayude — p. ej. `motor: ...`, `ui: ...`, `teoría: ...`, `presets: ...`.
4. Describe **qué cambia y por qué**; si afecta al sonido, di cómo escucharlo.
5. Las cuatro pruebas pasan.

Ideas, dudas o "¿esto tiene sentido?" → abre un issue antes de escribir mucho
código. Mejor conversar temprano que rehacer.
