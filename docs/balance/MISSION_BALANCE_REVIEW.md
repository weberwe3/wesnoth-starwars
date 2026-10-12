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

### 3.19 Rank abilities (2026-10-12)

Owner direction: a rank-up must bring a passive or active ability specific to
the unit's class and rank, not only a stat increase, so that keeping units
alive is rewarded. Reaching rank I, II or III now also grants that class's
ability for the rank (`production/tools/rank_abilities.py`, generated into
`lua/sw_rank_abilities.lua`, granted by `lua/sw_rank.lua` as a permanent
object), on top of the advancement's own choice (+3 HP or a drill). Each
unit's description lists its three, so players see what a veteran is working
towards.

Second owner rule: do not pile on attack types. No rank adds an attack. Each
ability is either a native ability (steadfast, skirmisher, hiding in forest or
settlements, regeneration, heals +8, adjacent auras of +10% to hit, -10% to hit
for adjacent enemies, or +10% resistance) or a special on a weapon the unit
already carries (first strike, marksman, slows, backstab, drains, guard, or
extra damage against a target class); a weapon's aimed shot gets the same
special. The generator refuses a special a weapon already has.

| Unit | Rank I | Rank II | Rank III |
| --- | --- | --- | --- |
| `sw_unit_nr_sergeant` | Fire discipline | Hold the line | Covering fire (blaster rifle) |
| `sw_unit_im_stormtrooper_sergeant` | Fire discipline | Hold the line | Covering fire (blaster rifle) |
| `sw_unit_nr_commando` | Jungle fighter | Knife work (vibroknife) | Saboteur (blaster carbine) |
| `sw_unit_bi_commando` | Disciplined | Marksman training (blaster rifle) | Corellian tactics |
| `sw_unit_nr_eweb_team` | Dug in | Suppressing fire (eweb repeater) | Armour-piercing (eweb repeater) |
| `sw_unit_nr_field_medic` | Field surgery | Field dressings | Rapid evacuation |
| `sw_unit_wk_warrior` | Battle roar | Thick hide | Wookiee fury (ryyk blade) |
| `sw_unit_wk_lookout` | Sniper's perch (bowcaster) | Forest ghost | Pinning shot (bowcaster) |
| `sw_unit_nr_xwing` | Wingman | Tuned deflectors | Ace (laser cannons) |
| `sw_unit_nr_awing` | Afterburners | Dogfighter (laser cannons) | Ace (laser cannons) |
| `sw_unit_nr_ywing` | Ion lock (ion cannon) | Armoured hull | Ship-killer (proton torpedoes) |
| `sw_unit_im_tie_fighter` | Wingman | Dogfighter (laser cannons) | Ace (laser cannons) |
| `sw_unit_im_tie_interceptor` | Afterburners | Dogfighter (laser cannons) | Ace (laser cannons) |
| `sw_unit_im_tie_bomber` | Bombardier (concussion bombs) | Armoured hull | Ship-killer (concussion bombs) |
| `sw_unit_im_scout_trooper` | Speeder jockey | Strafing run (bike blaster) | Ramming speed (ram) |
| `sw_unit_im_officer` | Fire discipline | Hold the line | Expert marksman (blaster pistol) |
| `sw_unit_im_at_st` | Armoured hull | Suppressing fire (twin blaster cannon) | Elevated targeting (concussion grenade) |
| `sw_unit_im_noghri` | Stun mastery (stun blaster) | Ghost | Death from the shadows (noghri knives) |
| `sw_unit_im_royal_guard` | Imperial Guard | Bodyguard | Riposte (force pike) |
| `sw_unit_im_infiltrator` | Ghost | Stun setting (blaster pistol) | Silent kill (vibroknife) |
| `sw_unit_im_decon_droid` | Reinforced plating | Self-repair | Caustic spray (sprayer) |
| `sw_unit_sm_veteran` | Quick draw (blaster pistol) | Dirty fighting (vibroknife) | Old hand |
| `sw_unit_sm_slicer` | Slip away | Overload shot (blaster pistol) | Street camouflage |
| `sw_unit_wy_myneyrshi` | Bow mastery (bow) | Steady | War cry |
| `sw_unit_wy_psadan` | Stone hide | Crushing blow (war club) | Recuperation |
| `sw_hero_luke` | Jedi reflexes | Lightsaber form (lightsaber) | Jedi serenity |
| `sw_hero_xwing_luke` | Wingman | Tuned deflectors | Ace (laser cannons) |
| `sw_hero_leia` | Rally | Hold the line | Force intuition |
| `sw_hero_han` | Trick shot (heavy blaster pistol) | Smuggler's nerve | Fearless |
| `sw_hero_chewbacca` | Battle roar | Thick hide | Wookiee recovery |
| `sw_hero_lando` | Gambler's nerve | Fire discipline | Expert marksman (blaster pistol) |
| `sw_hero_mara` | Emperor's Hand (vibroblade) | Hardened | Assassin (vibroblade) |
| `sw_hero_karrde` | Old fox | Fire discipline | Contingency plan |
| `sw_hero_wedge` | Wingman | Tuned deflectors | Ace (laser cannons) |
| `sw_hero_khabarakh` | Stun mastery (stun blaster) | Silent kill (noghri knives) | Clan honour (noghri knives) |
| `sw_hero_bel_iblis` | Veteran commander | Fire discipline | Corellian tactics |

Units that only promote (troopers, militia, stormtroopers, clone troopers,
smugglers) earn their ranks once promoted; sergeants and smuggler veterans
start at rank I and receive its ability with the promotion. Vehicles,
shuttles, capital ships, installations, creatures and the enemy's named
commanders have none. Hero rank abilities never repeat a hero's own
specialization choices (Mara's and Khabarakh's infiltration, the field
coordination of Leia, Lando and Karrde). Existing veterans in saved
campaigns receive the abilities for their rank at the next mission start.

The AI uses all of these natively. Balance needs a human playtest: veterans on
both sides are stronger than before, most noticeably Imperial sergeants with
fire discipline and enemy TIE aces.

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

## 10. Wookiee Suppressor

Kashyyyk's two Wookiee recruits previously offered direct combat or detection.
The new Suppressor adds control: an ordinary concussive bowcaster hit slows
the target, reducing its damage and pursuit until it ends a turn.

| Wookiee choice | Gold | HP | Move | Ryyk blade | Bowcaster | Role |
| --- | --- | --- | --- | --- | --- | --- |
| Existing Warrior | 18 | 48 | 5 | 8×3 | 10×2 | Direct combat |
| Existing Lookout | 15 | 38 | 6 | 5×2 | 8×2 | Keen senses and sensors |
| New Suppressor | 22 | 34 | 5 | 4×2 | 4×2, Slow | Control support |

The bowcaster reaches two hexes; its aimed variant is 4×1 with +20% accuracy
before distance penalties, available only on offense at two hexes. Slow is the
native weapon special, triggered by a hit in ordinary combat, including return
fire. It halves attack damage and doubles movement costs; it neither stuns
nor prevents attacks. A miss still spends the attack and applies no status.
The target clears Slow when it ends a turn. Overwatch uses the existing damage
volley system and does not apply Slow, so reserving an attack trades control
for reaction damage.

Higher cost, fewer hitpoints and much weaker weapons prevent the specialist
from replacing a Warrior. No keen-senses upgrade replaces the Lookout.
Warriors screen it from assault; Lookouts expose hidden Noghri. Existing
veteran training and rank rules apply without changing older units.

