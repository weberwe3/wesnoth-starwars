#!/usr/bin/env python3

"""Loopback dashboard server with authenticated Windows LAN access."""

from __future__ import annotations

import argparse
import datetime as dt
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import ipaddress
import os
from pathlib import Path
import secrets
import sys
import threading
from urllib.parse import urlsplit


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
STATIC = HERE / "static"
sys.path.insert(0, str(ROOT / "agent" / "coordinator"))

from coordination_control import ControlStore, control_state_path  # noqa: E402
from runtime_status import default_state, runtime_status_path  # noqa: E402
from autonomy import AutonomyController, ControlError  # noqa: E402
from approval_queue import QueueError  # noqa: E402


def public_state(state: object) -> dict:
    """Allowlist the telemetry schema; unknown fields never reach the browser."""
    fallback = default_state(ROOT)
    if not isinstance(state, dict):
        return fallback
    public = {
        "schema_version": state.get("schema_version"),
        "updated_at": state.get("updated_at"),
        "system": {},
        "job": None,
        "active_transfer": None,
        "workers": {},
        "gates": [],
        "routing_history": [],
        "events": [],
    }
    system = state.get("system")
    if isinstance(system, dict):
        for key in ("state", "localhost_only", "credential_values_exposed"):
            public["system"][key] = system.get(key)
    job = state.get("job")
    if isinstance(job, dict):
        public["job"] = {key: job.get(key) for key in (
            "task_id", "objective", "state", "stage", "started_at",
            "completed_at", "branch", "worktree", "validation_profile", "result",
        )}
    transfer = state.get("active_transfer")
    if isinstance(transfer, dict):
        public["active_transfer"] = {key: transfer.get(key) for key in ("from", "to", "started_at", "message")}
    workers = state.get("workers")
    if isinstance(workers, dict):
        for role in fallback["workers"]:
            worker = workers.get(role)
            if isinstance(worker, dict):
                public["workers"][role] = {key: worker.get(key) for key in (
                    "label", "provider", "model", "assignment_error", "state",
                    "task", "started_at", "error",
                )}
            else:
                public["workers"][role] = fallback["workers"][role]
    for collection, keys, maximum in (
        ("gates", ("name", "state", "detail", "at"), 30),
        ("routing_history", ("at", "from", "to", "message"), 100),
        (
            "events",
            (
                "at", "kind", "level", "message", "source", "target", "detail",
                "failure_class", "required_action", "recovery_attempt", "recovery_limit",
            ),
            200,
        ),
    ):
        values = state.get(collection)
        if isinstance(values, list):
            public[collection] = [
                {key: item.get(key) for key in keys}
                for item in values[-maximum:]
                if isinstance(item, dict)
            ]
    try:
        updated = dt.datetime.fromisoformat(str(public["updated_at"]))
        age = max(0, int((dt.datetime.now(dt.timezone.utc) - updated).total_seconds()))
    except (TypeError, ValueError):
        age = -1
    public["system"]["telemetry_age_seconds"] = age
    if public["job"] and public["job"].get("state") == "running" and (age < 0 or age > 300):
        public["system"]["state"] = "stale"
    return public


