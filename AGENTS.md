# Wesnoth Star Wars Project Rules

This repository is an AI-assisted Battle for Wesnoth total-conversion project.

## Safety and Git rules

- Never merge directly into `main`.
- Never push directly to `main`.
- Never force-push.
- Never rewrite published Git history.
- Never delete branches or worktrees unless explicitly instructed by the coordinator.
- Never modify files outside the assigned task scope unless required to make the assigned task work.
- Never expose, print, log, commit, or persist API keys, tokens, credentials, or environment-variable values.
- Never create `.env` files containing secrets.
- Never modify Windows credential storage or the secure launcher.
- Do not commit generated logs, temporary files, caches, or credentials.

## Work model

Each implementation task should occur on an isolated branch/worktree.

Before changing code:

1. Inspect the relevant files.
2. State the intended change briefly.
3. Keep the change bounded to the assigned task.
4. Preserve existing behavior unless the task explicitly requires changing it.

After changing code:

1. Do not execute tests or shell commands.
2. Report which tests the deterministic coordinator should run.
3. Do not commit, merge, or push.
4. Report the files changed, implementation summary, assumptions, known issues,
   and tests needed.

The deterministic coordinator, not an LLM worker, executes tests and records
their real exit codes and output.

## Wesnoth requirements

- Target the Wesnoth 1.19/1.20-generation engine unless a task states otherwise.
- Prefer native WML/Lua/Wesnoth functionality over unnecessary external dependencies.
- Avoid assumptions that a normal Wesnoth unit occupies more than one logical hex.
- Keep game logic separate from art/content where practical.
- Favor deterministic, testable mechanics.
- Keep campaign-specific content from unnecessarily coupling core mechanics.

## Intellectual-property boundary

This is a fan total-conversion project.

- Do not copy copyrighted novel prose, movie dialogue, scripts, game assets, music, sound effects, or proprietary source code.
- Use original dialogue, descriptions, artwork, audio, and implementation.
- Broad characters, settings, plot structure, and gameplay concepts may be represented as directed by the project owner, but implementation content should be original.

## Quality bar

Prefer:

- small reviewable commits
- clear names
- reusable WML macros where appropriate
- comments explaining non-obvious engine workarounds
- tests for mechanics
- fail-closed behavior when an engine capability is uncertain

Do not claim tests passed based on inspection. The deterministic coordinator executes tests and records their actual results.