Integration with Claude's class-specific ranks assigns this new type only:
Veteran grants thick hide (positive defensive resistance doubled to at most
50%, no change to vulnerabilities or offense); Seasoned veteran adds covering
fire (first strike on the existing bowcaster and aimed variant, while aimed
shots remain offense-only); Elite grants fire discipline (adjacent allies
+10 percentage points ranged hit chance, nonstacking, no self or melee bonus).
The base Slow is retained once per bowcaster and no rank adds an attack.
Every prior catalogue entry, assignment and rank-runtime behavior is preserved.
The combined native run below includes these rank assignments and preserves
Claude's original rank checks.

Only the two player recruit declarations in HTE04 gain the new ID. Every old
entry, starting force, gold amount, turn limit, difficulty, objective, reward,
wave and Claude-owned mission event is retained. The fourteen original warm-brown
Lookout sprite frames and portrait are reused byte-for-byte, with matching
muzzle metadata and a new art-direction entry. Claude's later gray Warrior
and Lookout artwork is preserved, keeping this recruit visually distinct.

Native Windows Wesnoth 1.19.27 validation passed 682 systems checks, including
all six main/load phases with real saves and reloads, with zero systems engine
errors. 14 existing synthetic-controller warnings remain recorded. Both
existing intelligence/air replay battles passed four original and four replay
checkpoints each; these are not Suppressor-specific replay battles.

Focused native checks recruited a Suppressor for 22 gold through the actual
paid recruit command, then verified its spent actions, generated profile,
legal normal and aimed attacks, unmodified aimed accuracy, on-hit Slow,
halved damage, doubled grass movement cost, normal return-fire Slow, the
target's next turn, native expiry, and an actual miss. Native AMLAs also verify all three rank
effects, positive defensive resistances without altering offense or fire
vulnerability, both bowcasters' first strike, the ranged-only adjacent allied
accuracy aura, lack of self/melee/distant bonuses, no duplicate grants or
specials, and the rank cap. The real reload retains an elite rank snapshot. Hit/miss tests temporarily
force 100%/0% accuracy to isolate the mechanic and restore the shipped weapon
specials afterward. Save/reload checks reconstruct the captured on-hit unit
snapshots, remove only their private engine identities, then save and reload
them; reconstruction is not another combat. The native reload retains HP,
spent actions, coordinates, Slow and the original weapon without fixture certainty.

All three campaign sequences passed all 30 stages and parsed 30 saves. These
are scripted route checks and saved-WML parsing, not native reloads of every
sequence save or a demonstration of human difficulty. The Windows systems-runner
regression suite passed 29 tests; the sequence suite ran 21 tests with 19
passes and two POSIX-only skips, including a passing actual Windows owned-stop test.
The required runner repair retains crash, nonzero-exit and timeout failures.
The proposed published-player CMD also passed all eight existing synchronization
checks; installed delivery of the merged feature remains a publication gate.

All ten HTE missions passed the existing careful-player AI soak gate: 3
victories and 7 defeats, listed below. Kashyyyk ended in victory turn 12.
The run does not record recruited types, so it does not establish that the AI
used the Suppressor or measure its effect. Raw logs retain formula type-error messages: sw_hte_02_ambush_at_bpfassh (270), sw_hte_04_shadows_of_kashyyyk (264).
Those diagnostics remain preserved; the existing soak gate passing does not
prove that every AI evaluation succeeded. No new diagnostic exemption was added. These single-run outcomes are
compatibility evidence, not a controlled balance comparison or human playtest.

| Mission | AI outcome | Final turn |
| --- | --- | --- |
| sw_hte_01_ysalamiri_harvest | Defeat | 17 |
| sw_hte_02_ambush_at_bpfassh | Defeat | 15 |
| sw_hte_03_adrift | Defeat | 8 |
| sw_hte_04_shadows_of_kashyyyk | Victory | 12 |
| sw_hte_05_prisoner_of_myrkr | Defeat | 15 |
| sw_hte_06_raid_on_karrdes_base | Defeat | 13 |
| sw_hte_07_the_forest_crossing | Defeat | 5 |
| sw_hte_08_nomad_city | Victory | 15 |
| sw_hte_09_sluis_van_shipyards | Victory | 8 |
| sw_hte_10_thrawns_gambit | Defeat | 6 |

### Katana compartment routes — 2026-10-12

The previous map put all four supply villages in sealed rooms. The installed
1.19.27 engine returned no path from Luke's airlock to any of them. Aboard the
Katana now connects those rooms through a northern maintenance passage and a
southern cargo passage. The central spine remains the shortest bridge approach;
the longer routes provide healing access and space to approach defenders from
the side. Cargo crates use the existing native cover terrain: ordinary infantry
get castle-level defense, but crates neither heal nor permit recruiting.

The 26×18 playable footprint, original walkable cells, airlock, bridge, four
villages, initial forces, reinforcement positions/timing, difficulty values,
objectives, hero conditions, rewards and all mission scripts are preserved.
Both sides can use the side routes, including troops arriving at the existing
northern and southern boarding shafts. Old saved missions retain their saved
map; start this mission afresh to get the new layout.

Native Windows Wesnoth 1.19.27 passed 30 main and 30 actual save/reload
checks with no engine errors or warnings. Luke and clone infantry can reach
all four preserved villages. Luke's village routes cost 9, 13, 19 and 8 MP;
the clone's cost 7, 8, 12 and 9 MP respectively. Both existing boarding shafts
remain reachable. The original bridge route still costs 21 MP; northern and
southern routes that exclude the middle spine cost 26 and 24 MP. These are
unopposed geometry checks, comfortably inside both Normal's 16-turn and Hard's
15-turn limits, not mission victories. A normal native move from (6,9) to the
north junction at (6,5) spent four MP and retained its location and one remaining
MP after an actual save and reload. All twelve cargo-cover cells survived that
reload. Infantry movement is one MP on deck and crates, with 40% and 60% defense
respectively; crates grant no healing, village income or recruitment.

The existing gates passed: inventory, all unit/map generator checks, scope,
whitespace, 107 declared contracts, 682 systems checks, and all 30 stages across
the three campaign sequences with 30 readable saved-WML snapshots. Systems
logs retain 15 synthetic-controller warnings, with no engine errors. Their
six main/load phases and both existing replay battles passed. Sequence checks
use scripted routes and parse saved WML; they are not human playtests or native
reloads of every sequence save. All 29 other maps and all 30 scenario CFGs are
byte-identical to the base.

Three careful-player AI soaks of the old layout and three of this layout all
passed the existing technical gate, but all six ended in defeat:

| Layout | Run | AI outcome | Final turn |
| --- | --- | --- | --- |
| Previous | 1 | Defeat — Luke killed | 13 |
| Previous | 2 | Defeat — Luke killed | 5 |
| Previous | 3 | Defeat — Luke killed | 5 |
| Connected compartments | 1 | Defeat — Luke killed | 2 |
| Connected compartments | 2 | Defeat — turn limit | 17 |
| Connected compartments | 3 | Defeat — Luke killed | 5 |

The candidate's second run cleared all defenders by turn 14 and retained Luke
at 47/52 HP on turn 16, but did not reach the bridge before the limit. Every
candidate trace retained Luke at 52/52 HP at the start of turn 2; the first
run's early loss followed its side-1 attack on that turn. Opening threat
estimates recorded at most one enemy with 24 potential damage against Luke
on both layouts. These samples use independent random runs, not paired seeds.
The outcome spread and the turn-2 loss remain recorded; they do not establish
a win-rate improvement, a balance regression, or human difficulty. The verified
benefit is access to previously sealed healing rooms and choices between a
short central approach and longer, contestable flanks. Both sides gain those
routes, so the player still needs to cover the announced boarding shafts.


## Cloning-vat production bays (2026-10-12)

