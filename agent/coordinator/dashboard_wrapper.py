#!/usr/bin/env python3

"""DASH-001 dashboard-aware wrapper around ticket_runner.py.

Per the DASH-001 MVP integration strategy, this wrapper instruments the
protected coordinator at runtime WITHOUT modifying ticket_runner.py: it
monkey-patches the worker-invocation entry points in the ticket_runner module
namespace and emits secret-free telemetry events (see dashboard_telemetry.py).

Instrumented lifecycle:
- run_ticket: coordinator active/idle + ticket started/completed/failed.
- invoke_agent: per-role active/idle|error with elapsed time; handoff
  coordinator -> role on dispatch.
- run_validation: deterministic-validation active/idle.

Usage:
    python3 dashboard_wrapper.py <ticket.json> [--recovery-effort low|medium|high] [--dashboard]

With --dashboard, the DASH-001 dashboard server starts in a background thread
for the duration of the run (automatic startup integration for the secure
launcher / batch flow: point the launcher at the wrapper instead of
ticket_runner.py and the dashboard comes up with the ticket).

Telemetry is best-effort and never changes runner behavior: if telemetry
fails, the run continues unaffected.
"""

from __future__ import annotations

import functools
import sys
import time
from pathlib import Path
from typing import Any, Callable

sys.path.insert(0, str(Path(__file__).resolve().parent))

import dashboard_telemetry as telemetry
import ticket_runner

# Map ticket_runner agent names onto DASH-001 dashboard roles.
AGENT_ROLE_MAP = {
    "implementer": "implementer",
    "fast-fix": "fast-fix",
    "tester": "tester",
    "reviewer": "reviewer",
    "reviewer-fallback": "reviewer-fallback",
}

_current_ticket_id = "unknown"


def _role_for(agent: str) -> str:
    return AGENT_ROLE_MAP.get(agent, agent)


def _wrap_invoke_agent(original: Callable) -> Callable:
    @functools.wraps(original)
    def instrumented(*, agent: str, **kwargs: Any) -> Any:
        role = _role_for(agent)
        telemetry.handoff("coordinator", role, ticket_id=_current_ticket_id)
        telemetry.role_state(role, "active", task=_current_ticket_id)
        start = time.monotonic()
        try:
            rc, output = original(agent=agent, **kwargs)
        except Exception:
            telemetry.role_state(
                role, "error", task=_current_ticket_id,
                elapsed_s=time.monotonic() - start, detail="exception",
            )
            raise
        elapsed = time.monotonic() - start
        state = "idle" if rc == 0 else "error"
        telemetry.role_state(
            role, state, task=_current_ticket_id, elapsed_s=elapsed,
            detail="" if rc == 0 else f"exit {rc}",
        )
        return rc, output

    return instrumented


def _wrap_run_validation(original: Callable) -> Callable:
    @functools.wraps(original)
    def instrumented(*args: Any, **kwargs: Any) -> Any:
        role = "deterministic-validation"
        telemetry.role_state(role, "active", task=_current_ticket_id)
        start = time.monotonic()
        try:
            return original(*args, **kwargs)
        finally:
            telemetry.role_state(
                role, "idle", task=_current_ticket_id,
                elapsed_s=time.monotonic() - start,
            )

    return instrumented


def _wrap_run_ticket(original: Callable) -> Callable:
    @functools.wraps(original)
    def instrumented(ticket_path: Path, recovery_effort: str | None = None) -> int:
        global _current_ticket_id
        _current_ticket_id = Path(ticket_path).stem
        telemetry.role_state("coordinator", "active", task=_current_ticket_id)
        telemetry.ticket_event(_current_ticket_id, "started")
        try:
            rc = original(ticket_path, recovery_effort)
        except Exception as exc:
            telemetry.ticket_event(
                _current_ticket_id, "failed", detail=type(exc).__name__
            )
            telemetry.role_state("coordinator", "error", task=_current_ticket_id)
            raise
        telemetry.ticket_event(
            _current_ticket_id, "completed" if rc == 0 else "failed",
            detail=f"exit {rc}",
        )
        telemetry.role_state(
            "coordinator", "idle" if rc == 0 else "error",
            task=_current_ticket_id,
        )
        return rc

    return instrumented


def install() -> None:
    """Patch ticket_runner entry points in its module namespace.

    Internal call sites use the bare names (module-global lookup at call
    time), so patching the module attributes instruments every call path.
    """
    ticket_runner.invoke_agent = _wrap_invoke_agent(ticket_runner.invoke_agent)
    ticket_runner.run_validation = _wrap_run_validation(
        ticket_runner.run_validation
    )
    ticket_runner.run_ticket = _wrap_run_ticket(ticket_runner.run_ticket)


