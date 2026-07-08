"""Motor de audio del sintetizador.

Síntesis sustractiva, polifónica, en tiempo real. No sabe nada de la interfaz:
recibe note_on/note_off y mueve parámetros; produce sonido por la tarjeta de
audio vía sounddevice. La interfaz (ui.py) solo lee `scope` y escribe en `params`.

Diseño: el callback de audio corre en su propio hilo (alta prioridad). Todo el
trabajo pesado está vectorizado en numpy/scipy para que un bloque entero se
calcule sin bucles de Python por muestra. Las transiciones de envolvente y los
coeficientes del filtro se recalculan una vez por bloque (~6 ms): grano fino de
sobra para el oído.
"""

from __future__ import annotations

import os
import threading
from dataclasses import dataclass, field

import numpy as np
from scipy.signal import lfilter

import reverb as _reverb

SR = 44_100          # frecuencia de muestreo
BLOCK = 512          # muestras por bloque -> ~11.6 ms (colchón vs. underruns)
MAX_VOICES = 8       # polifonía
MAX_FILTER_OCT = 6.0 # octavas que la envolvente puede abrir el cutoff

# Formas de onda
SINE, TRI, SAW, SQUARE = 0, 1, 2, 3
WAVE_NAMES = ["seno", "triángulo", "sierra", "cuadrada"]

# Etapas de la envolvente
IDLE, ATTACK, DECAY, SUSTAIN, RELEASE = 0, 1, 2, 3, 4

# Tipos de instrumento: sustractivo melódico, o percusión (ruido + tono)
INST_SYNTH, INST_DRUM = 0, 1

# Cómo se filtra el ruido de la percusión: pasa-bajos (cuerpo, kick),
# pasa-banda (chasquido del redoble) o pasa-altos (siseo del hat/plato).
NOISE_LP, NOISE_BP, NOISE_HP = 0, 1, 2
NOISE_MODE_NAMES = ["bajos", "banda", "altos"]

# Destinos del LFO (modulación lenta)
LFO_OFF, LFO_PITCH, LFO_FILTER, LFO_PWM = 0, 1, 2, 3
LFO_DEST_NAMES = ["off", "pitch", "filtro", "PWM"]

# Ecualizador por patch: bandas de octava (Hz) con ganancia propia en dB.
# Va DESPUÉS del pasa-bajos: el cutoff sigue barriendo los niveles (con su
# envolvente y LFO) y el EQ esculpe a mano qué frecuencias suben o bajan.
EQ_BANDS = [63.0, 125.0, 250.0, 500.0, 1000.0, 2000.0, 4000.0, 8000.0]
EQ_Q = 1.2            # ancho ~1 octava por banda
EQ_RANGE_DB = 12.0    # cada banda va de -12 a +12 dB


def _lfo_array(shape: int, phase: np.ndarray) -> np.ndarray:
    """Onda del LFO en [-1, 1] muestreada por muestra (fase array en [0,1))."""
    if shape == SINE:
        return np.sin(2.0 * np.pi * phase)
    if shape == TRI:
        return 2.0 * np.abs(2.0 * phase - 1.0) - 1.0
    if shape == SAW:
        return 2.0 * phase - 1.0
    return np.where(phase < 0.5, 1.0, -1.0)   # SQUARE


def midi_to_freq(midi: float) -> float:
    return 440.0 * 2.0 ** ((midi - 69) / 12.0)


