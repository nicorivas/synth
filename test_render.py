"""Prueba headless del render fuera de línea: toca la canción de ejemplo sin
tarjeta de audio y verifica que suena algo (la señal no es plana) y que la
mezcla no satura. Es la red de seguridad de la mitad 'ojo' del flujo de
composición."""

import json

import render


def main():
    with open("canciones/primera.json", encoding="utf-8") as f:
        data = json.load(f)
    sig = render.render(data, seconds=2.5)
    a = render.analyze(sig)
    assert a["rms"] > 0.01, f"señal casi muda: rms={a['rms']}"
    assert not a["clip"], f"la mezcla satura (peak={a['peak']})"
    print(f"render: ok  ({a['segundos']:.1f}s  rms={a['rms']:.3f}  peak={a['peak']:.3f})")
    print("OK -> render")


if __name__ == "__main__":
    main()
