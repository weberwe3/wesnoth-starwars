#!/usr/bin/env python3

from __future__ import annotations

from pathlib import Path

import ticket_runner


def main() -> int:
    root = Path(__file__).resolve().parents[2]
    package = ticket_runner.load_reference_package(root)
    references = package["canonical_references"]

    assert len(references) == 3
    assert package["manifest"]["schema_version"] == 1
    assert len(package["manifest"]["sha256"]) == 64
    assert len(package["policy"]["sha256"]) == 64
    assert len(package["human_archives"]) == 2

    for path, metadata in references.items():
        assert len(metadata["sha256"]) == 64
        assert ticket_runner.is_protected(path)

    for path, metadata in package["human_archives"].items():
        assert len(metadata["sha256"]) == 64
        assert ticket_runner.is_protected(path)

    for path in package["controlled_paths"]:
        assert ticket_runner.is_protected(path), path

    prompt = ticket_runner.build_governance_prompt(package)
    normalized_prompt = " ".join(prompt.split())
    assert "docs/PROJECT_SCOPE_AND_FEATURE_SET.md" in prompt
    assert "docs/AGENT_ORCHESTRATION_FUNCTIONAL_SPEC.md" in prompt
    assert "DOCX files are human/archive counterparts" in normalized_prompt
    assert "not duplicate prompt context" in normalized_prompt
    assert "Expanded Universe (Legends) terms" in normalized_prompt
    assert "dialogue and story prose remain original" in normalized_prompt
    assert "WML/Lua IDs with sw_" in normalized_prompt
    assert "free non-commercial Wesnoth add-on distribution" in normalized_prompt
    assert "complete scoped Wesnoth-ready files or snippets" in normalized_prompt
    assert "one compact Sol call may refill a small ticket backlog" in normalized_prompt
    assert "without another planning call" in normalized_prompt

    print("Controlled files:", len(package["controlled_paths"]))
    print("Canonical LLM references:", len(references))
    print("Human DOCX archives:", len(package["human_archives"]))
    print("Manifest SHA-256:", package["manifest"]["sha256"])
    print("Reference package hashes: PASS")
    print("Protected paths: PASS")
    print("Canonical prompt behavior: PASS")
    print("INFRA-002 REFERENCE PACKAGE SELF-TEST: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
