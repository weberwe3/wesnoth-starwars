# Wesnoth Agent Manager dashboard

The dashboard is a read-only view over structured coordinator telemetry. It
uses only the Python standard library, binds exclusively to `127.0.0.1`, and
does not inspect process environment variables, provider credentials, model
logs, or the Windows secret store.

Start it from WSL:

```bash
bash ./agent/dashboard/start-dashboard.sh
```

Open `http://127.0.0.1:8765`.

For the Windows startup workflow, use `Start-WesnothAgentEnvironment.cmd`.
It starts the dashboard first and then delegates credential handling unchanged
to the existing DPAPI-backed secure launcher. The existing secure launcher is
not modified and no credential is forwarded to the dashboard process.

Runtime state is stored under the ignored `agent/runtime/` directory. The path
is deliberately fixed so the HTTP server cannot be pointed at arbitrary JSON.
Override the port with `WESNOTH_DASHBOARD_PORT`.
