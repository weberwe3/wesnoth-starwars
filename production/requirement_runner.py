"""Run one accepted engine fixture and bind its direct observation to evidence.

Only this live invocation may report a scoped observed result. Persisted
envelopes alone never grant readiness after restart; a future protected
consumer must also reconcile runner origin and requirement coverage.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile

try:  # Direct script and package imports both serve coordinator callers.
    from .evidence import SCHEMA_ID as EVIDENCE_SCHEMA_ID, assess_freshness, validate_envelope
    from .inventory import check_inventory
    from .mission_probe import run_probe
except ImportError:
    from evidence import SCHEMA_ID as EVIDENCE_SCHEMA_ID, assess_freshness, validate_envelope
    from inventory import check_inventory
    from mission_probe import run_probe


SPEC_PATH = "production/requirements/restore_beacon_objective.json"
INVENTORY_PATH = "production/source_inventory.json"
EXTRA_DEPENDENCIES = (
    SPEC_PATH, INVENTORY_PATH, "production/evidence.py",
    "production/mission_probe.py", "production/requirement_runner.py",
    "production/inventory.py", "production/contract_store.py",
)
SHA1 = re.compile(r"[0-9a-f]{40}\Z")


class RequirementRunError(ValueError):
    """An accepted requirement cannot be exercised with trusted inputs."""


def _digest(path: Path) -> str:
    sha = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(65536), b""):
            sha.update(chunk)
    return sha.hexdigest()


def _git(root: Path, *args: str) -> str:
    if os.name == "nt":
        distro = os.environ.get("WESNOTH_WSL_DISTRO", "Ubuntu-24.04")
        resolved = root.resolve()
        drive = resolved.drive
        if len(drive) != 2 or drive[1] != ":" or not drive[0].isalpha():
            raise RequirementRunError("WSL Git path unavailable")
        linux_root = "/mnt/" + drive[0].lower() + resolved.as_posix()[2:]
        command = ["wsl.exe", "-d", distro, "--", "git", "-C", linux_root, *args]
    else:
        command = ["git", "-C", str(root), *args]
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=30, check=False)
    except (OSError, subprocess.SubprocessError) as exc:
        raise RequirementRunError("Git identity unavailable") from exc
    if result.returncode:
        raise RequirementRunError("Git identity unavailable")
    return result.stdout.strip()


def _spec(root: Path) -> dict:
    path = root / SPEC_PATH
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 20_000:
        raise RequirementRunError("accepted requirement specification missing")
    try:
        spec = json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise RequirementRunError("accepted requirement specification invalid") from exc
    required = {"schema_id", "schema_version", "id", "scenario_id", "positive_case",
                "negative_case", "exercise_type", "difficulty", "seed",
                "expected_exit_code", "limitation"}
    if (not isinstance(spec, dict) or set(spec) != required
            or spec["schema_id"] != "wesnoth-starwars.production.scoped-engine-requirement"
            or spec["schema_version"] != 1
            or spec["positive_case"] != "path_to_beacon"
            or spec["negative_case"] != "wrong_unit_terminal"
            or spec["expected_exit_code"] != 8):
        raise RequirementRunError("unsupported scoped requirement")
    return spec


def accepted_requirement(root: Path) -> dict:
    spec = _spec(root)
    inventory = json.loads((root / INVENTORY_PATH).read_text(encoding="utf-8"))
    source_files = inventory.get("source_files") if isinstance(inventory, dict) else None
    if not isinstance(source_files, list):
        raise RequirementRunError("source inventory unavailable")
    source_paths = [item.get("path") for item in source_files if isinstance(item, dict)]
    if (len(source_paths) != len(source_files)
            or any(not isinstance(path, str) or not path for path in source_paths)
            or len(source_paths) != len(set(source_paths))):
        raise RequirementRunError("requirement dependency inventory invalid")
    paths = sorted(set(source_paths) | set(EXTRA_DEPENDENCIES))
    if not 1 <= len(paths) <= 128:
        raise RequirementRunError("requirement dependency inventory invalid or unbounded")
    return {
        "id": spec["id"], "revision_sha256": _digest(root / SPEC_PATH),
        "scenario_id": spec["scenario_id"],
        "probe_id": "sw_probe_restore_beacon_path_to_beacon",
        "exercise_type": spec["exercise_type"], "difficulty": spec["difficulty"],
        "seed": spec["seed"], "expected_exit_code": spec["expected_exit_code"],
        "dependency_paths": paths,
    }


def _write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.parent.is_symlink():
        raise RequirementRunError("symlinked runtime evidence directory")
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", suffix=".tmp",
                                     prefix=".requirement-", dir=path.parent, delete=False) as stream:
        json.dump(value, stream, indent=2)
        stream.write("\n")
        temporary = Path(stream.name)
    try:
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def execute_requirement(root: Path, engine: Path) -> dict:
    """Execute the two fixed engine cases and assess this run in process."""
    check_inventory(root, root / INVENTORY_PATH)
    spec = _spec(root)
    requirement = accepted_requirement(root)
    if not engine.is_absolute() or engine.is_symlink() or not engine.is_file():
        raise RequirementRunError("installed engine missing or symlinked")
    commit = _git(root, "rev-parse", "HEAD")
    tree = _git(root, "rev-parse", "HEAD^{tree}")
    if not SHA1.fullmatch(commit) or not SHA1.fullmatch(tree):
        raise RequirementRunError("candidate Git identity invalid")
    if _git(root, "status", "--porcelain", "--untracked-files=all"):
        raise RequirementRunError("candidate worktree has uncommitted files")
    cases = [spec["positive_case"], spec["negative_case"]]
    raw = run_probe(root, engine, cases)
    if not isinstance(raw, dict):
        raise RequirementRunError("engine probe returned no structured result")
    rows = raw.get("results")
    by_case = {item.get("case"): item for item in rows} if isinstance(rows, list) and all(isinstance(item, dict) for item in rows) else {}
    positive, negative = by_case.get(cases[0]), by_case.get(cases[1])
    observed = bool(
        raw.get("pass") is True and len(rows or []) == 2
        and positive and negative
        and isinstance(raw.get("engine_version"), str) and bool(raw["engine_version"])
        and positive.get("test_id") == requirement["probe_id"]
        and positive.get("log_verdict") == "victory" and positive.get("exit_code") == 8
        and positive.get("meets_expectation") is True
        and negative.get("log_verdict") == "pass" and negative.get("exit_code") == 0
        and negative.get("meets_expectation") is True
        and raw.get("legal_objective_victory") == "observed_with_enemy_turn_disabled_and_terminal_dialogue_suppressed"
        and raw.get("wrong_unit_rejection") == "observed_with_commander_start_staged"
    )
    artifact_rel = "agent/runtime/requirements/restore-beacon-objective-raw.json"
    artifact = root / artifact_rel
    _write_json(artifact, raw)
    envelope = {
        "schema_id": EVIDENCE_SCHEMA_ID, "schema_version": 1,
        "requirement_id": requirement["id"],
        "requirement_revision_sha256": requirement["revision_sha256"],
        "candidate_commit": commit, "candidate_tree": tree,
        "scenario_id": requirement["scenario_id"], "probe_id": requirement["probe_id"],
        "exercise_type": requirement["exercise_type"], "difficulty": requirement["difficulty"],
        "seed": requirement["seed"], "engine_version": raw.get("engine_version") or "unobserved",
        "engine_sha256": _digest(engine),
        "dependencies": [{"path": rel, "sha256": _digest(root / rel)}
                         for rel in requirement["dependency_paths"]],
        "artifact_path": artifact_rel, "artifact_sha256": _digest(artifact),
        "exit_code": positive.get("exit_code") if positive else -1,
        "outcome": "pass" if observed else "fail",
        "observations": ["source engineer route fixture: " + str(positive.get("log_verdict") if positive else "missing"),
                         "staged commander negative fixture: " + str(negative.get("log_verdict") if negative else "missing")],
    }
    validate_envelope(envelope)
    assessment = assess_freshness(root, envelope, requirement, engine)
    accepted_now = observed and assessment["freshness"] == "current" and assessment["result_matches"]
    _write_json(root / "agent/runtime/requirements/restore-beacon-objective-envelope.json", envelope)
    return {"pass": accepted_now, "scope": "controlled objective fixture only",
            "requirement_id": requirement["id"], "freshness": assessment,
            "raw_artifact_sha256": envelope["artifact_sha256"],
            "envelope_sha256": _digest(root / "agent/runtime/requirements/restore-beacon-objective-envelope.json"),
            "candidate_commit": commit, "candidate_tree": tree}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--engine", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = execute_requirement(args.repo_root, args.engine)
    except (RequirementRunError, OSError, ValueError) as exc:
        parser.error(str(exc))
    print(json.dumps(result, indent=2))
    return 0 if result["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
