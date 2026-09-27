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
