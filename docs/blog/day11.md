# Day 11｜場景圖生成：Gemini 原生圖片模型（Nano Banana）與 Imagen

> 30 天打造 AI 短影片生成平台 — 第 11 天

## 今日目標
- 實作 `GeminiImage`（`gemini-2.5-flash-image`）與 `ImagenImage`（`imagen-4.0-generate-001`）兩個供應商。
- 處理比例、尺寸與輸出檔案。
- 在管線中為每個場景生成圖片，並支援單場景重生。

## 兩種圖片模型怎麼選

| | Gemini 原生圖片（Nano Banana） | Imagen 4 |
|---|---|---|
| 呼叫方式 | `generate_content`，回傳含圖片的 part | `generate_images` 專用 API |
| 強項 | 理解長提示詞、可帶參考圖做角色一致、可對話式修圖 | 純文生圖品質穩定、明確的 `aspect_ratio` 參數 |
| 適合 | 有角色的敘事影片（Day 12、27） | 知識型、風景型影片 |

我們預設用 Gemini 原生圖片，因為之後角色一致性會靠它。

## GeminiImage

```python
from pathlib import Path
from google import genai
from google.genai import types
from PIL import Image
import io

ASPECT_HINT = {"9:16": "vertical 9:16 portrait", "16:9": "wide 16:9 landscape", "1:1": "square 1:1"}

class GeminiImage:
    def __init__(self, api_key: str, model: str):
        self.client = genai.Client(api_key=api_key)
        self.model = model

    async def generate(self, prompt: str, *, aspect: str, out: Path,
                       references: list[Path] | None = None, seed: int | None = None) -> Path:
        parts: list = []
        for ref in references or []:
            parts.append(types.Part.from_bytes(data=ref.read_bytes(), mime_type="image/png"))
        parts.append(f"{prompt}. Composition: {ASPECT_HINT[aspect]}. No text, no watermark.")

        resp = await self.client.aio.models.generate_content(
            model=self.model,
            contents=parts,
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE", "TEXT"],
                image_config=types.ImageConfig(aspect_ratio=aspect),
            ),
        )
        for part in resp.candidates[0].content.parts:
            if part.inline_data is not None:
                img = Image.open(io.BytesIO(part.inline_data.data)).convert("RGB")
                img = fit_aspect(img, aspect)      # 保險：裁到精確比例
                img.save(out, "PNG")
                return out
        raise RuntimeError("模型未回傳圖片，可能被安全政策擋下")
```

`fit_aspect` 用置中裁切把圖片修到 1080×1920 / 1920×1080 / 1080×1080，避免模型偶爾回傳非精確比例讓 ffmpeg 出錯。

## ImagenImage

```python
class ImagenImage:
    async def generate(self, prompt, *, aspect, out, references=None, seed=None):
        resp = await self.client.aio.models.generate_images(
            model=self.model,                      # imagen-4.0-generate-001
            prompt=prompt,
            config=types.GenerateImagesConfig(
                number_of_images=1,
                aspect_ratio=aspect,               # "9:16" | "16:9" | "1:1"
                person_generation="allow_adult",
            ),
        )
        resp.generated_images[0].image.save(str(out))
        return out
```

Imagen 不吃參考圖，`references` 直接忽略。

## 管線：generate_assets 的圖片部分

```python
async def generate_images(self, project: Project, *, only: set[str] | None = None, progress=None):
    pdir = self.projects.project_dir(project.id)
    targets = [s for s in project.scenes
               if (only is None or s.id in only) and (s.image_stale or not s.image_path)]
    for n, scene in enumerate(targets, 1):
        out = pdir / f"scene_{scene.index + 1:02d}.png"
        await self.providers.image.generate(
            self.style_prompt(project, scene), aspect=project.options.aspect, out=out)
        scene.image_path = str(out.relative_to(self.data_dir))
        scene.image_stale = False
        await self.db.save_project(project)      # 每張存一次，中斷也不會白做
        if progress: await progress(n / len(targets), f"場景圖 {n}/{len(targets)}")
```

`style_prompt` 會把風格預設接在場景提示詞後面，保證整支影片風格一致。

單場景重生的路由：`POST /api/projects/{id}/scenes/{scene_id}/image`，呼叫時 `only={scene_id}` 並強制 `image_stale=True`。

## 並行與配額

免費層圖片模型的每分鐘請求數不高，先用 `asyncio.Semaphore(2)` 限制並行數，Day 29 再加指數退避。

## 靜態檔案服務

`main.py` 掛載 `app.mount("/data", StaticFiles(directory=data_dir))`，前端就能用 `/data/projects/<id>/scene_01.png` 顯示縮圖。之後為了避免瀏覽器快取舊圖，URL 後面加 `?v=<updated_at>`。

## 給 Antigravity 的提示詞
```
實作 providers/image/gemini.py（generate_content + response_modalities IMAGE，支援 references 與 aspect_ratio）、
providers/image/imagen.py（generate_images）、fit_aspect 裁切、pipeline.generate_images（stale 判斷、逐張存檔、進度回呼、Semaphore(2)）、
單場景重生路由與 /data 靜態掛載。用 8001 埠的 placeholder 設定跑通後，再用真實金鑰對一個場景測一次。
```

## 今日檢查清單
- [ ] 每個場景都有 `scene_XX.png`，尺寸精確符合比例。
- [ ] 改 `image_prompt` 後只有該場景被標記過期並重生。
- [ ] 瀏覽器能開 `/data/projects/<id>/scene_01.png`。

## 明日預告
Day 12 風格一致性：風格預設、角色參考圖、Nano Banana 的多圖編輯，讓 6 張圖看起來像同一部片。
