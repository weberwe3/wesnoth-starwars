# Implementation plan for autonomous mod production

Companion to [the target architecture](TARGET_ARCHITECTURE.md). These are ordered
work packages for the coordinator to split into bounded immutable contracts.
They are not executable tickets, a replacement runtime backlog, or authorization
to start publication. Completion of one package does not establish completion of
later packages or any game milestone.

Revision: 2026-09-27. Start with the
[implementation handoff](UNATTENDED_DEVELOPMENT_HANDOFF.md). The detailed
unattended acceptance contract is [the delivery specification](UNATTENDED_DELIVERY_SPEC.md).
The required first outcome is a connected three-mission playable build that can
be improved, verified, installed, and preserved without routine owner presence.

## Execution order and first delivery

Existing package numbers 1-8 are retained. U1-U6 add the delivery and reliability
work; 6A is the early prototype checkpoint and 6B is the full production proof.
Split each package into bounded contracts rather than dispatching an entire
package as one worker ticket. Path/role coordination permits independent work;
the initial implementation still uses one write worker and one publication lane.

| Stage | Packages | Evidence needed to advance |
| --- | --- | --- |
| Adopt direction | 1 | Reviewed controlled references and exact package identity; pending local drafts are not adoption |
| Establish facts and capabilities | 2, 3 | Inventory and installed-engine probe capability, including explicit unknowns |
| Define trusted inputs | 4, U1 | Evidence identity, coverage migration, and validated operating charter |
| Build delivery and operation | 5, U2, U3, U5 | Shadow selection, stable build storage/launch, supervisor, and prepared asset route |
| Deliver the first sequence | 6A, U4 | Three connected missions and bounded recovery/progress integration |
| Qualify unattended improvement | U6 | Real delivered improvement plus interruption and host/session evidence |
| Polish and expand | 6B, 7, 8 | Full production proof, vertical slice, campaigns, and release gates in order |

Mission design and scoped repairs begin as soon as inventory and probes permit;
do not wait for every infrastructure package to finish before improving content.
Likewise, deliver the minimal play/build-status interface in U2; the broader
dashboard in package 7 must not delay first delivery. Record evidence and the next
eligible contract after every package; a design document alone closes no runtime
requirement.

## 1. Adopt coherent references

**Outcome:** subsequent workers receive one consistent architecture and current
product direction.

Use a dedicated governance branch/PR to reconcile scope section 4 and development
priorities, orchestration routing section 5 versus stage 6, and stale continuity
status/roadmap sections. Distinguish implemented behavior from target design and
historical snapshots. Adopt the production graph, readiness dimensions, and
validation tiers without changing authentication or granting workers extra authority.
Synchronize affected canonical Markdown, DOCX, and manifest hashes together.
Define protection and review ownership for production schemas and milestone gates.

Reconcile the unattended delivery specification with canonical section 21,
including operating charter authority, prototype versus final-presentation gates,
save-preserving local promotion/rollback, supervisor host requirements, and the
existing publication/deletion rules. Synchronize any resulting controlled edits
with their DOCX and manifest. Prototype media allowances and additional runtime
permissions take effect only through this adoption; do not assume a planning
document has granted them. Protection-code changes remain separate tickets.

**Acceptance:** reference-package self-test and independent review agree on the
exact package; every normative routing statement resolves to one reviewed policy;
the new design is discoverable from the canonical architecture. Preserve the
current configured routing pending that reconciliation.

**Dependency:** none. **Scope:** controlled references and continuity only; any
needed protection-code change is a separate bounded coordinator ticket.

## 2. Inventory the game and establish production records

**Outcome:** a machine-readable view of what exists and what is missing.

Start with strict node/requirement/dependency schemas and an inventory importer.
Read campaign entry points, all current scenario files (21 at the inspected baseline), transition edges,
unit IDs, asset references, and existing contracts. Record structural findings
separately from installed-engine evidence; never label imported nodes complete.
Create the trilogy outline, faction/character bible, and representative mission
records through bounded design tickets and independent creative review.

**Acceptance:** every existing scenario and published compatibility ID is
accounted for; duplicate IDs, broken references, production cycles, and unsafe
paths fail; campaign transition graphs are shown separately. Repeated import of
unchanged sources produces the same inventory. Readiness defaults to unknown
where evidence is absent. Existing records are preserved on a rejected import.

**Dependency:** package 1. **Likely paths:** new `production/` schemas/records,
a bounded `agent/coordinator/production_inventory.py` module and its tests.
Keep data migration and dashboard display in separate tickets.

