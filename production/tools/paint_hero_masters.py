#!/usr/bin/env python3
"""Paint detailed original master figures for heroes the image service refused.

The image service declines some named characters. For those, the owner asked
for code-drawn art instead (2026-10-01), lore-accurate to the Thrawn trilogy
era. This tool paints one large master figure per hero (512x512, shaded
layers, rim light, glow), which ``derive_unit_frames.py`` then turns into the
12 animation frames and the portrait. Every frame is a transform of the same
master, so outfit and equipment stay identical across the set.

Designs (no actor likeness; costume and equipment carry the identity):
  sw_hero_luke       Jedi Knight in the black tunic, belt and boots he wears
                     after Endor; black glove over the prosthetic right hand;
                     green lightsaber raised in a ready guard.
  sw_hero_chewbacca  Wookiee: shaggy brown fur, silver-and-brown cartridge
                     bandolier over the left shoulder, bowcaster held ready.

Usage:
  paint_hero_masters.py --out DIR [--unit sw_hero_luke ...]
Writes DIR/<slug>-master.png and DIR/<slug>-portrait.png. Requires Pillow.
"""
from __future__ import annotations

import argparse
import random
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter

SIZE = 512


# --- painting helpers --------------------------------------------------------

def mask_of(draw_fn) -> Image.Image:
    mask = Image.new("L", (SIZE, SIZE), 0)
    draw_fn(ImageDraw.Draw(mask))
    return mask


def shift(mask: Image.Image, dx: int, dy: int) -> Image.Image:
    return ImageChops.offset(mask, dx, dy)


def layer(canvas: Image.Image, mask: Image.Image, base: tuple[int, int, int], *,
          light: float = 0.35, shadow: float = 0.45, light_dir: tuple[int, int] = (-1, -1),
          depth: int = 10, outline: bool = True) -> None:
    """Fill MASK with BASE plus rounded light/shadow bands and a dark outline.

    The light band is the part of the shape that a copy offset toward the
    light does not cover; the shadow band is the mirror. Blurring both gives
    a soft, painted volume without per-pixel lighting.
    """
    lx, ly = light_dir
    hi = ImageChops.subtract(mask, shift(mask, -lx * depth, -ly * depth)).filter(ImageFilter.GaussianBlur(depth * 0.6))
    lo = ImageChops.subtract(mask, shift(mask, lx * depth, ly * depth)).filter(ImageFilter.GaussianBlur(depth * 0.6))
    hi = ImageChops.multiply(hi, mask)
    lo = ImageChops.multiply(lo, mask)
    fill = Image.new("RGBA", canvas.size, base + (255,))
    piece = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    piece.paste(fill, (0, 0), mask)
    lighter = tuple(min(255, int(c + (255 - c) * light)) for c in base)
    darker = tuple(int(c * (1 - shadow)) for c in base)
    piece.paste(Image.new("RGBA", canvas.size, lighter + (255,)), (0, 0), hi.point(lambda a: int(a * 0.8)))
    piece.paste(Image.new("RGBA", canvas.size, darker + (255,)), (0, 0), lo.point(lambda a: int(a * 0.85)))
    piece.putalpha(mask)
    if outline:
        edge = ImageChops.subtract(mask.filter(ImageFilter.MaxFilter(5)), mask)
        ink = Image.new("RGBA", canvas.size, (14, 12, 16, 0))
        ink.putalpha(edge.point(lambda a: int(a * 0.9)))
        canvas.alpha_composite(ink)
    canvas.alpha_composite(piece)


def glow(canvas: Image.Image, mask: Image.Image, core: tuple[int, int, int], halo: tuple[int, int, int],
         radius: int) -> None:
    halo_layer = Image.new("RGBA", canvas.size, halo + (0,))
    halo_layer.putalpha(mask.filter(ImageFilter.MaxFilter(9)).filter(ImageFilter.GaussianBlur(radius))
                        .point(lambda a: min(255, int(a * 1.6))))
    canvas.alpha_composite(halo_layer)
    body = Image.new("RGBA", canvas.size, core + (0,))
    body.putalpha(mask.filter(ImageFilter.GaussianBlur(1.5)))
    canvas.alpha_composite(body)


