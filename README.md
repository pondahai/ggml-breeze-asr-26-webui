# 🎙️ AI Audio Hub (Jetson Xavier 邊緣語音中控中心)

這是一個專為 NVIDIA Jetson (如 Xavier) 等邊緣設備打造的**多模態與多引擎語音辨識 WebUI**。
從單一的 Breeze ASR 專案，現已全面升級為支援**動態硬體探測**與**多引擎路由**的綜合語音中控中心。

<img width="907" height="445" alt="image" src="https://github.com/user-attachments/assets/c8a25824-c293-44cf-8fda-42846d7797b0" />

## ✨ 核心特色與架構大整合

本專案將四種強大的 AI 引擎整合於單一的 Web 介面，並具備「環境探測」能力，會根據您的硬體 (GPU VRAM、CUDA) 動態開啟或隱藏功能：

1. **🚀 Breeze ASR (預設輕量引擎)**
   - 基於 `whisper.cpp`，針對台灣口音優化的繁體中文語音辨識。
   - 硬體需求極低，支援 CPU 降級執行。
2. **🗣️ WhisperX (高精度 + 講者分離)**
   - 適合多人會議，可精準識別「誰在什麼時候說了什麼」(Speaker Diarization)。
   - **硬體需求：** 需 CUDA 支援且建議 VRAM >= 7GB。
3. **⚡ Faster Whisper (極速 API)**
   - 適合需要極限轉錄速度的單人語音。
   - **硬體需求：** 需 CUDA 支援。
4. **🧠 Gemma-4-E2B (多模態 AI 秘書)**
   - 內建 Google DeepMind 最新的邊緣語音大語言模型 (LLM)。
   - 轉錄完成後，可直接在網頁上一鍵進行「姓名重寫」、「會議摘要」、「擷取待辦事項」。
   - **硬體需求：** 需 CUDA 支援且建議 VRAM >= 7GB。

## 🛠️ 安裝與自動環境探測

本專案包含智慧型的環境探測系統，在安裝前會掃描您的硬體規格，並產生 `system_capabilities.json` 報告，WebUI 會根據此報告決定能顯示哪些功能。

```bash
# 1. 取得程式碼
git clone <your-repo-url>
cd ggml-breeze-asr-26-webui

# 2. 執行硬體探測 (重要！)
bash scripts/probe_env.sh

# 3. 執行安裝
bash scripts/install.sh
```

## 🚀 服務啟動

我們建議使用一鍵啟動腳本，它會根據探測結果，自動將有支援的後端服務全部拉起：

```bash
bash scripts/start-all.sh
```

接著打開瀏覽器前往：`http://<您的IP>:8012`

### 網頁介面操作指南
- **引擎切換：** 在上傳區塊可以勾選是否啟用 **WhisperX 講者分離**。
- **超大檔案支援：** 系統已實作 Chunked Upload，數百 MB 的音訊檔也能穩定上傳並進行 Smart Audio Splitting。
- **重新整理不中斷：** 結合 LocalStorage 機制，上傳處理中即使重新整理網頁，進度條也能無縫接軌。
- **AI 秘書：** 若 Gemma-4 伺服器啟動成功，右上角會亮綠燈，您可以直接點擊「智慧發言人姓名重寫」等功能。

## 📁 目錄結構說明

- `scripts/`：包含環境探測 (`probe_env.sh`)、安裝 (`install.sh`)、與全域啟動腳本 (`start-all.sh`)。
- `webui/`：Flask API 閘道器與前端 Vue/HTML 介面，負責協調各個語音與 LLM 引擎。
- `system_capabilities.json`：由 `probe_env.sh` 產生的本機硬體能力報告 (請勿手動修改)。
- `third_party/`：編譯好的 `whisper.cpp` 等底層工具。

## ⚠️ 硬體支援與降級說明 (Graceful Degradation)

若您的設備 (例如無 GPU 的普通電腦或 RAM 不足的 Jetson Nano) 不支援特定功能，系統**不會崩潰**，而是會：
1. `probe_env.sh` 報告將顯示該功能為 `false`。
2. 網頁介面上對應的按鈕（如 WhisperX 切換開關）會自動反灰。
3. 預設降級為最輕量的 **Breeze ASR (CPU 模式)** 來確保最基本的語音轉文字功能依然可用。
