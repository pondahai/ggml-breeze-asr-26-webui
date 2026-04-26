#!/usr/bin/env bash
set -euo pipefail
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WCPP="$PROJECT_ROOT/third_party/whisper.cpp"
MODEL="$WCPP/models/ggml-breeze-asr-26.bin"
MODEL_URL="https://huggingface.co/doggy8088/ggml-breeze-asr-26/resolve/main/ggml-breeze-asr-26.bin"

if [[ "$OSTYPE" == "darwin"* ]]; then
  echo "[OS] macOS detected"
  brew install cmake curl python
  pip3 install flask
else
  echo "[OS] Linux detected"
  sudo apt-get update
  sudo apt-get install -y build-essential cmake curl python3-flask
fi

mkdir -p "$PROJECT_ROOT/third_party"
if [ ! -d "$WCPP/.git" ]; then
  git clone https://github.com/ggml-org/whisper.cpp.git "$WCPP"
fi

cd "$WCPP"
cmake -B build
cmake --build build -j
mkdir -p models
[ -f "$MODEL" ] || curl -L --fail -o "$MODEL" "$MODEL_URL"

echo "[OK] whisper-cli: $WCPP/build/bin/whisper-cli"
echo "[OK] model: $MODEL"
