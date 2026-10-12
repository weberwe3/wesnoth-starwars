#!/usr/bin/env python3
"""Draw every wall's art: a seamless top, a front face, rims and a cast shadow.

Owner direction (2026-10-12): walls looked malformed -- each wall hex showed
its own hex-shaped plate with features centred on it or clipped at its edge,
so a run of wall hexes read as a honeycomb of separate tiles rather than one
wall. Walls must look like walls and be identified at a glance.

1. Tops (sw/<stem>.png and its numbered variants, placed by NEW:BASE in
   utils/hte_terrain.cfg). Every hex of a terrain uses the same image, and a
   hex at column c, row r is drawn at x = 54c, y = 72r + 36(c mod 2). A
   pattern that repeats every 54 px across and every 36 px down therefore
   continues unbroken from hex to hex: plate seams, block courses and plank
   rows run straight through a whole wall. Nothing is centred on the hex.
   Variants differ only in fine noise.

     bulkhead  dark blue-grey steel plates (18 px) with seams and rivets
     colony    pale duracrete blocks (18 px) in a running bond
     palace    polished sandstone slabs (18 px) with gold inlay seams
     rock      rough grey stone (periodic noise and cracks, no seams)
     timber    dark log planks in 12 px rows with staggered joints

2. Edges (sw/wall-relief-<family>-<dir>.png, utils/hte_terrain.cfg
   SW_WALL_RELIEF), on a wall hex along each edge it shares with floor:
     s, se, sw  the wall's front face -- a tall, dark vertical face in the
                family's face material, a bright lip where the top ends and
                a near-black line at its foot;
     n, ne, nw  a slightly brighter coping on the top, outlined in near-black.
   Neighbouring walls get no edge between them, so a run of walls is one
   raised mass with a crisp silhouette. (bunker: the castle hexes round a
   command bunker, a low parapet in the bulkhead style.)

3. Shadows (sw/wall-shadow-<dir>.png), on a floor hex along an edge shared
   with a wall to its north: the shadow the wall casts.

Usage (art Python): gen_wall_relief.py
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parents[2] / "addons/Star_Wars_Thrawn_Trilogy/images/terrain/sw"
S = 72
PX, PY = 54, 36          # lattice periods: one hex column across, half a hex down
# family -> (top image stem, variant count)
FAMILIES = {"timber": ("wall-timber", 2), "colony": ("wall-colony", 2), "palace": ("wall-palace", 2),
            "rock": ("wall-rock", 2), "bulkhead": ("bulkhead", 3)}
# Height of each family's face relative to a full wall: bunker aprons (the
# castle hexes round a command bunker) get a low parapet, so the recruiting
# footprint stands out without reading as an impassable wall.
HEIGHT = {"bunker": 0.45}
CORNERS = {"nw": (18, 0), "ne": (54, 0), "e": (72, 36), "se": (54, 72), "sw": (18, 72), "w": (0, 36)}
EDGES = {"n": ("nw", "ne"), "ne": ("ne", "e"), "se": ("e", "se"), "s": ("se", "sw"), "sw": ("sw", "w"),
         "nw": ("w", "nw")}
SOUTH = {"s": 22, "se": 15, "sw": 15}   # front-face depth in pixels, deepest straight below
NORTH = {"n": 3, "ne": 3, "nw": 3}
CENTRE = np.array([36.0, 36.0])
YS, XS = np.mgrid[0:S, 0:S]


def hex_mask() -> np.ndarray:
    m = Image.new("L", (S, S), 0)
    ImageDraw.Draw(m).polygon([CORNERS[k] for k in ("nw", "ne", "e", "se", "sw", "w")], fill=255)
    return np.asarray(m) > 0


def edge_distance(direction: str) -> np.ndarray:
    """Distance of every pixel from the given edge, measured towards the centre."""
    a, b = (np.array(CORNERS[k], float) for k in EDGES[direction])
    normal = np.array([-(b - a)[1], (b - a)[0]])
    normal /= np.linalg.norm(normal)
    if np.dot(CENTRE - a, normal) < 0:
        normal = -normal
    pts = np.dstack([XS + 0.5, YS + 0.5])
    return (pts - a) @ normal


# --- Periodic noise (repeats every PX across and PY down) --------------------

def periodic_noise(seed: int, octaves=((1, 1, 1.0), (2, 3, 0.6), (4, 5, 0.35), (9, 6, 0.25), (18, 12, 0.15))):
    rng = np.random.default_rng(seed)
    out = np.zeros((S, S))
    for kx, ky, amp in octaves:
        for _ in range(3):
            fx, fy = rng.integers(-kx, kx + 1), rng.integers(-ky, ky + 1)
            out += amp * np.cos(2 * np.pi * (fx * XS / PX + fy * YS / PY) + rng.uniform(0, 2 * np.pi))
    out -= out.mean()
    return out / (np.abs(out).max() + 1e-9)


def fine_noise(seed: int) -> np.ndarray:
    """Pixel-scale grain, also periodic, so it never shows a seam."""
    rng = np.random.default_rng(seed)
    tile = rng.normal(0, 1, (PY, PX))
    return tile[YS % PY, XS % PX]


def colour(base, shade: np.ndarray) -> np.ndarray:
    return np.clip(np.array(base, float)[None, None, :] * shade[..., None], 0, 255)


# --- Tops -------------------------------------------------------------------

def top_bulkhead(seed: int) -> np.ndarray:
    gx, gy = XS % 18, YS % 18
    cell = (XS // 18) % 3 + 3 * ((YS // 18) % 2)
    shade = 1.0 + 0.04 * np.array([0, -1, 1, 1, 0, -1])[cell]
    shade = shade + 0.035 * periodic_noise(seed) + 0.025 * fine_noise(seed + 1)
    seam = (gx == 0) | (gy == 0)
    hilite = (gx == 1) | (gy == 1)
    shade = np.where(seam, 0.55, np.where(hilite, shade * 1.12, shade))
    rivet = np.isin(gx, (3, 15)) & np.isin(gy, (3, 15))
    shade = np.where(rivet, 1.35, shade)
    return colour((84, 93, 106), shade)


def top_colony(seed: int) -> np.ndarray:
    row = YS // 18
    gx = (XS + 9 * (row % 2)) % 18
    gy = YS % 18
    shade = 1.0 + 0.05 * periodic_noise(seed) + 0.035 * fine_noise(seed + 1)
    seam = (gx == 0) | (gy == 0)
    shade = np.where(seam, 0.72, np.where((gy == 1) | (gx == 1), shade * 1.06, shade))
    return colour((168, 166, 158), shade)


def top_palace(seed: int) -> np.ndarray:
    gx, gy = XS % 18, YS % 18
    shade = 1.0 + 0.03 * periodic_noise(seed) + 0.02 * fine_noise(seed + 1)
    rgb = colour((222, 206, 172), shade)
    seam = (gx == 0) | (gy == 0)
    rgb[seam] = (176, 138, 62)          # gold inlay
    edge = (gx == 1) | (gy == 1)
    rgb[edge] = np.minimum(255, rgb[edge] * 1.05)
    return rgb


def top_rock(seed: int) -> np.ndarray:
    shade = 1.0 + 0.16 * periodic_noise(seed) + 0.06 * fine_noise(seed + 1)
    # Cracks: thin dark lines where a second noise field crosses zero.
    crack = np.abs(periodic_noise(seed + 7, ((2, 2, 1.0), (4, 3, 0.5)))) < 0.035
    shade = np.where(crack, shade * 0.62, shade)
    return colour((112, 110, 106), shade)


def top_timber(seed: int) -> np.ndarray:
    row = YS // 12
    gy = YS % 12
    joint = ((XS - 18 * (row % 3)) % PX) == 0
    grain = 0.06 * np.cos(2 * np.pi * (XS / PX * 3) + row * 1.7)
    shade = 1.0 + grain + 0.05 * fine_noise(seed + 1) + 0.03 * periodic_noise(seed)
    shade = np.where(gy == 0, 0.5, np.where(gy == 11, shade * 0.85, np.where(gy == 1, shade * 1.15, shade)))
    shade = np.where(joint, 0.55, shade)
    return colour((104, 72, 44), shade)


TOPS = {"bulkhead": top_bulkhead, "colony": top_colony, "palace": top_palace, "rock": top_rock,
        "timber": top_timber}


def top_image(family: str, variant: int) -> Image.Image:
    rgb = TOPS[family](100 + 17 * variant)
    a = np.where(hex_mask(), 255, 0)
    return Image.fromarray(np.dstack([rgb, a]).astype(np.uint8), "RGBA")


# --- Front faces ------------------------------------------------------------

FACE = {   # base colour of the vertical face, and its pattern
    "bulkhead": ((52, 58, 68), "ribs"),
    "colony": ((112, 110, 104), "courses"),
    "palace": ((170, 152, 118), "courses"),
    "rock": ((74, 72, 69), "rough"),
    "timber": ((70, 47, 28), "planks"),
    "bunker": ((52, 58, 68), "ribs"),
}


def face_rgb(family: str, t: np.ndarray, seed: int = 5) -> np.ndarray:
    """Face colour at height t (0 = foot, 1 = top lip)."""
    base, pattern = FACE[family]
    shade = 0.78 + 0.32 * t           # light falls from above: brighter near the top
    if pattern == "ribs":
        shade = shade * np.where(XS % 6 == 0, 0.7, np.where(XS % 6 == 1, 1.15, 1.0))
    elif pattern == "courses":
        shade = shade * np.where((YS % 7) == 0, 0.8, 1.0)
    elif pattern == "planks":
        shade = shade * np.where((XS % 9) == 0, 0.65, 1.0)
    else:
        shade = shade * (1.0 + 0.12 * periodic_noise(seed))
    shade = shade + 0.03 * fine_noise(seed)
    return colour(base, shade)


def relief(family: str, direction: str, height: float = 1.0) -> Image.Image:
    inside = hex_mask()
    d = edge_distance(direction)
    out = np.zeros((S, S, 4))
    if direction in SOUTH:
        depth = max(5, round(SOUTH[direction] * height))
        t = np.clip(d / depth, 0, 1)
        rgb = face_rgb(family, t)
        band = inside & (d >= 0) & (d < depth)
        foot = inside & (d >= 0) & (d < 1.2)
        lip = inside & (d >= depth - 0.2) & (d < depth + 1.8)
        # The lip where the top ends: the top's own colour, a little brighter.
        top = TOPS.get(family, TOPS["bulkhead"])(117)
        rgb[lip] = np.minimum(255, top[lip] * 1.15 + 10)
        rgb[foot] = (16, 16, 18)
        out[..., :3] = rgb
        out[..., 3] = np.where(band | lip, 255, 0)
    else:
        # The far edge: the top's own colour, a little brighter where the
        # coping catches the light, outlined in near-black.
        rim = inside & (d >= 0) & (d < NORTH[direction])
        outline = inside & (d >= 0) & (d < 1.1)
        top = TOPS.get(family, TOPS["bulkhead"])(117)
        rgb = np.minimum(255, top * 1.18 + 12)
        rgb[outline] = (16, 16, 18)
        out[..., :3] = rgb
        out[..., 3] = np.where(rim, 255, 0)
    return Image.fromarray(out.astype(np.uint8), "RGBA")


def shadow(direction: str) -> Image.Image:
    out = np.zeros((S, S, 4), dtype=np.uint8)
    if direction in NORTH:
        reach = 18 if direction == "n" else 11
        d = edge_distance(direction)
        alpha = np.clip(1 - d / reach, 0, 1) ** 1.5 * 140
        alpha = np.where(hex_mask() & (d >= 0), alpha, 0)
        out[..., 3] = alpha.astype(np.uint8)
    return Image.fromarray(out, "RGBA")


def main() -> int:
    n = 0
    for family, (stem, variants) in FAMILIES.items():
        for v in range(1, variants + 1):
            top_image(family, v).save(OUT / f"{stem}{'' if v == 1 else v}.png", optimize=True)
            n += 1
    for family in list(FAMILIES) + ["bunker"]:
        for direction in EDGES:
            relief(family, direction, HEIGHT.get(family, 1.0)).save(
                OUT / f"wall-relief-{family}-{direction}.png", optimize=True)
            n += 1
    for direction in EDGES:
        shadow(direction).save(OUT / f"wall-shadow-{direction}.png", optimize=True)
        n += 1
    print(f"wrote {n} wall images")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
