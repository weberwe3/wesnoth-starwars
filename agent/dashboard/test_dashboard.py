#!/usr/bin/env python3

from __future__ import annotations

import json
import http.client
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "agent" / "coordinator"))

from runtime_status import RuntimeStatus, default_state  # noqa: E402
from coordination_control import ControlStore  # noqa: E402
import recovery_policy  # noqa: E402
sys.path.insert(0, str(ROOT / "agent" / "dashboard"))
from autonomy import AutonomyController, ControlError  # noqa: E402
from approval_queue import ApprovalQueue  # noqa: E402
from server import create_server, public_state  # noqa: E402


class RuntimeStatusTests(unittest.TestCase):
    def test_default_state_has_every_role_and_no_secret_fields(self) -> None:
        state = default_state(ROOT)
        self.assertEqual(
            set(state["workers"]),
            {"coordinator", "implementer", "fast-fix", "validation", "tester", "reviewer", "reviewer-fallback"},
        )
        payload = json.dumps(state).lower()
        self.assertNotIn("api_key", payload)
        self.assertNotIn("token", payload)

    def test_runtime_records_job_handoff_gate_and_result(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "agent" / "runtime" / "state.json"
            status = RuntimeStatus(path)
            status.begin_job(task_id="DASH-TEST", objective="Verify telemetry", branch="agent/dash-test", worktree=Path("/tmp/dash-test"), validation_profile="static-text")
            status.handoff("coordinator", "implementer", "Assigned")
            status.gate("Static checks", "pass", "PASS")
            status.finish(True, "Complete")
            state = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(state["job"]["result"], "PASS")
            self.assertEqual(state["job"]["worktree"], "dash-test")
            self.assertEqual(state["routing_history"][-1]["to"], "implementer")
            self.assertEqual(state["gates"][-1]["state"], "pass")

    def test_runtime_exposes_bounded_recovery_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "agent" / "runtime" / "state.json"
            status = RuntimeStatus(path)
            status.event(
                "Recovery attempt 1 of 2",
                kind="recovery",
                level="warning",
                detail="Static check failed",
                failure_class="implementation_or_validation_failure",
                required_action="Correct the scoped file",
                recovery_attempt=1,
                recovery_limit=2,
            )
            state = public_state(json.loads(path.read_text(encoding="utf-8")))
            event = state["events"][-1]
            self.assertEqual(event["recovery_attempt"], 1)
            self.assertEqual(event["recovery_limit"], 2)
            self.assertEqual(event["required_action"], "Correct the scoped file")

    def test_runtime_can_publish_exact_fallback_assignment(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "agent" / "runtime" / "state.json"
            status = RuntimeStatus(path)
            status.set_assignment("implementer", "OpenAI", "GPT-5.6 Terra · Medium")
            state = public_state(json.loads(path.read_text(encoding="utf-8")))
            self.assertEqual(state["workers"]["implementer"]["provider"], "OpenAI")
            self.assertEqual(state["workers"]["implementer"]["model"], "GPT-5.6 Terra · Medium")

    def test_public_state_drops_unknown_and_marks_stale_running_job(self) -> None:
        state = default_state(ROOT)
        state["secret"] = "must-not-escape"
        state["job"] = {"state": "running", "task_id": "TEST"}
        state["updated_at"] = "2000-01-01T00:00:00+00:00"
        public = public_state(state)
        self.assertNotIn("secret", public)
        self.assertEqual(public["system"]["state"], "stale")

    def test_server_rejects_non_loopback_host_header(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            server = create_server(0, Path(directory) / "state.json")
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                connection = http.client.HTTPConnection("127.0.0.1", server.server_port)
                connection.request("GET", "/healthz", headers={"Host": "attacker.invalid"})
                response = connection.getresponse()
                self.assertEqual(response.status, 400)
                response.read()
                connection.close()
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)


class CoordinationControlTests(unittest.TestCase):
    @staticmethod
    def controller(directory: str) -> AutonomyController:
        base = Path(directory)
        return AutonomyController(
            ROOT,
            ControlStore(base / "control.json"),
            ApprovalQueue(ROOT, base / "approval-queue.json"),
        )

    def test_mode_switch_is_allowlisted_and_persistent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            controller = self.controller(directory)
            controller.set_mode("sol-high")
            public = controller.public_state()
            self.assertEqual(public["mode"], "sol-high")
            self.assertEqual(public["assignment"]["model"], "GPT-5.6 Sol")
            self.assertEqual(public["assignment"]["effort"], "high")
            self.assertTrue(public["capabilities"]["merge"])
            self.assertFalse(public["automation"]["enabled"])
            with self.assertRaises(ControlError):
                controller.set_mode("danger-full-access")

    def test_sol_ticket_cannot_target_protected_paths(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            controller = self.controller(directory)
            proposal = {
                "action": "run_ticket",
                "summary": "Unsafe",
                "impact": "Would modify governance",
                "ticket": {
                    "worker": "implementer",
                    "objective": "Change governance",
                    "allowed_paths": ["docs/AGENT_ORCHESTRATION_FUNCTIONAL_SPEC.md"],
                    "validation_profile": "static-text",
                    "validation_root": None,
                },
            }
            with self.assertRaises(ControlError):
                controller._build_ticket("abc123def456", proposal)

    def test_deterministic_mode_rejects_continuous_automation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            controller = self.controller(directory)
            with self.assertRaises(ControlError):
                controller.set_automation(True, "Continue safely")

    def test_public_queue_drops_private_worktree_identity(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            controller = self.controller(directory)
            state = controller.public_state()
            self.assertEqual(state["approval_queue"], [])
            payload = json.dumps(state).lower()
            self.assertNotIn("api_key", payload)

    def test_recovery_policy_allows_exactly_two_attempts(self) -> None:
        eligible = {"eligible": True}
        self.assertTrue(recovery_policy.can_attempt(0, eligible, True))
        self.assertTrue(recovery_policy.can_attempt(1, eligible, True))
        self.assertFalse(recovery_policy.can_attempt(2, eligible, True))
        self.assertFalse(recovery_policy.can_attempt(0, eligible, False))
        self.assertFalse(recovery_policy.can_attempt(0, {"eligible": False}, True))

    def test_terra_fallback_is_single_and_implementer_only(self) -> None:
        self.assertTrue(recovery_policy.should_use_terra_fallback("implementer", 1, False))
        self.assertFalse(recovery_policy.should_use_terra_fallback("implementer", 1, True))
        self.assertFalse(recovery_policy.should_use_terra_fallback("fast-fix", 1, False))
        self.assertFalse(recovery_policy.should_use_terra_fallback("implementer", 0, False))

    def test_failed_terra_fallback_is_not_recoverable(self) -> None:
        failure = recovery_policy.classify_validation(
            {"scope": {"changed_paths": ["addons/example.cfg"]}, "static": {"checks": []}},
            recovery_policy.TERRA_FALLBACK_FAILURE,
        )
        self.assertEqual(failure["class"], "implementer_fallback_failure")
        self.assertFalse(failure["eligible"])

    def test_repository_hygiene_is_immediate_hard_stop(self) -> None:
        failure = recovery_policy.hard_stop_for_exit(2)
        self.assertEqual(failure["class"], "repository_hygiene")
        self.assertFalse(failure["eligible"])
        self.assertFalse(recovery_policy.can_attempt(0, failure, True))

    def test_scope_violation_never_consumes_recovery_attempt(self) -> None:
        failure = recovery_policy.classify_validation({
            "scope": {"violations": ["AGENTS.md: protected"]},
            "static": {"checks": []},
        }, 0)
        self.assertEqual(failure["class"], "scope_violation")
        self.assertFalse(recovery_policy.can_attempt(0, failure, True))

    def test_failure_diagnostic_redacts_secret_shapes(self) -> None:
        diagnostic = recovery_policy.safe_text(
            "TOKEN=abcdefghijklmnopqrstuvwxyz0123456789ABCDEFGHIJ validator failed",
            "fallback",
        )
        self.assertNotIn("abcdefghijklmnopqrstuvwxyz", diagnostic)
        self.assertIn("[redacted]", diagnostic)

    def test_open_pull_request_path_overlap_is_rejected(self) -> None:
        ticket = {"allowed_paths": ["addons/Star_Wars_Thrawn_Trilogy/**"]}
        inventory = {
            "approval_queue": [],
            "open_pull_requests": [{
                "changed_paths": ["addons/Star_Wars_Thrawn_Trilogy/_main.cfg"]
            }],
        }
        with self.assertRaises(ControlError):
            AutonomyController._reject_overlapping_proposal(ticket, inventory)

    def test_control_api_requires_same_origin_token(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            server = create_server(0, base / "state.json", base / "control.json")
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                connection = http.client.HTTPConnection("127.0.0.1", server.server_port)
                connection.request("GET", "/api/control", headers={"Host": f"127.0.0.1:{server.server_port}"})
                response = connection.getresponse()
                control = json.loads(response.read())
                self.assertEqual(response.status, 200)
                connection.request(
                    "POST",
                    "/api/control",
                    body=json.dumps({"action": "set_mode", "mode": "sol-low"}),
                    headers={
                        "Host": f"127.0.0.1:{server.server_port}",
                        "Origin": f"http://127.0.0.1:{server.server_port}",
                        "Content-Type": "application/json",
                        "X-Wesnoth-CSRF": control["csrf_token"],
                    },
                )
                response = connection.getresponse()
                changed = json.loads(response.read())
                self.assertEqual(response.status, 202)
                self.assertEqual(changed["mode"], "sol-low")
                connection.request(
                    "POST",
                    "/api/control",
                    body=json.dumps({"action": "set_mode", "mode": "sol-high"}),
                    headers={
                        "Host": f"127.0.0.1:{server.server_port}",
                        "Origin": "http://attacker.invalid",
                        "Content-Type": "application/json",
                    },
                )
                response = connection.getresponse()
                self.assertEqual(response.status, 403)
                response.read()
                connection.close()
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)


class ApprovalQueueTests(unittest.TestCase):
    @staticmethod
    def git(cwd: Path, *args: str) -> str:
        completed = subprocess.run(
            ["git", *args], cwd=cwd, text=True, check=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        return completed.stdout.strip()

    def test_deletion_pauses_before_commit_and_binds_exact_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            root = base / "project"
            worktrees = base / "project-worktrees"
            root.mkdir()
            self.git(root, "init", "-b", "main")
            self.git(root, "config", "user.email", "test@example.invalid")
            self.git(root, "config", "user.name", "Dashboard Test")
            tracked = root / "obsolete.txt"
            tracked.write_text("old\n", encoding="utf-8")
            self.git(root, "add", "obsolete.txt")
            self.git(root, "commit", "-m", "fixture")
            worktree = worktrees / "delete-ticket"
            self.git(root, "worktree", "add", "-b", "agent/delete-ticket", str(worktree), "main")
            (worktree / "obsolete.txt").unlink()
            queue = ApprovalQueue(root)
            result = {
                "task_id": "DELETE-TEST", "branch": "agent/delete-ticket",
                "worktree": str(worktree), "final_verdict": "PASS",
                "reviewer_used": "reviewer",
                "validation": {"scope": {"changed_paths": ["obsolete.txt"]}},
            }
            self.assertEqual(queue._changes(worktree), (["obsolete.txt"], ["obsolete.txt"]))
            record = queue.add_passed_ticket(
                result, {"task_id": "DELETE-TEST", "objective": "Remove obsolete file"},
                summary="Remove obsolete file", impact="The obsolete fixture is removed.",
            )
            self.assertEqual(record["state"], "deletion_pending")
            self.assertEqual(self.git(worktree, "rev-parse", "HEAD"), record["base_sha"])
            request = json.loads((root / "agent/runtime/deletion-approval-request.json").read_text())
            self.assertEqual(request["deleted_paths"], ["obsolete.txt"])
            self.assertEqual(len(request["manifest_digest"]), 64)


if __name__ == "__main__":
    unittest.main()
