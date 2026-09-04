from __future__ import annotations

from typing import Any

from fastapi import APIRouter, File, HTTPException, Query, Response, UploadFile, status

from ..deps import projects, task_queue
from ..models import (
    AssetsRequest,
    EpisodeUpdate,
    Project,
    ProjectCreate,
    ProjectUpdate,
    PublishRequest,
    SceneCreate,
    SceneReorder,
    SceneUpdate,
    Task,
    new_id,
    now_iso,
)
from ..services import storage
from ..services.project_service import NotFound
from ..services.series import SeriesError
from ..services.source_loader import SourceError
from ..services.task_queue import ActiveTaskError

router = APIRouter(prefix="/api/projects", tags=["projects"])
UPLOAD_KINDS = {"image", "audio", "video"}
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


@router.patch("/{project_id}/scenes/{scene_id}", response_model=Project)
async def update_scene(project_id: str, scene_id: str, body: SceneUpdate) -> Project:
    try:
        return await projects.update_scene(project_id, scene_id, body)
    except NotFound as exc:
        raise _404(exc) from exc


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
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "kind must be image, audio or video")
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
            for rel, label in ((scene.image_path, "image"), (scene.video_path, "clip")):
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

    sched = body.schedule_time if body and body.schedule_time is not None else project.publish_settings.schedule_time
    if sched and sched > now_iso():
        project.publish_status = "scheduled"
        project.publish_settings.schedule_mode = "scheduled"
        await projects.db.save_project(project)
        task = Task(
            id=new_id("task"),
            project_id=project_id,
            type="publish",
            status="queued",
            message=f"已排程於 {sched} 發布",
            payload=payload,
        )
        return task

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
