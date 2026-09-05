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
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "agent" / "coordinator"))

from runtime_status import RuntimeStatus, default_state  # noqa: E402
from coordination_control import ControlStore  # noqa: E402
import recovery_policy  # noqa: E402
import model_policy  # noqa: E402
import ticket_runner  # noqa: E402
sys.path.insert(0, str(ROOT / "agent" / "dashboard"))
from autonomy import (  # noqa: E402
    AutonomyController,
    ControlError,
    TICKET_SCHEMA,
    validate_strict_output_schema,
)
import approval_queue  # noqa: E402
from approval_queue import ApprovalQueue, QueueError  # noqa: E402
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

    def test_dirty_outdated_local_remnant_is_preserved_and_blocked(self) -> None:
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
            original_head = git(worktree, "rev-parse", "HEAD")

            with self.assertRaisesRegex(SystemExit, "uncommitted changes"):
                ticket_runner.prepare_local_resume(root, worktree)
            self.assertEqual(git(worktree, "rev-parse", "HEAD"), original_head)
            self.assertEqual((worktree / "partial.txt").read_text(), "partial\n")

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

    def test_terra_fallback_is_single_and_implementer_only(self) -> None:
        self.assertTrue(recovery_policy.should_use_terra_fallback("implementer", 1, False))
        self.assertFalse(recovery_policy.should_use_terra_fallback("implementer", 1, True))
        self.assertFalse(recovery_policy.should_use_terra_fallback("fast-fix", 1, False))
        self.assertFalse(recovery_policy.should_use_terra_fallback("implementer", 0, False))

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

    def test_control_bridge_forwards_verified_codex_path(self) -> None:
        text = (ROOT / "agent" / "dashboard" / "control-bridge.ps1").read_text(
            encoding="utf-8"
        )
        self.assertIn('EnvironmentVariables["WESNOTH_CODEX_EXE"]', text)
        self.assertIn('forwardWslEnv += "WESNOTH_CODEX_EXE"', text)

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
        self.assertIsNone(model_policy.MODEL_RPM["google/gemini-3.8-flash"])

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
        responses: list[tuple[int, str]],
        *,
        google_available: bool = True,
        terra_response: tuple[int, str] = (1, "Terra unavailable"),
        terra_implemented: bool = False,
    ) -> tuple[dict, list[str]]:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            log_dir = base / "logs"
            log_dir.mkdir()
            status = mock.Mock()
            invoked: list[str] = []

            def invoke(**kwargs):
                invoked.append(kwargs["agent"])
                return responses.pop(0)

            policy = model_policy.ModelPolicy(base / "runtime")
            run_sequence = policy.begin_run("REVIEW-CHAIN")
            with mock.patch.object(ticket_runner, "run_validation", return_value={"pass": True}), mock.patch.object(
                ticket_runner, "invoke_agent", side_effect=invoke
            ), mock.patch.object(ticket_runner, "invoke_terra", return_value=terra_response):
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
                    google_available=google_available,
                    implementer_rc=0,
                    attempt=0,
                    policy=policy,
                    run_sequence=run_sequence,
                    terra_implemented=terra_implemented,
                )
            return result, invoked

    def test_nemotron_is_primary_reviewer(self) -> None:
        result, invoked = self._evaluate([
            (0, "VERDICT: PASS"),
            (0, "VERDICT: APPROVE"),
        ])
        self.assertTrue(result["pass"])
        self.assertEqual(
            result["reviewer_used"],
            "cloudflare-workers-ai/@cf/nvidia/nemotron-3-120b-a12b",
        )
        self.assertEqual(invoked, ["tester", "reviewer"])
        self.assertIsNone(result["reviewer_intermediate_exit_code"])

    def test_gemini_38_runs_after_non_decisive_nemotron(self) -> None:
        result, invoked = self._evaluate([
            (0, "VERDICT: PASS"),
            (1, "primary infrastructure failure"),
            (0, "VERDICT: APPROVE"),
        ])
        self.assertTrue(result["pass"])
        self.assertEqual(result["reviewer_used"], "google/gemini-3.8-flash")
        self.assertEqual(invoked, ["tester", "reviewer", "reviewer-intermediate"])
        self.assertIsNone(result["reviewer_fallback_exit_code"])

    def test_gemini_36_runs_after_nemotron_and_gemini_38_are_non_decisive(self) -> None:
        result, invoked = self._evaluate([
            (0, "VERDICT: PASS"),
            (1, "primary infrastructure failure"),
            (1, "intermediate infrastructure failure"),
            (0, "VERDICT: APPROVE"),
        ])
        self.assertTrue(result["pass"])
        self.assertEqual(result["reviewer_used"], "google/gemini-3.6-flash")
        self.assertEqual(
            invoked,
            ["tester", "reviewer", "reviewer-intermediate", "reviewer-fallback"],
        )

    def test_intermediate_request_changes_is_authoritative(self) -> None:
        result, invoked = self._evaluate([
            (0, "VERDICT: PASS"),
            (1, "primary infrastructure failure"),
            (0, "VERDICT: REQUEST_CHANGES"),
        ])
        self.assertFalse(result["pass"])
        self.assertEqual(result["reviewer_used"], "google/gemini-3.8-flash")
        self.assertEqual(invoked, ["tester", "reviewer", "reviewer-intermediate"])
        self.assertIsNone(result["reviewer_fallback_exit_code"])

    def test_terra_runs_after_three_non_decisive_reviewers(self) -> None:
        result, invoked = self._evaluate(
            [
                (0, "VERDICT: PASS"),
                (1, "primary infrastructure failure"),
                (1, "intermediate infrastructure failure"),
                (1, "fallback infrastructure failure"),
            ],
            terra_response=(0, "VERDICT: APPROVE"),
        )
        self.assertTrue(result["pass"])
        self.assertEqual(result["reviewer_used"], "openai/gpt-5.6-terra")
        self.assertEqual(result["reviewer_terra_exit_code"], 0)
        self.assertEqual(
            invoked,
            ["tester", "reviewer", "reviewer-intermediate", "reviewer-fallback"],
        )

    def test_terra_cannot_review_its_own_implementation(self) -> None:
        result, _ = self._evaluate(
            [
                (0, "VERDICT: PASS"),
                (1, "primary infrastructure failure"),
                (1, "intermediate infrastructure failure"),
                (1, "fallback infrastructure failure"),
            ],
            terra_response=(0, "VERDICT: APPROVE"),
            terra_implemented=True,
        )
        self.assertFalse(result["pass"])
        self.assertIsNone(result["reviewer_terra_exit_code"])

    def test_missing_google_credential_still_runs_primary_nemotron(self) -> None:
        result, invoked = self._evaluate(
            [(0, "VERDICT: PASS"), (0, "VERDICT: APPROVE")],
            google_available=False,
        )
        self.assertTrue(result["pass"])
        self.assertEqual(invoked, ["tester", "reviewer"])
        self.assertEqual(result["reviewer_used"], "cloudflare-workers-ai/@cf/nvidia/nemotron-3-120b-a12b")
        self.assertEqual(result["reviewer_primary_exit_code"], 0)
        self.assertIsNone(result["reviewer_intermediate_exit_code"])
        self.assertIsNone(result["reviewer_fallback_exit_code"])


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


if __name__ == "__main__":
    unittest.main()
