#!/usr/bin/env python3
"""Static balance numbers for every mission, read from the installed engine's
own preprocessor output (so macros, difficulty defines and includes resolve
exactly as in play).

For each campaign and difficulty: preprocess the add-on with the campaign
define and EASY/NORMAL/HARD, parse the plain WML, and report per scenario:

  turns, villages on the map, carryover;
  per side: controller, gold, income, recruit list, starting units
  (count / total cost / total HP, using the add-on's own unit types);
  reinforcements: units created by events after the start, by turn and side;
  the objectives text.

and a force ratio: enemy value (gold + starting units + reinforcements +
income over the turn limit) over the player's (gold + starting units +
income), the usual first-order balance signal (wiki BuildingScenariosBalancing).

Usage:
  python3 production/tools/mission_balance_report.py [--engine PATH]
      [--difficulty NORMAL ...] [--json out.json] [--markdown out.md]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ADDON = ROOT / "addons/Star_Wars_Thrawn_Trilogy"
ENGINE = Path.home() / "opt/bin/wesnoth-linux"
CAMPAIGN_DEFINES = {
    "Heir to the Empire": "CAMPAIGN_STAR_WARS_THRAWN_TRILOGY",
    "Dark Force Rising": "CAMPAIGN_STAR_WARS_DARK_FORCE_RISING",
    "The Last Command": "CAMPAIGN_STAR_WARS_THE_LAST_COMMAND",
}
DIFFICULTIES = ("EASY", "NORMAL", "HARD")


# ---------------------------------------------------------------- WML parsing

class Node:
    def __init__(self, tag: str):
        self.tag = tag
        self.attrs: dict[str, str] = {}
        self.children: list[Node] = []

    def all(self, tag: str) -> list["Node"]:
        return [c for c in self.children if c.tag == tag]

    def walk(self, tag: str):
        for c in self.children:
            if c.tag == tag:
                yield c
            yield from c.walk(tag)


STRING_PART = re.compile(r'\s*(?:_\s*)?"((?:[^"]|"")*)"\s*(\+)?\s*')


def parse_wml(text: str) -> Node:
    root = Node("root")
    stack = [root]
    i, n = 0, len(text)
    lines = text.split("\n")
    li = 0
    while li < len(lines):
        line = lines[li].strip()
        li += 1
        if not line or line.startswith("#"):
            continue
        if line.startswith("[/"):
            if len(stack) > 1:
                stack.pop()
            continue
        if line.startswith("[") and line.endswith("]"):
            tag = line[1:-1].lstrip("+")
            node = Node(tag)
            stack[-1].children.append(node)
            stack.append(node)
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        value = value.strip()
        if '"' in value:
            # Quoted (possibly multi-line, possibly concatenated) value.
            buf = value
            while buf.count('"') % 2 == 1 and li < len(lines):
                buf += "\n" + lines[li]
                li += 1
            parts = re.findall(r'"((?:[^"]|"")*)"', buf)
            value = "".join(p.replace('""', '"') for p in parts)
        elif value.startswith("<<"):
            buf = value
            while ">>" not in buf and li < len(lines):
                buf += "\n" + lines[li]
                li += 1
            value = buf[2:buf.index(">>")]
        for k in key.split(","):
            stack[-1].attrs[k.strip()] = value
    del i, n
    return root


# ---------------------------------------------------------------- analysis

def as_int(v, default=0):
    try:
        return int(float(str(v).strip()))
    except (TypeError, ValueError):
        return default


def unit_table(root: Node) -> dict[str, dict]:
    table = {}
    for ut in root.walk("unit_type"):
        uid = ut.attrs.get("id")
        if uid:
            table[uid] = {"cost": as_int(ut.attrs.get("cost"), 0), "hp": as_int(ut.attrs.get("hitpoints"), 0),
                          "level": as_int(ut.attrs.get("level"), 1), "name": ut.attrs.get("name", uid)}
    return table


def unit_value(types: dict, utype: str) -> tuple[int, int]:
    t = types.get(utype)
    if not t:
        return 0, 0
    # Leaders/heroes with no cost: value them like a recruit of their level.
    cost = t["cost"] or 14 * max(1, t["level"]) + 6
    return cost, t["hp"]


def count_villages(map_data: str) -> int:
    return sum(1 for code in re.split(r"[,\n]", map_data) if "^V" in code)


KEEP_CODE = re.compile(r"^(K|Qsk|Qkb|Qkp)|\^K")  # mainline keeps and utils/hte_terrain.cfg recruit_from


def player_start_on_keep(map_data: str) -> bool | None:
    """True if side 1's start hex is a keep; None if the map has no side-1 start."""
    for row in map_data.split("\n"):
        for cell in row.split(","):
            cell = cell.strip()
            if cell.startswith("1 "):
                return bool(KEEP_CODE.search(cell.split(" ")[-1]))
    return None


