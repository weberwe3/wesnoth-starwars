# Wesnoth Star Wars Project Continuity Ledger

**Purpose:** living project handoff, operational history, current-state summary, and forward plan<br>
**Repository:** `weberwe3/wesnoth-starwars`<br>
**Repository visibility at this snapshot:** public<br>
**Primary branch:** `main`<br>
**Last continuity refresh:** 2026-09-05 during DASH-021 tester resilience work<br>
**Main before this snapshot:** `9c0ce98f860cf50ffd79977a455333916bcb210f`<br>
**Active infrastructure ticket:** DASH-021 independent Terra Medium tester fallback<br>
**Next intended game-development ticket:** the first bounded playable scenario-skeleton increment

---

## 0. How to use this file

This document exists so that a fresh Codex/LLM instance, project coordinator, or human maintainer can resume the project without relying on chat history.

For a fresh project-level session, read sources in this order:

1. `AGENTS.md`
2. `docs/PROJECT_SCOPE_AND_FEATURE_SET.md`
3. `docs/AGENT_ORCHESTRATION_FUNCTIONAL_SPEC.md`
4. `docs/REFERENCE_POLICY.md`
5. `docs/REFERENCE_MANIFEST.json`
6. **this file, `docs/PROJECT_CONTINUITY.md`**
7. the current GitHub issue/PR for the task being resumed

The controlled reference package is authoritative. This continuity ledger is descriptive operational state. If this file conflicts with a controlled reference, the controlled reference wins and this file should be corrected in the next governance/continuity update.

Do not put credentials, token values, private keys, recovery codes, encrypted secret blobs, or secret environment-variable values in this file.

---

## 1. Executive resume block

### What this project is

A serious, original fan total conversion for Battle for Wesnoth, inspired by the broad post-Return of the Jedi setting and high-level plot concepts associated with Timothy Zahn's Thrawn trilogy. The intended end product is a three-campaign tactical game of roughly 25-30 missions with ground combat, heroes, squads, vehicles, off-map air support, and dedicated space scenarios.

### What has already been built

The project has:

- a GitHub repository with protected `main`;
- hardened OpenCode worker/reviewer definitions;
- a deterministic local Python coordinator and bounded ticket runner;
- isolated Git branches/worktrees per ticket;
- strict allowed-path and protected-path enforcement;
- static and Wesnoth-oriented deterministic validation;
- independent tester and reviewer gates;
- secure Windows-to-WSL credential forwarding backed by Windows DPAPI storage;
- a controlled reference package with Markdown canonical LLM references and two preserved DOCX human/archive counterparts;
- SHA-256 reference-package provenance;
- GitHub Actions deterministic CI with no model-provider secrets;
- an initial Wesnoth add-on root and textdomain registration from `ENGINE-001`;
- a registered `ENGINE-002` campaign and first scenario;
- a deterministic installed-engine preprocessing harness for that scenario.

### What should happen next

Scenario validation is complete. The next bounded game ticket should advance the playable scenario skeleton while retaining static and installed-engine checks appropriate to its scope.

Do not reopen the infrastructure/reference design unless a concrete defect or new requirement justifies it. The project is now ready to prioritize actual game development.

---

## 2. Source-of-truth hierarchy

### 2.1 Controlled project references

The mandatory controlled reference package is:

- `AGENTS.md`
- `docs/PROJECT_SCOPE_AND_FEATURE_SET.md`
- `docs/AGENT_ORCHESTRATION_FUNCTIONAL_SPEC.md`
- `docs/REFERENCE_POLICY.md`
- `docs/REFERENCE_MANIFEST.json`
- `docs/reference-source/Wesnoth_Project_Scope_and_Feature_Set.docx`
- `docs/reference-source/Wesnoth_Agent_Development_Functional_Specification.docx`

The two Markdown specifications are the canonical machine-readable runtime references for LLMs. The DOCX files are preserved human/archive counterparts and are intentionally not injected redundantly into prompts.

`docs/REFERENCE_MANIFEST.json` maps each Markdown specification to its DOCX counterpart and records SHA-256 and byte-length provenance.

### 2.2 Continuity ledger

`docs/PROJECT_CONTINUITY.md` is the living operational memory. It should track:

- current state;
- completed milestones;
- unresolved items;
- known lessons;
- current roadmap;
- important implementation decisions;
- resume instructions.

It should be updated after meaningful merged milestones, architecture/security changes, or roadmap changes.

---

## 3. Product vision and gameplay scope

### 3.1 Campaign plan

Planned trilogy:

1. **Campaign I — Heir to the Empire**
2. **Campaign II — Dark Force Rising**
3. **Campaign III — The Last Command**

Target total size: approximately **25-30 missions**.

Indicative production milestones:

- proof of concept: 3-5 missions;
- vertical slice: 6-8 missions;
- first complete campaign: about 10-12 missions;
- trilogy completion: about 25-30 missions;
- final balance, UX, compatibility, art, and audio polish afterward.

Earlier effort estimates used for planning:

- PoC 3-5 missions: roughly 60-120 agent-hours;
- vertical slice 6-8 missions: roughly 150-300 hours;
- first campaign 10-12 missions: roughly 350-650 hours;
- trilogy core production: roughly 900-1700 hours;
- additional polish: roughly 300-800 hours;
- broad total planning range: roughly 1200-2500 hours.

