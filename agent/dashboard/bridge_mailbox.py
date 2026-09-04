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
RUN_ID = re.compile(r"[a-f0-9]{12}")
RECOVERY_EFFORTS = {"low", "medium", "high"}


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
        if not ACCEPTED.exists() and REQUEST.exists():
            os.replace(REQUEST, ACCEPTED)
        if not ACCEPTED.exists():
            return 0
        try:
            request = json.loads(ACCEPTED.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise SystemExit("ERROR: invalid bridge request") from exc
        if not isinstance(request, dict) or set(request) != {"run_id", "recovery_effort"}:
            raise SystemExit("ERROR: invalid bridge request")
        effort = request.get("recovery_effort")
        if effort is not None and effort not in RECOVERY_EFFORTS:
            raise SystemExit("ERROR: invalid recovery effort")
        print(valid_run_id(request["run_id"]))
        return 0
    if command == "result" and len(sys.argv) == 3:
        run_id = valid_run_id(sys.argv[2])
        if (RUNTIME / f"sol-result-{run_id}.json").is_file():
            print("ready")
        return 0
    if command == "prepare" and len(sys.argv) == 3:
        run_id = valid_run_id(sys.argv[2])
        ticket = RUNTIME / f"sol-ticket-{run_id}.json"
        result = RUNTIME / f"sol-result-{run_id}.json"
        bridge = ROOT / "agent" / "dashboard" / "secure_ticket_bridge.py"
        bootstrap = RUNTIME / f"secure-bootstrap-{run_id}.sh"
        try:
            request = json.loads(ACCEPTED.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise SystemExit("ERROR: invalid accepted bridge request") from exc
        if request.get("run_id") != run_id:
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
    if command == "failure" and len(sys.argv) == 3:
        run_id = valid_run_id(sys.argv[2])
        write_json(RUNTIME / f"sol-result-{run_id}.json", {
            "return_code": 125,
            "failure": {
                "class": "secure_bridge_failure",
                "detail": "The secure ticket process did not return a valid result.",
                "required_action": "Restart the secure Windows launcher and try again.",
                "eligible": False,
                "attempt": 0,
                "limit": 2,
            },
        })
        return 0
    if command == "cleanup" and len(sys.argv) == 3:
        run_id = valid_run_id(sys.argv[2])
        ACCEPTED.unlink(missing_ok=True)
        (RUNTIME / f"secure-bootstrap-{run_id}.sh").unlink(missing_ok=True)
        return 0
    raise SystemExit("ERROR: unsupported bridge mailbox command")


if __name__ == "__main__":
    raise SystemExit(main())
