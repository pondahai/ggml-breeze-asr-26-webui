#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<EOF
Usage: $0 [-m 25|26] /path/to/audio

  -m 25   台灣華語、中英夾雜
  -m 26   台語，輸出中文字 (預設)

模型檔在 \$MODEL_DIR (預設 third_party/whisper.cpp/models)，
用 MODEL_VARIANT 可改預設值。
EOF
}

VARIANT="${MODEL_VARIANT:-26}"
while getopts ":m:h" opt; do
  case "$opt" in
    m) VARIANT="$OPTARG" ;;
    h) usage; exit 0 ;;
    *) usage >&2; exit 1 ;;
  esac
done
shift $((OPTIND - 1))

[ $# -ge 1 ] || { usage >&2; exit 1; }
IN="$1"

case "$VARIANT" in
  25|26) ;;
  *) echo "未知的模型: $VARIANT (可用: 25, 26)" >&2; exit 1 ;;
esac

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CLI="${WHISPER_CLI:-$PROJECT_ROOT/third_party/whisper.cpp/build/bin/whisper-cli}"
MODEL_DIR="${MODEL_DIR:-$PROJECT_ROOT/third_party/whisper.cpp/models}"
MODEL="$MODEL_DIR/ggml-breeze-asr-$VARIANT.bin"
OUT_DIR="$PROJECT_ROOT/webui/results"
mkdir -p "$OUT_DIR"

[ -x "$CLI" ] || { echo "找不到 whisper-cli，請執行: bash scripts/install.sh"; exit 1; }

# install.sh 只負責編譯引擎，不會產生模型 —— 之前這裡叫人回去跑 install.sh，
# 是一條死路。轉檔工具在 breeze-asr-hub。
if [ ! -f "$MODEL" ]; then
  cat >&2 <<EOF
找不到模型: $MODEL

本專案不含轉檔工具。用 breeze-asr-hub 產生一顆再放進 $MODEL_DIR/：

    git clone https://github.com/pondahai/breeze-asr-hub
    cd breeze-asr-hub
    scripts/fetch_model.sh --convert --variant $VARIANT
EOF
  exit 1
fi

BASE="$(date +%s)-$(basename "$IN")"
OUT_BASE="$OUT_DIR/${BASE%.*}"
echo "[..] 使用 Breeze ASR $VARIANT ($(basename "$MODEL"))"
"$CLI" -m "$MODEL" -f "$IN" -otxt -osrt -ovtt -of "$OUT_BASE" -nt -ml 20 -l zh -sow
echo "[OK] outputs:"
echo "  - ${OUT_BASE}.txt"
echo "  - ${OUT_BASE}.srt"
echo "  - ${OUT_BASE}.vtt"
