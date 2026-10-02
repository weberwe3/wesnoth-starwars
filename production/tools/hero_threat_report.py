#!/usr/bin/env python3
"""Static turn-1 threat report for every hero's starting hex.

For each scenario, the report lists the side-1 heroes placed at start (the
side's own unit and every {SW_HERO ...} placement) and the enemy units placed
at start that can reach a hex next to the hero on their first move (hex
distance <= movement + 1, ignoring terrain cost, so it over-counts). The
expected damage is each reaching enemy's strongest attack (damage x strikes)
at a 55% hit chance. A hero whose expected damage is at least 80% of its
hitpoints is flagged "!!": the player could lose that hero before acting.

A side leader without x,y starts at the map's side-1 start marker. Only start-of-scenario units are counted (NORMAL difficulty); event-spawned
waves are not. This complements the AI soak (run_ai_soak.py), whose AI-played
heroes die for reasons a human would avoid.

Usage: python3 production/tools/hero_threat_report.py [--fail-on-flag]
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ADDON = Path(__file__).resolve().parents[2] / "addons/Star_Wars_Thrawn_Trilogy"
HIT_CHANCE = 0.55
FLAG_FRACTION = 0.8


def _key(block: str, key: str) -> str | None:
    match = re.search(rf"^\s*{key}=(.*)$", block, re.M)
    return match.group(1).strip() if match else None


def unit_stats() -> dict[str, dict[str, int]]:
    stats: dict[str, dict[str, int]] = {}
    for path in sorted((ADDON / "units").glob("*.cfg")):
        for match in re.finditer(r"\[unit_type\](.*?)\[/unit_type\]", path.read_text(encoding="utf-8"), re.S):
            body = match.group(1)
            best = 0
            for attack in re.finditer(r"\[attack\](.*?)\[/attack\]", body, re.S):
                try:
                    best = max(best, int(_key(attack.group(1), "damage")) * int(_key(attack.group(1), "number")))
                except (TypeError, ValueError):
                    continue
            try:
                stats[_key(body, "id")] = {"hp": int(_key(body, "hitpoints")),
                                           "mv": int(_key(body, "movement")), "best": best}
            except (TypeError, ValueError):
                continue
    return stats


def hex_distance(a: tuple[int, int], b: tuple[int, int]) -> int:
    """Wesnoth hex distance; WML coordinates are 1-based, even columns sit lower."""
    def cube(x: int, y: int) -> tuple[int, int, int]:
        col, row = x - 1, y - 1
        r = row - (col - (col & 1)) // 2
        return col, r, -col - r
    p, q = cube(*a), cube(*b)
    return max(abs(p[i] - q[i]) for i in range(3))


def map_start(text: str, side: int) -> tuple[int, int] | None:
    """Start hex of SIDE from the scenario's map file (rows/columns include the border)."""
    name = _key(text, "map_file")
    path = ADDON / "maps" / name if name else None
    if path is None or not path.is_file():
        return None
    for y, line in enumerate(path.read_text(encoding="utf-8").splitlines()):
        for x, token in enumerate(line.split(",")):
            if token.strip().startswith(f"{side} "):
                return x, y
    return None


def normal_difficulty(text: str) -> str:
    text = re.sub(r"#ifdef (EASY|HARD)\n.*?#endif", "", text, flags=re.S)
    return re.sub(r"#ifndef EASY\n(.*?)#endif", r"\1", text, flags=re.S)


def report(stats: dict[str, dict[str, int]]) -> list[dict]:
    rows = []
    for path in sorted((ADDON / "scenarios").glob("*/*.cfg")):
        text = normal_difficulty(path.read_text(encoding="utf-8"))
        sides = re.findall(r"\[side\](.*?)\[/side\]", text, re.S)
        if not sides:
            continue
        heroes = []
        own_type, own_xy = _key(sides[0], "type"), re.search(r"^\s*x,y=(\d+),(\d+)", sides[0], re.M)
        own_hex = (int(own_xy.group(1)), int(own_xy.group(2))) if own_xy else map_start(text, 1)
        if own_type and own_hex:
            heroes.append((own_type, own_hex))
        for match in re.finditer(r"\{SW_HERO(?:_LEADER)? (\S+) (\S+) \(.*?\) (\d+) (\d+)\}", text):
            heroes.append((match.group(2), (int(match.group(3)), int(match.group(4)))))
        enemies = []
        player_team = _key(sides[0], "team_name")
        for side in sides[1:]:
            if player_team and _key(side, "team_name") == player_team:
                continue  # allied side
            for unit in re.finditer(r"\[unit\](.*?)\[/unit\]", side, re.S):
                kind, xy = _key(unit.group(1), "type"), re.search(r"x,y=(\d+),(\d+)", unit.group(1))
                if kind and xy:
                    enemies.append((kind, (int(xy.group(1)), int(xy.group(2)))))
            for macro in re.finditer(r"\{\w+ (sw_\w+) (\d+) (\d+)\}", side):
                enemies.append((macro.group(1), (int(macro.group(2)), int(macro.group(3)))))
        for hero, where in heroes:
            if hero not in stats:
                continue
            reaching = [kind for kind, pos in enemies
                        if kind in stats and hex_distance(where, pos) <= stats[kind]["mv"] + 1]
            expected = sum(stats[kind]["best"] * HIT_CHANCE for kind in reaching)
            rows.append({"scenario": path.stem, "hero": hero, "hex": where, "hp": stats[hero]["hp"],
                         "reaching": reaching, "expected": round(expected),
                         "flag": expected >= stats[hero]["hp"] * FLAG_FRACTION})
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fail-on-flag", action="store_true")
    args = parser.parse_args()
    rows = report(unit_stats())
    for row in rows:
        print(f"{row['scenario']:34} {row['hero']:22} hp{row['hp']:>3} reach {len(row['reaching'])} "
              f"expected {row['expected']:>3}{'  !!' if row['flag'] else ''}")
    flagged = [row for row in rows if row["flag"]]
    print(f"{len(rows)} hero starts checked, {len(flagged)} flagged")
    return 1 if flagged and args.fail_on_flag else 0


if __name__ == "__main__":
    raise SystemExit(main())
