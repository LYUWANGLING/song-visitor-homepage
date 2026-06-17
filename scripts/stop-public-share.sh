#!/bin/zsh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
RUNTIME_DIR="$ROOT_DIR/.runtime/share"
SERVER_PID_FILE="$RUNTIME_DIR/server.pid"
TUNNEL_PID_FILE="$RUNTIME_DIR/tunnel.pid"

stop_pid_file() {
  local pid_file="$1"
  if [[ -f "$pid_file" ]]; then
    local pid
    pid="$(cat "$pid_file")"
    if kill -0 "$pid" >/dev/null 2>&1; then
      kill "$pid" >/dev/null 2>&1 || true
    fi
    rm -f "$pid_file"
  fi
}

stop_pid_file "$TUNNEL_PID_FILE"
stop_pid_file "$SERVER_PID_FILE"

echo "公开分享和本地服务都已经停止。"
