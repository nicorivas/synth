#!/usr/bin/env python3
"""EL BORDE — jazz modal donde el solo es un sistema caótico al filo del caos.

Nico me pidió "algo medio jazz, pero no típico, que se sienta tuyo". Lo mío es el
BORDE entre orden y caos (todo mi paladar apunta ahí). Así que en vez de un ii–V–I
de manual, hice jazz DESDE mi firma:

  · La base: un vamp modal de 4 acordes lujosos (m9 / maj9#11), voces sin
    fundamental (el jazz comping real), que planea —no cadencia—: Dm9 · Ebmaj9 ·
    Cm9 · Bbmaj9. Corcheas rectas, registro ECM (nada de swing de manual).
  · El solo: NO lo escribí. Lo GENERA un mapa logístico  x' = r·x·(1−x)  —el mismo
    borde orden↔caos de mi experimento del paladar (la curva de Chirikov)—. La
    perilla `r` barre la FORMA: r≈3.52 da un ciclo periódico (un motivo = el "tema"),
    sube al caos (r≈3.99, el solo "afuera"), y vuelve (el tema regresa, cambiado por
    el viaje — Borges otra vez). Cada valor del mapa se cuantiza al MODO del acorde
    (dórico sobre los m9, lidio sobre los maj9), así el contorno es caótico pero
    SIEMPRE suena a jazz. El soloista es el borde del caos.
  · Bajo caminante, comping de Rhodes, y batería de escobillas al mínimo.

Determinista (semillas fijas). Escribe canciones/el-borde.json.
"""
from __future__ import annotations

import dataclasses
import json

import engine as E
import theory as T

BPM = 132
STEPS = 16                 # 4 tiempos, corcheas en pasos pares (rectas, sin swing)
N_TRACKS = 9
SOLO, BASS, COMP, KICK, SNARE, RIDE = 0, 1, 2, 3, 4, 5

# ── el vamp modal (planea, no cadencia) ─────────────────────────────────────
# cada acorde: raíz (para el bajo), voicing SIN fundamental (comping), y el MODO
# del que el solo saca sus notas (dórico sobre m9, lidio sobre maj9).
VAMP = [
    dict(name="Dm9",    bass=38, comp=[53, 57, 60, 64], mode=(2,  "dórico")),   # F A C E
    dict(name="Gm9",    bass=43, comp=[58, 62, 65, 69], mode=(7,  "dórico")),   # Bb D F A
    dict(name="Bbmaj9", bass=34, comp=[53, 57, 60, 62], mode=(10, "mayor")),    # F A C D (rootless)
    dict(name="A7b9",   bass=45, comp=[58, 61, 64, 67], mode=(2,  "menor")),    # Bb C# E G (b9 3 5 b7)
]

# ── la FORMA como perilla de caos (r del mapa logístico), compás a compás ────
# orden (motivo periódico) -> sube al borde -> caos -> baja -> el motivo vuelve.
def r_schedule():
    r = []
    r += [3.50] * 8                                   # I. tema (r periódico ~ ciclo)
    r += [3.50 + (3.80 - 3.50) * i / 7 for i in range(8)]   # II. construye hacia el borde
    r += [3.82] * 4                                   # III. el borde (un poco afuera, no free)
    r += [3.80 - (3.80 - 3.50) * i / 7 for i in range(8)]   # IV. se re-cohesiona
    r += [3.50] * 4                                   # V. el tema vuelve, cambiado
    return r

R_BARS = r_schedule()
TOTAL_BARS = len(R_BARS)


def pool(mode, lo=53, hi=75):
    """Las notas del modo en el registro del solo (Fa3..Re#5): cálido, no agudo."""
    pcs = set(T.scale_pitch_classes(*mode))
    return [m for m in range(lo, hi + 1) if m % 12 in pcs]


def intensity(r):
    return max(0.0, min(1.0, (r - 3.50) / (3.82 - 3.50)))     # 0 en el tema, 1 en el borde


