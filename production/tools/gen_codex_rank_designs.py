#!/usr/bin/env python3
"""Have Codex redraw a unit as its own ranked-up design.

Owner direction (2026-10-10): iterative designs for characters as they rank
up; higher ranks clearly more distinctive and of a higher tier, lore-accurate,
yet plainly the same character. A unit at rank II (Seasoned veteran) or III
(Elite) changes into a better-equipped version of itself.

Owner rules for the prompts (2026-10-10): the unit's idle sprite is the
reference, and Codex is only asked to redraw the sprite it is given in a
stated way -- no character names, no setting terms (prompt_scrub still
checks). Two steps per rank:

  1. design  -- the idle sprite (idle-1.png of the base art, or of the rank-2
     art when drawing rank 3, so each tier builds on the last) is redrawn
     with the rank's changes (rank_design_jobs.json). The sheet shows the
     sprite unchanged beside the redraw; the unchanged copy sets the scale.
  2. frames  -- the new idle sprite is redrawn as the unit's full frame set
     (the poses are described in words; the old sheet is not shown).

Frames are cut by import_owner_sheet.figures, scaled so the unchanged copy
matches the installed idle frame, reduced to their own palette and written to
units/<slug>-rank<N>/ (with --install). gen_hte_units.py turns each art set
into a hidden variation that lua/sw_rank.lua applies.

Reviews go to --out-dir (<slug>-rank<N>-design.png, <slug>-rank<N>.png and a
preview strip).

Usage: python3 production/tools/gen_codex_rank_designs.py --out-dir DIR --rank N [--only SLUG ...]
           [--install]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
import gen_codex_reference_frames as g  # noqa: E402
from prompt_scrub import scrub  # noqa: E402

UNITS = g.ROOT / "addons/Star_Wars_Thrawn_Trilogy/images/units"
JOBS = TOOLS / "rank_design_jobs.json"
RANK_WORDS = {2: "a seasoned veteran", 3: "an elite of the highest tier"}
CRAFT = {"sw-unit-nr-xwing", "sw-unit-nr-awing", "sw-unit-nr-ywing", "sw-hero-xwing-luke", "sw-hero-wedge"}

DESIGN_PROMPT = """Use your image generation tool to create exactly ONE image and save it as {name} in the current working directory. Do not create any other files.

Redraw the attached pixel-art sprite (enlarged, on a flat magenta background) as {rank}, with these changes: {design}.

The changes must read at a glance at this small sprite size: bold, clearly visible, with a new silhouette element and a stronger accent colour. Everything else stays exactly the same: the exact colours and patterns of the outfit (do not add or change any pattern), the pose, proportions, head size, face, hair, skin, base colours, the item held, the pixel-art style, dark outline and shading, the size, and the three-quarter view facing right.

Make the image a sheet of TWO frames side by side on the same flat magenta background, each labelled in small yellow text above it: before, after. "before" is the attached sprite, unchanged; "after" is the redrawn sprite. Leave a wide empty gap between them and draw nothing else.
{corrections}
After saving, reply with only the file name."""

FRAMES_PROMPT = """Use your image generation tool to create exactly ONE image and save it as {name} in the current working directory. Do not create any other files.

Redraw the attached pixel-art sprite (enlarged, on a flat magenta background) as an animation sprite sheet: two rows of frames on the same flat magenta background, each frame labelled in small yellow text above it.
Top row: {top}.
Bottom row: {bottom}.
The frames:
{poses}

