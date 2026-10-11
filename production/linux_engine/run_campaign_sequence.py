#!/usr/bin/env python3
"""Run the Campaign I sequence probe on the Linux Wesnoth GUI harness.

Stages the add-on into an isolated userdata directory, launches the Linux
engine (SDL offscreen video, dummy audio) with campaign_sequence_plugin.lua,
and writes a JSON evidence summary.

The probe enters the real campaign through the title screen, so it exercises
GUI campaign entry, every scenario load, scripted win events, linger mode,
transition, hero carryover, and in-game saves. Exit code 0 means every
expected scenario was entered in order and no fatal WML/Lua error was logged.

Usage:
  python3 production/linux_engine/run_campaign_sequence.py [--engine PATH]
      [--workdir DIR] [--output evidence.json] [--timeout SECONDS]
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ADDON_ID = "Star_Wars_Thrawn_Trilogy"
ADDON = ROOT / "addons" / ADDON_ID
PLUGIN = Path(__file__).resolve().parent / "campaign_sequence_plugin.lua"
CAMPAIGN_I = "Star_Wars_Thrawn_Trilogy"
CAMPAIGN_II = "Star_Wars_Thrawn_Trilogy_Dark_Force_Rising"
EXPECTED = [
    "sw_hte_01_ysalamiri_harvest",
    "sw_hte_02_ambush_at_bpfassh",
    "sw_hte_03_adrift",
    "sw_hte_04_shadows_of_kashyyyk",
    "sw_hte_05_prisoner_of_myrkr",
    "sw_hte_06_raid_on_karrdes_base",
    "sw_hte_07_the_forest_crossing",
    "sw_hte_08_nomad_city",
    "sw_hte_09_sluis_van_shipyards",
    "sw_hte_10_thrawns_gambit",
]
EXPECTED_II = [
    "sw_dfr_01_the_noghri_prisoner",
    "sw_dfr_02_honoghr",
    "sw_dfr_03_jomark",
    "sw_dfr_04_the_senators_men",
    "sw_dfr_05_peregrines_nest",
    "sw_dfr_06_the_mad_jedi",
    "sw_dfr_07_the_dark_force",
    "sw_dfr_08_aboard_the_katana",
    "sw_dfr_09_battle_for_the_fleet",
    "sw_dfr_10_honoghrs_choice",
]
CAMPAIGN_III = "Star_Wars_Thrawn_Trilogy_The_Last_Command"
EXPECTED_III = [
    "sw_tlc_01_the_siege_of_coruscant",
    "sw_tlc_02_the_smugglers_council",
    "sw_tlc_03_the_palace_infiltrators",
    "sw_tlc_04_landfall_on_wayland",
    "sw_tlc_05_the_natives_of_wayland",
    "sw_tlc_06_the_gates_of_tantiss",
    "sw_tlc_07_the_cloning_vats",
    "sw_tlc_08_the_throne_room",
    "sw_tlc_09_bilbringi",
    "sw_tlc_10_the_last_command",
]
CAMPAIGNS = {CAMPAIGN_I: EXPECTED, CAMPAIGN_II: EXPECTED_II, CAMPAIGN_III: EXPECTED_III}
# Heroes that must be on the map when each scenario becomes playable.
REQUIRED_HEROES = {
    "sw_hte_01_ysalamiri_harvest": ["sw_hero_pellaeon"],
    "sw_hte_02_ambush_at_bpfassh": ["sw_hero_leia", "sw_hero_han", "sw_hero_chewbacca"],
    "sw_hte_03_adrift": ["sw_hero_luke"],
    "sw_hte_04_shadows_of_kashyyyk": ["sw_hero_leia", "sw_hero_chewbacca"],
    "sw_hte_05_prisoner_of_myrkr": ["sw_hero_luke"],
    "sw_hte_06_raid_on_karrdes_base": ["sw_hero_han", "sw_hero_lando", "sw_hero_karrde"],
    "sw_hte_07_the_forest_crossing": ["sw_hero_luke", "sw_hero_mara"],
    "sw_hte_08_nomad_city": ["sw_hero_lando", "sw_hero_han"],
    "sw_hte_09_sluis_van_shipyards": ["sw_hero_wedge", "sw_hero_luke"],
    "sw_hte_10_thrawns_gambit": ["sw_hero_wedge", "sw_hero_luke"],
    "sw_dfr_01_the_noghri_prisoner": ["sw_hero_leia", "sw_hero_chewbacca"],
    "sw_dfr_02_honoghr": ["sw_hero_leia", "sw_hero_chewbacca", "sw_hero_khabarakh"],
    "sw_dfr_03_jomark": ["sw_hero_luke"],
    "sw_dfr_04_the_senators_men": ["sw_hero_han", "sw_hero_lando"],
    "sw_dfr_05_peregrines_nest": ["sw_hero_han", "sw_hero_lando", "sw_hero_bel_iblis"],
    "sw_dfr_06_the_mad_jedi": ["sw_hero_luke"],
    "sw_dfr_07_the_dark_force": ["sw_hero_wedge", "sw_hero_luke"],
    "sw_dfr_08_aboard_the_katana": ["sw_hero_luke", "sw_hero_han", "sw_hero_lando", "sw_hero_chewbacca"],
    "sw_dfr_09_battle_for_the_fleet": ["sw_hero_wedge", "sw_hero_luke"],
    "sw_dfr_10_honoghrs_choice": ["sw_hero_leia", "sw_hero_chewbacca", "sw_hero_khabarakh"],
    "sw_tlc_01_the_siege_of_coruscant": ["sw_hero_wedge", "sw_hero_luke"],
    "sw_tlc_02_the_smugglers_council": ["sw_hero_karrde", "sw_hero_mara"],
    "sw_tlc_03_the_palace_infiltrators": ["sw_hero_leia", "sw_hero_chewbacca", "sw_hero_khabarakh"],
    "sw_tlc_04_landfall_on_wayland": ["sw_hero_luke", "sw_hero_mara"],
    "sw_tlc_05_the_natives_of_wayland": ["sw_hero_luke", "sw_hero_mara"],
    "sw_tlc_06_the_gates_of_tantiss": ["sw_hero_han", "sw_hero_leia", "sw_hero_lando", "sw_hero_chewbacca",
                                       "sw_hero_khabarakh"],
    "sw_tlc_07_the_cloning_vats": ["sw_hero_han", "sw_hero_lando", "sw_hero_chewbacca"],
    "sw_tlc_08_the_throne_room": ["sw_hero_luke", "sw_hero_mara"],
    "sw_tlc_09_bilbringi": ["sw_hero_wedge", "sw_hero_luke"],
    "sw_tlc_10_the_last_command": ["sw_hero_wedge", "sw_hero_luke"],
}
# Heroes that must NOT be on the map (stashed or out of story).
FORBIDDEN_HEROES = {
    "sw_hte_03_adrift": ["sw_hero_leia", "sw_hero_han", "sw_hero_chewbacca"],
    "sw_hte_05_prisoner_of_myrkr": ["sw_hero_leia", "sw_hero_han", "sw_hero_chewbacca", "sw_hero_mara"],
}
FATAL_LOG = re.compile(
    r"(error (?:wml|config|lua|engine|preprocessor|scripting)|lua error|"
    r"Invalid WML|unknown unit type|could not find|Failed to load|traceback)",
    re.IGNORECASE,
)
NATIVE_FATAL_LOG = re.compile(
    r"(Fatal glibc error|\bassertion\b.*\bfailed\b|\bterminate called\b|"
    r"\bAborted\b|\bsegmentation fault\b|\bdouble free\b|\bcorrupted (?:size|double-linked)\b)",
    re.IGNORECASE,
)
FATAL_DIAGNOSTIC = re.compile(
    r"^\s*(?:(?:\[\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(?:[.,]\d+)?(?:Z|[+-]\d{2}:?\d{2})?\]|"
    r"\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(?:[.,]\d+)?(?:Z|[+-]\d{2}:?\d{2})?|"
    r"\d{8}\s+\d{2}:\d{2}:\d{2}(?:[.,]\d+)?|"
    r"\[?\d{2}:\d{2}:\d{2}(?:[.,]\d+)?\]?)\s+)?fatal(?:\s+error)?\s*:\s*\S",
    re.IGNORECASE,
)
DEFAULT_ENGINE = Path.home() / "opt/bin/wesnoth-linux"
# The runner targets Linux; retain portable importability for Windows static
# checks, where Python does not expose SIGKILL.
_TERMINATE_EXIT = -int(signal.SIGTERM)
_KILL_EXIT = -int(getattr(signal, "SIGKILL", 9))


def sha256_tree(root: Path) -> str:
    h = hashlib.sha256()
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        h.update(path.relative_to(root).as_posix().encode())
        h.update(b"\0")
        h.update(path.read_bytes())
    return h.hexdigest()


def parse(log_text: str) -> dict:
    scenarios: list[dict] = []
    current: dict | None = None
    notes: list[str] = []
    for line in log_text.splitlines():
        if not line.startswith("SW_SEQ: "):
            continue
        body = line[len("SW_SEQ: "):]
        if body.startswith("scenario "):
            parts = body.split()
            current = {"id": parts[1], "heroes_on_map": {}, "saved": False, "won": False, "left": None}
            scenarios.append(current)
        elif current is not None and body.startswith("heroes_on_map "):
            for item in body[len("heroes_on_map "):].split(";"):
                if "=" in item:
                    hid, rest = item.split("=", 1)
                    current["heroes_on_map"][hid] = rest
        elif current is not None and body.startswith("heroes_on_recall "):
            current["heroes_on_recall"] = [x for x in body[len("heroes_on_recall "):].split(";") if x]
        elif current is not None and body.startswith("stashed "):
            current["stashed"] = [x for x in body[len("stashed "):].split(";") if x]
        elif current is not None and body.startswith("side1_gold "):
            current["side1_gold"] = int(body.split()[1])
        elif current is not None and body.startswith("saved "):
            current["saved"] = body == "saved " + current["id"]
        elif current is not None and body.startswith("win script ran "):
            current["won"] = body == "win script ran " + current["id"]
        elif current is not None and body.startswith("left "):
            if body.startswith("left " + current["id"] + " via "):
                current["left"] = body
        elif current is not None and body.startswith("route "):
            current.setdefault("routes", []).append(body[len("route "):])
        else:
            notes.append(body)
    return {"scenarios": scenarios, "notes": notes}


def evaluate(parsed: dict, log_text: str, expected: list[str] | None = None) -> list[str]:
    failures: list[str] = []
    expected = expected or EXPECTED
    ids = [s["id"] for s in parsed["scenarios"]]
    if ids != expected:
        failures.append(f"scenario order {ids} != expected {expected}")
    for s in parsed["scenarios"]:
        for hero in REQUIRED_HEROES.get(s["id"], []):
            if hero not in s["heroes_on_map"]:
                failures.append(f"{s['id']}: required hero {hero} missing")
        for hero in FORBIDDEN_HEROES.get(s["id"], []):
            if hero in s["heroes_on_map"]:
                failures.append(f"{s['id']}: hero {hero} should not be present")
        if not s["saved"]:
            failures.append(f"{s['id']}: in-game save not confirmed")
        if not s["won"]:
            failures.append(f"{s['id']}: win script did not run")
        if not s["left"]:
            failures.append(f"{s['id']}: scenario transition not confirmed")
    for s in parsed["scenarios"]:
        for route in s.get("routes", []):
            match = re.search(r"turns=(\S+) limit=(\S+)", route)
            if "missing_unit" in route or not match or match.group(1) == "nil":
                failures.append(f"{s['id']}: objective unreachable by legal moves: {route}")
                continue
            turns, limit = int(match.group(1)), int(match.group(2))
            # The objective must fit comfortably: at most 80% of the turn
            # limit with no enemies in the way.
            if limit > 0 and turns > limit * 0.8:
                failures.append(f"{s['id']}: objective route needs {turns} of {limit} turns: {route}")
    for note in parsed["notes"]:
        if note.startswith(("fatal", "win_script_error", "route_error")):
            failures.append(note)
    if "done" not in parsed["notes"]:
        failures.append("probe did not finish")
    fatal = sorted({line.strip() for line in log_text.splitlines()
                    if NATIVE_FATAL_LOG.search(line) or FATAL_DIAGNOSTIC.search(line)
                    or (FATAL_LOG.search(line) and "could not open image" not in line)})
    failures.extend(f"log: {line}"[:300] for line in fatal[:20])
    return failures


def _serialized_value_fragment(fragment: str, quoted: bool, continuation: bool) -> tuple[bool, bool] | None:
    """Recognize engine-written quoted/translated string concatenation.

    A trailing + requires another quoted term, possibly translated (_"...").
    Multiline terms retain their quoted state. Ordinary serialized scalar
    properties remain single-line; a bare continuation is never accepted.
    """

    index = 0
    after_term = False
    initial_scalar = not quoted and not continuation
    while True:
        if quoted:
            while index < len(fragment):
                char = fragment[index]
                if char == '"':
                    if index + 1 < len(fragment) and fragment[index + 1] == '"':
                        index += 2  # Native WML serializes embedded quotes twice.
                        continue
                    quoted = False
                    index += 1
                    after_term = True
                    break
                index += 1
            if quoted:
                return True, False
        while index < len(fragment) and fragment[index].isspace():
            index += 1
        if after_term:
            if index == len(fragment):
                return False, False
            if fragment[index] != "+":
                return None
            index += 1
            continuation = True
            after_term = False
            initial_scalar = False
            continue
        if index == len(fragment):
            return False, continuation
        if fragment[index] == "_":
            index += 1
            while index < len(fragment) and fragment[index].isspace():
                index += 1
        if index < len(fragment) and fragment[index] == '"':
            quoted = True
            continuation = False
            initial_scalar = False
            index += 1
            continue
        if initial_scalar and not re.search(r'["+]', fragment):
            return False, False
        return None


def _engine_save_diagnostic(path: Path, campaign: str, scenario: str) -> str | None:
    """Check the observed 1.19 gzip/WML snapshot without certifying a reload.

    Actual saves contain a top-level campaign, one snapshot with the scenario
    id, map data and side children, plus serialized replay state. Gzip reading
    verifies its checksum; bounded UTF-8 and balanced WML reject empty or
    arbitrary compressed data. Installed-engine reload remains a separate test.
    """

    limit = 64 * 1024 * 1024
    try:
        if path.is_symlink() or not path.is_file() or not 0 < path.stat().st_size <= limit:
            return "save is missing, empty, indirect or oversized"
        with gzip.open(path, "rb") as stream:
            payload = stream.read(limit + 1)
        if not payload or len(payload) > limit:
            return "decoded save is empty or oversized"
        text = payload.decode("utf-8")
    except (OSError, EOFError, UnicodeError, zlib.error) as error:
        return f"save is not readable gzip UTF-8 WML ({type(error).__name__})"
    stack: list[str] = []
    quoted = False
    continuation = False
    campaigns: list[str] = []
    snapshot_ids: list[str] = []
    snapshots = 0
    sides = 0
    has_map = False
    for line in text.splitlines():
        fragment = line
        if not quoted and not continuation:
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            tag = re.fullmatch(r"\[(/?)([A-Za-z_][A-Za-z0-9_]*)\]", stripped)
            if tag:
                closing, name = tag.groups()
                if closing:
                    if not stack or stack.pop() != name:
                        return "save WML has unbalanced tags"
                else:
                    if not stack and name == "snapshot":
                        snapshots += 1
                    if stack == ["snapshot"] and name == "side":
                        sides += 1
                    stack.append(name)
                continue
            field = re.match(r"([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$", stripped)
            if field is None:
                return "save WML has an invalid property"
            name, value = field.groups()
            fragment = value
            value = value.strip().strip('"')
            if not stack and name == "campaign":
                campaigns.append(value)
            if stack == ["snapshot"]:
                if name == "id":
                    snapshot_ids.append(value)
                if name == "map_data" and value:
                    has_map = True
        state = _serialized_value_fragment(fragment, quoted, continuation)
        if state is None:
            return "save WML has an invalid string or concatenation"
        quoted, continuation = state
    if quoted or continuation or stack:
        return "save WML has an unfinished string, concatenation or tag"
    if campaigns != [campaign]:
        return "save campaign identity does not match the requested campaign"
    if snapshots != 1 or snapshot_ids != [scenario]:
        return "save snapshot identity does not match the expected scenario"
    if not has_map or sides < 1:
        return "save snapshot is missing map or side state"
    return None


def validate_sequence_saves(userdata: Path, campaign: str, expected: list[str]) -> dict:
    """Bind every scenario to its exact save in the engine's sync directory."""

    directory = userdata / "sync" / "saves"
    checks = []
    for scenario in expected:
        filename = f"sw_seq_{scenario}.gz"
        path = directory / filename
        indirect = (userdata / "sync").is_symlink() or directory.is_symlink()
        problem = "authoritative save directory is indirect" if indirect else _engine_save_diagnostic(path, campaign, scenario)
        checks.append({"scenario": scenario, "filename": filename, "path": str(path),
                       "pass": problem is None, "diagnostic": problem or "readable gzip WML with matching campaign and scenario snapshot"})
    failures = [f"{item['scenario']}: {item['filename']}: {item['diagnostic']}" for item in checks if not item["pass"]]
    return {"directory": str(directory), "checks": checks, "failures": failures,
            "saves": sorted(p.name for p in directory.glob("sw_seq_*.gz") if p.is_file()), "pass": not failures}


