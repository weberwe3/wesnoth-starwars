# Original art brief — New Republic Field Engineer Team

Paste one state request at a time into a Codex interactive task with `$imagegen`.
The generated PNGs belong in the exact project paths below.

```text
$imagegen

Use case: stylized-concept
Asset type: Battle for Wesnoth tactical unit sprite set
Primary request: Create one original, unnamed New Republic Field Engineer Team for a post-Return of the Jedi Legends-inspired campaign. The unit is described in this project's original WML as: A versatile support squad specializing in field repair and signal restoration. Equipped with a short-range blaster for defensive fire and portable repair and signaling equipment, the Field Engineer Team restores damaged vehicles and re-establishes communications across the battlefield. Their modest armor and short-range blaster make them effective defenders of key positions, while their repair tools allow them to sustain allied formations in contested areas.
Style/medium: hand-painted tactical strategy-game sprite; strong readable silhouette at 72×72 pixels; transparent background; use a consistent original wardrobe, palette, and equipment design across every state.
Composition/framing: three-quarter full-body tactical pose; preserve the same character identity, proportions, clothing, and equipment in every frame; alter only the motion or pose specified for the requested state.
Constraints: fully original artwork. Do not reproduce or closely imitate book-cover art, comics, film stills, actors, logos, named-character likenesses, official game art, or public reference-image composition. No text and no watermark.
```

## Required output set

- `images/units/sw-unit-nr-field-engineer-team/standing.png` — Base standing sprite.
- `images/units/sw-unit-nr-field-engineer-team/idle-1.png` — Idle animation frame one.
- `images/units/sw-unit-nr-field-engineer-team/idle-2.png` — Idle animation frame two.
- `images/units/sw-unit-nr-field-engineer-team/move-1.png` — Movement animation frame one.
- `images/units/sw-unit-nr-field-engineer-team/move-2.png` — Movement animation frame two.
- `images/units/sw-unit-nr-field-engineer-team/melee-1.png` — Melee attack wind-up frame.
- `images/units/sw-unit-nr-field-engineer-team/melee-2.png` — Melee attack follow-through frame.
- `images/units/sw-unit-nr-field-engineer-team/ranged-1.png` — Ranged attack aiming frame.
- `images/units/sw-unit-nr-field-engineer-team/ranged-2.png` — Ranged attack firing frame.
- `images/units/sw-unit-nr-field-engineer-team/defend.png` — Defend or hit-reaction sprite.
- `images/units/sw-unit-nr-field-engineer-team/death-1.png` — Death animation frame one.
- `images/units/sw-unit-nr-field-engineer-team/death-2.png` — Death animation frame two.
- `images/portraits/sw-unit-nr-field-engineer-team.png` — Unit profile portrait.

Generate each listed state as a separate transparent PNG. Do not mark this job
complete until every listed file is imported and the unit WML references the
standing, idle, move, melee, ranged, defend, death, and portrait assets.
