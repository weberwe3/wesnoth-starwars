#!/usr/bin/env python3
"""Have Codex compose the add-on's music as scores; render them orchestrally.

Owner direction (2026-10-10): remake the music with Codex, following a
memorable-game-music methodology (a 3-7 note hook in the first two bars,
2/4/8-bar phrases, A-A'-B-A'' form, a recurring 2-4 chord progression, a
distinct bass, a countermelody, repetition with variation, a composed
transition back to the opening), with the instruments and sound of a classic
space-opera film score.

Codex cannot make audio, so it writes each track as a Python score against
production/tools/music/score.py; this tool checks and renders it with recorded
orchestral samples (MuseScore General SoundFont, MIT). Prompts name no
franchise or character (owner rule; prompt_scrub) and require original
melodies: no quotation or close paraphrase of any existing film theme.

Scores are kept in production/tools/music/scores/<track>.py; renders go to the
add-on's music/ folder (or --out). A failing score is retried with the error.

Usage: python3 production/tools/gen_codex_music_scores.py [--only TRACK ...] [--out DIR]
       [--render-only]   (re-render existing scores without calling Codex)
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import time
import traceback
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(TOOLS / "music"))
import gen_codex_reference_frames as g  # noqa: E402
import score as sc  # noqa: E402
from prompt_scrub import check as scrub_check  # noqa: E402

SCORES = TOOLS / "music" / "scores"
OUT = g.ROOT / "addons/Star_Wars_Thrawn_Trilogy/music"

STYLE = (
    "the sound of a classic late-1970s/early-1980s space-opera film score played by a full symphony orchestra: "
    "bold, noble brass fanfares (trumpets and horns in unison or octaves) with leaping intervals (rising fourths, "
    "fifths and sixths) and quick triplet pickups; driving, rhythmic string ostinatos; sweeping legato strings and "
    "horns for lyrical themes; martial snare and timpani; cymbal crashes on phrase arrivals; harp glissandi and "
    "celesta or glockenspiel sparkle; choir for mystery and menace; Lydian colour (raised fourth) for wonder; "
    "chromatic-mediant chord shifts (e.g. C major to A-flat major or E major) for drama; clear, singable melodies "
    "doubled across sections the way a late-romantic film orchestra is scored"
)

TRACKS = {
    "sw-heroic": "the heroes' main theme for battles of the young allied republic: triumphant and optimistic, "
                 "B-flat major, about 108 bpm, trumpet-and-horn melody over a galloping string ostinato, "
                 "ending each A section on a heroic arrival chord",
    "sw-imperial": "the military regime's march: menacing, heavy and disciplined, G minor, about 100 bpm in 4/4 "
                   "march time, low brass (trombones, tuba, horns) melody with dotted rhythms over a relentless "
                   "low-string and timpani ostinato, snare drum, minor chords moving by chromatic mediants. "
                   "Do not use a repeated three-note opening on one pitch or any well-known march's rhythm",
    "sw-space": "a starfighter dogfight in space: fast, thrilling and urgent, E minor with bright major "
                "flashes, about 144 bpm, racing sixteenth-note violins, brass stabs and syncopated horn calls, "
                "xylophone-like glockenspiel accents, timpani and snare driving, a heroic trumpet hook",
    "sw-battle": "a ground battle in forests and outposts: tense, determined and percussive, C minor, about "
                 "126 bpm, pounding low strings and timpani ostinato, horn and trombone melody, snare and toms, "
                 "a defiant major-key turn in the B section",
    "sw-tension": "infiltration and stealth: quiet, suspenseful and mysterious, A minor, about 76 bpm, low "
                  "string tremolo and a soft pizzicato pulse, a sparse celesta and harp hook, clarinet and "
                  "bassoon answers, distant muted trumpet; never loud",
    "sw-jungle": "exploring wild forest and jungle worlds: mysterious, organic and adventurous, D Dorian, about "
                 "96 bpm, flute and English horn melody, harp arpeggios, soft taiko and low tom rhythm, "
                 "wordless choir (voices) swells, a gentle string pad",
    "sw-thrawn": "the theme of a brilliant, cold and cultured enemy grand admiral who studies art to defeat his "
                 "foes: slow, elegant and menacing, B harmonic minor, about 72 bpm, solo English horn or oboe "
                 "melody over dark low strings and a low male-choir pad (choir), celesta glints, soft low "
                 "timpani; grows to full menacing brass in A''",
    "sw-victory": "a short victory fanfare for the end-of-mission screen: about 12 seconds, C major, a bright "
                  "trumpet-and-horn fanfare built from a 4-5 note hook, timpani roll and cymbal on the final "
                  "chord, a held triumphant final chord with harp glissando. Not looped: no A-A'-B-A'' form needed",
    "sw-defeat": "a short defeat cue for the end-of-mission screen: about 12 seconds, A minor, slow, a mournful "
                 "horn line over low strings descending to a dark final chord, soft tam-tam. Not looped: no "
                 "A-A'-B-A'' form needed",
}

METHOD = """Compositional method (follow it):
- Melodic hook: a distinctive 3-7 note motif introduced within the first two bars of the theme, with strong contour and rhythmic identity (mix short notes, held notes, selective syncopation, strategic rests). Call-and-response between phrases. Tension and resolution.
- Phrases of 2, 4 or 8 bars. A recurring 2-4 chord progression gives familiarity; a distinct bass line gives drive.
- Form: an optional 2-4 bar intro, then a 32-bar A (1-8, establish the hook) - A' (9-16, hook again with added instruments or rhythmic variation) - B (17-24, contrasting melody, altered harmony or register) - A'' (25-32, the hook returns, harmonically preparing a return to bar 1, e.g. ending on the dominant or with a pickup). Then play the 32 bars a second time with fuller orchestration and a new countermelody, and close with a short 2-4 bar ending that resolves but could lead back into the opening.
- Repetition with variation: the hook returns changed in rhythm, register, harmony, ornament or instrumentation, never identical three times in a row.
- A countermelody answers the hook between repetitions. Layers enter and leave to build and release; no unnecessary climaxes, no excessive melodic density, keep the melody clearly on top.
- Melody notes should mostly be quarter and eighth notes, with held notes at phrase ends; leave room to breathe.
The best game music is not the most complicated: give it a strong identity the brain learns quickly and enjoys hearing many times."""

API = sc.__doc__ + """
Instruments (name: sound): """ + ", ".join(sorted(sc.INSTRUMENTS)) + """.
'strings' is a sustained string section, 'violins' a faster-attack section (for ostinatos and runs), 'tremolo' tremolo strings, 'pizzicato' plucked strings; 'cellos', 'basses', 'violin_solo' are solo-sampled, use them doubled with sections. 'choir' is choir aahs, 'voices' choir oohs, 'space_pad' and 'space_voice' are soft synth pads (use sparingly for atmosphere). Percussion pitches: """ + ", ".join(sorted(sc.PERCUSSION)) + """ (timpani is its own pitched part).
Ranges: keep each instrument in its natural range (trumpets G3-C6, horns F2-F5, trombones E2-F4, tuba D1-F3, violins G3-C7, cellos C2-A4, basses C1-G2, flute C4-C7, timpani F2... use D2-A3 if pitched lower sounds odd).
Velocity is dynamics (40 soft, 70 medium, 100 loud, 120 fortissimo); part volume sets the section's overall level (0.4-1.0)."""

