"""Publishing service for uploading rendered videos to YouTube Shorts, TikTok, and webhooks."""

from __future__ import annotations

import asyncio
import logging
import secrets
from pathlib import Path
from typing import Any, Awaitable, Callable, Optional

import httpx

from ..config import config_manager
from ..db import Database
from ..models import Project, PublishPlatform, PublishPrivacy, PublishRecord, now_iso
from . import storage

log = logging.getLogger("easyaivideo.publish")
Progress = Callable[[float, str], Awaitable[None]]


class PublishError(RuntimeError):
    pass


class YouTubePublisher:
    """Publishes videos to YouTube Shorts via YouTube Data API v3."""

    def __init__(self, db: Database) -> None:
        self.db = db

    async def publish(
        self,
        video_path: Path,
        title: str,
        description: str,
        tags: list[str],
        privacy: PublishPrivacy,
        schedule_time: Optional[str] = None,
        progress: Optional[Progress] = None,
    ) -> tuple[str, str]:
        """Returns (video_id, video_url)."""
        cfg = config_manager.get().publish.youtube
        if cfg.mock:
            if progress:
                await progress(0.2, "【模擬發布】正在上傳至 YouTube Shorts…")
            await asyncio.sleep(1.0)
            mock_id = f"yt_{secrets.token_hex(5)}"
            url = f"https://www.youtube.com/shorts/{mock_id}"
            if progress:
                await progress(0.9, "【模擬發布】YouTube Shorts 發布成功")
            return mock_id, url

        # Real YouTube Upload
        access_token = await self._get_access_token(cfg.client_id, cfg.client_secret, cfg.refresh_token)
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json; charset=UTF-8",
            "X-Upload-Content-Type": "video/mp4",
            "X-Upload-Content-Length": str(video_path.stat().st_size),
        }

        # If schedule_time is present, YouTube requires privacyStatus to be 'private'
        effective_privacy = "private" if schedule_time else privacy
        body: dict[str, Any] = {
            "snippet": {
                "title": title[:100],
                "description": description[:5000],
                "tags": tags[:50],
                "categoryId": "22",
            },
            "status": {
                "privacyStatus": effective_privacy,
                "selfDeclaredMadeForKids": False,
            },
        }
        if schedule_time:
            body["status"]["publishAt"] = schedule_time

        init_url = "https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status"
        async with httpx.AsyncClient(timeout=120.0) as client:
            if progress:
                await progress(0.2, "正在向 YouTube 註冊影片…")
            res = await client.post(init_url, headers=headers, json=body)
            if res.status_code not in (200, 201):
                raise PublishError(f"YouTube 註冊上傳失敗 ({res.status_code}): {res.text}")

            upload_url = res.headers.get("Location")
            if not upload_url:
                raise PublishError("YouTube 未回傳上傳網址 (Location Header)")

            if progress:
                await progress(0.5, "正在上傳影片資料至 YouTube…")

            video_data = video_path.read_bytes()
            up_res = await client.put(
                upload_url,
                headers={"Content-Type": "video/mp4", "Content-Length": str(len(video_data))},
                content=video_data,
            )
            if up_res.status_code not in (200, 201):
                raise PublishError(f"YouTube 影片上傳失敗 ({up_res.status_code}): {up_res.text}")

            data = up_res.json()
            video_id = data.get("id")
            if not video_id:
                raise PublishError(f"YouTube 未回傳 video id: {data}")
            return str(video_id), f"https://www.youtube.com/shorts/{video_id}"

    async def _get_access_token(self, client_id: str, client_secret: str, refresh_token: str) -> str:
        if not refresh_token:
            raise PublishError("未設定 YouTube refresh_token，請至「設定 -> 社群發布」填寫。")
        if not client_id or not client_secret:
            # Maybe user provided direct access token in refresh_token field
            return refresh_token

        token_url = "https://oauth2.googleapis.com/token"
        payload = {
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        }
        async with httpx.AsyncClient(timeout=15.0) as client:
            res = await client.post(token_url, data=payload)
            if res.status_code != 200:
                raise PublishError(f"更新 YouTube OAuth token 失敗 ({res.status_code}): {res.text}")
            token = res.json().get("access_token")
            if not token:
                raise PublishError("Google OAuth 未回傳 access_token")
            return str(token)


