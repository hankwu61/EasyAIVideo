from pathlib import Path
import pytest

from easyaivideo.services.slide_service import (
    clean_speech_text,
    parse_speaker_guide,
    calculate_proportional_subtitles,
    format_srt_timestamp,
    generate_presentation_srt,
    extract_pptx_slides_data,
)


def test_clean_speech_text():
    raw = (
        "# Slide 1: Welcome\n"
        "> 「各位同仁好，今天非常高興和大家分享這個主題：**AI Agent**。\n"
        "過去只要提到`軟體開發` -> 大家第一反應是難度很高 => 但現在不同了！🚀🎯\n"
        "- 重點一：自動化\n"
        "- 重點二：無程式碼\n"
        "```python\nprint('hello')\n```\n"
    )
    cleaned = clean_speech_text(raw)
    assert "#" not in cleaned
    assert ">" not in cleaned
    assert "**" not in cleaned
    assert "`" not in cleaned
    assert "```" not in cleaned
    assert "🚀" not in cleaned
    assert "🎯" not in cleaned
    assert "，接著" in cleaned
    assert "，也就是" in cleaned
    assert "重點一：自動化" in cleaned


def test_parse_speaker_guide():
    guide_md = (
        "### Slide 1: 開場介紹\n"
        "- **預估時長**：01:30\n"
        "- **核心目標**：抓住聽眾注意力\n\n"
        "#### 【畫面動作】\n"
        "游標停留在封面中央。\n\n"
        "#### 【逐字稿】\n"
        "各位好，歡迎來到今天的簡報。\n\n"
        "#### 【轉場】\n"
        "接下來讓我們看第二頁。\n\n"
        "---\n\n"
        "### Slide 2: 核心架構\n\n"
        "#### 講稿內容\n"
        "這是我們的系統架構說明。\n"
    )
    slides = parse_speaker_guide(guide_md)
    assert len(slides) == 2
    assert slides[0]["slide_num"] == 1
    assert slides[0]["title"] == "開場介紹"
    assert "歡迎來到今天的簡報" in slides[0]["clean_text"]
    # Transition, action, and metadata must NOT be in clean_text (narration)
    assert "接下來讓我們看第二頁" not in slides[0]["clean_text"]
    assert "游標停留在封面中央" not in slides[0]["clean_text"]
    assert "抓住聽眾注意力" not in slides[0]["clean_text"]
    assert "01:30" not in slides[0]["clean_text"]
    # But should be captured in their respective metadata fields
    assert slides[0]["target_duration"] == 90.0
    assert "抓住聽眾注意力" in slides[0]["goal"]
    assert "游標停留在封面中央" in slides[0]["action"]
    assert "接下來讓我們看第二頁" in slides[0]["transition"]
    assert slides[0]["calibrated_speed"] is not None

    assert slides[1]["slide_num"] == 2
    assert "系統架構說明" in slides[1]["clean_text"]


def test_parse_20_slides_example_guide():
    example_path = Path("docs/SPEAKER_GUIDE_20_SLIDES_EXAMPLE.md")
    assert example_path.exists()
    content = example_path.read_text(encoding="utf-8")
    slides = parse_speaker_guide(content)
    assert len(slides) == 20

    # Verify that clean_text on all 20 slides contains pure spoken script and NO metadata/headers
    forbidden_tokens = ["畫面動作", "轉場", "預估時長", "核心目標", "投影片資訊", "【", "】"]
    for s in slides:
        assert s["clean_text"], f"Slide {s['slide_num']} has empty clean_text"
        for tok in forbidden_tokens:
            assert tok not in s["clean_text"], (
                f"Slide {s['slide_num']} clean_text should not contain '{tok}', but got:\n{s['clean_text'][:200]}"
            )
        # Verify goals and calibrated speeds are parsed
        if s["slide_num"] == 1:
            assert "各位夥伴" in s["clean_text"]
            assert s["goal"] != ""
            assert s["target_duration"] == 90.0
            assert s["calibrated_speed"] is not None


def test_calculate_proportional_subtitles():
    text = "各位同仁好。今天我們來探討簡報影音自動化的實踐方案！"
    subs = calculate_proportional_subtitles(text, 5.0)
    assert len(subs) == 2
    assert subs[0]["start"] == 0.0
    assert subs[-1]["end"] == 5.0
    assert "各位同仁好。" in subs[0]["text"]
    assert "今天我們來探討簡報影音自動化的實踐方案！" in subs[1]["text"]


def test_format_srt_timestamp():
    assert format_srt_timestamp(0.0) == "00:00:00,000"
    assert format_srt_timestamp(65.432) == "00:01:05,432"
    assert format_srt_timestamp(3661.005) == "01:01:01,005"


def test_generate_presentation_srt(tmp_path: Path):
    subtitles_data = [
        {
            "slide_start": 0.0,
            "sentences": [
                {"start": 0.0, "end": 2.5, "text": "第一頁開場白。"},
            ],
        },
        {
            "slide_start": 5.0,
            "sentences": [
                {"start": 0.0, "end": 3.0, "text": "第二頁核心內容。"},
            ],
        },
    ]
    out_file = tmp_path / "test.srt"
    generate_presentation_srt(subtitles_data, out_file, pre_pad=0.4)
    content = out_file.read_text(encoding="utf-8")
    assert "1" in content
    assert "00:00:00,400 --> 00:00:02,900" in content
    assert "第一頁開場白。" in content
    assert "2" in content
    assert "00:00:05,400 --> 00:00:08,400" in content
    assert "第二頁核心內容。" in content


def test_extract_pptx_slides_data():
    sample_pptx = Path("D:/AgentSlide/Empowering_Non_Programmers_AI_Agent_IDEs.pptx")
    if sample_pptx.exists():
        data = extract_pptx_slides_data(sample_pptx)
        assert len(data) == 20
        assert data[0]["slide_num"] == 1
        assert "Empowering Non-Programmers" in data[0]["clean_text"] or len(data[0]["clean_text"]) > 20


@pytest.mark.asyncio
async def test_create_slide_project_endpoint():
    from httpx import AsyncClient, ASGITransport
    from easyaivideo.main import app
    from easyaivideo.db import db
    from easyaivideo.deps import projects

    await db.init()
    sample_pptx = Path("D:/AgentSlide/Empowering_Non_Programmers_AI_Agent_IDEs.pptx")
    if not sample_pptx.exists():
        pytest.skip("Sample PPTX not found")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        files = {
            "pptx_file": (
                "presentation.pptx",
                sample_pptx.read_bytes(),
                "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            ),
        }
        data = {
            "title": "測試簡報影片",
            "auto_start": "false",
            "aspect_ratio": "16:9",
            "voice": "zh-TW-YunJheNeural",
        }
        resp = await client.post("/api/projects/slide", files=files, data=data)
        assert resp.status_code == 201, resp.text
        proj = resp.json()
        assert proj["input_mode"] == "slide"
        assert proj["aspect_ratio"] == "16:9"
        assert len(proj["scenes"]) == 20
        assert proj["scenes"][0]["image_url"] is not None
        assert len(proj["scenes"][0]["narration"]) > 10

        # Clean up test project
        await projects.delete(proj["id"])