## 3. Prove engine-observed acceptance

**Outcome:** demonstrate the difference between retained source and real behavior.

Extend the existing installed-engine harness in an isolated capability spike.
Choose one small existing mission, such as Restore the Beacon, and implement
fixtures for legal victory, wrong-unit rejection, required-unit death, timeout,
and save/reload before the objective. Record whether each fixture exercises a
handler directly or reaches it through legal gameplay. Detect intentional broken
fixtures. Do not assume headless actions/replay APIs before validating them.

**Acceptance:** observations bind to exact build/scenario/difficulty/seed and
test harness; deliberately broken behavior fails; unexercised behavior stays
pending; instrumentation is absent from the distributable. A process remaining
alive cannot produce PASS by itself.

**Dependency:** package 1; can proceed alongside inventory after role/path
coordination exists. **Likely paths:** focused extensions near
`scenario_launch_selftest.py`, new test fixtures, one selected scenario's test
contract. Scenario gameplay changes require a separate repair ticket if defects
are found. Python executes all tests; workers propose and edit scoped artifacts.

## 4. Add evidence identities and scalable contract coverage

**Outcome:** readiness remains trustworthy as content grows and shared rules change.

Introduce a versioned evidence envelope, requirement-to-source dependencies, and
deterministic stale-state calculation. Add a bounded contract index with per-mission
files, migrating the existing 47 contracts without dropping any IDs or assertions.
Keep compatibility with historical ticket evidence during a documented transition.
Raise capacity deliberately beyond the current 100-contract ceiling using per-file
and aggregate bounds; do not accept unlimited data.

**Acceptance:** changes to shared rules invalidate affected mission evidence;
unrelated documentation leaves it reusable; harness/engine changes invalidate the
appropriate results; unknown dependencies take a conservative path. Missing,
duplicate, stale, and unsupported evidence cannot satisfy a requirement. Negative
fixtures and a pre/post-migration assertion inventory prove no coverage was lost.

**Dependency:** packages 2 and 3. **Likely paths:** focused coordinator evidence
module, `gameplay_contracts.py`, contract index/data, integration tests. Split
schema, migration, and consumer wiring into separate contracts.

## 5. Make the scheduler close product gaps

**Outcome:** the next ticket advances a named playable milestone.

Add a pure deterministic gap selector that reads the production graph and evidence
and feeds the existing `autonomy.py` proposal/validation path. Preserve resume-first
behavior, recorded-contract reuse, queue ownership, original acceptance, hard stops,
recovery limits, and publication controls. Extend the ticket schema only through
validated adapters. Add budgets and no-progress detection without weakening gates.

**Acceptance:** fixtures prove repair/resume precedence, dependency ordering,
stable tie-breaking, rejected overlaps, stale-design rejection, and zero planning
calls for an already valid contract. A blocked asset does not become an art PASS.
A global safety pause still prevents scheduling. Restart cannot duplicate an
external action or erase the original ticket identity.

**Dependency:** packages 2 and 4. **Likely paths:** new selector module plus narrow
`autonomy.py`, ticket validation, and dashboard tests. Start in read-only shadow
mode: compare recommendations to the actual approved backlog before enabling it.

## 6. Finish a production proof using existing missions

**Outcome:** 3-5 missions demonstrate the intended final experience together.

**Early checkpoint 6A:** select and connect three existing missions under the
reviewed playable-prototype profile. Require legal objective completion, defeat,
save/load and carryover evidence, exact packaged installation, stable launch, and
rollback. Declare the tested difficulties and seeds. Temporary original assets
require prior profile approval and all applicable technical/full-state gates;
missing final presentation remains unverified. This checkpoint does not close
the full production-proof milestone.

**Checkpoint 6B:** complete the full 3-5 mission proof below, including final
representative assets and independent playtest dispositions.

Select a coherent sequence using the inventory and creative outline. Cover ground
combat, a meaningful specialist objective, space combat, and an actual carryover
transition. Assess current maps and rosters before selecting. Improve tactical
choices, original story, objectives, difficulty, readable range/support behavior,
and final representative assets. Extract shared services only where duplicated
behavior warrants them. Preserve published IDs and save behavior.

Each mission has a separate design contract followed by bounded mechanics, map,
narrative, asset, and integration tickets as needed. Keep a visible asset handoff
queue under the existing 13-file policy. Original audio production is explicit;
do not silently substitute licensed content or fabricate a completion status.

