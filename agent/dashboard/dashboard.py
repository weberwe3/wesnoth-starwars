#!/usr/bin/env python3
from __future__ import annotations

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
import subprocess
import threading
import time
import webbrowser

ROOT = Path(__file__).resolve().parents[2]
STATE_PATH = ROOT / "agent/logs/dashboard-state.json"

ROLE_FILES = {
    "implementer": ".opencode/agents/implementer.md",
    "fast-fix": ".opencode/agents/fast-fix.md",
    "tester": ".opencode/agents/tester.md",
    "reviewer": ".opencode/agents/reviewer.md",
    "reviewer-fallback": ".opencode/agents/reviewer-fallback.md",
}


def provider_name(model: str) -> str:
    prefix = model.split("/", 1)[0].lower()
    return {
        "groq": "Groq",
        "opencode": "OpenCode",
        "google": "Google",
        "cloudflare-workers-ai": "Cloudflare Workers AI",
    }.get(prefix, prefix.title() if prefix else "Unknown")


def model_for(role: str) -> str:
    rel = ROLE_FILES.get(role)
    if not rel:
        return "Deterministic Python"
    try:
        text = (ROOT / rel).read_text(encoding="utf-8")
    except OSError:
        return "Unknown"
    match = re.search(r"(?m)^model:\s*(\S+)\s*$", text)
    return match.group(1) if match else "Unknown"


def default_state() -> dict:
    now = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    labels = {
        "coordinator": "Coordinator",
        "implementer": "Implementer",
        "fast-fix": "Fast-Fix",
        "validation": "Deterministic Validation",
        "tester": "Tester",
        "reviewer": "Reviewer",
        "reviewer-fallback": "Reviewer Fallback",
    }
    workers = {}
    for role, label in labels.items():
        model = model_for(role)
        workers[role] = {
            "role": label,
            "kind": "system" if role in ("coordinator", "validation") else "llm",
            "model": model,
            "provider": "Local" if role in ("coordinator", "validation") else provider_name(model),
            "state": "idle",
            "task": "Standing by",
            "since": now,
            "error": None,
        }
    return {
        "schema_version": 1,
        "updated_at": now,
        "ticket": None,
        "workers": workers,
        "active_transfer": None,
        "events": [],
        "latest_error": None,
        "final_verdict": None,
    }


def read_state() -> dict:
    try:
        state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        if not isinstance(state, dict):
            raise ValueError
    except Exception:
        state = default_state()

    workers = state.setdefault("workers", {})
    for role in ROLE_FILES:
        model = model_for(role)
        worker = workers.setdefault(role, {})
        worker["model"] = model
        worker["provider"] = provider_name(model)
        worker["kind"] = "llm"
    return state


