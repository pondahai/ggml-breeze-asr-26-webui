#!/bin/bash
# ========================================================================
# AI Audio Hub - Environment & Hardware Probing Script
# =========================================================================

echo "============================================================"
echo "🔍 啟動系統硬體與環境探測 (AI Audio Hub Environment Probe)"
echo "============================================================"

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
OUTPUT_FILE="$DIR/../system_capabilities.json"

HAS_CUDA=false
GPU_VRAM_GB=0
IS_JETSON=false
HAS_FFMPEG=false
PYTHON_CMD="python3"

# 1. OS & Architecture
ARCH=$(uname -m)
OS_INFO=$(cat /etc/os-release | grep PRETTY_NAME | cut -d '"' -f 2)
echo "💻 作業系統: $OS_INFO ($ARCH)"

# 2. Memory
TOTAL_MEM_KB=$(grep MemTotal /proc/meminfo | awk '{print $2}')
TOTAL_MEM_GB=$((TOTAL_MEM_KB / 1024 / 1024))
echo "🧠 系統記憶體: ~${TOTAL_MEM_GB} GB"

# 3. GPU & CUDA Detection
if command -v nvcc &> /dev/null; then
    HAS_CUDA=true
    CUDA_VER=$(nvcc --version | grep "release" | awk '{print $5}' | cut -d ',' -f 1)
    echo "🟩 CUDA 工具鍊: 支援 (版本: $CUDA_VER)"
else
    echo "🟨 CUDA 工具鍊: 未安裝 (可能只能使用 CPU 運算)"
fi

if [ -f /etc/nv_tegra_release ] || command -v tegrastats &> /dev/null; then
    IS_JETSON=true
    echo "🚀 設備類型: NVIDIA Jetson 邊緣設備"
    # Jetson uses unified memory
    GPU_VRAM_GB=$TOTAL_MEM_GB
    echo "🎮 GPU 共享記憶體: ~${GPU_VRAM_GB} GB"
elif command -v nvidia-smi &> /dev/null; then
    echo "🚀 設備類型: 獨立 NVIDIA 顯示卡"
    VRAM_MB=$(nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits | head -n 1)
    GPU_VRAM_GB=$((VRAM_MB / 1024))
    echo "🎮 GPU VRAM: ~${GPU_VRAM_GB} GB"
else
    echo "🟨 設備類型: 未偵測到 NVIDIA GPU"
fi

# 4. Toolchains
if command -v ffmpeg &> /dev/null; then
    HAS_FFMPEG=true
    echo "🟩 FFmpeg: 支援"
else
    echo "🟥 FFmpeg: 未安裝 (無法處理多種音訊格式)"
fi

if command -v $PYTHON_CMD &> /dev/null; then
    PY_VER=$($PYTHON_CMD --version)
    echo "🟩 Python: $PY_VER"
else
    echo "🟥 Python: 未安裝 python3"
fi

# 5. Engine Capability Assessment
echo "------------------------------------------------------------"
echo "📊 引擎支援能力評估結果："

SUPPORT_WHISPERX=false
SUPPORT_FASTER_WHISPER=false
SUPPORT_GEMMA_E2B=false
SUPPORT_BREEZE=true # whisper.cpp CPU fallback is okay

if [ "$HAS_CUDA" = true ]; then
    SUPPORT_FASTER_WHISPER=true
    echo "✅ Faster Whisper: 支援 (GPU 加速)"
    if [ "$GPU_VRAM_GB" -ge 7 ]; then
        SUPPORT_WHISPERX=true
        SUPPORT_GEMMA_E2B=true
        echo "✅ WhisperX 講者分離: 支援 (VRAM >= 7GB)"
        echo "✅ Gemma-4-E2B 多模態模型: 支援 (VRAM >= 7GB)"
    else
        echo "⚠️ WhisperX 講者分離: 不建議 (VRAM 不足，可能會 OOM)"
        echo "⚠️ Gemma-4-E2B: 不建議 (VRAM 不足，請使用較小量化版本)"
    fi
else
    echo "⚠️ Faster Whisper / WhisperX: 降級為 CPU 模式 (速度極慢)"
fi

echo "✅ Breeze ASR (whisper.cpp): 支援"

# 6. Generate JSON Report
cat <<EOT > "$OUTPUT_FILE"
{
  "os": "$OS_INFO",
  "architecture": "$ARCH",
  "total_memory_gb": $TOTAL_MEM_GB,
  "is_jetson": $IS_JETSON,
  "has_cuda": $HAS_CUDA,
  "gpu_vram_gb": $GPU_VRAM_GB,
  "capabilities": {
    "breeze_asr": $SUPPORT_BREEZE,
    "faster_whisper": $SUPPORT_FASTER_WHISPER,
    "whisperx_diarization": $SUPPORT_WHISPERX,
    "gemma_e2b_multimodal": $SUPPORT_GEMMA_E2B
  }
}
EOT

echo "------------------------------------------------------------"
echo "📄 探測報告已生成至: $OUTPUT_FILE"
echo "WebUI 將根據此報告動態開放對應的 UI 按鈕與功能。"
