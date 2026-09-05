#!/usr/bin/env python3

"""Secret-safe failure classification for bounded autonomous recovery."""

from __future__ import annotations

import re
from typing import Any


MAX_RECOVERY_ATTEMPTS = 2
TERRA_FALLBACK_FAILURE = 86
_SENSITIVE = re.compile(
    r"(?i)(api[_-]?key|token|secret|password|credential|private[_-]?key)"
    r"\s*[\"']?\s*[:=]\s*[\"']?[^\"'\s,;]+"
)
_LONG_SECRET = re.compile(
    r"\b(?=[A-Za-z0-9_+=-]{40,}\b)(?=[A-Za-z0-9_+=-]*[A-Z])"
    r"(?=[A-Za-z0-9_+=-]*[a-z])(?=[A-Za-z0-9_+=-]*\d)[A-Za-z0-9_+=-]+\b"
)


def safe_text(value: object, fallback: str, limit: int = 900) -> str:
    """Return a compact diagnostic with common credential forms redacted."""

    text = str(value or "").replace("\\r", " ").replace("\\n", "\n")
    text = _SENSITIVE.sub(r"\1=[redacted]", text)
    text = _LONG_SECRET.sub("[redacted]", text)
    text = " ".join(text.split())
    return (text or fallback)[:limit]


def can_attempt(attempts_used: int, failure: dict[str, Any], enabled: bool) -> bool:
    """Enforce the per-ticket ceiling in one testable policy function."""

    return (
        enabled
        and failure.get("eligible") is True
        and 0 <= attempts_used < MAX_RECOVERY_ATTEMPTS
    )


def should_use_terra_fallback(worker: str, return_code: int, used: bool) -> bool:
    """Allow one Terra fallback only for a failed primary Implementer call."""

    return worker == "implementer" and return_code != 0 and not used


def model_finding(output: str, fallback: str) -> str:
    """Extract only the bounded verdict neighborhood, never the raw model log."""

    normalized = output.replace("\\n", "\n").replace("\\r", "")
    match = re.search(
        r"VERDICT\s*:\s*(?:PASS|FAIL|APPROVE|REQUEST_CHANGES)\b.{0,700}",
        normalized,
        flags=re.IGNORECASE | re.DOTALL,
    )
    return safe_text(match.group(0) if match else "", fallback)


def _failure(
    failure_class: str,
    detail: str,
    required_action: str,
    *,
    eligible: bool,
) -> dict[str, Any]:
    return {
        "class": failure_class,
        "detail": safe_text(detail, "Ticket gate failed."),
        "required_action": safe_text(required_action, "Review the ticket evidence."),
        "eligible": eligible,
    }


def classify_implementer_fallback(
    primary_output: str,
    primary_rc: int,
    terra_output: str,
    terra_rc: int,
) -> dict[str, Any]:
    """Describe two provider failures without exposing either provider's raw output."""

    primary_text = primary_output.casefold()
    terra_text = terra_output.casefold()
    if any(marker in primary_text for marker in (
        "contextoverflowerror", "request too large", "tokens per minute",
    )):
        primary = "GPT-OSS exceeded the Groq request/context token limit."
    elif any(marker in primary_text for marker in ("rate_limit", "rate limit", "quota")):
        primary = "GPT-OSS was rate-limited by Groq."
    elif primary_rc == 124:
        primary = "GPT-OSS timed out."
    else:
        primary = f"GPT-OSS exited with code {primary_rc}."

    if terra_rc == 127:
        terra = "The secure runner could not locate the Codex executable, so Terra did not run."
        action = "Restart the updated dashboard launcher, then resume the preserved ticket."
        failure_class = "implementer_fallback_unavailable"
    elif terra_rc == 124:
        terra = "The Terra Medium fallback timed out."
        action = "Check Codex availability and resume the preserved ticket when capacity returns."
        failure_class = "implementer_fallback_failure"
    elif any(marker in terra_text for marker in ("usage limit", "rate limit", "quota")):
        terra = "The Terra Medium fallback reached its Codex usage limit."
        action = "Resume the preserved ticket after Codex capacity resets."
        failure_class = "implementer_fallback_failure"
    else:
        terra = f"The Terra Medium fallback exited with code {terra_rc}."
        action = "Inspect the bounded provider diagnostics before resuming the preserved ticket."
        failure_class = "implementer_fallback_failure"
    return _failure(
        failure_class,
        f"{primary} {terra}",
        action,
        eligible=False,
    )


