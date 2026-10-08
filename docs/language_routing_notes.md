# 語言參數與外語模型路由（2026-10-08）

## 問題
- `/api/transcribe` 呼叫 whisper-cli 時寫死 `-l zh`，WhisperX 路徑也寫死 `'zh'`。
- 英文錄音因此不是只輸出「(英文)」，就是被翻成中文（例：「LLM benchmark leaderboards」→「L&L BENCHMARK領班」）。
- 就算改成 `-l en`，Breeze-ASR-26（台語→中文字，Whisper-large-v2 微調）對部分英文錄音仍會整段或後半翻成中文，而且每次結果不同。
- `-l auto` 的語言判斷也壞了：一段英文被判成 mk（馬其頓語，p=0.12）。
- 加英文 `--prompt` 能救一段，卻讓另一段只剩「Timing」，不可靠。

## 改動（webui/app.py）
- 新增表單參數 `language`：
  - 預設 `zh`，維持原行為（網頁前端不送此參數，所以不受影響）。
  - 也可送 `auto`，或 2～3 字母語言碼（en、ja…）。
  - 其他值回 400。
  - WhisperX 路徑一併傳入（`auto` 時傳 None）。
- `language` 不是 `zh` 時改用原版 Whisper **large-v3-turbo**：
  - 模型檔：`/media/nvidia/sd/models/whisper/ggml-large-v3-turbo.bin`（1.6 GB，來源 ggerganov/whisper.cpp）
  - 程式常數：`MODEL_MULTI`。模型檔不存在時退回 Breeze。
  - job log 會寫一行 `Model: ... (language=...)`。
- 備份：
  - `webui/app.py.bak-before-lang`：最初原檔
  - `webui/app.py.bak-before-turbo`：加 language 後、加 turbo 前
- 套用：`systemctl --user restart asr-8012.service`（名稱是 8012，實際聽 8013）。

## 實測（5 秒英文錄音）
| 引擎 | 結果 | 時間 |
|---|---|---|
| Breeze-26 `-l zh`（原行為） | 「(英文)」或中文翻譯 | 約 12 s |
| Breeze-26 `-l en` | 部分正確，部分仍翻成中文，每次結果不同 | 約 12 s |
| faster-whisper large-v3（venv-fw-asr，CPU int8） | 正確 | 載入 90 s＋每段約 2 分鐘 |
| whisper.cpp large-v3-turbo（GPU） | 正確；auto 判斷 en，p≥0.995 | 8～11 s（含載入），GPU 佔 1.6 GB |

## 為什麼 faster-whisper 在這台用不了 GPU
- 機器環境：JetPack 5.1.5、CUDA 11.4、cuDNN 8.6。
- pip 的 aarch64 版 CTranslate2 只有 CPU：`venv-fw-asr` 裝的是 ctranslate2 4.5.0，`get_cuda_device_count()` 回傳 0。
- CTranslate2 4.x 要 CUDA 12，但 JetPack 5 只到 CUDA 11.4，JetPack 6 又不支援 Xavier。
- jetson-containers 的 faster-whisper 映像只發布 JetPack 6 版。
- 剩下唯一的路是用 CUDA 11.4 自己編譯 CTranslate2 3.x，搭配舊版 faster-whisper。成本高，不建議。
- 結論：問題不在 Volta（sm_72），而在 CUDA 版本。外語改用 whisper.cpp＋turbo 即可用 GPU。

## 其他觀察
- `use_whisperx` 要送字串 `true`，送 `1` 會被當成 false。
- WhisperX 聲紋服務（:8088，/media/nvidia/sd/whisperx-service）目前沒在跑。
- 舊的 `~/faster_whisper_server.py`（:8012，tiny 模型）沒在跑。
- 開機自動啟動的 AI 服務：
  - `realtime-voice.service`：系統服務，:8015／:8016
  - `asr-8012.service`：使用者服務，已開 linger，實際聽 :8013
- 記憶體：兩個模型都是每個 job 才載入，跑完就釋放，不常駐。同時跑約 5.5 GB，總共 14 GB 夠用。
