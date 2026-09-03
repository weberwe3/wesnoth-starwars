# INFRA-001 Implementation Notes

Issue: #1

This governance change establishes the project reference set and GitHub lifecycle before the next game-development ticket.

Completed on this branch:

- Canonical scope and feature-set reference added.
- Canonical agent-orchestration functional specification added.
- `AGENTS.md` updated to require both references.
- Deterministic GitHub Actions CI added with read-only repository permissions.
- Pull request template added.
- GitHub development lifecycle documented.

Still required before this change is ready to merge:

- Update the deterministic ticket runner so all LLM prompts explicitly reference the mandatory governance files.
- Record SHA-256 hashes of the mandatory governance references in every ticket result.
- Add the two canonical governance documents to deterministic protected-path enforcement.
- Validate the updated coordinator locally and through GitHub Actions.

The local coordinator remains responsible for provider calls and installed-Wesnoth validation. GitHub CI intentionally does not use external model-provider credentials.
