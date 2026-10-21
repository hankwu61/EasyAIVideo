import json
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from easyaivideo.config import VideoConfig
from easyaivideo.providers.base import ProviderError, VideoRequest
from easyaivideo.providers.video.agnes import AgnesVideo
from easyaivideo.services.media_source import save_source


def request(tmp_path, **kwargs):
    return VideoRequest(prompt="A fixed camera. The person opens their eyes.", duration=2.5,
                        width=1280, height=720, fps=24, output_path=tmp_path / "clip.mp4", **kwargs)


def provider():
    return AgnesVideo(VideoConfig(api_key="test", model="agnes-video-v2.5", resolution="720p"))


def test_v25_modes_and_parameter_contract(tmp_path):
    start = tmp_path / "start.png"
    start.write_bytes(b"start")
    save_source(start, "https://example.com/start.png")
    end = tmp_path / "end.png"
    end.write_bytes(b"end")
    save_source(end, "https://example.com/end.png")
    p = provider()
    text = p.build_payload(request(tmp_path))
    assert text["model"] == "agnes-video-2.5"
    assert text["seconds"] == "4"
    assert text["mode"] == "text"
    single = p.build_payload(request(tmp_path, start_image=start, reference_images=[end]))
    assert single["mode"] == "keyframe"
    assert single["first_frame"] == "https://example.com/start.png"
    assert "last_frame" not in single and "images" not in single
    pair = p.build_payload(request(tmp_path, start_image=start, end_image=end))
    assert pair["last_frame"] == "https://example.com/end.png"
    ref = p.build_payload(request(tmp_path, reference_images=[start]))
    assert ref["mode"] == "reference"
    assert ref["images"] == ["https://example.com/start.png"]
    assert not {"num_frames", "width", "height", "frame_rate", "num_inference_steps", "image", "extra_body"} & pair.keys()


def test_modified_image_does_not_reuse_stale_url(tmp_path):
    path = tmp_path / "image.png"
    path.write_bytes(b"old")
    save_source(path, "https://example.com/old.png")
    path.write_bytes(b"new")
    payload = provider().build_payload(request(tmp_path, start_image=path))
    assert payload["first_frame"] != "https://example.com/old.png"
    assert payload["first_frame"].startswith("data:image/png;base64,")


def test_flash_resolution(tmp_path):
    # Flash gracefully auto-clamps resolution to 720P
    cfg = VideoConfig(api_key="test", model="agnes-video-2.5-flash", resolution="1080p")
    payload = AgnesVideo(cfg).build_payload(request(tmp_path))
    assert payload["model"] == "agnes-video-2.5-flash"
    assert payload["size"] == "720P"

    cfg.resolution = "720p"
    payload = AgnesVideo(cfg).build_payload(request(tmp_path))
    assert payload["model"] == "agnes-video-2.5-flash"
    assert payload["size"] == "720P"


@pytest.mark.asyncio
async def test_v25_uses_video_id_and_model_name(tmp_path):
    calls = []
    def handler(req):
        calls.append(req)
        if req.method == "POST":
            assert json.loads(req.content)["model"] == "agnes-video-2.5"
            return httpx.Response(200, json={"id": "task-wrong", "video_id": "video-correct"})
        if req.url.path == "/agnesapi":
            assert req.url.params["video_id"] == "video-correct"
            assert req.url.params["model_name"] == "agnes-video-2.5"
            return httpx.Response(200, json={"status": "completed", "url": "https://example.com/clip.mp4"})
        return httpx.Response(200, content=b"video")
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    with patch("easyaivideo.providers.video.agnes.httpx.AsyncClient", return_value=client), patch("easyaivideo.providers.video.agnes.asyncio.sleep", new=AsyncMock()):
        path = await provider().generate(request(tmp_path))
    assert path.read_bytes() == b"video"
    assert len(calls) == 3


@pytest.mark.asyncio
async def test_v25_retry_on_queue_full_success(tmp_path):
    attempts = 0
    def handler(req):
        nonlocal attempts
        if req.method == "POST":
            attempts += 1
            if attempts < 3:
                return httpx.Response(503, json={"code": "video_queue_full", "message": "video queue is full"})
            return httpx.Response(200, json={"video_id": "video-after-retry"})
        if req.url.path == "/agnesapi":
            return httpx.Response(200, json={"status": "completed", "url": "https://example.com/clip.mp4"})
        return httpx.Response(200, content=b"video")

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    cfg = VideoConfig(api_key="test", model="agnes-video-2.5-flash", resolution="720p")
    with patch("easyaivideo.providers.video.agnes.httpx.AsyncClient", return_value=client), patch("easyaivideo.providers.video.agnes.asyncio.sleep", new=AsyncMock()) as mock_sleep:
        path = await AgnesVideo(cfg).generate(request(tmp_path))
    assert path.read_bytes() == b"video"
    assert attempts == 3
    assert mock_sleep.call_count >= 2


@pytest.mark.asyncio
async def test_v25_fallback_query_includes_model_name(tmp_path):
    queried_params = []
    def handler(req):
        if req.method == "POST":
            return httpx.Response(200, json={"video_id": "vid-123"})
        if req.url.path == "/agnesapi":
            queried_params.append(dict(req.url.params))
            if len(queried_params) == 1:
                # First poll returns completed but without url, triggering fallback query
                return httpx.Response(200, json={"status": "completed", "video_id": "vid-123"})
            return httpx.Response(200, json={"status": "completed", "url": "https://example.com/clip.mp4"})
        return httpx.Response(200, content=b"video")

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    cfg = VideoConfig(api_key="test", model="agnes-video-2.5-flash", resolution="720p")
    with patch("easyaivideo.providers.video.agnes.httpx.AsyncClient", return_value=client), patch("easyaivideo.providers.video.agnes.asyncio.sleep", new=AsyncMock()):
        path = await AgnesVideo(cfg).generate(request(tmp_path))
    assert path.read_bytes() == b"video"
    assert len(queried_params) == 2
    assert queried_params[1]["model_name"] == "agnes-video-2.5-flash"

