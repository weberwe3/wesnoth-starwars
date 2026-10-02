#!/usr/bin/env python3
"""Synthesize the add-on's original sound effects from scratch.

Every sound is generated mathematically (oscillators, noise and envelopes)
with fixed seeds, so the output is reproducible and contains no recorded or
copied audio (project rule: no copyrighted score, dialogue or effects).
Output: 22,050 Hz mono 16-bit WAV under addons/.../sounds/.

  sw-blaster.wav           hand blaster: bright descending "pew" with a crack
  sw-blaster-heavy.wav     rifles' heavier cousin: repeaters, cannons, E-Web
  sw-laser-cannon.wav      starfighter laser: sharp twin-tone zap
  sw-turbolaser.wav        capital-ship turbolaser: deep falling boom
  sw-ion.wav               ion cannon: buzzing electric crackle
  sw-torpedo.wav           proton torpedo launch: rising whoosh
  sw-explosion.wav         bombs, grenades and torpedo impacts
  sw-stun.wav              stun setting: warbling rings
  sw-bowcaster.wav         Wookiee bowcaster: string twang plus energy zap
  sw-lightsaber.wav        lightsaber swing: humming blade with a Doppler sweep
  sw-force-lightning.wav   Force lightning: dense electric crackling
  sw-vibroblade.wav        vibroblade: high whine swish

Usage: python3 production/tools/gen_sound_effects.py
Standard library only.
"""
from __future__ import annotations

import math
import random
import struct
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "addons/Star_Wars_Thrawn_Trilogy/sounds"
RATE = 22050


def envelope(n: int, attack: float, decay: float) -> list[float]:
    """Linear attack then exponential decay over n samples."""
    a = max(1, int(attack * RATE))
    out = []
    for i in range(n):
        if i < a:
            out.append(i / a)
        else:
            out.append(math.exp(-(i - a) / (decay * RATE)))
    return out


def sweep(n: int, f0: float, f1: float, curve: float = 1.0, shape: str = "sine") -> list[float]:
    """Oscillator whose frequency glides from f0 to f1."""
    phase = 0.0
    out = []
    for i in range(n):
        t = (i / n) ** curve
        f = f0 + (f1 - f0) * t
        phase += 2 * math.pi * f / RATE
        if shape == "saw":
            out.append(2 * ((phase / (2 * math.pi)) % 1.0) - 1)
        elif shape == "square":
            out.append(1.0 if math.sin(phase) >= 0 else -1.0)
        else:
            out.append(math.sin(phase))
    return out


def noise(n: int, rng: random.Random, smooth: float = 0.0) -> list[float]:
    """White noise, optionally low-passed by a one-pole filter (smooth in 0..1)."""
    out, last = [], 0.0
    for _ in range(n):
        v = rng.uniform(-1, 1)
        last = last * smooth + v * (1 - smooth)
        out.append(last)
    return out


def mix(*tracks: tuple[float, list[float]]) -> list[float]:
    n = max(len(t) for _, t in tracks)
    out = [0.0] * n
    for gain, track in tracks:
        for i, v in enumerate(track):
            out[i] += gain * v
    return out


def times(a: list[float], b: list[float]) -> list[float]:
    return [x * y for x, y in zip(a, b)]


