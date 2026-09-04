# Day 15｜ffmpeg 入門：Ken Burns 動態鏡頭讓靜態圖動起來

> 30 天打造 AI 短影片生成平台 — 第 15 天

## 今日目標
- 建立 `services/ffmpeg.py`：非同步執行 ffmpeg、統一錯誤處理。
- 用 `zoompan` 濾鏡實作 Ken Burns（推近、拉遠、平移）。
- 完成 `KenBurnsVideo` 供應商，為每個場景輸出等長的 mp4 片段。

## ffmpeg 執行封裝

```python
import asyncio, shutil

FFMPEG = shutil.which("ffmpeg") or "ffmpeg"
FFPROBE = shutil.which("ffprobe") or "ffprobe"

async def run_ffmpeg(*args: str, timeout: float = 600) -> None:
    proc = await asyncio.create_subprocess_exec(
        FFMPEG, "-y", "-hide_banner", "-loglevel", "error", *args,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    try:
        _, err = await asyncio.wait_for(proc.communicate(), timeout)
    except asyncio.TimeoutError:
        proc.kill(); raise RuntimeError("ffmpeg 逾時")
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg 失敗：{err.decode(errors='ignore')[-800:]}")

async def probe_duration(path) -> float:
    proc = await asyncio.create_subprocess_exec(
        FFPROBE, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path),
        stdout=asyncio.subprocess.PIPE)
    out, _ = await proc.communicate()
    return float(out.decode().strip())
```

`-y` 覆寫、`-loglevel error` 只留錯誤，錯誤訊息截尾 800 字回給前端顯示。

## Ken Burns 的原理

`zoompan` 濾鏡每一幀重新計算縮放倍率 `z` 與視窗左上角 `x`、`y`。常用四種鏡頭：

| 鏡頭 | z 表達式 | x / y |
|---|---|---|
| 推近 zoom in | `min(zoom+0.0008, 1.25)` | 置中：`iw/2-(iw/zoom/2)` |
| 拉遠 zoom out | `if(eq(on,1),1.25,max(zoom-0.0008,1.0))` | 置中 |
| 向左平移 pan left | 固定 1.2 | `x = (iw-iw/zoom)*(1-on/{frames})` |
| 向右平移 pan right | 固定 1.2 | `x = (iw-iw/zoom)*(on/{frames})` |

`on` 是輸出幀序號。

## 避免抖動的關鍵

`zoompan` 在 1080p 直接縮放會有明顯抖動。標準解法：**先放大到 4–6 倍再 zoompan，最後縮回輸出尺寸**：

```
scale=6480:-1, zoompan=..., scale=1080:1920
```

## KenBurnsVideo

```python
MOTIONS = ["zoom_in", "zoom_out", "pan_left", "pan_right"]

def zoompan_expr(motion: str, frames: int, w: int, h: int) -> str:
    center = "x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
    if motion == "zoom_in":
        return f"zoompan=z='min(zoom+0.0008,1.25)':{center}:d={frames}:s={w}x{h}:fps=30"
    if motion == "zoom_out":
        return f"zoompan=z='if(eq(on,1),1.25,max(zoom-0.0008,1.0))':{center}:d={frames}:s={w}x{h}:fps=30"
    if motion == "pan_left":
        return f"zoompan=z='1.2':x='(iw-iw/zoom)*(1-on/{frames})':y='ih/2-(ih/zoom/2)':d={frames}:s={w}x{h}:fps=30"
    return f"zoompan=z='1.2':x='(iw-iw/zoom)*(on/{frames})':y='ih/2-(ih/zoom/2)':d={frames}:s={w}x{h}:fps=30"

class KenBurnsVideo:
    async def animate(self, *, image, prompt, duration, aspect, out, last_image=None):
        w, h = ASPECTS[aspect]
        frames = int(duration * 30)
        motion = MOTIONS[hash(str(image)) % len(MOTIONS)]     # 同一張圖固定同一種鏡頭
        vf = f"scale={w*6}:-1,{zoompan_expr(motion, frames, w, h)},format=yuv420p"
        await run_ffmpeg("-loop", "1", "-i", str(image), "-vf", vf, "-t", f"{duration:.3f}",
                         "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-r", "30", "-an", str(out))
        return out
```

片段沒有音軌（`-an`），語音在 Day 17 合成階段再混進去，這樣 Veo 產的片段與 Ken Burns 片段可以用同一條合成流程。

## 讓使用者選鏡頭

`ProjectOptions.motion_style: Literal["auto", "zoom_in", "zoom_out", "pan", "static"]`。`auto` 交錯使用，`static` 就只是 `-loop 1` 靜態圖。

## 管線：animate_scenes

```python
async def animate_scenes(self, project, *, only=None, progress=None):
    for n, s in enumerate(project.scenes, 1):
        if only and s.id not in only and s.clip_path: continue
        out = pdir / f"clip_{s.index + 1:02d}.mp4"
        await self.providers.video.animate(image=abs(s.image_path), prompt=s.video_prompt,
                                          duration=s.duration, aspect=project.options.aspect, out=out)
        s.clip_path = rel(out); await self.db.save_project(project)
        if progress: await progress(n / len(project.scenes), f"動態片段 {n}/{len(project.scenes)}")
```

## 給 Antigravity 的提示詞
```
實作 services/ffmpeg.py（run_ffmpeg、probe_duration）、providers/video/kenburns.py（四種鏡頭、6 倍預放大、無音軌）、
motion_style 選項與 pipeline.animate_scenes。對一張 1080x1920 的 placeholder 圖產生 5 秒 zoom_in 片段，
用 ffprobe 確認時長與解析度，並截一幀給我看。
```

## 今日檢查清單
- [ ] 每個場景都有 `clip_XX.mp4`，長度等於 `scene.duration`。
- [ ] 推近片段肉眼看不到抖動。
- [ ] ffmpeg 失敗時 API 回傳含錯誤訊息的 500，而不是掛住。

## 明日預告
Day 16 用 PIL 畫標題與字幕的透明圖層，處理中文字型、描邊、安全區，讓字幕在手機上清楚可讀。
