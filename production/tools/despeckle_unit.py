#!/usr/bin/env python3
"""Fill pinholes: tiny transparent gaps inside a unit's figure.

Sheets are cut from a flat green backdrop; the importer's thresholds (and
redraws that copied older frames) left one- to few-pixel transparent holes
inside some figures, so the map shows through (green specks in Chewbacca's
fur, dots in Luke's black tunic). Each enclosed transparent region of at most
MAX_HOLE pixels (not touching the frame edge) is filled from the average of
its opaque neighbours, snapped to the nearest colour already in the frame.
Larger enclosed gaps (between an arm and the body) are real and kept, as are
lattice craft whose open framework is drawn as small gaps (SKIP).

Usage (art Python): despeckle_unit.py [SLUG ...] [--all] [--dry-run]
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

UNITS = Path(__file__).resolve().parents[2] / "addons/Star_Wars_Thrawn_Trilogy/images/units"
MAX_HOLE = 4
# Dark outfits lost larger patches to the alpha cut.
MAX_HOLE_BY_UNIT = {"sw-hero-chewbacca": 10, "sw-hero-luke": 12, "sw-hero-luke-unarmed": 12, "sw-hero-luuke": 12}
# Open framework (engine nacelle cages, scaffolding, porous rock) is drawn as small gaps.
SKIP = {"sw-unit-nr-ywing", "sw-unit-ob-shipyard-platform", "sw-unit-ob-cloaked-asteroid", "human"}


def fill_holes(a: np.ndarray, max_hole: int) -> tuple[np.ndarray, int]:
    a = a.copy()
    opaque = a[..., 3] > 0
    lab, n = ndimage.label(~opaque)
    if not n:
        return a, 0
    border = set(np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]])))
    sizes = ndimage.sum(np.ones_like(lab), lab, range(1, n + 1))
    holes = np.isin(lab, [i for i in range(1, n + 1) if i not in border and sizes[i - 1] <= max_hole])
    total = int(holes.sum())
    if not total:
        return a, 0
    palette = np.unique(a[opaque][:, :3], axis=0).astype(int)
    good = opaque.copy()
    for _ in range(8):
        if not holes.any():
            break
        rgb = a[..., :3].astype(float)
        acc = np.zeros_like(rgb)
        cnt = np.zeros(holes.shape)
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if dy == dx == 0:
                    continue
                m = np.roll(np.roll(good, dy, 0), dx, 1)
                acc += np.roll(np.roll(rgb, dy, 0), dx, 1) * m[..., None]
                cnt += m
        fill = holes & (cnt > 0)
        mean = acc[fill] / cnt[fill][:, None]
        a[..., :3][fill] = palette[((mean[:, None, :] - palette[None]) ** 2).sum(-1).argmin(1)]
        a[..., 3][fill] = 255
        holes &= ~fill
        good |= fill
    return a, total


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("slugs", nargs="*")
    parser.add_argument("--all", action="store_true", help="every unit art folder (except SKIP)")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    slugs = sorted(p.name for p in UNITS.iterdir() if p.is_dir()) if args.all else args.slugs
    for slug in slugs:
        if slug in SKIP:
            continue
        fixed = 0
        for path in sorted((UNITS / slug).glob("*.png")):
            out, n = fill_holes(np.asarray(Image.open(path).convert("RGBA")),
                                MAX_HOLE_BY_UNIT.get(slug.split("-rank")[0], MAX_HOLE))
            fixed += n
            if n and not args.dry_run:
                Image.fromarray(out, "RGBA").save(path, optimize=True)
        if fixed:
            print(f"{slug}: {fixed} pinhole pixels filled{' (dry run)' if args.dry_run else ''}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