def _read_phase_logs(userdata: Path, stdout_path: Path, stderr_path: Path) -> tuple[str, str, str]:
    engine_log = "\n".join(p.read_text(encoding="utf-8", errors="replace")
                           for p in sorted((userdata / "logs").glob("*.log")))
    return (engine_log, stdout_path.read_text(encoding="utf-8", errors="replace"),
            stderr_path.read_text(encoding="utf-8", errors="replace"))


def process_failures(phase: dict) -> list[str]:
    """Certify only healthy exit or the exact runner-owned post-done signal."""

    failures = []
    if phase["timed_out"]:
        failures.append(f"engine timed out after {phase['timeout_seconds']}s")
    if not phase["done"]:
        failures.append("engine phase missing exact SW_SEQ: done marker")
    code = phase["exit_code"]
    owned = phase["done_before_stop"] and not phase["timed_out"] and (
        (phase["terminate_requested"] and not phase["kill_requested"] and code == _TERMINATE_EXIT)
        or (phase["terminate_requested"] and phase["kill_requested"] and code == _KILL_EXIT)
    )
    if code != 0 and not owned:
        failures.append(f"engine exited unexpectedly with code {code}")
    if phase["terminate_requested"] and not phase["done_before_stop"] and not phase["timed_out"]:
        failures.append("engine stop was not authorized by completion")
    return failures


