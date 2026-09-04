# EasyAIVideo

AI 短影片生成平台：輸入一個主題（或貼上你的文稿），系統自動撰寫腳本、為每個場景生成圖片與配音、加上字幕與背景音樂，最後合成一支完整影片。

功能:（主題 → 分鏡 → 逐幀合成的管線、可替換的 ComfyUI 工作流）與 （專案制工作台、可編輯的分鏡與逐場景重生成、任務佇列與進度追蹤）。

## 功能

- **主題生成腳本**：LLM 產生標題、每個場景的旁白與英文圖片提示詞；或直接使用自己的文稿自動分段。
- **多供應商**：
  - LLM：任何 OpenAI 相容 API（OpenAI、DeepSeek、Qwen、Moonshot、Ollama、LM Studio…）或內建 mock。
  - 語音：Microsoft Edge TTS（免費）、OpenAI 相容 `/audio/speech`、或無聲模式。
  - 圖片：本地占位圖（離線測試）、OpenAI 相容 `/images/generations`（dall-e-3、gpt-image-1、各種代理）、ComfyUI 工作流。
  - 影片：ffmpeg Ken Burns 動態鏡頭（不需 AI 影片模型）、**Agnes AI 影片**（`agnes-video-v2.0`，文生影片／圖生影片／首尾幀）或 ComfyUI 圖生影片工作流。
- **分鏡工作台**：逐場景編輯旁白與圖片提示詞、重新產生單一場景的圖片或語音、上傳自己的圖片/語音/影片、新增/刪除/排序場景。
- **輸出**：直式 9:16、橫式 16:9、方形 1:1；可開關字幕與標題；背景音樂淡入淡出混音。
- **任務系統**：背景任務佇列、即時進度、可取消；伺服器重啟後自動標記中斷的任務。
- **繁中 / 英文介面**。

## 需求

