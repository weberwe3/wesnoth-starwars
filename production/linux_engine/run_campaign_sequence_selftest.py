#!/usr/bin/env python3
"""Regressions for campaign completion, process ownership and fatal evidence."""
from __future__ import annotations

import os
import gzip
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock
import run_campaign_sequence as sequence

from run_campaign_sequence import (
    CAMPAIGN_I, EXPECTED, REQUIRED_HEROES, _KILL_EXIT, _TERMINATE_EXIT,
    _run_engine_phase, evaluate, parse, process_failures, run_sequence, validate_sequence_saves,
)


def completed_campaign_log() -> str:
    lines = []
    for scenario in EXPECTED:
        heroes = ";".join(f"{hero}=type@1,1:xp0" for hero in REQUIRED_HEROES.get(scenario, []))
        lines += [f"SW_SEQ: scenario {scenario} turn 1", f"SW_SEQ: heroes_on_map {heroes}",
                  f"SW_SEQ: saved {scenario}", f"SW_SEQ: win script ran {scenario}",
                  f"SW_SEQ: left {scenario} via Dialog"]
    return "\n".join(lines + ["SW_SEQ: done"]) + "\n"


def engine_save(campaign: str, scenario: str) -> bytes:
    return gzip.compress((f'campaign="{campaign}"\n[snapshot]\n'
                          f'\tid="{scenario}"\n\tmap_data="Gg, Gg\nGg, Gg"\n'
                          '\t[side]\n\t\tside=1\n\t[/side]\n[/snapshot]\n'
                          '[replay]\n[/replay]\n').encode("utf-8"))


