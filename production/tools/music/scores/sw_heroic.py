"""A bright, loopable republic battle march in B-flat major."""


def compose(s):
    s.tempo(108)
    s.meter(4)

    trumpets = s.part("trumpets", volume=0.94, pan=0.12)
    horns = s.part("horns", volume=0.86, pan=-0.18)
    trombones = s.part("trombones", volume=0.72, pan=0.24)
    tuba = s.part("tuba", volume=0.72, pan=0.12)
    violins = s.part("violins", volume=0.75, pan=-0.36)
    strings = s.part("strings", volume=0.62, pan=-0.24)
    violas = s.part("violas", volume=0.64, pan=0.14)
    cellos = s.part("cellos", volume=0.77, pan=0.25)
    basses = s.part("basses", volume=0.71, pan=0.31)
    flute = s.part("flute", volume=0.61, pan=-0.12)
    oboe = s.part("oboe", volume=0.57, pan=0.08)
    harp = s.part("harp", volume=0.53, pan=-0.29)
    glock = s.part("glockenspiel", volume=0.43, pan=0.29)
    timpani = s.part("timpani", volume=0.75, pan=0.11)
    drums = s.part("percussion", volume=0.72, pan=0.04)

    # Chord tones run from bass root through a compact middle register.
    harmony = {
        "Bb": (34, (58, 62, 65, 70)),
        "Gm": (31, (55, 58, 62, 67)),
        "Eb": (39, (55, 58, 63, 67)),
        "F": (41, (53, 57, 60, 65)),
        "Dm": (38, (53, 57, 62, 65)),
        "Cm": (36, (55, 60, 63, 67)),
        "F7": (41, (53, 57, 63, 65)),
        "C": (36, (55, 60, 64, 67)),
        "Ab": (32, (56, 60, 63, 68)),
    }
    a_chords = ["Bb", "Gm", "Eb", "F", "Dm", "Gm", "Cm", "Bb"]
    ap_chords = ["Bb", "Gm", "Eb", "F", "Dm", "Gm", "Cm", "F7"]
    b_chords = ["Eb", "C", "Ab", "F7", "Gm", "Eb", "Cm", "F7"]

    # Original five-note crest: an eighth-note launch, a fourth, a dip,
    # then a leap up to a sustained high note. Pitches are MIDI integers.
    hook = [(0.5, 0.5, 65), (1, 0.75, 70), (2, 0.5, 74),
            (2.5, 0.5, 72), (3, 1, 77)]
    hook_high = [(0, 0.25, 74), (0.25, 0.25, 76),
                 (0.5, 0.5, 77), (1, 0.75, 70),
                 (2, 0.5, 74), (2.5, 0.5, 72), (3, 1, 77)]

    a_melody = [
        hook,
        [(0, 1.5, 77), (2, 0.5, 75), (2.5, 0.5, 74), (3, 1, 70)],
        [(0.5, 0.5, 67), (1, 1, 70), (2, 0.5, 75),
         (2.5, 0.5, 74), (3, 1, 79)],
        [(0, 0.5, 77), (0.5, 0.5, 76), (1, 1, 72),
         (2.5, 0.5, 69), (3, 1, 72)],
        [(0.5, 0.5, 69), (1, 0.75, 74), (2, 0.5, 77),
         (2.5, 0.5, 76), (3, 1, 81)],
        [(0, 1.5, 79), (2, 0.5, 77), (2.5, 0.5, 74), (3, 1, 70)],
        [(0, 0.5, 72), (0.5, 0.5, 75), (1, 1, 79),
         (2.5, 0.5, 75), (3, 1, 72)],
        [(0, 0.5, 69), (0.5, 0.5, 72), (1, 0.5, 77),
         (1.5, 0.5, 74), (2, 2, 70)],
    ]
    b_melody = [
        [(0, 1, 70), (1.5, 0.5, 72), (2, 1, 74), (3, 1, 79)],
        [(0, 1.5, 76), (2, 0.5, 74), (2.5, 0.5, 72), (3, 1, 67)],
        [(0.5, 0.5, 68), (1, 1, 72), (2, 0.5, 75), (2.5, 0.5, 72),
         (3, 1, 80)],
        [(0, 1, 77), (1.5, 0.5, 75), (2, 1, 72), (3, 1, 69)],
        [(0, 1, 70), (1.5, 0.5, 74), (2, 1, 79), (3, 1, 82)],
        [(0, 1.5, 79), (2, 0.5, 77), (2.5, 0.5, 75), (3, 1, 70)],
        [(0.5, 0.5, 67), (1, 1, 72), (2, 0.5, 75),
         (2.5, 0.5, 79), (3, 1, 75)],
        [(0, 1, 77), (1.5, 0.5, 76), (2, 0.5, 74),
         (2.5, 0.5, 72), (3, 1, 69)],
    ]

    def place(part, bar, events, shift=0, vel=90):
        start = s.bar(bar)
        for offset, duration, pitch in events:
            part.note(start + offset, duration, pitch + shift, vel)

    def brass_theme(bar, events, force=96, horns_only=False):
        lead = horns if horns_only else trumpets
        place(lead, bar, events, vel=force)
        if not horns_only:
            # A lower octave on horns thickens the crest without masking it.
            place(horns, bar, events, shift=-12, vel=force - 10)

    def ostinato(bar, name, full):
        root, chord = harmony[name]
        t = s.bar(bar)
        # Long-short-short gallop in each half-bar, with a different upper tone.
        pitches = (chord[1], chord[2], chord[3], chord[2], chord[1], chord[3])
        for offset, dur, pitch in zip(
            (0, 0.75, 1.5, 2, 2.75, 3.5),
            (0.65, 0.35, 0.35, 0.65, 0.35, 0.35), pitches
        ):
            violins.note(t + offset, dur, pitch + 12, 68 + (9 if full else 0))
        strings.chord(t, 3.75, chord[1:4], 57 + (7 if full else 0))
        violas.note(t, 1.7, chord[1], 65)
        violas.note(t + 2, 1.7, chord[2], 68)
        cellos.note(t, 1.35, root + 12, 83)
        cellos.note(t + 1.5, 0.4, root + 19, 73)
        cellos.note(t + 2, 1.25, root + 12, 80)
        cellos.note(t + 3.5, 0.4, root + 19, 72)
        basses.note(t, 1.6, root, 78)
        basses.note(t + 2, 1.6, root, 75)
        tuba.note(t, 0.8, root, 71 + (7 if full else 0))
        tuba.note(t + 2, 0.7, root, 68 + (7 if full else 0))
        if bar % 2 == 1:
            harp.note(t + 0.5, 0.5, chord[0], 59)
            harp.note(t + 1, 0.5, chord[2], 62)
            harp.note(t + 1.5, 0.5, chord[3], 64)

    def percussion(bar, full, arrival=False, light=False, name=None):
        t = s.bar(bar)
        chord_name = name or chord_for_bar(bar)
        root = harmony[chord_name][0]
        if arrival:
            drums.note(t, 1, "crash", 95 + (10 if full else 0))
            timpani.note(t, 1.1, max(38, root + 12), 96)
            trombones.chord(t, 1.6, harmony[chord_name][1][:3], 84)
        if not light:
            for offset in (0, 2):
                drums.note(t + offset, 0.25, "bass_drum", 82)
            for offset in (1, 3):
                drums.note(t + offset, 0.25, "snare", 73 + (8 if full else 0))
            if full:
                drums.note(t + 1.5, 0.2, "snare_rim", 49)
                drums.note(t + 3.5, 0.2, "snare_rim", 49)
        elif bar % 2 == 0:
            drums.note(t + 3, 0.8, "suspended_cymbal", 49)

    def chord_for_bar(bar):
        i = (bar - 1) % 32
        if i < 8:
            return a_chords[i]
        if i < 16:
            return ap_chords[i - 8]
        if i < 24:
            return b_chords[i - 16]
        return ap_chords[i - 24]

    # Two complete 32-bar statements. The second gains a high answering line,
    # fuller snare rhythm, and extra brass at its cadences.
    for cycle in range(2):
        full = cycle == 1
        base = cycle * 32
        for local in range(1, 33):
            bar = base + local
            section = (local - 1) // 8
            phrase_bar = (local - 1) % 8
            name = chord_for_bar(bar)
            ostinato(bar, name, full)
            arrival = phrase_bar == 7 and section in (0, 1)
            percussion(bar, full, arrival=arrival, light=section == 2)

            if section == 2:
                # Broad B melody, mainly horns; an octave of oboe on the
                # second pass brings a gentler reply above the strings.
                events = b_melody[phrase_bar]
                place(horns, bar, events, shift=-12, vel=83 + (6 if full else 0))
                place(flute, bar, events, vel=72 + (5 if full else 0))
                if full and phrase_bar % 2 == 1:
                    place(oboe, bar, events, vel=66)
            else:
                events = a_melody[phrase_bar]
                if section == 1 and phrase_bar == 0:
                    events = hook_high
                if section == 3 and phrase_bar == 0:
                    events = [(0, 0.5, 70)] + [(x, d, p) for x, d, p in hook]
                if section == 3 and phrase_bar == 7:
                    # Dominant ending gives bar one a natural new launch.
                    events = [(0, 0.5, 69), (0.5, 0.5, 72),
                              (1, 0.5, 77), (1.5, 0.5, 76), (2, 2, 72)]
                brass_theme(bar, events, 91 + (8 if full else 0))
                if full and phrase_bar in (2, 5):
                    # Answer in the open space after a crest.
                    flute.note(s.bar(bar) + 2, 0.5, 82, 66)
                    flute.note(s.bar(bar) + 2.5, 0.5, 79, 63)
                    flute.note(s.bar(bar) + 3, 0.75, 77, 67)
                if section == 1 and phrase_bar in (3, 7):
                    glock.note(s.bar(bar) + 3, 0.8, 84, 62)

            if phrase_bar == 6:
                timpani.swell(s.bar(bar), 8, 0.48, 0.9)
                strings.swell(s.bar(bar), 8, 0.62, 0.96)
            if section == 2 and phrase_bar == 0:
                horns.swell(s.bar(bar), 8, 0.55, 0.83)

    # A four-bar tag settles on B-flat while leaving the gallop in motion.
    for bar, name in zip(range(65, 69), ("Eb", "F7", "Bb", "Bb")):
        ostinato(bar, name, True)
        percussion(bar, True, arrival=bar in (67, 68), light=bar == 65,
                   name=name)
    place(trumpets, 65, [(0.5, 0.5, 75), (1, 1, 79),
                         (2.5, 0.5, 77), (3, 1, 75)], vel=98)
    place(horns, 65, [(0.5, 0.5, 63), (1, 1, 67),
                      (2.5, 0.5, 65), (3, 1, 63)], vel=89)
    place(trumpets, 66, [(0, 0.5, 72), (0.5, 0.5, 74),
                         (1, 0.5, 76), (1.5, 0.5, 77),
                         (2, 1.5, 81)], vel=101)
    place(horns, 66, [(0, 0.5, 60), (0.5, 0.5, 62),
                      (1, 0.5, 64), (1.5, 0.5, 65),
                      (2, 1.5, 69)], vel=92)
    for part, pitches, velocity in (
        (trumpets, (70, 74, 77), 105),
        (horns, (58, 65, 70), 99),
        (trombones, (58, 62, 65), 96),
        (strings, (58, 62, 65, 70), 79),
    ):
        part.chord(s.bar(67), 3.6, pitches, velocity)
    trumpets.note(s.bar(68), 3.5, 70, 89)
    horns.chord(s.bar(68), 3.5, (58, 65, 70), 82)
    harp.line(s.bar(68), [(0.25, 58, 58), (0.25, 62, 60),
                          (0.25, 65, 62), (0.25, 70, 64)])
    glock.note(s.bar(68) + 0.5, 1.7, 82, 61)
    strings.swell(s.bar(67), 8, 0.95, 0.35)
    s.end(s.bar(69))
