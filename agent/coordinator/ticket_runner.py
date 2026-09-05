#!/usr/bin/env python3

from __future__ import annotations

import argparse
import datetime as dt
import fnmatch
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

import coordinator as core
import reference_package as reference_pkg
import recovery_policy
from runtime_status import RuntimeStatus, runtime_status_path


IMPLEMENTER_TIMEOUT = 240
TESTER_TIMEOUT = 180
PRIMARY_REVIEWER_TIMEOUT = 75
INTERMEDIATE_REVIEWER_TIMEOUT = 90
FALLBACK_REVIEWER_TIMEOUT = 180
RECOVERY_PLANNER_TIMEOUT = 300
TERRA_IMPLEMENTER_TIMEOUT = 600

VALID_WORKERS = {"implementer", "fast-fix"}
VALID_PROFILES = {"static-text", "wesnoth-addon-static"}
ACTIVE_STATUS: RuntimeStatus | None = None
RECOVERY_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["action", "summary", "corrective_action"],
    "properties": {
        "action": {"type": "string", "enum": ["repair", "stop"]},
        "summary": {"type": "string", "minLength": 1, "maxLength": 500},
        "corrective_action": {"type": "string", "minLength": 1, "maxLength": 1200},
    },
}

PROTECTED_EXACT = {
    ".gitignore",
    "opencode.json",
    "opencode.jsonc",
    *reference_pkg.CONTROLLED_REFERENCE_PATHS,
}

PROTECTED_PREFIXES = (
    ".git/",
    ".opencode/",
    "agent/coordinator/",
)

TEXT_EXTENSIONS = {
    ".cfg",
    ".lua",
    ".md",
    ".txt",
    ".json",
    ".py",
    ".yaml",
    ".yml",
    ".toml",
    ".ini",
}


def load_reference_package(root: Path) -> dict:
    """Validate and fingerprint the controlled reference package."""

    return reference_pkg.load_reference_package(root)


def load_governance_references(root: Path) -> dict:
    """Backward-compatible canonical reference metadata accessor."""

    return load_reference_package(root)["canonical_references"]


def build_governance_prompt(package: dict) -> str:
    """Build mandatory controlled-reference instructions for every LLM."""

    return reference_pkg.build_governance_prompt(package)


def invoke_agent(
    *,
    opencode: str,
    worktree: Path,
    agent: str,
    prompt: str,
    log_file: Path,
    timeout: int,
) -> tuple[int, str]:
    command = [
        opencode,
        "run",
        "--auto",
        "--agent",
        agent,
        "--format",
        "json",
        "--dir",
        str(worktree),
        prompt,
    ]

    rc, output = core.run_process(
        command,
        cwd=worktree,
        timeout=timeout,
        env=dict(os.environ),
    )

    log_file.write_text(output)
    return rc, output


def invoke_terra_implementer(
    *, worktree: Path, prompt: str, log_file: Path
) -> tuple[int, str]:
    """Run the single sandboxed Terra Medium Implementer fallback."""

    executable = shutil.which("codex") or shutil.which("codex.exe")
    if not executable:
        return 127, "Codex Terra fallback is unavailable."
    windows_binary = executable.lower().endswith(".exe")
    command = [
        executable, "exec", "-C", _codex_path(worktree, windows_binary),
        "-s", "workspace-write", "-m", "gpt-5.6-terra",
        "-c", 'model_reasoning_effort="medium"',
        "-c", 'web_search="disabled"', "--ephemeral", "--ignore-user-config",
        "--color", "never", "-",
    ]
    environment = {
        key: value for key, value in core.make_test_env().items()
        if not re.search(
            r"(?:API[_-]?KEY|TOKEN|SECRET|PASSWORD|CREDENTIAL|PRIVATE[_-]?KEY)",
            key, re.IGNORECASE,
        )
    }
    try:
        completed = subprocess.run(
            command, cwd=worktree, env=environment, input=prompt, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            timeout=TERRA_IMPLEMENTER_TIMEOUT, check=False,
        )
        output = completed.stdout or ""
        log_file.write_text(output, encoding="utf-8")
        return completed.returncode, output
    except subprocess.TimeoutExpired as exc:
        output = str(exc.stdout or "") + "\n[COORDINATOR] TERRA FALLBACK TIMEOUT\n"
        log_file.write_text(output, encoding="utf-8")
        return 124, output