**Acceptance:** legal play can complete the sequence; defeat and reload cases
pass; carryover remains usable; required visuals resolve and read well in-engine;
independent playtest findings have dispositions. The owner reviews the combined
experience at the milestone, rather than approving every routine code edit.

**Dependency:** design and content work start after packages 2-4; 6A delivery also
requires U2 and U5, including their dependencies. Package 5 automates selection
when ready. Checkpoint 6B builds on 6A with the full quality gates. This package
must start as soon as adequate inventory and probes exist; do not wait for a
complete dashboard redesign. **Scope:** one bounded content area per ticket.

## 7. Expose readiness and expand to the vertical slice

**Outcome:** the owner can see and play progress toward 6-8 polished missions.

Show mission readiness by dimension, build identity, playable entry points,
critical blockers, pending art, actual playtest evidence, and costs. Read status
from verified backend state. Expand the proof's systems and quality bar to the
vertical slice; cover hero/vehicle/support identities and more varied objectives.

**Acceptance:** UI cannot turn a structural pass into a runtime pass; stale data
is visible; readiness changes are explainable by evidence; existing authorization,
pairing, cancellation, and error handling remain intact. The slice exits only
when its required content and quality gates are satisfied.

**Dependency:** packages 4-6B and U6 for unattended operation. **Scope:** separate dashboard tickets and scenario
production contracts. Add concurrency only if measured throughput justifies its
new leases, reconciliation, and integration tests.

## 8. Complete campaigns and qualify the release

**Outcome:** a coherent trilogy with verified installation and playthroughs.

Finish Campaign I before using its production pattern for the rest of the trilogy.
Campaign II's existing missions are assessed and integrated, not automatically
accepted. Design Campaign III's arc before registering and populating it. Track
the approximately 25-30 mission target as scope, not as a pressure to add empty maps.

Run full progression, difficulty and carryover checks, held-out balance seeds,
save/load and supported upgrade cases, final presentation/audio review, localization
readiness, and clean-userdata package tests. Preserve exact release identities,
credits/provenance, and compatibility notes. Public add-on-server upload remains
a separate authorized release action.

**Acceptance:** every required product node is verified on the release candidate;
no blocking defects or unresolved required asset handoffs; all three campaigns
reach their intended ending; installation works without development tools.

**Dependency:** package 7 and all campaign-specific prerequisite contracts.

## U1. Validate the unattended operating charter

**Outcome:** one reviewed run definition resolves routine decisions and gives
the coordinator enforceable limits and existing-authority references.

Implement the bounded schema and adapters for delivery-specification section 2.
Bind milestone/design/reference identities, profile, allowed actions/paths,
capabilities, decision defaults, budgets, completion reserve, expiry, and
revocation. Reuse the current authorization mechanism where it already permits
continuous publication. Inspect that mechanism before adding another state store.

**Acceptance:** reject absent limits, stale design/reference identity, unauthorized
actions, invalid profiles, and unresolved critical prerequisites. Revocation or
expiry blocks new affected actions after restart; an already attempted external
action is reconciled safely. Routine authorized actions require no extra prompt.
Budget reservations and actual usage persist across interruption. Workers cannot
modify the charter or accepted outcomes to make a candidate eligible.

**Dependency:** 1 and 2. **Scope:** separate schema/protection, adapter, and
authorization integration tickets. The document is not an executable charter.

## U2. Deliver and preserve verified player builds

**Outcome:** the owner can launch the latest eligible immutable build, even while
development is broken or stopped.

Implement delivery-specification section 3 using the existing publisher and
installed-engine boundary. Add a bounded build manifest, reproducible package
allowlist, isolated package validation, single-owner promotion journal, atomic
pointer, save isolation, rollback, and eligibility revocation. Split build storage,
promotion, launcher migration, and minimal owner display into separate tickets.

Inspect `agent/coordinator/scenario_launch_selftest.py`,
`agent/dashboard/approval_queue.py`, and
`agent/runtime/Play-WesnothStarWars.cmd`. Keep local experimental launch available
under an explicit developer entry point. The normal launcher resolves verified
bytes and never silently stages uncommitted files.

**Acceptance:** before/after-interruption fixtures never expose a partial build;
altered bytes, unsupported manifests, stale requirements, and failed package tests
cannot be promoted. Active games remain pinned to their selected build. Rollback
preserves saves and reports incompatibility. A failed candidate retains its
eligible predecessor; no valid baseline means an honest empty state. The player
entry point works offline with the controller stopped. Required deletion and
publication authority is preserved.

**Dependency:** 3, 4, U1. A one-mission test package can prove the mechanism before
6A; that test does not satisfy the three-mission delivery checkpoint.

