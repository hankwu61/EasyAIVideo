import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from pathlib import Path
import httpx

from easyaivideo.config import ImageConfig
from easyaivideo.providers.image.openai_compat import OpenAICompatImage
from easyaivideo.providers.base import ProviderError


@pytest.mark.asyncio
async def test_openai_compat_retries_on_503(tmp_path: Path):
    cfg = ImageConfig(
        provider="openai_compat",
        api_key="test-key",
        base_url="https://fake-api.example.com/v1",
        model="test-model",
    )
    provider = OpenAICompatImage(cfg)
    output_file = tmp_path / "out.png"

    # Simulate: 1st call 503, 2nd call 200 with b64 image
    mock_503 = MagicMock(spec=httpx.Response)
    mock_503.status_code = 503
    mock_503.text = "Service Unavailable"

    mock_200 = MagicMock(spec=httpx.Response)
    mock_200.status_code = 200
    # b64 for 4 empty bytes
    mock_200.json.return_value = {"data": [{"b64_json": "AAAA"}]}

    call_count = 0

    async def mock_post(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return mock_503
        return mock_200

    with patch("httpx.AsyncClient.post", new=mock_post):
        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            res = await provider.generate(
                prompt="test prompt",
                negative_prompt="",
                width=1024,
                height=1024,
                output_path=output_file,
            )
            assert res == output_file
            assert call_count == 2
            assert mock_sleep.await_count == 1
            assert output_file.exists()


@pytest.mark.asyncio
async def test_openai_compat_fails_after_max_retries(tmp_path: Path):
    cfg = ImageConfig(
        provider="openai_compat",
        api_key="test-key",
        base_url="https://fake-api.example.com/v1",
        model="test-model",
    )
    provider = OpenAICompatImage(cfg)
    output_file = tmp_path / "out.png"

    mock_503 = MagicMock(spec=httpx.Response)
    mock_503.status_code = 503
    mock_503.text = "Service Unavailable"

    call_count = 0

    async def mock_post(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        return mock_503

    with patch("httpx.AsyncClient.post", new=mock_post):
        with patch("asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(ProviderError, match="Image request rejected after 4 attempts"):
                await provider.generate(
                    prompt="test prompt",
                    negative_prompt="",
                    width=1024,
                    height=1024,
                    output_path=output_file,
                )
            assert call_count == 4


@pytest.mark.asyncio
async def test_openai_compat_falls_back_to_t2i_when_ref_queue_full(tmp_path: Path):
    cfg = ImageConfig(
        provider="openai_compat",
        api_key="test-key",
        base_url="https://fake-api.example.com/v1",
        model="agnes-image-2.5-flash",
        use_references=True,
    )
    provider = OpenAICompatImage(cfg)
    output_file = tmp_path / "out.png"
    ref_image = tmp_path / "ref.png"
    ref_image.write_bytes(b"PNGDATA")

    mock_503 = MagicMock(spec=httpx.Response)
    mock_503.status_code = 503
    mock_503.text = '{"error":{"message":"image queue is full, please retry later"}}'

    mock_200 = MagicMock(spec=httpx.Response)
    mock_200.status_code = 200
    mock_200.json.return_value = {"data": [{"b64_json": "AAAA"}]}

    posted_bodies = []

    async def mock_post(*args, **kwargs):
        body = kwargs.get("json", {})
        posted_bodies.append(body)
        if "extra_body" in body and "image" in body["extra_body"]:
            return mock_503
        return mock_200

    with patch("httpx.AsyncClient.post", new=mock_post):
        res = await provider.generate(
            prompt="test prompt",
            negative_prompt="",
            width=1024,
            height=1024,
            output_path=output_file,
            reference_images=[ref_image],
        )
        assert res == output_file
        assert len(posted_bodies) == 2
        # First call contained reference images
        assert "extra_body" in posted_bodies[0]
        # Second call stripped reference images (pure text-to-image fallback)
        assert "extra_body" not in posted_bodies[1] or "image" not in posted_bodies[1].get("extra_body", {})
        assert output_file.exists()

