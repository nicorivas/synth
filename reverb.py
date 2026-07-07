"""Reverb — un poco de sala para las composiciones.

Estilo Freeverb (Schroeder-Moorer): varios filtros peine (comb) en PARALELO con
amortiguación —un pasa-bajos en la realimentación que oscurece la cola— sumados y
pasados por filtros allpass en SERIE que difunden los ecos hasta volverlos una
cola suave. Es el reverb algorítmico clásico: barato y cálido.

Procesa por BLOQUES con numpy. Truco para vectorizar: todos los delays son >= el
tamaño de bloque del motor (512/1024), así las muestras retardadas que necesito
para un bloque ya fueron escritas en bloques anteriores —no hay recursión dentro
del bloque— y todo sale con operaciones de array (la amortiguación, que sí es
recursiva muestra a muestra, la hace `lfilter` con su estado `zi` cruzando bloques).
Es exacto por muestra, independiente del tamaño de bloque (los delays van en muestras).

Puro: no sabe del motor. Recibe un bloque mono seco y devuelve seco + cola.
"""
from __future__ import annotations

import numpy as np
from scipy.signal import lfilter

# longitudes de delay en muestras (a 44100 Hz). Combs de Freeverb (todos > 1024).
# Los allpass de Freeverb son cortos (225..556); los alargo a > 1024 para poder
# vectorizar por bloque —difusión un pelo más suave, que a estas piezas les sienta—.
_COMB = [1116, 1188, 1277, 1356, 1422, 1491, 1557, 1617]
_ALLPASS = [1153, 1051, 1301, 1213]
_INPUT_GAIN = 0.06           # cuánta señal entra a los combs (nivel de la cola). Freeverb
                             # usa 0.015 (muy tenue); acá más presente para que se oiga la sala.


class _Comb:
    """Filtro peine con amortiguación: y[n] = x[n]·g_in leído con retardo L y
    realimentado por `fb` a través de un pasa-bajos de un polo (`damp`)."""
    def __init__(self, L: int):
        self.buf = np.zeros(L)
        self.L = L
        self.w = 0
        self.zi = np.zeros(1)          # estado del pasa-bajos de amortiguación

    def process(self, x: np.ndarray, fb: float, damp: float) -> np.ndarray:
        N = len(x)
        idx = (self.w + np.arange(N)) % self.L
        delayed = self.buf[idx].copy()                 # la salida = lo retardado
        damped, self.zi = lfilter([1.0 - damp], [1.0, -damp], delayed, zi=self.zi)
        self.buf[idx] = x + fb * damped
        self.w = (self.w + N) % self.L
        return delayed


class _Allpass:
    """Allpass de Schroeder (difusor): esparce el eco sin colorear el espectro."""
    def __init__(self, L: int):
        self.buf = np.zeros(L)
        self.L = L
        self.w = 0

    def process(self, x: np.ndarray, g: float = 0.5) -> np.ndarray:
        N = len(x)
        idx = (self.w + np.arange(N)) % self.L
        bufout = self.buf[idx].copy()
        self.buf[idx] = x + bufout * g
        self.w = (self.w + N) % self.L
        return -x + bufout


class Reverb:
    """El reverb completo. `wet` 0 = seco (apagado, no cambia nada). `room` alarga
    la cola; `damp` la oscurece."""
    def __init__(self):
        self.combs = [_Comb(L) for L in _COMB]
        self.allpasses = [_Allpass(L) for L in _ALLPASS]
        self.wet = 0.0        # 0..1 · cuánta sala se mezcla (0 = seco)
        self.room = 0.72      # 0..1 · tamaño (feedback de los combs -> largo de cola)
        self.damp = 0.40      # 0..1 · amortiguación (oscurece la cola)

    def process(self, dry: np.ndarray) -> np.ndarray:
        if self.wet <= 0.0:
            return dry                                 # seco: idéntico a antes
        N = len(dry)
        if N > self.combs[0].L:                        # bloque mayor que el delay: sin reverb
            return dry
        fb = 0.70 + max(0.0, min(1.0, self.room)) * 0.28   # room 0..1 -> fb 0.70..0.98
        damp = max(0.0, min(0.95, self.damp))
        x = dry * _INPUT_GAIN
        acc = np.zeros(N)
        for c in self.combs:
            acc += c.process(x, fb, damp)
        for a in self.allpasses:
            acc = a.process(acc)
        return dry + self.wet * acc

    def reset(self):
        for c in self.combs:
            c.buf[:] = 0.0; c.w = 0; c.zi[:] = 0.0
        for a in self.allpasses:
            a.buf[:] = 0.0; a.w = 0
