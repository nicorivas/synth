"""Interfaz del sintetizador en el terminal (Textual).

Todo es clickeable con el mouse (clic + arrastre en los faders, clic en el piano)
y manejable con el teclado (Tab cambia el foco, flechas mueven el control con
foco, y las teclas tipo tracker tocan notas). Estética catppuccin mocha.
"""

from __future__ import annotations

import math
import time

import numpy as np
from rich.text import Text
from textual import events
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widget import Widget
from textual.widgets import Input, Static, TabbedContent, TabPane

import engine as E
import presets
import theory
from sequencer import Sequencer

# ---------------------------------------------------------------- colores
CBASE = "#1e1e2e"
CCRUST = "#11111b"
CTEXT = "#cdd6f4"
CSUB = "#a6adc8"
COVER = "#6c7086"
CSURF = "#45475a"
CSURF2 = "#585b70"
CMAUVE = "#cba6f7"
CLAV = "#b4befe"
CBLUE = "#89b4fa"
CTEAL = "#94e2d5"
CGREEN = "#a6e3a1"
CYELLOW = "#f9e2af"
CSKY = "#89dceb"
CDARK = "#313244"

NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

# Distribución de teclas tipo tracker: dos octavas (fila z = base, fila q = +1).
WHITE_DISPLAY = [
    ("z", 0), ("x", 2), ("c", 4), ("v", 5), ("b", 7), ("n", 9), ("m", 11),
    ("q", 12), ("w", 14), ("e", 16), ("r", 17), ("t", 19), ("y", 21), ("u", 23), ("i", 24),
]
BLACK_DISPLAY = [
    ("s", 1, 0), ("d", 3, 1), ("g", 6, 3), ("h", 8, 4), ("j", 10, 5),
    ("2", 13, 7), ("3", 15, 8), ("5", 18, 10), ("6", 20, 11), ("7", 22, 12),
]
KEYMAP = {c: s for c, s in WHITE_DISPLAY}
KEYMAP.update({c: s for c, s, _ in BLACK_DISPLAY})


def note_name(midi: int) -> str:
    return f"{NOTE_NAMES[midi % 12]}{midi // 12 - 1}"


# ================================================================ Fader
class Fader(Widget):
    """Fader vertical: clic+arrastre con el mouse, rueda, o flechas con el foco."""

    can_focus = True

    def __init__(self, label, vmin, vmax, value, fmt, setter, log=False, getter=None):
        super().__init__()
        self.label = label
        self.vmin = float(vmin)
        self.vmax = float(vmax)
        self.value = float(value)
        self.fmt = fmt
        self.setter = setter
        self.getter = getter        # relee el valor del instrumento activo
        self.logscale = log
        self._dragging = False
        self._drag_y = 0
        self._drag_frac = 0.0

    def reload(self):
        """Recargar el valor desde el instrumento seleccionado (al cambiar de pista)."""
        if self.getter is not None:
            self.value = float(self.getter())
            self.refresh()

    # --- valor <-> fracción 0..1 ---
    def _to_frac(self) -> float:
        if self.logscale:
            return (math.log(self.value) - math.log(self.vmin)) / (
                math.log(self.vmax) - math.log(self.vmin))
        return (self.value - self.vmin) / (self.vmax - self.vmin)

    def _set_frac(self, f: float):
        f = max(0.0, min(1.0, f))
        if self.logscale:
            self.value = math.exp(math.log(self.vmin) + f * (math.log(self.vmax) - math.log(self.vmin)))
        else:
            self.value = self.vmin + f * (self.vmax - self.vmin)
        self.setter(self.value)
        self.refresh()

    # --- mouse ---
    def on_mouse_down(self, event: events.MouseDown):
        self._dragging = True
        self._drag_y = event.screen_y
        self._drag_frac = self._to_frac()
        self.capture_mouse()
        self.focus()
        event.stop()

    def on_mouse_move(self, event: events.MouseMove):
        if not self._dragging:
            return
        rows = max(1, self.size.height - 2)
        dy = self._drag_y - event.screen_y          # arriba = sube
        self._set_frac(self._drag_frac + dy / rows)
        event.stop()

    def on_mouse_up(self, event: events.MouseUp):
        self._dragging = False
        self.capture_mouse(False)
        event.stop()

    def on_mouse_scroll_up(self, event):
        self._set_frac(self._to_frac() + 0.04)
        event.stop()

    def on_mouse_scroll_down(self, event):
        self._set_frac(self._to_frac() - 0.04)
        event.stop()

    # --- teclado ---
    def on_key(self, event: events.Key):
        k = event.key
        if k in ("up", "right"):
            self._set_frac(self._to_frac() + 0.02); event.stop()
        elif k in ("down", "left"):
            self._set_frac(self._to_frac() - 0.02); event.stop()
        elif k == "pageup":
            self._set_frac(self._to_frac() + 0.1); event.stop()
        elif k == "pagedown":
            self._set_frac(self._to_frac() - 0.1); event.stop()
        elif k == "home":
            self._set_frac(1.0); event.stop()
        elif k == "end":
            self._set_frac(0.0); event.stop()
        # cualquier otra tecla (notas, etc.) burbujea hasta la App

    def render(self) -> Text:
        w, h = self.size.width, self.size.height
        if w < 2 or h < 3:
            return Text("")
        focus = self.has_focus
        frac = self._to_frac()
        rows = h - 2
        handle = round((1 - frac) * (rows - 1))
        col = w // 2

        lab_color = CYELLOW if focus else CSUB
        out = Text()
        out.append(self.label[:w].center(w) + "\n", style=lab_color)
        for r in range(rows):
            line = [" "] * w
            line[col] = "│"
            style = CSURF
            if r > handle:
                style = CSKY                       # parte "llena" bajo el pomo
            if r == handle:
                line[col] = "◆"
                style = CYELLOW if focus else CBLUE
            out.append("".join(line), style=style)
            out.append("\n")
        out.append(self.fmt(self.value).center(w), style=lab_color)
        return out


# ============================================================ WaveSelector
class WaveSelector(Widget):
    can_focus = True
    GLYPHS = ["seno", "triáng", "sierra", "cuadr"]

    def __init__(self, value, setter, getter=None, title="Onda", options=None):
        super().__init__()
        self.value = int(value)
        self.setter = setter
        self.getter = getter
        self.title = title
        self.options = options if options is not None else self.GLYPHS

    def reload(self):
        if self.getter is not None:
            self.value = int(self.getter())
            self.refresh()

    def _set(self, v):
        self.value = v % len(self.options)
        self.setter(self.value)
        self.refresh()

    def on_mouse_down(self, event: events.MouseDown):
        idx = event.y - 1
        if 0 <= idx < len(self.options):
            self._set(idx)
        self.focus()
        event.stop()

    def on_key(self, event: events.Key):
        k = event.key
        if k in ("up", "left"):
            self._set(self.value - 1); event.stop()
        elif k in ("down", "right"):
            self._set(self.value + 1); event.stop()

    def render(self) -> Text:
        w = self.size.width
        focus = self.has_focus
        out = Text()
        out.append(self.title.center(w) + "\n", style=CYELLOW if focus else CSUB)
        for i, name in enumerate(self.options):
            sel = i == self.value
            mark = "▸" if sel else " "
            txt = f"{mark} {name}"
            if sel:
                style = f"bold {CYELLOW if focus else CGREEN}"
            else:
                style = COVER
            out.append(txt.ljust(w)[:w] + "\n", style=style)
        return out