Every frame shows exactly the same figure as the attached sprite: the exact colours and patterns, the same proportions, head size, face, hair, outfit, armour, colours, markings and held item, the same pixel-art style, dark outline and shading, the same size, and the same three-quarter view facing right. Leave wide empty gaps between frames so no frame touches another, and draw nothing else on the sheet.
{corrections}
After saving, reply with only the file name."""

POSES = {
    "figure": {
        "idle": "the attached sprite, unchanged",
        "standing": "standing at ease, almost the same as the attached sprite",
        "idle-2": "the attached pose with a slight breath: shoulders a pixel higher, the held item shifted a little",
        "walk-1": "walking, contact pose with the near leg forward",
        "walk-2": "walking, passing pose with the legs together under the body, body one pixel higher",
        "walk-3": "walking, contact pose with the far leg forward",
        "walk-4": "walking, passing pose again",
        "melee-1": "winding up a close-range strike",
        "melee-2": "the strike, following through",
        "ranged-1": "aiming the held weapon forward",
        "ranged-2": "firing the held weapon forward, with a small bright {flash} muzzle flash at its tip",
        "defend": "flinching back from a hit",
        "death-1": "collapsing to the knees",
        "death-2": "lying on the ground",
    },
    "craft": {
        "idle": "the attached sprite, unchanged",
        "standing": "the same craft, level",
        "idle-2": "the same craft banked very slightly",
        "move-1": "the same craft with its engines glowing brighter",
        "move-2": "the same craft with its engines flaring",
        "melee-1": "the same craft banking into a turn",
        "melee-2": "the same craft banking the other way",
        "ranged-1": "the same craft lining up a shot",
        "ranged-2": "the same craft firing its forward guns, with small bright {flash} flashes at the gun tips",
        "defend": "the same craft jolted by a hit, with a few sparks",
        "death-1": "the same craft breaking apart in a small explosion",
        "death-2": "a burning, broken wreck of the same craft",
    },
}
# Units whose ranged attack is not a gun.
POSE_OVERRIDES = {
    "sw-hero-luke": {"ranged-1": "raising the held glowing blade to guard",
                     "ranged-2": "the held glowing blade turning aside a small bright red bolt"},
}
# Frame name in the add-on for each sheet label ("idle" is the unit's idle-1).
INSTALL_AS = {"idle": "idle-1", "walk-1": "move-1", "walk-2": "move-2", "walk-3": "move-3", "walk-4": "move-4"}
BOTTOM = ["melee-1", "melee-2", "ranged-1", "ranged-2", "defend", "death-1", "death-2"]


def sheet_rows(slug: str) -> list[list[str]]:
    # Figures always get a four-frame walk: the frames are drawn from the idle
    # sprite, so they do not depend on the base unit's walk art (a base unit
    # with two walking frames plays move-1 and move-2 only).
    if slug in CRAFT:
        return [["idle", "standing", "idle-2", "move-1", "move-2"], BOTTOM]
    return [["idle", "standing", "idle-2", "walk-1", "walk-2", "walk-3", "walk-4"], BOTTOM]


def install_names(slug: str) -> list[str]:
    return [INSTALL_AS.get(n, n) for r in sheet_rows(slug) for n in r]


COLOUR_WORDS = {"red": "red", "blue": "blue", "green": "green", "orange": "orange", "yellow": "yellow",
                "violet": "violet", "white": "white"}


def flash_colour(slug: str) -> str:
    """The colour of the bolt this unit fires (gen_hte_units.projectile): the
    redrawn firing frame paints its own muzzle flash, which must match it."""
    import gen_hte_units as units
    uid = slug.replace("-", "_")
    u = next((x for x in units.ROSTER if x["id"] == uid), None)
    ranged = [a for a in (u["attacks"] if u else []) if a["range"] == "ranged"]
    shot = units.projectile(uid, ranged[0]["name"]) if ranged else None
    if not shot:
        return "white"
    for word in COLOUR_WORDS:
        if f"-{word}-" in shot[0]:
            return COLOUR_WORDS[word]
    return "pale blue" if "ion" in shot[0] else "white"


def source_art(slug: str, rank: int) -> Path:
    return UNITS / (f"{slug}-rank{rank - 1}" if rank > 2 else slug)


def workspace_for(slug: str, rank: int, step: str) -> Path:
    # Codex sees its working directory: the name must not carry the character's name.
    return g.codex_art._managed_directory(f"rank{rank}-{step}-" + hashlib.sha1(slug.encode()).hexdigest()[:10])


def enlarge(image: Path, out: Path) -> None:
    script = f"""
