# GitHub Development Workflow

This repository uses GitHub as the remote collaboration, review, CI, and audit layer while keeping LLM execution and authoritative installed-Wesnoth engine validation local on KillDozer.

## Flow

1. GitHub issue defines the bounded task.
2. The local deterministic coordinator creates an isolated `agent/<ticket>-<timestamp>` branch/worktree from `main`.
3. Every LLM role receives the mandatory governance references and their SHA-256 fingerprints.
4. The implementer performs only the ticket-scoped changes.
5. The coordinator enforces path scope, protected paths, static checks, and applicable Wesnoth validation.
6. Independent tester and reviewer gates run.
7. A local PASS makes the exact ticket commit eligible for GitHub publication; it does not merge anything.
8. The ticket branch is pushed and a pull request is opened against `main`.
9. GitHub Actions runs deterministic repository checks with read-only repository permissions and no model-provider credentials.
10. The pull request may merge only when local gates and GitHub gates pass for the exact head commit.
11. Local `main` is then synchronized and the completed worktree/branch is cleaned up.

## Mandatory references

Every substantive LLM role must operate from:

- `AGENTS.md`
- `docs/PROJECT_SCOPE_AND_FEATURE_SET.md`
- `docs/AGENT_ORCHESTRATION_FUNCTIONAL_SPEC.md`

The coordinator fails closed if these references are missing, empty, invalid UTF-8, or symlinks. Their SHA-256 values are recorded with ticket evidence.

Ordinary feature tickets may not modify these files. Governance changes require dedicated architecture/scope work and review.

## Security boundary

GitHub Actions must not receive Groq, Gemini, Cloudflare, NVIDIA, or other model-provider credentials. GitHub authentication for local publication is supplied ephemerally by the DPAPI-backed secure launcher rather than persisted in WSL configuration.

The workflow `GITHUB_TOKEN` is limited to `contents: read` unless a future job has a documented need for additional permission.

## CI

The deterministic CI workflow currently checks:

- mandatory governance references exist, are non-empty, and decode as UTF-8;
- coordinator Python compiles;
- governance references are hashed and protected by the runner;
- governance paths are injected into the model-context preamble;
- `git diff --check` passes for the pull-request diff.

Hosted CI does not replace local Wesnoth 1.19.27 validation. Engine-backed checks remain a local coordinator gate unless a deliberately version-matched hosted engine check is added later as supplemental evidence.

## Main branch policy

Steady-state policy is pull-request-only updates to `main`, required deterministic CI, resolved review conversations, no force pushes, no deletion, and linear history when supported by the repository plan and chosen merge strategy.
