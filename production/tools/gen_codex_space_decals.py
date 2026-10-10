#!/usr/bin/env python3
"""Have Codex paint decorative details for open-space hexes.

Open space (Qsp) was a dark, featureless starfield across every space
mission. Codex paints one sheet of six space details on pure black (a nebula
wisp, a distant ringed planet, a star cluster, a spiral galaxy, a glowing gas
cloud, a small moon); this tool cuts the 3x2 grid, turns black into
transparency (luminance becomes alpha, so the details glow over the tile),
dims them so units stay readable, and writes images/terrain/sw/space-decal-N.png
(nebula 1, star cluster 3, galaxy 4, gas cloud 5).
utils/hte_terrain.cfg scatters them over a few open-space hexes (purely
visual; the terrain type is unchanged).

Usage (art Python): gen_codex_space_decals.py [--sheet EXISTING.png]
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gen_codex_reference_frames as g  # noqa: E402

OUT = g.ROOT / "addons/Star_Wars_Thrawn_Trilogy/images/terrain/sw"
SIZES = [144, 72, 108, 108, 144, 72]   # rendered size of each detail (px)
# The planet (2) and moon (6) are distinctive one-off objects: scattered at
# random they read as copies, so they are not installed.
UNUSED = {2, 6}
BRIGHT = [0.55, 0.85, 0.75, 0.6, 0.5, 0.85]  # peak opacity: big soft shapes stay faint

PROMPT = """Use your image generation tool to create exactly ONE image and save it as {name} in the current working directory. Do not create any other files.

A sheet of six separate deep-space details for a top-down science-fiction strategy game map, arranged in a 3 x 2 grid of equal square cells on a PURE BLACK background (#000000 everywhere outside the details), with wide black gaps so no detail touches another or the edge of its cell:
1. a soft, wispy purple-and-blue nebula cloud
2. a small distant ringed planet, softly lit from one side
3. a tight cluster of bright blue-white stars with a faint glow
4. a small distant spiral galaxy seen at an angle
5. a faint glowing teal-and-green gas cloud
6. a small grey cratered moon, lit from one side

Painterly, slightly soft, subtle colours that would sit behind game pieces; no text, no labels, no borders, no grid lines.

After saving, reply with only the file name."""


def cut(sheet: Path) -> None:
    im = np.asarray(Image.open(sheet).convert("RGB")).astype(float)
    h, w, _ = im.shape
    cw, ch = w // 3, h // 2
    for i in range(6):
        cell = im[(i // 3) * ch:(i // 3 + 1) * ch, (i % 3) * cw:(i % 3 + 1) * cw]
        lum = cell.max(axis=2)
        # Black is empty space: luminance becomes opacity; colour is unpremultiplied.
        alpha = np.clip((lum - 12) / 200, 0, 1) ** 1.2
        rgb = np.clip(cell / np.maximum(lum[..., None], 1) * 255, 0, 255)
        ys, xs = np.nonzero(alpha > 0.03)
        if len(xs) == 0:
            raise SystemExit(f"cell {i + 1} is empty")
        pad = 6
        box = (max(0, xs.min() - pad), max(0, ys.min() - pad), min(cw, xs.max() + pad), min(ch, ys.max() + pad))
        rgba = np.dstack([rgb, alpha * 255 * BRIGHT[i]]).astype(np.uint8)
        piece = Image.fromarray(rgba, "RGBA").crop(box)
        piece.thumbnail((SIZES[i], SIZES[i]), Image.LANCZOS)
        if i + 1 in UNUSED:
            continue
        piece.save(OUT / f"space-decal-{i + 1}.png")
        print(f"space-decal-{i + 1}.png {piece.size}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sheet", type=Path)
    args = parser.parse_args()
    sheet = args.sheet
    if sheet is None:
        workspace = g.codex_art._managed_directory("space-decals")
        target = workspace / "space-decals.png"
        ok, _ = g._codex_with_refs(PROMPT.format(name=target.name), [], target, "space-decals")
        if not ok:
            raise SystemExit("Codex made no image")
        sheet = g.REFERENCES / "codex-space-decals.png"
        shutil.copyfile(target, sheet)
    cut(sheet)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
