# Scenario Audit

**Date:** 2026-10-17. **Standard:** [MISSION_DESIGN_STANDARD.md](MISSION_DESIGN_STANDARD.md).
**Scope:** all 30 playable scenarios in the three campaigns. All 30 are
reachable through `next_scenario` chains (confirmed by
`run_campaign_sequence.py` for each campaign). The retired placeholder
scenarios are listed in `addons/Star_Wars_Thrawn_Trilogy/tests/retired-content.json`
and are not audited.

**Who audited what.**

- **Heir to the Empire:** Claude (Opus 5.5).
- **Dark Force Rising and The Last Command:** Sol 6.1 (`gpt-6.1-sol` through the
  Codex CLI, read-only). Every confirmed defect and every finding acted on was
  re-checked against the code by Claude. One finding was rejected; it is
  marked below.

**Evidence used.**

- Scenario WML and Lua, maps and map generators.
- Static numbers from `mission_balance_report.py` (Easy, Normal and Hard).
- Engine route checks from `run_campaign_sequence.py`: turns for the
  objective unit to reach its goal with no enemies in the way.
- Earlier AI-soak results (`../balance/MISSION_BALANCE_REVIEW.md` §4).

No human playtest was part of this audit. The scores judge the design as
built, not measured fun.

**Score key.** Each mission has nine criteria scored 0–5, in this order, with
these weights:

| | Criterion | Weight |
|---|---|---|
| A | Tactical depth | 20% |
| B | Map | 15% |
| C | Difficulty and fairness | 15% |
| D | Objectives | 10% |
| E | Pacing | 10% |
| F | Enemy AI | 10% |
| G | Army | 10% |
| H | Narrative | 5% |
| I | Identity | 5% |

Each mission's score is out of 100. It is the score **before** the changes of
2026-10-17. The re-scoring rule is in standard §2.4: a fixed defect is only
credited once the fix is verified.

---

## 1. Inventory and scores

Values are for Normal. "Route" is the engine route check: unobstructed turns
for the objective unit against the turn limit.

### Heir to the Empire (`CAMPAIGN_STAR_WARS_THRAWN_TRILOGY`)

| # | Mission | Type | Turns E/N/H | Force ratio | Route | Critical | Score |
|---|---|---|---|---|---|---|---|
| 1 | The Grand Admiral's Harvest | Tutorial collection (Imperial view) | 18/16/14 | 0.23 | 4 turns per leg / 16 | Pellaeon | **69** |
| 2 | Ambush at Bpfassh | Escape with escort | 16/14/13 | 0.92 | 6/14 | Leia | **78** |
| 3 | Adrift | Space survival, one hero | 9/10/11 | 2.40 | — | Luke | **66** |
| 4 | Shadows of Kashyyyk | Night defense and survival | 13/14/15 | 1.10 | — | Leia | **66** |
| 5 | Prisoner of Myrkr | Infiltration and escape | 16/14/13 | 2.17 | 2+2/14 | Luke | **76** |
| 6 | Raid on Karrde's Base | Evacuation under assault | 17/15/14 | 1.30 | 3/15 | Han | **82** |
| 7 | The Forest Crossing | Escape with escort | 20/18/17 | 1.55 | 5/18 | Luke | **61** |
| 8 | Nomad City | Defense against raids, with a hazard | 15/14/13 | 1.43 | 6/14 | Lando | **79** |
| 9 | The Sluis Van Shipyards | Space defense | 16/14/13 | 0.61 | — | Wedge | **67** |
| 10 | Thrawn's Gambit | Space finale, three objectives | 18/17/16 | 2.01 | — | Wedge | **75** |

### Dark Force Rising (`CAMPAIGN_STAR_WARS_DARK_FORCE_RISING`)

| # | Mission | Type | Turns E/N/H | Force ratio | Route | Critical | Score |
|---|---|---|---|---|---|---|---|
| 1 | The Noghri Prisoner | Capture while protecting Leia | 14/12/11 | 1.00 | — | Leia, Khabarakh (alive) | **72** |
| 2 | Honoghr | Covert crossing (escape) | 18/16/15 | 0.73 | 5/16 | Leia | **71** |
| 3 | Jomark | Spread-out defense, then assault | 16/14/13 | 1.32 | 4/14 | Luke | **72** |
| 4 | The Senator's Men | Escape | 16/14/13 | 1.00 | 5/14 | Han | **68** |
| 5 | The Peregrine's Nest | Defense, with an optional assault | 16/15/14 | 1.21 | — | Han | **85** |
| 6 | The Mad Jedi | Escape past an invulnerable pursuer | 16/14/13 | 1.04 | 6/14 | Luke, Mara | **68** |
| 7 | The Dark Force | Boarding race | 18/16/15 | 2.80\* | — | Wedge | **53** |
| 8 | Aboard the Katana | Assault | 18/16/15 | 0.64 | 4/16 | Luke | **83** |
| 9 | Battle for the Fleet | Escort | 18/16/15 | 1.36 | 12/16 | Wedge | **76** |
| 10 | Honoghr's Choice | Defense, with an optional assault (finale) | 15/14/13 | 0.98 | — | Leia | **71** |

