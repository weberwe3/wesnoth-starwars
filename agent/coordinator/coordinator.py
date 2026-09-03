#!/usr/bin/env python3

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from typing import Optional


AGENT_TIMEOUT_SECONDS = 240

# These are stripped from any future deterministic test subprocess.
# The initial smoke test does not execute generated code at all.
SENSITIVE_ENV_VARS = {
    "GEMINI_API_KEY",
    "GOOGLE_GENERATIVE_AI_API_KEY",
    "GROQ_API_KEY",
    "NVIDIA_API_KEY",
    "MISTRAL_API_KEY",
    "CLOUDFLARE_ACCOUNT_ID",
    "CLOUDFLARE_API_KEY",
    "COHERE_API_KEY",
    "CEREBRAS_API_KEY",
    "HF_TOKEN",
}


def run_process(
    command: list[str],
    *,
    cwd: Path,
    timeout: int,
    env: Optional[dict[str, str]] = None,
) -> tuple[int, str]:
    """Run a subprocess and return (exit_code, combined_output)."""
    try:
        completed = subprocess.run(
            command,
            cwd=str(cwd),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=timeout,
            check=False,
        )
        return completed.returncode, completed.stdout
    except subprocess.TimeoutExpired as exc:
        partial = exc.stdout or ""
        if isinstance(partial, bytes):
            partial = partial.decode(errors="replace")
        return 124, partial + "\n[COORDINATOR] PROCESS TIMEOUT\n"


def git(
    root: Path,
    *args: str,
    timeout: int = 30,
) -> tuple[int, str]:
    return run_process(
        ["git", *args],
        cwd=root,
        timeout=timeout,
    )


def require_success(rc: int, output: str, description: str) -> None:
    if rc != 0:
        print(f"\nERROR: {description} failed with exit code {rc}.")
        if output:
            print(output)
        raise SystemExit(rc or 1)


def find_repo_root() -> Path:
    here = Path(__file__).resolve().parent
    rc, output = git(here, "rev-parse", "--show-toplevel")
    require_success(rc, output, "Locate repository")
    return Path(output.strip()).resolve()


def make_test_env() -> dict[str, str]:
    """Create an environment suitable for executing deterministic tests later."""
    env = dict(os.environ)

    for key in SENSITIVE_ENV_VARS:
        env.pop(key, None)

    # Prevent WSL from re-exporting stripped credential variables if a future
    # test process crosses the Windows/WSL boundary.
    wslenv = env.get("WSLENV", "")
    if wslenv:
        parts = []
        for entry in wslenv.split(":"):
            name = entry.split("/", 1)[0]
            if name not in SENSITIVE_ENV_VARS:
                parts.append(entry)
        env["WSLENV"] = ":".join(parts)

    return env


def verify_main_baseline(root: Path) -> None:
    rc, branch = git(root, "branch", "--show-current")
    require_success(rc, branch, "Read current branch")

    if branch.strip() != "main":
        raise SystemExit(
            f"ERROR: coordinator must be launched from main; current branch is "
            f"{branch.strip()!r}"
        )

    rc, status = git(root, "status", "--porcelain")
    require_success(rc, status, "Read Git status")

    if status.strip():
        print("ERROR: main is not clean:")
        print(status)
        raise SystemExit(2)

    rc, head = git(root, "rev-parse", "--verify", "HEAD")
    require_success(rc, head, "Verify baseline commit")


