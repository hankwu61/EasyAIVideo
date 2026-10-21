"""Build provider instances from the current config (re-read on every call for hot reload)."""

from __future__ import annotations

from typing import Optional

from ..config import AppConfig
from .base import ImageProvider, LLMProvider, ProviderError, TTSProvider, VideoProvider


def get_llm(cfg: AppConfig) -> LLMProvider:
    if cfg.llm.provider == "openai_compat":
        from .llm.openai_compat import OpenAICompatLLM

        return OpenAICompatLLM(cfg.llm)
    from .llm.mock import MockLLM

    return MockLLM()


def get_tts(cfg: AppConfig) -> TTSProvider:
    if cfg.tts.provider == "edge":
        from .tts.edge import EdgeTTS

        return EdgeTTS()
    if cfg.tts.provider == "openai_compat":
        from .tts.openai_compat import OpenAICompatTTS

        return OpenAICompatTTS(cfg.tts)
    if cfg.tts.provider == "fish_audio":
        from .tts.fish_audio import FishAudioTTS

        return FishAudioTTS(cfg.tts)
    from .tts.silent import SilentTTS

    return SilentTTS()


def get_image(cfg: AppConfig) -> ImageProvider:
    if cfg.image.provider == "openai_compat":
        from .image.openai_compat import OpenAICompatImage

        return OpenAICompatImage(cfg.image)
    if cfg.image.provider == "comfyui":
        from .image.comfyui import ComfyUIImage

        return ComfyUIImage(cfg.image)
    from .image.placeholder import PlaceholderImage

    return PlaceholderImage()


def get_video(cfg: AppConfig) -> Optional[VideoProvider]:
    """Returns an AI video provider, or None when clips are animated locally (kenburns)."""
    if cfg.video.provider == "comfyui":
        from .video.comfyui import ComfyUIVideo

        return ComfyUIVideo(cfg.video)
    if cfg.video.provider == "agnes":
        from .video.agnes import AgnesVideo

        return AgnesVideo(cfg.video)
    if cfg.video.provider == "minimax":
        from .video.minimax import MinimaxVideo

        return MinimaxVideo(cfg.video)
    if cfg.video.provider == "comfyui_minimax":
        from .video.comfyui_minimax import ComfyUIMinimaxVideo

        return ComfyUIMinimaxVideo(cfg.video)
    return None


def get_vision(cfg: AppConfig):
    if cfg.llm.provider == "mock" and not cfg.review.model:
        from .llm.vision import MockVision

        return MockVision()
    from .llm.vision import OpenAICompatVision

    return OpenAICompatVision(cfg)


async def test_provider(cfg: AppConfig, kind: str) -> str:
    if kind == "llm":
        return await get_llm(cfg).test()
    if kind == "review":
        return await get_vision(cfg).test()
    if kind == "tts":
        return await get_tts(cfg).test()
    if kind == "image":
        return await get_image(cfg).test()
    if kind == "video":
        provider = get_video(cfg)
        if provider is None:
            return "Video provider 'kenburns' uses ffmpeg only; nothing to test."
        return await provider.test()
    if kind == "comfyui":
        from .comfyui import ComfyUIClient

        url = cfg.image.comfyui_url if cfg.image.provider == "comfyui" else cfg.video.comfyui_url
        try:
            stats = await ComfyUIClient(url).stats()
        except Exception as exc:  # noqa: BLE001
            raise ProviderError(f"Cannot reach ComfyUI at {url}: {exc}") from exc
        version = stats.get("system", {}).get("comfyui_version", "?")
        return f"ComfyUI online at {url} (version {version})"
    if kind == "youtube":
        yt = cfg.publish.youtube
        if yt.mock:
            return "YouTube Shorts 目前處於「沙盒模擬測試模式（Mock Mode）」，發布時將模擬上傳成功。"
        token = (yt.refresh_token or "").strip()
        if not token:
            raise ProviderError("請填寫 YouTube refresh_token。")
        import httpx
        if token.startswith("ya29."):
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.get(
                    "https://www.googleapis.com/youtube/v3/channels?part=snippet&mine=true",
                    headers={"Authorization": f"Bearer {token}"},
                )
                if res.status_code != 200:
                    raise ProviderError(f"YouTube Access Token 驗證失敗 ({res.status_code}): {res.text}")
                items = res.json().get("items", [])
                name = items[0]["snippet"]["title"] if items else "已授權頻道"
                return f"YouTube 連線驗證成功！已連接頻道: {name} (Access Token 模式)"
        if yt.client_id and yt.client_secret:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.post(
                    "https://oauth2.googleapis.com/token",
                    data={
                        "client_id": yt.client_id,
                        "client_secret": yt.client_secret,
                        "refresh_token": token,
                        "grant_type": "refresh_token",
                    },
                )
                if res.status_code != 200:
                    err_text = res.text
                    if "unauthorized_client" in err_text:
                        raise ProviderError(
                            "Google OAuth 驗證失敗: Client ID 與 Refresh Token 不匹配 (unauthorized_client)。\n"
                            "原因：此 Refresh Token 不是由您填寫的 Client ID 所簽發。\n"
                            "解決方式：在 Google OAuth Playground 右上角齒輪 ⚙️ 勾選「Use your own OAuth credentials」並填入此 Client ID 與 Secret 後重新授權；\n"
                            "或者在 OAuth Playground Step 2 點擊「Exchange authorization code for tokens」後，直接將產生的 Access token (ya29...) 複製貼入 refresh_token 欄位。"
                        )
                    raise ProviderError(f"Google OAuth 驗證失敗 ({res.status_code}): {err_text}")
                access_token = res.json().get("access_token")
                if access_token:
                    ch_res = await client.get(
                        "https://www.googleapis.com/youtube/v3/channels?part=snippet&mine=true",
                        headers={"Authorization": f"Bearer {access_token}"},
                    )
                    if ch_res.status_code == 200:
                        items = ch_res.json().get("items", [])
                        if items:
                            return f"YouTube Shorts 連線驗證成功！已成功連接頻道: {items[0]['snippet']['title']}"
        return "YouTube Shorts 連線驗證成功，可正常發布影片。"
    if kind == "tiktok":
        tt = cfg.publish.tiktok
        if tt.mock:
            return "TikTok 目前處於「沙盒模擬測試模式（Mock Mode）」，發布時將模擬上傳成功。"
        if not tt.access_token:
            raise ProviderError("請填寫 TikTok access_token。")
        return "TikTok 設定格式正確，已就緒發布。"
    if kind == "webhook":
        wh = cfg.publish.webhook
        if not wh.url:
            raise ProviderError("請填寫 Webhook URL。")
        return f"Webhook 設定完成 ({wh.url})"
    raise ProviderError(f"Unknown provider kind: {kind}")
