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
PR_HEAD_CONFIRM_ATTEMPTS = 8
PR_HEAD_CONFIRM_INTERVAL_SECONDS = 1
CI_REGISTRATION_ATTEMPTS = 60
CI_REGISTRATION_INTERVAL_SECONDS = 2
REQUIRED_CHECK_NAME = "repository-gates"
TERMINAL_QUEUE_STATES = {
    "published", "rejected", "stale", "dismissed", "superseded", "discarded",
}


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
            "depends_on_id", "depends_on_commit", "automation_authorized",
        }
        records = [
            {key: item.get(key) for key in allowed}
            for item in state["records"]
            if isinstance(item, dict)
            and item.get("state") not in {"dismissed", "superseded", "discarded"}
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
        return {
            "records": records,
            "batches": self._public_batches(state["records"], allowed),
            "activity": activity,
        }

    def _batch_chains(self, records: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
        ready = {
            item.get("id"): item for item in records
            if isinstance(item, dict) and item.get("state") == "ready"
        }
        children: dict[str, list[dict[str, Any]]] = {}
        for item in ready.values():
            parent_id = item.get("depends_on_id")
            parent = ready.get(parent_id)
            if parent is not None and item.get("depends_on_commit") == parent.get("commit_sha"):
                children.setdefault(str(parent_id), []).append(item)

        child_ids = {
            str(item.get("id")) for group in children.values() for item in group
        }
        chains: list[list[dict[str, Any]]] = []
        used: set[str] = set()
        for item in sorted(
            ready.values(), key=lambda value: int(value.get("dependency_index") or 0)
        ):
            item_id = str(item.get("id"))
            if item_id in child_ids or item_id in used:
                continue
            chain = [item]
            while True:
                next_items = children.get(str(chain[-1].get("id")), [])
                if len(next_items) != 1:
                    break
                candidate = next_items[0]
                if int(candidate.get("dependency_index") or 0) <= int(
                    chain[-1].get("dependency_index") or 0
                ):
                    break
                chain.append(candidate)
            if len(chain) > 1:
                chains.append(chain)
                used.update(str(member.get("id")) for member in chain)
        return chains

    def _public_batches(
        self,
        records: list[dict[str, Any]],
        allowed: set[str],
    ) -> list[dict[str, Any]]:
        batches: list[dict[str, Any]] = []
        for chain in self._batch_chains(records):
            identity = ":".join(
                f"{item.get('id')}:{item.get('commit_sha')}" for item in chain
            )
            batch_id = hashlib.sha256(f"batch:{identity}".encode()).hexdigest()[:16]
            members = [{key: item.get(key) for key in allowed} for item in chain]
            batches.append({
                "id": batch_id,
                "state": "ready",
                "ticket_id": f"Ordered batch · {len(chain)} tickets",
                "purpose": "Publish a verified cumulative dependency chain",
                "impact": "Imports the listed tickets together through one exact-head pull request.",
                "dependency_index": chain[0].get("dependency_index"),
                "changed_paths": sorted({
                    path for item in chain for path in item.get("changed_paths", [])
                    if isinstance(path, str)
                }),
                "deleted_paths": sorted({
                    path for item in chain for path in item.get("deleted_paths", [])
                    if isinstance(path, str)
                }),
                "commit_sha": chain[-1].get("commit_sha"),
                "branch": chain[-1].get("branch"),
                "members": members,
                "automation_authorized": all(
                    item.get("automation_authorized") is True for item in chain
                ),
            })
        return batches

    def add_passed_ticket(
        self,
        result: dict[str, Any],
        ticket: dict[str, Any],
        *,
        summary: str,
        impact: str,
        automation_authorization_id: str | None = None,
    ) -> dict[str, Any]:
        if (
            automation_authorization_id is not None
            and not re.fullmatch(r"[0-9a-f]{32}", automation_authorization_id)
        ):
            raise QueueError("Invalid automation publication authorization")
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
        queued_records = self.read()["records"]
        queued_ids = {item.get("ticket_id") for item in queued_records}
        if ticket.get("task_id") in queued_ids:
            raise QueueError("Ticket is already queued")
        if any(
            item.get("branch") == branch
            and item.get("state") not in TERMINAL_QUEUE_STATES | {"failed"}
            for item in queued_records
        ):
            raise QueueError("This branch is already owned by an active approval-queue ticket")

        queue_state = self.read()
        record_id = hashlib.sha256(
            f"{ticket['task_id']}:{branch}:{base_sha}".encode()
        ).hexdigest()[:16]
        depends_on_id = None
        depends_on_commit = None
        for earlier in reversed(queue_state["records"]):
            earlier_commit = earlier.get("commit_sha")
            if (
                earlier.get("state") == "ready"
                and isinstance(earlier_commit, str)
                and HEX_SHA.fullmatch(earlier_commit)
                and self._is_ancestor(earlier_commit, "HEAD", worktree)
            ):
                depends_on_id = earlier.get("id")
                depends_on_commit = earlier_commit
                break
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
            "depends_on_id": depends_on_id,
            "depends_on_commit": depends_on_commit,
            "automation_authorized": bool(automation_authorization_id),
            "automation_authorization_id": automation_authorization_id,
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

    def approve_and_publish(self, record_id: str, commit_sha: str) -> dict[str, Any]:
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
        return self.record(record_id)

    def approve_and_publish_batch(self, batch_id: str) -> list[dict[str, Any]]:
        if not REQUEST_ID.fullmatch(batch_id):
            raise QueueError("Invalid batch approval")
        with self._lock:
            state = self.read()
            allowed = {
                "id", "ticket_id", "commit_sha", "branch", "dependency_index",
                "depends_on_id", "depends_on_commit", "state",
            }
            batch = next(
                (
                    item for item in self._public_batches(state["records"], allowed)
                    if item.get("id") == batch_id
                ),
                None,
            )
            if batch is None:
                raise QueueError("Publication batch is no longer valid")
            member_ids = [item.get("id") for item in batch["members"]]
            members = [
                next(item for item in state["records"] if item.get("id") == member_id)
                for member_id in member_ids
            ]
            ready = [item for item in state["records"] if item.get("state") == "ready"]
            if not ready or ready[0].get("id") != members[0].get("id"):
                raise QueueError("Publication batch is not first in dependency order")
            final = members[-1]
            final_worktree = self._worktree(final)
            for previous, current in zip(members, members[1:]):
                if (
                    current.get("depends_on_id") != previous.get("id")
                    or current.get("depends_on_commit") != previous.get("commit_sha")
                    or not self._is_ancestor(
                        str(previous.get("commit_sha")),
                        str(current.get("commit_sha")),
                        final_worktree,
                    )
                ):
                    raise QueueError("Publication batch dependency identity changed")
            for member in members:
                member.update({"state": "publishing", "updated_at": utc_now()})
            _atomic_json(self.path, state)

        self.event(
            f"Publishing ordered batch of {len(members)} tickets",
            detail=(
                "Batch approval matched every queue ID and exact commit. The final cumulative "
                f"head is {final.get('commit_sha')}."
            ),
            ticket_id=str(final.get("ticket_id") or ""),
        )
        publication_record = dict(final)
        publication_record.update({
            "purpose": f"Ordered batch of {len(members)} dependent tickets",
            "impact": "\n".join(
                f"{index}. {member.get('ticket_id')}: {member.get('impact') or member.get('purpose')}"
                for index, member in enumerate(members, start=1)
            )[:1200],
            "changed_paths": sorted({
                path for member in members for path in member.get("changed_paths", [])
                if isinstance(path, str)
            }),
            "batch_members": [
                {
                    "ticket_id": member.get("ticket_id"),
                    "commit_sha": member.get("commit_sha"),
                    "purpose": member.get("purpose"),
                }
                for member in members
            ],
        })
        try:
            self._publish(publication_record)
        except (QueueError, OSError, subprocess.SubprocessError) as exc:
            def restore(value: dict[str, Any]) -> None:
                for member in members[:-1]:
                    current = next(
                        item for item in value["records"]
                        if item.get("id") == member.get("id")
                    )
                    current.update({"state": "ready", "updated_at": utc_now()})
            self._update(restore)
            self._record_failure(
                str(final.get("id")), "Batch publication stopped safely", str(exc)
            )
            return [self.record(str(item.get("id"))) for item in members]

        published_final = self.record(str(final.get("id")))
        def complete(value: dict[str, Any]) -> None:
            for member in members[:-1]:
                current = next(
                    item for item in value["records"]
                    if item.get("id") == member.get("id")
                )
                current.update({
                    "state": "published",
                    "pr_number": published_final.get("pr_number"),
                    "pr_url": published_final.get("pr_url"),
                    "merge_sha": published_final.get("merge_sha"),
                    "error": None,
                    "updated_at": utc_now(),
                })
        self._update(complete)
        self.event(
            f"Ordered batch of {len(members)} tickets merged into protected main",
            level="success",
            detail=(
                f"PR #{published_final.get('pr_number')} imported the verified cumulative chain."
            ),
            ticket_id=str(final.get("ticket_id") or ""),
        )
        return [self.record(str(item.get("id"))) for item in members]

    def record(self, record_id: str) -> dict[str, Any]:
        record = next(
            (item for item in self.read()["records"] if item.get("id") == record_id),
            None,
        )
        if record is None:
            raise QueueError("Queue record disappeared")
        return dict(record)

    def autonomous_publication_target(
        self,
        record_id: str,
        authorization_id: str,
    ) -> dict[str, str] | None:
        if not re.fullmatch(r"[0-9a-f]{32}", authorization_id):
            return None
        stored = self.read()["records"]
        public = self.public_state()
        ready = [item for item in public["records"] if item.get("state") == "ready"]
        stored_by_id = {item.get("id"): item for item in stored}
        if (
            not ready
            or stored_by_id.get(ready[0].get("id"), {}).get("automation_authorization_id")
            != authorization_id
        ):
            return None
        for batch in public["batches"]:
            members = batch.get("members") or []
            if (
                members
                and members[0].get("id") == ready[0].get("id")
                and members[-1].get("id") == record_id
                and all(
                    stored_by_id.get(item.get("id"), {}).get("automation_authorization_id")
                    == authorization_id
                    for item in members
                )
            ):
                return {"kind": "batch", "id": str(batch["id"])}
        if ready[0].get("id") == record_id:
            return {
                "kind": "record", "id": str(record_id),
                "commit_sha": str(ready[0].get("commit_sha")),
            }
        return None

    def failed_record(self, record_id: str, commit_sha: str) -> dict[str, Any]:
        """Return a safe snapshot only when an exact recoverable queue item is selected."""

        if not REQUEST_ID.fullmatch(record_id) or not HEX_SHA.fullmatch(commit_sha):
            raise QueueError("Invalid failed-ticket selection")
        record = next(
            (item for item in self.read()["records"] if item.get("id") == record_id),
            None,
        )
        if (
            record is None
            or record.get("state") not in {"failed", "stale"}
            or record.get("commit_sha") != commit_sha
        ):
            raise QueueError("Failed ticket no longer matches the selected commit")
        return {
            key: record.get(key)
            for key in (
                "id", "ticket_id", "purpose", "impact", "branch", "commit_sha",
                "pr_number", "pr_url",
            )
        }

    def discard_local_remnants(self, record_id: str, commit_sha: str) -> None:
        """Delete only an exact stale ticket's clean local worktree and branch."""

        selected = self.failed_record(record_id, commit_sha)
        state = self.read()
        record = next(item for item in state["records"] if item.get("id") == record_id)
        branch = selected.get("branch")
        if not isinstance(branch, str) or not BRANCH.fullmatch(branch):
            raise QueueError("Stale ticket branch identity is invalid")
        if record.get("pr_number") or record.get("pr_url"):
            raise QueueError("A ticket with a pull request cannot be deleted from the dashboard")
        if any(
            item.get("id") != record_id
            and item.get("branch") == branch
            and item.get("state") not in TERMINAL_QUEUE_STATES | {"failed"}
            for item in state["records"]
        ):
            raise QueueError("A newer queue entry still owns this branch")
        dependent_ids = {record_id}
        while True:
            discovered = {
                item.get("id") for item in state["records"]
                if item.get("depends_on_id") in dependent_ids
            }
            expanded = dependent_ids | {item for item in discovered if isinstance(item, str)}
            if expanded == dependent_ids:
                break
            dependent_ids = expanded
        if any(
            item.get("id") in dependent_ids - {record_id}
            and item.get("state") not in {
                "discarded", "dismissed", "superseded", "published", "rejected",
            }
            for item in state["records"]
        ):
            raise QueueError("A later queued ticket still depends on this code")
        if self._ref_sha(f"refs/remotes/origin/{branch}") is not None:
            raise QueueError("A remote branch exists; local dashboard deletion is refused")

        worktree_name = record.get("worktree_name")
        if not isinstance(worktree_name, str) or not re.fullmatch(r"[A-Za-z0-9._-]+", worktree_name):
            raise QueueError("Queue worktree identity is invalid")
        worktree = (self.root.parent / f"{self.root.name}-worktrees" / worktree_name).resolve()
        expected_parent = (self.root.parent / f"{self.root.name}-worktrees").resolve()
        try:
            worktree.relative_to(expected_parent)
        except ValueError as exc:
            raise QueueError("Queue worktree is outside the managed root") from exc
        if worktree.exists():
            if _run(["git", "branch", "--show-current"], worktree) != branch:
                raise QueueError("Managed worktree branch no longer matches the queue")
            if _run(["git", "rev-parse", "HEAD"], worktree) != commit_sha:
                raise QueueError("Managed worktree head no longer matches the queue")
            if _run(["git", "status", "--porcelain"], worktree):
                raise QueueError("Managed worktree contains uncommitted remnants; recode it instead")
            _run(["git", "worktree", "remove", str(worktree)], self.root, 120)

        local_sha = self._ref_sha(f"refs/heads/{branch}")
        if local_sha is not None and local_sha != commit_sha:
            raise QueueError("Local branch head no longer matches the selected commit")
        if local_sha == commit_sha:
            _run(["git", "branch", "-D", branch], self.root)

        def discard(value: dict[str, Any]) -> None:
            current = next(item for item in value["records"] if item.get("id") == record_id)
            current.update({"state": "discarded", "updated_at": utc_now()})
        self._update(discard)
        self.event(
            f"{selected['ticket_id']} local remnants deleted",
            level="warning",
            detail=(
                f"Deleted only managed worktree {worktree_name} and exact local branch {branch}; "
                "the non-secret queue audit record remains."
            ),
            ticket_id=str(selected.get("ticket_id") or ""),
        )

    def _ref_sha(self, ref: str) -> str | None:
        completed = subprocess.run(
            ["git", "show-ref", "--verify", "--hash", ref],
            cwd=self.root, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            text=True, timeout=30, check=False,
        )
        if completed.returncode in {1, 128} and not completed.stdout.strip():
            return None
        if completed.returncode != 0 or not HEX_SHA.fullmatch(completed.stdout.strip()):
            raise QueueError("Git reference inventory failed")
        return completed.stdout.strip()

    @staticmethod
    def _is_ancestor(ancestor: str, descendant: str, cwd: Path) -> bool:
        completed = subprocess.run(
            ["git", "merge-base", "--is-ancestor", ancestor, descendant],
            cwd=cwd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            timeout=30, check=False,
        )
        if completed.returncode not in {0, 1}:
            raise QueueError("Git dependency verification failed")
        return completed.returncode == 0

    def dismiss_failed(
        self,
        record_id: str,
        commit_sha: str,
        *,
        superseded_by: str | None = None,
    ) -> None:
        """Hide a failed queue record without deleting repository or audit evidence."""

        selected = self.failed_record(record_id, commit_sha)

        def dismiss(state: dict[str, Any]) -> None:
            record = next(item for item in state["records"] if item.get("id") == record_id)
            record.update({
                "state": "superseded" if superseded_by else "dismissed",
                "updated_at": utc_now(),
                "superseded_by": superseded_by,
            })

        self._update(dismiss)
        self.event(
            (
                f"{selected['ticket_id']} was superseded by {superseded_by}"
                if superseded_by
                else f"{selected['ticket_id']} was removed from the approval queue"
            ),
            level="info",
            detail=(
                "The failed queue card was removed. Its Git branch, worktree, commits, "
                "pull request, files, and audit evidence were preserved."
            ),
            ticket_id=str(selected.get("ticket_id") or ""),
        )

    def _publish(self, record: dict[str, Any]) -> None:
        if _run(["git", "status", "--porcelain"], self.root):
            raise QueueError("Local main is not clean; publication did not start")
        worktree = self._worktree(record)
        if _run(["git", "status", "--porcelain"], worktree):
            raise QueueError("Queued worktree changed after validation")
        head = _run(["git", "rev-parse", "HEAD"], worktree)
        if head != record["commit_sha"]:
            raise QueueError("Queued branch head changed after approval")
        try:
            _run(["git", "merge-base", "--is-ancestor", "main", "HEAD"], worktree)
        except QueueError as exc:
            raise QueueError(
                "Approved ticket is behind current main; use Recode with AI to "
                "reconcile main and rerun every gate"
            ) from exc

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
        pr_data = self._wait_for_pr_head(
            str(pr_data.get("url") or record["branch"]),
            record["commit_sha"],
            worktree,
            initial=pr_data,
        )
        pr_number = pr_data.get("number")
        if not isinstance(pr_number, int):
            raise QueueError("GitHub returned no PR number")
        self._update_record(record["id"], pr_number=pr_number, pr_url=pr_data.get("url"))

        self._wait_for_ci_registration(pr_number, record["commit_sha"], worktree)
        try:
            _run(
                ["gh", "pr", "checks", str(pr_number), "--required", "--watch", "--interval", "10"],
                worktree,
                PUBLISH_TIMEOUT_SECONDS,
            )
        except QueueError as exc:
            raise QueueError("Required exact-head CI did not pass") from exc
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
        if review.get("mergeStateStatus") == "BEHIND":
            raise QueueError(
                "Pull request is behind current main; use Recode with AI to "
                "reconcile main and rerun every gate"
            )
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

    def _wait_for_pr_head(
        self,
        locator: str,
        expected_sha: str,
        worktree: Path,
        *,
        initial: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Bound GitHub's brief post-push read-after-write propagation window."""

        latest = initial
        for attempt in range(PR_HEAD_CONFIRM_ATTEMPTS):
            if latest is None:
                try:
                    latest = json.loads(_run([
                        "gh", "pr", "view", locator,
                        "--json", "number,url,headRefOid,state",
                    ], worktree))
                except json.JSONDecodeError as exc:
                    raise QueueError("GitHub returned malformed PR identity") from exc
            if latest.get("headRefOid") == expected_sha:
                return latest
            if attempt + 1 < PR_HEAD_CONFIRM_ATTEMPTS:
                threading.Event().wait(PR_HEAD_CONFIRM_INTERVAL_SECONDS)
                latest = None
        raise QueueError("PR head did not converge to the approved commit after push")

    def _wait_for_ci_registration(
        self,
        pr_number: int,
        expected_sha: str,
        worktree: Path,
    ) -> list[dict[str, Any]]:
        """Wait until GitHub attaches the required check to the exact PR head."""

        for attempt in range(CI_REGISTRATION_ATTEMPTS):
            try:
                value = json.loads(_run([
                    "gh", "pr", "view", str(pr_number),
                    "--json", "headRefOid,statusCheckRollup",
                ], worktree))
            except (QueueError, json.JSONDecodeError):
                value = None
            if isinstance(value, dict):
                if value.get("headRefOid") != expected_sha:
                    raise QueueError("PR head changed before required CI registered")
                checks = value.get("statusCheckRollup")
                if isinstance(checks, list) and any(
                    isinstance(item, dict) and item.get("name") == REQUIRED_CHECK_NAME
                    for item in checks
                ):
                    return checks
            if attempt + 1 < CI_REGISTRATION_ATTEMPTS:
                threading.Event().wait(CI_REGISTRATION_INTERVAL_SECONDS)
        raise QueueError("Required exact-head CI did not register within two minutes")

    def _pr_body(self, record: dict[str, Any]) -> str:
        paths = "\n".join(f"- `{path}`" for path in record["changed_paths"])
        batch_members = record.get("batch_members")
        batch = ""
        if isinstance(batch_members, list) and batch_members:
            ordered = "\n".join(
                f"{index}. `{item.get('ticket_id')}` at `{item.get('commit_sha')}` — "
                f"{item.get('purpose')}"
                for index, item in enumerate(batch_members, start=1)
                if isinstance(item, dict)
            )
            batch = f"## Ordered batch\n\n{ordered}\n\n"
        return (
            f"## Ticket\n\n{record['ticket_id']}\n\n"
            f"## Purpose\n\n{record['purpose']}\n\n"
            f"## Expected impact\n\n{record['impact']}\n\n"
            f"{batch}"
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
