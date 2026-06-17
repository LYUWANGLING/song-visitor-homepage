#!/bin/zsh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
RUNTIME_DIR="$ROOT_DIR/.runtime/share"
SERVER_LOG="$RUNTIME_DIR/server.log"
TUNNEL_LOG="$RUNTIME_DIR/tunnel.log"
SERVER_PID_FILE="$RUNTIME_DIR/server.pid"
TUNNEL_PID_FILE="$RUNTIME_DIR/tunnel.pid"
PUBLIC_URL_FILE="$RUNTIME_DIR/public-url.txt"
PORT="${SONG_GALLERY_PORT:-8123}"
SUBDOMAIN="${SONG_SHARE_SUBDOMAIN:-song-smp-homepage}"

mkdir -p "$RUNTIME_DIR"

start_server() {
  if [[ -f "$SERVER_PID_FILE" ]]; then
    local existing_pid
    existing_pid="$(cat "$SERVER_PID_FILE")"
    if kill -0 "$existing_pid" >/dev/null 2>&1; then
      return
    fi
    rm -f "$SERVER_PID_FILE"
  fi

  cd "$ROOT_DIR"
  nohup python3 web_gallery_server.py >"$SERVER_LOG" 2>&1 &
  echo $! >"$SERVER_PID_FILE"
}

start_tunnel() {
  if [[ -f "$TUNNEL_PID_FILE" ]]; then
    local existing_pid
    existing_pid="$(cat "$TUNNEL_PID_FILE")"
    if kill -0 "$existing_pid" >/dev/null 2>&1; then
      return
    fi
    rm -f "$TUNNEL_PID_FILE"
  fi

  : >"$TUNNEL_LOG"
  nohup npx localtunnel --port "$PORT" --subdomain "$SUBDOMAIN" >"$TUNNEL_LOG" 2>&1 &
  echo $! >"$TUNNEL_PID_FILE"
}

extract_public_url() {
  local attempts=0
  while [[ $attempts -lt 30 ]]; do
    if grep -q "your url is:" "$TUNNEL_LOG" 2>/dev/null; then
      grep "your url is:" "$TUNNEL_LOG" | tail -n 1 | sed 's/.*your url is: //' >"$PUBLIC_URL_FILE"
      cat "$PUBLIC_URL_FILE"
      return 0
    fi
    sleep 1
    attempts=$((attempts + 1))
  done
  return 1
}

start_server
start_tunnel

PUBLIC_URL="$(extract_public_url || true)"

if [[ -n "${PUBLIC_URL:-}" ]]; then
  echo "游客主页：$PUBLIC_URL/generated-views/visitor-homepage.html"
  echo "名单后台：$PUBLIC_URL/generated-views/coupon-registrations-dashboard.html"
else
  echo "服务已启动，但还没拿到公开地址。"
  echo "你可以稍后查看：$TUNNEL_LOG"
  exit 1
fi
