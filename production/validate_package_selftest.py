"""Package validation uses only copied, hash-matched candidate bytes."""

import hashlib
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest import mock

from validate_package import validate_packaged_candidate


class PackageValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.candidate = self.root / "candidate"
        addon = self.candidate / "addon"
        addon.mkdir(parents=True)
        blob = b"[campaign]\nid=sw_fixture\n[/campaign]\n"
        (addon / "_main.cfg").write_bytes(blob)
        self.engine = self.root / "wesnoth.exe"
        self.engine.write_bytes(b"fixture engine")
        self.manifest = {
            "build_id": "a" * 40, "source_commit": "a" * 40,
            "source_tree": "b" * 40, "package_sha256": "c" * 64,
            "files": [{"path": "_main.cfg", "bytes": len(blob),
                       "sha256": hashlib.sha256(blob).hexdigest()}],
        }

    def test_matching_package_runs_existing_engine_gates(self) -> None:
        with (mock.patch("validate_package.verify_candidate", return_value=self.manifest) as verify,
              mock.patch("validate_package.validate_engine_002", return_value={"pass": True}) as preprocess,
              mock.patch("validate_package.probe_sequence_load", return_value={"pass": True}) as sequence,
              mock.patch("validate_package.probe_extraction_route", return_value={"pass": True}) as route,
              mock.patch("validate_package.probe_interception_route", return_value={"pass": True}) as interception,
              mock.patch("validate_package.probe_convoy_route", return_value={"pass": True}) as convoy,
              mock.patch("validate_package.runtime_scenario_probes", return_value={"pass": True}) as runtime):
            result = validate_packaged_candidate(self.root, self.candidate, self.engine)
        self.assertTrue(result["pass"])
        self.assertTrue(result["package_copy_matches"])
        self.assertEqual(verify.call_count, 2)
        self.assertEqual(preprocess.call_count, 1)
        self.assertEqual(sequence.call_count, 1)
        self.assertEqual(route.call_count, 1)
        self.assertEqual(interception.call_count, 1)
        self.assertEqual(runtime.call_count, 1)

    def test_copy_mutation_stops_before_engine(self) -> None:
        real_copytree = shutil.copytree

        def altered_copy(source, target):
            output = real_copytree(source, target)
            (output / "_main.cfg").write_text("altered", encoding="utf-8")
            return output

        with (mock.patch("validate_package.verify_candidate", return_value=self.manifest),
              mock.patch("validate_package.shutil.copytree", side_effect=altered_copy),
              mock.patch("validate_package.validate_engine_002") as preprocess):
            result = validate_packaged_candidate(self.root, self.candidate, self.engine)
        self.assertFalse(result["pass"])
        preprocess.assert_not_called()

    def test_failed_preprocess_does_not_run_gui_probe(self) -> None:
        with (mock.patch("validate_package.verify_candidate", return_value=self.manifest),
              mock.patch("validate_package.validate_engine_002", return_value={"pass": False}),
              mock.patch("validate_package.probe_sequence_load") as sequence,
              mock.patch("validate_package.probe_extraction_route") as route,
              mock.patch("validate_package.probe_interception_route") as interception,
              mock.patch("validate_package.runtime_scenario_probes") as runtime):
            result = validate_packaged_candidate(self.root, self.candidate, self.engine)
        self.assertFalse(result["pass"])
        sequence.assert_not_called()
        route.assert_not_called()
        interception.assert_not_called()
        runtime.assert_not_called()

    def test_failed_packaged_first_move_blocks_gui_and_promotion(self) -> None:
        with (mock.patch("validate_package.verify_candidate", return_value=self.manifest),
              mock.patch("validate_package.validate_engine_002", return_value={"pass": True}),
              mock.patch("validate_package.probe_sequence_load", return_value={"pass": False}),
              mock.patch("validate_package.probe_extraction_route") as route,
              mock.patch("validate_package.probe_interception_route") as interception,
              mock.patch("validate_package.runtime_scenario_probes") as runtime):
            result = validate_packaged_candidate(self.root, self.candidate, self.engine)
        self.assertFalse(result["pass"])
        self.assertEqual(result["sequence_first_moves"], {"pass": False})
        route.assert_not_called()
        interception.assert_not_called()
        runtime.assert_not_called()

    def test_failed_packaged_objective_route_blocks_gui_and_promotion(self) -> None:
        with (mock.patch("validate_package.verify_candidate", return_value=self.manifest),
              mock.patch("validate_package.validate_engine_002", return_value={"pass": True}),
              mock.patch("validate_package.probe_sequence_load", return_value={"pass": True}),
              mock.patch("validate_package.probe_extraction_route", return_value={"pass": False}),
              mock.patch("validate_package.probe_interception_route") as interception,
              mock.patch("validate_package.runtime_scenario_probes") as runtime):
            result = validate_packaged_candidate(self.root, self.candidate, self.engine)
        self.assertFalse(result["pass"])
        self.assertEqual(result["extraction_objective_route"], {"pass": False})
        interception.assert_not_called()
        runtime.assert_not_called()

    def test_failed_interception_route_blocks_gui_and_promotion(self) -> None:
        with (mock.patch("validate_package.verify_candidate", return_value=self.manifest),
              mock.patch("validate_package.validate_engine_002", return_value={"pass": True}),
              mock.patch("validate_package.probe_sequence_load", return_value={"pass": True}),
              mock.patch("validate_package.probe_extraction_route", return_value={"pass": True}),
              mock.patch("validate_package.probe_interception_route", return_value={"pass": False}),
              mock.patch("validate_package.runtime_scenario_probes") as runtime):
            result = validate_packaged_candidate(self.root, self.candidate, self.engine)
        self.assertFalse(result["pass"])
        self.assertEqual(result["interception_objective_route"], {"pass": False})
        runtime.assert_not_called()


if __name__ == "__main__":
    unittest.main()
