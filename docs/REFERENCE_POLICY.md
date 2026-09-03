# Controlled Reference Package Policy

## Purpose

This policy defines how project reference documents are stored, consumed by LLM agents, validated, and changed.

## Controlled package

The controlled reference package consists of:

- `AGENTS.md`
- `docs/PROJECT_SCOPE_AND_FEATURE_SET.md`
- `docs/AGENT_ORCHESTRATION_FUNCTIONAL_SPEC.md`
- `docs/reference-source/Wesnoth_Project_Scope_and_Feature_Set.docx`
- `docs/reference-source/Wesnoth_Agent_Development_Functional_Specification.docx`
- `docs/REFERENCE_MANIFEST.json`
- `docs/REFERENCE_POLICY.md`

## Precedence and model consumption

The two Markdown specifications are the canonical machine-readable references for LLM execution:

1. `docs/PROJECT_SCOPE_AND_FEATURE_SET.md`
2. `docs/AGENT_ORCHESTRATION_FUNCTIONAL_SPEC.md`

Every substantive LLM role must read those canonical Markdown files, together with `AGENTS.md`, before acting on a ticket. The coordinator supplies their exact paths and hashes in the mandatory-reference prompt block.

The DOCX files are controlled human-readable/archive counterparts. They preserve the reviewed presentation documents and provenance, but they are **not** separately injected into model prompts. This avoids duplicate context and conflicting renderings of the same specification.

If a DOCX copy and its canonical Markdown counterpart ever disagree, development fails closed until a dedicated reference-governance change reconciles them. For runtime LLM behavior, the Markdown file remains authoritative because it is the deterministic, diffable representation validated by the coordinator and CI.

## Manifest

`docs/REFERENCE_MANIFEST.json` maps each canonical Markdown specification to its DOCX counterpart and records the expected SHA-256 digest and byte length of both files.

The manifest does not contain its own hash. The coordinator calculates and records the manifest SHA-256 at ticket runtime as part of the reference-package identity.

A valid reference package requires:

- all controlled files to exist;
- all controlled files to be regular files rather than symlinks;
- canonical Markdown, policy, manifest, and `AGENTS.md` to be nonempty UTF-8;
- the manifest schema and expected paths to match policy;
- every Markdown and DOCX SHA-256 and byte length to match the manifest;
- every controlled path to be protected from ordinary development tickets.

## Change control

Ordinary game, engine, scenario, unit, art, balance, testing, and maintenance tickets must not modify any controlled reference-package artifact.

A reference-package change requires a dedicated governance/reference branch and pull request. That change must deliberately update all affected representations and manifest values in the same PR. CI must pass for the exact PR head before merge.

Reference-governance changes should include a concise explanation of:

- why the reference changed;
- which canonical Markdown content changed;
- whether either DOCX counterpart changed;
- which manifest hashes changed; and
- whether the change alters project scope, architecture, security boundaries, validation policy, or development priorities.

## Ticket evidence

For every future ticket, the deterministic coordinator records a `reference_package` evidence object containing:

- the manifest SHA-256;
- the policy SHA-256;
- the `AGENTS.md` SHA-256;
- each canonical Markdown file's SHA-256 and byte length; and
- each DOCX counterpart's SHA-256 and byte length.

The same canonical Markdown hashes are included in the mandatory prompt block supplied to implementer/fast-fix, tester, primary reviewer, and fallback reviewer roles.

## Fail-closed rule

If the package is missing, malformed, inconsistent, hash-mismatched, unexpectedly symlinked, or otherwise unverifiable, the coordinator must stop before invoking any LLM worker. A ticket may not proceed using stale, partial, or inferred reference context.
