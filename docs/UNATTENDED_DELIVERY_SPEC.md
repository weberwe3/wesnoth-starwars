# Unattended development and playable build delivery

Revision: 2026-09-27. Implementation specification, not an implementation report.

The owner's goal is to leave the computer unattended and return to a mod they can
play. Each run should improve an approved playable milestone, verify its changes,
and leave the newest eligible build ready to launch. If no improved candidate
qualifies, retain the previous eligible build and explain the blocker. Never
promise that every run will finish a milestone or the whole trilogy.

This specification extends [the target architecture](TARGET_ARCHITECTURE.md).
Use [the implementation plan](AUTONOMOUS_PRODUCTION_PLAN.md) for dependencies and
[the implementation handoff](UNATTENDED_DEVELOPMENT_HANDOFF.md) to start work.
The controlled scope and orchestration references remain authoritative. Proposed
fields and states below require validated adapters; they are not accepted inputs
to the current ticket runner. Any additional operating authority must be adopted
through the controlled governance process before activation.

## 1. Delivery targets

The first target, checkpoint 6A in the plan, is a coherent sequence of three
existing missions with reachable objectives, actual transitions, usable carryover,
defeat handling, and save/load evidence. Select the sequence from the inventory;
do not assume mission numbering proves continuity. Cover ground combat, a
meaningful specialist objective, and space combat where the reviewed sequence
supports them. Any unresolved mode gap remains an explicit milestone requirement.

Distinguish three delivery profiles, each with reviewed required evidence:

| Profile | What may be claimed | Remaining requirements |
| --- | --- | --- |
| Playable prototype | The named sequence passes its approved gameplay and installation gates; declared temporary original assets are permitted | Final presentation, broader difficulty coverage, and human play quality remain independently tracked |
| Production proof | The 3-5 mission proof meets the architecture's representative final presentation and playtest gates | Expansion to the vertical slice and campaigns |
| Release candidate | All required campaign, presentation, compatibility, and release requirements pass | Separate public distribution authorization |

The profile is fixed before work begins. Workers cannot downgrade it after a
failure. A prototype pass cannot verify the production-proof milestone or the
final-presentation dimension. The existing full 13-file unit contract still
applies; temporary assets do not waive technical import or source gates. An
approved prototype profile must resolve any conflict with current policy through
package 1 before use.

## 2. Bounded operating charter

Persist a versioned, reviewed charter for the run. Bind it to the controlled
reference identity and production design revisions. Validate at least:

- milestone ID, required nodes, delivery profile, permitted build entry points,
  and the specific player outcome;
- allowed ticket classes and paths, protected inputs, permitted original asset
  sources, and bounded defaults for routine creative choices;
- model-call, elapsed-time, engine-run, repair, and disk limits; explicit cost
  limits when reliable cost data exists, otherwise an enforceable usage bound;
- a completion cutoff and a reserve for integration, testing, and packaging;
- permissions for local build promotion and existing governed publication,
  their approval identity, expiry, revocation, and restart behavior;
- available capabilities, required desktop/session conditions, retry policy,
  escalation conditions, and notification preferences.

Reject missing limits and unresolved choices that are critical to the selected
milestone. Optional choices use approved defaults. Reuse authority already
recorded by the existing workflow; do not add per-ticket prompts for actions
already permitted. A charter cannot authorize itself or silently broaden scope.

Reserve sufficient remaining budget before beginning a new ticket. At the
completion cutoff, stop selecting expansion work and finish only eligible
bounded integration/delivery work within the remaining budget. Exhaustion never
removes a gate or publishes a half-tested build. Persist actual budget usage
across restarts; reserve in-flight usage so a crash cannot reset the allowance.

Changes to credentials, model routing, protected governance, destructive actions,
and public distribution retain their existing authorization requirements. A
required decision should identify the exact blocked action and policy, preserve
work, and allow unrelated eligible work only when current policy permits it.

## 3. Verified build storage and launch

Keep development staging separate from the player installation. Extend the
existing installed-engine harness and publisher instead of creating competing
validation or Git publication systems. Preserve an explicitly labeled developer
launcher for local experiments. The normal player launcher must resolve an
immutable verified build and never silently stage uncommitted development files.

Build from an exact reviewed and integrated revision that passed all applicable
publication gates. Package with an allowlist that excludes controller state,
credentials, test instrumentation, development tools, and raw logs. Test the
packaged bytes in isolated clean userdata before promotion. Validate upgrade and
save compatibility where the selected delivery profile requires them.