- Python 3.11+ 與 [uv](https://docs.astral.sh/uv/)
- Node.js 20+（只在建置前端時需要）
- [ffmpeg](https://ffmpeg.org/)（含 ffprobe）在 PATH 上
- Windows 建議安裝微軟正黑體（系統預設有）以正確顯示中文字幕；Linux 請安裝 Noto Sans CJK，或把字型檔放進 `resources/fonts/`

## 快速開始

```bash
# Windows
start.bat

# macOS / Linux
./start.sh
```

腳本會自動安裝 Python 相依套件、建置前端（第一次），然後在 http://127.0.0.1:8000 啟動。

手動步驟：

```bash
uv sync
cd frontend && npm install && npm run build && cd ..
uv run easyaivideo --host 127.0.0.1 --port 8000
```

第一次啟動會在專案根目錄建立 `config.yaml`（預設為完全離線可跑的 mock / placeholder / edge 組合）。到 **設定** 頁面填入你的 LLM / 圖片供應商即可產出真正的 AI 內容。設定頁每個區塊都有「測試連線」。

## 使用流程

1. **新增專案**：輸入主題或文稿，選擇語言、風格、比例、聲音、背景音樂、鏡頭動態。按「建立並開始生成」會直接跑完整流程。
2. **工作台**：腳本產生後可以逐場景修改旁白與提示詞；修改後的素材會標記「已過期」，按「產生素材」只會重做過期或缺少的部分。每張場景圖下方有三個按鈕：重新產生、上傳自己的圖片（也可直接把圖片拖到縮圖上）、下載；分鏡標題列的「下載全部場景圖」會打包所有場景圖與 AI 片段成 zip。
3. **合成影片**：所有場景都有圖片與語音後按「合成影片」，右側即可預覽與下載。

也可以直接呼叫 REST API（Swagger UI 在 `/docs`，完整契約見 [docs/API.md](docs/API.md)）。

## 長文／小說 → 分集影片（參考 ArcReel）

新增專案時選擇「長文／小說 → 分集影片」，即進入系列工作台：

1. **匯入文檔**：上傳 `.txt` `.md` `.docx` `.epub` `.pdf`（自動偵測 UTF-8 / Big5 / GB18030）或直接貼上文字，可多檔累加。
2. **分析內容**：LLM 產出故事概要（概要、類型、主題、世界觀）、主要角色（性格描述、英文外觀描述、性別、自動配對的語音）與常見場景。角色與場景都可手動修改，並可用圖片供應商「生成角色圖」。
3. **規劃分集**：依「每集目標長度」把全文按段落切成連續的集數，LLM 補上每集標題與摘要；標題與摘要可編輯。
4. **生成集數**：每一集都是獨立的子專案，沿用一般的分鏡工作台。腳本改編時會帶入概要、角色外觀與場景，讓各集圖片提示詞保持角色一致；可單集生成，也可「生成全部集數」排入佇列依序執行。
5. **兩種內容模式**：
   - 旁白解說：由旁白濃縮重述劇情，每個場景一段旁白。
   - 劇情演繹：角色各自說台詞（`speaker` 對應角色，使用該角色的語音），旁白補足敘述；字幕逐句依語音時間顯示並標示說話者。

## 目錄結構

## 目錄結構

```
easyaivideo/
  config.py            YAML 設定（可由 UI 熱更新）
  models.py            Project / Scene / Task 資料模型
  db.py                SQLite 持久化（專案 JSON、任務）
  prompts.py           LLM 提示詞
  providers/           llm / tts / image / video 供應商與 ComfyUI 客戶端
  services/
    pipeline.py        腳本 → 素材 → 合成 的核心管線；系列的分析、分集、角色圖
    series.py          文檔儲存、分集切分、子專案（集數）建立
    source_loader.py   txt / md / docx / epub / pdf 文字擷取
    task_queue.py      背景任務佇列
    ffmpeg.py          ffmpeg 合成（Ken Burns、疊字幕、串接、混 BGM）
    overlay.py         用 PIL 繪製標題/字幕透明圖層
    project_service.py 專案與場景編輯
  routers/             FastAPI 路由
frontend/              React + Vite + Tailwind 前端
data/
  projects/<id>/       每個專案的素材與輸出
  bgm/                 放入 mp3/wav 即會出現在背景音樂清單
  workflows/comfyui/   ComfyUI API 格式工作流（image_*.json / video_*.json）
```

## AI 影片生成（Agnes）

在 **設定 → 影片** 選擇 `agnes`，填入 Agnes API Key（與 LLM／圖片共用同一把即可），再把專案的「鏡頭動態」設為「AI 影片生成」：

| 模式 | 說明 |
|---|---|
| `i2v` 圖生影片 | 先生成場景圖，再以該圖為首幀生成影片（預設，角色與構圖最穩定） |
| `t2v` 文生影片 | 只用場景的影片提示詞生成，角色參考圖（若有）會一併送出 |
| `keyframes` 首尾幀 | 以本場景圖為首幀、下一場景圖為尾幀，鏡頭自然銜接到下一場 |

LLM 撰寫腳本時會為每個場景額外產生英文「影片提示詞」（動作、運鏡、氛圍），工作台可修改。每段片長取旁白長度並限制在 `max_clip_seconds`（最多 18 秒），旁白更長時合成階段會循環片段。Agnes 影片沒有音軌，語音、字幕與 BGM 仍由 ffmpeg 合成。

圖片若也使用 Agnes（`image.provider: openai_compat`、`base_url` 指向 apihub、`model: agnes-image-2.1-flash`），請把 `size_mode` 設為 `exact`，並可開啟 `use_references` 讓場景圖以角色圖為參考，維持角色一致。

## AI 審片

影片合成完成後，工作台按「AI 審片」：系統從成品逐場景抽取關鍵幀（預設每場景 2 張），連同該場景的旁白、原始圖片提示詞與角色外觀送給多模態模型，回報：

- 每個場景的評分（1–5）、畫面與旁白不符之處（例如旁白提到的主體不在畫面、地點或時間錯誤、畫面出現亂碼文字、角色外觀不一致、肢體或臉部變形）。
- 評分偏低時附上修正後的英文圖片提示詞，可一鍵套用並重新產生圖片，再重新合成。
- 整體摘要，指出優先修正的場景。

設定 → 審片 可指定多模態模型；留空則沿用 LLM 設定（需為支援圖片輸入的 OpenAI 相容模型，例如 Agnes 多模態模型、gpt-4o、qwen-vl）。「測試連線」會送一張合成小圖確認模型看得見圖片。

## ComfyUI 工作流

把 ComfyUI 以「Save (API Format)」匯出的工作流放到 `data/workflows/comfyui/`，檔名以 `image_` 或 `video_` 開頭，並把需要代入的欄位改成佔位字串：

| 佔位符 | 圖片工作流 | 影片工作流 |
|---|---|---|
| `"{{prompt}}"` / `"{{negative_prompt}}"` | ✓ | ✓ |
| `"{{width}}"` / `"{{height}}"` / `"{{seed}}"` | ✓ | ✓ |
| `"{{image}}"`（EasyAIVideo 會先上傳場景圖片） | | ✓ |
| `"{{fps}}"` / `"{{frames}}"` / `"{{duration}}"` | | ✓ |

被引號包住的佔位符會依型別代入（數字不加引號）。內附的 `image_default.json`（SDXL）與 `video_default.json`（SVD + VideoHelperSuite）是範本，請改成你實際擁有的模型檔名。

## 設定檔

見 [config.example.yaml](config.example.yaml)。環境變數：

- `EASYAIVIDEO_CONFIG`：設定檔路徑（預設 `./config.yaml`）
- `EASYAIVIDEO_DATA_DIR`：資料目錄（預設 `./data`）

## 授權

Apache-2.0