The eight cylinders now sit in distinct durasteel production bays inside Mount
Tantiss, joined by staggered doors, the existing central dispatch aisle and two
hewn service passages. Fourteen equipment-cover hexes create defended positions
for both sides. Cylinder locations, heroes, guards, reinforcements, recruitment,
gold, turns and victory/defeat rules are unchanged. Han remains mission-critical.
The passages connect to the eastern clone entry, so they are contestable.

Layout checks confirm all 240 walkable hexes are connected, compared with
244 in the old hall. Installed Wesnoth 1.19.27 confirms all eight cylinders have
vacant adjacent attack positions reachable by Han, a New Republic trooper,
a Noghri and a clone guard in unopposed native path checks. Han's original central advance to (23,9) still
costs 20 MP; his cheapest approaches to the cylinders cost 9-18 MP. These
measurements describe available routes, not a win or a safe route through guards.

Han, Republic troopers and clones have 40% defense on these floors; the tested
Noghri has 50%. Equipment cover gives all four tested types 60% defense, retains
one-MP movement and grants no healing, income or recruitment. Bulkheads and
surrounding rock walls remain impassable. Both sides can reach both service
passages, including the eastern passage beside the unchanged reinforcement
entries.

A real native move from (6,9) to (7,5) spent five MP. Ordinary move commands were
resumed when the engine paused along the route, using the remaining budget
without teleports or refills. An actual save/reload retained the destination,
zero remaining MP, all fourteen cover cells and all eight original cylinders.
The initial diagnostic fixture assumed four MP, then assumed a single command
would complete the route; both failed attempts are retained. Correcting those
fixture assumptions passed 77 main-phase and 73 reload checks without changing
the gameplay map.

Inventory, unit and all three map-generator checks, scope/whitespace, 107
declared contracts, 682 systems checks and all 30 campaign sequence stages
passed. All 30 sequence saves were parsed as readable, matching saved WML.
Systems logs retain 15 synthetic-controller warnings, with no engine errors;
their six main/load phases and existing replay tests passed. Campaign sequence
probes use scripted objectives and parsed saves, rather than human playtests
or native reloads of every sequence save. All 29 other maps and all 30 scenario
CFGs remain byte-identical to the base.

Six careful-player AI soaks passed the existing technical gate:

| Layout | Run | Recorded AI outcome | Turns played |
| --- | --- | --- | --- |
| Previous hall | 1 | result VICTORY turn 12 | 12 |
| Previous hall | 2 | result VICTORY turn 10 | 10 |
| Previous hall | 3 | result VICTORY turn 14 | 14 |
| Production bays | 1 | result VICTORY turn 8 | 8 |
| Production bays | 2 | result VICTORY turn 10 | 10 |
| Production bays | 3 | result DEFEAT turn 4 | 4 |

These are independent random runs, not paired seeds. The recorded outcomes
remain a rough automated balance signal, with no claim of improved win rate
or human difficulty. The verified player benefit is a readable industrial
layout with choices between a direct central advance and compartment assaults
using cover and contested flanks. Existing enemy numbers, target durability,
hero-defeat rules, gold and turn limits are unchanged.


## Nystao clan-house defense (2026-10-12)

Honoghr's Choice now has a timber clan house with four entrances, connected
village tracks across dark poisoned soil, broken earthworks and eight supply
crate cover hexes. The six original villages and all recruiting terrain remain.
Both landing zones can contest the entrances and village approaches. Leia is
still mission-critical; the east shuttle on turn4, Noghri allies on turn6, force
counts, recruitment, gold, turn limits and mission rules are unchanged.

All 456 remaining walkable hexes connect; the previous layout had 468.
Twelve impassable timber wall hexes define the clan house, with four entrances.
Installed Wesnoth 1.19.27 confirms Leia, Chewbacca, Khabarakh and the western
clone can reach every entrance, all six villages and both landing zones in
unopposed native path checks. Leia reaches either west/east door in two MP
and the north/south door in two/three MP; her routes to the landing-zone keeps
cost eleven/twelve MP. These paths describe access, not safety through enemies.

The timber floor and dirt retain one-MP movement for all four tested types.
Chewbacca and the clone have 40% floor defense and 60% crate defense;
Khabarakh has 50%/60%, while Leia has 50%/70%. These are actual native unit
defenses, not uniform terrain guarantees. Dry hills cost Khabarakh one MP and
the other three tested units two MP, with 60% defense for Leia/Khabarakh and
50% for Chewbacca/the clone. Crates grant no healing, income or recruitment;
the original six dukhas still provide village healing and income.

A normal native Chewbacca move from (13,10) through cover at (14,10) to the
south entrance (14,11) spent two MP, leaving three of five. A real save/reload
retained his destination and remaining moves, all four doors, eight covers,
twelve wall hexes, six villages and the original other hero positions.

The fresh-mission and actual reload phases passed 100 and 98 checks respectively, without engine errors or warnings.

Inventory, unit and all map-generator checks, scope/whitespace, 107 declared
contracts, 682 systems checks and all 30 campaign sequence stages passed.
All 30 sequence saves were parsed as readable matching saved WML. Systems
logs retain 15 warnings from the existing synthetic-controller fixtures, with no engine
errors; the main/load phases and existing replay tests passed. Sequence probes
use scripted objectives and parsed saves, rather than human playtests or actual
reloads of every sequence save. The other 29 maps and all 30 scenario CFGs
remain byte-identical to the base.

Six careful-player AI soaks passed the existing technical gate:

| Layout | Run | Recorded AI outcome | Turns played |
| --- | --- | --- | --- |
| Previous settlement | 1 | result VICTORY turn 3 | 3 |
| Previous settlement | 2 | result VICTORY turn 4 | 4 |
| Previous settlement | 3 | result VICTORY turn 3 | 3 |
| Clan-house defense | 1 | result VICTORY turn 4 | 4 |
| Clan-house defense | 2 | result DEFEAT turn 7 | 7 |
| Clan-house defense | 3 | result VICTORY turn 5 | 5 |

These are independent random runs, not paired seeds or a human win-rate
estimate. Terrain and route changes affect tactics; no claim is made that
human difficulty has improved. The player now chooses between holding the
house entrances, contesting the surrounding healing villages and covering the
eastern landing approach. The announced eastern shuttle, turn6 Noghri allies,
enemy numbers, recruitment, gold, turn limits and victory/defeat rules remain.


## Bilbringi docking piers and asteroid approaches (2026-10-12)

The Bilbringi Shipyards now has four two-row docking piers joined by a narrow
service spine. Six visible asteroid formations offer fighters slower cover
approaches, with open channels for capital ships. The central and outer routes
remain open, but the original cloaked mine screen still makes nearby space
hazardous. All four original platforms, seven starting mines, turn6 seed
coordinates, heroes, recruitment terrain, force counts, gold, turn limits and
mission events/rules remain unchanged. Victory still requires three platforms.

All 660 fighter-passable hexes connect, and all 610 capital-passable hexes
connect without crossing an asteroid. The layout has 50 visible asteroid
terrain hexes, compared with seven before, and 71 docking-deck hexes, compared
with 82 before. Four two-row piers replace the broad slab. Every original
platform has open attack approaches from either side of its west-facing edge;
all eleven original recruiting hexes retain their terrain and no villages,
healing or additional recruitment terrain were added.

Installed Wesnoth 1.19.27 confirms Wedge, Luke's X-wing, ordinary X-wings and
TIE fighters pay one MP in open space or on docks and two MP in asteroids.
Their actual native defenses are 50% in open space, 60% in asteroids and 40%
on docking decks. Death's Head pays one MP in space or on docks, cannot enter
asteroid terrain, and retains 10% defense. Native unopposed path checks for
all five types reach every platform approach and the full-length channels.
These paths describe access, not safety through enemies or the mine screen.

