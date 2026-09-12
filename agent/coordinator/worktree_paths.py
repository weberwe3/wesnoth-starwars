"""Trusted locations for coordinator-managed Git worktrees."""

from __future__ import annotations

import os
from pathlib import Path


WORKTREE_ROOT_ENV = "WESNOTH_AGENT_WORKTREE_ROOT"
LOCAL_HANDOFF_STATUS = "?? docs/AI_HANDOFF_REFERENCE.md"


def unexpected_main_status_entries(status: str) -> list[str]:
    """Return all main-worktree changes except the required local handoff.

    The handoff is intentionally supplied locally and stays out of ticket
    worktrees. Every other porcelain status entry remains a hard stop.
    """

    return [
        line for line in status.splitlines()
        if line and line != LOCAL_HANDOFF_STATUS
    ]


def legacy_worktree_root(repo_root: Path) -> Path:
    root = repo_root.resolve()
    return (root.parent / f"{root.name}-worktrees").resolve()


def managed_worktree_root(repo_root: Path) -> Path:
    """Return the configured primary root after rejecting unsafe broad paths."""

    root = repo_root.resolve()
    raw = os.environ.get(WORKTREE_ROOT_ENV, "").strip()
    if not raw:
        return legacy_worktree_root(root)
    candidate = Path(raw)
    if not candidate.is_absolute():
        raise RuntimeError(f"{WORKTREE_ROOT_ENV} must be an absolute path")
    candidate = candidate.resolve()
    forbidden = {Path("/").resolve(), Path.home().resolve(), root}
    if candidate in forbidden or candidate.parent == candidate:
        raise RuntimeError(f"{WORKTREE_ROOT_ENV} identifies an unsafe broad path")
    return candidate


def managed_worktree_roots(repo_root: Path) -> tuple[Path, ...]:
    """Return the primary root plus the legacy root for safe resumption."""

    primary = managed_worktree_root(repo_root)
    legacy = legacy_worktree_root(repo_root)
    return (primary,) if primary == legacy else (primary, legacy)


def contains_managed_worktree(repo_root: Path, candidate: Path) -> bool:
    resolved = candidate.resolve()
    for managed_root in managed_worktree_roots(repo_root):
        try:
            resolved.relative_to(managed_root)
            return True
        except ValueError:
            continue
    return False


def named_worktree(repo_root: Path, name: str, *, must_exist: bool) -> Path:
    """Resolve an exact worktree name without accepting an arbitrary path."""

    candidates = [root / name for root in managed_worktree_roots(repo_root)]
    existing = [candidate.resolve() for candidate in candidates if candidate.is_dir()]
    if len(existing) > 1:
        raise RuntimeError("Managed worktree name is ambiguous across configured roots")
    if existing:
        return existing[0]
    if must_exist:
        raise RuntimeError("Managed worktree is unavailable")
    return candidates[0].resolve()
