#!/usr/bin/env python3
"""Animate unit sprites with Codex, using exported sheet sprites as references.

Owner direction (2026-10-04): every unit's animation frames are drawn from a
reference sprite, so the whole set keeps the character's exact design.

  animate  a unit whose standing sprite was exported from SacraiCross's
           collection sheet (import_sheet_sprites.py; CC BY-SA, credited in
           docs/ART_CREDITS.md). That sprite is the reference: it stays the
           standing frame, and Codex draws the other poses of the same
           character from it.
  new      a unit the sheet does not have (Noghri, natives, droids,
           vehicles): Codex first draws its standing sprite from the unit's
           art-direction subject, with a few exported sprites attached as
           style references, then it is animated like the others.

One Codex call per animation draws that animation's poses side by side
(a small sprite sheet): idle, move, melee, ranged, defend, death. Each pose
is cut out, scaled to the reference figure's height, mapped to the
reference sprite's palette, and placed like the standing frame. The firing
pose carries no muzzle flash: the unit WML draws one in the shot's colour.

Run only while no other Codex art generation is active.
Usage: python3 production/tools/gen_codex_reference_frames.py --mode animate|new [--only UNIT_ID ...]
       [--style-ref UNIT_ID ...] [--preview-dir DIR]
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "agent" / "coordinator"))
import codex_art  # noqa: E402
import ticket_runner  # noqa: E402
sys.path.insert(0, str(Path(__file__).resolve().parent))
from prompt_scrub import check, scrub  # noqa: E402

UNITS = ROOT / "addons/Star_Wars_Thrawn_Trilogy/images/units"
SHEET_MAP = Path(__file__).resolve().parent / "sheet_sprite_map.json"

# animation -> (frame files, poses described left to right)
ANIMATIONS = {
    "idle": (["idle-1", "idle-2"], ["breathing in, shoulders slightly raised",
                                    "breathing out, weight shifted a little"]),
    "move": (["move-1", "move-2"], ["mid-stride walking to the right, left foot forward",
                                    "mid-stride walking to the right, right foot forward"]),
    "melee": (["melee-1", "melee-2"], ["winding up a close-combat strike with the melee weapon or fists",
                                       "the strike landing, leaning into it"]),
    "ranged": (["ranged-1", "ranged-2"], ["aiming the ranged weapon to the right",
                                          "firing to the right with a slight recoil (no muzzle flash, no "
                                          "projectile)"]),
    "defend": (["defend"], ["flinching from a hit, guarding"]),
    "death": (["death-1", "death-2"], ["collapsing, knees buckling", "fallen and lying on the ground"]),
}

PROMPT = """Use your image generation tool to create exactly ONE original image: a small sprite sheet of {count} animation frames of the SAME game character, arranged left to right in one row with clear empty space between them, on a TRANSPARENT background. Save it as frames.png in the current working directory. Do not create any other files.

The attached image is the character reference: copy its exact design, colours, proportions, outline, size and pixel-art style. Do not redesign or restyle it, do not add or remove equipment.

Frames, left to right:
{poses}

Rules:
- One character per frame, the same character in every frame, all frames the same scale as the reference.
- No text, letters, numbers, logos, watermarks, borders, ground or shadows.

After saving, reply with only the file name."""

NEW_PROMPT = """Use your image generation tool to create exactly ONE original image: a single full-body game unit sprite for a turn-based tactics game, in a relaxed three-quarter view turned slightly to the right, on a TRANSPARENT background, the whole subject centered with an empty margin. Save it as sprite.png in the current working directory. Do not create any other files.

Subject: {subject}

The attached images are STYLE references only: match their pixel-art style -- proportions, dark outline, shading, palette depth and size -- but draw a new, different subject as described. Do not copy any character from them.

Rules:
- No text, letters, numbers, logos, watermarks, borders, ground or shadows.