def turn_of(event_name: str) -> int | None:
    m = re.match(r"\s*(?:side \d+ )?turn (\d+)\s*$", event_name)
    if m:
        return int(m.group(1))
    m = re.match(r"\s*turn (\d+)\s*$", event_name)
    return int(m.group(1)) if m else None


def side_units(side: Node) -> list[str]:
    out = []
    if side.attrs.get("type"):
        out.append(side.attrs["type"])
    for leader in side.all("leader"):
        if leader.attrs.get("type"):
            out.append(leader.attrs["type"])
    for unit in side.all("unit"):
        if unit.attrs.get("type"):
            out.append(unit.attrs["type"])
    return out


def scenario_report(sc: Node, types: dict) -> dict:
    turns = as_int(sc.attrs.get("turns"), -1)
    sides = {}
    for side in sc.all("side"):
        num = as_int(side.attrs.get("side"), len(sides) + 1)
        units = side_units(side)
        cost = sum(unit_value(types, u)[0] for u in units)
        hp = sum(unit_value(types, u)[1] for u in units)
        sides[num] = {
            "controller": side.attrs.get("controller", "ai"),
            "team": side.attrs.get("team_name", ""),
            "gold": as_int(side.attrs.get("gold"), 100),
            "income": as_int(side.attrs.get("income"), 0),
            "recruit": [r for r in side.attrs.get("recruit", "").split(",") if r],
            "units": units, "unit_cost": cost, "unit_hp": hp,
            "villages": len(side.all("village")),
            "aggression": next((a.attrs.get("aggression") for a in side.walk("ai") if "aggression" in a.attrs), None),
        }
    start_spawn: dict[int, list[str]] = {}
    reinf: list[dict] = []
    objectives = []
    for ev in sc.all("event"):
        name = ev.attrs.get("name", "")
        for obj in ev.walk("objective"):
            objectives.append((obj.attrs.get("condition", ""), obj.attrs.get("description", "")))
        spawned = []
        for u in ev.walk("unit"):
            if u.attrs.get("type") and u.attrs.get("side"):
                spawned.append((as_int(u.attrs["side"]), u.attrs["type"]))
        if not spawned:
            continue
        first_names = [x.strip() for x in name.split(",")]
        if any(x in ("prestart", "start") for x in first_names):
            for s, t in spawned:
                start_spawn.setdefault(s, []).append(t)
        else:
            t = next((turn_of(x) for x in first_names if turn_of(x)), None)
            reinf.append({"event": name, "turn": t, "units": spawned})
    for s, lst in start_spawn.items():
        d = sides.setdefault(s, {"controller": "?", "team": "", "gold": 0, "income": 0, "recruit": [], "units": [],
                                 "unit_cost": 0, "unit_hp": 0, "villages": 0, "aggression": None})
        d["units"] = d["units"] + lst
        d["unit_cost"] += sum(unit_value(types, u)[0] for u in lst)
        d["unit_hp"] += sum(unit_value(types, u)[1] for u in lst)
    map_data = sc.attrs.get("map_data", "")
    if not map_data and sc.attrs.get("map_file"):
        found = list(ADDON.rglob(Path(sc.attrs["map_file"]).name))
        map_data = found[0].read_text(encoding="utf-8") if found else ""
    report = {
        "id": sc.attrs.get("id"), "name": sc.attrs.get("name"), "turns": turns,
        "villages": count_villages(map_data), "sides": sides, "reinforcements": reinf,
        "objectives": objectives,
        "carryover": sc.all("carryover") and True,
    }
    # A side that can recruit needs a keep to recruit from (two maps once lost
    # theirs to a path drawn over it).
    p1 = sides.get(1, {})
    report["warnings"] = []
    if p1.get("recruit") and p1.get("gold", 0) > 0 and player_start_on_keep(map_data) is False:
        report["warnings"].append("side 1 has gold and recruits but does not start on a keep")
    # Force ratio: side 1 (+ allied human/allied sides sharing its team) vs. the rest.
    player_team = sides.get(1, {}).get("team", "")
    span = turns if turns > 0 else 20
    player = enemy = 0
    reinf_by_side: dict[int, int] = {}
    for r in reinf:
        for s, t in r["units"]:
            reinf_by_side[s] = reinf_by_side.get(s, 0) + unit_value(types, t)[0]
    for num, d in sides.items():
        value = d["gold"] + d["unit_cost"] + reinf_by_side.get(num, 0)
        value += max(0, d["income"]) * span // 2  # base income accrues; half-weight (spent late)
        if d["recruit"] == [] and num != 1:
            value -= d["gold"]  # gold with nothing to recruit is not strength
        if num == 1 or (player_team and d.get("team") == player_team):
            player += value
        else:
            enemy += value
    report["player_value"] = player
    report["enemy_value"] = enemy
    report["force_ratio"] = round(enemy / player, 2) if player else None
    return report


