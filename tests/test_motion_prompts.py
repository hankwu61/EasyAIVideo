import pytest
from easyaivideo.models import Scene
from easyaivideo.prompts import topic_script_prompt, image_prompts_prompt, video_motion_rules
from easyaivideo.services.pipeline import video_prompt_for


def test_i2v_fallback_does_not_copy_visuals():
    scene = Scene(id="s1", image_prompt="red silk dress, golden light, ornate palace")
    prompt = video_prompt_for(scene, "cinematic lighting")
    assert "red silk" not in prompt
    assert "cinematic lighting" not in prompt
    assert "slow" not in prompt
    assert "camera stays fixed" in prompt


def test_authored_motion_is_preserved():
    scene = Scene(id="s1", video_prompt="Track left as the person walks.")
    assert video_prompt_for(scene, "anime") == scene.video_prompt


def test_mode_specific_fallback():
    scene = Scene(id="s1", image_prompt="A boat at sea")
    assert "ending frame" not in video_prompt_for(scene, "")
    assert "then" in video_prompt_for(scene, "", video_mode="keyframes")
    assert "finally" in video_prompt_for(scene, "", video_mode="keyframes")
    assert "A boat at sea" in video_prompt_for(scene, "", video_mode="t2v")


@pytest.mark.parametrize("mode", ["i2v", "keyframes", "t2v"])
def test_script_templates_receive_mode_rules(mode):
    for prompt in (topic_script_prompt("story", 3, "en", "anime", mode),
                   image_prompts_prompt(["story"], "en", "anime", mode)):
        assert video_motion_rules(mode) in prompt
        assert "one main action and one camera behavior" in prompt
        if mode == "keyframes":
            assert "initiation, progression, then arrival" in prompt
        elif mode == "i2v":
            assert "Do not refer to a final frame" in prompt
