"""Strict identity and freshness checks for production evidence records.

This module does not award readiness. A protected coordinator must establish
the origin of a run and match its observations to an accepted requirement.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath
import re
from typing import Any


SCHEMA_ID = "wesnoth-starwars.production.evidence-envelope"
SCHEMA_VERSION = 1
MAX_DEPENDENCIES = 128
MAX_OBSERVATIONS = 20
MAX_RECORD_BYTES = 100_000
MAX_DEPENDENCY_BYTES = 2_000_000
MAX_ARTIFACT_BYTES = 10_000_000
SHA256 = re.compile(r"[0-9a-f]{64}\Z")
SHA1 = re.compile(r"[0-9a-f]{40}\Z")
IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{2,100}\Z")


class EvidenceError(ValueError):
    """An evidence envelope or accepted requirement is malformed."""


def _object(value: Any, keys: set[str], label: str) -> dict:
    if not isinstance(value, dict) or set(value) != keys:
        raise EvidenceError(f"{label} must have exactly the required fields")
    return value


def _text(value: Any, label: str, limit: int = 512) -> str:
    if not isinstance(value, str) or not value or len(value) > limit:
        raise EvidenceError(f"{label} must be bounded nonempty text")
    return value


def _hash(value: Any, label: str, pattern: re.Pattern[str] = SHA256) -> str:
    if not isinstance(value, str) or not pattern.fullmatch(value):
        raise EvidenceError(f"{label} must be a lowercase digest")
    return value


def _relative(value: Any, label: str) -> str:
    path = _text(value, label)
    parts = PurePosixPath(path).parts
    if (
        path.startswith("/") or "\\" in path or ":" in path
        or not parts or any(part in ("", ".", "..") for part in parts)
        or PurePosixPath(path).as_posix() != path
    ):
        raise EvidenceError(f"{label} must be a safe repository-relative path")
    return path


def _safe_file(root: Path, rel: str, max_bytes: int) -> Path:
    cursor = root
    for part in PurePosixPath(rel).parts:
        cursor = cursor / part
        if cursor.is_symlink():
            raise EvidenceError(f"symlink is not an accepted evidence input: {rel}")
    try:
        cursor.resolve().relative_to(root.resolve())
    except ValueError as exc:
        raise EvidenceError(f"evidence input escapes repository: {rel}") from exc
    if not cursor.is_file() or cursor.stat().st_size > max_bytes:
        raise EvidenceError(f"evidence input is missing or exceeds its bound: {rel}")
    return cursor


def _digest(path: Path) -> str:
    sha = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(65536), b""):
            sha.update(chunk)
    return sha.hexdigest()


def validate_envelope(value: Any) -> dict:
    """Reject unknown fields, duplicate paths, unsafe input, and vague identity."""

    envelope = _object(value, {
        "schema_id", "schema_version", "requirement_id", "requirement_revision_sha256",
        "candidate_commit", "candidate_tree", "scenario_id", "probe_id",
        "exercise_type", "difficulty", "seed", "engine_version", "engine_sha256",
        "dependencies", "artifact_path", "artifact_sha256", "exit_code",
        "outcome", "observations",
    }, "envelope")
    if envelope["schema_id"] != SCHEMA_ID or envelope["schema_version"] != SCHEMA_VERSION:
        raise EvidenceError("unsupported evidence envelope version")
    for key in ("requirement_id", "scenario_id", "probe_id"):
        if not IDENTIFIER.fullmatch(_text(envelope[key], key, 101)):
            raise EvidenceError(f"invalid {key}")
    for key in ("requirement_revision_sha256", "engine_sha256", "artifact_sha256"):
        _hash(envelope[key], key)
    for key in ("candidate_commit", "candidate_tree"):
        _hash(envelope[key], key, SHA1)
    for key in ("exercise_type", "difficulty", "engine_version"):
        _text(envelope[key], key, 80)
    seed = _text(envelope["seed"], "seed", 64)
    if seed != "not-applicable" and not re.fullmatch(r"[0-9a-f]{1,64}", seed):
        raise EvidenceError("seed must be hexadecimal or not-applicable")
    path = _relative(envelope["artifact_path"], "artifact_path")
    if not path.startswith("agent/runtime/"):
        raise EvidenceError("raw evidence artifacts must stay in ignored runtime storage")
    if not isinstance(envelope["exit_code"], int) or isinstance(envelope["exit_code"], bool):
        raise EvidenceError("exit_code must be an integer")
    if envelope["outcome"] not in ("pass", "fail", "unassessed"):
        raise EvidenceError("unsupported outcome")
    observations = envelope["observations"]
    if not isinstance(observations, list) or len(observations) > MAX_OBSERVATIONS:
        raise EvidenceError("observations exceed their bound")
    for item in observations:
        _text(item, "observation")
    dependencies = envelope["dependencies"]
    if not isinstance(dependencies, list) or not dependencies or len(dependencies) > MAX_DEPENDENCIES:
        raise EvidenceError("dependencies must be nonempty and bounded")
    seen: set[str] = set()
    for item in dependencies:
        item = _object(item, {"path", "sha256"}, "dependency")
        rel = _relative(item["path"], "dependency path")
        _hash(item["sha256"], "dependency sha256")
        if rel in seen:
            raise EvidenceError("duplicate evidence dependency")
        seen.add(rel)
    return envelope


def validate_requirement(value: Any) -> dict:
    """Validate the accepted identity to which an envelope must be compared."""

    requirement = _object(value, {
        "id", "revision_sha256", "scenario_id", "probe_id", "exercise_type",
        "difficulty", "seed", "expected_exit_code", "dependency_paths",
    }, "requirement")
    for key in ("id", "scenario_id", "probe_id"):
        if not IDENTIFIER.fullmatch(_text(requirement[key], key, 101)):
            raise EvidenceError(f"invalid requirement {key}")
    _hash(requirement["revision_sha256"], "requirement revision")
    for key in ("exercise_type", "difficulty"):
        _text(requirement[key], key, 80)
    seed = _text(requirement["seed"], "seed", 64)
    if seed != "not-applicable" and not re.fullmatch(r"[0-9a-f]{1,64}", seed):
        raise EvidenceError("invalid requirement seed")
    if not isinstance(requirement["expected_exit_code"], int) or isinstance(requirement["expected_exit_code"], bool):
        raise EvidenceError("expected_exit_code must be an integer")
    paths = requirement["dependency_paths"]
    if not isinstance(paths, list) or not paths or len(paths) > MAX_DEPENDENCIES:
        raise EvidenceError("requirement dependencies must be nonempty and bounded")
    for path in paths:
        _relative(path, "requirement dependency")
    if len(paths) != len(set(paths)):
        raise EvidenceError("duplicate requirement dependency")
    return requirement


def load_envelope(path: Path) -> dict:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_RECORD_BYTES:
        raise EvidenceError("evidence envelope is missing or exceeds its bound")
    try:
        return validate_envelope(json.loads(path.read_text(encoding="utf-8")))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise EvidenceError("evidence envelope is not valid UTF-8 JSON") from exc


def assess_freshness(root: Path, envelope: dict | None, requirement: dict,
                     engine_binary: Path) -> dict:
    """Check current inputs without promoting the evidence to verified state.

    A trusted coordinator must additionally prove run origin and accepted
    observations before consuming an envelope as requirement evidence.
    """

    try:
        accepted = validate_requirement(requirement)
        if envelope is None:
            return {"freshness": "missing", "reasons": ["no evidence envelope"],
                    "result_matches": False}
        record = validate_envelope(envelope)
    except EvidenceError as exc:
        return {"freshness": "invalid", "reasons": [str(exc)], "result_matches": False}

    reasons: list[str] = []
    equal_fields = {
        "requirement_id": "id", "requirement_revision_sha256": "revision_sha256",
        "scenario_id": "scenario_id", "probe_id": "probe_id",
        "exercise_type": "exercise_type", "difficulty": "difficulty", "seed": "seed",
    }
    for evidence_key, required_key in equal_fields.items():
        if record[evidence_key] != accepted[required_key]:
            reasons.append("changed " + evidence_key)
    hashes = {item["path"]: item["sha256"] for item in record["dependencies"]}
    required_paths = set(accepted["dependency_paths"])
    if set(hashes) != required_paths:
        reasons.append("dependency set changed or incomplete")
    for rel in sorted(required_paths & set(hashes)):
        try:
            if _digest(_safe_file(root, rel, MAX_DEPENDENCY_BYTES)) != hashes[rel]:
                reasons.append("changed dependency: " + rel)
        except EvidenceError:
            reasons.append("unavailable dependency: " + rel)
    try:
        artifact = _safe_file(root, record["artifact_path"], MAX_ARTIFACT_BYTES)
        if _digest(artifact) != record["artifact_sha256"]:
            reasons.append("raw artifact changed")
    except EvidenceError:
        reasons.append("raw artifact unavailable")
    if engine_binary.is_symlink() or not engine_binary.is_file():
        reasons.append("engine binary unavailable")
    elif _digest(engine_binary) != record["engine_sha256"]:
        reasons.append("engine binary changed")
    result_matches = (
        not reasons and record["outcome"] == "pass"
        and record["exit_code"] == accepted["expected_exit_code"]
    )
    return {"freshness": "stale" if reasons else "current", "reasons": reasons,
            "result_matches": result_matches}
