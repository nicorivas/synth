#!/usr/bin/env python3
"""OJOS — para un compositor sin oídos.

Kichoro compone escribiendo archivos y no puede oírlos. Esto traduce una canción
a cosas que sí puedo *ver*, en el terminal (y opcionalmente a PNG):

  1. RESUMEN     — tempo, tonalidad probable (inferida), pistas, duración.
  2. ARMONÍA     — el acorde de cada compás del arreglo: la progresión, en una línea.
  3. PIANO-ROLL  — el score dibujado: altura (vertical) × paso (horizontal), una
                   letra por pista. Ver contorno de la melodía, voicings, choques.
  4. AVISOS      — notas fuera de la tonalidad, saltos melódicos grandes, barro de
                   registro (dos voces pegadas y graves), cruces de voces.
  5. AUDIO       — renderiza y mide: nivel/clip, el ARCO dinámico compás a compás,
                   el balance grave/medio/agudo, y un COTEJO por FFT de que las
                   alturas que escribí de verdad sonaron (mi 'oído' es el espectro).

Uso:
    uv run ojos.py canciones/la-mano.json            # todo a texto
    uv run ojos.py canciones/la-mano.json --png roll.png   # además, piano-roll a PNG
"""
from __future__ import annotations

import json
import sys

import numpy as np

import engine as E
import render
import theory as T
from sequencer import _split_cell

STEP_EMPTY, STEP_SUS = "·", "─"


# ── lectura del score ───────────────────────────────────────────────────────