## U3. Make supervision and host preflight durable

**Outcome:** supported interruptions resume safely without duplicate workers or
external actions, and unsupported host conditions are explicit.

Implement delivery-specification section 4 around the current controller. Add
single-writer ownership, versioned checkpoints, action intent/reconciliation,
owned-process deadlines, and safe update/restart boundaries. Preflight storage,
engine, existing authentication availability, budgets, and desktop capabilities.
Do not change host login/power/security settings implicitly.

**Acceptance:** restart fixtures preserve immutable ticket identity and state
revisions; duplicate owners and PID reuse cannot affect unrelated processes;
completed pushes/merges are reconciled rather than blindly repeated. Qualify
required engine GUI checks under the supported locked-session configuration.
Missing capabilities block their requirements without fabricating PASS. Declare
whether automatic startup is configured before claiming recovery after reboot.

**Dependency:** U1. **Scope:** separate state/ownership, process recovery, and
host-preflight tickets; protect the controller from ordinary content workers.

## U4. Integrate bounded recovery and progress decisions

**Outcome:** ordinary recoverable failures are handled automatically while
existing hard stops and budgets remain effective.

Map the delivery-specification section 5 responses to existing failure classes.
Persist retry timing, failure fingerprints, in-flight budget reservations, and
verified-progress windows. Add completion-reserve admission checks to selection.
Keep original contracts, repair counters, global pauses, and publication ordering.

**Acceptance:** quota waits are bounded; fallback/circuit exhaustion and the
existing two-attempt/three-failure boundaries remain stops; restart cannot reset
usage or retries. Independent work bypasses only blockers already eligible under
policy. Repeated no-progress outcomes produce one bounded planning review and a
precise preserved stop. The completion cutoff prevents expansion without skipping
mandatory validation. A model-generated success message cannot satisfy progress.

**Dependency:** 5, U1, U3. **Scope:** deterministic policy tests first, then narrow
scheduler/authorization integrations. Any changed stop policy requires package 1
governance before activation.

## U5. Prepare an asset route that can finish unattended

**Outcome:** the selected milestone has a feasible media plan before it starts.

Apply delivery-specification section 7. Inventory approved original assets and
reuse the existing art queue by stable IDs and brief hashes. Default to prepared
assets, retaining the 13-file contract. Require explicit profile approval for
temporary original media. Record final-presentation and audio gaps independently.

**Acceptance:** preflight finds a missing required interactive handoff before
dispatch; prototype evidence cannot verify final art; no duplicate asset status
store exists; a complete prepared set can traverse the existing governed import.
Unavailable required media blocks the affected milestone honestly. An unattended
provider adapter is optional, separately authorized work, not an assumed service.

**Dependency:** 2, U1. **Scope:** inventory/capability checks and bounded asset
contracts; original media creation and imports remain independently reviewed.

## U6. Qualify unattended delivery on the first sequence

**Outcome:** a real bounded session leaves an improved playable build without
routine owner intervention, and failures preserve safe state.

Execute the full matrix in delivery-specification section 8 through deterministic
test orchestration. Include accelerated isolated fault fixtures and the proposed
12-hour real trial after its explicit resource limits are approved. Use the
actual host, engine, session configuration, reviewed input state, and charter.
Capture exact evidence and unsupported conditions; do not run faults against
unowned processes or player saves.

**Acceptance:** the matrix passes; at least one real requirement improvement is
promoted and launchable with development services stopped; candidate failure or
interruption preserves the eligible player build and saves. No unplanned routine
approval, repeated failure loop, duplicate side effect, or exceeded budget occurs.
A safe stop alone does not satisfy successful unattended delivery. Final owner
status distinguishes new build, retained build with blocker, and no eligible build.

**Dependency:** 5, 6A, U1-U5. **Scope:** qualification fixtures, bounded trial,
and retained report. Any discovered defect returns to its responsible bounded
contract; rerun only affected gates plus the required final trial coverage.

## Review and validation of this design change

The architecture draft authored this plan and `TARGET_ARCHITECTURE.md`. The
companion governance change reconciles the controlled Markdown and DOCX
references, manifest, and continuity ledger. The deterministic coordinator
should check UTF-8, relative document links, whitespace, bounded scope, and
independent consistency with the controlled package. No gameplay test result
should be attributed to this documentation and governance change.

The architecture was checked against the inspected source and the reference
package. Its engine automation mechanisms, quality targets, and future schemas
remain implementation work with explicit acceptance above.
