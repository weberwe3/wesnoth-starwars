# Fan sprite references and their licence confirmation

**Status 2026-10-04:** the project owner reports permission from every artist
in the table below. The images are stored outside the repository in
`~/art-references/`, and `production/tools/reference_sprite_map.json` maps
them to units. `gen_codex_reference_frames.py --mode reference` redraws or
restyles them in the house style (the SacraiCross sheet sprites). Credits are
added to the add-on (README, campaign credits, `docs/ART_CREDITS.md`) for
each unit whose art is installed from them.

The search notes below are kept for the record.

Searched 2026-10-04 for fan pixel sprites of units that the SacraiCross
"Star Wars Collection - Complete v6" sheet does not cover (or covers but could
not be cut out cleanly). No candidate carries a standard open licence (CC0,
CC BY, CC BY-SA or GPL) that the Wesnoth add-on server accepts. Each needs the
artist's written confirmation, preferably of CC BY-SA, before any of it is
used, even as a reference that Codex restyles. Until then the units keep their
current art.

Confirmation to ask for: "May the sprites be used, recoloured and animated in
a free Battle for Wesnoth add-on, published under CC BY-SA with credit to
you?"

| Units | Candidate | Artist | Stated terms | Notes |
|---|---|---|---|---|
| Thrawn (and any other SacraiCross sprite) | [Tarot Star Wars](https://www.deviantart.com/sacraicross/art/Tarot-Star-Wars-852691763) and the rest of the [SacraiCross gallery](https://www.deviantart.com/sacraicross/gallery) | SacraiCross | None on the page (all rights reserved). The owner's permission was given for the v6 sheet. | Best fit: same artist and style. Ask whether the permission covers the whole gallery. The Tarot card version of Thrawn may be easier to cut out than the one on the marble sheet. |
| Clone trooper | [Ph 1 Clone troopers sheet](https://www.deviantart.com/middytheknight/art/READ-THE-DESC-Ph-1-Clone-troopers-sheet-PD-714368412) | MiddytheKnight (sprites by zerorunner67) | "Public domain", but credit is required and recolouring is allowed. | Informal terms, so confirm CC BY-SA, with zerorunner67 as well. Prequel-era armour, smaller and in a different style. |
| Scout trooper | [Imperial Scout Trooper](https://www.deviantart.com/milosh--andrich/art/Star-wars-Imperial-Scout-Trooper-511887221) | Milosh--Andrich | "But credit me"; no licence. | Thanks two collaborators (Tounushi, elMengu), who may also need to agree. |
| Rebel and smuggler extras (militia, crews) | [Pixel Star Wars Original Trilogy sprites part 1](https://www.deviantart.com/mudkat101/art/Pixel-Star-Wars-Original-Trilogy-sprites-PART-1-611895035) | mudkat101 | None (all rights reserved). | Covers the same cast as the sheet. Only useful for variants. |
| X-wing, Y-wing, TIE fighter | [Star Wars Ship sprites (1 px = 1 m)](https://www.deviantart.com/silent-drew/art/Star-Wars-Ship-sprites-1-px-1-Meter-819078778) | silent-Drew | None (all rights reserved). | Top-down view; our units use a three-quarter view, so these would be references only. |
| Noghri, Khabarakh | [Noghri](https://www.deviantart.com/codemus/art/Noghri-596303698) | Codemus | Not checked; DeviantArt default is all rights reserved. | An illustration, not a sprite; reference only. |

Openly licensed but not a good fit: the CC0
[retro FPS "Storm Trooper"](https://whiteknightstudios.itch.io/old-school-fps-8d-trooper-v3)
by W_K_Studio. It is usable without confirmation, but it is a 512 px
first-person-shooter sprite in a very different style. OpenGameArt has only
generic sci-fi soldiers and ships.

No fan sprites were found for the vornskr, Myneyrshi, Psadan, the
decontamination droid, the E-Web team, the infiltrator or the remaining ships
and objects.

## Ship references (owner-confirmed permission, 2026-10-04)

**Status:** the owner reports permission for every ship candidate below, and
for a Y-wing 3D model render by Welljinco on TurboSquid (stored as `turbosquid-ywing.jpg`)
as a pixel-art template. Queued: TIE fighter (danyelon), X-wing for
`sw-unit-nr-xwing`, `sw-hero-wedge` and `sw-hero-xwing-luke` (danyelon), A-wing
(Interdictorssd) and Y-wing (TurboSquid render). The others are stored in
`~/art-references/` as alternatives.

The owner judged the silent-Drew top-down ships too low quality, so the craft
units (`reference_sprite_map.json`, marked "hold") are on hold. These
higher-quality candidates are waiting for the owner to confirm their licences.
Local previews are in `~/art-preview/ship-candidates/` (`preview.png` is
numbered to match this table).

| # | Ships | Candidate | Artist | Stated terms |
|---|---|---|---|---|
| 1 | TIE fighter, X-wing (Millennium Falcon also shown) | [Star Wars Ships Pixel Art 8Bit](https://www.deviantart.com/danyelon/art/Star-Wars-Ships-Pixel-Art-8Bit-622959756) | danyelon | None on the page; another work by the artist is CC BY-NC-ND 3.0. The best fit: detailed three-quarter views. |
| 2 | TIE fighter | [TIE Fighter pixel art animation](https://www.deviantart.com/aet-obli/art/Star-Wars-TIE-Fighter-Pixel-art-animation-891753455) | Aet-Obli | CC BY-NC-SA 3.0. The server cannot accept the NonCommercial condition, so ask for CC BY-SA. Three-quarter view, animated. |
| 3 | X-wing | [Pixel X-Wing](https://www.deviantart.com/kyleandreigames/art/Pixel-X-Wing-Star-Wars-Fanart-915165018) | kyleandreigames | None (all rights reserved). Three-quarter view, inside a poster. |
| 4 | X-wing | [X-Wing Fighter Pixel Art](https://www.deviantart.com/rockyfirewolf/art/X-Wing-Fighter-Pixel-Art-678898823) | RockyFirewolf | None (all rights reserved). Large and detailed, rear and above view. |
| 5 | X-wing | [X-Wing Sprite](https://www.deviantart.com/interdictorssd/art/X-Wing-Sprite-853667979) | Interdictorssd | None (all rights reserved). Detailed, top-down. |
| 6 | A-wing | [A-Wing Sprite](https://www.deviantart.com/interdictorssd/art/A-Wing-Sprite-853668071) | Interdictorssd | None (all rights reserved). Detailed, top-down. |
| 7 | TIE fighter | [Pixel Tie Fighter](https://www.deviantart.com/x-tender/art/Pixel-Tie-Fighter-17778282) | x-tender | None on this piece. Detailed front view. |
| 8 | TIE Advanced (Vader's) | [Pixel Darth Vaders Tie Fighter](https://www.deviantart.com/x-tender/art/Pixel-Darth-Vaders-Tie-Fighter-31774138) | x-tender | CC BY-SA 3.0, usable with credit. It is not a standard TIE fighter, so it is a reference only. |
| - | Y-wing | [Star Wars - Y-Wing](https://pixeljoint.com/pixelart/14475.htm) | Darth Mandarb | Not checked; PixelJoint blocks automated access. An isometric 49-colour piece, not in the preview. |

## Reference candidates for the remaining old-style characters (2026-10-06)

None of these has been used before. Local previews are in
`~/art-preview/ref-candidates/`; `preview.png` is numbered to match this table.
SacraiCross sheets fall under the owner's existing gallery-wide permission and
are already in the house style. Every other candidate states no reuse licence
on its page (some DeviantArt pages show unrelated Creative Commons boilerplate,
which does not apply to the artwork), so each needs the owner's confirmation.

| # | Unit | Candidate | Artist | Licence |
|---|---|---|---|---|
| 1 | Imperial Infiltrator | [Fan Art 190 (Outlaws)](https://www.deviantart.com/sacraicross/art/Fan-Art-190-Star-Wars-Outlaws-968460358), the hooded, masked gunman | SacraiCross | Gallery permission |
| 2 | Decontamination Droid | [Star Wars Sanitation Droids](https://www.deviantart.com/wobbley/art/Star-Wars-Sanitation-Droids-944282255) (26 utility droid designs; also [Cleaning Droids](https://www.deviantart.com/wobbley/art/Star-Wars-Cleaning-Droids-992349603)) | Wobbley | All rights reserved; needs confirmation (preview needs a DeviantArt login) |
| 2b | Decontamination Droid (alternative) | [Fan Art 214 (Comics)](https://www.deviantart.com/sacraicross/art/Fan-Art-214-%28Star-Wars---Comics%29-1362896118), the heavy-legged droid | SacraiCross | Gallery permission |
| 3 | Recon Squad (and Thrawn Phalanx) | [Fan Art 121](https://www.deviantart.com/sacraicross/art/Fan-Art-121-Star-Wars-Empire-Solo-and-Rogue-One-879476676), the caped, gas-masked swamp trooper | SacraiCross | Gallery permission |
| 4 | Signal Jammer Team | Fan Art 121, the fur-lined range trooper | SacraiCross | Gallery permission |
| 5 | Combat Engineer Squad | [Fan Art 210 (Andor)](https://www.deviantart.com/sacraicross/art/Fan-Art-210-%28Star-Wars---Andor%29-1203872550), the orange-jumpsuit mechanic | SacraiCross | Gallery permission |
| 6 | E-Web Heavy Weapons Team | [Fan Art 60 (Rebels)](https://www.deviantart.com/sacraicross/art/Fan-Art-60-Star-Wars-Rebels-856873823), the large helmeted trooper as the crew; no E-Web gun sprite found | SacraiCross | Gallery permission |
| 7 | Heavy Weapons Squad | [Fan Art 99 (Bad Batch)](https://www.deviantart.com/sacraicross/art/Fan-Art-99-Star-Wars-The-Bad-Batch-871163441), the heavy-weapons specialist (clone armour, needs restyling as a New Republic soldier) | SacraiCross | Gallery permission |
| 8 | Republic Commander | [Fan Art 179 (Andor)](https://www.deviantart.com/sacraicross/art/Fan-Art-179-Star-Wars-Andor-934685160), the long-coated leader or the blue-uniformed officer | SacraiCross | Gallery permission |
| 9 | Slicer Team | Fan Art 99, the goggled tech specialist | SacraiCross | Gallery permission |
| 10 | Vornskr | [The Chiss and the Vornskr spirit](https://www.deviantart.com/dimorali/art/The-Chiss-and-the-Vornskr-spirit-880905662) | dimorali | All rights reserved; needs confirmation |
| 10b | Vornskr (alternative) | [Vornskr](https://www.deviantart.com/tactical-sandwiches/art/Vornskr-120769260), a photo manipulation | Tactical-Sandwiches | All rights reserved; needs confirmation |
| 11 | Myneyrshi Warrior | [Myneyrsh](https://www.deviantart.com/codemus/art/Myneyrsh-595307486) | Codemus | Owner's Codemus permission covered the Noghri; confirm it covers this piece |
| 12 | Psadan Elder | No fan art found; only the official West End Games sourcebook art (Lucasfilm copyright) | n/a | Not usable |
| 13 | Rifle Squad | Fan Art 60, the small helmeted fleet trooper | SacraiCross | Gallery permission |