A normal native X-wing test unit moved from (7,6) to asteroid cover at (9,5),
spending four MP and retaining four of its normal eight. A real save/reload
retained that destination and spent movement, both original heroes, Death's
Head, all four platforms, all seven starting cloaked mines and all 50 visible
asteroid terrain cells. Test units were added only to the isolated fixture;
production scenario forces and recruitment remain unchanged.

Fresh-mission and actual reload phases passed 143 and 141 native checks, without engine errors or warnings.

Inventory, unit and all map-generator checks, scope/whitespace, 107 declared
contracts, 682 systems checks and all 30 campaign sequence stages passed.
All 30 sequence saves were parsed as readable matching saved WML. Systems
logs retain 15 warnings from the existing synthetic-controller fixtures,
with no engine errors; existing replay tests passed. Sequence probes use
scripted objectives and parsed saves rather than human playtests or actual
reloads of every sequence save. Other 29 maps and all 30 scenario CFGs remain
byte-identical to the base.

Six careful-player AI soaks passed the existing technical gate:

| Layout | Run | Recorded AI outcome | Turns played |
| --- | --- | --- | --- |
| Previous dock slab | 1 | result VICTORY turn 12 | 12 |
| Previous dock slab | 2 | result DEFEAT turn 8 | 8 |
| Previous dock slab | 3 | result VICTORY turn 14 | 14 |
| Piers and asteroid approaches | 1 | result VICTORY turn 16 | 16 |
| Piers and asteroid approaches | 2 | result VICTORY turn 14 | 14 |
| Piers and asteroid approaches | 3 | result VICTORY turn 13 | 13 |

These are independent random runs, not paired seeds or a human win-rate
estimate. All wins and losses are reported; no claim is made that human
difficulty has improved. Players now choose between faster open routes,
slower fighter cover and dock approaches with less fighter defense. The
existing cloaked hazards, platform blast events, turn6 seeds, enemy forces,
gold, turn limits, bonus objective and three-platform victory rule remain.


## Nomad City mining bays and intercept routes (2026-10-12)

Nomad City's formerly open platform now has internal bay walls, four service
doors, an open central aisle and 12 crate cover cells. Players can hold the
five miner sheds from bay positions, keep reserves centrally or intercept
stolen miners near the gates. All original gates and their interior landing
cells, recruitment terrain, shed terrain and exterior heat/shade tiles remain.
The entire scenario CFG and all other mission maps/CFGs remain unchanged,
including Claude's objectives, balance, events, air support and rewards.

The 28x18 playable map changes 21 interior cells: nine new wall hexes and 12
crate cover hexes. The city now has 37 walls, compared with 28 before. Four bay
doors and the open central aisle retain access to all four original gates;
their interior landing cells remain open. All 467 infantry/miner-passable and
450 scout-passable hexes connect (previously 476 and 459). All five healing
miner sheds and eleven recruiting hexes retain their exact terrain. All 268
exposed desert/dune heat hexes, all exterior shade, starts and extraction
terrain remain byte-identical. No healing, village or recruiting terrain is
added by the crates.

Installed Wesnoth 1.19.27 confirms Han, Lando and ordinary New Republic
infantry have 40% defense on the deck and 60% behind crates, with one MP paid
for either terrain. Imperial scouts and mole miners have 40% on both; cover
does not benefit every unit equally. City walls block all five tested types.
Scouts cannot cross the original mountains; the mole miner uses its existing
starfighter movetype and pays two MP there. Native unopposed route checks
reach all sheds, gates, gate landings, bay doors and the western exit.
Actual-type isolated miner probes reached extraction from each of the five
sheds for 18,18,20,24,24 MP respectively. These are access checks rather than
claims that a route is safe through hostile units or heat.

Han made an ordinary native move from (22,10) through (21,10) and(20,10) to
crate cover at (20,11), spending three of his normal six MP around a bay wall.
The fixture's initial two-MP estimate was corrected to the measured native
route. A real save/reload retained his destination and spent movement,
original Lando/Harbid/scouts, all five sheds, twelve covers and 37 walls.
Temporary test miners/trooper existed only in the isolated fixture;
production forces and recruitment remain unchanged.

Fresh-mission and actual reload phases passed 153 and 146 native checks, without engine errors or warnings.

Inventory, unit and all map-generator checks, scope/whitespace, 107 declared
contracts, 682 systems checks and all 30 campaign sequence stages passed.
All 30 sequence saves were parsed as readable matching saved WML. Systems
logs retain 14 warnings from existing synthetic-controller fixtures,
with no engine errors. Sequence probes use scripted objectives and parsed
saves, not human playtests or actual reloads of every sequence save. Other 29
maps and all 30 scenario CFGs remain byte-identical to the base.

Six careful-player AI soaks passed the existing technical gate:

| Layout | Run | Recorded AI outcome | Turns played |
| --- | --- | --- | --- |
| Previous open platform | 1 | result VICTORY turn 15 | 15 |
| Previous open platform | 2 | result VICTORY turn 14 | 14 |
| Previous open platform | 3 | result VICTORY turn 13 | 13 |
| Mining bays and cover | 1 | result VICTORY turn 12 | 12 |
| Mining bays and cover | 2 | result VICTORY turn 14 | 14 |
| Mining bays and cover | 3 | result VICTORY turn 15 | 15 |

These are independent random runs, not paired seeds or a human win-rate
estimate. All wins and losses are reported; no claim is made that human
difficulty has improved. Bay defense, central reserves and gate interception
now provide distinct choices. Original heat damage, miner theft thresholds,
enemy forces/AI, air support, turns/gold, victory/loss rules, bonus objectives,
achievements, mission tips and rewards remain unchanged.


## Peregrine's Nest canyon and layered base defense (2026-10-12)

The scattered hills now form a central canyon, with longer northern and southern
trails approaching the original side gates. Hewn base rooms and a durasteel
generator deck create fallback positions; 12 cargo cells provide unit-dependent
cover. The original six healing depots, 12 castle/keep cells and all scripted
unit tiles retain their exact terrain tokens. All scenario CFGs and other maps
remain byte-identical, including Claude's mission events and balance.

All 504 infantry-passable cells connect. All 454 scout/walker-passable cells
also connect without crossing an ordinary mountain. The layout replaces eight
metal wall cells with 13 hewn wall cells and adds 43 sheer mountain cells.
Its 12 crate cells provide cover without healing or recruitment. All six
original healing depots and twelve keep/castle tiles retain their exact
terrain tokens, as do all nine scripted unit locations. All three original
gates, their inner and outer landings, the two room doors, the hill depot
access and both outer trails remain passable. The southwest outer landing
(17,13) remains its original dry hills, with the native unit-specific cost.

Installed Wesnoth 1.19.27 confirms hewn floors, durasteel, roads and crate
cells cost one MP for Han, Lando, Bel Iblis, commandos, clone troopers, the
original AT-ST and an isolated actual-type scout. Hewn walls and the installed
Mm^Xm sheer mountain terrain cost at least 99 MP for all seven types.
All seven native types reach every depot, gate, adjacent landing, room door,
outer trail waypoint, keep and generator on unopposed path checks. These
paths establish access rather than safety through enemy zones of control.

Actual native defense is unit-dependent:

| Unit type | Hewn floor | Crate cover | Durasteel |
| --- | --- | --- | --- |
| sw_hero_han | 40% | 60% | 40% |
| sw_hero_lando | 40% | 60% | 40% |
| sw_hero_bel_iblis | 40% | 60% | 40% |
| sw_unit_bi_commando | 40% | 60% | 40% |
| sw_unit_im_clone_trooper | 40% | 60% | 40% |
| sw_unit_im_at_st | 30% | 40% | 30% |
| sw_unit_im_scout_trooper | 40% | 40% | 40% |

