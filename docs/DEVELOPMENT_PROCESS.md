# Development Process for LLM Contributors

This is the working method used to build the three rebuilt campaigns
(Heir to the Empire, Dark Force Rising, The Last Command) and to repair the
dashboard's validation. Follow it step by step. It sits below the controlled
references: if anything here conflicts with `AGENTS.md`,
`docs/PROJECT_SCOPE_AND_FEATURE_SET.md`, or
`docs/AGENT_ORCHESTRATION_FUNCTIONAL_SPEC.md`, those documents win; stop and
report the conflict.

## 1. Before you start

1. Read, in order: `AGENTS.md`, the two controlled references,
   `docs/PROJECT_CONTINUITY.md` (especially the newest addenda at the end),
   and `docs/WORKTREE_LESSONS.md`. Every lesson there is a mistake someone
   already made; do not repeat one.
2. Check live state rather than trusting documents:
   ```bash
   cd /home/willj/projects/wesnoth-starwars
   git fetch origin && git status --short --branch && git log --oneline -5 origin/main
   gh pr list
   curl -s http://127.0.0.1:8766/healthz
   ```
3. Never work on `main` directly. Leave the main checkout's working tree
   alone: the dashboard's art import publishes from it, and it refuses to run
   if unrelated files are modified there. The owner's untracked
   `docs/AI_HANDOFF_REFERENCE.md` is expected; do not touch it.

## 2. Tools and environment

| Tool | Location | Use |
| --- | --- | --- |
| Linux Wesnoth 1.19.27 | `~/opt/bin/wesnoth-linux` | All automated engine and GUI checks (SDL offscreen video, dummy audio). The same version as the player's Windows install. |
| Windows Wesnoth 1.19.27 | `C:\Program Files (x86)\battle for wesnoth\wesnoth.exe` | The player build. Used by the player launcher check. |
| Image Python | `~/opt/swtools/bin/python` | Has Pillow; runs the map previews and art tools. System `python3` has no Pillow. |
| Dashboard | `http://127.0.0.1:8766`, started by `agent/dashboard/start-dashboard.sh` | Codex art generation and governed art import; automation of small Codex tickets. |
| Codex CLI | resolved by `ticket_runner.resolve_codex_executable()` | Image generation only through `agent/coordinator/codex_art.py`. ChatGPT-account auth only, never API keys. |

How the Linux engine was built (if you need to rebuild it) is in
`production/linux_engine/README.md`.

## 3. The per-change loop

Every change, small or large, follows this loop.

1. **Isolated worktree from current `origin/main`:**
   ```bash
   git fetch origin
   git worktree add ~/projects/wsw-wt/<topic> -b <kind>/<topic> origin/main
   ```
   Use `content/…` for game content, `fix/…` for repairs, `docs/…` for
   documentation.
2. **Inspect before editing.** Read the files you will change and the engine
   source or data when behavior matters. The engine source tree is
   `~/opt/wesnoth-1.19.27` (`src/`, `data/core/`, `data/schema/`). Check
   claims there; do not guess about engine behavior.
3. **Make the change** (Sections 4–6 describe the content recipes).
4. **Run the checks** (Section 7). Do not claim anything passed that you did
   not run.
5. **Diagnose failures from evidence**: the engine log, the start-of-scenario
   save, or the engine source. Fix the smallest confirmed cause and rerun. Add
   a `docs/WORKTREE_LESSONS.md` entry (symptom, cause, resolution, prevention)
   for every confirmed and repaired failure.
6. **Commit** with the repository author and the attribution line:
   ```bash
   git -c user.name=weberwe3 -c user.email=weberwe3@users.noreply.github.com commit
   ```
   End the message with `Co-Authored-By: Claude …` per the active attribution
   rule. Never amend or force-push a pushed commit; add a new commit instead.
7. **Push the branch and open a PR** with `gh pr create`. In the body, state
   what was verified and what was **not** (for example, scripted wins are not
   proof of legal-move routes or balance).
