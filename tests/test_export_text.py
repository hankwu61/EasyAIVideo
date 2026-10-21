import zipfile
import io
import pytest
from httpx import AsyncClient, ASGITransport

from easyaivideo.main import app
from easyaivideo.models import Line, Project, Scene
from easyaivideo.routers.projects import (
    _generate_video_prompts_text,
    _generate_image_prompts_text,
    _generate_narration_text,
    _generate_full_script_text,
)


def _make_dummy_project():
    return Project(
        id="proj_test_export",
        title="Cyberpunk Adventure",
        scenes=[
            Scene(
                id="s1",
                index=0,
                narration="In a distant neon future.",
                image_prompt="Cyberpunk city with rainy streets",
                video_prompt="Slow dolly forward through rain",
            ),
            Scene(
                id="s2",
                index=1,
                narration="Heroes unite.",
                image_prompt="Two warriors standing back to back",
                video_prompt="360 camera orbit around warriors",
                lines=[
                    Line(speaker="Alice", text="Are you ready?"),
                    Line(speaker="Bob", text="Always."),
                ],
            ),
        ],
    )


def test_generate_video_prompts_text():
    p = _make_dummy_project()
    text = _generate_video_prompts_text(p)
    assert "Cyberpunk Adventure" in text
    assert "第 1 場 (Scene 1):" in text
    assert "Slow dolly forward through rain" in text
    assert "第 2 場 (Scene 2):" in text
    assert "360 camera orbit around warriors" in text


def test_generate_image_prompts_text():
    p = _make_dummy_project()
    text = _generate_image_prompts_text(p)
    assert "Cyberpunk Adventure" in text
    assert "Cyberpunk city with rainy streets" in text
    assert "Two warriors standing back to back" in text


def test_generate_narration_text():
    p = _make_dummy_project()
    text = _generate_narration_text(p)
    assert "In a distant neon future." in text
    assert "Alice: Are you ready?" in text
    assert "Bob: Always." in text


def test_generate_full_script_text():
    p = _make_dummy_project()
    text = _generate_full_script_text(p)
    assert "【專案名稱】Cyberpunk Adventure" in text
    assert "【圖片提示詞】" in text
    assert "【影片提示詞】" in text
    assert "【旁白 / 台詞】" in text
    assert "Slow dolly forward through rain" in text


@pytest.mark.asyncio
async def test_export_endpoints_http():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Test on existing project
        r = await ac.get("/api/projects/proj_c4699202/export/text?kind=video_prompts")
        assert r.status_code == 200
        assert "text/plain" in r.headers["content-type"]
        assert "影片提示詞" in r.text

        r_img = await ac.get("/api/projects/proj_c4699202/export/text?kind=image_prompts")
        assert r_img.status_code == 200
        assert "圖片提示詞" in r_img.text

        r_narr = await ac.get("/api/projects/proj_c4699202/export/text?kind=narration")
        assert r_narr.status_code == 200
        assert "旁白台詞" in r_narr.text

        from urllib.parse import unquote

        r_script = await ac.get("/api/projects/proj_c4699202/export/text?kind=script")
        assert r_script.status_code == 200
        assert "完整腳本提示詞" in unquote(r_script.headers.get("content-disposition", ""))

        r_zip = await ac.get("/api/projects/proj_c4699202/export/texts.zip")
        assert r_zip.status_code == 200
        assert r_zip.headers["content-type"] == "application/zip"
        
        zf = zipfile.ZipFile(io.BytesIO(r_zip.content))
        names = zf.namelist()
        assert "01_影片提示詞.txt" in names
        assert "02_圖片提示詞.txt" in names
        assert "03_旁白.txt" in names
        assert "04_完整腳本提示詞.txt" in names
