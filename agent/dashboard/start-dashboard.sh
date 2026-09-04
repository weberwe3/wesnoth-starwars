#!/usr/bin/env bash
set -u

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
runtime_dir="$project_root/agent/runtime"
pid_file="$runtime_dir/dashboard.pid"
log_file="$runtime_dir/dashboard.log"
port="${WESNOTH_DASHBOARD_PORT:-8765}"

mkdir -p "$runtime_dir"
chmod 700 "$runtime_dir"

if [[ -f "$pid_file" ]]; then
    current_pid="$(<"$pid_file")"
    if [[ "$current_pid" =~ ^[0-9]+$ ]] && kill -0 "$current_pid" 2>/dev/null; then
        printf 'Wesnoth Agent Manager already running: http://127.0.0.1:%s\n' "$port"
        exit 0
    fi
    rm -f "$pid_file"
fi

nohup python3 "$project_root/agent/dashboard/server.py" --port "$port" \
    </dev/null >"$log_file" 2>&1 &
dashboard_pid=$!
printf '%s\n' "$dashboard_pid" >"$pid_file"
chmod 600 "$pid_file" "$log_file"
printf 'Wesnoth Agent Manager started: http://127.0.0.1:%s\n' "$port"