def _run_engine_phase(command: list[str], workdir: Path, userdata: Path, environment: dict,
                      timeout: float, *, completion_grace: float = 3.0,
                      poll_interval: float = 0.25, stop_timeout: float = 20.0) -> dict:
    """Capture the owned child and every output stream through final shutdown."""

    stdout_path, stderr_path = workdir / "engine.stdout.log", workdir / "engine.stderr.log"
    timed_out = False
    done = False
    done_before_stop = False
    terminate_requested = False
    kill_requested = False
    deadline = time.monotonic() + timeout
    with stdout_path.open("w", encoding="utf-8") as stdout, stderr_path.open("w", encoding="utf-8") as stderr:
        process = subprocess.Popen(command, cwd=workdir, env=environment, stdout=stdout, stderr=stderr)
        while process.poll() is None:
            streams = _read_phase_logs(userdata, stdout_path, stderr_path)
            done = any("SW_SEQ: done" == line.strip() for stream in streams for line in stream.splitlines())
            if done:
                # Observe spontaneous failures after completion before sending
                # any signal. A done marker never converts an abort to success.
                try:
                    process.wait(timeout=completion_grace)
                except subprocess.TimeoutExpired:
                    pass
                break
            if time.monotonic() >= deadline:
                timed_out = True
                break
            time.sleep(poll_interval)
        if process.poll() is None:
            done_before_stop = done
            terminate_requested = True
            process.terminate()
            try:
                process.wait(timeout=stop_timeout)
            except subprocess.TimeoutExpired:
                kill_requested = True
                process.kill()
                process.wait()
        exit_code = process.wait()
    engine_log, stdout_text, stderr_text = _read_phase_logs(userdata, stdout_path, stderr_path)
    done = any("SW_SEQ: done" == line.strip() for stream in (engine_log, stdout_text, stderr_text)
               for line in stream.splitlines())
    # std_print normally appears in engine logs. Select one marker stream so
    # duplicate stdout capture cannot create duplicate campaign visits.
    plugin_log = next((stream for stream in (engine_log, stdout_text, stderr_text)
                       if any(line.startswith("SW_SEQ: ") for line in stream.splitlines())), "")
    return {
        "pid": process.pid, "exit_code": exit_code, "timed_out": timed_out,
        "timeout_seconds": timeout, "done": done, "done_before_stop": done_before_stop,
        "terminate_requested": terminate_requested, "kill_requested": kill_requested,
        "stdout_path": str(stdout_path), "stderr_path": str(stderr_path),
        "stdout_tail": stdout_text[-4000:], "stderr_tail": stderr_text[-4000:],
        "log_text": plugin_log, "all_output": "\n".join((engine_log, stdout_text, stderr_text)),
    }


