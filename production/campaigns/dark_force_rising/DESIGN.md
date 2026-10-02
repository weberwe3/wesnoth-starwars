# Campaign II — Dark Force Rising: Design Record

**Status:** owner-directed rebuild, design revision 1 (2026-10-02)
**Campaign id (unchanged):** `Star_Wars_Thrawn_Trilogy_Dark_Force_Rising`
**Define:** `CAMPAIGN_STAR_WARS_DARK_FORCE_RISING`

Built on the same systems as Campaign I (see
`production/campaigns/heir_to_the_empire/DESIGN.md`): generated maps and
roster, hero stash/restore, ysalamiri zones, space terrain, fixed side-1
`save_id`, explicit hero-death defeat. The placeholder scenarios
`sw_13_dark_force_rising_recon` … `sw_21_restore_the_beacon` are retired through
`tests/retired-content.json`.

All dialogue and story text is original. Legends names and concepts are used;
no prose or dialogue from the novels is quoted or closely paraphrased.

## 1. Story spine (broad plot concepts only)

- **Leia and the Noghri.** A captured Noghri commando, Khabarakh, brings Leia
  to his ruined homeworld, Honoghr. The Noghri revere the bloodline of Darth
  Vader; Leia must learn how the Empire has kept them in its service.
- **Luke and C'baoth.** Luke travels to Jomark, where a long-lost Jedi Master,
  Joruus C'baoth, offers to teach him. C'baoth is powerful and unstable.
- **Han, Lando, and Bel Iblis.** The search for the Katana fleet leads them to
  Senator Garm Bel Iblis and his private army.
- **The Dark Force.** Two hundred Dreadnaught cruisers lost before the Clone
  Wars drift in deep space. The New Republic, Bel Iblis, Karrde's smugglers,
  and Thrawn race to claim them.

## 2. New roster entries

| id | Name | Side | Role |
| --- | --- | --- | --- |
| `sw_hero_khabarakh` | Noghri Commando (Khabarakh) | ally | stealth hero, first captured, then ally |
| `sw_hero_cbaoth` | Jedi Master (Joruus C'baoth) | ally, then enemy | lightsaber, Force lightning (magical), Force healing |
| `sw_hero_bel_iblis` | Senator-General (Garm Bel Iblis) | ally | leadership, blaster |
| `sw_unit_bi_commando` | Corellian Commando | player | Bel Iblis's elite infantry |
| `sw_unit_im_clone_trooper` | Clone Stormtrooper | enemy | Thrawn's new clone soldiers: tougher stormtroopers |
| `sw_unit_im_decon_droid` | Decontamination Droid | enemy | slow, armored Honoghr droid |
| `sw_unit_ob_dreadnaught` | Katana Dreadnaught | neutral | derelict capital ship, captured by boarding |
| `sw_unit_nr_boarding_shuttle` | Boarding Shuttle | player | carries boarding crews to Dreadnaughts |
| `sw_unit_im_boarding_shuttle` | Imperial Assault Shuttle | enemy | Imperial boarding craft |

## 3. Missions

| # | id | Name | Map | T | POV |
| --- | --- | --- | --- | --- | --- |
| 1 | `sw_dfr_01_the_noghri_prisoner` | The Noghri Prisoner | Kashyyyk 24×18 | 12 | Leia, Chewbacca |
| 2 | `sw_dfr_02_honoghr` | Honoghr | blighted plain 28×18 | 16 | Leia, Chewbacca, Khabarakh |
| 3 | `sw_dfr_03_jomark` | Jomark | lake island 26×20 | 14 | Luke (C'baoth allied) |
| 4 | `sw_dfr_04_the_senators_men` | The Senator's Men | city 26×18 | 14 | Han, Lando |
| 5 | `sw_dfr_05_peregrines_nest` | The Peregrine's Nest | rock base 28×20 | 15 | Han, Lando, Bel Iblis |
| 6 | `sw_dfr_06_the_mad_jedi` | The Mad Jedi | lake and forest 28×18 | 14 | Luke, Mara |
| 7 | `sw_dfr_07_the_dark_force` | The Dark Force | deep space 30×22 | 16 | Wedge, Luke |
| 8 | `sw_dfr_08_aboard_the_katana` | Aboard the Katana | ship interior 26×18 | 16 | Luke, Han, Lando, Chewbacca |
| 9 | `sw_dfr_09_battle_for_the_fleet` | Battle for the Fleet | deep space 30×22 | 16 | Wedge, Luke, Bel Iblis |
| 10 | `sw_dfr_10_honoghrs_choice` | Honoghr's Choice | Nystao 26×18 | 14 | Leia, Chewbacca, Khabarakh |

### 1. The Noghri Prisoner
Another Noghri team comes for Leia on Kashyyyk. This time she wants one alive.
- Win: capture Khabarakh by reducing him to a third of his hit points or less.
- Lose: Khabarakh is killed; Leia or Chewbacca dies; turns run out.

### 2. Honoghr
Khabarakh guides Leia across his blighted world. Imperial decontamination
droids patrol the brown plains; the Noghri clans watch.
- Win: Leia reaches the clan house (dukha) at Nystao.
- Lose: Leia, Chewbacca, or Khabarakh dies; turns run out.

### 3. Jomark
On Jomark, C'baoth asks Luke to help drive off raiders who have landed on the
lake shore. C'baoth fights beside him, too eagerly.
- Win: defeat the raid leader, with at least two of the three villages unharmed.
- Lose: Luke dies; two villages are taken.

### 4. The Senator's Men
Han and Lando, chasing a lead on the Katana fleet, are cornered by Imperial
agents. Unexpected help arrives.
- Win: reach the landing pad; Bel Iblis's commandos join on turn 4.
- Lose: Han or Lando dies; turns run out.

### 5. The Peregrine's Nest
Bel Iblis's hidden base is found by the Empire. Hold the shield generator.
- Win: hold the generator hex through the last turn, or defeat the commander.
- Lose: an Imperial unit occupies the generator; Han, Lando, or Bel Iblis dies.

### 6. The Mad Jedi
Luke realizes that C'baoth intends to bend him. Mara Jade arrives with a
warning and a ship. C'baoth calls storms over the lake.
- Win: Luke and Mara reach Mara's ship.
- Lose: Luke or Mara dies; turns run out.
- Beat: every second turn C'baoth's Force storm strikes a random band of hexes.

### 7. The Dark Force
The Katana fleet is found. Boarding shuttles must reach the drifting
Dreadnaughts before the Empire's do.
- Win: secure three Dreadnaughts (a boarding shuttle ends its move next to one).
- Lose: the Empire secures four Dreadnaughts; Wedge or Luke dies; turns run out.

### 8. Aboard the Katana
Inside the flagship, clone stormtroopers fight for every corridor.
- Win: Luke reaches the bridge.
- Lose: Luke, Han, Lando, or Chewbacca dies; turns run out.

### 9. Battle for the Fleet
Thrawn arrives in force. Escort the captured Dreadnaughts to the jump point.
- Win: two Dreadnaughts reach the eastern edge.
- Lose: all captured Dreadnaughts are destroyed; Wedge, Luke, or Bel Iblis dies.

### 10. Honoghr's Choice
Leia returns to Honoghr with the truth about the decontamination droids. An
Imperial detachment comes to take her. The Noghri must choose.
- Win: survive until the clans rise (final turn) or defeat the detachment.
- Lose: Leia, Chewbacca, or Khabarakh dies.
- Ending: the Noghri renounce their service to the Empire. Hook for Campaign III.