def load_ticket(path: Path) -> dict:
    try:
        ticket = json.loads(path.read_text())
    except Exception as exc:
        raise SystemExit(f"ERROR: could not read ticket: {exc}")

    if not isinstance(ticket, dict):
        raise SystemExit("ERROR: ticket must contain a JSON object.")

    allowed_keys = {
        "task_id",
        "worker",
        "objective",
        "allowed_paths",
        "validation_profile",
        "validation_root",
        "resume_branch",
        "resume_pr_number",
        "resume_pr_head_sha",
        "replace_pr_number",
        "replace_pr_head_sha",
        "replace_pr_branch",
    }

    unknown = sorted(set(ticket) - allowed_keys)
    if unknown:
        raise SystemExit(
            "ERROR: unsupported ticket fields: " + ", ".join(unknown)
        )

    task_id = ticket.get("task_id")
    if not isinstance(task_id, str) or not re.fullmatch(
        r"[A-Z0-9][A-Z0-9_-]{2,63}",
        task_id,
    ):
        raise SystemExit(
            "ERROR: task_id must contain 3-64 uppercase letters, numbers, "
            "underscores, or hyphens."
        )

    worker = ticket.get("worker")
    if worker not in VALID_WORKERS:
        raise SystemExit(
            f"ERROR: worker must be one of {sorted(VALID_WORKERS)}."
        )

    objective = ticket.get("objective")
    if not isinstance(objective, str) or not objective.strip():
        raise SystemExit("ERROR: objective must be a non-empty string.")

    allowed_paths = ticket.get("allowed_paths")
    if (
        not isinstance(allowed_paths, list)
        or not allowed_paths
        or not all(isinstance(x, str) and x for x in allowed_paths)
    ):
        raise SystemExit(
            "ERROR: allowed_paths must be a non-empty list of strings."
        )

    for pattern in allowed_paths:
        if pattern.startswith("/") or ".." in Path(pattern).parts:
            raise SystemExit(
                f"ERROR: unsafe allowed_paths entry: {pattern!r}"
            )

    profile = ticket.get("validation_profile")
    if profile not in VALID_PROFILES:
        raise SystemExit(
            f"ERROR: validation_profile must be one of "
            f"{sorted(VALID_PROFILES)}."
        )

    validation_root = ticket.get("validation_root")

    if profile == "wesnoth-addon-static":
        if (
            not isinstance(validation_root, str)
            or not validation_root
            or validation_root.startswith("/")
            or ".." in Path(validation_root).parts
        ):
            raise SystemExit(
                "ERROR: wesnoth-addon-static requires a safe "
                "validation_root."
            )

    resume_branch = ticket.get("resume_branch")
    if resume_branch is not None and (
        not isinstance(resume_branch, str)
        or not re.fullmatch(r"agent/[a-z0-9][a-z0-9._/-]{0,180}", resume_branch)
    ):
        raise SystemExit("ERROR: resume_branch must be null or a safe agent branch.")

    resume_pr_number = ticket.get("resume_pr_number")
    resume_pr_head_sha = ticket.get("resume_pr_head_sha")
    if (resume_pr_number is None) != (resume_pr_head_sha is None):
        raise SystemExit("ERROR: resume PR number and head SHA must be supplied together.")
    if resume_pr_number is not None and (
        not isinstance(resume_pr_number, int) or resume_pr_number < 1
        or not isinstance(resume_pr_head_sha, str)
        or not re.fullmatch(r"[0-9a-f]{40}", resume_pr_head_sha)
        or resume_branch is None
    ):
        raise SystemExit("ERROR: resume PR identity is invalid or has no resume branch.")

    replacement = (
        ticket.get("replace_pr_number"),
        ticket.get("replace_pr_head_sha"),
        ticket.get("replace_pr_branch"),
    )
    if any(value is not None for value in replacement):
        number, head_sha, branch = replacement
        if (
            not isinstance(number, int) or number < 1
            or not isinstance(head_sha, str) or not re.fullmatch(r"[0-9a-f]{40}", head_sha)
            or not isinstance(branch, str)
            or not re.fullmatch(r"agent/[a-z0-9][a-z0-9._/-]{0,180}", branch)
            or resume_branch is not None or resume_pr_number is not None
        ):
            raise SystemExit("ERROR: replacement PR identity is invalid.")

    return ticket


def is_protected(path: str) -> bool:
    path = path.replace("\\", "/")

    if path in PROTECTED_EXACT or path == ".git":
        return True

    return any(path.startswith(prefix) for prefix in PROTECTED_PREFIXES)


def path_allowed(path: str, patterns: list[str]) -> bool:
    path = path.replace("\\", "/")
    return any(fnmatch.fnmatchcase(path, pattern) for pattern in patterns)


def _read_git_changes_against(
    worktree: Path,
    base: str,
) -> tuple[list[str], list[str]]:
    rc, candidate_output = core.git(
        worktree,
        "diff",
        "--name-status",
        "-M",
        base,
    )
    core.require_success(rc, candidate_output, "Read candidate changes from main")

    rc, output = core.git(
        worktree,
        "status",
        "--porcelain=v1",
        "--untracked-files=all",
    )
    core.require_success(rc, output, "Read implementation Git status")

    entries = [f"CANDIDATE {line}" for line in candidate_output.splitlines() if line]
    paths = []

    for line in candidate_output.splitlines():
        fields = line.split("\t")
        if not fields:
            continue
        status_code = fields[0]
        if status_code.startswith(("R", "C")) or len(fields) != 2:
            paths.append("<RENAME_OR_COPY_NOT_SUPPORTED>")
            continue
        paths.append(fields[1])

    for line in output.splitlines():
        if not line:
            continue

        entries.append(line)

        if len(line) < 4:
            paths.append("<UNPARSEABLE>")
            continue

        status_code = line[:2]
        path = line[3:].strip()

        # Renames and copies require special path semantics. Reject them in
        # v1 rather than accidentally approving the wrong side.
        if (
            " -> " in path
            or "R" in status_code
            or "C" in status_code
        ):
            paths.append("<RENAME_OR_COPY_NOT_SUPPORTED>")
            continue

        if status_code == "??" or path not in paths:
            paths.append(path)

    return entries, sorted(set(paths))


def read_git_changes(worktree: Path) -> tuple[list[str], list[str]]:
    return _read_git_changes_against(worktree, "main")


def read_resume_changes(worktree: Path) -> tuple[list[str], list[str]]:
    """Read branch-owned and dirty remnants without attributing newer main changes."""

    rc, merge_base = core.git(worktree, "merge-base", "main", "HEAD")
    core.require_success(rc, merge_base, "Find interrupted ticket merge base")
    base = merge_base.strip()
    if not re.fullmatch(r"[0-9a-f]{40}", base):
        raise SystemExit("ERROR: interrupted ticket merge base was malformed.")
    return _read_git_changes_against(worktree, base)


def resolve_resume_worktree(root: Path, branch: str) -> Path:
    """Resolve a trusted existing ticket worktree without accepting a path from an LLM."""

    rc, output = core.git(root, "worktree", "list", "--porcelain")
    core.require_success(rc, output, "Inventory resumable worktrees")
    managed_root = (root.parent / f"{root.name}-worktrees").resolve()
    current_path: Path | None = None
    for line in output.splitlines() + [""]:
        if line.startswith("worktree "):
            current_path = Path(line.removeprefix("worktree ")).resolve()
        elif line == f"branch refs/heads/{branch}" and current_path is not None:
            try:
                current_path.relative_to(managed_root)
            except ValueError as exc:
                raise SystemExit("ERROR: resume worktree is outside the managed root.") from exc
            rc, active = core.git(current_path, "branch", "--show-current")
            core.require_success(rc, active, "Verify resumed ticket branch")
            if active.strip() != branch:
                raise SystemExit("ERROR: resume worktree branch does not match.")
            return current_path
    raise SystemExit("ERROR: requested resume branch has no managed worktree.")


