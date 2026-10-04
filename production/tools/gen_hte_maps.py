#!/usr/bin/env python3
"""Build the Campaign I (Heir to the Empire) map files.

Each map is constructed from deterministic primitives in hte_mapkit, written
to ``maps/hte_*.map`` (terrain rows only, including a mirrored border), and
optionally previewed as PNGs for review (``--preview DIR``).

Gameplay-critical hexes (objectives, keeps, spawn points) are listed in
``KEY_HEXES`` and asserted after construction so scenario WML and maps cannot
silently drift apart.

Usage: python3 production/tools/gen_hte_maps.py [--check] [--preview DIR]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from hte_mapkit import HexMap, neighbors, preview  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
MAPS = ROOT / "addons/Star_Wars_Thrawn_Trilogy/maps"

FOREST = "Gll^Fds"
RAIN = "Gll^Ftr"
GREAT = "Gll^Fet"
FLOOR = "Gll"
DIRT = "Re"
SPACE = "Qsp"
ROCKS = "Qsa"
DECK = "Qsd"

KEY_HEXES: dict[str, dict[str, tuple[int, int]]] = {}


def keys(name: str, **points: tuple[int, int]) -> None:
    KEY_HEXES[name] = points


def castle_ring(m: HexMap, keep: tuple[int, int], keep_code: str, castle_code: str, count: int) -> None:
    m.set(*keep, keep_code)
    for n in neighbors(*keep)[:count]:
        m.set(*n, castle_code)


# 1. The Grand Admiral's Harvest -- Myrkr forest, 26x18 -----------------------
def m01() -> HexMap:
    m = HexMap(26, 18, FOREST, seed=101)
    m.planet = "myrkr"  # planet forests (hte_mapkit.PLANET_FORESTS)
    m.scatter(RAIN, 0.30)
    m.scatter(GREAT, 0.05)
    m.scatter("Hh^Fds", 0.05)
    # Shuttle clearing on the west edge.
    m.disc((4, 9), 3, FLOOR)
    m.scatter("Gll^Efm", 0.15, where=FLOOR)
    castle_ring(m, (3, 9), "Ke", "Ce", 4)
    # North-south stream with two fords on the trails.
    m.path([(9, 1), (8, 6), (10, 12), (9, 18)], "Ww")
    # Trails out to the four marked ysalamiri trees.
    m.path([(5, 9), (8, 7), (12, 5)], DIRT, keep=("Ww",))
    m.path([(5, 10), (9, 12), (13, 13), (17, 13)], DIRT, keep=("Ww",))
    m.path([(12, 5), (16, 4), (21, 5)], DIRT)
    m.path([(17, 13), (20, 14), (23, 15)], DIRT)
    for f in ((8, 7), (9, 12), (8, 6), (10, 12)):
        if m.get(*f) == "Ww":
            m.set(*f, "Wwf")
    # Smugglers' observation camp to the north.
    m.disc((14, 2), 1, DIRT)
    m.set(13, 2, "Re^Vct")
    m.set(15, 2, "Re^Vct")
    m.set(14, 1, "Re^Ecf")
    # Vornskr dens.
    m.disc((24, 9), 1, "Hh")
    m.set(24, 9, FLOOR)
    m.disc((12, 17), 1, "Hh")
    m.set(12, 17, FLOOR)
    # Hunters' cabins (villages).
    for v in ((6, 4), (6, 15), (19, 9), (15, 16), (22, 2), (25, 13), (11, 9)):
        m.set(*v, "Gll^Vl")
    trees = dict(tree_n=(12, 4), tree_ne=(21, 5), tree_c=(17, 13), tree_se=(23, 15))
    for t in trees.values():
        m.set(*t, GREAT)
    m.start(1, 3, 9)
    keys("hte_01_ysalamiri_harvest", shuttle=(3, 9), den_east=(24, 9), den_south=(12, 17),
         camp=(14, 2), **trees)
    return m


# 2. Ambush at Bpfassh -- city, 26x18 ------------------------------------------
def m02() -> HexMap:
    m = HexMap(26, 18, "Rr", seed=202)
    m.interior = "colony"  # location interior (hte_mapkit.INTERIORS)
    # City blocks: impassable building masses separated by streets.
    blocks = [(3, 2, 5, 4), (9, 2, 11, 3), (15, 2, 17, 4), (3, 7, 4, 9), (8, 6, 10, 8), (14, 7, 16, 8),
              (20, 6, 22, 8), (3, 13, 5, 15), (9, 12, 11, 14), (15, 12, 17, 13), (20, 11, 22, 13),
              (13, 16, 16, 17)]
    for x1, y1, x2, y2 in blocks:
        m.rect(x1, y1, x2, y2, "Xos")
    # Shops and residences scattered along the streets (villages).
    for v in ((6, 3), (12, 2), (18, 5), (5, 8), (11, 7), (13, 8), (19, 8), (6, 14), (12, 13), (18, 12),
              (23, 12), (17, 16)):
        m.set(*v, "Rr^Vhc")
    # Central plaza and two parks (forest gives Noghri cover).
    m.disc((13, 10), 2, "Rrc")
    m.disc((7, 11), 1, "Gg^Fds")
    m.disc((19, 15), 2, "Gg^Fds")
    m.disc((24, 9), 1, "Gg^Fds")
    # Government hall where Leia starts (south-west) and the Falcon's pad.
    castle_ring(m, (2, 16), "Kh", "Ch", 5)
    m.rect(23, 1, 26, 4, "Rrc")
    m.set(25, 2, "Qsk")
    # A canal crossing the east side with bridges on two streets.
    m.path([(20, 1), (19, 5), (19, 10)], "Ww")
    m.set(19, 3, "Ww^Bsb|")
    m.set(19, 9, "Ww^Bsb|")
    # Imperial landing area in the north-west.
    castle_ring(m, (7, 1), "Ke", "Ce", 4)
    m.start(1, 2, 16)
    m.start(2, 7, 1)
    keys("hte_02_ambush_at_bpfassh", leia_start=(2, 16), falcon=(25, 2), plaza=(13, 10),
         imperial_lz=(7, 1), park_west=(7, 11), park_east=(19, 15))
    return m


# 3. Adrift -- deep space, 22x16 ------------------------------------------------
def m03() -> HexMap:
    m = HexMap(22, 16, SPACE, seed=303)
    # A drifting asteroid cluster around Luke and a thinner belt to the east.
    m.disc((7, 8), 3, ROCKS, prob=0.55)
    m.disc((15, 4), 2, ROCKS, prob=0.45)
    m.disc((16, 13), 2, ROCKS, prob=0.45)
    m.disc((20, 8), 1, ROCKS, prob=0.5)
    m.set(6, 8, SPACE)
    m.start(1, 6, 8)
    keys("hte_03_adrift", luke=(6, 8), tie_spawn_ne=(22, 2), tie_spawn_e=(22, 8), tie_spawn_se=(22, 15),
         karrde_arrival=(2, 2))
    return m


# 4. Shadows of Kashyyyk -- wroshyr forest, 26x20 -----------------------------
def m04() -> HexMap:
    m = HexMap(26, 20, GREAT, seed=404)
    m.planet = "kashyyyk"  # planet forests (hte_mapkit.PLANET_FORESTS)
    m.scatter(RAIN, 0.35)
    m.scatter("Ss^Ftr", 0.06)
    # Village platforms and walkways high in the trees.
    m.disc((12, 10), 2, "Iwr")
    walk = [[(12, 10), (5, 5)], [(12, 10), (20, 4)], [(12, 10), (21, 15)], [(12, 10), (6, 16)]]
    for seg in walk:
        m.path(seg, "Iwr")
    # The keep goes down after the walkways: drawn first, the walkways from
    # its hex painted over it and Leia could never recruit (balance review
    # 2026-10-04).
    castle_ring(m, (12, 10), "Ke", "Ce", 5)
    for v in ((5, 5), (20, 4), (21, 15), (6, 16), (14, 13), (9, 8), (16, 8), (3, 11), (24, 10)):
        m.set(*v, "Iwr^Vht")
    # Deep under-forest gullies.
    m.path([(1, 1), (4, 9), (2, 20)], "Ss")
    m.path([(26, 1), (23, 9), (26, 20)], "Ss")
    m.start(1, 12, 10)
    keys("hte_04_shadows_of_kashyyyk", leia_start=(12, 10), noghri_w=(1, 10), noghri_e=(26, 10),
         noghri_n=(13, 1), noghri_s=(13, 20))
    return m


# 5. Prisoner of Myrkr -- smuggler compound, 24x18 ------------------------------
def compound(m: HexMap, ox: int, oy: int) -> dict[str, tuple[int, int]]:
    """Karrde's compound shared by missions 5 and 6 (origin = north-west wall)."""
    m.rect(ox, oy, ox + 15, oy + 12, "Re")
    m.rect(ox, oy, ox + 15, oy, "Xos")
    m.rect(ox, oy + 12, ox + 15, oy + 12, "Xos")
    m.rect(ox, oy, ox, oy + 12, "Xos")
    m.rect(ox + 15, oy, ox + 15, oy + 12, "Xos")
    # Main house (offices) in the north-west with an interior floor.
    m.rect(ox + 1, oy + 1, ox + 6, oy + 4, "Isr")
    m.rect(ox + 1, oy + 5, ox + 6, oy + 5, "Xos")
    m.set(ox + 4, oy + 5, "Isr")
    # Detention block in the south-west.
    m.rect(ox + 1, oy + 8, ox + 4, oy + 11, "Isr")
    m.rect(ox + 5, oy + 8, ox + 5, oy + 11, "Xos")
    m.set(ox + 5, oy + 10, "Isr")
    # Vehicle shed and hangar in the east.
    m.rect(ox + 11, oy + 4, ox + 14, oy + 8, "Isr")
    m.rect(ox + 10, oy + 4, ox + 10, oy + 8, "Xos")
    m.set(ox + 10, oy + 6, "Isr")
    # Gates.
    m.set(ox + 15, oy + 6, "Re")
    m.set(ox + 8, oy, "Re")
    m.set(ox, oy + 6, "Re")
    # Cargo crates: cover in the yard and inside the buildings, so an
    # intruder can move from shadow to shadow (^Qcr: castle-grade cover).
    for dx, dy in ((7, 9), (7, 6), (9, 5), (12, 2), (3, 6), (13, 9), (11, 11), (6, 11), (2, 9), (5, 2), (12, 6)):
        x, y = ox + dx, oy + dy
        base = m.cells[(x, y)].partition("^")[0]
        m.set(x, y, base + "^Qcr")
    # Barracks and stores (villages) in the yard.
    for dx, dy in ((8, 3), (8, 9), (12, 10), (2, 2)):
        m.set(ox + dx, oy + dy, "Re^Vhc" if (dx, dy) != (2, 2) else "Isr^Vhc")
    return dict(office=(ox + 2, oy + 2), cell=(ox + 2, oy + 10), shed=(ox + 13, oy + 6),
                east_gate=(ox + 15, oy + 6), north_gate=(ox + 8, oy), west_gate=(ox, oy + 6))


