#!/usr/bin/env python3
"""Run the deterministic engine tests for the tactical systems.

Suites (default: all):
  force   Force and overwatch: stages sw_test_systems, points Campaign I at
          it, runs systems_test_plugin.lua, then reloads the save it made.
  intel   Sensors/EW and Thrawn Doctrine: same, with sw_test_intel and
          intel_test_plugin.lua (fog, decoys, doctrine, AI turn, save/load).
  replay  Engine replay: runs the [test] sw_test_intel_replay with -u (an AI
          battle using every intelligence mechanic); the engine then replays
          the recorded game and the test compares digests of all
          intelligence state recorded at checkpoints.
Every check prints SW_TEST: PASS/FAIL.

Usage: python3 production/linux_engine/run_systems_tests.py [--suite all|force|intel|replay]
       [--workdir DIR] [--output evidence.json]
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


def run_phase(engine: Path, userdata: Path, plugin_name: str, phase: str, timeout: int, extra: list[str]) -> str:
    plugin = userdata.parent / f"plugin_{phase}.lua"
    plugin.write_text((HERE / plugin_name).read_text(encoding="utf-8")
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


SUITES = {
    "force": ("sw_test_systems", "systems_test_plugin.lua", "sw_systems_test_save"),
    "intel": ("sw_test_intel", "intel_test_plugin.lua", "sw_intel_test_save"),
}
REPLAY_TEST = "sw_test_intel_replay"
REPLAY_STRICT_IGNORE = re.compile(r"change_controller_wml")


def stage(work: Path, scenario: str | None, replay: bool) -> Path:
    if work.exists():
        shutil.rmtree(work)
    userdata = work / "userdata"
    (userdata / "logs").mkdir(parents=True)
    staged = userdata / "data/add-ons" / ADDON_ID
    shutil.copytree(ADDON, staged)
    main_cfg = staged / "_main.cfg"
    text = main_cfg.read_text(encoding="utf-8")
    if scenario:
        shutil.copy(HERE / f"{scenario}.cfg", staged / f"scenarios/heir_to_the_empire/00_{scenario}.cfg")
        shutil.copy(HERE / f"{scenario}.map", staged / f"maps/{scenario}.map")
        first = CAMPAIGNS["Star_Wars_Thrawn_Trilogy"][0]
        text = text.replace(f"first_scenario={first}", f"first_scenario={scenario}", 1)
    if replay:
        (staged / "tests").mkdir(exist_ok=True)
        shutil.copy(HERE / f"{REPLAY_TEST}.cfg", staged / f"tests/{REPLAY_TEST}.cfg")
        text += (
            "\n#ifdef TEST\n"
            f"{{~add-ons/{ADDON_ID}/utils/hte_terrain.cfg}}\n"
            f"[+units]\n    {{~add-ons/{ADDON_ID}/units}}\n[/units]\n"
            f"{{~add-ons/{ADDON_ID}/utils/mission_events.cfg}}\n"
            f"{{~add-ons/{ADDON_ID}/utils/hte_macros.cfg}}\n"
            f"{{~add-ons/{ADDON_ID}/tests/{REPLAY_TEST}.cfg}}\n"
            "#endif\n")
    main_cfg.write_text(text, encoding="utf-8")
    (userdata / "preferences").write_text("animate_map=no\nidle_anim=no\nturbo=yes\nturbo_speed=20\n", encoding="utf-8")
    return userdata


def run_plugin_suite(engine: Path, work: Path, suite: str, timeout: int) -> tuple[list[str], list[str]]:
    scenario, plugin, save_name = SUITES[suite]
    userdata = stage(work, scenario, False)
    log_main = run_phase(engine, userdata, plugin, "main", timeout, [])
    saves = sorted(userdata.rglob(f"{save_name}*"))
    log_load = run_phase(engine, userdata, plugin, "load", timeout, ["--load", saves[-1].name]) if saves else ""
    results = []
    for text in (log_main, log_load):
        for line in text.splitlines():
            if line.startswith("SW_TEST: PASS ") or line.startswith("SW_TEST: FAIL "):
                results.append(f"[{suite}] " + line[len("SW_TEST: "):])
    if not saves:
        results.append(f"[{suite}] FAIL save/load: no save produced")
    errors = sorted({l.strip() for l in (log_main + log_load).splitlines() if ENGINE_ERRORS.search(l)})
    return results, errors


def run_replay_suite(engine: Path, work: Path, timeout: int) -> tuple[list[str], list[str]]:
    userdata = stage(work, None, True)
    env = dict(os.environ, SDL_VIDEO_DRIVER="offscreen", SDL_AUDIO_DRIVER="dummy")
    try:
        proc = subprocess.run([str(engine), "--userdata-dir", str(userdata), "--log-strict=error",
                               "-u", REPLAY_TEST], cwd=work, env=env, capture_output=True, text=True,
                              timeout=timeout)
        out, code = proc.stdout + proc.stderr, proc.returncode
    except subprocess.TimeoutExpired as exc:
        out = (exc.stdout or b"").decode(errors="replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        code = -1
    logs = "\n".join(p.read_text(encoding="utf-8", errors="replace") for p in (userdata / "logs").glob("*.log"))
    text = out + "\n" + logs
    lines = sorted({l for l in text.splitlines() if l.startswith("SW_TEST: ")})
    results = [f"[replay] " + l[len("SW_TEST: "):] for l in lines if l.startswith(("SW_TEST: PASS", "SW_TEST: FAIL"))]
    original = [l for l in lines if "(original)" in l and "PASS" in l]
    replayed = [l for l in lines if "(replay)" in l and "PASS" in l]
    verdict = re.search(r"(PASS TEST|FAIL TEST|BROKE STRICT)[^\n]*", text)
    ok = code == 0 and verdict is not None and verdict.group(0).startswith("PASS TEST")
    results.append(f"[replay] {'PASS' if ok else 'FAIL'} engine unit test and replay: exit {code}, "
                   f"{verdict.group(0) if verdict else 'no verdict'}")
    results.append(f"[replay] {'PASS' if len(original) >= 4 else 'FAIL'} digest checkpoints recorded in play: {len(original)}")
    results.append(f"[replay] {'PASS' if len(replayed) >= 4 and len(replayed) == len(original) else 'FAIL'} "
                   f"digest checkpoints reproduced by the replay: {len(replayed)}")
    errors = sorted({l.strip() for l in text.splitlines()
                     if ENGINE_ERRORS.search(l) and not REPLAY_STRICT_IGNORE.search(l)})
    return results, errors


LUA_DIR = ADDON / "lua"


def run_static_checks() -> list[str]:
    """Source checks for determinism and the textdomain pitfall."""
    results = []
    modules = sorted(LUA_DIR.glob("sw_*.lua"))
    shadow = [f"{m.name}:{i}" for m in modules for i, line in enumerate(m.read_text().splitlines(), 1)
              if re.search(r"\bfor\s+_\s*[,=]|,\s*_\s+in\b", line)]
    results.append(f"[static] {'FAIL' if shadow else 'PASS'} no loop variable shadows the textdomain function _"
                   + (f" -- {shadow[:5]}" if shadow else ""))
    unsynced = [f"{m.name}:{i}" for m in modules for i, line in enumerate(m.read_text().splitlines(), 1)
                if re.search(r"\bmath\.random\b|\bos\.(time|clock|date)\b|\bio\.", line)]
    results.append(f"[static] {'FAIL' if unsynced else 'PASS'} no unsynced randomness, clock or file access in game logic"
                   + (f" -- {unsynced[:5]}" if unsynced else ""))
    viewing = [f"{m.name}:{i}" for m in modules for i, line in enumerate(m.read_text().splitlines(), 1)
               if "get_viewing_side" in line and m.name != "sw_core.lua"]
    results.append(f"[static] {'FAIL' if viewing else 'PASS'} the local viewing side is read only by the display helper"
                   + (f" -- {viewing[:5]}" if viewing else ""))
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine", type=Path, default=Path(os.environ.get("WESNOTH_LINUX_ENGINE", DEFAULT_ENGINE)))
    parser.add_argument("--suite", choices=("all", "force", "intel", "replay"), default="all")
    parser.add_argument("--workdir", type=Path)
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    base = args.workdir or Path(tempfile.mkdtemp(prefix="sw-systems-"))
    suites = ["force", "intel", "replay"] if args.suite == "all" else [args.suite]
    results: list[str] = run_static_checks()
    errors: list[str] = []
    for suite in suites:
        if suite == "replay":
            r, e = run_replay_suite(args.engine, base / suite, args.timeout)
        else:
            r, e = run_plugin_suite(args.engine, base / suite, suite, args.timeout)
        results += r
        errors += [f"[{suite}] {x}" for x in e]
    passed = [r for r in results if r.split("] ", 1)[-1].startswith("PASS")]
    failed = [r for r in results if r.split("] ", 1)[-1].startswith("FAIL")]
    for r in results:
        print(r)
    for e in errors[:10]:
        print("ENGINE ERROR:", e[:300])
    print(f"{len(passed)} passed, {len(failed)} failed, {len(errors)} engine errors")
    evidence = {"schema_version": 2, "kind": "sw-systems-tests", "suites": suites, "passed": passed,
                "failed": failed, "engine_errors": errors[:50],
                "pass": not failed and not errors and bool(passed)}
    if args.output:
        args.output.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    return 0 if evidence["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