def prepare_open_pr_resume(root: Path, worktree: Path, ticket: dict) -> bool:
    """Verify an exact open PR and append current main without rewriting history."""

    number = ticket.get("resume_pr_number")
    expected_head = ticket.get("resume_pr_head_sha")
    if number is None:
        return False
    rc, status = core.git(worktree, "status", "--porcelain=v1", "--untracked-files=all")
    core.require_success(rc, status, "Verify open pull-request worktree state")
    if status.strip():
        raise SystemExit("ERROR: open pull-request worktree is not clean.")
    rc, local_head = core.git(worktree, "rev-parse", "HEAD")
    core.require_success(rc, local_head, "Verify open pull-request local head")
    local_head = local_head.strip()
    rc, _ = core.git(worktree, "merge-base", "--is-ancestor", expected_head, local_head)
    if rc != 0:
        raise SystemExit("ERROR: local pull-request history does not descend from its remote head.")
    completed = subprocess.run(
        [
            "gh", "pr", "view", str(number), "--json",
            "number,state,headRefName,headRefOid,baseRefName,isCrossRepository",
        ],
        cwd=root,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        timeout=60,
        check=False,
    )
    try:
        current = json.loads(completed.stdout) if completed.returncode == 0 else {}
    except json.JSONDecodeError as exc:
        raise SystemExit("ERROR: open pull-request identity could not be verified.") from exc
    if current != {
        "number": number,
        "state": "OPEN",
        "headRefName": ticket["resume_branch"],
        "headRefOid": expected_head,
        "baseRefName": "main",
        "isCrossRepository": False,
    }:
        raise SystemExit("ERROR: open pull-request identity changed before resumption.")
    rc, _ = core.git(worktree, "merge-base", "--is-ancestor", "main", "HEAD")
    if rc == 0:
        return False
    if rc != 1:
        raise SystemExit("ERROR: open pull-request ancestry could not be verified.")
    rc, output = core.git(worktree, "merge", "--no-edit", "--no-ff", "main", timeout=120)
    if rc != 0:
        core.git(worktree, "merge", "--abort", timeout=60)
        raise SystemExit(
            "ERROR: open pull request cannot be reconciled with main without conflicts. "
            "Its branch was restored unchanged."
        )
    return True


def prepare_local_resume(root: Path, worktree: Path) -> bool:
    """Append current main to an unpublished remnant without losing local work."""

    rc, _ = core.git(worktree, "merge-base", "--is-ancestor", "main", "HEAD")
    if rc == 0:
        return False
    if rc != 1:
        raise SystemExit("ERROR: local remnant ancestry could not be verified.")

    rc, status = core.git(
        worktree, "status", "--porcelain=v1", "--untracked-files=all"
    )
    core.require_success(rc, status, "Verify local remnant worktree state")
    if status.strip():
        raise SystemExit(
            "ERROR: local remnant has uncommitted changes and does not contain current "
            "main; automatic reconciliation was refused to preserve the remnants."
        )

    rc, output = core.git(worktree, "merge", "--no-edit", "main", timeout=120)
    if rc != 0:
        core.git(worktree, "merge", "--abort", timeout=60)
        raise SystemExit(
            "ERROR: local remnant cannot be reconciled with main without conflicts. "
            "Its branch was restored unchanged."
        )
    return True


def validate_scope(
    changed_paths: list[str],
    allowed_paths: list[str],
) -> dict:
    violations = []

    for path in changed_paths:
        if path.startswith("<"):
            violations.append(path)
            continue

        if is_protected(path):
            violations.append(f"{path}: protected")
            continue

        if not path_allowed(path, allowed_paths):
            violations.append(f"{path}: outside allowed_paths")

    return {
        "changed_paths": changed_paths,
        "allowed_paths": allowed_paths,
        "violations": violations,
        "pass": bool(changed_paths) and not violations,
    }


def validate_resume_scope(
    changed_paths: list[str],
    allowed_paths: list[str],
) -> dict:
    """Validate pre-existing remnants; an exact-contract clean worktree is resumable."""

    result = validate_scope(changed_paths, allowed_paths)
    result["state"] = "changed" if changed_paths else "clean"
    result["pass"] = not result["violations"]
    return result


def validate_static_files(
    worktree: Path,
    changed_paths: list[str],
) -> dict:
    checks = []
    passed = True

    rc, output = core.git(worktree, "diff", "--check", "main")
    diff_check = {
        "name": "git_diff_check",
        "pass": rc == 0,
        "output": output.strip(),
    }
    checks.append(diff_check)

    if rc != 0:
        passed = False

    for rel in changed_paths:
        if rel.startswith("<"):
            continue

        path = worktree / rel

        # Deleted files are already represented correctly by Git status.
        if not path.exists():
            continue

        if path.is_symlink():
            checks.append({
                "name": f"no_symlink:{rel}",
                "pass": False,
            })
            passed = False
            continue

        if path.is_dir():
            continue

        size = path.stat().st_size
        size_ok = size <= 2 * 1024 * 1024

        checks.append({
            "name": f"size:{rel}",
            "pass": size_ok,
            "bytes": size,
        })

        if not size_ok:
            passed = False
            continue

        if path.suffix.lower() in TEXT_EXTENSIONS:
            data = path.read_bytes()

            nul_ok = b"\x00" not in data
            checks.append({
                "name": f"no_nul:{rel}",
                "pass": nul_ok,
            })

            if not nul_ok:
                passed = False

            try:
                data.decode("utf-8")
                utf8_ok = True
            except UnicodeDecodeError:
                utf8_ok = False

            checks.append({
                "name": f"utf8:{rel}",
                "pass": utf8_ok,
            })

            if not utf8_ok:
                passed = False

    return {
        "pass": passed,
        "checks": checks,
    }


def validate_wesnoth_addon(
    worktree: Path,
    validation_root: str,
) -> dict:
    root = worktree / validation_root
    main_cfg = root / "_main.cfg"

    checks = {
        "addon_root_exists": root.is_dir(),
        "main_cfg_exists": main_cfg.is_file(),
        "main_cfg_nonempty": False,
        "main_cfg_utf8": False,
        "no_invalid_addon_tag": False,
        "no_invalid_translations_tag": False,
        "textdomain_tag_present": False,
        "textdomain_name_present": False,
        "textdomain_path_present": False,
    }

    if main_cfg.is_file():
        data = main_cfg.read_bytes()
        checks["main_cfg_nonempty"] = bool(data.strip())

        try:
            text = data.decode("utf-8")
            checks["main_cfg_utf8"] = True
        except UnicodeDecodeError:
            text = ""

        if text:
            normalized = text.replace(" ", "").replace("\t", "")

            checks["no_invalid_addon_tag"] = (
                "[addon]" not in normalized
                and "[/addon]" not in normalized
            )

            checks["no_invalid_translations_tag"] = (
                "[translations]" not in normalized
                and "[/translations]" not in normalized
            )

            checks["textdomain_tag_present"] = (
                "[textdomain]" in normalized
                and "[/textdomain]" in normalized
            )

            checks["textdomain_name_present"] = (
                'name="wesnoth-Star_Wars_Thrawn_Trilogy"'
                in normalized
                or "name=wesnoth-Star_Wars_Thrawn_Trilogy"
                in normalized
            )

            checks["textdomain_path_present"] = (
                'path="data/add-ons/Star_Wars_Thrawn_Trilogy/translations"'
                in normalized
                or
                "path=data/add-ons/Star_Wars_Thrawn_Trilogy/translations"
                in normalized
            )

    return {
        "pass": all(checks.values()),
        "checks": checks,
        "validation_root": validation_root,
    }


