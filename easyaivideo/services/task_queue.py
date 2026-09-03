"""In-process task queue: one worker, one active task per project, cancellable."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Optional

from ..db import Database
from ..models import Task, TaskType, new_id, now_iso
from ..providers.base import ProviderError
from .ffmpeg import FFmpegError
from .pipeline import Pipeline, PipelineError, refresh_project_status

log = logging.getLogger("easyaivideo.tasks")


class ActiveTaskError(Exception):
    def __init__(self, task: Task) -> None:
        super().__init__(f"Project already has an active task: {task.id}")
        self.task = task


class TaskQueue:
    def __init__(self, db: Database, pipeline: Pipeline) -> None:
        self.db = db
        self.pipeline = pipeline
        self._queue: asyncio.Queue[str] = asyncio.Queue()
        self._worker: Optional[asyncio.Task[None]] = None
        self._current: Optional[asyncio.Task[Any]] = None
        self._current_id: Optional[str] = None
        self._submit_lock = asyncio.Lock()

    async def start(self) -> None:
        await self.db.fail_unfinished_tasks("伺服器重新啟動，任務已中斷。")
        self._worker = asyncio.create_task(self._run(), name="easyaivideo-worker")

    async def stop(self) -> None:
        if self._current:
            self._current.cancel()
        if self._worker:
            self._worker.cancel()
            try:
                await self._worker
            except asyncio.CancelledError:
                pass

    async def submit(self, project_id: str, task_type: TaskType, payload: Optional[dict[str, Any]] = None) -> Task:
        async with self._submit_lock:
            active = await self.db.active_task(project_id)
            if active:
                raise ActiveTaskError(active)
            task = Task(id=new_id("task"), project_id=project_id, type=task_type, payload=payload or {}, message="等待中…")
            await self.db.save_task(task)
            await self._queue.put(task.id)
            return task

    async def cancel(self, task_id: str) -> Optional[Task]:
        task = await self.db.get_task(task_id)
        if task is None:
            return None
        if task.status == "queued":
            task.status = "cancelled"
            task.finished_at = now_iso()
            task.message = "已取消"
            await self.db.save_task(task)
        elif task.status == "running" and self._current_id == task_id and self._current:
            self._current.cancel()
            task.message = "取消中…"
        return task

    async def _run(self) -> None:
        while True:
            task_id = await self._queue.get()
            try:
                await self._execute(task_id)
            except asyncio.CancelledError:
                raise
            except Exception:  # noqa: BLE001
                log.exception("worker crashed on task %s", task_id)

    async def _execute(self, task_id: str) -> None:
        task = await self.db.get_task(task_id)
        if task is None or task.status != "queued":
            return
        project = await self.db.get_project(task.project_id)
        if project is None:
            task.status, task.error, task.finished_at = "failed", "專案不存在", now_iso()
            await self.db.save_task(task)
            return

        task.status, task.started_at, task.message = "running", now_iso(), "開始執行…"
        await self.db.save_task(task)

        async def progress(p: float, msg: str) -> None:
            task.progress = max(0.0, min(1.0, p))
            task.message = msg
            await self.db.save_task(task)

        async def handler() -> dict[str, Any]:
            payload = task.payload
            if task.type == "script":
                result = await self.pipeline.generate_script(project, progress)
            elif task.type == "assets":
                result = await self.pipeline.generate_assets(
                    project, progress, scene_ids=payload.get("scene_ids"), kinds=payload.get("kinds"), force=bool(payload.get("force"))
                )
            elif task.type == "render":
                result = await self.pipeline.render(project, progress)
            elif task.type == "analyze":
                result = await self.pipeline.analyze(project, progress)
            elif task.type == "plan":
                result = await self.pipeline.plan_episodes(project, progress)
            elif task.type == "character_image":
                result = await self.pipeline.character_image(project, str(payload.get("char_id", "")), progress)
            else:
                result = await self.pipeline.full(project, progress)
            return {"status": result.status, "final_video_url": result.final_video_url, "scene_count": len(result.scenes)}

        self._current = asyncio.create_task(handler())
        self._current_id = task_id
        try:
            await asyncio.wait({self._current})
            inner = self._current
            if inner.cancelled():
                task.status, task.message = "cancelled", "已取消"
            elif inner.exception() is not None:
                exc = inner.exception()
                task.status = "failed"
                if isinstance(exc, (PipelineError, ProviderError, FFmpegError)):
                    task.error = str(exc)
                else:
                    log.exception("task %s failed", task_id, exc_info=exc)
                    task.error = f"{type(exc).__name__}: {exc}"
                task.message = "失敗"
            else:
                task.status, task.progress, task.result = "succeeded", 1.0, inner.result()
                task.message = task.message or "完成"
        finally:
            task.finished_at = now_iso()
            await self.db.save_task(task)
            self._current = None
            self._current_id = None
            latest = await self.db.get_project(project.id)
            if latest is not None and task.status in ("cancelled", "failed") and latest.kind != "series":
                refresh_project_status(latest)
                await self.db.save_project(latest)
