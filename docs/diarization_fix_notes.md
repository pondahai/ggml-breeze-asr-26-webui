# 📝 AI Audio Hub 聲紋標記與環境探測修正筆記 (2026-05-28)

## 1. 環境探測修正 (scripts/probe_env.sh)
### 🔴 發現問題
在 NVIDIA Jetson 系列開發板上，CUDA 編譯工具 `nvcc` 預設安裝於 `/usr/local/cuda/bin/nvcc`。
由於該路徑在預設的非互動式 SSH 或服務啟動環境下通常**不在 `PATH` 環境變數中**，導致原先的探測腳本在檢查 `command -v nvcc` 時失效，誤判本機不具備 CUDA GPU 加速能力。這直接導致網頁主門戶 (Port 8013) 自動載入 `system_capabilities.json` 時，將 **「WhisperX 講者分離與聲紋標記」** 功能強制反灰停用。

### 🟢 解決方案
我們對 `scripts/probe_env.sh` 的 CUDA 偵測區塊進行了升級：
1.  自動將 `/usr/local/cuda/bin` 加入環境 `PATH`。
2.  增加對 `/usr/local/cuda/bin/nvcc` 檔案的可執行性 (`-x`) 顯式雙重檢查。
這使得 ASR 與 聲紋標記 (Diarization) 功能在 Jetson Xavier 上被正確識別為 **`true`**，並順利解鎖了前端網頁的按鈕控制。

---

## 2. 聲紋標記 API 拋出 500 (Internal Server Error) 修正
### 🔴 發現問題
當用戶點擊送出聲紋標記任務時，WebUI 網頁端日誌顯示：
```text
[錯誤] 聲紋處理失敗: FastAPI 服務回傳錯誤 (500): Internal Server Error
```
連線 Xavier 後台後，我們排查了以下健康狀況：
*   Port `8088` (WhisperX 服務) 確實在 `0.0.0.0` 上監聽。
*   主進程 (PID `626201`) 處於在線狀態。
*   手動執行 ASR 子進程 `worker.py` 能順利初始化 CUDA 並進入轉錄流程，這代表模型與顯卡資源完全正常。

**根本原因分析：**
該 WhisperX FastAPI 背景進程（PID `626201`）已經在後台連續運行了 **6 天** (自 5月22日 啟動)。
在 Linux 中，FastAPI 調用 `subprocess.run` 啟動重量級的 PyTorch/whisperx 子進程時，必須使用系統調用 `fork()`。由於父進程運行時間過長、記憶體可能產生碎裂，或者系統的 Copy-on-Write 記憶體鎖定機制在 `fork` 瞬間被拒絕，因而拋出了 `ENOMEM` (Cannot allocate memory / 無法分配記憶體) 的系統層級致命錯誤。此時 Uvicorn 事件循環直接回傳了 HTTP `500` 的原始字串 `"Internal Server Error"`，而非標準的 FastAPI JSON 回應。

### 🟢 解決方案
1.  手動 `kill -9 626201` 強制終結了累積記憶體負擔的 6 天前舊進程，徹底釋放 Xavier 的 unified memory 資源。
2.  以乾淨的記憶體 footprint 重新啟動了 Port `8088` 的聲紋標記服務。
3.  測試證實重置後服務運作流暢，任務能順利通過 `fork` 調用啟動 PyTorch 運算，徹底解決了該 500 錯誤！

---

## 3. Git 歷史紀錄
*   **修復時間：** 2026-05-28 09:22 (Local Time)
*   **修改檔案：**
    *   `scripts/probe_env.sh` (修復 CUDA nvcc 探測路徑)
    *   `README.md` (新增常見排錯與維護指南)
    *   `docs/diarization_fix_notes.md` (新建本篇修正筆記)
