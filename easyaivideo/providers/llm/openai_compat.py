"""OpenAI-compatible chat completion provider (OpenAI, DeepSeek, Qwen, Ollama, LM Studio ...)."""

from __future__ import annotations

import json
import re
from typing import Any, Optional

import httpx

from ...config import LLMConfig
from ..base import ProviderError


def extract_json(text: str) -> dict[str, Any]:
    """Parse JSON from an LLM reply: direct, fenced, or first {...} block."""
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fence:
        try:
            return json.loads(fence.group(1))
        except json.JSONDecodeError:
            pass
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            pass
    raise ProviderError(f"LLM did not return valid JSON. Reply started with: {text[:200]!r}")


class OpenAICompatLLM:
    name = "openai_compat"

    def __init__(self, cfg: LLMConfig) -> None:
        self.cfg = cfg
        if not cfg.base_url:
            raise ProviderError("LLM base_url is empty.")
        if not cfg.model:
            raise ProviderError("LLM model is empty.")

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.cfg.api_key:
            headers["Authorization"] = f"Bearer {self.cfg.api_key}"
        return headers

    async def complete(self, prompt: str, *, system: Optional[str] = None) -> str:
        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        body = {"model": self.cfg.model, "messages": messages, "temperature": self.cfg.temperature}
        url = self.cfg.base_url.rstrip("/") + "/chat/completions"
        async with httpx.AsyncClient(timeout=180) as client:
            try:
                resp = await client.post(url, headers=self._headers(), json=body)
            except httpx.HTTPError as exc:
                raise ProviderError(f"LLM request failed: {exc}") from exc
        if resp.status_code >= 400:
            raise ProviderError(f"LLM HTTP {resp.status_code}: {resp.text[:300]}")
        data = resp.json()
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderError(f"Unexpected LLM response: {str(data)[:300]}") from exc
        if isinstance(content, list):  # some providers return content parts
            content = "".join(part.get("text", "") for part in content if isinstance(part, dict))
        return str(content)

    async def complete_json(self, prompt: str, *, system: Optional[str] = None) -> dict[str, Any]:
        last_error: Optional[Exception] = None
        for _ in range(3):
            try:
                reply = await self.complete(prompt, system=system or "You are a helpful assistant that always answers with valid JSON only.")
                return extract_json(reply)
            except ProviderError as exc:
                last_error = exc
        raise ProviderError(f"LLM failed to produce JSON after 3 attempts: {last_error}")

    async def test(self) -> str:
        reply = await self.complete("Reply with the single word OK.")
        return f"Connected to {self.cfg.model}: {reply.strip()[:40]}"
