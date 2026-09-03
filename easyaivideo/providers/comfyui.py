"""Minimal ComfyUI HTTP client: run an API-format workflow with {{placeholders}} and fetch outputs."""

from __future__ import annotations

import asyncio
import json
import re
import uuid
from pathlib import Path
from typing import Any

import httpx

from ..config import WORKFLOWS_DIR
from .base import ProviderError


def render_workflow(template_text: str, params: dict[str, Any]) -> dict[str, Any]:
    """Substitute {{name}} placeholders. Quoted placeholders receive JSON-typed values."""
    text = template_text
    for key, value in params.items():
        quoted = f'"{{{{{key}}}}}"'
        text = text.replace(quoted, json.dumps(value, ensure_ascii=False))
        escaped = json.dumps(str(value), ensure_ascii=False)[1:-1]
        text = text.replace(f"{{{{{key}}}}}", escaped)
    leftover = re.findall(r"\{\{(\w+)\}\}", text)
    if leftover:
        raise ProviderError(f"Workflow has unfilled placeholders: {sorted(set(leftover))}")
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise ProviderError(f"Workflow JSON is invalid after substitution: {exc}") from exc


def load_workflow(name: str) -> str:
    path = WORKFLOWS_DIR / name
    if not path.exists():
        raise ProviderError(f"ComfyUI workflow not found: {path}")
    return path.read_text(encoding="utf-8")


class ComfyUIClient:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.client_id = uuid.uuid4().hex

    async def stats(self) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{self.base_url}/system_stats")
            resp.raise_for_status()
            return resp.json()

    async def upload_image(self, path: Path) -> str:
        async with httpx.AsyncClient(timeout=60) as client:
            with path.open("rb") as fh:
                resp = await client.post(
                    f"{self.base_url}/upload/image",
                    files={"image": (path.name, fh, "image/png")},
                    data={"overwrite": "true"},
                )
        if resp.status_code >= 400:
            raise ProviderError(f"ComfyUI upload failed: HTTP {resp.status_code} {resp.text[:200]}")
        data = resp.json()
        name = data.get("name", path.name)
        sub = data.get("subfolder", "")
        return f"{sub}/{name}" if sub else name

    async def run(self, workflow: dict[str, Any], timeout: float = 1800) -> dict[str, Any]:
        """Queue a prompt and wait for its history entry. Returns the outputs dict."""
        async with httpx.AsyncClient(timeout=30) as client:
            try:
                resp = await client.post(f"{self.base_url}/prompt", json={"prompt": workflow, "client_id": self.client_id})
            except httpx.HTTPError as exc:
                raise ProviderError(f"Cannot reach ComfyUI at {self.base_url}: {exc}") from exc
            if resp.status_code >= 400:
                raise ProviderError(f"ComfyUI rejected the workflow: {resp.text[:500]}")
            prompt_id = resp.json().get("prompt_id")
            if not prompt_id:
                raise ProviderError(f"ComfyUI returned no prompt_id: {resp.text[:200]}")

            waited = 0.0
            while waited < timeout:
                await asyncio.sleep(1.5)
                waited += 1.5
                hist = await client.get(f"{self.base_url}/history/{prompt_id}")
                if hist.status_code != 200:
                    continue
                entry = hist.json().get(prompt_id)
                if not entry:
                    continue
                status = entry.get("status", {})
                if status.get("status_str") == "error":
                    messages = status.get("messages", [])
                    raise ProviderError(f"ComfyUI execution error: {json.dumps(messages)[:500]}")
                outputs = entry.get("outputs", {})
                if outputs:
                    return outputs
        raise ProviderError("ComfyUI execution timed out.")

    async def download(self, item: dict[str, Any], output_path: Path) -> Path:
        params = {"filename": item["filename"], "subfolder": item.get("subfolder", ""), "type": item.get("type", "output")}
        async with httpx.AsyncClient(timeout=300) as client:
            resp = await client.get(f"{self.base_url}/view", params=params)
        if resp.status_code >= 400:
            raise ProviderError(f"ComfyUI download failed: HTTP {resp.status_code}")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(resp.content)
        return output_path

    @staticmethod
    def first_output(outputs: dict[str, Any], keys: tuple[str, ...]) -> dict[str, Any]:
        for node_output in outputs.values():
            for key in keys:
                items = node_output.get(key)
                if items:
                    return items[0]
        raise ProviderError(f"ComfyUI produced no output of type {keys}. Outputs: {json.dumps(outputs)[:300]}")
