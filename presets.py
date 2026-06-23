"""Guardar y cargar presets: la foto completa del instrumento.

Un preset captura *todo* el estado editable —los `Params` y el nombre de cada
instrumento del motor, cuál está seleccionado, y el patrón + tempo del
secuenciador— en un JSON legible. No sabe nada de la interfaz ni del audio: la
UI llama `save`/`load`/`available`/`delete`, y `restore` aplica una foto sobre un
motor ya vivo (bajo su candado, sin cortar el sonido más que un parpadeo).

Diseño a prueba del futuro: al leer, se ignoran campos que ya no existen y se
dejan en su valor por defecto los que falten. Así un preset viejo siempre carga.
"""

from __future__ import annotations

import dataclasses
import json
import os
import re

import engine as E
from sequencer import Pattern

SCHEMA = 1
PRESET_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "presets")

_FIELDS = {f.name: f for f in dataclasses.fields(E.Params)}


def _slug(name: str) -> str:
    """Nombre de archivo seguro a partir del nombre visible."""
    s = re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-")
    return s or "preset"


def _coerce(name: str, value):
    """Lleva un valor del JSON al tipo del campo de Params (int/float/bool)."""
    default = _FIELDS[name].default
    if isinstance(default, bool):
        return bool(value)
    if isinstance(default, int):
        return int(value)
    if isinstance(default, float):
        return float(value)
    return value


def _params_from_dict(d: dict) -> E.Params:
    """Reconstruye Params tolerando claves de más (se ignoran) o de menos
    (quedan en su valor por defecto)."""
    p = E.Params()
    for k, v in (d or {}).items():
        if k in _FIELDS and v is not None:
            try:
                setattr(p, k, _coerce(k, v))
            except (TypeError, ValueError):
                pass   # valor corrupto: se queda el por defecto
    return p


# ---------------------------------------------------------------- serializar

def snapshot(engine, seq) -> dict:
    """Estado completo como dict serializable (sin tocar nada)."""
    return {
        "version": SCHEMA,
        "sel": int(engine.sel),
        "sequencer": {
            "bpm": int(seq.bpm),
            "swing": float(seq.swing),
            "grid": [list(row) for row in seq.grid],
        },
        "instruments": [
            {"name": ins.name, "params": dataclasses.asdict(ins.params)}
            for ins in engine.instruments
        ],
    }


def _coerce_cell(v):
    """Una celda: None, una nota midi, [midi, vel] o [midi, vel, duración].
    Conserva velocity (0..1) y duración (pasos) si vienen; una nota suelta queda
    como int (velocity 1.0, duración 1)."""
    if v is None:
        return None
    if isinstance(v, (list, tuple)) and v:
        midi = max(0, min(108, int(v[0])))
        if len(v) > 2:
            vel = max(0.0, min(1.0, float(v[1])))
            return [midi, vel, max(1, int(v[2]))]
        if len(v) > 1:
            return [midi, max(0.0, min(1.0, float(v[1])))]
        return midi
    return max(0, min(108, int(v)))


def _coerce_grid(raw: list, n_tracks: int) -> list:
    """Lleva una grilla cruda (filas de None|midi|[midi,vel], posiblemente
    irregular) a una grilla rectangular de n_tracks filas. El ancho (pasos) lo
    fija la fila más larga, así cada patrón conserva su propio largo."""
    raw = raw or []
    width = max((len(r or []) for r in raw), default=16) or 16
    grid = []
    for tr in range(n_tracks):
        src = raw[tr] if tr < len(raw) and raw[tr] else []
        row = [_coerce_cell(src[st] if st < len(src) else None) for st in range(width)]
        grid.append(row)
    return grid


