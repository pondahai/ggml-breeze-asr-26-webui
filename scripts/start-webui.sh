#!/usr/bin/env bash
set -euo pipefail
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP="$PROJECT_ROOT/webui/app.py"
LOG="/tmp/ggml-breeze-asr-26-webui.log"
PORT="${PORT:-8013}"

# stop same app if running
pkill -f "$APP" || true

# if target port already occupied, stop that process to avoid false start
if ss -ltnp | grep -q ":$PORT"; then
  PIDS=$(ss -ltnp | awk -v p=":$PORT" '$4 ~ p {print $NF}' | sed -n 's/.*pid=\([0-9]\+\).*/\1/p' | sort -u)
  for pid in $PIDS; do
    kill "$pid" || true
  done
  sleep 1
fi

nohup python3 "$APP" >"$LOG" 2>&1 &
sleep 1
ss -ltnp | grep ":$PORT" || true
echo "[OK] WebUI started: http://127.0.0.1:$PORT"
echo "[LOG] $LOG"
