# Day 07｜資料模型：Project、Scene、Task 與 SQLite 持久化

> 30 天打造 AI 短影片生成平台 — 第 7 天

## 今日目標
- 用 Pydantic 定義 Project、Scene、Task 三個核心模型。
- 用 aiosqlite 實作最小持久化：專案 JSON 表、任務表。
- 完成專案 CRUD 的 service 與路由，第一週收工。

## 模型設計

`easyaivideo/models.py`：

```python
from __future__ import annotations
from datetime import datetime
from enum import Enum
from typing import Literal
from uuid import uuid4
from pydantic import BaseModel, Field

def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:8]}"

class Scene(BaseModel):
    id: str = Field(default_factory=lambda: new_id("sc"))
    index: int
    narration: str = ""
    image_prompt: str = ""
    video_prompt: str = ""          # 給 Veo 用的動作／運鏡描述
    speaker: str | None = None      # Day 28 劇情演繹模式
    image_path: str | None = None
    audio_path: str | None = None
    clip_path: str | None = None
    audio_duration: float | None = None
    duration: float | None = None   # 最終場景時長（秒）
    image_stale: bool = True        # 提示詞改了 → 圖過期
    audio_stale: bool = True        # 旁白改了 → 語音過期

class ProjectOptions(BaseModel):
    language: str = "zh-TW"
    style: str = "cinematic"
    aspect: Literal["9:16", "16:9", "1:1"] = "9:16"
    voice: str = "Kore"
    bgm: str | None = None
    motion: Literal["kenburns", "ai"] = "kenburns"
    subtitle: bool = True
    show_title: bool = True
    target_seconds: int = 60

class ProjectStatus(str, Enum):
    draft = "draft"
    scripted = "scripted"
    assets_ready = "assets_ready"
    rendered = "rendered"
    failed = "failed"

class Project(BaseModel):
    id: str = Field(default_factory=lambda: new_id("proj"))
    title: str = ""
    topic: str = ""
    source_text: str | None = None  # 使用者貼上的文稿
    options: ProjectOptions = ProjectOptions()
    scenes: list[Scene] = []
    status: ProjectStatus = ProjectStatus.draft
    output_path: str | None = None
    error: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class TaskStatus(str, Enum):
    queued = "queued"
    running = "running"
    done = "done"
    failed = "failed"
    cancelled = "cancelled"
    interrupted = "interrupted"

class Task(BaseModel):
    id: str = Field(default_factory=lambda: new_id("task"))
    project_id: str
    kind: str                       # full | script | assets | render | scene_image ...
    status: TaskStatus = TaskStatus.queued
    progress: float = 0.0           # 0–1
    message: str = ""
    error: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
```

`image_stale` / `audio_stale` 是整個工作台體驗的關鍵：使用者改一個字，我們只重做該場景的該素材。

## SQLite 持久化

`easyaivideo/db.py`：

```python
import aiosqlite
from pathlib import Path
from easyaivideo.models import Project, Task

SCHEMA = """
CREATE TABLE IF NOT EXISTS projects (
  id TEXT PRIMARY KEY, data TEXT NOT NULL,
  created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS tasks (
  id TEXT PRIMARY KEY, project_id TEXT NOT NULL, data TEXT NOT NULL,
  status TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS idx_tasks_project ON tasks(project_id);
"""

class Database:
    def __init__(self, path: Path):
        self.path = path

    async def init(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        async with aiosqlite.connect(self.path) as db:
            await db.executescript(SCHEMA)
            # 伺服器重啟時，把上次還在跑的任務標記為 interrupted（Day 20 會用到）
            await db.execute(
                "UPDATE tasks SET status='interrupted' WHERE status IN ('queued','running')")
            await db.commit()

    async def save_project(self, p: Project):
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                "INSERT INTO projects VALUES (?,?,?,?) "
                "ON CONFLICT(id) DO UPDATE SET data=excluded.data, updated_at=excluded.updated_at",
                (p.id, p.model_dump_json(), p.created_at.isoformat(), p.updated_at.isoformat()))
            await db.commit()

    async def get_project(self, pid: str) -> Project | None:
        async with aiosqlite.connect(self.path) as db:
            async with db.execute("SELECT data FROM projects WHERE id=?", (pid,)) as cur:
                row = await cur.fetchone()
        return Project.model_validate_json(row[0]) if row else None

    async def list_projects(self) -> list[Project]:
        async with aiosqlite.connect(self.path) as db:
            async with db.execute("SELECT data FROM projects ORDER BY updated_at DESC") as cur:
                return [Project.model_validate_json(r[0]) for r in await cur.fetchall()]

    async def delete_project(self, pid: str):
        async with aiosqlite.connect(self.path) as db:
            await db.execute("DELETE FROM projects WHERE id=?", (pid,))
            await db.execute("DELETE FROM tasks WHERE project_id=?", (pid,))
            await db.commit()

    # save_task / get_task / list_tasks 同樣模式
```

整包 JSON 存進 `data` 欄位。這是刻意的取捨：用查詢彈性換取 schema 演進的自由。

## 專案 service 與路由

`services/project_service.py` 負責建立專案時同時建立資料夾：

```python
class ProjectService:
    def __init__(self, db: Database, data_dir: Path):
        self.db, self.data_dir = db, data_dir

    def project_dir(self, pid: str) -> Path:
        d = self.data_dir / "projects" / pid
        d.mkdir(parents=True, exist_ok=True)
        return d

    async def create(self, topic: str, source_text: str | None, options: ProjectOptions) -> Project:
        p = Project(topic=topic, source_text=source_text, options=options, title=topic[:30])
        self.project_dir(p.id)
        await self.db.save_project(p)
        return p
```

`routers/projects.py` 提供：`GET /api/projects`、`POST /api/projects`、`GET /api/projects/{id}`、`PATCH /api/projects/{id}`、`DELETE /api/projects/{id}`（同時刪除資料夾）。

## 依賴注入

`deps.py` 提供 `get_db()`、`get_config()`、之後的 `get_queue()`，並在 `main.py` 的 lifespan 中呼叫 `db.init()`。

## 給 Antigravity 的提示詞
```
實作 models.py（Scene/ProjectOptions/Project/Task，含 stale 旗標）、db.py（aiosqlite，projects 與 tasks 兩張表，
JSON 欄位，init 時把 queued/running 任務標為 interrupted）、services/project_service.py、routers/projects.py 的 CRUD，
以及 deps.py 與 main.py 的 lifespan。寫 tests/test_projects.py 用 httpx AsyncClient 測 CRUD。
執行 uv run pytest 並回報結果。
```

## 今日檢查清單
- [ ] `POST /api/projects` 會在 `data/projects/<id>/` 建資料夾並回傳 Project JSON。
- [ ] 重啟伺服器後專案還在。
- [ ] `uv run pytest` 綠燈。

## 第一週回顧
我們有了工具（Antigravity、AI Studio）、能呼叫 Gemini、有了架構圖、跑得起來的 FastAPI 與可持久化的資料模型。下週開始接 AI。

## 明日預告
Day 08 提示詞工程：把 AI Studio 裡試出來的腳本提示詞變成 `prompts.py` 與 Gemini LLM 供應商，產出真正的分鏡。
