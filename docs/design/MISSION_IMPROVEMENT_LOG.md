# Mission Improvement Log

Every design change made under [MISSION_DESIGN_STANDARD.md](MISSION_DESIGN_STANDARD.md):
what changed, why, how it was tested, and what is still uncertain. Newest
first. Findings and scores are in [SCENARIO_AUDIT.md](SCENARIO_AUDIT.md).

---

## 2026-10-17 — Design audit, round 3: the trilogy finale and more bonuses

**The Last Command becomes an assault** (SDF, P4).
- **Before:** win by surviving to a scripted turn 10, when Rukh kills Thrawn,
  or by destroying both escorts.
- **After:**
  - The Grand Admiral falls when the Chimaera is brought to half strength
    (checked after every attack: Rukh strikes while the bridge is under
    fire), or when both escorts are destroyed.
  - There is no timer win. Turns are 16/14/14.
  - A note explains how to fight Star Destroyers.
- **Why:**
  - After round 2, this was the last finale with the passive shape.
  - The three finales now differ: three objectives at Sluis Van, defense then
    counterattack at Honoghr, and an assault here.
  - It keeps the story beat, Rukh's strike and Pellaeon's retreat, tied to the
    battle the player fights.
- **Precedent:** Thrawn's Gambit already uses "damage the Chimaera to half
  strength".
- **Test:** the sequence win script sets the Chimaera to half and fires
  `attack end`; the level must end. Plus an AI soak.
- **Risk:** the hardest mission loses its safe route. A human Normal
  playtest is needed.

**Four more mission-specific bonuses** (SDF, P4), each replacing "lose no
units":

| Mission | New bonus |
|---|---|
| The Senator's Men | Get Han to the Falcon by the end of turn 8 |
| The Mad Jedi | Never let the Force storm catch one of your units |
| Battle for the Fleet | Lose none of the three Dreadnaughts |
| Bilbringi | Destroy three platforms by the end of turn 10 |

- **Tests:** sequence checks `senators_bonus_swift`, `mad_jedi_bonus_dry`,
  `fleet_bonus_all_ships` and `bilbringi_bonus_swift`.
- **Engine detail:** the storm's location filters now pair `x` and `y` lists
  (`y=1-18,1-18`). Unequal lists log an engine error
  (`map_location::matches_range`).

**Round 3 test results:**
- `run_campaign_sequence.py` passes all three campaigns with every check,
  including the new finale win path and the four new bonus checks.
- AI soak (careful player, one game each), with no WML, Lua or engine errors.

  | Mission | Outcome |
  |---|---|
  | Bilbringi | win, turn 8, inside the new bonus |
  | The Last Command | loss, turn 7 (before: losses on turns 5–6) |
  | The Mad Jedi | loss, turn 8 |
  | Battle for the Fleet | loss, turn 17 (turn limit) |
  | The Senator's Men | loss, turn 15 (turn limit) |

  The last two match earlier soaks: the AI player does not pursue movement
  objectives.

## 2026-10-17 — Design audit, round 2: structure, maps and bonuses

**Branch:** `design/mission-audit` (same PR as round 1).

This round implements recommendations from round 1's campaign review.

**Honoghr's Choice: a finale that is not "hold or kill"** (SDF, P4).
- **Before:** win by surviving to the last turn, or by killing Sorrell, the
  shape of all three finales.
- **After:**
  - The clans answer only to Leia in their clan house (13,9), from turn 6, at
    the start of the first player turn she is there. Until then Khabarakh
    reminds the player where she must be.
  - Their warriors then join and Noghri become recruitable. The only win is
    to defeat Sorrell, west of the village. Running out the turns is a loss.
  - Killing Sorrell before the clans rise still wins; the declaration plays at
    victory.
- **Why:**
  - It gives the campaign's ending a phase change, from defense to
    counterattack, which the standard (§3.2) asks of defenses.
  - It removes the passive way to win.
  - It ties the political payoff to holding the clan house.
- **Alternatives considered:**
  - An escort to the clan elders: a new map path and AI escort, more risk.
  - Changing The Last Command instead: it is the trilogy's finale and the
    novel's set piece.
- **Evidence it is winnable:** earlier AI soaks won this mission on turns 4–5
  by killing Sorrell, the route that remains.
