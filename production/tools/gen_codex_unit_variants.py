#!/usr/bin/env python3
"""Have Codex draw a new unit as a variant of an existing unit's art.

A new unit type that reuses another unit's sprites cannot be told apart on the
map (2026-10-12: the Smuggler Slicer shipped as a byte-identical copy of the
Smuggler gunhand). This tool gives such a unit its own art by the same rules
as every other redraw (owner rules, 2026-10-10; gen_codex_rank_designs.py):
the source unit's idle sprite is Codex's only reference, and the prompt only
asks for that sprite to be redrawn in a stated way -- no character names, no
setting terms (prompt_scrub checks), no art_direction.json descriptions.

Three steps per unit (jobs in unit_variant_jobs.json: "from" is the source
unit's art folder, "design" the stated changes, "portrait" whether to redraw
the source portrait too, "poses" optional per-frame pose wording that names
which held item an attack uses):

  1. design   -- the source idle sprite is redrawn as a different person of
     the same kind with the stated changes (a before/after sheet; the
     unchanged copy sets the scale).
  2. frames   -- the new idle sprite is redrawn as the full frame set, exactly
     as rank designs are (poses in words, four-frame walk, painted flash in
     the colour of the unit's bolt).
  3. portrait -- the source portrait is redrawn as the same person as the new
     sprite (both attached), then fitted like every other portrait.

Every result must be reviewed by eye before --install. Installed frames go to
units/<slug>/, the portrait to portraits/<slug>.png; afterwards run
scan_muzzle_flashes.py (the new firing frame paints its own flash).

Run only while no other Codex art generation is active.

Usage: python3 production/tools/gen_codex_unit_variants.py --out-dir DIR [--only SLUG ...]
           [--step design|frames|portrait] [--install]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
import gen_codex_rank_designs as r  # noqa: E402
from prompt_scrub import scrub  # noqa: E402

JOBS = TOOLS / "unit_variant_jobs.json"
PORTRAITS = r.UNITS.parent / "portraits"

DESIGN_PROMPT = """Use your image generation tool to create exactly ONE image and save it as {name} in the current working directory. Do not create any other files.

Redraw the attached pixel-art sprite (enlarged, on a flat magenta background) as a different person of the same kind, with these changes: {design}.

The changes must read at a glance at this small sprite size: a clearly different silhouette element and a different main colour. Keep the same: the pixel-art style, dark outline and shading, proportions, head size, overall size, the standing pose, and the three-quarter view facing right.

Make the image a sheet of TWO frames side by side on the same flat magenta background, each labelled in small yellow text above it: before, after. "before" is the attached sprite, unchanged; "after" is the redrawn sprite. Leave a wide empty gap between them and draw nothing else.
{corrections}
After saving, reply with only the file name."""

PORTRAIT_PROMPT = """Use your image generation tool to create exactly ONE image and save it as {name} in the current working directory. Do not create any other files.

The first attached image is a painted head-and-shoulders portrait. The second attached image is a small pixel-art sprite of a different person. Repaint the portrait so that it shows the person from the sprite instead: their face, hair, clothing, colours and equipment, at the same angle and framing. Keep everything else the same: the painting style, lighting, level of detail, the transparent background and the canvas size.
{corrections}
After saving, reply with only the file name."""


# Owner-supplied likeness (job "likeness": a file in ~/art-references). The
# owner's image sets who is shown; a project portrait sets the painting style,
# so the result is a new painting in the house style, not a copy of the
# reference (2026-10-12: Chewbacca's placeholder portrait).
LIKENESS_PROMPT = """Use your image generation tool to create exactly ONE image and save it as {name} in the current working directory. Do not create any other files.

The first attached image is a painted head-and-shoulders portrait: copy its painting style, lighting, level of detail, framing and transparent background. The second attached image shows the subject to paint. Paint a new head-and-shoulders portrait of the subject from the second image -- the same face, fur colour and pattern, and the same bandolier -- in the style and framing of the first image, at the same canvas size. Do not copy the second image's background, text or pose exactly.
{corrections}
After saving, reply with only the file name."""


def workspace_for(slug: str, step: str) -> Path:
    # Codex sees its working directory: the name must not carry the unit's name.
    return r.g.codex_art._managed_directory(f"variant-{step}-" + hashlib.sha1(slug.encode()).hexdigest()[:10])


def import_design(source: str, sheet: Path, out_png: Path) -> str | None:
    """The 'after' frame of the design sheet, as a 72x72 idle sprite."""
    ref = r.UNITS / source / "idle-1.png"
    return r._run(r.COMMON.format(tools=TOOLS) + f"""
