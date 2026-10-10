"""Score API and orchestral renderer for the add-on's music.

A track is a Python module (production/tools/music/scores/<track>.py) with a
`compose(s: Score)` function that writes notes into named orchestral parts.
The renderer plays each part through the MuseScore General SoundFont (MIT
licensed; FluidR3 lineage; see docs/ART_CREDITS.md) with tinysoundfont, so
every instrument is a recorded orchestral sample, then mixes the parts in
stereo through a concert-hall convolution reverb and masters the result.

Composition API (all times in beats; bar numbers start at 1):

    s.tempo(bpm); s.meter(beats_per_bar)
    s.bar(b) -> beat at the start of bar b
    p = s.part(instrument, volume=0.8, pan=None, reverb=None)
    p.note(start, dur, pitch, vel=90)        pitch: "C4", "F#3", "Bb5" or MIDI int
    p.chord(start, dur, [pitches], vel=90)
    p.line(start, [(dur, pitch_or_chord_or_None, vel?), ...]) -> end beat
    p.swell(start, dur, from_level, to_level)   crescendo/diminuendo (0..1)
    s.end(beat)                               total length (notes may ring past)

Percussion part: s.part("percussion") and pitches from PERCUSSION
("bass_drum", "snare", "crash", ...).
"""
from __future__ import annotations

import importlib.util
import re
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

RATE = 44100
SOUNDFONT = Path.home() / "opt/soundfonts/MuseScore_General.sf2"

# name -> (bank, preset, default pan, default reverb send)
INSTRUMENTS = {
    "violins": (0, 48, -0.45, 0.35), "violins_slow": (0, 49, -0.45, 0.45), "violas": (0, 49, -0.15, 0.4),
    "strings": (0, 49, 0.0, 0.45), "tremolo": (0, 44, -0.2, 0.4), "pizzicato": (0, 45, -0.25, 0.3),
    "violin_solo": (0, 40, -0.3, 0.4), "cellos": (0, 42, 0.35, 0.35), "basses": (0, 43, 0.45, 0.3),
    "horns": (0, 60, -0.25, 0.5), "trumpets": (0, 56, 0.25, 0.4), "trombones": (0, 57, 0.35, 0.4),
    "tuba": (0, 58, 0.4, 0.35), "brass": (0, 61, 0.15, 0.4), "muted_trumpet": (0, 59, 0.2, 0.4),
    "flute": (0, 73, -0.1, 0.4), "piccolo": (0, 72, -0.1, 0.4), "oboe": (0, 68, 0.05, 0.4),
    "english_horn": (0, 69, 0.05, 0.4), "clarinet": (0, 71, 0.15, 0.4), "bassoon": (0, 70, 0.2, 0.35),
    "harp": (0, 46, -0.5, 0.45), "celesta": (0, 8, 0.4, 0.5), "glockenspiel": (0, 9, 0.35, 0.5),
    "chimes": (0, 14, 0.3, 0.55), "timpani": (0, 47, 0.0, 0.4), "choir": (0, 52, 0.0, 0.55),
    "voices": (0, 53, 0.0, 0.55), "space_pad": (0, 94, 0.0, 0.6), "space_voice": (0, 91, 0.0, 0.6),
    "taiko": (0, 116, 0.0, 0.35), "orchestra_hit": (0, 55, 0.0, 0.35),
    "percussion": (128, 48, 0.0, 0.35),
}
# Level trims (dB) so a part at the same volume and velocity sounds about
# equally loud whatever the sample's recorded level (measured: one forte note).
TRIM_DB = {'violins': 6.1, 'violins_slow': 6.8, 'violas': 6.6, 'strings': 6.5, 'tremolo': 9.7, 'pizzicato': 7.1, 'violin_solo': 1.6, 'cellos': -3.1, 'basses': 3.6, 'horns': -4.2, 'trumpets': -2.9, 'trombones': -10, 'tuba': -7.7, 'brass': -3.7, 'muted_trumpet': 1.2, 'flute': 2.0, 'piccolo': 2.5, 'oboe': -0.6, 'english_horn': 4.0, 'clarinet': 3.0, 'bassoon': -0.6, 'harp': 3.2, 'celesta': 10, 'glockenspiel': 8.8, 'chimes': 1.7, 'timpani': -1.9, 'choir': 6.0, 'voices': -0.8, 'space_pad': 0.6, 'space_voice': -0.9, 'taiko': 3.1, 'orchestra_hit': 5.4, 'percussion': -0.7}
PERCUSSION = {"bass_drum": 36, "bass_drum_soft": 35, "snare": 38, "snare_rim": 37, "snare_roll": 40,
              "crash": 49, "crash2": 57, "suspended_cymbal": 51, "tam_tam": 52, "triangle": 81,
              "tambourine": 54, "low_tom": 45, "mid_tom": 47, "high_tom": 50, "woodblock": 76}
