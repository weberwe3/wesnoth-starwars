# Sensors, cloaking and electronic warfare; Thrawn Doctrine

Two integrated, reusable systems for every mission of the add-on:

- **Sensors and electronic warfare** (`lua/sw_ew.lua`). Each team keeps its
  own sensor picture of hostile units and decoys. Contacts progress from
  undetected through an unknown contact and partial identification (class)
  to full identification (type).
- **Thrawn Doctrine** (`lua/sw_doctrine.lua`). A designated side gains
  Insight from enemy behaviour it can actually observe, and configurable
  thresholds unlock explicit effects.

They share the loader, helpers and conventions of the Force and overwatch
systems ([FORCE_AND_OVERWATCH.md](FORCE_AND_OVERWATCH.md)).

## Files

| File | Role |
| --- | --- |
| `lua/sw_ew.lua` | Profiles, detection scoring, pictures, concealment, overlays, sweeps, decoys, reveals, configuration, the Sensor contact text. |
| `lua/sw_doctrine.lua` | Insight storage, observation, patterns, tiers and effects, prediction, scenario control, the summary text. |
| `lua/sw_systems.lua` | Registers every event handler, menu item and WML tag, and wires the systems' hooks together. `sw_systems.digest()` fingerprints the state for tests. |
| `lua/sw_core.lua` | Team keys, sorted iteration, scenario scoping, display-only helpers (viewing side, team-private floating labels). |
| `utils/hte_macros.cfg` | `{SW_THRAWN_DOCTRINE SIDE}`, `{SW_DOCTRINE_GRANT SIDE AMOUNT SOURCE TEXT}`, Field Manual topics. |
| `production/tools/gen_hte_units.py` | `EW_PROFILES` generates `[dummy] id=sw_ability_ew` on lore-relevant unit types; `cloaked()` generates the status-filtered concealment `[hides]`. |
| `production/tools/gen_ui_icons.py` | Contact markers, EW overlays, Insight pips, prediction marker, menu icons. |
| `production/linux_engine/run_systems_tests.py --suite intel\|replay` | Engine tests (see Tests). |

## Sensors and electronic warfare

### Profiles

| Class (by movement type) | Sensor | Range | Signature |
| --- | --- | --- | --- |
| capital (`sw_capital`) | 5 | 7 | 8 |
| starfighter (`sw_starfighter`, `fly`) | 3 | 5 | 3 |
| vehicle (`sw_walker`, `sw_repulsor`, `mounted`) | 3 | 4 | 4 |
| infantry (default) | 2 | 3 | 2 |
| creature (`sw_beast`) | 3 | 3 | 2 |
| object (set with `class=object`) | 0 | 0 | 4 |

Every unit also has cloak 0, ECM 0 (range 2), ECCM 0, scan 0 and decoys 0.
A unit type overrides these with:

```
[dummy]
    id=sw_ability_ew
    sensor=6  sensor_range=8  signature=8
    cloak=0                # needs the concealment [hides] (generator: "cloaked")
    ecm=2  ecm_range=3     # jamming strength and radius
    eccm=1                 # counter-jamming
    scan=3                 # active sweep bonus (0 = cannot sweep)
    decoys=1               # decoy launches per mission
    class=capital  disguise_class=object  decoy_class=capital  decoy_type=<unit type>
[/dummy]
```

A single unit overrides its type with `[sw_ew_profile] [filter]…[/filter]
sensor= … [/sw_ew_profile]`. The tag stores unit variables `sw_ew_<field>`,
and a cloak also grants the concealment `[hides]`.

Lore-based unit-type profiles (generator `EW_PROFILES`):

- Star Destroyers: sensors 6 out to 8, jammer 2 over 3 hexes, sweep +3, one
  sensor decoy.
- A-wings: jammer 2.
- X-wings, Luke's X-wing and Wedge: counter-jamming 1.
- Y-wings: Longprobe-style sweep +3.
- Scout troopers and Wookiee lookouts: better sensors and a sweep.
- Karrde: sweep, jammer 1 and two decoys.
- Commandos, Noghri and infiltrators: signature 1.
- Mole miners: read as objects until identified (Sluis Van).
- Cloaked asteroids: cloak 6, signature 1.

### Detection

All values are integers and there are no dice. The best observer on the team
counts, and sides with the same `team_name` share one picture.

