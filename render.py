#!/usr/bin/env python3
"""Render fuera de línea: toca una partitura SIN tarjeta de audio.

Avanza el secuenciador con un reloj falso y llama al callback del motor a mano
—igual que test_engine— para producir la señal completa, escribirla a WAV y
sacar unos números (duración, nivel RMS, pico, si satura). Es el "ojo" de
Kichoro: deja revisar lo que compuso —que suene algo, que no clipee, dónde cae
la energía— antes de pedirle el oído a alguien. No abre la tarjeta de audio, así
que corre en cualquier parte (CI incluido).

Uso:
    uv run render.py canciones/primera.json [segundos] [salida.wav]
"""
from __future__ import annotations

import json
import sys
import wave

import numpy as np

import engine as E
import presets
from sequencer import Sequencer

BLOCK = 1024   # mismo bloque que el stream en vivo


def song_seconds(seq) -> float:
    """Duración de una vuelta completa del arreglo (suma de los pasos de cada
    patrón del orden × la duración de un paso)."""
    steps = sum(seq.patterns[i % len(seq.patterns)].n_steps for i in seq.order)
    return steps * seq.step_dur()


def render(data: dict, seconds: float = None) -> np.ndarray:
    """Señal mono (float32) de tocar `data`, determinista en el tiempo (el reloj
    lo ponemos nosotros, bloque a bloque). Si `seconds` es None, rinde una vuelta
    completa de la canción."""
    eng = E.Engine()
    seq = Sequencer(eng)
    presets.restore(eng, seq, data)
    if seconds is None:
        seconds = max(song_seconds(seq), 2.0)

    n_blocks = int(seconds * E.SR / BLOCK)
    out = np.zeros(n_blocks * BLOCK, dtype=np.float32)
    buf = np.zeros((BLOCK, 2), dtype=np.float32)
    t = 0.0
    seq.play(t)
    for i in range(n_blocks):
        seq.tick(t)                       # avanza pasos / dispara notas según el reloj
        buf[:] = 0.0
        eng._callback(buf, BLOCK, None, None)
        out[i * BLOCK:(i + 1) * BLOCK] = buf[:, 0]
        t += BLOCK / E.SR
    return out


def analyze(sig: np.ndarray) -> dict:
    """Lo que sí puedo 'ver' del sonido sin oírlo."""
    if not len(sig):
        return {"segundos": 0.0, "rms": 0.0, "peak": 0.0, "clip": False}
    peak = float(np.max(np.abs(sig)))
    return {
        "segundos": len(sig) / E.SR,
        "rms": float(np.sqrt(np.mean(sig.astype(np.float64) ** 2))),
        "peak": peak,
        "clip": peak >= 0.999,
    }


def write_wav(sig: np.ndarray, path: str) -> None:
    pcm = (np.clip(sig, -1.0, 1.0) * 32767).astype("<i2")
    with wave.open(path, "w") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(E.SR)
        w.writeframes(pcm.tobytes())


def main():
    args = sys.argv[1:]
    if not args:
        print("uso: uv run render.py <archivo.json> [segundos] [salida.wav]")
        raise SystemExit(2)
    path = args[0]
    seconds = float(args[1]) if len(args) > 1 else None   # None -> una vuelta completa
    out_path = args[2] if len(args) > 2 else "render.wav"

    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    sig = render(data, seconds)
    a = analyze(sig)
    write_wav(sig, out_path)
    print(f"{path}: {a['segundos']:.1f}s  rms={a['rms']:.3f}  peak={a['peak']:.3f}"
          f"  {'¡CLIP!' if a['clip'] else 'sin clip'}  -> {out_path}")


if __name__ == "__main__":
    main()
