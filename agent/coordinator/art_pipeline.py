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
import struct
import tempfile
from typing import Any
import zlib

from gameplay_contracts import ADDON_ROOT, _config_files


ART_MANIFEST = "assets/art-queue.json"
ART_PROMPT_DIRECTORY = "assets/prompts"
ART_SCHEMA_VERSION = 1
MAX_ART_JOBS = 100
MAX_PUBLIC_BRIEF_CHARS = 6_000
VALID_ART_STATES = {
    "pending_codex_imagegen", "generating", "ready_for_import", "complete", "failed",
}
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
UNIT_SPRITE_DIMENSIONS = (72, 72)
PORTRAIT_DIMENSIONS = (256, 256)


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


def _expected_dimensions(asset: dict[str, str]) -> tuple[int, int]:
    """Return the import dimensions defined by the art-production contract."""

    return PORTRAIT_DIMENSIONS if asset["state"] == "portrait" else UNIT_SPRITE_DIMENSIONS


def _png_diagnostic(path: Path, expected_dimensions: tuple[int, int]) -> str | None:
    """Verify a complete, alpha-capable PNG without loading untrusted image code."""

    if path.is_symlink() or not path.is_file():
        return "is missing"
    try:
        payload = path.read_bytes()
    except OSError:
        return "could not be read"
    if not payload.startswith(PNG_SIGNATURE):
        return "is not a PNG"

    offset = len(PNG_SIGNATURE)
    ihdr: bytes | None = None
    has_idat = False
    saw_iend = False
    while offset < len(payload):
        if offset + 12 > len(payload):
            return "has a truncated PNG chunk"
        length = struct.unpack(">I", payload[offset:offset + 4])[0]
        chunk_type = payload[offset + 4:offset + 8]
        end = offset + 12 + length
        if end > len(payload):
            return "has a truncated PNG chunk"
        chunk_data = payload[offset + 8:offset + 8 + length]
        expected_crc = struct.unpack(">I", payload[offset + 8 + length:end])[0]
        actual_crc = zlib.crc32(chunk_type + chunk_data) & 0xFFFFFFFF
        if actual_crc != expected_crc:
            return "has an invalid PNG checksum"
        if chunk_type == b"IHDR":
            if ihdr is not None or length != 13 or offset != len(PNG_SIGNATURE):
                return "has an invalid PNG header"
            ihdr = chunk_data
        elif chunk_type == b"IDAT":
            has_idat = True
        elif chunk_type == b"IEND":
            if length != 0 or end != len(payload):
                return "has an invalid PNG trailer"
            saw_iend = True
            break
        offset = end

    if ihdr is None or not has_idat or not saw_iend:
        return "is an incomplete PNG"
    width, height, bit_depth, color_type, compression, filter_method, _interlace = struct.unpack(
        ">IIBBBBB", ihdr
    )
    if (width, height) != expected_dimensions:
        return (
            f"has dimensions {width}×{height}; expected "
            f"{expected_dimensions[0]}×{expected_dimensions[1]}"
        )
    if bit_depth != 8 or color_type not in {4, 6} or compression != 0 or filter_method != 0:
        return "is not an 8-bit alpha-capable PNG"
    return None


def _completion_failures(
    root: Path,
    source_path: str,
    source: str,
    expected: list[dict[str, str]],
) -> list[dict[str, str]]:
    """Return bounded deterministic failures for one complete art state set."""

    failures: list[dict[str, str]] = []
    for asset in expected:
        relative = asset["path"]
        image = root / ADDON_ROOT / relative
        png_problem = _png_diagnostic(image, _expected_dimensions(asset))
        if png_problem:
            failures.append({
                "path": source_path,
                "detail": f"Completed art job is missing valid PNG {relative}: {png_problem}",
            })
        if not re.search(
            rf'(?m)^\s*(?:image|icon|profile)\s*=\s*"?{re.escape(relative)}',
            source,
        ):
            failures.append({
                "path": source_path,
                "detail": f"Completed art job is not fully wired into unit WML: {relative}",
            })
    return failures


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
            failures.extend(_completion_failures(
                root, live_units[unit_id]["source_path"], source, expected,
            ))
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


