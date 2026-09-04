#!/usr/bin/env python3

"""Run one fixed ticket and publish an allowlisted, secret-free outcome."""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def _runtime_file(value: str, pattern: str) -> Path:
    path = Path(value).resolve()
    runtime = (ROOT / "agent" / "runtime").resolve()
    try:
        relative = path.relative_to(runtime).as_posix()
    except ValueError as exc:
        raise SystemExit("ERROR: bridge path is outside agent/runtime") from exc
    if not re.fullmatch(pattern, relative):
        raise SystemExit("ERROR: bridge path failed validation")
    return path


def main() -> int:
    if len(sys.argv) not in {3, 4}:
        raise SystemExit("usage: secure_ticket_bridge.py TICKET RESULT [RECOVERY_EFFORT]")
    ticket = _runtime_file(sys.argv[1], r"sol-ticket-[a-f0-9]{12}\.json")
    result = _runtime_file(sys.argv[2], r"sol-result-[a-f0-9]{12}\.json")
    runner = ROOT / "agent" / "coordinator" / "ticket_runner.py"
    command = [sys.executable, str(runner), str(ticket)]
    if len(sys.argv) == 4:
        if sys.argv[3] not in {"low", "medium", "high"}:
            raise SystemExit("ERROR: invalid recovery effort")
        command.extend(["--recovery-effort", sys.argv[3]])
    completed = subprocess.run(
        command,
        cwd=ROOT,
        check=False,
    )
    failure = None
    try:
        state = json.loads((ROOT / "agent/runtime/dashboard-state.json").read_text(encoding="utf-8"))
        errors = [
            item for item in state.get("events", [])
            if isinstance(item, dict) and item.get("level") == "error"
        ]
        if errors:
            event = errors[-1]
            failure = {
                "class": event.get("failure_class") or "ticket_failure",
                "detail": event.get("detail") or event.get("message") or "Ticket execution failed.",
                "required_action": event.get("required_action") or "Review the ticket evidence before retrying.",
                "eligible": False,
                "attempt": event.get("recovery_attempt") or 0,
                "limit": event.get("recovery_limit") or 2,
            }
    except (OSError, json.JSONDecodeError, TypeError):
        failure = None
    payload_value = {"return_code": completed.returncode}
    if completed.returncode != 0:
        payload_value["failure"] = failure or {
            "class": "ticket_failure",
            "detail": "The deterministic ticket runner stopped without a safe diagnostic.",
            "required_action": "Review local ticket evidence before retrying.",
            "eligible": False,
            "attempt": 0,
            "limit": 2,
        }
    payload = json.dumps(payload_value) + "\n"
    result.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(
        prefix=".sol-result-", suffix=".json", dir=result.parent, text=True
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, result)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