8. **Wait for CI on the exact head commit**, then squash-merge:
   ```bash
   H=$(git rev-parse HEAD)
   gh run list --branch <branch> --limit 1 --json headSha,status,conclusion
   # proceed only when headSha == $H and conclusion == success
   gh pr merge <N> --squash --subject "<title> (#<N>)"
   ```
9. **Update local `main`** by fast-forward only:
   `git fetch origin && git merge --ff-only origin/main`.
10. **Post-merge checks** for any add-on change: run the player-launcher check
    against the full merged SHA (Section 7), restart the dashboard so it runs
    the merged code, and add a short addendum to `docs/PROJECT_CONTINUITY.md`
    for meaningful milestones.

## 4. Building game content

The three campaigns are produced by generators plus hand-written scenario
WML. Reuse them; do not hand-edit generated files.

### 4.1 Design record first
Write `production/campaigns/<campaign>/DESIGN.md` before code: story spine
(broad Legends plot concepts only), new roster entries, a mission table
(id, name, map size, turns, point of view), and each mission's win and lose
conditions.

### 4.2 Units
- Add units to `ROSTER` in `production/tools/gen_hte_units.py` (one `U(...)`
  per unit, `file=` naming the output `units/<file>.cfg`), then run
  `python3 production/tools/gen_hte_units.py`. The generator writes all 13
  animation-frame references literally, which the art validator requires.
- Ids use the `sw_` prefix; player-facing names use Legends terminology.
- Damage conventions: blasters `fire`, lightsabers `arcane`, ion `cold`
  with `slow`, torpedoes and bombs `impact`. `max_range > 1` only on player
  units: the AI does not plan multi-hex attacks.
- Force abilities and deflection must keep the `sw_ysalamiri_zone` filter.

### 4.3 Maps
- Write a `production/tools/gen_<campaign>_maps.py` builder using
  `hte_mapkit.HexMap` (fills, discs, rects, hex-accurate paths, scatter,
  `start(side, x, y)`), and record every gameplay hex in `keys(...)`.
- Every side that has a leader needs a map start position; a missing one
  means the leader is never placed.
- Preview before using:
  `~/opt/swtools/bin/python production/tools/gen_<campaign>_maps.py --preview <dir> --keys`.
- Only use terrain codes that exist in the installed engine's
  `data/core/terrain.cfg`, or the add-on's `utils/hte_terrain.cfg`
  (`Qsp` open space, `Qsa` asteroids, `Qsd` deck, `Qsk` hangar keep, `Qsc`
  launch rail).

### 4.4 Scenario checklist (every scenario)
Copy an existing scenario from the same campaign and keep all of these:

- `map_file=<name>.map`, `{QUANTITY turns E N H}`,
  `victory_when_enemies_defeated=no`, a time-of-day macro, and an original
  `[story]`.
- Side 1: `save_id=sw_player`, `persistent=yes`, `defeat_condition=never`,
  and the leader defined in `[side]` (`id=sw_hero_…`, `canrecruit=yes`).
- Side numbers must be contiguous from 1.
- At the start of `prestart`: `[set_recruit] side=1` with this scenario's
  list, then `[modify_unit]` setting the leader's `canrecruit=yes`.
- `{SW_STASH_HEROES …}` for heroes who are not in this mission, then
  `{SW_HERO id type name x y}` for each participating non-leader hero. For
  space missions, `[transform_unit] id=sw_hero_luke transform_to=sw_hero_xwing_luke`
  here and transform back at victory.
- Displayed `[objectives]` in prestart; each objective is implemented by an
  event.
- Victory comes only from scenario events, using
  `[endlevel] result=victory … {NEW_GOLD_CARRYOVER 40}`. A `victory` event
  must call `{SW_VICTORY_HOUSEKEEPING}` and remove any one-mission allies
  from side 1 (`[store_unit] … kill=yes`).
- `{SW_HERO_DEATH_IS_DEFEAT id}` for every hero whose loss ends the mission.
- The final scenario uses `next_scenario=null`.
- WML pitfalls already hit: no `$( … )` formulas inside parenthesized macro
  arguments; `[variable]` has no `modulo` (compute it with `[set_variable]`
  first); `name="turn N"` for turn events.
