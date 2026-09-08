#!/usr/bin/env python3

"""Immutable, baseline-aware acceptance checks for gameplay tickets.

The retained-gameplay contracts prove that the assembled add-on still has
important features. They cannot prove that this ticket made the feature it
promised. These checks compare the candidate to its original worktree base.
"""

from __future__ import annotations

from pathlib import Path
import re
import subprocess
from typing import Any


ADDON_ROOT = "addons/Star_Wars_Thrawn_Trilogy"
MAX_CLAIMS = 12
MAX_TEXT = 500
_SHA = re.compile(r"[0-9a-f]{40}")
_SAFE_PATH = re.compile(r"addons/Star_Wars_Thrawn_Trilogy/[A-Za-z0-9_./-]+")
_UNIT_BLOCK = re.compile(r"(?s)\[unit\](.*?)\[/unit\]")
_EVENT_BLOCK = re.compile(r"(?s)\[event\](.*?)\[/event\]")
_EVENT_SELECTOR = re.compile(r"(?:\[/?event\b|/?event\s*\[)", re.IGNORECASE)
_SIDE_TAG = re.compile(r"(?m)^\s*\[(/?)side\]\s*$")
_WML_TAG = re.compile(r"^\s*\[(/?)[A-Za-z_][A-Za-z0-9_]*\]\s*$")


def _safe_path(value: object) -> str | None:
    if not isinstance(value, str) or not _SAFE_PATH.fullmatch(value):
        return None
    if ".." in Path(value).parts:
        return None
    return value


def validate_acceptance_contract(value: object) -> dict[str, Any]:
    """Validate untrusted planner contract data without reading a worktree."""

    if not isinstance(value, dict):
        return {"pass": False, "diagnostic": "Gameplay tickets require an acceptance contract."}
    if value.get("schema_version") != 1:
        return {"pass": False, "diagnostic": "Acceptance contract schema_version must be 1."}
    claims = value.get("claims")
    if not isinstance(claims, list) or not 1 <= len(claims) <= MAX_CLAIMS:
        return {"pass": False, "diagnostic": f"Acceptance contracts require 1-{MAX_CLAIMS} claims."}
    normalized: list[dict[str, Any]] = []
    for index, claim in enumerate(claims, start=1):
        if not isinstance(claim, dict):
            return {"pass": False, "diagnostic": f"Acceptance claim {index} must be an object."}
        kind = claim.get("kind")
        path = _safe_path(claim.get("path"))
        baseline = claim.get("base", "absent")
        if kind not in {"source_text", "unit_placement", "event_contains", "map_cell", "installed_game_repair"}:
            return {"pass": False, "diagnostic": f"Acceptance claim {index} has an unsupported kind."}
        if path is None:
            return {"pass": False, "diagnostic": f"Acceptance claim {index} has an unsafe project path."}
        if baseline not in {"absent", "different"}:
            return {"pass": False, "diagnostic": f"Acceptance claim {index} has an invalid base condition."}
        item: dict[str, Any] = {"kind": kind, "path": path, "base": baseline}
        if kind == "installed_game_repair":
            # A repair created from an actual installed-engine failure cannot
            # truthfully name its source-level remedy before investigation.
            # It remains explicitly deferred and is only certified by the
            # exact post-merge installed-game run in approval_queue.py.
            item["deferred_to_installed_game"] = True
        elif kind == "source_text":
            contains = claim.get("contains")
            if not isinstance(contains, str) or not 1 <= len(contains) <= MAX_TEXT:
                return {"pass": False, "diagnostic": f"Acceptance source_text claim {index} needs bounded text."}
            item["contains"] = contains
        elif kind == "unit_placement":
            required = ("unit_type", "instance_id", "side", "x", "y")
            if not all(isinstance(claim.get(key), (str, int)) and str(claim[key]) for key in required):
                return {"pass": False, "diagnostic": f"Acceptance unit_placement claim {index} is incomplete."}
            item.update({key: str(claim[key]) for key in required})
        elif kind == "event_contains":
            event_id, contains = claim.get("event_id"), claim.get("contains")
            if not isinstance(event_id, str) or not event_id or not isinstance(contains, str) or not contains:
                return {"pass": False, "diagnostic": f"Acceptance event_contains claim {index} is incomplete."}
            if len(event_id) > 160 or len(contains) > MAX_TEXT:
                return {"pass": False, "diagnostic": f"Acceptance event_contains claim {index} is too large."}
            # `contains` is checked against the body of the matching WML event,
            # not against an XPath/CSS-style selector. Reject a selector before
            # a worktree is created with proof that can never pass.
            if _EVENT_SELECTOR.search(contains):
                return {
                    "pass": False,
                    "diagnostic": (
                        f"Acceptance event_contains claim {index} must use literal "
                        "event-body evidence, not an event selector."
                    ),
                }
            normalized_contains = re.sub(r"\s+", "", contains)
            normalized_id = re.sub(r"\s+", "", event_id)
            if normalized_contains in {normalized_id, f"id={normalized_id}"}:
                return {
                    "pass": False,
                    "diagnostic": (
                        f"Acceptance event_contains claim {index} must prove event behavior "
                        "with literal body text, not repeat only its id."
                    ),
                }
            item.update({"event_id": event_id, "contains": contains})
        else:
            fields = ("row", "column", "terrain")
            if not isinstance(claim.get("row"), int) or claim["row"] < 1:
                return {"pass": False, "diagnostic": f"Acceptance map_cell claim {index} needs a positive row."}
            if not isinstance(claim.get("column"), int) or claim["column"] < 1:
                return {"pass": False, "diagnostic": f"Acceptance map_cell claim {index} needs a positive column."}
            if not isinstance(claim.get("terrain"), str) or not claim["terrain"] or len(claim["terrain"]) > 12:
                return {"pass": False, "diagnostic": f"Acceptance map_cell claim {index} needs a terrain token."}
            item.update({key: claim[key] for key in fields})
        normalized.append(item)
    return {"pass": True, "contract": {"schema_version": 1, "claims": normalized}}


