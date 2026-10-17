# Campaign Design Review

**Date:** 2026-10-17. **Standard:** [MISSION_DESIGN_STANDARD.md](MISSION_DESIGN_STANDARD.md) §4.
**Per-mission evidence:** [SCENARIO_AUDIT.md](SCENARIO_AUDIT.md).

Good missions do not automatically make a good campaign. This review looks
at the three campaigns as sequences: variety, difficulty curve, army and
gold, consequences between missions, how mechanics are introduced, and
narrative pacing. The Dark Force Rising and The Last Command sections draw
on Sol 6.1's campaign assessments, verified and edited by Claude.

---

## 1. The sequences at a glance

| # | Heir to the Empire | Dark Force Rising | The Last Command |
|---|---|---|---|
| 1 | Tutorial collection (Imperial) | Capture | Space hazard sweep and assault |
| 2 | Escape with escort (city) | Covert crossing | Fortress defense |
| 3 | Space survival (one hero) | Spread-out defense, then assault | Interception defense |
| 4 | Night defense and survival | Escape (city) | Escape (jungle) |
| 5 | Infiltration and escape | Fortress defense | Assault with allies (jungle) |
| 6 | Evacuation under assault | Escape past an invulnerable pursuer | Assault on a gate |
| 7 | Escape with escort (forest) | Space boarding race | Demolition (interior) |
| 8 | Defense against raids, with a hazard | Interior assault | Commander confrontation |
| 9 | Space defense | Space escort | Space assault |
| 10 | Space finale (three objectives) | Defense finale | Space survival finale |

Ground and space: 8 of the 30 missions are space battles. Heir to the Empire
and The Last Command both end with two space missions in a row.

### Mission types across the campaigns

| Type | Count | Missions |
|---|---|---|
| Escape or traversal | 8 | HTE 2, 5, 7; DFR 2, 4, 6; TLC 4; DFR 9 (escort) |
| Defense or survival | 10 | HTE 3, 4, 6, 8, 9; DFR 3, 5, 10; TLC 2, 3 |
| Assault or demolition | 7 | DFR 8; TLC 1, 5, 6, 7, 9; HTE 10 (partly) |
| Special | 5 | HTE 1 (collection); DFR 1 (capture), 7 (race); TLC 8 (boss), 10 (finale) |

