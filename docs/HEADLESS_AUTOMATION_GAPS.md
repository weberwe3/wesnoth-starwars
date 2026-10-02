# Headless Automation Gaps: Transition, Save/Reload, Carryover

> **Superseded 2026-10-02.** These gaps are now automated. Plugin-driven GUI
> runs on the Linux 1.19.27 harness enter campaigns through the title screen,
> dismiss dialogs, end linger mode, move between scenarios, check carryover,
> and save in-game (`production/linux_engine/`). The text below is kept as
> history.

**Date:** 2026-09-27
**Engine:** Wesnoth 1.19.28
**Status:** Documented limitation, not a code defect

## What IS verified headless

### Defeat wiring (all pass on 1.19.28)
- Space Interception: escort death → defeat, leader death → defeat, turn-12 deadline → defeat
- Ground Extraction: hero death → defeat, leader death → defeat, turn-10 deadline → defeat
- Restore the Beacon: timeout, engineer death, commander death → defeat
- Method: `[kill] fire_event=yes` or `[fire_event]` in `[test]` mode, exit code 7

### Victory wiring
- Space Interception: escort reaches (5,3) → victory, exit code 8
- Ground Extraction: 6-step route → victory, exit code 8
- Restore the Beacon: engineer reaches terminal → victory, exit code 8

### Event syntax (fixed 2026-09-27)
- 14 events across 4 scenarios used invalid `name=turn` + `turn=N` syntax
- Fixed to `name="turn N"` per Wesnoth EventWML specification
- Verified against official campaigns (Heir to the Throne uses `name=turn 12`)
- Without this fix, turn-based events (reinforcement deadlines, bomber deployments) never fired

### Scenario loading
- All `next_scenario` targets exist and are loadable in isolation
- Campaign definition valid, `first_scenario` resolves

## What CANNOT be automated headless

### 1. Campaign transition (victory → next scenario)

**Blocker:** Modal victory dialog requires GUI interaction.

When `[endlevel] result=victory next_scenario=X` fires in campaign mode:
1. Engine shows victory dialog with scenario results
2. User must click "End Scenario"
3. Engine loads next scenario

With `SDL_VIDEODRIVER=dummy`, the dialog appears but cannot be dismissed.
The process hangs indefinitely. Verified 2026-09-27: victory event fired
(`sw_transition_test_victory_triggered` in log), but no transition occurred,
no save file created, process timed out after 45s.

**What this means:** The `[endlevel] next_scenario=` mechanism is standard
Wesnoth engine behavior (stable for 20+ years). The WML is valid. Targets exist.
But the actual GUI flow has not been observed.

**Manual test required:**
1. Launch Wesnoth with the addon installed
2. Start campaign "Star Wars: Thrawn Trilogy"
3. Play through 01_First_Battle to victory
4. Confirm transition to sw_02_space_interception
5. Repeat for 02 → 03

### 2. Save/reload cycle

**Blocker:** Save/load requires GUI interaction.

The `[test]` mode (`-u`) used by all probes does not exercise the save system.
There is no headless flag to:
- Create a mid-scenario save
- Quit and reload that save
- Verify state restoration

**What this means:** Save compatibility relies on standard engine behavior.
The scenarios use no known save-incompatible constructs (e.g., unsaved Lua
state, transient variables). But a full save → quit → load → continue cycle
has not been observed.

**Manual test required:**
1. Start any scenario in the campaign
2. Play several turns
3. Save the game (Ctrl+S or menu)
4. Quit to title
5. Load the save
6. Verify units, positions, variables, and turn number are restored
7. Continue playing to victory

### 3. Variable/gold/unit carryover

**Status:** Likely works (standard engine behavior), but unverified.

Wesnoth carries over between scenarios:
- Variables (e.g., `sw_first_battle_jammer_destroyed`)
- Gold (with `carryover_percentage`)
- Recall list (surviving units)

The scenarios reference previous-scenario variables (e.g., 02 checks
`sw_first_battle_jammer_destroyed` set in 01). This is standard campaign
behavior and should work, but has not been observed in a real transition
because of Blocker #1.

**Manual test required:** Same as transition test; verify that choices in
01 (e.g., jammer destroyed) affect 02 (escort movement bonus).

## Why not fix the automation?

Options considered:

1. **Virtual display (Xvfb) + GUI automation:** Would allow clicking through
   dialogs, but introduces flakiness, requires display server, and tests the
   GUI rather than the game logic. The probes already verify logic headless.

2. **Wesnoth `--plugin` Lua automation:** Could theoretically interact with
   the game, but the plugin API doesn't expose dialog dismissal, and this
   would be testing the test harness rather than the game.

3. **Engine modification:** Out of scope; we test against the installed engine.

The current probe suite verifies all game LOGIC headless. The remaining gaps
are GUI interaction flows, which are engine-standard and require human
verification once, not continuous automation.

## Recommendation

Before release:
- [ ] Manual playthrough of 01 → 02 → 03 transition
- [ ] Manual save/load cycle in each of the 3 scenarios
- [ ] Verify carryover variables affect gameplay as designed

These are one-time manual QA steps, not blockers for continued development.
