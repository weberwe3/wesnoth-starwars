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
ART_PYTHON_DEFAULT = Path.home() / "opt" / "swtools" / "bin" / "python"
MANAGED_ART_ROOT = "art-gen"
CODEX_TIMEOUT_SECONDS = 1500
MODERATION = re.compile(r"moderation_blocked|rejected by the safety system", re.IGNORECASE)
QUOTA = re.compile(r"usage limit|rate limit|quota|too many requests|429", re.IGNORECASE)
JOB_ID = re.compile(r"art-[a-z0-9-]{1,100}")


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


def build_prompt(direction: dict[str, Any], unit_id: str, unit_name: str) -> str:
    subject = direction["units"].get(unit_id)
    if not isinstance(subject, str) or not subject.strip():
        raise CodexArtError(f"No art direction for {unit_id}")
    rules = "\n".join(f"- {rule}" for rule in direction.get("rules", []))
    return f"""Use your image generation tool to create exactly TWO original images and save them in the current working directory. Do not create any other files and do not run other commands.

1. sprite.png: a full-body game unit for a turn-based tactics game, seen in three-quarter view facing right, standing in a ready stance. The whole subject is centered with an empty margin, on a TRANSPARENT background.
2. portrait.png: a head-and-shoulders portrait of the same character (for vehicles and ships, a dramatic close three-quarter view of the same craft), TRANSPARENT background.

Subject ({unit_name}): {subject}

Style: {direction.get("style", "")}

Rules:
{rules}

The sprite and portrait must show the same design with identical clothing, colors, and equipment.
After saving both files, reply with only the two file names."""


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
    try:
        with path.open("rb") as stream:
            return stream.read(8) == b"\x89PNG\r\n\x1a\n" and path.stat().st_size > 2_000
    except OSError:
        return False


def generate_unit_art(
    root: Path, job: dict[str, Any], *,
    runner: Callable[..., subprocess.CompletedProcess] = subprocess.run,
    model: str = "gpt-6-luna",
) -> dict[str, Any]:
    """Generate one unit's art set into ``root``'s add-on image tree.

    Returns ``{"state": "generated" | "coded_fallback" | "failed", ...}``.
    """
    job_id, unit_id = job.get("id"), job.get("unit_id")
    if not isinstance(job_id, str) or not JOB_ID.fullmatch(job_id) or not isinstance(unit_id, str):
        raise CodexArtError("Invalid art job")
    slug = job_id.removeprefix("art-")
    direction = load_direction(root)
    prompt = build_prompt(direction, unit_id, str(job.get("unit_name") or unit_id))
    executable = ticket_runner.resolve_codex_executable()
    environment = ticket_runner.require_codex_chatgpt_quota(executable or "")
    workspace = _managed_directory(slug)
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
    sprite, portrait = workspace / "sprite.png", workspace / "portrait.png"
    result: dict[str, Any] = {"job_id": job_id, "unit_id": unit_id, "seconds": round(time.time() - started),
                              "workspace": workspace.name}
    if not (_valid_png(sprite) and _valid_png(portrait)):
        if QUOTA.search(output) and not MODERATION.search(output):
            result.update(state="quota_paused", reason="Codex usage limit reached; art generation paused")
            return result
        refused = bool(MODERATION.search(output))
        _run_tool(root, CODED_TOOL, "--only", unit_id)
        result.update(state="coded_fallback" if refused else "failed",
                      reason="image service refused the design" if refused else "Codex did not produce both images")
        return result
    derived = _run_tool(root, DERIVE_TOOL, "--sprite", str(sprite), "--portrait", str(portrait),
                        "--addon", str(root / ADDON_ROOT), "--slug", slug)
    result.update(state="generated", written=len(json.loads(derived).get("written", [])))
    return result


def _run_tool(root: Path, tool: str, *arguments: str) -> str:
    completed = subprocess.run([str(art_python()), str(root / tool), *arguments], cwd=root, text=True,
                               capture_output=True, timeout=300, check=False)
    if completed.returncode:
        raise CodexArtError(f"{Path(tool).name} failed: {(completed.stderr or completed.stdout)[-300:]}")
    return completed.stdout.strip().splitlines()[-1] if completed.stdout.strip() else "{}"
