#!/usr/bin/env python3
"""Paint original 60x60 attack icons for the Star Wars weapons.

Mainline icons stay where they already fit (fists, fangs, the Wayland
natives' spears and bows); everything technological gets its own icon here
instead of a flaming sword or an iron crossbow. Each icon is a dark rounded
plate with the weapon drawn across it, lit from the upper left, in the same
footprint as mainline icons.

Usage: python3 production/tools/gen_attack_icons.py
Requires Pillow.
"""
from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "addons/Star_Wars_Thrawn_Trilogy/images/attacks"
SIZE = 60
S = 4
BIG = SIZE * S

GUNMETAL = (70, 74, 82)
DARK = (34, 36, 42)
STEEL = (170, 176, 186)


def plate() -> Image.Image:
    img = Image.new("RGBA", (BIG, BIG), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((2 * S, 2 * S, BIG - 2 * S, BIG - 2 * S), 8 * S, fill=(22, 24, 30, 255),
                        outline=(90, 96, 108, 255), width=S)
    glow = Image.new("L", (BIG, BIG), 0)
    ImageDraw.Draw(glow).ellipse((-10 * S, -10 * S, 40 * S, 40 * S), fill=60)
    light = Image.new("RGBA", (BIG, BIG), (120, 140, 170, 0))
    light.putalpha(glow.filter(ImageFilter.GaussianBlur(8 * S)))
    img.alpha_composite(light)
    return img


def done(img: Image.Image) -> Image.Image:
    return img.resize((SIZE, SIZE), Image.LANCZOS)


def glow_line(img: Image.Image, points, color, width, core=True) -> None:
    halo = Image.new("L", (BIG, BIG), 0)
    ImageDraw.Draw(halo).line(points, fill=255, width=width * 3)
    layer = Image.new("RGBA", (BIG, BIG), color + (0,))
    layer.putalpha(halo.filter(ImageFilter.GaussianBlur(width)).point(lambda a: int(a * 0.8)))
    img.alpha_composite(layer)
    d = ImageDraw.Draw(img)
    d.line(points, fill=color + (255,), width=width)
    if core:
        d.line(points, fill=(255, 255, 245, 255), width=max(S, width // 2))


def poly(img: Image.Image, points, fill, outline=(10, 10, 12, 255)) -> None:
    d = ImageDraw.Draw(img)
    d.polygon([(x * S, y * S) for x, y in points], fill=fill + (255,), outline=outline)


def pistol(img: Image.Image, barrel_len: float = 18, color=GUNMETAL) -> None:
    """Side view of a blaster pistol pointing right."""
    poly(img, [(14, 24), (28 + barrel_len, 24), (28 + barrel_len, 30), (30, 30), (26, 42), (19, 42), (21, 30),
               (14, 30)], color)
    poly(img, [(28, 21), (36, 21), (36, 24), (28, 24)], DARK)                    # scope
    poly(img, [(28 + barrel_len, 25), (31 + barrel_len, 25), (31 + barrel_len, 29), (28 + barrel_len, 29)], DARK)
    d = ImageDraw.Draw(img)
    for x in range(30, int(26 + barrel_len), 4):                                  # cooling vents
        d.line([(x * S, 26 * S), (x * S, 28 * S)], fill=DARK + (255,), width=S)


def blaster_pistol() -> Image.Image:
    img = plate()
    pistol(img, 12)
    glow_line(img, [(46 * S, 27 * S), (56 * S, 27 * S)], (255, 70, 50), 2 * S)
    return done(img)


def heavy_pistol() -> Image.Image:
    """Heavy blaster pistol: longer barrel with a flash suppressor cone."""
    img = plate()
    pistol(img, 18)
    poly(img, [(46, 24), (50, 23), (50, 31), (46, 30)], STEEL)
    return done(img)


def hold_out() -> Image.Image:
    img = plate()
    poly(img, [(20, 26), (38, 26), (38, 31), (28, 31), (25, 40), (20, 40), (22, 31), (20, 31)], (96, 90, 84))
    return done(img)


def blaster_rifle() -> Image.Image:
    """Long rifle with stock, scope and a folding stock outline."""
    img = plate()
    poly(img, [(6, 28), (14, 26), (48, 26), (48, 32), (24, 32), (21, 39), (16, 39), (17, 32), (6, 33)], GUNMETAL)
    poly(img, [(24, 22), (36, 22), (36, 26), (24, 26)], DARK)
    poly(img, [(48, 27), (55, 27), (55, 31), (48, 31)], DARK)
    d = ImageDraw.Draw(img)
    for x in range(28, 46, 4):
        d.line([(x * S, 28 * S), (x * S, 30 * S)], fill=DARK + (255,), width=S)
    return done(img)


def heavy_repeater() -> Image.Image:
    """Tripod-mounted repeating blaster (E-Web, twin cannons)."""
    img = plate()
    poly(img, [(10, 20), (46, 20), (46, 30), (10, 30)], GUNMETAL)
    poly(img, [(46, 22), (54, 22), (54, 28), (46, 28)], DARK)
    poly(img, [(18, 14), (30, 14), (30, 20), (18, 20)], DARK)
    d = ImageDraw.Draw(img)
    for start, end in (((26, 30), (14, 50)), ((28, 30), (28, 50)), ((30, 30), (42, 50))):
        d.line([(start[0] * S, start[1] * S), (end[0] * S, end[1] * S)], fill=STEEL + (255,), width=2 * S)
    return done(img)


def laser_cannon() -> Image.Image:
    """Starfighter laser cannon: long barrel with flash suppressor rings, firing."""
    img = plate()
    poly(img, [(6, 26), (40, 26), (40, 32), (6, 32)], (190, 194, 200))
    d = ImageDraw.Draw(img)
    for x in (16, 24, 32):
        d.rectangle((x * S, 24 * S, (x + 3) * S, 34 * S), fill=(120, 124, 132, 255))
    glow_line(img, [(42 * S, 29 * S), (56 * S, 29 * S)], (255, 60, 40), 3 * S)
    return done(img)


def turbolaser() -> Image.Image:
    """Capital-ship turbolaser turret: dome with twin barrels, heavy green bolts."""
    img = plate()
    d = ImageDraw.Draw(img)
    d.pieslice((8 * S, 26 * S, 32 * S, 50 * S), 180, 360, fill=GUNMETAL + (255,), outline=(10, 10, 12, 255))
    for y in (30, 36):
        poly(img, [(24, y), (40, y), (40, y + 3), (24, y + 3)], DARK)
        glow_line(img, [(42 * S, (y + 1.5) * S), (55 * S, (y - 6) * S)], (60, 255, 80), 3 * S)
    return done(img)


def ion_cannon() -> Image.Image:
    img = plate()
    poly(img, [(6, 26), (30, 24), (30, 34), (6, 32)], GUNMETAL)
    for i, r in enumerate((6, 10, 14)):
        d = ImageDraw.Draw(img)
        cx = (36 + i * 6) * S
        d.arc((cx - r * S, 29 * S - r * S, cx + r * S, 29 * S + r * S), 300, 60,
              fill=(150, 200, 255, 230), width=S)
    glow_line(img, [(32 * S, 29 * S), (54 * S, 29 * S)], (130, 190, 255), 2 * S)
    return done(img)


def torpedo() -> Image.Image:
    img = plate()
    d = ImageDraw.Draw(img)
    halo = Image.new("L", (BIG, BIG), 0)
    ImageDraw.Draw(halo).ellipse((22 * S, 18 * S, 46 * S, 42 * S), fill=255)
    layer = Image.new("RGBA", (BIG, BIG), (110, 160, 255, 0))
    layer.putalpha(halo.filter(ImageFilter.GaussianBlur(5 * S)))
    img.alpha_composite(layer)
    d.ellipse((28 * S, 24 * S, 40 * S, 36 * S), fill=(235, 245, 255, 255))
    glow_line(img, [(8 * S, 34 * S), (28 * S, 30 * S)], (110, 160, 255), 2 * S, core=False)
    return done(img)


def bomb() -> Image.Image:
    img = plate()
    d = ImageDraw.Draw(img)
    d.ellipse((20 * S, 18 * S, 40 * S, 44 * S), fill=(58, 60, 66, 255), outline=(10, 10, 12, 255), width=S)
    d.rectangle((26 * S, 14 * S, 34 * S, 19 * S), fill=STEEL + (255,))
    halo = Image.new("L", (BIG, BIG), 0)
    ImageDraw.Draw(halo).ellipse((26 * S, 26 * S, 34 * S, 34 * S), fill=255)
    layer = Image.new("RGBA", (BIG, BIG), (255, 130, 30, 0))
    layer.putalpha(halo.filter(ImageFilter.GaussianBlur(2 * S)))
    img.alpha_composite(layer)
    return done(img)


def lightsaber(color) -> Image.Image:
    """Hilt at lower left, glowing blade rising diagonally."""
    img = plate()
    glow_line(img, [(24 * S, 36 * S), (52 * S, 8 * S)], color, 3 * S)
    d = ImageDraw.Draw(img)
    d.line([(10 * S, 50 * S), (24 * S, 36 * S)], fill=STEEL + (255,), width=5 * S)
    d.line([(14 * S, 46 * S), (18 * S, 42 * S)], fill=DARK + (255,), width=5 * S)
    d.line([(21 * S, 39 * S), (24 * S, 36 * S)], fill=DARK + (255,), width=6 * S)
    return done(img)


def deflection() -> Image.Image:
    """Green blade turning back a red bolt."""
    img = plate()
    glow_line(img, [(18 * S, 46 * S), (40 * S, 10 * S)], (70, 255, 90), 3 * S)
    glow_line(img, [(54 * S, 20 * S), (34 * S, 28 * S)], (255, 60, 40), 2 * S)
    glow_line(img, [(34 * S, 28 * S), (52 * S, 44 * S)], (255, 60, 40), 2 * S)
    return done(img)


def force_lightning() -> Image.Image:
    img = plate()
    mask = Image.new("L", (BIG, BIG), 0)
    d = ImageDraw.Draw(mask)
    for offset in (-6, 0, 6):
        pts = [(8, 30), (18, 24 + offset), (26, 34 + offset), (36, 22 + offset), (44, 32 + offset),
               (54, 26 + offset)]
        d.line([(x * S, y * S) for x, y in pts], fill=255, width=S * (2 if offset == 0 else 1))
    halo = Image.new("RGBA", (BIG, BIG), (110, 140, 255, 0))
    halo.putalpha(mask.filter(ImageFilter.GaussianBlur(3 * S)).point(lambda a: min(255, a * 2)))
    img.alpha_composite(halo)
    core = Image.new("RGBA", (BIG, BIG), (235, 240, 255, 0))
    core.putalpha(mask)
    img.alpha_composite(core)
    return done(img)


def stun_blaster() -> Image.Image:
    img = plate()
    pistol(img, 10, (80, 84, 92))
    d = ImageDraw.Draw(img)
    for i, r in enumerate((3, 5, 7)):
        cx = (44 + i * 5) * S
        d.ellipse((cx - S, 27 * S - r * S, cx + S, 27 * S + r * S), outline=(90, 170, 255, 255), width=S)
    return done(img)


def vibroblade(length: float) -> Image.Image:
    """Straight vibroblade with a faint humming edge."""
    img = plate()
    tip = (14 + length, 16)
    poly(img, [(18, 40), (tip[0], tip[1]), (tip[0] - 3, tip[1] + 6), (21, 43)], STEEL)
    glow_line(img, [((tip[0] - 1) * S, (tip[1] + 1) * S), (19 * S, 41 * S)], (200, 230, 255), S, core=False)
    d = ImageDraw.Draw(img)
    d.line([(10 * S, 50 * S), (19 * S, 41 * S)], fill=DARK + (255,), width=4 * S)
    d.line([(15 * S, 38 * S), (23 * S, 46 * S)], fill=(120, 124, 132, 255), width=2 * S)
    return done(img)


def force_pike() -> Image.Image:
    """Royal Guard force pike: long staff with a vibro-blade head."""
    img = plate()
    d = ImageDraw.Draw(img)
    d.line([(8 * S, 52 * S), (42 * S, 18 * S)], fill=(40, 38, 44, 255), width=3 * S)
    poly(img, [(40, 20), (52, 8), (46, 22)], STEEL)
    glow_line(img, [(42 * S, 19 * S), (51 * S, 9 * S)], (200, 230, 255), S, core=False)
    return done(img)


def bowcaster() -> Image.Image:
    """Wookiee bowcaster: stock and body with curved bow limbs and a glowing quarrel."""
    img = plate()
    poly(img, [(8, 30), (40, 27), (40, 33), (8, 35)], (110, 86, 60))
    d = ImageDraw.Draw(img)
    d.arc((30 * S, 12 * S, 48 * S, 48 * S), 290, 70, fill=STEEL + (255,), width=2 * S)
    glow_line(img, [(40 * S, 30 * S), (55 * S, 30 * S)], (80, 255, 90), 2 * S)
    return done(img)


def sprayer() -> Image.Image:
    img = plate()
    poly(img, [(10, 26), (34, 26), (34, 34), (10, 34)], (150, 130, 60))
    mist = Image.new("L", (BIG, BIG), 0)
    ImageDraw.Draw(mist).polygon([(34 * S, 30 * S), (56 * S, 18 * S), (56 * S, 42 * S)], fill=200)
    layer = Image.new("RGBA", (BIG, BIG), (170, 230, 140, 0))
    layer.putalpha(mist.filter(ImageFilter.GaussianBlur(4 * S)))
    img.alpha_composite(layer)
    return done(img)


def manipulator() -> Image.Image:
    """Droid manipulator arm with a two-finger claw."""
    img = plate()
    d = ImageDraw.Draw(img)
    d.line([(8 * S, 44 * S), (26 * S, 30 * S), (40 * S, 34 * S)], fill=(150, 130, 60, 255), width=4 * S)
    d.ellipse((23 * S, 27 * S, 29 * S, 33 * S), fill=DARK + (255,))
    d.line([(40 * S, 34 * S), (52 * S, 26 * S)], fill=STEEL + (255,), width=2 * S)
    d.line([(40 * S, 34 * S), (52 * S, 40 * S)], fill=STEEL + (255,), width=2 * S)
    return done(img)


ICONS = {
    "sw-blaster-pistol": blaster_pistol,
    "sw-heavy-blaster-pistol": heavy_pistol,
    "sw-hold-out-blaster": hold_out,
    "sw-blaster-rifle": blaster_rifle,
    "sw-heavy-repeater": heavy_repeater,
    "sw-laser-cannon": laser_cannon,
    "sw-turbolaser": turbolaser,
    "sw-ion-cannon": ion_cannon,
    "sw-proton-torpedo": torpedo,
    "sw-concussion-bomb": bomb,
    "sw-lightsaber-green": lambda: lightsaber((60, 255, 80)),
    "sw-lightsaber-blue": lambda: lightsaber((70, 150, 255)),
    "sw-deflection": deflection,
    "sw-force-lightning": force_lightning,
    "sw-stun-blaster": stun_blaster,
    "sw-vibroblade": lambda: vibroblade(30),
    "sw-vibroknife": lambda: vibroblade(20),
    "sw-force-pike": force_pike,
    "sw-bowcaster": bowcaster,
    "sw-sprayer": sprayer,
    "sw-manipulator": manipulator,
}


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    for name, paint in ICONS.items():
        paint().save(OUT / f"{name}.png", optimize=True)
    print(f"wrote {len(ICONS)} attack icons")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