**Reading.** Heir to the Empire is almost entirely reactive: the player
escapes, defends or survives in nine of ten missions. This is deliberate.
Thrawn holds the initiative in the first book, and the campaign ends with
the first real counterstroke (Thrawn's Gambit). The Last Command reverses it,
with seven of ten missions offensive, which is also the story. Dark Force
Rising is the most varied. **No type quota is recommended**: the balance
follows the war.

---

## 2. Repetition

| Pattern | Where | Verdict |
|---|---|---|
| **"Hold until the last turn, or kill X"** | HTE 3, 4, 8, 10; DFR 5, 10; TLC 2, 10. **All three finales.** | The most repeated structure. Each instance differs in map and enemy, so no single mission is weak because of it, but the three finales feel alike in structure. **Done (round 2):** Honoghr's Choice is now hold the clan house until the clans rise, then break Sorrell's detachment; the timer no longer wins. **Round 3:** The Last Command is now an assault (Chimaera to half strength, or both escorts), with no timer win. The three finales now have three shapes. |
| **Hero reaches one hex** | HTE 2, 7; DFR 2, 4, 6, 8; TLC 4 | Told apart by terrain and opposition. Kept. The escape turn limits were too generous in three of them (below). |
| **"Survive or kill all" twice in a row** | HTE 3 → 4 | Different domain (space, then forest) and tools. Kept; noted. |
| **Two-hero jungle crossing twice in a row** | TLC 4 → 5 | The clearest local repetition (Sol). Same map size, same western two-hero opening, same jungle. **Done:** mission 5 is now an alliance battle. The native war parties hold their villages from turn 1, the garrison raids them, and the bonus is to lose none of them. |
| **Space maps mostly empty** | HTE 9, 10; DFR 7, 9; TLC 1, 10 | 6 of 8 space maps are open void with a few asteroid clusters; Bilbringi (TLC 9) is the exception and the model. **Recommendation:** an asteroid-lane pass on the Sluis Van and Thrawn's Gambit maps, after the space rework (#430) has been played. |
| **Generic bonus objectives** | Before: "lose no units" 9 times, "keep heroes" 10, "hold villages" 7. After rounds 2–4, "lose no units" is left only in The Dark Force (reworked in PR #434) | They reward preservation but rarely create a different way to play. The good exceptions are Adrift (destroy the patrol) and Prisoner of Myrkr (stay unseen). **Recommendation:** when a mission is next reworked, give it a bonus that is a real trade-off for that mission. |
| **Fixed-turn reinforcements** | Most missions | Mostly fine. Conditional ones are better (Jomark's boat, Thrawn's Gambit's flanking bombers, the Gates sortie), provided they are announced; three were not, and are now. |

---

## 3. Difficulty progression

Force ratios on Normal, before the 2026-10-17 changes. They are rough
accounting, not combat strength: the enemy's gold and units over the
player's. The audit found two flaws in them:

- The report counted a neutral side as enemy. This is fixed, and it affected
  The Dark Force.
- It counts each reinforcement declaration once, even when the event repeats.

| # | HTE | DFR | TLC |
|---|---|---|---|
| 1 | 0.23 | 1.00 | 1.40 |
| 2 | 0.92 | 0.73 | 0.99 (the E-Web was missing) |
| 3 | 2.40 (survival) | 1.32 | 0.54 |
| 4 | 1.10 | 1.00 | 1.09 |
| 5 | 2.17 (stealth) | 1.21 | 1.09 |
| 6 | 1.30 | 1.04 | 1.12 |
| 7 | 1.55 | (counted neutral derelicts) | 1.18 |
| 8 | 1.43 | 0.64 | 2.20 (boss) |
| 9 | 0.61 | 1.36 | 2.46 |
| 10 | 2.01 | 0.98 | 2.60 |

- **Heir to the Empire** rises from a gentle tutorial to a hard finale. The
  low Sluis Van ratio (0.61) is a breather before the finale, which is
  appropriate.
- **Dark Force Rising** is flat (0.64–1.36) apart from The Dark Force. Its
  finale is no harder than its middle. The defense finale Honoghr's Choice
  (0.98) was also winnable early by killing Sorrell, now with its payoff
  intact. **Recommendation:** leave numbers alone until there is human
  evidence; the owner reported The Dark Force as too easy, which #434
  addresses.
- **The Last Command** has the steepest curve and the two weakest missions by
  score (The Throne Room 53, the Smugglers' Council 57), both because of
  defects that are now fixed. The fixes make both missions easier:
  - the Council gets its E-Web back;
  - the Throne Room's lightning is blocked in the field and the guards hold
    as intended.
  This was intended by the 2026-10-04 balance review and is the fair
  baseline. It needs a human check that neither becomes too easy.

**Owner goal check ("tough, several approaches, never impossible").** No
mission was found unwinnable. Seven confirmed defects made missions harder
or more confusing than designed: Jomark, the Smugglers' Council, the Throne
Room (two), the Noghri Prisoner (two) and Prisoner of Myrkr's bonus. Two
problems made missions easier than designed: Landfall's goal could be met on
the near bank, and three escapes had turn limits over three times their
travel time.

---

## 4. Army, gold and recall

- **Carryover** is 40% of remaining gold. The bonus bank pays in full at the
  next mission **where the player can recruit**; the objective text now says
  so.
- **Restricted missions** (hero-only, no recruiting) compound the 40% cut:
  - In The Last Command, missions 4, 5 and 8 cannot recruit. 100 extra
    credits at the end of mission 3 are worth about 6 by mission 6 (Sol).
  - The bonus bank is what carries value across those stretches.
  - **Recommendation:** keep it, and keep the base gold of each recruiting
    mission enough on its own to win; it currently is, by design.
- **Domains:** ground and space veterans cannot reinforce each other
  (PR #428 recalls each only into its own battles). A strong ground army
  does not help Battle for the Fleet. This is the intended trade-off; the
  space missions' base gold covers it.
- **Command decisions** (DFR 4, TLC 3: supply, cadre or counter-intelligence)
  shape later economy unevenly (Sol). The AI soak always picks supply, so
  the other two paths are untested. **Recommendation:** soak each choice
  once.
- **Medics:** The Cloning Vats has no medic recruit and no villages.
  **Recommendation (needs a playtest):** consider adding the field medic if a
  weak roster cannot recover.

---

## 5. Consequences between missions

Before this review, only **Sluis Van → Thrawn's Gambit** (all four warships
saved gives 40 credits) and the Khabarakh capture carried outcomes forward.

Added (bounded, per standard §4.4):

- **Nomad City → Sluis Van:** none stolen means one mole miner fewer; two
  or more means one more. This is announced in Nomad City.
- **Sluis Van → Thrawn's Gambit:** the finale's warships are the ones that
  survived, by name.

**Recommendations:**

- **The Dark Force → Battle for the Fleet:** the number of Dreadnaughts
  secured could set how many escape candidates the player has. This depends
  on #434.
- **The Smugglers' Council → The Last Command:** how many chiefs survive
  could set the size of Karrde's turn-6 relief.

---

## 6. How mechanics are introduced

- **Heir to the Empire** introduces one system per mission, in good order:
  - movement and recruiting;
  - air support and hidden Noghri;
  - space;
  - lookouts;
  - stealth and takedowns;
  - evacuation timers;
  - ysalamiri bubbles;
  - the sunside hazard;
  - space defense;
  - Thrawn's doctrine.
- **Dark Force Rising, mission 1** stacks hidden Noghri, lookouts, hero
  withdrawal and a "don't kill him" capture. The capture rule is now
  reliable, which was the dangerous part.
- **The Last Command, mission 1** opens a campaign that can be started on its
  own with cloaking, sensors, hazards, limited ordnance and Thrawn's doctrine
  at once. Luke's briefing used to point at the wrong tool (the Force); it
  now points at the sensors.
- **Telegraphing.** The Mad Jedi's storm now teaches the same "marked area,
  then strike" pattern that air support already uses.

---

## 7. Narrative pacing

All three campaigns alternate their story threads well (Leia, Luke, Han and
Lando, the fleet). The strongest arcs are HTE 5–7 (Myrkr) and DFR 7–9 (find
the fleet, take the flagship, escape). The weak point is the four
consecutive Wayland missions in The Last Command (escape, outpost, gate,
vats). They are in the right order. Missions 4 and 5 played too much alike;
mission 5 is now an alliance battle (§2).

Continuity fixes made:

- Honoghr's Choice: Thrawn no longer learns of the Noghri defection before
  the story says he does.
- Honoghr's Choice: the clans' declaration always plays.
- Thrawn's Gambit: the warships are named after Sluis Van's survivors.
- Coruscant: Luke no longer claims a Force ability he does not have.

---

## 8. Campaign-level changes: done and recommended

| Change | Status |
|---|---|
| Fix confirmed objective and logic defects in 9 missions | **Done** (MISSION_IMPROVEMENT_LOG.md) |
| Announce scripted threats before they matter (Jomark, Gates, Bilbringi, Battle for the Fleet relief) | **Done** |
| Escape turn limits at most about 3× unobstructed travel (engine route check) | **Done** for The Forest Crossing, Honoghr and Landfall; added to the standard |
| Bounded consequences between missions | **Done** for Nomad City → Sluis Van → Thrawn's Gambit |
| Fix the force-ratio tool for neutral sides | **Done** |
| Give one finale a structure other than "hold or kill" | **Done (round 2):** Honoghr's Choice is now hold the clan house, then counterattack Sorrell; no win by timer |
| Rework TLC 5 into an alliance battle | **Done** (natives at their villages from turn 1, garrison raids, ally-preservation bonus) |
| Asteroid lanes on the Sluis Van and Thrawn's Gambit maps | **Done (round 2):** a three-lane belt at Sluis Van; cover patches at Thrawn's Gambit. Playtest after the space rework |
| Mission-specific bonus objectives | **Rounds 2–3:** also The Senator's Men (Falcon by turn 8), The Mad Jedi (never caught by the storm), Battle for the Fleet (no Dreadnaught lost), Bilbringi (three platforms by turn 10); earlier: Raid on Karrde's Base (all six aboard), Sluis Van (all four warships), Siege of Coruscant (minelayers by turn 8), Natives of Wayland (no native losses) |
| Soak each command-decision branch | Recommended |
| Human playtest of the open items (SCENARIO_AUDIT.md §3) | Required before any further balance change |
