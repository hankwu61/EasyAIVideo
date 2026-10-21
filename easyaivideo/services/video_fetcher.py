"""Download a video from a web page URL (YouTube, TikTok, Bilibili, X, Instagram, direct .mp4 ...) via yt-dlp.

Only public videos are supported (no cookies / login). The download is capped by duration and file
size, merged to MP4 (H.264 + AAC preferred, <= 1080p) with the configured ffmpeg, and then handed to
the normal video clone flow.
"""

from __future__ import annotations

import asyncio
import logging
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlsplit

from . import ffmpeg

log = logging.getLogger("easyaivideo.fetch")

MAX_SOURCE_SECONDS = 600  # 10 minutes
MAX_FILESIZE = 800 * 1024 * 1024
FORMAT = (
    "bv*[height<=1080][vcodec^=avc1]+ba[ext=m4a]/"
    "bv*[height<=1080][vcodec^=avc1]+ba/"
    "bv*[height<=1080]+ba/"
    "b[height<=1080]/b"
)


class VideoFetchError(RuntimeError):
    pass


@dataclass
class FetchedVideo:
    path: Path
    url: str
    webpage_url: str = ""
    title: str = ""
    uploader: str = ""
    duration: Optional[float] = None
    extractor: str = ""
    video_id: str = ""
    thumbnail: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    def meta(self) -> dict[str, Any]:
        return {
            "url": self.url,
            "webpage_url": self.webpage_url or self.url,
            "title": self.title,
            "uploader": self.uploader,
            "duration": self.duration,
            "extractor": self.extractor,
            "video_id": self.video_id,
            "thumbnail": self.thumbnail,
        }


def yt_dlp_version() -> Optional[str]:
    try:
        from yt_dlp.version import __version__

        return str(__version__)
    except Exception:
        return None


def _fmt_len(seconds: float) -> str:
    return f"{seconds / 60:.1f} 分鐘" if seconds >= 120 else f"{seconds:.0f} 秒"


class _QuietLogger:
    """Routes yt-dlp output to our logger instead of stderr."""

    def debug(self, msg: str) -> None:
        pass

    def info(self, msg: str) -> None:
        pass

    def warning(self, msg: str) -> None:
        log.debug("yt-dlp: %s", msg)

    def error(self, msg: str) -> None:
        log.info("yt-dlp: %s", msg)


def validate_url(url: str) -> str:
    u = (url or "").strip()
    if not u:
        raise VideoFetchError("請輸入影片網址。")
    parts = urlsplit(u)
    if parts.scheme not in ("http", "https") or not parts.netloc:
        raise VideoFetchError("影片網址必須以 http:// 或 https:// 開頭。")
    return u


_ERROR_HINTS: tuple[tuple[tuple[str, ...], str], ...] = (
    (("private video", "this video is private"), "這是私人影片，無法下載。"),
    (("sign in to confirm your age", "age-restricted", "age restricted", "inappropriate for some users"), "此影片有年齡限制，需要登入才能下載（目前不支援登入）。"),
    (("sign in to confirm you", "login required", "log in", "logged-in", "cookies", "rate-limit", "rate limit"), "網站要求登入或暫時限制下載（目前不支援登入），請稍後再試或改用上傳檔案。"),
    (("in your country", "geo restriction", "geo-restricted", "blocked it in your country"), "此影片有地區限制，無法在你所在地區下載。"),
    (("unsupported url",), "不支援這個網址；請貼上單一影片頁面的網址（YouTube / TikTok / Bilibili / X / 直接 .mp4 連結等）。"),
    (("video unavailable", "has been removed", "http error 404", "404: not found", "does not exist"), "影片不存在或已被移除。"),
    (("is live", "live event", "premieres in", "this live"), "直播或尚未開始的首播無法下載。"),
    (("requested format is not available",), "找不到可下載的影片格式。"),
    (("ffmpeg", "ffprobe"), "合併影音需要 ffmpeg，請確認 ffmpeg 已安裝或在 設定 → 渲染 指定路徑。"),
)


def translate_error(message: str) -> str:
    low = (message or "").lower()
    for keys, hint in _ERROR_HINTS:
        if any(k in low for k in keys):
            return hint
    return f"影片下載失敗：{(message or '').strip()[:300]}"


def _ffmpeg_location() -> Optional[str]:
    binary = ffmpeg.ffmpeg_bin()
    p = Path(binary)
    if p.is_file():
        return str(p.parent)
    found = shutil.which(binary)
    return str(Path(found).parent) if found else None


