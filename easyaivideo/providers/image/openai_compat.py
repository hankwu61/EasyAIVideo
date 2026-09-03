"""OpenAI-style /images/generations provider (dall-e-3, gpt-image-1, Agnes image models, proxies)."""

from __future__ import annotations

import asyncio
import base64
import mimetypes
from pathlib import Path
from typing import Any, Optional

import httpx

from ...config import ImageConfig
from ...services.sizes import aspect_size
from ..base import ProviderError


def pick_size(cfg: ImageConfig, width: int, height: int) -> str:
    if cfg.size_mode == "exact":
        w, h = aspect_size(width, height, cfg.short_edge, round_to=8, max_long_edge=2048)
        return f"{w}x{h}"
    if width == height:
        return cfg.size_square
    return cfg.size_portrait if height > width else cfg.size_landscape


def _data_uri(path: Path) -> str:
    mime = mimetypes.guess_type(path.name)[0] or "image/png"
    return f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode('ascii')}"


class OpenAICompatImage:
    name = "openai_compat"

    def __init__(self, cfg: ImageConfig) -> None:
        self.cfg = cfg
        if not cfg.base_url:
            raise ProviderError("Image base_url is empty.")

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.cfg.api_key:
            headers["Authorization"] = f"Bearer {self.cfg.api_key}"
        return headers

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
        body: dict[str, Any] = {"model": self.cfg.model, "prompt": prompt, "n": 1, "size": pick_size(self.cfg, width, height)}
        if self.cfg.model.startswith("dall-e"):
            body["response_format"] = "b64_json"
        refs = [p for p in (reference_images or []) if p.is_file()]
        if refs and self.cfg.use_references:
            body["image"] = await asyncio.to_thread(lambda: [_data_uri(p) for p in refs[:4]])
        url = self.cfg.base_url.rstrip("/") + "/images/generations"
        async with httpx.AsyncClient(timeout=300) as client:
            try:
                resp = await client.post(url, headers=self._headers(), json=body)
            except httpx.HTTPError as exc:
                raise ProviderError(f"Image request failed: {exc}") from exc
            if resp.status_code >= 400:
                raise ProviderError(f"Image HTTP {resp.status_code}: {resp.text[:300]}")
            data = resp.json()
            try:
                item = data["data"][0]
            except (KeyError, IndexError, TypeError) as exc:
                raise ProviderError(f"Unexpected image response: {str(data)[:300]}") from exc
            output_path.parent.mkdir(parents=True, exist_ok=True)
            if item.get("url"):
                dl = await client.get(item["url"])
                if dl.status_code >= 400:
                    raise ProviderError(f"Image download failed: HTTP {dl.status_code}")
                output_path.write_bytes(dl.content)
            elif item.get("b64_json"):
                output_path.write_bytes(base64.b64decode(item["b64_json"]))
            else:
                raise ProviderError("Image response contained neither b64_json nor url.")
        return output_path

    async def test(self) -> str:
        url = self.cfg.base_url.rstrip("/") + "/models"
        async with httpx.AsyncClient(timeout=20) as client:
            try:
                resp = await client.get(url, headers=self._headers())
            except httpx.HTTPError as exc:
                raise ProviderError(f"Cannot reach {url}: {exc}") from exc
        if resp.status_code >= 400:
            raise ProviderError(f"HTTP {resp.status_code}: {resp.text[:200]}")
        return f"Endpoint reachable; model '{self.cfg.model}' will be used (size mode: {self.cfg.size_mode})."