@dataclass
class Params:
    """Parámetros compartidos. La UI escribe estos atributos; el hilo de audio
    los lee al inicio de cada bloque. Asignar un float es atómico bajo el GIL,
    así que no hace falta candado para estos."""
    wave: int = SAW
    detune: float = 0.0        # cents de separación entre osc1 y osc2 (0 = unísono)
    pulse_width: float = 0.5   # ancho del pulso de la cuadrada (PWM); 0.5 = simétrica
    # afinación del patch entero (además de la nota): con capas, permite poner
    # la B una octava/quinta arriba (transpose) o desafinarla unos cents (fine)
    transpose: float = 0.0     # semitonos, -24..+24
    fine: float = 0.0          # cents, -50..+50
    cutoff: float = 4_000.0    # Hz
    resonance: float = 1.2     # Q del filtro
    env_to_cutoff: float = 0.4 # 0..1, cuánto abre la envolvente de filtro el cutoff
    # envolvente de amplitud (VCA): la forma del volumen de la nota
    amp_attack: float = 0.01   # s
    amp_decay: float = 0.25    # s
    amp_sustain: float = 0.7   # 0..1
    amp_release: float = 0.30  # s
    # envolvente de filtro (VCF): mueve el cutoff de forma independiente del volumen
    flt_attack: float = 0.01   # s
    flt_decay: float = 0.25    # s
    flt_sustain: float = 0.7   # 0..1
    flt_release: float = 0.30  # s
    volume: float = 0.6        # 0..1
    drive: float = 1.0         # ganancia previa al soft-clip (carácter)
    # --- instrumento ---
    kind: int = INST_SYNTH
    # percusión (kind == INST_DRUM): un cuerpo tonal cuyo pitch cae + ruido filtrado
    drum_drop: float = 3.0       # pitch inicial extra (factor) que cae al golpear
    drum_pdecay: float = 0.03    # s, qué tan rápido cae el pitch
    drum_noise: float = 0.5      # 0 = tono puro (kick) .. 1 = ruido puro (hi-hat)
    drum_bright: float = 4000.0  # Hz, corte/centro del ruido (agudo = hi-hat)
    drum_noise_mode: int = NOISE_LP  # cómo se filtra el ruido (bajos/banda/altos)
    drum_click: float = 0.0      # 0..1, transitorio corto de ataque (pegada/snap)
    choke_group: int = 0         # >0: al golpear, calla a los demás del mismo grupo
                                 #     (hat cerrado ahoga al abierto)
    # LFO: un oscilador lento que mueve un destino (vibrato / wah / PWM)
    lfo_dest: int = LFO_OFF
    lfo_shape: int = SINE
    lfo_rate: float = 5.0        # Hz
    lfo_depth: float = 0.0       # 0..1
    # ecualizador: ganancia en dB por banda de EQ_BANDS (0 = banda plana)
    eq: list = field(default_factory=lambda: [0.0] * len(EQ_BANDS))


def _poly_blep(t: np.ndarray, dt: float) -> np.ndarray:
    """Corrección polyBLEP para suavizar los saltos de sierra/cuadrada y matar
    casi todo el aliasing. `t` es la fase en ciclos [0,1); `dt` el incremento de
    fase por muestra."""
    out = np.zeros_like(t)
    if dt <= 0:
        return out
    # justo después de un salto (cerca de 0)
    m = t < dt
    x = t[m] / dt
    out[m] = x + x - x * x - 1.0
    # justo antes de un salto (cerca de 1)
    m = t > 1.0 - dt
    x = (t[m] - 1.0) / dt
    out[m] = x * x + x + x + 1.0
    return out


def _biquad_lowpass(fc: float, q: float):
    """Coeficientes de un pasa-bajos RBJ (Audio EQ Cookbook)."""
    fc = float(np.clip(fc, 20.0, SR * 0.45))
    q = max(q, 0.3)
    w0 = 2.0 * np.pi * fc / SR
    cw, sw = np.cos(w0), np.sin(w0)
    alpha = sw / (2.0 * q)
    b0 = (1.0 - cw) / 2.0
    b1 = 1.0 - cw
    b2 = (1.0 - cw) / 2.0
    a0 = 1.0 + alpha
    a1 = -2.0 * cw
    a2 = 1.0 - alpha
    b = np.array([b0, b1, b2]) / a0
    a = np.array([1.0, a1 / a0, a2 / a0])
    return b, a


def _biquad_highpass(fc: float, q: float):
    """Pasa-altos RBJ: deja pasar lo agudo. Para el siseo del hi-hat/plato."""
    fc = float(np.clip(fc, 20.0, SR * 0.45))
    q = max(q, 0.3)
    w0 = 2.0 * np.pi * fc / SR
    cw, sw = np.cos(w0), np.sin(w0)
    alpha = sw / (2.0 * q)
    b0 = (1.0 + cw) / 2.0
    b1 = -(1.0 + cw)
    b2 = (1.0 + cw) / 2.0
    a0 = 1.0 + alpha
    a1 = -2.0 * cw
    a2 = 1.0 - alpha
    return np.array([b0, b1, b2]) / a0, np.array([1.0, a1 / a0, a2 / a0])