- **Test:** sequence win (Sorrell's last breath), plus an AI soak.
- **Risk:** harder than before, because there is no timer win. A human check
  is needed on Normal.

**Asteroid lanes at Sluis Van and Thrawn's Gambit** (SDF, P4).
- `gen_hte_maps.py`:
  - Sluis Van gets a broken belt at x=15–17 with open lanes at rows 4–5, 9–11
    and 15–16.
  - Thrawn's Gambit gets 2×2 rock patches in front of each warship and
    between the Star Destroyers.
- Key hexes, spawns and warships are untouched (`gen_hte_maps.py --check`).
- **Risk:** asteroids give fighters 60% defense for 2 movement, so screening
  gets stronger. A playtest is needed with the post-#430 craft.

**Mission-specific bonuses** (SDF, P4). Each replaces a generic "lose no
units" with a trade-off particular to the mission:

| Mission | New bonus | Trade-off |
|---|---|---|
| Raid on Karrde's Base | Get all six of Karrde's people aboard | The win needs 3/4/5; the rest cost turns at the field |
| The Sluis Van Shipyards | Save all four docked warships | Screen every dock, or hunt miners forward; replaces Thrawn's Gambit's separate +40, so it is paid once |
| The Siege of Coruscant | Destroy both minelayers by the end of turn 8 | Speed against flying through a thicker cordon |

- **Tests:** sequence checks `raid_bonus_all_out`,
  `sluis_van_bonus_all_saved` and `coruscant_bonus_swift`.

**Round 2 test results:**
- `gen_hte_maps.py --check`: 10 maps. Only the Sluis Van and Thrawn's Gambit
  maps changed.
- `run_campaign_sequence.py` passes all three campaigns, with every round 1
  and round 2 check passing.
- AI soak (careful player, one game each), with no WML, Lua or engine errors.

  | Mission | Outcome |
  |---|---|
  | Honoghr's Choice | win, turn 4, by breaking Sorrell as the redesign requires |
  | Sluis Van | win, turn 7 |
  | Siege of Coruscant | win, turn 8, inside the new speed bonus |
  | Thrawn's Gambit | loss, turn 8, matching earlier soaks |
  | Raid on Karrde's Base | loss, turn 4: the AI player walked Han into the AT-ST, a known pattern |

## 2026-10-17 — Design audit, round 1: defects, information and consequences

**Branch:** `design/mission-audit`.

**Approach.** Fix confirmed defects first (standard §6.1). Then fix information
the player needed but was not given (§1.2 point 3). Then make small changes
with clear mechanical evidence. Out of scope: premise redesigns, map rework
and numeric rebalancing that need human play first (see the open items in
SCENARIO_AUDIT.md §3).

**Who did what.** Sol 6.1 (read-only) produced the first audit of Dark Force
Rising and The Last Command. Claude audited Heir to the Empire, verified
Sol's findings against the code, and made all the changes.

### Confirmed defects fixed

| Mission | Defect | Change | Evidence it works |
|---|---|---|---|
| HTE 5 Prisoner of Myrkr | Bonus "never raise the alarm" was impossible: the required lightsaber pickup raises it by script | New `bonus.secure()` (`lua/sw_bonus.lua`) locks a met bonus in; called on reaching the office unseen. Bonus text: "Reach Karrde's office without raising the alarm" | Sequence check `myrkr_bonus_secured` (HTE 6 sees the Myrkr bonus marked complete) |
| DFR 1 The Noghri Prisoner | A multi-strike attack could pass Khabarakh through the surrender threshold and kill him, which loses the mission | Hit events mark him subdued when a strike leaves him at a third of his HP or less; a later strike in the same fight captures him instead of killing him | Sequence win script is now a real forced-hit attack from 20 HP (subdue, then a lethal strike); Khabarakh must reach Honoghr |
| DFR 1 | Force damage never triggered the capture check | New `sw_force_used` event (`lua/sw_systems.lua`) after every Force power; the scenario runs its capture check on it | Code path; covered by the same capture event |
| DFR 3 Jomark | A village lost, retaken and lost again counted twice, so the mission was lost with one village gone | Each marked village counts once; the objective reads "two different lakeshore villages" | Sequence check `village_counted_once` (two captures of 13,2 count 1; the mission continues) |
| DFR 10 Honoghr's Choice | The objective said the clans decide at the last turn (they do on turn 6); Thrawn reacted to a defection the end text says he does not know of; the finale showed a carryover note | Objective text corrected; Thrawn only notes the detachment is overdue; the note is removed | Text review |
| TLC 2 Smugglers' Council | The E-Web recruit (the balance review's ranged counter) was dropped from the prestart list by #396 | Restored; a scan found no other recruit-list mismatch in the 30 missions | Sequence check `eweb_recruit` |
| TLC 4 Landfall on Wayland | The goal region included two west-bank forest hexes, so "Across" fired without crossing | The goal is the far bank (x=28, y=9–11), labelled "Far Bank" | Sequence route check to (28,10) and (28,9); win script moves there |
| TLC 5 Natives of Wayland | The note said the natives come on turn 4 on every difficulty (turn 2 on Easy and Normal) | Note set per difficulty | Text review |
| TLC 8 The Throne Room | The lock holding C'baoth and the guards while Luuke lives ran in `side 2 turn`, before the engine restores movement | Runs in `side 2 turn refresh` | Engine source (`play_controller.cpp`: `side_turn` fires before `new_turn`) |
| TLC 8 (and every Force-lightning user) | Force lightning ignored ysalamiri, although the mission's counterplay is "nobody can use the Force in Mara's field" | Generator special `force_weapon`: lightning is disabled when the caster or the target is in a bubble; shown as "Force" in help | Sequence checks `lightning_blocked_in_field` and `lightning_outside_field` (Luuke's counter to Mara's ranged attack) |
| All | The bonus reward said "credits next mission"; it is paid at the next mission where you can recruit | `SW_BONUS_OBJECTIVE` text | Text review |
| Tool | `mission_balance_report.py` counted a side allied with both camps as enemy (The Dark Force's derelicts) | Allies are found by overlapping team lists; sides allied with both camps count for neither | Report rerun |

### Information added (threats the player could prepare for)

| Mission | Added |
|---|---|
| HTE 3 Adrift, HTE 4 Shadows of Kashyyyk, TLC 3 Palace Infiltrators | "Destroy them all" objectives now say when the last wave arrives |
| DFR 3 Jomark | Note: a second boat lands on turn 5 beside the weaker southern village |
| DFR 9 Battle for the Fleet | Exit rule ("any two Dreadnaughts, anywhere in the last two columns"); Bel Iblis's relief expected around turn 8 |
| TLC 6 Gates of Mount Tantiss | Note: the gate reserve comes out when any unit gets within six hexes |
| TLC 9 Bilbringi | Notes: more asteroids may be seeded; reactor blasts deal 10 to adjacent ships (never fatal) |
| TLC 1 Siege of Coruscant | Luke no longer claims to feel the asteroids (Force Sense finds only the living); he points the fleet to its sensors |

### Design changes

**The Mad Jedi: C'baoth's storm is telegraphed** (SDF, P3).
- **Before:** on even turns a random two-column band was hit at once. The
  owner saw only "a large flash … does not appear to have any effect"
  (2026-10-16).
- **After:**
  - On odd turns C'baoth marks the band with a new coded marker,
    `misc/sw-storm-gathering.png` (from `gen_ui_icons.py`), and a "Force
    storm" label.
  - It breaks at the start of the next turn on whoever is still there.
  - Cadence and damage are unchanged.
- **Why not remove it (Sol's proposal):** telegraphed, it becomes a moving
  barrier the player times the crossing around. That is a decision, where
  random damage was not. It also matches the air-support marker pattern.
- **Test:** sequence check `storm_marked_ahead`.
- **Risk:** the escape may be slightly easier. Playtest Hard.

**Escape turn limits at most 3× travel** (SDF, P4). Engine route checks
measured unobstructed travel against the Normal turn limit:

| Mission | Route | Old turns E/N/H | New turns E/N/H |
|---|---|---|---|
| The Forest Crossing | 5 turns | 20/18/17 | 17/15/14 |
| Honoghr | 5 turns | 18/16/15 | 17/15/14 |
| Landfall on Wayland | 5 turns (far bank) | 18/16/15 | 17/15/14 |

- **Why:** the escape standard asks for pursuit that makes delay costly. At
  over three times the travel time the player could wait out the pursuit.
- **Swift achievements** (a third of the turns unused) remain reachable.
- **Risk:** fights slow the heroes more than the route check shows. A human
  check is needed that the limits feel tense, not tight.

**Nomad City → Sluis Van consequence** (SDF, P4).
- **Change:**
  - `sw_hte_miners_stolen` carries forward.
  - At Sluis Van, none stolen removes the turn-5 miner; two or more add one
    to the last wave.
  - Nomad City's objectives say the stolen miners will be used against the
    Republic, and Luke comments at Sluis Van.
  - A save from before the change counts as one stolen (no change).
- **Test:** sequence check `miners_stolen_carried`.
- **Risk:** ±1 miner in a mission with 6–7.

**Sluis Van → Thrawn's Gambit continuity** (SDF, P5).
- **Change:** the finale's two warships are named after Sluis Van's
  survivors (`sw_hte_warship_north/south`). The flanking-strike lines use the
  names.
- **Test:** sequence check `warship_names`.

**Honoghr's Choice: the clans' declaration always plays** (SDF, P4).
- **Change:** killing Sorrell before turn 6 now plays the declaration at
  victory, once.
- **Test:** text and event review. The win script reaches victory on turn 1,
  which runs this path.

**The Natives of Wayland becomes an alliance battle** (SDF, P4).
- **Before:**
  - Luke and Mara crossed jungle alone from the west edge, right after doing
    the same in Landfall on Wayland.
  - Native war parties appeared at the map corners on turn 2.
  - The bonus asked the heroes to hold four settlements.
- **After:**
  - The Myneyrshi (north villages 6,4 and 13,3) and the Psadans (south
    villages 6,16 and 13,17) start at home as guardians and join the advance
    on turn 2 (Hard: 4). Same units, plus the Easy extra.
  - The garrison has a `target_location` goal on those four villages: it
    raids them, as the opening dialogue says.
  - The bonus is "Lose none of the native warriors" (flag
    `sw_tlc05_allies_kept`, cleared by a side-3 death).
- **Why:**
  - It removes the clearest local repetition in The Last Command.
  - It gives the mission a signature decision: help the villages, or strike
    the outpost while the garrison is out raiding.
  - It replaces a bonus that would have meant taking villages from your own
    allies.
- **Alternatives considered:**
  - A new map. Larger; the existing villages already sit in two flanks.
  - Only changing the bonus text. That leaves the repetition.
- **Test:** sequence checks `natives_hold_villages` and `allies_bonus_armed`.
  The win path is unchanged (the commander's last breath).
- **Risk:** the allies are present a turn earlier, so the opening is safer.
  It is no longer two heroes against the garrison, which was the 2026-10-04
  failure. A human playtest should check that the raids keep it tough.

### Test results

- `gen_hte_units.py --check`: 59 unit types consistent after the `force_weapon`
  special.
- `run_campaign_sequence_selftest.py`: 21 tests pass, including the new
  check-line parser.
- `run_campaign_sequence.py` passes all three campaigns, with every design
  check listed above passing:
  - The Mad Jedi's storm is marked on turn 1.
  - Luuke's counter to Mara is not lightning inside the field, and is lightning
    outside it.
  - The Noghri Prisoner's forced-hit attack captures Khabarakh, who arrives in
    Honoghr.
- Measured routes against the new limits, all on Normal:

  | Mission | Route |
  |---|---|
  | The Forest Crossing | 5 of 15 turns |
  | Honoghr | 5 of 15 turns |
  | Landfall on Wayland | 5 of 15 turns, to the far bank |

- `run_systems_tests.py --suite all`: 1,213 checks pass. Three fail, and all
  three also fail on unchanged `main`:
  - The air main-phase timeout, and the save/load check that depends on it.
  - "allies beside the attacker do not flank". PR #433 fixes this.
- AI soak (careful player, one game each), used as a runtime check of the new
  event code. There were no WML, Lua or engine errors in any of the ten.

  | Mission | Outcome |
  |---|---|
  | The Noghri Prisoner | win, turn 4 |
  | Honoghr's Choice | win, turn 4 |
  | Sluis Van | win, turn 7 |
  | The Natives of Wayland | win, turn 5 |
  | Jomark | loss, turn 4 (villages) |
  | The Mad Jedi | loss, turn 7 |
  | The Forest Crossing | loss, turn 5 |
  | Smugglers' Council | loss, turn 4 |
  | Landfall | loss, turn 4 |
  | The Throne Room | loss, turn 3 |

  The losses are the AI player's known patterns: heroes marched into combat,
  and objectives left undefended. None was lost to a turn limit. One AI game is
  not a balance measure.

### Remaining uncertainty

- None of these changes has been played by a person. The Throne Room and the
  Smugglers' Council become easier as intended; whether they are now too easy
  is a playtest question.
- The Dark Force is unchanged here; PR #434 addresses its findings.
- Deferred recommendations are in CAMPAIGN_DESIGN_REVIEW.md §8.
