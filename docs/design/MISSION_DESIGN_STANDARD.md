# Mission Design Standard

**Status:** canonical. Every new scenario, and every change to an existing
one, is designed and reviewed against this document.

**Source:** the owner's brief, `MISSION_DESIGN_STANDARD.mc` (repository root,
2026-10-16). This document turns that brief into a working specification for
this add-on: its engine (Wesnoth 1.19.27), its systems (hero withdrawal,
stealth, overwatch, air support, Force powers, space evasion) and its three
campaigns. Where the two differ, the owner's brief states the intent and this
document states how it is applied here.

**Companions:**

| Document | Role |
|---|---|
| [SCENARIO_AUDIT.md](SCENARIO_AUDIT.md) | Every mission scored against this standard, with evidence |
| [CAMPAIGN_DESIGN_REVIEW.md](CAMPAIGN_DESIGN_REVIEW.md) | Variety, difficulty curve, economy and pacing per campaign |
| [MISSION_IMPROVEMENT_LOG.md](MISSION_IMPROVEMENT_LOG.md) | Every design change: reason, test, result, open risk |
| [../balance/MISSION_BALANCE_REVIEW.md](../balance/MISSION_BALANCE_REVIEW.md) | Numeric balance history and AI-soak results |
| `production/campaigns/*/DESIGN.md` | Each campaign's story spine, roster and mission list |

---

## 1. Core design philosophy

### 1.1 What a good mission is

A good mission gives the player **an interesting tactical problem**, **enough
information to make informed decisions**, **meaningful consequences** for
those decisions, and **the satisfaction of winning through their own
choices**.

The owner's standing goal for this add-on: missions are **tough**, the fun
comes from **several approaches to each mission**, and no mission ever
**feels impossible**.

### 1.2 Principles

1. **Decisions over execution.** Every mission must contain at least one
   decision whose right answer depends on the battlefield: which approach to
   defend, when to commit the reserve, whether to risk detection for
   information. A mission that only asks the player to execute an obvious
   plan carefully is a chore, however well it is scripted.
2. **Terrain is the first tool.** Wesnoth's identity is terrain defense,
   movement cost, villages, time of day and zones of control. A mission's
   problem should be expressed through the map before it is expressed through
   scripts. Fix a tactical problem with the map before adding enemies or
   events.
3. **Fair difficulty.** Losing must be explainable by a decision the player
   could have made differently with the information they had. Every scripted
   threat that the player could prepare for (a landing, a sortie, a hazard, a
   reserve) is either visible a full player turn before it can act, or named
   in the objectives with its trigger. Unannounced
   ambushes that kill a critical hero, reinforcements behind the player with
   no warning, and objectives that require knowledge from a previous failed
   attempt are unfair, not hard.
4. **Agency over spectacle.** Scripted events exist to change the tactical
   situation and to tell the story through play. An event that only shows
   something, or that takes a decision away from the player, needs a strong
   narrative reason and should be short.
5. **Less can be better.** A revision can remove mechanics, enemies or
   events. A conventional battle on an excellent map with a well-tuned enemy
   is a complete mission.
6. **Each mission has an identity.** It should be remembered for something:
   a map, a situation, an enemy, a decision. Two adjacent missions should not
   be remembered for the same thing.
7. **The campaign is the product.** A mission is judged in its place in the
   sequence: what came before, what the player has learned, what army they
   bring, what comes next.

### 1.3 Why missions must reward intelligent play

Luck, hidden information and arbitrary difficulty make outcomes feel
unearned. The player reloads instead of thinking, and a win teaches nothing.
Wesnoth combat is random per strike, so a mission must be robust to bad rolls:

- no single enemy turn may end the mission on Normal without a visible
  warning the turn before;
- critical units should not be forced into positions where an average enemy
  turn kills them;
- objectives should have slack (turns, units, hit points) so that one missed
  attack does not decide the mission.

### 1.4 Systems this add-on already provides

Use these before inventing scenario-specific scripts. Each is documented in
`docs/systems/` and the in-game Field Manual.

