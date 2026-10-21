from pathlib import Path
import json
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from easyaivideo.services.video_clone_service import (
    VideoCloneService,
    calculate_sample_timestamps,
    detect_aspect_ratio,
)
from easyaivideo.prompts import analyze_video_remake_prompt
from easyaivideo.models import Project


def test_detect_aspect_ratio():
    assert detect_aspect_ratio(1080, 1920) == "9:16"
    assert detect_aspect_ratio(720, 1280) == "9:16"
    assert detect_aspect_ratio(1920, 1080) == "16:9"
    assert detect_aspect_ratio(1280, 720) == "16:9"
    assert detect_aspect_ratio(1080, 1080) == "1:1"
    assert detect_aspect_ratio(600, 600) == "1:1"


def test_calculate_sample_timestamps():
    # Very short video (4s)
    ts_short = calculate_sample_timestamps(4.0)
    assert len(ts_short) >= 3
    assert all(0 <= t <= 4.0 for t in ts_short)

    # 15s video (default max_samples=8)
    ts_15 = calculate_sample_timestamps(15.0)
    assert 4 <= len(ts_15) <= 8
    assert ts_15 == sorted(ts_15)
    assert all(0 <= t <= 15.0 for t in ts_15)

    # 60s video
    ts_60 = calculate_sample_timestamps(60.0)
    assert len(ts_60) == 8
    assert ts_60 == sorted(ts_60)


def test_analyze_video_remake_prompt():
    prompt = analyze_video_remake_prompt("zh-TW", n_frames=5, duration_seconds=15.0)
    assert "Traditional Chinese" in prompt
    assert "5" in prompt
    assert "15.0" in prompt
    assert "scenes" in prompt
    assert "style_id" in prompt


@pytest.mark.asyncio
async def test_clone_from_video(tmp_path: Path):
    from easyaivideo.db import Database
    # Prepare dummy video file
    video_path = tmp_path / "sample.mp4"
    video_path.write_bytes(b"dummy_video_bytes")

    fake_analysis = {
        "title": "測試短影片主題",
        "theme": "科技未來",
        "style_id": "cyberpunk",
        "style_prompt": "neon lights, cyberpunk city, high contrast",
        "scenes": [
            {
                "index": 0,
                "keyframe_index": 0,
                "duration": 4.5,
                "narration": "在這個霓虹閃爍的未來世界。",
                "image_prompt": "A bustling cyberpunk metropolis at night, neon reflections",
                "video_prompt": "Camera tracking forward through flying cars and holographic ads",
            },
            {
                "index": 1,
                "keyframe_index": 1,
                "duration": 5.0,
                "narration": "科技改變了我們的一切。",
                "image_prompt": "A close up of a cyborg eyes reflecting digital code",
                "video_prompt": "Slow zoom in on the glowing mechanical eye with iris aperture shift",
            },
        ],
    }

    db = AsyncMock()
    db.save_project = AsyncMock(side_effect=lambda p: p)
    service = VideoCloneService(db)

    async def fake_extract(src, t, dest, width=768):
        dest.write_bytes(b"dummy_frame_jpeg")

    fake_vision = AsyncMock()
    fake_vision.complete_json_with_images = AsyncMock(return_value=fake_analysis)

    with patch(
        "easyaivideo.services.ffmpeg.probe_duration",
        new=AsyncMock(return_value=12.0),
    ), patch(
        "easyaivideo.services.ffmpeg.probe_dimensions",
        new=AsyncMock(return_value=(1080, 1920)),
    ), patch(
        "easyaivideo.services.ffmpeg.extract_frame",
        side_effect=fake_extract,
    ), patch(
        "easyaivideo.services.video_clone_service.get_vision",
        return_value=fake_vision,
    ):
        project = await service.clone_from_video(
            video_path=video_path,
            language="zh-TW",
            motion="ai_video",
            style_id=None,
            title_override=None,
            auto_start=False,
            generation_mode="standard",
        )

        assert isinstance(project, Project)
        assert project.title == "測試短影片主題"
        assert project.aspect_ratio == "9:16"
        assert project.style_id == "cyberpunk"
        assert project.input_mode == "video"
        assert len(project.scenes) == 2

        s1 = project.scenes[0]
        assert s1.index == 0
        assert s1.narration == "在這個霓虹閃爍的未來世界。"
        assert "cyberpunk metropolis" in s1.image_prompt
        assert "Camera tracking" in s1.video_prompt

        s2 = project.scenes[1]
        assert s2.index == 1
        assert s2.narration == "科技改變了我們的一切。"


# --------------------------------------------------------------------------- MiniMax H3 clone flow


def _fake_forensic_result(src: Path, out_dir: Path):
    from easyaivideo.services.forensic_service import ForensicAnalysisResult, Transition

    return ForensicAnalysisResult(
        duration=20.0, width=1080, height=1920, fps=24.0, has_audio=True, frame_paths=[], grid_paths=[],
        audio_path=None, spectrum_path=None, rms_envelope=[(1.0, 0.1)], band_energies={"low": 1, "mid": 1, "hi": 0},
        onsets=[{"time": 3.0, "grade": "S"}], estimated_tempo=None, tempo_stable=False, summary_text="DOSSIER",
        transitions=[Transition(9.5, "cut", 0.6)], breath_gaps=[(9.4, 9.7)], pitch_hz=220.0, onset_cv=1.0,
        has_bgm=False, source_path=src, output_dir=out_dir,
    )