def _base_opts(dest_dir: Path) -> dict[str, Any]:
    opts: dict[str, Any] = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "noprogress": True,
        "format": FORMAT,
        "merge_output_format": "mp4",
        "outtmpl": str(dest_dir / "source.%(ext)s"),
        "max_filesize": MAX_FILESIZE,
        "socket_timeout": 30,
        "retries": 3,
        "restrictfilenames": True,
        "overwrites": True,
        "logger": _QuietLogger(),
    }
    loc = _ffmpeg_location()
    if loc:
        opts["ffmpeg_location"] = loc
    return opts


def check_info(info: dict[str, Any], max_seconds: float = MAX_SOURCE_SECONDS) -> None:
    """Reject playlists, live streams and over-long videos before downloading."""
    if info.get("_type") in ("playlist", "multi_video") and not info.get("url"):
        entries = info.get("entries") or []
        raise VideoFetchError(f"這是播放清單／多影片網址（{len(list(entries)) or '多'} 部），請貼上單一影片的網址。")
    if info.get("is_live") or info.get("live_status") in ("is_live", "is_upcoming", "post_live"):
        raise VideoFetchError("直播或尚未開始的首播無法下載。")
    dur = info.get("duration")
    if isinstance(dur, (int, float)) and dur > max_seconds:
        raise VideoFetchError(f"影片長 {_fmt_len(dur)}，超過上限 {_fmt_len(max_seconds)}。")


def _find_output(info: dict[str, Any], dest_dir: Path) -> Path:
    for item in info.get("requested_downloads") or []:
        fp = item.get("filepath")
        if fp and Path(fp).is_file():
            return Path(fp)
    fp = info.get("filepath") or info.get("_filename")
    if fp and Path(fp).is_file():
        return Path(fp)
    candidates = sorted(
        (p for p in dest_dir.glob("source.*") if p.suffix.lower() in (".mp4", ".mkv", ".webm", ".mov")),
        key=lambda p: p.stat().st_size,
        reverse=True,
    )
    if candidates:
        return candidates[0]
    raise VideoFetchError("下載完成但找不到影片檔案。")


def _fetch_sync(url: str, dest_dir: Path, max_seconds: float) -> FetchedVideo:
    try:
        from yt_dlp import YoutubeDL
        from yt_dlp.utils import DownloadError
    except ImportError as exc:
        raise VideoFetchError("尚未安裝 yt-dlp：請在專案資料夾執行 `uv sync`（或 pip install yt-dlp）後重新啟動。") from exc

    dest_dir.mkdir(parents=True, exist_ok=True)
    opts = _base_opts(dest_dir)
    try:
        with YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if info is None:
                raise VideoFetchError("無法讀取影片資訊。")
            check_info(info, max_seconds)
            info = ydl.process_ie_result(info, download=True)
    except VideoFetchError:
        raise
    except DownloadError as exc:
        raise VideoFetchError(translate_error(str(exc))) from exc
    except Exception as exc:  # network errors, extractor crashes ...
        raise VideoFetchError(translate_error(str(exc))) from exc

    path = _find_output(info or {}, dest_dir)
    return FetchedVideo(
        path=path,
        url=url,
        webpage_url=str(info.get("webpage_url") or url),
        title=str(info.get("title") or ""),
        uploader=str(info.get("uploader") or info.get("channel") or ""),
        duration=float(info["duration"]) if isinstance(info.get("duration"), (int, float)) else None,
        extractor=str(info.get("extractor_key") or info.get("extractor") or ""),
        video_id=str(info.get("id") or ""),
        thumbnail=str(info.get("thumbnail") or ""),
    )


async def fetch_video(url: str, dest_dir: Path, *, max_seconds: float = MAX_SOURCE_SECONDS) -> FetchedVideo:
    """Download ``url`` into ``dest_dir`` and verify the result with ffprobe."""
    url = validate_url(url)
    fetched = await asyncio.to_thread(_fetch_sync, url, dest_dir, max_seconds)
    try:
        duration = await ffmpeg.probe_duration(fetched.path)
    except Exception as exc:
        raise VideoFetchError(f"下載的檔案無法解析：{exc}") from exc
    if duration <= 0:
        raise VideoFetchError("下載的影片時長無效。")
    if duration > max_seconds + 1:
        fetched.path.unlink(missing_ok=True)
        raise VideoFetchError(f"影片長 {_fmt_len(duration)}，超過上限 {_fmt_len(max_seconds)}。")
    fetched.duration = round(duration, 2)
    log.info("Fetched %s (%s, %.1fs) -> %s", url, fetched.extractor, duration, fetched.path.name)
    return fetched