def _biquad_bandpass(fc: float, q: float):
    """Pasa-banda RBJ (ganancia de pico constante): un foco de frecuencia. Para
    el chasquido del redoble (banda media-aguda)."""
    fc = float(np.clip(fc, 20.0, SR * 0.45))
    q = max(q, 0.3)
    w0 = 2.0 * np.pi * fc / SR
    cw, sw = np.cos(w0), np.sin(w0)
    alpha = sw / (2.0 * q)
    b0 = alpha
    b1 = 0.0
    b2 = -alpha
    a0 = 1.0 + alpha
    a1 = -2.0 * cw
    a2 = 1.0 - alpha
    return np.array([b0, b1, b2]) / a0, np.array([1.0, a1 / a0, a2 / a0])


def _biquad_peaking(fc: float, q: float, gain_db: float):
    """Campana RBJ (peaking EQ): sube o baja una banda alrededor de `fc` sin
    tocar el resto. Una por banda del ecualizador."""
    fc = float(np.clip(fc, 20.0, SR * 0.45))
    amp = 10.0 ** (gain_db / 40.0)
    w0 = 2.0 * np.pi * fc / SR
    cw, sw = np.cos(w0), np.sin(w0)
    alpha = sw / (2.0 * max(q, 0.3))
    b0 = 1.0 + alpha * amp
    b1 = -2.0 * cw
    b2 = 1.0 - alpha * amp
    a0 = 1.0 + alpha / amp
    a1 = -2.0 * cw
    a2 = 1.0 - alpha / amp
    return np.array([b0, b1, b2]) / a0, np.array([1.0, a1 / a0, a2 / a0])


def _noise_filter(mode: int, fc: float, q: float):
    if mode == NOISE_HP:
        return _biquad_highpass(fc, q)
    if mode == NOISE_BP:
        return _biquad_bandpass(fc, q)
    return _biquad_lowpass(fc, q)