def preprocess(engine: Path, define: str, difficulty: str, work: Path) -> Node:
    ud = work / "ud"
    if not (ud / "data/add-ons/Star_Wars_Thrawn_Trilogy").exists():
        (ud / "data/add-ons").mkdir(parents=True, exist_ok=True)
        shutil.copytree(ADDON, ud / "data/add-ons/Star_Wars_Thrawn_Trilogy")
    out = work / f"pp_{define}_{difficulty}"
    out.mkdir(parents=True, exist_ok=True)
    subprocess.run([str(engine), "--userdata-dir", str(ud), "--preprocess-defines", f"{define},{difficulty}",
                    "--preprocess", str(ud / "data/add-ons/Star_Wars_Thrawn_Trilogy"), str(out)],
                   check=True, capture_output=True, text=True, timeout=600)
    raw = (out / "_main.cfg.plain").read_bytes()
    # The plain output keeps the preprocessor's location markers (0xFE "line
    # ..." / "textdomain ...", each to the end of its line) even inside
    # values; drop each marker with its newline to restore the real text.
    raw = re.sub(rb"\xfe(?:line|textdomain)[^\n]*\n?", b"", raw)
    return parse_wml(raw.decode("utf-8", errors="replace"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine", type=Path, default=ENGINE)
    parser.add_argument("--difficulty", action="append", choices=DIFFICULTIES)
    parser.add_argument("--json", type=Path)
    parser.add_argument("--markdown", type=Path)
    args = parser.parse_args()
    results = {}
    with tempfile.TemporaryDirectory() as tmp:
        for campaign, define in CAMPAIGN_DEFINES.items():
            for diff in args.difficulty or DIFFICULTIES:
                root = preprocess(args.engine, define, diff, Path(tmp))
                types = unit_table(root)
                scenarios = [scenario_report(sc, types) for sc in root.walk("scenario")]
                results.setdefault(campaign, {})[diff] = scenarios
    if args.json:
        args.json.write_text(json.dumps(results, indent=1), encoding="utf-8")
    lines = []
    for campaign, by_diff in results.items():
        lines.append(f"## {campaign}")
        for diff, scenarios in by_diff.items():
            lines.append(f"### {diff}")
            lines.append("| scenario | turns | vill | P gold/inc | P units | enemy gold/inc | enemy units | reinf | ratio |")
            lines.append("|---|---|---|---|---|---|---|---|---|")
            for s in scenarios:
                p = s["sides"].get(1, {})
                en = [d for n, d in s["sides"].items() if n != 1 and d.get("team") != p.get("team")]
                eg = "+".join(f"{d['gold']}/{d['income']}" for d in en)
                eu = sum(len(d["units"]) for d in en)
                rn = sum(len(r["units"]) for r in s["reinforcements"])
                lines.append(f"| {s['id']} | {s['turns']} | {s['villages']} | {p.get('gold')}/{p.get('income')} | "
                             f"{len(p.get('units', []))} | {eg} | {eu} | {rn} | {s['force_ratio']} |")
    warnings = sorted({f"{s['id']}: {w}" for by in results.values() for sc in by.values() for s in sc
                       for w in s.get("warnings", [])})
    if warnings:
        lines += ["", "## Warnings"] + [f"- {w}" for w in warnings]
    text = "\n".join(lines) + "\n"
    if args.markdown:
        args.markdown.write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