def m05() -> HexMap:
    m = HexMap(24, 18, FOREST, seed=505)
    m.interior = "timber"  # location interior (hte_mapkit.INTERIORS)
    m.planet = "myrkr"  # planet forests (hte_mapkit.PLANET_FORESTS)
    m.scatter(RAIN, 0.3)
    m.scatter(GREAT, 0.05)
    k = compound(m, 4, 3)
    # Ysalamiri frames hang throughout the compound.
    keys("hte_05_prisoner_of_myrkr", ysal_1=(7, 6), ysal_2=(12, 9), ysal_3=(16, 11), **k)
    m.start(1, *k["cell"])
    return m


# 6. Raid on Karrde's Base -- compound and forest, 28x20 ------------------------
def m06() -> HexMap:
    m = HexMap(28, 20, FOREST, seed=606)
    m.interior = "timber"  # location interior (hte_mapkit.INTERIORS)
    m.planet = "myrkr"  # planet forests (hte_mapkit.PLANET_FORESTS)
    m.scatter(RAIN, 0.25)
    m.scatter(GREAT, 0.04)
    k = compound(m, 9, 4)
    # Landing field with evacuation transports to the east.
    m.rect(25, 6, 28, 15, "Rrc")
    for e in ((27, 8), (27, 11), (27, 14)):
        m.set(*e, "Qsk")
    # Imperial staging area to the west.
    m.disc((3, 10), 2, FLOOR)
    castle_ring(m, (3, 10), "Ke", "Ce", 5)
    m.path([(5, 10), (9, 10)], DIRT)
    m.path([(24, 10), (25, 10)], DIRT)
    keep = (k["office"][0] + 2, k["office"][1] + 1)
    castle_ring(m, keep, "Kh", "Ch", 3)
    for v in ((2, 3), (4, 17), (21, 2), (21, 18), (14, 18), (7, 6)):
        m.set(*v, "Gll^Vl")
    m.start(1, *keep)
    m.start(2, 3, 10)
    keys("hte_06_raid_on_karrdes_base", han_keep=keep, imperial_keep=(3, 10), evac_n=(27, 8),
         evac_c=(27, 11), evac_s=(27, 14), **k)
    return m


