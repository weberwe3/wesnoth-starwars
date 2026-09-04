# Wesnoth Star Wars Agent Development System - Functional Specification

**Status:** Living architecture and operating specification<br>
**Baseline date:** 2026-09-03<br>
**Repository:** `wesnoth-starwars`<br>
**Primary host:** KillDozer (Windows + WSL Ubuntu 24.04)

## 1. Purpose

This specification defines the architecture, control flow, tools, security boundaries, validation rules, source-control model, LLM roles, and operating requirements for developing the Wesnoth Star Wars total conversion.

This document is normative for development-process behavior. If an implementation ticket, model response, or ad-hoc instruction conflicts with this specification, the deterministic coordinator and repository protections should fail closed until the conflict is intentionally resolved.

## 2. Architectural Principles

The development system follows these principles:

1. **Deterministic orchestration controls nondeterministic workers.** LLMs perform bounded creative/coding work; Python and Git enforce workflow state.
2. **No LLM owns `main`.** Workers cannot directly merge or make authoritative repository decisions.
3. **Least privilege.** Agents receive only the tools and paths required for their role.
4. **Fail closed.** Missing credentials, scope violations, validator failures, reviewer ambiguity, or infrastructure errors do not become implicit approval.
5. **Independent verification.** Implementation, testing, deterministic validation, and review are distinct stages.
6. **Secrets stay out of the repository and WSL persistence.** Provider credentials are decrypted on Windows and forwarded ephemerally.
7. **Every substantive change is traceable.** Tickets, logs, Git branches, commits, pull requests, and CI results form an audit chain.
8. **Engine-backed checks outrank model confidence.** A model saying WML is valid is not sufficient when Wesnoth can test the relevant behavior.
9. **Project references are mandatory context.** All agents must operate from the same feature/scope and architecture references.

## 3. System Components

### 3.1 ChatGPT / Sol - architect and coordinator-of-record

Responsibilities:

- maintain high-level architecture and project direction;
- define bounded tickets;
- choose validation expectations;
- interpret failures;
- design changes to deterministic tooling;
- review major architectural decisions;
- maintain the project reference documents;
- avoid acting as an uncontrolled direct code merger.

ChatGPT is not the runtime authority for local filesystem state. Local Git, coordinator logs, engine results, and GitHub are authoritative for actual execution state.

### 3.2 Deterministic Python coordinator

Primary files currently include:

- `agent/coordinator/coordinator.py`
- `agent/coordinator/ticket_runner.py`

Responsibilities:

- validate ticket schema;
- verify provider preconditions;
- require a clean base state;
- create ticket branch/worktree isolation;
- invoke the assigned LLM worker;
- enforce changed-path scope;
- enforce protected paths;
- run deterministic validators;
- invoke tester and reviewer stages;
- control reviewer fallback rules;
- record structured logs/results;
- refuse implicit commit/merge;
- eventually publish approved results into the GitHub PR workflow.

The coordinator is the workflow state machine. Model output is input to that state machine, not a substitute for it.

### 3.3 OpenCode

Installed local CLI version baseline: **1.18.27**.

Binary:

`/home/willj/.opencode/bin/opencode`

OpenCode provides the model-agent execution layer. It is used to run the hardened project agents and may also expose an interactive web interface. The OpenCode Web UI is an interactive model session interface; it is not the authoritative ticket dashboard for the deterministic coordinator.

A purpose-built Wesnoth Agent Manager dashboard visualizes coordinator state, ticket history, gates, diffs, retries, PR status, and merge readiness. Its Python server remains bound to loopback; a separately constrained Windows proxy may expose paired access on the private LAN.

### 3.4 Battle for Wesnoth

Installed Windows executable baseline:

`C:\Program Files (x86)\battle for wesnoth\wesnoth.exe`

Verified version:

**Battle for Wesnoth 1.19.27 x86_64**

Wesnoth is the authoritative parser/runtime for game-facing WML behavior. Engine checks should be selected appropriately:

- `--preprocess` for preprocessing/parse smoke checks of isolated WML/add-on content;
- `--validate-addon` when the add-on has sufficient campaign/scenario content for meaningful validation;
- direct scenario launch/smoke tests once scenarios are registered;
- do not use `--validate <_main.cfg>` as a standalone add-on validity test because that mode validates against the complete game configuration schema and produces false negatives for minimal add-on roots.

