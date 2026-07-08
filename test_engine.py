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


def check_layer():
    """Capa B del lead: apagada no aporta nada; encendida se apila —la señal con
    las dos capas debe ser exactamente la suma de cada capa sola (es lineal
    antes del limitador global)."""
    def render_lead(layer_on, vol_a=None):
        eng = E.Engine()
        ins = eng.instruments[0]
        assert ins.params_b is not None, "el lead debe tener capa B"
        ins.layer_on = layer_on
        ins.params_b.wave = E.SINE            # la B con timbre propio
        if vol_a is not None:
            ins.params.volume = vol_a
        eng.note_on(69, inst=0)
        out = np.zeros(20 * E.BLOCK)
        for i in range(20):
            ins.render_into(out[i * E.BLOCK:(i + 1) * E.BLOCK], E.BLOCK)
        return out

    solo_a = render_lead(False)
    solo_b = render_lead(True, vol_a=0.0)     # A muda: queda la B sola
    juntas = render_lead(True)
    assert float(np.max(np.abs(solo_b))) > 0.01, "la capa B no suena"
    assert np.allclose(juntas, solo_a + solo_b, atol=1e-9), \
        "la capa B no se apila como suma limpia"

    # las capas arrancan EN FASE aunque antes se haya tocado con la capa
    # apagada (la voz reusada de A parte en 0, igual que la voz virgen de B):
    # con una B idéntica a la A, ambas deben aportar exactamente lo mismo
    def contrib(mute):
        import dataclasses
        eng = E.Engine()
        ins = eng.instruments[0]
        ins.params_b = dataclasses.replace(ins.params)
        eng.note_on(48, inst=0)                    # historia previa, capa apagada
        for _ in range(7):
            ins.render_into(np.zeros(E.BLOCK), E.BLOCK)
        eng.note_off(48, inst=0)
        for _ in range(400):                       # deja morir la cola ENTERA
            ins.render_into(np.zeros(E.BLOCK), E.BLOCK)
            if not any(v.active for v in ins.voices):
                break
        ins.layer_on = True
        (ins.params if mute == 'a' else ins.params_b).volume = 0.0
        eng.note_on(36, inst=0)
        out = np.zeros(20 * E.BLOCK)
        for i in range(20):
            ins.render_into(out[i * E.BLOCK:(i + 1) * E.BLOCK], E.BLOCK)
        return out
    assert np.allclose(contrib('b'), contrib('a'), atol=1e-9), \
        "las capas no arrancan en fase (desfase A↔B)"

    # con la capa apagada, sus voces ni se despiertan
    eng = E.Engine()
    eng.note_on(69, inst=0)
    assert not any(v.active for v in eng.instruments[0].voices_b), \
        "la capa B sonó estando apagada"
    # y note_off también suelta la capa B
    eng2 = E.Engine()
    eng2.instruments[0].layer_on = True
    eng2.note_on(69, inst=0)
    eng2.note_off(69, inst=0)
    assert all(v.amp_stage in (E.RELEASE, E.IDLE)
               for v in eng2.instruments[0].voices_b if v.active), \
        "quedó una voz B sin soltar"
    print("capa B del lead: apagada silente, encendida se apila: ok")


def check_legato():
    """Legato (el gate del terminal): retomar una nota que aún se está soltando
    debe volver a su sustain en la MISMA voz, sin re-atacar: nada de segunda
    voz, nada de envolvente a tope, nada de filtro reabierto (sonaba dos veces)."""
    eng = E.Engine()
    ins = eng.instruments[0]

    def render(n):
        out = np.zeros(n * E.BLOCK)
        for i in range(n):
            ins.render_into(out[i * E.BLOCK:(i + 1) * E.BLOCK], E.BLOCK)
        return out

    eng.note_on(60, inst=0)
    held = render(30)                     # hasta el sustain estable
    nivel_sustain = float(np.max(np.abs(held[-5 * E.BLOCK:])))
    eng.note_off(60, inst=0)              # el gate la suelta...
    render(5)                             # ...entra al release
    eng.note_on(60, inst=0, legato=True)  # ...y la repetición la retoma
    activas = [v for v in ins.voices if v.active]
    assert len(activas) == 1, "el legato abrió una segunda voz"
    assert activas[0].amp_stage == E.DECAY, "el resume debía ir al sustain, no re-atacar"
    resumed = render(30)
    pico_resume = float(np.max(np.abs(resumed)))
    assert pico_resume <= nivel_sustain * 1.05, \
        f"el resume infló la amplitud ({pico_resume:.3f} > {nivel_sustain:.3f}): doble golpe"
    # sin legato (secuenciador), el mismo caso sí abre voz nueva: golpe fresco
    eng2 = E.Engine()
    ins2 = eng2.instruments[0]
    eng2.note_on(60, inst=0)
    for _ in range(10):
        ins2.render_into(np.zeros(E.BLOCK), E.BLOCK)
    eng2.note_off(60, inst=0)
    for _ in range(5):
        ins2.render_into(np.zeros(E.BLOCK), E.BLOCK)
    eng2.note_on(60, inst=0)
    assert sum(v.active for v in ins2.voices) == 2, \
        "sin legato el re-ataque debía ser una voz fresca"
    print("legato del gate: retoma sin doble ataque: ok")


