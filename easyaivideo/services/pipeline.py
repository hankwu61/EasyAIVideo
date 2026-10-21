"""The generation pipeline: script -> per-scene assets -> rendered video, plus series analysis/planning."""

from __future__ import annotations

import asyncio
import re
import secrets
from pathlib import Path
from typing import Any, Awaitable, Callable, Optional

from ..config import AppConfig, config_manager
from ..db import Database
from ..models import AssetKind, Character, Episode, Line, Location, Overview, Project, Scene
from ..presets import style_prompt
from ..prompts import (
    analyze_document_prompt,
    end_image_prompt_for,
    episode_script_prompt,
    episode_titles_prompt,
    image_prompts_prompt,
    is_cjk,
    topic_script_prompt,
    video_motion_rules,
)
from ..providers.base import ProviderError, VideoRequest
from ..providers.registry import get_image, get_llm, get_tts, get_video
from . import ffmpeg, series, slide_service, storage, storyboard
from .overlay import render_overlay
from .text_split import split_script

Progress = Callable[[float, str], Awaitable[None]]
SCENE_TAIL_SECONDS = 0.35
LINE_GAP_SECONDS = 0.3
IMAGE_CONCURRENCY = 3
DEFAULT_MOTION_HINT = "The camera stays fixed. Gentle ambient movement unfolds naturally within the frame."

_SPEAKABLE = re.compile(r"[A-Za-z0-9぀-ヿ㐀-鿿가-힯]")


class PipelineError(RuntimeError):
    pass


def speakable(text: str) -> bool:
    return bool(_SPEAKABLE.search(text))


def _required_kinds(project: Project) -> list[AssetKind]:
    kinds: list[AssetKind] = []
    if project.h3_segments:  # MiniMax H3 clone: each scene = one H3 part (reference frame + generated clip)
        return ["image", "video"]
    if project.input_mode != "prompt" or project.subtitle_enabled:
        kinds.append("audio")
    kinds.append("image")
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


def image_prompt_for(
    scene: Scene,
    style: str,
    prev_scene: Optional[Scene] = None,
    first_scene: Optional[Scene] = None,
    prompt_prefix: str = "",
) -> str:
    """Build the full image generation prompt, ensuring continuity with the previous scene and original first frame."""
    parts: list[str] = []
    if prompt_prefix.strip():
        parts.append(prompt_prefix.strip())

    base = scene.image_prompt.strip()
    # If not the first scene, reinforce character and environment continuity with the previous scene / master keyframe
    if scene.index > 0 and (prev_scene or first_scene):
        if not any(k in base.lower() for k in ("continuity", "consistent", "same character", "same person", "same face")):
            base = f"{base}, strict visual continuity with preceding scene, identical character facial features, same hairstyle, exact same outfit and clothing colors, matching environment lighting and atmosphere"

    parts.append(base)
    if style.strip() and style.strip().lower() not in base.lower():
        parts.append(style.strip())

    return ", ".join(parts)


def video_prompt_for(scene: Scene, style: str, prev_scene: Optional[Scene] = None, *, video_mode: str = "i2v") -> str:
    # Preserve authored motion instructions; image appearance/style belong to input frames.
    base = scene.video_prompt.strip()
    if video_mode == "t2v":
        base = base or f"{scene.image_prompt.strip()}. {DEFAULT_MOTION_HINT}"
        return f"{base}, {style}" if style and style.lower() not in base.lower() else base
    if base:
        return base
    if video_mode == "keyframes":
        return ("The camera stays fixed. The subject begins the movement implied by the starting pose, "
                "then progresses naturally toward the final pose, finally settling into the positions shown in the ending frame.")
    return DEFAULT_MOTION_HINT


