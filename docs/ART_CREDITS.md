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

- `sw-hero-luke`
- `sw-hero-leia`
- `sw-hero-han`
- `sw-hero-chewbacca`
- `sw-hero-lando`
- `sw-hero-mara`
- `sw-hero-pellaeon`
- `sw-hero-cbaoth`
- `sw-hero-luuke`
- `sw-hero-karrde`
- `sw-hero-bel-iblis`
- `sw-unit-im-stormtrooper`
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

Mapped but not imported yet (their earlier art is kept):

- `sw-hero-thrawn`: white figure on the white marble with a broken outline; the cut-out loses most of the body
- `sw-unit-im-stormtrooper-sergeant`: white armour on the white marble; the cut-out loses the legs
- `sw-unit-im-clone-trooper`: white figure on the white marble with a broken outline; the cut-out loses most of the body
