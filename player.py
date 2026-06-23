#!/usr/bin/env python3
"""Reproductor en vivo: vigila un archivo de partitura y lo suena por los
parlantes, recargándolo en caliente cada vez que cambia —sin reiniciar.

Pensado para componer a cuatro manos: Kichoro escribe el archivo, este programa
lo re-suena al instante, y quien escucha va diciendo cómo suena. El motor de
audio corre en su propio hilo; aquí solo avanzamos el secuenciador con el reloj
real y, cuando el archivo cambia, le aplicamos la nueva foto al motor vivo
(`presets.restore`, que reemplaza patches/grilla/bpm bajo el candado).

El archivo es una "foto" como las de presets/: basta el bloque `sequencer`
(bpm + grilla de 6 pistas × 16 pasos, cada celda `null` o una nota midi); los
instrumentos usan los patches por defecto salvo que incluyas un bloque
`instruments`. Si lo pillamos a medio escribir y no parsea, mantenemos lo último
bueno y reintentamos al próximo guardado.

Uso:
    ./play canciones/primera.json        # o:  uv run player.py <archivo>
Ctrl-C para salir.
"""
from __future__ import annotations

import json
import os
import sys
import time

import engine as E
import presets
from sequencer import Sequencer


def _read(path: str):
    """Lee y parsea el archivo; devuelve el dict, o None si no se pudo (no existe
    todavía, o quedó a medio escribir y aún no es JSON válido)."""
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def main():
    if len(sys.argv) < 2:
        print("uso: ./play <archivo.json>")
        raise SystemExit(2)
    path = sys.argv[1]

    eng = E.Engine()
    seq = Sequencer(eng)

    data = _read(path)
    if data is not None:
        presets.restore(eng, seq, data)
    mtime = os.path.getmtime(path) if os.path.exists(path) else 0.0

    eng.start()
    seq.play(time.monotonic())
    print(f"♪ sonando {path} — edítalo y se recarga solo · Ctrl-C para salir")
    try:
        while True:
            seq.tick(time.monotonic())
            if os.path.exists(path):
                m = os.path.getmtime(path)
                if m != mtime:
                    data = _read(path)
                    if data is not None:
                        presets.restore(eng, seq, data)
                        mtime = m       # solo avanzamos mtime si parseó: si no, reintenta
                        print(f"↻ recargado {time.strftime('%H:%M:%S')}")
            time.sleep(0.004)           # ~4 ms: muy fino para los 16avos, suave con la CPU
    except KeyboardInterrupt:
        pass
    finally:
        seq.stop()
        eng.stop()
        print("· detenido")


if __name__ == "__main__":
    main()
