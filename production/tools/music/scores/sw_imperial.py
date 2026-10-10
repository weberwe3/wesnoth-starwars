"""The regime's march: an original, loop-friendly orchestral cue in G minor."""


def compose(s):
    s.tempo(100)
    s.meter(4)

    # MIDI pitches keep all of the transposed figures in their intended ranges.
    brass = s.part("trombones", volume=0.91, pan=-0.13)
    horns = s.part("horns", volume=0.80, pan=-0.25)
    trumpets = s.part("trumpets", volume=0.71, pan=0.15)
    tuba = s.part("tuba", volume=0.83, pan=-0.08)
    strings = s.part("strings", volume=0.68, pan=0.22)
    violins = s.part("violins", volume=0.66, pan=0.31)
    slow_violins = s.part("violins_slow", volume=0.63, pan=0.36)
    violas = s.part("violas", volume=0.62, pan=0.04)
    cellos = s.part("cellos", volume=0.73, pan=-0.27)
    basses = s.part("basses", volume=0.82, pan=-0.32)
    timpani = s.part("timpani", volume=0.82, pan=-0.19)
    drums = s.part("percussion", volume=0.77, pan=0.04)
    choir = s.part("choir", volume=0.45, pan=0.03, reverb=0.48)
    harp = s.part("harp", volume=0.45, pan=0.31)
    glock = s.part("glockenspiel", volume=0.35, pan=0.26)

    # Four two-bar harmonic pillars: G minor, E-flat minor, B minor, D7.
    # The minor-third and major-third shifts give the march its severe colour.
    march = [
        (55, True, 31),   # G3 / G1
        (51, True, 27),   # Eb3 / Eb1
        (59, True, 35),   # B3 / B1
        (50, False, 38),  # D3 / D2, dominant seventh
    ]
    bridge = [
        (51, False, 39),  # Eb major
        (47, False, 35),  # B major
        (48, True, 36),   # C minor
        (50, False, 38),  # D7
    ]

    def chord_tones(root, minor, dominant=False):
        third = 3 if minor else 4
        return [root, root + third, root + 7, root + (10 if dominant else 12)]

    def rhythm_section(bar, harmony, section, pass_no, intensity=0):
        root, minor, bass_pitch = harmony
        t = s.bar(bar)
        third = 3 if minor else 4
        fifth = root + 7
        strong = 81 + 8 * pass_no + intensity
        low_root = bass_pitch if bass_pitch >= 28 else bass_pitch + 12

        # A two-beat cell repeats, while its last eighth changes on alternate bars.
        figure = [root - 12, fifth - 12, root - 12, root + third - 12,
                  root - 12, fifth - 12, root + third - 12,
                  (root + 2 if bar % 2 else fifth) - 12]
        for i, pitch in enumerate(figure):
            vel = strong - 11 + (8 if i in (0, 4) else 0)
            cellos.note(t + i * 0.5, 0.40, pitch, vel)
            if section != "B" or pass_no:
                violas.note(t + i * 0.5, 0.38, pitch + 12, vel - 15)
            if pass_no and section != "B":
                violins.note(t + i * 0.5, 0.33, pitch + 24, vel - 24)

        basses.note(t, 1.45, low_root, strong)
        basses.note(t + 2, 1.20, low_root + 7, strong - 6)
        basses.note(t + 3.5, 0.42, low_root + (2 if bar % 2 else 7), strong - 9)
        tuba.note(t, 1.7, max(26, bass_pitch), strong + 2)
        tuba.note(t + 2, 1.25, max(26, bass_pitch + 7), strong - 4)

        timp_root = root - 12 if root - 12 >= 38 else root
        timpani.note(t, 0.8, timp_root, strong + 5)
        timpani.note(t + 2, 0.65, timp_root + 7, strong - 2)
        if bar % 2 == 0:
            timpani.note(t + 3.5, 0.4, timp_root, strong - 15)
        drums.note(t, 0.20, "bass_drum", strong + 5)
        drums.note(t + 2, 0.18, "bass_drum_soft", strong - 8)
        for beat in (1, 3):
            drums.note(t + beat, 0.16, "snare", strong - 1)
        drums.note(t + 3.75, 0.11, "snare_rim", strong - 22)
        if (bar - 1) % 8 == 0:
            drums.note(t, 1.5, "crash", 87 + 9 * pass_no)
        elif (bar - 1) % 4 == 0:
            drums.note(t, 1.1, "suspended_cymbal", 66 + 8 * pass_no)

    # Original hook: a rising fourth and minor third, then a fall and
    # a displaced, held upper neighbour. The answering bar descends.
    def hook(bar, harmony, variant, pass_no, section):
        root, minor, _ = harmony
        if root == 59:  # keep the B-minor statement in the trombone's register
            root -= 12
        third = 3 if minor else 4
        t = s.bar(bar)
        if variant == 0:
            notes = [(0, .48, -5), (.75, .24, 0), (1, 1.42, third),
                     (2.75, .42, -2), (3.25, .70, 2)]
        elif variant == 1:
            notes = [(0, .43, -5), (.5, .43, 0), (1.25, 1.18, third),
                     (2.5, .40, 7), (3.0, .86, 2)]
        else:
            notes = [(0, .65, -5), (1, .26, 0), (1.33, .26, 2),
                     (1.67, 1.06, third), (3, .72, 7)]
        for offset, dur, interval in notes:
            pitch = root + interval
            brass.note(t + offset, dur, pitch, 98 + 8 * pass_no)
            horns.note(t + offset, dur + .08, pitch + 12, 86 + 7 * pass_no)
            if pass_no and section != "A":
                trumpets.note(t + offset, dur, pitch + 12, 83)

    def answer(bar, harmony, variant, pass_no, section):
        root, minor, _ = harmony
        if root == 59:
            root -= 12
        third = 3 if minor else 4
        t = s.bar(bar)
        patterns = [
            [(0, .45, 5), (.5, .45, third), (1, .72, 0),
             (2, .44, -2), (2.5, 1.35, -5)],
            [(0, .34, 7), (.34, .34, 5), (.68, .34, third),
             (1.25, .65, 0), (2.25, 1.55, -5)],
            [(0, .67, 5), (1, .37, 7), (1.5, .40, third),
             (2.25, .40, 0), (2.75, 1.15, -5)],
        ]
        for offset, dur, interval in patterns[variant]:
            pitch = root + interval
            brass.note(t + offset, dur, pitch, 94 + 8 * pass_no)
            horns.note(t + offset, dur + .09, pitch + 12, 83 + 7 * pass_no)
            if pass_no and section == "A2":
                trumpets.note(t + offset, dur, pitch + 12, 82)

    def harmony_bar(bar, harmony, section, pass_no, phrase_start=False):
        root, minor, _ = harmony
        t = s.bar(bar)
        tones = chord_tones(root, minor, section != "B" and root == 50)
        strings.chord(t, 3.75, [tones[1] + 12, tones[2] + 12,
                               tones[3] + 12], 59 + 8 * pass_no)
        horns.chord(t + .03, 3.45, [tones[0], tones[1], tones[2]],
                    53 + 7 * pass_no)
        if section == "B":
            choir.chord(t, 3.8, [tones[0] + 12, tones[1] + 12,
                                tones[2] + 12], 51 + 5 * pass_no)
        elif pass_no and phrase_start:
            choir.chord(t, 3.4, [tones[0] + 12, tones[2] + 12], 44)

    def bridge_melody(bar, harmony, second_bar, pass_no):
        root, minor, _ = harmony
        third = 3 if minor else 4
        t = s.bar(bar)
        # A broad, upward answer leaves the ostinato and snare exposed.
        pattern = ([(0, 1.35, 7), (1.5, .46, 12), (2.25, 1.64, 10)]
                   if not second_bar else
                   [(0, .78, 12), (1, .70, 7), (2, 1.85, third)])
        for offset, dur, interval in pattern:
            pitch = root + interval + 12
            slow_violins.note(t + offset, dur, pitch, 82 + 7 * pass_no)
            horns.note(t + offset, dur, pitch - 12, 77 + 7 * pass_no)
            if pass_no:
                trumpets.note(t + offset, dur, pitch, 72)
        if not second_bar:
            harp.note(t + 2.75, .24, root + 12, 56)
            harp.note(t + 3, .24, root + third + 12, 56)
            harp.note(t + 3.25, .24, root + 7 + 12, 58)
            harp.note(t + 3.5, .30, root + 12 + 12, 60)

    def counterline(bar, harmony, pass_no):
        root, minor, _ = harmony
        third = 3 if minor else 4
        t = s.bar(bar)
        # Starts after the hook has spoken; used on the second traversal.
        for offset, dur, interval in [(1.75, .4, 7), (2.25, .4, 5),
                                      (2.75, .4, third), (3.25, .65, 0)]:
            slow_violins.note(t + offset, dur, root + interval + 24, 62 + 3 * pass_no)

    for pass_no in range(2):
        base = 1 + 32 * pass_no
        for local in range(32):
            bar = base + local
            block = local // 8
            phrase_pos = local % 8
            pair = phrase_pos // 2
            section = "B" if block == 2 else ("A2" if block == 3 else "A")
            harmony = (bridge if section == "B" else march)[pair]
            rhythm_section(bar, harmony, section, pass_no,
                           3 if block == 3 else 0)
            harmony_bar(bar, harmony, section, pass_no,
                        phrase_pos in (0, 4))

            if section == "B":
                bridge_melody(bar, harmony, phrase_pos % 2 == 1, pass_no)
            else:
                variant = (block + pair + pass_no) % 3
                if phrase_pos % 2 == 0:
                    hook(bar, harmony, variant, pass_no, section)
                else:
                    answer(bar, harmony, variant, pass_no, section)
                if pass_no and phrase_pos % 2 == 0 and pair in (1, 3):
                    counterline(bar, harmony, pass_no)

            if phrase_pos == 7:
                drums.note(s.bar(bar) + 3.25, .55, "snare_roll", 71 + 8 * pass_no)
            if pass_no and phrase_pos in (0, 4) and section != "B":
                glock.note(s.bar(bar), .55, harmony[0] + 24, 50)

        # A shaped second traversal, with one restrained release in the bridge.
        horns.swell(s.bar(base), 16, .75, .95)
        horns.swell(s.bar(base + 16), 8, .95, .67)
        horns.swell(s.bar(base + 24), 8, .67, 1.0)
        strings.swell(s.bar(base), 16, .67, .88)
        strings.swell(s.bar(base + 16), 8, .88, .62)
        strings.swell(s.bar(base + 24), 8, .62, .98)

    # Four-bar cadence: the last G minor chord can feed directly into bar 1.
    for i, harmony in enumerate([march[0], march[1], march[3], march[0]]):
        bar = 65 + i
        rhythm_section(bar, harmony, "A2", 1, -2 if i == 3 else 4)
        harmony_bar(bar, harmony, "A2", 1, i in (0, 3))
    hook(65, march[0], 2, 1, "A2")
    answer(66, march[1], 1, 1, "A2")
    t = s.bar(67)
    for offset, dur, pitch in [(0, .43, 57), (.5, .43, 62),
                               (1, .43, 66), (1.5, .43, 69),
                               (2.25, 1.45, 62)]:
        brass.note(t + offset, dur, pitch, 104)
        trumpets.note(t + offset, dur, pitch + 12, 91)
    t = s.bar(68)
    brass.chord(t, 3.55, [55, 58, 62], 107)
    trumpets.chord(t, 2.85, [67, 70, 74], 94)
    horns.chord(t, 3.7, [55, 62, 67], 92)
    choir.chord(t, 3.75, [67, 70, 74], 62)
    timpani.note(t, 1.7, 43, 108)
    drums.note(t, 2, "crash2", 107)
    drums.note(t, .23, "bass_drum", 107)
    harp.note(t + 2.75, .2, 62, 53)
    harp.note(t + 3.0, .2, 67, 53)
    harp.note(t + 3.25, .3, 70, 52)
    strings.swell(s.bar(65), 4, .91, .68)
    choir.swell(s.bar(65), 4, .65, .88)
    s.end(s.bar(69))