def run_sequence(addon: Path, engine: Path, workdir: Path, timeout: int = 2400,
                 campaign: str = CAMPAIGN_I) -> dict:
    """Stage ``addon`` in isolated userdata, run the plugin, return evidence."""

    expected = CAMPAIGNS[campaign]
    workdir.mkdir(parents=True, exist_ok=True)
    plugin = workdir / "campaign_sequence_plugin.lua"
    plugin.write_text(
        PLUGIN.read_text(encoding="utf-8")
        .replace('local CAMPAIGN = "Star_Wars_Thrawn_Trilogy"', f'local CAMPAIGN = "{campaign}"')
        .replace('local FINAL_SCENARIO = "sw_hte_10_thrawns_gambit"', f'local FINAL_SCENARIO = "{expected[-1]}"'),
        encoding="utf-8",
    )
    userdata = workdir / "userdata"
    if userdata.exists():
        shutil.rmtree(userdata)
    (userdata / "logs").mkdir(parents=True)
    (userdata / "data/add-ons").mkdir(parents=True)
    shutil.copytree(addon, userdata / "data/add-ons" / ADDON_ID)
    started = time.time()
    environment = dict(os.environ)
    environment.setdefault("SDL_VIDEO_DRIVER", "offscreen")
    environment.setdefault("SDL_AUDIO_DRIVER", "dummy")
    phase = _run_engine_phase(
        [str(engine), "--resolution", "1024x768", "--userdata-dir", str(userdata), "--plugin", str(plugin)],
        workdir, userdata, environment, timeout,
    )
    parsed = parse(phase["log_text"])
    save_evidence = validate_sequence_saves(userdata, campaign, expected)
    failures = evaluate(parsed, phase["all_output"], expected) + process_failures(phase) + save_evidence["failures"]
    return {
        "schema_version": 1,
        "kind": "linux-gui-campaign-sequence",
        "campaign": campaign,
        "engine": str(engine),
        "addon_sha256": sha256_tree(addon),
        "plugin_sha256": hashlib.sha256(PLUGIN.read_bytes()).hexdigest(),
        "exit_code": phase["exit_code"],
        "process": {key: value for key, value in phase.items() if key not in {"log_text", "all_output"}},
        "seconds": round(time.time() - started, 1),
        "scenarios": parsed["scenarios"],
        "saves": save_evidence["saves"],
        "save_validation": save_evidence,
        "failures": failures,
        "pass": not failures,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine", type=Path, default=Path(os.environ.get("WESNOTH_LINUX_ENGINE", DEFAULT_ENGINE)))
    parser.add_argument("--addon", type=Path, default=ADDON)
    parser.add_argument("--workdir", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--timeout", type=int, default=2400)
    parser.add_argument("--campaign", choices=sorted(CAMPAIGNS), default=CAMPAIGN_I)
    args = parser.parse_args()
    if not args.engine.is_file():
        print(f"Linux engine not found: {args.engine}", file=sys.stderr)
        return 2
    workdir = args.workdir or Path(tempfile.mkdtemp(prefix="sw-seq-"))
    evidence = run_sequence(args.addon, args.engine, workdir, args.timeout, args.campaign)
    text = json.dumps(evidence, indent=2)
    if args.output:
        args.output.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0 if evidence["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
