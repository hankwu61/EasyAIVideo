# Day 21｜REST API 設計：FastAPI 路由、Pydantic 契約與 Swagger

> 30 天打造 AI 短影片生成平台 — 第 21 天

## 今日目標
- 把三週累積的路由整理成一致的契約：命名、狀態碼、錯誤格式。
- 用 Pydantic 定義所有請求／回應模型，讓 Swagger 與前端型別自動對齊。
- 產出 `docs/API.md`，第四週前端就照這份做。

## 路由總覽

```
GET    /api/health
GET    /api/presets                         風格、比例、聲音、轉場
GET    /api/settings          PATCH /api/settings
POST   /api/settings/test/{section}         llm | image | tts | video
GET    /api/bgm
POST   /api/tts/preview

GET    /api/projects          POST /api/projects
GET    /api/projects/{id}     PATCH /api/projects/{id}     DELETE /api/projects/{id}
POST   /api/projects/{id}/source                          上傳文稿
POST   /api/projects/{id}/duplicate?aspect=
POST   /api/projects/{id}/generate | script | assets | render   → 202 Task
GET    /api/projects/{id}/tasks
GET    /api/projects/{id}/subtitles.srt
GET    /api/projects/{id}/export.zip                      Day 26

PATCH  /api/projects/{id}/scenes/{sid}                    改旁白/提示詞（自動標 stale）
POST   /api/projects/{id}/scenes                          新增場景
DELETE /api/projects/{id}/scenes/{sid}
POST   /api/projects/{id}/scenes/reorder                  {order: [sid...]}
POST   /api/projects/{id}/scenes/{sid}/image | audio      → 202 Task
POST   /api/projects/{id}/scenes/{sid}/image/edit         → 202 Task
POST   /api/projects/{id}/scenes/{sid}/upload             multipart: image | audio | video

GET    /api/tasks/{id}        POST /api/tasks/{id}/cancel
GET    /data/...                                          靜態素材
```

## 請求／回應模型

`easyaivideo/schemas.py`（跟 `models.py` 分開：models 是儲存結構，schemas 是 API 契約）：

```python
class ProjectCreate(BaseModel):
    topic: str = Field(min_length=1, max_length=200)
    source_text: str | None = None
    options: ProjectOptions = ProjectOptions()
    start: bool = False                 # True 則建立後直接排入 full 任務

class ProjectSummary(BaseModel):        # 列表用，不帶 scenes
    id: str; title: str; status: ProjectStatus; aspect: str
    thumbnail: str | None; updated_at: datetime

class SceneUpdate(BaseModel):
    narration: str | None = None
    image_prompt: str | None = None
    video_prompt: str | None = None
    speaker: str | None = None

class TaskResponse(BaseModel):
    task: Task

class ErrorResponse(BaseModel):
    error: str
    detail: str | None = None
```

`PATCH scenes/{sid}` 的 service 邏輯：

```python
if body.narration is not None and body.narration != scene.narration:
    scene.narration, scene.audio_stale = body.narration, True
if body.image_prompt is not None and body.image_prompt != scene.image_prompt:
    scene.image_prompt, scene.image_stale = body.image_prompt, True
```

過期旗標由後端決定，前端不需要知道規則。

## 錯誤格式統一

```python
from fastapi import Request
from fastapi.responses import JSONResponse

class AppError(Exception):
    def __init__(self, status: int, error: str, detail: str | None = None): ...

@app.exception_handler(AppError)
async def app_error(_: Request, e: AppError):
    return JSONResponse(status_code=e.status, content={"error": e.error, "detail": e.detail})

@app.exception_handler(Exception)
async def unhandled(_: Request, e: Exception):
    return JSONResponse(status_code=500, content={"error": "internal_error", "detail": str(e)[:500]})
```

常用：`404 project_not_found`、`409 task_in_progress`、`400 missing_assets`（沒圖或沒語音就按合成）、`402 provider_quota`（Gemini 429 轉譯）。

## Swagger 加註

每個路由給 `summary` 與 `response_model`，`FastAPI(title=..., description=..., openapi_tags=[...])` 把路由分成 projects / scenes / tasks / settings 四組。Swagger 在 `/docs`，ReDoc 在 `/redoc`。

## 產生前端型別

```bash
uv run python -c "import json; from easyaivideo.main import app; print(json.dumps(app.openapi()))" > frontend/openapi.json
cd frontend && npx openapi-typescript openapi.json -o src/api/types.ts
```

明天前端就用這份型別，後端改欄位前端編譯期就會發現。

## docs/API.md

用一個腳本從 OpenAPI 產生 markdown 表格（路徑、方法、summary、請求模型、回應模型），並附上三個 curl 範例：建立專案並開始、輪詢任務、下載影片。

## 給 Antigravity 的提示詞
```
建立 easyaivideo/schemas.py，把所有路由改用明確的 request/response model 與 summary，加入 AppError 與全域錯誤處理、
openapi_tags 分組、scenes 的 PATCH/新增/刪除/排序路由。寫 scripts/gen_api_doc.py 從 openapi 產生 docs/API.md，
並執行 openapi-typescript 產生 frontend/src/api/types.ts。
```

## 今日檢查清單
- [ ] `/docs` 每個路由都有 summary、request 與 response schema。
- [ ] 錯誤回應都是 `{error, detail}` 格式。
- [ ] `docs/API.md` 與 `types.ts` 已產生。

## 第三週回顧
影片合成、多比例、Veo、任務佇列與 API 契約完成。後端功能已經齊全，接下來一週把它包成好用的工作台。

## 明日預告
Day 22 前端骨架：React + Vite + Tailwind，型別安全的 API client，路由與版面。
