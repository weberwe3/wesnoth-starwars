"""Bounded, deterministic gameplay contract index and legacy v1 reader."""

from __future__ import annotations

import json
from pathlib import Path
import re


INDEX_PATH = "addons/Star_Wars_Thrawn_Trilogy/tests/gameplay-contracts.json"
SHARD_DIR = "addons/Star_Wars_Thrawn_Trilogy/tests/gameplay-contracts"
MAX_SHARDS = 32
MAX_CONTRACTS_PER_SHARD = 100
MAX_CONTRACTS = 1000
_FILENAME = re.compile(r"[a-z0-9][a-z0-9-]{0,63}\.json\Z")


class ContractStoreError(ValueError):
    """The contract store cannot be trusted."""


def _json_file(path: Path) -> dict:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 2_000_000:
        raise ContractStoreError(f"missing, symlinked, or oversized contract file: {path.name}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ContractStoreError(f"invalid contract JSON: {path.name}") from exc
    if not isinstance(value, dict):
        raise ContractStoreError(f"invalid contract object: {path.name}")
    return value


def _checked_file(root: Path, rel: str) -> dict:
    cursor = root
    for part in Path(rel).parts:
        cursor = cursor / part
        if cursor.is_symlink():
            raise ContractStoreError(f"symlinked contract path: {rel}")
    return _json_file(cursor)


def load_contracts(root: Path) -> tuple[list[tuple[dict, str]], list[str]]:
    """Return (contract, declaring path) pairs and every hashed store path.

    The v1 single-file form remains readable for historical fixtures. A v2
    index is the only current repository authority; unlisted shards are rejected
    so no gameplay contract silently disappears from the index.
    """
    index = _checked_file(root, INDEX_PATH)
    if index.get("schema_version") == 1:
        names = [(INDEX_PATH, index)]
        if set(index) != {"schema_version", "contracts"}:
            raise ContractStoreError("unsupported legacy contract fields")
    elif index.get("schema_version") == 2:
        if set(index) != {"schema_version", "files"}:
            raise ContractStoreError("invalid contract index fields")
        files = index["files"]
        if (not isinstance(files, list) or not 1 <= len(files) <= MAX_SHARDS
                or any(not isinstance(name, str) or not _FILENAME.fullmatch(name) for name in files)
                or len(set(files)) != len(files) or files != sorted(files)):
            raise ContractStoreError("invalid or unordered contract shard names")
        directory = root / SHARD_DIR
        if directory.is_symlink() or not directory.is_dir():
            raise ContractStoreError("missing or symlinked contract shard directory")
        actual = sorted(path.name for path in directory.iterdir() if path.is_file() or path.is_symlink())
        if actual != files:
            raise ContractStoreError("contract shard directory differs from index")
        names = [(f"{SHARD_DIR}/{name}", _checked_file(root, f"{SHARD_DIR}/{name}")) for name in files]
    else:
        raise ContractStoreError("unsupported gameplay contract schema")
    result: list[tuple[dict, str]] = []
    seen: set[str] = set()
    for rel, value in names:
        contracts = value.get("contracts")
        if set(value) != {"schema_version", "contracts"} or value.get("schema_version") != 1:
            raise ContractStoreError(f"invalid contract shard schema: {rel}")
        if not isinstance(contracts, list) or not 1 <= len(contracts) <= MAX_CONTRACTS_PER_SHARD:
            raise ContractStoreError(f"invalid contract count: {rel}")
        for contract in contracts:
            if not isinstance(contract, dict) or not isinstance(contract.get("id"), str) or not contract["id"]:
                raise ContractStoreError(f"contract missing id: {rel}")
            if contract["id"] in seen:
                raise ContractStoreError(f"duplicate gameplay contract id: {contract['id']}")
            seen.add(contract["id"])
            result.append((contract, rel))
            if len(result) > MAX_CONTRACTS:
                raise ContractStoreError("aggregate gameplay contract limit exceeded")
    return result, [INDEX_PATH, *[rel for rel, _ in names if rel != INDEX_PATH]]