A normal native Bel Iblis move from (24,10) to crate cover at (24,13) spent
three MP of his normal five. An actual save/reload retained the destination
and remaining two MP, all original heroes, both commandos, Tierce, the
AT-ST and clone, all six depots, 43 sheer cliffs, 13 hewn walls and 12 crates.
The scout probe existed only in isolated test userdata; the production
scenario's original forces and recruitment remain unchanged.

Fresh mission and actual reload phases passed 236 and 234 native checks, with no engine errors or warnings.

Inventory, unit and all map-generator checks, scope/whitespace, 107 declared
contracts, 682 systems checks and all 30 campaign sequence stages passed.
All 30 sequence saves were parsed as readable matching saved WML. Systems
logs retain 15 existing synthetic-controller warnings, with no engine
errors; existing replay tests passed. Sequence probes use scripted objectives
and parsed saves, rather than human playtests or actual reloads of every
sequence save. Only generator m05 changed; the other 29 maps and all 30
scenario CFGs remain byte-identical to the base.

Six careful-player AI soaks passed the existing technical gate:

| Layout | Run | Recorded AI outcome | Turns played |
| --- | --- | --- | --- |
| Scattered hills and open base | 1 | result VICTORY turn 12 | 12 |
| Scattered hills and open base | 2 | result DEFEAT turn 13 | 13 |
| Scattered hills and open base | 3 | result VICTORY turn 11 | 11 |
| Canyon and layered base | 1 | result DEFEAT turn 11 | 11 |
| Canyon and layered base | 2 | result VICTORY turn 15 | 15 |
| Canyon and layered base | 3 | result DEFEAT turn 7 | 7 |

These are independent random runs, not paired seeds or a human win-rate
estimate. All recorded wins and losses are reported, with no claim about
human difficulty. Players now choose between holding the central canyon,
covering two flanks and keeping reserves near the generator. Han's critical
death, Lando/Bel Iblis withdrawal, Imperial generator-entry defeat, Tierce
alternative victory, survival turns, gold, income, air support and optional
objective remain exactly as Claude authored them.


## Myneyrshi Field Medic forest support (2026-10-12)

The Wayland native roster gains one optional healer in The Gates of Tantiss.
Its 20-gold cost, 28 HP, 6 movement, 48 XP and weak 4x2 spear/bow trade combat
power for keeping up with forest troops. Existing sw_wookiee forest cost1
contrasts with the Republic Field Medic's cost2 and five movement. Both pay2
on hills; fire vulnerability110% remains. Base adjacent healing4 slows poison
without curing or self-healing, and does not add together with other healers.
RankI forest ghost, II field surgery (healing8 replaces4), III rapid evacuation
(skirmisher). No new attacks. The Republic medic reaches healing8 at rankI;
its earlier treatment and lower cost remain useful alongside the mobile option.

Only two existing TLC06 player recruit declarations gain this ID. Every prior
unit and rank assignment, other scenario byte, map, event, reinforcement,
objective, difficulty, gold, turn limit and reward remains unchanged. Fourteen
original Myneyrshi animation frames and portrait are reused byte-for-byte;
the shared silhouette is a presentation limitation, with role identified by
the unit name, native healing ability and Field Manual.

Native Wesnoth 1.19.27 checks confirm paid recruitment spends 20 gold and
all native recruit actions. An ordinary forest move spends one MP without
refilling movement; the Republic medic pays two on the same terrain. Real
side transitions show healing waits for the healer's own turn. Two healing4
sources give four HP rather than eight. Poison damage is stopped without
curing or restoring HP; the healer itself, distant allies and enemies are
excluded. Rank II gives eight rather than twelve HP on the next native turn.

Native AMLAs grant forest concealment, one healing8 ability replacing4, and
skirmisher without adding attacks. A further AMLA/update retains one object
per earned rank. Actual save/reload retains the type and all three abilities,
and the loaded medic heals an adjacent wounded ally for8 on its next turn.
A separate actual Gates of Tantiss launch buys the optional unit from Han's
original keep, then an actual reload retains its position, spent actions and
paid gold. All nine original mission units retain their positions.

Inventory, unit and all map generators, whitespace, official static contracts,
711 systems checks and all 30 campaign sequence stages passed.
All 30 sequence saves were parsed as matching readable saved WML. Systems
logs retain 15 synthetic-controller warnings with no engine
errors. Existing replay checks passed. Scripted sequences and parsed saves
do not establish human difficulty or reload every campaign-sequence save.

Six independent careful-player AI soaks of Gates of Tantiss passed the
existing technical gate:

| Roster | Run | Recorded AI outcome | Turns played |
| --- | --- | --- | --- |
| Previous roster | 1 | result DEFEAT turn 14 | 14 |
| Previous roster | 2 | result DEFEAT turn 9 | 9 |
| Previous roster | 3 | result VICTORY turn 15 | 15 |
| Optional forest medic | 1 | result DEFEAT turn 9 | 9 |
| Optional forest medic | 2 | result DEFEAT turn 6 | 6 |
| Optional forest medic | 3 | result DEFEAT turn 12 | 12 |

These are independent random runs, not paired seeds or a human win-rate
estimate. Recruited types are not established by the soak report, so no
outcome is attributed to the medic. All wins and losses are reported. Native
functional checks establish the new choice; no enemy forces, objective,
turn, gold, reward or Claude-owned mission event was adjusted.


## Bpfassh colony passages and evacuation cover (2026-10-12)

Three formerly solid colony buildings have through-passages with cargo cover,
linked by six street cover positions. They offer staging positions for screening
Leia through the southern district, militia plaza and east district toward the
Falcon, alongside every original exposed route. Ten walls open as floors and
six street cells gain crates: exactly16 altered playable hexes and9 cover cells.
All original villages, recruitment terrain, canal bridges, ambush parks, scripted
positions and scenario CFG bytes remain. Claude's events, forces, difficulty,
objectives, rewards, achievements and tips are preserved. Native unit-specific
cover and route costs will be reported; geometry alone does not prove safer
play or a win-rate improvement.

The 26x18 playable map changes exactly 16 interior cells: ten previously
impassable wall cells become colony floor, including three crate positions,
and six road cells gain crates. There are now 83 colony wall cells and nine
cargo cover hexes. All nine existing village positions, original streets,
keeps and recruiting hexes, both canal bridges, three ambush parks, militia
plaza, opening party and Falcon extraction hex retain their exact terrain
or placement. No healing, village or recruiting terrain is added by crates.

Installed Wesnoth 1.19.27 measured the following unit-specific defence
(chance to avoid an attack), with one MP paid for road, colony floor or crate
terrain by all ten tested unit types:

| Tested unit type | Road / colony floor | Cargo crates |
| --- | --- | --- |
| Leia | 50% | 70% |
| Han, Chewbacca, New Republic trooper, commando, medic and E-web team | 40% | 60% |
| Imperial officer | 40% | 60% |
| Noghri warrior | 50% | 60% |
| Imperial repulsor scout | 40% | 40% |

Walls remain impassable to those types. Unopposed native path checks reach
all new floors, the plaza, lower canal bridge and Falcon. Leia's unopposed
route to the Falcon costs 29 MP. These checks ignore units and their zones
of control; they do not establish a safe escape through enemies. Four
additional actual-type probes (commando, medic, E-web and scout) were private
unplaced unit objects, with no extra mapped or recalled units.

