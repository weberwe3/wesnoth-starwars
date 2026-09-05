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

from runtime_status import RuntimeStatus, runtime_status_path


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
ACTIVE_STATUS: RuntimeStatus | None = None


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



def provider_preflight() -> bool:
    """Validate the provider environment without exposing credential values."""

    required = {
        "GROQ_API_KEY": "Groq implementer",
        "CLOUDFLARE_ACCOUNT_ID": "Cloudflare workers",
        "CLOUDFLARE_API_KEY": "Cloudflare workers",
    }

    missing = [
        f"{name} ({purpose})"
        for name, purpose in required.items()
        if not os.environ.get(name)
    ]

    print("PROVIDER PREFLIGHT:")
    print(
        "  Groq:       "
        + ("PRESENT" if os.environ.get("GROQ_API_KEY") else "MISSING")
    )
    print(
        "  Cloudflare: "
        + (
            "PRESENT"
            if (
                os.environ.get("CLOUDFLARE_ACCOUNT_ID")
                and os.environ.get("CLOUDFLARE_API_KEY")
            )
            else "MISSING"
        )
    )
    print("  Google:     DISABLED — free-tier reviewer route is not reliable")
    print()

    if missing:
        print("ERROR: required provider credentials are missing:")
        for item in missing:
            print(f"  - {item}")
        print(
            "\nLaunch the project through the secure Wesnoth Agent Shell "
            "instead of a normal WSL shell."
        )
        raise SystemExit(6)

    return False


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


