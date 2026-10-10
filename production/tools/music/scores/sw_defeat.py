"""A short, unlooped A-minor defeat cue (four bars at 80 BPM)."""


def compose(s):
    s.tempo(80)
    s.meter(4)

    horn = s.part("horns", volume=0.87, pan=-0.13, reverb=0.35)
    low_strings = s.part("strings", volume=0.68, pan=0.12, reverb=0.40)
    violas = s.part("violas", volume=0.56, pan=-0.17, reverb=0.36)
    cellos = s.part("cellos", volume=0.72, pan=0.15, reverb=0.35)
    basses = s.part("basses", volume=0.74, pan=0.08, reverb=0.32)
    bassoon = s.part("bassoon", volume=0.49, pan=0.03, reverb=0.34)
    trombones = s.part("trombones", volume=0.48, pan=0.16, reverb=0.43)
    timpani = s.part("timpani", volume=0.53, pan=-0.06, reverb=0.39)
    perc = s.part("percussion", volume=0.40, pan=0.07, reverb=0.52)

    # A falling minor third, a brief upward reach, then a long sigh.
    # The same contour returns in a lower register as a quiet answer.
    motif = [(0.0, 0.5, 0, 78), (0.5, 0.5, -3, 73),
             (1.25, 0.75, 2, 81), (2.25, 1.25, -2, 77)]

    def play_motif(part, start, pitches, change=0, softness=0):
        for offset, duration, degree, velocity in motif:
            part.note(start + offset + (0.125 if offset == 1.25 and change else 0),
                      duration - (0.125 if offset == 1.25 and change else 0),
                      pitches[degree], velocity - softness)

    # Degree offsets let the hook change harmony without repeating a fixed lick.
    play_motif(horn, s.bar(1), {-3: "E4", -2: "F4", 0: "G4", 2: "B4"})
    play_motif(horn, s.bar(2), {-3: "D4", -2: "E4", 0: "F4", 2: "A4"},
               change=1, softness=5)
    horn.note(s.bar(3), 0.75, "F4", 73)
    horn.note(s.bar(3) + 1.0, 0.75, "E4", 70)
    horn.note(s.bar(3) + 2.0, 1.5, "D4", 67)
    horn.note(s.bar(4), 2.75, "C4", 69)
    horn.note(s.bar(4) + 3.0, 0.65, "A3", 56)

    # Each bar's inner voices descend while the bass traces its own descent.
    harmony = [
        ("A3", "C4", "E4"),
        ("G3", "B3", "D4"),
        ("F3", "A3", "D4"),
        ("A3", "C4", "E4"),
    ]
    for bar, chord in enumerate(harmony, 1):
        start = s.bar(bar)
        low_strings.chord(start, 3.85, chord, 58 if bar < 4 else 53)
        violas.note(start, 3.7, chord[1], 53)

    bass_motion = [
        ("A2", "G2", "F2", "E2"),
        ("G2", "F2", "E2", "D2"),
        ("F2", "E2", "D2", "E2"),
        ("A2", "A2", "A2", "A2"),
    ]
    for bar, notes in enumerate(bass_motion, 1):
        start = s.bar(bar)
        for beat, pitch in enumerate(notes):
            cellos.note(start + beat, 0.94, pitch, 61 - 2 * bar)
        basses.note(start, 1.85, ("A1", "G1", "F1", "A1")[bar - 1], 60)
        basses.note(start + 2, 1.7, ("F1", "E1", "D1", "A1")[bar - 1], 54)

    # A restrained low brass shadow and a single final tam-tam wash.
    bassoon.note(s.bar(2) + 2.0, 1.7, "D3", 51)
    bassoon.note(s.bar(3) + 2.0, 1.65, "E3", 50)
    trombones.chord(s.bar(4), 3.5, ["A2", "E3", "C4"], 53)
    timpani.note(s.bar(1), 1.4, "A2", 48)
    timpani.note(s.bar(3), 1.2, "D3", 45)
    timpani.note(s.bar(4), 2.1, "A2", 51)
    perc.note(s.bar(4), 2.6, "tam_tam", 40)

    horn.swell(s.bar(1), 6, 0.66, 0.90)
    horn.swell(s.bar(3), 5, 0.86, 0.53)
    low_strings.swell(s.bar(1), 12, 0.62, 0.86)
    low_strings.swell(s.bar(4), 4, 0.76, 0.27)
    trombones.swell(s.bar(4), 4, 0.70, 0.29)
    s.end(s.bar(5))
