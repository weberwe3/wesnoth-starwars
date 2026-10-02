#!/usr/bin/env python3
"""Draw the status-indicator overlays and menu icons for the tactical systems.

Overlays are 72x72 transparent images drawn over a unit. Each indicator keeps
to its own corner so they never cover each other or the engine's health bar
and orb (top left) or the ysalamiri frame badge (top right):

  misc/sw-fp-0..10.png        Force Points: blue pips up the right edge, bottom
  misc/sw-force-suppressed.png  ysalamiri field: violet ring with a slash, bottom right
  misc/sw-overwatch-1..3.png  overwatch crosshair with reaction pips, bottom left
  misc/sw-dazed.png           Mind Trick: swirl, top centre
  misc/sw-menu-force.png, misc/sw-menu-overwatch.png  16x16 menu icons

Usage: python3 production/tools/gen_ui_icons.py   (requires Pillow)
"""
from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "addons/Star_Wars_Thrawn_Trilogy/images/misc"
S = 4
BIG = 72 * S
OUTLINE = (10, 12, 18, 255)


def canvas(size: int = BIG) -> Image.Image:
    return Image.new("RGBA", (size, size), (0, 0, 0, 0))


def done(img: Image.Image, size: int = 72) -> Image.Image:
    return img.resize((size, size), Image.LANCZOS)


def fp(n: int) -> Image.Image:
    """Up to ten pips stacked from the bottom right; filled = available."""
    img = canvas()
    d = ImageDraw.Draw(img)
    for i in range(10):
        cx, cy = 66 * S, (66 - i * 5) * S
        r = 2 * S
        pts = [(cx, cy - r), (cx + r, cy), (cx, cy + r), (cx - r, cy)]
        if i < n:
            d.polygon(pts, fill=(110, 170, 255, 255), outline=OUTLINE)
        elif i < 6 or i < n + 2:
            d.polygon(pts, fill=(30, 40, 60, 150), outline=(10, 12, 18, 150))
    return done(img)


def suppressed() -> Image.Image:
    img = canvas()
    d = ImageDraw.Draw(img)
    cx, cy, r = 62 * S, 61 * S, 7 * S
    d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=OUTLINE, width=4 * S)
    d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=(170, 110, 230, 255), width=2 * S)
    d.line([(cx - r * 0.7, cy + r * 0.7), (cx + r * 0.7, cy - r * 0.7)], fill=OUTLINE, width=4 * S)
    d.line([(cx - r * 0.7, cy + r * 0.7), (cx + r * 0.7, cy - r * 0.7)], fill=(170, 110, 230, 255), width=2 * S)
    return done(img)


def crosshair(d: ImageDraw.ImageDraw, cx: float, cy: float, r: float, color) -> None:
    d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=OUTLINE, width=4 * S)
    d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=color, width=2 * S)
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        d.line([(cx + dx * r * 0.4, cy + dy * r * 0.4), (cx + dx * r * 1.4, cy + dy * r * 1.4)], fill=OUTLINE, width=3 * S)
        d.line([(cx + dx * r * 0.4, cy + dy * r * 0.4), (cx + dx * r * 1.4, cy + dy * r * 1.4)], fill=color, width=S)


def overwatch(shots: int) -> Image.Image:
    img = canvas()
    d = ImageDraw.Draw(img)
    crosshair(d, 10 * S, 61 * S, 5 * S, (255, 200, 90, 255))
    for i in range(shots):
        x = (19 + i * 5) * S
        d.rectangle((x, 64 * S, x + 3 * S, 68 * S), fill=(255, 200, 90, 255), outline=OUTLINE)
    return done(img)


def dazed() -> Image.Image:
    img = canvas()
    d = ImageDraw.Draw(img)
    cx, cy = 36 * S, 7 * S
    pts = []
    for i in range(60):
        a = i / 60 * 4 * math.pi
        r = (1 + i / 60 * 5) * S
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a) * 0.6))
    d.line(pts, fill=OUTLINE, width=3 * S)
    d.line(pts, fill=(150, 190, 255, 255), width=S)
    return done(img)


def menu_force() -> Image.Image:
    img = canvas(64)
    d = ImageDraw.Draw(img)
    d.line([(14, 50), (50, 14)], fill=(110, 170, 255, 255), width=8)
    d.line([(14, 50), (50, 14)], fill=(235, 245, 255, 255), width=3)
    d.line([(8, 56), (16, 48)], fill=(170, 176, 186, 255), width=8)
    return img.resize((16, 16), Image.LANCZOS)


def menu_overwatch() -> Image.Image:
    img = canvas(64)
    d = ImageDraw.Draw(img)
    d.ellipse((12, 12, 52, 52), outline=(255, 200, 90, 255), width=6)
    for a, b in (((32, 2), (32, 22)), ((32, 42), (32, 62)), ((2, 32), (22, 32)), ((42, 32), (62, 32))):
        d.line([a, b], fill=(255, 200, 90, 255), width=5)
    return img.resize((16, 16), Image.LANCZOS)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    for n in range(11):
        fp(n).save(OUT / f"sw-fp-{n}.png", optimize=True)
    suppressed().save(OUT / "sw-force-suppressed.png", optimize=True)
    for n in (1, 2, 3):
        overwatch(n).save(OUT / f"sw-overwatch-{n}.png", optimize=True)
    dazed().save(OUT / "sw-dazed.png", optimize=True)
    menu_force().save(OUT / "sw-menu-force.png", optimize=True)
    menu_overwatch().save(OUT / "sw-menu-overwatch.png", optimize=True)
    print("wrote tactical-system UI icons")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