These are planning estimates, not commitments.

### 3.2 Tone and presentation

Target tone:

- serious;
- dark/painterly;
- military science-fiction;
- readable at Wesnoth tactical scale;
- not cartoonish;
- mechanically distinct from stock medieval Wesnoth rather than merely renamed fantasy units.

### 3.3 Copyright/IP boundary

The project may use broad characters, settings, relationships, and plot concepts as directed by the project owner, but must not copy protected expressive content.

Do not copy:

- Zahn novel prose;
- film/TV/game dialogue or scripts;
- proprietary art or game assets;
- copyrighted music or sound effects;
- proprietary source code.

All project dialogue, descriptive writing, implementation, art, audio, UI treatment, and mission scripting should be original.

### 3.4 Unit scale

Current representational decisions:

- major heroes and named characters: individual units;
- infantry: squad-level logical units;
- small/medium vehicles: oversized one-hex units where practical;
- AT-AT-scale walkers: oversized/scripted set pieces rather than true multi-hex occupancy;
- space fighters: squadron-level units in space scenarios;
- Millennium Falcon and similar narratively distinct craft: individual units;
- capital ships: oversized units or scenario/set-piece abstractions.

True multi-hex unit occupancy is intentionally avoided unless future Wesnoth engine capability makes it reliable enough for production.

### 3.5 Ground combat

Expected systems include:

- infantry squads;
- heroes/specialists;
- armored and transport vehicles;
- walkers/heavy set pieces;
- meaningful ranged distance bands;
- terrain/cover interaction;
- faction-specific tactical identities;
- objectives beyond simple elimination;
- reinforcements and scripted events;
- hero survival and narrative state where appropriate.

Wesnoth 1.19/1.20-generation native `min_range`/`max_range` may be used for enforcement, supplemented by WML/Lua when UI or AI behavior is incomplete.

### 3.6 Ground-air integration

Fast fighter/bomber support on ground maps should generally be **off-map sorties**, not normal persistent map units.

Examples:

- X-wing strike;
- TIE strike;
- bomber strike.

Slower or tactically persistent craft such as speeders/gunships may appear as on-map units when useful.

### 3.7 Space combat

Dedicated space scenarios should use a tactical abstraction distinct from ground combat, including:

- fighter/interceptor squadrons;
- bomber squadrons;
- named individual craft where narratively important;
- capital ships as large units or scenario structures/set pieces;
- escort, screening, interception, assault, survival, positioning, and timed objectives.

---

## 4. Engine and technical target

### 4.1 Wesnoth

Primary installed development target:

- Battle for Wesnoth **1.19.27** development generation;
- forward target: Wesnoth **1.20** generation.

Known Windows executable location:

`C:\Program Files (x86)\battle for wesnoth\wesnoth.exe`

Primary runtime scripting technologies:

- WML;
- Lua.

Python is for deterministic development orchestration, not gameplay runtime.

### 4.2 Engine capabilities/assumptions

Important current assumptions:

- native `min_range` / `max_range` exists in the targeted dev generation;
- full add-on GUI2 themes are available;
- `[defense]` ability support exists in the targeted generation;
- native range enforcement does not necessarily provide complete player UI or AI behavior;
- custom WML/Lua may therefore be needed for range visualization, targeting assistance, AI support, range-dependent modifiers, or special firing rules;
- prefer native engine behavior when reliable, understandable, and maintainable.

---

## 5. Current repository layout

Repository:

`weberwe3/wesnoth-starwars`

Local WSL project root:

`~/projects/wesnoth-starwars`

Canonical add-on root:

`addons/Star_Wars_Thrawn_Trilogy/`

Current initial add-on foundation includes:

- `README.md`
- `_main.cfg`
- `lua/README.md`
- `scenarios/README.md`
- `translations/README.md`
- `units/README.md`
- `utils/README.md`

Current `_main.cfg` intentionally contains only textdomain setup. Campaign/scenario/unit/Lua registrations have not yet been added; that starts with `ENGINE-002`.

---

## 6. Development architecture

### 6.1 Role split

Intended system roles:

- **ChatGPT/Sol** — project architect, coordinator, planning/review layer;
- **local deterministic Python coordinator** — authoritative executor of local checks and ticket orchestration;
- **free/low-cost hosted worker LLMs** — bounded implementation work in isolated branches/worktrees;
- **tester LLM** — independent inspection after deterministic gates;
- **reviewer LLM** — final independent model review;
- **reviewer fallback** — GPT-5.6 Luna Light only when the primary Nemotron reviewer is unavailable/non-decisive for infrastructure reasons.

Workers do not control `main`.

### 6.2 OpenCode

OpenCode version used during setup: **1.18.27**.

Binary:

`~/.opencode/bin/opencode`

Committed agent definitions:

- `.opencode/agents/coordinator.md`
- `.opencode/agents/implementer.md`
- `.opencode/agents/fast-fix.md`
- `.opencode/agents/tester.md`
- `.opencode/agents/reviewer.md`
- `.opencode/agents/reviewer-intermediate.md`
- `.opencode/agents/reviewer-fallback.md`

