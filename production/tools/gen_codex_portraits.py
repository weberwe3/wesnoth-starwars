#!/usr/bin/env python3
"""Regenerate dialogue portraits with Codex for heroes that lack a proper bust.

Run only while no other Codex art generation is active: one image per call
is harvested from the shared Codex image folder by time window.

Usage: python3 production/tools/gen_codex_portraits.py [--unit sw_hero_han ...]
Default units: the heroes whose portrait used to be framed from the sprite.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "agent" / "coordinator"))
import codex_art  # noqa: E402

DEFAULT_UNITS = {
    "sw_hero_han": "Han Solo",
    "sw_hero_leia": "Leia Organa Solo",
    "sw_hero_lando": "Lando Calrissian",
    "sw_hero_pellaeon": "Captain Pellaeon",
    "sw_hero_wedge": "Wedge Antilles",
    "sw_hero_luke": "Luke Skywalker",
    "sw_hero_chewbacca": "Chewbacca",
}


# Units that speak with another unit's face: the pilot of a starfighter form.
PORTRAIT_ALIASES = {"sw_hero_xwing_luke": "sw_hero_luke"}
PORTRAITS = ROOT / "addons/Star_Wars_Thrawn_Trilogy/images/portraits"


def slug(unit_id: str) -> str:
    return unit_id.replace("_", "-")


def copy_aliases() -> None:
    for alias, source in PORTRAIT_ALIASES.items():
        (PORTRAITS / f"{slug(alias)}.png").write_bytes((PORTRAITS / f"{slug(source)}.png").read_bytes())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--unit", action="append", choices=sorted(DEFAULT_UNITS))
    args = parser.parse_args()
    results = []
    for unit_id in args.unit or list(DEFAULT_UNITS):
        try:
            outcome = codex_art.generate_portrait(ROOT, unit_id, DEFAULT_UNITS[unit_id])
        except codex_art.CodexArtError as exc:
            outcome = {"unit_id": unit_id, "state": "failed", "reason": str(exc)[:300]}
        results.append(outcome)
        print(json.dumps(outcome), flush=True)
        if outcome["state"] == "quota_paused":
            break
    copy_aliases()
    return 0 if all(item["state"] in {"generated", "refused"} for item in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
