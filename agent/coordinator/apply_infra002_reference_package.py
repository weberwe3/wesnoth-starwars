#!/usr/bin/env python3

from __future__ import annotations

from pathlib import Path


TARGET = Path(__file__).with_name("ticket_runner.py")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(
            f"ERROR: expected exactly one {label} anchor, found {count}."
        )
    return text.replace(old, new, 1)


def main() -> int:
    source = TARGET.read_text(encoding="utf-8")
    text = source

    if "import reference_package as reference_pkg\n" not in text:
        text = replace_once(
            text,
            "import coordinator as core\n",
            "import coordinator as core\n"
            "import reference_package as reference_pkg\n",
            "reference package import",
        )

    constants_start = text.find(
        'GOVERNANCE_REFERENCE_PATHS = (\n'
    )
    protected_prefix = text.find(
        'PROTECTED_PREFIXES = (\n'
    )

    if constants_start == -1 or protected_prefix == -1:
        raise SystemExit("ERROR: could not locate governance constants block.")

    constants_replacement = '''PROTECTED_EXACT = {
    ".gitignore",
    "opencode.json",
    "opencode.jsonc",
    *reference_pkg.CONTROLLED_REFERENCE_PATHS,
}

'''

    text = (
        text[:constants_start]
        + constants_replacement
        + text[protected_prefix:]
    )

    helpers_start = text.find(
        "def load_governance_references(root: Path) -> dict:\n"
    )
    invoke_start = text.find("def invoke_agent(\n")

    if helpers_start == -1 or invoke_start == -1:
        raise SystemExit("ERROR: could not locate governance helper block.")

    helpers_replacement = '''def load_reference_package(root: Path) -> dict:
    """Validate and fingerprint the controlled reference package."""

    return reference_pkg.load_reference_package(root)


def load_governance_references(root: Path) -> dict:
    """Backward-compatible canonical reference metadata accessor."""

    return load_reference_package(root)["canonical_references"]


def build_governance_prompt(package: dict) -> str:
    """Build mandatory controlled-reference instructions for every LLM."""

    return reference_pkg.build_governance_prompt(package)


'''

    text = (
        text[:helpers_start]
        + helpers_replacement
        + text[invoke_start:]
    )

    old_load = '''    governance_references = load_governance_references(root)
    governance_prompt = build_governance_prompt(
        governance_references
    )
'''
    new_load = '''    reference_package = load_reference_package(root)
    governance_references = reference_package["canonical_references"]
    governance_prompt = build_governance_prompt(reference_package)
'''

    text = replace_once(
        text,
        old_load,
        new_load,
        "ticket reference package load",
    )

    old_log = '''    (log_dir / "governance-references.json").write_text(
        json.dumps(governance_references, indent=2) + "\\n"
    )
'''
    new_log = '''    (log_dir / "governance-references.json").write_text(
        json.dumps(governance_references, indent=2) + "\\n"
    )

    (log_dir / "reference-package.json").write_text(
        json.dumps(reference_package, indent=2) + "\\n"
    )
'''

    text = replace_once(
        text,
        old_log,
        new_log,
        "reference package evidence log",
    )

    result_anchor = (
        '            "governance_references": governance_references,\n'
    )
    result_replacement = (
        '            "governance_references": governance_references,\n'
        '            "reference_package": reference_package,\n'
    )

    early_count = text.count(result_anchor)
    if early_count != 2:
        raise SystemExit(
            "ERROR: expected exactly two early result reference anchors, "
            f"found {early_count}."
        )
    text = text.replace(result_anchor, result_replacement)

    final_anchor = (
        '        "governance_references": governance_references,\n'
        '        "worker": ticket["worker"],\n'
    )
    final_replacement = (
        '        "governance_references": governance_references,\n'
        '        "reference_package": reference_package,\n'
        '        "worker": ticket["worker"],\n'
    )

    text = replace_once(
        text,
        final_anchor,
        final_replacement,
        "final result reference package evidence",
    )

    required = (
        "import reference_package as reference_pkg",
        "*reference_pkg.CONTROLLED_REFERENCE_PATHS",
        "def load_reference_package(root: Path)",
        "return reference_pkg.load_reference_package(root)",
        "return reference_pkg.build_governance_prompt(package)",
        'reference_package = load_reference_package(root)',
        'reference_package["canonical_references"]',
        '"reference-package.json"',
        '"reference_package": reference_package',
    )

    missing = [fragment for fragment in required if fragment not in text]
    if missing:
        raise SystemExit(
            "ERROR: INFRA-002 migration incomplete; missing: "
            + ", ".join(missing)
        )

    TARGET.write_text(text, encoding="utf-8")
    print("INFRA-002 reference package migration applied to ticket_runner.py.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
