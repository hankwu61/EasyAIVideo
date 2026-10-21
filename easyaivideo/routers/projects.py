import asyncio
from typing import Any, Literal, Optional

from fastapi import APIRouter, File, Form, HTTPException, Query, Response, UploadFile, status

from ..config import BGM_DIR, config_manager
from ..deps import projects, task_queue
from ..models import (
    AssetsRequest,
    BoundAsset,
    BurnSubtitlesRequest,
    EpisodeUpdate,
    H3GenerateRequest,
    H3SegmentUpdate,
    Motion,
    Project,
    ProjectCreate,
    ProjectUpdate,
    PublishRequest,
    QuickVideoRequest,
    SceneCreate,
    SceneReorder,
    SceneUpdate,
    SubtitleCueModel,
    SubtitlesUpdateRequest,
    SynthesizeCueRequest,
    Task,
    TrimVideoRequest,
    new_id,
    now_iso,
)
from ..providers.registry import get_tts
from ..services import ffmpeg, slide_service, source_loader, storage, subtitle_service
from ..services.project_service import NotFound
from ..services.series import SeriesError
from ..services.source_loader import SourceError
from ..services.subtitle_service import SubtitleCue
from ..services.task_queue import ActiveTaskError

router = APIRouter(prefix="/api/projects", tags=["projects"])
UPLOAD_KINDS = {"image", "end_image", "audio", "video"}
MAX_UPLOAD = 200 * 1024 * 1024
MAX_SOURCE = 50 * 1024 * 1024


def _404(exc: Exception) -> HTTPException:
    return HTTPException(status.HTTP_404_NOT_FOUND, str(exc))


async def _submit(project_id: str, task_type: str, payload: dict[str, Any] | None = None) -> Task:
    try:
        await projects.get(project_id)
    except NotFound as exc:
        raise _404(exc) from exc
    try:
        return await task_queue.submit(project_id, task_type, payload)  # type: ignore[arg-type]
    except ActiveTaskError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, f"此專案已有任務執行中 ({exc.task.type})，請等待完成或取消。") from exc


@router.get("")
async def list_projects(include_episodes: bool = False) -> list[dict[str, Any]]:
    return await projects.list(include_episodes=include_episodes)


@router.post("", response_model=Project, status_code=status.HTTP_201_CREATED)
async def create_project(body: ProjectCreate) -> Project:
    try:
        project = await projects.create(body)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    if body.auto_start:
        if project.kind == "series":
            if project.source_chars > 0:
                await task_queue.submit(project.id, "analyze")
        else:
            await task_queue.submit(project.id, "full")
    return await projects.get(project.id)


@router.post("/quick-video", response_model=Project, status_code=status.HTTP_201_CREATED)
async def create_quick_video(body: QuickVideoRequest) -> Project:
    """Create and immediately generate a single video from a single prompt."""
    import base64

    prompt = body.prompt.strip()
    if not prompt:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "提示詞不能為空。")

    title = body.title.strip() if body.title else prompt[:24]
    p_create = ProjectCreate(
        title=title,
        topic=prompt,
        input_mode="prompt",
        n_scenes=1,
        aspect_ratio=body.aspect_ratio,
        motion=body.motion,
        video_mode=body.video_mode,
        style_id=body.style_id,
        style_prompt=body.style_prompt,
        voice=body.voice or "zh-TW-HsiaoChenNeural",
        subtitle_enabled=body.with_narration,
        auto_start=False,
    )
    try:
        project = await projects.create(p_create)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc

    # Create initial scene with user-chosen duration
    scene_id = project.next_scene_id()
    rel: Optional[str] = None
    if body.image_base64:
        try:
            raw_b64 = body.image_base64.split(",", 1)[-1]
            img_bytes = base64.b64decode(raw_b64)
            rel = storage.scene_rel(project.id, scene_id, "image", "png")
            abs_path = storage.abs_path(rel)
            abs_path.parent.mkdir(parents=True, exist_ok=True)
            abs_path.write_bytes(img_bytes)
        except Exception:
            rel = None

    end_rel: Optional[str] = None
    if body.end_image_base64:
        try:
            raw_b64 = body.end_image_base64.split(",", 1)[-1]
            img_bytes = base64.b64decode(raw_b64)
            end_rel = storage.scene_rel(project.id, scene_id, "end_image", "png")
            abs_path = storage.abs_path(end_rel)
            abs_path.parent.mkdir(parents=True, exist_ok=True)
            abs_path.write_bytes(img_bytes)
        except Exception:
            end_rel = None

    scene = Scene(
        id=scene_id,
        index=0,
        narration=prompt if body.with_narration else "",
        image_prompt=prompt,
        end_image_prompt=prompt if end_rel else None,
        video_prompt=prompt,
        image_path=rel,
        end_image_path=end_rel,
        duration=body.duration,
    )
    project.scenes = [scene]
    await projects.db.save_project(project)

    # Submit task "full"
    try:
        await task_queue.submit(project.id, "full")
    except Exception as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, f"任務啟動失敗: {exc}") from exc

    return await projects.get(project.id)


