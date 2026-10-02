# Campaign I — Heir to the Empire: Design Record

**Status:** owner-directed rebuild, design revision 1 (2026-10-01)
**Campaign id (unchanged, save compatible):** `Star_Wars_Thrawn_Trilogy`
**Define:** `CAMPAIGN_STAR_WARS_THRAWN_TRILOGY`
**Engine target:** Wesnoth 1.19.27 (forward: 1.20)

The owner directed on 2026-10-01 that Campaign I be rebuilt to a real
production standard before Campaigns II and III: proper-size maps, named
Legends-era characters, a coherent faction roster, and original dialogue.
The earlier placeholder Campaign I scenarios (`01_First_Battle` …
`sw_12_breakout_at_the_rendezvous`) are retired through
`addons/Star_Wars_Thrawn_Trilogy/tests/retired-content.json`; their history
remains in Git. Campaign II's existing scenarios are untouched by this record.

All dialogue, descriptions, and story text are newly written for this add-on.
They use authentic Legends names and terminology but do not quote or closely
paraphrase any novel, film, script, or game.

## 1. Story spine (broad plot concepts only)

Five years after Endor, a Grand Admiral returns from the Unknown Regions and
takes command of the Imperial Remnant. The New Republic, still learning to
govern, faces a commander who studies a species' art to predict its tactics.
Campaign I follows three threads that converge:

1. **Thrawn's preparation** — ysalamiri from Myrkr to blunt the Jedi; a hunt
   for mole miners; a strike on the Sluis Van shipyards.
2. **Leia, Han, and Chewbacca** — pursued by Noghri commandos who want Leia
   alive; a refuge on Kashyyyk.
3. **Luke Skywalker** — stranded, then captive among Talon Karrde's smugglers
   on Myrkr, where Force-repelling ysalamiri leave him without the Force; an
   uneasy escape with Mara Jade, who has her own reasons to want him dead.

The campaign ends with Thrawn's shipyard gambit at Sluis Van foiled — at a
cost — and the first hint of a lost Dreadnaught fleet (Campaign II hook).

## 2. Systems used in Campaign I

| System | Implementation | Notes |
| --- | --- | --- |
| Blasters | `fire` damage, mostly `range=ranged` adjacent attacks | Unit help explains blaster bolts as fire damage. |
| Heavy weapons | E-Web and AT-ST cannons may use `max_range=2` | 1.19.27 supports multi-hex attacks (`src/actions/attack.cpp`); the default AI does not plan them, so long range is limited to player units and a few static emplacements. |
| Lightsaber | `arcane` melee, high strikes | Vehicles and droids take extra arcane damage via negative resistance. |
| Deflection | defensive-only ranged attack (`[disable] active_on=offense`) | Lets Jedi return blaster fire only when shot at. |
| Ion weapons | `cold` damage + `slows` | Strong vs vehicles and starfighters. |
| Force abilities | WML abilities with a `[filter]` that excludes ysalamiri zones | Luke's Force abilities and deflection fail inside the zone. |
| Ysalamiri zone | scenario variable `sw_ysalamiri_zone` (location list) | Myrkr scenarios mark the bubbles on the map with labels and halo. |
| Noghri | `ambush` + `nightstalk` + `backstab` | Vulnerable once revealed; Wookiee lookouts reveal them on Kashyyyk. |
| Space | custom terrain `Qsp` (open space) and `Qsp^Xsa` (asteroids) | Only starfighter/spacecraft movetypes can enter open space. |
| Heroes | named units with `canrecruit` only where leading | Absent heroes are stored away and restored between missions (`SW_STASH_HEROES` / `SW_RESTORE_HEROES`). |
| Difficulty | `[difficulty]` EASY / NORMAL / HARD with `{QUANTITY}` | |

## 3. Factions and roster (Campaign I)

Unit ids use the `sw_unit_` prefix; player-facing names are lore names.

### New Republic (player)

| id | Name | L | Role |
| --- | --- | --- | --- |
| `sw_unit_nr_trooper` | New Republic Trooper | 1 | line infantry, blaster rifle |
| `sw_unit_nr_sergeant` | New Republic Sergeant | 2 | leadership, advances from Trooper |
| `sw_unit_nr_commando` | New Republic Commando | 1 | skirmisher, scout |
| `sw_unit_nr_eweb_team` | E-Web Heavy Weapons Team | 1 | slow, `max_range=2` heavy repeating blaster |
| `sw_unit_nr_field_medic` | Field Medic | 1 | heals +4 |
| `sw_unit_nr_xwing` | X-wing Starfighter | 1 | space: lasers + proton torpedoes |
| `sw_unit_nr_awing` | A-wing Interceptor | 1 | space: fast, fragile |
| `sw_unit_nr_ywing` | Y-wing Bomber | 1 | space: ion cannon (slows), torpedoes |
| `sw_unit_nr_militia` | Planetary Militia | 0 | allied local defenders |
| `sw_unit_wk_warrior` | Wookiee Warrior | 1 | bowcaster, forest specialist |
| `sw_unit_wk_lookout` | Wookiee Lookout | 1 | reveals hidden units nearby |

