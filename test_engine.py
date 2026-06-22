"""Prueba headless del motor: no abre la tarjeta de audio, solo llama al
callback a mano, junta un segundo de sonido, verifica la afinación por FFT y
escribe un WAV para escuchar."""

import wave

import numpy as np

import engine as E


def render_seconds(eng, seconds, note_on_at=0.0, note_off_at=None):
    n_blocks = int(seconds * E.SR / E.BLOCK)
    buf = np.zeros((n_blocks * E.BLOCK, 2), dtype="float32")
    for i in range(n_blocks):
        t = i * E.BLOCK / E.SR
        if note_on_at is not None and abs(t - note_on_at) < (E.BLOCK / E.SR):
            pass
        out = np.zeros((E.BLOCK, 2), dtype="float32")
        eng._callback(out, E.BLOCK, None, None)
        buf[i * E.BLOCK:(i + 1) * E.BLOCK] = out
    return buf


def main():
    eng = E.Engine()
    p = eng.params
    p.wave = E.SAW
    p.cutoff = 3000
    p.resonance = 3.0
    p.amp_attack = 0.005
    p.amp_decay = 0.2
    p.amp_sustain = 0.7
    p.amp_release = 0.3
    p.detune = 8.0

    # acorde A4 - C#5 - E5 (La mayor)
    for m in (69, 73, 76):
        eng.note_on(m)
    held = render_seconds(eng, 1.2)
    for m in (69, 73, 76):
        eng.note_off(m)
    tail = render_seconds(eng, 0.6)

    audio = np.concatenate([held, tail])
    mono = audio[:, 0]

    # --- verificaciones ---
    assert np.all(np.isfinite(audio)), "salida no finita"
    peak = float(np.max(np.abs(audio)))
    assert 0.05 < peak <= 1.0, f"amplitud sospechosa: {peak}"

    # afinación: FFT del tramo sostenido, debe haber energía cerca de 440 Hz
    seg = held[E.SR // 4: E.SR][:, 0]
    spec = np.abs(np.fft.rfft(seg * np.hanning(len(seg))))
    freqs = np.fft.rfftfreq(len(seg), 1 / E.SR)
    f0 = freqs[np.argmax(spec)]
    print(f"pico espectral: {f0:.1f} Hz (esperado ~440)")
    print(f"amplitud pico: {peak:.3f}")
    print(f"voces activas tras note_off+cola: {eng.active_notes()}")

    # debe sonar una de las fundamentales del acorde
    assert any(abs(f0 - f) < 6 for f in (440.0, 554.4, 659.3)), f"afinación rara: {f0}"
    assert eng.active_notes() == [], "quedaron notas colgadas"

    # escribir WAV
    pcm = (np.clip(audio, -1, 1) * 32767).astype(np.int16)
    with wave.open("demo.wav", "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(E.SR)
        w.writeframes(pcm.tobytes())
    print("OK -> demo.wav escrito")


if __name__ == "__main__":
    main()
