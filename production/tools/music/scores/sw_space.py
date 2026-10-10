"""Starfighter pursuit: a 68-bar, six-beat orchestral cue."""


def compose(s):
    s.tempo(144)
    s.meter(6)

    violins = s.part("violins", volume=0.66, pan=-0.25)
    strings = s.part("strings", volume=0.57, pan=-0.16)
    violas = s.part("violas", volume=0.50, pan=0.05)
    cellos = s.part("cellos", volume=0.66, pan=0.17)
    basses = s.part("basses", volume=0.68, pan=0.22)
    trumpets = s.part("trumpets", volume=0.90, pan=0.20)
    horns = s.part("horns", volume=0.82, pan=-0.12)
    trombones = s.part("trombones", volume=0.72, pan=0.24)
    tuba = s.part("tuba", volume=0.63, pan=0.20)
    flute = s.part("flute", volume=0.53, pan=-0.22)
    oboe = s.part("oboe", volume=0.49, pan=0.08)
    harp = s.part("harp", volume=0.53, pan=-0.28)
    glock = s.part("glockenspiel", volume=0.46, pan=0.32)
    choir = s.part("choir", volume=0.40, pan=0.06)
    timpani = s.part("timpani", volume=0.78, pan=-0.12)
    drums = s.part("percussion", volume=0.76, pan=0.06)

    # Root in octave 2; upper chord tones. The F# in C is the raised fourth.
    em = (40, (64, 67, 71), (64, 69, 72, 71, 76, 74))
    clyd = (36, (64, 66, 71), (64, 70, 74, 71, 76, 78))
    g = (43, (62, 67, 71), (67, 72, 76, 74, 79, 78))
    d = (38, (62, 66, 69), (66, 71, 74, 73, 78, 76))
    am = (45, (64, 69, 72), (69, 74, 77, 76, 81, 79))
    b7 = (35, (63, 66, 69), (63, 68, 72, 69, 75, 73))
    ab = (44, (63, 68, 72), (68, 73, 77, 75, 80, 78))
    e = (40, (64, 68, 71), (64, 69, 73, 71, 76, 75))
    c = (36, (64, 67, 72), (64, 69, 72, 71, 76, 74))

    cycle = [
        em, clyd, g, d, em, c, am, b7,
        em, ab, c, b7, em, clyd, d, b7,
        e, c, ab, b7, g, d, clyd, b7,
        em, clyd, g, d, em, ab, c, b7,
    ]

    # The six-note signal: an upward fourth, a further leap, a retreat,
    # then a higher arrival. Its eighth-note launches leave a breath at end.
    def signal(start, tones, target, velocity, variant=0):
        attacks = (0, 0.5, 1, 2.5, 3, 4.5)
        lengths = (0.5, 0.5, 1.5, 0.5, 1.5, 0.75)
        if variant == 1:
            attacks = (0, 0.5, 1.25, 2.5, 3.25, 4.75)
            lengths = (0.5, 0.5, 1.0, 0.5, 1.25, 0.75)
        elif variant == 2:
            attacks = (0.25, 0.75, 1.25, 2.75, 3.25, 4.75)
            lengths = (0.5, 0.5, 1.25, 0.5, 1.25, 0.75)
        for i, (at, dur) in enumerate(zip(attacks, lengths)):
            target.note(start + at, dur, tones[i], velocity + (5 if i == 4 else 0))

    def answer(start, tones, target, velocity, variation=0):
        if variation:
            events = ((0.5, 0.5, tones[4]), (1, 0.5, tones[3]),
                      (1.5, 1, tones[2]), (3, 2, tones[1]))
        else:
            events = ((0.5, 1, tones[4]), (2, 0.5, tones[3]),
                      (2.5, 0.5, tones[2]), (3.5, 1.75, tones[0]))
        for at, dur, pitch in events:
            target.note(start + at, dur, pitch, velocity)

    def ostinato(start, chord, bar_index, second):
        # Four groups of sixteenths, with tiny gaps for brass attacks.
        a, b, c0 = chord
        figure = (a + 12, b + 12, c0 + 12, b + 12,
                  a + 12, b + 12, c0 + 12, b + 12)
        if bar_index % 2:
            figure = (b + 12, c0 + 12, a + 12, c0 + 12,
                      b + 12, a + 12, c0 + 12, a + 12)
        for group in range(3):
            for i, pitch in enumerate(figure):
                if i == 7 and group == 2:
                    continue
                violins.note(start + group * 2 + i * 0.25, 0.21,
                             pitch, 63 + 5 * second + (7 if i == 0 else 0))

    def bass_motion(start, root, strong):
        basses.note(start, 1.4, max(24, root - 12), 75 + strong)
        basses.note(start + 2, 0.75, root - 5, 65 + strong)
        basses.note(start + 3, 1.35, max(24, root - 12), 72 + strong)
        basses.note(start + 5, 0.7, root - 2, 70 + strong)
        cellos.note(start, 1.35, root, 76 + strong)
        cellos.note(start + 1.5, 0.45, root + 7, 67 + strong)
        cellos.note(start + 2, 0.7, root + 12, 70 + strong)
        cellos.note(start + 3, 1.2, root + 7, 72 + strong)
        cellos.note(start + 4.5, 0.45, root + 2, 64 + strong)
        cellos.note(start + 5, 0.75, root + 7, 70 + strong)

    def rhythm(start, root, bar_number, second, arrival):
        timpani_root = root if root >= 38 else root + 12
        timpani.note(start, 0.75, timpani_root, 87 if arrival else 73)
        timpani.note(start + 3, 0.65, timpani_root + 7, 76 + 5 * second)
        if arrival:
            timpani.note(start + 5, 0.7, timpani_root, 77)
        for beat in (0, 3):
            drums.note(start + beat, 0.22, "bass_drum", 85 if beat == 0 else 72)
        for beat in (1.5, 4.5):
            drums.note(start + beat, 0.18, "snare", 73 + 7 * second)
        if bar_number % 2 == 0:
            drums.note(start + 5.5, 0.18, "snare_rim", 54)
        if arrival:
            drums.note(start, 1.5, "crash", 83 if second else 72)

    def sparkle(start, chord, bright):
        a, b, c0 = chord
        for i, pitch in enumerate((a + 24, b + 24, c0 + 24, b + 24)):
            harp.note(start + 4 + i * 0.25, 0.33, pitch - 12, 55 + 5 * bright)
        if bright:
            glock.note(start + 0.25, 0.45, c0 + 24, 61)
            glock.note(start + 3.25, 0.55, b + 24, 58)

    for pass_number in range(2):
        second = pass_number == 1
        for index, (root, chord, tones) in enumerate(cycle):
            bar_number = pass_number * 32 + index + 1
            start = s.bar(bar_number)
            section = index // 8
            place = index % 8
            arrival = place == 0 or (index == 16 or index == 24)
            bass_motion(start, root, 4 if second else 0)
            ostinato(start, chord, index, second)
            rhythm(start, root, bar_number, second, arrival)
            strings.chord(start, 5.65, chord, 58 + 6 * second)
            violas.note(start + 0.5, 2.0, chord[1] - 12, 59 + 4 * second)
            violas.note(start + 3.5, 2.0, chord[2] - 12, 58 + 4 * second)
            sparkle(start, chord, place in (0, 3, 6) or (second and place == 4))

            if place % 2 == 0:
                if section == 2:
                    # Lyrical, wider B melody above a restrained pulse.
                    for at, dur, tone in ((0, 1.5, tones[2]),
                                          (1.5, 1, tones[3]),
                                          (3, 2.25, tones[4])):
                        horns.note(start + at, dur, tone - 12, 81 + 4 * second)
                        strings.note(start + at, dur, tone, 72 + 4 * second)
                    flute.note(start + 4.5, 1.1, tones[5] + 12, 62)
                else:
                    variation = (pass_number + place // 2 + (section == 3)) % 3
                    signal(start, tones, trumpets, 92 + 4 * second, variation)
                    if second or place in (0, 4):
                        signal(start, tuple(x - 12 for x in tones), horns,
                               77 + 5 * second, variation)
                    if section == 3 and place >= 4:
                        trombones.chord(start + 3, 0.75,
                                        (chord[0] - 12, chord[2] - 12), 76)
            else:
                if section == 2:
                    answer(start, tones, oboe, 70 + 3 * second, place % 4 == 3)
                    horns.note(start + 3.5, 1.9, tones[0] - 12, 67)
                else:
                    answer(start, tones, horns, 78 + 4 * second,
                           (place + pass_number) % 4 == 3)
                    if second and place in (3, 7):
                        answer(start, tuple(x + 12 for x in tones), flute, 64, 1)
                    if place in (3, 7):
                        trumpets.note(start + 5.25, 0.5, tones[0], 74)

            if place in (0, 4):
                trombones.chord(start, 0.75,
                                (chord[0] - 12, chord[1] - 12), 76 + 5 * second)
                tuba.note(start, 1, max(26, root - 12), 79)
            if place in (2, 6):
                horns.chord(start + 5, 0.7, (chord[0] - 12, chord[2] - 12),
                            69 + 5 * second)
            if section == 2 and place in (1, 2, 3, 6):
                choir.chord(start + 0.5, 4.8, chord, 49 + 5 * second)
            if second and section in (0, 3) and place % 2 == 1:
                # A descending woodwind answer remains between brass phrases.
                flute.note(start + 1, 0.65, tones[5] + 12, 62)
                flute.note(start + 2, 0.65, tones[3] + 12, 60)
                oboe.note(start + 3, 1.0, tones[2], 59)
            if bar_number in (8, 16, 24, 32, 40, 48, 56, 64):
                strings.swell(start + 3, 3, 0.52, 0.91)
                horns.swell(start + 3, 3, 0.58, 0.94)

    # Four-bar coda: one last signal, a bright E-major glimpse, and Em home.
    for offset, (root, chord, tones) in enumerate((em, clyd, e, em)):
        start = s.bar(65 + offset)
        bass_motion(start, root, 5)
        strings.chord(start, 5.8, chord, 71)
        ostinato(start, chord, offset, True)
        rhythm(start, root, 65 + offset, True, offset in (0, 3))
        sparkle(start, chord, True)
        if offset == 0:
            signal(start, tones, trumpets, 101, 1)
            signal(start, tuple(x - 12 for x in tones), horns, 88, 1)
        elif offset == 1:
            answer(start, tones, horns, 83)
        elif offset == 2:
            trumpets.note(start + 0.5, 1, 68, 89)
            trumpets.note(start + 2, 1, 71, 92)
            trumpets.note(start + 3.5, 1.7, 76, 99)
            trombones.chord(start + 3.5, 1.4, (52, 56, 59), 83)
        else:
            trumpets.note(start, 4.75, 76, 102)
            horns.chord(start, 4.8, (52, 59, 64), 91)
            trombones.chord(start, 4.7, (52, 55, 59), 88)
            tuba.note(start, 4.5, 28, 86)
            choir.chord(start, 4.9, (64, 67, 71), 66)
            drums.note(start, 2, "crash2", 92)
            strings.swell(start + 3, 2.5, 0.95, 0.42)
            horns.swell(start + 3, 2.5, 0.94, 0.45)

    s.end(s.bar(69))