# ============================================================== HPicker
class HPicker(Widget):
    """Selector horizontal: una fila de opciones, la elegida resaltada. Clic o
    ←→. Para la tonalidad (tónica de 12, escala, tríada/séptima…). Lee y escribe
    por getter/setter, así refleja el estado de la app en vivo."""
    can_focus = True

    def __init__(self, title, options, getter, setter):
        super().__init__()
        self.title = title
        self.options = options
        self.getter = getter
        self.setter = setter
        self._cell = max(len(o) for o in options) + 2

    def reload(self):
        self.refresh()

    def _set(self, v):
        self.setter(v % len(self.options))
        self.refresh()

    def on_mouse_down(self, event: events.MouseDown):
        idx = event.x // self._cell
        if 0 <= idx < len(self.options):
            self._set(idx)
        self.focus()
        event.stop()

    def on_key(self, event: events.Key):
        k = event.key
        if k in ("left", "up"):
            self._set(self.getter() - 1); event.stop()
        elif k in ("right", "down"):
            self._set(self.getter() + 1); event.stop()

    def render(self) -> Text:
        w = self.size.width
        focus = self.has_focus
        cur = self.getter()
        out = Text()
        out.append(self.title.ljust(w)[:w] + "\n", style=CYELLOW if focus else CSUB)
        line = Text()
        for i, o in enumerate(self.options):
            cell = o.center(self._cell)
            if i == cur:
                line.append(cell, style=f"bold {CBASE} on {CYELLOW if focus else CGREEN}")
            else:
                line.append(cell, style=COVER)
        out.append(line)
        return out


# ================================================================ Scope
class Scope(Widget):
    """Osciloscopio: dibuja el último bloque de audio con puntos braille."""
    can_focus = False

    def __init__(self, eng: E.Engine):
        super().__init__()
        self.eng = eng

    def render(self) -> Text:
        w, h = self.size.width, self.size.height
        if w < 2 or h < 2:
            return Text("")
        gw, gh = w * 2, h * 4          # rejilla de puntos braille
        cells = [[0] * w for _ in range(h)]
        buf = self.eng.scope
        n = len(buf)
        for gx in range(gw):
            idx = int(gx / gw * (n - 1))
            v = float(buf[idx])
            v = max(-1.0, min(1.0, v))
            gy = int((0.5 - v * 0.46) * (gh - 1))
            cx, cy = gx // 2, gy // 4
            bit = _BRAILLE[(gy % 4) * 2 + (gx % 2)]
            cells[cy][cx] |= bit
        out = Text()
        for row in cells:
            for b in row:
                out.append(chr(0x2800 + b) if b else " ", style=CTEAL)
            out.append("\n")
        return out


# dot bits braille: (fila 0..3, col 0..1) -> bit
_BRAILLE = [0x01, 0x08, 0x02, 0x10, 0x04, 0x20, 0x40, 0x80]


# ================================================================ EnvViz
class EnvViz(Widget):
    """Gráfico de envolvente (ADSR) en braille, como el de los sintes con GUI.
    Dibuja las dos envolventes a la vez —amplitud (verde) y filtro (azul)— sobre
    un eje de tiempo común, para que se vea cuál es más rápida. Abajo, la escala
    total en segundos. Se redibuja al mover los faders, no con el audio."""
    can_focus = False

    def __init__(self, eng: E.Engine):
        super().__init__()
        self.eng = eng

    @staticmethod
    def _seg(p: float, v0: float, v1: float, curve: float = 3.5) -> float:
        """Tramo exponencial (un polo) de v0 a v1, con p en [0,1]."""
        p = 0.0 if p < 0 else 1.0 if p > 1 else p
        k = (1.0 - math.exp(-curve * p)) / (1.0 - math.exp(-curve))
        return v0 + (v1 - v0) * k

    def _levels(self, a, d, s, r, gw, pps, sus_w):
        """Nivel [0,1] de la envolvente para cada columna de puntos."""
        aw, dw, rw = a * pps, d * pps, r * pps
        out = []
        for gx in range(gw):
            if gx < aw:
                v = self._seg(gx / aw if aw else 1.0, 0.0, 1.0)
            elif gx < aw + dw:
                v = self._seg((gx - aw) / dw if dw else 1.0, 1.0, s)
            elif gx < aw + dw + sus_w:
                v = s
            elif gx < aw + dw + sus_w + rw:
                v = self._seg((gx - aw - dw - sus_w) / rw if rw else 1.0, s, 0.0)
            else:
                v = 0.0
            out.append(v)
        return out

    def _raster(self, levels, gw, gh, w, h):
        """Enciende los puntos braille de una curva, conectando columnas vecinas."""
        cells = [[0] * w for _ in range(h)]
        prev = None
        for gx in range(gw):
            gy = int((1.0 - max(0.0, min(1.0, levels[gx])) * 0.94) * (gh - 1))
            ys = (gy,) if prev is None else range(min(prev, gy), max(prev, gy) + 1)
            for yy in ys:
                cx, cy = gx // 2, yy // 4
                if 0 <= cy < h and 0 <= cx < w:
                    cells[cy][cx] |= _BRAILLE[(yy % 4) * 2 + (gx % 2)]
            prev = gy
        return cells

    def render(self) -> Text:
        w, h = self.size.width, self.size.height
        if w < 2 or h < 2:
            return Text("")
        gw, gh = w * 2, h * 4
        p = self.eng.params
        tot_amp = p.amp_attack + p.amp_decay + p.amp_release
        tot_flt = p.flt_attack + p.flt_decay + p.flt_release
        sus = 0.28 * max(tot_amp, tot_flt, 0.05)      # ancho del tramo de sustain
        t_max = max(tot_amp, tot_flt, 1e-3) + sus
        pps = (gw - 1) / t_max                         # puntos por segundo (escala común)
        sus_w = sus * pps
        amp = self._raster(self._levels(p.amp_attack, p.amp_decay, p.amp_sustain,
                                        p.amp_release, gw, pps, sus_w), gw, gh, w, h)
        flt = self._raster(self._levels(p.flt_attack, p.flt_decay, p.flt_sustain,
                                        p.flt_release, gw, pps, sus_w), gw, gh, w, h)
        self.border_subtitle = f"[{CGREEN}]amp[/]  [{CBLUE}]filtro[/]  ·  {t_max:.2f}s"
        out = Text()
        for cy in range(h):
            for cx in range(w):
                ab, fb = amp[cy][cx], flt[cy][cx]
                b = ab | fb
                if not b:
                    out.append(" ")
                else:
                    color = CTEXT if (ab and fb) else (CGREEN if ab else CBLUE)
                    out.append(chr(0x2800 + b), style=color)
            out.append("\n")
        return out


