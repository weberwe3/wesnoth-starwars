#!/usr/bin/env python3
"""Have Codex redraw a unit's idle and walk frames, keeping the rest.

Owner direction (2026-10-07): walking animations must alternate legs (move-1
one leg forward, move-2 the other) and idle frames must show a small motion
that fits the character and equipment. Many units had idle frames that were
the standing frame shifted or brightened, and walk frames with the same leg
forward twice.

For each unit: compose its installed 12 frames into a labelled house-style
sheet (the layout import_owner_sheet.py reads), send it to Codex asking for
the same sheet with only idle-1, idle-2, move-1 and move-2 redrawn, check the
result (12 frames; idle differs from standing but stays the same character;
the walk frames differ from each other), and write the four new frames,
scaled to the unit's current standing height, to --out-dir for review.

Usage: python3 production/tools/repair_walk_idle.py --out-dir DIR [--only UNIT_ID ...]
       [--kind walker|craft] [--attempts N]
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gen_codex_reference_frames as g  # noqa: E402
from prompt_scrub import scrub  # noqa: E402

TOOLS = Path(__file__).resolve().parent
NAMES = ["standing", "idle-1", "idle-2", "move-1", "move-2", "melee-1",
         "melee-2", "ranged-1", "ranged-2", "defend", "death-1", "death-2"]
REDRAW = ["idle-1", "idle-2", "move-1", "move-2"]

GUIDANCE = {
    "walker": (
        "idle-1 and idle-2: a small idle motion that fits this character and its equipment -- for example "
        "breathing, a shift of weight, adjusting the grip on its weapon, a glance aside, a cape, robe, fur or "
        "tail stirring. The figure stays in the same spot and at the same size as the standing frame, and "
        "idle-1 and idle-2 differ visibly from the standing frame and from each other. "
        "move-1 and move-2: a two-frame walk cycle facing right in which the legs SWAP. In move-1 the NEAR leg "
        "(the one closer to the viewer, drawn in front, with any holster or strap on it) steps forward and the "
        "far leg is back. In move-2 the FAR leg steps forward and the NEAR leg is behind it, trailing back -- "
        "the opposite leg leads, so the two frames must not show the same leg in front. The arms swing "
        "opposite to the legs, so the arm in front also swaps. A four-legged animal alternates its diagonal "
        "leg pairs the same way; a figure in a long robe or cape shows the alternating feet and the cloth "
        "swinging the other way."),
    "craft": (
        "idle-1 and idle-2: the craft hovering in place -- engine glow pulsing, a slight bob, running lights "
        "blinking; same spot and size as the standing frame, and visibly different from it and from each "
        "other. move-1 and move-2: flying forward to the right with engines flaring, banking slightly one way "
        "in move-1 and the other way in move-2."),
}

PROMPT = """Use your image generation tool to create exactly ONE image and save it as {name} in the current working directory. Do not create any other files.

The attached image is the complete 12-frame pixel-art sprite sheet of one game unit: two rows of six frames on a flat green background, each frame labelled in small yellow text (standing, idle-1, idle-2, move-1, move-2, melee-1 in the top row; melee-2, ranged-1, ranged-2, defend, death-1, death-2 in the bottom row).

Redraw this same sheet. Keep every frame exactly as it is EXCEPT these four, which must be redrawn: idle-1, idle-2, move-1 and move-2.
{guidance}
{notes}
Keep the same character in all twelve frames: the same design, colours, equipment, outline, shading, pixel-art style, scale and view. Keep the layout, the yellow labels in the same places and the flat green background, with clear empty space between frames.
{corrections}
After saving, reply with only the file name."""


def compose(unit_dir: Path, out: Path) -> None:
    """The unit's installed frames as a labelled sheet, 4x, labels left-aligned above each frame."""
    script = f"""
from PIL import Image, ImageDraw, ImageFont
names = {NAMES!r}
k, cell_w, label_h = 4, 333, 34
sheet = Image.new("RGB", (cell_w * 6, 2 * (label_h + 72 * k + 20)), (64, 90, 58))
d = ImageDraw.Draw(sheet)
try:
    font = ImageFont.truetype("DejaVuSans.ttf", 18)
except OSError:
    font = ImageFont.load_default()
for i, n in enumerate(names):
    x, y = (i % 6) * cell_w, (i // 6) * (label_h + 72 * k + 20)
    d.text((x + 8, y + 6), n, fill=(240, 220, 40), font=font)
    f = Image.open({str(unit_dir)!r} + "/" + n + ".png").convert("RGBA").resize((72 * k, 72 * k), Image.NEAREST)
    sheet.paste(f, (x + (cell_w - 72 * k) // 2, y + label_h), f)
sheet.save({str(out)!r})
"""
    subprocess.run([str(g.codex_art.art_python()), "-c", script], check=True, capture_output=True, timeout=120)


