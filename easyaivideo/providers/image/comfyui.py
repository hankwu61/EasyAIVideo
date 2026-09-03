"""ComfyUI text-to-image provider driven by a workflow template."""

from __future__ import annotations

import random
from pathlib import Path
from typing import Optional

from ...config import ImageConfig
from ..base import ProviderError
from ..comfyui import ComfyUIClient, load_workflow, render_workflow


class ComfyUIImage:
    name = "comfyui"

    def __init__(self, cfg: ImageConfig) -> None:
        self.cfg = cfg
        self.client = ComfyUIClient(cfg.comfyui_url)

    async def generate(
        self,
        prompt: str,
        negative_prompt: str,
        width: int,
        height: int,
        output_path: Path,
        seed: Optional[int] = None,
        reference_images: Optional[list[Path]] = None,
    ) -> Path:
        template = load_workflow(self.cfg.comfyui_workflow)
        workflow = render_workflow(
            template,
            {
                "prompt": prompt,
                "negative_prompt": negative_prompt,
                "width": width,
                "height": height,
                "seed": seed if seed is not None else random.randint(1, 2**31),
            },
        )
        outputs = await self.client.run(workflow)
        item = ComfyUIClient.first_output(outputs, ("images",))
        return await self.client.download(item, output_path)

    async def test(self) -> str:
        try:
            stats = await self.client.stats()
        except Exception as exc:  # noqa: BLE001
            raise ProviderError(f"Cannot reach ComfyUI at {self.cfg.comfyui_url}: {exc}") from exc
        load_workflow(self.cfg.comfyui_workflow)
        devices = stats.get("devices", [])
        gpu = devices[0].get("name", "?") if devices else "unknown device"
        return f"ComfyUI online ({gpu}); workflow {self.cfg.comfyui_workflow} found."