### 3.5 Git

Git is the local source-of-truth mechanism for code history and isolation.

Authoritative branch:

`main`

Ticket branches:

`agent/<ticket-id-lowercase>-<timestamp>`

Ticket worktrees are created outside the main worktree, under:

`~/projects/wesnoth-starwars-worktrees/`

Workers operate only inside their assigned worktree.

### 3.6 GitHub

GitHub is the remote system of record for collaboration, pull requests, protected-branch enforcement, CI status, and durable review/audit history.

GitHub does not replace local deterministic validation. It adds a second policy boundary and remote evidence trail.

Target workflow:

- private repository initially unless the project owner chooses public publication;
- `origin` remote points to GitHub;
- `main` protected with a ruleset or branch protection;
- PR required before merge;
- required status checks;
- conversation resolution required;
- linear history preferred;
- force pushes and branch deletion to `main` blocked;
- bypass minimized;
- GitHub Actions `GITHUB_TOKEN` granted least privilege;
- no provider API secrets needed in GitHub CI unless a future workflow has a compelling reason.

### 3.7 Windows secure credential store and launcher

Provider credentials are stored encrypted with Windows DPAPI at:

`C:\Users\willj\AppData\Local\WesnothAgentManager\provider-secrets.json`

Generic location:

`%LOCALAPPDATA%\WesnothAgentManager\provider-secrets.json`

Secure launcher:

`%LOCALAPPDATA%\WesnothAgentManager\Start-WesnothAgentShell.ps1`

The launcher:

1. decrypts credentials into the Windows process environment;
2. appends approved variable names to `WSLENV`;
3. launches Ubuntu/WSL project shell;
4. makes credentials available only in process memory;
5. cleans the Windows process environment after handoff.

Secrets must not be written to `.env`, `.bashrc`, `.profile`, Git, task logs, OpenCode auth files, or temporary plaintext files.

## 4. Provider Configuration

Configured provider environment variables currently include:

- `GEMINI_API_KEY`
- `GROQ_API_KEY`
- `NVIDIA_API_KEY`
- `MISTRAL_API_KEY`
- `CLOUDFLARE_ACCOUNT_ID`
- `CLOUDFLARE_API_KEY`
- `CEREBRAS_API_KEY`
- `HF_TOKEN`

Google alias in `~/.profile`:

`GOOGLE_GENERATIVE_AI_API_KEY="${GOOGLE_GENERATIVE_AI_API_KEY:-$GEMINI_API_KEY}"`

The alias contains no secret value at rest; it only maps an already-forwarded process environment value.

A normal WSL shell is not assumed to contain provider credentials. Provider-dependent workflows must be launched from the secure Wesnoth Agent Shell or an equivalent secure process path.

## 5. Current Model Routing

Baseline routing:

| Role | Provider / model | Purpose |
|---|---|---|
| Implementer | Groq - `groq/openai/gpt-oss-120b`; one fallback: OpenAI `gpt-5.6-terra` at medium reasoning | Main bounded implementation work |
| Fast fix | OpenCode Zen - `opencode/ling-3.0-flash-fin-free` | Small mechanical corrections |
| Tester | Cloudflare Workers AI - `@cf/zai-org/glm-4.7-flash` | Independent read-only test evaluation |
| Primary reviewer | Google - `google/gemini-3.6-flash` | Independent review when quota is available |
| Fallback reviewer | Cloudflare Workers AI - `@cf/nvidia/nemotron-3-120b-a12b` | Reviewer fallback for infrastructure/non-decisive primary failure |

Routing is policy, not permanence. Models may change if availability, capability, retirement, quota, or quality changes. The role separation and fallback rules are more important than any specific model.

Known provider observations:

