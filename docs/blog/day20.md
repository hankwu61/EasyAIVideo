# Day 20｜背景任務佇列：進度回報、取消與伺服器重啟恢復

> 30 天打造 AI 短影片生成平台 — 第 20 天

## 今日目標
- 實作 `services/task_queue.py`：單一 worker、序列執行、進度回報。
- 所有耗時 API（腳本、素材、合成、完整流程）改為回傳 `task_id`。
- 支援取消，與伺服器重啟後把中斷的任務標記清楚。

## 為什麼不用 Celery / RQ

單機、單使用者為主的工具，多裝一個 Redis 只會讓安裝變複雜。`asyncio.Queue` + 一個 worker 協程完全夠用；之後真的要橫向擴充，再把 `TaskQueue` 換成 Celery 實作，介面不變。

## TaskQueue

```python
import asyncio, traceback
from typing import Awaitable, Callable
from easyaivideo.models import Task, TaskStatus

ProgressFn = Callable[[float, str], Awaitable[None]]

class TaskQueue:
    def __init__(self, db):
        self.db = db
        self.queue: asyncio.Queue[tuple[Task, Callable]] = asyncio.Queue()
        self.current: asyncio.Task | None = None
        self.current_task_id: str | None = None
        self._cancel_flags: set[str] = set()

    async def start(self):
        asyncio.create_task(self._worker())

    async def submit(self, task: Task, fn: Callable[[ProgressFn], Awaitable[None]]) -> Task:
        await self.db.save_task(task)
        await self.queue.put((task, fn))
        return task

    def cancel(self, task_id: str):
        self._cancel_flags.add(task_id)
        if self.current_task_id == task_id and self.current:
            self.current.cancel()

    async def _worker(self):
        while True:
            task, fn = await self.queue.get()
            if task.id in self._cancel_flags:
                task.status = TaskStatus.cancelled; await self.db.save_task(task); continue

            async def progress(p: float, msg: str, _t=task):
                _t.progress, _t.message = p, msg
                await self.db.save_task(_t)

            task.status = TaskStatus.running
            await self.db.save_task(task)
            self.current_task_id = task.id
            self.current = asyncio.create_task(fn(progress))
            try:
                await self.current
                task.status, task.progress = TaskStatus.done, 1.0
            except asyncio.CancelledError:
                task.status = TaskStatus.cancelled
            except Exception as e:
                task.status, task.error = TaskStatus.failed, f"{e}\n{traceback.format_exc()[-1500:]}"
            finally:
                await self.db.save_task(task)
                self.current = self.current_task_id = None
                self._cancel_flags.discard(task.id)
```

要點：
- 每次 `progress()` 都寫回 SQLite，前端輪詢 `GET /api/tasks/{id}` 就能看到。
- 取消靠 `asyncio.Task.cancel()`：正在 `await` Gemini 或 ffmpeg 時會立即中斷；ffmpeg 子程序要在 `run_ffmpeg` 的 `except CancelledError` 裡 `proc.kill()`。
- 錯誤訊息保留 traceback 尾段，工作台能直接顯示。

## 管線改成可回報進度

`pipeline.run_full(project_id, progress)`：

```python
async def run_full(self, pid: str, progress: ProgressFn):
    p = await self.db.get_project(pid)
    await progress(0.02, "撰寫腳本"); p = await self.write_script(p)
    await progress(0.10, "生成場景圖")
    await self.generate_images(p, progress=lambda f, m: progress(0.10 + 0.35 * f, m))
    await progress(0.45, "配音")
    await self.generate_audio(p, progress=lambda f, m: progress(0.45 + 0.15 * f, m))
    self.rebuild_timeline(p)
    await progress(0.60, "動態片段")
    await self.animate_scenes(p, progress=lambda f, m: progress(0.60 + 0.20 * f, m))
    await progress(0.80, "合成影片")
    await self.render(p, progress=lambda f, m: progress(0.80 + 0.20 * f, m))
```

每個階段一個權重，進度條才會平滑。

## 路由

```
POST /api/projects/{id}/generate        → 完整流程（kind=full）
POST /api/projects/{id}/script          → kind=script
POST /api/projects/{id}/assets          → kind=assets（只做過期/缺少）
POST /api/projects/{id}/render          → kind=render
POST /api/projects/{id}/scenes/{sid}/image | /audio → kind=scene_image / scene_audio
GET  /api/tasks/{task_id}
GET  /api/projects/{id}/tasks           → 該專案任務歷史
POST /api/tasks/{task_id}/cancel
```

全部回 `{"task": Task}`，HTTP 202。

同一專案若已有 `queued` / `running` 任務，新請求回 409，避免同時寫同一個資料夾。

## 重啟恢復

Day 07 的 `db.init()` 已經把 `queued/running` 改成 `interrupted`。管線每一步都存檔，所以使用者只要再按一次「產生素材」，就會從中斷點續做，不會重做已經完成的場景。專案的 `status` 也要在任務失敗時標 `failed` 並記錄 `error`。

## 給 Antigravity 的提示詞
```
實作 services/task_queue.py（asyncio.Queue worker、progress 寫回 DB、cancel、錯誤 traceback）、
run_ffmpeg 的取消時 kill 子程序、pipeline.run_full 的階段權重進度、routers/tasks.py 與所有 202 路由、同專案 409 檢查。
在 8001 埠跑完整流程並每秒 GET task，把進度變化列給我看；中途 cancel 一次確認 ffmpeg 程序被清掉。
```

## 今日檢查清單
- [ ] 進度從 0 平滑到 1，訊息對應階段。
- [ ] 取消後 5 秒內任務變 `cancelled`，工作管理員沒有殘留 ffmpeg。
- [ ] 重啟伺服器後舊任務變 `interrupted`，重跑不會重做完成的場景。

## 明日預告
Day 21 整理 REST API：路由分組、Pydantic 請求／回應模型、錯誤格式、Swagger 文件與 `docs/API.md`。
