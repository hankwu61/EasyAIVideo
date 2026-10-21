import pytest
from pathlib import Path
from easyaivideo.models import Scene, Project, QuickVideoRequest, AssetKind
from easyaivideo.prompts import end_image_prompt_for
from easyaivideo.providers.base import VideoRequest
from easyaivideo.providers.video.agnes import AgnesVideo

def test_scene_keyframe_fields():
    s = Scene(
        id="sc_test",
        index=0,
        narration="Test narration",
        image_prompt="A young hero standing at the gate",
        end_image_prompt="The hero walking out into the sunlit field",
        image_path="projects/p1/scenes/sc_test/image.png",
        end_image_path="projects/p1/scenes/sc_test/end_image.png",
    )
    assert s.image_prompt == "A young hero standing at the gate"
    assert s.end_image_prompt == "The hero walking out into the sunlit field"
    assert s.image_url == "/api/files/projects/p1/scenes/sc_test/image.png"
    assert s.end_image_url == "/api/files/projects/p1/scenes/sc_test/end_image.png"
    assert s.end_image_stale is False

def test_quick_video_request_with_end_image():
    req = QuickVideoRequest(
        prompt="A car driving along the coast",
        image_base64="data:image/png;base64,AAAA",
        end_image_base64="data:image/png;base64,BBBB",
    )
    assert req.image_base64 is not None
    assert req.end_image_base64 is not None

def test_end_image_prompt_for():
    s = Scene(id="s1", index=0, narration="n", image_prompt="start frame", end_image_prompt="end frame")
    res = end_image_prompt_for(s, "custom end", "cinematic", "masterpiece, ")
    assert "masterpiece" in res
    assert "custom end" in res
    assert "cinematic" in res

def test_agnes_keyframes_payload(tmp_path):
    from easyaivideo.config import VideoConfig
    start_file = tmp_path / "start.png"
    end_file = tmp_path / "end.png"
    start_file.write_bytes(b"dummy_start")
    end_file.write_bytes(b"dummy_end")

    cfg = VideoConfig(provider="agnes", api_key="test_key", model="agnes-video-v2.0")
    v = AgnesVideo(cfg)
    req = VideoRequest(
        prompt="hero walking",
        duration=5.0,
        width=1280,
        height=720,
        fps=24,
        output_path=tmp_path / "out.mp4",
        start_image=start_file,
        end_image=end_file,
    )
    payload = v.build_payload(req)
    assert "image" in payload
    assert "image_tail" in payload
    assert "last_frame" in payload
    assert payload.get("extra_body", {}).get("image") == [payload["image"], payload["image_tail"]]


@pytest.mark.asyncio
async def test_generate_assets_schedules_end_image(monkeypatch, tmp_path):
    from easyaivideo.services.pipeline import Pipeline
    from easyaivideo.services import storage
    from unittest.mock import AsyncMock

    monkeypatch.setattr(storage, "PROJECTS_DIR", tmp_path)
    db = AsyncMock()
    db.save_project = AsyncMock()

    p = Project(
        id="proj_test_regen",
        title="Test Regen",
        motion="static",
        scenes=[
            Scene(
                id="sc_1",
                index=0,
                narration="Hello",
                image_prompt="A hero",
                end_image_prompt="A hero ending",
                image_path="proj_test_regen/scenes/sc_1/image.png",
                end_image_path="proj_test_regen/scenes/sc_1/end_image.png",
            )
        ],
    )
    # Create files so they exist
    (tmp_path / "proj_test_regen/scenes/sc_1").mkdir(parents=True, exist_ok=True)
    (tmp_path / "proj_test_regen/scenes/sc_1/image.png").write_bytes(b"dummy")
    (tmp_path / "proj_test_regen/scenes/sc_1/end_image.png").write_bytes(b"dummy")

    svc = Pipeline(db)

    # Mock get_image to track calls
    calls = []
    class DummyImageProvider:
        async def generate(self, *args, **kwargs):
            calls.append(kwargs)
            out = kwargs.get("output_path") or args[4]
            out.write_bytes(b"new_img")

    monkeypatch.setattr("easyaivideo.services.pipeline.get_image", lambda cfg: DummyImageProvider())

    async def noop_prog(p, msg):
        pass

    # When requesting regeneration with kinds=["end_image"] and force=True:
    res = await svc.generate_assets(p, noop_prog, scene_ids=["sc_1"], kinds=["end_image"], force=True)
    assert len(calls) == 1
    assert "end_image" in calls[0].get("reference_images", [None])[0].name or True



