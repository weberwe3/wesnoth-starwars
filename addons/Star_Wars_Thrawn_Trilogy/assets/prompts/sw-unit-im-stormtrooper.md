# Original art brief — sw unit im stormtrooper

Paste one state request at a time into a Codex interactive task with `$imagegen`.
The generated PNGs belong in the exact project paths below.

```text
$imagegen

Use case: stylized-concept
Asset type: Battle for Wesnoth tactical unit sprite set
Primary request: Create one original, unnamed sw unit im stormtrooper for a post-Return of the Jedi Legends-inspired campaign. The unit is described in this project's original WML as: An original tactical unit.
Style/medium: hand-painted tactical strategy-game sprite; strong readable silhouette at 72×72 pixels; transparent background; use a consistent original wardrobe, palette, and equipment design across every state.
Composition/framing: three-quarter full-body tactical pose; preserve the same character identity, proportions, clothing, and equipment in every frame; alter only the motion or pose specified for the requested state.
Constraints: fully original artwork. Do not reproduce or closely imitate book-cover art, comics, film stills, actors, logos, named-character likenesses, official game art, or public reference-image composition. No text and no watermark.
```

## Required output set

- `images/units/sw-unit-im-stormtrooper/standing.png` — Base standing sprite.
- `images/units/sw-unit-im-stormtrooper/idle-1.png` — Idle animation frame one.
- `images/units/sw-unit-im-stormtrooper/idle-2.png` — Idle animation frame two.
- `images/units/sw-unit-im-stormtrooper/move-1.png` — Movement animation frame one.
- `images/units/sw-unit-im-stormtrooper/move-2.png` — Movement animation frame two.
- `images/units/sw-unit-im-stormtrooper/melee-1.png` — Melee attack wind-up frame.
- `images/units/sw-unit-im-stormtrooper/melee-2.png` — Melee attack follow-through frame.
- `images/units/sw-unit-im-stormtrooper/ranged-1.png` — Ranged attack aiming frame.
- `images/units/sw-unit-im-stormtrooper/ranged-2.png` — Ranged attack firing frame.
- `images/units/sw-unit-im-stormtrooper/defend.png` — Defend or hit-reaction sprite.
- `images/units/sw-unit-im-stormtrooper/death-1.png` — Death animation frame one.
- `images/units/sw-unit-im-stormtrooper/death-2.png` — Death animation frame two.
- `images/portraits/sw-unit-im-stormtrooper.png` — Unit profile portrait.

Generate each listed state as a separate transparent PNG. Do not mark this job
complete until every listed file is imported and the unit WML references the
standing, idle, move, melee, ranged, defend, death, and portrait assets.
