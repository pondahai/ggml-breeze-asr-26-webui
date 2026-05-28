#!/bin/bash
# =========================================================================
# AI Audio Hub - Unified Startup Script
# =========================================================================

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
ROOT_DIR="$DIR/.."

echo "============================================================"
echo "🚀 啟動 AI Audio Hub 所有服務"
echo "============================================================"

# 1. 讀取 .env 變數
if [ -f "$ROOT_DIR/.env" ]; then
    export $(grep -v '^#' "$ROOT_DIR/.env" | xargs)
else
    echo "⚠️ 找不到 .env 檔案，使用系統預設配置啟動 WebUI。"
fi

# 2. 啟動輔助微服務 (根據 .env 配置)
echo "正在檢查本地附屬服務配置..."

# 啟動 WhisperX (如果已配置)
if [ -n "$WHISPERX_SERVICE_SCRIPT" ] && [ -f "$WHISPERX_SERVICE_SCRIPT" ]; then
    echo "▶️ 啟動 WhisperX 服務 (Port 8088)..."
    if [ -n "$WHISPERX_VENV" ]; then
        nohup $WHISPERX_VENV/bin/python3 $WHISPERX_SERVICE_SCRIPT > $ROOT_DIR/whisperx.log 2>&1 &
    else
        nohup python3 $WHISPERX_SERVICE_SCRIPT > $ROOT_DIR/whisperx.log 2>&1 &
    fi
fi

# 啟動 Faster Whisper (如果已配置)
if [ -n "$FASTER_WHISPER_SERVICE_SCRIPT" ] && [ -f "$FASTER_WHISPER_SERVICE_SCRIPT" ]; then
    echo "▶️ 啟動 Faster Whisper 服務 (Port 8013)..."
    if [ -n "$FASTER_WHISPER_VENV" ]; then
        nohup $FASTER_WHISPER_VENV/bin/python3 $FASTER_WHISPER_SERVICE_SCRIPT > $ROOT_DIR/faster_whisper.log 2>&1 &
    else
        nohup python3 $FASTER_WHISPER_SERVICE_SCRIPT > $ROOT_DIR/faster_whisper.log 2>&1 &
    fi
fi

# 啟動 Gemma LLM (如果已配置)
if [ -n "$LLAMA_SERVER_CMD" ]; then
    echo "▶️ 啟動 Gemma-4-E2B 多模態模型伺服器 (Port 18082)..."
    nohup $LLAMA_SERVER_CMD > $ROOT_DIR/gemma_llm.log 2>&1 &
fi

# 3. 啟動主 WebUI
echo "▶️ 啟動 AI Audio Hub 主閘道器 (WebUI Port ${WEBUI_PORT:-8012})..."
cd "$ROOT_DIR"
nohup python3 webui/app.py > $ROOT_DIR/webui_gateway.log 2>&1 &

echo "============================================================"
echo "✅ 服務啟動指令已送出！"
echo "請開啟瀏覽器前往 http://localhost:${WEBUI_PORT:-8012} (或設備的區域網路 IP)"
echo "如需除錯，請查看專案根目錄下的各個 .log 檔案。"
echo "============================================================"
