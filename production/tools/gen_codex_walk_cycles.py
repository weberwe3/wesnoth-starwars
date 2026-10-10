#!/usr/bin/env python3
"""Have Codex draw a smooth four-frame walk cycle for a unit.

Owner direction (2026-10-10): extra frames for smoother motion. Units were
drawn with two walking frames (two strides, no passing pose), so a walk
snapped between them. Codex is shown the unit's installed standing and
walking frames (enlarged) and draws one labelled row of five frames:
standing, then contact - passing - contact - passing. The standing figure
is only the scale reference: the row is scaled so it matches the installed
standing frame's height, anchored like the other frames (bottom centre),
and reduced to its own palette. move-1..move-4 are written; the generator
(gen_hte_units.py) plays all four when move-3.png exists.

Reviews go to --out-dir (a 4x preview strip per unit); --install writes the
frames. Codex is told no names (owner rule; prompt_scrub).

Usage: python3 production/tools/gen_codex_walk_cycles.py --out-dir DIR [--only SLUG ...]
           [--install] [--sheet SLUG=EXISTING.png ...]
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

# Gait per movement family; units not listed walk on two legs.
GAITS = {
    "quadruped": ("a four-frame trot cycle for this four-legged creature: frame walk-1 with the near front and "
                  "far hind legs reaching forward, walk-2 with the legs gathered under the body, walk-3 with the "
                  "other diagonal pair reaching forward, walk-4 gathered again"),
    "walker": ("a four-frame walking cycle for this two-legged armoured walker machine: walk-1 with the near leg "
               "planted forward, walk-2 with the far leg lifted and passing the near leg (the cab slightly "
               "higher), walk-3 with the far leg planted forward, walk-4 with the near leg lifted and passing"),
    "biped": ("a four-frame walking cycle: walk-1 contact pose with the near leg forward (like the first walking "
              "frame in the reference), walk-2 passing pose with the legs together under the body and the body "
              "one pixel higher, walk-3 contact pose with the far leg forward (like the second walking frame), "
              "walk-4 passing pose again"),
}
QUADRUPEDS = {"sw-unit-wl-vornskr"}
WALKERS = {"sw-unit-im-at-st"}

PROMPT = """Use your image generation tool to create exactly ONE image and save it as {name} in the current working directory. Do not create any other files.

The attached image shows one pixel-art unit from a turn-based tactics game, enlarged: {subject}. It shows the unit's standing frame and its two walking frames, on a flat green background.

Draw a sprite sheet of this same unit: ONE row of five frames on the same flat green background, each frame labelled in small yellow text above it: standing, walk-1, walk-2, walk-3, walk-4.
- standing: the standing frame, unchanged.
- walk-1 to walk-4: {gait}. Arms and held equipment swing naturally and stay consistent between the four frames; the weapon or tool is held the same way as in the walking frames of the reference. {note}

Keep exactly the same unit, proportions, colours, equipment, pixel-art style, dark outline and shading, the same size, and the same three-quarter view facing right. Leave wide empty gaps of background between the frames so no frame touches another, and draw nothing else on the sheet.
{corrections}
After saving, reply with only the file name."""


def gait_for(slug: str) -> str:
    return GAITS["quadruped" if slug in QUADRUPEDS else "walker" if slug in WALKERS else "biped"]


def reference_strip(slug: str, out: Path) -> None:
    script = f"""
from PIL import Image
frames = [Image.open(r"{UNITS / slug}/" + n + ".png").convert("RGBA") for n in ("standing", "move-1", "move-2")]
k, gap = 8, 48
w = sum(f.width * k for f in frames) + gap * (len(frames) + 1)
sheet = Image.new("RGBA", (w, 72 * k + 2 * gap), (60, 112, 60, 255))
x = gap
for f in frames:
    sheet.alpha_composite(f.resize((f.width * k, f.height * k), Image.NEAREST), (x, gap))
    x += f.width * k + gap
sheet.convert("RGB").save(r"{out}")
"""
    subprocess.run([str(g.codex_art.art_python()), "-c", script], check=True, capture_output=True, timeout=120)


def import_sheet(slug: str, sheet: Path, preview: Path | None, install: bool) -> str | None:
    """Cut, scale-match and write the walk frames; returns a problem or None."""
    script = f"""
