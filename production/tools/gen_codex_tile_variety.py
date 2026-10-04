#!/usr/bin/env python3
"""Tile variety and detail pass (owner review, 2026-10-04), drawn by Codex.

Every add-on terrain was reviewed for character-scale detail, an obvious read
of what it represents, and variety. This generates the replacements and
extra variants. Wesnoth picks a random variant per hex from stem.png,
stem2.png, ... (NEW:BASE up to 11, NEW:VILLAGE up to 7), so variants are just
numbered files.

Modes:
  texture   seamless top-down texture, cut to the hex with the engine's mask
  object    one object group on transparency, fitted like a village overlay
  asteroid  asteroid group on transparency, composited onto a space tile

Run only while no other Codex art generation is active.
Usage: python3 production/tools/gen_codex_tile_variety.py [--only NAME ...] [--group GROUP]
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "agent" / "coordinator"))
import codex_art  # noqa: E402
import ticket_runner  # noqa: E402

OUT = ROOT / "addons/Star_Wars_Thrawn_Trilogy/images/terrain/sw"
ALPHAMASK = Path.home() / "opt/wesnoth-1.19.27/data/core/images/terrain/alphamask.png"

SCALE = ("Everything at a fine, small scale: this square is about two metres across and a soldier standing on "
         "it is as tall as the square, so plates, tiles, grates, cracks and details must be small and numerous.")

# (output file stem, mode, group, subject)
TILES: list[tuple[str, str, str, str]] = []


def add(stems, mode, group, subject_fn):
    for i, stem in enumerate(stems, 1):
        TILES.append((stem, mode, group, subject_fn(i)))


SPACE = [
    "deep space: a dense field of tiny stars of different brightness and faint colours on near-black",
    "deep space: tiny stars on near-black with one faint, barely visible wisp of violet-blue nebula dust",
    "deep space: sparse tiny stars on near-black with a distant faint spiral galaxy smudge",
    "deep space: tiny stars on near-black with a thin faint band of reddish interstellar dust",
    "deep space: a dense field of tiny white and pale-blue stars on near-black, no nebula",
    "deep space: tiny stars on near-black with a soft faint teal glow of distant gas",
]
add(["space", "space2", "space3", "space4", "space5", "space6"], "texture", "space",
    lambda i: SPACE[i - 1] + ". Low contrast and dark, so neighbouring squares blend; no planets, no ships")

ASTEROIDS = [
    "a group of three craggy gray-brown rock asteroids of different sizes with pitted cratered surfaces and "
    "sharp shadows lit from one side",
    "one large irregular dark asteroid with deep craters, fractured ridges and a few small rocks drifting near it",
    "a cluster of many small jagged rocks and gravel-sized debris spread loosely, like a dense part of an "
    "asteroid belt",
    "two pale icy asteroids with frosted bluish-white crusts, cracks and a faint glitter of ice",
    "a dark metallic-sheened asteroid with veins of ore catching the light, and two small companions",
    "an elongated tumbling rock asteroid with a long shadowed groove and scattered pebbles of debris",
]
add(["asteroids", "asteroids2", "asteroids3", "asteroids4", "asteroids5", "asteroids6"], "asteroid", "asteroids",
    lambda i: ASTEROIDS[i - 1])

DECK = [
    "the deck of a space station: small interlocking gray metal floor plates with fine rivets and seams, "
    "a narrow strip of recessed blue guide lights",
    "the deck of a space station: gray metal plating with a small square floor grate showing pipes beneath, "
    "fine rivets",
    "the deck of a space station: worn gray deck plates with a painted yellow-and-black hazard stripe along "
    "one side and scuff marks",
    "the deck of a space station: gray metal plates with a covered cable trench running across and two small "
    "access hatches",
]
add(["deck", "deck2", "deck3", "deck4"], "texture", "metal", lambda i: DECK[i - 1])

INTERIOR = [
    "the corridor floor of a starship: dark gray riveted metal floor plates with a small ventilation grille",
    "the corridor floor of a starship: dark metal plating with a diamond-tread non-slip panel and fine rivets",
    "the corridor floor of a starship: dark metal floor with a small round maintenance hatch and seams",
    "the corridor floor of a starship: dark riveted plates with a thin strip of glowing white floor lights",
]
add(["interior-deck", "interior-deck2", "interior-deck3", "interior-deck4"], "texture", "metal",
    lambda i: INTERIOR[i - 1])

BULKHEAD = [
    "the top of a thick starship bulkhead wall: heavy dark gray armoured plates with bolted seams and a bundle "
    "of pipes along it, clearly a solid wall",
    "the top of a thick starship bulkhead wall: dark armoured plating with conduits, a warning stripe and a "
    "small status light, clearly a solid wall",
    "the top of a thick starship bulkhead wall: reinforced dark metal with structural ribs and cable runs, "
    "clearly a solid wall",
]
add(["bulkhead", "bulkhead2", "bulkhead3"], "texture", "metal", lambda i: BULKHEAD[i - 1])

add(["hangar", "hangar2"], "texture", "metal",
    lambda i: ("a starship hangar bay floor: dark gray deck with painted white landing markings, tie-down "
               "points and " + ("a yellow-and-black hazard border" if i == 1 else "faint scorch marks from engines")))
add(["launch-rail", "launch-rail2"], "texture", "metal",
    lambda i: ("a starfighter launch rail on a station deck: two parallel glowing magnetic rails with fine "
               "metal ribs between them on dark plating" + ("" if i == 1 else ", with blinking guide lights")))

ROAD = [
    "a weathered duracrete road: pale gray concrete slabs with fine cracks, a few tiny weeds in the seams",
    "a weathered duracrete road: pale gray concrete with a small round drain grate and stains",
    "a weathered duracrete road: pale gray slabs with faded painted lane markings and scattered grit",
]
add(["duracrete-road", "duracrete-road2", "duracrete-road3"], "texture", "built", lambda i: ROAD[i - 1])
PLAZA = [
    "a colony plaza: small square pale duracrete paving tiles with fine joints and a few cracked tiles",
    "a colony plaza: pale paving tiles with a small inset light and dirt in the joints",
    "a colony plaza: pale paving with a utility access cover and a few dry leaves",
]
add(["duracrete-plaza", "duracrete-plaza2", "duracrete-plaza3"], "texture", "built", lambda i: PLAZA[i - 1])
add(["bunker", "bunker2"], "texture", "built",
    lambda i: ("the reinforced apron of a military bunker: heavy gray duracrete blocks with blast scoring, "
               + ("bolted anchor plates" if i == 1 else "sandbag-coloured patches and a drainage channel")))
add(["throne-floor", "throne-floor2"], "texture", "built",
    lambda i: ("the floor of a dark imperial throne room: polished black stone tiles with thin silver inlay "
               + ("lines" if i == 1 else "lines and a faint reflection")))

# Extra variants of the location interiors.
add(["floor-timber2"], "texture", "built", lambda i: "a frontier building's wooden plank floor: narrower dark planks with "
    "nail heads, a worn rug corner and a few scratches")
add(["floor-colony2"], "texture", "built", lambda i: "a colony building floor: light gray duracrete tiles with a small "
    "floor drain and scuffs")
add(["floor-palace2"], "texture", "built", lambda i: "a grand palace floor: polished cream marble with a fine dark red "
    "border inlay")
add(["floor-rock2"], "texture", "built", lambda i: "a tunnel floor cut into a mountain: smoothed dark stone with a "
    "shallow drainage groove and grit")
add(["wall-timber2"], "texture", "built", lambda i: "the top of a thick wall of dark logs with a crossbeam and iron "
    "brackets, clearly a solid wall")
add(["wall-colony2"], "texture", "built", lambda i: "the top of a thick duracrete wall with a metal cap and a small "
    "conduit, clearly a solid wall")
add(["wall-palace2"], "texture", "built", lambda i: "the top of a thick palace wall of carved pale stone with a "
    "fluted moulding, clearly a solid wall")
add(["wall-rock2"], "texture", "built", lambda i: "solid raw mountain rock with a vein of pale quartz and deep "
    "cracks, clearly impassable")

# Settlement variants: same kind of place per biome, each visibly distinct.
VILLAGES = {
    "dome": ["a single large weathered prefab dome habitat with an awning and a small vaporator",
             "two prefab dome habitats joined by a short tube corridor with a satellite dish"],
    "depot": ["an indoor supply depot: shelves of gray supply crates and a fuel cell rack",
              "an indoor supply depot: a medical station with a bacta tank and stacked crates"],
    "wookiee": ["a Wookiee dwelling of carved wood and woven branches high on a giant tree branch with a rope "
                "bridge", "a cluster of two small round Wookiee huts of wood and leaves on a platform around a "
                "huge trunk"],
    "wayland": ["a single large round native hut with a steep thatched roof and drying racks",
                "three small primitive huts of woven reeds around a fire pit"],
    "dukha": ["a smaller Noghri dukha of rough gray stone with a dark timber roof and a carved doorpost",
              "a Noghri dukha with a stone wall courtyard and a sloped dark roof"],
    "farmstead": ["a colonist farmstead: a prefab barn with a moisture vaporator and a plowed plot",
                  "a colonist farmstead: a small dome house, a water tank and a fenced pen"],
    "outpost": ["a hunter's outpost: a log lean-to with a tarp roof and a rack of supplies",
                "a hunter's outpost: a small prefab hut on stilts with a ladder and an antenna"],
    "camp": ["an Imperial field camp: one large gray command tent with a holotable glow and a power generator",
             "an Imperial field camp: a sensor tower, two crates and a gray shelter"],
}
for kind, subjects in VILLAGES.items():
    add([f"village-{kind}2", f"village-{kind}3"], "object", "villages", lambda i, s=subjects: s[i - 1])

TEXTURE_PROMPT = """Use your image generation tool to create exactly ONE original image: a seamless square texture of {subject}. Seen straight from above, filling the entire square edge to edge, with flat even lighting, no perspective and no vignette. {scale} Save it as tile.png in the current working directory. Do not create any other files.

