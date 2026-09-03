from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status

from ..db import db
from ..deps import task_queue
from ..models import Task

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


@router.get("", response_model=list[Task])
async def list_tasks(
    project_id: Optional[str] = None,
    active: bool = False,
    limit: int = Query(50, ge=1, le=500),
) -> list[Task]:
    return await db.list_tasks(project_id=project_id, active=active, limit=limit)


@router.get("/{task_id}", response_model=Task)
async def get_task(task_id: str) -> Task:
    task = await db.get_task(task_id)
    if task is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "task not found")
    return task


@router.post("/{task_id}/cancel", response_model=Task)
async def cancel_task(task_id: str) -> Task:
    task = await task_queue.cancel(task_id)
    if task is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "task not found")
    return task
