"""Wild-world exploration cue in D Dorian, for the orchestral score API."""


def compose(s):
    s.tempo(96)
    s.meter(4)

    flute = s.part("flute", volume=0.82, pan=0.18)
    english = s.part("english_horn", volume=0.78, pan=-0.12)
    harp = s.part("harp", volume=0.68, pan=-0.27)
    strings = s.part("strings", volume=0.58, pan=0.08)
    violins = s.part("violins", volume=0.49, pan=0.22)
    violas = s.part("violas", volume=0.52, pan=-0.17)
    cellos = s.part("cellos", volume=0.65, pan=-0.12)
    basses = s.part("basses", volume=0.65)
    voices = s.part("voices", volume=0.42, reverb=0.72)
    horns = s.part("horns", volume=0.59, pan=-0.14)
    trumpets = s.part("trumpets", volume=0.42, pan=0.16)
    timpani = s.part("timpani", volume=0.48)
    perc = s.part("percussion", volume=0.52)
    celesta = s.part("celesta", volume=0.32, pan=0.3)

    # Root, third, fifth, sixth/seventh, ninth. The recurring D-G-C-A
    # progression keeps B natural audible; the B passage shifts its light.
    harmony = {
        "Dm": (50, (62, 65, 69, 71, 76)),
        "G": (43, (59, 62, 67, 71, 76)),
        "C": (48, (60, 64, 67, 71, 74)),
        "Am": (45, (57, 60, 64, 67, 71)),
        "F": (41, (60, 64, 65, 69, 72)),
        "Eb": (39, (58, 62, 63, 67, 70)),
        "Bb": (46, (58, 62, 65, 69, 72)),
        "A7": (45, (57, 61, 64, 67, 71)),
    }
    a_chords = ("Dm", "G", "C", "Am", "Dm", "G", "C", "A7")
    ap_chords = ("Dm", "G", "C", "Am", "F", "G", "Dm", "A7")
    b_chords = ("F", "Eb", "Bb", "A7", "F", "G", "Eb", "A7")
    aa_chords = ("Dm", "G", "C", "Am", "Dm", "G", "C", "A7")
    form = a_chords + ap_chords + b_chords + aa_chords

    def notes(part, bar, events, shift=0, strength=1.0):
        t = s.bar(bar)
        for offset, dur, pitch, vel in events:
            if pitch is not None:
                part.note(t + offset, dur, pitch + shift, int(vel * strength))

    # Five-note hook: quick rising fourth, rising third, a held fall,
    # then a shorter inward answer. Its rests leave space for the forest.
    hook = ((0, .5, 69, 78), (.5, .5, 74, 85),
            (1, 1.5, 77, 88), (2.5, .5, 76, 75),
            (3, 1, 72, 78))
    answer = ((.5, .5, 67, 70), (1, .5, 71, 77),
              (1.5, 1, 74, 81), (2.5, .5, 72, 71),
              (3, 1, 69, 74))
    ascent = ((0, .5, 72, 75), (.5, .5, 74, 79),
              (1, 1, 77, 86), (2, .5, 79, 84),
              (2.5, .5, 77, 77), (3, 1, 76, 82))
    release = ((0, 1, 74, 78), (1.5, .5, 72, 73),
               (2, 2, 69, 76))
    b_melody = (
        ((0, 1, 72, 78), (1, .5, 76, 82),
         (1.5, .5, 79, 85), (2, 2, 77, 81)),
        ((0, .5, 75, 75), (.5, .5, 79, 82),
         (1, 1, 82, 84), (2.5, .5, 79, 75), (3, 1, 77, 76)),
        ((.5, .5, 74, 75), (1, 1, 77, 80),
         (2, .5, 79, 82), (2.5, 1.5, 81, 84)),
        ((0, 1, 79, 80), (1.5, .5, 76, 74),
         (2, 2, 73, 79)),
    )

    def melody(bar, local, pass_no):
        section = local // 8
        at = local % 8
        lead = english if (section == 0 and pass_no == 0) or section == 2 else flute
        if section == 2:
            events = b_melody[at % 4]
            if at >= 4:
                # Reprise of the contrasting idea, shifted to answer itself.
                events = tuple((o, d, p - (2 if at < 7 else 0), v)
                               for o, d, p, v in events)
        else:
            events = (hook, answer, ascent, release,
                      hook, answer, ascent, release)[at]
            if section == 1:
                # Small rhythmic change in A', never three exact hooks.
                if at in (0, 4):
                    events = ((0, .5, 69, 77), (.5, .5, 74, 84),
                              (1, 1, 77, 87), (2, .5, 79, 81),
                              (2.5, .5, 76, 76), (3, 1, 72, 79))
            elif section == 3 and at in (0, 4):
                events = ((0, .5, 69, 82), (.5, .5, 74, 86),
                          (1, 1.5, 77, 89), (3, .5, 76, 79),
                          (3.5, .5, 72, 78))
        if pass_no and section != 2 and at in (0, 4):
            events = tuple((o, d, p + (2 if section == 1 else 0), v)
                           for o, d, p, v in events)
        notes(lead, bar, events, strength=1.04 if pass_no else 1.0)
        # A gentle octave/section doubling only at phrase peaks.
        if pass_no and at in (2, 6) and section != 2:
            notes(violins, bar, events, shift=-12, strength=.67)
        if pass_no and section == 3 and at in (0, 4):
            notes(horns, bar, events[:3], shift=-12, strength=.62)

    def accompaniment(bar, key, local, pass_no):
        t = s.bar(bar)
        root, chord = harmony[key]
        thick = pass_no == 1
        # Harp gives each harmony a distinctive upward ripple.
        pattern = (0, 2, 3, 4, 3, 2, 1, 2)
        for step, ix in enumerate(pattern):
            harp.note(t + step * .5, .44, chord[ix], 57 + (step % 4) * 3)
        if local % 8 in (3, 7):
            for j, p in enumerate((chord[0], chord[1], chord[2], chord[3])):
                harp.note(t + 3 + j * .25, .24, p + 12, 45 + j * 2)

        # The low line walks into the next root on the second half of a bar.
        bass_pitch = root - 12 if root - 12 >= 28 else root
        basses.note(t, 2, bass_pitch, 65 if thick else 58)
        basses.note(t + 2.5, 1, bass_pitch + 7, 54 if thick else 49)
        cellos.note(t, 1.5, root, 70 if thick else 60)
        cellos.note(t + 2, .75, root + 7, 62 if thick else 54)
        cellos.note(t + 3, 1, root + (2 if key != "A7" else 4), 59)

        strings.chord(t, 3.8, chord[1:4], 54 if thick else 47)
        violas.note(t, 2, chord[0] - 12, 48)
        violas.note(t + 2, 2, chord[1] - 12, 48)
        if thick or (8 <= local < 16):
            for beat, p in enumerate((chord[0], chord[2], chord[1], chord[2],
                                      chord[0], chord[2], chord[1], chord[2])):
                violins.note(t + beat * .5, .38, p, 49 if thick else 41)

        # Percussion marks the terrain without turning exploration into battle.
        perc.note(t, .55, "bass_drum_soft", 54 if thick else 45)
        perc.note(t + 2, .55, "low_tom", 52 if thick else 43)
        if local % 4 in (1, 3):
            perc.note(t + 3.5, .3, "high_tom", 36)
        if thick and local % 8 in (3, 7):
            perc.note(t + 3, .7, "snare_roll", 36)
        if local % 8 == 0 and (thick or local >= 24):
            perc.note(t, 2.2, "suspended_cymbal", 43)
        if local % 8 == 7:
            timpani.note(t + 2, .75, root, 58)
            timpani.note(t + 3, .75, root + 7, 63)

        if local % 4 == 0:
            voices.chord(t, 3.7, chord[0:3], 43 if thick else 37)
            voices.swell(t, 3.7, .28, .56 if thick else .43)
        if local % 4 == 2:
            voices.chord(t, 3.7, chord[1:4], 39 if thick else 34)
            voices.swell(t, 3.7, .43, .25)
        if local % 8 in (2, 6):
            celesta.note(t + 3, .6, chord[4] + 12, 46)
        if thick and local % 8 in (0, 4, 7):
            horns.chord(t + (0 if local % 8 != 7 else 2),
                        2 if local % 8 != 7 else 1.5,
                        (chord[0] - 12, chord[2] - 12), 57)
        if thick and local % 8 == 7:
            trumpets.note(t + 3, .33, 69, 58)
            trumpets.note(t + 3.33, .33, 74, 62)
            trumpets.note(t + 3.66, .32, 77, 64)

    for pass_no in range(2):
        for local, key in enumerate(form):
            bar = 1 + pass_no * 32 + local
            accompaniment(bar, key, local, pass_no)
            melody(bar, local, pass_no)
        start = s.bar(1 + pass_no * 32)
        strings.swell(start, 16, .42, .6 if pass_no else .5)
        strings.swell(start + 64, 16, .43, .67 if pass_no else .55)
        voices.swell(start + 64, 16, .27, .51 if pass_no else .42)

    # Three-bar close: home chord, a brief last question, then a soft D.
    for i, key in enumerate(("Dm", "G", "Dm")):
        bar = 65 + i
        t = s.bar(bar)
        root, chord = harmony[key]
        strings.chord(t, 3.8, chord[:4], 50 - i * 4)
        harp.line(t, ((.5, chord[0], 55), (.5, chord[2], 54),
                      (.5, chord[3], 51), (.5, chord[4], 48)))
        cellos.note(t, 3.7, root, 56 - i * 4)
        basses.note(t, 3.7, root - 12, 52 - i * 4)
    notes(english, 65, hook, strength=.75)
    notes(flute, 66, ((.5, .5, 67, 57), (1, .5, 71, 60),
                      (1.5, 2, 74, 63)))
    notes(flute, 67, ((0, 3.5, 74, 56),))
    voices.chord(s.bar(67), 3.5, (62, 65, 69), 34)
    voices.swell(s.bar(67), 3.5, .38, .12)
    strings.swell(s.bar(67), 3.8, .5, .13)
    s.end(s.bar(68))
