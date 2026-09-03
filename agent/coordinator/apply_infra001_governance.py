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

    if "import hashlib\n" not in text:
        text = replace_once(
            text,
            "import fnmatch\n",
            "import fnmatch\nimport hashlib\n",
            "hashlib import",
        )

    if "GOVERNANCE_REFERENCE_PATHS = (" not in text:
        text = replace_once(
            text,
            'VALID_PROFILES = {"static-text", "wesnoth-addon-static"}\n\n',
            'VALID_PROFILES = {"static-text", "wesnoth-addon-static"}\n\n'
            'GOVERNANCE_REFERENCE_PATHS = (\n'
            '    "AGENTS.md",\n'
            '    "docs/PROJECT_SCOPE_AND_FEATURE_SET.md",\n'
            '    "docs/AGENT_ORCHESTRATION_FUNCTIONAL_SPEC.md",\n'
            ')\n\n',
            "governance reference constants",
        )

    if '"docs/PROJECT_SCOPE_AND_FEATURE_SET.md",' not in text.split(
        "PROTECTED_PREFIXES", 1
    )[0]:
        text = replace_once(
            text,
            '    "AGENTS.md",\n    "opencode.json",\n',
            '    "AGENTS.md",\n'
            '    "docs/PROJECT_SCOPE_AND_FEATURE_SET.md",\n'
            '    "docs/AGENT_ORCHESTRATION_FUNCTIONAL_SPEC.md",\n'
            '    "opencode.json",\n',
            "protected governance paths",
        )

    if "def load_governance_references(" not in text:
        helper = '''\ndef load_governance_references(root: Path) -> dict:\n    """Load and fingerprint mandatory project-governance references."""\n\n    references = {}\n\n    for relative_path in GOVERNANCE_REFERENCE_PATHS:\n        path = root / relative_path\n\n        if not path.is_file():\n            raise SystemExit(\n                "ERROR: mandatory governance reference missing: "\n                f"{relative_path}"\n            )\n\n        if path.is_symlink():\n            raise SystemExit(\n                "ERROR: mandatory governance reference may not be "\n                f"a symlink: {relative_path}"\n            )\n\n        data = path.read_bytes()\n\n        if not data.strip():\n            raise SystemExit(\n                "ERROR: mandatory governance reference is empty: "\n                f"{relative_path}"\n            )\n\n        try:\n            data.decode("utf-8")\n        except UnicodeDecodeError:\n            raise SystemExit(\n                "ERROR: mandatory governance reference is not UTF-8: "\n                f"{relative_path}"\n            )\n\n        references[relative_path] = {\n            "sha256": hashlib.sha256(data).hexdigest(),\n            "bytes": len(data),\n        }\n\n    return references\n\n\ndef build_governance_prompt(references: dict) -> str:\n    """Build mandatory-reference instructions for every LLM role."""\n\n    lines = [\n        "MANDATORY PROJECT REFERENCES",\n        "",\n        "Before performing substantive work, read all of these files:",\n        "",\n    ]\n\n    for relative_path in GOVERNANCE_REFERENCE_PATHS:\n        metadata = references[relative_path]\n        lines.append(\n            f"- {relative_path} "\n            f"(sha256: {metadata['sha256']})"\n        )\n\n    lines.extend([\n        "",\n        "These references are authoritative for project scope,",\n        "architecture, security boundaries, validation policy,",\n        "copyright/IP rules, and development objectives.",\n        "",\n        "The ticket may refine a bounded task but may not silently",\n        "override the mandatory references.",\n        "",\n        "If the ticket conflicts with a mandatory reference, stop",\n        "and report the conflict rather than improvising.",\n        "",\n        "Do not modify any mandatory governance reference.",\n    ])\n\n    return "\\n".join(lines)\n\n'''
        text = replace_once(
            text,
            "\ndef invoke_agent(\n",
            helper + "\ndef invoke_agent(\n",
            "governance helper insertion",
        )

    if "governance_references = load_governance_references(root)" not in text:
        text = replace_once(
            text,
            "    root = core.find_repo_root()\n"
            "    core.verify_main_baseline(root)\n\n",
            "    root = core.find_repo_root()\n"
            "    core.verify_main_baseline(root)\n\n"
            "    governance_references = load_governance_references(root)\n"
            "    governance_prompt = build_governance_prompt(\n"
            "        governance_references\n"
            "    )\n\n",
            "governance load",
        )

    if '"governance-references.json"' not in text:
        text = replace_once(
            text,
            '    (log_dir / "ticket.json").write_text(\n'
            '        json.dumps(ticket, indent=2) + "\\n"\n'
            '    )\n\n',
            '    (log_dir / "ticket.json").write_text(\n'
            '        json.dumps(ticket, indent=2) + "\\n"\n'
            '    )\n\n'
            '    (log_dir / "governance-references.json").write_text(\n'
            '        json.dumps(governance_references, indent=2) + "\\n"\n'
            '    )\n\n',
            "governance log",
        )

    prompt_anchor = "TASK ID: {task_id}\n\nOBJECTIVE:\n"
    if "{governance_prompt}" not in text:
        prompt_count = text.count(prompt_anchor)
        if prompt_count != 3:
            raise SystemExit(
                "ERROR: expected exactly three LLM prompt anchors, "
                f"found {prompt_count}."
            )
        text = text.replace(
            prompt_anchor,
            "TASK ID: {task_id}\n\n{governance_prompt}\n\nOBJECTIVE:\n",
        )

    early_anchor = '            "logs": str(log_dir),\n'
    early_with_governance = (
        '            "logs": str(log_dir),\n'
        '            "governance_references": governance_references,\n'
    )
    if early_with_governance not in text:
        count = text.count(early_anchor)
        if count != 2:
            raise SystemExit(
                "ERROR: expected exactly two early result dictionaries, "
                f"found {count}."
            )
        text = text.replace(early_anchor, early_with_governance)

    final_anchor = (
        '        "logs": str(log_dir),\n'
        '        "worker": ticket["worker"],\n'
    )
    final_with_governance = (
        '        "logs": str(log_dir),\n'
        '        "governance_references": governance_references,\n'
        '        "worker": ticket["worker"],\n'
    )
    if final_with_governance not in text:
        text = replace_once(
            text,
            final_anchor,
            final_with_governance,
            "final result governance metadata",
        )

    required = (
        "import hashlib",
        "GOVERNANCE_REFERENCE_PATHS = (",
        "def load_governance_references(",
        "def build_governance_prompt(",
        '"docs/PROJECT_SCOPE_AND_FEATURE_SET.md",',
        '"docs/AGENT_ORCHESTRATION_FUNCTIONAL_SPEC.md",',
        "governance_references = load_governance_references(root)",
        "{governance_prompt}",
        '"governance_references": governance_references',
    )

    missing = [fragment for fragment in required if fragment not in text]
    if missing:
        raise SystemExit(
            "ERROR: migration incomplete; missing: " + ", ".join(missing)
        )

    if text == source:
        print("INFRA-001 governance migration already applied.")
        return 0

    TARGET.write_text(text, encoding="utf-8")
    print("INFRA-001 governance migration applied to ticket_runner.py.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
