"""Forest outpost battle: an original, looping orchestral cue in C minor."""


def compose(s):
    s.tempo(122)
    s.meter(4)

    basses = s.part("basses", volume=0.85, pan=-0.18)
    cellos = s.part("cellos", volume=0.72, pan=-0.13)
    violas = s.part("violas", volume=0.65, pan=-0.08)
    violins = s.part("violins", volume=0.68, pan=0.2)
    strings = s.part("strings", volume=0.58, pan=0.13)
    tremolo = s.part("tremolo", volume=0.38, pan=0.16)
    horns = s.part("horns", volume=0.92, pan=-0.1)
    trombones = s.part("trombones", volume=0.78, pan=0.11)
    trumpets = s.part("trumpets", volume=0.7, pan=0.14)
    tuba = s.part("tuba", volume=0.55, pan=0.04)
    flute = s.part("flute", volume=0.48, pan=0.22)
    oboe = s.part("oboe", volume=0.43, pan=-0.2)
    harp = s.part("harp", volume=0.45, pan=-0.3)
    glock = s.part("glockenspiel", volume=0.31, pan=0.29)
    choir = s.part("choir", volume=0.38, pan=0.02)
    timpani = s.part("timpani", volume=0.79, pan=-0.11)
    drums = s.part("percussion", volume=0.75, pan=0.02)

    # Roots are in the double bass register; chord tones are in the viola
    # register. The fourth A chord is a dominant that leads back to C minor.
    minor = (
        (36, (60, 63, 67), (60, 63, 67, 72)),  # C minor
        (32, (56, 60, 63), (60, 63, 68, 72)),  # A-flat major
        (29, (53, 56, 60), (60, 65, 68, 72)),  # F minor
        (31, (55, 59, 62), (59, 62, 67, 71)),  # G major
    )
    # C Lydian's F-sharp gives the major turn a flash of wonder. The
    # chromatic-mediant E major chord makes its second phrase more defiant.
    major = (
        (36, (60, 64, 67), (64, 67, 72, 76)),  # C major
        (32, (56, 60, 63), (63, 68, 72, 75)),  # A-flat major
        (28, (52, 56, 59), (59, 64, 68, 71)),  # E major
        (31, (55, 59, 62), (62, 67, 71, 74)),  # G major
    )

    def note(part, at, length, pitch, velocity):
        part.note(at, length, pitch, velocity)

    def run(part, start, events, shift=0, force=None):
        """Events are (offset, duration, pitch, velocity); None is a rest."""
        for offset, length, pitch, velocity in events:
            if pitch is not None:
                note(part, start + offset, length, pitch + shift,
                     velocity if force is None else force)

    # Six-note battlefield call: rising fourth, minor third, then a falling
    # answer. Its clipped opening and last held note leave a recognizable gap.
    call = (
        (0, .5, 67, 101), (.5, .5, 72, 107), (1, 1, 75, 108),
        (2.25, .5, 74, 98), (2.75, .5, 68, 101), (3.25, .75, 67, 105),
    )
    call_high = (
        (0, .5, 67, 106), (.5, .5, 72, 112), (1, .75, 75, 113),
        (1.75, .25, 77, 99), (2.25, .5, 74, 103),
        (2.75, .5, 68, 106), (3.25, .75, 67, 110),
    )
    answer = (
        (.5, .5, 63, 93), (1, .5, 65, 96),
        (1.5, .5, 67, 99), (2, .5, 68, 100),
        (2.5, 1.5, 67, 104),
    )
    # Broader, brighter B melody: fourth leap and a raised fourth on C.
    bright = (
        (0, 1, 64, 97), (1, .5, 69, 102), (1.5, .5, 71, 103),
        (2, 1, 72, 108), (3.25, .75, 78, 104),
    )
    bright_answer = (
        (.5, .5, 76, 101), (1, .5, 75, 97),
        (1.5, 1, 72, 103), (2.75, .5, 71, 96),
        (3.25, .75, 67, 100),
    )

    def harmony(bar, chord, intensity, is_major=False):
        at = s.bar(bar)
        root, middle, upper = chord
        root2 = root + 12
        # A distinct low line: two pedal blows, a fifth, then an approach.
        for off, length, pitch, accent in (
            (0, .7, root, 9), (.75, .4, root, 0),
            (1.5, .6, root + 7, 3), (2.25, .5, root, 0),
            (3, .45, root + 7, 4), (3.5, .4, root + 2, 0),
        ):
            note(basses, at + off, length, pitch, intensity + accent)
        for off, pitch in ((0, root2), (1.5, root2 + 7),
                           (2.5, root2), (3.25, root2 + 2)):
            note(cellos, at + off, .62, pitch, intensity - 8)
        violas.chord(at, 3.8, middle, intensity - 26)
        strings.chord(at, 3.85, upper[1:3], intensity - 37)
        pattern = (upper[0], upper[1], upper[2], upper[1],
                   upper[0], upper[1], upper[3], upper[1])
        for i, pitch in enumerate(pattern):
            if i in (2, 6) and intensity < 78:
                continue
            note(violins, at + i * .5, .38, pitch, intensity - 21)
        if intensity >= 88:
            note(tuba, at, 1.2, root + 12, intensity - 18)
        if is_major:
            note(harp, at + 3, .34, upper[0], 56)
            note(harp, at + 3.33, .34, upper[1], 59)
            note(harp, at + 3.66, .33, upper[2], 62)
        else:
            note(tremolo, at + 2, 1.8, upper[0], intensity - 38)

    def martial(bar, root, strength, arrival=False, lighter=False):
        at = s.bar(bar)
        drum_root = root + 12
        if drum_root < 41:
            drum_root += 12
        for off, pitch, vel in ((0, drum_root, strength + 4),
                                (1.5, drum_root + 7, strength - 9),
                                (2, drum_root, strength),
                                (3.5, drum_root + 7, strength - 11)):
            note(timpani, at + off, .47, pitch, vel)
        for off in (0, 2):
            note(drums, at + off, .32, "bass_drum", strength - 4)
        if not lighter:
            for off in (1, 3):
                note(drums, at + off, .23, "snare", strength - 10)
            for off in (1.75, 3.75):
                note(drums, at + off, .18, "snare_rim", strength - 27)
            if bar % 4 == 0:
                note(drums, at + 3.25, .25, "low_tom", strength - 12)
                note(drums, at + 3.65, .25, "mid_tom", strength - 8)
        if arrival:
            note(drums, at, 1.6, "crash", strength - 10)

    # Four-bar gathering: the rhythm emerges before the entire theme.
    for i in range(4):
        bar = i + 1
        chord = minor[i]
        harmony(bar, chord, 66 + i * 5)
        martial(bar, chord[0], 70 + i * 4, lighter=i < 2)
        if i == 1:
            run(oboe, s.bar(bar), ((2, .5, 67, 70), (2.5, .5, 72, 74),
                                    (3, .85, 75, 77)))
        if i == 3:
            note(horns, s.bar(bar) + 3, .35, 62, 74)
            note(horns, s.bar(bar) + 3.5, .4, 66, 79)
    strings.swell(s.bar(1), 16, .32, .72)
    timpani.swell(s.bar(1), 16, .42, .82)

    def a_phrase(bar, index, second_pass=False):
        """Eight bars, first call and answer, then a varied response."""
        base = s.bar(bar)
        v = 86 + (7 if second_pass else 0) + (3 if index else 0)
        for j in range(8):
            actual = bar + j
            chord = minor[j % 4]
            strength = 76 + (5 if second_pass else 0) + (3 if index else 0)
            harmony(actual, chord, strength)
            martial(actual, chord[0], strength + 9,
                    arrival=j in (0, 4) and (second_pass or index > 0),
                    lighter=(not second_pass and index == 0 and j in (2, 6)))
        # The call starts in the first bar of the theme and reappears with
        # different ornament or scoring. The intervening bar answers it.
        shape = call_high if index or second_pass else call
        run(horns, base, shape, force=v + 12)
        run(trombones, base, shape, shift=-12, force=v - 1)
        run(horns, base + 4, answer, force=v + 2)
        run(oboe, base + 4, answer, shift=0, force=v - 20)
        if second_pass:
            run(trumpets, base, shape, force=v + 1)
        # A quieter, higher countermelody occupies the gap after the call.
        counter = ((.5, .5, 79, 68), (1.25, .5, 77, 70),
                   (2, .75, 75, 71), (3, .75, 72, 67))
        run(flute if second_pass else oboe, base + 8, counter,
            shift=0 if second_pass else -12)
        # Second call resolves differently so the four-bar unit breathes.
        run(horns, base + 12, shape, shift=-2 if index else 0,
            force=v + 6)
        run(trombones, base + 12, shape, shift=-14 if index else -12,
            force=v - 5)
        run(horns, base + 16, answer, shift=0 if index else -2,
            force=v + 2)
        run(flute, base + 20, counter, force=70 + (7 if second_pass else 0))
        # Phrase ending: a held horn tone and a low dominant pickup.
        note(horns, base + 28, 2.4, 67 if index else 63, v + 4)
        note(trombones, base + 28, 2.2, 55 if index else 51, v - 4)
        note(horns, base + 31.5, .35, 62, v - 12)

    def b_phrase(bar, second_pass=False):
        base = s.bar(bar)
        gain = 7 if second_pass else 0
        for j in range(8):
            actual = bar + j
            chord = major[j % 4]
            strength = 80 + gain + (3 if j >= 4 else 0)
            harmony(actual, chord, strength, is_major=True)
            martial(actual, chord[0], strength + 5,
                    arrival=j in (0, 4), lighter=j in (1, 5))
            if j in (0, 4):
                glock.note(s.bar(actual), .65, 84, 62 + gain)
        for off in (0, 16):
            run(trumpets, base + off, bright, force=99 + gain)
            run(horns, base + off, bright, shift=-12, force=104 + gain)
            run(violins, base + off, bright, force=76 + gain)
            run(horns, base + off + 4, bright_answer,
                shift=-12, force=98 + gain)
            run(oboe, base + off + 4, bright_answer,
                force=76 + gain)
        # Long arcs over the moving bass, with a clear space after each.
        for off, first, second in ((8, 76, 75), (24, 80, 79)):
            note(trumpets, base + off, 1.75, first, 99 + gain)
            note(horns, base + off, 1.75, first - 12, 105 + gain)
            note(trumpets, base + off + 2.25, 1.55, second, 99 + gain)
            note(horns, base + off + 2.25, 1.55, second - 12, 105 + gain)
            note(strings, base + off, 3.7, first - 12, 63 + gain)
        if second_pass:
            choir.chord(base, 7.5, (60, 64, 67), 63)
            choir.chord(base + 16, 7.5, (60, 64, 67), 66)

    def return_phrase(bar, second_pass=False):
        base = s.bar(bar)
        gain = 8 if second_pass else 0
        for j in range(8):
            chord = minor[j % 4]
            strength = 84 + gain + (4 if j >= 4 else 0)
            harmony(bar + j, chord, strength)
            martial(bar + j, chord[0], strength + 6,
                    arrival=j in (0, 4))
        run(horns, base, call_high, force=106 + gain)
        run(trumpets, base, call_high, force=96 + gain)
        run(trombones, base, call_high, shift=-12, force=93 + gain)
        run(horns, base + 4, answer, force=101 + gain)
        run(flute, base + 8, ((.5, .5, 75, 73), (1, .5, 77, 76),
                               (1.5, .5, 79, 77), (2.25, 1.25, 75, 75)))
        run(horns, base + 12, call, force=106 + gain)
        run(trumpets, base + 12, call, force=95 + gain)
        run(trombones, base + 12, call, shift=-12, force=93 + gain)
        run(horns, base + 16, answer, force=100 + gain)
        run(oboe, base + 20, ((.5, .5, 67, 77), (1, .5, 68, 79),
                              (1.5, .75, 72, 82), (2.5, 1.25, 71, 79)))
        # On the last bar, the dominant is left open for the repeat.
        note(horns, base + 28, 2.35, 67, 111 + gain)
        note(trombones, base + 28, 2.35, 55, 99 + gain)
        for off, pitch in ((30.5, 62), (30.83, 66), (31.16, 67)):
            note(trumpets, base + off, .3, pitch, 85 + gain)
        strings.swell(base, 31.8, .62, .94 if second_pass else .83)

    # Two complete 32-bar statements after the introduction.
    for repeat in range(2):
        start = 5 + repeat * 32
        a_phrase(start, 0, repeat == 1)
        a_phrase(start + 8, 1, repeat == 1)
        b_phrase(start + 16, repeat == 1)
        return_phrase(start + 24, repeat == 1)

    # Four-bar ending: victory settles into C minor, with a small G pickup
    # that lets a game loop return naturally to the opening pulse.
    for j in range(4):
        bar = 69 + j
        chord = (minor[0], minor[1], minor[0], minor[3])[j]
        harmony(bar, chord, 82 - j * 7)
        martial(bar, chord[0], 92 - j * 10,
                arrival=j == 0, lighter=j >= 2)
    note(horns, s.bar(69), 1, 67, 110)
    note(horns, s.bar(69) + 1, 1, 72, 113)
    note(horns, s.bar(69) + 2, 2, 75, 112)
    note(trumpets, s.bar(69), 1, 67, 100)
    note(trumpets, s.bar(69) + 1, 1, 72, 103)
    note(trumpets, s.bar(69) + 2, 2, 75, 102)
    note(horns, s.bar(71), 3.3, 72, 98)
    note(trombones, s.bar(71), 3.3, 60, 88)
    choir.chord(s.bar(71), 3.5, (60, 63, 67), 60)
    note(drums, s.bar(72) + 3.4, .28, "snare_rim", 45)
    note(timpani, s.bar(72) + 3.4, .34, 43, 54)
    strings.swell(s.bar(69), 15.8, .9, .28)
    horns.swell(s.bar(69), 15.8, .94, .35)
    s.end(s.bar(73))
