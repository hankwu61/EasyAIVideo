"""ComfyUI -> MiniMax H3 Partner Node provider (ComfyUI is simulated with httpx.MockTransport)."""

import json
from pathlib import Path

import httpx
import pytest

from easyaivideo.config import VideoConfig
from easyaivideo.providers.base import ProviderError, VideoRequest
from easyaivideo.providers.video.comfyui_minimax import (
    H3,
    H3_MAX,
    H3_MAX_TURBO,
    NODE_FLF,
    NODE_REF,
    NODE_T2V,
    ComfyUIMinimaxVideo,
    build_workflow,
    clamp_duration,
    normalise_model,
    pick_resolution,
    translate_error,
)


def _cfg(**kw) -> VideoConfig:
    base = {"provider": "comfyui_minimax", "comfyui_url": "http://comfy.local:8188", "comfy_api_key": "comfyui-key"}
    base.update(kw)
    return VideoConfig(**base)


def _req(tmp_path: Path, **kw) -> VideoRequest:
    base = dict(prompt="A cat on a sofa", duration=8.0, width=1080, height=1920, fps=24, output_path=tmp_path / "out.mp4", seed=7)
    base.update(kw)
    return VideoRequest(**base)


def _file(tmp_path: Path, name: str) -> Path:
    p = tmp_path / name
    p.write_bytes(b"x")
    return p


def _node(wf: dict, class_type: str) -> dict:
    return next(n for n in wf.values() if n["class_type"] == class_type)


def test_model_resolution_duration_rules():
    assert normalise_model("minimax h3 max turbo") == H3_MAX_TURBO
    assert normalise_model("MiniMax-H3-Max") == H3_MAX
    assert normalise_model("anything") == H3
    assert pick_resolution(H3, "2K") == "2K" and pick_resolution(H3_MAX, "2K") == "768P"
    assert pick_resolution(H3_MAX_TURBO, "480P") == "480P" and pick_resolution(H3, "480P") == "768P"
    assert clamp_duration(H3, 2) == 4 and clamp_duration(H3_MAX, 4) == 5 and clamp_duration(H3, 40) == 15


def test_t2v_workflow():
    wf = build_workflow(mode="t2va", model=H3, prompt="P", resolution="768P", ratio="9:16", duration=6, seed=1)
    node = _node(wf, NODE_T2V)["inputs"]
    assert node["model"] == "MiniMax H3" and node["model.prompt"] == "P" and node["model.ratio"] == "9:16"
    assert node["model.duration"] == 6 and node["model.resolution"] == "768P" and node["seed"] == 1
    assert "model.prompt_expansion_mode" not in node  # base H3 has no expansion option
    save = _node(wf, "SaveVideo")["inputs"]
    t2v_id = next(k for k, v in wf.items() if v["class_type"] == NODE_T2V)
    assert save["video"] == [t2v_id, 0]


def test_flf_workflow_has_frames_and_no_ratio():
    wf = build_workflow(mode="fl2va", model=H3_MAX, prompt="P", resolution="768P", ratio="9:16", duration=5, seed=1,
                        first_frame="a.png", last_frame="b.png")
    node = _node(wf, NODE_FLF)["inputs"]
    assert "model.ratio" not in node and node["model.prompt_expansion_mode"] == "balanced"
    assert wf[node["first_frame"][0]]["inputs"]["image"] == "a.png"
    assert wf[node["last_frame"][0]]["inputs"]["image"] == "b.png"
    with pytest.raises(ProviderError):
        build_workflow(mode="i2va", model=H3, prompt="P", resolution="768P", ratio="9:16", duration=5, seed=1)


def test_reference_workflow_inputs():
    wf = build_workflow(mode="ref2va", model=H3_MAX, prompt="P", resolution="480P", ratio="9:16", duration=10, seed=1,
                        images=["p1.png", "p2.png"], videos=["ref.mp4"], audios=["ref.wav"])
    node = _node(wf, NODE_REF)["inputs"]
    assert node["model.reference_detail"] == "standard"
    assert wf[node["model.reference_images.image_1"][0]]["class_type"] == "LoadImage"
    assert wf[node["model.reference_images.image_2"][0]]["inputs"]["image"] == "p2.png"
    assert wf[node["model.reference_videos.video_1"][0]] == {"class_type": "LoadVideo", "inputs": {"file": "ref.mp4"}, "_meta": {"title": "Reference video 1"}}
    assert wf[node["model.reference_audios.audio_1"][0]]["inputs"] == {"audio": "ref.wav"}
    with pytest.raises(ProviderError, match="Turbo"):
        build_workflow(mode="ref2va", model=H3_MAX_TURBO, prompt="P", resolution="480P", ratio="9:16", duration=5, seed=1, images=["a.png"])
    with pytest.raises(ProviderError):
        build_workflow(mode="ref2va", model=H3, prompt="P", resolution="768P", ratio="9:16", duration=5, seed=1, audios=["a.wav"])


