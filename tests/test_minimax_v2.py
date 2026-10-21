"""MiniMax H3 v2 payload assembly and polling (HTTP is mocked)."""

from pathlib import Path

import httpx
import pytest

from easyaivideo.config import VideoConfig
from easyaivideo.providers.base import ProviderError, VideoRequest
from easyaivideo.providers.video.minimax import MinimaxVideo, api_root, clamp_duration, infer_mode, pick_resolution


def _cfg(**kw) -> VideoConfig:
    base = {"provider": "minimax", "api_key": "k", "base_url": "", "model": "MiniMax-H3"}
    base.update(kw)
    return VideoConfig(**base)


def _req(tmp_path: Path, **kw) -> VideoRequest:
    base = dict(prompt="subject_definitions: test", duration=13.0, width=1080, height=1920, fps=24, output_path=tmp_path / "out.mp4")
    base.update(kw)
    return VideoRequest(**base)


def _file(tmp_path: Path, name: str, data: bytes = b"x" * 16) -> Path:
    p = tmp_path / name
    p.write_bytes(data)
    return p


def test_api_root_and_model_defaults():
    assert api_root("") == "https://api.minimax.io"
    assert api_root("https://apihub.agnes-ai.com/v1") == "https://api.minimax.io"  # Agnes default left in settings
    assert api_root("https://api.minimaxi.com/v1/") == "https://api.minimaxi.com"
    assert api_root("https://api.minimax.io/v2") == "https://api.minimax.io"
    assert MinimaxVideo(_cfg(model="agnes-video-v2.0")).model == "MiniMax-H3"
    assert MinimaxVideo(_cfg(model="minimax-h3-max")).model == "MiniMax-H3-Max"
    assert clamp_duration("MiniMax-H3", 2) == 4 and clamp_duration("MiniMax-H3-Max", 4) == 5 and clamp_duration("MiniMax-H3", 30) == 15
    assert pick_resolution("MiniMax-H3", "2K") == "2K" and pick_resolution("MiniMax-H3-Max", "2K") == "768P"
    assert pick_resolution("MiniMax-H3", "480P") == "768P"


def test_ref2va_payload(tmp_path: Path):
    v = _file(tmp_path, "ref.mp4")
    a = _file(tmp_path, "ref.wav")
    pic = _file(tmp_path, "p1.png")
    prov = MinimaxVideo(_cfg(minimax_resolution="2K"))
    payload = prov.build_payload(
        _req(tmp_path, reference_videos=[v], reference_audios=[a], reference_images=[pic], h3_mode="ref2va", ratio="9:16")
    )
    assert payload["model"] == "MiniMax-H3" and payload["resolution"] == "2K" and payload["duration"] == 13
    assert payload["ratio"] == "9:16"
    roles = [(c["type"], c.get("role")) for c in payload["content"]]
    assert roles == [("text", None), ("image_url", "reference_image"), ("video_url", "reference_video"), ("audio_url", "reference_audio")]
    assert payload["content"][2]["video_url"]["url"].startswith("data:video/mp4;base64,")
    assert payload["content"][3]["audio_url"]["url"].startswith("data:audio/wav;base64,")


def test_ref2va_requires_visual_reference(tmp_path: Path):
    a = _file(tmp_path, "ref.wav")
    with pytest.raises(ProviderError):
        MinimaxVideo(_cfg()).build_payload(_req(tmp_path, reference_audios=[a], h3_mode="ref2va"))


def test_i2v_fl2v_t2v_payloads(tmp_path: Path):
    first = _file(tmp_path, "first.jpg")
    last = _file(tmp_path, "last.jpg")
    prov = MinimaxVideo(_cfg())
    p = prov.build_payload(_req(tmp_path, start_image=first, h3_mode="i2va", ratio="9:16"))
    assert p["ratio"] == "adaptive" and [c.get("role") for c in p["content"]] == [None, "first_frame"]
    p = prov.build_payload(_req(tmp_path, start_image=first, end_image=last))
    assert [c.get("role") for c in p["content"]] == [None, "first_frame", "last_frame"]
    p = prov.build_payload(_req(tmp_path, h3_mode="t2va"))
    assert p["ratio"] == "9:16" and len(p["content"]) == 1
    assert infer_mode(_req(tmp_path, end_image=last)) == "l2va"


