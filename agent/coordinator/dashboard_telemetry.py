#!/usr/bin/env python3

"""Secret-free JSONL telemetry for the DASH-001 operations dashboard.

DASH-001 MVP integration strategy: instrument the coordinator at runtime and
write ignored local telemetry under ``agent/logs/`` without destabilizing the
protected coordinator. This module is the event writer; a dashboard-aware
wrapper around ``ticket_runner.py`` consumes it later.

Security: no credentials, provider tokens, environment-variable values, or
secret material may be persisted. Every payload passes through
:func:`sanitize_payload`, which drops known-secret keys and redacts
secret-shaped values. Telemetry is best-effort: write failures never raise.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import re
from pathlib import Path
from typing import Any

TELEMETRY_DIR = Path(__file__).resolve().parents[1] / "logs"
TELEMETRY_FILE = TELEMETRY_DIR / "dashboard_telemetry.jsonl"
MAX_EVENTS = 5000

# Roles shown on the DASH-001 dashboard.
DASHBOARD_ROLES = (
    "coordinator",
    "implementer",
    "fast-fix",
    "deterministic-validation",
    "tester",
    "reviewer",
    "reviewer-fallback",
)

_SECRET_KEY_RE = re.compile(
    r"(token|secret|password|passwd|api[_-]?key|auth|credential|private[_-]?key|"
    r"bearer|session|cookie)",
    re.IGNORECASE,
)
# Long opaque strings (32+ chars of token-shaped characters) are redacted even
# when the key name is innocuous.
_SECRET_VALUE_RE = re.compile(r"^[A-Za-z0-9_\-+/=]{32,}$")


def sanitize_payload(payload: Any) -> Any:
    """Return a secret-free copy of a JSON-able payload."""
    if isinstance(payload, dict):
        clean: dict[str, Any] = {}
        for key, value in payload.items():
            if isinstance(key, str) and _SECRET_KEY_RE.search(key):
                clean[key] = "[redacted]"
            else:
                clean[key] = sanitize_payload(value)
        return clean
    if isinstance(payload, (list, tuple)):
        return [sanitize_payload(item) for item in payload]
    if isinstance(payload, str) and _SECRET_VALUE_RE.fullmatch(payload):
        return "[redacted]"
    return payload


def _utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def emit(event_type: str, role: str, payload: dict[str, Any] | None = None) -> bool:
    """Append one sanitized telemetry event. Returns True on success.

    Never raises: telemetry must not break the coordinator it instruments.
    """
    try:
        event = {
            "ts": _utc_now(),
            "type": event_type,
            "role": role,
            "payload": sanitize_payload(payload or {}),
        }
        TELEMETRY_DIR.mkdir(parents=True, exist_ok=True)
        with TELEMETRY_FILE.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, default=str) + "\n")
        _trim()
        return True
    except OSError:
        return False


def _trim() -> None:
    """Keep the telemetry file bounded; drop oldest events on overflow."""
    try:
        lines = TELEMETRY_FILE.read_text(encoding="utf-8").splitlines()
    except OSError:
        return
    if len(lines) > MAX_EVENTS:
        try:
            TELEMETRY_FILE.write_text(
                "\n".join(lines[-MAX_EVENTS:]) + "\n", encoding="utf-8"
            )
        except OSError:
            pass


def model_for_agent(agent: str) -> tuple[str, str]:
    """Best-effort (model, provider) for a coordinator agent name.

    Reads the model assignment from model_policy.AGENT_MODELS; the provider
    is the model string's leading path segment (e.g. "openai" from
    "openai/gpt-6-sol"). Returns ("", "") when the mapping is unavailable —
    telemetry must never break the caller.
    """
    try:
        from model_policy import AGENT_MODELS
    except Exception:
        return "", ""
    model = AGENT_MODELS.get(agent, "")
    provider = model.split("/")[0] if "/" in model else ""
    return model, provider


def role_state(
    role: str,
    state: str,
    task: str = "",
    model: str = "",
    provider: str = "",
    elapsed_s: float = 0.0,
    detail: str = "",
) -> bool:
    """Record a worker role state transition.

    ``state`` is one of: idle, active, warning, error.
    """
    return emit("role_state", role, {
        "state": state,
        "task": task,
        "model": model,
        "provider": provider,
        "elapsed_s": round(elapsed_s, 1),
        "detail": detail,
    })


def handoff(sender: str, receiver: str, ticket_id: str = "") -> bool:
    """Record a directional handoff between two roles."""
    return emit("handoff", sender, {
        "receiver": receiver,
        "ticket_id": ticket_id,
    })


def ticket_event(ticket_id: str, status: str, detail: str = "") -> bool:
    """Record a ticket lifecycle event (queued, started, completed, failed)."""
    return emit("ticket", "coordinator", {
        "ticket_id": ticket_id,
        "status": status,
        "detail": detail,
    })


def error_event(role: str, message: str, task: str = "") -> bool:
    """Record an error for the dashboard activity/error feed."""
    return emit("error", role, {"message": message, "task": task})


def read_events(limit: int = 200) -> list[dict[str, Any]]:
    """Read the most recent telemetry events (dashboard serving helper)."""
    try:
        lines = TELEMETRY_FILE.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    events: list[dict[str, Any]] = []
    for line in lines[-limit:]:
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return events


def _selftest() -> int:
    """Deterministic self-test: secret-free writes, sanitization, read-back."""
    import tempfile

    global TELEMETRY_DIR, TELEMETRY_FILE
    real_dir, real_file = TELEMETRY_DIR, TELEMETRY_FILE
    failures = []
    try:
        with tempfile.TemporaryDirectory() as tmp:
            TELEMETRY_DIR = Path(tmp)
            TELEMETRY_FILE = TELEMETRY_DIR / "dashboard_telemetry.jsonl"

            # 1. Secret keys and secret-shaped values are redacted.
            assert emit("role_state", "tester", {
                "api_key": "sk-live-123",
                "nested": {"password": "hunter2"},
                "opaque": "A" * 40,
                "task": "ticket-42",
            })
            events = read_events()
            assert len(events) == 1, events
            payload = events[0]["payload"]
            assert payload["api_key"] == "[redacted]", payload
            assert payload["nested"]["password"] == "[redacted]", payload
            assert payload["opaque"] == "[redacted]", payload
            assert payload["task"] == "ticket-42", payload

            # 2. Convenience helpers write well-formed events.
            assert role_state("implementer", "active", task="t-1",
                              model="m", provider="p", elapsed_s=12.34)
            assert handoff("implementer", "tester", ticket_id="t-1")
            assert ticket_event("t-1", "completed")
            assert error_event("reviewer", "schema mismatch")
            events = read_events()
            assert len(events) == 5, len(events)
            assert events[1]["payload"]["elapsed_s"] == 12.3, events[1]
            assert events[2]["payload"]["receiver"] == "tester", events[2]

            # 3. Telemetry never raises on unwritable paths.
            TELEMETRY_DIR = Path("/proc/definitely-not-writable-xyz")
            TELEMETRY_FILE = TELEMETRY_DIR / "dashboard_telemetry.jsonl"
            assert emit("role_state", "tester", {}) is False

            # 4. model_for_agent resolves the exact model/provider assignment.
            model, provider = model_for_agent("implementer")
            assert model == "openai/gpt-6-sol", model
            assert provider == "openai", provider
            model, provider = model_for_agent("reviewer")
            assert provider == "cloudflare-workers-ai", provider
            assert model_for_agent("no-such-agent") == ("", "")
    except AssertionError as exc:
        failures.append(str(exc))
    finally:
        TELEMETRY_DIR, TELEMETRY_FILE = real_dir, real_file

    if failures:
        print("FAIL:", failures)
        return 1
    print("dashboard_telemetry self-test: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(_selftest())
