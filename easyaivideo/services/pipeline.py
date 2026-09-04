"""The generation pipeline: script -> per-scene assets -> rendered video, plus series analysis/planning."""

from __future__ import annotations

import asyncio
import re
import secrets
from pathlib import Path
from typing import Awaitable, Callable, Optional

from ..config import AppConfig, config_manager
from ..db import Database
from ..models import AssetKind, Character, Episode, Line, Location, Overview, Project, Scene
from ..presets import style_prompt
from ..prompts import analyze_document_prompt, episode_script_prompt, episode_titles_prompt, image_prompts_prompt, topic_script_prompt
from ..providers.base import ProviderError, VideoRequest
from ..providers.registry import get_image, get_llm, get_tts, get_video
from . import ffmpeg, series, storage
from .overlay import render_overlay
from .text_split import split_script

Progress = Callable[[float, str], Awaitable[None]]
SCENE_TAIL_SECONDS = 0.35
LINE_GAP_SECONDS = 0.3
IMAGE_CONCURRENCY = 3
DEFAULT_MOTION_HINT = "slow cinematic camera movement, subtle natural motion, consistent characters and lighting"

_SPEAKABLE = re.compile(r"[A-Za-z0-9぀-ヿ㐀-鿿가-힯]")


class PipelineError(RuntimeError):
    pass


def speakable(text: str) -> bool:
    return bool(_SPEAKABLE.search(text))


def _required_kinds(project: Project) -> list[AssetKind]:
    kinds: list[AssetKind] = ["audio", "image"]
    if project.motion == "ai_video":
        kinds.append("video")
    return kinds


def refresh_scene_status(project: Project, scene: Scene) -> None:
    if scene.error:
        scene.status = "failed"
        return
    have = {
        "audio": bool(scene.audio_path) and not scene.audio_stale and storage.abs_path(scene.audio_path).exists(),
        "image": bool(scene.image_path) and not scene.image_stale and storage.abs_path(scene.image_path).exists(),
        "video": bool(scene.video_path) and not scene.video_stale and storage.abs_path(scene.video_path).exists(),
    }
    required = _required_kinds(project)
    done = sum(1 for k in required if have[k])
    scene.status = "ready" if done == len(required) else ("partial" if done else "pending")


def refresh_project_status(project: Project) -> None:
    for scene in project.scenes:
        refresh_scene_status(project, scene)
    all_ready = all(s.status == "ready" for s in project.scenes)
    final_ok = bool(project.final_video_path) and storage.abs_path(project.final_video_path or "").exists()
    segments_current = all(bool(s.segment_path) and storage.abs_path(s.segment_path).exists() for s in project.scenes)
    if not project.scenes:
        project.status = "draft"
    elif final_ok and all_ready and segments_current:
        project.status = "rendered"
    elif all_ready:
        project.status = "assets_ready"
    else:
        project.status = "scripted"


def _mentioned_characters(scene: Scene, characters: list[Character]) -> list[Character]:
    text = scene.narration + " " + " ".join(ln.speaker or "" for ln in scene.lines) + " " + scene.image_prompt
    return [c for c in characters if c.name and c.name in text]


def _ensure_appearance(image_prompt: str, mentioned: list[Character]) -> str:
    """Append character appearance text to an image prompt when a character is mentioned but not described."""
    extra = [c.appearance for c in mentioned if c.appearance and c.appearance[:25].lower() not in image_prompt.lower()]
    return image_prompt + (", " + ", ".join(extra) if extra else "")


def video_prompt_for(scene: Scene, style: str) -> str:
    base = scene.video_prompt.strip() or f"{DEFAULT_MOTION_HINT}. {scene.image_prompt.strip()}"
    return f"{base}, {style}".strip(", ") if style and style.lower() not in base.lower() else base


