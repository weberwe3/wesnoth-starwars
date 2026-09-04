#!/usr/bin/env python3

from __future__ import annotations

import json
import http.client
from pathlib import Path
import sys
import tempfile
import threading
import unittest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "agent" / "coordinator"))

from runtime_status import RuntimeStatus, default_state  # noqa: E402
from coordination_control import ControlStore  # noqa: E402
sys.path.insert(0, str(ROOT / "agent" / "dashboard"))
from autonomy import AutonomyController, ControlError  # noqa: E402
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
    def test_mode_switch_is_allowlisted_and_persistent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = ControlStore(Path(directory) / "control.json")
            controller = AutonomyController(ROOT, store)
            controller.set_mode("sol-high")
            public = controller.public_state()
            self.assertEqual(public["mode"], "sol-high")
            self.assertEqual(public["assignment"]["model"], "GPT-5.6 Sol")
            self.assertEqual(public["assignment"]["effort"], "high")
            self.assertFalse(public["capabilities"]["merge"])
            with self.assertRaises(ControlError):
                controller.set_mode("danger-full-access")

    def test_sol_ticket_cannot_target_protected_paths(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            controller = AutonomyController(
                ROOT,
                ControlStore(Path(directory) / "control.json"),
            )
            proposal = {
                "action": "run_ticket",
                "summary": "Unsafe",
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


if __name__ == "__main__":
    unittest.main()
