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


def write(name: str, samples: list[float], peak: float = 0.85) -> None:  # noqa: D401
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




# --- impacts: hit and miss for every weapon family --------------------------------

def sizzle(n: int, rng: random.Random, tone: float, decay: float) -> list[float]:
    """Energy bolt striking a target: crack, bright fizz, falling tone."""
    crack = times(noise(n, rng), envelope(n, 0.0005, 0.01))
    fizz = times(noise(n, rng, 0.2), envelope(n, 0.002, decay))
    body = times(sweep(n, tone, tone * 0.4, 0.5, "saw"), envelope(n, 0.001, decay * 0.6))
    return mix((0.8, crack), (0.5, fizz), (0.35, body))


def flyby(n: int, rng: random.Random, f0: float, f1: float) -> list[float]:
    """A shot passing close by: Doppler-falling tone that swells and fades."""
    swell = [math.sin(math.pi * i / n) ** 2 for i in range(n)]
    tone = sweep(n, f0, f1, 1.0, "saw")
    air = noise(n, rng, 0.7)
    return times(mix((0.5, tone), (0.3, air)), swell)


def blaster_hit(seed: int = 21) -> list[float]:
    return sizzle(n_of(0.35), random.Random(seed), 900, 0.09)


def blaster_miss(seed: int = 22) -> list[float]:
    return flyby(n_of(0.3), random.Random(seed), 2200, 700)


def heavy_hit(seed: int = 23) -> list[float]:
    rng = random.Random(seed)
    n = n_of(0.5)
    thump = times(sweep(n, 160, 50, 0.4), envelope(n, 0.001, 0.12))
    return mix((1.0, sizzle(n, rng, 500, 0.14)), (0.8, thump))


def heavy_miss(seed: int = 24) -> list[float]:
    return flyby(n_of(0.4), random.Random(seed), 1300, 380)


def laser_hit(seed: int = 25) -> list[float]:
    """Starfighter laser striking a hull: metallic ping and spark spray."""
    rng = random.Random(seed)
    n = n_of(0.45)
    ping = times(mix((0.5, sine(n, 1900)), (0.3, sine(n, 2870)), (0.2, sine(n, 4100))), envelope(n, 0.001, 0.08))
    sparks = [v if rng.random() < 0.05 else 0.0 for v in noise(n, rng)]
    return mix((0.7, ping), (0.8, times(sparks, envelope(n, 0.002, 0.15))), (0.6, sizzle(n, rng, 1500, 0.05)))


def laser_miss(seed: int = 26) -> list[float]:
    return flyby(n_of(0.25), random.Random(seed), 3200, 1100)


def turbolaser_hit(seed: int = 27) -> list[float]:
    rng = random.Random(seed)
    n = n_of(1.2)
    return mix((1.0, explosion_body(n, rng, 0.35)), (0.5, times(sweep(n, 600, 80, 0.4, "saw"), envelope(n, 0.002, 0.1))))


def turbolaser_miss(seed: int = 28) -> list[float]:
    return flyby(n_of(0.7), random.Random(seed), 420, 110)


def ion_hit(seed: int = 29) -> list[float]:
    """Systems shorting out: dense crackle with a dying whine."""
    rng = random.Random(seed)
    n = n_of(0.7)
    crackle = [v * (1.0 if rng.random() < 0.15 else 0.2) for v in noise(n, rng)]
    whine = sweep(n, 1400, 200, 0.6, "square")
    return mix((0.8, times(crackle, envelope(n, 0.002, 0.25))), (0.25, times(whine, envelope(n, 0.01, 0.3))))


def ion_miss(seed: int = 30) -> list[float]:
    rng = random.Random(seed)
    n = n_of(0.45)
    return times(mix((0.5, sweep(n, 160, 120, shape="square")), (0.4, noise(n, rng))),
                 [math.sin(math.pi * i / n) for i in range(n)])


def explosion_body(n: int, rng: random.Random, decay: float) -> list[float]:
    blast = times(noise(n, rng, 0.88), envelope(n, 0.002, decay))
    thump = times(sweep(n, 110, 28, 0.4), envelope(n, 0.002, decay * 0.7))
    debris = [v if rng.random() < 0.02 else 0.0 for v in noise(n, rng)]
    return mix((1.0, blast), (0.9, thump), (0.4, times(debris, envelope(n, 0.05, decay * 1.5))))


def torpedo_hit(seed: int = 31) -> list[float]:
    return explosion_body(n_of(1.1), random.Random(seed), 0.3)


def torpedo_miss(seed: int = 32) -> list[float]:
    return flyby(n_of(0.6), random.Random(seed), 700, 260)


