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

# 3. 執行安裝 (會自動取得並編譯 whisper.cpp)
bash scripts/install.sh
```

`install.sh` 會 clone `whisper.cpp` 到 `third_party/`(該目錄在 `.gitignore` 裡，
所以全新 clone 不會有)、用 CMake 依探測結果編譯，並把 Python 相依裝進專案的
`.venv`。

## 🎙️ 語音模型

本專案**不含**轉檔工具，模型請用
[breeze-asr-hub](https://github.com/pondahai/breeze-asr-hub) 產生：

```bash
scripts/fetch_model.sh --convert --variant 26   # 台語，輸出中文字
scripts/fetch_model.sh --convert --variant 25   # 台灣華語、中英夾雜
```

把產生的 `.bin` 放進 `third_party/whisper.cpp/models/`(或設 `MODEL_DIR`)。
兩顆可以並存 —— **只要有兩顆以上，網頁上就會自動出現模型下拉選單**，
每次轉錄可以分別指定。預設是 `26`,用 `MODEL_VARIANT` 可改。

實測補充:在一段**華語**會議錄音上，`26` 開頭生成了幻覺字幕並整段漏掉主席致詞，
`25` 則正確轉出。音檔以華語為主的話建議把預設設成 `25`。

命令列也可以指定:

```bash
bash scripts/transcribe.sh -m 25 /path/to/audio.wav
curl localhost:8013/api/models                    # 有哪幾顆可用
```

## 🚀 服務啟動

我們建議使用一鍵啟動腳本，它會根據探測結果，自動將有支援的後端服務全部拉起：

```bash
bash scripts/start-all.sh
```

接著打開瀏覽器前往：`http://<您的IP>:8012`

### 網頁介面操作指南
- **引擎切換：** 在上傳區塊可以勾選是否啟用 **WhisperX 講者分離**。
- **模型切換：** 轉好兩顆以上模型時會出現「辨識模型」選單，可逐次選擇 Breeze ASR 25 / 26。只有一顆時選單會隱藏。
- **超大檔案支援：** 系統已實作 Chunked Upload，數百 MB 的音訊檔也能穩定上傳並進行 Smart Audio Splitting。
- **重新整理不中斷：** 結合 LocalStorage 機制，上傳處理中即使重新整理網頁，進度條也能無縫接軌。
- **AI 秘書：** 若 Gemma-4 伺服器啟動成功，右上角會亮綠燈，您可以直接點擊「智慧發言人姓名重寫」等功能。

## 🔌 API 使用方法

WebUI 是純 HTTP 的 Flask 服務，網頁上做得到的事都可以直接呼叫 API（預設埠 `8013`）。

| 方法 | 路徑 | 說明 |
| --- | --- | --- |
| `POST` | `/api/transcribe` | 送出轉寫工作，回傳 `job_id` |
| `GET` | `/api/jobs/<job_id>` | 查狀態與結果 |
| `GET` | `/api/jobs/<job_id>/download?ext=txt` | 下載結果檔（`txt` / `srt` / `vtt`） |
| `POST` | `/api/jobs/<job_id>/cancel` | 中止進行中的工作 |
| `POST` | `/api/upload_chunk` | 分片上傳（大檔用） |
| `GET` | `/api/models` | 有哪幾顆 Breeze 模型可用 |
| `GET` | `/api/system/capabilities` | `probe_env.sh` 產生的能力報告 |
| `POST` | `/api/llm` | 把逐字稿丟給 Gemma 處理 |
| `GET` | `/api/llm/health` | Gemma 伺服器是否活著 |

`POST /api/transcribe` 吃 multipart 表單：

| 欄位 | 預設 | 說明 |
| --- | --- | --- |
| `file` | — | 音檔，支援 `.wav .mp3 .m4a .flac .ogg` |
| `model` | `MODEL_VARIANT`（`26`） | `25` 或 `26` |
| `format` | `txt` | `txt` / `srt` / `vtt` |
| `max_len` | `20` | 每段字幕最長字數 |
| `use_whisperx` | `false` | 改走 WhisperX 講者分離 |
| `hf_token` | — | WhisperX 取用受管制權重時需要 |
| `min_speakers` / `max_speakers` | — | 提示講者人數 |
| `upload_id` + `filename` | — | 分片上傳時取代 `file` |

一次完整流程：

```bash
JOB=$(curl -sS -F file=@meeting.wav -F model=25 -F format=srt \
        localhost:8013/api/transcribe | python3 -c 'import sys,json;print(json.load(sys.stdin)["job_id"])')

until [ "$(curl -sS localhost:8013/api/jobs/$JOB | python3 -c 'import sys,json;print(json.load(sys.stdin)["status"])')" = done ]; do sleep 5; done

curl -sS -o meeting.srt "localhost:8013/api/jobs/$JOB/download?ext=srt"
```

