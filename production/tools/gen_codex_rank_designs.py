#!/usr/bin/env python3
"""Have Codex redraw a unit as its own ranked-up design.

Owner direction (2026-10-10): iterative designs for characters as they rank
up. A unit at rank II (Seasoned veteran) or III (Elite) changes into a
better-equipped version of itself: the same poses, frame for frame, with
gear earned in the field (rank_design_jobs.json). Codex is shown the unit's
installed frames as one labelled sheet (the rank-2 art when drawing rank 3,
so each design builds on the last) and redraws that sheet. The result is cut
by import_owner_sheet.figures, scaled so its standing figure matches the
installed standing frame, and written to units/<slug>-rank<N>/ (with
--install). gen_hte_units.py turns each art set into a hidden variation that
lua/sw_rank.lua applies.

Reviews go to --out-dir (<slug>-rank<N>.png and a preview strip).

Usage: python3 production/tools/gen_codex_rank_designs.py --out-dir DIR --rank N [--only SLUG ...]
           [--install]
"""
from __future__ import annotations

import argparse
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
RANK_NAMES = {2: "seasoned veteran", 3: "elite veteran"}
TOP = ["standing", "idle-1", "idle-2", "move-1", "move-2", "move-3", "move-4"]
BOTTOM = ["melee-1", "melee-2", "ranged-1", "ranged-2", "defend", "death-1", "death-2"]

PROMPT = """Use your image generation tool to create exactly ONE image and save it as {name} in the current working directory. Do not create any other files.

The attached image is a pixel-art unit sprite sheet for a turn-based tactics game: two rows of frames on a flat green background, each frame labelled in small yellow text above it ({labels}). It shows {subject}.

Redraw this whole sheet frame by frame, keeping every pose, the layout, the labels and the background exactly as they are, but now show the unit as a {rank}: {design}.

The new rank must read at a glance at this small sprite size: the gear is bold and clearly visible, with a new silhouette element (armour plates, a cape or cloak, a crest, a pauldron or bold paint) and a stronger accent colour, so the unit plainly looks like a higher tier than the reference. Keep the same character, face, body, base colours and weapon type, so it is instantly the same unit, promoted; the same pixel-art style, dark outline, shading and scale; the same three-quarter view facing right; wide empty gaps between frames so no frame touches another; nothing else on the sheet.
{corrections}
After saving, reply with only the file name."""


def frame_rows(art: Path) -> list[list[str]]:
    top = [n for n in TOP if (art / f"{n}.png").exists()]
    return [top, BOTTOM]


def source_art(slug: str, rank: int) -> Path:
    return UNITS / (f"{slug}-rank{rank - 1}" if rank > 2 else slug)


def reference_sheet(art: Path, rows: list[list[str]], out: Path) -> None:
    script = f"""
from PIL import Image, ImageDraw, ImageFont
rows = {rows!r}
k, gap, label_h = 6, 40, 34
cols = max(len(r) for r in rows)
cell = 72 * k
w = gap + cols * (cell + gap)
h = len(rows) * (label_h + cell + gap) + gap
sheet = Image.new("RGB", (w, h), (60, 112, 60))
draw = ImageDraw.Draw(sheet)
try:
    font = ImageFont.truetype("DejaVuSans-Bold.ttf", 26)
except OSError:
    font = ImageFont.load_default()
y = gap
for row in rows:
    x = gap
    for name in row:
        draw.text((x, y), name, fill=(240, 220, 60), font=font)
        f = Image.open(r"{art}/" + name + ".png").convert("RGBA").resize((cell, cell), Image.NEAREST)
        sheet.paste(f, (x, y + label_h), f)
        x += cell + gap
    y += label_h + cell + gap
sheet.save(r"{out}")
"""
    subprocess.run([str(g.codex_art.art_python()), "-c", script], check=True, capture_output=True, timeout=120)


