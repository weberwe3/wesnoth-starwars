#!/usr/bin/env python3
"""Draw the original projectile sprites for ranged attacks.

Each projectile follows the mainline convention: a 72x72 image with the
object centred, drawn pointing north (``-n``) and north-east (``-ne``); the
engine rotates and mirrors them for the other directions.

Blaster bolts are a white-hot core inside a coloured glow, the way they read
on screen in the films. Colours follow the owner's rule (2026-10-02):
Imperial or evil red, New Republic green or blue, neutral orange or green,
except where film or Legends lore fixes a colour (see gen_hte_units.py).

Usage: python3 production/tools/gen_projectile_art.py [--check]
Requires Pillow.
"""
from __future__ import annotations

import argparse
import io
import math
import sys
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "addons/Star_Wars_Thrawn_Trilogy/images/projectiles"
SIZE = 72
SCALE = 4  # supersample, then reduce for smooth edges

BOLT_COLORS = {
    "red": (255, 40, 30),
    "green": (40, 255, 70),
    "blue": (60, 140, 255),
    "orange": (255, 140, 20),
}


def _canvas() -> Image.Image:
    return Image.new("RGBA", (SIZE * SCALE, SIZE * SCALE), (0, 0, 0, 0))


def _finish(img: Image.Image, diagonal: bool) -> Image.Image:
    if diagonal:
        img = img.rotate(-45, resample=Image.BICUBIC)
    return img.resize((SIZE, SIZE), Image.LANCZOS)


def _glow_line(length: int, width: int, color: tuple[int, int, int], core_width: int) -> Image.Image:
    """A vertical streak: soft coloured halo, saturated body, white-hot core."""
    img = _canvas()
    c = SIZE * SCALE // 2
    half = length * SCALE // 2
    halo = Image.new("L", img.size, 0)
    ImageDraw.Draw(halo).line([(c, c - half), (c, c + half)], fill=255, width=width * SCALE * 3)
    halo = halo.filter(ImageFilter.GaussianBlur(width * SCALE))
    body = Image.new("L", img.size, 0)
    ImageDraw.Draw(body).line([(c, c - half), (c, c + half)], fill=255, width=width * SCALE)
    body = body.filter(ImageFilter.GaussianBlur(SCALE))
    core = Image.new("L", img.size, 0)
    ImageDraw.Draw(core).line([(c, c - half + SCALE * 2), (c, c + half - SCALE * 2)], fill=255,
                              width=core_width * SCALE)
    core = core.filter(ImageFilter.GaussianBlur(SCALE * 0.6))
    for mask, rgb, strength in ((halo, color, 0.55), (body, color, 1.0), (core, (255, 255, 245), 1.0)):
        layer = Image.new("RGBA", img.size, rgb + (0,))
        layer.putalpha(mask.point(lambda a, s=strength: int(a * s)))
        img.alpha_composite(layer)
    return img


def bolt(color: tuple[int, int, int], diagonal: bool) -> Image.Image:
    return _finish(_glow_line(24, 3, color, 1), diagonal)


def heavy_bolt(color: tuple[int, int, int], diagonal: bool) -> Image.Image:
    """Turbolaser / cannon bolt: longer and thicker."""
    return _finish(_glow_line(34, 5, color, 2), diagonal)


def ion_bolt(diagonal: bool) -> Image.Image:
    """Ion cannon discharge: pale blue-white bolt wrapped in a crackling halo."""
    img = _glow_line(26, 5, (150, 200, 255), 2)
    crackle = Image.new("L", img.size, 0)
    d = ImageDraw.Draw(crackle)
    c = SIZE * SCALE // 2
    for i in range(-5, 6):
        y = c + i * 9 * SCALE // 2
        x = c + (12 if i % 2 else -12) * SCALE // 2
        d.line([(c, y), (x, y + 3 * SCALE)], fill=200, width=SCALE)
    layer = Image.new("RGBA", img.size, (200, 230, 255, 0))
    layer.putalpha(crackle.filter(ImageFilter.GaussianBlur(SCALE * 0.7)))
    img.alpha_composite(layer)
    return _finish(img, diagonal)


def glow_ball(core: tuple[int, int, int], halo: tuple[int, int, int], radius: int) -> Image.Image:
    img = _canvas()
    c = SIZE * SCALE // 2
    r = radius * SCALE
    for mask_r, blur, rgb, strength in ((r * 2.2, r, halo, 0.6), (r, SCALE * 1.5, halo, 1.0),
                                        (r * 0.45, SCALE, core, 1.0)):
        mask = Image.new("L", img.size, 0)
        ImageDraw.Draw(mask).ellipse((c - mask_r, c - mask_r, c + mask_r, c + mask_r), fill=255)
        mask = mask.filter(ImageFilter.GaussianBlur(blur))
        layer = Image.new("RGBA", img.size, rgb + (0,))
        layer.putalpha(mask.point(lambda a, s=strength: int(a * s)))
        img.alpha_composite(layer)
    return _finish(img, False)


def lightning(diagonal: bool, seed: int = 7) -> Image.Image:
    """Force lightning: a forked blue-white arc."""
    import random

    rng = random.Random(seed)
    img = _canvas()
    c = SIZE * SCALE // 2
    mask = Image.new("L", img.size, 0)
    d = ImageDraw.Draw(mask)
    for branch in range(3):
        x, y = c, c + 30 * SCALE // 2 * 2 // 2
        points = [(x, c + 15 * SCALE)]
        for step in range(8):
            y = c + 15 * SCALE - (step + 1) * 4 * SCALE
            x = c + rng.randint(-5, 5) * SCALE + (branch - 1) * step * SCALE // 2
            points.append((x, y))
        d.line(points, fill=255, width=SCALE * (2 if branch == 1 else 1))
    halo = mask.filter(ImageFilter.GaussianBlur(SCALE * 3))
    for m, rgb, s in ((halo, (120, 150, 255), 0.9), (mask.filter(ImageFilter.GaussianBlur(SCALE * 0.5)),
                                                     (235, 240, 255), 1.0)):
        layer = Image.new("RGBA", img.size, rgb + (0,))
        layer.putalpha(m.point(lambda a, s=s: int(min(255, a * s * 1.6))))
        img.alpha_composite(layer)
    return _finish(img, diagonal)


