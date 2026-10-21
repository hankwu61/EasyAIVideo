"""Agnes AI video provider: async POST /v1/videos + polling.

Supports text-to-video (no image), image-to-video (top-level `image`, bare base64) and
first+last frame (`extra_body.image=[start, end]`, `mode="keyframes"`), plus reference images
(`extra_body.image=[refs]`). fps is fixed at 24, num_frames must be 8n+1 (max 441 ≈ 18 s).
"""

from __future__ import annotations

import asyncio
import base64
import logging
import math
from pathlib import Path
import re
from typing import Any, Optional
from urllib.parse import urlsplit

import httpx

from ...config import VideoConfig
from ...services.sizes import VIDEO_TIER_SHORT_EDGE, aspect_size
from ...services.media_source import public_source
from ..base import ProviderError, VideoRequest

log = logging.getLogger("easyaivideo.agnes")

FPS = 24
FRAME_STEP = 8
MAX_FRAMES = 441
MAX_FRAMES_1080P = 241
MIN_SECONDS, MAX_SECONDS = 1, 18
MAX_REFERENCES = 4
FAILED = ("failed", "error", "cancelled", "canceled")
URL_FIELDS = ("url", "video_url")


def host_and_base(configured: str) -> tuple[str, str]:
    base = (configured or "").strip().rstrip("/") or "https://apihub.agnes-ai.com/v1"
    host = base[:-3] if base.endswith("/v1") else base
    return host, host + "/v1"


