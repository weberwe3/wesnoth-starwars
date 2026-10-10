"""A quiet, looping infiltration cue for sampled orchestra."""


def compose(s):
    s.tempo(76)
    s.meter(3)

    trem = s.part("tremolo", volume=0.47, pan=-0.28, reverb=0.62)
    pizz = s.part("pizzicato", volume=0.43, pan=-0.36, reverb=0.45)
    basses = s.part("basses", volume=0.45, pan=-0.24, reverb=0.48)
    cellos = s.part("cellos", volume=0.47, pan=-0.15, reverb=0.52)
    violas = s.part("violas", volume=0.35, pan=-0.06, reverb=0.58)
    strings = s.part("strings", volume=0.32, pan=-0.25, reverb=0.63)
    celesta = s.part("celesta", volume=0.48, pan=0.28, reverb=0.67)
    harp = s.part("harp", volume=0.43, pan=0.35, reverb=0.64)
    clarinet = s.part("clarinet", volume=0.50, pan=0.12, reverb=0.57)
    bassoon = s.part("bassoon", volume=0.46, pan=0.22, reverb=0.55)
    trumpet = s.part("muted_trumpet", volume=0.31, pan=0.4, reverb=0.72)
    horns = s.part("horns", volume=0.30, pan=0.15, reverb=0.68)
    choir = s.part("voices", volume=0.23, pan=0.0, reverb=0.75)
    timpani = s.part("timpani", volume=0.28, pan=-0.13, reverb=0.58)
    perc = s.part("percussion", volume=0.25, pan=0.04, reverb=0.65)

    # Bass, dark sustained tones, glinting upper tones, and a five-note hook.
    # The hook's eighth-eighth, late quarter, clipped eighth, eighth shape
    # remains recognizable while its intervals follow each harmony.
    chords = {
        "Am": (33, (57, 60, 64), (69, 72, 76, 71, 72)),
        "F":  (29, (53, 57, 60), (65, 69, 72, 67, 69)),
        "Dm": (38, (53, 57, 62), (62, 65, 69, 64, 65)),
        "E":  (40, (52, 56, 62), (64, 68, 71, 66, 68)),
        "C":  (36, (55, 60, 64), (67, 72, 76, 71, 72)),
        "Ab": (32, (56, 60, 63), (68, 72, 75, 70, 72)),
    }
    # Four eight-bar phrases: A, A', a more remote B, and A''.
    progression = (
        ("Am", "F", "Dm", "E", "Am", "F", "Dm", "E")
        + ("Am", "F", "Dm", "E", "Am", "F", "Dm", "E")
        + ("C", "Ab", "Dm", "E", "C", "Ab", "Dm", "E")
        + ("Am", "F", "Dm", "E", "Am", "F", "Dm", "E")
    )

    def hook(bar, name, variation, player=celesta, strength=57):
        t = s.bar(bar)
        notes = chords[name][2]
        if variation == 0:
            pattern = ((0, .5, 0), (.5, .5, 1), (1.25, .75, 2),
                       (2.25, .25, 3), (2.5, .5, 4))
        elif variation == 1:
            pattern = ((0, .75, 0), (1, .25, 1), (1.25, .75, 2),
                       (2.25, .25, 3), (2.5, .5, 4))
        else:
            pattern = ((.25, .5, 0), (.75, .5, 1), (1.5, .5, 2),
                       (2.25, .25, 3), (2.5, .5, 4))
        for off, dur, index in pattern:
            player.note(t + off, dur, notes[index], strength - (4 if index == 3 else 0))
        # The harp catches only the rising outline, leaving the top line clear.
        harp.note(t + .5, .55, notes[1] - 12, 43)
        harp.note(t + 1.25, .9, notes[2] - 12, 47)

    def answer(bar, name, phrase, second):
        t = s.bar(bar)
        tones = chords[name][1]
        if phrase == 2:
            # A contrasting, descending B melody in the woodwind register.
            clarinet.note(t + .5, .5, tones[2] + 12, 51 + second * 3)
            clarinet.note(t + 1, .5, tones[1] + 12, 49 + second * 3)
            clarinet.note(t + 1.75, 1.15, tones[0] + 12, 53 + second * 3)
        elif bar % 4 == 2:
            clarinet.note(t + .75, .75, tones[2] + 7, 54 + second * 3)
            clarinet.note(t + 1.75, 1.05, tones[1] + 7, 49 + second * 3)
        else:
            bassoon.note(t + .5, 1, tones[1] - 5, 48 + second * 3)
            bassoon.note(t + 1.75, 1.1, tones[0] - 5, 51 + second * 3)

    for pass_no in range(2):
        for i, name in enumerate(progression):
            bar = 1 + 32 * pass_no + i
            t = s.bar(bar)
            bass, tones, motif = chords[name]
            phrase = i // 8
            position = i % 8

            # A soft two-step pedal is the cue's clock. D2/E2 are kept on
            # cellos where the bass section would sit below its range.
            if bass <= 33:
                basses.note(t, 2.7, bass, 49 + pass_no * 3)
            else:
                cellos.note(t, 2.7, bass, 47 + pass_no * 3)
            cellos.note(t + 1.5, 1.3, bass + 12, 43 + pass_no * 3)
            pizz.note(t, .38, bass + 24, 46 + pass_no * 3)
            pizz.note(t + 1.5, .32, tones[1], 40 + pass_no * 3)

            trem.chord(t, 2.8, tones[:2], 43 + pass_no * 4)
            violas.note(t + .2, 2.4, tones[2], 38 + pass_no * 4)
            if phrase in (1, 2) or pass_no:
                strings.note(t + .25, 2.25, tones[1] + 12, 37 + pass_no * 3)

            if position % 2 == 0:
                variation = (phrase + pass_no + position // 4) % 3
                hook(bar, name, variation, strength=55 + pass_no * 4)
                if pass_no and position in (0, 4) and phrase != 2:
                    # A single veiled octave doubles the phrase opening.
                    clarinet.note(t + 1.25, .75, motif[2] - 12, 45)
            else:
                answer(bar, name, phrase, pass_no)

            if phrase == 2:
                choir.note(t + .35, 2.3, tones[0] + 12, 37 + pass_no * 3)
                if position in (0, 4):
                    harp.chord(t + 2.35, .55, (tones[0] + 12, tones[2] + 12), 41)
            if (phrase == 1 or pass_no) and position in (3, 7):
                trumpet.note(t + 1.7, 1.05, motif[1] - 12, 43 + pass_no * 3)
            if pass_no and phrase in (1, 3) and position in (1, 5):
                horns.note(t + .5, 1.8, tones[1], 42)

            if position == 7:
                timpani.note(t, .7, 40, 43 + pass_no * 3)
                perc.note(t + 2.5, .25, "suspended_cymbal", 35)
            elif pass_no and position in (2, 6):
                perc.note(t + 1.5, .25, "snare_rim", 32)

        # Each 32-bar turn grows gently, then withdraws for the repeat.
        start = s.bar(1 + 32 * pass_no)
        trem.swell(start, 24, .56, .71)
        trem.swell(start + 24, 24, .71, .53)
        trem.swell(start + 48, 24, .53, .69)
        trem.swell(start + 72, 24, .69, .48)

    # Three-bar release: A minor arrives softly, with E left in the bass
    # before the last celesta A so the opening can follow naturally.
    for bar, name in ((65, "Am"), (66, "F"), (67, "Am")):
        t = s.bar(bar)
        bass, tones, motif = chords[name]
        trem.chord(t, 2.8, tones[:2], 39)
        pizz.note(t, .4, bass + 24, 40)
        harp.note(t + 1, 1.35, tones[2] + 12, 43)
    cellos.note(s.bar(66) + 1.5, 1.25, 40, 42)
    clarinet.note(s.bar(65) + .5, 1.5, 72, 46)
    bassoon.note(s.bar(66) + .75, 1.6, 52, 42)
    celesta.note(s.bar(67) + 1.5, 1.2, 69, 48)
    trem.swell(s.bar(65), 9, .48, .18)
    s.end(s.bar(68))
