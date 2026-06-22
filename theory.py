"""Teoría musical mínima para componer dentro de una tonalidad.

Una *tonalidad* es una nota base (la tónica, 0=Do … 11=Si) más una *escala*
(mayor o menor): un patrón fijo de 7 notas dentro de la octava. Sobre cada grado
de la escala se arma un acorde apilando terceras *de la propia escala* —y así la
calidad (mayor / menor / disminuido) sale sola, sin elegirla: en una tonalidad
mayor los grados 1·4·5 quedan mayores, 2·3·6 menores y el 7 disminuido. Esa
mezcla automática es la que hace que las notas "suenen bien juntas".

Módulo puro: no sabe de audio ni de interfaz. Solo recibe números y devuelve
números (midi) y etiquetas.
"""

from __future__ import annotations

NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

# patrón de la escala en semitonos desde la tónica (7 grados)
SCALES = {
    "mayor": [0, 2, 4, 5, 7, 9, 11],
    "menor": [0, 2, 3, 5, 7, 8, 10],   # menor natural
}
MODES = ["mayor", "menor"]


def pc_name(pitch: int) -> str:
    """Nombre de la clase de altura (ignora la octava)."""
    return NOTE_NAMES[pitch % 12]


def scale_pitch_classes(tonic: int, mode: str) -> list[int]:
    """Las 7 clases de altura (0..11) de la tonalidad, en orden."""
    return [(tonic + iv) % 12 for iv in SCALES[mode]]


def in_scale(midi: int, tonic: int, mode: str) -> bool:
    """¿La nota cae dentro de la tonalidad (en cualquier octava)?"""
    return (midi - tonic) % 12 in set(SCALES[mode])


def diatonic_chord(degree: int, tonic: int, mode: str,
                   octave: int = 4, sevenths: bool = False) -> list[int]:
    """Notas midi del acorde diatónico sobre `degree` (1..7). Apila terceras de
    la escala: grados 0,2,4 (tríada) y 6 (séptima), envolviendo octavas. La
    calidad sale sola de la escala. `octave` fija dónde queda la tónica (4 → C4=60)."""
    ivs = SCALES[mode]
    n = len(ivs)
    root = 12 * (octave + 1) + tonic            # C4 = 60 cuando tonic=0, octave=4
    d = (degree - 1) % n
    steps = [0, 2, 4, 6] if sevenths else [0, 2, 4]
    return [root + ivs[(d + s) % n] + 12 * ((d + s) // n) for s in steps]


def chord_label(notes: list[int]) -> str:
    """Nombre corto del acorde a partir de sus notas: C, Dm, B°, G7, Cmaj7, Bø7…"""
    root = NOTE_NAMES[notes[0] % 12]
    iv = [(x - notes[0]) % 12 for x in notes[1:]]
    third, fifth = iv[0], iv[1]
    if (third, fifth) == (4, 7):
        q = ""        # mayor
    elif (third, fifth) == (3, 7):
        q = "m"       # menor
    elif (third, fifth) == (3, 6):
        q = "°"       # disminuido
    elif (third, fifth) == (4, 8):
        q = "+"       # aumentado
    else:
        q = "?"
    if len(iv) < 3:
        return root + q
    sev = iv[2]
    if q == "" and sev == 11:
        return root + "maj7"
    if q == "" and sev == 10:
        return root + "7"          # dominante
    if q == "m" and sev == 10:
        return root + "m7"
    if q == "°" and sev == 10:
        return root + "ø7"         # semidisminuido (m7♭5)
    if q == "°" and sev == 9:
        return root + "°7"
    return root + q + "7"


def chord_quality(label: str) -> str:
    """Clase gruesa para colorear: 'mayor' | 'menor' | 'dim'."""
    if "°" in label or "ø" in label:
        return "dim"
    if "m" in label.replace("maj", ""):
        return "menor"
    return "mayor"


def diatonic_overview(tonic: int, mode: str, octave: int = 4,
                      sevenths: bool = False) -> list[tuple[int, list[int], str]]:
    """Los 7 acordes de la tonalidad: [(grado, notas_midi, etiqueta), …]."""
    out = []
    for deg in range(1, 8):
        notes = diatonic_chord(deg, tonic, mode, octave, sevenths)
        out.append((deg, notes, chord_label(notes)))
    return out
