#!/usr/bin/env python3
"""Ojos: las funciones puras que traducen score→vista. Nombrar acordes (incluidas
inversiones y notas añadidas) e inferir la tonalidad. `uv run python test_ojos.py`."""
from __future__ import annotations

import ojos


def test_name_chord():
    assert ojos.name_chord([60, 64, 67]) == "C"          # Do mayor
    assert ojos.name_chord([62, 65, 69]) == "Dm"         # Re menor
    assert ojos.name_chord([60, 64, 67, 71]) == "Cmaj7"
    assert ojos.name_chord([67, 71, 74, 77]) == "G7"     # dominante
    assert ojos.name_chord([57, 60, 65]) == "F"          # F/A inversión -> F
    assert ojos.name_chord([41, 60]) == "F5"             # quinta abierta (F2+C4)
    assert ojos.name_chord([57, 60, 65, 67]) == "Fadd9"  # F A C G
    assert ojos.name_chord([60]) == "C"                  # una sola nota
    print("ok  name_chord (mayor/menor/7/maj7/inversión/quinta/add9)")


def test_infer_key():
    # notas de Do mayor; la tónica (Do) pesa más -> gana Do mayor sobre su relativo
    wpc = {0: 5, 2: 2, 4: 2, 5: 2, 7: 3, 9: 2, 11: 1}
    t, m, fit = ojos.infer_key(wpc)
    assert (t, m) == (0, "mayor") and fit > 0.99, (t, m, fit)
    # notas de La menor con La pesada -> La menor (no su relativo Do mayor)
    wpc2 = {9: 5, 11: 2, 0: 2, 2: 2, 4: 3, 5: 2, 7: 1}
    t2, m2, _ = ojos.infer_key(wpc2)
    assert (t2, m2) == (9, "menor"), (t2, m2)
    print("ok  infer_key (rompe el empate de relativos por peso de tónica)")


if __name__ == "__main__":
    test_name_chord()
    test_infer_key()
    print("\nTODO OK — ojos")
