# Signature weapon traits

Owner request (2026-10-13): units should fight in ways specific to their
role, not with a generic punch and shot. Each unit below gets one trait, a
weapon special on a weapon it already carries, at its base level. Under the
2026-10-12 unit rules no attack is added, and rank abilities
(`production/tools/rank_abilities.py`) are unchanged and do not overlap
these traits. They are defined in `SPECIALS` in
`production/tools/gen_hte_units.py`. Aimed-shot variants inherit them.

| Unit | Weapon | Trait | Effect |
| --- | --- | --- | --- |
| E-Web Heavy Weapons Team | E-Web repeating blaster | set up | +50% damage when attacking without having moved this turn |
| Stormtrooper, Stormtrooper Sergeant, Clone Stormtrooper | E-11 blaster rifle | attack formation | +10% to hit while another stormtrooper of any kind is adjacent |
| TIE Fighter, TIE Interceptor, TIE Bomber | laser cannons | pack tactics | +10% to hit while another TIE is adjacent |
| Planetary Militia | fists, blaster pistol | home ground | +25% damage while standing in a village or settlement |
| Lando Calrissian | blaster pistol | long odds | +50% damage against a target on terrain giving it 60% defence or more |

Engine facts relied on (Wesnoth 1.19.27 source):
- `set up` tests `moves >= max_moves`. `attack::perform` builds the battle
  context before it spends the attacker's movement, so the test sees the
  movement left before the attack. On defence the trait is inactive.
- `long odds` uses WFL `defense_on(self, loc)`, which returns the unit's
  defence percentage on its hex (`formula/function_gamestate.cpp`).

Verified 2026-10-13 with a throwaway engine probe (`wesnoth.simulate_combat`
on the Linux engine): E-Web 14 vs 9 damage set up vs moved, and 9 on defence;
attack formation (then called formation fire) and pack tactics 70% vs 60%, including aimed shots, with no
bonus from an adjacent enemy; militia 5/6 vs 4/5 in a village; Lando 9 vs 6
on exactly the 60%+ terrains (village, castle). Balance with these traits has
not been playtested. Formation fire and pack tactics mostly help the enemy
AI, so Imperial infantry and TIE screens hit somewhat more often.

Not changed: the punching melee of the heroes (Leia, Lando, Karrde,
Pellaeon, Thrawn, Bel Iblis), the Imperial Officer, militia and E-Web crew.
Their melee frames show a punch, so a different melee weapon needs new attack
art first.

## Lore weapons (2026-10-13)

Owner request: guns should vary by their Legends model so units play
differently. Each ranged weapon shows its model name, and models with a
known character get a profile to match. Attack ids are unchanged
(`blaster_rifle`, `blaster_pistol`, `heavy_blaster_pistol`), so sounds, icons,
ranges, overwatch, drills and rank abilities are unaffected. Units with no
clear canonical weapon keep a generic name rather than an invented model.

| Weapon | Carried by | Profile |
| --- | --- | --- |
| E-11 blaster rifle | Stormtrooper 5×4, Sergeant 7×4, Clone 6×4 (were 7×3, 9×3, 8×3) | rapid fire: more, lighter shots; attack formation |
| A280 blaster rifle | New Republic Trooper 7×3, Sergeant 9×3 | armour-piercing: +25% damage against armoured troopers |
| DH-17 blaster pistol | Field Medic 4×3 (was 5×2) | rapid-fire sidearm |
| Defender sporting blaster | Leia 6×3 (was 7×3) | precise: +10% chance to hit |
| DL-44 heavy blaster pistol | Han | unchanged (first strike, range 2) |
| SE-14 blaster pistol | Imperial Officer, Pellaeon, Thrawn | name only |
| DL-18 blaster pistol | Smuggler, Smuggler Veteran | name only |
| hold-out blaster | Smuggler Slicer, Imperial Infiltrator (Mara already had one) | name only |
| sporting blaster | Planetary Militia | name only (home ground) |

The A280 and E-11 set up a matchup: New Republic rifles hit stormtroopers
harder, while stormtroopers put out more, lighter shots and gain accuracy in
formation. `hero_threat_report.py --fail-on-flag` still flags no hero start
(68 checked).
