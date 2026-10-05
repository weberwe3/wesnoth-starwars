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
{corrections}
After saving, reply with only the file name."""

NEW_PROMPT = """Use your image generation tool to create exactly ONE original image: a single full-body game unit sprite for a turn-based tactics game, in a relaxed three-quarter view turned slightly to the right, on a TRANSPARENT background, the whole subject centered with an empty margin. Save it as sprite.png in the current working directory. Do not create any other files.

Subject: {subject}

The attached images are STYLE references only: match their pixel-art style -- proportions, dark outline, shading, palette depth and size -- but draw a new, different subject as described. Do not copy any character from them.

Rules:
- No text, letters, numbers, logos, watermarks, borders, ground or shadows.

After saving, reply with only the file name."""

REPAIR_PROMPT = """Use your image generation tool to create exactly ONE original image: the single pixel-art game character from the attached image, redrawn on a TRANSPARENT background. Save it as sprite.png in the current working directory. Do not create any other files.

The attached image is an enlarged crop of a sprite sheet: one character standing on the sheet's background (a pale marble texture or a dark card), possibly with guide lines, a shadow disc, card decoration or parts of neighbouring sprites at the edges. Keep ONLY the central character and redraw it exactly: the same pose, design, colours, proportions, outline and pixel-art style, with every part of the body and equipment complete, including light and white areas such as armour, clothing and boots. Remove the background, lines, shadow and anything else that is not part of the character.

Rules:
- One character only, centered, with an empty margin.
- No text, letters, numbers, logos, watermarks, borders, ground or shadows.
{corrections}
After saving, reply with only the file name."""

# Fit a repaired sheet sprite like an imported one and report what evaluate_repair checks.
REPAIR_FIT = """
import sys, json
sys.path.insert(0, {tools!r})
import numpy as np
from PIL import Image
from derive_unit_frames import degenerate_reason, remove_flat_background
from import_sheet_sprites import fit
img = remove_flat_background(Image.open({src!r})); img = img.crop(img.getbbox())
aspect = img.width / img.height
img = img.resize((max(1, round(img.width * 64 / img.height)), 64), Image.LANCZOS) if img.height > 64 else img
alpha = img.getchannel("A").point(lambda v: 255 if v >= 110 else 0)
rgb = Image.new("RGB", img.size, (0, 0, 0)); rgb.paste(img.convert("RGB"), mask=alpha)
rgb = rgb.quantize(colors=48, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE).convert("RGBA"); rgb.putalpha(alpha)
out = fit(rgb)
out.save({dest!r}, optimize=True)
crop = np.asarray(Image.open({crop!r}).convert("RGB"), dtype=float).reshape(-1, 3)
pal = crop[np.random.default_rng(0).choice(len(crop), min(4000, len(crop)), replace=False)]
px = np.asarray(out.convert("RGB"), dtype=float)[np.asarray(out.getchannel("A")) > 0]
err = float(np.sqrt(((px[:, None, :] - pal[None]) ** 2).sum(-1)).min(1).mean()) if len(px) else 999.0
print(json.dumps({{"aspect": aspect, "colour_error": err, "degenerate": degenerate_reason(out, 12)}}))
"""


RESTYLE_PROMPT = """Use your image generation tool to create exactly ONE original image: {framing}, on a TRANSPARENT background, the whole subject centered with an empty margin. Save it as {name} in the current working directory. Do not create any other files.

The FIRST attached image is the subject reference: keep its design, markings and colours{view}. The OTHER attached images are STYLE references only: redraw the subject in exactly their pixel-art style -- proportions, dark outline, shading, palette depth and size. Do not copy any character from them.

Subject: {subject}

