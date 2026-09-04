#!/usr/bin/env python3

"""Structured, secret-free runtime telemetry for the local dashboard."""

from __future__ import annotations

import datetime as dt
import json
import os
from pathlib import Path
import tempfile
from typing import Any


ROLE_ASSIGNMENTS = {
    "coordinator": {
        "label": "Coordinator",
        "provider": "Local process",
        "model": "No LLM — deterministic Python",
    },
    "implementer": {
        "label": "Implementer",
        "provider": "Unknown",
        "model": "Unknown — configuration not verified",
    },
    "fast-fix": {
        "label": "Fast-Fix",
        "provider": "Unknown",
        "model": "Unknown — configuration not verified",
    },
    "validation": {
        "label": "Deterministic Validation",
        "provider": "Local",
        "model": "Python validation gates",
    },
    "tester": {
        "label": "Tester",
        "provider": "Unknown",
        "model": "Unknown — configuration not verified",
    },
    "reviewer": {
        "label": "Reviewer",
        "provider": "Unknown",
        "model": "Unknown — configuration not verified",
    },
    "reviewer-fallback": {
        "label": "Reviewer-Fallback",
        "provider": "Unknown",
        "model": "Unknown — configuration not verified",
    },
}


def _utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def _configured_assignments(root: Path | None) -> dict[str, dict[str, str]]:
    assignments = {key: dict(value) for key, value in ROLE_ASSIGNMENTS.items()}
    if root is None:
        return assignments
    role_files = {
        "implementer": "implementer.md",
        "fast-fix": "fast-fix.md",
        "tester": "tester.md",
        "reviewer": "reviewer.md",
        "reviewer-fallback": "reviewer-fallback.md",
    }
    provider_names = {
        "groq": "Groq",
        "opencode": "OpenCode Zen",
        "cloudflare-workers-ai": "Cloudflare Workers AI",
        "google": "Google",
    }
    for role, filename in role_files.items():
        try:
            lines = (root / ".opencode" / "agents" / filename).read_text(
                encoding="utf-8"
            ).splitlines()
            configured = next(
                line.split(":", 1)[1].strip()
                for line in lines
                if line.startswith("model:")
            )
        except (FileNotFoundError, OSError, StopIteration):
            assignments[role]["assignment_error"] = True
            continue
        provider, _, model = configured.partition("/")
        assignments[role]["provider"] = provider_names.get(provider, provider)
        assignments[role]["model"] = model or configured
        assignments[role]["assignment_error"] = False
    return assignments


def default_state(root: Path | None = None) -> dict[str, Any]:
    now = _utc_now()
    return {
        "schema_version": 1,
        "updated_at": now,
        "system": {
            "state": "attention" if any(
                assignment.get("assignment_error")
                for assignment in _configured_assignments(root).values()
            ) else "ready",
            "localhost_only": True,
            "credential_values_exposed": False,
        },
        "job": None,
        "active_transfer": None,
        "workers": {
            key: {
                **assignment,
                "state": "idle",
                "task": "Awaiting work",
                "started_at": None,
                "error": None,
            }
            for key, assignment in _configured_assignments(root).items()
        },
        "gates": [],
        "routing_history": [],
        "events": [
            {
                "at": now,
                "kind": "system",
                "level": "info",
                "message": "Dashboard telemetry ready",
            }
        ],
    }


