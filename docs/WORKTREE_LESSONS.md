# Worktree Failure and Resolution Register

This compact register is mandatory practical guidance for every planner, implementer, tester, reviewer, and recovery LLM. Read it with `AGENTS.md` before editing or validating a ticket. It supplements, but never overrides, the controlled project references.

## Update rule

When a deterministic, installed-engine, or worktree validation failure is diagnosed and then repaired:

1. Reproduce or preserve the bounded diagnostic without secrets or generated logs.
2. Fix the smallest confirmed cause and rerun the affected deterministic or engine check.
3. Before the repaired ticket is queued or published, add one concise entry below with: symptom, coding/design cause, resolution, and the prevention check.
4. Do not add speculative causes, credentials, raw provider output, or unrelated history. If the cause remains unknown, preserve the ticket and report it rather than writing a false lesson.

Keep entries short and reusable. Newer entries may supersede earlier ones; do not remove history merely to make a prompt smaller.

## Verified lessons

### 2026-09-07 — secure bridge accepted a ticket but never ran it

- **Symptom:** Autonomous dispatch ended as `secure_bridge_failure` with “did not return a valid result” despite a fresh bridge heartbeat.
- **Cause:** The Windows credential launcher starts a login shell for normal interactive use. Login Bash does not load `BASH_ENV`, so the bridge’s generated, allowlisted bootstrap never ran and could not produce its structured result.
- **Resolution:** When—and only when—the inherited bootstrap matches the strict per-run managed-runtime path, the launcher invokes that script directly. All normal manual launches retain their interactive login shell.
- **Prevention:** The bridge must distinguish “heartbeat online” from “bootstrap executed”; retain the result-file gate and report bootstrap failures as secure-bridge infrastructure, never as a model or ticket failure.

### 2026-09-07 — bridge bootstrap could not find OpenCode

- **Symptom:** After the bootstrap execution repair, a ticket stopped immediately with `OpenCode unavailable` before a worktree or ticket log was created.
- **Cause:** The secure bootstrap correctly runs in a non-login shell, but the prior OpenCode discovery relied on `/home/willj/.profile` adding its binary directory to `PATH`.
- **Resolution:** Resolve OpenCode through `PATH` when available, then through the verified executable at the current user's `.opencode/bin/opencode` path. Refuse non-executable or symlink candidates.
- **Prevention:** Secure runner dependencies must be resolved explicitly in Python, not implicitly through interactive/login shell startup files.

### 2026-09-06 — empty scenario after apparently successful startup

- **Symptom:** First Battle opened on a small empty map and immediately ended. The installed engine log reported `error engine/team_construction: game_error: unknown unit type` for the scenario leader and squads.
- **Cause:** The add-on registered custom `[unit_type]` definitions only inside campaign-specific preprocessor guards. The campaign could load its scenario path while the engine constructed its sides without the required custom unit registry. The former log filter also matched `error engine:` but missed the engine's actual subsystem form, `error engine/team_construction:`.
- **Resolution:** Load project unit definitions before campaign-specific scenario guards. Treat `engine/<subsystem>` errors, `game_error`, and `unknown unit type` as fatal. Run each affected scenario through an isolated temporary campaign using the installed Windows Wesnoth executable; require it to remain alive without fatal engine diagnostics.
- **Prevention:** For every gameplay ticket, run the staged runtime probe for each changed scenario and every scenario when a shared unit file changes. A successful preprocess or a process that merely remains open is never enough without inspecting the engine log.

### 2026-09-06 — gameplay-contract coverage

- **Symptom:** A campaign could preprocess and reach its opening map while a newly added event, unit, or objective still lacked a deterministic check of its intended effect.
- **Cause:** Startup smoke testing proves loadability, not that a ticket's gameplay outcome remains present after later edits.
- **Resolution:** Every changed add-on WML/Lua source now requires a passing entry in `addons/Star_Wars_Thrawn_Trilogy/tests/gameplay-contracts.json`; protected-main validation combines the installed-engine staged preprocess/startup probe with those contracts. Existing published add-on tickets are swept once in first-parent publication order for retained files and WML identifiers before new autonomous planning resumes.
- **Prevention:** For each gameplay source touched, add a compact `source-id` or `event-unit` contract in the same ticket. Never claim a feature is tested merely because Wesnoth launches.

### 2026-09-06 — staged campaign load failure

- **Symptom:** Wesnoth rejected `01_first_battle.cfg` with WML parser errors, then later reported a missing macro and an invalid closing tag during campaign loading.
- **Cause:** Several prototype shortcuts were not valid WML or engine data: compact `[message]` text, a command embedded in a unit `[ability]`, legacy `Ff` terrain, scenario transition IDs without their `sw_` prefixes, and scenario inclusion before its reusable macro definition. Removing a bad objective also left an orphan opening tag.
- **Resolution:** Use normal `[message]` key/value fields; move air support to a scenario `[set_menu_item]` with recognized `[set_variable]` and `[harm_unit]` actions; replace terrain with `Gg^Fp`; match `next_scenario` to exact IDs; include utility macros before scenarios; and verify each edited WML block has balanced tags.
- **Prevention:** Run `PYTHONPATH=agent/coordinator python3 agent/coordinator/scenario_launch_selftest.py --engine` for add-on changes. Protected-main publication also runs an isolated campaign-startup probe; it must pass before normal autonomous backlog work resumes.

### 2026-09-06 — execution-sandbox helper failure

- **Symptom:** Every command was rejected with an execution-sandbox helper setup/refresh error.
- **Cause:** The host execution environment was unhealthy; it was not a Wesnoth, Git, model, credential, or code failure.
- **Resolution:** Stop modifying code, restore the execution environment, then resume with `git status`, `git diff --check`, relevant Python tests, and the installed-engine probe.
- **Prevention:** Treat a uniform command-launch failure as infrastructure first. Do not burn model calls, rotate credentials, or record a code-repair lesson until the command channel is healthy.

### 2026-09-06 — dashboard/bridge worktree-root mismatch

- **Symptom:** Autonomous coordination stopped before ticket work began because the selected worktree was outside the managed root after a dashboard restart.
- **Cause:** A direct WSL dashboard restart omitted `WESNOTH_AGENT_WORKTREE_ROOT`, so it used the legacy Linux root while the Windows-launched secure bridge retained the native Windows-backed root.
- **Resolution:** `agent/dashboard/start-dashboard.sh` now defaults to the supported Windows-backed root when no launcher value was inherited. The inherited launcher value remains authoritative and the existing exact-branch migration still preserves legacy work safely.
- **Prevention:** Before autonomous dispatch, dashboard and bridge must use `/mnt/c/Users/<Windows user>/Documents/Codex/WesnothAgentWorktrees`; never weaken the managed-root guard or accept an arbitrary worktree path.