PROMPT = """Write ONE Python file named {name}.py in the current working directory and nothing else. Do not run anything that needs network access.

It is a music score for a turn-based science-fiction strategy game, written against this API (the file must define compose(s); `s` is a Score; do not import anything except standard-library modules such as math or random with a fixed seed):

{api}

The cue: {brief}.

Orchestral style: {style}.

{method}

Rules:
- Every melody, hook and progression must be your own original invention. Do not quote or closely paraphrase any existing film, television or game theme.
- Write real orchestration: melody doubled in octaves or across sections where a film orchestra would, sustained harmony, a moving bass line, percussion that supports the phrasing, and swells (part.swell) for builds and fades.
- Use helper functions and loops in the file to state the hook, vary it and transpose it, rather than listing thousands of notes by hand. Keep the file under about 400 lines.
- Call s.end(...) with the final beat. Target length: {length}.
{corrections}
After writing the file, reply with only its file name."""


def codex_text(prompt: str, workspace: Path, label: str, model: str = "gpt-6-sol") -> str:
    """Run Codex in a managed workspace for a text/code task; returns its reply."""
    scrub_check(prompt)
    executable = g.ticket_runner.resolve_codex_executable() or ""
    environment = g.ticket_runner.require_codex_chatgpt_quota(executable)
    command = [executable, "exec", "--skip-git-repo-check", "-C", g.codex_art._windows_path(workspace),
               "-m", model, "-c", 'model_reasoning_effort="medium"', "-c", 'web_search="disabled"',
               "--approve-for-me", "--ephemeral", "--color", "never", "-"]
    try:
        done = subprocess.run(command, cwd=workspace, env=environment, input=prompt, text=True,
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                              timeout=g.codex_art.CODEX_TIMEOUT_SECONDS, check=False)
        output = done.stdout or ""
    except subprocess.TimeoutExpired:
        output = ""
    (workspace / f"codex-output-{label}.txt").write_text(output, encoding="utf-8")
    return output


