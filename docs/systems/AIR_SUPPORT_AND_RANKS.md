# Off-map air support and rank insignia

## Air support (`lua/sw_air.lua`)

Fast starfighters and bombers support ground battles as **off-map
sorties**, not map units (project scope 5.3).

### Calling a sortie

- **Who can call:** a unit with the forward-observer ability
  (`[dummy] id=sw_ability_forward_observer range=N`).
- **How:** right-click a hex the side can see, or tracks on sensors as at
  least a partial contact (`sw_ew`), within the observer's range. Then
  choose **Call air support…**.
- **Cost:** calling uses the observer's attack. One sortie per side per
  turn. Charges come from the mission.
- **Information before calling:** the window shows accuracy, every
  modifier, the visible enemies and friends in the area, and the expected
  damage to each.

### Sortie types

| Sortie | Area | Timing | Per unit | Accuracy |
| --- | --- | --- | --- | --- |
| Strafing run | 4 hexes in a line, running away from the observer | immediate | 3 shots × 6 fire | +0 |
| Bombing run | target + 6 neighbours | lands at the caller's next turn start; the area is marked for **everyone** (`misc/sw-air-inbound.png`) | 2 bombs × 9 fire | +10 |

### Resolution

- **Hit chance:** each shot hits with `100 − target terrain defence +
  accuracy`, clamped 10–90%. Rolls use the synced RNG, so cover matters
  and replays match.
- **Accuracy modifiers:**
  - Enemy anti-air (`[dummy] id=sw_ability_anti_air radius= penalty=`)
    within its radius of any struck hex: −20 each, −40 at most.
  - Enemy ECM covering the target hex: −10 per point above the
    observer's ECCM.
- **Damage:** dealt through `[harm_unit]`, so resistances apply. The
  observer earns experience.
- **Not selective:** every unit in the area is hit, friend or foe.
- **Never lethal:** a unit is left with at least 1 HP. Air support softens;
  ground forces finish. A mission is never lost to an off-map strike
  alone.

### Units

- **Forward observers:**
  - New Republic: sergeants (6 hexes) and commandos (7).
  - Bel Iblis's commandos (7).
  - Imperial: officers (6), stormtrooper sergeants (5) and scout troopers
    (7).
  - Commanders Han, Lando, Leia, Bel Iblis and Pellaeon.
- **Anti-air:** AT-ST walkers and E-Web teams (radius 2), and shield
  generators (radius 3).

### AI

AI sides with sorties call one at the end of their turn. The target is the
visible enemy position with the highest expected damage to enemies, minus
twice the expected damage to friends, and the call must clear
`sw_air_ai_min` (default 8). The AI never bombs its own units. While a
bombing run is inbound, hostile AI sides avoid its area through the AI
`avoid` aspect.

### Missions

| Mission | Player | Enemy |
| --- | --- | --- |
| HTE 2 Bpfassh | 1 X-wing strafe | scripted TIE pass (unchanged balance: certain, 8 damage, never lethal) |
| HTE 6 Raid on Karrde's Base | — | TIE strafe, TIE bomber run |
| HTE 8 Nomad City | — | 2 TIE strafes |
| DFR 4 The Senator's Men | 1 X-wing strafe | — |
| DFR 5 The Peregrine's Nest | 2 X-wing strafes, 1 Y-wing bombing run | 1 TIE strafe |
| TLC 6 Gates of Mount Tantiss | — | TIE strafe, TIE bomber run |

Objectives carry a note (`{SW_NOTE_AIR_SUPPORT}` / `{SW_NOTE_ENEMY_AIR}`),
and the Field Manual has an "Air support" page.

### Configuration

```
{SW_AIR_SUPPORT 1 strafe 2 sw_unit_nr_xwing}         # in prestart or later: side, sortie, count, craft
[sw_air_support] side=1 sortie=bombing count=1 craft=sw_unit_nr_ywing [/sw_air_support]
[sw_air_strike] side=2 sortie=strafe craft=sw_unit_im_tie_fighter damage=8 strikes=1 certain=yes
    enemies_only=yes [filter_location] y=10 x=8-20 [/filter_location] [/sw_air_strike]  # scripted set piece
[set_variable] name=sw_air_ai value=no [/set_variable]   # AI does not call sorties
[set_variable] name=sw_air_ai_min value=8 [/set_variable]
[set_variable] name=sw_air_effects value=no [/set_variable]   # no flyover/blasts (display only)
```