@pytest.mark.asyncio
async def test_clone_from_video_h3_segments(tmp_path: Path, monkeypatch):
    from easyaivideo.providers.llm.vision import MockVision
    from easyaivideo.services import storage
    from easyaivideo.services.forensic_service import ForensicService

    monkeypatch.setattr(storage, "PROJECTS_DIR", tmp_path / "projects")
    video_path = tmp_path / "sample.mp4"
    video_path.write_bytes(b"dummy")
    pic = tmp_path / "face.png"
    pic.write_bytes(b"png")

    async def fake_probe(self, src, out_dir):
        out_dir.mkdir(parents=True, exist_ok=True)
        return _fake_forensic_result(src, out_dir)

    async def fake_cut(self, src, start, end, out_v, out_a, short_edge=720):
        out_v.parent.mkdir(parents=True, exist_ok=True)
        out_v.write_bytes(b"v")
        if out_a is not None:
            out_a.write_bytes(b"a")
        return out_v, out_a

    async def fake_frames(self, src, start, end, fps, out_dir, width=360, prefix="w"):
        return []

    async def fake_extract(src, t, dest, width=768):
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b"jpg")
        return dest

    monkeypatch.setattr(ForensicService, "run_probe", fake_probe)
    monkeypatch.setattr(ForensicService, "cut_reference_media", fake_cut)
    monkeypatch.setattr(ForensicService, "extract_window_frames", fake_frames)

    db = AsyncMock()
    db.save_project = AsyncMock(side_effect=lambda p: p)
    with patch("easyaivideo.services.ffmpeg.probe_duration", new=AsyncMock(return_value=20.0)), patch(
        "easyaivideo.services.ffmpeg.probe_dimensions", new=AsyncMock(return_value=(1080, 1920))
    ), patch("easyaivideo.services.ffmpeg.extract_frame", side_effect=fake_extract), patch(
        "easyaivideo.services.video_clone_service.get_vision", return_value=MockVision()
    ):
        project = await VideoCloneService(db).clone_from_video(
            video_path, generation_mode="minimax_h3", reference_images=[pic], use_ref_audio=True
        )

    assert project.input_mode == "video"
    assert [round(s.start, 2) for s in project.h3_segments] == [0.0, 9.55]
    assert len(project.scenes) == 2
    seg = project.h3_segments[0]
    assert seg.request_duration == 10 and seg.ref_video_path and seg.ref_audio_path and seg.first_frame_path
    assert seg.prompt.startswith("subject_definitions:")
    assert project.h3_reference_images and project.h3_reference_images[0].endswith("picture_1.png")
    assert project.subtitle_enabled is False
    assert "分段計畫" in (project.forensic_report or "")
    assert "### PART 1/2" in (project.h3_prompt or "")


@pytest.mark.asyncio
async def test_pipeline_generate_h3(tmp_path: Path, monkeypatch):
    from easyaivideo.config import config_manager
    from easyaivideo.models import H3Segment, Scene
    from easyaivideo.services import storage
    from easyaivideo.services.pipeline import Pipeline

    monkeypatch.setattr(storage, "PROJECTS_DIR", tmp_path / "projects")
    cfg = config_manager.get().model_copy(deep=True)
    cfg.video.provider = "minimax"
    cfg.video.api_key = "k"
    monkeypatch.setattr(config_manager, "get", lambda: cfg)

    pid = "proj_h3test"
    ref = storage.abs_path(f"{pid}/forensics/part_01/ref_video.mp4")
    ref.parent.mkdir(parents=True, exist_ok=True)
    ref.write_bytes(b"v")
    project = Project(
        id=pid, title="t", input_mode="video", aspect_ratio="9:16", motion="ai_video",
        h3_segments=[
            H3Segment(index=0, start=0, end=9.5, duration=9.5, request_duration=10, prompt="P1", ref_video_path=f"{pid}/forensics/part_01/ref_video.mp4"),
            H3Segment(index=1, start=9.5, end=20, duration=10.5, request_duration=11, prompt="P2", ref_video_path=f"{pid}/forensics/part_01/ref_video.mp4"),
        ],
        scenes=[Scene(id="s01", index=0), Scene(id="s02", index=1)],
    )
    requests = []

    class FakeProvider:
        name = "minimax"

        async def generate(self, req):
            requests.append(req)
            req.output_path.parent.mkdir(parents=True, exist_ok=True)
            req.output_path.write_bytes(b"raw")
            return req.output_path

    async def fake_normalize(video, duration, w, h, fps, output, crf=18):
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(b"clip")
        return output

    async def fake_concat(clips, output):
        output.write_bytes(b"final")
        return output

    db = AsyncMock()
    db.save_project = AsyncMock(side_effect=lambda p: p)
    progress = AsyncMock()
    with patch("easyaivideo.services.pipeline.get_video", return_value=FakeProvider()), patch(
        "easyaivideo.services.ffmpeg.probe_duration", new=AsyncMock(return_value=10.0)
    ), patch("easyaivideo.services.ffmpeg.normalize_clip", side_effect=fake_normalize), patch(
        "easyaivideo.services.ffmpeg.concat", side_effect=fake_concat
    ):
        result = await Pipeline(db).generate_h3(project, progress)

    assert len(requests) == 2
    assert requests[0].h3_mode == "ref2va" and requests[0].reference_videos and requests[0].ratio == "9:16"
    assert requests[1].duration == 11.0
    assert all(s.status == "done" and s.clip_path for s in result.h3_segments)
    assert result.final_video_path and result.scenes[0].video_path == result.h3_segments[0].clip_path
