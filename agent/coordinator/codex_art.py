#!/usr/bin/env python3
"""Generate original unit art with the signed-in Codex CLI, then derive frames.

One art job (one unit) becomes exactly two Codex image generations: a master
full-body design and a portrait. All 12 animation frames are derived from the
master by ``production/tools/derive_unit_frames.py`` so outfit and equipment
stay identical across the set (owner rule, 2026-10-02).

Authentication and billing follow the project's existing Codex boundary
(``ticket_runner.require_codex_chatgpt_quota``): ChatGPT-account Codex only,
API keys stripped, no credential is read, printed, or stored. Codex writes into
a managed Windows-native directory under the existing worktree root.

When the image service refuses a design (for example a likeness it will not
draw), the job keeps its code-drawn art from
``production/tools/gen_coded_unit_art.py`` and is reported as
``coded_fallback``; nothing is fabricated or retried in a loop.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import time
from pathlib import Path
from typing import Any, Callable

import ticket_runner
from gameplay_contracts import ADDON_ROOT

ART_DIRECTION = "production/assets/art_direction.json"
DERIVE_TOOL = "production/tools/derive_unit_frames.py"
CODED_TOOL = "production/tools/gen_coded_unit_art.py"
# Refused heroes with a detailed painted master; others use the simpler coded set.
PAINT_TOOL = "production/tools/paint_hero_masters.py"
PORTRAIT_TOOL = "production/tools/fit_portrait.py"
PAINTED_HEROES = frozenset({"sw_hero_luke", "sw_hero_chewbacca"})
ART_PYTHON_DEFAULT = Path.home() / "opt" / "swtools" / "bin" / "python"
MANAGED_ART_ROOT = "art-gen"
CODEX_TIMEOUT_SECONDS = 1500
MODERATION = re.compile(r"moderation_blocked|rejected by the safety system", re.IGNORECASE)
QUOTA = re.compile(r"usage limit|rate limit|quota|too many requests|429", re.IGNORECASE)
JOB_ID = re.compile(r"art-[a-z0-9-]{1,100}")


# Images already taken by this process, so an image can never be reused for
# a second job even if its timestamp falls in a later window.
_HARVESTED: set[str] = set()


def harvest_generated(codex_home: Path | None, started: float, finished: float) -> list[Path]:
    """Images Codex generated during one run, oldest first.

    Codex keeps every generated image under ``CODEX_HOME/generated_images/<session>/``
    but does not always copy it into the working directory. Only folders and
    files created inside this run's time window are used, so another session's
    images are never picked up (art generation runs one job at a time).
    """
    if codex_home is None:
        return []
    root = codex_home / "generated_images"
    found: list[tuple[float, Path]] = []
    try:
        sessions = [entry for entry in root.iterdir() if entry.is_dir() and not entry.is_symlink()]
    except OSError:
        return []
    for session in sessions:
        try:
            if session.stat().st_mtime < started - 1:
                continue
            for image in session.glob("*.png"):
                modified = image.stat().st_mtime
                # Inside this call's window (one second of tolerance for coarse
                # file timestamps). Images already taken are never reused, so a
                # previous job's late image cannot be picked up again.
                if started - 1 < modified <= finished + 5 and not image.is_symlink() \
                        and str(image) not in _HARVESTED:
                    found.append((modified, image))
        except OSError:
            continue
    return [path for _, path in sorted(found)]


class CodexArtError(RuntimeError):
    """Raised for an art-generation infrastructure problem (not a refusal)."""


def art_python() -> Path:
    configured = os.environ.get("WESNOTH_ART_PYTHON")
    path = Path(configured) if configured else ART_PYTHON_DEFAULT
    if not path.is_file():
        raise CodexArtError("Image-processing Python (with Pillow) is not available")
    return path


def load_direction(root: Path) -> dict[str, Any]:
    data = json.loads((root / ART_DIRECTION).read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("units"), dict):
        raise CodexArtError("Art direction record is invalid")
    return data


def build_prompt(direction: dict[str, Any], unit_id: str, unit_name: str, kind: str) -> str:
    """Prompt for ONE image. ``kind`` is ``sprite`` or ``portrait``.

    One image per Codex call: earlier two-image prompts sometimes produced a
    single composite picture, and Codex does not always copy its output into
    the working directory, so each call must be unambiguous on its own.
    """
    subject = direction["units"].get(unit_id)
    if kind == "portrait":
        # A pilot hero's unit is a starfighter, but the pilot speaks in dialogue.
        subject = (direction.get("portrait_subjects") or {}).get(unit_id, subject)
    if not isinstance(subject, str) or not subject.strip():
        raise CodexArtError(f"No art direction for {unit_id}")
    rules = "\n".join(f"- {rule}" for rule in direction.get("rules", []))
    if kind == "sprite":
        framing = ("a full-body game unit for a turn-based tactics game, seen in three-quarter view facing "
                   "right in a ready stance, the whole subject centered with an empty margin")
    else:
        framing = ("a head-and-shoulders portrait of the character for dialogue scenes, the face and upper body "
                   "filling the frame (for a vehicle or ship, a dramatic close three-quarter view of the craft)")
    return f"""Use your image generation tool to create exactly ONE original image: {framing}, on a TRANSPARENT background. Show a single subject only; do not combine several views in one image. Save it as {kind}.png in the current working directory. Do not create any other files.

