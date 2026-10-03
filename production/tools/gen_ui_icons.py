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

Sensors and EW (lua/sw_ew.lua) and Thrawn Doctrine (lua/sw_doctrine.lua):
  misc/sw-contact.png               hex marker: unknown sensor contact (amber "?")
  misc/sw-contact-<class>.png       hex marker: partially identified, by class
  misc/sw-contact-<class>-id.png    hex marker: identified by sensors but unseen (red)
  misc/sw-contact-locked.png        hex marker: cloaked unit identified (red brackets)
  misc/sw-ew-cloak.png, sw-ew-ecm.png, sw-ew-sweep.png  unit overlays, left edge
  misc/sw-insight-0..5.png          doctrine tier pips, top centre of the commander
  misc/sw-doctrine-threat.png       hex marker: predicted enemy target
  misc/sw-menu-sensor.png, sw-menu-decoy.png, sw-menu-doctrine.png  menu icons

Rank insignia (lua/sw_rank.lua) and air support (lua/sw_air.lua):
  misc/sw-rank-<style>-1..3.png  20x10 rank plates blitted into the unit sprite
                                 at (37,61); each higher rank covers the lower
  misc/sw-air-inbound.png        hex marker: bombing run inbound (seen by all)
  misc/sw-menu-air.png           menu icon

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


# --- sensors / EW / doctrine -------------------------------------------------

AMBER = (255, 190, 70, 255)
RED = (255, 80, 70, 255)
CYAN = (120, 225, 255, 255)
CLASSES = ("capital", "starfighter", "vehicle", "infantry", "creature", "object")


def hex_points(inset: float = 0.0) -> list[tuple[float, float]]:
    pts = [(18, 0), (54, 0), (72, 36), (54, 72), (18, 72), (0, 36)]
    c = 36
    return [((x - c) * (1 - inset) + c, (y - c) * (1 - inset) + c) for x, y in pts]


def outlined(d: ImageDraw.ImageDraw, kind: str, pts, color, width: float) -> None:
    for fill, w in ((OUTLINE, width + 2 * S), (color, width)):
        if kind == "line":
            d.line(pts, fill=fill, width=int(w), joint="curve")
        else:
            d.polygon(pts, outline=fill, width=int(w))


def glyph(d: ImageDraw.ImageDraw, cls: str, color, cx: float = 36, cy: float = 36, r: float = 9) -> None:
    """A small class symbol centred on the hex (r in 72px units)."""
    cx, cy, r = cx * S, cy * S, r * S
    w = 2 * S
    if cls == "capital":      # wedge: Star Destroyer silhouette
        outlined(d, "poly", [(cx - r, cy - r * 0.7), (cx + r * 1.2, cy), (cx - r, cy + r * 0.7)], color, w)
    elif cls == "starfighter":
        outlined(d, "line", [(cx - r, cy - r), (cx + r, cy + r)], color, w)
        outlined(d, "line", [(cx - r, cy + r), (cx + r, cy - r)], color, w)
    elif cls == "vehicle":
        outlined(d, "poly", [(cx - r, cy - r * 0.5), (cx + r, cy - r * 0.5), (cx + r, cy + r * 0.3), (cx - r, cy + r * 0.3)], color, w)
        outlined(d, "line", [(cx - r * 0.6, cy + r * 0.3), (cx - r * 0.8, cy + r)], color, w)
        outlined(d, "line", [(cx + r * 0.6, cy + r * 0.3), (cx + r * 0.8, cy + r)], color, w)
    elif cls == "infantry":
        for fill, ww in ((OUTLINE, w + 2 * S), (color, w)):
            d.ellipse((cx - r * 0.35, cy - r, cx + r * 0.35, cy - r * 0.3), outline=fill, width=int(ww))
        outlined(d, "poly", [(cx, cy - r * 0.2), (cx + r * 0.7, cy + r), (cx - r * 0.7, cy + r)], color, w)
    elif cls == "creature":
        for dx, dy in ((-0.7, -0.6), (0, -0.9), (0.7, -0.6)):
            for fill, ww in ((OUTLINE, 3.2), (color, 2.2)):
                rr = ww * S
                d.ellipse((cx + dx * r - rr, cy + dy * r - rr, cx + dx * r + rr, cy + dy * r + rr), fill=fill)
        for fill, ww in ((OUTLINE, 0.62), (color, 0.5)):
            d.ellipse((cx - r * ww, cy - r * 0.1, cx + r * ww, cy + r * (0.1 + 2 * ww * 0.9)), fill=fill)
    else:                     # object: tumbling rock
        outlined(d, "poly", [(cx - r, cy - r * 0.2), (cx - r * 0.3, cy - r), (cx + r * 0.8, cy - r * 0.6),
                             (cx + r, cy + r * 0.4), (cx + r * 0.1, cy + r), (cx - r * 0.8, cy + r * 0.7)], color, w)


