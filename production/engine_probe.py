"""Run isolated installed-engine WML test capability fixtures.

These fixtures exercise Wesnoth's test-mode action injection and failure
signaling. They do not execute a project mission or prove legal mission play.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile


ADDON_ID = "sw_engine_capability_probe"
TIMEOUT_SECONDS = 90
FIXTURE = r'''#textdomain wesnoth-test
#ifdef TEST
{GENERIC_UNIT_TEST "sw_capability_move_positive" (
    [event]
        name=side 1 turn 1
        [do_command]
            [move]
                x=7,8
                y=3,3
            [/move]
        [/do_command]
        {ASSERT (
            [have_unit]
                id=alice
                x,y=8,3
            [/have_unit]
        )}
        {SUCCEED}
    [/event]
)}

{GENERIC_UNIT_TEST "sw_capability_move_broken_expectation" (
    [event]
        name=side 1 turn 1
        [do_command]
            [move]
                x=7,8
                y=3,3
            [/move]
        [/do_command]
        {ASSERT (
            [have_unit]
                id=alice
                x,y=9,3
            [/have_unit]
        )}
        {SUCCEED}
    [/event]
)}
#endif
'''


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(65536), b""):
            digest.update(block)
    return digest.hexdigest()


def _run_fixture(engine: Path, userdata: Path, fixture_id: str) -> dict:
    command = [
        str(engine), "--log-to-file", "--userdata-dir", str(userdata),
        "-u", fixture_id,
    ]
    try:
        completed = subprocess.run(
            command, cwd=engine.parent, text=True, capture_output=True,
            timeout=TIMEOUT_SECONDS, check=False,
        )
        logs = sorted(
            (path for path in userdata.rglob("*") if path.is_file() and "log" in path.name.lower()),
            key=lambda path: path.stat().st_mtime_ns,
        )
        diagnostic_tail = ""
        if logs and logs[-1].stat().st_size <= 5_000_000:
            diagnostic_tail = logs[-1].read_text(encoding="utf-8", errors="replace")[-2000:]
        return {
            "fixture_id": fixture_id,
            "exit_code": completed.returncode,
            "timed_out": False,
            "stdout_tail": completed.stdout[-1000:],
            "stderr_tail": completed.stderr[-1000:],
            "diagnostic_tail": diagnostic_tail,
        }
    except subprocess.TimeoutExpired:
        return {
            "fixture_id": fixture_id,
            "exit_code": None,
            "timed_out": True,
            "stdout_tail": "",
            "stderr_tail": "engine test exceeded the bounded timeout",
            "diagnostic_tail": "",
        }


def probe(engine: Path) -> dict:
    engine = engine.resolve(strict=True)
    if not engine.is_file():
        raise ValueError("engine path is not a regular file")
    with tempfile.TemporaryDirectory(prefix="sw-engine-probe-") as directory:
        userdata = Path(directory)
        addon = userdata / "data" / "add-ons" / ADDON_ID
        addon.mkdir(parents=True)
        (addon / "_main.cfg").write_text(FIXTURE, encoding="utf-8")
        positive = _run_fixture(engine, userdata, "sw_capability_move_positive")
        negative = _run_fixture(engine, userdata, "sw_capability_move_broken_expectation")
    positive_log = positive["diagnostic_tail"]
    negative_log = negative["diagnostic_tail"]
    positive_pass = (
        positive["exit_code"] == 0 and not positive["timed_out"]
        and "PASS TEST (0): sw_capability_move_positive" in positive_log
    )
    negative_pass = (
        negative["exit_code"] == 1 and not negative["timed_out"]
        and "conditional test unexpectedly failed" in negative_log
        and re.search(r"FAIL TEST .*: sw_capability_move_broken_expectation", negative_log) is not None
    )
    version_match = re.search(r"Battle for Wesnoth v([0-9]+(?:\.[0-9]+)+)", positive_log)
    return {
        "schema_id": "wesnoth-starwars.production.engine-capability-probe",
        "schema_version": 1,
        "observed_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "engine": {
            "path": str(engine),
            "sha256": _sha256(engine),
            "bytes": engine.stat().st_size,
            "version": version_match.group(1) if version_match else None,
        },
        "fixture_sha256": hashlib.sha256(FIXTURE.encode("utf-8")).hexdigest(),
        "exercise_type": "engine_unit_test_action_injection",
        "results": [positive, negative],
        "capabilities": {
            "custom_test_loaded_and_move_executed": positive_pass,
            "broken_expectation_rejected": negative_pass,
            "mission_legal_play": "unassessed",
            "mission_transition": "unassessed",
            "save_reload": "unassessed",
        },
        "pass": positive_pass and negative_pass,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine", default=os.environ.get("WESNOTH_EXECUTABLE"))
    parser.add_argument(
        "--output",
        default=Path(__file__).resolve().parents[1] / "agent/runtime/engine-capability-probe.json",
    )
    args = parser.parse_args()
    if not args.engine:
        parser.error("--engine or WESNOTH_EXECUTABLE is required")
    try:
        result = probe(Path(args.engine))
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", prefix=".engine-probe-", suffix=".tmp",
        dir=output.parent, delete=False,
    ) as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")
        temporary = Path(stream.name)
    os.replace(temporary, output)
    print(json.dumps({
        "pass": result["pass"],
        "engine_version": result["engine"]["version"],
        "fixture_exits": {item["fixture_id"]: item["exit_code"] for item in result["results"]},
        "output": str(output),
    }))
    return 0 if result["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
