#!/usr/bin/env python3
"""Import unit sprites from SacraiCross's Star Wars collection sheet.

Character sprites by SacraiCross, "Star Wars Collection - Complete v6",
https://www.deviantart.com/sacraicross/art/Star-Wars-Collection---Complete-v6-941875516
used under CC BY-SA, confirmed by the artist to the project owner
(docs/ART_CREDITS.md).

The sheet itself is not part of the repository: it carries franchise
branding and hundreds of characters we do not use. Only the extracted
sprites of the mapped units are written.

For each unit in sheet_sprite_map.json ({unit_id: {"at": [x, y], ...}};
optional "keep_radius", "close" and "erase", see extract and closed_background;
"skip" lists a unit whose cut-out is not yet clean enough to import):
  1. crop around the given point on the sheet;
  2. remove the background: the light, unsaturated marble and the grey
     guide lines, flood-filled from the crop border (a sprite's dark outline
     stops the fill, so white armour inside it is kept);
  3. keep the character: the largest connected sprite area near the point,
     plus anything touching it (a lightsaber blade, a held weapon) -- other
     characters and effects reaching into the crop are dropped;
  4. scale to fit the 72x72 unit frame (the sheet's characters are ~90 px
     tall) and derive the 12 animation frames like every other unit
     (derive_unit_frames.derive). The unit's portrait is kept.

Usage (art Python):
  import_sheet_sprites.py --sheet SHEET.png [--only UNIT_ID ...] [--preview OUT.png]
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import deque
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from derive_unit_frames import degenerate_reason, derive  # noqa: E402

MAP = Path(__file__).resolve().parent / "sheet_sprite_map.json"
UNITS = ROOT / "addons/Star_Wars_Thrawn_Trilogy/images/units"
CROP = 75            # half-size of the search crop around the mapped point
SPRITE = 72
MAX_H, MAX_W = 66, 70
# Hand-drawn pixel sprites use a small palette; the painted-art floor of
# derive_unit_frames would reject them. Still catches blank or flat cut-outs.
PIXEL_ART_MIN_COLORS = 12


def background_mask(rgb: np.ndarray) -> np.ndarray:
    """Pixels that look like the sheet background: the marble (light grey,
    unsaturated) or the guide lines drawn over it (mid grey)."""
    mx, mn = rgb.max(-1), rgb.min(-1)
    return ((mx - mn) <= 26) & (mx >= 88)


def flood_from_border(candidate: np.ndarray) -> np.ndarray:
    h, w = candidate.shape
    seen = np.zeros_like(candidate, dtype=bool)
    q: deque = deque()
    border = [(y, x) for x in range(w) for y in (0, h - 1)] + [(y, x) for y in range(h) for x in (0, w - 1)]
    for y, x in border:
        if candidate[y, x] and not seen[y, x]:
            seen[y, x] = True
            q.append((y, x))
    while q:
        y, x = q.popleft()
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            ny, nx = y + dy, x + dx
            if 0 <= ny < h and 0 <= nx < w and candidate[ny, nx] and not seen[ny, nx]:
                seen[ny, nx] = True
                q.append((ny, nx))
    return seen


def _grow(mask: np.ndarray, steps: int, diagonal: bool = False) -> np.ndarray:
    for _ in range(steps):
        g = mask.copy()
        g[1:] |= mask[:-1]
        g[:-1] |= mask[1:]
        g[:, 1:] |= mask[:, :-1]
        g[:, :-1] |= mask[:, 1:]
        if diagonal:
            g[1:, 1:] |= mask[:-1, :-1]
            g[1:, :-1] |= mask[:-1, 1:]
            g[:-1, 1:] |= mask[1:, :-1]
            g[:-1, :-1] |= mask[1:, 1:]
        mask = g
    return mask


def closed_background(candidate: np.ndarray, close: int) -> np.ndarray:
    """Background fill for white sprites on the white marble (armour, gowns),
    whose dark outline has gaps the plain fill leaks through: the outline is
    thickened by `close` px to seal the gaps, the background is flooded, then
    allowed to regrow `close` px so no marble halo is left around the
    sprite. A leak can reach at most `close` px into the sprite."""
    sealed = flood_from_border(candidate & ~_grow(~candidate, close, diagonal=True))
    return _grow(sealed, close, diagonal=True) & candidate


def components(mask: np.ndarray) -> np.ndarray:
    """8-connected component labels (0 = background)."""
    h, w = mask.shape
    labels = np.zeros((h, w), dtype=int)
    n = 0
    for y in range(h):
        for x in range(w):
            if mask[y, x] and not labels[y, x]:
                n += 1
                labels[y, x] = n
                q = deque([(y, x)])
                while q:
                    cy, cx = q.popleft()
                    for dy in (-1, 0, 1):
                        for dx in (-1, 0, 1):
                            ny, nx = cy + dy, cx + dx
                            if 0 <= ny < h and 0 <= nx < w and mask[ny, nx] and not labels[ny, nx]:
                                labels[ny, nx] = n
                                q.append((ny, nx))
    return labels


def extract(sheet: Image.Image, at: tuple[int, int], keep_radius: int = 2, close: int = 0,
            erase: list[list[int]] = ()) -> Image.Image:
    x, y = at
    box = (max(0, x - CROP), max(0, y - CROP), min(sheet.width, x + CROP), min(sheet.height, y + CROP))
    crop = np.asarray(sheet.crop(box).convert("RGBA")).copy()
    # Sheet boxes [x0, y0, x1, y1] holding a prop or creature that touches the
    # character (a set-down helmet, a pet) and would otherwise be kept with it.
    for x0, y0, x1, y1 in erase:
        crop[max(0, y0 - box[1]):max(0, y1 - box[1]), max(0, x0 - box[0]):max(0, x1 - box[0]), 3] = 0
    candidate = background_mask(crop[..., :3].astype(int))
    removed = closed_background(candidate, close) if close else flood_from_border(candidate)
    labels = components(~removed & (crop[..., 3] > 0))
    cy, cx = y - box[1], x - box[0]
    near = labels[max(0, cy - 25):cy + 25, max(0, cx - 20):cx + 20]
    ids = np.unique(near[near > 0])
    if len(ids) == 0:
        raise SystemExit(f"no sprite near {at}")
    main = max(ids, key=lambda i: int((labels == i).sum()))
    keep = labels == main
    grown = _grow(keep, keep_radius)
    for i in np.unique(labels[grown & (labels > 0)]):
        if i != main and (labels == i).sum() >= 3:
            keep |= labels == i
    crop[~keep, 3] = 0
    img = Image.fromarray(crop.astype(np.uint8), "RGBA")
    return img.crop(img.getbbox())


def fit(img: Image.Image) -> Image.Image:
    scale = min(MAX_H / img.height, MAX_W / img.width, 1.0)
    if scale < 1.0:
        img = img.resize((max(1, round(img.width * scale)), max(1, round(img.height * scale))), Image.LANCZOS)
    out = Image.new("RGBA", (SPRITE, SPRITE), (0, 0, 0, 0))
    out.alpha_composite(img, ((SPRITE - img.width) // 2, SPRITE - 2 - img.height))
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sheet", type=Path, required=True)
    parser.add_argument("--only", action="append")
    parser.add_argument("--preview", type=Path, help="write a review sheet instead of unit frames")
    args = parser.parse_args()
    sheet = Image.open(args.sheet).convert("RGBA")
    mapping = json.loads(MAP.read_text(encoding="utf-8"))
    previews = []
    for unit_id in [u for u in mapping if not args.only or u in args.only]:
        entry = mapping[unit_id]
        if entry.get("skip") and not args.only:
            print(f"{unit_id}: skipped: {entry['skip']}")
            continue
        base = fit(extract(sheet, tuple(entry["at"]), entry.get("keep_radius", 2), entry.get("close", 0),
                           entry.get("erase", [])))
        reason = degenerate_reason(base, PIXEL_ART_MIN_COLORS)
        if args.preview:
            if reason:
                print(f"{unit_id}: degenerate sprite: {reason}")
            previews.append((unit_id, base))
            continue
        if reason:
            raise SystemExit(f"{unit_id}: degenerate sprite: {reason}")
        unit_dir = UNITS / unit_id.replace("_", "-")
        if not unit_dir.is_dir():
            raise SystemExit(f"{unit_id}: no art folder {unit_dir}")
        for state, frame in derive(base).items():
            frame.save(unit_dir / f"{state}.png", optimize=True)
        print(f"{unit_id}: frames written")
    if args.preview:
        scale, cols = 3, 6
        rows = (len(previews) + cols - 1) // cols
        out = Image.new("RGBA", (cols * SPRITE * scale, rows * (SPRITE * scale + 14)), (70, 90, 60, 255))
        for i, (unit_id, img) in enumerate(previews):
            x, y = (i % cols) * SPRITE * scale, (i // cols) * (SPRITE * scale + 14)
            out.alpha_composite(img.resize((SPRITE * scale, SPRITE * scale), Image.NEAREST), (x, y + 14))
            ImageDraw.Draw(out).text((x + 2, y + 1), unit_id.replace("sw_", ""), fill=(255, 255, 0, 255))
        out.save(args.preview)
        print(f"preview of {len(previews)} units: {args.preview}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