class RuntimeStatus:
    """Atomically publishes a bounded status snapshot for read-only consumers."""

    def __init__(self, path: Path):
        self.path = path.resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.state = default_state(self.path.parents[2])
        self._write()

    def _write(self) -> None:
        self.state["updated_at"] = _utc_now()
        payload = json.dumps(self.state, indent=2) + "\n"
        fd, temporary = tempfile.mkstemp(
            prefix=".dashboard-state-",
            suffix=".json",
            dir=self.path.parent,
            text=True,
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.chmod(temporary, 0o600)
            os.replace(temporary, self.path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    def event(
        self,
        message: str,
        *,
        kind: str = "activity",
        level: str = "info",
        source: str | None = None,
        target: str | None = None,
        detail: str | None = None,
        failure_class: str | None = None,
        required_action: str | None = None,
        recovery_attempt: int | None = None,
        recovery_limit: int | None = None,
    ) -> None:
        record = {
            "at": _utc_now(),
            "kind": kind,
            "level": level,
            "message": message,
        }
        if source:
            record["source"] = source
        if target:
            record["target"] = target
        if detail:
            record["detail"] = detail[:2000]
        if failure_class:
            record["failure_class"] = failure_class[:80]
        if required_action:
            record["required_action"] = required_action[:1000]
        if recovery_attempt is not None:
            record["recovery_attempt"] = recovery_attempt
        if recovery_limit is not None:
            record["recovery_limit"] = recovery_limit
        self.state["events"] = (self.state["events"] + [record])[-200:]
        self._write()

    def begin_job(
        self,
        *,
        task_id: str,
        objective: str,
        branch: str,
        worktree: Path,
        validation_profile: str,
    ) -> None:
        now = _utc_now()
        self.state["job"] = {
            "task_id": task_id,
            "objective": objective,
            "state": "running",
            "stage": "coordinator",
            "started_at": now,
            "completed_at": None,
            "branch": branch,
            "worktree": worktree.name,
            "validation_profile": validation_profile,
            "result": None,
        }
        self.set_worker("coordinator", "active", "Preparing isolated worktree")
        self.event(f"{task_id} started", source="coordinator")

    def set_worker(
        self,
        role: str,
        state: str,
        task: str,
        *,
        error: str | None = None,
    ) -> None:
        worker = self.state["workers"][role]
        was_active = worker["state"] == "active"
        worker.update({"state": state, "task": task, "error": error})
        if state == "active" and not was_active:
            worker["started_at"] = _utc_now()
        elif state != "active":
            worker["started_at"] = None
        if self.state["job"] and state == "active":
            self.state["job"]["stage"] = role
        self._write()

    def set_assignment(self, role: str, provider: str, model: str) -> None:
        """Publish the exact active assignment without exposing configuration."""

        self.state["workers"][role].update({
            "provider": provider[:80],
            "model": model[:160],
            "assignment_error": False,
        })
        self._write()

    def handoff(self, source: str, target: str, message: str) -> None:
        at = _utc_now()
        self.state["active_transfer"] = {
            "from": source,
            "to": target,
            "started_at": at,
            "message": message,
        }
        self.state["routing_history"] = (
            self.state["routing_history"]
            + [{"at": at, "from": source, "to": target, "message": message}]
        )[-100:]
        self.event(message, kind="handoff", source=source, target=target)

    def clear_handoff(self) -> None:
        self.state["active_transfer"] = None
        self._write()

    def gate(self, name: str, state: str, detail: str) -> None:
        gates = [gate for gate in self.state["gates"] if gate["name"] != name]
        gates.append({"name": name, "state": state, "detail": detail, "at": _utc_now()})
        self.state["gates"] = gates
        self._write()

    def finish(
        self,
        passed: bool,
        message: str,
        *,
        detail: str | None = None,
        failure_class: str | None = None,
        required_action: str | None = None,
        recovery_attempt: int | None = None,
        recovery_limit: int | None = None,
    ) -> None:
        now = _utc_now()
        for worker in self.state["workers"].values():
            if worker["state"] == "active":
                worker["state"] = "idle" if passed else "error"
                worker["started_at"] = None
        if self.state["job"]:
            self.state["job"].update({
                "state": "passed" if passed else "failed",
                "result": "PASS" if passed else "FAIL",
                "completed_at": now,
            })
        self.state["active_transfer"] = None
        self.state["system"]["state"] = "ready" if passed else "attention"
        self.event(
            message,
            kind="result",
            level="success" if passed else "error",
            detail=detail,
            failure_class=failure_class,
            required_action=required_action,
            recovery_attempt=recovery_attempt,
            recovery_limit=recovery_limit,
        )

    def fail_system(
        self,
        message: str,
        *,
        detail: str | None = None,
        failure_class: str | None = None,
        required_action: str | None = None,
    ) -> None:
        self.state["active_transfer"] = None
        self.state["system"]["state"] = "attention"
        for worker in self.state["workers"].values():
            if worker["state"] == "active":
                worker["state"] = "error"
                worker["started_at"] = None
        if self.state["job"]:
            self.state["job"].update({
                "state": "failed",
                "result": "FAIL",
                "completed_at": _utc_now(),
            })
        self.event(
            message,
            kind="system",
            level="error",
            detail=detail,
            failure_class=failure_class,
            required_action=required_action,
            recovery_attempt=0,
            recovery_limit=2,
        )


def runtime_status_path(root: Path) -> Path:
    return root / "agent" / "runtime" / "dashboard-state.json"