Workers are deny-by-default:

- no shell execution;
- no web use;
- no edits outside ticket scope;
- no nested agents;
- no direct commit/merge/push.

The deterministic coordinator, not the worker LLM, executes tests and records actual exit codes/output.

### 6.3 Provider routing snapshot

Routing used during the infrastructure baseline:

- implementer: `groq/openai/gpt-oss-120b`, with one `gpt-5.6-terra` medium fallback after primary Implementer process failure
- fast-fix: `opencode/ling-3.0-flash-fin-free`
- tester: `cloudflare-workers-ai/@cf/zai-org/glm-4.7-flash`
- primary reviewer: `cloudflare-workers-ai/@cf/nvidia/nemotron-3-120b-a12b`
- reviewer fallback: Codex `openai/gpt-5.6-luna` at low reasoning through the local Codex application

Observed behavior:

- Google reviewers are disabled in unattended routing because Gemini 3.6 repeatedly exhausted its 20-request project free-tier daily allowance and Gemini 3.8 also produced protocol and timeout failures;
- Luna Light follows Nemotron only for infrastructure/unavailability/non-decisive failures;
- model launches use published free-tier ceilings where universal values exist (Groq GPT-OSS 30 RPM, NVIDIA Nemotron 40 RPM, Cloudflare GLM 300 RPM), while account/project-specific quotas remain provider-managed;
- a provider/process/timeout/non-decisive failure suppresses that model for the next two worktree runs, while a valid negative verdict does not;
- a substantive `REQUEST_CHANGES` from any reviewer must not be bypassed by a later fallback.

Provider choices may change over time; the role boundaries and fail-closed policy matter more than a specific model name.

---

## 7. Secure host and credential architecture

Primary host: **KillDozer**.

Operating split:

- Windows host: Wesnoth executable, encrypted credential storage, secure launcher/shortcut;
- WSL Ubuntu 24.04: Git, Python, OpenCode, repository, coordinator, worktrees.

### 7.1 Credential policy

Secrets are stored on Windows using a DPAPI-backed encrypted store, not in WSL plaintext files.

Generic store location:

`%LOCALAPPDATA%\WesnothAgentManager\provider-secrets.json`

Secure launcher:

`%LOCALAPPDATA%\WesnothAgentManager\Start-WesnothAgentShell.ps1`

The launcher:

1. reads encrypted properties;
2. decrypts secrets in Windows process memory;
3. injects the environment variables for the launched process;
4. dynamically appends injected variable names to `WSLENV`;
5. launches WSL;
6. removes the injected Windows process variables after WSL exits.

No plaintext secret values should be persisted to:

- `.env`;
- `.bashrc`;
- `.profile`;
- Git;
- OpenCode auth files;
- ordinary temp files.

A RAM-backed `/dev/shm` temporary file is acceptable only when explicitly needed and carefully cleaned up.

### 7.2 Google environment alias

A non-secret alias/export may map the Gemini variable name to the provider-specific environment variable. Do not store the secret value itself.

### 7.3 GitHub authentication

GitHub authentication is process-scoped via the secure launcher. `GH_TOKEN` is forwarded dynamically by the launcher when present in the encrypted store.

Do not add a long-lived GitHub PAT to repository files or GitHub Actions secrets for this workflow.

---

## 8. Deterministic ticket pipeline

Core coordinator files:

- `agent/coordinator/coordinator.py`
- `agent/coordinator/ticket_runner.py`
- `agent/coordinator/reference_package.py`
- `agent/coordinator/reference_package_selftest.py`

### 8.1 Current ticket-runner behavior

A ticket run currently:

1. verifies the local main baseline;
2. validates the controlled reference package and fails closed on invalid references;
3. builds the mandatory governance/reference prompt block;
4. performs provider preflight;
5. creates an isolated `agent/<ticket>-<timestamp>` branch/worktree from local `main`;
6. invokes implementer or fast-fix worker;
7. runs deterministic validation;
8. invokes independent tester if deterministic validation passes;
9. invokes primary reviewer, or permitted fallback if primary is unavailable/non-decisive;
10. writes structured ticket evidence/results;
11. returns PASS/FAIL;
12. **does not automatically commit or merge**.

Project-level orchestration handles the later commit/push/PR/merge lifecycle after a successful ticket.

### 8.2 Deterministic evidence

Ticket evidence includes:

- original ticket JSON;
- governance-reference metadata;
- full controlled reference-package identity;
- model JSONL logs;
- deterministic validation JSON;
- result JSON;
- model exit codes and verdicts;
- reviewer used;
- final PASS/FAIL;
- explicit `commit_created` / `merge_performed` flags.

### 8.3 Reference-package enforcement

All model roles receive the same canonical reference instructions before substantive ticket content.

The coordinator validates:

- required package files exist;
- files are regular files, not symlinks;
- text references are UTF-8 and nonblank;
- manifest schema is supported;
- manifest IDs/paths match expected policy;
- canonical Markdown hashes/byte lengths match manifest;
- human/archive DOCX hashes/byte lengths match manifest.

Controlled reference paths are protected from ordinary feature-ticket modification.

---

