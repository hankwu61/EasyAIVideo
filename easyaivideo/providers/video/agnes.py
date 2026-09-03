"""Agnes AI video provider: async POST /v1/videos + polling.

Supports text-to-video (no image), image-to-video (top-level `image`, bare base64) and
first+last frame (`extra_body.image=[start, end]`, `mode="keyframes"`), plus reference images
(`extra_body.image=[refs]`). fps is fixed at 24, num_frames must be 8n+1 (max 441 ≈ 18 s).
"""

from __future__ import annotations

import asyncio
import base64
import logging
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlsplit

import httpx

from ...config import VideoConfig
from ...services.sizes import VIDEO_TIER_SHORT_EDGE, aspect_size
from ..base import ProviderError, VideoRequest

log = logging.getLogger("easyaivideo.agnes")

FPS = 24
FRAME_STEP = 8
MAX_FRAMES = 441
MIN_SECONDS, MAX_SECONDS = 1, 18
MAX_REFERENCES = 4
FAILED = ("failed", "error", "cancelled", "canceled")
URL_FIELDS = ("url", "video_url")


def host_and_base(configured: str) -> tuple[str, str]:
    base = (configured or "").strip().rstrip("/") or "https://apihub.agnes-ai.com/v1"
    host = base[:-3] if base.endswith("/v1") else base
    return host, host + "/v1"


def duration_to_frames(seconds: float) -> int:
    target = max(1, round(seconds)) * FPS
    n = round((target - 1) / FRAME_STEP)
    return max(1, min(FRAME_STEP * n + 1, MAX_FRAMES))


def _looks_like_url(value: Any) -> bool:
    if not isinstance(value, str) or not value:
        return False
    parts = urlsplit(value)
    return parts.scheme in ("http", "https") and bool(parts.netloc)


def first_url(body: dict[str, Any]) -> Optional[str]:
    meta = body.get("metadata") if isinstance(body.get("metadata"), dict) else {}
    for key in URL_FIELDS:
        for source in (body, meta):
            if _looks_like_url(source.get(key)):
                return source[key]
    for source in (body, meta):
        if _looks_like_url(source.get("remixed_from_video_id")):
            return source["remixed_from_video_id"]
    return None


def _b64(path: Path) -> str:
    if not path.is_file():
        raise ProviderError(f"Image for video generation not found: {path.name}")
    return base64.b64encode(path.read_bytes()).decode("ascii")


