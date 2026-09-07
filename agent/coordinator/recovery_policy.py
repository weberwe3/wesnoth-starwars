#!/usr/bin/env python3

"""Secret-safe failure classification for bounded autonomous recovery."""

from __future__ import annotations

import re
from typing import Any


MAX_RECOVERY_ATTEMPTS = 2
WORKER_FALLBACK_FAILURE = 86
# Retained for result compatibility with previously persisted ticket records.
TERRA_FALLBACK_FAILURE = WORKER_FALLBACK_FAILURE
CODEX_WRITE_SANDBOX_UNAVAILABLE = 89
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


def should_use_luna_light_fallback(worker: str, return_code: int, used: bool) -> bool:
    """Allow one bounded Luna Light fallback for a failed model-worker call."""

    return worker in {"implementer", "fast-fix", "tester", "reviewer"} and return_code != 0 and not used


def should_use_terra_fallback(worker: str, return_code: int, used: bool) -> bool:
    """Compatibility alias for old callers and persisted-test imports."""

    return should_use_luna_light_fallback(worker, return_code, used)


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


def classify_worker_fallback(
    primary_output: str,
    primary_rc: int,
    fallback_output: str,
    fallback_rc: int,
    *,
    primary_label: str,
    fallback_label: str = "Luna Light",
) -> dict[str, Any]:
    """Describe a bounded worker primary/fallback failure without raw logs."""

    primary_text = primary_output.casefold()
    fallback_text = fallback_output.casefold()
    if any(marker in primary_text for marker in (
        "contextoverflowerror", "request too large", "tokens per minute",
    )):
        primary = f"{primary_label} exceeded its request/context token limit."
    elif any(marker in primary_text for marker in ("rate_limit", "rate limit", "quota", "usage limit")):
        primary = f"{primary_label} reached its provider usage limit."
    elif primary_rc == 124:
        primary = f"{primary_label} timed out."
    else:
        primary = f"{primary_label} exited with code {primary_rc}."

    if fallback_rc == 127:
        fallback = f"The secure runner could not locate Codex, so {fallback_label} did not run."
        action = "Restart the updated dashboard launcher, then resume the preserved ticket."
        failure_class = "implementer_fallback_unavailable"
    elif fallback_rc == CODEX_WRITE_SANDBOX_UNAVAILABLE:
        fallback = f"The {fallback_label} fallback was restricted to a read-only sandbox."
        action = (
            "Restart the updated dashboard launcher. If workspace-write remains unavailable, "
            "inspect the Codex host policy before resuming the preserved ticket."
        )
        failure_class = "implementer_fallback_unavailable"
    elif fallback_rc == 124:
        fallback = f"The {fallback_label} fallback timed out."
        action = "Check Codex availability and resume the preserved ticket when capacity returns."
        failure_class = "implementer_fallback_failure"
    elif any(marker in fallback_text for marker in ("usage limit", "rate limit", "quota")):
        fallback = f"The {fallback_label} fallback reached its Codex usage limit."
        action = "Resume the preserved ticket after Codex capacity resets."
        failure_class = "implementer_fallback_failure"
    else:
        fallback = f"The {fallback_label} fallback exited with code {fallback_rc}."
        action = "Inspect the bounded provider diagnostics before resuming the preserved ticket."
        failure_class = "implementer_fallback_failure"
    return _failure(
        failure_class,
        f"{primary} {fallback}",
        action,
        eligible=False,
    )


def classify_implementer_fallback(
    primary_output: str,
    primary_rc: int,
    fallback_output: str,
    fallback_rc: int,
    fallback_label: str = "Luna Light",
) -> dict[str, Any]:
    """Compatibility wrapper for existing implementer failure records."""

    return classify_worker_fallback(
        primary_output,
        primary_rc,
        fallback_output,
        fallback_rc,
        primary_label="Implementer",
        fallback_label=fallback_label,
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
    if implementer_rc == WORKER_FALLBACK_FAILURE:
        if implementation_failure:
            return implementation_failure
        return _failure(
            "implementer_fallback_failure",
            "Both the Terra Medium Implementer and its single Luna Light fallback failed.",
            "Check Codex availability before starting another ticket.",
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
    nested_profile_failures = []
    for name in ("declared_contracts", "historical_retention"):
        evidence = profile.get(name)
        if isinstance(evidence, dict) and evidence.get("pass") is False:
            diagnostic = safe_text(
                evidence.get("diagnostic"), f"{name} validation failed", 1000
            )
            nested_profile_failures.append(f"{name}: {diagnostic}")
    details = []
    if implementer_rc != 0:
        details.append(f"implementation exit code {implementer_rc}")
    if failed_checks:
        details.append("failed checks: " + ", ".join(failed_checks))
    if profile_failures:
        details.append("failed profile checks: " + ", ".join(profile_failures))
    details.extend(nested_profile_failures)
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


def classify_tester_fallback(
    primary_rc: int,
    luna_rc: int | None,
    primary_output: str = "",
    luna_output: str = "",
) -> dict[str, Any]:
    """Describe exhaustion of the independent tester provider chain."""

    def reason(label: str, code: int | None, output: str) -> str:
        if code is None:
            return f"{label} was not invoked."
        if code == 88:
            return f"{label} was skipped because its provider-failure circuit is open."
        if code == 127:
            return f"{label} was unavailable to the secure runner."
        if code == 124:
            return f"{label} timed out."
        if code == 0:
            return f"{label} returned no decisive PASS or FAIL verdict."
        folded = output.casefold()
        if any(marker in folded for marker in (
            "too many requests", '"statuscode":429', "daily free allocation",
            "rate limit", "rate_limit", "quota", "resource_exhausted",
        )):
            return f"{label} exhausted its provider quota or rate limit."
        return f"{label} exited with code {code}."

    return _failure(
        "tester_provider_failure",
        reason("Luna Medium tester", primary_rc, primary_output)
        + " " + reason("Luna Light tester fallback", luna_rc, luna_output),
        "Allow the autonomous worktree retry policy to re-evaluate provider availability.",
        eligible=False,
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