Each immutable build manifest records:

- build ID, source commit/tree identity, package digest, and per-file inventory;
- engine/version matrix, harness and requirement identities, retained evidence
  digests, and tested scenarios, difficulties, seeds, and exercise types;
- delivery profile, asset provenance references, declared limitations, and
  unverified readiness dimensions;
- launch entry points, save compatibility/version information, predecessor
  build ID, creation time, and promotion/revocation history references.

Use a single promotion owner with a durable intent record. Write and validate the
candidate and manifest before replacing a small current-build pointer atomically
on the same filesystem. Validate the chosen Windows/WSL filesystem behavior with
interruption fixtures; never assume a multi-file copy is atomic. Interrupted
promotion must leave either the old complete build or the new complete build
selected. On restart, reconcile pointer, manifest, actual bytes, and intent.

Resolve and pin a build once at launch. A promotion cannot replace files beneath
a running game. Keep player saves outside immutable build directories; never
overwrite or delete them during promotion, rollback, or cleanup. Do not promise
backward save compatibility: preserve incompatible saves and explain which build
can load them. Cleanup must respect active game sessions, retained rollback
builds, disk budgets, and existing deletion authority.

Expose **Play Latest Verified Build**, build identity and profile, and rollback
to the previous eligible build. Launch must work with the development controller
stopped and without Python, Codex, or network access. Do not replace a saved game
or start a GUI session merely to announce that a build is ready.

Verification is tied to recorded inputs. If later evidence shows a retained build
is broken or its required evidence is no longer applicable, revoke its eligibility
without rewriting its immutable history. Select an eligible predecessor under the
approved promotion policy; otherwise show that no verified build is available.
On first setup, establish a genuinely verified baseline or expose that same empty
state. Never label an untested current checkout as the initial verified build.

## 4. Durable supervisor and host preflight

Use one authoritative state writer, monotonic revisions, atomic checkpoints, and
stable action identities. A supervisor may restart owned processes within bounded
policy; a second supervisor must be rejected by an OS-backed ownership lock.
Process ownership must include run/action identity and process creation identity,
not only a reusable PID. Cleanup targets only verified owned resources.

Record intent before launching workers, engine tests, publication, import, or
promotion. After interruption, inspect the actual Git/PR/engine/build state before
retrying a side effect. Expired process ownership does not imply that a push or
merge failed. Model text cannot advance an execution state or synthesize evidence.

Preflight the engine, storage and free space, repository health, existing
authentication availability without exposing secrets, network-dependent services,
configured budgets, asset availability, and required desktop conditions. Test
locked-session and restart behavior on the actual host. Headless tests and GUI
tests have separate capability results. A missing interactive desktop cannot
silently skip a required GUI gate.

Document the supported session conditions, including sleep behavior. Do not
disable desktop security or change power, login, credential, or startup settings
implicitly. Any host installation/configuration action follows existing authority.
Without approved automatic startup, recovery begins when the owner next starts
the controller; do not claim reboot-unattended recovery in that configuration.

Supervisor updates are reviewed and activated at a safe checkpoint. Do not let an
in-flight implementation worker hot-replace its own control process. A failed
supervisor update retains the previous usable controller and state schema.

## 5. Recovery and useful progress

Use the existing failure taxonomy and recovery limits as the authority, with
explicit mappings for any added states:

| Failure | Response within approved policy |
| --- | --- |
| Temporary service/network failure | Persist diagnosis; bounded backoff and retry when eligible |
| Quota/rate limit | Respect a reliable reset/retry time within run limits; no rapid polling or unauthorized provider switch |
| Provider circuit or fallback exhaustion | Preserve the existing hard stop; do not reinterpret it as a content repair |
| Content/test/review defect | Preserve original acceptance and diagnosis; use existing bounded repair attempts |
| Ordinary local asset/dependency blocker | Mark the affected nodes blocked; select independent eligible work only if permitted |
| Global safety pause, reference mismatch, security or repository-integrity failure | Stop scheduling and publication; preserve evidence and report the required action |
| Packaging or promotion failure | Preserve the previous eligible player build; diagnose and retry only within policy |

Keep the existing two-attempt recovery and three-consecutive-worktree-failure
boundaries. Availability handling cannot reset counters, rotate identities, or
choose unrelated work to escape a mandatory pause. Apply any proposed changes to
that behavior only in a separate explicit governance ticket.