@router.post("/clone-video", response_model=Project, status_code=status.HTTP_201_CREATED)
async def clone_video_project(
    video_file: Optional[UploadFile] = File(None),
    source_url: Optional[str] = Form(None),
    title: Optional[str] = Form(None),
    language: str = Form("zh-TW"),
    motion: Motion = Form("ai_video"),
    style_id: Optional[str] = Form(None),
    auto_start: bool = Form(False),
    voice: Optional[str] = Form(None),
    generation_mode: str = Form("minimax_h3"),
    h3_mode: str = Form("ref2va"),
    character_replacement: Optional[str] = Form(None),
    use_ref_video: bool = Form(True),
    use_ref_audio: bool = Form(True),
    reference_images: Optional[list[UploadFile]] = File(None),
) -> Project:
    """Clone a short video from an uploaded file OR a web URL (YouTube / TikTok / Bilibili / X / direct .mp4 ...)."""
    from pathlib import Path
    import shutil
    import tempfile
    from ..services.video_clone_service import VideoCloneError, VideoCloneService
    from ..services.video_fetcher import VideoFetchError, fetch_video

    url = (source_url or "").strip()
    has_file = video_file is not None and bool(video_file.filename)
    if has_file and url:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "請擇一提供：上傳影片檔案或影片網址。")
    if not has_file and not url:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "請上傳短影片檔案或貼上影片網址。")

    work_dir = Path(tempfile.mkdtemp(prefix="eav_clone_"))
    pic_paths: list[Path] = []
    source_meta: dict[str, Any] = {}

    try:
        for up in reference_images or []:
            pname = (up.filename or "").lower()
            if not pname.endswith((".jpg", ".jpeg", ".png", ".webp")):
                raise HTTPException(status.HTTP_400_BAD_REQUEST, f"參考圖片格式不支援：{up.filename}（請用 JPG / PNG / WEBP）")
            data = await up.read()
            if not data:
                continue
            pp = work_dir / f"picture_{len(pic_paths) + 1}{Path(pname).suffix}"
            pp.write_bytes(data)
            pic_paths.append(pp)

        if has_file:
            assert video_file is not None
            fn = video_file.filename or ""
            allowed_exts = (".mp4", ".mov", ".webm", ".mkv", ".avi")
            if not any(fn.lower().endswith(ext) for ext in allowed_exts):
                raise HTTPException(status.HTTP_400_BAD_REQUEST, "請上傳 MP4、MOV、WebM 等短影片格式檔案。")
            content = await video_file.read()
            if not content:
                raise HTTPException(status.HTTP_400_BAD_REQUEST, "上傳的短影片檔案是空的。")
            tmp_path = work_dir / f"upload{Path(fn).suffix.lower() or '.mp4'}"
            tmp_path.write_bytes(content)
        else:
            try:
                fetched = await fetch_video(url, work_dir / "download")
            except VideoFetchError as exc:
                raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
            tmp_path = fetched.path
            source_meta = fetched.meta()

        service = VideoCloneService(projects.db)
        project = await service.clone_from_video(
            tmp_path,
            language=language,
            motion=motion,
            style_id=style_id,
            title_override=title,
            voice=voice,
            auto_start=auto_start,
            generation_mode=generation_mode,
            h3_mode=h3_mode,
            character_replacement=character_replacement,
            reference_images=pic_paths,
            use_ref_video=use_ref_video,
            use_ref_audio=use_ref_audio,
            source_meta=source_meta or None,
        )
        return project
    except HTTPException:
        raise
    except VideoCloneError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, f"短影片分析復刻失敗: {exc}") from exc
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


@router.get("/{project_id}/h3-prompt")
async def get_project_h3_prompt(project_id: str) -> dict[str, Any]:
    try:
        project = await projects.get(project_id)
    except NotFound as exc:
        raise _404(exc) from exc
    return {
        "project_id": project.id,
        "title": project.title,
        "h3_prompt": project.h3_prompt or "",
        "forensic_report": project.forensic_report or "",
        "h3_mode": project.h3_mode,
        "segments": [s.model_dump() for s in project.h3_segments],
    }


@router.patch("/{project_id}/h3-segments/{index}", response_model=Project)
async def update_h3_segment(project_id: str, index: int, body: H3SegmentUpdate) -> Project:
    from ..services.h3_prompt_tools import validate_h3_prompt

    try:
        project = await projects.get(project_id)
    except NotFound as exc:
        raise _404(exc) from exc
    seg = next((s for s in project.h3_segments if s.index == index), None)
    if seg is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"H3 分段 {index} 不存在。")
    if body.prompt is not None:
        seg.prompt = body.prompt.strip()
        seg.warnings = validate_h3_prompt(seg.prompt, mode=project.h3_mode, duration=seg.duration)
        scene = next((sc for sc in project.scenes if sc.index == index), None)
        if scene is not None:
            scene.video_prompt = seg.prompt
    if body.request_duration is not None:
        seg.request_duration = body.request_duration
    parts = [
        f"### PART {s.index + 1}/{len(project.h3_segments)} - source {s.start:.2f}-{s.end:.2f}s, duration {s.request_duration}s (trim to {s.duration:.2f}s)\n{s.prompt}"
        for s in project.h3_segments
    ]
    project.h3_prompt = "\n\n".join(parts)
    return await projects.db.save_project(project)