def texture(canvas: Image.Image, mask: Image.Image, palette: list[tuple[int, int, int]], *, strokes: int,
            length: tuple[int, int], width: int, slant: tuple[int, int], seed: int) -> None:
    """Short directional strokes clipped to MASK (fur, cloth weave)."""
    rng = random.Random(seed)
    strokes_layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(strokes_layer)
    box = mask.getbbox()
    if not box:
        return
    px = mask.load()
    for _ in range(strokes):
        x = rng.randint(box[0], box[2] - 1)
        y = rng.randint(box[1], box[3] - 1)
        if px[x, y] < 128:
            continue
        n = rng.randint(*length)
        dx = rng.randint(*slant)
        color = rng.choice(palette) + (rng.randint(110, 200),)
        d.line([(x, y), (x + dx, y + n)], fill=color, width=width)
    clipped = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    clipped.paste(strokes_layer, (0, 0), ImageChops.multiply(strokes_layer.split()[3], mask))
    canvas.alpha_composite(clipped)


def shaggy(mask: Image.Image, *, strands: int, length: tuple[int, int], seed: int) -> Image.Image:
    """Grow hanging strands from the edge of MASK so fur has a ragged outline."""
    rng = random.Random(seed)
    edge = ImageChops.subtract(mask, mask.filter(ImageFilter.MinFilter(5)))
    points = [(x, y) for y in range(0, SIZE, 2) for x in range(0, SIZE, 2) if edge.getpixel((x, y)) > 128]
    out = mask.copy()
    d = ImageDraw.Draw(out)
    for _ in range(strands):
        if not points:
            break
        x, y = rng.choice(points)
        n = rng.randint(*length)
        d.line([(x, y), (x + rng.randint(-4, 4), y + n)], fill=255, width=rng.randint(2, 4))
    return out


def rim(canvas: Image.Image, mask: Image.Image, color: tuple[int, int, int], dx: int = 5, dy: int = -2) -> None:
    """Cool rim light on the side away from the key light."""
    band = ImageChops.subtract(mask, shift(mask, -dx, -dy)).filter(ImageFilter.GaussianBlur(2))
    band = ImageChops.multiply(band, mask)
    lit = Image.new("RGBA", canvas.size, color + (0,))
    lit.putalpha(band.point(lambda a: int(a * 0.55)))
    canvas.alpha_composite(lit)


# --- Luke Skywalker, Jedi Knight ----------------------------------------------