NOTE = re.compile(r"^([A-Ga-g])([#b]?)(-?\d)$")
STEPS = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}


def midi(p) -> int:
    if isinstance(p, (int, np.integer)):
        return int(p)
    if p in PERCUSSION:
        return PERCUSSION[p]
    m = NOTE.match(str(p))
    if not m:
        raise ValueError(f"bad pitch {p!r}")
    letter, acc, octave = m.groups()
    return 12 * (int(octave) + 1) + STEPS[letter.upper()] + (1 if acc == "#" else -1 if acc == "b" else 0)


@dataclass
class Part:
    instrument: str
    volume: float
    pan: float
    reverb: float
    notes: list = field(default_factory=list)      # (start, dur, key, vel)
    levels: list = field(default_factory=list)     # (beat, level 0..1) for expression

    def note(self, start, dur, pitch, vel=90):
        if pitch is None:
            return
        self.notes.append((float(start), float(dur), midi(pitch), int(max(1, min(127, vel)))))

    def chord(self, start, dur, pitches, vel=90):
        for p in pitches:
            self.note(start, dur, p, vel)

    def line(self, start, items):
        t = float(start)
        for item in items:
            dur, pitch = item[0], item[1]
            vel = item[2] if len(item) > 2 else 90
            if isinstance(pitch, (list, tuple)):
                self.chord(t, dur, pitch, vel)
            else:
                self.note(t, dur, pitch, vel)
            t += dur
        return t

    def swell(self, start, dur, a, b):
        steps = max(2, int(dur * 8))
        for i in range(steps + 1):
            self.levels.append((start + dur * i / steps, a + (b - a) * i / steps))


class Score:
    def __init__(self):
        self.bpm, self.beats_per_bar, self.length, self.parts = 100.0, 4, None, []

    def tempo(self, bpm):
        self.bpm = float(bpm)

    def meter(self, beats):
        self.beats_per_bar = beats

    def bar(self, b):
        return (b - 1) * self.beats_per_bar

    def end(self, beat):
        self.length = float(beat)

    def part(self, instrument, volume=0.8, pan=None, reverb=None):
        if instrument not in INSTRUMENTS:
            raise ValueError(f"unknown instrument {instrument!r}; choose from {sorted(INSTRUMENTS)}")
        _, _, dpan, drev = INSTRUMENTS[instrument]
        p = Part(instrument, float(volume), dpan if pan is None else float(pan), drev if reverb is None else float(reverb))
        self.parts.append(p)
        return p

    def seconds(self, beat):
        return beat * 60.0 / self.bpm


