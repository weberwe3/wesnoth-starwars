#!/usr/bin/env python3

from __future__ import annotations

import hashlib
import json
from pathlib import Path


MANIFEST_PATH = "docs/REFERENCE_MANIFEST.json"
POLICY_PATH = "docs/REFERENCE_POLICY.md"
AGENTS_PATH = "AGENTS.md"

EXPECTED_REFERENCES = {
    "project_scope_and_feature_set": {
        "canonical_markdown": "docs/PROJECT_SCOPE_AND_FEATURE_SET.md",
        "human_archive": (
            "docs/reference-source/"
            "Wesnoth_Project_Scope_and_Feature_Set.docx"
        ),
    },
    "agent_orchestration_functional_spec": {
        "canonical_markdown": (
            "docs/AGENT_ORCHESTRATION_FUNCTIONAL_SPEC.md"
        ),
        "human_archive": (
            "docs/reference-source/"
            "Wesnoth_Agent_Development_Functional_Specification.docx"
        ),
    },
}

CANONICAL_LLM_REFERENCE_PATHS = (
    AGENTS_PATH,
    EXPECTED_REFERENCES["project_scope_and_feature_set"][
        "canonical_markdown"
    ],
    EXPECTED_REFERENCES["agent_orchestration_functional_spec"][
        "canonical_markdown"
    ],
)

HUMAN_ARCHIVE_PATHS = tuple(
    spec["human_archive"] for spec in EXPECTED_REFERENCES.values()
)

CONTROLLED_REFERENCE_PATHS = (
    AGENTS_PATH,
    POLICY_PATH,
    MANIFEST_PATH,
    *CANONICAL_LLM_REFERENCE_PATHS[1:],
    *HUMAN_ARCHIVE_PATHS,
)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _read_regular(root: Path, relative_path: str) -> bytes:
    path = root / relative_path

    if not path.is_file():
        raise SystemExit(
            f"ERROR: controlled reference missing: {relative_path}"
        )

    if path.is_symlink():
        raise SystemExit(
            "ERROR: controlled reference may not be a symlink: "
            f"{relative_path}"
        )

    data = path.read_bytes()

    if not data:
        raise SystemExit(
            f"ERROR: controlled reference is empty: {relative_path}"
        )

    return data


def _read_utf8(root: Path, relative_path: str) -> bytes:
    data = _read_regular(root, relative_path)

    if not data.strip():
        raise SystemExit(
            f"ERROR: controlled text reference is blank: {relative_path}"
        )

    try:
        data.decode("utf-8")
    except UnicodeDecodeError:
        raise SystemExit(
            "ERROR: controlled text reference is not UTF-8: "
            f"{relative_path}"
        )

    return data


def _metadata(data: bytes) -> dict:
    return {
        "sha256": _sha256(data),
        "bytes": len(data),
    }