import sys
sys.path.insert(0, r"{TOOLS}")
import numpy as np
from PIL import Image
import import_owner_sheet as o
figs = o.figures(Image.open(r"{sheet}"), (5,))
installed = Image.open(r"{UNITS / slug}/standing.png").convert("RGBA")
box = installed.getbbox()
scale = (box[3] - box[1]) / figs[0].height
fit = min(min(o.MAX_W / f.width, o.MAX_H / f.height) for f in figs)
scale = min(scale, fit)
padded = figs + [figs[0]] * 7
made = o.frames(padded, True, scale, colors=72, alpha_cut=40)
names = ["move-1", "move-2", "move-3", "move-4"]
out = {{n: made[o.NAMES[i + 1]] for i, n in enumerate(names)}}
stand = made["standing"].getbbox()
if abs((stand[3] - stand[1]) - (box[3] - box[1])) > 2:
    raise SystemExit("standing height mismatch")
preview = {str(preview)!r}
if preview != "None":
    strip = Image.new("RGBA", (6 * 288, 288), (70, 90, 60, 255))
    for i, f in enumerate([installed, Image.open(r"{UNITS / slug}/move-1.png").convert("RGBA")] + list(out.values())):
        strip.alpha_composite(f.resize((288, 288), Image.NEAREST), (i * 288, 0))
    strip.save(preview)
# Specks of backdrop green the cut kept as "effects" (bright greens survive
# for laser light): tiny isolated green pieces are dropped. A lightsaber
# blade is one large piece and stays.
from scipy import ndimage
for n, f in out.items():
    a = np.asarray(f).copy()
    c = a[..., :3].astype(int)
    green = (a[..., 3] > 0) & (c[..., 1] > c[..., 0] + 30) & (c[..., 1] > c[..., 2] + 30)
    lab, k = ndimage.label(green)
    for i in range(1, k + 1):
        if (lab == i).sum() <= 4:
            a[lab == i, 3] = 0
    out[n] = Image.fromarray(a, "RGBA")
if {install!r}:
    for n, f in out.items():
        f.save(r"{UNITS / slug}/" + n + ".png", optimize=True)
print("ok")
"""
    run = subprocess.run([str(g.codex_art.art_python()), "-c", script], capture_output=True, text=True, timeout=600)
    return None if run.returncode == 0 else (run.stderr or run.stdout).strip().splitlines()[-1][-200:]


def describe(slug: str) -> str:
    direction = g.codex_art.load_direction(g.ROOT)
    return scrub(direction["units"].get(slug.replace("-", "_"), "") or "a unit")


def generate(slug: str, out_dir: Path, attempts: int, note: str = "") -> dict:
    workspace = g.codex_art._managed_directory(f"walk-{slug}")
    ref = workspace / "walk-reference.png"
    reference_strip(slug, ref)
    corrections: list[str] = []
    history = []
    for attempt in range(1, attempts + 1):
        target = workspace / f"walk-{attempt}.png"
        prompt = PROMPT.format(name=target.name, subject=describe(slug), gait=gait_for(slug), note=scrub(note),
                               corrections="".join(f"- Correction: {c}\n" for c in corrections))
        ok, output = g._codex_with_refs(prompt, [ref], target, slug)
        if not ok:
            history.append({"attempt": attempt, "issue": "blocked" if "moderation_blocked" in output else "no image"})
            if g.codex_art.QUOTA.search(output) and not g.codex_art.MODERATION.search(output):
                return {"unit": slug, "state": "quota_paused", "history": history}
            continue
        problem = import_sheet(slug, target, out_dir / f"{slug}-preview.png", False)
        history.append({"attempt": attempt, "issue": problem})
        if not problem:
            shutil.copyfile(target, out_dir / f"{slug}.png")
            return {"unit": slug, "state": "generated", "sheet": str(out_dir / f"{slug}.png"), "history": history}
        corrections = [f"The previous sheet could not be split into its five frames ({problem}). Draw exactly one "
                       "row of five frames, each with its yellow label above it, wide gaps between frames, and "
                       "nothing else."]
    return {"unit": slug, "state": "failed", "history": history}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--only", action="append", required=True, help="unit art slug, e.g. sw-unit-nr-trooper")
    parser.add_argument("--attempts", type=int, default=3)
    parser.add_argument("--install", action="store_true", help="install already generated sheets from --out-dir")
    parser.add_argument("--note", default="", help="extra direction for these units (e.g. a posture to keep)")
    args = parser.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    failed = 0
    for slug in args.only:
        if args.install:
            problem = import_sheet(slug, args.out_dir / f"{slug}.png", None, True)
            print(f"{slug}: {'installed' if not problem else 'FAILED ' + problem}", flush=True)
            failed += bool(problem)
            continue
        outcome = generate(slug, args.out_dir, args.attempts, args.note)
        print(json.dumps(outcome), flush=True)
        failed += outcome["state"] != "generated"
        if outcome["state"] == "quota_paused":
            break
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