class DashboardHandler(SimpleHTTPRequestHandler):
    server_version = "WesnothDashboard/2"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(STATIC), **kwargs)

    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; img-src 'self'; style-src 'self'; "
            "script-src 'self'; connect-src 'self'; frame-ancestors 'none'",
        )
        super().end_headers()

    def do_GET(self) -> None:  # noqa: N802
        if not self._valid_host():
            self.send_error(HTTPStatus.BAD_REQUEST, "Invalid host")
            return
        path = urlsplit(self.path).path
        remote_view = self.headers.get("X-Wesnoth-LAN-View") == "1"
        if remote_view and path in {"/api/status", "/api/control"} and not self._valid_lan_token():
            self._json({"error": "This device needs the secure LAN access link"}, HTTPStatus.FORBIDDEN)
            return
        if path == "/api/status":
            self._status()
            return
        if path == "/healthz":
            self._json({
                "ok": True,
                "bind": "127.0.0.1",
                "lan_url": self.server.lan_url,  # type: ignore[attr-defined]
            })
            return
        if path == "/api/control":
            state = self.server.controller.public_state()  # type: ignore[attr-defined]
            state["access"] = self._access_state(remote_view)
            state["csrf_token"] = self.server.csrf_token  # type: ignore[attr-defined]
            self._json(state)
            return
        if path == "/":
            self.path = "/index.html"
        super().do_GET()

    def do_POST(self) -> None:  # noqa: N802
        if not self._valid_host():
            self.send_error(HTTPStatus.BAD_REQUEST, "Invalid host")
            return
        if urlsplit(self.path).path != "/api/control":
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        remote_view = self.headers.get("X-Wesnoth-LAN-View") == "1"
        if remote_view and not self._valid_lan_token():
            self._json({"error": "Invalid LAN access token"}, HTTPStatus.FORBIDDEN)
            return
        expected_origin = (
            self.server.lan_url  # type: ignore[attr-defined]
            if remote_view else f"http://127.0.0.1:{self.server.server_port}"  # type: ignore[attr-defined]
        )
        if self.headers.get("Origin") != expected_origin:
            self._json({"error": "Invalid origin"}, HTTPStatus.FORBIDDEN)
            return
        if not secrets.compare_digest(
            self.headers.get("X-Wesnoth-CSRF", ""),
            self.server.csrf_token,  # type: ignore[attr-defined]
        ):
            self._json({"error": "Invalid control token"}, HTTPStatus.FORBIDDEN)
            return
        if self.headers.get_content_type() != "application/json":
            self._json({"error": "JSON required"}, HTTPStatus.UNSUPPORTED_MEDIA_TYPE)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = -1
        if length < 2 or length > 4096:
            self._json({"error": "Invalid request size"}, HTTPStatus.BAD_REQUEST)
            return
        try:
            data = json.loads(self.rfile.read(length))
        except (UnicodeDecodeError, json.JSONDecodeError):
            self._json({"error": "Invalid JSON"}, HTTPStatus.BAD_REQUEST)
            return
        if not isinstance(data, dict):
            self._json({"error": "JSON object required"}, HTTPStatus.BAD_REQUEST)
            return
        controller = self.server.controller  # type: ignore[attr-defined]
        shutdown_requested = False
        try:
            if data.get("action") == "set_mode" and set(data) == {"action", "mode"}:
                controller.set_mode(data.get("mode"))
            elif data.get("action") == "run" and set(data) == {"action", "brief"}:
                controller.start(data.get("brief") if isinstance(data.get("brief"), str) else "")
            elif data.get("action") == "set_automation" and set(data) == {
                "action", "enabled", "brief",
            }:
                if not isinstance(data.get("enabled"), bool) or not isinstance(data.get("brief"), str):
                    raise ControlError("Invalid automation request")
                controller.set_automation(data["enabled"], data["brief"])
            elif data.get("action") == "approve_publish" and set(data) == {
                "action", "record_id", "commit_sha",
            }:
                if not isinstance(data.get("record_id"), str) or not isinstance(data.get("commit_sha"), str):
                    raise ControlError("Invalid publication request")
                controller.approve_publish(data["record_id"], data["commit_sha"])
            elif data.get("action") in {"recode_ticket", "remove_failed_ticket"} and set(data) == {
                "action", "record_id", "commit_sha",
            }:
                if not isinstance(data.get("record_id"), str) or not isinstance(data.get("commit_sha"), str):
                    raise ControlError("Invalid failed-ticket request")
                if data["action"] == "recode_ticket":
                    controller.recode_failed_ticket(data["record_id"], data["commit_sha"])
                else:
                    controller.remove_failed_ticket(data["record_id"], data["commit_sha"])
            elif data == {"action": "shutdown"}:
                state = controller.public_state()
                if state.get("run", {}).get("state") in {
                    "planning", "executing", "publishing",
                }:
                    raise ControlError(
                        "An active operation must reach a safe stopping point before shutdown"
                    )
                shutdown_requested = True
            else:
                raise ControlError("Unsupported control action")
        except (ControlError, QueueError) as exc:
            self._json({"error": str(exc)}, HTTPStatus.CONFLICT)
            return
        response = controller.public_state()
        response["access"] = self._access_state(remote_view)
        if shutdown_requested:
            response["shutdown"] = "accepted"
            self.server.exit_requested = True  # type: ignore[attr-defined]
        self._json(response, HTTPStatus.ACCEPTED)
        if shutdown_requested:
            threading.Thread(
                target=self.server.shutdown,  # type: ignore[attr-defined]
                name="dashboard-clean-shutdown",
                daemon=True,
            ).start()

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_error(HTTPStatus.METHOD_NOT_ALLOWED)

    def _valid_host(self) -> bool:
        return self.headers.get("Host", "") in {
            f"127.0.0.1:{self.server.server_port}",  # type: ignore[attr-defined]
            "127.0.0.1",
        }

    def _valid_lan_token(self) -> bool:
        expected = self.server.lan_token  # type: ignore[attr-defined]
        return bool(expected) and secrets.compare_digest(
            self.headers.get("X-Wesnoth-LAN-Token", ""), expected,
        )

    def _access_state(self, remote_view: bool) -> dict:
        lan_url = self.server.lan_url  # type: ignore[attr-defined]
        return {
            "remote": remote_view,
            "lan_url": lan_url,
            "lan_proxy_online": (
                ROOT / "agent" / "runtime" / "dashboard-lan-proxy.ready"
            ).is_file(),
            "lan_access_url": (
                "" if remote_view or not lan_url
                else f"{lan_url}/#access={self.server.lan_token}"  # type: ignore[attr-defined]
            ),
            "shutdown_available": True,
        }

    def _status(self) -> None:
        status_file = self.server.status_file  # type: ignore[attr-defined]
        try:
            state = json.loads(status_file.read_text(encoding="utf-8"))
        except (FileNotFoundError, OSError, ValueError):
            state = default_state(ROOT)
            state["system"]["state"] = "standby"
            state["events"][0]["message"] = "Waiting for coordinator telemetry"
        self._json(public_state(state))

    def _json(self, data: object, status: HTTPStatus = HTTPStatus.OK) -> None:
        payload = json.dumps(data, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, format: str, *args: object) -> None:
        if self.path not in {"/api/status", "/api/control", "/healthz"}:
            super().log_message(format, *args)