def _read_patterns(data: dict, sq: dict, n_tracks: int):
    """Construye (patrones, orden) desde la foto. Entiende tres formas:
      · canción: `patterns` (dict nombre→grilla, o lista) + `order` (nombres o índices)
      · clásico: `sequencer.grid` (una sola grilla) -> un patrón
      · nada reconocible -> (None, None), no se toca el secuenciador.
    """
    raw = data.get("patterns")
    idx = {}
    if isinstance(raw, dict):
        pats = [Pattern(_coerce_grid(g, n_tracks), str(nm)) for nm, g in raw.items()]
        idx = {p.name: i for i, p in enumerate(pats)}
    elif isinstance(raw, list):
        pats = []
        for i, item in enumerate(raw):
            if isinstance(item, dict):
                nm, g = str(item.get("name", i)), item.get("grid")
            else:
                nm, g = str(i), item
            pats.append(Pattern(_coerce_grid(g or [], n_tracks), nm))
            idx[nm] = i
    else:
        g = sq.get("grid")
        if isinstance(g, list):
            return [Pattern(_coerce_grid(g, n_tracks), "A")], [0]
        return None, None

    order = []
    for o in (data.get("order") or []):
        if isinstance(o, bool):
            continue
        if isinstance(o, int) and 0 <= o < len(pats):
            order.append(o)
        elif isinstance(o, str) and o in idx:
            order.append(idx[o])
    if not order:                                 # sin orden explícito: todos, en orden
        order = list(range(len(pats)))
    return pats, order


def restore(engine, seq, data: dict) -> None:
    """Aplica una foto sobre un motor/secuenciador vivos. Reemplaza los Params
    de cada instrumento bajo el candado del motor (el callback de audio lee
    `instrument.params` de una; intercambiar el objeto es atómico)."""
    insts = data.get("instruments", [])
    with engine._lock:
        engine.panic()                       # evita notas colgadas con el patch viejo
        for i, ins in enumerate(engine.instruments):
            if i < len(insts):
                idata = insts[i]
                ins.params = _params_from_dict(idata.get("params"))
                ins.name = str(idata.get("name", ins.name))
                ins.lfo_phase = 0.0
        sel = data.get("sel", engine.sel)
        engine.sel = int(sel) % len(engine.instruments) if engine.instruments else 0

    sq = data.get("sequencer", {}) or {}
    bpm = data.get("bpm", sq.get("bpm"))     # el tempo va arriba (canción) o dentro (clásico)
    if bpm is not None:
        try:
            seq.bpm = max(40, min(300, int(bpm)))
        except (TypeError, ValueError):
            pass
    swing = data.get("swing", sq.get("swing"))
    if swing is not None:
        try:
            seq.swing = max(0.0, min(0.7, float(swing)))
        except (TypeError, ValueError):
            pass

    pats, order = _read_patterns(data, sq, len(engine.instruments))
    if pats:
        seq.patterns = pats
        seq.order = order
        seq.order_pos = 0
        seq.pos = -1


# ---------------------------------------------------------------- disco

def save(name: str, engine, seq, directory: str = PRESET_DIR) -> str:
    """Guarda la foto actual con el nombre dado. Devuelve la ruta escrita."""
    data = snapshot(engine, seq)
    data["name"] = name.strip() or "preset"
    os.makedirs(directory, exist_ok=True)
    path = os.path.join(directory, _slug(name) + ".json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    return path


def load(key: str, engine, seq, directory: str = PRESET_DIR) -> dict:
    """Carga un preset por su clave (nombre de archivo sin .json) y lo aplica.
    Devuelve el dict leído (incluye `name` para mostrar)."""
    path = os.path.join(directory, key + ".json")
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    restore(engine, seq, data)
    return data


def available(directory: str = PRESET_DIR) -> list[dict]:
    """Lista los presets guardados: [{"label": nombre, "key": archivo}], ordenada
    por nombre visible. `label` es el nombre que el usuario escribió; `key` es el
    identificador para load/delete."""
    out = []
    try:
        names = os.listdir(directory)
    except FileNotFoundError:
        return out
    for fn in names:
        if not fn.endswith(".json"):
            continue
        key = fn[:-5]
        label = key
        try:
            with open(os.path.join(directory, fn), encoding="utf-8") as f:
                label = json.load(f).get("name", key)
        except (OSError, ValueError):
            pass
        out.append({"label": label, "key": key})
    out.sort(key=lambda d: d["label"].lower())
    return out


def delete(key: str, directory: str = PRESET_DIR) -> None:
    path = os.path.join(directory, key + ".json")
    if os.path.exists(path):
        os.remove(path)
