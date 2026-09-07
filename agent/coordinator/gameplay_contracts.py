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


def _ifdef_blocks(text: str) -> dict[str, str]:
    """Return exact preprocessor blocks without attempting to evaluate WML."""

    return {
        match.group(1): match.group(2)
        for match in re.finditer(
            r"(?ms)^\s*#ifdef\s+([A-Za-z0-9_]+)\s*$(.*?)^\s*#endif\s*$",
            text,
        )
    }


def _unit_type_ids(sources: dict[str, str]) -> set[str]:
    """Find project-owned unit definitions in included unit configuration."""

    identifiers: set[str] = set()
    for path, text in sources.items():
        if not path.startswith(ADDON_ROOT + "/units/"):
            continue
        for block in re.finditer(r"(?s)\[unit_type\](.*?)\[/unit_type\]", text):
            match = re.search(r"(?m)^\s*id\s*=\s*(sw_unit_[A-Za-z0-9_]+)\s*$", block.group(1))
            if match:
                identifiers.add(match.group(1))
    return identifiers


def _referenced_unit_type_ids(sources: dict[str, str]) -> set[str]:
    """Collect project unit types instantiated by current scenario sources."""

    identifiers: set[str] = set()
    for path, text in sources.items():
        if path.startswith(ADDON_ROOT + "/scenarios/"):
            identifiers.update(re.findall(
                r"(?m)^\s*type\s*=\s*(sw_unit_[A-Za-z0-9_]+)\s*$", text
            ))
    return identifiers


def _campaign_scenarios(sources: dict[str, str]) -> tuple[dict[str, str], list[str]]:
    """Return unique scenario IDs and duplicate-ID diagnostics.

    Wesnoth resolves ``first_scenario`` and ``next_scenario`` by the scenario
    ID, not by a filename. Keeping this extraction deliberately small avoids
    pretending to fully parse WML while still detecting routes the engine
    could never load.
    """

    scenario_paths: dict[str, str] = {}
    duplicates: list[str] = []
    for path, text in sources.items():
        if not path.startswith(ADDON_ROOT + "/scenarios/"):
            continue
        for block in re.finditer(r"(?s)\[scenario\](.*?)\[/scenario\]", text):
            match = re.search(r"(?m)^\s*id\s*=\s*([A-Za-z0-9_]+)\s*$", block.group(1))
            if not match:
                continue
            scenario_id = match.group(1)
            if scenario_id in scenario_paths and scenario_paths[scenario_id] != path:
                duplicates.append(scenario_id)
            else:
                scenario_paths[scenario_id] = path
    return scenario_paths, sorted(set(duplicates))


def _include_precedes(block: str, relative: str, later: int) -> bool:
    """Whether a WML include covers ``relative`` before a later loader step."""

    before = block[:later]
    candidate = Path(relative)
    # Wesnoth permits either a direct file include or a directory include. A
    # campaign commonly includes ``scenarios}``, which covers all descendant
    # scenario files, so check the path and each parent directory.
    while candidate != Path("."):
        escaped = re.escape(
            "{~add-ons/Star_Wars_Thrawn_Trilogy/" + candidate.as_posix()
        )
        if re.search(escaped + r"(?:[}/])", before):
            return True
        candidate = candidate.parent
    return False


def _wml_code(text: str) -> str:
    """Drop whole-line WML/preprocessor comments before symbol scanning."""

    return "\n".join(
        "" if line.lstrip().startswith("#") else line
        for line in text.splitlines()
    )


def _project_resource_references(sources: dict[str, str]) -> list[tuple[str, str]]:
    """Collect project-owned binary and Lua resources named by WML."""

    references: list[tuple[str, str]] = []
    expression = re.compile(
        r"~add-ons/Star_Wars_Thrawn_Trilogy/([A-Za-z0-9_./-]+\.(?:png|jpe?g|webp|ogg|wav|mp3|lua))",
        re.IGNORECASE,
    )
    for source_path, text in sources.items():
        for match in expression.finditer(_wml_code(text)):
            relative = match.group(1)
            if ".." not in Path(relative).parts:
                references.append((source_path, relative))
    return sorted(set(references))


def _project_lua_actions(root: Path) -> set[str]:
    """Return add-on WML action names implemented by project Lua modules."""

    actions: set[str] = set()
    lua_root = root / ADDON_ROOT / "lua"
    if not lua_root.is_dir():
        return actions
    for path in sorted(lua_root.rglob("*.lua")):
        if path.is_symlink() or not path.is_file():
            continue
        try:
            text = _read_text(path)
        except OSError:
            continue
        actions.update(re.findall(r"wesnoth\.wml_actions\.((?:sw|star_wars)_[A-Za-z0-9_]+)\s*=", text))
        actions.update(re.findall(r"wesnoth\.wml_actions\[['\"]((?:sw|star_wars)_[A-Za-z0-9_]+)['\"]\]\s*=", text))
    return actions


