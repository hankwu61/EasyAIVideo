# Day 08｜提示詞工程：讓 Agnes 從主題寫出分鏡腳本與防禦性 JSON 解析

> 30 天打造 AI 短影片生成平台（Claude Code × Agnes AI × Edge-TTS）— 第 8 天

## 今日目標
- 建立 `prompts.py`，集中所有提示詞。
- 實作 `OpenAICompatLLM.write_script()`，輸出符合 Scene 結構的腳本。
- 建立提示詞版本化習慣。

## 腳本提示詞的四個要素

1. 角色與格式：你是誰、只輸出 JSON。
2. 內容約束：語言、總長度、場景數、每場字數、鉤子與結尾。
3. 畫面約束：`image_prompt` 英文、描述主體／構圖／光線／風格、禁止文字。
4. 動態約束：`video_prompt` 一句英文描述動作與運鏡，給 Agnes 影片模型。

## prompts.py

```python
SCRIPT_SYSTEM = """你是專業的短影片編劇與分鏡師。根據主題寫出 {aspect} 比例、約 {target_seconds} 秒的腳本。
規則：
- 旁白語言 {language}，口語自然、適合朗讀，不要條列、括號或舞台指示。
- 共 {scene_count} 個場景，每場旁白 {min_chars}–{max_chars} 字。第一場是 3 秒內抓住注意力的鉤子，最後一場是結論或行動呼籲。
- image_prompt：英文，描述主體、環境、構圖、光線、鏡頭，風格「{style}」。禁止任何文字、字幕、浮水印、logo。
- video_prompt：英文一句話，只描述動作與運鏡（slow push-in, pan left, gentle wind...）。
- 全片視覺風格一致。
只輸出 JSON：{{"title": "...", "scenes": [{{"narration": "...", "image_prompt": "...", "video_prompt": "..."}}]}}
"""

SCRIPT_USER = "主題：{topic}\n{extra}"
```

字數與場景數由程式算：中文每秒約 4 字，60 秒 ≈ 240 字，6 場，每場 30–50 字。

## schema 與供應商

```python
class SceneDraft(BaseModel):
    narration: str
    image_prompt: str
    video_prompt: str = ""

class ScriptDraft(BaseModel):
    title: str
    scenes: list[SceneDraft] = Field(min_length=1)
```

`providers/llm/openai_compat.py`：

```python
class OpenAICompatLLM:
    name = "openai_compat"

    def __init__(self, cfg: LLMConfig):
        self.cfg = cfg

    async def complete(self, prompt: str, *, system: str | None = None, json_mode: bool = False) -> str:
        body = {"model": self.cfg.model, "temperature": self.cfg.temperature,
                "messages": ([{"role": "system", "content": system}] if system else []) + [{"role": "user", "content": prompt}]}
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        async with httpx.AsyncClient(timeout=180) as client:
            r = await client.post(self.cfg.base_url.rstrip("/") + "/chat/completions", headers=self._headers(), json=body)
            if r.status_code == 400 and json_mode:
                body.pop("response_format")
                r = await client.post(..., json=body)
            if r.status_code >= 400:
                raise ProviderError(f"LLM HTTP {r.status_code}: {r.text[:300]}")
            return r.json()["choices"][0]["message"]["content"]

    async def complete_json(self, prompt, *, system, schema: type[T], retries=2) -> T:
        # Day 04 的三層防禦 + 驗證失敗回饋重試
        ...

    async def write_script(self, topic, *, language, style, aspect, target_seconds, extra="") -> ScriptDraft:
        n = max(3, min(12, round(target_seconds / 10)))
        chars = target_seconds * 4 // n
        system = SCRIPT_SYSTEM.format(aspect=aspect, target_seconds=target_seconds, language=language,
                                      scene_count=n, min_chars=int(chars * .7), max_chars=int(chars * 1.2),
                                      style=STYLE_PRESETS.get(style, style))
        return await self.complete_json(SCRIPT_USER.format(topic=topic, extra=extra), system=system, schema=ScriptDraft)

    async def test(self) -> str:
        return (await self.complete("回覆 OK"))[:20]
```

## 後處理

模型再聽話也會偶爾出錯，程式端做保險：

```python
def clean_narration(s: str) -> str:
    s = re.sub(r"[（(【\[].*?[)）】\]]", "", s)        # 去括號內舞台指示
    s = re.sub(r"[*_#`>]", "", s)                       # 去 markdown
    return re.sub(r"\s+", " ", s).strip()

def clean_image_prompt(s: str) -> str:
    return re.sub(r"\b(text|caption|subtitle|watermark|logo)\b.*", "", s, flags=re.I).strip(" ,.")
```

## 接進管線

```python
async def write_script(self, project):
    llm = self.providers.llm
    draft = await llm.write_script(project.topic, language=..., style=..., aspect=..., target_seconds=...)
    project.title = draft.title
    project.scenes = [Scene(index=i, narration=clean_narration(s.narration),
                            image_prompt=clean_image_prompt(s.image_prompt), video_prompt=s.video_prompt)
                      for i, s in enumerate(draft.scenes)]
    project.status = "scripted"
    await self.db.save_project(project)
```

路由 `POST /api/projects/{id}/script`，今天先同步執行。

## 提示詞版本化

`SCRIPT_SYSTEM` 上方註解 `# v1 2026-09-15`，改動時把舊版搬到 `docs/prompts_archive.md`。不同模型對同一提示詞表現差很多，有紀錄才能比。

## 用 Claude Code 調提示詞

把 Claude Code 當提示詞夥伴：「用 `scripts/try_prompt.py` 對『貓咪與紙箱』『台北捷運冷知識』『如何煮溏心蛋』各跑一次，列出旁白裡出現的括號或舞台指示，並提出提示詞修改建議」。它會實際執行、觀察、修改，比自己盲改快。

## 給 Claude Code 的提示詞
```
建立 prompts.py（SCRIPT_SYSTEM/SCRIPT_USER/STYLE_PRESETS）、providers/llm/schemas.py、providers/llm/openai_compat.py
（complete/complete_json/write_script/test，含 response_format 退回與驗證重試）、clean_narration/clean_image_prompt、
pipeline.write_script 與 POST /api/projects/{id}/script。config.yaml 的 llm 已設為 openai_compat + Agnes。
用 curl 建立主題「為什麼貓咪喜歡紙箱」並呼叫 /script，把 scenes 貼給我。
```

## 今日檢查清單
- [ ] `/script` 產生 5–7 個場景，欄位齊全。
- [ ] 旁白沒有括號、markdown。
- [ ] 提示詞只在 `prompts.py`。

## 明日預告
Day 09 貼上文稿：保留原文逐字切段、超長文粗切、txt/docx/pdf/epub 擷取與多編碼偵測。
