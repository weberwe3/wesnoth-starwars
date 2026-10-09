#!/usr/bin/env python3
"""Scale each unit's frames to its lore size tier (size_tiers.json).

Every frame of a unit is scaled by the same factor, anchored at the bottom
centre of the frame (where the unit stands on its hex), so animations stay
consistent; colours are snapped back to the unit's own palette. A unit
already within 3% of its target is left alone, so the tool is idempotent.
Game-drawn muzzle flash points (muzzle_flashes.json "blit") move with the
art. Run gen_hte_units.py afterwards.

Usage (art Python): size_unit_tiers.py [--only SLUG ...] [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

TOOLS = Path(__file__).resolve().parent
UNITS = TOOLS.parents[1] / "addons/Star_Wars_Thrawn_Trilogy/images/units"
TIERS = TOOLS / "size_tiers.json"
FLASHES = TOOLS / "muzzle_flashes.json"
NAMES = ["standing", "idle-1", "idle-2", "move-1", "move-2", "melee-1", "melee-2", "ranged-1", "ranged-2",
         "defend", "death-1", "death-2"]
S, AX, AY = 72, 36, 70          # frame size; anchor: bottom centre where units stand
FLASH_W, FLASH_H = 14, 10
BODY = {"standing", "idle-1", "idle-2", "move-1", "move-2", "defend"}
# Variations drawn at one scale with another unit (measured before resizing).
SAME_SCALE_AS = {"sw-hero-luke-unarmed": "sw-hero-luke"}


def measure(img: Image.Image, dim: str) -> int:
    b = img.getbbox()
    h, w = b[3] - b[1], b[2] - b[0]
    return {"h": h, "w": w, "max": max(h, w)}[dim]


def scale_frame(img: Image.Image, f: float, palette: Image.Image) -> Image.Image:
    big = img.resize((round(S * f), round(S * f)), Image.LANCZOS)
    alpha = big.getchannel("A").point(lambda v: 255 if v >= 110 else 0)
    rgb = Image.new("RGB", big.size, (0, 0, 0))
    rgb.paste(big.convert("RGB"), mask=alpha)
    rgb = rgb.quantize(palette=palette, dither=Image.Dither.NONE).convert("RGBA")
    rgb.putalpha(alpha)
    out = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    # place so the anchor point keeps its position
    out.alpha_composite(rgb, (round(AX - AX * f), round(AY - AY * f))) if f <= 1 else \
        out.paste(rgb.crop((round(AX * f - AX), round(AY * f - AY), round(AX * f - AX) + S, round(AY * f - AY) + S)), (0, 0))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--only", action="append")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    tiers = {k: v for k, v in json.loads(TIERS.read_text(encoding="utf-8")).items() if not k.startswith("_")}
    flashes = json.loads(FLASHES.read_text(encoding="utf-8"))
    for slug, (dim, target, _lore) in tiers.items():
        if args.only and slug not in args.only:
            continue
        d = UNITS / slug
        frames = {n: Image.open(d / f"{n}.png").convert("RGBA") for n in NAMES}
        cur = measure(frames["standing"], dim)
        f = target / cur
        if slug in SAME_SCALE_AS:
            ref = UNITS / SAME_SCALE_AS[slug] / "standing.png"
            rdim, rtarget, _ = tiers[SAME_SCALE_AS[slug]]
            f = rtarget / measure(Image.open(ref).convert("RGBA"), rdim)
        # never push the body past the frame edges (effects in attack and
        # death frames may clip when a unit is scaled up)
        for n, img in frames.items():
            if n not in BODY:
                continue
            b = img.getbbox()
            if b:
                f = min(f, AX / max(1, AX - b[0]), (S - AX) / max(1, b[2] - AX), AY / max(1, AY - b[1]))
        if abs(f - 1) < 0.03:
            print(f"{slug}: {cur}px ({dim}) already at tier")
            continue
        print(f"{slug}: {dim} {cur} -> {round(cur * f)} px (x{f:.2f})")
        if args.dry_run:
            continue
        src = Image.new("RGB", (S * len(frames), S), (0, 0, 0))
        for i, img in enumerate(frames.values()):
            src.paste(img.convert("RGB"), (S * i, 0), mask=img.getchannel("A"))
        palette = src.quantize(colors=128, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
        for n, img in frames.items():
            scale_frame(img, f, palette).save(d / f"{n}.png", optimize=True)
        entry = flashes.get(slug)
        if entry and "blit" in entry:
            cx, cy = entry["blit"][0] + FLASH_W / 2, entry["blit"][1] + FLASH_H / 2
            nx, ny = AX + (cx - AX) * f, AY + (cy - AY) * f
            entry["blit"] = [max(0, min(S - FLASH_W, round(nx - FLASH_W / 2))),
                             max(0, min(S - FLASH_H, round(ny - FLASH_H / 2)))]
    if not args.dry_run:
        raw = FLASHES.read_text(encoding="utf-8")
        FLASHES.write_text(json.dumps(flashes, indent=2 if raw.startswith('{\n  "') else 1, sort_keys=True) + "\n",
                           encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
