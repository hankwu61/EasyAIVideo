"""Video clone and remake service: analyze existing short videos and regenerate same-theme/scene videos.

Includes deep forensic reverse-engineering into MiniMax Hailuo H3 prompts (Ref2VA / 14-field),
following the D:\\video-to-h3-prompt forensic workflow:
- Audio/video probing, contact sheet, RMS energy, and note onset detection
- Camera state machine triage (A: Continuous, B: Snap-lock, C: Montage)
- Ready-to-paste MiniMax H3 English prompts and Chinese forensic dossier
- Character / coser replacement support
"""

from __future__ import annotations

import logging
import math
import shutil
from pathlib import Path
from typing import Any, Optional

from ..config import config_manager
from ..db import Database
from ..models import AspectRatio, H3Segment, Motion, Project, Scene, new_id
from ..prompts import analyze_h3_segment_prompt, analyze_video_h3_overview_prompt, analyze_video_remake_prompt
from ..providers.base import ProviderError
from ..providers.registry import get_llm, get_vision
from . import ffmpeg, storage
from .forensic_service import ForensicService, build_timecoded_sheet, plan_segments
from .h3_prompt_tools import request_duration, validate_h3_prompt

log = logging.getLogger("easyaivideo.clone")


class VideoCloneError(RuntimeError):
    pass


def source_header(meta: Optional[dict[str, Any]]) -> str:
    """Markdown block naming the online source of a cloned video (empty for uploads)."""
    if not meta:
        return ""
    url = meta.get("webpage_url") or meta.get("url")
    if not url:
        return ""
    bits = [f"- 網址：{url}"]
    if meta.get("title"):
        bits.append(f"- 原始標題：{meta['title']}")
    if meta.get("uploader"):
        bits.append(f"- 作者／頻道：{meta['uploader']}")
    if meta.get("extractor"):
        bits.append(f"- 來源網站：{meta['extractor']}")
    if meta.get("duration"):
        bits.append(f"- 時長：{float(meta['duration']):.2f} 秒")
    return "## 影片來源\n" + "\n".join(bits)


def _rel(path: Path) -> str:
    """Absolute path inside the projects directory -> relative storage path."""
    return path.resolve().relative_to(storage.PROJECTS_DIR.resolve()).as_posix()


def calculate_sample_timestamps(duration: float, max_frames: int = 8) -> list[float]:
    """Calculate evenly spaced keyframe timestamps across the video."""
    if duration <= 0:
        return [0.0]
    if duration < 8.0:
        count = 3
    elif duration < 18.0:
        count = 5
    elif duration < 35.0:
        count = 6
    else:
        count = min(max_frames, 8)

    step = duration / count
    return [round(step * (i + 0.5), 3) for i in range(count)]


def detect_aspect_ratio(width: int, height: int) -> AspectRatio:
    """Classify video dimensions into 9:16, 16:9, or 1:1."""
    if height > width * 1.15:
        return "9:16"
    if width > height * 1.15:
        return "16:9"
    return "1:1"


