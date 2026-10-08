#!/bin/bash
# =========================================================================
# AI Audio Hub - Installation Script
# =========================================================================

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
ROOT_DIR="$DIR/.."
PROBE_FILE="$ROOT_DIR/system_capabilities.json"

echo "============================================================"
echo "🛠️ 啟動 AI Audio Hub 安裝程序"
echo "============================================================"

# 1. 確保已執行過環境探測
if [ ! -f "$PROBE_FILE" ]; then
    echo "⚠️ 找不到環境探測報告 ($PROBE_FILE)！"
    echo "請先執行: bash scripts/probe_env.sh"
    exit 1
fi

HAS_CUDA=$(grep -o '"has_cuda": true' "$PROBE_FILE" || echo "")

# 2. 建立 .env 檔案 (如果不存在)
if [ ! -f "$ROOT_DIR/.env" ]; then
    echo "📝 從 .env.example 建立預設環境變數檔 .env"
    cp "$ROOT_DIR/.env.example" "$ROOT_DIR/.env"
fi

# 3. 安裝 WebUI Python 依賴
# 裝進專案自己的 .venv：Ubuntu 24.04 起，系統層 pip 會被 PEP 668 擋下
# (externally-managed-environment)。啟動腳本會優先用這個 venv，找不到才退回
# 系統 python3，所以既有的部署不受影響。
echo "📦 安裝 WebUI Python 依賴套件..."
cd "$ROOT_DIR"
if [ ! -d "$ROOT_DIR/.venv" ]; then
    python3 -m venv "$ROOT_DIR/.venv" || echo "⚠️ 無法建立 venv，改用系統 python3"
fi
if [ -x "$ROOT_DIR/.venv/bin/pip" ]; then
    "$ROOT_DIR/.venv/bin/pip" install -q --upgrade pip
    "$ROOT_DIR/.venv/bin/pip" install -r requirements.txt || echo "⚠️ Python 套件安裝可能不完整，請稍後檢查。"
else
    python3 -m pip install -r requirements.txt || echo "⚠️ Python 套件安裝可能不完整，請稍後檢查。"
fi

# 4. 取得 whisper.cpp (底層 Breeze 引擎)
# third_party/ 在 .gitignore 裡，所以全新 clone 不會有這個目錄 —— 之前這裡直接
# cd 進去然後 exit 1，等於乾淨環境永遠裝不起來。
ENGINE_DIR="$ROOT_DIR/third_party/whisper.cpp"
WHISPER_REPO="${WHISPER_REPO:-https://github.com/ggml-org/whisper.cpp.git}"

if [ ! -d "$ENGINE_DIR/.git" ]; then
    echo "📥 取得 whisper.cpp 原始碼..."
    mkdir -p "$ROOT_DIR/third_party"
    git clone --depth 1 "$WHISPER_REPO" "$ENGINE_DIR" || {
        echo "❌ whisper.cpp 下載失敗"; exit 1; }
else
    echo "♻️ 沿用既有的 whisper.cpp: $ENGINE_DIR"
fi

# 5. 編譯 whisper.cpp
# CMake only：whisper.cpp 已廢棄 Makefile，舊的 `make GGML_CUDA=1` 在近期版本
# 會直接 "No rule to make target"。
echo "🔨 編譯 whisper.cpp 核心引擎..."
command -v cmake >/dev/null 2>&1 || {
    echo "❌ 找不到 cmake。請安裝: sudo apt install cmake"; exit 1; }

CMAKE_ARGS=(-B build -DCMAKE_BUILD_TYPE=Release -DWHISPER_BUILD_TESTS=OFF -DWHISPER_BUILD_EXAMPLES=ON)

if [ -n "$HAS_CUDA" ]; then
    echo "🚀 偵測到 CUDA，啟用 GPU 加速編譯..."
    CMAKE_ARGS+=(-DGGML_CUDA=ON)
    # CUDA 裝了不代表 nvcc 在 PATH 上（DGX OS 就不是），cmake 會找到 toolkit
    # 卻報 "No CMAKE_CUDA_COMPILER could be found"。
    if ! command -v nvcc >/dev/null 2>&1 && [ -x /usr/local/cuda/bin/nvcc ]; then
        CMAKE_ARGS+=(-DCMAKE_CUDA_COMPILER=/usr/local/cuda/bin/nvcc)
    fi
else
    echo "🐢 未偵測到 CUDA，使用一般 CPU 模式編譯..."
fi

cd "$ENGINE_DIR"
cmake "${CMAKE_ARGS[@]}"
cmake --build build --config Release -j "$(nproc 2>/dev/null || echo 4)" --target whisper-cli

echo "============================================================"
echo "✅ 安裝程序完成！"
echo "請檢查 .env 檔案中的路徑是否符合您的系統配置。"
echo ""

# 6. 模型：這個專案不會自己產生模型，所以講清楚要去哪裡拿，不要讓使用者
#    照著一個不會做這件事的腳本繞回來。
MODEL_DIR="${MODEL_DIR:-$ENGINE_DIR/models}"
FOUND=""
for V in 25 26; do
    [ -f "$MODEL_DIR/ggml-breeze-asr-$V.bin" ] && FOUND="$FOUND $V"
done
if [ -n "$FOUND" ]; then
    echo "🎯 已就緒的模型:$FOUND"
else
    cat <<EOF
⚠️  還沒有任何 Breeze ASR 模型。本專案不含轉檔工具，請用 breeze-asr-hub 產生：

      git clone https://github.com/pondahai/breeze-asr-hub
      cd breeze-asr-hub
      scripts/fetch_model.sh --convert --variant 26   # 台語
      scripts/fetch_model.sh --convert --variant 25   # 台灣華語、中英夾雜

    再把產生的 .bin 放到:
      $MODEL_DIR/

    兩顆可以並存，WebUI 會自動出現切換選單。
EOF
fi

echo ""
echo "啟動服務請執行: bash scripts/start-all.sh"
echo "============================================================"
