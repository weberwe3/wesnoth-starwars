"""The direct runner accepts only both exact engine observations."""

import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from requirement_runner import RequirementRunError, SPEC_PATH, execute_requirement


class RequirementRunnerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        source_spec = Path(__file__).resolve().parent / "requirements/restore_beacon_objective.json"
        spec = self.root / SPEC_PATH
        spec.parent.mkdir(parents=True)
        spec.write_bytes(source_spec.read_bytes())
        source = self.root / "addons/Star_Wars_Thrawn_Trilogy/scenarios/fixture.cfg"
        source.parent.mkdir(parents=True)
        source.write_text("[scenario]\nid=sw_fixture\n[/scenario]\n", encoding="utf-8")
        inventory = self.root / "production/source_inventory.json"
        inventory.write_text(json.dumps({"source_files": [{"path": source.relative_to(self.root).as_posix()}]}), encoding="utf-8")
        for rel in ("production/evidence.py", "production/mission_probe.py",
                    "production/requirement_runner.py", "production/inventory.py",
                    "production/contract_store.py"):
            (self.root / rel).write_text(rel, encoding="utf-8")
        self.engine = self.root / "wesnoth.exe"
        self.engine.write_bytes(b"fixture engine")
        self.raw = {
            "pass": True, "engine_version": "1.19.27",
            "legal_objective_victory": "observed_with_enemy_turn_disabled_and_terminal_dialogue_suppressed",
            "wrong_unit_rejection": "observed_with_commander_start_staged",
            "results": [
                {"case": "path_to_beacon", "test_id": "sw_probe_restore_beacon_path_to_beacon",
                 "log_verdict": "victory", "exit_code": 8, "meets_expectation": True},
                {"case": "wrong_unit_terminal", "test_id": "sw_probe_restore_beacon_wrong_unit_terminal",
                 "log_verdict": "pass", "exit_code": 0, "meets_expectation": True},
            ],
        }

    def run_fixture(self, raw=None):
        with (mock.patch("requirement_runner.check_inventory"),
              mock.patch("requirement_runner._git", side_effect=["a" * 40, "b" * 40, ""]),
              mock.patch("requirement_runner.run_probe", return_value=self.raw if raw is None else raw)):
            return execute_requirement(self.root, self.engine)

    def test_positive_and_negative_engine_cases_yield_scoped_observation(self) -> None:
        result = self.run_fixture()
        self.assertTrue(result["pass"])
        self.assertEqual(result["freshness"]["freshness"], "current")
        envelope = json.loads((self.root / "agent/runtime/requirements/restore-beacon-objective-envelope.json").read_text())
        self.assertEqual(envelope["outcome"], "pass")
        self.assertEqual(envelope["candidate_commit"], "a" * 40)

    def test_wrong_unit_victory_does_not_pass(self) -> None:
        raw = copy.deepcopy(self.raw)
        raw["results"][1]["log_verdict"] = "victory"
        result = self.run_fixture(raw)
        self.assertFalse(result["pass"])
        self.assertFalse(result["freshness"]["result_matches"])

    def test_missing_engine_version_does_not_pass(self) -> None:
        raw = copy.deepcopy(self.raw)
        raw["engine_version"] = None
        self.assertFalse(self.run_fixture(raw)["pass"])

    def test_source_change_stales_persisted_observation(self) -> None:
        self.run_fixture()
        source = self.root / "addons/Star_Wars_Thrawn_Trilogy/scenarios/fixture.cfg"
        source.write_text("changed", encoding="utf-8")
        from evidence import assess_freshness
        from requirement_runner import accepted_requirement
        envelope = json.loads((self.root / "agent/runtime/requirements/restore-beacon-objective-envelope.json").read_text())
        result = assess_freshness(self.root, envelope, accepted_requirement(self.root), self.engine)
        self.assertEqual(result["freshness"], "stale")

    def test_unsupported_requirement_cases_fail_closed(self) -> None:
        spec = self.root / SPEC_PATH
        payload = json.loads(spec.read_text())
        payload["negative_case"] = "none"
        spec.write_text(json.dumps(payload), encoding="utf-8")
        with self.assertRaisesRegex(RequirementRunError, "unsupported"):
            self.run_fixture()


if __name__ == "__main__":
    unittest.main()
