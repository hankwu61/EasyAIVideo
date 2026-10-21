"""MiniMax H3 through ComfyUI Partner Nodes (text-to-video / first-last-frame / reference-to-video).

The API-format workflow is built in code because the reference node takes a variable number of
image / video / audio inputs. Node and input names follow ComfyUI ``comfy_api_nodes/nodes_minimax.py``:

- MinimaxHailuo03TextToVideoNode        model, model.prompt, model.resolution, model.ratio, model.duration, seed
- MinimaxHailuo03FirstLastFrameNode     ... + first_frame (+ last_frame); no ratio (follows the image)
- MinimaxHailuo03ReferenceNode          ... + model.reference_images.image_N / reference_videos.video_N /
                                        reference_audios.audio_N (dynamic inputs are flattened with dots)

Partner Nodes run on MiniMax's servers and are billed to the Comfy account; a headless /prompt call must
carry the Comfy platform API key as ``extra_data.api_key_comfy_org``.
"""

from __future__ import annotations

import random
from pathlib import Path
from typing import Any, Optional

import httpx

from ...config import VideoConfig
from ..base import ProviderError, VideoRequest
from ..comfyui import ComfyUIClient
from .minimax import infer_mode

H3 = "MiniMax H3"
H3_MAX = "MiniMax H3 Max"
H3_MAX_TURBO = "MiniMax H3 Max Turbo"
MODELS = (H3, H3_MAX, H3_MAX_TURBO)
NODE_T2V = "MinimaxHailuo03TextToVideoNode"
NODE_FLF = "MinimaxHailuo03FirstLastFrameNode"
NODE_REF = "MinimaxHailuo03ReferenceNode"
RATIOS = ("16:9", "4:3", "1:1", "3:4", "9:16", "21:9")
PROMPT_LIMIT = {H3: 7000, H3_MAX: 50000, H3_MAX_TURBO: 50000}

_ERROR_HINTS = (
    (("unauthorized", "401", "api key", "api_key", "login", "sign in", "authentication"),
     "ComfyUI Partner Node 驗證失敗：請在 設定 → 影片 填入 Comfy 平台 API Key（platform.comfy.org）並確認帳戶有點數。"),
    (("402", "insufficient", "credit", "balance"), "Comfy 帳戶點數不足，請到 platform.comfy.org 儲值。"),
    (("does not exist",), "ComfyUI 找不到 MiniMax H3 節點，請更新 ComfyUI 到最新版（H3 Max 需 ≥ 0.34.3）。"),
)


def normalise_model(name: str) -> str:
    n = (name or "").strip().lower().replace("-", " ")
    for m in MODELS:
        if n == m.lower():
            return m
    if "turbo" in n:
        return H3_MAX_TURBO
    if "max" in n:
        return H3_MAX
    return H3


def resolutions(model: str) -> tuple[str, ...]:
    return ("768P", "2K") if model == H3 else ("480P", "768P")


def pick_resolution(model: str, wanted: str) -> str:
    wanted = (wanted or "768P").upper()
    return wanted if wanted in resolutions(model) else "768P"


def clamp_duration(model: str, seconds: float) -> int:
    lo = 4 if model == H3 else 5
    return int(max(lo, min(15, round(seconds))))


def pick_ratio(req: VideoRequest) -> str:
    if req.ratio in RATIOS:
        return str(req.ratio)
    if req.height > req.width:
        return "9:16"
    if req.width > req.height:
        return "16:9"
    return "1:1"


def translate_error(message: str) -> str:
    low = (message or "").lower()
    for keys, hint in _ERROR_HINTS:
        if any(k in low for k in keys):
            return f"{hint}（{(message or '')[:200]}）"
    return message


def build_workflow(
    *,
    mode: str,
    model: str,
    prompt: str,
    resolution: str,
    ratio: str,
    duration: int,
    seed: int,
    first_frame: Optional[str] = None,
    last_frame: Optional[str] = None,
    images: Optional[list[str]] = None,
    videos: Optional[list[str]] = None,
    audios: Optional[list[str]] = None,
    reference_detail: str = "standard",
    filename_prefix: str = "easyaivideo/minimax_h3",
) -> dict[str, Any]:
    """API-format workflow for one H3 generation. ``images`` etc. are names already uploaded to ComfyUI."""
    images, videos, audios = list(images or []), list(videos or []), list(audios or [])
    wf: dict[str, Any] = {}
    counter = [0]

    def add(class_type: str, inputs: dict[str, Any], title: str) -> str:
        counter[0] += 1
        nid = str(counter[0])
        wf[nid] = {"class_type": class_type, "inputs": inputs, "_meta": {"title": title}}
        return nid

    common: dict[str, Any] = {
        "model": model,
        "model.prompt": prompt,
        "model.resolution": resolution,
        "model.duration": duration,
        "seed": seed,
        "watermark": False,
    }
    if model != H3:
        common["model.prompt_expansion_mode"] = "balanced"

    if mode == "t2va":
        h3 = add(NODE_T2V, {**common, "model.ratio": ratio}, "MiniMax H3 Text to Video")
    elif mode in ("i2va", "fl2va"):
        if not first_frame:
            raise ProviderError("ComfyUI MiniMax H3 圖生影片需要首幀圖片。")
        inputs = dict(common)
        inputs["first_frame"] = [add("LoadImage", {"image": first_frame}, "First frame"), 0]
        if mode == "fl2va" and last_frame:
            inputs["last_frame"] = [add("LoadImage", {"image": last_frame}, "Last frame"), 0]
        h3 = add(NODE_FLF, inputs, "MiniMax H3 First-Last-Frame to Video")
    elif mode == "ref2va":
        if model == H3_MAX_TURBO:
            raise ProviderError("MiniMax H3 Max Turbo 不支援參考生影片，請改用 MiniMax H3 或 H3 Max。")
        if not images and not videos:
            raise ProviderError("參考生影片至少需要一張參考圖片或一段參考影片。")
        inputs = {**common, "model.ratio": ratio}
        if model == H3_MAX:
            inputs["model.reference_detail"] = reference_detail
        for i, name in enumerate(images[:9], start=1):
            inputs[f"model.reference_images.image_{i}"] = [add("LoadImage", {"image": name}, f"Reference image {i}"), 0]
        for i, name in enumerate(videos[:3], start=1):
            inputs[f"model.reference_videos.video_{i}"] = [add("LoadVideo", {"file": name}, f"Reference video {i}"), 0]
        for i, name in enumerate(audios[:3], start=1):
            inputs[f"model.reference_audios.audio_{i}"] = [add("LoadAudio", {"audio": name}, f"Reference audio {i}"), 0]
        h3 = add(NODE_REF, inputs, "MiniMax H3 Reference to Video")
    else:
        raise ProviderError(f"ComfyUI MiniMax H3 不支援模式 {mode}（只有尾幀時請同時提供首幀）。")

    add("SaveVideo", {"video": [h3, 0], "filename_prefix": filename_prefix, "format": "auto", "codec": "auto"}, "Save video")
    return wf


