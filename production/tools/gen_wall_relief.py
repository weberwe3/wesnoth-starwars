#!/usr/bin/env python3
"""Draw every wall's art: walls as solid raised blocks, cut into per-hex pieces.

Owner direction (2026-10-12): walls looked malformed -- each wall hex showed
its own hex-shaped plate, so a run of wall hexes read as a honeycomb of
separate tiles rather than one wall. Walls must look like walls, be identified
at a glance, and the player-facing side of conjoined wall hexes must read as
one uniform face with clean corners where it turns.

The engine cuts every terrain image to its own hex (picture.cpp: HEXED, the
binary terrain/alphamask.png), so no image can reach into a neighbouring hex.
An earlier version drew each wall's faces inside its own hex, with a
"reaching" image for inside corners; the game clipped that reach away, and
faces ended in wedges at the hex corners (owner report 2026-10-12).

So the wall is drawn as what it is: every wall hex is a block of height H.
Its top is the hex lifted H pixels up the screen; its front faces are the
south edges (s, se, sw) raised H pixels, wherever the hex beyond is floor.
The block's image is then cut along the hex grid: each hex shows exactly the
part of the picture that falls inside it. Since a block only reaches up the
screen, by less than half a hex, what a hex X shows depends on four hexes
only: X and its s, se and sw neighbours, each wall or not -- sixteen cases.
For each wall family and each owner (the hex whose block a piece belongs to:
c = X itself, s, se, sw) the piece is drawn for each case:

    sw/wall-<family>-<owner>-<c><s><se><sw>.png     (1 = wall, 0 = floor)

and utils/sw_wall_relief.cfg (generated here) places it on X when X and its
three neighbours match. Pieces of one case never overlap, so the lines of
neighbouring blocks -- the silhouette outline, the lip where the top meets a
face, the foot, the face's vertical ends -- are drawn once, in one picture,
and meet exactly at the corners. Faces of the same block turning a corner
are shaded a little differently, so the corner reads as a crisp crease.

1. Tops (also the base images sw/<stem>.png and its numbered variants, placed
   by NEW:BASE in utils/hte_terrain.cfg). Every hex at column c, row r is
   drawn at x = 54c, y = 72r + 36(c mod 2), so a pattern that repeats every
   54 px across and every 36 px down continues unbroken from hex to hex:
   plate seams, block courses and plank rows run straight through a whole
   wall. Nothing is centred on the hex.

     bulkhead  dark blue-grey steel plates (18 px) with seams and rivets
     colony    pale duracrete blocks (18 px) in a running bond
     palace    polished sandstone slabs (18 px) with gold inlay seams
     rock      rough grey stone (periodic noise and cracks, no seams)
     timber    dark log planks in 12 px rows with staggered joints

2. Shadows (sw/wall-shadow-<dir>.png), on a floor hex along an edge shared
   with a wall to its north: the soft shadow at the foot of the wall.

3. The bunker apron (Qcb, the castle round a command bunker) keeps a low
   parapet inside its own hex (sw/wall-relief-bunker-<dir>.png).

Usage (art Python): gen_wall_relief.py
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[2]
ADDON = ROOT / "addons/Star_Wars_Thrawn_Trilogy"
OUT = ADDON / "images/terrain/sw"
CFG = ADDON / "utils/sw_wall_relief.cfg"
ENGINE_MASK = Path.home() / "opt/wesnoth-1.19.27/data/core/images/terrain/alphamask.png"
S = 72
PX, PY = 54, 36          # lattice periods: one hex column across, half a hex down
H = 20                   # wall height in screen pixels
K = 4                    # supersampling for clean slanted edges
# family -> (terrain code, top image stem, variant count)
FAMILIES = {"timber": ("Qwt", "wall-timber", 2), "colony": ("Qwc", "wall-colony", 2),
            "palace": ("Qwp", "wall-palace", 2), "rock": ("Qwr", "wall-rock", 2),
            "bulkhead": ("Qib", "bulkhead", 3)}
WALL_CODES = ",".join(code for code, _stem, _n in FAMILIES.values())
CORNERS = {"nw": (18, 0), "ne": (54, 0), "e": (72, 36), "se": (54, 72), "sw": (18, 72), "w": (0, 36)}
EDGES = {"n": ("nw", "ne"), "ne": ("ne", "e"), "se": ("e", "se"), "s": ("se", "sw"), "sw": ("sw", "w"),
         "nw": ("w", "nw")}
# Where each neighbour sits, as the offset of its hex's top-left corner.
STEP = {"n": (0, -72), "ne": (54, -36), "se": (54, 36), "s": (0, 72), "sw": (-54, 36), "nw": (-54, -36)}
OWNERS = ("c", "s", "se", "sw")          # the hexes whose blocks can show in hex X
OFFSET = {"c": (0, 0), "s": STEP["s"], "se": STEP["se"], "sw": STEP["sw"]}
CENTRE = np.array([36.0, 36.0])
YS, XS = np.mgrid[0:S, 0:S]


def hex_mask() -> np.ndarray:
    """The pixels of a hex, exactly as the engine cuts terrain images."""
    if ENGINE_MASK.exists():
        return np.asarray(Image.open(ENGINE_MASK).convert("RGBA"))[..., 3] > 0
    m = Image.new("L", (S, S), 0)
    ImageDraw.Draw(m).polygon([CORNERS[k] for k in ("nw", "ne", "e", "se", "sw", "w")], fill=255)
    return np.asarray(m) > 0


def edge_distance(direction: str, xs=None, ys=None) -> np.ndarray:
    """Distance of every point from the given edge, measured towards the centre."""
    xs = XS + 0.5 if xs is None else xs
    ys = YS + 0.5 if ys is None else ys
    a, b = (np.array(CORNERS[k], float) for k in EDGES[direction])
    normal = np.array([-(b - a)[1], (b - a)[0]])
    normal /= np.linalg.norm(normal)
    if np.dot(CENTRE - a, normal) < 0:
        normal = -normal
    return (xs - a[0]) * normal[0] + (ys - a[1]) * normal[1]


def in_mask(u: np.ndarray, v: np.ndarray) -> np.ndarray:
    """Points relative to a hex's top-left corner on the pixels the engine
    gives that hex."""
    ui, vi = np.floor(u).astype(int), np.floor(v).astype(int)
    ok = (ui >= 0) & (ui < S) & (vi >= 0) & (vi < S)
    return ok & hex_mask()[np.clip(vi, 0, S - 1), np.clip(ui, 0, S - 1)]


def in_hex(u: np.ndarray, v: np.ndarray) -> np.ndarray:
    """Points (u, v), relative to a hex's top-left corner, inside that hex."""
    return (v >= 0) & (v < S) & (2 * np.minimum(u, S - u) >= np.abs(v - 36))


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