def art_import_contract(root: Path, job_id: str) -> dict[str, Any]:
    """Return one current art contract after rejecting stale or ambiguous jobs."""

    manifest_path = root / ADDON_ROOT / ART_MANIFEST
    manifest = _load_manifest(manifest_path)
    jobs = manifest.get("jobs") if isinstance(manifest, dict) else None
    if manifest.get("schema_version") != ART_SCHEMA_VERSION or not isinstance(jobs, list):
        return {"pass": False, "message": "Art queue manifest is missing or invalid"}
    matches = [job for job in jobs if isinstance(job, dict) and job.get("id") == job_id]
    if len(matches) != 1:
        return {"pass": False, "message": "Art job is not uniquely present in the queue"}
    job = matches[0]
    unit_id = job.get("unit_id")
    sources = _config_files(root)
    units = {unit["id"]: unit for unit in _unit_definitions(sources)}
    if not isinstance(unit_id, str) or unit_id not in units or job.get("assets") != _unit_assets(unit_id):
        return {"pass": False, "message": "Art job contract does not match a current custom unit"}
    return {
        "pass": True,
        "job": job,
        "unit_id": unit_id,
        "unit_name": units[unit_id]["name"],
        "source_path": units[unit_id]["source_path"],
        "source": sources[units[unit_id]["source_path"]],
        "assets": _unit_assets(unit_id),
    }


def art_import_preflight(root: Path, job_id: str) -> dict[str, Any]:
    """Verify a user-imported art set without changing its queue state."""

    contract = art_import_contract(root, job_id)
    if not contract["pass"]:
        return {**contract, "requires_llm": False}
    job = contract["job"]
    unit_id = contract["unit_id"]
    source_path = contract["source_path"]
    failures = _completion_failures(root, source_path, contract["source"], contract["assets"])
    if failures:
        detail = " ".join(item["detail"] for item in failures[:3])
        needs_wiring = any("not fully wired" in item["detail"] for item in failures)
        return {
            "pass": False,
            "message": detail[:1200],
            "requires_llm": needs_wiring,
            "state": job.get("state"),
        }
    return {
        "pass": True,
        "message": "All 13 original art files are valid, correctly sized, alpha-capable, and wired into unit WML. No LLM follow-up is needed.",
        "requires_llm": False,
        "state": job.get("state"),
    }


def art_import_batch_contract(root: Path, job_id: str) -> dict[str, Any]:
    """Collect one safe source-file batch of fully imported pending art jobs.

    A user can generate several coherent state sets before publishing.  Their
    WML animation wiring often lands in the same unit source file, so treating
    the neighboring complete sets as unrelated local changes would make each
    otherwise-valid import impossible.  This deliberately batches only jobs
    which share the selected job's source file and independently pass the full
    local import contract.  Missing or partially wired jobs never enter the
    batch.
    """

    selected = art_import_contract(root, job_id)
    if not selected.get("pass"):
        return selected
    selected_preflight = art_import_preflight(root, job_id)
    if not selected_preflight.get("pass"):
        return {**selected_preflight, "job_ids": []}

    manifest = _load_manifest(root / ADDON_ROOT / ART_MANIFEST)
    jobs = manifest.get("jobs") if isinstance(manifest, dict) else None
    if not isinstance(jobs, list):
        return {"pass": False, "message": "Art queue manifest is missing or invalid", "job_ids": []}
    source_path = selected["source_path"]
    contracts: list[dict[str, Any]] = []
    for job in jobs:
        candidate_id = job.get("id") if isinstance(job, dict) else None
        # ``complete`` is the durable manifest state of an already-published
        # import.  It must never be reintroduced into a later batch merely
        # because it shares its WML source file.
        if not isinstance(candidate_id, str) or job.get("state") == "complete":
            continue
        candidate = art_import_contract(root, candidate_id)
        if not candidate.get("pass") or candidate.get("source_path") != source_path:
            continue
        if art_import_preflight(root, candidate_id).get("pass"):
            contracts.append(candidate)
    if not any(contract["job"]["id"] == job_id for contract in contracts):
        return {"pass": False, "message": "Selected art is no longer eligible for governed import", "job_ids": []}

    assets: dict[str, dict[str, str]] = {}
    for contract in contracts:
        for asset in contract["assets"]:
            assets[asset["path"]] = asset
    return {
        "pass": True,
        "job_ids": [contract["job"]["id"] for contract in contracts],
        "unit_ids": [contract["unit_id"] for contract in contracts],
        "unit_names": [contract["unit_name"] for contract in contracts],
        "source_path": source_path,
        "assets": [assets[path] for path in sorted(assets)],
        "message": (
            "One verified art import is ready for governed publication."
            if len(contracts) == 1
            else f"{len(contracts)} verified art imports share one unit source and will publish as one ordered batch."
        ),
    }


