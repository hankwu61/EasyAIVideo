from io import BytesIO
from unittest.mock import AsyncMock

import pytest
from PIL import Image

from easyaivideo.models import BoundAsset, Project, Scene, SceneCreate, SceneUpdate, Task
from easyaivideo.services import storage, storyboard
from easyaivideo.services.project_service import ProjectService


def setup(monkeypatch, tmp_path):
    monkeypatch.setattr(storage, "PROJECTS_DIR", tmp_path)
    scene = Scene(id="s01", image_path="p/old.png", video_path="p/old.mp4", segment_path="p/segment.mp4")
    project = Project(id="p", scenes=[scene], scene_counter=1)
    for name in ("old.png", "old.mp4", "segment.mp4"):
        target = tmp_path / "p" / name
        target.parent.mkdir(exist_ok=True)
        target.write_bytes(b"original")
    db = AsyncMock()
    db.get_project.return_value = project
    db.active_task.return_value = None
    return ProjectService(db), project, scene


@pytest.mark.asyncio
async def test_uploaded_versions_survive_selection_and_missing_version(monkeypatch, tmp_path):
    service, project, scene = setup(monkeypatch, tmp_path)
    buf = BytesIO()
    Image.new("RGB", (16, 16), "red").save(buf, format="PNG")
    await service.upload_asset("p", "s01", "image", "new.png", buf.getvalue())
    assert len(scene.media_history) == 2
    new_path = scene.image_path
    old = scene.media_history[0]
    await service.select_version("p", "s01", old.id)
    assert scene.image_path == "p/old.png"
    assert storage.abs_path(new_path).is_file()
    assert scene.video_stale and scene.segment_path is None
    assert not scene.image_stale
    with pytest.raises(ValueError):
        await service.select_version("p", "s01", "another-scenes-version")


@pytest.mark.asyncio
async def test_bindings_are_frozen_and_validate_ids(monkeypatch, tmp_path):
    service, project, scene = setup(monkeypatch, tmp_path)
    project.assets = [BoundAsset(id="sword", kind="prop", name="長劍", description="silver blade", image_path="p/old.png")]
    await service.update_scene("p", "s01", SceneUpdate(asset_ids=["sword"]))
    project.assets[0].description = "changed"
    storage.remove("p/old.png")
    assert "silver blade" in storyboard.binding_prompt(scene)
    assert len(storyboard.binding_refs(scene)) == 1
    assert scene.image_stale and scene.video_stale
    with pytest.raises(ValueError):
        await service.update_scene("p", "s01", SceneUpdate(asset_ids=["missing"]))


@pytest.mark.asyncio
async def test_group_does_not_reorder_and_add_below_inherits(monkeypatch, tmp_path):
    service, project, scene = setup(monkeypatch, tmp_path)
    await service.update_scene("p", "s01", SceneUpdate(group="覺醒"))
    await service.add_scene("p", SceneCreate(after="s01"))
    assert [s.id for s in project.scenes] == ["s01", "s02"]
    assert [s.group for s in project.scenes] == ["覺醒", "覺醒"]


@pytest.mark.asyncio
async def test_active_generation_blocks_version_and_binding_changes(monkeypatch, tmp_path):
    service, project, scene = setup(monkeypatch, tmp_path)
    service.db.active_task.return_value = Task(id="t", project_id="p", type="assets", status="running")
    with pytest.raises(ValueError):
        await service.update_scene("p", "s01", SceneUpdate(asset_ids=[]))
    with pytest.raises(ValueError):
        await service.select_version("p", "s01", "v")


def test_legacy_scene_defaults():
    scene = Scene.model_validate({"id": "legacy"})
    assert scene.group == "" and not scene.asset_bindings and not scene.media_history
    assert scene.stage_positions == []


@pytest.mark.asyncio
async def test_staging_persists_invalidates_media_and_drives_prompt(monkeypatch, tmp_path):
    service, project, scene = setup(monkeypatch, tmp_path)
    body = SceneUpdate(stage_positions=[{"character_id": "hero", "name": "Hero", "x": 25, "y": 70, "facing": 90}])
    await service.update_scene("p", "s01", body)
    restored = Project.model_validate_json(project.model_dump_json())
    assert restored.scenes[0].stage_positions[0].x == 25
    assert "Hero: x=25%, y=70%, facing=90" in storyboard.binding_prompt(scene)
    assert scene.image_stale and scene.video_stale and scene.segment_path is None
    await service.update_scene("p", "s01", SceneUpdate(stage_positions=[]))
    assert storyboard.staging_prompt(scene) == ""


@pytest.mark.asyncio
async def test_staging_rejects_duplicate_characters_and_running_task(monkeypatch, tmp_path):
    service, project, scene = setup(monkeypatch, tmp_path)
    pos = {"character_id": "hero", "name": "Hero"}
    with pytest.raises(ValueError, match="重複"):
        await service.update_scene("p", "s01", SceneUpdate(stage_positions=[pos, pos]))
    assert not scene.stage_positions
    service.db.active_task.return_value = Task(id="t", project_id="p", type="assets", status="running")
    with pytest.raises(ValueError):
        await service.update_scene("p", "s01", SceneUpdate(stage_positions=[pos]))


@pytest.mark.parametrize("patch", [{"x": -1}, {"y": 101}, {"facing": 360}, {"x": float("nan")}])
def test_staging_validates_coordinates(patch):
    with pytest.raises(ValueError):
        SceneUpdate(stage_positions=[{"character_id": "hero", "name": "Hero", **patch}])