- Groq GPT-OSS 120B has successfully implemented tickets but may occasionally emit malformed tool-call output. This is a provider/tool-generation failure class, not necessarily a code failure.
- When the primary GPT-OSS Implementer process fails, the coordinator may invoke exactly one GPT-5.6 Terra fallback at medium reasoning in the same isolated worktree. The fallback uses workspace-write sandboxing, disabled web search, an ephemeral session, a credential-stripped environment, the original objective, and the original allowed-path boundary. It may not commit, merge, push, broaden scope, or run as a Fast-Fix fallback.
- A failed Terra fallback is an immediate provider/worker hard stop and does not consume either of the two bounded code-recovery attempts. If Terra produces a candidate but a later deterministic/test/review gate fails, the normal bounded recovery policy applies.
- Gemini reviewer may hit free-tier `429 RESOURCE_EXHAUSTED` limits and time out.
- A primary reviewer returning substantive `REQUEST_CHANGES` must not be bypassed by asking a fallback reviewer for a more favorable answer.
- Retired or unavailable provider model IDs must be treated as infrastructure failures and corrected deliberately, not silently rerouted in a way that weakens review policy.

## 6. OpenCode Agent Security Model

Project agents are defined under:

`.opencode/agents/`

Current roles:

- `coordinator`
- `implementer`
- `fast-fix`
- `tester`
- `reviewer`
- `reviewer-fallback`

Security rules:

- deny by default;
- no arbitrary shell access for LLM workers;
- no external-directory access;
- no web access unless explicitly designed for a future bounded role;
- no nested-agent spawning by workers;
- implementer/fast-fix may read/edit only permitted project areas;
- protected coordinator/config/reference paths are denied unless the ticket explicitly authorizes architecture/documentation maintenance;
- tester/reviewer roles are read-only;
- deterministic test execution belongs to Python, not the LLM worker.

The Terra Implementer fallback is a narrowly authorized exception to the OpenCode worker tool profile. Codex runs with its `workspace-write` sandbox, no web search, no forwarded provider credentials, and explicit instructions to edit only the allowed project paths. Deterministic scope and protected-path gates remain authoritative immediately after it returns; sandbox access never grants publication or governance authority.

Tool denial is an application-level security boundary. It is not claimed to be equivalent to a separately virtualized OS sandbox.

## 7. Mandatory Project References

Canonical repository references:

- `docs/PROJECT_SCOPE_AND_FEATURE_SET.md`
- `docs/AGENT_ORCHESTRATION_FUNCTIONAL_SPEC.md`

These documents must be treated as protected baseline context.

### 7.1 Agent requirement

Before substantive ticket work, every LLM role must read both reference files or receive an equivalent coordinator-supplied snapshot. Root `AGENTS.md` must explicitly require this behavior.

### 7.2 Coordinator requirement

The deterministic coordinator should include a mandatory-reference block in every worker/tester/reviewer prompt containing:

- exact reference paths;
- instruction to read them before acting;
- statement that ticket objectives may refine but must not silently contradict the references;
- current SHA-256 hashes of the references for audit logging.

A future hardening step should record the hashes in each ticket result.

### 7.3 Change control

Changes to either canonical reference document are architecture/scope changes. They should occur only through a dedicated documentation/architecture ticket and independent review. Ordinary feature tickets must not modify these files.

## 8. Ticket Contract

Current ticket fields:

- `task_id`
- `worker` (`implementer` or `fast-fix`)
- `objective`
- `allowed_paths`
- `validation_profile`
- `validation_root` where applicable
- `resume_branch` when continuing an unfinished managed ticket worktree

Ticket objectives should be bounded, testable, and explicit about exclusions when omission is important.

The ticket is a contract. A worker must not expand scope merely because adjacent changes appear useful.

## 9. Ticket Lifecycle

### Stage 0 - Preconditions

Coordinator verifies:

- execution started from the intended repository;
- base branch is `main`;
- main worktree is clean;
- required provider credentials are present;
- ticket schema is valid;
- task ID is valid and unique enough for current execution;
- required project references exist.
- existing ticket remnants have a managed worktree, an original ticket contract,
  no terminal PASS, no representing pull request, and changes contained by the
  original allowed paths. A failed run remains unfinished work when its remnants
  still satisfy those boundaries.

Failure stops the run.

### Stage 1 - Isolated branch/worktree

For a new ticket, create:

- branch: `agent/<ticket>-<timestamp>`;
- worktree: `~/projects/wesnoth-starwars-worktrees/<ticket>-<timestamp>`.

No worker edits the main worktree.

