"""Stage and verify immutable, unpromoted player-build candidates from Git.

Only a later protected promotion owner may make a tested candidate eligible.
This module never changes the player's current-build pointer or saves.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import tarfile
import tempfile


SCHEMA_ID = "wesnoth-starwars.production.player-build-candidate"
ADDON_ID = "Star_Wars_Thrawn_Trilogy"
PREFIX = f"addons/{ADDON_ID}/"
ALLOWED_SUFFIXES = {".cfg", ".lua", ".map", ".png", ".jpg", ".jpeg",
                    ".ogg", ".wav", ".po", ".mo"}
MAX_FILES = 512
MAX_FILE_BYTES = 5_000_000
MAX_TOTAL_BYTES = 100_000_000
SHA1 = re.compile(r"[0-9a-f]{40}\Z")
SHA256 = re.compile(r"[0-9a-f]{64}\Z")


class BuildStoreError(ValueError):
    """Candidate bytes or source identity cannot be trusted."""


def _git(root: Path, *args: str) -> bytes:
    try:
        run = subprocess.run(["git", "-C", str(root), *args], capture_output=True,
                             timeout=60, check=False)
    except (OSError, subprocess.SubprocessError) as exc:
        raise BuildStoreError("Git source inventory unavailable") from exc
    if run.returncode:
        raise BuildStoreError("Git source identity or archive unavailable")
    return run.stdout


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _allowed(rel: str) -> bool:
    if not isinstance(rel, str) or not rel.startswith(PREFIX) or "\\" in rel or ":" in rel:
        return False
    parts = PurePosixPath(rel).parts
    if (len(parts) < 3 or any(part in ("", ".", "..") for part in parts)
            or parts[2] in {"tests", "assets"}):
        return False
    return PurePosixPath(rel).suffix.lower() in ALLOWED_SUFFIXES


def _package_digest(files: list[dict]) -> str:
    return _sha256(json.dumps(files, sort_keys=True, separators=(",", ":")).encode("utf-8"))


def _archive_files(data: bytes) -> list[tuple[str, bytes]]:
    if len(data) > MAX_TOTAL_BYTES + 10_000_000:
        raise BuildStoreError("Git archive exceeds package bound")
    selected: list[tuple[str, bytes]] = []
    total = 0
    try:
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:") as archive:
            for member in archive:
                if member.isdir():
                    continue
                if not member.isfile():
                    raise BuildStoreError("Git archive contains a link or special file")
                if not _allowed(member.name):
                    continue
                if member.size > MAX_FILE_BYTES:
                    raise BuildStoreError("package member exceeds file bound")
                source = archive.extractfile(member)
                if source is None:
                    raise BuildStoreError("package member cannot be read")
                blob = source.read(MAX_FILE_BYTES + 1)
                if len(blob) != member.size:
                    raise BuildStoreError("package member size mismatch")
                total += len(blob)
                if total > MAX_TOTAL_BYTES or len(selected) >= MAX_FILES:
                    raise BuildStoreError("package exceeds aggregate bounds")
                selected.append((member.name.removeprefix(PREFIX), blob))
    except (tarfile.TarError, OSError) as exc:
        raise BuildStoreError("invalid Git archive") from exc
    if not selected or len({path for path, _ in selected}) != len(selected):
        raise BuildStoreError("package has no unique game files")
    if "_main.cfg" not in {path for path, _ in selected}:
        raise BuildStoreError("package is missing the add-on loader")
    return sorted(selected)


def verify_candidate(path: Path) -> dict:
    manifest_path = path / "manifest.json"
    if (path.is_symlink() or (path / "addon").is_symlink()
            or manifest_path.is_symlink() or not manifest_path.is_file()):
        raise BuildStoreError("candidate manifest missing or symlinked")
    if manifest_path.stat().st_size > 500_000:
        raise BuildStoreError("candidate manifest oversized")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise BuildStoreError("candidate manifest invalid") from exc
    required = {"schema_id", "schema_version", "build_id", "source_commit",
                "source_tree", "addon_id", "package_sha256", "files", "created_at",
                "eligibility"}
    if (not isinstance(manifest, dict) or set(manifest) != required
            or manifest["schema_id"] != SCHEMA_ID or manifest["schema_version"] != 1
            or isinstance(manifest["schema_version"], bool)
            or manifest["addon_id"] != ADDON_ID
            or manifest["eligibility"] != "candidate_unverified"
            or not isinstance(manifest["source_commit"], str)
            or not SHA1.fullmatch(manifest["source_commit"])
            or not isinstance(manifest["source_tree"], str)
            or not SHA1.fullmatch(manifest["source_tree"])
            or manifest["build_id"] != manifest["source_commit"]
            or not isinstance(manifest["package_sha256"], str)
            or not SHA256.fullmatch(manifest["package_sha256"])):
        raise BuildStoreError("unsupported candidate manifest identity")
    try:
        created_at = datetime.fromisoformat(manifest["created_at"])
    except (TypeError, ValueError) as exc:
        raise BuildStoreError("candidate creation time invalid") from exc
    if created_at.tzinfo is None:
        raise BuildStoreError("candidate creation time lacks timezone")
    files = manifest["files"]
    if not isinstance(files, list) or not 1 <= len(files) <= MAX_FILES:
        raise BuildStoreError("invalid candidate file inventory")
    expected_paths: set[str] = set()
    actual_files: list[dict] = []
    total = 0
    for record in files:
        if (not isinstance(record, dict) or set(record) != {"path", "sha256", "bytes"}
                or not isinstance(record["path"], str)
                or not _allowed(PREFIX + record["path"])
                or record["path"] in expected_paths
                or not isinstance(record["sha256"], str) or not SHA256.fullmatch(record["sha256"])
                or not isinstance(record["bytes"], int) or isinstance(record["bytes"], bool)
                or not 0 <= record["bytes"] <= MAX_FILE_BYTES):
            raise BuildStoreError("invalid candidate file entry")
        expected_paths.add(record["path"])
        cursor = path / "addon"
        for part in PurePosixPath(record["path"]).parts:
            cursor = cursor / part
            if cursor.is_symlink():
                raise BuildStoreError("symlinked candidate file")
        if not cursor.is_file() or cursor.stat().st_size != record["bytes"]:
            raise BuildStoreError("candidate file missing or changed")
        digest = _sha256(cursor.read_bytes())
        if digest != record["sha256"]:
            raise BuildStoreError("candidate file digest changed")
        total += record["bytes"]
        actual_files.append(record)
    if total > MAX_TOTAL_BYTES or actual_files != sorted(actual_files, key=lambda item: item["path"]):
        raise BuildStoreError("candidate file inventory exceeds bound or order")
    if "_main.cfg" not in expected_paths:
        raise BuildStoreError("candidate loader is missing")
    if _package_digest(actual_files) != manifest["package_sha256"]:
        raise BuildStoreError("candidate package digest changed")
    discovered = set()
    for item in (path / "addon").rglob("*"):
        if item.is_symlink():
            raise BuildStoreError("symlinked candidate content")
        if item.is_file():
            discovered.add(item.relative_to(path / "addon").as_posix())
    if discovered != expected_paths:
        raise BuildStoreError("candidate contains missing or extra bytes")
    return manifest


def stage_candidate(repo_root: Path, store_root: Path, source_commit: str) -> dict:
    """Atomically stage exact committed game bytes without promoting them."""
    if not isinstance(source_commit, str) or not SHA1.fullmatch(source_commit):
        raise BuildStoreError("source commit must be an exact SHA")
    if store_root.is_symlink():
        raise BuildStoreError("symlinked build store")
    _git(repo_root, "merge-base", "--is-ancestor", source_commit, "origin/main")
    tree = _git(repo_root, "rev-parse", f"{source_commit}^{{tree}}").decode().strip()
    if not SHA1.fullmatch(tree):
        raise BuildStoreError("source tree identity invalid")
    target = store_root / source_commit
    if target.is_symlink():
        raise BuildStoreError("symlinked candidate target")
    if target.exists():
        existing = verify_candidate(target)
        if existing["source_tree"] != tree:
            raise BuildStoreError("existing build ID has a different tree")
        return existing
    archive = _git(repo_root, "archive", "--format=tar", source_commit, "--", PREFIX.removesuffix("/"))
    selected = _archive_files(archive)
    store_root.mkdir(parents=True, exist_ok=True)
    if store_root.is_symlink():
        raise BuildStoreError("symlinked build store")
    temporary = Path(tempfile.mkdtemp(prefix=".candidate-", dir=store_root))
    try:
        records = []
        for rel, blob in selected:
            destination = temporary / "addon" / PurePosixPath(rel)
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(blob)
            records.append({"path": rel, "sha256": _sha256(blob), "bytes": len(blob)})
        manifest = {"schema_id": SCHEMA_ID, "schema_version": 1,
                    "build_id": source_commit, "source_commit": source_commit,
                    "source_tree": tree, "addon_id": ADDON_ID,
                    "package_sha256": _package_digest(records), "files": records,
                    "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    "eligibility": "candidate_unverified"}
        (temporary / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        verify_candidate(temporary)
        os.replace(temporary, target)
        return verify_candidate(target)
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)
