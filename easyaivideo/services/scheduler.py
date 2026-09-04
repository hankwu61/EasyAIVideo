"""Background scheduler for scheduled video publishing."""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

from ..db import Database
from ..models import now_iso
from . import storage
from .task_queue import ActiveTaskError, TaskQueue

log = logging.getLogger("easyaivideo.scheduler")


class PublishScheduler:
    """Checks for scheduled publishing jobs that have reached their trigger time."""

    def __init__(self, db: Database, task_queue: TaskQueue, interval_seconds: float = 20.0) -> None:
        self.db = db
        self.task_queue = task_queue
        self.interval_seconds = interval_seconds
        self._worker: Optional[asyncio.Task[None]] = None

    async def start(self) -> None:
        self._worker = asyncio.create_task(self._run(), name="publish-scheduler")
        log.info("PublishScheduler started (interval=%.1fs)", self.interval_seconds)

    async def stop(self) -> None:
        if self._worker:
            self._worker.cancel()
            try:
                await self._worker
            except asyncio.CancelledError:
                pass
            self._worker = None

    async def _run(self) -> None:
        while True:
            try:
                await self.check_and_trigger()
            except asyncio.CancelledError:
                raise
            except Exception:  # noqa: BLE001
                log.exception("Error in PublishScheduler tick")
            await asyncio.sleep(self.interval_seconds)

    async def check_and_trigger(self) -> None:
        now = now_iso()
        projects = await self.db.list_projects()
        for p in projects:
            if p.publish_status != "scheduled":
                continue
            sched_time = p.publish_settings.schedule_time
            if not sched_time or sched_time > now:
                continue

            # Project is due for publishing!
            if not p.final_video_path or not storage.abs_path(p.final_video_path).exists():
                log.warning("Project %s is scheduled for publish but final video does not exist yet", p.id)
                continue

            try:
                await self.task_queue.submit(
                    p.id,
                    "publish",
                    payload={
                        "platforms": p.publish_settings.platforms,
                        "privacy": p.publish_settings.privacy,
                        "schedule_time": sched_time,
                    },
                )
                log.info("Triggered scheduled publish for project %s", p.id)
            except ActiveTaskError:
                # Already running another task, will retry on next tick
                pass
