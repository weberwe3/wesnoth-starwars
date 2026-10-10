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
       [--match-scale OTHER_SHEET]
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
LABEL_MARGIN = 12     # a cut may fall this far right of a left-aligned label (and is preferred this far left)
LABEL_REACH = 80      # ... or this far left of it
LABEL_LEFT_EDGE = 40  # labels starting further in than this are centred under their frames


def figures(img: Image.Image, per_row: tuple[int, int] = (6, 6)) -> list[Image.Image]:
    """The 12 figures, in order. Labelled sheets are cut into cells near the
    labels (each label sits at its cell's left edge), at the emptiest column,
    so a frame keeps all its pieces (debris, sparks, a muzzle flash) and wide
    figures that nearly touch stay apart; unlabelled sheets are split at empty
    columns."""
    a = np.asarray(img.convert("RGB")).astype(int)
    h, w, _ = a.shape
    corners = np.array([a[2, 2], a[2, w - 3], a[h - 3, 2], a[h - 3, w - 3]])
    bg = np.median(corners, axis=0)
    dist = np.sqrt(((a - bg) ** 2).sum(-1))
    fg = dist > 40
    # Clothing close to the backdrop colour (an olive coat on a green sheet)
    # falls under that threshold and would be punched out, leaving the coat's
    # buttons and highlights as speckles. Near-background regions enclosed by
    # the figure stay figure unless they are the flat backdrop itself (a real
    # gap between arm and body is drawn in the exact background colour).
    from scipy import ndimage
    near, n = ndimage.label(~fg)
    if n:
        border = set(np.unique(np.concatenate([near[0], near[-1], near[:, 0], near[:, -1]])))
        mean_dist = ndimage.mean(dist, near, range(1, n + 1))
        keep = np.array([i not in border and mean_dist[i - 1] > 16 for i in range(1, n + 1)])
        fg |= np.concatenate([[False], keep])[near]
    # Label rows: yellow text spread across the sheet (in at least four
    # places along the row); a painted muzzle flash is yellow too, but only in
    # one frame. The text (and its anti-aliased edge) is removed from those
    # rows, so a figure reaching up into a label row keeps its own pixels.
    yellow = (a[..., 0] > 170) & (a[..., 1] > 160) & (a[..., 2] < 110) & (np.abs(a[..., 0] - a[..., 1]) < 70)
    label_row = np.array([len(_runs(yellow[y], merge_gap=40)) >= min(4, min(per_row)) for y in range(h)])
    label_bands = _runs(label_row, merge_gap=3)
    text = np.zeros_like(fg)
    for ly0, ly1 in label_bands:
        lo, hi = max(0, ly0 - 2), min(h, ly1 + 2)
        near = yellow[lo:hi].copy()
        for _ in range(2):
            grown = near.copy()
            grown[1:] |= near[:-1]
            grown[:-1] |= near[1:]
            grown[:, 1:] |= near[:, :-1]
            grown[:, :-1] |= near[:, 1:]
            near = grown
        text[lo:hi] |= near
    figure = fg & ~text
    bands = _runs(figure.any(1))
    rows = sorted(sorted((b for b in bands if b[1] - b[0] > LABEL_MAX_H), key=lambda b: b[0] - b[1])[:2])
    fg = figure
    out = []
    for row_i, (y0, y1) in enumerate(rows):
        n_row = per_row[row_i]
        # The row's labels: the nearest label band on the sheet's label side
        # (all labels sit above their frames, or all below).
        above_side = bool(label_bands) and bool(rows) and label_bands[0][0] < rows[0][0]
        side = [lb for lb in label_bands if (lb[1] <= y0 if above_side else lb[0] >= y1)]
        nearest = sorted(side or label_bands, key=lambda lb: min(abs(lb[1] - y0), abs(lb[0] - y1)))
        starts = []
        if nearest:
            ly0, ly1 = nearest[0]
            words = _runs(yellow[ly0:ly1].any(0), merge_gap=20)
            if len(words) == n_row:
                # Cut between frames at the emptiest column near each label:
                # a figure may reach a little past its own label to the left.
                occupancy = fg[y0:y1].sum(0)
                starts = [0]
                # Left-aligned labels (the first one at the sheet's left edge)
                # start their frame: cut just left of the next label. Centred
                # labels: cut anywhere between two labels' centres.
                centred = words[0][0] > LABEL_LEFT_EDGE
                for (p0, p1), (x0, x1) in zip(words, words[1:]):
                    if centred:
                        lo, hi = max(starts[-1] + 1, (p0 + p1) // 2), min(w, (x0 + x1) // 2)
                    else:
                        lo, hi = max(starts[-1] + 1, x0 - LABEL_REACH), min(w, x0 + LABEL_MARGIN)
                    window = occupancy[lo:hi]
                    best = window.min()
                    candidates = [lo + i for i, v in enumerate(window) if v == best]
                    starts.append(min(candidates, key=lambda c: abs(c - (x0 - LABEL_MARGIN))))
        if starts:
            cells = list(zip(starts, starts[1:] + [w]))
            # A piece that straddles a cut (a prop set down beside a figure,
            # under the next frame's carried weapon) goes whole to the frame
            # its centre lies in.
            band_parts = components(fg[y0:y1])
            straddling = {}
            for i in range(1, int(band_parts.max()) + 1):
                xs = np.nonzero((band_parts == i).any(axis=0))[0]
                # Only small pieces (a prop, a spark) move whole; a large piece that
                # spans two frames (a shield dome touching the next frame's arc) is cut.
                cell_w = w / n_row
                if len(xs) and xs.max() - xs.min() < 0.6 * cell_w and \
                        any(xs.min() < c0 <= xs.max() for c0 in starts[1:]):
                    centre = (xs.min() + xs.max()) / 2
                    straddling[i] = sum(1 for c0 in starts if c0 <= centre) - 1
        else:
            cells = sorted(sorted((r for r in _runs(fg[y0:y1].sum(0) > 2) if r[1] - r[0] >= 8),
                                  key=lambda r: r[0] - r[1])[:n_row])
        for k, (x0, x1) in enumerate(cells):
            mask = fg[y0:y1, x0:x1].copy()
            if starts:
                # Everything in the cell, minus straddling pieces owned by a
                # neighbour, plus straddling pieces this frame owns.
                inside = np.zeros_like(fg[y0:y1])
                inside[:, x0:x1] = fg[y0:y1, x0:x1]
                foreign = np.isin(band_parts, [i for i, o in straddling.items() if o != k])
                own = np.isin(band_parts, [i for i, o in straddling.items() if o == k])
                mine = (inside & ~foreign) | own
                cols = np.nonzero(mine.any(axis=0))[0]
                if len(cols):
                    x0, x1 = min(x0, int(cols.min())), max(x1, int(cols.max()) + 1)
                mask = mine[:, x0:x1]
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
    if len(out) != sum(per_row):
        raise SystemExit(f"found {len(out)} figures, wanted {sum(per_row)}")
    return out


def sheet_scale(figs: list[Image.Image]) -> float:
    """One factor for the whole sheet: the standing figure MAX_H px tall, unless
    a wider or taller frame needs less to fit the 72x72 frame."""
    return min([MAX_H / figs[0].height] + [min(MAX_W / f.width, MAX_H / f.height) for f in figs])


def frames(figs: list[Image.Image], palette_from_all: bool = False,
           scale: float | None = None, only: list[str] | None = None,
           colors: int | None = None, alpha_cut: int = 110) -> dict[str, Image.Image]:
    """The 72x72 frames. The palette comes from the standing figure, or with
    palette_from_all from every frame (for sheets whose effects -- a fire
    burst, a muzzle flash -- use colours the standing pose does not)."""
    # With only=, just those frames are made (and must fit the 72x72 frame).
    picked = [f for n, f in zip(NAMES, figs) if only is None or n in only]
    fit = sheet_scale(figs) if only is None else min(min(MAX_W / f.width, MAX_H / f.height) for f in picked)
    if scale is None:
        scale = fit
    elif scale > fit:
        raise SystemExit(f"--match-scale {scale:.3f} is too large for this sheet (at most {fit:.3f})")
    sources = figs if palette_from_all else figs[:1]
    pal_src = Image.new("RGB", (sum(f.width for f in sources), max(f.height for f in sources)), (0, 0, 0))
    x = 0
    for f in sources:
        pal_src.paste(f.convert("RGB"), (x, 0), mask=f.getchannel("A"))
        x += f.width
    palette = pal_src.quantize(colors=colors or (64 if palette_from_all else 48), method=Image.Quantize.MEDIANCUT,
                               dither=Image.Dither.NONE)
    if colors:
        # Small, bright, strongly coloured effects (laser bolts, engine glow) are few
        # pixels against a large hull, so median cut merges them away: give the
        # saturated pixels their own palette entries.
        src = np.asarray(pal_src).reshape(-1, 3).astype(int)
        # Bright only: dim green edge pixels are background bleed, not effects.
        sat = src[((src.max(1) - src.min(1)) > 60) & (src.max(1) > 150)]
        if len(sat) >= 16:
            # Per hue band (12 bands), up to 4 shades each, so a rare green is
            # not merged into a common cyan.
            r, g, b = sat[:, 0] / 255, sat[:, 1] / 255, sat[:, 2] / 255
            mx, mn = sat.max(1) / 255, sat.min(1) / 255
            d = np.maximum(mx - mn, 1e-6)
            hue = np.where(mx == r, ((g - b) / d) % 6, np.where(mx == g, (b - r) / d + 2, (r - g) / d + 4)) * 60
            add = []
            for band in range(12):
                px = sat[(hue >= band * 30) & (hue < band * 30 + 30)]
                if len(px) < 12:
                    continue
                order = np.argsort(px.sum(1))
                for chunk in np.array_split(px[order], 4):
                    if len(chunk):
                        add += [int(v) for v in np.median(chunk, axis=0)]
            base = palette.getpalette()[:3 * (colors or 64)]
            merged = (base + add)[:768]
            palette = Image.new("P", (1, 1))
            palette.putpalette(merged + [0] * (768 - len(merged)))
    out = {}
    for name, fig in zip(NAMES, figs):
        if only is not None and name not in only:
            continue
        if colors:
            # Background spill: dim green pixels on the figure's edge (touching
            # transparency) are the backdrop blended into the outline. Bright
            # greens (laser bolts) are kept.
            arr = np.asarray(fig.convert("RGBA")).copy()
            for _ in range(2):
                op = arr[..., 3] > 0
                pad = np.pad(~op, 1, constant_values=True)
                edge = op & (pad[:-2, 1:-1] | pad[2:, 1:-1] | pad[1:-1, :-2] | pad[1:-1, 2:])
                c = arr[..., :3].astype(int)
                spill = edge & (c[..., 1] > c[..., 0] + 12) & (c[..., 1] > c[..., 2] + 12) & (c[..., 1] < 135)
                arr[spill, 3] = 0
            fig = Image.fromarray(arr, "RGBA")
        small = fig.resize((max(1, round(fig.width * scale)), max(1, round(fig.height * scale))), Image.LANCZOS)
        if alpha_cut < 110:
            # Thin effects (laser lines, sparks) keep their colour: resize the
            # colour premultiplied by alpha, so a 2-px line shrunk 5x is a
            # faint pixel of laser colour rather than a mix with the background.
            arr = np.asarray(fig.convert("RGBA")).astype(float)
            pre = np.dstack([arr[..., :3] * arr[..., 3:4] / 255, arr[..., 3]]).astype(np.uint8)
            pm = np.asarray(Image.fromarray(pre, "RGBA").resize(small.size, Image.BOX)).astype(float)
            a_ = np.maximum(pm[..., 3:4], 1)
            rgb_ = np.clip(pm[..., :3] * 255 / a_, 0, 255)
            small = Image.fromarray(np.dstack([rgb_, pm[..., 3:4]]).astype(np.uint8), "RGBA")
        alpha = small.getchannel("A").point(lambda v: 255 if v >= alpha_cut else 0)
        rgb = Image.new("RGB", small.size, (0, 0, 0))
        rgb.paste(small.convert("RGB"), mask=alpha)
        rgb = rgb.quantize(palette=palette, dither=Image.Dither.NONE).convert("RGBA")
        rgb.putalpha(alpha)
        frame = Image.new("RGBA", (SPRITE, SPRITE), (0, 0, 0, 0))
        frame.alpha_composite(rgb, ((SPRITE - rgb.width) // 2, SPRITE - 2 - rgb.height))
        out[name] = frame
    return out


def partial_frames(named: dict[str, Image.Image], palette_from_all: bool, colors: int | None,
                   alpha_cut: int) -> dict[str, Image.Image]:
    """Frames of a partial sheet, all at one scale: the first frame (the unit's
    standing pose) is MAX_H tall unless a wider frame needs less."""
    figs = list(named.values())
    scale = min([MAX_H / figs[0].height] + [min(MAX_W / f.width, MAX_H / f.height) for f in figs])
    padded = figs + [figs[0]] * (12 - len(figs))       # frames() works on a 12-frame list
    made = frames(padded, palette_from_all, scale, colors=colors, alpha_cut=alpha_cut)
    return {name: made[NAMES[i]] for i, name in enumerate(named)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sheet", type=Path)
    parser.add_argument("unit_id")
    parser.add_argument("--preview", type=Path, help="write a 4x review strip instead of installing")
    parser.add_argument("--palette-from-all", action="store_true",
                        help="build the palette from every frame (effects in colours the standing pose lacks)")
    parser.add_argument("--match-scale", type=Path, metavar="OTHER_SHEET",
                        help="use the scale of another sheet of the same character drawn at the same size "
                             "(e.g. an unarmed set matching the armed one), so the unit keeps its size")
    parser.add_argument("--alpha-cut", type=int, default=110,
                        help="opacity below which a shrunk pixel is dropped; lower it (e.g. 40) to keep thin effects")
    parser.add_argument("--colors", type=int, help="palette size (default 48, or 64 with --palette-from-all); "
                        "raise it when small effects in a rare colour lose their hue")
    parser.add_argument("--frames", help="a partial sheet: its frame names, row by row, rows split by '/' "
                        "(e.g. 'idle-1,idle-2/death-1,death-2'); only these frames are written")
    args = parser.parse_args()
    if args.frames:
        rows_spec = [r.split(",") for r in args.frames.split("/")]
        figs = figures(Image.open(args.sheet), tuple(len(r) for r in rows_spec))
        names = [n for r in rows_spec for n in r]
        made = partial_frames(dict(zip(names, figs)), args.palette_from_all, args.colors, args.alpha_cut)
        target = UNITS / args.unit_id.replace("_", "-")
        if args.preview:
            strip = Image.new("RGBA", (len(made) * SPRITE * 4, SPRITE * 4), (70, 90, 60, 255))
            for i, f in enumerate(made.values()):
                strip.alpha_composite(f.resize((SPRITE * 4, SPRITE * 4), Image.NEAREST), (i * SPRITE * 4, 0))
            strip.save(args.preview)
            print(f"preview: {args.preview}")
            return 0
        for name, frame in made.items():
            frame.save(target / f"{name}.png", optimize=True)
        print(f"{args.unit_id}: {', '.join(made)} installed")
        return 0
    scale = sheet_scale(figures(Image.open(args.match_scale))) if args.match_scale else None
    made = frames(figures(Image.open(args.sheet)), args.palette_from_all, scale, colors=args.colors,
                  alpha_cut=args.alpha_cut)
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