def _run_smoke(root: Path) -> int:
    global ACTIVE_STATUS
    status = RuntimeStatus(runtime_status_path(root))
    ACTIVE_STATUS = status
    verify_main_baseline(root)

    opencode = shutil.which("opencode")
    if not opencode:
        print("ERROR: opencode not found in PATH.")
        status.fail_system("Coordinator stopped: OpenCode unavailable")
        return 3

    google_available = provider_preflight()

    timestamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    task_id = f"COORD-SMOKE-{timestamp}"
    branch = f"agent/coord-smoke-{timestamp}"

    # Keep Git worktrees outside the main worktree. Nested worktrees make
    # repository status and cleanup unnecessarily confusing.
    worktree_base = root.parent / f"{root.name}-worktrees"
    worktree = worktree_base / f"coord-smoke-{timestamp}"

    log_dir = root / "agent" / "logs" / task_id
    status.begin_job(
        task_id=task_id,
        objective="Coordinator pipeline smoke test",
        branch=branch,
        worktree=worktree,
        validation_profile="coordinator-smoke",
    )
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
    status.handoff("coordinator", "implementer", "Smoke implementation assigned")
    status.set_worker("coordinator", "idle", "Monitoring smoke test")
    status.set_worker("implementer", "active", "Creating bounded smoke artifact")

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
    status.set_worker(
        "implementer",
        "idle" if impl_rc == 0 else "error",
        "Smoke implementation returned" if impl_rc == 0 else "Smoke implementation failed",
        error=None if impl_rc == 0 else f"Worker exited with code {impl_rc}",
    )
    status.handoff("implementer", "validation", "Smoke artifact sent to validation")
    status.set_worker("validation", "active", "Checking exact smoke-test output")

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
    status.set_worker(
        "validation",
        "idle" if deterministic_pass else "error",
        "Smoke validation passed" if deterministic_pass else "Smoke validation failed",
        error=None if deterministic_pass else "Smoke artifact did not match contract",
    )
    status.gate(
        "Deterministic validation",
        "pass" if deterministic_pass else "fail",
        "Exact smoke contract" if deterministic_pass else "Smoke contract mismatch",
    )
    status.handoff("validation", "tester", "Smoke evidence sent to tester")
    status.set_worker("tester", "active", "Independent smoke verification")

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
    status.set_worker(
        "tester",
        "idle" if tester_pass else "error",
        "Tester passed" if tester_pass else "Tester did not pass",
        error=None if tester_pass else "Independent tester did not return PASS",
    )
    status.gate("Independent tester", "pass" if tester_pass else "fail", "PASS" if tester_pass else "FAIL")
    status.handoff("tester", "reviewer", "Smoke result sent to reviewer")
    status.set_worker("reviewer", "active", "Independent smoke review")

    # ------------------------------------------------------------------
    # Independent reviewer
    #
    # Gemini is preferred for model/provider diversity. It may be
    # unavailable because of quota/rate limits. Infrastructure failure or
    # malformed output triggers the independent fallback reviewer.
    #
    # A substantive REQUEST_CHANGES verdict NEVER triggers fallback.
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

    reviewer_primary_rc = None
    reviewer_primary_approve = False
    reviewer_primary_request_changes = False
    reviewer_intermediate_rc = None
    reviewer_intermediate_approve = False
    reviewer_intermediate_request_changes = False
    reviewer_fallback_rc = None
    reviewer_fallback_approve = False
    reviewer_fallback_request_changes = False
    reviewer_used = None
    reviewer_pass = False

    reviewer_primary_rc, reviewer_primary_output = invoke_agent(
        opencode=opencode,
        worktree=worktree,
        agent="reviewer",
        prompt=reviewer_prompt,
        log_file=log_dir / "reviewer-primary.jsonl",
    )

    reviewer_primary_approve = (
        reviewer_primary_rc == 0
        and contains_verdict(reviewer_primary_output, "APPROVE")
    )

    reviewer_primary_request_changes = (
        reviewer_primary_rc == 0
        and contains_verdict(
            reviewer_primary_output,
            "REQUEST_CHANGES",
        )
    )

    print(
        f"      Primary reviewer exit code: {reviewer_primary_rc}; "
        f"APPROVE={reviewer_primary_approve}; "
        f"REQUEST_CHANGES={reviewer_primary_request_changes}"
    )

    # A real negative review is authoritative. Do not shop for a more
    # favorable answer by invoking another reviewer.
    if reviewer_primary_request_changes:
        status.set_worker("reviewer", "error", "Changes requested", error="Primary reviewer requested changes")
        reviewer_used = "cloudflare-workers-ai/@cf/nvidia/nemotron-3-120b-a12b"
        reviewer_pass = False

    elif reviewer_primary_approve:
        status.set_worker("reviewer", "idle", "Approved")
        reviewer_used = "cloudflare-workers-ai/@cf/nvidia/nemotron-3-120b-a12b"
        reviewer_pass = True

    else:
        status.set_worker("reviewer", "waiting", "Unavailable or non-decisive")
        if google_available:
            status.handoff("reviewer", "reviewer-fallback", "Intermediate smoke review activated")
            status.set_assignment("reviewer-fallback", "Google", "gemini-3.8-flash")
            status.set_worker("reviewer-fallback", "active", "Independent intermediate smoke review")
            print(
                "      Primary reviewer unavailable or non-decisive; "
                "invoking intermediate reviewer."
            )

            reviewer_intermediate_rc, reviewer_intermediate_output = invoke_agent(
                opencode=opencode,
                worktree=worktree,
                agent="reviewer-intermediate",
                prompt=reviewer_prompt,
                log_file=log_dir / "reviewer-intermediate.jsonl",
            )

            reviewer_intermediate_approve = (
                reviewer_intermediate_rc == 0
                and contains_verdict(reviewer_intermediate_output, "APPROVE")
            )
            reviewer_intermediate_request_changes = (
                reviewer_intermediate_rc == 0
                and contains_verdict(reviewer_intermediate_output, "REQUEST_CHANGES")
            )

            print(
                f"      Intermediate reviewer exit code: {reviewer_intermediate_rc}; "
                f"APPROVE={reviewer_intermediate_approve}; "
                f"REQUEST_CHANGES={reviewer_intermediate_request_changes}"
            )

        if reviewer_intermediate_request_changes:
            reviewer_used = "google/gemini-3.8-flash"
            reviewer_pass = False
            status.set_worker("reviewer-fallback", "error", "Changes requested", error="Intermediate reviewer requested changes")
        elif reviewer_intermediate_approve:
            reviewer_used = "google/gemini-3.8-flash"
            reviewer_pass = True
            status.set_worker("reviewer-fallback", "idle", "Approved")
        else:
            status.set_worker("reviewer-fallback", "waiting", "Intermediate unavailable or non-decisive")
            if google_available:
                status.handoff("reviewer-fallback", "reviewer-fallback", "Final fallback smoke review activated")
                status.set_assignment("reviewer-fallback", "Google", "gemini-3.6-flash")
                status.set_worker("reviewer-fallback", "active", "Independent final fallback smoke review")
                print(
                    "      Intermediate reviewer unavailable or non-decisive; "
                    "invoking final fallback reviewer."
                )
                reviewer_fallback_rc, reviewer_fallback_output = invoke_agent(
                    opencode=opencode,
                    worktree=worktree,
                    agent="reviewer-fallback",
                    prompt=reviewer_prompt,
                    log_file=log_dir / "reviewer-fallback.jsonl",
                )
                reviewer_fallback_approve = (
                    reviewer_fallback_rc == 0
                    and contains_verdict(reviewer_fallback_output, "APPROVE")
                )
                reviewer_fallback_request_changes = (
                    reviewer_fallback_rc == 0
                    and contains_verdict(reviewer_fallback_output, "REQUEST_CHANGES")
                )
                reviewer_used = "google/gemini-3.6-flash"
                reviewer_pass = reviewer_fallback_approve
                status.set_worker(
                    "reviewer-fallback",
                    "idle" if reviewer_fallback_approve else "error",
                    "Approved" if reviewer_fallback_approve else "Final fallback did not approve",
                    error=None if reviewer_fallback_approve else "Final fallback reviewer did not approve",
                )
                print(
                    f"      Final fallback reviewer exit code: {reviewer_fallback_rc}; "
                    f"APPROVE={reviewer_fallback_approve}; "
                    f"REQUEST_CHANGES={reviewer_fallback_request_changes}"
                )
            else:
                reviewer_used = "cloudflare-workers-ai/@cf/nvidia/nemotron-3-120b-a12b"
                reviewer_pass = False
                status.set_worker(
                    "reviewer-fallback",
                    "error",
                    "Google fallbacks unavailable",
                    error="Nemotron was non-decisive and Google credentials are unavailable",
                )

    final_pass = (
        deterministic_pass
        and tester_pass
        and reviewer_pass
    )
    status.gate(
        "Independent review",
        "pass" if reviewer_pass else "fail",
        f"{reviewer_used or 'No reviewer'}: "
        + ("APPROVE" if reviewer_pass else "NOT APPROVED"),
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
        "google_reviewer_available": google_available,
        "reviewer_primary_exit_code": reviewer_primary_rc,
        "reviewer_primary_approve": reviewer_primary_approve,
        "reviewer_primary_request_changes": (
            reviewer_primary_request_changes
        ),
        "reviewer_intermediate_exit_code": reviewer_intermediate_rc,
        "reviewer_intermediate_approve": reviewer_intermediate_approve,
        "reviewer_intermediate_request_changes": (
            reviewer_intermediate_request_changes
        ),
        "reviewer_fallback_exit_code": reviewer_fallback_rc,
        "reviewer_fallback_approve": reviewer_fallback_approve,
        "reviewer_fallback_request_changes": (
            reviewer_fallback_request_changes
        ),
        "reviewer_used": reviewer_used,
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
        status.finish(True, "Coordinator smoke test passed all gates")
        print(
            "\nPASS: pipeline completed successfully. "
            "The worktree has intentionally been left in place for inspection."
        )
        return 0

    status.finish(False, "Coordinator smoke test failed")
    print(
        "\nFAIL: at least one gate failed. "
        "No commit or merge was performed."
    )
    return 10


def run_smoke(root: Path) -> int:
    try:
        return _run_smoke(root)
    except SystemExit:
        if ACTIVE_STATUS is not None:
            ACTIVE_STATUS.fail_system("Coordinator stopped before completion")
        raise
    except Exception:
        if ACTIVE_STATUS is not None:
            ACTIVE_STATUS.fail_system("Unexpected coordinator failure")
        raise


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
