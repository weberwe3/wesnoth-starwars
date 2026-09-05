const roles = {coordinator: "⌁", implementer: "⚒", "fast-fix": "ϟ", validation: "✓", tester: "◫", reviewer: "◇", "reviewer-fallback": "↳"};

const $ = (id) => document.getElementById(id);
let snapshot = null;
let controlSnapshot = null;
let controlToken = null;
let controlBusy = false;
let ticketCatalogReady = false;
const plannedTickets = new Map();
const fragmentAccess = new URLSearchParams(location.hash.slice(1)).get("access");
const fragmentToken = fragmentAccess && /^[A-Za-z0-9_-]{32,128}$/.test(fragmentAccess) ? fragmentAccess : "";
let storedAccess = "";
try {
  storedAccess = localStorage.getItem("wesnoth-dashboard-lan-token") || "";
  if (fragmentToken) {
    localStorage.setItem("wesnoth-dashboard-lan-token", fragmentToken);
    storedAccess = fragmentToken;
    history.replaceState(null, "", `${location.pathname}${location.search}`);
  }
} catch (_) {}
const lanToken = fragmentToken || storedAccess;

function apiHeaders(extra = {}) {
  return lanToken ? {...extra, "X-Wesnoth-LAN-Token": lanToken} : extra;
}

