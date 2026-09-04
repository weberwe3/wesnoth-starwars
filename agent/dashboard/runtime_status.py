#!/usr/bin/env python3
from __future__ import annotations

import datetime as dt
import json
import os
from pathlib import Path
import re
import tempfile
from typing import Any

STATE_REL = Path("agent/logs/dashboard-state.json")
MAX_EVENTS = 160

ROLE_META = {
    "coordinator": {"label": "Coordinator", "kind": "system"},
    "implementer": {"label": "Implementer", "kind": "llm"},
    "fast-fix": {"label": "Fast-Fix", "kind": "llm"},
    "validation": {"label": "Deterministic Validation", "kind": "system"},
    "tester": {"label": "Tester", "kind": "llm"},
    "reviewer": {"label": "Reviewer", "kind": "llm"},
    "reviewer-fallback": {"label": "Reviewer Fallback", "kind": "llm"},
}

AGENT_FILES = {
    "implementer": ".opencode/agents/implementer.md",
    "fast-fix": ".opencode/agents/fast-fix.md",
    "tester": ".opencode/agents/tester.md",
    "reviewer": ".opencode/agents/reviewer.md",
    "reviewer-fallback": ".opencode/agents/reviewer-fallback.md",
}


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).astimezone().isoformat(timespec="seconds")


def _provider(model: str) -> str:
    prefix = model.split("/", 1)[0].lower()
    return {
        "groq": "Groq",
        "opencode": "OpenCode",
        "google": "Google",
        "cloudflare-workers-ai": "Cloudflare Workers AI",
    }.get(prefix, prefix.title() if prefix else "Unknown")


def _model_from_agent(root: Path, rel: str) -> str:
    try:
        text = (root / rel).read_text(encoding="utf-8")
    except OSError:
        return "Unknown"
    match = re.search(r"(?m)^model:\s*(\S+)\s*$", text)
    return match.group(1) if match else "Unknown"


def assignments(root: Path) -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {
        "coordinator": {
            "model": "Deterministic Python",
            "provider": "Local",
            "kind": "system",
        },
        "validation": {
            "model": "Deterministic Python",
            "provider": "Local",
            "kind": "system",
        },
    }
    for role, rel in AGENT_FILES.items():
        model = _model_from_agent(root, rel)
        result[role] = {
            "model": model,
            "provider": _provider(model),
            "kind": "llm",
        }
    return result


def default_state(root: Path) -> dict[str, Any]:
    now = _now()
    models = assignments(root)
    workers: dict[str, dict[str, Any]] = {}
    for role, meta in ROLE_META.items():
        assignment = models.get(role, {})
        workers[role] = {
            "role": meta["label"],
            "kind": assignment.get("kind", meta["kind"]),
            "model": assignment.get("model", "Unknown"),
            "provider": assignment.get("provider", "Unknown"),
            "state": "idle",
            "task": "Standing by",
            "since": now,
            "error": None,
        }
    return {
        "schema_version": 1,
        "updated_at": now,
        "ticket": None,
        "workers": workers,
        "active_transfer": None,
        "events": [],
        "latest_error": None,
        "final_verdict": None,
    }


def state_path(root: Path) -> Path:
    return root / STATE_REL


def _read(root: Path) -> dict[str, Any]:
    path = state_path(root)
    if not path.exists():
        return default_state(root)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("state must be object")
    except Exception:
        data = default_state(root)

    fresh = assignments(root)
    workers = data.setdefault("workers", {})
    for role, meta in ROLE_META.items():
        existing = workers.setdefault(role, {})
        assignment = fresh.get(role, {})
        existing.setdefault("role", meta["label"])
        existing["kind"] = assignment.get("kind", meta["kind"])
        existing["model"] = assignment.get(
            "model", existing.get("model", "Unknown")
        )
        existing["provider"] = assignment.get(
            "provider", existing.get("provider", "Unknown")
        )
        existing.setdefault("state", "idle")
        existing.setdefault("task", "Standing by")
        existing.setdefault("since", _now())
        existing.setdefault("error", None)
    return data


