"""ComfyUI image-to-video provider driven by a workflow template."""

from __future__ import annotations

import math
import random
from pathlib import Path

from ...config import VideoConfig
from ..base import ProviderError, VideoRequest
from ..comfyui import ComfyUIClient, load_workflow, render_workflow


class ComfyUIVideo:
    name = "comfyui"

    def __init__(self, cfg: VideoConfig) -> None:
        self.cfg = cfg
        self.client = ComfyUIClient(cfg.comfyui_url)

    async def generate(self, req: VideoRequest) -> Path:
        if req.start_image is None:
            raise ProviderError("The ComfyUI video workflow needs a scene image (image-to-video).")
        uploaded = await self.client.upload_image(req.start_image)
        template = load_workflow(self.cfg.comfyui_workflow)
        clip_seconds = min(max(req.duration, 2.0), float(self.cfg.max_clip_seconds))
        workflow = render_workflow(
            template,
            {
                "image": uploaded,
                "prompt": req.prompt,
                "width": req.width,
                "height": req.height,
                "fps": req.fps,
                "frames": int(math.ceil(clip_seconds * req.fps)),
                "duration": round(clip_seconds, 2),
                "seed": req.seed if req.seed is not None else random.randint(1, 2**31),
            },
        )
        outputs = await self.client.run(workflow, timeout=self.cfg.poll_timeout)
        item = ComfyUIClient.first_output(outputs, ("videos", "gifs", "images"))
        return await self.client.download(item, req.output_path)

    async def test(self) -> str:
        try:
            await self.client.stats()
        except Exception as exc:  # noqa: BLE001
            raise ProviderError(f"Cannot reach ComfyUI at {self.cfg.comfyui_url}: {exc}") from exc
        load_workflow(self.cfg.comfyui_workflow)
        return f"ComfyUI online; video workflow {self.cfg.comfyui_workflow} found."
