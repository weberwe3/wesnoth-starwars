#!/usr/bin/env python3
"""Run the Campaign I sequence probe on the Linux Wesnoth GUI harness.

Stages the add-on into an isolated userdata directory, launches the Linux
engine (SDL offscreen video, dummy audio) with campaign_sequence_plugin.lua,
and writes a JSON evidence summary.

The probe enters the real campaign through the title screen, so it exercises
GUI campaign entry, every scenario load, scripted win events, linger mode,
transition, hero carryover, and in-game saves. Exit code 0 means every
expected scenario was entered in order and no fatal WML/Lua error was logged.

Usage:
  python3 production/linux_engine/run_campaign_sequence.py [--engine PATH]
      [--workdir DIR] [--output evidence.json] [--timeout SECONDS]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ADDON_ID = "Star_Wars_Thrawn_Trilogy"
ADDON = ROOT / "addons" / ADDON_ID
PLUGIN = Path(__file__).resolve().parent / "campaign_sequence_plugin.lua"
CAMPAIGN_I = "Star_Wars_Thrawn_Trilogy"
CAMPAIGN_II = "Star_Wars_Thrawn_Trilogy_Dark_Force_Rising"
EXPECTED = [
    "sw_hte_01_ysalamiri_harvest",
    "sw_hte_02_ambush_at_bpfassh",
    "sw_hte_03_adrift",
    "sw_hte_04_shadows_of_kashyyyk",
    "sw_hte_05_prisoner_of_myrkr",
    "sw_hte_06_raid_on_karrdes_base",
    "sw_hte_07_the_forest_crossing",
    "sw_hte_08_nomad_city",
    "sw_hte_09_sluis_van_shipyards",
    "sw_hte_10_thrawns_gambit",
]
EXPECTED_II = [
    "sw_dfr_01_the_noghri_prisoner",
    "sw_dfr_02_honoghr",
    "sw_dfr_03_jomark",
    "sw_dfr_04_the_senators_men",
    "sw_dfr_05_peregrines_nest",
    "sw_dfr_06_the_mad_jedi",
    "sw_dfr_07_the_dark_force",
    "sw_dfr_08_aboard_the_katana",
    "sw_dfr_09_battle_for_the_fleet",
    "sw_dfr_10_honoghrs_choice",
]
CAMPAIGNS = {CAMPAIGN_I: EXPECTED, CAMPAIGN_II: EXPECTED_II}
# Heroes that must be on the map when each scenario becomes playable.
REQUIRED_HEROES = {
    "sw_hte_01_ysalamiri_harvest": ["sw_hero_pellaeon"],
    "sw_hte_02_ambush_at_bpfassh": ["sw_hero_leia", "sw_hero_han", "sw_hero_chewbacca"],
    "sw_hte_03_adrift": ["sw_hero_luke"],
    "sw_hte_04_shadows_of_kashyyyk": ["sw_hero_leia", "sw_hero_chewbacca"],
    "sw_hte_05_prisoner_of_myrkr": ["sw_hero_luke"],
    "sw_hte_06_raid_on_karrdes_base": ["sw_hero_han", "sw_hero_lando", "sw_hero_karrde"],
    "sw_hte_07_the_forest_crossing": ["sw_hero_luke", "sw_hero_mara"],
    "sw_hte_08_nomad_city": ["sw_hero_lando", "sw_hero_han"],
    "sw_hte_09_sluis_van_shipyards": ["sw_hero_wedge", "sw_hero_luke"],
    "sw_hte_10_thrawns_gambit": ["sw_hero_wedge", "sw_hero_luke"],
    "sw_dfr_01_the_noghri_prisoner": ["sw_hero_leia", "sw_hero_chewbacca"],
    "sw_dfr_02_honoghr": ["sw_hero_leia", "sw_hero_chewbacca", "sw_hero_khabarakh"],
    "sw_dfr_03_jomark": ["sw_hero_luke"],
    "sw_dfr_04_the_senators_men": ["sw_hero_han", "sw_hero_lando"],
    "sw_dfr_05_peregrines_nest": ["sw_hero_han", "sw_hero_lando", "sw_hero_bel_iblis"],
    "sw_dfr_06_the_mad_jedi": ["sw_hero_luke"],
    "sw_dfr_07_the_dark_force": ["sw_hero_wedge", "sw_hero_luke"],
    "sw_dfr_08_aboard_the_katana": ["sw_hero_luke", "sw_hero_han", "sw_hero_lando", "sw_hero_chewbacca"],
    "sw_dfr_09_battle_for_the_fleet": ["sw_hero_wedge", "sw_hero_luke"],
    "sw_dfr_10_honoghrs_choice": ["sw_hero_leia", "sw_hero_chewbacca", "sw_hero_khabarakh"],
}
# Heroes that must NOT be on the map (stashed or out of story).
FORBIDDEN_HEROES = {
    "sw_hte_03_adrift": ["sw_hero_leia", "sw_hero_han", "sw_hero_chewbacca"],
    "sw_hte_05_prisoner_of_myrkr": ["sw_hero_leia", "sw_hero_han", "sw_hero_chewbacca", "sw_hero_mara"],
}
FATAL_LOG = re.compile(
    r"(error (?:wml|config|lua|engine|preprocessor|scripting)|lua error|"
    r"Invalid WML|unknown unit type|could not find|Failed to load|traceback)",
    re.IGNORECASE,
)
DEFAULT_ENGINE = Path.home() / "opt/bin/wesnoth-linux"


def sha256_tree(root: Path) -> str:
    h = hashlib.sha256()
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        h.update(path.relative_to(root).as_posix().encode())
        h.update(b"\0")
        h.update(path.read_bytes())
    return h.hexdigest()


def parse(log_text: str) -> dict:
    scenarios: list[dict] = []
    current: dict | None = None
    notes: list[str] = []
    for line in log_text.splitlines():
        if not line.startswith("SW_SEQ: "):
            continue
        body = line[len("SW_SEQ: "):]
        if body.startswith("scenario "):
            parts = body.split()
            current = {"id": parts[1], "heroes_on_map": {}, "saved": False, "won": False, "left": None}
            scenarios.append(current)
        elif current is not None and body.startswith("heroes_on_map "):
            for item in body[len("heroes_on_map "):].split(";"):
                if "=" in item:
                    hid, rest = item.split("=", 1)
                    current["heroes_on_map"][hid] = rest
        elif current is not None and body.startswith("heroes_on_recall "):
            current["heroes_on_recall"] = [x for x in body[len("heroes_on_recall "):].split(";") if x]
        elif current is not None and body.startswith("stashed "):
            current["stashed"] = [x for x in body[len("stashed "):].split(";") if x]
        elif current is not None and body.startswith("side1_gold "):
            current["side1_gold"] = int(body.split()[1])
        elif current is not None and body.startswith("saved "):
            current["saved"] = True
        elif current is not None and body.startswith("win script ran "):
            current["won"] = True
        elif current is not None and body.startswith("left "):
            current["left"] = body
        else:
            notes.append(body)
    return {"scenarios": scenarios, "notes": notes}


def evaluate(parsed: dict, log_text: str, expected: list[str] | None = None) -> list[str]:
    failures: list[str] = []
    expected = expected or EXPECTED
    ids = [s["id"] for s in parsed["scenarios"]]
    if ids != expected:
        failures.append(f"scenario order {ids} != expected {expected}")
    for s in parsed["scenarios"]:
        for hero in REQUIRED_HEROES.get(s["id"], []):
            if hero not in s["heroes_on_map"]:
                failures.append(f"{s['id']}: required hero {hero} missing")
        for hero in FORBIDDEN_HEROES.get(s["id"], []):
            if hero in s["heroes_on_map"]:
                failures.append(f"{s['id']}: hero {hero} should not be present")
        if not s["saved"]:
            failures.append(f"{s['id']}: in-game save not confirmed")
        if not s["won"]:
            failures.append(f"{s['id']}: win script did not run")
    for note in parsed["notes"]:
        if note.startswith(("fatal", "win_script_error")):
            failures.append(note)
    if "done" not in parsed["notes"]:
        failures.append("probe did not finish")
    fatal = sorted({line.strip() for line in log_text.splitlines()
                    if FATAL_LOG.search(line) and "could not open image" not in line})
    failures.extend(f"log: {line}"[:300] for line in fatal[:20])
    return failures


def run_sequence(addon: Path, engine: Path, workdir: Path, timeout: int = 2400,
                 campaign: str = CAMPAIGN_I) -> dict:
    """Stage ``addon`` in isolated userdata, run the plugin, return evidence."""

    expected = CAMPAIGNS[campaign]
    workdir.mkdir(parents=True, exist_ok=True)
    plugin = workdir / "campaign_sequence_plugin.lua"
    plugin.write_text(
        PLUGIN.read_text(encoding="utf-8")
        .replace('local CAMPAIGN = "Star_Wars_Thrawn_Trilogy"', f'local CAMPAIGN = "{campaign}"')
        .replace('local FINAL_SCENARIO = "sw_hte_10_thrawns_gambit"', f'local FINAL_SCENARIO = "{expected[-1]}"'),
        encoding="utf-8",
    )
    userdata = workdir / "userdata"
    if userdata.exists():
        shutil.rmtree(userdata)
    (userdata / "logs").mkdir(parents=True)
    (userdata / "data/add-ons").mkdir(parents=True)
    shutil.copytree(addon, userdata / "data/add-ons" / ADDON_ID)
    started = time.time()
    environment = dict(os.environ)
    environment.setdefault("SDL_VIDEO_DRIVER", "offscreen")
    environment.setdefault("SDL_AUDIO_DRIVER", "dummy")
    # The engine does not always exit after the plugin calls exit; once the
    # probe reports "done" (or the deadline passes) the process is ended.
    process = subprocess.Popen(
        [str(engine), "--resolution", "1024x768", "--userdata-dir", str(userdata), "--plugin", str(plugin)],
        cwd=workdir, env=environment, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    timed_out = False
    deadline = started + timeout
    while process.poll() is None:
        if any("SW_SEQ: done" in p.read_text(encoding="utf-8", errors="replace")
               for p in (userdata / "logs").glob("*.log")):
            time.sleep(3)
            break
        if time.time() > deadline:
            timed_out = True
            break
        time.sleep(2)
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=20)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
    exit_code: int | None = None if timed_out else process.returncode
    log_text = "\n".join(p.read_text(encoding="utf-8", errors="replace")
                         for p in sorted((userdata / "logs").glob("*.log")))
    parsed = parse(log_text)
    failures = evaluate(parsed, log_text, expected)
    if timed_out:
        failures.append(f"engine timed out after {timeout}s")
    return {
        "schema_version": 1,
        "kind": "linux-gui-campaign-sequence",
        "campaign": campaign,
        "engine": str(engine),
        "addon_sha256": sha256_tree(addon),
        "plugin_sha256": hashlib.sha256(PLUGIN.read_bytes()).hexdigest(),
        "exit_code": exit_code,
        "seconds": round(time.time() - started, 1),
        "scenarios": parsed["scenarios"],
        "saves": sorted(p.name for p in userdata.rglob("sw_seq_*.gz")),
        "failures": failures,
        "pass": not failures,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine", type=Path, default=Path(os.environ.get("WESNOTH_LINUX_ENGINE", DEFAULT_ENGINE)))
    parser.add_argument("--addon", type=Path, default=ADDON)
    parser.add_argument("--workdir", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--timeout", type=int, default=2400)
    parser.add_argument("--campaign", choices=sorted(CAMPAIGNS), default=CAMPAIGN_I)
    args = parser.parse_args()
    if not args.engine.is_file():
        print(f"Linux engine not found: {args.engine}", file=sys.stderr)
        return 2
    workdir = args.workdir or Path(tempfile.mkdtemp(prefix="sw-seq-"))
    evidence = run_sequence(args.addon, args.engine, workdir, args.timeout, args.campaign)
    text = json.dumps(evidence, indent=2)
    if args.output:
        args.output.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0 if evidence["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
