# Art credits

## SacraiCross character sprites (CC BY-SA)

Artist: SacraiCross. Source: "Star Wars Collection - Complete v6",
https://www.deviantart.com/sacraicross/art/Star-Wars-Collection---Complete-v6-941875516.
The artist told the project owner (weberwe3) that the sprites may be used with credit.
They are used under CC BY-SA, which the Wesnoth add-on server accepts for art.
Derived frames (the idle, move, attack, defend and death frames made from each
standing sprite) are shared under the same licence.

The sheet itself is not stored in the repository: it carries franchise branding
and hundreds of characters the add-on does not use. `production/tools/import_sheet_sprites.py`
cuts out the mapped units listed in `production/tools/sheet_sprite_map.json` and writes
their 12 unit frames. Portraits are not from the sheet.

Units whose sprite frames come from the sheet:

- `sw-unit-im-stormtrooper-sergeant` (hand-traced; replaced by an owner-supplied sheet, below)
- `sw-unit-im-clone-trooper` (hand-traced)
- `sw-hero-luke` (replaced by an owner-supplied sheet, below)
- `sw-hero-leia`
- `sw-hero-han`
- `sw-hero-chewbacca`
- `sw-hero-lando`
- `sw-hero-mara`
- `sw-hero-pellaeon`
- `sw-hero-cbaoth`
- `sw-hero-luuke` (replaced by an owner-supplied sheet, below)
- `sw-hero-karrde`
- `sw-hero-bel-iblis`
- `sw-unit-im-stormtrooper` (replaced by an owner-supplied sheet, below)
- `sw-unit-im-officer`
- `sw-unit-im-royal-guard`
- `sw-unit-nr-trooper`
- `sw-unit-nr-sergeant`
- `sw-unit-nr-commando`
- `sw-unit-bi-commando`
- `sw-unit-nr-militia`
- `sw-unit-nr-field-medic`
- `sw-unit-sm-smuggler`
- `sw-unit-sm-veteran`
- `sw-unit-wk-warrior`
- `sw-unit-wk-lookout`

Also from the sheet, but not cut out by the importer: `sw-hero-thrawn`. The
cut-out lost most of the body (white figure on the white marble), so Codex
redrew the standing sprite from its sheet crop.

## Other fan sprite references (owner-confirmed permission, 2026-10-04)

The sources are listed in `production/tools/reference_sprite_map.json` and
`docs/ART_LICENSE_CANDIDATES.md`. The images are kept outside the repository.
Codex redraws or restyles each one in the SacraiCross house style. Installed
2026-10-05 and credited in the README and every campaign's credits:

- SacraiCross: `sw-hero-thrawn` was redrawn from the v6 sheet (the Tarot card
  version was not used).
- MiddytheKnight (sprites by zerorunner67): stored, not used. The clone trooper
  comes from the v6 sheet instead (hand-traced, below).
- Milosh--Andrich: the first `sw-unit-im-scout-trooper` design; replaced
  2026-10-06 by an owner-supplied sheet (below).
- Codemus: `sw-unit-im-noghri`, `sw-hero-khabarakh`.
- danyelon: `sw-unit-im-tie-fighter`, `sw-unit-nr-xwing`, `sw-hero-wedge`,
  `sw-hero-xwing-luke`.
- Interdictorssd: `sw-unit-nr-awing`.
- Welljinco (TurboSquid Y-wing model render, used as a template):
  `sw-unit-nr-ywing`.
- Stored as alternatives, no unit yet: silent-Drew, Aet-Obli, kyleandreigames,
  RockyFirewolf, x-tender.
- mudkat101: stored as a reference; no unit uses it yet.

## Animation frames

The move, melee, ranged, defend and death frames of the sheet and reference
units were drawn by Codex from each unit's standing sprite
(`gen_codex_reference_frames.py`). The idle frames are derived from the
standing sprite. OpenAI's image safety system blocked some animations for
`sw-hero-chewbacca` (move, melee, death), so those keep frames derived from the
standing sprite. Ship
frames are all derived from their standing sprite.

## Hand-traced sheet sprites

`sw-unit-im-stormtrooper-sergeant` and `sw-unit-im-clone-trooper` are white
figures on the sheet's white marble, which the automatic cut-out could not
separate, and OpenAI's image safety system blocked Codex redraws. Their sprites
are cut out of the v6 sheet along hand-traced outlines (`outline` in
`sheet_sprite_map.json`), and all their frames are derived from that standing
sprite. Both are SacraiCross art under CC BY-SA, like the other sheet units.

## Owner-supplied sprite sheets

`sw-unit-im-stormtrooper`: all 12 frames come from a sprite sheet the project
owner supplied on 2026-10-06 (kept outside the repository as
`~/art-references/owner-stormtrooper.webp`), installed with
`production/tools/import_owner_sheet.py`. This replaces its SacraiCross sheet
sprite and the earlier generated frames.

