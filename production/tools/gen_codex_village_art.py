#!/usr/bin/env python3
"""Generate lore-accurate settlement overlays with Codex, one image per call.

Each settlement replaces a medieval mainline village overlay (see
utils/hte_terrain.cfg). Codex draws the object on a transparent background;
it is fitted onto a 72x72 hex tile, centred low like mainline village art,
and rejected if degenerate. Run only while no other Codex art generation is
active (images are harvested from the shared Codex folder by time window).

Usage: python3 production/tools/gen_codex_village_art.py [--kind dome ...]
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

# Lore notes: prefab domes and supply depots are the standard frontier and
# base architecture of the Legends era; Wookiees live in wroshyr-tree
# dwellings; Noghri clans live in stone dukhas; Wayland's natives
# (Myneyrshi and Psadan) are pre-industrial; Imperial field units deploy
# modular gray shelters.
KINDS = {
    "dome": "a small cluster of two or three weathered white-gray prefabricated dome habitats with round hatches, "
            "a short comm antenna and a few cargo crates, the kind of cheap frontier housing used across the galaxy",
    "depot": "an indoor supply depot: a neat stack of gray durasteel cargo crates and a wall-mounted medical "
             "bacta cabinet glowing faintly blue, seen from above at a three-quarter angle",
    "wookiee": "a Wookiee dwelling on the planet Kashyyyk: a round hut of carved wood and woven branches built on a "
               "wooden platform around the base of an enormous tree trunk, warm light in its doorway",
    "wayland": "a small native village on the jungle planet Wayland: two round huts with steep thatched roofs and "
               "a low wooden palisade, primitive and handmade",
    "dukha": "a Noghri clan dukha on the blighted planet Honoghr: a long low hall of rough gray stone with a heavy "
             "sloped roof of dark timber and a single wide doorway",
    "farmstead": "a lonely colonist farmstead: one weathered prefab hut, a tall cylindrical moisture vaporator and "
                 "a small fenced garden plot",
    "outpost": "a hunter's outpost in a dark forest: one battered prefab shelter with a slanted roof, a small "
               "satellite dish and a stack of supply crates",
    "camp": "an Imperial field camp: two gray modular military shelters with slanted roofs, a portable power "
            "generator and a sensor mast, orderly and utilitarian",
}

# Planet forests: a dense cluster of trees filling the hex, drawn in two
# variants each so neighbouring forest hexes do not repeat exactly.
FORESTS = {
    "wroshyr": "the forest of the planet Kashyyyk: two or three colossal wroshyr trees with massive gray-brown "
               "trunks and broad flat branching canopies of deep green leaves, vines hanging between them",
    "myrkr": "the dark forest of the planet Myrkr: tall straight pale-barked trees with dense dark blue-green "
             "foliage, a few small furry tree-dwelling lizard-like creatures clinging to the branches",
    "wayland": "the jungle of the planet Wayland: a tangle of thick tropical trees with huge leaves, hanging "
               "vines and dense undergrowth, steamy and overgrown",
}
for _name, _subject in FORESTS.items():
    for _variant in (1, 2):
        KINDS[f"forest-{_name}-{_variant}"] = _subject + (", seen from a slightly different side" if _variant == 2 else "")

PROMPT = """Use your image generation tool to create exactly ONE original image: {subject}. Seen from above at a three-quarter angle, like a building in a turn-based strategy game, the whole object centered with an empty margin on a TRANSPARENT background. A single object group only; no ground plane, no shadow outside the object, no people. Save it as village.png in the current working directory. Do not create any other files.

Style: {style}

Rules:
- Fully original artwork. Do not copy or closely imitate any existing illustration, film still, game asset or toy.
- No text, letters, numbers, logos, insignia, emblems, symbols, watermarks or borders anywhere in the image.

After saving, reply with only the file name."""

FIT = """
import sys
sys.path.insert(0, {tools!r})
from PIL import Image
from derive_unit_frames import degenerate_reason, fit, remove_flat_background
img = fit(remove_flat_background(Image.open({src!r})), 72, margin={margin}, anchor_bottom=False)
reason = degenerate_reason(img)
if reason:
    raise SystemExit("degenerate village art rejected: " + reason)
img.save({dst!r}, optimize=True)
"""


def output_name(kind: str) -> str:
    """Mainline variant naming: stem.png, stem2.png (terrain macro uses @V)."""
    if kind.startswith("forest-"):
        stem, _, variant = kind.rpartition("-")
        return f"{stem}{'' if variant == '1' else variant}.png"
    return f"village-{kind}.png"


def generate(kind: str, style: str) -> dict:
    executable = ticket_runner.resolve_codex_executable()
    environment = ticket_runner.require_codex_chatgpt_quota(executable or "")
    workspace = codex_art._managed_directory(f"village-{kind}")
    target = workspace / "village.png"
    ok, output = codex_art._codex_image(executable or "", environment, workspace,
                                        PROMPT.format(subject=KINDS[kind], style=style), target,
                                        subprocess.run, "gpt-6-luna")
    if not ok:
        if codex_art.QUOTA.search(output) and not codex_art.MODERATION.search(output):
            return {"kind": kind, "state": "quota_paused"}
        return {"kind": kind, "state": "failed", "reason": "no image produced"}
    script = FIT.format(tools=str(ROOT / "production/tools"), src=str(target), margin=2 if kind.startswith("forest-") else 6,
                        dst=str(OUT / output_name(kind)))
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
