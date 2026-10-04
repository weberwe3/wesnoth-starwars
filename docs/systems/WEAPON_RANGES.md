# Weapon ranges, accuracy falloff and aimed shots

Owner design (2026-10-03). This uses the engine's native ranged combat:
attacks carry `min_range`/`max_range`, and the engine only allows targets
within that band. A defender retaliates only with a weapon that reaches the
attacker's distance.

## Ranges

All ranges are set in `production/tools/gen_hte_units.py`, in `WEAPON_RANGES`.

| Class | Max range | Weapons |
| --- | --- | --- |
| Melee | 1 | all melee attacks |
| Pistols, close weapons | 1 | blaster pistol, hold-out blaster, stun blaster, decontamination sprayer |
| **Exception** | 2 | Han Solo's DL-44 (`heavy_blaster_pistol`) |
| Rifles and long arms | 2 | blaster rifle, carbine, bowcaster, scout bike blaster, Myneyrshi bow |
| Thrown or lobbed | 2 | AT-ST concussion grenade |
| The Force | 2 | Force lightning |
| Heavy, crew-served | 3 | E-Web repeater, AT-ST twin blaster cannon |
| Starfighters | 2 | laser cannons, ion cannon |
| Guided | 3, no falloff | proton torpedoes |
| Bombs | 1 | concussion bombs |
| Point defense | 1 | point-defense guns |
| Capital batteries | 3 | turbolasers, Star Destroyer ion cannons |

## Accuracy falloff

- Each hex beyond the first costs 10% chance to hit (`RANGE_FALLOFF`).
- This is applied by a `[chance_to_hit]` weapon special with id
  `sw_special_range`. Its name, such as "range 2", is what puts the range in
  the weapon information beside damage and strikes. The engine's sidebar
  does not show `max_range` itself.
- The formula is `sub="(10 * (distance_between(attacker.loc, defender.loc) - 1))"`.
  Weapon-special formulas see the combatants as `attacker` and `defender`,
  not `self` and `other`.
- Guided weapons show "range 3, guided" and lose no accuracy with distance.

## Aimed shot

- Rifles, carbines, bowcasters, bows and the DL-44 get a second attack,
  "… (aimed)": one strike fewer and +20% to hit (`AIMED_BONUS`).
- `min_range=2`: there is no time to aim at point-blank range.
- `[disable] active_on=defense`: aimed shots are attack-only, so they never
  return fire.
- The player chooses between the standard and the aimed attack in the attack
  dialog. The aimed shot pays off against targets in cover or at distance.
  For example, against 60% defence at 2 hexes: standard 3 × 30% = 0.9 hits,
  aimed 2 × 50% = 1.0 hit.
- Overwatch never uses aimed shots, because they are not in
  `OVERWATCH_WEAPONS`.

## AI

The engine's default AI only attacks from adjacent hexes, and its attack
action refuses targets further away. The candidate action
`lua/sw_ai_ranged.lua`, added for every side at prestart, closes that gap:

- For each unit, it scores every attack from a reachable hex 2+ hexes from a
  visible enemy. The score is expected damage dealt, plus a likely-kill
  bonus, minus 0.8 × the return fire the target could deliver at that
  distance.
- It uses its own expected-damage model, because the engine's combat preview
  evaluates range specials from the unit's real position.
- If the best attack scores at least 4, it moves there and attacks with the
  same synced attack command a player's click issues.
- Each unit is tried once per turn. All iteration is in a fixed order, so
  replays match.

## Flanking

Owner design, 2026-10-04: surrounding a target makes it easier to hit.

- **Rule:** when attacking, each unit hostile to the target that stands next
  to it on its far side gives +10% chance to hit, up to +20%. Far side means
  adjacent to the target and farther from the attacker than the target is.
  - For melee, that is the three hexes behind the target.
  - For a shot from 2+ hexes, it is the hexes behind the target along the
    line of fire.
- **Who counts:** only armed, non-petrified units. The attacker never counts.
- **Offense only:** flanking never applies to return fire.
- **Implementation:** the `sw_special_flanking` weapon special lives in the
  macro `SW_SPECIAL_FLANKING` (generated `units/00_sw_specials.cfg`). Every
  weapon of every unit type references it.
  - It uses two tiers (+10% and +20%), each a `[chance_to_hit]` special with a
    `[filter_opponent]` WFL formula, in the same style as mainline backstab.
  - The attack dialog therefore names the exact bonus. Both tiers have an
    empty `name_inactive`, so they are hidden when they do not apply.
  - WFL details, verified in the engine source:
    - Inside `filter()`/`map()`, `self`, `loc` and `other` resolve against
      the list element first, so the target and both hexes are bound up front
      with `sw_`-named `where` variables.
    - `and` evaluates both sides, so empty hexes are dropped before unit
      fields are read.
- **AI:** the stand-off ranged-fire action adds the same bonus
  (`flank_bonus`) to its expected-damage model.

## Tests

`run_systems_tests.py --suite air` checks, using the engine's combat
simulation and the weapons' range data:

- −10% to hit per hex;
- the 2-hex rifle limit;
- the aimed shot's +20% and one fewer strike, `min_range` 2, and no use in
  retaliation;
- pistols limited to 1 hex, and the DL-44 exception;
- the E-Web at 3 hexes and −20%;
- guided torpedoes without falloff;
- the range special being listed with the weapon;
- the AI's stand-off evaluation, and a real AI turn in which it fires on a
  pistol-armed target from 2 hexes.
- flanking: +10% for one far-side ally, +20% for two, capped at +20% with
  three; no bonus from allies beside the attacker or from a petrified unit;
  no bonus on return fire; +10% on a 2-hex shot; the AI model agrees.