def length_for(name: str) -> str:
    return "about 12 seconds" if name in ("sw-victory", "sw-defeat") else "about 140-200 seconds"


# Mastering loudness (RMS before limiting): quiet cues stay quiet.
LOUDNESS = {"sw-tension": 0.07, "sw-thrawn": 0.09, "sw-jungle": 0.095}


def validate_and_render(path: Path, out: Path) -> str | None:
    try:
        score = sc.load(path)
        problems = sc.check(score)
        if problems:
            return "; ".join(problems)
        audio = sc.render(score, target_rms=LOUDNESS.get(out.stem, 0.11))
        sc.write_ogg(out, audio)
        return None
    except Exception:  # report the composer's error back to it
        return traceback.format_exc(limit=3)[-900:]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--only", action="append")
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--attempts", type=int, default=3)
    parser.add_argument("--render-only", action="store_true")
    args = parser.parse_args()
    SCORES.mkdir(parents=True, exist_ok=True)
    args.out.mkdir(parents=True, exist_ok=True)
    failed = 0
    for name, brief in TRACKS.items():
        if args.only and name not in args.only:
            continue
        dest = SCORES / f"{name.replace('-', '_')}.py"
        if args.render_only:
            problem = validate_and_render(dest, args.out / f"{name}.ogg")
            print(f"{name}: {'rendered' if not problem else 'FAILED ' + problem}", flush=True)
            failed += bool(problem)
            continue
        workspace = g.codex_art._managed_directory(f"music-{name}")
        corrections, problem = "", "not attempted"
        for attempt in range(1, args.attempts + 1):
            fname = name.replace("-", "_")
            prompt = PROMPT.format(name=fname, api=API, brief=brief, style=STYLE, method=METHOD,
                                   length=length_for(name), corrections=corrections)
            started = time.time()
            codex_text(prompt, workspace, f"{fname}-{attempt}")
            written = workspace / f"{fname}.py"
            if not written.exists():
                problem = "Codex wrote no file"
                continue
            shutil.copyfile(written, dest)
            problem = validate_and_render(dest, args.out / f"{name}.ogg")
            print(f"{name} attempt {attempt}: {'ok' if not problem else problem.splitlines()[-1]} "
                  f"({time.time() - started:.0f}s)", flush=True)
            if not problem:
                break
            corrections = (f"- Correction: the previous version of {fname}.py (in this directory) failed: {problem}. "
                           "Fix it and write the complete file again.\n")
        failed += bool(problem)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
