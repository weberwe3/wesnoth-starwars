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
| Stormtrooper, Stormtrooper Sergeant, Clone Stormtrooper | blaster rifle | formation fire | +10% to hit while another stormtrooper of any kind is adjacent |
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
formation fire and pack tactics 70% vs 60%, including aimed shots, with no
bonus from an adjacent enemy; militia 5/6 vs 4/5 in a village; Lando 9 vs 6
on exactly the 60%+ terrains (village, castle). Balance with these traits has
not been playtested. Formation fire and pack tactics mostly help the enemy
AI, so Imperial infantry and TIE screens hit somewhat more often.

Not changed: the punching melee of the heroes (Leia, Lando, Karrde,
Pellaeon, Thrawn, Bel Iblis), the Imperial Officer, militia and E-Web crew.
Their melee frames show a punch, so a different melee weapon needs new attack
art first.
