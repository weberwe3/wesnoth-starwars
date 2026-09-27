"""Admission and negative fixtures for the proposed unattended charter."""

import copy
from datetime import datetime, timezone
import hashlib
from pathlib import Path
import tempfile
import unittest

from charter import CharterError, SCHEMA_ID, _REFS, canonical_digest, validate_charter


NOW = datetime(2026, 9, 27, tzinfo=timezone.utc)
AUTH = "a" * 32


class CharterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        identity = {}
        for key, rel in _REFS.items():
            path = self.root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(key.encode())
            identity[key] = hashlib.sha256(path.read_bytes()).hexdigest()
        self.charter = {
            "schema_id": SCHEMA_ID, "schema_version": 1,
            "milestone_id": "prototype-6A", "required_nodes": ["mission-21"],
            "profile": "playable_prototype", "player_outcome": "Launch the approved sequence",
            "entry_points": ["verified_player_launcher"],
            "allowed_actions": ["development", "governed_publication"],
            "allowed_ticket_classes": ["gameplay", "repair"],
            "allowed_paths": ["addons/Star_Wars_Thrawn_Trilogy/scenarios/**"],
            "protected_inputs": list(_REFS.values()), "asset_sources": ["prepared_original"],
            "creative_defaults": {"dialogue": "original"},
            "limits": {"model_calls": 20, "elapsed_seconds": 3600, "engine_runs": 20,
                       "repair_attempts": 2, "disk_bytes": 100_000_000,
                       "completion_cutoff_model_calls": 14,
                       "completion_reserve_model_calls": 6},
            "authority": {"automation_authorization_id": AUTH,
                          "promotion_approval_id": None,
                          "expires_at": "2026-09-28T00:00:00Z", "revoked": False},
            "capabilities": {"engine": True}, "required_session": "interactive_unlocked",
            "retry_policy": {"max_retries": 2}, "escalation": {"hard_stop": "notify"},
            "notification": {"on_blocker": True}, "identity": identity,
        }

    def assess(self, value=None, *, approval=None, automation=AUTH, promotion=None):
        candidate = self.charter if value is None else value
        return validate_charter(self.root, candidate,
                                accepted_sha256=canonical_digest(candidate) if approval is None else approval,
                                automation_authorization_id=automation,
                                promotion_approval_id=promotion, now=NOW)

    def test_reviewed_current_charter_is_admissible(self) -> None:
        self.assertEqual(self.assess()["milestone_id"], "prototype-6A")

    def test_missing_review_or_changed_reviewed_bytes_is_rejected(self) -> None:
        with self.assertRaisesRegex(CharterError, "approval is absent"):
            self.assess(approval="")
        with self.assertRaisesRegex(CharterError, "digest changed"):
            self.assess(approval="0" * 64)

    def test_stale_reference_and_revocation_are_rejected(self) -> None:
        (self.root / _REFS["scope"]).write_text("changed")
        with self.assertRaisesRegex(CharterError, "stale identity"):
            self.assess()
        (self.root / _REFS["scope"]).write_text("scope")
        changed = copy.deepcopy(self.charter)
        changed["authority"]["revoked"] = True
        with self.assertRaisesRegex(CharterError, "revoked"):
            self.assess(changed)

    def test_expiry_or_changed_live_authorization_is_rejected(self) -> None:
        changed = copy.deepcopy(self.charter)
        changed["authority"]["expires_at"] = "2026-09-27T00:00:00Z"
        with self.assertRaisesRegex(CharterError, "expired"):
            self.assess(changed)
        with self.assertRaisesRegex(CharterError, "authorization"):
            self.assess(automation="b" * 32)

    def test_unsupported_profile_action_and_asset_source_are_rejected(self) -> None:
        for field, value, diagnostic in (
            ("profile", "unreviewed", "profile"),
            ("allowed_actions", ["public_release"], "action"),
            ("asset_sources", ["unknown_provider"], "asset"),
        ):
            changed = copy.deepcopy(self.charter)
            changed[field] = value
            with self.subTest(field=field), self.assertRaisesRegex(CharterError, diagnostic):
                self.assess(changed)

    def test_missing_limits_and_reserve_violation_are_rejected(self) -> None:
        changed = copy.deepcopy(self.charter)
        changed["limits"].pop("engine_runs")
        with self.assertRaisesRegex(CharterError, "limits"):
            self.assess(changed)
        changed = copy.deepcopy(self.charter)
        changed["limits"]["completion_reserve_model_calls"] = 8
        with self.assertRaisesRegex(CharterError, "reserve"):
            self.assess(changed)

    def test_promotion_requires_separate_live_approval(self) -> None:
        changed = copy.deepcopy(self.charter)
        changed["allowed_actions"].append("local_build_promotion")
        changed["authority"]["promotion_approval_id"] = "approved-build-1"
        with self.assertRaisesRegex(CharterError, "promotion approval"):
            self.assess(changed)
        self.assertEqual(self.assess(changed, promotion="approved-build-1"), changed)

    def test_path_escape_and_unresolved_protected_input_are_rejected(self) -> None:
        changed = copy.deepcopy(self.charter)
        changed["allowed_paths"] = ["addons/Star_Wars_Thrawn_Trilogy/../agent/**"]
        with self.assertRaisesRegex(CharterError, "paths"):
            self.assess(changed)
        changed = copy.deepcopy(self.charter)
        changed["protected_inputs"].remove(_REFS["scope"])
        with self.assertRaisesRegex(CharterError, "protected"):
            self.assess(changed)


if __name__ == "__main__":
    unittest.main()