def confirm_art_import(root: Path, job_id: str) -> dict[str, Any]:
    """Mark exactly one fully verified user-imported art job complete."""

    preflight = art_import_preflight(root, job_id)
    if not preflight["pass"]:
        return preflight
    manifest_path = root / ADDON_ROOT / ART_MANIFEST
    manifest = _load_manifest(manifest_path)
    jobs = manifest["jobs"]
    job = next(job for job in jobs if isinstance(job, dict) and job.get("id") == job_id)
    if job.get("state") != "complete":
        job["state"] = "complete"
        _atomic_write(manifest_path, json.dumps(manifest, indent=2) + "\n")
    return {
        **preflight,
        "state": "complete",
        "message": "Art import confirmed. The complete state set is staged for governed validation and publication; no LLM follow-up was needed.",
    }


def confirm_art_import_batch(root: Path, job_ids: list[str]) -> dict[str, Any]:
    """Atomically mark an already-verified, same-source art batch complete."""

    unique_ids = list(dict.fromkeys(job_ids))
    if not unique_ids or len(unique_ids) > MAX_ART_JOBS or any(
        not isinstance(job_id, str) or not job_id.startswith("art-") for job_id in unique_ids
    ):
        return {"pass": False, "message": "Art import batch identity is invalid"}
    first = art_import_batch_contract(root, unique_ids[0])
    if not first.get("pass") or first.get("job_ids") != unique_ids:
        return {"pass": False, "message": "Art import batch changed before confirmation"}
    manifest_path = root / ADDON_ROOT / ART_MANIFEST
    manifest = _load_manifest(manifest_path)
    for job in manifest["jobs"]:
        if isinstance(job, dict) and job.get("id") in unique_ids:
            job["state"] = "complete"
    _atomic_write(manifest_path, json.dumps(manifest, indent=2) + "\n")
    return {
        "pass": True,
        "state": "complete",
        "job_ids": unique_ids,
        "message": (
            "Art import confirmed for governed validation and publication."
            if len(unique_ids) == 1
            else f"{len(unique_ids)} art imports confirmed as one governed batch."
        ),
    }


def public_art_queue(
    root: Path, production_status: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
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
        preflight = art_import_preflight(root, str(public_job.get("id") or ""))
        public_job["import_ready"] = bool(preflight["pass"]) and public_job.get("state") != "complete"
        public_job["import_message"] = preflight["message"]
        public_job["requires_llm"] = preflight["requires_llm"]
        production = (production_status or {}).get(str(public_job.get("id") or ""), {})
        if isinstance(production, dict):
            public_job["production_state"] = production.get("state")
            public_job["production_message"] = production.get("message")
            public_job["production_error"] = production.get("error")
            public_job["production_completed_at"] = production.get("completed_at")
        jobs.append(public_job)
    return {
        "pass": evidence["pass"],
        "diagnostic": evidence["diagnostic"],
        "pending": evidence["pending"],
        "complete": evidence["complete"],
        "jobs": jobs,
        "policy": "Codex quota interactive art generation; no API key",
    }
