#!/usr/bin/env python3
"""Have Codex redraw a 12-frame house-style sprite sheet for another unit.

Owner method (2026-10-06): attach an existing labelled 12-frame sheet in the
house style (the template) and the unit's reference image, and ask Codex to
"replace the characters in this sheet with the same character as the
reference, updating the frames to suit it -- be intelligent in the design".
The result keeps the template's layout (two labelled rows of six on a flat
green background), so production/tools/import_owner_sheet.py installs it.

Jobs are in owner_sheet_jobs.json: {unit_id: {"ref": [image, [x0, y0, x1, y1]]
or null, "notes": "...", optional "template": a sheet in ~/art-references}}; reference images live in ~/art-references (licensed;
see docs/ART_LICENSE_CANDIDATES.md). Every sheet is checked to split into 12
frames; a failing attempt is retried with a correction. Results go to
--out-dir for review; nothing is installed.

Usage: python3 production/tools/gen_codex_owner_sheets.py --template SHEET --out-dir DIR
       [--only UNIT_ID ...] [--attempts N]
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

JOBS = Path(__file__).resolve().parent / "owner_sheet_jobs.json"
LABELS = "standing, idle-1, idle-2, move-1, move-2, melee-1 (top row); melee-2, ranged-1, ranged-2, defend, death-1, death-2 (bottom row)"

PROMPT = """Use your image generation tool to create exactly ONE image and save it as {name} in the current working directory. Do not create any other files.

The FIRST attached image is a 12-frame pixel-art unit sprite sheet for a turn-based tactics game: two rows of six frames on a flat green background, each frame labelled in small yellow text ({labels}).

Replace the character in every frame of this sheet with {subject}. The frames should be updated to account for this character: {notes} Be intelligent in the design.

Keep from the template: the same layout of two rows of six frames, the same yellow labels in the same places, the same flat green background, the same pixel-art style, outline and shading, the same scale, and the same view (three-quarter, facing right). Keep the same character, colours and equipment in every frame, with clear empty space between frames so no frame touches another.
{corrections}
After saving, reply with only the file name."""

WITH_REF = "the same character as shown in the SECOND attached image ({described})"


def crop_ref(image: Path, box: list[int] | None, workspace: Path) -> Path:
    out = workspace / "reference.png"
    script = ("from PIL import Image; i = Image.open(%r).convert('RGBA'); w = Image.new('RGBA', i.size, 'white'); "
              "w.alpha_composite(i); c = w.convert('RGB')%s; k = max(1, 480 // max(c.size)); "
              "c = c.resize((c.width * k, c.height * k), Image.NEAREST) if k > 1 else c; c.thumbnail((900, 900)); c.save(%r)"
              % (str(image), f".crop({tuple(box)!r})" if box else "", str(out)))
    subprocess.run([str(g.codex_art.art_python()), "-c", script], check=True, capture_output=True, timeout=120)
    return out


def check_sheet(path: Path) -> str | None:
    script = ("import sys; sys.path.insert(0, %r); import import_owner_sheet as o; from PIL import Image; "
              "o.frames(o.figures(Image.open(%r)), True); print('ok')" % (str(Path(__file__).resolve().parent), str(path)))
    run = subprocess.run([str(g.codex_art.art_python()), "-c", script], capture_output=True, text=True, timeout=600)
    return None if run.returncode == 0 else (run.stderr or run.stdout).strip().splitlines()[-1][-200:]


def generate(unit_id: str, job: dict, template: Path, out_dir: Path, attempts: int) -> dict:
    direction = g.codex_art.load_direction(g.ROOT)
    described = scrub(job.get("describe") or direction["units"].get(unit_id, ""))
    workspace = g.codex_art._managed_directory(f"sheet-{unit_id.replace('_', '-')}")
    refs = [g.REFERENCES / job["template"] if job.get("template") else template]
    if job.get("ref"):
        image, box = job["ref"]
        refs.append(crop_ref(g.REFERENCES / image, box, workspace))
        subject = WITH_REF.format(described=described)
    else:
        subject = described
    corrections: list[str] = []
    history = []
    for attempt in range(1, attempts + 1):
        target = workspace / f"sheet-{attempt}.png"
        prompt = PROMPT.format(name=target.name, labels=LABELS, subject=subject, notes=scrub(job["notes"]),
                               corrections="".join(f"- Correction: {c}\n" for c in corrections))
        ok, output = g._codex_with_refs(prompt, refs, target, unit_id)
        if not ok:
            blocked = "moderation_blocked" in output
            history.append({"attempt": attempt, "issue": "blocked by the image safety system" if blocked else "no image"})
            if g.codex_art.QUOTA.search(output) and not g.codex_art.MODERATION.search(output):
                return {"unit": unit_id, "state": "quota_paused", "history": history}
            continue
        problem = check_sheet(target)
        history.append({"attempt": attempt, "issue": problem})
        if not problem:
            dest = out_dir / f"{unit_id}.png"
            shutil.copyfile(target, dest)
            return {"unit": unit_id, "state": "generated", "sheet": str(dest), "history": history}
        corrections = [f"The previous sheet could not be split into its 12 frames ({problem}). Keep exactly two "
                       "rows of six frames, each with its yellow label above it, wide empty gaps between frames, "
                       "and nothing else on the sheet."]
    return {"unit": unit_id, "state": "failed", "history": history}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--template", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--only", action="append")
    parser.add_argument("--attempts", type=int, default=3)
    args = parser.parse_args()
    jobs = json.loads(JOBS.read_text(encoding="utf-8"))
    args.out_dir.mkdir(parents=True, exist_ok=True)
    results = []
    for unit_id in args.only or [u for u in jobs if not u.startswith("_")]:
        outcome = generate(unit_id, jobs[unit_id], args.template, args.out_dir, args.attempts)
        results.append(outcome)
        print(json.dumps(outcome), flush=True)
        if outcome["state"] == "quota_paused":
            break
    return 0 if all(r["state"] == "generated" for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
