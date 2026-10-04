# Mission balance review — 2026-10-04

Owner goal: missions should be **tough**, with fun coming from **several
approaches to each mission**, but never **feel impossible**.

This document records the review of all 30 missions. For each balancing
update it gives the cause, the update and its measured effect on play.

## 1. Principles used

From tactical-game and Wesnoth balancing guidance:

- **Balance with several levers, not just gold.** Starting gold alone is a
  blunt tool. Enemy income, enemy recruit lists, reinforcement timing,
  terrain, AI parameters (aggression, targets, guardians) and village
  placement give finer control. A few extra enemy units can make the first
  engagement impossible ([Wesnoth: BuildingScenariosBalancing][wesnoth-bal]).
- **The first engagement must be survivable.** Players should be able to
  finish a campaign on the first attempt without repeated reloads. Better
  strategy, not luck, should win a mission ([Wesnoth: CampaignStrategies][wesnoth-camp]).
- **Avoid cascading, punishing failure.** Missions should allow graceful
  failure: losses that cost you something without ending the run. Avoid
  set-ups where one unlucky turn decides everything
  ([Game Developer: a deep dive into XCOM and XCOM 2][xcom]).
- **Multiple approaches.** Give objectives and tools, and let the player
  choose: fight, sneak, take another route, or use special tools. A higher
  difficulty should make the riskier approaches costlier, not remove them
  ([God Slayer mission design][godslayer]).
- **Turn limits must leave a buffer.** They should motivate, not demand a
  perfect run ([Wesnoth: BuildingScenariosBalancing][wesnoth-bal]).
- **Difficulty levels must differ meaningfully.** Normal should be
  challenging but not punishing; Hard may keep the harsh original pressure.

[wesnoth-bal]: https://wiki.wesnoth.org/BuildingScenariosBalancing
[wesnoth-camp]: https://wiki.wesnoth.org/CampaignStrategies
[xcom]: https://www.gamedeveloper.com/design/a-deep-dive-into-xcom-and-xcom-2
[godslayer]: https://thegameswiki.com/the-god-slayer/wiki/mission-design/diff

## 2. Method

**1. Static numbers.** `production/tools/mission_balance_report.py` reads the
installed engine's own preprocessor output for every campaign on Easy, Normal
and Hard. Per mission it reports:

- turns and villages;
- each side's gold, income, recruits and starting army (cost and HP);
- reinforcements by turn;
- a force ratio: enemy value over player value;
- a warning if the player can recruit but does not start on a keep.

**2. Play data.** `run_ai_soak.py --player careful` hands the player's side to
the engine AI, set to value its own units (heroes above all), and plays every
mission to the end. Each mission ran 3 times per round, 90 games per round,
over 4 rounds. The soak now records:

- a per-turn trace: units, HP and gold per side, and the player heroes' HP;
- each death with its killer;
- the opening threat: how many enemies can reach each hero on the first enemy
  turn.

**3. Reading each mission's objectives and scripts.**

**Caveat.** The AI player is much weaker than a person. It fights with its
heroes, marches into invulnerable bosses, and cannot sneak or carry
objectives. Its defeats are therefore not a difficulty measure in
themselves. The signal used is **how and when** it loses:

- a named hero dead on turn 1–3, every run, means the first engagement is too
  harsh;
- unspent gold means the player cannot act at all.

## 3. Findings and updates

### 3.1 Systemic: losing any one hero lost the mission

**Cause.** Most missions listed 2–5 named heroes whose death meant defeat
(The Gates of Tantiss listed five). Heroes are also the army's strongest
fighters, so they end up in combat, and the enemy AI focuses them.

In the baseline, **45 of 90 games were lost by turn 3**, nearly always to one
hero's death in a single enemy turn:

- Mara on turn 1 in The Throne Room;
- Leia on turn 2 in every run of The Noghri Prisoner;
- Lando on turns 1–2 in The Cloning Vats;
- Luke's X-wing on turns 2–3 in every fleet battle.

This is the cascading, one-bad-turn failure that the guidance warns against.

**Update.** Each mission now has **critical heroes**: the leader, plus any hero
the objective is about. Only their death loses the mission. Every other hero
**withdraws badly wounded** when they fall (`SW_HERO_WITHDRAWS`,
`utils/hte_macros.cfg`):

- the hero is gone for the rest of the mission, with all their firepower;
- they return, healed, for the next mission;
- allies who are temporary to one mission simply leave
  (`SW_HERO_WITHDRAWS_TEMPORARY`).

Engine basis: if WML removes the dying unit in `last breath`, the death is
cancelled (`src/actions/attack.cpp`, `unit_killed`). `[harm_unit]` and `[kill]`
fire the same event, so Force powers and hazards are covered too.