If a prior ticket started but did not reach a terminal PASS, resume its
existing managed branch/worktree before planning fresh work. Python must derive
the worktree from the trusted Git worktree inventory, restore the original
worker, objective, allowed paths, and validation profile from the prior ticket
record, and validate all existing committed and uncommitted changes before an
LLM continues. The worker must preserve useful partial changes and must not
reset, discard, recreate, or restart the implementation. Branches already
represented by a pull request, terminal PASS results, unmanaged
worktrees, and protected or out-of-scope remnants are not resumable.

A new branch/worktree may be created only when the project owner explicitly
requests a fresh start in the coordinator brief, such as “start from scratch”
or “start a fresh ticket.” Without that instruction and without safe resumable
work, automation pauses with a visible reason.

### Stage 2 - Implementation

Invoke assigned implementer with:

- ticket objective;
- allowed paths;
- prohibited behavior;
- mandatory project references;
- instruction not to commit, merge, push, or run untrusted commands.

If the model exits nonzero, the implementation gate fails unless the error matches a narrowly defined retryable infrastructure/tool-generation class.

### Stage 2A - Controlled transient retry

For recognized malformed tool-generation failures such as parsing/failed-generation errors, the coordinator may retry once in the same worktree with a continuation prompt.

Rules:

- preserve correct partial edits;
- inspect existing work first;
- complete only the original objective;
- same allowed paths;
- maximum retry count must be bounded;
- a second failure fails closed;
- genuine code/test/reviewer failures are not retry candidates.

### Stage 3 - Deterministic validation

Current/static checks include:

- implementer exit code must be zero;
- changed paths collected from Git;
- every changed path must match an allowed path;
- protected paths must remain untouched;
- `git diff --check`;
- maximum file-size checks;
- NUL-byte rejection;
- UTF-8 validation;
- symlink rejection where applicable.

For `wesnoth-addon-static`:

- add-on root exists;
- `_main.cfg` exists;
- `_main.cfg` is nonempty UTF-8;
- invalid `[addon]` and `[translations]` structures are rejected for the minimal foundation case;
- required `[textdomain]` structure is present;
- expected textdomain name/path is validated.

Project-specific expectations should migrate toward ticket-configured expected values rather than unnecessary hard-coding in generic validators.

### Stage 4 - Engine validation

For WML/add-on changes, use the strongest meaningful engine-backed test available at that stage.

Baseline minimal foundation test:

- invoke Wesnoth 1.19.27 `--preprocess` against relevant WML;
- require exit code 0.

As the add-on matures, add:

- `--validate-addon` when meaningful;
- direct scenario load/smoke launch;
- deterministic save/load or replay-based tests where practical;
- focused Lua/WML regression scenarios.

Engine validation should become an automatic trusted coordinator gate rather than an ad-hoc manual command.

### Stage 5 - Tester

A separate read-only model evaluates the implementation against the objective and available evidence.

Tester must not modify files or compensate for deterministic failures.

### Stage 6 - Reviewer

Primary reviewer runs independently.

Fallback reviewer is used only when primary review is unavailable or non-decisive due to infrastructure conditions such as timeout or quota failure.

**No reviewer shopping:** if the primary reviewer substantively requests changes, the result is not sent to a fallback solely to seek approval.

### Stage 7 - Local verdict

Final local PASS requires every mandatory gate to pass.

A local PASS means **eligible for commit/PR**, not automatically merged.

### Optional continuous automation mode

The Agent Manager may offer a human-controlled automation toggle for
the selected Sol coordinator mode. This is an alternate ticket-scheduling mode,
not an exemption from deterministic governance.

When automation is enabled:

- Sol must inventory and resume safe unfinished ticket work before proposing a
  new ticket; stale remnants are continuation context, not grounds to discard
  prior work;
- a fresh ticket is permitted only when the owner-provided coordinator brief
  explicitly authorizes a fresh/new ticket or starting from scratch;
- Sol may read the controlled references and continuity ledger, prioritize the
  planned backlog, and propose one bounded ticket at a time;
- Python remains the authoritative state machine and must validate each ticket,
  create its isolated worktree, enforce path scope, and run every applicable
  deterministic, engine, tester, and reviewer gate;
- a passing ticket may be committed locally to its ticket branch and added to a
  FIFO approval queue, but it must not be pushed, opened as a PR, merged, or
  applied to protected `main` without a separate explicit human approval for
  that exact queued commit;
