"""Static preset data exposed to the UI."""

from __future__ import annotations

ASPECT_RATIOS = [
    {"id": "9:16", "label": "直式 9:16 (1080×1920)", "width": 1080, "height": 1920},
    {"id": "16:9", "label": "橫式 16:9 (1920×1080)", "width": 1920, "height": 1080},
    {"id": "1:1", "label": "方形 1:1 (1080×1080)", "width": 1080, "height": 1080},
]

LANGUAGES = [
    {"id": "zh-TW", "label": "繁體中文"},
    {"id": "zh-CN", "label": "简体中文"},
    {"id": "en", "label": "English"},
    {"id": "ja", "label": "日本語"},
    {"id": "ko", "label": "한국어"},
]

LANGUAGE_NAMES = {
    "zh-TW": "Traditional Chinese (繁體中文, Taiwan usage)",
    "zh-CN": "Simplified Chinese (简体中文)",
    "en": "English",
    "ja": "Japanese",
    "ko": "Korean",
}

MOTIONS = [
    {"id": "kenburns", "label": "Ken Burns 動態鏡頭"},
    {"id": "static", "label": "靜態圖片"},
    {"id": "ai_video", "label": "AI 影片生成（Agnes / ComfyUI）"},
]

VIDEO_MODES = [
    {"id": "i2v", "label": "圖生影片（場景圖為首幀）"},
    {"id": "t2v", "label": "文生影片（只用提示詞）"},
    {"id": "keyframes", "label": "首尾幀（下一場景圖為尾幀）"},
]

CONTENT_MODES = [
    {"id": "narration", "label": "旁白解說"},
    {"id": "drama", "label": "劇情演繹（角色對白）"},
]

KINDS = [
    {"id": "single", "label": "短影片（主題／文稿）"},
    {"id": "series", "label": "長文／小說 → 分集影片"},
]

INPUT_MODES = [
    {"id": "topic", "label": "輸入主題，AI 撰寫腳本"},
    {"id": "script", "label": "使用我的文稿（自動分段）"},
]

LLM_PRESETS = [
    {"id": "openai", "label": "OpenAI", "base_url": "https://api.openai.com/v1", "model": "gpt-4o-mini"},
    {"id": "deepseek", "label": "DeepSeek", "base_url": "https://api.deepseek.com", "model": "deepseek-chat"},
    {"id": "qwen", "label": "Qwen (DashScope)", "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1", "model": "qwen-plus"},
    {"id": "moonshot", "label": "Moonshot", "base_url": "https://api.moonshot.cn/v1", "model": "moonshot-v1-8k"},
    {"id": "ollama", "label": "Ollama (local)", "base_url": "http://localhost:11434/v1", "model": "llama3.2"},
    {"id": "lmstudio", "label": "LM Studio (local)", "base_url": "http://localhost:1234/v1", "model": "local-model"},
]

STYLES = [
    {"id": "cinematic", "label": "電影感寫實", "prompt": "cinematic photograph, dramatic natural lighting, shallow depth of field, ultra detailed, 35mm film look"},
    {"id": "anime", "label": "日系動畫", "prompt": "high quality anime illustration, clean line art, vibrant colors, detailed background, studio quality"},
    {"id": "watercolor", "label": "水彩插畫", "prompt": "soft watercolor illustration, gentle brush strokes, pastel palette, paper texture, storybook style"},
    {"id": "flat", "label": "扁平向量", "prompt": "flat vector illustration, minimal shapes, bold colors, clean composition, modern infographic style"},
    {"id": "3d", "label": "3D 卡通", "prompt": "3D rendered cartoon scene, Pixar style, soft global illumination, cute proportions, highly detailed"},
    {"id": "sketch", "label": "黑白線稿", "prompt": "minimalist black and white line sketch, simple strokes, hand drawn, white background"},
    {"id": "cyberpunk", "label": "賽博龐克", "prompt": "cyberpunk city aesthetic, neon lights, rain reflections, futuristic, high contrast, cinematic"},
    {"id": "photo", "label": "商品攝影", "prompt": "professional product photography, studio lighting, clean background, sharp focus, commercial quality"},
]

# Curated Edge TTS voices (id, display name, locale, gender)
EDGE_VOICES = [
    ("zh-TW-HsiaoChenNeural", "曉臻 (女)", "zh-TW", "Female"),
    ("zh-TW-HsiaoYuNeural", "曉雨 (女)", "zh-TW", "Female"),
    ("zh-TW-YunJheNeural", "雲哲 (男)", "zh-TW", "Male"),
    ("zh-CN-XiaoxiaoNeural", "晓晓 (女)", "zh-CN", "Female"),
    ("zh-CN-XiaoyiNeural", "晓伊 (女)", "zh-CN", "Female"),
    ("zh-CN-YunxiNeural", "云希 (男)", "zh-CN", "Male"),
    ("zh-CN-YunjianNeural", "云健 (男)", "zh-CN", "Male"),
    ("zh-CN-YunyangNeural", "云扬 (男, 新聞)", "zh-CN", "Male"),
    ("zh-HK-HiuGaaiNeural", "曉佳 (女, 粵語)", "zh-HK", "Female"),
    ("zh-HK-WanLungNeural", "雲龍 (男, 粵語)", "zh-HK", "Male"),
    ("en-US-AriaNeural", "Aria (F)", "en-US", "Female"),
    ("en-US-JennyNeural", "Jenny (F)", "en-US", "Female"),
    ("en-US-GuyNeural", "Guy (M)", "en-US", "Male"),
    ("en-US-ChristopherNeural", "Christopher (M)", "en-US", "Male"),
    ("en-GB-SoniaNeural", "Sonia (F)", "en-GB", "Female"),
    ("en-GB-RyanNeural", "Ryan (M)", "en-GB", "Male"),
    ("ja-JP-NanamiNeural", "七海 (女)", "ja-JP", "Female"),
    ("ja-JP-KeitaNeural", "圭太 (男)", "ja-JP", "Male"),
    ("ko-KR-SunHiNeural", "선히 (여)", "ko-KR", "Female"),
    ("ko-KR-InJoonNeural", "인준 (남)", "ko-KR", "Male"),
]

OPENAI_VOICES = ["alloy", "ash", "coral", "echo", "fable", "onyx", "nova", "sage", "shimmer"]


def style_prompt(style_id: str) -> str:
    for s in STYLES:
        if s["id"] == style_id:
            return s["prompt"]
    return ""