| System | Use it for | Source |
|---|---|---|
| Hero withdrawal | Non-critical heroes leave wounded instead of dying, so one bad turn does not end a mission | `SW_HERO_WITHDRAWS`, `utils/hte_macros.cfg` |
| Critical heroes | Only the leader and the objective's subject lose the mission | `SW_HERO_DEATH_IS_DEFEAT` |
| Stealth and alert | Guards with facing and sight cones, takedowns, alarms | `lua/sw_alert.lua` |
| Overwatch | Reaction fire that punishes careless advances | `lua/sw_overwatch.lua` |
| Air support | Limited strafing and bombing runs for either side | `lua/sw_air.lua`, `SW_AIR_SUPPORT` |
| Intelligence and electronic warfare | Sensors, jamming, revealed and hidden units | `lua/sw_ew.lua` |
| Force powers | Cooldown abilities for Force users; ysalamiri zones cancel them | `lua/sw_force.lua`, `SW_YSALAMIRI_ZONE` |
| Command decisions | A one-time choice offered to the player mid-mission | `lua/sw_command.lua` |
| Thrawn's doctrine | The enemy learns the player's habits in Thrawn's battles | `lua/sw_doctrine.lua` |
| Bonus objectives | One optional goal per mission, paid in credits next mission | `lua/sw_bonus.lua`, `SW_BONUS` |
| Weapon ranges | Rifles 2 hexes, heavy weapons 3, Jedi deflection 2 | `docs/systems/WEAPON_RANGES.md` |
| Ranks | Veteran abilities and tough-kill experience | `lua/sw_rank*.lua`, `lua/sw_xp.lua` |

---

## 2. Universal quality rubric

### 2.1 Criteria and weights

| Criterion | Weight | Core question |
|---|---|---|
| A. Tactical depth | 20% | Are there meaningful decisions and more than one viable approach? |
| B. Map design | 15% | Does the terrain shape combat, movement and positioning? |
| C. Difficulty and fairness | 15% | Is success earned by decisions, not luck or foreknowledge? |
| D. Objective design | 10% | Are the goals clear, interesting and honestly implemented? |
| E. Pacing and escalation | 10% | Does the mission develop, without dead time or a decided-early finish? |
| F. Enemy AI behavior | 10% | Does the enemy act out its role convincingly, without exploitable failure? |
| G. Army management and progression | 10% | Do recruits, veterans, gold and casualties matter, without cascading harm? |
| H. Narrative integration | 5% | Does play tell the story, with motivated objectives and in-character factions? |
| I. Mission identity | 5% | Is it memorable and different from its neighbors? |

### 2.2 Scoring

Each criterion gets **0–5**. The mission score is

```
score = Σ (criterion score / 5 × weight)          → 0–100
```

Score each criterion **against the mission's type** (section 3): an escape is
not marked down for lacking a frontal assault.

| Points | Meaning |
|---|---|
| 5 | Exemplary: a reference other missions should copy |
| 4 | Strong: works well; small, specific improvements possible |
| 3 | Adequate: works but is ordinary or has a clear weakness |
| 2 | Weak: a real problem that players will notice |
| 1 | Poor: the criterion mostly fails |
| 0 | Broken or absent |

### 2.3 Scoring anchors per criterion

**A. Tactical depth (20%)**
- 5: two or more approaches that a strong player would genuinely choose
  between depending on circumstances; competing threats force prioritization;
  mistakes are recoverable at a cost.
- 3: one clearly best approach with minor variations; positioning matters.
- 1: the plan is obvious and the mission is execution only, or the best play
  is passive (wait, turtle) by a wide margin.
- Common failures: false choices (two routes, one obviously better); a
  dominant strategy (e.g. "send the fast hero alone"); missions won by
  ignoring the enemy.

**B. Map design (15%)**
- 5: terrain creates chokepoints, flanks and defensible ground that matter;
  villages and healing are placed to create decisions; travel time is right
  for the turn limit.
- 3: functional map; terrain matters in places; some dead space.
- 1: terrain is decorative, or travel dominates play, or the map funnels
  everything into one line.
- Check: the movement cost of the main routes for the units that must use
  them, against the turn limit; where each side's units will first meet;
  whether faction movetypes create asymmetry on purpose.

**C. Difficulty and fairness (15%)**
- 5: hard but legible; every threat is visible or announced before it can
  strike; Easy, Normal and Hard differ in meaningful ways; first attempt is
  winnable by a careful player.
