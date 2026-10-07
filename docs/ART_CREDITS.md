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

- `sw-unit-im-stormtrooper-sergeant` (hand-traced)
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