Han made an ordinary native move from (3,16) through (4,15) to covered
colony floor at (4,14), spending two of his normal six MP. A real save/reload
kept his destination and four remaining MP, the layout, original party,
militia and Noghri. Main and reload phases passed 213 and 210 checks
(423 total), with no engine errors or warnings. Normal still starts with
120 gold and 14 turns. Existing saves retain their stored map; a fresh
Bpfassh mission uses the new passages.

Inventory, unit and all map-generator checks, scope/whitespace, 109 declared
contracts, 711 systems checks and all 30 campaign sequence stages passed.
All 30 sequence saves were parsed as readable matching saved WML. Systems
logs retain 15 synthetic-controller warnings, with no engine
errors; existing replay checks passed. Scripted sequences and parsed saves
do not establish human difficulty or reload every sequence save. All 30
scenario CFGs, other 29 maps and all other HTE map builders retain base bytes.

Six independent careful-player AI soaks of Ambush at Bpfassh passed the
existing technical gate:

| Layout | Run | Recorded AI outcome | Turns played |
| --- | --- | --- | --- |
| Previous solid buildings | 1 | result DEFEAT turn 15 | 15 |
| Previous solid buildings | 2 | result DEFEAT turn 15 | 15 |
| Previous solid buildings | 3 | result DEFEAT turn 15 | 15 |
| Covered building passages | 1 | result DEFEAT turn 15 | 15 |
| Covered building passages | 2 | result DEFEAT turn 15 | 15 |
| Covered building passages | 3 | result DEFEAT turn 15 | 15 |

These are independent random runs, not paired seeds or a human win-rate
estimate. All wins and losses are reported. The new passage and cover
positions provide choices for escort screening and regrouping; no claim is
made that human difficulty improved. Enemy forces, AI, gold/turns,
victory/loss conditions, objectives, rewards, achievements, tips and
Claude-owned mission event behavior retain their base bytes.

Raw careful-player soak logs also retain repeated enemy_of formula type
diagnostics (expected object but found null) on both the unchanged baseline
and the candidate, plus the synthetic controller-change warning and occasional
fake air-sortie route warnings. The existing technical validator reports PASS
for these runs; no matcher, error exemption, deadline or verdict was changed
for this ticket. PASS therefore does not establish error-free AI play. The
formula counts below count both printed TYPE ERROR/formula messages, rather
than unique error sites; they must not be treated as a human balance result.

| Layout | Run | Formula diagnostic lines | Synthetic controller lines | Fake air-route warnings |
| --- | --- | --- | --- | --- |
| Previous solid buildings | 1 | 542 | 1 | 3 |
| Previous solid buildings | 2 | 318 | 1 | 3 |
| Previous solid buildings | 3 | 294 | 1 | 1 |
| Covered building passages | 1 | 330 | 1 | 2 |
| Covered building passages | 2 | 520 | 1 | 1 |
| Covered building passages | 3 | 268 | 1 | 0 |


### Safe base backstab combat evaluation (2026-10-12)

Noghri commandos, Khabarakh (all three visual ranks) and Imperial infiltrators now use a guarded base knife special. Only the native backstab opponent filter changes: no opponent or empty opposite hex safely fails, instead of passing a null object to enemy_of. Core special identity, labels, double damage and offense-only activation remain. All mission CFGs/maps and Claude’s rank assignments and rank-special guards retain their bytes.

Current-main native diagnosis on Wesnoth 1.19.27 reproduced three null-object events (six TYPE ERROR/formula diagnostic lines) for three solo knife previews. The guarded private-unit control had zero diagnostics: Noghri and Khabarakh stayed at 9 damage alone and 18 with a valid opposite hostile unit; infiltrator stayed at 7 and 14. Petrified support gave ordinary damage. This confirms the isolated evaluation repair; final full systems, native combat/reload, campaign sequence and AI results follow. It does not establish improved AI win rates or human difficulty. Existing units cached in older saves may retain their serialized old special.

The initial full systems run is preserved as FAIL: the unarmed-flanker fixture attempted to assign Lua unit.attacks, a read-only property. The fixture now uses the supported native remove_attacks object effect and independently asserts an empty attack list before the damage/accuracy check. No shipped damage formula, native special or combat expectation was relaxed. The fresh required run below verifies the fixture repair.


The first systems run retained one failing unarmed fixture; the repaired full run uses the supported native remove_attacks effect and a direct zero-attack check. The original failure and raw logs are retained.

Measured final validation on installed Wesnoth 1.19.27:

- Existing unit/all-map/inventory/scope/whitespace gates passed; 110 declared contracts retain all 109 previous declarations.
- The full systems suite passed 991 assertions, with no failures or engine errors and 15 retained synthetic-controller warnings. Both existing replay comparisons passed. New native regressions cover all six directions in five shipped profiles (the three base families and Khabarakh rank2/rank3), absent opponent, empty/opposite hostile/target ally/petrified/unarmed/off-axis support, and return fire. The separate accuracy-flanking special and Claudeâ€™s original rank cases remain intact.
- Native actual combat and real reload passed 38 checks (22 main + 16 reload), without diagnostics. The Noghri solo attack dealt ordinary knife damage; Khabarakh and the infiltrator dealt doubled knife damage with valid support. Every actual attack spent movement and its attack, and the save/reload retained positions, HP, spent actions, the shipped guarded special and the same native preview. Test-only 100% hit chance and high-HP targets ensured all planned strikes could be checked; original weapon specials were restored before saving. No combat snapshot was reconstructed, no victory was preset, and this isolated fixture does not establish mission difficulty.
- All three scripted campaign sequences passed 30 stages and 30 parsed matching WML saves. These do not reload each sequence save or constitute human playtests.

All 30 careful-player AI soaks passed the existing technical gate. Every raw log was also scanned separately without modifying the matcher, exemption, timeout or verdict; all 30 had zero TYPE ERROR/formula diagnostic lines. Other raw diagnostics and every outcome remain recorded:

| Mission | Recorded AI outcome | Turns | Formula diagnostic lines | Other raw diagnostic lines |
| --- | --- | --- | --- | --- |
| sw_hte_01_ysalamiri_harvest | result DEFEAT turn 17 | 17 | 0 | 1 |
| sw_hte_02_ambush_at_bpfassh | result DEFEAT turn 15 | 15 | 0 | 4 |
| sw_hte_03_adrift | result DEFEAT turn 7 | 7 | 0 | 1 |
| sw_hte_04_shadows_of_kashyyyk | result VICTORY turn 13 | 13 | 0 | 1 |
| sw_hte_05_prisoner_of_myrkr | result DEFEAT turn 15 | 15 | 0 | 1 |
| sw_hte_06_raid_on_karrdes_base | result DEFEAT turn 16 | 16 | 0 | 5 |
| sw_hte_07_the_forest_crossing | result DEFEAT turn 7 | 7 | 0 | 1 |
| sw_hte_08_nomad_city | result VICTORY turn 15 | 15 | 0 | 6 |
| sw_hte_09_sluis_van_shipyards | result VICTORY turn 13 | 13 | 0 | 1 |
| sw_hte_10_thrawns_gambit | result DEFEAT turn 7 | 7 | 0 | 1 |
| sw_dfr_01_the_noghri_prisoner | result DEFEAT turn 3 | 3 | 0 | 1 |
| sw_dfr_02_honoghr | result DEFEAT turn 4 | 4 | 0 | 1 |
| sw_dfr_03_jomark | result DEFEAT turn 4 | 4 | 0 | 1 |
| sw_dfr_04_the_senators_men | result DEFEAT turn 9 | 9 | 0 | 5 |
| sw_dfr_05_peregrines_nest | result DEFEAT turn 9 | 9 | 0 | 15 |
| sw_dfr_06_the_mad_jedi | result DEFEAT turn 8 | 8 | 0 | 1 |
| sw_dfr_07_the_dark_force | result DEFEAT turn 17 | 17 | 0 | 24 |
| sw_dfr_08_aboard_the_katana | result DEFEAT turn 17 | 17 | 0 | 1 |
| sw_dfr_09_battle_for_the_fleet | result DEFEAT turn 17 | 17 | 0 | 1 |
| sw_dfr_10_honoghrs_choice | result VICTORY turn 4 | 4 | 0 | 1 |
| sw_tlc_01_the_siege_of_coruscant | result VICTORY turn 8 | 8 | 0 | 1 |
| sw_tlc_02_the_smugglers_council | result DEFEAT turn 5 | 5 | 0 | 1 |
| sw_tlc_03_the_palace_infiltrators | result VICTORY turn 8 | 8 | 0 | 1 |
| sw_tlc_04_landfall_on_wayland | result DEFEAT turn 5 | 5 | 0 | 1 |
| sw_tlc_05_the_natives_of_wayland | result VICTORY turn 5 | 5 | 0 | 1 |
| sw_tlc_06_the_gates_of_tantiss | result DEFEAT turn 11 | 11 | 0 | 2 |
| sw_tlc_07_the_cloning_vats | result VICTORY turn 8 | 8 | 0 | 1 |
| sw_tlc_08_the_throne_room | result DEFEAT turn 8 | 8 | 0 | 1 |
| sw_tlc_09_bilbringi | result DEFEAT turn 9 | 9 | 0 | 3 |
| sw_tlc_10_the_last_command | result DEFEAT turn 4 | 4 | 0 | 1 |

