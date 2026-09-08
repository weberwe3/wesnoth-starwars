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

### 2026-09-08 — a syntactically valid map token was not an engine terrain

- **Symptom:** Mission 1 was marked Published and Tested, but the player launcher stopped while loading the level with `Unknown tile in map: (Gg^Ff) 'Gg^Ff'`.
- **Cause:** PR #160 introduced `Gg^Ff`. The deterministic map gate checked only the shape and length of each token, so an unregistered code passed. The GUI smoke launched only the campaign selector path, counted a still-running process as success, and did not force a difficulty, scenario, or story skip; it therefore never proved that the map was instantiated.
- **Resolution:** Preserve PR #160's map layout while replacing `Gg^Ff` with the supported forest overlay `Gg^Fp`. Validate every map cell against the add-on's target-engine-approved terrain registry. Direct the installed-engine probe to the exact scenario and difficulty, skip story screens, force file logging, and explicitly treat unknown-tile diagnostics as fatal.
- **Prevention:** A well-shaped terrain code is not sufficient evidence that Wesnoth knows it. New terrain codes must first load in the supported installed engine, then be added deliberately to the approved registry. Publication cannot claim scenario coverage from a process-survival probe that did not target the scenario.

### 2026-09-08 — separately confirmed art sets shared one WML source

- **Symptom:** Several complete owner-generated unit-art sets were shown as failed, even though every PNG passed import preflight and their animation references were present.
- **Cause:** The governed importer treated each card as a one-unit commit. When multiple ready units legitimately edited the same `units/infantry.cfg`, the sibling art files and shared WML edit were rejected as unrelated dirty state.
- **Resolution:** Build one bounded batch from only independently verified pending art jobs that share the selected WML source, then validate, commit, exact-head CI-check, merge, and installed-engine test that batch once. Missing art remains an awaiting-art state rather than a failed production attempt.
- **Prevention:** Do not publish a shared-source art import one card at a time. Batch only same-source, full 13-state contracts; never include incomplete, unrelated, or already-published art.

### 2026-09-07 — GUI map error was hidden by process-survival validation

- **Symptom:** The published ticket was marked tested, but the Windows play launcher showed `The game map could not be loaded` and identified `center` as a terrain token.
- **Cause:** The runtime probe treated a still-running Wesnoth GUI process as success and inspected only the primary log stream. A modal map error can leave that process alive, while the launcher’s persistent userdata can retain an older add-on copy.
- **Resolution:** Validate every quoted `map_data` cell before engine launch, treat the map-parser wording as fatal, inspect both Wesnoth log streams, and make the play launcher refresh the add-on from a clean protected-main checkout before starting the campaign.
- **Prevention:** A map token longer than four characters or outside the short terrain/overlay form fails deterministic validation; the launcher refuses a dirty/non-main source and limits stale-file removal to the campaign add-on directory.

### 2026-09-07 — declared project visual resources were absent from the add-on

- **Symptom:** Unit WML referenced add-on `images/units/...` and `images/portraits/...` paths that did not exist in the repository. The engine could continue past a missing visual in some configurations, producing a misleadingly successful loader check or invisible/default presentation.
- **Cause:** Prototype WML retained project-owned placeholder paths without committing original matching assets. The previous deterministic checks validated map and unit registration but not the resource graph.
- **Resolution:** Preserve project-owned paths and generate small original procedural PNG placeholders inside those exact paths. The generator never downloads or copies external art; it runs only for missing `.png` references beneath `images/` and records the created files as normal candidate changes.
- **Prevention:** Campaign dependency validation now blocks missing or unsafe project resources, broken scenario routes, duplicate scenario IDs, missing project macros/Lua actions, and custom terrain loaded after scenarios. Audio, non-PNG visuals, and unsafe paths are not fabricated; they stop for an explicit, scoped original-content repair.

### 2026-09-07 — unit art must be a complete state contract, not a lone sprite

- **Symptom:** A unit could receive a single placeholder image or a standing sprite, yet have no coherent move, attack, defense, death, or portrait art ready for a real tactical implementation.
- **Cause:** A headless worktree was incorrectly treated as if it could directly invoke Codex's interactive image-generation capability, or as if producing every existing unit's art at once were safe for an owner's quota.
- **Resolution:** Changed units create one bounded, interactive-Codex-only art job with 13 exact state assets and a dashboard-copyable `$imagegen` brief. Pending art is explicit; a completed job must contain every valid PNG and wire all paths into the unit WML.
- **Prevention:** Do not call an image API, read a credential, fabricate visual content beyond the narrow procedural fallback, or generate a project-wide art batch. Generate original art one unit at a time; preserve character consistency across its states and do not copy official, cover, film, actor, logo, or public-reference compositions.

