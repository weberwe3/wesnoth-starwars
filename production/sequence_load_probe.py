"""Check initial engine state for missions 2 and 3 in isolated test mode.

Each fixture retains the scenario body and changes only its root to [test],
then asserts one source unit and an initialized variable. The isolated loader
does not include successor scenarios, so its next-scenario warnings cannot
serve as transition evidence. This probe does not play an objective or save.
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
CASES = (
    ("02_space_interception.cfg", "sw_02_space_interception", "sw_escort_unit", "sw_turn_limit", "12"),
    ("03_ground_extraction.cfg", "sw_03_ground_extraction", "sw_hero_commander", "sw_turn_limit", "10"),
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _fixture(source: str, scenario_id: str, unit_id: str, variable: str, expected: str) -> str:
    if (source.count("[scenario]") != 1 or source.count("[/scenario]") != 1
            or source.count("id=" + scenario_id) != 1):
        raise ValueError("scenario structure changed; refusing fixture transformation")
    fixture = source.replace("[scenario]", "[test]\n    is_unit_test=yes", 1)
    fixture = fixture.replace("id=" + scenario_id, "id=sw_load_" + scenario_id, 1)
    return fixture.replace("[/scenario]", f'''
    [event]
        name=side 1 turn 1
        {{ASSERT (
            [have_unit]
                id={unit_id}
            [/have_unit]
        )}}
        {{ASSERT (
            [variable]
                name={variable}
                equals={expected}
            [/variable]
        )}}
        {{SUCCEED}}
    [/event]
[/test]''', 1)


def _latest_log(userdata: Path) -> str:
    logs = sorted((p for p in userdata.rglob("*.log") if p.is_file()),
                  key=lambda p: p.stat().st_mtime_ns)
    if not logs or logs[-1].stat().st_size > 5_000_000:
        return ""
    return logs[-1].read_text(encoding="utf-8", errors="replace")[-12000:]


def probe(root: Path, engine: Path) -> dict:
    root = root.resolve(strict=True)
    if not engine.is_absolute() or engine.is_symlink() or not engine.is_file():
        raise ValueError("installed engine is missing or symlinked")
    engine = engine.resolve(strict=True)
    addon_source = root / "addons" / ADDON_ID
    with tempfile.TemporaryDirectory(prefix="sw-sequence-load-") as temporary:
        userdata = Path(temporary)
        addon = userdata / "data" / "add-ons" / ADDON_ID
        shutil.copytree(addon_source, addon)
        fixtures = addon / "probe-tests"
        fixtures.mkdir()
        prepared = []
        for name, scenario_id, unit_id, variable, expected in CASES:
            source_path = addon_source / "scenarios" / name
            fixture_path = fixtures / name
            fixture_path.write_text(_fixture(source_path.read_text(encoding="utf-8"),
                                             scenario_id, unit_id, variable, expected), encoding="utf-8")
            prepared.append((scenario_id, source_path, fixture_path))
        (addon / "_main.cfg").write_text(
            "#ifdef TEST\n"
            "[binary_path]\n    path=data/add-ons/" + ADDON_ID + "\n[/binary_path]\n"
            "[+units]\n    {~add-ons/" + ADDON_ID + "/units}\n[/units]\n"
            "{~add-ons/" + ADDON_ID + "/utils/mission_events.cfg}\n"
            "{~add-ons/" + ADDON_ID + "/probe-tests}\n"
            "#endif\n", encoding="utf-8")
        results = []
        version = None
        for scenario_id, source_path, fixture_path in prepared:
            test_id = "sw_load_" + scenario_id
            try:
                completed = subprocess.run(
                    [str(engine), "--log-to-file", "--userdata-dir", str(userdata), "-u", test_id],
                    cwd=engine.parent, capture_output=True, text=True, timeout=60, check=False)
                exit_code = completed.returncode
            except subprocess.TimeoutExpired:
                exit_code = None
            log = _latest_log(userdata)
            version_match = re.search(r"Battle for Wesnoth v([0-9]+(?:\.[0-9]+)+)", log)
            if version_match:
                version = version_match.group(1)
            passed = (exit_code == 0 and f"PASS TEST (0): {test_id}" in log
                      and "error wml:" not in log and "Unknown tile in map" not in log
                      and "FAIL TEST" not in log)
            results.append({"scenario_id": scenario_id, "test_id": test_id,
                            "source_sha256": _sha256(source_path),
                            "fixture_sha256": _sha256(fixture_path),
                            "exit_code": exit_code, "pass": passed,
                            "diagnostic_tail": log[-3000:]})
    return {"schema_id": "wesnoth-starwars.production.sequence-load-probe",
            "schema_version": 1, "exercise_type": "isolated_initial_state_engine_test",
            "engine_version": version, "engine_sha256": _sha256(engine),
            "probe_sha256": _sha256(Path(__file__)),
            "next_scenario_warnings_expected_from_isolation": True,
            "transition": "unassessed", "objective_play": "unassessed",
            "save_reload": "unassessed", "results": results,
            "pass": bool(version) and all(row["pass"] for row in results)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine", type=Path, required=True)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parents[1]
                        / "agent/runtime/sequence-load-probe.json")
    args = parser.parse_args()
    try:
        result = probe(args.repo_root, args.engine)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", prefix=".sequence-load-",
                                     suffix=".tmp", dir=args.output.parent, delete=False) as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")
        temporary = Path(stream.name)
    os.replace(temporary, args.output)
    print(json.dumps({"pass": result["pass"], "engine_version": result["engine_version"],
                      "results": [{k: row[k] for k in ("scenario_id", "exit_code", "pass")}
                                  for row in result["results"]], "output": str(args.output)}))
    return 0 if result["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