from PIL import Image
f = Image.open(r"{image}").convert("RGBA")
k, gap = 8, 64
sheet = Image.new("RGBA", (f.width * k + 2 * gap, f.height * k + 2 * gap), (255, 0, 255, 255))
sheet.alpha_composite(f.resize((f.width * k, f.height * k), Image.NEAREST), (gap, gap))
sheet.convert("RGB").save(r"{out}")
"""
    subprocess.run([str(g.codex_art.art_python()), "-c", script], check=True, capture_output=True, timeout=120)


def idle_reference(slug: str, out: Path) -> None:
    """The unit's idle sprite as Codex's reference: its idle frame cut from the
    unit's original high-resolution sheet (~/art-references, where the installed
    frames were scaled down from), or else the installed 72x72 idle sprite
    enlarged 8x. On a flat magenta key."""
    uid = slug.replace("-", "_")
    sheet = next((g.REFERENCES / f"{p}-{uid}.png" for p in ("owner", "codex")
                  if (g.REFERENCES / f"{p}-{uid}.png").exists()), None)
    script = f"""
import sys
sys.path.insert(0, r"{TOOLS}")
from PIL import Image
import import_owner_sheet as o
sheet = {str(sheet) if sheet else None!r}
fig = None
if sheet:
    try:
        fig = o.figures(Image.open(sheet))[1]          # idle-1 of the 12-frame sheet
    except SystemExit:
        fig = None
if fig is None:
    f = Image.open(r"{UNITS / slug}/idle-1.png").convert("RGBA")
    f = f.crop(f.getbbox())
    fig = f.resize((f.width * 8, f.height * 8), Image.NEAREST)
gap = 64
canvas = Image.new("RGBA", (fig.width + 2 * gap, fig.height + 2 * gap), (255, 0, 255, 255))
canvas.alpha_composite(fig.convert("RGBA"), (gap, gap))
canvas.convert("RGB").save(r"{out}")
"""
    subprocess.run([str(g.codex_art.art_python()), "-c", script], check=True, capture_output=True, timeout=300)


def on_key(image: Path, out: Path) -> None:
    script = f"""
from PIL import Image
fig = Image.open(r"{image}").convert("RGBA")
gap = 64
canvas = Image.new("RGBA", (fig.width + 2 * gap, fig.height + 2 * gap), (255, 0, 255, 255))
canvas.alpha_composite(fig, (gap, gap))
canvas.convert("RGB").save(r"{out}")
"""
    subprocess.run([str(g.codex_art.art_python()), "-c", script], check=True, capture_output=True, timeout=120)


def _run(script: str) -> str | None:
    run = subprocess.run([str(g.codex_art.art_python()), "-c", script], capture_output=True, text=True, timeout=900)
    return None if run.returncode == 0 else (run.stderr or run.stdout).strip().splitlines()[-1][-200:]


COMMON = r"""
import sys, os
sys.path.insert(0, r"{tools}")
import numpy as np
from PIL import Image
from scipy import ndimage
import import_owner_sheet as o

# Drop magenta key-colour fringe on the figure's edge (pixels touching transparency).
def despill(img):
    a = np.asarray(img).copy()
    for _ in range(2):
        op = a[..., 3] > 0
        pad = np.pad(~op, 1, constant_values=True)
        edge = op & (pad[:-2, 1:-1] | pad[2:, 1:-1] | pad[1:-1, :-2] | pad[1:-1, 2:])
        c = a[..., :3].astype(int)
        spill = edge & (c[..., 0] > c[..., 1] + 40) & (c[..., 2] > c[..., 1] + 40)
        a[spill, 3] = 0
    return Image.fromarray(a, "RGBA")


# Identity gate: the copy of the reference that Codex was asked to keep
# unchanged must keep the reference's colours (mean colour within 20 of the
# installed sprite). It catches a figure redrawn in another palette.
def same_colours(fig, ref_path):
    ref = np.asarray(Image.open(ref_path).convert("RGBA")).astype(int)
    f = np.asarray(fig.convert("RGBA")).astype(int)
    diff = np.abs(f[f[..., 3] > 0][:, :3].mean(0) - ref[ref[..., 3] > 0][:, :3].mean(0)).sum()
    if diff > 20:
        raise SystemExit(f"the unchanged copy changed colour ({{diff:.0f}})")