@router.post("/{project_id}/h3-generate", response_model=Task, status_code=status.HTTP_202_ACCEPTED)
async def generate_h3_video(project_id: str, body: H3GenerateRequest) -> Task:
    payload: dict[str, Any] = {"force": body.force}
    if body.segment_indexes:
        payload["segment_indexes"] = body.segment_indexes
    return await _submit(project_id, "h3_generate", payload)


@router.post("/slide", response_model=Project, status_code=status.HTTP_201_CREATED)
async def create_slide_project(
    pptx_file: UploadFile = File(...),
    guide_file: Optional[UploadFile] = File(None),
    guide_text: Optional[str] = Form(None),
    title: Optional[str] = Form(None),
    language: str = Form("zh-TW"),
    aspect_ratio: str = Form("16:9"),
    voice: str = Form("zh-TW-YunJheNeural"),
    tts_speed: float = Form(1.0),
    bgm: Optional[str] = Form(None),
    bgm_volume: float = Form(0.2),
    subtitle_enabled: bool = Form(True),
    subtitle_position: str = Form("bottom"),
    font_family: str = Form("msjh"),
    font_size: int = Form(24),
    show_title: bool = Form(False),
    transition: str = Form("none"),
    transition_duration: float = Form(0.5),
    motion: str = Form("static"),
    template_id: Optional[str] = Form(None),
    auto_start: bool = Form(True),
) -> Project:
    if not pptx_file.filename or not pptx_file.filename.lower().endswith(".pptx"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "請上傳 .pptx 格式的 PowerPoint 簡報檔案。")

    proj_id = new_id("proj")
    p_dir = storage.project_dir(proj_id)
    p_dir.mkdir(parents=True, exist_ok=True)

    # Save PPTX
    pptx_path = p_dir / "presentation.pptx"
    content = await pptx_file.read()
    if not content:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "簡報檔案是空的。")
    pptx_path.write_bytes(content)

    # Read guide text if provided
    final_guide_text = (guide_text or "").strip()
    if guide_file and guide_file.filename:
        guide_bytes = await guide_file.read()
        if guide_bytes:
            decoded_guide = source_loader.decode_bytes(guide_bytes)
            final_guide_text = (final_guide_text + "\n\n" + decoded_guide).strip()
            # Save companion guide
            (p_dir / "SPEAKER_GUIDE.md").write_text(final_guide_text, encoding="utf-8")

    # Instantiate project
    proj_title = (title or "").strip() or pptx_file.filename.rsplit(".", 1)[0]
    project = Project(
        id=proj_id,
        title=proj_title,
        topic=proj_title,
        input_mode="slide",
        language=language,
        aspect_ratio=aspect_ratio,  # type: ignore[arg-type]
        voice=voice,
        tts_speed=tts_speed,
        bgm=bgm,
        bgm_volume=bgm_volume,
        subtitle_enabled=subtitle_enabled,
        subtitle_position=subtitle_position,  # type: ignore[arg-type]
        font_family=font_family,
        font_size=font_size,
        show_title=show_title,
        transition=transition,  # type: ignore[arg-type]
        transition_duration=transition_duration,
        motion=motion,  # type: ignore[arg-type]
        template_id=template_id,
    )

    try:
        # Import presentation in thread to avoid blocking event loop
        project = await asyncio.to_thread(
            slide_service.import_presentation, project, pptx_path, final_guide_text
        )
    except Exception as exc:
        storage.delete_project_files(proj_id)
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"解析簡報失敗: {exc}") from exc

    await projects.db.save_project(project)

    if auto_start:
        await task_queue.submit(project.id, "full")

    return await projects.get(project.id)


@router.get("/{project_id}", response_model=Project)
async def get_project(project_id: str) -> Project:
    try:
        return await projects.get(project_id)
    except NotFound as exc:
        raise _404(exc) from exc


@router.patch("/{project_id}", response_model=Project)
async def update_project(project_id: str, body: ProjectUpdate) -> Project:
    try:
        return await projects.update(project_id, body)
    except NotFound as exc:
        raise _404(exc) from exc


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(project_id: str) -> None:
    try:
        project = await projects.get(project_id)
    except NotFound as exc:
        raise _404(exc) from exc
    if project.active_task:
        await task_queue.cancel(project.active_task.id)
    for ep in project.episodes:
        if ep.task_status and ep.project_id:
            active = await task_queue.db.active_task(ep.project_id)
            if active:
                await task_queue.cancel(active.id)
    await projects.delete(project_id)


# ---- scenes -------------------------------------------------------------

@router.get("/{project_id}/asset-library", response_model=list[BoundAsset])
async def asset_library(project_id: str):
    from ..services.storyboard import catalog
    project = await projects.get(project_id)
    owner = await projects.get(project.parent_id) if project.parent_id else project
    return catalog(owner)