## 9. GitHub governance and CI

### 9.1 Protected main

`main` is protected.

Verified branch-protection behavior includes:

- required status check: `repository-gates`;
- strict status checking/current branch requirement;
- admins are subject to protection;
- required approving review count: 0, appropriate for a one-person repo;
- conversation resolution required;
- linear history required;
- force pushes disabled;
- branch deletion disabled.

### 9.2 GitHub Actions

Workflow:

`.github/workflows/deterministic-ci.yml`

Workflow name:

`Deterministic CI`

Job/check context:

`repository-gates`

The workflow uses read-only repository permissions and does not receive model-provider credentials.

Current checks cover:

- controlled reference package presence;
- manifest schema and IDs;
- SHA-256 and byte-length provenance;
- UTF-8 requirements for canonical text references;
- coordinator Python compilation;
- controlled/protected path enforcement;
- canonical prompt construction;
- whitespace via `git diff --check`.

`actions/checkout@v5` is used to avoid the prior Node 20 deprecation warning seen with v4 on newer runners.

### 9.3 Intended steady-state lifecycle

For normal completed work:

1. create/confirm GitHub issue;
2. run local ticket in isolated worktree/branch;
3. pass deterministic local gates;
4. pass tester/reviewer gates;
5. commit successful branch;
6. push branch;
7. open PR to `main`;
8. run GitHub Actions;
9. resolve review threads/required policy;
10. merge only after exact-head green CI;
11. synchronize local `main`;
12. clean up completed branch/worktree when appropriate;
13. update this continuity ledger if the merge materially changes project state, architecture, roadmap, or completed milestones.

---

## 10. Completed development history

### 10.1 Hardened OpenCode baseline

Historical setup commits included:

- `248056b` — Establish hardened OpenCode agent baseline
- `cf5ccc1` — Add deterministic agent coordinator
- `007d6cd` — Ignore Python cache files
- `db0b41b` — Add resilient reviewer fallback
- `058c704` — Add bounded deterministic ticket runner
- `138a8db` — Strengthen Wesnoth add-on validation

Key result: worker execution was separated from deterministic validation, with deny-by-default worker permissions and independent tester/reviewer gates.

### 10.2 ENGINE-001 — initial Star Wars add-on foundation

Historical commit:

- `7ea7187` — Add initial Star Wars add-on foundation

Ticket instance:

`ENGINE-001-20260903-151259`

Created:

- add-on root;
- README;
- `_main.cfg`;
- placeholder/readme directories for Lua, scenarios, translations, units, and utils.

Correct initial `_main.cfg` textdomain setup:

```text
#textdomain wesnoth-Star_Wars_Thrawn_Trilogy

[textdomain]
    name="wesnoth-Star_Wars_Thrawn_Trilogy"
    path="data/add-ons/Star_Wars_Thrawn_Trilogy/translations"
[/textdomain]
```

Ticket outcome:

- implementer exit 0;
- deterministic validation PASS;
- tester PASS;
- Gemini primary reviewer timed out/unavailable;
- fallback reviewer APPROVE;
- final PASS.

Installed Wesnoth preprocessing of the early add-on foundation returned exit code 0.

### 10.3 Project reference documentation baseline

Historical commit:

- `943f1e4` — Add project scope and agent governance references

Created the canonical Markdown project scope and orchestration specifications later formalized by INFRA-001/002.

### 10.4 INFRA-001 — GitHub governance and mandatory LLM reference enforcement

GitHub issue:

- #1 `INFRA-001: GitHub governance and mandatory LLM reference enforcement`

PR:

- #2 `INFRA-001: GitHub governance and mandatory LLM references`

Final merge commit on `main`:

- `0c070ee86b2f42ab04fd877b3ac78225c6767648`

Accomplishments:

- established GitHub as remote governance/audit layer;
- made project references mandatory for implementer, fast-fix, tester, primary reviewer, and fallback reviewer;
- added SHA-256 reference fingerprints to ticket evidence/results;
- protected canonical governance files from ordinary tickets;
- added deterministic GitHub Actions CI;
- added PR governance template;
- documented GitHub development lifecycle;
- strengthened CI to explicitly test governance hashing, protection, and prompt construction;
- upgraded checkout action to v5;
- protected `main` with required `repository-gates`, linear history, conversation resolution, admin enforcement, no force push, and no deletion.

Important bug caught during INFRA-001:

The first migration helper loaded the two canonical docs as mandatory references but accidentally failed to add them to the protected-path set. The local governance self-test caught this because both docs returned `protected: False`. A follow-up fix added them to `PROTECTED_EXACT`, and CI was strengthened so this class of regression is now explicitly tested.

### 10.5 INFRA-002 — controlled reference package

GitHub issue:

- #3 `INFRA-002: Controlled reference package for LLM governance`

PR:

- #4 `INFRA-002: Controlled reference package`

Final merge commit on `main`:

- `102d962841b04b37f6b2eedfc8861d7a96299106`

Accomplishments:

- committed the two original Word specification files under `docs/reference-source/`;
- established Markdown as canonical LLM runtime format;
- established DOCX as synchronized human/archive format;
- created `REFERENCE_POLICY.md`;
- created `REFERENCE_MANIFEST.json` with SHA-256 and byte-length provenance;
- added deterministic `reference_package.py` validation;
- integrated reference-package validation into `ticket_runner.py`;
- added permanent `reference_package_selftest.py`;
- extended CI to validate manifest/package identity;
- protected all controlled reference-package paths;
- ensured package identity is recorded in ticket evidence/results;
- normalized DOCX Git file modes to `100644`;
- removed the one-time migration helper before merge.

Final local self-test output included:

- Controlled files: 7
- Canonical LLM references: 3
- Human DOCX archives: 2
- Reference package hashes: PASS
- Protected paths: PASS
- Canonical prompt behavior: PASS
- INFRA-002 REFERENCE PACKAGE SELF-TEST: PASS

---

## 11. Important lessons and corrections already learned

These should not be rediscovered from scratch.

### 11.1 Wesnoth validation

Do **not** use:

`wesnoth.exe --validate <_main.cfg>`

for a standalone early add-on `_main.cfg`; that is the wrong validation path.

For early add-on smoke/preprocessing, the verified pattern was equivalent to:

`wesnoth.exe --preprocess-defines=SKIP_CORE --preprocess <_main.cfg> <outdir>`

Once a real campaign/scenario exists, move toward scenario launch checks and `--validate-addon <addon_id>` or the engine-equivalent validation that is meaningful for the registered add-on.

A static pipeline PASS is **not** the same as engine validation.

### 11.2 OpenCode command behavior

Known command behavior:

- `opencode run --dir` is supported;
- `opencode agent list --dir` was not supported in the tested version.

### 11.3 Provider errors vs. code errors

Gemini reviewer hangs/timeouts were traced to provider quota/429 behavior in at least one case, not necessarily code failure.

Normal WSL sessions may appear to have missing providers because the secure credential launcher was not used. Verify secure environment forwarding before diagnosing a provider/model configuration problem.

### 11.4 Interactive shell safety

Do not leave persistent `set -e` enabled in an interactive WSL shell; a failing command can terminate the shell/session unexpectedly.

Capture command exit codes immediately when validation depends on them.

### 11.5 Worker permissions

Earlier permissive shell access (`bash: allow`) was treated as a security flaw. Workers are now intentionally denied shell execution. Keep deterministic execution in the coordinator.

### 11.6 GitHub connector/status

GitHub integration is connected and functional. Do not assume it is unavailable simply because a local `gh` operation is also possible.

### 11.7 DOCX file mode

Files copied from `/mnt/c` into WSL may inherit executable mode. The two reference DOCX files were initially committed as `100755`; this was corrected to `100644` before INFRA-002 merge. Future binary/document additions should be checked for accidental executable mode.

### 11.8 Migration-helper policy

One-time migration helpers are acceptable for controlled infrastructure migrations but should be removed before the final PR is merged unless they have clear ongoing value.

---

## 12. Known current limitations / deferred infrastructure

These are not blockers for ENGINE-002 unless the specific ticket exposes them.

- `ticket_runner.py` currently does not automatically retry a failed implementation attempt; retry handling exists as a concept but is not a completed general mechanism.
- OpenCode Web is a session UI, not the deterministic project dashboard.
- DASH-001 covers live ticket status, gates, routing, role/model assignments,
  and recent activity. DASH-002 added a narrowly scoped execution control:
  Python/manual coordination or a GPT-5.6 Sol low/medium/high planning pass may
  initiate exactly one schema-validated deterministic ticket. A dedicated
  governance change is now being prepared for an optional continuous scheduler,
  validated-local-commit approval queue, exact-commit publication action, and a
  separate Codex-routed approval gate for file deletions. These capabilities are
  proposed until their governance and implementation changes are reviewed and
  merged.
- `OPENCODE_SERVER_PASSWORD` hardening would matter if OpenCode Web is intentionally exposed/used.
- The exact model-provider mix can change; keep routing policy bounded and fail-closed.
- Installed-Wesnoth validation remains local rather than GitHub Actions because CI does not replace the local engine environment.

---

## 13. Current development status

### Infrastructure

**Ready / baseline complete:**

- secure local provider execution;
- hardened workers;
- deterministic coordinator;
- controlled reference package;
- GitHub issue/PR/CI lifecycle;
- protected main;
- reference provenance;
- continuity-ledger work initiated by INFRA-003.

**DASH-001 and DASH-002 merged; later dashboard controls remain in development:**

- a loopback-bound Agent Manager backend with same-origin protected,
  allowlisted coordinator controls and an optional paired private-LAN proxy;
- structured coordinator telemetry rather than log scraping;
- live role, provider, configured model, ticket, stage, elapsed-time, gate,
  routing/fallback, activity, error, and health views;
- a repository-owned Windows batch entry point that starts the dashboard and
  then delegates credential handling unchanged to the existing secure launcher;
- responsive, accessible control-console presentation with reduced-motion
  support and no external runtime dependencies.
- a bounded Sol handoff that uses read-only planning, strict JSON output,
  protected-path rejection, a native Windows run-ID bridge, the unchanged
  existing DPAPI launcher, and the existing deterministic ticket runner; each
  run stops before commit, push, or merge.