def periodic_sample(field: np.ndarray, x: np.ndarray, y: np.ndarray) -> np.ndarray:
    """Look up a lattice-periodic field (computed on the 72 x 72 grid) at any
    pixel position, so a texture stays fixed to the map wherever it is drawn."""
    return field[np.floor(y).astype(int) % PY, np.floor(x).astype(int) % PX]


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
TOP_SEED = 117


def top_image(family: str) -> Image.Image:
    """The base image of a wall hex: its block's top, lifted H pixels (the
    pieces cover it; it shows where a wall meets impassable terrain)."""
    tex = TOPS[family](TOP_SEED)
    rgb = periodic_sample(tex, XS, YS + H)
    a = np.where(hex_mask(), 255, 0)
    return Image.fromarray(np.dstack([rgb, a]).astype(np.uint8), "RGBA")


# --- Faces ------------------------------------------------------------------

FACE = {   # base colour of the vertical face, and its pattern
    "bulkhead": ((52, 58, 68), "ribs"),
    "colony": ((112, 110, 104), "courses"),
    "palace": ((170, 152, 118), "courses"),
    "rock": ((74, 72, 69), "rough"),
    "timber": ((70, 47, 28), "planks"),
    "bunker": ((52, 58, 68), "ribs"),
}
# Each face direction catches the light differently, so where two faces meet
# at an angle the corner reads as a clean crease.
TURN = {"s": 1.0, "se": 0.8, "sw": 0.9}
# The foot of each front face: the hex edge as y = f(x) over its x range.
FOOT = {
    "s": (18, 54, lambda x: np.full_like(x, 72.0)),
    "se": (54, 72, lambda x: 72.0 - 2.0 * (x - 54)),
    "sw": (0, 18, lambda x: 36.0 + 2.0 * x),
}


