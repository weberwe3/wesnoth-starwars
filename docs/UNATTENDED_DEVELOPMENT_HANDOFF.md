# Implement unattended development and playable delivery

Prepared 2026-09-27. This is the entry point for the next project-level LLM.

## Owner objective

The owner wants to leave the computer unattended and return to a mod they can
play. Implement the production architecture through a connected three-mission
playable prototype, safe verified-build delivery, and a qualified unattended
improvement run. Then continue toward the production proof and later milestones
when their dependencies and existing authority permit. An improved build or a
precise preserved blocker must be visible when the owner returns.

The task is implementation, verification, and delivery through the existing
governed workflow. Producing more planning documents does not satisfy it. Never
claim that a whole trilogy, final art, or human enjoyment has been established by
ticket throughput, source inspection, or an engine process staying alive.

## Read in this order

1. [Repository instructions](../AGENTS.md).
2. [Canonical scope](PROJECT_SCOPE_AND_FEATURE_SET.md) and
   [canonical orchestration](AGENT_ORCHESTRATION_FUNCTIONAL_SPEC.md).
3. [Reference policy](REFERENCE_POLICY.md), [manifest](REFERENCE_MANIFEST.json),
   [continuity](PROJECT_CONTINUITY.md), and [worktree lessons](WORKTREE_LESSONS.md).
4. [Target architecture](TARGET_ARCHITECTURE.md).
5. [Unattended delivery specification](UNATTENDED_DELIVERY_SPEC.md).
6. [Implementation plan](AUTONOMOUS_PRODUCTION_PLAN.md), including packages U1-U6
   and the distinction between prototype checkpoint 6A and production proof 6B.

Controlled references govern authority. The target and delivery documents specify
the intended behavior to implement; they do not expand current permissions or
make proposed schema fields acceptable to the existing runner. Resolve a concrete
conflict through the dedicated reference/coordinator work, preserving worker
restrictions and independent verification.

## Known starting state to reconcile

At the preparation snapshot:

- The supplied native checkout is
  `C:/Users/willj/Documents/Codex/WesnothAgentWorktrees/autonomous-mod-architecture-20260926`.
- Its WSL path is
  `/mnt/c/Users/willj/Documents/Codex/WesnothAgentWorktrees/autonomous-mod-architecture-20260926`.
  Git metadata refers to the WSL repository; native Windows Git may reject that
  gitdir. WSL Git successfully inspected this checkout. This observation is not
  permission to move implementation workers to unsupported UNC/WSL write paths.
- The checked-out branch was
  `governance/autonomous-production-adoption-20260926`, based on local commit
  `d356dab1bf61b749669502ec2776fd580640781d`. Remote state was not refreshed.
- Controlled Markdown, both DOCX copies, manifest, and continuity contain local
  adoption edits. The architecture/plan and this unattended documentation are
  local drafts. Preserve and inspect all changes before choosing a worktree.
- Earlier reference-package self-test and whitespace checks passed, but that is
  not independent approval, CI, merge, or current-head evidence. Recheck the
  actual package and diff. The DOCX copies lack visual QA because the configured
  bundled renderer could not find its LibreOffice executable. Resolve or report
  this exact remaining archive-quality gate through the project workflow.
- No implementation code, runtime capability, engine playtest, commit, PR, or
  merge was produced by the documentation preparation. No unattended run or new
  media provider has been enabled.

This list is a historical handoff, not live state. Inspect Git/worktrees, open
PRs and CI, controller ownership, pending tickets, active processes, capability
results, and current reference hashes before dispatch. Preserve existing work
and any local handoff file. Never infer a clean base or completed adoption from
the branch name or this document.

## First actions and sequencing

Finish package 1 through the dedicated governed reference process. Reconcile the
new unattended requirements with canonical section 21 and preserve the configured
reviewer route. Synchronize any changed controlled representations and manifest.
The existing local edits are input to that review, not evidence it already passed.

Then compile the plan into small immutable execution contracts. Each contract
names its package, concrete player or operational outcome, allowed paths,
requirements, dependencies, actual validation capability, acceptance evidence,
resource limit, and stop conditions. Validate adapters before dispatching new
fields. Reuse complete recorded contracts and resume eligible repairs first.

Use the plan's dependency table. Begin inventory and an installed-engine behavior
spike before a general simulator or mission framework. Build the charter and
evidence layer, then verified packaging/launch, supervision, asset feasibility,
and scheduler integration. Improve actual mission content as soon as inventory
and probes permit. Do not defer playable delivery behind a dashboard redesign.