def contact_marker(cls: str | None, color, identified: bool = False) -> Image.Image:
    img = canvas()
    d = ImageDraw.Draw(img)
    big = [(x * S, y * S) for x, y in hex_points(0.12)]
    # dashed hex ring: every other edge segment drawn in two halves
    for i in range(6):
        a, b = big[i], big[(i + 1) % 6]
        for t0, t1 in ((0.0, 0.32), (0.68, 1.0)):
            p0 = (a[0] + (b[0] - a[0]) * t0, a[1] + (b[1] - a[1]) * t0)
            p1 = (a[0] + (b[0] - a[0]) * t1, a[1] + (b[1] - a[1]) * t1)
            outlined(d, "line", [p0, p1], color, 2 * S)
    if cls is None:
        # "?" built from an arc and a dot
        cx, cy, r = 36 * S, 32 * S, 6 * S
        for fill, w in ((OUTLINE, 5 * S), (color, 3 * S)):
            d.arc((cx - r, cy - r, cx + r, cy + r), start=180, end=40, fill=fill, width=w)
            d.line([(cx + r * 0.75, cy + r * 0.6), (cx, cy + r * 1.1), (cx, cy + r * 1.6)], fill=fill, width=w)
            rr = w * 0.6
            d.ellipse((cx - rr, cy + r * 2.3 - rr, cx + rr, cy + r * 2.3 + rr), fill=fill)
    else:
        glyph(d, cls, color)
    if identified:
        for (x, y), (dx, dy) in zip(((14, 14), (58, 14), (14, 58), (58, 58)), ((1, 1), (-1, 1), (1, -1), (-1, -1))):
            outlined(d, "line", [(x * S, (y + 7 * dy) * S), (x * S, y * S), ((x + 7 * dx) * S, y * S)], color, 2 * S)
    return done(img)


def locked() -> Image.Image:
    img = canvas()
    d = ImageDraw.Draw(img)
    for (x, y), (dx, dy) in zip(((10, 10), (62, 10), (10, 62), (62, 62)), ((1, 1), (-1, 1), (1, -1), (-1, -1))):
        outlined(d, "line", [(x * S, (y + 9 * dy) * S), (x * S, y * S), ((x + 9 * dx) * S, y * S)], RED, 2 * S)
    return done(img)


def ew_overlay(kind: str) -> Image.Image:
    """Unit overlays on the left edge, between the health bar and the overwatch crosshair."""
    img = canvas()
    d = ImageDraw.Draw(img)
    cx, cy = 7 * S, 38 * S
    if kind == "cloak":       # broken diamond: a shimmering field
        r = 5 * S
        pts = [(cx, cy - r), (cx + r, cy), (cx, cy + r), (cx - r, cy)]
        for i in range(4):
            a, b = pts[i], pts[(i + 1) % 4]
            m0 = (a[0] + (b[0] - a[0]) * 0.15, a[1] + (b[1] - a[1]) * 0.15)
            m1 = (a[0] + (b[0] - a[0]) * 0.85, a[1] + (b[1] - a[1]) * 0.85)
            outlined(d, "line", [m0, m1], CYAN, 1.5 * S)
    elif kind == "ecm":       # jagged jamming waves
        color = (230, 240, 90, 255)
        for off in (-3, 1):
            pts = [(cx - 5 * S + i * 2 * S, cy + off * S + (-2 if i % 2 else 2) * S) for i in range(6)]
            outlined(d, "line", pts, color, 1.5 * S)
    else:                     # sweep: radar arcs
        for rr in (3, 6):
            for fill, w in ((OUTLINE, 3.5 * S), (CYAN, 1.5 * S)):
                d.arc((cx - 4 * S - rr * S, cy - rr * S, cx - 4 * S + rr * S, cy + rr * S), start=-50, end=50,
                      fill=fill, width=int(w))
        for fill, w in ((OUTLINE, 3.2), (CYAN, 2)):
            d.ellipse((cx - 4 * S - w * S, cy - w * S, cx - 4 * S + w * S, cy + w * S), fill=fill)
    return done(img)