def face_colour(family: str, x: np.ndarray, h: np.ndarray, height: float, turn: float) -> np.ndarray:
    """Face colour at map pixel column x, h pixels above the foot."""
    base, pattern = FACE[family]
    t = np.clip(h / height, 0, 1)
    shade = (0.78 + 0.32 * t) * turn     # light falls from above: brighter near the top
    xi = np.floor(x).astype(int)
    if pattern == "ribs":
        shade = shade * np.where(xi % 6 == 0, 0.7, np.where(xi % 6 == 1, 1.15, 1.0))
    elif pattern == "courses":
        # Courses run parallel to the foot, so they continue round corners.
        shade = shade * np.where(np.floor(h).astype(int) % 7 == 0, 0.8, 1.0)
    elif pattern == "planks":
        shade = shade * np.where(xi % 9 == 0, 0.65, 1.0)
    else:
        shade = shade * (1.0 + 0.12 * periodic_sample(periodic_noise(5), x, h))
    shade = shade + 0.03 * periodic_sample(fine_noise(5), x, h)
    return np.clip(np.array(base, float) * shade[..., None], 0, 255)


DARK = np.array([16.0, 16.0, 18.0])


def render_case(family: str, walls: dict) -> dict:
    """Draw the blocks that show in hex X for one case, cut to X.

    walls: (dx, dy) hex offset -> True for a wall. Hexes not listed are floor.
    Returns owner -> RGBA piece (72 x 72); empty pieces are left out.

    Blocks are painted from the back (north) to the front (south): each
    block's top, then its faces, so a block in front hides what it should."""
    n = S * K
    ys, xs = np.mgrid[0:n, 0:n]
    x = (xs + 0.5) / K
    y = (ys + 0.5) / K
    rgb = np.zeros((n, n, 3))
    owner = np.full((n, n), -1)
    tex = TOPS[family](TOP_SEED)
    top_rgb = periodic_sample(tex, x, y + H)

    def wall(off):
        return walls.get(off, False)

    for idx, name in sorted(enumerate(OWNERS), key=lambda p: OFFSET[p[1]][1]):
        ox, oy = OFFSET[name]
        if not wall((ox, oy)):
            continue
        nb = {d: wall((ox + sx, oy + sy)) for d, (sx, sy) in STEP.items()}
        u, v = x - ox, y - oy                        # relative to the block's hex
        # Top: the hex lifted H.
        top = in_hex(u, v + H)
        col = top_rgb.copy()
        for d in ("n", "ne", "nw", "s", "se", "sw"):
            if nb[d]:
                continue                              # the top runs on into the next block
            dist = edge_distance(d, u, v + H)
            if d in ("n", "ne", "nw"):                # silhouette: coping, outlined
                col = np.where((top & (dist < 3.0))[..., None], np.minimum(255, top_rgb * 1.18 + 12), col)
                col = np.where((top & (dist < 1.0))[..., None], DARK, col)
            else:                                     # lip above a face
                col = np.where((top & (dist < 1.6))[..., None], np.minimum(255, top_rgb * 1.15 + 10), col)
        rgb[top] = col[top]
        owner[top] = idx
        # Faces: each south edge with floor beyond, raised H.
        for d in ("s", "se", "sw"):
            if nb[d]:
                continue
            x0, x1, foot = FOOT[d]
            within = (u >= x0) & (u <= x1)
            h = foot(np.clip(u, x0, x1)) - v
            face = within & (h >= -1.0) & (h <= H)   # to the edge of the engine's hex mask
            col = face_colour(family, x, h, H, TURN[d])
            col = np.where((h < 1.0)[..., None], DARK, col)
            # Vertical end of the face where the wall's outline turns away
            # (the north edge at that corner looks onto floor): an outline.
            # Drawn only outside the block's own hex, where it shows.
            ends = []
            if d == "se" and not nb["ne"]:
                ends.append(u > x1 - 1.0)
            if d == "sw" and not nb["nw"]:
                ends.append(u < x0 + 1.0)
            for end in ends:
                col = np.where((end & ~in_mask(u, v))[..., None], DARK, col)
            rgb[face] = col[face]
            owner[face] = idx
    # Down to screen pixels. A pixel covered by several blocks goes to the
    # block covering most of it, so neighbouring pieces never overlap; only
    # the outer outline is soft.
    cover = (owner >= 0).reshape(S, K, S, K).mean(axis=(1, 3))
    rgb_avg = (rgb * (owner >= 0)[..., None]).reshape(S, K, S, K, 3).sum(axis=(1, 3))
    rgb_avg = rgb_avg / np.maximum(cover * K * K, 1e-9)[..., None]
    counts = np.stack([(owner == i).reshape(S, K, S, K).sum(axis=(1, 3)) for i in range(len(OWNERS))])
    best = counts.argmax(axis=0)
    mask = hex_mask()
    out = {}
    for i, name in enumerate(OWNERS):
        mine = (best == i) & (cover > 0) & mask
        if not mine.any():
            continue
        img = np.zeros((S, S, 4))
        img[..., :3] = np.where(mine[..., None], rgb_avg, 0)
        img[..., 3] = np.where(mine, np.round(cover * 255), 0)
        out[name] = Image.fromarray(np.clip(img, 0, 255).astype(np.uint8), "RGBA")
    return out