### 2026-09-07 — local add-on gate omitted current declared gameplay contracts

- **Symptom:** A recoded map ticket passed local deterministic validation, tester, and reviewer, then exact-head CI rejected moved reinforcement coordinates that no longer matched their declared event-unit contract.
- **Cause:** The local `wesnoth-addon-static` profile checked syntax and historical published retention but did not run `validate_declared_contracts`; CI did, so a current candidate could consume model and publication resources before the mismatch was detected.
- **Resolution:** Run the complete declared-contract set inside local add-on validation and include its bounded evidence in the profile result before tester or reviewer dispatch.
- **Prevention:** A regression forces local validation to fail when syntax and historical retention pass but a declared gameplay contract does not; coordinate-changing tickets must update every affected event-unit expectation in their allowed contract file.

### 2026-09-07 — recovery worker received only a generic contract failure

- **Symptom:** The new local declared-contract gate correctly stopped a stale coordinate, but both bounded AI repair attempts made no correction and the worktree retry counter advanced.
- **Cause:** Failure classification inspected only the add-on validator's top-level check map. It omitted the nested declared-contract diagnostic, so the recovery worker was told only that deterministic validation failed.
- **Resolution:** Include bounded diagnostics from failed declared-contract and historical-retention evidence in the coordinator's corrective handoff.
- **Prevention:** Regression coverage requires the exact safe contract diagnostic to reach recovery classification; verbose process output and secrets remain excluded.

### 2026-09-07 — recovery prompt prohibited the inspection it required

- **Symptom:** Luna received the exact stale-coordinate diagnostic but returned blocked twice without editing because the prompt required inspection while prohibiting commands.
- **Cause:** The workspace-write recovery prompt inherited a blanket “do not execute commands” sentence even though candidate contents are intentionally not embedded and Codex must use bounded read-only commands to inspect them.
- **Resolution:** Explicitly allow bounded read-only file inspection and in-scope patching for all write workers while continuing to prohibit tests, package managers, network operations, and Git writes.
- **Prevention:** The shared write-worker command policy is regression-checked and used by both primary implementation and recovery/fallback prompts so their permissions cannot drift.

### 2026-09-07 — recode branch disappeared after repository branch count exceeded 100

- **Symptom:** Recode with AI claimed an exact failed-ticket pull request was no longer open, and re-enabling automation paused with a yellow no-safe-ticket warning even though the PR, commit, branch, and managed worktree still existed.
- **Cause:** The planning inventory silently indexed only the first 100 local `agent/*` refs. Once the repository exceeded that count, newer PR branches had no local-head entry and were excluded from both resumable and replaceable candidates. Normal automation also did not deterministically adopt an eligible failed publication record for recode.
- **Resolution:** Index the complete local agent-ref set up to an explicit 1,000-branch safety bound, fail clearly above that bound, and make continuous automation select the oldest non-deleting failed publication for exact-record recode before new planning.
- **Prevention:** Regression coverage forbids the former 100-ref slice and verifies that toggle-driven recovery selects the earliest eligible failed record while preserving manual approval for deletion-bearing failures.

### 2026-09-07 — blocked planner launched a guaranteed-conflicting backlog call

- **Symptom:** The dashboard remained in generic Planning for several minutes after Sol had already identified an open PR and failed queue record owning the requested Mission 1 files.
- **Cause:** In continuous mode, every `stop` response unconditionally launched a second backlog-generation call. Its proposals overlapped the same authoritative ownership and Python rejected all of them.
- **Resolution:** Honor the first bounded planner's stop. Generate a backlog only through the existing deterministic exhausted-priority path, and display that distinct bounded phase when it is genuinely needed.
- **Prevention:** Regression coverage requires a stop with pending/owned work to make no refill call; legitimate backlog generation must publish an explicit up-to-five-minute phase instead of appearing motionless.

### 2026-09-07 — non-game deployment caused a full Wesnoth launch sweep

- **Symptom:** Enabling automation after a dashboard-only merge visibly started and stopped Wesnoth once for the campaign and once for every registered scenario.
- **Cause:** Historical gameplay evidence was keyed only to the complete `main` commit, so every descendant commit invalidated it even when neither add-on content nor its gameplay validators changed.
- **Resolution:** Carry a passing record forward only across a verified descendant range whose changed paths exclude the add-on and both authoritative gameplay-validation modules; record the bounded equivalence trail.
- **Prevention:** Regression tests require dashboard-only changes to invoke no engine or retention check, while any add-on, scenario-probe, or gameplay-contract validator change must run both real historical gates.

### 2026-09-07 — batch publication interrupted during game testing

