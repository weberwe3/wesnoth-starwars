#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
COORDINATOR_DIR = ROOT / "agent" / "coordinator"
DASHBOARD_DIR = ROOT / "agent" / "dashboard"

sys.path.insert(0, str(COORDINATOR_DIR))
sys.path.insert(0, str(DASHBOARD_DIR))

import runtime_status as status  # noqa: E402
import ticket_runner  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run a normal ticket with live dashboard telemetry"
    )
    parser.add_argument("ticket", type=Path)
    args = parser.parse_args()
    ticket_path = args.ticket.resolve()

    ticket = ticket_runner.load_ticket(ticket_path)
    root = ticket_runner.core.find_repo_root()
    selected_worker = ticket["worker"]

    status.start_ticket(root, ticket)

    original_invoke = ticket_runner.invoke_agent
    original_validation = ticket_runner.run_validation
    original_save_result = ticket_runner.save_result
    original_git = ticket_runner.core.git

    def live_git(cwd: Path, *git_args: str, **kwargs):
        if len(git_args) >= 5 and git_args[0:2] == ("worktree", "add"):
            try:
                branch_index = git_args.index("-b")
                branch = git_args[branch_index + 1]
                worktree = git_args[branch_index + 2]
                status.set_ticket_context(
                    root,
                    branch=branch,
                    worktree=str(worktree),
                )
            except (ValueError, IndexError):
                pass
        return original_git(cwd, *git_args, **kwargs)

    def live_invoke_agent(**kwargs):
        agent = kwargs.get("agent")

        if agent in ("implementer", "fast-fix"):
            status.set_worker(
                root,
                "coordinator",
                "idle",
                "Implementation worker is active",
            )
            status.transfer(
                root,
                "coordinator",
                agent,
                "Implementation task assigned",
            )
            status.set_worker(
                root,
                agent,
                "working",
                ticket["objective"][:220],
                event_message=f"{agent} started implementation.",
            )

        elif agent == "tester":
            status.transfer(
                root,
                "validation",
                "tester",
                "Deterministic validation passed; tester review assigned",
            )
            status.set_worker(
                root,
                "tester",
                "working",
                "Independently evaluating implementation and validation evidence",
                event_message="Tester review started.",
            )

        elif agent == "reviewer":
            status.transfer(
                root,
                "tester",
                "reviewer",
                "Tester passed; primary review assigned",
            )
            status.set_worker(
                root,
                "reviewer",
                "working",
                "Performing independent final review",
                event_message="Primary reviewer started.",
            )

        elif agent == "reviewer-fallback":
            status.transfer(
                root,
                "reviewer",
                "reviewer-fallback",
                "Primary reviewer unavailable or non-decisive; fallback assigned",
            )
            status.set_worker(
                root,
                "reviewer-fallback",
                "working",
                "Performing fallback final review",
                event_message="Fallback reviewer started.",
            )

        rc, output = original_invoke(**kwargs)

        if agent in ("implementer", "fast-fix"):
            status.set_worker(
                root,
                agent,
                "idle" if rc == 0 else "error",
                "Implementation returned" if rc == 0 else "Implementation failed",
                error=None if rc == 0 else f"Implementation exit code {rc}",
                event_message=(
                    f"{agent} returned successfully."
                    if rc == 0
                    else f"{agent} returned exit code {rc}."
                ),
            )

        elif agent == "tester":
            passed = rc == 0 and ticket_runner.core.contains_verdict(output, "PASS")
            status.set_worker(
                root,
                "tester",
                "idle" if passed else "error",
                "Tester passed" if passed else "Tester rejected or failed",
                error=None if passed else f"Tester exit code {rc} or FAIL verdict",
                event_message=(
                    "Tester passed."
                    if passed
                    else "Tester did not pass the implementation."
                ),
            )

        elif agent == "reviewer":
            approved = rc == 0 and ticket_runner.core.contains_verdict(
                output, "APPROVE"
            )
            requested = rc == 0 and ticket_runner.core.contains_verdict(
                output, "REQUEST_CHANGES"
            )
            if approved:
                state_name = "idle"
                task = "Primary reviewer approved"
                error = None
            elif requested:
                state_name = "error"
                task = "Primary reviewer requested changes"
                error = "Primary reviewer returned REQUEST_CHANGES"
            else:
                state_name = "waiting"
                task = "Primary reviewer unavailable or non-decisive"
                error = None
            status.set_worker(
                root,
                "reviewer",
                state_name,
                task,
                error=error,
                event_message=task,
            )

        elif agent == "reviewer-fallback":
            approved = rc == 0 and ticket_runner.core.contains_verdict(
                output, "APPROVE"
            )
            status.set_worker(
                root,
                "reviewer-fallback",
                "idle" if approved else "error",
                "Fallback reviewer approved"
                if approved
                else "Fallback reviewer rejected or failed",
                error=None if approved else f"Fallback reviewer exit code {rc}",
                event_message=(
                    "Fallback reviewer approved."
                    if approved
                    else "Fallback reviewer did not approve."
                ),
            )

        return rc, output

    def live_validation(**kwargs):
        status.transfer(
            root,
            selected_worker,
            "validation",
            "Implementation returned for deterministic validation",
        )
        status.set_worker(
            root,
            "validation",
            "working",
            f"Running {ticket['validation_profile']}",
            event_message="Deterministic validation started.",
        )
        result = original_validation(**kwargs)
        passed = bool(result.get("pass"))
        status.set_worker(
            root,
            "validation",
            "idle" if passed else "error",
            "Deterministic validation passed"
            if passed
            else "Deterministic validation failed",
            error=None if passed else "Deterministic validation failed",
            event_message=(
                "Deterministic validation passed."
                if passed
                else "Deterministic validation failed."
            ),
        )
        return result

    def live_save_result(log_dir: Path, result: dict) -> None:
        original_save_result(log_dir, result)
        verdict = result.get("final_verdict")
        if verdict in ("PASS", "FAIL"):
            status.finish_ticket(
                root,
                verdict,
                f"Ticket {result.get('task_id')} finished with {verdict}.",
            )

    ticket_runner.core.git = live_git
    ticket_runner.invoke_agent = live_invoke_agent
    ticket_runner.run_validation = live_validation
    ticket_runner.save_result = live_save_result

    try:
        return ticket_runner.run_ticket(ticket_path)
    except KeyboardInterrupt:
        status.finish_ticket(root, "FAIL", "Ticket interrupted by user.")
        raise
    except BaseException as exc:
        status.set_worker(
            root,
            "coordinator",
            "error",
            "Ticket runner raised an exception",
            error=f"{type(exc).__name__}: {exc}",
            event_message="Ticket runner raised an exception.",
        )
        status.finish_ticket(root, "FAIL", "Ticket runner terminated unexpectedly.")
        raise


if __name__ == "__main__":
    raise SystemExit(main())
