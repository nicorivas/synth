"""Prueba headless del arreglo (canción): encadenar patrones con `order`.

Verifica que el secuenciador avanza de un patrón al siguiente según el orden,
disparando las notas del patrón vigente, y que la canción de ejemplo carga con
sus cuatro patrones."""

import json

import engine as E
import presets
from sequencer import Sequencer


def main():
    eng = E.Engine()
    seq = Sequencer(eng)
    n = len(eng.instruments)

    # dos patrones de 2 pasos: A dispara lead(60) en el paso 0; B, bajo(40) en el paso 0
    A = [[None, None] for _ in range(n)]; A[0][0] = 60
    B = [[None, None] for _ in range(n)]; B[1][0] = 40
    presets.restore(eng, seq, {"bpm": 240, "patterns": {"A": A, "B": B},
                               "order": ["A", "B"]})
    assert len(seq.patterns) == 2 and seq.order == [0, 1], (seq.order, seq.patterns)
    print("carga patrones + orden: ok")

    # espiamos qué nota se dispara, anotando en qué punto del arreglo y paso
    fired = []
    real_note_on = eng.note_on
    def spy(midi, inst=None, vel=1.0):
        fired.append((seq.order_pos, seq.pos, midi))
        real_note_on(midi, inst, vel)
    eng.note_on = spy

    t = 0.0
    seq.play(t)
    dur = seq.step_dur()
    for _ in range(8):          # A0 A1 B0 B1 A0 A1 B0 B1 (vuelve a empezar)
        seq.tick(t)
        t += dur

    step0 = {(op, midi) for (op, ps, midi) in fired if ps == 0}
    assert (0, 60) in step0, f"patrón A no disparó su nota: {fired}"
    assert (1, 40) in step0, f"patrón B no disparó su nota: {fired}"
    assert seq.order_pos == 1, seq.order_pos     # tras 8 pasos volvimos al patrón B
    print("encadena y repite el arreglo: ok")

    # --- duración: una nota larga se sostiene varios pasos (aliento) ---
    eng3 = E.Engine()
    seq3 = Sequencer(eng3)
    n3 = len(eng3.instruments)
    P = [[None] * 4 for _ in range(n3)]
    P[0][0] = [60, 1.0, 3]                 # nota de 3 pasos en el paso 0
    presets.restore(eng3, seq3, {"patterns": {"P": P}, "order": ["P"]})
    offs = []
    real_off = eng3.note_off
    def spy_off(midi, inst=None):
        offs.append((seq3.pos, midi))
        real_off(midi, inst)
    eng3.note_off = spy_off
    t = 0.0
    seq3.play(t)
    d = seq3.step_dur()
    for _ in range(4):                      # pasos 0,1,2,3
        seq3.tick(t)
        t += d
    assert (3, 60) in offs, f"la nota de 3 pasos no se soltó en el paso 3: {offs}"
    assert not any(m == 60 and p in (1, 2) for (p, m) in offs), f"se soltó antes: {offs}"
    print("duración (la nota larga se sostiene): ok")

    # la canción de ejemplo carga entera
    with open("canciones/cancion.json", encoding="utf-8") as f:
        data = json.load(f)
    eng2 = E.Engine(); seq2 = Sequencer(eng2)
    presets.restore(eng2, seq2, data)
    assert len(seq2.patterns) == 4, len(seq2.patterns)
    assert len(seq2.order) == 8, len(seq2.order)
    assert seq2.patterns[seq2.order[-1]].name == "fill"   # el arreglo termina en el relleno
    print("canción de ejemplo: ok")

    print("OK -> song")


if __name__ == "__main__":
    main()