def load(path: Path) -> Score:
    spec = importlib.util.spec_from_file_location(path.stem, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    s = Score()
    mod.compose(s)
    if s.length is None:
        s.length = max((n[0] + n[1] for p in s.parts for n in p.notes), default=0)
    return s


def check(s: Score) -> list[str]:
    """Problems a composer should fix: empty parts, notes out of range."""
    out = []
    if not s.parts:
        out.append("no parts")
    for p in s.parts:
        if not p.notes:
            out.append(f"part {p.instrument} has no notes")
        bad = [n for n in p.notes if p.instrument != "percussion" and not 21 <= n[2] <= 108]
        if bad:
            out.append(f"part {p.instrument} has {len(bad)} notes outside the piano range")
    secs = s.seconds(s.length or 0)
    if not 8 <= secs <= 260:
        out.append(f"length {secs:.0f}s is outside 8-260 s")
    return out


def render_part(s: Score, p: Part, total: int):
    import tinysoundfont

    synth = tinysoundfont.Synth(gain=-6, samplerate=RATE)
    sfid = synth.sfload(str(SOUNDFONT))
    bank, preset, _, _ = INSTRUMENTS[p.instrument]
    synth.program_select(0, sfid, bank, preset, is_drums=(bank == 128))
    synth.control_change(0, 7, int(127 * min(1.0, p.volume)))
    synth.control_change(0, 11, 127)
    events = []
    for start, dur, key, vel in p.notes:
        t0 = int(s.seconds(start) * RATE)
        t1 = int(s.seconds(start + max(dur * 0.98, 0.05)) * RATE)
        events.append((t0, 1, key, vel))
        events.append((t1, 0, key, 0))
    for beat, level in p.levels:
        events.append((int(s.seconds(beat) * RATE), 2, int(127 * max(0, min(1, level))), 0))
    events.sort(key=lambda e: (e[0], e[1]))
    out = np.zeros((total, 2), dtype=np.float32)
    pos = 0
    for t, kind, a, b in events + [(total, -1, 0, 0)]:
        t = min(t, total)
        if t > pos:
            out[pos:t] = np.frombuffer(synth.generate(t - pos), dtype=np.float32).reshape(-1, 2)
            pos = t
        if kind == 1:
            synth.noteon(0, a, b)
        elif kind == 0:
            synth.noteoff(0, a)
        elif kind == 2:
            synth.control_change(0, 11, a)
    # Re-pan the (mostly centred) sample output to the part's seat.
    mono = out.mean(axis=1)
    side = (out[:, 0] - out[:, 1]) * 0.5
    angle = (p.pan + 1) * np.pi / 4
    g = 10 ** (TRIM_DB.get(p.instrument, 0) / 20)
    return g * np.stack([mono * np.cos(angle) * 1.414 + side, mono * np.sin(angle) * 1.414 - side])


def hall_ir(seconds=2.8, seed=7):
    from scipy import signal
    rng = np.random.default_rng(seed)
    n = int(seconds * RATE)
    t = np.arange(n) / RATE
    ir = np.zeros((2, n))
    sos = signal.butter(2, 6000, fs=RATE, output="sos")
    for ch in range(2):
        tail = rng.uniform(-1, 1, n) * np.exp(-t / (seconds / 6.9)) * np.clip(t / 0.03, 0, 1)
        ir[ch] = signal.sosfilt(sos, tail)
        for d, g in ((0.017, 0.5), (0.023, 0.35), (0.031, 0.3), (0.043, 0.22), (0.057, 0.15)):
            ir[ch, int((d + 0.003 * ch) * RATE)] += g
        ir[ch] /= np.sqrt((ir[ch] ** 2).sum())
    return ir


def render(s: Score, tail_seconds=3.5, target_rms=0.11) -> np.ndarray:
    from scipy import signal
    total = int((s.seconds(s.length) + tail_seconds) * RATE)
    dry = np.zeros((2, total))
    send = np.zeros((2, total))
    for p in s.parts:
        stem = render_part(s, p, total)
        dry += stem
        send += stem * p.reverb
    ir = hall_ir()
    wet = np.stack([signal.fftconvolve(send[c], ir[c])[:total] for c in range(2)])
    mix = dry + 0.9 * wet
    mix = signal.sosfilt(signal.butter(2, 30, "highpass", fs=RATE, output="sos"), mix)
    rms = np.sqrt((mix ** 2).mean()) or 1.0
    mix *= target_rms / rms
    mix = np.tanh(1.2 * mix) / np.tanh(1.2)
    peak = np.abs(mix).max() or 1.0
    if peak > 0.88:  # headroom: the Vorbis encoder overshoots by a few percent
        mix *= 0.88 / peak
    fade = int(min(tail_seconds, 3.0) * RATE)
    mix[:, -fade:] *= np.linspace(1, 0, fade) ** 2
    mix[:, :int(0.01 * RATE)] *= np.linspace(0, 1, int(0.01 * RATE))
    return mix


def write_ogg(path: Path, audio: np.ndarray) -> None:
    import soundfile as sf
    with sf.SoundFile(path, "w", RATE, 2, format="OGG", subtype="VORBIS") as f:
        data = audio.T.astype(np.float32)
        for i in range(0, len(data), 8192):
            f.write(data[i:i + 8192])