`sw-unit-im-scout-trooper` (the speeder-bike scout unit): all 12 frames come
from an owner-supplied speeder-bike sheet (2026-10-06,
`~/art-references/owner-scout-speeder.webp`, palette from all frames so its
painted muzzle flash and explosion keep their colours). It replaced, the same
day, an owner-supplied on-foot sheet (`owner-scout-trooper.webp`, kept for a
possible dismounted unit), which had replaced the frames restyled from
Milosh--Andrich's reference. The painted flash is orange, so the unit's bolts
are orange.

`sw-hero-luke` and `sw-hero-luuke`: all 12 frames come from an owner-supplied
Luke sheet (2026-10-06, `~/art-references/owner-luke.webp`, palette from all
frames). Their firing frame paints a Force wave instead of a muzzle flash, so
no flash is blitted; Luke's deflected bolts stay red and Luuke's Force
lightning keeps its lightning projectile.

`sw-hero-luke-unarmed`: Luke's unarmed variation (owner-supplied sheet,
2026-10-06, `~/art-references/owner-luke-unarmed.webp`, scaled to match the
armed Luke sheet with `import_owner_sheet.py --match-scale`). Missions where
Luke has lost his lightsaber switch to it with `{SW_UNARMED sw_hero_luke}` and
back with `{SW_ARMED sw_hero_luke}` (utils/hte_macros.cfg); currently HTE 5,
Prisoner of Myrkr.

## Codex sheets from licensed references (2026-10-07)

Made with `production/tools/gen_codex_owner_sheets.py` (jobs in
`owner_sheet_jobs.json`): Codex gets the owner's on-foot scout trooper sheet as a
house-style template plus the unit's reference crop, and redraws all 12 frames
for that unit. The sheets are kept as `~/art-references/codex-<unit>.png` and
installed with `import_owner_sheet.py --palette-from-all`.

- SacraiCross references (gallery permission): `sw-unit-im-recon-squad`,
  `sw-unit-im-signal-jammer-team` (Fan Art 121), `sw-unit-nr-engineer-squad`
  (Fan Art 210), `sw-unit-nr-eweb-team`, `sw-unit-nr-rifle-squad` (Fan Art 60),
  `sw-unit-nr-heavy-weapons-squad`, `sw-unit-nr-slicer-team` (Fan Art 99),
  `sw-unit-nr-hero-commander` (Fan Art 179), `sw-unit-im-decon-droid` (Fan Art
  214, recoloured to its ochre tracked design).
- Codemus: `sw-unit-wy-myneyrshi`. Tactical-Sandwiches: `sw-unit-wl-vornskr`.
- No reference: `sw-unit-wy-psadan` (from its written description).
- `sw-unit-nr-eweb-team`'s standing frame is its crouched idle-1 (behind the
  gun), so standing and idle do not alternate with and without the gun.
- `sw-unit-nr-rifle-squad` previously used a mainline image; it now has its own
  art folder and animations (units/infantry.cfg).

`sw-unit-im-infiltrator`: all 12 frames from an owner-supplied sheet
(`~/art-references/owner-infiltrator.webp`) and its portrait from an
owner-supplied image (`owner-infiltrator-portrait.webp`, fitted with
`fit_portrait.py`).

`sw-unit-im-stormtrooper-sergeant`: all 12 frames from an owner-supplied sheet
(2026-10-07, `~/art-references/owner-stormtrooper-sergeant.webp`), replacing
the hand-traced sheet sprite. Its firing frame paints an orange flash, so its
bolts are orange.

## Walk and idle pass (2026-10-08)

Owner direction: walk frames alternate legs (the near leg leads in move-1, the
far leg in move-2) and idle frames show a small motion fitting the character.
`production/tools/repair_walk_idle.py` had Codex redraw only idle-1, idle-2,
move-1 and move-2 of each unit's installed sheet; every result was reviewed by
eye. Installed for 42 units (all four frames), the E-Web team (walk only), and
Bel Iblis and the Wookiee lookout (idle only: their redrawn walks lost the
grey beard and the weapon). Not changed: the stormtrooper and clone trooper
(blocked by the image safety system), the scout trooper speeder, the
decontamination droid, and the Y-wing (Codex redesigned the craft).

The old-style vehicles, ships and objectives (boarding shuttles, minelayer,
mole miner, Star Destroyer, TIE bomber and interceptor, docked warship,
Katana dreadnaught, cloning cylinder, shield generator, shipyard platform,
AT-ST walker, cloaked asteroid)
got full Codex sheets in the house style (`gen_codex_owner_sheets.py`, the
speeder sheet as template, the old sprite as the design reference); their
shots and effects are painted, so no flash is blitted over them.

## Owner-supplied portraits (2026-10-08)

From `character-portraits-v1.zip` (kept as `~/art-references/portraits-v1/`),
fitted to 256x256 with `production/tools/fit_portrait.py`: Luke (also used by
his unarmed variation), Imperial Infiltrator, Republic Commander, Heavy
Weapons Squad, Slicer Team, Psadan Elder, Recon Squad (previously a mainline
peasant portrait), Decontamination Droid and Combat Engineer Squad.

`sw-unit-im-at-st`: all 12 frames from an owner-supplied sheet (2026-10-08,
`~/art-references/owner-at-st.webp`), replacing the Codex sheet. Its shots
are painted, so no flash is blitted.
