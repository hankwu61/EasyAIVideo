# Day 11｜Agnes 圖片生成：/images/generations、精確尺寸與 b64／URL 回傳

> 30 天打造 AI 短影片生成平台（Claude Code × Agnes AI × Edge-TTS）— 第 11 天

## 今日目標
- 實作 `OpenAICompatImage`：對 Agnes 圖片模型送 `/images/generations`。
- 尺寸策略：`exact`（依比例算 WxH，Agnes）與 `preset`（DALL-E 三種固定尺寸）。
- 回傳同時支援 `b64_json` 與 `url`，並在管線中逐場景生成與單場景重生。

## 尺寸

Agnes 圖片模型接受精確的 `"WxH"`。從專案比例與短邊算：

```python
# services/sizes.py
def aspect_size(w_ratio: int, h_ratio: int, short_edge: int, *, round_to=8, max_long_edge=2048) -> tuple[int, int]:
    if w_ratio >= h_ratio:
        h = short_edge; w = int(short_edge * w_ratio / h_ratio)
    else:
        w = short_edge; h = int(short_edge * h_ratio / w_ratio)
    scale = min(1.0, max_long_edge / max(w, h))
    w, h = int(w * scale) // round_to * round_to, int(h * scale) // round_to * round_to
    return w, h

ASPECT_RATIO = {"9:16": (9, 16), "16:9": (16, 9), "1:1": (1, 1)}
```

`short_edge=1024`：9:16 → 1024×1816、16:9 → 1816×1024、1:1 → 1024×1024。輸出影片是 1080p，合成階段會等比放大並裁切，Day 15 的 6 倍預放大會讓 Ken Burns 沒有鋸齒。

`size_mode: preset` 時回 `1024x1792` / `1792x1024` / `1024x1024`，給 DALL-E 類服務用。

## OpenAICompatImage

```python
class OpenAICompatImage:
    name = "openai_compat"

    async def generate(self, prompt, *, width, height, output_path, reference_images=None, seed=None):
        body = {"model": self.cfg.model, "prompt": self.full_prompt(prompt), "n": 1, "size": pick_size(self.cfg, width, height)}
        if self.cfg.model.startswith("dall-e"):
            body["response_format"] = "b64_json"
        refs = [p for p in (reference_images or []) if p.is_file()]
        if refs and self.cfg.use_references:
            body["image"] = [data_uri(p) for p in refs[:4]]          # Day 12
        async with httpx.AsyncClient(timeout=300) as client:
            r = await client.post(self.cfg.base_url.rstrip("/") + "/images/generations", headers=self._headers(), json=body)
            if r.status_code >= 400:
                raise ProviderError(f"Image HTTP {r.status_code}: {r.text[:300]}")
            item = r.json()["data"][0]
            if item.get("b64_json"):
                output_path.write_bytes(base64.b64decode(item["b64_json"]))
            elif item.get("url"):
                img = await client.get(item["url"], timeout=120); img.raise_for_status()
                output_path.write_bytes(img.content)
            else:
                raise ProviderError("回應既無 b64_json 也無 url")
        normalize(output_path, width, height)       # 轉 PNG、置中裁到精確比例
        return output_path

    def full_prompt(self, prompt: str) -> str:
        parts = [self.cfg.prompt_prefix, prompt]
        if self.cfg.negative_prompt:
            parts.append(f"Avoid: {self.cfg.negative_prompt}")
        return ". ".join(p for p in parts if p)
```

`url` 回傳通常有時效，拿到後立刻下載。

## 管線：generate_images

```python
async def generate_images(self, project, *, only=None, progress=None):
    w, h = aspect_size(*ASPECT_RATIO[project.options.aspect], self.cfg.image.short_edge)
    targets = [s for s in project.scenes if (only is None or s.id in only) and (s.image_stale or not s.image_path)]
    sem = asyncio.Semaphore(2)
    async def one(n, s):
        async with sem:
            out = pdir / f"scene_{s.index + 1:02d}.png"
            await self.providers.image.generate(self.scene_prompt(project, s), width=w, height=h, output_path=out,
                                                reference_images=self.refs_for(project, s))
            s.image_path, s.image_stale = rel(out), False
            s.clip_path = None                       # 圖變了，動態片段也要重做
            await self.db.save_project(project)
            if progress: await progress(n / len(targets), f"場景圖 {n}/{len(targets)}", scene_id=s.id)
    await asyncio.gather(*(one(i + 1, s) for i, s in enumerate(targets)))
```

單場景重生：`POST /api/projects/{id}/scenes/{sid}/image`。

## 靜態檔案

`app.mount("/data", StaticFiles(directory=data_dir))`，前端用 `/data/projects/<id>/scene_01.png?v=<updated_at>`。

## 給 Claude Code 的提示詞
```
實作 services/sizes.py（aspect_size、ASPECT_RATIO）、providers/image/openai_compat.py（size_mode、b64/url、prompt_prefix/negative、normalize 裁切）、
pipeline.generate_images（Semaphore(2)、逐張存檔、scene_id 進度）、單場景重生路由、/data 掛載。
先在 8001 用 placeholder 跑通；然後問我是否要用真實金鑰對「一個」場景測試，得到同意再執行。
```

## 今日檢查清單
- [ ] 每場都有 `scene_XX.png`，尺寸精確符合比例。
- [ ] 改 `image_prompt` 只有該場重生。
- [ ] `size_mode` 切 preset 時送出的 size 是三種固定值之一。

## 明日預告
Day 12 風格一致性：`prompt_prefix`、負面提示、角色參考圖（`image` 陣列）與風格錨點。
