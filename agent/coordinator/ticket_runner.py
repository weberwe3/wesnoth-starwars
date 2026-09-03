#!/usr/bin/env python3

from __future__ import annotations

import argparse
import datetime as dt
import fnmatch
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

import coordinator as core


IMPLEMENTER_TIMEOUT = 240
TESTER_TIMEOUT = 180
PRIMARY_REVIEWER_TIMEOUT = 75
FALLBACK_REVIEWER_TIMEOUT = 180

VALID_WORKERS = {"implementer", "fast-fix"}
VALID_PROFILES = {"static-text", "wesnoth-addon-static"}

PROTECTED_EXACT = {
    ".gitignore",
    "AGENTS.md",
    "opencode.json",
    "opencode.jsonc",
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

    return ticket


def is_protected(path: str) -> bool:
    path = path.replace("\\", "/")

    if path in PROTECTED_EXACT or path == ".git":
        return True

    return any(path.startswith(prefix) for prefix in PROTECTED_PREFIXES)


def path_allowed(path: str, patterns: list[str]) -> bool:
    path = path.replace("\\", "/")
    return any(fnmatch.fnmatchcase(path, pattern) for pattern in patterns)


def read_git_changes(worktree: Path) -> tuple[list[str], list[str]]:
    rc, output = core.git(
        worktree,
        "status",
        "--porcelain=v1",
        "--untracked-files=all",
    )
    core.require_success(rc, output, "Read implementation Git status")

    entries = []
    paths = []

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

        paths.append(path)

    return entries, paths


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


def validate_static_files(
    worktree: Path,
    changed_paths: list[str],
) -> dict:
    checks = []
    passed = True

    rc, output = core.git(worktree, "diff", "--check")
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


def run_ticket(ticket_path: Path) -> int:
    ticket = load_ticket(ticket_path)

    root = core.find_repo_root()
    core.verify_main_baseline(root)

    opencode = shutil.which("opencode")
    if not opencode:
        print("ERROR: opencode not found in PATH.")
        return 3

    google_available = core.provider_preflight()

    timestamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    task_id = ticket["task_id"]

    branch = f"agent/{task_id.lower()}-{timestamp}"

    worktree_base = root.parent / f"{root.name}-worktrees"
    worktree = worktree_base / f"{task_id.lower()}-{timestamp}"

    log_dir = root / "agent" / "logs" / f"{task_id}-{timestamp}"

    worktree_base.mkdir(parents=True, exist_ok=True)
    log_dir.mkdir(parents=True, exist_ok=True)

    (log_dir / "ticket.json").write_text(
        json.dumps(ticket, indent=2) + "\n"
    )

    print(f"TASK:       {task_id}")
    print(f"WORKER:     {ticket['worker']}")
    print(f"BRANCH:     {branch}")
    print(f"WORKTREE:   {worktree}")
    print(f"VALIDATION: {ticket['validation_profile']}")
    print(f"LOGS:       {log_dir}")
    print()

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

    implementation_prompt = f"""
TASK ID: {task_id}

OBJECTIVE:
{ticket["objective"]}

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

    print(f"[2/5] Implementation exit code: {impl_rc}")

    validation = run_validation(
        worktree=worktree,
        ticket=ticket,
        implementer_rc=impl_rc,
    )

    (log_dir / "validation.json").write_text(
        json.dumps(validation, indent=2) + "\n"
    )

    print(
        "[3/5] Deterministic validation: "
        + ("PASS" if validation["pass"] else "FAIL")
    )

    if not validation["pass"]:
        result = {
            "task_id": task_id,
            "branch": branch,
            "worktree": str(worktree),
            "logs": str(log_dir),
            "implementation_exit_code": impl_rc,
            "validation": validation,
            "tester_pass": None,
            "reviewer_approve": None,
            "final_verdict": "FAIL",
            "commit_created": False,
            "merge_performed": False,
        }
        save_result(log_dir, result)

        print(json.dumps(result, indent=2))
        print("\nFAIL: deterministic gate rejected the implementation.")
        return 10

    tester_prompt = f"""
TASK ID: {task_id}

OBJECTIVE:
{ticket["objective"]}

ALLOWED PATHS:
{json.dumps(ticket["allowed_paths"], indent=2)}

DETERMINISTIC VALIDATION:
{json.dumps(validation, indent=2)}

Independently inspect the changed project files.

Do not execute commands.
Do not edit files.
Do not use the web.

Determine whether the implementation satisfies the objective and whether the
deterministic evidence is sufficient.

Return your normal report beginning with:
VERDICT: PASS
or
VERDICT: FAIL
""".strip()

    tester_rc, tester_output = invoke_agent(
        opencode=opencode,
        worktree=worktree,
        agent="tester",
        prompt=tester_prompt,
        log_file=log_dir / "tester.jsonl",
        timeout=TESTER_TIMEOUT,
    )

    tester_pass = (
        tester_rc == 0
        and core.contains_verdict(tester_output, "PASS")
    )

    print(
        f"[4/5] Tester exit code: {tester_rc}; "
        f"PASS={tester_pass}"
    )

    if not tester_pass:
        result = {
            "task_id": task_id,
            "branch": branch,
            "worktree": str(worktree),
            "logs": str(log_dir),
            "implementation_exit_code": impl_rc,
            "validation": validation,
            "tester_exit_code": tester_rc,
            "tester_pass": False,
            "reviewer_approve": None,
            "final_verdict": "FAIL",
            "commit_created": False,
            "merge_performed": False,
        }
        save_result(log_dir, result)

        print(json.dumps(result, indent=2))
        print("\nFAIL: tester gate rejected the implementation.")
        return 11

    reviewer_prompt = f"""
TASK ID: {task_id}

OBJECTIVE:
{ticket["objective"]}

ALLOWED PATHS:
{json.dumps(ticket["allowed_paths"], indent=2)}

DETERMINISTIC VALIDATION:
{json.dumps(validation, indent=2)}

TESTER:
- exit code: {tester_rc}
- PASS: {tester_pass}

Perform an independent final review.

Inspect the relevant changed files yourself.

Do not execute commands.
Do not edit files.
Do not invoke another agent.
Do not use the web.

Return your normal report beginning with:
VERDICT: APPROVE
or
VERDICT: REQUEST_CHANGES
""".strip()

    primary_rc = None
    primary_approve = False
    primary_request_changes = False

    if google_available:
        primary_rc, primary_output = invoke_agent(
            opencode=opencode,
            worktree=worktree,
            agent="reviewer",
            prompt=reviewer_prompt,
            log_file=log_dir / "reviewer-primary.jsonl",
            timeout=PRIMARY_REVIEWER_TIMEOUT,
        )

        primary_approve = (
            primary_rc == 0
            and core.contains_verdict(primary_output, "APPROVE")
        )

        primary_request_changes = (
            primary_rc == 0
            and core.contains_verdict(
                primary_output,
                "REQUEST_CHANGES",
            )
        )

    fallback_rc = None
    fallback_approve = False
    fallback_request_changes = False
    reviewer_used = None

    if primary_request_changes:
        reviewer_used = "google/gemini-3.6-flash"
        reviewer_approve = False

    elif primary_approve:
        reviewer_used = "google/gemini-3.6-flash"
        reviewer_approve = True

    else:
        print(
            "      Primary reviewer unavailable/non-decisive; "
            "using fallback."
        )

        fallback_rc, fallback_output = invoke_agent(
            opencode=opencode,
            worktree=worktree,
            agent="reviewer-fallback",
            prompt=reviewer_prompt,
            log_file=log_dir / "reviewer-fallback.jsonl",
            timeout=FALLBACK_REVIEWER_TIMEOUT,
        )

        fallback_approve = (
            fallback_rc == 0
            and core.contains_verdict(
                fallback_output,
                "APPROVE",
            )
        )

        fallback_request_changes = (
            fallback_rc == 0
            and core.contains_verdict(
                fallback_output,
                "REQUEST_CHANGES",
            )
        )

        reviewer_used = (
            "cloudflare-workers-ai/"
            "@cf/nvidia/nemotron-3-120b-a12b"
        )

        reviewer_approve = fallback_approve

    print(
        f"[5/5] Reviewer: {reviewer_used}; "
        f"APPROVE={reviewer_approve}"
    )

    final_pass = reviewer_approve

    result = {
        "task_id": task_id,
        "branch": branch,
        "worktree": str(worktree),
        "logs": str(log_dir),
        "worker": ticket["worker"],
        "implementation_exit_code": impl_rc,
        "validation": validation,
        "tester_exit_code": tester_rc,
        "tester_pass": tester_pass,
        "reviewer_primary_exit_code": primary_rc,
        "reviewer_primary_approve": primary_approve,
        "reviewer_primary_request_changes": primary_request_changes,
        "reviewer_fallback_exit_code": fallback_rc,
        "reviewer_fallback_approve": fallback_approve,
        "reviewer_fallback_request_changes": fallback_request_changes,
        "reviewer_used": reviewer_used,
        "reviewer_approve": reviewer_approve,
        "final_verdict": "PASS" if final_pass else "FAIL",
        "commit_created": False,
        "merge_performed": False,
    }

    save_result(log_dir, result)

    print()
    print("========================================")
    print("TICKET RESULT")
    print("========================================")
    print(json.dumps(result, indent=2))
    print("========================================")

    if final_pass:
        print(
            "\nPASS: ticket passed all gates. "
            "No commit or merge was performed."
        )
        return 0

    print(
        "\nFAIL: reviewer gate rejected the ticket. "
        "No commit or merge was performed."
    )
    return 12


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Bounded deterministic project ticket runner"
    )

    parser.add_argument(
        "ticket",
        type=Path,
        help="Path to a ticket JSON file",
    )

    args = parser.parse_args()
    return run_ticket(args.ticket.resolve())


if __name__ == "__main__":
    sys.exit(main())
