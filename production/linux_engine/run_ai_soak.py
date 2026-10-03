#!/usr/bin/env python3
"""AI soak test: let the AI play every scenario through on the Linux engine.

For each scenario, the add-on is staged with its campaign's first_scenario
pointed at that scenario, side 1 is handed to the AI, and the engine plays
until the scenario ends (or a turn cap). This exercises everything the
scripted campaign-sequence probe skips: turn-based events, reinforcement
waves, hazards, storms, AI movement, and combat.

A scenario FAILS on any WML/Lua/engine error during play, or if it never
starts. The outcome (victory, defeat, turn cap) is recorded as a rough
balance signal only: an AI-controlled player is not a human player.

Usage:
  python3 production/linux_engine/run_ai_soak.py [--campaign ID] [--scenario ID]
      [--player default|careful] [--jobs 2] [--workdir DIR] [--output evidence.json]
"""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from run_campaign_sequence import ADDON, ADDON_ID, CAMPAIGNS, DEFAULT_ENGINE, FATAL_LOG  # noqa: E402

PLUGIN = Path(__file__).resolve().parent / "ai_soak_plugin.lua"
PLAY_ERRORS = re.compile(
    r"(error (?:wml|config|lua|engine|scripting)[^:]*:|lua error|stack traceback|"
    r"unknown unit type|invalid WML|could not find)",
    re.IGNORECASE,
)


def soak_one(engine: Path, campaign: str, scenario: str, workdir: Path, timeout: int,
             player: str = "default") -> dict:
    userdata = workdir / "userdata"
    if workdir.exists():
        shutil.rmtree(workdir)
    (userdata / "logs").mkdir(parents=True)
    staged = userdata / "data/add-ons" / ADDON_ID
    shutil.copytree(ADDON, staged)
    main_cfg = staged / "_main.cfg"
    first = CAMPAIGNS[campaign][0]
    text = main_cfg.read_text(encoding="utf-8")
    if f"first_scenario={first}" not in text:
        return {"scenario": scenario, "pass": False, "failures": [f"first_scenario {first} not found"]}
    main_cfg.write_text(text.replace(f"first_scenario={first}", f"first_scenario={scenario}", 1), encoding="utf-8")
    plugin = workdir / "ai_soak_plugin.lua"
    plugin.write_text(
        PLUGIN.read_text(encoding="utf-8").replace(
            'local CAMPAIGN = "Star_Wars_Thrawn_Trilogy"', f'local CAMPAIGN = "{campaign}"').replace(
            'local PLAYER_STYLE = "default"', f'local PLAYER_STYLE = "{player}"'),
        encoding="utf-8",
    )
    # Skip animations and AI move playback: the soak checks logic, not looks.
    (userdata / "preferences").write_text(
        'skip_ai_moves=yes\nanimate_map=no\nanimate_water=no\nidle_anim=no\nturbo=yes\nturbo_speed=20\n',
        encoding="utf-8",
    )
    environment = dict(os.environ)
    environment.setdefault("SDL_VIDEO_DRIVER", "offscreen")
    environment.setdefault("SDL_AUDIO_DRIVER", "dummy")
    started = time.time()
    process = subprocess.Popen(
        [str(engine), "--resolution", "1024x768", "--userdata-dir", str(userdata), "--plugin", str(plugin)],
        cwd=workdir, env=environment, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    timed_out = False

    def log_text() -> str:
        return "\n".join(p.read_text(encoding="utf-8", errors="replace")
                         for p in sorted((userdata / "logs").glob("*.log")))

    while process.poll() is None:
        if "SW_SOAK: done" in log_text() or "SW_SOAK: fatal" in log_text():
            time.sleep(3)
            break
        if time.time() - started > timeout:
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
    text = log_text()
    lines = [line[len("SW_SOAK: "):] for line in text.splitlines() if line.startswith("SW_SOAK: ")]
    result = next((line for line in lines if line.startswith("result ")), None)
    turns = [int(m.group(1)) for line in lines for m in [re.match(r"turn (\d+)$", line)] if m]
    errors = sorted({line.strip() for line in text.splitlines()
                     if (PLAY_ERRORS.search(line) or FATAL_LOG.search(line))
                     and "could not open image" not in line
                     # Air sorties fly a fake unit over enemy-held hexes; the
                     # engine warns, then uses its emergency path as intended.
                     and "move_unit_fake route" not in line})
    failures = [line for line in lines if line.startswith("fatal")]
    if not any(line.startswith("scenario ") for line in lines):
        failures.append("scenario never started")
    if timed_out and result is None:
        failures.append(f"timed out after {timeout}s")
    failures.extend(f"log: {line}"[:300] for line in errors[:10])
    deaths = [line[len("died "):] for line in lines if line.startswith("died ")]
    return {
        "scenario": scenario,
        "campaign": campaign,
        "player": player,
        "side1_deaths": [d for d in deaths if " side 1 " in d][:12],
        "pass": not failures,
        "outcome": result,
        "turns_played": max(turns) if turns else 0,
        "seconds": round(time.time() - started, 1),
        "failures": failures,
        "intel": next((line[len("intel "):] for line in reversed(lines) if line.startswith("intel ")), None),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine", type=Path, default=Path(os.environ.get("WESNOTH_LINUX_ENGINE", DEFAULT_ENGINE)))
    parser.add_argument("--campaign", choices=sorted(CAMPAIGNS))
    parser.add_argument("--scenario")
    parser.add_argument("--jobs", type=int, default=2)
    parser.add_argument("--timeout", type=int, default=600)
    parser.add_argument("--player", choices=("default", "careful"), default="default",
                        help="side-1 AI style; 'careful' protects units like a human with heroes")
    parser.add_argument("--workdir", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    workdir = args.workdir or Path(tempfile.mkdtemp(prefix="sw-soak-"))
    work = [(campaign, scenario) for campaign, scenarios in CAMPAIGNS.items()
            if not args.campaign or campaign == args.campaign
            for scenario in scenarios if not args.scenario or scenario == args.scenario]
    results: list[dict] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, args.jobs)) as pool:
        futures = {pool.submit(soak_one, args.engine, campaign, scenario, workdir / scenario, args.timeout, args.player): scenario
                   for campaign, scenario in work}
        for future in concurrent.futures.as_completed(futures):
            item = future.result()
            results.append(item)
            print(f"{item['scenario']}: {'PASS' if item['pass'] else 'FAIL'} "
                  f"{item.get('outcome')} turns={item.get('turns_played')} {item.get('seconds')}s "
                  f"{'; '.join(item['failures'])[:300]}", flush=True)
    order = {scenario: i for i, (_, scenario) in enumerate(work)}
    results.sort(key=lambda item: order.get(item["scenario"], 0))
    evidence = {"schema_version": 1, "kind": "linux-ai-soak", "engine": str(args.engine), "player": args.player,
                "results": results, "pass": all(item["pass"] for item in results)}
    if args.output:
        args.output.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    return 0 if evidence["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