class ComfyUIMinimaxVideo:
    name = "comfyui_minimax"

    def __init__(self, cfg: VideoConfig) -> None:
        self.cfg = cfg
        self.client = ComfyUIClient(cfg.comfyui_url)
        self.model = normalise_model(getattr(cfg, "comfyui_h3_model", H3))
        self.resolution = pick_resolution(self.model, getattr(cfg, "minimax_resolution", "768P"))
        self.api_key = (getattr(cfg, "comfy_api_key", "") or "").strip()

    def _seconds(self, req: VideoRequest) -> float:
        if req.h3_mode:  # H3 clone parts are pre-planned
            return req.duration
        return min(req.duration, float(self.cfg.max_clip_seconds or 15))

    async def build(self, req: VideoRequest) -> dict[str, Any]:
        prompt = req.prompt.strip()
        if not prompt:
            raise ProviderError("MiniMax H3 prompt is empty.")
        if len(prompt) > PROMPT_LIMIT[self.model]:
            raise ProviderError(f"MiniMax H3 prompt is {len(prompt)} characters (limit {PROMPT_LIMIT[self.model]}).")
        mode = infer_mode(req)
        if mode == "l2va":
            raise ProviderError("ComfyUI 的 MiniMax H3 節點必須有首幀；只有尾幀時請改用 MiniMax 直連或補上首幀。")

        async def up(paths: list[Path], limit: int) -> list[str]:
            return [await self.client.upload_file(p) for p in paths if p and p.is_file()][:limit]

        first = await self.client.upload_file(req.start_image) if req.start_image and mode in ("i2va", "fl2va") else None
        last = await self.client.upload_file(req.end_image) if req.end_image and mode == "fl2va" else None
        images = await up(req.reference_images, 9) if mode == "ref2va" else []
        videos = await up(req.reference_videos, 3) if mode == "ref2va" else []
        audios = await up(req.reference_audios, 3) if mode == "ref2va" and (images or videos) else []
        return build_workflow(
            mode=mode,
            model=self.model,
            prompt=prompt,
            resolution=self.resolution,
            ratio=pick_ratio(req),
            duration=clamp_duration(self.model, self._seconds(req)),
            seed=req.seed if req.seed is not None else random.randint(0, 2**32 - 1),
            first_frame=first,
            last_frame=last,
            images=images,
            videos=videos,
            audios=audios,
        )

    async def generate(self, req: VideoRequest) -> Path:
        workflow = await self.build(req)
        extra = {"api_key_comfy_org": self.api_key} if self.api_key else None
        try:
            outputs = await self.client.run(workflow, timeout=self.cfg.poll_timeout, extra_data=extra)
        except ProviderError as exc:
            raise ProviderError(translate_error(str(exc))) from exc
        item = ComfyUIClient.first_output(outputs, ("videos", "images", "gifs"))
        return await self.client.download(item, req.output_path)

    async def test(self) -> str:
        try:
            await self.client.stats()
        except Exception as exc:  # noqa: BLE001
            raise ProviderError(f"無法連線 ComfyUI（{self.cfg.comfyui_url}）：{exc}") from exc
        missing: list[str] = []
        async with httpx.AsyncClient(timeout=15) as client:
            for node in (NODE_T2V, NODE_FLF, NODE_REF):
                try:
                    resp = await client.get(f"{self.client.base_url}/object_info/{node}")
                    if resp.status_code != 200 or node not in (resp.json() or {}):
                        missing.append(node)
                except (httpx.HTTPError, ValueError):
                    missing.append(node)
        if missing:
            raise ProviderError(f"ComfyUI 缺少 MiniMax H3 節點 {missing}，請更新 ComfyUI 到最新版（H3 Max 需 ≥ 0.34.3）。")
        if not self.api_key:
            return f"ComfyUI 在線且有 MiniMax H3 節點；但尚未填 Comfy API Key，Partner Node 執行時會驗證失敗。（模型 {self.model}，{self.resolution}）"
        return f"ComfyUI 在線，MiniMax H3 三種節點皆可用（模型 {self.model}，{self.resolution}，費用由 Comfy 帳戶點數扣除）。"
