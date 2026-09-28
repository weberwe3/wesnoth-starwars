#!/usr/bin/env python3

"""DASH-001 localhost operations dashboard server (MVP).

Serves a responsive single-page dashboard for the Wesnoth multi-agent
pipeline, backed by the secret-free JSONL telemetry written by
``dashboard_telemetry.py``.

Security (per DASH-001):
- Binds only to 127.0.0.1; never 0.0.0.0.
- Serves telemetry only; no credentials, provider tokens, environment-variable
  values, or secret material are read or served. Telemetry payloads are
  sanitized at write time (see dashboard_telemetry.sanitize_payload).
- Read-only endpoints; no command execution.

Standard library only. Usage:
    python3 dashboard_server.py [--port 8765]
Then open http://127.0.0.1:8765 in a browser.
"""

from __future__ import annotations

import argparse
import html
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import dashboard_telemetry as telemetry

HOST = "127.0.0.1"
DEFAULT_PORT = 8765

# Pipeline order for the flowchart: (role, icon, label).
FLOW = (
    ("coordinator", "⚙", "Coordinator"),
    ("implementer", "🔧", "Implementer"),
    ("fast-fix", "⚡", "Fast-Fix"),
    ("deterministic-validation", "✔", "Deterministic Validation"),
    ("tester", "🧪", "Tester"),
    ("reviewer", "🔍", "Reviewer"),
    ("reviewer-fallback", "🔄", "Reviewer Fallback"),
)

PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Wesnoth Agent Operations</title>
<style>
:root{--bg:#0e1116;--card:#171c24;--dim:#5b6472;--green:#35d07f;--amber:#e0a63c;--red:#e5534b;--text:#dbe2ec}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--text);font:14px/1.45 system-ui,-apple-system,Segoe UI,Roboto,sans-serif;padding:16px}
h1{font-size:18px;margin:0 0 4px}
.sub{color:var(--dim);font-size:12px;margin-bottom:16px}
.flow{display:flex;flex-wrap:wrap;gap:8px;align-items:stretch;margin-bottom:16px}
.role{flex:1 1 140px;background:var(--card);border:1px solid #2a3240;border-radius:10px;padding:10px 12px;min-width:140px;position:relative;transition:border-color .3s}
.role .icon{font-size:20px}
.role .name{font-weight:600;margin:2px 0}
.role .meta{font-size:11px;color:var(--dim);word-break:break-word}
.role.idle{opacity:.55}
.role.active{border-color:var(--green);box-shadow:0 0 12px rgba(53,208,127,.25)}
.role.active .dot{animation:pulse 1.2s infinite}
.role.warning{border-color:var(--amber)}
.role.error{border-color:var(--red);box-shadow:0 0 12px rgba(229,83,75,.3)}
.dot{display:inline-block;width:8px;height:8px;border-radius:50%;background:var(--dim);margin-right:6px}
.role.active .dot{background:var(--green)}
.role.warning .dot{background:var(--amber)}
.role.error .dot{background:var(--red)}
.arrow{align-self:center;color:var(--dim);font-size:18px}
.arrow.hot{color:var(--accent);animation:hpulse 1s ease-in-out infinite}
@keyframes hpulse{50%{opacity:.25;transform:scale(1.3)}}
.panels{display:grid;grid-template-columns:1fr 1fr;gap:12px}
@media(max-width:800px){.panels{grid-template-columns:1fr}}
.panel{background:var(--card);border:1px solid #2a3240;border-radius:10px;padding:12px}
.panel h2{font-size:13px;margin:0 0 8px;color:var(--dim);text-transform:uppercase;letter-spacing:.06em}
#feed{list-style:none;margin:0;padding:0;max-height:320px;overflow-y:auto}
#feed li{padding:6px 8px;border-bottom:1px solid #232a36;font-size:12px}
#feed li.err{color:var(--red)}
#feed li.warn{color:var(--amber)}
#feed .ts{color:var(--dim);margin-right:8px}
#ticket{font-size:13px}
#ticket .tid{font-weight:700}
.stale{color:var(--amber);font-size:12px}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.35}}
</style>
</head>
<body>
<h1>Wesnoth Agent Operations</h1>
<div class="sub">localhost dashboard &middot; telemetry: <span id="count">0</span> events <span id="stale"></span></div>
<div class="flow" id="flow"></div>
<div class="panels">
  <div class="panel"><h2>Current ticket</h2><div id="ticket">No ticket activity yet.</div></div>
  <div class="panel"><h2>Model assignments</h2><div id="models">No activity yet.</div></div>
</div>
<div class="panel" style="margin-top:12px"><h2>Run history</h2><div id="history">No completed runs yet.</div></div>
<div class="panel" style="margin-top:12px"><h2>Activity / error feed <select id="rolefilter" style="font-size:12px;margin-left:8px"><option value="">All roles</option></select></h2><ul id="feed"></ul></div>
<script>
const FLOW=[["coordinator","\\u2699","Coordinator"],["implementer","\\uD83D\\uDD27","Implementer"],["fast-fix","\\u26a1","Fast-Fix"],["deterministic-validation","\\u2714","Deterministic Validation"],["tester","\\uD83E\\uDDEA","Tester"],["reviewer","\\uD83D\\uDD0D","Reviewer"],["reviewer-fallback","\\uD83D\\uDD04","Reviewer Fallback"],["reviewer-intermediate","\\uD83D\\uDD0E","Reviewer Intermediate"]];
const flowEl=document.getElementById("flow");
const roleFilter=document.getElementById("rolefilter");
FLOW.forEach(([role,,label])=>{const o=document.createElement("option");o.value=role;o.textContent=label;roleFilter.appendChild(o);});
let lastFeed=[];
function renderFeed(items){
  const feed=document.getElementById("feed");
  feed.innerHTML=items.map(e=>{
    const cls=e.type==="error"?"err":(e.payload&&e.payload.state==="warning"?"warn":"");
    return '<li class="'+cls+'"><span class="ts">'+esc(e.ts)+'</span><b>'+esc(e.role)+
      "</b> "+esc(e.type)+" "+esc(JSON.stringify(e.payload).slice(0,160))+"</li>";
  }).join("");
}
async function refreshFeed(){
  const role=roleFilter.value;
  if(!role){renderFeed(lastFeed);return;}
  try{
    const r=await fetch("/api/events?role="+encodeURIComponent(role)+"&limit=50");
    if(r.ok)renderFeed((await r.json()).slice().reverse());
  }catch(e){}
}
roleFilter.addEventListener("change",refreshFeed);
function esc(s){return String(s==null?"":s).replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]))}
function render(state){
  document.getElementById("count").textContent=state.event_count;
  const stale=document.getElementById("stale");
  stale.textContent=state.stale_s!=null?("· last event "+state.stale_s+"s ago"):"";
  stale.className=state.stale_s!=null&&state.stale_s>120?"stale":"";
  flowEl.innerHTML="";
  FLOW.forEach(([role,icon,label],i)=>{
    const r=state.roles[role]||{state:"idle"};
    const d=document.createElement("div");
    d.className="role "+(r.state||"idle");
    d.innerHTML='<span class="dot"></span><span class="icon">'+icon+'</span>'+
      '<div class="name">'+esc(label)+'</div>'+
      '<div class="meta">'+esc(r.state||"idle")+
      (r.task?'<br>task: '+esc(r.task):"")+
      (r.model?'<br>'+esc(r.model)+" · "+esc(r.provider):"")+
      (r.elapsed_s?'<br>'+esc(r.elapsed_s)+"s":"")+
      (r.detail?'<br>'+esc(r.detail):"")+'</div>';
    flowEl.appendChild(d);
    if(i<FLOW.length-1){const a=document.createElement("div");a.className="arrow";a.textContent="→";flowEl.appendChild(a);}
  });
  const lh=state.last_handoff;
  if(lh&&lh.age_s!=null&&lh.age_s<10){
    const fi=FLOW.findIndex(([role])=>role===lh.from);
    if(fi>=0&&fi<FLOW.length-1){
      const arrowEl=flowEl.children[2*fi+1];
      if(arrowEl&&arrowEl.classList.contains("arrow"))arrowEl.classList.add("hot");
    }
  }
  const t=state.ticket;
  document.getElementById("ticket").innerHTML=t?
    '<span class="tid">'+esc(t.ticket_id)+'</span> — '+esc(t.status)+
    (t.detail?'<br><span style="color:var(--dim)">'+esc(t.detail)+"</span>":"")+
    '<br><span style="color:var(--dim)">'+esc(t.ts)+"</span>":"No ticket activity yet.";
  const m=state.models;
  document.getElementById("models").innerHTML=Object.keys(m).length?
    Object.entries(m).map(([r,v])=>"<div><b>"+esc(r)+"</b>: "+esc(v)+"</div>").join(""):
    "No activity yet.";
  lastFeed=state.feed;
  refreshFeed();
  const h=state.history||{};
  document.getElementById("history").innerHTML=Object.keys(h).length?
    '<table style="font-size:12px;border-collapse:collapse">'+
    "<tr><th style='text-align:left;padding:4px 8px'>role</th><th style='padding:4px 8px'>runs</th><th style='padding:4px 8px'>errors</th><th style='padding:4px 8px'>avg s</th><th style='padding:4px 8px'>max s</th></tr>"+
    Object.entries(h).map(([r,v])=>"<tr><td style='padding:4px 8px'><b>"+esc(r)+"</b></td><td style='padding:4px 8px'>"+v.runs+"</td><td style='padding:4px 8px'>"+v.errors+"</td><td style='padding:4px 8px'>"+v.avg_s+"</td><td style='padding:4px 8px'>"+v.max_s+"</td></tr>").join("")+
    "</table>":"No completed runs yet.";
}
async function poll(){
  try{const r=await fetch("/api/state");if(r.ok)render(await r.json());}
  catch(e){}
  setTimeout(poll,2000);
}
poll();
</script>
</body>
</html>
"""


def filter_events(
    events: list[dict],
    role: str | None = None,
    etype: str | None = None,
) -> list[dict]:
    """Filter telemetry events by role and/or type (DASH-001 history filtering)."""
    result = events
    if role:
        result = [e for e in result if e.get("role") == role]
    if etype:
        result = [e for e in result if e.get("type") == etype]
    return result


def compute_history(events: list[dict]) -> dict[str, dict]:
    """Per-role run statistics from role_state telemetry (DASH-001 history).

    A "run" is a role_state event with state idle|warning|error carrying
    elapsed_s > 0. Returns {role: {runs, errors, avg_s, max_s}}.
    """
    stats: dict[str, dict] = {}
    for event in events:
        if event.get("type") != "role_state":
            continue
        payload = event.get("payload", {})
        state = payload.get("state")
        elapsed = payload.get("elapsed_s", 0) or 0
        if state not in ("idle", "warning", "error") or elapsed <= 0:
            continue
        role = event.get("role", "")
        entry = stats.setdefault(
            role, {"runs": 0, "errors": 0, "total_s": 0.0, "max_s": 0.0}
        )
        entry["runs"] += 1
        entry["total_s"] += elapsed
        entry["max_s"] = max(entry["max_s"], elapsed)
        if state == "error":
            entry["errors"] += 1
    return {
        role: {
            "runs": entry["runs"],
            "errors": entry["errors"],
            "avg_s": round(entry["total_s"] / entry["runs"], 1),
            "max_s": round(entry["max_s"], 1),
        }
        for role, entry in stats.items()
    }


def build_state() -> dict:
    """Aggregate the latest telemetry into dashboard state (secret-free)."""
    events = telemetry.read_events(limit=500)
    roles: dict[str, dict] = {}
    models: dict[str, str] = {}
    ticket = None
    feed: list[dict] = []
    now_ts = None
    for event in events:
        etype = event.get("type")
        role = event.get("role", "")
        payload = event.get("payload", {})
        if etype == "role_state":
            roles[role] = {
                "state": payload.get("state", "idle"),
                "task": payload.get("task", ""),
                "model": payload.get("model", ""),
                "provider": payload.get("provider", ""),
                "elapsed_s": payload.get("elapsed_s", 0),
                "detail": payload.get("detail", ""),
            }
            if payload.get("model"):
                models[role] = f"{payload['model']} ({payload.get('provider', '?')})"
        elif etype == "ticket":
            ticket = {
                "ticket_id": payload.get("ticket_id", ""),
                "status": payload.get("status", ""),
                "detail": payload.get("detail", ""),
                "ts": event.get("ts", ""),
            }
        if etype in ("error", "handoff", "ticket") or (
            etype == "role_state" and payload.get("state") in ("warning", "error")
        ):
            feed.append({
                "ts": event.get("ts", ""),
                "type": etype,
                "role": role,
                "payload": payload,
            })
    stale_s = None
    last_handoff = None
    if events:
        try:
            import datetime as dt

            last = dt.datetime.fromisoformat(events[-1]["ts"])
            now = dt.datetime.now(dt.timezone.utc)
            stale_s = int((now - last).total_seconds())
            for event in reversed(events):
                if event.get("type") == "handoff":
                    hts = dt.datetime.fromisoformat(event["ts"])
                    last_handoff = {
                        "from": event.get("role", ""),
                        "to": event.get("payload", {}).get("receiver", ""),
                        "age_s": int((now - hts).total_seconds()),
                    }
                    break
        except (ValueError, KeyError):
            pass
    return {
        "roles": roles,
        "models": models,
        "ticket": ticket,
        "feed": feed[-50:][::-1],
        "event_count": len(events),
        "stale_s": stale_s,
        "last_handoff": last_handoff,
        "history": compute_history(events),
    }


class Handler(BaseHTTPRequestHandler):
    server_version = "WesnothDash/1.0"

    def log_message(self, *args):  # quiet
        pass

    def _send(self, body: bytes, content_type: str) -> None:
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        if path == "/":
            self._send(PAGE.encode("utf-8"), "text/html; charset=utf-8")
        elif path == "/api/events":
            query = parse_qs(parsed.query)
            try:
                limit = int(query.get("limit", ["200"])[0])
            except (TypeError, ValueError):
                limit = 200
            events = filter_events(
                telemetry.read_events(limit=max(1, min(limit, 1000))),
                role=query.get("role", [None])[0],
                etype=query.get("type", [None])[0],
            )
            body = json.dumps(events).encode()
            self._send(body, "application/json")
        elif path == "/api/state":
            body = json.dumps(build_state()).encode()
            self._send(body, "application/json")
        else:
            self.send_response(404)
            self.end_headers()


def run(port: int = DEFAULT_PORT) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer((HOST, port), Handler)
    return server


def main() -> int:
    parser = argparse.ArgumentParser(description="DASH-001 localhost dashboard")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = parser.parse_args()
    server = run(args.port)
    bound = server.server_address
    assert bound[0] == HOST, f"refusing to bind non-localhost: {bound[0]}"
    print(f"Dashboard on http://{HOST}:{bound[1]} (localhost only)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
