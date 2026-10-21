from easyaivideo.models import Character, Project, Scene
from easyaivideo.prompts import episode_script_prompt, image_prompts_prompt, topic_script_prompt
from easyaivideo.services.pipeline import image_prompt_for, video_prompt_for


def test_prompts_include_continuity_rules():
    t_prompt = topic_script_prompt("Cyberpunk Adventure", 5, "zh-TW", "cinematic anime")
    assert "VISUAL CONTINUITY" in t_prompt
    assert "preceding scene" in t_prompt.lower()
    assert "CHARACTER CONSISTENCY" in t_prompt
    assert "MOTION CONTINUITY" in t_prompt

    i_prompt = image_prompts_prompt(["Segment 1", "Segment 2"], "zh-TW", "cinematic anime")
    assert "CONTINUITY" in i_prompt
    assert "previous segment" in i_prompt.lower()

    e_prompt_drama = episode_script_prompt(
        mode="drama",
        excerpt="Hello world",
        language="zh-TW",
        target_seconds=30,
        style_prompt="cinematic anime",
        overview=None,
        characters=[],
        locations=[],
        episode_title="Ep 1",
    )
    assert "VISUAL CONTINUITY" in e_prompt_drama
    assert "MOTION CONTINUITY" in e_prompt_drama

    e_prompt_narr = episode_script_prompt(
        mode="narration",
        excerpt="Hello world",
        language="zh-TW",
        target_seconds=30,
        style_prompt="cinematic anime",
        overview=None,
        characters=[],
        locations=[],
        episode_title="Ep 1",
    )
    assert "VISUAL CONTINUITY" in e_prompt_narr
    assert "MOTION CONTINUITY" in e_prompt_narr


def test_image_prompt_for_continuity():
    s0 = Scene(id="s0", index=0, image_prompt="Hero standing on a cliff at sunset", video_prompt="Slow zoom in")
    s1 = Scene(id="s1", index=1, image_prompt="Hero draws a sword and looks forward", video_prompt="Pan right to follow sword")

    # Scene 0 has no preceding scene, should keep prompt clean
    res0 = image_prompt_for(s0, "cinematic anime", None, None)
    assert "Hero standing on a cliff at sunset" in res0
    assert "continuity with preceding scene" not in res0

    # Scene 1 has s0 as preceding scene, should inject visual continuity
    res1 = image_prompt_for(s1, "cinematic anime", s0, s0)
    assert "Hero draws a sword and looks forward" in res1
    assert "visual continuity with preceding scene" in res1
    assert "identical character facial features" in res1


def test_video_prompt_for_continuity():
    s0 = Scene(id="s0", index=0, image_prompt="Hero standing on cliff", video_prompt="Slow camera push-in toward character face")
    s1 = Scene(id="s1", index=1, image_prompt="Hero looks up", video_prompt="Camera tilts up toward the sky")

    # Scene 0
    v0 = video_prompt_for(s0, "cinematic anime", None)
    assert "Slow camera push-in toward character face" in v0
    assert "smoothly continuing motion" not in v0

    # Scene 1 continuing from s0
    v1 = video_prompt_for(s1, "cinematic anime", s0)
    assert "Camera tilts up toward the sky" in v1
    assert "smoothly continuing motion and camera direction from preceding scene" not in v1