@router.post("/{project_id}/asset-library", response_model=list[BoundAsset])
async def add_library_asset(project_id: str, name: str = Form(...),
                            kind: Literal["character", "location", "prop"] = Form(...),
                            description: str = Form(""), file: Optional[UploadFile] = File(None)):
    from io import BytesIO
    from PIL import Image
    from ..services.storyboard import catalog
    project = await projects.get(project_id)
    owner = await projects.get(project.parent_id) if project.parent_id else project
    if owner.active_task or project.active_task:
        raise HTTPException(409, "生成中，請稍後再新增資產。")
    if not name.strip() or len(name.strip()) > 100:
        raise HTTPException(400, "資產名稱須為 1–100 字。")
    asset = BoundAsset(kind=kind, name=name.strip(), description=description)
    if file:
        data = await file.read(20 * 1024 * 1024 + 1)
        if len(data) > 20 * 1024 * 1024:
            raise HTTPException(413, "圖片不得超過 20 MB。")
        try:
            with Image.open(BytesIO(data)) as img:
                img.verify()
                ext = (img.format or "png").lower()
        except Exception as exc:
            raise HTTPException(400, "請上傳有效圖片。") from exc
        asset.image_path = f"{owner.id}/assets/{asset.id}.{ext}"
        path = storage.abs_path(asset.image_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    owner.assets.append(asset)
    await projects.db.save_project(owner)
    return catalog(owner)


@router.post("/{project_id}/scenes/{scene_id}/versions/{version_id}", response_model=Project)
async def select_media_version(project_id: str, scene_id: str, version_id: str):
    try:
        return await projects.select_version(project_id, scene_id, version_id)
    except NotFound as exc:
        raise _404(exc) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.patch("/{project_id}/scenes/{scene_id}", response_model=Project)
async def update_scene(project_id: str, scene_id: str, body: SceneUpdate) -> Project:
    try:
        return await projects.update_scene(project_id, scene_id, body)
    except NotFound as exc:
        raise _404(exc) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/{project_id}/scenes", response_model=Project)
async def add_scene(project_id: str, body: SceneCreate) -> Project:
    try:
        return await projects.add_scene(project_id, body)
    except NotFound as exc:
        raise _404(exc) from exc


@router.delete("/{project_id}/scenes/{scene_id}", response_model=Project)
async def delete_scene(project_id: str, scene_id: str) -> Project:
    try:
        return await projects.delete_scene(project_id, scene_id)
    except NotFound as exc:
        raise _404(exc) from exc


@router.post("/{project_id}/scenes/reorder", response_model=Project)
async def reorder_scenes(project_id: str, body: SceneReorder) -> Project:
    try:
        return await projects.reorder(project_id, body.scene_ids)
    except NotFound as exc:
        raise _404(exc) from exc
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc


@router.post("/{project_id}/scenes/{scene_id}/upload/{kind}", response_model=Project)
async def upload_scene_asset(project_id: str, scene_id: str, kind: str, file: UploadFile = File(...)) -> Project:
    if kind not in UPLOAD_KINDS:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "kind must be image, end_image, audio or video")
    data = await file.read()
    if not data:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "empty file")
    if len(data) > MAX_UPLOAD:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "file too large")
    try:
        return await projects.upload_asset(project_id, scene_id, kind, file.filename or "", data)
    except NotFound as exc:
        raise _404(exc) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"無法處理上傳檔案: {exc}") from exc


@router.get("/{project_id}/scenes/images.zip")
async def download_scene_images(project_id: str) -> Response:
    """All scene images (and AI clips when present) as one zip, named by scene order."""
    import io
    import zipfile

    from ..services import storage
    from .files import attachment_headers

    try:
        project = await projects.get(project_id)
    except NotFound as exc:
        raise _404(exc) from exc
    buf = io.BytesIO()
    count = 0
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as zf:
        for scene in project.scenes:
            for rel, label in ((scene.image_path, "image_start"), (scene.end_image_path, "image_end"), (scene.video_path, "clip")):
                if not rel:
                    continue
                path = storage.abs_path(rel)
                if path.is_file():
                    zf.write(path, f"scene{scene.index + 1:02d}_{label}{path.suffix}")
                    count += 1
    if count == 0:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "此專案還沒有任何場景圖。")
    headers = attachment_headers(f"{project.title or project.id}_scenes.zip")
    return Response(content=buf.getvalue(), media_type="application/zip", headers=headers)


