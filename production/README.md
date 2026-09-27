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
negative assertion detection for the recorded engine binary. It does not
execute a project mission. Legal objective victory, wrong-unit rejection,
defeat paths, transitions, carryover, and save/reload remain pending engine
tests before any playable-delivery claim.
