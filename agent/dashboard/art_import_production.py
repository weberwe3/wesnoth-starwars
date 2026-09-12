#!/usr/bin/env python3

"""Governed production of owner-imported original unit art.

This module never generates art and never reads provider credentials.  It
copies only a verified art contract from the local main checkout into a managed
worktree, validates it, commits it on a dedicated branch, and publishes only
after exact-head CI succeeds.  The dashboard action itself is the owner's
explicit approval for this narrow asset import.
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
import re
import shutil
import subprocess
import time
from typing import Any, Callable

from approval_queue import QueueError, _atomic_json, _run
from art_pipeline import (
    ART_MANIFEST,
    ADDON_ROOT,
    art_import_batch_contract,
    confirm_art_import_batch,
)
from scenario_launch_selftest import validate_post_publish_game
import ticket_runner
import worktree_paths


RUNTIME_FILE = "art-import-production.json"
JOB_ID = re.compile(r"art-[a-z0-9-]{1,100}")
HEX_SHA = re.compile(r"[0-9a-f]{40}")
MAX_ERROR_CHARS = 1_200
CI_TIMEOUT_SECONDS = 1_800
CI_REGISTRATION_ATTEMPTS = 60
CI_REGISTRATION_INTERVAL_SECONDS = 2
PR_HEAD_CONFIRM_ATTEMPTS = 8
PR_HEAD_CONFIRM_INTERVAL_SECONDS = 1
REQUIRED_CHECK_NAME = "repository-gates"


class ArtProductionError(RuntimeError):
    """A bounded, safe error suitable for the local dashboard."""


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def _safe_text(value: object, fallback: str) -> str:
    text = str(value or fallback).replace("\x00", " ")
    text = re.sub(r"(?i)(?:api[_-]?key|token|secret|password)\s*[:=]\s*\S+", "[redacted]", text)
    return " ".join(text.split())[:MAX_ERROR_CHARS]


def status_path(root: Path) -> Path:
    return root / "agent" / "runtime" / RUNTIME_FILE


def read_status(root: Path) -> dict[str, dict[str, Any]]:
    """Read public, credential-free art-import progress records."""

    try:
        value = json.loads(status_path(root).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    jobs = value.get("jobs") if isinstance(value, dict) else None
    if not isinstance(jobs, dict):
        return {}
    return {
        key: dict(item)
        for key, item in jobs.items()
        if isinstance(key, str) and JOB_ID.fullmatch(key) and isinstance(item, dict)
    }


def update_status(root: Path, job_id: str, **values: Any) -> dict[str, Any]:
    """Atomically update one public art-import progress record."""

    if not JOB_ID.fullmatch(job_id):
        raise ArtProductionError("Invalid art job identity")
    jobs = read_status(root)
    current = dict(jobs.get(job_id, {}))
    current.update(values)
    current["updated_at"] = utc_now()
    jobs[job_id] = current
    _atomic_json(status_path(root), {"schema_version": 1, "jobs": jobs})
    return current


def public_status(root: Path) -> dict[str, dict[str, Any]]:
    """Allowlist the small status schema exposed to the browser."""

    allowed = {
        "state", "message", "error", "branch", "commit_sha", "pr_number",
        "pr_url", "started_at", "updated_at", "completed_at", "attempt",
        "changed_paths", "merged", "batch_job_ids",
    }
    return {
        job_id: {key: value for key, value in record.items() if key in allowed}
        for job_id, record in read_status(root).items()
    }


class ArtImportProduction:
    """Perform one owner-approved art import through the normal GitHub gates."""

    def __init__(self, root: Path, event: Callable[..., None]):
        self.root = root.resolve()
        self.event = event

    def begin(self, job_id: str) -> dict[str, Any]:
        batch = art_import_batch_contract(self.root, job_id)
        if not batch.get("pass"):
            # A missing generated PNG or WML reference is an awaiting-art state,
            # not a failed publication.  Leave existing runtime failure evidence
            # intact, but do not create a new red failure card for an incomplete
            # owner-side art set.
            if "requires_llm" in batch:
                return {
                    "pass": False, "state": "awaiting_art",
                    "message": _safe_text(batch.get("message"), "This art set is not ready for import."),
                }
            record = update_status(
                self.root, job_id, state="failed", message="Art import configuration needs correction",
                error=_safe_text(batch.get("message"), "The art import contract is invalid."),
                completed_at=None,
            )
            return {"pass": False, **record}
        job_ids = batch["job_ids"]
        current = read_status(self.root)
        active = next((current.get(item, {}) for item in job_ids if current.get(item, {}).get("state") in {
            "validating", "committing", "publishing", "testing",
        }), None)
        if active:
            return {"pass": True, **active}
        attempt = max((int(current.get(item, {}).get("attempt", 0) or 0) for item in job_ids), default=0) + 1
        message = (
            "Verifying the imported art contract before creating its governed commit."
            if len(job_ids) == 1
            else f"Verifying {len(job_ids)} compatible art imports before creating one governed batch commit."
        )
        record = self._update_batch(
            job_ids, state="validating", message=message, error=None,
            branch=None, commit_sha=None, pr_number=None, pr_url=None,
            started_at=utc_now(), completed_at=None, merged=False, attempt=attempt,
            batch_job_ids=job_ids,
        )
        return {"pass": True, **record}

    def run(self, job_id: str) -> dict[str, Any]:
        """Publish one already-preflighted art contract, restoring source on failure."""

        record = read_status(self.root).get(job_id, {})
        if record.get("state") != "validating":
            raise ArtProductionError("Art import is not ready to run")
        worktree: Path | None = None
        stash_ref: str | None = None
        merged = False
        batch: dict[str, Any] | None = None
        try:
            batch = art_import_batch_contract(self.root, job_id)
            if not batch.get("pass"):
                raise ArtProductionError(_safe_text(batch.get("message"), "Art import is no longer ready."))
            job_ids = batch["job_ids"]
            allowed_paths = self._allowed_paths(batch)
            self._require_source_scope(allowed_paths)
            worktree, branch = self._create_candidate(job_id)
            self._copy_contract(worktree, allowed_paths)
            completed = confirm_art_import_batch(worktree, job_ids)
            if not completed.get("pass"):
                raise ArtProductionError(_safe_text(completed.get("message"), "Candidate art verification failed."))
            validation, changed_paths = self._validate_candidate(worktree, batch, allowed_paths)
            commit_sha = self._commit_candidate(worktree, batch, changed_paths)
            self._update_batch(
                job_ids, state="committing", branch=branch,
                commit_sha=commit_sha, changed_paths=changed_paths,
                message=(
                    "Validated art is committed on an isolated branch; preparing protected publication."
                    if len(job_ids) == 1 else
                    f"Validated {len(job_ids)} art imports are committed as one batch; preparing protected publication."
                ),
                batch_job_ids=job_ids,
            )
            self.event(
                "Original unit art committed for governed publication",
                level="success", ticket_id=job_id,
                detail=(f"Validated {len(changed_paths)} art-import paths for {len(job_ids)} unit state sets "
                        f"on exact commit {commit_sha}."),
            )
            stash_ref = self._stash_matching_source(allowed_paths)
            self._update_batch(
                job_ids, state="publishing",
                message="Creating pull request and waiting for exact-head CI before protected merge.",
            )
            pr_number, pr_url, merge_sha = self._publish_candidate(worktree, branch, commit_sha, job_id)
            merged = True
            self._update_batch(
                job_ids, state="testing", pr_number=pr_number, pr_url=pr_url,
                message="Merged into main; running the installed Wesnoth validation on the published art.",
                merged=True,
            )
            self._pull_main_and_verify(commit_sha, allowed_paths)
            self._drop_stash(stash_ref)
            stash_ref = None
            evidence = validate_post_publish_game(
                self.root, required_gameplay_paths=changed_paths,
            )
            if evidence.get("pass") is not True:
                raise ArtProductionError(
                    "Publication succeeded, but the installed Wesnoth validation failed: "
                    + _safe_text(evidence.get("diagnostic"), "No engine diagnostic was returned.")
                )
            completed_at = utc_now()
            result = self._update_batch(
                job_ids, state="published", message=(
                    "Art production complete: exact-head CI, protected merge, and installed Wesnoth validation passed."
                ), error=None, completed_at=completed_at, merged=True,
            )
            self.event(
                "Original unit art published and tested",
                level="success", ticket_id=job_id,
                detail=f"PR #{pr_number} merged as {merge_sha}; the installed Wesnoth check passed.",
            )
            return {"pass": True, **result}
        except (ArtProductionError, QueueError, OSError, subprocess.SubprocessError, ValueError) as exc:
            if stash_ref and not merged:
                try:
                    self._restore_stash(stash_ref)
                    stash_ref = None
                except (QueueError, OSError, subprocess.SubprocessError) as restore_error:
                    exc = ArtProductionError(
                        _safe_text(exc, "Art production failed.")
                        + " Local source remains preserved in its recovery stash: "
                        + _safe_text(restore_error, "restore it before retrying.")
                    )
            failed_ids = batch.get("job_ids", [job_id]) if batch else [job_id]
            failure = self._update_batch(
                failed_ids, state="failed", message="Art production stopped safely",
                error=_safe_text(exc, "The art production pipeline did not complete."),
                completed_at=None, merged=merged,
            )
            self.event(
                "Original unit art production failed",
                level="error", ticket_id=job_id, detail=failure["error"],
            )
            return {"pass": False, **failure}

    def retry_published_validation(self, job_id: str) -> dict[str, Any]:
        """Re-run only post-merge validation after a published-art test failure."""

        record = read_status(self.root).get(job_id, {})
        if not record.get("merged"):
            return self.begin(job_id)
        job_ids = record.get("batch_job_ids")
        if not isinstance(job_ids, list) or not job_ids or any(not isinstance(item, str) for item in job_ids):
            job_ids = [job_id]
        paths = record.get("changed_paths")
        if not isinstance(paths, list) or not all(isinstance(path, str) for path in paths):
            raise ArtProductionError("Published art has no safe validation path record")
        self._update_batch(
            job_ids, state="testing", error=None,
            message="Re-running installed Wesnoth validation for the published art.",
        )
        evidence = validate_post_publish_game(self.root, required_gameplay_paths=paths)
        if evidence.get("pass") is not True:
            return self._update_batch(
                job_ids, state="failed", merged=True,
                message="Published art still needs a game-validation repair.",
                error=_safe_text(evidence.get("diagnostic"), "No engine diagnostic was returned."),
            )
        return self._update_batch(
            job_ids, state="published", merged=True, error=None,
            message="Published art passed the retried installed Wesnoth validation.",
            completed_at=utc_now(),
        )

    def _update_batch(self, job_ids: list[str], **values: Any) -> dict[str, Any]:
        """Persist the same public lifecycle result for every batch member."""

        results = [update_status(self.root, job_id, **values) for job_id in job_ids]
        return results[0]

    def _allowed_paths(self, contract: dict[str, Any]) -> list[str]:
        source_path = contract.get("source_path")
        assets = contract.get("assets")
        if not isinstance(source_path, str) or not source_path.startswith(ADDON_ROOT + "/"):
            raise ArtProductionError("Art job source path is invalid")
        if not isinstance(assets, list):
            raise ArtProductionError("Art job asset contract is invalid")
        paths = [f"{ADDON_ROOT}/{ART_MANIFEST}", source_path]
        for asset in assets:
            relative = asset.get("path") if isinstance(asset, dict) else None
            if not isinstance(relative, str) or relative.startswith("/") or ".." in Path(relative).parts:
                raise ArtProductionError("Art job contains an unsafe asset path")
            paths.append(f"{ADDON_ROOT}/{relative}")
        return sorted(set(paths))

    def _source_status(self) -> list[str]:
        raw = _run(
            ["git", "status", "--porcelain=v1", "--untracked-files=all"],
            self.root, strip=False,
        )
        paths: list[str] = []
        for line in worktree_paths.unexpected_main_status_entries(raw):
            if len(line) < 4 or " -> " in line:
                raise ArtProductionError("Local main has an unsupported pending Git change")
            paths.append(line[3:])
        return paths

    def _require_source_scope(self, allowed_paths: list[str]) -> None:
        pending = self._source_status()
        outside = sorted(set(pending) - set(allowed_paths))
        if outside:
            raise ArtProductionError(
                "Local main has unrelated uncommitted changes; art production will not include them."
            )

    def _create_candidate(self, job_id: str) -> tuple[Path, str]:
        stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d-%H%M%S")
        slug = job_id.removeprefix("art-")[:80]
        branch = f"agent/art-import-{slug}-{stamp}"
        base = worktree_paths.managed_worktree_root(self.root)
        worktree = (base / f"art-import-{slug}-{stamp}").resolve()
        base.mkdir(parents=True, exist_ok=True)
        if worktree.exists():
            raise ArtProductionError("The generated art worktree already exists")
        _run(["git", "worktree", "add", "-b", branch, str(worktree), "main"], self.root, 90)
        return worktree, branch

    def _copy_contract(self, worktree: Path, allowed_paths: list[str]) -> None:
        for relative in allowed_paths:
            source = self.root / relative
            target = worktree / relative
            if source.is_symlink() or not source.is_file():
                raise ArtProductionError(f"Verified art source is unavailable: {relative}")
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)

    def _validate_candidate(
        self, worktree: Path, contract: dict[str, Any], allowed_paths: list[str]
    ) -> tuple[dict[str, Any], list[str]]:
        unit_ids = contract.get("unit_ids")
        unit_names = contract.get("unit_names")
        if not isinstance(unit_ids, list) or not unit_ids or not isinstance(unit_names, list):
            raise ArtProductionError("Art import batch contract is invalid")
        ticket = {
            "task_id": "ART-BATCH-" + str(unit_ids[0]).upper().replace("_", "-")[:90],
            "objective": "Production import of original art state sets for " + ", ".join(
                str(name) for name in unit_names
            ) + ".",
            "allowed_paths": allowed_paths,
            "validation_profile": "wesnoth-addon-static",
            "validation_root": ADDON_ROOT,
        }
        validation = ticket_runner.run_validation(
            worktree=worktree, ticket=ticket, implementer_rc=0,
        )
        if validation.get("pass") is not True:
            raise ArtProductionError("Deterministic art-import validation did not pass")
        changed_paths = validation.get("scope", {}).get("changed_paths")
        if not isinstance(changed_paths, list) or not changed_paths:
            raise ArtProductionError("The art-import candidate has no safe changed paths")
        if sorted(changed_paths) != sorted(set(changed_paths)) or any(
            path not in allowed_paths for path in changed_paths
        ):
            raise ArtProductionError("The art-import candidate changed an unsafe path")
        return validation, changed_paths

    def _commit_candidate(self, worktree: Path, contract: dict[str, Any], changed_paths: list[str]) -> str:
        _run(["git", "add", "--", *changed_paths], worktree)
        staged = subprocess.run(
            ["git", "diff", "--cached", "--quiet"], cwd=worktree,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30,
            check=False,
        )
        if staged.returncode != 1:
            raise ArtProductionError("The validated art-import candidate did not stage a commit")
        job_ids = contract.get("job_ids")
        if not isinstance(job_ids, list) or not job_ids:
            raise ArtProductionError("Art import batch has no safe job identity")
        subject = str(job_ids[0])[4:52]
        suffix = "" if len(job_ids) == 1 else f" plus {len(job_ids) - 1} related sets"
        _run(["git", "commit", "-m", f"art: import original state set for {subject}{suffix}"], worktree)
        commit_sha = _run(["git", "rev-parse", "HEAD"], worktree)
        if not HEX_SHA.fullmatch(commit_sha):
            raise ArtProductionError("Art-import commit identity is invalid")
        if _run(["git", "status", "--porcelain"], worktree):
            raise ArtProductionError("Art-import worktree changed after its commit")
        return commit_sha

    def _stash_matching_source(self, allowed_paths: list[str]) -> str | None:
        pending = self._source_status()
        if not pending:
            return None
        if set(pending) - set(allowed_paths):
            raise ArtProductionError("Local main has unrelated changes and cannot be prepared safely")
        before = _run(["git", "stash", "list", "--format=%gd"], self.root, strip=False).splitlines()
        _run(
            ["git", "stash", "push", "--include-untracked", "-m", "dashboard-art-import", "--", *allowed_paths],
            self.root,
        )
        after = _run(["git", "stash", "list", "--format=%gd"], self.root, strip=False).splitlines()
        if not after or after == before:
            raise ArtProductionError("Local art could not be preserved for protected publication")
        if self._source_status():
            raise ArtProductionError("Local main was not clean after preserving the art import")
        return after[0]

    def _restore_stash(self, stash_ref: str) -> None:
        _run(["git", "stash", "pop", stash_ref], self.root, 120)

    def _drop_stash(self, stash_ref: str | None) -> None:
        if stash_ref:
            _run(["git", "stash", "drop", stash_ref], self.root)

    def _publish_candidate(
        self, worktree: Path, branch: str, commit_sha: str, job_id: str
    ) -> tuple[int, str, str]:
        _run(["git", "push", "--set-upstream", "origin", branch], worktree, 180)
        try:
            current = json.loads(_run(["gh", "pr", "view", branch, "--json", "number,url,headRefOid,state"], worktree))
        except (QueueError, ValueError):
            url = _run([
                "gh", "pr", "create", "--base", "main", "--head", branch,
                "--title", f"ART: import original unit art for {job_id[4:]}",
                "--body", "## Original art import\n\nOwner-confirmed original unit state assets, deterministic validation, and installed-engine verification.",
            ], worktree, 180)
            current = json.loads(_run(["gh", "pr", "view", url, "--json", "number,url,headRefOid,state"], worktree))
        for _ in range(PR_HEAD_CONFIRM_ATTEMPTS):
            if current.get("headRefOid") == commit_sha:
                break
            time.sleep(PR_HEAD_CONFIRM_INTERVAL_SECONDS)
            current = json.loads(_run(["gh", "pr", "view", str(current.get("url") or branch), "--json", "number,url,headRefOid,state"], worktree))
        if current.get("headRefOid") != commit_sha or not isinstance(current.get("number"), int):
            raise ArtProductionError("GitHub did not confirm the exact art-import commit")
        pr_number = current["number"]
        for _ in range(CI_REGISTRATION_ATTEMPTS):
            checks = json.loads(_run(["gh", "pr", "view", str(pr_number), "--json", "statusCheckRollup"], worktree)).get("statusCheckRollup")
            if isinstance(checks, list) and any(item.get("name") == REQUIRED_CHECK_NAME for item in checks if isinstance(item, dict)):
                break
            time.sleep(CI_REGISTRATION_INTERVAL_SECONDS)
        else:
            raise ArtProductionError("Required exact-head CI was not registered")
        try:
            _run(["gh", "pr", "checks", str(pr_number), "--required", "--watch", "--interval", "10"], worktree, CI_TIMEOUT_SECONDS)
        except QueueError as exc:
            raise ArtProductionError("Required exact-head CI did not pass") from exc
        review = json.loads(_run(["gh", "pr", "view", str(pr_number), "--json", "headRefOid,mergeable,mergeStateStatus,statusCheckRollup"], worktree))
        checks = review.get("statusCheckRollup")
        if review.get("headRefOid") != commit_sha or not isinstance(checks, list) or not checks:
            raise ArtProductionError("Exact-head CI identity changed before merge")
        if not all(
            isinstance(item, dict)
            and item.get("status") == "COMPLETED"
            and item.get("conclusion") == "SUCCESS"
            for item in checks
        ):
            raise ArtProductionError("One or more exact-head checks did not pass")
        if review.get("mergeable") != "MERGEABLE" or review.get("mergeStateStatus") != "CLEAN":
            raise ArtProductionError("Protected merge requirements are not satisfied")
        _run(["gh", "pr", "merge", str(pr_number), "--squash", "--delete-branch=false", "--match-head-commit", commit_sha], worktree, 180)
        merged = json.loads(_run(["gh", "pr", "view", str(pr_number), "--json", "state,mergeCommit,url"], worktree))
        merge_sha = (merged.get("mergeCommit") or {}).get("oid")
        if merged.get("state") != "MERGED" or not isinstance(merge_sha, str) or not HEX_SHA.fullmatch(merge_sha):
            raise ArtProductionError("GitHub did not confirm the protected art merge")
        return pr_number, str(merged.get("url") or current.get("url") or ""), merge_sha

    def _pull_main_and_verify(self, commit_sha: str, allowed_paths: list[str]) -> None:
        _run(["git", "pull", "--ff-only", "origin", "main"], self.root, 180)
        head = _run(["git", "rev-parse", "HEAD"], self.root)
        if not HEX_SHA.fullmatch(head):
            raise ArtProductionError("Local main could not confirm its merged revision")
        status = _run(["git", "status", "--porcelain=v1", "--untracked-files=all"], self.root)
        if worktree_paths.unexpected_main_status_entries(status):
            raise ArtProductionError("Local main changed while applying the published art")
        for relative in allowed_paths:
            candidate_blob = _run(["git", "rev-parse", f"{commit_sha}:{relative}"], self.root)
            current_blob = _run(["git", "hash-object", "--", relative], self.root)
            if candidate_blob != current_blob:
                raise ArtProductionError("Published art does not match the validated candidate")
