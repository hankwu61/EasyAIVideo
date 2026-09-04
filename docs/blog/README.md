# 30 天打造 AI 短影片生成平台：Antigravity IDE × Google AI Studio × Gemini API

這是一個為期 30 天的連載。目標是從零開始，用 **Antigravity IDE** 進行 vibe coding，
在 **Google AI Studio** 取得 API Key，全程使用 **Gemini API**（文字、圖片、語音、影片），
打造一個 AI 短影片生成平台：

> 輸入一個主題（或貼上你的文稿），系統自動撰寫腳本、為每個場景生成圖片與配音、加上字幕與背景音樂，最後合成一支完整影片。

技術堆疊：Python 3.11 + FastAPI + SQLite 後端、React + Vite + Tailwind 前端、ffmpeg 合成、`google-genai` SDK。

## 30 篇目錄

### 第一週：願景、工具與地基
| Day | 標題 |
|---|---|
| 01 | [為什麼要做 AI 短影片生成平台？產品願景與 30 天路線圖](day01.md) |
| 02 | [安裝 Antigravity IDE：Agent Manager、Editor 與 vibe coding 心法](day02.md) |
| 03 | [Google AI Studio 入門：取得 Gemini API Key、認識模型與配額](day03.md) |
| 04 | [第一支 Gemini 程式：google-genai SDK、串流與結構化輸出](day04.md) |
| 05 | [系統架構設計：FastAPI + SQLite + React + ffmpeg 的資料流](day05.md) |
| 06 | [用 Antigravity 生成專案骨架：uv、config.yaml 與熱更新設定](day06.md) |
| 07 | [資料模型：Project、Scene、Task 與 SQLite 持久化](day07.md) |

### 第二週：腳本與素材生成
| Day | 標題 |
|---|---|
| 08 | [提示詞工程：讓 Gemini 從主題寫出分鏡腳本（JSON Schema 輸出）](day08.md) |
| 09 | [貼上文稿也能用：長文分段、場景切分與提示詞補全](day09.md) |
| 10 | [供應商抽象層：可替換的 LLM / TTS / Image / Video 介面與 mock](day10.md) |
| 11 | [場景圖生成：Gemini 原生圖片模型（Nano Banana）與 Imagen](day11.md) |
| 12 | [風格一致性：風格預設、角色參考圖與多圖編輯](day12.md) |
| 13 | [Gemini TTS 配音：預建聲音、風格指令與多語言](day13.md) |
| 14 | [時間軸與字幕：從音訊長度推算場景時長與逐句字幕](day14.md) |

### 第三週：影片合成與任務系統
| Day | 標題 |
|---|---|
| 15 | [ffmpeg 入門：Ken Burns 動態鏡頭讓靜態圖動起來](day15.md) |
| 16 | [用 PIL 繪製標題與字幕圖層：中文字型、描邊與安全區](day16.md) |
| 17 | [串接場景、混入 BGM：淡入淡出、音量正規化與 loudnorm](day17.md) |
| 18 | [直式 9:16、橫式 16:9、方形 1:1：一份腳本三種輸出](day18.md) |
| 19 | [Veo 影片生成：文生影片、圖生影片與首尾幀](day19.md) |
| 20 | [背景任務佇列：進度回報、取消與伺服器重啟恢復](day20.md) |
| 21 | [REST API 設計：FastAPI 路由、Pydantic 契約與 Swagger](day21.md) |

### 第四週：前端工作台與進階功能
| Day | 標題 |
|---|---|
| 22 | [前端骨架：React + Vite + Tailwind 與型別安全的 API client](day22.md) |
| 23 | [新增專案表單：主題、語言、風格、比例、聲音與 BGM 選擇](day23.md) |
| 24 | [分鏡工作台：逐場景編輯、單場景重生與拖曳上傳](day24.md) |
| 25 | [即時進度：輪詢 vs SSE，任務狀態視覺化](day25.md) |
| 26 | [影片預覽、下載與素材打包 zip](day26.md) |
| 27 | [長文／小說 → 分集影片：內容分析、角色設定與分集規劃](day27.md) |
| 28 | [劇情演繹模式：多角色台詞、多說話者 TTS 與說話者字幕](day28.md) |

### 收尾
| Day | 標題 |
|---|---|
| 29 | [成本、配額與穩定性：快取、重試、安全設定與費用估算](day29.md) |
| 30 | [部署與回顧：打包、Docker、Cloud Run 與下一個 30 天](day30.md) |

## 每篇文章的固定結構
1. **今日目標**：今天做完會得到什麼。
2. **正文**：概念、程式碼與踩坑筆記。
3. **給 Antigravity 的提示詞**：可以直接貼給 Agent 的任務描述。
4. **今日檢查清單**：驗收標準。
5. **明日預告**。

> 模型名稱會隨時間更新。文中以 `gemini-2.5-flash`、`gemini-2.5-flash-image`、`gemini-2.5-flash-preview-tts`、`veo-3.1-generate-preview` 等為例，
> 實作時請以 [Google AI Studio](https://aistudio.google.com/) 與 [官方文件](https://ai.google.dev/gemini-api/docs) 當下列出的模型為準。