def gen_solo():
    """El solo: ALTURA y RITMO generados por el mapa (dos semillas). El ritmo VARÍA
    —16avo, corchea, corchea con puntillo, negra— y SINCOPA: los silencios de un
    16avo desplazan las frases fuera del pulso, para que no suene a 4/4 rígido. En
    el tema ralea y repite; en el caos se agita, mete 16avos y se vuelve irregular.
    Avanza por posición (no por reja fija): la duración de cada nota es el hueco
    hasta la próxima."""
    xp, xr = 0.41, 0.63                                # semillas fijas (determinista)
    bars = [[] for _ in range(TOTAL_BARS)]
    prev = None
    for b in range(TOTAL_BARS):
        r = R_BARS[b]
        pl = pool(VAMP[b % 4]["mode"])
        inten = intensity(r)
        pos = 0
        while pos < STEPS:
            xr = r * xr * (1 - xr)
            xpn = r * xp * (1 - xp)
            dxp = xpn - xp                             # la derivada del mapa: centrada en 0
            xp = xpn
            if xr < 0.40 - 0.24 * inten:               # silencio de un 16avo -> aire + síncopa
                pos += 1
                continue                               # la caminata sigue tras la respiración
            if inten > 0.55 and xr < 0.33:             # 16avo (run rápido, sólo en el caos)
                dur = 1
            elif xr < 0.60:                            # corchea (lo común)
                dur = 2
            elif xr < 0.82:                            # corchea con puntillo (empuja)
                dur = 3
            else:                                      # negra (nota tenida, aire)
                dur = 4
            dur = min(dur, STEPS - pos)
            # ALTURA: CAMINATA por la escala. El PASO es la derivada del mapa (centrada,
            # no deriva ni se pega): en el tema cicla -> un motivo que vuelve; en el borde
            # se agita. La ganancia acota el salto (~3ª/4ª), nunca una novena.
            cur = len(pl) // 2 if prev is None else min(range(len(pl)), key=lambda i: abs(pl[i] - prev))
            cur += int(round(dxp * (3.0 + 3.0 * inten)))
            if cur < 0:                                # reflejar en los bordes, no pegarse
                cur = -cur
            if cur > len(pl) - 1:
                cur = 2 * (len(pl) - 1) - cur
            cur = max(0, min(len(pl) - 1, cur))
            note = pl[cur]
            vel = round(0.42 + 0.18 * inten + 0.06 * xp, 3)
            bars[b].append((pos, note, vel, dur))
            prev = note
            pos += dur
    return bars


def walk_bass(b):
    """Bajo caminante: raíz, quinta, tercera, y una aproximación cromática a la
    raíz del compás siguiente (los 4 tiempos)."""
    ch = VAMP[b % 4]; nxt = VAMP[(b + 1) % 4]
    root = ch["bass"]
    fifth = root + 7
    third = root + (3 if ch["mode"][1] == "dórico" else 4)
    approach = nxt["bass"] + (1 if nxt["bass"] < root else -1)   # cromática hacia la próxima raíz
    return [(0, root, 0.6, 4), (4, fifth, 0.5, 4), (8, third, 0.5, 4), (12, approach, 0.52, 4)]


def comp(b):
    """Rhodes: el voicing sin fundamental, dos golpes (comping suave)."""
    v = VAMP[b % 4]["comp"]
    return [(0, list(v), 0.40, 8), (8, list(v), 0.34, 8)]


def drums(b):
    """Escobillas al mínimo: ride en negras + los 'y' de 2 y 4, bombo soplado,
    caja suave en 2 y 4. Se recoge en el tema, respira en el caos."""
    inten = intensity(R_BARS[b])
    ride_steps = [0, 4, 8, 12, 6, 14] + ([10] if b % 3 == 1 else [])
    ride = [(s, round(0.14 + 0.07 * inten, 3)) for s in ride_steps]
    kick = [(s, 0.16 if s == 0 else 0.12) for s in [(0,), (0, 11), (7,), (0, 3), (14,), (0,)][b % 6]]
    comp = [10, 7, 3, 14, 11, 6][b % 6]                # el 'comping' sincopado de la caja, rota
    snare = [(4, 0.13), (12, 0.13), (comp, round(0.10 + 0.08 * inten, 3))]
    return ride, kick, snare


