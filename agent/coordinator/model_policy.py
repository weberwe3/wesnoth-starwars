"""Persistent model pacing, failure circuits, and daily provider blocks."""

from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
import time
from typing import Callable


SCHEMA_VERSION = 1
SKIP_FUTURE_RUNS = 2
CLOUDFLARE_PROVIDER = "cloudflare-workers-ai"
CLOUDFLARE_PREFIX = CLOUDFLARE_PROVIDER + "/"
CLOUDFLARE_DAILY_QUOTA_MARKERS = (
    "daily free allocation",
    "10,000 neurons",
)

# Workflow-launch ceilings use each service's published free-tier maximum.
# None means the service publishes only account/project-specific limits, so
# its own quota remains authoritative rather than inventing a local ceiling.
MODEL_RPM: dict[str, int | None] = {
    "groq/openai/gpt-oss-120b": 30,
    "opencode/ling-3.0-flash-fin-free": None,
    "cloudflare-workers-ai/@cf/zai-org/glm-4.7-flash": 300,
    "cloudflare-workers-ai/@cf/nvidia/nemotron-3-120b-a12b": 40,
    "google/gemini-3.8-flash": None,
    "google/gemini-3.6-flash": None,
    "openai/gpt-5.6-sol": None,
    "openai/gpt-5.6-terra": None,
    "openai/gpt-5.6-luna": None,
}

MODEL_LIMIT_SOURCE = {
    "groq/openai/gpt-oss-120b": "published free tier",
    "opencode/ling-3.0-flash-fin-free": "provider/account assigned",
    "cloudflare-workers-ai/@cf/zai-org/glm-4.7-flash": "published free tier",
    "cloudflare-workers-ai/@cf/nvidia/nemotron-3-120b-a12b": "published free tier",
    "google/gemini-3.8-flash": "provider/project assigned",
    "google/gemini-3.6-flash": "provider/project assigned",
    "openai/gpt-5.6-sol": "Codex account managed",
    "openai/gpt-5.6-terra": "Codex account managed",
    "openai/gpt-5.6-luna": "Codex account managed",
}

AGENT_MODELS = {
    "implementer": "groq/openai/gpt-oss-120b",
    "fast-fix": "opencode/ling-3.0-flash-fin-free",
    "tester": "cloudflare-workers-ai/@cf/zai-org/glm-4.7-flash",
    "reviewer": "cloudflare-workers-ai/@cf/nvidia/nemotron-3-120b-a12b",
    "reviewer-intermediate": "google/gemini-3.8-flash",
    "reviewer-fallback": "google/gemini-3.6-flash",
}


