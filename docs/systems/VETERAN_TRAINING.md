# Veteran training

Terminal combat units need a reason to keep earning experience after their final
promotion. At a normal native advancement, their commander can now choose between
survivability, weapon discipline and better repositioning. The original
`AMLA_DEFAULT` remains first and retains its usual +3 maximum HP.

| Choice | Permanent benefit | Limit per unit |
| --- | --- | --- |
| Default AMLA | +3 maximum HP | Existing core limit (100) |
| Weapons drill (`sw_amla_weapons_drill`) | +1 damage per strike on every offensive weapon, including aimed variants | 2 |
| Mobility drill (`sw_amla_mobility_drill`) | +1 maximum movement; vision unchanged | 1 |

All choices use core `AMLA_EFFECTS_HEAL_AND_RAISE_XP`: full healing, poison and
slow removal, and +20% experience required for the next advancement. Native XP
rounding and carryover apply. Drills add no maximum HP, strikes, weapon range,
accuracy, resistance, income, attacks per turn or vision. The choice description
states the benefit, cure and XP cost. After all three drills, default AMLA remains
available. The caps bound the increase in damage and mobility while keeping the
long-term survivability path intact.

## Eligibility and generation

`production/tools/gen_hte_units.py` owns these definitions. Eligible units have no
promotion destination, positive movement and at least one damaging offensive
attack. Heroes, wildlife/creature types and objective objects are excluded even
when armed or technically mobile. Sentient alien soldiers (including Wookiees,
Noghri, Myneyrshi and Psadans), combat droids and piloted mobile craft qualify.
Unarmed transports and stationary structures do not. The attack effect explicitly
names the generated offensive weapons; defensive-only/zero-weight weapons and
zero-damage utilities are excluded. Aimed variants receive the same +1 as their
normal weapon, with no double application.

The generator emits the two native `[advancement]` blocks beside `AMLA_DEFAULT`
and uses `strict_amla=yes` and native `max_times`. Full rank variations are built
through the same `unit_wml` function, so their definitions are identical. Existing
rank code counts native advancement modifications, including drills, and
reapplies their effects when switching art. No base roster stat, promotion tree,
scenario, shared system Lua or generated output is hand-edited by this worker.

Native modification IDs persist in saves. Existing default AMLAs are neither
removed nor reinterpreted. Old saves can carry a cached list of the old unit's
advancement definitions; this change intentionally adds no save migration. A
normal engine rebuild/variation transition can refresh such definitions.

## Engine contract

The pre-code references are official [UnitTypeWML](https://wiki.wesnoth.org/UnitTypeWML),
[EffectWML](https://wiki.wesnoth.org/EffectWML) and
[Lua unit advancement](https://wiki.wesnoth.org/LuaAPI/wesnoth/units).
Installed 1.19.27 `data/core/macros/amla.cfg` supplies the heal/cure/+20% macro;
`src/units/unit.cpp::get_modification_advances` enforces limits before native
advancement. `apply_to=movement` defaults to also changing vision, so mobility
explicitly sets `apply_to_vision=no`.

## Coordinator validation

Workers must not execute commands after editing. The deterministic coordinator
should regenerate the roster, check generator freshness and run project static
gates, then run the dedicated fixture:

```sh
python3 production/tools/gen_hte_units.py
python3 production/tools/gen_hte_units.py --check
python3 production/linux_engine/veterancy_tests/run_veterancy_tests.py --output /tmp/sw-veterancy-evidence.json
python3 production/linux_engine/run_systems_tests.py --suite air
python3 production/linux_engine/run_campaign_sequence.py
```

The dedicated runner stages a disposable add-on copy and an isolated scenario,
then saves and reloads it in the actual engine. It checks raw generated options,
actual native advancement and cap rejection, exact damage/movement/vision,
healing and statuses, XP consumption/growth, rank II/III variation reapplication,
unchanged base stats, exclusion examples and persistence after save/load.
To select a choice deterministically without depending on GUI dialog handling,
the fixture temporarily offers only that unchanged native config and calls
`unit:advance(false,true)`. It restores the full choice list afterward. It never
uses `add_modification` to simulate an advancement or computes eligibility itself:
the engine must accept or reject the isolated choice using its native caps.

The main phase writes a real engine save; the reload phase launches a second
engine process with the bare save filename from its authoritative
`userdata/sync/saves` directory. Each plugin phase emits its completion marker
after its checks (and the main phase's save), then yields idle slices without
issuing further UI actions. The runner terminates its own disposable process
after observing completion; this owned post-completion SIGTERM/SIGKILL is an
expected harness shutdown, recorded in the JSON evidence. Every mandatory check
must still pass, and engine errors, missing completion markers, timeouts and
unexpected crashes remain failures. Unexpected exits retain the last 32,768
characters of raw engine log in the JSON report before temporary staging is
removed. This fixture validates native progression and real save/load; it does
not validate the game's interactive quit lifecycle.

Engine validation and playtesting are required before reporting these effects as
verified. Damage bonuses also apply on retaliation by the same offensive weapon,
as expected for permanent weapon training. AI picks among native choices using
the engine's existing advancement behavior; no new AI policy is introduced.
