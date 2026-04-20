#!/usr/bin/env bash
set -euo pipefail
[ $# -ge 1 ] || { echo "Usage: $0 /path/to/audio"; exit 1; }
IN="$1"
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CLI="$PROJECT_ROOT/third_party/whisper.cpp/build/bin/whisper-cli"
MODEL="$PROJECT_ROOT/third_party/whisper.cpp/models/ggml-breeze-asr-26.bin"
OUT_DIR="$PROJECT_ROOT/webui/results"
mkdir -p "$OUT_DIR"
[ -x "$CLI" ] || { echo "missing whisper-cli, run: bash scripts/install.sh"; exit 1; }
[ -f "$MODEL" ] || { echo "missing model, run: bash scripts/install.sh"; exit 1; }
BASE="$(date +%s)-$(basename "$IN")"
OUT_BASE="$OUT_DIR/${BASE%.*}"
"$CLI" -m "$MODEL" -f "$IN" -otxt -of "$OUT_BASE" -nt
echo "[OK] output: ${OUT_BASE}.txt"