### Heroes

| id | Name | Notes |
| --- | --- | --- |
| `sw_hero_luke` | Luke Skywalker | Jedi Knight; lightsaber, deflection, Force abilities |
| `sw_hero_leia` | Leia Organa Solo | leadership, blaster; Noghri objective target |
| `sw_hero_han` | Han Solo | heavy blaster pistol with first strike |
| `sw_hero_chewbacca` | Chewbacca | bowcaster, Wookiee strength |
| `sw_hero_lando` | Lando Calrissian | leadership, blaster |
| `sw_hero_mara` | Mara Jade | ally in Myrkr; blaster + vibroblade, ambush |
| `sw_hero_karrde` | Talon Karrde | smuggler leader, ally |
| `sw_hero_wedge` | Wedge Antilles | X-wing ace (space missions) |
| `sw_hero_xwing_luke` | Luke Skywalker (X-wing) | space form used in mission 3 |

### Imperial Remnant (enemy; player in mission 1)

| id | Name | L | Role |
| --- | --- | --- | --- |
| `sw_unit_im_stormtrooper` | Stormtrooper | 1 | armored line infantry |
| `sw_unit_im_stormtrooper_sergeant` | Stormtrooper Sergeant | 2 | leadership |
| `sw_unit_im_scout_trooper` | Scout Trooper | 1 | speeder bike, fast on open ground |
| `sw_unit_im_officer` | Imperial Officer | 2 | leader, leadership |
| `sw_unit_im_at_st` | AT-ST Walker | 2 | armored, weak to ion and lightsaber |
| `sw_unit_im_noghri` | Noghri Commando | 2 | ambush, nightstalk, backstab |
| `sw_unit_im_tie_fighter` | TIE Fighter | 1 | space: fast, fragile |
| `sw_unit_im_tie_interceptor` | TIE Interceptor | 2 | space: faster, harder hitting |
| `sw_unit_im_tie_bomber` | TIE Bomber | 1 | space: bombs vs. stations/capital ships |
| `sw_unit_im_mole_miner` | Hijacked Mole Miner | 1 | objective unit; plasma cutters |
| `sw_unit_im_star_destroyer` | Imperial Star Destroyer | 4 | space set piece; turbolasers |
| `sw_hero_pellaeon` | Captain Gilad Pellaeon | 3 | Imperial commander |
| `sw_hero_thrawn` | Grand Admiral Thrawn | 4 | appears in briefings and the finale |

### Smugglers and wildlife

| id | Name | L | Role |
| --- | --- | --- | --- |
| `sw_unit_sm_smuggler` | Karrde's Smuggler | 1 | blaster, quick |
| `sw_unit_sm_veteran` | Smuggler Veteran | 2 | marksman blaster |
| `sw_unit_wl_vornskr` | Vornskr | 1 | Myrkr predator, bonus vs. Force-sensitives |

### Infrastructure / set pieces

| id | Name | Role |
| --- | --- | --- |
| `sw_unit_nr_docked_warship` | Docked Warship | immobile objective in Sluis Van |
| `sw_unit_ob_ysalamiri_frame` | Ysalamiri Nutrient Frame | immobile, carried objective marker on Myrkr |

## 4. Missions

Map sizes are playable areas (excluding the border). `T` = turn limit
(Normal). Every mission has one primary objective, defeat conditions, and at
least one scripted beat.

| # | id | Name | Map | T | POV |
| --- | --- | --- | --- | --- | --- |
| 1 | `sw_hte_01_ysalamiri_harvest` | The Grand Admiral's Harvest | Myrkr forest 26×18 | 16 | Imperial |
| 2 | `sw_hte_02_ambush_at_bpfassh` | Ambush at Bpfassh | city/plaza 26×18 | 14 | Leia, Han, Chewbacca |
| 3 | `sw_hte_03_adrift` | Adrift | deep space 22×16 | 10 | Luke (X-wing) |
| 4 | `sw_hte_04_shadows_of_kashyyyk` | Shadows of Kashyyyk | wroshyr forest 26×20 | 14 (night) | Leia, Chewbacca |
| 5 | `sw_hte_05_prisoner_of_myrkr` | Prisoner of Myrkr | smuggler compound 24×18 | 14 | Luke |
| 6 | `sw_hte_06_raid_on_karrdes_base` | Raid on Karrde's Base | compound + forest 28×20 | 15 | Han, Lando, Karrde |
| 7 | `sw_hte_07_the_forest_crossing` | The Forest Crossing | Myrkr forest 30×20 | 18 | Luke, Mara |
| 8 | `sw_hte_08_nomad_city` | Nomad City | Nkllon sunside 28×18 | 14 | Han, Lando |
| 9 | `sw_hte_09_sluis_van_shipyards` | The Sluis Van Shipyards | orbital 28×20 | 14 | Wedge, Lando |
| 10 | `sw_hte_10_thrawns_gambit` | Thrawn's Gambit | orbital 30×22 | 18 | full party |

