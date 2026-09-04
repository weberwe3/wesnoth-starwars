#!/usr/bin/env bash
set -u

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
runtime_dir="$project_root/agent/runtime"
pid_file="$runtime_dir/dashboard.pid"
commit_file="$runtime_dir/dashboard.commit"
session_file="$runtime_dir/dashboard.session"
lan_token_file="$runtime_dir/dashboard-lan-token"
log_file="$runtime_dir/dashboard.log"
port="${WESNOTH_DASHBOARD_PORT:-8765}"
lan_url="${WESNOTH_DASHBOARD_LAN_URL:-}"
session_id="${WESNOTH_DASHBOARD_SESSION_ID:-}"
current_commit="$(git -C "$project_root" rev-parse HEAD 2>/dev/null || printf 'unknown')"

if [[ -n "$lan_url" ]] && [[ ! "$lan_url" =~ ^http://[0-9.]+:[0-9]+$ ]]; then
    printf 'Invalid LAN dashboard URL.\n' >&2
    exit 1
fi
if [[ -n "$session_id" ]] && [[ ! "$session_id" =~ ^[A-Za-z0-9-]{8,80}$ ]]; then
    printf 'Invalid dashboard session identifier.\n' >&2
    exit 1
fi

mkdir -p "$runtime_dir"
chmod 700 "$runtime_dir"

if [[ -f "$pid_file" ]]; then
    current_pid="$(<"$pid_file")"
    if [[ "$current_pid" =~ ^[0-9]+$ ]] && kill -0 "$current_pid" 2>/dev/null; then
        command_line="$(tr '\0' ' ' <"/proc/$current_pid/cmdline" 2>/dev/null || true)"
        running_commit="$(cat "$commit_file" 2>/dev/null || true)"
        running_session="$(cat "$session_file" 2>/dev/null || true)"
        if [[ "$command_line" == *"$project_root/agent/dashboard/server.py"* ]]; then
            if [[ "$running_commit" == "$current_commit" ]] && {
                [[ -z "$session_id" ]] || [[ "$running_session" == "$session_id" ]];
            }; then
                printf 'Wesnoth Agent Manager already running: http://127.0.0.1:%s\n' "$port"
                exit 0
            fi
            control_state="$(python3 - "$runtime_dir/coordination-control.json" <<'PY'
import json
import sys
try:
    value = json.load(open(sys.argv[1], encoding="utf-8"))
    print(value.get("run", {}).get("state", "idle"))
except (FileNotFoundError, OSError, ValueError):
    print("idle")
PY
)"
            if [[ "$control_state" =~ ^(planning|executing|publishing)$ ]]; then
                printf 'Dashboard update pending; active %s operation was not interrupted.\n' "$control_state" >&2
                exit 1
            fi
            kill "$current_pid"
            for _ in {1..20}; do
                kill -0 "$current_pid" 2>/dev/null || break
                sleep .1
            done
            if kill -0 "$current_pid" 2>/dev/null; then
                printf 'Existing dashboard did not stop cleanly; restart aborted.\n' >&2
                exit 1
            fi
        fi
    fi
    rm -f "$pid_file" "$commit_file" "$session_file"
fi

if [[ -n "$lan_url" && ! -s "$lan_token_file" ]]; then
    umask 077
    python3 -c 'import secrets; print(secrets.token_urlsafe(32))' >"$lan_token_file"
fi
if [[ -n "$session_id" ]]; then
    rm -f "$runtime_dir/dashboard.shutdown.$session_id"
fi

server_args=("$project_root/agent/dashboard/server.py" --port "$port")
if [[ -n "$lan_url" ]]; then
    server_args+=(--lan-url "$lan_url" --lan-token-file "$lan_token_file")
fi
if [[ -n "$session_id" ]]; then
    server_args+=(--session-id "$session_id")
fi
nohup python3 "${server_args[@]}" \
    </dev/null >"$log_file" 2>&1 &
dashboard_pid=$!
printf '%s\n' "$dashboard_pid" >"$pid_file"
printf '%s\n' "$current_commit" >"$commit_file"
printf '%s\n' "$session_id" >"$session_file"
chmod 600 "$pid_file" "$commit_file" "$session_file" "$log_file"
[[ ! -e "$lan_token_file" ]] || chmod 600 "$lan_token_file"

dashboard_ready=0
for _ in {1..50}; do
    if python3 - "$port" <<'PY'
import json
import sys
import urllib.request

try:
    with urllib.request.urlopen(
        f"http://127.0.0.1:{sys.argv[1]}/healthz", timeout=0.25
    ) as response:
        value = json.load(response)
    raise SystemExit(
        0 if value.get("ok") is True and value.get("bind") == "127.0.0.1" else 1
    )
except (OSError, ValueError):
    raise SystemExit(1)
PY
    then
        dashboard_ready=1
        break
    fi
    kill -0 "$dashboard_pid" 2>/dev/null || break
    sleep .1
done
if [[ "$dashboard_ready" != 1 ]]; then
    printf 'Wesnoth Agent Manager failed to become ready; see %s\n' "$log_file" >&2
    kill "$dashboard_pid" 2>/dev/null || true
    for _ in {1..20}; do
        kill -0 "$dashboard_pid" 2>/dev/null || break
        sleep .1
    done
    rm -f "$pid_file" "$commit_file" "$session_file"
    exit 1
fi
printf 'Wesnoth Agent Manager started: http://127.0.0.1:%s\n' "$port"