Style: {style}

Rules:
- Fully original artwork. Do not copy or closely imitate any existing illustration, film still, game asset or texture pack.
- No text, letters, numbers, logos, insignia, emblems, symbols, watermarks or borders anywhere in the image.

After saving, reply with only the file name."""

OBJECT_PROMPT = """Use your image generation tool to create exactly ONE original image: {subject}. Seen from above at a three-quarter angle, like an object in a turn-based strategy game, the whole group centered with an empty margin on a TRANSPARENT background, with fine believable detail. No ground plane, no shadow outside the object, no people. Save it as tile.png in the current working directory. Do not create any other files.

Style: {style}

Rules:
- Fully original artwork. Do not copy or closely imitate any existing illustration, film still, game asset or toy.
- No text, letters, numbers, logos, insignia, emblems, symbols, watermarks or borders anywhere in the image.

After saving, reply with only the file name."""

FIT_TEXTURE = """
from PIL import Image
img = Image.open({src!r}).convert("RGBA")
side = min(img.size)
left, top = (img.width - side) // 2, (img.height - side) // 2
img = img.crop((left, top, left + side, top + side)).resize((72, 72), Image.LANCZOS)
mask = Image.open({mask!r}).convert("RGBA").getchannel("A").resize((72, 72))
img.putalpha(mask)
colors = img.convert("RGB").getcolors(72 * 72) or []
if len(colors) < 6:
    raise SystemExit("degenerate tile rejected: %d colours" % len(colors))
