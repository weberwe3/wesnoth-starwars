#!/usr/bin/env python3
"""Build the Campaign III (The Last Command) map files.

Same conventions as gen_hte_maps.py / gen_dfr_maps.py.

Usage: python3 production/tools/gen_tlc_maps.py [--check] [--preview DIR] [--keys]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from hte_mapkit import HexMap, neighbors, preview  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
MAPS = ROOT / "addons/Star_Wars_Thrawn_Trilogy/maps"
SPACE, ROCKS, DECK = "Qsp", "Qsa", "Qsd"
JUNGLE, RAIN = "Gg^Ftr", "Gll^Ftr"
KEY_HEXES: dict[str, dict[str, object]] = {}


def keys(name: str, **points: object) -> None:
    KEY_HEXES[name] = points


def ring(m: HexMap, keep: tuple[int, int], keep_code: str, castle_code: str, count: int) -> None:
    m.set(*keep, keep_code)
    for n in neighbors(*keep)[:count]:
        m.set(*n, castle_code)


# Hidden asteroid positions for the Coruscant cordon (mission 1).
CORDON = ((12, 4), (14, 9), (13, 15), (17, 6), (18, 12), (16, 18), (20, 9), (21, 15), (11, 11), (19, 3))
# Asteroid screen at Bilbringi (mission 9).
SCREEN = ((14, 5), (15, 9), (14, 13), (15, 17), (16, 11), (13, 2), (16, 20))


# 1. The Siege of Coruscant -- orbital, 30x22 ---------------------------------
def m01() -> HexMap:
    m = HexMap(30, 22, SPACE, seed=3101)
    m.rect(1, 1, 3, 22, DECK)
    ring(m, (4, 11), "Qsk", "Qsc", 5)
    m.disc((25, 4), 1, ROCKS, prob=0.4)
    m.disc((26, 19), 1, ROCKS, prob=0.4)
    m.start(1, 4, 11)
    keys("tlc_01_the_siege_of_coruscant", wedge_keep=(4, 11), minelayer_n=(26, 6), minelayer_s=(26, 16),
         cordon=CORDON)
    return m


# 2. The Smugglers' Council -- fortress, 26x20 --------------------------------
def m02() -> HexMap:
    m = HexMap(26, 20, "Hh", seed=3202)
    m.interior = "colony"  # location interior (hte_mapkit.INTERIORS)
    m.scatter("Dd", 0.3)
    m.scatter("Mm", 0.08)
    m.disc((12, 10), 5, "Xos")
    m.disc((12, 10), 4, "Isr")
    for gate in ((12, 5), (17, 10), (7, 10), (12, 15)):
        m.set(*gate, "Isr")
    ring(m, (12, 10), "Kh", "Ch", 5)
    for v in ((10, 7), (14, 7), (10, 13), (14, 13)):
        m.set(*v, "Isr^Vhc")
    m.disc((23, 10), 1, "Dd")
    ring(m, (23, 10), "Ke", "Ce", 4)
    m.start(1, 12, 10)
    m.start(2, 23, 10)
    keys("tlc_02_the_smugglers_council", karrde_keep=(12, 10), imperial_keep=(23, 10),
         chiefs=((10, 8), (14, 8), (10, 12), (14, 12), (12, 13)))
    return m


# 3. The Palace Infiltrators -- palace interior, 26x18 -------------------------
def m03() -> HexMap:
    m = HexMap(26, 18, "Isr", seed=3303)
    m.interior = "palace"  # location interior (hte_mapkit.INTERIORS)
    for x in (6, 12, 18):
        m.rect(x, 1, x, 18, "Xos")
        for y in (4, 9, 14):
            m.set(x, y, "Isr")
    m.rect(1, 6, 26, 6, "Xos")
    m.rect(1, 12, 26, 12, "Xos")
    for x in (3, 9, 15, 22):
        m.set(x, 6, "Isr")
        m.set(x, 12, "Isr")
    m.rect(20, 7, 24, 11, "Iwr")
    m.set(22, 9, "Iwr^Vov")
    ring(m, (9, 9), "Kh", "Ch", 3)
    for v in ((3, 3), (15, 15), (24, 3)):
        m.set(*v, "Isr^Vhc")
    m.start(1, 9, 9)
    keys("tlc_03_the_palace_infiltrators", leia_keep=(9, 9), nursery=(22, 9),
         entries=((1, 3), (1, 15), (13, 1), (25, 17)))
    return m


# 4. Landfall on Wayland -- jungle, 28x20 --------------------------------------
def m04() -> HexMap:
    m = HexMap(28, 20, JUNGLE, seed=3404)
    m.planet = "wayland"  # planet forests (hte_mapkit.PLANET_FORESTS)
    m.scatter("Gg", 0.2)
    m.scatter("Hh^Fp", 0.08)
    m.path([(26, 1), (25, 8), (27, 14), (26, 20)], "Ww", width=1)
    m.set(25, 10, "Wwf")
    m.set(26, 10, "Wwf")
    m.disc((3, 10), 1, "Gg")
    m.set(4, 10, "Gg^Dr")
    m.disc((12, 5), 2, "Gg")
    m.disc((15, 15), 2, "Gg")
    m.start(1, 3, 10)
    keys("tlc_04_landfall_on_wayland", crash=(3, 10), crossing=(26, 10))
    return m


# 5. The Natives of Wayland -- jungle and hills, 28x20 -------------------------
def m05() -> HexMap:
    m = HexMap(28, 20, JUNGLE, seed=3505)
    m.planet = "wayland"  # planet forests (hte_mapkit.PLANET_FORESTS)
    m.scatter("Hh", 0.12)
    m.scatter("Gg", 0.2)
    m.disc((22, 10), 2, "Re")
    ring(m, (22, 10), "Ke", "Ce", 5)
    m.rect(19, 6, 25, 6, "Gg^Eqp")
    for v in ((6, 4), (6, 16), (13, 3), (13, 17), (24, 15)):
        m.set(*v, "Gg^Vht")
    m.disc((3, 10), 1, "Gg")
    m.start(1, 3, 10)
    m.start(2, 22, 10)
    keys("tlc_05_the_natives_of_wayland", start=(3, 10), outpost_keep=(22, 10), native_entry=(1, 4))
    return m


# 6. The Gates of Mount Tantiss -- mountain base, 28x20 ------------------------
def m06() -> HexMap:
    m = HexMap(28, 20, "Hh", seed=3606)
    m.interior = "rock"  # location interior (hte_mapkit.INTERIORS)
    m.planet = "wayland"  # planet forests (hte_mapkit.PLANET_FORESTS)
    m.scatter("Mm", 0.22)
    m.scatter(JUNGLE, 0.15)
    m.rect(25, 1, 28, 20, "Mm^Xm")
    m.path([(2, 10), (12, 9), (20, 10), (25, 10)], "Re", width=1)
    m.rect(22, 7, 26, 13, "Isr")
    m.set(25, 10, "Isr")
    ring(m, (3, 10), "Kh", "Ch", 5)
    ring(m, (21, 10), "Ke", "Ce", 4)
    m.start(1, 3, 10)
    m.start(2, 21, 10)
    keys("tlc_06_the_gates_of_tantiss", han_keep=(3, 10), garrison_keep=(21, 10), generator=(24, 10))
    return m


# 7. The Cloning Vats -- interior, 26x18 ---------------------------------------
def m07() -> HexMap:
    m = HexMap(26, 18, "Xos", seed=3707)
    m.interior = "rock"  # location interior (hte_mapkit.INTERIORS)
    m.path([(2, 9), (25, 9)], "Isr", width=1)
    m.rect(8, 2, 23, 16, "Isr")
    for x in (11, 15, 19):
        m.rect(x, 4, x, 7, "Xos")
        m.rect(x, 11, x, 14, "Xos")
    ring(m, (3, 9), "Kh", "Ch", 3)
    cylinders = ((10, 3), (13, 5), (17, 4), (21, 6), (10, 15), (13, 13), (17, 14), (21, 12))
    m.start(1, 3, 9)
    keys("tlc_07_the_cloning_vats", entry=(3, 9), cylinders=cylinders, garrison=(23, 9))
    return m


# 8. The Throne Room -- 20x16 --------------------------------------------------
def m08() -> HexMap:
    m = HexMap(20, 16, "Isr", seed=3808)
    m.interior = "rock"  # location interior (hte_mapkit.INTERIORS)
    m.rect(1, 1, 20, 1, "Xos")
    m.rect(1, 16, 20, 16, "Xos")
    for pillar in ((6, 4), (6, 12), (10, 4), (10, 12), (14, 4), (14, 12)):
        m.set(*pillar, "Xos")
    m.rect(16, 6, 18, 10, "Urc")
    m.set(17, 8, "Urc^Vov")
    m.start(1, 3, 8)
    keys("tlc_08_the_throne_room", start=(3, 8), throne=(17, 8), luuke=(14, 8))
    return m


# 9. The Bilbringi Shipyards -- orbital, 30x22 ---------------------------------
def m09() -> HexMap:
    m = HexMap(30, 22, SPACE, seed=3909)
    ring(m, (3, 11), "Qsk", "Qsc", 5)
    m.rect(23, 3, 27, 19, DECK)
    ring(m, (27, 11), "Qsk", "Qsc", 4)
    m.disc((9, 4), 1, ROCKS, prob=0.5)
    m.disc((8, 18), 1, ROCKS, prob=0.5)
    platforms = ((22, 4), (22, 9), (22, 14), (22, 19))
    m.start(1, 3, 11)
    m.start(2, 27, 11)
    keys("tlc_09_bilbringi", wedge_keep=(3, 11), shipyard_keep=(27, 11), platforms=platforms, screen=SCREEN)
    return m


# 10. The Last Command -- orbital, 30x22 ---------------------------------------
def m10() -> HexMap:
    m = HexMap(30, 22, SPACE, seed=4010)
    ring(m, (3, 11), "Qsk", "Qsc", 5)
    ring(m, (27, 11), "Qsk", "Qsc", 4)
    ring(m, (25, 4), "Qsk", "Qsc", 3)
    ring(m, (25, 18), "Qsk", "Qsc", 3)
    m.disc((14, 6), 2, ROCKS, prob=0.45)
    m.disc((15, 16), 2, ROCKS, prob=0.45)
    m.start(1, 3, 11)
    m.start(2, 27, 11)
    m.start(3, 25, 4)
    m.start(4, 25, 18)
    keys("tlc_10_the_last_command", wedge_keep=(3, 11), chimaera=(27, 11), escort_n=(25, 4), escort_s=(25, 18))
    return m


BUILDERS = {
    "tlc_01_the_siege_of_coruscant": m01,
    "tlc_02_the_smugglers_council": m02,
    "tlc_03_the_palace_infiltrators": m03,
    "tlc_04_landfall_on_wayland": m04,
    "tlc_05_the_natives_of_wayland": m05,
    "tlc_06_the_gates_of_tantiss": m06,
    "tlc_07_the_cloning_vats": m07,
    "tlc_08_the_throne_room": m08,
    "tlc_09_bilbringi": m09,
    "tlc_10_the_last_command": m10,
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--preview", type=Path)
    parser.add_argument("--keys", action="store_true")
    args = parser.parse_args()
    stale = []
    for name, build in BUILDERS.items():
        m = build()
        text = m.text()
        path = MAPS / f"{name}.map"
        if args.check:
            if not path.is_file() or path.read_text(encoding="utf-8") != text:
                stale.append(path.name)
        else:
            path.write_text(text, encoding="utf-8")
        if args.preview:
            args.preview.mkdir(parents=True, exist_ok=True)
            marks = {pos: label[0].upper() for label, pos in KEY_HEXES.get(name, {}).items()
                     if isinstance(pos, tuple) and len(pos) == 2 and isinstance(pos[0], int)}
            preview(m, args.preview / f"{name}.png", marks)
    if args.keys:
        for name, pts in KEY_HEXES.items():
            print(name, pts)
    if stale:
        print("stale maps: " + ", ".join(stale), file=sys.stderr)
        return 1
    print(("checked " if args.check else "wrote ") + f"{len(BUILDERS)} maps")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
