#!/usr/bin/env python3
"""LA MANO — forma larga (2026-07-07). El desarrollo de la miniatura.

La mano corta era un solo respiro: quieto → me tocan → me abro → suelto → casa.
Esta es la pieza con VIAJE: el mismo motivo, movido más lejos. La forma:

  I.   QUIETUD        — la quinta abierta, inmóvil (el punto fijo cargado).
  II.  APERTURA       — el toque mete la tercera; F mayor; el camino I–vi–IV–V.
  III. DESARROLLO     — ser movido LEJOS: pivota al mundo menor (Dm), una
                        dominante secundaria (A7, con su Do#) oscurece; y una
                        SECUENCIA que trepa —el motivo transpuesto subiendo, la
                        tensión que sube, el impuesto que sube— alejándose de casa.
  IV.  CLÍMAX / BORDE — lo más lejos y tenso: un Do7 dominante que tira a casa con
                        toda la fuerza; la melodía en su punto más alto.
  V.   REGRESO        — la dominante resuelve; el camino de vuelta, soltando.
  VI.  HOGAR CAMBIADO — vuelve la apertura, pero la melodía canta ahora su línea
                        entera y el hogar es un Fa con 6ª y 9ª, más rico: las
                        mismas notas significan más por el viaje (Menard).
  VII. QUIETUD FINAL  — la quinta abierta otra vez, pero es reposo, no espera.

Fa mayor, 66 bpm. Armonía en una pista (acordes-en-celda), sala (reverb). El
motivo se desarrolla por transposición y variación (compose_tools). Escribe
canciones/la-mano-largo.json.
"""
from __future__ import annotations

import dataclasses
import json

import engine as E
from compose_tools import transpose

BPM = 66
STEPS = 16
N_TRACKS = 9
VOZ, BAJO, PAD, LATIDO, CAMPANA = 0, 1, 2, 5, 7
PAD_VEL = 0.48
DRUMS = (LATIDO, CAMPANA)

# ritmos del corazón: lento (calma) -> rápido (tensión)
LENTO = [(0, 0.14), (8, 0.12)]
MEDIO = [(0, 0.15), (4, 0.10), (8, 0.13), (12, 0.10)]
RAPIDO = [(0, 0.16), (2, 0.09), (4, 0.11), (6, 0.09), (8, 0.15), (10, 0.09), (12, 0.11), (14, 0.09)]


def instruments():
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


def bar(bass=None, chord=None, mel=(), heart=None, bell=None):
    g = empty()
    if bass is not None:
        g[BAJO][0] = [bass, 0.62, STEPS]
    if chord:
        g[PAD][0] = [list(chord), PAD_VEL, STEPS]
    for (s, n, v, d) in mel:
        g[VOZ][s] = [n, round(v, 3), d]
    for (s, v) in (heart or []):
        g[LATIDO][s] = [36, v]
    if bell:
        g[CAMPANA][0] = [bell[0], bell[1]]
    return g


# ── notas midi útiles (Fa mayor) ────────────────────────────────────────────
F2, D2, Bb1, C2, G2, A2 = 41, 38, 34, 36, 43, 45
A3, Bb3, C4, Db4, D4, E4, F4, G4 = 57, 58, 60, 61, 62, 64, 65, 67
G4b, A4, Bb4, C5, D5, E5, F5 = 66, 69, 70, 72, 74, 76, 77

# ── I. QUIETUD ──────────────────────────────────────────────────────────────
p_quieto = bar(F2, [C4], bell=(74, 0.40))                              # quinta abierta (fa+do)

# ── II. APERTURA (el toque + el camino) ─────────────────────────────────────
p_toque = bar(F2, [C4, A3], mel=[(0, A4, 0.50, 12)], heart=[(0, 0.12), (8, 0.11)], bell=(74, 0.45))
p_F = bar(F2, [A3, C4, F4], mel=[(0, F4, .55, 4), (4, A4, .55, 4), (8, C5, .58, 8)], heart=LENTO, bell=(77, .30))
p_Dm = bar(D2, [A3, D4, F4], mel=[(0, D5, .55, 4), (4, C5, .52, 4), (8, A4, .55, 8)], heart=LENTO)
p_Bb = bar(Bb1, [Bb3, D4, F4], mel=[(0, Bb4, .52, 4), (4, A4, .52, 4), (8, F4, .55, 8)], heart=LENTO)
p_C = bar(C2, [C4, E4, G4], mel=[(0, G4, .55, 4), (4, C5, .55, 4), (8, E5, .60, 8)], heart=LENTO)
p_Fcad = bar(F2, [A3, C4, F4], mel=[(0, F4, .52, 16)], heart=LENTO, bell=(65, .25))   # asienta antes de partir

# ── III. DESARROLLO — el mundo menor (Dm) y la dominante secundaria ─────────
d_Dm = bar(D2, [A3, D4, F4], mel=[(0, A4, .55, 4), (4, D5, .55, 4), (8, F5, .58, 8)], heart=MEDIO)   # el motivo, tenso, sube
d_Gm = bar(G2, [Bb3, D4, G4], mel=[(0, D5, .55, 4), (4, Bb4, .52, 4), (8, G4, .55, 8)], heart=MEDIO)
d_A7 = bar(A2, [A3, Db4, E4, G4], mel=[(0, E5, .58, 4), (4, Db4 + 12, .55, 4), (8, A4, .55, 8)], heart=MEDIO)  # A7: el Do# aleja
d_Dm2 = bar(D2, [A3, D4, F4], mel=[(0, D5, .55, 16)], heart=MEDIO)