def cases():
    """Every combination of X, s, se, sw being wall (1) or floor (0)."""
    for bits in range(16):
        flags = tuple(bool(bits >> (3 - i) & 1) for i in range(4))
        yield "".join("1" if f else "0" for f in flags), dict(zip(OWNERS, flags))


# --- Bunker parapet (inside its own hex) ------------------------------------

def bunker_face(direction: str, height: float) -> Image.Image:
    face_h = max(5, round(22 * height))
    x0, x1, foot = FOOT[direction]
    xc, yc = XS + 0.5, YS + 0.5
    within = (xc >= x0) & (xc <= x1)
    h = foot(np.clip(xc, x0, x1)) - yc
    region = within & (h > 0) & (h <= face_h) & hex_mask()
    rgb = face_colour("bunker", xc, h, face_h, TURN[direction])
    lip = within & (h > face_h) & (h <= face_h + 1.8) & hex_mask()
    top = TOPS["bulkhead"](TOP_SEED)
    rgb[lip] = np.minimum(255, top[lip] * 1.15 + 10)
    rgb[region & (h <= 1.2)] = DARK
    out = np.zeros((S, S, 4))
    out[..., :3] = rgb
    out[..., 3] = np.where(region | lip, 255, 0)
    return Image.fromarray(out.astype(np.uint8), "RGBA")


def bunker_relief(direction: str, height: float = 0.45) -> Image.Image:
    if direction in FOOT:
        return bunker_face(direction, height)
    inside = hex_mask()
    d = edge_distance(direction)
    rim = inside & (d >= 0) & (d < 3)
    outline = inside & (d >= 0) & (d < 1.1)
    rgb = np.minimum(255, TOPS["bulkhead"](TOP_SEED) * 1.18 + 12)
    rgb[outline] = DARK
    out = np.zeros((S, S, 4))
    out[..., :3] = rgb
    out[..., 3] = np.where(rim, 255, 0)
    return Image.fromarray(out.astype(np.uint8), "RGBA")