HTML = r'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Wesnoth Agent Operations</title>
<style>
:root{color-scheme:dark;--bg:#091017;--panel:#111b24;--panel2:#16232e;--border:#273846;--text:#edf4f8;--muted:#91a4b4;--subtle:#667b8c;--cyan:#5cc9d9;--green:#42d89d;--amber:#e8b55f;--red:#ff7080;--shadow:0 24px 60px rgba(0,0,0,.28)}
*{box-sizing:border-box}html,body{margin:0;min-height:100%;background:radial-gradient(circle at 10% 0%,rgba(92,201,217,.08),transparent 28rem),radial-gradient(circle at 90% 8%,rgba(105,145,255,.06),transparent 32rem),var(--bg);color:var(--text);font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}body{min-height:100vh}.shell{width:min(1600px,calc(100% - 36px));margin:auto;padding:24px 0 40px}header{display:flex;justify-content:space-between;align-items:flex-end;gap:18px;margin-bottom:16px}.eyebrow{font-size:10px;font-weight:850;letter-spacing:.18em;text-transform:uppercase;color:var(--cyan)}h1{font-size:clamp(28px,3vw,42px);line-height:1.05;letter-spacing:-.035em;margin:6px 0 0}.header-meta{text-align:right;color:var(--muted);font-size:12px;line-height:1.5}.live-dot{display:inline-block;width:8px;height:8px;border-radius:50%;background:var(--green);box-shadow:0 0 0 5px rgba(66,216,157,.08),0 0 18px rgba(66,216,157,.5);margin-right:8px}.health{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:10px;margin-bottom:14px}.health-card,.panel{background:linear-gradient(180deg,rgba(21,34,45,.97),rgba(14,23,31,.97));border:1px solid rgba(76,99,117,.5);box-shadow:var(--shadow)}.health-card{border-radius:14px;padding:13px 15px;min-height:72px}.h-label{font-size:9px;letter-spacing:.14em;text-transform:uppercase;color:var(--subtle);font-weight:850}.h-value{font-size:14px;font-weight:800;margin-top:7px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.layout{display:grid;grid-template-columns:minmax(0,1.35fr) minmax(340px,.65fr);gap:14px;align-items:start}.panel{border-radius:18px;overflow:hidden}.panel-head{display:flex;justify-content:space-between;gap:12px;align-items:center;padding:17px 19px;border-bottom:1px solid rgba(68,89,105,.45)}.panel-title{font-weight:820;letter-spacing:-.015em}.panel-sub{font-size:11px;color:var(--muted);margin-top:2px}.flow-body{position:relative;padding:22px 24px 28px;min-height:850px}.flow-stack{position:relative;z-index:2;display:flex;flex-direction:column;align-items:center;gap:34px}.worker-row{display:flex;justify-content:center;gap:18px;width:100%}.worker{width:min(520px,86%);border:1px solid var(--border);background:linear-gradient(145deg,rgba(24,37,49,.98),rgba(14,23,31,.98));border-radius:16px;padding:15px 17px;transition:.2s ease;position:relative}.worker.dual{width:min(360px,44%)}.worker[data-state="idle"]{opacity:.6}.worker[data-state="working"]{opacity:1;border-color:rgba(66,216,157,.72);box-shadow:0 0 0 1px rgba(66,216,157,.12),0 0 32px rgba(66,216,157,.13)}.worker[data-state="waiting"]{opacity:.9;border-color:rgba(232,181,95,.55)}.worker[data-state="error"]{opacity:1;border-color:rgba(255,112,128,.72);box-shadow:0 0 26px rgba(255,112,128,.1)}.worker-top{display:flex;gap:12px;align-items:center}.icon{width:42px;height:42px;border-radius:12px;display:grid;place-items:center;flex:0 0 auto;background:rgba(92,201,217,.08);border:1px solid rgba(92,201,217,.16);color:var(--cyan);font-weight:900;font-size:17px}.w-main{min-width:0;flex:1}.role-line{display:flex;align-items:center;gap:8px}.role{font-size:15px;font-weight:850}.light{width:8px;height:8px;border-radius:50%;background:#617484}.worker[data-state="working"] .light{background:var(--green);animation:pulse 1.8s ease-in-out infinite}.worker[data-state="waiting"] .light{background:var(--amber)}.worker[data-state="error"] .light{background:var(--red);box-shadow:0 0 12px rgba(255,112,128,.55)}.state{font-size:9px;letter-spacing:.12em;text-transform:uppercase;color:var(--muted);font-weight:850}.model{font-size:12px;color:#cbd8df;margin-top:3px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.provider{font-size:10px;color:var(--subtle)}.task{font-size:12px;line-height:1.4;color:#d9e4ea;border-top:1px solid rgba(60,80,95,.42);padding-top:11px;margin-top:11px}.worker-meta{display:flex;justify-content:space-between;gap:10px;margin-top:8px;color:var(--subtle);font-size:10px}.error-text{font-size:10px;line-height:1.35;color:#ff9ba7;margin-top:7px}.flow-svg{position:absolute;inset:0;width:100%;height:100%;z-index:1;pointer-events:none}.path{fill:none;stroke:rgba(78,106,126,.45);stroke-width:2}.path.active{stroke:rgba(66,216,157,.72);filter:drop-shadow(0 0 5px rgba(66,216,157,.42))}.packet{fill:var(--green);filter:drop-shadow(0 0 6px rgba(66,216,157,.8))}.side{display:flex;flex-direction:column;gap:14px}.ticket{padding:18px 19px}.ticket-id{font-size:20px;font-weight:860;letter-spacing:-.02em}.ticket-objective{font-size:12px;color:#c9d7df;line-height:1.48;margin-top:8px}.kv{display:grid;grid-template-columns:84px minmax(0,1fr);gap:7px 10px;margin-top:14px;font-size:11px}.kv div:nth-child(odd){color:var(--subtle)}.kv div:nth-child(even){color:#dbe5ea;overflow:hidden;text-overflow:ellipsis}.assignments{padding:8px 11px 12px}.assignment{display:grid;grid-template-columns:110px minmax(0,1fr);gap:10px;padding:9px 7px;border-bottom:1px solid rgba(54,73,88,.36)}.assignment:last-child{border-bottom:0}.a-role{font-size:10px;font-weight:800;color:var(--muted)}.a-model{font-size:10px;color:#dce6eb;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.a-provider{font-size:9px;color:var(--subtle);margin-top:2px}.feed{max-height:430px;overflow:auto;padding:8px 10px 13px}.event{display:grid;grid-template-columns:72px 9px minmax(0,1fr);gap:8px;padding:9px 7px;border-bottom:1px solid rgba(54,73,88,.32)}.event:last-child{border-bottom:0}.e-time{font:9px ui-monospace,SFMono-Regular,Menlo,monospace;color:var(--subtle)}.e-dot{width:7px;height:7px;border-radius:50%;background:var(--cyan);margin-top:3px}.event.error .e-dot{background:var(--red)}.event.error .e-msg{color:#ffadb7}.e-msg{font-size:10px;line-height:1.42;color:#cbd8df}.e-route{font-size:9px;color:var(--subtle);margin-top:3px}.empty{padding:20px;color:var(--subtle);font-size:11px}.badge{font-size:9px;letter-spacing:.12em;text-transform:uppercase;color:var(--cyan);font-weight:850}@keyframes pulse{0%,100%{box-shadow:0 0 0 0 rgba(66,216,157,.36),0 0 12px rgba(66,216,157,.65)}50%{box-shadow:0 0 0 8px rgba(66,216,157,0),0 0 22px rgba(66,216,157,.75)}}@media(max-width:1100px){.layout{grid-template-columns:1fr}.side{display:grid;grid-template-columns:1fr 1fr}.side .panel:last-child{grid-column:1/-1}.flow-body{min-height:820px}}@media(max-width:780px){.shell{width:min(100% - 20px,1600px);padding-top:18px}header{align-items:flex-start;flex-direction:column}.header-meta{text-align:left}.health{grid-template-columns:1fr 1fr}.health-card:last-child{grid-column:1/-1}.side{display:flex}.flow-body{padding:18px 10px;min-height:1050px}.worker-row{flex-direction:column;align-items:center}.worker,.worker.dual{width:min(94%,520px)}.flow-stack{gap:29px}}@media(max-width:520px){.health{grid-template-columns:1fr}.health-card:last-child{grid-column:auto}.worker{padding:13px}.icon{width:38px;height:38px}.role{font-size:14px}.flow-body{min-height:1090px}}@media(prefers-reduced-motion:reduce){*,*:before,*:after{animation-duration:.001ms!important;animation-iteration-count:1!important}}
</style>
</head>
<body>
<div class="shell">
<header><div><div class="eyebrow">KillDozer · Local Agent Control</div><h1>Wesnoth Agent Operations</h1></div><div class="header-meta"><span class="live-dot"></span><span id="connection">Live telemetry</span><br><span id="updated">Waiting for status…</span></div></header>
<section class="health"><div class="health-card"><div class="h-label">Current Ticket</div><div class="h-value" id="h-ticket">No active ticket</div></div><div class="health-card"><div class="h-label">Pipeline Stage</div><div class="h-value" id="h-stage">Idle</div></div><div class="health-card"><div class="h-label">Active LLM</div><div class="h-value" id="h-model">None</div></div><div class="health-card"><div class="h-label">Branch</div><div class="h-value" id="h-branch">main</div></div><div class="health-card"><div class="h-label">Health</div><div class="h-value" id="h-health">Nominal</div></div></section>
<main class="layout">
<section class="panel"><div class="panel-head"><div><div class="panel-title">Live Worker Architecture</div><div class="panel-sub">Role state, LLM assignment, and directional handoffs</div></div><div class="badge" id="flow-label">Standby</div></div><div class="flow-body" id="flow-body"><svg class="flow-svg" id="flow-svg" aria-hidden="true"></svg><div class="flow-stack"><div class="worker-row"><div class="worker" data-role="coordinator"></div></div><div class="worker-row"><div class="worker dual" data-role="implementer"></div><div class="worker dual" data-role="fast-fix"></div></div><div class="worker-row"><div class="worker" data-role="validation"></div></div><div class="worker-row"><div class="worker" data-role="tester"></div></div><div class="worker-row"><div class="worker" data-role="reviewer"></div></div><div class="worker-row"><div class="worker" data-role="reviewer-fallback"></div></div></div></div></section>
<aside class="side"><section class="panel"><div class="panel-head"><div><div class="panel-title">Current Job</div><div class="panel-sub">Execution context</div></div></div><div class="ticket" id="ticket-panel"></div></section><section class="panel"><div class="panel-head"><div><div class="panel-title">Model Assignment</div><div class="panel-sub">LLM currently serving each role</div></div></div><div class="assignments" id="assignments"></div></section><section class="panel"><div class="panel-head"><div><div class="panel-title">Activity & Errors</div><div class="panel-sub">Newest events first</div></div></div><div class="feed" id="feed"></div></section></aside>
</main></div>
<script>
const ROLES=["coordinator","implementer","fast-fix","validation","tester","reviewer","reviewer-fallback"],EDGES=[["coordinator","implementer"],["coordinator","fast-fix"],["implementer","validation"],["fast-fix","validation"],["validation","tester"],["tester","reviewer"],["reviewer","reviewer-fallback"]],ICONS={"coordinator":"◈","implementer":"⚙","fast-fix":"ϟ","validation":"✓","tester":"◇","reviewer":"◎","reviewer-fallback":"↺"};let last=null;function esc(v){return String(v??"").replace(/[&<>\"']/g,m=>({"&":"&amp;","<":"&lt;",">":"&gt;",'\"':"&quot;","'":"&#39;"}[m]))}function tm(i){if(!i)return"—";let d=new Date(i);return isNaN(d)?i:d.toLocaleTimeString([],{hour:"2-digit",minute:"2-digit",second:"2-digit"})}function elapsed(i){if(!i)return"—";let s=Math.max(0,Math.floor((Date.now()-new Date(i))/1000)),m=Math.floor(s/60),h=Math.floor(m/60);s%=60;m%=60;return h?`${h}h ${m}m`:m?`${m}m ${s}s`:`${s}s`}function renderWorker(r,w){let e=document.querySelector(`[data-role="${r}"]`);if(!e)return;let st=w?.state||"idle";e.dataset.state=st;e.innerHTML=`<div class="worker-top"><div class="icon">${ICONS[r]}</div><div class="w-main"><div class="role-line"><span class="role">${esc(w?.role||r)}</span><span class="light"></span><span class="state">${esc(st.toUpperCase())}</span></div><div class="model">${esc(w?.model||"Unknown")}</div><div class="provider">${esc(w?.provider||"Unknown")}</div></div></div><div class="task">${esc(w?.task||"Standing by")}</div><div class="worker-meta"><span>${esc(w?.kind==="llm"?"LLM worker":"Local system")}</span><span>${esc(elapsed(w?.since))}</span></div>${w?.error?`<div class="error-text">${esc(w.error)}</div>`:""}`}
function render(s){last=s;let w=s.workers||{};ROLES.forEach(r=>renderWorker(r,w[r]));let t=s.ticket,a=ROLES.find(r=>w[r]?.state==="working");document.getElementById("h-ticket").textContent=t?.id||"No active ticket";document.getElementById("h-stage").textContent=a?(w[a]?.role||a):"Idle";document.getElementById("h-model").textContent=a&&w[a]?.kind==="llm"?(w[a]?.model||"Unknown"):"None";document.getElementById("h-branch").textContent=t?.branch||"main";document.getElementById("h-health").textContent=s.latest_error&&t?.status!=="complete"?"Attention":"Nominal";document.getElementById("updated").textContent=`Updated ${tm(s.updated_at)}`;let tr=s.active_transfer;document.getElementById("flow-label").textContent=tr?`${tr.from} → ${tr.to}`:(s.final_verdict||"Standby");let p=document.getElementById("ticket-panel");p.innerHTML=t?`<div class="ticket-id">${esc(t.id)}</div><div class="ticket-objective">${esc(t.objective||"")}</div><div class="kv"><div>Status</div><div>${esc((t.status||"running").toUpperCase())}</div><div>Worker</div><div>${esc(t.worker||"—")}</div><div>Validation</div><div>${esc(t.validation_profile||"—")}</div><div>Runtime</div><div>${esc(elapsed(t.started_at))}</div><div>Branch</div><div>${esc(t.branch||"pending")}</div><div>Worktree</div><div title="${esc(t.worktree||"")}">${esc(t.worktree||"pending")}</div></div>`:`<div class="empty">No ticket is currently running. Worker assignments remain visible and the dashboard is ready.</div>`;document.getElementById("assignments").innerHTML=ROLES.filter(r=>w[r]?.kind==="llm").map(r=>`<div class="assignment"><div class="a-role">${esc(w[r]?.role||r)}</div><div><div class="a-model">${esc(w[r]?.model||"Unknown")}</div><div class="a-provider">${esc(w[r]?.provider||"Unknown")}</div></div></div>`).join("");let ev=[...(s.events||[])].reverse().slice(0,40);document.getElementById("feed").innerHTML=ev.length?ev.map(x=>`<div class="event ${x.level==="error"?"error":""}"><div class="e-time">${esc(tm(x.time))}</div><div class="e-dot"></div><div><div class="e-msg">${esc(x.message)}</div>${x.from||x.to?`<div class="e-route">${esc(x.from||"system")}${x.to?` → ${esc(x.to)}`:""}</div>`:""}</div></div>`).join(""):`<div class="empty">No activity has been recorded yet.</div>`;draw()}
function c(e,b){let a=e.getBoundingClientRect(),z=b.getBoundingClientRect();return{x:a.left-z.left+a.width/2,top:a.top-z.top,bottom:a.bottom-z.top}}function draw(){let b=document.getElementById("flow-body"),svg=document.getElementById("flow-svg"),tr=last?.active_transfer||{},out=[];svg.setAttribute("viewBox",`0 0 ${b.clientWidth} ${b.clientHeight}`);EDGES.forEach(([a,d],i)=>{let A=document.querySelector(`[data-role="${a}"]`),B=document.querySelector(`[data-role="${d}"]`);if(!A||!B)return;let p=c(A,b),q=c(B,b),m=(p.bottom+q.top)/2,path=`M ${p.x} ${p.bottom} C ${p.x} ${m}, ${q.x} ${m}, ${q.x} ${q.top}`,active=tr.from===a&&tr.to===d,id=`edge${i}`;out.push(`<path id="${id}" class="path ${active?"active":""}" d="${path}"/>`);if(active)for(let n=0;n<3;n++)out.push(`<circle class="packet" r="3.5"><animateMotion dur="1.35s" begin="${n*.36}s" repeatCount="indefinite"><mpath href="#${id}"/></animateMotion></circle>`)});svg.innerHTML=out.join("")}
async function poll(){try{let r=await fetch("/api/status",{cache:"no-store"});if(!r.ok)throw Error();render(await r.json());document.getElementById("connection").textContent="Live telemetry"}catch{document.getElementById("connection").textContent="Telemetry unavailable"}}new ResizeObserver(draw).observe(document.getElementById("flow-body"));poll();setInterval(poll,900);setInterval(()=>{if(last)render(last)},1000);
</script>
</body></html>'''


class Handler(BaseHTTPRequestHandler):
    server_version = "WesnothAgentDashboard/0.1"

    def send_payload(self, status: int, content_type: str, payload: bytes) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; "
            "connect-src 'self'; img-src 'self' data:; frame-ancestors 'none'",
        )
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self) -> None:
        if self.path in ("/", "/index.html"):
            self.send_payload(200, "text/html; charset=utf-8", HTML.encode("utf-8"))
            return
        if self.path == "/api/status":
            payload = (json.dumps(read_state(), ensure_ascii=False) + "\n").encode("utf-8")
            self.send_payload(200, "application/json; charset=utf-8", payload)
            return
        if self.path == "/health":
            self.send_payload(200, "text/plain; charset=utf-8", b"ok\n")
            return
        self.send_payload(404, "text/plain; charset=utf-8", b"not found\n")

    def log_message(self, fmt: str, *args) -> None:
        if self.path != "/api/status":
            super().log_message(fmt, *args)


def open_browser(url: str) -> None:
    time.sleep(0.8)
    for command in (
        ["powershell.exe", "-NoProfile", "-Command", "Start-Process", url],
        ["cmd.exe", "/c", "start", "", url],
    ):
        try:
            subprocess.run(
                command,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
                timeout=4,
            )
            return
        except (OSError, subprocess.TimeoutExpired):
            pass
    webbrowser.open(url)


def main() -> int:
    parser = argparse.ArgumentParser(description="Local Wesnoth agent operations dashboard")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--open", action="store_true")
    args = parser.parse_args()

    if args.host not in ("127.0.0.1", "localhost"):
        raise SystemExit("Refusing non-local bind. Use 127.0.0.1 or localhost.")

    url = f"http://127.0.0.1:{args.port}"
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    server.daemon_threads = True

    if args.open:
        threading.Thread(target=open_browser, args=(url,), daemon=True).start()

    print(f"Wesnoth Agent Operations dashboard: {url}")
    print(f"Telemetry: {STATE_PATH}")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        print("\nDashboard stopped.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
