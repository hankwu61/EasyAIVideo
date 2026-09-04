# Day 20｜背景任務佇列：進度回報、取消與伺服器重啟恢復

> 30 天打造 AI 短影片生成平台（Claude Code × Agnes AI × Edge-TTS）— 第 20 天

## 今日目標
- `services/task_queue.py`：asyncio 單 worker、進度寫回 SQLite。
- 所有耗時 API 改回 202 + `task_id`。
- 取消（含 kill ffmpeg、放棄 Agnes 輪詢）、重啟後標記 `interrupted`。

## 為什麼不用 Celery

單機工具，多一個 Redis 只會讓安裝變複雜。`asyncio.Queue` + worker 協程夠用，介面不變之後可換。

## TaskQueue

```python
class TaskQueue:
    def __init__(self, db):
        self.db = db; self.q = asyncio.Queue(); self.current = None; self.current_id = None; self.cancel_flags = set()

    async def start(self): asyncio.create_task(self._worker())

    async def submit(self, task: Task, fn) -> Task:
        await self.db.save_task(task); await self.q.put((task, fn)); return task

    def cancel(self, task_id):
        self.cancel_flags.add(task_id)
        if self.current_id == task_id and self.current: self.current.cancel()

    async def _worker(self):
        while True:
            task, fn = await self.q.get()
            if task.id in self.cancel_flags:
                task.status = "cancelled"; await self.db.save_task(task); continue
            async def progress(p, msg, scene_id=None, _t=task):
                _t.progress, _t.message, _t.scene_id = p, msg, scene_id; await self.db.save_task(_t)
            task.status = "running"; await self.db.save_task(task)
            self.current_id, self.current = task.id, asyncio.create_task(fn(progress))
            try:
                await self.current; task.status, task.progress = "done", 1.0
            except asyncio.CancelledError:
                task.status = "cancelled"
            except Exception as e:
                task.status, task.error = "failed", f"{e}\n{traceback.format_exc()[-1500:]}"
            finally:
                await self.db.save_task(task); self.current = self.current_id = None; self.cancel_flags.discard(task.id)
```

取消時 `run_ffmpeg` 會 kill 子程序（Day 15），`AgnesVideo._poll` 的 `await asyncio.sleep` 會被中斷、直接放棄輪詢（Agnes 那邊的任務會自己跑完，但我們不再等）。

## 階段權重

```python
async def run_full(self, pid, progress):
    p = await self.db.get_project(pid)
    await progress(0.02, "撰寫腳本"); p = await self.write_script(p)
    await self.generate_images(p, progress=scale(progress, 0.10, 0.45))
    await self.generate_audio(p, progress=scale(progress, 0.45, 0.60))
    self.rebuild_timeline(p)
    await self.animate_scenes(p, progress=scale(progress, 0.60, 0.80))
    await self.render(p, progress=scale(progress, 0.80, 1.00))
```

用 AI 影片時，動態段權重放大到 0.6–0.9，因為那是最久的一步。

## 路由

```
POST /api/projects/{id}/generate | script | assets | render         → 202 {task}
POST /api/projects/{id}/scenes/{sid}/image | audio                 → 202
GET  /api/tasks/{id}     POST /api/tasks/{id}/cancel     GET /api/projects/{id}/tasks
```

同專案已有 queued/running 任務 → 409。任務失敗時專案 `status="failed"`、`error` 記錄，成功後清空。

## 重啟恢復

`db.init()` 已把 queued/running 改 interrupted。管線每步存檔，重按「產生素材」從中斷處續做。

## Claude Code 的 hooks

這時候 hooks 很好用：在 `.claude/settings.json` 加 PostToolUse hook，每次編輯 `easyaivideo/**/*.py` 後自動 `uv run ruff check --fix` 與 `uv run pytest -q tests/test_task_queue.py`，任務佇列這種容易 regress 的模組就有了安全網。

## 給 Claude Code 的提示詞
```
實作 services/task_queue.py、run_full 階段權重、routers/tasks.py、所有 202 路由與 409 檢查、專案 failed 狀態。
寫 tests/test_task_queue.py：正常完成、拋錯、取消（fn 內 sleep 10 秒）三個案例。
在 8001 跑完整流程每秒 GET task 把進度列給我，中途 cancel 一次並確認沒有殘留 ffmpeg 程序。
```

## 今日檢查清單
- [ ] 進度 0→1 平滑，訊息對應階段，`scene_id` 正確。
- [ ] 取消後 5 秒內 cancelled、無殭屍 ffmpeg。
- [ ] 重啟後舊任務 interrupted，續跑不重做已完成場景。

## 明日預告
Day 21 REST API 整理：schemas、錯誤格式、Swagger 分組、`docs/API.md` 與前端型別。
