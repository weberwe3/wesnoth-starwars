# Campaign III — The Last Command: Design Record

**Status:** new campaign, design revision 1 (2026-10-02)
**Campaign id:** `Star_Wars_Thrawn_Trilogy_The_Last_Command`
**Define:** `CAMPAIGN_STAR_WARS_THE_LAST_COMMAND`

Built on the shared systems of Campaigns I and II (generated maps and roster,
hero stash/restore, ysalamiri zones, space terrain, fixed side-1 `save_id`,
explicit hero-death defeat). All dialogue and story text is original; Legends
names and broad plot concepts only.

## 1. Story spine (broad plot concepts only)

- The Grand Admiral besieges Coruscant, seeding its orbit with cloaked
  asteroids so that no ship can safely come or go.
- Talon Karrde tries to unite the fringe's smugglers against the Empire.
- Leia, now mother of twins, is targeted inside the Imperial Palace.
- Luke and Mara Jade travel to Wayland, where the Emperor's storehouse at
  Mount Tantiss holds Thrawn's cloning cylinders, and where Joruus C'baoth now
  rules with a clone of Luke.
- The New Republic strikes Thrawn's shipyards at Bilbringi. The battle ends
  when the Grand Admiral's own bodyguard turns on him; Captain Pellaeon orders
  the retreat.

## 2. New roster entries

| id | Name | Side | Role |
| --- | --- | --- | --- |
| `sw_hero_luuke` | Dark Clone (Luuke) | enemy | C'baoth's clone of Luke: lightsaber, Force lightning |
| `sw_unit_wy_myneyrshi` | Myneyrshi Warrior | ally | four-armed Wayland native with spear and bow |
| `sw_unit_wy_psadan` | Psadan Elder | ally | armored, slow Wayland native |
| `sw_unit_ob_cloaked_asteroid` | Cloaked Asteroid | hazard | hidden; damages ships that end their move next to it |
| `sw_unit_ob_shield_generator` | Shield Generator | objective | immobile structure |
| `sw_unit_ob_cloning_cylinder` | Cloning Cylinder | objective | immobile structure |
| `sw_unit_im_royal_guard` | Imperial Guard | enemy | elite crimson-robed guards of Mount Tantiss |

## 3. Missions

| # | id | Name | Map | T | POV |
| --- | --- | --- | --- | --- | --- |
| 1 | `sw_tlc_01_the_siege_of_coruscant` | The Siege of Coruscant | orbital 30×22 | 16 | Wedge, Luke |
| 2 | `sw_tlc_02_the_smugglers_council` | The Smugglers' Council | fortress 26×20 | 15 | Karrde, Mara |
| 3 | `sw_tlc_03_the_palace_infiltrators` | The Palace Infiltrators | palace 26×18 | 14 | Leia, Chewbacca, Khabarakh |
| 4 | `sw_tlc_04_landfall_on_wayland` | Landfall on Wayland | jungle 28×20 | 16 | Luke, Mara |
| 5 | `sw_tlc_05_the_natives_of_wayland` | The Natives of Wayland | jungle and hills 28×20 | 15 | Luke, Mara |
| 6 | `sw_tlc_06_the_gates_of_tantiss` | The Gates of Mount Tantiss | mountain base 28×20 | 16 | Han, Lando, Chewbacca, Leia |
| 7 | `sw_tlc_07_the_cloning_vats` | The Cloning Vats | interior 26×18 | 16 | Han, Lando, Chewbacca |
| 8 | `sw_tlc_08_the_throne_room` | The Throne Room | throne room 20×16 | 14 | Luke, Mara |
| 9 | `sw_tlc_09_bilbringi` | The Bilbringi Shipyards | orbital 30×22 | 16 | Wedge, Ackbar's fleet |
| 10 | `sw_tlc_10_the_last_command` | The Last Command | orbital 30×22 | 18 | full party |

### 1. The Siege of Coruscant
Imperial ships are seeding Coruscant's orbit with cloaked asteroids. Destroy
the minelayer group before the cordon is complete.
- Win: destroy the two Imperial minelayers.
- Lose: Wedge or Luke dies; turns run out.
- Hazard: hidden asteroids damage any ship that ends its move next to one.

### 2. The Smugglers' Council
Karrde gathers the fringe's smuggler chiefs at an old fortress. Imperial
forces arrive to break up the meeting.
- Win: hold until the last turn with at least three chiefs alive, or defeat
  the Imperial commander.
- Lose: Karrde or Mara dies; three chiefs are killed.

### 3. The Palace Infiltrators
Imperial commandos slip into the Imperial Palace to take Leia's newborn twins.
- Win: defeat every infiltrator.
- Lose: an infiltrator reaches the nursery; Leia, Chewbacca, or Khabarakh dies.

### 4. Landfall on Wayland
Luke and Mara crash-land near Mount Tantiss and must reach the river crossing
through jungle patrolled by the garrison.
- Win: both reach the river crossing.
- Lose: Luke or Mara dies; turns run out.

### 5. The Natives of Wayland
The Myneyrshi and Psadan peoples distrust all outsiders. Prove the Empire is
the common enemy by breaking the garrison outpost that oppresses them.
- Win: destroy the outpost commander; natives join from turn 4.
- Lose: Luke or Mara dies.

### 6. The Gates of Mount Tantiss
Han, Lando, Chewbacca, and Leia (with Noghri) assault the mountain entrance.
- Win: destroy the shield generator.
- Lose: Han, Leia, or Chewbacca dies; turns run out.

### 7. The Cloning Vats
Inside the mountain, wreck the cloning cylinders before the garrison seals
the chamber.
- Win: destroy all cloning cylinders.
- Lose: Han, Lando, or Chewbacca dies; turns run out.

### 8. The Throne Room
Luke and Mara confront C'baoth and his dark clone of Luke.
- Win: defeat Luuke and C'baoth.
- Lose: Luke or Mara dies.
- Note: Mara deals extra damage to Luuke; C'baoth's Force abilities fail
  inside the ysalamiri that Mara brings.

### 9. The Bilbringi Shipyards
The New Republic fleet strikes Thrawn's shipyard. Clear the cloaked-asteroid
screen and destroy the shipyard platforms.
- Win: destroy three shipyard platforms.
- Lose: Wedge dies; turns run out.

### 10. The Last Command
Thrawn commits his fleet. Hold until the Grand Admiral's plan collapses.
- Win: survive until the scripted turn when Thrawn falls and Pellaeon orders
  the retreat, or destroy the Chimaera's escorts.
- Lose: Wedge, Luke, or Mara dies.
- Ending: Rukh's betrayal; Pellaeon's retreat; the trilogy closes.