def note_name(midi: int) -> str:
    return T.NOTE_NAMES[midi % 12] + str(midi // 12 - 1)


def track_info(song: dict) -> list:
    """[{name, drum, glyph}] por pista. La letra (glyph) distingue cada pista
    melódica en el piano-roll; las de percusión van en su propia banda."""
    insts = song.get("instruments", [])
    used = set()
    out = []
    for i, ins in enumerate(insts):
        name = str(ins.get("name", f"t{i}"))
        drum = int(ins.get("params", {}).get("kind", E.INST_SYNTH)) == E.INST_DRUM
        glyph = ""
        for ch in (name.upper() + "ABCDEFGHJKLMNP"):
            if ch.isalnum() and ch not in used:
                glyph = ch; used.add(ch); break
        out.append({"name": name, "drum": drum, "glyph": glyph})
    return out


def cell_notes(cell):
    """(notas, vel, dur) de una celda, o ([], 0, 1) si está apagada."""
    notes, vel, dur = _split_cell(cell)
    return (notes or []), vel, dur


def pattern_events(grid: list, tracks: list):
    """Eventos (track, pitch, step, dur, vel) de un patrón, separando melódico/perc."""
    ev = []
    for tr, row in enumerate(grid):
        drum = tracks[tr]["drum"] if tr < len(tracks) else False
        for step, cell in enumerate(row):
            notes, vel, dur = cell_notes(cell)
            for p in notes:
                ev.append({"tr": tr, "pitch": p, "step": step, "dur": dur,
                           "vel": vel, "drum": drum})
    return ev


# ── nombrar el acorde de un compás ──────────────────────────────────────────

_TRIAD = {(0, 4, 7): "", (0, 3, 7): "m", (0, 3, 6): "°", (0, 4, 8): "+"}


def name_chord(midis: list) -> str:
    """Nombre del acorde a partir de notas cualesquiera (maneja inversiones y
    notas añadidas probando cada nota como fundamental)."""
    pcs = sorted(set(m % 12 for m in midis))
    if not pcs:
        return "—"
    if len(pcs) == 1:
        return T.NOTE_NAMES[pcs[0]]
    if len(pcs) == 2:
        lo = min(midis) % 12
        iv = sorted((p - lo) % 12 for p in pcs)[1]
        if iv == 7:
            return T.NOTE_NAMES[lo] + "5"            # quinta abierta / power
        return "+".join(T.NOTE_NAMES[p] for p in pcs)
    best = None
    for root in pcs:
        ivs = set((p - root) % 12 for p in pcs)
        for triad, q in _TRIAD.items():
            if set(triad) <= ivs:
                extras = ivs - set(triad)
                cand = (len(triad), -len(extras), root, q, extras)
                if best is None or cand[:2] > best[:2]:
                    best = cand
    if best is None:
        return "(" + " ".join(T.NOTE_NAMES[p] for p in pcs) + ")"
    _, _, root, q, extras = best
    tags = []
    if 11 in extras: tags.append("maj7"); extras -= {11}
    elif 10 in extras: tags.append("7"); extras -= {10}
    if 2 in extras: tags.append("add9"); extras -= {2}
    if 5 in extras: tags.append("add4"); extras -= {5}
    if 9 in extras and q == "": tags.append("6"); extras -= {9}
    for e in sorted(extras): tags.append("+" + T.NOTE_NAMES[(root + e) % 12])
    return T.NOTE_NAMES[root] + q + "".join(tags)


def bar_harmony(grid: list, tracks: list, n_steps: int) -> list:
    """Las notas 'de armonía' de un compás: las sostenidas (dur >= medio compás),
    que son el pad/bajo, no la melodía rápida."""
    thr = max(2, int(n_steps * 0.75))       # casi el compás entero = pad/bajo, no melodía
    notes = []
    for ev in pattern_events(grid, tracks):
        if not ev["drum"] and ev["dur"] >= thr:
            notes.append(ev["pitch"])
    return notes


# ── tonalidad probable (inferida de las notas) ──────────────────────────────

def infer_key(weighted_pcs: dict):
    """(tónica, modo, ajuste 0..1) que mejor cubre las notas (ponderadas por
    duración). Prueba mayores y menores."""
    total = sum(weighted_pcs.values()) or 1
    cands = []
    for tonic in range(12):
        for mode in ("mayor", "menor"):
            sc = set(T.scale_pitch_classes(tonic, mode))
            fit = sum(w for pc, w in weighted_pcs.items() if pc in sc) / total
            # desempate: la tónica con más peso (drone/bajo/resolución) gana entre
            # relativos que comparten notas (Fa mayor vs Re menor tienen igual ajuste)
            cands.append((round(fit, 4), weighted_pcs.get(tonic, 0), tonic, mode))
    cands.sort(reverse=True)
    fit, _, tonic, mode = cands[0]
    return tonic, mode, fit


# ── piano-roll ASCII ────────────────────────────────────────────────────────

def piano_roll(grid: list, tracks: list, n_steps: int) -> list:
    """Líneas del piano-roll melódico (altura×paso) + la banda de percusión."""
    cells = {}                          # (pitch, step) -> glyph|sustain
    used = set()
    for ev in pattern_events(grid, tracks):
        if ev["drum"]:
            continue
        g = tracks[ev["tr"]]["glyph"]
        p, s = ev["pitch"], ev["step"]
        used.add(p)
        cells[(p, s)] = g
        for k in range(1, ev["dur"]):
            if s + k < n_steps and (p, s + k) not in cells:
                cells[(p, s + k)] = STEP_SUS
    lines = []
    if used:
        hi, lo = max(used), min(used)
        raw = []
        for pitch in range(hi, lo - 1, -1):
            rowstr = "".join(cells.get((pitch, s), STEP_EMPTY) for s in range(n_steps))
            raw.append((note_name(pitch), rowstr, set(rowstr) <= {STEP_EMPTY}))
        i = 0
        while i < len(raw):                          # colapsa huecos vacíos de >=4
            if raw[i][2]:
                j = i
                while j < len(raw) and raw[j][2]:
                    j += 1
                if j - i >= 4:
                    lines.append("     ⋮")
                else:
                    lines += [f"{lbl:>4} {rs}" for lbl, rs, _ in raw[i:j]]
                i = j
            else:
                lines.append(f"{raw[i][0]:>4} {raw[i][1]}")
                i += 1
    # banda de percusión: una fila por pista de tambor, X=fuerte x=suave
    for tr, t in enumerate(tracks):
        if not t["drum"]:
            continue
        row = grid[tr] if tr < len(grid) else []
        marks = []
        for s in range(n_steps):
            notes, vel, _ = cell_notes(row[s] if s < len(row) else None)
            marks.append(("X" if vel >= 0.5 else "x") if notes else STEP_EMPTY)
        if any(m != STEP_EMPTY for m in marks):
            lines.append(f"{t['name'][:4]:>4} {''.join(marks)}")
    return lines


# ── avisos (voice-leading / registro) ───────────────────────────────────────

def warnings(song: dict, tracks: list, patterns: dict, tonic: int, mode: str) -> list:
    w = []
    scale = set(T.scale_pitch_classes(tonic, mode))
    key = f"{T.NOTE_NAMES[tonic]} {mode}"
    for name, grid in patterns.items():
        ev = pattern_events(grid, tracks)
        # 1) notas fuera de la tonalidad (melódicas)
        outs = sorted({note_name(e["pitch"]) for e in ev
                       if not e["drum"] and e["pitch"] % 12 not in scale})
        if outs:
            w.append(f"«{name}» fuera de {key}: {', '.join(outs)}")
        # 2) saltos melódicos grandes (>1 octava) dentro de una pista
        for tr in {e["tr"] for e in ev if not e["drum"]}:
            seq = sorted((e["step"], e["pitch"]) for e in ev if e["tr"] == tr)
            for (s0, p0), (s1, p1) in zip(seq, seq[1:]):
                if abs(p1 - p0) > 12:
                    w.append(f"«{name}» {tracks[tr]['name']}: salto de "
                             f"{abs(p1-p0)} semitonos ({note_name(p0)}→{note_name(p1)})")
        # 3) barro: dos notas melódicas simultáneas a <=2 semitonos y graves (<C3=48)
        onsets = {}
        for e in ev:
            if not e["drum"]:
                onsets.setdefault(e["step"], []).append(e["pitch"])
        for s, ps in onsets.items():
            ps = sorted(ps)
            for a, b in zip(ps, ps[1:]):
                if 0 < b - a <= 2 and b < 48:
                    w.append(f"«{name}» barro grave: {note_name(a)}+{note_name(b)} "
                             f"(2ª pegada bajo Do3)")
    return w


# ── audio: arco, balance, cotejo de alturas ─────────────────────────────────

def bar_len_samples(song: dict, n_steps: int) -> int:
    return int(round(n_steps * (60.0 / song["bpm"] / 4.0) * E.SR))


def band_balance(sig: np.ndarray):
    S = np.abs(np.fft.rfft(sig * np.hanning(len(sig)))) ** 2
    f = np.fft.rfftfreq(len(sig), 1.0 / E.SR)
    tot = S.sum() or 1.0
    lo = S[f < 250].sum() / tot
    mid = S[(f >= 250) & (f < 2000)].sum() / tot
    hi = S[f >= 2000].sum() / tot
    return lo, mid, hi


def spark(vals):
    blocks = "▁▂▃▄▅▆▇█"
    lo, hi = min(vals), max(vals)
    rng = (hi - lo) or 1.0
    return "".join(blocks[min(7, int((v - lo) / rng * 7.999))] for v in vals)


def pitch_check(song: dict, patterns: dict, order: list, tracks: list, n_steps: int):
    """Cotejo por FFT: en el compás con más armonía sostenida, ¿cada altura que
    escribí tiene energía en su fundamental? (Cacha 'lo escribí pero no sonó'.)"""
    # el compás más 'lleno' de notas sostenidas
    best_name, best_notes = None, []
    for name, grid in patterns.items():
        notes = bar_harmony(grid, tracks, n_steps)
        if len(set(notes)) > len(set(best_notes)):
            best_name, best_notes = name, notes
    if not best_notes:
        return None
    mini = dict(song)
    mini = {**song, "patterns": {best_name: patterns[best_name]}, "order": [best_name]}
    sig = render.render(mini, seconds=None)
    S = np.abs(np.fft.rfft(sig * np.hanning(len(sig))))
    f = np.fft.rfftfreq(len(sig), 1.0 / E.SR)
    top = S.max() or 1.0
    missing = []
    for p in sorted(set(best_notes)):
        fr = E.midi_to_freq(p)
        band = (f > fr - 8) & (f < fr + 8)
        if not band.any() or S[band].max() < 0.08 * top:
            missing.append(note_name(p))
    return best_name, sorted(set(note_name(p) for p in best_notes)), missing


# ── PNG opcional (piano-roll lineal de toda la canción) ─────────────────────

def write_png(song, patterns, order, tracks, n_steps, path):
    from PIL import Image, ImageDraw
    # colores por pista (catppuccin-ish)
    pal = [(203,166,247),(137,180,250),(166,227,161),(250,179,135),
           (245,194,231),(148,226,213),(243,139,168),(249,226,175)]
    ev_all = []
    x0 = 0
    for name in order:
        grid = patterns[name]
        for e in pattern_events(grid, tracks):
            if not e["drum"]:
                ev_all.append((x0 + e["step"], e["pitch"], e["dur"], e["tr"]))
        x0 += n_steps
    if not ev_all:
        return
    total_steps = x0
    pitches = [e[1] for e in ev_all]
    hi, lo = max(pitches) + 1, min(pitches) - 1
    cw, ch = 8, 7                     # ancho de paso, alto de semitono
    W, H = total_steps * cw + 40, (hi - lo) * ch + 20
    img = Image.new("RGB", (W, H), (30, 30, 46))
    d = ImageDraw.Draw(img)
    for b in range(len(order) + 1):                     # líneas de compás
        x = 40 + b * n_steps * cw
        d.line([(x, 10), (x, H - 10)], fill=(60, 60, 80))
    for x, p, dur, tr in ev_all:
        y = 10 + (hi - p) * ch
        px = 40 + x * cw
        d.rectangle([px, y, px + dur * cw - 1, y + ch - 2], fill=pal[tr % len(pal)])
    img.save(path)
    return W, H


# ── main ────────────────────────────────────────────────────────────────────

def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    png = None
    if "--png" in sys.argv:
        i = sys.argv.index("--png")
        png = sys.argv[i + 1] if i + 1 < len(sys.argv) else "roll.png"
    if not args:
        print("uso: uv run ojos.py <cancion.json> [--png roll.png]")
        raise SystemExit(2)
    song = json.load(open(args[0], encoding="utf-8"))
    tracks = track_info(song)
    raw_pats = song.get("patterns", {})
    patterns = raw_pats if isinstance(raw_pats, dict) else {str(i): g for i, g in enumerate(raw_pats)}
    order = [str(o) for o in song.get("order", list(patterns))]
    n_steps = max((len(next(iter(g), [])) for g in patterns.values()), default=16)

    # pesos de clase de altura (por duración) para inferir tonalidad
    wpc = {}
    for grid in patterns.values():
        for e in pattern_events(grid, tracks):
            if not e["drum"]:
                wpc[e["pitch"] % 12] = wpc.get(e["pitch"] % 12, 0) + e["dur"]
    tonic, mode, fit = infer_key(wpc)

    # 1) RESUMEN
    print(f"\n╔═ OJOS · {song.get('name','?')} "
          f"────────────────────────────────────────")
    dur_s = sum(n_steps for _ in order) * (60.0 / song["bpm"] / 4.0)
    print(f"  {song['bpm']} bpm · swing {song.get('swing',0)} · {len(patterns)} patrones · "
          f"{len(order)} compases · ~{dur_s:.0f}s")
    print(f"  tonalidad probable: {T.NOTE_NAMES[tonic]} {mode}  (ajuste {fit*100:.0f}%)")
    rv = song.get("reverb")
    if isinstance(rv, dict) and rv.get("wet", 0) > 0:
        print(f"  sala (reverb): wet {rv['wet']} · room {rv.get('room', '·')} · damp {rv.get('damp', '·')}")
    pitched = [t for t in tracks if not t["drum"]]
    print("  pistas: " + "  ".join(f"{t['glyph']}={t['name']}" for t in pitched))

    # 2) ARMONÍA (la progresión)
    print("\n─ ARMONÍA (acorde por compás) " + "─" * 28)
    prog = [name_chord(bar_harmony(patterns[o], tracks, n_steps)) for o in order]
    line, chords = "  ", []
    for o, ch in zip(order, prog):
        chords.append(ch)
    print("  " + "  ".join(f"{c}" for c in chords))
    # patrón→acorde (referencia)
    seen = {}
    for o in order:
        seen[o] = name_chord(bar_harmony(patterns[o], tracks, n_steps))
    print("  patrones: " + "   ".join(f"{k}:{v}" for k, v in seen.items()))

    # 3) PIANO-ROLL por patrón único (en orden de primera aparición)
    print("\n─ PIANO-ROLL (altura × paso; letra=pista, ─=sostenido) " + "─" * 5)
    order_unique = list(dict.fromkeys(order))
    ruler = "     " + "".join(str((s // 4) % 10) if s % 4 == 0 else " " for s in range(n_steps))
    for name in order_unique:
        ch = name_chord(bar_harmony(patterns[name], tracks, n_steps))
        print(f"\n  «{name}»  [{ch}]")
        print(ruler)
        for ln in piano_roll(patterns[name], tracks, n_steps):
            print("  " + ln)

    # 4) AVISOS
    print("\n─ AVISOS " + "─" * 49)
    ws = warnings(song, tracks, patterns, tonic, mode)
    if ws:
        for x in ws:
            print("  ⚠ " + x)
    else:
        print("  ✓ sin choques de registro, saltos raros ni notas fuera de tono")

    # 5) AUDIO
    print("\n─ AUDIO (renderizado) " + "─" * 36)
    sig = render.render(song, seconds=None)
    a = render.analyze(sig)
    print(f"  {a['segundos']:.1f}s · rms {a['rms']:.3f} · pico {a['peak']:.3f} · "
          f"{'¡CLIP!' if a['clip'] else 'sin clip'}")
    bl = bar_len_samples(song, n_steps)
    bars = [sig[i*bl:(i+1)*bl] for i in range(len(order))]
    rmss = [float(np.sqrt(np.mean(b**2))) if len(b) else 0.0 for b in bars]
    print(f"  arco dinámico: {spark(rmss)}   (compás {order[int(np.argmin(rmss))]}=más suave, "
          f"{order[int(np.argmax(rmss))]}=más fuerte)")
    lo, mid, hi = band_balance(sig)
    print(f"  balance: grave {lo*100:4.0f}% · medio {mid*100:4.0f}% · agudo {hi*100:4.0f}%")
    pc = pitch_check(song, patterns, order, tracks, n_steps)
    if pc:
        name, wrote, missing = pc
        if missing:
            print(f"  ⚠ cotejo FFT en «{name}»: escribí {wrote} pero NO sonó {missing}")
        else:
            print(f"  ✓ cotejo FFT en «{name}»: sonaron las {len(wrote)} alturas que escribí ({', '.join(wrote)})")

    if png:
        r = write_png(song, patterns, order, tracks, n_steps, png)
        if r:
            print(f"\n  piano-roll PNG {r[0]}×{r[1]} -> {png}")
    print()


if __name__ == "__main__":
    main()
