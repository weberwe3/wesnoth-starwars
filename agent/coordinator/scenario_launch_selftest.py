#!/usr/bin/env python3

"""Deterministic installed-Wesnoth campaign smoke with isolated staged userdata."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock

from gameplay_contracts import validate_declared_contracts, validate_historical_retention, validate_map_data


ADDON_ID = "Star_Wars_Thrawn_Trilogy"
SCENARIO_ID = "01_First_Battle"
CAMPAIGN_DEFINE = "CAMPAIGN_STAR_WARS_THRAWN_TRILOGY"
ENGINE_TIMEOUT_SECONDS = 120
CAMPAIGN_STARTUP_PROBE_SECONDS = 12
SCENARIO_RUNTIME_PROBE_SECONDS = 6
MAX_DIAGNOSTIC_CHARS = 6000


def find_wesnoth_executable() -> Path | None:
    configured = os.environ.get("WESNOTH_EXECUTABLE")
    candidates = [
        configured,
        shutil.which("wesnoth"),
        shutil.which("wesnoth.exe"),
        r"C:\\Program Files (x86)\\battle for wesnoth\\wesnoth.exe",
        r"C:\\Program Files\\Battle for Wesnoth\\wesnoth.exe",
        "/mnt/c/Program Files (x86)/battle for wesnoth/wesnoth.exe",
        "/mnt/c/Program Files/Battle for Wesnoth/wesnoth.exe",
    ]
    for value in candidates:
        if not value:
            continue
        path = Path(value)
        if path.is_absolute() and path.is_file() and not path.is_symlink():
            return path
    return None


def windows_path(path: Path) -> str:
    if os.name == "nt":
        return str(path)
    completed = subprocess.run(
        ["wslpath", "-w", str(path)],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        timeout=10,
        check=False,
    )
    if completed.returncode != 0 or not completed.stdout.strip():
        raise RuntimeError("Could not translate an engine-validation path")
    return completed.stdout.strip()


def build_command(
    executable: Path,
    userdata: Path,
    source: Path,
    output: Path,
    *,
    path_converter=windows_path,
) -> list[str]:
    convert = path_converter if executable.suffix.casefold() == ".exe" else str
    return [
        convert(executable),
        "--userdata-dir", convert(userdata),
        "--preprocess", convert(source), convert(output),
        "--preprocess-defines", CAMPAIGN_DEFINE,
    ]


def _bounded_diagnostic(*values: object) -> str:
    lines: list[str] = []
    for value in values:
        if not isinstance(value, str):
            continue
        for line in value.splitlines():
            cleaned = line.strip()
            if cleaned and cleaned not in lines:
                lines.append(cleaned)
    return "\n".join(lines)[-MAX_DIAGNOSTIC_CHARS:]


def diagnostic_paths(diagnostic: str) -> list[str]:
    """Return only project-owned add-on paths named by Wesnoth diagnostics."""

    prefix = f"addons/{ADDON_ID}/"
    found: list[str] = []
    pattern = re.compile(
        rf"~add-ons/{re.escape(ADDON_ID)}/([^:\r\n]+)(?::\d+)?",
        re.IGNORECASE,
    )
    for match in pattern.finditer(diagnostic):
        relative = match.group(1).replace("\\", "/").strip(" /")
        candidate = prefix + relative
        if ".." not in Path(relative).parts and candidate not in found:
            found.append(candidate)
    return found[:20]


def _powershell_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def run_engine(command: list[str], *, cwd: Path, timeout: int) -> subprocess.CompletedProcess:
    """Wait correctly for a Windows GUI-subsystem executable launched from WSL."""

    if os.name == "nt" or not command[0].casefold().endswith(".exe"):
        return subprocess.run(
            command, cwd=cwd, text=True, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, timeout=timeout, check=False,
        )
    argument_line = subprocess.list2cmdline(command[1:])
    script = (
        "$ErrorActionPreference='Stop';"
        "$process=Start-Process -FilePath " + _powershell_literal(command[0])
        + " -ArgumentList " + _powershell_literal(argument_line)
        + " -Wait -PassThru -WindowStyle Hidden;"
        "exit $process.ExitCode"
    )
    encoded = base64.b64encode(script.encode("utf-16le")).decode("ascii")
    return subprocess.run(
        ["powershell.exe", "-NoLogo", "-NoProfile", "-NonInteractive", "-EncodedCommand", encoded],
        cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        timeout=timeout, check=False,
    )


def run_campaign_startup_probe(
    executable: Path, userdata: Path, *, cwd: Path,
    campaign_id: str = ADDON_ID,
    timeout: int = CAMPAIGN_STARTUP_PROBE_SECONDS,
) -> dict:
    """Launch the staged campaign briefly, then close only that child process.

    A campaign that reaches its initial map remains alive at the probe deadline. A
    configuration or WML failure exits early and is reported in the staged log.
    """

    if executable.suffix.casefold() != ".exe":
        return {"started": False, "survived_probe": False, "exit_code": None, "diagnostic": "Campaign startup probe requires the installed Windows engine."}
    arguments = subprocess.list2cmdline([
        "--userdata-dir", windows_path(userdata), "--campaign", campaign_id,
    ])
    script = (
        "$ErrorActionPreference='Stop';"
        "$process=Start-Process -FilePath " + _powershell_literal(windows_path(executable))
        + " -ArgumentList " + _powershell_literal(arguments) + " -PassThru -WindowStyle Hidden;"
        + f"Start-Sleep -Seconds {timeout};"
        + "$alive=-not $process.HasExited;"
        + "if($alive){Stop-Process -Id $process.Id -Force;$process.WaitForExit()};"
        + "[Console]::Out.WriteLine((@{started=$true;survived_probe=$alive;exit_code=$process.ExitCode}|ConvertTo-Json -Compress))"
    )
    encoded = base64.b64encode(script.encode("utf-16le")).decode("ascii")
    completed = subprocess.run(
        ["powershell.exe", "-NoLogo", "-NoProfile", "-NonInteractive", "-EncodedCommand", encoded],
        cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        timeout=timeout + 20, check=False,
    )
    payload = next(
        (line for line in completed.stdout.splitlines() if line.lstrip().startswith("{")),
        "",
    )
    try:
        output = json.loads(payload)
    except json.JSONDecodeError:
        return {
            "started": False, "survived_probe": False, "exit_code": completed.returncode,
            "diagnostic": _bounded_diagnostic(completed.stdout),
        }
    return {
        "started": output.get("started") is True,
        "survived_probe": output.get("survived_probe") is True,
        "exit_code": output.get("exit_code") if isinstance(output.get("exit_code"), int) else None,
        "diagnostic": "",
    }


def campaign_error_lines(text: str) -> list[str]:
    """Return bounded fatal diagnostics emitted while loading the add-on.

    Wesnoth can keep its GUI process alive while showing a modal map/parser
    error.  Process survival is therefore not evidence of a successful launch;
    these messages must fail the probe as well.
    """

    return [
        line.strip() for line in text.splitlines()
        if re.search(
            r"\berror\s+(?:wml|config|engine(?:/[a-z0-9_/-]+)?):|"
            r"\bgame_error:|\bunknown unit type:|"
            r"the game map could not be loaded|"
            r"terrain with a string with more than 4 characters|"
            r"unexpected characters after variable name|"
            r"could not be loaded:\s*",
            line, re.IGNORECASE,
        )
    ][-40:]


def campaign_log_text(userdata: Path) -> str:
    """Read both Wesnoth diagnostic streams, including GUI-launch output."""

    paths = sorted(
        (userdata / "logs").glob("wesnoth-*.log"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    paths += sorted(
        (userdata / "logs").glob("wesnoth-*.out.log"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    chunks: list[str] = []
    seen: set[Path] = set()
    for path in paths[:6]:
        if path in seen:
            continue
        seen.add(path)
        try:
            chunks.append(path.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
    return "\n".join(chunks)


def scenario_sources(root: Path) -> dict[str, Path]:
    """Return declared scenario IDs and their source paths without loading WML."""

    sources: dict[str, Path] = {}
    for path in sorted((root / "addons" / ADDON_ID / "scenarios").rglob("*.cfg")):
        text = path.read_text(encoding="utf-8")
        for block in re.finditer(r"\[scenario\](.*?)\[/scenario\]", text, re.DOTALL):
            match = re.search(r"(?m)^\s*id\s*=\s*([A-Za-z0-9_]+)\s*$", block.group(1))
            if match:
                scenario_id = match.group(1)
                if scenario_id in sources:
                    raise ValueError(f"Duplicate scenario id: {scenario_id}")
                sources[scenario_id] = path
    return sources


def scenario_structure_evidence(root: Path, selected: set[str]) -> dict:
    """Reject an empty or instant-ending source scenario before engine launch."""

    checks: list[dict] = []
    diagnostics: list[str] = []
    for scenario_id, path in scenario_sources(root).items():
        if scenario_id not in selected:
            continue
        text = path.read_text(encoding="utf-8")
        block = next(iter(re.findall(r"\[scenario\](.*?)\[/scenario\]", text, re.DOTALL)), "")
        sides = re.findall(r"\[side\](.*?)\[/side\]", block, re.DOTALL)
        playable_sides = [
            side for side in sides
            if re.search(r"(?m)^\s*(?:type|id)\s*=", side)
            and re.search(r"(?m)^\s*x\s*=", side)
            and re.search(r"(?m)^\s*y\s*=", side)
        ]
        opening_events = re.findall(
            r"\[event\](.*?)\[/event\]", block, re.DOTALL
        )
        immediate_end = any(
            re.search(r"(?m)^\s*name\s*=\s*(?:prestart|start)\s*$", event)
            and "[endlevel]" in event for event in opening_events
        )
        passed = len(playable_sides) >= 2 and not immediate_end
        item = {
            "scenario_id": scenario_id,
            "path": path.relative_to(root).as_posix(),
            "pass": passed,
            "playable_side_count": len(playable_sides),
            "immediate_endlevel": immediate_end,
        }
        checks.append(item)
        if not passed:
            diagnostics.append(
                f"{scenario_id} has {len(playable_sides)} playable sides"
                + (" and ends during setup" if immediate_end else "")
            )
    return {
        "pass": bool(checks) and all(item["pass"] for item in checks),
        "scenarios": checks,
        "diagnostic": _bounded_diagnostic("\n".join(diagnostics)),
        "diagnostic_paths": [item["path"] for item in checks if not item["pass"]][:20],
    }


def selected_scenarios(root: Path, required_gameplay_paths: list[str] | None) -> set[str]:
    """Run all scenarios for a one-time sweep, otherwise only affected scenarios."""

    sources = scenario_sources(root)
    if not required_gameplay_paths:
        return set(sources)
    changed = set(required_gameplay_paths)
    selected = {
        scenario_id for scenario_id, path in sources.items()
        if path.relative_to(root).as_posix() in changed
    }
    # A changed unit definition can be used by multiple scenarios; test every
    # registered scenario rather than guess at text-level references.
    if any(path.endswith((".cfg", ".lua")) and "/units/" in path for path in changed):
        return set(sources)
    return selected or {SCENARIO_ID}


def prepare_runtime_probe_addon(staged_main: Path, scenario_relative: Path, scenario_id: str) -> str:
    """Append one temporary campaign that launches exactly one real scenario.

    This touches only isolated staged userdata. The player-facing add-on and
    normal campaign routing are never modified by the test harness.
    """

    token = hashlib.sha256(scenario_id.encode("utf-8")).hexdigest()[:12]
    campaign_id = f"sw_runtime_probe_{token}"
    relative = scenario_relative.as_posix()
    staged_main.write_text(
        staged_main.read_text(encoding="utf-8")
        + "\n# Isolated deterministic runtime probe; never committed to the add-on.\n"
        + "{~add-ons/Star_Wars_Thrawn_Trilogy/utils/mission_events.cfg}\n"
        + "{~add-ons/Star_Wars_Thrawn_Trilogy/" + relative + "}\n"
        + "[campaign]\n"
        + f"    id={campaign_id}\n"
        + f"    define=SW_RUNTIME_PROBE_{token}\n"
        + f"    first_scenario={scenario_id}\n"
        + "[/campaign]\n",
        encoding="utf-8",
    )
    return campaign_id


def runtime_scenario_probes(root: Path, executable: Path, selected: set[str]) -> dict:
    """Launch each selected scenario through the installed engine's campaign path."""

    results: list[dict] = []
    for scenario_id, source in scenario_sources(root).items():
        if scenario_id not in selected:
            continue
        temporary = Path(tempfile.mkdtemp(prefix=".wesnoth-runtime-", dir=root.parent))
        try:
            userdata = temporary / "userdata"
            staged = userdata / "data" / "add-ons" / ADDON_ID
            staged.parent.mkdir(parents=True)
            shutil.copytree(root / "addons" / ADDON_ID, staged)
            campaign_id = prepare_runtime_probe_addon(
                staged / "_main.cfg",
                source.relative_to(root / "addons" / ADDON_ID),
                scenario_id,
            )
            probe = run_campaign_startup_probe(
                executable, userdata, cwd=root, campaign_id=campaign_id,
                timeout=SCENARIO_RUNTIME_PROBE_SECONDS,
            )
            log_text = campaign_log_text(userdata)
            failures = campaign_error_lines(log_text)
            results.append({
                "scenario_id": scenario_id,
                "path": source.relative_to(root).as_posix(),
                "pass": probe["survived_probe"] and not failures,
                "started": probe["started"],
                "survived_probe": probe["survived_probe"],
                "diagnostic": _bounded_diagnostic(probe.get("diagnostic"), "\n".join(failures)),
            })
        except (OSError, subprocess.SubprocessError, ValueError) as exc:
            results.append({
                "scenario_id": scenario_id,
                "path": source.relative_to(root).as_posix(),
                "pass": False,
                "started": False,
                "survived_probe": False,
                "diagnostic": f"Runtime probe infrastructure failed: {exc.__class__.__name__}",
            })
        finally:
            shutil.rmtree(temporary, ignore_errors=True)
    failed = [item for item in results if not item["pass"]]
    return {
        "pass": bool(results) and not failed,
        "scenarios": results,
        "diagnostic": _bounded_diagnostic(*(item["diagnostic"] for item in failed)),
        "diagnostic_paths": [item["path"] for item in failed][:20],
    }


