#!/usr/bin/env python3
"""Focused planning-gate controls; no Wesnoth process is started."""

from __future__ import annotations

import unittest
import json
import tempfile
from pathlib import Path

from engine_compatibility import AREA_SOURCES, TARGET_ENGINE, validate_review
import ticket_runner


GAME_PATH = ["addons/Star_Wars_Thrawn_Trilogy/scenarios/03_ground_extraction.cfg"]


def review() -> dict:
    return {
        "schema_version": 1,
        "target_engine": TARGET_ENGINE,
        "areas": {
            area: {
                "disposition": "not_affected",
                "constraint": "This design does not change this engine area.",
                "design": None,
                "precode_check": None,
                "runtime_check": None,
            }
            for area in AREA_SOURCES
        },
    }


def checked(entry: dict) -> None:
    entry.update({
        "disposition": "checked",
        "constraint": "Scenario objective must be implemented by an event, not display text.",
        "design": "Keep the terminal action in the moving unit's event.",
        "precode_check": "Inspect the event filter and the objective coordinate in source.",
        "runtime_check": "Run a legal nonterminal and terminal move in the engine fixture.",
    })


class CompatibilityReviewTests(unittest.TestCase):
    def test_scenario_plan_requires_its_design_area(self) -> None:
        candidate = review()
        with self.assertRaisesRegex(ValueError, "scenario_objectives must be checked"):
            validate_review(candidate, required=True, paths=GAME_PATH)
        checked(candidate["areas"]["scenario_objectives"])
        self.assertEqual(validate_review(candidate, required=True, paths=GAME_PATH), candidate)

    def test_missing_area_and_empty_check_fail_before_coding(self) -> None:
        candidate = review()
        candidate["areas"].pop("events_state")
        with self.assertRaisesRegex(ValueError, "every design area"):
            validate_review(candidate, required=True, paths=GAME_PATH)
        candidate = review()
        checked(candidate["areas"]["scenario_objectives"])
        candidate["areas"]["scenario_objectives"]["precode_check"] = ""
        with self.assertRaisesRegex(ValueError, "precode_check"):
            validate_review(candidate, required=True, paths=GAME_PATH)

    def test_experiment_stops_automatic_dispatch(self) -> None:
        candidate = review()
        checked(candidate["areas"]["scenario_objectives"])
        candidate["areas"]["scenario_objectives"]["disposition"] = "experiment"
        with self.assertRaisesRegex(ValueError, "separate engine spike"):
            validate_review(candidate, required=True, paths=GAME_PATH)

    def test_non_game_ticket_may_omit_review(self) -> None:
        self.assertIsNone(validate_review(None, required=False, paths=["docs/README.md"]))
        with self.assertRaisesRegex(ValueError, "lacks a pre-code"):
            validate_review(None, required=True, paths=GAME_PATH)

    def test_ticket_loader_enforces_plan_before_game_code(self) -> None:
        ticket = {
            "task_id": "TEST-COMPATIBILITY",
            "worker": "implementer",
            "objective": "Change the extraction objective",
            "allowed_paths": GAME_PATH,
            "validation_profile": "wesnoth-addon-static",
            "validation_root": "addons/Star_Wars_Thrawn_Trilogy",
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ticket.json"
            path.write_text(json.dumps(ticket), encoding="utf-8")
            with self.assertRaisesRegex(SystemExit, "lacks a pre-code"):
                ticket_runner.load_ticket(path)
            candidate = review()
            checked(candidate["areas"]["scenario_objectives"])
            ticket["compatibility_review"] = candidate
            path.write_text(json.dumps(ticket), encoding="utf-8")
            self.assertEqual(ticket_runner.load_ticket(path)["compatibility_review"], candidate)


if __name__ == "__main__":
    unittest.main()