# 7. The Forest Crossing -- Myrkr forest, 30x20 ---------------------------------
def m07() -> HexMap:
    m = HexMap(30, 20, FOREST, seed=707)
    m.planet = "myrkr"  # planet forests (hte_mapkit.PLANET_FORESTS)
    m.scatter(RAIN, 0.35)
    m.scatter(GREAT, 0.08)
    m.scatter("Hh^Fds", 0.06)
    # Crash site in the west.
    m.disc((3, 12), 1, FLOOR)
    m.set(4, 12, "Gll^Dr")
    m.start(1, 3, 12)
    # Clearings where speeder bikes are dangerous.
    m.disc((10, 6), 2, FLOOR)
    m.disc((15, 15), 2, FLOOR)
    m.disc((21, 8), 2, FLOOR)
    # River with one ford and a log bridge.
    m.path([(18, 1), (17, 8), (19, 14), (18, 20)], "Ww")
    m.set(17, 8, "Wwf")
    m.set(19, 14, "Ww^Bsb|")
    # Hunter's cabin where Karrde's people can be contacted.
    m.set(12, 11, "Gll^Vl")
    m.set(24, 16, "Gll^Vl")
    m.set(8, 17, "Gll^Vl")
    # Hyllyard City on the eastern edge.
    m.rect(28, 6, 30, 15, "Rr")
    for v in ((28, 7), (29, 9), (28, 11), (29, 13), (30, 10)):
        m.set(*v, "Rr^Vhc")
    keys("hte_07_the_forest_crossing", crash=(3, 12), cabin=(12, 11), city_w=(28, 10),
         ysal_west=(9, 13), ysal_mid=(16, 5), ysal_east=(23, 12))
    return m


