#!/usr/bin/env python3

"""Fixed-file mailbox used by the native Windows control bridge."""

from __future__ import annotations

import datetime as dt
import json
import os
from pathlib import Path
import re
import shlex
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[2]
RUNTIME = ROOT / "agent" / "runtime"
REQUEST = RUNTIME / "secure-run-request.json"
ACCEPTED = RUNTIME / "secure-run-request.accepted.json"
CONTROL = RUNTIME / "coordination-control.json"
ACTIVE_RUN_STATES = {"planning", "executing", "publishing"}
RUN_ID = re.compile(r"[a-f0-9]{12}")
RECOVERY_EFFORTS = {"low", "medium", "high"}
FAILURE_PHASES = {"prepare", "launch", "wait", "result"}


def write_json(path: Path, value: object) -> None:
    RUNTIME.mkdir(parents=True, exist_ok=True)
    os.chmod(RUNTIME, 0o700)
    fd, temporary = tempfile.mkstemp(
        prefix=".bridge-mailbox-", suffix=".json", dir=RUNTIME, text=True
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(json.dumps(value, separators=(",", ":")) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def valid_run_id(value: object) -> str:
    if not isinstance(value, str) or not RUN_ID.fullmatch(value):
        raise SystemExit("ERROR: invalid bridge run ID")
    return value


def ticket_identity(run_id: str) -> str | None:
    """Return the validated identity bound to a run's immutable ticket."""
    try:
        ticket = json.loads((RUNTIME / f"sol-ticket-{run_id}.json").read_text(
            encoding="utf-8"
        ))
    except (OSError, json.JSONDecodeError):
        return None
    ticket_id = ticket.get("task_id") if isinstance(ticket, dict) else None
    if not isinstance(ticket_id, str) or not re.fullmatch(
        r"SOL-[A-Za-z0-9-]{4,120}", ticket_id
    ):
        return None
    return ticket_id


def failure_context(values: list[str]) -> tuple[str | None, int | None]:
    """Validate the small, secret-free bridge context allowed in a fallback."""
    if not values:
        return None, None
    if len(values) not in {1, 2} or values[0] not in FAILURE_PHASES:
        raise SystemExit("ERROR: invalid bridge failure context")
    if len(values) == 1:
        return values[0], None
    if not re.fullmatch(r"(?:0|[1-9][0-9]{0,2})", values[1]):
        raise SystemExit("ERROR: invalid bridge child exit code")
    exit_code = int(values[1])
    if exit_code > 255:
        raise SystemExit("ERROR: invalid bridge child exit code")
    return values[0], exit_code


def read_request(path: Path) -> dict[str, object] | None:
    """Return a schema-valid mailbox request, without trusting stale files."""
    try:
        request = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(request, dict) or set(request) != {"run_id", "recovery_effort"}:
        return None
    try:
        valid_run_id(request.get("run_id"))
    except SystemExit:
        return None
    effort = request.get("recovery_effort")
    if effort is not None and effort not in RECOVERY_EFFORTS:
        return None
    return request


def active_run_id() -> str | None:
    """Read the one dashboard run allowed to own the native bridge."""
    try:
        control = json.loads(CONTROL.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    run = control.get("run") if isinstance(control, dict) else None
    if not isinstance(run, dict) or run.get("state") not in ACTIVE_RUN_STATES:
        return None
    try:
        return valid_run_id(run.get("run_id"))
    except SystemExit:
        return None


def main() -> int:
    if len(sys.argv) < 2:
        raise SystemExit("usage: bridge_mailbox.py COMMAND")
    command = sys.argv[1]
    if command == "heartbeat" and len(sys.argv) == 4:
        state, message = sys.argv[2:]
        if state not in {"online", "executing", "error"} or len(message) > 100:
            raise SystemExit("ERROR: invalid heartbeat")
        write_json(RUNTIME / "secure-bridge-health.json", {
            "schema_version": 1,
            "state": state,
            "message": message,
            "updated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        })
        return 0
    if command == "claim" and len(sys.argv) == 2:
        RUNTIME.mkdir(parents=True, exist_ok=True)
        active_run = active_run_id()
        accepted = read_request(ACCEPTED) if ACCEPTED.exists() else None
        # A mailbox is single-consumer. Never allow a request left by an older
        # dashboard process to be claimed for a different control run.
        if ACCEPTED.exists() and (accepted is None or accepted.get("run_id") != active_run):
            ACCEPTED.unlink(missing_ok=True)
            accepted = None
        if not ACCEPTED.exists() and REQUEST.exists():
            request = read_request(REQUEST)
            if request is None or request.get("run_id") != active_run:
                REQUEST.unlink(missing_ok=True)
                return 0
            os.replace(REQUEST, ACCEPTED)
            accepted = request
        if not ACCEPTED.exists() or accepted is None:
            return 0
        print(valid_run_id(accepted["run_id"]))
        return 0
    if command == "result" and len(sys.argv) == 3:
        run_id = valid_run_id(sys.argv[2])
        accepted = read_request(ACCEPTED)
        if (
            accepted is not None
            and accepted.get("run_id") == run_id
            and active_run_id() == run_id
            and (RUNTIME / f"sol-result-{run_id}.json").is_file()
        ):
            print("ready")
        return 0
    if command == "prepare" and len(sys.argv) == 3:
        run_id = valid_run_id(sys.argv[2])
        ticket = RUNTIME / f"sol-ticket-{run_id}.json"
        result = RUNTIME / f"sol-result-{run_id}.json"
        bridge = ROOT / "agent" / "dashboard" / "secure_ticket_bridge.py"
        bootstrap = RUNTIME / f"secure-bootstrap-{run_id}.sh"
        request = read_request(ACCEPTED)
        if request is None or request.get("run_id") != run_id or active_run_id() != run_id:
            raise SystemExit("ERROR: accepted bridge request does not match")
        effort = request.get("recovery_effort")
        if effort is not None and effort not in RECOVERY_EFFORTS:
            raise SystemExit("ERROR: invalid recovery effort")
        arguments = [str(bridge), str(ticket), str(result)]
        if effort:
            arguments.append(effort)
        script = "#!/usr/bin/env bash\nunset BASH_ENV\nexec python3 {}\n".format(
            " ".join(shlex.quote(value) for value in arguments)
        )
        bootstrap.write_text(script, encoding="utf-8")
        os.chmod(bootstrap, 0o700)
        print(bootstrap)
        return 0
    if command == "failure" and len(sys.argv) in {3, 4, 5}:
        run_id = valid_run_id(sys.argv[2])
        phase, child_exit_code = failure_context(sys.argv[3:])
        result = RUNTIME / f"sol-result-{run_id}.json"
        # A delayed timeout callback must not overwrite an already-complete
        # result written by the secure bridge.
        if not result.exists():
            detail = "The secure ticket process did not return a valid result."
            if phase is not None:
                detail += f" Bridge phase: {phase}."
            if child_exit_code is not None:
                detail += f" Child exit code: {child_exit_code}."
            failure = {
                "return_code": 125,
                "failure": {
                    "class": "secure_bridge_failure",
                    "detail": detail,
                    "required_action": "Restart the secure Windows launcher and try again.",
                    "eligible": False,
                    "attempt": 0,
                    "limit": 2,
                },
            }
            if phase is not None:
                failure["bridge_phase"] = phase
            if child_exit_code is not None:
                failure["child_exit_code"] = child_exit_code
            ticket_id = ticket_identity(run_id)
            if ticket_id is not None:
                failure["ticket_id"] = ticket_id
            write_json(result, failure)
        return 0
    if command == "cleanup" and len(sys.argv) == 3:
        run_id = valid_run_id(sys.argv[2])
        accepted = read_request(ACCEPTED)
        if accepted is not None and accepted.get("run_id") == run_id:
            ACCEPTED.unlink(missing_ok=True)
        (RUNTIME / f"secure-bootstrap-{run_id}.sh").unlink(missing_ok=True)
        (RUNTIME / f"secure-run-cancel.{run_id}").unlink(missing_ok=True)
        return 0
    raise SystemExit("ERROR: unsupported bridge mailbox command")


if __name__ == "__main__":
    raise SystemExit(main())
