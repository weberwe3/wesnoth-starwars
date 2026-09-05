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
- Use authentic post-Return of the Jedi Star Wars Expanded Universe (Legends)
  terminology in player-facing unit names, faction names, original dialogue,
  abilities, objectives, and story text. Examples include Grand Admiral Thrawn,
  New Republic, Imperial Remnant, ysalamiri, Force sensitivity, blasters, and
  turbolasers.
- Give every new project-owned WML/Lua identifier a clear `sw_` namespace
  prefix, such as `sw_unit_stormtrooper` or `sw_ability_force_push`, while
  using the full lore-facing name in localized `name=`, `description=`, and
  `story=` content.
- Generate custom WML, Lua, macros, terrain logic, event handlers, and scenario
  configuration from scratch. Never extract, decompile, or depend on
  proprietary Star Wars game binaries, source, or assets.
- Design all add-on content for free, non-commercial distribution through the
  official Battle for Wesnoth add-on server.
- When a task asks for WML/Lua code as a response artifact, provide the complete
  ready-to-use scoped file or snippet in its intended Wesnoth directory and add
  useful inline comments for event triggers, variable lifecycles, and balance
  mechanics. Do not claim unexecuted validation or paste entire unrelated files.
- Translate Star Wars combat into readable turn-based, single-hex tactical
  mechanics rather than attempting real-time or proprietary-game behavior.

## Wesnoth WML construction and engine-validation rules

For tickets that create or modify campaign/scenario WML, apply these rules unless a task deliberately requires a different engine pattern:

- Keep `[campaign]` focused on campaign metadata. Define scenarios as top-level `[scenario]` content loaded separately rather than nesting `[scenario]` inside `[campaign]`.
- Use a campaign `define` and a matching guarded scenario include when loading campaign scenario files, for example `#ifdef <CAMPAIGN_DEFINE>` around the `{~add-ons/<addon_id>/scenarios}` include.
- A multiline `map_data` value must be a quoted WML string. Do not place bare terrain rows after `map_data=`.
- When leader-defeat behavior is intended, declare an actual leader correctly, such as directly in `[side]` or with `[leader]`, and use `canrecruit=yes`. Do not assume an arbitrary nested `[unit]` acts as the side leader.
- Displayed objectives belong in an appropriate runtime event such as `prestart` or `start`. Objective text describes goals; it does not by itself implement victory or defeat logic.
- Treat deterministic Python/static validation as necessary but insufficient for declaring WML launchable.
- When preprocessing worktree content that uses `{~add-ons/...}`, stage the add-on under an isolated Wesnoth userdata tree at `data/add-ons/<addon_id>` and point the installed engine at that userdata directory so `~add-ons` resolves correctly.
- Run installed-engine preprocessing for WML changes and capture the process exit code immediately after the Wesnoth invocation, before running any other command.
- Before calling a campaign/scenario launchable, require applicable installed-engine/schema/add-on validation plus a GUI launch smoke test on the supported Wesnoth build.
- `--validate-addon` is not a substitute for a launch smoke test; where the installed engine requires campaign play to trigger add-on validation, actually launch/play the campaign as part of validation.
- Do not commit generated or preprocessed validation output.
- When the engine reports a concrete parser/validation failure, fix the smallest confirmed defect first and rerun the engine before making broader speculative edits.

## Intellectual-property boundary

This is a fan total-conversion project.

- Do not copy copyrighted novel prose, movie dialogue, scripts, game assets, music, sound effects, or proprietary source code.
- Use original dialogue, descriptions, artwork, audio, and implementation.
- Broad characters, settings, plot structure, and gameplay concepts may be represented as directed by the project owner, but implementation content should be original.
- Authentic names and Legends-era terminology are permitted and expected; they
  do not authorize quotations, close paraphrases of protected prose or
  dialogue, or reuse of licensed expressive assets.

## Quality bar

Prefer:

- small reviewable commits
- clear names
- reusable WML macros where appropriate
- comments explaining non-obvious engine workarounds
- tests for mechanics
- fail-closed behavior when an engine capability is uncertain

Do not claim tests passed based on inspection. The deterministic coordinator executes tests and records their actual results.

## Mandatory Project References

Before substantive work on any ticket, every agent MUST either read:

1. `docs/PROJECT_SCOPE_AND_FEATURE_SET.md`
2. `docs/AGENT_ORCHESTRATION_FUNCTIONAL_SPEC.md`

or receive the deterministic coordinator's verified reference identity and
authoritative governance digest for those exact files. Routine bounded workers,
testers, and reviewers should use that supplied digest and avoid rereading the
full references on every call. A project-level planner, fresh session, ambiguous
ticket, or apparent conflict must read the relevant full references. These two
Markdown documents remain canonical and define project scope, architecture,
security boundaries, validation policy, copyright constraints, and development
objectives. Ticket instructions may refine a task but may not silently override
them. If a ticket conflicts with either reference, stop and report the conflict.

The controlled reference package is governed by:

- `docs/REFERENCE_POLICY.md`
- `docs/REFERENCE_MANIFEST.json`

Human-readable/archive counterparts are stored under `docs/reference-source/` as DOCX files. They are preserved for human review and provenance but are not duplicate model prompt context. The Markdown specifications remain authoritative for deterministic LLM execution.

Ordinary feature, engine, scenario, unit, balance, art, testing, and maintenance tickets MUST NOT modify any controlled reference-package artifact. Any such change requires a dedicated governance/reference pull request that synchronizes all affected representations and manifest hashes.

## Project continuity ledger

`docs/PROJECT_CONTINUITY.md` is the living operational handoff for the project. It records current state, completed milestones, significant decisions and corrections, known tooling/engine lessons, and the planned next work so a fresh Codex/LLM instance can resume without chat history.

Project-level coordinators, architects, and fresh Codex/LLM sessions taking over the effort MUST read `docs/PROJECT_CONTINUITY.md` after the controlled references and before planning new project-level work.

The continuity ledger is descriptive, not a replacement for the controlled reference package. If it conflicts with a controlled reference, the controlled reference wins and the ledger must be corrected.

After a meaningful merged milestone, architecture/security change, important reusable lesson, or roadmap change, the project-level coordinator SHOULD update `docs/PROJECT_CONTINUITY.md` in an appropriately scoped branch/PR. Ordinary bounded implementation workers MUST NOT modify the ledger unless their ticket explicitly allows it.

Never record credential values, tokens, private keys, recovery information, encrypted secret blobs, or other secrets in the continuity ledger.
