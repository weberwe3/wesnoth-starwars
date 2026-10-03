# Force and overwatch systems

Two reusable gameplay systems for every mission of the add-on: a Force-resource
framework with ysalamiri null fields, and movement-triggered overwatch. Both
live in Lua modules under `addons/Star_Wars_Thrawn_Trilogy/lua/`. Units and
scenarios configure them declaratively in WML. The core contains no scenario
or unit ids.

## Files

| File | Role |
| --- | --- |
| `lua/sw_systems.lua` | Loader: registers every event handler (the only place) and the right-click menus. Defines the global `sw_systems`. |
| `lua/sw_core.lua` | Shared helpers: ability config reading, synced choices, indicator overlays, debug log. |
| `lua/sw_force.lua` | Force Points, the power registry, the seven powers, null fields, Mind Trick, Force Sense. |
| `lua/sw_overwatch.lua` | Overwatch entry/expiry, the reaction resolver, guards, hooks, AI overwatch. |
| `utils/hte_macros.cfg` | `{SW_TACTICAL_SYSTEMS}` (loads the systems; placed in every scenario), `{SW_YSALAMIRI_ZONE XS YS RADIUS}` (static null fields), Field Manual topics. |
| `production/tools/gen_hte_units.py` | Generates the units' `sw_ability_force` / `sw_ability_overwatch` abilities (`FORCE_PROFILES`, `OVERWATCH_WEAPONS`). |
| `production/tools/gen_ui_icons.py` | The indicator overlays and menu icons. |
| `production/linux_engine/run_systems_tests.py`, `systems_test/` | Engine tests (below). |

## Architecture

**Loading.** Every scenario contains `{SW_TACTICAL_SYSTEMS}`, a top-level
`[lua]` that runs on new games and on every load. It registers the handlers
with `wesnoth.game_events.add` and the menus with
`wesnoth.interface.set_menu_item`. All gameplay state lives in WML variables
and unit variables, so a reload restores the systems exactly. The Lua null-field
cache rebuilds lazily from the saved `sw_ysalamiri_zone`.

**Determinism.**
- Reaction hit rolls use `mathx.random`, the synced game RNG, inside the
  synced movement event, so they replay identically.
- Iteration over units is sorted by id, and over targets by distance, then id.
- Player choices (power, target) are `[message]` options, which are synced
  choices recorded in replays.
- Nothing depends on the UI selection. `needs_select` is deprecated as
  multiplayer-unsafe and is not used.

**State.**

| Where | Variables |
| --- | --- |
| Force units | `sw_fp`, `sw_cd_<power>` (cooldown turns left), `sw_used_<power>` (turn used, once-per-turn powers) |
| Mind Trick targets | `sw_dazed_turn` / `sw_dazed_active` |
| Force Sense targets | `sw_sensed_side` |
| Overwatch units | `sw_ow_active`, `sw_ow_shots`, `sw_ow_range`, `sw_ow_weapon`, `sw_ow_accuracy`, `sw_ow_damage`, `sw_ow_arc`, `sw_ow_facing`, `sw_ow_fired` |
| Every moving unit | `sw_move_serial` |
| Globals | `sw_force_null_sources` (static fields), `sw_ysalamiri_zone` (current field hexes, also used by WML `find_in` filters), `sw_force_null_drawn`, `sw_ow_index` (ids of units on overwatch) |

**Indexing.**
- A moving unit checks only the overwatch index (units actually on overwatch),
  never every unit on the map.
- The null field is recomputed only on moves, displacement, deaths,
  placements and turn starts, and per hex only while a ysalamiri carrier or a
  Force user is moving.

### Event precedence

All handlers are registered in `sw_systems.lua`:

| Event | Order |
| --- | --- |
| `enter_hex` | 1. overwatch reaction check for the moving unit; 2. null-field refresh if the mover is a carrier or a Force user |
| `moveto` | move-serial bump (duplicate guard), then null-field refresh |
| `turn refresh` (a side's turn start, after the engine resets moves) | 1. that side's overwatch expires; 2. null-field refresh; 3. Force regeneration, cooldown ticks, Mind Trick, Force Sense expiry |
| `side turn end` | AI sides may enter overwatch |
| `die`, `unit placed` | null-field refresh, overwatch cleanup, Force Point initialisation |
| `prestart` | carried-over units start full on FP and off overwatch; indicator objects compacted |

**Reaction resolution order:**
1. Eligibility: on overwatch, reactions left, alive, enemy, not dazed or
   disabled, in range, in arc, the hex is not fogged, the unit is visible,
   not already fired at during this move order, and no `can_react` hook vetoes.
2. The target's reactive Force deflection.
3. `modify` hooks.
4. Hit rolls.
5. Damage and death through `[harm_unit]`, firing `die` events.
6. If the target survives, `[cancel_action]` pauses its move.

The sensors/EW and doctrine handlers slot into the same events; the full
order is in the header of `lua/sw_systems.lua` and in
[INTELLIGENCE_AND_EW.md](INTELLIGENCE_AND_EW.md). Mission state is stamped
with the scenario id, so static ysalamiri sources from one mission are not
carried into the next.

**Loop prevention:**
- `overwatch.resolving` blocks any reaction while one resolves.
- Force Push and Pull move units without firing events, so they never provoke
  reactions or trigger objectives.
- One volley per watcher per enemy move order, enforced by `sw_ow_fired`
  together with `sw_move_serial`.

## Configuring units

Force-sensitive unit (all attributes optional except `id`):

```
[dummy]
    id=sw_ability_force
    fp_max=8
    fp_regen=2
    powers=push,pull,speed,sense,mind_trick,deflection
    cost_push=3        # optional per-unit override: cost_/range_/cooldown_<power>
    name= _ "the Force"
    description= _ "..."
[/dummy]
```

Overwatch-capable unit (defaults shown):

```
[dummy]
    id=sw_ability_overwatch
    weapons=blaster_rifle   # default: the unit's ranged attacks
    range=2
    reactions=1             # volleys per overwatch
    accuracy=-10            # added to the chance to hit
    damage=100              # percent of weapon damage per hit
    arc=all                 # or front: facing direction and its two neighbours
    commit_moves=yes        # entering overwatch also ends movement
[/dummy]
```

Ysalamiri carrier: the field moves with the unit. It can be given by an
`[object]` `new_ability`, as HTE 1's frame carriers are:

```
[dummy]
    id=sw_ability_ysalamiri
    radius=2
[/dummy]
```

## Configuring scenarios

- Static null field: `{SW_YSALAMIRI_ZONE 7,12,16 6,9,11 3}` (coordinate
  lists and a radius), inside an event such as `prestart`.
- Disable AI overwatch: `[set_variable] name=sw_overwatch_ai value=no`.
- Debug log: `[set_variable] name=sw_systems_debug value=yes`. Decisions print
  as `SW_SYSTEMS[force|overwatch]: ...`.
- Pre-set or change state with ordinary WML, e.g. `[modify_unit]` to set
  `variables.sw_fp`, or Lua:
  `sw_systems.force.add_static_source(x, y, radius)`,
  `sw_systems.overwatch.enter(unit)`.

## Extending

- **New power:**
  ```lua
  sw_systems.force.register_power("battle_meditation", { name = ..., cost = 3, range = 4,
      target = "ally", cooldown = 2, valid = function(caster, target, power) ... end,
      apply = function(caster, target, power) ... end })
  ```
  Then list it in a unit's `powers=`. The menu, cost, cooldown, target
  validation and ysalamiri suppression apply automatically. Set
  `alignment = "dark"` and so on for future light/dark-side rules.
- **Force Sense:** `force.SENSE_REVEALS` lists the living-stealth abilities it
  defeats. Technological cloaking (`sw_ability_cloaked`) is deliberately not
  in it.
- **Overwatch hooks:**
  - `sw_systems.overwatch.hooks.can_react` takes `function(shooter, target)`;
    returning false vetoes the reaction. Use it for future cloaking/detection
    and suppression.
  - `.modify` takes `function(shooter, target, shot)`, which edits
    `shot.accuracy`, `shot.damage` and `shot.strikes`. Use it for future cover
    and command bonuses.
  - `force.on_disabled(unit)` is called when a unit is disabled (Mind Trick)
    and clears its overwatch.

## Player interface

| Indicator | Meaning |
| --- | --- |
| Blue pips, right edge | Force Points |
| Violet slashed ring, bottom right | Force suppressed by a ysalamiri |
| Gold crosshair with bars, bottom left | On overwatch, reactions left |
| Swirl above the head | Dazed by Mind Trick |

- **Right-click menus:**
  - **The Force…** (powers with cost, and why a power is unavailable),
    shown only on your own Force users.
  - **Overwatch** (commits this turn's attack), shown only when allowed.
  - **Tactical status**, the text summary.
- Short floating labels report pushes, deflections and reaction fire. There
  are no popups apart from the menus.
- The in-game Field Manual explains both systems.

## Tests

```bash
python3 production/linux_engine/run_systems_tests.py --suite force
```

`--suite all` (the default) also runs the sensors/EW and doctrine suites
([INTELLIGENCE_AND_EW.md](INTELLIGENCE_AND_EW.md)). The force suite stages a
test-only scenario (`systems_test/sw_test_systems.cfg`: a flat map with one
wall hex) and runs 85 engine checks across two phases.
The second phase reloads the save the first one made. Coverage:
- Force Point spending, regeneration and cap; target validation; Push and Pull
  displacement plus its blocked, occupied and edge safety; cooldowns.
- Moving, static and dying-carrier null fields; entering and leaving
  suppression by real move orders.
- Overwatch entry, movement-triggered fire, the pause, multiple shooters,
  consumption and expiry.
- Deflection versus overwatch, inside and outside a field.
- Hidden targets; Mind Trick and overwatch; arcs and hooks; Force Sense versus
  cloaking; Force Choke.
- The reentrancy and duplicate guards.
- An AI-controlled turn.
- Save and load.

Exit code 0 means every check passed and the engine logged no Lua/WML errors.

## Engine limitations and fallbacks

| Limitation | Fallback |
| --- | --- |
| An interrupted move cannot be resumed automatically. | Reaction fire pauses the mover with `[cancel_action]`; it keeps its remaining movement points and the player (or AI) issues a new move. |
| Reaction fire cannot use the engine's attack action for a non-acting side. | The resolver rolls hits on the synced RNG, using the target's terrain defense plus the accuracy modifier. Damage goes through `[harm_unit]`, which applies resistance, time-of-day alignment, experience and `die` events. There is no retaliation, and weapon specials such as marksman do not apply. |
| `needs_select` is deprecated and unsafe in multiplayer. | Abilities are chosen caster-first from the right-click menu on the Force user, with synced `[message]` choices. |
| Removing a unit modification rebuilds the unit, which can reset extra movement mid-turn. | Indicators only ever add overlay add/remove objects (as core `[unit_overlay]` does). They are compacted at mission start. |
| The AI does not choose active Force powers. | Passive and reactive powers (regeneration, deflection, suppression) apply to AI units. AI units enter overwatch automatically at turn end when they kept their attack. |
| Force Sense restores stealth by removing its object, which rebuilds the sensed unit. | This happens only at the sensing side's turn start, when nothing transient is lost. |
