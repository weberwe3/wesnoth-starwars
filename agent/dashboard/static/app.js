const roles = {coordinator: "⌁", implementer: "⚒", "fast-fix": "ϟ", validation: "✓", tester: "◫", reviewer: "◇", "reviewer-fallback": "↳"};

const $ = (id) => document.getElementById(id);
let snapshot = null;
let controlSnapshot = null;
let controlToken = null;
let controlBusy = false;

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
  $("routing-list").innerHTML = (data.routing_history || []).slice(-6).reverse().map(r => `<li><time>${clock(r.at)}</time><span class="event-route">${esc(r.from)} → ${esc(r.to)}</span><br>${esc(r.message)}</li>`).join("") || '<li class="empty">No handoffs recorded</li>';
  $("event-list").innerHTML = (data.events || []).slice(-10).reverse().map(e => `<li class="${e.level === "error" ? "error" : ""}"><time>${clock(e.at)}</time>${e.source ? `<span class="event-route">${esc(e.source)}${e.target ? ` → ${esc(e.target)}` : ""}</span><br>` : ""}${esc(e.message)}</li>`).join("");
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
      fetch("/api/status", {cache: "no-store"}),
      fetch("/api/control", {cache: "no-store"}),
    ]);
    if (!statusResponse.ok || !controlResponse.ok) throw new Error("Status unavailable");
    const control = await controlResponse.json();
    controlToken = control.csrf_token;
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
  const running = ["planning", "executing"].includes(control.run?.state);
  const bridgeOnline = control.capabilities?.secure_bridge_online;
  $("coordination-brief").disabled = !autonomous || running || controlBusy;
  $("handoff-button").disabled = !autonomous || !bridgeOnline || running || controlBusy;
  $("handoff-button").textContent = running
    ? (control.run.state === "planning" ? "Sol is planning…" : "Ticket gates running…")
    : "Hand off one ticket";
  $("control-state").textContent = `${control.assignment?.label || "Coordinator"} · ${displayState(control.run?.state)}`;
  $("control-summary").textContent = autonomous && !bridgeOnline
    ? "Secure bridge offline — restart with the Windows launcher"
    : control.run?.error || control.run?.summary || "Ready";
  $("control-state-dot").className = running ? "active" : control.run?.state === "failed" ? "error" : "";
}

async function controlAction(payload) {
  if (!controlToken || controlBusy) return;
  controlBusy = true;
  let errorMessage = null;
  if (controlSnapshot) renderControl(controlSnapshot);
  try {
    const response = await fetch("/api/control", {
      method: "POST",
      headers: {"Content-Type": "application/json", "X-Wesnoth-CSRF": controlToken},
      body: JSON.stringify(payload),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "Control request rejected");
    renderControl(result);
  } catch (error) {
    errorMessage = error.message;
  } finally {
    controlBusy = false;
    if (controlSnapshot) renderControl(controlSnapshot);
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

$("mode-form").addEventListener("submit", event => {
  event.preventDefault();
  controlAction({action: "run", brief: $("coordination-brief").value});
});

refresh();
setInterval(refresh, 1500);
setInterval(updateElapsed, 1000);