After saving, reply with only the file name."""

# Cut the poses out of a generated strip, fit them to the reference, write frames.
SLICE = """
import sys, json
sys.path.insert(0, {tools!r})
import numpy as np
from PIL import Image
from derive_unit_frames import remove_flat_background
SPRITE = 72
ref = Image.open({ref!r}).convert("RGBA")
rb = ref.getbbox(); ref_h = rb[3] - rb[1]; ref_bottom = rb[3]
ref_fig = ref.crop(rb)
# The reference palette (adaptive, from the reference's own pixels).
pal_src = Image.new("RGB", ref_fig.size, (0, 0, 0)); pal_src.paste(ref_fig.convert("RGB"), mask=ref_fig.getchannel("A"))
palette = pal_src.quantize(colors=64, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
strip = remove_flat_background(Image.open({src!r}))
a = np.asarray(strip.getchannel("A")) > 40
cols = a.any(axis=0)
# Figures: runs of occupied columns separated by empty gaps.
runs, start = [], None
for x, filled in enumerate(list(cols) + [False]):
    if filled and start is None: start = x
    if not filled and start is not None:
        runs.append((start, x)); start = None
runs = [r for r in runs if r[1] - r[0] >= 8]
want = {count}
if len(runs) < want:
    raise SystemExit(f"found {{len(runs)}} figures, wanted {{want}}")
runs = sorted(sorted(runs, key=lambda r: -(r[1] - r[0]))[:want])
out = {{}}
names = {names!r}
lying = {lying!r}
for name, (x0, x1) in zip(names, runs):
    fig = strip.crop((x0, 0, x1, strip.height)); fig = fig.crop(fig.getbbox())
    # Upright poses match the reference height; a lying pose matches its width to that height.
    scale = (ref_h / fig.width) if name in lying else (ref_h / fig.height)
    scale = min(scale, 70 / fig.width, 70 / fig.height)
    fig = fig.resize((max(1, round(fig.width * scale)), max(1, round(fig.height * scale))), Image.LANCZOS)
    alpha = fig.getchannel("A").point(lambda v: 255 if v >= 110 else 0)
    rgb = Image.new("RGB", fig.size, (0, 0, 0)); rgb.paste(fig.convert("RGB"), mask=alpha)
    rgb = rgb.quantize(palette=palette, dither=Image.Dither.NONE).convert("RGBA"); rgb.putalpha(alpha)
    frame = Image.new("RGBA", (SPRITE, SPRITE), (0, 0, 0, 0))
    frame.alpha_composite(rgb, ((SPRITE - rgb.width) // 2, min(SPRITE - rgb.height, ref_bottom - rgb.height)))
    frame.save({dest!r} + "/" + name + ".png", optimize=True)
print("ok")
"""


def _codex_with_refs(prompt: str, refs: list[Path], target: Path, label: str) -> tuple[bool, str]:
    # No character or franchise names in a prompt (owner rule; prompt_scrub).
    check(prompt)
    executable = ticket_runner.resolve_codex_executable() or ""
    environment = ticket_runner.require_codex_chatgpt_quota(executable)
    workspace = target.parent
    attached = []
    for i, ref in enumerate(refs):
        local = workspace / f"reference-{i + 1}.png"
        shutil.copyfile(ref, local)
        attached += ["-i", codex_art._windows_path(local)]
    command = [executable, "exec", "--skip-git-repo-check", "-C", codex_art._windows_path(workspace),
               "-m", "gpt-6-luna", "-c", 'model_reasoning_effort="low"', "-c", 'web_search="disabled"',
               "--approve-for-me", "--ephemeral", "--color", "never", *attached, "-"]
    started = time.time()
    try:
        done = subprocess.run(command, cwd=workspace, env=environment, input=prompt, text=True,
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                              timeout=codex_art.CODEX_TIMEOUT_SECONDS, check=False)
        output = done.stdout or ""
    except subprocess.TimeoutExpired:
        output = ""
    if not codex_art._valid_png(target):
        home = Path(environment["CODEX_HOME"]) if environment.get("CODEX_HOME") else None
        made = [p for p in codex_art.harvest_generated(home, started, time.time()) if codex_art._valid_png(p)]
        if made:
            target.write_bytes(made[-1].read_bytes())
    del label
    return codex_art._valid_png(target), output


def enlarged(path: Path, workspace: Path) -> Path:
    """A crisp 8x copy of a 72x72 sprite, so the model sees the pixels clearly."""
    out = workspace / f"{path.parent.name}-ref.png"
    subprocess.run([str(codex_art.art_python()), "-c",
                    "from PIL import Image; im = Image.open(%r).convert('RGBA'); "
                    "im.crop(im.getbbox()).resize((im.getbbox()[2] * 0 + (im.getbbox()[2] - im.getbbox()[0]) * 8, "
                    "(im.getbbox()[3] - im.getbbox()[1]) * 8), Image.NEAREST).save(%r)" % (str(path), str(out))],
                   check=True, capture_output=True, timeout=60)
    return out


def animate(unit_id: str, dest: Path) -> dict:
    standing = UNITS / unit_id.replace("_", "-") / "standing.png"
    if not standing.exists():
        return {"unit": unit_id, "state": "failed", "reason": "no standing sprite"}
    for animation, (names, poses) in ANIMATIONS.items():
        workspace = codex_art._managed_directory(f"anim-{unit_id.replace('_', '-')}-{animation}")
        ref = enlarged(standing, workspace)
        prompt = PROMPT.format(count=len(names),
                               poses="\n".join(f"{i + 1}. {p}" for i, p in enumerate(poses)))
        ok, output = _codex_with_refs(prompt, [ref], workspace / "frames.png", unit_id)
        if not ok:
            if codex_art.QUOTA.search(output) and not codex_art.MODERATION.search(output):
                return {"unit": unit_id, "state": "quota_paused", "at": animation}
            return {"unit": unit_id, "state": "failed", "at": animation, "reason": "no image produced"}
        script = SLICE.format(tools=str(ROOT / "production/tools"), ref=str(standing),
                              src=str(workspace / "frames.png"), count=len(names), names=names,
                              lying=["death-2"], dest=str(dest))
        done = subprocess.run([str(codex_art.art_python()), "-c", script], capture_output=True, text=True,
                              timeout=300, check=False)
        if done.returncode:
            return {"unit": unit_id, "state": "failed", "at": animation, "reason": (done.stderr or done.stdout)[-300:]}
    return {"unit": unit_id, "state": "generated"}


def new_standing(unit_id: str, direction: dict, style_refs: list[str]) -> dict:
    subject = direction["units"].get(unit_id)
    if not subject:
        return {"unit": unit_id, "state": "failed", "reason": "no art direction"}
    workspace = codex_art._managed_directory(f"new-{unit_id.replace('_', '-')}")
    refs = [enlarged(UNITS / r.replace("_", "-") / "standing.png", workspace) for r in style_refs]
    ok, output = _codex_with_refs(NEW_PROMPT.format(subject=scrub(subject)), refs, workspace / "sprite.png", unit_id)
    if not ok:
        if codex_art.QUOTA.search(output) and not codex_art.MODERATION.search(output):
            return {"unit": unit_id, "state": "quota_paused"}
        return {"unit": unit_id, "state": "failed", "reason": "no image produced"}
    # Fit like a sheet sprite (~64 px figure, bottom-anchored), palette from the style references.
    script = f"""
import sys
sys.path.insert(0, {str(ROOT / 'production/tools')!r})
from PIL import Image
from derive_unit_frames import degenerate_reason, remove_flat_background
img = remove_flat_background(Image.open({str(workspace / 'sprite.png')!r})); img = img.crop(img.getbbox())
s = min(64 / img.height, 70 / img.width)
img = img.resize((max(1, round(img.width * s)), max(1, round(img.height * s))), Image.LANCZOS)
alpha = img.getchannel("A").point(lambda v: 255 if v >= 110 else 0)
rgb = Image.new("RGB", img.size, (0, 0, 0)); rgb.paste(img.convert("RGB"), mask=alpha)
rgb = rgb.quantize(colors=64, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE).convert("RGBA"); rgb.putalpha(alpha)
out = Image.new("RGBA", (72, 72), (0, 0, 0, 0)); out.alpha_composite(rgb, ((72 - rgb.width) // 2, 70 - rgb.height))
r = degenerate_reason(out)
if r: raise SystemExit("degenerate: " + r)
out.save({str(UNITS / unit_id.replace('_', '-') / 'standing.png')!r}, optimize=True)
"""
    done = subprocess.run([str(codex_art.art_python()), "-c", script], capture_output=True, text=True,
                          timeout=300, check=False)
    if done.returncode:
        return {"unit": unit_id, "state": "failed", "reason": (done.stderr or done.stdout)[-300:]}
    return {"unit": unit_id, "state": "generated"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("animate", "new"), required=True)
    parser.add_argument("--only", action="append")
    parser.add_argument("--style-ref", action="append",
                        default=["sw_unit_im_stormtrooper", "sw_hero_han", "sw_hero_chewbacca"])
    parser.add_argument("--preview-dir", type=Path, help="write animation frames here instead of the unit folder")
    args = parser.parse_args()
    direction = codex_art.load_direction(ROOT)
    on_sheet = set(json.loads(SHEET_MAP.read_text(encoding="utf-8")))
    if args.mode == "animate":
        units = args.only or sorted(on_sheet)
    else:
        units = args.only or sorted(u for u in direction["units"]
                                    if u not in on_sheet and (UNITS / u.replace("_", "-")).is_dir())
    results = []
    for unit_id in units:
        if args.mode == "new":
            outcome = new_standing(unit_id, direction, args.style_ref)
            print(json.dumps(outcome), flush=True)
            if outcome["state"] != "generated":
                results.append(outcome)
                if outcome["state"] == "quota_paused":
                    break
                continue
        dest = args.preview_dir / unit_id if args.preview_dir else UNITS / unit_id.replace("_", "-")
        dest.mkdir(parents=True, exist_ok=True)
        outcome = animate(unit_id, dest)
        results.append(outcome)
        print(json.dumps(outcome), flush=True)
        if outcome["state"] == "quota_paused":
            break
    return 0 if all(r["state"] == "generated" for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