# Import the returned sheet, take the four frames at the unit's current scale, and measure them.
EXTRACT = """
import sys, json
sys.path.insert(0, {tools!r})
import numpy as np
from PIL import Image
import import_owner_sheet as o
figs = o.figures(Image.open({src!r}))
cur = Image.open({unit!r} + "/standing.png").convert("RGBA")
bb = cur.getbbox()
scale = (bb[3] - bb[1]) / figs[0].height
scale = min([scale] + [min(o.MAX_W / f.width, 70 / f.height) for f in figs])
made = o.frames(figs, True, scale)
# Snap the redrawn frames to the colours of the unit's installed frames, so
# background green bleeding into the new art is replaced and colours match.
names_all = ["standing", "idle-1", "idle-2", "move-1", "move-2", "melee-1", "melee-2", "ranged-1", "ranged-2",
             "defend", "death-1", "death-2"]
inst = [Image.open({unit!r} + "/" + n + ".png").convert("RGBA") for n in names_all]
pal_src = Image.new("RGB", (72 * len(inst), 72), (0, 0, 0))
for i, f in enumerate(inst):
    pal_src.paste(f.convert("RGB"), (72 * i, 0), mask=f.getchannel("A"))
palette = pal_src.quantize(colors=96, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
st_px = np.asarray(inst[0].convert("RGBA")).astype(int)
st_px = st_px[..., :3][st_px[..., 3] > 110]
greenish = lambda c: c[1] > c[0] + 12 and c[1] > c[2] + 12
if len(st_px) and sum(1 for c in st_px if greenish(c)) / len(st_px) < 0.02:
    # The unit has no green of its own: greenish palette entries are background bleed.
    pal = [tuple(palette.getpalette()[i * 3:i * 3 + 3]) for i in range(96)]
    keep = [c for c in pal if not greenish(c)] or pal
    flat = [v for c in keep for v in c] + [0, 0, 0] * (256 - len(keep))
    palette = Image.new("P", (1, 1)); palette.putpalette(flat)
from collections import deque
# Fill small transparent holes enclosed by the figure (background-coloured
# pixels inside dark hair or fur) with the colour of a neighbour.
def fill_holes(f, limit=16):
    x = np.asarray(f.convert("RGBA")).copy(); h, w = x.shape[:2]
    clear = x[..., 3] == 0; seen = np.zeros_like(clear)
    for sy in range(h):
        for sx in range(w):
            if not clear[sy, sx] or seen[sy, sx]: continue
            q = deque([(sy, sx)]); seen[sy, sx] = True; region = []; edge = False
            while q:
                cy, cx = q.popleft(); region.append((cy, cx))
                if cy in (0, h - 1) or cx in (0, w - 1): edge = True
                for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    ny, nx = cy + dy, cx + dx
                    if 0 <= ny < h and 0 <= nx < w and clear[ny, nx] and not seen[ny, nx]:
                        seen[ny, nx] = True; q.append((ny, nx))
            if edge or len(region) > limit: continue
            for cy, cx in region:
                for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    ny, nx = cy + dy, cx + dx
                    if 0 <= ny < h and 0 <= nx < w and x[ny, nx, 3] > 0:
                        x[cy, cx] = x[ny, nx]; break
    return Image.fromarray(x, "RGBA")
for n in {redraw!r}:
    made[n] = fill_holes(made[n])
for n in {redraw!r}:
    f = made[n]; alpha = f.getchannel("A")
    rgb = f.convert("RGB").quantize(palette=palette, dither=Image.Dither.NONE).convert("RGBA"); rgb.putalpha(alpha)
    made[n] = rgb
def a(im): return np.asarray(im.convert("RGBA")).astype(int)
def diff(x, y):
    m = (x[..., 3] > 0) | (y[..., 3] > 0)
    return float(((np.abs(x - y).sum(-1) > 30) & m).sum() / max(1, m.sum()))
def hist(im):
    x = a(im); px = x[..., :3][x[..., 3] > 110] // 32
    h = np.bincount(px[:, 0] * 64 + px[:, 1] * 8 + px[:, 2], minlength=512).astype(float)
    return h / max(1, h.sum())
st = made["standing"]
report = {{"idle1_vs_standing": diff(a(st), a(made["idle-1"])), "idle2_vs_standing": diff(a(st), a(made["idle-2"])),
          "idle1_vs_idle2": diff(a(made["idle-1"]), a(made["idle-2"])), "move1_vs_move2": diff(a(made["move-1"]), a(made["move-2"])),
          "identity": float(min(np.minimum(hist(made[n]), hist(cur)).sum() for n in {redraw!r}))}}
for n in {redraw!r}:
    made[n].save({dest!r} + "/" + n + ".png", optimize=True)
print(json.dumps(report))
"""