def load_reference_package(root: Path) -> dict:
    """Validate and fingerprint the complete controlled reference package."""

    agents_data = _read_utf8(root, AGENTS_PATH)
    policy_data = _read_utf8(root, POLICY_PATH)
    manifest_data = _read_utf8(root, MANIFEST_PATH)

    try:
        manifest = json.loads(manifest_data.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(
            f"ERROR: invalid reference manifest JSON: {exc}"
        )

    if manifest.get("schema_version") != 1:
        raise SystemExit("ERROR: unsupported reference manifest schema.")

    if manifest.get("canonical_runtime_format") != "markdown":
        raise SystemExit(
            "ERROR: reference manifest runtime format must be markdown."
        )

    if manifest.get("human_archive_format") != "docx":
        raise SystemExit(
            "ERROR: reference manifest archive format must be docx."
        )

    records = manifest.get("references")
    if not isinstance(records, list):
        raise SystemExit("ERROR: reference manifest references must be a list.")

    by_id = {}
    for record in records:
        if not isinstance(record, dict):
            raise SystemExit("ERROR: invalid reference manifest record.")
        ref_id = record.get("id")
        if not isinstance(ref_id, str) or ref_id in by_id:
            raise SystemExit("ERROR: duplicate/invalid reference manifest id.")
        by_id[ref_id] = record

    if set(by_id) != set(EXPECTED_REFERENCES):
        raise SystemExit(
            "ERROR: reference manifest ids do not match controlled policy."
        )

    canonical_references = {
        AGENTS_PATH: _metadata(agents_data),
    }
    human_archives = {}

    for ref_id, expected in EXPECTED_REFERENCES.items():
        record = by_id[ref_id]

        if record.get("required_for_all_agents") is not True:
            raise SystemExit(
                f"ERROR: reference is not mandatory for agents: {ref_id}"
            )

        canonical_record = record.get("canonical_markdown")
        archive_record = record.get("human_archive")

        if not isinstance(canonical_record, dict):
            raise SystemExit(
                f"ERROR: missing canonical Markdown record: {ref_id}"
            )
        if not isinstance(archive_record, dict):
            raise SystemExit(
                f"ERROR: missing human archive record: {ref_id}"
            )

        canonical_path = expected["canonical_markdown"]
        archive_path = expected["human_archive"]

        if canonical_record.get("path") != canonical_path:
            raise SystemExit(
                f"ERROR: canonical path mismatch in manifest: {ref_id}"
            )
        if archive_record.get("path") != archive_path:
            raise SystemExit(
                f"ERROR: archive path mismatch in manifest: {ref_id}"
            )

        canonical_data = _read_utf8(root, canonical_path)
        archive_data = _read_regular(root, archive_path)

        canonical_meta = _metadata(canonical_data)
        archive_meta = _metadata(archive_data)

        if canonical_meta["sha256"] != canonical_record.get("sha256"):
            raise SystemExit(
                f"ERROR: canonical reference hash mismatch: {canonical_path}"
            )
        if canonical_meta["bytes"] != canonical_record.get("bytes"):
            raise SystemExit(
                "ERROR: canonical reference byte-length mismatch: "
                f"{canonical_path}"
            )
        if archive_meta["sha256"] != archive_record.get("sha256"):
            raise SystemExit(
                f"ERROR: human archive hash mismatch: {archive_path}"
            )
        if archive_meta["bytes"] != archive_record.get("bytes"):
            raise SystemExit(
                "ERROR: human archive byte-length mismatch: "
                f"{archive_path}"
            )

        canonical_references[canonical_path] = canonical_meta
        human_archives[archive_path] = archive_meta

    return {
        "schema_version": 1,
        "manifest": {
            "path": MANIFEST_PATH,
            "sha256": _sha256(manifest_data),
            "bytes": len(manifest_data),
            "schema_version": manifest["schema_version"],
        },
        "policy": {
            "path": POLICY_PATH,
            **_metadata(policy_data),
        },
        "canonical_references": canonical_references,
        "human_archives": human_archives,
        "controlled_paths": list(CONTROLLED_REFERENCE_PATHS),
    }


def build_governance_prompt(package: dict) -> str:
    """Build the canonical reference instructions supplied to every LLM."""

    references = package["canonical_references"]

    lines = [
        "MANDATORY PROJECT REFERENCES",
        "",
        "The deterministic coordinator verified these controlled files:",
        "",
    ]

    for relative_path in CANONICAL_LLM_REFERENCE_PATHS:
        metadata = references[relative_path]
        lines.append(
            f"- {relative_path} (sha256: {metadata['sha256']})"
        )

    lines.extend([
        "",
        "REFERENCE PACKAGE IDENTITY",
        "",
        f"- {package['manifest']['path']} "
        f"(sha256: {package['manifest']['sha256']})",
        f"- {package['policy']['path']} "
        f"(sha256: {package['policy']['sha256']})",
        "",
        "The two Markdown specifications are the canonical runtime",
        "references for LLM behavior. DOCX files are human/archive",
        "counterparts and are not duplicate prompt context.",
        "",
        "These references are authoritative for project scope,",
        "architecture, security boundaries, validation policy,",
        "copyright/IP rules, and development objectives.",
        "",
        "The ticket may refine a bounded task but may not silently",
        "override the controlled reference package.",
        "",
        "If the ticket conflicts with a controlled reference, stop",
        "and report the conflict rather than improvising.",
        "",
        "Do not modify any controlled reference-package artifact.",
        "",
        "AUTHORITATIVE GOVERNANCE DIGEST",
        "",
        "- Work only on the stated objective and allowed paths.",
        "- Preserve existing useful work; do not restart, reset, or discard it.",
        "- Never access secrets or environment values.",
        "- Never commit, push, merge, rewrite history, or alter governance.",
        "- Use original content and do not copy protected Star Wars expression or assets.",
        "- Use authentic post-ROTJ Expanded Universe (Legends) terms in player-facing content; dialogue and story prose remain original.",
        "- Prefix new project-owned WML/Lua IDs with sw_; use full lore names in localized player-facing fields.",
        "- Author WML/Lua and assets from scratch for free non-commercial Wesnoth add-on distribution; never extract proprietary game content.",
        "- When code is requested as output, provide complete scoped Wesnoth-ready files or snippets with useful mechanics comments.",
        "- Python owns execution, validation, retry ceilings, and publication gates.",
        "- Tester and reviewer roles are read-only and independent.",
        "",
        "For routine bounded work, this verified digest is the equivalent coordinator-supplied",
        "snapshot required by AGENTS.md; do not reread the full controlled references.",
        "Open a relevant controlled-reference section only if the ticket is ambiguous or",
        "appears to conflict with this digest, then stop and report an actual conflict.",
    ])

    return "\n".join(lines)
