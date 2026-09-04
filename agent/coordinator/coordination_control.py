#!/usr/bin/env python3

"""Persistent, secret-free control state for dashboard coordination modes."""

from __future__ import annotations

import datetime as dt
import json
import os
from pathlib import Path
import tempfile
import threading
from typing import Any, Callable


VALID_MODES = {
    "deterministic": {
        "label": "Deterministic Python",
        "provider": "Local process",
        "model": "No LLM — deterministic Python",
        "effort": None,
    },
    "sol-low": {
        "label": "Sol Low",
        "provider": "OpenAI",
        "model": "GPT-5.6 Sol",
        "effort": "low",
    },
    "sol-medium": {
        "label": "Sol Medium",
        "provider": "OpenAI",
        "model": "GPT-5.6 Sol",
        "effort": "medium",
    },
    "sol-high": {
        "label": "Sol High",
        "provider": "OpenAI",
        "model": "GPT-5.6 Sol",
        "effort": "high",
    },
}


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def default_control_state() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "updated_at": utc_now(),
        "mode": "deterministic",
        "automation": {
            "enabled": False,
            "brief": "Select the next safe, documented project priority.",
        },
        "run": {
            "state": "idle",
            "run_id": None,
            "requested_at": None,
            "started_at": None,
            "completed_at": None,
            "ticket_id": None,
            "summary": "Manual Python/Bash coordination",
            "error": None,
        },
    }


class ControlStore:
    """Atomically updates the local control file within one dashboard process."""

    def __init__(self, path: Path):
        self.path = path.resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        os.chmod(self.path.parent, 0o700)
        self._lock = threading.RLock()
        if not self.path.exists():
            self._write(default_control_state())
        else:
            state = self.read()
            if state["run"]["state"] in {"planning", "executing"}:
                state["run"].update({
                    "state": "interrupted",
                    "completed_at": utc_now(),
                    "error": "Dashboard restarted during the prior run",
                })
                state["automation"]["enabled"] = False
                self._write(state)

    def read(self) -> dict[str, Any]:
        with self._lock:
            try:
                state = json.loads(self.path.read_text(encoding="utf-8"))
            except (FileNotFoundError, OSError, ValueError):
                state = default_control_state()
            return self._normalize(state)

    def update(self, change: Callable[[dict[str, Any]], None]) -> dict[str, Any]:
        with self._lock:
            state = self.read()
            change(state)
            state["updated_at"] = utc_now()
            self._write(state)
            return state

    def _write(self, state: dict[str, Any]) -> None:
        payload = json.dumps(self._normalize(state), indent=2) + "\n"
        fd, temporary = tempfile.mkstemp(
            prefix=".coordination-control-",
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

    @staticmethod
    def _normalize(value: object) -> dict[str, Any]:
        fallback = default_control_state()
        if not isinstance(value, dict) or value.get("mode") not in VALID_MODES:
            return fallback
        run = value.get("run")
        if not isinstance(run, dict):
            run = fallback["run"]
        valid_states = {
            "idle", "planning", "executing", "queued", "awaiting_deletion_approval",
            "publishing", "paused", "passed", "failed", "interrupted",
        }
        state = run.get("state") if run.get("state") in valid_states else "idle"
        automation = value.get("automation")
        if not isinstance(automation, dict):
            automation = fallback["automation"]
        brief = automation.get("brief")
        if not isinstance(brief, str) or not brief.strip() or len(brief) > 1000:
            brief = fallback["automation"]["brief"]
        return {
            "schema_version": 1,
            "updated_at": value.get("updated_at") or fallback["updated_at"],
            "mode": value["mode"],
            "automation": {
                "enabled": bool(automation.get("enabled")),
                "brief": brief,
            },
            "run": {
                "state": state,
                "run_id": run.get("run_id"),
                "requested_at": run.get("requested_at"),
                "started_at": run.get("started_at"),
                "completed_at": run.get("completed_at"),
                "ticket_id": run.get("ticket_id"),
                "summary": run.get("summary") or fallback["run"]["summary"],
                "error": run.get("error"),
            },
        }


def control_state_path(root: Path) -> Path:
    return root / "agent" / "runtime" / "coordination-control.json"
