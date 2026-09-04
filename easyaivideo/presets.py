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


TRANSITIONS = [
    {"id": "none", "label": "無轉場（直接接續）", "description": "極速直接拼接，無轉場動態"},
    {"id": "fade", "label": "淡入淡出 (Fade)", "description": "黑幕淡入淡出，經典平穩過渡"},
    {"id": "dissolve", "label": "疊化 (Dissolve)", "description": "兩畫面平滑交叉溶解"},
    {"id": "wipeleft", "label": "向左擦除 (Wipe Left)", "description": "新畫面由右向左推入切換"},
    {"id": "wiperight", "label": "向右擦除 (Wipe Right)", "description": "新畫面由左向右推入切換"},
    {"id": "slideup", "label": "向上滑動 (Slide Up)", "description": "新畫面由下向上推動進入"},
    {"id": "slidedown", "label": "向下滑動 (Slide Down)", "description": "新畫面由上向下推動進入"},
    {"id": "circlecrop", "label": "圓形縮放 (Circle Crop)", "description": "圓形向內縮小展開轉場"},
]

SUBTITLE_POSITIONS = [
    {"id": "bottom", "label": "畫面底部", "description": "標準影片字幕位置（垂直高度約 82% 處）"},
    {"id": "middle", "label": "畫面中央", "description": "強烈視覺焦點、短影音解說風格（垂直居中）"},
    {"id": "top", "label": "畫面頂部", "description": "頂部位置（垂直高度約 12% 處，避免遮擋核心動態）"},
]

FONTS = [
    {"id": "msjh", "label": "微軟正黑體", "family": "Microsoft JhengHei", "description": "清晰工整的繁體黑體"},
    {"id": "msyh", "label": "微軟雅黑", "family": "Microsoft YaHei", "description": "現代簡潔的黑體"},
    {"id": "simhei", "label": "黑體 / 粗黑", "family": "SimHei", "description": "粗體醒目，適合標題與解說"},
    {"id": "arial", "label": "Arial (英數推薦)", "family": "Arial", "description": "無襯線標準字型"},
    {"id": "noto", "label": "思源黑體 (Noto Sans)", "family": "Noto Sans CJK", "description": "多語系開源標準黑體"},
    {"id": "system", "label": "系統預設", "family": "sans-serif", "description": "使用作業系統預設無襯線字型"},
]

BUILTIN_TEMPLATES = [
    {
        "id": "tpl_cinematic",
        "name": "🎬 電影敘事風格",
        "description": "電影質感、微軟正黑體、底部經典字幕、淡入淡出轉場，營造沈浸大片感。",
        "category": "cinema",
        "cover_color": "from-amber-600 to-stone-900",
        "icon": "Film",
        "is_builtin": True,
        "config": {
            "style_id": "cinematic",
            "style_prompt": "cinematic photograph, dramatic natural lighting, shallow depth of field, ultra detailed, 35mm film look",
            "font_family": "msjh",
            "font_size": 24,
            "subtitle_position": "bottom",
            "transition": "fade",
            "transition_duration": 0.5,
            "bgm": None,
            "bgm_volume": 0.2,
        },
    },
    {
        "id": "tpl_anime",
        "name": "🎌 熱血日漫風格",
        "description": "日系清爽畫風、醒目粗黑字型、中央字幕、向左擦除轉場，節奏鮮明熱血。",
        "category": "anime",
        "cover_color": "from-pink-500 to-rose-700",
        "icon": "Sparkles",
        "is_builtin": True,
        "config": {
            "style_id": "anime",
            "style_prompt": "high quality anime illustration, clean line art, vibrant colors, detailed background, studio quality",
            "font_family": "simhei",
            "font_size": 26,
            "subtitle_position": "middle",
            "transition": "wipeleft",
            "transition_duration": 0.4,
            "bgm": None,
            "bgm_volume": 0.25,
        },
    },
    {
        "id": "tpl_short_video",
        "name": "📱 短影音解說風格",
        "description": "3D 卡通立體質感、畫面中央大字幕、向上滑動快節奏切換，專為 Shorts/Reels/TikTok 打造。",
        "category": "social",
        "cover_color": "from-blue-600 to-indigo-800",
        "icon": "Smartphone",
        "is_builtin": True,
        "config": {
            "style_id": "3d",
            "style_prompt": "3D rendered cartoon scene, Pixar style, soft global illumination, cute proportions, highly detailed",
            "font_family": "msyh",
            "font_size": 28,
            "subtitle_position": "middle",
            "transition": "slideup",
            "transition_duration": 0.4,
            "bgm": None,
            "bgm_volume": 0.2,
        },
    },
    {
        "id": "tpl_healing",
        "name": "🎨 治癒水彩繪本",
        "description": "溫柔水彩筆觸、頂部輕盈字幕、疊化柔和過渡，適合故事、心靈與睡前讀物。",
        "category": "art",
        "cover_color": "from-teal-400 to-emerald-700",
        "icon": "Palette",
        "is_builtin": True,
        "config": {
            "style_id": "watercolor",
            "style_prompt": "soft watercolor illustration, gentle brush strokes, pastel palette, paper texture, storybook style",
            "font_family": "msjh",
            "font_size": 22,
            "subtitle_position": "top",
            "transition": "dissolve",
            "transition_duration": 0.8,
            "bgm": None,
            "bgm_volume": 0.15,
        },
    },
    {
        "id": "tpl_cyberpunk",
        "name": "⚡ 賽博龐克未來",
        "description": "霓虹科幻未來感、Arial英數風格字幕、圓形縮放轉場，強烈科技氛圍。",
        "category": "scifi",
        "cover_color": "from-cyan-500 to-purple-800",
        "icon": "Zap",
        "is_builtin": True,
        "config": {
            "style_id": "cyberpunk",
            "style_prompt": "cyberpunk city aesthetic, neon lights, rain reflections, futuristic, high contrast, cinematic",
            "font_family": "arial",
            "font_size": 26,
            "subtitle_position": "bottom",
            "transition": "circlecrop",
            "transition_duration": 0.5,
            "bgm": None,
            "bgm_volume": 0.2,
        },
    },
    {
        "id": "tpl_minimal_sketch",
        "name": "📰 極簡黑白線條",
        "description": "極簡手繪線稿、思源黑體標準字幕、乾淨無轉場直接接續，專注內容乾貨傳遞。",
        "category": "minimal",
        "cover_color": "from-gray-600 to-slate-900",
        "icon": "PenTool",
        "is_builtin": True,
        "config": {
            "style_id": "sketch",
            "style_prompt": "minimalist black and white line sketch, simple strokes, hand drawn, white background",
            "font_family": "noto",
            "font_size": 24,
            "subtitle_position": "bottom",
            "transition": "none",
            "transition_duration": 0.5,
            "bgm": None,
            "bgm_volume": 0.15,
        },
    },
]

