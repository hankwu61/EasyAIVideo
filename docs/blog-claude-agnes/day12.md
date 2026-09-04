# Day 12｜風格一致性：prompt_prefix、負面提示與角色參考圖

> 30 天打造 AI 短影片生成平台（Claude Code × Agnes AI × Edge-TTS）— 第 12 天

## 今日目標
- `presets.py`：風格、比例、負面提示集中管理。
- 用 Agnes 圖片模型的 `image` 參考圖陣列讓角色在各場景一致。
- 風格錨點：第一張圖當後續場景的參考。

## 一致性三層

1. **文字層**：每個 `image_prompt` 後面接同一段風格描述 + 負面提示。最便宜。
2. **角色層**：先生成角色定妝照，含該角色的場景把定妝照當參考圖。
3. **錨點層**：第一場生成後當後續場景的參考，延續色調與筆觸。

## presets.py

```python
STYLES = {
    "cinematic": {"label": "電影感", "prompt": "cinematic photography, anamorphic lens, shallow depth of field, soft volumetric light, teal-orange grade"},
    "anime": {"label": "動漫", "prompt": "high quality anime illustration, clean lineart, cel shading, vibrant palette"},
    "flat": {"label": "扁平插畫", "prompt": "flat vector illustration, minimal shapes, pastel palette"},
    "watercolor": {"label": "水彩", "prompt": "watercolor painting, soft bleeding edges, paper texture"},
    "3d": {"label": "3D 卡通", "prompt": "3D render, Pixar-like character design, soft global illumination"},
}
NEGATIVE = "text, letters, captions, watermark, logo, signature, blurry, deformed hands, extra fingers"
ASPECTS = {"9:16": (1080, 1920), "16:9": (1920, 1080), "1:1": (1080, 1080)}
```

`GET /api/presets` 回風格、比例、轉場，以及 Edge-TTS 聲音清單（Day 13）。

## 角色參考圖

```python
class Character(BaseModel):
    id: str; name: str; appearance: str; gender: str = "other"
    voice: str = "zh-TW-HsiaoChenNeural"; image_path: str | None = None

class Project(BaseModel):
    ...
    characters: list[Character] = []
    anchor_first_scene: bool = False
```

角色圖：`POST /api/projects/{id}/characters/{cid}/image`，提示詞「character sheet, full body, front view, neutral background, {appearance}, {style}」。

Agnes `/images/generations` 的 `image` 欄位接受最多 4 張 data URI：

```python
def data_uri(p: Path) -> str:
    return "data:image/png;base64," + base64.b64encode(p.read_bytes()).decode()

def refs_for(self, project, scene) -> list[Path]:
    refs = [abs(c.image_path) for c in project.characters
            if c.image_path and c.name in (scene.narration + scene.image_prompt)]
    if project.anchor_first_scene and scene.index > 0 and project.scenes[0].image_path:
        refs.append(abs(project.scenes[0].image_path))
    return refs[:4]
```

提示詞裡明講「Keep the characters exactly as in the reference images」，並把角色的 `appearance` 直接寫進 `image_prompt`（Day 27 的改編提示詞會要求模型這麼做）。

`use_references` 只在 Agnes 圖片模型有效；DALL-E 類服務會忽略或報錯，所以設定頁註明。

## 模型選擇

`agnes-image-2.0-flash` 便宜快速，適合知識型；`agnes-image-2.1-flash` 對參考圖與細節更好，敘事型與有角色時用它。設定頁提供下拉，值來自 `/models` 過濾 `image`。

## 給 Claude Code 的提示詞
```
建立 presets.py 與 GET /api/presets；models 加 Character、characters、anchor_first_scene；角色圖生成路由；
OpenAICompatImage 的 data_uri 參考圖與 refs_for；設定頁模型下拉來源 /models 過濾。
用 8001 placeholder 跑通參考圖路徑（placeholder 忽略 refs 但要記錄 log）。
```

## 今日檢查清單
- [ ] `/api/presets` 回風格與比例。
- [ ] 含角色的場景請求 body 內有 `image` 陣列。
- [ ] 同一角色在三個場景外觀一致（真實模型驗證，一次即可）。

## 明日預告
Day 13 Edge-TTS 配音：免費神經語音、聲音清單、語速與重試。