### 1. The Grand Admiral's Harvest (Imperial prologue)
Captain Pellaeon's landing party must collect four ysalamiri nutrient frames
from marked trees in the Myrkr forest and return them to the Lambda shuttle.
Vornskr packs attack; Karrde's smugglers watch from a neutral camp and must
not be provoked (attacking them is a defeat). Teaches movement, forests,
villages, recruiting, and objectives. Thrawn comments by hologram.
- Win: all four frames delivered to the shuttle hex.
- Lose: Pellaeon dies; turns run out; a smuggler is attacked.

### 2. Ambush at Bpfassh
An Imperial hit-and-run raid strikes Bpfassh while Leia meets local leaders.
Noghri commandos move to seize Leia in the confusion. Han and Chewbacca must
get her across the city to the Millennium Falcon's landing pad while the
militia holds the plaza.
- Win: Leia reaches the Falcon (hex marked) — Han and Chewbacca must be alive.
- Lose: Leia, Han, or Chewbacca dies; turns run out.
- Beats: turn 3 TIE strafing run (off-map strike damages a row), Noghri
  reveal when adjacent, militia reinforcements on turn 5.

### 3. Adrift
Luke's X-wing is pulled out of hyperspace by a gravity-well trap and a TIE
patrol. His hyperdrive is damaged. Survive until the freighter *Wild Karrde*
arrives; destroy the patrol for a bonus.
- Win: survive to the final turn (the *Wild Karrde* takes the X-wing aboard).
- Bonus: destroy every TIE (carryover gold bonus).
- Lose: Luke's X-wing is destroyed.

### 4. Shadows of Kashyyyk
Leia and Chewbacca take refuge on Kashyyyk. Noghri commandos stalk them through
the wroshyr branches at night. Wookiee lookouts reveal hidden Noghri.
- Win: defeat all Noghri, or survive until dawn (final turn).
- Lose: Leia dies; Chewbacca dies.

### 5. Prisoner of Myrkr
Karrde holds Luke in a compound surrounded by ysalamiri. Without the Force,
Luke must slip past guards, recover his lightsaber from Karrde's office, and
reach the vehicle shed.
- Win: Luke reaches the vehicle shed with his lightsaber recovered.
- Lose: Luke dies; turns run out.
- Beat: once the lightsaber is recovered, Mara Jade raises the alarm.

### 6. Raid on Karrde's Base
Han and Lando have come to Myrkr looking for Luke. An Imperial assault force
arrives hunting for him too. Help Karrde's people evacuate before the
compound falls.
- Win: six evacuees (or all surviving Karrde units) reach the transports, and
  Han and Lando escape.
- Lose: Han, Lando, or Karrde dies; turns run out.

### 7. The Forest Crossing
Luke and Mara, crash-landed together, must cross the Myrkr forest to Hyllyard
City while stormtroopers on speeder bikes and vornskr packs hunt them. Inside
ysalamiri bubbles Luke has no Force abilities.
- Win: both reach Hyllyard City.
- Lose: Luke or Mara dies; turns run out.

### 8. Nomad City
On the scorching world Nkllon, Lando's mobile mining city is raided by
Imperial teams stealing mole miners. Sunside hexes burn units that end their
turn there unexposed to shade (shadow hexes protect).
- Win: fewer than three mole miners stolen by the final turn, or all raiders
  destroyed.
- Lose: three mole miners reach the extraction zone; Han or Lando dies.

### 9. The Sluis Van Shipyards
Thrawn's TIE fighters escort hijacked mole miners toward warships docked at
Sluis Van. Destroy the mole miners before they cut into the warships.
- Win: all mole miners destroyed.
- Lose: two warships captured (a mole miner ends its turn adjacent to a
  warship for two turns); Wedge dies.

### 10. Thrawn's Gambit
The Chimaera's task force commits to the attack. Hold the shipyards, destroy
the Imperial strike group's escorts, and force the Grand Admiral to withdraw.
- Win: destroy the strike carrier group (marked targets) or hold until the
  final turn with at least one warship intact.
- Lose: all warships lost; Wedge or Luke dies.
- Ending: Thrawn withdraws; a closing exchange mentions a lost fleet of
  Dreadnaughts — hook for Campaign II.

## 5. Carryover and hero state

- Side 1's recall list carries heroes and veterans. Each mission recalls the
  heroes it needs by id and stores the others with `SW_STASH_HEROES`, then
  restores them at victory with `SW_RESTORE_HEROES`.
- Mission 1 (Imperial POV) uses a separate side-1 roster that is discarded at
  victory; mission 2 creates the New Republic heroes when absent.
- Gold carryover uses Wesnoth's default 40% (`carryover_percentage`).
- Campaign variables: `sw_hte_bonus_*` record optional objectives and adjust
  later missions' starting gold.

## 6. Acceptance and evidence

Each mission needs, in the installed engine:

1. preprocess + campaign load with no WML errors;
2. a staged runtime probe proving the scenario starts with its units;
3. a legal-route or event probe for its victory path and each defeat;
4. GUI campaign entry under the Linux virtual-display harness;
5. a campaign-sequence probe proving each transition and hero carryover.

Art: each new unit gets a 13-state art-queue job generated by Codex through
the dashboard's art workflow. Until a job completes, a unit uses an original
procedural placeholder sprite.
