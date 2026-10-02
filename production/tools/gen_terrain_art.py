#!/usr/bin/env python3
"""Generate original procedural hex tiles for the add-on's custom terrains.

Outputs 72x72 hex-masked PNGs under ``images/terrain/sw/``. The art is drawn
entirely from code (random stars, polygon asteroids, plated decks) with a fixed
seed so results are reproducible. Requires Pillow.

Usage: python3 production/tools/gen_terrain_art.py
"""
from __future__ import annotations

import math
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "addons/Star_Wars_Thrawn_Trilogy/images/terrain/sw"
SIZE = 72
HEX = [(18, 0), (54, 0), (72, 36), (54, 72), (18, 72), (0, 36)]
SPACE_BG = (6, 8, 16, 255)


def hex_mask() -> Image.Image:
    mask = Image.new("L", (SIZE, SIZE), 0)
    ImageDraw.Draw(mask).polygon(HEX, fill=255)
    return mask


def finish(img: Image.Image) -> Image.Image:
    out = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    out.paste(img, (0, 0), hex_mask())
    return out


def starfield(rng: random.Random) -> Image.Image:
    img = Image.new("RGBA", (SIZE, SIZE), SPACE_BG)
    d = ImageDraw.Draw(img)
    for _ in range(rng.randint(10, 16)):
        x, y = rng.randrange(SIZE), rng.randrange(SIZE)
        b = rng.choice((90, 120, 160, 200, 240))
        tint = rng.choice(((0, 0, 0), (0, 10, 30), (30, 10, 0)))
        d.point((x, y), fill=(min(255, b + tint[0]), min(255, b + tint[1]), min(255, b + tint[2]), 255))
    if rng.random() < 0.5:
        x, y = rng.randrange(8, SIZE - 8), rng.randrange(8, SIZE - 8)
        d.point([(x, y), (x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)], fill=(220, 225, 255, 255))
    return img


def asteroid(d: ImageDraw.ImageDraw, rng: random.Random, cx: float, cy: float, r: float) -> None:
    points = []
    n = rng.randint(7, 11)
    for i in range(n):
        a = 2 * math.pi * i / n + rng.uniform(-0.2, 0.2)
        rr = r * rng.uniform(0.7, 1.15)
        points.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
    base = rng.choice(((92, 84, 74), (80, 78, 76), (98, 88, 70)))
    d.polygon(points, fill=base + (255,))
    # Light from the upper left: a lighter inner polygon offset toward it.
    hi = [(cx + (x - cx) * 0.6 - r * 0.15, cy + (y - cy) * 0.6 - r * 0.15) for x, y in points]
    d.polygon(hi, fill=tuple(min(255, c + 28) for c in base) + (255,))
    for _ in range(rng.randint(1, 3)):
        px, py = cx + rng.uniform(-r * 0.4, r * 0.4), cy + rng.uniform(-r * 0.4, r * 0.4)
        cr = r * rng.uniform(0.12, 0.22)
        d.ellipse((px - cr, py - cr, px + cr, py + cr), fill=tuple(max(0, c - 30) for c in base) + (255,))


def asteroid_tile(rng: random.Random) -> Image.Image:
    img = starfield(rng)
    d = ImageDraw.Draw(img)
    for _ in range(rng.randint(2, 4)):
        asteroid(d, rng, rng.uniform(16, 56), rng.uniform(14, 58), rng.uniform(6, 15))
    return img


def plating(rng: random.Random, base=(72, 76, 84), stripe=None) -> Image.Image:
    img = Image.new("RGBA", (SIZE, SIZE), base + (255,))
    d = ImageDraw.Draw(img)
    for x in range(0, SIZE, 12):
        d.line([(x, 0), (x, SIZE)], fill=tuple(max(0, c - 18) for c in base) + (255,))
    for y in range(0, SIZE, 12):
        d.line([(0, y), (SIZE, y)], fill=tuple(max(0, c - 18) for c in base) + (255,))
    for _ in range(14):
        x, y = rng.randrange(0, SIZE, 12) + 6, rng.randrange(0, SIZE, 12) + 6
        d.point((x, y), fill=tuple(min(255, c + 30) for c in base) + (255,))
    if stripe:
        for i in range(-SIZE, SIZE, 14):
            d.polygon([(i, 60), (i + 7, 60), (i + 19, 72), (i + 12, 72)], fill=stripe + (255,))
    return img.filter(ImageFilter.SMOOTH)


