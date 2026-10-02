#!/usr/bin/env python3
"""Fit one generated portrait into the add-on's 256x256 dialogue portrait.

Used for portrait-only regeneration (codex_art.generate_portrait): the unit's
sprites are left untouched. Rejects a degenerate image (flat shape) the same
way frame derivation does.

Usage: fit_portrait.py --portrait in.png --addon addons/Star_Wars_Thrawn_Trilogy --slug sw-hero-han
Requires Pillow.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image

from derive_unit_frames import PORTRAIT, degenerate_reason, fit, remove_flat_background


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--portrait", type=Path, required=True)
    parser.add_argument("--addon", type=Path, required=True)
    parser.add_argument("--slug", required=True)
    args = parser.parse_args()
    if not args.slug.replace("-", "").isalnum():
        raise SystemExit("invalid slug")
    portrait = fit(remove_flat_background(Image.open(args.portrait)), PORTRAIT, margin=6, anchor_bottom=True)
    reason = degenerate_reason(portrait.resize((72, 72)))
    if reason:
        raise SystemExit(f"degenerate portrait rejected: {reason}")
    path = args.addon / "images/portraits" / f"{args.slug}.png"
    path.parent.mkdir(parents=True, exist_ok=True)
    portrait.save(path, optimize=True)
    print(json.dumps({"written": [path.as_posix()]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
