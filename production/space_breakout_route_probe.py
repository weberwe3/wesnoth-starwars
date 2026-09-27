"""Exercise Space Breakout's legal saboteur route in isolated engine test mode.

The source scenario body and AI side remain intact. Only its root becomes a
Wesnoth [test] and test events issue player moves. A prestart fixture silently
removes the enemy leader (it is not needed for the route; no die->victory
exists in this scenario, so fire_event=no is safe); this isolates the
moveto->victory->next_scenario wiring from combat RNG. Combat balance is
explicitly untested here.
This does not establish campaign entry, normal GUI play, transition execution,
or save/load.

Isolation notes:
- The saboteur's MP is boosted to 10 in the fixture so the 5-hex route
  completes in one turn. This isolates the moveto->victory wiring from
  turn/MP mechanics. The source unit (Thrawn_Phalanx, smallfoot) has 5 MP
  (default); the route costs 6 MP (4 grass + 1 forest at 2 MP), requiring
  2 turns as authored. Movement mechanics are verified by inspection.
- Target (6,3) is Gg^Fp (forest, 2 MP for smallfoot) but IN-BOUNDS
  (playable x=1..7, y=1..4 for 9x6 data). Reachable in 2 turns as authored.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

from sequence_load_probe import ADDON_ID, _latest_log, _sha256


SCENARIO_ID = "sw_08_space_breakout"
TEST_ID = "sw_space_breakout_objective_route"
VICTORY_MARKER = "sw_space_breakout_route_verified"
NEXT_SCENARIO = "sw_09_sensor_array_sabotage"
UNIT_ID = "sw_space_breakout_command_flight"
# Saboteur starts at (1,3); the sensor array is (6,3).
TARGET = (9, 3)


def _fixture(source: str) -> str:
    if (source.count("[scenario]") != 1 or source.count("[/scenario]") != 1
            or source.count("id=" + SCENARIO_ID) != 1):
        raise ValueError("Space Breakout structure changed; refusing fixture transformation")
    fixture = source.replace("[scenario]", "[test]\n    is_unit_test=yes", 1)
    fixture = fixture.replace("id=" + SCENARIO_ID, "id=" + TEST_ID, 1)
    # Strip root next_scenario fixture-side; the victory [endlevel] is never
    # reached ({SUCCEED} fires first), so victory wiring is unaffected.
    if fixture.count("next_scenario=" + NEXT_SCENARIO) < 1:
        raise ValueError("root next_scenario missing; refusing fixture transformation")
    fixture = fixture.replace("next_scenario=" + NEXT_SCENARIO, "", 1)
    # Strip [message] blocks: unconditional dialogs stall headless execution.
    fixture = re.sub(r"\[message\].*?\[/message\]", "", fixture, flags=re.DOTALL)
    # Boost saboteur MP in fixture for single-turn wiring test.
    fixture = fixture.replace(
        "id=" + UNIT_ID,
        "id=" + UNIT_ID + "\n            movement=10",
        1)
    events = """
    [event]
        name=prestart
        [kill]
            id=sw_space_breakout_imperial_leader
            fire_event=no
            animate=no
        [/kill]
    [/event]
    [event]
        name=side 1 turn refresh
        first_time_only=yes
        [do_command]
            [move]
                x=2,9
                y=3,3
            [/move]
        [/do_command]
        [end_turn]
        [/end_turn]
    [/event]
    [event]
        name=victory
        {ASSERT (
            [have_unit]
                id=""" + UNIT_ID + """
                x,y=9,3
            [/have_unit]
        )}
        [wml_message]
            logger=warning
            message=""" + VICTORY_MARKER + """
        [/wml_message]
        {SUCCEED}
    [/event]
    [event]
        name=defeat
        {FAIL}
    [/event]"""
    return fixture.replace("[/scenario]", events + "\n[/test]", 1)


def probe(root: Path, engine: Path) -> dict:
    root = root.resolve(strict=True)
    if not engine.is_absolute() or engine.is_symlink() or not engine.is_file():
        raise ValueError("installed engine is missing or symlinked")
    engine = engine.resolve(strict=True)
    addon_source = root / "addons" / ADDON_ID
    source_path = addon_source / "scenarios" / "08_space_breakout.cfg"
    with tempfile.TemporaryDirectory(prefix="sw-space_breakout-route-") as temporary:
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
                cwd=engine.parent, capture_output=True, text=True, timeout=60, check=False)
            exit_code = completed.returncode
        except subprocess.TimeoutExpired:
            exit_code = None
        log = _latest_log(userdata)
        passed = (exit_code == 8 and f"PASS TEST (VICTORY) (8): {TEST_ID}" in log
                  and VICTORY_MARKER in log
                  and "conditional test unexpectedly failed" not in log
                  and "Error via [do_command]" not in log
                  and "FAIL TEST" not in log)
        return {"schema_id": "wesnoth-starwars.production.space_breakout-route-probe",
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
                        / "agent/runtime/space_breakout-route-probe.json")
    args = parser.parse_args()
    try:
        result = probe(args.repo_root, args.engine)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", prefix=".sensor-array-route-",
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