def run_validation(
    *,
    worktree: Path,
    ticket: dict,
    implementer_rc: int,
) -> dict:
    status_entries, changed_paths = read_git_changes(worktree)

    scope = validate_scope(
        changed_paths,
        ticket["allowed_paths"],
    )

    static = validate_static_files(
        worktree,
        changed_paths,
    )

    profile_result = None

    if ticket["validation_profile"] == "wesnoth-addon-static":
        profile_result = validate_wesnoth_addon(
            worktree,
            ticket["validation_root"],
        )

    profile_pass = (
        True if profile_result is None else profile_result["pass"]
    )

    return {
        "implementer_exit_zero": implementer_rc == 0,
        "git_status": status_entries,
        "scope": scope,
        "static": static,
        "profile": ticket["validation_profile"],
        "profile_result": profile_result,
        "pass": (
            implementer_rc == 0
            and scope["pass"]
            and static["pass"]
            and profile_pass
        ),
    }


def save_result(log_dir: Path, result: dict) -> None:
    (log_dir / "result.json").write_text(
        json.dumps(result, indent=2) + "\n"
    )


def _codex_path(path: Path, windows_binary: bool) -> str:
    if not windows_binary:
        return str(path)
    completed = subprocess.run(
        ["wslpath", "-w", str(path)],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        timeout=10,
        check=False,
    )
    if completed.returncode != 0 or not completed.stdout.strip():
        raise RuntimeError("Could not translate the recovery-planner path")
    return completed.stdout.strip()


