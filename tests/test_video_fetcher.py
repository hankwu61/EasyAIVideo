"""Video URL fetching (yt-dlp is replaced by a fake; no network)."""

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from easyaivideo.services import video_fetcher
from easyaivideo.services.video_fetcher import (
    VideoFetchError,
    check_info,
    fetch_video,
    translate_error,
    validate_url,
)


def test_validate_url():
    assert validate_url(" https://www.youtube.com/shorts/abc ") == "https://www.youtube.com/shorts/abc"
    for bad in ("", "ftp://x.com/a.mp4", "youtube.com/watch?v=1", "file:///etc/passwd"):
        with pytest.raises(VideoFetchError):
            validate_url(bad)


def test_check_info_rejects_playlist_live_and_long():
    check_info({"duration": 59})
    with pytest.raises(VideoFetchError, match="播放清單"):
        check_info({"_type": "playlist", "entries": [{}, {}]})
    with pytest.raises(VideoFetchError, match="直播"):
        check_info({"is_live": True})
    with pytest.raises(VideoFetchError, match="超過上限 10.0 分鐘"):
        check_info({"duration": 601})


def test_translate_error():
    assert "私人" in translate_error("ERROR: [youtube] x: Private video. Sign in if you've been granted access")
    assert "年齡" in translate_error("Sign in to confirm your age. This video may be inappropriate for some users.")
    assert "地區" in translate_error("The uploader has not made this video available in your country")
    assert "不支援" in translate_error("ERROR: Unsupported URL: https://example.com/page")
    assert "移除" in translate_error("ERROR: [youtube] abc: Video unavailable")
    assert translate_error("weird").startswith("影片下載失敗")


class FakeYDL:
    """Mimics the parts of yt_dlp.YoutubeDL used by the fetcher."""

    info: dict = {}
    opts_seen: dict = {}

    def __init__(self, opts):
        FakeYDL.opts_seen = opts
        self.opts = opts

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def extract_info(self, url, download=False):
        return dict(FakeYDL.info, webpage_url=url)

    def process_ie_result(self, info, download=True):
        out = Path(self.opts["outtmpl"].replace("%(ext)s", "mp4"))
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(b"mp4")
        return dict(info, requested_downloads=[{"filepath": str(out)}])


@pytest.mark.asyncio
async def test_fetch_video_downloads_and_returns_meta(tmp_path: Path):
    FakeYDL.info = {"id": "abc", "title": "貓咪迷思", "uploader": "Cat TV", "duration": 56.7, "extractor_key": "Youtube"}
    with patch("yt_dlp.YoutubeDL", FakeYDL), patch.object(video_fetcher.ffmpeg, "probe_duration", new=AsyncMock(return_value=56.68)):
        got = await fetch_video("https://www.youtube.com/shorts/abc", tmp_path)
    assert got.path.read_bytes() == b"mp4"
    assert got.duration == 56.68 and got.title == "貓咪迷思" and got.extractor == "Youtube"
    meta = got.meta()
    assert meta["webpage_url"] == "https://www.youtube.com/shorts/abc" and meta["uploader"] == "Cat TV"
    assert FakeYDL.opts_seen["noplaylist"] is True and FakeYDL.opts_seen["merge_output_format"] == "mp4"
    assert "height<=1080" in FakeYDL.opts_seen["format"]


@pytest.mark.asyncio
async def test_fetch_video_rejects_too_long_before_download(tmp_path: Path):
    FakeYDL.info = {"id": "x", "duration": 3600}
    with patch("yt_dlp.YoutubeDL", FakeYDL):
        with pytest.raises(VideoFetchError, match="超過上限"):
            await fetch_video("https://www.youtube.com/watch?v=x", tmp_path)
    assert not list(tmp_path.glob("source.*"))


@pytest.mark.asyncio
async def test_fetch_video_translates_download_error(tmp_path: Path):
    from yt_dlp.utils import DownloadError

    class Broken(FakeYDL):
        def extract_info(self, url, download=False):
            raise DownloadError("ERROR: [youtube] q: Private video")

    with patch("yt_dlp.YoutubeDL", Broken):
        with pytest.raises(VideoFetchError, match="私人影片"):
            await fetch_video("https://youtu.be/q", tmp_path)


def test_clone_endpoint_url_and_validation(tmp_path: Path, monkeypatch):
    from fastapi.testclient import TestClient

    from easyaivideo.main import app
    from easyaivideo.models import Project
    from easyaivideo.services.video_clone_service import VideoCloneService
    from easyaivideo.services.video_fetcher import FetchedVideo

    captured: dict = {}

    async def fake_fetch(url, dest_dir, **kw):
        dest_dir.mkdir(parents=True, exist_ok=True)
        p = dest_dir / "source.mp4"
        p.write_bytes(b"mp4")
        return FetchedVideo(path=p, url=url, webpage_url=url, title="T", uploader="U", duration=20.0, extractor="Youtube")

    async def fake_clone(self, video_path, **kw):
        captured["path_exists"] = Path(video_path).is_file()
        captured.update(kw)
        meta = kw.get("source_meta") or {}
        return Project(id="proj_url", title="t", source_url=meta.get("webpage_url"), source_meta=meta)

    monkeypatch.setattr("easyaivideo.services.video_fetcher.fetch_video", fake_fetch)
    monkeypatch.setattr(VideoCloneService, "clone_from_video", fake_clone)
    with TestClient(app) as client:
        r = client.post("/api/projects/clone-video", data={"source_url": "https://youtu.be/abc"})
        assert r.status_code == 201, r.text
        assert r.json()["source_url"] == "https://youtu.be/abc"
        assert captured["path_exists"] and captured["source_meta"]["title"] == "T"

        r = client.post("/api/projects/clone-video", data={})
        assert r.status_code == 400
        r = client.post(
            "/api/projects/clone-video",
            data={"source_url": "https://youtu.be/abc"},
            files={"video_file": ("a.mp4", b"x", "video/mp4")},
        )
        assert r.status_code == 400
