#!/usr/bin/env python3
"""Compose and render the add-on's original music from code.

Project rule: no copyrighted score. Every note here is generated from scales,
chord progressions and rhythm patterns written in this file, with fixed
seeds; melodies are built from chord tones by rule, not modelled on any film
or game theme. Rendering is additive synthesis (detuned saw pads, a filtered
"brass" lead, sine/saw bass, timpani and snare made from tuned sine sweeps and
noise, plucked arpeggios) through a convolution reverb, written as Ogg Vorbis.

  sw-imperial.ogg   cold minor ostinato, low brass and timpani (Imperial missions)
  sw-heroic.ogg     major-key fanfare over driving strings (New Republic battles)
  sw-space.ogg      fast arpeggios and drums (space battles)
  sw-tension.ogg    sparse pulses and drones (infiltration and stealth)
  sw-jungle.ogg     hand-drum rhythms and modal pads (Wayland)

Usage: python3 production/tools/gen_music.py [--track NAME]
Requires numpy and soundfile (art toolchain Python).
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "addons/Star_Wars_Thrawn_Trilogy/music"
RATE = 32000

SCALES = {
    "minor": [0, 2, 3, 5, 7, 8, 10],
    "major": [0, 2, 4, 5, 7, 9, 11],
    "phrygian": [0, 1, 3, 5, 7, 8, 10],
    "dorian": [0, 2, 3, 5, 7, 9, 10],
}


def hz(midi: float) -> float:
    return 440.0 * 2 ** ((midi - 69) / 12)


def lowpass(x: np.ndarray, cutoff: float) -> np.ndarray:
    """Brick-wall-ish low-pass in the frequency domain with a soft shoulder."""
    spec = np.fft.rfft(x)
    freqs = np.fft.rfftfreq(len(x), 1 / RATE)
    spec *= 1 / (1 + (freqs / cutoff) ** 4)
    return np.fft.irfft(spec, len(x))


def highpass(x: np.ndarray, cutoff: float) -> np.ndarray:
    spec = np.fft.rfft(x)
    freqs = np.fft.rfftfreq(len(x), 1 / RATE)
    spec *= (freqs / cutoff) ** 4 / (1 + (freqs / cutoff) ** 4)
    return np.fft.irfft(spec, len(x))


def adsr(n: int, a: float, d: float, s: float, r: float) -> np.ndarray:
    a_n, d_n, r_n = max(1, int(a * RATE)), max(1, int(d * RATE)), max(1, int(r * RATE))
    env = np.full(n, float(s))
    env[:a_n] = np.linspace(0, 1, a_n)[: min(a_n, n)] if a_n <= n else np.linspace(0, 1, n)
    if a_n < n:
        end = min(n, a_n + d_n)
        env[a_n:end] = np.linspace(1, s, d_n)[: end - a_n]
    if r_n < n:
        env[-r_n:] *= np.linspace(1, 0, r_n)
    return env


def saw(freq: float, n: int, phase: float = 0.0) -> np.ndarray:
    t = np.arange(n) / RATE
    return 2 * ((freq * t + phase) % 1.0) - 1


def sine(freq, n: int) -> np.ndarray:
    t = np.arange(n) / RATE
    return np.sin(2 * np.pi * freq * t)


@dataclass
class Track:
    name: str
    tempo: int
    root: int                    # MIDI note of the key centre
    scale: str
    progression: list[int]       # scale degrees, one chord per bar
    bars: int
    seed: int
    lead: bool = True
    arps: bool = False
    drums: str = "march"         # march, battle, sparse, hand
    pad_cutoff: float = 1800
    lead_octave: int = 1
    notes: list = field(default_factory=list)


def chord(track: Track, degree: int) -> list[int]:
    scale = SCALES[track.scale]
    return [track.root + scale[(degree + k) % 7] + 12 * ((degree + k) // 7) for k in (0, 2, 4)]


def place(buf: np.ndarray, start: int, sound: np.ndarray) -> None:
    end = min(len(buf), start + len(sound))
    if start < len(buf):
        buf[start:end] += sound[: end - start]


def render(track: Track) -> np.ndarray:
    rng = np.random.default_rng(track.seed)
    beat = 60 / track.tempo
    bar = 4 * beat
    total = int((track.bars * bar + 3) * RATE)
    pad = np.zeros(total)
    bass = np.zeros(total)
    lead = np.zeros(total)
    arp = np.zeros(total)
    drum = np.zeros(total)
    bar_n = int(bar * RATE)
    beat_n = int(beat * RATE)
    previous = None
    for b in range(track.bars):
        degree = track.progression[b % len(track.progression)]
        tones = chord(track, degree)
        start = b * bar_n
        # Pad: three detuned saws per chord tone, slow swell.
        for note in tones:
            n = bar_n + int(0.4 * RATE)
            voice = sum(saw(hz(note) * d, n, rng.random()) for d in (0.997, 1.0, 1.004)) / 3
            place(pad, start, voice * adsr(n, 0.6, 0.4, 0.8, 0.5))
        # Bass: root ostinato on eighth notes with accents.
        root = tones[0] - 24
        for k in range(8):
            n = beat_n // 2
            accent = 1.0 if k in (0, 3, 6) else 0.55
            tone = 0.7 * sine(hz(root), n) + 0.3 * saw(hz(root), n)
            place(bass, start + k * n, accent * tone * adsr(n, 0.005, 0.1, 0.4, 0.05))
        # Lead: a rule-built phrase from chord tones every other bar.
        if track.lead and b % 2 == 0:
            rhythm = [2, 1, 1, 2, 2] if b % 4 == 0 else [1, 1, 1, 1, 3, 1]
            t = start
            for i, length in enumerate(rhythm):
                choices = tones + [tones[0] + 12]
                note = int(rng.choice(choices))
                if previous is not None and abs(note - previous) > 7:  # keep leaps singable
                    note = min(choices, key=lambda c: abs(c - previous))
                previous = note
                n = int(length * beat_n / 2) + int(0.05 * RATE)
                f = hz(note + 12 * track.lead_octave)
                vib = 1 + 0.004 * np.sin(2 * np.pi * 5.5 * np.arange(n) / RATE)
                phase = np.cumsum(f * vib) / RATE
                brass = 2 * (phase % 1.0) - 1
                place(lead, t, brass * adsr(n, 0.04, 0.12, 0.7, 0.08))
                t += int(length * beat_n / 2)
        # Arpeggio: plucked chord tones in sixteenths.
        if track.arps:
            for k in range(16):
                note = tones[k % 3] + 12 * (1 + (k // 3) % 2)
                n = beat_n // 4
                pluck = np.sign(sine(hz(note), n)) * adsr(n, 0.002, 0.06, 0.0, 0.01)
                place(arp, start + k * n, pluck)
        # Drums.
        for k in range(4):
            t = start + k * beat_n
            if track.drums in ("march", "battle"):
                if k in (0, 2) or track.drums == "battle":
                    n = int(0.6 * RATE)
                    timp = sine(np.linspace(110, 55, n), n) * adsr(n, 0.002, 0.3, 0.0, 0.1)
                    place(drum, t, timp)
                if k in (1, 3):
                    n = int(0.18 * RATE)
                    snare = highpass(rng.uniform(-1, 1, n), 1500) * adsr(n, 0.001, 0.08, 0.0, 0.02)
                    place(drum, t, 0.6 * snare)
                if track.drums == "battle":
                    for off in (beat_n // 2,):
                        n = int(0.1 * RATE)
                        place(drum, t + off, 0.3 * highpass(rng.uniform(-1, 1, n), 3000) * adsr(n, 0.001, 0.04, 0, 0.01))
            elif track.drums == "hand":
                for off, pitch, gain in ((0, 160, 1.0), (beat_n * 3 // 4, 220, 0.6), (beat_n // 2, 180, 0.5)):
                    n = int(0.25 * RATE)
                    hit = sine(np.linspace(pitch, pitch * 0.7, n), n) * adsr(n, 0.001, 0.12, 0, 0.05)
                    place(drum, t + off, gain * hit)
            elif track.drums == "sparse" and k == 0 and b % 2 == 0:
                n = int(1.2 * RATE)
                place(drum, t, sine(np.linspace(70, 40, n), n) * adsr(n, 0.005, 0.6, 0, 0.3))
    mix = (0.32 * lowpass(pad, track.pad_cutoff) + 0.5 * lowpass(bass, 600) + 0.24 * lowpass(lead, 2600)
           + 0.12 * lowpass(arp, 3500) + 0.55 * drum)
    # Convolution reverb: decaying filtered noise tail.
    tail_n = int(1.8 * RATE)
    impulse = rng.uniform(-1, 1, tail_n) * np.exp(-np.arange(tail_n) / (0.45 * RATE))
    impulse = lowpass(impulse, 4000)
    impulse[0] = 6.0
    size = 1 << int(np.ceil(np.log2(len(mix) + tail_n)))
    wet = np.fft.irfft(np.fft.rfft(mix, size) * np.fft.rfft(impulse, size), size)[: len(mix)]
    out = 0.75 * mix + 0.25 * wet / (np.abs(wet).max() or 1) * np.abs(mix).max()
    out = out[: int(track.bars * bar * RATE)]
    fade = int(0.05 * RATE)
    out[:fade] *= np.linspace(0, 1, fade)
    out[-fade:] *= np.linspace(1, 0, fade)
    return 0.9 * out / (np.abs(out).max() or 1)


TRACKS = [
    Track("sw-imperial", tempo=84, root=50, scale="phrygian", progression=[0, 0, 5, 1, 0, 3, 5, 1],
          bars=32, seed=101, drums="march", pad_cutoff=1200, lead_octave=0),
    Track("sw-heroic", tempo=112, root=55, scale="major", progression=[0, 4, 5, 3, 0, 4, 1, 4],
          bars=40, seed=202, drums="battle", pad_cutoff=2400),
    Track("sw-space", tempo=132, root=52, scale="minor", progression=[0, 5, 3, 6, 0, 5, 4, 4],
          bars=48, seed=303, arps=True, drums="battle", pad_cutoff=2000),
    Track("sw-tension", tempo=70, root=45, scale="minor", progression=[0, 0, 1, 0, 5, 5, 1, 0],
          bars=24, seed=404, lead=False, arps=False, drums="sparse", pad_cutoff=700),
    Track("sw-jungle", tempo=96, root=48, scale="dorian", progression=[0, 3, 0, 6, 0, 3, 4, 0],
          bars=32, seed=505, lead=True, drums="hand", pad_cutoff=1500, lead_octave=0),
]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--track", action="append")
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    for track in TRACKS:
        if args.track and track.name not in args.track:
            continue
        audio = render(track)
        # libsndfile's Vorbis encoder can crash on one huge write; feed it in blocks.
        with sf.SoundFile(OUT / f"{track.name}.ogg", "w", RATE, 1, format="OGG", subtype="VORBIS") as f:
            data = audio.astype(np.float32)
            for i in range(0, len(data), 8192):
                f.write(data[i:i + 8192])
        print(f"{track.name}.ogg  {len(audio) / RATE:.0f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
