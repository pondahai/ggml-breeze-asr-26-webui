# ggml-breeze-asr-26-webui

使用 `whisper.cpp` + `doggy8088/ggml-breeze-asr-26` 的可攜專案，clone 後可直接依 README 完成安裝與使用。

## 來源
- 模型: https://huggingface.co/doggy8088/ggml-breeze-asr-26
- 引擎: https://github.com/ggml-org/whisper.cpp

## 專案結構
- `scripts/` 安裝、CLI 轉錄、啟動 WebUI
- `webui/` Flask 前端（上傳、進度、取消）
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

### 2) CLI 轉錄
```bash
bash scripts/transcribe.sh /path/to/audio.mp3
```
結果輸出到 `webui/results/*.txt`

## 需求
- Ubuntu/WSL2
- Python 3
- 可用網路下載模型（約 2.9GB）

## 致謝
- https://www.facebook.com/will.fans/posts/pfbid0Nc4mhy5ZpziLjcDMsXQbMbN3Auoy13h3bwmLGmk2wYBDbDyG7PMi8S39S5orAgALl
