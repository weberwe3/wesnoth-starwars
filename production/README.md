# Production source inventory

`inventory.py` imports a bounded, deterministic structural view of the two
registered campaigns, all current scenario IDs, transition edges, custom unit
type IDs, local and external asset references, and gameplay contract IDs. It is deliberately
separate from Wesnoth runtime evidence: every imported record is structural,
and runtime/play readiness is `unknown` or `unassessed` until the installed
engine probe records evidence.

The importer uses only the Python standard library. It validates duplicate
IDs, unknown campaign entry points and transitions, bounded input, local path
and symlink safety, schema identity, and cycles in `production_dependencies`.
Scenario transitions are retained as a separate graph and are allowed to loop.
Source SHA-256 records cover campaign, scenario, unit, utility, and Lua sources,
gameplay contracts, and verified local map and
image references so `--check` detects content-only edits. Stock art paths
that are not present in the add-on are recorded as unresolved external references;
they are not treated as verified local assets. A missing `sw-` project art path
is rejected instead of being classified as stock art.

Generate atomically with `python production/inventory.py`. Use
`python production/inventory.py --check` to fail on a stale record without
writing it. A rejected import leaves the previous inventory bytes untouched.

## Installed engine capability spike

Run `python production/engine_probe.py --engine <installed-wesnoth-executable>`
to stage two WML fixtures in temporary isolated userdata. The first issues a
one-hex move with Wesnoth's `[do_command]` test action and checks the resulting
unit position. The second deliberately asserts the wrong position and must
produce the engine's `FAIL TEST` diagnostic and exit code 1. The detailed local
run record is written under ignored `agent/runtime/`; the small observed
baseline is `engine_capability_baseline.json`.

This proves custom test fixture loading, test-mode action injection, and
negative assertion detection for the recorded engine binary. Mission-specific
evidence is described below; this generic spike alone does not execute a
project mission.

## Restore the Beacon movement probe

`mission_probe.py` copies the existing mission and add-on into isolated
userdata. It changes the copy's root tag to Wesnoth's test tag and adds bounded
observation events; the source mission stays untouched. Its load, movement
point, first legal move, and deliberately wrong origin assertions distinguish
an actual move from a fixture that merely exits successfully. Run with
`--temporary-movetype-fix` only as a diagnosis of a possible repair; that mode
replaces movement type names in the temporary copy and is never evidence that
the shipped source was corrected.

The original defect baseline is recorded in `mission_capability_baseline.json`:
the mission failed the first legal move and let the wrong-origin fixture pass.
The temporary movement type repair reversed both outcomes. The follow-up
source change replaced all invalid project movement type names with registered
installed-core names; `movement_repair_evidence.json` records the passing
real-source move and failing wrong-origin fixture.

## Restore the Beacon objective and filter probe

Run `python production/mission_probe.py --engine <installed-wesnoth-executable>`
to exercise the current source in isolated Wesnoth test mode. The default set
checks mission load, the engineer's movement point, a legal first move, a
deliberately wrong origin assertion, a six-move route to the terminal, and a
commander move onto the terminal that must not win. The runner rejects an
unknown scenario or a WML/configuration error even if Wesnoth also prints a
`PASS TEST` line; an early fixture draft exposed that false-positive pattern.

`mission_legal_path_evidence.json` records the exact scenario, unit, fixture,
script, inventory, and engine binary hashes and the observed exit codes.
The objective route retains the source engineer-only `moveto` filter and
`[endlevel]` action, but sets the enemy controller to `null` and removes the
terminal dialogue **only in the temporary fixture**. Those controls make the
objective test deterministic and avoid a test-mode display stall. The negative
fixture stages the commander one hex from the terminal and uses a normal
player move for the final step. The shipped mission content is unchanged by
this probe.