def plan_recovery(
    *,
    worktree: Path,
    log_dir: Path,
    ticket: dict,
    failure: dict,
    attempt: int,
    effort: str,
    governance_prompt: str,
) -> dict:
    executable = shutil.which("codex") or shutil.which("codex.exe")
    if not executable:
        raise RuntimeError("Codex recovery planner is unavailable")
    schema_path = log_dir / f"recovery-{attempt}-schema.json"
    output_path = log_dir / f"recovery-{attempt}-plan.json"
    schema_path.write_text(json.dumps(RECOVERY_SCHEMA, indent=2) + "\n")
    windows_binary = executable.lower().endswith(".exe")
    prompt = f"""You are the selected bounded recovery planner for this ticket.

{governance_prompt}

Do not edit files, run commands, use the web, expose secrets, broaden scope, or change governance.
This is recovery attempt {attempt} of {recovery_policy.MAX_RECOVERY_ATTEMPTS} for the ticket.
Diagnose only the structured failure below and propose the smallest corrective action.
If the evidence is insufficient or repair would exceed allowed paths, return action stop.

TICKET:
{json.dumps(ticket, indent=2)}

STRUCTURED FAILURE:
{json.dumps(failure, indent=2)}
""".strip()
    command = [
        executable,
        "exec",
        "-C",
        _codex_path(worktree, windows_binary),
        "-s",
        "read-only",
        "-m",
        "gpt-5.6-sol",
        "-c",
        f'model_reasoning_effort="{effort}"',
        "--ephemeral",
        "--ignore-user-config",
        "--color",
        "never",
        "--output-schema",
        _codex_path(schema_path, windows_binary),
        "-o",
        _codex_path(output_path, windows_binary),
        "-",
    ]
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
        cwd=worktree,
        env=environment,
        input=prompt,
        text=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        timeout=RECOVERY_PLANNER_TIMEOUT,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError("Codex recovery planner did not complete")
    try:
        plan = json.loads(output_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError("Codex recovery planner returned no valid plan") from exc
    if plan.get("action") not in {"repair", "stop"}:
        raise RuntimeError("Codex recovery planner returned an invalid action")
    plan["summary"] = recovery_policy.safe_text(plan.get("summary"), "Recovery plan")
    plan["corrective_action"] = recovery_policy.safe_text(
        plan.get("corrective_action"), "Inspect the structured failure.", 1200
    )
    return plan


def plan_recovery_or_fallback(**kwargs: object) -> tuple[dict, bool]:
    """Reuse structured evidence when sufficient and preserve a bounded fallback."""

    failure = kwargs["failure"]
    if not isinstance(failure, dict):
        raise TypeError("failure must be a structured mapping")
    if failure.get("class") == "implementation_or_validation_failure":
        return {
            "action": "repair",
            "summary": "Structured deterministic failure already identifies the repair.",
            "corrective_action": recovery_policy.safe_text(
                failure.get("required_action"),
                "Inspect the structured failure and make the smallest in-scope correction.",
                1200,
            ),
        }, True
    try:
        return plan_recovery(**kwargs), False
    except Exception:
        return {
            "action": "repair",
            "summary": "Recovery planner unavailable; using the structured gate diagnosis.",
            "corrective_action": recovery_policy.safe_text(
                failure.get("required_action"),
                "Inspect the structured failure and make the smallest in-scope correction.",
                1200,
            ),
        }, True


def compact_validation_evidence(validation: dict) -> dict:
    """Retain gate facts needed by models without repeating verbose command evidence."""

    scope = validation.get("scope") or {}
    static = validation.get("static") or {}
    profile = validation.get("profile_result") or {}
    checks = static.get("checks") or []
    return {
        "pass": validation.get("pass") is True,
        "changed_paths": list(scope.get("changed_paths") or [])[:200],
        "scope_violations": list(scope.get("violations") or [])[:50],
        "static_checks": [
            {"name": str(item.get("name") or "")[:160], "pass": item.get("pass") is True}
            for item in checks[:200]
            if isinstance(item, dict)
        ],
        "validation_profile": validation.get("profile"),
        "profile_result": profile,
    }


def evaluate_candidate(
    *,
    status: RuntimeStatus,
    ticket: dict,
    worktree: Path,
    log_dir: Path,
    governance_prompt: str,
    opencode: str,
    google_available: bool,
    implementer_rc: int,
    attempt: int,
) -> dict:
    suffix = "" if attempt == 0 else f"-recovery-{attempt}"
    task_id = ticket["task_id"]
    status.handoff(ticket["worker"] if attempt == 0 else "fast-fix", "validation", "Candidate sent to deterministic validation")
    status.set_worker("validation", "active", "Running deterministic gates")
    validation = run_validation(
        worktree=worktree,
        ticket=ticket,
        implementer_rc=implementer_rc,
    )
    (log_dir / f"validation{suffix}.json").write_text(
        json.dumps(validation, indent=2) + "\n"
    )
    status.set_worker(
        "validation",
        "idle" if validation["pass"] else "error",
        "Deterministic gates passed" if validation["pass"] else "Deterministic gates failed",
        error=None if validation["pass"] else "One or more deterministic gates failed",
    )
    status.gate(
        "Deterministic validation",
        "pass" if validation["pass"] else "fail",
        "All configured checks passed" if validation["pass"] else "Review validation evidence",
    )
    if not validation["pass"]:
        return {
            "pass": False,
            "exit_code": 10,
            "validation": validation,
            "tester_pass": None,
            "reviewer_approve": None,
            "failure": recovery_policy.classify_validation(validation, implementer_rc),
        }

    status.handoff("validation", "tester", "Validated change sent to tester")
    status.set_worker("tester", "active", "Independent verification")
    validation_evidence = compact_validation_evidence(validation)
    tester_prompt = f"""TASK ID: {task_id}

{governance_prompt}

OBJECTIVE:
{ticket['objective']}

ALLOWED PATHS:
{json.dumps(ticket['allowed_paths'], separators=(',', ':'))}

DETERMINISTIC VALIDATION:
{json.dumps(validation_evidence, separators=(',', ':'))}

Independently inspect the changed project files. Do not execute commands, edit files, or use the web.
Return your normal report beginning with VERDICT: PASS or VERDICT: FAIL.
""".strip()
    tester_rc, tester_output = invoke_agent(
        opencode=opencode,
        worktree=worktree,
        agent="tester",
        prompt=tester_prompt,
        log_file=log_dir / f"tester{suffix}.jsonl",
        timeout=TESTER_TIMEOUT,
    )
    tester_pass = tester_rc == 0 and core.contains_verdict(tester_output, "PASS")
    status.set_worker(
        "tester",
        "idle" if tester_pass else "error",
        "Tester passed" if tester_pass else "Tester rejected change",
        error=None if tester_pass else "Independent tester did not return PASS",
    )
    status.gate(
        "Independent tester",
        "pass" if tester_pass else "fail",
        "PASS" if tester_pass else "FAIL or non-decisive response",
    )
    if not tester_pass:
        return {
            "pass": False,
            "exit_code": 11,
            "validation": validation,
            "tester_exit_code": tester_rc,
            "tester_pass": False,
            "reviewer_approve": None,
            "failure": recovery_policy.classify_tester(tester_output, tester_rc),
        }

    status.handoff("tester", "reviewer", "Verified change sent to reviewer")
    status.set_worker("reviewer", "active", "Independent final review")
    reviewer_prompt = f"""TASK ID: {task_id}

{governance_prompt}

OBJECTIVE:
{ticket['objective']}

ALLOWED PATHS:
{json.dumps(ticket['allowed_paths'], separators=(',', ':'))}

DETERMINISTIC VALIDATION:
{json.dumps(validation_evidence, separators=(',', ':'))}

TESTER: exit code {tester_rc}; PASS={tester_pass}

Perform an independent final review. Inspect the relevant changed files yourself.
Do not execute commands, edit files, invoke another agent, or use the web.
Return your normal report beginning with VERDICT: APPROVE or VERDICT: REQUEST_CHANGES.
""".strip()
    primary_rc = None
    primary_output = ""
    primary_approve = False
    primary_request_changes = False
    primary_rc, primary_output = invoke_agent(
        opencode=opencode,
        worktree=worktree,
        agent="reviewer",
        prompt=reviewer_prompt,
        log_file=log_dir / f"reviewer-primary{suffix}.jsonl",
        timeout=PRIMARY_REVIEWER_TIMEOUT,
    )
    primary_approve = primary_rc == 0 and core.contains_verdict(primary_output, "APPROVE")
    primary_request_changes = primary_rc == 0 and core.contains_verdict(primary_output, "REQUEST_CHANGES")

    intermediate_rc = None
    intermediate_output = ""
    intermediate_approve = False
    intermediate_request_changes = False
    fallback_rc = None
    fallback_output = ""
    fallback_approve = False
    fallback_request_changes = False
    reviewer_used = "cloudflare-workers-ai/@cf/nvidia/nemotron-3-120b-a12b"
    reviewer_approve = False
    decisive_output = primary_output
    decisive_rc = primary_rc
    decisive_changes = False
    if primary_request_changes:
        reviewer_used = "cloudflare-workers-ai/@cf/nvidia/nemotron-3-120b-a12b"
        reviewer_approve = False
        decisive_output = primary_output
        decisive_rc = primary_rc
        decisive_changes = True
        status.set_worker("reviewer", "error", "Changes requested", error="Primary reviewer requested changes")
    elif primary_approve:
        reviewer_used = "cloudflare-workers-ai/@cf/nvidia/nemotron-3-120b-a12b"
        reviewer_approve = True
        decisive_output = primary_output
        decisive_rc = primary_rc
        decisive_changes = False
        status.set_worker("reviewer", "idle", "Approved")
    else:
        status.set_worker("reviewer", "waiting", "Unavailable or non-decisive")
        if google_available:
            status.handoff("reviewer", "reviewer-fallback", "Intermediate review activated")
            status.set_assignment("reviewer-fallback", "Google", "gemini-3.8-flash")
            status.set_worker("reviewer-fallback", "active", "Independent intermediate review")
            intermediate_rc, intermediate_output = invoke_agent(
                opencode=opencode,
                worktree=worktree,
                agent="reviewer-intermediate",
                prompt=reviewer_prompt,
                log_file=log_dir / f"reviewer-intermediate{suffix}.jsonl",
                timeout=INTERMEDIATE_REVIEWER_TIMEOUT,
            )
            intermediate_approve = intermediate_rc == 0 and core.contains_verdict(intermediate_output, "APPROVE")
            intermediate_request_changes = intermediate_rc == 0 and core.contains_verdict(intermediate_output, "REQUEST_CHANGES")
        if intermediate_request_changes:
            reviewer_used = "google/gemini-3.8-flash"
            reviewer_approve = False
            decisive_output = intermediate_output
            decisive_rc = intermediate_rc
            decisive_changes = True
            status.set_worker("reviewer-fallback", "error", "Changes requested", error="Intermediate reviewer requested changes")
        elif intermediate_approve:
            reviewer_used = "google/gemini-3.8-flash"
            reviewer_approve = True
            decisive_output = intermediate_output
            decisive_rc = intermediate_rc
            decisive_changes = False
            status.set_worker("reviewer-fallback", "idle", "Approved")
        else:
            status.set_worker("reviewer-fallback", "waiting", "Intermediate unavailable or non-decisive")
            if google_available:
                status.handoff("reviewer-fallback", "reviewer-fallback", "Final fallback review activated")
                status.set_assignment("reviewer-fallback", "Google", "gemini-3.6-flash")
                status.set_worker("reviewer-fallback", "active", "Independent final fallback review")
                fallback_rc, fallback_output = invoke_agent(
                    opencode=opencode,
                    worktree=worktree,
                    agent="reviewer-fallback",
                    prompt=reviewer_prompt,
                    log_file=log_dir / f"reviewer-fallback{suffix}.jsonl",
                    timeout=FALLBACK_REVIEWER_TIMEOUT,
                )
                fallback_approve = fallback_rc == 0 and core.contains_verdict(fallback_output, "APPROVE")
                fallback_request_changes = fallback_rc == 0 and core.contains_verdict(fallback_output, "REQUEST_CHANGES")
                reviewer_used = "google/gemini-3.6-flash"
                reviewer_approve = fallback_approve
                decisive_output = fallback_output
                decisive_rc = fallback_rc
                decisive_changes = fallback_request_changes
                status.set_worker(
                    "reviewer-fallback",
                    "idle" if fallback_approve else "error",
                    "Approved" if fallback_approve else "Final fallback review rejected change",
                    error=None if fallback_approve else "Final fallback reviewer did not approve",
                )
            else:
                status.set_worker(
                    "reviewer-fallback",
                    "error",
                    "Google fallbacks unavailable",
                    error="Nemotron was non-decisive and Google credentials are unavailable",
                )

    status.gate(
        "Independent review",
        "pass" if reviewer_approve else "fail",
        f"{reviewer_used}: " + ("APPROVE" if reviewer_approve else "NOT APPROVED"),
    )
    result = {
        "pass": reviewer_approve,
        "exit_code": 0 if reviewer_approve else 12,
        "validation": validation,
        "tester_exit_code": tester_rc,
        "tester_pass": tester_pass,
        "reviewer_primary_exit_code": primary_rc,
        "reviewer_primary_approve": primary_approve,
        "reviewer_primary_request_changes": primary_request_changes,
        "reviewer_intermediate_exit_code": intermediate_rc,
        "reviewer_intermediate_approve": intermediate_approve,
        "reviewer_intermediate_request_changes": intermediate_request_changes,
        "reviewer_fallback_exit_code": fallback_rc,
        "reviewer_fallback_approve": fallback_approve,
        "reviewer_fallback_request_changes": fallback_request_changes,
        "reviewer_used": reviewer_used,
        "reviewer_approve": reviewer_approve,
    }
    if not reviewer_approve:
        result["failure"] = recovery_policy.classify_reviewer(
            decisive_output,
            decisive_rc,
            requested_changes=decisive_changes,
        )
    return result


def _run_ticket(ticket_path: Path, recovery_effort: str | None = None) -> int:
    global ACTIVE_STATUS
    ticket = load_ticket(ticket_path)

    root = core.find_repo_root()
    status = RuntimeStatus(runtime_status_path(root))
    ACTIVE_STATUS = status
    core.verify_main_baseline(root)

    reference_package = load_reference_package(root)
    governance_references = reference_package["canonical_references"]
    governance_prompt = build_governance_prompt(reference_package)

    opencode = shutil.which("opencode")
    if not opencode:
        print("ERROR: opencode not found in PATH.")
        status.fail_system("Ticket runner stopped: OpenCode unavailable")
        return 3

    google_available = core.provider_preflight()

    timestamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    task_id = ticket["task_id"]

    resume_branch = ticket.get("resume_branch")
    worktree_base = root.parent / f"{root.name}-worktrees"
    if resume_branch:
        branch = resume_branch
        worktree = resolve_resume_worktree(root, branch)
    else:
        branch = f"agent/{task_id.lower()}-{timestamp}"
        worktree = worktree_base / f"{task_id.lower()}-{timestamp}"

    log_dir = root / "agent" / "logs" / f"{task_id}-{timestamp}"
    status.begin_job(
        task_id=task_id,
        objective=ticket["objective"],
        branch=branch,
        worktree=worktree,
        validation_profile=ticket["validation_profile"],
    )

    worktree_base.mkdir(parents=True, exist_ok=True)
    log_dir.mkdir(parents=True, exist_ok=True)

    (log_dir / "ticket.json").write_text(
        json.dumps(ticket, indent=2) + "\n"
    )

    (log_dir / "governance-references.json").write_text(
        json.dumps(governance_references, indent=2) + "\n"
    )

    (log_dir / "reference-package.json").write_text(
        json.dumps(reference_package, indent=2) + "\n"
    )

    print(f"TASK:       {task_id}")
    print(f"WORKER:     {ticket['worker']}")
    print(f"BRANCH:     {branch}")
    print(f"WORKTREE:   {worktree}")
    print(f"VALIDATION: {ticket['validation_profile']}")
    print(f"LOGS:       {log_dir}")
    print()

    if resume_branch:
        _, existing_paths = read_resume_changes(worktree)
        existing_scope = validate_resume_scope(existing_paths, ticket["allowed_paths"])
        if not existing_scope["pass"]:
            violations = "; ".join(existing_scope["violations"][:5])
            status.fail_system(
                "Resumable work failed its original scope boundary",
                detail=f"Existing ticket remnants contain unsafe paths: {violations}",
                failure_class="resume_scope_violation",
                required_action="Inspect the listed unexpected paths before continuing.",
            )
            return 14
        try:
            if ticket.get("resume_pr_number") is not None:
                main_appended = prepare_open_pr_resume(root, worktree, ticket)
            else:
                main_appended = prepare_local_resume(root, worktree)
        except SystemExit as exc:
            status.fail_system(
                "Resumable branch reconciliation stopped safely",
                detail=recovery_policy.safe_text(
                    exc, "The interrupted ticket could not be reconciled with current main."
                ),
                failure_class="resume_reconciliation_failure",
                required_action=(
                    "Inspect the preserved ticket worktree and resolve its main-base state "
                    "before retrying."
                ),
            )
            return 15
        _, existing_paths = read_git_changes(worktree)
        existing_scope = validate_resume_scope(existing_paths, ticket["allowed_paths"])
        if not existing_scope["pass"]:
            violations = "; ".join(existing_scope["violations"][:5])
            status.fail_system(
                "Main reconciliation exceeded the original scope boundary",
                detail=f"Reconciled ticket state contains unsafe paths: {violations}",
                failure_class="resume_scope_violation",
                required_action="Inspect the reconciled worktree before continuing.",
            )
            return 14
        print("[1/5] Existing ticket worktree resumed.")
        status.event(
            (
                "Existing ticket resumed after appending current main"
                if main_appended
                else (
                    "Clean exact-contract ticket worktree resumed before its first edit"
                    if not existing_paths
                    else "Existing isolated ticket worktree resumed"
                )
            ),
            source="coordinator",
        )
    else:
        rc, output = core.git(
            root,
            "worktree",
            "add",
            "-b",
            branch,
            str(worktree),
            "main",
            timeout=60,
        )
        core.require_success(rc, output, "Create isolated ticket worktree")
        print("[1/5] Worktree created.")
        status.event("Isolated ticket worktree created", source="coordinator")
    status.handoff("coordinator", ticket["worker"], "Implementation assigned")
    status.set_worker("coordinator", "idle", "Monitoring ticket gates")
    status.set_worker(ticket["worker"], "active", ticket["objective"])

    continuation_instruction = (
        "This ticket is resuming an existing isolated worktree. Inspect and preserve all "
        "useful existing changes, then complete the original objective in place. Do not "
        "discard, reset, recreate, or restart the implementation."
        if resume_branch else
        "This is an explicitly authorized fresh ticket worktree."
    )
    implementation_prompt = f"""
TASK ID: {task_id}

{governance_prompt}

OBJECTIVE:
{ticket["objective"]}

CONTINUATION POLICY:
{continuation_instruction}

You may modify ONLY paths matching these patterns:

{json.dumps(ticket["allowed_paths"], indent=2)}

Do not modify any other project path.

Do not execute commands or tests.
Do not commit, merge, or push.

Implement the smallest change that completely satisfies the objective.

Return your normal structured implementation report.
""".strip()

    impl_rc, impl_output = invoke_agent(
        opencode=opencode,
        worktree=worktree,
        agent=ticket["worker"],
        prompt=implementation_prompt,
        log_file=log_dir / "implementer.jsonl",
        timeout=IMPLEMENTER_TIMEOUT,
    )

    primary_impl_rc = impl_rc
    terra_fallback = {
        "used": False, "provider": "OpenAI", "model": "gpt-5.6-terra",
        "reasoning_effort": "medium", "exit_code": None,
    }
    if recovery_policy.should_use_terra_fallback(ticket["worker"], impl_rc, False):
        terra_fallback["used"] = True
        status.handoff("coordinator", "implementer", "GPT-OSS to Terra Medium fallback")
        status.set_assignment("implementer", "OpenAI", "GPT-5.6 Terra · Medium")
        status.set_worker("implementer", "active", "Running single Terra fallback")
        terra_prompt = implementation_prompt.replace(
            "Do not execute commands or tests.",
            "You may use read-only inspection commands and apply patches. Do not run tests, "
            "package managers, network commands, or Git write commands.",
        )
        terra_rc, _ = invoke_terra_implementer(
            worktree=worktree,
            prompt=terra_prompt,
            log_file=log_dir / "implementer-terra-fallback.txt",
        )
        terra_fallback["exit_code"] = terra_rc
        impl_rc = 0 if terra_rc == 0 else recovery_policy.TERRA_FALLBACK_FAILURE
        status.set_worker(
            "implementer", "idle" if terra_rc == 0 else "error",
            "Terra fallback returned" if terra_rc == 0 else "Terra fallback failed",
            error=None if terra_rc == 0 else f"Terra exited with code {terra_rc}",
        )

    print(f"[2/5] Implementation exit code: {impl_rc}")
    status.set_worker(
        ticket["worker"],
        "idle" if impl_rc == 0 else "error",
        "Implementation returned" if impl_rc == 0 else "Implementation failed",
        error=None if impl_rc == 0 else f"Worker exited with code {impl_rc}",
    )
    recovery_attempts = []
    attempt = 0
    while True:
        evaluation = evaluate_candidate(
            status=status,
            ticket=ticket,
            worktree=worktree,
            log_dir=log_dir,
            governance_prompt=governance_prompt,
            opencode=opencode,
            google_available=google_available,
            implementer_rc=impl_rc,
            attempt=attempt,
        )
        if attempt and recovery_attempts:
            recovery_attempts[-1]["changed_paths"] = (
                evaluation.get("validation", {}).get("scope", {}).get("changed_paths", [])
            )
            recovery_attempts[-1]["gate_result"] = (
                "PASS" if evaluation["pass"] else evaluation.get("failure", {}).get("class", "FAIL")
            )
        if evaluation["pass"]:
            result = {
                "task_id": task_id,
                "branch": branch,
                "worktree": str(worktree),
                "logs": str(log_dir),
                "governance_references": governance_references,
                "reference_package": reference_package,
                "worker": ticket["worker"],
                "implementation_exit_code": impl_rc,
                "primary_implementation_exit_code": primary_impl_rc,
                "terra_implementer_fallback": terra_fallback,
                **{key: value for key, value in evaluation.items() if key not in {"pass", "exit_code"}},
                "recovery_attempts": recovery_attempts,
                "final_verdict": "PASS",
                "commit_created": False,
                "merge_performed": False,
            }
            save_result(log_dir, result)
            status.finish(True, "Ticket passed all local gates")
            print(json.dumps(result, indent=2))
            print("\nPASS: ticket passed all gates. No commit or merge was performed.")
            return 0

        failure = evaluation["failure"]
        can_recover = recovery_policy.can_attempt(
            attempt,
            failure,
            recovery_effort is not None,
        )
        if not can_recover:
            failure = {**failure, "attempt": attempt, "limit": recovery_policy.MAX_RECOVERY_ATTEMPTS}
            result = {
                "task_id": task_id,
                "branch": branch,
                "worktree": str(worktree),
                "logs": str(log_dir),
                "governance_references": governance_references,
                "reference_package": reference_package,
                "worker": ticket["worker"],
                "implementation_exit_code": impl_rc,
                "primary_implementation_exit_code": primary_impl_rc,
                "terra_implementer_fallback": terra_fallback,
                **{key: value for key, value in evaluation.items() if key not in {"pass", "exit_code"}},
                "failure": failure,
                "recovery_attempts": recovery_attempts,
                "final_verdict": "FAIL",
                "commit_created": False,
                "merge_performed": False,
            }
            save_result(log_dir, result)
            status.finish(
                False,
                "Ticket stopped after bounded recovery" if attempt else "Ticket stopped safely",
                detail=failure["detail"],
                failure_class=failure["class"],
                required_action=failure["required_action"],
                recovery_attempt=attempt,
                recovery_limit=recovery_policy.MAX_RECOVERY_ATTEMPTS,
            )
            print(json.dumps(result, indent=2))
            print("\nFAIL: ticket stopped without commit or merge.")
            return evaluation["exit_code"]

        next_attempt = attempt + 1
        plan, structured_plan = plan_recovery_or_fallback(
            worktree=worktree,
            log_dir=log_dir,
            ticket=ticket,
            failure=failure,
            attempt=next_attempt,
            effort=recovery_effort,
            governance_prompt=governance_prompt,
        )
        if structured_plan:
            status.event(
                "Structured recovery brief used; advisory planning call avoided",
                kind="recovery",
                level="warning",
                detail=plan["summary"],
                failure_class=failure["class"],
                required_action=plan["corrective_action"],
                recovery_attempt=attempt,
                recovery_limit=recovery_policy.MAX_RECOVERY_ATTEMPTS,
            )
        if plan["action"] == "stop":
            failure = {
                **failure,
                "detail": plan["summary"],
                "required_action": plan["corrective_action"],
                "eligible": False,
                "attempt": attempt,
                "limit": recovery_policy.MAX_RECOVERY_ATTEMPTS,
            }
            evaluation["failure"] = failure
            result = {
                "task_id": task_id, "branch": branch, "worktree": str(worktree),
                "logs": str(log_dir), "governance_references": governance_references,
                "reference_package": reference_package, "worker": ticket["worker"],
                "implementation_exit_code": impl_rc,
                "primary_implementation_exit_code": primary_impl_rc,
                "terra_implementer_fallback": terra_fallback,
                **evaluation,
                "recovery_attempts": recovery_attempts, "final_verdict": "FAIL",
                "commit_created": False, "merge_performed": False,
            }
            save_result(log_dir, result)
            status.finish(
                False, "Recovery planner declined unsafe repair", detail=failure["detail"],
                failure_class=failure["class"], required_action=failure["required_action"],
                recovery_attempt=attempt, recovery_limit=recovery_policy.MAX_RECOVERY_ATTEMPTS,
            )
            return evaluation["exit_code"]

        attempt = next_attempt
        status.event(
            f"Recovery attempt {attempt} of {recovery_policy.MAX_RECOVERY_ATTEMPTS}",
            kind="recovery",
            level="warning",
            detail=failure["detail"],
            failure_class=failure["class"],
            required_action=plan["corrective_action"],
            recovery_attempt=attempt,
            recovery_limit=recovery_policy.MAX_RECOVERY_ATTEMPTS,
        )
        status.handoff("coordinator", "fast-fix", f"Scoped recovery attempt {attempt} assigned")
        status.set_worker("fast-fix", "active", plan["corrective_action"])
        repair_prompt = f"""TASK ID: {task_id}

{governance_prompt}

This is recovery attempt {attempt} of {recovery_policy.MAX_RECOVERY_ATTEMPTS}.
Preserve the original objective and modify only the original allowed paths.
Do not execute commands or tests. Do not commit, merge, or push.

ORIGINAL OBJECTIVE:
{ticket['objective']}

ALLOWED PATHS:
{json.dumps(ticket['allowed_paths'], indent=2)}

SAFE FAILURE DIAGNOSTIC:
{failure['detail']}

COORDINATOR CORRECTIVE ACTION:
{plan['corrective_action']}

Inspect the existing candidate and make the smallest correction.
""".strip()
        impl_rc, _ = invoke_agent(
            opencode=opencode,
            worktree=worktree,
            agent="fast-fix",
            prompt=repair_prompt,
            log_file=log_dir / f"recovery-{attempt}-fast-fix.jsonl",
            timeout=IMPLEMENTER_TIMEOUT,
        )
        status.set_worker(
            "fast-fix",
            "idle" if impl_rc == 0 else "error",
            "Recovery candidate returned" if impl_rc == 0 else "Recovery worker failed",
            error=None if impl_rc == 0 else f"Fast-Fix exited with code {impl_rc}",
        )
        recovery_attempts.append({
            "attempt": attempt,
            "failure_class": failure["class"],
            "diagnostic": failure["detail"],
            "corrective_action": plan["corrective_action"],
            "fast_fix_exit_code": impl_rc,
        })


def run_ticket(ticket_path: Path, recovery_effort: str | None = None) -> int:
    try:
        return _run_ticket(ticket_path, recovery_effort)
    except SystemExit as exc:
        if ACTIVE_STATUS is not None:
            try:
                code = int(exc.code)
            except (TypeError, ValueError):
                code = 1
            failure = recovery_policy.hard_stop_for_exit(code)
            ACTIVE_STATUS.fail_system(
                "Ticket runner stopped before completion",
                detail=failure["detail"],
                failure_class=failure["class"],
                required_action=failure["required_action"],
            )
        raise
    except Exception as exc:
        if ACTIVE_STATUS is not None:
            ACTIVE_STATUS.fail_system(
                "Unexpected ticket-runner failure",
                detail="The deterministic runner encountered an internal error and stopped fail-closed.",
                failure_class="internal_runner_failure",
                required_action="Review the local ticket traceback; do not retry autonomously.",
            )
        raise


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Bounded deterministic project ticket runner"
    )

    parser.add_argument(
        "ticket",
        type=Path,
        help="Path to a ticket JSON file",
    )
    parser.add_argument(
        "--recovery-effort",
        choices=("low", "medium", "high"),
        default=None,
        help="Enable at most two Sol-planned scoped repair attempts.",
    )

    args = parser.parse_args()
    return run_ticket(args.ticket.resolve(), args.recovery_effort)


if __name__ == "__main__":
    sys.exit(main())
