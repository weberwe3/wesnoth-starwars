"""The Admiral's Gallery: a dark, measured orchestral cue in B minor."""


def compose(s):
    s.tempo(72)
    s.meter(3)

    # Pitches are MIDI numbers; the hook's sharpened A belongs to B harmonic minor.
    chords = {
        "Bm": ((47, 54, 59), (59, 62, 66, 71)),
        "F#": ((42, 49, 54), (58, 61, 66, 70)),
        "G": ((43, 50, 55), (55, 59, 62, 67)),
        "Em": ((40, 47, 52), (52, 59, 64, 67)),
        "D": ((38, 45, 50), (54, 57, 62, 66)),
        "C": ((36, 43, 48), (52, 55, 60, 64)),
        "E": ((40, 47, 52), (56, 59, 64, 68)),
        "A": ((45, 52, 57), (57, 61, 64, 69)),
    }

    eh = s.part("english_horn", volume=0.89, pan=-0.11, reverb=0.34)
    oboe = s.part("oboe", volume=0.68, pan=0.12, reverb=0.34)
    horns = s.part("horns", volume=0.80, pan=-0.25, reverb=0.30)
    trumpets = s.part("trumpets", volume=0.76, pan=0.24, reverb=0.28)
    trombones = s.part("trombones", volume=0.74, pan=0.31, reverb=0.29)
    tuba = s.part("tuba", volume=0.69, pan=0.18, reverb=0.29)
    strings = s.part("strings", volume=0.78, pan=-0.12, reverb=0.37)
    violins = s.part("violins", volume=0.59, pan=-0.32, reverb=0.34)
    violas = s.part("violas", volume=0.61, pan=0.09, reverb=0.34)
    cellos = s.part("cellos", volume=0.76, pan=0.23, reverb=0.31)
    basses = s.part("basses", volume=0.72, pan=0.19, reverb=0.28)
    choir = s.part("choir", volume=0.62, pan=0.02, reverb=0.48)
    celesta = s.part("celesta", volume=0.49, pan=0.37, reverb=0.44)
    harp = s.part("harp", volume=0.53, pan=-0.40, reverb=0.40)
    timpani = s.part("timpani", volume=0.63, pan=0.12, reverb=0.29)
    perc = s.part("percussion", volume=0.57, pan=0.04, reverb=0.30)

    def beat(bar, offset=0):
        return s.bar(bar) + offset

    def phrase(part, bar, events, shift=0, vel=75, stretch=1):
        for at, dur, pitch in events:
            if pitch is not None:
                part.note(beat(bar, at * stretch), dur * stretch,
                          pitch + shift, vel)

    # A silver flash, a falling answer, and the half-step that refuses to settle.
    hook = [(0, .5, 71), (.5, .5, 78), (1, 1, 76),
            (2, .5, 73), (3, .5, 74), (3.5, .5, 73),
            (4, 1, 70), (5, 1, 71)]
    hook_turn = [(0, .5, 71), (.5, .5, 78), (1, .5, 76),
                 (1.5, .5, 74), (2, 1, 73), (3, .5, 74),
                 (3.5, .5, 73), (4, .5, 70), (4.5, .5, 73),
                 (5, 1, 71)]
    answer = [(0, 1, 74), (1, .5, 71), (1.5, .5, 67),
              (2, 1, 69), (3, .5, 67), (3.5, .5, 64),
              (4, 1, 66), (5, 1, 69)]
    answer2 = [(0, .5, 74), (.5, .5, 76), (1, 1, 78),
               (2, 1, 74), (3, .5, 73), (3.5, .5, 71),
               (4, 1, 70), (5, 1, 66)]
    bridge = [(0, 1, 76), (1, .5, 73), (1.5, .5, 69),
              (2, 1, 74), (3, .5, 72), (3.5, .5, 76),
              (4, 1, 79), (5, 1, 76)]
    bridge2 = [(0, .5, 80), (.5, .5, 76), (1, 1, 73),
               (2, 1, 71), (3, 1, 73), (4, .5, 70),
               (4.5, .5, 73), (5, 1, 78)]

    # Four eight-bar panels, heard twice. The second viewing is more dangerous.
    panels = [
        ["Bm", "F#", "G", "Em", "Bm", "F#", "G", "F#"],
        ["Bm", "F#", "G", "Em", "Bm", "F#", "Em", "F#"],
        ["D", "A", "C", "G", "E", "C", "Em", "F#"],
        ["Bm", "F#", "G", "Em", "Bm", "F#", "G", "F#"],
    ]
    progression = [ch for _ in range(2) for panel in panels for ch in panel]

    for i, name in enumerate(progression):
        bar = i + 1
        start = beat(bar)
        low, high = chords[name]
        root, fifth, octave = low
        second_pass = i >= 32
        panel = (i // 8) % 4
        local = i % 8
        strong = panel == 3 or (second_pass and panel == 1)

        # A bass gesture on each bar: root, fifth, and a restrained pickup.
        basses.note(start, 2.65, root - 12, 62 if not strong else 78)
        cellos.note(start, 1.65, root, 64 if not strong else 80)
        cellos.note(start + 2, .75, fifth, 57 if not strong else 72)
        if local in (3, 7):
            cellos.note(start + 2.5, .42,
                        chords[progression[(i + 1) % 64]][0][0], 62)

        strings.chord(start, 2.82, high[:3], 48 if panel == 0 else 59)
        if panel in (0, 2):
            choir.chord(start, 2.8, high[:3], 43 if not second_pass else 53)
        if panel == 1 or second_pass or strong:
            violas.note(start, 2.75, high[1] - 12, 52 if not strong else 67)
        if strong:
            # A three-beat motor with space for the lead voice.
            for off, pitch in ((0, high[0]), (.5, high[1]),
                               (1, high[2]), (1.5, high[1]),
                               (2, high[0]), (2.5, high[1])):
                violins.note(start + off, .42, pitch + 12, 54 if not second_pass else 64)
        elif panel == 1 and local % 2 == 0:
            for off, pitch in ((0, high[0]), (1, high[1]), (2, high[2])):
                violins.note(start + off, .72, pitch + 12, 48)

        if local in (0, 4):
            timpani.note(start, 1.1, max(38, root), 53 if not strong else 72)
        if strong and local in (0, 4):
            perc.note(start, .15, "bass_drum", 63 if not second_pass else 77)
        if strong and local in (3, 7):
            perc.note(start + 2, .28, "snare_roll", 52)
        if local == 0 and panel in (2, 3):
            perc.note(start, .5, "suspended_cymbal", 42)
        if local == 0 and panel == 3 and second_pass:
            perc.note(start, .8, "crash", 69)

        # Harmonic dust at phrase ends, never a continuous glitter layer.
        if local in (3, 7):
            for off, pitch in ((1.5, high[0] + 24),
                               (2, high[1] + 24), (2.5, high[2] + 24)):
                celesta.note(start + off, .32, pitch, 45 if not second_pass else 54)
        if local == 7 and panel in (1, 2):
            for n, pitch in enumerate((high[0], high[1], high[2], high[-1])):
                harp.note(start + 1 + n * .38, .8, pitch + 12, 49)

    for cycle in range(2):
        offset = cycle * 32
        for panel in range(4):
            first = 1 + offset + panel * 8
            lead = oboe if (panel == 2 and cycle == 0) else eh
            if panel == 2:
                phrase(lead, first, bridge, vel=74 if cycle == 0 else 84)
                phrase(lead, first + 2, bridge2, vel=77 if cycle == 0 else 85)
                phrase(lead, first + 4, bridge, shift=-2, vel=76)
                phrase(lead, first + 6, bridge2, shift=-2, vel=79)
                # The C and E major colours appear as an unsettled string reply.
                phrase(violins, first + 2, answer, shift=12, vel=52)
            else:
                use_turn = cycle == 1 or panel == 1
                phrase(lead, first, hook_turn if use_turn else hook,
                       vel=76 if cycle == 0 else 84)
                phrase(lead, first + 2, answer, vel=72 if cycle == 0 else 80)
                phrase(lead, first + 4, hook if use_turn else hook_turn,
                       vel=79 if cycle == 0 else 88)
                phrase(lead, first + 6, answer2, vel=75 if cycle == 0 else 84)

            # Brass enters by degrees; the last panel gives the hook its full weight.
            if panel == 1:
                phrase(horns, first, hook, shift=-12, vel=58 if cycle == 0 else 69)
                phrase(horns, first + 4, hook_turn, shift=-12, vel=62 if cycle == 0 else 72)
            elif panel == 2:
                phrase(horns, first + 2, bridge2, shift=-12, vel=61 if cycle == 0 else 72)
            elif panel == 3:
                for b, motif in ((first, hook), (first + 4, hook_turn)):
                    phrase(horns, b, motif, shift=-12, vel=77 if cycle == 0 else 91)
                    phrase(trumpets, b, motif, vel=69 if cycle == 0 else 84)
                for b in (first + 2, first + 6):
                    phrase(trombones, b, answer, shift=-12, vel=65 if cycle == 0 else 78)
                for b in (first, first + 4):
                    tuba.note(beat(b), 2.65, 35, 61 if cycle == 0 else 73)
            elif cycle == 1:
                phrase(horns, first + 2, answer, shift=-12, vel=62)

        # A small second-pass countermelody lives in the gaps of the main theme.
        if cycle == 1:
            counter = [(0, .5, 62), (.5, .5, 66), (1, 1, 69),
                       (2, 1, 66), (3, 1, 67), (4, .5, 64),
                       (4.5, .5, 62), (5, 1, 61)]
            for panel in (0, 1, 3):
                for pos in (2, 6):
                    phrase(violas, 1 + offset + panel * 8 + pos,
                           counter, vel=51 if panel == 0 else 58)

    # Three bars: release to B minor, with the sharpened leading tone left in view.
    end_bar = 65
    for j, name in enumerate(("Em", "F#", "Bm")):
        start = beat(end_bar + j)
        low, high = chords[name]
        strings.chord(start, 2.9, high, 64 if j < 2 else 56)
        choir.chord(start, 2.9, high[:3], 54 if j < 2 else 44)
        basses.note(start, 2.8, low[0] - 12, 72 if j == 1 else 61)
        cellos.note(start, 2.8, low[0], 72 if j == 1 else 60)
        timpani.note(start, .9, max(38, low[0]), 68 if j == 1 else 52)
    phrase(eh, 65, [(0, 1, 67), (1, .5, 66), (1.5, .5, 64),
                    (2, 1, 66), (3, .5, 70), (3.5, .5, 73),
                    (4, 1, 78), (5, 1, 70), (6, 2.7, 71)], vel=78)
    horns.note(beat(67), 2.8, 59, 64)
    celesta.note(beat(67, 1.5), 1.3, 83, 44)
    strings.swell(beat(63), 9, .72, .43)
    choir.swell(beat(65), 9, .62, .34)
    horns.swell(beat(57), 16, .7, .93)
    s.end(beat(68))
