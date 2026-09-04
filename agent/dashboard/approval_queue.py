#!/usr/bin/env python3

"""Fail-closed local ticket queue, deletion gate, and publication pipeline."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import threading
from typing import Any, Callable


BRANCH = re.compile(r"agent/[a-z0-9][a-z0-9._/-]{0,180}")
HEX_SHA = re.compile(r"[0-9a-f]{40}")
REQUEST_ID = re.compile(r"[0-9a-f]{16}")
SAFE_CONCLUSIONS = {"SUCCESS"}
PUBLISH_TIMEOUT_SECONDS = 1800


class QueueError(RuntimeError):
    """A safe, user-displayable queue error."""


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def _atomic_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    os.chmod(path.parent, 0o700)
    fd, temporary = tempfile.mkstemp(
        prefix=".approval-queue-", suffix=".json", dir=path.parent, text=True
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(json.dumps(value, indent=2) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _run(
    command: list[str], cwd: Path, timeout: int = 60, *, strip: bool = True
) -> str:
    environment = {
        key: value for key, value in os.environ.items()
        if not re.search(
            r"(?:API[_-]?KEY|TOKEN|SECRET|PASSWORD|CREDENTIAL|PRIVATE[_-]?KEY)",
            key,
            re.IGNORECASE,
        )
    }
    completed = subprocess.run(
        command,
        cwd=cwd,
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=timeout,
        check=False,
    )
    if completed.returncode != 0:
        raise QueueError(f"{command[0]} {command[1]} failed")
    return completed.stdout.strip() if strip else completed.stdout


def _default() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "updated_at": utc_now(),
        "records": [],
        "activity": [],
    }


class ApprovalQueue:
    def __init__(self, root: Path, path: Path | None = None):
        self.root = root.resolve()
        self.path = (path or self.root / "agent" / "runtime" / "approval-queue.json").resolve()
        self.runtime = self.path.parent
        self._lock = threading.RLock()
        if not self.path.exists():
            _atomic_json(self.path, _default())
        else:
            self._recover_interrupted_publication()

    def _recover_interrupted_publication(self) -> None:
        state = self.read()
        interrupted = [item for item in state["records"] if item.get("state") == "publishing"]
        if not interrupted:
            return
        for record in interrupted:
            record.update({
                "state": "failed",
                "error": "Dashboard restarted during publication; remote state requires review",
                "updated_at": utc_now(),
            })
            self._stale_after(state, record)
            state["activity"].append({
                "id": hashlib.sha256(f"restart:{record.get('id')}".encode()).hexdigest()[:16],
                "at": utc_now(),
                "level": "error",
                "message": "Publication was interrupted by a dashboard restart",
                "detail": "Publication stopped fail-closed. Review GitHub and local main before retrying.",
                "ticket_id": record.get("ticket_id"),
            })
        state["updated_at"] = utc_now()
        _atomic_json(self.path, state)

    def read(self) -> dict[str, Any]:
        with self._lock:
            try:
                value = json.loads(self.path.read_text(encoding="utf-8"))
            except (FileNotFoundError, OSError, json.JSONDecodeError):
                value = _default()
            if not isinstance(value, dict):
                return _default()
            records = value.get("records")
            activity = value.get("activity")
            return {
                "schema_version": 1,
                "updated_at": value.get("updated_at") or utc_now(),
                "records": records if isinstance(records, list) else [],
                "activity": activity if isinstance(activity, list) else [],
            }

    def _update(self, change: Callable[[dict[str, Any]], None]) -> dict[str, Any]:
        with self._lock:
            state = self.read()
            change(state)
            state["updated_at"] = utc_now()
            state["records"] = state["records"][-100:]
            state["activity"] = state["activity"][-300:]
            _atomic_json(self.path, state)
            return state

    def event(
        self,
        message: str,
        *,
        level: str = "info",
        detail: str | None = None,
        ticket_id: str | None = None,
        failure_class: str | None = None,
        required_action: str | None = None,
        recovery_attempt: int | None = None,
        recovery_limit: int | None = None,
    ) -> None:
        record = {
            "id": hashlib.sha256(
                f"{utc_now()}:{message}:{ticket_id or ''}".encode()
            ).hexdigest()[:16],
            "at": utc_now(),
            "level": level if level in {"info", "success", "warning", "error"} else "info",
            "message": message[:300],
            "detail": (detail or message)[:2000],
            "ticket_id": ticket_id,
        }
        if failure_class:
            record["failure_class"] = failure_class[:80]
        if required_action:
            record["required_action"] = required_action[:1000]
        if recovery_attempt is not None:
            record["recovery_attempt"] = recovery_attempt
        if recovery_limit is not None:
            record["recovery_limit"] = recovery_limit
        self._update(lambda state: state["activity"].append(record))

    def public_state(self) -> dict[str, Any]:
        state = self.read()
        allowed = {
            "id", "ticket_id", "purpose", "impact", "dependency_index",
            "changed_paths", "deleted_paths", "branch", "base_sha", "commit_sha",
            "state", "created_at", "updated_at", "validation", "reviewer",
            "pr_number", "pr_url", "merge_sha", "error", "deletion_request",
        }
        records = [
            {key: item.get(key) for key in allowed}
            for item in state["records"]
            if isinstance(item, dict)
        ]
        activity_allowed = {
            "id", "at", "level", "message", "detail", "ticket_id",
            "failure_class", "required_action", "recovery_attempt", "recovery_limit",
        }
        activity = [
            {key: item.get(key) for key in activity_allowed}
            for item in state["activity"]
            if isinstance(item, dict)
        ]
        return {"records": records, "activity": activity}

    def add_passed_ticket(
        self,
        result: dict[str, Any],
        ticket: dict[str, Any],
        *,
        summary: str,
        impact: str,
    ) -> dict[str, Any]:
        if result.get("final_verdict") != "PASS":
            raise QueueError("Only a locally passing ticket can enter the queue")
        branch = result.get("branch")
        worktree_value = result.get("worktree")
        if not isinstance(branch, str) or not BRANCH.fullmatch(branch):
            raise QueueError("Ticket result contains an invalid branch")
        if not isinstance(worktree_value, str):
            raise QueueError("Ticket result contains no worktree")
        worktree = Path(worktree_value).resolve()
        expected_parent = (self.root.parent / f"{self.root.name}-worktrees").resolve()
        try:
            worktree.relative_to(expected_parent)
        except ValueError as exc:
            raise QueueError("Ticket worktree is outside the managed worktree root") from exc
        if not worktree.is_dir():
            raise QueueError("Ticket worktree is unavailable")
        if _run(["git", "branch", "--show-current"], worktree) != branch:
            raise QueueError("Ticket branch no longer matches its evidence")

        base_sha = _run(["git", "merge-base", "main", "HEAD"], worktree)
        if not HEX_SHA.fullmatch(base_sha):
            raise QueueError("Ticket base commit is invalid")
        changed_paths, deleted_paths = self._changes(worktree)
        validated = result.get("validation", {}).get("scope", {}).get("changed_paths", [])
        if sorted(changed_paths) != sorted(validated):
            raise QueueError("Ticket changes no longer match validated evidence")
        queued_ids = {item.get("ticket_id") for item in self.read()["records"]}
        if ticket.get("task_id") in queued_ids:
            raise QueueError("Ticket is already queued")

        queue_state = self.read()
        record_id = hashlib.sha256(
            f"{ticket['task_id']}:{branch}:{base_sha}".encode()
        ).hexdigest()[:16]
        record = {
            "id": record_id,
            "ticket_id": ticket["task_id"],
            "purpose": (summary or ticket["objective"])[:500],
            "impact": (impact or ticket["objective"])[:1200],
            "dependency_index": len(queue_state["records"]) + 1,
            "changed_paths": changed_paths,
            "deleted_paths": deleted_paths,
            "branch": branch,
            "worktree_name": worktree.name,
            "base_sha": base_sha,
            "commit_sha": None,
            "state": "deletion_pending" if deleted_paths else "committing",
            "created_at": utc_now(),
            "updated_at": utc_now(),
            "validation": "PASS",
            "reviewer": result.get("reviewer_used"),
            "pr_number": None,
            "pr_url": None,
            "merge_sha": None,
            "error": None,
            "deletion_request": None,
        }
        if deleted_paths:
            request = self._deletion_request(record, worktree)
            record["deletion_request"] = {
                "request_id": request["request_id"],
                "manifest_digest": request["manifest_digest"],
                "state": "pending",
            }
        else:
            record["commit_sha"] = self._commit(record, worktree)
            record["state"] = "ready"

        self._update(lambda state: state["records"].append(record))
        if deleted_paths:
            self.event(
                f"{ticket['task_id']} requires deletion approval",
                level="warning",
                detail="The ticket is paused before commit because it deletes: "
                + ", ".join(deleted_paths),
                ticket_id=ticket["task_id"],
            )
        else:
            self.event(
                f"{ticket['task_id']} added to the approval queue",
                level="success",
                detail=f"Local commit {record['commit_sha']} passed all local gates.",
                ticket_id=ticket["task_id"],
            )
        return record

    def _changes(self, worktree: Path) -> tuple[list[str], list[str]]:
        output = _run(
            ["git", "diff", "--name-status", "-M", "main"],
            worktree,
            strip=False,
        )
        changed: list[str] = []
        deleted: list[str] = []
        for line in output.splitlines():
            fields = line.split("\t")
            if len(fields) != 2 or fields[0].startswith(("R", "C")):
                raise QueueError("Unsupported Git status in ticket worktree")
            code, path = fields
            changed.append(path)
            if code == "D":
                deleted.append(path)
        status = _run(
            ["git", "status", "--porcelain=v1", "--untracked-files=all"],
            worktree,
            strip=False,
        )
        for line in status.splitlines():
            if len(line) < 4 or " -> " in line:
                raise QueueError("Unsupported Git status in ticket worktree")
            if line[:2] == "??":
                changed.append(line[3:].strip())
        if not changed:
            raise QueueError("Passing ticket has no changes to queue")
        return sorted(set(changed)), sorted(set(deleted))

    def _candidate_digest(self, record: dict[str, Any], worktree: Path) -> str:
        digest = hashlib.sha256()
        digest.update(record["base_sha"].encode())
        for path in record["changed_paths"]:
            digest.update(path.encode())
            candidate = worktree / path
            if candidate.is_file() and not candidate.is_symlink():
                digest.update(hashlib.sha256(candidate.read_bytes()).digest())
            elif path in record["deleted_paths"]:
                blob = _run(["git", "rev-parse", f"main:{path}"], worktree)
                digest.update(blob.encode())
            else:
                raise QueueError("Candidate tree changed while preparing approval")
        return digest.hexdigest()

    def _deletion_request(self, record: dict[str, Any], worktree: Path) -> dict[str, Any]:
        request_id = hashlib.sha256(
            f"{record['id']}:{utc_now()}:{os.urandom(16).hex()}".encode()
        ).hexdigest()[:16]
        prior_blobs = {
            path: _run(["git", "rev-parse", f"main:{path}"], worktree)
            for path in record["deleted_paths"]
        }
        request = {
            "schema_version": 1,
            "request_id": request_id,
            "ticket_id": record["ticket_id"],
            "branch": record["branch"],
            "base_sha": record["base_sha"],
            "candidate_digest": self._candidate_digest(record, worktree),
            "deleted_paths": record["deleted_paths"],
            "prior_blobs": prior_blobs,
            "purpose": record["purpose"],
            "impact": record["impact"],
            "created_at": utc_now(),
        }
        manifest_source = json.dumps(request, sort_keys=True, separators=(",", ":"))
        request["manifest_digest"] = hashlib.sha256(manifest_source.encode()).hexdigest()
        _atomic_json(self.runtime / f"deletion-approval-request-{request_id}.json", request)
        _atomic_json(self.runtime / "deletion-approval-request.json", request)
        return request

    def _commit(self, record: dict[str, Any], worktree: Path) -> str:
        _run(["git", "add", "--all"], worktree)
        staged = subprocess.run(
            ["git", "diff", "--cached", "--quiet"],
            cwd=worktree,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=30,
            check=False,
        )
        if staged.returncode == 1:
            _run(
                ["git", "commit", "-m", f"{record['ticket_id']}: {record['purpose'][:60]}"],
                worktree,
            )
        elif staged.returncode != 0:
            raise QueueError("Could not determine whether the candidate needs a commit")
        commit_sha = _run(["git", "rev-parse", "HEAD"], worktree)
        if not HEX_SHA.fullmatch(commit_sha):
            raise QueueError("Created commit identity is invalid")
        return commit_sha

    def process_deletion_decisions(self) -> bool:
        changed = False
        with self._lock:
            state = self.read()
            for record in state["records"]:
                if record.get("state") != "deletion_pending":
                    continue
                deletion = record.get("deletion_request") or {}
                request_id = deletion.get("request_id")
                if not isinstance(request_id, str) or not REQUEST_ID.fullmatch(request_id):
                    continue
                decision_path = self.runtime / f"deletion-approval-decision-{request_id}.json"
                if not decision_path.exists():
                    continue
                try:
                    decision = json.loads(decision_path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    continue
                if set(decision) != {"request_id", "manifest_digest", "decision"}:
                    record.update({"state": "failed", "error": "Invalid deletion decision"})
                    self._stale_after(state, record)
                    changed = True
                    continue
                if (
                    decision["request_id"] != request_id
                    or decision["manifest_digest"] != deletion.get("manifest_digest")
                    or decision["decision"] not in {"approve", "reject"}
                ):
                    record.update({"state": "failed", "error": "Deletion approval mismatch"})
                    self._stale_after(state, record)
                    changed = True
                    continue
                if decision["decision"] == "reject":
                    record.update({"state": "rejected", "error": "File deletion rejected"})
                    deletion["state"] = "rejected"
                    self._stale_after(state, record)
                    changed = True
                    continue
                worktree = self._worktree(record)
                request_path = self.runtime / f"deletion-approval-request-{request_id}.json"
                try:
                    request = json.loads(request_path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    request = None
                if not self._request_matches(record, request):
                    record.update({"state": "failed", "error": "Deletion manifest changed after approval"})
                    self._stale_after(state, record)
                    changed = True
                    continue
                if self._candidate_digest(record, worktree) != request["candidate_digest"]:
                    record.update({"state": "failed", "error": "Candidate changed after deletion approval"})
                    self._stale_after(state, record)
                    changed = True
                    continue
                record["commit_sha"] = self._commit(record, worktree)
                record["state"] = "ready"
                record["updated_at"] = utc_now()
                deletion["state"] = "approved"
                changed = True
            if changed:
                state["updated_at"] = utc_now()
                _atomic_json(self.path, state)
        return changed

    @staticmethod
    def _request_matches(record: dict[str, Any], request: object) -> bool:
        if not isinstance(request, dict):
            return False
        manifest_digest = request.get("manifest_digest")
        unsigned = {key: value for key, value in request.items() if key != "manifest_digest"}
        computed = hashlib.sha256(
            json.dumps(unsigned, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        deletion = record.get("deletion_request") or {}
        return (
            isinstance(manifest_digest, str)
            and manifest_digest == computed == deletion.get("manifest_digest")
            and request.get("request_id") == deletion.get("request_id")
            and request.get("ticket_id") == record.get("ticket_id")
            and request.get("branch") == record.get("branch")
            and request.get("base_sha") == record.get("base_sha")
            and request.get("deleted_paths") == record.get("deleted_paths")
        )

    def approve_and_publish(self, record_id: str, commit_sha: str) -> None:
        if not REQUEST_ID.fullmatch(record_id) or not HEX_SHA.fullmatch(commit_sha):
            raise QueueError("Invalid publication approval")
        with self._lock:
            state = self.read()
            record = next((item for item in state["records"] if item.get("id") == record_id), None)
            if record is None or record.get("state") != "ready":
                raise QueueError("Ticket is not ready for publication")
            pending = [item for item in state["records"] if item.get("state") == "ready"]
            if not pending or pending[0].get("id") != record_id:
                raise QueueError("Queued tickets must be approved in dependency order")
            if record.get("commit_sha") != commit_sha:
                raise QueueError("Approval does not match the queued commit")
            record["state"] = "publishing"
            record["updated_at"] = utc_now()
            _atomic_json(self.path, state)
        self.event(
            f"Publishing {record['ticket_id']}",
            detail=f"Approval matched exact commit {commit_sha}.",
            ticket_id=record["ticket_id"],
        )
        try:
            self._publish(record)
        except (QueueError, OSError, subprocess.SubprocessError) as exc:
            self._record_failure(record_id, "Publication stopped safely", str(exc))
            return

    def _publish(self, record: dict[str, Any]) -> None:
        if _run(["git", "status", "--porcelain"], self.root):
            raise QueueError("Local main is not clean; publication did not start")
        worktree = self._worktree(record)
        if _run(["git", "status", "--porcelain"], worktree):
            raise QueueError("Queued worktree changed after validation")
        head = _run(["git", "rev-parse", "HEAD"], worktree)
        if head != record["commit_sha"]:
            raise QueueError("Queued branch head changed after approval")

        _run(["git", "push", "--set-upstream", "origin", record["branch"]], worktree, 180)
        try:
            pr_data = json.loads(_run([
                "gh", "pr", "view", record["branch"],
                "--json", "number,url,headRefOid,state",
            ], worktree))
        except (QueueError, json.JSONDecodeError):
            pr_url = _run([
                "gh", "pr", "create", "--base", "main", "--head", record["branch"],
                "--title", f"{record['ticket_id']}: {record['purpose'][:100]}",
                "--body", self._pr_body(record),
            ], worktree, 180)
            pr_data = json.loads(_run([
                "gh", "pr", "view", pr_url,
                "--json", "number,url,headRefOid,state",
            ], worktree))
        if pr_data.get("headRefOid") != record["commit_sha"]:
            raise QueueError("PR head does not match the approved commit")
        pr_number = pr_data.get("number")
        if not isinstance(pr_number, int):
            raise QueueError("GitHub returned no PR number")
        self._update_record(record["id"], pr_number=pr_number, pr_url=pr_data.get("url"))

        _run(
            ["gh", "pr", "checks", str(pr_number), "--required", "--watch", "--interval", "10"],
            worktree,
            PUBLISH_TIMEOUT_SECONDS,
        )
        review = json.loads(_run([
            "gh", "pr", "view", str(pr_number),
            "--json", "headRefOid,mergeable,mergeStateStatus,statusCheckRollup",
        ], worktree))
        if review.get("headRefOid") != record["commit_sha"]:
            raise QueueError("PR head changed while CI was running")
        checks = review.get("statusCheckRollup")
        if not isinstance(checks, list) or not checks:
            raise QueueError("No exact-head CI evidence was returned")
        if any(
            item.get("status") != "COMPLETED"
            or item.get("conclusion") not in SAFE_CONCLUSIONS
            for item in checks
        ):
            raise QueueError("One or more exact-head checks did not pass")
        if review.get("mergeable") != "MERGEABLE" or review.get("mergeStateStatus") != "CLEAN":
            raise QueueError("Protected merge requirements are not satisfied")

        _run([
            "gh", "pr", "merge", str(pr_number), "--squash", "--delete-branch=false",
            "--match-head-commit", record["commit_sha"],
        ], worktree, 180)
        merged = json.loads(_run([
            "gh", "pr", "view", str(pr_number), "--json", "state,mergeCommit",
        ], worktree))
        merge_sha = (merged.get("mergeCommit") or {}).get("oid")
        if merged.get("state") != "MERGED" or not isinstance(merge_sha, str):
            raise QueueError("GitHub did not confirm the protected merge")
        _run(["git", "pull", "--ff-only", "origin", "main"], self.root, 180)
        self._update_record(
            record["id"], state="published", merge_sha=merge_sha, error=None
        )
        self.event(
            f"{record['ticket_id']} merged into protected main",
            level="success",
            detail=f"PR #{pr_number} merged as {merge_sha}.",
            ticket_id=record["ticket_id"],
        )

    def _pr_body(self, record: dict[str, Any]) -> str:
        paths = "\n".join(f"- `{path}`" for path in record["changed_paths"])
        return (
            f"## Ticket\n\n{record['ticket_id']}\n\n"
            f"## Purpose\n\n{record['purpose']}\n\n"
            f"## Expected impact\n\n{record['impact']}\n\n"
            f"## Changed paths\n\n{paths}\n\n"
            "## Local gates\n\nDeterministic validation: PASS\n\n"
            f"Independent reviewer: {record.get('reviewer') or 'approved by configured policy'}\n"
        )

    def _worktree(self, record: dict[str, Any]) -> Path:
        name = record.get("worktree_name")
        if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9._-]+", name):
            raise QueueError("Queue worktree identity is invalid")
        path = (self.root.parent / f"{self.root.name}-worktrees" / name).resolve()
        if not path.is_dir():
            raise QueueError("Queue worktree is unavailable")
        return path

    def _update_record(self, record_id: str, **values: Any) -> None:
        def change(state: dict[str, Any]) -> None:
            record = next((item for item in state["records"] if item.get("id") == record_id), None)
            if record is None:
                raise QueueError("Queue record disappeared")
            record.update(values)
            record["updated_at"] = utc_now()
        self._update(change)

    def _record_failure(self, record_id: str, message: str, detail: str) -> None:
        try:
            state = self.read()
            record = next(item for item in state["records"] if item.get("id") == record_id)
            def fail(value: dict[str, Any]) -> None:
                current = next(item for item in value["records"] if item.get("id") == record_id)
                current.update({"state": "failed", "error": detail[:500], "updated_at": utc_now()})
                self._stale_after(value, current)
            self._update(fail)
            self.event(
                message,
                level="error",
                detail=detail,
                ticket_id=record.get("ticket_id"),
            )
        except (StopIteration, QueueError):
            self.event(message, level="error", detail=detail)

    @staticmethod
    def _stale_after(state: dict[str, Any], record: dict[str, Any]) -> None:
        position = record.get("dependency_index")
        if not isinstance(position, int):
            return
        for later in state["records"]:
            if (
                isinstance(later.get("dependency_index"), int)
                and later["dependency_index"] > position
                and later.get("state") not in {"published", "rejected", "failed"}
            ):
                later.update({
                    "state": "stale",
                    "error": "An earlier queued ticket did not publish",
                    "updated_at": utc_now(),
                })


def queue_path(root: Path) -> Path:
    return root / "agent" / "runtime" / "approval-queue.json"
