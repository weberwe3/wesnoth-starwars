#!/usr/bin/env python3
"""Coordinator-only regressions for native phase evidence using simulated processes.

No engine is started. Temporary stdout/stderr/native logs exercise the actual
runner's supervision and verdict path, including exit races after completion.
Run: python3 production/linux_engine/systems_test/run_systems_tests_selftest.py
"""
from __future__ import annotations

import json
import io
import signal
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import run_systems_tests as runner  # noqa: E402

PLUGIN = "air_test_plugin.lua"
SIGKILL = getattr(signal, "SIGKILL", 9)


def simulated_stop(process, *, force=False):
    """Simulated processes retain their configured native exit/race behavior."""
    if force:
        process.kill()
    else:
        process.terminate()


def valid_output(phase: str) -> str:
    lines = ["SW_TEST: PASS " + check for check in runner.REQUIRED_CHECKS[PLUGIN][phase]]
    if phase == "main":
        lines += ["SW_TEST: state prepared for save", "SW_TEST: saved"]
    return "\n".join(lines + ["SW_TEST: done"]) + "\n"


class SimulatedProcess:
    def __init__(self, stdout, stderr, specification: dict):
        self.returncode = specification.get("exit_code")
        self.stop_code = specification.get("stop_code", runner._TERMINATE_EXIT)
        self.kill_code = specification.get("kill_code", runner._KILL_EXIT)
        self.terminate_calls = 0
        self.kill_calls = 0
        stdout.write(specification.get("stdout", ""))
        stderr.write(specification.get("stderr", ""))
        stdout.flush()
        stderr.flush()

    def poll(self):
        return self.returncode

    def terminate(self):
        self.terminate_calls += 1
        self.returncode = self.stop_code

    def kill(self):
        self.kill_calls += 1
        self.returncode = self.kill_code

    def wait(self, timeout=None):
        if self.returncode is None:
            raise subprocess.TimeoutExpired("simulated-engine", timeout)
        return self.returncode


class NativePhaseEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="sw-phase-selftest-")
        self.addCleanup(self.directory.cleanup)
        self.work = Path(self.directory.name)
        self.userdata = self.work / "userdata"
        (self.userdata / "logs").mkdir(parents=True)
        self.fixture = self.work / "fixtures"
        self.fixture.mkdir()
        (self.fixture / PLUGIN).write_text('local PHASE = "main"\n', encoding="utf-8")
        self.processes = []
        self.commands = []
        self.clock = 0.0

    def monotonic(self):
        self.clock += 0.5
        return self.clock

    def factory(self, specification):
        def start(command, **kwargs):
            self.commands.append(command)
            phase = "load" if "--load" in command else "main"
            spec = specification(phase) if callable(specification) else specification
            if "native_log" in spec:
                (self.userdata / "logs" / f"{phase}.log").write_text(spec["native_log"], encoding="utf-8")
            if spec.get("make_save"):
                saves = self.userdata / "sync/saves"
                saves.mkdir(parents=True, exist_ok=True)
                (saves / "sw_air_test_save.gz").write_text("simulated save", encoding="utf-8")
            process = SimulatedProcess(kwargs["stdout"], kwargs["stderr"], spec)
            self.processes.append(process)
            return process
        return start

    def phase(self, specification, phase="main"):
        extra = ["--load", "sw_air_test_save.gz"] if phase == "load" else []
        with patch.object(runner, "HERE", self.fixture), \
             patch.object(runner, "request_engine_stop", side_effect=simulated_stop), \
             patch.object(runner.subprocess, "Popen", side_effect=self.factory(specification)), \
             patch.object(runner.time, "monotonic", side_effect=self.monotonic), \
             patch.object(runner.time, "sleep"):
            return runner.run_phase(Path("simulated-engine"), self.userdata, PLUGIN, phase, 1, extra)

    def suite(self, specification):
        evidence = []
        with patch.object(runner, "HERE", self.fixture), \
             patch.object(runner, "request_engine_stop", side_effect=simulated_stop), \
             patch.object(runner, "stage", return_value=self.userdata), \
             patch.object(runner.subprocess, "Popen", side_effect=self.factory(specification)), \
             patch.object(runner.time, "monotonic", side_effect=self.monotonic), \
             patch.object(runner.time, "sleep"):
            results, errors = runner.run_plugin_suite(Path("simulated-engine"), self.work,
                                                     "air", 1, evidence)
        return results, errors, evidence

    def test_completed_idle_process_owned_stop_passes(self):
        result = self.phase({"stdout": valid_output("main")})
        self.assertTrue(result["pass"], result)
        self.assertTrue(result["completed"])
        self.assertTrue(result["termination_requested"])
        self.assertTrue(result["termination_after_completion"])
        self.assertTrue(result["owned_stop_after_completion"])
        self.assertEqual(result["engine_exit_code"], runner._TERMINATE_EXIT)
        self.assertEqual(self.processes[0].terminate_calls, 1)
        json.dumps(result)  # All retained phase evidence is JSON serializable.

    def test_normal_completed_exit_passes_without_owned_stop(self):
        result = self.phase({"stdout": valid_output("main"), "exit_code": 0})
        self.assertTrue(result["pass"], result)
        self.assertFalse(result["termination_requested"])
        self.assertFalse(result["owned_stop_after_completion"])

    def test_owned_kill_fallback_is_recorded(self):
        result = self.phase({"stdout": valid_output("main"), "stop_code": None})
        self.assertTrue(result["pass"], result)
        self.assertTrue(result["kill_requested"])
        self.assertEqual(self.processes[0].kill_calls, 1)
        self.assertEqual(result["engine_exit_code"], runner._KILL_EXIT)

    def test_unrequested_signals_are_not_owned(self):
        for code in (runner._TERMINATE_EXIT, runner._KILL_EXIT, 1):
            with self.subTest(code=code):
                result = self.phase({"stdout": valid_output("main"), "exit_code": code})
                self.assertFalse(result["pass"])
                self.assertFalse(result["owned_stop_after_completion"])

    def test_aborts_after_done_still_fail(self):
        for code in (-6, -11):
            with self.subTest(code=code):
                result = self.phase({"stdout": valid_output("main"), "exit_code": code})
                self.assertTrue(result["completed"])
                self.assertFalse(result["pass"])
                self.assertIn(f"unexpected engine exit: {code}", result["errors"])

    def test_abort_racing_with_owned_shutdown_still_fails(self):
        for code in (-6, -11, -SIGKILL, 1):
            with self.subTest(code=code):
                result = self.phase({"stdout": valid_output("main"), "stop_code": code})
                self.assertTrue(result["termination_after_completion"])
                self.assertFalse(result["owned_stop_after_completion"])
                self.assertFalse(result["pass"])

    def test_exit_zero_without_done_fails(self):
        text = valid_output("main").replace("SW_TEST: done\n", "")
        result = self.phase({"stdout": text, "exit_code": 0})
        self.assertFalse(result["pass"])
        self.assertIn("phase completion marker missing", result["errors"])

    def test_timeout_is_not_owned_completion(self):
        result = self.phase({"stdout": "SW_TEST: PASS early check\n"})
        self.assertTrue(result["timed_out"])
        self.assertFalse(result["completed"])
        self.assertFalse(result["termination_after_completion"])
        self.assertFalse(result["pass"])

    def test_done_without_checks_or_save_is_partial_failure(self):
        result = self.phase({"stdout": "SW_TEST: done\n"})
        self.assertFalse(result["pass"])
        self.assertIn("phase produced no meaningful checks", result["errors"])
        self.assertIn("main phase did not complete save preparation and saving", result["errors"])

    def test_partial_reload_with_done_fails_required_checks(self):
        text = valid_output("load")
        missing = runner.REQUIRED_CHECKS[PLUGIN]["load"][-1]
        text = text.replace("SW_TEST: PASS " + missing + "\n", "")
        result = self.phase({"stdout": text}, "load")
        self.assertTrue(result["completed"])
        self.assertFalse(result["pass"])
        self.assertIn("required passing check missing: " + missing, result["errors"])

    def test_any_reported_failure_survives_completion(self):
        result = self.phase({"stdout": valid_output("main") + "SW_TEST: FAIL extra gameplay check\n"})
        self.assertFalse(result["pass"])
        self.assertIn("SW_TEST: FAIL extra gameplay check", result["failed_checks"])

    def test_fatal_in_stdout_or_stderr_fails_even_with_zero_exit(self):
        fatal = "Fatal glibc error: pthread_mutex_lock.c:450: Assertion `e != ESRCH || !robust' failed.\n"
        for stream in ("stdout", "stderr"):
            with self.subTest(stream=stream):
                spec = {"stdout": valid_output("main"), "exit_code": 0}
                spec[stream] = spec.get(stream, "") + fatal
                result = self.phase(spec)
                self.assertFalse(result["pass"])
                self.assertTrue(any("Fatal glibc" in error for error in result["errors"]))
                self.assertIn(fatal.strip(), result["diagnostics"][stream]["tail"])

    def test_native_log_fatal_is_also_visible(self):
        result = self.phase({"stdout": valid_output("main"), "exit_code": 0,
                             "native_log": "error engine: native fatal assertion\n"})
        self.assertFalse(result["pass"])
        self.assertTrue(any("native fatal assertion" in error for error in result["errors"]))

    def test_failure_tails_are_bounded(self):
        text = "X" * (runner.LOG_TAIL_LIMIT + 100) + "\n" + valid_output("main")
        result = self.phase({"stdout": text, "exit_code": -6})
        tail = result["diagnostics"]["stdout"]
        self.assertTrue(tail["truncated"])
        self.assertEqual(len(tail["tail"]), runner.LOG_TAIL_LIMIT)
        self.assertIn("SW_TEST: done", tail["tail"])

    def test_native_log_and_stdout_mirror_do_not_duplicate_checks(self):
        text = valid_output("main")
        result = self.phase({"stdout": text, "native_log": text})
        self.assertTrue(result["pass"], result)
        self.assertEqual(len(result["checks"]), len(runner.REQUIRED_CHECKS[PLUGIN]["main"]))

    def test_required_save_and_two_phases_use_bare_filename(self):
        def spec(phase):
            return {"stdout": valid_output(phase), "make_save": phase == "main"}
        results, errors, evidence = self.suite(spec)
        self.assertFalse(errors, errors)
        self.assertFalse(any("] FAIL " in line for line in results), results)
        self.assertEqual([phase["phase"] for phase in evidence], ["main", "load"])
        self.assertTrue(all(phase["pass"] for phase in evidence))
        self.assertEqual(self.commands[-1][-2:], ["--load", "sw_air_test_save.gz"])

    def test_missing_authoritative_save_blocks_reload_and_suite(self):
        (self.work / "sw_air_test_save.gz").write_text("wrong directory", encoding="utf-8")
        results, errors, evidence = self.suite({"stdout": valid_output("main")})
        self.assertTrue(any("no authoritative save" in error for error in errors), errors)
        self.assertTrue(any("] FAIL save/load" in line for line in results), results)
        self.assertEqual(len(evidence), 1)
        self.assertEqual(len(self.commands), 1)

    def test_successful_main_cannot_hide_partial_reload(self):
        def spec(phase):
            return {"stdout": valid_output(phase) if phase == "main" else "SW_TEST: done\n",
                    "make_save": phase == "main"}
        results, errors, evidence = self.suite(spec)
        self.assertTrue(evidence[0]["pass"])
        self.assertFalse(evidence[1]["pass"])
        self.assertTrue(errors)
        self.assertTrue(any("] FAIL load phase evidence" in line for line in results), results)

    def test_main_fatal_is_not_erased_by_successful_reload(self):
        def spec(phase):
            return {"stdout": valid_output(phase), "make_save": phase == "main",
                    "stderr": "Fatal glibc error: mutex assertion failed\n" if phase == "main" else ""}
        results, errors, evidence = self.suite(spec)
        self.assertFalse(evidence[0]["pass"])
        self.assertTrue(evidence[1]["pass"])
        self.assertTrue(errors)
        self.assertTrue(any("] FAIL main phase evidence" in line for line in results), results)

    def test_exact_synthetic_warning_is_retained_in_each_output_source(self):
        warning = "20261010 21:00:34 " + runner.SYNTHETIC_CONTROLLER_DIAGNOSTIC
        for source in ("stdout", "stderr", "native_log"):
            with self.subTest(source=source):
                spec = {"stdout": valid_output("main")}
                spec[source] = spec.get(source, "") + warning + "\n"
                result = self.phase(spec)
                self.assertTrue(result["pass"], result)
                self.assertEqual(result["warnings"], [warning])
                self.assertFalse(result["errors"])

    def test_classifier_matches_only_complete_known_diagnostic(self):
        warning = runner.SYNTHETIC_CONTROLLER_DIAGNOSTIC
        errors, warnings = runner.classify_diagnostics(warning + "\n20261010 21:00:34 " + warning)
        self.assertFalse(errors)
        self.assertEqual(warnings, [warning, "20261010 21:00:34 " + warning])
        negatives = (
            "error replay: OOS detected: change_controller_wml state differs",
            warning.replace("doing the choice locally", "doing another choice locally"),
            warning + " Fatal glibc error: controller assertion failed",
            "Fatal glibc error: change_controller_wml assertion failed",
            "error replay: change_controller_wml failed in synced context",
            "error engine: " + warning,
        )
        for diagnostic in negatives:
            with self.subTest(diagnostic=diagnostic):
                errors, warnings = runner.classify_diagnostics(diagnostic)
                self.assertEqual(errors, [diagnostic])
                self.assertFalse(warnings)

    def test_warning_never_excuses_real_replay_errors_or_fatals(self):
        warning = runner.SYNTHETIC_CONTROLLER_DIAGNOSTIC
        negatives = (
            "error replay: OOS detected: change_controller_wml state differs",
            "error replay: change_controller_wml choice unavailable",
            "Fatal glibc error: change_controller_wml mutex assertion failed",
            warning + " Assertion `controller' failed.",
            warning.replace("This can cause OOS.", "This caused OOS."),
        )
        for diagnostic in negatives:
            with self.subTest(diagnostic=diagnostic):
                result = self.phase({"stdout": valid_output("main") + warning + "\n",
                                     "stderr": diagnostic + "\n"})
                self.assertFalse(result["pass"])
                self.assertIn(diagnostic, result["errors"])
                self.assertEqual(result["warnings"], [warning])

    def test_exact_warning_does_not_excuse_abort_or_missing_completion(self):
        warning = runner.SYNTHETIC_CONTROLLER_DIAGNOSTIC + "\n"
        aborted = self.phase({"stdout": valid_output("main") + warning, "exit_code": -6})
        self.assertFalse(aborted["pass"])
        self.assertIn("unexpected engine exit: -6", aborted["errors"])
        incomplete = self.phase({"stdout": valid_output("main").replace("SW_TEST: done\n", "")
                                 + warning, "exit_code": 0})
        self.assertFalse(incomplete["pass"])
        self.assertIn("phase completion marker missing", incomplete["errors"])

    def replay_output(self, diagnostic):
        checkpoints = [f"SW_TEST: PASS checkpoint {i} (original)" for i in range(4)]
        checkpoints += [f"SW_TEST: PASS checkpoint {i} (replay)" for i in range(4)]
        return "\n".join(checkpoints + ["PASS TEST", diagnostic]) + "\n"

    def test_replay_uses_exact_warning_classifier_and_retains_warnings(self):
        warning = runner.SYNTHETIC_CONTROLLER_DIAGNOSTIC
        warnings = []
        process = subprocess.CompletedProcess(["simulated-engine"], 0,
                                             stdout=self.replay_output(warning), stderr="")
        with patch.object(runner, "stage", return_value=self.userdata), \
             patch.object(runner.subprocess, "run", return_value=process):
            results, errors = runner.run_replay_test(Path("simulated-engine"), self.work,
                                                     "sw_test_air_replay", 1, warnings)
        self.assertFalse(errors)
        self.assertFalse(any("] FAIL " in result for result in results), results)
        self.assertEqual(warnings, ["[replay:sw_test_air_replay] " + warning])

    def test_replay_controller_mentions_cannot_hide_real_error(self):
        for diagnostic in (
                "error replay: OOS detected for change_controller_wml",
                "Fatal glibc error: change_controller_wml assertion failed",
                runner.SYNTHETIC_CONTROLLER_DIAGNOSTIC + " Fatal native failure"):
            with self.subTest(diagnostic=diagnostic):
                process = subprocess.CompletedProcess(["simulated-engine"], 0,
                                                     stdout=self.replay_output(diagnostic), stderr="")
                warnings = []
                with patch.object(runner, "stage", return_value=self.userdata), \
                     patch.object(runner.subprocess, "run", return_value=process):
                    _, errors = runner.run_replay_test(Path("simulated-engine"), self.work,
                                                       "sw_test_air_replay", 1, warnings)
                self.assertIn(diagnostic, errors)
                self.assertFalse(warnings)

    def test_windows_native_log_supplies_replay_checkpoints(self):
        text = self.replay_output("")
        (self.userdata / "logs/native.out.log").write_text(text, encoding="utf-8")
        for stdout in ("", text):
            with self.subTest(mirrored=bool(stdout)):
                process = subprocess.CompletedProcess(["simulated-engine"], 0, stdout=stdout, stderr="")
                with patch.object(runner, "stage", return_value=self.userdata), \
                     patch.object(runner.subprocess, "run", return_value=process):
                    results, errors = runner.run_replay_test(Path("simulated-engine"), self.work,
                                                            "sw_test_air_replay", 1)
                self.assertFalse(errors)
                self.assertFalse(any("] FAIL " in result for result in results), results)
                self.assertTrue(any("reproduced by the replay: 4" in result for result in results))

    def test_windows_replay_keeps_output_in_owned_pipes(self):
        process = subprocess.CompletedProcess(["simulated-engine"], 0, stdout=self.replay_output(""), stderr="")
        for windows in (False, True):
            with self.subTest(windows=windows), patch.object(runner, "_WINDOWS_HOST", windows), \
                 patch.object(runner, "stage", return_value=self.userdata), \
                 patch.object(runner.subprocess, "run", return_value=process) as run:
                _, errors = runner.run_replay_test(Path("simulated-engine"), self.work, "sw_test_air_replay", 1)
                self.assertFalse(errors)
                self.assertEqual("--wnoconsole" in run.call_args.args[0], windows)

    def test_native_log_cannot_excuse_missing_checkpoint_or_fatal(self):
        for text in (self.replay_output("").replace("SW_TEST: PASS checkpoint 3 (replay)\n", ""),
                     self.replay_output("error engine: native replay failed")):
            with self.subTest(text=text):
                (self.userdata / "logs/native.out.log").write_text(text, encoding="utf-8")
                process = subprocess.CompletedProcess(["simulated-engine"], 0, stdout="", stderr="")
                with patch.object(runner, "stage", return_value=self.userdata), \
                     patch.object(runner.subprocess, "run", return_value=process):
                    results, errors = runner.run_replay_test(Path("simulated-engine"), self.work,
                                                            "sw_test_air_replay", 1)
                self.assertTrue(errors or any("] FAIL " in result for result in results))

    def test_top_level_json_explicitly_retains_phase_warnings(self):
        warning = runner.SYNTHETIC_CONTROLLER_DIAGNOSTIC
        output = self.work / "report.json"

        def completed_suite(engine, work, suite, timeout, phase_evidence):
            phase_evidence.append({"suite": suite, "phase": "main", "warnings": [warning]})
            return ["[air] PASS simulated complete suite"], []

        with patch.object(sys, "argv", ["runner", "--suite", "air", "--workdir", str(self.work),
                                        "--output", str(output)]), \
             patch.object(runner, "run_static_checks", return_value=[]), \
             patch.object(runner, "run_plugin_suite", side_effect=completed_suite), \
             patch("sys.stdout", new_callable=io.StringIO):
            code = runner.main()
        evidence = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(code, 0)
        self.assertEqual(evidence["engine_warnings"], ["[air] main: " + warning])
        self.assertEqual(evidence["phase_evidence"][0]["warnings"], [warning])
        self.assertFalse(evidence["engine_errors"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
