"""Exercise Defensive Hold's survival route in isolated engine test mode.

The source scenario body and AI side remain intact. Only its root becomes a
Wesnoth [test] and test events issue end-turn commands. A prestart fixture
silently removes all side-2 units (defeat is leader-only, so no defeat event
fires); this isolates the turn-8 survival->victory wiring from combat RNG.
Combat balance is explicitly untested here.
This does not establish campaign entry, normal GUI play, transition execution,
or save/load.

Headless note: the source scenario shows unconditional [message] dialogs in
the turn-8 victory event; a [message] shown mid-run waits for dismissal that
never comes in headless mode, so the fixture strips every [message] block --
dialog text is not what's under test.
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


SCENARIO_ID = "sw_04_defensive_hold"
TEST_ID = "sw_defensive_hold_survival_route"
VICTORY_MARKER = "sw_defensive_hold_route_verified"
NEXT_SCENARIO = "sw_05_relay_raid"
# Victory fires at the start of turn 8 (name="turn 8"). From side-1 turn 1,
# 14 [end_turn] commands (7 full rounds x 2 sides) land on side-1 turn-8 start.
END_TURNS = 14


def _strip_messages(source: str) -> tuple[str, int]:
    """Remove every [message]...[/message] block; return (stripped, count)."""
    stripped, count = re.subn(r"\[message\].*?\[/message\]", "", source, flags=re.DOTALL)
    return stripped, count


def _fixture(source: str) -> str:
    if (source.count("[scenario]") != 1 or source.count("[/scenario]") != 1
            or source.count("id=" + SCENARIO_ID) != 1):
        raise ValueError("Defensive Hold structure changed; refusing fixture transformation")
    if source.count('name="turn 8"') != 1:
        raise ValueError("turn-8 victory event changed; refusing fixture transformation")
    # Dialogs block headless execution; strip them fixture-side only.
    expected_messages = len(re.findall(r"\[message\].*?\[/message\]", source, flags=re.DOTALL))
    transformed, stripped = _strip_messages(source)
    if stripped != expected_messages or stripped == 0:
        raise ValueError("message strip count changed; refusing fixture transformation")
    transformed = transformed.replace("[scenario]", "[test]\n    is_unit_test=yes", 1)
    transformed = transformed.replace("id=" + SCENARIO_ID, "id=" + TEST_ID, 1)
    # The scenario-root next_scenario cannot be resolved in the isolated
    # probe-tests context (the scenarios directory is not included in the
    # fixture _main.cfg); strip it fixture-side only. The victory event's
    # [endlevel] has no next_scenario, so victory wiring is unaffected.
    if transformed.count("next_scenario=" + NEXT_SCENARIO) != 1:
        raise ValueError("root next_scenario changed; refusing fixture transformation")
    transformed = transformed.replace("next_scenario=" + NEXT_SCENARIO, "", 1)
    end_turns = ""
    events = f"""
    # Fixture: silently clear all side-2 units. Defeat is leader-only, so no
    # defeat event fires; this isolates the survival->victory wiring.
    [event]
        name=prestart
        [kill]
            side=2
            fire_event=no
            animate=no
        [/kill]
    [/event]
    # End each side-1 turn immediately. After 7 full rounds (14 end_turns
    # total across both sides), the "turn 8" event fires at the start of
    # side-1 turn 8, triggering victory.
    [event]
        name=side 1 turn
        first_time_only=no
        [end_turn]
        [/end_turn]
    [/event]
    [event]
        name=victory
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
    return transformed.replace("[/scenario]", events + "\n[/test]", 1)


def probe(root: Path, engine: Path) -> dict:
    root = root.resolve(strict=True)
    if not engine.is_absolute() or engine.is_symlink() or not engine.is_file():
        raise ValueError("installed engine is missing or symlinked")
    engine = engine.resolve(strict=True)
    addon_source = root / "addons" / ADDON_ID
    source_path = addon_source / "scenarios" / "04_defensive_hold.cfg"
    with tempfile.TemporaryDirectory(prefix="sw-defensive-hold-route-") as temporary:
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
        return {"schema_id": "wesnoth-starwars.production.defensive-hold-route-probe",
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
                        / "agent/runtime/defensive-hold-route-probe.json")
    args = parser.parse_args()
    try:
        result = probe(args.repo_root, args.engine)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", prefix=".defensive-hold-route-",
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
