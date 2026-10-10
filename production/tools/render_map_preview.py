#!/usr/bin/env python3
"""Render a quick preview image of a scenario map, for reviewing map art.

Each hex is drawn with its terrain's symbol image (the editor tile) from the
add-on's and the installed engine's terrain definitions: base terrain first,
then the overlay (forest, village, ...). Transitions between terrains, which
the engine blends at run time, are not drawn, so the preview is blockier than
the game; it is meant for judging layout, variety and readability.

Usage (art Python): render_map_preview.py MAP.map [MAP ...] --out DIR [--scale 0.5]
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
ADDON = ROOT / "addons/Star_Wars_Thrawn_Trilogy"
ENGINE = Path.home() / "opt/wesnoth-1.19.27/data"
TERRAIN_CFGS = [ENGINE / "core/terrain.cfg", ADDON / "utils/hte_terrain.cfg"]
IMAGE_DIRS = [ADDON / "images/terrain", ENGINE / "core/images/terrain"]


def terrain_symbols() -> dict[str, str]:
    out = {}
    for cfg in TERRAIN_CFGS:
        text = cfg.read_text(encoding="utf-8", errors="replace")
        for block in re.findall(r"\[terrain_type\](.*?)\[/terrain_type\]", text, re.S):
            code = re.search(r"^\s*string=(\S+)", block, re.M)
            img = re.search(r"^\s*(?:editor_image|symbol_image)=(\S+)", block, re.M)
            if code and img:
                out[code.group(1)] = img.group(1)
    return out


_cache: dict[str, Image.Image | None] = {}


def tile(name: str) -> Image.Image | None:
    if name not in _cache:
        found = None
        for d in IMAGE_DIRS:
            p = d / f"{name}.png"
            if p.exists():
                found = Image.open(p).convert("RGBA")
                break
        _cache[name] = found
    return _cache[name]


def render(map_path: Path, symbols: dict[str, str], scale: float) -> Image.Image:
    rows = [r for r in map_path.read_text(encoding="utf-8").splitlines() if r.strip() and "," in r]
    grid = [[c.strip().split(" ")[-1] for c in r.split(",")] for r in rows]
    h, w = len(grid), max(len(r) for r in grid)
    img = Image.new("RGBA", (54 * w + 18, 72 * h + 36), (0, 0, 0, 255))
    missing = set()
    for y, row in enumerate(grid):
        for x, code in enumerate(row):
            base, _, overlay = code.partition("^")
            px, py = 54 * x, 72 * y + (36 if x % 2 else 0)
            for part in [base] + ([f"^{overlay}"] if overlay else []):
                t = tile(symbols.get(part, "")) if part in symbols else None
                if t is None:
                    missing.add(part)
                    continue
                img.alpha_composite(t, (px + (72 - t.width) // 2, py + (72 - t.height) // 2))
    if missing:
        print(f"{map_path.name}: no tile for {sorted(missing)}")
    return img.resize((int(img.width * scale), int(img.height * scale)), Image.LANCZOS)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("maps", nargs="+", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--scale", type=float, default=0.5)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    symbols = terrain_symbols()
    for m in args.maps:
        render(m, symbols, args.scale).convert("RGB").save(args.out / f"{m.stem}.jpg", quality=82)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