def check_pitch():
    """Afinación por patch: transpose (semitonos) y fine (cents) corren la
    frecuencia de la capa entera —así la B puede ir una octava arriba o unos
    cents corrida de la A. Verificado por FFT, como la afinación base."""
    def spectrum(setup):
        eng = E.Engine()
        setup(eng.instruments[0])
        eng.note_on(69, inst=0)                     # La4 = 440 Hz
        n = int(1.0 * E.SR / E.BLOCK)
        sig = np.zeros(n * E.BLOCK, dtype="float32")
        buf = np.zeros((E.BLOCK, 2), dtype="float32")
        for i in range(n):
            buf[:] = 0.0
            eng._callback(buf, E.BLOCK, None, None)
            sig[i * E.BLOCK:(i + 1) * E.BLOCK] = buf[:, 0]
        seg = sig[E.SR // 4:] * np.hanning(len(sig) - E.SR // 4)
        return np.abs(np.fft.rfft(seg)), np.fft.rfftfreq(len(seg), 1 / E.SR)

    def sine(p):
        p.wave = E.SINE
        p.cutoff = 18000.0
        p.amp_sustain = 1.0

    def peak_hz(**kw):
        def setup(ins):
            sine(ins.params)
            for k, v in kw.items():
                setattr(ins.params, k, v)
        spec, freqs = spectrum(setup)
        return float(freqs[np.argmax(spec)])

    assert abs(peak_hz() - 440.0) < 3, "afinación base corrida"
    assert abs(peak_hz(transpose=12.0) - 880.0) < 5, "transpose +12 no es una octava"
    assert abs(peak_hz(transpose=-12.0) - 220.0) < 3, "transpose -12 no es una octava abajo"
    esperado = 440.0 * 2 ** (50 / 1200)             # +50 cents ≈ 452.9 Hz
    assert abs(peak_hz(fine=50.0) - esperado) < 4, "fine +50c corrido"

    # por capa: A en 440 y B una octava arriba deben sonar AMBAS
    def dos_capas(ins):
        sine(ins.params)
        ins.layer_on = True
        sine(ins.params_b)
        ins.params_b.transpose = 12.0
    spec, freqs = spectrum(dos_capas)
    def mag(f):
        m = (freqs > f * 0.98) & (freqs < f * 1.02)
        return float(spec[m].max())
    piso = float(np.median(spec))
    assert mag(440.0) > 100 * piso and mag(880.0) > 100 * piso, \
        "las dos capas afinadas no conviven en el espectro"
    print("afinación por capa (transpose/fine): ok")


def check_eq():
    """El ecualizador por patch: subir una banda sube esa zona del espectro,
    bajarla la hunde, y con todas las bandas planas no toca nada."""
    def band_energy(gain_1k):
        eng = E.Engine()
        p = eng.instruments[0].params
        p.wave = E.SAW
        p.cutoff = 18000.0            # el pasa-bajos abierto: que mande el eq
        p.amp_sustain = 1.0
        p.eq[E.EQ_BANDS.index(1000.0)] = gain_1k
        eng.note_on(45, inst=0)       # La2 = 110 Hz: armónicos por todo el rango
        n = int(1.0 * E.SR / E.BLOCK)
        sig = np.zeros(n * E.BLOCK, dtype="float32")
        buf = np.zeros((E.BLOCK, 2), dtype="float32")
        for i in range(n):
            buf[:] = 0.0
            eng._callback(buf, E.BLOCK, None, None)
            sig[i * E.BLOCK:(i + 1) * E.BLOCK] = buf[:, 0]
        seg = sig[E.SR // 4:]
        spec = np.abs(np.fft.rfft(seg * np.hanning(len(seg))))
        freqs = np.fft.rfftfreq(len(seg), 1 / E.SR)
        m = (freqs > 800.0) & (freqs < 1250.0)
        return float(np.sum(spec[m] ** 2))

    plano = band_energy(0.0)
    arriba = band_energy(12.0)
    abajo = band_energy(-12.0)
    assert arriba > plano * 3.0, f"subir 1k no subió su energía ({arriba:.3g} vs {plano:.3g})"
    assert abajo < plano * 0.4, f"bajar 1k no la hundió ({abajo:.3g} vs {plano:.3g})"
    print(f"eq por bandas: 1k plano/±12dB = {plano:.3g} / {arriba:.3g} / {abajo:.3g}: ok")


def main():
    check_layer()
    check_legato()
    check_pitch()
    check_eq()
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