class TikTokPublisher:
    """Publishes videos to TikTok via TikTok Content Posting API v2."""

    def __init__(self, db: Database) -> None:
        self.db = db

    async def publish(
        self,
        video_path: Path,
        title: str,
        privacy: PublishPrivacy,
        schedule_time: Optional[str] = None,
        progress: Optional[Progress] = None,
    ) -> tuple[str, str]:
        """Returns (publish_id, video_url)."""
        cfg = config_manager.get().publish.tiktok
        if cfg.mock:
            if progress:
                await progress(0.2, "【模擬發布】正在上傳至 TikTok…")
            await asyncio.sleep(1.0)
            mock_id = f"tt_{secrets.token_hex(6)}"
            url = f"https://www.tiktok.com/@user/video/{mock_id}"
            if progress:
                await progress(0.9, "【模擬發布】TikTok 發布成功")
            return mock_id, url

        # Real TikTok Upload
        if not cfg.access_token:
            raise PublishError("未設定 TikTok access_token，請至「設定 -> 社群發布」填寫。")

        size = video_path.stat().st_size
        privacy_map = {
            "public": "PUBLIC_TO_EVERYONE",
            "unlisted": "MUTUAL_FOLLOW_FRIENDS",
            "private": "SELF_ONLY",
        }
        init_url = "https://open.tiktokapis.com/v2/post/publish/video/init/"
        headers = {
            "Authorization": f"Bearer {cfg.access_token}",
            "Content-Type": "application/json; charset=UTF-8",
        }
        body: dict[str, Any] = {
            "post_info": {
                "title": title[:150],
                "privacy_level": privacy_map.get(privacy, "PUBLIC_TO_EVERYONE"),
                "disable_duet": False,
                "disable_stitch": False,
                "disable_comment": False,
                "video_cover_timestamp_ms": 1000,
            },
            "source_info": {
                "source": "FILE_UPLOAD",
                "video_size": size,
                "chunk_size": size,
                "total_chunk_count": 1,
            },
        }

        async with httpx.AsyncClient(timeout=120.0) as client:
            if progress:
                await progress(0.3, "正在向 TikTok 註冊影片發布…")
            res = await client.post(init_url, headers=headers, json=body)
            if res.status_code != 200:
                raise PublishError(f"TikTok 註冊上傳失敗 ({res.status_code}): {res.text}")

            res_data = res.json().get("data") or {}
            publish_id = res_data.get("publish_id")
            upload_url = res_data.get("upload_url")
            if not upload_url:
                raise PublishError(f"TikTok 未回傳 upload_url: {res.text}")

            if progress:
                await progress(0.6, "正在上傳影片資料至 TikTok…")

            video_data = video_path.read_bytes()
            up_res = await client.put(
                upload_url,
                headers={
                    "Content-Range": f"bytes 0-{size - 1}/{size}",
                    "Content-Type": "video/mp4",
                    "Content-Length": str(size),
                },
                content=video_data,
            )
            if up_res.status_code not in (200, 201, 206):
                raise PublishError(f"TikTok 檔案上傳失敗 ({up_res.status_code}): {up_res.text}")

            video_url = f"https://www.tiktok.com/@user/video/{publish_id}" if publish_id else "https://www.tiktok.com"
            return str(publish_id or "tiktok_published"), video_url


class WebhookPublisher:
    """Sends publish webhook notification with video details."""

    def __init__(self, db: Database) -> None:
        self.db = db

    async def publish(
        self,
        project: Project,
        title: str,
        description: str,
        tags: list[str],
        progress: Optional[Progress] = None,
    ) -> tuple[str, str]:
        cfg = config_manager.get().publish.webhook
        if not cfg.enabled or not cfg.url:
            raise PublishError("Webhook 未啟用或未設定 URL")

        if progress:
            await progress(0.5, "正在發送發布通知至 Webhook…")

        payload = {
            "event": "video_published",
            "project_id": project.id,
            "title": title,
            "description": description,
            "tags": tags,
            "final_video_url": project.final_video_url,
            "aspect_ratio": project.aspect_ratio,
            "timestamp": now_iso(),
        }
        headers = {"Content-Type": "application/json"}
        if cfg.secret:
            headers["X-Webhook-Secret"] = cfg.secret

        async with httpx.AsyncClient(timeout=15.0) as client:
            res = await client.post(cfg.url, headers=headers, json=payload)
            if res.status_code >= 400:
                raise PublishError(f"Webhook 呼叫失敗 ({res.status_code}): {res.text}")
            return "webhook", cfg.url


