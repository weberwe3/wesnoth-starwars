#!/usr/bin/env python3

"""Deterministic, no-API art-production contracts for add-on unit sprites.

The local ticket runner cannot invoke ChatGPT's interactive image-generation
tool.  Instead this module maintains exact original-art requirements and
Codex-ready ``$imagegen`` briefs.  A Codex art task uses the owner's normal
Codex allowance to generate the files, then a normal governed ticket imports
and validates them.  No API key, provider credential, or external artwork is
used or stored here.
"""

from __future__ import annotations

import json
from pathlib import Path
import re
import tempfile
from typing import Any

from gameplay_contracts import ADDON_ROOT, _config_files


ART_MANIFEST = "assets/art-queue.json"
ART_PROMPT_DIRECTORY = "assets/prompts"
ART_SCHEMA_VERSION = 1
MAX_ART_JOBS = 100
MAX_PUBLIC_BRIEF_CHARS = 6_000
VALID_ART_STATES = {
    "pending_codex_imagegen", "generating", "ready_for_import", "complete", "failed",
}


def _safe_slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")[:80]


def _unit_definitions(sources: dict[str, str]) -> list[dict[str, str]]:
    """Extract the small unit identity needed to generate stable art contracts."""

    units: list[dict[str, str]] = []
    for path, text in sorted(sources.items()):
        if not path.startswith(ADDON_ROOT + "/units/"):
            continue
        for block_match in re.finditer(r"(?s)\[unit_type\](.*?)\[/unit_type\]", text):
            block = block_match.group(1)
            unit_id = re.search(r"(?m)^\s*id\s*=\s*([A-Za-z0-9_]+)\s*$", block)
            name = re.search(r"(?m)^\s*name\s*=\s*_?\"([^\"]+)\"\s*$", block)
            description = re.search(r"(?m)^\s*description\s*=\s*_?\"([^\"]+)\"\s*$", block)
            if not unit_id:
                continue
            units.append({
                "id": unit_id.group(1),
                "name": name.group(1) if name else unit_id.group(1).replace("_", " "),
                "description": description.group(1) if description else "An original tactical unit.",
                "source_path": path,
            })
    return units


def _unit_assets(unit_id: str) -> list[dict[str, str]]:
    """Return every importable visual state required for a custom unit."""

    slug = _safe_slug(unit_id)
    unit_root = f"images/units/{slug}"
    states = (
        ("standing", f"{unit_root}/standing.png", "Base standing sprite"),
        ("idle-1", f"{unit_root}/idle-1.png", "Idle animation frame one"),
        ("idle-2", f"{unit_root}/idle-2.png", "Idle animation frame two"),
        ("move-1", f"{unit_root}/move-1.png", "Movement animation frame one"),
        ("move-2", f"{unit_root}/move-2.png", "Movement animation frame two"),
        ("melee-1", f"{unit_root}/melee-1.png", "Melee attack wind-up frame"),
        ("melee-2", f"{unit_root}/melee-2.png", "Melee attack follow-through frame"),
        ("ranged-1", f"{unit_root}/ranged-1.png", "Ranged attack aiming frame"),
        ("ranged-2", f"{unit_root}/ranged-2.png", "Ranged attack firing frame"),
        ("defend", f"{unit_root}/defend.png", "Defend or hit-reaction sprite"),
        ("death-1", f"{unit_root}/death-1.png", "Death animation frame one"),
        ("death-2", f"{unit_root}/death-2.png", "Death animation frame two"),
        ("portrait", f"images/portraits/{slug}.png", "Unit profile portrait"),
    )
    return [{"state": state, "path": path, "purpose": purpose} for state, path, purpose in states]


