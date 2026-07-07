#!/usr/bin/env python3
"""DEMO de acordes-en-celda: toda la ARMONÍA en UNA sola pista.

Antes, para vocear un triada había que gastar 3 pistas (en «La mano» reconvertí
kick y snare en pads sólo para eso). Ahora una celda lleva el acorde entero: la
pista 2 (pad) carga cada triada diatónica con `theory.chord_cell(grado, ...)`.
I–V–vi–IV en Do mayor, cálido. Escribe canciones/acordes.json.
"""
from __future__ import annotations

import dataclasses
import json

import engine as E
import theory as T

TONIC, MODE = 0, "mayor"          # Do mayor
BPM = 72
STEPS = 16
N_TRACKS = 9
VOZ, BAJO, PAD, LATIDO = 0, 1, 2, 5


def instruments():
    insts = E.default_instruments()
    P = [dataclasses.asdict(i.params) for i in insts]
    nm = [i.name for i in insts]
    P[VOZ].update(wave=E.SINE, cutoff=2800.0, amp_attack=0.10, amp_decay=0.30,
                  amp_sustain=0.85, amp_release=0.40, volume=0.75,
                  lfo_dest=E.LFO_PITCH, lfo_shape=E.SINE, lfo_rate=5.0, lfo_depth=0.05)
    nm[VOZ] = "voz"
    P[BAJO].update(wave=E.TRI, cutoff=600.0, amp_attack=0.05, amp_decay=0.40,
                   amp_sustain=0.90, amp_release=0.70, volume=0.80)
    nm[BAJO] = "bajo"
    P[PAD].update(wave=E.TRI, detune=7.0, cutoff=1700.0, amp_attack=0.35,
                  amp_decay=0.60, amp_sustain=0.85, amp_release=1.4, volume=0.50,
                  lfo_dest=E.LFO_FILTER, lfo_shape=E.SINE, lfo_rate=0.15, lfo_depth=0.30)
    nm[PAD] = "pad-acorde"
    P[LATIDO].update(kind=E.INST_DRUM, drum_noise=0.05, drum_drop=3.0, drum_pdecay=0.05,
                     drum_bright=1100.0, drum_click=0.0, amp_decay=0.28, amp_release=0.10,
                     volume=0.85)
    nm[LATIDO] = "latido"
    return [{"name": nm[i], "params": P[i]} for i in range(len(insts))]


def empty():
    return [[None] * STEPS for _ in range(N_TRACKS)]


def bar(degree, melody):
    g = empty()
    # LA ARMONÍA ENTERA EN UNA PISTA: el acorde diatónico del grado, sostenido
    g[PAD][0] = T.chord_cell(degree, TONIC, MODE, octave=4, vel=0.5, dur=STEPS)
    root = T.diatonic_chord(degree, TONIC, MODE, octave=4)[0]
    g[BAJO][0] = [root - 24, 0.6, STEPS]           # el bajo, dos octavas bajo la raíz
    g[LATIDO][0] = [36, 0.14]; g[LATIDO][8] = [36, 0.12]
    for step, n, v, d in melody:
        g[VOZ][step] = [n, v, d]
    return g


PATTERNS = {
    "I":  bar(1, [(0, 72, 0.55, 4), (4, 76, 0.55, 4), (8, 79, 0.58, 8)]),   # Do
    "V":  bar(5, [(0, 74, 0.52, 4), (8, 71, 0.50, 8)]),                     # Sol
    "vi": bar(6, [(0, 72, 0.52, 4), (4, 69, 0.50, 4), (8, 72, 0.55, 8)]),   # Lam
    "IV": bar(4, [(0, 77, 0.55, 8), (8, 72, 0.55, 8)]),                     # Fa
}
ORDER = ["I", "V", "vi", "IV", "I", "V", "vi", "IV"]


def main():
    song = {
        "version": 2, "name": "acordes",
        "_nota": "DEMO acordes-en-celda: TODA la armonia en UNA pista (2=pad) con "
                 "theory.chord_cell. I-V-vi-IV en Do mayor, 72 bpm. Antes esto pedia "
                 "3 pistas de pad; ahora una celda lleva el acorde entero. Generado "
                 "por compose_acordes.py.",
        "bpm": BPM, "swing": 0.0,
        "instruments": instruments(),
        "patterns": PATTERNS,
        "order": ORDER,
    }
    with open("canciones/acordes.json", "w", encoding="utf-8") as f:
        json.dump(song, f, ensure_ascii=False, indent=1)
    print(f"acordes.json escrito: {len(ORDER)} compases; armonia en 1 pista (chord_cell)")


if __name__ == "__main__":
    main()
