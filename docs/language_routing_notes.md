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

## 更新：合併上游、改用 Breeze-25（同日稍晚）
- 合併 GitHub main（8/7 的 12 個 commit：支援 25／26 兩顆模型、`model` 參數、`/api/models`）。上游仍寫死 `-l zh`，language 參數重新加回。
- 路由改為：`zh`／`en`／`auto` 用預設 Breeze 模型；其他語言碼沒指定 `model` 時用 turbo（`MULTILINGUAL_MODEL`，可用環境變數覆寫）。明確指定 `model` 時以指定為準。
- 預設模型改 25：systemd drop-in `~/.config/systemd/user/asr-8012.service.d/model.conf` 設 `MODEL_VARIANT=25`。
- 25 版模型取自 DGX Spark `~/breeze-asr-hub/models/ggml-breeze-asr-25.bin`（官方轉檔，md5 開頭 32ce35fc50c9），放在 `third_party/whisper.cpp/models/`。

| 錄音 | Breeze-25 | Breeze-26 |
|---|---|---|
| 黃仁勳（英） | It's also home of some of the world's greatest computer scientists, so this is a great opportunity.（兩次相同；auto 判成 zh 但仍輸出英文） | 整段或後半翻成中文，每次不同 |
| 馬斯克（英） | …it's 134 days I believe which ends in a few days. | It's 134 days I |
| 白日依山盡（中） | 白日「一」山盡…（錯 1 字），12 s | 「來」日「伊」山盡…（錯 2 字），47 s |

結論：中英都用 25；26 留給台語；其他語言用 turbo。
