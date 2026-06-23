#!/usr/bin/env python3
"""Un tema largo de jazz con la misma base y progresión que compose_jazz, pero
como un SOLO DE BATERÍA: el bajo caminante y el comping de voces guía mantienen
el ii–V–I–VI debajo (la forma sigue corriendo), y por encima el baterista toma el
control con intensidad creciente —desde el plato susurrado hasta una explosión
por todo el kit con toms.

Reusa la base armónica de compose_jazz (`base_grid`) y le superpone capas de
batería. La estructura larga la arma el arreglo (`order`): expone el tema, el
baterista cambia (trading) y construye, estalla, y vuelve a casa.

Escribe canciones/jazz-solo.json.
"""
from __future__ import annotations

import json

import compose_jazz as J
import theory as T

N = 9                                   # kit con toms: 9 pistas
BAR = J.STEPS_PER_BAR                    # 8 corcheas por compás
KICK, SNARE, HAT, HOPEN, TOMH, TOML = 3, 4, 5, 6, 7, 8
DRUM_NOTE = {KICK: 36, SNARE: 50, HAT: 54, HOPEN: 54, TOMH: 50, TOML: 43}


def lay(g, hits, base=0):
    """Coloca (paso, pista, velocity) en la grilla, afinando cada tambor a su nota."""
    for st, tr, v in hits:
        g[tr][base + st] = [DRUM_NOTE[tr], min(1.0, round(v, 3))]


# --- vocabulario de la batería, por compás (8 corcheas; beats en 0,2,4,6) ---

HEAD = [(0, HAT, .5), (2, HAT, .5), (3, HAT, .4), (4, HAT, .5), (6, HAT, .5),
        (7, HAT, .4), (0, KICK, .25), (2, SNARE, .3), (6, SNARE, .3)]

S1 = [(0, HAT, .45), (2, HAT, .45), (4, HAT, .45), (6, HAT, .45), (0, KICK, .3),
      (3, SNARE, .5), (5, SNARE, .25), (7, SNARE, .45)]                 # caja conversando
S1_FILL = [(0, SNARE, .5), (1, SNARE, .3), (2, TOMH, .55), (3, TOMH, .5),
           (4, TOML, .6), (5, TOML, .55), (6, TOML, .65), (7, KICK, .5)]  # fill de toms

S2 = [(0, KICK, .6), (1, TOMH, .4), (2, SNARE, .55), (3, TOMH, .5),     # vuelta al kit
      (4, TOML, .55), (5, SNARE, .3), (6, KICK, .45), (7, TOML, .5)]
S2_FILL = [(0, SNARE, .55), (1, SNARE, .45), (2, SNARE, .6), (3, TOMH, .55),
           (4, TOMH, .6), (5, TOML, .6), (6, TOML, .65), (7, TOML, .7)]


def pat_lick(bar_lick, fill=None):
    """Patrón de 4 compases: el lick en cada compás, con un fill opcional en el 4º."""
    g = J.base_grid(N)
    for b in range(4):
        lay(g, fill if (fill and b == 3) else bar_lick, b * BAR)
    return g


def pat_build():
    """Construcción: corcheas casi continuas por caja+toms, con crescendo, y el
    bombo machacando cada negra."""
    g = J.base_grid(N)
    cyc = [SNARE, TOMH, TOML]
    for st in range(4 * BAR):
        tr = cyc[st % 3]
        v = 0.45 + 0.35 * (st / (4 * BAR - 1))         # crescendo a lo largo de los 4 compases
        if st % 2 == 0:
            v += 0.1                                    # acento en el beat
        g[tr][st] = [DRUM_NOTE[tr], min(1.0, round(v, 3))]
    for st in range(0, 4 * BAR, 2):
        g[KICK][st] = [36, 0.4]
    return g


def pat_climax():
    """Explosión: un golpe en cada corchea (caja y toms alternados, con acentos en
    el beat), bombo en cada negra y platillo abierto al inicio de cada compás."""
    g = J.base_grid(N)
    cyc = [SNARE, TOML, TOMH, SNARE]
    for st in range(4 * BAR):
        tr = cyc[st % 4]
        v = (0.7 if st % 2 == 0 else 0.52) + 0.12 * (st / (4 * BAR - 1))
        g[tr][st] = [DRUM_NOTE[tr], min(0.95, round(v, 3))]
    for st in range(0, 4 * BAR, 2):
        g[KICK][st] = [36, 0.65]
    for b in range(4):
        g[HOPEN][b * BAR] = [54, 0.6]
    return g


PATTERNS = {
    "head": pat_lick(HEAD),
    "s1": pat_lick(S1, S1_FILL),
    "s2": pat_lick(S2, S2_FILL),
    "build": pat_build(),
    "climax": pat_climax(),
}

# el arco: expone el tema (head), cambia y construye (trading head/solo, s1->s2->build),
# estalla (climax x2), y vuelve a casa (build->s1->head).
ORDER = ["head", "head",
         "head", "s1", "head", "s2", "s1", "build",
         "climax", "climax",
         "build", "s1", "head", "head"]


def main():
    labels = " · ".join(T.chord_symbol(r, q) for r, q in J.PROG)
    song = {
        "version": 2, "name": "jazz-solo",
        "_nota": f"Solo de bateria sobre el ii-V-I-VI ({labels}). El bajo caminante "
                 f"y el comping de voces guia mantienen la forma; la bateria solea "
                 f"con intensidad creciente (head -> trading -> build -> climax -> "
                 f"vuelta). Kit con toms. Generado por compose_jazz_solo.py.",
        "bpm": J.BPM, "swing": J.SWING,
        "patterns": PATTERNS,
        "order": ORDER,
    }
    with open("canciones/jazz-solo.json", "w", encoding="utf-8") as f:
        json.dump(song, f, ensure_ascii=False, indent=1)
    bars = len(ORDER) * 4
    print(f"jazz-solo.json escrito: {len(ORDER)} patrones ({bars} compases), {labels}")


if __name__ == "__main__":
    main()
