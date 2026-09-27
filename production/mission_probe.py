"""Exercise one source mission through isolated Wesnoth test-mode fixtures.

Every fixture changes the root tag and adds bounded observations/actions.
Specific cases also change enemy control, dialogue, starting placement, or a
death handler in the temporary copy; results declare those controls. Engine
actions and outcomes are evidence only for the exercised fixture conditions.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile


ADDON_ID = "Star_Wars_Thrawn_Trilogy"
SCENARIO = "scenarios/dark_force_rising/21_restore_the_beacon.cfg"
ORIGINAL_ID = "sw_21_restore_the_beacon"
GUARD = "#ifdef CAMPAIGN_STAR_WARS_DARK_FORCE_RISING"
TERMINAL_DIALOGUE = '''        [message]
            speaker=sw_beacon_field_engineer_team
            message= _ "Beacon synchronized. New Republic channels are live again."
        [/message]
'''
ENGINEER_DIE_EVENT = '''    [event]
        name=die
        [filter]
            id=sw_beacon_field_engineer_team
        [/filter]
        [endlevel]
            result=defeat
        [/endlevel]
    [/event]
'''
CASES = {
    "load": r'''
    [event]
        name=side 1 turn 1
        {ASSERT (
            [have_unit]
                id=sw_beacon_field_engineer_team
                x,y=2,3
            [/have_unit]
        )}
        {SUCCEED}
    [/event]
''',
    "movement_point": r'''
    [event]
        name=side 1 turn 1
        {ASSERT (
            [have_unit]
                id=sw_beacon_field_engineer_team
                x,y=2,3
                [filter_wml]
                    moves=1
                [/filter_wml]
            [/have_unit]
        )}
        {SUCCEED}
    [/event]
''',
    "first_move": r'''
    [event]
        name=side 1 turn 1
        [do_command]
            [move]
                x=2,3
                y=3,3
            [/move]
        [/do_command]
        {ASSERT (
            [have_unit]
                id=sw_beacon_field_engineer_team
                x,y=3,3
            [/have_unit]
        )}
        {SUCCEED}
    [/event]
''',
    "first_move_origin": r'''
    [event]
        name=side 1 turn 1
        [do_command]
            [move]
                x=2,3
                y=3,3
            [/move]
        [/do_command]
        {ASSERT (
            [have_unit]
                id=sw_beacon_field_engineer_team
                x,y=2,3
            [/have_unit]
        )}
        {SUCCEED}
    [/event]
''',
    "two_turns": r'''
    [event]
        name=side 1 turn refresh
        first_time_only=no
        [filter_condition]
            [variable]
                name=turn_number
                equals=1
            [/variable]
        [/filter_condition]
        [do_command]
            [move]
                x=2,3
                y=3,3
            [/move]
        [/do_command]
        {ASSERT (
            [have_unit]
                id=sw_beacon_field_engineer_team
                x,y=3,3
            [/have_unit]
        )}
        [end_turn]
        [/end_turn]
    [/event]
    [event]
        name=side 1 turn refresh
        first_time_only=no
        [filter_condition]
            [variable]
                name=turn_number
                equals=2
            [/variable]
        [/filter_condition]
        [do_command]
            [move]
                x=3,4
                y=3,3
            [/move]
        [/do_command]
        {ASSERT (
            [have_unit]
                id=sw_beacon_field_engineer_team
                x,y=4,3
            [/have_unit]
        )}
        {SUCCEED}
    [/event]
''',
}


def _assert_unit_at(unit_id: str, x: int, y: int) -> str:
    return (
        "{ASSERT (\n"
        "    [have_unit]\n"
        f"        id={unit_id}\n"
        f"        x,y={x},{y}\n"
        "    [/have_unit]\n"
        ")}"
    )


def _beacon_route_events() -> str:
    """Issue player move commands; only the source objective may end the level."""

    route = [(2, 3), (3, 3), (4, 3), (5, 3), (6, 4), (7, 4), (8, 3)]
    events = []
    for turn, (origin, target) in enumerate(zip(route, route[1:]), 1):
        x0, y0 = origin
        x1, y1 = target
        expectation = (
            "" if turn == len(route) - 1 else
            _assert_unit_at("sw_beacon_field_engineer_team", x1, y1)
        )
        end_turn = "" if turn == len(route) - 1 else "[end_turn]\n[/end_turn]"
        events.append(
            "[event]\n"
            "    name=side 1 turn refresh\n"
            "    first_time_only=no\n"
            "    [filter_condition]\n        [variable]\n"
            f"            name=turn_number\n            equals={turn}\n"
            "        [/variable]\n    [/filter_condition]\n"
            "    [do_command]\n        [move]\n"
            f"            x={x0},{x1}\n            y={y0},{y1}\n"
            "        [/move]\n    [/do_command]\n"
            f"    {expectation}\n    {end_turn}\n"
            "[/event]\n"
        )
    events.append(
        "[event]\n    name=victory\n"
        "    " + _assert_unit_at("sw_beacon_field_engineer_team", 8, 3) + "\n"
        "    {SUCCEED}\n[/event]\n"
        "[event]\n    name=defeat\n    {FAIL}\n[/event]\n"
    )
    return "\n".join(events)


CASES["path_to_beacon"] = _beacon_route_events()


CASES["wrong_unit_terminal"] = r'''
    [event]
        name=side 1 turn 1
        {ASSERT (
            [have_unit]
                id=sw_beacon_commander
                x,y=7,2
            [/have_unit]
        )}
        [do_command]
            [move]
                x=7,8
                y=2,3
            [/move]
        [/do_command]
        {ASSERT (
            [have_unit]
                id=sw_beacon_commander
                x,y=8,3
            [/have_unit]
        )}
        {SUCCEED}
    [/event]
    [event]
        name=victory
        {FAIL}
    [/event]
'''
CASES["commander_start"] = r'''
    [event]
        name=side 1 turn 1
        {ASSERT (
            [have_unit]
                id=sw_beacon_commander
                x,y=1,3
            [/have_unit]
        )}
        {SUCCEED}
    [/event]
'''
CASES["timeout_defeat"] = r'''
    [event]
        name=side 1 turn refresh
        first_time_only=no
        [wml_message]
            logger=warning
            message=probe_turn_$turn_number
        [/wml_message]
        {ASSERT (
            [have_unit]
                id=sw_beacon_commander
            [/have_unit]
        )}
        {ASSERT (
            [have_unit]
                id=sw_beacon_field_engineer_team
            [/have_unit]
        )}
        [end_turn]
        [/end_turn]
    [/event]
'''
CASES["engineer_death_direct"] = r'''
    [event]
        name=side 1 turn 1
        [kill]
            id=sw_beacon_field_engineer_team
            fire_event=yes
        [/kill]
        {FAIL}
    [/event]
'''
CASES["commander_death_direct"] = r'''
    [event]
        name=side 1 turn 1
        [kill]
            id=sw_beacon_commander
            fire_event=yes
        [/kill]
        {FAIL}
    [/event]
'''
CASES["engineer_death_handler_removed"] = r'''
    [event]
        name=side 1 turn 1
        [kill]
            id=sw_beacon_field_engineer_team
            fire_event=yes
        [/kill]
        {ASSERT (
            [have_unit]
                id=sw_beacon_commander
            [/have_unit]
        )}
        {SUCCEED}
    [/event]
'''
EXPECTED_VERDICTS = {
    "load": "pass",
    "movement_point": "pass",
    "first_move": "pass",
    "first_move_origin": "fail",
    "two_turns": "pass",
    "path_to_beacon": "victory",
    "wrong_unit_terminal": "pass",
    "commander_start": "pass",
    "timeout_defeat": "defeat",
    "engineer_death_direct": "defeat",
    "commander_death_direct": "defeat",
    "engineer_death_handler_removed": "pass",
}
EXERCISE_TYPES = {
    "load": "engine_scenario_initial_state",
    "movement_point": "engine_scenario_initial_state",
    "first_move": "engine_player_move_command",
    "first_move_origin": "engine_negative_position_fixture",
    "two_turns": "engine_player_move_sequence",
    "path_to_beacon": "engine_player_move_sequence_to_original_victory",
    "wrong_unit_terminal": "staged_wrong_unit_then_engine_player_move_command",
    "commander_start": "engine_scenario_initial_state",
    "timeout_defeat": "normal_turn_progression_to_time_limit_defeat",
    "engineer_death_direct": "direct_death_event_injection",
    "commander_death_direct": "direct_death_event_injection",
    "engineer_death_handler_removed": "direct_death_event_injection_mutation_negative",
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _render_test(source: str, case: str) -> str:
    if source.count(GUARD) != 1 or source.count("#endif") != 1:
        raise ValueError("scenario guard changed; refusing test transformation")
    if source.count("[scenario]") != 1 or source.count("[/scenario]") != 1:
        raise ValueError("scenario root changed; refusing test transformation")
    if source.count("id=" + ORIGINAL_ID) != 1:
        raise ValueError("scenario ID changed; refusing test transformation")
    test_id = "sw_probe_restore_beacon_" + case
    transformed = source.replace(GUARD, "", 1).replace("#endif", "", 1)
    if case == "path_to_beacon":
        if transformed.count(TERMINAL_DIALOGUE) != 1:
            raise ValueError("terminal dialogue changed; refusing fixture transformation")
        transformed = transformed.replace(TERMINAL_DIALOGUE, "", 1)
        if transformed.count("controller=ai") != 1:
            raise ValueError("enemy controller changed; refusing fixture transformation")
        transformed = transformed.replace("controller=ai", "controller=null", 1)
    if case == "wrong_unit_terminal":
        commander_start = "id=sw_beacon_commander\n        name= _ \"New Republic Commander\"\n        x=1\n        y=3"
        if transformed.count(commander_start) != 1:
            raise ValueError("commander start changed; refusing fixture transformation")
        transformed = transformed.replace(commander_start, commander_start.replace("x=1", "x=7").replace("y=3", "y=2"), 1)
    if case == "timeout_defeat":
        if transformed.count("controller=ai") != 1:
            raise ValueError("enemy controller changed; refusing fixture transformation")
        transformed = transformed.replace("controller=ai", "controller=null", 1)
    if case == "engineer_death_handler_removed":
        if transformed.count(ENGINEER_DIE_EVENT) != 1:
            raise ValueError("engineer death handler changed; refusing mutation fixture")
        transformed = transformed.replace(ENGINEER_DIE_EVENT, "", 1)
    transformed = transformed.replace("[scenario]", "[test]\n    is_unit_test=yes", 1)
    transformed = transformed.replace("id=" + ORIGINAL_ID, "id=" + test_id, 1)
    transformed = transformed.replace("[/scenario]", CASES[case] + "[/test]", 1)
    return transformed


def _latest_log(userdata: Path) -> str:
    paths = sorted(
        (path for path in userdata.rglob("*.log") if path.is_file() and not path.name.endswith(".out.log")),
        key=lambda path: path.stat().st_mtime_ns,
    )
    if not paths or paths[-1].stat().st_size > 5_000_000:
        return ""
    return paths[-1].read_text(encoding="utf-8", errors="replace")[-12000:]


def run_probe(root: Path, engine: Path, case_names: list[str], *, temporary_movetype_fix: bool = False) -> dict:
    root = root.resolve(strict=True)
    engine = engine.resolve(strict=True)
    addon_source = root / "addons" / ADDON_ID
    scenario_path = addon_source / SCENARIO
    source = scenario_path.read_text(encoding="utf-8")
    unit_source_hashes = {
        path.relative_to(root).as_posix(): _sha256(path)
        for path in sorted((addon_source / "units").glob("*.cfg"))
    }
    with tempfile.TemporaryDirectory(prefix="sw-mission-probe-") as temporary:
        userdata = Path(temporary)
        addon = userdata / "data" / "add-ons" / ADDON_ID
        shutil.copytree(addon_source, addon)
        changed_movetypes = 0
        if temporary_movetype_fix:
            for unit_file in (addon / "units").glob("*.cfg"):
                text = unit_file.read_text(encoding="utf-8")
                text, foot_count = re.subn(r"(?m)^([ \t]*movement_type=)foot[ \t]*$", r"\1smallfoot", text)
                text, mount_count = re.subn(r"(?m)^([ \t]*movement_type=)mount[ \t]*$", r"\1mounted", text)
                changed_movetypes += foot_count + mount_count
                unit_file.write_text(text, encoding="utf-8")
            if changed_movetypes == 0:
                raise ValueError("diagnostic movement-type override found no source occurrences")
        fixtures = addon / "probe-tests"
        fixtures.mkdir()
        for case in case_names:
            (fixtures / (case + ".cfg")).write_text(_render_test(source, case), encoding="utf-8")
        (addon / "_main.cfg").write_text(
            "#ifdef TEST\n"
            "[binary_path]\n    path=data/add-ons/" + ADDON_ID + "\n[/binary_path]\n"
            "[+units]\n    {~add-ons/" + ADDON_ID + "/units}\n[/units]\n"
            "{~add-ons/" + ADDON_ID + "/utils/mission_events.cfg}\n"
            "{~add-ons/" + ADDON_ID + "/probe-tests}\n"
            "#endif\n",
            encoding="utf-8",
        )
        results = []
        engine_version = None
        for case in case_names:
            test_id = "sw_probe_restore_beacon_" + case
            command = [str(engine), "--log-to-file", "--userdata-dir", str(userdata), "-u", test_id]
            try:
                completed = subprocess.run(
                    command, cwd=engine.parent, capture_output=True, text=True,
                    timeout=60, check=False,
                )
                log = _latest_log(userdata)
                version_match = re.search(r"Battle for Wesnoth v([0-9]+(?:\.[0-9]+)+)", log)
                if version_match:
                    engine_version = version_match.group(1)
                if any(marker in log for marker in (
                    "Unknown scenario:", "Couldn't find [test]", "error config:",
                    "error wml:", "Error via [do_command]",
                )):
                    verdict = "invalid_fixture"
                elif f"PASS TEST (VICTORY) (8): {test_id}" in log:
                    verdict = "victory"
                elif f"FAIL TEST (DEFEAT) (7): {test_id}" in log:
                    verdict = "defeat"
                elif f"PASS TEST (0): {test_id}" in log:
                    verdict = "pass"
                elif re.search(rf"FAIL TEST .*: {re.escape(test_id)}", log):
                    verdict = "fail"
                else:
                    verdict = "unknown"
                expected = EXPECTED_VERDICTS[case]
                meets_expectation = (
                    verdict == expected
                    and completed.returncode == {"pass": 0, "fail": 1, "victory": 8, "defeat": 7}[expected]
                    and (expected != "fail" or "conditional test unexpectedly failed" in log)
                    and (case != "timeout_defeat" or "probe_turn_10" in log)
                )
                results.append({
                    "case": case,
                    "test_id": test_id,
                    "fixture_sha256": _sha256(fixtures / (case + ".cfg")),
                    "exercise_type": EXERCISE_TYPES[case],
                    "exit_code": completed.returncode,
                    "log_verdict": verdict,
                    "expected_verdict": expected,
                    "meets_expectation": meets_expectation,
                    "diagnostic_tail": log[-6000:],
                })
            except subprocess.TimeoutExpired:
                log = _latest_log(userdata)
                results.append({"case": case, "test_id": test_id,
                                "exercise_type": EXERCISE_TYPES[case], "exit_code": None,
                                "log_verdict": "timeout", "expected_verdict": EXPECTED_VERDICTS[case],
                                "meets_expectation": False, "diagnostic_tail": log[-6000:]})
    verified_cases = {row["case"] for row in results if row["meets_expectation"]}
    return {
        "schema_id": "wesnoth-starwars.production.mission-probe",
        "schema_version": 1,
        "scenario_id": ORIGINAL_ID,
        "scenario_source_sha256": _sha256(scenario_path),
        "unit_source_sha256": unit_source_hashes,
        "engine_binary_sha256": _sha256(engine),
        "engine_version": engine_version,
        "exercise_type": "instrumented_real_scenario_test_mode",
        "terminal_dialogue_suppressed_in_path_fixture": "path_to_beacon" in case_names,
        "enemy_turn_disabled_in_path_fixture": "path_to_beacon" in case_names,
        "commander_start_staged_in_wrong_unit_fixture": "wrong_unit_terminal" in case_names,
        "enemy_turn_disabled_in_timeout_fixture": "timeout_defeat" in case_names,
        "engineer_death_handler_removed_in_negative_fixture": "engineer_death_handler_removed" in case_names,
        "temporary_movetype_fix": temporary_movetype_fix,
        "temporary_movetype_replacements": changed_movetypes,
        "results": results,
        "pass": all(row["meets_expectation"] for row in results),
        "legal_objective_victory": (
            "observed_with_enemy_turn_disabled_and_terminal_dialogue_suppressed"
            if "path_to_beacon" in verified_cases else "unassessed"
        ),
        "wrong_unit_rejection": (
            "observed_with_commander_start_staged"
            if "wrong_unit_terminal" in verified_cases else "unassessed"
        ),
        "mission_transition": "unassessed",
        "defeat_paths": {
            "turn_limit": "observed_with_enemy_turn_disabled" if "timeout_defeat" in verified_cases else "unassessed",
            "engineer_death": (
                "direct_death_event_and_source_handler_causality_observed"
                if {"engineer_death_direct", "engineer_death_handler_removed"} <= verified_cases
                else "unassessed"
            ),
            "commander_death": "direct_death_defeat_observed" if "commander_death_direct" in verified_cases else "unassessed",
        },
        "save_reload": "unassessed",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine", required=True)
    parser.add_argument("--repo-root", default=Path(__file__).resolve().parents[1])
    parser.add_argument("--cases", nargs="+", choices=sorted(CASES), default=[
        "load", "movement_point", "first_move", "first_move_origin",
        "path_to_beacon", "wrong_unit_terminal", "timeout_defeat",
        "engineer_death_direct", "engineer_death_handler_removed",
        "commander_death_direct",
    ])
    parser.add_argument("--temporary-movetype-fix", action="store_true", help="diagnostic only: replace invalid movement type names in the temporary copy")
    parser.add_argument("--output", default=Path(__file__).resolve().parents[1] / "agent/runtime/mission-probe.json")
    args = parser.parse_args()
    result = run_probe(Path(args.repo_root), Path(args.engine), args.cases,
                       temporary_movetype_fix=args.temporary_movetype_fix)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", prefix=".mission-probe-", suffix=".tmp",
        dir=output.parent, delete=False,
    ) as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")
        temporary = Path(stream.name)
    os.replace(temporary, output)
    print(json.dumps({
        "pass": result["pass"],
        "results": [{k: row[k] for k in ("case", "exit_code", "log_verdict", "meets_expectation")}
                    for row in result["results"]],
        "output": str(output),
    }))
    return 0 if result["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