Other details:

- Objectives now name only the critical heroes, and a note lists who
  withdraws.
- Where an objective needed a withdrawable hero to arrive, it now reads "...
  (with Mara/Lando, if still in the fight)": Landfall on Wayland, The Forest
  Crossing and Raid on Karrde's Base.
- `SW_HERO` restores a returning hero's form, so Luke withdrawn in his X-wing
  comes back on foot.
- The Field Manual's "Heroes" topic explains the rule.

| Mission | Critical | Withdraws |
|---|---|---|
| Ambush at Bpfassh | Leia | Han, Chewbacca |
| Shadows of Kashyyyk | Leia | Chewbacca |
| Raid on Karrde's Base | Han | Lando; Karrde (temporary) |
| The Forest Crossing | Luke | Mara (temporary) |
| Nomad City | Lando | Han |
| Sluis Van, Thrawn's Gambit, The Dark Force, Battle for the Fleet, Siege of Coruscant, Bilbringi, The Last Command | Wedge | Luke (X-wing) |
| The Noghri Prisoner | Leia | Chewbacca |
| Honoghr, Honoghr's Choice, The Palace Infiltrators | Leia | Chewbacca, Khabarakh |
| The Senators' Men | Han | Lando |
| Peregrine's Nest | Han | Lando, Bel Iblis |
| Aboard the Katana | Luke | Han, Lando, Chewbacca |
| The Smugglers' Council | Karrde | Mara |
| Landfall on Wayland, The Natives of Wayland, The Throne Room | Luke | Mara |
| The Gates of Tantiss | Han | Leia, Lando, Chewbacca, Khabarakh |
| The Cloning Vats | Han | Lando, Chewbacca |
| The Mad Jedi | Luke, Mara | — (Mara flies the escape ship) |
| Single-hero missions | the hero | — |

**Impact.** Fleet battles now run to the turn limit or end in victory, where
before they were lost on turns 2–3:

- Bilbringi: 0 → 2 wins in 3.
- Battle for the Fleet: lasts to turn 8–17.
- Sluis Van: 1 → 3 wins in 3.

Ground missions also last much longer: The Gates of Tantiss from turns 2–3 to
turns 5–16, and Peregrine's Nest from turns 3–4 to turns 9–12. Losing a hero
still costs the player real strength, so the missions stay tough.

### 3.2 Systemic: Jedi could not answer rifle fire

