#!/usr/bin/env python3
"""Reverb: identidad en seco, cola que decae, estabilidad, y —lo importante—
que sea independiente del tamaño de bloque (los delays van en muestras, así que
procesar en trozos de 512 o de 1024 debe dar la MISMA señal). `uv run python test_reverb.py`."""
from __future__ import annotations

import numpy as np

from reverb import Reverb

rng = np.random.default_rng(7)


def test_seco_es_identidad():
    r = Reverb(); r.wet = 0.0
    x = rng.standard_normal(512).astype(float)
    y = r.process(x)
    assert np.array_equal(x, y), "con wet=0 debe devolver la señal intacta"
    print("ok  seco (wet=0) = identidad")


def test_cola_decae_y_es_finita():
    r = Reverb(); r.wet, r.room, r.damp = 0.7, 0.8, 0.4
    imp = np.zeros(512); imp[0] = 1.0
    r.process(imp)                                   # el impulso
    energias = []
    for _ in range(60):                              # 60 bloques de silencio: la cola
        y = r.process(np.zeros(512))
        assert np.all(np.isfinite(y)), "la cola no puede tener NaN/inf"
        assert max(abs(y.max()), abs(y.min())) < 5.0, "la cola no puede dispararse"
        energias.append(float(np.sqrt(np.mean(y ** 2))))
    peak = int(np.argmax(energias))                  # la cola arranca tras el pre-delay (~2 bloques)
    assert energias[peak] > 1e-4, "tiene que haber cola tras el impulso"
    assert energias[-1] < energias[peak] * 0.5, "la cola debe DECAER con el tiempo"
    print(f"ok  cola aparece en bloque {peak} (~{peak*512/44100*1000:.0f}ms), "
          f"decae {energias[peak]:.4f} -> {energias[-1]:.5f}")


def test_room_alarga_la_cola():
    def cola_tardia(room):
        r = Reverb(); r.wet, r.room, r.damp = 0.7, room, 0.3
        imp = np.zeros(512); imp[0] = 1.0
        r.process(imp)
        late = [r.process(np.zeros(512)) for _ in range(30)]
        return float(np.sqrt(np.mean(np.concatenate(late[15:]) ** 2)))   # energía tardía
    chica, grande = cola_tardia(0.2), cola_tardia(0.95)
    assert grande > chica * 1.5, f"más room = cola más larga ({chica:.5f} vs {grande:.5f})"
    print(f"ok  room alarga la cola (tardía: {chica:.5f} chica -> {grande:.5f} grande)")


def test_independiente_del_bloque():
    sig = rng.standard_normal(512 * 12).astype(float) * 0.3
    def run(hop):
        r = Reverb(); r.wet, r.room, r.damp = 0.6, 0.7, 0.4
        return np.concatenate([r.process(sig[i:i + hop]) for i in range(0, len(sig), hop)])
    a, b = run(512), run(1024)
    assert np.allclose(a, b, atol=1e-9), f"512 vs 1024 difieren (máx {np.abs(a-b).max():.2e})"
    print("ok  independiente del tamaño de bloque (512 == 1024, exacto por muestra)")


if __name__ == "__main__":
    test_seco_es_identidad()
    test_cola_decae_y_es_finita()
    test_room_alarga_la_cola()
    test_independiente_del_bloque()
    print("\nTODO OK — reverb")
