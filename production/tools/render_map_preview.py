#!/usr/bin/env python3
"""Render a quick preview image of a scenario map, for reviewing map art.

Each hex is drawn with its terrain's symbol image (the editor tile) from the
add-on's and the installed engine's terrain definitions: base terrain first,
then the overlay (forest, village, ...). Transitions between terrains, which
the engine blends at run time, are not drawn, so the preview is blockier than
the game; it is meant for judging layout, variety and readability. The wall
blocks (gen_wall_relief.py, utils/sw_wall_relief.cfg) are drawn with the same
neighbour rules as the game.

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


WALLS = {"Qwt": "timber", "Qwc": "colony", "Qwp": "palace", "Qwr": "rock", "Qib": "bulkhead"}


def low_column(x: int) -> int:
    """1 if map-file column x sits half a hex lower. File columns include the
    border, so file column x is engine column x - 1, and the engine lowers
    its odd columns (src/map/location.cpp get_direction): even file columns."""
    return 1 - x % 2


def neighbours(x: int, y: int) -> dict[str, tuple[int, int]]:
    odd = low_column(x)
    return {"n": (x, y - 1), "s": (x, y + 1), "ne": (x + 1, y - 1 + odd), "se": (x + 1, y + odd),
            "nw": (x - 1, y - 1 + odd), "sw": (x - 1, y + odd)}


def draw_relief(img: Image.Image, grid: list[list[str]]) -> None:
    """Wall blocks, bunker parapets and wall shadows, placed by the same
    neighbour rules as the game (utils/sw_wall_relief.cfg, hte_terrain.cfg).
    Every image stays inside its own hex, as the engine cuts it."""
    def base(x, y):
        if 0 <= y < len(grid) and 0 <= x < len(grid[y]):
            return grid[y][x].partition("^")[0]
        return None

    def solid(code):      # walls, impassable terrain and the map border
        return code is None or code in WALLS or code.startswith("X")

    draws = []
    for y, row in enumerate(grid):
        for x in range(len(row)):
            here = base(x, y)
            # The engine draws a row's upper columns, then its lower ones, and
            # each hex's images by layer.
            key = (y, low_column(x), x)
            pos = (54 * x, 72 * y + 36 * low_column(x))
            nb = neighbours(x, y)
            if here in WALLS or not solid(here):
                cells = {"c": here, "s": base(*nb["s"]), "se": base(*nb["se"]), "sw": base(*nb["sw"])}
                bits = "".join("1" if (here in WALLS if o == "c" else solid(cells[o])) else "0"
                               for o in ("c", "s", "se", "sw"))
                for o, code in cells.items():
                    if code in WALLS:
                        draws.append((key, -400, pos, f"wall-{WALLS[code]}-{o}-{bits}"))
            for d, (nx, ny) in nb.items():
                there = base(nx, ny)
                if there is None:
                    continue
                if here == "Qcb" and there not in ("Qcb", "Qkb"):
                    draws.append((key, -400, pos, f"wall-relief-bunker-{d}"))
                elif not solid(here) and there in WALLS:
                    draws.append((key, -450, pos, f"wall-shadow-{d}"))
    for _key, _layer, (px, py), name in sorted(draws):
        t = tile(f"sw/{name}")
        if t is not None:
            img.alpha_composite(t, (px, py))


def render(map_path: Path, symbols: dict[str, str], scale: float) -> Image.Image:
    rows = [r for r in map_path.read_text(encoding="utf-8").splitlines() if r.strip() and "," in r]
    grid = [[c.strip().split(" ")[-1] for c in r.split(",")] for r in rows]
    h, w = len(grid), max(len(r) for r in grid)
    img = Image.new("RGBA", (54 * w + 18, 72 * h + 36), (0, 0, 0, 255))
    missing = set()
    for y, row in enumerate(grid):
        for x, code in enumerate(row):
            base, _, overlay = code.partition("^")
            px, py = 54 * x, 72 * y + 36 * low_column(x)
            for part in [base] + ([f"^{overlay}"] if overlay else []):
                t = tile(symbols.get(part, "")) if part in symbols else None
                if t is None:
                    missing.add(part)
                    continue
                img.alpha_composite(t, (px + (72 - t.width) // 2, py + (72 - t.height) // 2))
    draw_relief(img, grid)
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
