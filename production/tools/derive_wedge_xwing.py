#!/usr/bin/env python3
"""Wedge Antilles's X-wing, drawn on Luke's X-wing design.

Owner request (2026-10-14): Wedge's X-wing should look like Luke's. Every
frame of each rank (sw-hero-xwing-luke, -rank2, -rank3) is copied into the
matching Wedge set (sw-hero-wedge, -rank2, -rank3) with its red squadron
markings recoloured to Wedge's orange-gold, so the two heroes share one
design but still read apart on the map (the same approach as
recolor_unit_fur.py for the Wookiees). Shading is kept: each marking pixel
keeps its value and saturation, only the hue moves.

Usage: derive_wedge_xwing.py [--preview OUT.png] [--install]
Run with the art Python (Pillow).
"""
from __future__ import annotations

import argparse
import colorsys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
UNITS = ROOT / "addons/Star_Wars_Thrawn_Trilogy/images/units"
PAIRS = [("sw-hero-xwing-luke", "sw-hero-wedge"), ("sw-hero-xwing-luke-rank2", "sw-hero-wedge-rank2"),
         ("sw-hero-xwing-luke-rank3", "sw-hero-wedge-rank3")]
WEDGE_HUE = 32 / 360   # orange-gold, Wedge's colours in the earlier art


def recolour(img: Image.Image) -> Image.Image:
    img = img.convert("RGBA")
    px = img.load()
    for y in range(img.height):
        for x in range(img.width):
            r, g, b, a = px[x, y]
            if a == 0:
                continue
            h, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
            # Red markings: hue within about 25 degrees of red, clearly saturated.
            if (h < 25 / 360 or h > 335 / 360) and s > 0.35 and v > 0.2:
                nr, ng, nb = colorsys.hsv_to_rgb(WEDGE_HUE, min(1.0, s * 1.05), v)
                px[x, y] = (round(nr * 255), round(ng * 255), round(nb * 255), a)
    return img


def frames(src: str) -> list[Path]:
    return sorted((UNITS / src).glob("*.png"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preview", type=Path)
    parser.add_argument("--install", action="store_true")
    args = parser.parse_args()
    if args.preview:
        rows = []
        for src, _dst in PAIRS:
            files = frames(src)
            row = Image.new("RGBA", (144 * len(files), 288), (30, 30, 40, 255))
            for i, f in enumerate(files):
                a = Image.open(f).convert("RGBA")
                row.alpha_composite(a.resize((144, 144), Image.NEAREST), (144 * i, 0))
                row.alpha_composite(recolour(a).resize((144, 144), Image.NEAREST), (144 * i, 144))
            rows.append(row)
        sheet = Image.new("RGBA", (max(r.width for r in rows), sum(r.height for r in rows)))
        y = 0
        for r in rows:
            sheet.alpha_composite(r, (0, y))
            y += r.height
        sheet.save(args.preview)
    if args.install:
        for src, dst in PAIRS:
            for f in frames(src):
                out = UNITS / dst / f.name
                recolour(Image.open(f)).save(out, optimize=True)
                print("wrote", out.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
