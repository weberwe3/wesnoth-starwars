"""Durable, conservative reservations for one reviewed unattended charter.

One controller process owns this ledger. U3 must add cross-process ownership
and reconciliation before it can drive unattended scheduling after a crash.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import tempfile
import threading


RESOURCES = ("model_calls", "elapsed_seconds", "engine_runs", "repair_attempts", "disk_bytes")
LIMIT_KEYS = set(RESOURCES) | {"completion_cutoff_model_calls", "completion_reserve_model_calls"}
KINDS = {"expansion", "integration", "delivery"}
ACTION_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{2,99}\Z")
SHA256 = re.compile(r"[0-9a-f]{64}\Z")
MAX_ACTIONS = 1000


class BudgetError(ValueError):
    """The resource ledger is malformed, exhausted, or inconsistent."""


def _units(value: object) -> dict[str, int]:
    if (not isinstance(value, dict) or set(value) != set(RESOURCES)
            or any(not isinstance(value[key], int) or isinstance(value[key], bool)
                   or value[key] < 0 or value[key] > 10**12 for key in RESOURCES)):
        raise BudgetError("resource units must specify every nonnegative bounded counter")
    return value


def _limits(value: object) -> dict[str, int]:
    if (not isinstance(value, dict) or set(value) != LIMIT_KEYS
            or any(not isinstance(value[key], int) or isinstance(value[key], bool)
                   or not 1 <= value[key] <= 10**12 for key in LIMIT_KEYS)):
        raise BudgetError("invalid charter resource limits")
    if value["completion_cutoff_model_calls"] + value["completion_reserve_model_calls"] > value["model_calls"]:
        raise BudgetError("completion reserve exceeds model-call limit")
    return value


class BudgetLedger:
    def __init__(self, path: Path, charter_sha256: str, limits: dict, *, create: bool = False):
        if not isinstance(charter_sha256, str) or not SHA256.fullmatch(charter_sha256):
            raise BudgetError("invalid accepted charter digest")
        self.path = path
        self.charter_sha256 = charter_sha256
        self.limits = dict(_limits(limits))
        self._lock = threading.RLock()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.is_symlink() or self.path.parent.is_symlink():
            raise BudgetError("symlinked budget ledger path")
        if not self.path.exists() and not create:
            raise BudgetError("budget ledger missing; restart cannot recreate it")
        if not self.path.exists():
            self._atomic_write({
                "schema_version": 1, "charter_sha256": charter_sha256,
                "limits": self.limits, "revision": 0,
                "spent": {key: 0 for key in RESOURCES},
                "reservations": {}, "settled": {}, "breached": False,
            })
        self.read()

    def _atomic_write(self, state: dict) -> None:
        data = (json.dumps(state, sort_keys=True, indent=2) + "\n").encode("utf-8")
        if len(data) > 500_000:
            raise BudgetError("ledger exceeds storage bound")
        fd, temporary = tempfile.mkstemp(prefix=".budget-", suffix=".tmp", dir=self.path.parent)
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            os.chmod(temporary, 0o600)
            os.replace(temporary, self.path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    def read(self) -> dict:
        with self._lock:
            if self.path.is_symlink() or not self.path.is_file() or self.path.stat().st_size > 500_000:
                raise BudgetError("budget ledger missing or invalid")
            try:
                state = json.loads(self.path.read_text(encoding="utf-8"))
            except (OSError, UnicodeError, json.JSONDecodeError) as exc:
                raise BudgetError("budget ledger cannot be read") from exc
            if (not isinstance(state, dict) or set(state) != {
                "schema_version", "charter_sha256", "limits", "revision", "spent",
                "reservations", "settled", "breached",
            } or state["schema_version"] != 1
                or state["charter_sha256"] != self.charter_sha256
                or _limits(state["limits"]) != self.limits
                or not isinstance(state["revision"], int) or isinstance(state["revision"], bool)
                or state["revision"] < 0 or not isinstance(state["breached"], bool)):
                raise BudgetError("budget ledger identity or schema changed")
            _units(state["spent"])
            reservations, settled = state["reservations"], state["settled"]
            if (not isinstance(reservations, dict) or not isinstance(settled, dict)
                    or len(reservations) + len(settled) > MAX_ACTIONS
                    or set(reservations) & set(settled)):
                raise BudgetError("budget action inventory invalid")
            for action_id, record in reservations.items():
                if (not ACTION_ID.fullmatch(action_id) or not isinstance(record, dict)
                        or set(record) != {"kind", "units"}
                        or not isinstance(record["kind"], str) or record["kind"] not in KINDS):
                    raise BudgetError("invalid reserved action")
                _units(record["units"])
            for action_id, actual in settled.items():
                if not ACTION_ID.fullmatch(action_id):
                    raise BudgetError("invalid settled action")
                _units(actual)
            return state

    def reserve(self, action_id: str, kind: str, units: dict[str, int]) -> dict:
        with self._lock:
            state = self.read()
            if (not isinstance(action_id, str) or not ACTION_ID.fullmatch(action_id)
                    or not isinstance(kind, str) or kind not in KINDS):
                raise BudgetError("invalid action identity or kind")
            requested = dict(_units(units))
            if not any(requested.values()):
                raise BudgetError("empty reservation")
            if action_id in state["settled"]:
                raise BudgetError("action already settled")
            record = {"kind": kind, "units": requested}
            if action_id in state["reservations"]:
                if state["reservations"][action_id] != record:
                    raise BudgetError("action reservation changed")
                return state
            if state["breached"] or len(state["reservations"]) + len(state["settled"]) >= MAX_ACTIONS:
                raise BudgetError("ledger breached or action bound reached")
            projected = {key: state["spent"][key] + requested[key]
                         + sum(item["units"][key] for item in state["reservations"].values())
                         for key in RESOURCES}
            if any(projected[key] > self.limits[key] for key in RESOURCES):
                raise BudgetError("charter resource limit would be exceeded")
            if kind == "expansion" and projected["model_calls"] > self.limits["completion_cutoff_model_calls"]:
                raise BudgetError("completion cutoff reached; expansion is closed")
            state["reservations"][action_id] = record
            state["revision"] += 1
            self._atomic_write(state)
            return state

    def settle(self, action_id: str, actual: dict[str, int]) -> dict:
        with self._lock:
            state = self.read()
            if not isinstance(action_id, str) or not ACTION_ID.fullmatch(action_id):
                raise BudgetError("invalid action identity")
            measured = dict(_units(actual))
            if action_id in state["settled"]:
                if state["settled"][action_id] != measured:
                    raise BudgetError("settled usage changed")
                return state
            if action_id not in state["reservations"]:
                raise BudgetError("action was never reserved")
            state["reservations"].pop(action_id)
            state["settled"][action_id] = measured
            for key in RESOURCES:
                state["spent"][key] += measured[key]
                if state["spent"][key] + sum(item["units"][key] for item in state["reservations"].values()) > self.limits[key]:
                    state["breached"] = True
            state["revision"] += 1
            self._atomic_write(state)
            return state
