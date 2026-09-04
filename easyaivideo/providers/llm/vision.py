"""Multimodal (image + text) chat via the OpenAI-compatible messages format."""

from __future__ import annotations

import base64
import mimetypes
from pathlib import Path
from typing import Any, Optional, Protocol

import httpx

from ...config import AppConfig
from ..base import ProviderError
from .openai_compat import extract_json


class VisionProvider(Protocol):
    name: str
    model: str

    async def complete_json_with_images(self, prompt: str, images: list[Path], *, system: Optional[str] = None) -> dict[str, Any]: ...

    async def test(self) -> str: ...


def _data_uri(path: Path) -> str:
    mime = mimetypes.guess_type(path.name)[0] or "image/jpeg"
    return f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode('ascii')}"


class OpenAICompatVision:
    name = "openai_compat"

    def __init__(self, cfg: AppConfig) -> None:
        r = cfg.review
        self.api_key = r.api_key or cfg.llm.api_key
        self.base_url = (r.base_url or cfg.llm.base_url).rstrip("/")
        self.model = r.model or cfg.llm.model
        if not self.base_url or not self.model:
            raise ProviderError("Review model is not configured (set review.model or an LLM in Settings).")

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    async def _chat(self, prompt: str, images: list[Path], system: Optional[str]) -> str:
        content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
        for img in images:
            content.append({"type": "image_url", "image_url": {"url": _data_uri(img), "detail": "low"}})
        messages: list[dict[str, Any]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": content})
        body = {"model": self.model, "messages": messages, "temperature": 0.2}
        async with httpx.AsyncClient(timeout=180) as client:
            try:
                resp = await client.post(f"{self.base_url}/chat/completions", headers=self._headers(), json=body)
            except httpx.HTTPError as exc:
                raise ProviderError(f"Review request failed: {exc}") from exc
        if resp.status_code >= 400:
            raise ProviderError(f"Review model HTTP {resp.status_code}: {resp.text[:300]}")
        data = resp.json()
        try:
            reply = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderError(f"Unexpected review response: {str(data)[:300]}") from exc
        if isinstance(reply, list):
            reply = "".join(part.get("text", "") for part in reply if isinstance(part, dict))
        return str(reply)

    async def complete_json_with_images(self, prompt: str, images: list[Path], *, system: Optional[str] = None) -> dict[str, Any]:
        last: Optional[Exception] = None
        for _ in range(2):
            try:
                reply = await self._chat(prompt, images, system or "You are a meticulous video quality reviewer. Answer with valid JSON only.")
                return extract_json(reply)
            except ProviderError as exc:
                last = exc
                if "HTTP 4" in str(exc):  # unsupported model / bad request: do not retry
                    break
        raise ProviderError(f"Review model failed: {last}")

    async def test(self) -> str:
        import tempfile

        from PIL import Image, ImageDraw

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "probe.png"
            img = Image.new("RGB", (256, 256), (30, 120, 200))
            ImageDraw.Draw(img).ellipse([64, 64, 192, 192], fill=(250, 200, 40))
            img.save(path)
            data = await self.complete_json_with_images(
                'Look at the image. Reply ONLY with JSON: {"shape": "<the shape you see>", "color": "<its color>"}', [path]
            )
        return f"Vision OK with {self.model}: {data}"


class MockVision:
    name = "mock"
    model = "mock-vision"

    async def complete_json_with_images(self, prompt: str, images: list[Path], *, system: Optional[str] = None) -> dict[str, Any]:
        if '"shape"' in prompt:
            return {"shape": "circle", "color": "yellow"}
        if "SCENE REVIEWS" in prompt:
            return {"summary": "示範摘要（mock）：整體畫面與旁白大致相符，請設定多模態模型以取得真正的審片結果。"}
        idx = 1
        for line in prompt.splitlines():
            if line.startswith("SCENE INDEX:"):
                idx = int(line.split(":", 1)[1].strip() or 1)
        bad = idx % 3 == 0
        return {
            "score": 2 if bad else 4,
            "match": not bad,
            "issues": ["畫面主體與旁白提到的物件不一致（mock 示範）", "畫面中出現無法辨識的文字"] if bad else [],
            "suggested_image_prompt": "revised prompt (mock): same scene, remove any text, show the subject mentioned in the narration clearly" if bad else "",
            "note": "mock 審片結果" if bad else "畫面與旁白相符（mock）",
        }

    async def test(self) -> str:
        return "Mock vision active (LLM provider is mock)."
