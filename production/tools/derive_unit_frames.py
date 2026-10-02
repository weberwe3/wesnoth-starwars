#!/usr/bin/env python3
"""Derive a complete 13-file Wesnoth unit art set from one master design.

Input: a master full-body sprite (any size) and a portrait image produced for
one unit. Output: the 12 animation frames at 72x72 and a 256x256 portrait at
the exact art-queue paths.

Every frame is a transform of the same master, so the character's outfit and
equipment stay identical across the set (owner rule, 2026-10-02). Only effects
that a specific action needs differ: the muzzle flash on the firing frame, the
lean of a melee swing, the hit tint when defending, and the fall when dying.

Usage:
  derive_unit_frames.py --sprite master.png --portrait portrait.png \
      --addon addons/Star_Wars_Thrawn_Trilogy --slug sw-unit-nr-trooper
Requires Pillow.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter

SPRITE = 72
PORTRAIT = 256


def remove_flat_background(img: Image.Image, tolerance: int = 28) -> Image.Image:
    """Make a uniform corner-colored background transparent (if not already)."""
    img = img.convert("RGBA")
    w, h = img.size
    corners = [img.getpixel(p) for p in ((0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1))]
    if all(c[3] < 16 for c in corners):
        return img
    ref = corners[0]
    mask = Image.new("L", img.size, 0)
    px = img.load()
    seen = set()
    stack = [(0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)]
    mp = mask.load()
    while stack:
        x, y = stack.pop()
        if (x, y) in seen or not (0 <= x < w and 0 <= y < h):
            continue
        seen.add((x, y))
        r, g, b, _ = px[x, y]
        if abs(r - ref[0]) + abs(g - ref[1]) + abs(b - ref[2]) > tolerance * 3:
            continue
        mp[x, y] = 255
        stack.extend(((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)))
    alpha = ImageChops.subtract(img.split()[3], mask.filter(ImageFilter.GaussianBlur(1)))
    img.putalpha(alpha)
    return img


def fit(img: Image.Image, size: int, *, margin: int, anchor_bottom: bool) -> Image.Image:
    bbox = img.split()[3].point(lambda a: 255 if a > 24 else 0).getbbox()
    if bbox:
        img = img.crop(bbox)
    room = size - 2 * margin
    scale = min(room / img.width, room / img.height)
    img = img.resize((max(1, round(img.width * scale)), max(1, round(img.height * scale))), Image.LANCZOS)
    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    x = (size - img.width) // 2
    y = size - margin - img.height if anchor_bottom else (size - img.height) // 2
    out.alpha_composite(img, (x, y))
    return out


def shifted(img: Image.Image, dx: int = 0, dy: int = 0, angle: float = 0.0) -> Image.Image:
    out = img
    if angle:
        out = out.rotate(angle, resample=Image.BICUBIC, center=(SPRITE // 2, SPRITE - 4))
    if dx or dy:
        canvas = Image.new("RGBA", out.size, (0, 0, 0, 0))
        canvas.alpha_composite(out, (dx, dy))
        out = canvas
    return out


def with_alpha(img: Image.Image, factor: float) -> Image.Image:
    out = img.copy()
    out.putalpha(out.split()[3].point(lambda a: int(a * factor)))
    return out


def muzzle_flash(img: Image.Image) -> Image.Image:
    """Add a blaster flash at the leading (right) edge of the figure."""
    bbox = img.split()[3].point(lambda a: 255 if a > 24 else 0).getbbox() or (0, 0, SPRITE, SPRITE)
    x = min(SPRITE - 6, bbox[2] + 1)
    y = bbox[1] + int((bbox[3] - bbox[1]) * 0.38)
    glow = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(glow)
    d.ellipse((x - 6, y - 4, x + 6, y + 4), fill=(255, 150, 90, 150))
    d.ellipse((x - 3, y - 2, x + 3, y + 2), fill=(255, 245, 200, 255))
    out = img.copy()
    out.alpha_composite(glow.filter(ImageFilter.GaussianBlur(0.8)))
    return out


def swing_arc(img: Image.Image) -> Image.Image:
    """Faint motion arc in front of the figure for the melee follow-through."""
    arc = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(arc)
    d.arc((30, 10, 70, 50), 300, 40, fill=(255, 255, 255, 140), width=2)
    out = img.copy()
    out.alpha_composite(arc.filter(ImageFilter.GaussianBlur(0.6)))
    return out


def hit_tint(img: Image.Image) -> Image.Image:
    red = Image.new("RGBA", img.size, (255, 60, 60, 0))
    red.putalpha(img.split()[3].point(lambda a: int(a * 0.28)))
    out = shifted(img, dx=-2)
    out.alpha_composite(shifted(red, dx=-2))
    return out


# A hand-painted sprite has hundreds of distinct colors; a flat shape (for
# example a solid disc returned instead of a character) has a handful.
MIN_SPRITE_COLORS = 40
MAX_DOMINANT_SHARE = 0.6


def degenerate_reason(img: Image.Image) -> str | None:
    """Why a derived sprite is not a usable unit image, or None if it is."""
    rgba = img.convert("RGBA")
    opaque = [pixel[:3] for pixel in rgba.getdata() if pixel[3] > 200]
    if len(opaque) < 150:
        return "almost no visible pixels"
    counts: dict[tuple[int, int, int], int] = {}
    for pixel in opaque:
        key = (pixel[0] >> 3, pixel[1] >> 3, pixel[2] >> 3)
        counts[key] = counts.get(key, 0) + 1
    if len(counts) < MIN_SPRITE_COLORS:
        return f"only {len(counts)} distinct colors (flat shape, not a painted unit)"
    if max(counts.values()) / len(opaque) > MAX_DOMINANT_SHARE:
        return "one flat color covers most of the sprite"
    return None


def derive(base: Image.Image) -> dict[str, Image.Image]:
    brighter = ImageEnhance.Brightness(base).enhance(1.06)
    return {
        "standing": base,
        "idle-1": shifted(base, dy=-1),
        "idle-2": brighter,
        "move-1": shifted(base, dx=2, angle=-3),
        "move-2": shifted(base, dx=-1, angle=2),
        "melee-1": shifted(base, dx=-2, angle=5),
        "melee-2": swing_arc(shifted(base, dx=4, angle=-7)),
        "ranged-1": base,
        "ranged-2": muzzle_flash(base),
        "defend": hit_tint(base),
        "death-1": with_alpha(shifted(base, angle=-30), 0.8),
        "death-2": with_alpha(shifted(shifted(base, angle=-80), dx=14, dy=4), 0.45),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sprite", type=Path, required=True)
    parser.add_argument("--portrait", type=Path, required=True)
    parser.add_argument("--addon", type=Path, required=True)
    parser.add_argument("--slug", required=True)
    args = parser.parse_args()
    if not args.slug.replace("-", "").isalnum():
        raise SystemExit("invalid slug")
    master = remove_flat_background(Image.open(args.sprite))
    base = fit(master, SPRITE, margin=2, anchor_bottom=True)
    reason = degenerate_reason(base)
    if reason:
        raise SystemExit(f"degenerate sprite rejected: {reason}")
    unit_dir = args.addon / "images/units" / args.slug
    unit_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for state, img in derive(base).items():
        path = unit_dir / f"{state}.png"
        img.save(path, optimize=True)
        written.append(path.as_posix())
    portrait = fit(remove_flat_background(Image.open(args.portrait)), PORTRAIT, margin=6, anchor_bottom=True)
    ppath = args.addon / "images/portraits" / f"{args.slug}.png"
    ppath.parent.mkdir(parents=True, exist_ok=True)
    portrait.save(ppath, optimize=True)
    written.append(ppath.as_posix())
    print(json.dumps({"written": written}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