def _git_text(worktree: Path, sha: str, path: str) -> str:
    completed = subprocess.run(
        ["git", "show", f"{sha}:{path}"], cwd=worktree,
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
        timeout=30, check=False,
    )
    return completed.stdout if completed.returncode == 0 else ""


def _base_sha(worktree: Path) -> str | None:
    completed = subprocess.run(
        ["git", "merge-base", "HEAD", "main"], cwd=worktree,
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
        timeout=30, check=False,
    )
    value = completed.stdout.strip()
    return value if completed.returncode == 0 and _SHA.fullmatch(value) else None


def _unit_fields(block: str) -> dict[str, str]:
    return {
        key: value.strip().strip('"')
        for key, value in re.findall(r"(?m)^\s*(type|id|side|x|y)\s*=\s*([^\n#]+)", block)
    }


def _side_blocks(text: str) -> list[str]:
    """Return balanced WML side bodies without mistaking nested tags for sides."""

    blocks: list[str] = []
    start: int | None = None
    depth = 0
    for match in _SIDE_TAG.finditer(text):
        if not match.group(1):
            if depth == 0:
                start = match.end()
            depth += 1
        elif depth:
            depth -= 1
            if depth == 0 and start is not None:
                blocks.append(text[start:match.start()])
                start = None
    return blocks


def _direct_side_id(side_block: str) -> str | None:
    """Read side= from a side body, excluding nested unit/event properties."""

    depth = 0
    for line in side_block.splitlines():
        tag = _WML_TAG.match(line)
        if tag:
            depth += -1 if tag.group(1) else 1
            continue
        if depth == 0:
            field = re.match(r"^\s*side\s*=\s*([^\n#]+)", line)
            if field:
                return field.group(1).strip().strip('"')
    return None


def _unit_matches(fields: dict[str, str], expected: dict[str, str]) -> bool:
    return all(fields.get(key) == value for key, value in expected.items())


def _unit_present(text: str, claim: dict[str, Any]) -> bool:
    expected = {
        "type": claim["unit_type"], "id": claim["instance_id"], "side": claim["side"],
        "x": claim["x"], "y": claim["y"],
    }
    # Event-created and standalone units state their own side explicitly.
    for block in _UNIT_BLOCK.findall(text):
        fields = _unit_fields(block)
        if _unit_matches(fields, expected):
            return True
    # Scenario setup units nested inside a [side] inherit that side in WML.
    # They are valid without a duplicate side= field on the [unit] itself.
    for side_block in _side_blocks(text):
        inherited_side = _direct_side_id(side_block)
        if inherited_side is None:
            continue
        for block in _UNIT_BLOCK.findall(side_block):
            fields = _unit_fields(block)
            fields.setdefault("side", inherited_side)
            if _unit_matches(fields, expected):
                return True
    return False


