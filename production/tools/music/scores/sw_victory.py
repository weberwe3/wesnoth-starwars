"""Short, original C-major victory fanfare for full orchestra."""


def compose(s):
    s.tempo(160)
    s.meter(4)

    trumpet = s.part("trumpets", volume=0.98, pan=0.18, reverb=0.28)
    horn = s.part("horns", volume=0.88, pan=-0.20, reverb=0.34)
    trombone = s.part("trombones", volume=0.78, pan=-0.10)
    tuba = s.part("tuba", volume=0.69, pan=-0.16)
    upper = s.part("violins", volume=0.68, pan=-0.34)
    sustained = s.part("strings", volume=0.65, pan=0.27)
    viola = s.part("violas", volume=0.58, pan=0.14)
    cello = s.part("cellos", volume=0.65, pan=0.19)
    bass = s.part("basses", volume=0.72, pan=0.05)
    harp = s.part("harp", volume=0.63, pan=-0.30)
    glock = s.part("glockenspiel", volume=0.46, pan=0.29)
    timp = s.part("timpani", volume=0.80, pan=-0.12)
    drums = s.part("percussion", volume=0.76, pan=0.08)

    # The five-note figure rises a fourth, climbs again, then settles by step.
    # The rest before its last note leaves space for a brass answer.
    hook = ((0, .5, 67), (.5, .5, 72), (1, 1, 76),
            (2, .5, 74), (3, 1, 72))

    def motif(part, bar, shift=0, speed=1, velocity=106, offset=0):
        start = s.bar(bar) + offset
        for at, duration, pitch in hook:
            part.note(start + at * speed, duration * speed,
                      pitch + shift, velocity)

    # Two-bar calls and answers; the final return broadens the rhythm.
    motif(trumpet, 1)
    motif(horn, 1, shift=-12, velocity=94)
    trumpet.note(s.bar(2), .5, 76, 103)
    trumpet.note(s.bar(2) + .5, .5, 79, 109)
    trumpet.note(s.bar(2) + 1, 1, 77, 107)
    trumpet.note(s.bar(2) + 2, 2, 76, 101)
    for at, dur, pitch in ((0, .5, 64), (.5, .5, 67),
                            (1, 1, 65), (2, 2, 64)):
        horn.note(s.bar(2) + at, dur, pitch, 91)

    motif(horn, 3, shift=-3, velocity=97)
    motif(trumpet, 3, shift=-3, velocity=94)
    # Three quick notes launch the second phrase into the dominant.
    for i, pitch in enumerate((67, 69, 71)):
        trumpet.note(s.bar(4) + i / 3, 1 / 3, pitch, 99)
    trumpet.note(s.bar(4) + 1, 1, 74, 107)
    trumpet.note(s.bar(4) + 2, 2, 71, 101)
    horn.chord(s.bar(4), 2, (59, 62, 67), 80)
    horn.chord(s.bar(4) + 2, 2, (59, 62, 67), 87)

    motif(trumpet, 5, shift=0, speed=.75, velocity=112)
    motif(horn, 5, shift=-12, speed=.75, velocity=99)
    trumpet.note(s.bar(5) + 3, 1, 79, 109)
    horn.note(s.bar(5) + 3, 1, 67, 95)
    for at, dur, pitch in ((0, .5, 81), (.5, .5, 79),
                            (1, 1, 77), (2, 1, 74), (3, 1, 71)):
        trumpet.note(s.bar(6) + at, dur, pitch, 105)
        horn.note(s.bar(6) + at, dur, pitch - 12, 91)

    # Cadential ascent answers the hook, then opens into a held tonic.
    for at, dur, pitch in ((0, .5, 67), (.5, .5, 72),
                            (1, .5, 74), (1.5, .5, 79), (2, 2, 83)):
        trumpet.note(s.bar(7) + at, dur, pitch, 109)
        horn.note(s.bar(7) + at, dur, pitch - 12, 96)
    trumpet.chord(s.bar(8), 4, (72, 76, 79), 116)
    horn.chord(s.bar(8), 4, (60, 64, 67), 106)
    trombone.chord(s.bar(8), 4, (48, 55, 60), 102)
    tuba.note(s.bar(8), 4, 36, 99)

    # A changing, clear bass line supports four two-bar harmonic gestures.
    harmony = (
        (0, (48, 55, 60), 36), (1, (53, 57, 60), 41),
        (2, (45, 52, 57), 33), (3, (43, 50, 55), 31),
        (4, (53, 57, 60), 41), (5, (43, 50, 55), 31),
        (6, (43, 50, 55), 31), (7, (48, 55, 60), 36),
    )
    for index, chord, root in harmony:
        bar = index + 1
        start = s.bar(bar)
        length = 4
        sustained.chord(start, length, tuple(p + 12 for p in chord),
                        67 if index < 6 else 85)
        viola.chord(start, length, chord[1:], 68 if index < 6 else 81)
        cello.note(start, 2, root + 12, 77)
        bass.note(start, 2, root, 83)
        if index < 7:
            fifth = root + 7
            cello.note(start + 2, 1, fifth + 12, 76)
            cello.note(start + 3, 1, root + 12, 78)
            bass.note(start + 2, 1, fifth, 77)
            bass.note(start + 3, 1, root, 82)
        else:
            cello.note(start + 2, 2, root + 12, 81)
            bass.note(start + 2, 2, root, 88)

    # Eighth-note string motion is light enough to leave the brass in front.
    figures = ((60, 64, 67, 64), (60, 65, 69, 65),
               (57, 60, 64, 60), (59, 62, 67, 62),
               (60, 65, 69, 65), (59, 62, 67, 62))
    for bar, figure in enumerate(figures, 1):
        start = s.bar(bar)
        for beat in range(8):
            upper.note(start + beat * .5, .46,
                       figure[beat % 4] + 12, 63 if beat % 2 else 70)
    upper.line(s.bar(7), ((.5, 79, 78), (.5, 76, 76),
                          (.5, 74, 77), (.5, 71, 78),
                          (2, 72, 86)))
    upper.chord(s.bar(8), 4, (72, 76, 79), 84)

    # Sparse punctuation; a sustained roll grows into the last chord.
    for bar in (1, 3, 5, 7):
        timp.note(s.bar(bar), .7, 48 if bar in (1, 5) else 43, 85)
        drums.note(s.bar(bar), .25, "bass_drum", 79)
    for bar in (2, 4, 6):
        drums.note(s.bar(bar) + 2, .25, "snare", 68)
        drums.note(s.bar(bar) + 3, .25, "snare", 74)
    drums.note(s.bar(4), .8, "crash", 77)
    for stroke in range(8):
        timp.note(s.bar(7) + 2 + stroke * .25, .24, 43,
                  73 + stroke * 3)
    drums.note(s.bar(7) + 2, 1.85, "snare_roll", 78)
    drums.note(s.bar(8), 1.6, "crash", 109)
    drums.note(s.bar(8), .5, "bass_drum", 103)
    timp.note(s.bar(8), 3.5, 48, 106)

    # An ascending diatonic harp sweep crosses the arrival and glitters above it.
    gliss = (48, 52, 55, 60, 64, 67, 72, 76, 79, 84)
    for i, pitch in enumerate(gliss):
        harp.note(s.bar(7) + 3 + i * .14, .54, pitch, 71 + i * 2)
    glock.note(s.bar(8), 1.5, 84, 83)
    glock.note(s.bar(8) + 1.5, 1.2, 79, 68)

    for part in (trumpet, horn, sustained, upper, trombone):
        part.swell(s.bar(7), 1, .73, 1)
        part.swell(s.bar(8), 4, 1, .76)
    s.end(s.bar(9))