def cut(sheet, per_row, ref_idle):
    figs = o.figures(Image.open(sheet), per_row)
    same_colours(figs[0], ref_idle)
    box = Image.open(ref_idle).convert("RGBA").getbbox()
    scale = (box[3] - box[1]) / figs[0].height
    scale = min(scale, min(min(o.MAX_W / f.width, o.MAX_H / f.height) for f in figs))
    out = []
    for start in range(0, len(figs), 12):
        chunk = figs[start:start + 12]
        # Pad to frames()'s 12 by cycling the drawn figures: padding with one
        # figure would let its colours dominate the shared palette.
        made = o.frames((chunk * 12)[:12], True, scale, colors=72, alpha_cut=40)
        out += [made[o.NAMES[i]] for i in range(len(chunk))]
    got = out[0].getbbox()
    if (got[3] - got[1]) < 0.92 * (box[3] - box[1]):
        raise SystemExit("scale reference too small")
    cleaned = []
    for f in out:
        a = np.asarray(f).copy()
        c = a[..., :3].astype(int)
        green = (a[..., 3] > 0) & (c[..., 1] > c[..., 0] + 30) & (c[..., 1] > c[..., 2] + 30)
        lab, k = ndimage.label(green)
        for i in range(1, k + 1):
            if (lab == i).sum() <= 4:
                a[lab == i, 3] = 0
        # Magenta key colour blended into the figure (outline gaps): dropped
        # anywhere, then pinholes it leaves are filled by despeckle_unit.py.
        c = a[..., :3].astype(int)
        a[(a[..., 3] > 0) & (c[..., 0] > c[..., 1] + 90) & (c[..., 2] > c[..., 1] + 90), 3] = 0
        lab, k = ndimage.label(a[..., 3] > 0)
        if k > 1:
            sizes = ndimage.sum(np.ones_like(lab), lab, range(1, k + 1))
            main = np.isin(lab, [i + 1 for i, v in enumerate(sizes) if v >= 0.25 * sizes.max()])
            near = ndimage.binary_dilation(main, iterations=3)
            for i, v in enumerate(sizes):
                piece = lab == i + 1
                if v < 12 and not (piece & near).any():
                    a[piece, 3] = 0
        cleaned.append(despill(Image.fromarray(a, "RGBA")))
    return cleaned
"""


def import_design(slug: str, rank: int, sheet: Path, out_png: Path) -> str | None:
    """Step 1: the 'after' frame of the design sheet, as a 72x72 idle sprite."""
    ref = source_art(slug, rank) / "idle-1.png"
    if not ref.exists():   # rank 3 drawn before rank 2 is installed
        ref = out_png.parent / f"{slug}-rank{rank - 1}-design.png"
    return _run(COMMON.format(tools=TOOLS) + f"""
figs = cut(r"{sheet}", (2,), r"{ref}")
figs[1].save(r"{out_png}")
# The full-resolution redraw: the next tier's reference.
o.figures(Image.open(r"{sheet}"), (2,))[1].save(r"{out_png}".replace("-design.png", "-design-hires.png"))
print("ok")
""")


def import_frames(slug: str, rank: int, sheet: Path, design_idle: Path, preview: Path | None,
                  install: bool) -> str | None:
    rows = sheet_rows(slug)
    names = install_names(slug)
    dest = UNITS / f"{slug}-rank{rank}"
    base = UNITS / slug
    return _run(COMMON.format(tools=TOOLS) + f"""
names = {names!r}
figs = cut(r"{sheet}", {tuple(len(r) for r in rows)!r}, r"{design_idle}")
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


def codex_sheet(prompt: str, ref: Path, workspace: Path, stem: str, attempts: int, check) -> tuple[Path | None, list]:
    history, corrections = [], []
    for attempt in range(1, attempts + 1):
        target = workspace / f"{stem}-{attempt}.png"
        full = prompt.replace("{name}", target.name).replace("{corrections}",
                                                             "".join(f"- Correction: {c}\n" for c in corrections))
        ok, output = g._codex_with_refs(full, [ref], target, stem)
        if not ok:
            history.append({"attempt": attempt, "issue": "blocked" if "moderation_blocked" in output else "no image"})
            if g.codex_art.QUOTA.search(output) and not g.codex_art.MODERATION.search(output):
                return None, history + [{"issue": "quota"}]
            continue
        problem = check(target)
        history.append({"attempt": attempt, "issue": problem})
        if not problem:
            return target, history
        corrections = [f"The previous sheet could not be split into its frames ({problem}). Keep exactly the "
                       "frames asked for, each with its yellow label above it, wide gaps, and nothing else."]
    return None, history