def validate_campaign_dependencies(root: Path, sources: dict[str, str]) -> dict[str, Any]:
    """Validate routes, project resources, macros, Lua, and custom terrain wiring.

    These checks intentionally cover only add-on-owned identifiers and files.
    Core Wesnoth resources and macros remain the engine's responsibility, which
    prevents this deterministic gate from rejecting a valid installed version
    merely because its core data differ from another supported release.
    """

    main_path = ADDON_ROOT + "/_main.cfg"
    main = sources.get(main_path, "")
    failures: list[dict[str, Any]] = []
    blocks = _ifdef_blocks(main)
    campaigns = re.findall(r"(?ms)\[campaign\](.*?)\[/campaign\]", main)
    definitions: dict[str, str] = {}
    for campaign in campaigns:
        define = re.search(r"(?m)^\s*define\s*=\s*([A-Za-z0-9_]+)\s*$", campaign)
        first = re.search(r"(?m)^\s*first_scenario\s*=\s*([A-Za-z0-9_]+)\s*$", campaign)
        if define and first:
            definitions[define.group(1)] = first.group(1)

    scenarios, duplicate_ids = _campaign_scenarios(sources)
    for scenario_id in duplicate_ids:
        failures.append({"path": main_path, "detail": f"Scenario id {scenario_id} is defined more than once"})
    for define, first_scenario in sorted(definitions.items()):
        path = scenarios.get(first_scenario)
        if not path:
            failures.append({"path": main_path, "detail": f"Campaign {define} starts missing scenario {first_scenario}"})
            continue
        block = blocks.get(define, "")
        scenario_marker = block.find("{~add-ons/Star_Wars_Thrawn_Trilogy/scenarios")
        relative = path.removeprefix(ADDON_ROOT + "/")
        if scenario_marker < 0 or not _include_precedes(block, relative, len(block)):
            failures.append({"path": main_path, "detail": f"Campaign {define} does not load its first scenario {first_scenario}"})

    for path, text in sources.items():
        if not path.startswith(ADDON_ROOT + "/scenarios/"):
            continue
        for target in re.findall(r"(?m)^\s*next_scenario\s*=\s*([A-Za-z0-9_]+)\s*$", text):
            if target not in scenarios:
                failures.append({"path": path, "detail": f"Scenario route points to missing next_scenario {target}"})

    for source_path, relative in _project_resource_references(sources):
        target = root / ADDON_ROOT / relative
        if target.is_symlink() or not target.is_file():
            failures.append({"path": source_path, "detail": f"Project resource is missing or unsafe: {relative}"})

    macro_definitions = {
        match.group(1)
        for text in sources.values()
        for match in re.finditer(r"(?m)^\s*#define\s+((?:SW|STAR_WARS)_[A-Za-z0-9_]+)\b", text)
    }
    for path, text in sources.items():
        code = _wml_code(text)
        for macro in re.findall(r"\{((?:SW|STAR_WARS)_[A-Za-z0-9_]+)(?:\s|\})", code):
            if macro not in macro_definitions:
                failures.append({"path": path, "detail": f"Project macro {macro} is used but never defined"})

    lua_actions = _project_lua_actions(root)
    for path, text in sources.items():
        for action in re.findall(r"(?m)^\s*lua_function\s*=\s*((?:sw|star_wars)_[A-Za-z0-9_]+)\s*$", _wml_code(text)):
            if action not in lua_actions:
                failures.append({"path": path, "detail": f"Project Lua action {action} is used but not implemented"})

    terrain_sources = [path for path, text in sources.items() if "[terrain_type]" in text]
    for path in terrain_sources:
        text = sources[path]
        strings = re.findall(r"(?m)^\s*string\s*=\s*([^\s#]+)\s*$", text)
        if not strings or any(not _TERRAIN_TOKEN.fullmatch(value) for value in strings):
            failures.append({"path": path, "detail": "Custom terrain definitions need valid short string= terrain codes"})
        relative = path.removeprefix(ADDON_ROOT + "/")
        for define, block in sorted(blocks.items()):
            scenario_marker = block.find("{~add-ons/Star_Wars_Thrawn_Trilogy/scenarios")
            if scenario_marker >= 0 and not _include_precedes(block, relative, scenario_marker):
                failures.append({"path": main_path, "detail": f"Campaign {define} does not load custom terrain {relative} before scenarios"})

    return {
        "pass": not failures,
        "failures": failures[:40],
        "diagnostic": _bounded([item["detail"] for item in failures]),
        "diagnostic_paths": sorted({item["path"] for item in failures})[:20],
        "scenario_ids": sorted(scenarios),
        "lua_actions": sorted(lua_actions),
        "project_resource_count": len(_project_resource_references(sources)),
        "custom_terrain_sources": terrain_sources,
    }