Proposed next dashboard-control work includes a repository-owned planned-ticket
picker and a continuous automation toggle. The continuous mode will schedule one
bounded ticket at a time, queue only validated local commits, require per-ticket
approval for the fixed push/PR/exact-head-CI/protected-merge pipeline, and pause
for a separate Codex-routed approval before any file deletion is committed.

The DPAPI-backed secure launcher remains unmodified. This preserves the rule
that feature work must not alter credential storage or credential-forwarding
logic. The new batch entry point composes with that launcher instead.

### Game

**Completed:**

- ENGINE-001 initial add-on/textdomain foundation.

**Not yet completed:**

- campaign registration;
- first actual scenario;
- scenario launch validation;
- unit roster/system implementation;
- range UX/AI additions;
- ground-air sortie system;
- space-combat systems;
- art/audio pipeline;
- campaign mission content beyond foundation.

---

## 14. Planned backlog / forward roadmap

### 14.1 Immediate confirmed next work

#### ENGINE-002 — minimal campaign and first launchable scenario

Purpose:

- register a minimal campaign in `_main.cfg`;
- create the first minimal scenario;
- make the add-on launchable enough to support real engine-backed validation;
- establish the path from structural foundation to playable scenario iteration.

Expected follow-on:

- scenario launch validation;
- stronger engine checks such as `--validate-addon` when applicable;
- automatic local preprocessing/engine gate in the coordinator where useful.

### 14.2 Near-term engine/game foundation sequence

After ENGINE-002, likely staged priorities are:

1. scenario launch/parse validation integrated into the deterministic workflow;
2. first playable scenario skeleton with objectives, sides, map, and victory/defeat flow;
3. baseline unit/faction data structures;
4. first representative infantry/hero/vehicle units;
5. ranged-combat proof of concept using native range support plus only the WML/Lua needed for UX/AI gaps;
6. first representative cover/defense mechanics;
7. initial mission scripting patterns/macros;
8. first small proof-of-concept mission set;
9. off-map air-support prototype;
10. space-scenario prototype;
11. vertical-slice integration and balance.

Exact ticket numbering/content should be created incrementally rather than treating this list as immutable.

### 14.3 Production progression

Broad progression remains:

- proof of concept 3-5 missions;
- vertical slice 6-8 missions;
- first complete campaign ~10-12 missions;
- expand to trilogy ~25-30 missions;
- dedicated balance/UX/compatibility/visual/audio polish.

---

## 15. Fresh Codex/LLM resume procedure

A completely fresh instance taking over this effort should do the following before changing code.

### Step 1 — establish authority and state

Read:

1. `AGENTS.md`
2. `docs/PROJECT_SCOPE_AND_FEATURE_SET.md`
3. `docs/AGENT_ORCHESTRATION_FUNCTIONAL_SPEC.md`
4. `docs/REFERENCE_POLICY.md`
5. `docs/REFERENCE_MANIFEST.json`
6. `docs/PROJECT_CONTINUITY.md`

### Step 2 — verify repository reality

Check:

- current `main` SHA;
- working tree clean state;
- current open GitHub issues/PRs;
- branch protection still active;
- latest `repository-gates` CI status;
- reference package self-test still passes if infrastructure/reference state is in question.

Do not trust this ledger's snapshot SHA if GitHub shows a newer merged state; update the ledger instead.

### Step 3 — verify secure execution environment before model/provider work

Confirm the shell was launched through the DPAPI-backed secure launcher and required provider environment variables are present **without printing their secret values**.

Do not diagnose provider availability from an ordinary WSL shell until secure-launcher state is confirmed.

### Step 4 — identify the active ticket

If no later ticket exists, the intended next game ticket is `ENGINE-002`.

If a later issue/PR exists, read it and reconcile it against the controlled references and this continuity ledger.

### Step 5 — preserve the workflow

For implementation:

- use bounded ticket scope;
- create isolated branch/worktree;
- inject mandatory references;
- let LLM worker modify only allowed paths;
- let deterministic coordinator execute checks;
- require tester/reviewer gates;
- push successful work to GitHub branch;
- open PR;
- require exact-head `repository-gates` PASS;
- merge only through protected `main` policy.

### Step 6 — update continuity after meaningful completion

After a meaningful milestone merge, update:

- current main SHA/snapshot;
- completed milestones;
- decisions/lessons;
- current status;
- next planned work;
- any changed provider/tool/engine assumptions.

Do not rewrite history to make it look cleaner than it was. Record meaningful corrections because they help future instances avoid repeating mistakes.

---

## 16. Continuity maintenance policy

Update this file when any of the following occurs:

- an `INFRA-*` milestone materially changes architecture, governance, security, references, CI, or orchestration;
- an `ENGINE-*` milestone materially changes the playable/engine foundation;
- a major gameplay system is added or its design changes;
- a provider/tool/engine assumption changes in a way that affects future work;
- an important bug or workflow failure teaches a reusable lesson;
- the roadmap or next-ticket priority changes;
- a full campaign/vertical-slice milestone is reached.

A small bounded implementation ticket that does not change the broader project state does not need a continuity update unless its completion changes the planned next action.

When updating this file:

- preserve controlled-reference precedence;
- record facts, not speculation, under completed/current-state sections;
- label future ideas as proposed/planned;
- never include secrets;
- prefer merge commit/PR/issue identifiers where they improve auditability;
- keep the fresh-instance resume procedure valid.

---

## 17. Chronological milestone ledger

| Date | Milestone | Result |
| --- | --- | --- |
| 2026-09-03 | Hardened OpenCode/coordinator baseline | Worker isolation, deterministic coordinator, tester/reviewer pipeline established |
| 2026-09-03 | ENGINE-001 | Initial add-on root and textdomain foundation completed; local Wesnoth preprocess smoke passed |
| 2026-09-03 | Project reference baseline | Project scope and orchestration specifications added |
| 2026-09-03 | INFRA-001 / PR #2 | GitHub governance, mandatory LLM references, hashing, protected paths, CI, branch protection merged |
| 2026-09-03 | INFRA-002 / PR #4 | Controlled Markdown/DOCX reference package, manifest provenance, package validator/self-test merged |
| 2026-09-03 | INFRA-003 / Issue #5 | Living project continuity ledger initiated; intended to become persistent handoff state |
| 2026-09-03 | DASH-001 / PR #9 | Local structured-telemetry Agent Manager dashboard and secure-launcher companion entry point merged |
| 2026-09-04 | DASH-002 / PR #16 | Coordinator mode control and one-ticket governed Sol handoff merged |
| 2026-09-04 | Continuous automation governance / PR #17 | Defined FIFO local-commit queue, exact-commit publication approval, activity/error presentation, and fail-closed deletion approval requirements |
| 2026-09-04 | DASH-004 / PR #18 | Autonomous scheduling toggle, planned-ticket picker, local approval queue, exact-commit publication pipeline, and deletion manifest gate merged |
| 2026-09-04 | Bounded error-recovery governance (proposed) | Permit no more than two scoped coordinator repair attempts for eligible implementation/gate errors; retain immediate hard stops for security, approval, repository hygiene, and publication failures |
| 2026-09-04 | Implementer provider fallback (proposed) | Keep GPT-OSS 120B primary and permit exactly one sandboxed GPT-5.6 Terra medium fallback after primary Implementer failure; failure of both providers hard-stops without consuming code-recovery attempts |
| 2026-09-04 | DASH-005 / PR #19 | Merged structured failure diagnostics, one Terra Medium Implementer fallback, open-work planning context, and a strict two-attempt Sol-planned/Fast-Fix recovery loop |
| 2026-09-04 | DASH-006 / PR #20 | Merged stale-dashboard restart, visible no-safe-ticket diagnostics, resume-first nonterminal worktrees, paired full-control private-LAN access, and safe-state dashboard/associated-console shutdown |
| 2026-09-04 | DASH-007 / PR #21 | Merged exact-head, contract-backed open-PR resumption with append-only main reconciliation, a fail-closed same-contract replacement path that preserves retired branches, and Gemini 3.8 Flash between Gemini 3.6 Flash and Nemotron in the reviewer fallback chain |
| 2026-09-04 | DASH-008 / PR #22 | Merged strict structured-output required-field repair, deterministic schema preflight, and bounded secret-free planner failure diagnostics |
| 2026-09-04 | DASH-009 / PR #23 | Merged bounded post-push GitHub head confirmation, duplicate queue-ownership prevention, and exact-record AI recode and non-destructive queue-removal controls |
| 2026-09-04 | DASH-010 / PR #25 | Merged continuous priority scheduling: the active Automation toggle authorizes fresh bounded tickets, skips queue/PR-owned priorities, advances through independent safe work, and sequences publication around exact-head CI registration/current-main checks while retaining manual publication/deletion gates |
| 2026-09-04 | DASH-011 / PR #26 | Merged live-state scheduling, publication/priorities context, and reviewer routing through Nemotron, Gemini 3.8 Flash, then Gemini 3.6 Flash |
| 2026-09-04 | DASH-012 / DASH-013 / PR #27 | Merged resilient active-run cancellation, preserved-remnant recovery, two bounded retries, deterministic remnant resumption, inventory-bound planning cache, compact prompts, Fast-Fix preference, and inter-ticket quota cooldown |
| 2026-09-04 | DASH-014 / PR #28 | Distinguish a clean pre-edit interrupted worktree from an invalid empty final result; reconcile clean unpublished remnants with current main; block unsafe paths, oversized scopes, conflicts, and dirty outdated bases without discarding work or spending a Sol planning call |
| 2026-09-04 | DASH-015 / PR #29 | Compute interrupted-ticket ownership from its merge base so newer `main` files are not misclassified as ticket remnants |
| 2026-09-04 | DASH-016 / PR #30 | Deterministically collapse equivalent empty retries to the newest worktree and prevent an older preserved blocker from hiding safe resumable work |
| 2026-09-04 | DASH-017 provider and scenario repair | Forward a verified Codex executable into the secure runner, report distinct provider/fallback failures, retire stale protected self-modification contracts without deleting evidence, enforce a smaller Groq read budget, and add bounded real-engine ENGINE-002 preprocessing evidence |
| 2026-09-04 | DASH-018 Codex resolver repair | Use one hardened Codex resolver for Sol planning and Terra fallback, including the verified per-user Windows installation when the secure WSL process intentionally has a stripped PATH |
| 2026-09-05 | DASH-019 model resilience | Pace model launches at published free-tier ceilings, persist a two-worktree-run circuit after provider failures, and add independent Terra Medium as the final reviewer fallback |
| 2026-09-05 | DASH-020 autonomous failure resolution | Prove and fast-forward dirty unfinished work when current-main changes are disjoint, supply installed-engine facts to bounded recovery, and retry a recoverable preserved worktree up to three consecutive autonomous runs before a detailed fail-closed pause |
| 2026-09-05 | DASH-021 tester resilience | Route unavailable or non-decisive GLM tester runs to one read-only Terra Medium fallback while prohibiting tester shopping and model self-testing/self-review |
| 2026-09-05 | DASH-022 through DASH-024 provider resilience | Extend slow tester execution time, canonicalize directory scopes, block Cloudflare after daily free-allocation exhaustion until its UTC reset, and use Luna Medium as the independent tester fallback |
| 2026-09-05 | DASH-025 stage-local model recovery | Remove unreliable Google free-tier reviewers from autonomous routing, use Luna Light after Nemotron, and resume unchanged failed candidates at Tester or Reviewer without replaying successful earlier stages |
| 2026-09-05 | DASH-026 exact recode selection | Bind Recode with AI directly to the selected failed queue ID, commit, branch, managed worktree, and recorded ticket contract instead of asking Sol to rediscover the already selected ticket |
| 2026-09-05 | DASH-027 queue governance controls | Add exact local stale-remnant deletion, cumulative dependency-batch publication, and automation-session-bound publication after a complete non-deleting local PASS |