def duration_to_frames(seconds: float, max_frames: int = MAX_FRAMES) -> int:
    target = max(1, round(seconds)) * FPS
    n = round((target - 1) / FRAME_STEP)
    return max(1, min(FRAME_STEP * n + 1, max_frames))


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
        self.model = {"agnes-video-v2.5": "agnes-video-2.5", "agnes-video-v2.5-flash": "agnes-video-2.5-flash"}.get(self.model, self.model)
        self.is_v25 = self.model in ("agnes-video-2.5", "agnes-video-2.5-flash")

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.cfg.api_key.strip()}", "Content-Type": "application/json"}

    def build_payload(self, req: VideoRequest) -> dict[str, Any]:
        if self.is_v25:
            return self._build_v25_payload(req)
        short = VIDEO_TIER_SHORT_EDGE.get(self.cfg.resolution, 720)
        width, height = aspect_size(req.width, req.height, short, round_to=8, max_long_edge=1920)
        is_1080p = self.cfg.resolution == "1080p" or short >= 1080 or width >= 1080 or height >= 1080
        max_f = MAX_FRAMES_1080P if is_1080p else MAX_FRAMES
        max_sec = 10.0 if is_1080p else min(MAX_SECONDS, float(self.cfg.max_clip_seconds))
        seconds = min(max(req.duration, MIN_SECONDS), max_sec)
        num_frames = duration_to_frames(seconds, max_frames=max_f)
        payload: dict[str, Any] = {
            "model": self.model,
            "prompt": req.prompt,
            "height": height,
            "width": width,
            "num_frames": num_frames,
            "frame_rate": FPS,
        }
        if req.seed is not None:
            payload["seed"] = req.seed
        if req.start_image and req.end_image:
            b64_start = _b64(req.start_image)
            b64_end = _b64(req.end_image)
            payload["image"] = b64_start
            payload["image_tail"] = b64_end
            payload["last_frame"] = b64_end
            payload["extra_body"] = {"image": [b64_start, b64_end], "mode": "keyframes"}
        elif req.start_image:
            payload["image"] = _b64(req.start_image)
        elif req.reference_images:
            payload["extra_body"] = {"image": [_b64(p) for p in req.reference_images[:MAX_REFERENCES]]}
        return payload

    def _build_v25_payload(self, req: VideoRequest) -> dict[str, Any]:
        size = (self.cfg.resolution or "720p").upper()
        if self.model == "agnes-video-2.5-flash":
            if size != "720P":
                log.warning("Agnes Video 2.5 Flash 僅支援 720P，自動調整輸出解析度為 720P（原設定為 %s）。", self.cfg.resolution)
                size = "720P"
        elif size not in ("720P", "1080P", "1K", "2K"):
            raise ProviderError("Agnes Video 2.5 請選擇 720p 或 1080p（或 1K、2K），未支援 480p。")

        ratios = {"21:9": 21/9, "16:9": 16/9, "4:3": 4/3, "1:1": 1, "3:4": 3/4, "9:16": 9/16}
        ratio = min(ratios, key=lambda key: abs(ratios[key] - req.width / req.height))
        payload: dict[str, Any] = {
            "model": self.model, "prompt": req.prompt, "mode": "text",
            "seconds": str(max(4, min(12, self.cfg.max_clip_seconds, math.ceil(req.duration)))),
            "size": size, "aspect_ratio": ratio,
        }
        if req.seed is not None:
            payload["seed"] = req.seed

        def source(path: Path) -> str:
            url = public_source(path)
            if url:
                return url
            if path.is_file():
                ext = path.suffix.lower().lstrip(".")
                mime = "image/jpeg" if ext in ("jpg", "jpeg") else "image/webp" if ext == "webp" else "image/png"
                b64 = base64.b64encode(path.read_bytes()).decode("ascii")
                return f"data:{mime};base64,{b64}"
            raise ProviderError(f"Agnes Video 圖片未找到：{path.name}")

        if req.start_image or req.end_image:
            payload["mode"] = "keyframe"
            if req.start_image:
                payload["first_frame"] = source(req.start_image)
            if req.end_image:
                payload["last_frame"] = source(req.end_image)
        elif req.reference_images:
            payload["mode"] = "reference"
            max_refs = 5 if self.model == "agnes-video-2.5-flash" else MAX_REFERENCES
            payload["images"] = [source(p) for p in req.reference_images[:max_refs]]
        return payload

    async def generate(self, req: VideoRequest) -> Path:
        payload = await asyncio.to_thread(self.build_payload, req)
        async with httpx.AsyncClient(timeout=60) as client:
            task_id = await self._submit(client, payload)
            log.info("Agnes video task %s submitted (model=%s)", task_id, self.model)
            final = await self._poll(client, task_id)
            url = first_url(final)
            if url is None:
                video_id = final.get("video_id")
                if isinstance(video_id, str) and video_id:
                    params: dict[str, str] = {"video_id": video_id}
                    if self.is_v25:
                        params["model_name"] = self.model
                    resp = await client.get(f"{self.host}/agnesapi", params=params, headers=self._headers())
                    if resp.status_code >= 400:
                        raise ProviderError(f"Agnes video query failed: HTTP {resp.status_code} {resp.text[:200]}")
                    url = first_url(resp.json())
            if url is None:
                raise ProviderError(f"Agnes task completed but returned no video URL (fields: {sorted(final)})")
            await self._download(client, url, req.output_path)
        return req.output_path

    async def _submit(self, client: httpx.AsyncClient, payload: dict[str, Any]) -> str:
        last = ""
        max_attempts = 12 if self.model == "agnes-video-2.5-flash" else 6
        for attempt in range(max_attempts):
            try:
                resp = await client.post(f"{self.base}/videos", json=payload, headers=self._headers(), timeout=300)
            except httpx.HTTPError as exc:
                raise ProviderError(f"Agnes video submit failed: {exc}") from exc
            if resp.status_code < 400:
                body = resp.json()
                for key in (("video_id", "id", "task_id") if self.is_v25 else ("task_id", "id")):
                    if isinstance(body.get(key), str) and body[key]:
                        return body[key]
                raise ProviderError(f"Agnes video submit returned no task_id (fields: {sorted(body)})")
            
            resp_text = resp.text
            last = f"HTTP {resp.status_code}: {resp_text[:300]}"

            # Auto-clamp num_frames if rejected by Agnes limit (e.g. num_frames 433 exceeds maximum 241 for 1080p)
            if resp.status_code == 400 and "num_frames" in resp_text and ("exceeds maximum" in resp_text or "Max frames" in resp_text):
                match = re.search(r"maximum\s+(\d+)", resp_text)
                limit = int(match.group(1)) if match else 241
                if payload.get("num_frames", 0) > limit:
                    log.warning(
                        "Agnes video rejected num_frames %s, auto-clamping to %s and retrying (attempt %d)",
                        payload.get("num_frames"), limit, attempt + 1,
                    )
                    payload["num_frames"] = limit
                    continue

            # Queue full (503) or rate limit (429) or transient errors
            if resp.status_code in (408, 429) or resp.status_code >= 500:
                if attempt < max_attempts - 1:
                    # Agnes free tier rate-limits if retried <25s. On 503 queue_full or 429, wait 28~32s.
                    if resp.status_code == 429:
                        wait = 32
                        log.warning(
                            "Agnes 影片提交觸發頻率限制 (HTTP 429)，等待 %ds 後重試（第 %d/%d 次）...",
                            wait, attempt + 1, max_attempts,
                        )
                    elif "video_queue_full" in resp_text or resp.status_code == 503:
                        wait = 28 + (attempt % 3) * 2
                        log.warning(
                            "Agnes 影片伺服器佇列滿載 (503 video_queue_full)，等待 %ds 後重試排隊（第 %d/%d 次）...",
                            wait, attempt + 1, max_attempts,
                        )
                    else:
                        wait = 20
                        log.warning(
                            "Agnes 影片提交回傳 HTTP %s，等待 %ds 後重試（第 %d/%d 次）...",
                            resp.status_code, wait, attempt + 1, max_attempts,
                        )
                    await asyncio.sleep(wait)
                    continue
            break
        if "video_queue_full" in last:
            raise ProviderError(
                f"Agnes 影片生成失敗：伺服器佇列持續滿載 (video_queue_full)。"
                "由於 agnes-video-2.5-flash 為限時免費模型，使用人數眾多導致伺服器佇列飽和，"
                "已自動排隊重試多次仍未成功。建議稍後離峰時段再試，或在「設定」切換運鏡模式為本機運鏡合成。"
            )
        if "rate_limit_exceeded" in last or "rate limit for free users" in last:
            raise ProviderError(
                f"Agnes 影片生成失敗：伺服器佇列滿載或觸發免費用戶頻率限制 ({last})。"
                "建議稍候 1~2 分鐘後再試，或在「設定」將影片模式改為本機 kenburns 運鏡合成。"
            )
        raise ProviderError(f"Agnes video submit rejected: {last}")

    async def _poll(self, client: httpx.AsyncClient, task_id: str) -> dict[str, Any]:
        waited = 0.0
        interval = 5.0
        errors = 0
        while waited < self.cfg.poll_timeout:
            await asyncio.sleep(interval)
            waited += interval
            try:
                if self.is_v25:
                    resp = await client.get(f"{self.host}/agnesapi", params={"video_id": task_id, "model_name": self.model}, headers=self._headers())
                else:
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
            if waited % 15.0 < interval:
                log.info("Agnes video task %s status=%s (waited %.0fs / %ds)", task_id, status, waited, self.cfg.poll_timeout)
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
