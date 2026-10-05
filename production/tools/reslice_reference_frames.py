#!/usr/bin/env python3
"""Re-cut generated animation strips into frames without new Codex calls.

gen_codex_reference_frames.py keeps every Codex strip in its art workspace
(WesnothAgentWorktrees/art-gen/anim-<unit>-<animation>-<attempt>-<time>/frames.png).
After a change to the cutting step (SLICE), this re-cuts the strip of each
animation's passing attempt and rewrites the preview frames that still pass
evaluate().

Usage: reslice_reference_frames.py --preview-dir DIR [--only UNIT_ID ...]
       [--standing-from-preview]
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gen_codex_reference_frames as g  # noqa: E402

ART_GEN = Path("/mnt/c/Users") / Path.home().name / "Documents/Codex/WesnothAgentWorktrees/art-gen"


def strip_for(unit_id: str, animation: str, attempt: int, before: float) -> Path | None:
    """The strip of that attempt made last before the animation passed (a unit
    animated twice, e.g. a repair and a reference version, has several)."""
    slug = unit_id.replace("_", "-")
    numbered = list(ART_GEN.glob(f"anim-{slug}-{animation}-{attempt}-*/frames.png"))
    plain = [p for p in ART_GEN.glob(f"anim-{slug}-{animation}-*/frames.png")
             if re.fullmatch(rf"anim-{re.escape(slug)}-{animation}-\d{{8}}-\d{{6}}", p.parent.name)]
    found = sorted((p for p in numbered or plain if p.stat().st_mtime <= before + 1), key=lambda p: p.stat().st_mtime)
    return found[-1] if found else None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preview-dir", type=Path, required=True)
    parser.add_argument("--only", action="append")
    parser.add_argument("--standing-from-preview", action="store_true",
                        help="the reference standing sprite is the preview folder's own (repairs, references)")
    args = parser.parse_args()
    for dest in sorted(d for d in args.preview_dir.iterdir() if d.is_dir()):
        unit_id = dest.name.split("@")[0]
        if args.only and unit_id not in args.only:
            continue
        standing = (dest / "standing.png") if args.standing_from_preview else \
            g.UNITS / unit_id.replace("_", "-") / "standing.png"
        for marker in sorted(dest.glob(".*.passed")):
            animation = marker.name[1:-len(".passed")]
            history = json.loads(marker.read_text(encoding="utf-8"))
            attempt = history[-1]["attempt"]
            src = strip_for(unit_id, animation, attempt, marker.stat().st_mtime)
            if not src:
                print(f"{unit_id} {animation}: strip not found")
                continue
            names = g.ANIMATIONS[animation][0]
            stage = src.parent / "restage"
            stage.mkdir(exist_ok=True)
            script = g.SLICE.format(tools=str(g.ROOT / "production/tools"), ref=str(standing), src=str(src),
                                    count=len(names), names=names, lying=["death-2"], stage=str(stage))
            run = subprocess.run([str(g.codex_art.art_python()), "-c", script], capture_output=True, text=True,
                                 timeout=300, check=False)
            if run.returncode:
                print(f"{unit_id} {animation}: cut failed: {(run.stderr or run.stdout)[-200:]}")
                continue
            issues = g.evaluate(animation, names, json.loads(run.stdout.strip().splitlines()[-1]))
            if issues:
                print(f"{unit_id} {animation}: kept old frames; re-cut fails: {issues}")
                continue
            for name in names:
                shutil.copyfile(stage / f"{name}.png", dest / f"{name}.png")
            print(f"{unit_id} {animation}: re-cut")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