查詢結果裡除了 `status` 與 `text`，還有 `model`（這份逐字稿是哪顆模型轉的）與
`log_tail`（whisper-cli 的即時輸出，可直接當進度顯示）。

**大檔請走分片上傳**：先把檔案切塊逐一 `POST /api/upload_chunk`（帶同一個自訂
`upload_id` 與遞增的 `chunk_index`），送完後 `POST /api/transcribe` 改帶
`upload_id` 與 `filename`，伺服器會自行組裝。網頁介面就是這樣做的，數百 MB 的檔案
才不會在瀏覽器或反向代理上斷掉。

## 📜 開發歷程

| 時間 | 里程碑 |
| --- | --- |
| 2026-04 | 初版：`whisper.cpp` + Breeze ASR 的單引擎轉寫網頁 |
| 2026-04 | 加入 SRT/VTT 字幕輸出與分段最佳化 |
| 2026-05 | 接上 Gemma-4 AI 秘書，支援思考過程即時串流 |
| 2026-05 | 分片上傳 + 智慧靜音切割，解決大檔穩定性 |
| 2026-05 | 整合離線 WhisperX 講者分離 |
| 2026-05 | 加入 `probe_env.sh` 硬體探測與能力降級 UI，從單引擎轉為多引擎中控 |
| 2026-08 | 修復乾淨環境無法安裝的問題；支援兩顆 Breeze 模型並存切換 |

### 與 breeze-asr-hub 的關係

姊妹專案 [breeze-asr-hub](https://github.com/pondahai/breeze-asr-hub) 是從這裡長出去
的：它把「跑得起來」的部分抽成不綁單一機器的形式，並加上即時聽寫與**模型轉檔**。

分工是：**模型在那邊產生，在這邊使用。** 本專案刻意不含轉檔工具（那需要 torch 與
數 GB 的暫存空間，不該讓一個推理前端扛），兩邊共用同一套檔名慣例
`ggml-breeze-asr-<25|26>.bin`。

### 2026-08 修了什麼

在 DGX Spark 上從**全新 clone** 實測，發現這個 repo 當時其實無法安裝：

- `third_party/` 在 `.gitignore` 裡，但 `install.sh` 從不 clone `whisper.cpp`，
  直接 `cd` 進不存在的目錄然後 `exit 1`
- 編譯用 `make GGML_CUDA=1`，但 `whisper.cpp` 早已廢棄 Makefile
- `requirements.txt` **不存在於 repo 中**，`pip install -r` 只是報錯後被忽略
- Ubuntu 24.04 起 PEP 668 擋下系統層 `pip install`

會一直沒被發現，是因為既有機器上這些檔案是歷史遺留的，從未從乾淨狀態驗證過。

另外 `probe_env.sh` 在統一記憶體的 GPU 上會中止（`nvidia-smi` 回傳 `[N/A]`），
使得 `gpu_vram_gb` 停在 0，於是一台有 121 GB 可用記憶體的機器被判定為
「VRAM 不足」，WhisperX 與 Gemma 兩個功能都被關掉。

### 已知邊界

實測過的是 Jetson Xavier 與 DGX Spark，也就是 **NVIDIA + Linux**。
早期（2026-04）曾有 macOS 安裝分支，在 2026-05 重寫 `install.sh` 時遺失，目前程式碼
中沒有任何 macOS 處理。純 CPU 路徑存在但尚未實測。

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

---

## 🔧 邊緣設備常見排錯 (Edge Device Troubleshooting)

### 1. Jetson 設備 CUDA 未偵測到 (網頁功能反灰)
*   **原因：** Jetson 設備的 `nvcc` 位於 `/usr/local/cuda/bin/nvcc`，在 SSH 非互動式環境中可能未加入 `PATH`。
*   **修正：** 腳本 `probe_env.sh` 已完成升級，會自動將 `/usr/local/cuda/bin` 加入環境變數，現在能完美適配所有 Jetson 邊緣設備。您只需重新執行 `bash scripts/probe_env.sh` 並刷新網頁即可。

### 2. 聲紋標記 API 拋出 500 錯誤 (Internal Server Error)
*   **原因：** 背景長期運行（數天以上）的 WhisperX 服務 (Port 8088) 在調用 `subprocess` 載入 PyTorch/Pyannote 進行發言人對齊時，可能因父進程記憶體分配鎖定或碎裂，導致系統 `fork()` 時回傳 `ENOMEM` (Cannot allocate memory) 錯誤。
*   **解決方法：** 請 SSH 登入 Jetson Xavier，使用 `kill -9 <PID>` 關閉 Port 8088 的舊進程，並重新跑一遍啟動服務指令以重置乾淨的運行記憶體空間。