def shadow(direction: str) -> Image.Image:
    out = np.zeros((S, S, 4), dtype=np.uint8)
    if direction in ("n", "ne", "nw"):
        reach = 18 if direction == "n" else 11
        d = edge_distance(direction)
        alpha = np.clip(1 - d / reach, 0, 1) ** 1.5 * 140
        alpha = np.where(hex_mask() & (d >= 0), alpha, 0)
        out[..., 3] = alpha.astype(np.uint8)
    return Image.fromarray(out, "RGBA")


# --- Placement rules --------------------------------------------------------

CFG_HEAD = """\
# GENERATED by production/tools/gen_wall_relief.py -- do not edit by hand.
#
# Walls are drawn as solid blocks cut along the hex grid. A hex X shows the
# pieces of the blocks on X and on its s, se and sw neighbours; each rule
# below places one block's piece on X for one combination of those four
# hexes being wall or floor (see gen_wall_relief.py). Impassable terrain and
# the map border count as solid, so no face is drawn against them, and no
# piece is drawn onto them.
"""
# Pattern: 1 = X, 2 = its sw neighbour, 3 = se, 4 = s.
CFG_MAP = 'map="\n, *\n* , *\n, 1\n2 , 3\n, 4"'
POS = {"c": 1, "sw": 2, "se": 3, "s": 4}


def rules(placed: dict) -> str:
    solid = f"{WALL_CODES},X*,_off^_usr"
    floor = f"!,{solid}"
    out = [CFG_HEAD]
    for family, (code, _stem, _n) in FAMILIES.items():
        for key, name in placed[family]:
            flags = dict(zip(OWNERS, (ch == "1" for ch in key)))
            out.append("[terrain_graphics]\n    " + CFG_MAP + "\n")
            for pos_name in ("c", "sw", "se", "s"):
                if pos_name == name:
                    types = code
                elif flags[pos_name]:
                    types = WALL_CODES if pos_name == "c" else solid
                else:
                    types = floor
                out.append(f"    [tile]\n        pos={POS[pos_name]}\n        type={types}\n")
                if pos_name == "c":
                    out.append(f"        [image]\n            name=sw/wall-{family}-{name}-{key}.png\n"
                               f"            layer=-400\n        [/image]\n")
                out.append("    [/tile]\n")
            out.append("[/terrain_graphics]\n")
    return "".join(out)


def main() -> int:
    n = 0
    for old in OUT.glob("wall-relief-*.png"):
        if not old.name.startswith("wall-relief-bunker-") or old.name.endswith("-ext.png"):
            old.unlink()
    for old in OUT.glob("wall-*-*-[01][01][01][01].png"):
        old.unlink()
    placed = {}
    for family, (_code, stem, variants) in FAMILIES.items():
        img = top_image(family)
        for v in range(1, variants + 1):
            img.save(OUT / f"{stem}{'' if v == 1 else v}.png", optimize=True)
            n += 1
        placed[family] = []
        for key, flags in cases():
            walls = {OFFSET[o]: f for o, f in flags.items()}
            for name, piece in render_case(family, walls).items():
                piece.save(OUT / f"wall-{family}-{name}-{key}.png", optimize=True)
                placed[family].append((key, name))
                n += 1
    for direction in EDGES:
        bunker_relief(direction).save(OUT / f"wall-relief-bunker-{direction}.png", optimize=True)
        shadow(direction).save(OUT / f"wall-shadow-{direction}.png", optimize=True)
        n += 2
    CFG.write_text(rules(placed), encoding="utf-8")
    print(f"wrote {n} wall images and {sum(map(len, placed.values()))} placement rules")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