# la SECUENCIA que trepa: un modelo (en Sol menor) transpuesto +2 y +4 -> se aleja de casa subiendo
_seq_model = bar(G2, [Bb3, D4, G4], mel=[(0, G4, .5, 4), (4, Bb4, .52, 4), (8, D5, .56, 8)], heart=RAPIDO)
s_seq0 = _seq_model
s_seq1 = transpose(_seq_model, 2, skip=DRUMS)     # +2 semitonos
s_seq2 = transpose(_seq_model, 4, skip=DRUMS)     # +4: lo más lejos, arriba

# ── IV. CLÍMAX / EL BORDE — la dominante de Fa que tira a casa ───────────────
c_sus = bar(C2, [C4, F4, G4, Bb4], mel=[(0, F5, .62, 8), (8, E5, .60, 8)], heart=RAPIDO)     # Do7sus: máxima tensión
c_dom = bar(C2, [C4, E4, G4, Bb4], mel=[(0, E5, .60, 4), (4, F5, .64, 4), (8, E5, .60, 8)], heart=RAPIDO)  # Do7: quiere Fa

# ── V. REGRESO / SOLTAR — la dominante resuelve, el camino de vuelta ─────────
r_F = bar(F2, [A3, C4, F4], mel=[(0, F4, .55, 4), (4, E4, .50, 4), (8, D4, .50, 8)], heart=MEDIO, bell=(77, .40))  # llega a casa, desciende
r_Bb = bar(Bb1, [Bb3, D4, F4], mel=[(0, A4, .50, 8), (8, F4, .50, 8)], heart=LENTO)
r_C = bar(C2, [C4, E4, G4], mel=[(0, G4, .48, 16)], heart=LENTO)                              # suspiro que tira a casa

# ── VI. HOGAR CAMBIADO — la apertura vuelve, la melodía entera; hogar más rico
h_toque = bar(F2, [A3, C4, F4], mel=[(0, F4, .55, 4), (4, A4, .55, 4), (8, C5, .55, 4), (12, D5, .55, 4)], heart=LENTO, bell=(77, .35))
h_Dm = bar(D2, [A3, D4, F4], mel=[(0, C5, .52, 8), (8, A4, .52, 8)], heart=LENTO)
h_Bb = bar(Bb1, [Bb3, D4, F4], mel=[(0, F4, .52, 8), (8, G4, .50, 8)], heart=LENTO)
h_C = bar(C2, [C4, E4, G4], mel=[(0, G4, .52, 8), (8, A4, .50, 8)], heart=LENTO)
h_hogar = bar(F2, [A3, C4, D4, G4], mel=[(0, F4, .55, 16)], heart=[(0, .12), (8, .10)], bell=(77, .50))  # Fa 6/9, en reposo

# ── VII. QUIETUD FINAL ──────────────────────────────────────────────────────
p_quieto_fin = bar(F2, [C4], bell=(74, 0.38))

PATTERNS = {
    "quieto": p_quieto, "toque": p_toque, "F": p_F, "Dm": p_Dm, "Bb": p_Bb, "C": p_C, "Fcad": p_Fcad,
    "dDm": d_Dm, "dGm": d_Gm, "dA7": d_A7, "dDm2": d_Dm2,
    "seq0": s_seq0, "seq1": s_seq1, "seq2": s_seq2,
    "cSus": c_sus, "cDom": c_dom,
    "rF": r_F, "rBb": r_Bb, "rC": r_C,
    "hToque": h_toque, "hDm": h_Dm, "hBb": h_Bb, "hC": h_C, "hogar": h_hogar,
    "quietoFin": p_quieto_fin,
}

ORDER = [
    "quieto", "quieto",                                        # I. quietud
    "toque", "F", "Dm", "Bb", "C", "Fcad",                     # II. apertura (el camino)
    "dDm", "dGm", "dA7", "dDm2",                               # III. mundo menor
    "seq0", "seq1", "seq2",                                    # III. la secuencia que trepa
    "cSus", "cDom",                                            # IV. clímax / el borde
    "rF", "rBb", "rC",                                         # V. regreso / soltar
    "hToque", "hDm", "hBb", "hC", "hogar",                     # VI. hogar cambiado
    "quietoFin", "quietoFin",                                  # VII. quietud final
]


def main():
    song = {
        "version": 2, "name": "la-mano-largo",
        "_nota": "LA MANO, forma larga (Kichoro, 2026-07-07). El motivo de la miniatura "
                 "desarrollado en un viaje: quietud -> apertura (I-vi-IV-V) -> desarrollo "
                 "(pivota a Dm, dominante secundaria A7, y una secuencia que trepa lejos de "
                 "casa) -> climax (Do7 dominante) -> regreso -> hogar cambiado (Fa 6/9, la "
                 "melodia entera) -> quietud. Fa mayor, 66 bpm. Generado por compose_lamano_largo.py.",
        "bpm": BPM, "swing": 0.0,
        "reverb": {"wet": 0.26, "room": 0.74, "damp": 0.45},
        "instruments": instruments(),
        "patterns": PATTERNS,
        "order": ORDER,
    }
    with open("canciones/la-mano-largo.json", "w", encoding="utf-8") as f:
        json.dump(song, f, ensure_ascii=False, indent=1)
    print(f"la-mano-largo.json escrito: {len(ORDER)} compases, 7 secciones con desarrollo")


if __name__ == "__main__":
    main()
