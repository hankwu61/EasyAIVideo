"""Project CRUD, scene editing and series (source/episode) operations."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from ..db import Database
from ..models import EpisodeUpdate, Project, ProjectCreate, ProjectUpdate, Scene, SceneCreate, SceneUpdate, new_id
from ..presets import style_prompt
from . import ffmpeg, series, storage
from .pipeline import refresh_project_status
from .source_loader import extract_text


class NotFound(Exception):
    pass


class ProjectService:
    def __init__(self, db: Database) -> None:
        self.db = db

    async def get(self, project_id: str) -> Project:
        project = await self.db.get_project(project_id)
        if project is None:
            raise NotFound(f"Project {project_id} not found")
        project.active_task = await self.db.active_task(project_id)
        if project.kind == "series":
            await series.enrich_episodes(self.db, project)
        return project

    async def list(self, include_episodes: bool = False) -> list[dict[str, Any]]:
        projects = await self.db.list_projects()
        active = {t.project_id: t for t in await self.db.list_tasks(active=True, limit=500)}
        out = []
        for p in projects:
            if p.kind == "episode" and not include_episodes:
                continue
            p.active_task = active.get(p.id)
            out.append(p.summary())
        return out

    async def create(self, body: ProjectCreate) -> Project:
        data = body.model_dump(exclude={"auto_start", "style_prompt", "source_text"})
        project = Project(id=new_id("proj"), **data)
        project.style_prompt = body.style_prompt or style_prompt(body.style_id)
        storage.project_dir(project.id).mkdir(parents=True, exist_ok=True)
        if project.kind == "series":
            project.input_mode = "novel"
            if body.source_text and body.source_text.strip():
                series.append_source(project, "pasted.txt", body.source_text.strip() + "\n")
            if not project.title.strip():
                first = (body.source_text or "").strip().splitlines()
                project.title = (first[0][:30] if first else "未命名系列")
        else:
            if not body.topic.strip():
                raise ValueError("請輸入主題或文稿內容。")
            if not project.title.strip():
                project.title = body.topic.strip().splitlines()[0][:30]
        await self.db.save_project(project)
        return project

    async def update(self, project_id: str, body: ProjectUpdate) -> Project:
        project = await self.get(project_id)
        patch = body.model_dump(exclude_unset=True)
        if "style_id" in patch and "style_prompt" not in patch and patch["style_id"] != project.style_id:
            patch["style_prompt"] = style_prompt(patch["style_id"]) or project.style_prompt
        if body.characters is not None:
            existing = {c.id: c for c in project.characters if c.id}
            for c in body.characters:
                old = existing.get(c.id) if c.id else None
                if old is not None and c.image_path is None:
                    c.image_path = old.image_path
            kept = {c.id for c in body.characters if c.id}
            for cid, old in existing.items():
                if cid not in kept:
                    storage.remove(old.image_path)
            project.characters = list(body.characters)
            series.assign_character_ids(project)
            patch.pop("characters", None)
        for key, value in patch.items():
            if key in ("overview", "locations"):
                setattr(project, key, getattr(body, key))
            else:
                setattr(project, key, value)
        refresh_project_status(project)
        await self.db.save_project(project)
        return await self.get(project_id)

    async def delete(self, project_id: str) -> None:
        project = await self.get(project_id)
        if project.kind == "series":
            for ep in project.episodes:
                if ep.project_id:
                    await self.db.delete_project(ep.project_id)
                    storage.delete_project_files(ep.project_id)
        await self.db.delete_project(project_id)
        storage.delete_project_files(project_id)

    # ---- scenes ---------------------------------------------------------
    def _scene(self, project: Project, scene_id: str) -> Scene:
        scene = project.scene_by_id(scene_id)
        if scene is None:
            raise NotFound(f"Scene {scene_id} not found")
        return scene

    async def update_scene(self, project_id: str, scene_id: str, body: SceneUpdate) -> Project:
        project = await self.get(project_id)
        scene = self._scene(project, scene_id)
        text_changed = False
        if body.lines is not None:
            new_lines = [ln for ln in body.lines if ln.text.strip()]
            if [(ln.speaker, ln.text) for ln in new_lines] != [(ln.speaker, ln.text) for ln in scene.lines]:
                scene.lines = new_lines
                scene.narration = scene.display_text()
                text_changed = True
        if body.narration is not None and body.narration != scene.narration and not scene.lines:
            scene.narration = body.narration
            text_changed = True
        if text_changed:
            scene.audio_stale = bool(scene.audio_path)
            storage.remove(scene.segment_path)
            scene.segment_path = None
        if body.image_prompt is not None and body.image_prompt != scene.image_prompt:
            scene.image_prompt = body.image_prompt
            scene.image_stale = bool(scene.image_path)
        if body.video_prompt is not None and body.video_prompt != scene.video_prompt:
            scene.video_prompt = body.video_prompt
            scene.video_stale = bool(scene.video_path)
        scene.error = None
        refresh_project_status(project)
        await self.db.save_project(project)
        return await self.get(project_id)

    async def add_scene(self, project_id: str, body: SceneCreate) -> Project:
        project = await self.get(project_id)
        scene = Scene(id=project.next_scene_id(), narration=body.narration, image_prompt=body.image_prompt)
        pos = len(project.scenes)
        if body.after:
            pos = next((i + 1 for i, s in enumerate(project.scenes) if s.id == body.after), pos)
        project.scenes.insert(pos, scene)
        project.reindex()
        refresh_project_status(project)
        await self.db.save_project(project)
        return await self.get(project_id)

    async def delete_scene(self, project_id: str, scene_id: str) -> Project:
        project = await self.get(project_id)
        scene = self._scene(project, scene_id)
        for rel in (scene.audio_path, scene.image_path, scene.video_path, scene.segment_path):
            storage.remove(rel)
        project.scenes = [s for s in project.scenes if s.id != scene_id]
        project.reindex()
        refresh_project_status(project)
        await self.db.save_project(project)
        return await self.get(project_id)

    async def reorder(self, project_id: str, scene_ids: list[str]) -> Project:
        project = await self.get(project_id)
        by_id = {s.id: s for s in project.scenes}
        if sorted(scene_ids) != sorted(by_id):
            raise ValueError("scene_ids must contain every scene exactly once")
        project.scenes = [by_id[i] for i in scene_ids]
        project.reindex()
        await self.db.save_project(project)
        return await self.get(project_id)

    async def upload_asset(self, project_id: str, scene_id: str, kind: str, filename: str, data: bytes) -> Project:
        project = await self.get(project_id)
        scene = self._scene(project, scene_id)
        ext = (Path(filename).suffix.lstrip(".") or {"image": "png", "audio": "mp3", "video": "mp4"}[kind]).lower()
        stem = {"image": "image", "audio": "audio", "video": "clip"}[kind]
        if kind == "image":
            try:
                from io import BytesIO

                from PIL import Image

                with Image.open(BytesIO(data)) as img:
                    img.verify()
                    ext = (img.format or "png").lower().replace("jpeg", "jpg")
            except Exception as exc:  # noqa: BLE001
                raise ValueError("上傳的檔案不是有效的圖片（支援 png / jpg / webp）。") from exc
        rel = storage.scene_rel(project.id, scene.id, stem, ext)
        path = storage.abs_path(rel)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        if kind != "image":
            try:
                probed = await ffmpeg.probe_duration(path)
            except Exception as exc:  # noqa: BLE001
                path.unlink(missing_ok=True)
                raise ValueError("上傳的檔案無法被 ffmpeg 讀取，請確認是有效的音訊／影片檔。") from exc
        if kind == "image":
            storage.remove(scene.image_path)
            scene.image_path, scene.image_stale = rel, False
            scene.video_stale = bool(scene.video_path)  # the clip's first frame changed
        elif kind == "audio":
            storage.remove(scene.audio_path)
            scene.audio_path, scene.audio_stale = rel, False
            scene.duration = round(probed, 3)
            for ln in scene.lines:
                ln.duration = None  # per-line timing unknown for uploaded audio
        else:
            storage.remove(scene.video_path)
            scene.video_path, scene.video_stale = rel, False
        storage.remove(scene.segment_path)
        scene.segment_path = None
        scene.error = None
        refresh_project_status(project)
        await self.db.save_project(project)
        return await self.get(project_id)

    # ---- series ---------------------------------------------------------
    async def upload_source(self, project_id: str, filename: str, data: bytes) -> Project:
        project = await self.get(project_id)
        text = extract_text(filename, data)
        series.append_source(project, Path(filename).name, text)
        if not project.title.strip() or project.title == "未命名系列":
            project.title = Path(filename).stem[:40]
        await self.db.save_project(project)
        return await self.get(project_id)

    async def source_text(self, project_id: str, offset: int, limit: int) -> dict[str, Any]:
        await self.get(project_id)
        text = series.read_source(project_id)
        return {"text": text[offset : offset + limit], "total_chars": len(text), "offset": offset}

    async def clear_source(self, project_id: str) -> Project:
        project = await self.get(project_id)
        for ep in project.episodes:
            if ep.project_id:
                await self.db.delete_project(ep.project_id)
                storage.delete_project_files(ep.project_id)
        series.clear_source(project)
        await self.db.save_project(project)
        return await self.get(project_id)

    async def update_episode(self, project_id: str, index: int, body: EpisodeUpdate) -> Project:
        project = await self.get(project_id)
        ep = series.episode_by_index(project, index)
        if body.title is not None:
            ep.title = body.title.strip()[:40]
        if body.summary is not None:
            ep.summary = body.summary.strip()[:400]
        await self.db.save_project(project)
        return await self.get(project_id)

    async def create_episode(self, project_id: str, index: int) -> Project:
        project = await self.get(project_id)
        if project.kind != "series":
            raise ValueError("只有系列專案可以建立集數。")
        await series.create_episode(self.db, project, index)
        return await self.get(project_id)

    async def episode_project_id(self, project_id: str, index: int) -> str:
        project = await self.get(project_id)
        if project.kind != "series":
            raise ValueError("只有系列專案可以建立集數。")
        child = await series.create_episode(self.db, project, index)
        return child.id

    async def scene_path(self, project_id: str, scene_id: str) -> Optional[Path]:
        project = await self.get(project_id)
        scene = self._scene(project, scene_id)
        return storage.abs_path(scene.image_path) if scene.image_path else None