def write(name: str, samples: list[float], peak: float = 0.85) -> None:
    top = max(1e-9, max(abs(s) for s in samples))
    data = b"".join(struct.pack("<h", int(max(-1, min(1, s / top * peak)) * 32767)) for s in samples)
    with wave.open(str(OUT / name), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(data)


def n_of(seconds: float) -> int:
    return int(seconds * RATE)


def blaster(seed: int = 1) -> list[float]:
    rng = random.Random(seed)
    n = n_of(0.32)
    tone = sweep(n, 2400, 300, curve=0.45, shape="saw")
    crack = times(noise(n, rng), envelope(n, 0.001, 0.012))
    return mix((0.75, times(tone, envelope(n, 0.002, 0.09))), (0.6, crack))


def blaster_heavy(seed: int = 2) -> list[float]:
    rng = random.Random(seed)
    n = n_of(0.42)
    tone = sweep(n, 1500, 160, curve=0.5, shape="saw")
    body = sweep(n, 220, 70, curve=0.6)
    crack = times(noise(n, rng, 0.3), envelope(n, 0.001, 0.025))
    return mix((0.6, times(tone, envelope(n, 0.002, 0.12))), (0.5, times(body, envelope(n, 0.002, 0.15))),
               (0.7, crack))


def laser_cannon(seed: int = 3) -> list[float]:
    rng = random.Random(seed)
    n = n_of(0.3)
    a = sweep(n, 3000, 900, curve=0.4, shape="square")
    b = sweep(n, 3150, 950, curve=0.4, shape="square")
    env = envelope(n, 0.001, 0.07)
    return mix((0.35, times(a, env)), (0.35, times(b, env)),
               (0.3, times(noise(n, rng), envelope(n, 0.001, 0.01))))


def turbolaser(seed: int = 4) -> list[float]:
    rng = random.Random(seed)
    n = n_of(0.9)
    boom = sweep(n, 260, 40, curve=0.5, shape="saw")
    rumble = noise(n, rng, 0.96)
    return mix((0.7, times(boom, envelope(n, 0.005, 0.3))), (0.9, times(rumble, envelope(n, 0.003, 0.35))),
               (0.4, times(sweep(n, 1200, 200, 0.4, "saw"), envelope(n, 0.002, 0.08))))


def ion(seed: int = 5) -> list[float]:
    rng = random.Random(seed)
    n = n_of(0.55)
    buzz = sweep(n, 140, 90, shape="square")
    crackle = [v if rng.random() < 0.08 else v * 0.15 for v in noise(n, rng)]
    shimmer = sweep(n, 1800, 2600, shape="sine")
    env = envelope(n, 0.01, 0.2)
    return mix((0.45, times(buzz, env)), (0.6, times(crackle, env)), (0.2, times(shimmer, env)))


def torpedo(seed: int = 6) -> list[float]:
    rng = random.Random(seed)
    n = n_of(0.7)
    whoosh = noise(n, rng, 0.85)
    rise = sweep(n, 300, 900, curve=0.8, shape="sine")
    env = [min(1.0, i / n_of(0.15)) * math.exp(-max(0, i - n_of(0.3)) / n_of(0.18)) for i in range(n)]
    return mix((0.8, times(whoosh, env)), (0.35, times(rise, env)))


def explosion(seed: int = 7) -> list[float]:
    rng = random.Random(seed)
    n = n_of(1.0)
    blast = noise(n, rng, 0.9)
    thump = sweep(n, 120, 30, curve=0.4)
    return mix((1.0, times(blast, envelope(n, 0.002, 0.28))), (0.8, times(thump, envelope(n, 0.002, 0.2))))


def stun(seed: int = 8) -> list[float]:
    n = n_of(0.45)
    wobble = []
    phase = 0.0
    for i in range(n):
        f = 900 + 400 * math.sin(2 * math.pi * 28 * i / RATE)
        phase += 2 * math.pi * f / RATE
        wobble.append(math.sin(phase))
    return times(wobble, envelope(n, 0.005, 0.16))


def bowcaster(seed: int = 9) -> list[float]:
    rng = random.Random(seed)
    n = n_of(0.45)
    twang = times(sweep(n, 180, 150, shape="saw"), envelope(n, 0.001, 0.05))
    zap = times(sweep(n, 1700, 500, curve=0.5, shape="saw"), envelope(n, 0.004, 0.11))
    return mix((0.5, twang), (0.6, zap), (0.3, times(noise(n, rng), envelope(n, 0.001, 0.01))))


def lightsaber(seed: int = 10) -> list[float]:
    """Humming blade: two detuned low saws, swelling and dipping in pitch as it swings."""
    n = n_of(0.6)
    swing = [math.sin(math.pi * i / n) for i in range(n)]
    out = []
    p1 = p2 = 0.0
    for i in range(n):
        bend = 1.0 + 0.35 * swing[i]
        p1 += 2 * math.pi * 92 * bend / RATE
        p2 += 2 * math.pi * 97 * bend / RATE
        hum = 0.5 * (2 * ((p1 / (2 * math.pi)) % 1) - 1) + 0.5 * (2 * ((p2 / (2 * math.pi)) % 1) - 1)
        out.append(hum * (0.35 + 0.65 * swing[i]))
    rng = random.Random(seed)
    hiss = times(noise(n, rng, 0.6), swing)
    return mix((0.85, out), (0.15, hiss))


def force_lightning(seed: int = 11) -> list[float]:
    rng = random.Random(seed)
    n = n_of(0.8)
    crack = []
    burst = 0.0
    for _ in range(n):
        if rng.random() < 0.004:
            burst = 1.0
        burst *= 0.995
        crack.append(rng.uniform(-1, 1) * (0.25 + burst))
    hum = sweep(n, 120, 150, shape="square")
    env = envelope(n, 0.02, 0.35)
    return mix((0.9, times(crack, env)), (0.25, times(hum, env)))


def vibroblade(seed: int = 12) -> list[float]:
    rng = random.Random(seed)
    n = n_of(0.35)
    whine = sweep(n, 1600, 2200, shape="sine")
    swish = noise(n, rng, 0.5)
    shape = [math.sin(math.pi * i / n) for i in range(n)]
    return mix((0.4, times(whine, shape)), (0.7, times(swish, shape)))


SOUNDS = {
    "sw-blaster.wav": blaster,
    "sw-blaster-heavy.wav": blaster_heavy,
    "sw-laser-cannon.wav": laser_cannon,
    "sw-turbolaser.wav": turbolaser,
    "sw-ion.wav": ion,
    "sw-torpedo.wav": torpedo,
    "sw-explosion.wav": explosion,
    "sw-stun.wav": stun,
    "sw-bowcaster.wav": bowcaster,
    "sw-lightsaber.wav": lightsaber,
    "sw-force-lightning.wav": force_lightning,
    "sw-vibroblade.wav": vibroblade,
}


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    for name, make in SOUNDS.items():
        write(name, make())
    print(f"wrote {len(SOUNDS)} sound effects")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
