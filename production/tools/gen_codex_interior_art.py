#!/usr/bin/env python3
"""Generate location-specific interior terrain art with Codex, one image per call.

The add-on's interiors all used the starship durasteel deck and bulkhead,
which read as "metal patterns" in places that are not ships. These tiles give
each kind of place its own floor and wall, plus a cover object:

  floors (top-down textures, hex-masked):  timber, colony, palace, rock
  walls  (top-down textures, hex-masked):  timber, colony, palace, rock
  cover  (object on transparency, fitted like a village overlay): crates

Applied per map by hte_mapkit (HexMap.interior). Run only while no other
Codex art generation is active (images are harvested from the shared Codex
folder by time window).

Usage: python3 production/tools/gen_codex_interior_art.py [--kind floor-timber ...]
Requires the art Python (Pillow) for fitting.
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

# Lore notes: Talon Karrde's base on Myrkr is a cluster of buildings in a
# forest clearing (timber); Bpfassh and the smugglers' meeting halls are
# ordinary colony duracrete; the Imperial Palace on Coruscant is polished
# stone; Mount Tantiss is a storehouse hollowed out of a mountain.
TEXTURES = {
    "floor-timber": "the wide wooden plank floor of a frontier building on a forest planet: long warm-brown planks "
                    "with visible grain, a few knots and worn paths, seen straight from above",
    "floor-colony": "the floor of an ordinary colony building: large square light-gray duracrete tiles with thin "
                    "dark seams, a little scuffed, seen straight from above",
    "floor-palace": "the floor of a grand old palace hall: polished dark red and cream marble with a subtle "
                    "geometric inlay, slightly reflective, seen straight from above",
    "floor-rock": "the floor of a tunnel cut into a mountain: smoothed dark gray stone with tool marks and a few "
                  "cracks, seen straight from above",
    "wall-timber": "the top of a thick wall of rough-hewn dark logs, bark edges and wooden pegs, seen straight from "
                   "above, darker than a floor",
    "wall-colony": "the top of a thick duracrete wall: rough medium-gray concrete with a darker metal cap strip "
                   "along its middle, seen straight from above",
    "wall-palace": "the top of a thick ornamental palace wall: carved pale stone blocks with a gilded trim line, "
                   "seen straight from above",
    "wall-rock": "solid raw mountain rock: jagged dark gray stone with deep cracks and shadows, seen straight "
                 "from above, clearly impassable",
}
OBJECTS = {
    "cover-crates": "a waist-high stack of four or five battered cargo crates of mixed sizes, some metal, some "
                    "wooden, the kind of cover a soldier crouches behind",
}

TEXTURE_PROMPT = """Use your image generation tool to create exactly ONE original image: a seamless square texture of {subject}. The texture must fill the entire square edge to edge, with flat even lighting, no perspective and no vignette. Save it as tile.png in the current working directory. Do not create any other files.

Style: {style}

Rules:
- Fully original artwork. Do not copy or closely imitate any existing illustration, film still, game asset or texture pack.
- No text, letters, numbers, logos, insignia, emblems, symbols, watermarks or borders anywhere in the image.

After saving, reply with only the file name."""

OBJECT_PROMPT = """Use your image generation tool to create exactly ONE original image: {subject}. Seen from above at a three-quarter angle, like an object in a turn-based strategy game, the whole object centered with an empty margin on a TRANSPARENT background. A single object group only; no ground plane, no shadow outside the object, no people. Save it as tile.png in the current working directory. Do not create any other files.

Style: {style}

Rules:
- Fully original artwork. Do not copy or closely imitate any existing illustration, film still, game asset or toy.
- No text, letters, numbers, logos, insignia, emblems, symbols, watermarks or borders anywhere in the image.

After saving, reply with only the file name."""

# A texture: centre square scaled to 72x72, cut to the hex with the engine's
# own terrain alpha mask, rejected if degenerate.
FIT_TEXTURE = """
import sys
sys.path.insert(0, {tools!r})
from PIL import Image
from derive_unit_frames import degenerate_reason
img = Image.open({src!r}).convert("RGBA")
side = min(img.size)
left, top = (img.width - side) // 2, (img.height - side) // 2
img = img.crop((left, top, left + side, top + side)).resize((72, 72), Image.LANCZOS)
mask = Image.open({mask!r}).convert("RGBA").getchannel("A").resize((72, 72))
img.putalpha(mask)
# Floors can be plain (a gray tile floor has few colours); reject only an
# empty or single flat colour, not the unit-sprite colour threshold.
colors = img.convert("RGB").getcolors(72 * 72) or []
if len(colors) < 6:
    raise SystemExit("degenerate interior art rejected: %d colours" % len(colors))
img.save({dst!r}, optimize=True)
"""

FIT_OBJECT = """
import sys
sys.path.insert(0, {tools!r})
from PIL import Image
from derive_unit_frames import degenerate_reason, fit, remove_flat_background
img = fit(remove_flat_background(Image.open({src!r})), 72, margin=10, anchor_bottom=False)
reason = degenerate_reason(img)
if reason:
    raise SystemExit("degenerate interior art rejected: " + reason)
img.save({dst!r}, optimize=True)
"""

KINDS = {**TEXTURES, **OBJECTS}


def generate(kind: str, style: str) -> dict:
    executable = ticket_runner.resolve_codex_executable()
    environment = ticket_runner.require_codex_chatgpt_quota(executable or "")
    workspace = codex_art._managed_directory(f"interior-{kind}")
    target = workspace / "tile.png"
    prompt = (TEXTURE_PROMPT if kind in TEXTURES else OBJECT_PROMPT).format(subject=KINDS[kind], style=style)
    ok, output = codex_art._codex_image(executable or "", environment, workspace, prompt, target,
                                        subprocess.run, "gpt-6-luna")
    if not ok:
        if codex_art.QUOTA.search(output) and not codex_art.MODERATION.search(output):
            return {"kind": kind, "state": "quota_paused"}
        return {"kind": kind, "state": "failed", "reason": "no image produced"}
    fit = FIT_TEXTURE if kind in TEXTURES else FIT_OBJECT
    script = fit.format(tools=str(ROOT / "production/tools"), src=str(target), mask=str(ALPHAMASK),
                        dst=str(OUT / f"{kind}.png"))
    done = subprocess.run([str(codex_art.art_python()), "-c", script], capture_output=True, text=True,
                          timeout=300, check=False)
    if done.returncode:
        return {"kind": kind, "state": "failed", "reason": (done.stderr or done.stdout)[-300:]}
    return {"kind": kind, "state": "generated"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kind", action="append", choices=sorted(KINDS))
    args = parser.parse_args()
    style = codex_art.load_direction(ROOT).get("style", "")
    OUT.mkdir(parents=True, exist_ok=True)
    results = []
    for kind in args.kind or list(KINDS):
        outcome = generate(kind, style)
        results.append(outcome)
        print(json.dumps(outcome), flush=True)
        if outcome["state"] == "quota_paused":
            break
    return 0 if all(item["state"] == "generated" for item in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