class Voice:
    """Una voz: dos osciladores (uno detuneado), una envolvente y un filtro
    propio con su estado de delay para que no haya clics entre bloques."""

    __slots__ = ("active", "midi", "freq", "phase1", "phase2", "vel",
                 "amp_env", "amp_stage", "flt_env", "flt_stage", "zi", "age", "t")

    def __init__(self):
        self.active = False
        self.midi = 0
        self.freq = 0.0
        self.phase1 = 0.0   # fase en ciclos [0,1) (synth) o radianes (drum)
        self.phase2 = 0.0
        self.vel = 1.0      # velocity del golpe (0..1): acentos y ghost notes
        self.amp_env = 0.0      # envolvente de amplitud (VCA)
        self.amp_stage = IDLE
        self.flt_env = 0.0      # envolvente de filtro (VCF)
        self.flt_stage = IDLE
        self.zi = np.zeros(2)  # estado del biquad
        self.age = 0
        self.t = 0             # muestras desde el último golpe (pitch drop de percusión)

    def note_on(self, midi: int, age: int, vel: float = 1.0):
        self.active = True
        self.midi = midi
        self.freq = midi_to_freq(midi)
        self.vel = max(0.0, min(1.0, vel))
        self.amp_stage = ATTACK
        self.flt_stage = ATTACK
        self.age = age
        self.t = 0
        # no reiniciamos fase ni env: retrigger sin clic

    def note_off(self):
        if self.active and self.amp_stage != IDLE:
            self.amp_stage = RELEASE
            self.flt_stage = RELEASE

    def resume(self, age: int):
        """Retomar una nota que estaba soltándose (el legato del gate): las
        envolventes vuelven SUAVES hacia su sustain —etapa DECAY, que tiende al
        sustain desde donde esté— sin pasar por el ataque. Re-atacar aquí
        sonaba como un segundo golpe (amplitud a tope y filtro reabierto)."""
        self.amp_stage = DECAY
        self.flt_stage = DECAY
        self.age = age

    # --- síntesis de un bloque ---

    def _osc(self, base_freq: float, wave: int, p: Params, frames: int, pw=None):
        """Genera `frames` muestras de los dos osciladores sumados y devuelve
        (señal, fase1_final, fase2_final)."""
        det = 2.0 ** (p.detune / 1200.0)  # cents -> factor de frecuencia
        sig = np.zeros(frames)
        n = np.arange(frames)
        # Indexamos por oscilador (0 y 1), no por su frecuencia: con detune=0 los
        # dos osciladores comparten frecuencia y comparar `f == base_freq` mandaba
        # la fase de ambos a phase1, dejando phase2 clavado -> el osc2 reiniciaba
        # su fase en cada bloque y metía un click de banda ancha en toda nota.
        for i, f in enumerate((base_freq, base_freq * det)):
            phase0 = self.phase1 if i == 0 else self.phase2
            dt = f / SR
            t = (phase0 + n * dt) % 1.0
            if wave == SINE:
                w = np.sin(2.0 * np.pi * t)
            elif wave == TRI:
                w = 4.0 * np.abs(t - 0.5) - 1.0
            elif wave == SAW:
                w = 2.0 * t - 1.0 - _poly_blep(t, dt)
            else:  # SQUARE / pulso de ancho variable (PWM, modulable por el LFO)
                pwv = np.clip(p.pulse_width if pw is None else pw, 0.02, 0.98)  # escalar o array
                w = np.where(t < pwv, 1.0, -1.0)
                # polyBLEP en las dos discontinuidades: subida en t=0, bajada en t=pwv
                w = w + _poly_blep(t, dt) - _poly_blep((t - pwv) % 1.0, dt)
            sig += w
            new_phase = (phase0 + frames * dt) % 1.0
            if i == 0:
                self.phase1 = new_phase
            else:
                self.phase2 = new_phase
        return sig * 0.5  # promedio de los dos osciladores

    @staticmethod
    def _adsr(env: float, stage: int, a: float, d: float, s: float, r: float,
              frames: int):
        """Avanza una ADSR exponencial (un polo) un bloque entero, vectorizada.
        Devuelve (señal del bloque, nuevo valor, nueva etapa). Es pura: el estado
        vive afuera, así una voz puede correr dos envolventes (amplitud y filtro)
        con el mismo código."""
        if stage == IDLE:
            return np.zeros(frames), 0.0, IDLE
        if stage == ATTACK:
            target, tau = 1.02, max(a, 1e-4)
        elif stage == DECAY:
            target, tau = s, max(d, 1e-4)
        elif stage == SUSTAIN:
            return np.full(frames, s), s, SUSTAIN
        else:  # RELEASE
            target, tau = 0.0, max(r, 1e-4)

        coeff = np.exp(-1.0 / (tau * SR))
        powers = coeff ** np.arange(1, frames + 1)
        out = target + (env - target) * powers
        env = float(out[-1])

        # transiciones de etapa (al borde del bloque)
        if stage == ATTACK and env >= 1.0:
            env = 1.0
            stage = DECAY
            out = np.clip(out, 0.0, 1.0)
        elif stage == DECAY and abs(env - s) < 0.005:
            stage = SUSTAIN
        elif stage == RELEASE and env <= 0.0006:
            env = 0.0
            stage = IDLE
        return np.clip(out, 0.0, 1.2), env, stage

    def render(self, p: Params, frames: int, lfo_arr=None) -> np.ndarray:
        if p.kind == INST_DRUM:
            return self._render_drum(p, frames)
        amp, self.amp_env, self.amp_stage = self._adsr(
            self.amp_env, self.amp_stage,
            p.amp_attack, p.amp_decay, p.amp_sustain, p.amp_release, frames)
        # la voz vive mientras su envolvente de AMPLITUD no se haya apagado
        if self.amp_stage == IDLE:
            self.active = False
            return np.zeros(frames)

        flt, self.flt_env, self.flt_stage = self._adsr(
            self.flt_env, self.flt_stage,
            p.flt_attack, p.flt_decay, p.flt_sustain, p.flt_release, frames)

        # afinación del patch (transpose en semitonos + fine en cents): se lee
        # aquí y no en note_on, así mover el fader retona las notas que suenan
        base = self.freq * 2.0 ** ((p.transpose + p.fine / 100.0) / 12.0)
        # el LFO (onda por muestra) mueve un destino sin escalones de bloque
        freq, pw, lfo_filter = base, None, False
        if lfo_arr is not None:
            if p.lfo_dest == LFO_PITCH:
                freq = base * 2.0 ** (float(lfo_arr.mean()) * p.lfo_depth * 2.0 / 12.0)
            elif p.lfo_dest == LFO_PWM:
                pw = p.pulse_width + lfo_arr * p.lfo_depth * 0.45   # ancho por muestra
            elif p.lfo_dest == LFO_FILTER:
                lfo_filter = True
        sig = self._osc(freq, p.wave, p, frames, pw)

        # la envolvente de filtro abre el cutoff (carácter "synth"), aparte del volumen
        flt_mean = float(flt.mean())
        base_fc = p.cutoff * (2.0 ** (p.env_to_cutoff * flt_mean * MAX_FILTER_OCT))
        if lfo_filter:
            # cutoff modulado por muestra -> sub-bloques para que el biquad no clickee
            cutoff_arr = base_fc * 2.0 ** (lfo_arr * p.lfo_depth * 2.0)
            sig = self._filter_swept(sig, cutoff_arr, p.resonance)
        else:
            b, a = _biquad_lowpass(base_fc, p.resonance)
            sig, self.zi = lfilter(b, a, sig, zi=self.zi)

        return sig * amp * self.vel

    def _filter_swept(self, sig, cutoff_arr, q, sub=64):
        """Pasa-bajos con cutoff que se mueve: en sub-bloques cortos (coeficientes
        interpolados) para que el barrido del LFO no produzca clics."""
        out = np.empty(len(sig))
        for s in range(0, len(sig), sub):
            e = min(s + sub, len(sig))
            b, a = _biquad_lowpass(float(cutoff_arr[s:e].mean()), q)
            out[s:e], self.zi = lfilter(b, a, sig[s:e], zi=self.zi)
        return out

    def _render_drum(self, p: Params, frames: int) -> np.ndarray:
        """Voz de percusión: cuerpo tonal con pitch que cae + ruido filtrado, con
        una envolvente percusiva (sin sustain). La nota afina el golpe."""
        amp, self.amp_env, self.amp_stage = self._adsr(
            self.amp_env, self.amp_stage,
            p.amp_attack, p.amp_decay, 0.0, p.amp_release, frames)  # percusivo: sustain 0
        if self.amp_stage == IDLE:
            self.active = False
            return np.zeros(frames)

        n = np.arange(frames)
        t = (self.t + n) / SR              # tiempo desde el golpe
        self.t += frames
        # cuerpo tonal: la frecuencia arranca alta y cae a la nota (el "tum" del kick)
        base = self.freq * 2.0 ** ((p.transpose + p.fine / 100.0) / 12.0)
        freq = base * (1.0 + p.drum_drop * np.exp(-t / max(p.drum_pdecay, 1e-4)))
        phase = self.phase1 + np.cumsum(2.0 * np.pi * freq / SR)
        self.phase1 = float(phase[-1] % (2.0 * np.pi))
        tone = np.sin(phase)
        # ruido filtrado según el modo: bajos = cuerpo, banda = chasquido, altos =
        # siseo. Un golpe más fuerte abre un poco el filtro (más brillo), como en
        # una batería real.
        noise = np.random.standard_normal(frames)
        bright = p.drum_bright * (0.7 + 0.3 * self.vel)
        b, a = _noise_filter(p.drum_noise_mode, bright, 0.7)
        noise, self.zi = lfilter(b, a, noise, zi=self.zi)
        mix = (1.0 - p.drum_noise) * tone + p.drum_noise * noise
        # click de ataque: un transitorio cortísimo (ruido de banda ancha que cae
        # en ~2 ms) que da pegada al golpe (beater del kick, snap del redoble)
        if p.drum_click > 0.0:
            click = np.random.standard_normal(frames) * np.exp(-t / 0.002)
            mix = mix + p.drum_click * click
        return mix * amp * self.vel