- Register the campaign in `_main.cfg`: a `[campaign]` entry with three
  `[difficulty]` levels and a matching `#ifdef` block that loads
  `hte_terrain.cfg`, `[+units]`, the macro files, then the scenario folder.

### 4.5 Writing and intellectual-property rules
- All dialogue and story text is original. Use Legends names and concepts,
  never quotations or close paraphrases of the novels, films, or games. (One
  famous last line was caught and replaced during Campaign III; check for
  this.)
- Retiring old content requires an owner decision: list the retired paths
  and ids in `addons/.../tests/retired-content.json` with the reason and date,
  and `git rm` the files.

### 4.6 Bookkeeping for each content change
- Contracts: add a `source-id` contract for every scenario id and unit id in
  `addons/.../tests/gameplay-contracts/<campaign>.json` (contract ids match
  `sw-[a-z0-9-]`), and keep the index `tests/gameplay-contracts.json` sorted.
- Art queue: `art_pipeline.synchronize_art_queue(root, {new unit ids})`.
- Interim art: add a lore-accurate `Look` per unit in
  `production/tools/gen_coded_unit_art.py`, then run it (it writes missing
  files only). The engine probes treat missing images as fatal.
- Art direction: add a lore-accurate description per unit to
  `production/assets/art_direction.json`, and add vehicles and structures to
  `sprite_only`.
- Inventory: `python3 production/inventory.py`, then `--check`.

## 5. Sequence harness for each campaign

The authoritative functional test plays the whole campaign in the real GUI.
For each new scenario:

1. Add a scripted win path to `WIN` in
   `production/linux_engine/campaign_sequence_plugin.lua`. Use
   `move(id, x, y)` (real `moveto` events), `kill_id(id)` (real `die` and
   `last breath` events), or `fire(event_name)`. Do not call `[endlevel]`
   directly; the scenario's own events must end it.
2. If the mission has a "reach a place" or "defeat a leader" objective, add
   a legal-route spec to `ROUTE_SPECS` in the same plugin, as a flat string
   `"unit_id:x,y;x,y|other_unit:x,y"`. The engine cannot serialize nested
   tables into the game kernel, so the specs must stay flat strings. The
   probe asks the engine's pathfinder whether each target can be reached over
   legal terrain, and fails if one needs more than 80% of the turn limit.
3. Add the scenario id to the campaign's expected list, and its required
   heroes to `REQUIRED_HEROES`, in
   `production/linux_engine/run_campaign_sequence.py`. A new campaign also
   goes into `CAMPAIGNS`.
4. Run it:
   ```bash
   python3 production/linux_engine/run_campaign_sequence.py --campaign <campaign_id> \
       --workdir /tmp/<dir> --output /tmp/<dir>/seq.json
   ```
   It must report `pass: true`, ten saves, and the right heroes in every
   scenario. The engine log is under `<workdir>/userdata/logs/`. The start
   save for each scenario (`sync/saves/<Abbrev>-<Name>.gz`) shows the
   constructed sides when a transition fails.

### 5.1 AI soak test
`production/linux_engine/run_ai_soak.py` starts each scenario directly, hands
side 1 to the AI, and plays until the scenario ends. That exercises every
turn-based event, wave, hazard, and AI decision the scripted probe skips.
Any WML/Lua/engine error fails it. It records the outcome and every side-1
death; a quick defeat with no hero death points to an objective that can be
lost before the player can react.
```bash
python3 production/linux_engine/run_ai_soak.py --jobs 3 --workdir /tmp/soak --output /tmp/soak.json
```
AI-controlled heroes charge recklessly, so hero deaths in the soak are not
balance verdicts on their own. `--player careful` gives side 1 negative
aggression and high caution, which is closer to how a person protects an
irreplaceable hero; compare both runs before reading anything into a death.

### 5.2 Hero start-threat report
`production/tools/hero_threat_report.py` lists, for every hero's starting
hex, the enemies placed at start that can reach it on their first move and
their expected damage. A hero whose expected damage reaches 80% of its
hitpoints is flagged: the player could lose it before acting. Run it after
changing a scenario's start positions or the roster's stats:
```bash
python3 production/tools/hero_threat_report.py --fail-on-flag
```