def video_frames_for(scene: Scene, mode: str) -> tuple[Optional[Path], Optional[Path]]:
    """Only pair frames belonging to this shot; never borrow another scene's frame."""
    if mode not in ("i2v", "keyframes"):
        return None, None
    start = storage.abs_path(scene.image_path) if scene.image_path else None
    if start is None or not start.is_file():
        raise ProviderError("此分鏡缺少首幀圖，請先產生或上傳此分鏡的首幀圖。")
    if scene.image_stale:
        raise ProviderError("此分鏡首幀圖已過期，請先重新產生首幀圖。")
    if mode == "i2v":
        return start, None
    end = storage.abs_path(scene.end_image_path) if scene.end_image_path else None
    if end is None or not end.is_file():
        raise ProviderError("首尾幀模式需要同一分鏡的尾幀圖，請先產生或上傳尾幀圖，或改用單首幀圖生影片。")
    if scene.end_image_stale:
        raise ProviderError("此分鏡尾幀圖已過期，請先重新產生尾幀圖。")
    return start, end


class Pipeline:
    def __init__(self, db: Database) -> None:
        self.db = db

    async def _load_series(self, project: Project) -> Optional[Project]:
        if project.kind == "episode" and project.parent_id:
            return await self.db.get_project(project.parent_id)
        return None

    def _reset_scenes(self, project: Project) -> None:
        for scene in project.scenes:
            for rel in (scene.audio_path, scene.image_path, scene.end_image_path, scene.video_path, scene.segment_path):
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
        if project.input_mode == "slide":
            return await self._process_slide_script(project, progress)
        cfg = config_manager.get()
        llm = get_llm(cfg)
        style = project.style_prompt or style_prompt(project.style_id)
        await progress(0.05, "正在撰寫腳本…")

        if project.input_mode == "prompt":
            prompt_text = project.topic.strip()
            if not prompt_text:
                raise PipelineError("提示詞是空的，請先輸入提示詞。")
            await progress(0.05, "正在處理單一提示詞…")

            english_prompt = prompt_text
            # If prompt has CJK characters, use LLM to translate/refine into vivid English for visual & video models
            if is_cjk(project.language) or any(ord(c) > 127 for c in prompt_text):
                try:
                    refine_query = (
                        f"Translate and refine the following video description into a vivid, high-quality visual prompt in English "
                        f"(30-50 words, specifying subject, motion, lighting, atmosphere, no text or logos):\n\n"
                        f"{prompt_text}\n\n"
                        f"Return ONLY the refined English prompt, nothing else."
                    )
                    translated = await llm.complete(refine_query)
                    if translated and translated.strip():
                        english_prompt = translated.strip().strip('"').strip("'")
                except Exception:
                    pass

            motion_prompt = english_prompt
            if (project.video_mode or cfg.video.mode) != "t2v":
                motion_prompt = ""
                try:
                    motion_prompt = (await llm.complete(
                        video_motion_rules(project.video_mode or cfg.video.mode)
                        + "\nUse the following description as context, not text to repeat. "
                        + "Return ONLY the video motion prompt.\n" + english_prompt
                    )).strip()
                except Exception:
                    pass  # Empty prompts use the mode-specific motion fallback.

            title = project.title.strip() or prompt_text[:20]
            data = {"title": title}
        elif project.input_mode == "script":
            segments = split_script(project.topic, project.language)
            if not segments:
                raise PipelineError("文稿內容是空的，請先輸入文字。")
            data = await llm.complete_json(image_prompts_prompt(segments, project.language, style, project.video_mode or cfg.video.mode))
            prompts = [str(p) for p in data.get("image_prompts", [])]
            end_prompts = [str(p) for p in data.get("end_image_prompts", [])]
            videos = [str(p) for p in data.get("video_prompts", [])]
            if len(prompts) < len(segments):
                prompts += [segments[i][:100] for i in range(len(prompts), len(segments))]
            scenes_data = [
                {
                    "narration": s,
                    "image_prompt": prompts[i],
                    "end_image_prompt": end_prompts[i] if i < len(end_prompts) else "",
                    "video_prompt": videos[i] if i < len(videos) else "",
                }
                for i, s in enumerate(segments)
            ]
        else:
            if not project.topic.strip():
                raise PipelineError("請先輸入主題。")
            data = await llm.complete_json(topic_script_prompt(project.topic, project.n_scenes, project.language, style, project.video_mode or cfg.video.mode))
            scenes_data = [
                {
                    "narration": str(s.get("narration", "")).strip(),
                    "image_prompt": str(s.get("image_prompt", "")).strip(),
                    "end_image_prompt": str(s.get("end_image_prompt", "") or "").strip(),
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

        if project.input_mode == "prompt":
            full_img_prompt = f"{english_prompt}, {style}".strip(", ") if style else english_prompt
            narration_text = prompt_text if project.subtitle_enabled else ""
            if project.scenes:
                scene = project.scenes[0]
                scene.image_prompt = full_img_prompt
                scene.video_prompt = motion_prompt
                scene.narration = narration_text
            else:
                scene = Scene(
                    id=project.next_scene_id(),
                    index=0,
                    duration=5.0,
                    narration=narration_text,
                    image_prompt=full_img_prompt,
                    video_prompt=motion_prompt,
                )
                project.scenes = [scene]
        else:
            self._reset_scenes(project)
            for item in scenes_data:
                project.scenes.append(Scene(id=project.next_scene_id(), **item))
        if project.characters:
            for s in project.scenes:
                s.image_prompt = _ensure_appearance(s.image_prompt, _mentioned_characters(s, project.characters))
        project.reindex()
        refresh_project_status(project)
        await self.db.save_project(project)
        await progress(1.0, f"腳本完成，共 {len(project.scenes)} 個場景")
        return project

    async def _process_slide_script(self, project: Project, progress: Progress) -> Project:
        if not project.scenes:
            raise PipelineError("專案尚未匯入簡報投影片，請先上傳 PPTX 簡報檔。")
        missing = [s for s in project.scenes if not s.narration.strip()]
        if not missing:
            await progress(1.0, f"投影片講稿齊全，共 {len(project.scenes)} 頁")
            refresh_project_status(project)
            await self.db.save_project(project)
            return project

        cfg = config_manager.get()
        llm = get_llm(cfg)
        await progress(0.1, f"正在為 {len(missing)} 頁投影片生成演講講稿…")
        for idx, scene in enumerate(missing, 1):
            prompt = (
                f"請為一場專業簡報的第 {scene.index + 1} 頁投影片撰寫口語化的演講講稿（繁體中文）。\n"
                f"投影片資訊：{scene.image_prompt}\n"
                f"要求：\n"
                f"1. 語氣生動自然、適合演講口語朗讀，不要包含 Markdown 語法、星號、表情符號或代碼塊。\n"
                f"2. 篇幅約 80~150 字，直接輸出講稿內容即可。"
            )
            try:
                res = await llm.complete(prompt)
                scene.narration = slide_service.clean_speech_text(res.strip())
            except Exception as exc:
                scene.narration = f"第 {scene.index + 1} 頁投影片說明。"
            await progress(0.1 + 0.85 * idx / len(missing), f"已完成 {idx}/{len(missing)} 頁講稿")

        refresh_project_status(project)
        await self.db.save_project(project)
        await progress(1.0, f"簡報講稿已備妥，共 {len(project.scenes)} 頁")
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
                video_mode=project.video_mode or cfg.video.mode,
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
            scene.end_image_prompt = str(item.get("end_image_prompt", "") or "").strip()
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
            has_end_image = bool(scene.end_image_path) and storage.abs_path(scene.end_image_path).exists()
            has_video = bool(scene.video_path) and storage.abs_path(scene.video_path).exists()
            if "audio" in wanted and (force or not has_audio or scene.audio_stale):
                todo.add("audio")
            if "image" in wanted and (force or not has_image or scene.image_stale):
                todo.add("image")
            has_end_prompt = bool((scene.end_image_prompt or "").strip())
            should_end_image = "end_image" in wanted or (kinds is None and video_mode == "keyframes" and has_end_prompt)
            if should_end_image and (force or not has_end_image or scene.end_image_stale or "image" in todo):
                todo.add("end_image")
            if need_video and (force or not has_video or scene.video_stale or "image" in todo or "end_image" in todo):
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
        image = get_image(cfg) if any("image" in t or "end_image" in t for _, t in jobs) else None
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
            eff_speed = scene.tts_speed or project.tts_speed
            if spoken:
                parts: list[Path] = []
                for i, ln in enumerate(spoken):
                    part = path.parent / f"line_{i:02d}_{path.stem[-6:]}.mp3"
                    voice = series.character_voice(ctx, ln.speaker, project.voice)
                    await tts.synthesize(ln.text, voice, eff_speed, part)
                    ln.duration = round(await ffmpeg.probe_duration(part), 3)
                    parts.append(part)
                await ffmpeg.concat_audio(parts, LINE_GAP_SECONDS, path)
                for p in parts:
                    p.unlink(missing_ok=True)
            else:
                await tts.synthesize(scene.narration, project.voice, eff_speed, path)
            duration = await ffmpeg.probe_duration(path)
            storage.remove(scene.audio_path)
            scene.audio_path, scene.duration, scene.audio_stale = rel, round(duration, 3), False
            invalidate_segment(scene)
            await step_done(f"場景 {scene.index + 1}/{n_total} 語音完成")

        async def do_image(scene: Scene) -> None:
            assert image is not None
            prev_scene = project.scenes[scene.index - 1] if scene.index > 0 else None
            first_scene = project.scenes[0] if scene.index > 0 else None
            prompt = image_prompt_for(scene, style, prev_scene, first_scene, cfg.image.prompt_prefix)
            refs: list[Path] = storyboard.binding_refs(scene)
            if cfg.image.use_references:
                for c in ([] if scene.asset_bindings else _mentioned_characters(scene, ctx.characters)):
                    if c.image_path:
                        p = storage.abs_path(c.image_path)
                        if p.is_file() and p not in refs:
                            refs.append(p)
                if scene.index > 0 and not scene.asset_bindings:
                    if not scene.asset_bindings and prev_scene and prev_scene.image_path:
                        p = storage.abs_path(prev_scene.image_path)
                        if p.is_file() and p not in refs:
                            refs.append(p)
                    if not scene.asset_bindings and first_scene and first_scene.image_path:
                        p = storage.abs_path(first_scene.image_path)
                        if p.is_file() and p not in refs:
                            refs.append(p)
            prompt += storyboard.binding_prompt(scene)
            rel = storage.scene_rel(project.id, scene.id, "image", "png")
            async with image_sem:
                await image.generate(prompt, cfg.image.negative_prompt, project.width, project.height, storage.abs_path(rel), reference_images=refs)
            storyboard.remember(scene, "image")
            scene.image_path, scene.image_stale = rel, False
            if video_mode == "keyframes" and scene.end_image_path:
                scene.end_image_stale = True
            scene.video_stale = bool(scene.video_path) and video_mode != "t2v"
            invalidate_segment(scene)
            await step_done(f"場景 {scene.index + 1}/{n_total} 圖片完成")

        async def do_end_image(scene: Scene) -> None:
            assert image is not None
            end_prompt_raw = (scene.end_image_prompt or "").strip()
            if not end_prompt_raw:
                motion_desc = (scene.video_prompt or "").strip() or "ending composition of the shot"
                img_prompt = (scene.image_prompt or "").strip()
                end_prompt_raw = f"{img_prompt}, ending frame of the shot, showing {motion_desc}" if img_prompt else motion_desc

            prompt = end_image_prompt_for(scene, end_prompt_raw, style, cfg.image.prompt_prefix)
            refs: list[Path] = storyboard.binding_refs(scene)
            if scene.image_path:
                start_p = storage.abs_path(scene.image_path)
                if start_p.is_file():
                    refs.append(start_p)
            if cfg.image.use_references:
                for c in ([] if scene.asset_bindings else _mentioned_characters(scene, ctx.characters)):
                    if c.image_path:
                        p = storage.abs_path(c.image_path)
                        if p.is_file() and p not in refs:
                            refs.append(p)
            prompt += storyboard.binding_prompt(scene)
            rel = storage.scene_rel(project.id, scene.id, "end_image", "png")
            # Build anti-mutation negative prompt specifically targeting limb/head/tail duplication & fusion
            neg_parts = [cfg.image.negative_prompt.strip()] if cfg.image.negative_prompt.strip() else []
            neg_parts.append("extra limbs, extra arms, extra legs, extra tails, two tails, multiple tails, split tail, multiple heads, cloned faces, duplicate body, deformed limbs, fused bodies, mutation, bad anatomy, disfigured")
            effective_negative = ", ".join(neg_parts)

            async with image_sem:
                await image.generate(prompt, effective_negative, project.width, project.height, storage.abs_path(rel), reference_images=refs)
            storyboard.remember(scene, "end_image")
            scene.end_image_path, scene.end_image_stale = rel, False
            storyboard.remember(scene, "end_image")
            scene.video_stale = bool(scene.video_path) and video_mode != "t2v"
            invalidate_segment(scene)
            await step_done(f"場景 {scene.index + 1}/{n_total} 尾幀完成")

        async def do_video(scene: Scene) -> None:
            assert video_provider is not None
            prev_scene = project.scenes[scene.index - 1] if scene.index > 0 else None
            first_scene = project.scenes[0] if scene.index > 0 else None
            start: Optional[Path] = None
            end: Optional[Path] = None
            refs: list[Path] = storyboard.binding_refs(scene)
            if video_mode in ("i2v", "keyframes"):
                start, end = video_frames_for(scene, video_mode)

                for c in ([] if scene.asset_bindings else _mentioned_characters(scene, ctx.characters)):
                    if c.image_path:
                        p = storage.abs_path(c.image_path)
                        if p.is_file() and p not in refs:
                            refs.append(p)
                if not scene.asset_bindings and first_scene and first_scene.image_path:
                    p = storage.abs_path(first_scene.image_path)
                    if p.is_file() and p not in refs and p != start:
                        refs.append(p)
            else:
                for c in ([] if scene.asset_bindings else _mentioned_characters(scene, ctx.characters)):
                    if c.image_path:
                        p = storage.abs_path(c.image_path)
                        if p.is_file() and p not in refs:
                            refs.append(p)
                if not scene.asset_bindings and first_scene and first_scene.image_path:
                    p = storage.abs_path(first_scene.image_path)
                    if p.is_file() and p not in refs:
                        refs.append(p)
                if not scene.asset_bindings and prev_scene and prev_scene.image_path:
                    p = storage.abs_path(prev_scene.image_path)
                    if p.is_file() and p not in refs:
                        refs.append(p)

            rel = storage.scene_rel(project.id, scene.id, "clip", "mp4")
            request = VideoRequest(
                prompt=video_prompt_for(scene, style, prev_scene, video_mode=video_mode) + (storyboard.binding_prompt(scene) if video_mode == "t2v" else storyboard.staging_prompt(scene)), duration=(scene.duration or 5.0) + SCENE_TAIL_SECONDS,
                width=project.width, height=project.height, fps=cfg.video.fps, output_path=storage.abs_path(rel),
                start_image=start, end_image=end, reference_images=refs,
            )
            async with video_sem:
                await video_provider.generate(request)
            storyboard.remember(scene, "video")
            scene.video_path, scene.video_stale = rel, False
            storyboard.remember(scene, "video")
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

        await progress(0.01, f"開始產生 {len(jobs)} 個場景的素材…")
        try:
            # Audio jobs run in parallel
            audio_jobs = [scene for scene, todo in jobs if "audio" in todo]
            if audio_jobs:
                await asyncio.gather(*(guarded(scene, do_audio(scene)) for scene in audio_jobs))

            # Image jobs run in scene order so each scene can reference the previous scene's image
            # and master keyframe (原首幀)
            image_jobs = [scene for scene, todo in jobs if "image" in todo]
            image_jobs.sort(key=lambda s: s.index)
            for scene in image_jobs:
                await guarded(scene, do_image(scene))
                refresh_scene_status(project, scene)

            # End image jobs run after start images exist so each end image can reference its start image
            end_image_jobs = [scene for scene, todo in jobs if "end_image" in todo and not scene.error]
            end_image_jobs.sort(key=lambda s: s.index)
            for scene in end_image_jobs:
                await guarded(scene, do_end_image(scene))
                refresh_scene_status(project, scene)

            # Videos run after each scene's own start/end image jobs complete.
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
        # In slide/presentation mode, subtitles are handled dynamically by SRT and studio
        if project.input_mode == "slide":
            return None, []

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
        # In presentation / slide mode, subtitles are managed dynamically via SRT and studio overlay
        # Do not burn static scene text into the slide frames to avoid duplicate subtitles
        if project.input_mode == "slide":
            subtitle = None
        else:
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

        is_slide = project.input_mode == "slide"
        pre_pad = slide_service.PRE_PAD_SECONDS if is_slide else 0.0
        post_pad = slide_service.POST_PAD_SECONDS if is_slide else 0.0

        segments: list[Path] = []
        slides_subtitles: list[dict] = []
        cumulative_offset = 0.0
        n = len(project.scenes)
        for i, scene in enumerate(project.scenes):
            await progress(0.05 + 0.75 * i / n, f"合成場景 {i + 1}/{n}…")
            scene_dir = storage.project_dir(project.id) / "scenes" / scene.id
            static, timed = await asyncio.to_thread(
                self._scene_overlays, project, scene, scene_dir, font_pref, font_size, sub_pos
            )
            has_audio = bool(scene.audio_path) and storage.abs_path(scene.audio_path).is_file()
            if has_audio:
                raw_audio_dur = scene.duration or await ffmpeg.probe_duration(storage.abs_path(scene.audio_path or ""))
            else:
                raw_audio_dur = scene.duration or 5.0
            if is_slide:
                duration = raw_audio_dur + pre_pad + post_pad
            else:
                duration = raw_audio_dur + (SCENE_TAIL_SECONDS if has_audio else 0.0)
            rel = storage.scene_rel(project.id, scene.id, "segment", "mp4")
            await ffmpeg.render_segment(
                output=storage.abs_path(rel), width=project.width, height=project.height, fps=fps, duration=duration,
                audio=storage.abs_path(scene.audio_path) if has_audio else None,
                image=storage.abs_path(scene.image_path) if scene.image_path else None,
                end_image=storage.abs_path(scene.end_image_path) if scene.end_image_path else None,
                clip=storage.abs_path(scene.video_path) if (project.motion == "ai_video" and scene.video_path) else None,
                overlay=static, timed_overlays=timed, motion=project.motion, scene_index=i, crf=cfg.render.crf,
                pre_pad=pre_pad, post_pad=post_pad,
            )
            storage.remove(scene.segment_path)
            scene.segment_path = rel
            segments.append(storage.abs_path(rel))

            # Record subtitle data
            sentences = slide_service.calculate_proportional_subtitles(scene.narration, raw_audio_dur)
            slides_subtitles.append({"slide_start": cumulative_offset, "sentences": sentences})
            cumulative_offset += duration

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

        # Generate synchronized SRT file
        if slides_subtitles:
            srt_rel = storage.output_rel(project.id, "subtitles", "srt")
            srt_abs = storage.abs_path(srt_rel)
            storage.remove(project.subtitles_path)
            slide_service.generate_presentation_srt(slides_subtitles, srt_abs, pre_pad=pre_pad)
            project.subtitles_path = srt_rel

        storage.remove(project.final_video_path)
        project.final_video_path = final_rel
        project.raw_video_path = final_rel
        project.final_video_duration = round(total, 2)
        project.final_video_size = final_abs.stat().st_size
        refresh_project_status(project)
        await self.db.save_project(project)
        await progress(1.0, "影片合成完成")
        return project

    # ------------------------------------------------------------ MiniMax H3 (video clone)
    async def generate_h3(
        self,
        project: Project,
        progress: Progress,
        segment_indexes: Optional[list[int]] = None,
        force: bool = False,
    ) -> Project:
        """Generate every H3 part with MiniMax (R2V / T2V / I2V), trim, conform and join into the final video."""
        cfg = config_manager.get()
        if not project.h3_segments:
            raise PipelineError("此專案沒有 H3 分段，請先用「短影片分析復刻（MiniMax H3）」建立專案。")
        if cfg.video.provider not in ("minimax", "comfyui_minimax"):
            raise PipelineError(
                "H3 生成需要 MiniMax：請到 設定 → 影片，將供應商改為「MiniMax H3」或「ComfyUI → MiniMax H3」並填入金鑰。"
            )
        provider = get_video(cfg)
        if provider is None:
            raise PipelineError("無法建立 MiniMax 影片 provider。")

        mode = project.h3_mode
        pictures = [storage.abs_path(r) for r in project.h3_reference_images if storage.abs_path(r).is_file()]
        wanted = set(segment_indexes) if segment_indexes else None
        targets = [
            s for s in project.h3_segments
            if (wanted is None or s.index in wanted)
            and (force or wanted is not None or not (s.clip_path and storage.abs_path(s.clip_path).exists()))
        ]
        h3_dir = storage.project_dir(project.id) / "h3"
        h3_dir.mkdir(parents=True, exist_ok=True)
        sem = asyncio.Semaphore(max(1, cfg.video.concurrency))
        done_count = 0
        n_total = max(1, len(targets))
        await progress(0.02, f"準備生成 {len(targets)} 段 H3 影片…")

        async def one(seg: Any) -> None:
            nonlocal done_count
            if not seg.prompt.strip():
                seg.status, seg.error = "failed", "此段沒有提示詞"
                return
            def p(rel: Optional[str]) -> Optional[Path]:
                return storage.abs_path(rel) if rel and storage.abs_path(rel).is_file() else None

            ref_v, ref_a = p(seg.ref_video_path), p(seg.ref_audio_path)
            req = VideoRequest(
                prompt=seg.prompt,
                duration=float(seg.request_duration),
                width=project.width,
                height=project.height,
                fps=cfg.video.fps,
                output_path=h3_dir / f"part_{seg.index + 1:02d}_raw.mp4",
                h3_mode=mode,
                ratio=project.aspect_ratio,
            )
            if mode == "ref2va":
                req.reference_images = pictures
                if project.h3_use_ref_video and ref_v:
                    req.reference_videos = [ref_v]
                if project.h3_use_ref_audio and ref_a and (req.reference_videos or req.reference_images):
                    req.reference_audios = [ref_a]
                if not req.reference_videos and not req.reference_images and ref_v:
                    req.reference_videos = [ref_v]  # R2V needs at least one visual reference
            elif mode in ("i2va", "fl2va"):
                req.start_image = p(seg.first_frame_path)
                if mode == "fl2va":
                    req.end_image = p(seg.last_frame_path)
            async with sem:
                seg.status, seg.error = "generating", None
                await self.db.save_project(project)
                try:
                    raw = await provider.generate(req)
                    actual = await ffmpeg.probe_duration(raw)
                    keep = min(seg.duration, actual) if actual > 0 else seg.duration
                    rel = storage.output_rel(project.id, f"h3_part_{seg.index + 1:02d}", "mp4")
                    await ffmpeg.normalize_clip(raw, keep, project.width, project.height, cfg.video.fps, storage.abs_path(rel), crf=cfg.render.crf)
                    raw.unlink(missing_ok=True)
                    storage.remove(seg.clip_path)
                    seg.clip_path, seg.status, seg.error = rel, "done", None
                    if keep + 0.05 < seg.duration:
                        seg.warnings.append(f"H3 輸出只有 {actual:.2f}s，短於本段 {seg.duration:.2f}s。")
                    scene = next((sc for sc in project.scenes if sc.index == seg.index), None)
                    if scene is not None:
                        scene.video_path = rel
                        scene.segment_path = rel
                        scene.video_stale = False
                        scene.error = None
                except Exception as exc:
                    seg.status, seg.error = "failed", str(exc)
                    scene = next((sc for sc in project.scenes if sc.index == seg.index), None)
                    if scene is not None:
                        scene.error = f"H3 生成失敗：{exc}"
                    raise
                finally:
                    done_count += 1
                    refresh_project_status(project)
                    await self.db.save_project(project)
                    await progress(0.05 + 0.8 * done_count / n_total, f"H3 第 {seg.index + 1} 段 {'完成' if seg.status == 'done' else '失敗'}")

        results = await asyncio.gather(*(one(s) for s in targets), return_exceptions=True)
        errors = [r for r in results if isinstance(r, BaseException)]
        for r in errors:
            if isinstance(r, asyncio.CancelledError):
                raise r

        ready = [s for s in project.h3_segments if s.clip_path and storage.abs_path(s.clip_path).exists()]
        if len(ready) == len(project.h3_segments):
            await progress(0.9, "串接所有 H3 段落…")
            clips = [storage.abs_path(s.clip_path or "") for s in sorted(project.h3_segments, key=lambda x: x.index)]
            final_rel = storage.output_rel(project.id, "final", "mp4")
            final_abs = storage.abs_path(final_rel)
            await ffmpeg.concat(clips, final_abs)
            storage.remove(project.final_video_path)
            project.final_video_path = final_rel
            project.raw_video_path = final_rel
            project.final_video_duration = round(await ffmpeg.probe_duration(final_abs), 2)
            project.final_video_size = final_abs.stat().st_size
        refresh_project_status(project)
        await self.db.save_project(project)
        if errors:
            raise PipelineError(f"{len(errors)} 段 H3 生成失敗：{errors[0]}")
        await progress(1.0, "H3 影片生成完成" if project.final_video_path else "H3 段落生成完成")
        return project

    # ------------------------------------------------------------ full
    async def full(self, project: Project, progress: Progress) -> Project:
        async def scaled(lo: float, hi: float) -> Progress:
            async def cb(p: float, msg: str) -> None:
                await progress(lo + (hi - lo) * p, msg)

            return cb

        if project.h3_segments:
            return await self.generate_h3(project, progress)
        if not project.scenes or project.input_mode == "prompt":
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
        prompt = ", ".join(p for p in (cfg.image.prompt_prefix.strip(), f"Character identity reference sheet of ONE identical character: {ch.appearance.strip()}. Exactly four clearly separated panels on a neutral background. Left two-thirds: three equal full-body orthographic views, front view, side profile, and rear view, head to feet fully visible, same scale, neutral standing pose, identical clothing and proportions. Right one-third: a large prominent front-facing head and face close-up cropped at the neck, showing only the neck and above, no shoulders or torso. Face fills this panel with clearly visible eyes, nose, mouth, ears, hairline and facial details. All four panels depict the SAME person, same age, face, hairstyle and colors. No text, labels, watermark or extra views", style) if p)
        await progress(0.1, f"生成角色圖：{ch.name}…")
        rel = f"{project.id}/characters/{ch.id}_{secrets.token_hex(3)}.png"
        await get_image(cfg).generate(prompt, cfg.image.negative_prompt, 1536, 1024, storage.abs_path(rel))
        storage.remove(ch.image_path)
        ch.image_path = rel
        await self.db.save_project(project)
        await progress(1.0, f"角色圖完成：{ch.name}")
        return project