---

## 18. Current handoff statement

At this snapshot, resume-state hardening is merged through PR #30. The subsequent scenario-validation attempt exposed three independent issues: GPT-OSS exceeded Groq's 8K request limit after requesting oversized source reads; the secure launcher did not expose the installed Codex executable to Terra; and the inherited ticket contract targeted protected coordinator paths that autonomous workers may never modify. DASH-017 addressed those infrastructure defects without weakening protection, but a real secure-run regression showed that launcher forwarding alone was not reliable across the nested Windows-to-WSL process boundary. DASH-018 makes Sol planning and Terra use the same hardened resolver and adds a bounded fallback lookup for the verified current user's Codex installation even when the secure process has an intentionally stripped PATH. DASH-019 adds free-tier-aware model launch pacing, a persistent two-worktree-run circuit for provider/process/timeout/non-decisive failures, and a final independent Terra Medium reviewer after Nemotron, Gemini 3.8 Flash, and Gemini 3.6 Flash. DASH-020 safely resumes disjoint dirty work and adds a three-run per-worktree failure ceiling. The next real failure showed GLM-4.7 Flash being correctly skipped by its provider circuit with code 88, but the tester stage had no independent fallback and exhausted the worktree limit without evaluating the candidate. DASH-021 adds one read-only Terra Medium tester fallback for unavailable or non-decisive GLM runs. A substantive GLM `FAIL` remains authoritative, Terra cannot test its own implementation, and a Terra tester cannot later act as the independent Terra reviewer. Security, scope, repository, reconciliation, deletion-approval, and publication boundaries still stop immediately. Exact-commit publication remains a manual boundary when automation is off; file-deletion approval always remains an explicit owner boundary.

A fresh Codex instance should not need historical chat transcripts to continue. The controlled references plus this ledger, current GitHub issues/PRs, and repository state should be sufficient to reconstruct the project's intent, operating model, completed work, constraints, and immediate next actions.

The current reviewer route is Nemotron followed immediately by a read-only GPT-5.6 Luna Light fallback. Gemini 3.6 Flash repeatedly exhausted the project's 20-request daily free allowance, while Gemini 3.8 Flash also produced protocol and timeout failures; neither Google model remains in unattended reviewer routing. Provider-only Tester or Reviewer failures now record the candidate-content digest and the first failed stage. A later resume may reuse earlier gate evidence only when that digest is unchanged; any candidate-content change invalidates the checkpoint and restores full validation.

The failed-ticket Recode control is an exact-record operation, not a general planning request. Its queue ID and commit are revalidated, its current worktree HEAD must still equal that commit, its original recorded contract and changed-path scope must remain safe, and reconciliation with current `main` must be provably non-destructive. Sol no longer selects a branch during recode; the selected worktree's Implementer performs the repair after Python has deterministically reconstructed the ticket. Open-PR recodes additionally require the PR to remain open at the exact recorded head.

DASH-027 requires its dedicated governance change to merge first. It binds standing publication authority to one live automation-toggle session and only records that authority after a non-deleting worktree completes all local gates. The controller then uses the same exact-commit push, PR, exact-head CI, protected merge, and local-main synchronization path as a manual approval. Cumulative queued dependencies are grouped only when stored predecessor identities and Git ancestry both verify; the final cumulative commit is the sole PR head. Failed or stale local remnants can be recoded, or deleted only through an exact confirmed action that refuses dirty, remote, PR-owned, mismatched, or still-dependent branches and retains audit evidence.
