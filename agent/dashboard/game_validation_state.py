"""Shared, bounded evidence for the historical gameplay repair lifecycle."""

from __future__ import annotations

from gameplay_contracts import validation_digest
from recovery_policy import safe_text


HISTORICAL_GAMEPLAY_VALIDATION_FILE = "historical-gameplay-validation.json"
GAMEPLAY_VALIDATOR_PATHS = {
    "agent/coordinator/gameplay_contracts.py",
    "agent/coordinator/scenario_launch_selftest.py",
}


def gameplay_revalidation_required(changed_paths: list[str]) -> bool:
    """Return true only when a revision can change installed-game evidence."""

    return any(
        path == "addons/Star_Wars_Thrawn_Trilogy"
        or path.startswith("addons/Star_Wars_Thrawn_Trilogy/")
        or path in GAMEPLAY_VALIDATOR_PATHS
        for path in changed_paths
    )


def carried_forward_record(record: dict, main_head: str, changed_paths: list[str], at: str) -> dict:
    """Bind still-valid evidence to a descendant with no game-relevant changes."""

    previous_head = record["main_head"]
    updated = dict(record)
    updated["main_head"] = main_head
    updated["validated_main_head"] = record.get("validated_main_head", previous_head)
    history = list(record.get("equivalent_revision_history") or [])[-19:]
    history.append({
        "from_main_head": previous_head,
        "to_main_head": main_head,
        "carried_forward_at": at,
        "non_game_changed_paths": changed_paths[:50],
    })
    updated["equivalent_revision_history"] = history
    return updated


def historical_record(main_head: str, engine: dict, retained: dict, checked_at: str) -> dict:
    """Bind both real checks to the same main revision; never reuse an old failure."""

    return {
        "schema_version": 1,
        "state": "passed" if engine.get("pass") is True and retained.get("pass") is True else "pending_repair",
        "main_head": main_head,
        "checked_at": checked_at,
        "evidence_digest": validation_digest({"engine": engine, "retention": retained}),
        "evidence": {
            "engine_pass": engine.get("pass") is True,
            "engine_failure_class": engine.get("failure_class"),
            "engine_exit_code": engine.get("exit_code"),
            "retention_pass": retained.get("pass") is True,
            "ticket_count": len(retained.get("tickets") or []),
            "diagnostic": safe_text("\n".join(filter(None, [
                str(engine.get("diagnostic") or ""),
                str(retained.get("diagnostic") or ""),
            ])), fallback="No diagnostic was returned by the validation checks.", limit=6000),
            "diagnostic_paths": sorted({
                path for path in list(engine.get("diagnostic_paths") or [])
                + list(retained.get("diagnostic_paths") or [])
                if isinstance(path, str) and path.startswith("addons/Star_Wars_Thrawn_Trilogy/")
                and ".." not in path.split("/")
            })[:20],
        },
    }