def bomb_miss(seed: int = 33) -> list[float]:
    """A blast that lands wide: muffled, distant thud."""
    rng = random.Random(seed)
    n = n_of(0.8)
    return [v * 0.5 for v in lowpass_list(explosion_body(n, rng, 0.2), 0.95)]


def lowpass_list(x: list[float], smooth: float) -> list[float]:
    out, last = [], 0.0
    for v in x:
        last = last * smooth + v * (1 - smooth)
        out.append(last)
    return out


def stun_hit(seed: int = 34) -> list[float]:
    rng = random.Random(seed)
    n = n_of(0.5)
    zap = times(noise(n, rng), envelope(n, 0.001, 0.02))
    buzz = times(sweep(n, 220, 180, shape="square"), envelope(n, 0.01, 0.2))
    return mix((0.6, zap), (0.5, buzz), (0.4, stun(seed)))


def stun_miss(seed: int = 35) -> list[float]:
    s = stun(seed)
    return [v * (1 - i / len(s)) for i, v in enumerate(s)]


def bowcaster_hit(seed: int = 36) -> list[float]:
    rng = random.Random(seed)
    n = n_of(0.45)
    punch = times(sweep(n, 200, 60, 0.4), envelope(n, 0.001, 0.07))
    return mix((0.9, sizzle(n, rng, 700, 0.1)), (0.8, punch))


def bowcaster_miss(seed: int = 37) -> list[float]:
    return flyby(n_of(0.35), random.Random(seed), 1700, 520)


def lightning_hit(seed: int = 38) -> list[float]:
    """Force lightning engulfing a target: louder, denser crackle and a body buzz."""
    rng = random.Random(seed)
    n = n_of(0.7)
    crack = [rng.uniform(-1, 1) * (1.0 if rng.random() < 0.3 else 0.3) for _ in range(n)]
    hum = sweep(n, 90, 110, shape="square")
    env = envelope(n, 0.01, 0.25)
    return mix((1.0, times(crack, env)), (0.4, times(hum, env)))


def lightning_miss(seed: int = 39) -> list[float]:
    s = force_lightning(seed)
    return [v * 0.6 * (1 - i / len(s)) for i, v in enumerate(s)]


def saber_clash(seed: int = 40) -> list[float]:
    """Lightsaber striking: crackling clash over the blade's hum."""
    rng = random.Random(seed)
    n = n_of(0.55)
    hum = lightsaber(seed)[:n]
    clash = times(noise(n, rng, 0.1), envelope(n, 0.001, 0.08))
    zap = times(sweep(n, 2600, 900, 0.5, "saw"), envelope(n, 0.001, 0.06))
    return mix((0.6, hum), (0.9, clash), (0.5, zap))


def deflect_hit(seed: int = 41) -> list[float]:
    """A bolt turned back by a blade: saber clash then the bolt's ricochet zip."""
    clash = saber_clash(seed)
    zip_ = flyby(n_of(0.3), random.Random(seed + 1), 2400, 900)
    return clash + [0.8 * v for v in zip_]


def vibro_hit(seed: int = 42) -> list[float]:
    """Vibroblade biting through armour: whine plus a metallic scrape."""
    rng = random.Random(seed)
    n = n_of(0.4)
    whine = times(sweep(n, 2100, 1500), envelope(n, 0.005, 0.15))
    scrape = times(noise(n, rng, 0.3), envelope(n, 0.002, 0.08))
    ring = times(mix((0.5, sine(n, 1250)), (0.3, sine(n, 3300))), envelope(n, 0.001, 0.12))
    return mix((0.5, whine), (0.7, scrape), (0.6, ring))


def sine(n: int, f: float) -> list[float]:
    return [math.sin(2 * math.pi * f * i / RATE) for i in range(n)]


# --- creatures and deaths -------------------------------------------------------

def growl(n: int, rng: random.Random, f0: float, f1: float, rough: float) -> list[float]:
    """Formant-like creature voice: buzzy pulse train through two resonances."""
    out, phase = [], 0.0
    for i in range(n):
        f = f0 + (f1 - f0) * i / n
        phase += 2 * math.pi * f / RATE
        pulse = (1 if math.sin(phase) > 0.6 else -0.3) + rough * rng.uniform(-1, 1)
        out.append(pulse)
    a = lowpass_list(out, 0.80)
    b = lowpass_list(out, 0.55)
    return mix((0.6, a), (0.4, [x - y for x, y in zip(b, a)]))


def wookiee_roar(seed: int = 43) -> list[float]:
    rng = random.Random(seed)
    n = n_of(0.9)
    shape = [min(1.0, i / n_of(0.08)) * (1 - (i / n) ** 2) for i in range(n)]
    return times(growl(n, rng, 120, 95, 0.35), shape)


