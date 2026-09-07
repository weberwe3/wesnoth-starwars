#!/usr/bin/env python3

"""Deterministic retained-gameplay contracts for the Wesnoth add-on."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import subprocess
from typing import Any


ADDON_ROOT = "addons/Star_Wars_Thrawn_Trilogy"
CONTRACT_FILE = "tests/gameplay-contracts.json"
MAX_DIAGNOSTIC_CHARS = 6000
MAX_HISTORICAL_TICKETS = 200
_TERRAIN_TOKEN = re.compile(r"^[A-Za-z0-9]{1,4}(?:\^[A-Za-z0-9]{1,4})?$")


def _bounded(values: list[str]) -> str:
    return "\n".join(value for value in values if value)[-MAX_DIAGNOSTIC_CHARS:]


def _read_text(path: Path) -> str:
    if path.is_symlink():
        raise OSError("gameplay contract path must not be a symlink")
    return path.read_text(encoding="utf-8")


def _config_files(root: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for path in sorted((root / ADDON_ROOT).rglob("*.cfg")):
        if path.is_file() and not path.is_symlink():
            result[path.relative_to(root).as_posix()] = _read_text(path)
    return result


def validate_map_data(root: Path, sources: dict[str, str]) -> dict[str, Any]:
    """Reject malformed map cells before the installed engine sees them.

    Wesnoth terrain cells are short terrain/overlay identifiers (for example
    ``Gg`` or ``Gg^Fp``).  A prose label such as ``center`` is not a terrain
    identifier; the engine reports it only after the player tries to launch a
    scenario, so keep this check in the deterministic gate as well.
    """
    failures: list[dict[str, Any]] = []
    for source_path, text in sources.items():
        for match in re.finditer(r"(?s)\bmap_data\s*=\s*\"(.*?)\"", text):
            path = source_path
            value = match.group(1)
            include = re.fullmatch(r"\{~add-ons/([^}]+)\}", value.strip())
            if include:
                relative = Path(include.group(1))
                if ".." in relative.parts:
                    failures.append({
                        "path": path,
                        "row": 1,
                        "column": 1,
                        "token": value[:80],
                        "detail": f"{path}: map_data include escapes the add-on root",
                    })
                    continue
                included_path = root / "addons" / relative
                try:
                    value = _read_text(included_path)
                    path = included_path.relative_to(root).as_posix()
                except (OSError, ValueError):
                    failures.append({
                        "path": path,
                        "row": 1,
                        "column": 1,
                        "token": value[:80],
                        "detail": f"{path}: referenced map_data file is missing or unreadable",
                    })
                    continue
            for row_number, row in enumerate(value.splitlines(), start=1):
                if row.lstrip().startswith("#"):
                    # External .map files are terrain data, not WML. Wesnoth
                    # does not ignore hash-prefixed prose here; it attempts to
                    # parse the words as terrain identifiers at scenario load.
                    failures.append({
                        "path": path,
                        "row": row_number,
                        "column": 1,
                        "token": row.strip()[:80],
                        "detail": (
                            f"{path}: map_data row {row_number} contains a comment; "
                            "Wesnoth map files may contain terrain rows only"
                        ),
                    })
                    continue
                for column, cell in enumerate(row.split(","), start=1):
                    token = cell.strip()
                    if not token or token == "*":
                        continue
                    if not _TERRAIN_TOKEN.fullmatch(token):
                        failures.append({
                            "path": path,
                            "row": row_number,
                            "column": column,
                            "token": token[:80],
                            "detail": (
                                f"{path}: map_data row {row_number}, column {column} "
                                f"has invalid terrain token {token!r}; expected a "
                                "short terrain code such as Gg or Gg^Fp"
                            ),
                        })
    return {
        "pass": not failures,
        "failures": failures[:40],
        "diagnostic": _bounded([item["detail"] for item in failures]),
        "diagnostic_paths": sorted({item["path"] for item in failures})[:20],
    }


def _event_block(text: str, event_id: str) -> str | None:
    for match in re.finditer(r"\[event\](.*?)\[/event\]", text, re.DOTALL):
        block = match.group(1)
        if re.search(r"(?m)^\s*id\s*=\s*" + re.escape(event_id) + r"\s*$", block):
            return block
    return None


def _matches_value(text: str, key: str, expected: str) -> bool:
    return bool(re.search(
        rf"(?m)^\s*{re.escape(key)}\s*=\s*{re.escape(expected)}\s*$", text
    ))


def _contract_result(contract: dict[str, Any], sources: dict[str, str]) -> dict[str, Any]:
    contract_id, path = contract.get("id"), contract.get("path")
    if not isinstance(contract_id, str) or not re.fullmatch(r"sw-[a-z0-9-]{3,80}", contract_id):
        return {"id": str(contract_id or "unknown"), "pass": False, "detail": "Invalid contract id"}
    if not isinstance(path, str) or not path.startswith(ADDON_ROOT + "/"):
        return {"id": contract_id, "pass": False, "detail": "Invalid contract path"}
    text = sources.get(path)
    if text is None:
        return {"id": contract_id, "pass": False, "detail": f"Missing source: {path}", "paths": [path]}
    if contract.get("kind") == "source-id":
        expected_id = contract.get("expected_id")
        passed = isinstance(expected_id, str) and _matches_value(text, "id", expected_id)
        return {"id": contract_id, "pass": passed, "detail": "Source id contract passed" if passed else f"Missing id {expected_id}", "paths": [path]}
    event_id, expected = contract.get("event_id"), contract.get("expected")
    if contract.get("kind") != "event-unit" or not isinstance(event_id, str) or not isinstance(expected, dict):
        return {"id": contract_id, "pass": False, "detail": "Invalid event-unit contract", "paths": [path]}
    block = _event_block(text, event_id)
    if block is None:
        return {"id": contract_id, "pass": False, "detail": f"Missing event {event_id}", "paths": [path]}
    failures: list[str] = []
    for key in ("name", "turn", "first_time_only"):
        value = expected.get(key)
        if isinstance(value, str) and not _matches_value(block, key, value):
            failures.append(f"event {key} is not {value}")
    unit_id = expected.get("unit_id")
    if isinstance(unit_id, str) and not _matches_value(block, "id", unit_id):
        failures.append(f"missing unit id {unit_id}")
    for key in ("side", "type", "x", "y"):
        value = expected.get(key)
        if isinstance(value, str) and not _matches_value(block, key, value):
            failures.append(f"unit {key} is not {value}")
    return {"id": contract_id, "pass": not failures, "detail": "; ".join(failures) or "Event outcome contract passed", "paths": [path]}


def validate_declared_contracts(root: Path, required_paths: list[str] | None = None) -> dict[str, Any]:
    """Validate explicit gameplay behavior contracts against current WML."""
    evidence: dict[str, Any] = {"schema_version": 1, "kind": "declared-gameplay-contracts", "pass": False, "checks": {"contract_file_present": False, "contract_schema_valid": False, "map_data_syntax": False}, "contracts": [], "diagnostic": "", "diagnostic_paths": []}
    try:
        payload = json.loads(_read_text(root / ADDON_ROOT / CONTRACT_FILE))
    except (OSError, json.JSONDecodeError) as exc:
        evidence["diagnostic"] = f"Gameplay contract file unavailable: {exc.__class__.__name__}"
        return evidence
    evidence["checks"]["contract_file_present"] = True
    contracts = payload.get("contracts") if isinstance(payload, dict) else None
    if payload.get("schema_version") != 1 or not isinstance(contracts, list) or not contracts or len(contracts) > 100 or any(not isinstance(item, dict) for item in contracts):
        evidence["diagnostic"] = "Gameplay contract file has an invalid schema"
        return evidence
    evidence["checks"]["contract_schema_valid"] = True
    try:
        sources = _config_files(root)
    except OSError as exc:
        evidence["diagnostic"] = f"Could not read add-on WML: {exc.__class__.__name__}"
        return evidence
    map_evidence = validate_map_data(root, sources)
    evidence["map_data"] = map_evidence
    evidence["checks"]["map_data_syntax"] = map_evidence["pass"]
    results = [_contract_result(item, sources) for item in contracts]
    failed = [item for item in results if not item["pass"]]
    evidence["contracts"] = results
    required = {
        item for item in (required_paths or [])
        if isinstance(item, str) and item.startswith(ADDON_ROOT + "/") and item.endswith((".cfg", ".lua"))
    }
    covered = {path for item in results if item["pass"] for path in item.get("paths", [])}
    uncovered = sorted(required - covered)
    if uncovered:
        failed.append({"detail": "Missing declared gameplay contract for " + ", ".join(uncovered), "paths": uncovered})
    evidence["diagnostic"] = _bounded(
        [map_evidence["diagnostic"]] + [str(item["detail"]) for item in failed]
    )
    evidence["diagnostic_paths"] = sorted({path for item in failed for path in item.get("paths", []) if isinstance(path, str) and path.startswith(ADDON_ROOT + "/")})[:20]
    evidence["diagnostic_paths"] = sorted(set(evidence["diagnostic_paths"]) | set(map_evidence["diagnostic_paths"]))[:20]
    evidence["required_paths"] = sorted(required)
    evidence["pass"] = not failed and map_evidence["pass"]
    return evidence


def _git(root: Path, args: list[str]) -> str:
    completed = subprocess.run(["git", *args], cwd=root, text=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=30, check=False)
    if completed.returncode:
        raise OSError("Git historical inventory unavailable")
    return completed.stdout


def _symbols_added_by_commit(root: Path, commit: str) -> tuple[list[str], list[str]]:
    paths: list[str] = []
    symbols: list[str] = []
    for line in _git(root, ["show", "--format=", "--unified=0", commit, "--", ADDON_ROOT]).splitlines():
        if line.startswith("+++ b/") and line.endswith(".cfg"):
            paths.append(line[6:])
        if line.startswith("+") and not line.startswith("+++"):
            match = re.match(r"\+\s*id\s*=\s*([A-Za-z0-9_]+)\s*$", line)
            if match:
                symbols.append(match.group(1))
    return sorted(set(paths)), sorted(set(symbols))


def validate_historical_retention(root: Path) -> dict[str, Any]:
    """Validate every published add-on ticket in first-parent publication order.

    Git history remains immutable: failures describe a missing retained outcome
    in current main and are repaired by a new, bounded ticket.
    """
    evidence: dict[str, Any] = {"schema_version": 1, "kind": "historical-gameplay-retention", "pass": False, "tickets": [], "diagnostic": "", "diagnostic_paths": []}
    try:
        commits = [line.strip() for line in _git(root, ["log", "--first-parent", "--reverse", "--format=%H", "--", ADDON_ROOT]).splitlines() if re.fullmatch(r"[0-9a-f]{40}", line.strip())]
        if not commits or len(commits) > MAX_HISTORICAL_TICKETS:
            raise OSError("Historical add-on ticket inventory is invalid")
        sources = _config_files(root)
    except OSError as exc:
        evidence["diagnostic"] = f"Historical validation unavailable: {exc.__class__.__name__}"
        return evidence
    corpus = "\n".join(sources.values())
    failures: list[dict[str, Any]] = []
    for sequence, commit in enumerate(commits, start=1):
        paths, symbols = _symbols_added_by_commit(root, commit)
        missing_paths = [path for path in paths if path not in sources]
        missing_symbols = [symbol for symbol in symbols if not re.search(rf"(?m)^\s*id\s*=\s*{re.escape(symbol)}\s*$", corpus)]
        item = {"sequence": sequence, "commit": commit, "pass": not missing_paths and not missing_symbols, "introduced_paths": paths, "introduced_ids": symbols, "missing_paths": missing_paths, "missing_ids": missing_symbols}
        evidence["tickets"].append(item)
        if not item["pass"]:
            failures.append(item)
    evidence["diagnostic"] = _bounded([f"{item['commit'][:12]} no longer retains " + ", ".join(item["missing_paths"] + item["missing_ids"]) for item in failures])
    evidence["diagnostic_paths"] = sorted({path for item in failures for path in item["missing_paths"]})[:20]
    evidence["pass"] = not failures
    return evidence


def validation_digest(evidence: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(evidence, sort_keys=True).encode("utf-8")).hexdigest()