figs = cut(r"{sheet}", (2,), r"{ref}")
figs[1].save(r"{out_png}")
print("ok")
""")


def import_frames(slug: str, sheet: Path, design_idle: Path, preview: Path | None, install: bool,
                  source: str) -> str | None:
    rows = r.sheet_rows(slug)
    names = r.install_names(slug)
    dest = r.UNITS / slug
    base = r.UNITS / source
    return r._run(r.COMMON.format(tools=TOOLS) + f"""
names = {names!r}
figs = cut(r"{sheet}", {tuple(len(x) for x in rows)!r}, r"{design_idle}")
out = dict(zip(names, figs))
out["idle-1"] = Image.open(r"{design_idle}").convert("RGBA")   # the approved design itself
preview = {str(preview)!r}
if preview != "None":
    strip = Image.new("RGBA", (len(names) * 144, 288), (70, 90, 60, 255))
    for i, n in enumerate(names):
        if os.path.exists(r"{base}/" + n + ".png"):
            strip.alpha_composite(Image.open(r"{base}/" + n + ".png").convert("RGBA").resize((144, 144), Image.NEAREST), (i * 144, 0))
        strip.alpha_composite(out[n].resize((144, 144), Image.NEAREST), (i * 144, 144))
    strip.save(preview)
if {install!r}:
    os.makedirs(r"{dest}", exist_ok=True)
    for n, f in out.items():
        f.save(r"{dest}/" + n + ".png", optimize=True)
print("ok")
""")


def design_step(slug: str, job: dict, out_dir: Path, attempts: int) -> dict:
    ws = workspace_for(slug, "design")
    ref = ws / "idle-reference.png"
    r.idle_reference(job["from"], ref)
    design_png = out_dir / f"{slug}-design.png"
    prompt = DESIGN_PROMPT.replace("{design}", scrub(job["design"]))
    sheet, history = r.codex_sheet(prompt, ref, ws, "design", attempts,
                                   lambda t: import_design(job["from"], t, design_png))
    if sheet is None:
        return {"unit": slug, "state": "failed", "step": "design", "history": history}
    shutil.copyfile(sheet, out_dir / f"{slug}-design-sheet.png")
    return {"unit": slug, "state": "generated", "step": "design", "history": history}


def frames_step(slug: str, job: dict, out_dir: Path, attempts: int) -> dict:
    design_png = out_dir / f"{slug}-design.png"
    if not design_png.exists():
        return {"unit": slug, "state": "failed", "step": "frames", "history": [{"issue": "no approved design"}]}
    ws = workspace_for(slug, "frames")
    ref = ws / "idle-reference.png"
    r.enlarge(design_png, ref)
    rows = r.sheet_rows(slug)
    # A job may name which held item each attack uses ("poses"): with two items
    # in hand, "the held weapon" is ambiguous (2026-10-12: the slicer fired its
    # handheld screen like a gun).
    poses = {**r.POSES["figure"], **r.POSE_OVERRIDES.get(slug, {}), **job.get("poses", {})}
    lines = "\n".join(f"- {n}: {poses[n].replace('{flash}', r.flash_colour(slug))}." for row in rows for n in row)
    prompt = (r.FRAMES_PROMPT.replace("{top}", ", ".join(rows[0])).replace("{bottom}", ", ".join(rows[1]))
              .replace("{poses}", lines))
    sheet, history = r.codex_sheet(prompt, ref, ws, "frames", attempts,
                                   lambda t: import_frames(slug, t, design_png, out_dir / f"{slug}-preview.png",
                                                           False, job["from"]))
    if sheet is None:
        return {"unit": slug, "state": "failed", "step": "frames", "history": history}
    shutil.copyfile(sheet, out_dir / f"{slug}-frames.png")
    return {"unit": slug, "state": "generated", "step": "frames", "history": history}


def painted(image: Path) -> bool:
    """A head-and-shoulders portrait fills most of its canvas; a returned
    full-body sprite (2026-10-12: the enlarged reference came back) covers
    about a sixth of it. Coverage in thousandths."""
    script = f"""