def _generate_video_prompts_text(project: Project) -> str:
    lines = [
        f"【專案】{project.title or project.id} - 影片提示詞",
        f"【總場景數】{len(project.scenes)} 場",
        "",
    ]
    for i, scene in enumerate(project.scenes, 1):
        lines.append("=" * 50)
        lines.append(f"第 {i} 場 (Scene {i}):")
        prompt = scene.video_prompt.strip() if scene.video_prompt else ""
        lines.append(prompt if prompt else "(無影片提示詞)")
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def _generate_image_prompts_text(project: Project) -> str:
    lines = [
        f"【專案】{project.title or project.id} - 圖片提示詞 (首幀/尾幀)",
        f"【總場景數】{len(project.scenes)} 場",
        "",
    ]
    for i, scene in enumerate(project.scenes, 1):
        lines.append("=" * 50)
        lines.append(f"第 {i} 場 (Scene {i}):")
        start_prompt = scene.image_prompt.strip() if scene.image_prompt else ""
        end_prompt = scene.end_image_prompt.strip() if scene.end_image_prompt else ""
        lines.append(f"【首幀提示詞】：\n{start_prompt if start_prompt else '(無首幀提示詞)'}")
        if end_prompt:
            lines.append(f"\n【尾幀提示詞】：\n{end_prompt}")
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def _generate_narration_text(project: Project) -> str:
    lines = [
        f"【專案】{project.title or project.id} - 旁白台詞",
        f"【總場景數】{len(project.scenes)} 場",
        "",
    ]
    for i, scene in enumerate(project.scenes, 1):
        lines.append("=" * 50)
        lines.append(f"第 {i} 場 (Scene {i}):")
        if scene.lines:
            dialogues = []
            for line in scene.lines:
                spk = f"{line.speaker}: " if line.speaker else ""
                dialogues.append(f"{spk}{line.text.strip()}")
            lines.append("\n".join(dialogues))
        else:
            text = scene.narration.strip() if scene.narration else ""
            lines.append(text if text else "(無旁白台詞)")
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def _generate_full_script_text(project: Project) -> str:
    lines = [
        f"【專案名稱】{project.title or project.id}",
        f"【總場景數】{len(project.scenes)} 場",
        f"【影片比例】{project.aspect_ratio}",
        "",
    ]
    for i, scene in enumerate(project.scenes, 1):
        lines.append("=" * 50)
        lines.append(f"【第 {i} 場 (Scene {i})】")
        lines.append("")
        lines.append("【旁白 / 台詞】")
        if scene.lines:
            dialogues = []
            for line in scene.lines:
                spk = f"{line.speaker}: " if line.speaker else ""
                dialogues.append(f"{spk}{line.text.strip()}")
            lines.append("\n".join(dialogues))
        else:
            text = scene.narration.strip() if scene.narration else ""
            lines.append(text if text else "(無旁白台詞)")
        lines.append("")
        lines.append("【圖片提示詞】")
        ip = scene.image_prompt.strip() if scene.image_prompt else ""
        lines.append(ip if ip else "(無圖片提示詞)")
        lines.append("")
        lines.append("【影片提示詞】")
        vp = scene.video_prompt.strip() if scene.video_prompt else ""
        lines.append(vp if vp else "(無影片提示詞)")
        lines.append("")
    return "\n".join(lines).strip() + "\n"


@router.get("/{project_id}/export/text")
async def export_project_text(
    project_id: str,
    kind: Literal["video_prompts", "image_prompts", "narration", "script", "zip"] = "script",
) -> Response:
    """Export scene texts: video prompts, image prompts, narration, full script, or all in a zip."""
    import io
    import zipfile
    from .files import attachment_headers

    try:
        project = await projects.get(project_id)
    except NotFound as exc:
        raise _404(exc) from exc

    title = project.title or project.id

    if kind == "video_prompts":
        content = _generate_video_prompts_text(project)
        headers = attachment_headers(f"{title}_影片提示詞.txt")
        return Response(content=content.encode("utf-8"), media_type="text/plain; charset=utf-8", headers=headers)
    elif kind == "image_prompts":
        content = _generate_image_prompts_text(project)
        headers = attachment_headers(f"{title}_圖片提示詞.txt")
        return Response(content=content.encode("utf-8"), media_type="text/plain; charset=utf-8", headers=headers)
    elif kind == "narration":
        content = _generate_narration_text(project)
        headers = attachment_headers(f"{title}_旁白.txt")
        return Response(content=content.encode("utf-8"), media_type="text/plain; charset=utf-8", headers=headers)
    elif kind == "script":
        content = _generate_full_script_text(project)
        headers = attachment_headers(f"{title}_完整腳本提示詞.txt")
        return Response(content=content.encode("utf-8"), media_type="text/plain; charset=utf-8", headers=headers)
    elif kind == "zip":
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr(f"01_影片提示詞.txt", _generate_video_prompts_text(project).encode("utf-8"))
            zf.writestr(f"02_圖片提示詞.txt", _generate_image_prompts_text(project).encode("utf-8"))
            zf.writestr(f"03_旁白.txt", _generate_narration_text(project).encode("utf-8"))
            zf.writestr(f"04_完整腳本提示詞.txt", _generate_full_script_text(project).encode("utf-8"))
        headers = attachment_headers(f"{title}_文字檔.zip")
        return Response(content=buf.getvalue(), media_type="application/zip", headers=headers)
    else:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Unknown export kind: {kind}")


@router.get("/{project_id}/export/texts.zip")
async def export_project_texts_zip(project_id: str) -> Response:
    return await export_project_text(project_id, kind="zip")