def generate(slug: str, rank: int, design: str, out_dir: Path, attempts: int) -> dict:
    src = source_art(slug, rank)
    hires_prev = out_dir / f"{slug}-rank{rank - 1}-design-hires.png"
    if not (src / "idle-1.png").exists() and not hires_prev.exists():
        return {"unit": slug, "rank": rank, "state": "failed", "history": [{"issue": f"no source art {src.name}"}]}
    # Step 1: the design, redrawn from the idle sprite.
    ws = workspace_for(slug, rank, "design")
    ref = ws / "idle-reference.png"
    hires = out_dir / f"{slug}-rank{rank - 1}-design-hires.png"
    if rank == 2:
        idle_reference(slug, ref)
    elif hires.exists():
        # Rank 3 builds on rank 2 from its full-resolution redraw, not the 72x72 sprite.
        on_key(hires, ref)
    else:
        enlarge(src / "idle-1.png", ref)
    design_png = out_dir / f"{slug}-rank{rank}-design.png"
    prompt = DESIGN_PROMPT.replace("{rank}", RANK_WORDS[rank]).replace("{design}", scrub(design))
    sheet, h1 = codex_sheet(prompt, ref, ws, "design", attempts,
                            lambda t: import_design(slug, rank, t, design_png))
    if sheet is None:
        return {"unit": slug, "rank": rank, "state": "failed", "step": "design", "history": h1}
    shutil.copyfile(sheet, out_dir / f"{slug}-rank{rank}-design-sheet.png")
    # Step 2: the full frame set, redrawn from the new idle sprite.
    ws2 = workspace_for(slug, rank, "frames")
    ref2 = ws2 / "idle-reference.png"
    enlarge(design_png, ref2)
    rows = sheet_rows(slug)
    poses = {**POSES["craft" if slug in CRAFT else "figure"], **POSE_OVERRIDES.get(slug, {})}
    lines = "\n".join(f"- {n}: {poses[n].replace('{flash}', flash_colour(slug))}." for r in rows for n in r)
    prompt2 = (FRAMES_PROMPT.replace("{top}", ", ".join(rows[0])).replace("{bottom}", ", ".join(rows[1]))
               .replace("{poses}", lines))
    sheet2, h2 = codex_sheet(prompt2, ref2, ws2, "frames", attempts,
                             lambda t: import_frames(slug, rank, t, design_png,
                                                     out_dir / f"{slug}-rank{rank}-preview.png", False))
    if sheet2 is None:
        return {"unit": slug, "rank": rank, "state": "failed", "step": "frames", "history": h1 + h2}
    shutil.copyfile(sheet2, out_dir / f"{slug}-rank{rank}.png")
    return {"unit": slug, "rank": rank, "state": "generated", "history": h1 + h2}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--rank", type=int, choices=sorted(RANK_WORDS), required=True)
    parser.add_argument("--only", action="append")
    parser.add_argument("--attempts", type=int, default=3)
    parser.add_argument("--install", action="store_true", help="install already generated sheets from --out-dir")
    args = parser.parse_args()
    jobs = json.loads(JOBS.read_text(encoding="utf-8"))
    args.out_dir.mkdir(parents=True, exist_ok=True)
    failed = 0
    for slug in args.only or [k for k in jobs if not k.startswith("_")]:
        if slug in jobs.get("_hold", []):
            print(f"{slug}: held (base art pending)", flush=True)
            continue
        if args.install:
            problem = import_frames(slug, args.rank, args.out_dir / f"{slug}-rank{args.rank}.png",
                                    args.out_dir / f"{slug}-rank{args.rank}-design.png", None, True)
            print(f"{slug} rank {args.rank}: {'installed' if not problem else 'FAILED ' + problem}", flush=True)
            failed += bool(problem)
            continue
        outcome = generate(slug, args.rank, jobs[slug][str(args.rank)], args.out_dir, args.attempts)
        print(json.dumps(outcome), flush=True)
        failed += outcome["state"] != "generated"
        if any(h.get("issue") == "quota" for h in outcome["history"]):
            break
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