```
score    = sensor + (scan, while sweeping) - floor(distance / falloff)
         - max(0, ECM - observer ECCM - doctrine ECCM)   (hostile jammer covering observer or target)
         + observer terrain modifier + scenario sensor_modifier
         + target signature (+3 sweeping, +2 fired this turn, +2 jamming)
         - target cloak (while active) - target terrain concealment
identify = score + doctrine identification bonus
state    = undetected     if score <  contact (0)
           contact        if score >= contact
           partial        if identify >= partial (3)    (class shown; a disguise shows its false class)
           identified     if identify >= full (6)       (type shown)
```

Further rules:

- Out of an observer's `sensor_range` (+2 while sweeping), that observer
  contributes nothing.
- **Physical contact always identifies.** A unit next to a member of the
  team is identified, and the engine's ambush rule matches this.
- **Ordinary sight identifies.** An uncloaked unit the team can see is
  identified.
- **Fog.** An uncloaked unit under fog is tracked by sensors and drawn as a
  contact marker in the fog.
- **Living stealth** (Noghri `[hides]`) on a hex the team can see cannot be
  tracked by sensors. Force Sense and keen senses handle it, as before.
- **A cloak is active** until the unit attacks. Its cloak then drops until
  its side's next turn, as the engine's `uncovered` status also does.
- **Scenario reveals** (`[sw_ew_reveal]`) set a minimum state for a number
  of turns.

### Engine visibility

A cloaked unit carries the `[hides]` ability `sw_ability_cloaked`, filtered
on the custom status `sw_ew_concealed`. The system sets that status while no
hostile team has identified the unit. The engine therefore hides it from
players, from the AI and from overwatch (which already requires
visibility), and moving next to it still ambushes.

Contacts that are not otherwise visible are drawn as hex overlays restricted
to the observing team (`[item] team_name=`, visible in fog), so no other
team's viewers ever see them.

### Actions

- **Active sensor sweep** (right-click menu, units with `scan > 0`):
  - Commits the unit's attack.
  - Until its side's next turn, the unit adds its scan rating and sees 2
    hexes further.
  - Its own emissions rise by 3, so it is easier to detect.
- **Sensor decoy** (right-click menu, units with `decoys > 0`):
  - Commits the unit's attack and launches a false contact 2 hexes away in
    a chosen direction.
  - The decoy has signature 6 and deception 4 and lasts 2 turns.
  - It reads exactly like a real contact. A team sees through it at
    `identify >= full + deception - discrimination`, or by moving next to
    it.
  - Under fog it can pass for an identified ship. In plain sight it can
    only pass for a classified (cloaked) contact.
- **Sensor contact** (right-click a marked hex) shows the reading and its
  terms. The text is the same for decoys and real contacts.
- **Tactical status** (right-click a visible unit) shows the unit's sensor
  and EW profile and your team's sensor state of it.

### Scenario configuration

```
[sw_ew_settings]                      # thresholds and modifiers (any subset)
    contact=0  partial=3  full=6  falloff=2  sweep_range=2  sweep_signature=3
    fire_signature=2  ecm_signature=2  decoy_signature=6  decoy_deception=4
    decoy_turns=2  decoy_range=2  sensor_modifier=-2   # e.g. an ion storm
    default_terrain=yes
    [terrain]                         # checked before the defaults; first match wins
        terrain=Qsa  conceal=2  sensor=-1   # conceal: target there; sensor: observer there
    [/terrain]
[/sw_ew_settings]
[sw_ew_reveal] [filter] id=… [/filter] side=1 state=contact|partial|full turns=1 [/sw_ew_reveal]
[sw_ew_decoy] x= y= side= class=capital type=sw_unit_im_star_destroyer signature= deception= turns= [/sw_ew_decoy]
[sw_ew_profile] [filter] … [/filter] cloak=5 signature=1 … [/sw_ew_profile]
```

The default terrain rules are:

| Terrain | Target concealment | Observer sensor |
| --- | --- | --- |
| Asteroid field (`Qsa`) | 2 | −1 |
| Forest (`*^F*`) | 1 | — |
| Settlements and structures (`*^V*`) | 1 | — |
| Mountains (`M*`) and forested hills | 1 | — |

`sw_ew_ai=no` stops AI sides from sweeping.

## Thrawn Doctrine

### Observation

A doctrine side observes only what its team's picture supports:

- Moves need the mover partially identified or better.
- Studying a unit type needs full identification.
- The defender's own side always sees who attacks it.

Observations by category:

| Category | Observed | Key |
| --- | --- | --- |
| move | completed enemy move | heading (n, ne, …) |
| attack | enemy attack | damage type / range |
| target | enemy attack | leader, Force user, wounded, isolated, front line |
| recruit | enemy recruit | class |
| formation | end of an enemy turn (≥3 identified units) | tight / dispersed |
| tactic | overwatch, sensor sweep, Force power, exposed decoy | the tactic |
| composition | doctrine side's turn start | each newly identified type |