def _event_contains(text: str, claim: dict[str, Any]) -> bool:
    for block in _EVENT_BLOCK.findall(text):
        identity = re.search(r"(?m)^\s*id\s*=\s*([^\s#]+)", block)
        if identity and identity.group(1).strip('"') == claim["event_id"]:
            return claim["contains"] in block
    return False


def _map_cell(text: str, claim: dict[str, Any]) -> bool:
    rows = [line.strip() for line in text.splitlines() if line.strip() and not line.lstrip().startswith("#")]
    row_index = claim["row"] - 1
    if row_index >= len(rows):
        return False
    cells = [cell.strip() for cell in rows[row_index].split(",")]
    column_index = claim["column"] - 1
    return column_index < len(cells) and cells[column_index] == claim["terrain"]


def _claim_present(text: str, claim: dict[str, Any]) -> bool:
    if claim["kind"] == "installed_game_repair":
        return True
    if claim["kind"] == "source_text":
        return claim["contains"] in text
    if claim["kind"] == "unit_placement":
        return _unit_present(text, claim)
    if claim["kind"] == "event_contains":
        return _event_contains(text, claim)
    return _map_cell(text, claim)


def validate_ticket_acceptance(
    worktree: Path,
    ticket: dict[str, Any],
    *,
    base_sha: str | None = None,
) -> dict[str, Any]:
    """Prove each claim is present now and was not already true at base."""

    if ticket.get("validation_profile") != "wesnoth-addon-static":
        return {"pass": True, "state": "not_applicable", "checks": [], "base_sha": None}
    contract_result = validate_acceptance_contract(ticket.get("acceptance"))
    if not contract_result["pass"]:
        return {"pass": False, "state": "missing_or_invalid", "checks": [], "base_sha": base_sha,
                "diagnostic": contract_result["diagnostic"]}
    base = base_sha or ticket.get("base_sha") or _base_sha(worktree)
    if base is None or not _SHA.fullmatch(base):
        return {"pass": False, "state": "base_unavailable", "checks": [], "base_sha": base,
                "diagnostic": "The ticket base revision could not be determined."}
    allowed_paths = ticket.get("allowed_paths") or []
    checks: list[dict[str, Any]] = []
    for index, claim in enumerate(contract_result["contract"]["claims"], start=1):
        path = claim["path"]
        target = worktree / path
        try:
            candidate = target.read_text(encoding="utf-8") if target.is_file() and not target.is_symlink() else ""
        except OSError:
            candidate = ""
        baseline = _git_text(worktree, base, path)
        in_scope = any(_path_matches(path, pattern) for pattern in allowed_paths if isinstance(pattern, str))
        candidate_present = _claim_present(candidate, claim)
        base_present = _claim_present(baseline, claim)
        changed = candidate != baseline
        deferred = claim["kind"] == "installed_game_repair"
        semantic_changed = candidate_present != base_present
        passes = deferred or (in_scope and candidate_present and changed and semantic_changed)
        checks.append({
            "index": index, "kind": claim["kind"], "path": path, "pass": passes,
            "candidate_present": candidate_present, "base_present": base_present,
            "path_changed_from_base": changed, "path_within_ticket_scope": in_scope,
            "claim_changed_from_base": semantic_changed,
            "deferred_to_installed_game": deferred,
        })
    failures = [item for item in checks if not item["pass"]]
    diagnostic = "All promised gameplay acceptance claims differ from the ticket base."
    if not failures and any(item["deferred_to_installed_game"] for item in checks):
        diagnostic = "Installed-game repair acceptance is deferred to the exact post-merge engine validation."
    if failures:
        first = failures[0]
        if first["base_present"]:
            reason = "was already satisfied by the ticket base"
        elif not first["candidate_present"]:
            reason = "is missing from the candidate"
        elif not first["path_changed_from_base"]:
            reason = "did not change from the ticket base"
        else:
            reason = "is outside the ticket's allowed paths"
        diagnostic = f"Acceptance claim {first['index']} ({first['kind']} at {first['path']}) {reason}."
    return {
        "pass": not failures, "state": "passed" if not failures else "failed",
        "base_sha": base, "contract": contract_result["contract"], "checks": checks,
        "diagnostic": diagnostic,
    }


def _path_matches(path: str, pattern: str) -> bool:
    if pattern.endswith("/**"):
        return path.startswith(pattern[:-2])
    return path == pattern
