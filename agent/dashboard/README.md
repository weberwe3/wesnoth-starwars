# Wesnoth Agent Manager dashboard

The dashboard is a structured telemetry view and localhost-only coordination
control plane. It uses only the Python standard library, binds exclusively to
`127.0.0.1`, and does not inspect process environment variables, provider
credentials, model logs, or the Windows secret store.

Start it from WSL:

```bash
bash ./agent/dashboard/start-dashboard.sh
```

Open `http://127.0.0.1:8765`.

For the Windows startup workflow, use `Start-WesnothAgentEnvironment.cmd`.
It starts a hidden native Windows control bridge, starts the dashboard, and
then delegates interactive credential handling unchanged to the existing
DPAPI-backed secure launcher. The existing secure launcher is not modified and
no credential is forwarded to the dashboard process.

## Coordinator modes

The **Coordination authority** control offers four modes:

- **Python** keeps the existing manual Python/Bash workflow.
- **Sol Low**, **Sol Medium**, and **Sol High** use GPT-5.6 Sol at the selected
  reasoning effort to propose one bounded ticket from the supplied brief.

Selecting a Sol mode does not begin work. Enter an optional brief, or load an
editable brief from the **planned ticket** menu, and choose **Hand off one
ticket**. Sol runs in a read-only planning sandbox and returns a
strict ticket object. Python then validates that object with the existing
ticket schema and protected-path rules. Only after validation does the
dashboard invoke the unchanged DPAPI secure launcher with a fixed
`secure_ticket_bridge.py` command. The native bridge accepts only a random run
ID and allowlisted recovery effort, derives all paths itself, and publishes a
numeric result plus a bounded secret-free failure diagnostic. The resulting work occurs in the normal isolated worktree and passes
through deterministic validation, tester, and reviewer gates.

GPT-OSS 120B remains the primary Implementer. If that process fails, the
runner makes one sandboxed GPT-5.6 Terra attempt at medium reasoning and shows
the live assignment in the Implementer card and activity log. Failure of both
providers stops the ticket without starting an unbounded retry cycle.

The green **Automation** switch lets the selected Sol effort plan another
bounded ticket after each safe completion. Turning it off prevents the next
ticket from starting; it does not interrupt an active gate mid-operation.
Switching back to **Python** restores the manual Python/Bash workflow.

In continuous automation, eligible implementation, deterministic-validation,
tester, or substantive reviewer failures can trigger no more than two recovery
attempts for the ticket. The selected Sol effort produces a read-only corrective
plan, Fast-Fix applies only that narrow plan inside the original allowed paths,
and Python reruns all gates. A third repair call is forbidden. Repository
hygiene, scope/protected-path, approval, security, credential, bridge, provider,
or publication failures stop immediately and consume no repair attempt. Error
entries show the safe diagnostic, required action, and attempt count.

Before Sol plans a ticket, Python inventories the local approval queue, local
agent branches, and open pull requests. A proposal that overlaps queued work or
an open PR is rejected instead of creating a duplicate ticket.

Passing tickets are committed locally and appear in the FIFO **Ticket approval
queue**. **Approve & publish** is a single, explicit authorization bound to the
displayed commit. The fail-closed publication pipeline verifies the clean
candidate, pushes without force, creates or reuses a PR, waits for exact-head
required CI, verifies protected-merge readiness, squash-merges, and
fast-forwards local `main`. A changed commit, missing CI evidence, dirty local
`main`, or GitHub error stops the pipeline. Controlled references remain
available only through their dedicated governance-ticket process.

Tickets that delete files pause before the local commit. The queue creates an
exact request and manifest digest under ignored `agent/runtime/`. The project
owner checks the dashboard queue and explicitly approves or rejects the matching
request ID and digest with the trusted local decision command:

```bash
python3 agent/dashboard/deletion_approval.py approve REQUEST_ID MANIFEST_DIGEST
# or
python3 agent/dashboard/deletion_approval.py reject REQUEST_ID MANIFEST_DIGEST
```

The local manifest gate is authoritative. No background notification automation
is required or installed.

Control POSTs require an in-memory same-origin nonce, reject non-loopback Host
headers and foreign Origin headers, and accept only allowlisted control JSON.
The nonce is regenerated whenever the dashboard restarts. Coordinator briefs
are sent to Sol, so never paste credentials into that field.

Runtime state is stored under the ignored `agent/runtime/` directory. The path
is deliberately fixed so the HTTP server cannot be pointed at arbitrary JSON.
Generated Sol proposals and control state are mode `0600` and are not served as
static files.
Override the port with `WESNOTH_DASHBOARD_PORT`.