def _write(root: Path, state: dict[str, Any]) -> None:
    path = state_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    state["updated_at"] = _now()
    encoded = json.dumps(state, indent=2, ensure_ascii=False) + "\n"
    fd, temp_name = tempfile.mkstemp(
        prefix=".dashboard-state-", suffix=".json", dir=str(path.parent)
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    finally:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass


def _safe_update(root: Path, mutator) -> bool:
    try:
        state = _read(root)
        mutator(state)
        _write(root, state)
        return True
    except Exception:
        # Dashboard telemetry must never break the deterministic ticket pipeline.
        return False


def _append(
    state: dict[str, Any],
    message: str,
    *,
    level: str = "info",
    sender: str | None = None,
    receiver: str | None = None,
) -> None:
    events = state.setdefault("events", [])
    events.append(
        {
            "time": _now(),
            "level": level,
            "from": sender,
            "to": receiver,
            "message": message,
        }
    )
    del events[:-MAX_EVENTS]


def start_ticket(root: Path, ticket: dict[str, Any]) -> bool:
    def mutate(state: dict[str, Any]) -> None:
        now = _now()
        fresh = default_state(root)
        state.clear()
        state.update(fresh)
        state["ticket"] = {
            "id": ticket.get("task_id"),
            "objective": ticket.get("objective"),
            "worker": ticket.get("worker"),
            "validation_profile": ticket.get("validation_profile"),
            "branch": None,
            "worktree": None,
            "started_at": now,
            "status": "running",
        }
        worker = state["workers"]["coordinator"]
        worker.update(
            state="working",
            task="Preparing ticket and governance checks",
            since=now,
            error=None,
        )
        _append(
            state,
            f"Ticket {ticket.get('task_id')} started.",
            sender="coordinator",
        )

    return _safe_update(root, mutate)


def set_ticket_context(
    root: Path,
    *,
    branch: str | None = None,
    worktree: str | None = None,
) -> bool:
    def mutate(state: dict[str, Any]) -> None:
        ticket = state.get("ticket")
        if isinstance(ticket, dict):
            if branch is not None:
                ticket["branch"] = branch
            if worktree is not None:
                ticket["worktree"] = worktree

    return _safe_update(root, mutate)


def set_worker(
    root: Path,
    role: str,
    state_name: str,
    task: str,
    *,
    error: str | None = None,
    event_message: str | None = None,
) -> bool:
    def mutate(state: dict[str, Any]) -> None:
        worker = state.setdefault("workers", {}).setdefault(role, {})
        worker["state"] = state_name
        worker["task"] = task
        worker["since"] = _now()
        worker["error"] = error
        if error:
            state["latest_error"] = {
                "time": _now(),
                "role": role,
                "message": error,
            }
            _append(
                state,
                event_message or error,
                level="error",
                sender=role,
            )
        elif event_message:
            _append(state, event_message, sender=role)

    return _safe_update(root, mutate)


def transfer(root: Path, sender: str, receiver: str, label: str) -> bool:
    def mutate(state: dict[str, Any]) -> None:
        state["active_transfer"] = {
            "from": sender,
            "to": receiver,
            "label": label,
            "started_at": _now(),
        }
        _append(state, label, sender=sender, receiver=receiver)

    return _safe_update(root, mutate)


def clear_transfer(root: Path) -> bool:
    return _safe_update(
        root,
        lambda state: state.__setitem__("active_transfer", None),
    )


def finish_ticket(root: Path, verdict: str, message: str | None = None) -> bool:
    def mutate(state: dict[str, Any]) -> None:
        state["active_transfer"] = None
        state["final_verdict"] = verdict
        ticket = state.get("ticket")
        if isinstance(ticket, dict):
            ticket["status"] = "complete" if verdict == "PASS" else "failed"
            ticket["finished_at"] = _now()
        coordinator = state.setdefault("workers", {}).setdefault("coordinator", {})
        coordinator["state"] = "idle" if verdict == "PASS" else "error"
        coordinator["task"] = (
            "Ticket complete" if verdict == "PASS" else "Ticket failed"
        )
        coordinator["since"] = _now()
        coordinator["error"] = None if verdict == "PASS" else (message or "Ticket failed")
        _append(
            state,
            message or f"Ticket finished with verdict {verdict}.",
            level="info" if verdict == "PASS" else "error",
            sender="coordinator",
        )

    return _safe_update(root, mutate)
