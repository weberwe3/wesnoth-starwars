"""Fail-closed validation for a reviewed unattended operating charter.

This is an admission gate, not a source of authority. The caller must supply
the independently accepted charter digest and live coordinator authorization.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from typing import Any


SCHEMA_ID = "wesnoth-starwars.production.unattended-charter"
SCHEMA_VERSION = 1
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{2,79}\Z")
_REFS = {
    "scope": "docs/PROJECT_SCOPE_AND_FEATURE_SET.md",
    "orchestration": "docs/AGENT_ORCHESTRATION_FUNCTIONAL_SPEC.md",
    "reference_manifest": "docs/REFERENCE_MANIFEST.json",
    "architecture": "docs/TARGET_ARCHITECTURE.md",
    "delivery": "docs/UNATTENDED_DELIVERY_SPEC.md",
}
_LIMITS = {"model_calls", "elapsed_seconds", "engine_runs", "repair_attempts",
           "disk_bytes", "completion_cutoff_model_calls", "completion_reserve_model_calls"}
_ACTIONS = {"development", "governed_publication", "local_build_promotion"}
_PROFILES = {"playable_prototype", "production_proof", "release_candidate"}
_ASSET_SOURCES = {"prepared_original"}
_ENTRY_POINTS = {"verified_player_launcher", "developer_launcher"}


class CharterError(ValueError):
    """Charter is malformed or not authorized for the requested run."""


def canonical_digest(charter: dict) -> str:
    return hashlib.sha256(json.dumps(charter, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=False).encode("utf-8")).hexdigest()


def _bounded_strings(value: Any, label: str, *, maximum: int = 64) -> list[str]:
    if (not isinstance(value, list) or not 1 <= len(value) <= maximum
            or any(not isinstance(item, str) or not item or len(item) > 160 for item in value)
            or len(set(value)) != len(value)):
        raise CharterError(f"{label} must be a bounded unique string list")
    return value


def _object(value: Any, keys: set[str], label: str) -> dict:
    if not isinstance(value, dict) or set(value) != keys:
        raise CharterError(f"{label} has missing or unsupported fields")
    return value


def _file_digest(root: Path, rel: str) -> str:
    path = root
    for part in rel.split("/"):
        path = path / part
        if path.is_symlink():
            raise CharterError(f"symlinked identity file: {rel}")
    if not path.is_file() or path.stat().st_size > 2_000_000:
        raise CharterError(f"missing or oversized identity file: {rel}")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _decisions(value: Any, label: str) -> None:
    if not isinstance(value, dict) or not 1 <= len(value) <= 32:
        raise CharterError(f"{label} must specify bounded decisions")
    for key, item in value.items():
        if not isinstance(key, str) or not 1 <= len(key) <= 80:
            raise CharterError(f"invalid {label} key")
        if isinstance(item, bool):
            continue
        if isinstance(item, int) and 0 <= item <= 10**9:
            continue
        if isinstance(item, str) and 1 <= len(item) <= 300:
            continue
        raise CharterError(f"invalid {label} decision")


def validate_charter(root: Path, charter: Any, *, accepted_sha256: str | None,
                     automation_authorization_id: str | None,
                     promotion_approval_id: str | None = None,
                     now: datetime | None = None) -> dict:
    """Return the reviewed charter or raise before any unattended action.

    `accepted_sha256` is supplied by an independent approval record, never by
    the charter itself. An absent record keeps a draft charter inactive.
    """
    value = _object(charter, {
        "schema_id", "schema_version", "milestone_id", "required_nodes", "profile",
        "player_outcome", "entry_points", "allowed_actions", "allowed_ticket_classes",
        "allowed_paths", "protected_inputs", "asset_sources", "creative_defaults",
        "limits", "authority", "capabilities", "required_session",
        "retry_policy", "escalation", "notification", "identity",
    }, "charter")
    if value["schema_id"] != SCHEMA_ID or value["schema_version"] != SCHEMA_VERSION:
        raise CharterError("unsupported charter version")
    if not isinstance(value["milestone_id"], str) or not _ID.fullmatch(value["milestone_id"]):
        raise CharterError("invalid milestone ID")
    nodes = _bounded_strings(value["required_nodes"], "required_nodes")
    if any(not _ID.fullmatch(item) for item in nodes):
        raise CharterError("invalid required node ID")
    if not isinstance(value["profile"], str) or value["profile"] not in _PROFILES:
        raise CharterError("unsupported delivery profile")
    if not isinstance(value["player_outcome"], str) or not 1 <= len(value["player_outcome"]) <= 500:
        raise CharterError("missing bounded player outcome")
    entry_points = set(_bounded_strings(value["entry_points"], "entry_points", maximum=8))
    if not entry_points <= _ENTRY_POINTS or "verified_player_launcher" not in entry_points:
        raise CharterError("unsupported entry point")
    actions = _bounded_strings(value["allowed_actions"], "allowed_actions", maximum=3)
    if not set(actions) <= _ACTIONS:
        raise CharterError("unauthorized action class")
    _bounded_strings(value["allowed_ticket_classes"], "allowed_ticket_classes", maximum=16)
    paths = _bounded_strings(value["allowed_paths"], "allowed_paths")
    if any(not path.startswith("addons/Star_Wars_Thrawn_Trilogy/")
           or ".." in path.split("/") or "\\" in path or ":" in path for path in paths):
        raise CharterError("charter paths must stay in the add-on")
    protected = _bounded_strings(value["protected_inputs"], "protected_inputs")
    if not set(_REFS.values()) <= set(protected):
        raise CharterError("controlled identity inputs are not protected")
    if not set(_bounded_strings(value["asset_sources"], "asset_sources", maximum=16)) <= _ASSET_SOURCES:
        raise CharterError("unapproved asset source")
    defaults = value["creative_defaults"]
    if (not isinstance(defaults, dict) or len(defaults) > 32
            or any(not isinstance(k, str) or not isinstance(v, str)
                   or not k or not v or len(k) > 80 or len(v) > 300
                   for k, v in defaults.items())):
        raise CharterError("invalid creative defaults")
    limits = _object(value["limits"], _LIMITS, "limits")
    if any(not isinstance(limits[key], int) or isinstance(limits[key], bool)
           or not 1 <= limits[key] <= 10**12 for key in _LIMITS):
        raise CharterError("all charter limits must be positive bounded integers")
    if limits["completion_cutoff_model_calls"] + limits["completion_reserve_model_calls"] > limits["model_calls"]:
        raise CharterError("completion reserve exceeds model-call budget")
    authority = _object(value["authority"], {
        "automation_authorization_id", "promotion_approval_id", "expires_at", "revoked",
    }, "authority")
    if authority["revoked"] is not False:
        raise CharterError("charter has been revoked")
    try:
        expiry = datetime.fromisoformat(authority["expires_at"].replace("Z", "+00:00"))
    except (AttributeError, ValueError) as exc:
        raise CharterError("invalid charter expiry") from exc
    if expiry.tzinfo is None or expiry <= (now or datetime.now(timezone.utc)):
        raise CharterError("charter expired")
    if "governed_publication" in actions and (
        not automation_authorization_id
        or authority["automation_authorization_id"] != automation_authorization_id
    ):
        raise CharterError("current continuous publication authorization is absent or changed")
    if "local_build_promotion" in actions and (
        not promotion_approval_id or authority["promotion_approval_id"] != promotion_approval_id
    ):
        raise CharterError("current local promotion approval is absent or changed")
    for field in ("capabilities", "retry_policy", "escalation", "notification"):
        _decisions(value[field], field)
    if not isinstance(value["required_session"], str) or value["required_session"] not in {"interactive_unlocked", "headless_only"}:
        raise CharterError("unsupported session condition")
    identity = _object(value["identity"], set(_REFS), "identity")
    for key, rel in _REFS.items():
        if not isinstance(identity[key], str) or not _SHA.fullmatch(identity[key]):
            raise CharterError(f"invalid identity hash: {key}")
        if identity[key] != _file_digest(root, rel):
            raise CharterError(f"stale identity: {key}")
    if not isinstance(accepted_sha256, str) or not _SHA.fullmatch(accepted_sha256):
        raise CharterError("independent reviewed-charter approval is absent")
    if canonical_digest(value) != accepted_sha256:
        raise CharterError("reviewed charter digest changed")
    return value