def classify_validation(
    validation: dict[str, Any],
    implementer_rc: int,
    implementation_failure: dict[str, Any] | None = None,
) -> dict[str, Any]:
    scope = validation.get("scope") or {}
    violations = scope.get("violations") or []
    if violations:
        return _failure(
            "scope_violation",
            "Candidate changed protected or out-of-scope paths: " + ", ".join(map(str, violations)),
            "Review the ticket scope and candidate manually; autonomous repair is prohibited.",
            eligible=False,
        )

    static = validation.get("static") or {}
    security_checks = []
    failed_checks = []
    for check in static.get("checks") or []:
        if not isinstance(check, dict) or check.get("pass") is not False:
            continue
        name = str(check.get("name") or "unknown check")
        failed_checks.append(name)
        if name.startswith(("no_symlink:", "size:", "no_nul:")):
            security_checks.append(name)
    if security_checks:
        return _failure(
            "security_validation_failure",
            "Candidate failed a protected file-safety check: " + ", ".join(security_checks),
            "Inspect the affected repository-relative files before continuing.",
            eligible=False,
        )

    changed = scope.get("changed_paths") or []
    if implementer_rc == TERRA_FALLBACK_FAILURE:
        if implementation_failure:
            return implementation_failure
        return _failure(
            "implementer_fallback_failure",
            "Both the primary Implementer and its single Terra Medium fallback failed.",
            "Check Codex and Groq availability before starting another ticket.",
            eligible=False,
        )
    if implementer_rc != 0 and not changed:
        return _failure(
            "provider_or_worker_failure",
            f"Implementation worker exited with code {implementer_rc} and produced no candidate change.",
            "Check the configured worker provider and secure launcher before retrying.",
            eligible=False,
        )

    profile = validation.get("profile_result") or {}
    profile_failures = [
        str(name) for name, passed in (profile.get("checks") or {}).items() if not passed
    ]
    details = []
    if implementer_rc != 0:
        details.append(f"implementation exit code {implementer_rc}")
    if failed_checks:
        details.append("failed checks: " + ", ".join(failed_checks))
    if profile_failures:
        details.append("failed profile checks: " + ", ".join(profile_failures))
    if not changed:
        details.append("no repository change was produced")
    return _failure(
        "implementation_or_validation_failure",
        "; ".join(details) or "Candidate did not pass deterministic validation.",
        "Use one scoped repair attempt, then rerun every local gate.",
        eligible=True,
    )


def classify_tester(output: str, return_code: int) -> dict[str, Any]:
    if return_code != 0:
        return _failure(
            "tester_provider_failure",
            f"Independent tester exited with code {return_code} without a usable verdict.",
            "Check tester-provider availability; a code repair cannot resolve this failure.",
            eligible=False,
        )
    return _failure(
        "tester_change_request",
        model_finding(output, "Independent tester returned FAIL for the candidate."),
        "Plan one scoped correction from the tester finding and rerun all gates.",
        eligible=True,
    )


def classify_reviewer(
    output: str,
    return_code: int | None,
    *,
    requested_changes: bool,
) -> dict[str, Any]:
    if requested_changes:
        return _failure(
            "reviewer_change_request",
            model_finding(output, "Independent reviewer requested changes."),
            "Plan one scoped correction from the review and rerun all gates.",
            eligible=True,
        )
    return _failure(
        "reviewer_provider_failure",
        f"Review policy produced no approval (exit code {return_code}).",
        "Check reviewer-provider availability; do not reinterpret this as approval.",
        eligible=False,
    )


def hard_stop_for_exit(code: int) -> dict[str, Any]:
    if code == 2:
        return _failure(
            "repository_hygiene",
            "Local main is not clean, so no ticket worktree was created.",
            "Move, commit, or remove the unexpected local item, then enable automation again.",
            eligible=False,
        )
    if code == 6:
        return _failure(
            "missing_credentials",
            "Required worker credentials were unavailable to the secure ticket process.",
            "Restart the agent environment through the secure Windows launcher.",
            eligible=False,
        )
    return _failure(
        "ticket_precondition_failure",
        f"Ticket runner stopped during a required precondition (exit code {code}).",
        "Review repository, reference-package, and secure-launcher state before retrying.",
        eligible=False,
    )