## 6. Art through the dashboard

- Owner rules: lore-accurate designs; the guide artists' qualities are
  written as style traits in `production/assets/art_direction.json` (never
  artist names in prompts); no real-actor likeness (film-portrayed characters
  are in `portrait_from_sprite`); the same outfit and equipment in every frame
  (frames are derived from one master by
  `production/tools/derive_unit_frames.py`).
- Generate: the dashboard's "Generate with Codex" or "Generate all pending
  art" (control actions `generate_art` and `generate_all_art`). Each unit
  costs one or two Codex image calls. If the image service refuses a design,
  the unit keeps its code-drawn art.
- Always look at a contact sheet of new art before publishing; wrong images
  have been collected before.
- Publish with the dashboard's art import (`confirm_art_import`). It batches
  every ready job that shares a unit source file, regenerates the inventory,
  and goes through PR, exact-head CI, merge, and engine validation.

## 7. Checks

Run before every PR:

```bash
python3 -m compileall -q agent/coordinator agent/dashboard
python3 agent/coordinator/scenario_launch_selftest.py
python3 agent/coordinator/codex_art_selftest.py
python3 agent/coordinator/ticket_acceptance_selftest.py
python3 agent/coordinator/engine_compatibility_selftest.py
python3 production/contract_store_selftest.py
python3 production/validate_package_selftest.py
python3 production/inventory_selftest.py
python3 production/inventory.py --check
python3 -m unittest agent/dashboard/test_dashboard.py
git diff --check origin/main...HEAD
```

For add-on changes, also run the full game validation and save it to a file
(the launcher prints a lot of output):

```bash
PYTHONPATH=agent/coordinator python3 -c "
import json; from pathlib import Path; import scenario_launch_selftest as s
json.dump(s.validate_post_publish_game(Path('.').resolve()), open('/tmp/ppv.json','w'), default=str)"
```

Before merge, every check except `published_player_launcher` must pass. After
merge, check the launcher against the full merged SHA:

```bash
PYTHONPATH=agent/coordinator python3 -c "
import subprocess; from pathlib import Path; import scenario_launch_selftest as s
root = Path('.').resolve(); sha = subprocess.run(['git','rev-parse','HEAD'], capture_output=True, text=True).stdout.strip()
print(s.validate_published_player_launcher(root, sha)['pass'])"
```

## 8. Engine facts that cost time to learn

- `--plugin` disables `--campaign`: probes drive the title screen themselves.
- Carryover is matched by side `save_id`; leaders carried over with
  `canrecruit=yes` can take over a later scenario's leader slot; clear the
  flag at victory and restore it in prestart (the macros do this).
- A side with no `canrecruit` unit is defeated at once unless
  `defeat_condition=never`.
- `previous_recruits` merges earlier recruit lists; use `[set_recruit]`.
- Directory includes load only `.cfg` files and do not recurse into
  subfolders unless they have `_main.cfg`.
- A plugin's `wesnoth.plugin.execute` serializes the function and its
  upvalues; nested tables cannot be serialized (it returns false and a
  message). Check its return value.
- Wesnoth 1.19.27 supports `min_range` and `max_range` attacks, but the AI
  does not use them.
- The Linux engine sometimes does not exit after the plugin asks it to; the
  runners stop it once the probe reports completion.

## 9. Safety rules (from `AGENTS.md`, restated)

Never push or merge directly to `main`, force-push, or rewrite published
history. Never print, log, or commit credentials, and never use API keys for
Codex. Never delete branches or worktrees unless instructed. Never modify the
controlled reference files outside a dedicated governance PR. Report real
results only; when something is unverified, say so.

## 10. Where things stand

See the newest addenda in `docs/PROJECT_CONTINUITY.md` and the open PRs.
Open work at the time of writing:

- Codex art: many units still use code-drawn art.
- Objective reachability is checked by the sequence probe. Full AI-opposed
  playthroughs and balance playtesting have not been done.
- The dashboard's automation of small Codex tickets needs the Windows
  launcher's secure bridge.
