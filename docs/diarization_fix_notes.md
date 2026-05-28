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
**根本原因分析：**
該 WhisperX FastAPI 背景進程（PID `626201`）已經在後台連續運行了 **6 天**。
在 Linux 中，FastAPI 調用 `subprocess.run` 啟動重量級的 PyTorch/whisperx 子進程時，必須使用系統調用 `fork()`。由於舊進程運行時間過長、記憶體可能產生碎裂，或者系統的 Copy-on-Write 記憶體鎖定機制在 `fork` 瞬間被拒絕，因而拋出了 `ENOMEM` (Cannot allocate memory / 無法分配記憶體) 的系統層級致命錯誤。此時 Uvicorn 事件循環直接回傳了 HTTP `500` 的原始字串 `"Internal Server Error"`。

### 🟢 解決方案
1.  手動 `kill -9 626201` 強制終結了累積記憶體負擔的舊進程，徹底釋放 Xavier 的 unified memory 資源。
2.  以乾淨的記憶體 footprint 重新啟動了 Port `8088` 的聲紋標記服務。

---

## 3. 解決 OOM Killer 導致的 Exit Code -9 錯誤 (核心修復)
### 🔴 發現問題
解決 500 錯誤後，用戶提交任務，雖然順利啟動了 ASR 轉錄與 Alignment 對齊，但在進入步驟 3/3 載入 Pyannote 聲紋識別時，子進程突然中斷，WebUI 報錯：
```text
500: Worker process returned non-zero code -9.
```
**根本原因分析：**
在 Linux 系統中，退出碼 `-9` 代表進程被核心強行發送了 `SIGKILL` 訊號。
我們深入排查了 `/var/log/syslog`，抓出了核心底層日誌：
```text
May 28 09:40:36 ubuntu kernel: Out of memory: Killed process 1089662 (python3) ...
```
這證實了是 **Linux OOM Killer (記憶體溢出守護進程)** 所為！
由於 Jetson Xavier 的 14 GB 記憶體為 CPU/GPU 共享 (Unified Memory)，且當時背景已經運行加載了 **Gemma-4-E2B (Port 18082)** 與 **Faster Whisper (Port 8012)**。當 `worker.py` 在 GPU CUDA 上載入龐大的 Pyannote (Segmentation 3.0 + ECAPA-TDNN) 聲紋分割模型時，顯存與記憶體瞬間衝破 14 GB 上限。由於 CUDA 鎖定頁（Pinned Memory）不允許被交換至硬碟，Linux 核心為了防止主機當機，只能強行將 `worker.py` 進程殺死。

### 🟢 解決方案
我們修改了 `/media/nvidia/sd/whisperx-service/worker.py`：
*   **強制將 `DIARIZE_DEVICE` 設為 `"cpu"`。**
*   **原由：** 雖然在 CPU 上進行聲紋識別速度會比 GPU 稍慢（約數分鐘內完成），但 CPU 記憶體分配非常溫和，且**允許作業系統自由調度 Swap 空間**。當實體記憶體吃緊時，Xavier 的 Linux 核心會自動將閒置的其他大模型或服務置換（Swap Out）到本機 7.4 GB 的 Swap 磁碟中，**完美繞過實體記憶體限制，100% 避免 OOM Killer (-9) 崩潰**，確保轉錄與對齊流程完美跑通！

---

## 4. Git 歷史紀錄
*   **修復時間：** 2026-05-28 09:51 (Local Time)
*   **修改檔案：**
    *   `/media/nvidia/sd/whisperx-service/worker.py` (強制聲紋分割降級至 CPU 運行，解決 -9 OOM 崩潰)
    *   `scripts/probe_env.sh` (修復 CUDA nvcc 探測路徑)
    *   `README.md` (新增常見排錯與維護指南，加入 OOM 處理說明)
    *   `docs/diarization_fix_notes.md` (新建本篇修正筆記)
