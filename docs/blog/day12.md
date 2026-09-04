# Day 12｜風格一致性：風格預設、角色參考圖與多圖編輯

> 30 天打造 AI 短影片生成平台 — 第 12 天

## 今日目標
- 建立 `presets.py`：風格、比例、負面描述集中管理。
- 用 Nano Banana 的參考圖能力讓同一個角色在各場景長得一樣。
- 提供「以第一張圖為風格錨點」的選項。

## 一致性的三個層次

1. **文字層**：所有 `image_prompt` 後面都接同一段風格描述（Day 11 的 `style_prompt`）。這是最便宜、最有效的一步。
2. **角色層**：先生成一張角色定妝照，之後每個含該角色的場景都把定妝照當參考圖送給模型。
3. **錨點層**：第一個場景生成後，把它當作參考圖餵給後續場景，讓色調與筆觸延續。

## presets.py

```python
STYLES = {
    "cinematic": {
        "label": "電影感",
        "prompt": "cinematic photography, anamorphic lens, shallow depth of field, soft volumetric light, muted teal-orange grade",
    },
    "anime": {"label": "動漫", "prompt": "high quality anime illustration, clean lineart, cel shading, vibrant palette"},
    "flat": {"label": "扁平插畫", "prompt": "flat vector illustration, minimal shapes, pastel palette, no gradients"},
    "watercolor": {"label": "水彩", "prompt": "watercolor painting, soft bleeding edges, visible paper texture"},
    "3d": {"label": "3D 卡通", "prompt": "3D render, Pixar-like character design, soft global illumination, octane"},
}

NEGATIVE = "text, letters, captions, watermark, logo, signature, blurry, deformed hands, extra fingers"

ASPECTS = {"9:16": (1080, 1920), "16:9": (1920, 1080), "1:1": (1080, 1080)}

VOICES = [  # Gemini TTS 預建聲音的一部分，Day 13 會用到
    {"id": "Kore", "label": "Kore（沉穩女聲）"}, {"id": "Puck", "label": "Puck（活潑男聲）"},
    {"id": "Charon", "label": "Charon（低沉男聲）"}, {"id": "Aoede", "label": "Aoede（輕快女聲）"},
    {"id": "Leda", "label": "Leda（年輕女聲）"}, {"id": "Fenrir", "label": "Fenrir（有力男聲）"},
]
```

Gemini 原生圖片模型沒有獨立的 negative prompt 參數，我們把 `NEGATIVE` 以「Avoid: ...」的形式接在提示詞尾端；Imagen 可用 `negative_prompt` 參數。

## 角色參考圖

在 `Project` 加上：

```python
class Character(BaseModel):
    id: str
    name: str
    appearance: str          # 英文外觀描述
    image_path: str | None = None

class Project(BaseModel):
    ...
    characters: list[Character] = []
```

生成角色圖：`POST /api/projects/{id}/characters/{cid}/image`，提示詞為「character sheet, full body, neutral background, {appearance}, {style}」。

場景圖生成時，若 `config.image.use_references` 開啟，就把出現在該場景的角色圖一起送：

```python
refs = [self.abs(c.image_path) for c in project.characters
        if c.image_path and c.name in scene.narration + scene.image_prompt]
prompt = f"{scene.image_prompt}. Keep the characters exactly as in the reference images. {style}. Avoid: {NEGATIVE}"
await self.providers.image.generate(prompt, aspect=..., out=out, references=refs)
```

Nano Banana 最多可以帶多張參考圖，提示詞裡明講「reference image 1 is Amy, image 2 is the dog」效果最好。

## 風格錨點

`ProjectOptions.anchor_first_scene: bool = False`。開啟時第一場正常生成，其餘場景把第一張圖加進 `references` 並附上「Match the color palette and rendering style of the reference」。這對水彩、扁平這類風格特別有效。

## 對話式修圖（進階）

Nano Banana 支援「拿一張圖 + 一句指令」做局部修改。可以做一個「微調」按鈕：

```python
async def edit(self, image: Path, instruction: str, out: Path):
    resp = await self.client.aio.models.generate_content(
        model=self.model,
        contents=[types.Part.from_bytes(data=image.read_bytes(), mime_type="image/png"), instruction],
        config=types.GenerateContentConfig(response_modalities=["IMAGE"]),
    )
    ...
```

例如「把天空改成黃昏」「移除背景的路人」，比整張重生省時得多。

## 給 Antigravity 的提示詞
```
建立 easyaivideo/presets.py（STYLES、NEGATIVE、ASPECTS、VOICES）與 GET /api/presets。
在 models 加入 Character 與 project.characters、anchor_first_scene 選項；實作角色圖生成路由、
場景圖生成時的參考圖挑選邏輯，以及 GeminiImage.edit 與 POST /api/projects/{id}/scenes/{sid}/image/edit。
```

## 今日檢查清單
- [ ] `GET /api/presets` 回傳風格、比例、聲音清單。
- [ ] 同一角色在三個場景的圖片中髮型、服裝一致。
- [ ] 微調指令能修改既有圖片而非重畫。

## 明日預告
Day 13 接上 Gemini TTS：預建聲音、用自然語言控制語氣、多語言，把旁白變成語音並取得精確長度。