- 3: fair on Normal but one difficulty is mis-tuned, or one spike needs a
  reload.
- 1: success depends on luck, foreknowledge or an AI exploit; or the mission
  is trivially easy for its place in the campaign.
- Evidence: force ratios (`mission_balance_report.py`), opening threat to
  critical heroes (`hero_threat_report.py`, AI soak), owner playtest reports.

**D. Objective design (10%)**
- 5: the goal is clear, motivated, and shapes play; displayed text matches the
  victory and defeat logic exactly; optional objectives create a real
  trade-off.
- 3: clear but generic ("defeat the enemy leader"), or the bonus is a chore.
- 1: objective text and logic disagree, or a stated objective is impossible.
- **Any mismatch between displayed and implemented objectives is a confirmed
  defect**, regardless of score.

**E. Pacing and escalation (10%)**
- 5: a clear opening, a developing problem, a change in the situation, and a
  climax; no long stretch without decisions; the end is not decided many
  turns before it arrives.
- 3: steady but flat, or a few turns of mop-up.
- 1: long empty travel, endless waves, or a finish decided on turn 3.

**F. Enemy AI behavior (10%)**
- 5: the enemy acts out its role (garrison holds, pursuers pursue, raiders
  raid, commanders preserve themselves); no exploitable failure.
- 3: generic aggression that fits roughly; minor exploits.
- 1: the enemy idles, suicides, or ignores the objective it should contest.
- Prefer standard AI configuration (`aggression`, `caution`, `[goal]`,
  `ai_special=guardian`, `passive_leader`, `[avoid]`, goto) before Lua.

**G. Army management and progression (10%)**
- 5: recruit choices matter; veterans are worth protecting; losses hurt but
  do not cascade; the mission is winnable from a weak carried-over army.
- 3: army choices are minor, or the mission gives a fixed force with no
  decisions.
- 1: the mission punishes the player for earlier choices out of proportion,
  invites farming, or forces losses of veterans without reason.
- Note: hero-only missions (no recruiting) are scored on how the fixed force
  is used: positioning, sequencing, and preservation.

**H. Narrative integration (5%)**
- 5: the objective is what these characters would actually be trying to do;
  dialogue is brief and tied to play; consequences carry forward.
- 3: plausible but generic; dialogue does not react to play.
- 1: the mission contradicts the story or the factions act out of character.

**I. Mission identity (5%)**
- 5: a clear hook the player will remember; not repeated nearby.
- 3: a recognizable situation, but similar to an adjacent mission.
- 1: indistinguishable from other missions.

### 2.4 Score interpretation and action

| Score | Assessment | Action |
|---|---|---|
| 90–100 | Excellent | Preserve. Fix only specific identified defects. |
| 80–89 | Strong | Minor, targeted improvements. |
| 70–79 | Good but imperfect | Improve the identifiable weaknesses. |
| 50–69 | Significant problems | Substantial redesign may be warranted. |
| < 50 | Poor | Reconsider the fundamental design. |

These are this project's review thresholds, not a Wesnoth standard.

**Overrides.** A critical defect (unwinnable objective, broken progression,
crash, objective text that contradicts the logic) is fixed first whatever the
score. A high score never excuses a confirmed defect.

**No score chasing.** A mission at 85 is not reworked to reach 90 unless a
specific weakness with a credible fix has been identified. A revision does
not earn a higher score automatically; it is re-scored on new evidence.

### 2.5 Evidence and severity

Every finding is labelled with how it is known:

| Label | Meaning | Example |
|---|---|---|
| **Confirmed defect** | Shown by code tracing or an engine test | Objective says "never raise the alarm", but the required pickup raises it by script |
| **Strong design finding** | Supported by specific mechanical evidence | Last wave on turn 7 of 14; the remaining 7 turns are mop-up |
| **Design hypothesis** | Plausible, needs playtest | "The north route is probably never taken" |
| **Subjective preference** | Taste, not yet shown to affect play | "The map would look better with more water" |

Priorities:

| Priority | Class |
|---|---|
| P1 | Broken or unwinnable mission, broken campaign progression |
| P2 | Serious balance or progression defect |
| P3 | Unfair or confusing play; objective text that misleads |
| P4 | Repetitive or weak tactical design |
| P5 | Minor polish |

---

## 3. Mission-type design standards