def evaluate(r: dict) -> list[str]:
    issues = []
    if r["idle1_vs_standing"] < 0.04 or r["idle2_vs_standing"] < 0.04 or r["idle1_vs_idle2"] < 0.03:
        issues.append("idle-1 and idle-2 must show a visible idle motion: each must differ from the standing "
                      "frame and from each other (breathing, weight shift, weapon or clothing movement).")
    if r["idle1_vs_standing"] > 0.7 or r["idle2_vs_standing"] > 0.7:
        issues.append("idle-1 and idle-2 must stay close to the standing pose, in the same spot and size; only a "
                      "small motion.")
    if r["move1_vs_move2"] < 0.12:
        issues.append("move-1 and move-2 must clearly differ: in move-1 the left leg leads, in move-2 the right "
                      "leg leads.")
    if r["identity"] < 0.45:
        issues.append("Keep exactly the same character and colours as in the other frames of the sheet.")
    return issues


def repair(unit_id: str, kind: str, notes: str, out_dir: Path, attempts: int) -> dict:
    unit_dir = g.UNITS / unit_id.replace("_", "-")
    workspace = g.codex_art._managed_directory(f"walkidle-{unit_id.replace('_', '-')}")
    sheet = workspace / "current-sheet.png"
    compose(unit_dir, sheet)
    dest = out_dir / unit_id
    dest.mkdir(parents=True, exist_ok=True)
    corrections: list[str] = []
    history = []
    for attempt in range(1, attempts + 1):
        target = workspace / f"sheet-{attempt}.png"
        prompt = PROMPT.format(name=target.name, guidance=GUIDANCE[kind], notes=scrub(notes),
                               corrections="".join(f"- Correction: {c}\n" for c in corrections))
        ok, output = g._codex_with_refs(prompt, [sheet], target, unit_id)
        if not ok:
            history.append({"attempt": attempt, "issues": ["blocked by the image safety system"
                                                           if "moderation_blocked" in output else "no image"]})
            if g.codex_art.QUOTA.search(output) and not g.codex_art.MODERATION.search(output):
                return {"unit": unit_id, "state": "quota_paused", "history": history}
            if "moderation_blocked" in output:
                break
            continue
        run = subprocess.run([str(g.codex_art.art_python()), "-c",
                              EXTRACT.format(tools=str(TOOLS), src=str(target), unit=str(unit_dir),
                                             dest=str(dest), redraw=REDRAW)],
                             capture_output=True, text=True, timeout=900)
        if run.returncode:
            problem = (run.stderr or run.stdout).strip().splitlines()[-1][-200:]
            history.append({"attempt": attempt, "issues": [problem]})
            corrections = ["Keep exactly two rows of six frames, each with its yellow label above it, wide empty "
                           "gaps between frames, and nothing else on the sheet."]
            continue
        report = json.loads(run.stdout.strip().splitlines()[-1])
        issues = evaluate(report)
        history.append({"attempt": attempt, "report": report, "issues": issues})
        if not issues:
            shutil.copyfile(target, dest / "sheet.png")
            return {"unit": unit_id, "state": "generated", "history": history}
        corrections = issues
    return {"unit": unit_id, "state": "failed", "history": history}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--only", action="append", required=True)
    parser.add_argument("--kind", choices=sorted(GUIDANCE), default="walker")
    parser.add_argument("--notes", default="", help="unit-specific guidance added to the prompt")
    parser.add_argument("--attempts", type=int, default=3)
    args = parser.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    results = []
    for unit_id in args.only:
        done = args.out_dir / unit_id / "sheet.png"
        if done.exists():
            print(json.dumps({"unit": unit_id, "state": "kept"}), flush=True)
            continue
        outcome = repair(unit_id, args.kind, args.notes, args.out_dir, args.attempts)
        results.append(outcome)
        print(json.dumps(outcome), flush=True)
        if outcome["state"] == "quota_paused":
            break
    return 0 if all(r["state"] == "generated" for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
