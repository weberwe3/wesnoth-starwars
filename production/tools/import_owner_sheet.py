#!/usr/bin/env python3
"""Install a 12-frame unit sprite sheet supplied by the project owner.

The sheet shows the frames in the add-on's order, six per row on a flat
background colour, optionally with frame labels in their own rows above the
figures (dropped):

  standing idle-1 idle-2 move-1 move-2 melee-1
  melee-2 ranged-1 ranged-2 defend death-1 death-2

Every frame is scaled by the same factor (the standing figure becomes
MAX_H px tall), bottom-anchored and centred in the 72x72 unit frame like
the other unit art, and reduced to the standing figure's own palette.

Usage (art Python): import_owner_sheet.py SHEET UNIT_ID [--preview OUT.png] [--palette-from-all]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
from import_sheet_sprites import MAX_H, MAX_W, SPRITE, UNITS, components  # noqa: E402

NAMES = ["standing", "idle-1", "idle-2", "move-1", "move-2", "melee-1",
         "melee-2", "ranged-1", "ranged-2", "defend", "death-1", "death-2"]


def _runs(mask: np.ndarray, merge_gap: int = 0) -> list[tuple[int, int]]:
    runs, start = [], None
    for i, filled in enumerate(list(mask) + [False]):
        if filled and start is None:
            start = i
        if not filled and start is not None:
            runs.append((start, i))
            start = None
    merged: list[tuple[int, int]] = []
    for r in runs:
        if merged and r[0] - merged[-1][1] <= merge_gap:
            merged[-1] = (merged[-1][0], r[1])
        else:
            merged.append(r)
    return merged


LABEL_MAX_H = 40      # a band this short is a row of frame labels
LABEL_MARGIN = 12     # a cut may fall this far right of the next frame's label
LABEL_REACH = 80      # ... or this far left of it


def figures(img: Image.Image) -> list[Image.Image]:
    """The 12 figures, in order. Labelled sheets are cut into cells near the
    labels (each label sits at its cell's left edge), at the emptiest column,
    so a frame keeps all its pieces (debris, sparks, a muzzle flash) and wide
    figures that nearly touch stay apart; unlabelled sheets are split at empty
    columns."""
    a = np.asarray(img.convert("RGB")).astype(int)
    h, w, _ = a.shape
    corners = np.array([a[2, 2], a[2, w - 3], a[h - 3, 2], a[h - 3, w - 3]])
    bg = np.median(corners, axis=0)
    fg = np.sqrt(((a - bg) ** 2).sum(-1)) > 40
    bands = _runs(fg.any(1))
    labels = [b for b in bands if b[1] - b[0] <= LABEL_MAX_H]
    rows = sorted(sorted((b for b in bands if b[1] - b[0] > LABEL_MAX_H), key=lambda b: b[0] - b[1])[:2])
    out = []
    for y0, y1 in rows:
        above = [lb for lb in labels if lb[1] <= y0]
        starts = []
        if above:
            ly0, ly1 = above[-1]
            words = _runs(fg[ly0:ly1].any(0), merge_gap=20)
            if len(words) == 6:
                # Cut between frames at the emptiest column near each label:
                # a figure may reach a little past its own label to the left.
                occupancy = fg[y0:y1].sum(0)
                starts = [0]
                for x0, _ in words[1:]:
                    lo, hi = max(starts[-1] + 1, x0 - LABEL_REACH), min(w, x0 + LABEL_MARGIN)
                    window = occupancy[lo:hi]
                    best = window.min()
                    candidates = [lo + i for i, v in enumerate(window) if v == best]
                    starts.append(min(candidates, key=lambda c: abs(c - x0)))
        if starts:
            cells = list(zip(starts, starts[1:] + [w]))
        else:
            cells = sorted(sorted((r for r in _runs(fg[y0:y1].sum(0) > 2) if r[1] - r[0] >= 8),
                                  key=lambda r: r[0] - r[1])[:6])
        for x0, x1 in cells:
            mask = fg[y0:y1, x0:x1].copy()
            if starts:
                # Small pieces touching the cell's side edge spill over from the
                # neighbouring frame (the tip of a sword slash): drop them.
                parts = components(mask)
                total = int(mask.sum())
                edge = set(np.unique(parts[:, 0])) | set(np.unique(parts[:, -1]))
                for i in edge - {0}:
                    piece = parts == i
                    if piece.sum() < 0.03 * total:
                        mask &= ~piece
            rgba = np.zeros((y1 - y0, x1 - x0, 4), dtype=np.uint8)
            rgba[..., :3] = a[y0:y1, x0:x1]
            rgba[..., 3] = np.where(mask, 255, 0)
            fig = Image.fromarray(rgba, "RGBA")
            out.append(fig.crop(fig.getbbox()))
    if len(out) != 12:
        raise SystemExit(f"found {len(out)} figures, wanted 12")
    return out


def frames(figs: list[Image.Image], palette_from_all: bool = False) -> dict[str, Image.Image]:
    """The 72x72 frames. The palette comes from the standing figure, or with
    palette_from_all from every frame (for sheets whose effects -- a fire
    burst, a muzzle flash -- use colours the standing pose does not)."""
    scale = min([MAX_H / figs[0].height] + [min(MAX_W / f.width, MAX_H / f.height) for f in figs])
    sources = figs if palette_from_all else figs[:1]
    pal_src = Image.new("RGB", (sum(f.width for f in sources), max(f.height for f in sources)), (0, 0, 0))
    x = 0
    for f in sources:
        pal_src.paste(f.convert("RGB"), (x, 0), mask=f.getchannel("A"))
        x += f.width
    palette = pal_src.quantize(colors=64 if palette_from_all else 48, method=Image.Quantize.MEDIANCUT,
                               dither=Image.Dither.NONE)
    out = {}
    for name, fig in zip(NAMES, figs):
        small = fig.resize((max(1, round(fig.width * scale)), max(1, round(fig.height * scale))), Image.LANCZOS)
        alpha = small.getchannel("A").point(lambda v: 255 if v >= 110 else 0)
        rgb = Image.new("RGB", small.size, (0, 0, 0))
        rgb.paste(small.convert("RGB"), mask=alpha)
        rgb = rgb.quantize(palette=palette, dither=Image.Dither.NONE).convert("RGBA")
        rgb.putalpha(alpha)
        frame = Image.new("RGBA", (SPRITE, SPRITE), (0, 0, 0, 0))
        frame.alpha_composite(rgb, ((SPRITE - rgb.width) // 2, SPRITE - 2 - rgb.height))
        out[name] = frame
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sheet", type=Path)
    parser.add_argument("unit_id")
    parser.add_argument("--preview", type=Path, help="write a 4x review strip instead of installing")
    parser.add_argument("--palette-from-all", action="store_true",
                        help="build the palette from every frame (effects in colours the standing pose lacks)")
    args = parser.parse_args()
    made = frames(figures(Image.open(args.sheet)), args.palette_from_all)
    if args.preview:
        strip = Image.new("RGBA", (12 * SPRITE * 4, SPRITE * 4), (70, 90, 60, 255))
        for i, name in enumerate(NAMES):
            strip.alpha_composite(made[name].resize((SPRITE * 4, SPRITE * 4), Image.NEAREST), (i * SPRITE * 4, 0))
        strip.save(args.preview)
        print(f"preview: {args.preview}")
        return 0
    target = UNITS / args.unit_id.replace("_", "-")
    if not target.is_dir():
        raise SystemExit(f"no art folder {target}")
    for name, frame in made.items():
        frame.save(target / f"{name}.png", optimize=True)
    print(f"{args.unit_id}: 12 frames installed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