Classify the mission by what the player is **trying to do**. Hybrids are
evaluated phase by phase. The type sets what "good" means for criteria A, B,
E and F.

### 3.1 Conventional battle
- **Experience:** two forces contest ground; maneuver, composition and terrain
  decide it.
- **Needs:** at least two viable axes of attack; terrain worth fighting for
  (villages, high ground, fords); an enemy that recruits to counter the
  player.
- **Opportunities:** time of day, flank versus center, village economy.
- **Anti-patterns:** the enemy leader is the only objective and sits at the
  far end; one central chokepoint decides everything; enemy gold as the only
  difficulty lever.

### 3.2 Defensive operation
- **Experience:** hold something with limited forces against a stronger
  attacker.
- **Needs:** more ground to cover than units to cover it, so allocation is
  the decision; attacks that arrive from more than one direction, announced;
  a moment to counterattack.
- **Opportunities:** fallback lines, reserves, repairing or reinforcing
  positions, choosing what to give up.
- **Anti-patterns:** one chokepoint the player plugs and waits behind;
  identical waves on a timer; turn limits long after the last wave.

### 3.3 Assault and siege
- **Experience:** break a prepared defense.
- **Needs:** more than one approach (walls, gate, flank, sapper or sabotage
  route); defensive obstacles that can be removed at a cost; a breakthrough
  moment that changes the battle.
- **Anti-patterns:** a frontal grind with no alternative; defenders who
  leave their fortifications; a turn limit too tight for anything but the
  obvious approach.

### 3.4 Escape and retreat
- **Experience:** get out alive with as much as possible.
- **Needs:** pursuit that grows; more than one route with different risks;
  meaningful sacrifices (rear guards, abandoned assets); a turn limit or
  pursuer that makes delay costly.
- **Anti-patterns:** pursuers that never catch up; a turn limit so generous
  that the player can clear the map and walk out; blocking forces that
  cannot be bypassed.