def validate_campaign_loader(root: Path, sources: dict[str, str]) -> dict[str, Any]:
    """Verify the campaign loader registers every project unit before play."""

    main_path = ADDON_ROOT + "/_main.cfg"
    main = sources.get(main_path, "")
    failures: list[dict[str, Any]] = []
    if not main:
        failures.append({"path": main_path, "detail": "Campaign loader is missing _main.cfg"})
    else:
        blocks = _ifdef_blocks(main)
        campaigns = re.findall(r"(?ms)\[campaign\](.*?)\[/campaign\]", main)
        defines = {
            match.group(1)
            for campaign in campaigns
            if (match := re.search(r"(?m)^\s*define\s*=\s*([A-Za-z0-9_]+)\s*$", campaign))
        }
        expected_binary_path = "path=data/add-ons/Star_Wars_Thrawn_Trilogy"
        expected_units_include = "{~add-ons/Star_Wars_Thrawn_Trilogy/units}"
        expected_scenarios_include = "{~add-ons/Star_Wars_Thrawn_Trilogy/scenarios"
        for define in sorted(defines):
            block = blocks.get(define, "")
            if not block:
                failures.append({
                    "path": main_path,
                    "detail": f"Campaign define {define} has no matching #ifdef loader block",
                })
                continue
            if expected_binary_path not in block:
                failures.append({
                    "path": main_path,
                    "detail": f"Campaign {define} is missing its add-on binary_path",
                })
            units = re.search(r"(?s)\[\+units\](.*?)\[/units\]", block)
            if units is None or expected_units_include not in units.group(1):
                failures.append({
                    "path": main_path,
                    "detail": f"Campaign {define} must load the add-on units directory inside [+units]",
                })
            if expected_scenarios_include not in block:
                failures.append({
                    "path": main_path,
                    "detail": f"Campaign {define} is missing its scenario loader include",
                })
            elif units is not None and units.start() > block.find(expected_scenarios_include):
                failures.append({
                    "path": main_path,
                    "detail": f"Campaign {define} loads scenarios before custom units",
                })

    defined = _unit_type_ids(sources)
    referenced = _referenced_unit_type_ids(sources)
    missing = sorted(referenced - defined)
    if missing:
        failures.append({
            "path": main_path,
            "detail": "Scenario references unregistered project unit types: " + ", ".join(missing),
        })
    return {
        "pass": not failures,
        "failures": failures[:40],
        "diagnostic": _bounded([item["detail"] for item in failures]),
        "diagnostic_paths": sorted({item["path"] for item in failures})[:20],
        "defined_unit_types": sorted(defined),
        "referenced_unit_types": sorted(referenced),
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
    evidence: dict[str, Any] = {"schema_version": 1, "kind": "declared-gameplay-contracts", "pass": False, "checks": {"contract_file_present": False, "contract_schema_valid": False, "map_data_syntax": False, "campaign_loader": False, "campaign_dependencies": False}, "contracts": [], "diagnostic": "", "diagnostic_paths": []}
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
    loader_evidence = validate_campaign_loader(root, sources)
    evidence["campaign_loader"] = loader_evidence
    evidence["checks"]["campaign_loader"] = loader_evidence["pass"]
    dependency_evidence = validate_campaign_dependencies(root, sources)
    evidence["campaign_dependencies"] = dependency_evidence
    evidence["checks"]["campaign_dependencies"] = dependency_evidence["pass"]
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
        [map_evidence["diagnostic"], loader_evidence["diagnostic"], dependency_evidence["diagnostic"]]
        + [str(item["detail"]) for item in failed]
    )
    evidence["diagnostic_paths"] = sorted({path for item in failed for path in item.get("paths", []) if isinstance(path, str) and path.startswith(ADDON_ROOT + "/")})[:20]
    evidence["diagnostic_paths"] = sorted(
        set(evidence["diagnostic_paths"])
        | set(map_evidence["diagnostic_paths"])
        | set(loader_evidence["diagnostic_paths"])
        | set(dependency_evidence["diagnostic_paths"])
    )[:20]
    evidence["required_paths"] = sorted(required)
    evidence["pass"] = (
        not failed and map_evidence["pass"] and loader_evidence["pass"]
        and dependency_evidence["pass"]
    )
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