def insight(n: int) -> Image.Image:
    """Five pips across the top centre: filled = doctrine tiers reached."""
    img = canvas()
    d = ImageDraw.Draw(img)
    for i in range(5):
        cx, cy, r = (26 + i * 5) * S, 4 * S, 2 * S
        pts = [(cx, cy - r), (cx + r, cy), (cx, cy + r), (cx - r, cy)]
        if i < n:
            d.polygon(pts, fill=(235, 50, 60, 255), outline=OUTLINE)
        else:
            d.polygon(pts, fill=(40, 30, 50, 150), outline=(10, 12, 18, 150))
    return done(img)


def threat() -> Image.Image:
    img = canvas()
    d = ImageDraw.Draw(img)
    color = (255, 70, 150, 255)
    big = [(x * S, y * S) for x, y in hex_points(0.05)]
    for i in range(6):
        a, b = big[i], big[(i + 1) % 6]
        mid = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
        for p0 in (a, b):
            q = (p0[0] + (mid[0] - p0[0]) * 0.45, p0[1] + (mid[1] - p0[1]) * 0.45)
            outlined(d, "line", [p0, q], color, 2 * S)
    # chevrons at the bottom edge pointing in
    for k in (0, 1):
        y = (63 - k * 4) * S
        outlined(d, "line", [(31 * S, y), (36 * S, y - 3 * S), (41 * S, y)], color, 1.5 * S)
    return done(img)


def menu_sensor() -> Image.Image:
    img = canvas(64)
    d = ImageDraw.Draw(img)
    for r in (14, 26, 38):
        d.arc((8 - r, 56 - r, 8 + r, 56 + r), start=-90, end=0, fill=(120, 225, 255, 255), width=6)
    d.ellipse((2, 50, 14, 62), fill=(120, 225, 255, 255))
    return img.resize((16, 16), Image.LANCZOS)


def menu_decoy() -> Image.Image:
    img = canvas(64)
    d = ImageDraw.Draw(img)
    pts = [(6, 18), (58, 32), (6, 46)]
    for i in range(3):
        a, b = pts[i], pts[(i + 1) % 3]
        for t in (0.0, 0.4):
            p0 = (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)
            p1 = (a[0] + (b[0] - a[0]) * (t + 0.3), a[1] + (b[1] - a[1]) * (t + 0.3))
            d.line([p0, p1], fill=(255, 190, 70, 255), width=6)
    return img.resize((16, 16), Image.LANCZOS)


def menu_doctrine() -> Image.Image:
    img = canvas(64)
    d = ImageDraw.Draw(img)
    d.ellipse((2, 16, 62, 48), fill=(60, 90, 190, 255), outline=(10, 12, 18, 255), width=3)
    d.ellipse((22, 18, 42, 46), fill=(230, 40, 50, 255))
    d.ellipse((28, 26, 36, 38), fill=(255, 200, 200, 255))
    return img.resize((16, 16), Image.LANCZOS)


# --- rank insignia ------------------------------------------------------------

RANK_W, RANK_H, RS = 20, 10, 8