These independent random runs recorded 8 victories and 22 defeats. They are not paired with earlier runs and do not establish a human win rate or better difficulty. The defeat count remains a playability concern for human mission playtests; this unpaired sample cannot attribute it to the repair. Raw controller-change and fake air-route warnings are preserved. The current source repair eliminates the confirmed null-object knife evaluation, while base unit numbers and all mission WML remain byte-identical. Older cached units can retain the old serialized special until rebuilt; no save migration is claimed.

The first unchanged static gate failed because the shared-specials CFG lacked a declaration. One declaration for its existing flanking identity, within the original immutable ticketâ€™s generated contract-shard scope, restores coverage while preserving all prior declarations. This source-coverage check is not native behavior proof; the actual combat, six-direction cases and AI logs provide that evidence.


## Target-centered bombing jamming (2026-10-12)

Bombing preview, AI selection and delayed resolution now measure ECM from the selected strike hex. The seven-cell footprint keeps its deterministic order, while anti-air still protects any struck cell. Strafing uses its selected first hex as before. Damage, strikes, charge counts, warning delay, jamming/ECCM multipliers, anti-air caps and all mission/unit/rank settings are unchanged.

The current-main native baseline on Wesnoth 1.19.27 measured zero jamming from a target-only jammer and 20 from a jammer covering only sorted edge(7,8), with the strafe control 20. The repair carries transient target metadata and rebuilds it from existing saved strike.x/y, without adding serialized state. New native cases cover target versus edge, odd/even coordinates, order permutations, ECM range and ECCM, area-wide anti-air, ordinary AI selection and an actual queued-strike reload. Measured gates and all AI outcomes follow; no human balance claim is made.


The first full systems run preserved one false fixture precondition (plus its aggregate main-phase FAIL): native flat defense40 gave expected damage9.0/12.6, not the assumed below8/above8. The actual AI target choice and spent-budget checks passed. The corrected fixture uses equal forest cover, directly checks native defense50 and restores both original terrains, preserving the existing AI threshold and every shipped statistic.

Measured validation on installed Wesnoth 1.19.27:

- Existing generators, unit-art uniqueness, inventory, scope and whitespace checks passed. Claude409 art and unit definitions are retained. The full systems suite passed 1057 assertions, with no failures or engine errors and 17 retained synthetic-controller warnings; both replay comparisons passed.
- New air cases verify four odd/even target positions, area reordering, target-only and edge-only ECM, range boundaries, friendly jamming, ECCM and blast-edge AA. An ordinary native AI turn chooses the exposed target and spends its sortie and observer attack. The existing native air save/reload retains the pending target, then lands the strike on ordinary caller turns with independently calculated jamming and hit chance.
- A separate unmodified-old-code native save creates an actual queued strike; the candidate reloads those exact bytes. All 10 reload checks passed without diagnostics, preserving selected x/y, spent actions, HP and turn, and resolving at target-centered ECM on the next ordinary caller turn. No saved schema migration, manually inserted queue or preset landing turn is used.
- The three scripted campaign sequences passed 30 stages and 30 parsed matching WML saves. Those sequence checks do not reload each save or represent human playtests.

All 30 careful-player AI soaks passed the existing technical gate. Every raw log was also scanned without changing its matcher, exemption, timeout or verdict:

| Mission | Recorded AI outcome | Turns | Formula diagnostic lines | Other raw diagnostic lines |
| --- | --- | --- | --- | --- |
| sw_hte_01_ysalamiri_harvest | result DEFEAT turn 17 | 17 | 0 | 1 |
| sw_hte_02_ambush_at_bpfassh | result DEFEAT turn 15 | 15 | 0 | 3 |
| sw_hte_03_adrift | result DEFEAT turn 8 | 8 | 0 | 1 |
| sw_hte_04_shadows_of_kashyyyk | result VICTORY turn 11 | 11 | 0 | 2 |
| sw_hte_05_prisoner_of_myrkr | result DEFEAT turn 15 | 15 | 0 | 1 |
| sw_hte_06_raid_on_karrdes_base | result DEFEAT turn 4 | 4 | 0 | 1 |
| sw_hte_07_the_forest_crossing | result DEFEAT turn 5 | 5 | 0 | 1 |
| sw_hte_08_nomad_city | result VICTORY turn 13 | 13 | 0 | 7 |
| sw_hte_09_sluis_van_shipyards | result VICTORY turn 7 | 7 | 0 | 1 |
| sw_hte_10_thrawns_gambit | result DEFEAT turn 11 | 11 | 0 | 1 |
| sw_dfr_01_the_noghri_prisoner | result VICTORY turn 4 | 4 | 0 | 2 |
| sw_dfr_02_honoghr | result VICTORY turn 5 | 5 | 0 | 1 |
| sw_dfr_03_jomark | result DEFEAT turn 5 | 5 | 0 | 1 |
| sw_dfr_04_the_senators_men | result DEFEAT turn 15 | 15 | 0 | 5 |
| sw_dfr_05_peregrines_nest | result DEFEAT turn 12 | 12 | 0 | 7 |
| sw_dfr_06_the_mad_jedi | result DEFEAT turn 5 | 5 | 0 | 1 |
| sw_dfr_07_the_dark_force | result DEFEAT turn 5 | 5 | 0 | 13 |
| sw_dfr_08_aboard_the_katana | result DEFEAT turn 2 | 2 | 0 | 1 |
| sw_dfr_09_battle_for_the_fleet | result DEFEAT turn 17 | 17 | 0 | 1 |
| sw_dfr_10_honoghrs_choice | result DEFEAT turn 4 | 4 | 0 | 1 |
| sw_tlc_01_the_siege_of_coruscant | result VICTORY turn 9 | 9 | 0 | 1 |
| sw_tlc_02_the_smugglers_council | result DEFEAT turn 4 | 4 | 0 | 1 |
| sw_tlc_03_the_palace_infiltrators | result VICTORY turn 8 | 8 | 0 | 1 |
| sw_tlc_04_landfall_on_wayland | result DEFEAT turn 4 | 4 | 0 | 1 |
| sw_tlc_05_the_natives_of_wayland | result VICTORY turn 7 | 7 | 0 | 1 |
| sw_tlc_06_the_gates_of_tantiss | result DEFEAT turn 7 | 7 | 0 | 1 |
| sw_tlc_07_the_cloning_vats | result DEFEAT turn 10 | 10 | 0 | 1 |
| sw_tlc_08_the_throne_room | result DEFEAT turn 4 | 4 | 0 | 1 |
| sw_tlc_09_bilbringi | result VICTORY turn 11 | 11 | 0 | 1 |
| sw_tlc_10_the_last_command | result DEFEAT turn 4 | 4 | 0 | 1 |