def validate_post_publish_game(
    root: Path, *, required_gameplay_paths: list[str] | None = None
) -> dict:
    """Fail closed unless engine startup and declared gameplay contracts pass."""

    evidence = validate_engine_002(root)
    evidence["command_kind"] = "wesnoth-wml-preprocess-and-campaign-startup"
    evidence["checks"]["campaign_startup_survived_probe"] = False
    evidence["checks"]["campaign_temporary_artifacts_cleaned"] = False
    evidence["checks"]["scenario_structure_contracts"] = False
    evidence["checks"]["scenario_runtime_probes"] = False
    if not evidence["pass"]:
        return evidence
    executable = find_wesnoth_executable()
    if executable is None:
        evidence["pass"] = False
        evidence["failure_class"] = "engine_infrastructure"
        return evidence
    temporary = Path(tempfile.mkdtemp(prefix=".wesnoth-campaign-", dir=root.parent))
    try:
        userdata = temporary / "userdata"
        staged = userdata / "data" / "add-ons" / ADDON_ID
        staged.parent.mkdir(parents=True)
        shutil.copytree(root / "addons" / ADDON_ID, staged)
        probe = run_campaign_startup_probe(executable, userdata, cwd=root)
        log_text = campaign_log_text(userdata)
        failures = campaign_error_lines(log_text)
        diagnostic = _bounded_diagnostic(probe.get("diagnostic"), "\n".join(failures))
        evidence["campaign_probe"] = {
            "started": probe["started"],
            "survived_probe": probe["survived_probe"],
            "exit_code": probe["exit_code"],
        }
        evidence["checks"]["campaign_startup_survived_probe"] = probe["survived_probe"] and not failures
        evidence["diagnostic"] = diagnostic
        evidence["diagnostic_paths"] = diagnostic_paths(diagnostic)
        if not evidence["checks"]["campaign_startup_survived_probe"]:
            evidence["failure_class"] = "addon_validation" if failures else "engine_infrastructure"
    except (OSError, subprocess.SubprocessError):
        evidence["failure_class"] = "engine_infrastructure"
    finally:
        shutil.rmtree(temporary, ignore_errors=True)
        evidence["checks"]["campaign_temporary_artifacts_cleaned"] = not temporary.exists()
    evidence["pass"] = all(
        value for key, value in evidence["checks"].items()
        if key not in {"scenario_structure_contracts", "scenario_runtime_probes"}
    )
    if not evidence["pass"]:
        return evidence
    selected = selected_scenarios(root, required_gameplay_paths)
    structure = scenario_structure_evidence(root, selected)
    evidence["scenario_structure"] = structure
    evidence["checks"]["scenario_structure_contracts"] = structure["pass"]
    if not structure["pass"]:
        evidence["failure_class"] = "gameplay_contract"
        evidence["diagnostic"] = _bounded_diagnostic(
            evidence.get("diagnostic", ""), structure["diagnostic"]
        )
        evidence["diagnostic_paths"] = structure["diagnostic_paths"]
        evidence["pass"] = False
        return evidence
    runtime = runtime_scenario_probes(root, executable, selected)
    evidence["scenario_runtime"] = runtime
    evidence["checks"]["scenario_runtime_probes"] = runtime["pass"]
    if not runtime["pass"]:
        evidence["failure_class"] = "addon_validation"
        evidence["diagnostic"] = _bounded_diagnostic(
            evidence.get("diagnostic", ""), runtime["diagnostic"]
        )
        evidence["diagnostic_paths"] = runtime["diagnostic_paths"]
        evidence["pass"] = False
        return evidence
    contract_evidence = validate_declared_contracts(root, required_gameplay_paths)
    evidence["gameplay_contracts"] = contract_evidence
    evidence["checks"]["declared_gameplay_contracts"] = contract_evidence.get("pass") is True
    if not evidence["checks"]["declared_gameplay_contracts"]:
        evidence["failure_class"] = "gameplay_contract"
        evidence["diagnostic"] = _bounded_diagnostic(
            evidence.get("diagnostic", ""), contract_evidence.get("diagnostic", "")
        )
        evidence["diagnostic_paths"] = sorted(set(
            evidence.get("diagnostic_paths", []) + contract_evidence.get("diagnostic_paths", [])
        ))[:20]
    evidence["pass"] = all(evidence["checks"].values())
    return evidence


