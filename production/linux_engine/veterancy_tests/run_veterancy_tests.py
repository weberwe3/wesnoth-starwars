#!/usr/bin/env python3
"""Stage and run native veteran-training checks, including real save/load.

Only the coordinator executes this script. No production campaign or shared
systems fixture is modified. Requires the installed Wesnoth Linux plugin engine.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from run_campaign_sequence import ADDON, ADDON_ID, CAMPAIGNS, DEFAULT_ENGINE  # noqa: E402

ERRORS = re.compile(r"error (?:scripting/lua|wml|config|engine)[^:]*:|stack traceback", re.IGNORECASE)
MANDATORY = {
    "main": (
        "fresh base stats unchanged",
        "native strict AMLA permits promotion instead of drill",
        "weapons I: native choice recorded",
        "mobility: native choice recorded",
        "weapons II: native choice recorded",
        "mobility cap: native cap rejects advance",
        "weapons cap: native cap rejects advance",
        "default after drill caps: native choice recorded",
        "rank reapplication: trained movement, vision, HP and counts retained",
    ),
    "load": (
        "save/load: exact trained native state",
        "save/load: exact partial native state",
        "save/load weapons cap: native cap rejects advance",
        "save/load mobility cap: native cap rejects advance",
        "remaining drill after load: native choice recorded",
    ),
}


def stage(work: Path) -> Path:
    userdata = work / "userdata"
    (userdata / "logs").mkdir(parents=True)
    staged = userdata / "data" / "add-ons" / ADDON_ID
    shutil.copytree(ADDON, staged)
    shutil.copy2(HERE / "sw_test_veterancy.cfg",
                 staged / "scenarios/heir_to_the_empire/00_sw_test_veterancy.cfg")
    shutil.copy2(HERE / "veterancy_probe.lua", staged / "lua/sw_veterancy_probe.lua")
    main_cfg = staged / "_main.cfg"
    text = main_cfg.read_text(encoding="utf-8")
    first = CAMPAIGNS["Star_Wars_Thrawn_Trilogy"][0]
    needle = f"first_scenario={first}"
    if text.count(needle) != 1:
        raise RuntimeError("expected exactly one Campaign I first_scenario to stage probe")
    main_cfg.write_text(text.replace(needle, "first_scenario=sw_test_veterancy", 1), encoding="utf-8")
    (userdata / "preferences").write_text(
        "animate_map=no\nidle_anim=no\nturbo=yes\nturbo_speed=20\n", encoding="utf-8")
    return userdata


def run_phase(engine: Path, userdata: Path, phase: str, timeout: int, save: Path | None) -> dict:
    work = userdata.parent
    plugin = work / f"sw_veterancy_plugin_{phase}.lua"
    source = (HERE / "veterancy_test_plugin.lua").read_text(encoding="utf-8")
    plugin.write_text(source.replace('local SW_PHASE = "main"', f'local SW_PHASE = "{phase}"'),
                      encoding="utf-8")
    before = set((userdata / "logs").glob("*.log"))
    stderr_path = work / f"sw_veterancy_{phase}.log"
    command = [str(engine), "--resolution", "1024x768", "--userdata-dir", str(userdata),
               "--plugin", str(plugin)]
    if save:
        # Wesnoth 1.19 resolves --load inside userdata/sync/saves, not as an
        # absolute path (docs/WORKTREE_LESSONS.md, 2026-10-02 save/load lesson).
        if save.resolve(strict=True).parent != (userdata / "sync/saves").resolve(strict=True):
            raise RuntimeError("probe save is outside authoritative userdata/sync/saves")
        command += ["--load", save.name]
    environment = dict(os.environ, SDL_VIDEO_DRIVER="offscreen", SDL_AUDIO_DRIVER="dummy")

    def read_logs() -> str:
        paths = sorted(set((userdata / "logs").glob("*.log")) - before)
        paths.append(stderr_path)
        return "\n".join(p.read_text(encoding="utf-8", errors="replace") for p in paths if p.exists())

    timed_out = False
    forced_stop = False
    with stderr_path.open("w", encoding="utf-8") as stream:
        process = subprocess.Popen(command, cwd=work, env=environment,
                                   stdout=stream, stderr=subprocess.STDOUT)
        deadline = time.monotonic() + timeout
        while process.poll() is None:
            if f"SW_VET: done {phase}" in read_logs():
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    forced_stop = True
                break
            if time.monotonic() >= deadline:
                timed_out = True
                break
            time.sleep(1)
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
    log = read_logs()
    checks = list(dict.fromkeys(re.findall(r"SW_VET: (?:PASS|FAIL) [^\r\n]+", log)))
    errors = list(dict.fromkeys(line for line in log.splitlines() if ERRORS.search(line)))
    if timed_out:
        errors.append("engine phase timed out")
    if f"SW_VET: done {phase}" not in log:
        errors.append("engine phase did not finish")
    for label in MANDATORY[phase]:
        if f"SW_VET: PASS {label}" not in checks:
            errors.append(f"missing required passing check: {label}")
    # Only our requested post-completion termination is an expected nonzero
    # exit. A crash racing with termination must remain a failing verdict.
    owned_stop = forced_stop and process.returncode in (-signal.SIGTERM, -signal.SIGKILL)
    unexpected_exit = process.returncode != 0 and not owned_stop
    if unexpected_exit:
        errors.append(f"engine exited with code {process.returncode}")
    result = {"phase": phase, "engine_exit_code": process.returncode,
            "forced_stop_after_completion": forced_stop, "checks": checks, "errors": errors,
            "passed": bool(checks) and not errors and not any("SW_VET: FAIL " in c for c in checks)}
    if unexpected_exit:
        # The temporary staging tree is removed after the run; preserve bounded
        # raw evidence in the JSON report so abnormal exits remain diagnosable.
        result["diagnostic_log_tail"] = log[-32768:]
        result["diagnostic_log_truncated"] = len(log) > 32768
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine", type=Path,
                        default=Path(os.environ.get("WESNOTH_LINUX_ENGINE", DEFAULT_ENGINE)))
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--workdir", type=Path, help="parent for a fresh disposable test directory")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = {"passed": False, "phases": [], "errors": []}
    try:
        engine = args.engine.resolve(strict=True)
        if args.workdir:
            args.workdir.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="sw-veterancy-", dir=args.workdir) as directory:
            userdata = stage(Path(directory))
            report["phases"].append(run_phase(engine, userdata, "main", args.timeout, None))
            saves = sorted(p for p in (userdata / "sync/saves").glob("sw_veterancy_test_save*")
                           if p.is_file())
            if saves:
                report["phases"].append(run_phase(engine, userdata, "load", args.timeout, saves[-1]))
            else:
                report["errors"].append("main phase did not produce the required real saved game")
            report["passed"] = (len(report["phases"]) == 2 and not report["errors"]
                                and all(p["passed"] for p in report["phases"]))
    except Exception as error:
        report["errors"].append(f"{type(error).__name__}: {error}")
    for phase in report["phases"]:
        for check in phase["checks"]:
            print(f"[{phase['phase']}] {check}")
        for error in phase["errors"]:
            print(f"[{phase['phase']}] ERROR: {error}", file=sys.stderr)
    for error in report["errors"]:
        print(f"ERROR: {error}", file=sys.stderr)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print("Native veteran training probes " + ("PASSED" if report["passed"] else "FAILED"))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