These independent random runs recorded 9 victories and 21 defeats. They are unpaired and do not establish a human win rate or a change in difficulty. Defeats and all raw warnings remain recorded; mission difficulty still warrants human playtests. All 30 scenario CFGs/maps and unit/rank data retain their base bytes. The fixture changes only test setup, and ECM/ECCM and other numeric rules remain unchanged.


## 3.26 - Ranged AI approaches around visible overwatch (2026-10-12)

Enemy ranged troops now reject a firing position if the ordinary native path to it crosses a visible active hostile overwatch lane. Reaction fire interrupts the move even on a miss, so the planner does not credit a shot from an endpoint it would fail to reach. It can choose a safe worthwhile alternative or fire from its current position. If no such ranged shot exists, the ordinary AI remains available; this change does not make every enemy move avoid reactions.

Only publicly visible hostile watchers count, with reactions remaining, current range and arc, disabled states and the per-move duplicate guard. The check is deliberately cautious about a visible lane: it does not inspect the opponent's fog, hidden sensors or contact picture to decide whether a concealed mover would be seen. Native visibility, cloak, powers and hooks still resolve actual reactions. All combat numbers, native terrain and zones of control, mission forces/objectives/difficulty and saved formats remain intact.

Current-main native baseline (Wesnoth 1.19.27): an ordinary 36-HP, five-MP stormtrooper at (6,8) selected a four-MP firing position at (10,7) against a smuggler at (12,8). Arming the visible E-Web at (5,6), range three, did not change that choice or its 14.5 rating. Its path entered the firing lane at (7,8), while (10,8) was a safe four-MP alternative. This is an isolated tactical fixture, not a mission difficulty result.

Measured validation on installed Wesnoth 1.19.27 with Claude's wall-art update retained:

- Generators, unit-art uniqueness, inventory, scope and whitespace passed. The unchanged full systems/replay suite passed 1269 checks with no failed assertions or engine errors and 19 warnings classified by the unchanged runner. All raw native diagnostics, including fixture animation/event warnings, are retained separately. Six native main/reload phases completed within their original deadlines.
- Public-path cases cover active/inactive/spent/hidden/allied/disabled watchers, duplicate movement serials, range, all six front facings and both column parities. Every entered hex is checked against native reaction eligibility; the source is excluded and stationary fire remains available. When all moving shots are covered, this candidate returns no shot and leaves ordinary AI available.
- The ordinary native AI turn follows its complete native planned path, spends four MP, reaches (10,8), and attacks with the shipped rifle without drawing the visible E-Web's volley. Arrival and attack events separately record movement and reactions. The real saved game retains watcher state, units and actions, and reproduces the same safe firing choice after loading.
- The initial focused run retained three failed fixture assertions and its aggregate main-phase failure. The fixture had assumed one E-Web reaction instead of the native ability's two and measured movement at the attack event after combat had spent it. The repair snapshots native reactions and records moveto arrival before attack; the same behavior checks pass without changing the planner or a gate.
- All three scripted campaign sequences passed 30 stages and 30 matching parsed saves. They do not reload each sequence save and do not represent human playtests.

All 30 careful-player AI soaks passed the existing technical gate. All raw logs were scanned without changing the matcher, exceptions, timeout or verdict:

| Mission | Recorded AI outcome | Turns | Formula diagnostic lines | Other raw diagnostic lines |
| --- | --- | --- | --- | --- |
| sw_hte_01_ysalamiri_harvest | result DEFEAT turn 17 | 17 | 0 | 1 |
| sw_hte_02_ambush_at_bpfassh | result DEFEAT turn 15 | 15 | 0 | 2 |
| sw_hte_03_adrift | result DEFEAT turn 8 | 8 | 0 | 1 |
| sw_hte_04_shadows_of_kashyyyk | result VICTORY turn 15 | 15 | 0 | 1 |
| sw_hte_05_prisoner_of_myrkr | result DEFEAT turn 15 | 15 | 0 | 1 |
| sw_hte_06_raid_on_karrdes_base | result DEFEAT turn 16 | 16 | 0 | 3 |
| sw_hte_07_the_forest_crossing | result DEFEAT turn 4 | 4 | 0 | 1 |
| sw_hte_08_nomad_city | result VICTORY turn 15 | 15 | 0 | 9 |
| sw_hte_09_sluis_van_shipyards | result VICTORY turn 7 | 7 | 0 | 1 |
| sw_hte_10_thrawns_gambit | result DEFEAT turn 11 | 11 | 0 | 1 |
| sw_dfr_01_the_noghri_prisoner | result DEFEAT turn 4 | 4 | 0 | 1 |
| sw_dfr_02_honoghr | result DEFEAT turn 4 | 4 | 0 | 1 |
| sw_dfr_03_jomark | result DEFEAT turn 4 | 4 | 0 | 1 |
| sw_dfr_04_the_senators_men | result DEFEAT turn 6 | 6 | 0 | 5 |
| sw_dfr_05_peregrines_nest | result VICTORY turn 16 | 16 | 0 | 10 |
| sw_dfr_06_the_mad_jedi | result DEFEAT turn 6 | 6 | 0 | 1 |
| sw_dfr_07_the_dark_force | result DEFEAT turn 17 | 17 | 0 | 14 |
| sw_dfr_08_aboard_the_katana | result DEFEAT turn 17 | 17 | 0 | 1 |
| sw_dfr_09_battle_for_the_fleet | result DEFEAT turn 16 | 16 | 0 | 1 |
| sw_dfr_10_honoghrs_choice | result VICTORY turn 3 | 3 | 0 | 1 |
| sw_tlc_01_the_siege_of_coruscant | result VICTORY turn 8 | 8 | 0 | 1 |
| sw_tlc_02_the_smugglers_council | result DEFEAT turn 4 | 4 | 0 | 1 |
| sw_tlc_03_the_palace_infiltrators | result VICTORY turn 9 | 9 | 0 | 1 |
| sw_tlc_04_landfall_on_wayland | result DEFEAT turn 7 | 7 | 0 | 1 |
| sw_tlc_05_the_natives_of_wayland | result DEFEAT turn 5 | 5 | 0 | 1 |
| sw_tlc_06_the_gates_of_tantiss | result DEFEAT turn 11 | 11 | 0 | 3 |
| sw_tlc_07_the_cloning_vats | result VICTORY turn 12 | 12 | 0 | 1 |
| sw_tlc_08_the_throne_room | result DEFEAT turn 6 | 6 | 0 | 1 |
| sw_tlc_09_bilbringi | result VICTORY turn 10 | 10 | 0 | 2 |
| sw_tlc_10_the_last_command | result DEFEAT turn 6 | 6 | 0 | 1 |

These independent random runs recorded 9 victories and 21 defeats. They are unpaired and do not establish a human win rate or a difficulty change. All defeats and raw warnings are retained. Mission scenarios/maps, unit statistics, rank abilities and overwatch resolution retain their integrated-base bytes.

Source coverage records a literal; native execution supplies behavioral evidence.
