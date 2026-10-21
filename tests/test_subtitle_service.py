from pathlib import Path
import pytest
from httpx import ASGITransport, AsyncClient

from easyaivideo.main import app
from easyaivideo.db import db
from easyaivideo.deps import projects
from easyaivideo.models import ProjectCreate
from easyaivideo.services.subtitle_service import (
    SubtitleCue,
    generate_cues_from_project_scenes,
    merge_cues,
    parse_srt_content,
    serialize_cues_to_srt,
    split_cue,
)


def test_srt_parse_and_serialize():
    raw_srt = (
        "1\n"
        "00:00:01,000 --> 00:00:03,500\n"
        "好的好的，我們前幾天就去了。\n\n"
        "2\n"
        "00:00:03,600 --> 00:00:06,200\n"
        "台南的奇美博物館\n\n"
        "3\n"
        "00:00:06,300 --> 00:00:08,800\n"
        "然後去看了這個埃及之法老特展\n"
    )
    cues = parse_srt_content(raw_srt)
    assert len(cues) == 3
    assert cues[0].id == 1
    assert cues[0].start == 1.0
    assert cues[0].end == 3.5
    assert "好的好的" in cues[0].text
    assert cues[1].id == 2
    assert cues[1].start == 3.6
    assert "奇美博物館" in cues[1].text

    serialized = serialize_cues_to_srt(cues)
    assert "00:00:01,000 --> 00:00:03,500" in serialized
    assert "台南的奇美博物館" in serialized


def test_split_and_merge_cues():
    cues = [
        SubtitleCue(id=1, start=0.0, end=4.0, text="前面這是一句很長的句子"),
        SubtitleCue(id=2, start=4.5, end=7.0, text="接著是第二句話"),
    ]
    # Split cue 1 at 2.0s
    split_result = split_cue(cues, cue_id=1, split_time=2.0)
    assert len(split_result) == 3
    assert split_result[0].start == 0.0
    assert split_result[0].end == 2.0
    assert split_result[1].start == 2.0
    assert split_result[1].end == 4.0

    # Merge cue 1 and 2
    merged_result = merge_cues(split_result, cue_id1=1, cue_id2=2)
    assert len(merged_result) == 2
    assert merged_result[0].start == 0.0
    assert merged_result[0].end == 4.0


@pytest.mark.asyncio
async def test_subtitles_api_endpoints():
    await db.init()
    # Create test project
    proj = await projects.create(ProjectCreate(title="測試字幕專案", topic="測試", input_mode="topic"))

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # GET subtitles initially (empty or generated)
        resp = await client.get(f"/api/projects/{proj.id}/subtitles")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

        # PUT subtitles
        new_cues = [
            {"id": 1, "start": 0.0, "end": 2.5, "text": "第一句測試字幕"},
            {"id": 2, "start": 2.6, "end": 5.0, "text": "第二句測試字幕"},
        ]
        resp = await client.put(f"/api/projects/{proj.id}/subtitles", json={"cues": new_cues})
        assert resp.status_code == 200
        saved = resp.json()
        assert len(saved) == 2
        assert saved[0]["text"] == "第一句測試字幕"

        # GET again to verify persistence
        resp2 = await client.get(f"/api/projects/{proj.id}/subtitles")
        assert resp2.status_code == 200
        cues_fetched = resp2.json()
        assert len(cues_fetched) == 2
        assert cues_fetched[1]["text"] == "第二句測試字幕"

        # Synthesize cue test
        syn_resp = await client.post(
            f"/api/projects/{proj.id}/synthesize-cue",
            json={"text": "測試單句配音"},
        )
        assert syn_resp.status_code == 200
        syn_data = syn_resp.json()
        assert syn_data["ok"] is True
        assert "audio_url" in syn_data

    # Cleanup
    await projects.delete(proj.id)