\*The Dark Force's 2.80 counted the neutral derelicts as enemy strength, a
bug in the report tool that is now fixed. The score is for the version on
`main` before PR #434, which reworks this mission and was merged on 2026-10-17.

### The Last Command (`CAMPAIGN_STAR_WARS_THE_LAST_COMMAND`)

| # | Mission | Type | Turns E/N/H | Force ratio | Route | Critical | Score |
|---|---|---|---|---|---|---|---|
| 1 | The Siege of Coruscant | Space hazard sweep and assault | 18/16/15 | 1.40 | — | Wedge | **70** |
| 2 | The Smugglers' Council | Fortress defense, with an optional assault | 16/15/14 | 0.99 | — | Karrde | **57** |
| 3 | The Palace Infiltrators | Interception defense | 16/14/13 | 0.54 | — | Leia | **76** |
| 4 | Landfall on Wayland | Escape | 18/16/15 | 1.09 | 4/16 | Luke | **57** |
| 5 | The Natives of Wayland | Assault with allies | 16/15/14 | 1.09 | 3/15 | Luke | **59** |
| 6 | The Gates of Mount Tantiss | Assault | 18/16/15 | 1.12 | 4/16 | Han | **74** |
| 7 | The Cloning Vats | Demolition across several targets | 18/16/15 | 1.18 | — | Han | **73** |
| 8 | The Throne Room | Commander confrontation | 16/14/13 | 2.20 | 3/14 | Luke | **53** |
| 9 | The Bilbringi Shipyards | Space assault | 18/16/15 | 2.46 | — | Wedge | **72** |
| 10 | The Last Command | Space survival, with an optional assault (finale) | 14/14/14 | 2.60 | — | Wedge | **68** |

**Distribution.**

| Campaign | Average | Lowest |
|---|---|---|
| Heir to the Empire | 72 | Forest Crossing, 61 |
| Dark Force Rising | 72 | The Dark Force, 53 |
| The Last Command | 66 | The Throne Room and Smugglers' Council, 53 and 57 |

No mission scored below 50. Four scored below 60, and in all four the main
cause was a confirmed defect, not the premise.

---

## 2. Per-mission findings

Labels follow standard §2.5:

- **CD:** confirmed defect.
- **SDF:** strong design finding.
- **DH:** design hypothesis.
- **REJ:** rejected after verification.

Each finding lists its **Action** and the **Priority** it was given.

### Heir to the Empire

**1 · The Grand Admiral's Harvest** — 69
- **Mission:**
  - Pellaeon's landing party collects four ysalamiri frames while vornskr
    packs return every three turns.
  - Premise: a safe tutorial in Imperial command.
  - Signature decision: split the squads to carry frames, or escort each
    carrier.
- **Scores:** A3 B3 C4 D4 E3 F3 G3 H5 I5.
- SDF: pressure is flat. Packs spawn at two fixed dens, at the same cadence.
  - This fits a tutorial; the low force ratio of 0.23 is intended.
  - Action: none (P5).
- Note: the design record's "attacking the smugglers is a defeat" has no
  code behind it. None is needed: the smugglers are on the player's team, so
  they cannot be attacked.

**2 · Ambush at Bpfassh** — 78
- **Mission:**
  - Leia crosses a city under a raid. Noghri hide in the parks; militia hold
    the plaza; a TIE strafing run comes on turn 3.
  - Signature decision: streets or parks; canal bridges or the long way
    round.
- **Scores:** A4 B4 C4 D4 E4 F3 G4 H4 I4.
- Route 6 of 14 turns, so the limit is about 2.3 times travel time: fine.
- Action: none. Strong as it stands.

**3 · Adrift** — 66
- **Mission:**
  - One X-wing survives TIE waves until rescue.
  - Signature decision: fight in the open, or hide in the asteroids and
    trade time for safety.
