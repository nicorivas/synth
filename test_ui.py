"""Prueba headless de la interfaz: monta la app sin tarjeta de audio, simula
notas y un movimiento de fader, y exporta una captura SVG para revisar."""

import asyncio

import numpy as np

import engine as E
from ui import SynthApp


async def main():
    app = SynthApp()
    app.engine.start = lambda: None   # nada de audio real en el test

    async with app.run_test(size=(112, 30)) as pilot:
        await pilot.pause()

        # 1) verificar el camino del teclado: una tecla debe disparar la nota
        await pilot.press("z")   # C de la octava base
        kbd_ok = app.engine.active_notes() != []
        app.engine.panic()

        # 1b) el gate del terminal: si el retardo de repetición del teclado
        # supera al gate, la repetición debe RETOMAR la nota (legato), no
        # re-atacarla (sonaba dos veces). Contamos los ataques de verdad.
        for ins in app.engine.instruments:      # silencio total, sin colas
            for v in (*ins.voices, *ins.voices_b):
                v.active = False
                v.amp_stage = E.IDLE
        app._kbd.clear()
        frescas = []
        orig_fresh = E.Instrument._fresh
        E.Instrument._fresh = (lambda self, v, m, vel=1.0:
                               (frescas.append(m), orig_fresh(self, v, m, vel))[1])
        await pilot.press("z")                  # keydown
        app._kbd[next(iter(app._kbd))] = 0.0    # como si el gate ya venciera
        app._tick()                             # -> suelta la nota (release)
        await pilot.press("z")                  # la repetición del terminal
        E.Instrument._fresh = orig_fresh
        gate_ok = frescas == [60]               # un solo ataque fresco
        app.engine.panic()
        app._kbd.clear()

        # 1c) el eq de la pantalla principal: flechas sobre el pad escriben
        # la ganancia de la banda en el patch del instrumento
        eqpad = app.query_one("#eqpad")
        eqpad.focus()
        await pilot.pause()
        await pilot.press("right")            # banda 125
        for _ in range(4):
            await pilot.press("up")           # +4 dB
        eq_ok = app.engine.params.eq[1] >= 3

        # 2) mover el fader de cutoff con el teclado
        cutoff = next(f for f in app.query("Fader") if f.label == "Cut")
        cutoff.focus()
        await pilot.pause()
        for _ in range(6):
            await pilot.press("down")

        # 3) para la captura: sostener un acorde directamente (sin el timeout)
        for m in (60, 64, 67):   # Do mayor
            app.engine.note_on(m)
        out = np.zeros((E.BLOCK, 2), dtype="float32")
        for _ in range(30):
            app.engine._callback(out, E.BLOCK, None, None)
        app.query_one("#piano").refresh()
        app._update_status()
        await pilot.pause()

        app.save_screenshot("ui.svg")
        print("teclado dispara nota:", kbd_ok)
        assert gate_ok, "la repetición tras el gate re-atacó la nota (doble ataque)"
        print("gate + repetición = un solo ataque (legato):", gate_ok)
        assert eq_ok, "el pad del eq no escribió en params.eq"
        print("eq en pantalla principal: la banda escribe en el patch:", eq_ok)
        print("cutoff tras 6 abajo:", round(app.engine.params.cutoff, 1))
        print("acorde activo:", app.engine.active_notes())
        print("scope no plano:", bool(np.any(np.abs(app.engine.scope) > 0.001)))
        print("captura -> ui.svg")


if __name__ == "__main__":
    asyncio.run(main())
