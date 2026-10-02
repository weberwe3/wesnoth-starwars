#!/usr/bin/env python3
"""Run the deterministic engine tests for the Force and overwatch systems.

Stages the add-on with a test-only scenario (systems_test/), points Campaign
I at it, runs systems_test_plugin.lua (every check prints SW_TEST: PASS/FAIL),
then reloads the save it made and checks that system state survived.

Usage: python3 production/linux_engine/run_systems_tests.py [--workdir DIR] [--output evidence.json]
Exit code 0 only if every check passed and none errored.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from run_campaign_sequence import ADDON, ADDON_ID, CAMPAIGNS, DEFAULT_ENGINE  # noqa: E402

HERE = Path(__file__).resolve().parent / "systems_test"
ENGINE_ERRORS = re.compile(r"error (?:scripting/lua|wml|config|engine)[^:]*:|stack traceback", re.IGNORECASE)


def run_phase(engine: Path, userdata: Path, phase: str, timeout: int, extra: list[str]) -> str:
    plugin = userdata.parent / f"plugin_{phase}.lua"
    plugin.write_text((HERE / "systems_test_plugin.lua").read_text(encoding="utf-8")
                      .replace('local PHASE = "main"', f'local PHASE = "{phase}"'), encoding="utf-8")
    logs = userdata / "logs"
    before = set(logs.glob("*.log"))
    env = dict(os.environ, SDL_VIDEO_DRIVER="offscreen", SDL_AUDIO_DRIVER="dummy")
    proc = subprocess.Popen([str(engine), "--resolution", "1024x768", "--userdata-dir", str(userdata),
                             "--plugin", str(plugin), *extra], cwd=userdata.parent, env=env,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    start = time.time()

    def text() -> str:
        return "\n".join(p.read_text(encoding="utf-8", errors="replace")
                         for p in sorted(set(logs.glob("*.log")) - before))
    while proc.poll() is None and time.time() - start < timeout:
        if "SW_TEST: done" in text():
            time.sleep(3)
            break
        time.sleep(1)
    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=15)
        except subprocess.TimeoutExpired:
            proc.kill()
    return text()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine", type=Path, default=Path(os.environ.get("WESNOTH_LINUX_ENGINE", DEFAULT_ENGINE)))
    parser.add_argument("--workdir", type=Path)
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    work = args.workdir or Path(tempfile.mkdtemp(prefix="sw-systems-"))
    if work.exists():
        shutil.rmtree(work)
    userdata = work / "userdata"
    (userdata / "logs").mkdir(parents=True)
    staged = userdata / "data/add-ons" / ADDON_ID
    shutil.copytree(ADDON, staged)
    shutil.copy(HERE / "sw_test_systems.cfg", staged / "scenarios/heir_to_the_empire/00_sw_test_systems.cfg")
    shutil.copy(HERE / "sw_test_systems.map", staged / "maps/sw_test_systems.map")
    main_cfg = staged / "_main.cfg"
    first = CAMPAIGNS["Star_Wars_Thrawn_Trilogy"][0]
    main_cfg.write_text(main_cfg.read_text(encoding="utf-8").replace(
        f"first_scenario={first}", "first_scenario=sw_test_systems", 1), encoding="utf-8")
    (userdata / "preferences").write_text("animate_map=no\nidle_anim=no\nturbo=yes\nturbo_speed=20\n", encoding="utf-8")

    log_main = run_phase(args.engine, userdata, "main", args.timeout, [])
    saves = sorted(userdata.rglob("sw_systems_test_save*"))
    log_load = run_phase(args.engine, userdata, "load", args.timeout, ["--load", saves[-1].name]) if saves else ""

    results = []
    for text in (log_main, log_load):
        for line in text.splitlines():
            if line.startswith("SW_TEST: PASS ") or line.startswith("SW_TEST: FAIL "):
                results.append(line[len("SW_TEST: "):])
    errors = sorted({l.strip() for l in (log_main + log_load).splitlines() if ENGINE_ERRORS.search(l)})
    passed = [r for r in results if r.startswith("PASS")]
    failed = [r for r in results if r.startswith("FAIL")]
    for r in results:
        print(r)
    if not saves:
        failed.append("FAIL save/load: no save produced")
    for e in errors[:10]:
        print("ENGINE ERROR:", e[:300])
    print(f"{len(passed)} passed, {len(failed)} failed, {len(errors)} engine errors")
    evidence = {"schema_version": 1, "kind": "sw-systems-tests", "passed": passed, "failed": failed,
                "engine_errors": errors[:50], "pass": not failed and not errors and bool(passed)}
    if args.output:
        args.output.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    return 0 if evidence["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