def import_sheet(slug: str, rank: int, sheet: Path, preview: Path | None, install: bool) -> str | None:
    art = source_art(slug, rank)
    rows = frame_rows(UNITS / slug)
    names = [n for r in rows for n in r]
    dest = UNITS / f"{slug}-rank{rank}"
    script = f"""
import sys
sys.path.insert(0, r"{TOOLS}")
import numpy as np
from PIL import Image
from scipy import ndimage
import import_owner_sheet as o
names = {names!r}
figs = o.figures(Image.open(r"{sheet}"), {tuple(len(r) for r in rows)!r})
installed = Image.open(r"{art}/standing.png").convert("RGBA")
box = installed.getbbox()
scale = min((box[3] - box[1]) / figs[0].height, min(min(o.MAX_W / f.width, o.MAX_H / f.height) for f in figs))
# frames() works on the 12 standard frame names; run it in chunks of up to 12.
out = {{}}
for start in range(0, len(figs), 12):
    chunk = figs[start:start + 12]
    made = o.frames(chunk + [chunk[0]] * (12 - len(chunk)), True, scale, colors=72, alpha_cut=40)
    for i, n in enumerate(names[start:start + 12]):
        out[n] = made[o.NAMES[i]]
stand = out["standing"].getbbox()
# Wider gear (a cape) can force a slightly smaller scale; more than ~8% would shrink the unit visibly.
if (stand[3] - stand[1]) < 0.92 * (box[3] - box[1]) or (stand[3] - stand[1]) > (box[3] - box[1]) + 2:
    raise SystemExit("standing height mismatch")
for n, f in out.items():
    a = np.asarray(f).copy()
    c = a[..., :3].astype(int)
    green = (a[..., 3] > 0) & (c[..., 1] > c[..., 0] + 30) & (c[..., 1] > c[..., 2] + 30)
    lab, k = ndimage.label(green)
    for i in range(1, k + 1):
        if (lab == i).sum() <= 4:
            a[lab == i, 3] = 0
    out[n] = Image.fromarray(a, "RGBA")
preview = {str(preview)!r}
if preview != "None":
    strip = Image.new("RGBA", (len(names) * 144, 288), (70, 90, 60, 255))
    for i, n in enumerate(names):
        strip.alpha_composite(Image.open(r"{art}/" + n + ".png").convert("RGBA").resize((144, 144), Image.NEAREST), (i * 144, 0))
        strip.alpha_composite(out[n].resize((144, 144), Image.NEAREST), (i * 144, 144))
    strip.save(preview)
if {install!r}:
    import os
    os.makedirs(r"{dest}", exist_ok=True)
    for n, f in out.items():
        f.save(r"{dest}/" + n + ".png", optimize=True)
print("ok")
"""
    run = subprocess.run([str(g.codex_art.art_python()), "-c", script], capture_output=True, text=True, timeout=900)
    return None if run.returncode == 0 else (run.stderr or run.stdout).strip().splitlines()[-1][-200:]


def describe(slug: str) -> str:
    direction = g.codex_art.load_direction(g.ROOT)
    return scrub(direction["units"].get(slug.replace("-", "_"), "") or "a unit")


def generate(slug: str, rank: int, design: str, out_dir: Path, attempts: int) -> dict:
    art = source_art(slug, rank)
    if not (art / "standing.png").exists():
        return {"unit": slug, "rank": rank, "state": "failed", "history": [{"issue": f"no source art {art.name}"}]}
    rows = frame_rows(UNITS / slug)
    workspace = g.codex_art._managed_directory(f"rank{rank}-{slug}")
    ref = workspace / "rank-reference.png"
    reference_sheet(art, rows, ref)
    labels = "; ".join(", ".join(r) for r in rows)
    corrections: list[str] = []
    history = []
    for attempt in range(1, attempts + 1):
        target = workspace / f"rank{rank}-{attempt}.png"
        prompt = PROMPT.format(name=target.name, labels=labels, subject=describe(slug), rank=RANK_NAMES[rank],
                               design=scrub(design), corrections="".join(f"- Correction: {c}\n" for c in corrections))
        ok, output = g._codex_with_refs(prompt, [ref], target, slug)
        if not ok:
            history.append({"attempt": attempt, "issue": "blocked" if "moderation_blocked" in output else "no image"})
            if g.codex_art.QUOTA.search(output) and not g.codex_art.MODERATION.search(output):
                return {"unit": slug, "rank": rank, "state": "quota_paused", "history": history}
            continue
        problem = import_sheet(slug, rank, target, out_dir / f"{slug}-rank{rank}-preview.png", False)
        history.append({"attempt": attempt, "issue": problem})
        if not problem:
            shutil.copyfile(target, out_dir / f"{slug}-rank{rank}.png")
            return {"unit": slug, "rank": rank, "state": "generated", "history": history}
        corrections = [f"The previous sheet could not be split into its frames ({problem}). Keep exactly the "
                       "same two rows of frames, each with its yellow label above it, wide gaps, nothing else."]
    return {"unit": slug, "rank": rank, "state": "failed", "history": history}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--rank", type=int, choices=sorted(RANK_NAMES), required=True)
    parser.add_argument("--only", action="append")
    parser.add_argument("--attempts", type=int, default=3)
    parser.add_argument("--install", action="store_true", help="install already generated sheets from --out-dir")
    args = parser.parse_args()
    jobs = json.loads(JOBS.read_text(encoding="utf-8"))
    args.out_dir.mkdir(parents=True, exist_ok=True)
    failed = 0
    for slug in args.only or [k for k in jobs if not k.startswith("_")]:
        # Held: its base art is still being redrawn (e.g. a walk cycle), and
        # the rank designs must be drawn from the final frames.
        if slug in jobs.get("_hold", []):
            print(f"{slug}: held (base art pending)", flush=True)
            continue
        if args.install:
            problem = import_sheet(slug, args.rank, args.out_dir / f"{slug}-rank{args.rank}.png", None, True)
            print(f"{slug} rank {args.rank}: {'installed' if not problem else 'FAILED ' + problem}", flush=True)
            failed += bool(problem)
            continue
        outcome = generate(slug, args.rank, jobs[slug][str(args.rank)], args.out_dir, args.attempts)
        print(json.dumps(outcome), flush=True)
        failed += outcome["state"] != "generated"
        if outcome["state"] == "quota_paused":
            break
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