- subsequent dependent tickets may be based on the preceding queued head so
  unattended work can continue, but approvals and publication must occur in
  dependency order; rejecting or invalidating an upstream item makes dependent
  queue entries stale and requires deterministic replanning;
- turning automation off prevents another ticket from starting. An active
  ticket proceeds only to its next safe deterministic stopping point before
  control returns to the manual Python/Bash workflow; and
- an eligible implementation, validation, tester, or reviewer error may enter
  the bounded recovery policy below before it becomes a final failure; and
- any unrecovered mandatory-gate failure, scope violation, provider failure
  outside established retry policy, dirty or unexpected Git state,
  publication failure, or approval mismatch pauses automation and is recorded
  as an error. Automation must never reinterpret failure as approval.

Automation does not grant a worker shell access, ownership of `main`, access to
credentials, or authority to weaken branch protection. Planning models remain
nondeterministic inputs to the Python coordinator.

#### Bounded autonomous error recovery

When continuous automation is enabled, the deterministic coordinator may ask
the selected coordinator model to diagnose and address an error only when the
error is supported by structured, secret-free evidence and can be corrected
inside the active ticket's existing allowed paths. Eligible errors are limited
to implementation defects, deterministic validation failures attributable to
the candidate change, tester failures, and reviewer requests for changes.

Recovery is limited to **two attempts per ticket**. Each attempt must record
the failure class, safe diagnostic summary, attempt number, proposed corrective
action, changed paths, and resulting gate evidence. The coordinator must use a
narrow corrective brief, preserve the original ticket scope, reject protected
or expanded paths, and rerun every applicable deterministic, engine, tester,
and reviewer gate. A complete PASS resets the recovery counter. Failure after
the second attempt pauses automation and leaves the candidate uncommitted.

The coordinator must stop immediately, without spending recovery attempts, for
errors an implementation ticket cannot safely resolve: dirty or unexpected
repository state; deletion approval; missing human approval; protected-path,
scope, governance, or security violations; missing credentials or secure
bridge; unavailable planner/provider outside existing retry policy; ambiguous
or credential-bearing diagnostics; publication, branch-protection, remote-head,
merge, or approval mismatch; and explicit user stop. These are recorded with a
specific safe reason and required human action.

Before planning new, resumed, or recovery work, the coordinator must include
structured local queue, open pull-request, and managed worktree context so it
does not duplicate an existing ticket. A resumable record must be backed by the
original unfinished ticket contract; terminal PASS results and PR-represented
branches are excluded. If that inventory cannot be established reliably,
automation pauses instead of guessing. A no-safe-ticket decision must preserve
the model's specific reason in the control state and activity log rather than
appearing as a silent or generic failure.

#### Ticket approval queue and publication

Each passing local commit enters a repository-owned approval record containing
at minimum the ticket ID, purpose, expected mod impact, dependency position,
changed paths, branch, base SHA, exact commit SHA, validation evidence, reviewer
verdict, and publication state. Queue records must expose no credential values.

The dashboard may present one approval action for the fixed publication
pipeline. That action is authorization for the exact queued commit only. The
deterministic controller must then, in order:

1. verify that the queue record, branch, commit, diff, dependency order, and
   local PASS evidence are unchanged;
2. push the ticket branch without force;
3. create or update its pull request with validation evidence;
4. wait for required GitHub checks on the exact PR head;
5. merge only through protected-branch policy after every required check and
   conversation rule passes; and
6. synchronize local `main` and update structured queue evidence.

A single approval does not authorize later commits, other queue items, direct
pushes to `main`, force pushes, branch-protection bypass, or credential access.
Any head change, failed check, merge conflict, unexpected remote state, or
policy rejection terminates the pipeline and requires a new review/approval.

#### File deletion approval

Before creating a local ticket commit, Python must inspect the actual Git diff
for deleted files. If any deletion exists, the ticket and continuous scheduler
pause and a dedicated deletion manifest is created. The manifest must bind the
ticket ID, branch, base SHA, candidate tree identity, exact deleted paths, prior
blob identities, stated reasons, and expected impact to a unique request ID.

