#!/usr/bin/env python3
"""Interim code-drawn art: the skiff waiting in the vehicle shed (Prisoner of Myrkr).

Owner request (2026-10-14): the shed hex Luke escapes from should show a
speeder waiting. Codex art could not be generated at the time (WSL interop
down); gen_codex_interior_art.py has the "prop-speeder" prompt to replace this
drawing later. A small open-topped repulsorlift skiff, three-quarter view,
facing right, hovering over a soft shadow; 72x72 with transparency.

Usage: gen_prop_speeder.py  (art Python with Pillow)
"""
from pathlib import Path

from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parents[2] / "addons/Star_Wars_Thrawn_Trilogy/images/misc/sw-prop-skiff.png"

OUTLINE = (34, 30, 26, 255)
HULL = (176, 150, 104, 255)
HULL_LIGHT = (205, 182, 136, 255)
HULL_DARK = (120, 100, 70, 255)
TRIM = (96, 104, 112, 255)
SEAT = (110, 58, 40, 255)
GLASS = (150, 200, 220, 210)
ENGINE = (84, 90, 98, 255)
GLOW = (120, 210, 255, 255)


def main() -> None:
    S = 4  # draw at 4x, then reduce for clean pixel edges
    W = 72 * S
    img = Image.new("RGBA", (W, W), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    def P(*pts):
        return [(x * S, y * S) for x, y in pts]
    # hover shadow
    shadow = Image.new("RGBA", (W, W), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).ellipse([12 * S, 52 * S, 62 * S, 62 * S], fill=(0, 0, 0, 90))
    img.alpha_composite(shadow)
    # engine pod at the rear (left)
    d.rounded_rectangle([7 * S, 31 * S, 21 * S, 43 * S], radius=3 * S, fill=ENGINE, outline=OUTLINE, width=S)
    d.ellipse([5 * S, 33 * S, 10 * S, 41 * S], fill=GLOW, outline=OUTLINE, width=S)
    # hull: a flat wedge, nose to the right
    d.polygon(P((14, 30), (52, 30), (66, 36), (60, 44), (14, 46)), fill=HULL, outline=OUTLINE, width=S)
    d.polygon(P((14, 30), (52, 30), (64, 35), (16, 36)), fill=HULL_LIGHT)
    d.polygon(P((14, 42), (60, 42), (60, 44), (14, 46)), fill=HULL_DARK)
    d.line(P((16, 39), (60, 39)), fill=TRIM, width=S)
    # open cockpit with two seats and a windscreen
    d.rounded_rectangle([24 * S, 27 * S, 46 * S, 35 * S], radius=2 * S, fill=HULL_DARK, outline=OUTLINE, width=S)
    for x in (27, 36):
        d.rounded_rectangle([x * S, 22 * S, (x + 6) * S, 33 * S], radius=2 * S, fill=SEAT, outline=OUTLINE, width=S)
    d.polygon(P((46, 33), (50, 24), (55, 25), (53, 33)), fill=GLASS, outline=OUTLINE)
    # repulsor vanes under the hull
    for x in (20, 44):
        d.rectangle([x * S, 46 * S, (x + 8) * S, 48 * S], fill=TRIM, outline=OUTLINE, width=S)
    small = img.resize((72, 72), Image.LANCZOS)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    small.save(OUT, optimize=True)
    print("wrote", OUT)


if __name__ == "__main__":
    main()
