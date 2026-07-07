#!/usr/bin/env python3
"""Acordes en una celda: una celda `[[n1,n2,...], vel, dur]` suena como un acorde
en UNA sola pista. Verifica las tres capas (split, parse, teoría) y, sobre todo,
end-to-end por FFT: que las tres alturas del acorde suenen a la vez.

No es pytest: correr con `uv run python test_chords.py`."""
from __future__ import annotations

import dataclasses

import numpy as np

import engine as E
import render
import theory as T
from presets import _coerce_cell
from sequencer import _split_cell


def test_split_cell():
    # compat: notas sueltas siguen igual, pero ahora `notas` es SIEMPRE una lista
    assert _split_cell(None) == (None, 0.0, 1)
    assert _split_cell(60) == ([60], 1.0, 1)
    assert _split_cell([60, 0.5]) == ([60], 0.5, 1)
    assert _split_cell([60, 0.5, 8]) == ([60], 0.5, 8)
    # acorde
    assert _split_cell([[60, 64, 67], 0.6, 16]) == ([60, 64, 67], 0.6, 16)
    assert _split_cell([[60, 64, 67]]) == ([60, 64, 67], 1.0, 1)
    print("ok  _split_cell (acorde + compat notas sueltas)")


def test_coerce_cell():
    # lo viejo intacto
    assert _coerce_cell(60) == 60
    assert _coerce_cell([60, 0.5]) == [60, 0.5]
    assert _coerce_cell([60, 0.5, 8]) == [60, 0.5, 8]
    # acorde preservado + clamp por nota + vel/dur
    assert _coerce_cell([[60, 64, 67], 0.6, 16]) == [[60, 64, 67], 0.6, 16]
    assert _coerce_cell([[200, -5], 0.5]) == [[108, 0], 0.5]
    print("ok  _coerce_cell (acorde preservado, clamp por nota)")


def test_theory_bridge():
    # I de Do mayor = Do Mi Sol ; V7 de Do = Sol Si Re Fa
    assert T.chord_cell(1, 0, "mayor", octave=4) == [[60, 64, 67], 1.0, 1]
    assert T.chord_cell(5, 0, "mayor", octave=4, sevenths=True, vel=0.5, dur=8) \
        == [[67, 71, 74, 77], 0.5, 8]
    print("ok  theory.chord_cell (armonía por grado -> celda)")


def _sine_song(chord_cell):
    """Una canción mínima: la pista 0 (seno puro) toca UN acorde sostenido."""
    insts = E.default_instruments()
    P = [dataclasses.asdict(i.params) for i in insts]
    P[0].update(wave=E.SINE, cutoff=8000.0, amp_attack=0.005, amp_decay=0.1,
                amp_sustain=0.9, amp_release=0.05, volume=0.7)
    grid = [[None] * 4 for _ in range(len(insts))]
    grid[0][0] = chord_cell                       # el acorde, en una sola pista
    return {"version": 2, "name": "t", "bpm": 120, "swing": 0.0,
            "instruments": [{"name": insts[i].name, "params": P[i]} for i in range(len(insts))],
            "patterns": {"A": grid}, "order": ["A"]}


def test_chord_sounds_end_to_end():
    """La prueba que importa: renderizar un acorde y comprobar por FFT que las
    tres alturas están presentes a la vez (no puedo oírlo; lo 'veo' en el espectro)."""
    sig = render.render(_sine_song([[60, 64, 67], 0.85, 4]), seconds=1.0)  # Do mayor
    win = sig * np.hanning(len(sig))
    S = np.abs(np.fft.rfft(win))
    freqs = np.fft.rfftfreq(len(sig), 1.0 / E.SR)
    top = S.max()

    def peak_at(f, tol=8.0):
        band = (freqs > f - tol) & (freqs < f + tol)
        return S[band].max() if band.any() else 0.0

    for midi, name in [(60, "Do4"), (64, "Mi4"), (67, "Sol4")]:
        f = E.midi_to_freq(midi)
        assert peak_at(f) > 0.15 * top, f"falta la fundamental {name} ({f:.1f} Hz)"
    # y una nota que NO está en el acorde no debería tener pico fuerte
    assert peak_at(E.midi_to_freq(62)) < 0.15 * top, "sonó una nota fuera del acorde (Re4)"
    print("ok  FFT end-to-end: Do+Mi+Sol suenan a la vez en UNA pista, sin Re")


if __name__ == "__main__":
    test_split_cell()
    test_coerce_cell()
    test_theory_bridge()
    test_chord_sounds_end_to_end()
    print("\nTODO OK — acordes en una celda funcionan de punta a punta")