The request remains visible in the dashboard approval queue for the
project owner to inspect. No recurring Codex task, background chat message, or
token-consuming notification job is required. The local fail-closed gate is
authoritative and must record an explicit approve or reject decision for the
exact manifest. A changed path set, candidate tree, branch, or request identity
invalidates the decision. No deletion commit, later ticket, push, PR, or merge
may proceed while this gate is unresolved.

#### Dashboard presentation

The dashboard places validated local commits in a **Ticket approval queue**.
Each item has an expandable summary of purpose, expected mod impact, files,
gates, dependencies, and publication state. The per-ticket approval action is
enabled only when deterministic prerequisites are satisfied.

The former routing-history surface becomes **Activity log and errors**. It
combines structured coordinator, routing, validation, approval, and publication
events. Recovery entries show the error class, current attempt out of two,
corrective action, and resulting state. Error-bearing entries use the
established red alert treatment and open an accessible detail dialog containing
the specific safe diagnostic and required next action when selected. Secrets,
environment values, raw
credential-bearing logs, and arbitrary filesystem content must never be shown.

Ordinary tickets remain unable to modify controlled references. A controlled
reference change must be a clearly identified governance ticket, synchronize
all affected Markdown/DOCX representations and manifest values, pass the
reference-package self-test, and receive its own exact-commit publication
approval through the queue.

#### Paired private-LAN access and clean shutdown

The Python dashboard server remains bound to `127.0.0.1`. The repository-owned
Windows launcher may expose it to other devices through a narrow user-space
proxy bound to one detected private IPv4 address and TCP port 8765. The Windows
firewall rule must be limited to the Private profile, that local address, and
`LocalSubnet` sources. The dashboard must display the LAN address under system
health.

LAN access must require a high-entropy runtime pairing token delivered in a URL
fragment. The token is stored only in a permission-restricted ignored runtime
file and the paired browser's local storage; it is not an environment variable,
telemetry field, provider credential, log value, query parameter, or committed
file. Static assets and minimal health status may be retrieved before pairing,
but status, coordinator state, and every mutation endpoint must reject an
unpaired LAN request. A paired LAN device receives the same governed controls as
localhost. Mutations additionally retain exact-origin, per-process CSRF,
allowlisted-action, request-size, and deterministic controller validation.

An **Exit dashboard** action may be accepted from localhost or a paired LAN
device only while no planning, ticket-execution, or publication operation is
active. The server must complete its shutdown and remove its own
PID/version/session records before signaling exit. A session-specific marker
may then close only the CMD process tree that launched that dashboard session;
unrelated consoles, processes, and WSL distributions must not be targeted. The
same signal stops the LAN proxy.

### Stage 8 - Commit and GitHub publication

After local PASS:

1. commit only the allowed validated changes on the ticket branch;
2. push ticket branch to `origin`;
3. create/update a GitHub pull request;
4. include ticket ID, objective, changed paths, local validation summary, engine test result, tester result, reviewer result, and known limitations;
5. do not push directly to protected `main`.

### Stage 9 - GitHub CI and policy

GitHub Actions should run checks that are safe and reproducible in GitHub-hosted CI, such as:

- Python syntax/compile checks;
- coordinator unit/regression tests;
- repository hygiene checks;
- documentation/reference existence checks;
- WML static checks that do not depend on the local Windows-only Wesnoth installation;
- optional Linux-engine validation only if its version is deliberately matched or treated as supplemental rather than authoritative.

Do not move private provider credentials to GitHub simply to duplicate local LLM review.

### Stage 10 - Merge

Merge only when:

- local gates passed for the exact commit SHA;
- GitHub required checks pass for the exact PR head;
- required review/conversation policy is satisfied;
- no new unvalidated commit has been pushed afterward.

Prefer linear history/fast-forward or squash policy consistently. The repository should not allow casual direct writes to `main` after protections are active.

### Stage 11 - Cleanup

After successful merge:

- synchronize local `main` with `origin/main`;
- verify clean status;
- remove completed ticket worktree;
- delete local ticket branch when safe;
- delete remote ticket branch when desired;
- prune worktrees;
- retain logs/results according to repository policy.

## 10. GitHub Repository Controls

Recommended `main` ruleset/protection:

- require a pull request before merging;
- require required status checks;
- require conversation resolution;
- block force pushes;
- block deletion;
- require linear history if compatible with chosen merge strategy;
- apply protections to administrators where practical;
- minimize bypass actors;
- optionally require the branch to be up to date before merge when CI cost is acceptable.

