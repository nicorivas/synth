#!/usr/bin/env python3
"""LA MANO, re-voiceada con acordes-en-celda (2026-07-07).

Misma pieza que compose_lamano.py —mismas notas, mismo bajo/voz/latido/campana,
mismo arreglo—, pero la ARMONÍA entera va ahora en UNA sola pista (2 = pad) como
un acorde por celda `[[notas], vel, dur]`, en vez de repartir la tríada en tres
pistas (PAD1/PAD2/PAD3, que además quemaban el kick y el snare). Resultado: el
kick y el snare quedan LIBRES otra vez, y el compose es más simple.

Honestidad: los tres pads originales eran tres TIMBRES distintos (dos triángulos
+ un seno arriba) a volúmenes distintos; aquí es un solo timbre para las tres
notas, así que suena *casi* igual, no idéntico. Los voicings (las notas exactas)
se preservan tal cual para no cambiar la armonía. Escribe canciones/la-mano-acordes.json.
"""
from __future__ import annotations

import dataclasses
import json

import engine as E

BPM = 66
SWING = 0.0
STEPS = 16
N_TRACKS = 9

VOZ, BAJO, PAD, LATIDO, CAMPANA = 0, 1, 2, 5, 7
PAD_VEL = 0.48                      # una sola velocity para el acorde (mezcla de las 3 viejas)


def instruments():
    """Un solo pad de acorde (triángulo cálido) en la pista 2. El kick (3) y el
    snare (4) vuelven a ser percusión: ya no hace falta quemarlos en pads."""
    insts = E.default_instruments()
    P = [dataclasses.asdict(i.params) for i in insts]
    nm = [i.name for i in insts]
    P[VOZ].update(wave=E.SINE, cutoff=2800.0, amp_attack=0.12, amp_decay=0.30,
                  amp_sustain=0.85, amp_release=0.50, volume=0.80,
                  lfo_dest=E.LFO_PITCH, lfo_shape=E.SINE, lfo_rate=5.0, lfo_depth=0.06)
    nm[VOZ] = "voz"
    P[BAJO].update(wave=E.TRI, cutoff=620.0, amp_attack=0.06, amp_decay=0.40,
                   amp_sustain=0.90, amp_release=0.80, volume=0.85)
    nm[BAJO] = "bajo"
    # el pad de acorde: triángulo con detune, filtro que respira lento. El volumen
    # (0.44) compensa que ahora una pista suma las 3 voces que antes iban en 3 pads.
    P[PAD].update(wave=E.TRI, detune=8.0, cutoff=1600.0, amp_attack=0.45,
                  amp_decay=0.60, amp_sustain=0.85, amp_release=1.7, volume=0.44,
                  lfo_dest=E.LFO_FILTER, lfo_shape=E.SINE, lfo_rate=0.14, lfo_depth=0.30)
    nm[PAD] = "pad-acorde"
    P[LATIDO].update(kind=E.INST_DRUM, drum_noise=0.05, drum_drop=3.0, drum_pdecay=0.05,
                     drum_bright=1000.0, drum_click=0.0, amp_decay=0.28, amp_release=0.10,
                     volume=0.90)
    nm[LATIDO] = "latido"
    P[CAMPANA].update(drum_drop=0.0, drum_noise=0.05, drum_noise_mode=E.NOISE_LP,
                      drum_bright=4200.0, drum_click=0.10, amp_attack=0.001,
                      amp_decay=0.60, amp_release=0.80, volume=1.10)
    nm[CAMPANA] = "campana"
    return [{"name": nm[i], "params": P[i]} for i in range(len(insts))]


def empty():
    return [[None] * STEPS for _ in range(N_TRACKS)]


def chord(g, bass, *notes):
    """El bajo + el acorde ENTERO en una celda de la pista PAD (antes: 3 pistas)."""
    g[BAJO][0] = [bass, 0.62, STEPS]
    voiced = [n for n in notes if n is not None]
    if voiced:
        g[PAD][0] = [voiced, PAD_VEL, STEPS]


