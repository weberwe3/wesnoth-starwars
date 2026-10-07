#!/usr/bin/env python3
"""Install a 12-frame unit sprite sheet supplied by the project owner.

The sheet shows the frames in the add-on's order, six per row on a flat
background colour, optionally with yellow frame labels (removed):

  standing idle-1 idle-2 move-1 move-2 melee-1
  melee-2 ranged-1 ranged-2 defend death-1 death-2

Every frame is scaled by the same factor (the standing figure becomes
MAX_H px tall), bottom-anchored and centred in the 72x72 unit frame like
the other unit art, and reduced to the standing figure's own palette.

Usage (art Python): import_owner_sheet.py SHEET UNIT_ID [--preview OUT.png]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
from import_sheet_sprites import MAX_H, MAX_W, SPRITE, UNITS  # noqa: E402

NAMES = ["standing", "idle-1", "idle-2", "move-1", "move-2", "melee-1",
         "melee-2", "ranged-1", "ranged-2", "defend", "death-1", "death-2"]


def figures(img: Image.Image) -> list[Image.Image]:
    a = np.asarray(img.convert("RGB")).astype(int)
    h, w, _ = a.shape
    corners = np.array([a[2, 2], a[2, w - 3], a[h - 3, 2], a[h - 3, w - 3]])
    bg = np.median(corners, axis=0)
    fg = np.sqrt(((a - bg) ** 2).sum(-1)) > 40
    fg &= ~((a[..., 0] > 140) & (a[..., 1] > 140) & (a[..., 2] < 110))   # yellow labels
    rows = fg.any(1)
    bands, start = [], None
    for y, filled in enumerate(list(rows) + [False]):
        if filled and start is None:
            start = y
        if not filled and start is not None:
            bands.append((start, y))
            start = None
    # Two rows of figures: merge label-sized gaps, keep the two tallest bands.
    bands = sorted(sorted(bands, key=lambda b: b[0] - b[1])[:2])
    out = []
    for y0, y1 in bands:
        cols = fg[y0:y1].sum(0) > 2
        runs, start = [], None
        for x, filled in enumerate(list(cols) + [False]):
            if filled and start is None:
                start = x
            if not filled and start is not None:
                runs.append((start, x))
                start = None
        runs = sorted(sorted((r for r in runs if r[1] - r[0] >= 8), key=lambda r: r[0] - r[1])[:6])
        for x0, x1 in runs:
            rgba = np.zeros((y1 - y0, x1 - x0, 4), dtype=np.uint8)
            rgba[..., :3] = a[y0:y1, x0:x1]
            rgba[..., 3] = np.where(fg[y0:y1, x0:x1], 255, 0)
            fig = Image.fromarray(rgba, "RGBA")
            out.append(fig.crop(fig.getbbox()))
    if len(out) != 12:
        raise SystemExit(f"found {len(out)} figures, wanted 12")
    return out


def frames(figs: list[Image.Image]) -> dict[str, Image.Image]:
    scale = min([MAX_H / figs[0].height] + [min(MAX_W / f.width, MAX_H / f.height) for f in figs])
    standing = figs[0]
    pal_src = Image.new("RGB", standing.size, (0, 0, 0))
    pal_src.paste(standing.convert("RGB"), mask=standing.getchannel("A"))
    palette = pal_src.quantize(colors=48, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
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
    args = parser.parse_args()
    made = frames(figures(Image.open(args.sheet)))
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