class CampaignSequenceEvidenceTests(unittest.TestCase):
    def test_complete_campaign_still_requires_every_save_win_transition_and_done(self) -> None:
        text = completed_campaign_log()
        self.assertEqual(evaluate(parse(text), text), [])
        for marker in (f"saved {EXPECTED[0]}", f"win script ran {EXPECTED[0]}",
                       f"left {EXPECTED[0]} via Dialog", "done"):
            with self.subTest(marker=marker):
                incomplete = text.replace("SW_SEQ: " + marker + "\n", "")
                self.assertTrue(evaluate(parse(incomplete), incomplete))

    def test_wrong_scenario_marker_cannot_confirm_another_scenario(self) -> None:
        text = completed_campaign_log()
        for marker in ("saved ", "win script ran ", "left "):
            with self.subTest(marker=marker):
                wrong = text.replace("SW_SEQ: " + marker + EXPECTED[0], "SW_SEQ: " + marker + "sw_wrong", 1)
                self.assertTrue(evaluate(parse(wrong), wrong))

    def test_native_fatal_after_all_campaign_markers_remains_failure(self) -> None:
        for fatal in ("Fatal glibc error: tpp.c:83 (__pthread_tpp_change_priority): assertion failed",
                      "terminate called after throwing an instance of std::runtime_error",
                      "Segmentation fault", "Aborted", "double free or corruption"):
            with self.subTest(fatal=fatal):
                text = completed_campaign_log() + fatal + "\n"
                self.assertTrue(any("log:" in failure for failure in evaluate(parse(text), text)))

    def test_generic_fatal_diagnostic_prefixes_fail_without_matching_narrative_mentions(self) -> None:
        for fatal in ("fatal: renderer unavailable", "fatal error: engine stopped",
                      "2026-10-10 14:33:22 fatal: engine stopped",
                      "20261010 14:33:22 fatal error: engine stopped",
                      "[2026-10-10T14:33:22.123Z] FATAL ERROR: engine stopped",
                      "14:33:22 fatal: engine stopped"):
            with self.subTest(fatal=fatal):
                text = completed_campaign_log() + fatal + "\n"
                self.assertTrue(any("log:" in failure for failure in evaluate(parse(text), text)))
        for narrative in ("SW_SEQ: note a fatal error: was discussed", "message: avoid a fatal: mistake", "fatalities: zero"):
            text = completed_campaign_log() + narrative + "\n"
            self.assertEqual(evaluate(parse(text), text), [])

    def test_generic_fatal_after_done_and_zero_exit_is_detected_in_every_stream(self) -> None:
        for stream in ("stdout", "stderr", "native"):
            with self.subTest(stream=stream):
                fatal = "fatal error: native fixture stopped"
                if stream == "native":
                    code = f"from pathlib import Path; print('SW_SEQ: done'); Path('userdata/logs/native.log').write_text({fatal!r})"
                else:
                    code = "import sys; print('SW_SEQ: done'); " + f"print({fatal!r}, file=sys.{stream})"
                phase = self.phase(code)
                self.assertEqual(phase["exit_code"], 0)
                self.assertTrue(any("log:" in failure for failure in evaluate(parse(phase["log_text"]), phase["all_output"])))

    def test_complete_markers_cannot_pass_without_actual_authoritative_saves(self) -> None:
        text = completed_campaign_log()
        phase = {"log_text": text, "all_output": text, "exit_code": 0, "done": True,
                 "done_before_stop": False, "timed_out": False, "timeout_seconds": 1,
                 "terminate_requested": False, "kill_requested": False}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            addon = root / "addon"
            addon.mkdir()
            (addon / "fixture.cfg").write_text("fixture", encoding="utf-8")
            with mock.patch("run_campaign_sequence._run_engine_phase", return_value=phase):
                evidence = run_sequence(addon, Path(sys.executable), root / "run")
            self.assertFalse(evidence["pass"], evidence)
            self.assertEqual(len(evidence["save_validation"]["failures"]), len(EXPECTED))
            self.assertEqual(evidence["saves"], [])

    def test_only_full_readable_matching_save_set_can_pass_the_runner(self) -> None:
        text = completed_campaign_log()
        phase = {"log_text": text, "all_output": text, "exit_code": 0, "done": True,
                 "done_before_stop": False, "timed_out": False, "timeout_seconds": 1,
                 "terminate_requested": False, "kill_requested": False}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            addon = root / "addon"
            addon.mkdir()
            (addon / "fixture.cfg").write_text("fixture", encoding="utf-8")
            def completed(_command, _workdir, userdata, _environment, _timeout):
                saves = userdata / "sync/saves"
                saves.mkdir(parents=True)
                for scenario in EXPECTED:
                    (saves / f"sw_seq_{scenario}.gz").write_bytes(engine_save(CAMPAIGN_I, scenario))
                return phase
            with mock.patch("run_campaign_sequence._run_engine_phase", side_effect=completed):
                evidence = run_sequence(addon, Path(sys.executable), root / "run")
            self.assertTrue(evidence["pass"], evidence)
            self.assertEqual(len(evidence["saves"]), len(EXPECTED))
            self.assertTrue(all(item["pass"] for item in evidence["save_validation"]["checks"]))

    def test_save_binding_rejects_wrong_directory_identity_and_invalid_content(self) -> None:
        scenario = EXPECTED[0]
        defects = ("wrong-directory", "wrong-filename", "wrong-scenario", "wrong-campaign", "empty",
                   "bad-gzip", "empty-gzip", "arbitrary-text", "unbalanced-wml", "missing-state")
        for defect in defects:
            with self.subTest(defect=defect), tempfile.TemporaryDirectory() as directory:
                userdata = Path(directory) / "userdata"
                saves = userdata / ("other/saves" if defect == "wrong-directory" else "sync/saves")
                saves.mkdir(parents=True)
                filename = "sw_seq_sw_wrong.gz" if defect == "wrong-filename" else f"sw_seq_{scenario}.gz"
                payload = engine_save(CAMPAIGN_I, scenario)
                if defect == "wrong-scenario":
                    payload = engine_save(CAMPAIGN_I, "sw_wrong")
                elif defect == "wrong-campaign":
                    payload = engine_save("sw_wrong", scenario)
                elif defect == "empty":
                    payload = b""
                elif defect == "bad-gzip":
                    payload = b"not gzip"
                elif defect == "empty-gzip":
                    payload = gzip.compress(b"")
                elif defect == "arbitrary-text":
                    payload = gzip.compress(b"a narrative mentioning the scenario")
                elif defect == "unbalanced-wml":
                    payload = gzip.compress(gzip.decompress(payload).replace(b"[/snapshot]", b""))
                elif defect == "missing-state":
                    payload = gzip.compress(f'campaign="{CAMPAIGN_I}"\n[snapshot]\nid="{scenario}"\n[/snapshot]\n'.encode())
                (saves / filename).write_bytes(payload)
                evidence = validate_sequence_saves(userdata, CAMPAIGN_I, [scenario])
                self.assertFalse(evidence["pass"], evidence)
                self.assertIn(f"sw_seq_{scenario}.gz", evidence["failures"][0])

    def test_engine_serialized_translated_and_multiline_concatenation_is_readable(self) -> None:
        scenario = EXPECTED[0]
        serialized = (
            '[event]\n[floating_text]\ntext="<span color=\'#c8a0ff\'>" +\n'
            '    _"Frame secured" +\n    "</span>"\n[/floating_text]\n'
            '[dummy]\nhelp_text=_"First translated phrase" +\n    "\n" +\n'
            '    _"Second translated phrase\ncontinues across lines."\n'
            'description="Embedded ""quotes"" remain a single term" + _" final term"\n'
            '[/dummy]\n[/event]\n'
        )
        with tempfile.TemporaryDirectory() as directory:
            userdata = Path(directory) / "userdata"
            saves = userdata / "sync/saves"
            saves.mkdir(parents=True)
            payload = gzip.decompress(engine_save(CAMPAIGN_I, scenario)).decode()
            payload = payload.replace("[/snapshot]", serialized + "[/snapshot]")
            (saves / f"sw_seq_{scenario}.gz").write_bytes(gzip.compress(payload.encode()))
            evidence = validate_sequence_saves(userdata, CAMPAIGN_I, [scenario])
            self.assertTrue(evidence["pass"], evidence)

    def test_engine_valid_names_starting_with_digits_are_readable(self) -> None:
        # Lua tables stored as WML variables serialize keys such as "2" or
        # "1st"; the engine accepts any letters, digits and underscores.
        scenario = EXPECTED[0]
        with tempfile.TemporaryDirectory() as directory:
            userdata = Path(directory) / "userdata"
            saves = userdata / "sync/saves"
            saves.mkdir(parents=True)
            payload = gzip.decompress(engine_save(CAMPAIGN_I, scenario)).decode()
            payload = payload.replace("[/snapshot]",
                                      '[variables]\n[2]\n1st=5\n_hidden=yes\n2="two"\n[/2]\n[/variables]\n[/snapshot]')
            (saves / f"sw_seq_{scenario}.gz").write_bytes(gzip.compress(payload.encode()))
            evidence = validate_sequence_saves(userdata, CAMPAIGN_I, [scenario])
            self.assertTrue(evidence["pass"], evidence)
            for bad in ("_=1", "[_]\n[/_]", "bad-key=1", "[x y]\n[/x y]"):
                broken = payload.replace("[/snapshot]", bad + "\n[/snapshot]", 1)
                (saves / f"sw_seq_{scenario}.gz").write_bytes(gzip.compress(broken.encode()))
                evidence = validate_sequence_saves(userdata, CAMPAIGN_I, [scenario])
                self.assertFalse(evidence["pass"], bad)

    def test_serialized_string_continuation_must_be_valid_and_complete(self) -> None:
        scenario = EXPECTED[0]
        defects = (
            'text="start" +\nnot_a_string\n',
            'text="start" +\n_\n',
            'text="start" +\n+ "extra"\n',
            'text="start"\n_"unrequested continuation"\n',
            'text="start" +\n[side]\n[/side]\n',
            'text="start" +\nother_property="wrong continuation"\n',
            'text="start" +\n',
            'text=_"unterminated translated string\n',
        )
        for defect in defects:
            with self.subTest(defect=defect), tempfile.TemporaryDirectory() as directory:
                userdata = Path(directory) / "userdata"
                saves = userdata / "sync/saves"
                saves.mkdir(parents=True)
                payload = gzip.decompress(engine_save(CAMPAIGN_I, scenario)).decode()
                payload = payload.replace("[/snapshot]", defect + "[/snapshot]")
                (saves / f"sw_seq_{scenario}.gz").write_bytes(gzip.compress(payload.encode()))
                evidence = validate_sequence_saves(userdata, CAMPAIGN_I, [scenario])
                self.assertFalse(evidence["pass"], evidence)

    def test_non_owned_signals_and_invalid_ownership_never_pass(self) -> None:
        base = {"done": True, "done_before_stop": False, "timed_out": False,
                "terminate_requested": False, "kill_requested": False,
                "exit_code": 0, "timeout_seconds": 1}
        self.assertEqual(process_failures(base), [])
        for code in (1, -6, -11, _TERMINATE_EXIT, _KILL_EXIT, None):
            with self.subTest(code=code):
                self.assertTrue(process_failures({**base, "exit_code": code}))
        owned = {**base, "done_before_stop": True, "terminate_requested": True,
                 "exit_code": _TERMINATE_EXIT}
        self.assertEqual(process_failures(owned), [])
        self.assertEqual(process_failures({**owned, "kill_requested": True, "exit_code": _KILL_EXIT}), [])
        for override in ({"done": False}, {"done_before_stop": False}, {"timed_out": True},
                         {"exit_code": -6}, {"exit_code": -11},
                         {"terminate_requested": False, "kill_requested": True, "exit_code": _KILL_EXIT}):
            with self.subTest(override=override):
                self.assertTrue(process_failures({**owned, **override}))

    def phase(self, code: str, *, timeout: float = 2.0) -> dict:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "userdata/logs").mkdir(parents=True)
            return _run_engine_phase(
                [sys.executable, "-u", "-c", code], root, root / "userdata", dict(os.environ), timeout,
                completion_grace=0.1, poll_interval=0.01, stop_timeout=0.2,
            )

    def test_actual_normal_exit_captures_completion_and_both_streams(self) -> None:
        phase = self.phase("import sys; print('SW_SEQ: done'); print('diagnostic', file=sys.stderr)")
        self.assertEqual(process_failures(phase), [])
        self.assertEqual(phase["exit_code"], 0)
        self.assertFalse(phase["terminate_requested"])
        self.assertIn("SW_SEQ: done", phase["stdout_tail"])
        self.assertIn("diagnostic", phase["stderr_tail"])

    def test_actual_native_fatal_stderr_is_retained_after_completion(self) -> None:
        phase = self.phase("import sys; print('SW_SEQ: done'); print('Fatal glibc error: tpp.c:83', file=sys.stderr)")
        self.assertIn("Fatal glibc error", phase["stderr_tail"])
        self.assertTrue(any("Fatal glibc error" in failure
                            for failure in evaluate(parse(phase["log_text"]), phase["all_output"])))

    def test_actual_nonzero_after_done_is_not_reclassified_as_owned_stop(self) -> None:
        phase = self.phase("import sys; print('SW_SEQ: done'); sys.exit(7)")
        self.assertEqual(phase["exit_code"], 7)
        self.assertFalse(phase["terminate_requested"])
        self.assertTrue(process_failures(phase))

    def test_actual_missing_or_inexact_done_marker_fails(self) -> None:
        for text in ("SW_SEQ: not done", "SW_SEQ: done unexpectedly"):
            with self.subTest(text=text):
                phase = self.phase(f"print({text!r})")
                self.assertFalse(phase["done"])
                self.assertTrue(process_failures(phase))

    def test_actual_timeout_records_final_exit_and_fails(self) -> None:
        phase = self.phase("import time; time.sleep(30)", timeout=0.15)
        self.assertTrue(phase["timed_out"])
        self.assertTrue(phase["terminate_requested"])
        self.assertFalse(phase["done_before_stop"])
        self.assertIsInstance(phase["exit_code"], int)
        self.assertTrue(process_failures(phase))

    def test_actual_owned_post_completion_termination_is_recorded(self) -> None:
        phase = self.phase("import time; print('SW_SEQ: done', flush=True); time.sleep(30)")
        self.assertTrue(phase["done_before_stop"])
        self.assertTrue(phase["terminate_requested"])
        self.assertFalse(phase["kill_requested"])
        self.assertEqual(phase["exit_code"], _TERMINATE_EXIT)
        self.assertEqual(process_failures(phase), [])

    def test_native_windows_stop_uses_distinct_owned_codes(self) -> None:
        process = mock.Mock()
        winapi = mock.Mock()
        for force, expected in ((False, 0x53570001), (True, 0x53570002)):
            with self.subTest(force=force), mock.patch.object(sequence, "_WINDOWS_HOST", True), \
                 mock.patch.object(sequence, "_TERMINATE_EXIT", 0x53570001), \
                 mock.patch.object(sequence, "_KILL_EXIT", 0x53570002), \
                 mock.patch.dict(sys.modules, {"_winapi": winapi}):
                sequence.request_engine_stop(process, force=force)
                winapi.TerminateProcess.assert_called_with(process._handle, expected)
        process.terminate.assert_not_called()
        process.kill.assert_not_called()

    @unittest.skipUnless(os.name == "posix", "Linux signal exit evidence")
    def test_actual_owned_kill_escalation_is_recorded(self) -> None:
        phase = self.phase("import signal,time; signal.signal(signal.SIGTERM, signal.SIG_IGN); print('SW_SEQ: done', flush=True); time.sleep(30)")
        self.assertTrue(phase["done_before_stop"])
        self.assertTrue(phase["terminate_requested"])
        self.assertTrue(phase["kill_requested"])
        self.assertEqual(phase["exit_code"], _KILL_EXIT)
        self.assertEqual(process_failures(phase), [])

    @unittest.skipUnless(os.name == "posix", "Linux signal exit evidence")
    def test_actual_abort_after_done_remains_failure(self) -> None:
        phase = self.phase("import os,resource; resource.setrlimit(resource.RLIMIT_CORE,(0,0)); print('SW_SEQ: done', flush=True); os.abort()")
        self.assertEqual(phase["exit_code"], -6)
        self.assertTrue(process_failures(phase))


if __name__ == "__main__":
    unittest.main()
