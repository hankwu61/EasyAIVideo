# Day 01｜為什麼要做 AI 短影片生成平台？產品願景與 30 天路線圖

> 30 天打造 AI 短影片生成平台 — 第 1 天

## 今日目標
- 釐清我們要做的產品到底是什麼、不是什麼。
- 把「主題 → 影片」拆成可以獨立開發、獨立驗證的六個階段。
- 看懂接下來 30 天的路線圖，並準備好開發機器。

## 我們要做的東西

一句話描述：

> 輸入一個主題（或貼上你的文稿），系統自動撰寫腳本、為每個場景生成圖片與配音、加上字幕與背景音樂，最後合成一支完整影片。

這類產品市面上已經有不少（Pictory、InVideo、Pixelle-Video、ArcReel……），但自己做一遍的價值在於：

1. **完全掌握管線**：每一步都可以換模型、換提示詞、換輸出格式。
2. **成本透明**：直接用 Gemini API 計價，沒有中間商。
3. **可以客製**：例如加入自家品牌字型、固定角色、公司內部知識庫。

## 把問題拆成六個階段

整條管線可以拆成六個階段，每一段都有清楚的輸入與輸出，這也是我們之後模組劃分的依據：

| 階段 | 輸入 | 輸出 | 使用的 Gemini 能力 |
|---|---|---|---|
| 1. 腳本 | 主題或文稿、語言、風格 | 標題 + N 個場景（旁白、圖片提示詞、影片提示詞） | Gemini 文字模型 + JSON 結構化輸出 |
| 2. 圖片 | 每個場景的英文圖片提示詞 | 每個場景一張圖 | Gemini 原生圖片模型（Nano Banana）或 Imagen |
| 3. 語音 | 每個場景的旁白 | 每個場景一段音訊 + 長度 | Gemini TTS |
| 4. 時間軸 | 音訊長度、旁白文字 | 場景時長、字幕時間碼 | 純程式邏輯 |
| 5. 動態 | 場景圖 | 動態片段 | ffmpeg Ken Burns 或 Veo |
| 6. 合成 | 片段、語音、字幕、BGM | 完整 mp4 | ffmpeg |

只要每一段都能單獨跑、單獨測，最後串起來就不會是黑盒子。

## 技術選型（先講結論）

- **後端**：Python 3.11 + FastAPI。Python 在影音處理與 AI SDK 生態最完整，FastAPI 的型別與自動文件可以省下大量溝通成本。
- **資料庫**：SQLite。單機部署零設定，專案 JSON 直接存進去，之後要換 Postgres 也容易。
- **前端**：React + Vite + Tailwind。工作台需要大量互動（逐場景編輯、拖曳上傳、即時進度），純伺服器渲染會很痛苦。
- **影音**：ffmpeg。所有合成都靠它，不需要任何 GPU。
- **AI**：全部走 Gemini API，透過 `google-genai` Python SDK。
- **開發工具**：Antigravity IDE 進行 vibe coding；Google AI Studio 管理 API Key、試提示詞、看配額。

## 30 天路線圖

- **第一週（Day 1–7）**：工具安裝、拿到 API Key、第一支 Gemini 程式、架構設計、專案骨架與資料模型。
- **第二週（Day 8–14）**：腳本生成、文稿分段、供應商抽象層、圖片、語音、時間軸與字幕。
- **第三週（Day 15–21）**：ffmpeg 合成、字幕圖層、BGM、多比例輸出、Veo、任務佇列、REST API。
- **第四週（Day 22–28）**：前端骨架、新增專案、分鏡工作台、即時進度、下載、小說分集、劇情演繹。
- **收尾（Day 29–30）**：成本與穩定性、部署與回顧。

## 開發機器準備

今天請先把以下東西裝好，明天才能專心在 IDE 上：

```bash
# Python 3.11+ 與 uv（Python 套件與虛擬環境管理）
winget install astral-sh.uv          # Windows
# brew install uv                    # macOS

# Node.js 20+（建置前端）
winget install OpenJS.NodeJS.LTS

# ffmpeg（含 ffprobe）
winget install Gyan.FFmpeg
```

裝完後確認：

```bash
uv --version
node --version
ffmpeg -version
```

Windows 使用者順便確認系統有「微軟正黑體」，之後中文字幕會用到；Linux 請安裝 Noto Sans CJK。

## 給 Antigravity 的提示詞
今天還不寫程式，但可以先在 Antigravity 建立一個空資料夾 `EasyAIVideo`，並貼上這段作為第一個「知識」項目：

```
這個專案是 AI 短影片生成平台。管線分六段：腳本 → 圖片 → 語音 → 時間軸 → 動態 → 合成。
後端 Python 3.11 + FastAPI + SQLite，前端 React + Vite + Tailwind，影音用 ffmpeg，
所有 AI 能力走 Gemini API（google-genai SDK）。之後所有任務都遵守這個架構。
```

## 今日檢查清單
- [ ] 能說出六個階段各自的輸入輸出。
- [ ] uv、node、ffmpeg 都能在終端機執行。
- [ ] 建好 `EasyAIVideo` 空資料夾。

## 明日預告
Day 02 安裝 Antigravity IDE，認識 Agent Manager 與 Editor 兩種視圖，並建立 vibe coding 的工作習慣。
