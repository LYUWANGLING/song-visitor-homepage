#!/bin/zsh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PUBLIC_URL_FILE="$ROOT_DIR/.runtime/share/public-url.txt"

if [[ -f "$PUBLIC_URL_FILE" ]]; then
  PUBLIC_URL="$(cat "$PUBLIC_URL_FILE")"
  echo "游客主页：$PUBLIC_URL/generated-views/visitor-homepage.html"
  echo "名单后台：$PUBLIC_URL/generated-views/coupon-registrations-dashboard.html"
else
  echo "还没有公开地址，请先运行 scripts/start-public-share.sh"
  exit 1
fi
