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
echo "📦 安裝 WebUI Python 依賴套件..."
cd "$ROOT_DIR"
python3 -m pip install -r requirements.txt || echo "⚠️ Python 套件安裝可能不完整，請稍後檢查。"

# 4. 編譯 whisper.cpp (底層 Breeze 引擎)
echo "🔨 編譯 whisper.cpp 核心引擎..."
cd "$ROOT_DIR/third_party/whisper.cpp" || { echo "❌ 找不到 whisper.cpp 目錄"; exit 1; }

if [ -n "$HAS_CUDA" ]; then
    echo "🚀 偵測到 CUDA，啟用 GPU 加速編譯 (GGML_CUDA=1)..."
    make clean && make GGML_CUDA=1
else
    echo "🐢 未偵測到 CUDA，使用一般 CPU 模式編譯..."
    make clean && make
fi

echo "============================================================"
echo "✅ 安裝程序完成！"
echo "請檢查 .env 檔案中的路徑是否符合您的系統配置。"
echo "啟動服務請執行: bash scripts/start-all.sh"
echo "============================================================"
