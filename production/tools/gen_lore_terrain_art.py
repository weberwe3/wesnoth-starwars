#!/usr/bin/env python3
"""Paint lore-accurate hex tiles that replace medieval mainline terrain.

Phase 1 (2026-10-02): starship and building interiors, and the keeps and
castles every mission uses. The art is original and drawn entirely from code,
with fixed seeds so it is reproducible.

  sw/interior-deck     durasteel deck plating, the floor of Karrde's base,
                       Nomad City, the Smugglers' council hall, Mount Tantiss,
                       the Imperial Palace and starship interiors
  sw/bulkhead          durasteel bulkhead wall (replaces stone walls)
  sw/throne-floor      polished black stone of the Mount Tantiss throne room
  sw/bunker-keep       duracrete command bunker seen from above (keeps)
  sw/bunker            duracrete pad with blast barriers (castles)
  sw/landing-pad-keep  circular shuttle landing pad (encampment keeps)
  sw/landing-pad       landing apron plates with guide lights (encampments)

Tiles are 72x72 flat-top hexes. Plate seams sit on an 18 px grid, which
divides the map's 54 px column step, 72 px row step and 36 px odd-column
offset, so plating continues seamlessly from hex to hex.

Usage: python3 production/tools/gen_lore_terrain_art.py
Requires Pillow.
"""
from __future__ import annotations

import math
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "addons/Star_Wars_Thrawn_Trilogy/images/terrain/sw"
SIZE = 72
S = 4  # supersampling factor
BIG = SIZE * S
HEX = [(18, 0), (54, 0), (72, 36), (54, 72), (18, 72), (0, 36)]


def hex_mask() -> Image.Image:
    mask = Image.new("L", (BIG, BIG), 0)
    ImageDraw.Draw(mask).polygon([(x * S, y * S) for x, y in HEX], fill=255)
    return mask


def finish(img: Image.Image) -> Image.Image:
    out = Image.new("RGBA", (BIG, BIG), (0, 0, 0, 0))
    out.paste(img, (0, 0), hex_mask())
    return out.resize((SIZE, SIZE), Image.LANCZOS)