def vornskr_snarl(seed: int = 44) -> list[float]:
    rng = random.Random(seed)
    n = n_of(0.5)
    shape = envelope(n, 0.01, 0.2)
    return times(growl(n, rng, 260, 180, 0.6), shape)


def death_armor(seed: int = 45) -> list[float]:
    """Armoured trooper falling: plastoid clatter and a heavy thud."""
    rng = random.Random(seed)
    n = n_of(0.6)
    thud = times(sweep(n, 120, 50, 0.5), envelope(n, 0.001, 0.09))
    out = mix((0.9, thud))
    for start in (0.0, 0.07, 0.15, 0.24):
        k = n_of(start)
        click = times(mix((0.5, sine(n_of(0.05), 1900 + rng.randint(-300, 300))), (0.5, noise(n_of(0.05), rng))),
                      envelope(n_of(0.05), 0.0005, 0.01))
        for i, v in enumerate(click):
            if k + i < n:
                out[k + i] += 0.6 * v
    return out


def death_soft(seed: int = 46) -> list[float]:
    rng = random.Random(seed)
    n = n_of(0.5)
    thud = times(sweep(n, 100, 45, 0.5), envelope(n, 0.001, 0.08))
    cloth = times(noise(n, rng, 0.6), envelope(n, 0.01, 0.12))
    return mix((1.0, thud), (0.4, cloth))


def death_beast(seed: int = 47) -> list[float]:
    rng = random.Random(seed)
    n = n_of(0.6)
    yelp = times(growl(n, rng, 520, 240, 0.3), envelope(n, 0.005, 0.15))
    return mix((0.8, yelp), (0.6, death_soft(seed)[:n]))


def death_wookiee(seed: int = 48) -> list[float]:
    roar = wookiee_roar(seed)
    return [v * (1 - i / len(roar)) for i, v in enumerate(roar)] + death_soft(seed)[:n_of(0.3)]


def death_droid(seed: int = 49) -> list[float]:
    rng = random.Random(seed)
    n = n_of(0.7)
    sparks = [v if rng.random() < 0.08 else 0.0 for v in noise(n, rng)]
    powerdown = times(sweep(n, 900, 60, 0.6, "square"), envelope(n, 0.005, 0.3))
    return mix((0.6, times(sparks, envelope(n, 0.002, 0.25))), (0.4, powerdown),
               (0.6, explosion_body(n, rng, 0.12)))


def death_vehicle(seed: int = 50) -> list[float]:
    return explosion_body(n_of(1.0), random.Random(seed), 0.28)


def death_fighter(seed: int = 51) -> list[float]:
    rng = random.Random(seed)
    n = n_of(1.0)
    whine = times(sweep(n, 1600, 200, 0.4, "saw"), envelope(n, 0.005, 0.12))
    return mix((0.4, whine), (1.0, explosion_body(n, rng, 0.25)))


def death_capital(seed: int = 52) -> list[float]:
    rng = random.Random(seed)
    n = n_of(2.0)
    first = explosion_body(n, rng, 0.5)
    second = [0.0] * n_of(0.45) + explosion_body(n - n_of(0.45), random.Random(seed + 1), 0.6)
    return mix((0.9, first), (1.0, second))


def death_glass(seed: int = 53) -> list[float]:
    """Cloning cylinder shattering: glassy pings over a splash of fluid."""
    rng = random.Random(seed)
    n = n_of(0.9)
    out = times(noise(n, rng, 0.5), envelope(n, 0.001, 0.3))
    out = [0.5 * v for v in out]
    for _ in range(14):
        k = rng.randint(0, n_of(0.4))
        f = rng.uniform(2500, 6000)
        m = n_of(0.12)
        ping = times(sine(m, f), envelope(m, 0.0005, 0.03))
        for i, v in enumerate(ping):
            if k + i < n:
                out[k + i] += 0.4 * v
    return out


def death_rock(seed: int = 54) -> list[float]:
    rng = random.Random(seed)
    n = n_of(0.9)
    grind = times(noise(n, rng, 0.93), envelope(n, 0.005, 0.35))
    knocks = [v if rng.random() < 0.01 else 0.0 for v in noise(n, rng, 0.5)]
    return mix((1.0, grind), (0.8, times(knocks, envelope(n, 0.01, 0.4))))


# --- movement (kept quiet: it plays on every hex step) ------------------------------

def move_fighter(seed: int = 55) -> list[float]:
    rng = random.Random(seed)
    n = n_of(0.3)
    swell = [math.sin(math.pi * i / n) for i in range(n)]
    return times(mix((0.6, sweep(n, 520, 440, shape="saw")), (0.4, noise(n, rng, 0.8))), swell)


