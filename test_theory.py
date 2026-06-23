"""Prueba headless de la teoría: escalas, acordes diatónicos y sus nombres.
Verifica con casos que cualquiera puede comprobar a mano (Do mayor, La menor)."""

import theory as T

C, A = 0, 9   # tónicas


def main():
    # --- escala mayor de Do = teclas blancas ---
    assert T.scale_pitch_classes(C, "mayor") == [0, 2, 4, 5, 7, 9, 11]
    assert T.scale_pitch_classes(A, "menor") == [9, 11, 0, 2, 4, 5, 7]
    assert T.in_scale(60, C, "mayor")          # C
    assert not T.in_scale(61, C, "mayor")      # C# fuera de Do mayor
    print("escalas: ok")

    # --- acordes diatónicos de Do mayor (octava 4): notas exactas ---
    grados = {d: notes for d, notes, _ in T.diatonic_overview(C, "mayor", octave=4)}
    assert grados[1] == [60, 64, 67]   # C  E  G
    assert grados[2] == [62, 65, 69]   # D  F  A   (Re menor)
    assert grados[5] == [67, 71, 74]   # G  B  D
    assert grados[7] == [71, 74, 77]   # B  D  F   (disminuido)
    print("acordes (notas): ok")

    # --- nombres y la regla de calidades en Do mayor ---
    nombres = {d: lbl for d, _, lbl in T.diatonic_overview(C, "mayor")}
    assert nombres == {1: "C", 2: "Dm", 3: "Em", 4: "F",
                       5: "G", 6: "Am", 7: "B°"}, nombres
    # 1,4,5 mayores · 2,3,6 menores · 7 disminuido (la "magia")
    assert [T.chord_quality(nombres[d]) for d in range(1, 8)] == \
        ["mayor", "menor", "menor", "mayor", "mayor", "menor", "dim"]
    print("calidades por grado: ok")

    # --- séptimas (sabor jazz) ---
    s = {d: lbl for d, _, lbl in T.diatonic_overview(C, "mayor", sevenths=True)}
    assert s[1] == "Cmaj7" and s[2] == "Dm7" and s[5] == "G7" and s[7] == "Bø7", s
    print("séptimas: ok")

    # --- La menor: el grado 1 es La menor ---
    am = T.diatonic_overview(A, "menor", octave=4)
    assert am[0][2] == "Am", am[0]
    assert am[0][1] == [69, 72, 76]    # A C E
    print("menor: ok")

    # --- jazz: acordes por cualidad, voces guía y el ii–V–I ---
    assert T.chord(C, "maj7") == [60, 64, 67, 71]          # Cmaj7 = C E G B
    assert T.chord(2, "m7") == [62, 65, 69, 72]            # Dm7 = D F A C
    # las voces guía son la 3ª y la 7ª (las que definen el acorde)
    assert T.guide_tones(2, "m7") == [5, 0]                # Dm7: 3ª=F, 7ª=C
    assert T.guide_tones(7, "7") == [11, 5]                # G7:  3ª=B, 7ª=F
    # el ii–V–I en Do, comprobado por el nombre que sale de las notas
    prog = T.ii_V_I(C)
    assert prog == [(2, "m7"), (7, "7"), (0, "maj7")], prog
    assert [T.chord_label(T.chord(r, q)) for r, q in prog] == ["Dm7", "G7", "Cmaj7"]
    assert T.chord_symbol(9, "7b9") == "A7♭9"
    # el giro ii–V–I–VI termina en la dominante secundaria A7♭9
    assert T.turnaround(C)[3] == (9, "7b9")
    print("jazz (ii–V–I, voces guía): ok")

    # --- modos: el frigio (Re frigio = teclas blancas desde Re, con ♭2 = Mi♭) ---
    assert T.scale_pitch_classes(2, "frigio") == [2, 3, 5, 7, 9, 10, 0]   # D E♭ F G A B♭ C
    assert T.in_scale(63, 2, "frigio")        # E♭ pertenece a Re frigio
    assert not T.in_scale(64, 2, "frigio")    # E natural no
    print("modos (frigio): ok")

    print("OK -> theory")


if __name__ == "__main__":
    main()