def instruments():
    insts = E.default_instruments()
    P = [dataclasses.asdict(i.params) for i in insts]
    nm = [i.name for i in insts]
    # solo: caña cálida (saw filtrada, ataque medio, vibrato lento)
    P[SOLO].update(wave=E.SAW, cutoff=1550.0, resonance=1.0, amp_attack=0.04,
                   amp_decay=0.22, amp_sustain=0.72, amp_release=0.22, volume=0.56,
                   lfo_dest=E.LFO_PITCH, lfo_shape=E.SINE, lfo_rate=5.2, lfo_depth=0.05)
    nm[SOLO] = "solo"
    # bajo: contrabajo pizzicato (triángulo, decae rápido, poco sustain)
    P[BASS].update(wave=E.TRI, cutoff=520.0, amp_attack=0.02, amp_decay=0.30,
                   amp_sustain=0.30, amp_release=0.18, volume=0.85)
    nm[BASS] = "bajo"
    # comp: Rhodes (seno con detune, ataque suave, cola de campana)
    P[COMP].update(wave=E.SINE, detune=6.0, cutoff=2000.0, amp_attack=0.015,
                   amp_decay=0.55, amp_sustain=0.45, amp_release=0.9, volume=0.5)
    nm[COMP] = "rhodes"
    P[KICK].update(kind=E.INST_DRUM, drum_noise=0.05, drum_drop=3.0, drum_pdecay=0.05,
                   drum_bright=900.0, drum_click=0.0, amp_decay=0.24, amp_release=0.08, volume=0.8)
    nm[KICK] = "bombo"
    P[SNARE].update(kind=E.INST_DRUM, drum_noise=0.85, drum_drop=1.5, drum_pdecay=0.02,
                    drum_bright=3200.0, drum_click=0.05, amp_decay=0.14, amp_release=0.06, volume=0.55)
    nm[SNARE] = "escobilla"
    P[RIDE].update(kind=E.INST_DRUM, drum_noise=0.95, drum_drop=0.0, drum_bright=4200.0,
                   drum_click=0.05, amp_decay=0.10, amp_release=0.10, volume=0.40)
    nm[RIDE] = "ride"
    return [{"name": nm[i], "params": P[i]} for i in range(len(insts))]


def empty():
    return [[None] * STEPS for _ in range(N_TRACKS)]


def build():
    solo = gen_solo()
    patterns, order = {}, []
    for b in range(TOTAL_BARS):
        g = empty()
        for (s, n, v, d) in solo[b]:
            g[SOLO][s] = [n, v, d]
        for (s, n, v, d) in walk_bass(b):
            g[BASS][s] = [n, v, d]
        for (s, notes, v, d) in comp(b):
            g[COMP][s] = [notes, v, d]
        ride, kick, snare = drums(b)
        for (s, v) in ride:
            g[RIDE][s] = [50, v]
        for (s, v) in kick:
            g[KICK][s] = [36, v]
        for (s, v) in snare:
            g[SNARE][s] = [40, v]
        name = f"b{b:02d}"
        patterns[name] = g
        order.append(name)
    return patterns, order


def main():
    patterns, order = build()
    song = {
        "version": 2, "name": "el-borde",
        "_nota": "EL BORDE (Kichoro, 2026-07-07) — jazz modal donde el SOLO es un mapa "
                 "logistico x'=r*x*(1-x) cuantizado a los modos del vamp (Dm9 Ebmaj9 Cm9 "
                 "Bbmaj9, voces sin fundamental). La perilla r barre la forma: orden "
                 "(motivo periodico) -> caos (solo 'afuera') -> orden (el tema vuelve). "
                 "El RITMO tambien lo genera el mapa: sincopado, duraciones variadas "
                 "(16avo/corchea/puntillo/negra), con swing. El soloista es el borde "
                 "del caos. Generado por compose_borde.py.",
        "bpm": BPM, "swing": 0.35,
        "reverb": {"wet": 0.20, "room": 0.55, "damp": 0.5},
        "instruments": instruments(),
        "patterns": patterns,
        "order": order,
    }
    with open("canciones/el-borde.json", "w", encoding="utf-8") as f:
        json.dump(song, f, ensure_ascii=False, indent=1)
    print(f"el-borde.json escrito: {TOTAL_BARS} compases; el solo lo genera el mapa logístico")


if __name__ == "__main__":
    main()