class Instrument:
    """Un instrumento = un patch (Params) + su propio grupo de voces. El motor
    tiene varios y los suma; cada uno asigna y roba sus voces de forma autónoma.

    Con `layered=True` el instrumento gana una **capa B**: un segundo patch
    completo con su propio grupo de voces y su propio LFO que, al activarla
    (`layer_on`), suena apilado con la capa A en cada nota —el "layer" de los
    sintes de los 80 (un pad detrás del lead, una sierra sobre un cuadrado)."""

    def __init__(self, name: str, params: Params, n_voices: int = 6,
                 layered: bool = False):
        self.name = name
        self.params = params
        self.voices = [Voice() for _ in range(n_voices)]
        self._age = 0
        self.lfo_phase = 0.0    # fase del LFO, compartida por todas las voces
        self.eq_zi = [np.zeros(2) for _ in EQ_BANDS]   # estado del EQ (por banda)
        # capa B (solo si layered): patch, voces, LFO y EQ propios
        self.layer_on = False
        self.params_b = Params() if layered else None
        self.voices_b = [Voice() for _ in range(n_voices)] if layered else []
        self.lfo_phase_b = 0.0
        self.eq_zi_b = [np.zeros(2) for _ in EQ_BANDS]

    def note_on(self, midi: int, vel: float = 1.0, legato: bool = False):
        self._age += 1
        self._pool_note_on(self.voices, self.params, midi, vel, legato)
        if self.layer_on and self.params_b is not None:
            self._pool_note_on(self.voices_b, self.params_b, midi, vel, legato)

    def _pool_note_on(self, voices: list, params: Params, midi: int, vel: float,
                      legato: bool = False):
        # synth: si la nota ya suena, retrigger suave (sin clic).
        # percusión: cada golpe reinicia limpio, nunca encadena.
        # legato (lo pide el teclado de la TUI): retomar también una nota que
        # aún está SOLTÁNDOSE —el gate del terminal la soltó pero la tecla
        # sigue apretada— para que la repetición no suene como segundo ataque.
        if params.kind != INST_DRUM:
            for v in voices:
                if v.active and v.midi == midi and (legato or v.amp_stage != RELEASE):
                    if legato and v.amp_stage == RELEASE:
                        v.resume(self._age)      # vuelve al sustain, sin re-atacar
                    else:
                        v.note_on(midi, self._age, vel)
                    return
        # voz libre
        for v in voices:
            if not v.active:
                self._fresh(v, midi, vel)
                return
        # sin voces libres: robar la más vieja, reiniciándola limpia (sin clic de robo)
        self._fresh(min(voices, key=lambda v: v.age), midi, vel)

    def _fresh(self, v, midi: int, vel: float = 1.0):
        v.amp_env = 0.0
        v.flt_env = 0.0
        v.zi = np.zeros(2)
        # fase a cero: con la envolvente en 0 no hay clic posible, y así las
        # capas A y B arrancan la nota EN FASE. Si cada voz partiera donde
        # quedó, el desfase aleatorio entre capas suena a eco/chorus (en el
        # grave, hasta ~15 ms: "no suenan juntas").
        v.phase1 = 0.0
        v.phase2 = 0.0
        v.note_on(midi, self._age, vel)

    def note_off(self, midi: int):
        for v in (*self.voices, *self.voices_b):
            if v.active and v.midi == midi:
                v.note_off()

    def panic(self):
        for v in (*self.voices, *self.voices_b):
            v.note_off()

    def active_notes(self):
        # basta la capa A: la B toca siempre las mismas notas
        return sorted({v.midi for v in self.voices
                       if v.active and v.amp_stage in (ATTACK, DECAY, SUSTAIN)})

    def render_into(self, out: np.ndarray, frames: int):
        self.lfo_phase = self._pool_render(out, self.voices, self.params,
                                           self.lfo_phase, self.eq_zi, frames)
        if self.params_b is not None:   # aun apagada, la capa suelta sus colas
            self.lfo_phase_b = self._pool_render(out, self.voices_b, self.params_b,
                                                 self.lfo_phase_b, self.eq_zi_b,
                                                 frames)

    def _pool_render(self, out: np.ndarray, voices: list, p: Params,
                     lfo_phase: float, eq_zi: list, frames: int) -> float:
        lfo_arr = None
        if p.lfo_dest != LFO_OFF and p.lfo_depth > 0.0:
            ph = (lfo_phase + np.arange(frames) * (p.lfo_rate / SR)) % 1.0
            lfo_arr = _lfo_array(p.lfo_shape, ph)
            lfo_phase = float((lfo_phase + frames * p.lfo_rate / SR) % 1.0)
        acc = None
        for v in voices:
            if v.active or v.amp_stage != IDLE:
                s = v.render(p, frames, lfo_arr)
                acc = s if acc is None else acc + s
        if acc is not None:
            acc = self._apply_eq(acc, p, eq_zi)
            out += acc * (p.volume * p.drive)   # volumen y carácter por capa
        return lfo_phase

    @staticmethod
    def _apply_eq(sig: np.ndarray, p: Params, eq_zi: list) -> np.ndarray:
        """El ecualizador del patch: una campana por banda con ganancia != 0.
        Es lineal, así que va sobre la suma de voces de la capa (no por voz):
        mismo resultado, un solo filtro. Las bandas planas no cuestan nada."""
        eq = p.eq or []
        for i, fc in enumerate(EQ_BANDS):
            if i >= len(eq) or abs(eq[i]) < 0.05:
                continue
            g = float(np.clip(eq[i], -EQ_RANGE_DB, EQ_RANGE_DB))
            b, a = _biquad_peaking(fc, EQ_Q, g)
            sig, eq_zi[i] = lfilter(b, a, sig, zi=eq_zi[i])
        return sig