Subject ({unit_name}): {subject}

Style: {direction.get("style", "")}

Rules:
{rules}

After saving, reply with only the file name."""


def _managed_directory(slug: str) -> Path:
    executable = ticket_runner.resolve_codex_executable()
    if not executable:
        raise CodexArtError("Codex CLI is not installed")
    home = Path.home().name
    if not re.fullmatch(r"[A-Za-z0-9._-]+", home):
        raise CodexArtError("Unsupported user profile name")
    base = Path("/mnt/c/Users") / home / "Documents/Codex/WesnothAgentWorktrees" / MANAGED_ART_ROOT
    stamp = time.strftime("%Y%m%d-%H%M%S")
    directory = base / f"{slug}-{stamp}"
    directory.mkdir(parents=True, exist_ok=False)
    return directory


def _windows_path(path: Path) -> str:
    completed = subprocess.run(["wslpath", "-w", str(path)], text=True, capture_output=True, timeout=10, check=False)
    if completed.returncode or not completed.stdout.strip():
        raise CodexArtError("Could not translate the art workspace path")
    return completed.stdout.strip()


def _valid_png(path: Path) -> bool:
    """A complete PNG: signature, plausible size, and the IEND trailer.

    A file Codex is still writing has the signature but no trailer yet.
    """
    try:
        if path.stat().st_size <= 2_000:
            return False
        with path.open("rb") as stream:
            head = stream.read(8)
            stream.seek(-12, 2)
            tail = stream.read(12)
        return head == b"\x89PNG\r\n\x1a\n" and tail[4:8] == b"IEND"
    except OSError:
        return False


def _codex_image(executable: str, environment: dict[str, str], workspace: Path, prompt: str, target: Path,
                 runner: Callable[..., subprocess.CompletedProcess], model: str) -> tuple[bool, str]:
    """Run one Codex image generation; return (image saved, transcript)."""
    command = [
        executable, "exec", "--skip-git-repo-check", "-C", _windows_path(workspace),
        "-m", model, "-c", 'model_reasoning_effort="low"', "-c", 'web_search="disabled"',
        "--approve-for-me", "--ephemeral", "--color", "never", "-",
    ]
    started = time.time()
    try:
        completed = runner(command, cwd=workspace, env=environment, input=prompt, text=True,
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                           timeout=CODEX_TIMEOUT_SECONDS, check=False)
        output = completed.stdout or ""
    except subprocess.TimeoutExpired:
        output = ""
    if not _valid_png(target):
        codex_home = Path(environment["CODEX_HOME"]) if environment.get("CODEX_HOME") else None
        deadline = time.time() + 20
        made: list[Path] = []
        while time.time() < deadline:
            made = [path for path in harvest_generated(codex_home, started, time.time()) if _valid_png(path)]
            if made:
                break
            time.sleep(2)
        if made:
            _HARVESTED.add(str(made[-1]))
            target.write_bytes(made[-1].read_bytes())
    return _valid_png(target), output


def generate_unit_art(
    root: Path, job: dict[str, Any], *,
    runner: Callable[..., subprocess.CompletedProcess] = subprocess.run,
    model: str = "gpt-6-luna",
) -> dict[str, Any]:
    """Generate one unit's art set into ``root``'s add-on image tree.

    Returns ``{"state": "generated" | "coded_fallback" | "failed" | "quota_paused", ...}``.
    """
    job_id, unit_id = job.get("id"), job.get("unit_id")
    if not isinstance(job_id, str) or not JOB_ID.fullmatch(job_id) or not isinstance(unit_id, str):
        raise CodexArtError("Invalid art job")
    slug = job_id.removeprefix("art-")
    direction = load_direction(root)
    name = str(job.get("unit_name") or unit_id)
    executable = ticket_runner.resolve_codex_executable()
    environment = ticket_runner.require_codex_chatgpt_quota(executable or "")
    workspace = _managed_directory(slug)
    sprite, portrait = workspace / "sprite.png", workspace / "portrait.png"
    started = time.time()
    result: dict[str, Any] = {"job_id": job_id, "unit_id": unit_id, "workspace": workspace.name}
    transcripts: list[str] = []
    ok, output = _codex_image(executable or "", environment, workspace, build_prompt(direction, unit_id, name, "sprite"),
                              sprite, runner, model)
    transcripts.append(output)
    sprite_only = unit_id in direction.get("portrait_from_sprite", []) or unit_id in direction.get("sprite_only", [])
    if ok and not sprite_only:
        _, output = _codex_image(executable or "", environment, workspace,
                                 build_prompt(direction, unit_id, name, "portrait"), portrait, runner, model)
        transcripts.append(output)
    transcript = "\n".join(transcripts)
    (workspace / "codex-output.txt").write_text(transcript[-20000:], encoding="utf-8")
    result["seconds"] = round(time.time() - started)
    if not _valid_png(sprite):
        if QUOTA.search(transcript) and not MODERATION.search(transcript):
            result.update(state="quota_paused", reason="Codex usage limit reached; art generation paused")
            return result
        refused = bool(MODERATION.search(transcript))
        if refused and unit_id in PAINTED_HEROES:
            _run_tool(root, PAINT_TOOL, "--out", str(workspace), "--unit", unit_id)
            _run_tool(root, DERIVE_TOOL, "--sprite", str(workspace / f"{slug}-master.png"),
                      "--portrait", str(workspace / f"{slug}-portrait.png"),
                      "--addon", str(root / ADDON_ROOT), "--slug", slug)
        else:
            _run_tool(root, CODED_TOOL, "--only", unit_id)
        result.update(state="coded_fallback" if refused else "failed",
                      reason="image service refused the design" if refused else "Codex did not produce an image")
        return result
    if not _valid_png(portrait):
        # Film-portrayed characters (no actor likeness), vehicles, or a refused
        # portrait: frame the portrait from the sprite so the set is complete.
        portrait.write_bytes(sprite.read_bytes())
    derived = _run_tool(root, DERIVE_TOOL, "--sprite", str(sprite), "--portrait", str(portrait),
                        "--addon", str(root / ADDON_ROOT), "--slug", slug)
    result.update(state="generated", written=len(json.loads(derived).get("written", [])))
    return result


def generate_portrait(
    root: Path, unit_id: str, unit_name: str, *,
    runner: Callable[..., subprocess.CompletedProcess] = subprocess.run,
    model: str = "gpt-6-luna",
) -> dict[str, Any]:
    """Generate only the dialogue portrait for one unit, keeping its sprites.

    Returns ``{"state": "generated" | "refused" | "failed" | "quota_paused", ...}``.
    """
    slug = re.sub(r"[^a-z0-9]+", "-", unit_id.casefold()).strip("-")
    if not JOB_ID.fullmatch(f"art-{slug}"):
        raise CodexArtError("Invalid portrait unit")
    direction = load_direction(root)
    executable = ticket_runner.resolve_codex_executable()
    environment = ticket_runner.require_codex_chatgpt_quota(executable or "")
    workspace = _managed_directory(f"{slug}-portrait")
    portrait = workspace / "portrait.png"
    ok, output = _codex_image(executable or "", environment, workspace,
                              build_prompt(direction, unit_id, unit_name, "portrait"), portrait, runner, model)
    (workspace / "codex-output.txt").write_text(output[-20000:], encoding="utf-8")
    result: dict[str, Any] = {"unit_id": unit_id, "workspace": workspace.name}
    if not ok:
        if QUOTA.search(output) and not MODERATION.search(output):
            return {**result, "state": "quota_paused", "reason": "Codex usage limit reached"}
        refused = bool(MODERATION.search(output))
        return {**result, "state": "refused" if refused else "failed",
                "reason": "image service refused the design" if refused else "Codex did not produce an image"}
    _run_tool(root, PORTRAIT_TOOL, "--portrait", str(portrait), "--addon", str(root / ADDON_ROOT), "--slug", slug)
    return {**result, "state": "generated"}


def _run_tool(root: Path, tool: str, *arguments: str) -> str:
    completed = subprocess.run([str(art_python()), str(root / tool), *arguments], cwd=root, text=True,
                               capture_output=True, timeout=300, check=False)
    if completed.returncode:
        raise CodexArtError(f"{Path(tool).name} failed: {(completed.stderr or completed.stdout)[-300:]}")
    return completed.stdout.strip().splitlines()[-1] if completed.stdout.strip() else "{}"
