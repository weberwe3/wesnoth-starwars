#!/usr/bin/env python3
"""Build the Campaign II (Dark Force Rising) map files.

Same conventions as gen_hte_maps.py: deterministic primitives from
hte_mapkit, terrain rows only, mirrored border, and KEY_HEXES that scenario
WML depends on.

Usage: python3 production/tools/gen_dfr_maps.py [--check] [--preview DIR] [--keys]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from hte_mapkit import HexMap, neighbors, preview  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
MAPS = ROOT / "addons/Star_Wars_Thrawn_Trilogy/maps"
GREAT, RAIN, FLOOR = "Gll^Fet", "Gll^Ftr", "Gll"
SPACE, ROCKS, DECK = "Qsp", "Qsa", "Qsd"
KEY_HEXES: dict[str, dict[str, tuple[int, int]]] = {}


def keys(name: str, **points: tuple[int, int]) -> None:
    KEY_HEXES[name] = points


def ring(m: HexMap, keep: tuple[int, int], keep_code: str, castle_code: str, count: int) -> None:
    m.set(*keep, keep_code)
    for n in neighbors(*keep)[:count]:
        m.set(*n, castle_code)


# 1. The Noghri Prisoner -- Kashyyyk, 24x18 ---------------------------------
def m01() -> HexMap:
    m = HexMap(24, 18, GREAT, seed=2101)
    m.scatter(RAIN, 0.35)
    m.disc((15, 9), 2, "Iwr")
    ring(m, (15, 9), "Ke", "Ce", 5)
    for seg in ([(15, 9), (20, 4)], [(15, 9), (21, 15)], [(15, 9), (8, 9)]):
        m.path(seg, "Iwr")
    for v in ((20, 4), (21, 15), (8, 9), (17, 13), (12, 5)):
        m.set(*v, "Iwr^Vht")
    m.path([(1, 1), (3, 9), (1, 18)], "Ss")
    m.start(1, 15, 9)
    keys("dfr_01_the_noghri_prisoner", leia_keep=(15, 9), noghri_entry=(2, 9), khabarakh=(3, 8))
    return m


# 2. Honoghr -- blighted plain, 28x18 ---------------------------------------
def m02() -> HexMap:
    m = HexMap(28, 18, "Gd", seed=2202)
    m.scatter("Rb", 0.25)
    m.scatter("Hhd", 0.12)
    m.scatter("Gd^Edt", 0.04)
    m.path([(1, 12), (9, 10), (16, 13), (28, 9)], "Rd")
    m.path([(10, 1), (12, 8), (11, 18)], "Ww")
    m.set(12, 8, "Wwf")
    m.set(10, 11, "Wwf")
    for c in ((6, 4), (8, 15), (18, 4), (20, 15), (15, 9)):
        m.disc(c, 1, "Hhd")
    for v in ((7, 5), (17, 3), (19, 15), (14, 9)):
        m.set(*v, "Rb^Vhh")
    m.disc((25, 9), 2, "Rd")
    ring(m, (25, 9), "Kh", "Ch", 4)
    m.set(26, 9, "Rd^Vhh")
    m.start(1, 3, 12)
    keys("dfr_02_honoghr", start=(3, 12), dukha=(26, 9), droid_w=(9, 5), droid_c=(15, 12),
         droid_e=(21, 7), droid_s=(18, 16))
    return m


# 3. Jomark -- lake island, 26x20 -------------------------------------------
def m03() -> HexMap:
    m = HexMap(26, 20, "Gg", seed=2303)
    m.scatter("Gg^Fds", 0.3)
    m.scatter("Hh", 0.08)
    m.disc((15, 10), 6, "Wo")
    m.disc((15, 10), 7, "Ww", prob=0.5)
    m.disc((15, 10), 6, "Wo")
    m.disc((15, 10), 2, "Gg")
    m.set(15, 10, "Gg^Vh")
    m.path([(9, 10), (13, 10)], "Ww^Bsb\\")
    villages = dict(village_n=(13, 2), village_w=(4, 14), village_s=(18, 19))
    for v in villages.values():
        m.disc(v, 1, "Gg")
        m.set(*v, "Gg^Vh")
    m.disc((6, 9), 1, "Gg")
    ring(m, (6, 9), "Kh", "Ch", 4)
    m.disc((24, 4), 2, "Gg")
    ring(m, (24, 4), "Ke", "Ce", 4)
    m.start(1, 6, 9)
    m.start(3, 24, 4)
    keys("dfr_03_jomark", luke_keep=(6, 9), raider_keep=(24, 4), island=(15, 10), **villages)
    return m


# 4. The Senator's Men -- city, 26x18 ----------------------------------------
def m04() -> HexMap:
    m = HexMap(26, 18, "Rr", seed=2404)
    for x1, y1, x2, y2 in ((4, 3, 7, 5), (11, 2, 13, 4), (18, 3, 21, 5), (3, 9, 5, 11), (9, 8, 12, 10),
                           (16, 8, 18, 10), (22, 9, 24, 11), (6, 14, 9, 16), (13, 13, 15, 16), (19, 14, 22, 16)):
        m.rect(x1, y1, x2, y2, "Xos")
    for v in ((8, 3), (14, 5), (22, 6), (6, 9), (13, 9), (19, 11), (10, 15), (16, 12), (24, 13)):
        m.set(*v, "Rr^Vhc")
    m.disc((14, 7), 1, "Rrc")
    ring(m, (2, 16), "Kh", "Ch", 4)
    m.rect(23, 1, 26, 3, "Rrc")
    m.set(25, 2, "Qsk")
    ring(m, (24, 17), "Ke", "Ce", 3)
    m.start(1, 2, 16)
    m.start(2, 24, 17)
    keys("dfr_04_the_senators_men", han_keep=(2, 16), pad=(25, 2), agents_keep=(24, 17), commando_entry=(13, 1))
    return m


# 5. The Peregrine's Nest -- rock base, 28x20 --------------------------------
def m05() -> HexMap:
    m = HexMap(28, 20, "Hh", seed=2505)
    m.scatter("Mm", 0.2)
    m.scatter("Hhd", 0.15)
    m.path([(1, 10), (8, 9), (14, 11), (19, 10)], "Re", width=1)
    m.rect(19, 5, 27, 15, "Isr")
    m.rect(18, 5, 18, 15, "Xos")
    m.set(18, 10, "Isr")
    m.set(18, 7, "Isr")
    m.set(18, 13, "Isr")
    ring(m, (21, 10), "Kh", "Ch", 5)
    m.set(25, 10, "Isr^Vhc")
    for v in ((22, 6), (22, 14), (9, 4), (8, 16), (13, 6)):
        m.set(*v, "Isr^Vhc" if v[0] > 18 else "Hh^Vhh")
    m.disc((3, 10), 2, "Re")
    ring(m, (3, 10), "Ke", "Ce", 5)
    m.start(1, 21, 10)
    m.start(2, 3, 10)
    keys("dfr_05_peregrines_nest", han_keep=(21, 10), generator=(25, 10), imperial_keep=(3, 10))
    return m


# 6. The Mad Jedi -- lake and forest, 28x18 ----------------------------------
def m06() -> HexMap:
    m = HexMap(28, 18, "Gg^Fds", seed=2606)
    m.scatter("Gg", 0.25)
    m.scatter("Hh^Fds", 0.06)
    m.path([(14, 1), (13, 6), (15, 12), (14, 18)], "Ww", width=1)
    m.set(13, 6, "Wwf")
    m.set(15, 12, "Ww^Bsb|")
    m.disc((4, 9), 1, "Gg")
    m.set(4, 9, "Gg^Vh")
    m.disc((25, 9), 2, "Gg")
    m.set(26, 9, "Qsk")
    m.start(1, 4, 9)
    keys("dfr_06_the_mad_jedi", start=(4, 9), ship=(26, 9), cbaoth=(9, 9))
    return m


# 7. The Dark Force -- deep space, 30x22 -------------------------------------
def m07() -> HexMap:
    m = HexMap(30, 22, SPACE, seed=2707)
    m.disc((15, 3), 2, ROCKS, prob=0.4)
    m.disc((15, 19), 2, ROCKS, prob=0.4)
    m.disc((9, 11), 1, ROCKS, prob=0.5)
    m.disc((21, 11), 1, ROCKS, prob=0.5)
    ring(m, (3, 11), "Qsk", "Qsc", 5)
    ring(m, (28, 11), "Qsk", "Qsc", 5)
    ships = {f"dread_{i}": p for i, p in enumerate(
        ((12, 5), (18, 5), (11, 9), (19, 9), (12, 14), (18, 14), (15, 8), (15, 15)), start=1)}
    m.start(1, 3, 11)
    m.start(2, 28, 11)
    keys("dfr_07_the_dark_force", wedge_keep=(3, 11), imperial_keep=(28, 11), **ships)
    return m


# 8. Aboard the Katana -- ship interior, 26x18 -------------------------------
def m08() -> HexMap:
    m = HexMap(26, 18, "Xos", seed=2808)
    # Corridors and compartments of the Dreadnaught's spine.
    m.path([(2, 9), (24, 9)], DECK, width=1)
    for x in (6, 11, 16, 21):
        m.path([(x, 2), (x, 16)], DECK)
    m.rect(8, 2, 9, 5, DECK)
    m.rect(13, 13, 14, 16, DECK)
    m.rect(18, 2, 19, 5, DECK)
    m.rect(3, 13, 4, 16, DECK)
    m.rect(22, 6, 25, 12, DECK)
    for v in ((8, 3), (14, 15), (19, 3), (4, 14)):
        m.set(*v, "Qsd^Vov")
    ring(m, (3, 9), "Qsk", "Qsc", 3)
    m.set(24, 9, "Qsc")
    m.start(1, 3, 9)
    keys("dfr_08_aboard_the_katana", airlock=(3, 9), bridge=(24, 9))
    return m


# 9. Battle for the Fleet -- deep space, 30x22 -------------------------------
def m09() -> HexMap:
    m = HexMap(30, 22, SPACE, seed=2909)
    m.disc((10, 6), 2, ROCKS, prob=0.45)
    m.disc((20, 16), 2, ROCKS, prob=0.45)
    m.disc((22, 5), 1, ROCKS, prob=0.5)
    ring(m, (3, 11), "Qsk", "Qsc", 5)
    ring(m, (15, 1), "Qsk", "Qsc", 3)
    ring(m, (15, 22), "Qsk", "Qsc", 3)
    m.start(1, 3, 11)
    m.start(2, 15, 1)
    m.start(3, 15, 22)
    keys("dfr_09_battle_for_the_fleet", wedge_keep=(3, 11), chimaera=(15, 1), judicator=(15, 22),
         dread_1=(6, 9), dread_2=(6, 11), dread_3=(6, 13))
    return m


# 10. Honoghr's Choice -- Nystao, 26x18 --------------------------------------
def m10() -> HexMap:
    m = HexMap(26, 18, "Gd", seed=3010)
    m.scatter("Rb", 0.2)
    m.scatter("Hhd", 0.1)
    m.disc((13, 9), 3, "Rd")
    ring(m, (13, 9), "Kh", "Ch", 5)
    for v in ((10, 7), (16, 7), (10, 12), (16, 12), (13, 5), (13, 13)):
        m.set(*v, "Rd^Vhh")
    m.disc((2, 9), 1, "Rd")
    ring(m, (2, 9), "Ke", "Ce", 3)
    m.disc((25, 9), 1, "Rd")
    m.start(1, 13, 9)
    m.start(2, 2, 9)
    keys("dfr_10_honoghrs_choice", dukha=(13, 9), west_lz=(2, 9), east_lz=(25, 9))
    return m


BUILDERS = {
    "dfr_01_the_noghri_prisoner": m01,
    "dfr_02_honoghr": m02,
    "dfr_03_jomark": m03,
    "dfr_04_the_senators_men": m04,
    "dfr_05_peregrines_nest": m05,
    "dfr_06_the_mad_jedi": m06,
    "dfr_07_the_dark_force": m07,
    "dfr_08_aboard_the_katana": m08,
    "dfr_09_battle_for_the_fleet": m09,
    "dfr_10_honoghrs_choice": m10,
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
            marks = {pos: label[0].upper() for label, pos in KEY_HEXES.get(name, {}).items()}
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
