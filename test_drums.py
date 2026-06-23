"""Prueba headless de la percusión sofisticada: velocity (acentos/ghost),
choke (el hat cerrado calla al abierto) y swing (el groove atrasa el
contratiempo). Sin tarjeta de audio: golpea a mano y mide la señal."""

import numpy as np

import engine as E
from sequencer import Pattern, Sequencer


def hit_peak(inst_idx: int, vel: float, blocks: int = 12) -> float:
    """Pico de amplitud de un solo golpe, renderizado a mano."""
    eng = E.Engine()
    eng.note_on(60, inst=inst_idx, vel=vel)
    buf = np.zeros((E.BLOCK, 2), dtype=np.float32)
    peak = 0.0
    for _ in range(blocks):
        buf[:] = 0.0
        eng._callback(buf, E.BLOCK, None, None)
        peak = max(peak, float(np.max(np.abs(buf[:, 0]))))
    return peak


def main():
    insts = E.default_instruments()
    names = [i.name for i in insts]
    assert len(insts) == 9, names
    assert "hat-open" in names and "hat" in names, names
    assert "tom-hi" in names and "tom-lo" in names, names
    KICK, HAT, HAT_OPEN = names.index("kick"), names.index("hat"), names.index("hat-open")
    print(f"kit: {names}")
    print("kit ampliado (9 voces: hats cerrado/abierto + 2 toms): ok")

    # --- velocity: un golpe suave suena más bajo que uno fuerte ---
    hard, soft = hit_peak(KICK, 1.0), hit_peak(KICK, 0.2)
    assert soft < hard * 0.6, f"la velocity no atenúa: suave={soft:.3f} fuerte={hard:.3f}"
    print(f"velocity (ghost vs acento): ok  (suave={soft:.3f} < fuerte={hard:.3f})")

    # --- choke: golpear el hat cerrado calla al abierto (mismo choke_group) ---
    eng = E.Engine()
    eng.note_on(60, inst=HAT_OPEN, vel=1.0)
    assert eng.active_notes(HAT_OPEN), "el hat abierto no sonó"
    eng.note_on(60, inst=HAT)                      # el cerrado debe ahogar al abierto
    assert not eng.active_notes(HAT_OPEN), "el choke no calló el hat abierto"
    print("choke (cerrado ahoga al abierto): ok")

    # --- swing: atrasa el siguiente paso (el contratiempo) sin cambiar el tempo ---
    eng = E.Engine()
    seq = Sequencer(eng)
    seq.patterns = [Pattern([[None, None] for _ in range(len(eng.instruments))], "A")]
    seq.order = [0]
    seq.bpm = 120
    seq.swing = 0.0; seq.play(0.0); seq.tick(0.0); plano = seq._next
    seq.swing = 0.5; seq.play(0.0); seq.tick(0.0); swung = seq._next
    assert swung > plano, f"el swing no atrasó el contratiempo: {swung} <= {plano}"
    print(f"swing (atrasa el contratiempo): ok  ({swung:.3f}s vs {plano:.3f}s recto)")

    print("OK -> drums")


if __name__ == "__main__":
    main()