def _start_dashboard() -> Callable[[], None]:
    """Start the dashboard server in a background thread (127.0.0.1 only).

    Returns a stop function with a ``url`` attribute pointing at the server.
    Mirrors dashboard_server's security posture: loopback binding is asserted
    inside dashboard_server.run().
    """
    import threading
    import dashboard_server

    server = dashboard_server.run(0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    url = f"http://127.0.0.1:{server.server_address[1]}/"
    print(f"Dashboard: {url}", flush=True)

    def stop() -> None:
        server.shutdown()
        thread.join(timeout=5)

    stop.url = url  # type: ignore[attr-defined]
    return stop


def main() -> int:
    argv = sys.argv[1:]
    stop_dashboard: Callable[[], None] | None = None
    if "--dashboard" in argv:
        argv = [a for a in argv if a != "--dashboard"]
        stop_dashboard = _start_dashboard()
    sys.argv = [sys.argv[0]] + argv
    install()
    try:
        return ticket_runner.main()
    finally:
        if stop_dashboard is not None:
            stop_dashboard()


def _selftest() -> int:
    """Deterministic self-test with stubbed runner functions (no subprocesses)."""
    import tempfile

    real_dir, real_file = telemetry.TELEMETRY_DIR, telemetry.TELEMETRY_FILE
    orig_invoke = ticket_runner.invoke_agent
    orig_validation = ticket_runner.run_validation
    orig_run_ticket = ticket_runner.run_ticket
    failures: list[str] = []
    try:
        with tempfile.TemporaryDirectory() as tmp:
            telemetry.TELEMETRY_DIR = Path(tmp)
            telemetry.TELEMETRY_FILE = Path(tmp) / "dashboard_telemetry.jsonl"

            calls: list[str] = []

            def fake_invoke(*, agent: str, **kwargs: Any) -> tuple[int, str]:
                calls.append(agent)
                return (0, "ok") if agent != "tester" else (3, "fail")

            def fake_validation(*args: Any, **kwargs: Any) -> dict:
                calls.append("validation")
                return {"pass": True}

            def fake_run_ticket(ticket_path: Path, recovery_effort=None) -> int:
                ticket_runner.invoke_agent(agent="implementer")
                ticket_runner.run_validation()
                ticket_runner.invoke_agent(agent="tester")
                return 0

            ticket_runner.invoke_agent = fake_invoke
            ticket_runner.run_validation = fake_validation
            ticket_runner.run_ticket = fake_run_ticket
            install()
            rc = ticket_runner.run_ticket(Path("/tmp/demo-ticket.json"))
            assert rc == 0, rc

            events = telemetry.read_events(limit=100)
            by_type = [(e["type"], e["role"]) for e in events]
            # coordinator + ticket lifecycle
            assert ("role_state", "coordinator") in by_type, by_type
            assert ("ticket", "coordinator") in by_type, by_type
            # per-role instrumentation with elapsed timing
            impl = [e for e in events
                    if e["type"] == "role_state" and e["role"] == "implementer"]
            assert len(impl) == 2, len(impl)
            assert impl[0]["payload"]["state"] == "active", impl[0]
            assert impl[1]["payload"]["state"] == "idle", impl[1]
            assert impl[1]["payload"]["elapsed_s"] >= 0, impl[1]
            # non-zero exit maps to error state
            tester = [e for e in events
                      if e["type"] == "role_state" and e["role"] == "tester"]
            assert tester[-1]["payload"]["state"] == "error", tester
            # handoff events coordinator -> role
            handoffs = [e for e in events if e["type"] == "handoff"]
            assert len(handoffs) == 2, len(handoffs)
            assert all(h["role"] == "coordinator" for h in handoffs), handoffs
            # deterministic validation instrumented
            dv = [e for e in events
                  if e["role"] == "deterministic-validation"]
            assert len(dv) == 2, len(dv)
            # ticket id comes from the path stem, never ticket contents
            assert all(
                e["payload"].get("task", _current_ticket_id) in ("demo-ticket", "")
                or e["type"] == "ticket"
                for e in events if e["type"] == "role_state"
            ), by_type
            # no secrets in telemetry
            assert "sk-" not in json_dump(events), "secret leak"

            # --dashboard startup integration: server binds loopback, serves state
            stop = _start_dashboard()
            try:
                import json as _json
                import time as _time
                import urllib.request as _request

                _time.sleep(0.3)
                assert stop.url.startswith("http://127.0.0.1:"), stop.url
                with _request.urlopen(
                    stop.url + "api/state", timeout=5
                ) as resp:
                    state = _json.loads(resp.read())
                assert "roles" in state and "history" in state, state.keys()
            finally:
                stop()
    except AssertionError as exc:
        failures.append(f"{exc}")
    finally:
        telemetry.TELEMETRY_DIR, telemetry.TELEMETRY_FILE = real_dir, real_file
        ticket_runner.invoke_agent = orig_invoke
        ticket_runner.run_validation = orig_validation
        ticket_runner.run_ticket = orig_run_ticket

    if failures:
        print("FAIL:", failures)
        return 1
    print("dashboard_wrapper self-test: OK")
    return 0


def json_dump(events: list[dict]) -> str:
    import json

    return json.dumps(events)


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        raise SystemExit(_selftest())
    raise SystemExit(main())
