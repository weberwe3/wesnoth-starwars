# DASH-001 MVP — Local Agent Operations Dashboard

This directory contains the first usable iteration of the live local dashboard.
It is intentionally lightweight and uses only the Python standard library.

## Security model

- The HTTP server binds only to `127.0.0.1` / `localhost`.
- The dashboard serves only structured operational telemetry.
- It does not read, persist, or expose provider tokens or environment-variable values.
- Telemetry is written to `agent/logs/dashboard-state.json`, which is already excluded by the repository's `agent/logs/` ignore rule.
- The deterministic coordinator remains authoritative over ticket execution.

## Start the dashboard

From the repository root in WSL:

```bash
python3 agent/dashboard/dashboard.py --open
```

The default URL is:

```text
http://127.0.0.1:8765
```

The server refuses non-local bind addresses.

## Run a ticket with live telemetry

Use the dashboard-aware wrapper instead of invoking `ticket_runner.py` directly:

```bash
python3 agent/dashboard/run_ticket_live.py /path/to/ticket.json
```

The wrapper delegates the actual work to the existing deterministic ticket runner. It instruments the existing function calls at runtime so the MVP does not modify coordinator source code.

The dashboard shows:

- Coordinator
- Implementer
- Fast-Fix
- Deterministic Validation
- Tester
- Reviewer
- Reviewer Fallback
- exact configured model and provider for every LLM role
- active/idle/waiting/error state
- current task and elapsed state time
- current ticket and branch/worktree context
- recent activity and errors
- directional animated handoffs between pipeline stages

Model assignments are read from the committed `.opencode/agents/*.md` definitions rather than hard-coded into the browser UI.

## MVP limitations

This is a usable preview, not the final DASH-001 implementation.

Still planned:

- automatic startup through the existing secure Windows launcher/batch workflow;
- direct telemetry hooks in the deterministic coordinator after the MVP is proven;
- richer historical views, filters, and metrics;
- additional visual refinement and accessibility review;
- automated dashboard-specific tests.

Do not merge the MVP solely because it renders successfully. Complete local validation and the normal GitHub review/CI workflow first.
