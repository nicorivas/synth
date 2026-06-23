"""Secuenciador por pasos, con dos niveles: patrón y arreglo (canción).

Nivel 1 — **patrón**: una grilla de N pasos × una pista por instrumento; cada
celda apagada (None) o con una nota (midi). Es el compás de antes.

Nivel 2 — **arreglo**: una lista ordenada de patrones (`order`) que se encadenan
para formar una canción larga. El reloj avanza en 16avos dentro del patrón
vigente; al llegar al último paso salta al siguiente patrón del orden, y al
terminar el orden vuelve al principio (la canción se repite). Así, con pocos
patrones reusados muchas veces, una pieza dura minutos: es un "secuenciador de
secuenciadores".

Compatibilidad: por defecto hay un solo patrón y un orden de un elemento, o sea
exactamente el secuenciador de antes. La TUI y los presets ven `grid` y
`n_steps` como *el patrón vigente*; nunca tienen por qué saber del arreglo.

No sabe nada de la interfaz: la UI lee `grid`/`pos`/`playing` para dibujar y
llama `tick(now)` desde su reloj. El tiempo entra de afuera (time.monotonic) para
que sea fácil de probar sin reloj real.
"""

from __future__ import annotations


# nota por defecto al encender un paso, por pista (índice = instrumento):
# lead/pad melódicos a media altura; bajo grave; kick/snare/hats a su tono típico
_DEFAULT_NOTE = [60, 36, 60, 36, 50, 54, 54, 50, 43]


def _split_cell(cell):
    """Una celda es None, una nota midi, [midi, vel] o [midi, vel, duración].
    Devuelve (midi, vel, dur_en_pasos). Sin duración, dura 1 paso (como antes);
    con duración mayor, la nota se sostiene varios pasos —el aliento largo de una
    cuerda. Una nota suelta = velocity 1.0, duración 1."""
    if cell is None:
        return None, 0.0, 1
    if isinstance(cell, (list, tuple)):
        midi = int(cell[0])
        vel = float(cell[1]) if len(cell) > 1 else 1.0
        dur = int(cell[2]) if len(cell) > 2 else 1
        return midi, max(0.0, min(1.0, vel)), max(1, dur)
    return int(cell), 1.0, 1


class Pattern:
    """Una grilla con nombre: n_tracks filas × n_steps celdas (None | midi).
    Distintos patrones pueden tener distinto largo (un relleno de 8, un compás
    de 16, un puente de 32)."""

    def __init__(self, grid: list, name: str = ""):
        self.grid = grid
        self.name = name

    @property
    def n_steps(self) -> int:
        return len(self.grid[0]) if self.grid and self.grid[0] is not None else 0


class Sequencer:
    def __init__(self, engine, n_steps: int = 16):
        self.engine = engine
        n_tracks = len(engine.instruments)
        # un patrón vacío y un orden de un elemento: el secuenciador clásico
        self.patterns = [Pattern([[None] * n_steps for _ in range(n_tracks)], "A")]
        self.order = [0]                 # arreglo: índices en self.patterns, en orden
        self.order_pos = 0               # en qué punto del arreglo vamos
        self.default_note = [(_DEFAULT_NOTE[i] if i < len(_DEFAULT_NOTE) else 60)
                             for i in range(n_tracks)]
        self.bpm = 110
        self.swing = 0.0                 # 0..~0.6: atrasa los 16avos pares (groove)
        self.playing = False
        self.pos = -1                    # paso dentro del patrón vigente (-1 = detenido)
        self._next = 0.0                 # próximo instante de avance (reloj monotónico)
        self._active = []                # notas sonando: [track, midi, pasos_restantes]

    # --- patrón vigente: lo que la TUI/los presets ven como "la grilla" ---

    @property
    def cur_pattern(self) -> Pattern:
        if not self.patterns:
            return None
        if not self.order:
            return self.patterns[0]
        return self.patterns[self.order[self.order_pos % len(self.order)] % len(self.patterns)]

    @property
    def grid(self) -> list:
        return self.cur_pattern.grid

    @grid.setter
    def grid(self, g: list):
        self.cur_pattern.grid = g

    @property
    def n_steps(self) -> int:
        return self.cur_pattern.n_steps

    # --- edición (siempre sobre el patrón vigente) ---

    def step_dur(self) -> float:
        return 60.0 / max(self.bpm, 1) / 4.0      # 16avos (4 pasos por negra)

    def toggle(self, track: int, step: int):
        row = self.grid[track]
        row[step] = None if row[step] is not None else self.default_note[track]

    def set_note(self, track: int, step: int, midi: int):
        self.grid[track][step] = max(0, min(108, midi))

    def shift_note(self, track: int, step: int, d: int):
        cur = self.grid[track][step]
        if cur is None:
            return
        if isinstance(cur, (list, tuple)):       # conserva la velocity al transponer
            self.grid[track][step] = [max(0, min(108, int(cur[0]) + d))] + list(cur[1:])
        else:
            self.set_note(track, step, cur + d)

    # --- transporte ---

    def play(self, now: float):
        self.playing = True
        self.order_pos = 0
        self.pos = -1
        self._active = []
        self._next = now            # el primer tick dispara el paso 0 del primer patrón

    def stop(self):
        self.playing = False
        self._release_all()
        self.pos = -1

    def _release_all(self):
        for tr, midi, _ in self._active:
            self.engine.note_off(midi, inst=tr)
        self._active = []

    def tick(self, now: float) -> bool:
        """Llamar seguido desde el reloj. Avanza si toca. Devuelve True si cambió
        de paso (para repintar)."""
        if not self.playing or now < self._next:
            return False
        self._advance()
        # swing: el 16avo par (downbeat del par) dura más y el impar menos, sin
        # cambiar el total. Eso atrasa el contratiempo y da el balanceo del groove.
        sw = max(0.0, min(0.7, self.swing))
        dur = self.step_dur() * ((1.0 + sw) if self.pos % 2 == 0 else (1.0 - sw))
        self._next += dur
        if self._next <= now:        # si el reloj se atrasó, re-sincroniza
            self._next = now + dur
        return True

    def _advance(self):
        self.pos += 1
        if self.pos >= self.n_steps:                      # se acabó el patrón...
            self.pos = 0
            if self.order:                                # ...salta al siguiente del arreglo
                self.order_pos = (self.order_pos + 1) % len(self.order)
        # 1) envejecer las notas activas; soltar las que cumplieron su duración.
        #    Una nota con duración 1 se suelta en el paso siguiente (como antes);
        #    una larga se sostiene varios pasos: ese es el aliento largo.
        still = []
        for entry in self._active:
            entry[2] -= 1
            if entry[2] <= 0:
                self.engine.note_off(entry[1], inst=entry[0])
            else:
                still.append(entry)
        self._active = still
        # 2) disparar las notas de este paso
        for tr, row in enumerate(self.grid):
            if self.pos < len(row):
                note, vel, dur = _split_cell(row[self.pos])
                if note is not None:
                    # monofónico por pista: si algo seguía sonando ahí, córtalo limpio
                    for e in self._active:
                        if e[0] == tr:
                            self.engine.note_off(e[1], inst=tr)
                    self._active = [e for e in self._active if e[0] != tr]
                    self.engine.note_on(note, inst=tr, vel=vel)
                    self._active.append([tr, note, dur])
