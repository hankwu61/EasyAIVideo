"""AI review: keyframes of the rendered video + narration -> multimodal model -> issues per scene."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Awaitable, Callable, Optional

from ..config import config_manager
from ..db import Database
from ..models import Project, ProjectReview, Scene, SceneReview, now_iso
from ..prompts import review_scene_prompt, review_summary_prompt
from ..providers.base import ProviderError
from ..providers.registry import get_llm, get_vision
from . import ffmpeg, series, storage

Progress = Callable[[float, str], Awaitable[None]]
SCENE_TAIL_SECONDS = 0.35


class ReviewError(RuntimeError):
    pass


def _frame_times(duration: float, n: int) -> list[float]:
    fractions = {1: [0.5], 2: [0.25, 0.7], 3: [0.15, 0.5, 0.85]}[max(1, min(n, 3))]
    return [max(0.0, min(duration * f, duration - 0.1)) for f in fractions]


async def extract_scene_frames(project: Project, scene: Scene, n: int, width: int) -> list[str]:
    """Keyframes from the rendered segment; falls back to the final video by offset, then the still image."""
    scene_dir = storage.project_dir(project.id) / "scenes" / scene.id
    for old in scene_dir.glob("review_*.jpg"):
        old.unlink(missing_ok=True)
    duration = (scene.duration or 4.0) + SCENE_TAIL_SECONDS
    source: Optional[Path] = None
    offset = 0.0
    if scene.segment_path and storage.abs_path(scene.segment_path).exists():
        source = storage.abs_path(scene.segment_path)
    elif project.final_video_path and storage.abs_path(project.final_video_path).exists():
        source = storage.abs_path(project.final_video_path)
        offset = sum((s.duration or 4.0) + SCENE_TAIL_SECONDS for s in project.scenes if s.index < scene.index)
    if source is None:
        if scene.image_path and storage.abs_path(scene.image_path).exists():
            return [scene.image_path]
        raise ReviewError("沒有可用的畫面（尚未合成影片，也沒有場景圖）。")
    rels: list[str] = []
    for i, t in enumerate(_frame_times(duration, n)):
        rel = f"{project.id}/scenes/{scene.id}/review_{i}_{now_iso()[11:19].replace(':', '')}.jpg"
        await ffmpeg.extract_frame(source, offset + t, storage.abs_path(rel), width)
        rels.append(rel)
    return rels


class ReviewService:
    def __init__(self, db: Database) -> None:
        self.db = db

    async def run(self, project: Project, progress: Progress) -> Project:
        if not project.scenes:
            raise ReviewError("專案還沒有場景。")
        if not (project.final_video_path and storage.abs_path(project.final_video_path).exists()):
            raise ReviewError("請先合成影片，AI 審片會檢查成品的關鍵幀。")
        cfg = config_manager.get()
        vision = get_vision(cfg)
        parent = await self.db.get_project(project.parent_id) if (project.kind == "episode" and project.parent_id) else None
        ctx = series.series_context(project, parent)
        n = len(project.scenes)
        results: dict[str, SceneReview] = {}
        done = 0
        lock = asyncio.Lock()
        sem = asyncio.Semaphore(cfg.review.concurrency)

        async def review_scene(scene: Scene) -> None:
            nonlocal done
            item = SceneReview(scene_id=scene.id, index=scene.index)
            try:
                item.frame_paths = await extract_scene_frames(project, scene, cfg.review.frames_per_scene, cfg.review.frame_width)
                prompt = review_scene_prompt(
                    index=scene.index + 1, total=n, narration=scene.display_text(), image_prompt=scene.image_prompt,
                    language=project.language, n_frames=len(item.frame_paths), characters=ctx.characters, title=project.title,
                )
                async with sem:
                    data = await vision.complete_json_with_images(prompt, [storage.abs_path(p) for p in item.frame_paths])
                item.score = max(1, min(5, int(data.get("score", 3) or 3)))
                item.match = bool(data.get("match", item.score >= 3))
                item.issues = [str(x).strip() for x in (data.get("issues") or []) if str(x).strip()][:8]
                item.suggested_image_prompt = str(data.get("suggested_image_prompt") or "").strip()
                item.note = str(data.get("note") or "").strip()
            except asyncio.CancelledError:
                raise
            except (ProviderError, ReviewError, ffmpeg.FFmpegError, ValueError) as exc:
                item.error = str(exc)[:400]
            results[scene.id] = item
            async with lock:
                done += 1
                await progress(0.05 + 0.8 * done / n, f"審片 {done}/{n}…")

        await progress(0.02, "抽取關鍵幀並送交模型…")
        await asyncio.gather(*(review_scene(s) for s in project.scenes))
        ordered = [results[s.id] for s in project.scenes if s.id in results]

        failures = [r for r in ordered if r.error]
        if len(failures) == len(ordered):
            raise ReviewError(f"所有場景審片失敗：{failures[0].error}")

        await progress(0.9, "整理審片摘要…")
        summary = ""
        try:
            lines = [f"{r.index + 1} | {r.score} | {'; '.join(r.issues) or '-'}" for r in ordered if not r.error]
            data = await get_llm(cfg).complete_json(review_summary_prompt(project.title, project.language, lines))
            summary = str(data.get("summary") or "").strip()
        except Exception:  # noqa: BLE001 - summary is optional
            summary = ""
        if not summary:
            low = [str(r.index + 1) for r in ordered if not r.error and r.score <= 2]
            summary = (f"共 {len(ordered)} 個場景，{len(low)} 個需要修正（場景 {', '.join(low)}）。" if low else f"共 {len(ordered)} 個場景，畫面與旁白大致相符。")

        project.review = ProjectReview(model=getattr(vision, "model", ""), video_path=project.final_video_path, summary=summary, scenes=ordered)
        await self.db.save_project(project)
        await progress(1.0, f"審片完成：{project.review.issue_count} 個問題")
        return project
