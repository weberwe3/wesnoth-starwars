#!/usr/bin/env python3
"""Install reviewed preview frames from gen_codex_reference_frames.py into the add-on.

Each SOURCE is a preview folder for one unit (`<preview>/<unit_id>` or
`<preview>/<unit_id>@<reference>`). Only animations marked as passed
(`.<animation>.passed`) are copied. A folder with its own standing.png
(a repaired or reference unit) also installs that sprite, and the idle
frames are derived from it again; a craft folder (all 12 frames, no
markers) is copied whole.

Usage (art Python): install_reference_frames.py SOURCE [SOURCE ...]
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
from derive_unit_frames import derive  # noqa: E402
from gen_codex_reference_frames import ANIMATIONS, UNITS  # noqa: E402

ALL_FRAMES = ["standing", "idle-1", "idle-2"] + [n for names, _ in ANIMATIONS.values() for n in names
                                                 if not n.startswith("idle")]


def install(source: Path) -> str:
    unit_id = source.name.split("@")[0]
    target = UNITS / unit_id.replace("_", "-")
    if not target.is_dir():
        raise SystemExit(f"{unit_id}: no art folder {target}")
    markers = sorted(source.glob(".*.passed"))
    if not markers:
        missing = [n for n in ALL_FRAMES if not (source / f"{n}.png").exists()]
        if missing:
            raise SystemExit(f"{source}: no passed animations and incomplete frames {missing}")
        for name in ALL_FRAMES:
            shutil.copyfile(source / f"{name}.png", target / f"{name}.png")
        return f"{unit_id}: all frames"
    done = []
    if (source / "standing.png").exists():
        shutil.copyfile(source / "standing.png", target / "standing.png")
        derived = derive(Image.open(target / "standing.png").convert("RGBA"))
        for name in ("idle-1", "idle-2"):
            derived[name].save(target / f"{name}.png", optimize=True)
        done.append("standing+idle")
    for marker in markers:
        animation = marker.name[1:-len(".passed")]
        for name in ANIMATIONS[animation][0]:
            shutil.copyfile(source / f"{name}.png", target / f"{name}.png")
        done.append(animation)
    return f"{unit_id}: {', '.join(done)}"


def main() -> int:
    for arg in sys.argv[1:]:
        print(install(Path(arg)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
