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
    "dórico": [0, 2, 3, 5, 7, 9, 10],     # menor con 6ª mayor (el modo del ii del jazz)
    "mixolidio": [0, 2, 4, 5, 7, 9, 10],  # mayor con 7ª menor (el modo del V dominante)
    "frigio": [0, 1, 3, 5, 7, 8, 10],     # menor con ♭2: el color devocional/oriental
    "lidio": [0, 2, 4, 6, 7, 9, 11],      # mayor con #4: el color lujoso del maj7#11 (el jazz modal)
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


def chord_cell(degree: int, tonic: int, mode: str, octave: int = 4,
               sevenths: bool = False, vel: float = 1.0, dur: int = 1) -> list:
    """Una CELDA de acorde lista para el secuenciador: `[[notas...], vel, dur]`.
    Envuelve `diatonic_chord` para escribir armonía **por grado** en un
    `compose_*.py` y soltar el acorde entero en UNA sola pista (el pad carga toda
    la armonía, sin gastar una pista por nota)."""
    return [diatonic_chord(degree, tonic, mode, octave, sevenths), round(vel, 3), max(1, int(dur))]


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


# ──────────────────────────────────────────────────────────────────────────
# Jazz: acordes por cualidad (no por grado de una escala), voces guía y el
# ii–V–I. El jazz piensa en acordes con nombre propio (Dm7, G7♭9) que no siempre
# salen de una sola tonalidad —dominantes secundarias, intercambios— así que aquí
# un acorde es una raíz (clase de altura) + una cualidad (un patrón de intervalos).

# intervalos en semitonos desde la raíz, por cualidad
CHORD_QUALITIES = {
    "maj7":  [0, 4, 7, 11],
    "7":     [0, 4, 7, 10],
    "m7":    [0, 3, 7, 10],
    "m7b5":  [0, 3, 6, 10],     # semidisminuido (el ii del menor)
    "dim7":  [0, 3, 6, 9],
    "6":     [0, 4, 7, 9],
    "m6":    [0, 3, 7, 9],
    "9":     [0, 4, 7, 10, 14],
    "maj9":  [0, 4, 7, 11, 14],
    "m9":    [0, 3, 7, 10, 14],
    "7b9":   [0, 4, 7, 10, 13],  # dominante con ♭9: tensión que empuja a resolver
    "7#5":   [0, 4, 8, 10],
}


def chord(root_pc: int, quality: str, octave: int = 4) -> list[int]:
    """Notas midi del acorde `root_pc` (0=Do…11=Si) con esa cualidad. `octave`
    fija el registro de la raíz (4 → C4=60)."""
    root = 12 * (octave + 1) + (root_pc % 12)
    return [root + iv for iv in CHORD_QUALITIES[quality]]


def guide_tones(root_pc: int, quality: str) -> list[int]:
    """Las dos voces guía —3ª y 7ª— como clases de altura. Son las notas que
    *definen* la cualidad del acorde; con la fundamental en el bajo bastan para
    que suene completo (el 'shell voicing' del jazz)."""
    ivs = CHORD_QUALITIES[quality]
    return [(root_pc + ivs[1]) % 12, (root_pc + ivs[3]) % 12]


def chord_symbol(root_pc: int, quality: str) -> str:
    """Nombre del acorde: 'Dm7', 'G7', 'Cmaj7', 'A7♭9'…"""
    return NOTE_NAMES[root_pc % 12] + quality.replace("b", "♭").replace("#", "♯")


def ii_V_I(tonic: int) -> list[tuple[int, str]]:
    """El ii–V–I mayor: la cadencia que define al jazz. Devuelve [(raíz, cualidad)]
    — p. ej. en Do: (Re, m7), (Sol, 7), (Do, maj7)."""
    return [((tonic + 2) % 12, "m7"), ((tonic + 7) % 12, "7"), (tonic % 12, "maj7")]


def turnaround(tonic: int) -> list[tuple[int, str]]:
    """ii–V–I–VI: el ii–V–I con una dominante secundaria (VI7♭9) que cierra el
    giro y empuja de vuelta al ii. En Do: Dm7 · G7 · Cmaj7 · A7♭9."""
    return ii_V_I(tonic) + [((tonic + 9) % 12, "7b9")]