# 8. Nomad City -- Nkllon, 28x18 ------------------------------------------------
def m08() -> HexMap:
    m = HexMap(28, 18, "Dd", seed=808)
    m.scatter("Hd", 0.18)
    m.scatter("Hhd", 0.10)
    m.scatter("Mm", 0.04)
    # Nomad City: a huge armored platform in the east.
    m.rect(17, 4, 26, 15, "Isr")
    m.rect(16, 4, 16, 15, "Xos")
    m.rect(17, 3, 26, 3, "Xos")
    m.rect(17, 16, 26, 16, "Xos")
    for g in ((16, 7), (16, 12), (21, 3), (21, 16)):
        m.set(*g, "Isr")
    castle_ring(m, (23, 9), "Kh", "Ch", 5)
    # Mole miner sheds at the city's edge (villages).
    sheds = dict(shed_1=(18, 5), shed_2=(18, 14), shed_3=(20, 9), shed_4=(25, 5), shed_5=(25, 14))
    for s in sheds.values():
        m.set(*s, "Isr^Vhc")
    # Shade: rock outcrops scattered across the sunside plain.
    for c in ((5, 4), (9, 13), (12, 7), (4, 15), (13, 16), (8, 2)):
        m.disc(c, 1, "Hhd")
    # Imperial raiders' landing zone and extraction point in the west.
    castle_ring(m, (3, 9), "Ke", "Ce", 4)
    m.start(1, 23, 9)
    m.start(2, 3, 9)
    keys("hte_08_nomad_city", lando_keep=(23, 9), raider_keep=(3, 9), extraction=(1, 9), **sheds)
    return m