class ModelPolicy:
    """Coordinate model launches across sequential ticket-runner processes."""

    def __init__(
        self,
        runtime_dir: Path,
        *,
        clock: Callable[[], float] = time.time,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        self.path = runtime_dir / "model-policy.json"
        self.clock = clock
        self.sleeper = sleeper
        runtime_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _default() -> dict:
        return {
            "schema_version": SCHEMA_VERSION,
            "run_sequence": 0,
            "models": {},
            "provider_blocks": {},
        }

    def _read(self) -> dict:
        try:
            state = json.loads(self.path.read_text(encoding="utf-8"))
        except (FileNotFoundError, OSError, json.JSONDecodeError):
            return self._default()
        if (
            not isinstance(state, dict)
            or state.get("schema_version") != SCHEMA_VERSION
            or not isinstance(state.get("run_sequence"), int)
            or not isinstance(state.get("models"), dict)
        ):
            return self._default()
        state.setdefault("provider_blocks", {})
        if not isinstance(state["provider_blocks"], dict):
            state["provider_blocks"] = {}
        return state

    @staticmethod
    def _next_utc_midnight(timestamp: float) -> float:
        return float((int(timestamp) // 86_400 + 1) * 86_400)

    @staticmethod
    def _is_cloudflare_daily_quota(model: str, output: str) -> bool:
        folded = output.casefold()
        return model.startswith(CLOUDFLARE_PREFIX) and any(
            marker in folded for marker in CLOUDFLARE_DAILY_QUOTA_MARKERS
        )

    @staticmethod
    def _provider_for(model: str) -> str | None:
        if model.startswith(CLOUDFLARE_PREFIX):
            return CLOUDFLARE_PROVIDER
        return None

    def _active_provider_block(
        self, state: dict, model: str, now: float
    ) -> dict | None:
        provider = self._provider_for(model)
        if provider is None:
            return None
        block = state["provider_blocks"].get(provider)
        if not isinstance(block, dict):
            return None
        try:
            blocked_until = float(block.get("blocked_until", 0))
        except (TypeError, ValueError):
            blocked_until = 0
        if blocked_until > now:
            return block

        state["provider_blocks"].pop(provider, None)
        for candidate, record in state["models"].items():
            if candidate.startswith(CLOUDFLARE_PREFIX) and isinstance(record, dict):
                record.pop("skip_through_run", None)
                if record.get("last_failure") == "quota":
                    record.pop("last_failure", None)
                    record.pop("failed_at", None)
        self._write(state)
        return None

    def _write(self, state: dict) -> None:
        handle, name = tempfile.mkstemp(
            prefix=".model-policy-", suffix=".tmp", dir=self.path.parent
        )
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as stream:
                json.dump(state, stream, indent=2, sort_keys=True)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.chmod(name, 0o600)
            os.replace(name, self.path)
        finally:
            try:
                os.unlink(name)
            except FileNotFoundError:
                pass

    def begin_run(self, task_id: str) -> int:
        state = self._read()
        state["run_sequence"] += 1
        state["current_task_id"] = task_id
        state["current_run_sequence"] = state["run_sequence"]
        self._write(state)
        return state["run_sequence"]

    def before_attempt(self, model: str, run_sequence: int) -> tuple[bool, float]:
        """Return availability and enforce the configured launch interval."""

        if model not in MODEL_RPM:
            raise ValueError(f"No RPM policy is configured for {model}")
        state = self._read()
        now = self.clock()
        if self._active_provider_block(state, model, now):
            return False, 0.0
        record = state["models"].get(model, {})
        if int(record.get("skip_through_run", 0)) >= run_sequence:
            return False, 0.0

        rpm = MODEL_RPM[model]
        minimum_interval = 0.0 if rpm is None else 60.0 / rpm
        wait = max(0.0, minimum_interval - (now - float(record.get("last_attempt_at", 0))))
        if wait:
            self.sleeper(wait)
            now = self.clock()
        record["last_attempt_at"] = now
        state["models"][model] = record
        self._write(state)
        return True, wait

    def record_success(self, model: str) -> None:
        state = self._read()
        record = state["models"].get(model, {})
        record.pop("last_failure", None)
        record.pop("failed_at", None)
        record.pop("skip_through_run", None)
        state["models"][model] = record
        self._write(state)

    def record_failure(
        self,
        model: str,
        run_sequence: int,
        failure: str,
        output: str = "",
    ) -> None:
        if failure not in {"process", "timeout", "non_decisive", "quota"}:
            raise ValueError("Unsupported model failure class")
        state = self._read()
        record = state["models"].get(model, {})
        now = self.clock()
        if self._is_cloudflare_daily_quota(model, output):
            blocked_until = self._next_utc_midnight(now)
            state["provider_blocks"][CLOUDFLARE_PROVIDER] = {
                "reason": "daily_free_allocation",
                "blocked_until": blocked_until,
            }
            record.pop("skip_through_run", None)
        else:
            record["skip_through_run"] = max(
                int(record.get("skip_through_run", 0)),
                run_sequence + SKIP_FUTURE_RUNS,
            )
        record["last_failure"] = failure
        record["failed_at"] = now
        state["models"][model] = record
        self._write(state)

    def unavailable_reason(self, model: str, run_sequence: int) -> str:
        state = self._read()
        now = self.clock()
        block = self._active_provider_block(state, model, now)
        if block:
            reset = time.strftime(
                "%Y-%m-%d %H:%M:%S UTC",
                time.gmtime(float(block["blocked_until"])),
            )
            return (
                "Cloudflare's daily free allocation is exhausted; all Cloudflare "
                f"models are disabled until the documented reset at {reset}."
            )
        if int(state["models"].get(model, {}).get("skip_through_run", 0)) >= run_sequence:
            return "A recent provider failure suppresses this model for two later worktree runs."
        return "The model is currently unavailable."

    def public_state(self, run_sequence: int) -> dict:
        state = self._read()
        now = self.clock()
        return {
            model: {
                "rpm": rpm,
                "limit_source": MODEL_LIMIT_SOURCE[model],
                "available_this_run": (
                    self._active_provider_block(state, model, now) is None
                    and int(state["models"].get(model, {}).get("skip_through_run", 0))
                    < run_sequence
                ),
                "skip_through_run": int(
                    state["models"].get(model, {}).get("skip_through_run", 0)
                ),
                "last_failure": state["models"].get(model, {}).get("last_failure"),
                "blocked_until": (
                    state["provider_blocks"].get(CLOUDFLARE_PROVIDER, {}).get(
                        "blocked_until"
                    )
                    if model.startswith(CLOUDFLARE_PREFIX)
                    else None
                ),
            }
            for model, rpm in MODEL_RPM.items()
        }


def failure_kind(return_code: int, output: str, *, decisive: bool = True) -> str | None:
    if return_code == 0 and decisive:
        return None
    text = output.casefold()
    if any(marker in text for marker in (
        "rate limit", "rate_limit", "quota", "resource_exhausted",
        "too many requests", '"statuscode":429', "daily free allocation",
    )):
        return "quota"
    if return_code == 124 or "process timeout" in text or "timed out" in text:
        return "timeout"
    if return_code != 0:
        return "process"
    return "non_decisive"