def hangar_tile(rng: random.Random) -> Image.Image:
    img = plating(rng, base=(60, 64, 72), stripe=(176, 140, 40))
    d = ImageDraw.Draw(img)
    d.rectangle((22, 18, 50, 46), outline=(150, 160, 175, 255), width=2)
    d.line([(26, 32), (46, 32)], fill=(120, 190, 255, 255), width=2)
    return img


MISC = ROOT / "addons/Star_Wars_Thrawn_Trilogy/images/misc"


def zone_tint() -> Image.Image:
    """Translucent violet hex marking a ysalamiri Force-null bubble."""
    img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.polygon(HEX, fill=(120, 60, 170, 46))
    inset = [(20, 3), (52, 3), (69, 36), (52, 69), (20, 69), (3, 36)]
    for a, b in zip(inset, inset[1:] + inset[:1]):
        for t in range(0, 10, 2):
            x1 = a[0] + (b[0] - a[0]) * t / 10
            y1 = a[1] + (b[1] - a[1]) * t / 10
            x2 = a[0] + (b[0] - a[0]) * (t + 1) / 10
            y2 = a[1] + (b[1] - a[1]) * (t + 1) / 10
            d.line([(x1, y1), (x2, y2)], fill=(170, 110, 220, 150), width=1)
    return img


def ysalamiri_icon() -> Image.Image:
    """A small salamander-like creature clinging to a curved branch."""
    img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.arc((14, 30, 62, 70), 200, 340, fill=(96, 66, 40, 255), width=5)
    body = [(30, 36), (36, 31), (44, 30), (51, 33), (54, 37), (48, 38), (41, 37), (34, 40)]
    d.polygon(body, fill=(150, 168, 96, 255), outline=(70, 86, 40, 255))
    d.line([(30, 36), (22, 40), (18, 46)], fill=(150, 168, 96, 255), width=3)
    for lx, ly in ((36, 39), (46, 38), (40, 32), (50, 34)):
        d.line([(lx, ly), (lx + 2, ly + 5)], fill=(90, 104, 50, 255), width=2)
    d.ellipse((50, 32, 53, 35), fill=(20, 20, 20, 255))
    return img


def frame_badge() -> Image.Image:
    """Overlay badge for a unit carrying a ysalamiri nutrient frame."""
    img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rectangle((50, 4, 66, 20), fill=(30, 30, 36, 220), outline=(200, 200, 210, 255))
    for x in (54, 58, 62):
        d.line([(x, 5), (x, 19)], fill=(200, 200, 210, 255))
    d.ellipse((53, 9, 63, 15), fill=(150, 168, 96, 255))
    return img


def objective_marker() -> Image.Image:
    """Pulsing-style ring marking a mission objective hex."""
    img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse((14, 22, 58, 50), outline=(255, 210, 60, 230), width=3)
    d.ellipse((24, 28, 48, 44), outline=(255, 240, 150, 160), width=2)
    return img


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    rng = random.Random(1977)
    outputs = {}
    for i, suffix in enumerate(("", "2", "3", "4")):
        outputs[f"space{suffix}.png"] = starfield(rng)
        outputs[f"asteroids{suffix}.png"] = asteroid_tile(rng)
        outputs[f"deck{suffix}.png"] = plating(rng)
    outputs["hangar.png"] = hangar_tile(rng)
    for name, img in outputs.items():
        finish(img).save(OUT / name, optimize=True)
    MISC.mkdir(parents=True, exist_ok=True)
    misc = {
        "sw-ysalamiri-zone.png": zone_tint(),
        "sw-ysalamiri.png": ysalamiri_icon(),
        "sw-frame-carried.png": frame_badge(),
        "sw-objective.png": objective_marker(),
    }
    for name, img in misc.items():
        img.save(MISC / name, optimize=True)
    print(f"wrote {len(outputs)} tiles to {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
