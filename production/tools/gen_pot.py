#!/usr/bin/env python3
"""Regenerate the add-on's translation template (.pot) with wmlxgettext.

Every player-facing string is marked translatable (_ "...") under the
wesnoth-Star_Wars_Thrawn_Trilogy textdomain; this collects them into
translations/wesnoth-Star_Wars_Thrawn_Trilogy.pot so translators can start
.po files. Uses the wmlxgettext tool shipped in Wesnoth's data/tools.

Usage: python3 production/tools/gen_pot.py [--wesnoth-data ~/opt/wesnoth-1.19.27/data]
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ADDON = ROOT / "addons/Star_Wars_Thrawn_Trilogy"
DOMAIN = "wesnoth-Star_Wars_Thrawn_Trilogy"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wesnoth-data", type=Path, default=Path.home() / "opt/wesnoth-1.19.27/data")
    args = parser.parse_args()
    tool = args.wesnoth_data / "tools" / "wmlxgettext"
    if not tool.is_file():
        print(f"wmlxgettext not found at {tool}", file=sys.stderr)
        return 2
    files = sorted(str(p.relative_to(ADDON)) for p in ADDON.rglob("*") if p.suffix in (".cfg", ".lua"))
    out = ADDON / "translations"
    completed = subprocess.run(
        [sys.executable, str(tool), "-o", str(out), f"--domain={DOMAIN}", f"--directory={ADDON}",
         "--package-version=1.0", "--no-text-colors", *files],
        capture_output=True, text=True, check=False,
    )
    if completed.returncode:
        print(completed.stdout[-2000:], completed.stderr[-2000:], file=sys.stderr)
        return completed.returncode
    pot = out / f"{DOMAIN}.pot"
    # wmlxgettext ends the file with a blank line, which the whitespace gate rejects.
    pot.write_text(pot.read_text(encoding="utf-8").rstrip("\n") + "\n", encoding="utf-8")
    print(f"wrote {pot.relative_to(ROOT)}: {pot.read_text(encoding='utf-8').count('msgid ') - 1} strings")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
