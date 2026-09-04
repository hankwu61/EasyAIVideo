"""Application-wide singletons wired at import time."""

from __future__ import annotations

from .db import db
from .services.pipeline import Pipeline
from .services.project_service import ProjectService
from .services.scheduler import PublishScheduler
from .services.task_queue import TaskQueue

pipeline = Pipeline(db)
task_queue = TaskQueue(db, pipeline)
projects = ProjectService(db)
publish_scheduler = PublishScheduler(db, task_queue)