def _brief(unit: dict[str, str], assets: list[dict[str, str]]) -> str:
    """Build a copy-ready, state-complete prompt for an interactive Codex task."""

    unit_name = unit["name"][:160]
    description = re.sub(r"\s+", " ", unit["description"]).strip()[:500]
    asset_lines = "\n".join(
        f"- `{asset['path']}` — {asset['purpose']}." for asset in assets
    )
    return f"""# Original art brief — {unit_name}

Paste one state request at a time into a Codex interactive task with `$imagegen`.
The generated PNGs belong in the exact project paths below.

```text
$imagegen

Use case: stylized-concept
Asset type: Battle for Wesnoth tactical unit sprite set
Primary request: Create one original, unnamed {unit_name} for a post-Return of the Jedi Legends-inspired campaign. The unit is described in this project's original WML as: {description}
Style/medium: hand-painted tactical strategy-game sprite; strong readable silhouette at 72×72 pixels; transparent background; use a consistent original wardrobe, palette, and equipment design across every state.
Composition/framing: three-quarter full-body tactical pose; preserve the same character identity, proportions, clothing, and equipment in every frame; alter only the motion or pose specified for the requested state.
Constraints: fully original artwork. Do not reproduce or closely imitate book-cover art, comics, film stills, actors, logos, named-character likenesses, official game art, or public reference-image composition. No text and no watermark.
```

## Required output set

{asset_lines}

Generate each listed state as a separate transparent PNG. Do not mark this job
complete until every listed file is imported and the unit WML references the
standing, idle, move, melee, ranged, defend, death, and portrait assets.
"""


def _redact_sensitive_text(value: str) -> str:
    """Keep a malformed unit description from disclosing a secret to the UI."""

    return re.sub(
        r"(?im)\b(?:api[_ -]?key|token|secret|password)\s*[:=]\s*[^\s`]+",
        "[redacted]",
        value,
    )


def _atomic_write(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", delete=False, dir=path.parent, prefix=f".{path.name}.", suffix=".tmp"
    ) as temporary:
        temporary.write(payload)
        temporary_path = Path(temporary.name)
    temporary_path.replace(path)


