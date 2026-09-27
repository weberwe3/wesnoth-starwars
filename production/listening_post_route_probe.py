"""Exercise Listening Post Infiltration's legal recon route in isolated engine test mode.

The source scenario body and AI side remain intact. Only its root becomes a
Wesnoth [test] and test events issue the player moves. A prestart fixture
silently removes all side-2 units (fire_event=no); this scenario has no
enemy-die victory path (victory_when_enemies_defeated=no), so only the recon
moveto->victory wiring is exercised. Combat balance is explicitly untested
here. The recon squad has 2 MP (smallfoot); the 3-hex route (Gg, Ce, Ch, all
cost 1) takes 2 turns (limit 8). The terminal macro
{sw_one_time_moveto_event} is defined before the victory moveto event in the
source, so the scripted move onto the terminal hex deterministically sets the
flag before victory resolves.
This does not establish campaign entry, normal GUI play, transition execution,
or save/load.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

from sequence_load_probe import ADDON_ID, _latest_log, _sha256


SCENARIO_ID = "sw_06_listening_post_infiltration"
SOURCE_FILE = "scenarios/06_listening_post_infiltration.cfg"
TEST_ID = "sw_listening_post_objective_route"
VICTORY_MARKER = "sw_listening_post_route_verified"
UNIT_ID = "sw_listening_post_recon"
# Recon starts at (2,3) with 2 MP; the terminal hex is (5,3). Single-hex
# 2-point moves (the proven [do_command][move] pattern); 3 turns, limit 8.
# All hexes cost 1 for smallfoot (Gg, Ce, Ch).
STEPS = [
    ("2,3", "3,3", (3, 3)),
    ("3,4", "3,3", (4, 3)),
    ("4,5", "3,3", (5, 3)),
]
ENEMY_IDS = ("sw_listening_post_guard_one", "sw_listening_post_guard_leader")
VICTORY_HEX = (5, 3)


def _turn_events() -> str:
    # Proven multi-turn pattern (cf. mission_probe.py): one
    # "side 1 turn refresh" event per turn, gated by [filter_condition] on
    # turn_number, with [end_turn] on every turn except the victory turn.
    events = []
    for turn, (xs, ys, (fx, fy)) in enumerate(STEPS, start=1):
        sx, sy = xs.split(",")[0], ys.split(",")[0]
        end_turn = "" if turn == len(STEPS) else "        [end_turn]\n        [/end_turn]\n"
        events.append(f"""    [event]
        name=side 1 turn refresh
        first_time_only=no
        [filter_condition]
            [variable]
                name=turn_number
                equals={turn}
            [/variable]
        [/filter_condition]
        {{ASSERT (
            [have_unit]
                id={UNIT_ID}
                x,y={sx},{sy}
            [/have_unit]
        )}}
        [do_command]
            [move]
                x={xs}
                y={ys}
            [/move]
        [/do_command]
        {{ASSERT (
            [have_unit]
                id={UNIT_ID}
                x,y={fx},{fy}
            [/have_unit]
        )}}
{end_turn}    [/event]""")
    return "\n".join(events)


def _fixture(source: str) -> str:
    if (source.count("[scenario]") != 1 or source.count("[/scenario]") != 1
            or source.count("id=" + SCENARIO_ID) != 1):
        raise ValueError("Listening Post structure changed; refusing fixture transformation")
    if UNIT_ID not in source:
        raise ValueError("Listening Post victory unit missing; refusing fixture transformation")
    for enemy in ENEMY_IDS:
        if enemy not in source:
            raise ValueError(f"Listening Post enemy {enemy} missing; refusing fixture transformation")
    vx, vy = VICTORY_HEX
    if f"x={vx}" not in source or f"y={vy}" not in source:
        raise ValueError("Listening Post victory hex missing; refusing fixture transformation")
    if "sw_one_time_moveto_event" not in source:
        raise ValueError("Listening Post terminal macro missing; refusing fixture transformation")
    fixture = source.replace("[scenario]", "[test]\n    is_unit_test=yes", 1)
    fixture = fixture.replace("id=" + SCENARIO_ID, "id=" + TEST_ID, 1)
    kills = "\n".join(
        f"""        [kill]
            id={enemy}
            fire_event=no
            animate=no
        [/kill]""" for enemy in ENEMY_IDS)
    events = f"""
    # Fixture: silently clear all side-2 units. This scenario has no
    # enemy-die victory path, so only the recon moveto->victory wiring
    # is exercised.
    [event]
        name=prestart
{kills}
    [/event]
{_turn_events()}
    [event]
        name=victory
        {{ASSERT (
            [have_unit]
                id={UNIT_ID}
                x,y={vx},{vy}
            [/have_unit]
        )}}
        [wml_message]
            logger=warning
            message={VICTORY_MARKER}
        [/wml_message]
        {{SUCCEED}}
    [/event]
    [event]
        name=defeat
        {{FAIL}}
    [/event]"""
    return fixture.replace("[/scenario]", events + "\n[/test]", 1)


def probe(root: Path, engine: Path) -> dict:
    root = root.resolve(strict=True)
    if not engine.is_absolute() or engine.is_symlink() or not engine.is_file():
        raise ValueError("installed engine is missing or symlinked")
    engine = engine.resolve(strict=True)
    addon_source = root / "addons" / ADDON_ID
    source_path = addon_source / SOURCE_FILE
    with tempfile.TemporaryDirectory(prefix="sw-listening-post-route-") as temporary:
        userdata = Path(temporary)
        addon = userdata / "data" / "add-ons" / ADDON_ID
        shutil.copytree(addon_source, addon)
        fixtures = addon / "probe-tests"
        fixtures.mkdir()
        fixture_path = fixtures / "route.cfg"
        fixture_path.write_text(_fixture(source_path.read_text(encoding="utf-8")), encoding="utf-8")
        (addon / "_main.cfg").write_text(
            "#ifdef TEST\n"
            "[binary_path]\n    path=data/add-ons/" + ADDON_ID + "\n[/binary_path]\n"
            "[+units]\n    {~add-ons/" + ADDON_ID + "/units}\n[/units]\n"
            "{~add-ons/" + ADDON_ID + "/utils/mission_events.cfg}\n"
            "{~add-ons/" + ADDON_ID + "/probe-tests}\n"
            "#endif\n", encoding="utf-8")
        try:
            completed = subprocess.run(
                [str(engine), "--log-to-file", "--userdata-dir", str(userdata), "-u", TEST_ID],
                cwd=engine.parent, capture_output=True, text=True, timeout=90, check=False)
            exit_code = completed.returncode
        except subprocess.TimeoutExpired:
            exit_code = None
        log = _latest_log(userdata)
        passed = (exit_code == 8 and f"PASS TEST (VICTORY) (8): {TEST_ID}" in log
                  and VICTORY_MARKER in log
                  and "conditional test unexpectedly failed" not in log
                  and "Error via [do_command]" not in log
                  and "FAIL TEST" not in log)
        return {"schema_id": "wesnoth-starwars.production.listening-post-route-probe",
                "schema_version": 1, "exercise_type": "isolated_legal_player_objective_route",
                "scenario_id": SCENARIO_ID, "test_id": TEST_ID,
                "source_sha256": _sha256(source_path),
                "fixture_sha256": _sha256(fixture_path),
                "engine_sha256": _sha256(engine),
                "probe_sha256": _sha256(Path(__file__)),
                "exit_code": exit_code, "pass": passed,
                "transition": "unassessed", "save_reload": "unassessed",
                "normal_gui_play": "unassessed",
                "combat_balance": "unassessed",
                "diagnostic_tail": log[-3000:]}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine", type=Path, required=True)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parents[1]
                        / "agent/runtime/listening-post-route-probe.json")
    args = parser.parse_args()
    try:
        result = probe(args.repo_root, args.engine)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", prefix=".listening-post-route-",
                                     suffix=".tmp", dir=args.output.parent, delete=False) as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")
        temporary = Path(stream.name)
    os.replace(temporary, args.output)
    print(json.dumps({"pass": result["pass"], "exit_code": result["exit_code"],
                      "output": str(args.output)}))
    return 0 if result["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