# ---- generation ---------------------------------------------------------


@router.post("/{project_id}/generate/script", response_model=Task, status_code=status.HTTP_202_ACCEPTED)
async def generate_script(project_id: str) -> Task:
    return await _submit(project_id, "script")


@router.post("/{project_id}/generate/assets", response_model=Task, status_code=status.HTTP_202_ACCEPTED)
async def generate_assets(project_id: str, body: AssetsRequest | None = None) -> Task:
    body = body or AssetsRequest()
    return await _submit(project_id, "assets", body.model_dump())


@router.post("/{project_id}/render", response_model=Task, status_code=status.HTTP_202_ACCEPTED)
async def render(project_id: str) -> Task:
    return await _submit(project_id, "render")


@router.post("/{project_id}/generate/all", response_model=Task, status_code=status.HTTP_202_ACCEPTED)
async def generate_all(project_id: str) -> Task:
    return await _submit(project_id, "full")


@router.post("/{project_id}/review", response_model=Task, status_code=status.HTTP_202_ACCEPTED)
async def review_project(project_id: str) -> Task:
    """AI review: keyframes of the rendered video vs narration (multimodal model)."""
    try:
        project = await projects.get(project_id)
    except NotFound as exc:
        raise _404(exc) from exc
    if not project.final_video_url:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "請先合成影片，AI 審片會檢查成品的關鍵幀。")
    return await _submit(project_id, "review")


@router.delete("/{project_id}/review", response_model=Project)
async def clear_review(project_id: str) -> Project:
    try:
        project = await projects.get(project_id)
    except NotFound as exc:
        raise _404(exc) from exc
    project.review = None
    await projects.db.save_project(project)
    return await projects.get(project_id)


# ---- series: source documents ------------------------------------------


@router.post("/{project_id}/source", response_model=Project)
async def upload_source(project_id: str, file: UploadFile = File(...)) -> Project:
    data = await file.read()
    if not data:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "empty file")
    if len(data) > MAX_SOURCE:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "file too large (max 50 MB)")
    try:
        return await projects.upload_source(project_id, file.filename or "document.txt", data)
    except NotFound as exc:
        raise _404(exc) from exc
    except SourceError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"無法讀取文檔: {exc}") from exc


@router.get("/{project_id}/source")
async def get_source(project_id: str, offset: int = Query(0, ge=0), limit: int = Query(20000, ge=1, le=200000)) -> dict[str, Any]:
    try:
        return await projects.source_text(project_id, offset, limit)
    except NotFound as exc:
        raise _404(exc) from exc


@router.delete("/{project_id}/source", response_model=Project)
async def clear_source(project_id: str) -> Project:
    try:
        return await projects.clear_source(project_id)
    except NotFound as exc:
        raise _404(exc) from exc


# ---- series: analysis, planning, episodes --------------------------------


@router.post("/{project_id}/analyze", response_model=Task, status_code=status.HTTP_202_ACCEPTED)
async def analyze(project_id: str) -> Task:
    return await _submit(project_id, "analyze")


@router.post("/{project_id}/plan-episodes", response_model=Task, status_code=status.HTTP_202_ACCEPTED)
async def plan_episodes(project_id: str) -> Task:
    return await _submit(project_id, "plan")


@router.post("/{project_id}/characters/{char_id}/generate-image", response_model=Task, status_code=status.HTTP_202_ACCEPTED)
async def generate_character_image(project_id: str, char_id: str) -> Task:
    return await _submit(project_id, "character_image", {"char_id": char_id})


@router.patch("/{project_id}/episodes/{index}", response_model=Project)
async def update_episode(project_id: str, index: int, body: EpisodeUpdate) -> Project:
    try:
        return await projects.update_episode(project_id, index, body)
    except NotFound as exc:
        raise _404(exc) from exc
    except SeriesError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc


@router.post("/{project_id}/episodes/generate-all", response_model=list[Task], status_code=status.HTTP_202_ACCEPTED)
async def generate_all_episodes(project_id: str) -> list[Task]:
    try:
        project = await projects.get(project_id)
    except NotFound as exc:
        raise _404(exc) from exc
    if project.kind != "series":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "只有系列專案可以生成集數。")
    if not project.episodes:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "尚未規劃分集。")
    tasks: list[Task] = []
    for ep in project.episodes:
        if ep.status == "rendered" or ep.task_status:
            continue
        child_id = await projects.episode_project_id(project_id, ep.index)
        try:
            tasks.append(await task_queue.submit(child_id, "full"))
        except ActiveTaskError:
            continue
    return tasks


@router.post("/{project_id}/episodes/{index}/create", response_model=Project)
async def create_episode(project_id: str, index: int) -> Project:
    try:
        return await projects.create_episode(project_id, index)
    except NotFound as exc:
        raise _404(exc) from exc
    except (SeriesError, ValueError) as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc


@router.post("/{project_id}/episodes/{index}/generate", response_model=Task, status_code=status.HTTP_202_ACCEPTED)
async def generate_episode(project_id: str, index: int) -> Task:
    try:
        child_id = await projects.episode_project_id(project_id, index)
    except NotFound as exc:
        raise _404(exc) from exc
    except (SeriesError, ValueError) as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    try:
        return await task_queue.submit(child_id, "full")
    except ActiveTaskError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, f"第 {index} 集已有任務執行中 ({exc.task.type})。") from exc


@router.post("/{project_id}/publish", response_model=Task, status_code=status.HTTP_202_ACCEPTED)
async def publish_video(project_id: str, body: Optional[PublishRequest] = None) -> Task:
    try:
        project = await projects.get(project_id)
    except NotFound as exc:
        raise _404(exc) from exc

    if not project.final_video_path or not storage.abs_path(project.final_video_path).exists():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "請先合成影片後再進行發布。")

    payload: dict[str, Any] = {}
    if body:
        if body.platforms:
            project.publish_settings.platforms = body.platforms
            payload["platforms"] = body.platforms
        if body.privacy:
            project.publish_settings.privacy = body.privacy
            payload["privacy"] = body.privacy
        if body.schedule_time is not None:
            project.publish_settings.schedule_time = body.schedule_time
            payload["schedule_time"] = body.schedule_time
        if body.auto_publish is not None:
            project.publish_settings.auto_publish = body.auto_publish
        if body.title:
            payload["title"] = body.title
        if body.description:
            payload["description"] = body.description
        if body.tags:
            payload["tags"] = body.tags

    # Only schedule if schedule_time was explicitly provided in the request and is in the future
    sched = body.schedule_time if (body and body.schedule_time) else None
    if sched and sched > now_iso():
        project.publish_status = "scheduled"
        project.publish_settings.schedule_mode = "scheduled"
        project.publish_settings.schedule_time = sched
        await projects.db.save_project(project)
        task = Task(
            id=new_id("task"),
            project_id=project_id,
            type="publish",
            status="queued",
            message=f"已排程於 {sched} 發布",
            payload=payload,
        )
        await projects.db.save_task(task)
        return task

    # Immediate publishing
    project.publish_settings.schedule_time = None
    project.publish_settings.schedule_mode = "immediate"
    project.publish_status = "publishing"
    await projects.db.save_project(project)
    return await _submit(project_id, "publish", payload)


@router.delete("/{project_id}/publish/schedule", response_model=Project)
async def cancel_publish_schedule(project_id: str) -> Project:
    try:
        project = await projects.get(project_id)
    except NotFound as exc:
        raise _404(exc) from exc

    project.publish_settings.schedule_time = None
    project.publish_settings.schedule_mode = "immediate"
    if project.publish_status == "scheduled":
        project.publish_status = "idle"
    await projects.db.save_project(project)
    return project


# ---- post-production: subtitles, burn-in, video clipping, cue audio -----


@router.get("/{project_id}/subtitles", response_model=list[SubtitleCueModel])
async def get_subtitles(project_id: str) -> list[SubtitleCueModel]:
    try:
        project = await projects.get(project_id)
    except NotFound as exc:
        raise _404(exc) from exc

    if project.subtitles_path:
        srt_abs = storage.abs_path(project.subtitles_path)
        if srt_abs.exists():
            content = srt_abs.read_text(encoding="utf-8")
            cues = subtitle_service.parse_srt_content(content)
            return [SubtitleCueModel(id=c.id, start=c.start, end=c.end, text=c.text) for c in cues]

    # Generate initial cues from project scenes
    cues = subtitle_service.generate_cues_from_project_scenes(project)
    return [SubtitleCueModel(id=c.id, start=c.start, end=c.end, text=c.text) for c in cues]


@router.put("/{project_id}/subtitles", response_model=list[SubtitleCueModel])
async def update_subtitles(project_id: str, body: SubtitlesUpdateRequest) -> list[SubtitleCueModel]:
    try:
        project = await projects.get(project_id)
    except NotFound as exc:
        raise _404(exc) from exc

    cue_objs = [SubtitleCue(id=c.id, start=c.start, end=c.end, text=c.text) for c in body.cues]
    srt_content = subtitle_service.serialize_cues_to_srt(cue_objs)

    srt_rel = storage.output_rel(project_id, "subtitles", "srt")
    srt_abs = storage.abs_path(srt_rel)
    srt_abs.parent.mkdir(parents=True, exist_ok=True)
    srt_abs.write_text(srt_content, encoding="utf-8")

    project.subtitles_path = srt_rel
    await projects.db.save_project(project)
    return body.cues