`mission_defeat_evidence.json` extends the default run with a normal ten-turn
timeout. The temporary timeout fixture disables enemy turns, asserts both
required units remain present, and logs turns 1 through 10 before the engine
returns its defeat result. Direct `[kill]` actions with `fire_event=yes` show
defeat after the engineer or commander dies. Removing the engineer's source
`die` handler only in a negative fixture makes the same injected death no
longer defeat the player, which identifies that rule as causal. Direct death
injection does not establish legal combat death; commander defeat may also be
enforced by the engine's generic leader rule.

Active-AI win reliability, the terminal dialogue, legal-combat death,
transition/carryover, save/reload, and a player-ready build remain unverified.

## Evidence identity core

`evidence.py` and `schemas/evidence_envelope.schema.json` define a bounded
versioned record for one accepted requirement and engine observation. The
record includes the candidate commit/tree, requirement revision, scenario,
probe, exercise type, difficulty/seed, exact engine binary, named source and
harness dependencies, the ignored raw artifact digest, exit code, and bounded
observations. Runtime artifacts stay under ignored `agent/runtime/`.

`assess_freshness` compares the envelope with an accepted requirement snapshot
and current bytes. Changed shared rules, harness, engine, requirement identity,
or artifact make it stale; a missing artifact or unknown dependency is not
reused. Unrelated documentation leaves an otherwise current record current.
The result is a freshness check, **not a readiness decision**: the protected
coordinator must still prove the run came from its authorized validation path
and that the observed behavior satisfies the requirement. Existing historical
ticket evidence is not migrated or reinterpreted by this module. Consumer
wiring and transitive dependency registration remain separate package-4 work.

Run `python production/evidence_selftest.py` for the focused freshness controls.

## Indexed gameplay contracts

`addons/Star_Wars_Thrawn_Trilogy/tests/gameplay-contracts.json` is the v2
authoritative index. It names five v1 contract shards under the adjacent
`gameplay-contracts/` directory. The migration retained all 47 IDs and their
complete assertions as JSON values; a pre/post comparison against the prior
main verified equality. The index requires sorted, unique, safe shard names,
an exact directory listing, at most 32 shards, at most 100 contracts per shard,
and at most 1,000 contracts overall. Duplicate IDs, omitted files, symlinks,
unsupported versions, and invalid JSON fail closed. The legacy v1 single-file
form remains readable for historical fixtures; the repository's current source
of truth is v2.

The declared-contract validator, dashboard completion check, ticket path scope,
and production inventory now read the index. Inventory hashes the index and
every shard so a changed assertion invalidates its snapshot. Add coverage to
the relevant shard; add a new sorted index entry only for a new shard. Run
`python production/contract_store_selftest.py`,
`python agent/coordinator/scenario_launch_selftest.py`,
`python agent/dashboard/test_dashboard.py`, and
`python production/inventory.py --check` after contract changes. The protected
evidence-to-readiness consumer remains separate package-4 work.

## Unattended charter admission core

`charter.py` validates a bounded proposed run definition against the current
controlled scope/orchestration manifest and production design bytes. It also
requires an independently accepted digest, a live matching continuous
publication authorization ID for governed publication, and a separate live
promotion approval ID before local build promotion can be admitted. Expired,
revoked, malformed, over-budget, and widened drafts fail closed. Only prepared
original assets are accepted by this initial schema. The module does not create
an approval or start automation; there is no active reviewed charter yet.
Run `python production/charter_selftest.py` for admission and rejection cases.
Budget persistence, authorization adapter, and selected-milestone charter review
remain U1 work.

`budget_ledger.py` adds an atomic, single-controller resource ledger keyed to
the accepted charter digest. It persists each action's reservation before work,
records actual usage once, and preserves unsettled reservations across restart.
Expansion closes at the charter's completion cutoff while integration and
delivery can use the reserve. A measured overrun is recorded and blocks further
reservations. Reopening a missing or corrupt ledger fails closed; only explicit
first activation may create one. The ledger does not release an unsettled
reservation automatically, because the external action may have occurred before
interruption. Cross-process ownership, action reconciliation, and control-state
admission are still required before unattended scheduling. Run
`python production/budget_ledger_selftest.py` for eight restart/exhaustion cases.

