#!/usr/bin/env python3
"""Redraw unit sprites as small hand-pixeled RPG characters, with Codex.

Owner direction (2026-10-04): a new sprite look -- small, chibi-leaning
pixel-art characters with bold dark outlines and soft cel shading -- for
the unit sprites. The style is described by its visual traits only; no
artist or work is named or imitated (art direction rule). Portraits keep
their painted look.

Per unit: Codex draws one original master from the unit's art-direction
subject (production/assets/art_direction.json) in the pixel style; it is
then pixelized to the 72x72 frame (downsample, hard alpha edge, reduced
palette, 1 px dark outline) and the 12 animation frames are derived with
derive_unit_frames.derive. The unit's portrait is kept.

Run only while no other Codex art generation is active.
Usage: python3 production/tools/gen_codex_pixel_sprites.py [--only UNIT_ID ...] [--preview OUT.png]
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
sys.path.insert(0, str(Path(__file__).resolve().parent))
from prompt_scrub import check, scrub  # noqa: E402

UNITS = ROOT / "addons/Star_Wars_Thrawn_Trilogy/images/units"

PIXEL_STYLE = (
    "Hand-pixeled 2D role-playing-game character sprite: small, chibi-leaning proportions (the head about a "
    "quarter of the body height, compact torso, short sturdy legs), a bold near-black one-pixel outline around "
    "the whole figure and its main shapes, soft cel shading with three or four tones per colour, warm "
    "highlights, crisp readable details at a very small size, standing in a relaxed three-quarter view turned "
    "slightly to the right, feet planted. Clean flat colours, no painterly brushwork, no blur, no glow except "
    "on energy blades and blaster bolts."
)

PROMPT = """Use your image generation tool to create exactly ONE original image: a single full-body game unit sprite for a turn-based tactics game, on a TRANSPARENT background, the whole figure centered with an empty margin. Show one subject only. Save it as sprite.png in the current working directory. Do not create any other files.

Subject: {subject}

Style: {style}

Rules:
{rules}

After saving, reply with only the file name."""

# Pixelize a high-resolution master into a 72x72 pixel-art frame.
PIXELIZE = """
import sys, json
sys.path.insert(0, {tools!r})
from PIL import Image
from derive_unit_frames import degenerate_reason, derive, remove_flat_background
SPRITE, MAX_H, MAX_W, COLORS = 72, 64, 70, 40
img = remove_flat_background(Image.open({src!r}))
img = img.crop(img.getbbox())
scale = min(MAX_H / img.height, MAX_W / img.width)
img = img.resize((max(1, round(img.width * scale)), max(1, round(img.height * scale))), Image.LANCZOS)
# Hard edge: pixel art has no partial transparency.
alpha = img.getchannel("A").point(lambda a: 255 if a >= 110 else 0)
# Reduced palette: the soft gradients of a painted image become flat tones.
rgb = Image.new("RGB", img.size, (0, 0, 0))
rgb.paste(img.convert("RGB"), mask=alpha)
rgb = rgb.quantize(colors=COLORS, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE).convert("RGB")
px, ap = rgb.load(), alpha.load()
w, h = img.size
# One-pixel dark outline on the figure's edge (inside, so the size is kept).
edge = []
for y in range(h):
    for x in range(w):
        if ap[x, y] and any(not (0 <= x + dx < w and 0 <= y + dy < h) or not ap[x + dx, y + dy]
                            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))):
            edge.append((x, y))
for x, y in edge:
    r, g, b = px[x, y]
    px[x, y] = (int(r * 0.25) + 8, int(g * 0.25) + 6, int(b * 0.25) + 10)
small = rgb.convert("RGBA")
small.putalpha(alpha)
base = Image.new("RGBA", (SPRITE, SPRITE), (0, 0, 0, 0))
base.alpha_composite(small, ((SPRITE - w) // 2, SPRITE - 2 - h))
reason = degenerate_reason(base)
if reason:
    raise SystemExit("degenerate sprite rejected: " + reason)
if {preview!r}:
    base.save({preview!r})
else:
    for state, frame in derive(base).items():
        frame.save({unit_dir!r} + "/" + state + ".png", optimize=True)
print("ok")
"""


def generate(unit_id: str, direction: dict, preview_dir: Path | None) -> dict:
    subject = direction["units"].get(unit_id)
    if not subject:
        return {"unit": unit_id, "state": "failed", "reason": "no art direction"}
    executable = ticket_runner.resolve_codex_executable()
    environment = ticket_runner.require_codex_chatgpt_quota(executable or "")
    workspace = codex_art._managed_directory(f"pixel-{unit_id.replace('_', '-')}")
    target = workspace / "sprite.png"
    rules = "\n".join(f"- {rule}" for rule in direction.get("rules", []))
    # No character or franchise names in a prompt (owner rule; prompt_scrub).
    prompt = PROMPT.format(subject=scrub(subject), style=PIXEL_STYLE, rules=rules)
    check(prompt)
    ok, output = codex_art._codex_image(executable or "", environment, workspace, prompt, target,
                                        subprocess.run, "gpt-6-luna")
    if not ok:
        if codex_art.QUOTA.search(output) and not codex_art.MODERATION.search(output):
            return {"unit": unit_id, "state": "quota_paused"}
        return {"unit": unit_id, "state": "failed", "reason": "no image produced"}
    unit_dir = UNITS / unit_id.replace("_", "-")
    preview = str(preview_dir / f"{unit_id}.png") if preview_dir else ""
    script = PIXELIZE.format(tools=str(ROOT / "production/tools"), src=str(target), preview=preview,
                             unit_dir=str(unit_dir))
    done = subprocess.run([str(codex_art.art_python()), "-c", script], capture_output=True, text=True,
                          timeout=300, check=False)
    if done.returncode:
        return {"unit": unit_id, "state": "failed", "reason": (done.stderr or done.stdout)[-300:]}
    return {"unit": unit_id, "state": "generated", "master": str(target)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", action="append")
    parser.add_argument("--preview-dir", type=Path, help="write pixelized previews here instead of unit frames")
    args = parser.parse_args()
    direction = codex_art.load_direction(ROOT)
    units = args.only or sorted(u for u in direction["units"] if (UNITS / u.replace("_", "-")).is_dir())
    if args.preview_dir:
        args.preview_dir.mkdir(parents=True, exist_ok=True)
    results = []
    for unit_id in units:
        outcome = generate(unit_id, direction, args.preview_dir)
        results.append(outcome)
        print(json.dumps(outcome), flush=True)
        if outcome["state"] == "quota_paused":
            break
    return 0 if all(r["state"] == "generated" for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