### Extending

- **New sortie types:** `sw_systems.air.register_sortie(id, { name, length
  or radius, strikes, damage, damage_type, accuracy, delay, sound, impact,
  description })`.
- **Hooks:** `air.hooks.modify_accuracy`, `air.hooks.on_call` (Thrawn
  Doctrine observes air strikes as a tactic), `air.hooks.on_strike`.

### State

- `sw_air_s<side>`: charges, craft, last turn used. Stamped with the
  scenario id; charges never carry into the next mission.
- `sw_air_inbound`: bombing runs that have been called but not yet landed.

### Visuals

- **Flyover:** a fake unit of the craft type flies the strike path, using a
  hidden `sw_flyover` variation with flying movement (`gen_hte_units.py`
  `FLYOVER_CRAFT`). The engine warns that it has no ordinary route over
  enemy-held hexes, then uses its emergency path as intended; the soak
  ignores that warning.
- **Blasts:** core flame-burst halos, rippling along the strike line one hex at a time (`air.PACING`: approach and exit hexes, 160 ms between detonations, 90 ms burst frames). A strike takes about 3–3.5 s at normal speed.

## Rank insignia (`lua/sw_rank.lua`)

### How rank is earned

- **Rank** = the type's starting rank + 1 per after-max-level advancement
  (AMLA), shown up to III: I Veteran, II Seasoned veteran, III Elite.
- **Promoted types** (New Republic Sergeant, Stormtrooper Sergeant,
  Smuggler Veteran) start at rank I.
- **Stats** are the engine's default AMLA: +3 max HP, +20% max XP, full
  heal. Balance is unchanged.

### How it's drawn

- The insignia is a 20×10 plate drawn into the unit's own sprite at
  (37,61) with an `image_mod` `BLIT` object, so it shows in every frame. It
  is not an overlay: overlays are hidden whenever an animation turns the
  bars off (lesson #303).
- Each new rank adds one add-only object whose plate exactly covers the
  last, so the unit is never rebuilt mid-turn.
- **Styles** (`gen_hte_units.py` `RANK_HEROES`/`RANK_PREFIXES`, generated
  into `lua/sw_rank_data.lua`):
  - New Republic: gold chevrons.
  - Imperial: red-over-blue rank plaque.
  - Independents: brass studs.
  - Dark Jedi: violet marks.
  - Creatures and objects: none.
- Heroes rank up too.
- **Display:** *Tactical status* shows the rank. A floating label names the
  new rank on promotion.

## Tests

```bash
python3 production/linux_engine/run_systems_tests.py --suite air      # 70 checks
python3 production/linux_engine/run_systems_tests.py --suite replay   # includes sw_test_air_replay
```

**air suite:**
- **Ranks:** promotions in all four styles and militia (no rank); AMLA
  ranks I–III and the cap; objects per rank; default AMLA stats; heroes;
  creatures.
- **Observers and targeting:** observers, range and visibility; the menu
  evaluated as the engine does.
- **Areas and accuracy:** strafing and bombing areas; base, anti-air (cap,
  friendly anti-air ignored), jamming and ECCM.
- **Strafing run:** immediate; resistance-adjusted damage; friendly fire;
  never lethal; charges, attack use and one per turn; doctrine
  observation; experience.
- **Bombing run:** telegraphed; public markers on 7 hexes; lands at the
  caller's next turn; never lethal.
- **Scripted strike:** certain fixed damage, enemies only.
- **Carryover:** mission state is not carried forward.
- **AI:** keeps out of an inbound area; calls its own strafing run.
- **Save/load:** charges, inbound strike, markers and rank insignia.

**sw_test_air_replay:** an AI-versus-AI ground battle with sorties on both
sides, anti-air and near-promotion units, replayed by the engine with
digests compared at four checkpoints.

## Limitations

- **Never lethal:** sorties cannot finish units. This is deliberate, for
  balance and so missions are never lost to off-map strikes.
- **AI avoidance is partial:** the AI won't move into an inbound area, but
  a unit already inside may stay.
- **Mirrored insignia:** when a unit faces left the sprite is mirrored, so
  the insignia sits bottom-left.