**Cause.** A side effect of the weapon-range update (#336):

- rifles reach 2 hexes;
- a Jedi's blaster deflection reached only 1.

So a stormtrooper 2 hexes from Luke shot him every turn without reply. Luke
was killed by riflemen or scout troopers in Landfall on Wayland, The Natives
of Wayland and Aboard the Katana. In the lore, a Jedi turns bolts back at
whoever fired them.

**Update.** Deflection reaches 2 hexes (`gen_hte_units.py` `WEAPON_RANGES`). It
still only returns fire, never starts it, and takes the usual −10% at 2 hexes.

**Impact.** Luke now trades fire with riflemen at range:

| Mission | Luke's losses before | After |
|---|---|---|
| Landfall on Wayland | turns 3–4 | turns 5–7 |
| The Natives of Wayland | turns 2–3 | turns 4–9 |
| Aboard the Katana | turns 2–3 | turns 4–12 |

### 3.3 Bug: two maps had no keep

**Cause.** Shadows of Kashyyyk and The Noghri Prisoner give Leia 100–110 gold
and a Wookiee recruit list, but she never recruited: the gold stayed unspent
all mission. Their map generators drew walkway paths outward from the keep
hex after placing the keep, which painted over it. Both missions were played
by two heroes against waves of Noghri.

**Update.**

- Keeps are placed after the paths, and both maps were regenerated (2 hexes
  each).
- The report tool now warns about this case, and it is recorded in
  `docs/WORKTREE_LESSONS.md`.

**Impact.**

- Shadows of Kashyyyk: 0 → 2 wins in 3.
- The Noghri Prisoner: 0 → 2 wins in 3 (all 3 previously lost on turn 2).

### 3.4 Mission-specific updates

All changes apply to Easy and Normal. **Hard keeps the original pressure**, as
noted for each mission.

**The Mad Jedi**

*Cause:*
- C'baoth is invulnerable here and started 5 hexes from Luke, inside his
  reach of 5 moves plus 2-hex Force lightning.
- He had an AI goal to hunt Luke, at aggression 0.8.
- Luke was struck on turn 1 and lost on turn 2 or 3 in every run.
- This contradicts the lore: C'baoth wants an apprentice, not a corpse.

*Update:*
- C'baoth waits by the river at 12,9 as a guardian, just outside Luke's
  starting reach. He covers both the ford and the bridge.
- A blow from C'baoth that would kill Luke leaves him at 1 HP instead, so the
  militia and the Force storm can still finish him.
- Approaches: north ford, south bridge, or a Force Speed dash past him.
- Hard: the original hunt.

*Impact:* the opening threat to Luke is now 0 (it was 1 attacker with 48
potential damage). The AI player still loses here by charging the
invulnerable C'baoth, which a person would not do.

**The Throne Room**

*Cause:*
- C'baoth, Luuke and two Royal Guards attacked at once, at aggression 0.9.
- Mara or Luke fell on turn 1 or 2 in every run.

*Update:*
- C'baoth sends his clone first: he and the guards hold the throne without
  moving while Luuke lives, striking only what comes next to them (C'baoth's
  lightning reaches 2).
- When Luuke falls, all of them attack.
- Aggression drops from 0.9 to 0.6.
- Approaches: draw Luuke into Mara's ysalamiri field, where nobody can use the
  Force, or duel him in the open.
- Hard: the original all-out attack.

*Impact:* defeats moved from turns 1–2 to turns 4–5.

**The Noghri Prisoner**

*Cause:* as well as the missing keep, the Noghri strike team reached Leia on
turn 2, before any screen could form.

*Update:*
- The Noghri stalk in place for the first turn (guardian), then close in from
  turn 2.
- Hard: no delay.

*Impact:* together with the keep fix, 2 wins in 3. The defeat comes on turn 4
at the earliest.

**The Smugglers' Council**

*Cause:*
- Karrde could recruit only pistol smugglers, reaching 1 hex.
- The Empire's rifles reach 2 hexes and the AT-ST 3, with 200 gold plus 9
  income from a keep 11 hexes away.
- The garrison was shot apart without reply: every player unit died by turns
  3–6.

*Update:*
- An E-Web crew joins the recruit list: a black-market heavy repeater
  reaching 3 hexes.
- Imperial gold and income: Normal 200/9 → 170/7, Easy 150/6 → 130/5. Hard
  unchanged.
- Approaches: hold to the last turn, or defeat Colonel Mardek.

*Impact:*
- Force ratio on Normal: 1.05 → 0.92.
- Defeats on turns 4–8. It stays one of the hardest missions for the AI
  player, which does not use the fortress walls.

**The Natives of Wayland**

*Cause:*
- Luke and Mara alone faced the garrison and its recruits for three turns
  before the native allies arrived on turn 4.
- They were lost on turns 2–3.

*Update:*
- The natives arrive on turn 2 (Hard: turn 4).
- Imperial gold and income: Normal 110/5 → 90/4, Easy 80/3 → 70/3.

*Impact:*
- Force ratio on Normal: 1.25 → 1.09.
- Defeats moved from turns 2–3 to turns 4–9.

### 3.5 Reviewed and left as is

These need no change. Either their numbers and play are in range, or the AI
player cannot judge them.

| Mission | Approaches available | Why no change |
|---|---|---|
| Ysalamiri Harvest | Harvest order and routes; escort vs speed | AI player cannot carry the frames; ratio 0.23 |
| Ambush at Bpfassh | Cross the city by streets or parks; air support | Runs to the turn limit; withdrawal covers Han and Chewbacca |
| Adrift | Survive to the turn limit, or destroy the whole patrol | 1–2 wins in 3 across rounds; a survival duel by design |
| Prisoner of Myrkr | Stealth, takedowns, cover, patrol timing (reworked in #337) | AI player cannot sneak; survives to the turn limit |
| Nomad City | Defeat Harbid, or hold to the last turn | 3 of 3 wins after withdrawal |
| Thrawn's Gambit | Destroy the Judicator, cripple the Chimaera, or hold | Lasts to turns 6–13 |
| Jomark | Defeat Tannick, guard the villages | 2 wins in 3 |
| The Senators' Men | Reach the Falcon; air support | Runs to the turn limit |
| Peregrine's Nest | Hold the generator, or defeat Tierce | Lasts to turns 9–12 |
| The Dark Force | Race to board Dreadnaughts; pick which ones | Lasts to turns 8–17 |
| Honoghr | Reach Nystao by several routes | 2 wins in 3 in the last round; slow droids can be outrun |
| Honoghr's Choice | Hold, or defeat Sorrell | Lasts to turns 4–7 |
| The Siege of Coruscant | Hunt the minelayers through cloaked asteroids | 3 of 3 wins |
| The Palace Infiltrators | Find the infiltrators; sensors, Noghri allies | 3 of 3 wins |
| The Gates of Tantiss | Destroy the generator; air support; varied recruits | Lasts to turns 5–16 |
| The Cloning Vats | Destroy the cylinders in any order | 2 wins in 3 |
| Bilbringi | Destroy any 3 of 4 platforms | 2 wins in 3 |
| The Last Command | Hold to turn 10, or destroy both escorts | Lasts to turns 5–6; finale (see below) |

### 3.6 Open items for human playtesting

- **The Last Command and The Throne Room** remain the hardest missions for the
  AI player. They are campaign finales: they should be the hardest, but a
  person should confirm they are winnable on Normal.
- **Raid on Karrde's Base** sometimes loses Han, the leader, on turn 2–3 to the
  starting AT-ST, when he is pushed forward. Keep him behind the line.
- **Hard** keeps the original pressure on the missions listed above. On Hard,
  levers compound: less player gold, more enemy gold and income, and fewer
  turns, giving force ratios up to about 3.2 in The Last Command. Hard is
  meant to be punishing.

## 4. Measured results

Careful AI player, Normal, 3 runs per mission. Each entry is the outcome and
turn: V = victory, D = defeat; D15 means a defeat on turn 15, typically the
turn limit.

| Mission | Before | After |
|---|---|---|
| Ysalamiri Harvest | D17 D17 D17 | D17 D17 D17 |
| Ambush at Bpfassh | D5 D15 D15 | D15 D15 D15 |
| Adrift | V9 V9 D8 | D8 D7 D6 |
| Shadows of Kashyyyk | D5 D3 D4 | V12 V15 D6 |
| Prisoner of Myrkr | D15 D15 D15 | D15 D15 D15 |
| Raid on Karrde's Base | D3 D6 D4 | D16 D3 D2 |
| The Forest Crossing | D5 D6 D8 | D6 D6 D6 (Mara withdrew on turns 4–5; the AI's Luke then fought alone) |
| Nomad City | D10 D5 V15 | V15 V15 V15 |
| Sluis Van Shipyards | D4 D3 V8 | V8 V8 V9 |
| Thrawn's Gambit | D3 D2 D4 | D6 D7 D7 |
| The Noghri Prisoner | D2 D2 D2 | V4 V5 D4 |
| Honoghr | D4 D4 D3 | V5 D4 V7 |
| Jomark | D5 D6 V10 | V9 D6 V12 |
| The Senators' Men | D4 D3 D3 | D15 D15 D14 |
| Peregrine's Nest | D3 D4 D3 | D12 D9 D11 |
| The Mad Jedi | D5 D2 D2 | D2 D2 D3 (AI charges the invulnerable C'baoth) |
| The Dark Force | D2 D3 D2 | D8 D17 D17 |
| Aboard the Katana | D3 D3 D3 | D4 D12 D7 |
| Battle for the Fleet | D3 D3 D3 | D14 D8 D17 |
| Honoghr's Choice | D2 D3 V4 | D4 D7 D5 |
| The Siege of Coruscant | V8 V10 V8 | V8 V9 V10 |
| The Smugglers' Council | D6 D4 D5 | D8 D5 D5 |
| The Palace Infiltrators | V8 V9 V8 | V11 V8 V8 |
| Landfall on Wayland | D4 D4 D3 | D5 D7 D6 |
| The Natives of Wayland | D2 D3 D3 | D9 D4 D6 |
| The Gates of Tantiss | D2 D2 D3 | D5 D7 D16 |
| The Cloning Vats | D2 D3 D1 | V12 V11 D13 |
| The Throne Room | D1 D1 D2 | D4 D5 D5 |
| Bilbringi | D3 D3 D3 | V9 D17 V10 |
| The Last Command | D3 D2 D2 | D6 D5 D6 |

**Totals over 90 games:**

| Measure | Baseline | Round 1 | Round 2 | Round 3 |
|---|---|---|---|---|
| Wins | 12 | 16 | 18 | 24 |
| Defeats by turn 3 | 45 | 16 | 9 | 6 |

Note: Mara's withdrawal in The Forest Crossing was added after round 3; its
row comes from 3 separate runs after the change.

## 5. Tools

- **`production/tools/mission_balance_report.py`:** static numbers for every
  mission and difficulty, from the engine's own preprocessor output, plus the
  keep check.
- **`production/linux_engine/run_ai_soak.py` and `ai_soak_plugin.lua`:**
  per-turn balance trace, killers, and opening threat in the evidence JSON.
- **Engine tests (`run_systems_tests.py --suite air`):** hero withdrawal,
  both outside combat (`[harm_unit]`) and in combat. The hero leaves the map,
  is kept healed, and the scenario continues.
