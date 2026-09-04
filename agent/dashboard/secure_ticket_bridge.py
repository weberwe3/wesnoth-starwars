#!/usr/bin/env python3

"""Run one fixed ticket inside the secure shell and publish only its exit code."""

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
    if len(sys.argv) != 3:
        raise SystemExit("usage: secure_ticket_bridge.py TICKET RESULT")
    ticket = _runtime_file(sys.argv[1], r"sol-ticket-[a-f0-9]{12}\.json")
    result = _runtime_file(sys.argv[2], r"sol-result-[a-f0-9]{12}\.json")
    runner = ROOT / "agent" / "coordinator" / "ticket_runner.py"
    completed = subprocess.run(
        [sys.executable, str(runner), str(ticket)],
        cwd=ROOT,
        check=False,
    )
    payload = json.dumps({"return_code": completed.returncode}) + "\n"
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
