#!/usr/bin/env python3
"""Herramientas de composición para formas largas: transponer y variar material
sin reescribir cada compás. Puras (operan sobre grillas/celdas del secuenciador).

Transponer es la palanca del desarrollo: secuenciar (repetir un motivo subiéndolo
un paso) y modular (mover una sección entera a otra tonalidad) —el motor de que
una pieza *vaya a algún lado* en vez de repetirse."""
from __future__ import annotations


def shift_cell(cell, semis: int):
    """Sube (o baja) una celda `semis` semitonos. Maneja None, nota suelta y acorde
    `[[n...],vel,dur]`; conserva velocity y duración."""
    if cell is None:
        return None
    if isinstance(cell, (list, tuple)):
        head = cell[0]
        if isinstance(head, (list, tuple)):
            head = [max(0, min(108, int(n) + semis)) for n in head]
        else:
            head = max(0, min(108, int(head) + semis))
        return [head] + list(cell[1:])
    return max(0, min(108, int(cell) + semis))


def transpose(grid: list, semis: int, skip=()):
    """Grilla nueva con TODAS las notas subidas `semis` semitonos, salvo las pistas
    en `skip` (la percusión —latido, campana— no se transpone)."""
    skip = set(skip)
    return [[shift_cell(c, semis) if tr not in skip else (list(c) if isinstance(c, (list, tuple)) else c)
             for c in row]
            for tr, row in enumerate(grid)]


def transpose_notes(notes, semis: int):
    """Sube una lista de eventos de melodía [(paso, midi, vel, dur), …] `semis`
    semitonos (para variar un motivo por secuencia/inversión desde el compose)."""
    return [(s, max(0, min(108, n + semis)), v, d) for (s, n, v, d) in notes]