class PublisherService:
    """Orchestrates scheduled and immediate publishing across all enabled platforms."""

    def __init__(self, db: Database) -> None:
        self.db = db
        self.youtube = YouTubePublisher(db)
        self.tiktok = TikTokPublisher(db)
        self.webhook = WebhookPublisher(db)

    async def publish(
        self,
        project: Project,
        progress: Progress,
        payload: Optional[dict[str, Any]] = None,
    ) -> Project:
        payload = payload or {}
        if not project.final_video_path:
            raise PublishError("專案尚未合成最終影片，請先合成影片。")

        video_path = storage.abs_path(project.final_video_path)
        if not video_path.exists():
            raise PublishError(f"合成影片檔案遺失: {project.final_video_path}")

        # Resolve publishing settings
        settings = project.publish_settings
        platforms: list[PublishPlatform] = payload.get("platforms") or settings.platforms or ["youtube"]
        privacy: PublishPrivacy = payload.get("privacy") or settings.privacy or "public"
        schedule_time: Optional[str] = payload.get("schedule_time") or (
            settings.schedule_time if settings.schedule_mode == "scheduled" else None
        )

        title = payload.get("title") or self._format_text(settings.title_template, project)
        description = payload.get("description") or self._format_text(settings.description_template, project)
        tags = payload.get("tags") or settings.tags or ["Shorts", "AI"]

        project.publish_status = "publishing"
        await self.db.save_project(project)
        await progress(0.05, f"開始發布至 {len(platforms)} 個平台…")

        any_failed = False
        n = len(platforms)

        for i, plat in enumerate(platforms):
            lo = 0.05 + 0.9 * i / n
            hi = 0.05 + 0.9 * (i + 1) / n

            async def sub_progress(p: float, msg: str) -> None:
                await progress(lo + (hi - lo) * p, msg)

            try:
                if plat == "youtube":
                    vid, url = await self.youtube.publish(
                        video_path=video_path,
                        title=title,
                        description=description,
                        tags=tags,
                        privacy=privacy,
                        schedule_time=schedule_time,
                        progress=sub_progress,
                    )
                elif plat == "tiktok":
                    vid, url = await self.tiktok.publish(
                        video_path=video_path,
                        title=title,
                        privacy=privacy,
                        schedule_time=schedule_time,
                        progress=sub_progress,
                    )
                elif plat == "webhook":
                    vid, url = await self.webhook.publish(
                        project=project,
                        title=title,
                        description=description,
                        tags=tags,
                        progress=sub_progress,
                    )
                else:
                    raise PublishError(f"未知的發布平台: {plat}")

                record = PublishRecord(
                    platform=plat,
                    status="succeeded",
                    video_id=vid,
                    url=url,
                    title=title,
                    scheduled_at=schedule_time,
                    published_at=now_iso(),
                )
                project.publish_records.insert(0, record)
            except Exception as exc:  # noqa: BLE001
                any_failed = True
                log.exception("Publish to %s failed for %s", plat, project.id)
                record = PublishRecord(
                    platform=plat,
                    status="failed",
                    title=title,
                    scheduled_at=schedule_time,
                    published_at=now_iso(),
                    error=str(exc),
                )
                project.publish_records.insert(0, record)

        project.publish_status = "failed" if any_failed and len(project.publish_records) == 1 else "published"
        # Clear one-time schedule once published
        if schedule_time and project.publish_status == "published":
            project.publish_settings.schedule_time = None

        await self.db.save_project(project)
        await progress(1.0, "社群發布完成" if not any_failed else "部分社群發布失敗")
        return project

    @staticmethod
    def _format_text(template: str, project: Project) -> str:
        safe_title = project.title or "短影音"
        safe_topic = project.topic or safe_title
        try:
            return template.format(title=safe_title, topic=safe_topic)
        except Exception:
            return f"{safe_title} #Shorts"
