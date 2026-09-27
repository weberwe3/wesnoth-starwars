"""Focused freshness controls for the production evidence envelope."""

from __future__ import annotations

import copy
import hashlib
from pathlib import Path
import tempfile
import unittest

from evidence import EvidenceError, SCHEMA_ID, assess_freshness, validate_envelope


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class EvidenceSelfTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="sw-evidence-test-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.paths = ["addons/a.cfg", "utils/shared.cfg", "production/harness.py"]
        for rel in self.paths:
            path = self.root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes((rel + " v1\n").encode())
        self.artifact = self.root / "agent/runtime/run.json"
        self.artifact.parent.mkdir(parents=True)
        self.artifact.write_bytes(b'{"exit_code": 8, "result": "victory"}\n')
        self.engine = self.root / "engine.exe"
        self.engine.write_bytes(b"installed engine v1")
        self.requirement = {
            "id": "sw-beacon-victory", "revision_sha256": "a" * 64,
            "scenario_id": "sw_21_restore_the_beacon", "probe_id": "sw-beacon-route",
            "exercise_type": "engine-player-moves", "difficulty": "test-mode",
            "seed": "not-applicable", "expected_exit_code": 8,
            "dependency_paths": list(self.paths),
        }
        self.envelope = {
            "schema_id": SCHEMA_ID, "schema_version": 1,
            "requirement_id": self.requirement["id"],
            "requirement_revision_sha256": self.requirement["revision_sha256"],
            "candidate_commit": "b" * 40, "candidate_tree": "c" * 40,
            "scenario_id": self.requirement["scenario_id"],
            "probe_id": self.requirement["probe_id"],
            "exercise_type": self.requirement["exercise_type"],
            "difficulty": self.requirement["difficulty"],
            "seed": self.requirement["seed"],
            "engine_version": "1.19.27", "engine_sha256": digest(self.engine),
            "dependencies": [{"path": rel, "sha256": digest(self.root / rel)}
                             for rel in self.paths],
            "artifact_path": "agent/runtime/run.json",
            "artifact_sha256": digest(self.artifact),
            "exit_code": 8, "outcome": "pass", "observations": ["engine victory"],
        }

    def assess(self, envelope=None, requirement=None):
        return assess_freshness(self.root, self.envelope if envelope is None else envelope,
                                self.requirement if requirement is None else requirement,
                                self.engine)

    def test_exact_inputs_current_and_unrelated_doc_ignored(self) -> None:
        self.assertEqual(self.assess(), {"freshness": "current", "reasons": [],
                                         "result_matches": True})
        (self.root / "README.md").write_text("unrelated documentation\n")
        self.assertEqual(self.assess()["freshness"], "current")

    def test_shared_source_change_stales_evidence(self) -> None:
        (self.root / "utils/shared.cfg").write_text("changed shared rule\n")
        result = self.assess()
        self.assertEqual(result["freshness"], "stale")
        self.assertIn("changed dependency: utils/shared.cfg", result["reasons"])
        self.assertFalse(result["result_matches"])

    def test_harness_engine_and_artifact_changes_stale(self) -> None:
        (self.root / "production/harness.py").write_text("changed harness\n")
        self.engine.write_bytes(b"new engine binary")
        self.artifact.write_bytes(b"changed run")
        result = self.assess()
        self.assertEqual(result["freshness"], "stale")
        self.assertIn("changed dependency: production/harness.py", result["reasons"])
        self.assertIn("engine binary changed", result["reasons"])
        self.assertIn("raw artifact changed", result["reasons"])

    def test_requirement_revision_and_unknown_dependency_stale(self) -> None:
        requirement = copy.deepcopy(self.requirement)
        requirement["revision_sha256"] = "d" * 64
        requirement["dependency_paths"].append("utils/new-shared.cfg")
        result = self.assess(requirement=requirement)
        self.assertEqual(result["freshness"], "stale")
        self.assertIn("changed requirement_revision_sha256", result["reasons"])
        self.assertIn("dependency set changed or incomplete", result["reasons"])

    def test_missing_evidence_and_missing_artifact(self) -> None:
        self.assertEqual(assess_freshness(self.root, None, self.requirement,
                                          self.engine)["freshness"], "missing")
        self.artifact.unlink()
        self.assertIn("raw artifact unavailable", self.assess()["reasons"])

    def test_failed_outcome_cannot_match_accepted_exit(self) -> None:
        envelope = copy.deepcopy(self.envelope)
        envelope["outcome"] = "fail"
        result = self.assess(envelope=envelope)
        self.assertEqual(result["freshness"], "current")
        self.assertFalse(result["result_matches"])

    def test_unsafe_or_duplicate_dependencies_rejected(self) -> None:
        envelope = copy.deepcopy(self.envelope)
        envelope["dependencies"].append(copy.deepcopy(envelope["dependencies"][0]))
        with self.assertRaises(EvidenceError):
            validate_envelope(envelope)
        envelope["dependencies"][-1]["path"] = "../secret"
        with self.assertRaises(EvidenceError):
            validate_envelope(envelope)

    def test_bad_requirement_type_is_invalid_not_exception(self) -> None:
        requirement = copy.deepcopy(self.requirement)
        requirement["dependency_paths"].append({"path": "bad"})
        self.assertEqual(self.assess(requirement=requirement)["freshness"], "invalid")


if __name__ == "__main__":
    unittest.main()
