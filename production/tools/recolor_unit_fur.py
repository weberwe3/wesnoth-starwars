#!/usr/bin/env python3
"""Recolour a unit line's fur so units that share one body plan read apart.

Owner direction (2026-10-12): the Wookiee units need clear visual distinction.
The Wookiee Warrior, Wookiee Lookout and Chewbacca were drawn from one
reference and share the same auburn fur, so at 72 px they look alike. Each line
gets its own fur colour in every frame of every tier and in its portrait,
keeping the approved art, house style, shading and animation exactly:

  warrior  slate      (dark grey-brown)
  lookout  silver     (mid silver-grey)
  Chewbacca keeps his auburn fur (not recoloured).

Fur is every warm pixel (hue 340-38 degrees) with some saturation; warm gear
goes with it (the Warrior's rank III feathered headdress turns slate, keeping
its silhouette and teal armour). Gear that is not warm (white or silver bandoliers, green camouflage, teal
armour, dark metal) is untouched. The Wookiee muzzle flash is blitted by the game
(muzzle_flashes.json, "posed"), so no painted flash is affected. The shading
(relative value) of each pixel is kept, so the drawing is unchanged.

It reads from --source (the original art, e.g. an images/ directory exported
from a git revision before this change) when given, otherwise from the
installed files. --install records the hash of every file it writes in
recolor_unit_fur.json, and the tool refuses to recolour a file whose hash is
listed there, so the fur is never shifted twice.

Usage: recolor_unit_fur.py [--preview OUT.png] [--install] [--source DIR]
"""
from __future__ import annotations

import argparse
import colorsys
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = Path(__file__).with_suffix(".json")
IMAGES = ROOT / "addons/Star_Wars_Thrawn_Trilogy/images"

# slug -> (saturation factor, value = a + b * value): the fur's new look.
FUR = {
    "sw-unit-wk-warrior": ("slate", 0.35, 0.07, 0.62),
    "sw-unit-wk-lookout": ("silver", 0.18, 0.16, 0.72),
}
TIERS = ("", "-rank2", "-rank3")


def warm(h: np.ndarray, s: np.ndarray) -> np.ndarray:
    deg = h * 360
    return ((deg >= 340) | (deg <= 38)) & (s >= 0.22)


def recolor(img: Image.Image, sat: float, a: float, b: float) -> Image.Image:
    rgba = np.asarray(img.convert("RGBA")).astype(float) / 255
    rgb = rgba[..., :3].reshape(-1, 3)
    hsv = np.array([colorsys.rgb_to_hsv(*p) for p in rgb])
    h, s, v = hsv[:, 0], hsv[:, 1], hsv[:, 2]
    mask = warm(h, s) & (rgba[..., 3].reshape(-1) > 0)
    s2 = np.where(mask, s * sat, s)
    v2 = np.where(mask, np.clip(a + b * v, 0, 1), v)
    out = np.array([colorsys.hsv_to_rgb(*p) for p in np.stack([h, s2, v2], 1)])
    rgba[..., :3] = out.reshape(rgba.shape[:2] + (3,))
    return Image.fromarray((rgba * 255).round().astype(np.uint8), "RGBA")


def files_for(slug: str, base: Path) -> list[Path]:
    out = []
    for tier in TIERS:
        d = base / "units" / f"{slug}{tier}"
        if d.is_dir():
            out += sorted(d.glob("*.png"))
    portrait = base / "portraits" / f"{slug}.png"
    if portrait.exists():
        out.append(portrait)
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--preview", type=Path)
    ap.add_argument("--install", action="store_true")
    ap.add_argument("--source", type=Path, help="images/ directory holding the original art")
    args = ap.parse_args()
    source = args.source or IMAGES
    done = json.loads(MANIFEST.read_text()) if MANIFEST.exists() else {}
    written = {}
    previews = []
    for slug, (_name, sat, a, b) in FUR.items():
        for src in files_for(slug, source):
            rel = src.relative_to(source)
            if hashlib.sha1(src.read_bytes()).hexdigest() == done.get(rel.as_posix()):
                raise SystemExit(f"{rel}: already recoloured (recolor_unit_fur.json); use --source")
            img = Image.open(src)
            new = recolor(img, sat, a, b)
            if args.install:
                dest = IMAGES / rel
                if img.mode == "P" or img.mode == "RGBA":
                    new.save(dest, optimize=True)
                else:
                    new.convert(img.mode).save(dest, optimize=True)
                written[rel.as_posix()] = hashlib.sha1(dest.read_bytes()).hexdigest()
            if rel.name in ("idle-1.png",):
                previews.append((rel.parent.name, img.convert("RGBA"), new))
    if args.install:
        MANIFEST.write_text(json.dumps({**done, **written}, indent=1, sort_keys=True) + "\n")
    if args.preview:
        k = 3
        sheet = Image.new("RGBA", (len(previews) * 72 * k, 2 * 72 * k), (70, 90, 60, 255))
        for i, (_n, old, new) in enumerate(previews):
            sheet.alpha_composite(old.resize((72 * k, 72 * k), Image.NEAREST), (i * 72 * k, 0))
            sheet.alpha_composite(new.resize((72 * k, 72 * k), Image.NEAREST), (i * 72 * k, 72 * k))
        sheet.save(args.preview)


if __name__ == "__main__":
    main()