Gains:

- Each observation gains its category's amount (default 1, tactics 2), at
  most `turn_limit` times per category per turn.
- A **pattern** is recognised when one key has at least `pattern_min` (4)
  observations and at least `pattern_share` (50%) of its category. Each
  recognised pattern gives a one-off +3.
- Insight never exceeds `cap` (100).

### Tiers and effects

The defaults are below. Every value is configurable, and the effects are
explicit and visible.

| Insight | Effect | What it does |
| --- | --- | --- |
| 10 | summary | Intelligence summary: identified enemy types, classified contacts ("unconfirmed, may be decoys"), unknown contacts, studied types, intelligence log. Only what the team detects; decoys are counted as they are read. |
| 25 | patterns | Recognised patterns with their counts (heading, favoured attack, chosen targets, reinforcements, formation, tactics). |
| 40 | sensors | Team identification +2, ECCM +2, decoy discrimination +2 (+2 more once enemy decoy use is recognised). Counter-deployment advice: the doctrine side's deployed unit type most resistant to the favoured damage type. **Contact detection is not improved**, so cloaks and jamming still work. |
| 60 | prediction | With a recognised target pattern, marks up to 3 own units matching it that known enemies can reach this turn (marker visible only to the doctrine team). |
| 80 | coordination | +10% chance to hit studied enemy types (seen in action at least 3 times), in attacks and overwatch reactions. The ability is visible on every doctrine unit, inactive below the tier. |

Indicators:

- Red pips over the doctrine side's commander show the tiers reached.
- *Tactical status* on that commander shows Insight, the active effects and
  the next threshold, to any player.
- The doctrine side's own player gets the **Thrawn's doctrine** menu (the
  summary).

### Scenario control

```
{SW_THRAWN_DOCTRINE 2}                                   # enable (campaign default: turn_limit=1)
[sw_doctrine] action=enable side=2 cap=100 turn_limit=2 pattern_min=4 pattern_share=50
    study_min=3 watch=1,3 persist=no
    [tier] insight=10 effect=summary [/tier]             # replaces the default tiers
    [tier] insight=40 effect=sensors identify=2 eccm=2 discrimination=2 [/tier]
    [gains] move=1 attack=1 tactic=2 pattern=3 [/gains]
[/sw_doctrine]
[sw_doctrine] action=disable|reset side=2 [/sw_doctrine]
[sw_doctrine] action=cap side=2 cap=40 [/sw_doctrine]
[sw_doctrine] action=seed side=2 amount=30               # exact Insight, plus optional seeds
    [study] type=sw_unit_nr_xwing count=3 [/study]
    [pattern] category=target key=wounded count=4 [/pattern]
[/sw_doctrine]
{SW_DOCTRINE_GRANT 2 15 art ( _ "Recordings of …")}      # Cultural and Art Intelligence
```

`grant` (sources `art`, `archive`, `intelligence`, `conversation`,
`objective`):

- Adds Insight up to the cap, ignoring the per-turn limit.
- Accepts the same `[study]` and `[pattern]` seeds as `seed`.
- Is logged and shown in the summary.
- Floats `+N insight` over the commander for that team.

Campaign use:

- Doctrine is enabled for Thrawn's own commands: HTE 9 and 10, DFR 9, and
  TLC 1, 9 and 10.
- HTE 10 grants 15 for studied art.
- TLC 1 grants 10 for Delta Source reports.

## Integration and hooks

- **Doctrine → EW:** `ew.hooks.bonus` (identification, ECCM, decoy
  discrimination per team).
- **EW → Doctrine:**
  - `ew.hooks.on_decoy_exposed` records the enemy's decoy use.
  - `ew.on_tactic` reports sweeps.
- **Overwatch:**
  - Hidden (concealed) units cannot be targeted.
  - `overwatch.hooks.modify` carries coordinated fire.
  - `overwatch.on_enter` is observed.
- **Force:** `force.on_power_used` is observed.
- **Future systems:**
  - `ew.hooks.relay(team) → sides` (command networks sharing sensors).
  - `ew.hooks.modify_score(observer, target, terms)` (scenario deception,
    nebulae).
  - `ew.hooks.on_state_change(team, record, old)`.
  - `doctrine.hooks.on_observe / on_tier / on_grant`.

### Precedence

Per event, all registered in `sw_systems.lua`:

| Event | Order |
| --- | --- |
| `moveto` | overwatch serial → null field → sensor pictures → doctrine observes the move |
| `attack` | doctrine observes the weapon and target → both units marked as emitting |
| `turn refresh` | overwatch expiry → null field → Force → EW (sweeps end, decoys and reveals expire, pictures) → doctrine (composition, studied marks, prediction) |
| `side turn end` | doctrine formation → AI sweeps → AI overwatch |

## Determinism, save/load, AI, information safety

- **No randomness.** Detection and doctrine use no randomness and no clock.
  Units iterate in id order, and Lua `pairs()` results are sorted before
  they affect state.
- **Synced actions.** Player actions are synced menu commands and `[message]`
  options. Information windows use `side_for=` so only the asking player
  sees them in multiplayer.
- **Saved state.** All state is in WML or unit variables and persistent
  items. Mission state is stamped with the scenario id: EW and doctrine
  state, and also the ysalamiri null-field sources (a regression fix), are
  dropped at the next mission unless `persist=yes`.
- **AI sides:**
  - They are hidden from by the engine like players.
  - They use passive sensors, and sweep at turn end when they hold
    unidentified contacts.
  - Their doctrine bonuses apply mechanically. The AI does not read
    summaries.
- **Menus cannot betray hidden units.** They appear only over units the
  viewer can see, or hexes with the viewer's own contacts.

## Tests

```bash
python3 production/linux_engine/run_systems_tests.py --suite all
```

The full run currently passes 241 checks.

- **static:** No `_` loop variable shadows the textdomain function. No
  unsynced randomness, clock or file access in game logic. The viewing side
  is read only by the display helper.
- **force:** The Force and overwatch suite (85 checks).
- **intel** (142 checks, `sw_test_intel`, side 1 under fog):
  - Profiles; detection thresholds at exact scores (−1, 0, 2, 3, 5, 6);
    concealment and decloaking; adjacency; firing.
  - ECM covering the target or the observer, ECCM, and self-jamming.
  - Sweeps through the real menu event, including the sweeper's own
    emissions.
  - Progressive transitions and a real move order.
  - Decoys: launch, limits, reading, equivalence to a real contact,
    exposure by sensors and by contact, expiry.
  - Terrain and scenario modifiers; configurable thresholds; reveals.
  - **Hidden-information leakage:** menus over a hidden unit's hex match an
    empty hex; every marker is team-restricted; doctrine learns nothing from
    undetected units; the summary lists only detected forces; Tactical
    status is refused for hidden units.
  - **Doctrine:** gains, turn limit, patterns, attack and target
    observation, threshold unlocks, the indicator, tactics; grant, cap,
    seed, reset, disable, custom tiers, gains and watch lists;
    coordination (+10% chance to hit by `simulate_combat`), overwatch
    bonus, prediction, summary.
  - **Integration:** identification improves while detection does not; a
    decoy fools low Insight and is exposed at higher Insight.
  - **Carryover:** state from an earlier mission is dropped.
  - **AI turn:** the AI sweeps for an unidentified contact.
  - **Save/load:** identical digest after reload and after recomputation.
- **replay** (`[test] sw_test_intel_replay`, run with `-u` and
  `--log-strict=error`):
  - Six turns of AI-versus-AI space battle with sweeps, a decoy, a reveal,
    ECM, cloaked asteroids, a disguised mole miner and doctrine on both
    sides.
  - Digests of all intelligence state are recorded through `wesnoth.sync`
    at four checkpoints.
  - The engine then replays the game, and each checkpoint must reproduce
    the recorded digest.

## Engine limitations and fallbacks

| Limitation | Fallback |
| --- | --- |
| The engine's `[hides]` cannot hide a unit from one enemy team but not another. | A cloaked unit stays hidden from every enemy while no hostile team has identified it. Once any hostile team identifies it, it is visible to all enemies. Exact for the campaign's two-team battles. |
| The engine cannot show a unit differently to different viewers. | A partially identified unit stays engine-hidden and is shown as a class marker. Only full identification reveals the unit itself. |
| Per-hex recomputation during moves would be expensive. | Pictures update after each completed action. A cloaked unit moving through sensor range is detected when its move ends; adjacency still ambushes mid-move. |
| Fog cleared during a turn stays cleared until that side's next turn. | A decoy on such a hex can only pass for a classified contact, which is consistent with what the player has seen. |
| The AI cannot weigh uncertain contacts. | AI sides use passive sensors and sweep for unidentified contacts. Hidden units are simply invisible to the AI, as to players. |
| Type resistances are not exposed to Lua without a unit. | Counter-deployment advice compares the doctrine side's units already on the map. |
