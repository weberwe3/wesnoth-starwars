"""Deterministic structural inventory for the Wesnoth source tree.

This module intentionally does not preprocess or launch Wesnoth.  Its output is
an auditable source inventory; runtime and play readiness remain unknown until
the installed-engine package supplies evidence.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Iterable, Mapping, Sequence

try:  # Both direct script and package imports are supported.
    from .contract_store import ContractStoreError, INDEX_PATH, load_contracts
except ImportError:
    from contract_store import ContractStoreError, INDEX_PATH, load_contracts

SCHEMA_ID = "wesnoth-starwars.production.source-inventory"
SCHEMA_VERSION = 1
MAX_FILES = 512
MAX_FILE_BYTES = 2_000_000
MAX_TOTAL_BYTES = 20_000_000
MAX_REFERENCES = 10_000
CAMPAIGN_FILE = Path("addons/Star_Wars_Thrawn_Trilogy/_main.cfg")
CONTRACT_FILE = Path(INDEX_PATH)

_ASSIGNMENT = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*$")
_BLOCK = re.compile(r"^\s*\[\s*([+A-Za-z_][A-Za-z0-9_]*)\s*\]\s*$")
_LOCAL = re.compile(r"(?:\{(~add-ons/[^}]+)\}|(?:image|portrait|profile)=\"?([^\s\"]+)\"?)")


class InventoryError(ValueError):
    """Raised when the bounded structural source inventory cannot be trusted."""


def _relative(path: Path, root: Path) -> str:
    try:
        rel = path.resolve().relative_to(root.resolve())
    except ValueError as exc:
        raise InventoryError(f"unsafe path outside repository: {path}") from exc
    if any(part in ("", ".", "..") for part in rel.parts):
        raise InventoryError(f"unsafe path: {rel}")
    return rel.as_posix()


def _safe_file(root: Path, rel: str) -> Path:
    rel_path = Path(rel.replace("/", os.sep))
    if rel_path.is_absolute() or any(part in ("", ".", "..") for part in rel_path.parts):
        raise InventoryError(f"unsafe referenced path: {rel}")
    raw_candidate = root / rel_path
    cursor = root
    for part in rel_path.parts:
        cursor = cursor / part
        if cursor.is_symlink():
            raise InventoryError(f"symlink ancestor is not an accepted source path: {rel}")
    candidate = raw_candidate.resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError as exc:
        raise InventoryError(f"unsafe referenced path: {rel}") from exc
    if not candidate.is_file():
        raise InventoryError(f"missing local referenced path: {rel}")
    return candidate


def _read(root: Path, rel: str) -> str:
    path = _safe_file(root, rel)
    data = path.read_bytes()
    if len(data) > MAX_FILE_BYTES:
        raise InventoryError(f"input file exceeds bound: {rel}")
    return data.decode("utf-8")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _blocks(text: str) -> Iterable[tuple[str, dict[str, str]]]:
    current: str | None = None
    values: dict[str, str] = {}
    for line in text.splitlines():
        match = _BLOCK.match(line.split("#", 1)[0])
        if match:
            if current is not None:
                yield current, values
            current, values = match.group(1), {}
            continue
        match = _ASSIGNMENT.match(line.split("#", 1)[0])
        if match and current is not None:
            values[match.group(1)] = match.group(2).strip().strip('"')
    if current is not None:
        yield current, values


def _scenario_files(root: Path) -> list[str]:
    base = root / "addons/Star_Wars_Thrawn_Trilogy/scenarios"
    paths = sorted(_relative(p, root) for p in base.rglob("*.cfg"))
    if not paths or len(paths) > MAX_FILES:
        raise InventoryError(f"scenario input exceeds bound: {len(paths)} files")
    return paths


def _asset_reference(root: Path, raw: str) -> tuple[str, str] | None:
    raw = raw.strip().strip('"')
    if raw.startswith("~add-ons/"):
        rel = "addons/" + raw[len("~add-ons/"):]
    elif raw.startswith("data/add-ons/"):
        rel = raw[len("data/add-ons/"):]
    elif raw.startswith("units/"):
        rel = "addons/Star_Wars_Thrawn_Trilogy/images/" + raw
    elif raw.startswith("portraits/"):
        rel = "addons/Star_Wars_Thrawn_Trilogy/images/" + raw
    else:
        return ("external", raw)
    if not rel.startswith("addons/Star_Wars_Thrawn_Trilogy/"):
        rel = "addons/Star_Wars_Thrawn_Trilogy/" + rel
    try:
        _safe_file(root, rel)
    except InventoryError as exc:
        if raw.startswith(("units/", "portraits/")) and "missing local referenced path" in str(exc):
            if any(part.startswith("sw-") for part in Path(raw).parts):
                raise
            return ("external", raw)
        raise
    return ("local", rel)


def _validate_dependency_cycles(edges: Sequence[Mapping[str, str]]) -> None:
    graph: dict[str, list[str]] = {}
    for edge in edges:
        source, target = edge.get("from"), edge.get("to")
        if not isinstance(source, str) or not isinstance(target, str):
            raise InventoryError("production dependency edges need string from/to")
        graph.setdefault(source, []).append(target)
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node: str) -> None:
        if node in visiting:
            raise InventoryError(f"production dependency cycle includes {node}")
        if node in visited:
            return
        visiting.add(node)
        for target in sorted(graph.get(node, [])):
            visit(target)
        visiting.remove(node)
        visited.add(node)

    for node in sorted(graph):
        visit(node)


def build_inventory(repo_root: str | os.PathLike[str]) -> dict:
    root = Path(repo_root).resolve()
    campaign_rel = _relative(root / CAMPAIGN_FILE, root)
    campaign_text = _read(root, campaign_rel)
    campaigns = []
    for block, values in _blocks(campaign_text):
        if block == "campaign":
            required = ("id", "define", "first_scenario")
            if any(not values.get(key) for key in required):
                raise InventoryError("campaign entry is missing id, define, or first_scenario")
            campaigns.append({"id": values["id"], "define": values["define"],
                              "first_scenario": values["first_scenario"],
                              "source_path": campaign_rel})
    if not campaigns or len({entry["id"] for entry in campaigns}) != len(campaigns):
        raise InventoryError("duplicate or missing campaign id")

    scenario_ids: dict[str, str] = {}
    scenarios = []
    transitions = []
    assets: dict[str, set[str]] = {}
    external_assets: dict[str, set[str]] = {}
    unit_types: dict[str, str] = {}
    scenario_files = _scenario_files(root)
    unit_files = sorted(_relative(p, root) for p in (root / "addons/Star_Wars_Thrawn_Trilogy/units").rglob("*.cfg"))
    utility_files = sorted(_relative(p, root) for p in (root / "addons/Star_Wars_Thrawn_Trilogy/utils").rglob("*.cfg"))
    lua_files = sorted(_relative(p, root) for p in (root / "addons/Star_Wars_Thrawn_Trilogy/lua").rglob("*.lua"))
    try:
        contracts, contract_files = load_contracts(root)
    except ContractStoreError as exc:
        raise InventoryError(str(exc)) from exc
    input_files = [campaign_rel, *scenario_files, *unit_files, *utility_files, *lua_files, *contract_files]
    if len(input_files) > MAX_FILES:
        raise InventoryError(f"inventory input exceeds file bound: {len(input_files)}")
    total = 0
    source_files = []
    for rel in input_files:
        path = _safe_file(root, rel)
        size = path.stat().st_size
        if size > MAX_FILE_BYTES:
            raise InventoryError(f"input file exceeds bound: {rel}")
        total += size
        source_files.append({"path": rel, "sha256": _sha256(path)})
    if total > MAX_TOTAL_BYTES:
        raise InventoryError("source input exceeds byte bound")
    for rel in scenario_files:
        text = _read(root, rel)
        ids = [values.get("id") for block, values in _blocks(text) if block == "scenario"]
        ids = [value for value in ids if value]
        if len(ids) != 1:
            raise InventoryError(f"scenario file must contain exactly one id: {rel}")
        scenario_id = ids[0]
        if scenario_id in scenario_ids:
            raise InventoryError(f"duplicate scenario id: {scenario_id}")
        scenario_ids[scenario_id] = rel
        next_ids = re.findall(r"^\s*next_scenario\s*=\s*([^\s#]+)", text, re.MULTILINE)
        for target in next_ids:
            transitions.append({"from": scenario_id, "to": target, "source_path": rel})
        for match in _LOCAL.finditer(text):
            raw = match.group(1) or match.group(2)
            if raw:
                asset = _asset_reference(root, raw)
                if asset:
                    target, asset_path = asset
                    (assets if target == "local" else external_assets).setdefault(asset_path, set()).add(rel)

    for rel in unit_files:
        text = _read(root, rel)
        for block, values in _blocks(text):
            if block == "unit_type" and values.get("id"):
                unit_id = values["id"]
                if unit_id in unit_types:
                    raise InventoryError(f"duplicate unit type id: {unit_id}")
                unit_types[unit_id] = rel
            for match in _LOCAL.finditer(text):
                raw = match.group(1) or match.group(2)
                if raw:
                    asset = _asset_reference(root, raw)
                    if asset:
                        target, asset_path = asset
                        (assets if target == "local" else external_assets).setdefault(asset_path, set()).add(rel)

    for campaign in campaigns:
        if campaign["first_scenario"] not in scenario_ids:
            raise InventoryError(f"unknown first_scenario: {campaign['first_scenario']}")
    for edge in transitions:
        if edge["to"] not in scenario_ids:
            raise InventoryError(f"unknown next_scenario: {edge['to']}")
    if len(transitions) > MAX_REFERENCES or len(assets) > MAX_REFERENCES or len(external_assets) > MAX_REFERENCES:
        raise InventoryError("reference input exceeds bounded inventory limits")

    # Local map and image bytes are part of the inventory's source identity.
    # A content-only asset change must invalidate --check just like a WML edit.
    for rel in sorted(assets):
        if rel in input_files:
            continue
        path = _safe_file(root, rel)
        size = path.stat().st_size
        if size > MAX_FILE_BYTES:
            raise InventoryError(f"input file exceeds bound: {rel}")
        total += size
        source_files.append({"path": rel, "sha256": _sha256(path)})
    if len(source_files) > MAX_FILES or total > MAX_TOTAL_BYTES:
        raise InventoryError("source input exceeds bounded inventory limits")

    contract_ids = []
    for contract, declaring_path in contracts:
        contract_ids.append({"id": contract["id"], "source_path": declaring_path})

    for campaign in campaigns:
        campaign["structural_status"] = "observed"
        campaign["runtime_readiness"] = "unknown"
        campaign["play_readiness"] = "unknown"
    campaign_roots = {}
    for campaign in campaigns:
        first_path = scenario_ids.get(campaign["first_scenario"])
        if first_path:
            campaign_roots[Path(first_path).parent.as_posix()] = campaign["id"]
    for rel in scenario_files:
        scenario_id = next(key for key, value in scenario_ids.items() if value == rel)
        campaign_id = campaign_roots.get(Path(rel).parent.as_posix(), "unknown")
        scenarios.append({"id": scenario_id, "campaign_id": campaign_id, "source_path": rel,
                          "next_scenarios": sorted({edge["to"] for edge in transitions if edge["from"] == scenario_id}),
                          "structural_status": "observed", "runtime_readiness": "unknown", "play_readiness": "unknown"})
    inventory = {"schema_id": SCHEMA_ID, "schema_version": SCHEMA_VERSION,
                 "status": {"structural": "observed", "runtime": "unassessed", "play": "unassessed"},
                 "campaigns": sorted(campaigns, key=lambda item: item["id"]),
                 "scenarios": sorted(scenarios, key=lambda item: item["id"]),
                 "transition_edges": sorted(transitions, key=lambda item: (item["from"], item["to"], item["source_path"])),
                 "unit_type_ids": [{"id": key, "source_path": unit_types[key]} for key in sorted(unit_types)],
                 "asset_references": [{"path": key, "source_paths": sorted(value)} for key, value in sorted(assets.items())],
                 "external_asset_references": [{"path": key, "source_paths": sorted(value)} for key, value in sorted(external_assets.items())],
                 "gameplay_contract_ids": sorted(contract_ids, key=lambda item: item["id"]),
                 "source_files": source_files,
                 "production_dependencies": []}
    _validate_dependency_cycles(inventory["production_dependencies"])
    return inventory


def canonical_bytes(inventory: Mapping) -> bytes:
    return (json.dumps(inventory, indent=2, sort_keys=False, ensure_ascii=False) + "\n").encode("utf-8")


def write_inventory(repo_root: str | os.PathLike[str], destination: str | os.PathLike[str]) -> None:
    inventory = build_inventory(repo_root)
    target = Path(destination)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".tmp", dir=target.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(canonical_bytes(inventory))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, target)
    except Exception:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise


def check_inventory(repo_root: str | os.PathLike[str], existing: str | os.PathLike[str]) -> None:
    target = Path(existing)
    if not target.is_file():
        raise InventoryError(f"inventory does not exist: {target}")
    try:
        stored = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise InventoryError(f"inventory is not valid JSON: {target}") from exc
    if not isinstance(stored, dict) or stored.get("schema_id") != SCHEMA_ID or stored.get("schema_version") != SCHEMA_VERSION:
        raise InventoryError("inventory schema identity mismatch")
    if target.read_bytes() != canonical_bytes(build_inventory(repo_root)):
        raise InventoryError("inventory is stale; source changed")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", default=Path(__file__).resolve().parent / "source_inventory.json")
    parser.add_argument("--check", action="store_true", help="reject stale inventory without writing")
    args = parser.parse_args(argv)
    try:
        if args.check:
            check_inventory(args.repo_root, args.output)
        else:
            write_inventory(args.repo_root, args.output)
    except (InventoryError, OSError, UnicodeError) as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