import numpy as np
from PIL import Image
a = np.asarray(Image.open(r"{image}").convert("RGBA"))
print(int(1000 * (a[..., 3] > 0).mean()))
"""
    import subprocess
    run = subprocess.run([str(r.g.codex_art.art_python()), "-c", script], capture_output=True, text=True, timeout=300)
    return run.returncode == 0 and int(run.stdout.strip() or 0) >= 300


def portrait_step(slug: str, job: dict, out_dir: Path, attempts: int) -> dict:
    # Portrait-only jobs ("portrait_only"): the unit keeps its installed sprites;
    # its own idle sprite is the identity and "portrait_from" the painting to
    # repaint (2026-10-12: the Wookiee Warrior's portrait read as an ape).
    design_png = (r.UNITS / slug / "idle-1.png") if job.get("portrait_only") else out_dir / f"{slug}-design.png"
    source_portrait = PORTRAITS / f"{job.get('portrait_from', job.get('from'))}.png"
    if not design_png.exists() or not source_portrait.exists():
        return {"unit": slug, "state": "failed", "step": "portrait", "history": [{"issue": "missing inputs"}]}
    ws = workspace_for(slug, "portrait")
    sprite = ws / "sprite-reference.png"
    r.enlarge(design_png, sprite)
    history, corrections = [], ""
    for attempt in range(1, attempts + 1):
        target = ws / f"portrait-{attempt}.png"
        prompt = PORTRAIT_PROMPT.replace("{name}", target.name).replace("{corrections}", corrections)
        if job.get("likeness"):
            prompt = LIKENESS_PROMPT.replace("{name}", target.name).replace("{corrections}", corrections)
            refs = [source_portrait, r.g.REFERENCES / job["likeness"]]
        else:
            refs = [source_portrait, sprite]
        ok, output = r.g._codex_with_refs(prompt, refs, target, "portrait")
        issue = None if ok else "no image"
        if ok and not painted(target):
            # 2026-10-12: one attempt returned the pixel sprite itself.
            issue = "pixel art, not a painted portrait"
            corrections = ("- Correction: the previous result was pixel art. Paint a smooth, detailed portrait "
                           "exactly like the first attached image, not pixel art.\n")
            ok = False
        history.append({"attempt": attempt, "issue": issue})
        if ok:
            shutil.copyfile(target, out_dir / f"{slug}-portrait-raw.png")
            return {"unit": slug, "state": "generated", "step": "portrait", "history": history}
        if r.g.codex_art.QUOTA.search(output) and not r.g.codex_art.MODERATION.search(output):
            break
    return {"unit": slug, "state": "failed", "step": "portrait", "history": history}


def install(slug: str, job: dict, out_dir: Path) -> str | None:
    if not job.get("portrait_only"):
        problem = import_frames(slug, out_dir / f"{slug}-frames.png", out_dir / f"{slug}-design.png", None, True,
                                job["from"])
        if problem:
            return problem
    raw = out_dir / f"{slug}-portrait-raw.png"
    if job.get("portrait") and raw.exists():
        # Same framing and size as the source portrait it was repainted from.
        return r._run(f"""
from PIL import Image
src = Image.open(r"{PORTRAITS / (job.get('portrait_from', job.get('from')) + '.png')}")
new = Image.open(r"{raw}").convert("RGBA").resize(src.size, Image.LANCZOS)
new.save(r"{PORTRAITS / (slug + '.png')}", optimize=True)
print("ok")
""")
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--only", action="append")
    parser.add_argument("--step", choices=["design", "frames", "portrait"])
    parser.add_argument("--attempts", type=int, default=3)
    parser.add_argument("--install", action="store_true", help="install reviewed results from --out-dir")
    args = parser.parse_args()
    jobs = json.loads(JOBS.read_text(encoding="utf-8"))
    args.out_dir.mkdir(parents=True, exist_ok=True)
    failed = 0
    for slug in args.only or [k for k in jobs if not k.startswith("_")]:
        job = jobs[slug]
        if args.install:
            problem = install(slug, job, args.out_dir)
            print(f"{slug}: {'installed' if not problem else 'FAILED ' + problem}", flush=True)
            failed += bool(problem)
            continue
        steps = [args.step] if args.step else (
            ["portrait"] if job.get("portrait_only")
            else ["design", "frames"] + (["portrait"] if job.get("portrait") else []))
        for step in steps:
            outcome = {"design": design_step, "frames": frames_step, "portrait": portrait_step}[step](
                slug, job, args.out_dir, args.attempts)
            print(json.dumps(outcome), flush=True)
            if outcome["state"] != "generated":
                failed += 1
                break
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