def default_instruments():
    """Set inicial: tres patches melódicos del sinte + un kit de percusión.

    El kit: kick (cuerpo grave + click de beater), redoble (ruido pasa-banda que
    chasquea + snap), hat cerrado (siseo pasa-altos, corto) y hat abierto (largo).
    Cerrado y abierto comparten choke_group=1: golpear el cerrado calla al
    abierto, como el pedal de un charles de verdad."""
    lead = Params(wave=SAW, cutoff=4000.0, env_to_cutoff=0.5)
    bajo = Params(wave=SQUARE, pulse_width=0.35, cutoff=1200.0, resonance=3.0,
                  amp_decay=0.18, amp_sustain=0.55, amp_release=0.18)
    pad = Params(wave=TRI, detune=8.0, cutoff=2500.0, amp_attack=0.4,
                 amp_release=0.7, amp_sustain=0.8)
    # volume alto a propósito: un tambor es un transitorio corto y, contra un
    # synth que sostiene, necesita más pico para sentirse parejo. El kick y el
    # redoble (el esqueleto del groove) pegan más fuerte; los hats, más suave.
    kick = Params(kind=INST_DRUM, drum_noise=0.05, drum_drop=4.0, drum_pdecay=0.04,
                  drum_noise_mode=NOISE_LP, drum_bright=2000.0, drum_click=0.5,
                  volume=1.7, amp_attack=0.001, amp_decay=0.18, amp_release=0.05)
    snare = Params(kind=INST_DRUM, drum_noise=0.6, drum_drop=2.0, drum_pdecay=0.02,
                   drum_noise_mode=NOISE_BP, drum_bright=2200.0, drum_click=0.4,
                   volume=1.5, amp_attack=0.001, amp_decay=0.14, amp_release=0.06)
    hat = Params(kind=INST_DRUM, drum_noise=0.97, drum_drop=0.0,
                 drum_noise_mode=NOISE_HP, drum_bright=6000.0, choke_group=1,
                 volume=0.7, amp_attack=0.001, amp_decay=0.04, amp_release=0.03)
    hat_open = Params(kind=INST_DRUM, drum_noise=0.97, drum_drop=0.0,
                      drum_noise_mode=NOISE_HP, drum_bright=5000.0, choke_group=1,
                      volume=0.75, amp_attack=0.001, amp_decay=0.30, amp_release=0.25)
    # toms: cuerpo tonal con caída de pitch suave (no como el kick) y poco ruido,
    # registro medio. La nota los afina —para fills melódicos por el kit.
    tom_hi = Params(kind=INST_DRUM, drum_noise=0.12, drum_drop=0.8, drum_pdecay=0.09,
                    drum_noise_mode=NOISE_LP, drum_bright=3500.0, drum_click=0.25,
                    volume=1.4, amp_attack=0.001, amp_decay=0.22, amp_release=0.10)
    tom_lo = Params(kind=INST_DRUM, drum_noise=0.12, drum_drop=0.8, drum_pdecay=0.11,
                    drum_noise_mode=NOISE_LP, drum_bright=2600.0, drum_click=0.25,
                    volume=1.5, amp_attack=0.001, amp_decay=0.28, amp_release=0.12)
    return [
        Instrument("lead", lead, layered=True),   # el lead trae capa B apilable
        Instrument("bajo", bajo),
        Instrument("pad", pad),
        Instrument("kick", kick, n_voices=8),
        Instrument("snare", snare, n_voices=8),
        Instrument("hat", hat, n_voices=8),
        Instrument("hat-open", hat_open, n_voices=4),
        Instrument("tom-hi", tom_hi, n_voices=4),
        Instrument("tom-lo", tom_lo, n_voices=4),
    ]


