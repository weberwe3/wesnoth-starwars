#!/usr/bin/env python3
"""Have Codex paint the story-screen backdrops, one per setting.

The story slides before each mission were plain black. Each setting below gets
one painted backdrop (cinematic concept-art style, darker toward the bottom
where the story text sits). Prompts are in-universe and name nothing
(owner rule; prompt_scrub). Results are cropped to 16:9, resized to 1280x720
and saved as JPEG in images/story/sw-story-<key>.jpg; the raw images stay in
the Codex workspace. A setting whose file already exists is skipped.

Usage: python3 production/tools/gen_codex_story_backdrops.py [--only KEY ...] [--attempts N]
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gen_codex_reference_frames as g  # noqa: E402

OUT = g.ROOT / "addons/Star_Wars_Thrawn_Trilogy/images/story"

SETTINGS = {
    "bridge": "the dim command bridge of a huge wedge-shaped military warship: a long forward viewport full of stars "
              "and a distant planet, sunken crew pits with glowing consoles below a raised walkway, cold blue-grey light",
    "fleet-attack": "two enormous wedge-shaped grey warships emerging from the darkness at the edge of a star system, "
                    "launching swarms of small fighters, streaks of green and red laser fire, a planet and its moons below",
    "dark-forest": "a dense alien forest of colossal pale-barked trees at twilight, mist on the ground, shafts of cold "
                   "light through the canopy, hanging vines, an oppressive, silent mood",
    "city-world": "a planet-wide city at dusk: endless towers to the horizon, streams of flying traffic, a vast "
                  "pyramid-shaped palace in the middle distance, warm windows against a violet sky",
    "palace-night": "the long, high-ceilinged corridor of a grand government palace at night, polished stone floors, "
                    "tall windows showing city lights, guards' lamps far away, deep shadows",
    "asteroids": "a lone small starfighter drifting beside a slowly tumbling cluster of dark asteroids in deep space, "
                 "a faint nebula behind, cold starlight",
    "tree-city": "a city of wooden platforms, round huts and rope bridges built high among colossal trees kilometres "
                 "tall, warm lantern light, mist and darkness far below",
    "mining-city": "a gigantic tracked mining city crawling across a scorched, cracked planet surface, a huge blazing "
                   "sun filling the sky, heat shimmer, the city's shadow side lit by work lights",
    "shipyard": "an orbital shipyard above a blue planet: huge skeletal dock frameworks, dozens of docked warships "
                "under repair, work lights, small tugs moving between them",
    "brown-world": "a barren world brown from horizon to horizon with no green anywhere, eroded terraced fields, small "
                   "dome-shaped machines crawling over the dirt, a village of low stone houses under a hazy sky",
    "lake-island": "a dark mountain lake surrounded by forest, a jagged rocky island peak in the middle with an old "
                   "stone hermitage on the summit, storm clouds gathering, a single light in a window",
    "spaceport": "a crowded, grimy spaceport town at night, battered cargo ships on landing pads, glowing signs "
                 "without any readable text, steam and smoke, figures in long coats",
    "hidden-base": "a hidden military base cut into a rocky mountainside, a hangar door half open with small fighters "
                   "inside, guard lights sweeping a landing pad, low clouds",
    "ghost-fleet": "a long line of identical old, dark heavy cruisers drifting in deep space, their running lights "
                   "dead, hulls pale grey in starlight, stretching away into the distance, eerie and silent",
    "derelict": "the interior of an old abandoned warship: a long dim corridor with emergency lighting, drifting dust, "
                "open blast doors, frost on the bulkheads",
    "orbit-siege": "space above a city-covered planet at night, orbital defence platforms, a cargo ship breaking apart "
                   "after striking something invisible, faint glints of hidden rocks",
    "jungle-mountain": "a steaming jungle world: a single huge forested mountain rising above an endless green "
                       "canopy, mist in the valleys, a small crashed ship smoking among the trees",
    "clone-vats": "rows of tall glass cylinders glowing faintly green inside a dark cavern laboratory carved into a "
                  "mountain, cables and pipes, catwalks, cold mist",
    "throne-room": "a vast dark throne room carved inside a mountain, a raised throne under a single shaft of light, "
                   "massive stone pillars, deep red and black tones",
}

PROMPT = """Use your image generation tool to create exactly ONE image and save it as {name} in the current working directory. Do not create any other files.

Paint a wide cinematic background for a story screen in a science-fiction strategy game: {subject}.

Style: painterly digital concept art, rich lighting, strong silhouettes, a sense of scale. Wide landscape format. Keep the lower third of the image darker and less detailed, because story text is shown over it. No text, no letters, no logos, no user interface, and no close-up faces or recognisable people.

After saving, reply with only the file name."""


def finish(raw: Path, dest: Path) -> None:
    script = ("from PIL import Image; i = Image.open(%r).convert('RGB'); w, h = i.size; th = round(w * 9 / 16); "
              "i = i.crop((0, (h - th) // 2, w, (h - th) // 2 + th)) if th <= h else "
              "i.crop(((w - round(h * 16 / 9)) // 2, 0, (w + round(h * 16 / 9)) // 2, h)); "
              "i.resize((1280, 720), Image.LANCZOS).save(%r, quality=84, optimize=True, progressive=True)"
              % (str(raw), str(dest)))
    subprocess.run([str(g.codex_art.art_python()), "-c", script], check=True, timeout=120)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", action="append")
    parser.add_argument("--attempts", type=int, default=2)
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    failed = 0
    for key, subject in SETTINGS.items():
        dest = OUT / f"sw-story-{key}.jpg"
        if (args.only and key not in args.only) or (dest.exists() and not args.only):
            continue
        workspace = g.codex_art._managed_directory(f"story-{key}")
        state = "failed"
        for attempt in range(1, args.attempts + 1):
            target = workspace / f"backdrop-{attempt}.png"
            ok, output = g._codex_with_refs(PROMPT.format(name=target.name, subject=subject), [], target, key)
            if ok:
                finish(target, dest)
                state = "generated"
                break
            if g.codex_art.QUOTA.search(output) and not g.codex_art.MODERATION.search(output):
                print(json.dumps({"setting": key, "state": "quota_paused"}), flush=True)
                return 1
        failed += state != "generated"
        print(json.dumps({"setting": key, "state": state, "file": str(dest)}), flush=True)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
