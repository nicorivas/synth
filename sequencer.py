"""Secuenciador por pasos.

Una pista por instrumento del motor; cada celda de la grilla está apagada o
guarda una nota (midi) — modelo melódico, nota por paso. El reloj avanza a un
tempo (BPM) en 16avos; en cada paso dispara las notas encendidas en el
instrumento de su pista y suelta las del paso anterior. La percusión decae sola,
pero soltarla igual no molesta.

No sabe nada de la interfaz: la UI lee `grid`/`pos`/`playing` para dibujar y
llama `tick(now)` desde su reloj. El tiempo entra de afuera (time.monotonic) para
que sea fácil de probar sin reloj real.
"""

from __future__ import annotations


# nota por defecto al encender un paso, por pista (índice = instrumento):
# lead/pad melódicos a media altura; bajo grave; kick/snare/hat a su tono típico
_DEFAULT_NOTE = [60, 36, 60, 36, 50, 54]


class Sequencer:
    def __init__(self, engine, n_steps: int = 16):
        self.engine = engine
        self.n_steps = n_steps
        n_tracks = len(engine.instruments)
        self.grid = [[None] * n_steps for _ in range(n_tracks)]  # None=off, o midi
        self.default_note = [(_DEFAULT_NOTE[i] if i < len(_DEFAULT_NOTE) else 60)
                             for i in range(n_tracks)]
        self.bpm = 110
        self.playing = False
        self.pos = -1               # paso actual (-1 = detenido)
        self._next = 0.0            # próximo instante de avance (reloj monotónico)
        self._sounding = []         # (track, midi) disparadas en el paso vigente

    # --- edición ---

    def step_dur(self) -> float:
        return 60.0 / max(self.bpm, 1) / 4.0      # 16avos (4 pasos por negra)

    def toggle(self, track: int, step: int):
        cur = self.grid[track][step]
        self.grid[track][step] = None if cur is not None else self.default_note[track]

    def set_note(self, track: int, step: int, midi: int):
        self.grid[track][step] = max(0, min(108, midi))

    def shift_note(self, track: int, step: int, d: int):
        cur = self.grid[track][step]
        if cur is not None:
            self.set_note(track, step, cur + d)

    # --- transporte ---

    def play(self, now: float):
        self.playing = True
        self.pos = -1
        self._next = now            # el primer tick dispara el paso 0

    def stop(self):
        self.playing = False
        self._release()
        self.pos = -1

    def _release(self):
        for tr, midi in self._sounding:
            self.engine.note_off(midi, inst=tr)
        self._sounding = []

    def tick(self, now: float) -> bool:
        """Llamar seguido desde el reloj de la UI. Avanza si toca. Devuelve True
        si cambió de paso (para repintar)."""
        if not self.playing or now < self._next:
            return False
        self._advance()
        self._next += self.step_dur()
        if self._next <= now:        # si el reloj se atrasó, re-sincroniza
            self._next = now + self.step_dur()
        return True

    def _advance(self):
        self._release()                                   # soltar el paso anterior
        self.pos = (self.pos + 1) % self.n_steps
        for tr, row in enumerate(self.grid):
            note = row[self.pos]
            if note is not None:
                self.engine.note_on(note, inst=tr)
                self._sounding.append((tr, note))
