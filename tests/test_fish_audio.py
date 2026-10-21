import json
from unittest.mock import patch

import httpx
import pytest

from easyaivideo.config import AppConfig, ConfigManager, FishAudioConfig, TTSConfig
from easyaivideo.providers.base import ProviderError
from easyaivideo.providers.registry import get_tts
from easyaivideo.providers.tts.fish_audio import FEMALE, MALE, FishAudioTTS


def config():
    return TTSConfig(provider="fish_audio", voice=FEMALE, fish_audio=FishAudioConfig(
        api_key="test-key", female_reference_id="female-id", male_reference_id="male-id"))


@pytest.mark.asyncio
@pytest.mark.parametrize("voice,reference", [(FEMALE, "female-id"), (MALE, "male-id"),
    ("zh-TW-YunJheNeural", "male-id"), ("zh-TW-HsiaoChenNeural", "female-id")])
async def test_synthesize(tmp_path, voice, reference):
    def handler(request):
        assert str(request.url) == "https://api.fish.audio/v1/tts"
        assert request.headers["authorization"] == "Bearer test-key"
        assert request.headers["model"] == "s2.1-pro"
        assert json.loads(request.content) == {"text": "繁體中文測試", "reference_id": reference,
            "format": "mp3", "prosody": {"speed": 1.2}}
        return httpx.Response(200, content=b"audio", headers={"content-type": "audio/mpeg"})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    with patch("easyaivideo.providers.tts.fish_audio.httpx.AsyncClient", return_value=client):
        result = await FishAudioTTS(config()).synthesize("繁體中文測試", voice, 1.2, tmp_path / "a.mp3")
    assert result.read_bytes() == b"audio"


@pytest.mark.asyncio
@pytest.mark.parametrize("status,content,kind", [(401, b"secret", "application/json"),
    (402, b"balance", "application/json"), (200, b"", "audio/mpeg"),
    (200, b"{}", "application/json")])
async def test_failed_response(tmp_path, status, content, kind):
    client = httpx.AsyncClient(transport=httpx.MockTransport(
        lambda request: httpx.Response(status, content=content, headers={"content-type": kind})))
    with patch("easyaivideo.providers.tts.fish_audio.httpx.AsyncClient", return_value=client):
        with pytest.raises(ProviderError):
            await FishAudioTTS(config()).synthesize("測試", FEMALE, 1, tmp_path / "a.mp3")
    assert not (tmp_path / "a.mp3").exists()


@pytest.mark.asyncio
async def test_setup_and_voices(tmp_path):
    provider = get_tts(AppConfig(tts=config()))
    assert [v.id for v in await provider.list_voices()] == [FEMALE, MALE]
    cfg = config()
    cfg.fish_audio.api_key = ""
    with pytest.raises(ProviderError, match="API Key"):
        await FishAudioTTS(cfg).synthesize("測試", FEMALE, 1, tmp_path / "a.mp3")
    cfg.fish_audio.male_reference_id = ""
    with pytest.raises(ProviderError, match="Voice ID"):
        FishAudioTTS(cfg).reference_id(MALE)


@pytest.mark.asyncio
@pytest.mark.parametrize("status,message", [(402, "API 額度與網站平台額度分開計算"),
                                           (401, "API Key 無效或已失效")])
async def test_actionable_errors(tmp_path, status, message):
    client = httpx.AsyncClient(transport=httpx.MockTransport(
        lambda request: httpx.Response(status, json={"message": "private server detail"})))
    with patch("easyaivideo.providers.tts.fish_audio.httpx.AsyncClient", return_value=client):
        with pytest.raises(ProviderError, match=message) as error:
            await FishAudioTTS(config()).synthesize("測試", FEMALE, 1, tmp_path / "a.mp3")
    assert "private server detail" not in str(error.value)


def test_secrets_and_legacy_config(tmp_path):
    manager = ConfigManager(tmp_path / "config.yaml")
    assert manager.get().tts.provider == "edge"
    manager.update({"tts": config().model_dump()})
    assert manager.masked()["tts"]["fish_audio"]["api_key"] == "***"
    manager.update(manager.masked())
    assert manager.get().tts.fish_audio.api_key == "test-key"


def test_character_gender():
    from easyaivideo.services.series import pick_voice

    with patch("easyaivideo.services.series.config_manager.get", return_value=AppConfig(tts=config())):
        assert pick_voice("zh-TW", "male", FEMALE) == MALE
        assert pick_voice("zh-TW", "female", MALE) == FEMALE
        assert pick_voice("zh-TW", "auto", MALE) == MALE


@pytest.mark.asyncio
async def test_connection_failure(tmp_path):
    def handler(request):
        raise httpx.ConnectError("offline", request=request)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    with patch("easyaivideo.providers.tts.fish_audio.httpx.AsyncClient", return_value=client):
        with pytest.raises(ProviderError, match="Fish Audio"):
            await FishAudioTTS(config()).synthesize("測試", FEMALE, 1, tmp_path / "a.mp3")
    assert not (tmp_path / "a.mp3").exists()