function safe(value, fallback = "—") { return value == null || value === "" ? fallback : String(value); }
function esc(value, fallback = "—") {
  return safe(value, fallback).replace(/[&<>'"]/g, character => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;"})[character]);
}
function displayState(value) { return safe(value, "idle").replaceAll("_", " ").replace(/\b\w/g, c => c.toUpperCase()); }
function clock(value) { if (!value) return "—"; const d = new Date(value); return Number.isNaN(d.valueOf()) ? "—" : d.toLocaleTimeString([], {hour: "2-digit", minute: "2-digit", second: "2-digit"}); }
function duration(start, end = Date.now()) {
  if (!start) return "00:00:00";
  const seconds = Math.max(0, Math.floor((end - new Date(start).getTime()) / 1000));
  return [Math.floor(seconds / 3600), Math.floor(seconds % 3600 / 60), seconds % 60].map(v => String(v).padStart(2, "0")).join(":");
}

async function loadPlannedTickets() {
  const picker = $("planned-ticket");
  try {
    const response = await fetch("/planned-tickets.json", {cache: "no-store"});
    if (!response.ok) throw new Error("Planned tickets unavailable");
    const catalog = await response.json();
    if (!Array.isArray(catalog.tickets)) throw new Error("Invalid ticket catalog");
    picker.replaceChildren(new Option("Choose a planned ticket…", ""));
    for (const ticket of catalog.tickets) {
      if (!ticket || typeof ticket.id !== "string" || typeof ticket.label !== "string" || typeof ticket.brief !== "string") continue;
      plannedTickets.set(ticket.id, ticket.brief);
      picker.add(new Option(ticket.label, ticket.id));
    }
    ticketCatalogReady = plannedTickets.size > 0;
    if (controlSnapshot) renderControl(controlSnapshot);
  } catch (_) {
    picker.replaceChildren(new Option("Planned tickets unavailable", ""));
    picker.disabled = true;
  }
}

function renderQueue(control) {
  const records = control.approval_queue || [];
  const batches = control.approval_batches || [];
  const firstReady = records.find(item => item.state === "ready")?.id;
  const ticketActive = ["planning", "executing", "publishing"].includes(control.run?.state);
  const groupedIds = new Set(batches.flatMap(batch => (batch.members || []).map(item => item.id)));
  const batchCards = batches.slice().reverse().map(batch => {
    const members = batch.members || [];
    const publishable = members[0]?.id === firstReady && !ticketActive;
    const tickets = members.map((item, index) => `<li><b>${index + 1}. ${esc(item.ticket_id)}</b><span>${esc(item.purpose)}</span><code>${esc(item.commit_sha)}</code></li>`).join("");
    const paths = (batch.changed_paths || []).map(path => `<li>${esc(path)}</li>`).join("");
    return `<article class="queue-card queue-batch state-ready">
      <div class="queue-summary"><div><span class="queue-ticket">${esc(batch.ticket_id)}</span><h3>${esc(batch.purpose)}</h3><p>${esc(batch.impact)}</p></div>
      <div class="queue-action"><span class="state-tag">Verified sequence</span><button type="button" class="publish-batch-button" data-batch-id="${esc(batch.id)}" ${publishable && !controlBusy ? "" : "disabled"}>Approve batch &amp; publish</button></div></div>
      <details><summary>Ordered tickets and cumulative publication evidence</summary><div class="queue-details">
        <ol class="batch-members">${tickets}</ol><dl><dt>Final exact head</dt><dd>${esc(batch.commit_sha)}</dd><dt>Publication branch</dt><dd>${esc(batch.branch)}</dd><dt>Dependency proof</dt><dd>Each later commit contains its exact predecessor</dd></dl>
        <div><strong>Combined changed paths</strong><ul>${paths}</ul></div>
      </div></details></article>`;
  });
  const recordCards = records.filter(item => !groupedIds.has(item.id)).slice().reverse().map(item => {
    const publishable = item.state === "ready" && item.id === firstReady && !ticketActive;
    const newerRevision = records.some(other => other.id !== item.id && other.branch === item.branch && !["published", "rejected", "stale", "failed"].includes(other.state));
    const needsRecovery = ["failed", "stale"].includes(item.state);
    const recoverable = needsRecovery && Boolean(item.commit_sha) && !ticketActive && !newerRevision;
    const commit = item.commit_sha || "Pending deletion approval";
    const paths = (item.changed_paths || []).map(path => `<li>${esc(path)}</li>`).join("");
    const deletion = (item.deleted_paths || []).length
      ? `<p class="queue-warning">Deletes ${item.deleted_paths.length} file(s); Codex approval is required before commit.</p>` : "";
    return `<article class="queue-card state-${esc(item.state)}">
      <div class="queue-summary"><div><span class="queue-ticket">${esc(item.ticket_id)}</span><h3>${esc(item.purpose)}</h3><p>${esc(item.impact)}</p></div>
      <div class="queue-action"><span class="state-tag">${esc(displayState(item.state))}</span>
        ${needsRecovery ? `<div class="queue-recovery-actions"><button type="button" class="recode-button" data-record-id="${esc(item.id)}" data-commit-sha="${esc(item.commit_sha, "")}" title="${newerRevision ? "A newer queued revision already owns this branch" : "Resume this exact branch and ask the selected Sol coordinator to repair it"}" ${recoverable && !controlBusy ? "" : "disabled"}>Recode with AI</button><button type="button" class="delete-stale-button" data-record-id="${esc(item.id)}" data-commit-sha="${esc(item.commit_sha, "")}" data-ticket-id="${esc(item.ticket_id)}" data-branch="${esc(item.branch)}" ${recoverable && !controlBusy ? "" : "disabled"}>Delete code &amp; entry</button></div>` : `<button type="button" class="publish-button" data-record-id="${esc(item.id)}" data-commit-sha="${esc(item.commit_sha, "")}" ${publishable && !controlBusy ? "" : "disabled"}>Approve &amp; publish</button>`}
      </div></div>
      <details><summary>Ticket impact and publication evidence</summary><div class="queue-details">
        ${deletion}<dl><dt>Exact commit</dt><dd>${esc(commit)}</dd><dt>Branch</dt><dd>${esc(item.branch)}</dd><dt>Local gates</dt><dd>${esc(item.validation)}</dd><dt>Reviewer</dt><dd>${esc(item.reviewer)}</dd><dt>Publication</dt><dd>${item.pr_number ? `PR #${esc(item.pr_number)} · ${esc(displayState(item.state))}` : esc(displayState(item.state))}</dd></dl>
        <div><strong>Changed paths</strong><ul>${paths}</ul></div>${item.error ? `<p class="queue-error">${esc(item.error)}</p>` : ""}
      </div></details></article>`;
  });
  $("approval-queue").innerHTML = [...batchCards, ...recordCards].join("") || '<p class="empty">No validated tickets awaiting approval</p>';
}

function renderActivity(data, control) {
  const queueActivity = (control.activity || []).map(item => ({...item, sortAt: item.at}));
  const telemetry = (data.events || []).map(item => ({
    at: item.at, sortAt: item.at, level: item.level, message: item.message,
    detail: item.detail || item.message, failure_class: item.failure_class,
    required_action: item.required_action, recovery_attempt: item.recovery_attempt,
    recovery_limit: item.recovery_limit,
    route: item.source ? `${item.source}${item.target ? ` → ${item.target}` : ""}` : "",
  }));
  const routing = (data.routing_history || []).map(item => ({
    at: item.at, sortAt: item.at, level: "info", message: item.message,
    detail: item.message, route: `${item.from} → ${item.to}`,
  }));
  const activity = [...queueActivity, ...telemetry, ...routing]
    .sort((a, b) => String(b.sortAt || "").localeCompare(String(a.sortAt || ""))).slice(0, 16);
  $("activity-log").innerHTML = activity.map(item => {
    const recovery = item.recovery_attempt != null
      ? `<span class="recovery-badge">Attempt ${esc(item.recovery_attempt)} / ${esc(item.recovery_limit || 2)}</span>` : "";
    const failureClass = item.failure_class
      ? `<span class="failure-class">${esc(displayState(item.failure_class))}</span>` : "";
    const inner = `<time>${clock(item.at)}</time>${item.route ? `<span class="event-route">${esc(item.route)}</span>` : ""}<span>${esc(item.message)}</span><span class="event-meta">${failureClass}${recovery}</span>`;
    return item.level === "error"
      ? `<li class="error"><button type="button" class="error-activity" data-message="${esc(item.message)}" data-detail="${esc(item.detail || item.message)}" data-action="${esc(item.required_action || "Review the ticket evidence before retrying.")}">${inner}</button></li>`
      : `<li class="level-${esc(item.level)}">${inner}</li>`;
  }).join("") || '<li class="empty">No activity recorded</li>';
}

function makeNode(data, key) {
    const worker = {...(data.workers?.[key] || {})};
    if (key === "coordinator" && controlSnapshot?.assignment) {
      worker.provider = controlSnapshot.assignment.provider;
      worker.model = controlSnapshot.assignment.effort
        ? `${controlSnapshot.assignment.model} · ${displayState(controlSnapshot.assignment.effort)}`
        : controlSnapshot.assignment.model;
      if (["planning", "executing"].includes(controlSnapshot.run?.state)) {
        worker.state = "active";
        worker.task = controlSnapshot.run.summary;
        worker.started_at = controlSnapshot.run.started_at;
      }
    }
    const node = document.createElement("article");
    node.className = `node ${safe(worker.state, "idle")}`;
    node.dataset.role = key;
    node.innerHTML = `<div class="node-icon" aria-hidden="true">${roles[key]}</div><div class="node-copy"><div class="node-title"><strong>${esc(worker.label, key)}</strong><span class="state-tag">${esc(displayState(worker.state))}</span></div><p class="node-model" title="${esc(worker.model)}">${esc(worker.model)}</p><p class="node-task">${esc(worker.error || worker.task, "Awaiting work")}</p></div><div class="node-provider">${esc(worker.provider)}<br><span class="tabular">${worker.started_at ? duration(worker.started_at) : ""}</span></div>`;
    return node;
}

function connector(data, sources, targets, extra = "") {
  const transfer = data.active_transfer;
  const active = transfer && sources.includes(transfer.from) && targets.includes(transfer.to);
  const reverse = transfer && targets.includes(transfer.from) && sources.includes(transfer.to);
  const line = document.createElement("div");
  line.className = `connector ${extra} ${active || reverse ? "active" : ""} ${reverse ? "reverse" : ""}`;
  line.title = active || reverse ? safe(transfer.message, "Active handoff") : "";
  line.setAttribute("aria-hidden", "true");
  return line;
}

function branchConnector(data, phase) {
  const routes = phase === "split"
    ? [["coordinator", "implementer"], ["coordinator", "fast-fix"]]
    : [["implementer", "validation"], ["fast-fix", "validation"]];
  const group = document.createElement("div");
  group.className = `branch-connector ${phase}`;
  group.setAttribute("aria-hidden", "true");
  for (const [source, target] of routes) {
    const transfer = data.active_transfer;
    const active = transfer?.from === source && transfer?.to === target;
    const reverse = transfer?.from === target && transfer?.to === source;
    const leg = document.createElement("span");
    leg.className = `branch-leg ${active || reverse ? "active" : ""} ${reverse ? "reverse" : ""}`;
    leg.title = active || reverse ? safe(transfer.message, "Active handoff") : `${source} → ${target}`;
    group.append(leg);
  }
  return group;
}

function renderFlow(data) {
  const flow = $("flow");
  flow.replaceChildren();
  flow.append(makeNode(data, "coordinator"));
  flow.append(branchConnector(data, "split"));
  const workers = document.createElement("div");
  workers.className = "worker-branch";
  workers.append(makeNode(data, "implementer"), makeNode(data, "fast-fix"));
  flow.append(workers);
  flow.append(branchConnector(data, "merge"));
  for (const [source, target] of [["validation", "tester"], ["tester", "reviewer"], ["reviewer", "reviewer-fallback"]]) {
    flow.append(makeNode(data, source));
    flow.append(connector(data, [source], [target]));
  }
  flow.append(makeNode(data, "reviewer-fallback"));
}

function render(data) {
  snapshot = data;
  const job = data.job;
  $("mission-title").textContent = job?.task_id || "Standing by";
  $("mission-objective").textContent = job?.objective || "Waiting for the deterministic coordinator.";
  $("job-state").textContent = displayState(job?.state || data.system?.state || "ready");
  $("job-stage").textContent = displayState(job?.stage || "coordinator");
  $("health-state").textContent = displayState(data.system?.state || "ready");
  $("last-update").textContent = `Updated ${clock(data.updated_at)}`;
  const details = [["Branch", job?.branch], ["Worktree", job?.worktree], ["Validation", job?.validation_profile], ["Result", job?.result]];
  $("job-details").innerHTML = details.map(([name, value]) => `<dt>${name}</dt><dd>${esc(value)}</dd>`).join("");
  $("gate-list").innerHTML = (data.gates || []).map(g => `<div class="gate ${esc(g.state).toLowerCase()}"><span><b>${esc(g.name)}</b><br>${esc(g.detail)}</span></div>`).join("");
  renderActivity(data, controlSnapshot || {});
  renderFlow(data);
  const live = data.system?.state !== "stale";
  $("connection-dot").classList.toggle("online", live);
  $("connection-label").textContent = live ? "Live telemetry" : "Telemetry stale";
  updateElapsed();
}

function updateElapsed() {
  const job = snapshot?.job;
  $("elapsed").textContent = job?.started_at ? duration(job.started_at, job.completed_at ? new Date(job.completed_at).getTime() : Date.now()) : "00:00:00";
  document.querySelectorAll(".node.active").forEach(node => {
    const started = snapshot?.workers?.[node.dataset.role]?.started_at;
    const timer = node.querySelector(".node-provider .tabular");
    if (timer && started) timer.textContent = duration(started);
  });
}

async function refresh() {
  try {
    const [statusResponse, controlResponse] = await Promise.all([
      fetch("/api/status", {cache: "no-store", headers: apiHeaders()}),
      fetch("/api/control", {cache: "no-store", headers: apiHeaders()}),
    ]);
    if (!statusResponse.ok || !controlResponse.ok) throw new Error("Status unavailable");
    const control = await controlResponse.json();
    controlToken = control.csrf_token || null;
    delete control.csrf_token;
    renderControl(control);
    render(await statusResponse.json());
  } catch (_) {
    $("connection-dot").classList.remove("online");
    $("connection-label").textContent = "Reconnecting";
  }
}

function renderControl(control) {
  controlSnapshot = control;
  document.querySelectorAll('input[name="mode"]').forEach(input => {
    input.checked = input.value === control.mode;
    input.disabled = controlBusy || ["planning", "executing"].includes(control.run?.state);
  });
  const autonomous = control.mode !== "deterministic";
  const running = ["planning", "executing", "publishing"].includes(control.run?.state);
  const bridgeOnline = control.capabilities?.secure_bridge_online;
  const automated = Boolean(control.automation?.enabled);
  const access = control.access || {};
  if (document.activeElement !== $("coordination-brief") && !$("coordination-brief").value) {
    $("coordination-brief").value = control.automation?.brief || "";
  }
  $("coordination-brief").disabled = !autonomous || running || controlBusy;
  $("planned-ticket").disabled = !ticketCatalogReady || !autonomous || running || controlBusy;
  $("handoff-button").disabled = !autonomous || !bridgeOnline || running || automated || controlBusy;
  $("automation-toggle").checked = automated;
  $("automation-toggle").disabled = !autonomous || !bridgeOnline || controlBusy;
  $("automation-status").textContent = automated ? "Continuous priority scheduling active" : "Manual trigger";
  $("automation-toggle").closest(".automation-control").classList.toggle("active", automated);
  $("handoff-button").textContent = running
    ? (control.run.state === "planning" ? "Sol is planning…" : "Ticket gates running…")
    : "Hand off one ticket";
  $("control-state").textContent = `${control.assignment?.label || "Coordinator"} · ${displayState(control.run?.state)}`;
  $("control-summary").textContent = autonomous && !bridgeOnline
    ? "Secure bridge offline — restart with the Windows launcher"
    : control.run?.error || control.run?.summary || "Ready";
  $("control-state-dot").className = running
    ? "active"
    : control.run?.state === "failed"
      ? "error"
      : control.run?.state === "paused" ? "warning" : "";
  const lanUrl = access.lan_url || "";
  const secureLanUrl = access.lan_access_url || (lanToken && lanUrl ? `${lanUrl}/#access=${lanToken}` : "");
  $("dashboard-address").textContent = access.remote ? "LAN · governed control" : "127.0.0.1 · governed control";
  $("network-exposure").textContent = access.lan_proxy_online ? "LAN online" : "LAN unavailable";
  $("dashboard-lan-url").textContent = lanUrl || "Unavailable";
  $("dashboard-lan-url").href = secureLanUrl || lanUrl || "#";
  $("copy-lan-button").disabled = !secureLanUrl;
  $("copy-lan-button").dataset.url = secureLanUrl;
  $("exit-button").disabled = !access.shutdown_available || controlBusy || !controlToken;
  $("exit-button").textContent = running ? "Exit & preserve work" : "Exit dashboard";
  $("dashboard-action-status").textContent = access.remote
    ? "Secure LAN device paired. All governed controls are available."
    : access.lan_proxy_online
      ? "Use the secure device link to pair another computer on this network."
      : "LAN access is not ready; localhost controls remain available.";
  renderQueue(control);
  if (snapshot) renderActivity(snapshot, control);
}

async function controlAction(payload) {
  if (!controlToken || controlBusy) return;
  controlBusy = true;
  let errorMessage = null;
  let shutdownAccepted = false;
  if (controlSnapshot) renderControl(controlSnapshot);
  try {
    const response = await fetch("/api/control", {
      method: "POST",
      headers: apiHeaders({"Content-Type": "application/json", "X-Wesnoth-CSRF": controlToken}),
      body: JSON.stringify(payload),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "Control request rejected");
    if (result.shutdown === "accepted") {
      shutdownAccepted = true;
      $("exit-button").textContent = "Shutting down…";
      $("exit-button").disabled = true;
      $("dashboard-action-status").textContent = "Dashboard stopped cleanly. Closing its launcher console.";
    } else {
      renderControl(result);
    }
  } catch (error) {
    errorMessage = error.message;
  } finally {
    controlBusy = false;
    if (controlSnapshot && !shutdownAccepted) renderControl(controlSnapshot);
    if (errorMessage) {
      $("control-state").textContent = "Control request rejected";
      $("control-summary").textContent = errorMessage;
      $("control-state-dot").className = "error";
    }
  }
}

document.querySelectorAll('input[name="mode"]').forEach(input => {
  input.addEventListener("change", () => controlAction({action: "set_mode", mode: input.value}));
});

$("automation-toggle").addEventListener("change", event => {
  controlAction({action: "set_automation", enabled: event.target.checked, brief: $("coordination-brief").value});
});

$("planned-ticket").addEventListener("change", event => {
  const brief = plannedTickets.get(event.target.value);
  if (!brief) return;
  $("coordination-brief").value = brief;
  $("coordination-brief").focus();
  $("planned-ticket-status").textContent = "Planned ticket brief loaded. You can edit it before handoff.";
});

$("approval-queue").addEventListener("click", event => {
  const button = event.target.closest(".publish-button, .publish-batch-button, .recode-button, .delete-stale-button");
  if (!button) return;
  if (button.classList.contains("publish-batch-button")) {
    controlAction({action: "approve_publish_batch", batch_id: button.dataset.batchId});
    return;
  }
  let action = "approve_publish";
  if (button.classList.contains("recode-button")) action = "recode_ticket";
  if (button.classList.contains("delete-stale-button")) {
    const shortCommit = (button.dataset.commitSha || "").slice(0, 12);
    const confirmed = window.confirm(
      `Permanently delete only the clean local worktree and branch for ${button.dataset.ticketId}?\n\nBranch: ${button.dataset.branch}\nCommit: ${shortCommit}\n\nThis removes the card but retains a non-secret audit event. It will be refused if the branch is dirty, remote, in a pull request, mismatched, or needed by another ticket.`
    );
    if (!confirmed) return;
    action = "delete_stale_ticket";
  }
  controlAction({action, record_id: button.dataset.recordId, commit_sha: button.dataset.commitSha});
});

$("activity-log").addEventListener("click", event => {
  const button = event.target.closest(".error-activity");
  if (!button) return;
  $("error-dialog-message").textContent = button.dataset.message;
  $("error-dialog-detail").textContent = button.dataset.detail;
  $("error-dialog-action").textContent = button.dataset.action;
  $("error-dialog").showModal();
});

$("mode-form").addEventListener("submit", event => {
  event.preventDefault();
  controlAction({action: "run", brief: $("coordination-brief").value});
});

$("copy-lan-button").addEventListener("click", async event => {
  const url = event.currentTarget.dataset.url;
  if (!url) return;
  try {
    await navigator.clipboard.writeText(url);
    $("dashboard-action-status").textContent = "Secure device link copied. Open it only on a trusted device on this LAN.";
  } catch (_) {
    $("dashboard-action-status").textContent = "Copy failed. Open the network-address link and copy it from the address bar.";
  }
});

$("exit-button").addEventListener("click", () => {
  if (!confirm("Shut down this dashboard and close only its associated launcher console?")) return;
  controlAction({action: "shutdown"});
});

loadPlannedTickets();
refresh();
setInterval(refresh, 1500);
setInterval(updateElapsed, 1000);
