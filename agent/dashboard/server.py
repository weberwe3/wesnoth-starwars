#!/usr/bin/env python3

"""Localhost-only, read-only status dashboard server."""

from __future__ import annotations

import argparse
import datetime as dt
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import sys
from urllib.parse import urlsplit


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
STATIC = HERE / "static"
sys.path.insert(0, str(ROOT / "agent" / "coordinator"))

from runtime_status import default_state, runtime_status_path  # noqa: E402


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
        ("events", ("at", "kind", "level", "message", "source", "target"), 200),
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
    server_version = "WesnothDashboard/1"

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
        allowed_hosts = {
            f"127.0.0.1:{self.server.server_port}",  # type: ignore[attr-defined]
            "127.0.0.1",
        }
        if self.headers.get("Host", "") not in allowed_hosts:
            self.send_error(HTTPStatus.BAD_REQUEST, "Invalid host")
            return
        path = urlsplit(self.path).path
        if path == "/api/status":
            self._status()
            return
        if path == "/healthz":
            self._json({"ok": True, "bind": "127.0.0.1"})
            return
        if path == "/":
            self.path = "/index.html"
        super().do_GET()

    def _status(self) -> None:
        status_file = self.server.status_file  # type: ignore[attr-defined]
        try:
            state = json.loads(status_file.read_text(encoding="utf-8"))
        except (FileNotFoundError, OSError, ValueError):
            state = default_state(ROOT)
            state["system"]["state"] = "standby"
            state["events"][0]["message"] = "Waiting for coordinator telemetry"
        self._json(public_state(state))

    def _json(self, data: object) -> None:
        payload = json.dumps(data, separators=(",", ":")).encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, format: str, *args: object) -> None:
        if self.path not in {"/api/status", "/healthz"}:
            super().log_message(format, *args)


def main() -> int:
    parser = argparse.ArgumentParser(description="Wesnoth Agent Manager dashboard")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error("port must be between 1024 and 65535")

    status_file = runtime_status_path(ROOT).resolve()
    server = create_server(args.port, status_file)
    print(f"Wesnoth Agent Manager: http://127.0.0.1:{args.port}")
    print(f"Telemetry: {status_file}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


def create_server(port: int, status_file: Path) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer(("127.0.0.1", port), DashboardHandler)
    server.status_file = status_file.resolve()  # type: ignore[attr-defined]
    return server


if __name__ == "__main__":
    raise SystemExit(main())
