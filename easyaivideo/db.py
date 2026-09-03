"""SQLite persistence (SQLAlchemy async) for projects and tasks."""

from __future__ import annotations

import json
from typing import Optional

from sqlalchemy import Float, String, Text, delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from .config import DB_PATH, ensure_dirs
from .models import Project, Task


class Base(DeclarativeBase):
    pass


class ProjectRow(Base):
    __tablename__ = "projects"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    created_at: Mapped[str] = mapped_column(String(40))
    updated_at: Mapped[str] = mapped_column(String(40))
    data: Mapped[str] = mapped_column(Text)


class TaskRow(Base):
    __tablename__ = "tasks"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(32), index=True)
    type: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(16), index=True)
    progress: Mapped[float] = mapped_column(Float, default=0.0)
    message: Mapped[str] = mapped_column(Text, default="")
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    payload: Mapped[str] = mapped_column(Text, default="{}")
    result: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(String(40))
    started_at: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    finished_at: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)


class Database:
    def __init__(self) -> None:
        ensure_dirs()
        self.engine = create_async_engine(f"sqlite+aiosqlite:///{DB_PATH.as_posix()}", echo=False)
        self.session = async_sessionmaker(self.engine, expire_on_commit=False)

    async def init(self) -> None:
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def close(self) -> None:
        await self.engine.dispose()

    # ---- projects -------------------------------------------------------
    async def list_projects(self) -> list[Project]:
        async with self.session() as s:
            rows = (await s.execute(select(ProjectRow).order_by(ProjectRow.created_at.desc()))).scalars().all()
            return [Project.model_validate_json(r.data) for r in rows]

    async def get_project(self, project_id: str) -> Optional[Project]:
        async with self.session() as s:
            row = await s.get(ProjectRow, project_id)
            return Project.model_validate_json(row.data) if row else None

    async def save_project(self, project: Project) -> Project:
        from .models import now_iso

        project.updated_at = now_iso()
        payload = project.model_dump_json(exclude={"active_task"})
        async with self.session() as s:
            row = await s.get(ProjectRow, project.id)
            if row is None:
                s.add(ProjectRow(id=project.id, created_at=project.created_at, updated_at=project.updated_at, data=payload))
            else:
                row.updated_at = project.updated_at
                row.data = payload
            await s.commit()
        return project

    async def delete_project(self, project_id: str) -> None:
        async with self.session() as s:
            await s.execute(delete(ProjectRow).where(ProjectRow.id == project_id))
            await s.execute(delete(TaskRow).where(TaskRow.project_id == project_id))
            await s.commit()

    # ---- tasks ----------------------------------------------------------
    @staticmethod
    def _task_from_row(r: TaskRow) -> Task:
        return Task(
            id=r.id, project_id=r.project_id, type=r.type, status=r.status, progress=r.progress,  # type: ignore[arg-type]
            message=r.message, error=r.error, payload=json.loads(r.payload or "{}"),
            result=json.loads(r.result) if r.result else None,
            created_at=r.created_at, started_at=r.started_at, finished_at=r.finished_at,
        )

    async def save_task(self, task: Task) -> Task:
        async with self.session() as s:
            row = await s.get(TaskRow, task.id)
            values = dict(
                project_id=task.project_id, type=task.type, status=task.status, progress=task.progress,
                message=task.message, error=task.error, payload=json.dumps(task.payload, ensure_ascii=False),
                result=json.dumps(task.result, ensure_ascii=False) if task.result is not None else None,
                created_at=task.created_at, started_at=task.started_at, finished_at=task.finished_at,
            )
            if row is None:
                s.add(TaskRow(id=task.id, **values))
            else:
                for k, v in values.items():
                    setattr(row, k, v)
            await s.commit()
        return task

    async def get_task(self, task_id: str) -> Optional[Task]:
        async with self.session() as s:
            row = await s.get(TaskRow, task_id)
            return self._task_from_row(row) if row else None

    async def list_tasks(self, project_id: Optional[str] = None, active: bool = False, limit: int = 50) -> list[Task]:
        async with self.session() as s:
            stmt = select(TaskRow).order_by(TaskRow.created_at.desc()).limit(limit)
            if project_id:
                stmt = stmt.where(TaskRow.project_id == project_id)
            if active:
                stmt = stmt.where(TaskRow.status.in_(["queued", "running"]))
            rows = (await s.execute(stmt)).scalars().all()
            return [self._task_from_row(r) for r in rows]

    async def active_task(self, project_id: str) -> Optional[Task]:
        tasks = await self.list_tasks(project_id=project_id, active=True, limit=1)
        return tasks[0] if tasks else None

    async def fail_unfinished_tasks(self, reason: str) -> None:
        from .models import now_iso

        async with self.session() as s:
            rows = (await s.execute(select(TaskRow).where(TaskRow.status.in_(["queued", "running"])))).scalars().all()
            for r in rows:
                r.status = "failed"
                r.error = reason
                r.finished_at = now_iso()
            await s.commit()


db = Database()
