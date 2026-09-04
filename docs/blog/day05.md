# Day 05｜系統架構設計：FastAPI + SQLite + React + ffmpeg 的資料流

> 30 天打造 AI 短影片生成平台 — 第 5 天

## 今日目標
- 畫出從使用者按下「生成」到影片產出的完整資料流。
- 定義模組邊界與目錄結構，之後 25 天都照這張圖蓋。
- 決定「專案」的檔案佈局。

## 整體架構

```
┌────────────┐  REST/JSON   ┌──────────────────────────────────────────┐
│  React UI  │ ───────────▶ │ FastAPI                                   │
│ (Vite)     │ ◀─────────── │  routers/  ── services/ ── providers/     │
└────────────┘  進度輪詢     │     │           │              │           │
                            │     │      task_queue      Gemini API      │
                            │     │           │        (llm/image/tts/   │
                            │     ▼           ▼         video)           │
                            │  SQLite     ffmpeg + PIL                   │
                            │ (專案 JSON、  (合成)                        │
                            │  任務)                                      │
                            └──────────────────────────────────────────┘
                                          │
                                          ▼
                              data/projects/<id>/  素材與輸出
```

三個層次，職責分明：

- **routers/**：只做 HTTP 進出、參數驗證，呼叫 service，不含業務邏輯。
- **services/**：管線（pipeline）、專案編輯、任務佇列、ffmpeg。這裡是核心。
- **providers/**：每種 AI 能力一個抽象介面 + 多個實作（Gemini、mock）。services 只認介面。

## 核心資料流

```
POST /api/projects (主題、選項)
  └─▶ 建立 Project(status=draft) 存進 SQLite
POST /api/projects/{id}/generate
  └─▶ task_queue.submit(pipeline.run_full)
        ├─ 1. write_script   → LLM   → project.scenes[]
        ├─ 2. generate_assets
        │     ├─ image provider → scenes[i].image_path
        │     └─ tts provider   → scenes[i].audio_path, audio_duration
        ├─ 3. build_timeline → scenes[i].duration, subtitle cues
        ├─ 4. motion (kenburns | veo) → scenes[i].clip_path
        └─ 5. compose (ffmpeg) → project.output_path
GET /api/tasks/{task_id}   ← 前端每秒輪詢進度
```

每一步完成都會把 Project 寫回 SQLite，所以任何一步失敗都可以從中間重跑，而不是整條重來。

## 目錄結構

```
easyaivideo/
  __init__.py
  main.py              FastAPI app、靜態檔案、啟動
  config.py            YAML 設定（可由 UI 熱更新）
  models.py            Project / Scene / Task 資料模型
  db.py                SQLite 持久化
  prompts.py           所有 LLM 提示詞集中在這
  presets.py           風格預設、比例預設、聲音清單
  deps.py              FastAPI 依賴注入（config、db、queue）
  providers/
    base.py            四個抽象介面
    llm/    gemini.py  mock.py
    image/  gemini.py  imagen.py  placeholder.py
    tts/    gemini.py  silent.py
    video/  kenburns.py  veo.py
  services/
    pipeline.py        腳本 → 素材 → 合成
    project_service.py 專案與場景編輯
    task_queue.py      背景任務
    timeline.py        時長與字幕時間碼
    ffmpeg.py          合成指令
    overlay.py         PIL 字幕圖層
  routers/
    projects.py  tasks.py  settings.py  assets.py
frontend/              React + Vite + Tailwind
data/
  projects/<id>/       scene_01.png, scene_01.wav, clip_01.mp4, output.mp4
  bgm/                 使用者自備背景音樂
  easyaivideo.db
```

## 專案檔案佈局

每個專案一個資料夾，素材以場景編號命名，這樣「重新產生第 3 場圖片」只要覆蓋一個檔案：

```
data/projects/proj_ab12cd34/
  project.json        （SQLite 也有一份，這裡方便除錯）
  scene_01.png  scene_01.wav  clip_01.mp4
  scene_02.png  ...
  subtitles.srt
  output.mp4
```

## 三個設計決策

1. **Project 整包存 JSON**：場景結構會一直演進（之後加 speaker、video_prompt），用 JSON 欄位比一直 migrate 表格輕鬆。
2. **素材「過期」標記**：使用者改了旁白，語音就標記 `stale=True`；「產生素材」只重做過期或缺少的部分。
3. **一切 async**：Gemini SDK 有 `client.aio`，ffmpeg 用 `asyncio.create_subprocess_exec`，任務佇列才不會卡住 API。

## 給 Antigravity 的提示詞
用 Planning 模式：

```
依照以下目錄結構建立空的 Python 套件與模組檔（只放 docstring 與 TODO，不要實作）：
[貼上上面的目錄樹]
另外在 docs/ARCHITECTURE.md 放入資料流說明與三個設計決策。
完成後執行 uv run python -c "import easyaivideo" 確認可匯入。
```

## 今日檢查清單
- [ ] 能不看圖說出五個管線步驟與它們讀寫的欄位。
- [ ] 目錄骨架建好，`import easyaivideo` 成功。
- [ ] `docs/ARCHITECTURE.md` 存在。

## 明日預告
Day 06 讓 Antigravity 生成可執行的專案骨架：FastAPI 啟動、health 路由、`config.yaml` 讀寫與熱更新、`start.bat` / `start.sh`。