Persist a failure fingerprint and verified-progress window. Repeated identical
failures or several tickets without a newly verified requirement must cause a
bounded planning review, then a precise blocked result if unresolved. Compilation,
commit count, token usage, and source growth do not count as product progress.
Fix accepted defects before expansion. A corrected contract is a linked reviewed
revision; it never erases the failed original or weakens its accepted checks.

## 6. Tests that establish playable outcomes

Use the installed-engine capability spike to establish setup, action injection,
observation, replay, and save/load mechanisms. Every probe declares whether it
uses legal gameplay, direct handler invocation, or structural inspection. Only
the applicable exercise type can satisfy a requirement. Legal victory must reach
the objective; calling its endlevel handler is insufficient.

The first sequence needs positive and negative objective cases, relevant defeat
paths, actual transitions and carryover, save/reload before and after important
state changes, and readable launch/objective feedback. Retain exact seeds, input
actions, outputs, and bounded observations so a failure can be reproduced.

Test designers and reviewers remain independent of the implementation under
review. Protect expected outcomes from worker edits. Include broken fixtures that
remove triggers, admit the wrong unit, make an objective unreachable, or corrupt
carryover. Negative fixtures must fail. Where the engine cannot automate a
required behavior, mark it pending and define the needed capability work; do not
advertise that milestone as fully unattended.

Use held-out seeds and measured tactical metrics for balance regression. Automated
success does not certify human enjoyment. Collect owner feedback at playable
milestones and convert it into bounded requirements for later runs; routine code
edits should not require the owner to be present.

## 7. Assets without an unplanned interactive dependency

Default to the existing asset queue and an approved inventory of original assets.
Before starting a run, identify every asset required by the selected profile and
whether it is already importable under the current full-state contract. Deduplicate
requirements by asset ID and brief revision; do not create a second status ledger.

An interactive image-generation handoff is not an unattended production capability.
If an asset is unavailable, choose already approved independent work or preserve
the blocked milestone. A prototype may use declared approved original temporary
assets only under its reviewed profile. Required audio follows explicit briefs,
provenance, wiring, and review; do not silently substitute licensed media or add a
voice-acting requirement.

An unattended media provider is an optional separate project with explicit
capability, cost, credential, originality, quality, and integration approval. It
is not a prerequisite when a prepared original asset library satisfies the run.

## 8. Unattended qualification and reporting

Run a real sustained trial against the first playable sequence before claiming
set-and-forget operation. Proposed qualification duration is 12 hours, adopted
with explicit call/time/cost limits before execution. Use accelerated fault
fixtures in addition to the real trial; they cannot replace host/session testing.
Exercise faults only in isolated test state and owned processes.

| Qualification case | Required result |
| --- | --- |
| Worker/controller terminated at a checkpoint | Original contract and budget survive; safe resume or precise preserved stop |
| Duplicate supervisor or reused PID | Second writer rejected; unrelated processes untouched |
| Temporary service failure and quota delay | Bounded recovery or policy stop; no unauthorized fallback or retry loop |
| Interrupted push, merge, import, or promotion | Actual state reconciled; no duplicate external action |
| Corrupt pointer, invalid manifest, stale evidence, or disk exhaustion | Candidate rejected; no false verified-build claim or partial installation |
| Locked desktop and restart under supported configuration | Required gates run successfully or capability is explicitly blocked |
| Failed candidate, revoked build, and rollback | Eligible predecessor remains launchable; saves preserved |
| Budget cutoff, repeated defect, or no verified progress | Safe finish/stop with durable diagnosis; no expansion loop |
| Successful bounded improvement | New requirement evidence and exact packaged build promoted; previous build retained |
| Owner returns with development services stopped | Selected build launches through the player entry point and remains playable offline |

Passing requires both fault-handling evidence and at least one real improvement
delivered without an unexpected routine owner intervention. Correct handling of
a blocker is valuable evidence but is not proof of unattended delivery. Record
tested and unsupported host conditions; repeat affected cases after relevant
controller, harness, engine, packaging, or authorization changes.

The owner view leads with the play button, selected build/profile, newly playable
content, tested coverage, and limitations. Show the last good build even when the
current run is blocked. Then show remaining budget, current requirement, and the
single next decision if one is required. Distinguish estimated from measured
cost. Notify on a new playable build, milestone completion, meaningful failure,
or required action; stay quiet for unchanged routine progress unless requested.
Reports must never expose credentials, raw provider output, or internal logs by
default.
