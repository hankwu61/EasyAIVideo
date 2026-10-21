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

    async def complete_json_with_images(
        self, prompt: str, images: list[Path], *, system: Optional[str] = None, detail: str = "low"
    ) -> dict[str, Any]: ...

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

    async def _chat(self, prompt: str, images: list[Path], system: Optional[str], detail: str = "low") -> str:
        content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
        for img in images:
            content.append({"type": "image_url", "image_url": {"url": _data_uri(img), "detail": detail}})
        messages: list[dict[str, Any]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": content})
        body = {"model": self.model, "messages": messages, "temperature": 0.2}
        async with httpx.AsyncClient(timeout=300) as client:
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

    async def complete_json_with_images(
        self, prompt: str, images: list[Path], *, system: Optional[str] = None, detail: str = "low"
    ) -> dict[str, Any]:
        last: Optional[Exception] = None
        for _ in range(2):
            try:
                reply = await self._chat(
                    prompt, images, system or "You are a meticulous video quality reviewer. Answer with valid JSON only.", detail
                )
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

    async def complete_json_with_images(
        self, prompt: str, images: list[Path], *, system: Optional[str] = None, detail: str = "low"
    ) -> dict[str, Any]:
        if "TASK: VIDEO_TO_H3_OVERVIEW" in prompt:
            return {
                "title": "短影片復刻（mock）",
                "theme": "mock 分析：請設定多模態模型以取得真正的取證結果",
                "film_type": "C_montage",
                "style_line": "The target video uses warm photoreal lifestyle cinematography, soft window light, shallow depth of field, smooth slow camera moves.",
                "subjects_block": "<Subject 1> is a young woman in an oversized cream knit sweater.",
                "post_text_overlays": [],
                "character_replacement_table": "",
                "forensic_report": "## 片型與分流結論\nmock 示範報告。",
            }
        if "TASK: VIDEO_TO_H3_SEGMENT_PROMPT" in prompt:
            return {
                "h3_prompt": (
                    "subject_definitions:\n<Subject 1> is a young woman in an oversized cream knit sweater.\n"
                    "<Video 1> is the source video segment that defines this segment's shot structure, motion path, and pacing.\n\n"
                    "summary:\n[Ref2VA remake + video reference] Recreate <Video 1> (mock).\n\n"
                    "retention_analysis:\n<Video 1> (governs the whole segment): reference - timing and camera paths.\n\n"
                    "detailed_description:\nThe target video uses warm photoreal lifestyle cinematography.\n"
                    "[Shot 1] A medium shot of <Subject 1> smiling in a bright living room; the camera pushes in with small amplitude at slow speed.\n\n"
                    "overall_soundscape:\nQuiet room tone.\n\nnon_diegetic_music:\nN/A - explicit silence."
                ),
                "hand_off_state": "<Subject 1> smiling at the camera in a medium shot.",
                "shots": [{"start": 0.0, "end": 1.0, "transition_in": "none", "summary": "mock 鏡頭"}],
                "warnings": ["mock 模型產生的示範提示詞"],
            }
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
