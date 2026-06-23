#!/usr/bin/env python3
"""SAMSARA — una pieza de mantra budista. La rueda del nacer y morir: música no
funcional, hecha de un drone continuo (el Om primordial), un canto que repite el
mantra, y la repetición misma —japa, las 108 cuentas del mala— como camino. La
forma es un ciclo que vuelve al Om: el loop del reproductor *es* el samsara.

Construcción:
  · drone (1) + tanpura (2): la raíz y la quinta sostenidas todo el ciclo —una
    quinta abierta, sin tercera, modal e inmóvil.
  · voz (0): el mantra Oṃ Maṇi Padme Hūm (6 sílabas) en modo frigio (el ♭2 da el
    color devocional), con un vibrato lento como una voz que canta.
  · campana (7, un tom afinado sin caída de pitch, de larga cola) y corazón (3,
    el bombo muy suave): marcan, lentos, cada vuelta de la rueda.

Las voces se construyen sobre los patches del motor, sobreescribiendo solo lo
necesario (ondas suaves, ataques lentos, colas largas). Escribe
canciones/samsara.json.
"""
from __future__ import annotations

import dataclasses
import json

import engine as E
import theory as T

ROOT = 2                     # Re
BPM = 52                     # lento, meditativo
SWING = 0.0                  # recto: sin balanceo
STEPS = 16                   # pasos por ciclo (una vuelta de la rueda)
N_TRACKS = 9

VOZ, DRONE, TANPURA, CORAZON, CAMPANA = 0, 1, 2, 3, 7

# Oṃ Maṇi Padme Hūm en Re frigio (D F G F E♭ D): un arco que sube a la 4ª y
# vuelve a la raíz, con el ♭2 (Mi♭) iluminando la resolución.
MANTRA = [62, 65, 67, 65, 63, 62]
MVEL = [0.60, 0.50, 0.55, 0.50, 0.50, 0.55]


def instruments():
    """Los patches del motor, ablandados para meditación."""
    insts = E.default_instruments()
    P = [dataclasses.asdict(i.params) for i in insts]
    nm = [i.name for i in insts]
    # voz del mantra: seno puro, ataque suave, cola que canta, vibrato lento
    P[VOZ].update(wave=E.SINE, cutoff=2800.0, amp_attack=0.13, amp_decay=0.25,
                  amp_sustain=0.85, amp_release=0.55, volume=0.8,
                  lfo_dest=E.LFO_PITCH, lfo_shape=E.SINE, lfo_rate=5.5, lfo_depth=0.08)
    nm[VOZ] = "voz"
    # drone: raíz grave, triángulo cálido, larga
    P[DRONE].update(wave=E.TRI, cutoff=550.0, amp_attack=0.15, amp_decay=0.5,
                    amp_sustain=0.92, amp_release=1.5, volume=0.9)
    nm[DRONE] = "drone"
    # tanpura: la quinta, con detune (batido de cuerdas simpáticas) y un filtro
    # que respira muy lento
    P[TANPURA].update(wave=E.TRI, detune=11.0, cutoff=1700.0, amp_attack=0.45,
                      amp_decay=0.6, amp_sustain=0.85, amp_release=2.0, volume=0.65,
                      lfo_dest=E.LFO_FILTER, lfo_shape=E.SINE, lfo_rate=0.16, lfo_depth=0.35)
    nm[TANPURA] = "tanpura"
    # corazón: el bombo, sin click, un latido sordo y profundo
    P[CORAZON].update(drum_click=0.0, drum_drop=2.0, drum_pdecay=0.06, drum_noise=0.04,
                      drum_bright=1200.0, amp_decay=0.28, amp_release=0.08, volume=1.0)
    nm[CORAZON] = "corazon"
    # campana: tom afinado SIN caída de pitch (un tono estable) y cola larga = un
    # cuenco/campana que tañe
    P[CAMPANA].update(drum_drop=0.0, drum_noise=0.05, drum_noise_mode=E.NOISE_LP,
                      drum_bright=4000.0, drum_click=0.12, amp_attack=0.001,
                      amp_decay=0.6, amp_release=0.8, volume=1.3)
    nm[CAMPANA] = "campana"
    return [{"name": nm[i], "params": P[i]} for i in range(len(insts))]


def empty():
    return [[None] * STEPS for _ in range(N_TRACKS)]


def drone(g):
    g[DRONE][0] = [38, 0.7, STEPS]        # Re2: la raíz, sostenida todo el ciclo
    g[TANPURA][0] = [57, 0.55, STEPS]     # La3: la quinta -> quinta abierta, modal


def pulse(g, heartbeat=True):
    g[CAMPANA][0] = [74, 0.5]             # la campana tañe al iniciar la vuelta
    if heartbeat:
        g[CORAZON][0] = [36, 0.18]        # latido lento...
        g[CORAZON][8] = [36, 0.16]        # ...dos por ciclo


def mantra(g, shift=0, vel=1.0):
    for i, (n, v) in enumerate(zip(MANTRA, MVEL)):
        g[VOZ][i * 2] = [n + shift, round(v * vel, 3), 2]   # una sílaba cada 2 pasos, legato


def pat_om():
    g = empty(); drone(g); pulse(g); return g                          # el vacío: drone + campana
def pat_mantra():
    g = empty(); drone(g); pulse(g); mantra(g); return g               # el canto
def pat_mantra_alta():
    g = empty(); drone(g); pulse(g); mantra(g, shift=12, vel=0.8); return g  # la rueda asciende
def pat_disolucion():
    g = empty(); drone(g); g[CAMPANA][0] = [74, 0.45]; return g         # se disuelve: solo drone + campana


PATTERNS = {
    "om": pat_om(),
    "mantra": pat_mantra(),
    "mantra-alta": pat_mantra_alta(),
    "disolucion": pat_disolucion(),
}

# la rueda: nace del vacío, canta, asciende, vuelve, se disuelve... y al repetir
# el orden (el reproductor hace loop) vuelve a empezar. Sin fin: samsara.
ORDER = ["om", "om",
         "mantra", "mantra", "mantra", "mantra-alta",
         "mantra", "mantra-alta", "mantra-alta", "mantra",
         "mantra", "mantra",
         "disolucion", "om"]


def main():
    song = {
        "version": 2, "name": "samsara",
        "_nota": "SAMSARA — mantra budista (Om Mani Padme Hum) en Re frigio. Drone "
                 "raiz+quinta sostenido (1,2), la voz canta el mantra de 6 silabas "
                 "(0), campana (7) y latido (3) lentos. Sin swing. La forma es un "
                 "ciclo que vuelve al Om; el loop del reproductor es la rueda, sin "
                 "fin (japa). Generado por compose_samsara.py.",
        "bpm": BPM, "swing": SWING,
        "instruments": instruments(),
        "patterns": PATTERNS,
        "order": ORDER,
    }
    with open("canciones/samsara.json", "w", encoding="utf-8") as f:
        json.dump(song, f, ensure_ascii=False, indent=1)
    print(f"samsara.json escrito: {len(ORDER)} ciclos en Re frigio, {BPM} bpm, sin swing")


if __name__ == "__main__":
    main()