# 9. The Sluis Van Shipyards -- orbital, 28x20 ----------------------------------
def m09() -> HexMap:
    m = HexMap(28, 20, SPACE, seed=909)
    # Shipyard station arms with four docked warships.
    m.rect(3, 4, 9, 5, DECK)
    m.rect(3, 15, 9, 16, DECK)
    m.rect(3, 6, 4, 14, DECK)
    castle_ring(m, (4, 10), "Qsk", "Qsc", 5)
    m.disc((22, 3), 1, ROCKS, prob=0.6)
    m.disc((24, 17), 2, ROCKS, prob=0.5)
    m.disc((15, 10), 1, ROCKS, prob=0.4)
    ships = dict(ship_1=(10, 4), ship_2=(10, 16), ship_3=(6, 7), ship_4=(6, 13))
    m.start(1, 4, 10)
    keys("hte_09_sluis_van_shipyards", wedge_keep=(4, 10), miner_entry_n=(28, 4), miner_entry_s=(28, 16),
         tie_entry=(28, 10), **ships)
    return m


# 10. Thrawn's Gambit -- orbital, 30x22 -----------------------------------------
def m10() -> HexMap:
    m = HexMap(30, 22, SPACE, seed=1010)
    m.rect(2, 5, 7, 6, DECK)
    m.rect(2, 17, 7, 18, DECK)
    m.rect(2, 7, 3, 16, DECK)
    castle_ring(m, (3, 11), "Qsk", "Qsc", 5)
    castle_ring(m, (26, 8), "Qsk", "Qsc", 4)
    castle_ring(m, (26, 15), "Qsk", "Qsc", 4)
    m.disc((15, 4), 2, ROCKS, prob=0.5)
    m.disc((14, 18), 2, ROCKS, prob=0.5)
    m.disc((19, 11), 1, ROCKS, prob=0.5)
    m.start(1, 3, 11)
    m.start(2, 26, 8)
    m.start(3, 26, 15)
    keys("hte_10_thrawns_gambit", wedge_keep=(3, 11), chimaera=(26, 8), judicator=(26, 15),
         ship_1=(8, 6), ship_2=(8, 17))
    return m


BUILDERS = {
    "hte_01_ysalamiri_harvest": m01,
    "hte_02_ambush_at_bpfassh": m02,
    "hte_03_adrift": m03,
    "hte_04_shadows_of_kashyyyk": m04,
    "hte_05_prisoner_of_myrkr": m05,
    "hte_06_raid_on_karrdes_base": m06,
    "hte_07_the_forest_crossing": m07,
    "hte_08_nomad_city": m08,
    "hte_09_sluis_van_shipyards": m09,
    "hte_10_thrawns_gambit": m10,
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--preview", type=Path)
    parser.add_argument("--keys", action="store_true", help="print key hexes")
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
