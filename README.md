# ggml-breeze-asr-26-webui

使用 `whisper.cpp` + `doggy8088/ggml-breeze-asr-26` 的可攜專案，clone 後可直接依 README 完成安裝與使用。
<img width="907" height="445" alt="image" src="https://github.com/user-attachments/assets/c8a25824-c293-44cf-8fda-42846d7797b0" />

## 來源
- 模型: https://huggingface.co/doggy8088/ggml-breeze-asr-26
- 引擎: https://github.com/ggml-org/whisper.cpp

## 功能亮點
- **跨平台支援**: 支援 Ubuntu/WSL2 及 macOS (Apple Silicon 優化)。
- **多格式輸出**: 支援 TXT, SRT, VTT 格式。
- **精確切分**: 可自訂段落最大長度，並啟用 `sow` (Split on Word) 優化中文字句切分。
- **繁體中文優化**: 預設鎖定 `zh` 語言，確保 Breeze ASR 模型最佳表現。

## 專案結構
- `scripts/` 安裝、CLI 轉錄、啟動 WebUI
- `webui/` Flask 前端（上傳、進度、格式選擇、下載）
- `third_party/` 安裝時放入 whisper.cpp 與模型

## 初始安裝
```bash
git clone <your-repo-url>
cd ggml-breeze-asr-26-webui
bash scripts/install.sh
```

## 使用方法
### 1) 啟動前端
```bash
bash scripts/start-webui.sh
```
開啟 `http://127.0.0.1:8013`
- 可選擇輸出格式 (TXT/SRT/VTT)。
- 可調整「段落限長」以符合字幕需求。

### 2) CLI 轉錄
```bash
bash scripts/transcribe.sh /path/to/audio.mp3
```
結果會同時輸出 TXT, SRT, VTT 到 `webui/results/` 目錄。

## 需求
- Ubuntu/WSL2 或 macOS
- Python 3
- FFmpeg (用於音檔智慧切片)
- 可用網路下載模型（約 2.9GB）

## 致謝
- https://www.facebook.com/will.fans/posts/pfbid0Nc4mhy5ZpziLjcDMsXQbMbN3Auoy13h3bwmLGmk2wYBDbDyG7PMi8S39S5orAgALl
.fans/posts/pfbid0Nc4mhy5ZpziLjcDMsXQbMbN3Auoy13h3bwmLGmk2wYBDbDyG7PMi8S39S5orAgALl