def validate_engine_002(
    root: Path,
    *,
    executable: Path | None = None,
    runner=subprocess.run,
    path_converter=windows_path,
) -> dict:
    addon = root / "addons" / ADDON_ID
    source_main = addon / "_main.cfg"
    source_scenario = addon / "scenarios" / "01_first_battle.cfg"
    checks = {
        "engine_found": False,
        "source_main_present": source_main.is_file(),
        "source_scenario_present": source_scenario.is_file(),
        "scenario_registered": False,
        "scenario_id_matches": False,
        "staged_main_present": False,
        "staged_scenario_present": False,
        "engine_exit_zero": False,
        "preprocessed_output_present": False,
        "temporary_artifacts_cleaned": False,
    }
    evidence = {
        "schema_version": 1,
        "addon_id": ADDON_ID,
        "scenario_id": SCENARIO_ID,
        "command_kind": "wesnoth-wml-preprocess",
        "checks": checks,
        "exit_code": None,
        "output_file_count": 0,
        "output_bytes": 0,
        "output_sha256": None,
        "diagnostic": "",
        "diagnostic_paths": [],
        "failure_class": None,
    }
    selected = executable or find_wesnoth_executable()
    checks["engine_found"] = bool(
        selected and selected.is_absolute() and selected.is_file() and not selected.is_symlink()
    )
    if not all((checks["engine_found"], checks["source_main_present"], checks["source_scenario_present"])):
        evidence["pass"] = False
        return evidence

    main_text = source_main.read_text(encoding="utf-8")
    checks["scenario_registered"] = bool(
        re.search(r"\bfirst_scenario\s*=\s*" + re.escape(SCENARIO_ID) + r"\b", main_text)
        and CAMPAIGN_DEFINE in main_text
    )
    scenario_text = source_scenario.read_text(encoding="utf-8")
    checks["scenario_id_matches"] = bool(
        re.search(r"\bid\s*=\s*" + re.escape(SCENARIO_ID) + r"\b", scenario_text)
    )
    temporary = Path(tempfile.mkdtemp(prefix=".wesnoth-scenario-", dir=root.parent))
    try:
        userdata = temporary / "userdata"
        staged = userdata / "data" / "add-ons" / ADDON_ID
        staged.parent.mkdir(parents=True)
        shutil.copytree(addon, staged)
        staged_main = staged / "_main.cfg"
        staged_scenario = staged / "scenarios" / "01_first_battle.cfg"
        output_dir = temporary / "preprocessed"
        output_dir.mkdir()
        checks["staged_main_present"] = staged_main.is_file()
        checks["staged_scenario_present"] = staged_scenario.is_file()
        command = build_command(
            selected, userdata, staged_main, output_dir, path_converter=path_converter
        )
        try:
            completed = (
                run_engine(command, cwd=root, timeout=ENGINE_TIMEOUT_SECONDS)
                if runner is subprocess.run
                else runner(
                    command, cwd=root, text=True, stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT, timeout=ENGINE_TIMEOUT_SECONDS,
                    check=False,
                )
            )
            evidence["exit_code"] = completed.returncode
            checks["engine_exit_zero"] = completed.returncode == 0
            output_files = sorted(path for path in output_dir.rglob("*") if path.is_file())
            digest = hashlib.sha256()
            output_bytes = 0
            for path in output_files:
                data = path.read_bytes()
                output_bytes += len(data)
                digest.update(path.relative_to(output_dir).as_posix().encode("utf-8"))
                digest.update(b"\0")
                digest.update(data)
            evidence["output_file_count"] = len(output_files)
            evidence["output_bytes"] = output_bytes
            evidence["output_sha256"] = digest.hexdigest() if output_files else None
            checks["preprocessed_output_present"] = bool(output_files and output_bytes)
            log_text = ""
            logs = sorted(
                (userdata / "logs").glob("wesnoth-*.log"),
                key=lambda path: path.stat().st_mtime,
                reverse=True,
            )
            if logs:
                log_text = logs[0].read_text(encoding="utf-8", errors="replace")
            diagnostic = _bounded_diagnostic(completed.stdout, log_text)
            evidence["diagnostic"] = diagnostic
            evidence["diagnostic_paths"] = diagnostic_paths(diagnostic)
            if completed.returncode != 0:
                evidence["failure_class"] = (
                    "addon_validation"
                    if evidence["diagnostic_paths"]
                    or re.search(
                        r"(?:parse error|unexpected characters|unterminated|wml error|"
                        r"included from ~add-ons)",
                        diagnostic,
                        re.I,
                    )
                    else "engine_infrastructure"
                )
        except (OSError, subprocess.SubprocessError):
            evidence["exit_code"] = 125
            evidence["failure_class"] = "engine_infrastructure"
    finally:
        shutil.rmtree(temporary, ignore_errors=True)
        checks["temporary_artifacts_cleaned"] = not temporary.exists()
    evidence["pass"] = all(checks.values())
    return evidence