def test_prompt_limit(tmp_path: Path):
    with pytest.raises(ProviderError):
        MinimaxVideo(_cfg()).build_payload(_req(tmp_path, prompt="x" * 7001, h3_mode="t2va"))


@pytest.mark.asyncio
async def test_generate_submit_poll_download(tmp_path: Path, monkeypatch):
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(f"{request.method} {request.url.path}")
        if request.method == "POST" and request.url.path == "/v2/video_generation":
            return httpx.Response(200, json={"task_id": "t123"})
        if request.url.path == "/v2/query/video_generation/t123":
            return httpx.Response(200, json={"task": {"id": "t123", "status": "succeeded", "content": {"url": "https://cdn.example/v.mp4"}}})
        if request.url.host == "cdn.example":
            return httpx.Response(200, content=b"MP4DATA")
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    real_client = httpx.AsyncClient

    def fake_client(*args, **kwargs):
        kwargs["transport"] = transport
        return real_client(*args, **kwargs)

    async def no_sleep(_s):
        return None

    monkeypatch.setattr("easyaivideo.providers.video.minimax.httpx.AsyncClient", fake_client)
    monkeypatch.setattr("easyaivideo.providers.video.minimax.asyncio.sleep", no_sleep)
    out = await MinimaxVideo(_cfg()).generate(_req(tmp_path, h3_mode="t2va"))
    assert out.read_bytes() == b"MP4DATA"
    assert calls[0] == "POST /v2/video_generation" and calls[1] == "GET /v2/query/video_generation/t123"


@pytest.mark.asyncio
async def test_generate_reports_failure(tmp_path: Path, monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            return httpx.Response(200, json={"task_id": "t9"})
        return httpx.Response(200, json={"task": {"status": "failed", "error": {"code": 1, "message": "content blocked"}}})

    transport = httpx.MockTransport(handler)
    real_client = httpx.AsyncClient
    monkeypatch.setattr(
        "easyaivideo.providers.video.minimax.httpx.AsyncClient", lambda *a, **k: real_client(*a, **{**k, "transport": transport})
    )

    async def no_sleep(_s):
        return None

    monkeypatch.setattr("easyaivideo.providers.video.minimax.asyncio.sleep", no_sleep)
    with pytest.raises(ProviderError, match="content blocked"):
        await MinimaxVideo(_cfg()).generate(_req(tmp_path, h3_mode="t2va"))


def test_frames_win_over_reference_images(tmp_path: Path):
    """Normal i2v projects pass character refs too; the first frame must not be dropped."""
    first = _file(tmp_path, "first.jpg")
    ref = _file(tmp_path, "char.png")
    req = _req(tmp_path, start_image=first, reference_images=[ref])
    assert infer_mode(req) == "i2va"
    p = MinimaxVideo(_cfg()).build_payload(req)
    assert [c.get("role") for c in p["content"]] == [None, "first_frame"]
    # without frames the refs are used as R2V references
    assert infer_mode(_req(tmp_path, reference_images=[ref])) == "ref2va"


def test_max_clip_seconds_caps_normal_scenes_only(tmp_path: Path):
    prov = MinimaxVideo(_cfg(max_clip_seconds=6))
    assert prov.build_payload(_req(tmp_path, duration=12.0, h3_mode=None))["duration"] == 6
    # H3 clone parts carry an explicit mode and keep their planned duration
    assert prov.build_payload(_req(tmp_path, duration=12.0, h3_mode="t2va"))["duration"] == 12


def test_minimax_config_warnings(monkeypatch):
    from easyaivideo.config import config_manager

    cfg = config_manager.get().model_copy(deep=True)
    cfg.video.provider = "minimax"
    cfg.video.api_key = "http://127.0.0.1:8000"
    cfg.video.base_url = "https://apihub.agnes-ai.com/v1"
    monkeypatch.setattr(config_manager, "get", lambda: cfg)
    msgs = " ".join(config_manager.warnings())
    assert "looks like a URL" in msgs and "not a MiniMax URL" in msgs
    cfg.video.api_key = ""
    assert "video.api_key is empty" in " ".join(config_manager.warnings())
