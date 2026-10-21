"""Forensic helpers for the video clone -> MiniMax H3 flow (no ffmpeg / network needed)."""

import numpy as np

from easyaivideo.services.forensic_service import (
    ForensicService,
    Transition,
    color_histograms,
    detect_breath_gaps,
    detect_soft_transitions,
    detect_transitions,
    estimate_pitch,
    localize,
    onset_regularity,
    parse_scene_scores,
    plan_segments,
)
from easyaivideo.services.h3_prompt_tools import request_duration, timestamps, validate_h3_prompt
from easyaivideo.prompts import analyze_h3_segment_prompt, analyze_video_h3_overview_prompt, h3_reference_docs

# Measured on the real 56.68 s reference clip (qq.mp4)
QQ_GAPS = [
    (2.68, 2.92), (3.54, 3.78), (5.46, 5.78), (7.72, 8.0), (9.92, 10.28), (11.4, 11.64), (12.86, 13.16), (15.4, 15.66),
    (17.32, 17.68), (18.78, 19.14), (20.9, 21.24), (23.48, 23.72), (25.44, 25.8), (27.26, 27.56), (28.82, 29.06),
    (32.76, 33.04), (34.0, 34.2), (35.78, 36.1), (37.36, 37.62), (39.56, 39.8), (40.86, 41.14), (42.3, 42.58),
    (44.92, 45.16), (47.46, 47.7), (50.28, 50.7), (52.54, 52.88), (54.48, 54.76), (56.14, 56.66),
]
QQ_TRANSITIONS = [
    Transition(7.125, "soft", 0.55), Transition(14.75, "soft", 0.4), Transition(16.583, "cut", 0.62),
    Transition(19.833, "cut", 0.51), Transition(23.0, "soft", 0.47), Transition(23.75, "cut", 0.74),
    Transition(28.0, "soft", 0.3), Transition(30.625, "soft", 0.43), Transition(32.75, "cut", 0.31),
    Transition(38.0, "soft", 0.35), Transition(46.75, "soft", 0.47), Transition(51.375, "soft", 0.32),
]


def test_plan_segments_matches_manual_forensics():
    plans = plan_segments(56.68, QQ_GAPS, QQ_TRANSITIONS)
    assert [round(p.start, 2) for p in plans] == [0.0, 13.01, 23.6, 32.9, 47.58]
    assert all(p.duration <= 15.0 + 1e-6 for p in plans)
    assert all(p.duration >= 2.0 for p in plans)
    assert plans[-1].end == 56.68
    assert plans[1].reason == "breath+cut"  # 23.48-23.72 gap next to the 23.75 hard cut


def test_plan_segments_short_clip_is_single_part():
    plans = plan_segments(12.0, [(5.0, 5.3)], [])
    assert len(plans) == 1 and plans[0].start == 0.0 and plans[0].end == 12.0


def test_plan_segments_fallback_without_candidates():
    plans = plan_segments(40.0, [], [])
    assert all(p.duration <= 15.0 for p in plans)
    assert plans[-1].end == 40.0
    assert all(p.duration >= 2.0 for p in plans)


def test_parse_scene_scores_and_hard_cuts():
    text = "\n".join(
        f"frame:{i} pts:{i} pts_time:{i / 24:.6f}\nlavfi.scene_score={0.6 if i == 120 else 0.01:.6f}" for i in range(240)
    )
    times, scores = parse_scene_scores(text)
    assert len(times) == 240 and len(scores) == 240
    cuts = [t for t in detect_transitions(times, scores) if t.kind == "cut"]
    assert len(cuts) == 1 and abs(cuts[0].time - 5.0) < 0.01


def test_soft_transition_from_colour_change():
    fps = 8
    red = np.zeros((40, 16, 9, 3), np.uint8)
    red[..., 0] = 220
    blue = np.zeros((40, 16, 9, 3), np.uint8)
    blue[..., 2] = 220
    # 0.5 s cross-dissolve between the two scenes
    mix = np.stack([(red[0] * (1 - a) + blue[0] * a).astype(np.uint8) for a in np.linspace(0, 1, 4)])
    frames = np.concatenate([red, mix, blue])
    soft = detect_soft_transitions(color_histograms(frames), fps, cuts=[])
    assert len(soft) == 1
    assert abs(soft[0].time - 40 / fps) < 0.6
    # a hard cut at the same spot suppresses the soft candidate
    assert detect_soft_transitions(color_histograms(frames), fps, cuts=[soft[0].time]) == []


