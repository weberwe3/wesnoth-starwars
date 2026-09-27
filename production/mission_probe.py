"""Exercise one real mission through isolated Wesnoth test-mode fixtures.

The source scenario is copied without changing its events or units. Only its
root tag becomes a test tag and each fixture adds an observation/action event.
Results are capability evidence, not a legal-victory claim unless the fixture
actually reaches the original objective through legal game actions.
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
}
EXPECTED_VERDICTS = {
    "load": "pass",
    "movement_point": "pass",
    "first_move": "pass",
    "first_move_origin": "fail",
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
    return paths[-1].read_text(encoding="utf-8", errors="replace")[-3000:]


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
                if f"PASS TEST (0): {test_id}" in log:
                    verdict = "pass"
                elif re.search(rf"FAIL TEST .*: {re.escape(test_id)}", log):
                    verdict = "fail"
                else:
                    verdict = "unknown"
                expected = EXPECTED_VERDICTS[case]
                meets_expectation = (
                    verdict == expected
                    and completed.returncode == (0 if expected == "pass" else 1)
                    and (expected != "fail" or "conditional test unexpectedly failed" in log)
                )
                results.append({
                    "case": case,
                    "test_id": test_id,
                    "exit_code": completed.returncode,
                    "log_verdict": verdict,
                    "expected_verdict": expected,
                    "meets_expectation": meets_expectation,
                    "diagnostic_tail": log[-1200:],
                })
            except subprocess.TimeoutExpired:
                results.append({"case": case, "test_id": test_id, "exit_code": None,
                                "log_verdict": "timeout", "expected_verdict": EXPECTED_VERDICTS[case],
                                "meets_expectation": False, "diagnostic_tail": ""})
    return {
        "schema_id": "wesnoth-starwars.production.mission-probe",
        "schema_version": 1,
        "scenario_id": ORIGINAL_ID,
        "scenario_source_sha256": _sha256(scenario_path),
        "unit_source_sha256": unit_source_hashes,
        "engine_binary_sha256": _sha256(engine),
        "engine_version": engine_version,
        "exercise_type": "instrumented_real_scenario_test_mode",
        "temporary_movetype_fix": temporary_movetype_fix,
        "temporary_movetype_replacements": changed_movetypes,
        "results": results,
        "pass": all(row["meets_expectation"] for row in results),
        "legal_objective_victory": "unassessed",
        "save_reload": "unassessed",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine", required=True)
    parser.add_argument("--repo-root", default=Path(__file__).resolve().parents[1])
    parser.add_argument("--cases", nargs="+", choices=sorted(CASES), default=["load", "movement_point", "first_move", "first_move_origin"])
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
