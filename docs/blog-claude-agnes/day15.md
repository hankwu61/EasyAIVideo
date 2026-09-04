# Day 15｜ffmpeg 入門：Ken Burns 動態鏡頭讓靜態圖動起來

> 30 天打造 AI 短影片生成平台（Claude Code × Agnes AI × Edge-TTS）— 第 15 天

## 今日目標
- `services/ffmpeg.py`：非同步執行、逾時、取消時清掉子程序、可設定 `ffmpeg_path`。
- `zoompan` 實作推近／拉遠／平移，6 倍預放大消除抖動。
- `KenBurnsVideo` 供應商：每場輸出等長無聲 mp4。

## 執行封裝

```python
def ffmpeg_bin(cfg) -> str:
    return cfg.render.ffmpeg_path or shutil.which("ffmpeg") or "ffmpeg"

async def run_ffmpeg(*args, timeout=600):
    proc = await asyncio.create_subprocess_exec(ffmpeg_bin(cfg), "-y", "-hide_banner", "-loglevel", "error", *args,
                                                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    try:
        _, err = await asyncio.wait_for(proc.communicate(), timeout)
    except (asyncio.TimeoutError, asyncio.CancelledError):
        proc.kill(); await proc.wait(); raise
    if proc.returncode != 0:
        raise ProviderError(f"ffmpeg 失敗：{err.decode(errors='ignore')[-800:]}")
```

`CancelledError` 時 kill，Day 20 的取消才不會留下殭屍程序。

## Ken Burns

| 鏡頭 | zoompan |
|---|---|
| zoom_in | `z='min(zoom+0.0008,1.25)'` 置中 |
| zoom_out | `z='if(eq(on,1),1.25,max(zoom-0.0008,1.0))'` 置中 |
| pan_left / right | `z='1.2'`，`x` 隨 `on/{frames}` 線性移動 |
| pan_up / down | `z='1.2'`，`y` 隨 `on/{frames}` 線性移動（直式用） |

```python
def zoompan(motion, frames, w, h):
    c = "x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
    table = {
        "zoom_in":  f"z='min(zoom+0.0008,1.25)':{c}",
        "zoom_out": f"z='if(eq(on,1),1.25,max(zoom-0.0008,1.0))':{c}",
        "pan_left": f"z='1.2':x='(iw-iw/zoom)*(1-on/{frames})':y='ih/2-(ih/zoom/2)'",
        "pan_right":f"z='1.2':x='(iw-iw/zoom)*(on/{frames})':y='ih/2-(ih/zoom/2)'",
        "pan_up":   f"z='1.2':x='iw/2-(iw/zoom/2)':y='(ih-ih/zoom)*(1-on/{frames})'",
        "pan_down": f"z='1.2':x='iw/2-(iw/zoom/2)':y='(ih-ih/zoom)*(on/{frames})'",
    }
    return f"zoompan={table[motion]}:d={frames}:s={w}x{h}:fps=30"

class KenBurnsVideo:
    name = "kenburns"
    async def generate(self, req: VideoRequest) -> Path:
        frames = int(req.duration * 30)
        motion = pick_motion(req)                      # 依比例與場景索引輪替
        vf = f"scale={req.width*6}:-1,{zoompan(motion, frames, req.width, req.height)},format=yuv420p"
        await run_ffmpeg("-loop", "1", "-i", str(req.start_image), "-vf", vf, "-t", f"{req.duration:.3f}",
                         "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-r", "30", "-an", str(req.output_path))
        return req.output_path
```

輸入圖是 1024 短邊，`scale` 到 6 倍後 zoompan 再輸出 1080p，畫質足夠且無鋸齒。

## 管線

`animate_scenes`：只做 `clip_path` 缺少的場景（圖片重生會清掉 `clip_path`）。`motion_override == "uploaded"` 的場景跳過。

## 讓 Claude Code 幫你調參數

「對 `scene_01.png` 用四種鏡頭各產生 4 秒片段，抽 3 幀存成 png 給我看」。它會寫一次性腳本、執行、回傳圖片，你只要選喜歡的。這種「產出多個候選讓我挑」的用法非常適合影音參數。

## 給 Claude Code 的提示詞
```
實作 services/ffmpeg.py（run_ffmpeg 含取消 kill、probe_duration、ffmpeg_path 設定）、providers/video/kenburns.py（六種鏡頭、6 倍預放大、-an）、
pipeline.animate_scenes。對一張 placeholder 圖產生 zoom_in 與 pan_up 各 5 秒，ffprobe 確認時長與解析度，各抽一幀給我看。
```

## 今日檢查清單
- [ ] 每場都有 `clip_XX.mp4`，長度 = `scene.duration`。
- [ ] 推近片段無抖動。
- [ ] ffmpeg 失敗時 API 回錯誤訊息而不是掛住。

## 明日預告
Day 16 PIL 字幕圖層：中文字型、描邊、安全區、卡拉 OK 樣式。