class AgnesVideo:
    name = "agnes"

    def __init__(self, cfg: VideoConfig) -> None:
        self.cfg = cfg
        if not cfg.api_key.strip():
            raise ProviderError("Agnes video api_key is empty. Fill it in Settings → Video.")
        self.host, self.base = host_and_base(cfg.base_url)
        self.model = cfg.model.strip() or "agnes-video-v2.0"

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.cfg.api_key.strip()}", "Content-Type": "application/json"}

    def build_payload(self, req: VideoRequest) -> dict[str, Any]:
        short = VIDEO_TIER_SHORT_EDGE.get(self.cfg.resolution, 720)
        width, height = aspect_size(req.width, req.height, short, round_to=8, max_long_edge=1920)
        seconds = min(max(req.duration, MIN_SECONDS), min(MAX_SECONDS, self.cfg.max_clip_seconds))
        payload: dict[str, Any] = {
            "model": self.model,
            "prompt": req.prompt,
            "height": height,
            "width": width,
            "num_frames": duration_to_frames(seconds),
            "frame_rate": FPS,
        }
        if req.seed is not None:
            payload["seed"] = req.seed
        if req.start_image and req.end_image:
            payload["extra_body"] = {"image": [_b64(req.start_image), _b64(req.end_image)], "mode": "keyframes"}
        elif req.start_image:
            payload["image"] = _b64(req.start_image)
        elif req.reference_images:
            payload["extra_body"] = {"image": [_b64(p) for p in req.reference_images[:MAX_REFERENCES]]}
        return payload

    async def generate(self, req: VideoRequest) -> Path:
        payload = await asyncio.to_thread(self.build_payload, req)
        async with httpx.AsyncClient(timeout=60) as client:
            task_id = await self._submit(client, payload)
            log.info("Agnes video task %s submitted (%sx%s, %s frames)", task_id, payload["width"], payload["height"], payload["num_frames"])
            final = await self._poll(client, task_id)
            url = first_url(final)
            if url is None:
                video_id = final.get("video_id")
                if isinstance(video_id, str) and video_id:
                    resp = await client.get(f"{self.host}/agnesapi", params={"video_id": video_id}, headers=self._headers())
                    if resp.status_code >= 400:
                        raise ProviderError(f"Agnes video query failed: HTTP {resp.status_code} {resp.text[:200]}")
                    url = first_url(resp.json())
            if url is None:
                raise ProviderError(f"Agnes task completed but returned no video URL (fields: {sorted(final)})")
            await self._download(client, url, req.output_path)
        return req.output_path

    async def _submit(self, client: httpx.AsyncClient, payload: dict[str, Any]) -> str:
        last = ""
        for attempt in range(4):
            try:
                resp = await client.post(f"{self.base}/videos", json=payload, headers=self._headers(), timeout=300)
            except httpx.HTTPError as exc:
                raise ProviderError(f"Agnes video submit failed: {exc}") from exc
            if resp.status_code < 400:
                body = resp.json()
                for key in ("task_id", "id"):
                    if isinstance(body.get(key), str) and body[key]:
                        return body[key]
                raise ProviderError(f"Agnes video submit returned no task_id (fields: {sorted(body)})")
            last = f"HTTP {resp.status_code}: {resp.text[:300]}"
            if resp.status_code in (408, 429) or resp.status_code >= 500:
                await asyncio.sleep(5 * (attempt + 1))
                continue
            break
        raise ProviderError(f"Agnes video submit rejected: {last}")

    async def _poll(self, client: httpx.AsyncClient, task_id: str) -> dict[str, Any]:
        waited = 0.0
        interval = 5.0
        errors = 0
        while waited < self.cfg.poll_timeout:
            await asyncio.sleep(interval)
            waited += interval
            try:
                resp = await client.get(f"{self.base}/videos/{task_id}", headers=self._headers())
            except httpx.HTTPError:
                errors += 1
                if errors > 5:
                    raise ProviderError("Agnes video polling failed repeatedly.")
                continue
            if resp.status_code >= 500 or resp.status_code in (404, 408, 429):
                errors += 1
                if errors > 8:
                    raise ProviderError(f"Agnes video polling failed: HTTP {resp.status_code}")
                continue
            if resp.status_code >= 400:
                raise ProviderError(f"Agnes video polling error: HTTP {resp.status_code} {resp.text[:200]}")
            errors = 0
            state = resp.json()
            status = str(state.get("status", "")).lower()
            if status == "completed":
                return state
            if status in FAILED:
                err = state.get("error")
                msg = (err.get("message") or err.get("code") or "unknown") if isinstance(err, dict) else (err or "unknown")
                raise ProviderError(f"Agnes video generation failed: {msg}")
        raise ProviderError("Agnes video generation timed out.")

    async def _download(self, client: httpx.AsyncClient, url: str, output: Path) -> None:
        output.parent.mkdir(parents=True, exist_ok=True)
        last: Optional[Exception] = None
        for attempt in range(3):
            try:
                async with client.stream("GET", url, timeout=600) as resp:
                    if resp.status_code >= 400:
                        raise ProviderError(f"Video download failed: HTTP {resp.status_code}")
                    with output.open("wb") as fh:
                        async for chunk in resp.aiter_bytes():
                            fh.write(chunk)
                if output.stat().st_size > 0:
                    return
            except (httpx.HTTPError, ProviderError, OSError) as exc:
                last = exc
                await asyncio.sleep(3 * (attempt + 1))
        raise ProviderError(f"Video download failed: {last}")

    async def test(self) -> str:
        async with httpx.AsyncClient(timeout=20) as client:
            try:
                resp = await client.get(f"{self.base}/models", headers=self._headers())
            except httpx.HTTPError as exc:
                raise ProviderError(f"Cannot reach {self.base}: {exc}") from exc
        if resp.status_code in (401, 403):
            raise ProviderError(f"Agnes rejected the API key (HTTP {resp.status_code}).")
        if resp.status_code >= 400 and resp.status_code != 404:
            raise ProviderError(f"HTTP {resp.status_code}: {resp.text[:200]}")
        return f"Agnes endpoint reachable; video model '{self.model}' ({self.cfg.resolution}, mode {self.cfg.mode}) will be used."
