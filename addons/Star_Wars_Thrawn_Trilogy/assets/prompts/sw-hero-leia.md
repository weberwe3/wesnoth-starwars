# Original art brief — sw hero leia

Paste one state request at a time into a Codex interactive task with `$imagegen`.
The generated PNGs belong in the exact project paths below.

```text
$imagegen

Use case: stylized-concept
Asset type: Battle for Wesnoth tactical unit sprite set
Primary request: Create one original, unnamed sw hero leia for a post-Return of the Jedi Legends-inspired campaign. The unit is described in this project's original WML as: An original tactical unit.
Style/medium: hand-painted tactical strategy-game sprite; strong readable silhouette at 72×72 pixels; transparent background; use a consistent original wardrobe, palette, and equipment design across every state.
Composition/framing: three-quarter full-body tactical pose; preserve the same character identity, proportions, clothing, and equipment in every frame; alter only the motion or pose specified for the requested state.
Constraints: fully original artwork. Do not reproduce or closely imitate book-cover art, comics, film stills, actors, logos, named-character likenesses, official game art, or public reference-image composition. No text and no watermark.
```

## Required output set

- `images/units/sw-hero-leia/standing.png` — Base standing sprite.
- `images/units/sw-hero-leia/idle-1.png` — Idle animation frame one.
- `images/units/sw-hero-leia/idle-2.png` — Idle animation frame two.
- `images/units/sw-hero-leia/move-1.png` — Movement animation frame one.
- `images/units/sw-hero-leia/move-2.png` — Movement animation frame two.
- `images/units/sw-hero-leia/melee-1.png` — Melee attack wind-up frame.
- `images/units/sw-hero-leia/melee-2.png` — Melee attack follow-through frame.
- `images/units/sw-hero-leia/ranged-1.png` — Ranged attack aiming frame.
- `images/units/sw-hero-leia/ranged-2.png` — Ranged attack firing frame.
- `images/units/sw-hero-leia/defend.png` — Defend or hit-reaction sprite.
- `images/units/sw-hero-leia/death-1.png` — Death animation frame one.
- `images/units/sw-hero-leia/death-2.png` — Death animation frame two.
- `images/portraits/sw-hero-leia.png` — Unit profile portrait.

Generate each listed state as a separate transparent PNG. Do not mark this job
complete until every listed file is imported and the unit WML references the
standing, idle, move, melee, ranged, defend, death, and portrait assets.
