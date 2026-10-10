#!/usr/bin/env python3
"""Draw relief edges that make interior walls read as raised walls.

Walls (timber, duracrete, palace, hewn rock, starship bulkheads) were flat
textures the same height as the floor beside them, so a wall looked like a
different floor (environment review 2026-10-10). Edge pieces are drawn from
each wall's own texture:

  sw/wall-relief-<family>-<dir>.png  on a wall hex, along an edge where it
      meets floor: to the south (s, se, sw) the wall's vertical face, darker,
      with a bright lip where the top surface ends; to the north (n, ne, nw)
      a light rim on the top surface.
  (bunker: the castle hexes of a command bunker, a low parapet.)
  sw/wall-shadow-<dir>.png  on a floor hex, along an edge shared with a wall
      to its north (n, ne, nw): the shadow the wall casts. Other directions
      are blank.

utils/hte_terrain.cfg (SW_WALL_RELIEF) places them; neighbouring walls get
no edge between them, so a run of wall hexes reads as one raised mass.

Usage (art Python): gen_wall_relief.py
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parents[2] / "addons/Star_Wars_Thrawn_Trilogy/images/terrain/sw"
FAMILIES = {"timber": "wall-timber", "colony": "wall-colony", "palace": "wall-palace", "rock": "wall-rock",
            "bulkhead": "bulkhead", "bunker": "bunker"}
# Height of each family's face relative to a full wall: bunker aprons (the
# castle hexes round a command bunker) get a low parapet, so the recruiting
# footprint stands out without reading as an impassable wall.
HEIGHT = {"bunker": 0.45}
S = 72
# Hex corners (flat top) and each edge's endpoints.
CORNERS = {"nw": (18, 0), "ne": (54, 0), "e": (72, 36), "se": (54, 72), "sw": (18, 72), "w": (0, 36)}
EDGES = {"n": ("nw", "ne"), "ne": ("ne", "e"), "se": ("e", "se"), "s": ("se", "sw"), "sw": ("sw", "w"),
         "nw": ("w", "nw")}
SOUTH = {"s": 16, "se": 11, "sw": 11}   # face depth in pixels, deepest straight below
NORTH = {"n": 3, "ne": 3, "nw": 3}
CENTRE = np.array([36.0, 36.0])


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
    ys, xs = np.mgrid[0:S, 0:S]
    pts = np.dstack([xs + 0.5, ys + 0.5])
    return (pts - a) @ normal


def wall_texture(stem: str) -> np.ndarray:
    return np.asarray(Image.open(OUT / f"{stem}.png").convert("RGBA").resize((S, S))).astype(float)


def relief(stem: str, direction: str, height: float = 1.0) -> Image.Image:
    tex = wall_texture(stem)
    inside = hex_mask()
    d = edge_distance(direction)
    out = np.zeros((S, S, 4))
    if direction in SOUTH:
        depth = max(4, round(SOUTH[direction] * height))
        band = inside & (d >= 0) & (d < depth)
        # The vertical face: the wall's own texture, darkened and graded so
        # it is darkest at the foot, with faint vertical courses.
        t = np.clip(d / depth, 0, 1)                    # 0 at the foot (edge), 1 at the top lip
        shade = 0.42 + 0.22 * t
        xs = np.arange(S)[None, :].repeat(S, 0)
        courses = np.where((xs % 9) == 0, 0.85, 1.0)
        rgb = tex[..., :3] * (shade * courses)[..., None]
        lip = inside & (d >= depth - 1.6) & (d < depth + 0.6)
        rgb[lip] = np.minimum(255, tex[..., :3][lip] * 1.35 + 18)
        out[..., :3] = rgb
        out[..., 3] = np.where(band | lip, 255, 0)
    else:
        rim = inside & (d >= 0) & (d < NORTH[direction])
        out[..., :3] = np.minimum(255, tex[..., :3] * 1.3 + 25)
        out[..., 3] = np.where(rim, 200, 0)
    return Image.fromarray(out.astype(np.uint8), "RGBA")


def shadow(direction: str) -> Image.Image:
    out = np.zeros((S, S, 4), dtype=np.uint8)
    if direction in NORTH:
        reach = 16 if direction == "n" else 10
        d = edge_distance(direction)
        alpha = np.clip(1 - d / reach, 0, 1) ** 1.6 * 120
        alpha = np.where(hex_mask() & (d >= 0), alpha, 0)
        out[..., 3] = alpha.astype(np.uint8)
    return Image.fromarray(out, "RGBA")


def main() -> int:
    for family, stem in FAMILIES.items():
        for direction in EDGES:
            relief(stem, direction, HEIGHT.get(family, 1.0)).save(OUT / f"wall-relief-{family}-{direction}.png", optimize=True)
    for direction in EDGES:
        shadow(direction).save(OUT / f"wall-shadow-{direction}.png", optimize=True)
    print(f"wrote {len(FAMILIES) * len(EDGES) + len(EDGES)} relief images")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