- **Scores:** A3 B3 C3 D4 E4 F3 G3 H4 I4.
- SDF: a one-unit duel is vulnerable to dice.
  - The astromech's 6 HP regeneration and asteroid cover soften it.
  - DH: the space rework (#430) changed X-wing and TIE evasion, so the old
    soak results (D8, D7, D6) no longer apply.
  - Human playtest needed (P3 verification).
- CD (clarity): "Destroy every TIE" only wins after the last wave arrives on
  turn 7, and the objective did not say so. **Fixed:** the text now says so
  (P3).

**4 · Shadows of Kashyyyk** — 66
- **Mission:**
  - Leia and the Wookiees hold the tree city through the night against
    Noghri arriving at four edge points.
  - Signature decision: spread the lookouts to see the Noghri coming, or
    keep them close to Leia.
- **Scores:** A3 B3 C4 D3 E3 F3 G4 H4 I3.
- CD (clarity): "Defeat every Noghri" only counts once the last wave arrives
  on turn 9. **Fixed:** the objective text now says so (P3).
- SDF: this is the second "survive to the timer, or kill them all" mission in
  a row, after Adrift.
  - The two are told apart by different domains (space against forest) and
    tools (lookouts).
  - Action: kept; recorded in the campaign review (P4).

**5 · Prisoner of Myrkr** — 76
- **Mission:**
  - Luke, without the Force or his lightsaber, sneaks through Karrde's
    compound. Guards have facing, takedowns and an alarm.
  - Signature decision: take a guard down to open a route, or wait for the
    patrol to turn.
- **Scores:** A4 B4 C4 D2 E4 F4 G3 H5 I5.
- **CD (P3): the bonus could never be earned.**
  - The bonus was "Never raise the alarm", but taking the lightsaber, which
    the win requires, raises the alarm by script (`[sw_alert] action=alarm`).
  - `lua/sw_bonus.lua` then marks the bonus failed.
  - **Fixed:** a new `bonus.secure()` locks the bonus in when Luke reaches
    the office unseen. The bonus is now "Reach Karrde's office without
    raising the alarm".
  - Engine check: `myrkr_bonus_secured`.

**6 · Raid on Karrde's Base** — 82
- **Round 2:** the generic "lose no units" bonus is now "get all six of
  Karrde's people aboard". The win needs 3/4/5, so the bonus trades turns and
  risk for the rest. Engine check `raid_bonus_all_out`.
- **Mission:**
  - Hold the landing field while the transports' engines warm up, and get
    Karrde's people out. Reworked in #427.
  - Signature decision: hold the house or hold the field.
- **Scores:** A5 B4 C4 D4 E4 F3 G4 H4 I4.
- Action: none. Keep it as the reference for evacuation missions.

**7 · The Forest Crossing** — 61
- **Mission:**
  - Luke and Mara cross Myrkr to Hyllyard City, hunted by bikes and
    vornskrs.
  - Signature decision: through the ysalamiri bubbles (no Force, but cover)
    or around them.
- **Scores:** A3 B2 C4 D4 E2 F3 G3 H4 I3.
- **SDF (P4): the turn limit removed the escape's urgency.**
  - The engine route check gives 5 turns of travel against an 18-turn limit,
    about 3.6 times.
  - The pursuit waves on turns 6 and 10 met a player who could wait them
    out.
  - **Fixed:** turns are now 17/15/14, three times travel on Normal; the swift
    achievement is still reachable.
- SDF: the map is mostly uniform forest, and this is the third Myrkr forest
  map in the campaign.
  - Action: recorded only. A map change is a bigger step than the evidence
    supports without a playtest (P4).

**8 · Nomad City** — 79
- **Mission:**
  - Stop raiders stealing mole miners on a sunside world where open sand
    burns.
  - Signature decision: guard the sheds, or intercept stolen miners on their
    way to extraction.
- **Scores:** A4 B4 C4 D4 E3 F4 G4 H4 I5.
- **SDF (P4): the outcome had no consequence**, though the story says these
  miners are the ones used at Sluis Van. **Fixed:**
  - the stolen count carries into Sluis Van: none stolen means one miner
    fewer there, two or more means one more;
  - Nomad City now says so in its objectives;
  - Sluis Van comments on it.
  - Engine check: `miners_stolen_carried`.

**9 · The Sluis Van Shipyards** — 67
- **Mission:**
  - Space defense of four docked warships against mole miners and escorts.
  - Signature decision: screen the docks, or hunt the miners forward.
- **Scores:** A3 B2 C4 D4 E3 F3 G4 H5 I4.
- SDF: the map is mostly empty space with a few asteroid clusters, so
  terrain barely shapes the fight.
  - **Round 2:** a broken asteroid belt (x=15–17) now leaves three open
    lanes, rows 4–5, 9–11 and 15–16. The slow miners must use them, and
    fighters can wait in the rock cover beside them (after the Bilbringi
    map).
- **Round 2:** the bonus is now "save all four docked warships". It replaces
  Thrawn's Gambit's separate +40 credits, so it is paid once. Engine check
  `sluis_van_bonus_all_saved`.

**10 · Thrawn's Gambit** — 75
- **Mission:**
  - Two Star Destroyers attack the shipyards. Win by killing the Judicator,
    crippling the Chimaera, or holding out.
  - Signature decision: defend both warships, or strike one Destroyer hard
    enough to force a withdrawal.
- **Scores:** A4 B2 C4 D4 E4 F4 G4 H5 I4.
- **SDF (P5):** the finale always fielded *Liberty's Hope* and *Valiant*,
  even if one was captured at Sluis Van. **Fixed:** the warships are named
  after Sluis Van survivors (engine check `warship_names`).
- SDF: the map was open, as at Sluis Van. **Round 2:** rock cover in front
  of each warship and between the two Star Destroyers; the lanes stay open.

### Dark Force Rising

**1 · The Noghri Prisoner** — 72
- Signature decision: which attacks are safe enough to force a surrender
  while Leia stays screened.
- **CD (P3): a dice roll could cause a defeat the objective did not
  describe.**
  - Capture was checked only when an attack ended. A multi-strike attack
    could take Khabarakh below a third of his HP and then kill him: he has
    42 HP, and Chewbacca's 10×3 melee can do it from anywhere between 15 and
    30 HP.
  - **Fixed (found by Claude):** the strike that leaves him at a third or
    less subdues him, and a later strike in the same fight captures him
    instead of killing him.
  - Engine check: the sequence's win script is now a real forced-hit attack
    from 20 HP, and Khabarakh must carry into Honoghr.
- **CD (P3, found by Sol):** Force damage (Force Push) could bring him to the
  threshold without any capture check. **Fixed:** a new `sw_force_used` event
  runs the check after every Force power.

**2 · Honoghr** — 71
- **SDF (P4):** route 5 of 16 turns, over three times travel. **Fixed:**
  17/15/14.
- DH (Sol): the four-settlement bonus may force a tour. Left until playtest.

**3 · Jomark** — 72
- **CD (P2, Sol; verified):** every capture added one to the village-loss
  counter.
  - So a village lost, retaken and lost again ended the mission with only one
    village gone.
  - **Fixed:** each village counts once; the objective now reads "two
    different lakeshore villages".
  - Engine check: `village_counted_once`.
- **SDF (P3, Sol):** the turn-5 second boat lands beside the weaker southern
  village with no warning. **Fixed:** an objective note names the turn and
  the rule.

**4 · The Senator's Men** — 68
- **Round 3 bonus:** "Get Han to the Falcon by the end of turn 8": break
  contact fast, or wait for the commandos.
- DH (Sol): the allied commandos may not hold the north street they promise
  to. Needs observation before any change (P4).

**5 · The Peregrine's Nest** — 85
- Strong. Preserve. DH (Sol): the AI may never press the flanks. Watch in
  playtest.

**6 · The Mad Jedi** — 68
- **Round 3 bonus:** "Never let the Force storm catch one of your units",
  which builds on the telegraphed storm.
- **SDF (P3): C'baoth's Force storm hit a random band with no warning.**
  - It added damage without a decision.
  - The owner's own report on 2026-10-16 ("a large flash … does not appear to
    have any effect") shows it was also unreadable.
  - Sol proposed removing the damage.
  - **Fixed differently:** the storm is now telegraphed. C'baoth marks a band
    with lightning markers on the player's odd turn, and it breaks at the
    start of the next turn on anyone still there. It becomes a moving
    barrier the player times the crossing around; same cadence and damage.
  - Engine check: `storm_marked_ahead`.
- DH (Sol, P2 verification): Hard brings back C'baoth's hunt from turn 1.
  Needs a human Hard run.

**7 · The Dark Force** — 53
- SDF (P2, Sol):
  - instant repeat boarding allows a two-turn win with one free shuttle;
  - nothing contests the western derelicts.
  - These are the problems PR #434 already addresses: docking takes a turn,
    a TIE picket, and Imperial shuttles with a head start. No overlapping
    change here.
- CD (P3, Sol): boarded Dreadnaughts keep their zero-movement lock although
  the dialogue says they answer the helm.
  - Recorded; not fixed. Mobile captured cruisers would change this mission's
    and #434's balance, and Battle for the Fleet already gives the ships
    their movement.

**8 · Aboard the Katana** — 83
- Strong. DH (Sol): a weak recall roster may struggle with Luke's corridor.
  Playtest.
- SDF (Sol, P4): the clone "discovery" line comes after The Peregrine's Nest
  has already fielded clones. Recorded for a dialogue pass.

**9 · Battle for the Fleet** — 76
- **Round 3 bonus:** "Lose none of the three Dreadnaughts": the win needs
  only two.
- **SDF (P3, Sol): the exit rule was vague.**
  - The objective said "the eastern edge", while the label and dialogue
    suggested one central jump point.
  - **Fixed:** "any two Dreadnaughts … anywhere in its last two columns".
- **SDF (P3, Sol):** the turn-8 friendly relief was unannounced. **Fixed:**
  a note announces Bel Iblis around turn 8.
- REJ (part): the turn-5 blockers need no warning. They appear at the start of
  the player's turn 5, about seven turns before the Dreadnaughts can reach
  them.

**10 · Honoghr's Choice** — 71
- **CD (P3, Sol; verified): the objective gave the wrong timing.**
  - It said the clans decide "(end of the last turn)", but they declare on
    turn 6.
  - **Fixed:** "Hold out until the end of the last turn". The existing note
    gives turn 6.
- **SDF (P4, Sol): killing Sorrell early skipped the clans' declaration**, the
  finale's payoff. **Fixed:** the declaration now plays once, at victory if
  turn 6 has not come.
- **CD (P4, Sol; verified):** Thrawn reacted to the Noghri break, then the
  end text said he does not know yet. **Fixed:** Thrawn now notes only that
  Sorrell's detachment is overdue.
- CD (P5): the finale showed a gold-carryover note although the campaign ends
  there. **Removed.**
- **SDF (P4, round 2): all three campaign finales were "hold until the last
  turn, or kill X".**
  - **Redesigned as a defense that turns into a counterattack:**
    - The clans answer only to Leia in their clan house, from turn 6, at the
      start of the first turn she is there.
    - Then the player must defeat Sorrell. Outlasting the turn limit no longer
      wins.
    - Killing Sorrell early still wins, and the declaration plays.
  - The signature decision becomes: how much to commit to holding the dukha,
    and when to turn and strike.

### The Last Command

**1 · The Siege of Coruscant** — 70
- **Round 2:** the bonus is now "destroy both minelayers by the end of turn
  8": speed against the growing cordon. Engine check `coruscant_bonus_swift`.
- **SDF (P3, Sol):** Luke said he could feel the cloaked asteroids, but Force
  Sense finds only living things. **Fixed:** Luke now points the fleet to its
  sensors.

**2 · The Smugglers' Council** — 57
- **CD (P2, Sol; verified):**
  - The E-Web crew was added in the 2026-10-04 balance review as the
    garrison's only answer to rifles and the AT-ST.
  - It was dropped from the prestart recruit list when the Slicer was added
    in #396.
  - **Fixed**, and a scan of all 30 missions found no other mismatch between
    a side's recruit list and its prestart list.
  - Engine check: `eweb_recruit`.

**3 · The Palace Infiltrators** — 76
- **Round 4 bonus:** "Keep every infiltrator out of the nursery wing" (3
  hexes): intercept forward, or fall back to the door. Engine check
  `palace_bonus_wing_clear`.
- **SDF (P3, Sol):** victory waits for the turn-7 wave, and the objective did
  not say so. **Fixed.**
- **CD (P3, Sol; verified), shared by every campaign:** the bonus reward said
  "credits next mission", but credits are paid at the next mission where you
  can recruit. **Fixed** in `SW_BONUS_OBJECTIVE`.

**4 · Landfall on Wayland** — 57
- **CD (P3, Sol; verified): the heroes could "cross" without entering the
  river.**
  - The goal region took in two west-bank forest hexes, (24,10) and (24,11).
  - **Fixed:** the goal is now the far bank (x=28, y=9–11), labelled "Far
    Bank".
- **SDF (P4):** route 4 of 16 turns (5 to the far bank). **Fixed:** 17/15/14.
- SDF (Sol, P4): another two-hero jungle crossing right after this one, in
  mission 5. See the campaign review.

**5 · The Natives of Wayland** — 59
- **CD (P3, Sol; verified):** the note said the natives join on turn 4; on
  Easy and Normal they join on turn 2. **Fixed** per difficulty.
- **SDF (P4, Sol + Claude): this played as a second two-heroes-alone jungle
  crossing**, right after Landfall on Wayland.
  - Same map size and western start; the natives appeared at the map corners
    on turn 2.
  - Its bonus asked the two heroes to hold four settlements the allies could
    not count toward.
  - **Redesigned as an alliance battle:**
    - The Myneyrshi (north) and Psadan (south) war parties start at their own
      villages, defending them, and join the advance on turn 2 (Hard: 4).
      They are the same units as before.
    - The garrison raids those villages for tribute (an AI target goal), as
      the opening dialogue already says.
    - The signature decision becomes: help the villages hold, or strike the
      outpost while the garrison is out raiding.
    - The bonus is now "Lose none of the native warriors".
    - Engine checks: `natives_hold_villages`, `allies_bonus_armed`.
  - **Risk:** the allies are on the map a turn earlier, which makes the
    opening safer. Playtest whether the garrison's raids keep it tough.

**6 · The Gates of Mount Tantiss** — 74
- **SDF (P3, Sol):** the gate reserve comes out when any unit comes within six
  hexes, unannounced. **Fixed:** an objective note says so.

**7 · The Cloning Vats** — 73
- DH (Sol, P3): recovery may depend on having kept a medic from mission 6,
  since there are no villages and no medic recruits. Weak-roster playtest
  first.

**8 · The Throne Room** — 53
- **CD (P2, Sol; verified in engine source): the hold was undone before the
  AI moved.**
  - The lock that holds C'baoth and the guards while Luuke lives ran in
    `side 2 turn`.
  - Movement is restored after that event (`play_controller.cpp`: `side_turn`
    fires before `new_turn`).
  - **Fixed:** it now runs at `side 2 turn refresh`.
- **CD (P2, Sol; verified):**
  - The objectives promise nobody can use the Force inside Mara's ysalamiri
    field, but Force lightning (Luuke, C'baoth) had no ysalamiri rule.
  - **Fixed in the unit generator:** lightning fails if the caster or the
    target is in a ysalamiri bubble. It is shown in the help as the special
    "Force".
  - Engine checks: `lightning_blocked_in_field`, `lightning_outside_field`.

**9 · The Bilbringi Shipyards** — 72
- **Round 3 bonus:** "Destroy three platforms by the end of turn 10": speed
  against the mines the yards keep seeding.
- **SDF (P3, Sol):** reactor blasts and turn-6 mines were explained only after
  they hit. **Fixed:** the objective notes now describe both.

**10 · The Last Command** — 68
- **REJ (Sol, P3 "rear reserve is a foreknowledge trap"):** the turn-4
  interceptors appear at the start of the **player's** turn and act on the
  enemy's. The player sees them a full turn ahead, which the standard (§1.3)
  counts as fair warning.
- DH (Sol, P4): survival may favor running away over holding a line.
- **Round 3: redesigned as the trilogy's assault finale**, which also answers
  that finding.
  - The scripted turn-10 win is gone.
  - The Grand Admiral falls when the Chimaera is brought to half strength
    (Rukh strikes while the bridge is under fire), or when both escorts are
    destroyed.
  - Easy gets 16 turns.
  - The three finales now have three shapes: three objectives at Sluis Van,
    defense then counterattack at Honoghr, and an assault here.
  - Risk: the hardest mission loses its safe route. A Normal playtest is
    needed.

---

## 3. Open items needing human play

| Mission | Question |
|---|---|
| Adrift | Is the one-X-wing duel fair after the space rework? |
| The Mad Jedi, Hard | Is there a reliable opening against C'baoth's turn-1 hunt? Is the telegraphed storm readable? |
| The Throne Room | With lightning blocked in the field and the hold fixed, is the duel now winnable on Normal and still tense? |
| The Last Command | Survival versus holding a line; can the escort-kill victory be reached? |
| Aboard the Katana, The Cloning Vats | Weak-roster recovery |
| The Dark Force | After #434: two viable boarding plans on each difficulty |
| Forest Crossing, Honoghr, Landfall | Are the tighter turn limits tense but fair? |
