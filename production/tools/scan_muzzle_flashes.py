#!/usr/bin/env python3
"""Measure every unit sprite's muzzle flash for production/tools/gen_hte_units.py.

Owner rule (2026-10-04): a ranged attack's laser colour matches the muzzle
flash of the sprite that fires it. If the sprite has no muzzle-flash colour of
its own, the faction/lore colour logic in gen_hte_units.projectile() decides,
and the flash is drawn in that colour.

Two kinds of sprite set exist:
  painted  hand-drawn firing poses (ranged-1 differs from standing) with the
           flash painted into the art: its colour is measured here and the
           bolts take that colour.
  derived  derive_unit_frames.py sets, where ranged-1 is the standing master
           and the flash is not part of the art. ranged-2 carries no flash;
           the unit WML blits a flash in each weapon's own colour onto it at
           the muzzle point measured here (same placement rule as the old
           baked-in flash).

--strip-generic removes the old baked-in warm flash from derived sets
(ranged-2 := ranged-1, which is the same master), once.

Writes production/tools/muzzle_flashes.json; --check fails if it is stale.
Run with the art Python (Pillow, numpy).
"""
from __future__ import annotations

import argparse
import colorsys
import json
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
UNITS = ROOT / "addons/Star_Wars_Thrawn_Trilogy/images/units"
OUT = Path(__file__).resolve().parent / "muzzle_flashes.json"
SPRITE = 72
# Flash image size (projectiles/sw-flash-*.png); the blit is centred on the muzzle.
FLASH_W, FLASH_H = 14, 10


def rgba(path: Path) -> np.ndarray:
    return np.asarray(Image.open(path).convert("RGBA")).astype(int)


def muzzle_point(frame: np.ndarray) -> tuple[int, int]:
    """Where derive_unit_frames.muzzle_flash put the flash: the figure's right
    edge, 38% down its height."""
    ys, xs = np.nonzero(frame[..., 3] > 24)
    if len(xs) == 0:
        return SPRITE - 6, SPRITE // 2
    left, top, right, bottom = xs.min(), ys.min(), xs.max() + 1, ys.max() + 1
    return int(min(SPRITE - 6, right + 1)), int(top + int((bottom - top) * 0.38))


def bucket(h: float) -> str | None:
    if h < 18 or h >= 330:
        return "red"
    if h < 55:
        return "orange"
    if h < 165:
        return "green"
    if h < 265:
        return "blue"
    return None


def bright_hues(frame: np.ndarray) -> dict[str, int]:
    """Count bright, tinted pixels by hue bucket. A flash core is nearly white,
    so a very bright pixel counts with only a slight tint; gun metal is
    neither that bright nor tinted."""
    out: dict[str, int] = {}
    for r, g, b, a in frame.reshape(-1, 4):
        if a < 128:
            continue
        h, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
        if (v >= 0.85 and s >= 0.2) or (v >= 0.92 and s >= 0.06):
            k = bucket(h * 360)
            if k:
                out[k] = out.get(k, 0) + 1
    return out


def painted_color(firing: np.ndarray) -> str | None:
    """The flash colour of a hand-drawn firing frame, from the bright tinted
    pixels at the muzzle: the figure's outermost 10 columns on either side
    (hand-drawn sets face either way; the rest of the pose differs from
    standing too, so a whole-frame comparison would count clothing). Skin and
    tan clothing are bright orange, so a red, green or blue tint there wins
    and orange counts only when nothing else is at the muzzle."""
    xs = np.nonzero((firing[..., 3] > 24).any(axis=0))[0]
    if len(xs) == 0:
        return None
    counts: dict[str, int] = {}
    for region in (firing[:, max(0, xs.max() - 9):xs.max() + 1], firing[:, xs.min():xs.min() + 10]):
        for k, n in bright_hues(region).items():
            counts[k] = counts.get(k, 0) + n
    laser = {k: n for k, n in counts.items() if k != "orange" and n >= 2}
    if laser:
        return max(laser.items(), key=lambda kv: kv[1])[0]
    return "orange" if counts.get("orange", 0) >= 3 else None


def scan() -> dict[str, dict]:
    result = {}
    for unit in sorted(p for p in UNITS.iterdir() if (p / "ranged-2.png").exists()):
        standing, r1, r2 = (rgba(unit / f"{n}.png") for n in ("standing", "ranged-1", "ranged-2"))
        derived = bool((standing == r1).all())
        mx, my = muzzle_point(r1)
        entry = {"kind": "derived" if derived else "painted",
                 "blit": [max(0, min(SPRITE - FLASH_W, mx - FLASH_W // 2)),
                          max(0, min(SPRITE - FLASH_H, my - FLASH_H // 2))]}
        if not derived:
            entry["color"] = painted_color(r2)
        result[unit.name] = entry
    return result


def strip_generic() -> list[str]:
    stripped = []
    for unit in sorted(p for p in UNITS.iterdir() if (p / "ranged-2.png").exists()):
        standing, r1, r2 = (rgba(unit / f"{n}.png") for n in ("standing", "ranged-1", "ranged-2"))
        if (standing == r1).all() and not (r1 == r2).all():
            Image.open(unit / "ranged-1.png").save(unit / "ranged-2.png", optimize=True)
            stripped.append(unit.name)
    return stripped


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--strip-generic", action="store_true")
    args = parser.parse_args()
    if args.strip_generic:
        print(f"stripped the baked-in flash from {len(strip_generic())} derived sets")
    text = json.dumps(scan(), indent=1, sort_keys=True) + "\n"
    if args.check:
        if not OUT.exists() or OUT.read_text(encoding="utf-8") != text:
            print("muzzle_flashes.json is stale: run scan_muzzle_flashes.py")
            return 1
        print("muzzle_flashes.json is current")
        return 0
    OUT.write_text(text, encoding="utf-8")
    print(f"wrote {OUT.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