def invoke_agent(
    *,
    opencode: str,
    worktree: Path,
    agent: str,
    prompt: str,
    log_file: Path,
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

    rc, output = run_process(
        command,
        cwd=worktree,
        timeout=AGENT_TIMEOUT_SECONDS,
        env=dict(os.environ),
    )

    log_file.write_text(output)

    return rc, output


def contains_verdict(output: str, verdict: str) -> bool:
    normalized = output.replace("\\n", "\n").replace("\\r", "")
    return re.search(
        rf"\bVERDICT\s*:\s*{re.escape(verdict)}\b",
        normalized,
        flags=re.IGNORECASE,
    ) is not None


def run_smoke(root: Path) -> int:
    verify_main_baseline(root)

    opencode = shutil.which("opencode")
    if not opencode:
        print("ERROR: opencode not found in PATH.")
        return 3

    timestamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    task_id = f"COORD-SMOKE-{timestamp}"
    branch = f"agent/coord-smoke-{timestamp}"

    # Keep Git worktrees outside the main worktree. Nested worktrees make
    # repository status and cleanup unnecessarily confusing.
    worktree_base = root.parent / f"{root.name}-worktrees"
    worktree = worktree_base / f"coord-smoke-{timestamp}"

    log_dir = root / "agent" / "logs" / task_id
    log_dir.mkdir(parents=True, exist_ok=True)
    worktree_base.mkdir(parents=True, exist_ok=True)

    if worktree.exists():
        print(f"ERROR: worktree already exists: {worktree}")
        return 4

    rc, branch_check = git(root, "show-ref", "--verify", f"refs/heads/{branch}")
    if rc == 0:
        print(f"ERROR: branch already exists: {branch}")
        return 5

    print(f"TASK:     {task_id}")
    print(f"BRANCH:   {branch}")
    print(f"WORKTREE: {worktree}")
    print(f"LOGS:     {log_dir}")
    print()

    # ------------------------------------------------------------------
    # Stage 1: create isolated worktree
    # ------------------------------------------------------------------

    rc, output = git(
        root,
        "worktree",
        "add",
        "-b",
        branch,
        str(worktree),
        "main",
        timeout=60,
    )
    require_success(rc, output, "Create isolated worktree")

    print("[1/4] Worktree created.")

    # ------------------------------------------------------------------
    # Stage 2: implementation
    # ------------------------------------------------------------------

    implementation_prompt = f"""
TASK ID: {task_id}

This is a coordinator smoke test.

Create exactly one new file in the repository root named:

coordinator-smoke.txt

Its entire contents must be exactly this single line followed by a newline:

COORDINATOR_SMOKE=PASS

Do not modify any other file.

Do not run commands or tests.
Do not commit, merge, or push.
Return your normal structured implementation report.
""".strip()

    impl_rc, impl_output = invoke_agent(
        opencode=opencode,
        worktree=worktree,
        agent="implementer",
        prompt=implementation_prompt,
        log_file=log_dir / "implementer.jsonl",
    )

    print(f"[2/4] Implementer exit code: {impl_rc}")

    # ------------------------------------------------------------------
    # Stage 3: trusted deterministic validation
    #
    # IMPORTANT:
    # We do NOT execute anything generated by the LLM here.
    # ------------------------------------------------------------------

    expected_file = worktree / "coordinator-smoke.txt"
    expected_bytes = b"COORDINATOR_SMOKE=PASS\n"

    file_exists = expected_file.is_file()
    exact_content = (
        file_exists and expected_file.read_bytes() == expected_bytes
    )

    status_rc, status_output = git(
        worktree,
        "status",
        "--porcelain=v1",
    )

    require_success(status_rc, status_output, "Inspect implementation status")

    changed_entries = [
        line.rstrip()
        for line in status_output.splitlines()
        if line.strip()
    ]

    expected_status = ["?? coordinator-smoke.txt"]
    scope_clean = changed_entries == expected_status

    deterministic_checks = {
        "implementer_exit_zero": impl_rc == 0,
        "file_exists": file_exists,
        "exact_content": exact_content,
        "only_expected_change": scope_clean,
        "git_status": changed_entries,
    }

    (log_dir / "deterministic-checks.json").write_text(
        json.dumps(deterministic_checks, indent=2) + "\n"
    )

    deterministic_pass = all(
        [
            deterministic_checks["implementer_exit_zero"],
            deterministic_checks["file_exists"],
            deterministic_checks["exact_content"],
            deterministic_checks["only_expected_change"],
        ]
    )

    print(
        "[3/4] Deterministic validation: "
        + ("PASS" if deterministic_pass else "FAIL")
    )

    # ------------------------------------------------------------------
    # Stage 4A: independent tester
    # ------------------------------------------------------------------

    tester_prompt = f"""
TASK ID: {task_id}

Independently evaluate this completed smoke-test implementation.

Requirement:
- coordinator-smoke.txt must exist in the repository root.
- Its entire contents must be exactly:
  COORDINATOR_SMOKE=PASS
- No other repository file may be changed by this task.

The deterministic coordinator produced this evidence:

{json.dumps(deterministic_checks, indent=2)}

Inspect the relevant project file yourself using your read-only tools.

Do not execute commands.
Do not edit files.
Do not use the web.

Return your normal structured tester report beginning with:
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
    )

    tester_pass = (
        tester_rc == 0
        and contains_verdict(tester_output, "PASS")
    )

    print(
        f"[4/4] Tester exit code: {tester_rc}; "
        f"verdict detected: {'PASS' if tester_pass else 'FAIL/UNKNOWN'}"
    )

    # ------------------------------------------------------------------
    # Independent reviewer
    # ------------------------------------------------------------------

    reviewer_prompt = f"""
TASK ID: {task_id}

Perform an independent final review of this smoke-test ticket.

Requirement:
Create only coordinator-smoke.txt with exact contents:
COORDINATOR_SMOKE=PASS

Deterministic coordinator evidence:

{json.dumps(deterministic_checks, indent=2)}

Independent tester process:
- exit code: {tester_rc}
- detected PASS verdict: {tester_pass}

Inspect the relevant project file yourself.

Do not execute commands.
Do not edit files.
Do not invoke another agent.
Do not use the web.

Return your normal structured review beginning with:
VERDICT: APPROVE
or
VERDICT: REQUEST_CHANGES
""".strip()

    reviewer_rc, reviewer_output = invoke_agent(
        opencode=opencode,
        worktree=worktree,
        agent="reviewer",
        prompt=reviewer_prompt,
        log_file=log_dir / "reviewer.jsonl",
    )

    reviewer_pass = (
        reviewer_rc == 0
        and contains_verdict(reviewer_output, "APPROVE")
    )

    print(
        f"      Reviewer exit code: {reviewer_rc}; "
        f"verdict detected: "
        f"{'APPROVE' if reviewer_pass else 'REQUEST_CHANGES/UNKNOWN'}"
    )

    final_pass = (
        deterministic_pass
        and tester_pass
        and reviewer_pass
    )

    result = {
        "task_id": task_id,
        "branch": branch,
        "worktree": str(worktree),
        "logs": str(log_dir),
        "implementation_exit_code": impl_rc,
        "deterministic_checks": deterministic_checks,
        "tester_exit_code": tester_rc,
        "tester_pass": tester_pass,
        "reviewer_exit_code": reviewer_rc,
        "reviewer_approve": reviewer_pass,
        "final_verdict": "PASS" if final_pass else "FAIL",
        "commit_created": False,
        "merge_performed": False,
    }

    (log_dir / "result.json").write_text(
        json.dumps(result, indent=2) + "\n"
    )

    print()
    print("========================================")
    print("COORDINATOR RESULT")
    print("========================================")
    print(json.dumps(result, indent=2))
    print("========================================")

    if final_pass:
        print(
            "\nPASS: pipeline completed successfully. "
            "The worktree has intentionally been left in place for inspection."
        )
        return 0

    print(
        "\nFAIL: at least one gate failed. "
        "No commit or merge was performed."
    )
    return 10


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Deterministic Wesnoth Star Wars agent coordinator"
    )
    parser.add_argument(
        "action",
        choices=["smoke"],
        help="Coordinator action to perform",
    )
    args = parser.parse_args()

    root = find_repo_root()

    if args.action == "smoke":
        return run_smoke(root)

    return 1


if __name__ == "__main__":
    sys.exit(main())
