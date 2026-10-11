#!/usr/bin/env python3
"""Run the deterministic engine tests for the tactical systems.

Suites (default: all):
  force   Force and overwatch: stages sw_test_systems, points Campaign I at
          it, runs systems_test_plugin.lua, then reloads the save it made.
  intel   Sensors/EW and Thrawn Doctrine: same, with sw_test_intel and
          intel_test_plugin.lua (fog, decoys, doctrine, AI turn, save/load).
  air     Off-map air support and rank insignia: sw_test_air and
          air_test_plugin.lua (sorties, accuracy, AI use and avoidance, ranks).
  replay  Engine replay: runs the [test] sw_test_intel_replay with -u (an AI
          battle using every intelligence mechanic); the engine then replays
          the recorded game and the test compares digests of all
          intelligence state recorded at checkpoints.
Every check prints SW_TEST: PASS/FAIL. Plugin suites require separate complete
main/reload process evidence and a real save. Air idles after completion until
owned termination; this does not test the engine's interactive quit lifecycle.

Usage: python3 production/linux_engine/run_systems_tests.py [--suite all|force|intel|air|replay]
       [--workdir DIR] [--output evidence.json]
Exit code 0 only if every check passed and none errored.
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

sys.path.insert(0, str(Path(__file__).resolve().parent))
from run_campaign_sequence import ADDON, ADDON_ID, CAMPAIGNS, DEFAULT_ENGINE  # noqa: E402

HERE = Path(__file__).resolve().parent / "systems_test"
ENGINE_ERRORS = re.compile(
    r"\berror(?:\s+[\w/.-]+)?\s*:|stack traceback|\bfatal\b|"
    r"\bassertion\b.*\bfailed\b|\bsegmentation fault\b|\bcore dumped\b|\bterminate called\b",
    re.IGNORECASE)
LOG_TAIL_LIMIT = 16384
# Artificial controller hand-offs in these isolated fixtures emit this exact
# installed-engine diagnostic. Preserve it as a warning; a controller-related
# error, actual OOS, appended fatal or different diagnostic remains an error.
SYNTHETIC_CONTROLLER_DIAGNOSTIC = (
    "error replay: Trying to ask the server for a 'change_controller_wml' choice in a unsynced "
    "context, doing the choice locally. This can cause OOS.")
SYNTHETIC_CONTROLLER_WARNING = re.compile(
    r"(?:[0-9]{8} [0-9]{2}:[0-9]{2}:[0-9]{2} )?" + re.escape(SYNTHETIC_CONTROLLER_DIAGNOSTIC))
REQUIRED_CHECKS = {
    "systems_test_plugin.lua": {
        "main": ("FP initialised to max on placement", "Force Choke damages its target",
                 "Force Choke spent C'baoth's FP"),
        "load": ("save/load: Force Points kept", "save/load: overwatch kept",
                 "save/load: overwatch index kept", "save/load: null field rebuilt",
                 "save/load: systems reloaded"),
    },
    "intel_test_plugin.lua": {
        "main": ("Star Destroyer profile from its unit type", "AI doctrine state stays valid"),
        "load": ("save/load: intelligence state identical after reload",
                 "save/load: recomputing the picture changes nothing", "save/load: sensor contact kept",
                 "save/load: contact marker kept", "save/load: cloaked unit still hidden",
                 "save/load: decoy kept", "save/load: doctrine Insight and patterns kept",
                 "save/load: EW ready after reload"),
    },
    "air_test_plugin.lua": {
        "main": ("a fresh trooper wears no insignia", "trooper promoted to sergeant",
                 "AMLA stats unchanged from the default: +3 max HP each, full heal",
                 "test scenarios earn nothing", "victory banks the reward",
                 "recruiting: paid in full", "Hide attack range clears it"),
        "load": ("save/load: state identical after reload", "save/load: sorties kept",
                 "save/load: inbound bombing kept", "save/load: inbound marker kept",
                 "save/load: rank insignia kept"),
    },
}


def phase_checks(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines()
            if line.strip().startswith(("SW_TEST: PASS ", "SW_TEST: FAIL "))]


def has_done(text: str) -> bool:
    return any(line.strip() == "SW_TEST: done" for line in text.splitlines())


def classify_diagnostics(text: str) -> tuple[list[str], list[str]]:
    """Return errors and explicitly retained exact synthetic-fixture warnings."""
    errors, warnings = [], []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if SYNTHETIC_CONTROLLER_WARNING.fullmatch(line):
            warnings.append(line)
        elif ENGINE_ERRORS.search(line):
            errors.append(line)
    return list(dict.fromkeys(errors)), list(dict.fromkeys(warnings))


def run_phase(engine: Path, userdata: Path, plugin_name: str, phase: str, timeout: int, extra: list[str]) -> dict:
    """Capture actual process evidence; completion never excuses a native crash.

    The air fixture idles after completion. Other existing fixtures may finish
    normally. Only a termination we requested after observing done can count as
    an expected signal exit. Interactive engine quit behavior is not tested.
    """
    required = REQUIRED_CHECKS[plugin_name][phase]
    plugin = userdata.parent / f"plugin_{phase}.lua"
    plugin.write_text((HERE / plugin_name).read_text(encoding="utf-8")
                      .replace('local PHASE = "main"', f'local PHASE = "{phase}"'), encoding="utf-8")
    logs = userdata / "logs"
    before = set(logs.glob("*.log"))
    env = dict(os.environ, SDL_VIDEO_DRIVER="offscreen", SDL_AUDIO_DRIVER="dummy")
    stdout_path = userdata.parent / f"stdout_{phase}.log"
    stderr_path = userdata.parent / f"stderr_{phase}.log"

    def native_logs() -> str:
        return "\n".join(p.read_text(encoding="utf-8", errors="replace")
                         for p in sorted(set(logs.glob("*.log")) - before))

    def streams() -> tuple[str, str]:
        return (stdout_path.read_text(encoding="utf-8", errors="replace"),
                stderr_path.read_text(encoding="utf-8", errors="replace"))

    completed = False
    timed_out = False
    termination_requested = False
    termination_after_completion = False
    kill_requested = False
    with stdout_path.open("w", encoding="utf-8") as stdout, stderr_path.open("w", encoding="utf-8") as stderr:
        proc = subprocess.Popen([str(engine), "--resolution", "1024x768", "--userdata-dir", str(userdata),
                                 "--plugin", str(plugin), *extra], cwd=userdata.parent, env=env,
                                stdout=stdout, stderr=stderr)
        deadline = time.monotonic() + timeout
        while True:
            code = proc.poll()
            out, err = streams()
            completed = has_done(native_logs() + "\n" + out + "\n" + err)
            if code is not None or completed:
                break
            if time.monotonic() >= deadline:
                timed_out = True
                break
            time.sleep(1)
        if proc.poll() is None:
            termination_requested = True
            termination_after_completion = completed
            proc.terminate()
            try:
                proc.wait(timeout=15)
            except subprocess.TimeoutExpired:
                kill_requested = True
                proc.kill()
                proc.wait()
        else:
            proc.wait()
    out, err = streams()
    log = native_logs()
    text = log + "\n" + out + "\n" + err
    # Preserve repeated checks within their authoritative log while avoiding a
    # duplicate copy when the engine mirrors those same lines to stdout.
    checks = phase_checks(log)
    checks += [check for check in phase_checks(out + "\n" + err) if check not in checks]
    errors, warnings = classify_diagnostics(text)
    completed = completed and has_done(text)
    owned_stop = (termination_requested and termination_after_completion and
                  (proc.returncode == -signal.SIGTERM or
                   (kill_requested and proc.returncode == -signal.SIGKILL)))
    if timed_out:
        errors.append("phase timed out before completion")
    if not completed:
        errors.append("phase completion marker missing")
    if not checks:
        errors.append("phase produced no meaningful checks")
    for check in required:
        if "SW_TEST: PASS " + check not in checks:
            errors.append("required passing check missing: " + check)
    prepared = any(line.strip().startswith("SW_TEST: state prepared for save") for line in text.splitlines())
    saved = any(line.strip() == "SW_TEST: saved" for line in text.splitlines())
    if phase == "main" and not (prepared and saved):
        errors.append("main phase did not complete save preparation and saving")
    if proc.returncode != 0 and not owned_stop:
        errors.append(f"unexpected engine exit: {proc.returncode}")
    failed = [check for check in checks if check.startswith("SW_TEST: FAIL ")]
    result = {"phase": phase, "engine_exit_code": proc.returncode, "completed": completed,
              "timed_out": timed_out, "termination_requested": termination_requested,
              "termination_after_completion": termination_after_completion,
              "kill_requested": kill_requested, "owned_stop_after_completion": owned_stop,
              "prepared_save": prepared, "saved": saved, "checks": checks,
              "failed_checks": failed, "errors": errors, "warnings": warnings,
              "pass": not errors and not failed}
    if not result["pass"]:
        result["diagnostics"] = {name: {"tail": value[-LOG_TAIL_LIMIT:],
                                        "truncated": len(value) > LOG_TAIL_LIMIT}
                                 for name, value in (("native_log", log), ("stdout", out), ("stderr", err))}
    return result


SUITES = {
    "force": ("sw_test_systems", "systems_test_plugin.lua", "sw_systems_test_save"),
    "intel": ("sw_test_intel", "intel_test_plugin.lua", "sw_intel_test_save"),
    "air": ("sw_test_air", "air_test_plugin.lua", "sw_air_test_save"),
}
REPLAY_TESTS = ("sw_test_intel_replay", "sw_test_air_replay")


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
        for test in REPLAY_TESTS:
            shutil.copy(HERE / f"{test}.cfg", staged / f"tests/{test}.cfg")
        text += (
            "\n#ifdef TEST\n"
            f"{{~add-ons/{ADDON_ID}/utils/hte_terrain.cfg}}\n"
            f"[+units]\n    {{~add-ons/{ADDON_ID}/units}}\n[/units]\n"
            f"{{~add-ons/{ADDON_ID}/utils/mission_events.cfg}}\n"
            f"{{~add-ons/{ADDON_ID}/utils/hte_macros.cfg}}\n"
            + "".join(f"{{~add-ons/{ADDON_ID}/tests/{test}.cfg}}\n" for test in REPLAY_TESTS) +
            "#endif\n")
    main_cfg.write_text(text, encoding="utf-8")
    (userdata / "preferences").write_text("animate_map=no\nidle_anim=no\nturbo=yes\nturbo_speed=20\n", encoding="utf-8")
    return userdata


def run_plugin_suite(engine: Path, work: Path, suite: str, timeout: int,
                     phase_evidence: list[dict] | None = None) -> tuple[list[str], list[str]]:
    scenario, plugin, save_name = SUITES[suite]
    userdata = stage(work, scenario, False)
    phases = [run_phase(engine, userdata, plugin, "main", timeout, [])]
    # The engine resolves --load names within userdata/sync/saves. Never pass
    # an absolute path or pick a similarly named file from another directory.
    save_dir = userdata / "sync/saves"
    saves = sorted(p for p in save_dir.glob(f"{save_name}*")
                   if p.is_file() and p.resolve().parent == save_dir.resolve())
    phases[0]["authoritative_save"] = saves[-1].name if saves else None
    if not saves:
        phases[0]["errors"].append("required authoritative save missing")
        phases[0]["pass"] = False
    if saves:
        phases.append(run_phase(engine, userdata, plugin, "load", timeout, ["--load", saves[-1].name]))
    results = []
    errors = []
    for phase_result in phases:
        phase_result["suite"] = suite
        results += [f"[{suite}] " + line[len("SW_TEST: "):] for line in phase_result["checks"]]
        results.append(f"[{suite}] {'PASS' if phase_result['pass'] else 'FAIL'} "
                       f"{phase_result['phase']} phase evidence: exit {phase_result['engine_exit_code']}")
        errors += [f"{phase_result['phase']}: {error}" for error in phase_result["errors"]]
    if phase_evidence is not None:
        phase_evidence.extend(phases)
    if not saves:
        results.append(f"[{suite}] FAIL save/load: no save produced")
        errors.append("required reload phase missing: no authoritative save produced")
    if len(phases) != 2:
        errors.append("both main and reload phases are required")
    return results, errors


def run_replay_suite(engine: Path, work: Path, timeout: int,
                     warning_evidence: list[str] | None = None) -> tuple[list[str], list[str]]:
    results: list[str] = []
    errors: list[str] = []
    for test in REPLAY_TESTS:
        r, e = run_replay_test(engine, work / test, test, timeout, warning_evidence)
        results += r
        errors += e
    return results, errors


def run_replay_test(engine: Path, work: Path, test: str, timeout: int,
                    warning_evidence: list[str] | None = None) -> tuple[list[str], list[str]]:
    userdata = stage(work, None, True)
    env = dict(os.environ, SDL_VIDEO_DRIVER="offscreen", SDL_AUDIO_DRIVER="dummy")
    try:
        proc = subprocess.run([str(engine), "--userdata-dir", str(userdata), "--log-strict=error",
                               "-u", test], cwd=work, env=env, capture_output=True, text=True,
                              timeout=timeout)
        out, code = proc.stdout + proc.stderr, proc.returncode
    except subprocess.TimeoutExpired as exc:
        out = (exc.stdout or b"").decode(errors="replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        code = -1
    logs = "\n".join(p.read_text(encoding="utf-8", errors="replace") for p in (userdata / "logs").glob("*.log"))
    text = out + "\n" + logs
    lines = sorted({l for l in text.splitlines() if l.startswith("SW_TEST: ")})
    tag = f"[replay:{test}]"
    results = [f"{tag} " + l[len("SW_TEST: "):] for l in lines if l.startswith(("SW_TEST: PASS", "SW_TEST: FAIL"))]
    infos = [l[len("SW_TEST: INFO "):] for l in lines if l.startswith("SW_TEST: INFO ")]
    # Count every checkpoint line on the engine's output (two checkpoints
    # may legitimately produce the same digest).
    out_lines = [l for l in out.splitlines() if l.startswith("SW_TEST: ")]
    original = [l for l in out_lines if "(original)" in l and "PASS" in l]
    replayed = [l for l in out_lines if "(replay)" in l and "PASS" in l]
    verdict = re.search(r"(PASS TEST|FAIL TEST|BROKE STRICT)[^\n]*", text)
    ok = code == 0 and verdict is not None and verdict.group(0).startswith("PASS TEST")
    results.append(f"{tag} {'PASS' if ok else 'FAIL'} engine unit test and replay: exit {code}, "
                   f"{verdict.group(0) if verdict else 'no verdict'}" + (f" ({'; '.join(infos)})" if infos else ""))
    results.append(f"{tag} {'PASS' if len(original) >= 4 else 'FAIL'} digest checkpoints recorded in play: {len(original)}")
    results.append(f"{tag} {'PASS' if len(replayed) >= 4 and len(replayed) == len(original) else 'FAIL'} "
                   f"digest checkpoints reproduced by the replay: {len(replayed)}")
    errors, warnings = classify_diagnostics(text)
    if warning_evidence is not None:
        warning_evidence.extend(f"{tag} {warning}" for warning in warnings)
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
    parser.add_argument("--suite", choices=("all", "force", "intel", "air", "replay"), default="all")
    parser.add_argument("--workdir", type=Path)
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    base = args.workdir or Path(tempfile.mkdtemp(prefix="sw-systems-"))
    suites = ["force", "intel", "air", "replay"] if args.suite == "all" else [args.suite]
    results: list[str] = run_static_checks()
    errors: list[str] = []
    phase_evidence: list[dict] = []
    warning_evidence: list[str] = []
    for suite in suites:
        if suite == "replay":
            r, e = run_replay_suite(args.engine, base / suite, args.timeout, warning_evidence)
        else:
            r, e = run_plugin_suite(args.engine, base / suite, suite, args.timeout, phase_evidence)
        results += r
        errors += [f"[{suite}] {x}" for x in e]
    warning_evidence += [f"[{phase['suite']}] {phase['phase']}: {warning}"
                         for phase in phase_evidence for warning in phase["warnings"]]
    passed = [r for r in results if r.split("] ", 1)[-1].startswith("PASS")]
    failed = [r for r in results if r.split("] ", 1)[-1].startswith("FAIL")]
    for r in results:
        print(r)
    for e in errors[:10]:
        print("ENGINE ERROR:", e[:300])
    for warning in warning_evidence[:10]:
        print("ENGINE WARNING:", warning[:300])
    print(f"{len(passed)} passed, {len(failed)} failed, {len(errors)} engine errors")
    evidence = {"schema_version": 3, "kind": "sw-systems-tests", "suites": suites, "passed": passed,
                "failed": failed, "engine_errors": errors[:50],
                "phase_evidence": phase_evidence,
                "engine_warnings": warning_evidence,
                "pass": not failed and not errors and bool(passed)}
    if args.output:
        args.output.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    return 0 if evidence["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
