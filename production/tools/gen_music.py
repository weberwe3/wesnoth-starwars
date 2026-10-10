#!/usr/bin/env python3
"""Compose and render the add-on's original music from code.

Project rule: no copyrighted score. Every note here comes from scales, chord
progressions, rhythm templates and rule-built motifs written in this file,
with fixed seeds; melodies are generated from chord tones by rule, not
modelled on any film or game theme. The two stingers are short hand-written
phrases, equally original.

Each looping track is arranged in sections (intro, theme, development,
breakdown, climax, outro) so it builds and releases instead of repeating one
loop. A track's theme is a two-bar motif generated once and restated over the
changing harmony, so it is recognisable when it returns. Instruments are
synthesized: band-limited saw string sections, additive brass with a
brightening attack, a vowel-like choir, Karplus-Strong harp, inharmonic bells,
a breathy flute, and tuned and noise percussion. Everything is mixed in
stereo through a convolution reverb and loudness-matched.

  sw-imperial.ogg  cold phrygian march: string ostinato, low brass, timpani
  sw-heroic.ogg    major-key fanfare over driving strings (New Republic battles)
  sw-space.ogg     fast arpeggios and drums (space battles)
  sw-tension.ogg   heartbeat pulse, bells and drones (infiltration, stealth)
  sw-jungle.ogg    hand drums, flute and harp in dorian (forest worlds)
  sw-battle.ogg    driving minor ground battle: brass stabs, toms
  sw-thrawn.ogg    the Grand Admiral: slow harmonic-minor choir and bells
  sw-victory.ogg   short fanfare for the victory screen
  sw-defeat.ogg    short lament for the defeat screen

Usage: python production/tools/gen_music.py [--track NAME] [--out DIR]
Requires numpy, scipy and soundfile (the art toolchain Python).
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy import signal

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "addons/Star_Wars_Thrawn_Trilogy/music"
RATE = 32000

SCALES = {
    "minor": [0, 2, 3, 5, 7, 8, 10],
    "major": [0, 2, 4, 5, 7, 9, 11],
    "phrygian": [0, 1, 3, 5, 7, 8, 10],
    "dorian": [0, 2, 3, 5, 7, 9, 10],
    "harmonic": [0, 2, 3, 5, 7, 8, 11],
}


def hz(midi: float) -> float:
    return 440.0 * 2 ** ((midi - 69) / 12)


# --- filters -------------------------------------------------------------------

def _sos(kind: str, cutoff, order: int = 2):
    return signal.butter(order, cutoff, btype=kind, fs=RATE, output="sos")


def lowpass(x: np.ndarray, cutoff: float, order: int = 2) -> np.ndarray:
    return signal.sosfilt(_sos("lowpass", min(cutoff, RATE * 0.45), order), x, axis=-1)


def highpass(x: np.ndarray, cutoff: float, order: int = 2) -> np.ndarray:
    return signal.sosfilt(_sos("highpass", cutoff, order), x, axis=-1)


def bandpass(x: np.ndarray, lo: float, hi: float) -> np.ndarray:
    return signal.sosfilt(_sos("bandpass", [lo, min(hi, RATE * 0.45)]), x, axis=-1)


# --- oscillators and envelopes -------------------------------------------------

def env(n: int, a: float, d: float, s: float, r: float) -> np.ndarray:
    """ADSR envelope over n samples; the release ends the note."""
    out = np.full(n, float(s))
    a_n = min(n, max(1, int(a * RATE)))
    out[:a_n] = np.linspace(0, 1, a_n)
    d_n = min(n - a_n, max(1, int(d * RATE)))
    if d_n > 0:
        out[a_n:a_n + d_n] = np.linspace(1, s, d_n)
    r_n = min(n, max(1, int(r * RATE)))
    out[-r_n:] *= np.linspace(1, 0, r_n)
    return out


def saw(freq, n: int, phase: float = 0.0) -> np.ndarray:
    """Band-limited (polyBLEP) sawtooth; freq may be a per-sample array."""
    dt = np.broadcast_to(np.asarray(freq, dtype=float) / RATE, (n,))
    t = (np.cumsum(dt) + phase) % 1.0
    out = 2 * t - 1
    lo = t < dt
    x = t[lo] / dt[lo]
    out[lo] -= x + x - x * x - 1
    hi = t > 1 - dt
    x = (t[hi] - 1) / dt[hi]
    out[hi] -= x * x + x + x + 1
    return out


def sine(freq, n: int, phase: float = 0.0) -> np.ndarray:
    dt = np.broadcast_to(np.asarray(freq, dtype=float) / RATE, (n,))
    return np.sin(2 * np.pi * (np.cumsum(dt) + phase))


def vibrato(f: float, n: int, depth: float = 0.004, rate: float = 5.2, delay: float = 0.25) -> np.ndarray:
    t = np.arange(n) / RATE
    ramp = np.clip((t - delay) / 0.4, 0, 1)
    return f * (1 + depth * ramp * np.sin(2 * np.pi * rate * t))


# --- instruments (mono note renderers) -----------------------------------------

def strings(f: float, n: int, rng, attack: float = 0.35, release: float = 0.5, voices: int = 6) -> np.ndarray:
    spread = np.linspace(-0.006, 0.006, voices)
    out = sum(saw(vibrato(f * (1 + s), n, 0.003, 4.8 + rng.random(), 0.1), n, rng.random()) for s in spread)
    return out / voices * env(n, attack, 0.2, 0.85, release)


def staccato(f: float, n: int, rng) -> np.ndarray:
    out = sum(saw(f * (1 + s), n, rng.random()) for s in (-0.004, 0.0, 0.004)) / 3
    return out * env(n, 0.008, 0.09, 0.35, 0.04)


def brass(f: float, n: int, rng, attack: float = 0.06, bright: float = 1.0) -> np.ndarray:
    freq = vibrato(f, n, 0.0035, 5.5, 0.3)
    t = np.arange(n) / RATE
    swell = np.clip(t / max(attack * 2.5, 1e-3), 0, 1) * bright
    amp = env(n, attack, 0.15, 0.75, min(0.12, n / RATE / 3))
    out = np.zeros(n)
    phase = np.cumsum(freq / RATE)
    for k in range(1, 17):
        if f * k > RATE * 0.42:
            break
        weight = (1 / k) * np.minimum(swell, 1.0) ** ((k - 1) * 0.45) * (bright if k > 4 else 1.0)
        out += weight * np.sin(2 * np.pi * k * phase)
    return out * amp * 0.6


def choir(f: float, n: int, rng, attack: float = 0.6) -> np.ndarray:
    out = np.zeros(n)
    for _ in range(4):
        freq = vibrato(f * (1 + rng.uniform(-0.004, 0.004)), n, 0.006, 4.6 + rng.random(), 0.2)
        ph = rng.random()
        out += sine(freq, n, ph) + 0.35 * sine(freq * 2, n, ph) + 0.18 * sine(freq * 3, n, ph) + 0.08 * sine(freq * 4, n, ph)
    return out / 4 * env(n, attack, 0.3, 0.9, 0.6)


def flute(f: float, n: int, rng) -> np.ndarray:
    freq = vibrato(f, n, 0.005, 5.0, 0.2)
    tone = sine(freq, n) + 0.12 * sine(freq * 2, n) + 0.05 * sine(freq * 3, n)
    breath = bandpass(rng.uniform(-1, 1, n), f * 0.9, f * 3.5) * 0.25
    return (tone + breath) * env(n, 0.07, 0.1, 0.8, 0.12) * 0.7


def harp(f: float, n: int, rng, decay: float = 0.996) -> np.ndarray:
    """Karplus-Strong plucked string."""
    period = max(2, int(RATE / f))
    excite = np.zeros(n)
    burst = rng.uniform(-1, 1, min(period, n))
    excite[:len(burst)] = lowpass(burst, min(8000, f * 8))
    a = np.zeros(period + 2)
    a[0], a[period], a[period + 1] = 1.0, -0.5 * decay, -0.5 * decay
    out = signal.lfilter([1.0], a, excite)
    return out * env(n, 0.001, 0.0, 1.0, 0.05)


def bell(f: float, n: int, rng) -> np.ndarray:
    t = np.arange(n) / RATE
    out = np.zeros(n)
    for ratio, amp, tau in ((1.0, 1.0, 1.6), (2.0, 0.5, 1.0), (2.76, 0.35, 0.6), (5.4, 0.2, 0.3), (8.93, 0.1, 0.15)):
        if f * ratio < RATE * 0.42:
            out += amp * np.sin(2 * np.pi * f * ratio * t + rng.random()) * np.exp(-t / tau)
    return out * env(n, 0.002, 0.0, 1.0, 0.05) * 0.5


def low_bass(f: float, n: int, rng) -> np.ndarray:
    tone = 0.75 * sine(f, n) + 0.25 * saw(f, n, rng.random())
    return tone * env(n, 0.01, 0.15, 0.7, 0.08)


INSTRUMENTS = {"strings": strings, "staccato": staccato, "brass": brass, "choir": choir,
               "flute": flute, "harp": harp, "bell": bell, "bass": low_bass}


# --- percussion ----------------------------------------------------------------

def timpani(rng, pitch: float = 82, length: float = 0.9) -> np.ndarray:
    n = int(length * RATE)
    t = np.arange(n) / RATE
    body = sine(pitch * (1 + 0.25 * np.exp(-t / 0.03)), n) * np.exp(-t / 0.35) * 0.8 + \
        0.25 * sine(pitch * 2.4, n) * np.exp(-t / 0.15)
    thump = lowpass(rng.uniform(-1, 1, n), 900) * np.exp(-t / 0.02)
    return body + 0.5 * thump


def kick(rng) -> np.ndarray:
    n = int(0.35 * RATE)
    t = np.arange(n) / RATE
    click = highpass(rng.uniform(-1, 1, n), 2500) * np.exp(-t / 0.004)
    return sine(50 + 90 * np.exp(-t / 0.04), n) * np.exp(-t / 0.1) * 0.9 + 0.25 * click


def snare(rng, gain: float = 1.0) -> np.ndarray:
    n = int(0.22 * RATE)
    t = np.arange(n) / RATE
    noise = bandpass(rng.uniform(-1, 1, n), 1200, 9000) * np.exp(-t / 0.06)
    tone = sine(185, n) * np.exp(-t / 0.03)
    return gain * (0.8 * noise + 0.5 * tone)


def tom(rng, pitch: float) -> np.ndarray:
    n = int(0.45 * RATE)
    t = np.arange(n) / RATE
    return sine(pitch * (1 + 0.4 * np.exp(-t / 0.05)), n) * np.exp(-t / 0.18) + \
        0.2 * lowpass(rng.uniform(-1, 1, n), 1500) * np.exp(-t / 0.02)


def hat(rng, gain: float = 0.3, length: float = 0.05) -> np.ndarray:
    n = int(length * RATE)
    t = np.arange(n) / RATE
    return gain * highpass(rng.uniform(-1, 1, n), 7000, 4) * np.exp(-t / (length / 3))


def crash(rng) -> np.ndarray:
    n = int(2.4 * RATE)
    t = np.arange(n) / RATE
    return 0.5 * highpass(rng.uniform(-1, 1, n), 4000, 2) * np.exp(-t / 0.7)


def boom(rng) -> np.ndarray:
    n = int(2.2 * RATE)
    t = np.arange(n) / RATE
    return sine(55 * np.exp(-t / 1.2) + 18, n) * np.exp(-t / 0.7) * 1.3 + \
        0.3 * lowpass(rng.uniform(-1, 1, n), 200) * np.exp(-t / 0.15)


def hand(rng, pitch: float) -> np.ndarray:
    n = int(0.3 * RATE)
    t = np.arange(n) / RATE
    return sine(pitch * (1 + 0.15 * np.exp(-t / 0.02)), n) * np.exp(-t / 0.09) + \
        0.15 * bandpass(rng.uniform(-1, 1, n), 800, 4000) * np.exp(-t / 0.01)


def roll(rng, beats: float, beat_n: int) -> np.ndarray:
    """Timpani roll swelling over the given number of beats."""
    n = int(beats * beat_n)
    out = np.zeros(n + int(RATE))
    hits = int(beats * 8)
    for i in range(hits):
        g = 0.15 + 0.85 * (i / max(1, hits - 1)) ** 1.5
        s = timpani(rng, 70, 0.4) * g * 0.6
        start = i * n // hits
        out[start:start + len(s)] += s
    return out


# Per-bar patterns on a 16-step grid: instrument -> [(step, gain)].
DRUMS = {
    "march": {"timp": [(0, 1.0), (8, 0.8), (6, 0.35)], "snare": [(4, 0.7), (12, 0.7), (14, 0.3), (15, 0.35)]},
    "battle": {"kick": [(0, 1.0), (6, 0.7), (8, 0.9), (11, 0.6)], "snare": [(4, 0.9), (12, 0.9)],
               "hat": [(i, 0.5 if i % 4 else 0.8) for i in range(0, 16, 2)], "timp": [(0, 0.5)]},
    "space": {"kick": [(0, 1.0), (3, 0.6), (8, 0.9), (10, 0.6)], "snare": [(4, 0.85), (12, 0.85)],
              "hat": [(i, 0.25 + 0.2 * (i % 4 == 2)) for i in range(16)]},
    "hand": {"hand_lo": [(0, 1.0), (6, 0.6), (10, 0.7)], "hand_hi": [(3, 0.5), (4, 0.7), (11, 0.4), (12, 0.7), (14, 0.5)],
             "hat": [(i, 0.15) for i in range(1, 16, 2)]},
    "heartbeat": {"kick": [(0, 0.8), (3, 0.5)], "hat": [(12, 0.12)]},
    "sparse": {"boom2": [(0, 0.8)]},
    "pulse": {"timp": [(0, 0.7)], "hat": [(i, 0.12) for i in range(0, 16, 4)]},
    "none": {},
}


# --- composition -----------------------------------------------------------------

@dataclass
class Section:
    bars: int
    progression: list[int]           # scale degrees, one chord per bar (cycled)
    layers: dict[str, float]         # layer -> gain; "kit" scales the drums
    melody: str | None = None        # "A", "B" or None
    drums: str = "none"
    crash: bool = False              # cymbal crash on the first beat
    roll: bool = False               # timpani roll into the next section


@dataclass
class Track:
    name: str
    tempo: int
    root: int                        # MIDI note of the key centre
    scale: str
    seed: int
    sections: list[Section]
    lead: str = "brass"              # instrument for the theme
    rhythm: str = "fanfare"          # motif rhythm family
    lead_octave: int = 1
    ostinato: str = "driving"
    pad_cutoff: float = 2400
    reverb: float = 0.3
    notes: list = field(default_factory=list)


RHYTHMS = {  # eighth-note durations filling one bar (8 eighths)
    "march": [[3, 1, 2, 2], [2, 1, 1, 4], [3, 1, 4], [2, 2, 3, 1]],
    "fanfare": [[1, 1, 2, 4], [3, 1, 2, 2], [2, 2, 4], [1, 1, 1, 1, 4], [3, 1, 3, 1]],
    "flow": [[2, 2, 2, 2], [4, 2, 2], [2, 1, 1, 4], [3, 3, 2]],
    "sparse": [[8], [6, 2], [4, 4], [5, 3]],
}

OSTINATI = {  # chord-tone index per eighth; 3 = root an octave up
    "imperial": [0, 0, 0, 1, 0, 0, 2, 1],
    "driving": [0, 0, 2, 0, 3, 0, 2, 1],
    "rocking": [0, 2, 1, 2, 0, 2, 1, 3],
}


def step_midi(track: Track, step: int) -> int:
    sc = SCALES[track.scale]
    return track.root + 12 * (step // 7) + sc[step % 7]


def chord_steps(degree: int) -> list[int]:
    return [degree, degree + 2, degree + 4]


def make_motif(rng, family: str) -> list[tuple[int, int]]:
    """Two bars of (duration in eighths, scale-step offset)."""
    options = RHYTHMS[family]
    first = options[int(rng.integers(len(options)))]
    longest = min(options, key=len)
    second = options[int(rng.integers(len(options)))] if rng.random() < 0.5 else longest
    durations = list(first) + list(second)
    offsets, cur, last_leap = [], 0, 0
    for i in range(len(durations)):
        if i == 0:
            offsets.append(0)
            continue
        if last_leap:
            move = -int(np.sign(last_leap)) * int(rng.integers(1, 3))
            last_leap = 0
        elif rng.random() < 0.18:
            move = int(rng.choice([-4, -3, 3, 4]))
            last_leap = move
        else:
            move = int(rng.choice([-2, -1, 1, 2], p=[0.2, 0.3, 0.3, 0.2]))
        cur = int(np.clip(cur + move, -4, 6))
        offsets.append(cur)
    return list(zip(durations, offsets))


def vary(motif, rng, cadence: bool):
    """Restatement: same rhythm, small contour change, optionally a long final note."""
    out = [list(x) for x in motif]
    i = int(rng.integers(1, len(out)))
    out[i][1] += int(rng.choice([-1, 1]))
    if cadence and len(out) >= 2:
        total = sum(d for d, _ in out)
        keep = out[:-2] if len(out) > 2 else out[:1]
        used = sum(d for d, _ in keep)
        keep.append([total - used, 0])
        out = keep
    return [tuple(x) for x in out]


def nearest(step: int, allowed: list[int]) -> int:
    cands = [a + 7 * k for a in allowed for k in range(-2, 4)]
    return min(cands, key=lambda c: (abs(c - step), c))


class Score:
    """Collects notes per layer into stereo stems."""

    def __init__(self, track: Track, length: int | None = None):
        self.track = track
        self.rng = np.random.default_rng(track.seed)
        self.beat_n = int(60 / track.tempo * RATE)
        self.bar_n = 4 * self.beat_n
        bars = sum(s.bars for s in track.sections)
        self.length = length or bars * self.bar_n + int(3 * RATE)
        self.stems: dict[str, np.ndarray] = {}
        self.sends: dict[str, float] = {}

    def add(self, name: str, start: int, sound: np.ndarray, pan: float = 0.0, send: float = 0.3) -> None:
        if name not in self.stems:
            self.stems[name] = np.zeros((2, self.length))
            self.sends[name] = send
        buf = self.stems[name]
        end = min(self.length, start + len(sound))
        if start >= self.length or end <= start:
            return
        angle = (pan + 1) * np.pi / 4
        buf[0, start:end] += np.cos(angle) * sound[:end - start]
        buf[1, start:end] += np.sin(angle) * sound[:end - start]


def compose(track: Track) -> Score:
    sc = Score(track)
    rng = sc.rng
    motifs = {"A": make_motif(rng, track.rhythm), "B": make_motif(rng, track.rhythm)}
    lead_inst = INSTRUMENTS[track.lead]
    bar0 = 0
    register = 9  # the theme sits around the 9th scale step above the root
    for sec in track.sections:
        L = sec.layers
        for b in range(sec.bars):
            degree = sec.progression[b % len(sec.progression)]
            start = (bar0 + b) * sc.bar_n
            midi = [step_midi(track, s) for s in chord_steps(degree)]
            # Sustained string pad, voiced low to high across the stereo field.
            if "pad" in L:
                n = sc.bar_n + int(0.5 * RATE)
                for i, m in enumerate(sorted(midi)):
                    sc.add("pad", start, L["pad"] * strings(hz(m - 12 + 12 * (i == 2)), n, rng), pan=(i - 1) * 0.5, send=0.45)
            if "choir" in L:
                n = sc.bar_n + int(0.6 * RATE)
                for i, m in enumerate(midi):
                    sc.add("choir", start, L["choir"] * choir(hz(m), n, rng), pan=(i - 1) * 0.6, send=0.6)
            if "bass" in L:
                root_m = step_midi(track, degree) - 24
                if track.ostinato == "imperial" or sec.drums in ("battle", "space"):
                    for k in range(8):
                        n = sc.beat_n // 2
                        acc = 1.0 if k in (0, 3, 6) else 0.6
                        sc.add("bass", start + k * n, L["bass"] * acc * low_bass(hz(root_m), n, rng), send=0.1)
                else:
                    for k in (0, 2):
                        n = 2 * sc.beat_n
                        sc.add("bass", start + k * sc.beat_n, L["bass"] * low_bass(hz(root_m), n, rng), send=0.1)
            if "ostinato" in L:
                for k, idx in enumerate(OSTINATI[track.ostinato]):
                    m = (midi[idx] if idx < 3 else midi[0] + 12) - 12
                    n = sc.beat_n // 2
                    sc.add("ostinato", start + k * n, L["ostinato"] * staccato(hz(m), n, rng), pan=-0.35, send=0.25)
            if "arp" in L:
                for k in range(16):
                    m = midi[k % 3] + 12 * (1 + (k // 3) % 2)
                    sc.add("arp", start + k * sc.beat_n // 4, L["arp"] * 0.5 * harp(hz(m), int(0.6 * RATE), rng),
                           pan=0.4 * np.sin(k), send=0.35)
            if "harp" in L:
                for k in range(8):
                    m = midi[k % 3] + 12 * (k // 3 % 2)
                    sc.add("harp", start + k * sc.beat_n // 2, L["harp"] * 0.6 * harp(hz(m), int(1.2 * RATE), rng, 0.998),
                           pan=0.45, send=0.4)
            if "bells" in L and b % 2 == 0:
                for k, idx in enumerate((2, 1)):
                    sc.add("bells", start + k * 2 * sc.beat_n, L["bells"] * bell(hz(midi[idx] + 12), int(2.5 * RATE), rng),
                           pan=0.3, send=0.6)
            if "stabs" in L:
                for k in (0, 3, 6):
                    for i, m in enumerate(midi):
                        sc.add("stabs", start + k * sc.beat_n // 2, L["stabs"] * 0.5 * brass(hz(m), int(0.25 * RATE), rng, 0.02, 1.3),
                               pan=(i - 1) * 0.3, send=0.3)
            kit = L.get("kit", 1.0)
            for name, hits in DRUMS[sec.drums].items():
                for step, gain in hits:
                    t = start + step * sc.beat_n // 4
                    g = gain * kit
                    if name == "timp":
                        sc.add("drums", t, g * timpani(rng), send=0.25)
                    elif name == "kick":
                        sc.add("drums", t, g * kick(rng), send=0.1)
                    elif name == "snare":
                        sc.add("drums", t, g * snare(rng), pan=0.1, send=0.25)
                    elif name == "hat":
                        sc.add("drums", t, g * hat(rng), pan=0.3, send=0.1)
                    elif name == "hand_lo":
                        sc.add("drums", t, g * hand(rng, 140), pan=-0.2, send=0.2)
                    elif name == "hand_hi":
                        sc.add("drums", t, g * hand(rng, 260), pan=0.25, send=0.2)
                    elif name == "boom2" and b % 2 == 0:
                        sc.add("drums", t, g * boom(rng), send=0.4)
            # Tom fill at the end of each four-bar battle phrase.
            if sec.drums in ("battle", "space") and b % 4 == 3:
                for k, p in enumerate((220, 180, 150, 120)):
                    sc.add("drums", start + (12 + k) * sc.beat_n // 4, 0.7 * kit * tom(rng, p), pan=0.5 - 0.33 * k, send=0.2)
            if b == 0 and sec.crash:
                sc.add("drums", start, crash(rng), pan=0.2, send=0.5)
        # Theme: motif, then a varied restatement that ends on a long chord tone.
        if sec.melody:
            base = motifs[sec.melody]
            for p in range(0, sec.bars, 2):
                cadence = (p // 2) % 2 == 1
                motif = base if not cadence else vary(base, rng, True)
                t8 = 0
                for dur, off in motif:
                    bar_in = p + t8 // 8
                    if bar_in >= sec.bars:
                        break
                    degree = sec.progression[bar_in % len(sec.progression)]
                    step = nearest(register, chord_steps(degree)) + off
                    if t8 % 4 == 0 or dur >= 4:
                        step = nearest(step, chord_steps(degree))
                    m = step_midi(track, step) + 12 * (track.lead_octave - 1)
                    n = int(dur * sc.beat_n / 2) + int(0.08 * RATE)
                    at = (bar0 + p) * sc.bar_n + t8 * sc.beat_n // 2
                    sc.add("lead", at, L.get("lead", 0.8) * lead_inst(hz(m), n, rng), pan=0.05, send=0.4)
                    if "double" in L:  # octave-down string doubling for climaxes
                        sc.add("lead", at, L["double"] * strings(hz(m - 12), n, rng, 0.05, 0.2), pan=-0.15, send=0.4)
                    t8 += dur
        if sec.roll:
            sc.add("drums", (bar0 + sec.bars - 1) * sc.bar_n, roll(rng, 4, sc.beat_n), send=0.3)
        bar0 += sec.bars
    return sc


BUS_LOWPASS = {"choir": 3600, "bass": 400, "ostinato": 4200, "arp": 6500, "harp": 6500, "lead": 6500, "stabs": 5500}
BUS_GAINS = {"pad": 0.3, "choir": 0.32, "bass": 0.3, "ostinato": 0.34, "arp": 0.24, "harp": 0.3,
             "bells": 0.26, "lead": 0.5, "stabs": 0.34, "drums": 0.45}
# Stems widened by delaying the right channel slightly (Haas effect).
WIDE = {"pad": 0.013, "choir": 0.017, "harp": 0.009, "arp": 0.007, "bells": 0.011}


def reverb_ir(rng, seconds: float = 2.6) -> np.ndarray:
    n = int(seconds * RATE)
    t = np.arange(n) / RATE
    ir = np.zeros((2, n))
    for ch in range(2):
        ir[ch] = lowpass(rng.uniform(-1, 1, n) * np.exp(-t / (seconds / 6.9)), 5500)
        for d, g in ((0.011, 0.5), (0.019, 0.35), (0.027, 0.3), (0.041, 0.2)):
            ir[ch, int((d + 0.004 * ch) * RATE)] += g
        ir[ch] /= np.sqrt((ir[ch] ** 2).sum())
    return ir


def mixdown(sc: Score, wet_level: float, length: int | None = None) -> np.ndarray:
    dry = np.zeros((2, sc.length))
    send = np.zeros((2, sc.length))
    for name, buf in sc.stems.items():
        if name == "pad":
            buf = lowpass(buf, sc.track.pad_cutoff)
        elif name in BUS_LOWPASS:
            buf = lowpass(buf, BUS_LOWPASS[name])
        buf = buf * BUS_GAINS.get(name, 0.3)
        if name in WIDE:
            d = int(WIDE[name] * RATE)
            buf = np.stack([buf[0], np.concatenate([np.zeros(d), buf[1, :-d]])])
        dry += buf
        send += buf * sc.sends[name]
    ir = reverb_ir(np.random.default_rng(sc.track.seed + 7))
    pre = int(0.02 * RATE)
    wet = np.stack([signal.fftconvolve(send[c], ir[c])[:sc.length] for c in range(2)])
    wet = np.roll(wet, pre, axis=1)
    wet[:, :pre] = 0
    mix = highpass(dry + wet_level * 3.0 * wet, 40)
    if length is not None:
        mix = mix[:, :length]
    return master(mix)


def master(mix: np.ndarray, target_rms: float = 0.105) -> np.ndarray:
    rms = np.sqrt((mix ** 2).mean()) or 1.0
    mix = mix * (target_rms / rms)
    mix = np.tanh(1.3 * mix) / np.tanh(1.3)          # gentle soft clip
    peak = np.abs(mix).max() or 1.0
    if peak > 0.93:
        mix *= 0.93 / peak
    fade_in, fade_out = int(0.05 * RATE), int(2.0 * RATE)
    mix[:, :fade_in] *= np.linspace(0, 1, fade_in)
    mix[:, -fade_out:] *= np.linspace(1, 0, fade_out) ** 1.5
    return mix


def render(track: Track) -> np.ndarray:
    sc = compose(track)
    bars = sum(s.bars for s in track.sections)
    return mixdown(sc, track.reverb, bars * sc.bar_n + int(2.5 * RATE))


# --- track definitions -----------------------------------------------------------

def S(bars, prog, melody=None, drums="none", crash=False, roll=False, **layers):
    return Section(bars, prog, layers, melody, drums, crash, roll)


IMP = [0, 0, 5, 1, 0, 3, 5, 1]
HERO = [0, 4, 5, 3, 0, 4, 1, 4]
HERO_B = [5, 3, 0, 4, 5, 3, 1, 4]
SPACE = [0, 5, 3, 6, 0, 5, 4, 4]
TENSE = [0, 0, 1, 0, 5, 5, 1, 0]
JUNGLE = [0, 3, 0, 6, 0, 3, 4, 0]
JUNGLE_B = [3, 6, 3, 4, 3, 6, 4, 0]
BATTLE = [0, 5, 6, 4, 0, 5, 3, 4]
BATTLE_B = [3, 4, 5, 6, 3, 4, 2, 4]
THRAWN = [0, 5, 3, 4, 0, 1, 4, 4]

TRACKS = [
    Track("sw-imperial", tempo=92, root=50, scale="phrygian", seed=101, lead="brass", rhythm="march",
          lead_octave=0, ostinato="imperial", pad_cutoff=1500, reverb=0.32, sections=[
              S(4, IMP, drums="march", ostinato=0.8, bass=0.8),
              S(8, IMP, "A", "march", ostinato=0.9, bass=0.9, pad=0.6, lead=0.9),
              S(8, IMP, "A", "march", True, ostinato=0.9, bass=1.0, pad=0.8, choir=0.5, lead=1.0, double=0.4),
              S(8, [5, 1, 5, 6, 3, 1, 0, 1], "B", "pulse", ostinato=0.6, bass=0.8, pad=0.8, lead=0.8),
              S(4, [0, 0, 1, 1], drums="sparse", roll=True, pad=0.9, choir=0.6, bass=0.6),
              S(8, IMP, "A", "march", True, ostinato=1.0, bass=1.0, pad=0.9, choir=0.7, lead=1.1, double=0.6, stabs=0.5),
              S(8, IMP, "B", "march", ostinato=1.0, bass=1.0, pad=0.9, choir=0.7, lead=1.0, double=0.5),
              S(4, [0, 1, 0, 0], drums="sparse", pad=0.8, choir=0.5, bass=0.6),
          ]),
    Track("sw-heroic", tempo=116, root=55, scale="major", seed=202, lead="brass", rhythm="fanfare",
          ostinato="driving", pad_cutoff=2600, reverb=0.3, sections=[
              S(4, [0, 4, 5, 4], drums="pulse", crash=True, ostinato=0.8, bass=0.8, pad=0.6, stabs=0.6),
              S(8, HERO, "A", "battle", ostinato=0.8, bass=0.9, pad=0.7, lead=1.0),
              S(8, HERO, "A", "battle", True, ostinato=0.9, bass=1.0, pad=0.8, lead=1.1, double=0.5, harp=0.4),
              S(8, HERO_B, "B", "march", ostinato=0.7, bass=0.9, pad=0.8, choir=0.4, lead=0.9),
              S(8, [5, 5, 3, 3, 1, 1, 4, 4], drums="pulse", roll=True, pad=0.9, choir=0.6, harp=0.5, bass=0.7),
              S(8, HERO, "A", "battle", True, ostinato=1.0, bass=1.0, pad=0.9, choir=0.6, lead=1.2, double=0.7, stabs=0.5),
              S(8, HERO_B, "B", "battle", ostinato=1.0, bass=1.0, pad=0.9, choir=0.6, lead=1.1, double=0.6),
              S(4, [0, 4, 0, 0], drums="pulse", crash=True, pad=0.9, choir=0.6, stabs=0.5, bass=0.8),
          ]),
    Track("sw-space", tempo=138, root=52, scale="minor", seed=303, lead="brass", rhythm="fanfare",
          ostinato="driving", pad_cutoff=2200, reverb=0.28, sections=[
              S(4, SPACE, arp=0.9, pad=0.5),
              S(8, SPACE, drums="space", arp=0.9, pad=0.6, bass=0.9),
              S(8, SPACE, "A", "space", True, arp=0.8, pad=0.7, bass=1.0, lead=1.0),
              S(8, SPACE, "A", "space", arp=0.8, pad=0.8, bass=1.0, lead=1.1, double=0.5, ostinato=0.5),
              S(8, [5, 3, 6, 4, 5, 3, 6, 4], "B", "battle", arp=0.7, pad=0.8, bass=1.0, lead=1.0, stabs=0.5),
              S(8, [0, 0, 5, 5, 3, 3, 4, 4], drums="pulse", roll=True, arp=0.9, pad=0.9, choir=0.6, bass=0.7),
              S(8, SPACE, "A", "space", True, arp=0.9, pad=0.9, choir=0.6, bass=1.0, lead=1.2, double=0.7, ostinato=0.6),
              S(8, SPACE, "B", "space", arp=0.8, pad=0.9, bass=1.0, lead=1.1, double=0.6, stabs=0.5),
              S(4, [0, 5, 0, 0], drums="sparse", arp=0.8, pad=0.8),
          ]),
    Track("sw-tension", tempo=72, root=45, scale="minor", seed=404, lead="bell", rhythm="sparse",
          pad_cutoff=900, reverb=0.45, sections=[
              S(4, TENSE, drums="heartbeat", pad=0.6, bass=0.5),
              S(8, TENSE, drums="heartbeat", pad=0.7, bass=0.6, bells=0.6),
              S(8, TENSE, "A", "heartbeat", pad=0.8, bass=0.6, lead=0.7),
              S(8, [5, 5, 1, 1, 6, 6, 4, 4], "B", "sparse", pad=0.8, choir=0.4, bass=0.6, lead=0.6),
              S(8, TENSE, drums="heartbeat", pad=0.8, bass=0.7, bells=0.7, ostinato=0.3),
              S(8, TENSE, "A", "pulse", pad=0.9, choir=0.5, bass=0.7, lead=0.8, ostinato=0.35),
              S(4, [0, 0, 0, 0], drums="sparse", pad=0.7, choir=0.4),
          ]),
    Track("sw-jungle", tempo=100, root=48, scale="dorian", seed=505, lead="flute", rhythm="flow",
          ostinato="rocking", pad_cutoff=1700, reverb=0.38, sections=[
              S(4, JUNGLE, drums="hand", kit=0.8, harp=0.6),
              S(8, JUNGLE, "A", "hand", pad=0.5, harp=0.6, bass=0.6, lead=0.9),
              S(8, JUNGLE, "A", "hand", pad=0.6, harp=0.6, bass=0.7, lead=1.0, choir=0.3),
              S(8, JUNGLE_B, "B", "hand", pad=0.7, harp=0.5, bass=0.7, lead=0.9),
              S(8, JUNGLE, drums="hand", pad=0.7, harp=0.7, bass=0.6, choir=0.5),
              S(8, JUNGLE, "A", "hand", pad=0.8, harp=0.6, bass=0.8, lead=1.1, choir=0.5, double=0.3),
              S(8, JUNGLE_B, "B", "hand", pad=0.8, harp=0.6, bass=0.8, lead=1.0),
              S(4, [0, 0, 0, 0], harp=0.6, pad=0.5),
          ]),
    Track("sw-battle", tempo=128, root=48, scale="minor", seed=606, lead="brass", rhythm="march",
          ostinato="driving", pad_cutoff=2200, reverb=0.26, sections=[
              S(4, [0, 0, 5, 4], drums="battle", ostinato=0.9, bass=0.9, stabs=0.6),
              S(8, BATTLE, "A", "battle", ostinato=0.9, bass=1.0, pad=0.6, lead=1.0, stabs=0.4),
              S(8, BATTLE, "A", "battle", True, ostinato=1.0, bass=1.0, pad=0.7, lead=1.1, double=0.5),
              S(8, BATTLE_B, "B", "march", ostinato=0.8, bass=0.9, pad=0.8, lead=1.0, choir=0.4),
              S(4, [0, 0, 5, 5], drums="sparse", roll=True, pad=0.9, choir=0.6, bass=0.7),
              S(8, BATTLE, "A", "battle", True, ostinato=1.0, bass=1.0, pad=0.9, choir=0.6, lead=1.2, double=0.7, stabs=0.6),
              S(8, BATTLE_B, "B", "battle", ostinato=1.0, bass=1.0, pad=0.9, lead=1.1, double=0.6, stabs=0.5),
              S(4, [0, 4, 0, 0], drums="battle", crash=True, stabs=0.7, pad=0.8, bass=0.9),
          ]),
    Track("sw-thrawn", tempo=66, root=47, scale="harmonic", seed=707, lead="bell", rhythm="sparse",
          ostinato="imperial", pad_cutoff=1300, reverb=0.5, sections=[
              S(4, THRAWN, drums="sparse", choir=0.6, bass=0.5),
              S(8, THRAWN, "A", "sparse", choir=0.7, pad=0.5, bass=0.6, lead=0.8),
              S(8, THRAWN, "A", "pulse", choir=0.8, pad=0.7, bass=0.7, lead=0.9, ostinato=0.35, double=0.35),
              S(8, [5, 1, 4, 0, 5, 1, 4, 4], "B", "pulse", choir=0.8, pad=0.8, bass=0.7, lead=0.8, ostinato=0.4),
              S(8, THRAWN, "A", "march", True, choir=0.9, pad=0.9, bass=0.8, lead=1.0, ostinato=0.5, double=0.5, stabs=0.3),
              S(4, [0, 0, 0, 0], drums="sparse", choir=0.7, pad=0.6),
          ]),
]


# --- stingers ----------------------------------------------------------------------

def stinger(name: str) -> np.ndarray:
    """Short end-of-mission cues, written out note by note: (beat, MIDI, beats)."""
    if name == "sw-victory":
        tempo, seed = 100, 808  # C major
        theme = [(0, 67, 0.5), (0.5, 72, 0.5), (1, 76, 0.5), (1.5, 79, 1.5), (3, 77, 0.5), (3.5, 76, 0.5),
                 (4, 74, 0.5), (4.5, 76, 0.5), (5, 79, 1.0), (6, 84, 4.0)]
        chords = [(0, [48, 55, 64, 67], 3), (3, [53, 57, 65, 72], 2), (5, [55, 59, 62, 67], 1), (6, [48, 55, 64, 72], 4)]
        hits, timp_pitch = [0, 3, 5, 6], 73
    else:
        tempo, seed = 60, 909   # A minor
        theme = [(0, 69, 1.0), (1, 67, 1.0), (2, 65, 1.0), (3, 64, 1.5), (4.5, 62, 0.5), (5, 64, 3.0)]
        chords = [(0, [45, 52, 57, 60], 2), (2, [41, 53, 57, 60], 1), (3, [40, 52, 55, 59], 2), (5, [33, 45, 52, 57], 3)]
        hits, timp_pitch = [0, 5], 55
    beats_total = max(t + d for t, _, d in theme)
    track = Track(name, tempo, 60, "major", seed=seed, sections=[])
    sc = Score(track, length=int((beats_total * 60 / tempo + 4.5) * RATE))
    rng, beat = sc.rng, sc.beat_n
    for t, pitches, dur in chords:
        n = int(dur * beat + 1.2 * RATE)
        for i, m in enumerate(pitches):
            sc.add("pad", int(t * beat), 0.8 * strings(hz(m), n, rng, 0.08, 1.0), pan=(i - 1.5) * 0.35, send=0.5)
            sc.add("choir", int(t * beat), 0.4 * choir(hz(m + 12), n, rng, 0.2), pan=(1.5 - i) * 0.3, send=0.6)
        sc.add("bass", int(t * beat), 0.8 * low_bass(hz(pitches[0] - 12), n, rng), send=0.1)
    for t, m, dur in theme:
        n = int(dur * beat + 0.15 * RATE) + (int(1.0 * RATE) if t == theme[-1][0] else 0)
        sc.add("lead", int(t * beat), 1.1 * brass(hz(m), n, rng, 0.04, 1.2), send=0.4)
        sc.add("lead", int(t * beat), 0.4 * strings(hz(m - 12), n, rng, 0.04, 0.4), pan=-0.2, send=0.4)
    for t in hits:
        sc.add("drums", int(t * beat), timpani(rng, timp_pitch, 1.4), send=0.3)
    if name == "sw-victory":
        sc.add("drums", int(6 * beat), crash(rng), pan=0.2, send=0.5)
    else:
        sc.add("drums", int(5 * beat), boom(rng), send=0.5)
    return mixdown(sc, 0.4)


STINGERS = ["sw-victory", "sw-defeat"]


def write(path: Path, audio: np.ndarray) -> None:
    # libsndfile's Vorbis encoder can crash on one huge write; feed it in blocks.
    with sf.SoundFile(path, "w", RATE, 2, format="OGG", subtype="VORBIS") as f:
        data = audio.T.astype(np.float32)
        for i in range(0, len(data), 8192):
            f.write(data[i:i + 8192])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--track", action="append", help="render only this track (repeatable)")
    parser.add_argument("--out", type=Path, default=OUT, help="output directory (default: the add-on's music/)")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    for name in [t.name for t in TRACKS] + STINGERS:
        if args.track and name not in args.track:
            continue
        track = next((t for t in TRACKS if t.name == name), None)
        audio = render(track) if track else stinger(name)
        write(args.out / f"{name}.ogg", audio)
        rms = 20 * np.log10(np.sqrt((audio ** 2).mean()))
        print(f"{name}.ogg  {audio.shape[1] / RATE:.0f}s  rms {rms:.1f} dBFS  peak {np.abs(audio).max():.2f}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
