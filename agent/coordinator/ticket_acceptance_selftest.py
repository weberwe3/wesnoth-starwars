#!/usr/bin/env python3

"""Regression tests for baseline-aware ticket acceptance evidence."""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path
import unittest

from ticket_acceptance import validate_acceptance_contract, validate_ticket_acceptance


SCENARIO = "addons/Star_Wars_Thrawn_Trilogy/scenarios/01_first_battle.cfg"
MAP = "addons/Star_Wars_Thrawn_Trilogy/maps/first.map"


def _run(root: Path, *args: str) -> None:
    completed = subprocess.run(["git", *args], cwd=root, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if completed.returncode:
        raise RuntimeError(completed.stderr)


def _output(root: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=root, stdout=subprocess.PIPE, check=True, text=True).stdout.strip()


class TicketAcceptanceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        scenario = self.root / SCENARIO
        scenario.parent.mkdir(parents=True)
        scenario.write_text("[scenario]\n    id=sw_first_battle\n[/scenario]\n", encoding="utf-8")
        game_map = self.root / MAP
        game_map.parent.mkdir(parents=True)
        game_map.write_text("Gg,Gg\nGg,Gg\n", encoding="utf-8")
        _run(self.root, "init")
        _run(self.root, "branch", "-M", "main")
        _run(self.root, "add", ".")
        _run(self.root, "-c", "user.name=Acceptance Test", "-c", "user.email=test@example.invalid", "commit", "-m", "base")
        self.base_sha = _output(self.root, "rev-parse", "HEAD")
        _run(self.root, "checkout", "-b", "agent/acceptance-test")

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def ticket(self, claim: dict) -> dict:
        return {
            "validation_profile": "wesnoth-addon-static",
            "allowed_paths": ["addons/Star_Wars_Thrawn_Trilogy/scenarios/**", "addons/Star_Wars_Thrawn_Trilogy/maps/**"],
            "base_sha": self.base_sha,
            "acceptance": {"schema_version": 1, "claims": [claim]},
        }

    def test_unit_claim_requires_the_promised_placement_not_a_note(self) -> None:
        Path(self.root / SCENARIO).write_text(
            "[scenario]\n    id=sw_first_battle\n    [note]\n        description=Only a note\n    [/note]\n[/scenario]\n",
            encoding="utf-8",
        )
        result = validate_ticket_acceptance(self.root, self.ticket({
            "kind": "unit_placement", "path": SCENARIO, "base": "absent",
            "unit_type": "sw_unit_nr_heavy_weapons", "instance_id": "sw_nr_heavy_weapons_alpha",
            "side": 1, "x": 6, "y": 6,
        }))
        self.assertFalse(result["pass"])
        self.assertIn("missing from the candidate", result["diagnostic"])

    def test_unit_claim_passes_only_after_the_exact_unit_is_added(self) -> None:
        Path(self.root / SCENARIO).write_text(
            "[scenario]\n    id=sw_first_battle\n    [unit]\n        type=sw_unit_nr_heavy_weapons\n        id=sw_nr_heavy_weapons_alpha\n        side=1\n        x=6\n        y=6\n    [/unit]\n[/scenario]\n",
            encoding="utf-8",
        )
        result = validate_ticket_acceptance(self.root, self.ticket({
            "kind": "unit_placement", "path": SCENARIO, "base": "absent",
            "unit_type": "sw_unit_nr_heavy_weapons", "instance_id": "sw_nr_heavy_weapons_alpha",
            "side": 1, "x": 6, "y": 6,
        }))
        self.assertTrue(result["pass"])
        self.assertEqual(result["checks"][0]["base_present"], False)

    def test_map_cell_claim_compares_the_ticket_base(self) -> None:
        Path(self.root / MAP).write_text("Gg,Gg^Fp\nGg,Gg\n", encoding="utf-8")
        result = validate_ticket_acceptance(self.root, self.ticket({
            "kind": "map_cell", "path": MAP, "base": "absent",
            "row": 1, "column": 2, "terrain": "Gg^Fp",
        }))
        self.assertTrue(result["pass"])

    def test_existing_feature_cannot_be_claimed_as_this_ticket_work(self) -> None:
        Path(self.root / SCENARIO).write_text(
            "[scenario]\n    id=sw_first_battle\n    [unit]\n        type=sw_unit_nr_heavy_weapons\n        id=sw_nr_heavy_weapons_alpha\n        side=1\n        x=6\n        y=6\n    [/unit]\n[/scenario]\n",
            encoding="utf-8",
        )
        _run(self.root, "add", ".")
        _run(self.root, "-c", "user.name=Acceptance Test", "-c", "user.email=test@example.invalid", "commit", "-m", "existing feature")
        self.base_sha = _output(self.root, "rev-parse", "HEAD")
        Path(self.root / SCENARIO).write_text(
            (self.root / SCENARIO).read_text(encoding="utf-8") + "\n# unrelated note\n",
            encoding="utf-8",
        )
        result = validate_ticket_acceptance(self.root, self.ticket({
            "kind": "unit_placement", "path": SCENARIO, "base": "absent",
            "unit_type": "sw_unit_nr_heavy_weapons", "instance_id": "sw_nr_heavy_weapons_alpha",
            "side": 1, "x": 6, "y": 6,
        }))
        self.assertFalse(result["pass"])
        self.assertIn("already satisfied by the ticket base", result["diagnostic"])

    def test_event_evidence_ignores_wml_indentation_but_remains_baseline_aware(self) -> None:
        Path(self.root / SCENARIO).write_text(
            "[scenario]\n    id=sw_first_battle\n[/scenario]\n\n"
            "[event]\n    id=sw_first_battle_eastern_observation\n    name=moveto\n"
            "    [filter_location]\n        x=15\n        y=2\n    [/filter_location]\n[/event]\n",
            encoding="utf-8",
        )
        result = validate_ticket_acceptance(self.root, self.ticket({
            "kind": "event_contains", "path": SCENARIO, "base": "different",
            "event_id": "sw_first_battle_eastern_observation", "contains": "x=15\ny=2",
        }))
        self.assertTrue(result["pass"])
        self.assertFalse(result["checks"][0]["base_present"])

    def test_invalid_contract_fails_closed(self) -> None:
        result = validate_acceptance_contract({"schema_version": 1, "claims": []})
        self.assertFalse(result["pass"])


if __name__ == "__main__":
    unittest.main()
