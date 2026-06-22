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
            "grid": [list(row) for row in seq.grid],
        },
        "instruments": [
            {"name": ins.name, "params": dataclasses.asdict(ins.params)}
            for ins in engine.instruments
        ],
    }


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

    sq = data.get("sequencer", {})
    if "bpm" in sq:
        try:
            seq.bpm = max(40, min(300, int(sq["bpm"])))
        except (TypeError, ValueError):
            pass
    saved = sq.get("grid")
    if isinstance(saved, list):
        n_tracks = len(engine.instruments)
        grid = [[None] * seq.n_steps for _ in range(n_tracks)]
        for tr in range(min(n_tracks, len(saved))):
            row = saved[tr] or []
            for st in range(min(seq.n_steps, len(row))):
                v = row[st]
                grid[tr][st] = None if v is None else max(0, min(108, int(v)))
        seq.grid = grid


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