def noise(rng: random.Random, base: tuple[int, int, int], amount: int, grain: int = 3) -> Image.Image:
    """Fine surface grain: random value noise, blurred, around a base colour."""
    small = Image.new("RGB", (BIG // grain, BIG // grain))
    small.putdata([tuple(max(0, min(255, c + rng.randint(-amount, amount))) for c in base)
                   for _ in range((BIG // grain) ** 2)])
    # RGB on purpose: ImageDraw blends translucent fills only into an RGB image.
    # On RGBA it overwrites alpha, which would punch see-through holes in a tile.
    return small.resize((BIG, BIG), Image.BICUBIC).filter(ImageFilter.GaussianBlur(S * 0.6))


def composite(img: Image.Image, layer: Image.Image) -> None:
    """Blend an RGBA light/glow layer onto the RGB working tile in place."""
    img.paste(Image.alpha_composite(img.convert("RGBA"), layer).convert("RGB"))


def shade(c: tuple[int, int, int], f: float) -> tuple[int, int, int]:
    return tuple(max(0, min(255, int(v * f))) for v in c)


def plates(img: Image.Image, base: tuple[int, int, int], rng: random.Random, cell: int = 18) -> None:
    """Deck plates on the global 18 px grid: dark seams, lit top-left bevels, rivets."""
    d = ImageDraw.Draw(img, "RGBA")
    step = cell * S
    for gx in range(0, BIG, step):
        for gy in range(0, BIG, step):
            tone = rng.uniform(0.9, 1.08)
            d.rectangle((gx + S, gy + S, gx + step - S, gy + step - S), fill=shade(base, tone) + (90,))
            d.line([(gx + S, gy + S), (gx + step - S, gy + S)], fill=(255, 255, 255, 34), width=S)
            d.line([(gx + S, gy + S), (gx + S, gy + step - S)], fill=(255, 255, 255, 24), width=S)
            for rx, ry in ((gx + 3 * S, gy + 3 * S), (gx + step - 3 * S, gy + 3 * S),
                           (gx + 3 * S, gy + step - 3 * S), (gx + step - 3 * S, gy + step - 3 * S)):
                d.ellipse((rx - S, ry - S, rx + S, ry + S), fill=(30, 32, 36, 200))
                d.ellipse((rx - S, ry - S, rx, ry), fill=(170, 175, 180, 120))
        d.line([(gx, 0), (gx, BIG)], fill=(14, 15, 18, 230), width=S)
    for gy in range(0, BIG, step):
        d.line([(0, gy), (BIG, gy)], fill=(14, 15, 18, 230), width=S)


def scuffs(img: Image.Image, rng: random.Random, count: int) -> None:
    d = ImageDraw.Draw(img, "RGBA")
    for _ in range(count):
        x, y = rng.randrange(BIG), rng.randrange(BIG)
        length = rng.randint(6, 18) * S
        angle = rng.uniform(0, math.pi)
        d.line([(x, y), (x + length * math.cos(angle), y + length * math.sin(angle))],
               fill=(0, 0, 0, rng.randint(8, 18)), width=S)


# --- interiors -----------------------------------------------------------------

def interior_deck(seed: int = 101) -> Image.Image:
    rng = random.Random(seed)
    base = (66, 70, 78)
    img = noise(rng, base, 10)
    plates(img, base, rng)
    d = ImageDraw.Draw(img, "RGBA")
    # A recessed floor grate with a cool lighting strip under it.
    gx, gy = 36 * S, 18 * S
    d.rectangle((gx + S, gy + 2 * S, gx + 18 * S - S, gy + 16 * S), fill=(24, 26, 30, 255))
    for i in range(3, 16, 3):
        d.line([(gx + 2 * S, gy + i * S), (gx + 17 * S - 2 * S, gy + i * S)], fill=(80, 84, 92, 255), width=S)
    glow = Image.new("L", (BIG, BIG), 0)
    ImageDraw.Draw(glow).rectangle((gx + 3 * S, gy + 8 * S, gx + 15 * S, gy + 10 * S), fill=200)
    light = Image.new("RGBA", (BIG, BIG), (150, 200, 255, 0))
    light.putalpha(glow.filter(ImageFilter.GaussianBlur(S * 2)))
    composite(img, light)
    scuffs(img, rng, 10)
    return finish(img)


def bulkhead(seed: int = 102) -> Image.Image:
    """Durasteel bulkhead: raised armour panels, a recessed light band, heavy shadow."""
    rng = random.Random(seed)
    base = (44, 47, 54)
    img = noise(rng, base, 7)
    d = ImageDraw.Draw(img, "RGBA")
    for gy in range(0, BIG, 18 * S):
        for gx in range(0, BIG, 18 * S):
            x0, y0, x1, y1 = gx + 2 * S, gy + 2 * S, gx + 16 * S, gy + 16 * S
            d.rectangle((x0, y0, x1, y1), fill=shade(base, rng.uniform(1.05, 1.2)) + (255,))
            d.line([(x0, y0), (x1, y0)], fill=(150, 156, 168, 160), width=S)  # lit top edge
            d.line([(x0, y0), (x0, y1)], fill=(120, 126, 138, 120), width=S)
            d.line([(x0, y1), (x1, y1)], fill=(10, 11, 14, 230), width=S)     # shadowed bottom
            d.line([(x1, y0), (x1, y1)], fill=(14, 15, 18, 200), width=S)
    # Recessed lighting band across the middle of each 36 px row.
    for gy in range(17 * S, BIG, 36 * S):
        band = Image.new("L", (BIG, BIG), 0)
        ImageDraw.Draw(band).rectangle((0, gy, BIG, gy + 2 * S), fill=220)
        light = Image.new("RGBA", (BIG, BIG), (190, 220, 255, 0))
        light.putalpha(band.filter(ImageFilter.GaussianBlur(S * 1.5)))
        composite(img, light)
    return finish(img)


def throne_floor(seed: int = 103) -> Image.Image:
    """Polished black stone in large slabs with a cold reflected sheen."""
    rng = random.Random(seed)
    base = (26, 25, 30)
    img = noise(rng, base, 5)
    d = ImageDraw.Draw(img, "RGBA")
    for g in range(0, BIG, 36 * S):
        d.line([(g, 0), (g, BIG)], fill=(70, 68, 80, 140), width=S)
        d.line([(0, g), (BIG, g)], fill=(70, 68, 80, 140), width=S)
    sheen = Image.new("L", (BIG, BIG), 0)
    ImageDraw.Draw(sheen).polygon([(10 * S, 0), (30 * S, 0), (62 * S, BIG), (42 * S, BIG)], fill=28)
    light = Image.new("RGBA", (BIG, BIG), (150, 140, 190, 0))
    light.putalpha(sheen.filter(ImageFilter.GaussianBlur(S * 6)))
    composite(img, light)
    return finish(img)


# --- keeps and castles -----------------------------------------------------------

DURACRETE = (150, 146, 136)


def bunker(seed: int = 104) -> Image.Image:
    """Duracrete apron with low blast barriers at two edges (castle hexes)."""
    rng = random.Random(seed)
    img = noise(rng, DURACRETE, 9)
    d = ImageDraw.Draw(img, "RGBA")
    for g in range(0, BIG, 18 * S):
        d.line([(g, 0), (g, BIG)], fill=(100, 96, 88, 150), width=S)
        d.line([(0, g), (BIG, g)], fill=(100, 96, 88, 150), width=S)
    for x0, y0, x1, y1 in ((20 * S, 4 * S, 52 * S, 11 * S), (20 * S, 61 * S, 52 * S, 68 * S)):
        d.rectangle((x0, y0 + 2 * S, x1, y1 + 2 * S), fill=(0, 0, 0, 70))       # cast shadow
        d.rectangle((x0, y0, x1, y1), fill=(172, 168, 158, 255))
        d.line([(x0, y0), (x1, y0)], fill=(215, 212, 204, 255), width=S)
        d.line([(x0, y1), (x1, y1)], fill=(100, 96, 88, 255), width=S)
    scuffs(img, rng, 14)
    return finish(img)


def bunker_keep(seed: int = 105) -> Image.Image:
    """Command bunker from above: octagonal duracrete roof, armoured hatch, vents."""
    rng = random.Random(seed)
    img = noise(rng, shade(DURACRETE, 0.85), 9)
    d = ImageDraw.Draw(img, "RGBA")
    c, r = BIG // 2, 27 * S
    octagon = [(c + r * math.cos(math.radians(22.5 + 45 * i)), c + r * math.sin(math.radians(22.5 + 45 * i)))
               for i in range(8)]
    d.polygon([(x + 3 * S, y + 4 * S) for x, y in octagon], fill=(0, 0, 0, 90))
    d.polygon(octagon, fill=(178, 174, 164, 255))
    inner = [(c + (r - 6 * S) * math.cos(math.radians(22.5 + 45 * i)),
              c + (r - 6 * S) * math.sin(math.radians(22.5 + 45 * i))) for i in range(8)]
    d.polygon(inner, fill=(160, 156, 146, 255))
    for (x0, y0), (x1, y1) in zip(octagon, octagon[1:] + octagon[:1]):
        tone = (220, 216, 206, 255) if y0 + y1 < 2 * c else (110, 106, 98, 255)
        d.line([(x0, y0), (x1, y1)], fill=tone, width=S)
    d.ellipse((c - 8 * S, c - 8 * S, c + 8 * S, c + 8 * S), fill=(70, 72, 78, 255))
    d.ellipse((c - 6 * S, c - 6 * S, c + 6 * S, c + 6 * S), fill=(96, 98, 106, 255))
    d.line([(c - 6 * S, c), (c + 6 * S, c)], fill=(50, 52, 58, 255), width=S)
    for angle in (45, 135, 225, 315):
        vx = c + 17 * S * math.cos(math.radians(angle))
        vy = c + 17 * S * math.sin(math.radians(angle))
        d.rectangle((vx - 3 * S, vy - 2 * S, vx + 3 * S, vy + 2 * S), fill=(60, 62, 66, 255))
        for k in range(-1, 2):
            d.line([(vx - 2 * S, vy + k * S), (vx + 2 * S, vy + k * S)], fill=(30, 31, 34, 255), width=S // 2)
    # Small red status lamp beside the hatch.
    glow = Image.new("L", (BIG, BIG), 0)
    ImageDraw.Draw(glow).ellipse((c + 9 * S, c - 11 * S, c + 12 * S, c - 8 * S), fill=255)
    lamp = Image.new("RGBA", (BIG, BIG), (255, 60, 40, 0))
    lamp.putalpha(glow.filter(ImageFilter.GaussianBlur(S)))
    composite(img, lamp)
    return finish(img)


def landing_pad(seed: int = 106) -> Image.Image:
    """Landing apron: dark composite plates, painted guide lines, inset lights."""
    rng = random.Random(seed)
    base = (78, 80, 84)
    img = noise(rng, base, 8)
    plates(img, base, rng, cell=36)
    d = ImageDraw.Draw(img, "RGBA")
    for x in (18 * S, 54 * S):
        d.line([(x, 0), (x, BIG)], fill=(214, 176, 60, 170), width=2 * S)
    lights = Image.new("L", (BIG, BIG), 0)
    ld = ImageDraw.Draw(lights)
    for x in (18 * S, 54 * S):
        for y in range(9 * S, BIG, 18 * S):
            ld.ellipse((x - 2 * S, y - 2 * S, x + 2 * S, y + 2 * S), fill=255)
    glow = Image.new("RGBA", (BIG, BIG), (255, 230, 150, 0))
    glow.putalpha(lights.filter(ImageFilter.GaussianBlur(S * 1.5)))
    composite(img, glow)
    scuffs(img, rng, 12)
    return finish(img)


def landing_pad_keep(seed: int = 107) -> Image.Image:
    """Circular shuttle landing pad with ring markings and a ring of lights."""
    rng = random.Random(seed)
    img = noise(rng, (70, 72, 76), 8)
    d = ImageDraw.Draw(img, "RGBA")
    c = BIG // 2
    for r, fill in ((32 * S, (52, 54, 58, 255)), (30 * S, (88, 90, 96, 255))):
        d.ellipse((c - r, c - r, c + r, c + r), fill=fill)
    d.ellipse((c - 24 * S, c - 24 * S, c + 24 * S, c + 24 * S), outline=(214, 176, 60, 230), width=2 * S)
    d.ellipse((c - 10 * S, c - 10 * S, c + 10 * S, c + 10 * S), outline=(225, 225, 225, 200), width=S)
    for angle in range(0, 360, 90):
        a = math.radians(angle)
        d.line([(c + 12 * S * math.cos(a), c + 12 * S * math.sin(a)),
                (c + 22 * S * math.cos(a), c + 22 * S * math.sin(a))], fill=(225, 225, 225, 200), width=S)
    lights = Image.new("L", (BIG, BIG), 0)
    ld = ImageDraw.Draw(lights)
    for angle in range(0, 360, 30):
        a = math.radians(angle)
        x, y = c + 28 * S * math.cos(a), c + 28 * S * math.sin(a)
        ld.ellipse((x - 1.5 * S, y - 1.5 * S, x + 1.5 * S, y + 1.5 * S), fill=255)
    glow = Image.new("RGBA", (BIG, BIG), (255, 220, 140, 0))
    glow.putalpha(lights.filter(ImageFilter.GaussianBlur(S * 1.2)))
    composite(img, glow)
    scuffs(img, rng, 8)
    return finish(img)


TILES = {
    "interior-deck": interior_deck,
    "bulkhead": bulkhead,
    "throne-floor": throne_floor,
    "bunker": bunker,
    "bunker-keep": bunker_keep,
    "landing-pad": landing_pad,
    "landing-pad-keep": landing_pad_keep,
}


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    for name, paint in TILES.items():
        paint().save(OUT / f"{name}.png", optimize=True)
    print(f"wrote {len(TILES)} tiles to {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
