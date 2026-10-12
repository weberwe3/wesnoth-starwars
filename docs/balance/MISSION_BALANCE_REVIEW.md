# Mission balance review â€” 2026-10-04

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

- a named hero dead on turn 1â€“3, every run, means the first engagement is too
  harsh;
- unspent gold means the player cannot act at all.

## 3. Findings and updates

### 3.1 Systemic: losing any one hero lost the mission

**Cause.** Most missions listed 2â€“5 named heroes whose death meant defeat
(The Gates of Tantiss listed five). Heroes are also the army's strongest
fighters, so they end up in combat, and the enemy AI focuses them.

In the baseline, **45 of 90 games were lost by turn 3**, nearly always to one
hero's death in a single enemy turn:

- Mara on turn 1 in The Throne Room;
- Leia on turn 2 in every run of The Noghri Prisoner;
- Lando on turns 1â€“2 in The Cloning Vats;
- Luke's X-wing on turns 2â€“3 in every fleet battle.

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
| The Mad Jedi | Luke, Mara | â€” (Mara flies the escape ship) |
| Single-hero missions | the hero | â€” |

**Impact.** Fleet battles now run to the turn limit or end in victory, where
before they were lost on turns 2â€“3:

- Bilbringi: 0 â†’ 2 wins in 3.
- Battle for the Fleet: lasts to turn 8â€“17.
- Sluis Van: 1 â†’ 3 wins in 3.

Ground missions also last much longer: The Gates of Tantiss from turns 2â€“3 to
turns 5â€“16, and Peregrine's Nest from turns 3â€“4 to turns 9â€“12. Losing a hero
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
still only returns fire, never starts it, and takes the usual âˆ’10% at 2 hexes.

**Impact.** Luke now trades fire with riflemen at range:

| Mission | Luke's losses before | After |
|---|---|---|
| Landfall on Wayland | turns 3â€“4 | turns 5â€“7 |
| The Natives of Wayland | turns 2â€“3 | turns 4â€“9 |
| Aboard the Katana | turns 2â€“3 | turns 4â€“12 |

### 3.3 Bug: two maps had no keep

**Cause.** Shadows of Kashyyyk and The Noghri Prisoner give Leia 100â€“110 gold
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

- Shadows of Kashyyyk: 0 â†’ 2 wins in 3.
- The Noghri Prisoner: 0 â†’ 2 wins in 3 (all 3 previously lost on turn 2).

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

*Impact:* defeats moved from turns 1â€“2 to turns 4â€“5.

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
  3â€“6.

*Update:*
- An E-Web crew joins the recruit list: a black-market heavy repeater
  reaching 3 hexes.
- Imperial gold and income: Normal 200/9 â†’ 170/7, Easy 150/6 â†’ 130/5. Hard
  unchanged.
- Approaches: hold to the last turn, or defeat Colonel Mardek.

*Impact:*
- Force ratio on Normal: 1.05 â†’ 0.92.
- Defeats on turns 4â€“8. It stays one of the hardest missions for the AI
  player, which does not use the fortress walls.

**The Natives of Wayland**

*Cause:*
- Luke and Mara alone faced the garrison and its recruits for three turns
  before the native allies arrived on turn 4.
- They were lost on turns 2â€“3.

*Update:*
- The natives arrive on turn 2 (Hard: turn 4).
- Imperial gold and income: Normal 110/5 â†’ 90/4, Easy 80/3 â†’ 70/3.

*Impact:*
- Force ratio on Normal: 1.25 â†’ 1.09.
- Defeats moved from turns 2â€“3 to turns 4â€“9.

### 3.5 Reviewed and left as is

These need no change. Either their numbers and play are in range, or the AI
player cannot judge them.

