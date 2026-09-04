# Day 19｜Veo 影片生成：文生影片、圖生影片與首尾幀

> 30 天打造 AI 短影片生成平台 — 第 19 天

## 今日目標
- 實作 `VeoVideo` 供應商：非同步操作、輪詢、下載。
- 支援三種模式：`t2v` 文生影片、`i2v` 圖生影片、`keyframes` 首尾幀。
- 處理片長限制：Veo 一段最多 8 秒，旁白更長時循環或補 Ken Burns。

## Veo 的基本形狀

Veo 是**長時間操作（long-running operation）**：送出請求拿到 operation，之後輪詢直到 `done`，再下載影片。付費層才能用；先在 AI Studio 的 Veo 介面試幾個提示詞，確認風格再寫程式。

```python
import asyncio
from pathlib import Path
from google import genai
from google.genai import types

class VeoVideo:
    def __init__(self, api_key: str, model: str, max_clip_seconds: int = 8, poll: float = 8.0):
        self.client = genai.Client(api_key=api_key)
        self.model, self.max_clip, self.poll = model, max_clip_seconds, poll

    async def animate(self, *, image: Path | None, prompt: str, duration: float, aspect: str, out: Path,
                      last_image: Path | None = None) -> Path:
        seconds = int(min(self.max_clip, max(4, round(duration))))
        cfg = types.GenerateVideosConfig(
            aspect_ratio="9:16" if aspect == "9:16" else "16:9",
            duration_seconds=seconds,
            number_of_videos=1,
            person_generation="allow_adult",
        )
        kwargs = {}
        if image is not None:
            kwargs["image"] = types.Image.from_file(location=str(image))
        if last_image is not None:
            cfg.last_frame = types.Image.from_file(location=str(last_image))

        op = await self.client.aio.models.generate_videos(model=self.model, prompt=prompt, config=cfg, **kwargs)
        while not op.done:
            await asyncio.sleep(self.poll)
            op = await self.client.aio.operations.get(op)
        if op.error:
            raise RuntimeError(f"Veo 失敗：{op.error}")
        video = op.response.generated_videos[0]
        await self.client.aio.files.download(file=video.video)
        video.video.save(str(out))
        return out
```

## 三種模式

| 模式 | 輸入 | 適合 |
|---|---|---|
| `i2v` 圖生影片（預設） | 場景圖當首幀 + `video_prompt` | 角色與構圖最穩定，因為圖已經是你審過的 |
| `t2v` 文生影片 | 只有 `video_prompt`（可附角色參考圖） | 想要完全交給 Veo 發揮、或場景不需要與圖片一致 |
| `keyframes` 首尾幀 | 本場景圖當首幀、下一場景圖當尾幀 | 場景之間自然銜接，像一鏡到底 |

`ProjectOptions.motion = "ai"` 時，`video_mode: Literal["i2v", "t2v", "keyframes"] = "i2v"`。

管線中：

```python
for i, s in enumerate(project.scenes):
    nxt = project.scenes[i + 1] if i + 1 < len(project.scenes) else None
    await self.providers.video.animate(
        image=abs(s.image_path) if mode != "t2v" else None,
        prompt=s.video_prompt or s.image_prompt,
        duration=s.duration, aspect=aspect, out=out,
        last_image=abs(nxt.image_path) if mode == "keyframes" and nxt else None)
```

## 片長不夠怎麼辦

旁白 15 秒、Veo 只給 8 秒。三個策略，依序嘗試：

1. **循環**：`-stream_loop -1 -t 15`，簡單但可能看到跳接。
2. **來回播放（boomerang）**：正放 + 倒放（`reverse`）串接，動作幅度小的場景很自然。
3. **Veo 續片**：把前一段的最後一幀截出來當下一段的首幀再生成一段。品質最好，成本翻倍。

預設用 boomerang，`ProjectOptions.long_scene_strategy` 可切換。

```python
async def boomerang(clip: Path, target: float, out: Path):
    await run_ffmpeg("-i", str(clip), "-filter_complex",
                     "[0:v]split[a][b];[b]reverse[r];[a][r]concat=n=2:v=1[v]",
                     "-map", "[v]", "-an", str(out / "bounce.mp4"))
    await run_ffmpeg("-stream_loop", "-1", "-i", str(out / "bounce.mp4"), "-t", f"{target:.3f}", "-c", "copy", str(out))
```

## 混合策略

一支 60 秒影片全用 Veo 相當貴。常見做法：第一場（鉤子）與最後一場用 Veo，中間用 Ken Burns。加一個場景層級的 `scene.motion_override: "kenburns" | "ai" | None`，工作台上每張圖旁邊一個開關。

## 成本提醒

Veo 依秒計價，先在設定頁顯示「本次預估：N 段 × M 秒」，並在任務開始前要求確認。Day 29 會做完整的費用估算。

## 給 Antigravity 的提示詞
```
實作 providers/video/veo.py（generate_videos + operations.get 輪詢 + files.download，支援 image/last_frame），
video_mode 三種模式的管線分流、boomerang 與 stream_loop 的補長策略、scene.motion_override。
Veo 需付費，請先只寫程式與單元測試（mock operation），不要真的呼叫；等我確認後再對一個場景測試。
```

## 今日檢查清單
- [ ] `i2v` 對一個場景成功產出片段，首幀與場景圖一致。
- [ ] 15 秒旁白的場景片段長度正確且無黑幀。
- [ ] 混合策略下只有指定場景呼叫 Veo。

## 明日預告
Day 20 背景任務佇列：所有耗時操作丟進佇列，進度即時回報、可取消，伺服器重啟自動恢復狀態。