def paint_luke() -> Image.Image:
    c = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    black = (34, 33, 38)
    tunic = (30, 30, 36)
    skin = (226, 184, 150)
    hair = (198, 158, 92)

    # Lightsaber blade first so the raised hand overlaps its hilt.
    blade = mask_of(lambda d: d.line([(332, 232), (452, 40)], fill=255, width=13))
    glow(c, blade, (226, 255, 226), (60, 235, 90), 14)

    # Boots and trousers: a balanced ready stance, weight slightly forward.
    legs = mask_of(lambda d: (
        d.polygon([(206, 300), (252, 300), (244, 440), (214, 440)], fill=255),
        d.polygon([(262, 300), (306, 300), (318, 438), (286, 440)], fill=255),
    ))
    layer(c, legs, black, depth=9)
    boots = mask_of(lambda d: (
        d.polygon([(210, 430), (246, 430), (250, 486), (196, 490), (200, 470)], fill=255),
        d.polygon([(284, 430), (320, 428), (334, 482), (342, 490), (288, 490)], fill=255),
    ))
    layer(c, boots, (22, 21, 24), light=0.25, depth=7)

    # Back (left) arm hangs relaxed at the side.
    back_arm = mask_of(lambda d: d.polygon([(196, 168), (220, 170), (214, 280), (194, 286), (186, 230)], fill=255))
    layer(c, back_arm, tunic, depth=8)
    back_hand = mask_of(lambda d: d.ellipse((186, 274, 214, 304), fill=255))
    layer(c, back_hand, skin, light=0.3, depth=5)

    # Torso: belted Jedi tunic with a crossed wrap front.
    torso = mask_of(lambda d: d.polygon([(196, 156), (226, 144), (290, 144), (316, 156), (312, 230), (300, 312), (212, 312), (200, 230)],
                                        fill=255))
    layer(c, torso, tunic, depth=12)
    texture(c, torso, [(44, 44, 52), (22, 22, 26)], strokes=500, length=(6, 14), width=1, slant=(-1, 1), seed=11)
    wrap = Image.new("RGBA", c.size, (0, 0, 0, 0))
    wd = ImageDraw.Draw(wrap)
    wd.line([(214, 156), (270, 248)], fill=(70, 70, 82, 255), width=4)
    wd.line([(300, 156), (262, 222)], fill=(12, 12, 14, 255), width=4)
    c.alpha_composite(wrap.filter(ImageFilter.GaussianBlur(0.8)))

    # Belt with buckle and utility pouches.
    belt = mask_of(lambda d: d.rectangle((202, 266, 312, 290), fill=255))
    layer(c, belt, (46, 40, 36), light=0.3, depth=4)
    buckle = mask_of(lambda d: d.rectangle((246, 266, 268, 290), fill=255))
    layer(c, buckle, (178, 178, 186), light=0.55, depth=3)
    for x in (212, 284):
        pouch = mask_of(lambda d, x=x: d.rounded_rectangle((x, 286, x + 18, 306), 3, fill=255))
        layer(c, pouch, (40, 36, 32), light=0.3, depth=3)

    # Neck and head, three-quarter view toward the right.
    neck = mask_of(lambda d: d.rectangle((242, 126, 270, 156), fill=255))
    layer(c, neck, skin, depth=5)
    head = mask_of(lambda d: d.ellipse((222, 58, 292, 140), fill=255))
    layer(c, head, skin, light=0.3, shadow=0.3, depth=9)
    hair_mask = mask_of(lambda d: (
        d.chord((216, 48, 296, 118), 180, 360, fill=255),
        d.polygon([(218, 84), (234, 70), (232, 112), (220, 106)], fill=255),
    ))
    layer(c, hair_mask, hair, light=0.4, depth=6)
    texture(c, hair_mask, [(236, 206, 140), (150, 112, 60)], strokes=160, length=(5, 12), width=1,
            slant=(1, 4), seed=3)
    face = Image.new("RGBA", c.size, (0, 0, 0, 0))
    fd = ImageDraw.Draw(face)
    fd.ellipse((258, 92, 266, 99), fill=(70, 96, 140, 255))      # blue eyes
    fd.ellipse((278, 92, 285, 99), fill=(70, 96, 140, 255))
    fd.line([(256, 88), (268, 86)], fill=(150, 112, 60, 255), width=2)
    fd.line([(276, 86), (287, 88)], fill=(150, 112, 60, 255), width=2)
    fd.line([(276, 100), (280, 113), (274, 114)], fill=(176, 130, 104, 255), width=2)
    fd.line([(266, 124), (280, 123)], fill=(160, 104, 92, 255), width=2)
    c.alpha_composite(face.filter(ImageFilter.GaussianBlur(0.5)))

    # Sword arm raised across the body; gloved prosthetic hand on the hilt.
    sword_arm = mask_of(lambda d: d.polygon([(286, 160), (312, 158), (336, 210), (330, 238), (306, 230),
                                             (292, 196)], fill=255))
    layer(c, sword_arm, tunic, depth=8)
    hilt = mask_of(lambda d: d.line([(316, 258), (338, 222)], fill=255, width=12))
    layer(c, hilt, (176, 176, 184), light=0.6, depth=3)
    glove = mask_of(lambda d: d.ellipse((310, 214, 344, 246), fill=255))
    layer(c, glove, (20, 20, 22), light=0.3, depth=5)

    rim(c, ImageChops.lighter(ImageChops.lighter(torso, legs), head), (150, 230, 160))
    return c


# --- Chewbacca, Wookiee ------------------------------------------------------

