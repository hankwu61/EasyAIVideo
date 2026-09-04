# Day 08｜提示詞工程：讓 Gemini 從主題寫出分鏡腳本（JSON Schema 輸出）

> 30 天打造 AI 短影片生成平台 — 第 8 天

## 今日目標
- 把 `prompts.py` 建起來，集中管理所有提示詞。
- 實作 Gemini LLM 供應商的 `write_script()`，輸出符合 Scene 結構的腳本。
- 建立「提示詞版本化」的習慣，方便日後 A/B。

## 腳本提示詞的四個要素

一個好的分鏡腳本提示詞要同時控制：

1. **角色與格式**：你是誰、輸出什麼。
2. **內容約束**：語言、總長度、場景數、每場旁白字數。
3. **畫面約束**：`image_prompt` 用英文、描述構圖／光線／風格、不能包含文字。
4. **動態約束**：`video_prompt` 描述動作與運鏡，給 Veo 用（Day 19）。

## prompts.py

```python
SCRIPT_SYSTEM = """你是專業的短影片編劇與分鏡師。
你會根據主題寫出適合 {aspect} 比例、約 {target_seconds} 秒的影片腳本。
規則：
- 旁白語言：{language}。語氣自然口語，適合配音朗讀，避免條列與括號。
- 場景數量：{scene_count} 個。每個場景旁白 {min_chars}–{max_chars} 字。
- 第一個場景必須是能在 3 秒內抓住注意力的鉤子。最後一個場景給出結論或行動呼籲。
- image_prompt：英文，描述主體、環境、構圖、光線、鏡頭與風格「{style}」。不得包含任何文字、字幕、浮水印、logo。
- video_prompt：英文，一句話描述主體動作與運鏡（例如 slow push-in, pan left），不描述靜態外觀。
- 所有場景的視覺風格必須一致。
"""

SCRIPT_USER = """主題：{topic}
{extra}
請輸出腳本。"""

# 風格預設會併入 {style}
STYLE_PRESETS = {
    "cinematic": "cinematic photography, shallow depth of field, soft volumetric light, 35mm",
    "anime": "anime illustration, clean lines, vibrant colors, Makoto Shinkai inspired",
    "flat": "flat vector illustration, minimal, pastel palette",
    "documentary": "realistic documentary photo, natural light",
    "watercolor": "watercolor painting, soft edges, paper texture",
}
```

把場景數與字數由程式依 `target_seconds` 推算：中文旁白約每秒 4 個字，60 秒 ≈ 240 字，分成 6 個場景，每場 30–50 字。

## 結構化輸出 schema

`providers/llm/schemas.py`：

```python
from pydantic import BaseModel, Field

class SceneDraft(BaseModel):
    narration: str = Field(description="旁白，使用指定語言")
    image_prompt: str = Field(description="English image prompt, no text in image")
    video_prompt: str = Field(description="English one-sentence motion/camera prompt")

class ScriptDraft(BaseModel):
    title: str = Field(description="影片標題，10 字內")
    scenes: list[SceneDraft]
```

## Gemini LLM 供應商

`providers/llm/gemini.py`：

```python
from google import genai
from google.genai import types
from easyaivideo.config import LLMCfg
from easyaivideo.prompts import SCRIPT_SYSTEM, SCRIPT_USER, STYLE_PRESETS
from .schemas import ScriptDraft

class GeminiLLM:
    def __init__(self, api_key: str, cfg: LLMCfg):
        self.client = genai.Client(api_key=api_key)
        self.cfg = cfg

    async def write_script(self, topic: str, *, language: str, style: str, aspect: str,
                           target_seconds: int, extra: str = "") -> ScriptDraft:
        scene_count = max(3, min(12, round(target_seconds / 10)))
        chars = target_seconds * 4 // scene_count
        system = SCRIPT_SYSTEM.format(
            aspect=aspect, target_seconds=target_seconds, language=language,
            scene_count=scene_count, min_chars=int(chars * 0.7), max_chars=int(chars * 1.2),
            style=STYLE_PRESETS.get(style, style))
        resp = await self.client.aio.models.generate_content(
            model=self.cfg.model,
            contents=SCRIPT_USER.format(topic=topic, extra=extra),
            config=types.GenerateContentConfig(
                system_instruction=system,
                response_mime_type="application/json",
                response_schema=ScriptDraft,
                temperature=self.cfg.temperature,
                thinking_config=types.ThinkingConfig(thinking_budget=self.cfg.thinking_budget),
            ),
        )
        if resp.parsed is None:
            raise RuntimeError(f"LLM 未回傳有效腳本：{resp.candidates[0].finish_reason}")
        return resp.parsed
```

## 接進管線

`services/pipeline.py` 的第一步：

```python
async def write_script(self, project: Project) -> Project:
    draft = await self.llm.write_script(
        project.topic, language=project.options.language, style=project.options.style,
        aspect=project.options.aspect, target_seconds=project.options.target_seconds)
    project.title = draft.title
    project.scenes = [
        Scene(index=i, narration=s.narration, image_prompt=s.image_prompt, video_prompt=s.video_prompt)
        for i, s in enumerate(draft.scenes)
    ]
    project.status = ProjectStatus.scripted
    await self.db.save_project(project)
    return project
```

加一個路由 `POST /api/projects/{id}/script`，今天先同步執行（Day 20 才丟進佇列）。

## 提示詞版本化

把 `SCRIPT_SYSTEM` 的版本寫在註解（`# v3 2026-09-11`），改動時複製舊版到 `prompts_archive.md`。之後你會發現同一個提示詞在不同模型上表現差很多，有紀錄才比得出來。

## 踩坑筆記
- 若旁白裡出現「（停頓）」「【畫面】」之類的舞台指示，TTS 會照唸。在 system prompt 明講「不要舞台指示」，並在程式端用正則清掉全形括號內容當保險。
- `image_prompt` 出現 "text saying ..." 會讓圖片模型畫出亂碼文字，一律禁止。
- 溫度 0.8 適合創意腳本；分段類任務用 0.2。

## 給 Antigravity 的提示詞
```
建立 easyaivideo/prompts.py（SCRIPT_SYSTEM、SCRIPT_USER、STYLE_PRESETS）、providers/llm/schemas.py、
providers/llm/gemini.py 的 write_script（async，使用 response_schema），以及 pipeline.write_script 與
POST /api/projects/{id}/script。用 curl 建一個主題「為什麼貓咪喜歡紙箱」的專案並呼叫 script，把回傳的 scenes 印給我看。
```

## 今日檢查清單
- [ ] 呼叫 `/script` 後專案有 5–7 個場景，每場都有 narration / image_prompt / video_prompt。
- [ ] 旁白沒有舞台指示與括號。
- [ ] 提示詞只存在於 `prompts.py`。

## 明日預告
Day 09 支援「貼上文稿」：長文本自動分段、對應場景、由 Gemini 補上圖片與影片提示詞。
