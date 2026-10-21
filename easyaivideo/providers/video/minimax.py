"""MiniMax H3 video provider (official v2 API).

POST {root}/v2/video_generation            -> {"task_id": ...}
GET  {root}/v2/query/video_generation/{id} -> {"task": {"status", "content": {"url"}, "error"}}

Request body uses a ``content`` array; each item is text / image_url / video_url / audio_url with
an optional ``role``:

- T2V : text only (ratio required, never "adaptive")
- I2V : text + image(first_frame) / image(last_frame) / both (ratio is always adaptive)
- R2V : text + any mix of reference_image (<=9), reference_video (<=3, 2-15s, total <=15s)
        and reference_audio (<=3, 2-15s, total <=15s; never alone)

I2V roles and reference roles are mutually exclusive. Local files are sent as data URIs, so the
whole request body must stay under 64 MB.
"""

from __future__ import annotations

import asyncio
import base64
import logging
import mimetypes
from pathlib import Path
from typing import Any, Optional

import httpx

from ...config import VideoConfig
from ...services.media_source import public_source
from ..base import ProviderError, VideoRequest

log = logging.getLogger("easyaivideo.minimax")

DEFAULT_ROOT = "https://api.minimax.io"
H3_MODELS = ("MiniMax-H3", "MiniMax-H3-Max")
RATIOS = ("21:9", "16:9", "4:3", "1:1", "3:4", "9:16")
MAX_BODY_BYTES = 64 * 1024 * 1024
MAX_IMAGE_BYTES = 30 * 1024 * 1024
MAX_VIDEO_BYTES = 50 * 1024 * 1024
MAX_AUDIO_BYTES = 15 * 1024 * 1024

_MIME_FALLBACK = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".mp4": "video/mp4",
    ".mov": "video/quicktime",
    ".wav": "audio/wav",
    ".mp3": "audio/mpeg",
}


def api_root(base_url: str) -> str:
    """Normalise a configured base URL to the API root (no /v1 or /v2 suffix).

    Empty or non-MiniMax URLs (e.g. the Agnes default left in the settings) fall back to the
    international endpoint.
    """
    base = (base_url or "").strip().rstrip("/")
    if not base or "minimax" not in base.lower():
        return DEFAULT_ROOT
    for suffix in ("/v1", "/v2"):
        if base.endswith(suffix):
            base = base[: -len(suffix)]
    return base


def normalise_model(model: str) -> str:
    m = (model or "").strip()
    for known in H3_MODELS:
        if m.lower() == known.lower():
            return known
    return "MiniMax-H3"


def clamp_duration(model: str, seconds: float) -> int:
    lo = 5 if model == "MiniMax-H3-Max" else 4
    return int(max(lo, min(15, round(seconds))))


def pick_resolution(model: str, wanted: str) -> str:
    wanted = (wanted or "768P").upper()
    if model == "MiniMax-H3-Max":
        return wanted if wanted in ("480P", "768P") else "768P"
    return wanted if wanted in ("768P", "2K") else "768P"


def _mime(path: Path) -> str:
    return _MIME_FALLBACK.get(path.suffix.lower()) or mimetypes.guess_type(path.name)[0] or "application/octet-stream"


def file_to_url(path: Path, *, limit: int, kind: str) -> str:
    """Public URL when the file was downloaded from one (verified by hash), else a data URI."""
    if not path.is_file():
        raise ProviderError(f"MiniMax {kind} file not found: {path.name}")
    pub = public_source(path)
    if pub:
        return pub
    size = path.stat().st_size
    if size > limit:
        raise ProviderError(f"MiniMax {kind} {path.name} is {size / 1e6:.1f} MB (limit {limit / 1e6:.0f} MB).")
    return f"data:{_mime(path)};base64,{base64.b64encode(path.read_bytes()).decode('ascii')}"


def infer_mode(req: VideoRequest) -> str:
    mode = (req.h3_mode or "").lower()
    if mode in ("ref2va", "t2va", "i2va", "fl2va", "l2va"):
        return mode
    # Explicit frames win: a normal i2v / keyframes project must keep its first (and last) frame;
    # I2V and reference roles are mutually exclusive in the H3 API.
    if req.start_image and req.end_image:
        return "fl2va"
    if req.start_image:
        return "i2va"
    if req.end_image:
        return "l2va"
    if req.reference_videos or req.reference_images:
        return "ref2va"
    return "t2va"


