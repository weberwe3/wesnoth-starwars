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