Recommended pull-request template fields:

- Ticket ID
- Objective
- Allowed paths
- Summary of implementation
- Deterministic validation result
- Wesnoth engine result
- Tester result
- Reviewer used/result
- Known risks/limitations
- Reference-document changes (normally `None`)

Recommended initial Actions permissions:

```yaml
permissions:
  contents: read
```

Increase individual job permissions only when a job specifically needs them.

## 11. GitHub Actions Security Rules

- default to least-privilege `GITHUB_TOKEN` permissions;
- avoid long-lived personal tokens in workflows;
- pin sensitive third-party actions to trusted versions/commits where appropriate;
- do not expose local provider keys to PR workflows;
- treat pull-request code as potentially untrusted input;
- avoid workflow patterns that execute untrusted PR code with write-capable secrets;
- keep job names unique if they become required status checks;
- require checks on the current PR head SHA before merge.

## 12. Protected Paths

The protected set should include at minimum:

- `.git` internals;
- `.opencode/agents/` except dedicated agent-configuration tickets;
- root `AGENTS.md` except dedicated architecture/reference tickets;
- `agent/coordinator/` except coordinator-maintenance tickets;
- `docs/PROJECT_SCOPE_AND_FEATURE_SET.md` except approved scope-documentation tickets;
- `docs/AGENT_ORCHESTRATION_FUNCTIONAL_SPEC.md` except approved architecture-documentation tickets;
- security/credential files and launcher definitions unless the ticket explicitly targets them.

Ticket-level allowlists do not implicitly override security-sensitive protected paths.

## 13. Logging and Evidence

Each run should retain enough evidence to reconstruct what happened without storing secrets.

Current/future result metadata should include:

- task ID;
- timestamps;
- base commit SHA;
- branch/worktree;
- worker/model;
- implementation exit code and retry count;
- changed paths;
- validation profile/results;
- engine command/version/result;
- tester model/result;
- reviewer primary/fallback/result;
- reference-document hashes;
- final verdict;
- commit SHA if created;
- PR number/URL once GitHub publication exists;
- merge SHA once merged.

Never log API key values.

## 14. Error Classification

Failures should be classified rather than treated uniformly.

### Implementation/content failure

Examples:

- objective not met;
- invalid WML;
- tests fail;
- scope violation;
- reviewer requests substantive changes.

Action: fail ticket and require correction.

### Infrastructure/provider failure

Examples:

- quota exhaustion;
- timeout;
- model endpoint retired;
- malformed provider tool-call generation;
- transient network/API failure.

Action: use only pre-defined retry/fallback policy. Do not reinterpret as content approval.

### Validation-design failure

Example already encountered:

- initial static validator accepted semantically incorrect Wesnoth add-on structure;
- direct `wesnoth --validate _main.cfg` was later discovered to be the wrong engine mode for a minimal add-on and produced false negatives.

Action: fix the validator/process itself, add regression coverage, and do not merge based on the flawed gate.

## 15. Current Known Technical Lessons

1. A pipeline PASS is only as strong as its deterministic semantics.
2. AI agreement does not prove WML correctness.
3. Wesnoth CLI modes must be matched to the object being validated.
4. Provider errors can masquerade as model/content failures.
5. Secure provider environment presence must be verified before diagnosing model availability.
6. Normal WSL shells are not equivalent to the secure launcher shell.
7. `opencode web` is useful for interaction but does not natively visualize deterministic ticket state.
8. Cleanup scripts must distinguish successful and stale ticket worktrees.
9. Shell `$?` must be captured immediately after the command whose exit code is needed.
10. Repository reference documents should be enforced as process inputs, not merely stored as human documentation.

## 16. LLM Rules of Engagement

All development LLMs must follow these rules:

- read the mandatory references before substantive work;
- obey ticket scope and allowed paths;
- do not broaden scope without explicit instruction;
- do not claim tests were run when they were not;
- do not modify protected architecture/security/reference files unless explicitly authorized;
- do not commit, merge, push, or alter GitHub protections unless the role/ticket explicitly allows it;
- do not request or expose secrets;
- do not copy copyrighted Star Wars prose, dialogue, art, audio, or proprietary assets;
- distinguish uncertainty from verified facts;
- preserve existing architectural decisions unless a ticket explicitly changes them;
- make original implementation choices compatible with the project scope;
- tester/reviewer agents remain read-only;
- fallback reviewer is not a mechanism to overturn a substantive negative primary review.