@router.post("/{project_id}/burn-subtitles")
async def burn_subtitles(project_id: str, body: BurnSubtitlesRequest) -> dict[str, Any]:
    try:
        project = await projects.get(project_id)
    except NotFound as exc:
        raise _404(exc) from exc

    if not project.final_video_path:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "專案尚未合成最終影片，無法燒錄字幕。")
    if not project.subtitles_path:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "專案尚未產生字幕檔。")

    # Prefer clean raw video without subtitles as source
    src_video_path = project.raw_video_path or project.final_video_path
    video_abs = storage.abs_path(src_video_path)
    srt_abs = storage.abs_path(project.subtitles_path)
    if not video_abs.exists() or not srt_abs.exists():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "影片或字幕檔案遺失。")

    burned_rel = storage.output_rel(project_id, "video_burned", "mp4")
    burned_abs = storage.abs_path(burned_rel)

    try:
        await ffmpeg.burn_subtitles(
            video=video_abs,
            srt_path=srt_abs,
            output=burned_abs,
            font_name=body.font_name,
            font_size=body.font_size,
            primary_color=body.primary_color,
            back_color=body.back_color,
            border_style=body.border_style,
            outline=body.outline,
            outline_color=body.outline_color,
            alignment=body.alignment,
            margin_v=body.margin_v,
            margin_l=body.margin_l,
        )
    except Exception as exc:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, f"燒錄字幕失敗: {exc}") from exc

    # If raw_video_path was not set before, preserve the original clean video
    if not project.raw_video_path:
        project.raw_video_path = project.final_video_path

    # Point final video to newly burned video (but keep raw_video_path clean!)
    if project.final_video_path != project.raw_video_path:
        storage.remove(project.final_video_path)
    project.final_video_path = burned_rel
    project.final_video_size = burned_abs.stat().st_size
    await projects.db.save_project(project)

    return {
        "ok": True,
        "burned_video_url": f"/api/files/{burned_rel}",
        "final_video_url": project.final_video_url,
    }


@router.post("/{project_id}/trim-video")
async def trim_video_endpoint(project_id: str, body: TrimVideoRequest) -> dict[str, Any]:
    try:
        project = await projects.get(project_id)
    except NotFound as exc:
        raise _404(exc) from exc

    if not project.final_video_path:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "專案尚未合成最終影片。")

    video_abs = storage.abs_path(project.final_video_path)
    if not video_abs.exists():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "影片檔案遺失。")

    trimmed_rel = storage.output_rel(project_id, f"trimmed_{int(body.start)}_{int(body.end)}", "mp4")
    trimmed_abs = storage.abs_path(trimmed_rel)

    try:
        await ffmpeg.trim_video(video=video_abs, start=body.start, end=body.end, output=trimmed_abs)
    except Exception as exc:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, f"剪輯影片失敗: {exc}") from exc

    return {
        "ok": True,
        "trimmed_video_url": f"/api/files/{trimmed_rel}",
        "duration": round(body.end - body.start, 2),
    }


@router.post("/{project_id}/synthesize-cue")
async def synthesize_cue_endpoint(project_id: str, body: SynthesizeCueRequest) -> dict[str, Any]:
    try:
        project = await projects.get(project_id)
    except NotFound as exc:
        raise _404(exc) from exc

    if not body.text.strip():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "請提供欲配音的文字。")

    cfg = config_manager.get()
    tts = get_tts(cfg)
    voice = body.voice or project.voice or cfg.tts.voice
    speed = body.speed or project.tts_speed or cfg.tts.speed or 1.0

    cue_rel = storage.output_rel(project_id, f"cue_{new_id('aud')}", "mp3")
    cue_abs = storage.abs_path(cue_rel)
    cue_abs.parent.mkdir(parents=True, exist_ok=True)

    try:
        await tts.synthesize(body.text.strip(), voice, speed, cue_abs)
        duration = await ffmpeg.probe_duration(cue_abs)
    except Exception as exc:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, f"語音合成失敗: {exc}") from exc

    return {
        "ok": True,
        "audio_url": f"/api/files/{cue_rel}",
        "duration": round(duration, 3),
    }


@router.get("/{project_id}/audio-waveform")
async def get_audio_waveform(
    project_id: str,
    bgm: Optional[str] = Query(None, description="Optional BGM track filename"),
) -> dict[str, Any]:
    """Return authentic high-resolution PCM audio waveform peaks for voice and BGM."""
    try:
        project = await projects.get(project_id)
    except NotFound as exc:
        raise _404(exc) from exc

    voice_data: dict[str, Any] = {"duration": 0.0, "sampleRate": 30, "peaks": []}
    bgm_data: Optional[dict[str, Any]] = None

    # 1. Resolve Voice / Video Media Path
    media_rel = project.raw_video_url or project.final_video_url
    if media_rel:
        # Strip leading /api/files/ if present
        clean_rel = media_rel.replace("/api/files/", "")
        media_abs = storage.abs_path(clean_rel)
        if media_abs.exists():
            voice_data = await ffmpeg.extract_audio_peaks(media_abs, points_per_second=30)

    # 2. Resolve BGM Track if specified
    bgm_target = bgm or getattr(project, "bgm", None) or getattr(project, "bgm_track", None)
    if bgm_target:
        clean_bgm = str(bgm_target).strip().replace("\\", "/").split("/")[-1]
        bgm_path = BGM_DIR / clean_bgm
        if bgm_path.exists():
            bgm_data = await ffmpeg.extract_audio_peaks(bgm_path, points_per_second=30)

    return {
        "ok": True,
        "voice": voice_data,
        "bgm": bgm_data,
    }