- **Turn limit (this project's rule, 2026-10-17):** on Normal, at most about
  **three times** the objective unit's unobstructed travel time, as measured
  by the engine route check in `run_campaign_sequence.py` (`ROUTE_SPECS`).
  The runner already fails a route that needs more than 80% of the limit.

### 3.5 Escort and rescue
- **Experience:** protect something that cannot protect itself, or extract
  someone under threat.
- **Needs:** the protected unit is controllable or behaves predictably; real
  threats to it that the player can see coming; route and timing choices.
- **Anti-patterns:** an AI-controlled escort that wanders into danger;
  one-hit failure of the protected unit; time pressure so loose it does not
  matter.

### 3.6 Reconnaissance and infiltration
- **Experience:** information and stealth are the weapons.
- **Needs:** what the player learns changes what they do next; detection has
  graded consequences (alert, then alarm), not instant failure; patrols that
  can be read and timed.
- **Anti-patterns:** a "recon" mission that is a battle with a scout in it;
  instant mission loss on first detection; patrol behavior that cannot be
  predicted from what the player sees.

### 3.7 Survival
- **Experience:** endure rising pressure until relief arrives.
- **Needs:** pressure that changes in kind, not just in number; positions
  worth moving between; a clear end condition shown from turn 1.
- **Anti-patterns:** one safe corner; long quiet stretches; waves that are
  the same unit from the same edge.

### 3.8 Commander confrontation (boss battle)
- **Experience:** defeat a distinctive enemy leader who fights differently.
- **Needs:** behavior or powers that are telegraphed and can be countered by
  positioning or tools (ysalamiri, ion, overwatch); a phase change; support
  units that matter.
- **Anti-patterns:** an invulnerable boss the player cannot affect; a damage
  race; a boss that kills a critical hero on turn 1.

### 3.9 Multi-objective and hybrid
- **Experience:** competing priorities.
- **Needs:** objectives that pull forces in different directions, so
  achieving one costs another; consequences for skipped optional goals.
- **Anti-patterns:** objectives that can all be done by the same blob in
  sequence; optional goals with no cost and trivial reward.

### 3.10 Space battles (this add-on)
- Space maps have no villages and no healing beyond abilities (astromech,
  carriers), so attrition is permanent within the mission. Missions must be
  shorter or offer resupply.
- Evasion ratings (`gen_hte_units.py` `EVASION_*`) make fighters hard to hit
  and capital ships easy: a fair space mission gives the player targets for
  every craft role (interceptors versus fighters, bombers versus ships).
- Asteroids are the terrain: they must create cover lanes and choke points,
  not just decoration.

---

## 4. Campaign-level design

Good missions can still make a poor campaign. Each campaign is reviewed as a
whole in `CAMPAIGN_DESIGN_REVIEW.md` against these standards.

### 4.1 Variety
- Map the sequence by type, objective, map structure, enemy mix, opening
  deployment and reinforcement pattern.
- **Repetition must be deliberate.** Two consecutive missions of the same
  type need a reason (a story beat that repeats on purpose) and must still
  differ in the decision they ask for.
- No quota of mission types. A campaign that is mostly defensive because the
  story puts the player on the back foot is fine, as long as each defense is
  different.

### 4.2 Difficulty progression
- Measure: force ratio per mission (Normal), opening threat to critical
  heroes, AI-soak outcomes, owner playtest reports.
- Expect a rising trend with recovery missions after spikes. A finale is the
  hardest mission in its campaign but must remain winnable on Normal with an
  average carried-over army.
- New threats are introduced in a mission where the player has room to learn
  them before a mission that depends on them.

### 4.3 Army, gold and recall
- Gold carryover is 40% of what is left plus the bonus bank
  (`lua/sw_bonus.lua`). Missions set a base gold for each difficulty so that
  a player who arrives with nothing can still win.
- Recalled veterans should be **worth** recalling: a mission that recruits
  should usually allow recalls of the same domain (ground or space; PR #428).
- Hero missions without recruiting are fine; they must not follow each other
  so long that the recruited army is forgotten.
- No mission may require an outcome from an earlier one that the player could
  have reasonably failed (e.g. "all four warships saved").

### 4.4 Consequences between missions
- Outcomes should **carry forward visibly** where the story supports it
  (warships saved, miners stolen, prisoners freed), in small bounded amounts:
  one unit more or fewer, some gold, a changed line of dialogue.
- Consequences must not cascade: a bad result makes the next mission harder,
  never unwinnable.

### 4.5 Mechanical progression
- Introduce one major new mechanic per mission at most, in a mission where it
  is the focus, with a Field Manual entry and a just-in-time tip
  (`lua/sw_tips.lua`).
- Reuse mechanics later in new combinations so learning pays off.

### 4.6 Narrative pacing
- Alternate large engagements with smaller operations; let quiet missions
  build tension for the next big one.
- The player should understand why each mission matters in the larger war.

---

## 5. Design anti-patterns

| Anti-pattern | How to spot it | Correction |
|---|---|---|
| **Enemy spam** | Waves of the same unit every N turns; force ratio driven by reinforcements | Fewer, better-chosen units with roles; vary entry points; tie waves to player actions |
| **Gold as the only lever** | Difficulty differs only in enemy gold | Use terrain, deployment, AI goals, timing, recruit lists |
| **Artificial difficulty** | Unannounced spawns next to critical units; hidden instant-loss rules | Announce threats a turn ahead; show every lose condition in the objectives |
| **Meaningless objective** | An objective nobody would choose differently for | Tie it to a trade-off or remove it |
| **Impossible optional objective** | The bonus fails by script | Confirmed defect: fix the logic or the wording |
| **Passive optimal play** | Waiting behind a choke wins comfortably | Pressure that rewards action: objectives that decay, an enemy that maneuvers |
| **Dead tail** | Last wave or decisive event many turns before the end | Shorten the limit, or add a reason to act (bonus, counterattack, early-win option) |
| **Repetitive battles** | Same type and same decision in adjacent missions | Change the decision, the map structure or the enemy role |
| **Ineffective terrain** | Large regions nobody needs to enter | Move objectives or villages so the region matters, or cut it |
| **Exploitable AI** | The enemy ignores its objective, suicides into a boss, or never leaves its keep | `[goal]`, guardian, `passive_leader`, `[avoid]`, caution; scripted orders only when needed |
| **Frustrating escort** | An AI ally walks into danger | Give the player control, or a predictable, visible route |
| **Excessive scripting** | Long dialogue, events that move units for the player | Shorten; let play show the story |
| **Unavoidable losses** | A veteran or hero must fall for the story | Use withdrawal; make losses a choice with a reward |
| **Foreknowledge required** | Only a second attempt can win | Warn in objectives, dialogue or a visible map cue |
| **Consequence-free campaign** | Outcomes never matter later | Bounded carry-forward effects (4.4) |

---

## 6. Improvement and validation

### 6.1 Procedure

1. **Inventory and classify.** Type, premise, signature decision, objectives,
   forces, scripts, carry-over dependencies.
2. **Score** with evidence for each criterion (section 2).
3. **Diagnose** each weakness, answering:
   1. What is wrong?
   2. Why does it reduce play quality?
   3. What evidence supports it (file:line, numbers, test)?
   4. What player behavior does it encourage?
   5. What change addresses it?
   6. Why that change rather than alternatives (including removing something)?
   7. What could it break (campaign variables, achievements, tests, balance)?
   8. How will the improvement be tested?
4. **Review the whole campaign** before redesigning any mission
   (section 4), so a fix does not create repetition or a difficulty spike.
5. **Prioritize** (P1–P5). Fix confirmed defects first.
6. **Implement incrementally**: small, separate changes; preserve scenario
   ids, `next_scenario` chains, campaign variables and save compatibility.
7. **Validate** (6.3) and **log** in `MISSION_IMPROVEMENT_LOG.md`.

### 6.2 Choosing between alternatives

Prefer, in order:
1. fixing logic or text that is wrong;
2. retuning existing levers (placement, timing, AI goals, turn limit);
3. changing the map;
4. reusing an existing system (section 1.4);
5. adding a new scripted mechanic.

Choose the smallest change that produces a meaningful improvement. Record the
alternatives considered.

### 6.3 Validation requirements

| Change | Minimum validation |
|---|---|
| Any WML or Lua | Engine preprocess and load of the campaign (`run_systems_tests.py` or the scenario probe) with no errors |
| Objective or event logic | An engine test that triggers the event and checks the outcome (`production/linux_engine/*_plugin.lua`) |
| Victory or defeat path | Engine test reaching each changed path |
| Campaign variable carried between missions | `run_campaign_sequence.py` for the campaign |
| Balance-relevant change | `mission_balance_report.py` for all difficulties, plus an AI soak (`run_ai_soak.py --player careful`) where the AI player can play the mission |
| Map change | `render_map_preview.py` review and a route check for the units that must use it |
| Player-facing text | `gen_pot.py --check` after regeneration |

### 6.4 What counts as evidence of improvement

- **Defect fixes:** an engine test that failed (or could not pass) before and
  passes after.
- **Design changes:** a measurable change in the problem's signature: the
  opening threat to a critical hero, turns of dead tail, number of viable
  routes within the turn limit, AI soak outcome turns. State what would show
  the change failed.
- **Play quality itself** is only established by human play. Automated
  results are recorded as such; the AI player cannot sneak, carry objectives
  or read the Field Manual, so its losses are not a difficulty measure in
  themselves. Every design change lists what a human playtest should check.

Never claim a mission is balanced because it loads, or because the AI player
can finish it. Never invent test results.

---

## 7. New-mission design gate

Before a new mission is built, or an existing one is redesigned, write down:

| Item | Question |
|---|---|
| Narrative purpose | Why does this mission exist in the campaign? |
| Tactical premise | What military problem must the player solve? |
| Signature decision | What is the most important trade-off the player faces? |
| Progression | How does the situation develop over the turns? |
| Distinctive quality | What makes it different from the adjacent missions? |
| Fairness criteria | What does a capable player need to know and have to win? |
| Validation | How will its mechanics and outcomes be verified? |

The signature decision matters most. Examples from this add-on:

- **Raid on Karrde's Base:** hold the house or hold the landing field while
  the transports' engines warm up.
- **Prisoner of Myrkr:** risk a takedown to open a route, or wait for the
  patrol to turn.
- **Thrawn's Gambit:** protect both warships, or strike one Star Destroyer
  hard enough to force a withdrawal.

---

## 8. Maintaining this standard

- Change this document only for a lasting lesson, with the reason in the
  improvement log.
- Keep `SCENARIO_AUDIT.md` current: re-score a mission after any design
  change, citing the new evidence.
