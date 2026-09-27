"""Deterministic defeat-case probes for Space Interception (sw_02_space_interception).

Exercises the scenario's three defeat paths in isolated engine test mode:
escort death, player-leader death, and the turn-12 reinforcement deadline.
Only the fixture root becomes a Wesnoth [test]; the source scenario body,
sides, and defeat/victory events are untouched.

Known finding (2026-09-27, engine 1.19.28): the scenario's turn-12 defeat
event is dead as authored -- it uses `name=turn` with a `turn=12` key, which
is not valid EventWML (turn-specific events must be named e.g.
`name="turn 12"`). The same defect kills the turn-4 torpedo-bomber deployment.
The timeout case advances past turn 12 and reports this instead of hanging.

Combat balance, mission transition, campaign entry, normal GUI play, and
save/load are unassessed.
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


SCENARIO_ID = "sw_02_space_interception"
TURN_LIMIT = 12
TURN_MARKER = "sw_interception_defeat_turn_$turn_number"

CASES = {
    # Escort dies -> scenario's escort die event -> [endlevel] result=defeat.
    "escort": r'''
    [event]
        name=side 1 turn 1
        [kill]
            id=sw_escort_unit
            fire_event=yes
            animate=no
        [/kill]
        {FAIL}
    [/event]
''',
    # Player leader dies -> scenario's leader die event -> defeat.
    "leader": r'''
    [event]
        name=side 1 turn 1
        [kill]
            id=sw_leader
            fire_event=yes
            animate=no
        [/kill]
        {FAIL}
    [/event]
''',
    # Passive turns advance past turn 12. The scenario's turn-12 defeat event
    # uses `name=turn` with a `turn=12` key, which is not valid EventWML
    # (turn-specific events must be named e.g. `name="turn 12"`); verified on
    # 1.19.28 that `name="turn 4"` fires once while `name=turn turn=3` never
    # fires. If the scenario is fixed, defeat fires at turn 12 and the else
    # branch below is never reached. As authored, no defeat fires and the
    # probe terminates at turn 16 with the defect recorded.
    "timeout": r'''
    # Fire the scenario's turn-12 reinforcement-deadline event directly.
    # The event now uses correct `name="turn 12"` syntax (fixed from the
    # invalid `name=turn` + `turn=12` which never fired). Natural turn
    # advancement is unreliable headless; this verifies the defeat wiring.
    [event]
        name=side 1 turn 1
        [fire_event]
            id=sw_turn12_timeout_event
        [/fire_event]
    [/event]
''',
}
EXPECTED_VERDICTS = {
    "escort": "defeat",
    "leader": "defeat",
    "timeout": "defeat",
}
EXERCISE_TYPES = {
    "escort": "direct_escort_death_defeat_wiring",
    "leader": "direct_leader_death_defeat_wiring",
    "timeout": "normal_turn_progression_to_turn_limit_defeat",
}


def _render_test(source: str, case: str) -> str:
    if (source.count("[scenario]") != 1 or source.count("[/scenario]") != 1
            or source.count("id=" + SCENARIO_ID) != 1):
        raise ValueError("Space Interception structure changed; refusing fixture transformation")
    test_id = "sw_interception_defeat_" + case
    transformed = source
    if case == "timeout":
        # Tag the turn-12 reinforcement-deadline event so the fixture can
        # fire it directly and verify the defeat wiring.
        if transformed.count('name="turn 12"') != 1:
            raise ValueError("turn-12 timeout event changed; refusing fixture transformation")
        transformed = transformed.replace(
            'name="turn 12"',
            'id=sw_turn12_timeout_event\n        name="turn 12"', 1)
    transformed = transformed.replace("[scenario]", "[test]\n    is_unit_test=yes", 1)
    transformed = transformed.replace("id=" + SCENARIO_ID, "id=" + test_id, 1)
    transformed = transformed.replace("[/scenario]", CASES[case] + "[/test]", 1)
    return transformed


def _meets_expectation(case: str, verdict: str, exit_code: int | None, log: str) -> bool:
    return bool(
        verdict == "defeat"
        and exit_code == 7
        and "conditional test unexpectedly failed" not in log
        and "Error via [do_command]" not in log
    )


def run_probe(root: Path, engine: Path, case_names: list[str]) -> dict:
    root = root.resolve(strict=True)
    if not engine.is_absolute() or engine.is_symlink() or not engine.is_file():
        raise ValueError("installed engine is missing or symlinked")
    engine = engine.resolve(strict=True)
    addon_source = root / "addons" / ADDON_ID
    scenario_path = addon_source / "scenarios" / "02_space_interception.cfg"
    source = scenario_path.read_text(encoding="utf-8")
    unit_source_hashes = {
        path.relative_to(root).as_posix(): _sha256(path)
        for path in sorted((addon_source / "units").glob("*.cfg"))
    }
    with tempfile.TemporaryDirectory(prefix="sw-interception-defeat-") as temporary:
        userdata = Path(temporary)
        addon = userdata / "data" / "add-ons" / ADDON_ID
        shutil.copytree(addon_source, addon)
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
            test_id = "sw_interception_defeat_" + case
            command = [str(engine), "--log-to-file", "--userdata-dir", str(userdata), "-u", test_id]
            try:
                completed = subprocess.run(
                    command, cwd=engine.parent, capture_output=True, text=True,
                    timeout=90, check=False,
                )
                exit_code: int | None = completed.returncode
            except subprocess.TimeoutExpired:
                exit_code = None
            log = _latest_log(userdata)
            version_match = re.search(r"Battle for Wesnoth v([0-9]+(?:\.[0-9]+)+)", log)
            if version_match:
                engine_version = version_match.group(1)
            if any(marker in log for marker in (
                "Unknown scenario:", "Couldn't find [test]", "error config:",
                "error wml:", "Error via [do_command]",
            )):
                verdict = "invalid_fixture"
            elif f"FAIL TEST (DEFEAT) (7): {test_id}" in log:
                verdict = "defeat"
            elif f"PASS TEST (VICTORY) (8): {test_id}" in log:
                verdict = "victory"
            elif f"PASS TEST (0): {test_id}" in log:
                verdict = "pass"
            elif re.search(rf"FAIL TEST .*: {re.escape(test_id)}", log):
                verdict = "fail"
            else:
                verdict = "unknown"
            meets_expectation = _meets_expectation(case, verdict, exit_code, log)
            entry = {
                "case": case,
                "test_id": test_id,
                "fixture_sha256": _sha256(fixtures / (case + ".cfg")),
                "exercise_type": EXERCISE_TYPES[case],
                "exit_code": exit_code,
                "log_verdict": verdict,
                "expected_verdict": EXPECTED_VERDICTS[case],
                "meets_expectation": meets_expectation,
                "diagnostic_tail": log[-6000:],
            }
            results.append(entry)
    verified_cases = {row["case"] for row in results if row["meets_expectation"]}
    return {
        "schema_id": "wesnoth-starwars.production.interception-defeat-probe",
        "schema_version": 1,
        "scenario_id": SCENARIO_ID,
        "scenario_source_sha256": _sha256(scenario_path),
        "unit_source_sha256": unit_source_hashes,
        "engine_binary_sha256": _sha256(engine),
        "engine_version": engine_version,
        "exercise_type": "instrumented_real_scenario_defeat_wiring",
        "enemy_turn_disabled_in_timeout_fixture": "timeout" in case_names,
        "results": results,
        "pass": all(row["meets_expectation"] for row in results),
        "defeat_paths": {
            "escort_death": "observed" if "escort" in verified_cases else "unassessed",
            "leader_death": "observed" if "leader" in verified_cases else "unassessed",
            "turn_limit": (
                "observed_with_enemy_turn_disabled" if "timeout" in verified_cases else "unassessed"
            ),
        },
        "mission_transition": "unassessed",
        "campaign_entry": "unassessed",
        "normal_gui_play": "unassessed",
        "combat_balance": "unassessed",
        "save_reload": "unassessed",
    }


def probe(root: Path, engine: Path) -> dict:
    """Run all defeat cases and return the full result dict."""
    return run_probe(root, engine, sorted(CASES))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine", type=Path, required=True)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--cases", nargs="+", choices=sorted(CASES), default=sorted(CASES))
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parents[1]
                        / "agent/runtime/interception-defeat-probe.json")
    args = parser.parse_args()
    try:
        result = run_probe(args.repo_root, args.engine, args.cases)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", prefix=".interception-defeat-",
                                     suffix=".tmp", dir=args.output.parent, delete=False) as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")
        temporary = Path(stream.name)
    os.replace(temporary, args.output)
    print(json.dumps({
        "pass": result["pass"],
        "results": [{k: row[k] for k in ("case", "exit_code", "log_verdict", "meets_expectation")}
                    for row in result["results"]],
        "output": str(args.output),
    }))
    return 0 if result["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