| Mission | Approaches available | Why no change |
|---|---|---|
| Ysalamiri Harvest | Harvest order and routes; escort vs speed | AI player cannot carry the frames; ratio 0.23 |
| Ambush at Bpfassh | Cross the city by streets or parks; air support | Runs to the turn limit; withdrawal covers Han and Chewbacca |
| Adrift | Survive to the turn limit, or destroy the whole patrol | 1â€“2 wins in 3 across rounds; a survival duel by design |
| Prisoner of Myrkr | Stealth, takedowns, cover, patrol timing (reworked in #337) | AI player cannot sneak; survives to the turn limit |
| Nomad City | Defeat Harbid, or hold to the last turn | 3 of 3 wins after withdrawal |
| Thrawn's Gambit | Destroy the Judicator, cripple the Chimaera, or hold | Lasts to turns 6â€“13 |
| Jomark | Defeat Tannick, guard the villages | 2 wins in 3 |
| The Senators' Men | Reach the Falcon; air support | Runs to the turn limit |
| Peregrine's Nest | Hold the generator, or defeat Tierce | Lasts to turns 9â€“12 |
| The Dark Force | Race to board Dreadnaughts; pick which ones | Lasts to turns 8â€“17 |
| Honoghr | Reach Nystao by several routes | 2 wins in 3 in the last round; slow droids can be outrun |
| Honoghr's Choice | Hold, or defeat Sorrell | Lasts to turns 4â€“7 |
| The Siege of Coruscant | Hunt the minelayers through cloaked asteroids | 3 of 3 wins |
| The Palace Infiltrators | Find the infiltrators; sensors, Noghri allies | 3 of 3 wins |
| The Gates of Tantiss | Destroy the generator; air support; varied recruits | Lasts to turns 5â€“16 |
| The Cloning Vats | Destroy the cylinders in any order | 2 wins in 3 |
| Bilbringi | Destroy any 3 of 4 platforms | 2 wins in 3 |
| The Last Command | Hold to turn 10, or destroy both escorts | Lasts to turns 5â€“6; finale (see below) |

### 3.6 Open items for human playtesting

- **The Last Command and The Throne Room** remain the hardest missions for the
  AI player. They are campaign finales: they should be the hardest, but a
  person should confirm they are winnable on Normal. Soak 2026-10-11 (careful
  AI player, Normal, 3 runs each): no early losses -- The Throne Room lost
  Luke to Luuke on turns 5-6 (the duel; the AI player never uses Mara's
  ysalamiri to strip the clone's powers), The Last Command lost Wedge to TIEs
  on turns 5-6 (the AI player flies its leader into the fighting). Left
  unchanged pending a human playtest.
- **Raid on Karrde's Base** sometimes lost Han, the leader, on turn 2â€“3 to the
  starting AT-ST when he was pushed forward. Addressed in 3.12 (the walker
  starts further back on Easy and Normal); a person should confirm it.
- **Hard** keeps the original pressure on the missions listed above. On Hard,
  levers compound: less player gold, more enemy gold and income, and fewer
  turns, giving force ratios up to about 3.2 in The Last Command. Hard is
  meant to be punishing.

### 3.7 Ability review (2026-10-10)

Owner goal: abilities that enhance play and balance while staying within the
lore. Three changes (`production/tools/gen_hte_units.py`):

| Unit | Change | Lore | Play |
|---|---|---|---|
| Chewbacca, Wookiee Warrior | **Wookiee rage** on their melee attack: +25% damage below half hit points | A Wookiee's temper is legendary | A wounded Wookiee is dangerous up close: finish it or keep away. Melee only, so it rewards closing in rather than adding raw power |
| Han Solo | **Skirmisher** | A smuggler who slips past blockades | Han flanks and breaks contact where others are pinned; a distinct role from Leia and Lando, who lead |
| Vornskr | **Force hunter** now matches every Force user (`sw_ability_force`), not only Luke and C'baoth | Karrde's vornskrs react to Mara Jade on sight | Mara and Leia now draw the beasts too: guard Force users in Myrkr's forests |

Not changed: Noghri stealth and backstab, Thrawn's tactical genius, the
leaders' leadership, the starfighter specials and the Force profiles already
match their sources and their roles.

### 3.8 Automatic overwatch (2026-10-11)

Owner direction: a unit that does not use its attack during a turn and can go
on overwatch takes it automatically at the end of the turn. This was already
the rule for AI sides; it now applies to the player too
(`lua/sw_overwatch.lua`, `ow.on_side_turn_end`). Units that attacked, used a
power or sensor sweep that costs the attack, or are dazed are left as they
are. Choosing Overwatch from the menu still takes it earlier (and ends the
unit's movement). Automatic entries are not reported to Thrawn's Doctrine,
which learns only from overwatch the player chooses, so the Grand Admiral
does not gain Insight every turn for free. Off switch:
`sw_overwatch_auto=no` (all sides); `sw_overwatch_ai=no` still turns it off
for AI sides only.

Only units that can actually attack take it (`ow.can_attack`, also used by the
menu): an attack left this turn, attacks at all (`max_attacks`), not
petrified, not an unaware guard, not dazed, and an overwatch weapon whose
specials allow attacking.

### 3.9 Achievements (2026-10-11)

Replay goals for each campaign, in the main menu's Achievements screen
(`achievements.cfg`, `lua/sw_achievements.lua`): complete it; complete it on
Hard; complete it with no hero ever withdrawing; **Hit and Run** (win each
mission with at least a third of its turns unused -- hold-out missions
excluded); and **Ace** (destroy armed enemy starfighters and warships: 30 in
Heir to the Empire, 20 in Dark Force Rising, 30 in The Last Command; an AI
player destroyed 26, 17 and 29 in one run of each campaign's space battles).
A Tactics group rewards using the systems (Force powers, chosen overwatch,
sensor sweeps, air support) and completing all three campaigns. Only the
human player earns them; the engine skips replays.

### 3.10 Just-in-time tips (2026-10-11)

The tactical systems were explained only in the Field Manual menu, so a new
player could miss most of them. `lua/sw_tips.lua` shows a short Field Manual
tip at the start of the player's turn the first time a system matters --
weapon ranges, the Force, overwatch, flanking, sensor contacts, air support,
getting in unseen, ysalamiri fields, Thrawn's doctrine, ranks -- at most one
per turn, each once per playthrough (`sw_tips_seen`, carried between
missions). Each tip offers "Turn off tips" (`sw_tips_off`); the Field Manual
has "Show the tips again".

### 3.11 Bonus objectives (2026-10-11)

Owner goal: fun from several approaches to each mission. Every mission except
the three finales now has one optional objective, shown in its objectives as
a "Bonus objective" (`SW_BONUS` / `SW_BONUS_OBJECTIVE`, `lua/sw_bonus.lua`).
Kinds, matched to each mission: hold N settlements; lose no units; keep named
heroes in the fight (those most likely to withdraw there); never raise the
alarm (Prisoner of Myrkr); Adrift's own "destroy the whole patrol", whose old
note promised a reward that nothing paid. Losing one is announced when it
happens. Reward: 40-50 credits, banked at victory and paid in full -- not cut
by the 40% gold carryover -- at the start of the next mission where the
player can recruit (`sw_bonus_bank`). Finales have none: their gold does not
carry into the next campaign.

### 3.12 Raid on Karrde's Base: the opening walker (2026-10-11)

Cause: the starting AT-ST at (5,9) is 8 hexes from Han, the critical hero;
with 4 moves and a 3-hex twin cannon it reached him on turn 2 whenever he
stepped forward -- a one-bad-turn loss of the kind 3.1 removes elsewhere.
Update: on Easy and Normal it starts on the Imperial landing apron at (2,9),
11 hexes away, giving Han a turn to set up; Hard keeps it at (5,9).
Measured (AI soak, careful player, Normal, 3 runs): Han fell on turns 4 and
6 (before: turns 2-3), and the third run lasted to turn 16 without losing him.

### 3.13 Mission debrief (2026-10-11)

A mission used to end with no word on how it went. At victory the player now
sees one debrief (`lua/sw_debrief.lua`): the turn it was won on, enemies
destroyed, units lost, heroes withdrawn, the bonus objective's result (it
replaces the separate bonus message) and, where it applies, the Hit and Run
target ("win by turn N for a swift victory"). Shown only to the human player.
After each campaign's finale a **campaign summary** follows: missions won,
enemies destroyed, units lost, heroes withdrawn, bonus objectives earned and
swift victories (`sw_campaign_stats`, carried between the missions).

### 3.14 Finale twists (2026-10-11)

The two space finales had no events once the battle began. Each now has a
Thrawn move and an answer to it (Easy/Normal/Hard counts):

| Mission | Thrawn's move | Relief |
| --- | --- | --- |
| Thrawn's Gambit | Turn 5: 2/3/3 TIE bombers (+1 interceptor on Hard) appear beside the warship with fewer defenders within 4 hexes, one turn from it | Turn 8: shipyard picket, 3/2/1 fighters |
| The Last Command | Turn 4: 2/2/3 TIE interceptors appear in the corners behind the strike force | Turn 6: Karrde's smugglers, 3/2/2 fighters (Y-wings with ion cannons) |

The bomber target rewards spreading the defence: piling every fighter on one
warship invites the strike on the other. Honoghr's Choice already has its
own turn 4 and turn 6 events.

### 3.15 Mid-mission events in quiet missions (2026-10-11)

Three more missions had no events after the opening. Each now has a
pressure event and a relief event (Easy/Normal/Hard counts):

| Mission | Pressure | Relief |
| --- | --- | --- |
| Battle for the Fleet | Turn 5: TIEs (2/3/4) sit on the jump point, so the escort must also clear the exit | Turn 8: Bel Iblis's fighters, 3/2/1 |
| The Gates of Mount Tantiss | First attacker within 6 hexes of the generator: the gate opens and 2/3/4 troops (a Royal Guard from Normal) sortie | Turn 5: a Wayland war party, 3/3/2 Myneyrshi and Psadan |
| The Bilbringi Shipyards | Turn 6: 1/2/3 new cloaked asteroids behind the screen, in the approach lanes | A destroyed platform's reactor blasts every adjacent ship for 10 (never lethal), Imperial guards included |

Jomark and The Smugglers' Council follow in Â§3.16.
### 3.16 The traitor and the second boat (2026-10-11)

The last two missions without mid-mission events:

- **The Smugglers' Council:**
  - On turn 5 one surviving chief, chosen at random, turns traitor inside the walls, with a smuggler veteran bodyguard from Normal.
  - He no longer counts as a chief.
  - Killing him pays a 30-credit bounty.
  - This plays out Karrde's opening line that "someone at this table brought them".
- **Jomark:**
  - On turn 5 a second raider boat (2/3/4, with a veteran from Normal) lands beside whichever southern village has fewer of Luke's units within 3 hexes.
  - On a tie it lands at the south-east village.

### 3.17 Command decisions (2026-10-11)

Nothing the player chose shaped a campaign beyond its recruits. Each campaign
now has one decision (`lua/sw_command.lua`), offered at the start of
Shadows of Kashyyyk, The Senator's Men and The Palace Infiltrators, standing
until the campaign ends:

| Choice | Effect | Rough value |
| --- | --- | --- |
| Supply convoy | +25 credits at the start of each later mission where the player recruits | 4-5 missions: about 100-125 credits |
| Veteran cadre | 2 loyal units of the best current recruit at once, half-way to their next level | about 40-60 credits now, no upkeep, and they carry over |
| Counter-intelligence | Thrawn's Doctrine capped at 75 Insight: no Coordinated fire (+10% to hit against studied types) | matters in the Thrawn missions: HTE 9-10, DFR 9, TLC 9-10 |

An AI-controlled player takes the supply convoy. The campaign summary after
the finale names the decision.

### 3.18 Mission feats (2026-10-11)

Four achievements reward the hard way through the new mission events
(`SW_FEAT`, `ach.feat`):

| Feat | Mission | Condition |
| --- | --- | --- |
| Not One Hull | Thrawn's Gambit | win without losing a warship |
| Fleet Intact | Battle for the Fleet | win without losing a Dreadnaught |
| Bounty Paid | The Smugglers' Council | bring down the traitor |
| Breaking the Line | The Last Command | win by destroying both escort Star Destroyers |

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
| The Forest Crossing | D5 D6 D8 | D6 D6 D6 (Mara withdrew on turns 4â€“5; the AI's Luke then fought alone) |
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


## 6. Hero specialization balance (2026-10-11)

Player impact: named heroes can specialize after their final level instead of
always taking +3 HP. Their advancement dialogs offer two or three role-specific,
capped options alongside the existing HP choice, with full healing/cure and the
normal +20% next-XP cost on every selection.

| Heroes | Specializations and caps |
| --- | --- |
| Luke, C'baoth, Luuke | Lightsaber +1 damage twice; +2 maximum Force Points once |
| X-wing Luke | Lasers +1 damage twice; +1 movement once; +2 Force Points once |
| Wedge | Lasers +1 damage twice; +1 movement once |
| Leia | Adjacent-allied healing 4 once; +1 movement once; +2 Force Points once |
| Mara | Vibroblade +1 damage twice; ignore zones of control once; +2 Force Points once |
| Khabarakh | Knives +1 damage twice; ignore zones of control once |
| Han | DL-44 +1 damage twice (normal and aimed); +1 movement once |
| Chewbacca | Melee +1 damage twice; bowcaster +1 damage twice (normal and aimed) |
| Lando, Karrde | Pistol +1 damage twice; adjacent-allied healing 4 once |
| Pellaeon, Thrawn, Bel Iblis | Adjacent-allied healing 4 once; +1 movement once |

Weapon training adds no strikes, range or accuracy. At most +2 damage per
strike, it competes with HP rather than arriving free; a four-strike lightsaber
can gain at most 8 raw damage per exchange. Mobility leaves vision unchanged.
Infiltration also works within ysalamiri fields, where Mara loses Force agility.
Field coordination affects allies adjacent at the commander's turn start,
excludes self, slows poison, and does not stack with medics or Force healing.
Force capacity adds no regeneration, power, discount or cooldown reduction and
still respects ysalamiri suppression; existing per-scenario Force overrides
remain intact. No starting stats, mission events, difficulty settings, recruit
lists, hero withdrawal or defeat conditions change. Native advancement IDs and
caps persist through rank art changes and saves. Existing saves retain any
cached advancement menu until the engine refreshes/rebuilds the unit, as with
veteran training; this feature does not rewrite saved heroes.

Validation against the candidate on Wesnoth 1.19.27:

| Existing gate | Actual result |
| --- | --- |
| Unit generator and inventory | Passed; 56 generated unit types |
| Native progression | 472 checks passed, including 30 real saved-game reload checks |
| Systems, all suites | 542 passed; 0 failed; 0 blocking engine errors |
| Three campaign sequences | All passed: 30 scenario transitions and 30 saved-WML validations |
| Declared gameplay contracts | 102 passed, including Force capacity and the Field Manual |
| Careful-player AI soak, all 30 missions | 30 technical passes; 9 victories and 21 defeats |

Campaign sequence victories are scripted route checks, and their save checks
validate saved WML. Native progression and systems tests separately exercise
real engine reloads. Systems retained 11 known unsynced-controller warnings from
the harness context. No soak mission reported a technical failure; wins and
losses below are ordinary AI outcomes, not evidence of human difficulty balance.

| Mission | AI outcome | Final turn |
| --- | --- | --- |
| sw_hte_01_ysalamiri_harvest | Defeat | 17 |
| sw_hte_02_ambush_at_bpfassh | Defeat | 15 |
| sw_hte_03_adrift | Defeat | 8 |
| sw_hte_04_shadows_of_kashyyyk | Defeat | 11 |
| sw_hte_05_prisoner_of_myrkr | Defeat | 15 |
| sw_hte_06_raid_on_karrdes_base | Defeat | 16 |
| sw_hte_07_the_forest_crossing | Defeat | 4 |
| sw_hte_08_nomad_city | Victory | 15 |
| sw_hte_09_sluis_van_shipyards | Victory | 7 |
| sw_hte_10_thrawns_gambit | Defeat | 6 |
| sw_dfr_01_the_noghri_prisoner | Victory | 3 |
| sw_dfr_02_honoghr | Defeat | 3 |
| sw_dfr_03_jomark | Defeat | 6 |
| sw_dfr_04_the_senators_men | Defeat | 15 |
| sw_dfr_05_peregrines_nest | Victory | 16 |
| sw_dfr_06_the_mad_jedi | Defeat | 5 |
| sw_dfr_07_the_dark_force | Defeat | 17 |
| sw_dfr_08_aboard_the_katana | Defeat | 7 |
| sw_dfr_09_battle_for_the_fleet | Defeat | 9 |
| sw_dfr_10_honoghrs_choice | Victory | 5 |
| sw_tlc_01_the_siege_of_coruscant | Victory | 8 |
| sw_tlc_02_the_smugglers_council | Defeat | 4 |
| sw_tlc_03_the_palace_infiltrators | Victory | 9 |
| sw_tlc_04_landfall_on_wayland | Defeat | 6 |
| sw_tlc_05_the_natives_of_wayland | Defeat | 4 |
| sw_tlc_06_the_gates_of_tantiss | Victory | 8 |
| sw_tlc_07_the_cloning_vats | Defeat | 16 |
| sw_tlc_08_the_throne_room | Defeat | 7 |
| sw_tlc_09_bilbringi | Victory | 14 |
| sw_tlc_10_the_last_command | Defeat | 7 |


## 7. Tactical AI electronic warfare (2026-10-11)

Player impact: enemy scanners choose reachable unidentified contacts and sweep
before combat so their allies can exploit the reading. Decoy carriers use spare
attacks to place false contacts toward threats their team actually knows.

One sweep and one decoy are allowed per AI side per turn. The budget is stored
in ordinary WML state and included in the save/replay digest. Sweep selection
uses contact positions and identification states, scanner range and scan rating;
it does not look up hidden targets or inspect their cloak, health or units
undetected by the team. Decoy placement uses the same public contacts and
visually detected enemies, stays within the existing six-direction launch list,
and avoids adjacency to known hostiles. It does not inspect hidden occupancy.

Both actions spend the unit's existing attack, and decoys spend their finite
unit charge. A scanner cannot also fire, enter overwatch or launch a decoy that
turn. Sweeps retain their higher emissions, existing range/strength and next-turn
expiry; decoys retain ordinary identification, adjacency and expiry counters.
Human-controlled sides, petrified units, unaware guards, and units with no action
are excluded. The existing sw_ew_ai=no switch disables both behaviors. No
starting stats, mission events, difficulty, recruit lists, air/overwatch rules,
hero defeat/withdrawal, achievements, tips, debrief or command choices change.

Validation against the candidate on Wesnoth 1.19.27:

| Existing gate | Actual result |
| --- | --- |
| Unit generator and inventory | Passed; 56 generated unit types |
| Systems, all suites | 566 passed; 0 failed; 0 blocking engine errors |
| Three campaign sequences | All passed: 30 scenario transitions and 30 saved-WML validations |
| Declared gameplay contracts | 104 passed, including both changed Lua paths |
| Careful-player AI soak, all 30 missions | 30 technical passes; 8 victories and 22 defeats |

Systems tests exercise native AI preparation before combat, reachable scanner
selection, action costs, side budgets, incapacitated/unaware exclusions, decoy
contacts and player sweep counterplay. Saved action budgets survive a real
engine reload, and both existing replay tests reproduce their state digests.
The harness retained 12 known unsynced-controller warnings; no blocking
engine error remained. The initial petrification fixture failure and diagnostic
are retained in validation evidence; only its incorrect attack expectation was
repaired, with the confirmed cause recorded in the worktree lessons.

Campaign sequence victories are scripted route checks, with saved-WML validation;
they do not demonstrate native reloads or human difficulty balance. The soak
outcomes below are ordinary AI outcomes, including every loss. Mission events,
starting forces and balance settings are unchanged.

| Mission | AI outcome | Final turn |
| --- | --- | --- |
| sw_hte_01_ysalamiri_harvest | Defeat | 17 |
| sw_hte_02_ambush_at_bpfassh | Defeat | 15 |
| sw_hte_03_adrift | Defeat | 6 |
| sw_hte_04_shadows_of_kashyyyk | Victory | 14 |
| sw_hte_05_prisoner_of_myrkr | Defeat | 15 |
| sw_hte_06_raid_on_karrdes_base | Defeat | 5 |
| sw_hte_07_the_forest_crossing | Defeat | 6 |
| sw_hte_08_nomad_city | Victory | 15 |
| sw_hte_09_sluis_van_shipyards | Victory | 8 |
| sw_hte_10_thrawns_gambit | Defeat | 6 |
| sw_dfr_01_the_noghri_prisoner | Victory | 4 |
| sw_dfr_02_honoghr | Defeat | 4 |
| sw_dfr_03_jomark | Defeat | 6 |
| sw_dfr_04_the_senators_men | Defeat | 8 |
| sw_dfr_05_peregrines_nest | Defeat | 15 |
| sw_dfr_06_the_mad_jedi | Defeat | 6 |
| sw_dfr_07_the_dark_force | Defeat | 10 |
| sw_dfr_08_aboard_the_katana | Defeat | 4 |
| sw_dfr_09_battle_for_the_fleet | Defeat | 17 |
| sw_dfr_10_honoghrs_choice | Victory | 3 |
| sw_tlc_01_the_siege_of_coruscant | Victory | 10 |
| sw_tlc_02_the_smugglers_council | Defeat | 5 |
| sw_tlc_03_the_palace_infiltrators | Victory | 9 |
| sw_tlc_04_landfall_on_wayland | Defeat | 5 |
| sw_tlc_05_the_natives_of_wayland | Victory | 7 |
| sw_tlc_06_the_gates_of_tantiss | Defeat | 16 |
| sw_tlc_07_the_cloning_vats | Defeat | 15 |
| sw_tlc_08_the_throne_room | Defeat | 5 |
| sw_tlc_09_bilbringi | Defeat | 17 |
| sw_tlc_10_the_last_command | Defeat | 5 |

## 8. Wounded-unit withdrawal and target selection

Ordinary AI troops at 40% maximum HP or less now look for a safe withdrawal before stand-off combat when a genuinely visible armed threat is within its current weapon range plus one hex. A destination must be reachable this turn through native terrain and zone-of-control rules, respect the AI's avoid locations, increase distance to the nearest visible armed enemy by at least two hexes, and lie beyond every visible enemy's current weapon reach. Distance preference caps at six hexes; cover, nearby armed allies and ordinary healing terrain improve the rating, with a small travel-distance penalty. Leaders and unaware or petrified troops are excluded. The installed core healing-retreat candidate action remains available and keeps its higher priority where applicable.

A completed or interrupted withdrawal that actually changes the troop's hex spends its remaining movement and attacks, preventing default combat from sending it straight back. A failed attempt is tried only once per unit per turn. No extra movement, healing, damage or accuracy is granted. Players can block escape routes with zones of control, cover their pursuit and exploit the withdrawn troop's spent attack. A unit that has already used its attack, including a sensor action, can still withdraw using its remaining movement.

Worthwhile legal stand-off attacks retain their existing expected-damage, kill and return-fire ratings, then gain at most four preference points for damage already suffered by a visible target and at most four for lacking nearby armed support. One armed ally within two hexes halves the isolation preference; two remove it. These terms only rank attacks that already meet the four-point baseline. Known occupied firing hexes and native visible flanking units are used; hidden occupants, hidden supporters and hidden enemies do not influence planning. Native movement and post-movement legality checks still resolve actual ambushes and changing combatants.

The Field Manual explains formation, withdrawal costs and pursuit counters. Mission events, starting forces, recruitment, difficulty values and Claude's mission polish are unchanged.

Validation against the candidate on Wesnoth 1.19.27:

| Existing gate | Actual result |
| --- | --- |
| Unit generator and inventory | Passed; 56 generated unit types |
| Systems, all suites | 601 passed; 0 failed; 0 blocking engine errors |
| Three campaign sequences | All passed: 30 scenario transitions and 30 saved-WML validations |
| Declared gameplay contracts | 104 passed; changed ranged-AI path already covered |
| Careful-player AI soak, all 30 missions | 30 technical passes; 9 victories and 21 defeats |

Systems tests exercise bounded wounded/isolation preferences, the worthwhile-shot
minimum, native hidden-occupant visibility, withdrawal eligibility and AI avoid
locations, a real AI-turn withdrawal, ordinary movement/attack costs, and actual
reload of the withdrawn troop position, health and spent actions. Both existing
replay tests reproduce their state digests; these digests include unit positions
and health rather than every action-budget field.
The harness retained 14 known unsynced-controller warnings; no blocking
engine error remained. The initial equal-rifle fixture failure and one bounded
native diagnosis are retained. That fixture was repaired: preserve the
below-baseline duel as a negative, then establish a worthwhile positive case
by restricting both fixture defenders to one-hex retaliation. The repaired
air portion of the full systems run passed 259 checks; its cause and prevention are
recorded in the worktree lessons. The full run also caught an AI-only action
budget change that was absent from replay. Withdrawal now records its
stand-down through a native synced command registered on every load/replay,
committed by a native fire_event so empty-action cleanup cannot discard it,
so air support and overwatch see the same spent actions. Both original
failed runs and their actual repaired checks are retained. Registration lives
in the dynamic systems loader so existing campaign saves retain the command;
a real load of a retained save with the older macro expansion passed.

Campaign sequence victories are scripted route checks with saved-WML parsing;
they do not demonstrate native reloads or human difficulty balance. The soak
outcomes below are ordinary AI outcomes, including every loss. Mission events,
starting forces, recruitment and difficulty settings are unchanged.

| Mission | AI outcome | Final turn |
| --- | --- | --- |
| sw_hte_01_ysalamiri_harvest | Defeat | 17 |
| sw_hte_02_ambush_at_bpfassh | Defeat | 15 |
| sw_hte_03_adrift | Defeat | 8 |
| sw_hte_04_shadows_of_kashyyyk | Defeat | 10 |
| sw_hte_05_prisoner_of_myrkr | Defeat | 15 |
| sw_hte_06_raid_on_karrdes_base | Defeat | 4 |
| sw_hte_07_the_forest_crossing | Defeat | 8 |
| sw_hte_08_nomad_city | Victory | 15 |
| sw_hte_09_sluis_van_shipyards | Victory | 8 |
| sw_hte_10_thrawns_gambit | Defeat | 7 |
| sw_dfr_01_the_noghri_prisoner | Victory | 4 |
| sw_dfr_02_honoghr | Defeat | 4 |
| sw_dfr_03_jomark | Defeat | 4 |
| sw_dfr_04_the_senators_men | Defeat | 15 |
| sw_dfr_05_peregrines_nest | Defeat | 6 |
| sw_dfr_06_the_mad_jedi | Defeat | 6 |
| sw_dfr_07_the_dark_force | Defeat | 17 |
| sw_dfr_08_aboard_the_katana | Defeat | 3 |
| sw_dfr_09_battle_for_the_fleet | Defeat | 17 |
| sw_dfr_10_honoghrs_choice | Victory | 3 |
| sw_tlc_01_the_siege_of_coruscant | Victory | 8 |
| sw_tlc_02_the_smugglers_council | Defeat | 5 |
| sw_tlc_03_the_palace_infiltrators | Victory | 8 |
| sw_tlc_04_landfall_on_wayland | Defeat | 4 |
| sw_tlc_05_the_natives_of_wayland | Victory | 7 |
| sw_tlc_06_the_gates_of_tantiss | Defeat | 17 |
| sw_tlc_07_the_cloning_vats | Victory | 12 |
| sw_tlc_08_the_throne_room | Defeat | 6 |
| sw_tlc_09_bilbringi | Victory | 13 |
| sw_tlc_10_the_last_command | Defeat | 6 |


## 9. Smuggler Slicer

Karrde's existing roster has two gunfighters. The new directly recruitable
Smuggler Slicer offers reconnaissance and deception in The Smugglers' Council:
it can recover contacts through interference, improve identification with a
sweep, or expend a finite decoy instead of firing. It uses the existing EW
systems and their existing action costs.

| Choice | Cost | HP | Move | Pistol | Vibroknife | Sensors | Counter-jamming | Sweep | Decoys |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Existing Smuggler | 13 | 34 | 6 | 7×2 | 5×3 | 2 / 3 hexes | 0 | 0 | 0 |
| New Smuggler Slicer | 18 | 28 | 6 | 5×2 | 4×2 | 3 / 5 hexes | 1 | +2 | 2 finite charges |

The extra five gold buys information rather than durability or gun damage.
Its adjacent-only pistol cannot answer a rifle at two hexes. Gunhands screen
the specialist while its contacts help the team. A sweep spends the attack,
raises sensors to 5 and range to 7 until the next turn, and increases emissions.
A decoy also spends an attack and one finite charge. Neither action adds
movement, healing, damage or accuracy. Stronger enemy sensors and physical
contact still answer deception.

Only the two player recruit declarations in TLC02 gain the new ID; their
existing entries are retained. Existing unit statistics, advancement chains,
mission events, starting forces, objectives, difficulty, rewards and Claude's
polish behavior are preserved. The new type cannot arise from HTE06's old
Smuggler advancement chain, so its rescue/debrief type filters stay unchanged.
All fourteen Smuggler sprite frames and its portrait are reused byte-for-byte
under the new unit's own paths, with its painted muzzle metadata retained.

Validation against the candidate on Wesnoth 1.19.27:

| Existing gate | Actual result |
| --- | --- |
| Unit generator and inventory | Passed; 57 generated unit types |
| Systems, all suites | 620 passed; 0 failed; 0 blocking engine errors |
| Three campaign sequences | All passed: 30 scenario transitions and 30 saved-WML checks |
| Declared gameplay contracts | 105 passed, including the generated Lua registry row |
| Existing art/wiring validation | All 14 sprite frames and the portrait passed |
| Existing CI art self-test | 17 passed after adding the Slicer art-direction entry |
| Careful-player AI soak, all ten TLC missions | 10 technical passes; 3 victories and 7 defeats |

The first PR 396 CI run identified a missing art-direction registry entry for
the new type. One description now matches the reused art; all other entries,
art assets, gameplay and engine-fixture bytes remain unchanged. The complete
17-test art self-test passes after the repair, with the failed run retained.

The native paid recruit command charges 18 gold and creates the Slicer with
spent movement and attack, preventing an immediate sweep or decoy. The existing
intel fixture checks its generated equipment, jammed contact recovery, sweep
identification, attack costs, and exhaustion after two decoys. Explicit fixture
action refreshes isolate the finite-charge limit; they are not proof of multiple
legal native-turn launches. Actual save/reload retains its type, position, health,
equipment, spent movement and attack, and the remaining charge. Both existing
replay cases pass and reproduce four state digest checkpoints each; these are
system-wide replay checks, not a separate Slicer-specific replay route.
The harness retains 15 unsynced-controller warnings with the same message
as the previous candidate; no blocking engine error remained.

The touched TLC02 soak ended in defeat on turn 3, compared with turn 5 in
the preceding candidate. Allied chiefs died while Karrde and Mara still had
full health. Recruited unit types are not recorded, so the Slicer’s contribution
cannot be established; this is not a controlled balance comparison. Both TLC02
logs retain ten pre-existing formula type-error messages. Raw logs remain
available: a technical pass is not proof that every AI evaluation is correct.

Campaign sequences are scripted route checks and saved-WML parsing. They do
not reload every sequence save or establish human difficulty. The soak includes
all ten TLC missions to check compatibility with possible later roster carryover.
Its single automated player profile may choose other recruits; its outcomes do
not establish the Slicer’s tactical value or human balance. Every loss is retained.

| Mission | AI outcome | Final turn |
| --- | --- | --- |
| sw_tlc_01_the_siege_of_coruscant | Victory | 12 |
| sw_tlc_02_the_smugglers_council | Defeat | 3 |
| sw_tlc_03_the_palace_infiltrators | Victory | 9 |
| sw_tlc_04_landfall_on_wayland | Defeat | 4 |
| sw_tlc_05_the_natives_of_wayland | Defeat | 6 |
| sw_tlc_06_the_gates_of_tantiss | Defeat | 14 |
| sw_tlc_07_the_cloning_vats | Defeat | 17 |
| sw_tlc_08_the_throne_room | Defeat | 5 |
| sw_tlc_09_bilbringi | Victory | 11 |
| sw_tlc_10_the_last_command | Defeat | 5 |
