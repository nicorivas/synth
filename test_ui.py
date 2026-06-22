"""Prueba headless de la interfaz: monta la app sin tarjeta de audio, simula
notas y un movimiento de fader, y exporta una captura SVG para revisar."""

import asyncio

import numpy as np

import engine as E
from ui import SynthApp


async def main():
    app = SynthApp()
    app.engine.start = lambda: None   # nada de audio real en el test

    async with app.run_test(size=(96, 30)) as pilot:
        await pilot.pause()

        # 1) verificar el camino del teclado: una tecla debe disparar la nota
        await pilot.press("z")   # C de la octava base
        kbd_ok = app.engine.active_notes() != []
        app.engine.panic()

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
        print("cutoff tras 6 abajo:", round(app.engine.params.cutoff, 1))
        print("acorde activo:", app.engine.active_notes())
        print("scope no plano:", bool(np.any(np.abs(app.engine.scope) > 0.001)))
        print("captura -> ui.svg")


if __name__ == "__main__":
    asyncio.run(main())