class FakeComfy:
    """Minimal ComfyUI HTTP API: /upload/image, /prompt, /history, /view, /object_info, /system_stats."""

    def __init__(self, fail: str = ""):
        self.uploads: list[str] = []
        self.prompts: list[dict] = []
        self.fail = fail

    def __call__(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/system_stats":
            return httpx.Response(200, json={"system": {"comfyui_version": "0.34.4"}})
        if path.startswith("/object_info/"):
            node = path.rsplit("/", 1)[1]
            return httpx.Response(200, json={node: {"name": node}})
        if path == "/upload/image":
            body = request.content.decode("latin-1")
            name = body.split('filename="', 1)[1].split('"', 1)[0]
            self.uploads.append(name)
            return httpx.Response(200, json={"name": name, "subfolder": "", "type": "input"})
        if path == "/prompt":
            self.prompts.append(json.loads(request.content))
            return httpx.Response(200, json={"prompt_id": "p1", "number": 1})
        if path == "/history/p1":
            if self.fail:
                return httpx.Response(200, json={"p1": {"status": {"status_str": "error", "completed": False,
                                                                  "messages": [["execution_error", {"exception_message": self.fail}]]}, "outputs": {}}})
            return httpx.Response(200, json={"p1": {"status": {"status_str": "success", "completed": True},
                                                    "outputs": {"9": {"images": [{"filename": "h3_00001.mp4", "subfolder": "easyaivideo", "type": "output"}], "animated": [True]}}}})
        if path == "/view":
            return httpx.Response(200, content=b"MP4")
        return httpx.Response(404)


@pytest.fixture
def fake_comfy(monkeypatch):
    def install(fake: FakeComfy):
        real = httpx.AsyncClient
        transport = httpx.MockTransport(fake)
        monkeypatch.setattr("easyaivideo.providers.comfyui.httpx.AsyncClient", lambda *a, **k: real(*a, **{**k, "transport": transport}))
        monkeypatch.setattr("easyaivideo.providers.video.comfyui_minimax.httpx.AsyncClient", lambda *a, **k: real(*a, **{**k, "transport": transport}))

        async def no_sleep(_s):
            return None

        monkeypatch.setattr("easyaivideo.providers.comfyui.asyncio.sleep", no_sleep)
        return fake

    return install


@pytest.mark.asyncio
async def test_generate_reference_to_video_end_to_end(tmp_path: Path, fake_comfy):
    fake = fake_comfy(FakeComfy())
    v, a, pic = _file(tmp_path, "ref_video.mp4"), _file(tmp_path, "ref_audio.wav"), _file(tmp_path, "picture_1.png")
    prov = ComfyUIMinimaxVideo(_cfg(minimax_resolution="2K"))
    out = await prov.generate(
        _req(tmp_path, h3_mode="ref2va", duration=13.0, reference_videos=[v], reference_audios=[a], reference_images=[pic], ratio="9:16")
    )
    assert out.read_bytes() == b"MP4"
    assert fake.uploads == ["picture_1.png", "ref_video.mp4", "ref_audio.wav"]
    body = fake.prompts[0]
    assert body["extra_data"] == {"api_key_comfy_org": "comfyui-key"}
    node = _node(body["prompt"], NODE_REF)["inputs"]
    assert node["model.resolution"] == "2K" and node["model.duration"] == 13 and node["model.ratio"] == "9:16"


@pytest.mark.asyncio
async def test_generate_modes_inferred(tmp_path: Path, fake_comfy):
    fake = fake_comfy(FakeComfy())
    prov = ComfyUIMinimaxVideo(_cfg(model="x", comfyui_h3_model="MiniMax H3 Max Turbo", max_clip_seconds=6))
    await prov.generate(_req(tmp_path, duration=12.0))  # no images -> text to video, capped by max_clip_seconds
    t2v = _node(fake.prompts[-1]["prompt"], NODE_T2V)["inputs"]
    assert t2v["model"] == "MiniMax H3 Max Turbo" and t2v["model.duration"] == 6 and t2v["model.resolution"] == "768P"
    first = _file(tmp_path, "first.png")
    ref = _file(tmp_path, "char.png")
    await prov.generate(_req(tmp_path, start_image=first, reference_images=[ref]))  # frame wins over refs
    assert NODE_FLF in {n["class_type"] for n in fake.prompts[-1]["prompt"].values()}
    with pytest.raises(ProviderError, match="首幀"):
        await prov.generate(_req(tmp_path, end_image=first))


@pytest.mark.asyncio
async def test_execution_error_is_translated(tmp_path: Path, fake_comfy):
    fake_comfy(FakeComfy(fail="401 Unauthorized: Please login first to use this node."))
    prov = ComfyUIMinimaxVideo(_cfg(comfy_api_key=""))
    with pytest.raises(ProviderError, match="Comfy 平台 API Key"):
        await prov.generate(_req(tmp_path))
    assert "點數不足" in translate_error("Payment required 402 insufficient credits")


@pytest.mark.asyncio
async def test_connection_test_checks_nodes(fake_comfy):
    fake_comfy(FakeComfy())
    msg = await ComfyUIMinimaxVideo(_cfg()).test()
    assert "三種節點皆可用" in msg
    msg = await ComfyUIMinimaxVideo(_cfg(comfy_api_key="")).test()
    assert "尚未填 Comfy API Key" in msg


def test_registry_and_secret_masking():
    from easyaivideo.config import SECRET_FIELDS, AppConfig
    from easyaivideo.providers.registry import get_video

    cfg = AppConfig()
    cfg.video.provider = "comfyui_minimax"
    assert type(get_video(cfg)).__name__ == "ComfyUIMinimaxVideo"
    assert "comfy_api_key" in SECRET_FIELDS