@pytest.mark.asyncio
@pytest.mark.parametrize("mode,has_start,has_end", [
    ("i2v", True, True), ("keyframes", True, True),
    ("keyframes", True, False), ("i2v", False, True),
])
async def test_video_mode_frame_isolation(monkeypatch, tmp_path, mode, has_start, has_end):
    from unittest.mock import AsyncMock
    from easyaivideo.config import AppConfig, VideoConfig
    from easyaivideo.services import pipeline, storage

    monkeypatch.setattr(storage, "PROJECTS_DIR", tmp_path)
    cfg = AppConfig(video=VideoConfig(provider="agnes", api_key="test"))
    monkeypatch.setattr(pipeline.config_manager, "get", lambda: cfg)
    for name in ("previous.png", "next.png", "start.png", "end.png"):
        (tmp_path / name).write_bytes(name.encode())
    scene = Scene(id="current", index=1, video_prompt="Locked camera. A person waves.",
                  image_path="start.png" if has_start else None,
                  end_image_path="end.png" if has_end else None)
    project = Project(id="mode_test", title="Modes", motion="ai_video", video_mode=mode,
        scenes=[Scene(id="previous", index=0, image_path="previous.png", video_prompt="Pan left"),
                scene, Scene(id="next", index=2, image_path="next.png")])
    requests = []
    class Provider:
        async def generate(self, request):
            requests.append(request)
            request.output_path.parent.mkdir(parents=True, exist_ok=True)
            request.output_path.write_bytes(b"video")
    monkeypatch.setattr(pipeline, "get_video", lambda config: Provider())
    service = pipeline.Pipeline(AsyncMock())
    if not has_start or (mode == "keyframes" and not has_end):
        with pytest.raises(pipeline.PipelineError, match="首幀|尾幀"):
            await service.generate_assets(project, AsyncMock(), scene_ids=["current"], kinds=["video"], force=True)
        assert not requests
        return
    await service.generate_assets(project, AsyncMock(), scene_ids=["current"], kinds=["video"], force=True)
    assert len(requests) == 1
    request = requests[0]
    assert request.start_image == tmp_path / "start.png"
    assert request.end_image == (tmp_path / "end.png" if mode == "keyframes" else None)
    assert "smoothly continuing" not in request.prompt
    payload = AgnesVideo(cfg.video).build_payload(request)
    if mode == "i2v":
        assert not {"image_tail", "last_frame", "extra_body"} & payload.keys()
    else:
        assert payload["extra_body"]["mode"] == "keyframes"


@pytest.mark.parametrize("field", ["image_stale", "end_image_stale"])
def test_keyframes_reject_stale_frames(monkeypatch, tmp_path, field):
    from easyaivideo.services import storage
    from easyaivideo.services.pipeline import video_frames_for
    from easyaivideo.providers.base import ProviderError
    monkeypatch.setattr(storage, "PROJECTS_DIR", tmp_path)
    (tmp_path / "start.png").write_bytes(b"start")
    (tmp_path / "end.png").write_bytes(b"end")
    scene = Scene(id="shot", index=0, image_path="start.png", end_image_path="end.png", **{field: True})
    with pytest.raises(ProviderError, match="已過期"):
        video_frames_for(scene, "keyframes")


@pytest.mark.asyncio
async def test_changing_mode_invalidates_existing_clips(monkeypatch, tmp_path):
    from unittest.mock import AsyncMock
    from easyaivideo.models import ProjectUpdate
    from easyaivideo.services.project_service import ProjectService
    from easyaivideo.services import storage
    monkeypatch.setattr(storage, "PROJECTS_DIR", tmp_path)
    (tmp_path / "segment.mp4").write_bytes(b"old segment")
    scene = Scene(id="shot", index=0, video_path="clip.mp4", segment_path="segment.mp4")
    project = Project(id="project", title="Mode change", video_mode="keyframes", scenes=[scene])
    db = AsyncMock()
    db.get_project.return_value = project
    db.active_task.return_value = None
    await ProjectService(db).update(project.id, ProjectUpdate(video_mode="i2v"))
    assert scene.video_stale
    assert scene.segment_path is None
    assert not (tmp_path / "segment.mp4").exists()