Rules:
- One subject only.
- No text, letters, numbers, logos, watermarks, borders, ground or shadows.
{corrections}
After saving, reply with only the file name."""

CHARACTER_FRAMING = ("a single full-body game unit sprite for a turn-based tactics game, in a relaxed "
                     "three-quarter view turned slightly to the right")
CRAFT_FRAMING = ("a single game unit sprite of the craft for a turn-based tactics game, in a three-quarter "
                 "view from above, angled toward the lower right")
CRAFT_VIEW = (" (it is drawn there from directly above; show the same craft from the three-quarter view "
              "described)")
CRAFT_BACKGROUND = (" (it may be a detailed render or sit on a scenic background; keep only the craft, "
                    "simplified into pixel art)")
REFERENCES = Path.home() / "art-references"   # licensed reference images, kept out of the repository
REFERENCE_MAP = Path(__file__).resolve().parent / "reference_sprite_map.json"


def evaluate_repair(report: dict, colours: bool = True, upright: bool = True) -> list[str]:
    issues = []
    if report["degenerate"]:
        issues.append("The result was a flat or empty shape; redraw the full detailed character.")
    if colours and report["colour_error"] > MAX_COLOUR_ERROR:
        issues.append("Keep the character's exact colours from the attached image; do not recolour it.")
    if upright and report["aspect"] > 0.9:
        issues.append("Draw only the one standing character, upright and full-body; leave out neighbouring "
                      "sprites and any props lying beside it.")
    return issues


# Cut the poses out of a generated strip, fit them to the reference, write
# frames to a staging folder and print the measurements evaluate() checks.
SLICE = """
import sys, json
sys.path.insert(0, {tools!r})
import numpy as np
from PIL import Image
from derive_unit_frames import degenerate_reason, remove_flat_background
SPRITE = 72
ref = Image.open({ref!r}).convert("RGBA")
rb = ref.getbbox(); ref_h = rb[3] - rb[1]; ref_bottom = rb[3]
ref_fig = ref.crop(rb)
# The reference palette (adaptive, from the reference's own pixels).
pal_src = Image.new("RGB", ref_fig.size, (0, 0, 0)); pal_src.paste(ref_fig.convert("RGB"), mask=ref_fig.getchannel("A"))
palette = pal_src.quantize(colors=64, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
pal = np.array(palette.getpalette()[:64 * 3], dtype=float).reshape(-1, 3)
strip = remove_flat_background(Image.open({src!r}))
a = np.asarray(strip.getchannel("A")) > 40
cols = a.any(axis=0)
# Figures: runs of occupied columns separated by empty gaps.
runs, start = [], None
for x, filled in enumerate(list(cols) + [False]):
    if filled and start is None: start = x
    if not filled and start is not None:
        runs.append((start, x)); start = None
small = max(8, strip.width // 100)
runs = [r for r in runs if r[1] - r[0] >= small]
want = {count}
report = {{"figures": len(runs), "frames": {{}}}}
if len(runs) >= want:
    widest = sorted(runs, key=lambda r: -(r[1] - r[0]))
    # Pieces beyond the wanted figures that are large enough to be props or extra characters.
    report["extra"] = sum(1 for r in widest[want:] if r[1] - r[0] >= (widest[want - 1][1] - widest[want - 1][0]) // 3)
    runs = sorted(widest[:want])
    names = {names!r}
    lying = {lying!r}
    masks = []
    figs = []
    for x0, x1 in runs:
        fig = strip.crop((x0, 0, x1, strip.height)); figs.append(fig.crop(fig.getbbox()))
    # One scale for the whole strip, so the poses keep the sizes Codex drew them
    # at relative to each other. The scale matches the figures' average body
    # area to the reference's: unlike height, area is not thrown off by a
    # raised blade, a crouch or a fall.
    def area(im):
        return int((np.asarray(im.getchannel("A")) > 110).sum())
    scale = (area(ref_fig) / (sum(area(f) for f in figs) / len(figs))) ** 0.5
    scale = min([scale] + [min(70 / f.width, 70 / f.height) for f in figs])
    for name, fig in zip(names, figs):
        source_aspect = fig.width / fig.height
        fig = fig.resize((max(1, round(fig.width * scale)), max(1, round(fig.height * scale))), Image.LANCZOS)
        alpha = fig.getchannel("A").point(lambda v: 255 if v >= 110 else 0)
        px = np.asarray(fig.convert("RGB"), dtype=float)[np.asarray(alpha) > 0]
        # How far the drawn colours are from the reference's palette (before snapping to it).
        colour_error = float(np.sqrt(((px[:, None, :] - pal[None]) ** 2).sum(-1)).min(1).mean()) if len(px) else 999.0
        rgb = Image.new("RGB", fig.size, (0, 0, 0)); rgb.paste(fig.convert("RGB"), mask=alpha)
        rgb = rgb.quantize(palette=palette, dither=Image.Dither.NONE).convert("RGBA"); rgb.putalpha(alpha)
        frame = Image.new("RGBA", (SPRITE, SPRITE), (0, 0, 0, 0))
        frame.alpha_composite(rgb, ((SPRITE - rgb.width) // 2, min(SPRITE - rgb.height, ref_bottom - rgb.height)))
        frame.save({stage!r} + "/" + name + ".png", optimize=True)
        masks.append(np.asarray(frame.getchannel("A")) > 0)
        report["frames"][name] = {{"aspect": source_aspect, "colour_error": colour_error,
                                   "degenerate": degenerate_reason(frame, 12)}}
    if len(masks) == 2:
        union = (masks[0] | masks[1]).sum()
        report["pose_change"] = float((masks[0] ^ masks[1]).sum() / max(1, union))
print(json.dumps(report))
"""

# Automatic evaluation thresholds (measured on the Han pilot, 2026-10-04).
MAX_COLOUR_ERROR = 18.0     # mean RGB distance of drawn pixels to the reference palette
MIN_POSE_CHANGE = 0.12      # share of the two frames' silhouettes that differs
MIN_LYING_ASPECT = 1.3      # width / height of a fallen figure
MAX_UPRIGHT_ASPECT = 1.25   # width / height of a standing pose (not a lunge)


def evaluate(animation: str, names: list[str], report: dict) -> list[str]:
    """Targeted corrections for the next attempt, or [] if the frames pass."""
    count = len(names)
    if report["figures"] < count:
        return [f"The image must show exactly {count} separate full-body figures side by side, with wide "
                "empty transparent gaps between them; no figure may touch or overlap another."]
    issues = []
    if report.get("extra"):
        issues.append(f"Draw only the {count} figures: no extra characters, props on the ground, effects, "
                      "copies or partial figures.")
    for name, frame in report["frames"].items():
        n = names.index(name) + 1
        if frame["degenerate"]:
            issues.append(f"Frame {n} came out as a flat or empty shape; draw the full detailed character.")
        if frame["colour_error"] > MAX_COLOUR_ERROR:
            issues.append(f"Frame {n} changed the character's colours; use exactly the reference's colours for "
                          "skin, hair, clothing and equipment, with no new colours or lighting tints.")
        if name == "death-2" and frame["aspect"] < MIN_LYING_ASPECT:
            issues.append(f"Frame {n} must show the character lying flat on the ground, body horizontal, "
                          "much wider than tall.")
        if animation in ("ranged", "defend", "idle") and frame["aspect"] > MAX_UPRIGHT_ASPECT:
            issues.append(f"Frame {n} must stay upright on both feet, not lunging, crouching low or falling.")
    if report.get("pose_change", 1.0) < MIN_POSE_CHANGE:
        issues.append("The frames are almost identical; make each pose clearly different, as described.")
    return issues


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
    # -i takes several files, so the images go before another option: placed
    # last, the "-" (prompt on stdin) would be read as one more image.
    command = [executable, "exec", *attached, "--skip-git-repo-check", "-C", codex_art._windows_path(workspace),
               "-m", "gpt-6-luna", "-c", 'model_reasoning_effort="low"', "-c", 'web_search="disabled"',
               "--approve-for-me", "--ephemeral", "--color", "never", "-"]
    started = time.time()
    try:
        done = subprocess.run(command, cwd=workspace, env=environment, input=prompt, text=True,
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                              timeout=codex_art.CODEX_TIMEOUT_SECONDS, check=False)
        output = done.stdout or ""
    except subprocess.TimeoutExpired:
        output = ""
    # Keep Codex's reply for diagnosis (a refusal or tool error leaves no image).
    (workspace / f"codex-output-{target.stem}.txt").write_text(output, encoding="utf-8")
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


def animate(unit_id: str, dest: Path, animations: list[str], attempts: int = 3,
            notes: dict[str, str] | None = None, force: bool = False, standing: Path | None = None) -> dict:
    """Generate, evaluate and write each animation; a failing attempt is retried
    with the evaluation's corrections added to the prompt. An animation whose
    frames are already in dest is kept unless force or a note asks for a redo."""
    standing = standing or UNITS / unit_id.replace("_", "-") / "standing.png"
    if not standing.exists():
        return {"unit": unit_id, "state": "failed", "reason": "no standing sprite"}
    notes = notes or {}
    log = {"unit": unit_id, "state": "generated", "animations": {}}
    for animation in animations:
        names, poses = ANIMATIONS[animation]
        done_marker = dest / f".{animation}.passed"
        if done_marker.exists() and not force and animation not in notes:
            log["animations"][animation] = "kept"
            continue
        corrections = [notes[animation]] if animation in notes else []
        history = []
        for attempt in range(1, attempts + 1):
            workspace = codex_art._managed_directory(
                f"anim-{unit_id.replace('_', '-')}-{animation}-{attempt}")
            ref = enlarged(standing, workspace)
            text = "".join(f"- Correction: {c}\n" for c in corrections)
            prompt = PROMPT.format(count=len(names),
                                   poses="\n".join(f"{i + 1}. {p}" for i, p in enumerate(poses)),
                                   corrections=text)
            ok, output = _codex_with_refs(prompt, [ref], workspace / "frames.png", unit_id)
            if not ok:
                if codex_art.QUOTA.search(output) and not codex_art.MODERATION.search(output):
                    log.update(state="quota_paused", at=animation)
                    return log
                history.append({"attempt": attempt, "issues": ["no image produced"]})
                continue
            stage = workspace / "stage"
            stage.mkdir(exist_ok=True)
            script = SLICE.format(tools=str(ROOT / "production/tools"), ref=str(standing),
                                  src=str(workspace / "frames.png"), count=len(names), names=names,
                                  lying=["death-2"], stage=str(stage))
            run = subprocess.run([str(codex_art.art_python()), "-c", script], capture_output=True, text=True,
                                 timeout=300, check=False)
            if run.returncode:
                history.append({"attempt": attempt, "issues": [(run.stderr or run.stdout)[-300:]]})
                continue
            issues = evaluate(animation, names, json.loads(run.stdout.strip().splitlines()[-1]))
            history.append({"attempt": attempt, "issues": issues})
            if not issues:
                for name in names:
                    shutil.copyfile(stage / f"{name}.png", dest / f"{name}.png")
                done_marker.write_text(json.dumps(history), encoding="utf-8")
                break
            corrections = ([notes[animation]] if animation in notes else []) + issues
        else:
            log["state"] = "failed"
        log["animations"][animation] = history
    return log


def _crop_reference(image: Path, box: list[int], workspace: Path) -> tuple[Path, Path]:
    """The reference crop, plus an enlarged copy (pixel art stays crisp) for Codex."""
    crop, big = workspace / "crop.png", workspace / "crop-big.png"
    subprocess.run([str(codex_art.art_python()), "-c",
                    "from PIL import Image; i = Image.open(%r).convert('RGBA'); w = Image.new('RGBA', i.size, 'white'); "
                    "w.alpha_composite(i); c = w.convert('RGB').crop(tuple(%r)); c.save(%r); "
                    "k = max(1, 600 // max(c.size)); c.resize((c.width * k, c.height * k), Image.NEAREST).save(%r)"
                    % (str(image), list(box), str(crop), str(big))],
                   check=True, capture_output=True, timeout=120)
    return crop, big


def _redraw_loop(unit_id: str, prompt_for, refs: list[Path], crop: Path, workspace: Path, dest: Path,
                 attempts: int, colours: bool, upright: bool) -> dict:
    """Ask Codex for one standing sprite, fit and evaluate it, retry with corrections."""
    corrections: list[str] = []
    history = []
    for attempt in range(1, attempts + 1):
        target = workspace / f"sprite-{attempt}.png"
        prompt = prompt_for(target.name, "".join(f"- Correction: {c}\n" for c in corrections))
        ok, output = _codex_with_refs(prompt, refs, target, unit_id)
        if not ok:
            if codex_art.QUOTA.search(output) and not codex_art.MODERATION.search(output):
                return {"unit": unit_id, "state": "quota_paused", "history": history}
            history.append({"attempt": attempt, "issues": ["no image produced"]})
            continue
        script = REPAIR_FIT.format(tools=str(ROOT / "production/tools"), src=str(target),
                                   dest=str(dest / "standing.png"), crop=str(crop))
        run = subprocess.run([str(codex_art.art_python()), "-c", script], capture_output=True, text=True,
                             timeout=300, check=False)
        if run.returncode:
            history.append({"attempt": attempt, "issues": [(run.stderr or run.stdout)[-300:]]})
            continue
        issues = evaluate_repair(json.loads(run.stdout.strip().splitlines()[-1]), colours, upright)
        history.append({"attempt": attempt, "issues": issues})
        if not issues:
            return {"unit": unit_id, "state": "generated", "history": history}
        corrections = issues
    return {"unit": unit_id, "state": "failed", "history": history}


def repair_standing(unit_id: str, entry: dict, sheet_path: Path, dest: Path, attempts: int) -> dict:
    """Redraw a sheet sprite whose cut-out failed (white figures on the white
    marble) from its sheet crop, on a transparent background."""
    workspace = codex_art._managed_directory(f"repair-{unit_id.replace('_', '-')}")
    x, y = entry["at"]
    crop, big = _crop_reference(sheet_path, [x - 55, y - 60, x + 55, y + 60], workspace)
    return _redraw_loop(unit_id, lambda name, c: REPAIR_PROMPT.format(corrections=c).replace("sprite.png", name),
                        [big], crop, workspace, dest, attempts, colours=True, upright=True)


def reference_standing(unit_id: str, entry: dict, subject: str, style_refs: list[str], dest: Path,
                       attempts: int) -> dict:
    """A standing sprite from a licensed reference image (reference_sprite_map.json):
    "redraw" copies a sprite already in the house style onto a transparent
    background; "restyle" redraws another artist's subject in the house style,
    with imported sheet sprites attached as style references."""
    workspace = codex_art._managed_directory(f"ref-{unit_id.replace('_', '-')}")
    crop, big = _crop_reference(REFERENCES / entry["source"], entry["box"], workspace)
    craft = bool(entry.get("craft"))
    if entry["how"] == "redraw":
        return _redraw_loop(unit_id, lambda name, c: REPAIR_PROMPT.format(corrections=c).replace("sprite.png", name),
                            [big], crop, workspace, dest, attempts, colours=True, upright=True)
    styles = [enlarged(UNITS / r.replace("_", "-") / "standing.png", workspace) for r in style_refs]

    def prompt_for(name: str, corrections: str) -> str:
        return RESTYLE_PROMPT.format(framing=CRAFT_FRAMING if craft else CHARACTER_FRAMING, name=name,
                                     view=(CRAFT_VIEW if entry.get("view") == "top" else CRAFT_BACKGROUND) if craft else "",
                                     subject=scrub(subject),
                                     corrections=corrections)
    return _redraw_loop(unit_id, prompt_for, [big, *styles], crop, workspace, dest, attempts,
                        colours=False, upright=not craft)


def derive_craft_frames(dest: Path) -> None:
    """Craft frames come from the standing sprite (no walking or falling poses)."""
    script = ("import sys; sys.path.insert(0, %r); from PIL import Image; from derive_unit_frames import derive; "
              "[f.save(%r + '/' + k + '.png', optimize=True) for k, f in derive(Image.open(%r + '/standing.png')"
              ".convert('RGBA')).items() if k != 'standing']" % (str(ROOT / "production/tools"), str(dest), str(dest)))
    subprocess.run([str(codex_art.art_python()), "-c", script], check=True, capture_output=True, timeout=300)


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
    parser.add_argument("--mode", choices=("animate", "new", "repair", "reference"), required=True)
    parser.add_argument("--sheet", type=Path, help="the SacraiCross sheet (repair mode)")
    parser.add_argument("--only", action="append")
    parser.add_argument("--style-ref", action="append",
                        default=["sw_unit_im_stormtrooper", "sw_hero_han", "sw_hero_chewbacca"])
    parser.add_argument("--preview-dir", type=Path, help="write animation frames here instead of the unit folder")
    parser.add_argument("--animations", nargs="+", choices=sorted(ANIMATIONS), default=sorted(ANIMATIONS),
                        help="animations to draw (idle is usually kept as derived from the standing frame)")
    parser.add_argument("--attempts", type=int, default=3, help="tries per animation before giving up")
    parser.add_argument("--note", action="append", default=[], metavar="UNIT:ANIMATION:TEXT",
                        help="a reviewer's correction for one animation; that animation is redone")
    parser.add_argument("--force", action="store_true", help="redo animations that already passed")
    args = parser.parse_args()
    direction = codex_art.load_direction(ROOT)
    on_sheet = set(json.loads(SHEET_MAP.read_text(encoding="utf-8")))
    sheet = json.loads(SHEET_MAP.read_text(encoding="utf-8"))
    notes: dict[str, dict[str, str]] = {}
    for note in args.note:
        unit, animation, text = note.split(":", 2)
        notes.setdefault(unit, {})[animation] = text
    if args.mode == "animate":
        units = args.only or sorted(u for u in on_sheet if not sheet[u].get("skip"))
    else:
        units = args.only or sorted(u for u in direction["units"]
                                    if u not in on_sheet and (UNITS / u.replace("_", "-")).is_dir())
    if args.mode == "reference":
        # Units with a licensed reference image: standing sprite, then frames, into the preview folder.
        if not args.preview_dir:
            parser.error("reference needs --preview-dir")
        refmap = json.loads(REFERENCE_MAP.read_text(encoding="utf-8"))["units"]
        results = []
        for unit_id in args.only or sorted(refmap):
            entry = refmap[unit_id]
            if entry.get("hold"):
                print(json.dumps({"unit": unit_id, "state": "held", "reason": entry["hold"]}), flush=True)
                continue
            dest = args.preview_dir / f"{unit_id}@{Path(entry['source']).stem}"
            dest.mkdir(parents=True, exist_ok=True)
            if (dest / "standing.png").exists() and not args.force:
                outcome = {"unit": unit_id, "state": "generated", "history": "kept"}
            else:
                outcome = reference_standing(unit_id, entry, direction["units"].get(unit_id, ""),
                                             args.style_ref, dest, args.attempts)
            if outcome["state"] == "generated":
                if entry.get("craft"):
                    derive_craft_frames(dest)
                else:
                    outcome["frames"] = animate(unit_id, dest, args.animations, args.attempts,
                                                notes.get(unit_id), args.force, dest / "standing.png")
                    outcome["state"] = outcome["frames"]["state"]
            results.append(outcome)
            print(json.dumps(outcome), flush=True)
            if outcome["state"] == "quota_paused" or outcome.get("frames", {}).get("state") == "quota_paused":
                break
        return 0 if all(r["state"] == "generated" for r in results) else 1
    if args.mode == "repair":
        # Skipped sheet units: redraw the standing sprite into the preview folder only.
        if not args.sheet or not args.preview_dir:
            parser.error("repair needs --sheet and --preview-dir")
        results = []
        for unit_id in args.only or sorted(u for u in on_sheet if sheet[u].get("skip")):
            dest = args.preview_dir / unit_id
            dest.mkdir(parents=True, exist_ok=True)
            if (dest / "standing.png").exists() and not args.force:
                outcome = {"unit": unit_id, "state": "generated", "history": "kept"}
            else:
                outcome = repair_standing(unit_id, sheet[unit_id], args.sheet, dest, args.attempts)
            if outcome["state"] == "generated":
                outcome["frames"] = animate(unit_id, dest, args.animations, args.attempts,
                                            notes.get(unit_id), args.force, dest / "standing.png")
                outcome["state"] = outcome["frames"]["state"]
            results.append(outcome)
            print(json.dumps(outcome), flush=True)
            if outcome["state"] == "quota_paused":
                break
        return 0 if all(r["state"] == "generated" for r in results) else 1
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
        outcome = animate(unit_id, dest, args.animations, args.attempts, notes.get(unit_id), args.force)
        results.append(outcome)
        print(json.dumps(outcome), flush=True)
        if outcome["state"] == "quota_paused":
            break
    return 0 if all(r["state"] == "generated" for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
