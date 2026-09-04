#!/usr/bin/env python3

"""Record one explicit Codex-mediated deletion approval decision."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

from approval_queue import _atomic_json


ROOT = Path(__file__).resolve().parents[2]
RUNTIME = ROOT / "agent" / "runtime"


def main() -> int:
    parser = argparse.ArgumentParser(description="Record an exact deletion decision")
    parser.add_argument("decision", choices=("approve", "reject"))
    parser.add_argument("request_id")
    parser.add_argument("manifest_digest")
    args = parser.parse_args()
    if not re.fullmatch(r"[0-9a-f]{16}", args.request_id):
        parser.error("invalid request ID")
    if not re.fullmatch(r"[0-9a-f]{64}", args.manifest_digest):
        parser.error("invalid manifest digest")
    request_path = RUNTIME / f"deletion-approval-request-{args.request_id}.json"
    try:
        request = json.loads(request_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        raise SystemExit("ERROR: deletion request is unavailable")
    unsigned = {key: value for key, value in request.items() if key != "manifest_digest"}
    computed = hashlib.sha256(
        json.dumps(unsigned, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    if (
        request.get("request_id") != args.request_id
        or request.get("manifest_digest") != args.manifest_digest
        or computed != args.manifest_digest
    ):
        raise SystemExit("ERROR: deletion request digest mismatch")
    decision_path = RUNTIME / f"deletion-approval-decision-{args.request_id}.json"
    if decision_path.exists():
        raise SystemExit("ERROR: deletion request already decided")
    _atomic_json(decision_path, {
        "request_id": args.request_id,
        "manifest_digest": args.manifest_digest,
        "decision": args.decision,
    })
    print(f"Deletion request {args.request_id}: {args.decision}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
