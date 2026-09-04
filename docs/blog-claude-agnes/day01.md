# Day 01｜為什麼要做 AI 短影片生成平台？產品願景與 30 天路線圖

> 30 天打造 AI 短影片生成平台（Claude Code × Agnes AI × Edge-TTS）— 第 1 天

## 今日目標
- 釐清產品是什麼、不是什麼。
- 把「主題 → 影片」拆成六個可獨立驗證的階段。
- 認識三個主角：Claude Code、Agnes AI、Edge-TTS，並把開發機器準備好。

## 我們要做的東西

> 輸入一個主題（或貼上你的文稿），系統自動撰寫腳本、為每個場景生成圖片與配音、加上字幕與背景音樂，最後合成一支完整影片。

自己做一遍的價值：管線每一步都能換模型與提示詞、成本透明、可以客製（品牌字型、固定角色、內部知識）。

## 六個階段

| 階段 | 輸入 | 輸出 | 使用的服務 |
|---|---|---|---|
| 1. 腳本 | 主題或文稿、語言、風格 | 標題 + N 個場景（旁白、圖片提示詞、影片提示詞） | Agnes 文字模型（OpenAI 相容 chat） |
| 2. 圖片 | 每場景的英文圖片提示詞 | 每場景一張圖 | Agnes 圖片模型（`/images/generations`） |
| 3. 語音 | 每場景的旁白 | 每場景一段 mp3 + 逐字時間戳 | Edge-TTS（免費） |
| 4. 時間軸 | 音訊長度、逐字時間戳 | 場景時長、字幕時間碼 | 純程式邏輯 |
| 5. 動態 | 場景圖 | 動態片段 | ffmpeg Ken Burns 或 Agnes 影片模型 |
| 6. 合成 | 片段、語音、字幕、BGM | 完整 mp4 | ffmpeg |

## 三個主角

**Claude Code**：Anthropic 的終端機 agent。你用自然語言描述任務，它讀程式、改檔案、跑指令、跑測試、開瀏覽器驗證。它的「專案記憶」是根目錄的 `CLAUDE.md`，30 天裡我們會持續維護這個檔案。

**Agnes AI**：`https://apihub.agnes-ai.com/v1` 提供 OpenAI 相容的 API，一把金鑰同時可用文字（`agnes-2.0-flash`）、圖片（`agnes-image-2.0-flash`、`agnes-image-2.1-flash`）與影片（`agnes-video-v2.0`）。因為相容 OpenAI 格式，程式碼不需要任何專屬 SDK，用 `httpx` 直接呼叫即可，也方便日後換成其他相容服務。

**Edge-TTS**：透過 `edge-tts` 套件使用微軟 Edge 瀏覽器的神經語音，免費、不需金鑰、有多種繁中／簡中／粵語／英文聲音，而且能回傳**逐字時間戳**，字幕可以做到精準對齊。這是選它的最大理由。

## 技術選型

- 後端 Python 3.11 + FastAPI + SQLite；前端 React + Vite + Tailwind；影音 ffmpeg。
- HTTP 客戶端一律 `httpx.AsyncClient`，不裝任何供應商 SDK。
- 套件與虛擬環境用 uv。

## 30 天路線圖

- 第一週（Day 1–7）：工具、金鑰、第一支程式、架構、骨架、資料模型。
- 第二週（Day 8–14）：腳本、文稿、供應商抽象、圖片、語音、逐字字幕。
- 第三週（Day 15–21）：ffmpeg、字幕圖層、BGM、多比例、Agnes 影片、任務佇列、API。
- 第四週（Day 22–28）：前端、表單、工作台、進度、下載、小說分集、劇情演繹。
- 收尾（Day 29–30）：成本穩定性、部署回顧。

## 開發機器準備

```bash
winget install astral-sh.uv            # Python 套件與虛擬環境
winget install OpenJS.NodeJS.LTS       # 建置前端
winget install Gyan.FFmpeg             # ffmpeg 與 ffprobe
```

確認：

```bash
uv --version
node --version
ffmpeg -version
```

Windows 內建微軟正黑體可直接用於中文字幕；Linux 請裝 Noto Sans CJK。

## 給 Claude Code 的提示詞
今天先不裝 Claude Code（明天），但可以先建立空資料夾 `EasyAIVideo` 並放一個 `CLAUDE.md` 草稿：

```markdown
# EasyAIVideo
AI 短影片生成平台。管線六段：腳本 → 圖片 → 語音 → 時間軸 → 動態 → 合成。
後端 Python 3.11 + FastAPI + SQLite，前端 React + Vite + Tailwind，影音 ffmpeg。
LLM／圖片／影片走 Agnes AI 的 OpenAI 相容 API（httpx 直接呼叫），語音用 edge-tts。
```

## 今日檢查清單
- [ ] 能說出六個階段各自的輸入輸出。
- [ ] uv、node、ffmpeg 可執行。
- [ ] `EasyAIVideo/CLAUDE.md` 草稿存在。

## 明日預告
Day 02 安裝 Claude Code，學會 CLAUDE.md、Plan 模式、權限設定與 vibe coding 的日常節奏。