class Pipeline:
    def __init__(self, db: Database) -> None:
        self.db = db

    async def _load_series(self, project: Project) -> Optional[Project]:
        if project.kind == "episode" and project.parent_id:
            return await self.db.get_project(project.parent_id)
        return None

    def _reset_scenes(self, project: Project) -> None:
        for scene in project.scenes:
            for rel in (scene.audio_path, scene.image_path, scene.video_path, scene.segment_path):
                storage.remove(rel)
        project.scenes = []
        project.scene_counter = 0
        project.final_video_path = None
        project.final_video_duration = None
        project.final_video_size = None

    # ------------------------------------------------------------ script
    async def generate_script(self, project: Project, progress: Progress) -> Project:
        if project.input_mode == "novel":
            return await self._generate_episode_script(project, progress)
        cfg = config_manager.get()
        llm = get_llm(cfg)
        style = project.style_prompt or style_prompt(project.style_id)
        await progress(0.05, "正在撰寫腳本…")

        if project.input_mode == "script":
            segments = split_script(project.topic, project.language)
            if not segments:
                raise PipelineError("文稿內容是空的，請先輸入文字。")
            data = await llm.complete_json(image_prompts_prompt(segments, project.language, style))
            prompts = [str(p) for p in data.get("image_prompts", [])]
            videos = [str(p) for p in data.get("video_prompts", [])]
            if len(prompts) < len(segments):
                prompts += [segments[i][:100] for i in range(len(prompts), len(segments))]
            scenes_data = [
                {"narration": s, "image_prompt": prompts[i], "video_prompt": videos[i] if i < len(videos) else ""}
                for i, s in enumerate(segments)
            ]
        else:
            if not project.topic.strip():
                raise PipelineError("請先輸入主題。")
            data = await llm.complete_json(topic_script_prompt(project.topic, project.n_scenes, project.language, style))
            scenes_data = [
                {
                    "narration": str(s.get("narration", "")).strip(),
                    "image_prompt": str(s.get("image_prompt", "")).strip(),
                    "video_prompt": str(s.get("video_prompt", "") or "").strip(),
                }
                for s in data.get("scenes", [])
                if isinstance(s, dict) and str(s.get("narration", "")).strip()
            ]
            if not scenes_data:
                raise PipelineError("LLM 沒有回傳任何場景，請檢查 LLM 設定後重試。")

        title = str(data.get("title") or "").strip()
        if title and (not project.title or project.title == project.topic[:30]):
            project.title = title[:40]

        self._reset_scenes(project)
        for item in scenes_data:
            project.scenes.append(Scene(id=project.next_scene_id(), **item))
        project.reindex()
        refresh_project_status(project)
        await self.db.save_project(project)
        await progress(1.0, f"腳本完成，共 {len(project.scenes)} 個場景")
        return project

    async def _generate_episode_script(self, project: Project, progress: Progress) -> Project:
        cfg = config_manager.get()
        llm = get_llm(cfg)
        parent = await self._load_series(project)
        ctx = series.series_context(project, parent)
        style = project.style_prompt or style_prompt(project.style_id)
        excerpt = project.topic
        episode_title = project.title
        if parent is not None and project.episode_index:
            ep = next((e for e in parent.episodes if e.index == project.episode_index), None)
            if ep is not None:
                fresh = series.episode_excerpt(parent, ep)
                if fresh.strip():
                    excerpt = fresh
                    project.topic = fresh
                episode_title = ep.title or episode_title
        if not excerpt.strip():
            raise PipelineError("這一集沒有文字內容，請先匯入文檔並規劃分集。")

        await progress(0.05, "正在改編本集腳本…")
        data = await llm.complete_json(
            episode_script_prompt(
                mode=project.content_mode, excerpt=excerpt, language=project.language,
                target_seconds=project.episode_target_seconds, style_prompt=style,
                overview=ctx.overview, characters=ctx.characters, locations=ctx.locations, episode_title=episode_title,
            )
        )
        raw_scenes = [s for s in data.get("scenes", []) if isinstance(s, dict)]
        if not raw_scenes:
            raise PipelineError("LLM 沒有回傳任何場景，請檢查 LLM 設定後重試。")

        self._reset_scenes(project)
        for item in raw_scenes:
            scene = Scene(id=project.next_scene_id())
            scene.location = (str(item.get("location")) if item.get("location") else None)
            if project.content_mode == "drama":
                lines: list[Line] = []
                for ln in item.get("lines", []) or []:
                    if not isinstance(ln, dict):
                        continue
                    text = str(ln.get("text", "")).strip()
                    if not speakable(text):
                        if lines:  # glue stray punctuation (e.g. a closing quote) onto the previous line
                            lines[-1].text += text
                        continue
                    speaker = ln.get("speaker")
                    speaker = str(speaker).strip() if speaker else None
                    if speaker and speaker.lower() in ("narrator", "旁白", "null", "none"):
                        speaker = None
                    lines.append(Line(speaker=speaker, text=text))
                if not lines and str(item.get("narration", "")).strip():
                    lines = [Line(text=str(item["narration"]).strip())]
                if not lines:
                    continue
                scene.lines = lines
                scene.narration = scene.display_text()
            else:
                scene.narration = str(item.get("narration", "")).strip()
                if not scene.narration:
                    continue
            scene.image_prompt = str(item.get("image_prompt", "")).strip()
            scene.image_prompt = _ensure_appearance(scene.image_prompt, _mentioned_characters(scene, ctx.characters))
            scene.video_prompt = str(item.get("video_prompt", "") or "").strip()
            project.scenes.append(scene)
        if not project.scenes:
            raise PipelineError("LLM 回傳的場景沒有可用的文字。")
        project.reindex()
        refresh_project_status(project)
        await self.db.save_project(project)
        await progress(1.0, f"本集腳本完成，共 {len(project.scenes)} 個場景")
        return project

    # ------------------------------------------------------------ assets
    async def generate_assets(
        self,
        project: Project,
        progress: Progress,
        scene_ids: Optional[list[str]] = None,
        kinds: Optional[list[AssetKind]] = None,
        force: bool = False,
    ) -> Project:
        if not project.scenes:
            raise PipelineError("專案還沒有場景，請先產生腳本。")
        cfg = config_manager.get()
        wanted = set(kinds or _required_kinds(project))
        targets = [s for s in project.scenes if scene_ids is None or s.id in scene_ids]
        if not targets:
            raise PipelineError("找不到指定的場景。")
        ctx = series.series_context(project, await self._load_series(project))

        need_video = project.motion == "ai_video" and "video" in wanted
        video_provider = get_video(cfg) if need_video else None
        if need_video and video_provider is None:
            raise PipelineError("此專案使用「AI 影片生成」，但設定中的 video.provider 是 kenburns。請在設定頁改為 agnes 或 comfyui。")
        video_mode = project.video_mode or cfg.video.mode

        jobs: list[tuple[Scene, set[str]]] = []
        for scene in targets:
            todo: set[str] = set()
            has_audio = bool(scene.audio_path) and storage.abs_path(scene.audio_path).exists()
            has_image = bool(scene.image_path) and storage.abs_path(scene.image_path).exists()
            has_video = bool(scene.video_path) and storage.abs_path(scene.video_path).exists()
            if "audio" in wanted and (force or not has_audio or scene.audio_stale):
                todo.add("audio")
            if "image" in wanted and (force or not has_image or scene.image_stale):
                todo.add("image")
            if need_video and (force or not has_video or scene.video_stale or "image" in todo):
                todo.add("video")
            if todo:
                scene.error = None
                jobs.append((scene, todo))

        total_steps = sum(len(t) for _, t in jobs) or 1
        done_steps = 0
        lock = asyncio.Lock()

        async def step_done(msg: str) -> None:
            nonlocal done_steps
            async with lock:
                done_steps += 1
                await self.db.save_project(project)
                await progress(min(done_steps / total_steps, 0.99), msg)

        if not jobs:
            await progress(1.0, "所有素材都已是最新")
            refresh_project_status(project)
            await self.db.save_project(project)
            return project

        tts = get_tts(cfg) if any("audio" in t for _, t in jobs) else None
        image = get_image(cfg) if any("image" in t for _, t in jobs) else None
        image_sem = asyncio.Semaphore(IMAGE_CONCURRENCY)
        video_sem = asyncio.Semaphore(cfg.video.concurrency)
        style = project.style_prompt or style_prompt(project.style_id)
        n_total = len(project.scenes)

        def invalidate_segment(scene: Scene) -> None:
            storage.remove(scene.segment_path)
            scene.segment_path = None

        async def do_audio(scene: Scene) -> None:
            assert tts is not None
            rel = storage.scene_rel(project.id, scene.id, "audio", "mp3")
            path = storage.abs_path(rel)
            path.parent.mkdir(parents=True, exist_ok=True)
            spoken = [ln for ln in scene.lines if speakable(ln.text)]
            if scene.lines and not spoken:
                raise ProviderError("這個場景沒有可朗讀的台詞。")
            if not scene.lines and not speakable(scene.narration):
                raise ProviderError("這個場景沒有可朗讀的旁白。")
            if spoken:
                parts: list[Path] = []
                for i, ln in enumerate(spoken):
                    part = path.parent / f"line_{i:02d}_{path.stem[-6:]}.mp3"
                    voice = series.character_voice(ctx, ln.speaker, project.voice)
                    await tts.synthesize(ln.text, voice, project.tts_speed, part)
                    ln.duration = round(await ffmpeg.probe_duration(part), 3)
                    parts.append(part)
                await ffmpeg.concat_audio(parts, LINE_GAP_SECONDS, path)
                for p in parts:
                    p.unlink(missing_ok=True)
            else:
                await tts.synthesize(scene.narration, project.voice, project.tts_speed, path)
            duration = await ffmpeg.probe_duration(path)
            storage.remove(scene.audio_path)
            scene.audio_path, scene.duration, scene.audio_stale = rel, round(duration, 3), False
            invalidate_segment(scene)
            await step_done(f"場景 {scene.index + 1}/{n_total} 語音完成")

        async def do_image(scene: Scene) -> None:
            assert image is not None
            prompt = ", ".join(p for p in (cfg.image.prompt_prefix.strip(), scene.image_prompt.strip(), style.strip()) if p)
            refs: list[Path] = []
            if cfg.image.use_references:
                refs = [storage.abs_path(c.image_path) for c in _mentioned_characters(scene, ctx.characters) if c.image_path]
            rel = storage.scene_rel(project.id, scene.id, "image", "png")
            async with image_sem:
                await image.generate(prompt, cfg.image.negative_prompt, project.width, project.height, storage.abs_path(rel), reference_images=refs)
            storage.remove(scene.image_path)
            scene.image_path, scene.image_stale = rel, False
            scene.video_stale = bool(scene.video_path) and video_mode != "t2v"
            invalidate_segment(scene)
            await step_done(f"場景 {scene.index + 1}/{n_total} 圖片完成")

        async def do_video(scene: Scene) -> None:
            assert video_provider is not None
            start: Optional[Path] = None
            end: Optional[Path] = None
            refs: list[Path] = []
            if video_mode in ("i2v", "keyframes"):
                if not scene.image_path:
                    raise ProviderError("需要先有場景圖片才能做圖生影片。")
                start = storage.abs_path(scene.image_path)
                if video_mode == "keyframes":
                    nxt = project.scenes[scene.index + 1] if scene.index + 1 < len(project.scenes) else None
                    if nxt is not None and nxt.image_path:
                        end = storage.abs_path(nxt.image_path)
            else:
                refs = [storage.abs_path(c.image_path) for c in _mentioned_characters(scene, ctx.characters) if c.image_path]
            rel = storage.scene_rel(project.id, scene.id, "clip", "mp4")
            request = VideoRequest(
                prompt=video_prompt_for(scene, style), duration=(scene.duration or 5.0) + SCENE_TAIL_SECONDS,
                width=project.width, height=project.height, fps=cfg.video.fps, output_path=storage.abs_path(rel),
                start_image=start, end_image=end, reference_images=refs,
            )
            async with video_sem:
                await video_provider.generate(request)
            storage.remove(scene.video_path)
            scene.video_path, scene.video_stale = rel, False
            invalidate_segment(scene)
            await step_done(f"場景 {scene.index + 1}/{n_total} AI 影片完成")

        async def guarded(scene: Scene, coro: Awaitable[None]) -> bool:
            try:
                await coro
                return True
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001 - surfaced per scene
                scene.error = str(exc)[:500]
                refresh_scene_status(project, scene)
                return False

        async def phase_one(scene: Scene, todo: set[str]) -> None:
            if "audio" in todo and not await guarded(scene, do_audio(scene)):
                return
            if "image" in todo:
                await guarded(scene, do_image(scene))
            refresh_scene_status(project, scene)

        await progress(0.01, f"開始產生 {len(jobs)} 個場景的素材…")
        try:
            await asyncio.gather(*(phase_one(scene, todo) for scene, todo in jobs))
            # Videos run after every image exists (keyframes mode needs the next scene's image).
            video_jobs = [scene for scene, todo in jobs if "video" in todo and not scene.error]
            if video_jobs:
                await asyncio.gather(*(guarded(scene, do_video(scene)) for scene in video_jobs))
                for scene in video_jobs:
                    refresh_scene_status(project, scene)
        finally:
            refresh_project_status(project)
            await self.db.save_project(project)

        failed = [s for s in project.scenes if s.error]
        if failed:
            first = failed[0]
            raise PipelineError(f"{len(failed)} 個場景素材失敗。場景 {first.index + 1}: {first.error}")
        await progress(1.0, "素材產生完成")
        return project

    # ------------------------------------------------------------ render
    def _scene_overlays(
        self,
        project: Project,
        scene: Scene,
        scene_dir: Path,
        font_path: str,
        size: int,
        subtitle_position: str = "bottom",
    ) -> tuple[Optional[Path], list[ffmpeg.TimedOverlay]]:
        """Static (title) overlay plus per-line subtitle overlays for drama scenes."""
        title = project.title if project.show_title else None
        spoken = [ln for ln in scene.lines if speakable(ln.text)]
        timed: list[ffmpeg.TimedOverlay] = []
        if project.subtitle_enabled and spoken and all(ln.duration for ln in spoken):
            static = None
            if title:
                static = scene_dir / "overlay_title.png"
                render_overlay(
                    static,
                    project.width,
                    project.height,
                    title=title,
                    subtitle=None,
                    font_path=font_path,
                    subtitle_size=size,
                    subtitle_position=subtitle_position,
                )
            t = 0.0
            for i, ln in enumerate(spoken):
                path = scene_dir / f"overlay_line_{i:02d}.png"
                render_overlay(
                    path,
                    project.width,
                    project.height,
                    title=None,
                    subtitle=ln.text,
                    speaker=ln.speaker,
                    font_path=font_path,
                    subtitle_size=size,
                    subtitle_position=subtitle_position,
                )
                end = t + (ln.duration or 0) + LINE_GAP_SECONDS
                timed.append((path, t, end + (SCENE_TAIL_SECONDS if i == len(spoken) - 1 else 0)))
                t = end
            return static, timed
        subtitle = scene.display_text() if project.subtitle_enabled else None
        if not title and not subtitle:
            return None, []
        static = scene_dir / "overlay.png"
        render_overlay(
            static,
            project.width,
            project.height,
            title=title,
            subtitle=subtitle,
            font_path=font_path,
            subtitle_size=size,
            subtitle_position=subtitle_position,
        )
        return static, []

    async def render(self, project: Project, progress: Progress) -> Project:
        if not project.scenes:
            raise PipelineError("專案還沒有場景，請先產生腳本。")
        missing_audio = [s.index + 1 for s in project.scenes if not s.audio_path or not storage.abs_path(s.audio_path).exists()]
        missing_image = [s.index + 1 for s in project.scenes if not s.image_path or not storage.abs_path(s.image_path).exists()]
        if missing_audio or missing_image:
            details = []
            if missing_audio:
                details.append(f"語音遺失（場景 {missing_audio}）")
            if missing_image:
                details.append(f"圖片遺失（場景 {missing_image}）")
            raise PipelineError(f"無法合成影片：{'、'.join(details)}，請先點擊「產生素材」。")
        if project.motion == "ai_video":
            missing_clip = [s.index + 1 for s in project.scenes if not s.video_path or not storage.abs_path(s.video_path).exists()]
            if missing_clip:
                raise PipelineError(f"無法合成影片：場景 {missing_clip} 缺少 AI 影片片段檔案，請先產生素材。")

        cfg = config_manager.get()
        fps = cfg.video.fps
        font_pref = project.font_family or cfg.render.font_path
        font_size = int(project.font_size * 2.333 * (project.width / 1080.0)) if project.font_size else cfg.render.subtitle_size
        sub_pos = project.subtitle_position or "bottom"

        segments: list[Path] = []
        n = len(project.scenes)
        for i, scene in enumerate(project.scenes):
            await progress(0.05 + 0.75 * i / n, f"合成場景 {i + 1}/{n}…")
            scene_dir = storage.project_dir(project.id) / "scenes" / scene.id
            static, timed = await asyncio.to_thread(
                self._scene_overlays, project, scene, scene_dir, font_pref, font_size, sub_pos
            )
            duration = (scene.duration or await ffmpeg.probe_duration(storage.abs_path(scene.audio_path or ""))) + SCENE_TAIL_SECONDS
            rel = storage.scene_rel(project.id, scene.id, "segment", "mp4")
            await ffmpeg.render_segment(
                output=storage.abs_path(rel), width=project.width, height=project.height, fps=fps, duration=duration,
                audio=storage.abs_path(scene.audio_path or ""),
                image=storage.abs_path(scene.image_path) if scene.image_path else None,
                clip=storage.abs_path(scene.video_path) if (project.motion == "ai_video" and scene.video_path) else None,
                overlay=static, timed_overlays=timed, motion=project.motion, scene_index=i, crf=cfg.render.crf,
            )
            storage.remove(scene.segment_path)
            scene.segment_path = rel
            segments.append(storage.abs_path(rel))
            await self.db.save_project(project)

        await progress(0.85, "串接所有場景…")
        out_dir = storage.project_dir(project.id) / "output"
        out_dir.mkdir(parents=True, exist_ok=True)
        joined = out_dir / "joined.mp4"
        trans = project.transition or "none"
        trans_dur = project.transition_duration or 0.5
        await ffmpeg.concat_with_transitions(
            segments,
            joined,
            transition=trans,
            duration=trans_dur,
            crf=cfg.render.crf,
            fps=fps,
        )
        total = await ffmpeg.probe_duration(joined)

        final_rel = storage.output_rel(project.id, "final", "mp4")
        final_abs = storage.abs_path(final_rel)
        bgm = storage.bgm_path(project.bgm)
        if bgm is not None and project.bgm_volume > 0:
            await progress(0.92, "混入背景音樂…")
            await ffmpeg.mix_bgm(joined, bgm, project.bgm_volume, total, final_abs)
            joined.unlink(missing_ok=True)
        else:
            joined.replace(final_abs)

        storage.remove(project.final_video_path)
        project.final_video_path = final_rel
        project.final_video_duration = round(total, 2)
        project.final_video_size = final_abs.stat().st_size
        refresh_project_status(project)
        await self.db.save_project(project)
        await progress(1.0, "影片合成完成")
        return project

    # ------------------------------------------------------------ full
    async def full(self, project: Project, progress: Progress) -> Project:
        async def scaled(lo: float, hi: float) -> Progress:
            async def cb(p: float, msg: str) -> None:
                await progress(lo + (hi - lo) * p, msg)

            return cb

        if not project.scenes:
            project = await self.generate_script(project, await scaled(0.0, 0.12))
        project = await self.generate_assets(project, await scaled(0.12, 0.72))
        return await self.render(project, await scaled(0.72, 1.0))

    # ------------------------------------------------------------ series
    async def analyze(self, project: Project, progress: Progress) -> Project:
        text = series.read_source(project.id)
        if not text.strip():
            raise PipelineError("尚未匯入任何文檔，請先上傳文字檔或貼上內容。")
        llm = get_llm(config_manager.get())
        await progress(0.1, "正在分析內容、角色與場景…")
        data = await llm.complete_json(analyze_document_prompt(series.excerpt_for_analysis(text), project.language))
        ov = data.get("overview") or {}
        project.overview = Overview(
            synopsis=str(ov.get("synopsis", "")), genre=str(ov.get("genre", "")),
            theme=str(ov.get("theme", "")), world_setting=str(ov.get("world_setting", "")),
        )
        chars: list[Character] = []
        for c in data.get("characters", []) or []:
            if not isinstance(c, dict) or not str(c.get("name", "")).strip():
                continue
            gender = str(c.get("gender", "other")).lower()
            chars.append(Character(
                name=str(c["name"]).strip()[:40], description=str(c.get("description", "")).strip(),
                appearance=str(c.get("appearance", "")).strip(),
                gender="female" if gender.startswith("f") else "male" if gender.startswith("m") else "other",
            ))
        for c in project.characters:
            storage.remove(c.image_path)
        project.characters = chars
        series.assign_character_ids(project)
        project.locations = [
            Location(name=str(loc.get("name", "")).strip()[:40], description=str(loc.get("description", "")).strip())
            for loc in (data.get("locations", []) or []) if isinstance(loc, dict) and str(loc.get("name", "")).strip()
        ]
        if not project.title or project.title == "未命名系列":
            project.title = (project.source_files[0].name.rsplit(".", 1)[0] if project.source_files else project.title)[:40]
        await self.db.save_project(project)
        await progress(1.0, f"分析完成：{len(project.characters)} 個角色，{len(project.locations)} 個場景")
        return project

    async def plan_episodes(self, project: Project, progress: Progress) -> Project:
        text = series.read_source(project.id)
        if not text.strip():
            raise PipelineError("尚未匯入任何文檔，請先上傳文字檔或貼上內容。")
        await progress(0.05, "正在切分集數…")
        ranges = series.split_into_episodes(text, series.chars_per_episode(project))
        if not ranges:
            raise PipelineError("文檔內容太少，無法切分集數。")
        old = {e.index: e for e in project.episodes}
        episodes = [
            Episode(index=i + 1, source_start=s, source_end=e, project_id=old[i + 1].project_id if i + 1 in old else None)
            for i, (s, e) in enumerate(ranges)
        ]
        for idx, ep in old.items():
            if idx > len(episodes) and ep.project_id:
                await self.db.delete_project(ep.project_id)
                storage.delete_project_files(ep.project_id)

        llm = get_llm(config_manager.get())
        batch = 20
        for start in range(0, len(episodes), batch):
            chunk = episodes[start : start + batch]
            await progress(0.1 + 0.85 * start / len(episodes), f"產生集數標題 {start + 1}-{start + len(chunk)}/{len(episodes)}…")
            excerpts = [(ep.index, text[ep.source_start : ep.source_start + 400].strip()) for ep in chunk]
            try:
                data = await llm.complete_json(episode_titles_prompt(excerpts, project.language))
                by_index = {int(e.get("index", 0)): e for e in data.get("episodes", []) if isinstance(e, dict)}
            except Exception:  # noqa: BLE001 - titles are optional
                by_index = {}
            for ep in chunk:
                item = by_index.get(ep.index, {})
                ep.title = str(item.get("title", "")).strip()[:40] or (old[ep.index].title if ep.index in old else "")
                ep.summary = str(item.get("summary", "")).strip()[:400] or (old[ep.index].summary if ep.index in old else "")
        project.episodes = episodes
        await self.db.save_project(project)
        await progress(1.0, f"已規劃 {len(episodes)} 集")
        return project

    async def character_image(self, project: Project, char_id: str, progress: Progress) -> Project:
        ch = next((c for c in project.characters if c.id == char_id), None)
        if ch is None:
            raise PipelineError("找不到角色。")
        if not ch.appearance.strip():
            raise PipelineError("請先填寫角色的外觀描述。")
        cfg: AppConfig = config_manager.get()
        style = project.style_prompt or style_prompt(project.style_id)
        prompt = ", ".join(p for p in (cfg.image.prompt_prefix.strip(), f"character portrait, {ch.appearance.strip()}, upper body, looking at the camera, simple neutral background", style) if p)
        await progress(0.1, f"生成角色圖：{ch.name}…")
        rel = f"{project.id}/characters/{ch.id}_{secrets.token_hex(3)}.png"
        await get_image(cfg).generate(prompt, cfg.image.negative_prompt, 1024, 1024, storage.abs_path(rel))
        storage.remove(ch.image_path)
        ch.image_path = rel
        await self.db.save_project(project)
        await progress(1.0, f"角色圖完成：{ch.name}")
        return project