class MinimaxVideo:
    name = "minimax"

    def __init__(self, cfg: VideoConfig) -> None:
        self.cfg = cfg
        if not cfg.api_key.strip():
            raise ProviderError("MiniMax api_key is empty. Fill it in Settings → Video.")
        self.root = api_root(cfg.base_url)
        self.model = normalise_model(cfg.model)
        self.resolution = pick_resolution(self.model, getattr(cfg, "minimax_resolution", "768P"))

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.cfg.api_key.strip()}",
            "Content-Type": "application/json",
        }

    # ------------------------------------------------------------ payload
    def build_payload(self, req: VideoRequest) -> dict[str, Any]:
        prompt = req.prompt.strip()
        if not prompt:
            raise ProviderError("MiniMax H3 prompt is empty.")
        if len(prompt) > 7000:
            raise ProviderError(f"MiniMax H3 prompt is {len(prompt)} characters (limit 7000).")

        mode = infer_mode(req)
        content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
        ratio: Optional[str] = req.ratio if req.ratio in RATIOS else None

        if mode == "ref2va":
            images = [p for p in req.reference_images if p and p.is_file()][:9]
            videos = [p for p in req.reference_videos if p and p.is_file()][:3]
            audios = [p for p in req.reference_audios if p and p.is_file()][:3]
            if not images and not videos:
                raise ProviderError("MiniMax R2V needs at least one reference image or reference video.")
            for p in images:
                content.append({"type": "image_url", "image_url": {"url": file_to_url(p, limit=MAX_IMAGE_BYTES, kind="image")}, "role": "reference_image"})
            for p in videos:
                content.append({"type": "video_url", "video_url": {"url": file_to_url(p, limit=MAX_VIDEO_BYTES, kind="video")}, "role": "reference_video"})
            for p in audios:
                content.append({"type": "audio_url", "audio_url": {"url": file_to_url(p, limit=MAX_AUDIO_BYTES, kind="audio")}, "role": "reference_audio"})
        elif mode in ("i2va", "fl2va", "l2va"):
            first = req.start_image if mode in ("i2va", "fl2va") else None
            last = req.end_image if mode in ("fl2va", "l2va") else None
            if first is None and last is None:
                raise ProviderError(f"MiniMax {mode.upper()} needs a first and/or last frame image.")
            if first is not None:
                content.append({"type": "image_url", "image_url": {"url": file_to_url(first, limit=MAX_IMAGE_BYTES, kind="image")}, "role": "first_frame"})
            if last is not None:
                content.append({"type": "image_url", "image_url": {"url": file_to_url(last, limit=MAX_IMAGE_BYTES, kind="image")}, "role": "last_frame"})
            ratio = "adaptive"
        else:  # t2va
            if ratio is None:
                ratio = "9:16" if req.height > req.width else ("16:9" if req.width > req.height else "1:1")

        payload: dict[str, Any] = {
            "model": self.model,
            "content": content,
            "resolution": self.resolution,
            "duration": clamp_duration(self.model, self._capped_seconds(req)),
        }
        if ratio:
            payload["ratio"] = ratio
        return payload

    def _capped_seconds(self, req: VideoRequest) -> float:
        """Settings → max clip seconds applies to ordinary scenes; H3 clone parts set h3_mode and are pre-planned."""
        if req.h3_mode:
            return req.duration
        cap = float(getattr(self.cfg, "max_clip_seconds", 15) or 15)
        return min(req.duration, cap)

    # ------------------------------------------------------------ run
    async def generate(self, req: VideoRequest) -> Path:
        payload = await asyncio.to_thread(self.build_payload, req)
        approx = sum(len(str(item)) for item in payload["content"])
        if approx > MAX_BODY_BYTES:
            raise ProviderError(f"MiniMax request body ~{approx / 1e6:.1f} MB exceeds the 64 MB limit; shorten or compress the references.")
        async with httpx.AsyncClient(timeout=120) as client:
            task_id = await self._submit(client, payload)
            log.info("MiniMax H3 task %s submitted (model=%s, %s, %ss)", task_id, self.model, self.resolution, payload["duration"])
            url = await self._poll(client, task_id)
            await self._download(client, url, req.output_path)
        return req.output_path

    @staticmethod
    def _error_text(resp: httpx.Response) -> str:
        try:
            body = resp.json()
        except ValueError:
            return resp.text[:300]
        err = body.get("error") if isinstance(body, dict) else None
        if isinstance(err, dict) and err.get("message"):
            return str(err["message"])
        base = body.get("base_resp") if isinstance(body, dict) else None
        if isinstance(base, dict) and base.get("status_msg"):
            return str(base["status_msg"])
        return resp.text[:300]

    async def _submit(self, client: httpx.AsyncClient, payload: dict[str, Any]) -> str:
        url = f"{self.root}/v2/video_generation"
        try:
            resp = await client.post(url, json=payload, headers=self._headers(), timeout=300)
        except httpx.HTTPError as exc:
            raise ProviderError(f"MiniMax video submit request failed: {exc}") from exc
        if resp.status_code >= 400:
            hint = {401: "API key 無效", 402: "餘額不足", 422: "內容審核未通過", 429: "請求過於頻繁"}.get(resp.status_code, "")
            raise ProviderError(f"MiniMax video submit failed (HTTP {resp.status_code}{' ' + hint if hint else ''}): {self._error_text(resp)}")
        body = resp.json()
        task_id = body.get("task_id") or (body.get("task") or {}).get("id")
        if not task_id:
            raise ProviderError(f"MiniMax video submit response missing task_id: {str(body)[:300]}")
        return str(task_id)

    async def _poll(self, client: httpx.AsyncClient, task_id: str) -> str:
        url = f"{self.root}/v2/query/video_generation/{task_id}"
        timeout = float(self.cfg.poll_timeout or 1800)
        interval = 5.0
        elapsed = 0.0
        while elapsed < timeout:
            await asyncio.sleep(interval)
            elapsed += interval
            try:
                resp = await client.get(url, headers=self._headers(), timeout=30)
            except httpx.HTTPError as exc:
                log.warning("MiniMax poll error (will retry): %s", exc)
                continue
            if resp.status_code >= 400:
                if resp.status_code in (400, 401, 404):
                    raise ProviderError(f"MiniMax query failed (HTTP {resp.status_code}): {self._error_text(resp)}")
                log.warning("MiniMax poll HTTP %s: %s", resp.status_code, resp.text[:200])
                continue
            task = (resp.json() or {}).get("task") or {}
            status = str(task.get("status", "")).lower()
            if status == "succeeded":
                out = (task.get("content") or {}).get("url")
                if not out:
                    raise ProviderError(f"MiniMax task succeeded but no video url: {str(task)[:300]}")
                return str(out)
            if status in ("failed", "cancelled"):
                err = task.get("error") or {}
                msg = err.get("message") if isinstance(err, dict) else str(err)
                raise ProviderError(f"MiniMax H3 generation {status}: {msg or 'unknown error'}")
            if elapsed > 60:
                interval = 10.0
        raise ProviderError(f"MiniMax video generation timed out after {timeout:.0f} seconds.")

    async def _download(self, client: httpx.AsyncClient, url: str, dest: Path) -> None:
        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp = dest.with_suffix(".tmp")
        try:
            async with client.stream("GET", url, timeout=300) as resp:
                resp.raise_for_status()
                with open(tmp, "wb") as f:
                    async for chunk in resp.aiter_bytes(chunk_size=65536):
                        f.write(chunk)
            tmp.replace(dest)
        except Exception as exc:
            tmp.unlink(missing_ok=True)
            raise ProviderError(f"Failed to download MiniMax video: {exc}") from exc

    async def test(self) -> str:
        async with httpx.AsyncClient(timeout=15) as client:
            try:
                resp = await client.get(f"{self.root}/v2/query/video_generation/test_connectivity", headers=self._headers())
            except httpx.HTTPError as exc:
                raise ProviderError(f"MiniMax 連線失敗: {exc}") from exc
        if resp.status_code == 401:
            raise ProviderError("MiniMax API Key 驗證無效 (HTTP 401)。請檢查設定。")
        if resp.status_code in (200, 400, 404):
            return f"MiniMax H3 API 在線（{self.root}，模型 {self.model}，{self.resolution}）"
        raise ProviderError(f"MiniMax 連線失敗: HTTP {resp.status_code} {resp.text[:150]}")
