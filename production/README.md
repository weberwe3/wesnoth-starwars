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
preprocessor, isolated legal first-move probes for missions 2 and 3, an isolated
legal Ground Extraction objective route, and the first-scenario GUI startup
probe. It rechecks both the staged copy and immutable candidate after the run
and writes a bounded raw result under ignored runtime storage. Five deterministic
wrapper fixtures pass locally. `extraction_route_probe.py` retains the source
scenario body and AI side, issues six player moves on successive test-mode turns,
and accepts victory only at the required hex with no failed WML assertion. Run
it with `--engine <installed-wesnoth-executable>`. It does not establish normal
GUI play, transition, carryover, defeat, or save/load.

The tracked `package_engine_baseline.json` records an exact 108-file candidate
from integrated commit `8fe5f506fad1aadba3dda9edcf72e98d7a85af8a`.
Package integrity, preprocessing, both isolated first moves, and the isolated
Ground Extraction objective route passed with installed Wesnoth 1.19.27. The
route reached its objective and exited 8. The GUI probe started and survived,
but no `Game` context was observed. The combined result failed and eligibility
remains `candidate_unverified`; normal play and promotion are unverified. The
ignored raw JSON SHA-256 is
`74c44ee38debc9a121b45faae6e3d25718e749b68aca47e8a805f0521bd40cdb`.
Earlier process-survival evidence was invalidated after discovering that
`--skip-story` was unsupported and a title screen could remain alive.

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

The clean integrated run on commit
`7e34d4455b72629921e68cf38c51289ff7d37e12` passed both checks with
Wesnoth 1.19.27 (exit 0 each). Its ignored raw JSON SHA-256 is
`1126a8800b49f198f52ad59e0a41c2a6214305c421f5f33c7475d8af33119b57`;
the engine SHA-256 is
`120dfe63c701de2229e0c4665349ea116ed79ee1772d5275f04b1a7bc32feaae`;
the probe SHA-256 is
`d2c3bc2e11060a1353cb24ed49125ffd8a7ab7dbe8641becb90284b431649030`.

The next engine check exposed an invalid early victory: separate
`[filter_location]` blocks in `moveto` events did not constrain the moving
unit, and Ground Extraction won when its hero first moved to (4,2). Space
Interception used the same pattern for its escort victory and two enemy
breakthrough defeats. Those destinations now live inside each moving-unit
`[filter]`. Ground Extraction's hero starts on a castle route instead of being
boxed in by allied units; its map has a grass approach to extraction, and the
turn-five reinforcement no longer occupies the destination. The reproducible
probe now requires legal first moves, exact positions, initialized variables,
and no early victory or conditional-test warning for both missions. This is
first-move evidence only. The earlier integrated load record above is a
historical result for the earlier source/probe hashes; it must not be reused
for the changed sources. A clean integrated rerun is still required.

That rerun used integrated commit
`10d6fbcdc2a0afde4511e08cea5ded0e4c9ae5c0` and Wesnoth 1.19.27.
Both first-move fixtures exited 0 with no failed assertion or premature
victory. Ignored raw JSON SHA-256:
`dd743f9a3ff316cd5009f8cc698e5dcd6cebc307c2eb6901a399b05cbac0bcd1`;
probe SHA-256:
`79c37b41c7b8dc2c1ad82f4a39cd891e1d3d8627fa011d7b358aaf68b2241519`;
mission 2 source SHA-256:
`d2bf94ae2379439f77f1545c96347dcc8b5c32360ff7b2ac8f5f51822d90d587`;
mission 3 source SHA-256:
`5b6890697a1a8b86131efab21bced3c4db4ddc3c977c82ffa336c5a4206e4521`.
The installed engine SHA-256 remains
`120dfe63c701de2229e0c4665349ea116ed79ee1772d5275f04b1a7bc32feaae`.

The same clean commit re-ran the protected Restore the Beacon objective
fixture: current/pass, raw SHA-256
`e3e7f2096b80554a61cc6202d85834c779072b775d4a1ee1e18f62284490cf1b`,
envelope SHA-256
`7eabd0803f7538ea21581f449e758dff6256ac7a65022b5a9cb2a925798cbc8e`.
That controlled fixture remains narrower than ordinary mission play.

The mission probe now rejects positive pass/victory/defeat markers whenever
the same engine log reports a failed WML assertion. An isolated longer-route
diagnostic exposed this case: the engine printed a victory test marker although
its victory-event position assertion had failed. Intentional negative fixtures
still require their failed assertion. A player-command error also rejects the
result. This harness change stales previous requirement envelopes until a
new direct run binds the revised probe hash.

The clean integrated rerun on
`ff54bc7f9e5b3805f25f3539c9d209cab75b7afe` used Wesnoth 1.19.27 and
returned current/pass under the stricter rule. Ignored raw SHA-256:
`d4dfd6a4b50fcc929ccece0ac3245e34bdd9e5df94dc5fd0acf763bf43cae48a`;
envelope SHA-256:
`e17cccd96b145b7cbc41bb1585ea416cab3eeb0173acf69f145e9dbc3d5ea169`.