def move_capital(seed: int = 56) -> list[float]:
    rng = random.Random(seed)
    n = n_of(0.6)
    swell = [math.sin(math.pi * i / n) for i in range(n)]
    return times(mix((0.6, sweep(n, 55, 52)), (0.5, noise(n, rng, 0.97))), swell)


def move_speeder(seed: int = 57) -> list[float]:
    n = n_of(0.25)
    swell = [math.sin(math.pi * i / n) for i in range(n)]
    return times(mix((0.6, sweep(n, 330, 300, shape="square")), (0.4, sweep(n, 660, 600))), swell)


def move_walker(seed: int = 58) -> list[float]:
    rng = random.Random(seed)
    n = n_of(0.35)
    stomp = times(sweep(n, 90, 40, 0.4), envelope(n, 0.001, 0.07))
    servo = times(sweep(n, 700, 900, shape="square"), envelope(n, 0.02, 0.06))
    return mix((1.0, stomp), (0.15, servo), (0.3, times(noise(n, rng, 0.6), envelope(n, 0.001, 0.03))))


# --- objectives ----------------------------------------------------------------------

def pickup_chime(seed: int = 59) -> list[float]:
    n = n_of(0.5)
    a = times(sine(n, 880), envelope(n, 0.002, 0.18))
    b = [0.0] * n_of(0.09) + times(sine(n - n_of(0.09), 1320), envelope(n - n_of(0.09), 0.002, 0.2))
    return mix((0.6, a), (0.6, b))


def objective_chime(seed: int = 60) -> list[float]:
    n = n_of(0.8)
    notes = [(0.0, 660), (0.12, 880), (0.24, 1320)]
    out = [0.0] * n
    for start, f in notes:
        k = n_of(start)
        m = n - k
        tone = times(mix((0.7, sine(m, f)), (0.3, sine(m, f * 2))), envelope(m, 0.002, 0.25))
        for i, v in enumerate(tone):
            out[k + i] += 0.5 * v
    return out

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
    "sw-blaster-hit.wav": blaster_hit, "sw-blaster-miss.wav": blaster_miss,
    "sw-heavy-hit.wav": heavy_hit, "sw-heavy-miss.wav": heavy_miss,
    "sw-laser-hit.wav": laser_hit, "sw-laser-miss.wav": laser_miss,
    "sw-turbolaser-hit.wav": turbolaser_hit, "sw-turbolaser-miss.wav": turbolaser_miss,
    "sw-ion-hit.wav": ion_hit, "sw-ion-miss.wav": ion_miss,
    "sw-torpedo-hit.wav": torpedo_hit, "sw-torpedo-miss.wav": torpedo_miss,
    "sw-bomb-miss.wav": bomb_miss,
    "sw-stun-hit.wav": stun_hit, "sw-stun-miss.wav": stun_miss,
    "sw-bowcaster-hit.wav": bowcaster_hit, "sw-bowcaster-miss.wav": bowcaster_miss,
    "sw-lightning-hit.wav": lightning_hit, "sw-lightning-miss.wav": lightning_miss,
    "sw-saber-clash.wav": saber_clash, "sw-deflect.wav": deflect_hit, "sw-vibro-hit.wav": vibro_hit,
    "sw-wookiee-roar.wav": wookiee_roar, "sw-vornskr-snarl.wav": vornskr_snarl,
    "sw-death-armor.wav": death_armor, "sw-death-soft.wav": death_soft, "sw-death-beast.wav": death_beast,
    "sw-death-wookiee.wav": death_wookiee, "sw-death-droid.wav": death_droid,
    "sw-death-vehicle.wav": death_vehicle, "sw-death-fighter.wav": death_fighter,
    "sw-death-capital.wav": death_capital, "sw-death-glass.wav": death_glass, "sw-death-rock.wav": death_rock,
    "sw-move-fighter.wav": move_fighter, "sw-move-capital.wav": move_capital,
    "sw-move-speeder.wav": move_speeder, "sw-move-walker.wav": move_walker,
    "sw-pickup.wav": pickup_chime, "sw-objective.wav": objective_chime,
}
# Movement plays on every hex step, so it is mixed well below the weapons.
QUIET = {"sw-move-fighter.wav": 0.3, "sw-move-capital.wav": 0.35, "sw-move-speeder.wav": 0.28,
         "sw-move-walker.wav": 0.4, "sw-pickup.wav": 0.6, "sw-objective.wav": 0.6}


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    for name, make in SOUNDS.items():
        write(name, make(), QUIET.get(name, 0.85))
    print(f"wrote {len(SOUNDS)} sound effects")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