def test_breath_gaps_and_pitch():
    sr = 22050
    t = np.arange(int(sr * 1.0)) / sr
    voiced = 0.3 * np.sin(2 * np.pi * 220 * t)
    silence = np.zeros(int(sr * 0.4))
    x = np.concatenate([voiced, silence, voiced])
    gaps = detect_breath_gaps(x, sr)
    assert len(gaps) == 1 and abs(gaps[0][0] - 1.0) < 0.05 and abs(gaps[0][1] - 1.4) < 0.05
    pitch = estimate_pitch(x, sr)
    assert pitch is not None and abs(pitch - 220) < 10


def test_onset_regularity_flags_irregular_rhythm():
    regular = [{"time": i * 0.5, "grade": "S"} for i in range(10)]
    irregular = [{"time": t, "grade": "H"} for t in (0.1, 0.3, 1.9, 2.0, 4.8, 5.0, 9.0)]
    assert onset_regularity(regular) == 0.0
    assert onset_regularity(irregular) > 0.8


def test_compose_summary_segment_local_times():
    text = ForensicService.compose_summary(
        duration=56.68, width=1080, height=1920, fps=24.0, n_frames=113, has_audio=True, tempo=84.7, has_bgm=False,
        onset_cv=0.8, band_e={"low": 1, "mid": 1, "hi": 0}, rms_env=[(14.0, 0.1), (20.0, 0.2)],
        onsets=[{"time": 16.45, "grade": "S"}, {"time": 40.0, "grade": "S"}], transitions=QQ_TRANSITIONS,
        breath_gaps=QQ_GAPS, pitch_hz=229.7, offset=13.01, end=23.6,
    )
    assert "SEGMENT-LOCAL" in text
    assert "3.57s" in text  # hard cut 16.583 - 13.01
    assert "3.44S" in text  # onset 16.45 - 13.01
    assert "40.00" not in text and "27.0" not in text  # onset outside the part is dropped
    assert "FALSE DETECTION" in text and "female" in text
    assert localize([1.0, 14.0, 30.0], 13.0, 20.0) == [1.0]


def test_request_duration_and_validation():
    assert request_duration(13.01) == 13
    assert request_duration(10.59) == 11
    assert request_duration(2.5) == 4
    assert request_duration(14.9, "MiniMax-H3-Max") == 15
    good = (
        "subject_definitions:\n<Subject 1> is a woman.\nsummary:\nx\nretention_analysis:\nx\ndetailed_description:\n"
        "[Shot 1] A medium shot. At 00:01.50 she smiles.\n[Shot 2] At 00:04.00, the camera cuts to a close-up.\n"
        "overall_soundscape:\nroom tone\nnon_diegetic_music:\nN/A - explicit silence."
    )
    assert validate_h3_prompt(good, duration=5.0) == []
    assert timestamps(good) == [1.5, 4.0]
    bad = good.replace("[Shot 1] A medium shot.", "[Shot 1] At 00:00.00 a medium shot 貓咪.").replace("00:04.00", "00:09.00")
    warnings = validate_h3_prompt(bad, duration=5.0)
    assert any("中文" in w for w in warnings)
    assert any("[Shot 1]" in w for w in warnings)
    assert any("超出段長" in w for w in warnings)
    assert validate_h3_prompt("x" * 7001)[0].startswith("提示詞 7001")


def test_h3_prompt_builders():
    assert "shot-syntax.md" in h3_reference_docs()
    ov = analyze_video_h3_overview_prompt(
        language="zh-TW", duration_seconds=56.68, aspect_ratio="9:16", dossier="DOSSIER",
        segments=[{"index": 0, "start": 0.0, "end": 13.0, "duration": 13.0, "reason": "breath"}], n_images=4, n_pictures=1,
    )
    assert "TASK: VIDEO_TO_H3_OVERVIEW" in ov and "post_text_overlays" in ov and "<Picture 1>" in ov
    seg = analyze_h3_segment_prompt(
        language="zh-TW", part_index=1, part_count=3, seg_start=13.0, seg_end=23.6, request_duration=11,
        aspect_ratio="9:16", local_dossier="LOCAL", film_type="C_montage", style_line="The target video uses ...",
        subjects_block="<Subject 1> is a woman.", prev_hand_off="She hugs the cat.", n_pictures=0,
    )
    assert "PART 2 of 3" in seg
    assert "OPEN ON THE HAND-OFF STATE" in seg and "She hugs the cat." in seg
    assert "<Video 1>" in seg and "<Audio 1>" in seg
    assert "CONTINUATION STATE" in seg
    last = analyze_h3_segment_prompt(
        language="zh-TW", part_index=2, part_count=3, seg_start=23.6, seg_end=30.0, request_duration=7,
        aspect_ratio="9:16", local_dossier="LOCAL", film_type="C_montage", style_line="", subjects_block="",
        prev_hand_off="", h3_mode="t2va", include_refs=False,
    )
    assert "LAST part" in last and "14-FIELD" in last and "text only" in last