## Immutable player-build candidates

`build_store.py` stages the exact add-on files from a named committed ancestor
of `origin/main` into an ignored, immutable candidate directory. Its allowlist
includes WML, maps, scripts, images, translations, and audio; it excludes tests,
controller files, raw logs, and development art prompts. A bounded manifest
records the source commit/tree, every file hash and length, and an aggregate
package digest. Staging completes in a temporary directory before an atomic
same-filesystem directory rename. Reopening a candidate verifies its complete
file set; changed or extra bytes, symlinks, unsupported manifests, and
unpublished commits fail closed. `python production/build_store_selftest.py`
covers those cases with four Git fixtures.

A real main-ancestor snapshot was staged locally with 108 game files and
`candidate_unverified` eligibility. This is a packaging mechanism only: no
installed-engine package validation, promotion journal, current-build pointer,
offline player launcher, save compatibility, or rollback policy is provided by
this module. Those are subsequent U2 contracts.

`validate_package.py` takes one candidate, verifies it, copies its exact game
files into isolated temporary userdata, then calls the existing installed-engine
preprocessor and first-scenario GUI startup probe. It rechecks both the staged
copy and immutable candidate after the run and writes a bounded raw result under
ignored runtime storage. Three deterministic wrapper fixtures pass in CI.
The tracked `package_engine_baseline.json` records the corrected real result
for the 108-file candidate: preprocessing exited 0, but no `Game` context was
observed during the GUI probe. The package is not loadability-qualified or
promotable. Earlier process-survival evidence was invalidated after discovering
that `--skip-story` was unsupported and a title screen could remain alive.

## Direct scoped requirement observation

`requirements/restore_beacon_objective.json` defines only the controlled
Restore the Beacon test-mode objective fixture. `requirement_runner.py` calls
the installed-engine probe itself for the engineer route and staged wrong-unit
negative case, checks both exact verdicts, and binds the raw artifact to a v1
evidence envelope. Dependencies conservatively include every hashed add-on
inventory input plus the requirement, inventory, runner, and freshness code;
an invalid source inventory blocks the run. The outcome may be called a scoped
observation only during that direct protected invocation. Reopening an envelope
later gives freshness information, not proof of runner origin or mission
readiness. Five focused tests cover matching outcomes, negative failure, engine
identity, changed source, and unsupported requirement cases.

The first clean integrated run used commit
`664213f8a797db5ce5238af1660bcb1b94f2a05e`, tree
`de701e61eb25fd3a394a03db16a09f67eaed3649`, and installed Wesnoth
1.19.27. The controlled engineer route reported victory/exit 8 and the staged
wrong-unit case reported pass/exit 0. The direct runner returned current/pass.
The ignored raw artifact SHA-256 was
`11a03f295a05fbc87732fcf5bd9a33ff629ba2860a980cbfc39bbd2477d18235`;
the ignored envelope SHA-256 was
`b30b9ad5bd792fa4a2afb0a643244ee0a277775ed8b5fca405c014caa6a824a9`.
This is a test-mode objective observation, not a normal-AI playthrough, GUI
campaign-entry result, save/load result, or player-build promotion.

## First-sequence engine load diagnostics

`sequence_load_probe.py` transforms each source body for Space Interception
and Ground Extraction into an isolated Wesnoth `[test]`. The added assertion
checks a required unit and the initialized turn-limit variable. Installed
Wesnoth 1.19.27 passed both checks after replacing Ground Extraction's
unsupported `Cc` tiles with core `Ch` castle, giving its commander and hero
distinct start hexes, and replacing unsupported `[command][variable]` event
actions with `[set_variable]`. The Ground Extraction terminal action is now
directly in its `moveto` event. The probe saves source, fixture, engine, and
probe hashes in ignored runtime output. Its isolated loader omits successor
scenarios, so successor warnings in its logs are fixture limitations. Initial
state success does not verify victory routes, actual transitions, carryover,
defeat, save/load, or package launch.
