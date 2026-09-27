"""Exercise Relay Raid's defeat conditions in isolated engine test mode.

Two deterministic defeat cases -- leader death and the turn-limit (time over)
-- against the unmodified source scenario. Each fixture only changes the root
tag ([scenario] -> [test]), renames the test id, and appends a bounded event;
the timeout case tags the source `time over` event with an id and fires it
directly via [fire_event] from side 1 turn 1, since natural turn advancement
is unreliable headless. Only the source defeat wiring may end the level.
This does not establish campaign entry, normal GUI play, transition, or
save/load.
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


SCENARIO_ID = "sw_05_relay_raid"
LEADER_ID = "sw_relay_raid_leader"

CASES = {
    "leader": r"""
    [event]
        name=side 1 turn 1
        # The source die handler (filter id=sw_relay_raid_leader) must end
        # the level in defeat. {FAIL} only runs if it does not.
        [kill]
            id=sw_relay_raid_leader
            fire_event=yes
        [/kill]
        {FAIL}
    [/event]
""",
    "timeout": r"""
    # Fire the scenario's time-over event directly. Natural turn advancement
    # is unreliable headless; this verifies the defeat wiring.
    [event]
        name=side 1 turn 1
        [fire_event]
            id=sw_relay_raid_time_over_event
        [/fire_event]
    [/event]
""",
}

TEST_IDS = {case: "sw_relay_raid_defeat_" + case for case in CASES}

EXPECTED_VERDICTS = {case: "defeat" for case in CASES}

EXERCISE_TYPES = {
    "leader": "direct_death_event_injection",
    "timeout": "direct_time_over_event_injection",
}


def _render_test(source: str, case: str) -> str:
    if (source.count("[scenario]") != 1 or source.count("[/scenario]") != 1
            or source.count("id=" + SCENARIO_ID) != 1):
        raise ValueError("Relay Raid structure changed; refusing fixture transformation")
    fixture = source.replace("[scenario]", "[test]\n    is_unit_test=yes", 1)
    fixture = fixture.replace("id=" + SCENARIO_ID, "id=" + TEST_IDS[case], 1)
    if case == "timeout":
        # Tag the time-over defeat event so the fixture can fire it directly
        # and verify the defeat wiring.
        if fixture.count("name=time over") != 1:
            raise ValueError("time-over defeat event changed; refusing fixture transformation")
        fixture = fixture.replace(
            "name=time over",
            "id=sw_relay_raid_time_over_event\n        name=time over", 1)
    return fixture.replace("[/scenario]", CASES[case] + "[/test]", 1)


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
    source_path = addon_source / "scenarios" / "05_relay_raid.cfg"
    source = source_path.read_text(encoding="utf-8")
    with tempfile.TemporaryDirectory(prefix="sw-relay-raid-defeat-") as temporary:
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
            test_id = TEST_IDS[case]
            try:
                completed = subprocess.run(
                    [str(engine), "--log-to-file", "--userdata-dir", str(userdata), "-u", test_id],
                    cwd=engine.parent, capture_output=True, text=True, timeout=90, check=False)
                exit_code = completed.returncode
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
            expected = EXPECTED_VERDICTS[case]
            results.append({
                "case": case,
                "test_id": test_id,
                "fixture_sha256": _sha256(fixtures / (case + ".cfg")),
                "exercise_type": EXERCISE_TYPES[case],
                "exit_code": exit_code,
                "log_verdict": verdict,
                "expected_verdict": expected,
                "meets_expectation": _meets_expectation(case, verdict, exit_code, log),
                "diagnostic_tail": log[-6000:],
            })
    verified = {row["case"] for row in results if row["meets_expectation"]}
    return {
        "schema_id": "wesnoth-starwars.production.relay-raid-defeat-probe",
        "schema_version": 1,
        "exercise_type": "instrumented_real_scenario_test_mode_defeat_cases",
        "scenario_id": SCENARIO_ID,
        "test_ids": TEST_IDS,
        "source_sha256": _sha256(source_path),
        "engine_sha256": _sha256(engine),
        "engine_version": engine_version,
        "probe_sha256": _sha256(Path(__file__)),
        "results": results,
        "pass": all(row["meets_expectation"] for row in results),
        "defeat_paths": {
            "leader_death": "direct_death_defeat_observed" if "leader" in verified else "unassessed",
            "time_over": "direct_time_over_defeat_observed" if "timeout" in verified else "unassessed",
        },
        "mission_transition": "unassessed",
        "save_reload": "unassessed",
        "normal_gui_play": "unassessed",
    }


def probe(root: Path, engine: Path) -> dict:
    return run_probe(root, engine, list(CASES))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine", type=Path, required=True)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--cases", nargs="+", choices=sorted(CASES), default=sorted(CASES))
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parents[1]
                        / "agent/runtime/relay-raid-defeat-probe.json")
    args = parser.parse_args()
    try:
        result = run_probe(args.repo_root, args.engine, args.cases)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", prefix=".relay-raid-defeat-",
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