def rank_plate(style: str, n: int) -> Image.Image:
    """An opaque 20x10 plate; identical footprint for every rank and style."""
    img = Image.new("RGBA", (RANK_W * RS, RANK_H * RS), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    plate, rim = {
        "republic": ((24, 36, 72, 255), (217, 176, 74, 255)),
        "imperial": ((44, 46, 52, 255), (170, 176, 186, 255)),
        "independent": ((78, 52, 32, 255), (196, 150, 84, 255)),
        "darkside": ((20, 12, 28, 255), (150, 70, 200, 255)),
    }[style]
    d.rounded_rectangle((0, 0, RANK_W * RS - 1, RANK_H * RS - 1), radius=2 * RS, fill=OUTLINE)
    d.rounded_rectangle((RS, RS, RANK_W * RS - 1 - RS, RANK_H * RS - 1 - RS), radius=RS, fill=plate, outline=rim, width=RS)
    cx0 = RANK_W * RS / 2
    if style == "republic":
        # n gold chevrons side by side
        span = 5 * RS
        for i in range(n):
            x = cx0 + (i - (n - 1) / 2) * span
            d.line([(x - 2 * RS, 6.5 * RS), (x, 3.2 * RS), (x + 2 * RS, 6.5 * RS)], fill=(255, 214, 90, 255), width=int(1.4 * RS))
    elif style == "imperial":
        # Imperial rank plaque: a row of red tiles over a row of blue tiles
        span = 4 * RS
        for i in range(n):
            x = cx0 + (i - (n - 1) / 2) * span
            d.rectangle((x - 1.4 * RS, 2.6 * RS, x + 1.4 * RS, 4.6 * RS), fill=(220, 40, 40, 255))
            d.rectangle((x - 1.4 * RS, 5.4 * RS, x + 1.4 * RS, 7.4 * RS), fill=(60, 110, 230, 255))
    elif style == "independent":
        span = 4.5 * RS
        for i in range(n):
            x = cx0 + (i - (n - 1) / 2) * span
            d.ellipse((x - 1.6 * RS, 3.4 * RS, x + 1.6 * RS, 6.6 * RS), fill=(232, 190, 110, 255), outline=(90, 60, 30, 255))
    else:
        span = 4.5 * RS
        for i in range(n):
            x, y, r = cx0 + (i - (n - 1) / 2) * span, 5 * RS, 1.9 * RS
            d.polygon([(x, y - r), (x + r, y), (x, y + r), (x - r, y)], fill=(220, 60, 90, 255))
    return img.resize((RANK_W, RANK_H), Image.LANCZOS)


def air_inbound() -> Image.Image:
    img = canvas()
    d = ImageDraw.Draw(img)
    color = (255, 120, 40, 255)
    cx, cy, r = 36 * S, 36 * S, 26 * S
    for a in range(0, 360, 30):
        outlined_arc = (cx - r, cy - r, cx + r, cy + r)
        d.arc(outlined_arc, start=a, end=a + 18, fill=OUTLINE, width=5 * S)
        d.arc(outlined_arc, start=a, end=a + 18, fill=color, width=3 * S)
    # three falling bombs
    for dx in (-9, 0, 9):
        x = (36 + dx) * S
        for fill, w in ((OUTLINE, 5 * S), (color, 3 * S)):
            d.line([(x, 26 * S), (x, 38 * S)], fill=fill, width=w)
        for fill, grow in ((OUTLINE, 1.2), (color, 0)):
            d.polygon([(x - (4 + grow) * S, 38 * S), (x + (4 + grow) * S, 38 * S), (x, (44 + grow) * S)], fill=fill)
    return done(img)


def menu_air() -> Image.Image:
    img = canvas(64)
    d = ImageDraw.Draw(img)
    color = (255, 150, 60, 255)
    d.polygon([(32, 4), (40, 24), (60, 30), (40, 34), (34, 44), (30, 44), (24, 34), (4, 30), (24, 24)], fill=color)
    d.line([(32, 46), (32, 62)], fill=(255, 220, 120, 255), width=5)
    d.polygon([(24, 54), (40, 54), (32, 63)], fill=(255, 220, 120, 255))
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
    contact_marker(None, AMBER).save(OUT / "sw-contact.png", optimize=True)
    for cls in CLASSES:
        contact_marker(cls, AMBER).save(OUT / f"sw-contact-{cls}.png", optimize=True)
        contact_marker(cls, RED, identified=True).save(OUT / f"sw-contact-{cls}-id.png", optimize=True)
    locked().save(OUT / "sw-contact-locked.png", optimize=True)
    for kind in ("cloak", "ecm", "sweep"):
        ew_overlay(kind).save(OUT / f"sw-ew-{kind}.png", optimize=True)
    for n in range(6):
        insight(n).save(OUT / f"sw-insight-{n}.png", optimize=True)
    threat().save(OUT / "sw-doctrine-threat.png", optimize=True)
    menu_sensor().save(OUT / "sw-menu-sensor.png", optimize=True)
    menu_decoy().save(OUT / "sw-menu-decoy.png", optimize=True)
    menu_doctrine().save(OUT / "sw-menu-doctrine.png", optimize=True)
    for style in ("republic", "imperial", "independent", "darkside"):
        for n in (1, 2, 3):
            rank_plate(style, n).save(OUT / f"sw-rank-{style}-{n}.png", optimize=True)
    air_inbound().save(OUT / "sw-air-inbound.png", optimize=True)
    menu_air().save(OUT / "sw-menu-air.png", optimize=True)
    print("wrote tactical-system UI icons")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