def _load_manifest(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def unit_ids_for_source_paths(root: Path, paths: list[str]) -> set[str]:
    """Return units declared by candidate-changed unit source files."""

    changed = set(paths)
    return {
        unit["id"] for unit in _unit_definitions(_config_files(root))
        if unit["source_path"] in changed
    }


def synchronize_art_queue(root: Path, unit_ids: set[str] | None = None) -> dict[str, Any]:
    """Create/update exact state contracts for requested units without an API.

    Existing jobs remain intact. A normal implementation run supplies only the
    unit IDs it changed, avoiding an accidental project-wide image batch.
    """

    sources = _config_files(root)
    units = _unit_definitions(sources)
    manifest_path = root / ADDON_ROOT / ART_MANIFEST
    existing = _load_manifest(manifest_path)
    prior_jobs = {
        item.get("unit_id"): item
        for item in existing.get("jobs", []) if isinstance(item, dict) and isinstance(item.get("unit_id"), str)
    }
    requested = set(unit_ids or ())
    jobs: list[dict[str, Any]] = []
    prompts: list[str] = []
    for unit in units:
        if unit["id"] not in requested and unit["id"] not in prior_jobs:
            continue
        previous = prior_jobs.get(unit["id"], {})
        state = previous.get("state") if isinstance(previous.get("state"), str) else "pending_codex_imagegen"
        if state not in VALID_ART_STATES:
            state = "pending_codex_imagegen"
        assets = _unit_assets(unit["id"])
        slug = _safe_slug(unit["id"])
        prompt_path = f"{ART_PROMPT_DIRECTORY}/{slug}.md"
        job = {
            "id": f"art-{slug}",
            "unit_id": unit["id"],
            "unit_name": unit["name"],
            "source_path": unit["source_path"],
            "state": state,
            "generation": "codex_quota_interactive_only",
            "prompt_path": prompt_path,
            "assets": assets,
        }
        jobs.append(job)
        prompt_file = root / ADDON_ROOT / prompt_path
        _atomic_write(prompt_file, _brief(unit, assets))
        prompts.append(prompt_file.relative_to(root).as_posix())
    if len(jobs) > MAX_ART_JOBS:
        return {
            "pass": False, "manifest_path": manifest_path.relative_to(root).as_posix(),
            "jobs": [], "prompt_paths": [], "generated_paths": [], "created_or_updated": 0,
        }
    manifest = {
        "schema_version": ART_SCHEMA_VERSION,
        "policy": "codex_quota_interactive_only",
        "summary": "Use an interactive Codex $imagegen task; no API key is permitted.",
        "jobs": jobs,
    }
    _atomic_write(manifest_path, json.dumps(manifest, indent=2) + "\n")
    return {
        "pass": len(units) <= MAX_ART_JOBS,
        "manifest_path": manifest_path.relative_to(root).as_posix(),
        "jobs": jobs,
        "prompt_paths": prompts,
        "generated_paths": [manifest_path.relative_to(root).as_posix(), *prompts],
        "created_or_updated": len(requested),
    }


def validate_art_queue(root: Path) -> dict[str, Any]:
    """Validate completed jobs strictly while allowing pending Codex art work."""

    manifest_path = root / ADDON_ROOT / ART_MANIFEST
    manifest = _load_manifest(manifest_path)
    failures: list[dict[str, str]] = []
    jobs = manifest.get("jobs") if isinstance(manifest, dict) else None
    if manifest.get("schema_version") != ART_SCHEMA_VERSION or not isinstance(jobs, list):
        return {"pass": False, "diagnostic": "Art queue manifest is missing or invalid", "jobs": [], "pending": 0}
    if len(jobs) > MAX_ART_JOBS:
        return {
            "pass": False,
            "diagnostic": f"Art queue exceeds the {MAX_ART_JOBS}-job safety limit",
            "diagnostic_paths": [ART_MANIFEST],
            "jobs": [],
            "pending": 0,
            "complete": 0,
        }
    sources = _config_files(root)
    live_units = {item["id"]: item for item in _unit_definitions(sources)}
    seen: set[str] = set()
    public_jobs: list[dict[str, Any]] = []
    pending = 0
    for job in jobs[:MAX_ART_JOBS]:
        if not isinstance(job, dict):
            failures.append({"path": ART_MANIFEST, "detail": "Art queue contains an invalid job"})
            continue
        unit_id = job.get("unit_id")
        state = job.get("state")
        assets = job.get("assets")
        if not isinstance(unit_id, str) or unit_id not in live_units or unit_id in seen:
            failures.append({"path": ART_MANIFEST, "detail": "Art queue contains an unknown or duplicate unit"})
            continue
        seen.add(unit_id)
        expected = _unit_assets(unit_id)
        if state not in VALID_ART_STATES or assets != expected:
            failures.append({"path": ART_MANIFEST, "detail": f"Art job {unit_id} lacks the complete required state set"})
            continue
        if state != "complete":
            pending += 1
        else:
            source = sources[live_units[unit_id]["source_path"]]
            for asset in expected:
                relative = asset["path"]
                image = root / ADDON_ROOT / relative
                if image.is_symlink() or not image.is_file() or image.read_bytes()[:8] != b"\x89PNG\r\n\x1a\n":
                    failures.append({"path": live_units[unit_id]["source_path"], "detail": f"Completed art job {unit_id} is missing valid PNG {relative}"})
                elif f"~add-ons/Star_Wars_Thrawn_Trilogy/{relative}" not in source:
                    failures.append({"path": live_units[unit_id]["source_path"], "detail": f"Completed art job {unit_id} is not fully wired into unit WML: {relative}"})
        public_jobs.append({
            "id": job.get("id"), "unit_id": unit_id, "unit_name": job.get("unit_name"),
            "state": state, "prompt_path": job.get("prompt_path"), "asset_count": len(expected),
        })
    return {
        "pass": not failures,
        "diagnostic": "\n".join(item["detail"] for item in failures)[:6000],
        "diagnostic_paths": sorted({item["path"] for item in failures})[:20],
        "jobs": public_jobs,
        "pending": pending,
        "complete": sum(1 for item in public_jobs if item["state"] == "complete"),
    }


def public_art_queue(root: Path) -> dict[str, Any]:
    """Return bounded, credential-free Codex art handoffs for the dashboard."""

    evidence = validate_art_queue(root)
    units = {unit["id"]: unit for unit in _unit_definitions(_config_files(root))}
    jobs: list[dict[str, Any]] = []
    for job in evidence["jobs"][:10]:
        public_job = dict(job)
        unit = units.get(public_job.get("unit_id"))
        if unit:
            public_job["brief"] = _redact_sensitive_text(
                _brief(unit, _unit_assets(unit["id"]))
            )[:MAX_PUBLIC_BRIEF_CHARS]
        jobs.append(public_job)
    return {
        "pass": evidence["pass"],
        "diagnostic": evidence["diagnostic"],
        "pending": evidence["pending"],
        "complete": evidence["complete"],
        "jobs": jobs,
        "policy": "Codex quota interactive art generation; no API key",
    }