class ScenarioLaunchSelfTests(unittest.TestCase):
    def fixture(self, directory: str) -> tuple[Path, Path]:
        root = Path(directory) / "project"
        scenario = root / "addons" / ADDON_ID / "scenarios" / "01_first_battle.cfg"
        scenario.parent.mkdir(parents=True)
        (scenario.parents[1] / "_main.cfg").write_text(
            "[campaign]\n"
            f"define={CAMPAIGN_DEFINE}\n"
            f"first_scenario={SCENARIO_ID}\n"
            "[/campaign]\n",
            encoding="utf-8",
        )
        scenario.write_text(f"[scenario]\nid={SCENARIO_ID}\n[/scenario]\n", encoding="utf-8")
        executable = Path(directory) / "wesnoth"
        executable.write_text("fixture\n", encoding="utf-8")
        executable.chmod(0o700)
        return root, executable

    def test_success_records_bounded_evidence_and_cleans_staging(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, executable = self.fixture(directory)
            def succeed(command: list[str], **_: object) -> subprocess.CompletedProcess:
                output = Path(command[5])
                (output / "_main.cfg").write_text("validated\n", encoding="utf-8")
                return subprocess.CompletedProcess(command, 0, "validated\n", "")

            runner = mock.Mock(side_effect=succeed)
            evidence = validate_engine_002(root, executable=executable, runner=runner)
            self.assertTrue(evidence["pass"])
            self.assertEqual(evidence["exit_code"], 0)
            self.assertEqual(len(evidence["output_sha256"]), 64)
            self.assertNotIn("output", evidence)
            self.assertTrue(evidence["checks"]["temporary_artifacts_cleaned"])
            self.assertFalse(any(root.parent.glob(".wesnoth-scenario-*")))

    def test_engine_failure_is_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, executable = self.fixture(directory)
            completed = subprocess.CompletedProcess([], 1, "parse error\n", "")
            evidence = validate_engine_002(
                root, executable=executable, runner=mock.Mock(return_value=completed)
            )
            self.assertFalse(evidence["pass"])
            self.assertFalse(evidence["checks"]["engine_exit_zero"])
            self.assertEqual(evidence["diagnostic"], "parse error")
            self.assertEqual(evidence["failure_class"], "addon_validation")

    def test_diagnostic_paths_are_bounded_to_the_addon(self) -> None:
        diagnostic = (
            "Unexpected characters at ~add-ons/Star_Wars_Thrawn_Trilogy/"
            "scenarios/01_first_battle.cfg:64\n"
            "at ~add-ons/Other_Addon/secret.cfg:1"
        )
        self.assertEqual(
            diagnostic_paths(diagnostic),
            ["addons/Star_Wars_Thrawn_Trilogy/scenarios/01_first_battle.cfg"],
        )

    def test_engine_subsystem_and_unknown_unit_diagnostics_are_fatal(self) -> None:
        lines = campaign_error_lines(
            "error engine/team_construction: game_error: unknown unit type: sw_unit_fixture\n"
        )
        self.assertEqual(len(lines), 1)
        self.assertIn("unknown unit type", lines[0])

    def test_modal_map_diagnostics_are_fatal_even_when_the_process_survives(self) -> None:
        lines = campaign_error_lines(
            "The game map could not be loaded: A terrain with a string with more than 4 characters has been found, the affected terrain is: center\n"
        )
        self.assertEqual(len(lines), 1)
        self.assertIn("center", lines[0])

    def test_map_data_rejects_prose_terrain_tokens(self) -> None:
        bad = validate_map_data(Path("."), {
            "addons/Star_Wars_Thrawn_Trilogy/scenarios/fixture.cfg": (
                '[scenario]\nmap_data="Gg,center,Gg^Fp"\n[/scenario]\n'
            ),
        })
        self.assertFalse(bad["pass"])
        self.assertIn("center", bad["diagnostic"])

    def test_map_data_rejects_hash_prefixed_prose_in_external_map(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            map_path = root / "addons/Star_Wars_Thrawn_Trilogy/maps/fixture.map"
            map_path.parent.mkdir(parents=True)
            map_path.write_text("# center firing lane\nGg,Gg^Fp\n", encoding="utf-8")
            bad = validate_map_data(root, {
                "addons/Star_Wars_Thrawn_Trilogy/scenarios/fixture.cfg": (
                    '[scenario]\nmap_data="{~add-ons/Star_Wars_Thrawn_Trilogy/'
                    'maps/fixture.map}"\n[/scenario]\n'
                ),
            })
        self.assertFalse(bad["pass"])
        self.assertIn("contains a comment", bad["diagnostic"])

    def test_map_data_accepts_short_terrain_and_overlay_codes(self) -> None:
        good = validate_map_data(Path("."), {
            "addons/Star_Wars_Thrawn_Trilogy/scenarios/fixture.cfg": (
                '[scenario]\nmap_data="Gg,Kh,Gg^Fp"\n[/scenario]\n'
            ),
        })
        self.assertTrue(good["pass"], good["diagnostic"])

    def test_runtime_probe_stages_a_one_scenario_campaign(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            staged = Path(directory) / "_main.cfg"
            staged.write_text("#textdomain fixture\n", encoding="utf-8")
            campaign_id = prepare_runtime_probe_addon(
                staged, Path("scenarios/fixture.cfg"), "sw_fixture"
            )
            text = staged.read_text(encoding="utf-8")
            self.assertIn(f"id={campaign_id}", text)
            self.assertIn("first_scenario=sw_fixture", text)
            self.assertIn("scenarios/fixture.cfg", text)

    def test_windows_command_translates_only_path_arguments(self) -> None:
        translated = []

        def convert(path: Path) -> str:
            translated.append(path)
            return "WIN:" + path.name

        command = build_command(
            Path("/mnt/c/Wesnoth/wesnoth.exe"), Path("/tmp/userdata"),
            Path("/tmp/addon/_main.cfg"), Path("/tmp/output"), path_converter=convert,
        )
        self.assertEqual(
            translated,
            [
                Path("/mnt/c/Wesnoth/wesnoth.exe"), Path("/tmp/userdata"),
                Path("/tmp/addon/_main.cfg"), Path("/tmp/output"),
            ],
        )
        self.assertEqual(command[0], "WIN:wesnoth.exe")
        self.assertIn("WIN:userdata", command)
        self.assertIn("WIN:_main.cfg", command)
        self.assertIn("WIN:output", command)

    def test_windows_engine_runner_uses_a_waiting_hidden_process(self) -> None:
        command = ["C:\\Wesnoth\\wesnoth.exe", "--preprocess", "a b.cfg", "output"]
        with mock.patch("os.name", "posix"), mock.patch("subprocess.run") as run:
            run.return_value = subprocess.CompletedProcess(command, 0, "", "")
            run_engine(command, cwd=Path("/tmp"), timeout=12)
        invoked = run.call_args.args[0]
        self.assertEqual(invoked[0], "powershell.exe")
        encoded = invoked[-1]
        script = base64.b64decode(encoded).decode("utf-16le")
        self.assertIn("Start-Process", script)
        self.assertIn("-Wait -PassThru -WindowStyle Hidden", script)

    def test_declared_reinforcement_contract_matches_the_current_scenario(self) -> None:
        evidence = validate_declared_contracts(Path(__file__).resolve().parents[2])
        self.assertTrue(evidence["pass"], evidence["diagnostic"])

    def test_contract_coverage_rejects_an_uncontracted_gameplay_source(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            addon = root / "addons" / ADDON_ID
            tests = addon / "tests"
            tests.mkdir(parents=True)
            scenario = addon / "scenario.cfg"
            scenario.write_text("[scenario]\nid=sw_fixture\n[/scenario]\n", encoding="utf-8")
            tests.joinpath("gameplay-contracts.json").write_text(json.dumps({
                "schema_version": 1,
                "contracts": [{
                    "id": "sw-fixture-contract", "kind": "source-id",
                    "path": f"addons/{ADDON_ID}/scenario.cfg", "expected_id": "sw_fixture",
                }],
            }), encoding="utf-8")
            self.assertTrue(validate_declared_contracts(root, [
                f"addons/{ADDON_ID}/scenario.cfg"
            ])["pass"])
            self.assertFalse(validate_declared_contracts(root, [
                f"addons/{ADDON_ID}/other.cfg"
            ])["pass"])

    def test_historical_retention_covers_every_published_addon_ticket(self) -> None:
        evidence = validate_historical_retention(Path(__file__).resolve().parents[2])
        self.assertTrue(evidence["pass"], evidence["diagnostic"])
        self.assertGreaterEqual(len(evidence["tickets"]), 1)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--engine", action="store_true", help="Run the installed-engine validation")
    args = parser.parse_args()
    if args.engine:
        result = validate_engine_002(Path(__file__).resolve().parents[2])
        print(json.dumps(result, indent=2))
        return 0 if result["pass"] else 1
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(ScenarioLaunchSelfTests)
    return 0 if unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