# ================================================================ LfoViz
class LfoViz(Widget):
    """Dibuja la onda del LFO del instrumento seleccionado, con un cursor que la
    recorre según su fase: ves la modulación moviéndose en vivo."""
    can_focus = False

    def __init__(self, eng: E.Engine):
        super().__init__()
        self.eng = eng

    def render(self) -> Text:
        w, h = self.size.width, self.size.height
        if w < 2 or h < 2:
            return Text("")
        p = self.eng.params
        inst = self.eng.instruments[self.eng.sel]
        active = (p.kind == E.INST_SYNTH and p.lfo_dest != E.LFO_OFF and p.lfo_depth > 0.0)
        wave_color = CMAUVE if active else COVER
        gw, gh = w * 2, h * 4
        vals = E._lfo_array(p.lfo_shape, np.arange(gw) / gw)   # un ciclo a lo ancho
        cells = [[0] * w for _ in range(h)]
        for gx in range(gw):
            gy = int((0.5 - float(vals[gx]) * 0.46) * (gh - 1))
            cells[gy // 4][gx // 2] |= _BRAILLE[(gy % 4) * 2 + (gx % 2)]
        # la fase de la capa que se está editando (A o B)
        phase = (inst.lfo_phase_b if self.eng.edit_b and inst.params_b is not None
                 else inst.lfo_phase)
        cursor = int((phase % 1.0) * w) if active else -1
        out = Text()
        for cy in range(h):
            for cx in range(w):
                b = cells[cy][cx]
                if cx == cursor:
                    out.append(chr(0x2800 + b) if b else "┊", style=CYELLOW)
                elif b:
                    out.append(chr(0x2800 + b), style=wave_color)
                else:
                    out.append(" ")
            out.append("\n")
        return out


# ================================================================ EqPad
class EqPad(Widget):
    """El ecualizador, en la pantalla principal: una barra por banda (±12 dB
    desde la línea de 0), clickeable y arrastrable, con la respuesta total del
    patch (pasa-bajos × eq) dibujada detrás —ahí se ve al cutoff arrastrar los
    niveles. Teclado: ←→ elige banda, ↑↓ sube/baja (PgUp/PgDn a saltos,
    Home la deja plana)."""
    can_focus = True

    LABELS = ["63", "125", "250", "500", "1k", "2k", "4k", "8k"]

    def __init__(self, eng: E.Engine):
        super().__init__()
        self.eng = eng
        self.band = 0
        self._dragging = False

    def reload(self):
        self.refresh()

    # --- estado ---
    def _gains(self) -> list:
        eq = self.eng.params.eq
        return [float(eq[i]) if i < len(eq) else 0.0
                for i in range(len(E.EQ_BANDS))]

    def _set_gain(self, band: int, g: float):
        self.band = max(0, min(len(E.EQ_BANDS) - 1, band))
        eq = self.eng.params.eq
        while len(eq) < len(E.EQ_BANDS):
            eq.append(0.0)
        eq[self.band] = float(max(-E.EQ_RANGE_DB,
                                  min(E.EQ_RANGE_DB, round(g))))
        self.refresh()

    def _cols(self) -> int:
        return max(2, self.size.width // len(E.EQ_BANDS))

    def _gain_at(self, y: int) -> float:
        rows = max(2, self.size.height - 1)      # la última fila es de etiquetas
        mid = (rows - 1) / 2.0
        return (mid - y) / max(mid, 1e-6) * E.EQ_RANGE_DB

    # --- mouse: clic/arrastre pone la banda en ese nivel; rueda ±1 dB ---
    def on_mouse_down(self, event: events.MouseDown):
        self._dragging = True
        self.capture_mouse()
        self._set_gain(event.x // self._cols(), self._gain_at(event.y))
        self.focus()
        event.stop()

    def on_mouse_move(self, event: events.MouseMove):
        if self._dragging:
            self._set_gain(event.x // self._cols(), self._gain_at(event.y))
            event.stop()

    def on_mouse_up(self, event: events.MouseUp):
        self._dragging = False
        self.capture_mouse(False)
        event.stop()

    def on_mouse_scroll_up(self, event):
        b = event.x // self._cols()
        self._set_gain(b, self._gains()[min(b, 7)] + 1)
        event.stop()

    def on_mouse_scroll_down(self, event):
        b = event.x // self._cols()
        self._set_gain(b, self._gains()[min(b, 7)] - 1)
        event.stop()

    # --- teclado ---
    def on_key(self, event: events.Key):
        k = event.key
        g = self._gains()
        if k == "left":
            self.band = max(0, self.band - 1); self.refresh(); event.stop()
        elif k == "right":
            self.band = min(len(E.EQ_BANDS) - 1, self.band + 1)
            self.refresh(); event.stop()
        elif k == "up":
            self._set_gain(self.band, g[self.band] + 1); event.stop()
        elif k == "down":
            self._set_gain(self.band, g[self.band] - 1); event.stop()
        elif k == "pageup":
            self._set_gain(self.band, g[self.band] + 3); event.stop()
        elif k == "pagedown":
            self._set_gain(self.band, g[self.band] - 3); event.stop()
        elif k == "home":
            self._set_gain(self.band, 0.0); event.stop()

    def render(self) -> Text:
        w, h = self.size.width, self.size.height
        if w < 10 or h < 3:
            return Text("")
        p = self.eng.params
        gains = self._gains()
        focus = self.has_focus
        rows = h - 1
        gh, gw, cw = rows * 4, w * 2, self._cols()
        mid = (gh - 1) / 2.0

        # la respuesta total (misma matemática del motor), de fondo
        f = np.geomspace(40.0, 16000.0, gw)
        z = np.exp(-1j * 2.0 * np.pi * f / E.SR)

        def mag(ba):
            b, a = ba
            return np.abs((b[0] + b[1] * z + b[2] * z * z) /
                          (1.0 + a[1] * z + a[2] * z * z))

        resp = mag(E._biquad_lowpass(p.cutoff, p.resonance))
        for i, fc in enumerate(E.EQ_BANDS):
            if abs(gains[i]) >= 0.05:
                resp = resp * mag(E._biquad_peaking(fc, E.EQ_Q, gains[i]))
        db = 20.0 * np.log10(np.maximum(resp, 1e-6))
        lvl = np.clip((db + 24.0) / 36.0, 0.0, 1.0)   # -24..+12 dB a 0..1

        curva = [[0] * w for _ in range(rows)]
        prev = None
        for gx in range(gw):
            gy = int((1.0 - lvl[gx]) * (gh - 1))
            ys = (gy,) if prev is None else range(min(prev, gy), max(prev, gy) + 1)
            for yy in ys:
                curva[yy // 4][gx // 2] |= _BRAILLE[(yy % 4) * 2 + (gx % 2)]
            prev = gy

        # las barras: desde la línea de 0 dB hacia arriba o abajo
        barras = [[0] * w for _ in range(rows)]
        dueno = [[-1] * w for _ in range(rows)]       # qué banda pinta la celda
        for i, g in enumerate(gains):
            x0 = i * cw + max(0, (cw - 2) // 2)
            dots = int(round(abs(g) / E.EQ_RANGE_DB * mid))
            lo, hi = (int(mid) - dots, int(mid)) if g >= 0 else \
                     (int(mid), int(mid) + dots)
            for gy in range(max(0, lo), min(gh, hi + 1)):
                bit = _BRAILLE[(gy % 4) * 2] | _BRAILLE[(gy % 4) * 2 + 1]
                for cx in range(x0, min(x0 + 2, w)):
                    barras[gy // 4][cx] |= bit
                    dueno[gy // 4][cx] = i

        ins = self.eng.instruments[self.eng.sel]
        capa = " · B" if (self.eng.edit_b and ins.params_b is not None) else ""
        self.border_title = f"eq · {ins.name}{capa}"
        self.border_subtitle = f"{self.LABELS[self.band]} Hz · {gains[self.band]:+.0f} dB"
        fila_cero = int(mid) // 4
        out = Text()
        for cy in range(rows):
            for cx in range(w):
                if barras[cy][cx]:
                    sel = dueno[cy][cx] == self.band
                    color = CYELLOW if (focus and sel) else (CTEAL if sel else CBLUE)
                    out.append(chr(0x2800 + (barras[cy][cx] | curva[cy][cx])),
                               style=color)
                elif curva[cy][cx]:
                    out.append(chr(0x2800 + curva[cy][cx]), style=COVER)
                elif cy == fila_cero:
                    out.append("·", style=CSURF)
                else:
                    out.append(" ")
            out.append("\n")
        for i, lb in enumerate(self.LABELS):      # etiquetas de las bandas
            sel = i == self.band
            out.append(lb.center(cw)[:cw],
                       style=(CYELLOW if focus else CGREEN) if sel else CSUB)
        return out


# ================================================================ Piano
class Piano(Widget):
    can_focus = False

    def __init__(self, eng: E.Engine):
        super().__init__()
        self.eng = eng
        self._whites = []   # (x0, x1, midi, label)
        self._blacks = []   # (x0, x1, midi, label)
        self._pressed = None

    def _layout(self, w, h):
        oct_base = 12 * (self.app.base_octave + 1)
        kw = max(2, w // 15)
        gap = 1 if kw >= 4 else 0
        cw = kw - gap
        whites, blacks = [], []
        for i, (ch, semi) in enumerate(WHITE_DISPLAY):
            x0 = i * kw
            whites.append((x0, x0 + cw, oct_base + semi, ch))
        wb = max(2, cw - 1)
        for ch, semi, after in BLACK_DISPLAY:
            center = (after + 1) * kw
            x0 = center - wb // 2
            blacks.append((x0, x0 + wb, oct_base + semi, ch))
        self._whites, self._blacks = whites, blacks
        return whites, blacks

    def _note_at(self, x, y):
        bh = max(1, self.size.height * 3 // 5)
        if y < bh:
            for x0, x1, midi, _ in self._blacks:
                if x0 <= x < x1:
                    return midi
        for x0, x1, midi, _ in self._whites:
            if x0 <= x < x1:
                return midi
        return None

    def on_mouse_down(self, event: events.MouseDown):
        midi = self._note_at(event.x, event.y)
        if midi is not None:
            self.eng.note_on(midi)
            self._pressed = midi
            self.capture_mouse()
            self.refresh()
        event.stop()

    def on_mouse_move(self, event: events.MouseMove):
        if self._pressed is None:
            return
        midi = self._note_at(event.x, event.y)
        if midi is not None and midi != self._pressed:
            self.eng.note_off(self._pressed)
            self.eng.note_on(midi)
            self._pressed = midi
            self.refresh()
        event.stop()

    def on_mouse_up(self, event: events.MouseUp):
        if self._pressed is not None:
            self.eng.note_off(self._pressed)
            self._pressed = None
            self.capture_mouse(False)
            self.refresh()
        event.stop()

    def render(self) -> Text:
        w, h = self.size.width, self.size.height
        if w < 4 or h < 2:
            return Text("")
        whites, blacks = self._layout(w, h)
        active = set(self.eng.active_notes())
        bh = max(1, h * 3 // 5)
        tonic, mode = self.app.tonic, self.app.mode   # tonalidad: resalta la escala

        # rejilla de celdas (char, fg, bg)
        grid = [[(" ", CBASE, CBASE) for _ in range(w)] for _ in range(h)]

        # teclas blancas (cuerpo completo); las de fuera de la escala, atenuadas
        for x0, x1, midi, label in whites:
            if midi in active:
                bg = CGREEN
            elif theory.in_scale(midi, tonic, mode):
                bg = CTEXT
            else:
                bg = COVER
            for y in range(h):
                for x in range(x0, min(x1, w)):
                    grid[y][x] = (" ", CBASE, bg)
            lx = (x0 + min(x1, w) - 1) // 2
            if 0 <= lx < w:
                grid[h - 1][lx] = (label, CBASE, bg)

        # teclas negras (encima); en la escala, un punto más claras que las de fuera
        for x0, x1, midi, label in blacks:
            if midi in active:
                bg = CTEAL
            elif theory.in_scale(midi, tonic, mode):
                bg = CSURF2
            else:
                bg = CDARK
            for y in range(bh):
                for x in range(max(0, x0), min(x1, w)):
                    grid[y][x] = (" ", CTEXT, bg)
            lx = (max(0, x0) + min(x1, w) - 1) // 2
            if 0 <= lx < w and bh >= 1:
                grid[bh - 1][lx] = (label, CTEXT, bg)

        out = Text()
        for row in grid:
            for ch, fg, bg in row:
                out.append(ch, style=f"{fg} on {bg}")
            out.append("\n")
        return out


# ================================================================ SeqGrid
class SeqGrid(Widget):
    """Grilla del secuenciador: filas = instrumentos, columnas = pasos. Resalta
    el cursor de edición y el playhead. Clic enciende/apaga; el teclado mueve el
    cursor, alterna pasos y cambia la nota."""
    can_focus = True
    LABEL_W = 7

    def __init__(self, seq, engine):
        super().__init__()
        self.seq = seq
        self.engine = engine
        self.cur_track = 1
        self.cur_step = 0
        # capas plegables: agrupan pistas para trabajar ritmo o melodía por separado
        self.groups = [
            {"name": "ritmo", "tracks": [1, 3, 4, 5], "collapsed": False},  # bajo+batería
            {"name": "melódico", "tracks": [0, 2], "collapsed": False},     # lead, pad
        ]
        self._rowmap = []   # fila de pantalla -> ("steps",) | ("header", gi) | ("track", tr)

    def _visible_tracks(self):
        out = []
        for g in self.groups:
            if not g["collapsed"]:
                out.extend(g["tracks"])
        return out

    def _fix_cursor(self):
        vis = self._visible_tracks()
        if vis and self.cur_track not in vis:
            self.cur_track = vis[0]
            self.app.select_instrument(self.cur_track)

    def _step_w(self, w):
        return max(2, (w - self.LABEL_W) // self.seq.n_steps)

    # --- mouse ---
    def on_mouse_down(self, event: events.MouseDown):
        y = event.y
        if 0 <= y < len(self._rowmap):
            kind = self._rowmap[y]
            if kind[0] == "header":                          # clic en la capa: plegar
                g = self.groups[kind[1]]
                g["collapsed"] = not g["collapsed"]
                self._fix_cursor()
            elif kind[0] == "track":
                tr = kind[1]
                self.cur_track = tr
                self.app.select_instrument(tr)
                if event.x >= self.LABEL_W:
                    st = (event.x - self.LABEL_W) // self._step_w(self.size.width)
                    if 0 <= st < self.seq.n_steps:
                        self.cur_step = st
                        self.seq.toggle(tr, st)
            self.focus()
            self.refresh()
            self.app.update_seq_status()
        event.stop()

    # --- teclado (solo cuando la grilla tiene foco) ---
    def on_key(self, event: events.Key):
        k = event.key
        seq = self.seq
        if k == "right":
            self.cur_step = (self.cur_step + 1) % seq.n_steps
        elif k == "left":
            self.cur_step = (self.cur_step - 1) % seq.n_steps
        elif k in ("down", "up"):
            vis = self._visible_tracks()
            if vis:
                i = vis.index(self.cur_track) if self.cur_track in vis else 0
                i = (i + (1 if k == "down" else -1)) % len(vis)
                self.cur_track = vis[i]
                self.app.select_instrument(self.cur_track)
        elif k == "backslash":                # plegar/desplegar la capa actual
            for g in self.groups:
                if self.cur_track in g["tracks"]:
                    g["collapsed"] = not g["collapsed"]
                    self._fix_cursor()
                    break
        elif k == "enter":
            seq.toggle(self.cur_track, self.cur_step)
        elif k == "right_square_bracket":      # ]  sube un semitono
            seq.shift_note(self.cur_track, self.cur_step, 1)
        elif k == "left_square_bracket":       # [  baja un semitono
            seq.shift_note(self.cur_track, self.cur_step, -1)
        elif k == "pageup":
            seq.shift_note(self.cur_track, self.cur_step, 12)
        elif k == "pagedown":
            seq.shift_note(self.cur_track, self.cur_step, -12)
        elif k == "full_stop":                 # .  acelera el tempo
            seq.bpm = min(300, seq.bpm + 2)
        elif k == "comma":                     # ,  desacelera
            seq.bpm = max(40, seq.bpm - 2)
        else:
            return                             # otras teclas burbujean (space=play, etc.)
        event.stop()
        self.refresh()
        self.app.update_seq_status()

    def render(self) -> Text:
        w, h = self.size.width, self.size.height
        if w < self.LABEL_W + 4 or h < 3:
            self._rowmap = []
            return Text("")
        seq = self.seq
        sw = self._step_w(w)
        vis = self._visible_tracks()
        avail = h - 1 - len(self.groups)                  # menos cabecera de pasos y headers
        rh = max(1, min(4, avail // max(1, len(vis)))) if vis else 1
        rowmap = [("steps",)]
        out = Text()
        # cabecera: número de paso cada 4 (1, 5, 9, 13)
        out.append(" " * self.LABEL_W, style=CSUB)
        for st in range(seq.n_steps):
            head = f"{st + 1}".ljust(sw)[:sw] if st % 4 == 0 else " " * sw
            out.append(head, style=CYELLOW if (seq.playing and st == seq.pos) else COVER)
        out.append("\n")
        # cada capa: una barra de encabezado plegable + sus pistas (si está abierta)
        for gi, g in enumerate(self.groups):
            arrow = "▾" if not g["collapsed"] else "▸"
            n = len(g["tracks"])
            title = f" {arrow} {g['name']}  ({n} pistas)" if g["collapsed"] else f" {arrow} {g['name']}"
            out.append(title.ljust(w)[:w], style=f"bold {CMAUVE} on {CDARK}")
            out.append("\n"); rowmap.append(("header", gi))
            if g["collapsed"]:
                continue
            for tr in g["tracks"]:
                inst = self.engine.instruments[tr]
                on_color = CTEAL if inst.params.kind == E.INST_DRUM else CGREEN
                sel_track = tr == self.cur_track
                mid = rh // 2
                for rr in range(rh):
                    label = (inst.name[:self.LABEL_W - 1].ljust(self.LABEL_W)
                             if rr == mid else " " * self.LABEL_W)
                    out.append(label, style=f"bold {CLAV}" if sel_track else CSUB)
                    for st in range(seq.n_steps):
                        note = seq.grid[tr][st]
                        on = note is not None
                        is_cur = sel_track and st == self.cur_step
                        is_play = seq.playing and st == seq.pos
                        txt = ((note_name(note) if on else "·").center(sw)[:sw]
                               if rr == mid else " " * sw)
                        if is_cur:
                            style = f"{CBASE} on {CYELLOW}"      # celda seleccionada
                        elif on:
                            style = f"{on_color} on {CDARK}"     # bloque encendido + nota
                        elif is_play:
                            style = f"{COVER} on {CSURF}"        # columna que suena
                        else:
                            style = COVER
                        out.append(txt, style=style)
                    out.append("\n"); rowmap.append(("track", tr))
        self._rowmap = rowmap
        return out


# ============================================================ PresetList
class PresetList(Widget):
    """Lista de presets guardados. Clic o ↑↓+Enter para cargar; `d` borra (con
    una confirmación: hay que pulsar `d` dos veces). Sigue el patrón de los demás
    widgets dibujados a mano."""
    can_focus = True

    def __init__(self):
        super().__init__()
        self.items = []            # [{"label", "key"}]
        self.cur = 0
        self._confirm = None       # key con borrado pendiente de confirmar

    def reload(self):
        self.items = presets.available()
        self.cur = max(0, min(self.cur, len(self.items) - 1))
        self._confirm = None
        self.refresh()

    def on_mouse_down(self, event: events.MouseDown):
        idx = event.y - 1          # fila 0 = título
        if 0 <= idx < len(self.items):
            self.cur = idx
            self._confirm = None
            self.app.load_preset(self.items[idx]["key"])
        self.focus()
        event.stop()

    def on_key(self, event: events.Key):
        k = event.key
        if not self.items:
            return
        if k == "up":
            self.cur = (self.cur - 1) % len(self.items); self._confirm = None
        elif k == "down":
            self.cur = (self.cur + 1) % len(self.items); self._confirm = None
        elif k == "enter":
            self._confirm = None
            self.app.load_preset(self.items[self.cur]["key"])
        elif k in ("d", "delete"):
            item = self.items[self.cur]
            if self._confirm == item["key"]:
                self._confirm = None
                self.app.delete_preset(item["key"])
            else:
                self._confirm = item["key"]
                self.app.set_preset_msg(f"¿borrar '{item['label']}'? pulsa d otra vez")
        else:
            return                 # otras teclas burbujean (notas, space=play…)
        event.stop()
        self.refresh()

    def render(self) -> Text:
        w, h = self.size.width, self.size.height
        focus = self.has_focus
        out = Text()
        out.append("guardados".ljust(w)[:w] + "\n", style=CYELLOW if focus else CSUB)
        if not self.items:
            out.append("  (aún no hay presets — guarda uno arriba)\n", style=COVER)
            return out
        for i, it in enumerate(self.items):
            sel = i == self.cur
            pending = self._confirm == it["key"]
            mark = "▸" if sel else " "
            txt = f" {mark} {it['label']}"
            if pending:
                txt += "   · borrar?"
                style = f"bold {CYELLOW}"
            elif sel:
                style = f"bold {CYELLOW if focus else CGREEN}"
            else:
                style = CSUB
            out.append(txt.ljust(w)[:w] + "\n", style=style)
        return out


# ================================================================ Panel
class Panel(Horizontal):
    def __init__(self, title, *children):
        super().__init__(*children, classes="panel")
        self._title = title

    def on_mount(self):
        self.border_title = self._title


# ================================================================ App
def _fmt_hz(v):
    return f"{v/1000:.1f}k" if v >= 1000 else f"{v:.0f}"


def _fmt_s(v):
    return f"{v*1000:.0f}ms" if v < 1 else f"{v:.2f}s"


def _fmt_pct(v):
    return f"{v*100:.0f}%"


GATE_TIMEOUT = 0.4   # s sin repetición de tecla -> soltar la nota


class SynthApp(App):
    CSS = f"""
    Screen {{ background: {CBASE}; color: {CTEXT}; }}
    #title {{ height: 1; background: {CCRUST}; color: {CMAUVE}; text-style: bold; padding: 0 1; }}
    #status {{ height: 1; background: {CCRUST}; color: {CSUB}; padding: 0 1; }}
    TabbedContent {{ height: 1fr; }}
    .rackrow {{ height: 7; padding: 0 1; }}
    #rack-drum {{ display: none; }}   /* visible solo con un tambor seleccionado */
    .panel {{ height: 7; border: round {CSURF}; border-title-color: {CLAV};
              padding: 0 1; margin: 0 1 0 0; width: auto; }}
    Fader {{ width: 7; height: 5; }}
    WaveSelector {{ width: 10; height: 5; }}
    .visrow {{ height: 1fr; }}
    #scope {{ width: 1fr; border: round {CSURF}; border-title-color: {CLAV};
              margin: 1 1 0 2; }}
    #lfoviz {{ width: 11; height: 5; }}
    #panel-layer WaveSelector {{ width: 7; }}
    #panel-layer Fader {{ width: 6; }}
    #eqpad {{ width: 36; border: round {CSURF}; border-title-color: {CLAV};
              border-subtitle-color: {CSUB}; margin: 1 2 0 1; }}
    #envviz {{ width: 2fr; border: round {CSURF}; border-title-color: {CLAV};
               border-subtitle-color: {CSUB}; margin: 1 2 0 1; }}
    #piano {{ height: 4; margin: 1 2 0 2; }}
    #seqgrid {{ height: 1fr; margin: 1 2; }}
    #seqbar {{ height: 1; background: {CCRUST}; color: {CSUB}; padding: 0 1; }}
    #preset-name {{ margin: 1 2 0 2; border: round {CSURF}; background: {CCRUST};
                    color: {CTEXT}; }}
    #preset-name:focus {{ border: round {CLAV}; }}
    #preset-list {{ height: 1fr; margin: 1 2; }}
    #preset-msg {{ height: 1; background: {CCRUST}; color: {CSUB}; padding: 0 1; }}
    .tonalrow {{ height: 3; margin: 1 2 0 2; }}
    HPicker {{ height: 3; width: auto; margin: 0 3 0 0; }}
    #chord-overview {{ height: 1fr; border: round {CSURF}; border-title-color: {CLAV};
                       margin: 1 2; padding: 1 2; }}
    #tonal-help {{ height: 1; background: {CCRUST}; color: {CSUB}; padding: 0 1; }}
    #help {{ height: 1; color: {COVER}; padding: 0 1; }}
    """

    BINDINGS = [
        Binding("ctrl+c", "quit", "Salir", priority=True),
        Binding("ctrl+q", "quit", "Salir"),
        Binding("space", "playstop", "Play/Stop"),
        Binding("escape", "panic", "Pánico"),
    ]

    def __init__(self):
        super().__init__()
        self.engine = E.Engine()
        self.seq = Sequencer(self.engine)
        self.base_octave = 4
        # tonalidad (composición): tónica 0..11, escala, tríada/séptima, y si la
        # fila 1..7 toca acordes diatónicos (en vez de las negras de esa octava)
        self.tonic = 0            # Do
        self.mode = "mayor"
        self.sevenths = False
        self.chords_on = True
        self._kbd = {}   # midi -> última vez visto (para soltar al dejar de repetir)
        self._last_active = ()  # notas activas en el tick previo (para repintar el piano solo al cambiar)
        self._last_env = None   # params de envolvente en el tick previo (para repintar la curva al cambiar)
        self._last_eq = None    # (cutoff, res, eq) en el tick previo (ídem, curva del eq)

    def compose(self) -> ComposeResult:
        yield Static("♪  kichoro · synth", id="title")
        eng = self.engine

        # los controles apuntan al instrumento SELECCIONADO (eng.params es dinámico)
        # y saben releerse al cambiar de pista (getter)
        def setp(name):
            return lambda v, n=name: setattr(eng.params, n, v)

        def getp(name):
            return lambda n=name: getattr(eng.params, n)

        def fdr(name, label, lo, hi, fmt, log=False):
            return Fader(label, lo, hi, getattr(eng.params, name), fmt,
                         setp(name), log=log, getter=getp(name))

        def sel(name, title, options):
            return WaveSelector(getattr(eng.params, name), setp(name),
                                getter=getp(name), title=title, options=options)

        osc = Panel("osc",
            WaveSelector(eng.params.wave, setp("wave"), getter=getp("wave")),
            fdr("detune", "Det", 0, 50, lambda v: f"{v:.0f}c"),
            fdr("pulse_width", "PW", 0.05, 0.95, _fmt_pct))
        filt = Panel("filtro",
            fdr("cutoff", "Cut", 20, 18000, _fmt_hz, log=True),
            fdr("resonance", "Res", 0.3, 14, lambda v: f"{v:.1f}"),
            fdr("env_to_cutoff", "E→F", 0, 1, _fmt_pct))
        ampvol = Panel("amp", fdr("volume", "Vol", 0, 1, _fmt_pct))
        ampenv = Panel("amp · env",
            fdr("amp_attack", "Atk", 0.001, 3, _fmt_s, log=True),
            fdr("amp_decay", "Dec", 0.005, 3, _fmt_s, log=True),
            fdr("amp_sustain", "Sus", 0, 1, _fmt_pct),
            fdr("amp_release", "Rel", 0.005, 4, _fmt_s, log=True))
        fltenv = Panel("filtro · env",
            fdr("flt_attack", "Atk", 0.001, 3, _fmt_s, log=True),
            fdr("flt_decay", "Dec", 0.005, 3, _fmt_s, log=True),
            fdr("flt_sustain", "Sus", 0, 1, _fmt_pct),
            fdr("flt_release", "Rel", 0.005, 4, _fmt_s, log=True))
        # capa B (solo instrumentos con layer, hoy el lead): activarla y elegir
        # cuál capa edita el rack completo (eng.params es dinámico también en esto).
        # Semi/Fine afinan la capa que se edita: octava/quinta arriba, o unos
        # cents para desafinarlas entre sí.
        layer = Panel("capa B",
            WaveSelector(0, self._set_layer_on,
                         getter=lambda: 1 if eng.instruments[eng.sel].layer_on else 0,
                         title="Capa", options=["off", "on"]),
            WaveSelector(0, self._set_edit_layer,
                         getter=lambda: 1 if eng.edit_b else 0,
                         title="Editar", options=["A", "B"]),
            Fader("Semi", -24, 24, eng.params.transpose, lambda v: f"{v:+.0f}",
                  lambda v: setattr(eng.params, "transpose", float(round(v))),
                  getter=getp("transpose")),
            fdr("fine", "Fine", -50, 50, lambda v: f"{v:+.0f}c"))
        layer.id = "panel-layer"

        lfoviz = LfoViz(eng); lfoviz.id = "lfoviz"
        lfo = Panel("LFO",
            sel("lfo_dest", "Dest", E.LFO_DEST_NAMES),
            sel("lfo_shape", "Forma", ["seno", "triáng", "sierra", "cuadr"]),
            fdr("lfo_rate", "Rate", 0.05, 20, lambda v: f"{v:.1f}", log=True),
            fdr("lfo_depth", "Depth", 0, 1, _fmt_pct),
            lfoviz)

        # controles de percusión (se muestran cuando la pista es un tambor)
        drumctl = Panel("percusión",
            fdr("drum_noise", "Ruido", 0, 1, _fmt_pct),
            fdr("drum_bright", "Brillo", 200, 14000, _fmt_hz, log=True),
            fdr("drum_drop", "Drop", 0, 8, lambda v: f"{v:.1f}x"),
            fdr("drum_pdecay", "Caída", 0.005, 0.2, _fmt_s, log=True))
        drumenv = Panel("golpe · env",
            fdr("amp_attack", "Atk", 0.001, 1, _fmt_s, log=True),
            fdr("amp_decay", "Dec", 0.005, 1, _fmt_s, log=True),
            fdr("amp_release", "Rel", 0.005, 1, _fmt_s, log=True))
        drumvol = Panel("amp", fdr("volume", "Vol", 0, 1, _fmt_pct))

        # eq en la pantalla principal: barras clickeables junto al osciloscopio
        eqpad = EqPad(eng); eqpad.id = "eqpad"

        scope = Scope(eng); scope.id = "scope"; scope.border_title = "osciloscopio"
        envviz = EnvViz(eng); envviz.id = "envviz"; envviz.border_title = "envolvente"
        piano = Piano(eng); piano.id = "piano"
        grid = SeqGrid(self.seq, eng); grid.id = "seqgrid"
        plist = PresetList(); plist.id = "preset-list"

        # --- tonalidad: selectores que escriben el estado de composición ---
        tonic_pick = HPicker("tónica", theory.NOTE_NAMES,
                             lambda: self.tonic, self.set_tonic)
        mode_pick = HPicker("escala", theory.MODES,
                            lambda: theory.MODES.index(self.mode), self.set_mode)
        chord_pick = HPicker("acordes", ["tríada", "séptima"],
                             lambda: 1 if self.sevenths else 0, self.set_sevenths)
        row_pick = HPicker("fila 1–7", ["toca acordes", "cromático"],
                           lambda: 0 if self.chords_on else 1, self.set_chords)
        overview = Static(id="chord-overview")
        overview.border_title = "acordes de la tonalidad"

        with TabbedContent(initial="tab-synth", id="tabs"):
            with TabPane("synth", id="tab-synth"):
                yield Horizontal(osc, filt, lfo, classes="rackrow rack-synth")
                yield Horizontal(ampenv, fltenv, ampvol, layer, classes="rackrow rack-synth")
                yield Horizontal(drumctl, drumenv, drumvol, classes="rackrow", id="rack-drum")
                yield Horizontal(scope, envviz, eqpad, classes="visrow")
                yield piano
            with TabPane("secuenciador", id="tab-seq"):
                yield grid
                yield Static("", id="seqbar")
            with TabPane("presets", id="tab-presets"):
                yield Input(placeholder="nombre del preset…  (Enter para guardar)",
                            id="preset-name")
                yield plist
                yield Static("  guarda el sonido + el patrón completos · clic o ↑↓+Enter carga · d borra",
                             id="preset-msg")
            with TabPane("tonalidad", id="tab-tonal"):
                yield Horizontal(tonic_pick, classes="tonalrow")
                yield Horizontal(mode_pick, chord_pick, row_pick, classes="tonalrow")
                yield overview
                yield Static("  en el piano: 1–7 tocan estos acordes · z… la melodía "
                             "· las notas de la escala salen resaltadas", id="tonal-help")

        yield Static("", id="status")
        yield Static(
            "  z/q = piano · 1–7 = acordes · −/= octava · ␣ play/stop · esc pánico · ctrl+c sale",
            id="help",
        )

    def on_mount(self):
        try:
            self.engine.start()
        except Exception as exc:  # noqa: BLE001
            self.query_one("#title", Static).update(f"♪  kichoro · synth  — sin audio: {exc}")
        self.set_interval(1 / 30, self._tick)
        self.set_interval(1 / 100, self._seq_tick)   # reloj del secuenciador (fino)
        self.refresh_tonality()

    def on_unmount(self):
        self.seq.stop()
        self.engine.stop()

    # --- secuenciador ---
    def _seq_tick(self):
        if self.seq.tick(time.monotonic()):
            try:
                self.query_one("#seqgrid").refresh()
                self.update_seq_status()
            except Exception:  # noqa: BLE001
                pass

    def action_playstop(self):
        if self.seq.playing:
            self.seq.stop()
        else:
            self.seq.play(time.monotonic())
        try:
            self.query_one("#seqgrid").refresh()
        except Exception:  # noqa: BLE001
            pass
        self.update_seq_status()

    def select_instrument(self, i: int):
        """Selecciona la pista/instrumento: la tab synth pasa a editar su patch.
        Si es un tambor, muestra los controles de percusión en vez de los del sinte."""
        self.engine.select(i)
        ins = self.engine.instruments[self.engine.sel]
        is_drum = ins.params.kind == E.INST_DRUM
        try:
            for w in self.query(".rack-synth"):
                w.display = not is_drum
            self.query_one("#rack-drum").display = is_drum
            self.query_one("#panel-layer").display = (ins.params_b is not None
                                                      and not is_drum)
        except Exception:  # noqa: BLE001
            pass
        self._reload_patch_controls()
        self.update_seq_status()

    def _reload_patch_controls(self):
        """Relee todo el rack desde el patch activo (cambió el instrumento
        seleccionado, o la capa A/B que se edita)."""
        for f in self.query(Fader):
            f.reload()
        for ws in self.query(WaveSelector):
            ws.reload()
        self._last_env = None     # fuerza repintar las curvas del nuevo patch
        self._last_eq = None
        try:
            self.query_one("#envviz").refresh()
            self.query_one("#lfoviz").refresh()
            self.query_one("#eqpad").refresh()
        except Exception:  # noqa: BLE001
            pass

    # --- capa B (los setters del panel "capa B") ---
    def _set_layer_on(self, v: int):
        ins = self.engine.instruments[self.engine.sel]
        if ins.params_b is None:
            return
        ins.layer_on = bool(v)
        if not ins.layer_on:          # al apagarla, suelta lo que tuviera sonando
            for voice in ins.voices_b:
                voice.note_off()

    def _set_edit_layer(self, v: int):
        self.engine.edit_b = bool(v)
        self._reload_patch_controls()

    def update_seq_status(self):
        try:
            grid = self.query_one("#seqgrid")
            bar = self.query_one("#seqbar", Static)
        except Exception:  # noqa: BLE001
            return
        seq = self.seq
        v = seq.grid[grid.cur_track][grid.cur_step]
        note = note_name(v) if v is not None else "—"
        inst = self.engine.instruments[self.engine.sel].name
        play = "▶ play" if seq.playing else "■ stop"
        bar.update(f"  {play}  ·  {seq.bpm} BPM  ·  pista {inst}  ·  "
                   f"paso {grid.cur_step + 1}  nota {note}    "
                   f"[␣ play · enter prende · [ ] semitono · ,/. tempo]")

    def on_tabbed_content_tab_activated(self, event):
        try:
            if event.pane.id == "tab-seq":
                self.query_one("#seqgrid").focus()
                self.update_seq_status()
            elif event.pane.id == "tab-presets":
                self.query_one("#preset-list", PresetList).reload()
            elif event.pane.id == "tab-tonal":
                self.refresh_tonality()
        except Exception:  # noqa: BLE001
            pass

    # --- presets (guardar/cargar la foto completa) ---
    def set_preset_msg(self, text: str):
        try:
            self.query_one("#preset-msg", Static).update("  " + text)
        except Exception:  # noqa: BLE001
            pass

    def on_input_submitted(self, event: Input.Submitted):
        if event.input.id != "preset-name":
            return
        name = event.value.strip()
        if not name:
            self.set_preset_msg("escribe un nombre primero")
            return
        try:
            presets.save(name, self.engine, self.seq)
        except Exception as exc:  # noqa: BLE001
            self.set_preset_msg(f"no pude guardar: {exc}")
            return
        event.input.value = ""
        self.query_one("#preset-list", PresetList).reload()
        self.set_preset_msg(f"guardado '{name}'")

    def load_preset(self, key: str):
        try:
            data = presets.load(key, self.engine, self.seq)
        except Exception as exc:  # noqa: BLE001
            self.set_preset_msg(f"no pude cargar: {exc}")
            return
        self._kbd.clear()
        self.select_instrument(self.engine.sel)   # resincroniza rack, faders y vis
        try:
            self.query_one("#seqgrid").refresh()
        except Exception:  # noqa: BLE001
            pass
        self.update_seq_status()
        self.set_preset_msg(f"cargado '{data.get('name', key)}'")

    def delete_preset(self, key: str):
        try:
            presets.delete(key)
        except Exception as exc:  # noqa: BLE001
            self.set_preset_msg(f"no pude borrar: {exc}")
            return
        self.query_one("#preset-list", PresetList).reload()
        self.set_preset_msg("borrado")

    # --- tonalidad (componer dentro de una escala) ---
    def set_tonic(self, i: int):
        self.tonic = i % 12
        self._tonality_changed()

    def set_mode(self, i: int):
        self.mode = theory.MODES[i % len(theory.MODES)]
        self._tonality_changed()

    def set_sevenths(self, i: int):
        self.sevenths = bool(i)
        self._tonality_changed()

    def set_chords(self, i: int):
        self.chords_on = (i == 0)
        self._tonality_changed()

    def _tonality_changed(self):
        self.refresh_tonality()
        try:
            self.query_one("#piano").refresh()
        except Exception:  # noqa: BLE001
            pass
        for hp in self.query(HPicker):       # mantener los selectores en sync
            hp.refresh()

    def refresh_tonality(self):
        try:
            ov = self.query_one("#chord-overview", Static)
        except Exception:  # noqa: BLE001
            return
        rows = theory.diatonic_overview(self.tonic, self.mode, self.base_octave,
                                        self.sevenths)
        scale = " ".join(theory.NOTE_NAMES[p]
                         for p in theory.scale_pitch_classes(self.tonic, self.mode))
        qcolor = {"mayor": CGREEN, "menor": CBLUE, "dim": CYELLOW}
        t = Text()
        t.append(f"tonalidad   {theory.NOTE_NAMES[self.tonic]} {self.mode}\n", style=CLAV)
        t.append(f"escala      {scale}\n\n", style=CSUB)
        per_line = 4
        for idx, (deg, _notes, label) in enumerate(rows):
            t.append(f" {deg} ", style=f"bold {CMAUVE}")
            t.append(f"· {label}".ljust(11),
                     style=qcolor[theory.chord_quality(label)])
            if idx % per_line == per_line - 1:
                t.append("\n")
        kind = "tríadas" if not self.sevenths else "séptimas"
        chordmode = "1–7 acordes" if self.chords_on else "fila numérica cromática"
        t.append(f"\n\n{kind} · {chordmode}", style=COVER)
        ov.update(t)

    def play_degree(self, degree: int):
        """Toca el acorde diatónico de un grado (1..7) en la octava actual."""
        notes = theory.diatonic_chord(degree, self.tonic, self.mode,
                                      self.base_octave, self.sevenths)
        now = time.monotonic()
        for m in notes:
            m = max(0, min(108, m))
            if m not in self._kbd:
                # legato: si el gate alcanzó a soltarla y esto es la repetición
                # de la tecla, retomarla sin segundo ataque
                self.engine.note_on(m, legato=True)
            self._kbd[m] = now

    # --- bucle visual + soltado de notas de teclado ---
    def _tick(self):
        now = time.monotonic()
        for midi, seen in list(self._kbd.items()):
            if now - seen > GATE_TIMEOUT:
                self.engine.note_off(midi)
                del self._kbd[midi]
        try:
            self.query_one("#scope").refresh()
            p = self.engine.params
            if p.lfo_dest != E.LFO_OFF and p.lfo_depth > 0.0:
                self.query_one("#lfoviz").refresh()   # el cursor recorre la onda
            # repintar el piano solo cuando cambia qué notas suenan (no a 30fps,
            # que recargaba el GIL; tampoco solo en eventos, que se perdía teclas)
            active = tuple(self.engine.active_notes())
            if active != self._last_active:
                self._last_active = active
                self.query_one("#piano").refresh()
            # repintar la curva de envolvente solo cuando cambia algún ADSR
            p = self.engine.params
            env_sig = (p.amp_attack, p.amp_decay, p.amp_sustain, p.amp_release,
                       p.flt_attack, p.flt_decay, p.flt_sustain, p.flt_release)
            if env_sig != self._last_env:
                self._last_env = env_sig
                self.query_one("#envviz").refresh()
            # repintar el eq cuando cambia el cutoff, la resonancia o una
            # banda: ahí se VE al cutoff arrastrando los niveles
            eq_sig = (p.cutoff, p.resonance, tuple(p.eq))
            if eq_sig != self._last_eq:
                self._last_eq = eq_sig
                self.query_one("#eqpad").refresh()
        except Exception:  # noqa: BLE001
            pass
        self._update_status()

    def _update_status(self):
        eng = self.engine
        notes = " ".join(note_name(m) for m in eng.active_notes()) or "—"
        lvl = min(1.0, eng.level * 2.2)
        bars = "▁▂▃▄▅▆▇█"
        meter = bars[min(len(bars) - 1, int(lvl * (len(bars) - 1)))] if lvl > 0.01 else "·"
        wave = E.WAVE_NAMES[eng.params.wave]
        tonal = f"{theory.NOTE_NAMES[self.tonic]} {self.mode}"
        txt = (f"  oct {self.base_octave}   onda {wave}   tonalidad {tonal}   notas {notes}"
               f"   voces {len(eng.active_notes())}/{E.MAX_VOICES}   nivel {meter}")
        try:
            self.query_one("#status", Static).update(txt)
        except Exception:  # noqa: BLE001
            pass

    def action_panic(self):
        self.engine.panic()
        self._kbd.clear()

    def shift_octave(self, d):
        self.base_octave = max(0, min(8, self.base_octave + d))
        self.engine.panic()
        self._kbd.clear()
        try:
            self.query_one("#piano").refresh()
        except Exception:  # noqa: BLE001
            pass

    def on_key(self, event: events.Key):
        k = event.key
        ch = event.character
        if k == "minus" or ch == "-":
            self.shift_octave(-1); event.stop(); return
        if k in ("equals_sign", "plus", "equal", "equals") or ch in ("=", "+"):
            self.shift_octave(1); event.stop(); return
        # tonalidad: la fila 1..7 toca los acordes de cada grado (gana a las negras)
        if self.chords_on and k in "1234567" and len(k) == 1:
            self.play_degree(int(k)); event.stop(); return
        if k in KEYMAP:
            midi = 12 * (self.base_octave + 1) + KEYMAP[k]
            if midi not in self._kbd:
                # legato: la repetición de una tecla sostenida retoma la nota
                # que el gate soltó, en vez de atacarla de nuevo (sonaba doble)
                self.engine.note_on(midi, legato=True)
            self._kbd[midi] = time.monotonic()
            event.stop()


def main():
    SynthApp().run()


if __name__ == "__main__":
    main()
