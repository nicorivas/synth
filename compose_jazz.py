#!/usr/bin/env python3
"""Compone una pieza de jazz USANDO la teoría, y la escribe a canciones/jazz.json.

Un ii–V–I–VI (Dm7 · G7 · Cmaj7 · A7♭9) en Do. El reparto aprovecha el límite de
3 voces melódicas igual que un trío de jazz:

  · bajo (1)  — camina la fundamental en negras, con nota de paso cromática.
  · lead (0) + pad (2) — sostienen las dos voces guía (la 3ª y la 7ª, las notas
    que definen cada acorde), moviéndose por el camino más corto (medio tono o
    nota común): la conducción de voces que hace que un ii–V–I suene "líquido".
  · batería — patrón de plato con swing.

Cada paso de la grilla es una corchea (no un 16avo), así el swing atrasa el
contratiempo —el balanceo del jazz— en vez de un 16avo.
"""
from __future__ import annotations

import json

import theory as T

PROG = T.turnaround(0)         # Do mayor: Dm7 · G7 · Cmaj7 · A7♭9
BPM = 68                       # cada paso = corchea  ->  negra ≈ 136
SWING = 0.38                   # pocket de tresillo (swing de corcheas)
STEPS_PER_BAR = 8              # 8 corcheas = 1 compás de 4/4
N_TRACKS = 7                   # 0 lead,1 bajo,2 pad,3 kick,4 snare,5 hat,6 hat-open

RIDE = {0: 0.6, 2: 0.6, 3: 0.45, 4: 0.6, 6: 0.6, 7: 0.45}   # plato "spang-a-lang"


def nearest(pc: int, ref: int) -> int:
    """La nota midi de clase de altura `pc` más cercana a `ref` (conducción suave)."""
    base = ref - (ref % 12) + (pc % 12)
    return min((base - 12, base, base + 12), key=lambda m: abs(m - ref))


def guide_voices(prog, start=(65, 60)):
    """Dos líneas de voces guía con movimiento mínimo: en cada acorde reparte su
    3ª y su 7ª entre las dos voces eligiendo la asignación que menos se mueve.
    De ahí sale la conducción por medios tonos y notas comunes del ii–V–I."""
    a, b = start
    out = []
    for root, qual in prog:
        g0, g1 = T.guide_tones(root, qual)
        optA = (nearest(g0, a), nearest(g1, b))
        optB = (nearest(g1, a), nearest(g0, b))
        cost = lambda o: abs(o[0] - a) + abs(o[1] - b)
        a, b = optA if cost(optA) <= cost(optB) else optB
        out.append((a, b))
    return out


def walking_bass(prog, ref=38):
    """Bajo caminante: fundamental, 3ª y 5ª del acorde, y una nota de paso
    cromática que cae sobre la fundamental del compás siguiente."""
    lines = []
    for i, (root, qual) in enumerate(prog):
        ivs = T.CHORD_QUALITIES[qual]
        r = nearest(root, ref); ref = r
        third, fifth = r + ivs[1], r + ivs[2]
        nroot = prog[(i + 1) % len(prog)][0]
        target = nearest(nroot, fifth)
        approach = min((target - 1, target + 1), key=lambda m: abs(m - fifth))
        lines.append([r, third, fifth, approach])
    return lines


def base_grid(n_tracks=N_TRACKS):
    """Solo la base armónica del ii–V–I–VI sobre 4 compases: bajo caminante (1) y
    comping de voces guía (lead 0 + pad 2). Sin batería —para reusarla (p. ej. un
    solo de batería sobre la misma progresión)."""
    n = len(PROG) * STEPS_PER_BAR
    grid = [[None] * n for _ in range(n_tracks)]
    voices, bass = guide_voices(PROG), walking_bass(PROG)
    for b in range(len(PROG)):
        o = b * STEPS_PER_BAR
        va, vb = voices[b]
        grid[0][o] = [va, 0.5, STEPS_PER_BAR]      # lead = voz guía A, sostenida el compás
        grid[2][o] = [vb, 0.5, STEPS_PER_BAR]      # pad  = voz guía B
        for j, note in enumerate(bass[b]):         # bajo caminante en negras
            grid[1][o + j * 2] = [note, 0.8 if j == 0 else 0.68]
    return grid


def build_grid():
    grid = base_grid()
    for b in range(len(PROG)):
        o = b * STEPS_PER_BAR
        for st, v in RIDE.items():                 # plato con swing
            grid[5][o + st] = [54, v]
        grid[3][o] = [36, 0.25]                    # bombo: una pluma en el 1
        grid[4][o + 2] = [50, 0.3]                 # caja suave en el 2...
        grid[4][o + 6] = [50, 0.3]                 # ...y en el 4
    return grid


def main():
    labels = " · ".join(T.chord_symbol(r, q) for r, q in PROG)
    song = {
        "version": 2, "name": "jazz",
        "_nota": f"ii-V-I-VI en Do ({labels}). Bajo caminante (1), comping de voces "
                 f"guia 3a/7a con conduccion suave (lead 0 + pad 2), bateria con "
                 f"swing. Cada paso es una corchea. Generado por compose_jazz.py.",
        "bpm": BPM, "swing": SWING,
        "patterns": {"tema": build_grid()},
        "order": ["tema"],
    }
    with open("canciones/jazz.json", "w", encoding="utf-8") as f:
        json.dump(song, f, ensure_ascii=False, indent=1)
    print(f"jazz.json escrito: {labels}   ({BPM} bpm, swing {SWING})")


if __name__ == "__main__":
    main()