- **Symptom:** Restarting during a merged batch's engine check could label its earlier members as unpublished failures.
- **Cause:** Only the final cumulative ticket received merge evidence before testing; other members waited for the test to finish.
- **Resolution:** Atomically persist the confirmed merge and subsequent test outcome to every exact-ID/exact-commit batch member.
- **Prevention:** Restart regression tests must preserve every member's merge identity without inferring test success; reject changed member identities without partial updates.

### 2026-09-07 — stale historical repairs and premature publication success

- **Symptom:** Historical repair tickets repeatedly failed with no repository changes even after newer main revisions passed game checks. The approval queue showed only Published, without distinguishing a completed engine test from a failed or interrupted test.
- **Cause:** The planner reused a pending historical failure without comparing its recorded main head to current main. Publication never refreshed that historical record. Separately, the post-publish writer emitted schema 2 while the repair reader accepted only schema 1, so newer repair evidence could be ignored. Queue publication success was recorded before the engine result.
- **Resolution:** Bind historical evidence to the checked main revision and refresh both installed-game and retention evidence after publication. Accept the supported post-publish schema versions. Record Published and Tested only after the relevant installed-game checks pass; retain the merge with an orange Published / Test failed state on failure or interruption, including for every member of a cumulative batch. Infrastructure failures stop for host recovery rather than inventing a game-code defect.
- **Prevention:** Exercise successful, failed, interrupted, and changed-head publication tests. A historical repair that produces no change must recheck the current game and history before retrying. Retire only an exact clean managed branch at the verified main head when both checks pass; preserve its worktree and failed-run evidence, record an already-resolved outcome separately, and invalidate that retirement if its branch head or working files change. Ordinary empty candidates still fail, and no missing test becomes an inferred PASS.

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

### 2026-09-07 — Windows Codex auth was not selected from WSL

- **Symptom:** Terra and Luna both returned a Codex `401 Unauthorized` before model execution; the fallback circuit then suppressed both routes.
- **Cause:** The secure bridge launched the Windows Codex executable from WSL without an explicit `CODEX_HOME`, so the CLI could not select the existing Windows profile authentication store while user-config loading was disabled.
- **Resolution:** Forward the existing `%USERPROFILE%\\.codex` directory through `CODEX_HOME/p` from the launcher and bridge, and derive the same profile path defensively in Python for planning, recovery, Terra, and Luna subprocesses. No credential file is copied or logged.
- **Prevention:** The bridge fails clearly when the existing auth store is absent; regression tests require the selector to survive credential stripping and WSL path translation without exposing provider values.

### 2026-09-07 — map prose was mistaken for a harmless comment

- **Symptom:** Mission 1 passed the deterministic map-token check and an earlier publication test, but manual play stopped with “a terrain with a string with more than 4 characters” for `center`.
- **Cause:** A `#`-prefixed descriptive header was added to the external `.map` file. The validator skipped such lines as if the file were WML, while Wesnoth parsed the words in that file as terrain tokens.
- **Resolution:** Remove the prose header and reject every comment line in external `map_data` sources before publication.
- **Prevention:** Keep external map files terrain rows only. The map-data regression fixture places a hash-prefixed `center` line in an included map and requires deterministic validation to fail.

### 2026-09-07 — custom units were included without Wesnoth registration

- **Symptom:** Mission 1's map opened after a ticket was marked Published and Tested, but every commander and squad was absent. The normal campaign log reported `unknown unit type` for all scenario unit instances.
- **Cause:** `_main.cfg` included raw unit files outside the selected campaign loader. Wesnoth requires custom units to be included in `[+units]` within the active campaign's matching `#ifdef`; raw top-level includes do not register those types for scenario construction.
- **Resolution:** Put the add-on unit directory in `[+units]` before the scenario include, within each campaign loader, and declare the add-on binary path there.
- **Prevention:** The campaign-loader gate validates every campaign define, binary path, `[+units]` loader order, scenario include, and referenced `sw_unit_*` definition before worker review or publication. The normal player launcher log remains authoritative for loader diagnostics.

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

### 2026-09-07 — historical scenario identity renamed during an AI recode

- **Symptom:** A recoded historical gameplay ticket passed its original local add-on checks but exact-head CI rejected it because published commit c61c0dc41821 no longer retained 01_First_Battle.
- **Cause:** The repair renamed an established scenario id and its campaign first_scenario target to apply the newer sw_ naming convention. That treated a published compatibility contract as a new identifier and did not run historical-retention validation locally.
- **Resolution:** Preserve established published WML identifiers and campaign targets; the sw_ convention applies to newly introduced project-owned identifiers. wesnoth-addon-static local validation now runs the same historical-retention check required by CI before a candidate reaches review or publication.
- **Prevention:** Do not rename a gameplay id, first_scenario, or other published compatibility symbol for style alone. Require local historical-retention PASS for every add-on candidate.
