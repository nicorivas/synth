"""Prueba headless de los presets: que la foto (patch de cada instrumento +
selección + patrón y tempo del secuenciador) sobreviva un ida y vuelta por disco
exactamente, y que un preset con esquema distinto cargue sin romperse."""

import dataclasses
import tempfile

import engine as E
import presets
from sequencer import Sequencer


def fresh():
    eng = E.Engine()
    return eng, Sequencer(eng)


def main():
    tmp = tempfile.mkdtemp(prefix="synth-presets-")

    # --- 1) armar un estado distinto del de fábrica ---
    eng, seq = fresh()
    eng.instruments[0].params.wave = E.SQUARE
    eng.instruments[0].params.cutoff = 1234.5
    eng.instruments[0].params.lfo_dest = E.LFO_FILTER
    eng.instruments[0].params.lfo_depth = 0.42
    eng.instruments[0].name = "mi-lead"
    eng.instruments[3].params.drum_drop = 6.5
    eng.instruments[0].layer_on = True             # capa B del lead, activa...
    eng.instruments[0].params_b.wave = E.TRI       # ...y con patch propio
    eng.instruments[0].params_b.cutoff = 777.0
    eng.instruments[0].params.eq[2] = -6.0         # el eq (lista) viaja por disco
    eng.instruments[0].params_b.eq[5] = 9.0
    eng.sel = 2
    seq.bpm = 137
    seq.grid[0][0] = 60
    seq.grid[0][4] = 64
    seq.grid[3][2] = 36

    path = presets.save("Mi Sonido Raro", eng, seq, directory=tmp)
    assert path.endswith("mi-sonido-raro.json"), f"slug raro: {path}"

    listed = presets.available(directory=tmp)
    assert [d["label"] for d in listed] == ["Mi Sonido Raro"], listed
    assert listed[0]["key"] == "mi-sonido-raro"

    # --- 2) cargar en un motor limpio y comparar ---
    eng2, seq2 = fresh()
    data = presets.load("mi-sonido-raro", eng2, seq2, directory=tmp)
    assert data["name"] == "Mi Sonido Raro"
    assert eng2.instruments[0].params.wave == E.SQUARE
    assert abs(eng2.instruments[0].params.cutoff - 1234.5) < 1e-6
    assert eng2.instruments[0].params.lfo_dest == E.LFO_FILTER
    assert abs(eng2.instruments[0].params.lfo_depth - 0.42) < 1e-6
    assert eng2.instruments[0].name == "mi-lead"
    assert abs(eng2.instruments[3].params.drum_drop - 6.5) < 1e-6
    assert eng2.instruments[0].layer_on is True
    assert eng2.instruments[0].params_b.wave == E.TRI
    assert abs(eng2.instruments[0].params_b.cutoff - 777.0) < 1e-6
    assert abs(eng2.instruments[0].params.eq[2] + 6.0) < 1e-6
    assert abs(eng2.instruments[0].params_b.eq[5] - 9.0) < 1e-6
    assert eng2.sel == 2
    assert seq2.bpm == 137
    assert seq2.grid[0][0] == 60 and seq2.grid[0][4] == 64 and seq2.grid[3][2] == 36
    assert seq2.grid[1][0] is None
    print("ida y vuelta por disco: ok")

    # --- 3) round-trip exacto de TODOS los campos de Params ---
    eng3, seq3 = fresh()
    presets.restore(eng3, seq3, presets.snapshot(eng, seq))
    for i, ins in enumerate(eng.instruments):
        a = dataclasses.asdict(ins.params)
        b = dataclasses.asdict(eng3.instruments[i].params)
        assert a == b, f"instrumento {i} difiere: {a} != {b}"
        if ins.params_b is not None:               # la capa B también, campo a campo
            a = dataclasses.asdict(ins.params_b)
            b = dataclasses.asdict(eng3.instruments[i].params_b)
            assert a == b, f"capa B del instrumento {i} difiere: {a} != {b}"
    print("todos los campos de Params: ok")

    # --- 4) a prueba del futuro: clave de más, clave de menos ---
    eng4, seq4 = fresh()
    base_release = eng4.instruments[0].params.amp_release
    eng4.instruments[0].layer_on = True    # una foto vieja (sin capa) la apaga
    presets.restore(eng4, seq4, {
        "instruments": [{"name": "x", "params": {
            "wave": E.TRI,
            "campo_inexistente": 99,      # se ignora
            # falta amp_release -> queda el por defecto
        }}],
        "sequencer": {"bpm": 90, "grid": [[60]]},
    })
    assert eng4.instruments[0].params.wave == E.TRI
    assert eng4.instruments[0].params.amp_release == base_release
    assert eng4.instruments[0].layer_on is False, "la foto vieja no apagó la capa"
    assert seq4.bpm == 90 and seq4.grid[0][0] == 60
    print("esquema viejo/raro carga sin romperse: ok")

    # --- 5) borrar ---
    presets.delete("mi-sonido-raro", directory=tmp)
    assert presets.available(directory=tmp) == []
    print("borrar: ok")

    print("OK -> presets")


if __name__ == "__main__":
    main()