def stun_rings(diagonal: bool) -> Image.Image:
    """Stun setting: the expanding blue rings seen in the films."""
    img = _canvas()
    c = SIZE * SCALE // 2
    mask = Image.new("L", img.size, 0)
    d = ImageDraw.Draw(mask)
    for i, r in enumerate((9, 7, 5)):
        y = c - 8 * SCALE + i * 8 * SCALE
        d.ellipse((c - r * SCALE, y - 2 * SCALE, c + r * SCALE, y + 2 * SCALE), outline=255, width=SCALE)
    layer = Image.new("RGBA", img.size, (90, 170, 255, 0))
    layer.putalpha(mask.filter(ImageFilter.GaussianBlur(SCALE * 0.8)))
    img.alpha_composite(layer)
    return _finish(img, diagonal)


def bomb(diagonal: bool) -> Image.Image:
    """Concussion bomb or grenade: a dark casing with an orange fuse glow."""
    img = glow_ball((255, 230, 160), (255, 120, 20), 3).resize((SIZE * SCALE, SIZE * SCALE))
    shell = Image.new("L", img.size, 0)
    c = SIZE * SCALE // 2
    ImageDraw.Draw(shell).ellipse((c - 5 * SCALE, c - 7 * SCALE, c + 5 * SCALE, c + 7 * SCALE), fill=255)
    layer = Image.new("RGBA", img.size, (55, 55, 62, 0))
    layer.putalpha(shell.filter(ImageFilter.GaussianBlur(SCALE * 0.6)))
    img.alpha_composite(layer)
    tip = glow_ball((255, 240, 200), (255, 120, 20), 2).resize((SIZE * SCALE, SIZE * SCALE))
    img.alpha_composite(ImageChops.offset(tip, 0, -7 * SCALE))
    return _finish(img, diagonal)


# Muzzle flashes (owner rule 2026-10-04: the flash matches the bolt). Small
# overlays blitted onto a unit's firing frame at its muzzle (unit WML
# ~BLIT, placement from production/tools/muzzle_flashes.json), one per
# projectile colour: the bolt colours above, plus ion, Force lightning and
# proton torpedo flashes in their own projectiles' colours.
FLASH_SIZE = (14, 10)
FLASH_COLORS = {**BOLT_COLORS, "ion": (150, 210, 255), "lightning": (170, 170, 255), "torpedo": (110, 160, 255)}


def muzzle_flash(color: tuple[int, int, int]) -> Image.Image:
    """A soft coloured glow with a hot, slightly tinted core (the shape of the
    flash derive_unit_frames.py used to bake in, now in the weapon's colour)."""
    w, h = FLASH_SIZE
    big = Image.new("RGBA", (w * SCALE, h * SCALE), (0, 0, 0, 0))
    d = ImageDraw.Draw(big)
    cx, cy = w * SCALE // 2, h * SCALE // 2
    d.ellipse((cx - 6 * SCALE, cy - 4 * SCALE, cx + 6 * SCALE, cy + 4 * SCALE), fill=color + (170,))
    core = tuple(int(c + (255 - c) * 0.75) for c in color)
    d.ellipse((cx - 3 * SCALE, cy - 2 * SCALE, cx + 3 * SCALE, cy + 2 * SCALE), fill=core + (255,))
    big = big.filter(ImageFilter.GaussianBlur(0.8 * SCALE))
    return big.resize(FLASH_SIZE, Image.LANCZOS)


def assets() -> dict[str, Image.Image]:
    out: dict[str, Image.Image] = {}
    for name, rgb in BOLT_COLORS.items():
        for suffix, diag in (("n", False), ("ne", True)):
            out[f"sw-bolt-{name}-{suffix}.png"] = bolt(rgb, diag)
            out[f"sw-heavy-bolt-{name}-{suffix}.png"] = heavy_bolt(rgb, diag)
    for suffix, diag in (("n", False), ("ne", True)):
        out[f"sw-ion-{suffix}.png"] = ion_bolt(diag)
        out[f"sw-force-lightning-{suffix}.png"] = lightning(diag)
        out[f"sw-stun-{suffix}.png"] = stun_rings(diag)
        out[f"sw-bomb-{suffix}.png"] = bomb(diag)
    # Proton torpedoes read as a bright blue-white sphere in the films.
    out["sw-torpedo.png"] = glow_ball((240, 248, 255), (110, 160, 255), 4)
    for name, rgb in FLASH_COLORS.items():
        out[f"sw-flash-{name}.png"] = muzzle_flash(rgb)
    return out


def png_bytes(img: Image.Image) -> bytes:
    buffer = io.BytesIO()
    img.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="fail if any file is missing")
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    missing = []
    for name, img in assets().items():
        path = OUT / name
        if args.check:
            if not path.is_file():
                missing.append(name)
        else:
            path.write_bytes(png_bytes(img))
    if missing:
        print("missing projectile art: " + ", ".join(missing), file=sys.stderr)
        return 1
    print(("checked " if args.check else "wrote ") + f"{len(assets())} projectile sprites")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