For 6A, select three existing missions using the inventory and reviewed creative
direction; prove their actual sequence and required save/defeat/carryover cases.
Deliver the exact verified package through the stable player launcher. Then run
U6 with explicit adopted limits and the real supported host/session configuration.
Proceed to the full production proof only with its additional quality evidence.

## Responsibility and authority

Coordinate work through the existing deterministic system. Workers edit bounded
artifacts; Python executes commands/tests, records real outcomes, and governs
publication. Tester and reviewer remain independent. Do not give workers protected
coordinator paths or tell them to test, commit, publish, or weaken acceptance.

The project-level coordinator should locate and use the existing authorized
validation, review, and publication path. Do not stop simply because those actions
are forbidden to a bounded worker; arrange the correct responsible stage. If the
needed path is unavailable, preserve the candidate and report the exact missing
capability or authority. Do not assume the LLM itself inherits runtime authority.

Reuse already recorded owner authorization for routine actions. Avoid repetitive
approval requests where the existing policy permits continuation. Missing or
expired authority for a consequential action is not implied approval: identify
that action, its governing rule, and the concrete reviewable candidate. Continue
independent eligible work only when the current policy permits it.

Keep one write worker and publication lane initially. Preserve recovery limits,
global pauses, deletion approval, secret handling, and separate public-release
authorization. Do not install a background host service, change power/login
security, or add an unattended media provider based solely on this handoff.

## Existing implementation seams

Inspect before designing replacements:

| Existing path | Relevant responsibility |
| --- | --- |
| `agent/dashboard/autonomy.py` | Selection, resumption, continuous-run control, publication handoff |
| `agent/dashboard/approval_queue.py` | Recorded authority and protected publication |
| `agent/coordinator/scenario_launch_selftest.py` | Installed-engine staging and player-build validation |
| `agent/coordinator/gameplay_contracts.py` | Structural contract retention and bounded coverage |
| `agent/coordinator/ticket_acceptance.py` | Baseline-aware ticket acceptance |
| `agent/coordinator/art_pipeline.py` | Existing complete asset contracts and import workflow |
| `agent/coordinator/reference_package.py` | Controlled reference identity and protection |
| `agent/coordinator/runtime_status.py` | Existing status/evidence surfaces |
| `agent/runtime/Play-WesnothStarWars.cmd` | Existing player launcher to migrate with explicit developer-launch preservation |

Names for new modules are implementation choices. Prefer focused modules and
validated adapters; do not create a second scheduler, evidence authority, art
queue, credential store, or publication pipeline.

## Required evidence at the first unattended-delivery checkpoint

- Reviewed charter and reference/design identities, enforced budgets, and
  documented supported host/session conditions.
- Inventory and explicit requirement coverage for the selected three missions.
- Installed-engine legal-play, negative-fixture, transition, defeat, and save/load
  results with exact identities; direct handler probes labeled separately.
- Exact package and manifest, eligible current/predecessor builds, stable offline
  player entry point, save preservation, and tested rollback.
- U6 fault matrix plus a real bounded run that delivers at least one verified
  improvement without an unexpected routine owner intervention.
- An owner-facing result: what can be played, what improved, what remains
  unverified, budget usage, and any precise blocker. Safe failure alone does not
  satisfy the successful-delivery checkpoint.

Keep raw logs and temporary state in ignored runtime storage. Commit only
appropriate durable summaries with evidence digests and exact identities. Record
completed versus pending packages honestly and preserve the next eligible
contract so another session can resume without reconstructing chat history.

## Prompt to give the implementing LLM

> Read `docs/UNATTENDED_DEVELOPMENT_HANDOFF.md` in this checkout and its required
> references. Act as the project-level implementation coordinator and carry out
> the target architecture, unattended delivery specification, and sequenced plan
> through the first connected three-mission playable delivery and unattended
> qualification, then continue the approved milestones as dependencies permit.
> Reconcile and preserve the existing local governance edits first. Use bounded
> isolated contracts and the existing deterministic validation, independent review,
> and publication workflow. Reuse existing authorization; resolve actual missing
> authority explicitly. Deliver a verified build with a stable launch entry point
> and retained rollback build. Continue through tested implementation. Keep
> prototype, final presentation, and release readiness distinct. Report actual
> evidence and precise blockers; never fabricate completed tests or weaken gates.
