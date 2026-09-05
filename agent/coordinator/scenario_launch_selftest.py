#!/usr/bin/env python3

"""Deterministic ENGINE-002 preprocessing smoke with isolated staged userdata."""

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
import unittest
from unittest import mock


ADDON_ID = "Star_Wars_Thrawn_Trilogy"
SCENARIO_ID = "01_First_Battle"
CAMPAIGN_DEFINE = "CAMPAIGN_STAR_WARS_THRAWN_TRILOGY"
ENGINE_TIMEOUT_SECONDS = 120


def find_wesnoth_executable() -> Path | None:
    configured = os.environ.get("WESNOTH_EXECUTABLE")
    candidates = [
        configured,
        shutil.which("wesnoth"),
        shutil.which("wesnoth.exe"),
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
        str(executable),
        "--userdata-dir", convert(userdata),
        "--preprocess", convert(source), convert(output),
        f"--preprocess-defines={CAMPAIGN_DEFINE}",
        "--no-log-to-file",
    ]


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
            completed = runner(
                command,
                cwd=root,
                text=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=ENGINE_TIMEOUT_SECONDS,
                check=False,
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
        except (OSError, subprocess.SubprocessError):
            evidence["exit_code"] = 125
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
            [Path("/tmp/userdata"), Path("/tmp/addon/_main.cfg"), Path("/tmp/output")],
        )
        self.assertIn("WIN:userdata", command)
        self.assertIn("WIN:_main.cfg", command)
        self.assertIn("WIN:output", command)


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