def paint_chewbacca() -> Image.Image:
    c = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    fur = (122, 82, 46)
    fur_palette = [(160, 116, 70), (96, 62, 34), (140, 98, 56), (74, 48, 28), (178, 136, 88)]

    feet = mask_of(lambda d: (
        d.ellipse((194, 456, 248, 490), fill=255),
        d.ellipse((288, 456, 344, 490), fill=255),
    ))
    layer(c, feet, (70, 46, 28), depth=6)
    body = shaggy(mask_of(lambda d: (
        d.polygon([(190, 118), (322, 118), (344, 230), (334, 330), (180, 330), (170, 230)], fill=255),
        d.polygon([(184, 316), (248, 316), (244, 472), (198, 472)], fill=255),       # back leg
        d.polygon([(262, 316), (328, 316), (338, 470), (290, 472)], fill=255),       # front leg
        d.polygon([(170, 140), (204, 136), (198, 300), (164, 308)], fill=255),       # back arm
    )), strands=900, length=(6, 18), seed=5)
    layer(c, body, fur, light=0.3, shadow=0.5, depth=14)
    texture(c, body, fur_palette, strokes=6000, length=(8, 22), width=2, slant=(-3, 3), seed=7)

    # Bandolier from the left shoulder to the right hip: silver cartridge boxes.
    strap = mask_of(lambda d: d.line([(212, 124), (322, 314)], fill=255, width=22))
    layer(c, strap, (92, 70, 48), light=0.3, depth=4)
    for i in range(6):
        t = (i + 0.5) / 6
        x = 212 + (322 - 212) * t
        y = 124 + (314 - 124) * t
        box = mask_of(lambda d, x=x, y=y: d.rectangle((x - 9, y - 7, x + 9, y + 7), fill=255))
        layer(c, box, (176, 178, 186), light=0.6, shadow=0.4, depth=3)

    # Head: tall Wookiee skull, darker muzzle, deep-set eyes.
    head = shaggy(mask_of(lambda d: (
        d.ellipse((214, 34, 302, 142), fill=255),
        d.polygon([(214, 90), (232, 40), (284, 32), (304, 84), (300, 150), (220, 150)], fill=255),
    )), strands=400, length=(6, 14), seed=6)
    layer(c, head, fur, light=0.32, depth=10)
    texture(c, head, fur_palette, strokes=1400, length=(6, 14), width=2, slant=(-3, 3), seed=9)
    muzzle = mask_of(lambda d: d.ellipse((246, 88, 300, 136), fill=255))
    layer(c, muzzle, (88, 58, 34), light=0.25, depth=6, outline=False)
    face = Image.new("RGBA", c.size, (0, 0, 0, 0))
    fd = ImageDraw.Draw(face)
    fd.ellipse((256, 70, 268, 80), fill=(24, 16, 10, 255))           # eyes
    fd.ellipse((280, 70, 292, 80), fill=(24, 16, 10, 255))
    fd.point([(259, 73), (283, 73)], fill=(220, 200, 170, 255))
    fd.line([(254, 66), (270, 64)], fill=(58, 36, 20, 255), width=3)  # heavy brow
    fd.line([(278, 64), (294, 66)], fill=(58, 36, 20, 255), width=3)
    fd.ellipse((274, 96, 292, 108), fill=(30, 20, 16, 255))          # nose
    fd.line([(262, 120), (290, 122)], fill=(40, 24, 18, 255), width=3)
    c.alpha_composite(face.filter(ImageFilter.GaussianBlur(0.7)))

    # Bowcaster held across the body, pointing right: stock, body, bow limbs.
    bow_body = mask_of(lambda d: d.polygon([(212, 236), (380, 210), (384, 226), (216, 256)], fill=255))
    layer(c, bow_body, (92, 78, 62), light=0.35, depth=4)
    limbs = mask_of(lambda d: (
        d.line([(352, 182), (372, 214), (360, 252)], fill=255, width=7),
    ))
    layer(c, limbs, (150, 150, 158), light=0.5, depth=3)
    cord = Image.new("RGBA", c.size, (0, 0, 0, 0))
    ImageDraw.Draw(cord).line([(352, 182), (360, 252)], fill=(210, 210, 210, 200), width=2)
    c.alpha_composite(cord)
    scope = mask_of(lambda d: d.rectangle((280, 206, 316, 218), fill=255))
    layer(c, scope, (60, 60, 66), light=0.4, depth=3)

    # Front arm and hand over the bowcaster grip.
    arm = shaggy(mask_of(lambda d: d.polygon([(298, 130), (334, 140), (342, 210), (316, 240), (296, 214)],
                                             fill=255)), strands=160, length=(4, 10), seed=12)
    layer(c, arm, fur, light=0.3, depth=10)
    texture(c, arm, fur_palette, strokes=900, length=(8, 18), width=2, slant=(-2, 2), seed=10)
    hand = mask_of(lambda d: d.ellipse((296, 212, 334, 248), fill=255))
    layer(c, hand, (90, 60, 36), depth=6)

    rim(c, ImageChops.lighter(body, head), (240, 200, 150), dx=4, dy=-1)
    return c


PAINTERS = {"sw_hero_luke": paint_luke, "sw_hero_chewbacca": paint_chewbacca}


def portrait_from_master(master: Image.Image) -> Image.Image:
    """Head-and-shoulders crop on a dark field, matching sprite-derived portraits."""
    bbox = master.split()[3].getbbox() or (0, 0, SIZE, SIZE)
    top = bbox[1]
    width = 240
    cx = (bbox[0] + bbox[2]) // 2
    crop = master.crop((cx - width // 2, max(0, top - 12), cx + width // 2, max(0, top - 12) + width))
    field = Image.new("RGBA", crop.size, (26, 28, 36, 255))
    field.alpha_composite(crop)
    return field.resize((256, 256), Image.LANCZOS)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--unit", action="append", choices=sorted(PAINTERS))
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    for unit in args.unit or sorted(PAINTERS):
        master = PAINTERS[unit]()
        slug = unit.replace("_", "-")
        master.save(args.out / f"{slug}-master.png")
        portrait_from_master(master).save(args.out / f"{slug}-portrait.png")
        print(f"painted {slug}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
