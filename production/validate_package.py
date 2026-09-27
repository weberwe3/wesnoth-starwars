"""Run existing installed-engine gates against an exact unverified package.

The result is diagnostic evidence. It never changes build eligibility or a
player pointer; promotion must check accepted requirements separately.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile

from build_store import ADDON_ID, BuildStoreError, verify_candidate
from extraction_route_probe import probe as probe_extraction_route
from interception_route_probe import probe as probe_interception_route
from sequence_load_probe import probe as probe_sequence_load

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "agent" / "coordinator"))
from scenario_launch_selftest import (  # noqa: E402
    SCENARIO_ID, runtime_scenario_probes, validate_engine_002,
)


SCHEMA_ID = "wesnoth-starwars.production.package-engine-validation"


def _digest(path: Path) -> str:
    sha = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(65536), b""):
            sha.update(chunk)
    return sha.hexdigest()


def _copy_matches(manifest: dict, addon: Path) -> bool:
    expected = {item["path"]: item for item in manifest["files"]}
    observed = set()
    for path in addon.rglob("*"):
        if path.is_symlink():
            return False
        if path.is_file():
            rel = path.relative_to(addon).as_posix()
            item = expected.get(rel)
            if item is None or path.stat().st_size != item["bytes"] or _digest(path) != item["sha256"]:
                return False
            observed.add(rel)
    return observed == set(expected)


def validate_packaged_candidate(repo_root: Path, candidate: Path, engine: Path) -> dict:
    """Copy verified bytes into isolated userdata and exercise existing gates."""
    manifest = verify_candidate(candidate)
    result = {
        "schema_id": SCHEMA_ID, "schema_version": 2,
        "candidate_build_id": manifest["build_id"],
        "source_commit": manifest["source_commit"],
        "source_tree": manifest["source_tree"],
        "package_sha256": manifest["package_sha256"],
        "engine_sha256": None,
        "harness_sha256": _digest(Path(__file__).resolve().parents[1] / "agent/coordinator/scenario_launch_selftest.py"),
        "sequence_harness_sha256": _digest(Path(__file__).resolve().parent / "sequence_load_probe.py"),
        "route_harness_sha256": _digest(Path(__file__).resolve().parent / "extraction_route_probe.py"),
        "interception_route_harness_sha256": _digest(Path(__file__).resolve().parent / "interception_route_probe.py"),
        "scenario_ids": [SCENARIO_ID],
        "sequence_scenario_ids": ["sw_02_space_interception", "sw_03_ground_extraction"],
        "route_scenario_ids": ["sw_02_space_interception", "sw_03_ground_extraction"],
        "package_copy_matches": False, "candidate_still_matches": False,
        "preprocess": None, "sequence_first_moves": None,
        "extraction_objective_route": None, "interception_objective_route": None,
        "runtime": None,
        "pass": False,
    }
    if not engine.is_absolute() or engine.is_symlink() or not engine.is_file():
        result["diagnostic"] = "Installed engine binary is missing or symlinked"
        return result
    result["engine_sha256"] = _digest(engine)
    runtime = repo_root / "agent" / "runtime"
    runtime.mkdir(parents=True, exist_ok=True)
    if runtime.is_symlink():
        result["diagnostic"] = "Runtime storage is symlinked"
        return result
    with tempfile.TemporaryDirectory(prefix=".package-validation-", dir=runtime) as directory:
        root = Path(directory) / "package"
        addon = root / "addons" / ADDON_ID
        addon.parent.mkdir(parents=True)
        shutil.copytree(candidate / "addon", addon)
        result["package_copy_matches"] = _copy_matches(manifest, addon)
        if not result["package_copy_matches"]:
            result["diagnostic"] = "Staged game bytes differ from candidate manifest"
            return result
        result["preprocess"] = validate_engine_002(root, executable=engine)
        if result["preprocess"].get("pass") is True:
            result["sequence_first_moves"] = probe_sequence_load(root, engine)
            if result["sequence_first_moves"].get("pass") is True:
                result["extraction_objective_route"] = probe_extraction_route(root, engine)
                if result["extraction_objective_route"].get("pass") is True:
                    result["interception_objective_route"] = probe_interception_route(root, engine)
                    if result["interception_objective_route"].get("pass") is True:
                        result["runtime"] = runtime_scenario_probes(root, engine, {SCENARIO_ID})
        result["package_copy_matches"] = _copy_matches(manifest, addon)
    try:
        result["candidate_still_matches"] = verify_candidate(candidate)["package_sha256"] == manifest["package_sha256"]
    except BuildStoreError:
        result["candidate_still_matches"] = False
    result["pass"] = (
        result["package_copy_matches"] and result["candidate_still_matches"]
        and result["preprocess"].get("pass") is True
        and isinstance(result["sequence_first_moves"], dict)
        and result["sequence_first_moves"].get("pass") is True
        and isinstance(result["extraction_objective_route"], dict)
        and result["extraction_objective_route"].get("pass") is True
        and isinstance(result["interception_objective_route"], dict)
        and result["interception_objective_route"].get("pass") is True
        and isinstance(result["runtime"], dict) and result["runtime"].get("pass") is True
    )
    if not result["pass"]:
        result["diagnostic"] = "Exact package failed preprocessing, sequence first moves, extraction route, interception route, GUI startup, or integrity recheck"
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--engine", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    output = args.output or args.repo_root / "agent/runtime/package-engine-validation.json"
    try:
        result = validate_packaged_candidate(args.repo_root, args.candidate, args.engine)
    except (BuildStoreError, OSError, ValueError) as exc:
        parser.error(str(exc))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"pass": result["pass"], "output": str(output),
                      "package_sha256": result["package_sha256"]}))
    return 0 if result["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