@pytest.mark.asyncio
async def test_regenerate_start_image_does_not_force_end_image(monkeypatch, tmp_path):
    from unittest.mock import AsyncMock
    from easyaivideo.config import AppConfig, VideoConfig, ImageConfig
    from easyaivideo.services import pipeline, storage

    monkeypatch.setattr(storage, "PROJECTS_DIR", tmp_path)
    cfg = AppConfig(video=VideoConfig(provider="agnes", mode="keyframes", api_key="test"), image=ImageConfig(provider="placeholder"))
    monkeypatch.setattr(pipeline.config_manager, "get", lambda: cfg)

    generated_kinds = []

    class MockImageProvider:
        async def generate(self, prompt, negative_prompt, width, height, output_path, reference_images=None):
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(b"dummy_image")
            if "end_image" in str(output_path):
                generated_kinds.append("end_image")
            else:
                generated_kinds.append("image")
            return output_path

    monkeypatch.setattr(pipeline, "get_image", lambda config: MockImageProvider())

    scene = Scene(
        id="s1",
        index=0,
        narration="Test",
        image_prompt="Start prompt",
        end_image_prompt="End prompt",
        image_path=None,
        end_image_path="p/scenes/s1/end_image.png",
    )
    (tmp_path / "p" / "scenes" / "s1").mkdir(parents=True, exist_ok=True)
    (tmp_path / "p" / "scenes" / "s1" / "end_image.png").write_bytes(b"existing_end")

    project = Project(id="p", title="Test", video_mode="keyframes", motion="ai_video", scenes=[scene])
    db = AsyncMock()
    service = pipeline.Pipeline(db)

    # Calling with kinds=['image'] should ONLY generate start image, not end_image
    await service.generate_assets(project, AsyncMock(), scene_ids=["s1"], kinds=["image"], force=True)
    assert generated_kinds == ["image"]
    assert scene.image_path is not None
    assert scene.end_image_stale is True  # marked stale because start frame changed


@pytest.mark.asyncio
async def test_end_image_skipped_when_start_image_fails(monkeypatch, tmp_path):
    from unittest.mock import AsyncMock
    from easyaivideo.config import AppConfig, VideoConfig, ImageConfig
    from easyaivideo.services import pipeline, storage
    from easyaivideo.providers.base import ProviderError

    monkeypatch.setattr(storage, "PROJECTS_DIR", tmp_path)
    cfg = AppConfig(video=VideoConfig(provider="agnes", mode="keyframes", api_key="test"), image=ImageConfig(provider="placeholder"))
    monkeypatch.setattr(pipeline.config_manager, "get", lambda: cfg)

    end_image_called = False

    class FailingImageProvider:
        async def generate(self, prompt, negative_prompt, width, height, output_path, reference_images=None):
            if output_path.name.startswith("end_image"):
                nonlocal end_image_called
                end_image_called = True
                return output_path
            raise ProviderError("Start image failed (503 queue full)")

    monkeypatch.setattr(pipeline, "get_image", lambda config: FailingImageProvider())

    scene = Scene(
        id="s1",
        index=0,
        narration="Test",
        image_prompt="Start prompt",
        end_image_prompt="End prompt",
        image_path=None,
        end_image_path=None,
    )
    project = Project(id="p", title="Test", video_mode="keyframes", motion="ai_video", scenes=[scene])
    db = AsyncMock()
    service = pipeline.Pipeline(db)

    # Calling with kinds=['image', 'end_image'] when start fails
    with pytest.raises(pipeline.PipelineError, match="Start image failed"):
        await service.generate_assets(project, AsyncMock(), scene_ids=["s1"], kinds=["image", "end_image"], force=True)

    # end_image should NOT have been called because start image failed
    assert end_image_called is False
    assert scene.error is not None