def heart(g, v0=0.15, v8=0.13):
    g[LATIDO][0] = [36, v0]
    g[LATIDO][8] = [36, v8]


def bell(g, note=74, vel=0.42):
    g[CAMPANA][0] = [note, vel]


def melody(g, notes):
    for step, n, v, d in notes:
        g[VOZ][step] = [n, round(v, 3), d]


# --- los patrones (idénticos en notas a compose_lamano.py) ---
def p_quieto():
    g = empty(); chord(g, 41, 60); bell(g, 74, 0.40); return g            # quinta abierta

def p_toque():
    g = empty(); chord(g, 41, 60, 57); bell(g, 74, 0.45); heart(g, 0.12, 0.11)
    melody(g, [(0, 69, 0.50, 12)]); return g                             # entra la tercera + voz

def p_F():
    g = empty(); chord(g, 41, 57, 60, 65); heart(g); bell(g, 77, 0.30)
    melody(g, [(0, 65, 0.55, 4), (4, 69, 0.55, 4), (8, 72, 0.58, 8)]); return g

def p_Dm():
    g = empty(); chord(g, 38, 57, 62, 65); heart(g)
    melody(g, [(0, 74, 0.55, 4), (4, 72, 0.52, 4), (8, 69, 0.55, 8)]); return g

def p_Bb():
    g = empty(); chord(g, 34, 58, 62, 65); heart(g)
    melody(g, [(0, 70, 0.52, 4), (4, 69, 0.52, 4), (8, 65, 0.55, 8)]); return g

def p_C():
    g = empty(); chord(g, 36, 60, 64, 67); heart(g)
    melody(g, [(0, 67, 0.55, 4), (4, 72, 0.55, 4), (8, 76, 0.60, 8)]); return g

def p_soltarBb():
    g = empty(); chord(g, 34, 58, 62, 65); heart(g, 0.13, 0.11)
    melody(g, [(0, 69, 0.50, 8), (8, 65, 0.50, 8)]); return g

def p_soltarC():
    g = empty(); chord(g, 36, 60, 64, 67); heart(g, 0.12, 0.10)
    melody(g, [(0, 67, 0.48, 16)]); return g

def p_hogar():
    g = empty(); chord(g, 41, 57, 60, 67); heart(g, 0.12, 0.10); bell(g, 77, 0.50)
    melody(g, [(0, 65, 0.55, 16)]); return g                             # Fa add9, reposo


PATTERNS = {
    "quieto": p_quieto(), "toque": p_toque(),
    "F": p_F(), "Dm": p_Dm(), "Bb": p_Bb(), "C": p_C(),
    "soltarBb": p_soltarBb(), "soltarC": p_soltarC(), "hogar": p_hogar(),
}
ORDER = ["quieto", "quieto", "toque", "F", "Dm", "Bb", "C",
         "soltarBb", "soltarC", "hogar", "quieto"]


def main():
    song = {
        "version": 2, "name": "la-mano-acordes",
        "_nota": "LA MANO (re-voiceada con acordes-en-celda, 2026-07-07) — misma pieza "
                 "que la-mano.json pero la armonia va en UNA pista (2=pad) como acorde por "
                 "celda, no en 3 pads. Kick y snare quedan libres. Mismas notas y arreglo. "
                 "Generado por compose_lamano_acordes.py.",
        "bpm": BPM, "swing": SWING,
        "reverb": {"wet": 0.26, "room": 0.74, "damp": 0.45},   # una sala cálida y suave
        "instruments": instruments(),
        "patterns": PATTERNS,
        "order": ORDER,
    }
    with open("canciones/la-mano-acordes.json", "w", encoding="utf-8") as f:
        json.dump(song, f, ensure_ascii=False, indent=1)
    print(f"la-mano-acordes.json escrito: armonia en 1 pista (antes 3), kick/snare libres")


if __name__ == "__main__":
    main()
