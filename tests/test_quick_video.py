import pytest
import base64
from unittest.mock import AsyncMock, patch
from easyaivideo.models import Project, ProjectCreate, QuickVideoRequest, Scene
from easyaivideo.presets import INPUT_MODES
from easyaivideo.services.pipeline import Pipeline
from easyaivideo.db import db
from easyaivideo.services import storage


def test_input_mode_prompt_in_presets():
    prompt_mode = next((m for m in INPUT_MODES if m["id"] == "prompt"), None)
    assert prompt_mode is not None
    assert "單一提示詞" in prompt_mode["label"]


def test_quick_video_request_model():
    req = QuickVideoRequest(
        prompt="A futuristic robot cat playing cyber chess in a neon lit cafe, 8k cinematic",
        duration=8,
        aspect_ratio="16:9",
        motion="ai_video",
        with_narration=True,
    )
    assert req.prompt.startswith("A futuristic robot")
    assert req.duration == 8
    assert req.aspect_ratio == "16:9"
    assert req.motion == "ai_video"
    assert req.with_narration is True


@pytest.mark.asyncio
async def test_pipeline_generate_script_prompt_mode(monkeypatch):
    from unittest.mock import AsyncMock
    motion = "The camera stays fixed as the cat raises the cup to its mouth."
    llm = AsyncMock()
    llm.complete.return_value = motion
    monkeypatch.setattr("easyaivideo.services.pipeline.get_llm", lambda cfg: llm)
    await db.init()
    pipeline = Pipeline(db)
    project = Project(
        id="proj_test_prompt",
        title="Quick Cat Video",
        topic="A high-tech cyberpunk cat drinking boba tea under rain",
        input_mode="prompt",
        language="en",
        aspect_ratio="16:9",
        style_id="cinematic",
        style_prompt="cinematic lighting, photorealistic",
        n_scenes=1,
    )

    async def dummy_progress(ratio: float, msg: str) -> None:
        pass

    # In prompt mode, generate_script should create exactly 1 scene
    # and directly map the prompt to image_prompt and video_prompt
    updated = await pipeline.generate_script(project, dummy_progress)

    assert len(updated.scenes) == 1
    scene = updated.scenes[0]
    assert scene.index == 0
    assert "cyberpunk cat" in scene.image_prompt.lower()
    assert scene.video_prompt == motion
    assert "one main action and one camera behavior" in llm.complete.call_args.args[0]


@pytest.mark.asyncio
async def test_quick_video_with_base64_image(tmp_path):
    await db.init()
    # 1x1 transparent PNG as base64
    tiny_png_b64 = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
    raw_b64 = tiny_png_b64.split(",", 1)[-1]
    img_bytes = base64.b64decode(raw_b64)
    assert len(img_bytes) > 0

    project = Project(
        id="proj_test_quick_img",
        title="Quick I2V Video",
        topic="An eagle flying over snow mountains",
        input_mode="prompt",
        language="zh-TW",
        aspect_ratio="16:9",
        style_id="cinematic",
        n_scenes=1,
    )
    scene_id = project.next_scene_id()
    rel = storage.scene_rel(project.id, scene_id, "image", "png")
    abs_path = storage.abs_path(rel)
    abs_path.parent.mkdir(parents=True, exist_ok=True)
    abs_path.write_bytes(img_bytes)

    scene = Scene(
        id=scene_id,
        index=0,
        narration="An eagle flying over snow mountains",
        image_prompt="An eagle flying over snow mountains",
        video_prompt="An eagle flying over snow mountains",
        image_path=rel,
        duration=6.0,
    )
    project.scenes = [scene]
    await db.save_project(project)

    loaded = await db.get_project("proj_test_quick_img")
    assert loaded is not None
    assert len(loaded.scenes) == 1
    assert loaded.scenes[0].image_path == rel
    assert abs_path.exists()
    assert abs_path.read_bytes() == img_bytes

    # Clean up
    if abs_path.exists():
        abs_path.unlink()


def test_required_kinds_prompt_mode():
    from easyaivideo.services.pipeline import _required_kinds

    p_prompt_no_sub = Project(id="p1", input_mode="prompt", subtitle_enabled=False, motion="ai_video")
    kinds = _required_kinds(p_prompt_no_sub)
    assert "audio" not in kinds
    assert "image" in kinds
    assert "video" in kinds

    p_prompt_with_sub = Project(id="p2", input_mode="prompt", subtitle_enabled=True, motion="ai_video")
    kinds_with_sub = _required_kinds(p_prompt_with_sub)
    assert "audio" in kinds_with_sub

    p_topic = Project(id="p3", input_mode="topic", subtitle_enabled=False, motion="ai_video")
    assert "audio" in _required_kinds(p_topic)


def test_agnes_1080p_frame_limit_clamping():
    from easyaivideo.config import VideoConfig
    from easyaivideo.providers.video.agnes import AgnesVideo
    from easyaivideo.providers.base import VideoRequest
    from pathlib import Path

    cfg = VideoConfig(
        provider="agnes",
        api_key="test-key",
        resolution="1080p",
        max_clip_seconds=18,
    )
    provider = AgnesVideo(cfg)

    # Even with 18 seconds requested duration, 1080p should be clamped to 241 frames max
    req = VideoRequest(
        prompt="Cyberpunk drone",
        duration=18.0,
        width=1920,
        height=1080,
        fps=24,
        output_path=Path("dummy.mp4"),
    )
    payload = provider.build_payload(req)
    assert payload["num_frames"] <= 241
    assert payload["height"] == 1080 or payload["width"] == 1080


@pytest.mark.asyncio
async def test_agnes_submit_auto_clamp_on_400():
    from easyaivideo.config import VideoConfig
    from easyaivideo.providers.video.agnes import AgnesVideo
    from unittest.mock import MagicMock
    import httpx

    cfg = VideoConfig(provider="agnes", api_key="test-key")
    provider = AgnesVideo(cfg)

    # Mock client: first returns 400 with "exceeds maximum 241", then returns 200 with task_id
    mock_resp_400 = MagicMock()
    mock_resp_400.status_code = 400
    mock_resp_400.text = '{"code":"fail_to_fetch_task","message":"num_frames 433 exceeds maximum 241 for 1080p/16:9"}'

    mock_resp_200 = MagicMock()
    mock_resp_200.status_code = 200
    mock_resp_200.json.return_value = {"task_id": "task_agnes_success_123"}

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.post = AsyncMock(side_effect=[mock_resp_400, mock_resp_200])

    payload = {"prompt": "test", "num_frames": 433}
    task_id = await provider._submit(mock_client, payload)
    assert task_id == "task_agnes_success_123"
    assert payload["num_frames"] == 241