## 17. Mandatory Reference Injection Design

The root `AGENTS.md` should contain a mandatory block equivalent to:

```text
MANDATORY PROJECT REFERENCES
Before substantive work, read:
1. docs/PROJECT_SCOPE_AND_FEATURE_SET.md
2. docs/AGENT_ORCHESTRATION_FUNCTIONAL_SPEC.md

These documents define project scope, architecture, security boundaries,
validation policy, copyright constraints, and development objectives.
Ticket instructions may refine a task but may not silently override these
references. If a conflict exists, stop and report the conflict.
```

Additionally, `ticket_runner.py` and `coordinator.py` should prepend the same requirement to every implementer, fast-fix, tester, reviewer, and fallback-reviewer prompt.

This dual mechanism prevents a single missed configuration path from silently removing project context.

## 18. Proposed GitHub Integration Implementation

### Phase A - repository connection

- authenticate GitHub CLI (`gh`) on KillDozer/WSL using browser/device flow or SSH-based Git authentication;
- create or select the private GitHub repository;
- add `origin`;
- push `main` and set upstream;
- verify remote URL and default branch.

No GitHub token should be placed in the project `.env` or committed files.

### Phase B - repository policy files

Add:

- `.github/workflows/ci.yml`
- `.github/pull_request_template.md`
- optional `CODEOWNERS` after the GitHub account/owner is known
- the two canonical `docs/` references
- updated `AGENTS.md`

### Phase C - branch protection/ruleset

Protect `main` after CI check names exist so required checks can be selected reliably.

### Phase D - coordinator publication

Extend deterministic tooling to optionally:

- commit an approved ticket branch;
- push branch;
- create PR via `gh pr create` or GitHub API;
- store PR identifier in result metadata;
- query required check status;
- refuse merge until checks pass;
- require explicit human/architect authorization for merge at the current maturity level.
- bind a dashboard publication approval to one exact queued commit and execute
  the fixed push/PR/exact-head-CI/protected-merge sequence without broad shell
  input from the browser;
- maintain FIFO dependency ordering for queued autonomous tickets; and
- pause before any file deletion until an exact deletion manifest is explicitly
  approved through the Codex-routed approval channel.

### Phase E - dashboard

The local Agent Manager dashboard displays:

- current/last ticket;
- worktree and branch;
- implementer/tester/reviewer stages;
- engine gate;
- GitHub push/PR state;
- CI checks;
- review state;
- merge readiness;
- ticket approval queue with expandable purpose and impact summaries;
- activity log and errors with accessible error-detail dialogs;
- paired private-LAN access with the reachable address shown under system health;
- a safe-state Exit dashboard action scoped to its associated launcher console;
- view diff/logs;
- retry eligible infrastructure failures;
- never bypass mandatory gates.

## 19. Definition of Done for a Development Ticket

A standard game-development ticket is Done only when all applicable items are true:

- objective satisfied;
- only allowed paths changed;
- protected paths untouched;
- deterministic checks pass;
- appropriate Wesnoth engine validation passes;
- tester passes;
- reviewer approves under policy;
- exact validated changes committed to ticket branch;
- branch pushed to GitHub;
- PR opened with evidence;
- required GitHub CI passes on the exact PR head;
- required review policy satisfied;
- PR merged into protected `main`;
- local `main` synchronized and clean;
- worktree/branch cleanup completed;
- result metadata updated with commit/PR/merge evidence.

Architecture or reference-document tickets additionally require explicit recognition that project policy itself is changing.

## 20. Reference Maintenance

These documents are living specifications. They should be updated when any of the following materially changes:

- project scope or gameplay feature set;
- campaign structure;
- engine target;
- agent roles/models;
- provider strategy;
- validation gates;
- secure credential design;
- ticket schema;
- Git/GitHub workflow;
- merge policy;
- protected paths;
- dashboard/orchestration architecture;
- copyright/content constraints.

Updates must be committed and reviewed so subsequent agents consume the new canonical version.
