# Day 07｜資料模型：Project、Scene、Task 與 SQLite 持久化

> 30 天打造 AI 短影片生成平台（Claude Code × Agnes AI × Edge-TTS）— 第 7 天

## 今日目標
- 用 Pydantic 定義 Project、Scene、Task。
- 用 aiosqlite 實作專案 JSON 表與任務表。
- 完成專案 CRUD 的 service 與路由，並用 pytest 驗證。

## 模型

`easyaivideo/models.py`：

```python
class Scene(BaseModel):
    id: str = Field(default_factory=lambda: new_id("sc"))
    index: int
    narration: str = ""
    image_prompt: str = ""
    video_prompt: str = ""
    speaker: str | None = None
    image_path: str | None = None
    audio_path: str | None = None
    words_path: str | None = None          # Edge-TTS 逐字時間戳 JSON
    clip_path: str | None = None
    audio_duration: float | None = None
    duration: float | None = None
    cues: list["Cue"] = []
    image_stale: bool = True
    audio_stale: bool = True
    motion_override: str | None = None     # kenburns | ai | uploaded

class ProjectOptions(BaseModel):
    language: str = "zh-TW"
    style: str = "cinematic"
    aspect: Literal["9:16", "16:9", "1:1"] = "9:16"
    voice: str = "zh-TW-HsiaoChenNeural"
    speed: float = 1.0
    bgm: str | None = None
    bgm_volume: float = 0.2
    motion: Literal["kenburns", "ai_video"] = "kenburns"
    subtitle: bool = True
    show_title: bool = True
    target_seconds: int = 60

class Project(BaseModel):
    id: str = Field(default_factory=lambda: new_id("proj"))
    title: str = ""
    topic: str = ""
    source_text: str | None = None
    options: ProjectOptions = ProjectOptions()
    scenes: list[Scene] = []
    status: Literal["draft", "scripted", "assets_ready", "rendered", "failed"] = "draft"
    output_path: str | None = None
    error: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class Task(BaseModel):
    id: str = Field(default_factory=lambda: new_id("task"))
    project_id: str
    kind: str
    status: Literal["queued", "running", "done", "failed", "cancelled", "interrupted"] = "queued"
    progress: float = 0.0
    message: str = ""
    scene_id: str | None = None            # 目前正在處理的場景，前端可顯示轉圈
    error: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
```

## SQLite

```python
SCHEMA = """
CREATE TABLE IF NOT EXISTS projects (id TEXT PRIMARY KEY, data TEXT NOT NULL, created_at TEXT, updated_at TEXT);
CREATE TABLE IF NOT EXISTS tasks (id TEXT PRIMARY KEY, project_id TEXT NOT NULL, data TEXT NOT NULL, status TEXT, updated_at TEXT);
CREATE INDEX IF NOT EXISTS idx_tasks_project ON tasks(project_id);
"""

class Database:
    async def init(self):
        async with aiosqlite.connect(self.path) as db:
            await db.executescript(SCHEMA)
            await db.execute("UPDATE tasks SET status='interrupted' WHERE status IN ('queued','running')")
            await db.commit()

    async def save_project(self, p: Project):
        p.updated_at = datetime.utcnow()
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                "INSERT INTO projects VALUES (?,?,?,?) ON CONFLICT(id) DO UPDATE SET data=excluded.data, updated_at=excluded.updated_at",
                (p.id, p.model_dump_json(), p.created_at.isoformat(), p.updated_at.isoformat()))
            await db.commit()
    # get_project / list_projects / delete_project / save_task / get_task / list_tasks
```

## service 與路由

`ProjectService.create()` 同時建立 `data/projects/<id>/`；`delete()` 連資料夾一起刪。路由：`GET/POST /api/projects`、`GET/PATCH/DELETE /api/projects/{id}`。

## 用 Claude Code 寫測試

Claude Code 很擅長寫測試，但要給它固定的夾具，避免它把測試寫到真實資料夾：

```python
# tests/conftest.py
@pytest.fixture
async def client(tmp_path, monkeypatch):
    monkeypatch.setenv("EASYAIVIDEO_CONFIG", str(tmp_path / "config.yaml"))
    monkeypatch.setenv("EASYAIVIDEO_DATA_DIR", str(tmp_path / "data"))
    from easyaivideo.main import app
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
        yield c
```

把「測試一律用 tmp_path 與環境變數隔離」寫進 `CLAUDE.md`。

## 給 Claude Code 的提示詞
```
實作 models.py、db.py（aiosqlite、init 時標記 interrupted）、services/project_service.py、routers/projects.py、deps.py 與 lifespan。
建立 tests/conftest.py（tmp_path 隔離）與 tests/test_projects.py 測 CRUD。執行 uv run pytest -q 並貼結果。
若測試失敗自己修到綠燈再回報。
```

## 今日檢查清單
- [ ] `POST /api/projects` 建資料夾並回 JSON。
- [ ] 重啟後專案仍在。
- [ ] `uv run pytest -q` 全綠。

## 第一週回顧
工具、金鑰、第一支呼叫、架構、可執行骨架、資料模型。下週接 AI 與語音。

## 明日預告
Day 08 提示詞工程：`prompts.py`、OpenAI 相容 LLM 供應商與 `write_script()`。
