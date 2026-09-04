# Day 05｜系統架構設計：FastAPI + SQLite + React + ffmpeg 的資料流

> 30 天打造 AI 短影片生成平台（Claude Code × Agnes AI × Edge-TTS）— 第 5 天

## 今日目標
- 畫出從「按下生成」到「影片產出」的完整資料流。
- 定義三層模組邊界與目錄結構。
- 決定專案資料夾的檔案佈局。

## 整體架構

```
┌────────────┐  REST/JSON   ┌──────────────────────────────────────────────┐
│  React UI  │ ───────────▶ │ FastAPI                                       │
│ (Vite)     │ ◀─────────── │  routers/ ── services/ ── providers/          │
└────────────┘  進度輪詢     │     │          │              ├─ llm   → Agnes chat        │
                            │     │     task_queue         ├─ image → Agnes images      │
                            │     │          │              ├─ tts   → Edge-TTS          │
                            │     ▼          ▼              └─ video → ffmpeg / Agnes    │
                            │  SQLite    ffmpeg + PIL                                    │
                            └──────────────────────────────────────────────┘
                                          │
                                          ▼
                              data/projects/<id>/  素材與輸出
```

- **routers/**：HTTP 進出與參數驗證，呼叫 service。
- **services/**：管線、專案編輯、任務佇列、時間軸、ffmpeg。核心邏輯在這。
- **providers/**：四種 AI 能力各一個介面、多個實作。service 只認介面。

## 核心資料流

```
POST /api/projects                 → Project(status=draft)
POST /api/projects/{id}/generate   → task_queue.submit(pipeline.run_full)
   1. write_script     LLM(Agnes)        → scenes[].narration / image_prompt / video_prompt
   2. generate_images  Image(Agnes)      → scenes[].image_path
   3. generate_audio   TTS(Edge)         → scenes[].audio_path / audio_duration / word_timings
   4. build_timeline   純邏輯            → scenes[].duration / cues
   5. animate          Video(kenburns|agnes) → scenes[].clip_path
   6. render           ffmpeg            → project.output_path
GET  /api/tasks/{id}               ← 前端每秒輪詢
```

每一步完成就把 Project 寫回 SQLite，失敗可以從中間續做。

## 目錄結構

```
easyaivideo/
  main.py  config.py  models.py  db.py  prompts.py  presets.py  deps.py
  providers/
    base.py                         四個 Protocol、ProviderError
    registry.py                     依設定組裝
    llm/    openai_compat.py  mock.py
    image/  openai_compat.py  placeholder.py
    tts/    edge.py  silent.py
    video/  kenburns.py  agnes.py
  services/
    pipeline.py  project_service.py  task_queue.py  timeline.py
    ffmpeg.py  overlay.py  sizes.py  source_loader.py
  routers/
    projects.py  scenes.py  tasks.py  settings.py  assets.py
frontend/
data/
  projects/<id>/  bgm/  easyaivideo.db
```

`llm/openai_compat.py` 與 `image/openai_compat.py` 刻意不叫 `agnes.py`：它們對任何 OpenAI 相容服務都適用，Agnes 只是預設的 `base_url`。影片端點是 Agnes 專屬格式，所以叫 `agnes.py`。

## 專案檔案佈局

```
data/projects/proj_ab12cd34/
  scene_01.png  scene_01.mp3  scene_01.words.json  clip_01.mp4  final_01.mp4
  scene_02.png  ...
  subtitles.srt  output.mp4
```

`scene_XX.words.json` 是 Edge-TTS 回傳的逐字時間戳，Day 14 會用。

## 三個設計決策

1. **Project 整包 JSON 存 SQLite**：場景欄位會一直長，免 migration。
2. **stale 旗標**：改旁白只重做語音，改提示詞只重做圖片。
3. **一切 async**：httpx async、edge-tts 本身就是 async、ffmpeg 用 `create_subprocess_exec`。

## 給 Claude Code 的提示詞
Plan 模式先看計畫，再執行：

```
依照 @docs/ARCHITECTURE.md（我剛寫好，內容如下…）建立目錄骨架：每個模組只放 docstring 與 TODO，不實作。
建立 easyaivideo/__init__.py 與 providers 的子套件。完成後 uv run python -c "import easyaivideo" 確認可匯入，
並把目錄樹貼給我。
```

## 今日檢查清單
- [ ] 能說出六個步驟各自讀寫的欄位。
- [ ] 骨架建好，`import easyaivideo` 成功。
- [ ] `docs/ARCHITECTURE.md` 存在，`CLAUDE.md` 的架構段落指向它。

## 明日預告
Day 06 用 Claude Code 生成可執行骨架：FastAPI、health、`config.yaml` 熱更新、設定 API、`.claude/launch.json` 預覽設定。