img.save({dst!r}, optimize=True)
"""

FIT_OBJECT = """
import sys
sys.path.insert(0, {tools!r})
from PIL import Image
from derive_unit_frames import degenerate_reason, fit, remove_flat_background
img = fit(remove_flat_background(Image.open({src!r})), 72, margin={margin}, anchor_bottom=False)
reason = degenerate_reason(img)
if reason:
    raise SystemExit("degenerate tile rejected: " + reason)
if {space!r}:
    # Asteroids: composite the rocks onto a space tile so fields blend with
    # the surrounding space.
    base = Image.open({space!r}).convert("RGBA")
    base.alpha_composite(img)
    img = base
    # A base terrain must stay inside the hex: clip rocks to the hex mask.
    from PIL import ImageChops
    mask = Image.open({mask!r}).convert("RGBA").getchannel("A").resize((72, 72))
    img.putalpha(ImageChops.multiply(img.getchannel("A"), mask))
img.save({dst!r}, optimize=True)
"""


def generate(stem: str, mode: str, subject: str, style: str) -> dict:
    executable = ticket_runner.resolve_codex_executable()
    environment = ticket_runner.require_codex_chatgpt_quota(executable or "")
    workspace = codex_art._managed_directory(f"tile-{stem}")
    target = workspace / "tile.png"
    if mode == "texture":
        prompt = TEXTURE_PROMPT.format(subject=subject, scale=SCALE, style=style)
    else:
        prompt = OBJECT_PROMPT.format(subject=subject, style=style)
    ok, output = codex_art._codex_image(executable or "", environment, workspace, prompt, target,
                                        subprocess.run, "gpt-6-luna")
    if not ok:
        if codex_art.QUOTA.search(output) and not codex_art.MODERATION.search(output):
            return {"tile": stem, "state": "quota_paused"}
        return {"tile": stem, "state": "failed", "reason": "no image produced"}
    dst = str(OUT / f"{stem}.png")
    if mode == "texture":
        script = FIT_TEXTURE.format(src=str(target), mask=str(ALPHAMASK), dst=dst)
    else:
        space = ""
        if mode == "asteroid":
            n = stem.replace("asteroids", "") or "1"
            candidate = OUT / (f"space{n}.png" if n != "1" else "space.png")
            space = str(candidate if candidate.exists() else OUT / "space.png")
        script = FIT_OBJECT.format(tools=str(ROOT / "production/tools"), src=str(target), dst=dst,
                                   mask=str(ALPHAMASK),
                                   margin=4 if mode == "asteroid" else 6, space=space)
    done = subprocess.run([str(codex_art.art_python()), "-c", script], capture_output=True, text=True,
                          timeout=300, check=False)
    if done.returncode:
        return {"tile": stem, "state": "failed", "reason": (done.stderr or done.stdout)[-300:]}
    return {"tile": stem, "state": "generated"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", action="append")
    parser.add_argument("--group", action="append")
    args = parser.parse_args()
    style = codex_art.load_direction(ROOT).get("style", "")
    results = []
    for stem, mode, group, subject in TILES:
        if args.only and stem not in args.only:
            continue
        if args.group and group not in args.group:
            continue
        outcome = generate(stem, mode, subject, style)
        results.append(outcome)
        print(json.dumps(outcome), flush=True)
        if outcome["state"] == "quota_paused":
            break
    return 0 if all(item["state"] == "generated" for item in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