class VideoCloneService:
    def __init__(self, db: Database) -> None:
        self.db = db

    async def clone_from_video(
        self,
        video_path: Path,
        *,
        language: str = "zh-TW",
        motion: Motion = "ai_video",
        style_id: Optional[str] = None,
        title_override: Optional[str] = None,
        voice: Optional[str] = None,
        auto_start: bool = False,
        generation_mode: str = "minimax_h3",  # "standard" | "minimax_h3"
        h3_mode: str = "ref2va",  # "ref2va" | "i2va" | "t2va" | "fl2va"
        character_replacement: Optional[str] = None,
        reference_images: Optional[list[Path]] = None,
        use_ref_video: bool = True,
        use_ref_audio: bool = True,
        source_meta: Optional[dict[str, Any]] = None,
    ) -> Project:
        source_meta = dict(source_meta or {})
        if not video_path.is_file():
            raise VideoCloneError(f"短影片檔案不存在: {video_path}")

        # 1. Probe video duration and dimensions
        try:
            duration = await ffmpeg.probe_duration(video_path)
            width, height = await ffmpeg.probe_dimensions(video_path)
        except Exception as exc:
            raise VideoCloneError(f"無法解析短影片資訊: {exc}") from exc

        if duration <= 0:
            raise VideoCloneError("短影片時長無效。")

        aspect = detect_aspect_ratio(width, height)
        proj_id = new_id("proj")
        p_dir = storage.project_dir(proj_id)
        p_dir.mkdir(parents=True, exist_ok=True)

        # 2. Store original video copy
        source_rel = f"{proj_id}/source_video{video_path.suffix.lower() or '.mp4'}"
        source_abs = storage.abs_path(source_rel)
        shutil.copy2(video_path, source_abs)

        cfg = config_manager.get()
        vision = get_vision(cfg)

        h3_prompt_text: Optional[str] = None
        forensic_report_text: Optional[str] = None
        analysis_data: dict[str, Any] = {}
        frame_paths: list[Path] = []

        if generation_mode == "minimax_h3":
            try:
                return await self._clone_h3(
                    proj_id=proj_id,
                    p_dir=p_dir,
                    source_abs=source_abs,
                    duration=duration,
                    aspect=aspect,
                    language=language,
                    motion=motion,
                    style_id=style_id,
                    title_override=title_override,
                    voice=voice,
                    auto_start=auto_start,
                    h3_mode=h3_mode,
                    character_replacement=character_replacement,
                    reference_images=list(reference_images or []),
                    use_ref_video=use_ref_video,
                    use_ref_audio=use_ref_audio,
                    source_meta=source_meta,
                )
            except VideoCloneError:
                raise
            except Exception as exc:
                log.exception("H3 clone failed")
                raise VideoCloneError(f"MiniMax H3 影片取證反推失敗: {exc}") from exc

        else:
            # 3B. Standard Clone flow
            timestamps = calculate_sample_timestamps(duration, max_frames=8)
            frames_dir = p_dir / "keyframes"
            frames_dir.mkdir(parents=True, exist_ok=True)

            for idx, t in enumerate(timestamps):
                fpath = frames_dir / f"frame_{idx:02d}.jpg"
                try:
                    await ffmpeg.extract_frame(source_abs, t, fpath, width=768)
                    if fpath.is_file():
                        frame_paths.append(fpath)
                except Exception as exc:
                    log.warning("Failed to extract frame at %.2fs: %s", t, exc)

            if not frame_paths:
                raise VideoCloneError("無法從短影片中抽取有效關鍵畫面。")

            prompt = analyze_video_remake_prompt(language, len(frame_paths), duration)
            try:
                analysis_data = await vision.complete_json_with_images(prompt, frame_paths)
            except Exception as exc:
                log.warning("Vision analysis error: %s, falling back to LLM", exc)
                try:
                    llm = get_llm(cfg)
                    fallback_prompt = (
                        f"請為一支時長約 {duration:.1f} 秒的短影片設計分鏡重製腳本（語言：{language}）。\n"
                        f"回傳 JSON 格式包含 title, theme, style_id, style_prompt, scenes（包含 duration, narration, image_prompt, video_prompt, keyframe_index）。"
                    )
                    analysis_data = await llm.complete_json(fallback_prompt)
                except Exception as llm_exc:
                    raise VideoCloneError(f"AI 鏡頭與風格分析失敗: {exc}") from llm_exc

        # 4. Extract structured fields
        title = (title_override or "").strip() or str(analysis_data.get("title") or "短影片復刻").strip()
        theme = str(analysis_data.get("theme") or analysis_data.get("film_type") or "").strip()
        chosen_style_id = (style_id or "").strip() or str(analysis_data.get("style_id") or "cinematic").strip()
        chosen_style_prompt = str(analysis_data.get("style_prompt") or "").strip()

        raw_scenes = analysis_data.get("scenes") or []
        if not isinstance(raw_scenes, list) or not raw_scenes:
            # Fallback to 1 scene per keyframe
            n_sc = max(1, len(frame_paths))
            raw_scenes = [
                {
                    "index": i,
                    "keyframe_index": i,
                    "duration": round(duration / n_sc, 2),
                    "narration": f"場景 {i + 1}",
                    "image_prompt": f"Scene {i + 1} recreating {theme}, cinematic lighting, 8k",
                    "video_prompt": "Slow camera motion",
                }
                for i in range(n_sc)
            ]

        # 5. Initialize Project and Scenes
        project = Project(
            id=proj_id,
            source_url=source_meta.get("webpage_url") or source_meta.get("url"),
            source_meta=source_meta,
            title=title,
            topic=theme or title,
            input_mode="video",
            language=language,
            aspect_ratio=aspect,
            style_id=chosen_style_id,
            style_prompt=chosen_style_prompt,
            motion=motion,
            voice=voice or (cfg.tts.voice if hasattr(cfg.tts, "voice") else "zh-TW-HsiaoChenNeural"),
            subtitle_enabled=True,
            n_scenes=len(raw_scenes),
            h3_prompt=h3_prompt_text,
            forensic_report=forensic_report_text,
        )

        created_scenes: list[Scene] = []
        for i, s_data in enumerate(raw_scenes):
            scene_id = project.next_scene_id()
            kf_idx = s_data.get("keyframe_index", i)
            kf_path: Optional[Path] = None
            if isinstance(kf_idx, int) and 0 <= kf_idx < len(frame_paths):
                kf_path = frame_paths[kf_idx]
            elif frame_paths:
                kf_path = frame_paths[min(i, len(frame_paths) - 1)]

            img_rel: Optional[str] = None
            if kf_path and kf_path.is_file():
                img_rel = storage.scene_rel(proj_id, scene_id, "ref_frame", "jpg")
                img_abs = storage.abs_path(img_rel)
                img_abs.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(kf_path, img_abs)

            sc_duration = float(s_data.get("duration") or 4.0)
            scene = Scene(
                id=scene_id,
                index=i,
                duration=max(1.0, min(15.0, sc_duration)),
                narration=str(s_data.get("narration") or "").strip(),
                image_prompt=str(s_data.get("image_prompt") or "").strip(),
                video_prompt=str(s_data.get("video_prompt") or "").strip(),
                image_path=img_rel,
            )
            created_scenes.append(scene)

        project.scenes = created_scenes
        project.n_scenes = len(created_scenes)
        await self.db.save_project(project)

        # 6. Optionally auto-start generation
        if auto_start:
            from ..deps import task_queue

            await task_queue.submit(project.id, "full")

        return project

    # ------------------------------------------------------------------ H3
    async def _vision_json(self, vision: Any, prompt: str, images: list[Path]) -> dict[str, Any]:
        """Vision call with high-detail images (timecodes must be legible); falls back to text-only LLM."""
        cfg = config_manager.get()
        try:
            try:
                return await vision.complete_json_with_images(prompt, images, detail="high")
            except TypeError:  # provider without the detail kwarg
                return await vision.complete_json_with_images(prompt, images)
        except Exception as exc:
            log.warning("Vision H3 analysis failed (%s); falling back to text-only LLM", exc)
            llm = get_llm(cfg)
            return await llm.complete_json(prompt)

    async def _clone_h3(
        self,
        *,
        proj_id: str,
        p_dir: Path,
        source_abs: Path,
        duration: float,
        aspect: AspectRatio,
        language: str,
        motion: Motion,
        style_id: Optional[str],
        title_override: Optional[str],
        voice: Optional[str],
        auto_start: bool,
        h3_mode: str,
        character_replacement: Optional[str],
        reference_images: list[Path],
        use_ref_video: bool,
        use_ref_audio: bool,
        source_meta: Optional[dict[str, Any]] = None,
    ) -> Project:
        source_meta = dict(source_meta or {})
        cfg = config_manager.get()
        vision = get_vision(cfg)
        mode = h3_mode.lower() if h3_mode.lower() in ("ref2va", "t2va", "i2va", "fl2va") else "ref2va"
        fs = ForensicService()
        forensic_dir = p_dir / "forensics"

        # 1. Evidence channels: probe, sparse frames, audio (RMS / onsets / breath gaps / pitch), transitions
        res = await fs.run_probe(source_abs, forensic_dir)
        has_audio = res.has_audio
        use_audio = bool(use_ref_audio and has_audio and mode == "ref2va")
        use_video = bool(use_ref_video and mode == "ref2va") or (mode == "ref2va" and not reference_images)

        # 2. Long-clip segmentation at breathing points (<= 15 s per H3 call)
        plans = plan_segments(res.duration or duration, res.breath_gaps, res.transitions)

        # 3. Identity pictures (<Picture 1..N>) copied into the project
        pic_rels: list[str] = []
        for i, src in enumerate(reference_images[:9]):
            if src.is_file():
                rel = f"{proj_id}/h3_refs/picture_{i + 1}{src.suffix.lower() or '.png'}"
                dst = storage.abs_path(rel)
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
                pic_rels.append(rel)

        # 4. Whole-video timecoded contact sheets for the overview pass
        sparse = res.frame_paths
        if len(sparse) > 64:
            step = len(sparse) / 64
            picked = [(sparse[int(i * step)], int(i * step)) for i in range(64)]
        else:
            picked = [(p, i) for i, p in enumerate(sparse)]
        overview_sheets: list[Path] = []
        for c in range(0, len(picked), 16):
            chunk = [(p, round(i * 0.5 + 0.25, 2), round(i * 0.5 + 0.25, 2)) for p, i in picked[c : c + 16]]
            sheet = build_timecoded_sheet(chunk, forensic_dir / f"overview_{c // 16 + 1:02d}.jpg")
            if sheet:
                overview_sheets.append(sheet)

        # 5. Per-part reference media, first/last frames and dense timecoded sheets
        segments: list[H3Segment] = []
        seg_sheets: list[list[Path]] = []
        for plan in plans:
            seg_dir = forensic_dir / f"part_{plan.index + 1:02d}"
            seg_dir.mkdir(parents=True, exist_ok=True)
            seg = H3Segment(
                index=plan.index,
                start=plan.start,
                end=plan.end,
                duration=plan.duration,
                request_duration=request_duration(plan.duration),
                reason=plan.reason,
            )
            try:
                ref_v, ref_a = await fs.cut_reference_media(
                    source_abs, plan.start, plan.end, seg_dir / "ref_video.mp4", seg_dir / "ref_audio.wav" if has_audio else None
                )
                seg.ref_video_path = _rel(ref_v)
                seg.ref_audio_path = _rel(ref_a) if ref_a else None
            except Exception as exc:
                seg.warnings.append(f"參考片段切割失敗：{exc}")
            for attr, t, name in (("first_frame_path", plan.start + 0.04, "first.jpg"), ("last_frame_path", max(plan.start, plan.end - 0.1), "last.jpg")):
                try:
                    out = seg_dir / name
                    await ffmpeg.extract_frame(source_abs, t, out, width=768)
                    if out.is_file():
                        setattr(seg, attr, _rel(out))
                except Exception as exc:
                    log.warning("Frame extraction failed at %.2f: %s", t, exc)
            fps = 4.0 if plan.duration <= 8.0 else 2.0
            sheets: list[Path] = []
            try:
                frames = await fs.extract_window_frames(source_abs, plan.start, plan.end, fps, seg_dir / "frames", width=320)
                for c in range(0, len(frames), 16):
                    sh = build_timecoded_sheet(frames[c : c + 16], seg_dir / f"sheet_{c // 16 + 1:02d}.jpg")
                    if sh:
                        sheets.append(sh)
            except Exception as exc:
                seg.warnings.append(f"密幀取證圖產生失敗：{exc}")
            seg.sheet_paths = [_rel(p) for p in sheets]
            seg_sheets.append(sheets)
            segments.append(seg)

        # 6. Pass 1 - whole-video triage, shared subjects, Chinese report
        overview_prompt = analyze_video_h3_overview_prompt(
            language=language,
            duration_seconds=res.duration or duration,
            aspect_ratio=aspect,
            dossier=res.summary_text,
            segments=[p.to_dict() for p in plans],
            n_images=len(overview_sheets),
            n_pictures=len(pic_rels),
            character_replacement=character_replacement,
        )
        try:
            overview = await self._vision_json(vision, overview_prompt, overview_sheets)
        except Exception as exc:
            raise VideoCloneError(f"MiniMax H3 影片取證總覽分析失敗: {exc}") from exc
        film_type = str(overview.get("film_type") or "C_montage")
        style_line = str(overview.get("style_line") or "").strip()
        subjects_block = str(overview.get("subjects_block") or "").strip()
        overlays = [str(x) for x in (overview.get("post_text_overlays") or []) if str(x).strip()]

        # 7. Pass 2 - one H3 prompt per part, sequential so hand-off states chain
        prev_hand = ""
        n_ok = 0
        for seg, sheets in zip(segments, seg_sheets):
            local = ForensicService.compose_summary(
                duration=res.duration, width=res.width, height=res.height, fps=res.fps, n_frames=len(res.frame_paths),
                has_audio=has_audio, tempo=res.estimated_tempo, has_bgm=res.has_bgm, onset_cv=res.onset_cv,
                band_e=res.band_energies, rms_env=res.rms_envelope, onsets=res.onsets, transitions=res.transitions,
                breath_gaps=res.breath_gaps, pitch_hz=res.pitch_hz, offset=seg.start, end=seg.end,
            )
            prompt = analyze_h3_segment_prompt(
                language=language,
                part_index=seg.index,
                part_count=len(segments),
                seg_start=seg.start,
                seg_end=seg.end,
                request_duration=seg.request_duration,
                aspect_ratio=aspect,
                local_dossier=local,
                film_type=film_type,
                style_line=style_line,
                subjects_block=subjects_block,
                prev_hand_off=prev_hand,
                h3_mode=mode,
                use_video=use_video,
                use_audio=use_audio,
                has_audio=has_audio,
                n_pictures=len(pic_rels),
                n_images=len(sheets),
            )
            try:
                data = await self._vision_json(vision, prompt, sheets)
            except Exception as exc:
                seg.status, seg.error = "failed", f"提示詞生成失敗：{exc}"
                continue
            seg.prompt = str(data.get("h3_prompt") or "").strip()
            seg.hand_off_state = str(data.get("hand_off_state") or "").strip()
            shots = data.get("shots") or []
            seg.shots = [s for s in shots if isinstance(s, dict)] if isinstance(shots, list) else []
            seg.warnings += [str(w) for w in (data.get("warnings") or []) if str(w).strip()]
            seg.warnings += validate_h3_prompt(seg.prompt, mode=mode, duration=seg.duration)
            prev_hand = seg.hand_off_state or prev_hand
            if seg.prompt:
                n_ok += 1
        if n_ok == 0:
            raise VideoCloneError("MiniMax H3 分段提示詞全部生成失敗，請檢查多模態模型設定（設定 → 審片模型）。")

        # 8. Persist project
        title = (title_override or "").strip() or str(overview.get("title") or "短影片復刻").strip()
        report = self._h3_report(overview, res, plans, segments, overlays)
        src_line = source_header(source_meta)
        if src_line:
            report = src_line + "\n\n" + report
        joined_prompt = "\n\n".join(
            f"### PART {s.index + 1}/{len(segments)} - source {s.start:.2f}-{s.end:.2f}s, duration {s.request_duration}s (trim to {s.duration:.2f}s)\n{s.prompt}"
            for s in segments
        )
        (p_dir / "h3_prompt.txt").write_text(joined_prompt, encoding="utf-8")
        (p_dir / "forensic_report.md").write_text(report, encoding="utf-8")

        project = Project(
            id=proj_id,
            source_url=source_meta.get("webpage_url") or source_meta.get("url"),
            source_meta=source_meta,
            title=title,
            topic=str(overview.get("theme") or title),
            input_mode="video",
            language=language,
            aspect_ratio=aspect,
            style_id=(style_id or "").strip() or "cinematic",
            style_prompt=style_line,
            motion=motion,
            voice=voice or (cfg.tts.voice if hasattr(cfg.tts, "voice") else "zh-TW-HsiaoChenNeural"),
            subtitle_enabled=False,
            n_scenes=len(segments),
            h3_prompt=joined_prompt,
            forensic_report=report,
            h3_mode=mode,  # type: ignore[arg-type]
            h3_segments=segments,
            h3_use_ref_video=use_video,
            h3_use_ref_audio=use_audio,
            h3_reference_images=pic_rels,
            h3_subjects=subjects_block,
        )
        scenes: list[Scene] = []
        for seg in segments:
            sid = project.next_scene_id()
            img_rel: Optional[str] = None
            if seg.first_frame_path and storage.abs_path(seg.first_frame_path).is_file():
                img_rel = storage.scene_rel(proj_id, sid, "ref_frame", "jpg")
                dst = storage.abs_path(img_rel)
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(storage.abs_path(seg.first_frame_path), dst)
            summary = "；".join(str(s.get("summary") or "") for s in seg.shots if s.get("summary"))
            scenes.append(
                Scene(
                    id=sid,
                    index=seg.index,
                    duration=max(1.0, seg.duration),
                    narration="",
                    image_prompt=summary or f"Part {seg.index + 1}",
                    video_prompt=seg.prompt,
                    image_path=img_rel,
                )
            )
        project.scenes = scenes
        project.n_scenes = len(scenes)
        await self.db.save_project(project)

        if auto_start:
            from ..deps import task_queue

            await task_queue.submit(project.id, "h3_generate")
        return project

    @staticmethod
    def _h3_report(overview: dict[str, Any], res: Any, plans: list[Any], segments: list[H3Segment], overlays: list[str]) -> str:
        parts = [str(overview.get("forensic_report") or "").strip()]
        parts.append("## 自動取證數據")
        parts.append("```\n" + res.summary_text + "\n```")
        rows = ["| 段 | 源片區間 | 實際長度 | H3 duration | 切點依據 |", "|---|---|---|---|---|"]
        for p, s in zip(plans, segments):
            rows.append(f"| Part {p.index + 1} | {p.start:.2f}–{p.end:.2f} | {p.duration:.2f}s | {s.request_duration} | {p.reason} |")
        parts.append("## 分段計畫\n" + "\n".join(rows))
        if overlays:
            parts.append("## 後製字卡文字（H3 不生成文字，請於後製加上）\n" + "\n".join(f"- {o}" for o in overlays))
        table = str(overview.get("character_replacement_table") or "").strip()
        if table:
            parts.append("## 角色替換對照表\n" + table)
        warn = [f"- Part {s.index + 1}：{w}" for s in segments for w in s.warnings]
        if warn:
            parts.append("## 自檢警告與待確認\n" + "\n".join(warn))
        return "\n\n".join(p for p in parts if p)