class Engine:
    def __init__(self):
        self.instruments = default_instruments()
        self.sel = 0                       # instrumento que toca/edita la tab synth
        self.edit_b = False                # si el rack edita la capa B (cuando la hay)
        self._lock = threading.RLock()
        self.scope = np.zeros(BLOCK, dtype=np.float32)  # último bloque (mono) para el osciloscopio
        self.level = 0.0   # nivel RMS para el medidor
        self.stream = None
        self.reverb = _reverb.Reverb()     # sala global (wet=0 por defecto -> apagado)
        # --- diagnóstico (SYNTH_DIAG=1): cuenta underflows y graba la salida ---
        self._diag = bool(os.environ.get("SYNTH_DIAG"))
        self._rec = []
        self._xrun = 0
        self._xrun_msgs = []
        self._frames_seen = {}
        self._dumped = False

    @property
    def params(self) -> Params:
        """El patch del instrumento seleccionado (lo que edita la tab synth).
        Con `edit_b` puesto y capa B disponible, es el patch B: el mismo rack
        de controles edita una capa u otra sin duplicar ni un fader."""
        ins = self.instruments[self.sel]
        if self.edit_b and ins.params_b is not None:
            return ins.params_b
        return ins.params

    def select(self, i: int):
        with self._lock:
            self.sel = i % len(self.instruments)

    # --- eventos de notas (inst=None -> el instrumento seleccionado) ---

    def note_on(self, midi: int, inst: int = None, vel: float = 1.0,
                legato: bool = False):
        with self._lock:
            i = self.sel if inst is None else inst
            target = self.instruments[i]
            g = target.params.choke_group
            if g:                       # choke: callar a los demás del mismo grupo
                for j, ins in enumerate(self.instruments):
                    if j != i and ins.params.choke_group == g:
                        ins.panic()
            target.note_on(midi, vel, legato)

    def note_off(self, midi: int, inst: int = None):
        with self._lock:
            self.instruments[self.sel if inst is None else inst].note_off(midi)

    def panic(self):
        with self._lock:
            for ins in self.instruments:
                ins.panic()

    def active_notes(self, inst: int = None):
        return self.instruments[self.sel if inst is None else inst].active_notes()

    # --- audio ---

    def _callback(self, outdata, frames, time_info, status):
        if status and self._diag:
            self._xrun += 1
            if len(self._xrun_msgs) < 30:
                self._xrun_msgs.append(str(status))
        out = np.zeros(frames)
        with self._lock:
            for ins in self.instruments:
                ins.render_into(out, frames)
        out *= 0.32                       # headroom para varios instrumentos
        out = self.reverb.process(out)    # sala (si wet>0; si no, devuelve la señal seca)
        out = np.tanh(out)                # soft-clip cálido / limitador global
        self.scope = out.astype(np.float32).copy()
        self.level = float(np.sqrt(np.mean(out * out)))
        outdata[:, 0] = out
        outdata[:, 1] = out
        if self._diag:
            self._rec.append(out.copy())
            self._frames_seen[frames] = self._frames_seen.get(frames, 0) + 1

    def start(self):
        import sounddevice as sd
        if self._diag:
            import atexit
            atexit.register(self._dump_diag)  # respaldo si la TUI no desmonta limpio
        # La TUI (Textual) corre en el hilo principal y compite con el callback
        # de audio por el GIL; cuando lo retrasa, hay crackle (PortAudio ni lo
        # marca como underflow). Un colchón grande -bloque amplio + latencia
        # holgada- absorbe esas pausas del hilo de interfaz.
        self.stream = sd.OutputStream(
            samplerate=SR, blocksize=1024, channels=2,
            dtype="float32", callback=self._callback, latency=0.08,
        )
        self.stream.start()

    def stop(self):
        if self.stream is not None:
            self.stream.stop()
            self.stream.close()
            self.stream = None
        if self._diag:
            self._dump_diag()

    def _dump_diag(self):
        if self._dumped:
            return
        self._dumped = True
        import wave
        sig = np.concatenate(self._rec) if self._rec else np.zeros(0, dtype=np.float32)
        with wave.open("/tmp/synth_rec.wav", "w") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
            w.writeframes((np.clip(sig, -1, 1) * 32767).astype("<i2").tobytes())
        with open("/tmp/synth_diag.txt", "w") as f:
            f.write(f"bloques={len(self._rec)} muestras={len(sig)} "
                    f"({len(sig)/SR:.2f} s)\n")
            f.write(f"eventos de status (underflow/overflow)={self._xrun}\n")
            f.write("ejemplos: " + " | ".join(self._xrun_msgs) + "\n")
            f.write(f"tamaños de bloque recibidos (frames: veces)={self._frames_seen}\n")
