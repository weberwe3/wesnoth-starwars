# GitHub Development Workflow

GitHub is the remote system of record for the project. The local deterministic coordinator remains the authority for LLM execution, worktree isolation, trusted validation, installed-Wesnoth engine checks, and provider credential handling.

## Canonical lifecycle

1. Create or select a GitHub Issue for the bounded task.
2. Run the task through the local coordinator in an isolated branch/worktree.
3. Require all LLM roles to follow `AGENTS.md`, `docs/PROJECT_SCOPE_AND_FEATURE_SET.md`, and `docs/AGENT_ORCHESTRATION_FUNCTIONAL_SPEC.md`.
4. Run deterministic local validation and the applicable Wesnoth engine gate.
5. Run the independent tester and reviewer gates.
6. Only after a local PASS, create a commit on the ticket branch and push the branch to GitHub.
7. Open a Pull Request targeting `main` and link the Issue.
8. Require deterministic GitHub Actions checks to pass.
9. Review the PR and resolve required changes.
10. Merge through GitHub. Do not directly push feature work to `main`.
11. Synchronize the local `main` branch and clean obsolete ticket worktrees/branches.

## Responsibility split

### Local secure coordinator

- Creates isolated worktrees and ticket branches.
- Calls implementer, fast-fix, tester, primary reviewer, and fallback reviewer models.
- Keeps provider and GitHub credentials process-scoped through the Windows DPAPI-backed launcher.
- Runs trusted deterministic validation.
- Runs installed Wesnoth validation where applicable.
- Fails closed on missing evidence or failed gates.

### GitHub

- Stores the canonical published Git history.
- Tracks Issues and Pull Requests.
- Runs deterministic CI that needs no external model-provider credentials.
- Preserves review and merge history.
- Serves as the collaboration and audit layer around the local coordinator.

## Governance references

The following files are mandatory project references:

- `AGENTS.md`
- `docs/PROJECT_SCOPE_AND_FEATURE_SET.md`
- `docs/AGENT_ORCHESTRATION_FUNCTIONAL_SPEC.md`

Ordinary feature tickets must not modify these files. Governance changes should be isolated in dedicated infrastructure/governance work and reviewed separately.

## Secret-handling rule

Do not commit provider credentials, GitHub credentials, plaintext environment files containing credentials, or local credential-store material. GitHub Actions must remain independent of model-provider credentials unless a future governance change explicitly establishes a reviewed secret-management design.
