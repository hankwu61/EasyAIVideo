# Day 21｜REST API 設計：FastAPI 路由、Pydantic 契約與 docs/API.md

> 30 天打造 AI 短影片生成平台（Claude Code × Agnes AI × Edge-TTS）— 第 21 天

## 今日目標
- 三週累積的路由整理成一致契約：命名、狀態碼、錯誤格式。
- `schemas.py` 明確定義請求／回應模型。
- 產生 `docs/API.md` 與前端 `types.ts`。

## 路由總覽

```
GET  /api/health          GET /api/presets          GET /api/bgm
GET  /api/settings        PATCH /api/settings       POST /api/settings/test/{section}   POST /api/settings/sync-key
GET  /api/tts/voices      POST /api/tts/preview
POST /api/source/extract

GET/POST /api/projects    GET/PATCH/DELETE /api/projects/{id}
POST /api/projects/{id}/source | duplicate | generate | script | assets | render
GET  /api/projects/{id}/tasks | subtitles.srt | subtitles.vtt | export.zip

PATCH  /api/projects/{id}/scenes/{sid}          POST /api/projects/{id}/scenes
DELETE /api/projects/{id}/scenes/{sid}          POST /api/projects/{id}/scenes/reorder
POST   /api/projects/{id}/scenes/{sid}/image | audio | upload
POST   /api/projects/{id}/characters/{cid}/image

GET /api/tasks/{id}       POST /api/tasks/{id}/cancel
GET /data/...
```

## schemas.py

`models.py` 是儲存結構，`schemas.py` 是 API 契約，分開才不會為了 API 改動儲存格式。

```python
class ProjectCreate(BaseModel):
    topic: str = Field(min_length=1, max_length=200)
    source_text: str | None = None
    options: ProjectOptions = ProjectOptions()
    start: bool = False

class ProjectSummary(BaseModel):
    id: str; title: str; status: str; aspect: str; thumbnail: str | None; updated_at: datetime

class SceneUpdate(BaseModel):
    narration: str | None = None; image_prompt: str | None = None; video_prompt: str | None = None; speaker: str | None = None

class TaskResponse(BaseModel): task: Task
class ErrorResponse(BaseModel): error: str; detail: str | None = None
```

`PATCH scenes/{sid}` 的 stale 規則由後端決定：旁白變 → `audio_stale`；提示詞變 → `image_stale`。

## 錯誤格式

```python
class AppError(Exception):
    def __init__(self, status: int, error: str, detail: str | None = None): ...

@app.exception_handler(AppError)
async def _(_, e): return JSONResponse(e.status, {"error": e.error, "detail": e.detail})

@app.exception_handler(ProviderError)
async def _(_, e): return JSONResponse(502, {"error": "provider_error", "detail": str(e)})
```

常用：`404 project_not_found`、`409 task_in_progress`、`400 missing_assets`、`502 provider_error`（Agnes / Edge-TTS 失敗）。

## Swagger 分組與前端型別

`openapi_tags` 分 projects / scenes / tasks / settings / tts。

```bash
uv run python -c "import json; from easyaivideo.main import app; print(json.dumps(app.openapi()))" > frontend/openapi.json
cd frontend && npx openapi-typescript openapi.json -o src/api/types.ts
```

把這兩行做成 `scripts/gen_types.py`，並加進 `CLAUDE.md` 的指令區：「改 API 後執行 `uv run python scripts/gen_types.py`」。

## docs/API.md

`scripts/gen_api_doc.py` 從 OpenAPI 產生表格（路徑、方法、summary、請求、回應）加三個 curl 範例：建立並開始、輪詢任務、下載影片。

## 給 Claude Code 的提示詞
```
建立 schemas.py 並讓所有路由使用明確 request/response model 與 summary；AppError 與 ProviderError 全域處理；openapi_tags 分組；
scenes 的 PATCH/新增/刪除/排序。寫 scripts/gen_types.py 與 scripts/gen_api_doc.py 並執行。
把「改 API 後要跑 gen_types」加進 CLAUDE.md。
```

## 今日檢查清單
- [ ] `/docs` 每個路由有 summary 與 schema。
- [ ] 錯誤都是 `{error, detail}`。
- [ ] `docs/API.md` 與 `types.ts` 已產生。

## 第三週回顧
合成、多比例、Agnes 影片、任務佇列、API 契約。後端完整，下週做工作台。

## 明日預告
Day 22 前端骨架：Vite + React + Tailwind、API client、路由與版面。
