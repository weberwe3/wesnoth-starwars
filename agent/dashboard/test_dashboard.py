#!/usr/bin/env python3

from __future__ import annotations

import json
import http.client
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "agent" / "coordinator"))

from runtime_status import RuntimeStatus, default_state  # noqa: E402
from coordination_control import ControlStore, VALID_MODES  # noqa: E402
import recovery_policy  # noqa: E402
import model_policy  # noqa: E402
import ticket_runner  # noqa: E402
import worktree_paths  # noqa: E402
sys.path.insert(0, str(ROOT / "agent" / "dashboard"))
from autonomy import (  # noqa: E402
    AutonomyController,
    BACKLOG_SCHEMA,
    ControlError,
    TICKET_SCHEMA,
    validate_strict_output_schema,
)
import approval_queue  # noqa: E402
from approval_queue import ApprovalQueue, QueueError  # noqa: E402
from server import create_server, public_state  # noqa: E402


class RuntimeStatusTests(unittest.TestCase):
    def test_dashboard_launcher_defaults_to_the_secure_native_worktree_root(self) -> None:
        launcher = ROOT / "agent" / "dashboard" / "start-dashboard.sh"
        text = launcher.read_text(encoding="utf-8")
        self.assertIn('WESNOTH_AGENT_WORKTREE_ROOT="/mnt/c/Users/${USER}/Documents/Codex/WesnothAgentWorktrees"', text)
        self.assertIn("export WESNOTH_AGENT_WORKTREE_ROOT", text)

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

    def test_runtime_publishes_the_exact_secret_safe_worker_dispatch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "agent" / "runtime" / "state.json"
            status = RuntimeStatus(path)
            prompt = "OBJECTIVE:\nRepair the scenario\nAPI_KEY=do-not-display"
            status.set_dispatch_prompt("implementer", prompt)
            state = public_state(json.loads(path.read_text(encoding="utf-8")))
            dispatch = state["workers"]["implementer"]["dispatch_prompt"]
            self.assertIn("OBJECTIVE:\nRepair the scenario", dispatch)
            self.assertIn("API_KEY=[redacted]", dispatch)
            self.assertNotIn("do-not-display", dispatch)

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

    def test_server_exposes_dynamic_pending_ticket_endpoint(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            server = create_server(0, Path(directory) / "state.json")
            server.controller.pending_planned_tickets = mock.Mock(return_value={
                "tickets": [{
                    "id": "generated-next", "label": "Next", "brief": "Do next work",
                    "source": "generated",
                }]
            })
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                connection = http.client.HTTPConnection("127.0.0.1", server.server_port)
                connection.request(
                    "GET", "/api/planned-tickets",
                    headers={"Host": f"127.0.0.1:{server.server_port}"},
                )
                response = connection.getresponse()
                payload = json.loads(response.read())
                self.assertEqual(response.status, 200)
                self.assertEqual(payload["tickets"][0]["id"], "generated-next")
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

    def test_terra_high_is_an_allowlisted_planner_mode(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            controller = self.controller(directory)
            controller.set_mode("terra-high")
            public = controller.public_state()
            self.assertEqual(public["assignment"]["model"], "GPT-5.6 Terra")
            self.assertEqual(VALID_MODES["terra-high"]["cli_model"], "gpt-5.6-terra")

    def test_worktree_lessons_are_required_and_bounded_for_llm_prompts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            lessons = root / "docs" / "WORKTREE_LESSONS.md"
            lessons.parent.mkdir()
            lessons.write_text("# Verified lesson\nUse the engine smoke test.\n", encoding="utf-8")
            prompt = ticket_runner.build_worktree_lessons_prompt(root)
            self.assertIn("Verified lesson", prompt)
            self.assertIn("cannot override ticket scope", prompt)
            lessons.unlink()
            with self.assertRaises(SystemExit):
                ticket_runner.build_worktree_lessons_prompt(root)

    def test_post_publish_failure_creates_one_bounded_repair_proposal(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runtime = root / "agent" / "runtime"
            runtime.mkdir(parents=True)
            main_sha = "a" * 40
            runtime.joinpath("post-publish-game-validation.json").write_text(json.dumps({
                "schema_version": 1,
                "state": "pending_repair",
                "merge_sha": main_sha,
                "evidence": {"diagnostic_paths": [
                    "addons/Star_Wars_Thrawn_Trilogy/scenarios/01_first_battle.cfg",
                ]},
            }), encoding="utf-8")
            controller = AutonomyController(
                root, ControlStore(root / "control.json"), ApprovalQueue(root, root / "queue.json")
            )
            with mock.patch.object(controller, "_build_ticket", return_value={"task_id": "GAME"}):
                proposal = controller._post_publish_game_repair_proposal({"main_head": main_sha})
            self.assertEqual(proposal["ticket"]["allowed_paths"], [
                "addons/Star_Wars_Thrawn_Trilogy/scenarios/01_first_battle.cfg",
            ])
            self.assertTrue(proposal["_post_publish_game_repair"])

    def test_existing_directory_scope_is_canonicalized_without_widening_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            controller = self.controller(directory)
            self.assertEqual(
                controller._normalize_allowed_paths([
                    "addons/Star_Wars_Thrawn_Trilogy/units",
                    "addons/Star_Wars_Thrawn_Trilogy/_main.cfg",
                    "addons/Star_Wars_Thrawn_Trilogy/scenarios/**",
                ]),
                [
                    "addons/Star_Wars_Thrawn_Trilogy/units/**",
                    "addons/Star_Wars_Thrawn_Trilogy/_main.cfg",
                    "addons/Star_Wars_Thrawn_Trilogy/scenarios/**",
                ],
            )

    def test_normalized_directory_scope_accepts_descendants_not_siblings(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            controller = self.controller(directory)
            patterns = controller._normalize_allowed_paths([
                "addons/Star_Wars_Thrawn_Trilogy/units"
            ])
            allowed = ticket_runner.validate_scope(
                ["addons/Star_Wars_Thrawn_Trilogy/units/baseline_units.cfg"],
                patterns,
            )
            sibling = ticket_runner.validate_scope(
                ["addons/Star_Wars_Thrawn_Trilogy/scenarios/example.cfg"],
                patterns,
            )
            self.assertTrue(allowed["pass"])
            self.assertFalse(sibling["pass"])

    def test_gameplay_ticket_scope_includes_the_required_contract_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            controller = self.controller(directory)
            scoped = controller._gameplay_contract_scope([
                "addons/Star_Wars_Thrawn_Trilogy/scenarios/01_first_battle.cfg"
            ])
            self.assertIn(
                "addons/Star_Wars_Thrawn_Trilogy/tests/gameplay-contracts.json", scoped
            )

    def test_existing_protected_directory_remains_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            controller = self.controller(directory)
            patterns = controller._normalize_allowed_paths(["agent"])
            self.assertEqual(patterns, ["agent/**"])
            self.assertTrue(
                ticket_runner.pattern_can_touch_protected(patterns[0])
            )

    def test_planner_schema_is_strict_at_every_object_level(self) -> None:
        validate_strict_output_schema(TICKET_SCHEMA)
        ticket_schema = TICKET_SCHEMA["properties"]["ticket"]["anyOf"][1]
        self.assertEqual(
            set(ticket_schema["required"]),
            set(ticket_schema["properties"]),
        )

    def test_planner_schema_preflight_rejects_optional_declared_property(self) -> None:
        invalid = {
            "type": "object",
            "properties": {
                "required_value": {"type": "string"},
                "omitted": {"type": "null"},
            },
            "required": ["required_value"],
        }
        with self.assertRaisesRegex(ControlError, "every property must be required"):
            validate_strict_output_schema(invalid)

    def test_planner_failure_details_are_safe_and_actionable(self) -> None:
        rejected = subprocess.CompletedProcess(
            ["codex"],
            1,
            stdout="",
            stderr=(
                "user prompt mentions quota and SECRET-RAW-DATA\n"
                'ERROR: {"code": "invalid_json_schema"}'
            ),
        )
        detail = AutonomyController._planner_failure_detail(rejected)
        self.assertEqual(
            detail,
            "Sol planner request schema was rejected by the model API",
        )
        self.assertNotIn("SECRET-RAW-DATA", detail)

        unknown = subprocess.CompletedProcess(
            ["codex"],
            17,
            stdout="arbitrary prompt echo",
            stderr="user prompt mentions quota but contains no ERROR record",
        )
        self.assertEqual(
            AutonomyController._planner_failure_detail(unknown),
            "Sol planner process exited without a proposal (code 17)",
        )

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
                controller._build_ticket(
                    "abc123def456", proposal, "Start a fresh ticket"
                )

    def test_ticket_loader_rejects_stale_protected_contract(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ticket.json"
            path.write_text(json.dumps({
                "task_id": "PROTECTED-TEST",
                "worker": "implementer",
                "objective": "Attempt coordinator self-modification",
                "allowed_paths": ["agent/coordinator/ticket_runner.py"],
                "validation_profile": "static-text",
                "validation_root": None,
                "resume_branch": None,
                "resume_pr_number": None,
                "resume_pr_head_sha": None,
                "replace_pr_number": None,
                "replace_pr_head_sha": None,
                "replace_pr_branch": None,
            }), encoding="utf-8")
            with self.assertRaisesRegex(SystemExit, "protected path"):
                ticket_runner.load_ticket(path)
            evidence = ticket_runner.load_ticket(path, allow_protected_evidence=True)
            self.assertEqual(
                evidence["allowed_paths"], ["agent/coordinator/ticket_runner.py"]
            )

    def test_deterministic_mode_rejects_continuous_automation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            controller = self.controller(directory)
            with self.assertRaises(ControlError):
                controller.set_automation(True, "Continue safely")

    def test_planning_guidance_persists_without_changing_automation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            controller = self.controller(directory)
            state = controller.set_guidance("Prioritize player-facing campaign missions.")
            self.assertEqual(
                state["automation"]["guidance"],
                "Prioritize player-facing campaign missions.",
            )
            self.assertFalse(state["automation"]["enabled"])
            self.assertEqual(
                controller._planning_guidance(),
                "Prioritize player-facing campaign missions.",
            )

    def test_planning_guidance_rejects_oversized_input(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            controller = self.controller(directory)
            with self.assertRaisesRegex(ControlError, "at most"):
                controller.set_guidance("x" * 1001)

    def test_no_safe_ticket_pauses_with_visible_reason(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            controller = self.controller(directory)
            controller.store.update(lambda state: state.update({
                "mode": "sol-low",
                "automation": {"enabled": True, "brief": "Continue safely"},
                "run": {
                    "state": "planning", "run_id": "abc123def456",
                    "requested_at": None, "started_at": None, "completed_at": None,
                    "ticket_id": None, "summary": "Planning", "error": None,
                },
            }))
            proposal = {
                "action": "stop",
                "summary": "ENGINE-002 is still open on PR #15.",
                "impact": "Follow-on work must wait.",
                "ticket": None,
            }
            with mock.patch.object(controller, "_plan", return_value=proposal) as planner:
                controller._run("abc123def456", "sol-low", "Continue safely", True)
            planner.assert_called_once_with(
                "abc123def456",
                "sol-low",
                "Continue safely",
                queue_exclude_id=None,
                fresh_start_authorized=True,
            )
            state = controller.public_state()
            self.assertEqual(state["run"]["state"], "paused")
            self.assertEqual(state["run"]["summary"], proposal["summary"])
            self.assertFalse(state["automation"]["enabled"])
            self.assertEqual(state["activity"][-1]["level"], "warning")
            self.assertIn("PR #15", state["activity"][-1]["detail"])

    def test_pr_represented_branches_are_not_local_planning_work(self) -> None:
        represented = AutonomyController._represented_pr_branches([
            {"headRefName": "agent/open-ticket", "state": "OPEN"},
            {"headRefName": "agent/merged-ticket", "state": "MERGED"},
            {"headRefName": "main", "state": "CLOSED"},
        ])
        self.assertEqual(
            represented,
            {"agent/open-ticket", "agent/merged-ticket"},
        )

    def test_fresh_work_requires_explicit_owner_language(self) -> None:
        self.assertFalse(AutonomyController._fresh_start_requested("Continue safely"))
        self.assertTrue(AutonomyController._fresh_start_requested("Start from scratch"))
        self.assertTrue(AutonomyController._fresh_start_requested("Start a fresh ticket"))

    def test_continuous_automation_authorizes_one_fresh_bounded_ticket(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            controller = self.controller(directory)
            proposal = {
                "action": "run_ticket",
                "summary": "Next independent priority",
                "impact": "Advance the documented roadmap",
                "ticket": {
                    "worker": "implementer",
                    "objective": "Implement the next safe bounded priority",
                    "allowed_paths": ["addons/example.cfg"],
                    "validation_profile": "static-text",
                    "validation_root": None,
                    "resume_branch": None,
                    "resume_pr_number": None,
                    "resume_pr_head_sha": None,
                    "replace_pr_number": None,
                    "replace_pr_head_sha": None,
                    "replace_pr_branch": None,
                },
            }
            with self.assertRaises(ControlError):
                controller._build_ticket("abc123def456", proposal, "Continue safely")
            ticket = controller._build_ticket(
                "abc123def456",
                proposal,
                "Continue safely",
                fresh_start_authorized=True,
            )
            self.assertIsNone(ticket["resume_branch"])
            self.assertEqual(ticket["worker"], "implementer")

    def test_continuous_local_pass_publishes_without_a_second_human_click(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "agent" / "runtime").mkdir(parents=True)
            queue = ApprovalQueue(root, root / "agent" / "runtime" / "queue.json")
            controller = AutonomyController(
                root,
                ControlStore(root / "agent" / "runtime" / "control.json"),
                queue,
            )
            run_id = "abc123def456"
            authorization_id = "d" * 32
            controller.store.update(lambda state: state.update({
                "mode": "sol-low",
                "automation": {
                    "enabled": True,
                    "brief": "Continue safely",
                    "authorization_id": authorization_id,
                },
                "run": {
                    "state": "planning", "run_id": run_id,
                    "requested_at": None, "started_at": None, "completed_at": None,
                    "ticket_id": None, "summary": "Planning", "error": None,
                },
            }))
            proposal = {
                "action": "run_ticket", "summary": "Safe ticket",
                "impact": "Bounded fixture impact", "ticket": {},
            }
            ticket = {"task_id": "AUTO-PUBLISH", "replace_pr_number": None}
            queued = {
                "id": "4" * 16, "ticket_id": "AUTO-PUBLISH", "state": "ready",
                "commit_sha": "e" * 40,
            }
            published = {**queued, "state": "published"}
            with (
                mock.patch.object(controller, "_plan", return_value=proposal),
                mock.patch.object(controller, "_build_ticket", return_value=ticket),
                mock.patch.object(controller, "_run_secure_ticket", return_value={"return_code": 0}),
                mock.patch.object(controller, "_load_ticket_result", return_value={"final_verdict": "PASS"}),
                mock.patch.object(ticket_runner, "load_ticket"),
                mock.patch.object(queue, "add_passed_ticket", return_value=queued) as add,
                mock.patch.object(
                    queue, "autonomous_publication_target",
                    return_value={
                        "kind": "record", "id": queued["id"],
                        "commit_sha": queued["commit_sha"],
                    },
                ) as target,
                mock.patch.object(queue, "approve_and_publish", return_value=published) as publish,
            ):
                controller._run(run_id, "sol-low", "Continue safely", True)
            self.assertEqual(
                add.call_args.kwargs["automation_authorization_id"], authorization_id
            )
            target.assert_called_once_with(queued["id"], authorization_id)
            publish.assert_called_once_with(queued["id"], queued["commit_sha"])
            state = controller.public_state()
            self.assertEqual(state["run"]["state"], "published")
            self.assertTrue(state["automation"]["enabled"])
            self.assertNotIn("authorization_id", state["automation"])

    def test_planned_priorities_expose_completion_and_advance_order(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            catalog = root / "agent" / "dashboard" / "static" / "planned-tickets.json"
            catalog.parent.mkdir(parents=True)
            catalog.write_text(json.dumps({"tickets": [
                {"id": "done", "status": "completed", "label": "Done", "brief": "Done"},
                {"id": "next", "status": "pending", "label": "Next", "brief": "Next"},
                {"id": "later", "status": "pending", "label": "Later", "brief": "Later"},
            ]}), encoding="utf-8")
            controller = AutonomyController(
                root,
                ControlStore(root / "control.json"),
                ApprovalQueue(root, root / "approval-queue.json"),
            )
            priorities = controller._planned_priorities([
                {"purpose": "next: completed ticket", "impact": "Validated"}
            ])
            self.assertEqual(
                [(item["id"], item["status"]) for item in priorities],
                [("done", "completed"), ("next", "completed"), ("later", "pending")],
            )

    def test_generated_backlog_schema_is_strict(self) -> None:
        validate_strict_output_schema(BACKLOG_SCHEMA)

    def test_generated_priorities_follow_static_catalog_and_track_completion(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            catalog = root / "agent" / "dashboard" / "static" / "planned-tickets.json"
            catalog.parent.mkdir(parents=True)
            catalog.write_text(json.dumps({"tickets": [{
                "id": "static-done", "status": "completed",
                "label": "Static done", "brief": "Already complete",
            }]}), encoding="utf-8")
            runtime = root / "agent" / "runtime"
            runtime.mkdir()
            runtime.joinpath("generated-planned-tickets.json").write_text(
                json.dumps({"schema_version": 1, "tickets": [
                    {
                        "id": "generated-batch-01",
                        "summary": "generated-batch-01: First",
                        "impact": "First impact",
                        "worker": "implementer",
                        "objective": "generated-batch-01: First objective",
                        "allowed_paths": ["addons/first.cfg"],
                        "validation_profile": "static-text",
                        "validation_root": None,
                    },
                    {
                        "id": "generated-batch-02",
                        "summary": "generated-batch-02: Second",
                        "impact": "Second impact",
                        "worker": "fast-fix",
                        "objective": "generated-batch-02: Second objective",
                        "allowed_paths": ["addons/second.cfg"],
                        "validation_profile": "static-text",
                        "validation_root": None,
                    },
                ]}), encoding="utf-8",
            )
            controller = AutonomyController(
                root,
                ControlStore(root / "control.json"),
                ApprovalQueue(root, root / "approval-queue.json"),
            )
            priorities = controller._planned_priorities([
                {"purpose": "generated-batch-01: First", "impact": "Complete"}
            ])
            self.assertEqual(
                [(item["id"], item["status"], item["source"]) for item in priorities],
                [
                    ("static-done", "completed", "static"),
                    ("generated-batch-01", "completed", "generated"),
                    ("generated-batch-02", "pending", "generated"),
                ],
            )

    def test_pending_planned_tickets_is_a_rolling_uncompleted_list(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            catalog = root / "agent" / "dashboard" / "static" / "planned-tickets.json"
            catalog.parent.mkdir(parents=True)
            catalog.write_text(json.dumps({"tickets": [
                {"id": "done", "status": "completed", "label": "Done", "brief": "Done"},
                {"id": "next", "status": "pending", "label": "Next", "brief": "Next brief"},
            ]}), encoding="utf-8")
            controller = AutonomyController(
                root,
                ControlStore(root / "control.json"),
                ApprovalQueue(root, root / "approval-queue.json"),
            )
            self.assertEqual(controller.pending_planned_tickets(), {"tickets": [{
                "id": "next", "label": "Next", "brief": "Next brief", "source": "static",
            }]})

    def test_browser_polls_dynamic_planned_ticket_endpoint(self) -> None:
        source = (ROOT / "agent" / "dashboard" / "static" / "app.js").read_text(
            encoding="utf-8"
        )
        self.assertIn('fetch("/api/planned-tickets"', source)
        self.assertNotIn('fetch("/planned-tickets.json"', source)

    def test_generated_ticket_selection_uses_no_planner_call(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runtime = root / "agent" / "runtime"
            runtime.mkdir(parents=True)
            source = {
                "id": "generated-batch-02",
                "summary": "generated-batch-02: Second",
                "impact": "Second impact",
                "worker": "fast-fix",
                "objective": "generated-batch-02: Second objective",
                "allowed_paths": ["addons/second.cfg"],
                "validation_profile": "static-text",
                "validation_root": None,
            }
            runtime.joinpath("generated-planned-tickets.json").write_text(
                json.dumps({"schema_version": 1, "tickets": [source]}),
                encoding="utf-8",
            )
            controller = AutonomyController(
                root,
                ControlStore(root / "control.json"),
                ApprovalQueue(root, root / "approval-queue.json"),
            )
            inventory = {"planned_priorities": [{
                "id": source["id"], "status": "pending", "source": "generated",
            }]}
            with (
                mock.patch.object(controller, "_reject_overlapping_proposal") as overlap,
                mock.patch.object(controller, "_build_ticket") as build,
            ):
                proposal = controller._next_generated_priority(inventory)
            self.assertEqual(proposal["summary"], source["summary"])
            self.assertEqual(proposal["ticket"]["worker"], "fast-fix")
            overlap.assert_called_once()
            build.assert_called_once()

    def test_priority_exhaustion_requires_no_pending_ticket(self) -> None:
        self.assertTrue(AutonomyController._priorities_exhausted({
            "planned_priorities": [{"status": "completed"}],
        }))
        self.assertFalse(AutonomyController._priorities_exhausted({
            "planned_priorities": [{"status": "pending"}],
        }))

    def test_refill_uses_one_model_call_and_persists_multiple_tickets(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runtime = root / "agent" / "runtime"
            runtime.mkdir(parents=True)
            controller = AutonomyController(
                root,
                ControlStore(root / "control.json"),
                ApprovalQueue(root, root / "approval-queue.json"),
            )
            response = {
                "action": "refill",
                "summary": "Four-ticket roadmap increment",
                "impact": "Continue bounded autonomous development",
                "tickets": [
                    {
                        "summary": "First ticket", "impact": "First impact",
                        "worker": "implementer", "objective": "First objective",
                        "allowed_paths": ["addons/first.cfg"],
                        "validation_profile": "static-text", "validation_root": None,
                    },
                    {
                        "summary": "Second ticket", "impact": "Second impact",
                        "worker": "fast-fix", "objective": "Second objective",
                        "allowed_paths": ["addons/second.cfg"],
                        "validation_profile": "static-text", "validation_root": None,
                    },
                ],
            }

            def run_planner(command, **_kwargs):
                output = Path(command[command.index("-o") + 1])
                output.write_text(json.dumps(response), encoding="utf-8")
                return subprocess.CompletedProcess(command, 0, "", "")

            def validate_ticket(_run_id, proposal, _brief, **_kwargs):
                return {"task_id": "TEST", **proposal["ticket"]}

            inventory = {
                "main_head": "a" * 40,
                "planned_priorities": [{
                    "id": "old", "status": "completed", "source": "static",
                }],
                "recently_published": [], "approval_queue": [],
                "open_pull_requests": [],
            }
            with (
                mock.patch.object(ticket_runner, "resolve_codex_executable", return_value="/usr/bin/codex"),
                mock.patch("autonomy.subprocess.run", side_effect=run_planner) as planner,
                mock.patch.object(controller, "_reject_overlapping_proposal"),
                mock.patch.object(controller, "_build_ticket", side_effect=validate_ticket),
                mock.patch.object(controller, "_planned_priorities", side_effect=lambda _recent: [
                    {
                        "id": item["id"], "status": "pending", "source": "generated",
                        "label": item["summary"], "brief": item["objective"],
                    }
                    for item in controller._generated_backlog()["tickets"]
                ]),
            ):
                proposal = controller._refill_backlog(
                    "abc123def456", "terra-high", "Continue autonomously", inventory
                )
            saved = controller._generated_backlog()
            self.assertEqual(len(saved["tickets"]), 2)
            self.assertTrue(proposal["summary"].startswith("generated-"))
            self.assertEqual(planner.call_count, 1)
            command = planner.call_args.args[0]
            self.assertEqual(command[command.index("-m") + 1], "gpt-5.6-terra")

    def test_planner_stop_does_not_launch_a_guaranteed_conflicting_refill(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runtime = root / "agent" / "runtime"
            runtime.mkdir(parents=True)
            controller = AutonomyController(
                root,
                ControlStore(runtime / "coordination-control.json"),
                ApprovalQueue(root, runtime / "approval-queue.json"),
            )
            inventory = {
                "main_head": "a" * 40,
                "planned_priorities": [{"id": "mission-1", "status": "pending"}],
                "approval_queue": [{
                    "id": "b" * 16, "state": "failed",
                    "changed_paths": ["addons/Star_Wars_Thrawn_Trilogy/scenarios/01_first_battle.cfg"],
                }],
                "open_pull_requests": [{
                    "number": 108,
                    "changed_paths": ["addons/Star_Wars_Thrawn_Trilogy/scenarios/01_first_battle.cfg"],
                }],
                "recently_published": [], "resumable_local_work": [],
                "resumable_pull_requests": [], "replaceable_pull_requests": [],
                "blocked_local_work": [],
            }
            response = {
                "action": "stop", "summary": "Existing work owns Mission 1",
                "impact": "Resolve PR #108 first", "ticket": None,
            }

            def run_planner(command, **_kwargs):
                output = Path(command[command.index("-o") + 1])
                output.write_text(json.dumps(response), encoding="utf-8")
                return subprocess.CompletedProcess(command, 0, "", "")

            with (
                mock.patch.object(controller, "_planning_inventory", return_value=inventory),
                mock.patch.object(controller, "_historical_gameplay_repair_proposal", return_value=None),
                mock.patch.object(controller, "_post_publish_game_repair_proposal", return_value=None),
                mock.patch.object(ticket_runner, "resolve_codex_executable", return_value="/usr/bin/codex"),
                mock.patch("autonomy.subprocess.run", side_effect=run_planner),
                mock.patch.object(controller, "_refill_backlog") as refill,
            ):
                proposal = controller._plan(
                    "abc123def456", "sol-medium", "Continue", fresh_start_authorized=True
                )
            self.assertEqual(proposal["action"], "stop")
            refill.assert_not_called()

    def test_backlog_generation_exposes_its_bounded_planning_phase(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runtime = root / "agent" / "runtime"
            runtime.mkdir(parents=True)
            store = ControlStore(runtime / "coordination-control.json")
            controller = AutonomyController(
                root, store, ApprovalQueue(root, runtime / "approval-queue.json")
            )
            store.update(lambda state: state.update(run={
                "state": "planning", "run_id": "abc123def456", "summary": "Selecting",
                "requested_at": None, "started_at": None, "completed_at": None,
                "ticket_id": None, "error": None,
            }))
            controller._set_planning_phase(
                "abc123def456", "Sol is generating a four-ticket backlog; bounded to five minutes"
            )
            self.assertIn("five minutes", store.read()["run"]["summary"])

    def test_backlog_timeout_is_reported_as_a_bounded_planning_failure(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runtime = root / "agent" / "runtime"
            runtime.mkdir(parents=True)
            controller = AutonomyController(
                root,
                ControlStore(runtime / "coordination-control.json"),
                ApprovalQueue(root, runtime / "approval-queue.json"),
            )
            inventory = {
                "main_head": "a" * 40, "planned_priorities": [],
                "recently_published": [], "approval_queue": [], "open_pull_requests": [],
            }
            with (
                mock.patch.object(ticket_runner, "resolve_codex_executable", return_value="/usr/bin/codex"),
                mock.patch("autonomy.subprocess.run", side_effect=subprocess.TimeoutExpired("codex", 300)),
            ):
                with self.assertRaisesRegex(ControlError, "five-minute limit"):
                    controller._refill_backlog(
                        "abc123def456", "sol-medium", "Continue", inventory
                    )

    def test_completed_priority_retires_failed_historical_contract(self) -> None:
        self.assertTrue(AutonomyController._contract_matches_completed_priority(
            {"task_id": "ENGINE-002", "objective": "Register campaign"},
            [{"id": "engine-002", "status": "completed"}],
        ))
        self.assertFalse(AutonomyController._contract_matches_completed_priority(
            {"task_id": "ENGINE-003", "objective": "Next work"},
            [{"id": "engine-002", "status": "completed"}],
        ))

    def test_resume_restores_original_ticket_contract(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            controller = self.controller(directory)
            proposal = {
                "action": "run_ticket",
                "summary": "Resume work",
                "impact": "Finish the existing change",
                "_planning_inventory": {
                    "local_agent_branches": [{
                        "name": "agent/interrupted-20260904-120000",
                        "worker": "implementer",
                        "objective": "Original bounded objective",
                        "allowed_paths": ["addons/example.cfg"],
                        "validation_profile": "static-text",
                        "validation_root": None,
                        "changed_paths": ["addons/example.cfg"],
                    }],
                },
                "ticket": {
                    "worker": "fast-fix",
                    "objective": "Broadened model objective",
                    "allowed_paths": ["**"],
                    "validation_profile": "wesnoth-addon-static",
                    "validation_root": "addons",
                    "resume_branch": "agent/interrupted-20260904-120000",
                },
            }
            ticket = controller._build_ticket("abc123def456", proposal)
            self.assertEqual(ticket["worker"], "implementer")
            self.assertEqual(ticket["objective"], "Original bounded objective")
            self.assertEqual(ticket["allowed_paths"], ["addons/example.cfg"])
            self.assertEqual(
                ticket["resume_branch"], "agent/interrupted-20260904-120000"
            )

    def test_open_pr_resume_restores_contract_and_exact_pr_identity(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            controller = self.controller(directory)
            branch = "agent/engine-002-final-20260903-233720"
            head = "09bae2fb65a9e9300e888d1af3755ec7b93c235d"
            proposal = {
                "action": "run_ticket",
                "summary": "Resume ENGINE-002",
                "impact": "Revalidate the existing launchable scenario",
                "_planning_inventory": {
                    "local_agent_branches": [],
                    "resumable_pull_requests": [{
                        "name": branch,
                        "number": 15,
                        "head_sha": head,
                        "worker": "fast-fix",
                        "objective": "Original ENGINE-002 contract",
                        "allowed_paths": ["addons/example.cfg"],
                        "validation_profile": "static-text",
                        "validation_root": None,
                        "changed_paths": ["addons/example.cfg"],
                    }],
                },
                "ticket": {
                    "worker": "implementer",
                    "objective": "Untrusted planner rewrite",
                    "allowed_paths": ["**"],
                    "validation_profile": "wesnoth-addon-static",
                    "validation_root": "addons",
                    "resume_branch": branch,
                    "resume_pr_number": 999,
                    "resume_pr_head_sha": "0" * 40,
                },
            }
            ticket = controller._build_ticket("abc123def456", proposal)
            self.assertEqual(ticket["objective"], "Original ENGINE-002 contract")
            self.assertEqual(ticket["resume_pr_number"], 15)
            self.assertEqual(ticket["resume_pr_head_sha"], head)

    def test_resume_ticket_rejects_partial_pr_identity(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ticket.json"
            path.write_text(json.dumps({
                "task_id": "TEST-PR-RESUME",
                "worker": "implementer",
                "objective": "Resume exact PR",
                "allowed_paths": ["addons/example.cfg"],
                "validation_profile": "static-text",
                "validation_root": None,
                "resume_branch": "agent/example",
                "resume_pr_number": 15,
            }), encoding="utf-8")
            with self.assertRaises(SystemExit):
                ticket_runner.load_ticket(path)

    def test_open_pr_resume_appends_main_without_rewriting_published_head(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            root = parent / "project"
            worktree = parent / "project-worktrees" / "ticket"
            root.mkdir()

            def git(cwd: Path, *args: str) -> str:
                return subprocess.run(
                    ["git", *args], cwd=cwd, check=True, text=True,
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                ).stdout.strip()

            git(root, "init", "-b", "main")
            git(root, "config", "user.email", "tests@example.invalid")
            git(root, "config", "user.name", "Dashboard Tests")
            (root / "base.txt").write_text("base\n", encoding="utf-8")
            git(root, "add", "base.txt")
            git(root, "commit", "-m", "base")
            worktree.parent.mkdir()
            branch = "agent/open-pr"
            git(root, "worktree", "add", "-b", branch, str(worktree), "main")
            (worktree / "feature.txt").write_text("feature\n", encoding="utf-8")
            git(worktree, "add", "feature.txt")
            git(worktree, "commit", "-m", "feature")
            published_head = git(worktree, "rev-parse", "HEAD")
            (root / "main.txt").write_text("new main\n", encoding="utf-8")
            git(root, "add", "main.txt")
            git(root, "commit", "-m", "advance main")

            real_run = subprocess.run

            def dispatch(command, *args, **kwargs):
                if command[0] == "gh":
                    payload = {
                        "number": 15, "state": "OPEN", "headRefName": branch,
                        "headRefOid": published_head, "baseRefName": "main",
                        "isCrossRepository": False,
                    }
                    return subprocess.CompletedProcess(command, 0, json.dumps(payload), "")
                return real_run(command, *args, **kwargs)

            ticket = {
                "resume_branch": branch,
                "resume_pr_number": 15,
                "resume_pr_head_sha": published_head,
            }
            with mock.patch("ticket_runner.subprocess.run", side_effect=dispatch):
                self.assertTrue(
                    ticket_runner.prepare_open_pr_resume(root, worktree, ticket)
                )
            resumed_head = git(worktree, "rev-parse", "HEAD")
            self.assertNotEqual(resumed_head, published_head)
            git(worktree, "merge-base", "--is-ancestor", published_head, resumed_head)
            git(worktree, "merge-base", "--is-ancestor", "main", resumed_head)

    def test_managed_worktree_parser_excludes_external_paths(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            managed = Path(directory).resolve()
            inside = managed / "ticket-one"
            outside = managed.parent / "outside-ticket"
            output = (
                f"worktree {inside}\nbranch refs/heads/agent/ticket-one\n\n"
                f"worktree {outside}\nbranch refs/heads/agent/outside-ticket\n"
            )
            parsed = AutonomyController._managed_worktrees(output, managed)
            self.assertEqual(parsed, {"agent/ticket-one": inside})

    def test_failed_result_remains_resumable_but_pass_does_not(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory) / "project"
            project.mkdir()
            controller = AutonomyController(
                project,
                ControlStore(Path(directory) / "control.json"),
                ApprovalQueue(project, Path(directory) / "approval-queue.json"),
            )
            logs = controller.root / "agent" / "logs"
            branch_stamp = "20260904-120000"
            run = logs / f"INTERRUPTED-1-{branch_stamp}"
            run.mkdir(parents=True)
            ticket = {
                "task_id": "INTERRUPTED-1",
                "worker": "implementer",
                "objective": "Finish bounded work",
                "allowed_paths": ["addons/example.cfg"],
                "validation_profile": "static-text",
                "validation_root": None,
            }
            (run / "ticket.json").write_text(json.dumps(ticket), encoding="utf-8")
            (run / "result.json").write_text(
                json.dumps({"final_verdict": "FAIL"}), encoding="utf-8"
            )
            branch = f"agent/interrupted-1-{branch_stamp}"
            self.assertIn(branch, controller._unfinished_ticket_evidence())
            (run / "result.json").write_text(
                json.dumps({"final_verdict": "PASS"}), encoding="utf-8"
            )
            self.assertNotIn(branch, controller._unfinished_ticket_evidence())

    def test_resume_keeps_committed_and_uncommitted_candidate_changes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            root = parent / "project"
            worktree = parent / "project-worktrees" / "interrupted"
            root.mkdir()

            def git(cwd: Path, *args: str) -> str:
                return subprocess.run(
                    ["git", *args], cwd=cwd, check=True, text=True,
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                ).stdout.strip()

            git(root, "init", "-b", "main")
            git(root, "config", "user.email", "tests@example.invalid")
            git(root, "config", "user.name", "Dashboard Tests")
            (root / "existing.txt").write_text("base\n", encoding="utf-8")
            git(root, "add", "existing.txt")
            git(root, "commit", "-m", "base")
            worktree.parent.mkdir()
            git(
                root, "worktree", "add", "-b", "agent/interrupted",
                str(worktree), "main",
            )
            (worktree / "existing.txt").write_text("partial\n", encoding="utf-8")
            git(worktree, "add", "existing.txt")
            git(worktree, "commit", "-m", "partial implementation")
            (worktree / "uncommitted.txt").write_text("more\n", encoding="utf-8")

            _, paths = ticket_runner.read_git_changes(worktree)
            self.assertEqual(paths, ["existing.txt", "uncommitted.txt"])
            self.assertEqual(
                ticket_runner.resolve_resume_worktree(root, "agent/interrupted"),
                worktree.resolve(),
            )

    def test_clean_exact_contract_worktree_is_safe_to_resume(self) -> None:
        result = ticket_runner.validate_resume_scope([], ["addons/example.cfg"])
        self.assertTrue(result["pass"])
        self.assertEqual(result["state"], "clean")
        self.assertFalse(ticket_runner.validate_scope([], ["addons/example.cfg"])["pass"])

    def test_resume_scope_still_rejects_unsafe_paths(self) -> None:
        protected = ticket_runner.validate_resume_scope(["AGENTS.md"], ["**"])
        outside = ticket_runner.validate_resume_scope(
            ["addons/other.cfg"], ["addons/example.cfg"]
        )
        self.assertFalse(protected["pass"])
        self.assertFalse(outside["pass"])

    def test_clean_local_remnant_advances_to_current_main(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            root = parent / "project"
            worktree = parent / "project-worktrees" / "interrupted"
            root.mkdir()

            def git(cwd: Path, *args: str) -> str:
                return subprocess.run(
                    ["git", *args], cwd=cwd, check=True, text=True,
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                ).stdout.strip()

            git(root, "init", "-b", "main")
            git(root, "config", "user.email", "tests@example.invalid")
            git(root, "config", "user.name", "Dashboard Tests")
            (root / "base.txt").write_text("base\n", encoding="utf-8")
            git(root, "add", "base.txt")
            git(root, "commit", "-m", "base")
            worktree.parent.mkdir()
            git(root, "worktree", "add", "-b", "agent/interrupted", str(worktree), "main")
            (root / "main.txt").write_text("new main\n", encoding="utf-8")
            git(root, "add", "main.txt")
            git(root, "commit", "-m", "advance main")

            self.assertEqual(ticket_runner.read_resume_changes(worktree)[1], [])
            self.assertEqual(ticket_runner.read_git_changes(worktree)[1], ["main.txt"])
            self.assertTrue(ticket_runner.prepare_local_resume(root, worktree))
            self.assertEqual(git(worktree, "rev-parse", "HEAD"), git(root, "rev-parse", "main"))
            self.assertEqual(ticket_runner.read_git_changes(worktree)[1], [])
            self.assertFalse(ticket_runner.prepare_local_resume(root, worktree))

    def test_dirty_outdated_local_remnant_fast_forwards_when_disjoint(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            root = parent / "project"
            worktree = parent / "project-worktrees" / "interrupted"
            root.mkdir()

            def git(cwd: Path, *args: str) -> str:
                return subprocess.run(
                    ["git", *args], cwd=cwd, check=True, text=True,
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                ).stdout.strip()

            git(root, "init", "-b", "main")
            git(root, "config", "user.email", "tests@example.invalid")
            git(root, "config", "user.name", "Dashboard Tests")
            (root / "base.txt").write_text("base\n", encoding="utf-8")
            git(root, "add", "base.txt")
            git(root, "commit", "-m", "base")
            worktree.parent.mkdir()
            git(root, "worktree", "add", "-b", "agent/interrupted", str(worktree), "main")
            (worktree / "partial.txt").write_text("partial\n", encoding="utf-8")
            (root / "main.txt").write_text("new main\n", encoding="utf-8")
            git(root, "add", "main.txt")
            git(root, "commit", "-m", "advance main")
            inspection = ticket_runner.inspect_local_resume_reconciliation(worktree)
            self.assertTrue(inspection["safe"])
            self.assertEqual(inspection["mode"], "dirty-disjoint-fast-forward")
            self.assertTrue(ticket_runner.prepare_local_resume(root, worktree))
            self.assertEqual(git(worktree, "rev-parse", "HEAD"), git(root, "rev-parse", "main"))
            self.assertEqual((worktree / "partial.txt").read_text(), "partial\n")

    def test_dirty_outdated_local_remnant_blocks_overlapping_main_change(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            root = parent / "project"
            worktree = parent / "project-worktrees" / "interrupted"
            root.mkdir()

            def git(cwd: Path, *args: str) -> str:
                return subprocess.run(
                    ["git", *args], cwd=cwd, check=True, text=True,
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                ).stdout.strip()

            git(root, "init", "-b", "main")
            git(root, "config", "user.email", "tests@example.invalid")
            git(root, "config", "user.name", "Dashboard Tests")
            (root / "shared.txt").write_text("base\n", encoding="utf-8")
            git(root, "add", "shared.txt")
            git(root, "commit", "-m", "base")
            worktree.parent.mkdir()
            git(root, "worktree", "add", "-b", "agent/interrupted", str(worktree), "main")
            (worktree / "shared.txt").write_text("unfinished\n", encoding="utf-8")
            (root / "shared.txt").write_text("new main\n", encoding="utf-8")
            git(root, "add", "shared.txt")
            git(root, "commit", "-m", "advance main")
            original_head = git(worktree, "rev-parse", "HEAD")

            inspection = ticket_runner.inspect_local_resume_reconciliation(worktree)
            self.assertFalse(inspection["safe"])
            self.assertEqual(inspection["mode"], "overlap")
            with self.assertRaisesRegex(SystemExit, "overlaps unfinished paths"):
                ticket_runner.prepare_local_resume(root, worktree)
            self.assertEqual(git(worktree, "rev-parse", "HEAD"), original_head)
            self.assertEqual((worktree / "shared.txt").read_text(), "unfinished\n")

    def test_terrain_registry_exposes_authoritative_recruitment_semantics(self) -> None:
        facts = ticket_runner.parse_terrain_registry(
            """
[terrain_type]
    id=human_keep
    string=Kh
    recruit_from=yes
    recruit_onto=yes
[/terrain_type]
[terrain_type]
    id=human_castle
    string=Ch
    recruit_onto=yes
[/terrain_type]
""",
            {"Kh", "Ch", "Kt"},
        )
        self.assertEqual(facts["Kh"]["id"], "human_keep")
        self.assertTrue(facts["Kh"]["recruit_from"])
        self.assertTrue(facts["Ch"]["recruit_onto"])
        self.assertNotIn("Kt", facts)

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

    def test_recovery_planner_failure_keeps_bounded_retry(self) -> None:
        failure = {
            "class": "implementation_or_validation_failure",
            "detail": "no repository change was produced",
            "required_action": "Use one scoped repair attempt.",
            "eligible": True,
        }
        with mock.patch.object(ticket_runner, "plan_recovery", side_effect=ValueError("fixture")) as planner:
            plan, used_fallback = ticket_runner.plan_recovery_or_fallback(
                worktree=Path("."), log_dir=Path("."), ticket={}, failure=failure,
                attempt=1, effort="low", governance_prompt="fixture",
            )
        self.assertTrue(used_fallback)
        planner.assert_not_called()
        self.assertEqual(plan["action"], "repair")
        self.assertEqual(plan["corrective_action"], failure["required_action"])

    def test_compact_validation_evidence_omits_verbose_process_state(self) -> None:
        evidence = ticket_runner.compact_validation_evidence({
            "pass": True,
            "git_status": [{"path": "fixture.txt", "raw": "verbose"}],
            "scope": {"changed_paths": ["fixture.txt"], "violations": []},
            "static": {"checks": [{"name": "utf8:fixture.txt", "pass": True}]},
            "profile": "static-text",
            "profile_result": {"pass": True},
        })
        self.assertNotIn("git_status", evidence)
        self.assertEqual(evidence["changed_paths"], ["fixture.txt"])
        self.assertTrue(evidence["static_checks"][0]["pass"])

    def test_single_verified_remnant_avoids_sol_planning(self) -> None:
        proposal = AutonomyController._single_resume_proposal({
            "resumable_local_work": [{
                "name": "agent/interrupted", "previous_task_id": "ENGINE-TEST",
                "worker": "implementer", "objective": "Continue fixture",
                "allowed_paths": ["fixture.txt"], "validation_profile": "static-text",
                "validation_root": None,
            }],
            "resumable_pull_requests": [],
        })
        self.assertEqual(proposal["action"], "run_ticket")
        self.assertEqual(proposal["ticket"]["resume_branch"], "agent/interrupted")
        self.assertIsNone(proposal["ticket"]["resume_pr_number"])

    def test_equivalent_retries_resume_the_newest_worktree_without_sol(self) -> None:
        contract = {
            "worker": "implementer", "objective": "Continue fixture",
            "allowed_paths": ["fixture.txt"], "validation_profile": "static-text",
            "validation_root": None,
        }
        proposal = AutonomyController._single_resume_proposal({
            "resumable_local_work": [
                {**contract, "name": "agent/retry-20260904-120000", "previous_task_id": "OLD"},
                {**contract, "name": "agent/retry-20260904-130000", "previous_task_id": "NEW"},
            ],
            "resumable_pull_requests": [],
        })
        self.assertEqual(
            proposal["ticket"]["resume_branch"], "agent/retry-20260904-130000"
        )
        self.assertIn("NEW", proposal["summary"])

    def test_blocked_remnant_stops_before_sol_planning(self) -> None:
        proposal = AutonomyController._blocked_resume_proposal({
            "blocked_local_work": [{
                "previous_task_id": "ENGINE-TEST",
                "reason": "Interrupted work contains an out-of-scope path.",
            }],
        })
        self.assertEqual(proposal["action"], "stop")
        self.assertIn("ENGINE-TEST", proposal["summary"])
        self.assertIn("out-of-scope", proposal["impact"])

    def test_blocked_historical_remnant_does_not_hide_safe_resume(self) -> None:
        self.assertIsNone(AutonomyController._blocked_resume_proposal({
            "resumable_local_work": [{"name": "agent/safe"}],
            "blocked_local_work": [{"previous_task_id": "OLD", "reason": "Preserved"}],
        }))

    def test_unchanged_planning_decision_is_cached(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime = Path(directory)
            proposal = {"action": "stop", "summary": "Blocked", "impact": "None", "ticket": None}
            AutonomyController._cache_plan(runtime, "a" * 64, proposal)
            self.assertEqual(
                AutonomyController._cached_plan(runtime, "a" * 64),
                proposal,
            )
            self.assertIsNone(AutonomyController._cached_plan(runtime, "b" * 64))

    def test_luna_light_fallback_is_single_for_every_model_worker(self) -> None:
        for worker in ("implementer", "fast-fix", "tester", "reviewer"):
            self.assertTrue(recovery_policy.should_use_luna_light_fallback(worker, 1, False))
            self.assertFalse(recovery_policy.should_use_luna_light_fallback(worker, 1, True))
        self.assertFalse(recovery_policy.should_use_luna_light_fallback("coordinator", 1, False))
        self.assertFalse(recovery_policy.should_use_luna_light_fallback("validation", 1, False))
        self.assertFalse(recovery_policy.should_use_luna_light_fallback("implementer", 0, False))

    def test_terra_fallback_accepts_low_reasoning_for_fast_fix(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            log = Path(directory) / "terra-light.txt"
            completed = subprocess.CompletedProcess(
                [], 0, stdout=(
                    "approval: on-request\nsandbox: read-only\ncandidate returned\n"
                )
            )
            with (
                mock.patch.object(
                    ticket_runner, "resolve_codex_executable", return_value="/opt/codex"
                ),
                mock.patch("ticket_runner.subprocess.run", return_value=completed) as run,
            ):
                code, _ = ticket_runner.invoke_terra(
                    worktree=Path(directory), prompt="fixture", log_file=log,
                    sandbox="workspace-write", timeout=300, reasoning_effort="low",
                )
            self.assertEqual(code, 0)
            self.assertIn('model_reasoning_effort="low"', run.call_args.args[0])
            self.assertIn("--approve-for-me", run.call_args.args[0])
            self.assertNotIn("-s", run.call_args.args[0])

    def test_terra_accepts_codex_auto_review_base_sandbox_header(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            log = Path(directory) / "terra-auto-review.txt"
            completed = subprocess.CompletedProcess(
                [], 0, stdout=(
                    "approval: on-request\nsandbox: read-only\npatch: completed\n"
                )
            )
            with (
                mock.patch.object(
                    ticket_runner, "resolve_codex_executable", return_value="/opt/codex"
                ),
                mock.patch("ticket_runner.subprocess.run", return_value=completed),
            ):
                code, _ = ticket_runner.invoke_terra(
                    worktree=Path(directory), prompt="fixture", log_file=log,
                    sandbox="workspace-write", timeout=300,
                )
            self.assertEqual(code, 0)

    def test_terra_write_fallback_rejects_silent_read_only_downgrade(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            log = Path(directory) / "terra-read-only.txt"
            completed = subprocess.CompletedProcess(
                [], 0, stdout="sandbox: read-only\nNo files changed.\n"
            )
            with (
                mock.patch.object(
                    ticket_runner, "resolve_codex_executable", return_value="/opt/codex"
                ),
                mock.patch("ticket_runner.subprocess.run", return_value=completed),
            ):
                code, _ = ticket_runner.invoke_terra(
                    worktree=Path(directory), prompt="fixture", log_file=log,
                    sandbox="workspace-write", timeout=300, reasoning_effort="low",
                )
            self.assertEqual(code, recovery_policy.CODEX_WRITE_SANDBOX_UNAVAILABLE)
            failure = recovery_policy.classify_implementer_fallback(
                "primary failed", 1, "sandbox: read-only", code, "Terra Light"
            )
            self.assertEqual(failure["class"], "implementer_fallback_unavailable")
            self.assertFalse(failure["eligible"])
            self.assertIn("read-only sandbox", failure["detail"])

    def test_terra_write_fallback_requires_sandbox_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            log = Path(directory) / "terra-missing-header.txt"
            completed = subprocess.CompletedProcess([], 0, stdout="No files changed.\n")
            with (
                mock.patch.object(
                    ticket_runner, "resolve_codex_executable", return_value="/opt/codex"
                ),
                mock.patch("ticket_runner.subprocess.run", return_value=completed),
            ):
                code, _ = ticket_runner.invoke_terra(
                    worktree=Path(directory), prompt="fixture", log_file=log,
                    sandbox="workspace-write", timeout=300,
                )
            self.assertEqual(code, recovery_policy.CODEX_WRITE_SANDBOX_UNAVAILABLE)

    def test_windows_codex_refuses_unc_write_workspace_before_launch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            log = Path(directory) / "terra-unc.txt"
            with (
                mock.patch.object(
                    ticket_runner,
                    "resolve_codex_executable",
                    return_value="C:\\Codex\\codex.exe",
                ),
                mock.patch.object(
                    ticket_runner,
                    "_codex_path",
                    return_value=r"\\wsl.localhost\Ubuntu-24.04\home\fixture\ticket",
                ),
                mock.patch("ticket_runner.subprocess.run") as run,
            ):
                code, output = ticket_runner.invoke_terra(
                    worktree=Path(directory), prompt="fixture", log_file=log,
                    sandbox="workspace-write", timeout=300,
                )
            self.assertEqual(code, recovery_policy.CODEX_WRITE_SANDBOX_UNAVAILABLE)
            self.assertIn("native Windows worktree", output)
            run.assert_not_called()

    def test_configured_native_worktree_root_retains_legacy_discovery(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            repo = base / "project"
            repo.mkdir()
            native = base / "Codex" / "WesnothAgentWorktrees"
            with mock.patch.dict(
                os.environ, {worktree_paths.WORKTREE_ROOT_ENV: str(native)}
            ):
                self.assertEqual(worktree_paths.managed_worktree_root(repo), native.resolve())
                self.assertEqual(
                    worktree_paths.managed_worktree_roots(repo),
                    (native.resolve(), (base / "project-worktrees").resolve()),
                )

    def test_clean_legacy_resume_moves_to_configured_native_root(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            repo = base / "project"
            repo.mkdir()
            subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True,
                           stdout=subprocess.DEVNULL)
            subprocess.run(["git", "config", "user.name", "Fixture"], cwd=repo, check=True)
            subprocess.run(
                ["git", "config", "user.email", "fixture@example.invalid"],
                cwd=repo, check=True,
            )
            (repo / "fixture.txt").write_text("baseline\n", encoding="utf-8")
            subprocess.run(["git", "add", "fixture.txt"], cwd=repo, check=True)
            subprocess.run(["git", "commit", "-m", "baseline"], cwd=repo, check=True,
                           stdout=subprocess.DEVNULL)
            legacy = base / "project-worktrees" / "ticket"
            legacy.parent.mkdir()
            branch = "agent/native-resume"
            subprocess.run(
                ["git", "worktree", "add", "-b", branch, str(legacy)],
                cwd=repo, check=True, stdout=subprocess.DEVNULL,
            )
            native = base / "Codex" / "WesnothAgentWorktrees"
            with mock.patch.dict(
                os.environ, {worktree_paths.WORKTREE_ROOT_ENV: str(native)}
            ):
                resolved = ticket_runner.resolve_resume_worktree(repo, branch)
            self.assertEqual(resolved, (native / "ticket").resolve())
            self.assertTrue(resolved.is_dir())
            self.assertFalse(legacy.exists())
            self.assertEqual(
                subprocess.run(
                    ["git", "branch", "--show-current"], cwd=resolved,
                    check=True, text=True, stdout=subprocess.PIPE,
                ).stdout.strip(),
                branch,
            )

    def test_local_sandbox_failure_does_not_open_terra_provider_circuit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime = Path(directory) / "runtime"
            policy = model_policy.ModelPolicy(runtime)
            run_sequence = policy.begin_run("NATIVE-WRITE")
            policy.record_failure("openai/gpt-5.6-terra", run_sequence, "process")
            status = mock.Mock()
            log = Path(directory) / "terra.txt"
            with mock.patch.object(
                ticket_runner,
                "invoke_terra",
                return_value=(
                    recovery_policy.CODEX_WRITE_SANDBOX_UNAVAILABLE,
                    "native Windows worktree required",
                ),
            ):
                code, _ = ticket_runner.invoke_managed_terra(
                    policy=policy, run_sequence=run_sequence + 3, status=status,
                    worktree=Path(directory), prompt="fixture", log_file=log,
                    sandbox="workspace-write", timeout=300,
                )
            self.assertEqual(code, recovery_policy.CODEX_WRITE_SANDBOX_UNAVAILABLE)
            self.assertTrue(
                policy.before_attempt("openai/gpt-5.6-terra", run_sequence + 4)[0]
            )

    def test_launcher_supplied_codex_path_survives_missing_path_entry(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            executable = Path(directory) / "codex.exe"
            executable.write_text("fixture\n", encoding="utf-8")
            with (
                mock.patch.dict(os.environ, {"WESNOTH_CODEX_EXE": str(executable)}),
                mock.patch("ticket_runner.shutil.which", return_value=None),
            ):
                self.assertEqual(ticket_runner.resolve_codex_executable(), str(executable))

    def test_installed_codex_path_survives_stripped_secure_environment(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory) / "home" / "fixture-user"
            executable = (
                Path(directory) / "mnt" / "c" / "Users" / "fixture-user"
                / "AppData" / "Local" / "OpenAI" / "Codex" / "bin"
                / "current" / "codex.exe"
            )
            executable.parent.mkdir(parents=True)
            executable.write_text("fixture\n", encoding="utf-8")
            real_path = ticket_runner.Path

            def mapped_path(value):
                path = real_path(value)
                if path == real_path("/mnt/c/Users"):
                    return real_path(directory) / "mnt" / "c" / "Users"
                return path

            with (
                mock.patch.dict(os.environ, {}, clear=True),
                mock.patch("ticket_runner.Path", side_effect=mapped_path),
                mock.patch("ticket_runner.shutil.which", return_value=None),
            ):
                ticket_runner.Path.home.return_value = home
                self.assertEqual(
                    ticket_runner.resolve_codex_executable(), str(executable)
                )

    def test_sol_and_terra_share_codex_resolver(self) -> None:
        source = (ROOT / "agent" / "dashboard" / "autonomy.py").read_text(
            encoding="utf-8"
        )
        self.assertIn(
            "executable = ticket_runner.resolve_codex_executable()",
            source,
        )

    def test_missing_terra_executable_writes_diagnostic(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            log = Path(directory) / "terra.txt"
            with mock.patch.object(ticket_runner, "resolve_codex_executable", return_value=None):
                code, output = ticket_runner.invoke_terra_implementer(
                    worktree=Path(directory), prompt="fixture", log_file=log
                )
            self.assertEqual(code, 127)
            self.assertIn("unavailable", output)
            self.assertEqual(log.read_text(encoding="utf-8").strip(), output)

    def test_luna_fallback_uses_medium_reasoning_and_requested_sandbox(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            log = Path(directory) / "luna.txt"
            completed = subprocess.CompletedProcess([], 0, stdout="VERDICT: PASS\n")
            with (
                mock.patch.object(
                    ticket_runner, "resolve_codex_executable", return_value="/opt/codex"
                ),
                mock.patch("ticket_runner.subprocess.run", return_value=completed) as run,
            ):
                code, output = ticket_runner.invoke_luna(
                    worktree=Path(directory),
                    prompt="fixture",
                    log_file=log,
                    sandbox="read-only",
                    timeout=300,
                )
            command = run.call_args.args[0]
            self.assertEqual(code, 0)
            self.assertEqual(output, "VERDICT: PASS\n")
            self.assertIn("gpt-5.6-luna", command)
            self.assertIn('model_reasoning_effort="medium"', command)
            self.assertEqual(command[command.index("-s") + 1], "read-only")

    def test_fallback_diagnostic_distinguishes_context_and_missing_codex(self) -> None:
        failure = recovery_policy.classify_implementer_fallback(
            "ContextOverflowError: Request too large for tokens per minute",
            1,
            "Codex executable unavailable",
            127,
        )
        self.assertEqual(failure["class"], "implementer_fallback_unavailable")
        self.assertIn("token limit", failure["detail"])
        self.assertIn("did not run", failure["detail"])
        self.assertNotIn("ContextOverflowError", failure["detail"])

    def test_tester_fallback_diagnostic_names_both_provider_failures(self) -> None:
        failure = recovery_policy.classify_tester_fallback(
            ticket_runner.MODEL_CIRCUIT_OPEN,
            124,
        )
        self.assertEqual(failure["class"], "tester_provider_failure")
        self.assertIn("circuit is open", failure["detail"])
        self.assertIn("Luna Medium", failure["detail"])
        self.assertIn("timed out", failure["detail"])

    def test_control_bridge_forwards_verified_codex_path(self) -> None:
        text = (ROOT / "agent" / "dashboard" / "control-bridge.ps1").read_text(
            encoding="utf-8"
        )
        self.assertIn('EnvironmentVariables["WESNOTH_CODEX_EXE"]', text)
        self.assertIn('forwardWslEnv += "WESNOTH_CODEX_EXE"', text)
        self.assertIn('EnvironmentVariables["WESNOTH_AGENT_WORKTREE_ROOT"]', text)
        self.assertIn('forwardWslEnv += "WESNOTH_AGENT_WORKTREE_ROOT"', text)

    def test_batch_launcher_exports_codex_compatible_worktree_root(self) -> None:
        text = (ROOT / "Start-WesnothAgentEnvironment.cmd").read_text(encoding="utf-8")
        self.assertIn(
            "WESNOTH_AGENT_WORKTREE_ROOT=/mnt/c/Users/%USERNAME%/Documents/Codex/"
            "WesnothAgentWorktrees",
            text,
        )
        self.assertIn("WESNOTH_AGENT_WORKTREE_ROOT/u", text)

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
                    body=json.dumps({
                        "action": "set_guidance",
                        "guidance": "Prioritize player-facing mission work.",
                    }),
                    headers={
                        "Host": f"127.0.0.1:{server.server_port}",
                        "Origin": f"http://127.0.0.1:{server.server_port}",
                        "Content-Type": "application/json",
                        "X-Wesnoth-CSRF": control["csrf_token"],
                    },
                )
                response = connection.getresponse()
                guided = json.loads(response.read())
                self.assertEqual(response.status, 202)
                self.assertEqual(
                    guided["automation"]["guidance"],
                    "Prioritize player-facing mission work.",
                )
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

    def test_paired_lan_client_receives_full_governed_control(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            lan_url = "http://192.168.4.88:8765"
            lan_token = "a" * 43
            server = create_server(
                0, base / "state.json", base / "control.json",
                lan_url=lan_url, lan_token=lan_token,
            )
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                connection = http.client.HTTPConnection("127.0.0.1", server.server_port)
                host = f"127.0.0.1:{server.server_port}"
                connection.request(
                    "GET", "/api/control",
                    headers={"Host": host, "X-Wesnoth-LAN-View": "1"},
                )
                response = connection.getresponse()
                self.assertEqual(response.status, 403)
                response.read()

                lan_headers = {
                    "Host": host,
                    "X-Wesnoth-LAN-View": "1",
                    "X-Wesnoth-LAN-Token": lan_token,
                }
                connection.request("GET", "/api/control", headers=lan_headers)
                response = connection.getresponse()
                control = json.loads(response.read())
                self.assertEqual(response.status, 200)
                self.assertTrue(control["access"]["remote"])
                self.assertTrue(control["access"]["shutdown_available"])
                self.assertEqual(control["access"]["lan_access_url"], "")
                self.assertIn("csrf_token", control)

                connection.request(
                    "POST", "/api/control",
                    body=json.dumps({"action": "set_mode", "mode": "sol-medium"}),
                    headers={
                        **lan_headers,
                        "Origin": lan_url,
                        "Content-Type": "application/json",
                        "X-Wesnoth-CSRF": control["csrf_token"],
                    },
                )
                response = connection.getresponse()
                changed = json.loads(response.read())
                self.assertEqual(response.status, 202)
                self.assertEqual(changed["mode"], "sol-medium")
                connection.close()
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)

    def test_idle_dashboard_accepts_clean_shutdown(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            server = create_server(0, base / "state.json", base / "control.json")
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            connection = http.client.HTTPConnection("127.0.0.1", server.server_port)
            host = f"127.0.0.1:{server.server_port}"
            connection.request("GET", "/api/control", headers={"Host": host})
            control = json.loads(connection.getresponse().read())
            connection.request(
                "POST", "/api/control", body=json.dumps({"action": "shutdown"}),
                headers={
                    "Host": host,
                    "Origin": f"http://127.0.0.1:{server.server_port}",
                    "Content-Type": "application/json",
                    "X-Wesnoth-CSRF": control["csrf_token"],
                },
            )
            response = connection.getresponse()
            result = json.loads(response.read())
            self.assertEqual(response.status, 202)
            self.assertEqual(result["shutdown"], "accepted")
            connection.close()
            thread.join(timeout=2)
            self.assertFalse(thread.is_alive())
            server.server_close()

    def test_active_dashboard_shutdown_cancels_only_current_run(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            control_file = base / "control.json"
            server = create_server(0, base / "state.json", control_file)
            server.controller.store.update(lambda state: (
                state["automation"].update({"enabled": True}),
                state["run"].update({
                    "state": "executing", "run_id": "a1b2c3d4e5f6",
                    "ticket_id": "DASH-TEST", "completed_at": None,
                }),
            ))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            connection = http.client.HTTPConnection("127.0.0.1", server.server_port)
            host = f"127.0.0.1:{server.server_port}"
            connection.request("GET", "/api/control", headers={"Host": host})
            control = json.loads(connection.getresponse().read())
            connection.request(
                "POST", "/api/control", body=json.dumps({"action": "shutdown"}),
                headers={
                    "Host": host,
                    "Origin": f"http://127.0.0.1:{server.server_port}",
                    "Content-Type": "application/json",
                    "X-Wesnoth-CSRF": control["csrf_token"],
                },
            )
            response = connection.getresponse()
            result = json.loads(response.read())
            self.assertEqual(response.status, 202)
            self.assertEqual(result["shutdown"], "accepted")
            self.assertEqual(result["run"]["state"], "interrupted")
            self.assertFalse(result["automation"]["enabled"])
            self.assertTrue((base / "secure-run-cancel.a1b2c3d4e5f6").is_file())
            connection.close()
            thread.join(timeout=2)
            self.assertFalse(thread.is_alive())
            server.server_close()


class ModelPolicyTests(unittest.TestCase):
    def test_tester_execution_budgets_allow_slow_provider_responses(self) -> None:
        self.assertEqual(ticket_runner.TESTER_TIMEOUT, 300)
        self.assertEqual(ticket_runner.LUNA_TESTER_TIMEOUT, 300)

    def test_published_free_tier_launch_limits(self) -> None:
        self.assertEqual(model_policy.MODEL_RPM["groq/openai/gpt-oss-120b"], 30)
        self.assertEqual(
            model_policy.MODEL_RPM[
                "cloudflare-workers-ai/@cf/nvidia/nemotron-3-120b-a12b"
            ],
            40,
        )
        self.assertEqual(
            model_policy.MODEL_RPM[
                "cloudflare-workers-ai/@cf/zai-org/glm-4.7-flash"
            ],
            300,
        )
        self.assertNotIn("google/gemini-3.8-flash", model_policy.MODEL_RPM)
        self.assertNotIn("google/gemini-3.6-flash", model_policy.MODEL_RPM)
        self.assertIsNone(model_policy.MODEL_RPM["openai/gpt-5.6-luna"])

    def test_active_worker_model_routes_match_the_cost_policy(self) -> None:
        self.assertEqual(model_policy.AGENT_MODELS["implementer"], "openai/gpt-5.6-terra")
        self.assertEqual(model_policy.AGENT_MODELS["fast-fix"], "openai/gpt-5.6-luna-medium")
        self.assertEqual(model_policy.AGENT_MODELS["tester"], "openai/gpt-5.6-luna-medium")
        self.assertEqual(
            model_policy.AGENT_MODELS["reviewer"],
            "cloudflare-workers-ai/@cf/nvidia/nemotron-3-120b-a12b",
        )

    def test_cloudflare_daily_neuron_exhaustion_is_quota_failure(self) -> None:
        output = (
            'Too Many Requests: {"statusCode":429,"message":'
            '"used up your daily free allocation"}'
        )
        self.assertEqual(model_policy.failure_kind(1, output), "quota")
        failure = recovery_policy.classify_tester_fallback(
            1, 127, output, "Luna unavailable"
        )
        self.assertIn("exhausted its provider quota", failure["detail"])
        self.assertIn("Luna Medium", failure["detail"])

    def test_cloudflare_daily_quota_blocks_all_models_until_utc_midnight(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            now = [1_788_613_668.0]
            policy = model_policy.ModelPolicy(
                Path(directory), clock=lambda: now[0], sleeper=lambda _: None
            )
            glm = "cloudflare-workers-ai/@cf/zai-org/glm-4.7-flash"
            nemotron = "cloudflare-workers-ai/@cf/nvidia/nemotron-3-120b-a12b"
            luna = "openai/gpt-5.6-luna"
            run = policy.begin_run("DAILY-QUOTA")
            self.assertTrue(policy.before_attempt(glm, run)[0])
            policy.record_failure(
                glm,
                run,
                "quota",
                "Too Many Requests: used up your daily free allocation of 10,000 neurons",
            )
            reset = float((int(now[0]) // 86_400 + 1) * 86_400)
            self.assertFalse(policy.before_attempt(glm, run + 1)[0])
            self.assertFalse(policy.before_attempt(nemotron, run + 1)[0])
            self.assertTrue(policy.before_attempt(luna, run + 1)[0])
            self.assertIn(
                time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime(reset)),
                policy.unavailable_reason(glm, run + 1),
            )
            state = policy.public_state(run + 1)
            self.assertEqual(state[glm]["blocked_until"], reset)
            self.assertFalse(state[nemotron]["available_this_run"])

            now[0] = reset
            self.assertTrue(policy.before_attempt(glm, run + 1)[0])
            self.assertTrue(policy.before_attempt(nemotron, run + 1)[0])
            self.assertIsNone(policy.public_state(run + 1)[glm]["blocked_until"])

    def test_non_daily_cloudflare_failure_keeps_two_run_circuit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            policy = model_policy.ModelPolicy(Path(directory))
            model = "cloudflare-workers-ai/@cf/zai-org/glm-4.7-flash"
            first = policy.begin_run("ONE")
            policy.record_failure(model, first, "quota", "ordinary rate limit")
            self.assertFalse(policy.before_attempt(model, first + 1)[0])
            self.assertFalse(policy.before_attempt(model, first + 2)[0])
            self.assertTrue(policy.before_attempt(model, first + 3)[0])

    def test_provider_failure_skips_exactly_two_later_runs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            policy = model_policy.ModelPolicy(Path(directory))
            model = "groq/openai/gpt-oss-120b"
            first = policy.begin_run("ONE")
            policy.record_failure(model, first, "quota")
            second = policy.begin_run("TWO")
            third = policy.begin_run("THREE")
            fourth = policy.begin_run("FOUR")
            self.assertFalse(policy.before_attempt(model, second)[0])
            self.assertFalse(policy.before_attempt(model, third)[0])
            self.assertTrue(policy.before_attempt(model, fourth)[0])

    def test_nemotron_pacing_uses_forty_rpm(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            now = [100.0]
            waits: list[float] = []

            def sleep(seconds: float) -> None:
                waits.append(seconds)
                now[0] += seconds

            policy = model_policy.ModelPolicy(
                Path(directory), clock=lambda: now[0], sleeper=sleep
            )
            model = "cloudflare-workers-ai/@cf/nvidia/nemotron-3-120b-a12b"
            run = policy.begin_run("ONE")
            policy.before_attempt(model, run)
            policy.before_attempt(model, run)
            self.assertEqual(waits, [1.5])

    def test_decisive_rejection_is_not_a_provider_failure(self) -> None:
        self.assertIsNone(
            model_policy.failure_kind(
                0, "VERDICT: REQUEST_CHANGES", decisive=True
            )
        )


class ReviewerFallbackRoutingTests(unittest.TestCase):
    def _evaluate(
        self,
        reviewer_responses: list[tuple[int, str]],
        *,
        luna_responses: list[tuple[int, str]] | None = None,
        resume_checkpoint: dict | None = None,
    ) -> tuple[dict, list[str]]:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            log_dir = base / "logs"
            log_dir.mkdir()
            status = mock.Mock()
            invoked: list[str] = []

            def invoke(**kwargs):
                invoked.append(kwargs["agent"])
                return reviewer_responses.pop(0)

            luna_responses = list(luna_responses or [(0, "VERDICT: PASS")])

            def invoke_luna(**_kwargs):
                return luna_responses.pop(0)

            policy = model_policy.ModelPolicy(base / "runtime")
            run_sequence = policy.begin_run("REVIEW-CHAIN")
            with mock.patch.object(ticket_runner, "run_validation", return_value={"pass": True}), mock.patch.object(
                ticket_runner, "invoke_agent", side_effect=invoke
            ), mock.patch.object(
                ticket_runner, "invoke_luna", side_effect=invoke_luna
            ):
                result = ticket_runner.evaluate_candidate(
                    status=status,
                    ticket={
                        "task_id": "REVIEW-CHAIN",
                        "objective": "Exercise reviewer fallback routing",
                        "allowed_paths": ["fixture.txt"],
                        "worker": "implementer",
                    },
                    worktree=base,
                    log_dir=log_dir,
                    governance_prompt="Controlled references loaded.",
                    opencode="opencode",
                    implementer_rc=0,
                    attempt=0,
                    policy=policy,
                    run_sequence=run_sequence,
                    resume_checkpoint=resume_checkpoint,
                )
            return result, invoked

    def test_nemotron_is_primary_reviewer(self) -> None:
        result, invoked = self._evaluate([(0, "VERDICT: APPROVE")])
        self.assertTrue(result["pass"])
        self.assertEqual(
            result["reviewer_used"],
            "cloudflare-workers-ai/@cf/nvidia/nemotron-3-120b-a12b",
        )
        self.assertEqual(invoked, ["reviewer"])
        self.assertIsNone(result["reviewer_intermediate_exit_code"])

    def test_luna_light_tests_when_luna_medium_is_unavailable(self) -> None:
        result, invoked = self._evaluate(
            [(0, "VERDICT: APPROVE")],
            luna_responses=[(1, "Luna Medium unavailable"), (0, "VERDICT: PASS")],
        )
        self.assertTrue(result["pass"])
        self.assertEqual(result["tester_primary_exit_code"], 1)
        self.assertEqual(result["tester_luna_exit_code"], 0)
        self.assertTrue(result["tester_luna_pass"])
        self.assertEqual(result["tester_used"], "openai/gpt-5.6-luna-light")
        self.assertEqual(invoked, ["reviewer"])

    def test_explicit_primary_tester_failure_does_not_seek_second_opinion(self) -> None:
        result, invoked = self._evaluate(
            [], luna_responses=[(0, "VERDICT: FAIL — candidate defect")],
        )
        self.assertFalse(result["pass"])
        self.assertEqual(result["failure"]["class"], "tester_change_request")
        self.assertIsNone(result["tester_luna_exit_code"])
        self.assertEqual(invoked, [])

    def test_luna_can_test_a_terra_implementation(self) -> None:
        result, invoked = self._evaluate(
            [(0, "VERDICT: APPROVE")],
            luna_responses=[(0, "VERDICT: PASS")],
        )
        self.assertTrue(result["pass"])
        self.assertEqual(result["tester_used"], "openai/gpt-5.6-luna-medium")
        self.assertIsNone(result["tester_luna_exit_code"])
        self.assertEqual(invoked, ["reviewer"])

    def test_luna_light_reviews_after_non_decisive_nemotron(self) -> None:
        result, invoked = self._evaluate(
            [(1, "primary reviewer unavailable")],
            luna_responses=[(0, "VERDICT: PASS"), (0, "VERDICT: APPROVE")],
        )
        self.assertTrue(result["pass"])
        self.assertEqual(result["reviewer_used"], "openai/gpt-5.6-luna")
        self.assertEqual(result["reviewer_luna_exit_code"], 0)
        self.assertEqual(invoked, ["reviewer"])
        self.assertEqual(result["reviewer_fallback_exit_code"], 0)

    def test_luna_light_request_changes_is_authoritative(self) -> None:
        result, invoked = self._evaluate(
            [(1, "primary infrastructure failure")],
            luna_responses=[(0, "VERDICT: PASS"), (0, "VERDICT: REQUEST_CHANGES")],
        )
        self.assertFalse(result["pass"])
        self.assertEqual(result["failure"]["class"], "reviewer_change_request")
        self.assertEqual(result["reviewer_used"], "openai/gpt-5.6-luna")
        self.assertEqual(invoked, ["reviewer"])

    def test_luna_light_can_review_when_terra_implemented(self) -> None:
        result, invoked = self._evaluate(
            [(1, "primary infrastructure failure")],
            luna_responses=[(0, "VERDICT: PASS"), (0, "VERDICT: APPROVE")],
        )
        self.assertTrue(result["pass"])
        self.assertEqual(result["reviewer_used"], "openai/gpt-5.6-luna")
        self.assertEqual(invoked, ["reviewer"])

    def test_reviewer_checkpoint_skips_validation_and_tester(self) -> None:
        checkpoint = {
            "stage": "reviewer",
            "result": {
                "validation": {"pass": True},
                "tester_exit_code": 0,
                "tester_used": "openai/gpt-5.6-luna",
                "tester_primary_exit_code": 88,
                "tester_primary_pass": False,
                "tester_primary_fail": False,
                "tester_luna_exit_code": 0,
                "tester_luna_pass": True,
                "tester_luna_fail": False,
                "tester_pass": True,
            },
        }
        result, invoked = self._evaluate(
            [(0, "VERDICT: APPROVE")], resume_checkpoint=checkpoint
        )
        self.assertTrue(result["pass"])
        self.assertEqual(invoked, ["reviewer"])
        self.assertEqual(result["tester_used"], "openai/gpt-5.6-luna")


class StageCheckpointTests(unittest.TestCase):
    def test_unchanged_reviewer_failure_resumes_at_reviewer(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result_dir = root / "agent/logs/RUN"
            result_dir.mkdir(parents=True)
            worktree = root / "worktree"
            worktree.mkdir()
            ticket = {
                "objective": "Fixture", "allowed_paths": ["fixture.txt"],
                "worker": "implementer", "validation_profile": "static-text",
                "validation_root": None,
            }
            (result_dir / "result.json").write_text(json.dumps({
                "branch": "agent/example",
                "final_verdict": "FAIL",
                "candidate_digest": "a" * 64,
                "ticket_contract_digest": ticket_runner.ticket_contract_digest(ticket),
                "resume_stage": "reviewer",
                "validation": {"pass": True},
                "tester_pass": True,
            }))
            with mock.patch.object(
                ticket_runner, "candidate_digest", return_value="a" * 64
            ):
                checkpoint = ticket_runner.load_stage_checkpoint(
                    root, "agent/example", worktree, ticket
                )
            self.assertEqual(checkpoint["stage"], "reviewer")

    def test_changed_candidate_invalidates_stage_checkpoint(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result_dir = root / "agent/logs/RUN"
            result_dir.mkdir(parents=True)
            worktree = root / "worktree"
            worktree.mkdir()
            ticket = {
                "objective": "Fixture", "allowed_paths": ["fixture.txt"],
                "worker": "implementer", "validation_profile": "static-text",
                "validation_root": None,
            }
            (result_dir / "result.json").write_text(json.dumps({
                "branch": "agent/example",
                "final_verdict": "FAIL",
                "candidate_digest": "a" * 64,
                "ticket_contract_digest": ticket_runner.ticket_contract_digest(ticket),
                "resume_stage": "tester",
                "validation": {"pass": True},
            }))
            with mock.patch.object(
                ticket_runner, "candidate_digest", return_value="b" * 64
            ):
                checkpoint = ticket_runner.load_stage_checkpoint(
                    root, "agent/example", worktree, ticket
                )
            self.assertIsNone(checkpoint)


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

    def test_pr_head_confirmation_retries_a_stale_github_read(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            queue = ApprovalQueue(root)
            expected = "a" * 40
            stale = json.dumps({
                "number": 15, "url": "https://example.invalid/15",
                "headRefOid": "b" * 40, "state": "OPEN",
            })
            current = json.dumps({
                "number": 15, "url": "https://example.invalid/15",
                "headRefOid": expected, "state": "OPEN",
            })
            with (
                mock.patch("approval_queue._run", return_value=current) as run,
                mock.patch.object(approval_queue, "PR_HEAD_CONFIRM_INTERVAL_SECONDS", 0),
            ):
                result = queue._wait_for_pr_head(
                    "https://example.invalid/15", expected, root,
                    initial=json.loads(stale),
                )
            self.assertEqual(result["headRefOid"], expected)
            self.assertEqual(run.call_count, 1)

    def test_ci_registration_waits_for_required_exact_head_check(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            queue = ApprovalQueue(root)
            expected = "a" * 40
            empty = json.dumps({
                "headRefOid": expected,
                "statusCheckRollup": [],
            })
            registered = json.dumps({
                "headRefOid": expected,
                "statusCheckRollup": [{
                    "name": "repository-gates",
                    "status": "QUEUED",
                    "conclusion": "",
                }],
            })
            with (
                mock.patch("approval_queue._run", side_effect=[empty, registered]) as run,
                mock.patch.object(approval_queue, "CI_REGISTRATION_INTERVAL_SECONDS", 0),
            ):
                checks = queue._wait_for_ci_registration(15, expected, root)
            self.assertEqual(checks[0]["name"], "repository-gates")
            self.assertEqual(run.call_count, 2)

    def test_ci_registration_rejects_a_changed_pr_head(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            queue = ApprovalQueue(root)
            changed = json.dumps({
                "headRefOid": "b" * 40,
                "statusCheckRollup": [{"name": "repository-gates"}],
            })
            with mock.patch("approval_queue._run", return_value=changed):
                with self.assertRaisesRegex(QueueError, "PR head changed"):
                    queue._wait_for_ci_registration(15, "a" * 40, root)

    def test_remove_failed_ticket_hides_only_queue_record(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            queue = ApprovalQueue(root)
            record_id = "1" * 16
            commit = "a" * 40
            queue._update(lambda state: state["records"].append({
                "id": record_id,
                "ticket_id": "DASH-TEST",
                "purpose": "Fixture",
                "impact": "Fixture impact",
                "branch": "agent/dash-test",
                "commit_sha": commit,
                "state": "failed",
            }))
            queue.dismiss_failed(record_id, commit)
            self.assertEqual(queue.public_state()["records"], [])
            stored = queue.read()["records"][0]
            self.assertEqual(stored["state"], "dismissed")
            self.assertEqual(stored["branch"], "agent/dash-test")
            with self.assertRaises(QueueError):
                queue.dismiss_failed(record_id, commit)

    def test_cumulative_ready_tickets_form_one_exact_batch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            queue = ApprovalQueue(root)
            first_id, second_id = "1" * 16, "2" * 16
            first_sha, second_sha = "a" * 40, "b" * 40
            authorization_id = "c" * 32
            queue._update(lambda state: state["records"].extend([
                {
                    "id": first_id, "ticket_id": "ONE", "state": "ready",
                    "dependency_index": 1, "commit_sha": first_sha,
                    "branch": "agent/one", "changed_paths": ["one.cfg"],
                    "automation_authorized": True,
                    "automation_authorization_id": authorization_id,
                },
                {
                    "id": second_id, "ticket_id": "TWO", "state": "ready",
                    "dependency_index": 2, "commit_sha": second_sha,
                    "branch": "agent/two", "changed_paths": ["two.cfg"],
                    "depends_on_id": first_id, "depends_on_commit": first_sha,
                    "automation_authorized": True,
                    "automation_authorization_id": authorization_id,
                },
            ]))
            public = queue.public_state()
            self.assertEqual(len(public["batches"]), 1)
            batch = public["batches"][0]
            self.assertEqual(
                [item["id"] for item in batch["members"]],
                [first_id, second_id],
            )
            self.assertEqual(
                queue.autonomous_publication_target(second_id, authorization_id),
                {"kind": "batch", "id": batch["id"]},
            )

    def test_batch_publication_uses_final_head_and_completes_every_member(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            queue = ApprovalQueue(root)
            first_id, second_id = "1" * 16, "2" * 16
            first_sha, second_sha = "a" * 40, "b" * 40
            queue._update(lambda state: state["records"].extend([
                {
                    "id": first_id, "ticket_id": "ONE", "state": "ready",
                    "dependency_index": 1, "commit_sha": first_sha,
                    "branch": "agent/one", "changed_paths": ["one.cfg"],
                },
                {
                    "id": second_id, "ticket_id": "TWO", "state": "ready",
                    "dependency_index": 2, "commit_sha": second_sha,
                    "branch": "agent/two", "changed_paths": ["two.cfg"],
                    "depends_on_id": first_id, "depends_on_commit": first_sha,
                },
            ]))
            batch_id = queue.public_state()["batches"][0]["id"]

            def publish_final(record: dict) -> None:
                self.assertEqual(record["id"], second_id)
                queue._update_record(
                    second_id, state="published", pr_number=27,
                    pr_url="https://example.invalid/27", merge_sha="c" * 40,
                )

            with (
                mock.patch.object(queue, "_worktree", return_value=root),
                mock.patch.object(queue, "_is_ancestor", return_value=True),
                mock.patch.object(queue, "_publish", side_effect=publish_final),
            ):
                records = queue.approve_and_publish_batch(batch_id)
            self.assertEqual([item["state"] for item in records], ["published", "published"])
            self.assertTrue(all(item["pr_number"] == 27 for item in records))

    def test_stale_cleanup_deletes_only_exact_clean_local_worktree_and_branch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            root = base / "project"
            worktrees = base / "project-worktrees"
            root.mkdir()
            self.git(root, "init", "-b", "main")
            self.git(root, "config", "user.email", "test@example.invalid")
            self.git(root, "config", "user.name", "Dashboard Test")
            (root / "base.txt").write_text("base\n", encoding="utf-8")
            self.git(root, "add", "base.txt")
            self.git(root, "commit", "-m", "fixture")
            worktree = worktrees / "stale-ticket"
            self.git(root, "worktree", "add", "-b", "agent/stale-ticket", str(worktree), "main")
            (worktree / "candidate.txt").write_text("candidate\n", encoding="utf-8")
            self.git(worktree, "add", "candidate.txt")
            self.git(worktree, "commit", "-m", "candidate")
            commit = self.git(worktree, "rev-parse", "HEAD")
            queue = ApprovalQueue(root)
            record_id = "3" * 16
            queue._update(lambda state: state["records"].append({
                "id": record_id, "ticket_id": "STALE", "state": "stale",
                "dependency_index": 1, "commit_sha": commit,
                "branch": "agent/stale-ticket", "worktree_name": worktree.name,
                "changed_paths": ["candidate.txt"], "pr_number": None, "pr_url": None,
            }))
            queue._update(lambda state: state["records"].append({
                "id": "4" * 16, "ticket_id": "DEPENDENT", "state": "stale",
                "dependency_index": 2, "commit_sha": "f" * 40,
                "branch": "agent/dependent", "depends_on_id": record_id,
                "depends_on_commit": commit,
            }))
            with self.assertRaisesRegex(QueueError, "still depends"):
                queue.discard_local_remnants(record_id, commit)
            queue._update(lambda state: next(
                item for item in state["records"] if item.get("id") == "4" * 16
            ).update({"state": "discarded"}))
            queue.discard_local_remnants(record_id, commit)
            self.assertFalse(worktree.exists())
            self.assertNotIn("agent/stale-ticket", self.git(root, "branch", "--list"))
            self.assertEqual(queue.public_state()["records"], [])
            self.assertEqual(queue.read()["records"][0]["state"], "discarded")

    def test_failed_queue_item_blocks_normal_planning_but_can_be_excluded_for_recode(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            controller = AutonomyController(
                base,
                ControlStore(base / "control.json"),
                ApprovalQueue(base, base / "queue.json"),
            )
            controller.queue._update(lambda state: state["records"].append({
                "id": "2" * 16,
                "ticket_id": "DASH-TEST",
                "purpose": "Fixture",
                "changed_paths": ["addons/example.cfg"],
                "branch": "agent/dash-test",
                "state": "failed",
            }))
            self.assertEqual(len(controller._queued_context()), 1)
            self.assertEqual(
                controller._queued_context(exclude_id="2" * 16),
                [],
            )

    def test_exact_recode_uses_selected_branch_and_recorded_contract_without_sol(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            worktree = base / "managed-worktree"
            worktree.mkdir()
            controller = AutonomyController(
                base,
                ControlStore(base / "control.json"),
                ApprovalQueue(base, base / "queue.json"),
            )
            commit = "a" * 40
            failed = {
                "id": "2" * 16,
                "ticket_id": "DASH-FAILED",
                "branch": "agent/dash-failed",
                "commit_sha": commit,
                "impact": "Repairs the selected candidate.",
                "pr_number": None,
            }
            evidence = {
                "task_id": "DASH-FAILED",
                "worker": "implementer",
                "objective": "Repair one bounded fixture",
                "allowed_paths": ["addons/example.cfg"],
                "validation_profile": "static-text",
                "validation_root": None,
            }
            completed = subprocess.CompletedProcess([], 0, stdout=commit + "\n")
            with (
                mock.patch.object(
                    controller, "_ticket_evidence",
                    return_value={"agent/dash-failed": evidence},
                ),
                mock.patch.object(
                    ticket_runner, "resolve_resume_worktree", return_value=worktree
                ),
                mock.patch.object(
                    ticket_runner, "read_resume_changes",
                    return_value=(["M addons/example.cfg"], ["addons/example.cfg"]),
                ),
                mock.patch.object(
                    ticket_runner, "validate_resume_scope", return_value={"pass": True}
                ),
                mock.patch.object(
                    ticket_runner, "inspect_local_resume_reconciliation",
                    return_value={"safe": True, "mode": "clean-fast-forward"},
                ),
                mock.patch("autonomy.subprocess.run", return_value=completed),
                mock.patch.object(controller, "_plan") as planner,
            ):
                proposal = controller._exact_recode_proposal(failed)
            planner.assert_not_called()
            self.assertEqual(proposal["action"], "run_ticket")
            self.assertEqual(
                proposal["ticket"]["resume_branch"], "agent/dash-failed"
            )
            self.assertEqual(
                proposal["ticket"]["objective"], "Repair one bounded fixture"
            )
            self.assertEqual(
                proposal["_planning_inventory"]["local_agent_branches"][0]["head"],
                commit,
            )

    def test_exact_recode_rejects_changed_worktree_head(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            worktree = base / "managed-worktree"
            worktree.mkdir()
            controller = AutonomyController(
                base,
                ControlStore(base / "control.json"),
                ApprovalQueue(base, base / "queue.json"),
            )
            evidence = {
                "task_id": "DASH-FAILED", "worker": "implementer",
                "objective": "Repair fixture", "allowed_paths": ["fixture.txt"],
                "validation_profile": "static-text", "validation_root": None,
            }
            completed = subprocess.CompletedProcess([], 0, stdout="b" * 40 + "\n")
            with (
                mock.patch.object(
                    controller, "_ticket_evidence",
                    return_value={"agent/dash-failed": evidence},
                ),
                mock.patch.object(
                    ticket_runner, "resolve_resume_worktree", return_value=worktree
                ),
                mock.patch("autonomy.subprocess.run", return_value=completed),
            ):
                with self.assertRaisesRegex(ControlError, "exact worktree head"):
                    controller._exact_recode_proposal({
                        "id": "2" * 16, "ticket_id": "DASH-FAILED",
                        "branch": "agent/dash-failed", "commit_sha": "a" * 40,
                        "pr_number": None,
                    })

    def test_continuous_automation_observes_completion_cooldown(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            controller = AutonomyController(
                base,
                ControlStore(base / "control.json"),
                ApprovalQueue(base, base / "queue.json"),
            )
            with mock.patch("autonomy.time.monotonic", return_value=100.0):
                controller._last_completion_monotonic = 50.0
                self.assertFalse(controller._cooldown_complete())
                controller._last_completion_monotonic = 39.0
                self.assertTrue(controller._cooldown_complete())

    def test_autonomous_worktree_stops_after_three_consecutive_failures(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            (base / "agent" / "runtime").mkdir(parents=True)
            controller = AutonomyController(
                base,
                ControlStore(base / "control.json"),
                ApprovalQueue(base, base / "queue.json"),
            )
            controller.store.update(lambda state: state.update({
                "mode": "sol-low",
                "automation": {"enabled": True, "brief": "Continue safely"},
            }))
            proposal = {
                "action": "run_ticket", "summary": "Resume fixture", "impact": "Fixture",
                "ticket": {},
            }
            ticket = {
                "task_id": "SOL-FAILURE-FIXTURE", "resume_branch": "agent/fixture",
            }
            failed = {
                "return_code": 12,
                "failure": {
                    "class": "reviewer_change_request",
                    "detail": "The reviewer found a bounded scenario defect.",
                    "required_action": "Correct the scenario objective and rerun all gates.",
                    "attempt": 2,
                    "limit": 2,
                },
            }
            with (
                mock.patch.object(controller, "_plan", return_value=proposal),
                mock.patch.object(controller, "_build_ticket", return_value=ticket),
                mock.patch.object(controller, "_run_secure_ticket", return_value=failed),
                mock.patch.object(
                    controller, "_failed_worktree_identity", return_value="agent/fixture"
                ),
                mock.patch.object(ticket_runner, "load_ticket", return_value=ticket),
            ):
                for index in range(1, 4):
                    run_id = f"abc123def45{index}"
                    controller.store.update(lambda state, value=run_id: state["run"].update({
                        "state": "planning", "run_id": value,
                    }))
                    controller._run(run_id, "sol-low", "Continue safely", True)
                    state = controller.public_state()
                    self.assertEqual(state["autonomous_failure_streak"]["count"], index)
                    self.assertEqual(state["automation"]["enabled"], index < 3)
                    if index == 1:
                        retry = controller._failure_streak_resume_proposal({
                            "resumable_local_work": [{
                                "name": "agent/other", "previous_task_id": "OTHER",
                            }, {
                                "name": "agent/fixture", "previous_task_id": "FIXTURE",
                                "worker": "fast-fix", "objective": "Repair fixture",
                                "allowed_paths": ["addons/example.cfg"],
                                "validation_profile": "static-text", "validation_root": None,
                            }],
                        })
                        self.assertEqual(retry["ticket"]["resume_branch"], "agent/fixture")

            state = controller.public_state()
            self.assertIn("three consecutive failures", state["run"]["summary"])
            self.assertIn("Last failure:", state["run"]["error"])
            self.assertIn("configured failure limit", state["run"]["error"])
            self.assertEqual(state["activity"][-1]["recovery_limit"], 3)


class PublicationGameValidationTests(unittest.TestCase):
    """Publication is irreversible; engine evidence must describe it honestly."""

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "project"
        self.root.mkdir()
        self.git("init", "-b", "main")
        self.git("config", "user.email", "test@example.invalid")
        self.git("config", "user.name", "Validation Test")
        (self.root / ".gitignore").write_text("/agent/runtime/\n/agent/logs/\n", encoding="utf-8")
        self.git("add", ".gitignore")
        self.git("commit", "-m", "fixture")
        self.head = self.git("rev-parse", "HEAD")
        self.queue = ApprovalQueue(self.root)
        self.controller = AutonomyController(
            self.root, ControlStore(self.root / "agent/runtime/control.json"), self.queue
        )
        self.record = {
            "id": "a" * 16, "ticket_id": "HISTORY-TEST", "state": "published",
            "merge_sha": self.head, "changed_paths": [], "dependency_index": 1,
        }
        self.queue._update(lambda state: state["records"].append(dict(self.record)))
        self.engine = {"pass": True, "exit_code": 0, "diagnostic": "", "gameplay_contracts": {"pass": True, "contracts": [{}]}}
        self.retained = {"pass": True, "tickets": [{"pass": True}], "diagnostic": ""}
        self.history = self.root / "agent/runtime/historical-gameplay-validation.json"

    def git(self, *args: str) -> str:
        return subprocess.check_output(["git", *args], cwd=self.root, text=True, stderr=subprocess.DEVNULL).strip()

    def test_success_sets_tested_and_refreshes_stale_history(self) -> None:
        self.history.write_text(json.dumps({"state": "pending_repair", "main_head": "b" * 40}), encoding="utf-8")
        with (
            mock.patch("approval_queue.validate_post_publish_game", return_value=self.engine),
            mock.patch("approval_queue.validate_historical_retention", return_value=self.retained),
        ):
            self.queue._record_post_publish_game_validation(self.record, self.head)
        record = self.queue.public_state()["records"][0]
        self.assertEqual(record["state"], "published_and_tested")
        self.assertEqual(record["post_publish_validation"], "PASS")
        self.assertTrue(record["post_publish_checked_at"])
        self.assertEqual(record["post_publish_evidence"]["exit_code"], 0)
        history = json.loads(self.history.read_text(encoding="utf-8"))
        self.assertEqual((history["state"], history["main_head"]), ("passed", self.head))

    def test_failed_engine_preserves_merge_and_repair_accepts_current_schema(self) -> None:
        engine = {**self.engine, "pass": False, "diagnostic": "Unknown unit type", "failure_class": "addon_validation"}
        with (
            mock.patch("approval_queue.validate_post_publish_game", return_value=engine),
            mock.patch("approval_queue.validate_historical_retention", return_value=self.retained),
        ):
            self.queue._record_post_publish_game_validation(self.record, self.head)
        record = self.queue.record(self.record["id"])
        self.assertEqual(record["state"], "published_test_failed")
        self.assertEqual(record["merge_sha"], self.head)
        self.assertEqual(record["error"], "Unknown unit type")
        proposal = self.controller._post_publish_game_repair_proposal({"main_head": self.head})
        self.assertTrue(proposal["_post_publish_game_repair"])
        self.assertIn("Unknown unit type", proposal["ticket"]["objective"])

    def test_validation_exception_does_not_erase_publication(self) -> None:
        with mock.patch("approval_queue.validate_post_publish_game", side_effect=OSError("unavailable")):
            self.queue._record_post_publish_game_validation(self.record, self.head)
        record = self.queue.record(self.record["id"])
        self.assertEqual(record["state"], "published_test_failed")
        self.assertEqual(record["post_publish_evidence"]["failure_class"], "engine_infrastructure")
        self.queue._record_failure(self.record["id"], "Synchronization failed", "Local update failed")
        self.assertEqual(self.queue.record(self.record["id"])["state"], "published_test_failed")

    def test_changed_main_does_not_receive_a_tested_label(self) -> None:
        with mock.patch("approval_queue.validate_post_publish_game") as probe:
            self.queue._record_post_publish_game_validation(self.record, "b" * 40)
        probe.assert_not_called()
        self.assertEqual(self.queue.record(self.record["id"])["state"], "published_test_failed")

    def test_restart_preserves_merge_but_does_not_infer_test_success(self) -> None:
        self.queue._update_record(self.record["id"], post_publish_validation="RUNNING")
        restarted = ApprovalQueue(self.root)
        record = restarted.record(self.record["id"])
        self.assertEqual(record["state"], "published_test_failed")
        self.assertEqual(record["merge_sha"], self.head)
        self.assertIn("restarted", record["error"])

    def test_engine_unavailability_does_not_generate_a_code_repair(self) -> None:
        with mock.patch("approval_queue.validate_post_publish_game", side_effect=OSError("offline")):
            self.queue._record_post_publish_game_validation(self.record, self.head)
        with self.assertRaisesRegex(ControlError, "engine health"):
            self.controller._post_publish_game_repair_proposal({"main_head": self.head})

    def test_batch_members_keep_the_final_game_result_even_after_merge_exception(self) -> None:
        for final_state, interrupted in (("published_and_tested", False), ("published_test_failed", False), ("published", True)):
            with self.subTest(final_state=final_state):
                records = [
                    {"id": "1" * 16, "ticket_id": "ONE", "state": "ready", "dependency_index": 1, "commit_sha": "a" * 40, "branch": "agent/one", "changed_paths": []},
                    {"id": "2" * 16, "ticket_id": "TWO", "state": "ready", "dependency_index": 2, "commit_sha": "b" * 40, "branch": "agent/two", "changed_paths": [], "depends_on_id": "1" * 16, "depends_on_commit": "a" * 40},
                ]
                self.queue._update(lambda state: state.update(records=records))
                batch_id = self.queue.public_state()["batches"][0]["id"]
                def publish(record):
                    self.queue._update_record(record["id"], state=final_state, merge_sha=self.head,
                        post_publish_validation="PASS" if final_state == "published_and_tested" else "FAIL",
                        post_publish_checked_at="2026-09-07T00:00:00+00:00", error=None if final_state == "published_and_tested" else "Test failed")
                    if interrupted:
                        raise QueueError("Local synchronization failed after the confirmed merge")
                with (
                    mock.patch.object(self.queue, "_worktree", return_value=self.root),
                    mock.patch.object(self.queue, "_is_ancestor", return_value=True),
                    mock.patch.object(self.queue, "_publish", side_effect=publish),
                ):
                    result = self.queue.approve_and_publish_batch(batch_id)
                expected = "published_test_failed" if interrupted else final_state
                self.assertEqual([item["state"] for item in result], [expected, expected])
                self.assertTrue(all(item["merge_sha"] == self.head for item in result))
                self.assertEqual(result[0]["post_publish_validation"], result[1]["post_publish_validation"])

    def test_pending_history_is_rechecked_on_a_new_main_head(self) -> None:
        self.history.write_text(json.dumps({"schema_version": 1, "state": "pending_repair", "main_head": "b" * 40, "evidence": {"diagnostic": "Old failure"}}), encoding="utf-8")
        with (
            mock.patch("autonomy.validate_post_publish_game", return_value=self.engine) as probe,
            mock.patch("autonomy.validate_historical_retention", return_value=self.retained),
        ):
            self.assertIsNone(self.controller._historical_gameplay_repair_proposal({"main_head": self.head}))
            self.assertIsNone(self.controller._historical_gameplay_repair_proposal({"main_head": self.head}))
        probe.assert_called_once()
        record = json.loads(self.history.read_text(encoding="utf-8"))
        self.assertEqual(record["main_head"], self.head)
        self.assertNotIn("Old failure", record["evidence"]["diagnostic"])

    def test_passed_history_is_carried_forward_for_dashboard_only_change(self) -> None:
        previous = self.head
        source = self.root / "agent" / "dashboard" / "example.py"
        source.parent.mkdir(parents=True)
        source.write_text("value = 1\n", encoding="utf-8")
        self.git("add", str(source.relative_to(self.root)))
        self.git("commit", "-m", "dashboard only")
        current = self.git("rev-parse", "HEAD")
        self.history.write_text(json.dumps({
            "schema_version": 1, "state": "passed", "main_head": previous,
            "checked_at": "2026-09-07T00:00:00+00:00", "evidence": {"engine_pass": True},
        }), encoding="utf-8")
        with (
            mock.patch("autonomy.validate_post_publish_game") as engine,
            mock.patch("autonomy.validate_historical_retention") as retention,
        ):
            self.assertIsNone(self.controller._historical_gameplay_repair_proposal({"main_head": current}))
        engine.assert_not_called()
        retention.assert_not_called()
        record = json.loads(self.history.read_text(encoding="utf-8"))
        self.assertEqual(record["main_head"], current)
        self.assertEqual(record["validated_main_head"], previous)
        self.assertEqual(record["equivalent_revision_history"][-1]["non_game_changed_paths"], [
            "agent/dashboard/example.py"
        ])

    def test_game_or_validator_change_forces_real_historical_checks(self) -> None:
        for changed_path in (
            "addons/Star_Wars_Thrawn_Trilogy/scenarios/new.cfg",
            "agent/coordinator/scenario_launch_selftest.py",
            "agent/coordinator/gameplay_contracts.py",
        ):
            with self.subTest(changed_path=changed_path):
                previous = self.git("rev-parse", "HEAD")
                source = self.root / changed_path
                source.parent.mkdir(parents=True, exist_ok=True)
                source.write_text(f"# {changed_path}\n", encoding="utf-8")
                self.git("add", changed_path)
                self.git("commit", "-m", f"change {source.name}")
                current = self.git("rev-parse", "HEAD")
                self.history.write_text(json.dumps({
                    "schema_version": 1, "state": "passed", "main_head": previous,
                    "evidence": {"engine_pass": True},
                }), encoding="utf-8")
                with (
                    mock.patch("autonomy.validate_post_publish_game", return_value=self.engine) as engine,
                    mock.patch("autonomy.validate_historical_retention", return_value=self.retained) as retention,
                ):
                    self.assertIsNone(self.controller._historical_gameplay_repair_proposal({"main_head": current}))
                engine.assert_called_once()
                retention.assert_called_once()

    def test_batch_merge_and_validation_are_atomic_across_restart(self) -> None:
        members = [
            {"id": "1" * 16, "commit_sha": "a" * 40, "state": "publishing"},
            {"id": "2" * 16, "commit_sha": "b" * 40, "state": "publishing"},
        ]
        self.queue._update(lambda state: state.update(records=members))
        record = {**members[-1], "batch_members": [dict(member) for member in members]}
        self.queue._update_publication_records(record, state="published", merge_sha=self.head,
                                               post_publish_validation="RUNNING", pr_number=123)
        restarted = ApprovalQueue(self.root)
        for member in members:
            saved = restarted.record(member["id"])
            self.assertEqual(saved["state"], "published_test_failed")
            self.assertEqual(saved["merge_sha"], self.head)
            self.assertEqual(saved["pr_number"], 123)
        restarted._update_publication_records(record, state="published_and_tested", post_publish_validation="PASS")
        restarted_again = ApprovalQueue(self.root)
        self.assertTrue(all(item["state"] == "published_and_tested" for item in restarted_again.read()["records"]))

    def test_batch_update_rejects_changed_identity_without_partial_writes(self) -> None:
        original = self.queue.read()
        record = {**self.record, "batch_members": [dict(self.record), {"id": "b" * 16, "commit_sha": "c" * 40}]}
        with self.assertRaisesRegex(QueueError, "identity changed"):
            self.queue._update_publication_records(record, state="published_and_tested")
        self.assertEqual(self.queue.read(), original)

    def test_refreshed_failure_contains_current_diagnostic(self) -> None:
        self.history.write_text(json.dumps({"state": "pending_repair", "main_head": "b" * 40}), encoding="utf-8")
        with (
            mock.patch("autonomy.validate_post_publish_game", return_value={**self.engine, "pass": False, "diagnostic": "Current engine failure"}),
            mock.patch("autonomy.validate_historical_retention", return_value=self.retained),
        ):
            proposal = self.controller._historical_gameplay_repair_proposal({"main_head": self.head})
        self.assertIn("Current engine failure", proposal["ticket"]["objective"])
        ticket = self.controller._build_ticket("historytest1", proposal, fresh_start_authorized=True)
        self.assertIs(ticket["historical_repair"], True)

    def empty_repair(self) -> tuple[dict, dict, dict, Path]:
        worktree = self.root.parent / "project-worktrees" / "history"
        self.git("worktree", "add", "-b", "agent/history", str(worktree), "main")
        ticket = {"task_id": "HISTORY-TEST", "historical_repair": True}
        failure = {"class": "implementation_or_validation_failure", "detail": "no repository change was produced"}
        result = {"task_id": ticket["task_id"], "branch": "agent/history", "worktree": str(worktree), "implementation_exit_code": 0, "final_verdict": "FAIL"}
        return ticket, {"return_code": 1, "failure": failure}, result, worktree

    def test_empty_repair_resolves_only_after_both_current_checks_pass(self) -> None:
        ticket, secure, result, _ = self.empty_repair()
        with (
            mock.patch.object(self.controller, "_latest_ticket_result", return_value=result),
            mock.patch("autonomy.validate_post_publish_game", return_value=self.engine),
            mock.patch("autonomy.validate_historical_retention", return_value=self.retained),
        ):
            self.assertTrue(self.controller._resolve_empty_historical_repair(ticket, secure))
        self.assertTrue(self.controller._resolved_historical_worktree("agent/history", self.head))
        self.assertFalse(self.controller._resolved_historical_worktree("agent/history", "b" * 40))
        self.assertEqual(result["final_verdict"], "FAIL")
        self.assertEqual(len(self.queue.read()["records"]), 1)

    def test_empty_repair_is_not_resolved_while_engine_still_fails(self) -> None:
        ticket, secure, result, _ = self.empty_repair()
        with (
            mock.patch.object(self.controller, "_latest_ticket_result", return_value=result),
            mock.patch("autonomy.validate_post_publish_game", return_value={**self.engine, "pass": False}),
            mock.patch("autonomy.validate_historical_retention", return_value=self.retained),
        ):
            self.assertFalse(self.controller._resolve_empty_historical_repair(ticket, secure))
        self.assertFalse(self.controller._resolved_historical_worktree("agent/history", self.head))

    def test_dirty_worktree_cannot_be_retired_as_resolved(self) -> None:
        ticket, secure, result, worktree = self.empty_repair()
        (worktree / "unfinished.txt").write_text("preserve me", encoding="utf-8")
        with (
            mock.patch.object(self.controller, "_latest_ticket_result", return_value=result),
            mock.patch("autonomy.validate_post_publish_game") as probe,
        ):
            self.assertFalse(self.controller._resolve_empty_historical_repair(ticket, secure))
        probe.assert_not_called()
        self.assertTrue((worktree / "unfinished.txt").exists())

    def test_unrelated_empty_ticket_does_not_skip_failed_gates(self) -> None:
        ticket, secure, _, _ = self.empty_repair()
        ticket.pop("historical_repair")
        with mock.patch.object(self.controller, "_latest_ticket_result") as evidence:
            self.assertFalse(self.controller._resolve_empty_historical_repair(ticket, secure))
        evidence.assert_not_called()


if __name__ == "__main__":
    unittest.main()