def main() -> int:
    parser = argparse.ArgumentParser(description="Wesnoth Agent Manager dashboard")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--lan-url", default="")
    parser.add_argument("--lan-token-file", type=Path)
    parser.add_argument("--session-id", default="")
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error("port must be between 1024 and 65535")
    if args.lan_url:
        parsed_lan = urlsplit(args.lan_url)
        try:
            lan_address = ipaddress.ip_address(parsed_lan.hostname or "")
        except ValueError:
            parser.error("lan-url must contain a private IPv4 address")
        if (
            parsed_lan.scheme != "http" or parsed_lan.path not in {"", "/"}
            or parsed_lan.query or parsed_lan.fragment or parsed_lan.port is None
            or lan_address.version != 4 or not lan_address.is_private
            or lan_address.is_loopback
        ):
            parser.error("lan-url must contain a private non-loopback IPv4 address and port")
    if args.session_id and (
        not 8 <= len(args.session_id) <= 80
        or not all(character.isalnum() or character == "-" for character in args.session_id)
    ):
        parser.error("session-id contains unsupported characters")
    lan_token = ""
    if args.lan_url:
        if args.lan_token_file is None:
            parser.error("lan-token-file is required with lan-url")
        try:
            lan_token = args.lan_token_file.read_text(encoding="utf-8").strip()
        except OSError as exc:
            parser.error(f"could not read lan-token-file: {exc}")
        if not 32 <= len(lan_token) <= 128 or not all(
            character.isalnum() or character in "_-" for character in lan_token
        ):
            parser.error("lan-token-file is invalid")

    status_file = runtime_status_path(ROOT).resolve()
    server = create_server(
        args.port, status_file, lan_url=args.lan_url, lan_token=lan_token,
        session_id=args.session_id,
    )
    print(f"Wesnoth Agent Manager: http://127.0.0.1:{args.port}")
    print(f"Telemetry: {status_file}")
    print("Control: governed manual or continuous ticket coordination")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        runtime = ROOT / "agent" / "runtime"
        pid_file = runtime / "dashboard.pid"
        try:
            if pid_file.read_text(encoding="utf-8").strip() == str(os.getpid()):
                for name in ("dashboard.pid", "dashboard.commit", "dashboard.session"):
                    (runtime / name).unlink(missing_ok=True)
        except OSError:
            pass
        if server.exit_requested and args.session_id:  # type: ignore[attr-defined]
            for name in ("dashboard.shutdown", f"dashboard.shutdown.{args.session_id}"):
                marker = runtime / name
                marker.write_text("clean\n", encoding="utf-8")
                os.chmod(marker, 0o600)
    return 0


def create_server(
    port: int,
    status_file: Path,
    control_file: Path | None = None,
    lan_url: str = "",
    lan_token: str = "",
    session_id: str = "",
) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer(("127.0.0.1", port), DashboardHandler)
    server.status_file = status_file.resolve()  # type: ignore[attr-defined]
    store = ControlStore(control_file or control_state_path(ROOT))
    queue = None
    if control_file is not None:
        from approval_queue import ApprovalQueue
        queue = ApprovalQueue(ROOT, control_file.resolve().parent / "approval-queue.json")
    server.controller = AutonomyController(ROOT, store, queue)  # type: ignore[attr-defined]
    server.csrf_token = secrets.token_urlsafe(32)  # type: ignore[attr-defined]
    server.lan_url = lan_url  # type: ignore[attr-defined]
    server.lan_token = lan_token  # type: ignore[attr-defined]
    server.session_id = session_id  # type: ignore[attr-defined]
    server.exit_requested = False  # type: ignore[attr-defined]
    server.daemon_threads = True
    return server


if __name__ == "__main__":
    raise SystemExit(main())
